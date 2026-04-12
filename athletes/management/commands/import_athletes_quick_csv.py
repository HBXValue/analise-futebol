import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from athletes.models import Athlete
from catalog.models import Country, Division
from clubs.models import Club


class Command(BaseCommand):
    help = "Importa atletas de forma simplificada a partir de um CSV."

    required_columns = {
        "full_name",
        "sport_name",
        "current_club_name",
        "club_division_level",
    }

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Caminho do arquivo CSV de atletas simplificado.")

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"]).expanduser()
        if not csv_path.exists():
            raise CommandError(f"Arquivo nao encontrado: {csv_path}")

        brazil = Country.objects.get(code="BRA")

        with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            sample = csv_file.read(2048)
            csv_file.seek(0)
            dialect = csv.Sniffer().sniff(sample, delimiters=",;")
            reader = csv.DictReader(csv_file, dialect=dialect)

            if not reader.fieldnames:
                raise CommandError("O CSV esta vazio ou sem cabecalho.")

            missing_columns = self.required_columns - set(reader.fieldnames)
            if missing_columns:
                missing = ", ".join(sorted(missing_columns))
                raise CommandError(f"Colunas obrigatorias ausentes: {missing}")

            created_count = 0
            updated_count = 0

            for row_number, row in enumerate(reader, start=2):
                full_name = row["full_name"].strip()
                sport_name = row["sport_name"].strip()
                current_club_name = row["current_club_name"].strip()

                if not full_name or not current_club_name:
                    self.stdout.write(self.style.WARNING(f"Linha {row_number}: dados obrigatorios vazios, ignorada."))
                    continue

                try:
                    division_level = int(row["club_division_level"].strip())
                except ValueError as exc:
                    raise CommandError(
                        f"Linha {row_number}: club_division_level invalido '{row['club_division_level']}'."
                    ) from exc

                try:
                    division = Division.objects.get(country=brazil, level=division_level)
                except Division.DoesNotExist as exc:
                    raise CommandError(
                        f"Linha {row_number}: divisao de nivel {division_level} nao encontrada no Brasil."
                    ) from exc

                club = self.get_club(division, current_club_name, row_number)

                athlete, created = Athlete.objects.update_or_create(
                    full_name=full_name,
                    defaults={
                        "sport_name": sport_name,
                        "nationality": brazil,
                        "primary_position": row.get("primary_position", "").strip() or "Nao informado",
                        "secondary_positions": row.get("secondary_positions", "").strip(),
                        "dominant_foot": "",
                        "current_club": club,
                        "status": Athlete.Status.ACTIVE,
                        "notes": row.get("notes", "").strip(),
                    },
                )
                athlete.full_clean()
                athlete.save()

                created_count += int(created)
                updated_count += int(not created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Importacao concluida: {created_count} atletas criados, {updated_count} atletas atualizados."
            )
        )

    def get_club(self, division, club_name, row_number):
        try:
            return Club.objects.get(division=division, short_name=club_name)
        except Club.DoesNotExist:
            try:
                return Club.objects.get(division=division, official_name=club_name)
            except Club.DoesNotExist as exc:
                raise CommandError(
                    f"Linha {row_number}: clube '{club_name}' nao encontrado na divisao {division.level}."
                ) from exc
