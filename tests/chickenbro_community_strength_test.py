import importlib
import unittest


class ChickenbroCommunityStrengthTest(unittest.TestCase):
    def setUp(self):
        importlib.import_module("server.chickenbro_community_strength").reset_public_wcl_rankings_state()

    def test_public_wcl_rankings_are_compacted_without_player_identity(self):
        try:
            module = importlib.import_module("server.chickenbro_community_strength")
        except ImportError:
            module = None
        builder = getattr(module, "build_wcl_public_rankings_tool_result", None) if module else None

        self.assertIsNotNone(builder, "current-strength research needs a bounded public WCL rankings adapter")
        result = builder(
            {"classKey": "shaman", "specKey": "elemental", "productPhase": "retail"},
            credentials_loader=lambda: {"configured": True, "mode": "v2_oauth", "api": "warcraftlogs-v2-graphql"},
            target_loader=lambda: {
                "encounterId": 99,
                "partition": 42,
                "seasonLabel": "Configured current Mythic+ season",
            },
            graphql_loader=lambda _query, variables, **_ignored: {
                "worldData": {
                    "encounter": {
                        "id": variables["encounterId"],
                        "name": "Test Dungeon",
                        "characterRankings": {
                            "rankings": [
                                {"name": "MUST_NOT_ESCAPE", "amount": 12345},
                                {"name": "ALSO_MUST_NOT_ESCAPE", "amount": 12000},
                            ]
                        },
                    }
                }
            },
        )

        self.assertEqual("warcraftlogs_public_rankings", result["sourceKey"])
        self.assertEqual("source_reference", result["status"])
        self.assertEqual(["wcl.public.shaman.elemental.mythic_plus"], result["evidenceRefs"])
        fact = result["facts"][0]
        self.assertEqual("dps", fact["metric"])
        self.assertEqual(2, fact["sampleCount"])
        self.assertIn("2", result["allowedNumbers"])
        self.assertIn("checkedAt", result["evidence"][0])
        self.assertEqual("Configured current Mythic+ season", result["evidence"][0]["seasonLabel"])
        self.assertNotIn("MUST_NOT_ESCAPE", str(result))

    def test_public_wcl_rankings_use_a_bounded_network_timeout(self):
        module = importlib.import_module("server.chickenbro_community_strength")
        captured = {}

        def graphql_loader(_query, variables, timeout_seconds=None):
            captured["timeoutSeconds"] = timeout_seconds
            return {
                "worldData": {
                    "encounter": {
                        "id": variables["encounterId"],
                        "name": "Test Dungeon",
                        "characterRankings": {"rankings": [{"amount": 12345}]},
                    }
                }
            }

        result = module.build_wcl_public_rankings_tool_result(
            {"classKey": "shaman", "specKey": "elemental", "productPhase": "retail"},
            credentials_loader=lambda: {"configured": True, "mode": "v2_oauth", "api": "warcraftlogs-v2-graphql"},
            target_loader=lambda: {"encounterId": 99, "partition": 42, "seasonLabel": "Configured current Mythic+ season"},
            graphql_loader=graphql_loader,
        )

        self.assertEqual("source_reference", result["status"])
        self.assertEqual(8, captured["timeoutSeconds"])

    def test_public_wcl_does_not_query_without_a_verified_current_mplus_target_contract(self):
        module = importlib.import_module("server.chickenbro_community_strength")
        result = module.build_wcl_public_rankings_tool_result(
            {"classKey": "shaman", "specKey": "elemental", "productPhase": "retail", "scenarioKey": "mythic_plus"},
            credentials_loader=lambda: {"configured": True, "mode": "v2_oauth", "api": "warcraftlogs-v2-graphql"},
            target_loader=lambda: None,
            graphql_loader=lambda *_args, **_kwargs: self.fail("unconfigured target must not reach WCL GraphQL"),
        )

        self.assertEqual("partial", result["status"])
        self.assertEqual([], result["evidenceRefs"])
        self.assertIn("target contract", result["limitations"][0].lower())

    def test_public_wcl_reuses_a_short_result_cache_and_rate_limits_distinct_requests(self):
        module = importlib.import_module("server.chickenbro_community_strength")
        calls = []
        target = {"encounterId": 99, "partition": 42, "seasonLabel": "Configured current Mythic+ season"}

        def graphql_loader(_query, variables, **_kwargs):
            calls.append(variables["encounterId"])
            return {
                "worldData": {
                    "encounter": {
                        "id": variables["encounterId"],
                        "name": "Test Dungeon",
                        "characterRankings": {"rankings": [{"amount": 12345}]},
                    }
                }
            }

        common = {
            "credentials_loader": lambda: {"configured": True, "api": "warcraftlogs-v2-graphql"},
            "graphql_loader": graphql_loader,
            "clock": lambda: 100.0,
        }
        first = module.build_wcl_public_rankings_tool_result(
            {"classKey": "shaman", "specKey": "elemental", "scenarioKey": "mythic_plus"},
            target_loader=lambda: target,
            **common,
        )
        second = module.build_wcl_public_rankings_tool_result(
            {"classKey": "shaman", "specKey": "elemental", "scenarioKey": "mythic_plus"},
            target_loader=lambda: target,
            **common,
        )
        self.assertEqual("source_reference", first["status"])
        self.assertEqual("source_reference", second["status"])
        self.assertEqual([99], calls)

        for encounter_id in range(100, 111):
            result = module.build_wcl_public_rankings_tool_result(
                {"classKey": "shaman", "specKey": "elemental", "scenarioKey": "mythic_plus"},
                target_loader=lambda encounter_id=encounter_id: {
                    "encounterId": encounter_id,
                    "partition": 42,
                    "seasonLabel": f"Configured current Mythic+ season {encounter_id}",
                },
                **common,
            )
            self.assertEqual("source_reference", result["status"])
        limited = module.build_wcl_public_rankings_tool_result(
            {"classKey": "shaman", "specKey": "elemental", "scenarioKey": "mythic_plus"},
            target_loader=lambda: {"encounterId": 999, "partition": 42, "seasonLabel": "Another configured season"},
            **common,
        )

        self.assertEqual("partial", limited["status"])
        self.assertIn("rate budget", limited["limitations"][0].lower())
        self.assertEqual(12, len(calls))


if __name__ == "__main__":
    unittest.main()
