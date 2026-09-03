from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
import unittest

from fastapi.testclient import TestClient

from server.app.identity.application import WebAuthApplication
from server.app.identity.domain import (
    Principal,
    WebLoginSessionStatus,
    cancel_web_login_session,
    confirm_web_login_session,
    consume_web_login_session,
)
from server.app.identity.ports import PublicUser, WechatIdentity
from server.app.main import create_app
from server.app.platform.config import AppSettings
from server.app.platform.health import ComponentState, ReadinessRegistry


NOW = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
PNG = b"\x89PNG\r\n\x1a\nreal"
JPEG = b"\xff\xd8\xffreal"


class FakeIdentityRepository:
    def __init__(self):
        self.sessions = {}
        self.auth_sessions = {}
        self.users = {}
        self.openids = {}

    def upsert_wechat_mini_identity(self, *, app_context, provider_subject, union_id, now):
        identity_key = (app_context, provider_subject)
        if identity_key not in self.openids:
            user_id = uuid4()
            self.openids[identity_key] = user_id
            self.users[user_id] = PublicUser(user_id=user_id, display_name="")
        return self.openids[identity_key]

    def issue_auth_session(self, *, token_hash, user_id, kind, expires_at):
        self.auth_sessions[token_hash] = (user_id, kind, expires_at)

    def resolve_auth_session(self, *, token_hash, kind, now):
        record = self.auth_sessions.get(token_hash)
        if record is None or record[1] != kind or record[2] <= now:
            return None
        return Principal(user_id=record[0], session_kind=kind)

    def revoke_auth_session(self, *, token_hash, kind, now):
        self.auth_sessions.pop(token_hash, None)

    def insert_web_login_session(self, session, *, now):
        self.sessions[session.id] = session
        return True

    def confirm_web_login_session(self, *, scene_ticket_sha256, user_id, now):
        session = next(
            (candidate for candidate in self.sessions.values() if candidate.scene_ticket_sha256 == scene_ticket_sha256),
            None,
        )
        if session is None:
            return False
        try:
            confirmed = confirm_web_login_session(
                session,
                scene_ticket_sha256=scene_ticket_sha256,
                user_id=user_id,
                now=now,
            )
        except ValueError:
            return False
        self.sessions[session.id] = confirmed
        return True

    def cancel_web_login_session(self, *, session_id, browser_verifier_sha256, now):
        session = self.sessions.get(session_id)
        if session is None or session.browser_verifier_sha256 != browser_verifier_sha256:
            return False
        try:
            cancelled = cancel_web_login_session(session, now=now)
        except ValueError:
            return False
        if cancelled.status is WebLoginSessionStatus.EXPIRED:
            return False
        self.sessions[session.id] = cancelled
        return True

    def expire_web_login_session(self, *, session_id, now):
        session = self.sessions.get(session_id)
        if (
            session is None
            or session.status not in {WebLoginSessionStatus.PENDING, WebLoginSessionStatus.CONFIRMED}
            or now < session.expires_at
        ):
            return False
        self.sessions[session.id] = replace(session, status=WebLoginSessionStatus.EXPIRED)
        return True

    def consume_web_login_session_and_issue_auth_session(
        self,
        *,
        session_id,
        browser_verifier_sha256,
        expected_user_id,
        token_hash,
        now,
        expires_at,
    ):
        session = self.sessions.get(session_id)
        if session is None or session.user_id != expected_user_id:
            return None
        try:
            consumed = consume_web_login_session(
                session,
                verifier_sha256=browser_verifier_sha256,
                now=now,
            )
        except ValueError:
            return None
        self.sessions[session.id] = consumed
        self.issue_auth_session(
            token_hash=token_hash,
            user_id=expected_user_id,
            kind="web_cookie",
            expires_at=expires_at,
        )
        return expected_user_id

    def get_web_login_session(self, *, session_id):
        return self.sessions.get(session_id)

    def get_web_login_session_by_scene(self, *, scene_ticket_sha256):
        return next(
            (session for session in self.sessions.values() if session.scene_ticket_sha256 == scene_ticket_sha256),
            None,
        )

    def get_web_login_session_by_idempotency(self, *, browser_verifier_sha256, idempotency_key_sha256):
        return next(
            (
                session for session in self.sessions.values()
                if session.browser_verifier_sha256 == browser_verifier_sha256
                and session.idempotency_key_sha256 == idempotency_key_sha256
            ),
            None,
        )

    def get_public_user(self, user_id):
        return self.users.get(user_id)


class FakeWechatGateway:
    def __init__(self, *, configured=True):
        self.configured = configured
        self.codes = []

    def exchange_code(self, code):
        if not self.configured:
            from server.app.integrations.wechat_mini import WechatNotConfiguredError
            raise WechatNotConfiguredError("not configured")
        return WechatIdentity(openid=f"openid-for-{code}")

    def create_mini_code(self, *, scene, page, env_version):
        if not self.configured:
            from server.app.integrations.wechat_mini import WechatNotConfiguredError
            raise WechatNotConfiguredError("not configured")
        self.codes.append((scene, page, env_version))
        return PNG


class FakeJpegWechatGateway(FakeWechatGateway):
    def create_mini_code(self, *, scene, page, env_version):
        self.codes.append((scene, page, env_version))
        return JPEG


def settings():
    return AppSettings(
        environment="test",
        database_url="postgresql://redacted",
        web_origin="https://testserver",
        web_cookie_name="__Host-wow_v2",
        web_login_ttl_seconds=300,
        web_session_ttl_seconds=3600,
        wechat_appid="wx-test",
        wechat_secret="secret-not-for-output",
        wechat_page="pages/auth/web-login-confirm",
        wechat_env_version="trial",
    )


class WebAuthApplicationTest(unittest.TestCase):
    def setUp(self):
        self.repository = FakeIdentityRepository()
        self.gateway = FakeWechatGateway()
        self.application = WebAuthApplication(
            repository=self.repository,
            wechat_gateway=self.gateway,
            settings=settings(),
            clock=lambda: NOW,
        )

    def test_web_exchange_is_one_time_and_returns_an_independent_cookie_session(self):
        created = self.application.create_web_login("A" * 43, idempotency_key="request-key")
        mini_session = self.application.exchange_mini_code("code")

        self.application.confirm_mini_web_login(
            self.gateway.codes[0][0],
            mini_session.principal,
        )
        exchanged = self.application.exchange_web_login(created.session.id, "A" * 43)

        self.assertEqual(exchanged.principal.session_kind, "web_cookie")
        self.assertNotEqual(exchanged.token, mini_session.token)
        self.assertEqual(
            self.repository.sessions[created.session.id].status,
            WebLoginSessionStatus.CONSUMED,
        )
        with self.assertRaisesRegex(ValueError, "already consumed"):
            self.application.exchange_web_login(created.session.id, "A" * 43)

    def test_repeated_create_with_the_same_key_is_idempotent_without_exposing_scene(self):
        first = self.application.create_web_login("B" * 43, idempotency_key="request-key")
        second = self.application.create_web_login("B" * 43, idempotency_key="request-key")

        self.assertEqual(first.session.id, second.session.id)
        self.assertFalse(hasattr(first, "scene_ticket"))
        self.assertNotIn("scene-ticket", repr(first))

    def test_web_login_preserves_a_real_jpeg_qr_response(self):
        gateway = FakeJpegWechatGateway()
        application = WebAuthApplication(
            repository=self.repository,
            wechat_gateway=gateway,
            settings=settings(),
            clock=lambda: NOW,
        )

        created = application.create_web_login("D" * 43, idempotency_key="request-key")

        self.assertTrue(created.qr_data_url.startswith("data:image/jpeg;base64,"))

    def test_api_enforces_origin_cookie_and_public_error_boundaries(self):
        registry = ReadinessRegistry({"database": lambda: ComponentState("ready", "")})
        client = TestClient(
            create_app(
                settings=settings(),
                readiness_registry=registry,
                web_auth_application=self.application,
            ),
            base_url="https://testserver",
        )

        unauthenticated = client.get("/api/v2/me")
        self.assertEqual(unauthenticated.status_code, 401)
        self.assertEqual(unauthenticated.json()["error"]["code"], "AUTH_REQUIRED")

        rejected = client.post(
            "/api/v2/auth/wechat/web/login-sessions",
            json={"browserVerifier": "A" * 43},
            headers={"Origin": "https://evil.example", "Idempotency-Key": "request-key"},
        )
        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(rejected.json()["error"]["code"], "ORIGIN_REJECTED")

        created = client.post(
            "/api/v2/auth/wechat/web/login-sessions",
            json={"browserVerifier": "A" * 43},
            headers={"Origin": "https://testserver", "Idempotency-Key": "request-key"},
        )
        self.assertEqual(created.status_code, 201)
        self.assertNotIn("sceneTicket", created.json())
        session_id = created.json()["sessionId"]

        status = client.get(
            f"/api/v2/auth/wechat/web/login-sessions/{session_id}",
            headers={"X-Web-Login-Verifier": "A" * 43},
        )
        self.assertEqual(status.status_code, 200)
        self.assertNotIn("displayName", status.json())

        mini = self.application.exchange_mini_code("code")
        confirmed = client.post(
            "/api/v2/auth/wechat/mini/web-login-confirm",
            json={"sceneTicket": self.gateway.codes[0][0]},
            headers={"Authorization": f"Bearer {mini.token}"},
        )
        self.assertEqual(confirmed.status_code, 200)

        exchanged = client.post(
            f"/api/v2/auth/wechat/web/login-sessions/{session_id}/exchange",
            headers={
                "Origin": "https://testserver",
                "X-Web-Login-Verifier": "A" * 43,
            },
        )
        self.assertEqual(exchanged.status_code, 200)
        self.assertIn("HttpOnly", exchanged.headers["set-cookie"])
        self.assertIn("Secure", exchanged.headers["set-cookie"])
        self.assertIn("SameSite=Lax", exchanged.headers["set-cookie"])
        self.assertNotIn("openid", exchanged.text.lower())

        me = client.get("/api/v2/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json(), {
            "connected": True,
            "displayName": "已连接微信账号",
            "requestId": me.json()["requestId"],
        })

        replay = client.post(
            f"/api/v2/auth/wechat/web/login-sessions/{session_id}/exchange",
            headers={
                "Origin": "https://testserver",
                "X-Web-Login-Verifier": "A" * 43,
            },
        )
        self.assertEqual(replay.status_code, 409)
        self.assertEqual(replay.json()["error"]["code"], "WEB_LOGIN_ALREADY_CONSUMED")

    def test_unconfigured_wechat_is_publicly_blocked(self):
        blocked_gateway = FakeWechatGateway(configured=False)
        application = WebAuthApplication(
            repository=self.repository,
            wechat_gateway=blocked_gateway,
            settings=settings(),
            clock=lambda: NOW,
        )
        registry = ReadinessRegistry({"database": lambda: ComponentState("ready", "")})
        client = TestClient(create_app(
            settings=settings(),
            readiness_registry=registry,
            web_auth_application=application,
        ))
        response = client.post(
            "/api/v2/auth/wechat/web/login-sessions",
            json={"browserVerifier": "C" * 43},
            headers={"Origin": "https://testserver", "Idempotency-Key": "request-key"},
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "WECHAT_NOT_CONFIGURED")
