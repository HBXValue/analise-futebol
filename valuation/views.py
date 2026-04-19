import json
import os
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from catalog.models import Country, Division
from clubs.models import Club
from valuation.auth import SESSION_KEY, get_current_user, login_required
from valuation.ai_service import generate_ai_dashboard_insight, get_cached_ai_dashboard_insight
from valuation.constants import get_position_group
from valuation.forms import AnalystNoteForm, AthleteCareerEntryForm, CSVUploadForm, ComparisonForm, DevelopmentPlanForm, GoCarrieraCheckInForm, LiveAnalysisEventForm, LiveAnalysisSessionForm, LoginForm, OnBallEventForm, PlayerValuationForm, ProgressTrackingForm, SignUpForm, SnapshotSimulationForm, UpliftSimulationForm
from valuation.i18n import LANGUAGES, get_language, get_translations, tr
from valuation.models import CareerIntelligenceCase, DataSourceLog, LiveAnalysisSession, LivePlayerEvaluation, Player, ScenarioLab, User
from valuation.ui_context import build_global_player_context
from valuation.services import (
    build_dashboard_payload,
    build_dashboard_executive_payload,
    build_athlete360_overview_payload,
    Athlete360Orchestrator,
    build_comparative_intelligence,
    build_projection_intelligence,
    build_opportunity_intelligence,
    build_reports_executive_payload,
    build_hbx_seed_from_profile,
    build_data_hub_payload,
    build_match_analysis_payload,
    build_market_intelligence_payload,
    build_growth_insights,
    build_behavioral_intelligence,
    calculate_scores,
    clamp,
    compute_hbx_value_profile,
    fetch_tiktok_signals,
    fetch_instagram_signals,
    fetch_youtube_signals,
    fetch_google_news_signals,
    comparison_chart_data,
    csv_template_response_content,
    ensure_live_analysis_session,
    evolution_chart_data,
    generate_pdf_report,
    growth_chart_data,
    import_players_from_csv,
    live_analysis_summary,
    longitudinal_delta_chart_data,
    longitudinal_bi_payload,
    normalize,
    pillar_trend_chart_data,
    percentile_chart_data,
    radar_chart_data,
    score_composition_chart_data,
    player_timeline_events,
    get_hbx_value_profile,
    save_analyst_note,
    save_athlete_career_entry,
    save_athlete_contract,
    save_athlete_transfer,
    save_go_carriera_checkin,
    save_development_plan,
    save_hbx_value_profile,
    save_live_analysis_event,
    save_live_analysis_session,
    save_manual_history_snapshot,
    save_on_ball_event,
    save_player_bundle,
    save_progress_tracking,
    save_scenario_lab_entry,
    simulate_uplift,
    sync_live_report_to_integrated_modules,
    sync_integrated_player_modules,
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
    mapped_group = get_position_group(position_label)
    if mapped_group:
        return mapped_group
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


def _player_club_name(player):
    if player.club_reference_id:
        return player.club_reference.short_name or player.club_reference.official_name
    return player.club_origin or ""


def _player_division_name(player):
    if player.division_reference_id:
        return player.division_reference.short_name or player.division_reference.name
    return player.league_level or ""


def _apply_player_identity_to_live_payload(payload, player):
    general_info = payload["informacoes_gerais"]
    position = _position_group_from_label(player.position) or player.position
    existing_position_values = payload["indicadores_especificos_posicao"].get("valores", {})
    general_info.update(
        {
            "nome_atleta": player.name,
            "posicao": position,
            "equipe": _player_club_name(player),
            "player_id": str(player.id),
        }
    )
    position_group = _position_group_from_label(position)
    payload["indicadores_especificos_posicao"]["grupo_posicao"] = position_group
    payload["indicadores_especificos_posicao"]["valores"] = {
        indicator: _coerce_non_negative_int(existing_position_values.get(indicator, 0))
        for indicator in POSITION_SPECIFIC_INDICATORS.get(position_group, [])
    }
    return payload


def _hydrate_payload_from_player(payload, player):
    return _apply_player_identity_to_live_payload(payload, player)


def _coerce_non_negative_int(value):
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return 0
    return max(numeric, 0)


def _build_hbx_value_score_seed(player):
    scores = calculate_scores(player)
    marketing = player.marketing_metrics
    market = player.market_metrics
    performance = player.performance_metrics
    public_name = player.public_name or player.name
    google_news_query = marketing.google_news_query or public_name
    youtube_query = marketing.youtube_query or public_name
    social_reach_score = round(normalize(marketing.followers, "followers"), 2)
    mention_volume = int(round(marketing.media_mentions))
    mention_momentum = round(clamp(50 + market.annual_growth), 2)
    source_relevance = round((market.club_interest + market.club_reputation) / 2, 2)
    estimated_reach = round((social_reach_score * 0.65) + (normalize(marketing.engagement, "engagement") * 0.35), 2)
    performance_signal = round(
        (scores["performance_score"] * 0.55)
        + (normalize(performance.xg + performance.xa, "xg_xa") * 0.20)
        + (normalize(performance.final_third_recoveries, "final_third_recoveries") * 0.25),
        2,
    )
    attention_spike = round(
        clamp((mention_momentum * 0.5) + (marketing.sentiment_score * 0.2) + (marketing.media_mentions * 0.15)),
        2,
    )
    return {
        "player_id": player.id,
        "athlete_name": player.name,
        "club_name": player.club_origin,
        "position": player.position,
        "current_value": float(player.current_value),
        "instagram_handle": marketing.instagram_handle,
        "google_news_query": google_news_query,
        "google_news_rss": "",
        "youtube_channel_id": "",
        "youtube_query": youtube_query,
        "tiktok_handle": marketing.tiktok_handle,
        "tiktok_query": public_name,
        "manual_context": "",
        "instagram_mentions": mention_volume,
        "instagram_momentum": mention_momentum,
        "instagram_sentiment": round(marketing.sentiment_score, 2),
        "instagram_reach": estimated_reach,
        "instagram_authority": round(marketing.engagement * 5, 2),
        "google_news_mentions": int(round(marketing.media_mentions * 0.35)),
        "google_news_momentum": round(clamp(45 + market.annual_growth), 2),
        "google_news_sentiment": round(marketing.sentiment_score, 2),
        "google_news_reach": round((estimated_reach * 0.85), 2),
        "google_news_authority": round(source_relevance, 2),
        "youtube_mentions": int(round(marketing.media_mentions * 0.2)),
        "youtube_momentum": round(clamp(40 + (market.annual_growth * 0.8)), 2),
        "youtube_sentiment": round(marketing.sentiment_score, 2),
        "youtube_reach": round((estimated_reach * 0.8), 2),
        "youtube_authority": round((source_relevance * 0.9), 2),
        "tiktok_mentions": int(round(marketing.media_mentions * 0.15)),
        "tiktok_momentum": round(clamp(42 + (market.annual_growth * 0.9)), 2),
        "tiktok_sentiment": round(marketing.sentiment_score, 2),
        "tiktok_reach": round((estimated_reach * 0.9), 2),
        "tiktok_authority": 58,
        "manual_mentions": 0,
        "manual_momentum": 0,
        "manual_sentiment": round(marketing.sentiment_score, 2),
        "manual_reach": 0,
        "manual_authority": 50,
        "manual_performance_rating": round(scores["performance_score"], 2),
        "manual_attention_spike": attention_spike,
        "manual_market_response": round(scores["marketing_score"], 2),
        "manual_visibility_efficiency": round((scores["marketing_score"] * 0.6) + (scores["market_score"] * 0.4), 2),
        "manual_note": "",
        "narrative_keywords": [
            "promissor" if scores["performance_score"] >= 65 else "em observacao",
            "decisivo" if performance.xg + performance.xa >= 0.45 else "consistente",
            "em ascensao" if market.annual_growth >= 12 else "estavel",
        ],
    }


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
    allowed_signup_email = os.environ.get("HBX_INTERNAL_ADMIN_EMAIL", "geral@hbelevensocial.com").strip().lower()
    if request.method == "POST" and form.is_valid():
        requested_email = form.cleaned_data["email"].lower()
        if requested_email != allowed_signup_email:
            messages.error(request, "Cadastro restrito ao administrador interno da plataforma.")
        elif User.objects.filter(email__iexact=requested_email).exists():
            messages.error(request, tr(lang, "email_exists"))
        else:
            user = User.objects.create(
                email=requested_email,
                password_hash=make_password(form.cleaned_data["password"]),
            )
            request.session[SESSION_KEY] = user.id
            return redirect("dashboard")
    return render(
        request,
        "valuation/signup.html",
        {
            "form": form,
            "lang": lang,
            "t": get_translations(lang),
            "languages": LANGUAGES,
            "allowed_signup_email": allowed_signup_email,
        },
    )


def logout_view(request):
    request.session.pop(SESSION_KEY, None)
    return redirect("login")


@login_required
def dashboard_view(request):
    lang = get_language(request)
    projection_period = request.GET.get("projection_period", "12")
    compare_window = request.GET.get("compare_window", "90")
    featured_player_id = request.GET.get("featured_player") or request.GET.get("athlete")
    current_user = get_current_user(request)
    players = list(
        Player.objects.filter(user=current_user).select_related(
            "performance_metrics",
            "market_metrics",
            "marketing_metrics",
            "behavior_metrics",
            "division_reference__country",
            "club_reference",
        ).prefetch_related("history", "development_plans", "progress_tracking")
    )
    for player in players:
        sync_integrated_player_modules(player)
        Athlete360Orchestrator.sync(player, source=DataSourceLog.SourceType.GENERATED_BY_HBX)
    comparison_form = ComparisonForm(request.GET or None, players=players)
    selected_ids = []
    if comparison_form.is_valid():
        selected_ids = [int(player_id) for player_id in comparison_form.cleaned_data["compare"]]
    selected_players = [player for player in players if player.id in selected_ids] or players[:3]
    featured_player = None
    if featured_player_id:
        try:
            featured_id = int(featured_player_id)
            featured_player = next((player for player in players if player.id == featured_id), None)
        except (TypeError, ValueError):
            featured_player = None
    if featured_player is None:
        featured_player = selected_players[0] if selected_players else (players[0] if players else None)
    uplift_form = UpliftSimulationForm(request.POST or None, lang=lang, player=featured_player) if featured_player else None
    uplift_result = None
    if request.method == "POST" and request.POST.get("form_name") == "uplift" and featured_player and uplift_form.is_valid():
        uplift_result = simulate_uplift(featured_player, uplift_form.cleaned_data, lang)

    players_payload = build_dashboard_payload(players, lang)
    ai_dashboard_insight = (
        get_cached_ai_dashboard_insight(featured_player, lang, int(compare_window), scope="dashboard")
        if featured_player else None
    )

    context = {
        "current_user": current_user,
        "players": players,
        "players_payload": players_payload,
        "dashboard_executive_payload": build_dashboard_executive_payload(featured_player, lang, int(compare_window)) if featured_player else None,
        "comparison_form": comparison_form,
        "featured_player": featured_player,
        "selected_players": selected_players,
        "radar_chart": radar_chart_data(featured_player, lang) if featured_player else None,
        "growth_chart": growth_chart_data(featured_player, lang) if featured_player else None,
        "comparison_chart": comparison_chart_data(selected_players, lang) if selected_players else None,
        "percentile_chart": percentile_chart_data(players[:8], lang) if players else None,
        "evolution_chart": evolution_chart_data(featured_player, lang, projection_period) if featured_player else None,
        "pillar_trend_chart": pillar_trend_chart_data(featured_player, lang) if featured_player else None,
        "score_composition_chart": score_composition_chart_data(featured_player, lang) if featured_player else None,
        "longitudinal_bi": longitudinal_bi_payload(featured_player, lang, int(compare_window)) if featured_player else None,
        "longitudinal_delta_chart": longitudinal_delta_chart_data(featured_player, lang, int(compare_window)) if featured_player else None,
        "player_timeline": player_timeline_events(featured_player, int(compare_window)) if featured_player else [],
        "growth_insights": build_growth_insights(featured_player, lang, projection_period) if featured_player else None,
        "ai_dashboard_insight": ai_dashboard_insight,
        "projection_period": projection_period,
        "projection_periods": ["3", "6", "12", "24"],
        "compare_window": compare_window,
        "compare_windows": ["30", "60", "90", "180"],
        "uplift_form": uplift_form,
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
    context.update(build_global_player_context(request, current_user, featured_player))
    return render(request, "valuation/dashboard.html", context)


@login_required
@require_http_methods(["POST"])
def player_ai_insight_view(request, player_id):
    lang = get_language(request)
    current_user = get_current_user(request)
    player = get_object_or_404(Player, pk=player_id, user=current_user)
    compare_window = request.POST.get("compare_window", "90")
    try:
        window_days = int(compare_window)
    except (TypeError, ValueError):
        window_days = 90
    if window_days not in {30, 60, 90, 180}:
        window_days = 90
    scope = request.POST.get("scope", "dashboard")
    if scope not in {"dashboard", "market", "performance", "reports"}:
        scope = "dashboard"

    try:
        generate_ai_dashboard_insight(player, lang, window_days, scope=scope)
        messages.success(request, "Leitura IA gerada e integrada ao dashboard.")
    except Exception as exc:
        messages.error(request, f"Nao foi possivel gerar a leitura IA: {exc}")

    if scope == "market":
        return redirect(f"{reverse('hbx-value-score')}?player={player.id}&lang={lang}")
    if scope == "performance":
        return redirect(f"{reverse('career-case-list')}?athlete={player.id}&lang={lang}")
    if scope == "reports":
        return redirect(f"{reverse('reports')}?player={player.id}&compare_window={window_days}&lang={lang}")
    return redirect(f"{reverse('dashboard')}?lang={lang}&featured_player={player.id}&compare_window={window_days}")


@login_required
def live_analysis_view(request):
    lang = get_language(request)
    current_user = get_current_user(request)
    players = list(
        Player.objects.filter(user=current_user)
        .select_related("division_reference__country", "club_reference", "athlete360_core", "performance_aggregate")
        .order_by("name")
    )
    for player in players:
        sync_integrated_player_modules(player)
    countries = list(Country.objects.filter(is_active=True).order_by("name"))
    divisions = list(
        Division.objects.filter(is_active=True)
        .select_related("country")
        .order_by("country__name", "scope", "state", "level", "name")
    )
    clubs = list(
        Club.objects.filter(status=Club.Status.ACTIVE)
        .select_related("country", "division")
        .order_by("official_name")
    )
    reports = list(
        LivePlayerEvaluation.objects.filter(user=current_user).select_related("player")
    )
    selected_player = None
    selected_report = None
    selected_player_id = request.GET.get("player") or request.GET.get("athlete")
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
    match_analysis_payload = build_match_analysis_payload(selected_player, lang) if selected_player else None
    context = {
            "current_user": current_user,
            "players": players,
            "countries": countries,
            "division_suggestions": divisions,
            "club_suggestions": clubs,
            "player_autofill": [
                {
                    "id": player.id,
                    "name": player.name,
                    "team": _player_club_name(player),
                    "position_group": _position_group_from_label(player.position),
                    "country_code": player.division_reference.country.code if player.division_reference_id else "",
                    "division_name": _player_division_name(player),
                    "club_name": _player_club_name(player),
                }
                for player in players
            ],
            "selected_player": selected_player,
            "match_analysis_payload": match_analysis_payload,
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
        }
    context.update(build_global_player_context(request, current_user, selected_player))
    return render(
        request,
        "valuation/live_analysis.html",
        context,
    )


@login_required
def hbx_value_score_view(request):
    lang = get_language(request)
    current_user = get_current_user(request)
    players = list(
        Player.objects.filter(user=current_user)
        .select_related(
            "performance_metrics",
            "market_metrics",
            "marketing_metrics",
            "behavior_metrics",
            "hbx_value_profile",
            "athlete360_core",
            "market_aggregate",
            "marketing_aggregate",
            "division_reference__country",
            "club_reference",
        )
        .order_by("name")
    )
    selected_player = None
    selected_player_id = request.POST.get("player_id") or request.GET.get("player") or request.GET.get("athlete")
    if selected_player_id:
        selected_player = get_object_or_404(
            Player.objects.select_related(
                "performance_metrics",
                "market_metrics",
                "marketing_metrics",
                "behavior_metrics",
                "hbx_value_profile",
                "athlete360_core",
                "market_aggregate",
                "marketing_aggregate",
                "division_reference__country",
                "club_reference",
            ),
            pk=selected_player_id,
            user=current_user,
        )
    elif players:
        selected_player = players[0]

    if request.method == "POST" and selected_player:
        action = request.POST.get("action") or "save_profile"
        profile_input = {
            "instagram_handle": request.POST.get("instagram_handle"),
            "instagram_username": request.POST.get("instagram_username"),
            "instagram_name": request.POST.get("instagram_name"),
            "instagram_biography": request.POST.get("instagram_biography"),
            "instagram_website": request.POST.get("instagram_website"),
            "instagram_profile_picture_url": request.POST.get("instagram_profile_picture_url"),
            "instagram_followers_count": request.POST.get("instagram_followers_count"),
            "instagram_media_count": request.POST.get("instagram_media_count"),
            "google_news_query": request.POST.get("google_news_query"),
            "google_news_rss": request.POST.get("google_news_rss"),
            "youtube_channel_id": request.POST.get("youtube_channel_id"),
            "youtube_query": request.POST.get("youtube_query"),
            "tiktok_handle": request.POST.get("tiktok_handle"),
            "tiktok_query": request.POST.get("tiktok_query"),
            "manual_context": request.POST.get("manual_context"),
            "instagram_mentions": request.POST.get("instagram_mentions"),
            "instagram_momentum": request.POST.get("instagram_momentum"),
            "instagram_sentiment": request.POST.get("instagram_sentiment"),
            "instagram_reach": request.POST.get("instagram_reach"),
            "instagram_authority": request.POST.get("instagram_authority"),
            "google_news_mentions": request.POST.get("google_news_mentions"),
            "google_news_momentum": request.POST.get("google_news_momentum"),
            "google_news_sentiment": request.POST.get("google_news_sentiment"),
            "google_news_reach": request.POST.get("google_news_reach"),
            "google_news_authority": request.POST.get("google_news_authority"),
            "youtube_mentions": request.POST.get("youtube_mentions"),
            "youtube_momentum": request.POST.get("youtube_momentum"),
            "youtube_sentiment": request.POST.get("youtube_sentiment"),
            "youtube_reach": request.POST.get("youtube_reach"),
            "youtube_authority": request.POST.get("youtube_authority"),
            "tiktok_mentions": request.POST.get("tiktok_mentions"),
            "tiktok_momentum": request.POST.get("tiktok_momentum"),
            "tiktok_sentiment": request.POST.get("tiktok_sentiment"),
            "tiktok_reach": request.POST.get("tiktok_reach"),
            "tiktok_authority": request.POST.get("tiktok_authority"),
            "manual_mentions": request.POST.get("manual_mentions"),
            "manual_momentum": request.POST.get("manual_momentum"),
            "manual_sentiment": request.POST.get("manual_sentiment"),
            "manual_reach": request.POST.get("manual_reach"),
            "manual_authority": request.POST.get("manual_authority"),
            "manual_performance_rating": request.POST.get("manual_performance_rating"),
            "manual_attention_spike": request.POST.get("manual_attention_spike"),
            "manual_market_response": request.POST.get("manual_market_response"),
            "manual_visibility_efficiency": request.POST.get("manual_visibility_efficiency"),
            "manual_note": request.POST.get("manual_note"),
            "narrative_keywords": [item.strip() for item in request.POST.get("narrative_keywords", "").split(",") if item.strip()],
        }
        if action == "fetch_instagram":
            handle = profile_input["instagram_handle"]
            try:
                instagram = fetch_instagram_signals(handle)
            except Exception:
                messages.error(request, "Nao foi possivel consultar o Instagram agora. A busca oficial depende da Meta Graph API e de uma conta profissional acessivel.")
                return redirect(f"{reverse('hbx-value-score')}?player={selected_player.id}&lang={lang}")
            profile_input.update(
                {
                    "instagram_handle": instagram["handle"],
                    "instagram_username": instagram["username"],
                    "instagram_name": instagram["name"],
                    "instagram_biography": instagram["biography"],
                    "instagram_website": instagram["website"],
                    "instagram_profile_picture_url": instagram["profile_picture_url"],
                    "instagram_followers_count": instagram["followers_count"],
                    "instagram_media_count": instagram["media_count"],
                    "instagram_mentions": instagram["mentions"],
                    "instagram_momentum": instagram["momentum"],
                    "instagram_sentiment": instagram["sentiment"],
                    "instagram_reach": instagram["reach"],
                    "instagram_authority": instagram["authority"],
                }
            )
            save_hbx_value_profile(selected_player, profile_input, source="ai")
            messages.success(request, "Instagram coletado e integrado ao perfil do atleta.")
        elif action == "fetch_google_news":
            query = profile_input["google_news_query"] or selected_player.name
            try:
                google_news = fetch_google_news_signals(query, profile_input["google_news_rss"])
            except Exception:
                messages.error(request, "Nao foi possivel consultar o Google News RSS agora.")
                return redirect(f"{reverse('hbx-value-score')}?player={selected_player.id}&lang={lang}")
            profile_input.update(
                {
                    "google_news_query": google_news["query"],
                    "google_news_rss": google_news["rss_url"],
                    "google_news_mentions": google_news["mentions"],
                    "google_news_momentum": google_news["momentum"],
                    "google_news_sentiment": google_news["sentiment"],
                    "google_news_reach": google_news["reach"],
                    "google_news_authority": google_news["authority"],
                    "google_news_articles": google_news["articles"],
                }
            )
            save_hbx_value_profile(selected_player, profile_input, source="ai")
            messages.success(request, "Google News RSS coletado e integrado ao perfil do atleta.")
        elif action == "fetch_youtube":
            query = profile_input["youtube_query"] or selected_player.name
            try:
                youtube = fetch_youtube_signals(query, profile_input["youtube_channel_id"])
            except Exception:
                messages.error(request, "Nao foi possivel consultar o YouTube Data API agora. Verifique a YOUTUBE_API_KEY.")
                return redirect(f"{reverse('hbx-value-score')}?player={selected_player.id}&lang={lang}")
            profile_input.update(
                {
                    "youtube_query": youtube["query"],
                    "youtube_channel_id": youtube["channel_id"],
                    "youtube_mentions": youtube["mentions"],
                    "youtube_momentum": youtube["momentum"],
                    "youtube_sentiment": youtube["sentiment"],
                    "youtube_reach": youtube["reach"],
                    "youtube_authority": youtube["authority"],
                    "youtube_videos": youtube["videos"],
                }
            )
            save_hbx_value_profile(selected_player, profile_input, source="ai")
            messages.success(request, "YouTube Data API coletado e integrado ao perfil do atleta.")
        elif action == "fetch_tiktok":
            query = profile_input["tiktok_query"] or selected_player.name
            try:
                tiktok = fetch_tiktok_signals(query, profile_input["tiktok_handle"])
            except Exception:
                messages.error(request, "Nao foi possivel consultar o TikTok agora. Verifique o acesso oficial da Research API.")
                return redirect(f"{reverse('hbx-value-score')}?player={selected_player.id}&lang={lang}")
            profile_input.update(
                {
                    "tiktok_query": tiktok["query"],
                    "tiktok_handle": tiktok["handle"],
                    "tiktok_mentions": tiktok["mentions"],
                    "tiktok_momentum": tiktok["momentum"],
                    "tiktok_sentiment": tiktok["sentiment"],
                    "tiktok_reach": tiktok["reach"],
                    "tiktok_authority": tiktok["authority"],
                    "tiktok_videos": tiktok["videos"],
                }
            )
            save_hbx_value_profile(selected_player, profile_input, source="ai")
            messages.success(request, "TikTok integrado ao perfil do atleta.")
        else:
            save_hbx_value_profile(selected_player, profile_input, source=request.POST.get("source", "manual"))
            messages.success(request, "HBX Value integrado ao perfil do atleta.")
        return redirect(f"{reverse('hbx-value-score')}?player={selected_player.id}&lang={lang}")

    selected_hbx_profile = get_hbx_value_profile(selected_player) if selected_player else None
    market_intelligence_payload = build_market_intelligence_payload(selected_player, lang) if selected_player else None
    ai_dashboard_insight = (
        get_cached_ai_dashboard_insight(selected_player, lang, 90, scope="market")
        if selected_player else None
    )
    if selected_player and selected_hbx_profile:
        selected_seed = build_hbx_seed_from_profile(selected_player, selected_hbx_profile)
    else:
        selected_seed = _build_hbx_value_score_seed(selected_player) if selected_player else None

    player_seed_map = {
        str(player.id): (
            build_hbx_seed_from_profile(player, player.hbx_value_profile)
            if get_hbx_value_profile(player) else _build_hbx_value_score_seed(player)
        )
        for player in players
    }
    selected_metrics = compute_hbx_value_profile(selected_seed) if selected_seed else None
    context = {
            "current_user": current_user,
            "players": players,
            "selected_player": selected_player,
            "selected_hbx_profile": selected_hbx_profile,
            "market_intelligence_payload": market_intelligence_payload,
            "ai_dashboard_insight": ai_dashboard_insight,
            "selected_seed_json": json.dumps(selected_seed or {}, ensure_ascii=True),
            "player_seed_map_json": json.dumps(player_seed_map, ensure_ascii=True),
            "selected_metrics": selected_metrics,
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
    return render(
        request,
        "valuation/hbx_value_score.html",
        context,
    )


@login_required
def reports_view(request):
    lang = get_language(request)
    current_user = get_current_user(request)
    compare_window = request.GET.get("compare_window", "90")
    audience = request.GET.get("audience", "consultancy")
    selected_player_id = request.GET.get("player") or request.GET.get("athlete")
    players = list(
        Player.objects.filter(user=current_user)
        .select_related("performance_metrics", "market_metrics", "marketing_metrics", "behavior_metrics", "division_reference__country", "club_reference")
        .order_by("name")
    )
    cases = list(
        CareerIntelligenceCase.objects.filter(user=current_user).select_related("player").order_by("-updated_at", "athlete_name")
    )
    selected_player = None
    if selected_player_id:
        try:
            selected_player = next((player for player in players if player.id == int(selected_player_id)), None)
        except (TypeError, ValueError):
            selected_player = None
    if selected_player is None and players:
        selected_player = players[0]
    if audience not in {"athlete", "agent", "club", "consultancy"}:
        audience = "consultancy"
    reports_executive_payload = (
        build_reports_executive_payload(selected_player, lang, int(compare_window))
        if selected_player else None
    )
    context = {
        "current_user": current_user,
        "players": players,
        "cases": cases,
        "selected_player": selected_player,
        "selected_audience": audience,
        "reports_executive_payload": reports_executive_payload,
        "audience_options": [
            ("athlete", "Atleta"),
            ("agent", "Agente"),
            ("club", "Clube"),
            ("consultancy", "Consultoria"),
        ],
        "ai_dashboard_insight": get_cached_ai_dashboard_insight(selected_player, lang, int(compare_window), scope="reports") if selected_player else None,
        "compare_window": compare_window,
        "compare_windows": ["30", "60", "90", "180"],
        "longitudinal_bi": reports_executive_payload["report_context"]["longitudinal"] if reports_executive_payload else None,
        "longitudinal_delta_chart": longitudinal_delta_chart_data(selected_player, lang, int(compare_window)) if selected_player else None,
        "lang": lang,
        "t": get_translations(lang),
        "languages": LANGUAGES,
    }
    context.update(build_global_player_context(request, current_user, selected_player))
    return render(request, "valuation/reports_hub.html", context)


@login_required
def data_view(request):
    lang = get_language(request)
    current_user = get_current_user(request)
    divisions = Division.objects.filter(is_active=True).count()
    clubs = Club.objects.filter(status=Club.Status.ACTIVE).count()
    athletes = Player.objects.filter(user=current_user).count()
    data_hub_payload = build_data_hub_payload(current_user)
    context = {
        "current_user": current_user,
        "division_count": divisions,
        "club_count": clubs,
        "athlete_count": athletes,
        "data_hub_payload": data_hub_payload,
        "lang": lang,
        "t": get_translations(lang),
        "languages": LANGUAGES,
    }
    context.update(build_global_player_context(request, current_user))
    return render(request, "valuation/data_hub.html", context)


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
        sync_integrated_player_modules(player)
        payload = _apply_player_identity_to_live_payload(payload, player)
        general_info = payload["informacoes_gerais"]

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

    if player:
        sync_live_report_to_integrated_modules(player, report)

    messages.success(request, "Ficha de analise ao vivo salva.")
    redirect_query = f"?report={report.id}&lang={lang}"
    return redirect(f"{reverse('live-analysis')}{redirect_query}")


@login_required
@require_http_methods(["GET"])
def player_operations_view(request, player_id):
    lang = get_language(request)
    current_user = get_current_user(request)
    player = get_object_or_404(
        Player.objects.select_related(
            "performance_metrics",
            "market_metrics",
            "marketing_metrics",
            "behavior_metrics",
            "division_reference__country",
            "club_reference",
        ).prefetch_related("development_plans", "progress_tracking", "scenario_lab_entries"),
        pk=player_id,
        user=current_user,
    )
    sync_integrated_player_modules(player)
    Athlete360Orchestrator.sync(player, source=DataSourceLog.SourceType.GENERATED_BY_HBX)
    context = {
        "current_user": current_user,
        "player": player,
        "development_plan_form": DevelopmentPlanForm(lang=lang),
        "progress_tracking_form": ProgressTrackingForm(lang=lang),
        "snapshot_form": SnapshotSimulationForm(lang=lang, player=player),
        "scenario_lab_entries": list(player.scenario_lab_entries.all()[:8]),
        "lang": lang,
        "t": get_translations(lang),
        "languages": LANGUAGES,
    }
    context.update(build_global_player_context(request, current_user, player))
    return render(request, "valuation/player_operations.html", context)


@login_required
@require_http_methods(["POST"])
def player_snapshot_view(request, player_id):
    lang = get_language(request)
    current_user = get_current_user(request)
    player = get_object_or_404(Player, pk=player_id, user=current_user)
    form = SnapshotSimulationForm(request.POST, lang=lang, player=player)
    if form.is_valid():
        save_scenario_lab_entry(player, form.cleaned_data)
        messages.success(request, "Cenario salvo no Scenario Lab e integrado ao historico do atleta.")
    else:
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)
    return redirect(f"{reverse('player-operations', args=[player.id])}?lang={lang}")


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
    return redirect(f"{reverse('player-operations', args=[player.id])}?lang={lang}")


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
    return redirect(f"{reverse('player-operations', args=[player.id])}?lang={lang}")


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
    recent_players = list(
        Player.objects.filter(user=current_user)
        .select_related("division_reference__country", "club_reference")
        .order_by("-id")[:8]
    )
    countries = list(Country.objects.filter(is_active=True).order_by("name"))
    divisions = list(Division.objects.filter(is_active=True).select_related("country").order_by("country__name", "scope", "state", "level", "name"))
    clubs = list(Club.objects.filter(status=Club.Status.ACTIVE).select_related("country", "division").order_by("official_name"))
    if request.method == "POST" and form.is_valid():
        player = save_player_bundle(current_user, form.cleaned_data)
        messages.success(request, f"{tr(lang, 'player_saved')} Continue preenchendo o atleta na tela de edicao.")
        return redirect(f"{reverse('player-edit', args=[player.id])}?lang={lang}")
    context = {
        "form": form,
        "current_user": current_user,
        "page_title": tr(lang, "new_player"),
        "is_new_player_page": True,
        "recent_players": recent_players,
        "countries": countries,
        "division_suggestions": divisions,
        "club_suggestions": clubs,
        "lang": lang,
        "t": get_translations(lang),
        "languages": LANGUAGES,
    }
    return render(request, "valuation/player_form.html", context)


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
            "athlete360_core",
            "performance_aggregate",
            "behavioral_aggregate",
            "market_aggregate",
            "marketing_aggregate",
            "projection_aggregate",
            "opportunity_aggregate",
        ),
        pk=player_id,
        user=current_user,
    )
    Athlete360Orchestrator.sync(player, source=DataSourceLog.SourceType.GENERATED_BY_HBX)
    player.refresh_from_db()
    form = PlayerValuationForm(request.POST or None, player=player, lang=lang)
    career_form = AthleteCareerEntryForm(lang=lang)
    go_carriera_form = GoCarrieraCheckInForm(lang=lang)
    career_entries = list(player.career_entries.all())
    contracts = list(player.contracts.all())
    transfers = list(player.transfers.all())
    go_carriera_checkins = list(player.go_carriera_checkins.all()[:10])
    recent_players = list(
        Player.objects.filter(user=current_user)
        .select_related("division_reference__country", "club_reference")
        .order_by("-id")[:8]
    )
    countries = list(Country.objects.filter(is_active=True).order_by("name"))
    divisions = list(Division.objects.filter(is_active=True).select_related("country").order_by("country__name", "scope", "state", "level", "name"))
    clubs = list(Club.objects.filter(status=Club.Status.ACTIVE).select_related("country", "division").order_by("official_name"))
    if request.method == "POST" and form.is_valid():
        save_player_bundle(current_user, form.cleaned_data, player=player)
        messages.success(request, tr(lang, "player_updated"))
        return redirect("dashboard")
    context = {
        "form": form,
        "current_user": current_user,
        "page_title": f"{tr(lang, 'edit')} {player.name}",
        "is_new_player_page": False,
        "player": player,
        "career_form": career_form,
        "go_carriera_form": go_carriera_form,
        "career_entries": career_entries,
        "contracts": contracts,
        "transfers": transfers,
        "go_carriera_checkins": go_carriera_checkins,
        "behavioral_intelligence": build_behavioral_intelligence(player),
        "comparative_intelligence": build_comparative_intelligence(player, lang=lang, compare_window_days=90),
        "projection_intelligence": build_projection_intelligence(player, lang=lang, period="12"),
        "opportunity_intelligence": build_opportunity_intelligence(player, lang=lang, period="12"),
        "athlete360_overview_payload": build_athlete360_overview_payload(player, lang=lang),
        "athlete360_core": getattr(player, "athlete360_core", None),
        "team_context_current": player.team_context_snapshots.first(),
        "performance_aggregate": getattr(player, "performance_aggregate", None),
        "behavioral_aggregate": getattr(player, "behavioral_aggregate", None),
        "market_aggregate": getattr(player, "market_aggregate", None),
        "marketing_aggregate": getattr(player, "marketing_aggregate", None),
        "projection_aggregate": getattr(player, "projection_aggregate", None),
        "opportunity_aggregate": getattr(player, "opportunity_aggregate", None),
        "latest_score_snapshot": player.score_snapshots.first(),
        "latest_projection_snapshot": player.projection_snapshots.first(),
        "latest_behavior_snapshot": player.behavior_snapshots.first(),
        "latest_market_snapshot": player.market_snapshots.first(),
        "latest_marketing_snapshot": player.marketing_snapshots.first(),
        "latest_performance_snapshot": player.performance_snapshots.first(),
        "latest_athlete_snapshot": player.athlete_snapshots.first(),
        "snapshot_counts": {
            "athlete": player.athlete_snapshots.count(),
            "performance": player.performance_snapshots.count(),
            "behavior": player.behavior_snapshots.count(),
            "market": player.market_snapshots.count(),
            "marketing": player.marketing_snapshots.count(),
            "score": player.score_snapshots.count(),
            "projection": player.projection_snapshots.count(),
        },
        "recent_players": recent_players,
        "countries": countries,
        "division_suggestions": divisions,
        "club_suggestions": clubs,
        "lang": lang,
        "t": get_translations(lang),
        "languages": LANGUAGES,
    }
    return render(request, "valuation/player_form.html", context)


@login_required
@require_http_methods(["POST"])
def player_career_entry_view(request, player_id):
    lang = get_language(request)
    current_user = get_current_user(request)
    player = get_object_or_404(Player, pk=player_id, user=current_user)
    form = AthleteCareerEntryForm(request.POST, lang=lang)
    if form.is_valid():
        save_athlete_career_entry(player, form.cleaned_data)
        messages.success(request, "Historico de carreira atualizado.")
    else:
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)
    return redirect(f"{reverse('player-edit', args=[player.id])}?lang={lang}")


@login_required
@require_http_methods(["POST"])
def player_contract_view(request, player_id):
    lang = get_language(request)
    current_user = get_current_user(request)
    player = get_object_or_404(Player, pk=player_id, user=current_user)
    try:
        cleaned_data = {
            "club_name": request.POST.get("club_name", "").strip(),
            "start_date": date.fromisoformat(request.POST["start_date"]) if request.POST.get("start_date") else None,
            "end_date": date.fromisoformat(request.POST["end_date"]) if request.POST.get("end_date") else None,
            "monthly_salary": Decimal(request.POST.get("monthly_salary") or "0"),
            "release_clause": Decimal(request.POST.get("release_clause") or "0"),
            "status": request.POST.get("status", "").strip() or "active",
            "is_current": bool(request.POST.get("is_current")),
            "notes": request.POST.get("notes", "").strip(),
            "contract_months_remaining": int(request.POST["contract_months_remaining"]) if request.POST.get("contract_months_remaining") else None,
        }
        if not cleaned_data["club_name"]:
            raise ValueError("Clube do contrato e obrigatorio.")
        if cleaned_data["start_date"] and cleaned_data["end_date"] and cleaned_data["end_date"] < cleaned_data["start_date"]:
            raise ValueError("A data final do contrato nao pode ser anterior a inicial.")
        save_athlete_contract(player, cleaned_data)
        messages.success(request, "Contrato atualizado.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect(f"{reverse('player-edit', args=[player.id])}?lang={lang}")


@login_required
@require_http_methods(["POST"])
def player_transfer_view(request, player_id):
    lang = get_language(request)
    current_user = get_current_user(request)
    player = get_object_or_404(Player, pk=player_id, user=current_user)
    try:
        cleaned_data = {
            "from_club": request.POST.get("from_club", "").strip(),
            "to_club": request.POST.get("to_club", "").strip(),
            "transfer_date": date.fromisoformat(request.POST["transfer_date"]) if request.POST.get("transfer_date") else None,
            "transfer_type": request.POST.get("transfer_type", "").strip() or "permanent",
            "transfer_fee": Decimal(request.POST.get("transfer_fee") or "0"),
            "currency": request.POST.get("currency", "").strip() or "EUR",
            "notes": request.POST.get("notes", "").strip(),
        }
        if not cleaned_data["to_club"]:
            raise ValueError("Clube de destino e obrigatorio.")
        if cleaned_data["transfer_date"] is None:
            raise ValueError("Data da transferencia e obrigatoria.")
        save_athlete_transfer(player, cleaned_data)
        messages.success(request, "Transferencia registrada.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect(f"{reverse('player-edit', args=[player.id])}?lang={lang}")


@login_required
@require_http_methods(["POST"])
def player_go_carriera_checkin_view(request, player_id):
    lang = get_language(request)
    current_user = get_current_user(request)
    player = get_object_or_404(Player, pk=player_id, user=current_user)
    form = GoCarrieraCheckInForm(request.POST, lang=lang)
    if form.is_valid():
        save_go_carriera_checkin(player, form.cleaned_data)
        messages.success(request, "Check-in Go Carriera registrado.")
    else:
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)
    return redirect(f"{reverse('player-edit', args=[player.id])}?lang={lang}")


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
    context = {"form": form, "current_user": current_user, "lang": lang, "t": get_translations(lang), "languages": LANGUAGES}
    context.update(build_global_player_context(request, current_user))
    return render(request, "valuation/upload.html", context)


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
    audience = request.GET.get("audience", "consultancy")
    if audience not in {"athlete", "agent", "club", "consultancy"}:
        audience = "consultancy"
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
    response = HttpResponse(generate_pdf_report(player, lang, audience=audience), content_type="application/pdf")
    slug = player.name.lower().replace(" ", "_")
    response["Content-Disposition"] = f'attachment; filename="{slug}_{audience}_report.pdf"'
    return response
