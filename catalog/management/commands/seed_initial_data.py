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
            {"name": "Campeonato Brasileiro Serie A", "short_name": "Serie A", "level": 1},
            {"name": "Campeonato Brasileiro Serie B", "short_name": "Serie B", "level": 2},
            {"name": "Campeonato Brasileiro Serie C", "short_name": "Serie C", "level": 3},
            {"name": "Campeonato Brasileiro Serie D", "short_name": "Serie D", "level": 4},
        ]

        created_count = 0
        for division_data in divisions:
            _, created = Division.objects.get_or_create(
                country=brazil,
                level=division_data["level"],
                defaults=division_data,
            )
            created_count += int(created)

        if country_created:
            self.stdout.write(self.style.SUCCESS("País Brasil criado com sucesso."))

        self.stdout.write(
            self.style.SUCCESS(
                f"Carga inicial concluída. {created_count} divisões criadas/confirmadas para o Brasil."
            )
        )
