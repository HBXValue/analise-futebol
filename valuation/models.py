from decimal import Decimal
import uuid

from django.db import models

from catalog.models import Division
from clubs.models import Club


class User(models.Model):
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255)

    class Meta:
        db_table = "users"
        ordering = ["email"]

    def __str__(self):
        return self.email


class Player(models.Model):
    class DominantFoot(models.TextChoices):
        RIGHT = "right", "Direito"
        LEFT = "left", "Esquerdo"
        BOTH = "both", "Ambos"

    class Category(models.TextChoices):
        PROFESSIONAL = "professional", "Profissional"
        ACADEMY = "academy", "Base"

    class SquadStatus(models.TextChoices):
        STARTER = "starter", "Titular"
        BACKUP = "backup", "Reserva"
        ROTATION = "rotation", "Rotacao"
        LIMITED = "limited", "Pouco utilizado"
        RECOVERING = "recovering", "Retorno de lesao"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="players")
    name = models.CharField(max_length=160)
    public_name = models.CharField(max_length=160, blank=True)
    age = models.PositiveSmallIntegerField()
    birth_date = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=80, blank=True)
    position = models.CharField(max_length=60)
    secondary_positions = models.JSONField(default=list, blank=True)
    dominant_foot = models.CharField(max_length=10, choices=DominantFoot.choices, blank=True)
    height_cm = models.PositiveSmallIntegerField(null=True, blank=True)
    weight_kg = models.PositiveSmallIntegerField(null=True, blank=True)
    current_value = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    league_level = models.CharField(max_length=80)
    club_origin = models.CharField(max_length=160)
    category = models.CharField(max_length=20, choices=Category.choices, blank=True)
    contract_months_remaining = models.PositiveSmallIntegerField(null=True, blank=True)
    squad_status = models.CharField(max_length=20, choices=SquadStatus.choices, blank=True)
    athlete_objectives = models.JSONField(default=list, blank=True)
    training_environment_score = models.FloatField(default=0)
    trajectory_score = models.FloatField(default=0)
    profile_notes = models.TextField(blank=True)
    division_reference = models.ForeignKey(
        Division,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="valuation_players",
    )
    club_reference = models.ForeignKey(
        Club,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="valuation_players",
    )

    class Meta:
        db_table = "players"
        ordering = ["name"]

    def __str__(self):
        return self.name


class HBXValueProfile(models.Model):
    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        AI = "ai", "IA"

    player = models.OneToOneField(Player, on_delete=models.CASCADE, related_name="hbx_value_profile")
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.MANUAL)
    mention_volume = models.PositiveIntegerField(default=0)
    mention_momentum = models.FloatField(default=0)
    sentiment_score = models.FloatField(default=0)
    estimated_reach = models.FloatField(default=0)
    source_relevance = models.FloatField(default=0)
    performance_rating = models.FloatField(default=0)
    attention_spike = models.FloatField(default=0)
    market_response = models.FloatField(default=0)
    visibility_efficiency = models.FloatField(default=0)
    market_perception_index = models.FloatField(default=0)
    performance_impact_score = models.FloatField(default=0)
    impact_correlation_score = models.FloatField(default=0)
    trend_label = models.CharField(max_length=40, blank=True)
    narrative_label = models.CharField(max_length=40, blank=True)
    market_label = models.CharField(max_length=80, blank=True)
    narrative_summary = models.TextField(blank=True)
    narrative_keywords = models.JSONField(default=list, blank=True)
    strategic_insights = models.JSONField(default=list, blank=True)
    source_targets = models.JSONField(default=dict, blank=True)
    source_collection = models.JSONField(default=dict, blank=True)
    delivery_payload = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hbx_value_profiles"
        ordering = ["-updated_at", "-id"]


class AthleteAIInsight(models.Model):
    class Scope(models.TextChoices):
        DASHBOARD = "dashboard", "Dashboard"
        MARKET = "market", "Market Intelligence"
        PERFORMANCE = "performance", "Performance Intelligence"
        REPORTS = "reports", "Reports"

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="ai_insights")
    scope = models.CharField(max_length=20, choices=Scope.choices, default=Scope.DASHBOARD)
    window_days = models.PositiveSmallIntegerField(default=90)
    language = models.CharField(max_length=10, default="pt")
    prompt_version = models.CharField(max_length=20, default="v1")
    model_name = models.CharField(max_length=80, blank=True)
    status_label = models.CharField(max_length=80, blank=True)
    executive_summary = models.TextField(blank=True)
    main_change = models.TextField(blank=True)
    main_risk = models.TextField(blank=True)
    main_opportunity = models.TextField(blank=True)
    recommended_action = models.TextField(blank=True)
    confidence = models.FloatField(default=0)
    dashboard_cards = models.JSONField(default=list, blank=True)
    payload_snapshot = models.JSONField(default=dict, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "athlete_ai_insights"
        ordering = ["-updated_at", "-id"]
        unique_together = ("player", "scope", "window_days", "language", "prompt_version")


class AthleteIdentity(models.Model):
    player = models.OneToOneField(Player, on_delete=models.CASCADE, related_name="identity_360")
    player_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    secondary_nationalities = models.JSONField(default=list, blank=True)
    passports = models.JSONField(default=list, blank=True)
    international_eligibility = models.JSONField(default=list, blank=True)
    external_ids = models.JSONField(default=dict, blank=True)
    status_label = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "athlete_identities"
        ordering = ["player__name", "id"]

    def __str__(self):
        return f"{self.player.name} | {self.player_uuid}"


class PerformanceMetrics(models.Model):
    player = models.OneToOneField(Player, on_delete=models.CASCADE, primary_key=True, related_name="performance_metrics", db_column="player_id")
    xg = models.FloatField(default=0)
    xa = models.FloatField(default=0)
    passes_pct = models.FloatField(default=0)
    dribbles_pct = models.FloatField(default=0)
    tackles_pct = models.FloatField(default=0)
    high_intensity_distance = models.FloatField(default=0)
    final_third_recoveries = models.FloatField(default=0)

    class Meta:
        db_table = "performance_metrics"


class MarketMetrics(models.Model):
    player = models.OneToOneField(Player, on_delete=models.CASCADE, primary_key=True, related_name="market_metrics", db_column="player_id")
    annual_growth = models.FloatField(default=0)
    club_interest = models.FloatField(default=0)
    league_score = models.FloatField(default=0)
    age_factor = models.FloatField(default=0)
    club_reputation = models.FloatField(default=0)

    class Meta:
        db_table = "market_metrics"


class MarketingMetrics(models.Model):
    player = models.OneToOneField(Player, on_delete=models.CASCADE, primary_key=True, related_name="marketing_metrics", db_column="player_id")
    instagram_handle = models.CharField(max_length=120, blank=True)
    instagram_followers = models.FloatField(default=0)
    instagram_engagement = models.FloatField(default=0)
    instagram_posts = models.FloatField(default=0)
    tiktok_handle = models.CharField(max_length=120, blank=True)
    tiktok_followers = models.FloatField(default=0)
    tiktok_engagement = models.FloatField(default=0)
    tiktok_posts = models.FloatField(default=0)
    x_handle = models.CharField(max_length=120, blank=True)
    x_followers = models.FloatField(default=0)
    x_engagement = models.FloatField(default=0)
    google_news_query = models.CharField(max_length=160, blank=True)
    youtube_query = models.CharField(max_length=160, blank=True)
    youtube_subscribers = models.FloatField(default=0)
    youtube_avg_views = models.FloatField(default=0)
    youtube_videos = models.FloatField(default=0)
    collection_notes = models.TextField(blank=True)
    followers = models.FloatField(default=0)
    engagement = models.FloatField(default=0)
    media_mentions = models.FloatField(default=0)
    sponsorships = models.FloatField(default=0)
    sentiment_score = models.FloatField(default=0)

    class Meta:
        db_table = "marketing_metrics"


class BehaviorMetrics(models.Model):
    player = models.OneToOneField(Player, on_delete=models.CASCADE, primary_key=True, related_name="behavior_metrics", db_column="player_id")
    conscientiousness = models.FloatField(default=0)
    adaptability = models.FloatField(default=0)
    resilience = models.FloatField(default=0)
    deliberate_practice = models.FloatField(default=0)
    executive_function = models.FloatField(default=0)
    leadership = models.FloatField(default=0)

    class Meta:
        db_table = "behavior_metrics"


class PlayerHistory(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="history", db_column="player_id")
    date = models.DateField()
    performance_score = models.FloatField(default=0)
    market_score = models.FloatField(default=0)
    marketing_score = models.FloatField(default=0)
    behavior_score = models.FloatField(default=0)
    valuation_score = models.FloatField(default=0)
    current_value = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        db_table = "player_history"
        ordering = ["date", "id"]


class AnalystNote(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="analyst_notes", db_column="player_id")
    date = models.DateField()
    analysis_text = models.TextField()
    strengths = models.TextField(blank=True)
    weaknesses = models.TextField(blank=True)

    class Meta:
        db_table = "analyst_notes"
        ordering = ["-date", "-id"]


class DevelopmentPlan(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="development_plans", db_column="player_id")
    goal = models.CharField(max_length=255)
    target_metric = models.CharField(max_length=80)
    target_value = models.FloatField()
    deadline = models.DateField()

    class Meta:
        db_table = "development_plan"
        ordering = ["deadline", "id"]


class ProgressTracking(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="progress_tracking", db_column="player_id")
    metric = models.CharField(max_length=80)
    current_value = models.FloatField()
    target_value = models.FloatField()
    progress_pct = models.FloatField(default=0)

    class Meta:
        db_table = "progress_tracking"
        ordering = ["metric", "id"]


class OnBallEvent(models.Model):
    class Pressure(models.TextChoices):
        UNDER_PRESSURE = "under_pressure", "Under pressure"
        NO_PRESSURE = "no_pressure", "No pressure"

    class FieldZone(models.TextChoices):
        DEFENSE = "defense", "Defense"
        MIDFIELD = "midfield", "Midfield"
        ATTACK = "attack", "Attack"

    class ActionType(models.TextChoices):
        PASS = "pass", "Pass"
        DRIBBLE = "dribble", "Dribble"
        SHOT = "shot", "Shot"
        CARRY = "carry", "Carry"
        TURNOVER = "turnover", "Turnover"

    class Outcome(models.TextChoices):
        POSITIVE = "positive", "Positive"
        NEGATIVE = "negative", "Negative"

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="on_ball_events", db_column="player_id")
    date = models.DateField()
    pressure_status = models.CharField(max_length=20, choices=Pressure.choices)
    field_zone = models.CharField(max_length=20, choices=FieldZone.choices, blank=True)
    action_type = models.CharField(max_length=20, choices=ActionType.choices)
    outcome = models.CharField(max_length=20, choices=Outcome.choices)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "on_ball_events"
        ordering = ["-date", "-id"]


class LiveAnalysisEvent(models.Model):
    class MatchPeriod(models.TextChoices):
        FIRST_HALF = "first_half", "First half"
        SECOND_HALF = "second_half", "Second half"

    class EventType(models.TextChoices):
        RECEIVED = "received", "Received"
        CONTROLLED = "controlled", "Controlled"
        FORWARD_PASS = "forward_pass", "Forward pass"
        BACKWARD_PASS = "backward_pass", "Backward pass"
        PROGRESSED = "progressed", "Progressed with ball"
        CROSS = "cross", "Cross"
        SHOT = "shot", "Shot"
        GOAL = "goal", "Goal"
        DISPOSSESSED = "dispossessed", "Dispossessed"
        TACKLE_WON = "tackle_won", "Tackle won"

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="live_analysis_events", db_column="player_id")
    session = models.ForeignKey("LiveAnalysisSession", on_delete=models.CASCADE, related_name="events", null=True, blank=True)
    created_at = models.DateTimeField()
    match_period = models.CharField(max_length=20, choices=MatchPeriod.choices, default=MatchPeriod.FIRST_HALF)
    minute = models.PositiveSmallIntegerField(default=1)
    event_type = models.CharField(max_length=30, choices=EventType.choices)
    duration_seconds = models.FloatField(default=0)
    points = models.FloatField(default=0)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "live_analysis_events"
        ordering = ["-created_at", "-id"]


class LiveAnalysisSession(models.Model):
    class HomeAway(models.TextChoices):
        HOME = "home", "Home"
        AWAY = "away", "Away"

    class StarterStatus(models.TextChoices):
        STARTER = "starter", "Starter"
        SUBSTITUTE = "substitute", "Substitute"

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="live_analysis_sessions", db_column="player_id")
    observed_on = models.DateField()
    kickoff_time = models.TimeField()
    venue = models.CharField(max_length=160)
    home_away = models.CharField(max_length=10, choices=HomeAway.choices)
    weather = models.CharField(max_length=120)
    played_position = models.CharField(max_length=60)
    starter_status = models.CharField(max_length=20, choices=StarterStatus.choices)
    minute_entered = models.PositiveSmallIntegerField(null=True, blank=True)
    match_notes = models.TextField(blank=True)
    match_story = models.TextField(blank=True)
    confidence = models.PositiveSmallIntegerField(default=5)
    intensity = models.PositiveSmallIntegerField(default=5)
    focus = models.PositiveSmallIntegerField(default=5)
    decision_making = models.PositiveSmallIntegerField(default=5)
    resilience = models.PositiveSmallIntegerField(default=5)
    anxiety = models.PositiveSmallIntegerField(default=5)
    motivation = models.PositiveSmallIntegerField(default=5)
    communication = models.PositiveSmallIntegerField(default=5)
    discipline = models.PositiveSmallIntegerField(default=5)
    emotional_control = models.PositiveSmallIntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "live_analysis_sessions"
        ordering = ["-observed_on", "-kickoff_time", "-id"]


class LivePlayerEvaluation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="live_player_evaluations")
    player = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True, related_name="live_player_evaluations")
    athlete_name = models.CharField(max_length=160)
    shirt_number = models.PositiveSmallIntegerField(null=True, blank=True)
    position = models.CharField(max_length=60)
    team = models.CharField(max_length=160)
    opponent = models.CharField(max_length=160)
    competition = models.CharField(max_length=160)
    match_date = models.DateField()
    analyst_name = models.CharField(max_length=160)
    minutes_played = models.PositiveSmallIntegerField(null=True, blank=True)
    physical_data_source = models.CharField(max_length=20, default="manual")
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    saved_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "live_player_evaluations"
        ordering = ["-match_date", "-saved_at", "-id"]


class DataSourceLog(models.Model):
    class SourceType(models.TextChoices):
        MANUAL = "manual", "Manual"
        MATCH_ANALYSIS = "match_analysis", "Match Analysis"
        HBX_VALUE = "hbx_value", "HBX Value"
        GO_CARRIERA = "go_carriera", "Go Carriera"
        IMPORT = "import", "Importacao"
        API = "api", "API"
        AI = "ai", "IA"
        SYSTEM = "system", "Sistema"

    player = models.ForeignKey(Player, on_delete=models.CASCADE, null=True, blank=True, related_name="data_source_logs")
    source_type = models.CharField(max_length=30, choices=SourceType.choices)
    source_name = models.CharField(max_length=120, blank=True)
    reference_id = models.CharField(max_length=120, blank=True)
    confidence_score = models.FloatField(default=50)
    payload = models.JSONField(default=dict, blank=True)
    collected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "data_source_logs"
        ordering = ["-collected_at", "-id"]


class AthleteSnapshot(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="athlete_snapshots")
    snapshot_date = models.DateField()
    source = models.CharField(max_length=30, default=DataSourceLog.SourceType.SYSTEM)
    data_confidence_score = models.FloatField(default=50)
    identity_payload = models.JSONField(default=dict, blank=True)
    career_payload = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "athlete_snapshots"
        ordering = ["-snapshot_date", "-id"]
        unique_together = ("player", "snapshot_date", "source")


class PerformanceSnapshot(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="performance_snapshots")
    snapshot_date = models.DateField()
    source = models.CharField(max_length=30, default=DataSourceLog.SourceType.SYSTEM)
    related_report = models.ForeignKey(LivePlayerEvaluation, on_delete=models.SET_NULL, null=True, blank=True, related_name="performance_snapshots")
    performance_score = models.FloatField(default=0)
    output_score = models.FloatField(default=0)
    positional_fit_score = models.FloatField(default=0)
    consistency_score = models.FloatField(default=0)
    context_score = models.FloatField(default=0)
    data_confidence_score = models.FloatField(default=50)
    metrics_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "performance_snapshots"
        ordering = ["-snapshot_date", "-id"]
        unique_together = ("player", "snapshot_date", "source")


class BehaviorSnapshot(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="behavior_snapshots")
    snapshot_date = models.DateField()
    source = models.CharField(max_length=30, default=DataSourceLog.SourceType.SYSTEM)
    behavior_score = models.FloatField(default=0)
    readiness_score = models.FloatField(default=0)
    habit_score = models.FloatField(default=0)
    emotional_stability_score = models.FloatField(default=0)
    professionalism_score = models.FloatField(default=0)
    adherence_score = models.FloatField(default=0)
    consistency_score = models.FloatField(default=0)
    injury_recovery_behavior_score = models.FloatField(default=0)
    engagement_score = models.FloatField(default=0)
    data_confidence_score = models.FloatField(default=50)
    metrics_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "behavior_snapshots"
        ordering = ["-snapshot_date", "-id"]
        unique_together = ("player", "snapshot_date", "source")


class MarketSnapshot(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="market_snapshots")
    snapshot_date = models.DateField()
    source = models.CharField(max_length=30, default=DataSourceLog.SourceType.SYSTEM)
    market_score = models.FloatField(default=0)
    current_value = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    projected_value = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    contract_timing_score = models.FloatField(default=0)
    league_context_score = models.FloatField(default=0)
    club_reputation_score = models.FloatField(default=0)
    data_confidence_score = models.FloatField(default=50)
    metrics_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "market_snapshots"
        ordering = ["-snapshot_date", "-id"]
        unique_together = ("player", "snapshot_date", "source")


class MarketingSnapshot(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="marketing_snapshots")
    snapshot_date = models.DateField()
    source = models.CharField(max_length=30, default=DataSourceLog.SourceType.SYSTEM)
    marketing_score = models.FloatField(default=0)
    media_attention_score = models.FloatField(default=0)
    exposure_performance_ratio = models.FloatField(default=0)
    narrative_sentiment_score = models.FloatField(default=0)
    authority_score = models.FloatField(default=0)
    growth_momentum_score = models.FloatField(default=0)
    buzz_stability_score = models.FloatField(default=0)
    data_confidence_score = models.FloatField(default=50)
    metrics_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "marketing_snapshots"
        ordering = ["-snapshot_date", "-id"]
        unique_together = ("player", "snapshot_date", "source")


class ScoreSnapshot(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="score_snapshots")
    snapshot_date = models.DateField()
    source = models.CharField(max_length=30, default=DataSourceLog.SourceType.SYSTEM)
    performance_score = models.FloatField(default=0)
    market_score = models.FloatField(default=0)
    marketing_score = models.FloatField(default=0)
    behavior_score = models.FloatField(default=0)
    potential_score = models.FloatField(default=0)
    final_score = models.FloatField(default=0)
    adjustment = models.FloatField(default=0)
    classification = models.CharField(max_length=120, blank=True)
    traffic_light = models.CharField(max_length=40, blank=True)
    data_confidence_score = models.FloatField(default=50)
    scores_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "score_snapshots"
        ordering = ["-snapshot_date", "-id"]
        unique_together = ("player", "snapshot_date", "source")


class ProjectionSnapshot(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="projection_snapshots")
    snapshot_date = models.DateField()
    source = models.CharField(max_length=30, default=DataSourceLog.SourceType.SYSTEM)
    potential_score = models.FloatField(default=0)
    projected_value = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    growth_velocity_score = models.FloatField(default=0)
    stagnation_risk_score = models.FloatField(default=0)
    adaptation_probability_score = models.FloatField(default=0)
    opportunity_window = models.CharField(max_length=80, blank=True)
    data_confidence_score = models.FloatField(default=50)
    projection_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "projection_snapshots"
        ordering = ["-snapshot_date", "-id"]
        unique_together = ("player", "snapshot_date", "source")


class AthleteCareerEntry(models.Model):
    class MoveType(models.TextChoices):
        PERMANENT = "permanent", "Contrato definitivo"
        LOAN = "loan", "Emprestimo"
        ACADEMY = "academy", "Base"
        PROMOTION = "promotion", "Promocao interna"
        TRIAL = "trial", "Periodo de avaliacao"
        OTHER = "other", "Outro"

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="career_entries")
    club_name = models.CharField(max_length=160)
    country_name = models.CharField(max_length=120, blank=True)
    division_name = models.CharField(max_length=120, blank=True)
    season_label = models.CharField(max_length=60, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    move_type = models.CharField(max_length=20, choices=MoveType.choices, default=MoveType.PERMANENT)
    is_current = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "athlete_career_entries"
        ordering = ["-is_current", "-start_date", "-id"]

    def __str__(self):
        return f"{self.player.name} | {self.club_name}"


class AthleteContract(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Ativo"
        RENEWAL = "renewal", "Em renovacao"
        EXPIRING = "expiring", "Proximo do fim"
        LOAN = "loan", "Emprestimo"
        FREE = "free", "Livre"

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="contracts")
    club_name = models.CharField(max_length=160)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    monthly_salary = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    release_clause = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    is_current = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "athlete_contracts"
        ordering = ["-is_current", "-start_date", "-id"]


class AthleteTransfer(models.Model):
    class TransferType(models.TextChoices):
        PERMANENT = "permanent", "Definitiva"
        LOAN = "loan", "Emprestimo"
        RETURN_LOAN = "return_loan", "Retorno de emprestimo"
        FREE = "free", "Livre"
        INTERNAL = "internal", "Promocao interna"
        OTHER = "other", "Outra"

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="transfers")
    from_club = models.CharField(max_length=160, blank=True)
    to_club = models.CharField(max_length=160)
    transfer_date = models.DateField()
    transfer_type = models.CharField(max_length=20, choices=TransferType.choices, default=TransferType.PERMANENT)
    transfer_fee = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=10, default="EUR")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "athlete_transfers"
        ordering = ["-transfer_date", "-id"]


class GoCarrieraCheckIn(models.Model):
    class InjuryStatus(models.TextChoices):
        NONE = "none", "Sem lesao"
        MANAGED = "managed", "Controle de carga"
        RECOVERY = "recovery", "Em recuperacao"

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="go_carriera_checkins")
    checkin_date = models.DateField()
    sleep_quality = models.PositiveSmallIntegerField(default=0)
    hydration = models.PositiveSmallIntegerField(default=0)
    nutrition = models.PositiveSmallIntegerField(default=0)
    energy = models.PositiveSmallIntegerField(default=0)
    focus = models.PositiveSmallIntegerField(default=0)
    mood = models.PositiveSmallIntegerField(default=0)
    motivation = models.PositiveSmallIntegerField(default=0)
    post_error_response = models.PositiveSmallIntegerField(default=0)
    soreness = models.PositiveSmallIntegerField(default=0)
    recovery = models.PositiveSmallIntegerField(default=0)
    treatment_adherence = models.PositiveSmallIntegerField(default=0)
    injury_status = models.CharField(max_length=20, choices=InjuryStatus.choices, default=InjuryStatus.NONE)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "go_carriera_checkins"
        ordering = ["-checkin_date", "-id"]
        unique_together = ("player", "checkin_date")


class CareerIntelligenceCase(models.Model):
    class Category(models.TextChoices):
        PROFESSIONAL = "professional", "Profissional"
        ACADEMY = "academy", "Base"

    class SquadStatus(models.TextChoices):
        STARTER = "starter", "Titular"
        BACKUP = "backup", "Reserva"
        ROTATION = "rotation", "Rotacao"
        LIMITED = "limited", "Pouco utilizado"
        RECOVERING = "recovering", "Retorno de lesao"

    class CurrentStep(models.TextChoices):
        ATHLETE = "athlete", "Atleta"
        CLUB = "club", "Clube"
        COACH = "coach", "Treinador"
        GAME_MODEL = "game_model", "Modelo de jogo"
        COMPETITION = "competition", "Concorrencia"
        DIAGNOSIS = "diagnosis", "Diagnostico"
        PROGNOSIS = "prognosis", "Prognostico"
        DEVELOPMENT = "development", "Plano"
        REPORT = "report", "Relatorio"

    class DominantFoot(models.TextChoices):
        RIGHT = "right", "Direito"
        LEFT = "left", "Esquerdo"
        BOTH = "both", "Ambos"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="career_cases")
    player = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True, related_name="career_cases")
    athlete_name = models.CharField(max_length=160)
    birth_date = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=80, blank=True)
    position_primary = models.CharField(max_length=60, blank=True)
    secondary_positions = models.JSONField(default=list, blank=True)
    dominant_foot = models.CharField(max_length=10, choices=DominantFoot.choices, blank=True)
    height_cm = models.PositiveSmallIntegerField(null=True, blank=True)
    weight_kg = models.PositiveSmallIntegerField(null=True, blank=True)
    current_club = models.CharField(max_length=160, blank=True)
    category = models.CharField(max_length=20, choices=Category.choices, blank=True)
    contract_months_remaining = models.PositiveSmallIntegerField(null=True, blank=True)
    squad_status = models.CharField(max_length=20, choices=SquadStatus.choices, blank=True)
    athlete_objectives = models.JSONField(default=list, blank=True)
    analyst_notes = models.TextField(blank=True)
    current_step = models.CharField(max_length=20, choices=CurrentStep.choices, default=CurrentStep.ATHLETE)
    report_generated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "career_intelligence_cases"
        ordering = ["-updated_at", "-id"]

    def __str__(self):
        return self.athlete_name


class ClubCompetitiveContext(models.Model):
    class TeamMoment(models.TextChoices):
        TITLE_RACE = "title_race", "Disputa por titulo"
        RELEGATION = "relegation", "Luta contra rebaixamento"
        REBUILD = "rebuild", "Reconstrucao"
        DEVELOPMENT = "development", "Desenvolvimento"

    class PressureLevel(models.TextChoices):
        HIGH = "high", "Alta"
        MEDIUM = "medium", "Media"
        LOW = "low", "Baixa"

    class ClubPhilosophy(models.TextChoices):
        DEVELOPMENT = "development", "Formador"
        COMPETITIVE = "competitive", "Competitivo"
        MIXED = "mixed", "Misto"

    case = models.OneToOneField(CareerIntelligenceCase, on_delete=models.CASCADE, related_name="club_context")
    club_name = models.CharField(max_length=160)
    competition = models.CharField(max_length=160)
    category = models.CharField(max_length=80, blank=True)
    team_moment = models.CharField(max_length=20, choices=TeamMoment.choices)
    pressure_level = models.CharField(max_length=10, choices=PressureLevel.choices)
    club_philosophy = models.CharField(max_length=20, choices=ClubPhilosophy.choices)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "club_competitive_contexts"
        ordering = ["club_name", "id"]


class CoachProfile(models.Model):
    class ProfileType(models.TextChoices):
        DEVELOPER = "developer", "Formador"
        CONSERVATIVE = "conservative", "Conservador"
        OFFENSIVE = "offensive", "Ofensivo"
        REACTIVE = "reactive", "Reativo"
        MANAGER = "manager", "Gestor"

    class Preference(models.TextChoices):
        EXPERIENCE = "experience", "Experiencia"
        YOUTH = "youth", "Juventude"
        BALANCED = "balanced", "Equilibrado"

    class DemandLevel(models.TextChoices):
        LOW = "low", "Baixo"
        MEDIUM = "medium", "Medio"
        HIGH = "high", "Alto"

    case = models.OneToOneField(CareerIntelligenceCase, on_delete=models.CASCADE, related_name="coach_profile")
    coach_name = models.CharField(max_length=160)
    age = models.PositiveSmallIntegerField(null=True, blank=True)
    nationality = models.CharField(max_length=80, blank=True)
    months_in_charge = models.PositiveSmallIntegerField(null=True, blank=True)
    profile_type = models.CharField(max_length=20, choices=ProfileType.choices)
    experience_preference = models.CharField(max_length=20, choices=Preference.choices)
    academy_usage_history = models.TextField(blank=True)
    physical_demand = models.CharField(max_length=10, choices=DemandLevel.choices)
    tactical_demand = models.CharField(max_length=10, choices=DemandLevel.choices)
    selection_criteria = models.JSONField(default=list, blank=True)
    analyst_notes = models.TextField(blank=True)

    class Meta:
        db_table = "coach_profiles"
        ordering = ["coach_name", "id"]


class TacticalGameModel(models.Model):
    class PlayingStyle(models.TextChoices):
        POSSESSION = "possession", "Posse"
        TRANSITION = "transition", "Transicao"
        DIRECT = "direct", "Jogo direto"
        HIGH_PRESS = "high_press", "Pressao alta"
        MIXED = "mixed", "Misto"

    class CreativeFreedom(models.TextChoices):
        LOW = "low", "Baixa"
        MEDIUM = "medium", "Media"
        HIGH = "high", "Alta"

    case = models.OneToOneField(CareerIntelligenceCase, on_delete=models.CASCADE, related_name="game_model")
    base_system = models.CharField(max_length=30, blank=True)
    in_possession_system = models.CharField(max_length=30, blank=True)
    out_of_possession_system = models.CharField(max_length=30, blank=True)
    playing_style = models.CharField(max_length=20, choices=PlayingStyle.choices, blank=True)
    offensive_principles = models.TextField(blank=True)
    defensive_principles = models.TextField(blank=True)
    physical_demands_by_position = models.TextField(blank=True)
    tactical_demands_by_position = models.TextField(blank=True)
    creative_freedom = models.CharField(max_length=10, choices=CreativeFreedom.choices, blank=True)
    analyst_notes = models.TextField(blank=True)

    class Meta:
        db_table = "tactical_game_models"


class PositionCompetitor(models.Model):
    class SquadRole(models.TextChoices):
        STARTER = "starter", "Titular"
        BACKUP = "backup", "Reserva"
        ROTATION = "rotation", "Rotacao"
        PROSPECT = "prospect", "Promessa"

    class DominantFoot(models.TextChoices):
        RIGHT = "right", "Direito"
        LEFT = "left", "Esquerdo"
        BOTH = "both", "Ambos"

    class FitLevel(models.TextChoices):
        LOW = "low", "Baixa"
        MEDIUM = "medium", "Media"
        HIGH = "high", "Alta"

    class TrustLevel(models.TextChoices):
        LOW = "low", "Baixo"
        MEDIUM = "medium", "Medio"
        HIGH = "high", "Alto"

    class LeadershipLevel(models.TextChoices):
        LOW = "low", "Baixa"
        MEDIUM = "medium", "Media"
        HIGH = "high", "Alta"

    case = models.ForeignKey(CareerIntelligenceCase, on_delete=models.CASCADE, related_name="competitors")
    name = models.CharField(max_length=160)
    age = models.PositiveSmallIntegerField(null=True, blank=True)
    position = models.CharField(max_length=60)
    dominant_foot = models.CharField(max_length=10, choices=DominantFoot.choices, blank=True)
    squad_role = models.CharField(max_length=20, choices=SquadRole.choices, blank=True)
    starts = models.PositiveSmallIntegerField(default=0)
    minutes_played = models.PositiveIntegerField(default=0)
    hierarchy_order = models.PositiveSmallIntegerField(default=1)
    strengths = models.TextField(blank=True)
    weaknesses = models.TextField(blank=True)
    fit_to_game_model = models.CharField(max_length=10, choices=FitLevel.choices, blank=True)
    coach_trust_level = models.CharField(max_length=10, choices=TrustLevel.choices, blank=True)
    leadership_level = models.CharField(max_length=10, choices=LeadershipLevel.choices, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "position_competitors"
        ordering = ["hierarchy_order", "name", "id"]

    def __str__(self):
        return self.name


class CompetitorComparison(models.Model):
    class Criterion(models.TextChoices):
        TECHNICAL = "technical", "Tecnico"
        TACTICAL = "tactical", "Tatico"
        PHYSICAL = "physical", "Fisico"
        MENTAL = "mental", "Mental"
        BEHAVIORAL = "behavioral", "Comportamental"
        MATURITY = "maturity", "Maturidade competitiva"
        GAME_MODEL_FIT = "game_model_fit", "Adequacao ao modelo"
        COACH_TRUST = "coach_trust", "Confianca do treinador"

    class Rating(models.TextChoices):
        INFERIOR = "inferior", "Inferior"
        SIMILAR = "similar", "Similar"
        SUPERIOR = "superior", "Superior"

    case = models.ForeignKey(CareerIntelligenceCase, on_delete=models.CASCADE, related_name="comparisons")
    competitor = models.ForeignKey(PositionCompetitor, on_delete=models.CASCADE, related_name="comparisons")
    criterion = models.CharField(max_length=30, choices=Criterion.choices)
    rating = models.CharField(max_length=10, choices=Rating.choices)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "competitor_comparisons"
        ordering = ["competitor__hierarchy_order", "criterion", "id"]
        unique_together = ("competitor", "criterion")


class CompetitiveDiagnosis(models.Model):
    REASON_CHOICES = [
        ("technical_gap", "Inferioridade tecnica"),
        ("tactical_gap", "Inferioridade tatica"),
        ("physical_gap", "Inferioridade fisica"),
        ("intensity_gap", "Falta de intensidade"),
        ("low_maturity", "Baixa maturidade"),
        ("coach_prefers_experience", "Preferencia do treinador por experientes"),
        ("hierarchy", "Hierarquia consolidada"),
        ("game_model_fit", "Incompatibilidade com o modelo"),
        ("injury_return", "Retorno de lesao"),
        ("emotional", "Questoes emocionais"),
        ("few_opportunities", "Poucas oportunidades"),
        ("adaptation", "Adaptacao ao clube"),
        ("other", "Outros"),
    ]

    case = models.OneToOneField(CareerIntelligenceCase, on_delete=models.CASCADE, related_name="diagnosis")
    main_reason = models.CharField(max_length=40, choices=REASON_CHOICES)
    secondary_reasons = models.JSONField(default=list, blank=True)
    contextual_reasons = models.JSONField(default=list, blank=True)
    other_reason = models.CharField(max_length=255, blank=True)
    summary = models.TextField(blank=True)

    class Meta:
        db_table = "competitive_diagnoses"


class CareerPrognosis(models.Model):
    class Classification(models.TextChoices):
        HIGH_CHANCE = "high_chance", "Alta chance de se tornar titular"
        MODERATE = "moderate", "Chance moderada com desenvolvimento"
        CONTEXT = "context", "Dependente do contexto"
        HIERARCHY = "hierarchy", "Bloqueado por hierarquia"
        UNLIKELY_SHORT = "unlikely_short", "Curto prazo improvavel"
        CHANGE = "change", "Necessidade de mudanca de ambiente"

    class Timeframe(models.TextChoices):
        SHORT = "short", "Curto prazo"
        MEDIUM = "medium", "Medio prazo"
        LONG = "long", "Longo prazo"

    case = models.OneToOneField(CareerIntelligenceCase, on_delete=models.CASCADE, related_name="prognosis")
    classification = models.CharField(max_length=20, choices=Classification.choices)
    timeframe = models.CharField(max_length=10, choices=Timeframe.choices)
    justification = models.TextField()

    class Meta:
        db_table = "career_prognoses"


class IndividualDevelopmentPlan(models.Model):
    case = models.OneToOneField(CareerIntelligenceCase, on_delete=models.CASCADE, related_name="development_plan_v2")
    strengths_to_keep = models.TextField(blank=True)
    short_term_priorities = models.TextField(blank=True)
    medium_term_development = models.TextField(blank=True)
    contextual_factors = models.TextField(blank=True)
    mental_strategy = models.TextField(blank=True)
    practical_strategy = models.TextField(blank=True)
    priority_actions = models.JSONField(default=list, blank=True)
    template_name = models.CharField(max_length=120, blank=True)

    class Meta:
        db_table = "individual_development_plans"
