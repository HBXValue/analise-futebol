from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from valuation.models import DataSourceLog, Player
from valuation.services import save_athlete_360_snapshots


class Command(BaseCommand):
    help = "Gera snapshots HBX 360 para atletas existentes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            dest="snapshot_date",
            help="Data do snapshot no formato YYYY-MM-DD. Padrao: data local de hoje.",
        )

    def handle(self, *args, **options):
        raw_snapshot_date = options.get("snapshot_date")
        snapshot_date = date.fromisoformat(raw_snapshot_date) if raw_snapshot_date else timezone.localdate()
        players = Player.objects.select_related(
            "division_reference__country",
            "club_reference",
            "performance_metrics",
            "market_metrics",
            "marketing_metrics",
            "behavior_metrics",
        ).order_by("id")
        created_count = 0
        for player in players:
            save_athlete_360_snapshots(
                player,
                snapshot_date=snapshot_date,
                source=DataSourceLog.SourceType.SYSTEM,
                payload={"backfill": True},
            )
            created_count += 1
        self.stdout.write(self.style.SUCCESS(f"Snapshots HBX 360 gerados para {created_count} atletas em {snapshot_date}."))
