import csv
import io
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from email.utils import parsedate_to_datetime
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from django.utils import timezone

from django.db import transaction

from valuation.career_services import case_completion
from valuation.constants import normalize_position_value
from valuation.i18n import tr
from catalog.models import Country, Division
from clubs.models import Club
from valuation.models import (
    AnalystNote,
    AthleteContract,
    AthleteTransfer,
    AthleteIdentity,
    AthleteSnapshot,
    AthleteCareerEntry,
    BehaviorMetrics,
    BehaviorSnapshot,
    CareerIntelligenceCase,
    DataSourceLog,
    DevelopmentPlan,
    HBXValueProfile,
    LiveAnalysisEvent,
    LiveAnalysisSession,
    MarketMetrics,
    MarketSnapshot,
    MarketingMetrics,
    MarketingSnapshot,
    GoCarrieraCheckIn,
    OnBallEvent,
    PerformanceMetrics,
    PerformanceSnapshot,
    Player,
    PlayerHistory,
    ProjectionSnapshot,
    ProgressTracking,
    ScoreSnapshot,
)


RANGES = {
    "xg_xa": (0, 1.5),
    "passes_pct": (0, 100),
    "dribbles_pct": (0, 100),
    "tackles_pct": (0, 100),
    "high_intensity_distance": (0, 14000),
    "final_third_recoveries": (0, 15),
    "annual_growth": (-20, 60),
    "club_interest": (0, 100),
    "league_score": (0, 100),
    "age_factor": (0, 100),
    "club_reputation": (0, 100),
    "followers": (0, 500000),
    "engagement": (0, 12),
    "media_mentions": (0, 100),
    "sponsorships": (0, 10),
    "sentiment_score": (0, 100),
}

POSITION_PERFORMANCE_RANGES = {
    "volante": {
        "xg": (0.00, 0.35),
        "xa": (0.00, 0.30),
        "passes_pct": (60, 95),
        "dribbles_pct": (35, 85),
        "tackles_pct": (35, 90),
        "high_intensity_distance": (500, 14000),
        "final_third_recoveries": (0, 8),
    },
    "meia": {
        "xg": (0.00, 0.50),
        "xa": (0.00, 0.45),
        "passes_pct": (60, 92),
        "dribbles_pct": (35, 85),
        "tackles_pct": (20, 75),
        "high_intensity_distance": (500, 13500),
        "final_third_recoveries": (0, 7),
    },
    "atacante": {
        "xg": (0.00, 0.90),
        "xa": (0.00, 0.40),
        "passes_pct": (50, 88),
        "dribbles_pct": (30, 85),
        "tackles_pct": (10, 55),
        "high_intensity_distance": (450, 13000),
        "final_third_recoveries": (0, 7),
    },
    "ponta": {
        "xg": (0.00, 0.70),
        "xa": (0.00, 0.50),
        "passes_pct": (50, 88),
        "dribbles_pct": (30, 90),
        "tackles_pct": (10, 60),
        "high_intensity_distance": (500, 14000),
        "final_third_recoveries": (0, 8),
    },
    "defensor": {
        "xg": (0.00, 0.20),
        "xa": (0.00, 0.20),
        "passes_pct": (55, 94),
        "dribbles_pct": (20, 75),
        "tackles_pct": (35, 95),
        "high_intensity_distance": (450, 12500),
        "final_third_recoveries": (0, 5),
    },
    "goleiro": {
        "xg": (0.00, 0.05),
        "xa": (0.00, 0.05),
        "passes_pct": (45, 90),
        "dribbles_pct": (0, 30),
        "tackles_pct": (0, 20),
        "high_intensity_distance": (50, 4000),
        "final_third_recoveries": (0, 1),
    },
}

PERFORMANCE_WEIGHTS = {
    "xg": 0.15,
    "xa": 0.15,
    "passes_pct": 0.15,
    "dribbles_pct": 0.15,
    "tackles_pct": 0.15,
    "high_intensity_distance": 0.15,
    "final_third_recoveries": 0.10,
}

FINAL_WEIGHTS = {
    "performance": 0.35,
    "market": 0.20,
    "marketing": 0.10,
    "behavioral": 0.15,
    "potential": 0.20,
}


def clamp(value, minimum=0, maximum=100):
    return max(minimum, min(maximum, value))


def normalize_range(value, min_value, max_value):
    if value is None or max_value <= min_value:
        return 0.0
    score = ((float(value) - min_value) / (max_value - min_value)) * 100.0
    return round(clamp(score), 2)


def normalize(value, range_key):
    min_value, max_value = RANGES[range_key]
    return normalize_range(value, min_value, max_value)


def normalize_mentions(value):
    return clamp((float(value) / 250) * 100)


def growth_label(score, lang="pt"):
    if score > 80:
        return tr(lang, "elite_prospect")
    if score >= 65:
        return tr(lang, "high_potential")
    if score >= 50:
        return tr(lang, "developing")
    return tr(lang, "low_projection")


@dataclass
class AthleteInput:
    position_group: str
    age: int | None = None
    xg: float | None = None
    xa: float | None = None
    passes_pct: float | None = None
    dribbles_pct: float | None = None
    tackles_pct: float | None = None
    high_intensity_distance: float | None = None
    final_third_recoveries: float | None = None
    annual_growth: float | None = None
    club_interest: float | None = None
    league_score: float | None = None
    age_factor: float | None = None
    club_reputation: float | None = None
    followers: float | None = None
    engagement: float | None = None
    media_mentions: float | None = None
    sponsorships: float | None = None
    sentiment_score: float | None = None
    conscientiousness: float | None = None
    adaptability: float | None = None
    resilience: float | None = None
    deliberate_practice: float | None = None
    executive_function: float | None = None
    leadership: float | None = None
    training_environment_score: float | None = None
    trajectory_score: float | None = None


def _position_group_from_player(player):
    position = normalize_position_value(player.position).lower()
    if "gole" in position:
        return "goleiro"
    if "zague" in position or "defen" in position:
        return "defensor"
    if "volante" in position:
        return "volante"
    if "meia" in position or "armador" in position or "mid" in position:
        return "meia"
    if "ponta" in position or "wing" in position or "extremo" in position:
        return "ponta"
    if "ata" in position or "forward" in position or "striker" in position or "centro" in position:
        return "atacante"
    return "meia"


def _coerce_behavioral_score(value):
    numeric = float(value or 0)
    if numeric <= 10:
        return clamp(numeric * 10)
    return clamp(numeric)


def _weighted_average_dict(items):
    total_weight = sum(weight for _, weight in items.values())
    if total_weight <= 0:
        return 0.0
    total_score = sum(score * weight for score, weight in items.values())
    return round(total_score / total_weight, 2)


def _score_age_by_table(age):
    if age is None:
        return 0.0
    if age <= 16:
        return 95.0
    if age >= 25:
        return 55.0
    age_table = {16: 95, 17: 92, 18: 88, 19: 84, 20: 80, 21: 75, 22: 70, 23: 65, 24: 60, 25: 55}
    return float(age_table.get(age, 55.0))


def _classification_label(score):
    if score <= 39:
        return "baixo nivel competitivo atual"
    if score <= 54:
        return "atleta em formacao"
    if score <= 69:
        return "atleta promissor"
    if score <= 84:
        return "alto valor esportivo"
    return "elite / projecao elite"


def _traffic_light_label(score):
    if score <= 54:
        return "vermelho"
    if score <= 69:
        return "amarelo"
    if score <= 84:
        return "verde"
    return "azul elite"


def _derived_training_environment_score(player):
    if float(player.training_environment_score or 0) > 0:
        return round(clamp(player.training_environment_score), 2)
    market = player.market_metrics
    return round((clamp(market.league_score) * 0.45) + (clamp(market.club_reputation) * 0.55), 2)


def _derived_trajectory_score(player):
    if float(player.trajectory_score or 0) > 0:
        return round(clamp(player.trajectory_score), 2)
    market = player.market_metrics
    performance = player.performance_metrics
    performance_signal = normalize_range((float(performance.xg or 0) + float(performance.xa or 0)), 0, 1.2)
    growth_signal = normalize(market.annual_growth, "annual_growth")
    return round((growth_signal * 0.55) + (clamp(market.age_factor) * 0.20) + (performance_signal * 0.25), 2)


def _athlete_input_from_player(player):
    performance = player.performance_metrics
    market = player.market_metrics
    marketing = player.marketing_metrics
    behavior = player.behavior_metrics
    return AthleteInput(
        position_group=_position_group_from_player(player),
        age=player.age,
        xg=performance.xg,
        xa=performance.xa,
        passes_pct=performance.passes_pct,
        dribbles_pct=performance.dribbles_pct,
        tackles_pct=performance.tackles_pct,
        high_intensity_distance=performance.high_intensity_distance,
        final_third_recoveries=performance.final_third_recoveries,
        annual_growth=market.annual_growth,
        club_interest=market.club_interest,
        league_score=market.league_score,
        age_factor=market.age_factor,
        club_reputation=market.club_reputation,
        followers=marketing.followers,
        engagement=marketing.engagement,
        media_mentions=marketing.media_mentions,
        sponsorships=marketing.sponsorships,
        sentiment_score=marketing.sentiment_score,
        conscientiousness=behavior.conscientiousness,
        adaptability=behavior.adaptability,
        resilience=behavior.resilience,
        deliberate_practice=behavior.deliberate_practice,
        executive_function=behavior.executive_function,
        leadership=behavior.leadership,
        training_environment_score=_derived_training_environment_score(player),
        trajectory_score=_derived_trajectory_score(player),
    )


def _score_potential_from_components(age, market_score, behavioral_score, training_environment_score, trajectory_score):
    items = {
        "age": (_score_age_by_table(age), 0.30),
        "training_environment": (clamp(training_environment_score or 0), 0.20),
        "trajectory": (clamp(trajectory_score or 0), 0.20),
        "behavioral": (clamp(behavioral_score or 0), 0.15),
        "market": (clamp(market_score or 0), 0.15),
    }
    return _weighted_average_dict(items)


def _historical_age(player, snapshot_date):
    if player.birth_date and snapshot_date:
        return snapshot_date.year - player.birth_date.year - (
            (snapshot_date.month, snapshot_date.day) < (player.birth_date.month, player.birth_date.day)
        )
    return player.age


def calculate_scores(player, lang="pt"):
    athlete = _athlete_input_from_player(player)
    ranges = POSITION_PERFORMANCE_RANGES.get(athlete.position_group, POSITION_PERFORMANCE_RANGES["meia"])
    performance_items = {
        metric: (normalize_range(getattr(athlete, metric), *ranges[metric]), weight)
        for metric, weight in PERFORMANCE_WEIGHTS.items()
    }
    performance_score = _weighted_average_dict(performance_items)
    market_score = _weighted_average_dict(
        {
            "annual_growth": (normalize(athlete.annual_growth, "annual_growth"), 0.25),
            "club_interest": (clamp(athlete.club_interest or 0), 0.20),
            "league_score": (clamp(athlete.league_score or 0), 0.20),
            "age_factor": (clamp(athlete.age_factor or 0), 0.20),
            "club_reputation": (clamp(athlete.club_reputation or 0), 0.15),
        }
    )
    marketing_score = _weighted_average_dict(
        {
            "followers": (normalize(athlete.followers, "followers"), 0.25),
            "engagement": (normalize(athlete.engagement, "engagement"), 0.25),
            "media_mentions": (normalize(athlete.media_mentions, "media_mentions"), 0.20),
            "sponsorships": (normalize(athlete.sponsorships, "sponsorships"), 0.15),
            "sentiment_score": (clamp(athlete.sentiment_score or 0), 0.15),
        }
    )
    behavioral_score = _weighted_average_dict(
        {
            "conscientiousness": (_coerce_behavioral_score(athlete.conscientiousness), 0.20),
            "adaptability": (_coerce_behavioral_score(athlete.adaptability), 0.15),
            "resilience": (_coerce_behavioral_score(athlete.resilience), 0.20),
            "deliberate_practice": (_coerce_behavioral_score(athlete.deliberate_practice), 0.20),
            "executive_function": (_coerce_behavioral_score(athlete.executive_function), 0.15),
            "leadership": (_coerce_behavioral_score(athlete.leadership), 0.10),
        }
    )
    potential_score = _score_potential_from_components(
        athlete.age,
        market_score,
        behavioral_score,
        athlete.training_environment_score,
        athlete.trajectory_score,
    )
    base_final_score = round(
        (performance_score * FINAL_WEIGHTS["performance"])
        + (market_score * FINAL_WEIGHTS["market"])
        + (marketing_score * FINAL_WEIGHTS["marketing"])
        + (behavioral_score * FINAL_WEIGHTS["behavioral"])
        + (potential_score * FINAL_WEIGHTS["potential"]),
        2,
    )
    adjustment = 0.0
    if athlete.age is not None and athlete.age <= 18 and performance_score >= 70 and potential_score >= 80:
        adjustment += 5.0
    if marketing_score >= 65 and float(athlete.sentiment_score or 0) >= 75:
        adjustment += 2.0
    if performance_score < 45 and behavioral_score < 50:
        adjustment -= 6.0
    if marketing_score > 75 and performance_score < 40:
        adjustment -= 5.0
    if athlete.age is not None and athlete.age > 21 and potential_score < 60 and market_score < 55:
        adjustment -= 4.0

    final_score = round(clamp(base_final_score + adjustment), 2)
    projected_value = (
        player.current_value * (Decimal("1") + Decimal(str(final_score)) / Decimal("100"))
    ).quantize(Decimal("0.01"))
    return {
        "performance_score": performance_score,
        "market_score": market_score,
        "marketing_score": marketing_score,
        "behavior_score": behavioral_score,
        "behavioral_score": behavioral_score,
        "potential_score": potential_score,
        "base_final_score": base_final_score,
        "adjustment": round(adjustment, 2),
        "final_score": final_score,
        "valuation_score": final_score,
        "projected_value": projected_value,
        "growth_potential_label": growth_label(final_score, lang),
        "classification": _classification_label(final_score),
        "traffic_light": _traffic_light_label(final_score),
        "position_group": athlete.position_group,
    }


def ensure_athlete_identity(player):
    identity, _ = AthleteIdentity.objects.get_or_create(
        player=player,
        defaults={"status_label": player.squad_status or player.category or ""},
    )
    return identity


def _metric_payload(instance, fields):
    if instance is None:
        return {field: 0 for field in fields}
    return {field: getattr(instance, field, 0) for field in fields}


def _player_identity_payload(player, identity):
    country = player.division_reference.country.name if player.division_reference_id else ""
    return {
        "player_uuid": str(identity.player_uuid),
        "name": player.name,
        "public_name": player.public_name,
        "birth_date": player.birth_date.isoformat() if player.birth_date else "",
        "age": player.age,
        "nationality": player.nationality,
        "secondary_nationalities": identity.secondary_nationalities,
        "current_country": country,
        "passports": identity.passports,
        "international_eligibility": identity.international_eligibility,
        "dominant_foot": player.dominant_foot,
        "position": player.position,
        "secondary_positions": player.secondary_positions,
        "category": player.category,
        "squad_status": player.squad_status,
        "height_cm": player.height_cm,
        "weight_kg": player.weight_kg,
        "external_ids": identity.external_ids,
    }


def _player_career_payload(player):
    current_contract = player.contracts.filter(is_current=True).order_by("-id").first()
    return {
        "current_club": player.club_reference.short_name if player.club_reference_id and player.club_reference.short_name else player.club_origin,
        "current_league": player.division_reference.short_name if player.division_reference_id and player.division_reference.short_name else player.league_level,
        "current_country": player.division_reference.country.name if player.division_reference_id else "",
        "contract_months_remaining": player.contract_months_remaining,
        "current_value": float(player.current_value),
        "athlete_objectives": player.athlete_objectives,
        "profile_notes": player.profile_notes,
        "career_entries_count": player.career_entries.count(),
        "transfers_count": player.transfers.count(),
        "current_contract": {
            "club_name": current_contract.club_name,
            "status": current_contract.status,
            "end_date": current_contract.end_date.isoformat() if current_contract.end_date else "",
        } if current_contract else {},
    }


def _source_confidence(source):
    confidence_by_source = {
        DataSourceLog.SourceType.GO_CARRIERA: 85,
        DataSourceLog.SourceType.API: 80,
        DataSourceLog.SourceType.MATCH_ANALYSIS: 75,
        DataSourceLog.SourceType.HBX_VALUE: 70,
        DataSourceLog.SourceType.IMPORT: 65,
        DataSourceLog.SourceType.MANUAL: 55,
        DataSourceLog.SourceType.AI: 50,
        DataSourceLog.SourceType.SYSTEM: 50,
    }
    return confidence_by_source.get(source, 50)


def _json_safe(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _upsert_snapshot(model, player, snapshot_date, source, defaults):
    snapshot, _ = model.objects.update_or_create(
        player=player,
        snapshot_date=snapshot_date,
        source=source,
        defaults=defaults,
    )
    return snapshot


def save_athlete_360_snapshots(player, snapshot_date=None, source=DataSourceLog.SourceType.SYSTEM, related_report=None, payload=None):
    snapshot_date = snapshot_date or timezone.localdate()
    confidence = _source_confidence(source)
    identity = ensure_athlete_identity(player)
    scores = calculate_scores(player)
    performance = getattr(player, "performance_metrics", None)
    market = getattr(player, "market_metrics", None)
    marketing = getattr(player, "marketing_metrics", None)
    behavior = getattr(player, "behavior_metrics", None)
    performance_payload = _metric_payload(
        performance,
        ("xg", "xa", "passes_pct", "dribbles_pct", "tackles_pct", "high_intensity_distance", "final_third_recoveries"),
    )
    market_payload = _metric_payload(
        market,
        ("annual_growth", "club_interest", "league_score", "age_factor", "club_reputation"),
    )
    marketing_payload = _metric_payload(
        marketing,
        (
            "instagram_followers",
            "instagram_engagement",
            "tiktok_followers",
            "tiktok_engagement",
            "x_followers",
            "x_engagement",
            "youtube_subscribers",
            "youtube_avg_views",
            "followers",
            "engagement",
            "media_mentions",
            "sponsorships",
            "sentiment_score",
        ),
    )
    behavior_payload = _metric_payload(
        behavior,
        ("conscientiousness", "adaptability", "resilience", "deliberate_practice", "executive_function", "leadership"),
    )
    data_log = DataSourceLog.objects.create(
        player=player,
        source_type=source,
        source_name="HBX 360 Snapshot",
        reference_id=str(getattr(related_report, "id", "")) if related_report else "",
        confidence_score=confidence,
        payload=_json_safe(payload or {}),
    )
    athlete_snapshot = _upsert_snapshot(
        AthleteSnapshot,
        player,
        snapshot_date,
        source,
        {
            "identity_payload": _player_identity_payload(player, identity),
            "career_payload": _player_career_payload(player),
            "data_confidence_score": confidence,
        },
    )
    performance_snapshot = _upsert_snapshot(
        PerformanceSnapshot,
        player,
        snapshot_date,
        source,
        {
            "related_report": related_report,
            "performance_score": scores["performance_score"],
            "output_score": clamp((scores["performance_score"] * 0.6) + (scores["potential_score"] * 0.4)),
            "positional_fit_score": clamp(scores["performance_score"]),
            "consistency_score": clamp(scores["behavior_score"]),
            "context_score": clamp(scores["market_score"]),
            "data_confidence_score": confidence,
            "metrics_payload": performance_payload,
        },
    )
    behavior_snapshot = _upsert_snapshot(
        BehaviorSnapshot,
        player,
        snapshot_date,
        source,
        {
            "behavior_score": scores["behavior_score"],
            "readiness_score": clamp((scores["behavior_score"] * 0.65) + (scores["performance_score"] * 0.35)),
            "habit_score": clamp((behavior_payload["conscientiousness"] + behavior_payload["deliberate_practice"]) * 5),
            "emotional_stability_score": clamp((behavior_payload["resilience"] + behavior_payload["adaptability"]) * 5),
            "professionalism_score": clamp((behavior_payload["conscientiousness"] + behavior_payload["leadership"]) * 5),
            "adherence_score": clamp(behavior_payload["deliberate_practice"] * 10),
            "consistency_score": clamp(scores["behavior_score"]),
            "injury_recovery_behavior_score": 0,
            "engagement_score": clamp((behavior_payload["leadership"] + behavior_payload["executive_function"]) * 5),
            "data_confidence_score": confidence,
            "metrics_payload": behavior_payload,
        },
    )
    market_snapshot = _upsert_snapshot(
        MarketSnapshot,
        player,
        snapshot_date,
        source,
        {
            "market_score": scores["market_score"],
            "current_value": player.current_value,
            "projected_value": scores["projected_value"],
            "contract_timing_score": clamp(100 - float(player.contract_months_remaining or 0)),
            "league_context_score": clamp(market_payload["league_score"]),
            "club_reputation_score": clamp(market_payload["club_reputation"]),
            "data_confidence_score": confidence,
            "metrics_payload": market_payload,
        },
    )
    marketing_snapshot = _upsert_snapshot(
        MarketingSnapshot,
        player,
        snapshot_date,
        source,
        {
            "marketing_score": scores["marketing_score"],
            "media_attention_score": clamp(marketing_payload["media_mentions"]),
            "exposure_performance_ratio": clamp((scores["marketing_score"] / max(scores["performance_score"], 1)) * 50),
            "narrative_sentiment_score": clamp(marketing_payload["sentiment_score"]),
            "authority_score": clamp((marketing_payload["engagement"] * 5) + (marketing_payload["sponsorships"] * 5)),
            "growth_momentum_score": clamp(market_payload["annual_growth"]),
            "buzz_stability_score": clamp((scores["marketing_score"] + scores["market_score"]) / 2),
            "data_confidence_score": confidence,
            "metrics_payload": marketing_payload,
        },
    )
    scores_payload = {
        key: (float(value) if isinstance(value, Decimal) else value)
        for key, value in scores.items()
    }
    score_snapshot = _upsert_snapshot(
        ScoreSnapshot,
        player,
        snapshot_date,
        source,
        {
            "performance_score": scores["performance_score"],
            "market_score": scores["market_score"],
            "marketing_score": scores["marketing_score"],
            "behavior_score": scores["behavior_score"],
            "potential_score": scores["potential_score"],
            "final_score": scores["final_score"],
            "adjustment": scores["adjustment"],
            "classification": scores["classification"],
            "traffic_light": scores["traffic_light"],
            "data_confidence_score": confidence,
            "scores_payload": scores_payload,
        },
    )
    projection_snapshot = _upsert_snapshot(
        ProjectionSnapshot,
        player,
        snapshot_date,
        source,
        {
            "potential_score": scores["potential_score"],
            "projected_value": scores["projected_value"],
            "growth_velocity_score": clamp(market_payload["annual_growth"]),
            "stagnation_risk_score": clamp(100 - scores["potential_score"]),
            "adaptation_probability_score": clamp((scores["behavior_score"] + scores["market_score"]) / 2),
            "opportunity_window": "curto prazo" if scores["market_score"] >= 70 else "desenvolvimento",
            "data_confidence_score": confidence,
            "projection_payload": {
                "growth_potential_label": scores["growth_potential_label"],
                "current_value": float(player.current_value),
                "projected_value": float(scores["projected_value"]),
            },
        },
    )
    return {
        "data_log": data_log,
        "athlete": athlete_snapshot,
        "performance": performance_snapshot,
        "behavior": behavior_snapshot,
        "market": market_snapshot,
        "marketing": marketing_snapshot,
        "score": score_snapshot,
        "projection": projection_snapshot,
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
        "Potential": scores["potential_score"],
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


def _hbx_narrative_label(mpi, performance_impact, correlation):
    if performance_impact >= 78 and correlation >= 72:
        return "Decisivo"
    if mpi >= 70 and performance_impact >= 62:
        return "Promissor"
    if mpi < 45 and correlation < 45:
        return "Irregular"
    return "Consistente"


def _hbx_trend_label(mpi, performance_impact):
    if mpi >= 70 or performance_impact >= 72:
        return "Crescimento"
    if mpi <= 45 and performance_impact <= 45:
        return "Queda"
    return "Estavel"


def _hbx_build_insights(values, mpi, performance_impact, correlation, narrative):
    insights = []
    if values["performance_rating"] >= 70 and correlation < 55:
        insights.append("Boa atuacao sem resposta proporcional do mercado. Prioridade para comunicacao, clipping e amplificacao de highlights.")
    if values["sentiment_score"] < 55:
        insights.append("Sentimento abaixo do ideal. Revisar narrativa publica, entrevistas, tom de cobertura e contexto de performance.")
    if values["mention_momentum"] >= 70 and values["source_relevance"] < 60:
        insights.append("O volume cresceu, mas em fontes pouco relevantes. Buscar validacao por jornalistas, scouts e canais de autoridade.")
    if values["performance_rating"] < 60:
        insights.append("A base tecnica ainda limita a valorizacao. O foco deve ser ganho de performance antes de aumentar exposicao.")
    if narrative == "Decisivo":
        insights.append("Momento favoravel para consolidar posicionamento premium com provas de impacto competitivo e recorrencia.")
    if not insights:
        insights.append("Performance e percepcao caminham de forma equilibrada. O proximo passo e aumentar recorrencia e tracao em fontes de maior alcance.")
    return insights[:3]


def _safe_text(value):
    return str(value or "").strip()


def _safe_float(value, minimum=0, maximum=100):
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = 0.0
    return clamp(numeric, minimum, maximum)


def _safe_int(value):
    try:
        numeric = int(float(value))
    except (TypeError, ValueError):
        numeric = 0
    return max(numeric, 0)


def _average(values):
    valid = [float(item) for item in values]
    if not valid:
        return 0.0
    return round(sum(valid) / len(valid), 2)


def _coalesce_metric(value, fallback):
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = 0.0
    return numeric if numeric > 0 else fallback


def _zero_if_none(value):
    return 0 if value is None else value


def _weighted_average(weighted_values):
    total_weight = 0.0
    total_value = 0.0
    for value, weight in weighted_values:
        safe_weight = max(float(weight or 0), 0.0)
        total_weight += safe_weight
        total_value += float(value or 0) * safe_weight
    if total_weight <= 0:
        return 0.0
    return round(total_value / total_weight, 2)


def _build_hbx_source_payload(seed):
    instagram_mentions = _safe_int(seed.get("instagram_mentions"))
    google_news_mentions = _safe_int(seed.get("google_news_mentions"))
    youtube_mentions = _safe_int(seed.get("youtube_mentions"))
    tiktok_mentions = _safe_int(seed.get("tiktok_mentions"))
    manual_mentions = _safe_int(seed.get("manual_mentions"))
    return {
        "instagram": {
            "target": {
                "handle": _safe_text(seed.get("instagram_handle")),
            },
            "collected": {
                "mentions": instagram_mentions,
                "momentum": _safe_float(seed.get("instagram_momentum")),
                "sentiment": _safe_float(seed.get("instagram_sentiment")),
                "reach": _safe_float(seed.get("instagram_reach")),
                "authority": _safe_float(seed.get("instagram_authority")),
                "profile": {
                    "username": _safe_text(seed.get("instagram_username")),
                    "name": _safe_text(seed.get("instagram_name")),
                    "biography": _safe_text(seed.get("instagram_biography")),
                    "website": _safe_text(seed.get("instagram_website")),
                    "profile_picture_url": _safe_text(seed.get("instagram_profile_picture_url")),
                    "followers_count": _safe_int(seed.get("instagram_followers_count")),
                    "media_count": _safe_int(seed.get("instagram_media_count")),
                },
            },
        },
        "google_news": {
            "target": {
                "query": _safe_text(seed.get("google_news_query")),
                "rss_url": _safe_text(seed.get("google_news_rss")),
            },
            "collected": {
                "mentions": google_news_mentions,
                "momentum": _safe_float(seed.get("google_news_momentum")),
                "sentiment": _safe_float(seed.get("google_news_sentiment")),
                "reach": _safe_float(seed.get("google_news_reach")),
                "authority": _safe_float(seed.get("google_news_authority")),
                "articles": list(seed.get("google_news_articles") or []),
            },
        },
        "youtube": {
            "target": {
                "channel_id": _safe_text(seed.get("youtube_channel_id")),
                "query": _safe_text(seed.get("youtube_query")),
            },
            "collected": {
                "mentions": youtube_mentions,
                "momentum": _safe_float(seed.get("youtube_momentum")),
                "sentiment": _safe_float(seed.get("youtube_sentiment")),
                "reach": _safe_float(seed.get("youtube_reach")),
                "authority": _safe_float(seed.get("youtube_authority")),
                "videos": list(seed.get("youtube_videos") or []),
            },
        },
        "tiktok": {
            "target": {
                "handle": _safe_text(seed.get("tiktok_handle")),
                "query": _safe_text(seed.get("tiktok_query")),
            },
            "collected": {
                "mentions": tiktok_mentions,
                "momentum": _safe_float(seed.get("tiktok_momentum")),
                "sentiment": _safe_float(seed.get("tiktok_sentiment")),
                "reach": _safe_float(seed.get("tiktok_reach")),
                "authority": _safe_float(seed.get("tiktok_authority")),
                "videos": list(seed.get("tiktok_videos") or []),
            },
        },
        "manual": {
            "target": {
                "context": _safe_text(seed.get("manual_context")),
            },
            "collected": {
                "mentions": manual_mentions,
                "momentum": _safe_float(seed.get("manual_momentum")),
                "sentiment": _safe_float(seed.get("manual_sentiment")),
                "reach": _safe_float(seed.get("manual_reach")),
                "authority": _safe_float(seed.get("manual_authority")),
                "performance_rating": _safe_float(seed.get("manual_performance_rating")),
                "attention_spike": _safe_float(seed.get("manual_attention_spike")),
                "market_response": _safe_float(seed.get("manual_market_response")),
                "visibility_efficiency": _safe_float(seed.get("manual_visibility_efficiency")),
                "qualitative_note": _safe_text(seed.get("manual_note")),
            },
        },
    }


POSITIVE_NEWS_TERMS = (
    "gol", "assist", "destaque", "vit", "convoca", "record", "recorde", "melhor", "promissor", "hero", "brace",
    "winner", "decis", "great", "excel", "star", "talent",
)
NEGATIVE_NEWS_TERMS = (
    "les", "injur", "suspens", "falha", "erro", "crit", "bench", "loan", "crise", "demit", "expuls", "rumor negativo",
)
HIGH_AUTHORITY_SOURCES = (
    "globo", "ge", "espn", "uol", "lance", "terra", "cnn", "band", "folha", "estadao", "goal",
)
YOUTUBE_HIGH_AUTHORITY_CHANNELS = (
    "ge", "espn", "tntsports", "uol", "lance", "cazetv", "goal", "premiere",
)


def _normalize_social_handle(value):
    normalized = _safe_text(value).strip()
    if not normalized:
        return ""
    return normalized[1:] if normalized.startswith("@") else normalized


def fetch_instagram_signals(handle):
    access_token = os.environ.get("INSTAGRAM_GRAPH_ACCESS_TOKEN", "").strip()
    ig_user_id = os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID", "").strip()
    graph_version = os.environ.get("INSTAGRAM_GRAPH_API_VERSION", "v23.0").strip() or "v23.0"
    normalized_handle = _normalize_social_handle(handle)

    if not access_token or not ig_user_id:
        raise RuntimeError("Instagram Graph API nao configurada.")

    if not normalized_handle:
        return {
            "handle": "",
            "username": "",
            "name": "",
            "biography": "",
            "website": "",
            "profile_picture_url": "",
            "followers_count": 0,
            "media_count": 0,
            "mentions": 0,
            "momentum": 0.0,
            "sentiment": 0.0,
            "reach": 0.0,
            "authority": 0.0,
        }

    fields = (
        f"business_discovery.username({normalized_handle})"
        "{username,name,biography,website,profile_picture_url,followers_count,media_count}"
    )
    endpoint = (
        f"https://graph.facebook.com/{graph_version}/{ig_user_id}"
        f"?fields={quote(fields, safe='{}(),_')}&access_token={quote(access_token, safe='')}"
    )
    request = Request(endpoint, method="GET")
    with urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))

    discovery = (payload or {}).get("business_discovery") or {}
    followers_count = _safe_int(discovery.get("followers_count"))
    media_count = _safe_int(discovery.get("media_count"))
    reach = clamp(normalize_range(followers_count, 0, 500000) * 0.75 + normalize_range(media_count, 0, 1000) * 0.25)
    authority = clamp(normalize_range(followers_count, 0, 500000) * 0.7 + normalize_range(media_count, 0, 1000) * 0.3)
    momentum = clamp(35 + normalize_range(media_count, 0, 1000) * 0.45)
    sentiment = 60.0

    return {
        "handle": f"@{normalized_handle}",
        "username": _safe_text(discovery.get("username")) or normalized_handle,
        "name": _safe_text(discovery.get("name")),
        "biography": _safe_text(discovery.get("biography")),
        "website": _safe_text(discovery.get("website")),
        "profile_picture_url": _safe_text(discovery.get("profile_picture_url")),
        "followers_count": followers_count,
        "media_count": media_count,
        "mentions": media_count,
        "momentum": round(momentum, 2),
        "sentiment": round(sentiment, 2),
        "reach": round(reach, 2),
        "authority": round(authority, 2),
    }


def build_google_news_rss_url(query):
    normalized_query = _safe_text(query)
    if not normalized_query:
        return ""
    return f"https://news.google.com/rss/search?q={quote(normalized_query)}&hl=pt-BR&gl=BR&ceid=BR:pt-419"


def _extract_news_source(item):
    source_text = ""
    source_element = item.find("{http://search.yahoo.com/mrss/}source") or item.find("source")
    if source_element is not None and source_element.text:
        source_text = source_element.text.strip()
    if source_text:
        return source_text
    title = _safe_text(item.findtext("title"))
    if " - " in title:
        return title.rsplit(" - ", 1)[-1].strip()
    return ""


def _news_recency_score(published_at):
    if not published_at:
        return 30.0
    now = timezone.now()
    delta = now - published_at
    days = delta.total_seconds() / 86400
    if days <= 1:
        return 100.0
    if days <= 3:
        return 85.0
    if days <= 7:
        return 70.0
    if days <= 14:
        return 55.0
    return 35.0


def _news_sentiment_score(text):
    normalized = _safe_text(text).lower()
    score = 55.0
    score += sum(6 for term in POSITIVE_NEWS_TERMS if term in normalized)
    score -= sum(7 for term in NEGATIVE_NEWS_TERMS if term in normalized)
    return clamp(score)


def _news_authority_score(source_name):
    normalized = _safe_text(source_name).lower()
    if any(term in normalized for term in HIGH_AUTHORITY_SOURCES):
        return 82.0
    if normalized:
        return 62.0
    return 45.0


def fetch_google_news_signals(query, rss_url=""):
    normalized_query = _safe_text(query)
    target_url = _safe_text(rss_url) or build_google_news_rss_url(normalized_query)
    if not normalized_query or not target_url:
        return {
            "query": normalized_query,
            "rss_url": target_url,
            "mentions": 0,
            "momentum": 0.0,
            "sentiment": 0.0,
            "reach": 0.0,
            "authority": 0.0,
            "articles": [],
        }

    with urlopen(target_url, timeout=10) as response:
        payload = response.read()

    root = ElementTree.fromstring(payload)
    items = root.findall(".//item")
    articles = []
    recency_scores = []
    sentiment_scores = []
    authority_scores = []
    unique_sources = set()

    for item in items[:12]:
        title = _safe_text(item.findtext("title"))
        link = _safe_text(item.findtext("link"))
        pub_date_raw = _safe_text(item.findtext("pubDate"))
        source_name = _extract_news_source(item)
        published_at = None
        if pub_date_raw:
            try:
                published_at = parsedate_to_datetime(pub_date_raw)
                if timezone.is_naive(published_at):
                    published_at = timezone.make_aware(published_at, timezone.get_current_timezone())
            except Exception:
                published_at = None
        recency_scores.append(_news_recency_score(published_at))
        sentiment_scores.append(_news_sentiment_score(title))
        authority = _news_authority_score(source_name)
        authority_scores.append(authority)
        if source_name:
            unique_sources.add(source_name.lower())
        articles.append(
            {
                "title": title,
                "link": link,
                "source": source_name,
                "published_at": published_at.isoformat() if published_at else "",
            }
        )

    mentions = len(articles)
    momentum = _average(recency_scores) if recency_scores else 0.0
    sentiment = _average(sentiment_scores) if sentiment_scores else 0.0
    authority = _average(authority_scores) if authority_scores else 0.0
    reach = clamp((mentions * 7) + (len(unique_sources) * 5))
    return {
        "query": normalized_query,
        "rss_url": target_url,
        "mentions": mentions,
        "momentum": round(momentum, 2),
        "sentiment": round(sentiment, 2),
        "reach": round(reach, 2),
        "authority": round(authority, 2),
        "articles": articles,
    }


def _youtube_sentiment_score(text):
    return _news_sentiment_score(text)


def _youtube_authority_score(channel_title):
    normalized = _safe_text(channel_title).lower()
    if any(term in normalized for term in YOUTUBE_HIGH_AUTHORITY_CHANNELS):
        return 84.0
    if normalized:
        return 66.0
    return 45.0


def fetch_youtube_signals(query, channel_id=""):
    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    normalized_query = _safe_text(query)
    normalized_channel_id = _safe_text(channel_id)
    if not api_key:
        raise RuntimeError("YOUTUBE_API_KEY nao configurada.")
    if not normalized_query:
        return {
            "query": normalized_query,
            "channel_id": normalized_channel_id,
            "mentions": 0,
            "momentum": 0.0,
            "sentiment": 0.0,
            "reach": 0.0,
            "authority": 0.0,
            "videos": [],
        }

    params = {
        "part": "snippet",
        "q": normalized_query,
        "type": "video",
        "maxResults": "10",
        "order": "date",
        "regionCode": "BR",
        "relevanceLanguage": "pt",
        "key": api_key,
    }
    if normalized_channel_id:
        params["channelId"] = normalized_channel_id
    endpoint = f"https://www.googleapis.com/youtube/v3/search?{urlencode(params)}"
    with urlopen(endpoint, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))

    items = payload.get("items") or []
    videos = []
    recency_scores = []
    sentiment_scores = []
    authority_scores = []
    total_views_proxy = 0.0

    for item in items:
        snippet = item.get("snippet") or {}
        published_at = None
        published_at_raw = _safe_text(snippet.get("publishedAt"))
        if published_at_raw:
            try:
                published_at = datetime.fromisoformat(published_at_raw.replace("Z", "+00:00"))
                if timezone.is_naive(published_at):
                    published_at = timezone.make_aware(published_at, timezone.get_current_timezone())
            except Exception:
                published_at = None
        title = _safe_text(snippet.get("title"))
        channel_title = _safe_text(snippet.get("channelTitle"))
        recency_scores.append(_news_recency_score(published_at))
        sentiment_scores.append(_youtube_sentiment_score(title))
        authority = _youtube_authority_score(channel_title)
        authority_scores.append(authority)
        recency = _news_recency_score(published_at)
        total_views_proxy += authority + recency
        videos.append(
            {
                "title": title,
                "video_id": _safe_text((item.get("id") or {}).get("videoId")),
                "channel_title": channel_title,
                "published_at": published_at.isoformat() if published_at else "",
            }
        )

    mentions = len(videos)
    momentum = _average(recency_scores) if recency_scores else 0.0
    sentiment = _average(sentiment_scores) if sentiment_scores else 0.0
    authority = _average(authority_scores) if authority_scores else 0.0
    reach = clamp((mentions * 6) + (total_views_proxy / max(mentions, 1)) * 0.35)
    return {
        "query": normalized_query,
        "channel_id": normalized_channel_id,
        "mentions": mentions,
        "momentum": round(momentum, 2),
        "sentiment": round(sentiment, 2),
        "reach": round(reach, 2),
        "authority": round(authority, 2),
        "videos": videos,
    }


def fetch_tiktok_signals(query, handle=""):
    access_token = os.environ.get("TIKTOK_RESEARCH_ACCESS_TOKEN", "").strip()
    normalized_query = _safe_text(query)
    normalized_handle = _safe_text(handle)
    if not access_token:
        raise RuntimeError("TIKTOK_RESEARCH_ACCESS_TOKEN nao configurado.")
    if not normalized_query:
        return {
            "query": normalized_query,
            "handle": normalized_handle,
            "mentions": 0,
            "momentum": 0.0,
            "sentiment": 0.0,
            "reach": 0.0,
            "authority": 0.0,
            "videos": [],
        }

    body = {
        "query": {
            "and": [
                {
                    "operation": "EQ",
                    "field_name": "keyword",
                    "field_values": [normalized_query],
                }
            ]
        },
        "max_count": 10,
        "cursor": 0,
        "start_date": (timezone.now() - timedelta(days=30)).strftime("%Y%m%d"),
        "end_date": timezone.now().strftime("%Y%m%d"),
        "is_random": False,
    }
    endpoint = "https://open.tiktokapis.com/v2/research/video/query/?fields=id,create_time,username,video_description,view_count,like_count,comment_count,share_count"
    request = Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))

    videos = (payload.get("data") or {}).get("videos") or []
    formatted_videos = []
    recency_scores = []
    sentiment_scores = []
    authority_scores = []
    reach_scores = []
    for video in videos:
        create_time = video.get("create_time")
        published_at = None
        if create_time:
            try:
                published_at = datetime.fromtimestamp(int(create_time), tz=timezone.utc)
            except Exception:
                published_at = None
        description = _safe_text(video.get("video_description"))
        username = _safe_text(video.get("username"))
        recency_scores.append(_news_recency_score(published_at))
        sentiment_scores.append(_news_sentiment_score(description))
        authority_scores.append(68.0 if username else 50.0)
        reach_scores.append(
            clamp(
                (float(video.get("view_count") or 0) / 50000) * 45
                + (float(video.get("like_count") or 0) / 10000) * 30
                + (float(video.get("share_count") or 0) / 1000) * 25
            )
        )
        formatted_videos.append(
            {
                "id": str(video.get("id") or ""),
                "username": username,
                "description": description,
                "published_at": published_at.isoformat() if published_at else "",
            }
        )

    mentions = len(formatted_videos)
    return {
        "query": normalized_query,
        "handle": normalized_handle,
        "mentions": mentions,
        "momentum": _average(recency_scores) if recency_scores else 0.0,
        "sentiment": _average(sentiment_scores) if sentiment_scores else 0.0,
        "reach": _average(reach_scores) if reach_scores else 0.0,
        "authority": _average(authority_scores) if authority_scores else 0.0,
        "videos": formatted_videos,
    }


def compute_hbx_value_profile(seed):
    source_payload = _build_hbx_source_payload(seed)
    source_collection = {key: value["collected"] for key, value in source_payload.items()}
    source_targets = {key: value["target"] for key, value in source_payload.items()}
    mention_volume = sum(block.get("mentions", 0) for block in source_collection.values())
    mention_momentum = _weighted_average(
        [(block.get("momentum", 0), block.get("mentions", 0) or 1) for block in source_collection.values()]
    )
    sentiment_score = _weighted_average(
        [(block.get("sentiment", 0), block.get("mentions", 0) or 1) for block in source_collection.values()]
    )
    estimated_reach = _weighted_average(
        [(block.get("reach", 0), block.get("mentions", 0) or 1) for block in source_collection.values()]
    )
    source_relevance = _average([block.get("authority", 0) for block in source_collection.values()])
    manual_collection = source_collection["manual"]
    values = {
        "mention_volume": mention_volume,
        "mention_momentum": mention_momentum,
        "sentiment_score": sentiment_score,
        "estimated_reach": estimated_reach,
        "source_relevance": source_relevance,
        "performance_rating": clamp(
            manual_collection.get("performance_rating") or float(seed.get("performance_rating", 0) or 0)
        ),
        "attention_spike": clamp(
            _weighted_average(
                [
                    (source_collection["instagram"].get("momentum", 0), source_collection["instagram"].get("mentions", 0) or 1),
                    (source_collection["google_news"].get("momentum", 0), source_collection["google_news"].get("mentions", 0) or 1),
                    (source_collection["youtube"].get("momentum", 0), source_collection["youtube"].get("mentions", 0) or 1),
                    (source_collection["tiktok"].get("momentum", 0), source_collection["tiktok"].get("mentions", 0) or 1),
                    (manual_collection.get("attention_spike", 0), 2),
                ]
            )
        ),
        "market_response": clamp(
            manual_collection.get("market_response")
            or float(seed.get("market_response", 0) or 0)
            or _weighted_average(
                [
                    (source_collection["google_news"].get("authority", 0), source_collection["google_news"].get("mentions", 0) or 1),
                    (source_collection["youtube"].get("authority", 0), source_collection["youtube"].get("mentions", 0) or 1),
                    (source_collection["tiktok"].get("reach", 0), source_collection["tiktok"].get("mentions", 0) or 1),
                    (source_collection["instagram"].get("reach", 0), source_collection["instagram"].get("mentions", 0) or 1),
                ]
            )
        ),
        "visibility_efficiency": clamp(
            manual_collection.get("visibility_efficiency")
            or float(seed.get("visibility_efficiency", 0) or 0)
            or _weighted_average(
                [
                    (source_collection["instagram"].get("reach", 0), source_collection["instagram"].get("mentions", 0) or 1),
                    (source_collection["youtube"].get("reach", 0), source_collection["youtube"].get("mentions", 0) or 1),
                    (source_collection["tiktok"].get("reach", 0), source_collection["tiktok"].get("mentions", 0) or 1),
                    (source_collection["google_news"].get("authority", 0), source_collection["google_news"].get("mentions", 0) or 1),
                ]
            )
        ),
    }
    mpi = round(
        normalize_mentions(values["mention_volume"]) * 0.20
        + values["mention_momentum"] * 0.20
        + values["sentiment_score"] * 0.25
        + values["estimated_reach"] * 0.20
        + values["source_relevance"] * 0.15,
        2,
    )
    performance_impact = round(
        values["performance_rating"] * 0.50
        + values["attention_spike"] * 0.30
        + values["market_response"] * 0.20,
        2,
    )
    impact_correlation = round(
        values["performance_rating"] * 0.45
        + values["market_response"] * 0.35
        + values["visibility_efficiency"] * 0.20,
        2,
    )
    narrative_label = _hbx_narrative_label(mpi, performance_impact, impact_correlation)
    trend_label = _hbx_trend_label(mpi, performance_impact)
    market_label = "Percepcao alta" if mpi >= 75 else "Percepcao moderada" if mpi >= 55 else "Percepcao fragil"
    if narrative_label == "Decisivo":
        narrative_summary = "A performance gera repercussao e reforca uma narrativa de impacto imediato no mercado."
    elif narrative_label == "Promissor":
        narrative_summary = "O mercado enxerga crescimento e potencial, mas ainda pede continuidade e validacao."
    elif narrative_label == "Irregular":
        narrative_summary = "A atencao nao se converteu em confianca. O posicionamento precisa de consistencia competitiva."
    else:
        narrative_summary = "O atleta sustenta leitura positiva, embora ainda sem pico maximo de valorizacao."
    return {
        **values,
        "market_perception_index": mpi,
        "performance_impact_score": performance_impact,
        "impact_correlation_score": impact_correlation,
        "trend_label": trend_label,
        "narrative_label": narrative_label,
        "market_label": market_label,
        "narrative_summary": narrative_summary,
        "narrative_keywords": list(seed.get("narrative_keywords") or []),
        "strategic_insights": _hbx_build_insights(values, mpi, performance_impact, impact_correlation, narrative_label),
        "source_targets": source_targets,
        "source_collection": source_collection,
        "delivery_payload": {
            "dashboard": {
                "market_perception_index": mpi,
                "trend_label": trend_label,
                "narrative_label": narrative_label,
                "market_label": market_label,
                "narrative_summary": narrative_summary,
                "source_count": sum(1 for block in source_collection.values() if any(block.values())),
            },
            "integrated_indicators": {
                "mention_volume": mention_volume,
                "sentiment_score": sentiment_score,
                "estimated_reach": estimated_reach,
                "source_relevance": source_relevance,
                "performance_impact_score": performance_impact,
                "impact_correlation_score": impact_correlation,
            },
            "manual_note": manual_collection.get("qualitative_note", ""),
        },
    }


def get_hbx_value_profile(player):
    try:
        return player.hbx_value_profile
    except HBXValueProfile.DoesNotExist:
        return None


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
        career_case = CareerIntelligenceCase.objects.filter(player=player).order_by("-updated_at", "-id").first()
        hbx_profile = get_hbx_value_profile(player)
        latest_live_report = player.live_player_evaluations.order_by("-match_date", "-saved_at", "-id").first()
        latest_live_summary = ""
        if latest_live_report:
            latest_live_summary = (
                str(
                    (latest_live_report.payload or {})
                    .get("avaliacao_geral", {})
                    .get("resumo_do_desempenho", "")
                ).strip()
            )
        completion = case_completion(career_case) if career_case else {}
        payload.append(
            {
                "player": player,
                "scores": scores,
                "percentile": calculate_percentile(player),
                "growth_series": build_growth_series(player),
                "growth_rate": round(calculate_growth_rate(player) * 100, 2),
                "career_case": career_case,
                "career_completion": completion,
                "career_completion_count": sum(1 for ready in completion.values() if ready),
                "hbx_profile": hbx_profile,
                "latest_live_report": latest_live_report,
                "latest_live_summary": latest_live_summary,
            }
        )
    return payload


def sync_integrated_player_modules(player):
    case, created = CareerIntelligenceCase.objects.get_or_create(
        user=player.user,
        player=player,
        defaults={
            "athlete_name": player.name,
            "birth_date": player.birth_date,
            "nationality": player.nationality,
            "position_primary": player.position,
            "secondary_positions": player.secondary_positions,
            "dominant_foot": player.dominant_foot,
            "height_cm": player.height_cm,
            "weight_kg": player.weight_kg,
            "current_club": player.club_origin,
            "category": player.category or CareerIntelligenceCase.Category.PROFESSIONAL,
            "contract_months_remaining": player.contract_months_remaining,
            "squad_status": player.squad_status,
            "athlete_objectives": player.athlete_objectives,
            "analyst_notes": player.profile_notes,
        },
    )
    if created:
        return case

    updated_fields = []
    if case.athlete_name != player.name:
        case.athlete_name = player.name
        updated_fields.append("athlete_name")
    if case.birth_date != player.birth_date:
        case.birth_date = player.birth_date
        updated_fields.append("birth_date")
    if case.nationality != player.nationality:
        case.nationality = player.nationality
        updated_fields.append("nationality")
    if case.position_primary != player.position:
        case.position_primary = player.position
        updated_fields.append("position_primary")
    if case.secondary_positions != player.secondary_positions:
        case.secondary_positions = player.secondary_positions
        updated_fields.append("secondary_positions")
    if case.dominant_foot != player.dominant_foot:
        case.dominant_foot = player.dominant_foot
        updated_fields.append("dominant_foot")
    if case.height_cm != player.height_cm:
        case.height_cm = player.height_cm
        updated_fields.append("height_cm")
    if case.weight_kg != player.weight_kg:
        case.weight_kg = player.weight_kg
        updated_fields.append("weight_kg")
    if case.current_club != player.club_origin:
        case.current_club = player.club_origin
        updated_fields.append("current_club")
    if case.category != (player.category or CareerIntelligenceCase.Category.PROFESSIONAL):
        case.category = player.category or CareerIntelligenceCase.Category.PROFESSIONAL
        updated_fields.append("category")
    if case.contract_months_remaining != player.contract_months_remaining:
        case.contract_months_remaining = player.contract_months_remaining
        updated_fields.append("contract_months_remaining")
    if case.squad_status != player.squad_status:
        case.squad_status = player.squad_status
        updated_fields.append("squad_status")
    if case.athlete_objectives != player.athlete_objectives:
        case.athlete_objectives = player.athlete_objectives
        updated_fields.append("athlete_objectives")
    if player.profile_notes and case.analyst_notes != player.profile_notes:
        case.analyst_notes = player.profile_notes
        updated_fields.append("analyst_notes")
    if updated_fields:
        updated_fields.append("updated_at")
        case.save(update_fields=updated_fields)
    return case


def _division_name_candidates(raw_name):
    normalized = str(raw_name or "").strip()
    if not normalized:
        return []
    lowered = normalized.lower()
    candidates = [normalized]
    if lowered.startswith("serie ") or lowered.startswith("série "):
        suffix = normalized.split(" ", 1)[1].strip()
        candidates.extend(
            [
                f"Campeonato Brasileiro Série {suffix}",
                f"Campeonato Brasileiro Serie {suffix}",
            ]
        )
    return list(dict.fromkeys(candidate for candidate in candidates if candidate))


def resolve_division_and_club(division_name, club_name, country_code="BRA"):
    division_name = str(division_name or "").strip()
    club_name = str(club_name or "").strip()
    country_code = str(country_code or "BRA").strip().upper()
    if not division_name and not club_name:
        return None, None

    country_defaults = {
        "BRA": {
            "name": "Brasil",
            "alternative_names": "Brazil",
        },
        "PRT": {
            "name": "Portugal",
            "alternative_names": "Portuguese Republic",
        },
        "ESP": {
            "name": "Espanha",
            "alternative_names": "Spain, Reino de Espanha",
        },
        "ITA": {
            "name": "Itália",
            "alternative_names": "Italy, Repubblica Italiana",
        },
        "FRA": {
            "name": "França",
            "alternative_names": "France, République française",
        },
        "DEU": {
            "name": "Alemanha",
            "alternative_names": "Germany, Deutschland",
        },
        "ENG": {
            "name": "Inglaterra",
            "alternative_names": "England",
        },
        "SAU": {
            "name": "Arábia Saudita",
            "alternative_names": "Saudi Arabia, Kingdom of Saudi Arabia",
        },
        "USA": {
            "name": "Estados Unidos",
            "alternative_names": "United States, United States of America, USA",
        },
        "ARG": {
            "name": "Argentina",
            "alternative_names": "Argentine Republic, República Argentina",
        },
        "MEX": {
            "name": "México",
            "alternative_names": "Mexico, Estados Unidos Mexicanos",
        },
        "NLD": {
            "name": "Holanda",
            "alternative_names": "Netherlands, Nederland, Países Baixos",
        },
    }
    country, _ = Country.objects.get_or_create(
        code=country_code,
        defaults={
            "name": country_defaults.get(country_code, {}).get("name", country_code),
            "alternative_names": country_defaults.get(country_code, {}).get("alternative_names", ""),
            "is_active": True,
        },
    )

    division = None
    for candidate in _division_name_candidates(division_name):
        division = (
            Division.objects.filter(country=country, name__iexact=candidate).first()
            or Division.objects.filter(country=country, short_name__iexact=candidate).first()
        )
        if division:
            break

    if division is None and division_name:
        inferred_level = None
        normalized_division = division_name.lower()
        for level, token in ((1, "a"), (2, "b"), (3, "c"), (4, "d")):
            if normalized_division in {f"serie {token}", f"série {token}"}:
                inferred_level = level
                break
        division = Division.objects.create(
            country=country,
            name=division_name,
            short_name=division_name,
            scope=Division.Scope.NATIONAL if inferred_level else Division.Scope.OTHER,
            level=inferred_level,
            is_active=True,
        )

    club = None
    if division and club_name:
        club = Club.objects.filter(country=country, division=division, official_name__iexact=club_name).first()
        if club is None:
            club = Club.objects.filter(country=country, division=division, short_name__iexact=club_name).first()
        if club is None:
            club = Club.objects.create(
                country=country,
                division=division,
                official_name=club_name,
                short_name=club_name,
                status=Club.Status.ACTIVE,
            )

    return division, club


def _live_report_note_fields(report):
    payload = report.payload or {}
    evaluation = payload.get("avaliacao_geral", {})
    summary = str(evaluation.get("resumo_do_desempenho") or "").strip()
    strengths = str(evaluation.get("pontos_fortes") or "").strip()
    weaknesses = str(evaluation.get("pontos_a_melhorar") or "").strip()

    title_bits = [f"Analise ao vivo {report.match_date:%d/%m/%Y}"]
    if report.competition:
        title_bits.append(report.competition)
    if report.opponent:
        title_bits.append(f"vs {report.opponent}")

    header = " | ".join(title_bits)
    analysis_lines = [header]
    if summary:
        analysis_lines.append(summary)
    if report.minutes_played:
        analysis_lines.append(f"Minutos observados: {report.minutes_played}.")
    return {
        "analysis_text": "\n".join(analysis_lines),
        "strengths": strengths,
        "weaknesses": weaknesses,
    }


def sync_live_report_to_integrated_modules(player, report):
    case = sync_integrated_player_modules(player)
    save_player_history_snapshot(
        player,
        report.match_date,
        source=DataSourceLog.SourceType.MATCH_ANALYSIS,
        related_report=report,
        payload={"report_id": report.id, "competition": report.competition, "opponent": report.opponent},
    )

    note_defaults = _live_report_note_fields(report)
    live_note = (
        AnalystNote.objects.filter(player=player, date=report.match_date, analysis_text__startswith="Analise ao vivo ")
        .order_by("-id")
        .first()
    )
    if live_note:
        live_note.analysis_text = note_defaults["analysis_text"]
        live_note.strengths = note_defaults["strengths"]
        live_note.weaknesses = note_defaults["weaknesses"]
        live_note.save(update_fields=["analysis_text", "strengths", "weaknesses"])
    else:
        AnalystNote.objects.create(player=player, date=report.match_date, **note_defaults)

    case_updates = []
    if report.team and case.current_club != report.team:
        case.current_club = report.team
        case_updates.append("current_club")
    live_summary = note_defaults["analysis_text"]
    if live_summary and live_summary not in (case.analyst_notes or ""):
        case.analyst_notes = (
            f"{case.analyst_notes}\n\n{live_summary}".strip()
            if case.analyst_notes else live_summary
        )
        case_updates.append("analyst_notes")
    if case_updates:
        case_updates.append("updated_at")
        case.save(update_fields=case_updates)
    from valuation.ai_service import refresh_ai_insights_for_player

    refresh_ai_insights_for_player(player)
    return case


def save_hbx_value_profile(player, cleaned_data, source=HBXValueProfile.Source.MANUAL):
    computed = compute_hbx_value_profile(cleaned_data)
    profile, _ = HBXValueProfile.objects.update_or_create(
        player=player,
        defaults={
            "source": source,
            **computed,
        },
    )
    from valuation.ai_service import refresh_ai_insights_for_player

    save_athlete_360_snapshots(
        player,
        source=DataSourceLog.SourceType.HBX_VALUE,
        payload={"hbx_value_profile_id": profile.id, "source": source},
    )
    refresh_ai_insights_for_player(player)
    return profile


def build_hbx_seed_from_profile(player, profile):
    if not player or not profile:
        return None
    source_targets = profile.source_targets or {}
    source_collection = profile.source_collection or {}
    manual_collection = source_collection.get("manual", {})
    return {
        "player_id": player.id,
        "athlete_name": player.name,
        "club_name": player.club_origin,
        "position": player.position,
        "current_value": float(player.current_value),
        "instagram_handle": _safe_text(source_targets.get("instagram", {}).get("handle")),
        "google_news_query": _safe_text(source_targets.get("google_news", {}).get("query")),
        "google_news_rss": _safe_text(source_targets.get("google_news", {}).get("rss_url")),
        "google_news_articles": source_collection.get("google_news", {}).get("articles", []),
        "youtube_channel_id": _safe_text(source_targets.get("youtube", {}).get("channel_id")),
        "youtube_query": _safe_text(source_targets.get("youtube", {}).get("query")),
        "youtube_videos": source_collection.get("youtube", {}).get("videos", []),
        "tiktok_handle": _safe_text(source_targets.get("tiktok", {}).get("handle")),
        "tiktok_query": _safe_text(source_targets.get("tiktok", {}).get("query")),
        "manual_context": _safe_text(source_targets.get("manual", {}).get("context")),
        "instagram_mentions": source_collection.get("instagram", {}).get("mentions", 0),
        "instagram_momentum": source_collection.get("instagram", {}).get("momentum", 0),
        "instagram_sentiment": source_collection.get("instagram", {}).get("sentiment", 0),
        "instagram_reach": source_collection.get("instagram", {}).get("reach", 0),
        "instagram_authority": source_collection.get("instagram", {}).get("authority", 0),
        "instagram_username": _safe_text(source_collection.get("instagram", {}).get("profile", {}).get("username")),
        "instagram_name": _safe_text(source_collection.get("instagram", {}).get("profile", {}).get("name")),
        "instagram_biography": _safe_text(source_collection.get("instagram", {}).get("profile", {}).get("biography")),
        "instagram_website": _safe_text(source_collection.get("instagram", {}).get("profile", {}).get("website")),
        "instagram_profile_picture_url": _safe_text(source_collection.get("instagram", {}).get("profile", {}).get("profile_picture_url")),
        "instagram_followers_count": source_collection.get("instagram", {}).get("profile", {}).get("followers_count", 0),
        "instagram_media_count": source_collection.get("instagram", {}).get("profile", {}).get("media_count", 0),
        "google_news_mentions": source_collection.get("google_news", {}).get("mentions", 0),
        "google_news_momentum": source_collection.get("google_news", {}).get("momentum", 0),
        "google_news_sentiment": source_collection.get("google_news", {}).get("sentiment", 0),
        "google_news_reach": source_collection.get("google_news", {}).get("reach", 0),
        "google_news_authority": source_collection.get("google_news", {}).get("authority", 0),
        "youtube_mentions": source_collection.get("youtube", {}).get("mentions", 0),
        "youtube_momentum": source_collection.get("youtube", {}).get("momentum", 0),
        "youtube_sentiment": source_collection.get("youtube", {}).get("sentiment", 0),
        "youtube_reach": source_collection.get("youtube", {}).get("reach", 0),
        "youtube_authority": source_collection.get("youtube", {}).get("authority", 0),
        "tiktok_mentions": source_collection.get("tiktok", {}).get("mentions", 0),
        "tiktok_momentum": source_collection.get("tiktok", {}).get("momentum", 0),
        "tiktok_sentiment": source_collection.get("tiktok", {}).get("sentiment", 0),
        "tiktok_reach": source_collection.get("tiktok", {}).get("reach", 0),
        "tiktok_authority": source_collection.get("tiktok", {}).get("authority", 0),
        "tiktok_videos": source_collection.get("tiktok", {}).get("videos", []),
        "manual_mentions": manual_collection.get("mentions", 0),
        "manual_momentum": manual_collection.get("momentum", 0),
        "manual_sentiment": manual_collection.get("sentiment", 0),
        "manual_reach": manual_collection.get("reach", 0),
        "manual_authority": manual_collection.get("authority", 0),
        "manual_performance_rating": manual_collection.get("performance_rating", profile.performance_rating),
        "manual_attention_spike": manual_collection.get("attention_spike", profile.attention_spike),
        "manual_market_response": manual_collection.get("market_response", profile.market_response),
        "manual_visibility_efficiency": manual_collection.get("visibility_efficiency", profile.visibility_efficiency),
        "manual_note": _safe_text(manual_collection.get("qualitative_note")),
        "narrative_keywords": profile.narrative_keywords,
        "source": profile.source,
    }


def radar_chart_data(player, lang="pt"):
    scores = calculate_scores(player, lang)
    categories = [tr(lang, "performance_metrics"), tr(lang, "market_metrics"), tr(lang, "marketing_metrics"), tr(lang, "behavior_metrics"), "Potential"]
    values = [
        scores["performance_score"],
        scores["market_score"],
        scores["marketing_score"],
        scores["behavior_score"],
        scores["potential_score"],
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
                "potential_score": scores["potential_score"],
            })()
        ]
    x_values = [item.date.strftime("%d/%m/%Y") for item in history]
    training_environment_score = _derived_training_environment_score(player)
    trajectory_score = _derived_trajectory_score(player)
    potential_values = [
        _score_potential_from_components(
            _historical_age(player, item.date),
            item.market_score,
            item.behavior_score,
            training_environment_score,
            trajectory_score,
        )
        for item in history
    ]
    series = [
        (tr(lang, "performance_metrics"), [item.performance_score for item in history], "#00e0b8"),
        (tr(lang, "market_metrics"), [item.market_score for item in history], "#4cc9f0"),
        (tr(lang, "marketing_metrics"), [item.marketing_score for item in history], "#f9c74f"),
        (tr(lang, "behavior_metrics"), [item.behavior_score for item in history], "#f72585"),
        ("Potential", potential_values, "#b8de6f"),
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


def score_composition_chart_data(player, lang="pt"):
    scores = calculate_scores(player, lang)
    contributions = [
        (tr(lang, "performance_metrics"), round(scores["performance_score"] * FINAL_WEIGHTS["performance"], 2), "#00e0b8"),
        (tr(lang, "market_metrics"), round(scores["market_score"] * FINAL_WEIGHTS["market"], 2), "#4cc9f0"),
        (tr(lang, "marketing_metrics"), round(scores["marketing_score"] * FINAL_WEIGHTS["marketing"], 2), "#f9c74f"),
        (tr(lang, "behavior_metrics"), round(scores["behavior_score"] * FINAL_WEIGHTS["behavioral"], 2), "#f72585"),
        ("Potential", round(scores["potential_score"] * FINAL_WEIGHTS["potential"], 2), "#b8de6f"),
    ]
    return json.dumps(
        {
            "data": [
                {
                    "type": "bar",
                    "x": [item[0] for item in contributions],
                    "y": [item[1] for item in contributions],
                    "marker": {"color": [item[2] for item in contributions]},
                }
            ],
            "layout": {
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(0,0,0,0)",
                "font": {"color": "#e8f1f2"},
                "margin": {"l": 40, "r": 20, "t": 20, "b": 70},
                "xaxis": {"gridcolor": "rgba(255,255,255,0.1)"},
                "yaxis": {"gridcolor": "rgba(255,255,255,0.1)", "range": [0, 40], "title": "Contribuicao no score final"},
                "showlegend": False,
            },
        }
    )


def _scores_from_history_snapshot(player, snapshot, lang="pt"):
    training_environment_score = _derived_training_environment_score(player)
    trajectory_score = _derived_trajectory_score(player)
    potential_score = _score_potential_from_components(
        _historical_age(player, snapshot.date),
        snapshot.market_score,
        snapshot.behavior_score,
        training_environment_score,
        trajectory_score,
    )
    return {
        "performance_score": round(snapshot.performance_score, 2),
        "market_score": round(snapshot.market_score, 2),
        "marketing_score": round(snapshot.marketing_score, 2),
        "behavior_score": round(snapshot.behavior_score, 2),
        "behavioral_score": round(snapshot.behavior_score, 2),
        "potential_score": round(potential_score, 2),
        "valuation_score": round(snapshot.valuation_score, 2),
        "current_value": float(snapshot.current_value),
        "date": snapshot.date,
        "classification": _classification_label(snapshot.valuation_score),
        "traffic_light": _traffic_light_label(snapshot.valuation_score),
    }


def longitudinal_bi_payload(player, lang="pt", compare_window_days=90):
    current_scores = calculate_scores(player, lang)
    today = timezone.localdate()
    target_date = today - timedelta(days=compare_window_days)
    history = list(player.history.order_by("date", "id"))
    baseline_snapshot = None
    if history:
        eligible = [item for item in history if item.date <= target_date]
        baseline_snapshot = eligible[-1] if eligible else history[0]

    baseline_scores = (
        _scores_from_history_snapshot(player, baseline_snapshot, lang)
        if baseline_snapshot else {
            "performance_score": current_scores["performance_score"],
            "market_score": current_scores["market_score"],
            "marketing_score": current_scores["marketing_score"],
            "behavior_score": current_scores["behavior_score"],
            "behavioral_score": current_scores["behavioral_score"],
            "potential_score": current_scores["potential_score"],
            "valuation_score": current_scores["valuation_score"],
            "current_value": float(player.current_value),
            "date": today,
            "classification": current_scores["classification"],
            "traffic_light": current_scores["traffic_light"],
        }
    )

    deltas = {
        "performance_score": round(current_scores["performance_score"] - baseline_scores["performance_score"], 2),
        "market_score": round(current_scores["market_score"] - baseline_scores["market_score"], 2),
        "marketing_score": round(current_scores["marketing_score"] - baseline_scores["marketing_score"], 2),
        "behavior_score": round(current_scores["behavior_score"] - baseline_scores["behavior_score"], 2),
        "potential_score": round(current_scores["potential_score"] - baseline_scores["potential_score"], 2),
        "valuation_score": round(current_scores["valuation_score"] - baseline_scores["valuation_score"], 2),
        "current_value": round(float(player.current_value) - baseline_scores["current_value"], 2),
    }
    baseline_value = baseline_scores["current_value"]
    value_delta_pct = round((deltas["current_value"] / baseline_value) * 100, 2) if baseline_value else 0.0

    pillar_labels = {
        "performance_score": tr(lang, "performance_metrics"),
        "market_score": tr(lang, "market_metrics"),
        "marketing_score": tr(lang, "marketing_metrics"),
        "behavior_score": tr(lang, "behavior_metrics"),
        "potential_score": "Potential",
    }
    best_key = max(pillar_labels, key=lambda key: deltas[key])
    worst_key = min(pillar_labels, key=lambda key: deltas[key])

    pillar_signal = {}
    for key, label in pillar_labels.items():
        delta_value = deltas[key]
        if delta_value >= 5:
            traffic = "verde"
        elif delta_value <= -5:
            traffic = "vermelho"
        else:
            traffic = "amarelo"
        pillar_signal[key] = {
            "label": label,
            "delta": delta_value,
            "traffic": traffic,
        }

    if deltas["valuation_score"] >= 5:
        status_label = "Evolucao consistente"
    elif deltas["valuation_score"] <= -5:
        status_label = "Queda relevante"
    else:
        status_label = "Estabilidade competitiva"

    insights = []
    if deltas[best_key] > 0:
        insights.append(f"Maior avanco: {pillar_labels[best_key]} ({deltas[best_key]:+.1f}).")
    if deltas[worst_key] < 0:
        insights.append(f"Ponto de atencao: {pillar_labels[worst_key]} ({deltas[worst_key]:+.1f}).")
    if deltas["market_score"] > 0 and deltas["performance_score"] <= 0:
        insights.append("O mercado melhorou mais que o campo. Validar se a valorizacao esta sustentada por desempenho.")
    elif deltas["performance_score"] > 0 and deltas["market_score"] <= 0:
        insights.append("A performance subiu antes da percepcao de mercado. Existe oportunidade de posicionamento.")
    if not insights:
        insights.append("A leitura do atleta segue estavel no periodo, sem deslocamento forte entre os pilares.")

    alerts = []
    if deltas["performance_score"] > 4 and deltas["market_score"] <= 0:
        alerts.append("Performance em alta sem resposta de mercado. Ha espaco para reposicionamento e comunicacao.")
    if deltas["market_score"] > 4 and deltas["performance_score"] <= 0:
        alerts.append("Mercado reagiu antes do campo. Validar sustentabilidade competitiva da valorizacao.")
    if deltas["marketing_score"] > 5 and deltas["performance_score"] < 0:
        alerts.append("Exposicao subiu mais do que o rendimento. Evitar narrativa desconectada da performance.")
    if deltas["potential_score"] < -4:
        alerts.append("Queda na leitura de potencial. Reavaliar ambiente de desenvolvimento e trajetoria.")
    if value_delta_pct >= 10:
        alerts.append("Valorizacao relevante no periodo. Momento favoravel para consolidar narrativa premium.")
    if value_delta_pct <= -10:
        alerts.append("Desvalorizacao relevante no periodo. Prioridade para recuperar consistencia e sinais de mercado.")
    if not alerts:
        alerts.append("Sem alerta critico no periodo. O atleta segue em zona de monitoramento controlado.")

    if deltas["performance_score"] > 4 and deltas["market_score"] <= 0:
        recommended_action = "Transformar a evolucao tecnica em narrativa de mercado com clipping, highlights e validacao externa."
    elif deltas["performance_score"] < 0 and deltas["market_score"] >= 4:
        recommended_action = "Proteger o ativo: reduzir hype vazio e reconectar a comunicacao com rendimento em campo."
    elif deltas["potential_score"] < -4:
        recommended_action = "Revisar contexto do atleta: minutos, ambiente de treino, staff e plano de desenvolvimento."
    elif deltas["valuation_score"] >= 5:
        recommended_action = "Aproveitar a janela positiva para reforcar posicionamento competitivo e comercial do atleta."
    elif deltas["valuation_score"] <= -5:
        recommended_action = "Atuar no pilar mais pressionado antes da proxima janela de observacao para interromper a queda."
    else:
        recommended_action = "Manter acompanhamento e buscar ganho objetivo no pilar com maior espaco de crescimento."

    return {
        "window_days": compare_window_days,
        "current": {
            "date": today,
            "scores": current_scores,
            "current_value": float(player.current_value),
        },
        "baseline": baseline_scores,
        "delta": deltas,
        "value_delta_pct": value_delta_pct,
        "status_label": status_label,
        "best_pillar_label": pillar_labels[best_key],
        "worst_pillar_label": pillar_labels[worst_key],
        "pillar_signal": pillar_signal,
        "alerts": alerts,
        "recommended_action": recommended_action,
        "insights": insights,
    }


def longitudinal_delta_chart_data(player, lang="pt", compare_window_days=90):
    payload = longitudinal_bi_payload(player, lang, compare_window_days)
    categories = [
        tr(lang, "performance_metrics"),
        tr(lang, "market_metrics"),
        tr(lang, "marketing_metrics"),
        tr(lang, "behavior_metrics"),
        "Potential",
        tr(lang, "valuation_score"),
    ]
    values = [
        payload["delta"]["performance_score"],
        payload["delta"]["market_score"],
        payload["delta"]["marketing_score"],
        payload["delta"]["behavior_score"],
        payload["delta"]["potential_score"],
        payload["delta"]["valuation_score"],
    ]
    colors = ["#00e0b8" if value >= 0 else "#f72585" for value in values]
    return json.dumps(
        {
            "data": [
                {
                    "type": "bar",
                    "x": categories,
                    "y": values,
                    "marker": {"color": colors},
                }
            ],
            "layout": {
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(0,0,0,0)",
                "font": {"color": "#e8f1f2"},
                "margin": {"l": 40, "r": 20, "t": 20, "b": 70},
                "xaxis": {"gridcolor": "rgba(255,255,255,0.1)"},
                "yaxis": {"gridcolor": "rgba(255,255,255,0.1)", "title": "Delta no periodo"},
                "showlegend": False,
            },
        }
    )


def player_timeline_events(player, compare_window_days=90):
    cutoff_date = timezone.localdate() - timedelta(days=compare_window_days)
    timeline = []

    for snapshot in player.history.filter(date__gte=cutoff_date).order_by("-date", "-id")[:8]:
        timeline.append(
            {
                "date": snapshot.date,
                "type": "Snapshot",
                "title": f"Score {snapshot.valuation_score:.1f} | Valor EUR {float(snapshot.current_value):.2f}",
                "detail": f"Performance {snapshot.performance_score:.1f} | Mercado {snapshot.market_score:.1f} | Marketing {snapshot.marketing_score:.1f}",
            }
        )

    for report in player.live_player_evaluations.filter(match_date__gte=cutoff_date).order_by("-match_date", "-saved_at", "-id")[:8]:
        summary = _safe_text((report.payload or {}).get("avaliacao_geral", {}).get("resumo_do_desempenho"))
        timeline.append(
            {
                "date": report.match_date,
                "type": "Match Analysis",
                "title": f"{report.competition or 'Jogo observado'} vs {report.opponent or 'Adversario nao informado'}",
                "detail": summary or "Ficha de analise ao vivo registrada.",
            }
        )

    for note in player.analyst_notes.filter(date__gte=cutoff_date).order_by("-date", "-id")[:8]:
        timeline.append(
            {
                "date": note.date,
                "type": "Nota",
                "title": "Leitura do analista",
                "detail": _safe_text(note.analysis_text) or "Nota qualitativa registrada.",
            }
        )

    for plan in player.development_plans.order_by("-deadline", "-id")[:6]:
        timeline.append(
            {
                "date": plan.deadline,
                "type": "Plano",
                "title": plan.goal,
                "detail": f"Meta: {plan.target_metric} -> {plan.target_value}",
            }
        )

    timeline.sort(key=lambda item: (item["date"], item["type"]), reverse=True)
    return timeline[:12]


def comparison_chart_data(players, lang="pt"):
    categories = [tr(lang, "performance_metrics"), tr(lang, "market_metrics"), tr(lang, "marketing_metrics"), tr(lang, "behavior_metrics"), "Potential", tr(lang, "valuation_score")]
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
                    scores["potential_score"],
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
    normalized_position = normalize_position_value(cleaned_data["position"])
    secondary_position = normalize_position_value(cleaned_data.get("secondary_positions"))
    division_reference, club_reference = resolve_division_and_club(
        cleaned_data["league_level"],
        cleaned_data["club_origin"],
        cleaned_data.get("country_code") or "BRA",
    )
    if player is None:
        player = Player.objects.create(
            user=user,
            name=cleaned_data["name"],
            public_name=cleaned_data.get("public_name", ""),
            age=cleaned_data["age"],
            birth_date=cleaned_data.get("birth_date"),
            nationality=cleaned_data.get("nationality", ""),
            position=normalized_position,
            secondary_positions=[secondary_position] if secondary_position else [],
            dominant_foot=cleaned_data.get("dominant_foot", ""),
            height_cm=cleaned_data.get("height_cm"),
            weight_kg=cleaned_data.get("weight_kg"),
            current_value=cleaned_data["current_value"],
            league_level=cleaned_data["league_level"],
            club_origin=cleaned_data["club_origin"],
            category=cleaned_data.get("category", ""),
            contract_months_remaining=cleaned_data.get("contract_months_remaining"),
            squad_status=cleaned_data.get("squad_status", ""),
            athlete_objectives=[cleaned_data["athlete_objectives"]] if cleaned_data.get("athlete_objectives") else [],
            training_environment_score=float(cleaned_data.get("training_environment_score") or 0),
            trajectory_score=float(cleaned_data.get("trajectory_score") or 0),
            profile_notes=cleaned_data.get("profile_notes", ""),
            division_reference=division_reference,
            club_reference=club_reference,
        )
        PerformanceMetrics.objects.create(player=player)
        MarketMetrics.objects.create(player=player)
        MarketingMetrics.objects.create(player=player)
        BehaviorMetrics.objects.create(player=player)
    else:
        player.name = cleaned_data["name"]
        player.public_name = cleaned_data.get("public_name", "")
        player.age = cleaned_data["age"]
        player.birth_date = cleaned_data.get("birth_date")
        player.nationality = cleaned_data.get("nationality", "")
        player.position = normalized_position
        player.secondary_positions = [secondary_position] if secondary_position else []
        player.dominant_foot = cleaned_data.get("dominant_foot", "")
        player.height_cm = cleaned_data.get("height_cm")
        player.weight_kg = cleaned_data.get("weight_kg")
        player.current_value = cleaned_data["current_value"]
        player.league_level = cleaned_data["league_level"]
        player.club_origin = cleaned_data["club_origin"]
        player.category = cleaned_data.get("category", "")
        player.contract_months_remaining = cleaned_data.get("contract_months_remaining")
        player.squad_status = cleaned_data.get("squad_status", "")
        player.athlete_objectives = [cleaned_data["athlete_objectives"]] if cleaned_data.get("athlete_objectives") else []
        player.training_environment_score = float(cleaned_data.get("training_environment_score") or 0)
        player.trajectory_score = float(cleaned_data.get("trajectory_score") or 0)
        player.profile_notes = cleaned_data.get("profile_notes", "")
        player.division_reference = division_reference
        player.club_reference = club_reference
        player.save()

    PerformanceMetrics.objects.filter(player=player).update(
        xg=_zero_if_none(cleaned_data["xg"]),
        xa=_zero_if_none(cleaned_data["xa"]),
        passes_pct=_zero_if_none(cleaned_data["passes_pct"]),
        dribbles_pct=_zero_if_none(cleaned_data["dribbles_pct"]),
        tackles_pct=_zero_if_none(cleaned_data["tackles_pct"]),
        high_intensity_distance=_zero_if_none(cleaned_data["high_intensity_distance"]),
        final_third_recoveries=_zero_if_none(cleaned_data["final_third_recoveries"]),
    )
    MarketMetrics.objects.filter(player=player).update(
        annual_growth=_zero_if_none(cleaned_data["annual_growth"]),
        club_interest=_zero_if_none(cleaned_data["club_interest"]),
        league_score=_zero_if_none(cleaned_data["league_score"]),
        age_factor=_zero_if_none(cleaned_data["age_factor"]),
        club_reputation=_zero_if_none(cleaned_data["club_reputation"]),
    )
    network_followers = sum(
        float(cleaned_data.get(field) or 0)
        for field in ("instagram_followers", "tiktok_followers", "x_followers", "youtube_subscribers")
    )
    engagement_candidates = [
        float(cleaned_data.get(field) or 0)
        for field in ("instagram_engagement", "tiktok_engagement", "x_engagement")
        if float(cleaned_data.get(field) or 0) > 0
    ]
    consolidated_followers = _coalesce_metric(cleaned_data.get("followers"), network_followers)
    consolidated_engagement = _coalesce_metric(
        cleaned_data.get("engagement"),
        round(sum(engagement_candidates) / len(engagement_candidates), 2) if engagement_candidates else 0,
    )
    MarketingMetrics.objects.filter(player=player).update(
        instagram_handle=cleaned_data.get("instagram_handle", ""),
        instagram_followers=float(cleaned_data.get("instagram_followers") or 0),
        instagram_engagement=float(cleaned_data.get("instagram_engagement") or 0),
        instagram_posts=float(cleaned_data.get("instagram_posts") or 0),
        tiktok_handle=cleaned_data.get("tiktok_handle", ""),
        tiktok_followers=float(cleaned_data.get("tiktok_followers") or 0),
        tiktok_engagement=float(cleaned_data.get("tiktok_engagement") or 0),
        tiktok_posts=float(cleaned_data.get("tiktok_posts") or 0),
        x_handle=cleaned_data.get("x_handle", ""),
        x_followers=float(cleaned_data.get("x_followers") or 0),
        x_engagement=float(cleaned_data.get("x_engagement") or 0),
        google_news_query=cleaned_data.get("google_news_query", ""),
        youtube_query=cleaned_data.get("youtube_query", ""),
        youtube_subscribers=float(cleaned_data.get("youtube_subscribers") or 0),
        youtube_avg_views=float(cleaned_data.get("youtube_avg_views") or 0),
        youtube_videos=float(cleaned_data.get("youtube_videos") or 0),
        collection_notes=cleaned_data.get("collection_notes", ""),
        followers=consolidated_followers,
        engagement=consolidated_engagement,
        media_mentions=_zero_if_none(cleaned_data["media_mentions"]),
        sponsorships=_zero_if_none(cleaned_data["sponsorships"]),
        sentiment_score=_zero_if_none(cleaned_data["sentiment_score"]),
    )
    BehaviorMetrics.objects.filter(player=player).update(
        conscientiousness=_zero_if_none(cleaned_data["conscientiousness"]),
        adaptability=_zero_if_none(cleaned_data["adaptability"]),
        resilience=_zero_if_none(cleaned_data["resilience"]),
        deliberate_practice=_zero_if_none(cleaned_data["deliberate_practice"]),
        executive_function=_zero_if_none(cleaned_data["executive_function"]),
        leadership=_zero_if_none(cleaned_data["leadership"]),
    )
    for relation_name in ("performance_metrics", "market_metrics", "marketing_metrics", "behavior_metrics"):
        player._state.fields_cache.pop(relation_name, None)
    sync_integrated_player_modules(player)
    save_player_history_snapshot(player)
    from valuation.ai_service import refresh_ai_insights_for_player

    refresh_ai_insights_for_player(player)
    return player


def save_player_history_snapshot(player, snapshot_date=None, source=DataSourceLog.SourceType.SYSTEM, related_report=None, payload=None):
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
        save_athlete_360_snapshots(player, snapshot_date, source=source, related_report=related_report, payload=payload)
        return history_entry
    history_entry = PlayerHistory.objects.create(
        player=player,
        date=snapshot_date,
        performance_score=scores["performance_score"],
        market_score=scores["market_score"],
        marketing_score=scores["marketing_score"],
        behavior_score=scores["behavior_score"],
        valuation_score=scores["valuation_score"],
        current_value=player.current_value,
    )
    save_athlete_360_snapshots(player, snapshot_date, source=source, related_report=related_report, payload=payload)
    return history_entry


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
        save_athlete_360_snapshots(
            player,
            cleaned_data["date"],
            source=DataSourceLog.SourceType.MANUAL,
            payload={"manual_history_snapshot": values},
        )
        from valuation.ai_service import refresh_ai_insights_for_player

        refresh_ai_insights_for_player(player)
        return history_entry
    history_entry = PlayerHistory.objects.create(player=player, date=cleaned_data["date"], **values)
    save_athlete_360_snapshots(
        player,
        cleaned_data["date"],
        source=DataSourceLog.SourceType.MANUAL,
        payload={"manual_history_snapshot": values},
    )
    from valuation.ai_service import refresh_ai_insights_for_player

    refresh_ai_insights_for_player(player)
    return history_entry


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


def save_athlete_career_entry(player, cleaned_data):
    if cleaned_data.get("is_current"):
        AthleteCareerEntry.objects.filter(player=player, is_current=True).update(is_current=False)
    entry = AthleteCareerEntry.objects.create(
        player=player,
        club_name=cleaned_data["club_name"],
        country_name=cleaned_data.get("country_name", ""),
        division_name=cleaned_data.get("division_name", ""),
        season_label=cleaned_data.get("season_label", ""),
        start_date=cleaned_data.get("start_date"),
        end_date=cleaned_data.get("end_date"),
        move_type=cleaned_data.get("move_type") or AthleteCareerEntry.MoveType.PERMANENT,
        is_current=bool(cleaned_data.get("is_current")),
        notes=cleaned_data.get("notes", ""),
    )
    if entry.is_current:
        player.club_origin = entry.club_name
        if entry.division_name:
            player.league_level = entry.division_name
        player.save(update_fields=["club_origin", "league_level"])
    save_athlete_360_snapshots(
        player,
        source=DataSourceLog.SourceType.MANUAL,
        payload={"career_entry_id": entry.id, "club_name": entry.club_name, "move_type": entry.move_type},
    )
    return entry


def save_athlete_contract(player, cleaned_data):
    if cleaned_data.get("is_current"):
        AthleteContract.objects.filter(player=player, is_current=True).update(is_current=False)
    contract = AthleteContract.objects.create(
        player=player,
        club_name=cleaned_data["club_name"],
        start_date=cleaned_data.get("start_date"),
        end_date=cleaned_data.get("end_date"),
        monthly_salary=cleaned_data.get("monthly_salary") or Decimal("0.00"),
        release_clause=cleaned_data.get("release_clause") or Decimal("0.00"),
        status=cleaned_data.get("status") or AthleteContract.Status.ACTIVE,
        is_current=bool(cleaned_data.get("is_current")),
        notes=cleaned_data.get("notes", ""),
    )
    if contract.is_current:
        player.contract_months_remaining = cleaned_data.get("contract_months_remaining")
        player.save(update_fields=["contract_months_remaining"])
    save_athlete_360_snapshots(
        player,
        source=DataSourceLog.SourceType.MANUAL,
        payload={"contract_id": contract.id, "club_name": contract.club_name, "status": contract.status},
    )
    return contract


def save_athlete_transfer(player, cleaned_data):
    transfer = AthleteTransfer.objects.create(
        player=player,
        from_club=cleaned_data.get("from_club", ""),
        to_club=cleaned_data["to_club"],
        transfer_date=cleaned_data["transfer_date"],
        transfer_type=cleaned_data.get("transfer_type") or AthleteTransfer.TransferType.PERMANENT,
        transfer_fee=cleaned_data.get("transfer_fee") or Decimal("0.00"),
        currency=cleaned_data.get("currency") or "EUR",
        notes=cleaned_data.get("notes", ""),
    )
    save_athlete_360_snapshots(
        player,
        snapshot_date=transfer.transfer_date,
        source=DataSourceLog.SourceType.MANUAL,
        payload={"transfer_id": transfer.id, "from_club": transfer.from_club, "to_club": transfer.to_club},
    )
    return transfer


def save_go_carriera_checkin(player, cleaned_data):
    checkin, _ = GoCarrieraCheckIn.objects.update_or_create(
        player=player,
        checkin_date=cleaned_data["checkin_date"],
        defaults={
            "sleep_quality": cleaned_data["sleep_quality"],
            "hydration": cleaned_data["hydration"],
            "nutrition": cleaned_data["nutrition"],
            "energy": cleaned_data["energy"],
            "focus": cleaned_data["focus"],
            "mood": cleaned_data["mood"],
            "motivation": cleaned_data["motivation"],
            "post_error_response": cleaned_data["post_error_response"],
            "soreness": cleaned_data["soreness"],
            "recovery": cleaned_data["recovery"],
            "treatment_adherence": cleaned_data.get("treatment_adherence") or 0,
            "injury_status": cleaned_data["injury_status"],
            "notes": cleaned_data.get("notes", ""),
        },
    )
    readiness_components = [
        checkin.sleep_quality,
        checkin.hydration,
        checkin.nutrition,
        checkin.energy,
        checkin.focus,
        checkin.recovery,
    ]
    habit_components = [
        checkin.sleep_quality,
        checkin.hydration,
        checkin.nutrition,
        checkin.treatment_adherence,
    ]
    emotional_components = [
        checkin.mood,
        checkin.motivation,
        checkin.post_error_response,
        checkin.focus,
    ]
    professionalism_components = [
        checkin.treatment_adherence,
        checkin.recovery,
        checkin.focus,
        checkin.motivation,
    ]
    soreness_penalty = 100 - (checkin.soreness * 10)
    injury_recovery_score = 50
    if checkin.injury_status == GoCarrieraCheckIn.InjuryStatus.NONE:
        injury_recovery_score = 80
    elif checkin.injury_status == GoCarrieraCheckIn.InjuryStatus.MANAGED:
        injury_recovery_score = 65
    elif checkin.injury_status == GoCarrieraCheckIn.InjuryStatus.RECOVERY:
        injury_recovery_score = clamp((checkin.recovery * 7) + (checkin.treatment_adherence * 3))
    behavior_score = round(
        (
            (sum(readiness_components) / len(readiness_components) * 10) * 0.30
            + (sum(habit_components) / len(habit_components) * 10) * 0.20
            + (sum(emotional_components) / len(emotional_components) * 10) * 0.20
            + (sum(professionalism_components) / len(professionalism_components) * 10) * 0.15
            + soreness_penalty * 0.05
            + injury_recovery_score * 0.10
        ),
        2,
    )
    save_athlete_360_snapshots(
        player,
        snapshot_date=checkin.checkin_date,
        source=DataSourceLog.SourceType.GO_CARRIERA,
        payload={"go_carriera_checkin_id": checkin.id},
    )
    BehaviorSnapshot.objects.update_or_create(
        player=player,
        snapshot_date=checkin.checkin_date,
        source=DataSourceLog.SourceType.GO_CARRIERA,
        defaults={
            "behavior_score": behavior_score,
            "readiness_score": round(sum(readiness_components) / len(readiness_components) * 10, 2),
            "habit_score": round(sum(habit_components) / len(habit_components) * 10, 2),
            "emotional_stability_score": round(sum(emotional_components) / len(emotional_components) * 10, 2),
            "professionalism_score": round(sum(professionalism_components) / len(professionalism_components) * 10, 2),
            "adherence_score": round(((checkin.treatment_adherence + checkin.focus) / 2) * 10, 2),
            "consistency_score": round(((checkin.energy + checkin.motivation + checkin.focus) / 3) * 10, 2),
            "injury_recovery_behavior_score": round(injury_recovery_score, 2),
            "engagement_score": round(((checkin.motivation + checkin.post_error_response + checkin.focus) / 3) * 10, 2),
            "data_confidence_score": _source_confidence(DataSourceLog.SourceType.GO_CARRIERA),
            "metrics_payload": {
                "sleep_quality": checkin.sleep_quality,
                "hydration": checkin.hydration,
                "nutrition": checkin.nutrition,
                "energy": checkin.energy,
                "focus": checkin.focus,
                "mood": checkin.mood,
                "motivation": checkin.motivation,
                "post_error_response": checkin.post_error_response,
                "soreness": checkin.soreness,
                "recovery": checkin.recovery,
                "treatment_adherence": checkin.treatment_adherence,
                "injury_status": checkin.injury_status,
                "notes": checkin.notes,
            },
        },
    )
    DataSourceLog.objects.create(
        player=player,
        source_type=DataSourceLog.SourceType.GO_CARRIERA,
        source_name="Go Carriera Daily Check-In",
        reference_id=str(checkin.id),
        confidence_score=_source_confidence(DataSourceLog.SourceType.GO_CARRIERA),
        payload={"checkin_date": checkin.checkin_date.isoformat(), "injury_status": checkin.injury_status},
    )
    return checkin


def build_behavioral_intelligence(player):
    snapshots = list(player.behavior_snapshots.order_by("-snapshot_date", "-id")[:6])
    latest = snapshots[0] if snapshots else None
    previous = snapshots[1] if len(snapshots) > 1 else None
    if not latest:
        return {
            "status": "Sem historico suficiente",
            "trend_label": "coleta inicial",
            "delta": 0,
            "readiness_band": "-",
            "stability_band": "-",
            "alert": "Registre mais snapshots comportamentais para iniciar a leitura.",
            "drivers": [],
        }
    previous_score = previous.behavior_score if previous else latest.behavior_score
    delta = round(latest.behavior_score - previous_score, 2)
    if latest.behavior_score >= 75:
        status = "behavior forte"
    elif latest.behavior_score >= 60:
        status = "behavior consistente"
    elif latest.behavior_score >= 45:
        status = "behavior em observacao"
    else:
        status = "behavior fragil"
    if delta >= 5:
        trend_label = "subida clara"
    elif delta <= -5:
        trend_label = "queda relevante"
    else:
        trend_label = "estabilidade"
    readiness_band = "alta" if latest.readiness_score >= 75 else "media" if latest.readiness_score >= 55 else "baixa"
    stability_band = "alta" if latest.emotional_stability_score >= 75 else "media" if latest.emotional_stability_score >= 55 else "baixa"
    drivers = [
        {"label": "Readiness", "value": round(latest.readiness_score, 1)},
        {"label": "Habits", "value": round(latest.habit_score, 1)},
        {"label": "Emotional stability", "value": round(latest.emotional_stability_score, 1)},
        {"label": "Professionalism", "value": round(latest.professionalism_score, 1)},
        {"label": "Adherence", "value": round(latest.adherence_score, 1)},
        {"label": "Engagement", "value": round(latest.engagement_score, 1)},
    ]
    weak_driver = min(drivers, key=lambda item: item["value"])
    alert = f"Ponto de atencao atual: {weak_driver['label']} em {weak_driver['value']:.1f}."
    return {
        "status": status,
        "trend_label": trend_label,
        "delta": delta,
        "readiness_band": readiness_band,
        "stability_band": stability_band,
        "alert": alert,
        "drivers": drivers,
    }


def _comparison_position_key(player):
    return normalize_position_value(getattr(player, "position", "") or "")


def _context_fit_score(player, other):
    score = 0.0
    tags = []
    if _comparison_position_key(player) and _comparison_position_key(player) == _comparison_position_key(other):
        score += 40
        tags.append("mesma posicao")
    age_gap = abs((player.age or 0) - (other.age or 0))
    age_score = max(0.0, 20.0 - (age_gap * 5.0))
    if age_score:
        score += age_score
    if age_gap <= 2:
        tags.append("faixa etaria parecida")
    same_category = bool(player.category and other.category and player.category == other.category)
    if same_category:
        score += 15
        tags.append("mesma categoria")
    same_league = bool(
        (player.division_reference_id and other.division_reference_id and player.division_reference_id == other.division_reference_id)
        or (player.league_level and other.league_level and player.league_level == other.league_level)
    )
    if same_league:
        score += 15
        tags.append("mesma liga")
    player_country_id = getattr(getattr(player, "division_reference", None), "country_id", None)
    other_country_id = getattr(getattr(other, "division_reference", None), "country_id", None)
    if player_country_id and other_country_id and player_country_id == other_country_id:
        score += 10
        tags.append("mesmo pais")
    return round(clamp(score), 2), tags


def build_comparative_intelligence(player, lang="pt", compare_window_days=90, shortlist_limit=5):
    self_axis = longitudinal_bi_payload(player, lang, compare_window_days)
    player_scores = calculate_scores(player, lang)
    peers = list(
        Player.objects.filter(user=player.user)
        .exclude(pk=player.pk)
        .select_related("division_reference__country", "club_reference")
        .order_by("name")
    )
    peer_rows = []
    for other in peers:
        other_scores = calculate_scores(other, lang)
        context_fit, context_tags = _context_fit_score(player, other)
        score_gap = round(other_scores["valuation_score"] - player_scores["valuation_score"], 2)
        market_gap = round(other_scores["market_score"] - player_scores["market_score"], 2)
        performance_gap = round(other_scores["performance_score"] - player_scores["performance_score"], 2)
        value_gap = round(float(other.current_value) - float(player.current_value), 2)
        peer_rows.append(
            {
                "player": other,
                "name": other.name,
                "club": other.club_reference.short_name if getattr(other, "club_reference", None) else other.club_origin,
                "league": (
                    other.division_reference.short_name
                    if getattr(other, "division_reference", None)
                    else other.league_level
                ),
                "age": other.age,
                "age_gap": abs((other.age or 0) - (player.age or 0)),
                "context_fit": context_fit,
                "context_tags": context_tags,
                "valuation_score": round(other_scores["valuation_score"], 2),
                "market_score": round(other_scores["market_score"], 2),
                "performance_score": round(other_scores["performance_score"], 2),
                "potential_score": round(other_scores["potential_score"], 2),
                "score_gap": score_gap,
                "market_gap": market_gap,
                "performance_gap": performance_gap,
                "value_gap": value_gap,
            }
        )

    contextual_group = sorted(
        peer_rows,
        key=lambda item: (-item["context_fit"], abs(item["score_gap"]), item["age_gap"], item["name"].lower()),
    )[:5]
    shortlist = sorted(
        peer_rows,
        key=lambda item: (abs(item["score_gap"]), abs(item["value_gap"]), -item["market_score"], item["name"].lower()),
    )[:shortlist_limit]

    if contextual_group:
        group_average = round(sum(item["valuation_score"] for item in contextual_group) / len(contextual_group), 2)
        group_best = max(contextual_group, key=lambda item: item["valuation_score"])
        contextual_summary = {
            "size": len(contextual_group),
            "group_average": group_average,
            "delta_vs_group": round(player_scores["valuation_score"] - group_average, 2),
            "best_name": group_best["name"],
            "best_score": group_best["valuation_score"],
        }
    else:
        contextual_summary = {
            "size": 0,
            "group_average": 0,
            "delta_vs_group": 0,
            "best_name": "",
            "best_score": 0,
        }

    if shortlist:
        best_market_fit = min(shortlist, key=lambda item: (abs(item["score_gap"]), abs(item["value_gap"])))
        shortlist_summary = {
            "size": len(shortlist),
            "closest_name": best_market_fit["name"],
            "closest_score_gap": best_market_fit["score_gap"],
            "closest_value_gap": best_market_fit["value_gap"],
        }
    else:
        shortlist_summary = {
            "size": 0,
            "closest_name": "",
            "closest_score_gap": 0,
            "closest_value_gap": 0,
        }

    if not peer_rows:
        executive_note = "Cadastre mais atletas para abrir a camada comparativa por contexto e shortlist."
    elif contextual_summary["delta_vs_group"] >= 5:
        executive_note = "O atleta esta acima do grupo contextual e pode ser tratado como ativo premium dentro da base."
    elif contextual_summary["delta_vs_group"] <= -5:
        executive_note = "O atleta esta abaixo do grupo contextual. A prioridade e recuperar o pilar mais pressionado antes da proxima janela."
    else:
        executive_note = "O atleta esta proximo do grupo contextual. Pequenos ganhos em performance ou mercado mudam o patamar comparativo."

    return {
        "self_axis": self_axis,
        "contextual_group": contextual_group,
        "contextual_summary": contextual_summary,
        "shortlist": shortlist,
        "shortlist_summary": shortlist_summary,
        "executive_note": executive_note,
    }


def build_projection_intelligence(player, lang="pt", period="12"):
    scenarios = build_projection_scenarios(player, lang, period)
    growth = build_growth_insights(player, lang, period)
    scores = calculate_scores(player, lang)
    latest_projection = player.projection_snapshots.first()
    peers = list(
        Player.objects.filter(user=player.user)
        .exclude(pk=player.pk)
        .select_related("division_reference__country", "division_reference", "club_reference")
    )

    league_buckets = {}
    for peer in peers:
        if _comparison_position_key(peer) != _comparison_position_key(player):
            continue
        league_name = (
            peer.division_reference.short_name
            if getattr(peer, "division_reference", None)
            else peer.league_level
        ) or "Liga nao definida"
        country_name = (
            peer.division_reference.country.name
            if getattr(peer, "division_reference", None) and getattr(peer.division_reference, "country", None)
            else ""
        )
        key = (country_name, league_name)
        bucket = league_buckets.setdefault(
            key,
            {
                "country": country_name,
                "league": league_name,
                "players": 0,
                "performance_total": 0.0,
                "market_total": 0.0,
                "potential_total": 0.0,
                "valuation_total": 0.0,
            },
        )
        peer_scores = calculate_scores(peer, lang)
        bucket["players"] += 1
        bucket["performance_total"] += peer_scores["performance_score"]
        bucket["market_total"] += peer_scores["market_score"]
        bucket["potential_total"] += peer_scores["potential_score"]
        bucket["valuation_total"] += peer_scores["valuation_score"]

    fit_markets = []
    for (_, _), bucket in league_buckets.items():
        players_count = max(bucket["players"], 1)
        avg_performance = bucket["performance_total"] / players_count
        avg_market = bucket["market_total"] / players_count
        avg_potential = bucket["potential_total"] / players_count
        avg_valuation = bucket["valuation_total"] / players_count
        fit_score = clamp(
            (avg_performance * 0.30)
            + (avg_market * 0.25)
            + (avg_potential * 0.20)
            + (scores["behavior_score"] * 0.15)
            + (scores["potential_score"] * 0.10)
        )
        fit_markets.append(
            {
                "country": bucket["country"],
                "league": bucket["league"],
                "players": bucket["players"],
                "fit_score": round(fit_score, 2),
                "avg_valuation": round(avg_valuation, 2),
                "avg_market": round(avg_market, 2),
            }
        )
    fit_markets.sort(key=lambda item: (-item["fit_score"], -item["players"], item["league"]))
    fit_markets = fit_markets[:5]

    current_value = float(player.current_value)
    expected_value = float(scenarios["scenarios"]["expected"])
    conservative_value = float(scenarios["scenarios"]["conservative"])
    aggressive_value = float(scenarios["scenarios"]["aggressive"])
    expected_growth_pct = growth["projected_growth_pct"]
    value_band = {
        "floor": conservative_value,
        "expected": expected_value,
        "ceiling": aggressive_value,
    }

    if expected_growth_pct >= 20:
        timing_label = "janela de aceleracao"
    elif expected_growth_pct >= 8:
        timing_label = "janela positiva"
    elif expected_growth_pct <= 0:
        timing_label = "janela de protecao"
    else:
        timing_label = "janela de maturacao"

    adaptation_score = (
        latest_projection.adaptation_probability_score
        if latest_projection
        else clamp((scores["behavior_score"] + scores["market_score"]) / 2)
    )
    stagnation_risk = (
        latest_projection.stagnation_risk_score
        if latest_projection
        else clamp(100 - scores["potential_score"])
    )
    growth_velocity = (
        latest_projection.growth_velocity_score
        if latest_projection
        else clamp(growth["growth_rate"])
    )

    if adaptation_score >= 75 and stagnation_risk <= 35:
        readiness_label = "pronto para subir de patamar"
    elif adaptation_score >= 60 and stagnation_risk <= 50:
        readiness_label = "transicao viavel"
    elif stagnation_risk >= 65:
        readiness_label = "risco de estagnacao"
    else:
        readiness_label = "desenvolvimento assistido"

    if fit_markets:
        top_market = fit_markets[0]
        market_note = f"Melhor aderencia atual: {top_market['country']} | {top_market['league']} ({top_market['fit_score']:.1f}/100)."
    else:
        market_note = "Ainda nao ha base contextual suficiente para sugerir ligas alvo com seguranca."

    if expected_growth_pct >= 15 and adaptation_score >= 65:
        recommended_action = "Preparar narrativa de salto competitivo e mapear clubes alvo na proxima janela."
    elif stagnation_risk >= 65:
        recommended_action = "Segurar a exposicao comercial e atacar os pilares que travam a valorizacao antes de reposicionar o atleta."
    elif expected_growth_pct > 0:
        recommended_action = "Construir evolucao sustentada em campo e validar o atleta em contexto competitivo acima nas proximas observacoes."
    else:
        recommended_action = "Priorizar recuperacao de performance e comportamento antes de qualquer movimento de mercado."

    return {
        "period": scenarios["period"],
        "growth_rate": growth["growth_rate"],
        "projected_growth_pct": expected_growth_pct,
        "main_driver": growth["main_driver"],
        "value_band": value_band,
        "timing_label": timing_label,
        "readiness_label": readiness_label,
        "adaptation_score": round(adaptation_score, 2),
        "stagnation_risk_score": round(stagnation_risk, 2),
        "growth_velocity_score": round(growth_velocity, 2),
        "fit_markets": fit_markets,
        "market_note": market_note,
        "recommended_action": recommended_action,
        "opportunity_window": latest_projection.opportunity_window if latest_projection else "",
        "current_value": current_value,
    }


def build_opportunity_intelligence(player, lang="pt", period="12"):
    projection = build_projection_intelligence(player, lang, period)
    comparison = build_comparative_intelligence(player, lang, compare_window_days=90, shortlist_limit=5)
    scores = calculate_scores(player, lang)
    current_contract = player.contracts.filter(is_current=True).order_by("-id").first()
    latest_transfer = player.transfers.order_by("-transfer_date", "-id").first()
    peers = list(
        Player.objects.filter(user=player.user)
        .exclude(pk=player.pk)
        .select_related("division_reference__country", "division_reference", "club_reference")
    )

    targets = []
    for peer in peers:
        if _comparison_position_key(peer) != _comparison_position_key(player):
            continue
        peer_scores = calculate_scores(peer, lang)
        club_name = peer.club_reference.short_name if getattr(peer, "club_reference", None) else peer.club_origin
        league_name = peer.division_reference.short_name if getattr(peer, "division_reference", None) else peer.league_level
        country_name = (
            peer.division_reference.country.name
            if getattr(peer, "division_reference", None) and getattr(peer.division_reference, "country", None)
            else ""
        )
        fit_score, fit_tags = _context_fit_score(player, peer)
        opportunity_score = clamp(
            (fit_score * 0.35)
            + (peer_scores["market_score"] * 0.20)
            + (projection["adaptation_score"] * 0.20)
            + (projection["projected_growth_pct"] * 0.10)
            + (scores["performance_score"] * 0.15)
        )
        targets.append(
            {
                "club": club_name,
                "league": league_name,
                "country": country_name,
                "fit_score": round(fit_score, 2),
                "opportunity_score": round(opportunity_score, 2),
                "benchmark_name": peer.name,
                "benchmark_score": round(peer_scores["valuation_score"], 2),
                "tags": fit_tags,
            }
        )

    deduped_targets = []
    seen = set()
    for item in sorted(targets, key=lambda x: (-x["opportunity_score"], -x["fit_score"], x["club"])):
        key = (item["club"], item["league"], item["country"])
        if key in seen:
            continue
        seen.add(key)
        deduped_targets.append(item)
    target_clubs = deduped_targets[:5]

    contract_months = player.contract_months_remaining
    if contract_months is None and current_contract and current_contract.end_date:
        today = timezone.localdate()
        contract_months = max(0, (current_contract.end_date.year - today.year) * 12 + (current_contract.end_date.month - today.month))
    contract_months = contract_months or 0

    if contract_months <= 6:
        window_status = "janela imediata"
    elif contract_months <= 12:
        window_status = "janela preparatoria"
    else:
        window_status = "janela de construcao"

    risk_flags = []
    if projection["stagnation_risk_score"] >= 65:
        risk_flags.append("Risco de estagnacao acima do ideal.")
    if projection["adaptation_score"] < 55:
        risk_flags.append("Probabilidade de adaptacao ainda baixa para um salto agressivo.")
    if scores["market_score"] < 55:
        risk_flags.append("Mercado ainda nao respondeu no mesmo ritmo da projeção.")
    if contract_months > 18:
        risk_flags.append("Contrato longo reduz alavancagem de janela no curto prazo.")
    if not risk_flags:
        risk_flags.append("Sem bloqueio critico para abertura comercial monitorada.")

    if target_clubs:
        top_target = target_clubs[0]
        thesis = (
            f"O atleta pode ser apresentado como ativo de {projection['readiness_label']}, "
            f"com encaixe inicial em {top_target['country']} | {top_target['league']} e narrativa de crescimento sustentado."
        )
    else:
        thesis = (
            "A tese comercial principal ainda deve ficar concentrada na evolucao do atleta e na consolidacao do score antes de abrir novos alvos."
        )

    if projection["projected_growth_pct"] >= 15 and contract_months <= 12:
        recommended_move = "abrir shortlist comercial na proxima janela"
    elif projection["projected_growth_pct"] > 0:
        recommended_move = "observar mais uma janela e amadurecer a tese"
    else:
        recommended_move = "segurar movimento e priorizar recuperacao do ativo"

    return {
        "window_status": window_status,
        "contract_months": contract_months,
        "thesis": thesis,
        "recommended_move": recommended_move,
        "risk_flags": risk_flags,
        "target_clubs": target_clubs,
        "target_leagues": projection["fit_markets"][:3],
        "projection": projection,
        "comparison": comparison,
        "latest_transfer": latest_transfer,
    }


def build_report_audience_packages(player, lang="pt", compare_window_days=90):
    longitudinal = longitudinal_bi_payload(player, lang, compare_window_days)
    projection = build_projection_intelligence(player, lang, "12")
    opportunity = build_opportunity_intelligence(player, lang, "12")
    comparison = build_comparative_intelligence(player, lang, compare_window_days, shortlist_limit=3)
    scores = calculate_scores(player, lang)

    packages = {
        "athlete": {
            "label": "Atleta",
            "headline": "Relatorio de desenvolvimento e proximo passo de carreira.",
            "focus": [
                f"Maior avanco recente: {longitudinal['best_pillar_label']}.",
                f"Ponto de atencao: {longitudinal['worst_pillar_label']}.",
                f"Acao prioritaria: {longitudinal['recommended_action']}",
            ],
            "cta": "Usar como plano de desenvolvimento e acompanhamento mensal.",
        },
        "agent": {
            "label": "Agente",
            "headline": "Relatorio de valorizacao, narrativa e timing comercial.",
            "focus": [
                opportunity["thesis"],
                f"Movimento sugerido: {opportunity['recommended_move']}.",
                f"Melhor janela: {opportunity['window_status']}.",
            ],
            "cta": "Usar como base para posicionamento, abordagem e tese de mercado.",
        },
        "club": {
            "label": "Clube",
            "headline": "Relatorio de fit competitivo, risco e oportunidade de contratacao.",
            "focus": [
                f"Readiness: {projection['readiness_label']}.",
                f"Probabilidade de adaptacao: {projection['adaptation_score']:.1f}/100.",
                f"Risco principal: {opportunity['risk_flags'][0]}",
            ],
            "cta": "Usar como material de triagem e validacao tecnica/comercial.",
        },
        "consultancy": {
            "label": "Consultoria",
            "headline": "Relatorio analitico completo para decisao interna.",
            "focus": [
                f"Delta vs grupo contextual: {comparison['contextual_summary']['delta_vs_group']:+.1f}.",
                f"Crescimento esperado: {projection['projected_growth_pct']:.1f}%.",
                f"HBX Score atual: {scores['final_score']:.1f}.",
            ],
            "cta": "Usar como material mestre da consultoria para coordenar os proximos modulos.",
        },
    }

    return {
        "packages": packages,
        "longitudinal": longitudinal,
        "projection": projection,
        "opportunity": opportunity,
        "comparison": comparison,
    }


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
        played_position=normalize_position_value(player.position),
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


def generate_pdf_report(player, lang="pt", audience="consultancy"):
    audience = audience if audience in {"athlete", "agent", "club", "consultancy"} else "consultancy"
    scores = calculate_scores(player, lang)
    bi_payload = longitudinal_bi_payload(player, lang, 90)
    audience_packages = build_report_audience_packages(player, lang, 90)
    package = audience_packages["packages"][audience]
    opportunity = audience_packages["opportunity"]
    projection = audience_packages["projection"]
    country_name = player.division_reference.country.name if player.division_reference_id else "-"
    division_name = player.division_reference.name if player.division_reference_id else player.league_level
    club_name = player.club_reference.official_name if player.club_reference_id else player.club_origin
    audience_titles = {
        "athlete": "Athlete Development Report",
        "agent": "Executive Career Report",
        "club": "Club Presentation Report",
        "consultancy": "Consultancy Master Report",
    }
    audience_title = audience_titles[audience]
    subtitle = f"Generated for {player.name} | {package['label']} | 90-day BI summary"
    sections = [
        (
            "Executive Summary",
            [
                f"Player: {player.name}",
                f"Club: {club_name}",
                f"Position: {player.position}",
                f"Audience: {package['label']}",
                f"Headline: {package['headline']}",
                f"Status: {bi_payload['status_label']}",
            ],
        ),
        (
            "Audience Focus",
            [f"- {item}" for item in package["focus"]] + [f"Use: {package['cta']}"],
        ),
        (
            "Profile",
            [
                f"Age: {player.age}",
                f"Country: {country_name}",
                f"Division: {division_name}",
                f"League level: {player.league_level}",
                f"Catalog club: {club_name}",
            ],
        ),
        (
            "Core Scores",
            [
                f"Current value: EUR {player.current_value}",
                f"Projected value: EUR {scores['projected_value']}",
                f"Valuation score: {scores['valuation_score']}",
                f"Classification: {scores['classification']}",
                f"Traffic light: {scores['traffic_light']}",
                f"Percentile rank: {calculate_percentile(player)}",
            ],
        ),
        (
            "Pillar Breakdown",
            [
                f"Performance: {scores['performance_score']}",
                f"Market: {scores['market_score']}",
                f"Marketing: {scores['marketing_score']}",
                f"Behavior: {scores['behavior_score']}",
                f"Potential: {scores['potential_score']}",
                f"Growth category: {scores['growth_potential_label']}",
            ],
        ),
        (
            "Longitudinal BI",
            [
                f"Window: {bi_payload['window_days']} days",
                f"Current score: {bi_payload['current']['scores']['valuation_score']}",
                f"Baseline score: {bi_payload['baseline']['valuation_score']}",
                f"Score delta: {bi_payload['delta']['valuation_score']:+.1f}",
                f"Value delta: {bi_payload['value_delta_pct']:+.1f}%",
                f"Best pillar: {bi_payload['best_pillar_label']}",
                f"Attention pillar: {bi_payload['worst_pillar_label']}",
            ],
        ),
        (
            "Projection & Opportunity",
            [
                f"Projected growth: {projection['projected_growth_pct']:.1f}%",
                f"Timing: {projection['timing_label']}",
                f"Readiness: {projection['readiness_label']}",
                f"Opportunity move: {opportunity['recommended_move']}",
                f"Window status: {opportunity['window_status']}",
            ],
        ),
        (
            "Alerts",
            [f"- {alert}" for alert in bi_payload["alerts"][:3]] or ["- No critical alerts in the current window."],
        ),
        (
            "Insights",
            [f"- {insight}" for insight in bi_payload["insights"][:3]],
        ),
    ]

    def _pdf_escape(value):
        return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    def _text(x, y, value, size=10):
        return [
            "BT",
            f"/F1 {size} Tf",
            f"{x} {y} Td",
            f"({_pdf_escape(value)}) Tj",
            "ET",
        ]

    def _rect(x, y, width, height, fill_rgb=None, stroke_rgb=None, line_width=1):
        commands = ["q"]
        if line_width:
            commands.append(f"{line_width} w")
        if fill_rgb:
            commands.append(f"{fill_rgb[0]} {fill_rgb[1]} {fill_rgb[2]} rg")
        if stroke_rgb:
            commands.append(f"{stroke_rgb[0]} {stroke_rgb[1]} {stroke_rgb[2]} RG")
        operator = "B" if fill_rgb and stroke_rgb else "f" if fill_rgb else "S"
        commands.append(f"{x} {y} {width} {height} re {operator}")
        commands.append("Q")
        return commands

    def _line(x1, y1, x2, y2, stroke_rgb=(0.35, 0.39, 0.45), line_width=1):
        return [
            "q",
            f"{line_width} w",
            f"{stroke_rgb[0]} {stroke_rgb[1]} {stroke_rgb[2]} RG",
            f"{x1} {y1} m {x2} {y2} l S",
            "Q",
        ]

    def _audience_visual(page, audience_key, x, y, width, height):
        page.extend(_rect(x, y, width, height, fill_rgb=(0.08, 0.10, 0.13), stroke_rgb=(0.18, 0.21, 0.26), line_width=0.8))
        titles = {
            "athlete": "Development Path",
            "agent": "Market Window",
            "club": "Club Fit Matrix",
            "consultancy": "Advisory Snapshot",
        }
        page.extend(_text(x + 12, y + height - 22, titles[audience_key], 12))
        if audience_key == "athlete":
            values = [
                ("Hoje", float(scores["final_score"])),
                ("90d", float(scores["final_score"] + bi_payload["delta"]["valuation_score"])),
                ("Prox.", float(projection["adaptation_score"])),
            ]
            base_x = x + 18
            base_y = y + 28
            max_h = 48
            max_v = max(max(v for _, v in values), 1)
            for idx, (label, value) in enumerate(values):
                bar_x = base_x + idx * 54
                bar_h = max_h * (value / max_v)
                page.extend(_rect(bar_x, base_y, 28, bar_h, fill_rgb=(0.00, 0.88, 0.72)))
                page.extend(_text(bar_x - 2, base_y - 12, label, 8))
                page.extend(_text(bar_x - 2, base_y + bar_h + 6, f"{value:.0f}", 7))
        elif audience_key == "agent":
            points = [
                (x + 24, y + 34),
                (x + 74, y + 54),
                (x + 124, y + 66),
                (x + 174, y + 78),
            ]
            for idx in range(len(points) - 1):
                page.extend(_line(points[idx][0], points[idx][1], points[idx + 1][0], points[idx + 1][1], stroke_rgb=(0.98, 0.78, 0.31), line_width=2))
            for px, py in points:
                page.extend(_rect(px - 3, py - 3, 6, 6, fill_rgb=(0.98, 0.78, 0.31)))
            page.extend(_text(x + 18, y + 16, "Timing", 8))
            page.extend(_text(x + 92, y + 16, "Narrativa", 8))
            page.extend(_text(x + 158, y + 16, "Janela", 8))
        elif audience_key == "club":
            metrics = [
                ("Fit", projection["adaptation_score"], (0.00, 0.88, 0.72)),
                ("Risk", 100 - projection["stagnation_risk_score"], (0.97, 0.15, 0.52)),
                ("Ready", projection["projected_growth_pct"] * 3, (0.24, 0.63, 0.95)),
            ]
            start_y = y + 24
            for idx, (label, value, color) in enumerate(metrics):
                row_y = start_y + idx * 18
                page.extend(_text(x + 12, row_y + 4, label, 8))
                page.extend(_rect(x + 46, row_y, 120, 10, fill_rgb=(0.18, 0.20, 0.24)))
                page.extend(_rect(x + 46, row_y, 120 * (max(min(value, 100), 0) / 100.0), 10, fill_rgb=color))
        else:
            cards = [
                ("Delta", comparison["contextual_summary"]["delta_vs_group"]),
                ("Growth", projection["projected_growth_pct"]),
                ("Window", 100 - min(opportunity["contract_months"] * 4, 100)),
            ]
            for idx, (label, value) in enumerate(cards):
                card_x = x + 14 + idx * 64
                page.extend(_rect(card_x, y + 24, 54, 38, fill_rgb=(0.10, 0.12, 0.16), stroke_rgb=(0.18, 0.21, 0.26), line_width=0.6))
                page.extend(_text(card_x + 8, y + 48, label, 7))
                page.extend(_text(card_x + 8, y + 30, f"{value:+.0f}" if label == "Delta" else f"{value:.0f}", 11))

    def _audience_detail_chart(page, audience_key, x, y, width, height):
        page.extend(_rect(x, y, width, height, fill_rgb=(0.08, 0.10, 0.13), stroke_rgb=(0.18, 0.21, 0.26), line_width=0.8))
        chart_titles = {
            "athlete": "Development Trend",
            "agent": "Market Momentum",
            "club": "Fit vs Risk",
            "consultancy": "Projection Matrix",
        }
        page.extend(_text(x + 12, y + height - 18, chart_titles[audience_key], 12))
        if audience_key == "athlete":
            data = [
                ("Base", float(bi_payload["baseline"]["valuation_score"])),
                ("Atual", float(bi_payload["current"]["scores"]["valuation_score"])),
                ("Proj.", float(projection["adaptation_score"])),
            ]
            base_x = x + 22
            base_y = y + 26
            max_h = 70
            max_v = max(max(v for _, v in data), 1)
            for idx, (label, value) in enumerate(data):
                bar_x = base_x + idx * 62
                bar_h = max_h * (value / max_v)
                page.extend(_rect(bar_x, base_y, 34, bar_h, fill_rgb=(0.00, 0.88, 0.72)))
                page.extend(_text(bar_x - 2, base_y - 12, label, 8))
                page.extend(_text(bar_x, base_y + bar_h + 6, f"{value:.0f}", 8))
        elif audience_key == "agent":
            values = [
                ("Val.", abs(float(bi_payload["value_delta_pct"]))),
                ("Mkt", float(scores["market_score"])),
                ("Win", 100 - min(opportunity["contract_months"] * 4, 100)),
            ]
            row_y = y + 34
            for idx, (label, value) in enumerate(values):
                current_y = row_y + idx * 24
                page.extend(_text(x + 14, current_y + 4, label, 8))
                page.extend(_rect(x + 48, current_y, 150, 10, fill_rgb=(0.18, 0.20, 0.24)))
                page.extend(_rect(x + 48, current_y, 150 * (max(min(value, 100), 0) / 100.0), 10, fill_rgb=(0.98, 0.78, 0.31)))
        elif audience_key == "club":
            cx = x + 95
            cy = y + 64
            page.extend(_line(cx, y + 24, cx, y + 112, stroke_rgb=(0.35, 0.39, 0.45)))
            page.extend(_line(x + 20, cy, x + 180, cy, stroke_rgb=(0.35, 0.39, 0.45)))
            px = x + 20 + (projection["adaptation_score"] / 100.0) * 160
            py = y + 24 + ((100 - projection["stagnation_risk_score"]) / 100.0) * 88
            page.extend(_rect(px - 4, py - 4, 8, 8, fill_rgb=(0.24, 0.63, 0.95)))
            page.extend(_text(x + 18, y + 116, "Risco", 8))
            page.extend(_text(x + 142, y + 116, "Fit", 8))
        else:
            metrics = [
                ("Delta", comparison["contextual_summary"]["delta_vs_group"], (0.24, 0.63, 0.95)),
                ("Growth", projection["projected_growth_pct"], (0.98, 0.78, 0.31)),
                ("Adapt", projection["adaptation_score"], (0.00, 0.88, 0.72)),
                ("Risk", projection["stagnation_risk_score"], (0.97, 0.15, 0.52)),
            ]
            start_x = x + 18
            for idx, (label, value, color) in enumerate(metrics):
                card_x = start_x + (idx % 2) * 88
                card_y = y + 28 + (idx // 2) * 34
                page.extend(_rect(card_x, card_y, 74, 24, fill_rgb=(0.10, 0.12, 0.16), stroke_rgb=(0.18, 0.21, 0.26), line_width=0.6))
                page.extend(_text(card_x + 8, card_y + 14, label, 7))
                page.extend(_text(card_x + 8, card_y + 5, f"{value:+.0f}" if label == "Delta" else f"{value:.0f}", 9))

    page_height_limit = 70

    pillar_chart = [
        ("Performance", float(scores["performance_score"]), (0.00, 0.88, 0.72)),
        ("Market", float(scores["market_score"]), (0.98, 0.78, 0.31)),
        ("Marketing", float(scores["marketing_score"]), (0.24, 0.63, 0.95)),
        ("Behavior", float(scores["behavior_score"]), (0.97, 0.15, 0.52)),
        ("Potential", float(scores["potential_score"]), (0.52, 0.80, 0.09)),
    ]
    value_chart = [
        ("Atual", float(player.current_value)),
        ("Piso", float(projection["value_band"]["floor"])),
        ("Esperado", float(projection["value_band"]["expected"])),
        ("Teto", float(projection["value_band"]["ceiling"])),
    ]
    max_value = max(value for _, value in value_chart) or 1.0

    pages = []

    def _new_page():
        return []

    def _page_header(page, title, subtitle_text="", page_number=1):
        page.extend(_rect(36, 36, 523, 770, fill_rgb=(0.04, 0.05, 0.07), stroke_rgb=(0.12, 0.14, 0.18), line_width=1))
        page.extend(_rect(36, 742, 523, 64, fill_rgb=(0.08, 0.10, 0.13)))
        page.extend(_text(52, 782, title, 20))
        if subtitle_text:
            page.extend(_text(52, 760, subtitle_text, 10))
        page.extend(_text(510, 760, f"Page {page_number}", 9))

    def _stat_card(page, x, y, width, title, value, note=""):
        page.extend(_rect(x, y, width, 54, fill_rgb=(0.10, 0.12, 0.16), stroke_rgb=(0.16, 0.18, 0.24), line_width=0.8))
        page.extend(_text(x + 12, y + 35, title, 8))
        page.extend(_text(x + 12, y + 17, value, 13))
        if note:
            page.extend(_text(x + 12, y + 5, note, 7))

    def _section_card(page, x, y_top, width, title, lines):
        height = 28 + (len(lines) * 14) + 12
        y = y_top - height
        page.extend(_rect(x, y, width, height, fill_rgb=(0.08, 0.10, 0.13), stroke_rgb=(0.18, 0.21, 0.26), line_width=0.8))
        page.extend(_text(x + 12, y_top - 18, title, 12))
        line_y = y_top - 38
        for line in lines:
            page.extend(_text(x + 14, line_y, line, 9))
            line_y -= 14
        return y - 14

    cover_page = _new_page()
    _page_header(cover_page, audience_title, subtitle, 1)
    cover_page.extend(_text(52, 720, package["headline"], 13))
    cover_page.extend(_text(52, 700, package["cta"], 10))
    _stat_card(cover_page, 52, 626, 116, "HBX Score", f"{scores['final_score']:.1f}", scores["classification"])
    _stat_card(cover_page, 178, 626, 116, "Valor atual", f"EUR {float(player.current_value)/1000000:.2f}M", player.position)
    _stat_card(cover_page, 304, 626, 116, "Valor proj.", f"EUR {float(scores['projected_value'])/1000000:.2f}M", projection["timing_label"])
    _stat_card(cover_page, 430, 626, 103, "Janela", opportunity["window_status"], opportunity["recommended_move"])

    cover_page.extend(_text(50, 594, "Score Charts", 14))
    left_chart_x = 50
    left_chart_y = 420
    left_chart_w = 240
    left_chart_h = 150
    right_chart_x = 320
    right_chart_y = left_chart_y
    right_chart_w = 220
    right_chart_h = 150

    cover_page.extend(_rect(left_chart_x, left_chart_y, left_chart_w, left_chart_h, fill_rgb=(0.08, 0.10, 0.13), stroke_rgb=(0.20, 0.23, 0.28), line_width=0.8))
    cover_page.extend(_rect(right_chart_x, right_chart_y, right_chart_w, right_chart_h, fill_rgb=(0.08, 0.10, 0.13), stroke_rgb=(0.20, 0.23, 0.28), line_width=0.8))
    cover_page.extend(_text(left_chart_x + 12, left_chart_y + left_chart_h - 16, "Pillar Breakdown", 11))
    cover_page.extend(_text(right_chart_x + 12, right_chart_y + right_chart_h - 16, "Value Range", 11))

    bar_x = left_chart_x + 18
    bar_y = left_chart_y + 20
    bar_h = 18
    bar_gap = 8
    bar_max_w = left_chart_w - 95
    for index, (label, value, color) in enumerate(pillar_chart):
        current_y = bar_y + ((len(pillar_chart) - 1 - index) * (bar_h + bar_gap))
        cover_page.extend(_text(bar_x, current_y + 4, label, 8))
        cover_page.extend(_rect(bar_x + 58, current_y, bar_max_w, bar_h, fill_rgb=(0.18, 0.20, 0.24)))
        cover_page.extend(_rect(bar_x + 58, current_y, bar_max_w * (max(min(value, 100), 0) / 100.0), bar_h, fill_rgb=color))
        cover_page.extend(_text(bar_x + 58 + bar_max_w + 6, current_y + 4, f"{value:.0f}", 8))

    chart_base_x = right_chart_x + 18
    chart_base_y = right_chart_y + 30
    chart_height = 88
    chart_bar_w = 32
    chart_gap = 16
    cover_page.extend(_line(chart_base_x, chart_base_y, chart_base_x + 170, chart_base_y))
    cover_page.extend(_line(chart_base_x, chart_base_y, chart_base_x, chart_base_y + chart_height + 8))
    for idx, (label, value) in enumerate(value_chart):
        x = chart_base_x + 12 + idx * (chart_bar_w + chart_gap)
        height = chart_height * (value / max_value)
        fill = (0.98, 0.78, 0.31) if label in {"Esperado", "Teto"} else (0.24, 0.63, 0.95) if label == "Atual" else (0.00, 0.88, 0.72)
        cover_page.extend(_rect(x, chart_base_y, chart_bar_w, height, fill_rgb=fill))
        cover_page.extend(_text(x - 2, chart_base_y - 12, label, 8))
        cover_page.extend(_text(x - 6, chart_base_y + height + 6, f"{value/1000000:.1f}M", 7))

    cover_page.extend(_text(50, 388, "Audience Focus", 14))
    cover_page.extend(_rect(50, 258, 490, 106, fill_rgb=(0.08, 0.10, 0.13), stroke_rgb=(0.18, 0.21, 0.26), line_width=0.8))
    _audience_visual(cover_page, audience, 50, 258, 208, 106)
    cover_page.extend(_text(276, 342, "Audience Focus", 12))
    bullet_y = 320
    for item in package["focus"][:3]:
        cover_page.extend(_text(282, bullet_y, f"- {item}", 10))
        bullet_y -= 18
    cover_page.extend(_text(282, 266, f"Use: {package['cta']}", 10))
    pages.append(cover_page)

    current_page = _new_page()
    _page_header(current_page, audience_title, "Analytical details", 2)
    y_position = 720
    _audience_detail_chart(current_page, audience, 50, 548, 230, 130)
    y_position = 530
    for title, lines in sections:
        estimated_height = 28 + (len(lines) * 14) + 12
        if y_position - estimated_height < page_height_limit:
            pages.append(current_page)
            current_page = _new_page()
            _page_header(current_page, audience_title, "Continued analytical details", len(pages) + 1)
            y_position = 720
        y_position = _section_card(current_page, 50, y_position, 490, title, lines)
    pages.append(current_page)

    page_streams = ["\n".join(page).encode("latin-1", errors="ignore") for page in pages]

    objects = [b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"]
    kids = []
    next_object_id = 3
    content_object_ids = []
    for _ in page_streams:
        kids.append(f"{next_object_id} 0 R")
        content_object_ids.append(next_object_id + 1)
        next_object_id += 2
    font_object_id = next_object_id
    objects.append(f"2 0 obj << /Type /Pages /Kids [{' '.join(kids)}] /Count {len(page_streams)} >> endobj\n".encode("latin-1"))
    page_object_id = 3
    for content_id in content_object_ids:
        objects.append(
            f"{page_object_id} 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents {content_id} 0 R /Resources << /Font << /F1 {font_object_id} 0 R >> >> >> endobj\n".encode("latin-1")
        )
        page_object_id += 2
    for idx, page_stream in enumerate(page_streams):
        content_id = content_object_ids[idx]
        objects.append(f"{content_id} 0 obj << /Length {len(page_stream)} >> stream\n".encode("latin-1") + page_stream + b"\nendstream endobj\n")
    objects.append(f"{font_object_id} 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n".encode("latin-1"))

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
