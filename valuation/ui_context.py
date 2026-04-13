from catalog.models import Country, Division
from clubs.models import Club
from valuation.models import Player


def build_global_player_context(request, current_user, selected_player=None):
    players = list(
        Player.objects.filter(user=current_user)
        .select_related("division_reference__country", "club_reference")
        .order_by("name")
    )
    selected = selected_player
    athlete_param = request.GET.get("athlete")
    if athlete_param:
        try:
            athlete_id = int(athlete_param)
            selected = next((player for player in players if player.id == athlete_id), selected)
        except (TypeError, ValueError):
            pass
    elif selected is None and players:
        selected = players[0]

    return {
        "global_players": players,
        "global_selected_player": selected,
        "countries": list(Country.objects.filter(is_active=True).order_by("name")),
        "division_suggestions": list(
            Division.objects.filter(is_active=True).select_related("country").order_by("country__name", "scope", "state", "level", "name")
        ),
        "club_suggestions": list(
            Club.objects.filter(status=Club.Status.ACTIVE).select_related("country", "division").order_by("official_name")
        ),
    }
