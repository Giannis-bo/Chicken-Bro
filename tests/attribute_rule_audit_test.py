#!/usr/bin/env python3
import copy
import json
import unittest
from pathlib import Path

from server.attribute_rule_audit import (
    audit_key,
    build_winner_audit_intents,
    canonical_input_signature,
    compare_attribute_panel,
    match_official_profile,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "attribute-rule-audit-v1.json"


def fixture():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


class AttributeRuleAuditTest(unittest.TestCase):
    def test_changed_observed_winner_with_verified_rule_creates_one_fetchable_intent(self):
        data = fixture()

        intents = build_winner_audit_intents(
            active_winners=data["activeWinners"],
            candidate_rows=data["candidateRows"],
            candidate_context=data["candidateContext"],
            rulebook=data["verifiedRulebook"],
        )

        self.assertEqual(len(intents), 1)
        intent = intents[0]
        self.assertEqual(intent["status"], "pending")
        self.assertTrue(intent["externalFetchAllowed"])
        self.assertEqual(intent["attributeRuleRevision"], "fixture-audit-r1")
        self.assertTrue(intent["canonicalInputSignature"].startswith("sha256:"))
        self.assertTrue(intent["auditKey"].startswith("attribute-audit:sha256:"))
        self.assertEqual(intent["sourceIdentity"], {
            "region": "eu", "realmSlug": "blackrock", "characterName": "Fixturemage", "locale": "en_GB"
        })

    def test_same_active_winner_hash_does_not_create_an_audit_intent(self):
        data = fixture()
        data["candidateRows"][0]["profileHash"] = data["activeWinners"][0]["profileHash"]
        data["candidateRows"][0]["gearHash"] = data["activeWinners"][0]["gearHash"]

        intents = build_winner_audit_intents(
            active_winners=data["activeWinners"],
            candidate_rows=data["candidateRows"],
            candidate_context=data["candidateContext"],
            rulebook=data["verifiedRulebook"],
        )

        self.assertEqual(intents, [])

    def test_missing_evidence_and_fixture_only_rule_never_allow_external_fetch(self):
        data = fixture()
        missing_evidence = copy.deepcopy(data["candidateRows"])
        del missing_evidence[0]["evidence"]["attributeAudit"]["canonicalEquipment"][0]["enchantIds"]

        blocked = build_winner_audit_intents(
            active_winners=data["activeWinners"],
            candidate_rows=missing_evidence,
            candidate_context=data["candidateContext"],
            rulebook=data["verifiedRulebook"],
        )
        unavailable = build_winner_audit_intents(
            active_winners=data["activeWinners"],
            candidate_rows=data["candidateRows"],
            candidate_context=data["candidateContext"],
            rulebook=data["fixtureOnlyRulebook"],
        )

        self.assertEqual(blocked[0]["status"], "blocked_missing_evidence")
        self.assertFalse(blocked[0]["externalFetchAllowed"])
        self.assertEqual(unavailable[0]["status"], "not_applicable")
        self.assertFalse(unavailable[0]["externalFetchAllowed"])
        for terminal in (blocked[0], unavailable[0]):
            self.assertTrue(terminal["auditKey"].startswith("attribute-audit:sha256:"))
            self.assertTrue(terminal["canonicalInputSignature"].startswith("sha256:"))
            self.assertTrue(terminal["attributeRuleRevision"])
            self.assertTrue(terminal["contextKey"])

    def test_input_signature_and_audit_key_are_stable_when_slots_or_candidates_reorder(self):
        data = fixture()
        first = build_winner_audit_intents(
            active_winners=data["activeWinners"],
            candidate_rows=data["candidateRows"],
            candidate_context=data["candidateContext"],
            rulebook=data["verifiedRulebook"],
        )[0]
        reordered = copy.deepcopy(data)
        reordered["candidateRows"][0]["evidence"]["attributeAudit"]["canonicalEquipment"].reverse()
        reordered["candidateRows"].append(copy.deepcopy(reordered["candidateRows"][0]))
        reordered["candidateRows"].reverse()
        second = build_winner_audit_intents(
            active_winners=reordered["activeWinners"],
            candidate_rows=reordered["candidateRows"],
            candidate_context=reordered["candidateContext"],
            rulebook=reordered["verifiedRulebook"],
        )[0]

        self.assertEqual(first["canonicalInputSignature"], second["canonicalInputSignature"])
        self.assertEqual(first["auditKey"], second["auditKey"])
        self.assertEqual(first["auditKey"], audit_key(first))
        self.assertEqual(
            first["canonicalInputSignature"],
            canonical_input_signature(first["sealedInput"]),
        )

    def test_official_profile_input_difference_is_inconclusive_before_calculation(self):
        data = fixture()
        intent = build_winner_audit_intents(
            active_winners=data["activeWinners"],
            candidate_rows=data["candidateRows"],
            candidate_context=data["candidateContext"],
            rulebook=data["verifiedRulebook"],
        )[0]
        official = copy.deepcopy(intent["sealedInput"])
        official["equipment"][0]["gemIds"] = ["different-gem"]

        result = match_official_profile(intent["sealedInput"], official)

        self.assertEqual(result["status"], "inconclusive_input_mismatch")
        self.assertTrue(any(row["field"] == "gemIds" for row in result["mismatches"]))

    def test_duplicate_gem_multiplicity_is_sealed_and_must_match(self):
        data = fixture()
        source_equipment = data["candidateRows"][0]["evidence"]["attributeAudit"]["canonicalEquipment"]
        next(row for row in source_equipment if row["slot"] == "head")["gemIds"] = ["240914", "240914"]
        intent = build_winner_audit_intents(
            active_winners=data["activeWinners"],
            candidate_rows=data["candidateRows"],
            candidate_context=data["candidateContext"],
            rulebook=data["verifiedRulebook"],
        )[0]
        official = copy.deepcopy(intent["sealedInput"])
        next(row for row in official["equipment"] if row["slot"] == "head")["gemIds"] = ["240914"]

        result = match_official_profile(intent["sealedInput"], official)

        sealed_head = next(row for row in intent["sealedInput"]["equipment"] if row["slot"] == "head")
        self.assertEqual(sealed_head["gemIds"], ["240914", "240914"])
        self.assertEqual(result["status"], "inconclusive_input_mismatch")
        self.assertTrue(any(row["field"] == "gemIds" for row in result["mismatches"]))

    def test_official_profile_can_match_equipment_without_replaying_server_static_facts(self):
        data = fixture()
        intent = build_winner_audit_intents(
            active_winners=data["activeWinners"],
            candidate_rows=data["candidateRows"],
            candidate_context=data["candidateContext"],
            rulebook=data["verifiedRulebook"],
        )[0]
        official = {
            "character": intent["sealedInput"]["character"],
            "equipment": intent["sealedInput"]["equipment"],
        }

        result = match_official_profile(intent["sealedInput"], official)

        self.assertEqual(result, {"status": "matched", "mismatches": []})

    def test_panel_comparison_respects_declared_precision_and_keeps_raw_and_display_values(self):
        rule = fixture()["verifiedRulebook"]["contexts"][0]
        expected = {
            "primary": {"key": "intellect", "rawValue": 1500},
            "stamina": {"key": "stamina", "rawValue": 2600},
            "resources": {"health": {"key": "health", "rawValue": 52100}},
            "secondary": [{"key": "haste", "rawValue": 100, "convertedValue": "2.0%", "displayUnit": "percent"}],
        }
        observed = {
            "primary": {"key": "intellect", "rawValue": 1500},
            "stamina": {"key": "stamina", "rawValue": 2600},
            "resources": {"health": {"key": "health", "rawValue": 52100}},
            "secondary": [{"key": "haste", "rawValue": 100, "convertedValue": "2.04%", "displayUnit": "percent"}],
        }

        passed = compare_attribute_panel(rule=rule, expected=expected, observed=observed)
        observed["secondary"][0]["convertedValue"] = "2.2%"
        mismatched = compare_attribute_panel(rule=rule, expected=expected, observed=observed)

        self.assertEqual(passed["status"], "pass")
        self.assertEqual(mismatched["status"], "confirmed_mismatch")
        haste = next(row for row in mismatched["fields"] if row["key"] == "haste")
        self.assertEqual(haste["expected"]["rawRating"], 100)
        self.assertEqual(haste["observed"]["displayValue"], "2.2%")
        self.assertEqual(haste["precision"], 1)


if __name__ == "__main__":
    unittest.main()
