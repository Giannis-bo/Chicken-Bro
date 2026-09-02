from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID
import unittest

from server.app.identity.audit import AuthAuditEvent, validate_auth_audit_payload
from server.app.identity.domain import Principal
from server.app.identity.request_auth import (
    CredentialTransportError,
    credential_for_principal,
    resolve_mutating_request_principal,
    resolve_request_principal,
)
from server.app.platform.config import AppSettings
from server.app.platform.csrf import CsrfRejectedError


USER_ID = UUID("00000000-0000-4000-8000-000000000041")
NOW = datetime(2026, 9, 2, 15, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]


class FakeAuthApplication:
    def __init__(self):
        self.calls = []

    def resolve_principal(self, credential, kind):
        self.calls.append((credential, kind))
        expected = {"mini-token": "mini_bearer", "web-token": "web_cookie"}
        if expected.get(credential) != kind:
            return None
        return Principal(user_id=USER_ID, session_kind=kind)


def request(
    *,
    authorization="",
    cookie="",
    origin="",
    host="",
    csrf_cookie="",
    csrf_header="",
):
    cookies = {"__Host-chickenbro-session": cookie} if cookie else {}
    if csrf_cookie:
        cookies["__Host-chickenbro-csrf"] = csrf_cookie
    return SimpleNamespace(
        headers={
            "authorization": authorization,
            "origin": origin,
            "host": host,
            "x-csrf-token": csrf_header,
        },
        cookies=cookies,
    )


class AppIdentityApiTest(unittest.TestCase):
    def setUp(self):
        self.application = FakeAuthApplication()
        self.settings = AppSettings(
            environment="test",
            database_url="postgresql://redacted",
            web_origin="https://www.chickenbro.cloud",
        )

    def test_bearer_and_cookie_together_are_rejected_before_resolution(self):
        with self.assertRaises(CredentialTransportError) as caught:
            resolve_request_principal(
                request(authorization="Bearer mini-token", cookie="web-token"),
                application=self.application,
                web_cookie_name="__Host-chickenbro-session",
            )

        self.assertEqual(caught.exception.code, "AMBIGUOUS_AUTH")
        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(self.application.calls, [])

    def test_each_transport_resolves_only_its_session_kind(self):
        mini = resolve_request_principal(
            request(authorization="Bearer mini-token"),
            application=self.application,
            web_cookie_name="__Host-chickenbro-session",
        )
        web = resolve_request_principal(
            request(cookie="web-token"),
            application=self.application,
            web_cookie_name="__Host-chickenbro-session",
        )

        self.assertEqual(mini.session_kind, "mini_bearer")
        self.assertEqual(web.session_kind, "web_cookie")
        self.assertEqual(credential_for_principal(request(authorization="Bearer mini-token"), mini, "__Host-chickenbro-session"), "mini-token")
        self.assertEqual(credential_for_principal(request(cookie="web-token"), web, "__Host-chickenbro-session"), "web-token")

        for cross_transport in (
            request(authorization="Bearer web-token"),
            request(cookie="mini-token"),
        ):
            with self.subTest(request=cross_transport):
                with self.assertRaises(CredentialTransportError) as caught:
                    resolve_request_principal(
                        cross_transport,
                        application=self.application,
                        web_cookie_name="__Host-chickenbro-session",
                    )
                self.assertEqual(caught.exception.code, "AUTH_REQUIRED")

    def test_missing_or_malformed_authorization_never_falls_back(self):
        for bad_request in (
            request(),
            request(authorization="Basic value"),
            request(authorization="Bearer"),
            request(authorization="Bearer mini token"),
            request(authorization="Bearer  mini-token"),
        ):
            with self.subTest(headers=bad_request.headers):
                with self.assertRaises(CredentialTransportError) as caught:
                    resolve_request_principal(
                        bad_request,
                        application=self.application,
                        web_cookie_name="__Host-chickenbro-session",
                    )
                self.assertEqual(caught.exception.code, "AUTH_REQUIRED")
                self.assertEqual(caught.exception.status_code, 401)

    def test_mutating_web_auth_requires_csrf_but_mini_bearer_does_not(self):
        mini = resolve_mutating_request_principal(
            request(authorization="Bearer mini-token"),
            application=self.application,
            settings=self.settings,
        )
        self.assertEqual(mini.session_kind, "mini_bearer")

        with self.assertRaises(CsrfRejectedError):
            resolve_mutating_request_principal(
                request(
                    cookie="web-token",
                    origin="https://www.chickenbro.cloud",
                    host="www.chickenbro.cloud",
                    csrf_cookie="right",
                    csrf_header="wrong",
                ),
                application=self.application,
                settings=self.settings,
            )

        web = resolve_mutating_request_principal(
            request(
                cookie="web-token",
                origin="https://www.chickenbro.cloud",
                host="www.chickenbro.cloud",
                csrf_cookie="right",
                csrf_header="right",
            ),
            application=self.application,
            settings=self.settings,
        )
        self.assertEqual(web.session_kind, "web_cookie")

    def test_auth_audit_payload_is_allowlisted_and_secret_fields_are_rejected(self):
        event = AuthAuditEvent(
            event_type="auth.decision",
            request_id="00000000-0000-4000-8000-000000000042",
            user_id=USER_ID,
            session_kind="mini_bearer",
            status_code=200,
            timestamp=NOW,
            reason_code="AUTHENTICATED",
        )
        payload = event.payload()

        self.assertEqual(set(payload), {
            "requestId",
            "sessionKind",
            "statusCode",
            "timestamp",
            "reasonCode",
        })
        validate_auth_audit_payload(payload)

        for key in ("token", "cookie", "openid", "session_key", "verifier", "ticket", "secret"):
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, "sensitive"):
                    validate_auth_audit_payload({**payload, key: "must-not-be-recorded"})

    def test_fastapi_wiring_uses_unified_principal_mutation_and_auth_cookie_contracts(self):
        """Catches leaving the tested security primitives disconnected from formal routes."""
        dependencies = (ROOT / "server/app/api/dependencies.py").read_text(encoding="utf-8")
        routes = (ROOT / "server/app/api/routes/auth.py").read_text(encoding="utf-8")
        main = (ROOT / "server/app/main.py").read_text(encoding="utf-8")

        for contract in (
            "def require_principal(",
            "def require_mutating_principal(",
            "resolve_request_principal(",
            "resolve_mutating_request_principal(",
            "record_auth_audit",
        ):
            self.assertIn(contract, dependencies)
        self.assertIn("Depends(require_principal)", routes)
        self.assertIn("Depends(require_mutating_principal)", routes)
        self.assertIn("set_web_auth_cookies(", routes)
        self.assertIn("clear_web_auth_cookies(", routes)
        self.assertIn("issue_csrf_token()", routes)
        self.assertIn("auth_audit_sink", main)


if __name__ == "__main__":
    unittest.main()
