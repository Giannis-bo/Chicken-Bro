import unittest

from server.app.platform.config import AppSettings


class AppConfigTest(unittest.TestCase):
    def test_postgres_url_is_required_and_secrets_are_not_repr_visible(self):
        with self.assertRaisesRegex(ValueError, "WOW_DATABASE_URL"):
            AppSettings.from_env({"WOW_APP_ENV": "candidate"})
        settings = AppSettings.from_env({
            "WOW_APP_ENV": "candidate",
            "WOW_DATABASE_URL": "postgresql://user:secret@db.example/wow",
            "WOW_API_V2_HOST": "127.0.0.1",
            "WOW_API_V2_PORT": "8790",
        })
        self.assertEqual(settings.port, 8790)
        self.assertNotIn("secret", repr(settings))

    def test_candidate_rejects_public_binding_and_invalid_poll_bounds(self):
        base = {
            "WOW_APP_ENV": "candidate",
            "WOW_DATABASE_URL": "postgresql://user@db.example/wow",
        }
        with self.assertRaisesRegex(ValueError, "loopback"):
            AppSettings.from_env({**base, "WOW_API_V2_HOST": "0.0.0.0"})
        with self.assertRaisesRegex(ValueError, "POLL"):
            AppSettings.from_env({**base, "WOW_WORKER_V2_POLL_SECONDS": "0.01"})

    def test_web_and_wechat_settings_are_bounded_and_secret_redacted(self):
        settings = AppSettings.from_env({
            "WOW_APP_ENV": "candidate",
            "WOW_DATABASE_URL": "postgresql://user@db.example/wow",
            "WOW_WEB_ORIGIN": "https://www.chickenbro.cloud",
            "WOW_WEB_COOKIE_NAME": "__Host-wow_v2",
            "WOW_WEB_LOGIN_TTL_SECONDS": "300",
            "WOW_WEB_SESSION_TTL_SECONDS": "604800",
            "WOW_WECHAT_APPID": "wx-test",
            "WOW_WECHAT_SECRET": "secret-value",
            "WOW_WECHAT_PAGE": "pages/auth/web-login-confirm",
            "WOW_WECHAT_ENV_VERSION": "trial",
        })
        self.assertEqual(settings.web_origin, "https://www.chickenbro.cloud")
        self.assertEqual(settings.web_login_ttl_seconds, 300)
        self.assertEqual(settings.web_session_ttl_seconds, 604800)
        self.assertEqual(settings.wechat_appid, "wx-test")
        self.assertNotIn("secret-value", repr(settings))
