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
        "bonusIds": ["13334", "9001", "9002"],
        "context": "heroic",
        "gemIds": ["240892", "240897"],
        "gemBonusIds": ["1514", "1514"],
        "gemItemLevels": [90, 90],
        "enchantId": "7443",
        "craftedStats": ["32", "36"],
        "embellishmentIds": ["999001", "999002"],
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
            ("bonusIds", ["13334", "7777", "9001", "9002"]),
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

    def test_v2_identity_blocks_out_of_contract_numeric_and_context_values(self):
        for changed in (
            exact_v2_row(declaredItemLevel=266.9),
            exact_v2_row(declaredItemLevel=True),
            exact_v2_row(context={"x": True}),
            exact_v2_row(context={"x": False}),
            exact_v2_row(gemItemLevels=[90.5, 90]),
        ):
            self.assertEqual(build_exact_item_identity(CURRENT_BINDING, changed)["status"], "blocked")

    def test_v2_identity_rejects_mismatched_external_enhancement_override(self):
        row = exact_v2_row()
        result = build_exact_item_identity(CURRENT_BINDING, row, enhancement_selection={"gemIds": ["different"], "gemBonusIds": ["1514"], "gemItemLevels": [90], "enchantId": "7443", "craftedStats": ["36", "32"], "embellishmentIds": ["999002", "999001"]})
        self.assertEqual(result["status"], "blocked")

    def test_v2_identity_direct_enhancements_remain_authoritative_with_override(self):
        base = exact_v2_row()
        equivalent = {key: base[key] for key in ("gemIds", "gemBonusIds", "gemItemLevels", "enchantId", "craftedStats", "embellishmentIds")}
        first = build_exact_item_identity(CURRENT_BINDING, base, enhancement_selection=equivalent)
        second_row = exact_v2_row(gemIds=["240897", "240892"])
        second_equivalent = {key: second_row[key] for key in equivalent}
        second = build_exact_item_identity(CURRENT_BINDING, second_row, enhancement_selection=second_equivalent)
        self.assertEqual(first["status"], "verified")
        self.assertEqual(second["status"], "verified")
        self.assertNotEqual(first["exactItemInstanceKey"], second["exactItemInstanceKey"])

    def test_every_direct_enhancement_field_changes_identity_with_equivalent_override(self):
        base = exact_v2_row()
        fields = ("gemIds", "gemBonusIds", "gemItemLevels", "enchantId", "craftedStats", "embellishmentIds")
        first = build_exact_item_identity(CURRENT_BINDING, base, enhancement_selection={field: base[field] for field in fields})
        for field, value in (("gemIds", ["240897", "240892"]), ("gemBonusIds", ["1515", "1514"]), ("gemItemLevels", [91, 90]), ("enchantId", "9999"), ("craftedStats", ["32"]), ("embellishmentIds", ["999001"])):
            row = exact_v2_row(**{field: value})
            result = build_exact_item_identity(CURRENT_BINDING, row, enhancement_selection={name: row[name] for name in fields})
            self.assertNotEqual(first["exactItemInstanceKey"], result["exactItemInstanceKey"], field)

    def test_v2_identity_rejects_non_string_identifiers_without_normalizing_them(self):
        for row in (
            exact_v2_row(itemId=1001),
            exact_v2_row(bonusIds=[13334]),
            exact_v2_row(gemIds=[240892, "240897"]),
            exact_v2_row(gemBonusIds=[True, "1514"]),
            exact_v2_row(enchantId=7443),
        ):
            self.assertEqual(build_exact_item_identity(CURRENT_BINDING, row)["status"], "blocked")

    def test_v2_enhancement_override_rejects_every_noncanonical_identifier_shape(self):
        base = exact_v2_row()
        fields = (
            "gemIds", "gemBonusIds", "gemItemLevels", "enchantId",
            "craftedStats", "embellishmentIds",
        )
        identifier_fields = ("gemIds", "gemBonusIds", "craftedStats", "embellishmentIds")
        for field in identifier_fields:
            original = base[field]
            for replacement in (
                [1001, *original[1:]],
                [True, *original[1:]],
                tuple(original),
                [f" {original[0]} ", *original[1:]],
                [f"{original[0]}\n", *original[1:]],
            ):
                override = {name: copy.deepcopy(base[name]) for name in fields}
                override[field] = replacement
                result = build_exact_item_identity(
                    CURRENT_BINDING, base, enhancement_selection=override,
                )
                self.assertEqual(result["status"], "blocked", (field, replacement))

        for replacement in ([10000, 90], [True, 90], ["90", 90], (90, 90)):
            override = {name: copy.deepcopy(base[name]) for name in fields}
            override["gemItemLevels"] = replacement
            result = build_exact_item_identity(
                CURRENT_BINDING, base, enhancement_selection=override,
            )
            self.assertEqual(result["status"], "blocked", replacement)

    def test_v2_direct_strings_and_levels_must_already_be_canonical_and_bounded(self):
        for row in (
            exact_v2_row(itemId=" 1001 "),
            exact_v2_row(itemId="1001\n"),
            exact_v2_row(context=" heroic "),
            exact_v2_row(context="heroic\nforged"),
            exact_v2_row(gemIds=[" 240892 ", "240897"]),
            exact_v2_row(gemIds=["240892\n", "240897"]),
            exact_v2_row(declaredItemLevel=10000),
            exact_v2_row(gemItemLevels=[10000, 90]),
        ):
            self.assertEqual(build_exact_item_identity(CURRENT_BINDING, row)["status"], "blocked", row)

    def test_v2_set_like_direct_fields_must_already_be_sorted_and_unique(self):
        for field, values in (
            ("bonusIds", (["13334", "100"], ["100", "100", "13334"])),
            ("craftedStats", (["haste", "crit"], ["crit", "crit", "haste"])),
            ("embellishmentIds", (["emb-b", "emb-a"], ["emb-a", "emb-a", "emb-b"])),
            ("redirectedBaseStats", (["mastery", "crit"], ["crit", "crit", "mastery"])),
        ):
            for replacement in values:
                result = build_exact_item_identity(
                    CURRENT_BINDING, exact_v2_row(**{field: replacement}),
                )
                self.assertEqual(result["status"], "blocked", (field, replacement))

    def test_v2_override_must_match_raw_direct_six_fields_without_normalization(self):
        base = exact_v2_row(
            craftedStats=["crit", "haste"],
            embellishmentIds=["emb-a", "emb-b"],
        )
        fields = (
            "gemIds", "gemBonusIds", "gemItemLevels", "enchantId",
            "craftedStats", "embellishmentIds",
        )
        for field, replacements in (
            ("craftedStats", (["haste", "crit"], ["crit", "crit", "haste"])),
            ("embellishmentIds", (["emb-b", "emb-a"], ["emb-a", "emb-a", "emb-b"])),
        ):
            for replacement in replacements:
                override = {name: copy.deepcopy(base[name]) for name in fields}
                override[field] = replacement
                result = build_exact_item_identity(
                    CURRENT_BINDING, base, enhancement_selection=override,
                )
                self.assertEqual(result["status"], "blocked", (field, replacement))

    def test_v2_blocks_out_of_contract_crafted_effect_ids_at_first_boundary(self):
        direct = build_exact_item_identity(
            CURRENT_BINDING, exact_v2_row(craftedEffectIds=["effect-a"]),
        )
        base = exact_v2_row()
        override = {
            name: copy.deepcopy(base[name])
            for name in (
                "gemIds", "gemBonusIds", "gemItemLevels", "enchantId",
                "craftedStats", "embellishmentIds",
            )
        }
        override["craftedEffectIds"] = ["effect-a"]
        derived = build_exact_item_identity(
            CURRENT_BINDING, base, enhancement_selection=override,
        )
        for result in (direct, derived):
            self.assertEqual(result["status"], "blocked")
            self.assertIn("EXACT_CRAFTED_EFFECT_IDS_UNSUPPORTED", result["problemCodes"])

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
