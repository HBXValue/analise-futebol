from decimal import Decimal

from django.db import models


class User(models.Model):
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255)

    class Meta:
        db_table = "users"
        ordering = ["email"]

    def __str__(self):
        return self.email


class Player(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="players")
    name = models.CharField(max_length=160)
    age = models.PositiveSmallIntegerField()
    position = models.CharField(max_length=60)
    current_value = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    league_level = models.CharField(max_length=80)
    club_origin = models.CharField(max_length=160)

    class Meta:
        db_table = "players"
        ordering = ["name"]

    def __str__(self):
        return self.name


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
