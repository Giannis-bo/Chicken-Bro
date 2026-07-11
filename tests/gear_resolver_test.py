import copy
import inspect
import json
from pathlib import Path
import unittest

from server import gear_resolver


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "gear-resolver-complete-authority-v1.json"


class GearResolverTest(unittest.TestCase):
    def fixture(self):
        return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def resolve(self, fixture=None):
        fixture = fixture or self.fixture()
        return gear_resolver.resolve(fixture["intent"], fixture["authorityContext"])

    def test_resolver_rejects_malformed_intent_before_slot_resolution(self):
        fixture = self.fixture()
        fixture["intent"]["readiness"] = {"simcReady": True}

        result = self.resolve(fixture)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["resolvedSlots"], {})
        self.assertTrue(any(problem["kind"] == "INVALID_INTENT" for problem in result["problems"]))

    def test_resolver_returns_revision_conflict_without_reinterpreting_intent(self):
        fixture = self.fixture()
        context = fixture["authorityContext"]
        context["manifest"]["gearCatalogRevision"] = "gear-r18"
        context["dependencyVector"]["gearCatalogRevision"] = "gear-r18"

        result = self.resolve(fixture)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["resolvedSlots"], {})
        self.assertTrue(any(problem["kind"] == "REVISION_CONFLICT" for problem in result["problems"]))

    def test_resolver_returns_authority_unavailable_without_client_fallback(self):
        fixture = self.fixture()
        fixture["authorityContext"].pop("itemsById")
        fixture["intent"]["slots"]["head"]["stats"] = {"strength": 999999}

        result = self.resolve(fixture)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["resolvedSlots"], {})
        self.assertTrue(any(problem["kind"] == "INVALID_INTENT" for problem in result["problems"]))
        self.assertNotIn("999999", json.dumps(result))

        fixture = self.fixture()
        fixture["authorityContext"].pop("itemsById")
        result = self.resolve(fixture)
        self.assertEqual(result["status"], "unavailable")
        self.assertTrue(any(problem["kind"] == "AUTHORITY_UNAVAILABLE" for problem in result["problems"]))

    def test_resolver_keeps_missing_weapon_mode_authority_structured(self):
        fixture = self.fixture()
        fixture["authorityContext"]["ruleParameters"].pop("weaponModesByClassSpec")

        result = self.resolve(fixture)

        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["profileReadiness"]["simcReady"])
        self.assertTrue(
            any(
                problem["code"] == "GEAR_HAND_AUTHORITY_UNAVAILABLE"
                for problem in result["problems"]
            )
        )

    def test_resolver_has_no_database_or_current_facade_dependency(self):
        source = inspect.getsource(gear_resolver)
        for forbidden in ("sqlite3", "psycopg", "postgres", "websim_payload", "news_backend", "subprocess"):
            self.assertNotIn(forbidden, source)
        for name in gear_resolver.__all__:
            value = getattr(gear_resolver, name)
            if callable(value):
                self.assertNotIn("conn", inspect.signature(value).parameters)

    def test_resolved_snapshot_signatures_are_deterministic(self):
        fixture = self.fixture()
        reordered = copy.deepcopy(fixture)
        reordered["intent"] = dict(reversed(list(reordered["intent"].items())))
        reordered["authorityContext"]["itemsById"] = dict(
            reversed(list(reordered["authorityContext"]["itemsById"].items()))
        )

        first = self.resolve(fixture)
        second = self.resolve(reordered)

        self.assertEqual(first["selectionSignature"], second["selectionSignature"])
        self.assertEqual(first["resolvedGearSignature"], second["resolvedGearSignature"])
        self.assertEqual(first["staticAttributes"], second["staticAttributes"])
        self.assertEqual(first["evidenceLedger"]["claims"], second["evidenceLedger"]["claims"])

    def test_resolver_does_not_mutate_intent_or_authority_context(self):
        fixture = self.fixture()
        before = copy.deepcopy(fixture)

        self.resolve(fixture)

        self.assertEqual(fixture, before)

    def test_missing_or_invalid_static_facts_fail_closed(self):
        fixture = self.fixture()
        fixture["authorityContext"]["variantsByKey"]["variant-set-head"].pop("resolvedStats")
        result = self.resolve(fixture)
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(
            any(problem["code"] == "GEAR_VARIANT_STATS_UNAVAILABLE" for problem in result["problems"])
        )

        fixture = self.fixture()
        fixture["authorityContext"]["variantsByKey"]["variant-set-head"]["resolvedStats"]["strength"] = "90"
        result = self.resolve(fixture)
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(
            any(problem["code"] == "GEAR_STATIC_ATTRIBUTE_INVALID" for problem in result["problems"])
        )

        fixture = self.fixture()
        fixture["authorityContext"]["variantsByKey"]["variant-set-head"]["overlay"]["statDeltas"]["haste"] = -999
        result = self.resolve(fixture)
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(
            any(problem["code"] == "GEAR_STATIC_ATTRIBUTE_NEGATIVE" for problem in result["problems"])
        )

    def test_slot_pipeline_applies_base_variant_overlay_capabilities_then_enhancements(self):
        result = self.resolve()
        head = result["resolvedSlots"]["head"]

        self.assertEqual(head["resolutionStages"], ["base", "variant", "overlay", "capabilities", "enhancements"])
        self.assertEqual(head["resolvedStats"], {"haste": 35, "stamina": 130, "strength": 90})
        self.assertEqual(head["effectiveCapabilities"]["socketCount"], 1)
        self.assertEqual(head["selectedOptions"]["gemOptionIds"], ["gem-haste"])
        self.assertEqual(
            head["simcOptions"],
            {"bonus_id": "head-bonus", "gem_id": "gem-haste", "ilevel": "289"},
        )
        gem_result = next(rule for rule in result["ruleResults"] if rule["ruleId"] == "socket_and_gem")
        self.assertEqual(gem_result["status"], "verified")

    def test_resolver_preserves_all_ten_ordered_rule_results(self):
        result = self.resolve()
        self.assertEqual(len(result["ruleResults"]), 10)
        self.assertEqual([rule["order"] for rule in result["ruleResults"]], list(range(10, 101, 10)))
        self.assertTrue(all(rule["status"] == "verified" for rule in result["ruleResults"]))

    def test_resolver_blocks_cross_slot_and_unique_conflicts(self):
        fixture = self.fixture()
        ring = {
            "itemId": "item-unique-ring",
            "variantKey": "variant-unique-ring",
            "gemOptionIds": [],
            "enchantOptionId": "",
            "embellishmentOptionId": "",
            "craftedOptionId": "",
            "catalystOptionId": "",
        }
        fixture["intent"]["slots"]["finger1"] = copy.deepcopy(ring)
        fixture["intent"]["slots"]["finger2"] = copy.deepcopy(ring)

        result = self.resolve(fixture)

        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any(problem["code"].startswith("GEAR_UNIQUE_") for problem in result["problems"]))
        self.assertFalse(result["profileReadiness"]["simcReady"])

    def test_resolver_aggregates_canonical_item_set_ids_without_name_guessing(self):
        result = self.resolve()
        self.assertEqual(result["setState"]["itemSetCounts"], {"set:resolver": 2})

        fixture = self.fixture()
        for item_id in ("item-set-head", "item-set-chest"):
            fixture["authorityContext"]["itemsById"][item_id]["itemSetId"] = ""
        for variant_key in ("variant-set-head", "variant-set-chest"):
            fixture["authorityContext"]["variantsByKey"][variant_key]["overlay"]["itemSetId"] = ""
        result = self.resolve(fixture)
        self.assertEqual(result["setState"]["itemSetCounts"], {})

    def test_dynamic_set_effects_remain_effects_and_never_become_static_stats(self):
        result = self.resolve()
        self.assertEqual(
            result["setState"]["activeDynamicEffects"],
            [
                {
                    "effectId": "set:resolver:2pc",
                    "itemSetId": "set:resolver",
                    "pieces": 2,
                    "sourceRefIds": ["evidence:set:resolver"],
                }
            ],
        )
        self.assertNotIn("set:resolver:2pc", result["staticAttributes"])

    def test_resolver_sums_only_deterministic_static_attributes(self):
        result = self.resolve()
        self.assertEqual(
            result["staticAttributes"],
            {"crit": 35, "haste": 35, "mastery": 25, "stamina": 290, "strength": 320},
        )

    def test_resolver_profile_readiness_requires_legal_slots_and_serializer_capability(self):
        result = self.resolve()
        readiness = result["profileReadiness"]
        self.assertEqual(result["status"], "verified")
        self.assertEqual(readiness["status"], "verified")
        self.assertTrue(readiness["simcReady"])
        self.assertEqual(readiness["serializerRevision"], "websim-profile-compat-v1")
        self.assertEqual(readiness["simcRuntimeRevision"], "simc-v1")

        fixture = self.fixture()
        fixture["authorityContext"]["capabilities"]["serializer"]["enabled"] = False
        result = self.resolve(fixture)
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["profileReadiness"]["simcReady"])

    def test_two_hand_configuration_does_not_require_a_fake_offhand(self):
        fixture = self.fixture()
        fixture["intent"]["slots"]["main_hand"] = {
            "itemId": "item-twohand",
            "variantKey": "variant-twohand",
            "gemOptionIds": [],
            "enchantOptionId": "",
            "embellishmentOptionId": "",
            "craftedOptionId": "",
            "catalystOptionId": "",
        }
        fixture["intent"]["slots"].pop("off_hand")

        result = self.resolve(fixture)

        self.assertEqual(result["status"], "verified")
        self.assertNotIn("off_hand", result["profileReadiness"]["requiredSlots"])
        self.assertTrue(result["profileReadiness"]["simcReady"])

    def test_ranged_main_hand_does_not_require_a_fake_offhand(self):
        fixture = self.fixture()
        fixture["authorityContext"]["itemsById"]["item-ranged"] = {
            **fixture["authorityContext"]["itemsById"]["item-twohand"],
            "itemId": "item-ranged",
            "weaponType": "bow",
            "handedness": "ranged",
        }
        fixture["authorityContext"]["variantsByKey"]["variant-ranged"] = {
            **fixture["authorityContext"]["variantsByKey"]["variant-twohand"],
            "variantKey": "variant-ranged",
            "itemId": "item-ranged",
        }
        fixture["authorityContext"]["ruleParameters"]["allowedWeaponTypesByClassSpec"]["warrior:fury"].append("bow")
        fixture["authorityContext"]["ruleParameters"]["weaponModesByClassSpec"] = {"warrior:fury": "ranged"}
        fixture["intent"]["slots"]["main_hand"] = {
            "itemId": "item-ranged",
            "variantKey": "variant-ranged",
            "gemOptionIds": [],
            "enchantOptionId": "",
            "embellishmentOptionId": "",
            "craftedOptionId": "",
            "catalystOptionId": "",
        }
        fixture["intent"]["slots"].pop("off_hand")

        result = self.resolve(fixture)

        self.assertEqual(result["status"], "verified")
        self.assertNotIn("off_hand", result["profileReadiness"]["requiredSlots"])
        self.assertTrue(result["profileReadiness"]["simcReady"])

    def test_constraints_are_derived_from_effective_capabilities(self):
        result = self.resolve()
        head = result["constraints"]["slots"]["head"]
        main = result["constraints"]["slots"]["main_hand"]
        self.assertEqual(head["socketCount"], 1)
        self.assertEqual(head["socketRemaining"], 0)
        self.assertFalse(head["canEnchant"])
        self.assertTrue(main["canEnchant"])
        self.assertTrue(main["hasSelectedEnchant"])

    def test_illegal_enhancements_never_change_resolved_facts(self):
        fixture = self.fixture()
        fixture["authorityContext"]["itemsById"]["item-set-head"]["allowedGemOptionIds"] = []
        fixture["authorityContext"]["itemsById"]["item-main-sword"]["allowedEnchantOptionIds"] = []

        result = self.resolve(fixture)

        self.assertEqual(result["status"], "blocked")
        head = result["resolvedSlots"]["head"]
        main = result["resolvedSlots"]["main_hand"]
        self.assertEqual(head["resolvedStats"]["haste"], 25)
        self.assertNotIn("gem_id", head["simcOptions"])
        self.assertEqual(main["resolvedStats"]["strength"], 60)
        self.assertNotIn("enchant_id", main["simcOptions"])

    def test_conflicting_overlay_set_identity_fails_closed(self):
        fixture = self.fixture()
        fixture["authorityContext"]["variantsByKey"]["variant-set-head"]["overlay"]["itemSetId"] = "set:other"

        result = self.resolve(fixture)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["resolvedSlots"]["head"]["itemSetId"], "set:resolver")
        self.assertTrue(
            any(problem["code"] == "GEAR_OVERLAY_SET_IDENTITY_CONFLICT" for problem in result["problems"])
        )

    def test_verified_overlay_without_source_reference_fails_closed(self):
        fixture = self.fixture()
        fixture["authorityContext"]["variantsByKey"]["variant-set-head"]["overlay"]["sourceRefIds"] = []

        result = self.resolve(fixture)

        self.assertEqual(result["status"], "blocked")
        self.assertTrue(
            any(problem["code"] == "GEAR_OVERLAY_SOURCE_UNAVAILABLE" for problem in result["problems"])
        )

    def test_resolved_slot_has_locked_structured_shape_and_claim_ids(self):
        head = self.resolve()["resolvedSlots"]["head"]
        for field in (
            "slot",
            "itemId",
            "variantKey",
            "itemLevel",
            "itemSetId",
            "overlayId",
            "resolvedStats",
            "statDeltas",
            "effectiveCapabilities",
            "selectedOptions",
            "simcOptions",
            "dynamicEffects",
            "legality",
            "sourceRefIds",
            "evidenceClaimIds",
        ):
            self.assertIn(field, head)
        self.assertEqual(head["legality"], {"status": "verified", "problemCodes": []})
        self.assertTrue(head["evidenceClaimIds"])

    def test_blocked_snapshot_keeps_problems_without_claiming_profile_ready(self):
        fixture = self.fixture()
        fixture["intent"]["slots"]["head"] = {
            "itemId": "item-unique-ring",
            "variantKey": "variant-unique-ring",
            "gemOptionIds": [],
            "enchantOptionId": "",
            "embellishmentOptionId": "",
            "craftedOptionId": "",
            "catalystOptionId": "",
        }
        result = self.resolve(fixture)
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(result["problems"])
        self.assertFalse(result["profileReadiness"]["simcReady"])

    def test_resolver_emits_identity_provenance_legality_static_and_profile_claims(self):
        result = self.resolve()
        ledger = result["evidenceLedger"]
        self.assertEqual(
            tuple(ledger["claimGroups"]),
            (
                "identity_options",
                "provenance",
                "legality",
                "static_attributes",
                "profile_executability",
            ),
        )
        self.assertTrue(all(ledger["claimGroups"][group] for group in ledger["claimGroups"]))
        self.assertTrue(all(claim["status"] == "verified" for claim in ledger["claims"]))

    def test_resolver_blocks_claims_when_evidence_records_are_missing(self):
        fixture = self.fixture()
        fixture["authorityContext"]["evidenceRecordsById"].pop("evidence:option:gem")
        result = self.resolve(fixture)

        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["profileReadiness"]["simcReady"])
        self.assertTrue(any(problem["code"] == "EVIDENCE_RECORD_MISSING" for problem in result["problems"]))

    def test_aggregate_claim_dependencies_are_bounded_and_existing(self):
        ledger = self.resolve()["evidenceLedger"]
        claim_ids = {claim["claimId"] for claim in ledger["claims"]}
        for claim in ledger["claims"]:
            if claim["dependsOn"]:
                self.assertTrue(claim["claimKey"].startswith("aggregate:"))
                self.assertTrue(set(claim["dependsOn"]).issubset(claim_ids))
            elif not claim["claimKey"].startswith("aggregate:"):
                self.assertEqual(claim["dependsOn"], [])

    def test_resolver_never_generates_profile_strings_or_dps(self):
        serialized = json.dumps(self.resolve(), sort_keys=True)
        self.assertNotIn("iterations=", serialized)
        self.assertNotIn(" dps", serialized.lower())
        self.assertNotIn('"profile":', serialized)


if __name__ == "__main__":
    unittest.main()
