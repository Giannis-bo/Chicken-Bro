import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

from server.app.chickenbro.source_gateway import (
    ChickenbroSourceGateway,
    SourceGatewayUnauthorized,
    ServerConfiguredSourceQuery,
)


class ChickenbroSourceGatewayTest(unittest.TestCase):
    def test_source_capability_lasts_through_analysis_but_can_still_be_revoked(self):
        now = datetime(2026, 9, 5, tzinfo=timezone.utc)
        gateway = ChickenbroSourceGateway(query_service=lambda *_: {"status": "verified"}, now=lambda: now)
        token = gateway.issue_capability()
        now += timedelta(seconds=480)
        self.assertEqual(gateway.query(token, "warcraftlogs", "target")["status"], "verified")
        gateway.revoke(token)
        with self.assertRaises(SourceGatewayUnauthorized):
            gateway.query(token, "warcraftlogs", "target")

    def test_capability_gateway_keeps_event_options_and_context(self):
        calls = []
        service = ServerConfiguredSourceQuery(wcl_reader=lambda value: calls.append(value) or {
            "sourceStatus": "verified", "players": [{"id": 4, "combatantInfo": {"gear": [{"id": 123}]}}],
            "events": [{"type": "cast", "timestamp": 500}], "eventPage": {"nextPageTimestamp": 600}})
        gateway = ChickenbroSourceGateway(query_service=service)
        token = gateway.issue_capability()
        options = {"dataType": "Casts", "startTime": 500, "endTime": 900}
        result = gateway.query(token, "warcraftlogs", "https://cn.warcraftlogs.com/reports/abc123?fight=4&source=4", options)
        self.assertEqual(calls[0]["options"], options)
        self.assertEqual(result["facts"][0]["events"][0]["timestamp"], 500)
        self.assertEqual(result["facts"][0]["players"][0]["combatantInfo"]["gear"][0]["id"], 123)

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

    def test_research_query_routes_without_simc_projection_and_retains_capability(self):
        class Research:
            def character(self, target):
                return {"status": "source_reference", "facts": [{"gear": {"neck": {
                    "gems_detail": [{"name": "16 Mastery & 7 Crit"}], "tier": "36"}}}], "target": target}
            def rankings(self, options):
                return {"status": "source_reference", "facts": [{"score": 3600}], "options": options}
            def characters(self, targets):
                return {"status": "partial", "facts": [{"targets": targets}]}
        service = ServerConfiguredSourceQuery(raiderio_research=Research())
        gateway = ChickenbroSourceGateway(query_service=service)
        token = gateway.issue_capability()
        target = "https://raider.io/cn/characters/cn/silver-hand/Giannis"
        profile = gateway.query(token, "raiderio", target)
        self.assertEqual(profile["facts"][0]["gear"]["neck"]["gems_detail"][0]["name"], "16 Mastery & 7 Crit")
        ranking = gateway.query(token, "raiderio_rankings", "rankings", {"className": "shaman", "spec": "enhancement"})
        self.assertEqual(ranking["options"]["spec"], "enhancement")
        batch = gateway.query(token, "raiderio_batch", "characters", {"targets": [target]})
        self.assertEqual(batch["facts"][0]["targets"], [target])
        gateway.revoke(token)
        with self.assertRaises(SourceGatewayUnauthorized):
            gateway.query(token, "raiderio_rankings", "rankings", {"className": "shaman", "spec": "enhancement"})

    def test_research_dispatch_rejects_unrecognized_targets_and_options(self):
        from server.app.simulation.sources import InvalidSourceLink
        service = ServerConfiguredSourceQuery(raiderio_research=object())
        for provider, target, options in [
            ("raiderio_batch", "characters", {"targets": [], "extra": "forbidden"}),
            ("raiderio_rankings", "https://localhost", {"className": "shaman", "spec": "enhancement"}),
            ("raiderio", "https://raider.io/characters/us/area-52/Test", {"extra": 1}),
        ]:
            with self.subTest(provider=provider), self.assertRaises(InvalidSourceLink):
                service.query(provider, target, options)


if __name__ == "__main__":
    unittest.main()
