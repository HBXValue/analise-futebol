import unicodedata
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from athletes.models import Athlete, AthleteClubHistory
from catalog.models import Country
from clubs.models import Club
from valuation.models import Player


def _normalized_key(value):
    normalized = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_only.split())


def _contains_non_ascii(value):
    return any(ord(char) > 127 for char in str(value or ""))


def _club_priority(club):
    short_name = (club.short_name or "").strip()
    official_name = (club.official_name or "").strip()
    return (
        1 if official_name == short_name and official_name else 0,
        1 if _contains_non_ascii(official_name) or _contains_non_ascii(short_name) else 0,
        len(official_name) * -1,
        club.id,
    )


class Command(BaseCommand):
    help = "Consolida clubes brasileiros duplicados por divisão com base no nome curto normalizado."

    @transaction.atomic
    def handle(self, *args, **options):
        brazil = Country.objects.get(code="BRA")
        grouped = defaultdict(list)

        clubs = list(
            Club.objects.filter(country=brazil)
            .select_related("division")
            .order_by("division__id", "id")
        )

        for club in clubs:
            key = (
                club.division_id,
                _normalized_key(club.short_name or club.official_name),
            )
            grouped[key].append(club)

        merged_groups = 0
        removed_total = 0

        for duplicates in grouped.values():
            if len(duplicates) <= 1:
                continue

            canonical = max(duplicates, key=_club_priority)
            aliases = []

            for club in duplicates:
                if club.pk == canonical.pk:
                    continue

                aliases.extend(
                    item.strip()
                    for item in [club.official_name, club.short_name]
                    if item and item.strip()
                )

                Athlete.objects.filter(current_club=club).update(current_club=canonical)
                AthleteClubHistory.objects.filter(club=club).update(club=canonical)
                Player.objects.filter(club_reference=club).update(
                    club_reference=canonical,
                    club_origin=canonical.short_name or canonical.official_name,
                    league_level=canonical.division.short_name or canonical.division.name,
                    division_reference=canonical.division,
                )
                club.delete()
                removed_total += 1

            existing_notes = canonical.notes.strip()
            alias_line = ", ".join(sorted({alias for alias in aliases if alias != canonical.official_name and alias != canonical.short_name}))
            if alias_line:
                note_text = f"Aliases consolidados: {alias_line}"
                if note_text not in existing_notes:
                    canonical.notes = f"{existing_notes}\n{note_text}".strip()
                    canonical.save(update_fields=["notes", "updated_at"])

            merged_groups += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Normalização concluída: {merged_groups} grupos consolidados, {removed_total} clubes duplicados removidos."
            )
        )
