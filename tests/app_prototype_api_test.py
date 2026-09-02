import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from server.app.identity.prototype import PrototypeIdentityApplication
from server.app.main import create_app
from server.app.platform.config import AppSettings
from server.app.platform.health import ReadinessRegistry


class MemoryPrototypeIdentityRepository:
    def __init__(self):
        self.users = set()
        self.sessions = {}

    def create_prototype_user(self, *, user_id, now):
        self.users.add(user_id)

    def insert_prototype_session(self, session, *, now):
        self.sessions[session.id] = session

    def get_prototype_session_by_token_hash(self, *, token_sha256, for_update=False):
        return next((item for item in self.sessions.values() if item.token_sha256 == token_sha256), None)

    def get_prototype_session(self, *, session_id, for_update=False):
        return self.sessions.get(session_id)

    def save_prototype_session(self, session, *, now):
        self.sessions[session.id] = session


class PrototypeApiTest(unittest.TestCase):
    def setUp(self):
        self.repository = MemoryPrototypeIdentityRepository()
        self.application = PrototypeIdentityApplication(
            repository=self.repository,
            ttl=__import__("datetime").timedelta(hours=1),
            clock=lambda: datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
        )
        settings = AppSettings(
            environment="test",
            database_url="postgresql://redacted",
            prototype_enabled=True,
        )
        self.client = TestClient(
            create_app(
                settings=settings,
                readiness_registry=ReadinessRegistry({}),
                web_auth_application=object(),
                prototype_identity_application=self.application,
            )
        )

    def test_create_session_is_available_without_formal_web_cookie(self):
        response = self.client.post("/api/v2/prototype/sessions")

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["mode"], "prototype")
        self.assertTrue(payload["sessionToken"])
        self.assertNotIn("userId", payload)
        self.assertNotIn("user_id", payload)
        self.assertNotIn("Cookie", response.request.headers)

    def test_revoke_requires_prototype_capability_and_invalidates_it(self):
        created = self.client.post("/api/v2/prototype/sessions").json()
        token = created["sessionToken"]

        revoked = self.client.post(
            "/api/v2/prototype/sessions/revoke",
            headers={"X-Prototype-Session": token},
        )
        self.assertEqual(revoked.status_code, 200)
        self.assertEqual(revoked.json()["revoked"], True)

        replay = self.client.post(
            "/api/v2/prototype/sessions/revoke",
            headers={"X-Prototype-Session": token},
        )
        self.assertEqual(replay.status_code, 401)
        self.assertEqual(replay.json()["error"]["code"], "PROTOTYPE_SESSION_REQUIRED")

    def test_missing_capability_is_rejected_without_formal_auth_fallback(self):
        response = self.client.post("/api/v2/prototype/sessions/revoke")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "PROTOTYPE_SESSION_REQUIRED")

    def test_disabled_prototype_returns_explicit_unavailable_state(self):
        settings = AppSettings(
            environment="test",
            database_url="postgresql://redacted",
            prototype_enabled=False,
        )
        client = TestClient(
            create_app(
                settings=settings,
                readiness_registry=ReadinessRegistry({}),
                web_auth_application=object(),
                prototype_identity_application=self.application,
            )
        )

        response = client.post("/api/v2/prototype/sessions")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "PROTOTYPE_DISABLED")

    def test_simulation_routes_are_registered(self):
        paths = set(self.client.app.openapi()["paths"])

        self.assertIn("/api/v2/prototype/source-snapshots", paths)
        self.assertIn("/api/v2/prototype/simulations", paths)
        self.assertIn("/api/v2/prototype/simulations/{job_id}", paths)


if __name__ == "__main__":
    unittest.main()
