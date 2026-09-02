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

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class ChickenbroWclSourceTest(unittest.TestCase):
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
