from django import forms

from valuation.constants import (
    CAREER_SQUAD_STATUS_LABELS,
    COMPETITOR_ROLE_LABELS,
    get_localized_choice_pairs,
    get_position_choices,
    normalize_position_list,
    normalize_position_value,
)
from valuation.models import (
    CareerIntelligenceCase,
    CareerPrognosis,
    ClubCompetitiveContext,
    CoachProfile,
    CompetitorComparison,
    CompetitiveDiagnosis,
    IndividualDevelopmentPlan,
    Player,
    PositionCompetitor,
    TacticalGameModel,
)


ATHLETE_OBJECTIVE_CHOICES = [
    ("become_starter", "Tornar-se titular"),
    ("gain_minutes", "Ganhar minutos"),
    ("improve_performance", "Elevar rendimento"),
    ("earn_transfer", "Preparar transferencia"),
    ("return_post_injury", "Retomar nivel apos lesao"),
]

SELECTION_CRITERIA_CHOICES = [
    ("experience", "Experiencia"),
    ("intensity", "Intensidade"),
    ("tactical_discipline", "Disciplina tatica"),
    ("technical_quality", "Qualidade tecnica"),
    ("leadership", "Lideranca"),
    ("physical_strength", "Forca fisica"),
    ("decision_making", "Tomada de decisao"),
    ("confidence", "Confianca"),
]


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = "field-input"
            if isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs["class"] = "choice-list"
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({"class": css, "rows": 4})
            else:
                field.widget.attrs["class"] = css


def apply_placeholders(form, placeholders):
    for field_name, placeholder in placeholders.items():
        if field_name in form.fields:
            form.fields[field_name].widget.attrs["placeholder"] = placeholder


class CareerCaseForm(StyledModelForm):
    player = forms.ModelChoiceField(queryset=Player.objects.none(), required=False)
    position_primary = forms.ChoiceField(required=False)
    secondary_positions = forms.ChoiceField(required=False)
    athlete_objectives = forms.ChoiceField(required=False)

    class Meta:
        model = CareerIntelligenceCase
        fields = [
            "player",
            "athlete_name",
            "birth_date",
            "nationality",
            "position_primary",
            "secondary_positions",
            "dominant_foot",
            "height_cm",
            "weight_kg",
            "current_club",
            "category",
            "contract_months_remaining",
            "squad_status",
            "athlete_objectives",
            "analyst_notes",
        ]
        widgets = {
            "birth_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        lang = kwargs.pop("lang", "pt")
        super().__init__(*args, **kwargs)
        self.lang = lang
        self.fields["player"].queryset = Player.objects.filter(user=user).order_by("name")
        self.fields["position_primary"].choices = [("", "---------")] + get_position_choices(lang)
        self.fields["secondary_positions"].choices = [("", "---------")] + get_position_choices(lang)
        self.fields["squad_status"].choices = [("", "---------")] + get_localized_choice_pairs(CAREER_SQUAD_STATUS_LABELS, lang)
        self.fields["athlete_objectives"].choices = [("", "---------")] + ATHLETE_OBJECTIVE_CHOICES
        self.fields["secondary_positions"].initial = (
            normalize_position_list(self.instance.secondary_positions)[0]
            if self.instance.pk and normalize_position_list(self.instance.secondary_positions)
            else ""
        )
        self.fields["position_primary"].initial = normalize_position_value(self.instance.position_primary) if self.instance.pk else ""
        self.fields["position_primary"].label = "Posicao primaria"
        self.fields["secondary_positions"].label = "Posicao secundaria"
        self.fields["athlete_objectives"].initial = (
            self.instance.athlete_objectives[0]
            if self.instance.pk and self.instance.athlete_objectives
            else ""
        )
        self.fields["athlete_objectives"].label = "Objetivo do atleta"
        apply_placeholders(
            self,
            {
                "athlete_name": "Ex.: Joao Silva",
                "nationality": "Ex.: Brasil",
                "current_club": "Ex.: Flamengo",
                "contract_months_remaining": "Ex.: 18",
                "analyst_notes": "Ex.: Atleta em crescimento, com boa resposta competitiva e necessidade de mais minutos.",
            },
        )

    def clean_athlete_name(self):
        value = (self.cleaned_data.get("athlete_name") or "").strip()
        if not value:
            raise forms.ValidationError("Nome do atleta e obrigatorio.")
        return value

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.position_primary = normalize_position_value(self.cleaned_data["position_primary"])
        secondary_position = normalize_position_value(self.cleaned_data["secondary_positions"])
        instance.secondary_positions = [secondary_position] if secondary_position else []
        athlete_objective = self.cleaned_data["athlete_objectives"]
        instance.athlete_objectives = [athlete_objective] if athlete_objective else []
        if commit:
            instance.save()
        return instance


class ClubContextForm(StyledModelForm):
    class Meta:
        model = ClubCompetitiveContext
        exclude = ["case", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_placeholders(
            self,
            {
                "club_name": "Ex.: Palmeiras",
                "competition": "Ex.: Serie A",
                "category": "Ex.: Profissional",
                "notes": "Ex.: Equipe pressiona por resultado imediato e tem pouca tolerancia a oscilacao.",
            },
        )


class CoachProfileForm(StyledModelForm):
    selection_criteria = forms.ChoiceField(required=False)

    class Meta:
        model = CoachProfile
        exclude = ["case"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["selection_criteria"].choices = [("", "---------")] + SELECTION_CRITERIA_CHOICES
        self.fields["selection_criteria"].initial = (
            self.instance.selection_criteria[0]
            if self.instance.pk and self.instance.selection_criteria
            else ""
        )
        self.fields["selection_criteria"].label = "Criterio de selecao"
        apply_placeholders(
            self,
            {
                "coach_name": "Ex.: Abel Ferreira",
                "nationality": "Ex.: Portugal",
                "months_in_charge": "Ex.: 14",
                "academy_usage_history": "Ex.: Costuma integrar atletas da base em contextos controlados.",
                "analyst_notes": "Ex.: Cobra intensidade alta e valoriza disciplina tatica e confianca competitiva.",
            },
        )

    def save(self, commit=True):
        instance = super().save(commit=False)
        selection_criteria = self.cleaned_data["selection_criteria"]
        instance.selection_criteria = [selection_criteria] if selection_criteria else []
        if commit:
            instance.save()
        return instance


class TacticalGameModelForm(StyledModelForm):
    class Meta:
        model = TacticalGameModel
        exclude = ["case"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_placeholders(
            self,
            {
                "base_system": "Ex.: 4-3-3",
                "in_possession_system": "Ex.: 3-2-5",
                "out_of_possession_system": "Ex.: 4-4-2",
                "offensive_principles": "Ex.: Amplitude com extremos altos, ataque ao espaco e apoio por dentro.",
                "defensive_principles": "Ex.: Pressao alta apos perda e linha defensiva agressiva.",
                "physical_demands_by_position": "Ex.: Laterais com alta repeticao de ida e volta e extremos de muita profundidade.",
                "tactical_demands_by_position": "Ex.: Volante precisa sustentar coberturas e acelerar a circulacao.",
                "analyst_notes": "Ex.: Modelo favorece atletas intensos, agressivos sem bola e funcionais por dentro.",
            },
        )


class PositionCompetitorForm(StyledModelForm):
    position = forms.ChoiceField(required=False)

    class Meta:
        model = PositionCompetitor
        exclude = ["case"]

    def __init__(self, *args, **kwargs):
        lang = kwargs.pop("lang", "pt")
        super().__init__(*args, **kwargs)
        self.fields["position"].choices = [("", "---------")] + get_position_choices(lang)
        self.fields["position"].initial = normalize_position_value(self.instance.position) if self.instance.pk else ""
        self.fields["squad_role"].choices = [("", "---------")] + get_localized_choice_pairs(COMPETITOR_ROLE_LABELS, lang)
        apply_placeholders(
            self,
            {
                "name": "Ex.: Pedro Souza",
                "starts": "Ex.: 12",
                "minutes_played": "Ex.: 980",
                "hierarchy_order": "Ex.: 1",
                "strengths": "Ex.: Melhor leitura defensiva, bom jogo aereo e regularidade.",
                "weaknesses": "Ex.: Dificuldade em espaco longo e menor agressividade ofensiva.",
                "notes": "Ex.: Hoje e a principal referencia da posicao no elenco.",
            },
        )

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.position = normalize_position_value(self.cleaned_data["position"])
        if commit:
            instance.save()
        return instance


class CompetitorComparisonForm(StyledModelForm):
    class Meta:
        model = CompetitorComparison
        fields = ["competitor", "criterion", "rating", "notes"]

    def __init__(self, *args, **kwargs):
        case = kwargs.pop("case")
        super().__init__(*args, **kwargs)
        self.fields["competitor"].queryset = case.competitors.all().order_by("hierarchy_order", "name")
        apply_placeholders(self, {"notes": "Ex.: Superior fisicamente, mas similar em tomada de decisao."})


class CompetitiveDiagnosisForm(StyledModelForm):
    secondary_reasons = forms.ChoiceField(required=False)
    contextual_reasons = forms.ChoiceField(required=False)

    class Meta:
        model = CompetitiveDiagnosis
        exclude = ["case"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [("", "---------")] + CompetitiveDiagnosis.REASON_CHOICES
        self.fields["secondary_reasons"].choices = choices
        self.fields["contextual_reasons"].choices = choices
        self.fields["secondary_reasons"].initial = (
            self.instance.secondary_reasons[0]
            if self.instance.pk and self.instance.secondary_reasons
            else ""
        )
        self.fields["contextual_reasons"].initial = (
            self.instance.contextual_reasons[0]
            if self.instance.pk and self.instance.contextual_reasons
            else ""
        )
        self.fields["secondary_reasons"].label = "Motivo secundario"
        self.fields["contextual_reasons"].label = "Motivo contextual"
        apply_placeholders(
            self,
            {
                "other_reason": "Ex.: Questao contratual, adaptacao familiar ou decisao interna do clube.",
                "summary": "Ex.: O atleta ainda nao se firmou por hierarquia consolidada e exigencia tatica elevada.",
            },
        )

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("main_reason"):
            self.add_error("main_reason", "Informe ao menos um motivo principal.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        secondary_reason = self.cleaned_data["secondary_reasons"]
        contextual_reason = self.cleaned_data["contextual_reasons"]
        instance.secondary_reasons = [secondary_reason] if secondary_reason else []
        instance.contextual_reasons = [contextual_reason] if contextual_reason else []
        if commit:
            instance.save()
        return instance


class CareerPrognosisForm(StyledModelForm):
    class Meta:
        model = CareerPrognosis
        exclude = ["case"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_placeholders(
            self,
            {
                "justification": "Ex.: Tem potencial para ganhar espaco no medio prazo se elevar intensidade e consistencia sem bola.",
            },
        )

    def clean_justification(self):
        value = (self.cleaned_data.get("justification") or "").strip()
        if not value:
            raise forms.ValidationError("A justificativa do prognostico e obrigatoria.")
        return value


class IndividualDevelopmentPlanForm(StyledModelForm):
    priority_actions = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Uma acao por linha. Minimo de 3 acoes prioritarias.",
    )

    class Meta:
        model = IndividualDevelopmentPlan
        exclude = ["case"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["priority_actions"].initial = "\n".join(self.instance.priority_actions)
        apply_placeholders(
            self,
            {
                "strengths_to_keep": "Ex.: Mobilidade, agressividade para atacar profundidade e confianca no duelo.",
                "short_term_priorities": "Ex.: Ajustar tomada de decisao no terco final e sustentar intensidade sem bola.",
                "medium_term_development": "Ex.: Evoluir repertorio associativo e leitura posicional.",
                "contextual_factors": "Ex.: Concorrencia alta, pouca margem para erro e necessidade de impacto imediato.",
                "mental_strategy": "Ex.: Trabalhar resiliencia, estabilidade emocional e resposta apos erros.",
                "practical_strategy": "Ex.: Plano de treino complementar com foco em finalizacao e pressao orientada.",
                "priority_actions": "Ex.:\nAumentar intensidade defensiva sem bola\nMelhorar tomada de decisao no ultimo terco\nBuscar impacto objetivo nos minutos recebidos",
                "template_name": "Ex.: Plano titularidade 90 dias",
            },
        )

    def clean_priority_actions(self):
        raw_value = self.cleaned_data.get("priority_actions", "")
        items = [line.strip() for line in raw_value.splitlines() if line.strip()]
        if len(items) < 3:
            raise forms.ValidationError("Informe pelo menos 3 acoes prioritarias.")
        return items

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.priority_actions = self.cleaned_data["priority_actions"]
        if commit:
            instance.save()
        return instance
