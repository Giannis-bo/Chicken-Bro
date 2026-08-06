import copy
from dataclasses import replace
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import server.gear_resolved_loadout as resolved_loadout_module
from server import gear_resolver
from tests.gear_exact_authority_store_test import authority_bundle
from tests.gear_resolver_test import build_midnight_mage_resolver_fixture
from server.gear_exact_authority import (
    seal_exact_authority_envelope,
    seal_exact_progression,
)
from server.gear_exact_authority_store import ExactAuthorityBundle
from server.gear_exact_item_instance import (
    seal_exact_item,
    seal_exact_static_facts,
)
from server.simc_item_effect_support import (
    derive_exact_effect_subjects,
    resolve_exact_effect_support,
    seal_effect_record,
)

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


def v2_resolver_snapshot(simc_runtime_revision="simc-runtime-v2"):
    """Return a genuine clean ``resolve_v2`` result for the v2 test surface."""
    fixture = build_midnight_mage_resolver_fixture()
    intent = fixture["intent"]
    authority = fixture["authorityContext"]
    head = copy.deepcopy(intent["slots"]["head"])
    source_item_id = head["itemId"]
    head["itemId"] = "1001"
    intent["slots"] = {"head": head}
    intent["eligibilityContext"]["specKey"] = "arcane"
    item = authority["itemsById"].pop(source_item_id)
    item["itemId"] = "1001"
    item["allowedSpecKeys"] = ["arcane"]
    authority["itemsById"]["1001"] = item
    authority["variantsByKey"][head["variantKey"]]["itemId"] = "1001"
    authority["ruleParameters"]["requiredSlots"] = ["head"]
    authority["dependencyVector"]["resolverContractRevision"] = "resolver-v2"
    authority["dependencyVector"]["simcRuntimeRevision"] = simc_runtime_revision
    return gear_resolver.resolve_v2(intent, authority)


def v2_bundle(slot, item_id, subjects, *, exact_fields=None):
    """Create a genuine, sealed v2 bundle for pure-domain callers."""
    subject_index = {str(subject): index for index, subject in enumerate(dict.fromkeys(subjects))}
    gems = [str(subject) for subject in subjects]
    exact = seal_exact_item({
        "itemId": item_id,
        "declaredItemLevel": 266,
        "bonusIds": ["13334"],
        "context": "heroic",
        "gemIds": gems,
        "gemBonusIds": [str(1514 + subject_index[gem]) for gem in gems],
        "gemItemLevels": [90 + subject_index[gem] for gem in gems],
        "enchantId": "",
        "craftedStats": [],
        "embellishmentIds": [],
        "redirectedBaseStats": [],
        **(exact_fields or {}),
    }).document
    static_facts = seal_exact_static_facts(exact, {"haste_rating": 241}).document
    progression = seal_exact_progression(
        exact,
        season_revision="season-17-f131dd36ddf1",
        gear_rule_revision=RULE_REVISION,
        slot=slot,
        has_crafted_source=False,
    ).document
    records = tuple(
        seal_effect_record({
            "schemaRevision": "simc-item-effect-record-v1",
            "status": "verified",
            "subjectKind": subject.kind,
            "subjectKey": subject.key,
            "subjectVariantSignature": subject.variant_signature,
            "hasDynamicEffect": False,
            "simcRuntimeRevision": "simc-runtime-v2",
            "verifiedAt": "2026-08-05T00:00:00Z",
        }, runtime_revision="simc-runtime-v2").document
        for subject in derive_exact_effect_subjects(exact)
    )
    effect_support = resolve_exact_effect_support(
        exact,
        runtime_revision="simc-runtime-v2",
        records=records,
    ).document
    envelope = seal_exact_authority_envelope(
        exact=exact,
        static_facts=static_facts,
        progression=progression,
        effect_support=effect_support,
        resolver_revision="resolver-v2",
    ).document
    return ExactAuthorityBundle(
        exact_item=exact,
        static_facts=static_facts,
        progression=progression,
        effect_records=records,
        effect_support=effect_support,
        envelope=envelope,
    )


class GearResolvedLoadoutTest(unittest.TestCase):
    def build(self, registry=None, snapshot=None):
        return build_resolved_loadout(
            resolver_snapshot=snapshot or resolver_snapshot(),
            exact_registry=registry or exact_registry(),
            template_scope="community",
            template_content_hash=TEMPLATE_HASH,
        )

    def test_module_imports_from_direct_server_runtime_without_v2_authority_store(self):
        """Would fail if the v2-only authority store became a startup dependency."""
        server_dir = Path(__file__).resolve().parents[1] / "server"

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import gear_resolved_loadout; print(gear_resolved_loadout.RESOLVED_LOADOUT_SCHEMA_REVISION)",
            ],
            cwd=server_dir,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "resolved-loadout-v1")

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
        snapshot = v2_resolver_snapshot()
        snapshot["resolvedSlots"] = {
            "finger1": {"slot": "finger1", "itemId": "1001", "legality": {"status": "verified"}},
            "finger2": {"slot": "finger2", "itemId": "1001", "legality": {"status": "verified"}},
        }
        snapshot["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["finger1", "finger2"], "readySlots": ["finger1", "finger2"], "simcRuntimeRevision": "simc-runtime-v2"}
        left_bundle = v2_bundle("finger1", "1001", ["A", "B", "A"])
        right_bundle = v2_bundle("finger2", "1001", ["A"])
        left = left_bundle.envelope.content_key
        right = right_bundle.envelope.content_key
        first = build_resolved_loadout_v2(
            resolver_snapshot=snapshot,
            exact_authority_by_slot=[
                {"slot": "finger2", "exactAuthorityEnvelopeKey": right},
                {"slot": "finger1", "exactAuthorityEnvelopeKey": left},
            ],
            authority_bundles={left: left_bundle, right: right_bundle},
            gear_rule_revision=RULE_REVISION,
            resolver_revision="resolver-v2",
            simc_runtime_revision="simc-runtime-v2",
            origin_catalog_revision="gear-catalog:sha256:" + "a" * 64,
        )
        second = build_resolved_loadout_v2(
            resolver_snapshot=snapshot,
            exact_authority_by_slot=list(reversed(first["exactAuthorityBySlot"])),
            authority_bundles={right: right_bundle, left: left_bundle},
            gear_rule_revision=RULE_REVISION,
            resolver_revision="resolver-v2",
            simc_runtime_revision="simc-runtime-v2",
            origin_catalog_revision="gear-catalog:sha256:" + "b" * 64,
        )
        self.assertEqual(first["status"], "ready")
        self.assertEqual(first["resolvedLoadoutKey"], second["resolvedLoadoutKey"])
        self.assertEqual([row["slot"] for row in first["exactAuthorityBySlot"]], ["finger1", "finger2"])
        self.assertEqual([row["subjectKey"] for row in first["effectEvidenceByOccurrence"]], ["1001", "A", "B", "A", "1001", "A"])
        self.assertEqual(verify_resolved_loadout_v2(first, resolver_snapshot=snapshot, authority_bundles={left: left_bundle, right: right_bundle}), [])

    def test_v2_rejects_reused_envelope_and_noncanonical_payload_order(self):
        """Would fail if an envelope could escape its progression slot binding."""
        snapshot = v2_resolver_snapshot()
        snapshot["resolvedSlots"] = {
            "trinket1": {"slot": "trinket1", "itemId": "1001", "legality": {"status": "verified"}},
            "trinket2": {"slot": "trinket2", "itemId": "1001", "legality": {"status": "verified"}},
        }
        snapshot["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["trinket1", "trinket2"], "readySlots": ["trinket1", "trinket2"], "simcRuntimeRevision": "simc-runtime-v2"}
        first_bundle = v2_bundle("trinket1", "1001", [])
        first_key = first_bundle.envelope.content_key
        blocked = build_resolved_loadout_v2(
            resolver_snapshot=snapshot,
            exact_authority_by_slot=[{"slot": "trinket1", "exactAuthorityEnvelopeKey": first_key}, {"slot": "trinket2", "exactAuthorityEnvelopeKey": first_key}],
            authority_bundles={first_key: first_bundle},
            gear_rule_revision=RULE_REVISION,
            resolver_revision="resolver-v2",
            simc_runtime_revision="simc-runtime-v2",
        )
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("LOADOUT_EXACT_AUTHORITY_REUSED", blocked["problemCodes"])
        second_bundle = v2_bundle("trinket2", "1001", [])
        second_key = second_bundle.envelope.content_key
        ready = build_resolved_loadout_v2(
            resolver_snapshot=snapshot,
            exact_authority_by_slot=[{"slot": "trinket1", "exactAuthorityEnvelopeKey": first_key}, {"slot": "trinket2", "exactAuthorityEnvelopeKey": second_key}],
            authority_bundles={first_key: first_bundle, second_key: second_bundle},
            gear_rule_revision=RULE_REVISION,
            resolver_revision="resolver-v2",
            simc_runtime_revision="simc-runtime-v2",
        )
        tampered = copy.deepcopy(ready)
        tampered["exactAuthorityBySlot"].reverse()
        self.assertIn("RESOLVED_LOADOUT_V2_SLOT_ORDER_INVALID", verify_resolved_loadout_v2(tampered, resolver_snapshot=snapshot, authority_bundles={first_key: first_bundle, second_key: second_bundle}))

        malformed = copy.deepcopy(ready)
        malformed["exactAuthorityBySlot"][0]["slot"] = "not_a_slot"
        self.assertIn("RESOLVED_LOADOUT_V2_SLOT_BINDING_INVALID", verify_resolved_loadout_v2(malformed, resolver_snapshot=snapshot, authority_bundles={first_key: first_bundle, second_key: second_bundle}))

    def test_v2_builder_rejects_invalid_effect_occurrence_that_verifier_rejects(self):
        """Would fail if v2 emitted a ready occurrence with empty subject identity."""
        snapshot = v2_resolver_snapshot()
        snapshot["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        snapshot["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"], "simcRuntimeRevision": "simc-runtime-v2"}
        bundle = v2_bundle("head", "1001", ["A"])
        key = bundle.envelope.content_key
        bundle = replace(bundle, effect_records=())
        result = build_resolved_loadout_v2(
            resolver_snapshot=snapshot, exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles={key: bundle}, gear_rule_revision=RULE_REVISION,
            resolver_revision="resolver-v2", simc_runtime_revision="simc-runtime-v2",
        )
        self.assertEqual(result["status"], "blocked")
        self.assertIn("LOADOUT_V2_AUTHORITY_BUNDLE_INVALID", result["problemCodes"])

    def test_v2_verifier_rejects_reordered_effect_occurrences_even_when_rehashed(self):
        """Would fail if canonical evidence order could be replaced by a valid hash."""
        snapshot = v2_resolver_snapshot()
        snapshot["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        snapshot["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"], "simcRuntimeRevision": "simc-runtime-v2"}
        bundle = v2_bundle("head", "1001", ["A", "B"])
        key = bundle.envelope.content_key
        ready = build_resolved_loadout_v2(
            resolver_snapshot=snapshot, exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles={key: bundle}, gear_rule_revision=RULE_REVISION,
            resolver_revision="resolver-v2", simc_runtime_revision="simc-runtime-v2",
        )
        tampered = copy.deepcopy(ready)
        tampered["effectEvidenceByOccurrence"].reverse()
        identity = {"classKey": "mage", "specKey": "arcane", "exactAuthorityBySlot": tampered["exactAuthorityBySlot"], "orderedSlots": tampered["orderedSlots"], "effectEvidenceByOccurrence": tampered["effectEvidenceByOccurrence"], "gearRuleRevision": RULE_REVISION, "resolverRevision": "resolver-v2", "simcRuntimeRevision": "simc-runtime-v2"}
        tampered["resolvedLoadoutKey"] = resolved_loadout_module._hash("resolved-loadout-v2:sha256:", identity)
        tampered["rowHash"] = resolved_loadout_module._hash("sha256:", {key: value for key, value in tampered.items() if key not in {"rowHash", "originCatalogRevision"}})
        self.assertIn("RESOLVED_LOADOUT_V2_EFFECT_ORDER_INVALID", verify_resolved_loadout_v2(tampered, resolver_snapshot=snapshot, authority_bundles={key: bundle}))

    def test_v2_binds_pair_to_genuine_sealed_envelope_and_reuses_duplicate_record_key(self):
        """Would fail if a bundle alias or duplicate support occurrence were synthetic."""
        snapshot = v2_resolver_snapshot("simc-2026.08.04")
        snapshot["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        snapshot["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"], "simcRuntimeRevision": "simc-2026.08.04"}
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
        snapshot = v2_resolver_snapshot()
        snapshot["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        snapshot["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"], "simcRuntimeRevision": "simc-runtime-v2"}
        bundle = v2_bundle("head", "1001", ["A"])
        key = bundle.envelope.content_key
        ready = build_resolved_loadout_v2(
            resolver_snapshot=snapshot, exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles={key: bundle}, gear_rule_revision=RULE_REVISION,
            resolver_revision="resolver-v2", simc_runtime_revision="simc-runtime-v2",
        )
        ready["effectEvidenceByOccurrence"][0]["recordOrdinal"] = "zero"
        self.assertIn("RESOLVED_LOADOUT_V2_EFFECT_OCCURRENCE_INVALID", verify_resolved_loadout_v2(ready, resolver_snapshot=snapshot, authority_bundles={key: bundle}))

    def test_v2_requires_one_rehydrated_bundle_dependency_closure(self):
        """Would fail if real dependencies from another bundle could be mixed in."""
        snapshot = v2_resolver_snapshot("simc-2026.08.04")
        snapshot["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        snapshot["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"], "simcRuntimeRevision": "simc-2026.08.04"}
        bundle = authority_bundle()
        other = authority_bundle("1001", gems=("999001", "999002", "999001"))
        key = bundle.envelope.content_key
        for mixed in (
            replace(bundle, exact_item=other.exact_item),
            replace(bundle, static_facts=other.static_facts),
            replace(bundle, progression=other.progression),
            replace(bundle, effect_support=other.effect_support),
            replace(bundle, effect_records=other.effect_records),
        ):
            blocked = build_resolved_loadout_v2(
                resolver_snapshot=snapshot, exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
                authority_bundles={key: mixed}, gear_rule_revision="gear-rule-matrix-v1", resolver_revision="resolver-v2", simc_runtime_revision="simc-2026.08.04",
            )
            self.assertEqual(blocked["status"], "blocked")
            self.assertIn("LOADOUT_V2_AUTHORITY_BUNDLE_INVALID", blocked["problemCodes"])

    def test_v2_rejects_synthetic_bundle_and_rehashed_nonlist_or_boolean_evidence(self):
        """Would fail if a v2 pair accepted a mapping or normalized hostile evidence."""
        snapshot = v2_resolver_snapshot("simc-2026.08.04")
        snapshot["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        snapshot["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"], "simcRuntimeRevision": "simc-2026.08.04"}
        key = "exact-authority:sha256:" + "8" * 64
        synthetic = build_resolved_loadout_v2(
            resolver_snapshot=snapshot, exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles={key: {"envelope": {"content_key": key}}}, gear_rule_revision=RULE_REVISION,
            resolver_revision="resolver-v2", simc_runtime_revision="simc-runtime-v2",
        )
        self.assertEqual(synthetic["status"], "blocked")
        self.assertIn("LOADOUT_V2_AUTHORITY_BUNDLE_INVALID", synthetic["problemCodes"])

        bundle = authority_bundle()
        key = bundle.envelope.content_key
        ready = build_resolved_loadout_v2(
            resolver_snapshot=snapshot, exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles={key: bundle}, gear_rule_revision="gear-rule-matrix-v1", resolver_revision="resolver-v2", simc_runtime_revision="simc-2026.08.04",
        )
        for hostile in ({}, None, "not-a-list"):
            tampered = copy.deepcopy(ready)
            tampered["effectEvidenceByOccurrence"] = hostile
            identity = {"classKey": "mage", "specKey": "arcane", "exactAuthorityBySlot": tampered["exactAuthorityBySlot"], "orderedSlots": tampered["orderedSlots"], "effectEvidenceByOccurrence": hostile, "gearRuleRevision": "gear-rule-matrix-v1", "resolverRevision": "resolver-v2", "simcRuntimeRevision": "simc-2026.08.04"}
            tampered["resolvedLoadoutKey"] = resolved_loadout_module._hash("resolved-loadout-v2:sha256:", identity)
            tampered["rowHash"] = resolved_loadout_module._hash("sha256:", {field: value for field, value in tampered.items() if field not in {"rowHash", "originCatalogRevision"}})
            self.assertIn("RESOLVED_LOADOUT_V2_EFFECT_EVIDENCE_INVALID", verify_resolved_loadout_v2(tampered, resolver_snapshot=snapshot, authority_bundles={key: bundle}))

        boolean_ordinal = copy.deepcopy(ready)
        boolean_ordinal["effectEvidenceByOccurrence"][0]["recordOrdinal"] = False
        identity = {"classKey": "mage", "specKey": "arcane", "exactAuthorityBySlot": boolean_ordinal["exactAuthorityBySlot"], "orderedSlots": boolean_ordinal["orderedSlots"], "effectEvidenceByOccurrence": boolean_ordinal["effectEvidenceByOccurrence"], "gearRuleRevision": "gear-rule-matrix-v1", "resolverRevision": "resolver-v2", "simcRuntimeRevision": "simc-2026.08.04"}
        boolean_ordinal["resolvedLoadoutKey"] = resolved_loadout_module._hash("resolved-loadout-v2:sha256:", identity)
        boolean_ordinal["rowHash"] = resolved_loadout_module._hash("sha256:", {field: value for field, value in boolean_ordinal.items() if field not in {"rowHash", "originCatalogRevision"}})
        self.assertIn("RESOLVED_LOADOUT_V2_EFFECT_OCCURRENCE_INVALID", verify_resolved_loadout_v2(boolean_ordinal, resolver_snapshot=snapshot, authority_bundles={key: bundle}))

    def test_v2_verifier_rejects_rehashed_deleted_genuine_trailing_occurrence(self):
        """Would fail if order checks stood in for the sealed A/B/A multiset."""
        snapshot = v2_resolver_snapshot("simc-2026.08.04")
        snapshot["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        snapshot["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"], "simcRuntimeRevision": "simc-2026.08.04"}
        bundle = authority_bundle()
        key = bundle.envelope.content_key
        ready = build_resolved_loadout_v2(
            resolver_snapshot=snapshot, exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles={key: bundle}, gear_rule_revision="gear-rule-matrix-v1", resolver_revision="resolver-v2", simc_runtime_revision="simc-2026.08.04",
        )
        self.assertIn("RESOLVED_LOADOUT_V2_AUTHORITY_CONTEXT_REQUIRED", verify_resolved_loadout_v2(ready, resolver_snapshot=snapshot))
        self.assertIn("RESOLVED_LOADOUT_V2_RESOLVER_CONTEXT_REQUIRED", verify_resolved_loadout_v2(ready, authority_bundles={key: bundle}))
        invalid_resolver = v2_resolver_snapshot("simc-runtime-other")
        invalid_resolver["resolvedSlots"] = snapshot["resolvedSlots"]
        invalid_resolver["profileReadiness"] = snapshot["profileReadiness"]
        self.assertIn("RESOLVED_LOADOUT_V2_RESOLVER_CONTEXT_INVALID", verify_resolved_loadout_v2(ready, resolver_snapshot=invalid_resolver, authority_bundles={key: bundle}))
        mixed_resolver = copy.deepcopy(snapshot)
        mixed_resolver["resolvedSlots"]["head"]["itemId"] = "9999"
        self.assertIn("RESOLVED_LOADOUT_V2_RESOLVER_CONTEXT_MISMATCH", verify_resolved_loadout_v2(ready, resolver_snapshot=mixed_resolver, authority_bundles={key: bundle}))
        self.assertIn("RESOLVED_LOADOUT_V2_AUTHORITY_CONTEXT_INVALID", verify_resolved_loadout_v2(ready, resolver_snapshot=snapshot, authority_bundles={}))
        alias = "exact-authority:sha256:" + "f" * 64
        self.assertIn("RESOLVED_LOADOUT_V2_AUTHORITY_CONTEXT_INVALID", verify_resolved_loadout_v2(ready, resolver_snapshot=snapshot, authority_bundles={alias: bundle}))
        mixed = replace(bundle, effect_records=authority_bundle("1001", gems=("999001", "999002", "999001")).effect_records)
        self.assertIn("RESOLVED_LOADOUT_V2_AUTHORITY_CONTEXT_INVALID", verify_resolved_loadout_v2(ready, resolver_snapshot=snapshot, authority_bundles={key: mixed}))
        tampered = copy.deepcopy(ready)
        tampered["effectEvidenceByOccurrence"].pop()
        identity = {"classKey": "mage", "specKey": "arcane", "exactAuthorityBySlot": tampered["exactAuthorityBySlot"], "orderedSlots": tampered["orderedSlots"], "effectEvidenceByOccurrence": tampered["effectEvidenceByOccurrence"], "gearRuleRevision": "gear-rule-matrix-v1", "resolverRevision": "resolver-v2", "simcRuntimeRevision": "simc-2026.08.04"}
        tampered["resolvedLoadoutKey"] = resolved_loadout_module._hash("resolved-loadout-v2:sha256:", identity)
        tampered["rowHash"] = resolved_loadout_module._hash("sha256:", {field: value for field, value in tampered.items() if field not in {"rowHash", "originCatalogRevision"}})
        self.assertIn("RESOLVED_LOADOUT_V2_EFFECT_EVIDENCE_CONTEXT_MISMATCH", verify_resolved_loadout_v2(tampered, resolver_snapshot=snapshot, authority_bundles={key: bundle}))

    def test_v2_verifier_rejects_rehashed_exact_execution_projection_drift(self):
        """Would fail if a real envelope could address substituted execution facts."""
        snapshot = v2_resolver_snapshot()
        snapshot["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        snapshot["profileReadiness"]["requiredSlots"] = ["head"]
        snapshot["profileReadiness"]["readySlots"] = ["head"]
        bundle = v2_bundle("head", "1001", ["A"])
        key = bundle.envelope.content_key
        ready = build_resolved_loadout_v2(
            resolver_snapshot=snapshot, exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles={key: bundle}, gear_rule_revision=RULE_REVISION,
            resolver_revision="resolver-v2", simc_runtime_revision="simc-runtime-v2",
        )

        def rehash(value):
            identity = {"classKey": "mage", "specKey": "arcane", "exactAuthorityBySlot": value["exactAuthorityBySlot"], "orderedSlots": value["orderedSlots"], "effectEvidenceByOccurrence": value["effectEvidenceByOccurrence"], "gearRuleRevision": RULE_REVISION, "resolverRevision": "resolver-v2", "simcRuntimeRevision": "simc-runtime-v2"}
            value["resolvedLoadoutKey"] = resolved_loadout_module._hash("resolved-loadout-v2:sha256:", identity)
            value["rowHash"] = resolved_loadout_module._hash("sha256:", {field: item for field, item in value.items() if field not in {"rowHash", "originCatalogRevision"}})

        item_drift = copy.deepcopy(ready)
        item_drift["orderedSlots"][0]["itemId"] = "9999"
        rehash(item_drift)
        self.assertIn("RESOLVED_LOADOUT_V2_ORDERED_SLOTS_CONTEXT_MISMATCH", verify_resolved_loadout_v2(item_drift, resolver_snapshot=snapshot, authority_bundles={key: bundle}))

        options_drift = copy.deepcopy(ready)
        options_drift["orderedSlots"][0]["simcOptions"]["bonus_id"] = "9999"
        rehash(options_drift)
        self.assertIn("RESOLVED_LOADOUT_V2_ORDERED_SLOTS_CONTEXT_MISMATCH", verify_resolved_loadout_v2(options_drift, resolver_snapshot=snapshot, authority_bundles={key: bundle}))

    def test_v2_rejects_resolver_context_with_extra_occupied_slot(self):
        """Would fail if head-only readiness silently filtered a verified main-hand slot."""
        poisoned = v2_resolver_snapshot()
        poisoned["profileReadiness"]["requiredSlots"] = ["head"]
        poisoned["profileReadiness"]["readySlots"] = ["head"]
        poisoned["resolvedSlots"]["main_hand"] = {
            **copy.deepcopy(poisoned["resolvedSlots"]["head"]),
            "slot": "main_hand",
            "itemId": "1002",
        }
        valid = copy.deepcopy(poisoned)
        valid["resolvedSlots"] = {"head": copy.deepcopy(poisoned["resolvedSlots"]["head"])}
        bundle = v2_bundle("head", "1001", ["A"])
        key = bundle.envelope.content_key
        kwargs = {
            "exact_authority_by_slot": [{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            "authority_bundles": {key: bundle},
            "gear_rule_revision": RULE_REVISION,
            "resolver_revision": "resolver-v2",
            "simc_runtime_revision": "simc-runtime-v2",
        }
        ready = build_resolved_loadout_v2(resolver_snapshot=valid, **kwargs)
        poisoned_result = build_resolved_loadout_v2(resolver_snapshot=poisoned, **kwargs)

        self.assertEqual(ready["status"], "ready")
        with self.subTest("builder"):
            self.assertEqual(poisoned_result["status"], "blocked")
            self.assertIn("LOADOUT_V2_RESOLVER_NOT_READY", poisoned_result["problemCodes"])
        with self.subTest("verifier"):
            self.assertIn("RESOLVED_LOADOUT_V2_RESOLVER_CONTEXT_INVALID", verify_resolved_loadout_v2(ready, resolver_snapshot=poisoned, authority_bundles={key: bundle}))

    def test_v2_rejects_resolver_readiness_runtime_mismatch(self):
        """Would fail if v2 accepted a ready profile bound to another SimC runtime."""
        snapshot = v2_resolver_snapshot()
        snapshot["resolvedSlots"] = {
            "head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}
        }
        snapshot["profileReadiness"] = {
            "status": "verified",
            "simcReady": True,
            "requiredSlots": ["head"],
            "readySlots": ["head"],
            "simcRuntimeRevision": "simc-runtime-v2",
        }
        bundle = v2_bundle("head", "1001", ["A"])
        key = bundle.envelope.content_key
        kwargs = {
            "exact_authority_by_slot": [{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            "authority_bundles": {key: bundle},
            "gear_rule_revision": RULE_REVISION,
            "resolver_revision": "resolver-v2",
            "simc_runtime_revision": "simc-runtime-v2",
        }
        ready = build_resolved_loadout_v2(resolver_snapshot=snapshot, **kwargs)
        self.assertEqual(ready["status"], "ready")

        mismatched = copy.deepcopy(snapshot)
        mismatched["profileReadiness"]["simcRuntimeRevision"] = "simc-runtime-other"
        blocked = build_resolved_loadout_v2(resolver_snapshot=mismatched, **kwargs)

        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("LOADOUT_V2_RESOLVER_NOT_READY", blocked["problemCodes"])
        self.assertIn(
            "RESOLVED_LOADOUT_V2_RESOLVER_CONTEXT_INVALID",
            verify_resolved_loadout_v2(
                ready,
                resolver_snapshot=mismatched,
                authority_bundles={key: bundle},
            ),
        )

    def test_v2_builder_rejects_noncanonical_authority_pair_or_bundle_closure(self):
        """Would fail if builder discarded authority fields or unrelated bundles."""
        snapshot = v2_resolver_snapshot()
        snapshot["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        snapshot["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"], "simcRuntimeRevision": "simc-runtime-v2"}
        bundle = v2_bundle("head", "1001", ["A"])
        key = bundle.envelope.content_key
        kwargs = {
            "resolver_snapshot": snapshot,
            "gear_rule_revision": RULE_REVISION,
            "resolver_revision": "resolver-v2",
            "simc_runtime_revision": "simc-runtime-v2",
        }

        malformed_pair = build_resolved_loadout_v2(
            exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key, "ignored": "x"}],
            authority_bundles={key: bundle},
            **kwargs,
        )
        self.assertEqual(malformed_pair["status"], "blocked")
        self.assertIn("LOADOUT_V2_EXACT_AUTHORITY_INVALID", malformed_pair["problemCodes"])

        unrelated_bundle = build_resolved_loadout_v2(
            exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles={key: bundle, "exact-authority:sha256:" + "f" * 64: bundle},
            **kwargs,
        )
        self.assertEqual(unrelated_bundle["status"], "blocked")
        self.assertIn("LOADOUT_V2_AUTHORITY_BUNDLE_CLOSURE_INVALID", unrelated_bundle["problemCodes"])

        unused_bundle = v2_bundle("main_hand", "1002", [])
        unused_key = unused_bundle.envelope.content_key
        genuine_unused = build_resolved_loadout_v2(
            exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles={key: bundle, unused_key: unused_bundle},
            **kwargs,
        )
        self.assertEqual(genuine_unused["status"], "blocked")
        self.assertIn("LOADOUT_V2_AUTHORITY_BUNDLE_CLOSURE_INVALID", genuine_unused["problemCodes"])

    def test_v2_loadout_serializer_input_is_authority_derived_and_verified(self):
        """Would fail if caller serializer input could differ from Exact ordered slots."""
        snapshot = v2_resolver_snapshot()
        snapshot["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        snapshot["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"], "simcRuntimeRevision": "simc-runtime-v2"}
        bundle = v2_bundle("head", "1001", ["A"])
        key = bundle.envelope.content_key
        ready = build_resolved_loadout_v2(
            resolver_snapshot=snapshot,
            exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles={key: bundle},
            gear_rule_revision=RULE_REVISION,
            resolver_revision="resolver-v2",
            simc_runtime_revision="simc-runtime-v2",
        )
        self.assertEqual(ready["status"], "ready")
        self.assertEqual(ready["serializerInput"], {"gearItems": ready["orderedSlots"]})

        tampered = copy.deepcopy(ready)
        tampered["serializerInput"] = {"gearItems": []}
        tampered["rowHash"] = resolved_loadout_module._hash("sha256:", {field: value for field, value in tampered.items() if field not in {"rowHash", "originCatalogRevision"}})
        self.assertIn("RESOLVED_LOADOUT_V2_SERIALIZER_INPUT_CONTEXT_MISMATCH", verify_resolved_loadout_v2(tampered, resolver_snapshot=snapshot, authority_bundles={key: bundle}))
    def test_v2_requires_clean_effect_boundary_and_canonical_revisions(self):
        """Would fail if v1-shaped/effect-bearing contexts or normalized revisions minted v2 rows."""
        snapshot = v2_resolver_snapshot()
        bundle = v2_bundle("head", "1001", ["A"])
        key = bundle.envelope.content_key
        kwargs = {
            "exact_authority_by_slot": [
                {"slot": "head", "exactAuthorityEnvelopeKey": key}
            ],
            "authority_bundles": {key: bundle},
            "gear_rule_revision": RULE_REVISION,
            "resolver_revision": "resolver-v2",
            "simc_runtime_revision": "simc-runtime-v2",
        }

        clean = build_resolved_loadout_v2(resolver_snapshot=snapshot, **kwargs)
        self.assertEqual(clean["status"], "ready")
        self.assertEqual(
            verify_resolved_loadout_v2(
                clean,
                resolver_snapshot=snapshot,
                authority_bundles={key: bundle},
            ),
            [],
        )

        unmarked = copy.deepcopy(snapshot)
        unmarked.pop("v2EffectBoundary", None)
        missing = build_resolved_loadout_v2(resolver_snapshot=unmarked, **kwargs)
        self.assertEqual(missing["status"], "blocked")
        self.assertIn("LOADOUT_EFFECT_AUTHORITY_REQUIRED", missing["problemCodes"])
        self.assertIn(
            "RESOLVED_LOADOUT_V2_RESOLVER_CONTEXT_INVALID",
            verify_resolved_loadout_v2(
                clean,
                resolver_snapshot=unmarked,
                authority_bundles={key: bundle},
            ),
        )

        effect_bearing = copy.deepcopy(snapshot)
        effect_bearing["setState"] = {
            "itemSetCounts": {"set-a": 1},
            "activeDynamicEffects": [
                {
                    "effectId": "set-a-1",
                    "itemSetId": "set-a",
                    "pieces": 1,
                    "sourceRefIds": [],
                }
            ],
        }
        effect_bearing["v2EffectBoundary"] = {
            "schemaRevision": "gear-resolver-v2-effect-boundary-v1",
            "status": "blocked",
            "resolvedGearSignature": effect_bearing["resolvedGearSignature"],
            "setState": effect_bearing["setState"],
            "subjects": [{"subjectKind": "set_bonus", "subjectKey": "set-a-1"}],
            "gearRuleRevision": RULE_REVISION,
            "resolverRevision": "resolver-v2",
            "simcRuntimeRevision": "simc-runtime-v2",
        }
        blocked = build_resolved_loadout_v2(
            resolver_snapshot=effect_bearing,
            **kwargs,
        )
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("LOADOUT_EFFECT_AUTHORITY_REQUIRED", blocked["problemCodes"])
        self.assertIn(
            "RESOLVED_LOADOUT_V2_RESOLVER_CONTEXT_INVALID",
            verify_resolved_loadout_v2(
                clean,
                resolver_snapshot=effect_bearing,
                authority_bundles={key: bundle},
            ),
        )

        for field, invalid in (
            ("gear_rule_revision", " gear-rule-matrix-v1 "),
            ("resolver_revision", ["resolver-v2"]),
            ("simc_runtime_revision", " simc-runtime-v2 "),
        ):
            with self.subTest(caller_field=field):
                invalid_kwargs = dict(kwargs)
                invalid_kwargs[field] = invalid
                result = build_resolved_loadout_v2(
                    resolver_snapshot=snapshot,
                    **invalid_kwargs,
                )
                self.assertEqual(result["status"], "blocked")
                self.assertIn("LOADOUT_V2_REVISION_INVALID", result["problemCodes"])

        for field, invalid in (
            ("gearRuleRevision", " gear-rule-matrix-v1 "),
            ("resolverRevision", ["resolver-v2"]),
            ("simcRuntimeRevision", " simc-runtime-v2 "),
        ):
            with self.subTest(row_field=field):
                tampered = copy.deepcopy(clean)
                tampered[field] = invalid
                identity = {
                    "classKey": "mage",
                    "specKey": "arcane",
                    "exactAuthorityBySlot": tampered["exactAuthorityBySlot"],
                    "orderedSlots": tampered["orderedSlots"],
                    "effectEvidenceByOccurrence": tampered[
                        "effectEvidenceByOccurrence"
                    ],
                    "gearRuleRevision": resolved_loadout_module._text(
                        tampered["gearRuleRevision"]
                    ),
                    "resolverRevision": resolved_loadout_module._text(
                        tampered["resolverRevision"]
                    ),
                    "simcRuntimeRevision": resolved_loadout_module._text(
                        tampered["simcRuntimeRevision"]
                    ),
                }
                tampered["resolvedLoadoutKey"] = resolved_loadout_module._hash(
                    "resolved-loadout-v2:sha256:", identity
                )
                tampered["rowHash"] = resolved_loadout_module._hash(
                    "sha256:",
                    {
                        key: value
                        for key, value in tampered.items()
                        if key not in {"rowHash", "originCatalogRevision"}
                    },
                )
                self.assertIn(
                    "RESOLVED_LOADOUT_V2_REVISION_INVALID",
                    verify_resolved_loadout_v2(
                        tampered,
                        resolver_snapshot=snapshot,
                        authority_bundles={key: bundle},
                    ),
                )


if __name__ == "__main__":
    unittest.main()
