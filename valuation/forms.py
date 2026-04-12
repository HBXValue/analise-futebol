from django import forms

from valuation.i18n import tr


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
    name = forms.CharField(max_length=160)
    age = forms.IntegerField(min_value=14, max_value=45)
    position = forms.CharField(max_length=60)
    current_value = forms.DecimalField(min_value=0, decimal_places=2, max_digits=14)
    league_level = forms.CharField(max_length=80)
    club_origin = forms.CharField(max_length=160)

    xg = forms.FloatField(min_value=0)
    xa = forms.FloatField(min_value=0)
    passes_pct = forms.FloatField(min_value=0, max_value=100)
    dribbles_pct = forms.FloatField(min_value=0, max_value=100)
    tackles_pct = forms.FloatField(min_value=0, max_value=100)
    high_intensity_distance = forms.FloatField(min_value=0)
    final_third_recoveries = forms.FloatField(min_value=0)

    annual_growth = forms.FloatField()
    club_interest = forms.FloatField(min_value=0, max_value=100)
    league_score = forms.FloatField(min_value=0, max_value=100)
    age_factor = forms.FloatField(min_value=0, max_value=100)
    club_reputation = forms.FloatField(min_value=0, max_value=100)

    followers = forms.FloatField(min_value=0)
    engagement = forms.FloatField(min_value=0)
    media_mentions = forms.FloatField(min_value=0)
    sponsorships = forms.FloatField(min_value=0)
    sentiment_score = forms.FloatField(min_value=0, max_value=100)

    conscientiousness = forms.FloatField(min_value=0, max_value=100)
    adaptability = forms.FloatField(min_value=0, max_value=100)
    resilience = forms.FloatField(min_value=0, max_value=100)
    deliberate_practice = forms.FloatField(min_value=0, max_value=100)
    executive_function = forms.FloatField(min_value=0, max_value=100)
    leadership = forms.FloatField(min_value=0, max_value=100)

    def __init__(self, *args, **kwargs):
        lang = kwargs.pop("lang", "pt")
        self.lang = lang
        player = kwargs.pop("player", None)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "field-input"
        labels = {
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
        for field_name, key in labels.items():
            self.fields[field_name].label = tr(lang, key)
        if player:
            self.initial.update(
                {
                    "name": player.name,
                    "age": player.age,
                    "position": player.position,
                    "current_value": player.current_value,
                    "league_level": player.league_level,
                    "club_origin": player.club_origin,
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
    played_position = forms.CharField(max_length=60)
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
                "confidence", "intensity", "focus", "decision_making", "resilience",
                "anxiety", "motivation", "communication", "discipline", "emotional_control",
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
        self.fields["starter_status"].choices = [
            ("starter", tr(lang, "starter")),
            ("substitute", tr(lang, "substitute")),
        ]
        if session:
            self.initial.update(
                {
                    "observed_on": session.observed_on,
                    "kickoff_time": session.kickoff_time,
                    "venue": session.venue,
                    "home_away": session.home_away,
                    "weather": session.weather,
                    "played_position": session.played_position,
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
