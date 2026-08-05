import copy
import inspect
import json
import unittest

from server.gear_canonical_kernel import (
    CanonicalValueError,
    SealedCanonicalDocument,
    seal_canonical_document,
)
from server.gear_exact_item_instance import (
    build_exact_item_instance,
    canonical_enhancement_selection,
    derive_simc_serializer_input,
    reload_exact_item,
    reload_exact_static_facts,
    seal_exact_item,
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


EXACT_SLOT_KEYS = frozenset({
    "itemId", "declaredItemLevel", "bonusIds", "context", "gemIds",
    "gemBonusIds", "gemItemLevels", "enchantId", "craftedStats",
    "embellishmentIds", "redirectedBaseStats",
})


def adapter_exact_slot_fields(row):
    return {key: copy.deepcopy(row[key]) for key in EXACT_SLOT_KEYS}


class GearExactItemInstanceTest(unittest.TestCase):
    def test_typed_reload_exact_and_static_facts_preserve_exact_bytes_and_binding(self):
        exact = seal_exact_item(exact_v2_row()).document
        static = __import__(
            "server.gear_exact_item_instance", fromlist=["seal_exact_static_facts"]
        ).seal_exact_static_facts(exact, {"haste_rating": 241}).document

        self.assertEqual(
            reload_exact_item(exact.canonical_bytes, exact.content_key), exact,
        )
        self.assertEqual(
            reload_exact_static_facts(
                static.canonical_bytes, static.content_key, exact=exact,
            ),
            static,
        )
        other = seal_exact_item(exact_v2_row(itemId="1002")).document
        with self.assertRaises(CanonicalValueError):
            reload_exact_static_facts(
                static.canonical_bytes, static.content_key, exact=other,
            )
        with self.assertRaises(CanonicalValueError):
            reload_exact_item(exact.canonical_bytes + b" ", exact.content_key)

    def test_seal_exact_item_rejects_noncanonical_sets_and_contract_extra_fields(self):
        for field, value in (
            ("craftedStats", ["haste", "crit"]),
            ("craftedStats", ["crit", "crit", "haste"]),
            ("embellishmentIds", ["emb-b", "emb-a"]),
            ("bonusIds", ["9002", "13334"]),
            ("redirectedBaseStats", ["mastery", "crit"]),
        ):
            with self.subTest(field=field, value=value):
                self.assertEqual(
                    seal_exact_item(exact_v2_row(**{field: value})).status,
                    "blocked",
                )

        crafted_effect = seal_exact_item(
            exact_v2_row(craftedEffectIds=["craft-a"])
        )
        listed = seal_exact_item(exact_v2_row(listed=False))
        self.assertEqual(crafted_effect.status, "blocked")
        self.assertEqual(crafted_effect.issues[0].path, "exactSlot.craftedEffectIds")
        self.assertEqual(listed.status, "blocked")
        self.assertEqual(listed.issues[0].path, "exactSlot.listed")

    def test_sealed_exact_ignores_adapter_only_catalog_provenance_and_binds_every_exact_field(self):
        base_row = exact_v2_row()
        base = seal_exact_item(base_row)
        self.assertEqual(base.status, "verified")
        self.assertEqual(base.document.document_kind, "exact_item")
        self.assertEqual(base.document.schema_revision, "gear-exact-item-instance-v2")
        self.assertRegex(
            base.document.content_key,
            r"^exact-item-instance:sha256:[0-9a-f]{64}$",
        )
        unlisted_import = adapter_exact_slot_fields({**base_row, "listed": False})
        self.assertEqual(base.document, seal_exact_item(unlisted_import).document)
        self.assertEqual(
            seal_exact_item({**base_row, "listed": False}).status,
            "blocked",
        )

        for field, replacement in (
            ("itemId", "1002"),
            ("declaredItemLevel", 269),
            ("bonusIds", ["13334", "9001"]),
            ("context", "mythic"),
            ("gemIds", ["240893", "240897"]),
            ("gemBonusIds", ["1514", "1515"]),
            ("gemItemLevels", [90, 91]),
            ("enchantId", "7444"),
            ("craftedStats", ["32"]),
            ("embellishmentIds", ["999001"]),
            ("redirectedBaseStats", ["mastery_rating"]),
        ):
            with self.subTest(field=field):
                changed = seal_exact_item(exact_v2_row(**{field: replacement}))
                self.assertEqual(changed.status, "verified")
                self.assertNotEqual(
                    base.document.content_key,
                    changed.document.content_key,
                )

    def test_sealed_exact_preserves_ordered_arrays_and_derives_the_only_simc_input(self):
        exact = seal_exact_item(exact_v2_row()).document
        payload = json.loads(exact.canonical_bytes)
        self.assertEqual(payload["gemIds"], ["240892", "240897"])
        self.assertEqual(payload["gemBonusIds"], ["1514", "1514"])
        self.assertEqual(payload["gemItemLevels"], [90, 90])
        self.assertEqual(
            derive_simc_serializer_input(exact),
            {
                "id": "1001",
                "ilevel": "266",
                "bonus_id": "13334/9001/9002",
                "gem_id": "240892/240897",
                "gem_bonus_id": "1514/1514",
                "gem_ilevel": "90/90",
                "enchant_id": "7443",
                "crafted_stats": "32/36",
                "embellishment": "999001/999002",
            },
        )

    def test_serializer_derivation_is_byte_stable_and_has_no_caller_payload_parameter(self):
        exact = seal_exact_item(exact_v2_row()).document
        first = derive_simc_serializer_input(exact)
        second = derive_simc_serializer_input(exact)
        self.assertEqual(
            json.dumps(first, sort_keys=True, separators=(",", ":")).encode(),
            json.dumps(second, sort_keys=True, separators=(",", ":")).encode(),
        )
        self.assertEqual(
            tuple(inspect.signature(derive_simc_serializer_input).parameters),
            ("exact",),
        )
        first["id"] = "9999"
        first["ilevel"] = "999"
        first["bonus_id"] = "forged"
        self.assertEqual(
            derive_simc_serializer_input(exact),
            second,
        )

    def test_simc_derivation_rejects_raw_wrong_or_tampered_exact_documents(self):
        exact = seal_exact_item(exact_v2_row()).document
        payload = json.loads(exact.canonical_bytes)
        wrong_documents = (
            payload,
            seal_canonical_document(
                document_kind="other", schema_revision=exact.schema_revision,
                payload=payload, key_prefix="exact-item-instance:sha256:",
            ),
            seal_canonical_document(
                document_kind="exact_item", schema_revision="wrong-schema",
                payload=payload, key_prefix="exact-item-instance:sha256:",
            ),
            seal_canonical_document(
                document_kind="exact_item", schema_revision=exact.schema_revision,
                payload=payload, key_prefix="attacker:sha256:",
            ),
        )
        for document in wrong_documents:
            with self.subTest(document=document):
                with self.assertRaises(CanonicalValueError):
                    derive_simc_serializer_input(document)

        tampered = object.__new__(SealedCanonicalDocument)
        object.__setattr__(tampered, "document_kind", exact.document_kind)
        object.__setattr__(tampered, "schema_revision", exact.schema_revision)
        object.__setattr__(tampered, "canonical_bytes", exact.canonical_bytes.replace(b'"1001"', b'"1002"'))
        object.__setattr__(tampered, "content_key", exact.content_key)
        with self.assertRaises(CanonicalValueError):
            derive_simc_serializer_input(tampered)

    def test_sealed_exact_rejects_noncanonical_types_text_and_cardinality(self):
        invalid_rows = (
            exact_v2_row(itemId=1001),
            exact_v2_row(itemId=" 1001 "),
            exact_v2_row(itemId="1001\n"),
            exact_v2_row(declaredItemLevel=True),
            exact_v2_row(declaredItemLevel=266.9),
            exact_v2_row(declaredItemLevel=10000),
            exact_v2_row(context={"difficulty": "heroic"}),
            exact_v2_row(context=" heroic "),
            exact_v2_row(context="heroic\u2028forged"),
            exact_v2_row(bonusIds=[13334]),
            exact_v2_row(gemIds=[240892, "240897"]),
            exact_v2_row(gemBonusIds=[True, "1514"]),
            exact_v2_row(gemItemLevels=[90.5, 90]),
            exact_v2_row(gemItemLevels=[10000, 90]),
            exact_v2_row(gemBonusIds=["1514"]),
            exact_v2_row(gemItemLevels=[90]),
            exact_v2_row(enchantId=7443),
        )
        for row in invalid_rows:
            with self.subTest(row=row):
                self.assertEqual(seal_exact_item(row).status, "blocked")

    def test_v2_identity_accepts_exact_slot_contract_without_v1_catalog_row_fields(self):
        result = seal_exact_item(exact_v2_row())
        self.assertEqual(result.status, "verified")

    def test_each_direct_v2_enhancement_field_changes_exact_key(self):
        original = seal_exact_item(exact_v2_row()).document
        for field, value in (
            ("gemIds", ["240897", "240892"]),
            ("gemBonusIds", ["1515", "1514"]),
            ("gemItemLevels", [91, 90]),
            ("enchantId", "9999"),
            ("craftedStats", ["32"]),
            ("embellishmentIds", ["999001"]),
        ):
            result = seal_exact_item(exact_v2_row(**{field: value}))
            self.assertEqual(result.status, "verified", field)
            self.assertNotEqual(result.document.content_key, original.content_key, field)

    def test_arbitrary_variant_key_cannot_gate_or_rescue_v2_identity(self):
        original = seal_exact_item(exact_v2_row()).document
        external = exact_v2_row(
            variantKey="fabricated-not-canonical",
            rowFamily="exact_instance",
            status="verified",
        )
        self.assertEqual(seal_exact_item(external).status, "blocked")
        projected = adapter_exact_slot_fields(external)
        self.assertEqual(seal_exact_item(projected).document, original)

    def test_v2_identity_blocks_out_of_contract_numeric_and_context_values(self):
        for changed in (
            exact_v2_row(declaredItemLevel=266.9),
            exact_v2_row(declaredItemLevel=True),
            exact_v2_row(context={"x": True}),
            exact_v2_row(context={"x": False}),
            exact_v2_row(gemItemLevels=[90.5, 90]),
        ):
            self.assertEqual(seal_exact_item(changed).status, "blocked")

    def test_v2_identity_rejects_mismatched_external_enhancement_override(self):
        self.assertEqual(
            tuple(inspect.signature(seal_exact_item).parameters),
            ("exact_slot_payload",),
        )
        with self.assertRaises(TypeError):
            seal_exact_item(
                exact_v2_row(),
                enhancement_selection={"gemIds": ["different"]},
            )

    def test_v2_identity_direct_enhancements_remain_authoritative_with_override(self):
        first = seal_exact_item(exact_v2_row()).document
        second = seal_exact_item(
            exact_v2_row(gemIds=["240897", "240892"]),
        ).document
        self.assertNotEqual(first.content_key, second.content_key)
        self.assertEqual(
            json.loads(second.canonical_bytes)["gemIds"],
            ["240897", "240892"],
        )

    def test_every_direct_enhancement_field_changes_identity_with_equivalent_override(self):
        first = seal_exact_item(exact_v2_row()).document
        for field, value in (("gemIds", ["240897", "240892"]), ("gemBonusIds", ["1515", "1514"]), ("gemItemLevels", [91, 90]), ("enchantId", "9999"), ("craftedStats", ["32"]), ("embellishmentIds", ["999001"])):
            result = seal_exact_item(exact_v2_row(**{field: value}))
            self.assertEqual(result.status, "verified", field)
            self.assertNotEqual(first.content_key, result.document.content_key, field)

    def test_v2_identity_rejects_non_string_identifiers_without_normalizing_them(self):
        for row in (
            exact_v2_row(itemId=1001),
            exact_v2_row(bonusIds=[13334]),
            exact_v2_row(gemIds=[240892, "240897"]),
            exact_v2_row(gemBonusIds=[True, "1514"]),
            exact_v2_row(enchantId=7443),
        ):
            self.assertEqual(seal_exact_item(row).status, "blocked")

    def test_v2_enhancement_override_rejects_every_noncanonical_identifier_shape(self):
        identifier_fields = ("gemIds", "gemBonusIds", "craftedStats", "embellishmentIds")
        for field in identifier_fields:
            original = exact_v2_row()[field]
            for replacement in (
                [1001, *original[1:]],
                [True, *original[1:]],
                tuple(original),
                [f" {original[0]} ", *original[1:]],
                [f"{original[0]}\n", *original[1:]],
            ):
                result = seal_exact_item(
                    exact_v2_row(**{field: replacement}),
                )
                self.assertEqual(result.status, "blocked", (field, replacement))

        for replacement in ([10000, 90], [True, 90], ["90", 90], (90, 90)):
            result = seal_exact_item(
                exact_v2_row(gemItemLevels=replacement),
            )
            self.assertEqual(result.status, "blocked", replacement)

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
            self.assertEqual(seal_exact_item(row).status, "blocked", row)

    def test_v2_set_like_direct_fields_must_already_be_sorted_and_unique(self):
        for field, values in (
            ("bonusIds", (["13334", "100"], ["100", "100", "13334"])),
            ("craftedStats", (["haste", "crit"], ["crit", "crit", "haste"])),
            ("embellishmentIds", (["emb-b", "emb-a"], ["emb-a", "emb-a", "emb-b"])),
            ("redirectedBaseStats", (["mastery", "crit"], ["crit", "crit", "mastery"])),
        ):
            for replacement in values:
                result = seal_exact_item(exact_v2_row(**{field: replacement}))
                self.assertEqual(result.status, "blocked", (field, replacement))

    def test_v2_override_must_match_raw_direct_six_fields_without_normalization(self):
        for field, replacements in (
            ("craftedStats", (["haste", "crit"], ["crit", "crit", "haste"])),
            ("embellishmentIds", (["emb-b", "emb-a"], ["emb-a", "emb-a", "emb-b"])),
        ):
            for replacement in replacements:
                result = seal_exact_item(
                    exact_v2_row(**{field: replacement}),
                )
                self.assertEqual(result.status, "blocked", (field, replacement))

    def test_v2_blocks_out_of_contract_crafted_effect_ids_at_first_boundary(self):
        result = seal_exact_item(
            exact_v2_row(craftedEffectIds=["effect-a"]),
        )
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.issues[0].path, "exactSlot.craftedEffectIds")

    def test_v1_wrapper_and_v2_exact_keys_remain_byte_compatible(self):
        self.assertEqual(
            seal_exact_item(exact_v2_row()).document.content_key,
            "exact-item-instance:sha256:e10e93ee691bc1073af958427aa06d451ba1132c5eb8ef0fa8654c70fb4670f6",
        )
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
