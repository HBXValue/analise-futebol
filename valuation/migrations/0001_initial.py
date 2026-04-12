from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="User",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("password_hash", models.CharField(max_length=255)),
            ],
            options={"db_table": "users", "ordering": ["email"]},
        ),
        migrations.CreateModel(
            name="Player",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                ("age", models.PositiveSmallIntegerField()),
                ("position", models.CharField(max_length=60)),
                ("current_value", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("league_level", models.CharField(max_length=80)),
                ("club_origin", models.CharField(max_length=160)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="players", to="valuation.user")),
            ],
            options={"db_table": "players", "ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="PerformanceMetrics",
            fields=[
                ("player", models.OneToOneField(db_column="player_id", on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name="performance_metrics", serialize=False, to="valuation.player")),
                ("xg", models.FloatField(default=0)),
                ("xa", models.FloatField(default=0)),
                ("passes_pct", models.FloatField(default=0)),
                ("dribbles_pct", models.FloatField(default=0)),
                ("tackles_pct", models.FloatField(default=0)),
                ("high_intensity_distance", models.FloatField(default=0)),
                ("final_third_recoveries", models.FloatField(default=0)),
            ],
            options={"db_table": "performance_metrics"},
        ),
        migrations.CreateModel(
            name="MarketMetrics",
            fields=[
                ("player", models.OneToOneField(db_column="player_id", on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name="market_metrics", serialize=False, to="valuation.player")),
                ("annual_growth", models.FloatField(default=0)),
                ("club_interest", models.FloatField(default=0)),
                ("league_score", models.FloatField(default=0)),
                ("age_factor", models.FloatField(default=0)),
                ("club_reputation", models.FloatField(default=0)),
            ],
            options={"db_table": "market_metrics"},
        ),
        migrations.CreateModel(
            name="MarketingMetrics",
            fields=[
                ("player", models.OneToOneField(db_column="player_id", on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name="marketing_metrics", serialize=False, to="valuation.player")),
                ("followers", models.FloatField(default=0)),
                ("engagement", models.FloatField(default=0)),
                ("media_mentions", models.FloatField(default=0)),
                ("sponsorships", models.FloatField(default=0)),
                ("sentiment_score", models.FloatField(default=0)),
            ],
            options={"db_table": "marketing_metrics"},
        ),
        migrations.CreateModel(
            name="BehaviorMetrics",
            fields=[
                ("player", models.OneToOneField(db_column="player_id", on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name="behavior_metrics", serialize=False, to="valuation.player")),
                ("conscientiousness", models.FloatField(default=0)),
                ("adaptability", models.FloatField(default=0)),
                ("resilience", models.FloatField(default=0)),
                ("deliberate_practice", models.FloatField(default=0)),
                ("executive_function", models.FloatField(default=0)),
                ("leadership", models.FloatField(default=0)),
            ],
            options={"db_table": "behavior_metrics"},
        ),
    ]
