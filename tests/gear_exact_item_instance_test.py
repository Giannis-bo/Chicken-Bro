import copy
import unittest

from server.gear_exact_item_instance import (
    build_exact_item_identity,
    build_exact_item_instance,
    canonical_enhancement_selection,
)


CURRENT_BINDING = {
    "seasonRevision": "season-17-f131dd36ddf1",
    "gearRuleRevision": "gear-rule-matrix-v1",
}
CATALOG_REVISION = "gear-catalog:sha256:" + ("2" * 64)


def exact_row(**overrides):
    row = {
        "rowFamily": "exact_instance",
        "status": "verified",
        "itemId": "1001",
        "variantKey": "observed-hero-3",
        "itemLevel": 266,
        "slot": "head",
        "bonusIds": ["9002", "13334", "9001"],
        "staticStats": {
            "stamina": 512,
            "haste_rating": 241,
            "mastery_rating": 180,
        },
        "simcOptions": {
            "ilevel": "266",
            "bonus_id": "9002/13334/9001",
            "gem_id": "240892/240897",
            "gem_bonus_id": "1514/1514",
            "gem_ilevel": "90/90",
            "enchant_id": "7443",
            "crafted_stats": "36/32",
            "embellishment": "999002/999001",
        },
        "payload": {
            "context": {"difficulty": "heroic", "dropContext": 16},
            "profileUrl": "https://example.invalid/character",
        },
        "updatedAt": "2026-07-29T01:00:00Z",
    }
    row.update(overrides)
    return row


def exact_v2_row(**overrides):
    row = {
        "itemId": "1001",
        "declaredItemLevel": 266,
        "bonusIds": ["9002", "13334", "9001"],
        "context": "heroic",
        "gemIds": ["240892", "240897"],
        "gemBonusIds": ["1514", "1514"],
        "gemItemLevels": [90, 90],
        "enchantId": "7443",
        "craftedStats": ["36", "32"],
        "embellishmentIds": ["999002", "999001"],
        "redirectedBaseStats": ["haste_rating"],
    }
    row.update(overrides)
    return row


class GearExactItemInstanceTest(unittest.TestCase):
    def test_v2_identity_ignores_catalog_listing_and_changes_for_each_exact_field(self):
        base = exact_v2_row()
        listed = build_exact_item_identity(
            CURRENT_BINDING,
            {**base, "catalogStatus": "listed", "catalogRevision": CATALOG_REVISION},
        )
        unlisted = build_exact_item_identity(
            CURRENT_BINDING,
            {
                **base,
                "catalogStatus": "unlisted",
                "catalogRevision": "gear-catalog:sha256:" + ("3" * 64),
                "owner": "never-an-identity-input",
                "observationCount": 99,
            },
        )

        self.assertEqual(listed["status"], "verified")
        self.assertEqual(listed["exactItemInstanceKey"], unlisted["exactItemInstanceKey"])
        for field, replacement in (
            ("itemLevel", 269),
            ("bonusIds", ["9002", "13334", "9001", "7777"]),
            ("context", "mythic"),
            ("gems", ["240897", "240892"]),
            ("enchant", "9999"),
            ("craftedStats", ["32"]),
            ("embellishments", ["999001"]),
            ("redirectedBaseStats", ["crit_rating"]),
        ):
            changed = exact_v2_row()
            if field == "context":
                changed["context"] = replacement
            elif field == "gems":
                changed["gemIds"] = replacement
            elif field == "enchant":
                changed["enchantId"] = replacement
            elif field == "craftedStats":
                changed["craftedStats"] = replacement
            elif field == "embellishments":
                changed["embellishmentIds"] = replacement
            elif field == "redirectedBaseStats":
                changed["redirectedBaseStats"] = replacement
            else:
                changed[field] = replacement
                if field == "itemLevel":
                    changed["declaredItemLevel"] = changed.pop("itemLevel")
            candidate = build_exact_item_identity(CURRENT_BINDING, changed)
            self.assertEqual(candidate["status"], "verified", field)
            self.assertNotEqual(listed["exactItemInstanceKey"], candidate["exactItemInstanceKey"], field)

    def test_v2_identity_accepts_exact_slot_contract_without_v1_catalog_row_fields(self):
        result = build_exact_item_identity(CURRENT_BINDING, exact_v2_row())
        self.assertEqual(result["status"], "verified")

    def test_each_direct_v2_enhancement_field_changes_exact_key(self):
        original = build_exact_item_identity(CURRENT_BINDING, exact_v2_row())
        for field, value in (
            ("gemIds", ["240897", "240892"]),
            ("gemBonusIds", ["1515", "1514"]),
            ("gemItemLevels", [91, 90]),
            ("enchantId", "9999"),
            ("craftedStats", ["32"]),
            ("embellishmentIds", ["999001"]),
        ):
            result = build_exact_item_identity(CURRENT_BINDING, exact_v2_row(**{field: value}))
            self.assertEqual(result["status"], "verified", field)
            self.assertNotEqual(result["exactItemInstanceKey"], original["exactItemInstanceKey"], field)

    def test_arbitrary_variant_key_cannot_gate_or_rescue_v2_identity(self):
        original = build_exact_item_identity(CURRENT_BINDING, exact_v2_row())
        changed = build_exact_item_identity(
            CURRENT_BINDING,
            exact_v2_row(variantKey="fabricated-not-canonical", rowFamily="exact_instance", status="verified"),
        )
        self.assertEqual(changed["status"], "verified")
        self.assertEqual(changed["exactItemInstanceKey"], original["exactItemInstanceKey"])

    def test_v1_catalog_wrapper_remains_byte_and_key_compatible(self):
        built = build_exact_item_instance(
            CURRENT_BINDING,
            exact_row(),
            catalog_revision=CATALOG_REVISION,
        )
        self.assertEqual(
            built["exactItemInstanceKey"],
            "exact-item-instance:sha256:38b1a60808918f4bab94bd5bc0fd9240418ce72d631369beb054ec485ab636aa",
        )
        self.assertEqual(built["validation"]["catalogRevision"], CATALOG_REVISION)

    def test_exact_identity_is_deterministic_and_excludes_provenance(self):
        first = build_exact_item_instance(
            CURRENT_BINDING,
            exact_row(),
            catalog_revision=CATALOG_REVISION,
        )
        changed = exact_row(
            updatedAt="2026-07-29T02:00:00Z",
            payload={
                "context": {"dropContext": 16, "difficulty": "heroic"},
                "profileUrl": "https://example.invalid/other-character",
            },
        )
        second = build_exact_item_instance(
            CURRENT_BINDING,
            changed,
            catalog_revision=CATALOG_REVISION,
        )

        self.assertEqual(first["status"], "verified")
        self.assertEqual(first["exactItemInstanceKey"], second["exactItemInstanceKey"])
        self.assertEqual(first["exactVariantSignature"], second["exactVariantSignature"])
        self.assertEqual(first["progressionState"]["trackKey"], "hero")
        self.assertEqual(first["progressionState"]["rank"], 3)
        self.assertEqual(first["itemLevel"], 266)
        self.assertEqual(first["bonusIds"], ["13334", "9001", "9002"])
        self.assertEqual(first["enhancementSelection"]["gemIds"], ["240892", "240897"])
        self.assertEqual(first["enhancementSelection"]["craftedStats"], ["32", "36"])
        self.assertEqual(
            first["enhancementSelection"]["embellishmentIds"],
            ["999001", "999002"],
        )

    def test_gem_order_changes_exact_instance_but_not_variant_signature(self):
        first = build_exact_item_instance(
            CURRENT_BINDING,
            exact_row(),
            catalog_revision=CATALOG_REVISION,
        )
        second_row = exact_row()
        second_row["simcOptions"] = {
            **second_row["simcOptions"],
            "gem_id": "240897/240892",
        }
        second = build_exact_item_instance(
            CURRENT_BINDING,
            second_row,
            catalog_revision=CATALOG_REVISION,
        )

        self.assertEqual(first["status"], "verified")
        self.assertEqual(second["status"], "verified")
        self.assertEqual(first["exactVariantSignature"], second["exactVariantSignature"])
        self.assertNotEqual(first["exactItemInstanceKey"], second["exactItemInstanceKey"])

    def test_template_enhancement_must_match_sealed_exact_values(self):
        result = build_exact_item_instance(
            CURRENT_BINDING,
            exact_row(),
            catalog_revision=CATALOG_REVISION,
            enhancement_selection={
                "gemIds": ["240892", "240897"],
                "gemBonusIds": ["1514", "1514"],
                "gemItemLevels": ["90", "90"],
                "enchantId": "9999",
                "craftedStats": ["32", "36"],
                "embellishmentIds": ["999001", "999002"],
            },
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn(
            "EXACT_ENHANCEMENT_SOURCE_MISMATCH",
            [problem["code"] for problem in result["problems"]],
        )

    def test_missing_static_facts_and_unproven_track_fail_closed(self):
        missing_stats = build_exact_item_instance(
            CURRENT_BINDING,
            exact_row(staticStats={}),
            catalog_revision=CATALOG_REVISION,
        )
        missing_track = exact_row(itemLevel=266, bonusIds=["9001"])
        missing_track["simcOptions"] = {
            **missing_track["simcOptions"],
            "bonus_id": "9001",
        }
        unresolved = build_exact_item_instance(
            CURRENT_BINDING,
            missing_track,
            catalog_revision=CATALOG_REVISION,
        )

        self.assertEqual(missing_stats["status"], "blocked")
        self.assertIn(
            "EXACT_STATIC_FACTS_MISSING",
            [problem["code"] for problem in missing_stats["problems"]],
        )
        self.assertEqual(unresolved["status"], "blocked")
        self.assertIn(
            "TRACK_AUTHORITY_EXACT_TRACK_EVIDENCE_MISSING",
            [problem["code"] for problem in unresolved["problems"]],
        )

    def test_enhancement_sequences_preserve_composite_source_enchants(self):
        malformed = canonical_enhancement_selection(
            {
                "gemIds": ["240892", "240897"],
                "gemBonusIds": ["1514"],
                "gemItemLevels": ["90", "90"],
                "enchantId": "7443",
                "craftedStats": [],
                "embellishmentIds": [],
            }
        )
        composite_source = copy.deepcopy(exact_row())
        composite_source["simcOptions"]["enchant_id"] = "7443/7444"
        composite_result = build_exact_item_instance(
            CURRENT_BINDING,
            composite_source,
            catalog_revision=CATALOG_REVISION,
        )
        malformed_source = copy.deepcopy(exact_row())
        malformed_source["simcOptions"]["enchant_id"] = "7443,7444"
        malformed_result = build_exact_item_instance(
            CURRENT_BINDING,
            malformed_source,
            catalog_revision=CATALOG_REVISION,
        )

        self.assertEqual(malformed["status"], "blocked")
        self.assertIn(
            "ENHANCEMENT_GEM_SEQUENCE_MISMATCH",
            [problem["code"] for problem in malformed["problems"]],
        )
        self.assertEqual(composite_result["status"], "verified")
        self.assertEqual(
            composite_result["enhancementSelection"]["enchantId"],
            "7443/7444",
        )
        self.assertEqual(
            composite_result["serializerInput"]["enchant_id"],
            "7443/7444",
        )
        self.assertEqual(malformed_result["status"], "blocked")
        self.assertIn(
            "ENHANCEMENT_SINGLE_VALUE_MALFORMED",
            [problem["code"] for problem in malformed_result["problems"]],
        )
