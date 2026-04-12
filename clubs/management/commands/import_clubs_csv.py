import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from catalog.models import Country, Division
from clubs.models import Club


class Command(BaseCommand):
    help = "Importa clubes a partir de um arquivo CSV."

    required_columns = {
        "country_code",
        "division_level",
        "official_name",
        "short_name",
        "state",
        "city",
        "founded_year",
        "badge_url",
        "status",
        "notes",
    }

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Caminho do arquivo CSV de clubes.")

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"]).expanduser()
        if not csv_path.exists():
            raise CommandError(f"Arquivo não encontrado: {csv_path}")

        with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            sample = csv_file.read(2048)
            csv_file.seek(0)
            dialect = csv.Sniffer().sniff(sample, delimiters=",;")
            reader = csv.DictReader(csv_file, dialect=dialect)

            if not reader.fieldnames:
                raise CommandError("O CSV está vazio ou sem cabeçalho.")

            missing_columns = self.required_columns - set(reader.fieldnames)
            if missing_columns:
                missing = ", ".join(sorted(missing_columns))
                raise CommandError(f"Colunas obrigatórias ausentes: {missing}")

            created_count = 0
            updated_count = 0

            for row_number, row in enumerate(reader, start=2):
                if not row["official_name"].strip():
                    self.stdout.write(self.style.WARNING(f"Linha {row_number}: nome oficial vazio, ignorada."))
                    continue

                country = self.get_country(row["country_code"], row_number)
                division = self.get_division(country, row["division_level"], row_number)

                defaults = {
                    "country": country,
                    "short_name": row["short_name"].strip(),
                    "state": row["state"].strip(),
                    "city": row["city"].strip(),
                    "founded_year": self.parse_optional_int(row["founded_year"], row_number, "founded_year"),
                    "badge_url": row["badge_url"].strip(),
                    "status": self.parse_status(row["status"].strip() or Club.Status.ACTIVE, row_number),
                    "notes": row["notes"].strip(),
                }

                club, created = Club.objects.update_or_create(
                    division=division,
                    official_name=row["official_name"].strip(),
                    defaults=defaults,
                )
                club.full_clean()
                club.save()

                created_count += int(created)
                updated_count += int(not created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Importação concluída: {created_count} clubes criados, {updated_count} clubes atualizados."
            )
        )

    def get_country(self, country_code, row_number):
        code = country_code.strip().upper()
        try:
            return Country.objects.get(code=code)
        except Country.DoesNotExist as exc:
            raise CommandError(f"Linha {row_number}: país '{code}' não encontrado.") from exc

    def get_division(self, country, division_level, row_number):
        try:
            level = int(division_level)
        except ValueError as exc:
            raise CommandError(f"Linha {row_number}: division_level inválido '{division_level}'.") from exc

        try:
            return Division.objects.get(country=country, level=level)
        except Division.DoesNotExist as exc:
            raise CommandError(
                f"Linha {row_number}: divisão de nível {level} não encontrada para {country.code}."
            ) from exc

    def parse_optional_int(self, value, row_number, field_name):
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return int(cleaned)
        except ValueError as exc:
            raise CommandError(f"Linha {row_number}: {field_name} inválido '{value}'.") from exc

    def parse_status(self, value, row_number):
        valid_statuses = {choice for choice, _ in Club.Status.choices}
        if value not in valid_statuses:
            allowed = ", ".join(sorted(valid_statuses))
            raise CommandError(f"Linha {row_number}: status '{value}' inválido. Use: {allowed}.")
        return value
