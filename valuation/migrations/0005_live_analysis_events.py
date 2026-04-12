from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("valuation", "0004_on_ball_events"),
    ]

    operations = [
        migrations.CreateModel(
            name="LiveAnalysisEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField()),
                ("event_type", models.CharField(choices=[("received", "Received"), ("controlled", "Controlled"), ("forward_pass", "Forward pass"), ("backward_pass", "Backward pass"), ("progressed", "Progressed with ball"), ("cross", "Cross"), ("shot", "Shot"), ("goal", "Goal"), ("dispossessed", "Dispossessed"), ("tackle_won", "Tackle won")], max_length=30)),
                ("duration_seconds", models.FloatField(default=0)),
                ("points", models.FloatField(default=0)),
                ("notes", models.CharField(blank=True, max_length=255)),
                ("player", models.ForeignKey(db_column="player_id", on_delete=django.db.models.deletion.CASCADE, related_name="live_analysis_events", to="valuation.player")),
            ],
            options={"db_table": "live_analysis_events", "ordering": ["-created_at", "-id"]},
        ),
    ]
