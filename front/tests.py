from django.test import TestCase
from django.utils import timezone
from datetime import date
from front.models import Commercial, FrontClient, Adresse, Rendezvous
from front.services import ensure_visits_next_4_weeks, RouteOptimizationService


class PlanningTests(TestCase):
    def setUp(self):
        self.com = Commercial.objects.create(
            commercial="Commercial 2",
            nom="Test",
            prenom="Nelson",
            email="t@example.com",
            telephone="000",
            password="x",
            latitude_depart=44.8378,
            longitude_depart=-0.5792,
            adresse_depart="BORDEAUX",
        )

        # Crée 8 clients: 6 proches, 2 éloignés
        coords_close = [
            (44.85, -0.57), (44.86, -0.56), (44.84, -0.58),
            (44.83, -0.57), (44.855, -0.565), (44.845, -0.59)
        ]
        coords_far = [(44.5, -0.3), (44.3, -0.2)]

        self.clients = []
        for i, (lat, lon) in enumerate(coords_close + coords_far, 1):
            fc = FrontClient.objects.create(
                rs_nom=f"C{i}",
                actif=True,
                commercial_id=self.com.id,
                classement_client='C',
            )
            Adresse.objects.create(client=fc, adresse=f"A{i}", code_postal="33000", ville="Bordeaux", latitude=lat, longitude=lon)
            self.clients.append(fc)

    def test_generation_respects_cap_and_objectives(self):
        today = timezone.localdate()
        res = ensure_visits_next_4_weeks(run_date=today, dry_run=False, collect_breakdown=False)
        # Au plus 7 RDV pour aujourd'hui pour ce commercial
        count = Rendezvous.objects.filter(commercial=self.com, date_rdv=today, statut_rdv='a_venir').count()
        self.assertLessEqual(count, 7)

    def test_order_is_optimized(self):
        today = timezone.localdate()
        ensure_visits_next_4_weeks(run_date=today, dry_run=False, collect_breakdown=False)
        data = RouteOptimizationService.get_optimized_route_for_commercial(self.com, today.isoformat())
        rdvs = data.get('rdvs', [])
        # On doit avoir au moins 3 RDV et un mode renseigné
        self.assertGreaterEqual(len(rdvs), 3)
        self.assertIn(data.get('mode'), ['HAVERSINE', 'GOOGLE'])



#other tests
# --- tests pour la commande show_route ---

from io import StringIO
import pytest
from django.core.management import call_command
from front.models import Commercial, Rendezvous

@pytest.fixture(autouse=True)
def disable_external_routing(settings):
    # Coupe Google pendant les tests (zéro appel réseau externe)
    settings.GOOGLE_MAPS_API_KEY = ""

@pytest.mark.django_db
def test_show_route_does_not_create_when_no_rdvs():
    # Arrange: un commercial sans RDV à la date
    Commercial.objects.create(commercial="Commercial 2")
    before = Rendezvous.objects.count()

    # Act
    out = StringIO()
    call_command("show_route", commercial="Commercial 2", date="2025-09-19", stdout=out)
    output = out.getvalue()

    # Assert
    assert "Aucun RDV" in output
    assert Rendezvous.objects.count() == before

@pytest.mark.django_db
def test_show_route_runs_without_side_effects_with_stub(monkeypatch):
    # Arrange
    Commercial.objects.create(commercial="Commercial 2")

    # On “stub” l’optimisation pour ne pas créer de vrais objets
    from front.services import RouteOptimizationService
    monkeypatch.setattr(
        RouteOptimizationService,
        "get_optimized_route_for_commercial",
        lambda commercial, date_iso: {
            "rdvs": [], "route_details": [],
            "total_distance": 0, "estimated_time_minutes": 0, "mode": "HAVERSINE"
        }
    )
    before = Rendezvous.objects.count()

    # Act
    out = StringIO()
    call_command("show_route", commercial="Commercial 2", date="2025-09-19", stdout=out)

    # Assert
    assert Rendezvous.objects.count() == before
