import dataclasses
import json
import unittest

from server import gear_rule_matrix


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
                "allowedWeaponTypesByClassSpec": {"mage:arcane": ["staff", "dagger", "sword"]},
                "dualWieldByClassSpec": {"mage:arcane": False},
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

    def test_rule_matrix_keeps_catalyst_blocked_without_verified_capability(self):
        intent = self.intent(
            {"head": self.slot("item-head", "variant-head", catalystOptionId="catalyst-head")}
        )

        result = gear_rule_matrix.evaluate_rule_matrix(intent, self.authority())

        catalyst = self.result_for(result, "catalyst_tier_overlay")
        self.assertEqual(catalyst["status"], "blocked")
        self.assertEqual(catalyst["problems"][0]["code"], "GEAR_CATALYST_CAPABILITY_BLOCKED")

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


if __name__ == "__main__":
    unittest.main()
