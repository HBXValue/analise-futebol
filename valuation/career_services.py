import json
import os
from urllib import error, request

from django.utils import timezone

from valuation.constants import (
    CAREER_SQUAD_STATUS_LABELS,
    get_career_step_label,
    get_localized_choice_label,
)
from valuation.models import CareerIntelligenceCase, CompetitorComparison


CAREER_STEPS = ["athlete", "club", "coach", "game_model", "competition", "diagnosis", "prognosis", "development", "report"]


class CareerPlanGenerationError(Exception):
    pass


def step_links(active_step, lang="pt"):
    return [
        {"key": key, "label": get_career_step_label(key, lang), "active": key == active_step}
        for key in CAREER_STEPS
    ]


def _has_related(instance, attr_name):
    try:
        return getattr(instance, attr_name) is not None
    except Exception:
        return False


def calculate_age(birth_date):
    if not birth_date:
        return None
    today = timezone.localdate()
    years = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


def apply_player_defaults(case):
    player = case.player
    if not player:
        return case
    if not case.athlete_name:
        case.athlete_name = player.name
    if not case.position_primary:
        case.position_primary = player.position
    if not case.current_club:
        case.current_club = player.club_origin
    if not case.nationality:
        case.nationality = "Nao informado"
    return case


def case_completion(case):
    checks = {
        "athlete": bool(case.athlete_name and case.position_primary and case.current_club),
        "club": _has_related(case, "club_context"),
        "coach": _has_related(case, "coach_profile"),
        "game_model": _has_related(case, "game_model"),
        "competition": case.competitors.exists(),
        "diagnosis": _has_related(case, "diagnosis"),
        "prognosis": _has_related(case, "prognosis") and bool(case.prognosis.justification),
        "development": _has_related(case, "development_plan_v2") and len(case.development_plan_v2.priority_actions) >= 3,
    }
    checks["report"] = all(checks.values())
    return checks


def comparison_matrix(case):
    criteria_order = [
        CompetitorComparison.Criterion.TECHNICAL,
        CompetitorComparison.Criterion.TACTICAL,
        CompetitorComparison.Criterion.PHYSICAL,
        CompetitorComparison.Criterion.MENTAL,
        CompetitorComparison.Criterion.BEHAVIORAL,
        CompetitorComparison.Criterion.MATURITY,
        CompetitorComparison.Criterion.GAME_MODEL_FIT,
        CompetitorComparison.Criterion.COACH_TRUST,
    ]
    comparisons = (
        case.comparisons.select_related("competitor")
        .order_by("competitor__hierarchy_order", "competitor__name", "criterion")
    )
    grouped = {}
    for comparison in comparisons:
        competitor_bucket = grouped.setdefault(
            comparison.competitor_id,
            {
                "competitor": comparison.competitor,
                "items": {},
            },
        )
        competitor_bucket["items"][comparison.criterion] = comparison
    rows = []
    for bucket in grouped.values():
        ordered_items = [bucket["items"].get(criterion) for criterion in criteria_order]
        rows.append({"competitor": bucket["competitor"], "items": ordered_items})
    return rows


def _json_text(value):
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if item)
    return str(value)


def build_career_case_summary(case):
    club = getattr(case, "club_context", None)
    coach = getattr(case, "coach_profile", None)
    model = getattr(case, "game_model", None)
    diagnosis = getattr(case, "diagnosis", None)
    prognosis = getattr(case, "prognosis", None)
    development = getattr(case, "development_plan_v2", None)
    competitors = list(case.competitors.all()[:5])
    comparisons = list(
        case.comparisons.select_related("competitor").order_by("competitor__hierarchy_order", "criterion")
    )

    comparison_lines = [
        f"- {item.competitor.name} | {item.get_criterion_display()}: {item.get_rating_display()} | {item.notes or '-'}"
        for item in comparisons
    ] or ["- Nenhuma comparacao registrada."]
    competitor_lines = [
        f"- {item.name} | posicao: {item.position} | papel: {item.get_squad_role_display() or '-'} | minutos: {item.minutes_played}"
        for item in competitors
    ] or ["- Nenhum concorrente registrado."]

    summary = {
        "atleta": {
            "nome": case.athlete_name,
            "idade": calculate_age(case.birth_date),
            "nacionalidade": case.nationality,
            "posicao_primaria": case.position_primary,
            "posicao_secundaria": case.secondary_positions,
            "pe_dominante": case.get_dominant_foot_display() if case.dominant_foot else "",
            "altura_cm": case.height_cm,
            "peso_kg": case.weight_kg,
            "clube_atual": case.current_club,
            "categoria": case.get_category_display() if case.category else "",
            "meses_restantes_contrato": case.contract_months_remaining,
            "status_elenco": case.get_squad_status_display() if case.squad_status else "",
            "objetivo_atleta": case.athlete_objectives,
            "notas_analista": case.analyst_notes,
        },
        "clube": {
            "nome": club.club_name if club else "",
            "competicao": club.competition if club else "",
            "categoria": club.category if club else "",
            "momento": club.get_team_moment_display() if club and club.team_moment else "",
            "pressao": club.get_pressure_level_display() if club and club.pressure_level else "",
            "filosofia": club.get_club_philosophy_display() if club and club.club_philosophy else "",
            "notas": club.notes if club else "",
        },
        "treinador": {
            "nome": coach.coach_name if coach else "",
            "idade": coach.age if coach else "",
            "nacionalidade": coach.nationality if coach else "",
            "meses_no_cargo": coach.months_in_charge if coach else "",
            "perfil": coach.get_profile_type_display() if coach and coach.profile_type else "",
            "preferencia": coach.get_experience_preference_display() if coach and coach.experience_preference else "",
            "uso_da_base": coach.academy_usage_history if coach else "",
            "demanda_fisica": coach.get_physical_demand_display() if coach and coach.physical_demand else "",
            "demanda_tatica": coach.get_tactical_demand_display() if coach and coach.tactical_demand else "",
            "criterio_de_selecao": coach.selection_criteria if coach else [],
            "notas": coach.analyst_notes if coach else "",
        },
        "modelo_de_jogo": {
            "sistema_base": model.base_system if model else "",
            "sistema_com_bola": model.in_possession_system if model else "",
            "sistema_sem_bola": model.out_of_possession_system if model else "",
            "estilo": model.get_playing_style_display() if model and model.playing_style else "",
            "principios_ofensivos": model.offensive_principles if model else "",
            "principios_defensivos": model.defensive_principles if model else "",
            "demandas_fisicas_por_posicao": model.physical_demands_by_position if model else "",
            "demandas_taticas_por_posicao": model.tactical_demands_by_position if model else "",
            "liberdade_criativa": model.get_creative_freedom_display() if model and model.creative_freedom else "",
            "notas": model.analyst_notes if model else "",
        },
        "diagnostico": {
            "motivo_principal": diagnosis.get_main_reason_display() if diagnosis else "",
            "motivo_secundario": diagnosis.secondary_reasons if diagnosis else [],
            "motivo_contextual": diagnosis.contextual_reasons if diagnosis else [],
            "outro_motivo": diagnosis.other_reason if diagnosis else "",
            "resumo": diagnosis.summary if diagnosis else "",
        },
        "prognostico": {
            "classificacao": prognosis.get_classification_display() if prognosis else "",
            "prazo": prognosis.get_timeframe_display() if prognosis else "",
            "justificativa": prognosis.justification if prognosis else "",
        },
        "plano_atual": {
            "manter": development.strengths_to_keep if development else "",
            "curto_prazo": development.short_term_priorities if development else "",
            "medio_prazo": development.medium_term_development if development else "",
            "fatores_contextuais": development.contextual_factors if development else "",
            "estrategia_mental": development.mental_strategy if development else "",
            "estrategia_pratica": development.practical_strategy if development else "",
            "acoes": development.priority_actions if development else [],
            "template": development.template_name if development else "",
        },
        "concorrentes": competitor_lines,
        "comparacoes": comparison_lines,
    }
    return json.dumps(summary, ensure_ascii=False, indent=2, default=_json_text)


def _sanitize_ai_plan(payload):
    priority_actions = payload.get("priority_actions") or []
    if isinstance(priority_actions, str):
        priority_actions = [line.strip() for line in priority_actions.splitlines() if line.strip()]
    if len(priority_actions) < 3:
        raise CareerPlanGenerationError("A IA nao retornou ao menos 3 acoes prioritarias.")
    return {
        "strengths_to_keep": str(payload.get("strengths_to_keep", "")).strip(),
        "short_term_priorities": str(payload.get("short_term_priorities", "")).strip(),
        "medium_term_development": str(payload.get("medium_term_development", "")).strip(),
        "contextual_factors": str(payload.get("contextual_factors", "")).strip(),
        "mental_strategy": str(payload.get("mental_strategy", "")).strip(),
        "practical_strategy": str(payload.get("practical_strategy", "")).strip(),
        "priority_actions": [str(item).strip() for item in priority_actions if str(item).strip()][:6],
        "template_name": str(payload.get("template_name", "")).strip() or "Sugestao IA",
    }


def generate_ai_development_plan(case):
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise CareerPlanGenerationError("OPENAI_API_KEY nao configurada para gerar sugestao por IA.")

    model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"
    prompt = build_career_case_summary(case)
    payload = {
        "model": model,
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "Voce e um especialista em desenvolvimento de carreira no futebol. "
                    "Responda apenas em JSON valido, em portugues, com as chaves: "
                    "strengths_to_keep, short_term_priorities, medium_term_development, "
                    "contextual_factors, mental_strategy, practical_strategy, priority_actions, template_name. "
                    "priority_actions deve ser uma lista com pelo menos 3 acoes objetivas."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Com base no caso abaixo, gere um plano de desenvolvimento pratico, objetivo e coerente com o contexto.\n\n"
                    f"{prompt}"
                ),
            },
        ],
    }
    req = request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise CareerPlanGenerationError(f"Falha ao gerar sugestao por IA: {detail or exc.reason}") from exc
    except error.URLError as exc:
        raise CareerPlanGenerationError(f"Falha de conexao com a IA: {exc.reason}") from exc
    except Exception as exc:
        raise CareerPlanGenerationError(f"Erro inesperado ao gerar sugestao por IA: {exc}") from exc

    try:
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except Exception as exc:
        raise CareerPlanGenerationError("A resposta da IA veio em formato invalido.") from exc
    return _sanitize_ai_plan(parsed)


def report_lines(case, lang="pt"):
    completion = case_completion(case)
    diagnosis = getattr(case, "diagnosis", None)
    prognosis = getattr(case, "prognosis", None)
    development = getattr(case, "development_plan_v2", None)
    club = getattr(case, "club_context", None)
    coach = getattr(case, "coach_profile", None)
    model = getattr(case, "game_model", None)

    lines = [
        "HBX - Inteligencia de Carreira e Competicao",
        f"Atleta: {case.athlete_name}",
        f"Posicao principal: {case.position_primary}",
        f"Idade: {calculate_age(case.birth_date) or '-'}",
        f"Clube atual: {case.current_club or '-'}",
        f"Status no elenco: {get_localized_choice_label(CAREER_SQUAD_STATUS_LABELS, case.squad_status, lang) if case.squad_status else '-'}",
        "",
        "Contexto competitivo",
        f"Competicao: {club.competition if club else '-'}",
        f"Momento da equipe: {club.get_team_moment_display() if club and club.team_moment else '-'}",
        f"Pressao por resultado: {club.get_pressure_level_display() if club and club.pressure_level else '-'}",
        "",
        "Treinador",
        f"Nome: {coach.coach_name if coach else '-'}",
        f"Perfil: {coach.get_profile_type_display() if coach and coach.profile_type else '-'}",
        f"Preferencia: {coach.get_experience_preference_display() if coach and coach.experience_preference else '-'}",
        "",
        "Modelo de jogo",
        f"Sistema base: {model.base_system if model else '-'}",
        f"Estilo: {model.get_playing_style_display() if model and model.playing_style else '-'}",
        "",
        "Diagnostico",
        f"Motivo principal: {diagnosis.get_main_reason_display() if diagnosis else '-'}",
        f"Resumo: {diagnosis.summary if diagnosis else '-'}",
        "",
        "Prognostico",
        f"Classificacao: {prognosis.get_classification_display() if prognosis else '-'}",
        f"Prazo: {prognosis.get_timeframe_display() if prognosis else '-'}",
        f"Justificativa: {prognosis.justification if prognosis else '-'}",
        "",
        "Plano de desenvolvimento",
        f"Acoes prioritarias: {', '.join(development.priority_actions) if development else '-'}",
        f"Pronto para relatorio final: {'Sim' if completion['report'] else 'Nao'}",
    ]
    return lines


def generate_career_report_pdf(case, lang="pt"):
    lines = report_lines(case, lang)
    stream_commands = ["BT", "/F1 12 Tf", "40 800 Td"]
    for index, line in enumerate(lines):
        if index:
            stream_commands.append("0 -18 Td")
        safe_line = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream_commands.append(f"({safe_line}) Tj")
    stream_commands.append("ET")
    page_stream = "\n".join(stream_commands).encode("latin-1", errors="ignore")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n",
        f"4 0 obj << /Length {len(page_stream)} >> stream\n".encode("latin-1") + page_stream + b"\nendstream endobj\n",
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)
    xref_position = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode("latin-1"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_position}\n%%EOF".encode("latin-1"))
    return bytes(pdf)
