import json
from datetime import date

from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from valuation.auth import SESSION_KEY, get_current_user, login_required
from valuation.forms import AnalystNoteForm, CSVUploadForm, ComparisonForm, DevelopmentPlanForm, LiveAnalysisEventForm, LiveAnalysisSessionForm, LoginForm, OnBallEventForm, PlayerValuationForm, ProgressTrackingForm, SignUpForm, SnapshotSimulationForm, UpliftSimulationForm
from valuation.i18n import LANGUAGES, get_language, get_translations, tr
from valuation.models import LiveAnalysisSession, LivePlayerEvaluation, Player, User
from valuation.services import (
    build_dashboard_payload,
    build_growth_insights,
    comparison_chart_data,
    csv_template_response_content,
    ensure_live_analysis_session,
    evolution_chart_data,
    generate_pdf_report,
    growth_chart_data,
    import_players_from_csv,
    live_analysis_summary,
    pillar_trend_chart_data,
    percentile_chart_data,
    radar_chart_data,
    save_analyst_note,
    save_development_plan,
    save_live_analysis_event,
    save_live_analysis_session,
    save_manual_history_snapshot,
    save_on_ball_event,
    save_player_bundle,
    save_progress_tracking,
    simulate_uplift,
)

TECHNICAL_INDICATORS = [
    "Passe certo",
    "Passe errado",
    "Passe progressivo",
    "Assistencia",
    "Finalizacao",
    "Finalizacao no alvo",
    "Drible certo",
    "Drible errado",
    "Cruzamento certo",
    "Cruzamento errado",
    "Perda de posse",
    "Falta cometida",
    "Falta sofrida",
]

DEFENSIVE_INDICATORS = [
    "Desarme",
    "Interceptacao",
    "Corte",
    "Duelo ganho",
    "Duelo perdido",
    "Duelo aereo ganho",
    "Duelo aereo perdido",
    "Pressao realizada",
    "Recuperacao de bola",
    "Cobertura defensiva correta",
    "Erro defensivo",
]

TACTICAL_INDICATORS = [
    "Posicionamento ofensivo",
    "Posicionamento defensivo",
    "Tomada de decisao",
    "Leitura de jogo",
    "Ocupacao de espacos",
    "Sincronizacao com a equipe",
    "Disciplina tatica",
]

PHYSICAL_INDICATORS = [
    "Distancia total percorrida",
    "Distancia em alta intensidade",
    "Numero de sprints",
    "Velocidade maxima",
    "Aceleracoes",
    "Desaceleracoes",
]

PSYCHOLOGICAL_INDICATORS = [
    "Concentracao",
    "Comunicacao",
    "Lideranca",
    "Reacao a pressao",
    "Controle emocional",
    "Comprometimento",
]

POSITION_SPECIFIC_INDICATORS = {
    "Goleiro": [
        "Defesa realizada",
        "Defesa dificil",
        "Saida do gol certa",
        "Saida do gol errada",
        "Reposicao curta certa",
        "Reposicao longa certa",
        "Erro com os pes",
        "Bola aerea interceptada",
    ],
    "Zagueiro / defensor": [
        "Corte",
        "Rebatida eficiente",
        "Cobertura certa",
        "Cobertura errada",
        "Duelo 1x1 ganho",
        "Duelo 1x1 perdido",
        "Passe vertical certo",
        "Erro de linha defensiva",
    ],
    "Lateral": [
        "Apoio ofensivo",
        "Cruzamento certo",
        "Cruzamento errado",
        "Recuperacao defensiva",
        "Duelo lateral ganho",
        "Duelo lateral perdido",
        "Infiltracao",
        "Erro de cobertura",
    ],
    "Volante / meio-campista": [
        "Inversao de jogo certa",
        "Passe entre linhas",
        "Recuperacao de posse",
        "Apoio na saida",
        "Quebra de pressao",
        "Perda de posse perigosa",
        "Cobertura defensiva",
        "Finalizacao de media distancia",
    ],
    "Meia / armador": [
        "Passe-chave",
        "Criacao de chance",
        "Assistencia",
        "Passe entre linhas",
        "Conducao progressiva",
        "Finalizacao",
        "Pressao pos-perda",
        "Perda de posse",
    ],
    "Atacante": [
        "Finalizacao",
        "Finalizacao no alvo",
        "Gol",
        "Ataque a profundidade",
        "Desmarque",
        "Pressao na saida rival",
        "Duelo ofensivo ganho",
        "Perda de chance clara",
    ],
}

POSITION_OPTIONS = list(POSITION_SPECIFIC_INDICATORS.keys())


def _default_counter_block(indicators):
    return {indicator: 0 for indicator in indicators}


def _default_score_block(indicators, default=None):
    return {indicator: default for indicator in indicators}


def _blank_live_evaluation_payload():
    return {
        "informacoes_gerais": {
            "nome_atleta": "",
            "numero_camisa": "",
            "posicao": "",
            "equipe": "",
            "adversario": "",
            "competicao": "",
            "data": date.today().isoformat(),
            "analista_responsavel": "",
            "minutos_jogados": "",
            "observacao_inicial": "",
            "player_id": "",
        },
        "indicadores_tecnicos": _default_counter_block(TECHNICAL_INDICATORS),
        "indicadores_defensivos": _default_counter_block(DEFENSIVE_INDICATORS),
        "indicadores_taticos": _default_score_block(TACTICAL_INDICATORS, default=3),
        "indicadores_fisicos": {
            "fonte": "manual",
            "arquivo_nome": "",
            "valores": {indicator: "" for indicator in PHYSICAL_INDICATORS},
        },
        "indicadores_psicologicos": _default_score_block(PSYCHOLOGICAL_INDICATORS, default=3),
        "indicadores_especificos_posicao": {
            "grupo_posicao": "",
            "valores": {},
        },
        "avaliacao_geral": {
            "resumo_do_desempenho": "",
            "pontos_fortes": "",
            "pontos_a_melhorar": "",
            "observacoes_finais": "",
        },
        "metadados": {
            "origem_dados_fisicos": "manual",
        },
    }


def _position_group_from_label(position_label):
    if position_label in POSITION_SPECIFIC_INDICATORS:
        return position_label
    normalized = (position_label or "").strip().lower()
    if not normalized:
        return ""
    if "gole" in normalized:
        return "Goleiro"
    if "zague" in normalized or "defen" in normalized:
        return "Zagueiro / defensor"
    if "lateral" in normalized:
        return "Lateral"
    if "volante" in normalized or "meio" in normalized or "mid" in normalized:
        return "Volante / meio-campista"
    if "meia" in normalized or "armador" in normalized:
        return "Meia / armador"
    if "atac" in normalized or "wing" in normalized or "forward" in normalized or "striker" in normalized:
        return "Atacante"
    return ""


def _hydrate_payload_from_player(payload, player):
    payload["informacoes_gerais"]["nome_atleta"] = player.name
    payload["informacoes_gerais"]["posicao"] = _position_group_from_label(player.position) or player.position
    payload["informacoes_gerais"]["equipe"] = player.club_origin
    payload["informacoes_gerais"]["player_id"] = str(player.id)
    position_group = _position_group_from_label(payload["informacoes_gerais"]["posicao"])
    payload["indicadores_especificos_posicao"]["grupo_posicao"] = position_group
    payload["indicadores_especificos_posicao"]["valores"] = _default_counter_block(
        POSITION_SPECIFIC_INDICATORS.get(position_group, [])
    )
    return payload


def _coerce_non_negative_int(value):
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return 0
    return max(numeric, 0)


def _coerce_score(value):
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return None
    if 1 <= numeric <= 5:
        return numeric
    return None


def _clean_text(value):
    return str(value or "").strip()


def _sanitize_live_payload(raw_payload):
    payload = _blank_live_evaluation_payload()
    source = raw_payload if isinstance(raw_payload, dict) else {}
    general_info = source.get("informacoes_gerais", {})
    payload["informacoes_gerais"].update(
        {
            "nome_atleta": _clean_text(general_info.get("nome_atleta")),
            "numero_camisa": _clean_text(general_info.get("numero_camisa")),
            "posicao": _clean_text(general_info.get("posicao")),
            "equipe": _clean_text(general_info.get("equipe")),
            "adversario": _clean_text(general_info.get("adversario")),
            "competicao": _clean_text(general_info.get("competicao")),
            "data": _clean_text(general_info.get("data")) or date.today().isoformat(),
            "analista_responsavel": _clean_text(general_info.get("analista_responsavel")),
            "minutos_jogados": _clean_text(general_info.get("minutos_jogados")),
            "observacao_inicial": _clean_text(general_info.get("observacao_inicial")),
            "player_id": _clean_text(general_info.get("player_id")),
        }
    )
    for indicator in TECHNICAL_INDICATORS:
        payload["indicadores_tecnicos"][indicator] = _coerce_non_negative_int(
            source.get("indicadores_tecnicos", {}).get(indicator)
        )
    for indicator in DEFENSIVE_INDICATORS:
        payload["indicadores_defensivos"][indicator] = _coerce_non_negative_int(
            source.get("indicadores_defensivos", {}).get(indicator)
        )
    for indicator in TACTICAL_INDICATORS:
        payload["indicadores_taticos"][indicator] = _coerce_score(
            source.get("indicadores_taticos", {}).get(indicator)
        )
    physical_source = _clean_text(source.get("indicadores_fisicos", {}).get("fonte")) or "manual"
    if physical_source not in {"manual", "arquivo"}:
        physical_source = "manual"
    payload["indicadores_fisicos"]["fonte"] = physical_source
    payload["indicadores_fisicos"]["arquivo_nome"] = _clean_text(
        source.get("indicadores_fisicos", {}).get("arquivo_nome")
    )
    for indicator in PHYSICAL_INDICATORS:
        payload["indicadores_fisicos"]["valores"][indicator] = _clean_text(
            source.get("indicadores_fisicos", {}).get("valores", {}).get(indicator)
        )
    for indicator in PSYCHOLOGICAL_INDICATORS:
        payload["indicadores_psicologicos"][indicator] = _coerce_score(
            source.get("indicadores_psicologicos", {}).get(indicator)
        )
    position_group = _position_group_from_label(
        source.get("indicadores_especificos_posicao", {}).get("grupo_posicao")
        or payload["informacoes_gerais"]["posicao"]
    )
    payload["indicadores_especificos_posicao"]["grupo_posicao"] = position_group
    payload["indicadores_especificos_posicao"]["valores"] = _default_counter_block(
        POSITION_SPECIFIC_INDICATORS.get(position_group, [])
    )
    source_position_values = source.get("indicadores_especificos_posicao", {}).get("valores", {})
    for indicator in POSITION_SPECIFIC_INDICATORS.get(position_group, []):
        payload["indicadores_especificos_posicao"]["valores"][indicator] = _coerce_non_negative_int(
            source_position_values.get(indicator)
        )
    payload["avaliacao_geral"].update(
        {
            "resumo_do_desempenho": _clean_text(source.get("avaliacao_geral", {}).get("resumo_do_desempenho")),
            "pontos_fortes": _clean_text(source.get("avaliacao_geral", {}).get("pontos_fortes")),
            "pontos_a_melhorar": _clean_text(source.get("avaliacao_geral", {}).get("pontos_a_melhorar")),
            "observacoes_finais": _clean_text(source.get("avaliacao_geral", {}).get("observacoes_finais")),
        }
    )
    payload["metadados"] = {
        "origem_dados_fisicos": physical_source,
    }
    return payload


def login_view(request):
    lang = get_language(request)
    if get_current_user(request):
        return redirect("dashboard")
    form = LoginForm(request.POST or None, lang=lang)
    if request.method == "POST" and form.is_valid():
        user = User.objects.filter(email__iexact=form.cleaned_data["email"]).first()
        if user and check_password(form.cleaned_data["password"], user.password_hash):
            request.session[SESSION_KEY] = user.id
            return redirect("dashboard")
        messages.error(request, tr(lang, "invalid_credentials"))
    return render(request, "valuation/login.html", {"form": form, "lang": lang, "t": get_translations(lang), "languages": LANGUAGES})


def signup_view(request):
    lang = get_language(request)
    if get_current_user(request):
        return redirect("dashboard")
    form = SignUpForm(request.POST or None, lang=lang)
    if request.method == "POST" and form.is_valid():
        if User.objects.filter(email__iexact=form.cleaned_data["email"]).exists():
            messages.error(request, tr(lang, "email_exists"))
        else:
            user = User.objects.create(
                email=form.cleaned_data["email"].lower(),
                password_hash=make_password(form.cleaned_data["password"]),
            )
            request.session[SESSION_KEY] = user.id
            return redirect("dashboard")
    return render(request, "valuation/signup.html", {"form": form, "lang": lang, "t": get_translations(lang), "languages": LANGUAGES})


def logout_view(request):
    request.session.pop(SESSION_KEY, None)
    return redirect("login")


@login_required
def dashboard_view(request):
    lang = get_language(request)
    projection_period = request.GET.get("projection_period", "12")
    current_user = get_current_user(request)
    players = list(
        Player.objects.filter(user=current_user).select_related(
            "performance_metrics",
            "market_metrics",
            "marketing_metrics",
            "behavior_metrics",
        ).prefetch_related("history", "development_plans", "progress_tracking")
    )
    comparison_form = ComparisonForm(request.GET or None, players=players)
    selected_ids = []
    if comparison_form.is_valid():
        selected_ids = [int(player_id) for player_id in comparison_form.cleaned_data["compare"]]
    selected_players = [player for player in players if player.id in selected_ids] or players[:3]
    featured_player = selected_players[0] if selected_players else (players[0] if players else None)
    snapshot_form = SnapshotSimulationForm(lang=lang, player=featured_player) if featured_player else None
    uplift_form = UpliftSimulationForm(request.POST or None, lang=lang, player=featured_player) if featured_player else None
    development_plan_form = DevelopmentPlanForm(lang=lang) if featured_player else None
    progress_tracking_form = ProgressTrackingForm(lang=lang) if featured_player else None
    uplift_result = None
    if request.method == "POST" and request.POST.get("form_name") == "uplift" and featured_player and uplift_form.is_valid():
        uplift_result = simulate_uplift(featured_player, uplift_form.cleaned_data, lang)

    context = {
        "current_user": current_user,
        "players_payload": build_dashboard_payload(players, lang),
        "comparison_form": comparison_form,
        "featured_player": featured_player,
        "selected_players": selected_players,
        "radar_chart": radar_chart_data(featured_player, lang) if featured_player else None,
        "growth_chart": growth_chart_data(featured_player, lang) if featured_player else None,
        "comparison_chart": comparison_chart_data(selected_players, lang) if selected_players else None,
        "percentile_chart": percentile_chart_data(players[:8], lang) if players else None,
        "evolution_chart": evolution_chart_data(featured_player, lang, projection_period) if featured_player else None,
        "pillar_trend_chart": pillar_trend_chart_data(featured_player, lang) if featured_player else None,
        "growth_insights": build_growth_insights(featured_player, lang, projection_period) if featured_player else None,
        "projection_period": projection_period,
        "projection_periods": ["3", "6", "12", "24"],
        "snapshot_form": snapshot_form,
        "uplift_form": uplift_form,
        "development_plan_form": development_plan_form,
        "progress_tracking_form": progress_tracking_form,
        "uplift_result": uplift_result,
        "lang": lang,
        "t": get_translations(lang),
        "languages": LANGUAGES,
    }
    if context["growth_insights"]:
        context["projected_growth_text"] = tr(lang, "projected_growth_sentence") % (
            context["growth_insights"]["projected_growth_pct"],
            context["growth_insights"]["period"],
        )
        context["main_driver_text"] = tr(lang, "main_driver_sentence") % context["growth_insights"]["main_driver"]
    return render(request, "valuation/dashboard.html", context)


@login_required
def live_analysis_view(request):
    lang = get_language(request)
    current_user = get_current_user(request)
    players = list(Player.objects.filter(user=current_user).order_by("name"))
    reports = list(
        LivePlayerEvaluation.objects.filter(user=current_user).select_related("player")
    )
    selected_player = None
    selected_report = None
    selected_player_id = request.GET.get("player")
    selected_report_id = request.GET.get("report")
    if selected_player_id:
        selected_player = get_object_or_404(Player, pk=selected_player_id, user=current_user)
    if selected_report_id:
        selected_report = get_object_or_404(
            LivePlayerEvaluation.objects.select_related("player"),
            pk=selected_report_id,
            user=current_user,
        )
        selected_player = selected_report.player or selected_player
    payload = _blank_live_evaluation_payload()
    if selected_report:
        payload = _sanitize_live_payload(selected_report.payload)
        payload["informacoes_gerais"]["player_id"] = str(selected_report.player_id or "")
    elif selected_player:
        payload = _hydrate_payload_from_player(payload, selected_player)
    return render(
        request,
        "valuation/live_analysis.html",
        {
            "current_user": current_user,
            "players": players,
            "player_autofill": [
                {
                    "id": player.id,
                    "name": player.name,
                    "team": player.club_origin,
                    "position_group": _position_group_from_label(player.position),
                }
                for player in players
            ],
            "selected_player": selected_player,
            "reports": reports,
            "selected_report": selected_report,
            "payload_json": json.dumps(payload, ensure_ascii=True),
            "blank_payload_json": json.dumps(_blank_live_evaluation_payload(), ensure_ascii=True),
            "position_options": POSITION_OPTIONS,
            "technical_indicators": TECHNICAL_INDICATORS,
            "defensive_indicators": DEFENSIVE_INDICATORS,
            "tactical_indicators": TACTICAL_INDICATORS,
            "physical_indicators": PHYSICAL_INDICATORS,
            "psychological_indicators": PSYCHOLOGICAL_INDICATORS,
            "position_specific_indicators": json.dumps(POSITION_SPECIFIC_INDICATORS, ensure_ascii=True),
            "lang": lang,
            "t": get_translations(lang),
            "languages": LANGUAGES,
        },
    )


@login_required
@require_http_methods(["POST"])
def live_analysis_session_view(request):
    lang = get_language(request)
    current_user = get_current_user(request)
    raw_payload = request.POST.get("payload_json", "")
    if not raw_payload:
        return HttpResponseBadRequest("payload_json is required")
    try:
        payload = _sanitize_live_payload(json.loads(raw_payload))
    except json.JSONDecodeError:
        return HttpResponseBadRequest("payload_json is invalid")

    general_info = payload["informacoes_gerais"]
    required_fields = {
        "nome_atleta": "Nome do atleta",
        "posicao": "Posicao",
        "equipe": "Equipe",
        "adversario": "Adversario",
        "competicao": "Competicao",
        "data": "Data",
        "analista_responsavel": "Analista responsavel",
    }
    for field_name, label in required_fields.items():
        if not general_info.get(field_name):
            messages.error(request, f"{label} e obrigatorio.")
            return redirect(f"{reverse('live-analysis')}?lang={lang}")

    player = None
    player_id = general_info.get("player_id")
    if player_id:
        player = get_object_or_404(Player, pk=player_id, user=current_user)

    report_id = request.POST.get("report_id")
    report = None
    if report_id:
        report = get_object_or_404(LivePlayerEvaluation, pk=report_id, user=current_user)

    shirt_number = general_info.get("numero_camisa")
    minutes_played = general_info.get("minutos_jogados")
    try:
        match_date = date.fromisoformat(general_info["data"])
    except ValueError:
        messages.error(request, "Data invalida.")
        return redirect(f"{reverse('live-analysis')}?lang={lang}")
    report_values = {
        "user": current_user,
        "player": player,
        "athlete_name": general_info["nome_atleta"],
        "shirt_number": _coerce_non_negative_int(shirt_number) if shirt_number else None,
        "position": general_info["posicao"],
        "team": general_info["equipe"],
        "opponent": general_info["adversario"],
        "competition": general_info["competicao"],
        "match_date": match_date,
        "analyst_name": general_info["analista_responsavel"],
        "minutes_played": _coerce_non_negative_int(minutes_played) if minutes_played else None,
        "physical_data_source": payload["indicadores_fisicos"]["fonte"],
        "payload": payload,
    }
    if report:
        for field_name, field_value in report_values.items():
            setattr(report, field_name, field_value)
        report.save()
    else:
        report = LivePlayerEvaluation.objects.create(**report_values)

    messages.success(request, "Ficha de analise ao vivo salva.")
    redirect_query = f"?report={report.id}&lang={lang}"
    return redirect(f"{reverse('live-analysis')}{redirect_query}")


@login_required
@require_http_methods(["POST"])
def player_snapshot_view(request, player_id):
    lang = get_language(request)
    current_user = get_current_user(request)
    player = get_object_or_404(Player, pk=player_id, user=current_user)
    form = SnapshotSimulationForm(request.POST, lang=lang, player=player)
    if form.is_valid():
        save_manual_history_snapshot(player, form.cleaned_data)
        messages.success(request, tr(lang, "snapshot_saved"))
    else:
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)
    return redirect(f"{reverse('dashboard')}?lang={lang}")


@login_required
@require_http_methods(["POST"])
def player_note_view(request, player_id):
    lang = get_language(request)
    current_user = get_current_user(request)
    player = get_object_or_404(Player, pk=player_id, user=current_user)
    form = AnalystNoteForm(request.POST, lang=lang)
    if form.is_valid():
        save_analyst_note(player, form.cleaned_data)
        messages.success(request, tr(lang, "note_saved"))
    else:
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)
    return redirect(f"{reverse('dashboard')}?lang={lang}")


@login_required
@require_http_methods(["POST"])
def player_plan_view(request, player_id):
    lang = get_language(request)
    current_user = get_current_user(request)
    player = get_object_or_404(Player, pk=player_id, user=current_user)
    form = DevelopmentPlanForm(request.POST, lang=lang)
    if form.is_valid():
        save_development_plan(player, form.cleaned_data)
        messages.success(request, tr(lang, "plan_saved"))
    else:
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)
    return redirect(f"{reverse('dashboard')}?lang={lang}")


@login_required
@require_http_methods(["POST"])
def player_progress_view(request, player_id):
    lang = get_language(request)
    current_user = get_current_user(request)
    player = get_object_or_404(Player, pk=player_id, user=current_user)
    form = ProgressTrackingForm(request.POST, lang=lang)
    if form.is_valid():
        save_progress_tracking(player, form.cleaned_data)
        messages.success(request, tr(lang, "progress_saved"))
    else:
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)
    return redirect(f"{reverse('dashboard')}?lang={lang}")


@login_required
@require_http_methods(["POST"])
def live_analysis_event_view(request):
    return JsonResponse({"ok": False, "message": "Timeline de eventos removida da analise ao vivo."}, status=410)


@login_required
@require_http_methods(["POST"])
def player_on_ball_event_view(request, player_id):
    lang = get_language(request)
    current_user = get_current_user(request)
    player = get_object_or_404(Player, pk=player_id, user=current_user)
    form = OnBallEventForm(request.POST, lang=lang)
    if form.is_valid():
        save_on_ball_event(player, form.cleaned_data)
        messages.success(request, tr(lang, "register_event"))
    else:
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)
    return redirect(f"{reverse('dashboard')}?lang={lang}")


@login_required
@require_http_methods(["GET", "POST"])
def player_create_view(request):
    lang = get_language(request)
    current_user = get_current_user(request)
    form = PlayerValuationForm(request.POST or None, lang=lang)
    if request.method == "POST" and form.is_valid():
        save_player_bundle(current_user, form.cleaned_data)
        messages.success(request, tr(lang, "player_saved"))
        return redirect("dashboard")
    return render(
        request,
        "valuation/player_form.html",
        {"form": form, "current_user": current_user, "page_title": tr(lang, "new_player"), "lang": lang, "t": get_translations(lang), "languages": LANGUAGES},
    )


@login_required
@require_http_methods(["GET", "POST"])
def player_edit_view(request, player_id):
    lang = get_language(request)
    current_user = get_current_user(request)
    player = get_object_or_404(
        Player.objects.select_related(
            "performance_metrics",
            "market_metrics",
            "marketing_metrics",
            "behavior_metrics",
        ),
        pk=player_id,
        user=current_user,
    )
    form = PlayerValuationForm(request.POST or None, player=player, lang=lang)
    if request.method == "POST" and form.is_valid():
        save_player_bundle(current_user, form.cleaned_data, player=player)
        messages.success(request, tr(lang, "player_updated"))
        return redirect("dashboard")
    return render(
        request,
        "valuation/player_form.html",
        {"form": form, "current_user": current_user, "page_title": f"{tr(lang, 'edit')} {player.name}", "player": player, "lang": lang, "t": get_translations(lang), "languages": LANGUAGES},
    )


@login_required
@require_http_methods(["GET", "POST"])
def csv_upload_view(request):
    lang = get_language(request)
    current_user = get_current_user(request)
    form = CSVUploadForm(request.POST or None, request.FILES or None, lang=lang)
    if request.method == "POST" and form.is_valid():
        result = import_players_from_csv(current_user, form.cleaned_data["csv_file"])
        if result.created:
            messages.success(request, f"{result.created} {tr(lang, 'players_imported')}")
        for error in result.errors[:10]:
            messages.error(request, error)
        return redirect("dashboard")
    return render(request, "valuation/upload.html", {"form": form, "current_user": current_user, "lang": lang, "t": get_translations(lang), "languages": LANGUAGES})


@login_required
def csv_template_view(request):
    lang = get_language(request)
    response = HttpResponse(csv_template_response_content(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="hb_eleven_template_{lang}.csv"'
    return response


@login_required
def export_report_view(request, player_id):
    lang = get_language(request)
    current_user = get_current_user(request)
    player = get_object_or_404(
        Player.objects.select_related(
            "performance_metrics",
            "market_metrics",
            "marketing_metrics",
            "behavior_metrics",
        ),
        pk=player_id,
        user=current_user,
    )
    response = HttpResponse(generate_pdf_report(player, lang), content_type="application/pdf")
    slug = player.name.lower().replace(" ", "_")
    response["Content-Disposition"] = f'attachment; filename="{slug}_valuation_report.pdf"'
    return response
