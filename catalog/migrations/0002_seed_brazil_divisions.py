from django.db import migrations


def seed_brazil_divisions(apps, schema_editor):
    country_model = apps.get_model("catalog", "Country")
    division_model = apps.get_model("catalog", "Division")

    brazil, _ = country_model.objects.get_or_create(
        code="BRA",
        defaults={
            "name": "Brasil",
            "slug": "brasil",
            "alternative_names": "Brazil",
            "is_active": True,
        },
    )

    divisions = [
        {
            "name": "Campeonato Brasileiro Serie A",
            "short_name": "Serie A",
            "level": 1,
            "slug": "campeonato-brasileiro-serie-a",
        },
        {
            "name": "Campeonato Brasileiro Serie B",
            "short_name": "Serie B",
            "level": 2,
            "slug": "campeonato-brasileiro-serie-b",
        },
        {
            "name": "Campeonato Brasileiro Serie C",
            "short_name": "Serie C",
            "level": 3,
            "slug": "campeonato-brasileiro-serie-c",
        },
        {
            "name": "Campeonato Brasileiro Serie D",
            "short_name": "Serie D",
            "level": 4,
            "slug": "campeonato-brasileiro-serie-d",
        },
    ]

    for division in divisions:
        division_model.objects.get_or_create(
            country=brazil,
            level=division["level"],
            defaults={
                "name": division["name"],
                "short_name": division["short_name"],
                "slug": division["slug"],
                "is_active": True,
            },
        )


def unseed_brazil_divisions(apps, schema_editor):
    country_model = apps.get_model("catalog", "Country")
    division_model = apps.get_model("catalog", "Division")

    division_model.objects.filter(country__code="BRA", level__in=[1, 2, 3, 4]).delete()
    country_model.objects.filter(code="BRA").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_brazil_divisions, unseed_brazil_divisions),
    ]
