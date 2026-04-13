from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Carrega catálogos de clubes pré-definidos."

    PRESETS = {
        "europe_top": [
            "data_templates/clubs_portugal_spain_italy_top_2025_2026.csv",
        ],
        "europe_second": [
            "data_templates/clubs_portugal_spain_italy_second_divisions_2025_2026.csv",
        ],
        "europe_all": [
            "data_templates/clubs_portugal_spain_italy_top_2025_2026.csv",
            "data_templates/clubs_portugal_spain_italy_second_divisions_2025_2026.csv",
        ],
        "europe_expansion_top": [
            "data_templates/clubs_france_germany_england_top_2025_2026.csv",
        ],
        "europe_expansion_second": [
            "data_templates/clubs_france_germany_england_second_divisions_2025_2026.csv",
        ],
        "europe_expansion_all": [
            "data_templates/clubs_france_germany_england_top_2025_2026.csv",
            "data_templates/clubs_france_germany_england_second_divisions_2025_2026.csv",
        ],
        "europe_complete": [
            "data_templates/clubs_portugal_spain_italy_top_2025_2026.csv",
            "data_templates/clubs_portugal_spain_italy_second_divisions_2025_2026.csv",
            "data_templates/clubs_france_germany_england_top_2025_2026.csv",
            "data_templates/clubs_france_germany_england_second_divisions_2025_2026.csv",
        ],
        "saudi_mls": [
            "data_templates/clubs_saudi_mls_2025_2026.csv",
        ],
        "arg_mex_nld": [
            "data_templates/clubs_argentina_mexico_holland_2026.csv",
        ],
        "brazil_all": [
            "data_templates/clubs_brasil_series_abc_2026.csv",
            "data_templates/clubs_brasil_serie_d_2026.csv",
        ],
    }

    def add_arguments(self, parser):
        parser.add_argument("preset", type=str, help="Preset de catálogo para importar.")

    def handle(self, *args, **options):
        preset = options["preset"].strip().lower()
        if preset not in self.PRESETS:
            available = ", ".join(sorted(self.PRESETS))
            raise CommandError(f"Preset inválido '{preset}'. Use: {available}")

        base_dir = Path.cwd()
        for relative_path in self.PRESETS[preset]:
            csv_path = base_dir / relative_path
            if not csv_path.exists():
                raise CommandError(f"Arquivo não encontrado: {csv_path}")
            self.stdout.write(f"Importando {csv_path.name}...")
            call_command("import_clubs_csv", str(csv_path))

        self.stdout.write(self.style.SUCCESS(f"Preset '{preset}' carregado com sucesso."))
