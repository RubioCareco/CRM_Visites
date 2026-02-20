import json
from datetime import date, time

from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from front.models import ActivityLog, Adresse, Commercial, FrontClient, Rendezvous


class BaseSecurityFlowTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.commercial = Commercial.objects.create(
            commercial="Commercial 2",
            nom="Durand",
            prenom="Alice",
            email="alice@example.com",
            telephone="0102030405",
            password=make_password("secret123"),
            role="commercial",
        )
        self.responsable = Commercial.objects.create(
            commercial="Responsable Commercial",
            nom="Boss",
            prenom="Bob",
            email="bob@example.com",
            telephone="0605040302",
            password=make_password("secret123"),
            role="responsable",
        )
        self.client_obj = FrontClient.objects.create(
            rs_nom="CLIENT TEST",
            commercial_id=self.commercial.id,
            commercial=self.commercial.commercial,
            actif=True,
            email="client@example.com",
            telephone="0555000000",
        )
        Adresse.objects.create(
            client=self.client_obj,
            adresse="1 RUE TEST",
            code_postal="33000",
            ville="Bordeaux",
            latitude=44.8378,
            longitude=-0.5792,
        )

    def login_as(self, commercial):
        session = self.client.session
        session["commercial_id"] = commercial.id
        session["commercial_nom"] = commercial.commercial
        session["role"] = commercial.role
        session.save()


class AuthAndPermissionsTests(BaseSecurityFlowTestCase):
    def test_login_logout_flow(self):
        resp = self.client.post(reverse("login"), {"email": "alice@example.com", "password": "secret123"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/dashboard-test/", resp.url)

        resp_logout = self.client.get(reverse("logout"))
        self.assertEqual(resp_logout.status_code, 302)
        self.assertIn("/", resp_logout.url)

    def test_dashboard_permissions(self):
        self.login_as(self.commercial)
        self.assertEqual(self.client.get(reverse("dashboard_test")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard_responsable")).status_code, 403)

        self.login_as(self.responsable)
        self.assertEqual(self.client.get(reverse("dashboard_responsable")).status_code, 200)


class AddRdvTests(BaseSecurityFlowTestCase):
    def test_add_rdv_missing_required_fields(self):
        self.login_as(self.commercial)
        resp = self.client.post(reverse("add_rdv"), {"client_id": self.client_obj.id, "date_rdv": "", "heure_rdv": ""})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Veuillez renseigner date, heure et client.")

    def test_add_rdv_duplicate(self):
        self.login_as(self.commercial)
        Rendezvous.objects.create(
            client=self.client_obj,
            commercial=self.commercial,
            date_rdv=date(2026, 2, 20),
            heure_rdv=time(10, 0),
            statut_rdv="a_venir",
            rs_nom=self.client_obj.rs_nom,
        )
        resp = self.client.post(
            reverse("add_rdv"),
            {"client_id": self.client_obj.id, "date_rdv": "2026-02-20", "heure_rdv": "10:00"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Un rendez-vous existe déjà pour ce client à cette date et heure.")

    def test_add_rdv_success_creates_log_with_actor_context(self):
        self.login_as(self.commercial)
        resp = self.client.post(
            reverse("add_rdv"),
            {"client_id": self.client_obj.id, "date_rdv": "2026-02-21", "heure_rdv": "11:30", "objet": "Test"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Rendezvous.objects.filter(client=self.client_obj, date_rdv=date(2026, 2, 21)).exists())

        log = ActivityLog.objects.filter(action_type="RDV_AJOUTE").latest("timestamp")
        self.assertEqual(log.commercial_id, self.commercial.id)
        self.assertEqual(log.actor_commercial_id, self.commercial.id)
        self.assertEqual(log.actor_role, "commercial")
        self.assertEqual(log.request_path, reverse("add_rdv"))
        self.assertEqual(log.request_method, "POST")

    def test_add_rdv_by_responsable_tracks_actor_and_target(self):
        self.login_as(self.responsable)
        resp = self.client.post(
            reverse("add_rdv"),
            {
                "commercial_id": self.commercial.id,
                "client_id": self.client_obj.id,
                "date_rdv": "2026-02-24",
                "heure_rdv": "14:10",
            },
        )
        self.assertEqual(resp.status_code, 302)
        log = ActivityLog.objects.filter(action_type="RDV_AJOUTE").latest("timestamp")
        self.assertEqual(log.commercial_id, self.commercial.id)
        self.assertEqual(log.actor_commercial_id, self.responsable.id)
        self.assertEqual(log.actor_role, "responsable")


class UpdateStatutAndClientFileTests(BaseSecurityFlowTestCase):
    def test_update_statut_ok(self):
        self.login_as(self.commercial)
        rdv = Rendezvous.objects.create(
            client=self.client_obj,
            commercial=self.commercial,
            date_rdv=date(2026, 2, 22),
            heure_rdv=time(9, 0),
            statut_rdv="a_venir",
            rs_nom=self.client_obj.rs_nom,
        )
        resp = self.client.post(
            reverse("update_statut", kwargs={"uuid": rdv.uuid, "statut": "valider"}),
            data=json.dumps({"commentaire": "OK", "is_pinned": False}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        rdv.refresh_from_db()
        self.assertEqual(rdv.statut_rdv, "valide")
        self.assertTrue(ActivityLog.objects.filter(action_type="RDV_VALIDE", commercial=self.commercial).exists())

    def test_update_client_ok(self):
        self.login_as(self.commercial)
        resp = self.client.post(
            reverse("update_client", kwargs={"client_id": self.client_obj.id}),
            data=json.dumps(
                {
                    "telephone": "0555112233",
                    "email": "updated@example.com",
                    "classement_client": "B",
                    "adresse": "2 RUE UPDATE",
                    "code_postal": "33100",
                    "ville": "Bordeaux",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.telephone, "0555112233")
        self.assertEqual(self.client_obj.email, "updated@example.com")


class ResetPasswordAndMapTests(BaseSecurityFlowTestCase):
    def test_reset_password_neutral_message_and_throttling(self):
        headers = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
        first = self.client.post(reverse("reset_password"), {"email": "unknown@example.com"}, **headers)
        self.assertEqual(first.status_code, 200)
        payload = first.json()
        self.assertTrue(payload.get("success"))
        self.assertIn("Si l'adresse existe", payload.get("message", ""))

        # 6 requêtes d'affilée depuis la même IP -> throttled à la 6e
        for _ in range(4):
            self.client.post(reverse("reset_password"), {"email": "unknown@example.com"}, **headers)
        limited = self.client.post(reverse("reset_password"), {"email": "unknown@example.com"}, **headers)
        self.assertEqual(limited.status_code, 429)
        self.assertFalse(limited.json().get("success"))

    def test_map_tournee_endpoint_access_and_payload(self):
        self.login_as(self.commercial)
        Rendezvous.objects.create(
            client=self.client_obj,
            commercial=self.commercial,
            date_rdv=date(2026, 2, 23),
            heure_rdv=time(10, 30),
            statut_rdv="a_venir",
            rs_nom=self.client_obj.rs_nom,
        )
        resp = self.client.get(reverse("api_map_tournee"), {"date": "2026-02-23"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("clients", data)
        self.assertIn("tournee", data)
        self.assertEqual(data["date"], "2026-02-23")
        self.assertGreaterEqual(len(data["tournee"]), 1)
