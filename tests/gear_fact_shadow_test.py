#!/usr/bin/env python3
import unittest


class GearFactShadowTest(unittest.TestCase):
    def test_shadow_classifies_exhaustive_allowed_categories(self):
        from server.gear_fact_shadow import compare_legacy_and_canonical

        legacy = {
            "items": [
                {
                    "itemId": "250033",
                    "slot": "head",
                    "payload": {
                        "hasSocket": False,
                        "baseCapabilities": {"socketCount": 1},
                    },
                },
                {
                    "itemId": "item-gap",
                    "slot": "neck",
                    "payload": {"baseCapabilities": {"socketCount": 1}},
                },
                {
                    "itemId": "item-regression",
                    "slot": "wrist",
                    "payload": {"baseCapabilities": {"socketCount": 1}},
                },
            ],
            "variants": [],
            "options": [],
        }
        facts = [
            self.fact("item:250033", "item_identity", {"itemId": "250033"}),
            self.fact("item:250033", "socket_count", 1),
            self.fact(
                "item:item-gap",
                "socket_count",
                None,
                status="unresolved_missing",
            ),
            self.fact("item:item-regression", "socket_count", 2),
        ]

        result = compare_legacy_and_canonical(legacy, facts)

        categories = [row["classification"] for row in result["comparisons"]]
        self.assertEqual(
            set(categories),
            {
                "exact_parity",
                "intended_correction",
                "newly_exposed_gap",
                "regression",
            },
        )
        self.assertEqual(result["status"], "blocked")
        correction = next(
            row
            for row in result["comparisons"]
            if row["classification"] == "intended_correction"
        )
        self.assertEqual(correction["subjectKey"], "item:250033")
        self.assertEqual(correction["legacyValue"], False)
        self.assertEqual(correction["canonicalValue"], 1)

    def test_unclassified_or_regression_blocks_candidate(self):
        from server.gear_fact_shadow import compare_legacy_and_canonical

        unclassified = compare_legacy_and_canonical(
            {"items": [], "variants": [], "options": []},
            [self.fact("item:1", "unsupported_fact", "value")],
        )
        self.assertEqual(unclassified["status"], "blocked")
        self.assertEqual(unclassified["blockers"][0]["code"], "UNCLASSIFIED_FACT_DIFFERENCE")

        regression = compare_legacy_and_canonical(
            {
                "items": [
                    {
                        "itemId": "1",
                        "payload": {"baseCapabilities": {"socketCount": 1}},
                    }
                ],
                "variants": [],
                "options": [],
            },
            [self.fact("item:1", "socket_count", 2)],
        )
        self.assertEqual(regression["status"], "blocked")
        self.assertEqual(regression["blockers"][0]["code"], "CANONICAL_FACT_REGRESSION")

    def test_unknown_unresolved_fact_is_not_promoted_to_new_gap_classification(self):
        from server.gear_fact_shadow import compare_legacy_and_canonical

        result = compare_legacy_and_canonical(
            {"items": [], "variants": [], "options": []},
            [
                self.fact(
                    "item:1",
                    "unsupported_fact",
                    None,
                    status="unresolved_missing",
                )
            ],
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(
            result["blockers"][0]["code"],
            "UNCLASSIFIED_FACT_DIFFERENCE",
        )

    def test_known_250033_correction_accepts_top_level_browse_flag(self):
        from server.gear_fact_shadow import compare_legacy_and_canonical

        result = compare_legacy_and_canonical(
            {
                "items": [
                    {
                        "itemId": "250033",
                        "hasSocket": False,
                        "payload": {
                            "baseCapabilities": {"socketCount": 1},
                        },
                    }
                ],
                "variants": [],
                "options": [],
            },
            [self.fact("item:250033", "socket_count", 1)],
        )

        self.assertEqual(result["status"], "pass")
        self.assertEqual(
            result["comparisons"][0]["classification"],
            "intended_correction",
        )

    def test_known_250033_correction_applies_to_exact_variant_subject(self):
        from server.gear_fact_shadow import compare_legacy_and_canonical

        result = compare_legacy_and_canonical(
            {
                "items": [],
                "variants": [
                    {
                        "variantId": "variant-250033",
                        "itemId": "250033",
                        "variantKey": "void-upgrade",
                        "hasSocket": False,
                        "payload": {
                            "capabilityOverrides": {"socketCount": 1},
                        },
                    }
                ],
                "options": [],
            },
            [
                self.fact(
                    "item:250033/variant:void-upgrade",
                    "socket_count",
                    1,
                )
            ],
        )

        self.assertEqual(result["status"], "pass")
        self.assertEqual(
            result["comparisons"][0]["classification"],
            "intended_correction",
        )

    def test_missing_or_duplicate_expected_fact_blocks(self):
        from server.gear_fact_shadow import compare_legacy_and_canonical

        missing = compare_legacy_and_canonical(
            {"items": [], "variants": [], "options": []},
            [],
            expected_fact_types_by_subject={
                "item:1": ["socket_count"],
            },
        )
        self.assertEqual(missing["status"], "blocked")

        fact = self.fact(
            "item:1",
            "socket_count",
            None,
            status="unresolved_missing",
        )
        duplicate = compare_legacy_and_canonical(
            {"items": [], "variants": [], "options": []},
            [fact, dict(fact)],
            expected_fact_types_by_subject={
                "item:1": ["socket_count"],
            },
        )
        self.assertEqual(duplicate["status"], "blocked")
        self.assertEqual(
            duplicate["blockers"][0]["code"],
            "UNCLASSIFIED_FACT_DIFFERENCE",
        )

    @staticmethod
    def fact(subject_key, fact_type, value, *, status="verified"):
        return {
            "factKey": f"fact:{subject_key}:{fact_type}",
            "subjectKey": subject_key,
            "factType": fact_type,
            "value": value,
            "status": status,
            "factValueHash": "sha256:" + ("a" * 64),
            "provenanceHash": "sha256:" + ("b" * 64),
            "compilerRuleRevision": "test-policy-v1",
            "observationRefs": [],
        }


if __name__ == "__main__":
    unittest.main()
