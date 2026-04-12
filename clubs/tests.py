import tempfile

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase

from catalog.models import Country, Division
from clubs.models import Club


class ClubModelTests(TestCase):
    def setUp(self):
        self.country = Country.objects.create(name="Pais de Teste", code="TST")
        self.other_country = Country.objects.create(name="Outro Pais", code="OTP")
        self.division = Division.objects.create(
            country=self.country,
            name="Serie A",
            short_name="A",
            level=1,
        )

    def test_club_cannot_use_division_from_different_country(self):
        club = Club(
            country=self.other_country,
            division=self.division,
            official_name="Clube Invalido",
        )

        with self.assertRaises(ValidationError):
            club.clean()

    def test_club_name_must_be_unique_within_division(self):
        Club.objects.create(
            country=self.country,
            division=self.division,
            official_name="Flamengo",
            short_name="FLA",
        )

        with self.assertRaises(IntegrityError):
            Club.objects.create(
                country=self.country,
                division=self.division,
                official_name="Flamengo",
                short_name="FLA 2",
            )


class ClubImportCommandTests(TestCase):
    def test_import_clubs_csv_creates_records(self):
        csv_content = (
            "country_code,division_level,official_name,short_name,state,city,founded_year,badge_url,status,notes\n"
            "BRA,1,Fortaleza Esporte Clube,Fortaleza,Ceara,Fortaleza,1918,,active,Importado por teste\n"
        )

        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as temp_file:
            temp_file.write(csv_content)
            csv_path = temp_file.name

        call_command("import_clubs_csv", csv_path)

        club = Club.objects.get(official_name="Fortaleza Esporte Clube")
        self.assertEqual(club.division.level, 1)
        self.assertEqual(club.country.code, "BRA")
        self.assertEqual(club.city, "Fortaleza")
