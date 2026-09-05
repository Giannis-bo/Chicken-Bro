import json
import os
import unittest
from unittest.mock import patch

from server.app.chickenbro.wcl_source import build_wcl_log_evidence


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self, *_args):
        return json.dumps(self.payload).encode("utf-8")


class ChickenbroWclSourceTest(unittest.TestCase):
    def test_unfiltered_report_tables_are_not_attributed_to_first_fight(self):
        with patch("server.app.chickenbro.wcl_source.warcraftlogs_credentials_state", return_value={"configured": True, "mode": "v2_oauth", "api": "warcraftlogs-v2-graphql"}), patch(
            "server.app.chickenbro.wcl_source._graphql", return_value={"reportData": {"report": {
                "fights": [{"id": 1, "name": "first"}, {"id": 2, "name": "second"}],
            }}},
        ):
            result = build_wcl_log_evidence({"wclUrl": "https://www.warcraftlogs.com/reports/abc123"})
        self.assertEqual(result["fight"], {})
        self.assertEqual(result["fightId"], "")
        self.assertEqual(len(result["fights"]), 2)

    def test_cn_link_keeps_fight_and_actor_and_returns_analysis_data(self):
        report = {"title": "report", "fights": [{"id": 4, "name": "Kings' Rest"}],
                  "masterData": {"actors": [{"id": 5, "name": "Giannis", "type": "Player", "subType": "Shaman"}]},
                  "casts": {"data": {"entries": [{"name": "Lava Burst", "total": 42}]}},
                  "damage": {"data": {"entries": [{"name": "Lava Burst", "total": 12345}]}},
                  "events": {"data": [{"type": "cast", "timestamp": 10, "sourceID": 5, "abilityGameID": 51505}], "nextPageTimestamp": 20}}
        with patch("server.app.chickenbro.wcl_source.warcraftlogs_credentials_state", return_value={"configured": True, "mode": "v2_oauth", "api": "warcraftlogs-v2-graphql"}), patch(
            "server.app.chickenbro.wcl_source._graphql", return_value={"reportData": {"report": report}},
        ) as query:
            result = build_wcl_log_evidence({"wclUrl": "https://cn.warcraftlogs.com/reports/pqThd2cvwFyKXD6g?fight=4&source=5"})
        self.assertEqual(result["sourceStatus"], "verified")
        self.assertEqual(query.call_args.args[1]["sourceId"], 5)
        self.assertEqual(result["actors"][0]["name"], "Giannis")
        self.assertEqual(result["casts"]["entries"][0]["total"], 42)
        self.assertEqual(result["eventPage"]["nextPageTimestamp"], 20)
        self.assertFalse(result["eventPage"]["complete"])

    def test_reader_fetches_oauth_and_bounded_graphql_evidence(self):
        responses = [
            FakeResponse({"access_token": "oauth-token"}),
            FakeResponse({
                "data": {
                    "reportData": {
                        "report": {
                            "title": "Giannis report",
                            "startTime": 100,
                            "endTime": 200,
                            "fights": [{"id": 1, "name": "Patchwerk", "difficulty": 10, "kill": True}],
                            "events": {"data": [
                                {"type": "cast"},
                                {"type": "damage"},
                                {"type": "death"},
                                {"type": "buffRemove"},
                            ]},
                        }
                    }
                }
            }),
        ]

        with patch.dict(os.environ, {
            "WOW_WARCRAFTLOGS_CLIENT_ID": "client-id",
            "WOW_WARCRAFTLOGS_CLIENT_SECRET": "client-secret",
            "WOW_WARCRAFTLOGS_TIMEOUT_SECONDS": "15",
        }, clear=False), patch(
            "server.app.chickenbro.wcl_source.urlopen",
            side_effect=responses,
        ) as opener:
            result = build_wcl_log_evidence({
                "wclUrl": "https://www.warcraftlogs.com/reports/KfVp6AQ8GMHYFN42?fight=1",
            })

        self.assertEqual("verified", result["sourceStatus"])
        self.assertEqual("KfVp6AQ8GMHYFN42", result["reportCode"])
        self.assertEqual("1", result["fightId"])
        self.assertEqual({
            "total": 4,
            "casts": 1,
            "buffEvents": 1,
            "deaths": 1,
            "damageEvents": 1,
            "healingEvents": 0,
            "mechanicEvents": 0,
        }, result["eventSummary"])
        self.assertEqual(2, opener.call_count)

    def test_reader_redacts_secret_from_api_failure(self):
        with patch.dict(os.environ, {
            "WOW_WARCRAFTLOGS_CLIENT_ID": "client-id",
            "WOW_WARCRAFTLOGS_CLIENT_SECRET": "client-secret",
        }, clear=False), patch(
            "server.app.chickenbro.wcl_source.urlopen",
            side_effect=RuntimeError("client_secret=client-secret Bearer oauth-token"),
        ):
            result = build_wcl_log_evidence({
                "wclUrl": "https://www.warcraftlogs.com/reports/KfVp6AQ8GMHYFN42?fight=1",
            })

        self.assertEqual("blocked", result["sourceStatus"])
        self.assertNotIn("client-secret", str(result["blockers"]))
        self.assertNotIn("oauth-token", str(result["blockers"]))


if __name__ == "__main__":
    unittest.main()
