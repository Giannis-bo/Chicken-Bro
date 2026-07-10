#!/usr/bin/env python3
import unittest


class PgCacheReadModelSelectorsTest(unittest.TestCase):
    def test_build_raiderio_cache_read_model_maps_row_and_preserves_payload_timestamps(self):
        from server.pg_cache_read_model_selectors import build_raiderio_cache_read_model

        row = (
            '{"status":"synced","checkedAt":"payload-checked","profiles":[{"name":"Mage"}]}',
            "2026-07-10T01:00:00+00:00",
            "2026-07-10T07:00:00+00:00",
        )

        payload = build_raiderio_cache_read_model(row)

        self.assertEqual(payload["status"], "synced")
        self.assertEqual(payload["sourceStatus"], "synced")
        self.assertEqual(payload["checkedAt"], "payload-checked")
        self.assertEqual(payload["updatedAt"], "2026-07-10T01:00:00+00:00")
        self.assertEqual(payload["expiresAt"], "2026-07-10T07:00:00+00:00")
        self.assertEqual(payload["profiles"], [{"name": "Mage"}])
        self.assertEqual(
            build_raiderio_cache_read_model(None),
            {
                "sourceStatus": "blocked",
                "status": "blocked",
                "errors": ["PostgreSQL Raider.IO cache is missing"],
            },
        )

    def test_build_stat_weight_cache_read_model_maps_row_and_preserves_payload_timestamp(self):
        from server.pg_cache_read_model_selectors import build_stat_weight_cache_read_model

        row = (
            '{"status":"verified","checkedAt":"payload-checked","weights":[{"key":"haste","value":1.2}]}',
            "verified",
            "2026-07-10T01:30:00+00:00",
        )

        payload = build_stat_weight_cache_read_model(
            row,
            class_key="mage",
            spec_key="frost",
            scenario_key="mplus_mixed_route",
        )

        self.assertEqual(payload["classKey"], "mage")
        self.assertEqual(payload["specKey"], "frost")
        self.assertEqual(payload["scenarioKey"], "mplus_mixed_route")
        self.assertEqual(payload["sourceStatus"], "verified")
        self.assertEqual(payload["status"], "verified")
        self.assertEqual(payload["checkedAt"], "payload-checked")
        self.assertEqual(payload["updatedAt"], "2026-07-10T01:30:00+00:00")
        self.assertEqual(payload["weights"], [{"key": "haste", "value": 1.2}])
        self.assertIsNone(
            build_stat_weight_cache_read_model(
                None,
                class_key="mage",
                spec_key="frost",
                scenario_key="mplus_mixed_route",
            )
        )


if __name__ == "__main__":
    unittest.main()
