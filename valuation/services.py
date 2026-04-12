import csv
import io
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from django.utils import timezone

from django.db import transaction

from valuation.i18n import tr
from valuation.models import AnalystNote, BehaviorMetrics, DevelopmentPlan, LiveAnalysisEvent, LiveAnalysisSession, MarketMetrics, MarketingMetrics, OnBallEvent, PerformanceMetrics, Player, PlayerHistory, ProgressTracking


RANGES = {
    "xg_xa": (0, 1.5),
    "passes_pct": (0, 100),
    "dribbles_pct": (0, 100),
    "tackles_pct": (0, 100),
    "high_intensity_distance": (0, 13000),
    "final_third_recoveries": (0, 15),
    "annual_growth": (-20, 60),
    "club_interest": (0, 100),
    "league_score": (0, 100),
    "age_factor": (0, 100),
    "club_reputation": (0, 100),
    "followers": (0, 20000000),
    "engagement": (0, 20),
    "media_mentions": (0, 1000),
    "sponsorships": (0, 20),
    "sentiment_score": (0, 100),
    "conscientiousness": (0, 100),
    "adaptability": (0, 100),
    "resilience": (0, 100),
    "deliberate_practice": (0, 100),
    "executive_function": (0, 100),
    "leadership": (0, 100),
}


def clamp(value, minimum=0, maximum=100):
    return max(minimum, min(maximum, value))


def normalize(value, range_key):
    min_value, max_value = RANGES[range_key]
    if max_value == min_value:
        return 0
    scaled = ((float(value) - min_value) / (max_value - min_value)) * 100
    return round(clamp(scaled), 2)


def growth_label(score, lang="pt"):
    if score > 80:
        return tr(lang, "elite_prospect")
    if score >= 65:
        return tr(lang, "high_potential")
    if score >= 50:
        return tr(lang, "developing")
    return tr(lang, "low_projection")


def calculate_scores(player, lang="pt"):
    performance = player.performance_metrics
    market = player.market_metrics
    marketing = player.marketing_metrics
    behavior = player.behavior_metrics

    normalized_xg_xa = normalize(performance.xg + performance.xa, "xg_xa")
    performance_score = round(
        (normalized_xg_xa * 0.25)
        + (normalize(performance.passes_pct, "passes_pct") * 0.15)
        + (normalize(performance.dribbles_pct, "dribbles_pct") * 0.15)
        + (normalize(performance.tackles_pct, "tackles_pct") * 0.15)
        + (normalize(performance.high_intensity_distance, "high_intensity_distance") * 0.15)
        + (normalize(performance.final_third_recoveries, "final_third_recoveries") * 0.15),
        2,
    )
    market_score = round(
        (normalize(market.annual_growth, "annual_growth") * 0.30)
        + (normalize(market.league_score, "league_score") * 0.20)
        + (normalize(market.club_interest, "club_interest") * 0.20)
        + (normalize(market.age_factor, "age_factor") * 0.15)
        + (normalize(market.club_reputation, "club_reputation") * 0.15),
        2,
    )
    marketing_score = round(
        (normalize(marketing.followers, "followers") * 0.25)
        + (normalize(marketing.engagement, "engagement") * 0.25)
        + (normalize(marketing.media_mentions, "media_mentions") * 0.20)
        + (normalize(marketing.sponsorships, "sponsorships") * 0.15)
        + (normalize(marketing.sentiment_score, "sentiment_score") * 0.15),
        2,
    )
    behavior_score = round(
        (normalize(behavior.conscientiousness, "conscientiousness") * 0.25)
        + (normalize(behavior.adaptability, "adaptability") * 0.20)
        + (normalize(behavior.resilience, "resilience") * 0.20)
        + (normalize(behavior.deliberate_practice, "deliberate_practice") * 0.15)
        + (normalize(behavior.executive_function, "executive_function") * 0.10)
        + (normalize(behavior.leadership, "leadership") * 0.10),
        2,
    )
    valuation_score = round(
        (performance_score * 0.40)
        + (market_score * 0.20)
        + (marketing_score * 0.20)
        + (behavior_score * 0.20),
        2,
    )
    projected_value = (
        player.current_value * (Decimal("1") + Decimal(str(valuation_score)) / Decimal("100"))
    ).quantize(Decimal("0.01"))
    return {
        "performance_score": performance_score,
        "market_score": market_score,
        "marketing_score": marketing_score,
        "behavior_score": behavior_score,
        "valuation_score": valuation_score,
        "projected_value": projected_value,
        "growth_potential_label": growth_label(valuation_score, lang),
    }


def calculate_growth_rate(player):
    history = list(player.history.order_by("-date", "-id")[:2])
    if len(history) < 2:
        return 0.0
    current_value = float(history[0].current_value)
    previous_value = float(history[1].current_value)
    if previous_value <= 0:
        return 0.0
    return round((current_value - previous_value) / previous_value, 4)


PROJECTION_FACTORS = {
    "3": Decimal("0.25"),
    "6": Decimal("0.5"),
    "12": Decimal("1"),
    "24": Decimal("2"),
}


def build_projection_scenarios(player, lang="pt", period="12"):
    period = period if period in PROJECTION_FACTORS else "12"
    months = int(period)
    time_factor = PROJECTION_FACTORS[period]
    growth_rate = Decimal(str(calculate_growth_rate(player)))
    current_value = Decimal(player.current_value)
    multipliers = {
        "conservative": Decimal("0.7"),
        "expected": Decimal("1.0"),
        "aggressive": Decimal("1.3"),
    }
    scenarios = {}
    for label, multiplier in multipliers.items():
        adjusted_rate = Decimal("1") + (growth_rate * multiplier)
        if adjusted_rate <= 0:
            adjusted_rate = Decimal("0.01")
        scenarios[label] = float((current_value * (adjusted_rate ** time_factor)).quantize(Decimal("0.01")))
    return {
        "period": months,
        "growth_rate": float(growth_rate),
        "scenarios": scenarios,
    }


def build_growth_insights(player, lang="pt", period="12"):
    scenarios = build_projection_scenarios(player, lang, period)
    scores = calculate_scores(player, lang)
    pillars = {
        tr(lang, "performance_metrics"): scores["performance_score"],
        tr(lang, "market_metrics"): scores["market_score"],
        tr(lang, "marketing_metrics"): scores["marketing_score"],
        tr(lang, "behavior_metrics"): scores["behavior_score"],
    }
    main_driver = max(pillars, key=pillars.get)
    expected_value = scenarios["scenarios"]["expected"]
    current_value = float(player.current_value)
    projected_growth = 0 if current_value == 0 else round(((expected_value - current_value) / current_value) * 100, 2)
    return {
        "projected_growth_pct": projected_growth,
        "main_driver": main_driver,
        "growth_rate": round(scenarios["growth_rate"] * 100, 2),
        "period": scenarios["period"],
        "scenarios": scenarios["scenarios"],
    }


def club_attractiveness_label(valuation_score, market_score, lang="pt"):
    if valuation_score >= 80 or market_score >= 78:
        return tr(lang, "elite_club_interest")
    if valuation_score >= 70 or market_score >= 68:
        return tr(lang, "high_club_interest")
    if valuation_score >= 58 or market_score >= 58:
        return tr(lang, "medium_club_interest")
    return tr(lang, "low_club_interest")


def simulate_uplift(player, target_data, lang="pt"):
    current_scores = calculate_scores(player, lang)
    current_performance = player.performance_metrics

    original_values = {
        "xg": current_performance.xg,
        "xa": current_performance.xa,
        "passes_pct": current_performance.passes_pct,
        "dribbles_pct": current_performance.dribbles_pct,
        "tackles_pct": current_performance.tackles_pct,
        "high_intensity_distance": current_performance.high_intensity_distance,
        "final_third_recoveries": current_performance.final_third_recoveries,
    }

    target_values = {}
    for key, pct_increase in target_data.items():
        base_value = float(original_values[key])
        target_values[key] = base_value * (1 + (float(pct_increase) / 100))
        setattr(current_performance, key, target_values[key])
    target_scores = calculate_scores(player, lang)
    for key, value in original_values.items():
        setattr(current_performance, key, value)

    elite_targets = {
        "xg": 0.55,
        "xa": 0.35,
        "passes_pct": 92,
        "dribbles_pct": 80,
        "tackles_pct": 72,
        "high_intensity_distance": 12000,
        "final_third_recoveries": 10,
    }

    metric_rows = []
    for key, current_value in original_values.items():
        target_value = target_values[key]
        elite_value = elite_targets[key]
        max_scale = max(float(elite_value), float(target_value), float(current_value), 1.0)
        metric_rows.append(
            {
                "label": tr(lang, key),
                "current": round(float(current_value), 2),
                "target": round(float(target_value), 2),
                "delta": round(float(target_value) - float(current_value), 2),
                "increase_pct": round(float(target_data[key]), 2),
                "elite": round(float(elite_value), 2),
                "gap_to_elite": round(float(elite_value) - float(target_value), 2),
                "current_pct": round((float(current_value) / max_scale) * 100, 2),
                "target_pct": round((float(target_value) / max_scale) * 100, 2),
                "elite_pct": round((float(elite_value) / max_scale) * 100, 2),
            }
        )

    value_delta_pct = 0.0
    if float(player.current_value) > 0:
        value_delta_pct = round(((float(target_scores["projected_value"]) - float(current_scores["projected_value"])) / float(player.current_value)) * 100, 2)

    return {
        "current_scores": current_scores,
        "target_scores": target_scores,
        "metric_rows": metric_rows,
        "performance_jump": round(target_scores["performance_score"] - current_scores["performance_score"], 2),
        "value_delta_pct": value_delta_pct,
        "club_attractiveness": club_attractiveness_label(target_scores["valuation_score"], target_scores["market_score"], lang),
    }


def calculate_percentile(player):
    peers = list(
        Player.objects.filter(position__iexact=player.position).select_related(
            "performance_metrics",
            "market_metrics",
            "marketing_metrics",
            "behavior_metrics",
        )
    )
    if not peers:
        return 100.0
    ranked = sorted(calculate_scores(item)["valuation_score"] for item in peers)
    player_score = calculate_scores(player)["valuation_score"]
    lower_or_equal = sum(1 for score in ranked if score <= player_score)
    return round((lower_or_equal / len(ranked)) * 100, 2)


def build_growth_series(player):
    valuation_share = calculate_scores(player)["valuation_score"] / 100
    points = []
    base = Decimal(player.current_value)
    for season in range(5):
        growth_factor = Decimal("1") + (Decimal(str(valuation_share)) * Decimal(str(season / 4 if season else 0)))
        points.append(float((base * growth_factor).quantize(Decimal("0.01"))))
    return points


def build_dashboard_payload(players, lang="pt"):
    payload = []
    for player in players:
        scores = calculate_scores(player, lang)
        payload.append(
            {
                "player": player,
                "scores": scores,
                "percentile": calculate_percentile(player),
                "growth_series": build_growth_series(player),
                "growth_rate": round(calculate_growth_rate(player) * 100, 2),
            }
        )
    return payload


def radar_chart_data(player, lang="pt"):
    scores = calculate_scores(player, lang)
    categories = [tr(lang, "performance_metrics"), tr(lang, "market_metrics"), tr(lang, "marketing_metrics"), tr(lang, "behavior_metrics")]
    values = [
        scores["performance_score"],
        scores["market_score"],
        scores["marketing_score"],
        scores["behavior_score"],
    ]
    return json.dumps(
        {
            "data": [
                {
                    "type": "scatterpolar",
                    "r": values + [values[0]],
                    "theta": categories + [categories[0]],
                    "fill": "toself",
                    "line": {"color": "#00e0b8"},
                    "fillcolor": "rgba(0, 224, 184, 0.28)",
                    "name": player.name,
                }
            ],
            "layout": {
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(0,0,0,0)",
                "font": {"color": "#e8f1f2"},
                "polar": {
                    "bgcolor": "rgba(0,0,0,0)",
                    "radialaxis": {"range": [0, 100], "gridcolor": "rgba(255,255,255,0.18)"},
                    "angularaxis": {"gridcolor": "rgba(255,255,255,0.12)"},
                },
                "margin": {"l": 20, "r": 20, "t": 20, "b": 20},
                "showlegend": False,
            },
        }
    )


def growth_chart_data(player, lang="pt"):
    projected = float(calculate_scores(player, lang)["projected_value"])
    return json.dumps(
        {
            "data": [
                {
                    "type": "scatter",
                    "mode": "lines+markers",
                    "x": [tr(lang, "today"), tr(lang, "months_6"), tr(lang, "months_12"), tr(lang, "months_24"), tr(lang, "months_36")],
                    "y": build_growth_series(player),
                    "line": {"color": "#f9c74f", "width": 3},
                    "marker": {"size": 8},
                    "name": tr(lang, "simulated_value"),
                },
                {
                    "type": "scatter",
                    "mode": "markers",
                    "x": [tr(lang, "months_36")],
                    "y": [projected],
                    "marker": {"size": 14, "color": "#00e0b8"},
                    "name": tr(lang, "projected_value"),
                },
            ],
            "layout": {
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(0,0,0,0)",
                "font": {"color": "#e8f1f2"},
                "margin": {"l": 40, "r": 20, "t": 20, "b": 40},
                "xaxis": {"gridcolor": "rgba(255,255,255,0.1)"},
                "yaxis": {"gridcolor": "rgba(255,255,255,0.1)", "title": tr(lang, "projected_value_axis")},
                "legend": {"orientation": "h"},
            },
        }
    )


def evolution_chart_data(player, lang="pt", period="12"):
    history = list(player.history.order_by("date", "id"))
    scenarios = build_projection_scenarios(player, lang, period)
    if history:
        past_dates = [item.date.strftime("%d/%m/%Y") for item in history]
        past_values = [float(item.current_value) for item in history]
    else:
        past_dates = [tr(lang, "today")]
        past_values = [float(player.current_value)]
    future_x = [
        f"+{scenarios['period']}m {tr(lang, 'conservative')}",
        f"+{scenarios['period']}m {tr(lang, 'expected')}",
        f"+{scenarios['period']}m {tr(lang, 'aggressive')}",
    ]
    future_y = list(scenarios["scenarios"].values())
    return json.dumps(
        {
            "data": [
                {
                    "type": "scatter",
                    "mode": "lines+markers",
                    "x": past_dates,
                    "y": past_values,
                    "line": {"color": "#00e0b8", "width": 3},
                    "name": tr(lang, "past_values"),
                },
                {
                    "type": "scatter",
                    "mode": "lines+markers",
                    "x": [past_dates[-1]] + future_x,
                    "y": [past_values[-1]] + future_y,
                    "line": {"color": "#f9c74f", "width": 3, "dash": "dot"},
                    "name": tr(lang, "projected_values"),
                },
            ],
            "layout": {
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(0,0,0,0)",
                "font": {"color": "#e8f1f2"},
                "margin": {"l": 40, "r": 20, "t": 20, "b": 60},
                "xaxis": {"gridcolor": "rgba(255,255,255,0.1)"},
                "yaxis": {"gridcolor": "rgba(255,255,255,0.1)", "title": tr(lang, "projected_value_axis")},
                "legend": {"orientation": "h"},
            },
        }
    )


def pillar_trend_chart_data(player, lang="pt"):
    history = list(player.history.order_by("date", "id"))
    if not history:
        scores = calculate_scores(player, lang)
        history = [
            type("Snapshot", (), {
                "date": timezone.localdate(),
                "performance_score": scores["performance_score"],
                "market_score": scores["market_score"],
                "marketing_score": scores["marketing_score"],
                "behavior_score": scores["behavior_score"],
            })()
        ]
    x_values = [item.date.strftime("%d/%m/%Y") for item in history]
    series = [
        (tr(lang, "performance_metrics"), [item.performance_score for item in history], "#00e0b8"),
        (tr(lang, "market_metrics"), [item.market_score for item in history], "#4cc9f0"),
        (tr(lang, "marketing_metrics"), [item.marketing_score for item in history], "#f9c74f"),
        (tr(lang, "behavior_metrics"), [item.behavior_score for item in history], "#f72585"),
    ]
    return json.dumps(
        {
            "data": [
                {"type": "scatter", "mode": "lines+markers", "x": x_values, "y": values, "name": name, "line": {"color": color, "width": 2}}
                for name, values, color in series
            ],
            "layout": {
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(0,0,0,0)",
                "font": {"color": "#e8f1f2"},
                "margin": {"l": 40, "r": 20, "t": 20, "b": 60},
                "xaxis": {"gridcolor": "rgba(255,255,255,0.1)"},
                "yaxis": {"gridcolor": "rgba(255,255,255,0.1)", "range": [0, 100]},
                "legend": {"orientation": "h"},
            },
        }
    )


def comparison_chart_data(players, lang="pt"):
    categories = [tr(lang, "performance_metrics"), tr(lang, "market_metrics"), tr(lang, "marketing_metrics"), tr(lang, "behavior_metrics"), tr(lang, "valuation_score")]
    data = []
    for player in players:
        scores = calculate_scores(player, lang)
        data.append(
            {
                "type": "bar",
                "name": player.name,
                "x": categories,
                "y": [
                    scores["performance_score"],
                    scores["market_score"],
                    scores["marketing_score"],
                    scores["behavior_score"],
                    scores["valuation_score"],
                ],
            }
        )
    return json.dumps(
        {
            "data": data,
            "layout": {
                "barmode": "group",
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(0,0,0,0)",
                "font": {"color": "#e8f1f2"},
                "margin": {"l": 40, "r": 20, "t": 20, "b": 50},
                "yaxis": {"gridcolor": "rgba(255,255,255,0.1)", "range": [0, 100]},
            },
        }
    )


def percentile_chart_data(players, lang="pt"):
    return json.dumps(
        {
            "data": [
                {
                    "type": "bar",
                    "x": [player.name for player in players],
                    "y": [calculate_percentile(player) for player in players],
                    "marker": {"color": "#00e0b8"},
                }
            ],
            "layout": {
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(0,0,0,0)",
                "font": {"color": "#e8f1f2"},
                "margin": {"l": 40, "r": 20, "t": 20, "b": 80},
                "yaxis": {"gridcolor": "rgba(255,255,255,0.1)", "range": [0, 100], "title": tr(lang, "percentile")},
            },
        }
    )


@transaction.atomic
def save_player_bundle(user, cleaned_data, player=None):
    if player is None:
        player = Player.objects.create(
            user=user,
            name=cleaned_data["name"],
            age=cleaned_data["age"],
            position=cleaned_data["position"],
            current_value=cleaned_data["current_value"],
            league_level=cleaned_data["league_level"],
            club_origin=cleaned_data["club_origin"],
        )
        PerformanceMetrics.objects.create(player=player)
        MarketMetrics.objects.create(player=player)
        MarketingMetrics.objects.create(player=player)
        BehaviorMetrics.objects.create(player=player)
    else:
        player.name = cleaned_data["name"]
        player.age = cleaned_data["age"]
        player.position = cleaned_data["position"]
        player.current_value = cleaned_data["current_value"]
        player.league_level = cleaned_data["league_level"]
        player.club_origin = cleaned_data["club_origin"]
        player.save()

    PerformanceMetrics.objects.filter(player=player).update(
        xg=cleaned_data["xg"],
        xa=cleaned_data["xa"],
        passes_pct=cleaned_data["passes_pct"],
        dribbles_pct=cleaned_data["dribbles_pct"],
        tackles_pct=cleaned_data["tackles_pct"],
        high_intensity_distance=cleaned_data["high_intensity_distance"],
        final_third_recoveries=cleaned_data["final_third_recoveries"],
    )
    MarketMetrics.objects.filter(player=player).update(
        annual_growth=cleaned_data["annual_growth"],
        club_interest=cleaned_data["club_interest"],
        league_score=cleaned_data["league_score"],
        age_factor=cleaned_data["age_factor"],
        club_reputation=cleaned_data["club_reputation"],
    )
    MarketingMetrics.objects.filter(player=player).update(
        followers=cleaned_data["followers"],
        engagement=cleaned_data["engagement"],
        media_mentions=cleaned_data["media_mentions"],
        sponsorships=cleaned_data["sponsorships"],
        sentiment_score=cleaned_data["sentiment_score"],
    )
    BehaviorMetrics.objects.filter(player=player).update(
        conscientiousness=cleaned_data["conscientiousness"],
        adaptability=cleaned_data["adaptability"],
        resilience=cleaned_data["resilience"],
        deliberate_practice=cleaned_data["deliberate_practice"],
        executive_function=cleaned_data["executive_function"],
        leadership=cleaned_data["leadership"],
    )
    save_player_history_snapshot(player)
    return player


def save_player_history_snapshot(player, snapshot_date=None):
    snapshot_date = snapshot_date or timezone.localdate()
    scores = calculate_scores(player)
    history_entry = PlayerHistory.objects.filter(player=player, date=snapshot_date).order_by("-id").first()
    if history_entry:
        history_entry.performance_score = scores["performance_score"]
        history_entry.market_score = scores["market_score"]
        history_entry.marketing_score = scores["marketing_score"]
        history_entry.behavior_score = scores["behavior_score"]
        history_entry.valuation_score = scores["valuation_score"]
        history_entry.current_value = player.current_value
        history_entry.save()
        return history_entry
    return PlayerHistory.objects.create(
        player=player,
        date=snapshot_date,
        performance_score=scores["performance_score"],
        market_score=scores["market_score"],
        marketing_score=scores["marketing_score"],
        behavior_score=scores["behavior_score"],
        valuation_score=scores["valuation_score"],
        current_value=player.current_value,
    )


def save_manual_history_snapshot(player, cleaned_data):
    scores = calculate_scores(player)
    history_entry = PlayerHistory.objects.filter(player=player, date=cleaned_data["date"]).order_by("-id").first()
    values = {
        "performance_score": cleaned_data.get("performance_score") if cleaned_data.get("performance_score") is not None else scores["performance_score"],
        "market_score": cleaned_data.get("market_score") if cleaned_data.get("market_score") is not None else scores["market_score"],
        "marketing_score": cleaned_data.get("marketing_score") if cleaned_data.get("marketing_score") is not None else scores["marketing_score"],
        "behavior_score": cleaned_data.get("behavior_score") if cleaned_data.get("behavior_score") is not None else scores["behavior_score"],
        "valuation_score": cleaned_data.get("valuation_score") if cleaned_data.get("valuation_score") is not None else scores["valuation_score"],
        "current_value": cleaned_data["current_value"],
    }
    if history_entry:
        for key, value in values.items():
            setattr(history_entry, key, value)
        history_entry.save()
        return history_entry
    return PlayerHistory.objects.create(player=player, date=cleaned_data["date"], **values)


def save_analyst_note(player, cleaned_data):
    return AnalystNote.objects.create(player=player, **cleaned_data)


def save_development_plan(player, cleaned_data):
    return DevelopmentPlan.objects.create(player=player, **cleaned_data)


def save_progress_tracking(player, cleaned_data):
    progress_pct = round((cleaned_data["current_value"] / cleaned_data["target_value"]) * 100, 2)
    return ProgressTracking.objects.create(
        player=player,
        metric=cleaned_data["metric"],
        current_value=cleaned_data["current_value"],
        target_value=cleaned_data["target_value"],
        progress_pct=min(progress_pct, 100),
    )


def save_on_ball_event(player, cleaned_data):
    return OnBallEvent.objects.create(player=player, **cleaned_data)


def on_ball_decision_analysis(player, lang="pt"):
    events = list(player.on_ball_events.all())
    total = len(events)
    if not total:
        return {
            "total_actions": 0,
            "decision_success_rate": 0,
            "action_distribution": [],
            "action_efficiency": [],
            "pressure_split": {"under_pressure": 0, "no_pressure": 0},
            "game_profile": tr(lang, "conservative_profile"),
            "decision_quality_text": tr(lang, "reliable_decision_making"),
            "pressure_note": tr(lang, "elite_pressure_indicator"),
        }

    positives = sum(1 for event in events if event.outcome == "positive")
    decision_success_rate = round((positives / total) * 100, 2)

    action_keys = ["pass", "dribble", "shot", "carry", "turnover"]
    action_distribution = []
    action_efficiency = []
    action_counts = {}
    for action_key in action_keys:
        action_events = [event for event in events if event.action_type == action_key]
        action_counts[action_key] = len(action_events)
        if action_events:
            positive_actions = sum(1 for event in action_events if event.outcome == "positive")
            action_distribution.append({"label": tr(lang, action_key), "value": round((len(action_events) / total) * 100, 2)})
            action_efficiency.append({"label": tr(lang, action_key), "value": round((positive_actions / len(action_events)) * 100, 2)})
        else:
            action_distribution.append({"label": tr(lang, action_key), "value": 0})
            action_efficiency.append({"label": tr(lang, action_key), "value": 0})

    pressure_split = {}
    for pressure_key in ["under_pressure", "no_pressure"]:
        pressure_events = [event for event in events if event.pressure_status == pressure_key]
        if pressure_events:
            positive_pressure = sum(1 for event in pressure_events if event.outcome == "positive")
            pressure_split[pressure_key] = round((positive_pressure / len(pressure_events)) * 100, 2)
        else:
            pressure_split[pressure_key] = 0

    pass_ratio = action_counts["pass"] / total
    dribble_ratio = action_counts["dribble"] / total
    shot_ratio = action_counts["shot"] / total
    if pass_ratio >= 0.55 and shot_ratio < 0.18:
        profile = tr(lang, "conservative_profile")
    elif dribble_ratio + shot_ratio >= 0.42:
        profile = tr(lang, "aggressive_profile")
    else:
        profile = tr(lang, "progressive_profile")

    decision_quality_text = tr(lang, "reliable_decision_making") if decision_success_rate >= 60 else tr(lang, "risky_decision_making")
    return {
        "total_actions": total,
        "decision_success_rate": decision_success_rate,
        "action_distribution": action_distribution,
        "action_efficiency": action_efficiency,
        "pressure_split": pressure_split,
        "game_profile": profile,
        "decision_quality_text": decision_quality_text,
        "pressure_note": tr(lang, "elite_pressure_indicator"),
    }


def on_ball_distribution_chart_data(player, lang="pt"):
    analysis = on_ball_decision_analysis(player, lang)
    return json.dumps(
        {
            "data": [
                {
                    "type": "pie",
                    "labels": [item["label"] for item in analysis["action_distribution"]],
                    "values": [item["value"] for item in analysis["action_distribution"]],
                    "hole": 0.45,
                    "marker": {"colors": ["#00e0b8", "#4cc9f0", "#f9c74f", "#f72585", "#ff6b6b"]},
                }
            ],
            "layout": {
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(0,0,0,0)",
                "font": {"color": "#e8f1f2"},
                "margin": {"l": 20, "r": 20, "t": 20, "b": 20},
                "showlegend": True,
            },
        }
    )


def on_ball_efficiency_chart_data(player, lang="pt"):
    analysis = on_ball_decision_analysis(player, lang)
    return json.dumps(
        {
            "data": [
                {
                    "type": "bar",
                    "x": [item["label"] for item in analysis["action_efficiency"]],
                    "y": [item["value"] for item in analysis["action_efficiency"]],
                    "marker": {"color": "#00e0b8"},
                }
            ],
            "layout": {
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(0,0,0,0)",
                "font": {"color": "#e8f1f2"},
                "margin": {"l": 40, "r": 20, "t": 20, "b": 60},
                "yaxis": {"gridcolor": "rgba(255,255,255,0.1)", "range": [0, 100]},
            },
        }
    )


LIVE_EVENT_POINTS = {
    "received": 0.5,
    "controlled": 0.5,
    "forward_pass": 1.2,
    "backward_pass": 0.4,
    "progressed": 1.5,
    "cross": 1.4,
    "shot": 1.8,
    "goal": 4.0,
    "dispossessed": -1.8,
    "tackle_won": 1.7,
}


MENTALITY_FIELDS = [
    "confidence",
    "intensity",
    "focus",
    "decision_making",
    "resilience",
    "anxiety",
    "motivation",
    "communication",
    "discipline",
    "emotional_control",
]


def save_live_analysis_session(player, cleaned_data, session=None):
    values = {
        "observed_on": cleaned_data["observed_on"],
        "kickoff_time": cleaned_data["kickoff_time"],
        "venue": cleaned_data["venue"],
        "home_away": cleaned_data["home_away"],
        "weather": cleaned_data["weather"],
        "played_position": cleaned_data["played_position"],
        "starter_status": cleaned_data["starter_status"],
        "minute_entered": cleaned_data.get("minute_entered"),
        "match_notes": cleaned_data.get("match_notes", ""),
        "match_story": cleaned_data.get("match_story", ""),
        "confidence": cleaned_data["confidence"],
        "intensity": cleaned_data["intensity"],
        "focus": cleaned_data["focus"],
        "decision_making": cleaned_data["decision_making"],
        "resilience": cleaned_data["resilience"],
        "anxiety": cleaned_data["anxiety"],
        "motivation": cleaned_data["motivation"],
        "communication": cleaned_data["communication"],
        "discipline": cleaned_data["discipline"],
        "emotional_control": cleaned_data["emotional_control"],
    }
    if session is None:
        return LiveAnalysisSession.objects.create(player=player, **values)
    for key, value in values.items():
        setattr(session, key, value)
    session.save()
    return session


def ensure_live_analysis_session(player):
    latest_session = player.live_analysis_sessions.first()
    if latest_session:
        return latest_session
    legacy_events = list(player.live_analysis_events.filter(session__isnull=True).order_by("created_at"))
    if not legacy_events:
        return None
    first_event = legacy_events[0]
    local_dt = timezone.localtime(first_event.created_at)
    session = LiveAnalysisSession.objects.create(
        player=player,
        observed_on=local_dt.date(),
        kickoff_time=local_dt.time().replace(second=0, microsecond=0),
        venue=tr("pt", "legacy_observation"),
        home_away=LiveAnalysisSession.HomeAway.AWAY,
        weather=tr("pt", "weather_not_informed"),
        played_position=player.position,
        starter_status=LiveAnalysisSession.StarterStatus.STARTER,
        match_notes=tr("pt", "legacy_observation_notes"),
        match_story=tr("pt", "legacy_observation_story"),
    )
    for event in legacy_events:
        event_local_dt = timezone.localtime(event.created_at)
        if not event.minute:
            event.minute = max(event_local_dt.minute, 1)
        if not event.match_period:
            event.match_period = LiveAnalysisEvent.MatchPeriod.FIRST_HALF
        event.session = session
        event.save(update_fields=["session", "minute", "match_period"])
    return session


def save_live_analysis_event(player, session, cleaned_data):
    event_type = cleaned_data["event_type"]
    return LiveAnalysisEvent.objects.create(
        player=player,
        session=session,
        created_at=cleaned_data["created_at"],
        match_period=cleaned_data["match_period"],
        minute=cleaned_data["minute"],
        event_type=event_type,
        duration_seconds=cleaned_data.get("duration_seconds") or 0,
        points=LIVE_EVENT_POINTS.get(event_type, 0),
        notes=cleaned_data.get("notes", ""),
    )


def live_analysis_summary(session, lang="pt"):
    if isinstance(session, Player):
        fallback_session = session.live_analysis_sessions.first()
        if fallback_session:
            session = fallback_session
        else:
            events = list(session.live_analysis_events.all()[:40])
            total_points = round(sum(event.points for event in events), 2)
            retention_events = [event.duration_seconds for event in events if event.duration_seconds > 0]
            average_retention = round(sum(retention_events) / len(retention_events), 2) if retention_events else 0
            return {
                "events": [
                    {
                        "label": tr(lang, event.event_type),
                        "created_at": event.created_at,
                        "match_period": tr(lang, getattr(event, "match_period", "first_half")),
                        "minute": getattr(event, "minute", 1),
                        "points": event.points,
                        "duration_seconds": event.duration_seconds,
                        "notes": event.notes,
                    }
                    for event in events
                ],
                "total_points": total_points,
                "average_retention": average_retention,
                "first_half_events": 0,
                "second_half_events": 0,
                "max_minute": 0,
                "mentality_average": 0,
                "strongest_trait": "-",
                "concern_trait": "-",
                "session": None,
                "shortcuts": [
                    {"key": "R", "label": tr(lang, "received")},
                    {"key": "D", "label": tr(lang, "controlled")},
                    {"key": "F", "label": tr(lang, "forward_pass")},
                    {"key": "B", "label": tr(lang, "backward_pass")},
                    {"key": "P", "label": tr(lang, "progressed")},
                    {"key": "C", "label": tr(lang, "cross")},
                    {"key": "S", "label": tr(lang, "shot")},
                    {"key": "G", "label": tr(lang, "goal")},
                    {"key": "L", "label": tr(lang, "dispossessed")},
                    {"key": "T", "label": tr(lang, "tackle_won")},
                ],
            }
    events = list(session.events.all()[:40])
    total_points = round(sum(event.points for event in events), 2)
    retention_events = [event.duration_seconds for event in events if event.duration_seconds > 0]
    average_retention = round(sum(retention_events) / len(retention_events), 2) if retention_events else 0
    first_half_events = sum(1 for event in events if event.match_period == "first_half")
    second_half_events = sum(1 for event in events if event.match_period == "second_half")
    minutes = [event.minute for event in events if event.minute]
    max_minute = max(minutes) if minutes else 0
    mentality_scores = {field: getattr(session, field) for field in MENTALITY_FIELDS}
    strongest_trait_key = max(mentality_scores, key=mentality_scores.get)
    concern_trait_key = min(mentality_scores, key=mentality_scores.get)
    mentality_average = round(sum(mentality_scores.values()) / len(mentality_scores), 2) if mentality_scores else 0
    return {
        "events": [
            {
                "label": tr(lang, event.event_type),
                "created_at": event.created_at,
                "match_period": tr(lang, event.match_period),
                "minute": event.minute,
                "points": event.points,
                "duration_seconds": event.duration_seconds,
                "notes": event.notes,
            }
            for event in events
        ],
        "total_points": total_points,
        "average_retention": average_retention,
        "first_half_events": first_half_events,
        "second_half_events": second_half_events,
        "max_minute": max_minute,
        "mentality_average": mentality_average,
        "strongest_trait": tr(lang, strongest_trait_key),
        "concern_trait": tr(lang, concern_trait_key),
        "session": session,
        "shortcuts": [
            {"key": "R", "label": tr(lang, "received")},
            {"key": "D", "label": tr(lang, "controlled")},
            {"key": "F", "label": tr(lang, "forward_pass")},
            {"key": "B", "label": tr(lang, "backward_pass")},
            {"key": "P", "label": tr(lang, "progressed")},
            {"key": "C", "label": tr(lang, "cross")},
            {"key": "S", "label": tr(lang, "shot")},
            {"key": "G", "label": tr(lang, "goal")},
            {"key": "L", "label": tr(lang, "dispossessed")},
            {"key": "T", "label": tr(lang, "tackle_won")},
        ],
    }


@dataclass
class CSVImportResult:
    created: int
    errors: list


def import_players_from_csv(user, uploaded_file):
    decoded = uploaded_file.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(decoded))
    created = 0
    errors = []
    text_fields = {"name", "position", "league_level", "club_origin"}
    for index, row in enumerate(reader, start=2):
        try:
            cleaned = {}
            for key, value in row.items():
                if key == "current_value":
                    cleaned[key] = Decimal(value)
                elif key == "age":
                    cleaned[key] = int(value)
                elif key in text_fields:
                    cleaned[key] = value
                else:
                    cleaned[key] = float(value)
            save_player_bundle(user, cleaned)
            created += 1
        except Exception as exc:
            errors.append(f"Line {index}: {exc}")
    return CSVImportResult(created=created, errors=errors)


def csv_template_response_content():
    header = [
        "name", "age", "position", "current_value", "league_level", "club_origin",
        "xg", "xa", "passes_pct", "dribbles_pct", "tackles_pct", "high_intensity_distance",
        "final_third_recoveries", "annual_growth", "club_interest", "league_score", "age_factor",
        "club_reputation", "followers", "engagement", "media_mentions", "sponsorships",
        "sentiment_score", "conscientiousness", "adaptability", "resilience",
        "deliberate_practice", "executive_function", "leadership",
    ]
    sample = [
        "Joao Prospect", "21", "Winger", "2500000", "Serie A Brazil", "EC Bahia",
        "0.32", "0.19", "84", "71", "58", "10800", "6", "18", "74", "78", "82", "69",
        "1250000", "8.6", "120", "4", "76", "81", "79", "77", "83", "74", "72",
    ]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerow(sample)
    return buffer.getvalue()


def generate_pdf_report(player, lang="pt"):
    scores = calculate_scores(player, lang)
    lines = [
        "HB Eleven Valuation System",
        f"Player: {player.name}",
        f"Position: {player.position}",
        f"Age: {player.age}",
        f"Club Origin: {player.club_origin}",
        f"League Level: {player.league_level}",
        f"Current Value: EUR {player.current_value}",
        f"Projected Value: EUR {scores['projected_value']}",
        f"Valuation Score: {scores['valuation_score']}",
        f"Growth Category: {scores['growth_potential_label']}",
        f"Performance Score: {scores['performance_score']}",
        f"Market Score: {scores['market_score']}",
        f"Marketing Score: {scores['marketing_score']}",
        f"Behavior Score: {scores['behavior_score']}",
        f"Percentile Rank: {calculate_percentile(player)}",
    ]
    stream_commands = ["BT", "/F1 16 Tf", "50 780 Td"]
    for index, line in enumerate(lines):
        if index:
            stream_commands.append("0 -22 Td")
        safe_line = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream_commands.append(f"({safe_line}) Tj")
    stream_commands.append("ET")
    page_stream = "\n".join(stream_commands).encode("latin-1", errors="ignore")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n",
        f"4 0 obj << /Length {len(page_stream)} >> stream\n".encode("latin-1") + page_stream + b"\nendstream endobj\n",
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)
    xref_position = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode("latin-1"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_position}\n%%EOF".encode("latin-1"))
    return bytes(pdf)
