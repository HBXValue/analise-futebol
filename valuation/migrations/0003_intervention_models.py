from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("valuation", "0002_playerhistory"),
    ]

    operations = [
        migrations.CreateModel(
            name="AnalystNote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("analysis_text", models.TextField()),
                ("strengths", models.TextField(blank=True)),
                ("weaknesses", models.TextField(blank=True)),
                ("player", models.ForeignKey(db_column="player_id", on_delete=django.db.models.deletion.CASCADE, related_name="analyst_notes", to="valuation.player")),
            ],
            options={"db_table": "analyst_notes", "ordering": ["-date", "-id"]},
        ),
        migrations.CreateModel(
            name="DevelopmentPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("goal", models.CharField(max_length=255)),
                ("target_metric", models.CharField(max_length=80)),
                ("target_value", models.FloatField()),
                ("deadline", models.DateField()),
                ("player", models.ForeignKey(db_column="player_id", on_delete=django.db.models.deletion.CASCADE, related_name="development_plans", to="valuation.player")),
            ],
            options={"db_table": "development_plan", "ordering": ["deadline", "id"]},
        ),
        migrations.CreateModel(
            name="ProgressTracking",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("metric", models.CharField(max_length=80)),
                ("current_value", models.FloatField()),
                ("target_value", models.FloatField()),
                ("progress_pct", models.FloatField(default=0)),
                ("player", models.ForeignKey(db_column="player_id", on_delete=django.db.models.deletion.CASCADE, related_name="progress_tracking", to="valuation.player")),
            ],
            options={"db_table": "progress_tracking", "ordering": ["metric", "id"]},
        ),
    ]
