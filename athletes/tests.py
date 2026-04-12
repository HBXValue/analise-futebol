import tempfile
from datetime import date

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from athletes.models import Athlete, AthleteClubHistory
from catalog.models import Country, Division
from clubs.models import Club


class AthleteModelTests(TestCase):
    def setUp(self):
        self.country = Country.objects.create(name="Pais de Teste", code="TST")
        self.division = Division.objects.create(
            country=self.country,
            name="Serie A",
            short_name="A",
            level=1,
        )
        self.club = Club.objects.create(
            country=self.country,
            division=self.division,
            official_name="Santos Futebol Clube",
            short_name="Santos",
        )
        self.athlete = Athlete.objects.create(
            full_name="Neymar da Silva Santos Junior",
            sport_name="Neymar",
            nationality=self.country,
            primary_position="Atacante",
            current_club=self.club,
        )

    def test_athlete_slug_is_auto_generated(self):
        self.assertEqual(self.athlete.slug, "neymar")

    def test_history_end_date_cannot_be_before_start_date(self):
        history = AthleteClubHistory(
            athlete=self.athlete,
            club=self.club,
            start_date=date(2024, 1, 1),
            end_date=date(2023, 1, 1),
        )

        with self.assertRaises(ValidationError):
            history.clean()

    def test_current_history_cannot_have_end_date(self):
        history = AthleteClubHistory(
            athlete=self.athlete,
            club=self.club,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            is_current=True,
        )

        with self.assertRaises(ValidationError):
            history.clean()


class AthleteImportCommandTests(TestCase):
    def setUp(self):
        self.country = Country.objects.get(code="BRA")
        self.division = Division.objects.get(country=self.country, level=1)
        self.club = Club.objects.create(
            country=self.country,
            division=self.division,
            official_name="Clube de Teste",
            short_name="Teste",
        )

    def test_import_athletes_csv_creates_athlete_and_history(self):
        csv_content = (
            "full_name,sport_name,nationality_code,primary_position,secondary_positions,dominant_foot,"
            "birth_date,height_cm,weight_kg,current_club_name,club_country_code,club_division_level,status,"
            "notes,history_start_date,history_end_date,history_shirt_number,history_is_current,history_notes\n"
            "Atleta de Teste,Teste,BRA,Meia,Volante,right,1998-02-10,177,70,Clube de Teste,BRA,1,active,"
            "Importado,2024-01-01,,8,true,Primeiro vinculo\n"
        )

        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as temp_file:
            temp_file.write(csv_content)
            csv_path = temp_file.name

        call_command("import_athletes_csv", csv_path)

        athlete = Athlete.objects.get(full_name="Atleta de Teste")
        history = AthleteClubHistory.objects.get(athlete=athlete, club=self.club)
        self.assertEqual(athlete.current_club, self.club)
        self.assertEqual(athlete.primary_position, "Meia")
        self.assertTrue(history.is_current)
        self.assertEqual(history.shirt_number, 8)


class AthleteQuickImportCommandTests(TestCase):
    def setUp(self):
        self.country = Country.objects.get(code="BRA")
        self.division = Division.objects.get(country=self.country, level=1)
        Club.objects.create(
            country=self.country,
            division=self.division,
            official_name="Clube de Regatas do Flamengo",
            short_name="Flamengo",
        )

    def test_import_athletes_quick_csv_creates_athlete(self):
        csv_content = (
            "full_name,sport_name,current_club_name,club_division_level,notes\n"
            "Jogador Rapido,JR,Flamengo,1,Importado rapido\n"
        )

        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as temp_file:
            temp_file.write(csv_content)
            csv_path = temp_file.name

        call_command("import_athletes_quick_csv", csv_path)

        athlete = Athlete.objects.get(full_name="Jogador Rapido")
        self.assertEqual(athlete.current_club.short_name, "Flamengo")
        self.assertEqual(athlete.primary_position, "Nao informado")
