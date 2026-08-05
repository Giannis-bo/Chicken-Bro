import unittest

from server.chickenbro_question_frame import build_chickenbro_question_frame


class ChickenbroEvidencePlanTest(unittest.TestCase):
    def _builder(self):
        try:
            from server.chickenbro_evidence_plan import build_chickenbro_evidence_plan
        except ImportError as error:
            self.fail(f"EvidencePlan module must exist: {error}")
        return build_chickenbro_evidence_plan

    @staticmethod
    def _registry(*capability_ids):
        return {"selectedCapabilityIds": list(capability_ids)}

    @staticmethod
    def _source(source_key, status="source_reference", refs=None):
        return {
            "sourceKey": source_key,
            "status": status,
            "evidenceRefs": list(refs or [f"{source_key}:evidence"]),
        }

    def test_retail_mplus_subject_strength_uses_a_supported_high_key_facet(self):
        frame = build_chickenbro_question_frame("元素萨正式服现在版本大秘境强度如何？", [])

        plan = self._builder()(frame, self._registry("source:raiderio-strength:v1"), [
            self._source("raiderio_strength"),
        ])

        self.assertEqual("chickenbro-evidence-plan-v1", plan["schemaRevision"])
        self.assertEqual("subject", plan["comparisonScope"])
        self.assertEqual("answered", plan["outcome"])
        self.assertEqual("reuse_compatible_only", plan["continuationPolicy"])
        self.assertEqual(["source:raiderio-strength:v1"], plan["selectedCapabilityIds"])
        self.assertEqual([], plan["unmetEvidenceNeeds"])
        self.assertEqual("high_key_trend", plan["facets"][0]["key"])
        self.assertEqual("supported", plan["facets"][0]["status"])

    def test_ptr_change_fact_is_partial_when_comparative_strength_is_missing(self):
        frame = build_chickenbro_question_frame("NQ 在 12.1 PTR 强度如何？", [])

        plan = self._builder()(frame, self._registry("source:current-wow-sources:v1"), [
            self._source("current_wow_sources"),
        ])

        self.assertEqual("partial", plan["outcome"])
        self.assertEqual(["comparative_strength_signal"], plan["unmetEvidenceNeeds"])
        self.assertEqual("official_changes", plan["facets"][0]["key"])
        self.assertEqual("supported", plan["facets"][0]["status"])
        self.assertEqual("subject_performance", plan["facets"][1]["key"])
        self.assertEqual("unavailable", plan["facets"][1]["status"])

    def test_cross_spec_dps_plan_discards_subject_only_high_key_signal(self):
        frame = build_chickenbro_question_frame("现在版本大秘境全职业 DPS 横向排名如何？", [])

        plan = self._builder()(frame, self._registry("source:raiderio-strength:v1"), [
            self._source("raiderio_strength"),
        ])

        self.assertEqual("cross_spec", plan["comparisonScope"])
        self.assertEqual("partial", plan["outcome"])
        self.assertEqual("replan", plan["continuationPolicy"])
        self.assertEqual(["comparative_strength_signal"], plan["unmetEvidenceNeeds"])
        self.assertEqual("cross_spec_performance", plan["facets"][0]["key"])
        self.assertEqual("unavailable", plan["facets"][0]["status"])

    def test_raid_question_does_not_consume_mythic_plus_strength_evidence(self):
        frame = build_chickenbro_question_frame("元素萨正式服团本单体强度如何？", [])

        plan = self._builder()(frame, self._registry("source:raiderio-strength:v1"), [
            self._source("raiderio_strength"),
        ])

        self.assertEqual("partial", plan["outcome"])
        self.assertEqual("subject_performance", plan["facets"][0]["key"])
        self.assertEqual("raid", plan["facets"][0]["scenarioKey"])
        self.assertEqual("unavailable", plan["facets"][0]["status"])

    def test_malformed_inputs_return_a_safe_partial_plan_without_source_selection(self):
        plan = self._builder()(None, None, None)

        self.assertEqual("subject", plan["comparisonScope"])
        self.assertEqual("partial", plan["outcome"])
        self.assertEqual([], plan["facets"])
        self.assertEqual([], plan["selectedCapabilityIds"])
        self.assertEqual([], plan["unmetEvidenceNeeds"])


if __name__ == "__main__":
    unittest.main()
