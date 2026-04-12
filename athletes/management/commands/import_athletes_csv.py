import csv
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from athletes.models import Athlete, AthleteClubHistory
from catalog.models import Country, Division
from clubs.models import Club


class Command(BaseCommand):
    help = "Importa atletas a partir de um arquivo CSV."

    required_columns = {
        "full_name",
        "sport_name",
        "nationality_code",
        "primary_position",
        "secondary_positions",
        "dominant_foot",
        "birth_date",
        "height_cm",
        "weight_kg",
        "current_club_name",
        "club_country_code",
        "club_division_level",
        "status",
        "notes",
        "history_start_date",
        "history_end_date",
        "history_shirt_number",
        "history_is_current",
        "history_notes",
    }

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Caminho do arquivo CSV de atletas.")

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
            history_count = 0

            for row_number, row in enumerate(reader, start=2):
                if not row["full_name"].strip():
                    self.stdout.write(self.style.WARNING(f"Linha {row_number}: full_name vazio, ignorada."))
                    continue

                nationality = self.get_country(row["nationality_code"], row_number, "nationality_code")
                current_club = self.get_club(
                    row["club_country_code"],
                    row["club_division_level"],
                    row["current_club_name"],
                    row_number,
                )

                athlete_defaults = {
                    "sport_name": row["sport_name"].strip(),
                    "nationality": nationality,
                    "primary_position": row["primary_position"].strip(),
                    "secondary_positions": row["secondary_positions"].strip(),
                    "dominant_foot": self.parse_dominant_foot(row["dominant_foot"].strip(), row_number),
                    "birth_date": self.parse_optional_date(row["birth_date"], row_number, "birth_date"),
                    "height_cm": self.parse_optional_int(row["height_cm"], row_number, "height_cm"),
                    "weight_kg": self.parse_optional_int(row["weight_kg"], row_number, "weight_kg"),
                    "current_club": current_club,
                    "status": self.parse_status(row["status"].strip() or Athlete.Status.ACTIVE, row_number),
                    "notes": row["notes"].strip(),
                }

                athlete, created = Athlete.objects.update_or_create(
                    full_name=row["full_name"].strip(),
                    defaults=athlete_defaults,
                )
                athlete.full_clean()
                athlete.save()

                created_count += int(created)
                updated_count += int(not created)

                if row["history_start_date"].strip():
                    history_defaults = {
                        "end_date": self.parse_optional_date(
                            row["history_end_date"],
                            row_number,
                            "history_end_date",
                        ),
                        "shirt_number": self.parse_optional_int(
                            row["history_shirt_number"],
                            row_number,
                            "history_shirt_number",
                        ),
                        "is_current": self.parse_bool(row["history_is_current"]),
                        "notes": row["history_notes"].strip(),
                    }
                    history, _ = AthleteClubHistory.objects.update_or_create(
                        athlete=athlete,
                        club=current_club,
                        start_date=self.parse_optional_date(
                            row["history_start_date"],
                            row_number,
                            "history_start_date",
                        ),
                        defaults=history_defaults,
                    )
                    history.full_clean()
                    history.save()
                    history_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Importação concluída: {created_count} atletas criados, {updated_count} atletas atualizados, "
                f"{history_count} vínculos processados."
            )
        )

    def get_country(self, country_code, row_number, field_name):
        code = country_code.strip().upper()
        try:
            return Country.objects.get(code=code)
        except Country.DoesNotExist as exc:
            raise CommandError(f"Linha {row_number}: país '{code}' em {field_name} não encontrado.") from exc

    def get_division(self, country, division_level, row_number):
        try:
            level = int(division_level)
        except ValueError as exc:
            raise CommandError(f"Linha {row_number}: club_division_level inválido '{division_level}'.") from exc

        try:
            return Division.objects.get(country=country, level=level)
        except Division.DoesNotExist as exc:
            raise CommandError(
                f"Linha {row_number}: divisão de nível {level} não encontrada para {country.code}."
            ) from exc

    def get_club(self, country_code, division_level, club_name, row_number):
        if not club_name.strip():
            return None

        country = self.get_country(country_code, row_number, "club_country_code")
        division = self.get_division(country, division_level, row_number)

        try:
            return Club.objects.get(division=division, official_name=club_name.strip())
        except Club.DoesNotExist:
            try:
                return Club.objects.get(division=division, short_name=club_name.strip())
            except Club.DoesNotExist as exc:
                raise CommandError(
                    f"Linha {row_number}: clube '{club_name}' não encontrado na divisão {division.short_name or division.name}."
                ) from exc

    def parse_optional_int(self, value, row_number, field_name):
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return int(cleaned)
        except ValueError as exc:
            raise CommandError(f"Linha {row_number}: {field_name} inválido '{value}'.") from exc

    def parse_optional_date(self, value, row_number, field_name):
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return date.fromisoformat(cleaned)
        except ValueError as exc:
            raise CommandError(f"Linha {row_number}: {field_name} inválido '{value}'. Use AAAA-MM-DD.") from exc

    def parse_bool(self, value):
        return value.strip().lower() in {"1", "true", "sim", "yes", "y"}

    def parse_dominant_foot(self, value, row_number):
        if not value:
            return ""
        valid_values = {choice for choice, _ in Athlete.Foot.choices}
        if value not in valid_values:
            allowed = ", ".join(sorted(valid_values))
            raise CommandError(f"Linha {row_number}: dominant_foot '{value}' inválido. Use: {allowed}.")
        return value

    def parse_status(self, value, row_number):
        valid_statuses = {choice for choice, _ in Athlete.Status.choices}
        if value not in valid_statuses:
            allowed = ", ".join(sorted(valid_statuses))
            raise CommandError(f"Linha {row_number}: status '{value}' inválido. Use: {allowed}.")
        return value
