from datetime import date

from django import forms

from catalog.models import Country
from valuation.constants import (
    LIVE_STARTER_STATUS_LABELS,
    get_localized_choice_pairs,
    get_position_choices,
    normalize_position_list,
    normalize_position_value,
)
from valuation.i18n import tr
from valuation.models import Player


class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput())

    def __init__(self, *args, **kwargs):
        lang = kwargs.pop("lang", "pt")
        self.lang = lang
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "field-input"
        self.fields["email"].label = tr(lang, "email")
        self.fields["password"].label = tr(lang, "password")


class SignUpForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(min_length=8, widget=forms.PasswordInput())
    confirm_password = forms.CharField(min_length=8, widget=forms.PasswordInput())

    def __init__(self, *args, **kwargs):
        lang = kwargs.pop("lang", "pt")
        self.lang = lang
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "field-input"
        self.fields["email"].label = tr(lang, "email")
        self.fields["password"].label = tr(lang, "password")
        self.fields["confirm_password"].label = tr(lang, "confirm_password")

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("password") != cleaned_data.get("confirm_password"):
            raise forms.ValidationError(tr(getattr(self, "lang", "pt"), "passwords_do_not_match"))
        return cleaned_data


class PlayerValuationForm(forms.Form):
    country_code = forms.ChoiceField(required=False)
    name = forms.CharField(max_length=160)
    public_name = forms.CharField(max_length=160, required=False)
    age = forms.IntegerField(min_value=14, max_value=45, required=False)
    birth_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    nationality = forms.CharField(max_length=80, required=False)
    position = forms.ChoiceField()
    secondary_positions = forms.ChoiceField(required=False)
    dominant_foot = forms.ChoiceField(required=False)
    height_cm = forms.IntegerField(min_value=120, max_value=240, required=False)
    weight_kg = forms.IntegerField(min_value=35, max_value=180, required=False)
    current_value = forms.DecimalField(min_value=0, decimal_places=2, max_digits=14)
    league_level = forms.CharField(max_length=80)
    club_origin = forms.CharField(max_length=160)
    category = forms.ChoiceField(required=False)
    contract_months_remaining = forms.IntegerField(min_value=0, required=False)
    squad_status = forms.ChoiceField(required=False)
    athlete_objectives = forms.ChoiceField(required=False)
    training_environment_score = forms.FloatField(min_value=0, max_value=100, required=False)
    trajectory_score = forms.FloatField(min_value=0, max_value=100, required=False)
    profile_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))

    xg = forms.FloatField(min_value=0, required=False, initial=0)
    xa = forms.FloatField(min_value=0, required=False, initial=0)
    passes_pct = forms.FloatField(min_value=0, max_value=100, required=False, initial=0)
    dribbles_pct = forms.FloatField(min_value=0, max_value=100, required=False, initial=0)
    tackles_pct = forms.FloatField(min_value=0, max_value=100, required=False, initial=0)
    high_intensity_distance = forms.FloatField(min_value=0, required=False, initial=0)
    final_third_recoveries = forms.FloatField(min_value=0, required=False, initial=0)

    annual_growth = forms.FloatField(required=False, initial=0)
    club_interest = forms.FloatField(min_value=0, max_value=100, required=False, initial=0)
    league_score = forms.FloatField(min_value=0, max_value=100, required=False, initial=0)
    age_factor = forms.FloatField(min_value=0, max_value=100, required=False, initial=0)
    club_reputation = forms.FloatField(min_value=0, max_value=100, required=False, initial=0)

    instagram_handle = forms.CharField(max_length=120, required=False)
    instagram_followers = forms.FloatField(min_value=0, required=False, initial=0)
    instagram_engagement = forms.FloatField(min_value=0, required=False, initial=0)
    instagram_posts = forms.FloatField(min_value=0, required=False, initial=0)
    tiktok_handle = forms.CharField(max_length=120, required=False)
    tiktok_followers = forms.FloatField(min_value=0, required=False, initial=0)
    tiktok_engagement = forms.FloatField(min_value=0, required=False, initial=0)
    tiktok_posts = forms.FloatField(min_value=0, required=False, initial=0)
    x_handle = forms.CharField(max_length=120, required=False)
    x_followers = forms.FloatField(min_value=0, required=False, initial=0)
    x_engagement = forms.FloatField(min_value=0, required=False, initial=0)
    google_news_query = forms.CharField(max_length=160, required=False)
    youtube_query = forms.CharField(max_length=160, required=False)
    youtube_subscribers = forms.FloatField(min_value=0, required=False, initial=0)
    youtube_avg_views = forms.FloatField(min_value=0, required=False, initial=0)
    youtube_videos = forms.FloatField(min_value=0, required=False, initial=0)
    collection_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    followers = forms.FloatField(min_value=0, required=False, initial=0)
    engagement = forms.FloatField(min_value=0, required=False, initial=0)
    media_mentions = forms.FloatField(min_value=0, required=False, initial=0)
    sponsorships = forms.FloatField(min_value=0, required=False, initial=0)
    sentiment_score = forms.FloatField(min_value=0, max_value=100, required=False, initial=0)

    conscientiousness = forms.FloatField(min_value=0, max_value=100, required=False, initial=0)
    adaptability = forms.FloatField(min_value=0, max_value=100, required=False, initial=0)
    resilience = forms.FloatField(min_value=0, max_value=100, required=False, initial=0)
    deliberate_practice = forms.FloatField(min_value=0, max_value=100, required=False, initial=0)
    executive_function = forms.FloatField(min_value=0, max_value=100, required=False, initial=0)
    leadership = forms.FloatField(min_value=0, max_value=100, required=False, initial=0)

    def __init__(self, *args, **kwargs):
        lang = kwargs.pop("lang", "pt")
        self.lang = lang
        player = kwargs.pop("player", None)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "field-input"

        translated_labels = {
            "name": "name",
            "age": "age",
            "position": "position",
            "current_value": "current_value",
            "league_level": "league_level",
            "club_origin": "club_origin",
            "annual_growth": "annual_growth",
            "club_interest": "club_interest",
            "league_score": "league_score",
            "age_factor": "age_factor",
            "club_reputation": "club_reputation",
            "followers": "followers",
            "engagement": "engagement",
            "media_mentions": "media_mentions",
            "sponsorships": "sponsorships",
            "sentiment_score": "sentiment_score",
            "conscientiousness": "conscientiousness",
            "adaptability": "adaptability",
            "resilience": "resilience",
            "deliberate_practice": "deliberate_practice",
            "executive_function": "executive_function",
            "leadership": "leadership",
            "high_intensity_distance": "high_intensity_distance",
            "final_third_recoveries": "final_third_recoveries",
        }
        for field_name, key in translated_labels.items():
            self.fields[field_name].label = tr(lang, key)

        custom_labels = {
            "country_code": "Pais",
            "public_name": "Nome publico",
            "birth_date": "Data de nascimento",
            "nationality": "Nacionalidade",
            "secondary_positions": "Posicao secundaria",
            "dominant_foot": "Pe dominante",
            "height_cm": "Altura (cm)",
            "weight_kg": "Peso (kg)",
            "category": "Categoria",
            "contract_months_remaining": "Meses restantes de contrato",
            "squad_status": "Status no elenco",
            "athlete_objectives": "Objetivo do atleta",
            "training_environment_score": "Ambiente de desenvolvimento",
            "trajectory_score": "Trajetoria e tendencia",
            "profile_notes": "Observacoes do analista",
            "instagram_handle": "Instagram do atleta",
            "instagram_followers": "Seguidores no Instagram",
            "instagram_engagement": "Engajamento no Instagram (%)",
            "instagram_posts": "Posts observados no Instagram",
            "tiktok_handle": "TikTok do atleta",
            "tiktok_followers": "Seguidores no TikTok",
            "tiktok_engagement": "Engajamento no TikTok (%)",
            "tiktok_posts": "Videos observados no TikTok",
            "x_handle": "X / Twitter do atleta",
            "x_followers": "Seguidores no X / Twitter",
            "x_engagement": "Engajamento no X / Twitter (%)",
            "google_news_query": "Nome para busca no Google News",
            "youtube_query": "Nome para busca no YouTube",
            "youtube_subscribers": "Inscritos no YouTube",
            "youtube_avg_views": "Media de views no YouTube",
            "youtube_videos": "Videos observados no YouTube",
            "collection_notes": "Notas da coleta publica",
        }
        for field_name, label in custom_labels.items():
            self.fields[field_name].label = label

        self.fields["position"].choices = get_position_choices(lang)
        self.fields["country_code"].choices = [
            ("", "---------"),
            *[(country.code, country.name) for country in Country.objects.filter(is_active=True).order_by("name")],
        ]
        self.fields["secondary_positions"].choices = [("", "---------")] + get_position_choices(lang)
        self.fields["dominant_foot"].choices = [("", "---------")] + list(Player.DominantFoot.choices)
        self.fields["category"].choices = [("", "---------")] + list(Player.Category.choices)
        self.fields["squad_status"].choices = [("", "---------")] + list(Player.SquadStatus.choices)
        self.fields["athlete_objectives"].choices = [
            ("", "---------"),
            ("become_starter", "Tornar-se titular"),
            ("gain_minutes", "Ganhar minutos"),
            ("improve_performance", "Elevar rendimento"),
            ("earn_transfer", "Preparar transferencia"),
            ("return_post_injury", "Retomar nivel apos lesao"),
        ]
        self.fields["league_level"].widget.attrs["list"] = "division-suggestions"
        self.fields["club_origin"].widget.attrs["list"] = "club-suggestions"
        self.fields["league_level"].help_text = "Use uma divisao existente ou digite uma nova nomenclatura."
        self.fields["club_origin"].help_text = "Use um clube existente ou digite um novo nome para cadastrar."

        placeholders = {
            "country_code": "",
            "name": "Ex.: Joao Silva",
            "public_name": "Ex.: Joao Silva ou Joao S.",
            "age": "Calculada automaticamente",
            "nationality": "Ex.: Brasil",
            "height_cm": "Ex.: 182",
            "weight_kg": "Ex.: 76",
            "current_value": "Ex.: 3500000",
            "league_level": "Ex.: Serie B",
            "club_origin": "Ex.: Sport Recife",
            "contract_months_remaining": "Ex.: 18",
            "training_environment_score": "Ex.: 82",
            "trajectory_score": "Ex.: 76",
            "profile_notes": "Ex.: Atleta em crescimento, com boa resposta competitiva e necessidade de mais minutos.",
            "xg": "Ex.: 0.34",
            "xa": "Ex.: 0.18",
            "passes_pct": "Ex.: 84",
            "dribbles_pct": "Ex.: 61",
            "tackles_pct": "Ex.: 58",
            "high_intensity_distance": "Ex.: 980",
            "final_third_recoveries": "Ex.: 5",
            "annual_growth": "Ex.: 12.5",
            "club_interest": "Ex.: 72",
            "league_score": "Ex.: 68",
            "age_factor": "Ex.: 81",
            "club_reputation": "Ex.: 74",
            "instagram_handle": "Ex.: @joaosilva",
            "instagram_followers": "Ex.: 125000",
            "instagram_engagement": "Ex.: 6.2",
            "instagram_posts": "Ex.: 48",
            "tiktok_handle": "Ex.: @joaosilva",
            "tiktok_followers": "Ex.: 98000",
            "tiktok_engagement": "Ex.: 8.4",
            "tiktok_posts": "Ex.: 22",
            "x_handle": "Ex.: @joaosilva",
            "x_followers": "Ex.: 18000",
            "x_engagement": "Ex.: 2.8",
            "google_news_query": "Ex.: Joao Silva Sport Recife",
            "youtube_query": "Ex.: Joao Silva highlights",
            "youtube_subscribers": "Ex.: 15000",
            "youtube_avg_views": "Ex.: 22000",
            "youtube_videos": "Ex.: 14",
            "collection_notes": "Ex.: dados publicos coletados manualmente ou por API conforme disponibilidade.",
            "followers": "Ex.: 256000",
            "engagement": "Ex.: 5.7",
            "media_mentions": "Ex.: 18",
            "sponsorships": "Ex.: 3",
            "sentiment_score": "Ex.: 78",
        }
        for field_name, placeholder in placeholders.items():
            self.fields[field_name].widget.attrs["placeholder"] = placeholder
        self.fields["country_code"].widget.attrs["data-role"] = "country-select"
        self.fields["age"].widget.attrs["readonly"] = "readonly"
        self.fields["age"].help_text = "A idade e calculada automaticamente a partir da data de nascimento."
        self.fields["birth_date"].help_text = "Informe a data de nascimento para calcular a idade atual do atleta."
        self.fields["training_environment_score"].help_text = "Escala de 0 a 100. Reflita a qualidade do contexto de treino, staff, estrutura e nivel competitivo."
        self.fields["trajectory_score"].help_text = "Escala de 0 a 100. Reflita a tendencia recente do atleta, curva de evolucao e consistencia do caminho."

        if player:
            secondary_positions = normalize_position_list(player.secondary_positions)
            self.initial.update(
                {
                    "country_code": player.division_reference.country.code if player.division_reference_id else "BRA",
                    "name": player.name,
                    "public_name": player.public_name,
                    "age": player.age,
                    "birth_date": player.birth_date,
                    "nationality": player.nationality,
                    "position": normalize_position_value(player.position),
                    "secondary_positions": secondary_positions[0] if secondary_positions else "",
                    "dominant_foot": player.dominant_foot,
                    "height_cm": player.height_cm,
                    "weight_kg": player.weight_kg,
                    "current_value": player.current_value,
                    "league_level": player.league_level,
                    "club_origin": player.club_origin,
                    "category": player.category,
                    "contract_months_remaining": player.contract_months_remaining,
                    "squad_status": player.squad_status,
                    "athlete_objectives": player.athlete_objectives[0] if player.athlete_objectives else "",
                    "training_environment_score": player.training_environment_score,
                    "trajectory_score": player.trajectory_score,
                    "profile_notes": player.profile_notes,
                    "xg": player.performance_metrics.xg,
                    "xa": player.performance_metrics.xa,
                    "passes_pct": player.performance_metrics.passes_pct,
                    "dribbles_pct": player.performance_metrics.dribbles_pct,
                    "tackles_pct": player.performance_metrics.tackles_pct,
                    "high_intensity_distance": player.performance_metrics.high_intensity_distance,
                    "final_third_recoveries": player.performance_metrics.final_third_recoveries,
                    "annual_growth": player.market_metrics.annual_growth,
                    "club_interest": player.market_metrics.club_interest,
                    "league_score": player.market_metrics.league_score,
                    "age_factor": player.market_metrics.age_factor,
                    "club_reputation": player.market_metrics.club_reputation,
                    "instagram_handle": player.marketing_metrics.instagram_handle,
                    "instagram_followers": player.marketing_metrics.instagram_followers,
                    "instagram_engagement": player.marketing_metrics.instagram_engagement,
                    "instagram_posts": player.marketing_metrics.instagram_posts,
                    "tiktok_handle": player.marketing_metrics.tiktok_handle,
                    "tiktok_followers": player.marketing_metrics.tiktok_followers,
                    "tiktok_engagement": player.marketing_metrics.tiktok_engagement,
                    "tiktok_posts": player.marketing_metrics.tiktok_posts,
                    "x_handle": player.marketing_metrics.x_handle,
                    "x_followers": player.marketing_metrics.x_followers,
                    "x_engagement": player.marketing_metrics.x_engagement,
                    "google_news_query": player.marketing_metrics.google_news_query,
                    "youtube_query": player.marketing_metrics.youtube_query,
                    "youtube_subscribers": player.marketing_metrics.youtube_subscribers,
                    "youtube_avg_views": player.marketing_metrics.youtube_avg_views,
                    "youtube_videos": player.marketing_metrics.youtube_videos,
                    "collection_notes": player.marketing_metrics.collection_notes,
                    "followers": player.marketing_metrics.followers,
                    "engagement": player.marketing_metrics.engagement,
                    "media_mentions": player.marketing_metrics.media_mentions,
                    "sponsorships": player.marketing_metrics.sponsorships,
                    "sentiment_score": player.marketing_metrics.sentiment_score,
                    "conscientiousness": player.behavior_metrics.conscientiousness,
                    "adaptability": player.behavior_metrics.adaptability,
                    "resilience": player.behavior_metrics.resilience,
                    "deliberate_practice": player.behavior_metrics.deliberate_practice,
                    "executive_function": player.behavior_metrics.executive_function,
                    "leadership": player.behavior_metrics.leadership,
                }
            )
        else:
            self.initial.setdefault("country_code", "BRA")

    def clean(self):
        cleaned_data = super().clean()
        birth_date = cleaned_data.get("birth_date")
        age = cleaned_data.get("age")
        if birth_date:
            today = date.today()
            calculated_age = today.year - birth_date.year - (
                (today.month, today.day) < (birth_date.month, birth_date.day)
            )
            cleaned_data["age"] = calculated_age
            if calculated_age < 14 or calculated_age > 45:
                self.add_error("birth_date", "A idade calculada precisa ficar entre 14 e 45 anos.")
        elif age is None:
            cleaned_data["age"] = 18
        return cleaned_data


class CSVUploadForm(forms.Form):
    csv_file = forms.FileField()

    def __init__(self, *args, **kwargs):
        lang = kwargs.pop("lang", "pt")
        self.lang = lang
        super().__init__(*args, **kwargs)
        self.fields["csv_file"].widget.attrs["class"] = "field-input"
        self.fields["csv_file"].label = tr(lang, "csv_file")


class ComparisonForm(forms.Form):
    compare = forms.MultipleChoiceField(
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "field-input field-multi"}),
    )

    def __init__(self, *args, **kwargs):
        players = kwargs.pop("players")
        super().__init__(*args, **kwargs)
        self.fields["compare"].choices = [(str(player.id), player.name) for player in players]


class SnapshotSimulationForm(forms.Form):
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    current_value = forms.DecimalField(min_value=0, decimal_places=2, max_digits=14)
    performance_score = forms.FloatField(min_value=0, max_value=100, required=False)
    market_score = forms.FloatField(min_value=0, max_value=100, required=False)
    marketing_score = forms.FloatField(min_value=0, max_value=100, required=False)
    behavior_score = forms.FloatField(min_value=0, max_value=100, required=False)
    valuation_score = forms.FloatField(min_value=0, max_value=100, required=False)

    def __init__(self, *args, **kwargs):
        lang = kwargs.pop("lang", "pt")
        player = kwargs.pop("player", None)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "field-input"
        self.fields["date"].label = tr(lang, "snapshot_date")
        self.fields["current_value"].label = tr(lang, "current_value")
        self.fields["performance_score"].label = tr(lang, "performance_metrics")
        self.fields["market_score"].label = tr(lang, "market_metrics")
        self.fields["marketing_score"].label = tr(lang, "marketing_metrics")
        self.fields["behavior_score"].label = tr(lang, "behavior_metrics")
        self.fields["valuation_score"].label = tr(lang, "valuation_score")
        self.fields["current_value"].widget.attrs["placeholder"] = "Ex.: 4200000"
        self.fields["performance_score"].widget.attrs["placeholder"] = "Ex.: 74"
        self.fields["market_score"].widget.attrs["placeholder"] = "Ex.: 68"
        self.fields["marketing_score"].widget.attrs["placeholder"] = "Ex.: 57"
        self.fields["behavior_score"].widget.attrs["placeholder"] = "Ex.: 81"
        self.fields["valuation_score"].widget.attrs["placeholder"] = "Ex.: 72"
        self.fields["performance_score"].help_text = "Padrao de 0 a 100. Se deixar em branco, o sistema usa o valor atual."
        self.fields["market_score"].help_text = "Padrao de 0 a 100. Use a nota esperada para este snapshot."
        self.fields["marketing_score"].help_text = "Padrao de 0 a 100. Considere o alcance e a presenca publica do atleta."
        self.fields["behavior_score"].help_text = "Padrao de 0 a 100. Reflita a resposta mental e comportamental esperada."
        self.fields["valuation_score"].help_text = "Padrao de 0 a 100. Use apenas se quiser simular uma nota consolidada manual."
        if player:
            self.initial["current_value"] = player.current_value


class UpliftSimulationForm(forms.Form):
    xg = forms.FloatField(min_value=0, initial=0)
    xa = forms.FloatField(min_value=0, initial=0)
    passes_pct = forms.FloatField(min_value=0, initial=0)
    dribbles_pct = forms.FloatField(min_value=0, initial=0)
    tackles_pct = forms.FloatField(min_value=0, initial=0)
    high_intensity_distance = forms.FloatField(min_value=0, initial=0)
    final_third_recoveries = forms.FloatField(min_value=0, initial=0)

    def __init__(self, *args, **kwargs):
        lang = kwargs.pop("lang", "pt")
        player = kwargs.pop("player", None)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "field-input"
        labels = {
            "xg": "xg",
            "xa": "xa",
            "passes_pct": "passes_pct",
            "dribbles_pct": "dribbles_pct",
            "tackles_pct": "tackles_pct",
            "high_intensity_distance": "high_intensity_distance",
            "final_third_recoveries": "final_third_recoveries",
        }
        for field_name, key in labels.items():
            self.fields[field_name].label = f"{tr(lang, key)} {tr(lang, 'increase_percent')}"
        self.fields["xg"].widget.attrs["placeholder"] = "Ex.: 12"
        self.fields["xa"].widget.attrs["placeholder"] = "Ex.: 10"
        self.fields["passes_pct"].widget.attrs["placeholder"] = "Ex.: 5"
        self.fields["dribbles_pct"].widget.attrs["placeholder"] = "Ex.: 8"
        self.fields["tackles_pct"].widget.attrs["placeholder"] = "Ex.: 6"
        self.fields["high_intensity_distance"].widget.attrs["placeholder"] = "Ex.: 7"
        self.fields["final_third_recoveries"].widget.attrs["placeholder"] = "Ex.: 9"
        self.fields["xg"].help_text = "Aumento percentual sobre o dado atual por 90 minutos."
        self.fields["xa"].help_text = "Aumento percentual sobre o dado atual por 90 minutos."
        self.fields["passes_pct"].help_text = "Aumento percentual sobre a taxa atual."
        self.fields["dribbles_pct"].help_text = "Aumento percentual sobre a taxa atual."
        self.fields["tackles_pct"].help_text = "Aumento percentual sobre a taxa atual."
        self.fields["high_intensity_distance"].help_text = "Aumento percentual sobre a distancia atual por 90 minutos."
        self.fields["final_third_recoveries"].help_text = "Aumento percentual sobre as recuperacoes atuais por 90 minutos."


class AnalystNoteForm(forms.Form):
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    analysis_text = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}))
    strengths = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    weaknesses = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        lang = kwargs.pop("lang", "pt")
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "field-input"
        self.fields["date"].label = tr(lang, "snapshot_date")
        self.fields["analysis_text"].label = tr(lang, "analysis_text")
        self.fields["strengths"].label = tr(lang, "strengths")
        self.fields["weaknesses"].label = tr(lang, "weaknesses")


class DevelopmentPlanForm(forms.Form):
    goal = forms.CharField(max_length=255)
    target_metric = forms.CharField(max_length=80)
    target_value = forms.FloatField()
    deadline = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, **kwargs):
        lang = kwargs.pop("lang", "pt")
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "field-input"
        self.fields["goal"].label = tr(lang, "goal")
        self.fields["target_metric"].label = tr(lang, "target_metric")
        self.fields["target_value"].label = tr(lang, "target_value")
        self.fields["deadline"].label = tr(lang, "deadline")
        self.fields["goal"].widget.attrs["placeholder"] = "Ex.: Aumentar a influencia ofensiva mantendo regularidade competitiva."
        self.fields["target_metric"].widget.attrs["placeholder"] = "Ex.: xG + xA por 90, score de performance, passes progressivos %."
        self.fields["target_value"].widget.attrs["placeholder"] = "Ex.: 72"
        self.fields["goal"].help_text = "Escreva o objetivo em formato de acao clara e mensuravel."
        self.fields["target_metric"].help_text = "Defina uma metrica objetiva. Dados de jogo e performance devem seguir base por 90 minutos."
        self.fields["target_value"].help_text = "Use o padrao da metrica. Para scores consolidados, trabalhe na escala de 0 a 100."


class ProgressTrackingForm(forms.Form):
    metric = forms.CharField(max_length=80)
    current_value = forms.FloatField()
    target_value = forms.FloatField(min_value=0.0001)

    def __init__(self, *args, **kwargs):
        lang = kwargs.pop("lang", "pt")
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "field-input"
        self.fields["metric"].label = tr(lang, "metric")
        self.fields["current_value"].label = tr(lang, "current_value")
        self.fields["target_value"].label = tr(lang, "target_value")
        self.fields["metric"].widget.attrs["placeholder"] = "Ex.: Score de performance, xG por 90, recuperacoes no ultimo terco por 90."
        self.fields["current_value"].widget.attrs["placeholder"] = "Ex.: 64"
        self.fields["target_value"].widget.attrs["placeholder"] = "Ex.: 78"
        self.fields["metric"].help_text = "Escolha uma metrica unica e acompanhe sempre no mesmo padrao."
        self.fields["current_value"].help_text = "Para scores, use escala de 0 a 100. Para dados de jogo, use base por 90 minutos."
        self.fields["target_value"].help_text = "Defina a meta no mesmo padrao do valor atual para manter a comparacao consistente."


class OnBallEventForm(forms.Form):
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    pressure_status = forms.ChoiceField()
    field_zone = forms.ChoiceField(required=False)
    action_type = forms.ChoiceField()
    outcome = forms.ChoiceField()
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        lang = kwargs.pop("lang", "pt")
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "field-input"
        self.fields["date"].label = tr(lang, "snapshot_date")
        self.fields["pressure_status"].label = tr(lang, "pressure_status")
        self.fields["field_zone"].label = tr(lang, "field_zone")
        self.fields["action_type"].label = tr(lang, "action_executed")
        self.fields["outcome"].label = tr(lang, "action_result")
        self.fields["notes"].label = tr(lang, "on_ball_notes")
        self.fields["pressure_status"].choices = [
            ("under_pressure", tr(lang, "under_pressure")),
            ("no_pressure", tr(lang, "no_pressure")),
        ]
        self.fields["field_zone"].choices = [
            ("", "---------"),
            ("defense", tr(lang, "defense")),
            ("midfield", tr(lang, "midfield")),
            ("attack", tr(lang, "attack")),
        ]
        self.fields["action_type"].choices = [
            ("pass", tr(lang, "pass")),
            ("dribble", tr(lang, "dribble")),
            ("shot", tr(lang, "shot")),
            ("carry", tr(lang, "carry")),
            ("turnover", tr(lang, "turnover")),
        ]
        self.fields["outcome"].choices = [
            ("positive", tr(lang, "positive")),
            ("negative", tr(lang, "negative")),
        ]


class LiveAnalysisSessionForm(forms.Form):
    observed_on = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    kickoff_time = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}))
    venue = forms.CharField(max_length=160)
    home_away = forms.ChoiceField()
    weather = forms.CharField(max_length=120)
    played_position = forms.ChoiceField()
    starter_status = forms.ChoiceField()
    minute_entered = forms.IntegerField(min_value=1, max_value=130, required=False)
    match_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    match_story = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 5}))
    confidence = forms.IntegerField(min_value=1, max_value=10)
    intensity = forms.IntegerField(min_value=1, max_value=10)
    focus = forms.IntegerField(min_value=1, max_value=10)
    decision_making = forms.IntegerField(min_value=1, max_value=10)
    resilience = forms.IntegerField(min_value=1, max_value=10)
    anxiety = forms.IntegerField(min_value=1, max_value=10)
    motivation = forms.IntegerField(min_value=1, max_value=10)
    communication = forms.IntegerField(min_value=1, max_value=10)
    discipline = forms.IntegerField(min_value=1, max_value=10)
    emotional_control = forms.IntegerField(min_value=1, max_value=10)

    def __init__(self, *args, **kwargs):
        lang = kwargs.pop("lang", "pt")
        self.lang = lang
        session = kwargs.pop("session", None)
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            css_class = "field-input"
            if field_name in {
                "confidence",
                "intensity",
                "focus",
                "decision_making",
                "resilience",
                "anxiety",
                "motivation",
                "communication",
                "discipline",
                "emotional_control",
            }:
                field.widget = forms.NumberInput(attrs={"class": css_class, "min": 1, "max": 10})
            else:
                field.widget.attrs["class"] = css_class
        self.fields["observed_on"].label = tr(lang, "match_date")
        self.fields["kickoff_time"].label = tr(lang, "kickoff_time")
        self.fields["venue"].label = tr(lang, "match_venue")
        self.fields["home_away"].label = tr(lang, "home_away")
        self.fields["weather"].label = tr(lang, "weather_conditions")
        self.fields["played_position"].label = tr(lang, "played_position")
        self.fields["starter_status"].label = tr(lang, "starter_status")
        self.fields["minute_entered"].label = tr(lang, "minute_entered")
        self.fields["match_notes"].label = tr(lang, "match_notes")
        self.fields["match_story"].label = tr(lang, "match_story")
        self.fields["confidence"].label = tr(lang, "confidence")
        self.fields["intensity"].label = tr(lang, "intensity")
        self.fields["focus"].label = tr(lang, "focus")
        self.fields["decision_making"].label = tr(lang, "decision_making")
        self.fields["resilience"].label = tr(lang, "resilience")
        self.fields["anxiety"].label = tr(lang, "anxiety")
        self.fields["motivation"].label = tr(lang, "motivation")
        self.fields["communication"].label = tr(lang, "communication")
        self.fields["discipline"].label = tr(lang, "discipline")
        self.fields["emotional_control"].label = tr(lang, "emotional_control")
        self.fields["home_away"].choices = [
            ("home", tr(lang, "home_match")),
            ("away", tr(lang, "away_match")),
        ]
        self.fields["played_position"].choices = get_position_choices(lang)
        self.fields["starter_status"].choices = get_localized_choice_pairs(LIVE_STARTER_STATUS_LABELS, lang)
        if session:
            self.initial.update(
                {
                    "observed_on": session.observed_on,
                    "kickoff_time": session.kickoff_time,
                    "venue": session.venue,
                    "home_away": session.home_away,
                    "weather": session.weather,
                    "played_position": normalize_position_value(session.played_position),
                    "starter_status": session.starter_status,
                    "minute_entered": session.minute_entered,
                    "match_notes": session.match_notes,
                    "match_story": session.match_story,
                    "confidence": session.confidence,
                    "intensity": session.intensity,
                    "focus": session.focus,
                    "decision_making": session.decision_making,
                    "resilience": session.resilience,
                    "anxiety": session.anxiety,
                    "motivation": session.motivation,
                    "communication": session.communication,
                    "discipline": session.discipline,
                    "emotional_control": session.emotional_control,
                }
            )

    def clean(self):
        cleaned_data = super().clean()
        starter_status = cleaned_data.get("starter_status")
        minute_entered = cleaned_data.get("minute_entered")
        if starter_status == "substitute" and minute_entered is None:
            self.add_error("minute_entered", tr(getattr(self, "lang", "pt"), "minute_entered_required"))
        if starter_status == "starter":
            cleaned_data["minute_entered"] = None
        return cleaned_data


class LiveAnalysisEventForm(forms.Form):
    session_id = forms.IntegerField()
    player_id = forms.IntegerField()
    event_type = forms.CharField(max_length=30)
    match_period = forms.CharField(max_length=20)
    minute = forms.IntegerField(min_value=1, max_value=130)
    duration_seconds = forms.FloatField(required=False, min_value=0)
    created_at = forms.DateTimeField()
    notes = forms.CharField(required=False, max_length=255)
