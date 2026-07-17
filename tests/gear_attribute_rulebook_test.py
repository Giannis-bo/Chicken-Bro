#!/usr/bin/env python3
import json
import unittest
from pathlib import Path

from server.gear_attribute_engine import calculate_noncombat_attributes
from server.gear_attribute_rulebook import ACTIVE_ATTRIBUTE_RULEBOOK
from server.gear_attribute_rules import (
    applicable_attribute_rule,
    public_attribute_calculator_context,
    validate_armory_golden_samples,
    validate_attribute_rulebook,
)


ARMORY_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "gear-attribute-armory-v1.json"
OFFICIAL_CASES_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "gear-attribute-official-cases-v1.json"


class GearAttributeRulebookTest(unittest.TestCase):
    def test_active_rulebook_reproduces_each_released_official_attribute_case(self):
        fixtures = json.loads(OFFICIAL_CASES_FIXTURE_PATH.read_text(encoding="utf-8"))["cases"]
        for fixture in fixtures:
            with self.subTest(case=fixture["id"]):
                rule, issues = applicable_attribute_rule(
                    ACTIVE_ATTRIBUTE_RULEBOOK,
                    class_key="mage",
                    spec_key=fixture["rule"]["specKey"],
                    level=90,
                    race_key=fixture["characterContext"]["raceKey"],
                )
                self.assertEqual(issues, [])
                self.assertEqual(
                    calculate_noncombat_attributes(
                        rule,
                        fixture["characterContext"],
                        fixture["staticAttributes"],
                        fixture["stableEffects"],
                    ),
                    fixture["expectedCalculation"],
                )

    def test_active_mage_rulebook_has_verified_golden_samples_and_public_contexts(self):
        armory_samples, sample_issues = validate_armory_golden_samples(
            json.loads(ARMORY_FIXTURE_PATH.read_text(encoding="utf-8"))
        )
        self.assertEqual(sample_issues, [])

        rulebook, rule_issues = validate_attribute_rulebook(
            ACTIVE_ATTRIBUTE_RULEBOOK,
            golden_samples=armory_samples,
        )
        self.assertEqual(rule_issues, [])

        frost = public_attribute_calculator_context(
            rulebook, class_key="mage", spec_key="frost", level=90
        )
        arcane = public_attribute_calculator_context(
            rulebook, class_key="mage", spec_key="arcane", level=90
        )
        self.assertEqual(frost["status"], "available")
        self.assertEqual(arcane["status"], "available")
        self.assertEqual(frost["raceOptions"], [{"raceKey": "dwarf"}])
        self.assertEqual(arcane["raceOptions"], [{"raceKey": "night_elf"}])

        frost_rule, frost_issues = applicable_attribute_rule(
            rulebook, class_key="mage", spec_key="frost", level=90, race_key="dwarf"
        )
        arcane_rule, arcane_issues = applicable_attribute_rule(
            rulebook, class_key="mage", spec_key="arcane", level=90, race_key="night_elf"
        )
        self.assertEqual(frost_issues, [])
        self.assertEqual(arcane_issues, [])
        self.assertEqual(frost_rule["attributeRuleRevision"], "midnight-mage-attributes-r1")
        self.assertEqual(arcane_rule["attributeRuleRevision"], "midnight-mage-attributes-r1")


if __name__ == "__main__":
    unittest.main()
