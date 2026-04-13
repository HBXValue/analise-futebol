from django.core.management.base import BaseCommand

from catalog.models import Country, Division


class Command(BaseCommand):
    help = "Cria/atualiza países e divisões principais do catálogo internacional."

    DIVISIONS = [
        {
            "country": {
                "code": "PRT",
                "name": "Portugal",
                "alternative_names": "Portuguese Republic",
            },
            "division": {
                "name": "Liga Portugal Betclic",
                "short_name": "Liga Portugal",
                "scope": Division.Scope.NATIONAL,
                "state": "",
                "level": 1,
                "alternative_names": "Primeira Liga, Liga Portugal",
                "is_active": True,
            },
        },
        {
            "country": {
                "code": "PRT",
                "name": "Portugal",
                "alternative_names": "Portuguese Republic",
            },
            "division": {
                "name": "Liga Portugal 2 Meu Super",
                "short_name": "Liga Portugal 2",
                "scope": Division.Scope.NATIONAL,
                "state": "",
                "level": 2,
                "alternative_names": "Segunda Liga, Liga Portugal Meu Super",
                "is_active": True,
            },
        },
        {
            "country": {
                "code": "ESP",
                "name": "Espanha",
                "alternative_names": "Spain, Reino de Espanha",
            },
            "division": {
                "name": "LALIGA EA SPORTS",
                "short_name": "LaLiga",
                "scope": Division.Scope.NATIONAL,
                "state": "",
                "level": 1,
                "alternative_names": "La Liga, Primera División",
                "is_active": True,
            },
        },
        {
            "country": {
                "code": "ESP",
                "name": "Espanha",
                "alternative_names": "Spain, Reino de Espanha",
            },
            "division": {
                "name": "LALIGA HYPERMOTION",
                "short_name": "Segunda Division",
                "scope": Division.Scope.NATIONAL,
                "state": "",
                "level": 2,
                "alternative_names": "LaLiga Hypermotion, Segunda División",
                "is_active": True,
            },
        },
        {
            "country": {
                "code": "ITA",
                "name": "Itália",
                "alternative_names": "Italy, Repubblica Italiana",
            },
            "division": {
                "name": "Serie A Enilive",
                "short_name": "Serie A",
                "scope": Division.Scope.NATIONAL,
                "state": "",
                "level": 1,
                "alternative_names": "Serie A",
                "is_active": True,
            },
        },
        {
            "country": {
                "code": "ITA",
                "name": "Itália",
                "alternative_names": "Italy, Repubblica Italiana",
            },
            "division": {
                "name": "Serie BKT",
                "short_name": "Serie B",
                "scope": Division.Scope.NATIONAL,
                "state": "",
                "level": 2,
                "alternative_names": "Serie B",
                "is_active": True,
            },
        },
        {
            "country": {
                "code": "FRA",
                "name": "França",
                "alternative_names": "France, République française",
            },
            "division": {
                "name": "Ligue 1 McDonald's",
                "short_name": "Ligue 1",
                "scope": Division.Scope.NATIONAL,
                "state": "",
                "level": 1,
                "alternative_names": "Ligue 1",
                "is_active": True,
            },
        },
        {
            "country": {
                "code": "FRA",
                "name": "França",
                "alternative_names": "France, République française",
            },
            "division": {
                "name": "Ligue 2 BKT",
                "short_name": "Ligue 2",
                "scope": Division.Scope.NATIONAL,
                "state": "",
                "level": 2,
                "alternative_names": "Ligue 2",
                "is_active": True,
            },
        },
        {
            "country": {
                "code": "DEU",
                "name": "Alemanha",
                "alternative_names": "Germany, Deutschland",
            },
            "division": {
                "name": "Bundesliga",
                "short_name": "Bundesliga",
                "scope": Division.Scope.NATIONAL,
                "state": "",
                "level": 1,
                "alternative_names": "1. Bundesliga",
                "is_active": True,
            },
        },
        {
            "country": {
                "code": "DEU",
                "name": "Alemanha",
                "alternative_names": "Germany, Deutschland",
            },
            "division": {
                "name": "2. Bundesliga",
                "short_name": "2. Bundesliga",
                "scope": Division.Scope.NATIONAL,
                "state": "",
                "level": 2,
                "alternative_names": "Bundesliga 2",
                "is_active": True,
            },
        },
        {
            "country": {
                "code": "ENG",
                "name": "Inglaterra",
                "alternative_names": "England",
            },
            "division": {
                "name": "Premier League",
                "short_name": "Premier League",
                "scope": Division.Scope.NATIONAL,
                "state": "",
                "level": 1,
                "alternative_names": "English Premier League, EPL",
                "is_active": True,
            },
        },
        {
            "country": {
                "code": "ENG",
                "name": "Inglaterra",
                "alternative_names": "England",
            },
            "division": {
                "name": "EFL Championship",
                "short_name": "Championship",
                "scope": Division.Scope.NATIONAL,
                "state": "",
                "level": 2,
                "alternative_names": "Sky Bet Championship, Championship",
                "is_active": True,
            },
        },
        {
            "country": {
                "code": "SAU",
                "name": "Arábia Saudita",
                "alternative_names": "Saudi Arabia, Kingdom of Saudi Arabia",
            },
            "division": {
                "name": "Saudi Pro League",
                "short_name": "Saudi Pro League",
                "scope": Division.Scope.NATIONAL,
                "state": "",
                "level": 1,
                "alternative_names": "Roshn Saudi League, SPL",
                "is_active": True,
            },
        },
        {
            "country": {
                "code": "USA",
                "name": "Estados Unidos",
                "alternative_names": "United States, United States of America, USA",
            },
            "division": {
                "name": "Major League Soccer",
                "short_name": "MLS",
                "scope": Division.Scope.NATIONAL,
                "state": "",
                "level": 1,
                "alternative_names": "MLS, Major League Soccer",
                "is_active": True,
            },
        },
        {
            "country": {
                "code": "ARG",
                "name": "Argentina",
                "alternative_names": "Argentine Republic, República Argentina",
            },
            "division": {
                "name": "Liga Profesional de Fútbol",
                "short_name": "Liga Profesional",
                "scope": Division.Scope.NATIONAL,
                "state": "",
                "level": 1,
                "alternative_names": "LPF, Primera División Argentina",
                "is_active": True,
            },
        },
        {
            "country": {
                "code": "MEX",
                "name": "México",
                "alternative_names": "Mexico, Estados Unidos Mexicanos",
            },
            "division": {
                "name": "Liga BBVA MX",
                "short_name": "Liga MX",
                "scope": Division.Scope.NATIONAL,
                "state": "",
                "level": 1,
                "alternative_names": "Liga MX, Primera División de México",
                "is_active": True,
            },
        },
        {
            "country": {
                "code": "NLD",
                "name": "Holanda",
                "alternative_names": "Netherlands, Nederland, Países Baixos",
            },
            "division": {
                "name": "Eredivisie",
                "short_name": "Eredivisie",
                "scope": Division.Scope.NATIONAL,
                "state": "",
                "level": 1,
                "alternative_names": "Dutch Eredivisie",
                "is_active": True,
            },
        },
    ]

    def handle(self, *args, **options):
        country_count = 0
        division_count = 0

        for item in self.DIVISIONS:
            country_defaults = {
                "name": item["country"]["name"],
                "alternative_names": item["country"]["alternative_names"],
                "is_active": True,
            }
            country, country_created = Country.objects.update_or_create(
                code=item["country"]["code"],
                defaults=country_defaults,
            )
            country_count += int(country_created)

            _, division_created = Division.objects.update_or_create(
                country=country,
                scope=item["division"]["scope"],
                state=item["division"]["state"],
                name=item["division"]["name"],
                defaults={
                    "short_name": item["division"]["short_name"],
                    "level": item["division"]["level"],
                    "alternative_names": item["division"]["alternative_names"],
                    "is_active": item["division"]["is_active"],
                },
            )
            division_count += int(division_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Carga europeia concluída. {country_count} países criados/confirmados e {division_count} divisões criadas/confirmadas."
            )
        )
