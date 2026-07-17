#!/usr/bin/env python3
import json
import unittest
from pathlib import Path

from server import gear_attribute_rules


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "gear-attribute-rulebook-v1.json"
ARMORY_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "gear-attribute-armory-v1.json"


def fixture_rulebook():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def verified_rulebook():
    rulebook = fixture_rulebook()
    context = rulebook["contexts"][0]
    context["status"] = "verified"
    context["sourceRefs"] = ["test:verified-source"]
    context["goldenSampleIds"] = ["test:mage-frost-human"]
    return rulebook


def armory_samples():
    return json.loads(ARMORY_FIXTURE_PATH.read_text(encoding="utf-8"))


class GearAttributeRulesTest(unittest.TestCase):
    def test_candidate_armory_samples_cannot_satisfy_verified_rule_publication(self):
        samples, sample_issues = gear_attribute_rules.validate_armory_golden_samples(armory_samples())
        self.assertEqual(sample_issues, [])
        candidate = next(sample for sample in samples["samples"] if sample["status"] == "candidate")
        rulebook = verified_rulebook()
        rulebook["contexts"][0]["goldenSampleIds"] = [candidate["id"]]

        parsed, issues = gear_attribute_rules.validate_attribute_rulebook(
            rulebook,
            golden_samples=samples,
        )

        self.assertIsNone(parsed)
        self.assertTrue(any(issue["code"] == "UNVERIFIED_GOLDEN_SAMPLE" for issue in issues))

    def test_not_found_armory_source_cannot_be_promoted_to_verified(self):
        samples = armory_samples()
        unavailable = next(sample for sample in samples["samples"] if sample["source"]["captureStatus"] == "not_found")
        unavailable["status"] = "verified"
        unavailable["missingEvidence"] = []

        parsed, issues = gear_attribute_rules.validate_armory_golden_samples(samples)

        self.assertIsNone(parsed)
        self.assertTrue(any(issue["code"] == "VERIFIED_SAMPLE_NOT_CAPTURED" for issue in issues))

    def test_incomplete_armory_equipment_cannot_be_promoted_to_verified(self):
        samples = armory_samples()
        partial = next(sample for sample in samples["samples"] if sample["source"]["captureStatus"] == "captured")
        partial["status"] = "verified"
        partial["missingEvidence"] = []

        parsed, issues = gear_attribute_rules.validate_armory_golden_samples(samples)

        self.assertIsNone(parsed)
        self.assertTrue(any(issue["code"] == "VERIFIED_SAMPLE_INCOMPLETE_EQUIPMENT" for issue in issues))

    def test_candidate_accepts_declared_official_profile_evidence(self):
        samples = armory_samples()
        candidate = next(sample for sample in samples["samples"] if sample["source"]["captureStatus"] == "captured")
        candidate["evidence"] = {
            "officialProfileApi": {
                "url": "https://eu.api.blizzard.com/profile/wow/character/blackrock/heated?namespace=profile-eu&locale=en_GB",
                "capturedAt": "2026-07-17T04:43:43Z",
                "credentialHandling": "read-only server-side OAuth; no token persisted",
            },
            "officialProfileSnapshot": {
                "capturedAt": "2026-07-17T04:43:43Z",
                "canonicalEquipmentCount": 15,
                "instances": [],
            },
        }

        parsed, issues = gear_attribute_rules.validate_armory_golden_samples(samples)

        self.assertEqual(issues, [])
        self.assertEqual(parsed["samples"][0]["evidence"]["officialProfileSnapshot"]["canonicalEquipmentCount"], 15)

    def test_unknown_sample_field_does_not_hide_verified_equipment_failure(self):
        samples = armory_samples()
        partial = next(sample for sample in samples["samples"] if sample["source"]["captureStatus"] == "captured")
        partial["status"] = "verified"
        partial["missingEvidence"] = []
        partial["unexpected"] = True

        parsed, issues = gear_attribute_rules.validate_armory_golden_samples(samples)

        self.assertIsNone(parsed)
        self.assertTrue(any(issue["code"] == "UNKNOWN_FIELD" for issue in issues))
        self.assertTrue(any(issue["code"] == "VERIFIED_SAMPLE_INCOMPLETE_EQUIPMENT" for issue in issues))

    def test_public_context_excludes_unverified_rulebook_context(self):
        context = gear_attribute_rules.public_attribute_calculator_context(
            fixture_rulebook(), class_key="mage", spec_key="frost", level=90
        )

        self.assertEqual(context["status"], "rule_unavailable")
        self.assertEqual(context["problems"][0]["code"], "ATTRIBUTE_RULE_UNAVAILABLE")
        self.assertEqual(context["raceOptions"], [])
        self.assertEqual(context["rules"], [])

    def test_character_context_accepts_only_explicit_race_key(self):
        parsed, issues = gear_attribute_rules.parse_attribute_character_context(
            {"schemaRevision": "gear-attribute-character-v1", "raceKey": "human"}
        )

        self.assertEqual(issues, [])
        self.assertEqual(
            parsed,
            {"schemaRevision": "gear-attribute-character-v1", "raceKey": "human"},
        )

    def test_character_context_rejects_unknown_empty_and_noncanonical_fields(self):
        vectors = (
            ({"schemaRevision": "gear-attribute-character-v1", "raceKey": ""}, "INVALID_RACE_KEY"),
            ({"schemaRevision": "gear-attribute-character-v1", "raceKey": "Human"}, "INVALID_RACE_KEY"),
            ({"schemaRevision": "gear-attribute-character-v1", "raceKey": "human", "stats": {}}, "UNKNOWN_FIELD"),
            ({"raceKey": "human"}, "MISSING_SCHEMA_REVISION"),
        )

        for raw, expected_code in vectors:
            with self.subTest(raw=raw):
                parsed, issues = gear_attribute_rules.parse_attribute_character_context(raw)
                self.assertIsNone(parsed)
                self.assertTrue(any(issue["code"] == expected_code for issue in issues))

    def test_rulebook_rejects_missing_sources_or_verified_golden_sample(self):
        missing_sources = verified_rulebook()
        missing_sources["contexts"][0]["sourceRefs"] = []
        parsed, issues = gear_attribute_rules.validate_attribute_rulebook(missing_sources)
        self.assertIsNone(parsed)
        self.assertTrue(any(issue["code"] == "MISSING_SOURCE_REFS" for issue in issues))

        missing_golden = verified_rulebook()
        missing_golden["contexts"][0]["goldenSampleIds"] = []
        parsed, issues = gear_attribute_rules.validate_attribute_rulebook(missing_golden)
        self.assertIsNone(parsed)
        self.assertTrue(any(issue["code"] == "MISSING_GOLDEN_SAMPLE" for issue in issues))

    def test_rulebook_rejects_duplicate_secondary_output_keys(self):
        duplicate = fixture_rulebook()
        duplicate["contexts"][0]["secondaryRules"][1]["outputKey"] = "crit"

        parsed, issues = gear_attribute_rules.validate_attribute_rulebook(duplicate)

        self.assertIsNone(parsed)
        self.assertTrue(any(issue["code"] == "DUPLICATE_OUTPUT_KEY" for issue in issues))

    def test_verified_rule_lookup_rejects_unknown_race(self):
        rule, issues = gear_attribute_rules.applicable_attribute_rule(
            verified_rulebook(), class_key="mage", spec_key="frost", level=90, race_key="orc"
        )

        self.assertIsNone(rule)
        self.assertEqual(issues[0]["code"], "ATTRIBUTE_RULE_UNAVAILABLE")

    def test_confirmed_audit_finding_blocks_only_future_rule_promotion_validation(self):
        rulebook = verified_rulebook()

        parsed, issues = gear_attribute_rules.validate_attribute_rulebook(
            rulebook,
            promotion_findings_reader=lambda revision: [{
                "attributeRuleRevision": revision,
                "contextKey": "mage:frost:90:human",
            }],
        )
        public_rule, public_issues = gear_attribute_rules.applicable_attribute_rule(
            rulebook, class_key="mage", spec_key="frost", level=90, race_key="human"
        )

        self.assertIsNone(parsed)
        self.assertTrue(any(issue["code"] == "ATTRIBUTE_RULE_AUDIT_MISMATCH_BLOCKS_PROMOTION" for issue in issues))
        self.assertEqual(public_issues, [])
        self.assertEqual(public_rule["attributeRuleRevision"], "fixture-r1")

    def test_verified_public_context_keeps_provenance_and_strips_implementation_notes(self):
        rulebook = verified_rulebook()
        public = gear_attribute_rules.public_attribute_calculator_context(
            rulebook, class_key="mage", spec_key="frost", level=90
        )

        self.assertEqual(public["status"], "available")
        self.assertEqual(public["attributeRuleRevision"], "fixture-r1")
        self.assertEqual(public["raceOptions"], [{"raceKey": "human"}])
        self.assertEqual(public["rules"][0]["attributeRuleRevision"], "fixture-r1")
        self.assertEqual(public["rules"][0]["sourceRefs"], ["test:verified-source"])
        self.assertEqual(public["rules"][0]["goldenSampleIds"], ["test:mage-frost-human"])
        self.assertNotIn("implementationNotes", public["rules"][0])

        rule, issues = gear_attribute_rules.applicable_attribute_rule(
            rulebook, class_key="mage", spec_key="frost", level=90, race_key="human"
        )
        self.assertEqual(issues, [])
        self.assertEqual(rule["contextKey"], "mage:frost:90:human")


if __name__ == "__main__":
    unittest.main()
