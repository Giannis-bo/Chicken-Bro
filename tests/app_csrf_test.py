from types import SimpleNamespace
from unittest.mock import patch
import re
import unittest

from server.app.platform.config import AppSettings
from server.app.platform.cookies import clear_web_auth_cookies, set_web_auth_cookies
from server.app.platform.csrf import CsrfRejectedError, issue_csrf_token, require_web_csrf
from server.app.platform.origin import OriginRejectedError, require_web_origin


class FakeResponse:
    def __init__(self):
        self.set_calls = []
        self.delete_calls = []

    def set_cookie(self, **kwargs):
        self.set_calls.append(kwargs)

    def delete_cookie(self, **kwargs):
        self.delete_calls.append(kwargs)


def request(*, origin="https://www.chickenbro.cloud", host="www.chickenbro.cloud", csrf_cookie="csrf", csrf_header="csrf"):
    return SimpleNamespace(
        headers={
            "origin": origin,
            "host": host,
            "x-csrf-token": csrf_header,
        },
        cookies={"__Host-chickenbro-csrf": csrf_cookie},
    )


class AppCsrfTest(unittest.TestCase):
    def setUp(self):
        self.settings = AppSettings(
            environment="test",
            database_url="postgresql://redacted",
            web_origin="https://www.chickenbro.cloud",
        )

    def test_formal_cookie_names_and_attributes_are_fixed_to_host_scope(self):
        self.assertEqual(self.settings.web_cookie_name, "__Host-chickenbro-session")
        self.assertEqual(self.settings.web_csrf_cookie_name, "__Host-chickenbro-csrf")

        response = FakeResponse()
        set_web_auth_cookies(response, self.settings, session_token="session", csrf_token="csrf")

        self.assertEqual([call["key"] for call in response.set_calls], [
            "__Host-chickenbro-session",
            "__Host-chickenbro-csrf",
        ])
        session, csrf = response.set_calls
        self.assertTrue(session["httponly"])
        self.assertFalse(csrf["httponly"])
        for call in (session, csrf):
            self.assertTrue(call["secure"])
            self.assertEqual(call["samesite"].lower(), "lax")
            self.assertEqual(call["path"], "/")
            self.assertNotIn("domain", call)

        clear_web_auth_cookies(response, self.settings)
        self.assertEqual([call["key"] for call in response.delete_calls], [
            "__Host-chickenbro-session",
            "__Host-chickenbro-csrf",
        ])

    def test_csrf_tokens_are_independent_opaque_256_bit_values(self):
        first = issue_csrf_token()
        second = issue_csrf_token()

        self.assertRegex(first, re.compile(r"[A-Za-z0-9_-]{43}\Z"))
        self.assertRegex(second, re.compile(r"[A-Za-z0-9_-]{43}\Z"))
        self.assertNotEqual(first, second)

    def test_cookie_write_requires_exact_origin_host_and_constant_time_double_submit(self):
        with patch("server.app.platform.csrf.hmac.compare_digest", return_value=True) as compared:
            require_web_csrf(request(), self.settings)

        compared.assert_called_once_with("csrf", "csrf")

        for rejected in (
            request(origin="https://evil.example"),
            request(host="evil.example"),
        ):
            with self.subTest(headers=rejected.headers):
                with self.assertRaises(OriginRejectedError):
                    require_web_origin(rejected, self.settings.web_origin)

        for rejected in (
            request(csrf_cookie=""),
            request(csrf_header=""),
            request(csrf_cookie="right", csrf_header="wrong"),
        ):
            with self.subTest(headers=rejected.headers, cookies=rejected.cookies):
                with self.assertRaises(CsrfRejectedError):
                    require_web_csrf(rejected, self.settings)

    def test_cookie_names_must_be_distinct_host_prefixed_values(self):
        base_env = {
            "WOW_APP_ENV": "test",
            "WOW_DATABASE_URL": "postgresql://redacted",
        }
        with self.assertRaisesRegex(ValueError, "WOW_WEB_CSRF_COOKIE_NAME"):
            AppSettings.from_env({**base_env, "WOW_WEB_CSRF_COOKIE_NAME": "csrf"})
        with self.assertRaisesRegex(ValueError, "distinct"):
            AppSettings.from_env({
                **base_env,
                "WOW_WEB_COOKIE_NAME": "__Host-same",
                "WOW_WEB_CSRF_COOKIE_NAME": "__Host-same",
            })


if __name__ == "__main__":
    unittest.main()
