from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("valuation", "0015_player_training_environment_score_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="AthleteAIInsight",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("window_days", models.PositiveSmallIntegerField(default=90)),
                ("language", models.CharField(default="pt", max_length=10)),
                ("prompt_version", models.CharField(default="v1", max_length=20)),
                ("model_name", models.CharField(blank=True, max_length=80)),
                ("status_label", models.CharField(blank=True, max_length=80)),
                ("executive_summary", models.TextField(blank=True)),
                ("main_change", models.TextField(blank=True)),
                ("main_risk", models.TextField(blank=True)),
                ("main_opportunity", models.TextField(blank=True)),
                ("recommended_action", models.TextField(blank=True)),
                ("confidence", models.FloatField(default=0)),
                ("dashboard_cards", models.JSONField(blank=True, default=list)),
                ("payload_snapshot", models.JSONField(blank=True, default=dict)),
                ("raw_response", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("player", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="ai_insights", to="valuation.player")),
            ],
            options={
                "db_table": "athlete_ai_insights",
                "ordering": ["-updated_at", "-id"],
                "unique_together": {("player", "window_days", "language", "prompt_version")},
            },
        ),
    ]
