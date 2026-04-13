import unicodedata


POSITION_DEFINITIONS = [
    {"order": 1, "value": "Goleiro", "labels": {"pt": "Goleiro", "es": "Portero", "en": "Goalkeeper"}, "group": "Goleiro"},
    {"order": 2, "value": "Lateral direito", "labels": {"pt": "Lateral direito", "es": "Lateral derecho", "en": "Right back"}, "group": "Lateral"},
    {"order": 3, "value": "Zagueiro central", "labels": {"pt": "Zagueiro central", "es": "Zaguero central", "en": "Center back"}, "group": "Zagueiro / defensor"},
    {"order": 4, "value": "Lateral esquerdo", "labels": {"pt": "Lateral esquerdo", "es": "Lateral izquierdo", "en": "Left back"}, "group": "Lateral"},
    {"order": 5, "value": "Volante", "labels": {"pt": "Volante", "es": "Pivote", "en": "Defensive midfielder"}, "group": "Volante / meio-campista"},
    {"order": 6, "value": "Quarto Zagueiro", "labels": {"pt": "Quarto Zagueiro", "es": "Segundo central", "en": "Second center back"}, "group": "Zagueiro / defensor"},
    {"order": 7, "value": "Extremo direito", "labels": {"pt": "Extremo direito", "es": "Extremo derecho", "en": "Right winger"}, "group": "Atacante"},
    {"order": 8, "value": "Meia direita", "labels": {"pt": "Meia direita", "es": "Interior derecho", "en": "Right midfielder"}, "group": "Meia / armador"},
    {"order": 9, "value": "Centroavante", "labels": {"pt": "Centroavante", "es": "Delantero centro", "en": "Striker"}, "group": "Atacante"},
    {"order": 10, "value": "Meia esquerda", "labels": {"pt": "Meia esquerda", "es": "Interior izquierdo", "en": "Left midfielder"}, "group": "Meia / armador"},
    {"order": 11, "value": "Extremo esquerdo", "labels": {"pt": "Extremo esquerdo", "es": "Extremo izquierdo", "en": "Left winger"}, "group": "Atacante"},
    {"order": 12, "value": "Segundo Volante", "labels": {"pt": "Segundo Volante", "es": "Mediocentro mixto", "en": "Box-to-box midfielder"}, "group": "Volante / meio-campista"},
    {"order": 13, "value": "Meia Atacante", "labels": {"pt": "Meia Atacante", "es": "Mediapunta", "en": "Attacking midfielder"}, "group": "Meia / armador"},
    {"order": 14, "value": "Segundo Atacante", "labels": {"pt": "Segundo Atacante", "es": "Segundo delantero", "en": "Second striker"}, "group": "Atacante"},
]

CAREER_SQUAD_STATUS_LABELS = {
    "starter": {"pt": "Titular", "es": "Titular", "en": "Starter"},
    "backup": {"pt": "Reserva", "es": "Suplente", "en": "Backup"},
    "rotation": {"pt": "Rotação", "es": "Rotación", "en": "Rotation"},
    "limited": {"pt": "Pouco utilizado", "es": "Poco utilizado", "en": "Limited minutes"},
    "recovering": {"pt": "Retorno de lesão", "es": "Regreso de lesión", "en": "Returning from injury"},
}

COMPETITOR_ROLE_LABELS = {
    "starter": {"pt": "Titular", "es": "Titular", "en": "Starter"},
    "backup": {"pt": "Reserva", "es": "Suplente", "en": "Backup"},
    "rotation": {"pt": "Rotação", "es": "Rotación", "en": "Rotation"},
    "prospect": {"pt": "Promessa", "es": "Proyecto", "en": "Prospect"},
}

LIVE_STARTER_STATUS_LABELS = {
    "starter": {"pt": "Titular", "es": "Titular", "en": "Starter"},
    "substitute": {"pt": "Reserva", "es": "Suplente", "en": "Substitute"},
}

CAREER_STEP_LABELS = {
    "athlete": {"pt": "1. Atleta", "es": "1. Jugador", "en": "1. Athlete"},
    "club": {"pt": "2. Clube", "es": "2. Club", "en": "2. Club"},
    "coach": {"pt": "3. Treinador", "es": "3. Entrenador", "en": "3. Coach"},
    "game_model": {"pt": "4. Modelo de jogo", "es": "4. Modelo de juego", "en": "4. Game model"},
    "competition": {"pt": "5. Concorrência", "es": "5. Competencia", "en": "5. Competition"},
    "diagnosis": {"pt": "6. Diagnóstico", "es": "6. Diagnóstico", "en": "6. Diagnosis"},
    "prognosis": {"pt": "7. Prognóstico", "es": "7. Pronóstico", "en": "7. Prognosis"},
    "development": {"pt": "8. Plano", "es": "8. Plan", "en": "8. Plan"},
    "report": {"pt": "9. Relatório", "es": "9. Informe", "en": "9. Report"},
}


POSITION_ALIASES = {
    "goleiro": "Goleiro",
    "goalkeeper": "Goleiro",
    "portero": "Goleiro",
    "lateral direito": "Lateral direito",
    "right back": "Lateral direito",
    "lateral derecho": "Lateral direito",
    "zagueiro": "Zagueiro central",
    "zagueiro central": "Zagueiro central",
    "center back": "Zagueiro central",
    "centre back": "Zagueiro central",
    "central defender": "Zagueiro central",
    "zaguero central": "Zagueiro central",
    "lateral esquerdo": "Lateral esquerdo",
    "left back": "Lateral esquerdo",
    "lateral izquierdo": "Lateral esquerdo",
    "volante": "Volante",
    "pivote": "Volante",
    "defensive midfielder": "Volante",
    "quarto zagueiro": "Quarto Zagueiro",
    "segundo central": "Quarto Zagueiro",
    "second center back": "Quarto Zagueiro",
    "second centre back": "Quarto Zagueiro",
    "extremo direito": "Extremo direito",
    "ponta direita": "Extremo direito",
    "winger right": "Extremo direito",
    "right winger": "Extremo direito",
    "extremo derecho": "Extremo direito",
    "meia direita": "Meia direita",
    "interior derecho": "Meia direita",
    "right midfielder": "Meia direita",
    "centroavante": "Centroavante",
    "atacante": "Centroavante",
    "forward": "Centroavante",
    "striker": "Centroavante",
    "delantero centro": "Centroavante",
    "meia esquerda": "Meia esquerda",
    "interior izquierdo": "Meia esquerda",
    "left midfielder": "Meia esquerda",
    "extremo esquerdo": "Extremo esquerdo",
    "ponta esquerda": "Extremo esquerdo",
    "left winger": "Extremo esquerdo",
    "extremo izquierdo": "Extremo esquerdo",
    "segundo volante": "Segundo Volante",
    "box to box midfielder": "Segundo Volante",
    "box-to-box midfielder": "Segundo Volante",
    "mediocentro mixto": "Segundo Volante",
    "meia atacante": "Meia Atacante",
    "meia": "Meia Atacante",
    "meio campista": "Meia Atacante",
    "meio-campista": "Meia Atacante",
    "attacking midfielder": "Meia Atacante",
    "mediapunta": "Meia Atacante",
    "segundo atacante": "Segundo Atacante",
    "second striker": "Segundo Atacante",
    "segundo delantero": "Segundo Atacante",
    "ponta": "Extremo direito",
}


def _normalize(value):
    text = str(value or "").strip()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return " ".join(text.lower().split())


def normalize_position_value(value):
    raw_value = str(value or "").strip()
    if not raw_value:
        return ""
    direct_match = next((item["value"] for item in POSITION_DEFINITIONS if item["value"] == raw_value), None)
    if direct_match:
        return direct_match
    normalized = _normalize(raw_value)
    if normalized in POSITION_ALIASES:
        return POSITION_ALIASES[normalized]
    for item in POSITION_DEFINITIONS:
        if normalized == _normalize(item["value"]):
            return item["value"]
        for translated_label in item["labels"].values():
            if normalized == _normalize(translated_label):
                return item["value"]
        if normalized in {f"{item['order']} { _normalize(item['value']) }", f"{item['order']} - { _normalize(item['value']) }"}:
            return item["value"]
    return raw_value


def normalize_position_list(values):
    normalized_values = []
    for value in values or []:
        normalized = normalize_position_value(value)
        if normalized and normalized not in normalized_values:
            normalized_values.append(normalized)
    return normalized_values


def get_position_label(value, lang="pt", include_order=False):
    canonical = normalize_position_value(value)
    position = next((item for item in POSITION_DEFINITIONS if item["value"] == canonical), None)
    if not position:
        return canonical
    label = position["labels"].get(lang, position["labels"]["pt"])
    return f"{position['order']}. {label}" if include_order else label


def get_position_choices(lang="pt"):
    return [(item["value"], get_position_label(item["value"], lang, include_order=True)) for item in POSITION_DEFINITIONS]


def get_position_group(value):
    canonical = normalize_position_value(value)
    position = next((item for item in POSITION_DEFINITIONS if item["value"] == canonical), None)
    return position["group"] if position else ""


def get_localized_choice_pairs(label_map, lang="pt"):
    return [(value, labels.get(lang, labels["pt"])) for value, labels in label_map.items()]


def get_localized_choice_label(label_map, value, lang="pt"):
    if not value:
        return ""
    labels = label_map.get(value)
    if not labels:
        return value
    return labels.get(lang, labels["pt"])


def get_career_step_label(step, lang="pt"):
    labels = CAREER_STEP_LABELS.get(step)
    if not labels:
        return step
    return labels.get(lang, labels["pt"])
