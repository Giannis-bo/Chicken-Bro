import unittest

from server import chickenbro_source_refresh


class ChickenbroSourceRefreshTest(unittest.TestCase):
    def test_raiderio_refresh_is_independent_of_observed_build_compilation(self):
        calls = []

        summary, exit_code = chickenbro_source_refresh.run_refresh(
            postgres_enabled=lambda: True,
            sync_raiderio=lambda **kwargs: calls.append(kwargs) or {
                "sourceStatus": "synced",
                "checkedAt": "2026-08-01T13:18:01+00:00",
                "expiresAt": "2026-08-01T19:18:01+00:00",
                "profileCount": 317,
            },
        )

        self.assertEqual(0, exit_code)
        self.assertEqual([{"force": True}], calls)
        self.assertEqual("synced", summary["sourceStatus"])
        self.assertEqual(317, summary["profileCount"])
        self.assertNotIn("communityTemplates", summary)

    def test_failed_source_refresh_is_visible_to_systemd(self):
        summary, exit_code = chickenbro_source_refresh.run_refresh(
            postgres_enabled=lambda: True,
            sync_raiderio=lambda **kwargs: {"sourceStatus": "blocked", "errors": ["upstream unavailable"]},
        )

        self.assertEqual(1, exit_code)
        self.assertEqual("blocked", summary["sourceStatus"])
        self.assertEqual(["upstream unavailable"], summary["errors"])


if __name__ == "__main__":
    unittest.main()
