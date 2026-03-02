import json
from datetime import date, time

from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from front.models import ActivityLog, Adresse, Commercial, CommentaireRdv, FrontClient, Rendezvous


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
        self.other_commercial = Commercial.objects.create(
            commercial="Commercial 3",
            nom="Martin",
            prenom="Eve",
            email="eve@example.com",
            telephone="0600000000",
            password=make_password("secret123"),
            role="commercial",
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


class SecurityHeadersTests(BaseSecurityFlowTestCase):
    def _assert_security_headers(self, response):
        self.assertEqual(response.get("X-Frame-Options"), "SAMEORIGIN")
        self.assertEqual(response.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.get("Referrer-Policy"), "strict-origin-when-cross-origin")
        self.assertEqual(response.get("Cross-Origin-Opener-Policy"), "same-origin")
        self.assertEqual(response.get("Cross-Origin-Embedder-Policy"), "unsafe-none")

    def test_security_headers_login(self):
        resp = self.client.get(reverse("login"))
        self.assertEqual(resp.status_code, 200)
        self._assert_security_headers(resp)

    def test_security_headers_reset_password(self):
        resp = self.client.get(reverse("reset_password"))
        self.assertEqual(resp.status_code, 200)
        self._assert_security_headers(resp)

    def test_security_headers_dashboard(self):
        self.login_as(self.commercial)
        resp = self.client.get(reverse("dashboard_test"))
        self.assertEqual(resp.status_code, 200)
        self._assert_security_headers(resp)


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

    def test_add_rdv_dry_run_ok_does_not_persist(self):
        self.login_as(self.commercial)
        before_count = Rendezvous.objects.count()
        resp = self.client.post(
            reverse("add_rdv"),
            {
                "client_id": self.client_obj.id,
                "date_rdv": "2026-03-01",
                "heure_rdv": "09:40",
                "objet": "Prospection",
                "notes": "Simulation",
                "dry_run": "1",
            },
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload.get("ok"))
        self.assertTrue(payload.get("dry_run"))
        self.assertEqual(payload.get("would_create", {}).get("statut_rdv"), "a_venir")
        self.assertEqual(Rendezvous.objects.count(), before_count)

    def test_add_rdv_dry_run_duplicate_returns_409(self):
        self.login_as(self.commercial)
        Rendezvous.objects.create(
            client=self.client_obj,
            commercial=self.commercial,
            date_rdv=date(2026, 3, 2),
            heure_rdv=time(10, 0),
            statut_rdv="a_venir",
            rs_nom=self.client_obj.rs_nom,
        )
        before_count = Rendezvous.objects.count()
        resp = self.client.post(
            reverse("add_rdv"),
            {
                "client_id": self.client_obj.id,
                "date_rdv": "2026-03-02",
                "heure_rdv": "10:00",
                "dry_run": "true",
            },
        )
        self.assertEqual(resp.status_code, 409)
        payload = resp.json()
        self.assertFalse(payload.get("ok"))
        self.assertTrue(payload.get("dry_run"))
        self.assertEqual(payload.get("error"), "duplicate_rdv")
        self.assertEqual(Rendezvous.objects.count(), before_count)


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

    def test_update_statut_rate_limited(self):
        self.login_as(self.commercial)
        rdv = Rendezvous.objects.create(
            client=self.client_obj,
            commercial=self.commercial,
            date_rdv=date(2026, 2, 22),
            heure_rdv=time(9, 0),
            statut_rdv="a_venir",
            rs_nom=self.client_obj.rs_nom,
        )
        cache.set(f"rl:update_statut:127.0.0.1:{self.commercial.id}", 120, timeout=60)
        resp = self.client.post(
            reverse("update_statut", kwargs={"uuid": rdv.uuid, "statut": "valider"}),
            data=json.dumps({"commentaire": "OK", "is_pinned": False}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(resp.json().get("code"), "RATE_LIMITED")

    def test_update_client_ok(self):
        self.login_as(self.commercial)
        resp = self.client.post(
            reverse("update_client_uuid", kwargs={"client_uuid": self.client_obj.uuid}),
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

    def test_update_client_rate_limited(self):
        self.login_as(self.commercial)
        cache.set(f"rl:update_client:127.0.0.1:{self.commercial.id}", 90, timeout=60)
        resp = self.client.post(
            reverse("update_client_uuid", kwargs={"client_uuid": self.client_obj.uuid}),
            data=json.dumps({"telephone": "0555112233"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(resp.json().get("code"), "RATE_LIMITED")


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
        self.assertIn("uuid", data["clients"][0])
        self.assertIn("client_uuid", data["tournee"][0])

    def test_routing_provider_status_endpoint_payload(self):
        self.login_as(self.commercial)
        resp = self.client.get(reverse("api_routing_provider_status"))
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload.get("ok"))
        self.assertIn(payload.get("provider_precedence"), ["GOOGLE_THEN_HAVERSINE", "HAVERSINE_ONLY"])
        self.assertIn("google_key_configured", payload)
        self.assertIn("google_travel_mode", payload)

    def test_api_route_optimisee_exposes_mode(self):
        self.login_as(self.commercial)
        Rendezvous.objects.create(
            client=self.client_obj,
            commercial=self.commercial,
            date_rdv=date(2026, 2, 23),
            heure_rdv=time(10, 30),
            statut_rdv="a_venir",
            rs_nom=self.client_obj.rs_nom,
        )
        resp = self.client.get(reverse("api_route_optimisee", kwargs={"date": "2026-02-23"}))
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload.get("success"))
        self.assertIn(payload.get("mode"), ["GOOGLE", "HAVERSINE"])

    def test_rdvs_by_date_payload_contains_client_uuid(self):
        self.login_as(self.commercial)
        Rendezvous.objects.create(
            client=self.client_obj,
            commercial=self.commercial,
            date_rdv=date(2026, 2, 24),
            heure_rdv=time(10, 45),
            statut_rdv="a_venir",
            rs_nom=self.client_obj.rs_nom,
        )
        resp = self.client.get(reverse("api_rdvs_by_date"), {"date": "2026-02-24", "statut": "a_venir"})
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertGreaterEqual(len(payload.get("rdvs", [])), 1)
        self.assertEqual(payload["rdvs"][0]["client"]["uuid"], str(self.client_obj.uuid))

    def test_replace_tournee_rate_limited(self):
        self.login_as(self.commercial)
        cache.set(f"rl:replace_tournee:127.0.0.1:{self.commercial.id}", 30, timeout=60)
        resp = self.client.post(
            reverse("api_replace_tournee"),
            data=json.dumps(
                {"commercial_id": self.commercial.id, "date": "2026-02-23", "client_ids": [self.client_obj.id]}
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(resp.json().get("code"), "RATE_LIMITED")

    def test_api_client_details_uuid_forbidden_for_other_commercial(self):
        self.login_as(self.other_commercial)
        resp = self.client.get(reverse("api_client_details_uuid", kwargs={"client_uuid": self.client_obj.uuid}))
        self.assertEqual(resp.status_code, 403)

    def test_toggle_pin_comment_forbidden_for_other_commercial(self):
        rdv = Rendezvous.objects.create(
            client=self.client_obj,
            commercial=self.commercial,
            date_rdv=date(2026, 2, 25),
            heure_rdv=time(9, 15),
            statut_rdv="a_venir",
            rs_nom=self.client_obj.rs_nom,
        )
        comment = CommentaireRdv.objects.create(
            rdv=rdv,
            commercial=self.commercial,
            texte="Commentaire test",
            rs_nom=self.client_obj.rs_nom,
            is_pinned=False,
        )

        self.login_as(self.other_commercial)
        resp = self.client.post(reverse("toggle_pin_comment", kwargs={"comment_id": comment.id}))
        self.assertEqual(resp.status_code, 403)

        self.login_as(self.responsable)
        resp_admin = self.client.post(reverse("toggle_pin_comment", kwargs={"comment_id": comment.id}))
        self.assertEqual(resp_admin.status_code, 200)
        self.assertTrue(resp_admin.json().get("ok"))

    def test_toggle_pin_comment_rate_limited(self):
        rdv = Rendezvous.objects.create(
            client=self.client_obj,
            commercial=self.commercial,
            date_rdv=date(2026, 2, 25),
            heure_rdv=time(9, 15),
            statut_rdv="a_venir",
            rs_nom=self.client_obj.rs_nom,
        )
        comment = CommentaireRdv.objects.create(
            rdv=rdv,
            commercial=self.commercial,
            texte="Commentaire test",
            rs_nom=self.client_obj.rs_nom,
            is_pinned=False,
        )
        self.login_as(self.commercial)
        cache.set(f"rl:toggle_pin_comment:127.0.0.1:{self.commercial.id}", 120, timeout=60)
        resp = self.client.post(reverse("toggle_pin_comment", kwargs={"comment_id": comment.id}))
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(resp.json().get("code"), "RATE_LIMITED")

    def test_api_client_comments_forbidden_for_other_commercial(self):
        rdv = Rendezvous.objects.create(
            client=self.client_obj,
            commercial=self.commercial,
            date_rdv=date(2026, 2, 26),
            heure_rdv=time(9, 45),
            statut_rdv="a_venir",
            rs_nom=self.client_obj.rs_nom,
        )
        CommentaireRdv.objects.create(
            rdv=rdv,
            commercial=self.commercial,
            texte="Commentaire privé",
            rs_nom=self.client_obj.rs_nom,
            is_pinned=True,
        )

        self.login_as(self.other_commercial)
        resp = self.client.get(reverse("get_client_comments_uuid", kwargs={"client_uuid": self.client_obj.uuid}))
        self.assertEqual(resp.status_code, 403)

        self.login_as(self.responsable)
        resp_ok = self.client.get(reverse("get_client_comments_uuid", kwargs={"client_uuid": self.client_obj.uuid}))
        self.assertEqual(resp_ok.status_code, 200)
        self.assertIn("commentaires", resp_ok.json())

    def test_api_client_comments_rate_limited(self):
        self.login_as(self.commercial)
        cache.set(f"rl:client_comments:127.0.0.1:{self.commercial.id}", 300, timeout=60)
        resp = self.client.get(reverse("get_client_comments_uuid", kwargs={"client_uuid": self.client_obj.uuid}))
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(resp.json().get("code"), "RATE_LIMITED")

    def test_api_client_comments_uuid_forbidden_for_other_commercial(self):
        self.login_as(self.other_commercial)
        resp = self.client.get(reverse("get_client_comments_uuid", kwargs={"client_uuid": self.client_obj.uuid}))
        self.assertEqual(resp.status_code, 403)

    def test_get_client_rdv_uuid_forbidden_for_other_commercial(self):
        self.login_as(self.other_commercial)
        resp = self.client.get(reverse("get_client_rdv_uuid", kwargs={"client_uuid": self.client_obj.uuid}))
        self.assertEqual(resp.status_code, 403)

    def test_get_last_rdv_commercial_forbidden_for_other_commercial(self):
        self.login_as(self.other_commercial)
        resp = self.client.get(reverse("get_last_rdv_commercial", kwargs={"commercial_id": self.commercial.id}))
        self.assertEqual(resp.status_code, 403)

    def test_set_comment_pin_forbidden_for_other_commercial(self):
        rdv = Rendezvous.objects.create(
            client=self.client_obj,
            commercial=self.commercial,
            date_rdv=date(2026, 2, 27),
            heure_rdv=time(11, 0),
            statut_rdv="a_venir",
            rs_nom=self.client_obj.rs_nom,
        )
        comment = CommentaireRdv.objects.create(
            rdv=rdv,
            commercial=self.commercial,
            texte="Commentaire privé",
            rs_nom=self.client_obj.rs_nom,
            is_pinned=False,
        )
        self.login_as(self.other_commercial)
        resp = self.client.post(
            reverse("set_comment_pin", kwargs={"comment_id": comment.id}),
            data=json.dumps({"is_pinned": True}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_update_client_uuid_ok(self):
        self.login_as(self.commercial)
        resp = self.client.post(
            reverse("update_client_uuid", kwargs={"client_uuid": self.client_obj.uuid}),
            data=json.dumps({"telephone": "0555998877"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.telephone, "0555998877")
