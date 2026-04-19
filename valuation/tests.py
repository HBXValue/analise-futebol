import json
from datetime import date
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.hashers import check_password, make_password
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Country, Division
from clubs.models import Club
from valuation.models import (
    AnalystNote,
    AthleteIdentity,
    AthleteSnapshot,
    AthleteAIInsight,
    AthleteCareerEntry,
    AthleteContract,
    Athlete360Core,
    GoCarrieraCheckIn,
    BehaviorMetrics,
    BehavioralAggregate,
    BehaviorSnapshot,
    CareerIntelligenceCase,
    CareerPrognosis,
    ClubCompetitiveContext,
    CoachProfile,
    CompetitiveDiagnosis,
    DevelopmentPlan,
    DataSourceLog,
    HBXValueProfile,
    IndividualDevelopmentPlan,
    LiveAnalysisEvent,
    LiveAnalysisSession,
    LivePlayerEvaluation,
    MarketMetrics,
    MarketAggregate,
    MarketSnapshot,
    MarketingMetrics,
    MarketingAggregate,
    MarketingSnapshot,
    OnBallEvent,
    PerformanceMetrics,
    PerformanceSnapshot,
    Player,
    PlayerHistory,
    ProjectionSnapshot,
    ProjectionAggregate,
    ProgressTracking,
    ScenarioLab,
    ScoreSnapshot,
    TeamContextSnapshot,
    PerformanceAggregate,
    OpportunityAggregate,
    AthleteTransfer,
    User,
)
from valuation.career_services import case_completion
from valuation.services import (
    build_growth_insights,
    build_projection_scenarios,
    calculate_growth_rate,
    calculate_scores,
    import_players_from_csv,
    live_analysis_summary,
    on_ball_decision_analysis,
    save_hbx_value_profile,
    save_manual_history_snapshot,
    save_on_ball_event,
    save_player_bundle,
    save_player_history_snapshot,
    sync_live_report_to_integrated_modules,
    simulate_uplift,
)


class ValuationServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(email="analyst@hbeleven.com", password_hash=make_password("secret123"))
        self.player = Player.objects.create(
            user=self.user,
            name="Lucas Silva",
            age=22,
            position="Midfielder",
            current_value=Decimal("5000000.00"),
            league_level="Brazil Serie A",
            club_origin="Palmeiras",
        )
        PerformanceMetrics.objects.create(
            player=self.player,
            xg=0.25,
            xa=0.21,
            passes_pct=88,
            dribbles_pct=67,
            tackles_pct=61,
            high_intensity_distance=11200,
            final_third_recoveries=7,
        )
        MarketMetrics.objects.create(
            player=self.player,
            annual_growth=24,
            club_interest=76,
            league_score=81,
            age_factor=84,
            club_reputation=73,
        )
        MarketingMetrics.objects.create(
            player=self.player,
            followers=1350000,
            engagement=9.4,
            media_mentions=180,
            sponsorships=5,
            sentiment_score=78,
        )
        BehaviorMetrics.objects.create(
            player=self.player,
            conscientiousness=82,
            adaptability=79,
            resilience=77,
            deliberate_practice=84,
            executive_function=74,
            leadership=72,
        )

    def test_valuation_scores_are_calculated(self):
        scores = calculate_scores(self.player)
        self.assertGreater(scores["valuation_score"], 0)
        self.assertGreater(scores["projected_value"], self.player.current_value)
        self.assertIn(
            scores["growth_potential_label"],
            {"Prospecto de Elite", "Alto Potencial", "Em Desenvolvimento", "Baixa Projeção"},
        )

    def test_password_hash_is_secure(self):
        self.assertTrue(check_password("secret123", self.user.password_hash))

    def test_history_snapshot_and_projection_are_calculated(self):
        save_player_history_snapshot(self.player, date(2026, 1, 1))
        self.player.current_value = Decimal("6000000.00")
        self.player.save()
        save_player_history_snapshot(self.player, date(2026, 4, 1))

        self.assertEqual(PlayerHistory.objects.filter(player=self.player).count(), 2)
        self.assertAlmostEqual(calculate_growth_rate(self.player), 0.2, places=2)

        scenarios = build_projection_scenarios(self.player, "pt", "12")
        self.assertIn("expected", scenarios["scenarios"])
        self.assertGreater(scenarios["scenarios"]["aggressive"], scenarios["scenarios"]["expected"])

        insights = build_growth_insights(self.player, "pt", "12")
        self.assertIn("main_driver", insights)
        self.assertGreaterEqual(insights["projected_growth_pct"], 0)

    def test_history_snapshot_creates_hbx_360_snapshots(self):
        save_player_history_snapshot(self.player, date(2026, 3, 1))

        self.assertTrue(AthleteIdentity.objects.filter(player=self.player).exists())
        self.assertTrue(AthleteSnapshot.objects.filter(player=self.player, snapshot_date=date(2026, 3, 1)).exists())
        self.assertTrue(PerformanceSnapshot.objects.filter(player=self.player, snapshot_date=date(2026, 3, 1)).exists())
        self.assertTrue(BehaviorSnapshot.objects.filter(player=self.player, snapshot_date=date(2026, 3, 1)).exists())
        self.assertTrue(MarketSnapshot.objects.filter(player=self.player, snapshot_date=date(2026, 3, 1)).exists())
        self.assertTrue(MarketingSnapshot.objects.filter(player=self.player, snapshot_date=date(2026, 3, 1)).exists())
        self.assertTrue(ScoreSnapshot.objects.filter(player=self.player, snapshot_date=date(2026, 3, 1)).exists())
        self.assertTrue(ProjectionSnapshot.objects.filter(player=self.player, snapshot_date=date(2026, 3, 1)).exists())
        self.assertTrue(DataSourceLog.objects.filter(player=self.player, source_type=DataSourceLog.SourceType.SYSTEM).exists())

    def test_hbx_360_snapshot_updates_same_day_and_source(self):
        save_player_history_snapshot(self.player, date(2026, 3, 1))
        self.player.current_value = Decimal("6500000.00")
        self.player.save()
        save_player_history_snapshot(self.player, date(2026, 3, 1))

        self.assertEqual(ScoreSnapshot.objects.filter(player=self.player, snapshot_date=date(2026, 3, 1)).count(), 1)
        market_snapshot = MarketSnapshot.objects.get(player=self.player, snapshot_date=date(2026, 3, 1))
        self.assertEqual(market_snapshot.current_value, Decimal("6500000.00"))

    def test_manual_snapshot_can_override_values(self):
        snapshot = save_manual_history_snapshot(
            self.player,
            {
                "date": date(2026, 2, 15),
                "current_value": Decimal("5400000.00"),
                "performance_score": 80,
                "market_score": 70,
                "marketing_score": 60,
                "behavior_score": 75,
                "valuation_score": 74,
            },
        )
        self.assertEqual(snapshot.valuation_score, 74)
        self.assertEqual(snapshot.current_value, Decimal("5400000.00"))

    @patch("valuation.ai_service.refresh_ai_insights_for_player")
    def test_save_player_bundle_refreshes_ai_insights(self, mocked_refresh):
        save_player_bundle(
            self.user,
            {
                "name": "Vitor Sena",
                "public_name": "Vitor Sena",
                "age": 18,
                "birth_date": date(2008, 2, 14),
                "nationality": "Brasil",
                "position": "Winger",
                "secondary_positions": "Forward",
                "dominant_foot": "left",
                "height_cm": 178,
                "weight_kg": 72,
                "current_value": Decimal("1100000.00"),
                "league_level": "Brazil Serie B",
                "club_origin": "Vila Nova",
                "category": "professional",
                "contract_months_remaining": 18,
                "squad_status": "rotation",
                "athlete_objectives": "gain_minutes",
                "profile_notes": "Boa resposta competitiva e pronta para crescer.",
                "xg": 0.2,
                "xa": 0.15,
                "passes_pct": 82,
                "dribbles_pct": 69,
                "tackles_pct": 44,
                "high_intensity_distance": 9800,
                "final_third_recoveries": 4,
                "annual_growth": 13,
                "club_interest": 61,
                "league_score": 67,
                "age_factor": 80,
                "club_reputation": 52,
                "instagram_handle": "@vitorsena",
                "tiktok_handle": "@vitorsena",
                "x_handle": "@vitorsena",
                "google_news_query": "Vitor Sena Vila Nova",
                "youtube_query": "Vitor Sena highlights",
                "followers": 12000,
                "engagement": 3.5,
                "media_mentions": 12,
                "sponsorships": 1,
                "sentiment_score": 73,
                "conscientiousness": 79,
                "adaptability": 77,
                "resilience": 75,
                "deliberate_practice": 82,
                "executive_function": 68,
                "leadership": 66,
            },
        )
        mocked_refresh.assert_called_once()

    @patch("valuation.ai_service.refresh_ai_insights_for_player")
    def test_save_hbx_value_profile_refreshes_ai_insights(self, mocked_refresh):
        save_hbx_value_profile(
            self.player,
            {
                "athlete_name": self.player.name,
                "club_name": self.player.club_origin,
                "position": self.player.position,
                "current_value": float(self.player.current_value),
                "instagram_handle": "@lucas",
                "google_news_query": "Lucas Silva Palmeiras",
                "youtube_query": "Lucas Silva highlights",
                "tiktok_handle": "@lucas",
                "manual_context": "Bom momento competitivo.",
                "google_news_mentions": 12,
                "google_news_momentum": 55,
                "google_news_sentiment": 70,
                "google_news_reach": 48,
                "google_news_authority": 60,
                "youtube_mentions": 8,
                "youtube_momentum": 50,
                "youtube_sentiment": 68,
                "youtube_reach": 52,
                "youtube_authority": 58,
                "manual_mentions": 4,
                "manual_momentum": 62,
                "manual_sentiment": 75,
                "manual_reach": 44,
                "manual_authority": 57,
                "manual_performance_rating": 78,
                "manual_attention_spike": 64,
                "manual_market_response": 59,
                "manual_visibility_efficiency": 61,
                "manual_note": "Resposta positiva do mercado.",
            },
        )
        mocked_refresh.assert_called_once_with(self.player)

    @patch("valuation.ai_service.refresh_ai_insights_for_player")
    def test_manual_snapshot_refreshes_ai_insights(self, mocked_refresh):
        save_manual_history_snapshot(
            self.player,
            {
                "date": date(2026, 2, 15),
                "current_value": Decimal("5400000.00"),
            },
        )
        mocked_refresh.assert_called_once_with(self.player)

    def test_uplift_simulation_compares_current_vs_target(self):
        result = simulate_uplift(
            self.player,
            {
                "xg": 20,
                "xa": 25,
                "passes_pct": 5,
                "dribbles_pct": 10,
                "tackles_pct": 8,
                "high_intensity_distance": 5,
                "final_third_recoveries": 15,
            },
            "pt",
        )
        self.assertGreater(result["performance_jump"], 0)
        self.assertTrue(result["metric_rows"])
        self.assertIn("club_attractiveness", result)
        self.assertEqual(result["metric_rows"][0]["increase_pct"], 20)

    def test_on_ball_analysis_generates_kpis(self):
        save_on_ball_event(
            self.player,
            {
                "date": date(2026, 4, 1),
                "pressure_status": "under_pressure",
                "field_zone": "midfield",
                "action_type": "pass",
                "outcome": "positive",
                "notes": "",
            },
        )
        save_on_ball_event(
            self.player,
            {
                "date": date(2026, 4, 1),
                "pressure_status": "no_pressure",
                "field_zone": "attack",
                "action_type": "dribble",
                "outcome": "negative",
                "notes": "",
            },
        )
        analysis = on_ball_decision_analysis(self.player, "pt")
        self.assertEqual(analysis["total_actions"], 2)
        self.assertEqual(analysis["decision_success_rate"], 50.0)
        self.assertTrue(analysis["action_distribution"])

    def test_live_analysis_summary_aggregates_points_and_retention(self):
        created_at = timezone.make_aware(datetime(2026, 4, 1, 15, 0, 0))
        session = LiveAnalysisSession.objects.create(
            player=self.player,
            observed_on=date(2026, 4, 1),
            kickoff_time=datetime.strptime("15:00", "%H:%M").time(),
            venue="Allianz Parque",
            home_away="home",
            weather="Ceu aberto",
            played_position="Midfielder",
            starter_status="starter",
            confidence=8,
            intensity=7,
            focus=8,
            decision_making=7,
            resilience=8,
            anxiety=4,
            motivation=8,
            communication=7,
            discipline=8,
            emotional_control=7,
        )
        LiveAnalysisEvent.objects.create(player=self.player, session=session, created_at=created_at, match_period="first_half", minute=12, event_type="received", duration_seconds=2.0, points=0.5)
        LiveAnalysisEvent.objects.create(player=self.player, session=session, created_at=created_at, match_period="first_half", minute=13, event_type="forward_pass", duration_seconds=2.0, points=1.2)
        summary = live_analysis_summary(session, "pt")
        self.assertEqual(summary["total_points"], 1.7)
        self.assertEqual(summary["average_retention"], 2.0)

    @patch("valuation.ai_service.refresh_ai_insights_for_player")
    def test_sync_live_report_refreshes_ai_insights(self, mocked_refresh):
        report = LivePlayerEvaluation.objects.create(
            user=self.user,
            player=self.player,
            athlete_name=self.player.name,
            position=self.player.position,
            match_date=date(2026, 4, 10),
            team="Palmeiras",
            opponent="Bahia",
            competition="Serie A",
            analyst_name="Analista HBX",
            minutes_played=72,
            payload={
                "avaliacao_geral": {
                    "resumo_do_desempenho": "Atleta sustentou boa intensidade.",
                    "pontos_fortes": "Ataque ao espaco",
                    "pontos_a_melhorar": "Tomada de decisao no ultimo passe",
                },
            },
        )
        sync_live_report_to_integrated_modules(self.player, report)
        mocked_refresh.assert_called_once_with(self.player)

    def test_csv_import_creates_related_records(self):
        content = (
            "name,age,position,current_value,league_level,club_origin,xg,xa,passes_pct,dribbles_pct,tackles_pct,"
            "high_intensity_distance,final_third_recoveries,annual_growth,club_interest,league_score,age_factor,"
            "club_reputation,followers,engagement,media_mentions,sponsorships,sentiment_score,conscientiousness,"
            "adaptability,resilience,deliberate_practice,executive_function,leadership\n"
            "Rafael Gomes,20,Forward,2000000,Brazil Serie B,Sport Recife,0.41,0.14,80,70,49,10400,5,16,68,72,80,64,980000,7.2,90,3,75,78,80,76,83,70,66\n"
        )
        uploaded = BytesIO(content.encode("utf-8"))
        uploaded.name = "players.csv"
        result = import_players_from_csv(self.user, uploaded)
        self.assertEqual(result.created, 1)
        self.assertTrue(Player.objects.filter(name="Rafael Gomes").exists())
        imported_player = Player.objects.get(name="Rafael Gomes")
        self.assertTrue(CareerIntelligenceCase.objects.filter(user=self.user, player=imported_player).exists())

    def test_save_player_bundle_creates_integrated_career_case(self):
        player = save_player_bundle(
            self.user,
            {
                "name": "Vitor Sena",
                "public_name": "Vitor Sena",
                "age": 18,
                "birth_date": date(2008, 2, 14),
                "nationality": "Brasil",
                "position": "Winger",
                "secondary_positions": "Forward",
                "dominant_foot": "left",
                "height_cm": 178,
                "weight_kg": 72,
                "current_value": Decimal("1100000.00"),
                "league_level": "Brazil Serie B",
                "club_origin": "Vila Nova",
                "category": "professional",
                "contract_months_remaining": 18,
                "squad_status": "rotation",
                "athlete_objectives": "gain_minutes",
                "profile_notes": "Boa resposta competitiva e pronta para crescer.",
                "xg": 0.2,
                "xa": 0.15,
                "passes_pct": 82,
                "dribbles_pct": 69,
                "tackles_pct": 44,
                "high_intensity_distance": 9800,
                "final_third_recoveries": 4,
                "annual_growth": 13,
                "club_interest": 61,
                "league_score": 67,
                "age_factor": 80,
                "club_reputation": 52,
                "instagram_handle": "@vitorsena",
                "tiktok_handle": "@vitorsena",
                "x_handle": "@vitorsena",
                "google_news_query": "Vitor Sena Vila Nova",
                "youtube_query": "Vitor Sena highlights",
                "followers": 12000,
                "engagement": 3.5,
                "media_mentions": 12,
                "sponsorships": 1,
                "sentiment_score": 73,
                "conscientiousness": 79,
                "adaptability": 77,
                "resilience": 75,
                "deliberate_practice": 82,
                "executive_function": 68,
                "leadership": 66,
            },
        )
        case = CareerIntelligenceCase.objects.get(player=player)
        self.assertEqual(case.athlete_name, "Vitor Sena")
        self.assertEqual(case.current_club, "Vila Nova")
        self.assertEqual(case.nationality, "Brasil")
        self.assertEqual(case.dominant_foot, "left")
        self.assertEqual(case.contract_months_remaining, 18)
        self.assertEqual(case.athlete_objectives, ["gain_minutes"])
        self.assertEqual(case.analyst_notes, "Boa resposta competitiva e pronta para crescer.")
        self.assertEqual(player.marketing_metrics.instagram_handle, "@vitorsena")
        self.assertEqual(player.marketing_metrics.google_news_query, "Vitor Sena Vila Nova")
        self.assertIsNotNone(player.division_reference)
        self.assertIsNotNone(player.club_reference)

    def test_save_player_bundle_creates_catalog_references_for_new_division_and_club(self):
        player = save_player_bundle(
            self.user,
            {
                "name": "Alan Souza",
                "age": 20,
                "position": "Winger",
                "current_value": Decimal("800000.00"),
                "league_level": "Paulistão Série A2",
                "club_origin": "Clube Exemplo SP",
                "xg": 0.18,
                "xa": 0.12,
                "passes_pct": 80,
                "dribbles_pct": 64,
                "tackles_pct": 40,
                "high_intensity_distance": 9700,
                "final_third_recoveries": 3,
                "annual_growth": 10,
                "club_interest": 58,
                "league_score": 60,
                "age_factor": 79,
                "club_reputation": 45,
                "followers": 9000,
                "engagement": 2.4,
                "media_mentions": 6,
                "sponsorships": 1,
                "sentiment_score": 70,
                "conscientiousness": 75,
                "adaptability": 76,
                "resilience": 72,
                "deliberate_practice": 79,
                "executive_function": 67,
                "leadership": 63,
            },
        )
        self.assertEqual(player.division_reference.name, "Paulistão Série A2")
        self.assertEqual(player.club_reference.official_name, "Clube Exemplo SP")
        self.assertTrue(Division.objects.filter(name="Paulistão Série A2").exists())
        self.assertTrue(Club.objects.filter(official_name="Clube Exemplo SP").exists())

    def test_save_player_bundle_uses_selected_foreign_country_for_division_and_club(self):
        call_command("seed_european_top_divisions")
        spain = Country.objects.get(code="ESP")
        laliga = Division.objects.get(country=spain, level=1)
        club = Club.objects.create(
            country=spain,
            division=laliga,
            official_name="Real Madrid",
            short_name="Real Madrid",
            status=Club.Status.ACTIVE,
        )

        player = save_player_bundle(
            self.user,
            {
                "country_code": "ESP",
                "name": "Adrian Torres",
                "age": 21,
                "position": "Winger",
                "current_value": Decimal("1800000.00"),
                "league_level": "LaLiga",
                "club_origin": "Real Madrid",
                "xg": 0.22,
                "xa": 0.16,
                "passes_pct": 82,
                "dribbles_pct": 67,
                "tackles_pct": 34,
                "high_intensity_distance": 9850,
                "final_third_recoveries": 4,
                "annual_growth": 13,
                "club_interest": 66,
                "league_score": 84,
                "age_factor": 77,
                "club_reputation": 95,
                "followers": 23000,
                "engagement": 4.2,
                "media_mentions": 12,
                "sponsorships": 2,
                "sentiment_score": 79,
                "conscientiousness": 80,
                "adaptability": 77,
                "resilience": 78,
                "deliberate_practice": 81,
                "executive_function": 74,
                "leadership": 69,
            },
        )

        self.assertEqual(player.division_reference_id, laliga.id)
        self.assertEqual(player.club_reference_id, club.id)
        self.assertEqual(player.division_reference.country.code, "ESP")

    def test_seed_initial_data_creates_brazilian_main_divisions(self):
        call_command("seed_initial_data")
        brazil = Country.objects.get(code="BRA")
        divisions = list(Division.objects.filter(country=brazil, scope=Division.Scope.NATIONAL).order_by("level"))
        self.assertEqual([division.short_name for division in divisions[:4]], ["Série A", "Série B", "Série C", "Série D"])

    def test_normalize_brazil_clubs_merges_duplicates_and_updates_player_reference(self):
        call_command("seed_initial_data")
        brazil = Country.objects.get(code="BRA")
        serie_a = Division.objects.get(country=brazil, level=1)
        duplicate_a = Club.objects.create(country=brazil, division=serie_a, official_name="Esporte Clube Bahia", short_name="Bahia")
        canonical = Club.objects.create(country=brazil, division=serie_a, official_name="Bahia", short_name="Bahia")
        player = save_player_bundle(
            self.user,
            {
                "name": "Ruan Costa",
                "age": 19,
                "position": "Winger",
                "current_value": Decimal("950000.00"),
                "league_level": "Série A",
                "club_origin": "Esporte Clube Bahia",
                "xg": 0.2,
                "xa": 0.12,
                "passes_pct": 81,
                "dribbles_pct": 66,
                "tackles_pct": 37,
                "high_intensity_distance": 9600,
                "final_third_recoveries": 4,
                "annual_growth": 11,
                "club_interest": 54,
                "league_score": 63,
                "age_factor": 78,
                "club_reputation": 52,
                "followers": 10000,
                "engagement": 2.1,
                "media_mentions": 10,
                "sponsorships": 1,
                "sentiment_score": 71,
                "conscientiousness": 76,
                "adaptability": 75,
                "resilience": 74,
                "deliberate_practice": 79,
                "executive_function": 66,
                "leadership": 64,
            },
        )
        player.club_reference = duplicate_a
        player.save(update_fields=["club_reference"])

        call_command("normalize_brazil_clubs")

        player.refresh_from_db()
        self.assertEqual(player.club_reference_id, canonical.id)
        self.assertFalse(Club.objects.filter(id=duplicate_a.id).exists())


class ValuationViewsTests(TestCase):
    def test_signup_and_redirect(self):
        response = self.client.post(
            reverse("signup"),
            {"email": "geral@hbelevensocial.com", "password": "secretpass", "confirm_password": "secretpass"},
        )
        self.assertRedirects(response, reverse("dashboard"))

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, reverse("login"))

    def test_player_create_redirects_to_edit_for_continuation(self):
        user = User.objects.create(email="create-edit@club.com", password_hash=make_password("secretpass"))
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()

        response = self.client.post(
            reverse("player-create"),
            {
                "name": "Carlos Ponte",
                "birth_date": "",
                "position": "Centroavante",
                "current_value": "900000.00",
                "league_level": "Serie B",
                "club_origin": "Sport Recife",
            },
        )

        player = Player.objects.get(user=user, name="Carlos Ponte")
        self.assertRedirects(response, f"{reverse('player-edit', args=[player.id])}?lang=pt")

    def test_logged_user_can_create_manual_snapshot(self):
        user = User.objects.create(email="agent@club.com", password_hash=make_password("secretpass"))
        player = Player.objects.create(
            user=user,
            name="Pedro Costa",
            age=23,
            position="Winger",
            current_value=Decimal("2500000.00"),
            league_level="Portugal Liga",
            club_origin="Braga",
        )
        PerformanceMetrics.objects.create(player=player)
        MarketMetrics.objects.create(player=player)
        MarketingMetrics.objects.create(player=player)
        BehaviorMetrics.objects.create(player=player)
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()
        response = self.client.post(
            reverse("player-snapshot", args=[player.id]),
            {"date": "2026-03-01", "current_value": "2700000.00", "valuation_score": "68"},
        )
        self.assertRedirects(response, f"{reverse('player-operations', args=[player.id])}?lang=pt")
        self.assertTrue(PlayerHistory.objects.filter(player=player, date="2026-03-01").exists())
        self.assertTrue(ScenarioLab.objects.filter(player=player, snapshot_date="2026-03-01").exists())

    def test_logged_user_can_create_intervention_records(self):
        user = User.objects.create(email="coach@club.com", password_hash=make_password("secretpass"))
        player = Player.objects.create(
            user=user,
            name="Mateus Lima",
            age=21,
            position="Forward",
            current_value=Decimal("3200000.00"),
            league_level="Brazil Serie A",
            club_origin="Fortaleza",
        )
        PerformanceMetrics.objects.create(player=player)
        MarketMetrics.objects.create(player=player)
        MarketingMetrics.objects.create(player=player)
        BehaviorMetrics.objects.create(player=player)
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()

        self.client.post(
            reverse("player-note", args=[player.id]),
            {
                "date": "2026-04-01",
                "analysis_text": "Baixa intensidade sem bola.",
                "strengths": "Boa aceleracao.",
                "weaknesses": "Pouca participacao ofensiva.",
            },
        )
        self.client.post(
            reverse("player-plan", args=[player.id]),
            {
                "goal": "Aumentar participacao ofensiva",
                "target_metric": "xG",
                "target_value": "0.45",
                "deadline": "2026-08-01",
            },
        )
        self.client.post(
            reverse("player-progress", args=[player.id]),
            {"metric": "xG", "current_value": "0.30", "target_value": "0.45"},
        )

        self.assertTrue(AnalystNote.objects.filter(player=player).exists())
        self.assertTrue(DevelopmentPlan.objects.filter(player=player).exists())
        self.assertTrue(ProgressTracking.objects.filter(player=player).exists())

    def test_player_operations_page_renders(self):
        user = User.objects.create(email="ops@club.com", password_hash=make_password("secretpass"))
        player = Player.objects.create(
            user=user,
            name="Andre Matos",
            age=22,
            position="Forward",
            current_value=Decimal("2100000.00"),
            league_level="Brazil Serie B",
            club_origin="Goias",
        )
        PerformanceMetrics.objects.create(player=player)
        MarketMetrics.objects.create(player=player)
        MarketingMetrics.objects.create(player=player)
        BehaviorMetrics.objects.create(player=player)
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()

        response = self.client.get(reverse("player-operations", args=[player.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Athlete Operations")
        self.assertContains(response, "Scenario Lab")
        self.assertContains(response, "Voltar ao Dashboard")

    def test_logged_user_can_create_on_ball_event(self):
        user = User.objects.create(email="analyst2@club.com", password_hash=make_password("secretpass"))
        player = Player.objects.create(
            user=user,
            name="Daniel Rocha",
            age=24,
            position="Midfielder",
            current_value=Decimal("2800000.00"),
            league_level="Brazil Serie B",
            club_origin="Ceara",
        )
        PerformanceMetrics.objects.create(player=player)
        MarketMetrics.objects.create(player=player)
        MarketingMetrics.objects.create(player=player)
        BehaviorMetrics.objects.create(player=player)
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()
        response = self.client.post(
            reverse("player-on-ball-event", args=[player.id]),
            {
                "date": "2026-04-03",
                "pressure_status": "under_pressure",
                "field_zone": "midfield",
                "action_type": "pass",
                "outcome": "positive",
                "notes": "Quebrou a linha de pressao.",
            },
        )
        self.assertRedirects(response, f"{reverse('dashboard')}?lang=pt")
        self.assertTrue(OnBallEvent.objects.filter(player=player).exists())

    def test_logged_user_can_save_live_analysis_report(self):
        user = User.objects.create(email="analyst3@club.com", password_hash=make_password("secretpass"))
        player = Player.objects.create(
            user=user,
            name="Leo Martins",
            age=20,
            position="Winger",
            current_value=Decimal("1500000.00"),
            league_level="Brazil Serie C",
            club_origin="Paysandu",
        )
        PerformanceMetrics.objects.create(player=player)
        MarketMetrics.objects.create(player=player)
        MarketingMetrics.objects.create(player=player)
        BehaviorMetrics.objects.create(player=player)
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()
        payload = {
            "informacoes_gerais": {
                "nome_atleta": "Leo Martins",
                "numero_camisa": "11",
                "posicao": "Atacante",
                "equipe": "Paysandu",
                "adversario": "Remo",
                "competicao": "Serie C",
                "data": "2026-04-09",
                "analista_responsavel": "Scout 1",
                "minutos_jogados": "28",
                "observacao_inicial": "",
                "player_id": str(player.id),
            },
            "indicadores_tecnicos": {"Passe certo": 5, "Finalizacao": 2},
            "indicadores_defensivos": {"Desarme": 1},
            "indicadores_taticos": {"Tomada de decisao": 4},
            "indicadores_fisicos": {"fonte": "manual", "arquivo_nome": "", "valores": {"Numero de sprints": "7"}},
            "indicadores_psicologicos": {"Concentracao": 4},
            "indicadores_especificos_posicao": {
                "grupo_posicao": "Atacante",
                "valores": {"Gol": 1, "Ataque a profundidade": 3},
            },
            "avaliacao_geral": {"resumo_do_desempenho": "Entrou bem no jogo."},
            "metadados": {"origem_dados_fisicos": "manual"},
        }
        response = self.client.post(
            reverse("live-analysis-session"),
            {
                "payload_json": json.dumps(payload),
            },
        )
        report = LivePlayerEvaluation.objects.get(player=player)
        self.assertRedirects(response, f"{reverse('live-analysis')}?report={report.id}&lang=pt")
        self.assertEqual(report.position, "Atacante")
        self.assertEqual(report.payload["indicadores_especificos_posicao"]["valores"]["Gol"], 1)
        case = CareerIntelligenceCase.objects.get(user=user, player=player)
        self.assertEqual(case.current_club, "Paysandu")
        self.assertIn("Analise ao vivo 09/04/2026", case.analyst_notes)
        self.assertTrue(PlayerHistory.objects.filter(player=player, date="2026-04-09").exists())
        analyst_note = AnalystNote.objects.get(player=player, date="2026-04-09")
        self.assertIn("Entrou bem no jogo.", analyst_note.analysis_text)

    def test_live_analysis_uses_registered_player_identity_when_selected(self):
        user = User.objects.create(email="identity@club.com", password_hash=make_password("secretpass"))
        country = Country.objects.get(code="BRA")
        division = Division.objects.filter(country=country, level=1).first()
        if division is None:
            division = Division.objects.create(country=country, name="Serie A", short_name="Serie A", level=1)
        club = Club.objects.create(country=country, division=division, official_name="Sociedade Esportiva Palmeiras", short_name="Palmeiras")
        opponent = Club.objects.create(country=country, division=division, official_name="Santos Futebol Clube", short_name="Santos")
        player = Player.objects.create(
            user=user,
            name="Rafael Dias",
            age=19,
            position="Atacante",
            current_value=Decimal("1000000.00"),
            league_level="Cadastro antigo",
            club_origin="Cadastro antigo",
            division_reference=division,
            club_reference=club,
        )
        PerformanceMetrics.objects.create(player=player)
        MarketMetrics.objects.create(player=player)
        MarketingMetrics.objects.create(player=player)
        BehaviorMetrics.objects.create(player=player)
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()
        payload = {
            "informacoes_gerais": {
                "nome_atleta": "Nome digitado errado",
                "numero_camisa": "9",
                "posicao": "Meia / armador",
                "equipe": "Equipe digitada errada",
                "adversario": opponent.short_name,
                "competicao": "Serie A",
                "data": "2026-04-10",
                "analista_responsavel": "Scout 1",
                "minutos_jogados": "90",
                "observacao_inicial": "",
                "player_id": str(player.id),
            },
            "indicadores_tecnicos": {},
            "indicadores_defensivos": {},
            "indicadores_taticos": {},
            "indicadores_fisicos": {"fonte": "manual", "arquivo_nome": "", "valores": {}},
            "indicadores_psicologicos": {},
            "indicadores_especificos_posicao": {"grupo_posicao": "", "valores": {}},
            "avaliacao_geral": {"resumo_do_desempenho": ""},
            "metadados": {"origem_dados_fisicos": "manual"},
        }
        self.client.post(reverse("live-analysis-session"), {"payload_json": json.dumps(payload)})
        report = LivePlayerEvaluation.objects.get(player=player)
        self.assertEqual(report.athlete_name, "Rafael Dias")
        self.assertEqual(report.position, "Atacante")
        self.assertEqual(report.team, "Palmeiras")
        self.assertEqual(report.opponent, "Santos")
        self.assertEqual(report.payload["informacoes_gerais"]["equipe"], "Palmeiras")

    def test_live_analysis_page_renders(self):
        user = User.objects.create(email="live@club.com", password_hash=make_password("secretpass"))
        player = Player.objects.create(
            user=user,
            name="Igor Nunes",
            age=22,
            position="Midfielder",
            current_value=Decimal("1800000.00"),
            league_level="Brazil Serie B",
            club_origin="Goias",
        )
        PerformanceMetrics.objects.create(player=player)
        MarketMetrics.objects.create(player=player)
        MarketingMetrics.objects.create(player=player)
        BehaviorMetrics.objects.create(player=player)
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()
        response = self.client.get(reverse("live-analysis"))
        self.assertEqual(response.status_code, 200)

    def test_live_analysis_shows_consolidated_match_context_for_selected_athlete(self):
        user = User.objects.create(email="live-context@club.com", password_hash=make_password("secretpass"))
        player = Player.objects.create(
            user=user,
            name="Joao Pedro",
            age=21,
            position="Atacante",
            current_value=Decimal("1300000.00"),
            league_level="Brazil Serie B",
            club_origin="Goias",
        )
        PerformanceMetrics.objects.create(player=player, xg=0.31, xa=0.14, passes_pct=78, dribbles_pct=64, tackles_pct=30, final_third_recoveries=3)
        MarketMetrics.objects.create(player=player)
        MarketingMetrics.objects.create(player=player)
        BehaviorMetrics.objects.create(player=player)
        save_player_history_snapshot(player, date(2026, 4, 15))
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()

        response = self.client.get(f"{reverse('live-analysis')}?athlete={player.id}&lang=pt")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Athlete360 Match Context")
        self.assertContains(response, "Team Context oficial")
        self.assertContains(response, "Resumo para análise da partida")

    def test_player_edit_page_renders_athlete_360_tabs(self):
        user = User.objects.create(email="athlete360@club.com", password_hash=make_password("secretpass"))
        player = Player.objects.create(
            user=user,
            name="Marcos Vieira",
            age=21,
            position="Midfielder",
            current_value=Decimal("900000.00"),
            league_level="Brazil Serie B",
            club_origin="Goias",
        )
        PerformanceMetrics.objects.create(player=player)
        MarketMetrics.objects.create(player=player)
        MarketingMetrics.objects.create(player=player)
        BehaviorMetrics.objects.create(player=player)
        save_player_history_snapshot(player, date(2026, 4, 15))
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()

        response = self.client.get(reverse("player-edit", args=[player.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Athlete 360")
        self.assertContains(response, "Timeline 360")
        self.assertContains(response, "Behavior")
        self.assertContains(response, "Carreira")
        self.assertContains(response, "Overview")
        self.assertContains(response, "Team Context")
        self.assertContains(response, "Athlete360 Executive Summary")
        self.assertContains(response, "Team context oficial")
        self.assertContains(response, "Novo atleta")

    def test_athlete360_core_and_aggregates_are_consolidated(self):
        user = User.objects.create(email="core360@club.com", password_hash=make_password("secretpass"))
        player = Player.objects.create(
            user=user,
            name="Marcio Lemos",
            public_name="Marcio",
            age=20,
            position="Winger",
            current_value=Decimal("1400000.00"),
            league_level="Brazil Serie B",
            club_origin="Avaí",
            category=Player.Category.PROFESSIONAL,
            squad_status=Player.SquadStatus.STARTER,
            contract_months_remaining=11,
        )
        PerformanceMetrics.objects.create(player=player, xg=0.22, xa=0.17, passes_pct=78, dribbles_pct=70, tackles_pct=31, high_intensity_distance=9800, final_third_recoveries=4)
        MarketMetrics.objects.create(player=player, annual_growth=16, club_interest=68, league_score=70, age_factor=82, club_reputation=64)
        MarketingMetrics.objects.create(player=player, followers=15000, engagement=5.2, media_mentions=18, sponsorships=1, sentiment_score=73)
        BehaviorMetrics.objects.create(player=player, conscientiousness=7, adaptability=8, resilience=7, deliberate_practice=8, executive_function=7, leadership=6)
        save_player_history_snapshot(player, date(2026, 4, 15))

        core = Athlete360Core.objects.get(player=player)
        self.assertEqual(core.current_club, "Avaí")
        self.assertEqual(core.primary_position, "Winger")
        self.assertTrue(PerformanceAggregate.objects.filter(player=player).exists())
        self.assertTrue(BehavioralAggregate.objects.filter(player=player).exists())
        self.assertTrue(MarketAggregate.objects.filter(player=player).exists())
        self.assertTrue(MarketingAggregate.objects.filter(player=player).exists())
        self.assertTrue(ProjectionAggregate.objects.filter(player=player).exists())
        self.assertTrue(OpportunityAggregate.objects.filter(player=player).exists())
        self.assertTrue(TeamContextSnapshot.objects.filter(player=player).exists())
        snapshot = AthleteSnapshot.objects.filter(player=player).first()
        self.assertIn("club_name", snapshot.team_context_summary_json)
        self.assertIn("final_score", snapshot.hbx_score_summary_json)

    def test_player_career_entry_can_be_saved(self):
        user = User.objects.create(email="career-entry@club.com", password_hash=make_password("secretpass"))
        player = Player.objects.create(
            user=user,
            name="Pedro Alves",
            age=20,
            position="Forward",
            current_value=Decimal("1200000.00"),
            league_level="Brazil Serie C",
            club_origin="Paysandu",
        )
        PerformanceMetrics.objects.create(player=player)
        MarketMetrics.objects.create(player=player)
        MarketingMetrics.objects.create(player=player)
        BehaviorMetrics.objects.create(player=player)
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()

        response = self.client.post(
            f"{reverse('player-career-entry', args=[player.id])}?lang=pt",
            {
                "club_name": "Paysandu",
                "country_name": "Brasil",
                "division_name": "Serie C",
                "season_label": "2026",
                "start_date": "2026-01-10",
                "move_type": "permanent",
                "is_current": "on",
                "notes": "Primeira temporada completa no profissional.",
            },
        )

        self.assertRedirects(response, f"{reverse('player-edit', args=[player.id])}?lang=pt")
        entry = AthleteCareerEntry.objects.get(player=player)
        self.assertEqual(entry.club_name, "Paysandu")
        self.assertTrue(entry.is_current)

    def test_player_contract_can_be_saved(self):
        user = User.objects.create(email="contract@club.com", password_hash=make_password("secretpass"))
        player = Player.objects.create(
            user=user,
            name="Ruan Lima",
            age=22,
            position="Defender",
            current_value=Decimal("1500000.00"),
            league_level="Brazil Serie B",
            club_origin="Ceara",
        )
        PerformanceMetrics.objects.create(player=player)
        MarketMetrics.objects.create(player=player)
        MarketingMetrics.objects.create(player=player)
        BehaviorMetrics.objects.create(player=player)
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()

        response = self.client.post(
            f"{reverse('player-contract', args=[player.id])}?lang=pt",
            {
                "club_name": "Ceara",
                "start_date": "2026-01-01",
                "end_date": "2027-12-31",
                "monthly_salary": "12000",
                "release_clause": "3000000",
                "status": "active",
                "is_current": "on",
                "contract_months_remaining": "24",
                "notes": "Contrato principal da temporada.",
            },
        )

        self.assertRedirects(response, f"{reverse('player-edit', args=[player.id])}?lang=pt")
        contract = AthleteContract.objects.get(player=player)
        self.assertEqual(contract.club_name, "Ceara")
        self.assertTrue(contract.is_current)

    def test_player_transfer_can_be_saved(self):
        user = User.objects.create(email="transfer@club.com", password_hash=make_password("secretpass"))
        player = Player.objects.create(
            user=user,
            name="Felipe Souza",
            age=23,
            position="Midfielder",
            current_value=Decimal("2100000.00"),
            league_level="Brazil Serie A",
            club_origin="Bahia",
        )
        PerformanceMetrics.objects.create(player=player)
        MarketMetrics.objects.create(player=player)
        MarketingMetrics.objects.create(player=player)
        BehaviorMetrics.objects.create(player=player)
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()

        response = self.client.post(
            f"{reverse('player-transfer', args=[player.id])}?lang=pt",
            {
                "from_club": "Sport",
                "to_club": "Bahia",
                "transfer_date": "2026-02-10",
                "transfer_type": "permanent",
                "transfer_fee": "1800000",
                "currency": "EUR",
                "notes": "Compra definitiva.",
            },
        )

        self.assertRedirects(response, f"{reverse('player-edit', args=[player.id])}?lang=pt")
        transfer = AthleteTransfer.objects.get(player=player)
        self.assertEqual(transfer.to_club, "Bahia")
        self.assertEqual(transfer.currency, "EUR")

    def test_player_go_carriera_checkin_creates_behavior_snapshot(self):
        user = User.objects.create(email="gocarriera@club.com", password_hash=make_password("secretpass"))
        player = Player.objects.create(
            user=user,
            name="Caio Mendes",
            age=19,
            position="Winger",
            current_value=Decimal("800000.00"),
            league_level="Brazil Serie B",
            club_origin="Avaí",
        )
        PerformanceMetrics.objects.create(player=player)
        MarketMetrics.objects.create(player=player)
        MarketingMetrics.objects.create(player=player)
        BehaviorMetrics.objects.create(player=player)
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()

        response = self.client.post(
            f"{reverse('player-go-carriera-checkin', args=[player.id])}?lang=pt",
            {
                "checkin_date": "2026-04-16",
                "sleep_quality": "8",
                "hydration": "9",
                "nutrition": "8",
                "energy": "8",
                "focus": "7",
                "mood": "8",
                "motivation": "9",
                "post_error_response": "8",
                "soreness": "3",
                "recovery": "8",
                "treatment_adherence": "7",
                "injury_status": "none",
                "notes": "Respondeu bem ao treino e manteve boa energia.",
            },
        )

        self.assertRedirects(response, f"{reverse('player-edit', args=[player.id])}?lang=pt")
        checkin = GoCarrieraCheckIn.objects.get(player=player, checkin_date="2026-04-16")
        self.assertEqual(checkin.energy, 8)
        snapshot = BehaviorSnapshot.objects.get(player=player, snapshot_date="2026-04-16", source="go_carriera")
        self.assertGreater(snapshot.behavior_score, 0)
        self.assertGreater(snapshot.readiness_score, 0)

    def test_player_edit_page_renders_comparative_intelligence(self):
        user = User.objects.create(email="comparative@club.com", password_hash=make_password("secretpass"))
        main_player = Player.objects.create(
            user=user,
            name="Arthur Costa",
            age=20,
            position="Winger",
            current_value=Decimal("1200000.00"),
            league_level="Brazil Serie B",
            club_origin="Avai",
            category=Player.Category.PROFESSIONAL,
        )
        peer_one = Player.objects.create(
            user=user,
            name="Bruno Lima",
            age=21,
            position="Winger",
            current_value=Decimal("1350000.00"),
            league_level="Brazil Serie B",
            club_origin="Ceara",
            category=Player.Category.PROFESSIONAL,
        )
        peer_two = Player.objects.create(
            user=user,
            name="Carlos Dias",
            age=19,
            position="Winger",
            current_value=Decimal("980000.00"),
            league_level="Brazil Serie B",
            club_origin="Sport",
            category=Player.Category.PROFESSIONAL,
        )
        for athlete in (main_player, peer_one, peer_two):
            PerformanceMetrics.objects.create(player=athlete)
            MarketMetrics.objects.create(player=athlete)
            MarketingMetrics.objects.create(player=athlete)
            BehaviorMetrics.objects.create(player=athlete)
            save_player_history_snapshot(athlete, date(2026, 4, 15))
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()

        response = self.client.get(reverse("player-edit", args=[main_player.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Comparative Intelligence")
        self.assertContains(response, "Bruno Lima")
        self.assertContains(response, "Carlos Dias")

    def test_player_edit_page_renders_projection_intelligence(self):
        user = User.objects.create(email="projection@club.com", password_hash=make_password("secretpass"))
        main_player = Player.objects.create(
            user=user,
            name="Diego Rocha",
            age=20,
            position="Winger",
            current_value=Decimal("1500000.00"),
            league_level="Brazil Serie B",
            club_origin="Sport",
            category=Player.Category.PROFESSIONAL,
        )
        peer = Player.objects.create(
            user=user,
            name="Enzo Prado",
            age=21,
            position="Winger",
            current_value=Decimal("2200000.00"),
            league_level="Brazil Serie A",
            club_origin="Bahia",
            category=Player.Category.PROFESSIONAL,
        )
        for athlete in (main_player, peer):
            PerformanceMetrics.objects.create(player=athlete)
            MarketMetrics.objects.create(player=athlete, annual_growth=12, club_interest=65, league_score=70, age_factor=78, club_reputation=66)
            MarketingMetrics.objects.create(player=athlete)
            BehaviorMetrics.objects.create(player=athlete, conscientiousness=7, adaptability=7, resilience=7, deliberate_practice=8, executive_function=7, leadership=6)
            save_player_history_snapshot(athlete, date(2026, 1, 10))
            athlete.current_value = athlete.current_value + Decimal("150000.00")
            athlete.save(update_fields=["current_value"])
            save_player_history_snapshot(athlete, date(2026, 4, 10))
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()

        response = self.client.get(reverse("player-edit", args=[main_player.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Projection Intelligence")
        self.assertContains(response, "Faixa de valorizacao")
        self.assertContains(response, "Mercados com maior aderencia")

    def test_player_edit_page_renders_opportunity_intelligence(self):
        user = User.objects.create(email="opportunity@club.com", password_hash=make_password("secretpass"))
        main_player = Player.objects.create(
            user=user,
            name="Fabio Nunes",
            age=21,
            position="Winger",
            current_value=Decimal("1800000.00"),
            league_level="Brazil Serie B",
            club_origin="Ceara",
            category=Player.Category.PROFESSIONAL,
            contract_months_remaining=10,
        )
        peer_one = Player.objects.create(
            user=user,
            name="Gabriel Torres",
            age=22,
            position="Winger",
            current_value=Decimal("2300000.00"),
            league_level="Brazil Serie A",
            club_origin="Bahia",
            category=Player.Category.PROFESSIONAL,
        )
        peer_two = Player.objects.create(
            user=user,
            name="Henrique Silva",
            age=20,
            position="Winger",
            current_value=Decimal("2100000.00"),
            league_level="Portugal Liga 1",
            club_origin="Braga",
            category=Player.Category.PROFESSIONAL,
        )
        for athlete in (main_player, peer_one, peer_two):
            PerformanceMetrics.objects.create(player=athlete)
            MarketMetrics.objects.create(player=athlete, annual_growth=15, club_interest=68, league_score=72, age_factor=80, club_reputation=70)
            MarketingMetrics.objects.create(player=athlete)
            BehaviorMetrics.objects.create(player=athlete, conscientiousness=7, adaptability=8, resilience=7, deliberate_practice=8, executive_function=7, leadership=6)
            save_player_history_snapshot(athlete, date(2026, 1, 10))
            athlete.current_value = athlete.current_value + Decimal("200000.00")
            athlete.save(update_fields=["current_value"])
            save_player_history_snapshot(athlete, date(2026, 4, 10))
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()

        response = self.client.get(reverse("player-edit", args=[main_player.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Opportunity Intelligence")
        self.assertContains(response, "Clubes alvo")
        self.assertContains(response, "Riscos da movimentacao")

    def test_player_create_page_shows_new_registration_state(self):
        user = User.objects.create(email="new-athlete@club.com", password_hash=make_password("secretpass"))
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()

        response = self.client.get(f"{reverse('player-create')}?lang=pt")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Novo cadastro ativo")
        self.assertContains(response, "Você está no cadastro de novo atleta")

    def test_data_hub_renders_ingestion_control(self):
        user = User.objects.create(email="data@club.com", password_hash=make_password("secretpass"))
        player = Player.objects.create(
            user=user,
            name="Nicolas Souza",
            age=20,
            position="Midfielder",
            current_value=Decimal("1200000.00"),
            league_level="Brazil Serie B",
            club_origin="Goias",
        )
        PerformanceMetrics.objects.create(player=player)
        MarketMetrics.objects.create(player=player)
        MarketingMetrics.objects.create(player=player)
        BehaviorMetrics.objects.create(player=player)
        save_player_history_snapshot(player, date(2026, 4, 15))
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()

        response = self.client.get(reverse("data"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Athlete360 Ingestion Control")
        self.assertContains(response, "Source Of Truth Por Origem")
        self.assertContains(response, "Preparação Base44")
        self.assertContains(response, "Preparação Go Carriera")

    def test_reports_view_supports_audience_packages(self):
        user = User.objects.create(email="reports-audience@club.com", password_hash=make_password("secretpass"))
        player = Player.objects.create(
            user=user,
            name="Igor Matos",
            age=22,
            position="Winger",
            current_value=Decimal("2100000.00"),
            league_level="Brazil Serie A",
            club_origin="Bahia",
            category=Player.Category.PROFESSIONAL,
            contract_months_remaining=12,
        )
        peer = Player.objects.create(
            user=user,
            name="Joao Pedro",
            age=21,
            position="Winger",
            current_value=Decimal("2600000.00"),
            league_level="Portugal Liga 1",
            club_origin="Porto",
            category=Player.Category.PROFESSIONAL,
        )
        for athlete in (player, peer):
            PerformanceMetrics.objects.create(player=athlete)
            MarketMetrics.objects.create(player=athlete, annual_growth=14, club_interest=69, league_score=74, age_factor=79, club_reputation=72)
            MarketingMetrics.objects.create(player=athlete)
            BehaviorMetrics.objects.create(player=athlete, conscientiousness=7, adaptability=8, resilience=7, deliberate_practice=8, executive_function=7, leadership=6)
            save_player_history_snapshot(athlete, date(2026, 1, 10))
            athlete.current_value = athlete.current_value + Decimal("200000.00")
            athlete.save(update_fields=["current_value"])
            save_player_history_snapshot(athlete, date(2026, 4, 10))
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()

        response = self.client.get(f"{reverse('reports')}?player={player.id}&audience=agent&compare_window=90")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Report por publico")
        self.assertContains(response, "Agente")
        self.assertContains(response, "Valorizacao")

    def test_player_report_pdf_supports_audience_variant(self):
        user = User.objects.create(email="report-pdf@club.com", password_hash=make_password("secretpass"))
        player = Player.objects.create(
            user=user,
            name="Lucas Ribeiro",
            age=21,
            position="Winger",
            current_value=Decimal("1900000.00"),
            league_level="Brazil Serie A",
            club_origin="Bahia",
            category=Player.Category.PROFESSIONAL,
            contract_months_remaining=12,
        )
        peer = Player.objects.create(
            user=user,
            name="Mateus Lima",
            age=22,
            position="Winger",
            current_value=Decimal("2400000.00"),
            league_level="Portugal Liga 1",
            club_origin="Sporting",
            category=Player.Category.PROFESSIONAL,
        )
        for athlete in (player, peer):
            PerformanceMetrics.objects.create(player=athlete)
            MarketMetrics.objects.create(player=athlete, annual_growth=12, club_interest=66, league_score=73, age_factor=80, club_reputation=71)
            MarketingMetrics.objects.create(player=athlete)
            BehaviorMetrics.objects.create(player=athlete, conscientiousness=7, adaptability=8, resilience=7, deliberate_practice=8, executive_function=7, leadership=6)
            save_player_history_snapshot(athlete, date(2026, 1, 10))
            athlete.current_value = athlete.current_value + Decimal("180000.00")
            athlete.save(update_fields=["current_value"])
            save_player_history_snapshot(athlete, date(2026, 4, 10))
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()

        response = self.client.get(f"{reverse('player-report', args=[player.id])}?audience=club&lang=pt")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("lucas_ribeiro_club_report.pdf", response["Content-Disposition"])
        self.assertIn(b"Club Presentation Report", response.content)
        self.assertIn(b"Score Charts", response.content)
        self.assertIn(b"Value Range", response.content)
        self.assertIn(b"Club Fit Matrix", response.content)
        self.assertIn(b"Fit vs Risk", response.content)
        self.assertIn(b"/Count 4", response.content)

    def test_hbx_value_score_page_renders(self):
        user = User.objects.create(email="hbx@club.com", password_hash=make_password("secretpass"))
        player = Player.objects.create(
            user=user,
            name="Luis Fernando",
            age=20,
            position="Atacante",
            current_value=Decimal("2400000.00"),
            league_level="Brazil Serie A",
            club_origin="Fortaleza",
        )
        PerformanceMetrics.objects.create(
            player=player,
            xg=0.32,
            xa=0.18,
            passes_pct=82,
            dribbles_pct=64,
            tackles_pct=37,
            high_intensity_distance=10500,
            final_third_recoveries=6,
        )
        MarketMetrics.objects.create(
            player=player,
            annual_growth=18,
            club_interest=72,
            league_score=75,
            age_factor=83,
            club_reputation=68,
        )
        MarketingMetrics.objects.create(
            player=player,
            followers=420000,
            engagement=7.8,
            media_mentions=95,
            sponsorships=2,
            sentiment_score=74,
        )
        BehaviorMetrics.objects.create(player=player)
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()
        response = self.client.get(reverse("hbx-value-score"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Market Intelligence")
        self.assertContains(response, "Market Intelligence aplicado ao futebol")
        self.assertContains(response, "Google News query")
        self.assertContains(response, "Buscar YouTube Data API")
        self.assertContains(response, "Buscar TikTok")
        self.assertNotContains(response, "Escopo do MVP")
        self.assertContains(response, "Contexto do atleta")
        self.assertContains(response, "Mercado atual")

    def test_hbx_value_score_post_persists_profile_for_player(self):
        user = User.objects.create(email="hbx-save@club.com", password_hash=make_password("secretpass"))
        player = Player.objects.create(
            user=user,
            name="Joao Teste",
            age=22,
            position="Atacante",
            current_value=Decimal("1300000.00"),
            league_level="Série B",
            club_origin="Sport Recife",
        )
        PerformanceMetrics.objects.create(player=player)
        MarketMetrics.objects.create(player=player)
        MarketingMetrics.objects.create(player=player)
        BehaviorMetrics.objects.create(player=player)
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()
        response = self.client.post(
            reverse("hbx-value-score"),
            {
                "player_id": player.id,
                "source": "manual",
                "instagram_handle": "@joaoteste",
                "google_news_query": "Joao Teste",
                "youtube_query": "Joao Teste highlights",
                "instagram_mentions": "70",
                "instagram_momentum": "72",
                "instagram_sentiment": "68",
                "instagram_reach": "64",
                "instagram_authority": "58",
                "google_news_mentions": "40",
                "google_news_momentum": "66",
                "google_news_sentiment": "70",
                "google_news_reach": "61",
                "google_news_authority": "80",
                "youtube_mentions": "20",
                "youtube_momentum": "74",
                "youtube_sentiment": "69",
                "youtube_reach": "60",
                "youtube_authority": "65",
                "manual_mentions": "10",
                "manual_momentum": "64",
                "manual_sentiment": "66",
                "manual_reach": "40",
                "manual_authority": "55",
                "manual_performance_rating": "75",
                "manual_attention_spike": "66",
                "manual_market_response": "71",
                "manual_visibility_efficiency": "69",
                "manual_note": "Entrou no radar apos boa sequencia.",
                "narrative_keywords": "promissor, decisivo, em ascensao",
            },
        )
        self.assertRedirects(response, f"{reverse('hbx-value-score')}?player={player.id}&lang=pt")
        profile = HBXValueProfile.objects.get(player=player)
        self.assertEqual(profile.source, "manual")
        self.assertEqual(profile.mention_volume, 140)
        self.assertGreater(profile.market_perception_index, 0)
        self.assertEqual(profile.narrative_keywords, ["promissor", "decisivo", "em ascensao"])
        self.assertEqual(profile.source_targets["instagram"]["handle"], "@joaoteste")
        self.assertEqual(profile.source_collection["google_news"]["mentions"], 40)
        self.assertEqual(profile.delivery_payload["manual_note"], "Entrou no radar apos boa sequencia.")

    @patch("valuation.views.fetch_google_news_signals")
    def test_hbx_value_score_can_collect_google_news_by_player_name(self, mocked_fetch):
        mocked_fetch.return_value = {
            "query": "Joao Teste",
            "rss_url": "https://news.google.com/rss/search?q=Joao%20Teste",
            "mentions": 6,
            "momentum": 82.0,
            "sentiment": 63.0,
            "reach": 57.0,
            "authority": 78.0,
            "articles": [
                {
                    "title": "Joao Teste vive grande fase no clube",
                    "link": "https://example.com/noticia",
                    "source": "ge",
                    "published_at": "2026-04-12T12:00:00+00:00",
                }
            ],
        }
        user = User.objects.create(email="hbx-rss@club.com", password_hash=make_password("secretpass"))
        player = Player.objects.create(
            user=user,
            name="Joao Teste",
            age=22,
            position="Atacante",
            current_value=Decimal("1300000.00"),
            league_level="Série B",
            club_origin="Sport Recife",
        )
        PerformanceMetrics.objects.create(player=player)
        MarketMetrics.objects.create(player=player)
        MarketingMetrics.objects.create(player=player)
        BehaviorMetrics.objects.create(player=player)
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()

        response = self.client.post(
            reverse("hbx-value-score"),
            {
                "player_id": player.id,
                "action": "fetch_google_news",
                "google_news_query": "",
                "narrative_keywords": "promissor, em ascensao",
            },
        )

        self.assertRedirects(response, f"{reverse('hbx-value-score')}?player={player.id}&lang=pt")
        mocked_fetch.assert_called_once_with("Joao Teste", None)
        profile = HBXValueProfile.objects.get(player=player)
        self.assertEqual(profile.source, "ai")
        self.assertEqual(profile.source_collection["google_news"]["mentions"], 6)
        self.assertEqual(profile.source_targets["google_news"]["query"], "Joao Teste")
        self.assertEqual(profile.source_collection["google_news"]["articles"][0]["source"], "ge")

    @patch("valuation.views.fetch_instagram_signals")
    def test_hbx_value_score_can_collect_instagram_by_handle(self, mocked_fetch):
        mocked_fetch.return_value = {
            "handle": "@marciosantos",
            "username": "marciosantos",
            "name": "Marcio Santos",
            "biography": "Atleta profissional",
            "website": "https://example.com",
            "profile_picture_url": "https://example.com/profile.jpg",
            "followers_count": 185000,
            "media_count": 214,
            "mentions": 214,
            "momentum": 61.5,
            "sentiment": 60.0,
            "reach": 58.2,
            "authority": 63.7,
        }
        user = User.objects.create(email="hbx-ig@club.com", password_hash=make_password("secretpass"))
        player = Player.objects.create(
            user=user,
            name="Marcio Santos",
            age=22,
            position="Atacante",
            current_value=Decimal("1500000.00"),
            league_level="Série B",
            club_origin="Sport Recife",
        )
        PerformanceMetrics.objects.create(player=player)
        MarketMetrics.objects.create(player=player)
        MarketingMetrics.objects.create(player=player)
        BehaviorMetrics.objects.create(player=player)
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()

        response = self.client.post(
            reverse("hbx-value-score"),
            {
                "player_id": player.id,
                "action": "fetch_instagram",
                "instagram_handle": "@marciosantos",
                "narrative_keywords": "promissor",
            },
        )

        self.assertRedirects(response, f"{reverse('hbx-value-score')}?player={player.id}&lang=pt")
        mocked_fetch.assert_called_once_with("@marciosantos")
        profile = HBXValueProfile.objects.get(player=player)
        self.assertEqual(profile.source, "ai")
        self.assertEqual(profile.source_targets["instagram"]["handle"], "@marciosantos")
        self.assertEqual(profile.source_collection["instagram"]["profile"]["username"], "marciosantos")
        self.assertEqual(profile.source_collection["instagram"]["profile"]["followers_count"], 185000)

    @patch("valuation.views.fetch_youtube_signals")
    def test_hbx_value_score_can_collect_youtube_by_player_name(self, mocked_fetch):
        mocked_fetch.return_value = {
            "query": "Carlos Video",
            "channel_id": "UC123",
            "mentions": 5,
            "momentum": 79.0,
            "sentiment": 66.0,
            "reach": 61.0,
            "authority": 74.0,
            "videos": [
                {
                    "title": "Carlos Video highlights 2026",
                    "video_id": "abc123",
                    "channel_title": "ge",
                    "published_at": "2026-04-12T12:00:00+00:00",
                }
            ],
        }
        user = User.objects.create(email="hbx-yt@club.com", password_hash=make_password("secretpass"))
        player = Player.objects.create(
            user=user,
            name="Carlos Video",
            age=21,
            position="Atacante",
            current_value=Decimal("1100000.00"),
            league_level="Série C",
            club_origin="Santa Cruz",
        )
        PerformanceMetrics.objects.create(player=player)
        MarketMetrics.objects.create(player=player)
        MarketingMetrics.objects.create(player=player)
        BehaviorMetrics.objects.create(player=player)
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()

        response = self.client.post(
            reverse("hbx-value-score"),
            {
                "player_id": player.id,
                "action": "fetch_youtube",
                "youtube_query": "",
                "youtube_channel_id": "UC123",
                "narrative_keywords": "promissor",
            },
        )

        self.assertRedirects(response, f"{reverse('hbx-value-score')}?player={player.id}&lang=pt")
        mocked_fetch.assert_called_once_with("Carlos Video", "UC123")
        profile = HBXValueProfile.objects.get(player=player)
        self.assertEqual(profile.source, "ai")
        self.assertEqual(profile.source_collection["youtube"]["mentions"], 5)
        self.assertEqual(profile.source_targets["youtube"]["channel_id"], "UC123")
        self.assertEqual(profile.source_collection["youtube"]["videos"][0]["video_id"], "abc123")

    @patch("valuation.views.fetch_tiktok_signals")
    def test_hbx_value_score_can_collect_tiktok_by_player_name(self, mocked_fetch):
        mocked_fetch.return_value = {
            "query": "Leo Tik",
            "handle": "@leotik",
            "mentions": 4,
            "momentum": 77.0,
            "sentiment": 64.0,
            "reach": 72.0,
            "authority": 68.0,
            "videos": [
                {
                    "id": "tk1",
                    "username": "scoutfutebol",
                    "description": "Leo Tik em grande fase",
                    "published_at": "2026-04-12T10:00:00+00:00",
                }
            ],
        }
        user = User.objects.create(email="hbx-tt@club.com", password_hash=make_password("secretpass"))
        player = Player.objects.create(
            user=user,
            name="Leo Tik",
            age=20,
            position="Lateral",
            current_value=Decimal("900000.00"),
            league_level="Série D",
            club_origin="Treze",
        )
        PerformanceMetrics.objects.create(player=player)
        MarketMetrics.objects.create(player=player)
        MarketingMetrics.objects.create(player=player)
        BehaviorMetrics.objects.create(player=player)
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()

        response = self.client.post(
            reverse("hbx-value-score"),
            {
                "player_id": player.id,
                "action": "fetch_tiktok",
                "tiktok_query": "",
                "tiktok_handle": "@leotik",
                "narrative_keywords": "ascensao",
            },
        )

        self.assertRedirects(response, f"{reverse('hbx-value-score')}?player={player.id}&lang=pt")
        mocked_fetch.assert_called_once_with("Leo Tik", "@leotik")
        profile = HBXValueProfile.objects.get(player=player)
        self.assertEqual(profile.source, "ai")
        self.assertEqual(profile.source_collection["tiktok"]["mentions"], 4)
        self.assertEqual(profile.source_targets["tiktok"]["handle"], "@leotik")
        self.assertEqual(profile.source_collection["tiktok"]["videos"][0]["id"], "tk1")

    def test_dashboard_exposes_hbx_value_score_link(self):
        user = User.objects.create(email="dash-hbx@club.com", password_hash=make_password("secretpass"))
        player = Player.objects.create(
            user=user,
            name="Pedro Lima",
            age=21,
            position="Lateral",
            current_value=Decimal("1100000.00"),
            league_level="Brazil Serie B",
            club_origin="America-MG",
        )
        PerformanceMetrics.objects.create(player=player)
        MarketMetrics.objects.create(player=player)
        MarketingMetrics.objects.create(player=player)
        BehaviorMetrics.objects.create(player=player)
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("hbx-value-score"))

    def test_dashboard_shows_integrated_career_and_live_status(self):
        user = User.objects.create(email="dash@club.com", password_hash=make_password("secretpass"))
        player = Player.objects.create(
            user=user,
            name="Caio Mendes",
            age=21,
            position="Centroavante",
            current_value=Decimal("2100000.00"),
            league_level="Brazil Serie B",
            club_origin="Criciuma",
        )
        PerformanceMetrics.objects.create(player=player)
        MarketMetrics.objects.create(player=player)
        MarketingMetrics.objects.create(player=player)
        BehaviorMetrics.objects.create(player=player)
        case = CareerIntelligenceCase.objects.create(
            user=user,
            player=player,
            athlete_name="Caio Mendes",
            position_primary="Centroavante",
            current_club="Criciuma",
            current_step="development",
        )
        LivePlayerEvaluation.objects.create(
            user=user,
            player=player,
            athlete_name="Caio Mendes",
            position="Atacante",
            team="Criciuma",
            opponent="Sport",
            competition="Serie B",
            match_date=date(2026, 4, 10),
            analyst_name="Scout 2",
            physical_data_source="manual",
            payload={"avaliacao_geral": {"resumo_do_desempenho": "Gerou ameaca constante em profundidade."}},
        )
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Estado integrado")
        self.assertContains(response, "development".title())
        self.assertContains(response, "Gerou ameaca constante em profundidade.")

    def test_dashboard_shows_hbx_value_when_profile_exists(self):
        user = User.objects.create(email="dash-hbx-profile@club.com", password_hash=make_password("secretpass"))
        player = Player.objects.create(
            user=user,
            name="Carlos HBX",
            age=23,
            position="Lateral",
            current_value=Decimal("1700000.00"),
            league_level="Série C",
            club_origin="Paysandu",
        )
        PerformanceMetrics.objects.create(player=player)
        MarketMetrics.objects.create(player=player)
        MarketingMetrics.objects.create(player=player)
        BehaviorMetrics.objects.create(player=player)
        HBXValueProfile.objects.create(
            player=player,
            source="manual",
            mention_volume=120,
            mention_momentum=70,
            sentiment_score=67,
            estimated_reach=63,
            source_relevance=71,
            performance_rating=74,
            attention_spike=68,
            market_response=69,
            visibility_efficiency=66,
            market_perception_index=68.5,
            performance_impact_score=71.3,
            impact_correlation_score=70.1,
            trend_label="Crescimento",
            narrative_label="Promissor",
            market_label="Percepcao moderada",
            narrative_summary="Boa leitura de mercado.",
            narrative_keywords=["promissor"],
            strategic_insights=["Aumentar validacao externa."],
        )
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Market Intelligence")
        self.assertContains(response, "68,5")
        self.assertContains(response, "Crescimento")
        self.assertContains(response, "0 fontes")

    def test_dashboard_shows_cached_ai_insight_when_available(self):
        user = User.objects.create(email="dash-ai@club.com", password_hash=make_password("secretpass"))
        player = Player.objects.create(
            user=user,
            name="Mateus AI",
            age=22,
            position="Meia",
            current_value=Decimal("1900000.00"),
            league_level="Serie B",
            club_origin="Goias",
        )
        PerformanceMetrics.objects.create(player=player)
        MarketMetrics.objects.create(player=player)
        MarketingMetrics.objects.create(player=player)
        BehaviorMetrics.objects.create(player=player)
        AthleteAIInsight.objects.create(
            player=player,
            scope="dashboard",
            window_days=90,
            language="pt",
            model_name="gpt-4.1-mini",
            status_label="Evolucao consistente",
            executive_summary="O atleta evoluiu com sustentacao de performance e potential.",
            main_change="Performance em crescimento.",
            main_risk="Mercado ainda abaixo do ritmo do campo.",
            main_opportunity="Posicionamento externo favoravel.",
            recommended_action="Consolidar narrativa competitiva.",
            confidence=86,
            dashboard_cards=[
                {"title": "Status", "value": "Forte", "commentary": "Momento favoravel."},
                {"title": "Mercado", "value": "Em resposta", "commentary": "Ha tracao inicial."},
                {"title": "Acao", "value": "Posicionar", "commentary": "Janela positiva."},
            ],
        )
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()

        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Leitura IA")
        self.assertContains(response, "Evolucao consistente")
        self.assertContains(response, "Consolidar narrativa competitiva.")

    @patch("valuation.views.generate_ai_dashboard_insight")
    def test_dashboard_can_trigger_ai_insight_generation(self, mocked_generate):
        user = User.objects.create(email="dash-ai-action@club.com", password_hash=make_password("secretpass"))
        player = Player.objects.create(
            user=user,
            name="Rafael IA",
            age=20,
            position="Ponta",
            current_value=Decimal("1600000.00"),
            league_level="Serie C",
            club_origin="Nautico",
        )
        PerformanceMetrics.objects.create(player=player)
        MarketMetrics.objects.create(player=player)
        MarketingMetrics.objects.create(player=player)
        BehaviorMetrics.objects.create(player=player)
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()

        response = self.client.post(
            reverse("player-ai-insight", args=[player.id]),
            {"compare_window": "90", "scope": "dashboard"},
        )

        self.assertRedirects(response, f"{reverse('dashboard')}?lang=pt&featured_player={player.id}&compare_window=90")
        mocked_generate.assert_called_once()

    @patch("valuation.views.generate_ai_dashboard_insight")
    def test_market_ai_trigger_redirects_back_to_market_module(self, mocked_generate):
        user = User.objects.create(email="market-ai-action@club.com", password_hash=make_password("secretpass"))
        player = Player.objects.create(
            user=user,
            name="Leo Market",
            age=21,
            position="Atacante",
            current_value=Decimal("1500000.00"),
            league_level="Serie B",
            club_origin="Ceara",
        )
        PerformanceMetrics.objects.create(player=player)
        MarketMetrics.objects.create(player=player)
        MarketingMetrics.objects.create(player=player)
        BehaviorMetrics.objects.create(player=player)
        session = self.client.session
        session["valuation_user_id"] = user.id
        session.save()

        response = self.client.post(
            reverse("player-ai-insight", args=[player.id]),
            {"compare_window": "90", "scope": "market"},
        )

        self.assertRedirects(response, f"{reverse('hbx-value-score')}?player={player.id}&lang=pt")
        mocked_generate.assert_called_once()


class CareerIntelligenceModuleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(email="career@club.com", password_hash=make_password("secretpass"))
        self.player = Player.objects.create(
            user=self.user,
            name="Bruno Alves",
            age=19,
            position="Atacante",
            current_value=Decimal("900000.00"),
            league_level="Brazil Serie B",
            club_origin="Avai",
        )
        PerformanceMetrics.objects.create(player=self.player)
        MarketMetrics.objects.create(player=self.player)
        MarketingMetrics.objects.create(player=self.player)
        BehaviorMetrics.objects.create(player=self.player)
        session = self.client.session
        session["valuation_user_id"] = self.user.id
        session.save()

    def test_can_create_case_and_advance_to_club_step(self):
        response = self.client.post(
            f"{reverse('career-case-create')}?lang=pt",
            {
                "player": self.player.id,
                "athlete_name": "Bruno Alves",
                "birth_date": "2007-03-14",
                "nationality": "Brasil",
                "position_primary": "Centroavante",
                "secondary_positions": ["Extremo direito"],
                "dominant_foot": "right",
                "height_cm": "182",
                "weight_kg": "75",
                "current_club": "Avai",
                "category": "professional",
                "contract_months_remaining": "18",
                "squad_status": "limited",
                "athlete_objectives": ["become_starter", "gain_minutes"],
                "analyst_notes": "Busca mais minutos.",
            },
        )
        case = CareerIntelligenceCase.objects.get(user=self.user)
        self.assertRedirects(response, f"{reverse('career-case-step', args=[case.id, 'club'])}?lang=pt")
        self.assertEqual(case.player, self.player)
        self.assertEqual(case.position_primary, "Centroavante")
        self.assertEqual(case.secondary_positions, ["Extremo direito"])

    def test_career_case_create_reuses_existing_integrated_case(self):
        integrated_case = CareerIntelligenceCase.objects.create(
            user=self.user,
            player=self.player,
            athlete_name=self.player.name,
            position_primary=self.player.position,
            current_club=self.player.club_origin,
        )
        response = self.client.post(
            f"{reverse('career-case-create')}?lang=pt",
            {
                "player": self.player.id,
                "athlete_name": "Bruno Alves",
                "birth_date": "2007-03-14",
                "nationality": "Brasil",
                "position_primary": "Centroavante",
                "secondary_positions": "Extremo direito",
                "dominant_foot": "right",
                "height_cm": "182",
                "weight_kg": "75",
                "current_club": "Avai",
                "category": "professional",
                "contract_months_remaining": "18",
                "squad_status": "limited",
                "athlete_objectives": "become_starter",
                "analyst_notes": "Busca mais minutos.",
            },
        )
        self.assertEqual(CareerIntelligenceCase.objects.filter(user=self.user, player=self.player).count(), 1)
        integrated_case.refresh_from_db()
        self.assertRedirects(response, f"{reverse('career-case-step', args=[integrated_case.id, 'club'])}?lang=pt")
        self.assertEqual(integrated_case.position_primary, "Centroavante")

    def test_career_list_supports_english_language(self):
        CareerIntelligenceCase.objects.create(
            user=self.user,
            athlete_name="Bruno Alves",
            position_primary="Centroavante",
            current_club="Avai",
        )
        response = self.client.get(f"{reverse('career-case-list')}?lang=en")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Performance Intelligence")
        self.assertContains(response, "Cases in progress")

    def test_career_list_shows_consolidated_performance_payload_for_selected_athlete(self):
        CareerIntelligenceCase.objects.create(
            user=self.user,
            player=self.player,
            athlete_name="Bruno Alves",
            position_primary="Atacante",
            current_club="Avai",
        )
        response = self.client.get(f"{reverse('career-case-list')}?lang=pt&athlete={self.player.id}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Executive Performance View")
        self.assertContains(response, "Athlete360 performance summary")
        self.assertContains(response, "Integrated status")

    def test_completion_requires_core_sections(self):
        case = CareerIntelligenceCase.objects.create(
            user=self.user,
            player=self.player,
            athlete_name="Bruno Alves",
            position_primary="Atacante",
            current_club="Avai",
        )
        ClubCompetitiveContext.objects.create(
            case=case,
            club_name="Avai",
            competition="Serie B",
            team_moment="development",
            pressure_level="medium",
            club_philosophy="mixed",
        )
        CoachProfile.objects.create(
            case=case,
            coach_name="Tecnico A",
            profile_type="developer",
            experience_preference="balanced",
            physical_demand="medium",
            tactical_demand="medium",
        )
        CompetitiveDiagnosis.objects.create(case=case, main_reason="technical_gap")
        CareerPrognosis.objects.create(case=case, classification="moderate", timeframe="medium", justification="Precisa desenvolver repertorio.")
        IndividualDevelopmentPlan.objects.create(case=case, priority_actions=["Acao 1", "Acao 2", "Acao 3"])
        completion = case_completion(case)
        self.assertTrue(completion["athlete"])
        self.assertTrue(completion["club"])
        self.assertTrue(completion["coach"])
        self.assertTrue(completion["diagnosis"])
        self.assertTrue(completion["prognosis"])
        self.assertTrue(completion["development"])
        self.assertFalse(completion["report"])

    def test_case_report_pdf_is_available(self):
        case = CareerIntelligenceCase.objects.create(
            user=self.user,
            athlete_name="Bruno Alves",
            position_primary="Atacante",
            current_club="Avai",
        )
        response = self.client.get(reverse("career-case-report-pdf", args=[case.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

    @patch("valuation.career_views.generate_ai_development_plan")
    def test_can_generate_ai_plan_suggestion(self, mocked_generate):
        mocked_generate.return_value = {
            "strengths_to_keep": "Atacar profundidade com regularidade.",
            "short_term_priorities": "Melhorar tomada de decisao no ultimo terco.",
            "medium_term_development": "Ganhar repertorio associativo.",
            "contextual_factors": "Concorrencia alta no setor ofensivo.",
            "mental_strategy": "Sustentar confianca e resposta apos erro.",
            "practical_strategy": "Treino complementar de finalizacao e pressao.",
            "priority_actions": ["Acao 1", "Acao 2", "Acao 3"],
            "template_name": "Sugestao IA",
        }
        case = CareerIntelligenceCase.objects.create(
            user=self.user,
            player=self.player,
            athlete_name="Bruno Alves",
            position_primary="Centroavante",
            current_club="Avai",
        )
        response = self.client.post(
            f"{reverse('career-case-step', args=[case.id, 'development'])}?lang=pt",
            {"action": "generate_ai_plan"},
        )
        self.assertEqual(response.status_code, 200)
        plan = IndividualDevelopmentPlan.objects.get(case=case)
        self.assertEqual(plan.template_name, "Sugestao IA")
        self.assertEqual(plan.priority_actions, ["Acao 1", "Acao 2", "Acao 3"])
        self.assertContains(response, "Sugestao de plano gerada pela IA")
