from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("valuation", "0016_athleteaiinsight"),
    ]

    operations = [
        migrations.AddField(
            model_name="athleteaiinsight",
            name="scope",
            field=models.CharField(
                choices=[
                    ("dashboard", "Dashboard"),
                    ("market", "Market Intelligence"),
                    ("performance", "Performance Intelligence"),
                    ("reports", "Reports"),
                ],
                default="dashboard",
                max_length=20,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="athleteaiinsight",
            unique_together={("player", "scope", "window_days", "language", "prompt_version")},
        ),
    ]
