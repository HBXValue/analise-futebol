from django.core.management.base import BaseCommand

from catalog.models import Country, Division


class Command(BaseCommand):
    help = "Cria os dados iniciais do Brasil com as Séries A, B, C e D."

    def handle(self, *args, **options):
        brazil, country_created = Country.objects.get_or_create(
            code="BRA",
            defaults={
                "name": "Brasil",
                "alternative_names": "Brazil",
                "is_active": True,
            },
        )

        divisions = [
            {
                "name": "Campeonato Brasileiro Série A",
                "short_name": "Série A",
                "level": 1,
                "scope": Division.Scope.NATIONAL,
                "alternative_names": "Campeonato Brasileiro Serie A,Brasileirão Série A,Brasileirao Serie A,Serie A",
            },
            {
                "name": "Campeonato Brasileiro Série B",
                "short_name": "Série B",
                "level": 2,
                "scope": Division.Scope.NATIONAL,
                "alternative_names": "Campeonato Brasileiro Serie B,Brasileirão Série B,Brasileirao Serie B,Serie B",
            },
            {
                "name": "Campeonato Brasileiro Série C",
                "short_name": "Série C",
                "level": 3,
                "scope": Division.Scope.NATIONAL,
                "alternative_names": "Campeonato Brasileiro Serie C,Brasileirão Série C,Brasileirao Serie C,Serie C",
            },
            {
                "name": "Campeonato Brasileiro Série D",
                "short_name": "Série D",
                "level": 4,
                "scope": Division.Scope.NATIONAL,
                "alternative_names": "Campeonato Brasileiro Serie D,Brasileirão Série D,Brasileirao Serie D,Serie D",
            },
        ]

        created_count = 0
        for division_data in divisions:
            division = (
                Division.objects.filter(
                    country=brazil,
                    scope=division_data["scope"],
                    state="",
                    name=division_data["name"],
                ).first()
                or Division.objects.filter(
                    country=brazil,
                    scope=division_data["scope"],
                    state="",
                    level=division_data["level"],
                ).first()
            )
            created = False
            if division is None:
                division = Division.objects.create(country=brazil, state="", is_active=True, **division_data)
                created = True
            else:
                updated = False
                for field_name in ("name", "short_name", "level", "alternative_names", "scope", "is_active"):
                    field_value = division_data.get(field_name, getattr(division, field_name))
                    if getattr(division, field_name) != field_value:
                        setattr(division, field_name, field_value)
                        updated = True
                if updated:
                    division.save()
            created_count += int(created)

        if country_created:
            self.stdout.write(self.style.SUCCESS("País Brasil criado com sucesso."))

        self.stdout.write(
            self.style.SUCCESS(
                f"Carga inicial concluída. {created_count} divisões criadas/confirmadas para o Brasil."
            )
        )
