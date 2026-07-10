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


if __name__ == "__main__":
    unittest.main()
