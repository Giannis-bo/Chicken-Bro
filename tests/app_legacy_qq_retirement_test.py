"""Retired personal QQ transport cannot be rebuilt or re-enabled."""
import unittest
from pathlib import Path
from server.app.platform.config import AppSettings

ROOT = Path(__file__).resolve().parents[1]

class LegacyQqRetirementTests(unittest.TestCase):
    def test_personal_qq_worker_scope_is_rejected(self):
        with self.assertRaises(ValueError):
            AppSettings.from_env({"WOW_APP_ENV": "production", "WOW_DATABASE_URL": "postgresql://wow_app@127.0.0.1/chickenbro_qq_channel", "WOW_WORKER_V2_SCOPE": "qq_group"})

    def test_retired_transport_and_bootstrap_are_not_executable(self):
        self.assertFalse((ROOT / "server/app/channels/qq").exists())
        self.assertFalse((ROOT / "server/qq-channel").exists())
        self.assertFalse(any((ROOT / "server/migrations/product").glob("*_qq_*channel.sql")))
        self.assertFalse(any((ROOT / "server/migrations/product").glob("*_qq_companion*.sql")))

    def test_website_qq_authentication_is_retained(self):
        from server.app.identity.qq_application import QqAuthApplication
        self.assertTrue(callable(QqAuthApplication))
        self.assertTrue((ROOT / "server/app/integrations/qq_connect.py").is_file())
        self.assertTrue((ROOT / "server/migrations/product/0007_qq_web_login.sql").is_file())
