from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("valuation", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlayerHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("performance_score", models.FloatField(default=0)),
                ("market_score", models.FloatField(default=0)),
                ("marketing_score", models.FloatField(default=0)),
                ("behavior_score", models.FloatField(default=0)),
                ("valuation_score", models.FloatField(default=0)),
                ("current_value", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("player", models.ForeignKey(db_column="player_id", on_delete=django.db.models.deletion.CASCADE, related_name="history", to="valuation.player")),
            ],
            options={
                "db_table": "player_history",
                "ordering": ["date", "id"],
            },
        ),
    ]
