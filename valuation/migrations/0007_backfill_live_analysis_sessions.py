from django.db import migrations


def backfill_live_sessions(apps, schema_editor):
    Player = apps.get_model("valuation", "Player")
    LiveAnalysisSession = apps.get_model("valuation", "LiveAnalysisSession")
    LiveAnalysisEvent = apps.get_model("valuation", "LiveAnalysisEvent")

    for player in Player.objects.all():
        legacy_events = list(
            LiveAnalysisEvent.objects.filter(player=player, session__isnull=True).order_by("created_at", "id")
        )
        if not legacy_events:
            continue
        first_event = legacy_events[0]
        created_at = first_event.created_at
        session = LiveAnalysisSession.objects.create(
            player=player,
            observed_on=created_at.date(),
            kickoff_time=created_at.time().replace(second=0, microsecond=0),
            venue="Observacao migrada",
            home_away="away",
            weather="Clima nao informado",
            played_position=player.position,
            starter_status="starter",
            match_notes="Sessao criada automaticamente a partir de eventos antigos.",
            match_story="Historico legado migrado para o novo formato de analise ao vivo.",
        )
        for event in legacy_events:
            event_time = event.created_at
            if not event.minute:
                event.minute = max(event_time.minute, 1)
            if not event.match_period:
                event.match_period = "first_half"
            event.session = session
            event.save(update_fields=["session", "minute", "match_period"])


class Migration(migrations.Migration):

    dependencies = [
        ("valuation", "0006_liveanalysisevent_match_period_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_live_sessions, migrations.RunPython.noop),
    ]
