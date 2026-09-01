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
