from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("valuation", "0003_intervention_models"),
    ]

    operations = [
        migrations.CreateModel(
            name="OnBallEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("pressure_status", models.CharField(choices=[("under_pressure", "Under pressure"), ("no_pressure", "No pressure")], max_length=20)),
                ("field_zone", models.CharField(blank=True, choices=[("defense", "Defense"), ("midfield", "Midfield"), ("attack", "Attack")], max_length=20)),
                ("action_type", models.CharField(choices=[("pass", "Pass"), ("dribble", "Dribble"), ("shot", "Shot"), ("carry", "Carry"), ("turnover", "Turnover")], max_length=20)),
                ("outcome", models.CharField(choices=[("positive", "Positive"), ("negative", "Negative")], max_length=20)),
                ("notes", models.TextField(blank=True)),
                ("player", models.ForeignKey(db_column="player_id", on_delete=django.db.models.deletion.CASCADE, related_name="on_ball_events", to="valuation.player")),
            ],
            options={"db_table": "on_ball_events", "ordering": ["-date", "-id"]},
        ),
    ]
