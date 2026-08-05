import copy
import unittest
from unittest.mock import patch

import server.gear_resolved_loadout as resolved_loadout_module
from tests.gear_exact_authority_store_test import authority_bundle

from server.gear_resolved_loadout import (
    build_resolved_loadout,
    build_resolved_loadout_from_registry,
    build_resolved_loadout_v2,
    verify_resolved_loadout_v2,
)


CATALOG_REVISION = "gear-catalog:sha256:" + ("2" * 64)
REGISTRY_REVISION = "gear-exact-registry:sha256:" + ("3" * 64)
RULE_REVISION = "gear-rule-matrix-v1"
HEAD_KEY = "exact-item-instance:sha256:" + ("a" * 64)
MAIN_KEY = "exact-item-instance:sha256:" + ("b" * 64)
EMPTY_SELECTION = "enhancement-selection:sha256:" + ("c" * 64)
ENCHANT_SELECTION = "enhancement-selection:sha256:" + ("d" * 64)
TEMPLATE_HASH = "sha256:" + ("e" * 64)
TEMPLATE_AUTHORITY_IDENTITY = "sha256:" + ("f" * 64)


def exact_instance(key, selection_key, item_id, ilevel, bonus_ids):
    return {
        "schemaRevision": "gear-exact-item-instance-v1",
        "exactItemInstanceKey": key,
        "exactVariantSignature": "exact-variant:sha256:" + (
            "1" * 64 if key == HEAD_KEY else "2" * 64
        ),
        "enhancementSelectionKey": selection_key,
        "itemId": item_id,
        "bonusIds": sorted(bonus_ids),
        "context": "",
        "progressionState": {
            "kind": "upgrade_track",
            "trackKey": "hero",
            "rank": 3,
            "maxRank": 6,
        },
        "ilevel": ilevel,
        "rowHash": "sha256:" + ("4" * 64 if key == HEAD_KEY else "5" * 64),
    }


def validation(key, item_id, ilevel, bonus_ids, static_facts, **options):
    serializer = {
        "id": item_id,
        "ilevel": str(ilevel),
        "bonus_id": "/".join(sorted(bonus_ids)),
        **options,
    }
    return {
        "schemaRevision": "gear-exact-item-validation-v1",
        "exactItemInstanceKey": key,
        "catalogRevision": CATALOG_REVISION,
        "gearRuleRevision": RULE_REVISION,
        "status": "verified",
        "staticFacts": static_facts,
        "serializerInput": serializer,
        "rowHash": "sha256:" + ("6" * 64 if key == HEAD_KEY else "7" * 64),
    }


def reference(slot, item_id, key, status="verified", problem_codes=None):
    row = {
        "schemaRevision": "gear-exact-template-reference-v1",
        "catalogRevision": CATALOG_REVISION,
        "templateScope": "community",
        "templateContentHash": TEMPLATE_HASH,
        "templateAuthorityIdentity": TEMPLATE_AUTHORITY_IDENTITY,
        "slot": slot,
        "itemId": item_id,
        "sourceVariantKey": f"variant-{slot}",
        "exactItemInstanceKey": key if status == "verified" else "",
        "validationStatus": status,
        "problemCodes": problem_codes or [],
        "rowHash": "sha256:" + ("8" * 64 if slot == "head" else "9" * 64),
    }
    if slot == "main_hand":
        row["editorManagedEnhancementFields"] = ["enchantOptionId"]
    return row


def exact_registry():
    return {
        "schemaRevision": "gear-exact-item-registry-v1",
        "status": "verified",
        "registryRevision": REGISTRY_REVISION,
        "catalogRevision": CATALOG_REVISION,
        "seasonRevision": "season-17",
        "gearRuleRevision": RULE_REVISION,
        "enhancementSelections": [
            {
                "enhancementSelectionKey": EMPTY_SELECTION,
                "selection": {
                    "schemaRevision": "gear-enhancement-selection-v1",
                    "gemIds": [],
                    "gemBonusIds": [],
                    "gemItemLevels": [],
                    "enchantId": "",
                    "craftedStats": [],
                    "embellishmentIds": [],
                },
                "rowHash": "sha256:" + ("c" * 64),
            },
            {
                "enhancementSelectionKey": ENCHANT_SELECTION,
                "selection": {
                    "schemaRevision": "gear-enhancement-selection-v1",
                    "gemIds": [],
                    "gemBonusIds": [],
                    "gemItemLevels": [],
                    "enchantId": "7443",
                    "craftedStats": [],
                    "embellishmentIds": [],
                },
                "rowHash": "sha256:" + ("d" * 64),
            },
        ],
        "exactItemInstances": [
            exact_instance(HEAD_KEY, EMPTY_SELECTION, "1001", 266, ["9002", "9001"]),
            exact_instance(MAIN_KEY, ENCHANT_SELECTION, "1002", 272, ["9010"]),
        ],
        "validations": [
            validation(
                HEAD_KEY,
                "1001",
                266,
                ["9002", "9001"],
                {"intellect": 400, "stamina": 700},
            ),
            validation(
                MAIN_KEY,
                "1002",
                272,
                ["9010"],
                {"intellect": 600, "haste": 250},
                enchant_id="7443",
            ),
        ],
        "templateReferences": [
            reference("head", "1001", HEAD_KEY),
            reference("main_hand", "1002", MAIN_KEY),
        ],
        "summary": {},
        "problemCodes": [],
    }


def resolver_snapshot():
    return {
        "contractRevision": "gear-resolved-snapshot-v1",
        "status": "verified",
        "dependencyVector": {
            "gearRuleRevision": RULE_REVISION,
            "simcRuntimeRevision": "simc-runtime-v1",
        },
        "eligibilityContext": {
            "classKey": "mage",
            "specKey": "arcane",
            "level": 90,
        },
        "resolvedSlots": {
            "head": {
                "slot": "head",
                "itemId": "1001",
                "itemLevel": 266,
                "resolvedStats": {"intellect": 400, "stamina": 700},
                "simcOptions": {
                    "ilevel": "266",
                    "bonus_id": "9002/9001",
                },
                "legality": {"status": "verified", "problemCodes": []},
                "problems": [],
            },
            "main_hand": {
                "slot": "main_hand",
                "itemId": "1002",
                "itemLevel": 272,
                "resolvedStats": {"intellect": 600, "haste": 250},
                "simcOptions": {
                    "ilevel": "272",
                    "bonus_id": "9010",
                    "enchant_id": "7443",
                },
                "legality": {"status": "verified", "problemCodes": []},
                "problems": [],
            },
        },
        "ruleResults": [],
        "aggregateLegality": {"status": "verified", "problemCodes": []},
        "staticAttributes": {
            "haste": 250,
            "intellect": 1000,
            "stamina": 700,
        },
        "constraints": {
            "embellishmentUsed": 0,
            "embellishmentMax": 2,
            "slots": {},
        },
        "profileReadiness": {
            "status": "verified",
            "simcReady": True,
            "requiredSlots": ["head", "main_hand"],
            "readySlots": ["head", "main_hand"],
            "serializerRevision": "websim-profile-compat-v1",
            "simcRuntimeRevision": "simc-runtime-v1",
            "problems": [],
        },
        "evidenceLedger": {
            "contractRevision": "gear-evidence-ledger-v1",
            "claims": [],
            "problems": [],
        },
        "problems": [],
    }


def v2_bundle(slot, item_id, envelope_key, subjects, *, exact_fields=None):
    records = []
    for ordinal, subject in enumerate(subjects):
        token = str(ordinal + 1)
        records.append({
            "subjectKind": "item",
            "subjectKey": subject,
            "subjectVariantSignature": "exact-variant:sha256:" + token * 64,
            "supportRecordKey": "simc-item-effect-record:sha256:" + token * 64,
        })
    return {
        "envelope": {"content_key": envelope_key, "resolverRevision": "resolver-v2"},
        "exact_item": {
            "itemId": item_id,
            "itemLevel": 266,
            "bonusIds": ["9001"],
            "gemIds": [],
            "gemBonusIds": [],
            "gemItemLevels": [],
            "enchantId": "",
            "craftedStats": [],
            "embellishmentIds": [],
            "redirectedBaseStats": [],
            **(exact_fields or {}),
        },
        "progression": {"gearRuleRevision": RULE_REVISION, "trackAuthorityInput": {"slot": slot}},
        "effect_support": {"status": "verified", "simcRuntimeRevision": "simc-runtime-v2", "subjects": records},
    }


class GearResolvedLoadoutTest(unittest.TestCase):
    def build(self, registry=None, snapshot=None):
        return build_resolved_loadout(
            resolver_snapshot=snapshot or resolver_snapshot(),
            exact_registry=registry or exact_registry(),
            template_scope="community",
            template_content_hash=TEMPLATE_HASH,
        )

    def test_ready_loadout_is_deterministic_and_uses_canonical_slot_order(self):
        first = self.build()
        reversed_registry = exact_registry()
        for field in (
            "enhancementSelections",
            "exactItemInstances",
            "validations",
            "templateReferences",
        ):
            reversed_registry[field].reverse()
        second = self.build(registry=reversed_registry)

        self.assertEqual(first["status"], "ready")
        self.assertEqual(first, second)
        self.assertRegex(
            first["resolvedLoadoutKey"],
            r"^resolved-loadout:sha256:[0-9a-f]{64}$",
        )
        self.assertEqual(
            [row["slot"] for row in first["orderedSlots"]],
            ["head", "main_hand"],
        )
        self.assertEqual(
            first["orderedSlots"][0]["exactItemInstanceKey"],
            HEAD_KEY,
        )
        self.assertEqual(
            first["staticAttributes"],
            {"haste": 250, "intellect": 1000, "stamina": 700},
        )
        self.assertEqual(
            first["serializerInput"]["gearItems"][0]["simcOptions"],
            {"bonus_id": "9001/9002", "id": "1001", "ilevel": "266"},
        )

    def test_legacy_option_canonicalization_can_preserve_multi_value_single_field(self):
        from server.gear_resolved_loadout import canonical_simc_options

        self.assertEqual(
            canonical_simc_options(
                {
                    "id": "1001",
                    "bonus_id": "9002/9001",
                    "enchant_id": "8039/8052",
                },
                strict_single_values=False,
            ),
            {
                "id": "1001",
                "bonus_id": "9001/9002",
                "enchant_id": "8039/8052",
            },
        )
        self.assertIsNone(
            canonical_simc_options(
                {
                    "id": "1001",
                    "enchant_id": "8039/8052",
                }
            )
        )

    def test_partial_reference_and_missing_slot_fail_closed(self):
        partial = exact_registry()
        partial["status"] = "partial"
        partial["problemCodes"] = ["ENHANCEMENT_SINGLE_VALUE_MALFORMED"]
        partial["templateReferences"][0] = reference(
            "head",
            "1001",
            "",
            status="partial",
            problem_codes=["ENHANCEMENT_SINGLE_VALUE_MALFORMED"],
        )
        missing = exact_registry()
        missing["templateReferences"] = [
            row for row in missing["templateReferences"] if row["slot"] != "head"
        ]

        partial_result = self.build(registry=partial)
        missing_result = self.build(registry=missing)

        self.assertEqual(partial_result["status"], "blocked")
        self.assertIn(
            "LOADOUT_EXACT_REFERENCE_NOT_VERIFIED",
            partial_result["problemCodes"],
        )
        self.assertEqual(missing_result["status"], "blocked")
        self.assertIn("LOADOUT_REQUIRED_SLOT_MISSING", missing_result["problemCodes"])
        self.assertNotIn("resolvedLoadoutKey", partial_result)

    def test_revision_serializer_and_static_fact_mismatch_fail_closed(self):
        revision = exact_registry()
        revision["gearRuleRevision"] = "gear-rule-matrix-v2"
        serializer = exact_registry()
        serializer["validations"][0]["serializerInput"]["bonus_id"] = "9999"
        static = copy.deepcopy(resolver_snapshot())
        static["staticAttributes"]["intellect"] = 9999

        revision_result = self.build(registry=revision)
        serializer_result = self.build(registry=serializer)
        static_result = self.build(snapshot=static)

        self.assertIn("LOADOUT_RULE_REVISION_CONFLICT", revision_result["problemCodes"])
        self.assertIn(
            "LOADOUT_SERIALIZER_PARITY_MISMATCH",
            serializer_result["problemCodes"],
        )
        self.assertIn(
            "LOADOUT_STATIC_ATTRIBUTES_MISMATCH",
            static_result["problemCodes"],
        )

    def test_unverified_resolver_legality_cannot_be_promoted(self):
        snapshot = resolver_snapshot()
        snapshot["aggregateLegality"]["status"] = "blocked"
        snapshot["profileReadiness"]["simcReady"] = False

        result = self.build(snapshot=snapshot)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("LOADOUT_RESOLVER_NOT_READY", result["problemCodes"])

    def test_compatibility_matcher_requires_one_unique_exact_loadout(self):
        matched = build_resolved_loadout_from_registry(
            resolver_snapshot=resolver_snapshot(),
            exact_registry=exact_registry(),
            template_scope="community",
            template_authority_identity=TEMPLATE_AUTHORITY_IDENTITY,
        )
        absent = exact_registry()
        absent["templateReferences"] = []
        missing = build_resolved_loadout_from_registry(
            resolver_snapshot=resolver_snapshot(),
            exact_registry=absent,
            template_scope="community",
            template_authority_identity=TEMPLATE_AUTHORITY_IDENTITY,
        )

        self.assertEqual(matched["status"], "ready")
        self.assertEqual(matched["resolvedLoadoutKey"], self.build()["resolvedLoadoutKey"])
        self.assertEqual(missing["status"], "blocked")
        self.assertIn(
            "LOADOUT_EXACT_TEMPLATE_MATCH_UNAVAILABLE",
            missing["problemCodes"],
        )

    def test_compatibility_matcher_never_scans_without_server_identity(self):
        with patch(
            "server.gear_resolved_loadout.build_resolved_loadout",
            wraps=build_resolved_loadout,
        ) as builder:
            result = build_resolved_loadout_from_registry(
                resolver_snapshot=resolver_snapshot(),
                exact_registry=exact_registry(),
                template_scope="community",
            )

        self.assertEqual(result["status"], "blocked")
        self.assertIn(
            "LOADOUT_EXACT_TEMPLATE_IDENTITY_REQUIRED",
            result["problemCodes"],
        )
        builder.assert_not_called()

    def test_compatibility_matcher_uses_known_template_hash_without_scanning_groups(self):
        registry = exact_registry()
        unrelated_hash = "sha256:" + ("f" * 64)
        for raw in list(registry["templateReferences"]):
            row = copy.deepcopy(raw)
            row["templateContentHash"] = unrelated_hash
            registry["templateReferences"].append(row)

        with patch(
            "server.gear_resolved_loadout.build_resolved_loadout",
            wraps=build_resolved_loadout,
        ) as builder:
            matched = build_resolved_loadout_from_registry(
                resolver_snapshot=resolver_snapshot(),
                exact_registry=registry,
                template_scope="community",
                template_content_hash=TEMPLATE_HASH,
            )

        self.assertEqual(matched["status"], "ready")
        self.assertEqual(builder.call_count, 1)
        self.assertEqual(
            builder.call_args.kwargs["template_content_hash"],
            TEMPLATE_HASH,
        )

    def test_compatibility_matcher_uses_server_template_identity_without_scanning_groups(self):
        registry = exact_registry()
        unrelated_hash = "sha256:" + ("0" * 64)
        for raw in list(registry["templateReferences"]):
            row = copy.deepcopy(raw)
            row["templateContentHash"] = unrelated_hash
            row["templateAuthorityIdentity"] = "sha256:" + ("1" * 64)
            registry["templateReferences"].append(row)

        with patch(
            "server.gear_resolved_loadout.build_resolved_loadout",
            wraps=build_resolved_loadout,
        ) as builder:
            matched = build_resolved_loadout_from_registry(
                resolver_snapshot=resolver_snapshot(),
                exact_registry=registry,
                template_scope="community",
                template_authority_identity=TEMPLATE_AUTHORITY_IDENTITY,
            )

        self.assertEqual(matched["status"], "ready")
        self.assertEqual(builder.call_count, 1)
        self.assertEqual(
            builder.call_args.kwargs["template_content_hash"],
            TEMPLATE_HASH,
        )

    def test_v2_slot_bound_envelopes_canonicalize_input_and_preserve_effect_occurrences(self):
        """Would fail if v2 sorted/deduped effect records or kept caller slot order."""
        snapshot = resolver_snapshot()
        snapshot["resolvedSlots"] = {
            "finger1": {"slot": "finger1", "itemId": "1001", "legality": {"status": "verified"}},
            "finger2": {"slot": "finger2", "itemId": "1001", "legality": {"status": "verified"}},
        }
        snapshot["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["finger1", "finger2"], "readySlots": ["finger1", "finger2"]}
        left = "exact-authority:sha256:" + "1" * 64
        right = "exact-authority:sha256:" + "2" * 64
        first = build_resolved_loadout_v2(
            resolver_snapshot=snapshot,
            exact_authority_by_slot=[
                {"slot": "finger2", "exactAuthorityEnvelopeKey": right},
                {"slot": "finger1", "exactAuthorityEnvelopeKey": left},
            ],
            authority_bundles={left: v2_bundle("finger1", "1001", left, ["A", "B", "A"]), right: v2_bundle("finger2", "1001", right, ["A"])},
            gear_rule_revision=RULE_REVISION,
            resolver_revision="resolver-v2",
            simc_runtime_revision="simc-runtime-v2",
            origin_catalog_revision="gear-catalog:sha256:" + "a" * 64,
        )
        second = build_resolved_loadout_v2(
            resolver_snapshot=snapshot,
            exact_authority_by_slot=list(reversed(first["exactAuthorityBySlot"])),
            authority_bundles={right: v2_bundle("finger2", "1001", right, ["A"]), left: v2_bundle("finger1", "1001", left, ["A", "B", "A"])},
            gear_rule_revision=RULE_REVISION,
            resolver_revision="resolver-v2",
            simc_runtime_revision="simc-runtime-v2",
            origin_catalog_revision="gear-catalog:sha256:" + "b" * 64,
        )
        self.assertEqual(first["status"], "ready")
        self.assertEqual(first["resolvedLoadoutKey"], second["resolvedLoadoutKey"])
        self.assertEqual([row["slot"] for row in first["exactAuthorityBySlot"]], ["finger1", "finger2"])
        self.assertEqual([row["subjectKey"] for row in first["effectEvidenceByOccurrence"]], ["A", "B", "A", "A"])
        self.assertEqual(verify_resolved_loadout_v2(first), [])

    def test_v2_rejects_reused_envelope_and_noncanonical_payload_order(self):
        """Would fail if an envelope could escape its progression slot binding."""
        snapshot = resolver_snapshot()
        snapshot["resolvedSlots"] = {
            "trinket1": {"slot": "trinket1", "itemId": "1001", "legality": {"status": "verified"}},
            "trinket2": {"slot": "trinket2", "itemId": "1001", "legality": {"status": "verified"}},
        }
        snapshot["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["trinket1", "trinket2"], "readySlots": ["trinket1", "trinket2"]}
        first_key = "exact-authority:sha256:" + "3" * 64
        blocked = build_resolved_loadout_v2(
            resolver_snapshot=snapshot,
            exact_authority_by_slot=[{"slot": "trinket1", "exactAuthorityEnvelopeKey": first_key}, {"slot": "trinket2", "exactAuthorityEnvelopeKey": first_key}],
            authority_bundles={first_key: v2_bundle("trinket1", "1001", first_key, [])},
            gear_rule_revision=RULE_REVISION,
            resolver_revision="resolver-v2",
            simc_runtime_revision="simc-runtime-v2",
        )
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("LOADOUT_EXACT_AUTHORITY_REUSED", blocked["problemCodes"])
        second_key = "exact-authority:sha256:" + "4" * 64
        ready = build_resolved_loadout_v2(
            resolver_snapshot=snapshot,
            exact_authority_by_slot=[{"slot": "trinket1", "exactAuthorityEnvelopeKey": first_key}, {"slot": "trinket2", "exactAuthorityEnvelopeKey": second_key}],
            authority_bundles={first_key: v2_bundle("trinket1", "1001", first_key, []), second_key: v2_bundle("trinket2", "1001", second_key, [])},
            gear_rule_revision=RULE_REVISION,
            resolver_revision="resolver-v2",
            simc_runtime_revision="simc-runtime-v2",
        )
        tampered = copy.deepcopy(ready)
        tampered["exactAuthorityBySlot"].reverse()
        self.assertIn("RESOLVED_LOADOUT_V2_SLOT_ORDER_INVALID", verify_resolved_loadout_v2(tampered))

        malformed = copy.deepcopy(ready)
        malformed["exactAuthorityBySlot"][0]["slot"] = "not_a_slot"
        self.assertIn("RESOLVED_LOADOUT_V2_SLOT_BINDING_INVALID", verify_resolved_loadout_v2(malformed))

    def test_v2_builder_rejects_invalid_effect_occurrence_that_verifier_rejects(self):
        """Would fail if v2 emitted a ready occurrence with empty subject identity."""
        snapshot = resolver_snapshot()
        snapshot["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        snapshot["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"]}
        key = "exact-authority:sha256:" + "5" * 64
        bundle = v2_bundle("head", "1001", key, ["A"])
        bundle["effect_support"]["subjects"][0]["subjectKey"] = ""
        result = build_resolved_loadout_v2(
            resolver_snapshot=snapshot, exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles={key: bundle}, gear_rule_revision=RULE_REVISION,
            resolver_revision="resolver-v2", simc_runtime_revision="simc-runtime-v2",
        )
        self.assertEqual(result["status"], "blocked")
        self.assertIn("LOADOUT_V2_EFFECT_RECORD_INVALID", result["problemCodes"])

    def test_v2_verifier_rejects_reordered_effect_occurrences_even_when_rehashed(self):
        """Would fail if canonical evidence order could be replaced by a valid hash."""
        snapshot = resolver_snapshot()
        snapshot["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        snapshot["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"]}
        key = "exact-authority:sha256:" + "6" * 64
        ready = build_resolved_loadout_v2(
            resolver_snapshot=snapshot, exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles={key: v2_bundle("head", "1001", key, ["A", "B"])}, gear_rule_revision=RULE_REVISION,
            resolver_revision="resolver-v2", simc_runtime_revision="simc-runtime-v2",
        )
        tampered = copy.deepcopy(ready)
        tampered["effectEvidenceByOccurrence"].reverse()
        identity = {"classKey": "mage", "specKey": "arcane", "exactAuthorityBySlot": tampered["exactAuthorityBySlot"], "effectEvidenceByOccurrence": tampered["effectEvidenceByOccurrence"], "gearRuleRevision": RULE_REVISION, "resolverRevision": "resolver-v2", "simcRuntimeRevision": "simc-runtime-v2"}
        tampered["resolvedLoadoutKey"] = resolved_loadout_module._hash("resolved-loadout-v2:sha256:", identity)
        tampered["rowHash"] = resolved_loadout_module._hash("sha256:", {key: value for key, value in tampered.items() if key not in {"rowHash", "originCatalogRevision"}})
        self.assertIn("RESOLVED_LOADOUT_V2_EFFECT_ORDER_INVALID", verify_resolved_loadout_v2(tampered))

    def test_v2_binds_pair_to_genuine_sealed_envelope_and_reuses_duplicate_record_key(self):
        """Would fail if a bundle alias or duplicate support occurrence were synthetic."""
        snapshot = resolver_snapshot()
        snapshot["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        snapshot["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"]}
        bundle = authority_bundle()
        key = bundle.envelope.content_key
        ready = build_resolved_loadout_v2(
            resolver_snapshot=snapshot, exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles={key: bundle}, gear_rule_revision="gear-rule-matrix-v1", resolver_revision="resolver-v2", simc_runtime_revision="simc-2026.08.04",
        )
        self.assertEqual(ready["status"], "ready")
        occurrences = ready["effectEvidenceByOccurrence"]
        self.assertEqual([entry["subjectKey"] for entry in occurrences[1:4]], ["240892", "240893", "240892"])
        self.assertEqual(occurrences[1]["supportRecordKey"], occurrences[3]["supportRecordKey"])

        alias = "exact-authority:sha256:" + "f" * 64
        blocked = build_resolved_loadout_v2(
            resolver_snapshot=snapshot, exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": alias}],
            authority_bundles={alias: bundle}, gear_rule_revision="gear-rule-matrix-v1", resolver_revision="resolver-v2", simc_runtime_revision="simc-2026.08.04",
        )
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("LOADOUT_V2_ENVELOPE_INVALID", blocked["problemCodes"])

    def test_v2_verifier_rejects_noninteger_effect_ordinal_without_crashing(self):
        """Would fail if malformed ordinal reached integer coercion before validation."""
        snapshot = resolver_snapshot()
        snapshot["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        snapshot["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"]}
        key = "exact-authority:sha256:" + "7" * 64
        ready = build_resolved_loadout_v2(
            resolver_snapshot=snapshot, exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles={key: v2_bundle("head", "1001", key, ["A"])}, gear_rule_revision=RULE_REVISION,
            resolver_revision="resolver-v2", simc_runtime_revision="simc-runtime-v2",
        )
        ready["effectEvidenceByOccurrence"][0]["recordOrdinal"] = "zero"
        self.assertIn("RESOLVED_LOADOUT_V2_EFFECT_OCCURRENCE_INVALID", verify_resolved_loadout_v2(ready))


if __name__ == "__main__":
    unittest.main()
