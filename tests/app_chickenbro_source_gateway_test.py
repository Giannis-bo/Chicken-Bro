import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from server.app.chickenbro.source_gateway import (
    ChickenbroSourceGateway,
    SourceGatewayUnauthorized,
    ServerConfiguredSourceQuery,
)


class ChickenbroSourceGatewayTest(unittest.TestCase):
    def test_cn_report_is_canonicalized_before_reader(self):
        reader_calls = []
        query = ServerConfiguredSourceQuery(wcl_reader=lambda value: reader_calls.append(value) or {
            "sourceStatus": "verified", "actors": [{"id": 5, "name": "Giannis"}],
            "casts": {"entries": [{"name": "Lava Burst", "total": 42}]},
        })
        result = query.query("warcraftlogs", "https://cn.warcraftlogs.com/reports/pqThd2cvwFyKXD6g?fight=4&source=5")
        self.assertEqual(reader_calls[0]["wclUrl"], "https://www.warcraftlogs.com/reports/pqThd2cvwFyKXD6g#fight=4&source=5")
        self.assertEqual(result["facts"][0]["actors"][0]["name"], "Giannis")
        self.assertEqual(result["facts"][0]["casts"]["entries"][0]["total"], 42)

    def test_formal_router_registers_the_internal_source_gateway(self):
        root = Path(__file__).resolve().parents[1]
        route_path = root / "server/app/api/routes/source_gateway.py"
        self.assertTrue(route_path.is_file())
        route_source = route_path.read_text(encoding="utf-8")
        router_source = (root / "server/app/api/routes/__init__.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("SOURCE_GATEWAY_PATH", route_source)
        self.assertIn("include_in_schema=False", route_source)
        self.assertIn("source_gateway_router", router_source)
        self.assertIn("include_router(source_gateway_router)", router_source)

    def test_issued_capability_allows_one_source_query_and_revoke_blocks_it(self):
        calls = []
        gateway = ChickenbroSourceGateway(
            query_service=lambda provider, target: calls.append((provider, target)) or {
                "sourceKey": provider,
                "status": "source_reference",
            },
            now=lambda: datetime(2026, 9, 2, 1, 0, tzinfo=timezone.utc),
        )

        token = gateway.issue_capability()
        result = gateway.query(token, "warcraftlogs", "https://www.warcraftlogs.com/reports/abc123?fight=1")

        self.assertEqual("source_reference", result["status"])
        self.assertEqual(
            [("warcraftlogs", "https://www.warcraftlogs.com/reports/abc123?fight=1")],
            calls,
        )
        gateway.revoke(token)
        with self.assertRaises(SourceGatewayUnauthorized):
            gateway.query(token, "warcraftlogs", "https://www.warcraftlogs.com/reports/abc123?fight=1")

    def test_server_query_uses_configured_wcl_api_reader_and_never_public_page_reader(self):
        log_evidence = {
            "status": "ready",
            "sourceStatus": "verified",
            "api": "warcraftlogs-v2-graphql",
            "reportCode": "KfVp6AQ8GMHYFN42",
            "sourceUrl": "https://www.warcraftlogs.com/reports/KfVp6AQ8GMHYFN42?fight=1",
            "fightId": "1",
            "reportTitle": "Giannis report",
            "reportWindow": {"startTime": 100, "endTime": 200},
            "fight": {"id": "1", "name": "Patchwerk", "kill": True},
            "eventSummary": {"casts": 12, "damageEvents": 80, "deaths": 0},
            "evidenceRefs": ["wcl.report", "wcl.fight", "wcl.events"],
            "nextActions": [],
        }

        with patch(
            "server.app.chickenbro.source_gateway.build_wcl_log_evidence",
            return_value=log_evidence,
        ) as reader, patch(
            "server.app.chickenbro.source_gateway.build_public_web_research_tool_result",
            side_effect=AssertionError("source API lookup must not open a public page"),
            create=True,
        ):
            result = ServerConfiguredSourceQuery().query(
                "warcraftlogs",
                "https://www.warcraftlogs.com/reports/KfVp6AQ8GMHYFN42?fight=1",
            )

        reader.assert_called_once()
        self.assertEqual("warcraftlogs", result["sourceKey"])
        self.assertEqual("verified", result["status"])
        self.assertEqual("KfVp6AQ8GMHYFN42", result["facts"][0]["reportCode"])
        self.assertEqual(["wcl.report", "wcl.fight", "wcl.events"], result["evidenceRefs"])

    def test_server_query_uses_raiderio_character_api_and_returns_bounded_snapshot(self):
        query = ServerConfiguredSourceQuery()
        candidate = type(
            "Candidate",
            (),
            {
                "snapshot": {
                    "character": {
                        "name": "Giannis",
                        "realm": "Silver Hand",
                        "region": "cn",
                        "classKey": "shaman",
                        "specKey": "elemental",
                        "level": 90,
                    },
                    "gear": {"head": {"itemId": 1, "itemLevel": 90, "bonusIds": [1], "enchant": 2}},
                    "talents": {"string": "loadout"},
                    "profileSource": "raiderio",
                },
                "provenance": {
                    "sourceUrl": "https://raider.io/characters/cn/silver-hand/Giannis",
                    "sourceRevision": "rev-1",
                    "fetchedAt": "2026-09-02T01:00:00+00:00",
                },
                "raw_sha256": "a" * 64,
                "readiness": type("Readiness", (), {"value": "INCOMPLETE_FOR_SIMC"})(),
                "source_url": "https://raider.io/characters/cn/silver-hand/Giannis",
            },
        )()

        class Router:
            def resolve(self, target):
                self.target = target
                return candidate

        router = Router()
        result = ServerConfiguredSourceQuery(character_router=router).query(
            "raiderio",
            "https://raider.io/cn/characters/cn/silver-hand/Giannis",
        )

        self.assertEqual("https://raider.io/cn/characters/cn/silver-hand/Giannis", router.target)
        self.assertEqual("raiderio", result["sourceKey"])
        self.assertEqual("source_reference", result["status"])
        self.assertEqual("Giannis", result["facts"][0]["character"]["name"])
        self.assertEqual("a" * 64, result["evidence"][0]["rawSha256"])
        self.assertNotIn("access_key", str(result))


if __name__ == "__main__":
    unittest.main()
