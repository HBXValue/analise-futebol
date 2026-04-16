from pathlib import Path

from django.apps import apps
from django.core import serializers
from django.core.management.base import BaseCommand


MODEL_LABELS = [
    "catalog.Country",
    "catalog.Division",
    "clubs.Club",
    "valuation.User",
    "valuation.Player",
    "valuation.AthleteIdentity",
    "valuation.PerformanceMetrics",
    "valuation.MarketMetrics",
    "valuation.MarketingMetrics",
    "valuation.BehaviorMetrics",
    "valuation.PlayerHistory",
    "valuation.DataSourceLog",
    "valuation.AthleteSnapshot",
    "valuation.PerformanceSnapshot",
    "valuation.BehaviorSnapshot",
    "valuation.MarketSnapshot",
    "valuation.MarketingSnapshot",
    "valuation.ScoreSnapshot",
    "valuation.ProjectionSnapshot",
    "valuation.AnalystNote",
    "valuation.DevelopmentPlan",
    "valuation.ProgressTracking",
    "valuation.OnBallEvent",
    "valuation.LiveAnalysisSession",
    "valuation.LiveAnalysisEvent",
    "valuation.LivePlayerEvaluation",
    "valuation.HBXValueProfile",
    "valuation.AthleteAIInsight",
    "valuation.CareerIntelligenceCase",
    "valuation.ClubCompetitiveContext",
    "valuation.CoachProfile",
    "valuation.CompetitiveDiagnosis",
    "valuation.CareerPrognosis",
    "valuation.IndividualDevelopmentPlan",
]


class Command(BaseCommand):
    help = "Exporta os dados principais do HBX para um fixture JSON em UTF-8."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="fixtures/hbx_data.json",
            help="Caminho do arquivo JSON de saida.",
        )

    def handle(self, *args, **options):
        output_path = Path(options["output"])
        output_path.parent.mkdir(parents=True, exist_ok=True)

        objects = []
        for label in MODEL_LABELS:
            model = apps.get_model(label)
            objects.extend(model.objects.all().order_by("pk"))

        with output_path.open("w", encoding="utf-8") as fixture_file:
            serializers.serialize("json", objects, indent=2, stream=fixture_file)

        self.stdout.write(self.style.SUCCESS(f"Exportacao concluida: {output_path}"))
