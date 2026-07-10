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

    def test_build_stat_weight_cache_read_model_preserves_all_existing_payload_fields(self):
        from server.pg_cache_read_model_selectors import build_stat_weight_cache_read_model

        existing_fields = {
            "classKey": "payload-class",
            "specKey": "payload-spec",
            "scenarioKey": "payload-scenario",
            "sourceStatus": "payload-source-status",
            "status": "payload-status",
            "checkedAt": "payload-checked-at",
            "updatedAt": "payload-updated-at",
        }

        payload = build_stat_weight_cache_read_model(
            (dict(existing_fields), "row-source-status", "row-computed-at"),
            class_key="supplied-class",
            spec_key="supplied-spec",
            scenario_key="supplied-scenario",
        )

        self.assertEqual(
            {field: payload[field] for field in existing_fields},
            existing_fields,
        )

    def test_build_stat_weight_cache_read_model_defaults_invalid_json_payloads(self):
        from server.pg_cache_read_model_selectors import build_stat_weight_cache_read_model

        cases = {
            "malformed JSON": "{not-json",
            "valid non-dict JSON": '["not", "a", "dict"]',
        }

        for label, raw_payload in cases.items():
            with self.subTest(label=label):
                payload = build_stat_weight_cache_read_model(
                    (raw_payload, None, "row-computed-at"),
                    class_key="mage",
                    spec_key="frost",
                    scenario_key="mplus_mixed_route",
                )

                self.assertEqual(
                    payload,
                    {
                        "classKey": "mage",
                        "specKey": "frost",
                        "scenarioKey": "mplus_mixed_route",
                        "sourceStatus": "blocked",
                        "status": "blocked",
                        "checkedAt": "row-computed-at",
                        "updatedAt": "row-computed-at",
                    },
                )

    def test_build_stat_weight_latest_run_read_model_returns_exact_empty_blocked_envelope(self):
        from server.pg_cache_read_model_selectors import build_stat_weight_latest_run_read_model

        self.assertEqual(
            build_stat_weight_latest_run_read_model([]),
            {
                "refreshMode": "",
                "refreshedAt": "",
                "status": "blocked",
                "sourceStatus": "blocked",
                "acceptedCount": 0,
                "blockedCount": 0,
                "errors": ["PostgreSQL stat weight cache is empty"],
            },
        )

    def test_build_stat_weight_latest_run_read_model_summarizes_statuses_and_timestamps(self):
        from server.pg_cache_read_model_selectors import build_stat_weight_latest_run_read_model

        cases = (
            ("all accepted", [(" verified ", "2026-07-10T01:00:00+00:00"), ("partial", "2026-07-10T02:00:00+00:00"), ("stale", "2026-07-10T03:00:00+00:00")], "verified"),
            ("mixed", [("verified", "2026-07-10T01:00:00+00:00"), ("blocked", "2026-07-10T04:00:00+00:00")], "partial"),
            ("all blocked", [(" VERIFIED", "2026-07-10T01:00:00+00:00"), ("blocked", "2026-07-10T02:00:00+00:00")], "blocked"),
        )

        for label, rows, expected_status in cases:
            with self.subTest(label=label):
                payload = build_stat_weight_latest_run_read_model(rows)
                self.assertEqual(payload["status"], expected_status)
                self.assertEqual(payload["sourceStatus"], expected_status)
                self.assertEqual(payload["acceptedCount"], 3 if label == "all accepted" else 1 if label == "mixed" else 0)
                self.assertEqual(payload["blockedCount"], 0 if label == "all accepted" else 1 if label == "mixed" else 2)
                self.assertEqual(payload["refreshedAt"], "2026-07-10T04:00:00+00:00" if label == "mixed" else "2026-07-10T03:00:00+00:00" if label == "all accepted" else "2026-07-10T02:00:00+00:00")
                self.assertEqual(payload["refreshMode"], "postgres_cache")
                self.assertEqual(payload["specCount"], 0)
                self.assertEqual(payload["scenarioCount"], len(rows))
                self.assertEqual(payload["errors"], [])


if __name__ == "__main__":
    unittest.main()
