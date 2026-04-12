import json
from datetime import date
from datetime import datetime
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.hashers import check_password, make_password
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from valuation.models import (
    AnalystNote,
    BehaviorMetrics,
    DevelopmentPlan,
    LiveAnalysisEvent,
    LiveAnalysisSession,
    LivePlayerEvaluation,
    MarketMetrics,
    MarketingMetrics,
    OnBallEvent,
    PerformanceMetrics,
    Player,
    PlayerHistory,
    ProgressTracking,
    User,
)
from valuation.services import (
    build_growth_insights,
    build_projection_scenarios,
    calculate_growth_rate,
    calculate_scores,
    import_players_from_csv,
    live_analysis_summary,
    on_ball_decision_analysis,
    save_manual_history_snapshot,
    save_on_ball_event,
    save_player_history_snapshot,
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


class ValuationViewsTests(TestCase):
    def test_signup_and_redirect(self):
        response = self.client.post(
            reverse("signup"),
            {"email": "agent@club.com", "password": "secretpass", "confirm_password": "secretpass"},
        )
        self.assertRedirects(response, reverse("dashboard"))

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, reverse("login"))

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
        self.assertRedirects(response, f"{reverse('dashboard')}?lang=pt")
        self.assertTrue(PlayerHistory.objects.filter(player=player, date="2026-03-01").exists())

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
        self.assertContains(response, "Registro de desempenho individual em jogo")
