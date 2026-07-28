import copy
import unittest

from server.gear_resolved_loadout import (
    build_resolved_loadout,
    build_resolved_loadout_from_registry,
)


CATALOG_REVISION = "gear-catalog:sha256:" + ("2" * 64)
REGISTRY_REVISION = "gear-exact-registry:sha256:" + ("3" * 64)
RULE_REVISION = "gear-rule-matrix-v1"
HEAD_KEY = "exact-item-instance:sha256:" + ("a" * 64)
MAIN_KEY = "exact-item-instance:sha256:" + ("b" * 64)
EMPTY_SELECTION = "enhancement-selection:sha256:" + ("c" * 64)
ENCHANT_SELECTION = "enhancement-selection:sha256:" + ("d" * 64)
TEMPLATE_HASH = "sha256:" + ("e" * 64)


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
    return {
        "schemaRevision": "gear-exact-template-reference-v1",
        "catalogRevision": CATALOG_REVISION,
        "templateScope": "community",
        "templateContentHash": TEMPLATE_HASH,
        "slot": slot,
        "itemId": item_id,
        "sourceVariantKey": f"variant-{slot}",
        "exactItemInstanceKey": key if status == "verified" else "",
        "validationStatus": status,
        "problemCodes": problem_codes or [],
        "rowHash": "sha256:" + ("8" * 64 if slot == "head" else "9" * 64),
    }


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
        )
        absent = exact_registry()
        absent["templateReferences"] = []
        missing = build_resolved_loadout_from_registry(
            resolver_snapshot=resolver_snapshot(),
            exact_registry=absent,
            template_scope="community",
        )

        self.assertEqual(matched["status"], "ready")
        self.assertEqual(matched["resolvedLoadoutKey"], self.build()["resolvedLoadoutKey"])
        self.assertEqual(missing["status"], "blocked")
        self.assertIn(
            "LOADOUT_EXACT_TEMPLATE_MATCH_UNAVAILABLE",
            missing["problemCodes"],
        )


if __name__ == "__main__":
    unittest.main()
