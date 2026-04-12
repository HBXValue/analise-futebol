from django.db import IntegrityError
from django.test import TestCase

from catalog.models import Country, Division


class CatalogModelTests(TestCase):
    def setUp(self):
        self.country = Country.objects.create(name="Pais de Teste", code="TST")

    def test_country_slug_is_auto_generated(self):
        self.assertEqual(self.country.slug, "pais-de-teste")

    def test_division_name_must_be_unique_per_country(self):
        Division.objects.create(country=self.country, name="Serie A", short_name="A", level=1)

        with self.assertRaises(IntegrityError):
            Division.objects.create(country=self.country, name="Serie A", short_name="A1", level=2)

    def test_division_level_must_be_unique_per_country(self):
        Division.objects.create(country=self.country, name="Serie A", short_name="A", level=1)

        with self.assertRaises(IntegrityError):
            Division.objects.create(country=self.country, name="Serie Especial", short_name="SE", level=1)
