#!/usr/bin/env python3
import copy
import json
import unittest
from pathlib import Path

from server.gear_attribute_engine import calculate_noncombat_attributes


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "gear-attribute-calculator-cases-v1.json"


def fixture_cases():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["cases"]


class GearAttributeEngineTest(unittest.TestCase):
    def test_calculates_every_shared_fixture_case(self):
        for fixture in fixture_cases():
            with self.subTest(case=fixture["id"]):
                result = calculate_noncombat_attributes(
                    fixture["rule"],
                    fixture["characterContext"],
                    fixture["staticAttributes"],
                    fixture["stableEffects"],
                )
                self.assertEqual(result, fixture["expected"])

    def test_modifier_order_is_declared_by_rule_not_effect_input_order(self):
        fixture = fixture_cases()[0]
        rule = copy.deepcopy(fixture["rule"])
        rule["stableModifiers"] = [
            {"effectId": "fixture:add", "targetKey": "intellect", "operation": "add", "value": 10},
            {"effectId": "fixture:multiply", "targetKey": "intellect", "operation": "multiply", "value": 2},
        ]
        effects = [{"effectId": "fixture:multiply"}, {"effectId": "fixture:add"}]

        declared_order = calculate_noncombat_attributes(
            rule, fixture["characterContext"], fixture["staticAttributes"], effects
        )
        rule["stableModifiers"].reverse()
        reversed_order = calculate_noncombat_attributes(
            rule, fixture["characterContext"], fixture["staticAttributes"], effects
        )

        self.assertEqual(declared_order["primary"]["rawValue"], 3020)
        self.assertEqual(reversed_order["primary"]["rawValue"], 3010)

    def test_post_conversion_modifier_order_is_declared_by_rule_not_effect_input_order(self):
        fixture = fixture_cases()[0]
        rule = copy.deepcopy(fixture["rule"])
        rule["secondaryRules"] = [{
            "inputKey": "haste_rating",
            "outputKey": "haste",
            "label": "急速",
            "basePercent": 10,
            "ratingPerPercent": 50,
            "postConversionModifiers": [
                {"effectId": "fixture:haste-add", "operation": "add", "value": 2},
                {"effectId": "fixture:haste-multiply", "operation": "multiply", "value": 1.05},
            ],
            "precision": 1,
            "sourceRefs": ["fixture:post-conversion-order"],
            "displayUnit": "percent",
        }]
        effects = [{"effectId": "fixture:haste-multiply"}, {"effectId": "fixture:haste-add"}]

        declared_order = calculate_noncombat_attributes(
            rule, fixture["characterContext"], {"haste_rating": 100}, effects
        )
        rule["secondaryRules"][0]["postConversionModifiers"].reverse()
        reversed_order = calculate_noncombat_attributes(
            rule, fixture["characterContext"], {"haste_rating": 100}, effects
        )

        self.assertEqual(declared_order["secondary"][0]["convertedValue"], "14.7%")
        self.assertEqual(reversed_order["secondary"][0]["convertedValue"], "14.6%")

    def test_zero_rating_is_visible_and_unknown_stable_effect_is_conditional(self):
        fixture = fixture_cases()[0]
        attributes = {**fixture["staticAttributes"], "mastery_rating": 0}
        result = calculate_noncombat_attributes(
            fixture["rule"],
            fixture["characterContext"],
            attributes,
            [{"effectId": "fixture:not-allowed"}],
        )

        mastery = next(row for row in result["secondary"] if row["key"] == "mastery")
        self.assertEqual(mastery["rawValue"], 0)
        self.assertEqual(mastery["convertedValue"], "8.0%")
        self.assertEqual(
            result["conditionals"],
            [{"effectId": "fixture:not-allowed", "included": False, "reason": "UNSUPPORTED_STABLE_EFFECT"}],
        )

    def test_piecewise_curve_matches_official_frost_avoidance_sample(self):
        fixture = fixture_cases()[0]
        rule = copy.deepcopy(fixture["rule"])
        rule["secondaryRules"] = [{
            "inputKey": "avoidance_rating",
            "outputKey": "avoidance",
            "label": "闪避",
            "basePercent": 0,
            "ratingTransform": {
                "kind": "piecewise_linear",
                "ratingPerPercent": 36.80052531,
                "points": [
                    {"input": 0, "output": 0},
                    {"input": 0.5, "output": 0.5},
                    {"input": 10, "output": 10},
                    {"input": 15, "output": 14},
                    {"input": 20, "output": 17},
                    {"input": 25, "output": 19},
                    {"input": 100, "output": 49},
                ],
                "outOfRange": "clamp",
            },
            "precision": 6,
            "sourceRefs": ["simc:dbc:curve:21025"],
            "displayUnit": "percent",
        }]

        result = calculate_noncombat_attributes(
            rule,
            fixture["characterContext"],
            {"avoidance_rating": 470},
            [],
        )

        self.assertEqual(result["status"], "calculated")
        self.assertEqual(result["secondary"], [{
            "key": "avoidance",
            "label": "闪避",
            "rawValue": 470,
            "value": "470",
            "convertedValue": "12.217245%",
            "displayUnit": "percent",
        }])

    def test_invalid_conversion_or_missing_rule_has_no_numeric_final_panel(self):
        fixture = fixture_cases()[0]
        invalid_rule = copy.deepcopy(fixture["rule"])
        invalid_rule["secondaryRules"][0]["ratingPerPercent"] = 0
        invalid = calculate_noncombat_attributes(
            invalid_rule,
            fixture["characterContext"],
            fixture["staticAttributes"],
            fixture["stableEffects"],
        )
        missing = calculate_noncombat_attributes(
            None,
            fixture["characterContext"],
            fixture["staticAttributes"],
            fixture["stableEffects"],
        )

        self.assertEqual(invalid["status"], "rule_unavailable")
        self.assertEqual(invalid["problems"][0]["code"], "INVALID_RATING_CONVERSION")
        self.assertIsNone(invalid["primary"])
        self.assertEqual(invalid["secondary"], [])
        self.assertEqual(missing["status"], "rule_unavailable")
        self.assertIsNone(missing["primary"])

    def test_input_signature_changes_for_race_static_modifiers_and_rule_revision(self):
        fixture = fixture_cases()[0]
        baseline = calculate_noncombat_attributes(
            fixture["rule"],
            fixture["characterContext"],
            fixture["staticAttributes"],
            fixture["stableEffects"],
        )
        elf_rule = copy.deepcopy(fixture["rule"])
        elf_rule.update({"contextKey": "mage:frost:90:elf", "raceKey": "elf"})
        changed_race = calculate_noncombat_attributes(
            elf_rule, {"raceKey": "elf"}, fixture["staticAttributes"], fixture["stableEffects"]
        )
        changed_static = calculate_noncombat_attributes(
            fixture["rule"],
            fixture["characterContext"],
            {**fixture["staticAttributes"], "haste_rating": 101},
            fixture["stableEffects"],
        )
        changed_modifier_rule = copy.deepcopy(fixture["rule"])
        changed_modifier_rule["stableModifiers"] = [
            {"effectId": "fixture:add", "targetKey": "intellect", "operation": "add", "value": 1}
        ]
        changed_modifier = calculate_noncombat_attributes(
            changed_modifier_rule,
            fixture["characterContext"],
            fixture["staticAttributes"],
            [{"effectId": "fixture:add"}],
        )
        changed_revision_rule = copy.deepcopy(fixture["rule"])
        changed_revision_rule["attributeRuleRevision"] = "fixture-r2"
        changed_revision = calculate_noncombat_attributes(
            changed_revision_rule,
            fixture["characterContext"],
            fixture["staticAttributes"],
            fixture["stableEffects"],
        )
        changed_conversion_rule = copy.deepcopy(fixture["rule"])
        changed_conversion_rule["secondaryRules"][0]["ratingPerPercent"] = 36
        changed_conversion = calculate_noncombat_attributes(
            changed_conversion_rule,
            fixture["characterContext"],
            fixture["staticAttributes"],
            fixture["stableEffects"],
        )

        baseline_signature = baseline["inputSignature"]
        self.assertNotEqual(baseline_signature, changed_race["inputSignature"])
        self.assertNotEqual(baseline_signature, changed_static["inputSignature"])
        self.assertNotEqual(baseline_signature, changed_modifier["inputSignature"])
        self.assertNotEqual(baseline_signature, changed_revision["inputSignature"])
        self.assertNotEqual(baseline_signature, changed_conversion["inputSignature"])


if __name__ == "__main__":
    unittest.main()
