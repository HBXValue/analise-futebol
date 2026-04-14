import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from valuation.models import AthleteAIInsight
from valuation.services import (
    build_growth_insights,
    calculate_scores,
    get_hbx_value_profile,
    longitudinal_bi_payload,
    player_timeline_events,
)


OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
PROMPT_VERSION = "v1"
SCOPE_CONFIG = {
    "dashboard": {
        "label": "dashboard",
        "focus": "leitura executiva geral do atleta para o dashboard principal",
        "card_count": 3,
    },
    "market": {
        "label": "market intelligence",
        "focus": "narrativa, mercado, percepção pública e oportunidade de posicionamento",
        "card_count": 3,
    },
    "performance": {
        "label": "performance intelligence",
        "focus": "contexto competitivo, avanço técnico e leitura de desenvolvimento",
        "card_count": 3,
    },
    "reports": {
        "label": "reports",
        "focus": "síntese executiva pronta para apresentação e relatório",
        "card_count": 3,
    },
}


def _safe_float(value):
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0


def _strip_json_fence(text):
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def build_ai_dashboard_payload(player, lang="pt", window_days=90):
    scores = calculate_scores(player, lang)
    bi_payload = longitudinal_bi_payload(player, lang, window_days)
    growth = build_growth_insights(player, lang, "12")
    hbx_profile = get_hbx_value_profile(player)
    timeline = player_timeline_events(player, window_days)[:6]
    return {
        "athlete": {
            "name": player.name,
            "public_name": player.public_name,
            "age": player.age,
            "position": player.position,
            "club": player.club_reference.short_name if player.club_reference_id and player.club_reference.short_name else player.club_origin,
            "division": player.division_reference.short_name if player.division_reference_id and player.division_reference.short_name else player.league_level,
            "country": player.division_reference.country.name if player.division_reference_id else "",
        },
        "scores": {
            "valuation_score": scores["valuation_score"],
            "performance_score": scores["performance_score"],
            "market_score": scores["market_score"],
            "marketing_score": scores["marketing_score"],
            "behavioral_score": scores["behavioral_score"],
            "potential_score": scores["potential_score"],
            "classification": scores["classification"],
            "traffic_light": scores["traffic_light"],
            "projected_value": float(scores["projected_value"]),
        },
        "longitudinal_bi": {
            "window_days": bi_payload["window_days"],
            "status_label": bi_payload["status_label"],
            "best_pillar_label": bi_payload["best_pillar_label"],
            "worst_pillar_label": bi_payload["worst_pillar_label"],
            "value_delta_pct": bi_payload["value_delta_pct"],
            "recommended_action": bi_payload["recommended_action"],
            "delta": bi_payload["delta"],
            "alerts": bi_payload["alerts"][:4],
            "insights": bi_payload["insights"][:4],
        },
        "growth_projection": {
            "projected_growth_pct": growth["projected_growth_pct"],
            "main_driver": growth["main_driver"],
            "growth_rate": growth["growth_rate"],
        },
        "market_intelligence": {
            "enabled": bool(hbx_profile),
            "market_perception_index": _safe_float(getattr(hbx_profile, "market_perception_index", 0)),
            "trend_label": getattr(hbx_profile, "trend_label", ""),
            "narrative_label": getattr(hbx_profile, "narrative_label", ""),
            "narrative_summary": getattr(hbx_profile, "narrative_summary", ""),
            "strategic_insights": list(getattr(hbx_profile, "strategic_insights", []) or [])[:3],
        },
        "timeline": timeline,
    }


def _build_system_prompt(scope):
    focus = SCOPE_CONFIG.get(scope, SCOPE_CONFIG["dashboard"])["focus"]
    return (
        "Voce e um estrategista sênior do HBX especializado em leitura executiva de atletas de futebol. "
        "Sua funcao e transformar um payload estruturado em uma leitura clara para dashboard. "
        "Nao invente dados, nao recalcula scores e nao contradiga o payload. "
        "Escreva em portugues do Brasil, com tom executivo, objetivo e profissional. "
        f"Foque especialmente em: {focus}. "
        "Responda somente JSON valido sem markdown."
    )


def _build_user_prompt(payload, scope):
    config = SCOPE_CONFIG.get(scope, SCOPE_CONFIG["dashboard"])
    schema = {
        "status_label": "string curto",
        "executive_summary": "string",
        "main_change": "string",
        "main_risk": "string",
        "main_opportunity": "string",
        "recommended_action": "string",
        "confidence": "numero de 0 a 100",
        "dashboard_cards": [
            {
                "title": "string",
                "value": "string",
                "commentary": "string",
            }
        ],
    }
    return (
        "Analise o atleta a partir do payload abaixo e devolva apenas JSON com esta estrutura:\n"
        f"{json.dumps(schema, ensure_ascii=True)}\n\n"
        "Regras:\n"
        "- status_label deve ser uma leitura curta, como 'Evolucao consistente' ou 'Momento de atencao'.\n"
        "- executive_summary deve ter no maximo 2 frases.\n"
        f"- dashboard_cards deve ter exatamente {config['card_count']} itens.\n"
        "- Cada commentary deve ser curto e orientado a decisao.\n\n"
        f"Escopo da analise: {config['label']}.\n"
        "Payload do atleta:\n"
        f"{json.dumps(payload, ensure_ascii=True)}"
    )


def _call_openai_chat(payload, scope):
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY nao configurada.")

    model_name = os.environ.get("OPENAI_MODEL", "").strip() or "gpt-4.1-mini"
    request_body = {
        "model": model_name,
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": _build_system_prompt(scope)},
            {"role": "user", "content": _build_user_prompt(payload, scope)},
        ],
    }
    data = json.dumps(request_body).encode("utf-8")
    request = Request(
        OPENAI_API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=45) as response:
            raw_body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Falha ao consultar a OpenAI: {exc.code} {detail}") from exc
    except URLError as exc:
        raise RuntimeError("Falha de rede ao consultar a OpenAI.") from exc

    parsed = json.loads(raw_body)
    content = parsed["choices"][0]["message"]["content"]
    structured = json.loads(_strip_json_fence(content))
    return model_name, parsed, structured


def get_cached_ai_dashboard_insight(player, lang="pt", window_days=90, scope="dashboard"):
    return (
        AthleteAIInsight.objects.filter(
            player=player,
            scope=scope,
            language=lang,
            window_days=window_days,
            prompt_version=PROMPT_VERSION,
        )
        .order_by("-updated_at", "-id")
        .first()
    )


def generate_ai_dashboard_insight(player, lang="pt", window_days=90, scope="dashboard"):
    payload = build_ai_dashboard_payload(player, lang, window_days)
    model_name, raw_response, structured = _call_openai_chat(payload, scope)
    insight, _ = AthleteAIInsight.objects.update_or_create(
        player=player,
        scope=scope,
        language=lang,
        window_days=window_days,
        prompt_version=PROMPT_VERSION,
        defaults={
            "model_name": model_name,
            "status_label": str(structured.get("status_label", "")).strip(),
            "executive_summary": str(structured.get("executive_summary", "")).strip(),
            "main_change": str(structured.get("main_change", "")).strip(),
            "main_risk": str(structured.get("main_risk", "")).strip(),
            "main_opportunity": str(structured.get("main_opportunity", "")).strip(),
            "recommended_action": str(structured.get("recommended_action", "")).strip(),
            "confidence": _safe_float(structured.get("confidence", 0)),
            "dashboard_cards": list(structured.get("dashboard_cards", []) or [])[:3],
            "payload_snapshot": payload,
            "raw_response": raw_response,
        },
    )
    return insight


def refresh_ai_insights_for_player(player, lang="pt", scopes=None, window_days_list=None, fail_silently=True):
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return []

    scopes = list(scopes or [
        AthleteAIInsight.Scope.DASHBOARD,
        AthleteAIInsight.Scope.MARKET,
        AthleteAIInsight.Scope.PERFORMANCE,
        AthleteAIInsight.Scope.REPORTS,
    ])
    window_days_list = list(window_days_list or [90])

    refreshed = []
    for scope in scopes:
        for window_days in window_days_list:
            try:
                refreshed.append(
                    generate_ai_dashboard_insight(
                        player,
                        lang=lang,
                        window_days=window_days,
                        scope=scope,
                    )
                )
            except Exception:
                if not fail_silently:
                    raise
    return refreshed
