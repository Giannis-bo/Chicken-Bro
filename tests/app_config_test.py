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

    def test_worker_heartbeat_configuration_is_environment_scoped_and_bounded(self):
        base = {
            "WOW_APP_ENV": "candidate",
            "WOW_DATABASE_URL": "postgresql://user@db.example/wow",
        }
        settings = AppSettings.from_env(base)
        self.assertEqual(
            settings.worker_heartbeat_path,
            "/var/lib/chickenbro/candidate-worker-heartbeat.json",
        )
        self.assertEqual(settings.worker_heartbeat_ttl_seconds, 45)
        with self.assertRaisesRegex(ValueError, "HEARTBEAT_TTL"):
            AppSettings.from_env({**base, "WOW_WORKER_V2_HEARTBEAT_TTL_SECONDS": "5"})
        with self.assertRaisesRegex(ValueError, "HEARTBEAT_PATH"):
            AppSettings.from_env({**base, "WOW_WORKER_V2_HEARTBEAT_PATH": "relative.json"})

    def test_web_settings_remain_bounded_and_wechat_configuration_is_retired(self):
        settings = AppSettings.from_env({
            "WOW_APP_ENV": "candidate",
            "WOW_DATABASE_URL": "postgresql://user@db.example/wow",
            "WOW_WEB_ORIGIN": "https://www.chickenbro.cloud",
            "WOW_WECHAT_SECRET": "unused-legacy-secret",
            "WOW_WECHAT_CHECK_PATH": "obsolete",
        })
        self.assertEqual(settings.web_origin, "https://www.chickenbro.cloud")
        self.assertFalse(hasattr(settings, "wechat_secret"))
        self.assertNotIn("unused-legacy-secret", repr(settings))

    def test_removed_prototype_environment_has_no_runtime_owner(self):
        settings = AppSettings.from_env({
            "WOW_APP_ENV": "candidate",
            "WOW_DATABASE_URL": "postgresql://user@db.example/wow",
            "WOW_WEB_PROTOTYPE_ENABLED": "1",
            "WOW_WEB_PROTOTYPE_TTL_SECONDS": "1800",
        })
        self.assertFalse(hasattr(settings, "prototype_enabled"))
        self.assertFalse(hasattr(settings, "prototype_ttl_seconds"))
