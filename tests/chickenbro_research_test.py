import unittest


def catalog_tool(tool_id, required=None, **overrides):
    tool = {
        "toolId": tool_id,
        "purpose": f"Use {tool_id} for bounded evidence.",
        "inputSchema": {"required": list(required or [])},
        "outputSchema": {"schemaRevision": "chickenbro-tool-result-v1"},
        "riskClass": "read_only",
        "ownerPolicy": "public_source",
        "sourcePolicy": {"sourceKey": tool_id.split(":")[1]},
        "freshnessPolicy": {"maxAgeSeconds": 60},
        "costBudget": {"status": "bounded"},
        "timeoutBudgetMs": 1000,
    }
    tool.update(overrides)
    return tool


def plan_with(tool_id, arguments=None, *, decision="continue"):
    return {
        "schemaRevision": "chickenbro-research-plan-v1",
        "goal": "比较当前可验证的表现",
        "hypotheses": ["来源可能覆盖不同维度"],
        "informationGaps": ["是否有同口径样本"],
        "toolCalls": [{"toolId": tool_id, "arguments": arguments or {}}],
        "decision": decision,
    }


class ChickenbroResearchTest(unittest.TestCase):
    def _module(self):
        try:
            from server import chickenbro_research
        except ImportError as error:
            self.fail(f"ResearchPlan module must exist: {error}")
        return chickenbro_research

    def test_valid_plan_can_select_two_published_tools_without_question_labels(self):
        module = self._module()
        catalog = [
            catalog_tool("source:official:v1", ["productPhase"]),
            catalog_tool("source:community:v1", ["scenarioKey"]),
        ]

        plan = module.validate_research_plan(
            {
                "schemaRevision": "chickenbro-research-plan-v1",
                "goal": "比较当前可验证的表现",
                "hypotheses": ["来源可能覆盖不同维度"],
                "informationGaps": ["是否有同口径样本"],
                "toolCalls": [
                    {"toolId": "source:official:v1", "arguments": {"productPhase": "ptr"}},
                    {"toolId": "source:community:v1", "arguments": {"scenarioKey": "mythic_plus"}},
                ],
                "decision": "continue",
            },
            catalog,
        )

        self.assertEqual("chickenbro-research-plan-v1", plan["schemaRevision"])
        self.assertEqual("continue", plan["decision"])
        self.assertEqual(
            ["source:official:v1", "source:community:v1"],
            [call["toolId"] for call in plan["toolCalls"]],
        )

    def test_codex_strict_schema_uses_closed_argument_entries_and_normalizes_them(self):
        module = self._module()
        schema = module.research_plan_schema()
        arguments = schema["properties"]["toolCalls"]["items"]["properties"]["arguments"]

        self.assertEqual("array", arguments["type"])
        self.assertEqual(False, arguments["items"]["additionalProperties"])
        self.assertEqual(["name", "value"], arguments["items"]["required"])

        plan = module.validate_research_plan(
            {
                **plan_with("source:official:v1", decision="answer"),
                "toolCalls": [{
                    "toolId": "source:official:v1",
                    "arguments": [{"name": "productPhase", "value": "ptr"}],
                }],
            },
            [catalog_tool("source:official:v1", ["productPhase"])],
        )

        self.assertEqual({"productPhase": "ptr"}, plan["toolCalls"][0]["arguments"])

    def test_plan_rejects_unpublished_tool_and_unsafe_argument(self):
        module = self._module()
        catalog = [catalog_tool("source:official:v1", ["productPhase"])]

        with self.assertRaisesRegex(ValueError, "published tool"):
            module.validate_research_plan(plan_with("https://example.invalid"), catalog)
        with self.assertRaisesRegex(ValueError, "unsafe research argument"):
            module.validate_research_plan(
                plan_with("source:official:v1", {"url": "file:///etc/passwd"}),
                catalog,
            )

    def test_plan_rejects_duplicate_tool_or_more_than_three_calls(self):
        module = self._module()
        catalog = [catalog_tool(f"source:tool-{index}:v1") for index in range(4)]
        duplicate = plan_with("source:tool-0:v1")
        duplicate["toolCalls"].append({"toolId": "source:tool-0:v1", "arguments": {}})
        with self.assertRaisesRegex(ValueError, "duplicate"):
            module.validate_research_plan(duplicate, catalog)

        oversized = plan_with("source:tool-0:v1")
        oversized["toolCalls"] = [
            {"toolId": f"source:tool-{index}:v1", "arguments": {}}
            for index in range(4)
        ]
        with self.assertRaisesRegex(ValueError, "tool call budget"):
            module.validate_research_plan(oversized, catalog)

    def test_plan_requires_an_answer_decision_when_no_tool_is_requested(self):
        module = self._module()
        empty = plan_with("source:official:v1")
        empty["toolCalls"] = []
        with self.assertRaisesRegex(ValueError, "empty tool calls"):
            module.validate_research_plan(empty, [catalog_tool("source:official:v1")])

        empty["decision"] = "answer"
        plan = module.validate_research_plan(empty, [catalog_tool("source:official:v1")])
        self.assertEqual([], plan["toolCalls"])

    def test_observations_strip_raw_tool_execution_details(self):
        module = self._module()
        observations = module.observations_from_tool_results(
            [{"toolId": "source:official:v1", "arguments": {"productPhase": "ptr"}}],
            [{
                "sourceKey": "official",
                "status": "source_reference",
                "facts": [{"summary": "Only a bounded summary", "scenarioKey": "mythic_plus"}],
                "evidenceRefs": ["official.ref"],
                "limitations": ["fixture limitation"],
                "rawBody": "must never be retained",
            }],
        )

        self.assertEqual("source:official:v1", observations[0]["toolId"])
        self.assertEqual(["official.ref"], observations[0]["evidenceRefs"])
        self.assertNotIn("rawBody", observations[0])
        self.assertNotIn("productPhase", str(observations[0].get("arguments")))


if __name__ == "__main__":
    unittest.main()
