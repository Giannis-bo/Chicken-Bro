import dataclasses
import json
import unittest

from server import gear_rule_matrix, gear_socket_authority, pg_gear_authority_loader


class GearRuleMatrixTest(unittest.TestCase):
    def slot(self, item_id, variant_key, **options):
        return {
            "itemId": item_id,
            "variantKey": variant_key,
            "gemOptionIds": options.get("gemOptionIds", []),
            "enchantOptionId": options.get("enchantOptionId", ""),
            "embellishmentOptionId": options.get("embellishmentOptionId", ""),
            "craftedOptionId": options.get("craftedOptionId", ""),
            "catalystOptionId": options.get("catalystOptionId", ""),
        }

    def intent(self, slots=None):
        return {
            "schemaRevision": "selection-intent-v1",
            "authoredAgainst": {
                "seasonRevision": "season-17-active",
                "gearCatalogRevision": "gear-r17",
            },
            "eligibilityContext": {"classKey": "mage", "specKey": "arcane", "level": 90},
            "slots": slots or {"head": self.slot("item-head", "variant-head")},
        }

    def authority(self):
        common = {
            "allowedClassKeys": ["mage"],
            "allowedSpecKeys": ["arcane"],
            "uniqueGroupId": "",
            "uniqueLimit": 0,
            "socketCount": 0,
            "allowedGemOptionIds": [],
            "allowedEnchantOptionIds": [],
            "allowedEmbellishmentOptionIds": [],
            "allowedCraftedOptionIds": [],
            "allowedCatalystOptionIds": [],
        }
        items = {
            "item-head": {
                **common,
                "itemId": "item-head",
                "allowedSlots": ["head"],
                "inventoryType": "head",
                "armorType": "cloth",
                "weaponType": "",
                "handedness": "",
                "socketCount": 1,
                "allowedGemOptionIds": ["gem-int"],
                "allowedEnchantOptionIds": ["enchant-head"],
                "allowedEmbellishmentOptionIds": ["embellishment-a"],
                "allowedCraftedOptionIds": ["crafted-a"],
                "allowedCatalystOptionIds": ["catalyst-head"],
            },
            "item-ring": {
                **common,
                "itemId": "item-ring",
                "allowedSlots": ["finger1", "finger2"],
                "inventoryType": "finger",
                "armorType": "",
                "weaponType": "",
                "handedness": "",
                "uniqueGroupId": "unique-ring",
                "uniqueLimit": 1,
                "socketCount": 1,
                "allowedGemOptionIds": ["gem-unique"],
                "allowedEnchantOptionIds": ["enchant-ring"],
            },
            "item-twohand": {
                **common,
                "itemId": "item-twohand",
                "allowedSlots": ["main_hand"],
                "inventoryType": "weapon",
                "armorType": "",
                "weaponType": "staff",
                "handedness": "two_hand",
            },
            "item-offhand": {
                **common,
                "itemId": "item-offhand",
                "allowedSlots": ["off_hand"],
                "inventoryType": "weapon",
                "armorType": "",
                "weaponType": "dagger",
                "handedness": "one_hand",
            },
        }
        return {
            "contractRevision": "gear-authority-context-v1",
            "manifest": {
                "seasonRevision": "season-17-active",
                "gearCatalogReleaseId": "gear-release-17",
                "gearCatalogRevision": "gear-r17",
            },
            "dependencyVector": {
                "seasonRevision": "season-17-active",
                "gearCatalogReleaseId": "gear-release-17",
                "gearCatalogRevision": "gear-r17",
                "gearRuleRevision": "gear-rule-matrix-v1",
                "resolverContractRevision": "gear-resolver-contract-v1",
                "serializerRevision": "serializer-v1",
                "simcRuntimeRevision": "simc-v1",
                "statPolicyRevision": "stat-policy-v1",
                "selectionSchemaRevision": "selection-intent-v1",
                "capabilityRevision": (
                    gear_socket_authority.LEGACY_CAPABILITY_REVISION
                ),
            },
            "itemsById": items,
            "variantsByKey": {
                "variant-head": {"itemId": "item-head"},
                "variant-ring": {"itemId": "item-ring"},
                "variant-twohand": {"itemId": "item-twohand"},
                "variant-offhand": {"itemId": "item-offhand"},
            },
            "optionsById": {
                "gem-int": {"optionType": "gem", "uniqueGroupId": "", "uniqueLimit": 0},
                "gem-unique": {"optionType": "gem", "uniqueGroupId": "unique-gem", "uniqueLimit": 1},
                "enchant-head": {"optionType": "enchant"},
                "enchant-ring": {"optionType": "enchant"},
                "embellishment-a": {"optionType": "embellishment"},
                "crafted-a": {"optionType": "crafted"},
                "catalyst-head": {"optionType": "catalyst", "capabilityRevision": "catalyst-proof-v1"},
            },
            "ruleParameters": {
                "inventoryTypesBySlot": {
                    "head": ["head"],
                    "finger1": ["finger"],
                    "finger2": ["finger"],
                    "main_hand": ["weapon"],
                    "off_hand": ["weapon", "offhand"],
                },
                "allowedArmorTypesByClass": {"mage": ["cloth"]},
                "armorRestrictedSlots": ["head", "shoulder", "chest", "wrist", "hands", "waist", "legs", "feet"],
                "allowedWeaponTypesByClassSpec": {"mage:arcane": ["staff", "dagger", "sword"]},
                "dualWieldByClassSpec": {"mage:arcane": False},
                "weaponModesByClassSpec": {"mage:arcane": "caster_1h_or_staff"},
                "uniqueLimits": {"unique-ring": 1},
                "uniqueGemLimits": {"unique-gem": 1},
                "runeforgeAllowedClassSpecs": [],
                "embellishmentLimit": 2,
                "catalystRevision": "catalyst-proof-v1",
                "crossSlotBlockers": [],
                "setAggregationInputs": [],
            },
            "capabilities": {
                "catalyst": {"enabled": False, "revision": "catalyst-proof-v1"},
            },
            "evidenceRecordsById": {},
            "missingFields": [],
        }

    def result_for(self, evaluation, rule_id):
        return next(result for result in evaluation["results"] if result["ruleId"] == rule_id)

    def test_rule_matrix_registers_ten_rules_in_approved_order(self):
        rules = gear_rule_matrix.ordered_rule_matrix()

        self.assertEqual([rule.order for rule in rules], list(range(10, 101, 10)))
        self.assertEqual(
            [rule.rule_id for rule in rules],
            [
                "season_release_identity",
                "slot_inventory_type",
                "class_spec_armor_weapon",
                "weapon_hand_configuration",
                "unique_equipped",
                "socket_and_gem",
                "enchant_and_runeforge",
                "embellishment_and_crafted",
                "catalyst_tier_overlay",
                "cross_slot_set_aggregate",
            ],
        )

    def test_every_rule_has_revision_scope_parameters_sources_code_and_explicit_evaluator(self):
        for rule in gear_rule_matrix.ordered_rule_matrix():
            with self.subTest(rule=rule.rule_id):
                self.assertTrue(dataclasses.is_dataclass(rule))
                self.assertEqual(rule.rule_revision, "gear-rule-matrix-v1")
                self.assertTrue(rule.scope)
                self.assertTrue(rule.parameters)
                self.assertTrue(rule.authority_source_refs)
                self.assertRegex(rule.blocker_code, r"^GEAR_[A-Z]+_$")
                self.assertTrue(callable(rule.evaluator))
                self.assertNotEqual(rule.evaluator.__name__, "<lambda>")
                with self.assertRaises(dataclasses.FrozenInstanceError):
                    rule.order = 999

    def test_rule_matrix_revision_is_deterministic(self):
        first = gear_rule_matrix.ordered_rule_matrix()
        second = gear_rule_matrix.ordered_rule_matrix()

        self.assertEqual(gear_rule_matrix.RULE_MATRIX_REVISION, "gear-rule-matrix-v1")
        self.assertEqual(first, second)
        self.assertEqual([rule.rule_revision for rule in first], [gear_rule_matrix.RULE_MATRIX_REVISION] * 10)

    def test_rule_matrix_missing_authority_fails_before_selection_rules(self):
        authority = self.authority()
        authority.pop("itemsById")

        result = gear_rule_matrix.evaluate_rule_matrix(self.intent(), authority)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["ruleId"], "season_release_identity")
        self.assertEqual(result["results"][0]["problems"][0]["kind"], "AUTHORITY_UNAVAILABLE")

    def test_rule_matrix_blocks_item_in_wrong_slot_with_stable_code(self):
        result = gear_rule_matrix.evaluate_rule_matrix(
            self.intent({"head": self.slot("item-ring", "variant-ring")}),
            self.authority(),
        )

        slot_rule = self.result_for(result, "slot_inventory_type")
        self.assertEqual(slot_rule["status"], "blocked")
        self.assertEqual(slot_rule["problems"][0]["code"], "GEAR_SLOT_NOT_ALLOWED")

    def test_rule_matrix_blocks_class_spec_armor_or_weapon_mismatch(self):
        intent = self.intent()
        intent["eligibilityContext"]["specKey"] = "fire"

        result = gear_rule_matrix.evaluate_rule_matrix(intent, self.authority())

        eligibility_rule = self.result_for(result, "class_spec_armor_weapon")
        self.assertEqual(eligibility_rule["status"], "blocked")
        self.assertTrue(all(problem["code"].startswith("GEAR_ELIGIBILITY_") for problem in eligibility_rule["problems"]))

    def test_rule_matrix_fails_closed_when_new_slot_or_weapon_mode_authority_is_missing(self):
        authority = self.authority()
        authority["ruleParameters"].pop("armorRestrictedSlots")

        result = gear_rule_matrix.evaluate_rule_matrix(self.intent(), authority)

        armor_problem = self.result_for(result, "class_spec_armor_weapon")["problems"][0]
        self.assertEqual(armor_problem["kind"], "AUTHORITY_UNAVAILABLE")
        self.assertEqual(armor_problem["code"], "GEAR_ELIGIBILITY_AUTHORITY_UNAVAILABLE")

        authority = self.authority()
        authority["ruleParameters"].pop("weaponModesByClassSpec")
        result = gear_rule_matrix.evaluate_rule_matrix(self.intent(), authority)
        weapon_problem = self.result_for(result, "weapon_hand_configuration")["problems"][0]
        self.assertEqual(weapon_problem["kind"], "AUTHORITY_UNAVAILABLE")
        self.assertEqual(weapon_problem["code"], "GEAR_HAND_AUTHORITY_UNAVAILABLE")

    def test_class_armor_restriction_does_not_apply_to_cloak_or_shield_slots(self):
        authority = self.authority()
        common = authority["itemsById"]["item-head"]
        authority["itemsById"]["item-back"] = {
            **common,
            "itemId": "item-back",
            "allowedSlots": ["back"],
            "inventoryType": "back",
            "armorType": "cloth",
            "socketCount": 0,
        }
        authority["itemsById"]["item-shield"] = {
            **common,
            "itemId": "item-shield",
            "allowedSlots": ["off_hand"],
            "inventoryType": "offhand",
            "armorType": "shield",
            "weaponType": "shield",
            "socketCount": 0,
        }
        authority["variantsByKey"].update(
            {
                "variant-back": {"itemId": "item-back"},
                "variant-shield": {"itemId": "item-shield"},
            }
        )
        authority["ruleParameters"]["inventoryTypesBySlot"]["back"] = ["back"]
        authority["ruleParameters"]["allowedWeaponTypesByClassSpec"]["mage:arcane"].append("shield")

        result = gear_rule_matrix.evaluate_rule_matrix(
            self.intent(
                {
                    "back": self.slot("item-back", "variant-back"),
                    "off_hand": self.slot("item-shield", "variant-shield"),
                }
            ),
            authority,
        )

        self.assertEqual(self.result_for(result, "class_spec_armor_weapon")["problems"], [])

    def test_weapon_hand_configuration_allows_authorized_two_hand_dual_wield(self):
        authority = self.authority()
        intent = self.intent(
            {
                "main_hand": self.slot("item-twohand", "variant-twohand"),
                "off_hand": self.slot("item-off-twohand", "variant-off-twohand"),
            }
        )
        intent["eligibilityContext"].update({"classKey": "warrior", "specKey": "fury"})
        for item_id in ("item-twohand", "item-off-twohand"):
            authority["itemsById"][item_id] = {
                **authority["itemsById"]["item-twohand"],
                "itemId": item_id,
                "allowedSlots": ["main_hand", "off_hand"],
                "allowedClassKeys": ["warrior"],
                "allowedSpecKeys": ["fury"],
                "weaponType": "two-handed sword",
            }
        authority["variantsByKey"].update(
            {
                "variant-twohand": {"itemId": "item-twohand"},
                "variant-off-twohand": {"itemId": "item-off-twohand"},
            }
        )
        authority["ruleParameters"]["allowedArmorTypesByClass"]["warrior"] = ["plate"]
        authority["ruleParameters"]["allowedWeaponTypesByClassSpec"]["warrior:fury"] = ["two-handed sword"]
        authority["ruleParameters"]["dualWieldByClassSpec"]["warrior:fury"] = True
        authority["ruleParameters"]["weaponModesByClassSpec"]["warrior:fury"] = "dual_wield_2h"

        result = gear_rule_matrix.evaluate_rule_matrix(intent, authority)

        self.assertEqual(self.result_for(result, "weapon_hand_configuration")["problems"], [])

    def test_rule_matrix_blocks_two_hand_offhand_and_unique_limit_conflicts(self):
        intent = self.intent(
            {
                "main_hand": self.slot("item-twohand", "variant-twohand"),
                "off_hand": self.slot("item-offhand", "variant-offhand"),
                "finger1": self.slot("item-ring", "variant-ring"),
                "finger2": self.slot("item-ring", "variant-ring"),
            }
        )

        result = gear_rule_matrix.evaluate_rule_matrix(intent, self.authority())

        self.assertEqual(self.result_for(result, "weapon_hand_configuration")["problems"][0]["code"], "GEAR_HAND_TWO_HAND_OFFHAND_CONFLICT")
        self.assertEqual(self.result_for(result, "unique_equipped")["problems"][0]["code"], "GEAR_UNIQUE_LIMIT_EXCEEDED")

    def test_rule_matrix_blocks_unknown_gem_enchant_embellishment_or_crafted_options(self):
        intent = self.intent(
            {
                "head": self.slot(
                    "item-head",
                    "variant-head",
                    gemOptionIds=["gem-unknown"],
                    enchantOptionId="enchant-unknown",
                    embellishmentOptionId="embellishment-unknown",
                    craftedOptionId="crafted-unknown",
                )
            }
        )

        result = gear_rule_matrix.evaluate_rule_matrix(intent, self.authority())

        self.assertEqual(self.result_for(result, "socket_and_gem")["problems"][0]["code"], "GEAR_GEM_OPTION_UNKNOWN")
        self.assertEqual(self.result_for(result, "enchant_and_runeforge")["problems"][0]["code"], "GEAR_ENCHANT_OPTION_UNKNOWN")
        craft_codes = {problem["code"] for problem in self.result_for(result, "embellishment_and_crafted")["problems"]}
        self.assertEqual(craft_codes, {"GEAR_CRAFT_EMBELLISHMENT_UNKNOWN", "GEAR_CRAFT_OPTION_UNKNOWN"})

    def test_customizable_crafted_variant_requires_its_resolver_option(self):
        authority = self.authority()
        authority["variantsByKey"]["variant-head"].update(
            {
                "status": "verified",
                "capabilityOverrides": {"requiresCraftedOption": True},
            }
        )

        missing = gear_rule_matrix.evaluate_rule_matrix(
            self.intent({"head": self.slot("item-head", "variant-head")}),
            authority,
        )
        selected = gear_rule_matrix.evaluate_rule_matrix(
            self.intent(
                {
                    "head": self.slot(
                        "item-head",
                        "variant-head",
                        craftedOptionId="crafted-a",
                    )
                }
            ),
            authority,
        )

        self.assertEqual(
            [
                problem["code"]
                for problem in self.result_for(
                    missing,
                    "embellishment_and_crafted",
                )["problems"]
            ],
            ["GEAR_CRAFT_OPTION_REQUIRED"],
        )
        self.assertEqual(
            self.result_for(
                selected,
                "embellishment_and_crafted",
            )["problems"],
            [],
        )

    def test_rule_matrix_keeps_catalyst_blocked_without_verified_capability(self):
        intent = self.intent(
            {"head": self.slot("item-head", "variant-head", catalystOptionId="catalyst-head")}
        )

        result = gear_rule_matrix.evaluate_rule_matrix(intent, self.authority())

        catalyst = self.result_for(result, "catalyst_tier_overlay")
        self.assertEqual(catalyst["status"], "blocked")
        self.assertEqual(catalyst["problems"][0]["code"], "GEAR_CATALYST_CAPABILITY_BLOCKED")

    def test_rule_matrix_uses_verified_overlay_capabilities_before_options(self):
        authority = self.authority()
        authority["itemsById"]["item-head"]["socketCount"] = 0
        authority["itemsById"]["item-head"]["baseCapabilities"] = {"socketCount": 0}
        authority["variantsByKey"]["variant-head"].update(
            {
                "status": "verified",
                "overlay": {
                    "status": "verified",
                    "capabilityOverrides": {"socketCount": 1},
                },
            }
        )
        intent = self.intent(
            {"head": self.slot("item-head", "variant-head", gemOptionIds=["gem-int"])}
        )

        result = gear_rule_matrix.evaluate_rule_matrix(intent, authority)

        gem_rule = self.result_for(result, "socket_and_gem")
        self.assertEqual(gem_rule["status"], "verified")
        self.assertEqual(gem_rule["problems"], [])

    def test_socket_rule_uses_v2_exact_variant_capacity(self):
        authority = self.authority()
        authority["dependencyVector"]["capabilityRevision"] = (
            gear_socket_authority.CAPABILITY_REVISION
        )
        evidence = {}
        authority["variantsByKey"]["variant-head"] = (
            pg_gear_authority_loader._project_variant(
                "item-head",
                "variant-head",
                {
                    "id": "variant-row-head",
                    "itemId": "item-head",
                    "variantKey": "variant-head",
                    "itemLevel": 289,
                    "status": "verified",
                    "simcOptions": {"gem_id": "240001/240002/240003"},
                    "payload": {
                        "capabilityOverrides": {"socketCount": 2},
                        "socketEvidence": {
                            "schemaRevision": (
                                gear_socket_authority.SOCKET_FACT_SCHEMA_REVISION
                            ),
                            "authorityRevision": gear_socket_authority.CAPABILITY_REVISION,
                            "minimumTotal": 2,
                            "claims": [
                                {
                                    "minimumTotal": 2,
                                    "scope": "exact_variant",
                                    "source": "observed_gem_occupancy",
                                    "sourceRevision": "observed-variant-r1",
                                }
                            ],
                        },
                        "overlay": {
                            "status": "verified",
                            "statDeltas": {"haste": 5},
                            "capabilityOverrides": {
                                "socketCount": 9,
                                "canEmbellish": True,
                            },
                        },
                    },
                },
                [],
                evidence,
                authority["dependencyVector"]["capabilityRevision"],
            )
        )
        gem_ids = ["gem-int", "gem-second", "gem-third"]
        authority["itemsById"]["item-head"]["allowedGemOptionIds"] = gem_ids
        authority["optionsById"].update(
            {
                "gem-second": {
                    "optionType": "gem",
                    "uniqueGroupId": "",
                    "uniqueLimit": 0,
                },
                "gem-third": {
                    "optionType": "gem",
                    "uniqueGroupId": "",
                    "uniqueLimit": 0,
                },
            }
        )
        intent = self.intent(
            {
                "head": self.slot(
                    "item-head",
                    "variant-head",
                    gemOptionIds=gem_ids,
                )
            }
        )

        result = gear_rule_matrix.evaluate_rule_matrix(intent, authority)

        gem_rule = self.result_for(result, "socket_and_gem")
        self.assertEqual(gem_rule["status"], "blocked")
        self.assertEqual(
            gem_rule["problems"][0]["code"],
            "GEAR_GEM_SOCKET_CAPACITY_EXCEEDED",
        )
        projected_overlay = authority["variantsByKey"]["variant-head"]["overlay"]
        self.assertEqual(projected_overlay["statDeltas"], {"haste": 5})
        self.assertTrue(
            projected_overlay["capabilityOverrides"]["canEmbellish"]
        )
        self.assertNotIn(
            "socketCount",
            projected_overlay["capabilityOverrides"],
        )

        fallback_authority = self.authority()
        fallback_authority["dependencyVector"]["capabilityRevision"] = (
            gear_socket_authority.CAPABILITY_REVISION
        )
        fallback_authority["variantsByKey"]["variant-head"] = (
            pg_gear_authority_loader._project_variant(
                "item-head",
                "variant-head",
                {
                    "id": "variant-row-head-missing-fact",
                    "itemId": "item-head",
                    "variantKey": "variant-head",
                    "itemLevel": 289,
                    "status": "verified",
                    "simcOptions": {"gem_id": "240001/240002/240003"},
                    "payload": {"capabilityOverrides": {}},
                },
                [],
                {},
                fallback_authority["dependencyVector"]["capabilityRevision"],
            )
        )
        self.assertNotIn(
            "socketCount",
            fallback_authority["variantsByKey"]["variant-head"][
                "capabilityOverrides"
            ],
        )
        fallback_result = gear_rule_matrix.evaluate_rule_matrix(
            self.intent(
                {
                    "head": self.slot(
                        "item-head",
                        "variant-head",
                        gemOptionIds=["gem-int"],
                    )
                }
            ),
            fallback_authority,
        )
        fallback_gem_rule = self.result_for(fallback_result, "socket_and_gem")
        self.assertEqual(fallback_gem_rule["status"], "verified")
        self.assertEqual(fallback_gem_rule["problems"], [])

    def test_rule_matrix_returns_all_ordered_results_without_resolving_attributes(self):
        authority = self.authority()
        authority["ruleParameters"]["crossSlotBlockers"] = [
            {
                "requiredItemIds": ["item-head", "item-ring"],
                "code": "GEAR_AGGREGATE_FORBIDDEN_COMBINATION",
                "detail": "Authoritative forbidden combination.",
            }
        ]
        intent = self.intent(
            {
                "head": self.slot("item-head", "variant-head"),
                "finger1": self.slot("item-ring", "variant-ring"),
            }
        )

        result = gear_rule_matrix.evaluate_rule_matrix(intent, authority)

        self.assertEqual([entry["ruleId"] for entry in result["results"]], [rule.rule_id for rule in gear_rule_matrix.ordered_rule_matrix()])
        self.assertEqual(self.result_for(result, "cross_slot_set_aggregate")["problems"][0]["code"], "GEAR_AGGREGATE_FORBIDDEN_COMBINATION")
        serialized = json.dumps(result, sort_keys=True)
        for forbidden in ("resolvedInstances", "attributes", "itemSetId", "evidenceClaims", "simcLines", "readiness"):
            self.assertNotIn(forbidden, serialized)

    def test_s2_aggregate_requires_verified_set_membership(self):
        authority = self.authority()
        s2_revision = "season-midnight-season-2:fixture"
        authority["manifest"]["seasonRevision"] = s2_revision
        authority["dependencyVector"]["seasonRevision"] = s2_revision
        intent = self.intent()
        intent["authoredAgainst"]["seasonRevision"] = s2_revision

        missing = gear_rule_matrix.evaluate_rule_matrix(intent, authority)
        aggregate = self.result_for(missing, "cross_slot_set_aggregate")
        self.assertEqual(aggregate["status"], "blocked")
        self.assertEqual(
            aggregate["problems"][0]["code"],
            "GEAR_AGGREGATE_SET_MEMBERSHIP_UNAVAILABLE",
        )

        authority["setMembership"] = {
            "schemaRevision": "season-set-membership-v1",
            "status": "verified",
            "seasonRevision": s2_revision,
            "setMembershipRevision": "s2-sets:sha256:fixture",
            "itemsById": {},
        }
        verified = gear_rule_matrix.evaluate_rule_matrix(intent, authority)
        self.assertEqual(
            self.result_for(verified, "cross_slot_set_aggregate")["status"],
            "verified",
        )

    def test_rule_matrix_exposes_active_set_effect_subjects_in_canonical_order(self):
        """Would fail if tier/set subjects were hidden from the v2 fail-closed boundary."""
        authority = self.authority()
        authority["itemsById"]["item-head"]["itemSetId"] = "set-a"
        authority["ruleParameters"]["setAggregationInputs"] = [{
            "itemSetId": "set-a", "memberItemIds": ["item-head"],
            "thresholds": [{"pieces": 1, "effectId": "set-a-1"}],
        }]
        subjects = gear_rule_matrix.loadout_effect_subjects(
            self.intent({"head": self.slot("item-head", "variant-head")}), authority
        )
        self.assertEqual(subjects, [{
            "subjectKind": "set_bonus",
            "itemSetId": "set-a",
            "pieces": 1,
            "subjectKey": "set-a-1",
        }])

    def test_loadout_effect_subjects_uses_effective_active_set_state(self):
        """Would fail if v2 recounted raw fields instead of Resolver's effective set state."""
        authority = self.authority()
        authority["itemsById"]["item-head"]["itemSetId"] = ""
        authority["ruleParameters"]["setAggregationInputs"] = [{
            "itemSetId": "set-a",
            "memberItemIds": [],
            "thresholds": [
                {"pieces": 1, "effectId": "set-a-1"},
            ],
        }]

        subjects = gear_rule_matrix.loadout_effect_subjects(
            self.intent({"head": self.slot("item-head", "variant-head")}),
            authority,
            effective_set_state={
                "itemSetCounts": {"set-a": 1},
                "activeDynamicEffects": [
                    {
                        "effectId": "set-a-1",
                        "itemSetId": "set-a",
                        "pieces": 1,
                        "sourceRefIds": [],
                    }
                ],
            },
        )

        self.assertEqual(subjects, [{
            "subjectKind": "set_bonus",
            "itemSetId": "set-a",
            "pieces": 1,
            "subjectKey": "set-a-1",
        }])

    def test_loadout_effect_subjects_preserves_sorted_duplicate_set_occurrences(self):
        """Would fail if the projection deduped or reordered active occurrences."""
        authority = self.authority()
        authority["ruleParameters"]["setAggregationInputs"] = [
            {
                "itemSetId": "set-a",
                "thresholds": [
                    {"pieces": 1, "effectId": "effect-a"},
                    {
                        "pieces": 1,
                        "effectId": "effect-a",
                        "subjectKind": "set_bonus",
                    },
                ],
            },
            {
                "itemSetId": "set-b",
                "thresholds": [
                    {"pieces": 2, "effectId": "effect-b"},
                ],
            },
        ]

        subjects = gear_rule_matrix.loadout_effect_subjects(
            self.intent({"head": self.slot("item-head", "variant-head")}),
            authority,
            effective_set_state={
                "activeDynamicEffects": [
                    {"effectId": "effect-b", "itemSetId": "set-b", "pieces": 2},
                    {"effectId": "effect-a", "itemSetId": "set-a", "pieces": 1},
                    {"effectId": "effect-a", "itemSetId": "set-a", "pieces": 1},
                ],
            },
        )

        self.assertEqual(subjects, [
            {
                "subjectKind": "set_bonus",
                "itemSetId": "set-a",
                "pieces": 1,
                "subjectKey": "effect-a",
            },
            {
                "subjectKind": "set_bonus",
                "itemSetId": "set-a",
                "pieces": 1,
                "subjectKey": "effect-a",
            },
            {
                "subjectKind": "set_bonus",
                "itemSetId": "set-b",
                "pieces": 2,
                "subjectKey": "effect-b",
            },
        ])

    def test_loadout_effect_subjects_rejects_missing_malformed_or_ambiguous_raw_match(self):
        """Would fail if v2 inferred set_bonus from an ungoverned raw occurrence."""
        effect = {
            "effectId": "effect-a",
            "itemSetId": "set-a",
            "pieces": 1,
            "sourceRefIds": [],
        }
        cases = {
            "missing": [],
            "malformed": [{
                "itemSetId": "set-a",
                "thresholds": [{
                    "pieces": 1,
                    "effectId": "effect-a",
                    "subjectKind": ["set_bonus"],
                }],
            }],
            "ambiguous": [{
                "itemSetId": "set-a",
                "thresholds": [
                    {
                        "pieces": 1,
                        "effectId": "effect-a",
                        "subjectKind": "set_bonus",
                    },
                    {
                        "pieces": 1,
                        "effectId": "effect-a",
                        "subjectKind": "trinket",
                    },
                ],
            }],
            "non-set-bonus": [{
                "itemSetId": "set-a",
                "thresholds": [{
                    "pieces": 1,
                    "effectId": "effect-a",
                    "subjectKind": "trinket",
                }],
            }],
        }

        for label, raw_inputs in cases.items():
            with self.subTest(label):
                authority = self.authority()
                authority["ruleParameters"][
                    "setAggregationInputs"
                ] = raw_inputs
                effects = [effect, effect] if label == "ambiguous" else [effect]

                subjects = gear_rule_matrix.loadout_effect_subjects(
                    self.intent({"head": self.slot("item-head", "variant-head")}),
                    authority,
                    effective_set_state={"activeDynamicEffects": effects},
                )

                self.assertEqual(subjects, [])


if __name__ == "__main__":
    unittest.main()
