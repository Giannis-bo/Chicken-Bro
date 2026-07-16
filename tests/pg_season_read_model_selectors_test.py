#!/usr/bin/env python3
import unittest


class PgSeasonReadModelSelectorsTest(unittest.TestCase):
    def test_build_active_season_read_model_maps_rows_and_marks_expired_payload_stale(self):
        from server.pg_season_read_model_selectors import build_active_season_read_model

        row = (
            "season-pg",
            "Season PG",
            "season-pg-r1",
            "",
            "verified",
            "2026-07-01T00:00:00+00:00",
            "2026-07-09T00:00:00+00:00",
            '[{"type":"official","sourceUrl":"https://example.test/season"}]',
            {"seasonRevision": "cached-revision", "errors": ["existing blocker"], "raids": []},
        )
        dungeon_rows = [
            (
                "dungeon-a",
                "instance-a",
                "Dungeon A",
                "DA",
                1800,
                '{"mapId":123}',
            )
        ]

        payload = build_active_season_read_model(
            row,
            dungeon_rows,
            now="2026-07-10T00:00:00+00:00",
        )

        self.assertEqual(payload["seasonId"], "season-pg")
        self.assertEqual(payload["id"], "season-pg")
        self.assertEqual(payload["seasonLabel"], "Season PG")
        self.assertEqual(payload["label"], "Season PG")
        self.assertEqual(payload["seasonRevision"], "season-pg-r1")
        self.assertEqual(payload["revision"], "season-pg-r1")
        self.assertEqual(payload["locale"], "zh_CN")
        self.assertEqual(payload["dataStatus"], "stale")
        self.assertEqual(payload["verifiedAt"], "2026-07-01T00:00:00+00:00")
        self.assertEqual(payload["expiresAt"], "2026-07-09T00:00:00+00:00")
        self.assertEqual(payload["errors"], ["existing blocker", "season cache expired"])
        self.assertEqual(payload["sourceRefs"][0]["type"], "official")
        self.assertEqual(
            payload["dungeons"],
            [
                {
                    "id": "dungeon-a",
                    "dungeonId": "dungeon-a",
                    "instanceId": "instance-a",
                    "name": "Dungeon A",
                    "shortName": "DA",
                    "timerSeconds": 1800,
                    "sourceRefs": payload["sourceRefs"],
                    "payload": {"mapId": 123},
                }
            ],
        )
        self.assertEqual(payload["raids"], [])
        self.assertEqual(build_active_season_read_model(None, []), {})


if __name__ == "__main__":
    unittest.main()
