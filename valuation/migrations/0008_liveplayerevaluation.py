from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("valuation", "0007_backfill_live_analysis_sessions"),
    ]

    operations = [
        migrations.CreateModel(
            name="LivePlayerEvaluation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("athlete_name", models.CharField(max_length=160)),
                ("shirt_number", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("position", models.CharField(max_length=60)),
                ("team", models.CharField(max_length=160)),
                ("opponent", models.CharField(max_length=160)),
                ("competition", models.CharField(max_length=160)),
                ("match_date", models.DateField()),
                ("analyst_name", models.CharField(max_length=160)),
                ("minutes_played", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("physical_data_source", models.CharField(default="manual", max_length=20)),
                ("payload", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("saved_at", models.DateTimeField(auto_now=True)),
                ("player", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="live_player_evaluations", to="valuation.player")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="live_player_evaluations", to="valuation.user")),
            ],
            options={
                "db_table": "live_player_evaluations",
                "ordering": ["-match_date", "-saved_at", "-id"],
            },
        ),
    ]
