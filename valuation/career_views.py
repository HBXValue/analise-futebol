from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from catalog.models import Country, Division
from clubs.models import Club
from valuation.ai_service import get_cached_ai_dashboard_insight
from valuation.auth import get_current_user, login_required
from valuation.career_forms import (
    CareerCaseForm,
    CareerPrognosisForm,
    ClubContextForm,
    CoachProfileForm,
    CompetitorComparisonForm,
    CompetitiveDiagnosisForm,
    IndividualDevelopmentPlanForm,
    PositionCompetitorForm,
    TacticalGameModelForm,
)
from valuation.career_services import (
    apply_player_defaults,
    case_completion,
    comparison_matrix,
    CareerPlanGenerationError,
    generate_career_report_pdf,
    generate_ai_development_plan,
    get_career_step_label,
    step_links,
)
from valuation.constants import CAREER_SQUAD_STATUS_LABELS, get_localized_choice_label
from valuation.models import (
    CareerIntelligenceCase,
    ClubCompetitiveContext,
    CoachProfile,
    CompetitorComparison,
    CompetitiveDiagnosis,
    IndividualDevelopmentPlan,
    Player,
    PositionCompetitor,
    TacticalGameModel,
    CareerPrognosis,
)
from valuation.i18n import LANGUAGES, get_language, get_translations, tr
from valuation.services import sync_integrated_player_modules
from valuation.ui_context import build_global_player_context


def _case_queryset(user):
    return CareerIntelligenceCase.objects.filter(user=user).select_related(
        "player__division_reference__country",
        "player__club_reference",
        "club_context",
        "coach_profile",
        "game_model",
        "diagnosis",
        "prognosis",
        "development_plan_v2",
    ).prefetch_related("competitors", "comparisons")


@login_required
def career_case_list_view(request):
    lang = get_language(request)
    current_user = get_current_user(request)
    players = list(Player.objects.filter(user=current_user).select_related("division_reference__country", "club_reference"))
    for case_player in players:
        sync_integrated_player_modules(case_player)
    cases = _case_queryset(current_user)
    selected_player = None
    selected_player_id = request.GET.get("athlete")
    if selected_player_id:
        try:
            selected_player = next((player for player in players if player.id == int(selected_player_id)), None)
        except (TypeError, ValueError):
            selected_player = None
    context = {
        "current_user": current_user,
        "cases": cases,
        "players": players,
        "selected_player": selected_player,
        "ai_dashboard_insight": get_cached_ai_dashboard_insight(selected_player, lang, 90, scope="performance") if selected_player else None,
        "case_rows": [{"case": case, "step_label": get_career_step_label(case.current_step, lang)} for case in cases],
        "countries": list(Country.objects.filter(is_active=True).order_by("name")),
        "division_suggestions": list(
            Division.objects.filter(is_active=True).select_related("country").order_by("country__name", "scope", "state", "level", "name")
        ),
        "club_suggestions": list(
            Club.objects.filter(status=Club.Status.ACTIVE).select_related("country", "division").order_by("official_name")
        ),
        "lang": lang,
        "t": get_translations(lang),
        "languages": LANGUAGES,
    }
    context.update(build_global_player_context(request, current_user, selected_player))
    return render(request, "valuation/career_case_list.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def career_case_create_view(request):
    lang = get_language(request)
    current_user = get_current_user(request)
    form = CareerCaseForm(request.POST or None, user=current_user, lang=lang)
    if request.method == "POST" and form.is_valid():
        draft_case = form.save(commit=False)
        case = draft_case
        case.user = current_user
        if draft_case.player:
            case = sync_integrated_player_modules(draft_case.player)
            for field_name in form.Meta.fields:
                if field_name == "player":
                    continue
                setattr(case, field_name, getattr(draft_case, field_name))
            case.user = current_user
        apply_player_defaults(case)
        case.save()
        messages.success(request, tr(lang, "career_case_created"))
        return redirect(f"{reverse('career-case-step', args=[case.id, 'club'])}?lang={lang}")
    context = {
        "current_user": current_user,
        "case": None,
        "step": "athlete",
        "step_links": step_links("athlete", lang),
        "section_title": tr(lang, "career_section_athlete"),
        "form": form,
        "submit_label": tr(lang, "save_and_continue"),
        "completion": {},
        "lang": lang,
        "t": get_translations(lang),
        "languages": LANGUAGES,
    }
    context.update(build_global_player_context(request, current_user))
    return render(request, "valuation/career_case_form.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def career_case_step_view(request, case_id, step):
    lang = get_language(request)
    current_user = get_current_user(request)
    case = get_object_or_404(_case_queryset(current_user), pk=case_id)
    completion = case_completion(case)
    template_context = {
        "current_user": current_user,
        "case": case,
        "step": step,
        "step_links": step_links(step, lang),
        "completion": completion,
        "competitors": case.competitors.all(),
        "comparison_rows": comparison_matrix(case),
        "localized_squad_status": get_localized_choice_label(CAREER_SQUAD_STATUS_LABELS, case.squad_status, lang),
        "lang": lang,
        "t": get_translations(lang),
        "languages": LANGUAGES,
    }

    if step == "athlete":
        form = CareerCaseForm(request.POST or None, instance=case, user=current_user, lang=lang)
        if request.method == "POST" and form.is_valid():
            case = form.save(commit=False)
            if case.player:
                sync_integrated_player_modules(case.player)
            apply_player_defaults(case)
            case.current_step = "club"
            case.save()
            messages.success(request, tr(lang, "career_athlete_updated"))
            return redirect(f"{reverse('career-case-step', args=[case.id, 'club'])}?lang={lang}")
        template_context.update({
            "section_title": tr(lang, "career_section_athlete"),
            "form": form,
            "submit_label": tr(lang, "save_and_continue"),
        })
    elif step == "club":
        instance, _ = ClubCompetitiveContext.objects.get_or_create(
            case=case,
            defaults={"club_name": case.current_club or "", "competition": "", "team_moment": "development", "pressure_level": "medium", "club_philosophy": "mixed"},
        )
        form = ClubContextForm(request.POST or None, instance=instance)
        if request.method == "POST" and form.is_valid():
            club = form.save(commit=False)
            club.case = case
            club.save()
            case.current_step = "coach"
            case.save(update_fields=["current_step", "updated_at"])
            messages.success(request, tr(lang, "career_club_updated"))
            return redirect(f"{reverse('career-case-step', args=[case.id, 'coach'])}?lang={lang}")
        template_context.update({
            "section_title": tr(lang, "career_section_club"),
            "form": form,
            "submit_label": tr(lang, "save_and_continue"),
        })
    elif step == "coach":
        instance, _ = CoachProfile.objects.get_or_create(
            case=case,
            defaults={
                "coach_name": "",
                "profile_type": "developer",
                "experience_preference": "balanced",
                "physical_demand": "medium",
                "tactical_demand": "medium",
            },
        )
        form = CoachProfileForm(request.POST or None, instance=instance)
        if request.method == "POST" and form.is_valid():
            coach = form.save(commit=False)
            coach.case = case
            coach.save()
            case.current_step = "game_model"
            case.save(update_fields=["current_step", "updated_at"])
            messages.success(request, tr(lang, "career_coach_updated"))
            return redirect(f"{reverse('career-case-step', args=[case.id, 'game_model'])}?lang={lang}")
        template_context.update({
            "section_title": tr(lang, "career_section_coach"),
            "form": form,
            "submit_label": tr(lang, "save_and_continue"),
        })
    elif step == "game_model":
        instance, _ = TacticalGameModel.objects.get_or_create(case=case)
        form = TacticalGameModelForm(request.POST or None, instance=instance)
        if request.method == "POST" and form.is_valid():
            model = form.save(commit=False)
            model.case = case
            model.save()
            case.current_step = "competition"
            case.save(update_fields=["current_step", "updated_at"])
            messages.success(request, tr(lang, "career_game_model_updated"))
            return redirect(f"{reverse('career-case-step', args=[case.id, 'competition'])}?lang={lang}")
        template_context.update({
            "section_title": tr(lang, "career_section_game_model"),
            "form": form,
            "submit_label": tr(lang, "save_and_continue"),
        })
    elif step == "competition":
        competitor_form = PositionCompetitorForm(request.POST or None, prefix="competitor", lang=lang)
        comparison_form = CompetitorComparisonForm(request.POST or None, prefix="comparison", case=case)
        if request.method == "POST":
            action = request.POST.get("action")
            if action == "add_competitor" and competitor_form.is_valid():
                competitor = competitor_form.save(commit=False)
                competitor.case = case
                competitor.save()
                messages.success(request, tr(lang, "career_competitor_saved"))
                return redirect(f"{reverse('career-case-step', args=[case.id, 'competition'])}?lang={lang}")
            if action == "add_comparison" and comparison_form.is_valid():
                comparison = comparison_form.save(commit=False)
                comparison.case = case
                comparison.save()
                messages.success(request, tr(lang, "career_comparison_saved"))
                return redirect(f"{reverse('career-case-step', args=[case.id, 'competition'])}?lang={lang}")
            if action == "continue":
                case.current_step = "diagnosis"
                case.save(update_fields=["current_step", "updated_at"])
                return redirect(f"{reverse('career-case-step', args=[case.id, 'diagnosis'])}?lang={lang}")
        template_context.update({
            "section_title": tr(lang, "career_section_competition"),
            "competitor_form": competitor_form,
            "comparison_form": comparison_form,
            "submit_label": tr(lang, "career_save_competition"),
        })
    elif step == "diagnosis":
        instance, _ = CompetitiveDiagnosis.objects.get_or_create(case=case, defaults={"main_reason": "technical_gap"})
        form = CompetitiveDiagnosisForm(request.POST or None, instance=instance)
        if request.method == "POST" and form.is_valid():
            diagnosis = form.save(commit=False)
            diagnosis.case = case
            diagnosis.save()
            case.current_step = "prognosis"
            case.save(update_fields=["current_step", "updated_at"])
            messages.success(request, tr(lang, "career_diagnosis_saved"))
            return redirect(f"{reverse('career-case-step', args=[case.id, 'prognosis'])}?lang={lang}")
        template_context.update({
            "section_title": tr(lang, "career_section_diagnosis"),
            "form": form,
            "submit_label": tr(lang, "save_and_continue"),
        })
    elif step == "prognosis":
        instance, _ = CareerPrognosis.objects.get_or_create(case=case, defaults={"classification": "moderate", "timeframe": "medium", "justification": ""})
        form = CareerPrognosisForm(request.POST or None, instance=instance)
        if request.method == "POST" and form.is_valid():
            prognosis = form.save(commit=False)
            prognosis.case = case
            prognosis.save()
            case.current_step = "development"
            case.save(update_fields=["current_step", "updated_at"])
            messages.success(request, tr(lang, "career_prognosis_saved"))
            return redirect(f"{reverse('career-case-step', args=[case.id, 'development'])}?lang={lang}")
        template_context.update({
            "section_title": tr(lang, "career_section_prognosis"),
            "form": form,
            "submit_label": tr(lang, "save_and_continue"),
        })
    elif step == "development":
        instance, _ = IndividualDevelopmentPlan.objects.get_or_create(case=case)
        form = IndividualDevelopmentPlanForm(request.POST or None, instance=instance)
        if request.method == "POST":
            action = request.POST.get("action", "save")
            if action == "generate_ai_plan":
                try:
                    suggestion = generate_ai_development_plan(case)
                    for field_name, field_value in suggestion.items():
                        setattr(instance, field_name, field_value)
                    instance.case = case
                    instance.save()
                    form = IndividualDevelopmentPlanForm(instance=instance)
                    messages.success(request, tr(lang, "career_ai_plan_generated"))
                except CareerPlanGenerationError as exc:
                    messages.error(request, str(exc))
            elif form.is_valid():
                plan = form.save(commit=False)
                plan.case = case
                plan.save()
                case.current_step = "report"
                case.save(update_fields=["current_step", "updated_at"])
                messages.success(request, tr(lang, "career_plan_saved"))
                return redirect(f"{reverse('career-case-step', args=[case.id, 'report'])}?lang={lang}")
        template_context.update({
            "section_title": tr(lang, "career_section_development"),
            "form": form,
            "submit_label": tr(lang, "save_and_continue"),
        })
    elif step == "report":
        if request.method == "POST":
            case.current_step = "report"
            case.report_generated_at = timezone.now()
            case.save(update_fields=["current_step", "report_generated_at", "updated_at"])
            messages.success(request, tr(lang, "career_report_consolidated"))
            return redirect(f"{reverse('career-case-step', args=[case.id, 'report'])}?lang={lang}")
        template_context.update({
            "section_title": tr(lang, "career_section_report"),
            "report_ready": completion["report"],
        })
    else:
        return redirect(f"{reverse('career-case-step', args=[case.id, 'athlete'])}?lang={lang}")

    template_context.update(build_global_player_context(request, current_user, case.player if case.player_id else None))
    return render(request, "valuation/career_case_form.html", template_context)


@login_required
def career_case_report_pdf_view(request, case_id):
    lang = get_language(request)
    current_user = get_current_user(request)
    case = get_object_or_404(_case_queryset(current_user), pk=case_id)
    response = HttpResponse(generate_career_report_pdf(case, lang), content_type="application/pdf")
    slug = case.athlete_name.lower().replace(" ", "_")
    response["Content-Disposition"] = f'attachment; filename="{slug}_career_report.pdf"'
    return response
