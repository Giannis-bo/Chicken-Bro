import copy
import inspect
import json
from pathlib import Path
import unittest

from server import gear_resolver, gear_rule_matrix, gear_socket_authority, pg_gear_authority_loader


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "gear-resolver-complete-authority-v1.json"
MIDNIGHT_SOCKET_FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "midnight-mage-frost-socket-evidence-v1.json"
)


def build_midnight_mage_resolver_fixture(
    selected_gem_count=0,
    *,
    include_reference_enhancements=False,
):
    socket_fixture = json.loads(
        MIDNIGHT_SOCKET_FIXTURE_PATH.read_text(encoding="utf-8")
    )
    reference = socket_fixture["referenceContract"]
    materialized = gear_socket_authority.materialize_gear_socket_facts(
        socket_fixture["snapshot"],
        season_revision=socket_fixture["seasonRevision"],
        socket_bonus_minimums=socket_fixture["socketBonusMinimums"],
    )
    items_by_id = {row["itemId"]: row for row in materialized["items"]}
    variants_by_key = {
        row["variantKey"]: row for row in materialized["variants"]
    }
    socket_instances = {
        instance["slot"]: instance for instance in socket_fixture["expectedInstances"]
    }
    item_by_slot = {
        row["slot"]: row
        for row in materialized["items"]
        if row.get("slot") in reference["requiredSlots"]
        and row.get("itemId") != "different-ring-one"
    }
    variant_by_item = {
        row["itemId"]: row
        for row in materialized["variants"]
        if row.get("itemId") != "different-ring-one"
    }
    instances = []
    for slot in reference["requiredSlots"]:
        if slot in socket_instances:
            instances.append(socket_instances[slot])
            continue
        item = item_by_slot[slot]
        variant = variant_by_item[item["itemId"]]
        instances.append(
            {
                "slot": slot,
                "itemId": item["itemId"],
                "variantKey": variant["variantKey"],
                "socketCount": 0,
                "gemIds": [],
            }
        )

    total_socket_count = sum(
        instance["socketCount"] for instance in socket_fixture["expectedInstances"]
    )
    remaining = min(selected_gem_count, total_socket_count)
    selected_gems_by_slot = {}
    for instance in socket_fixture["expectedInstances"]:
        selected_here = min(instance["socketCount"], remaining)
        selected_gems_by_slot[instance["slot"]] = instance["gemIds"][:selected_here]
        remaining -= selected_here
    if selected_gem_count > total_socket_count:
        selected_gems_by_slot["neck"].extend(
            [reference["replacementValues"]["gemId"]]
            * (selected_gem_count - total_socket_count)
        )

    option_records = {}

    def ensure_option(option_id, option_type, simc_field, simc_value, slot):
        record = option_records.get(option_id)
        if record is None:
            unique_rule = (
                reference["uniqueGemRules"].get(simc_value, {})
                if option_type == "socket"
                else {}
            )
            record = {
                "id": f"option-{option_id}",
                "optionKey": option_id,
                "optionType": option_type,
                "name": f"Canonical {option_type} {simc_value}",
                "applicableSlots": [],
                "simcOptions": {simc_field: simc_value},
                "status": "verified",
                "isVisible": True,
                "payload": {"statDeltas": {}, **unique_rule},
                "updatedAt": "2026-07-14T00:00:00+00:00",
            }
            option_records[option_id] = record
        if slot not in record["applicableSlots"]:
            record["applicableSlots"].append(slot)

    armor_slots = {"head", "shoulder", "chest", "wrist", "hands", "waist", "legs", "feet"}
    item_rows = []
    slots = {}
    for instance in instances:
        slot = instance["slot"]
        item = items_by_id[instance["itemId"]]
        variant = variants_by_key[instance["variantKey"]]
        canonical_reference = reference["canonicalEnhancementBySlot"].get(slot, {})
        selected_gem_ids = selected_gems_by_slot.get(slot, [])
        selected_gem_options = []
        for gem_id in selected_gem_ids:
            option_id = f"gem-{gem_id}"
            selected_gem_options.append(option_id)
            ensure_option(option_id, "socket", "gem_id", gem_id, slot)

        enchant_option_id = ""
        embellishment_option_id = ""
        if include_reference_enhancements and canonical_reference.get("enchantId"):
            enchant_id = canonical_reference["enchantId"]
            enchant_option_id = f"enchant-{slot}-{enchant_id}"
            ensure_option(
                enchant_option_id,
                "enchant",
                "enchant_id",
                enchant_id,
                slot,
            )
        if include_reference_enhancements and canonical_reference.get("embellishment"):
            embellishment = canonical_reference["embellishment"]
            embellishment_option_id = f"embellishment-{embellishment}"
            ensure_option(
                embellishment_option_id,
                "embellishment",
                "embellishment",
                embellishment,
                slot,
            )
        slots[slot] = {
            "itemId": instance["itemId"],
            "variantKey": instance["variantKey"],
            "gemOptionIds": selected_gem_options,
            "enchantOptionId": enchant_option_id,
            "embellishmentOptionId": embellishment_option_id,
            "craftedOptionId": "",
            "catalystOptionId": "",
        }

        inventory_type = slot
        weapon_type = ""
        handedness = ""
        if slot == "main_hand":
            inventory_type = "weapon"
            weapon_type = "Staff"
            handedness = "two_hand"
        base_capabilities = copy.deepcopy(item["baseCapabilities"])
        base_capabilities["canEnchant"] = slot in reference["enchantEligibleSlots"]
        base_capabilities["canEmbellish"] = slot in reference["embellishmentEligibleSlots"]
        item_payload = {
            **item.get("payload", {}),
            "inventoryType": inventory_type,
            "armorType": "Cloth" if slot in armor_slots else "",
            "weaponType": weapon_type,
            "handedness": handedness,
            "allowedClassKeys": ["mage"],
            "allowedSpecKeys": ["frost"],
            "baseStats": {"intellect": 100, "stamina": 100},
            "baseCapabilities": base_capabilities,
            "socketEvidence": item["socketEvidence"],
            "socketCount": 0,
        }
        enhancement_management_fields = {}
        for simc_field in (
            "gem_id",
            "gem_bonus_id",
            "gem_ilevel",
            "enchant_id",
            "embellishment",
        ):
            if not variant.get("simcOptions", {}).get(simc_field):
                continue
            editor_managed = (
                simc_field.startswith("gem_") and canonical_reference.get("gemIds")
            ) or (
                simc_field == "enchant_id" and canonical_reference.get("enchantId")
            ) or (
                simc_field == "embellishment" and canonical_reference.get("embellishment")
            )
            enhancement_management_fields[simc_field] = (
                "editor_managed" if editor_managed else "source_only"
            )
        item_rows.append(
            (
                instance["itemId"],
                instance["variantKey"],
                {
                    "id": instance["itemId"],
                    "name": item.get("name", instance["itemId"]),
                    "slot": slot,
                    "sourceStatus": "verified",
                    "payload": item_payload,
                },
                {
                    "id": f"row-{instance['variantKey']}",
                    "itemId": instance["itemId"],
                    "slot": slot,
                    "variantKey": instance["variantKey"],
                    "itemLevel": int(variant.get("simcOptions", {}).get("ilevel", 0)),
                    "simcOptions": copy.deepcopy(variant.get("simcOptions", {})),
                    "status": "verified",
                    "payload": {
                        "resolvedStats": {"intellect": 100, "stamina": 100},
                        "capabilityOverrides": variant["capabilityOverrides"],
                        "socketEvidence": variant["socketEvidence"],
                        **(
                            {
                                "enhancementManagement": {
                                    "schemaRevision": "gear-enhancement-management-v1",
                                    "authorityRevision": gear_socket_authority.CAPABILITY_REVISION,
                                    "fields": enhancement_management_fields,
                                }
                            }
                            if enhancement_management_fields
                            else {}
                        ),
                    },
                },
                [
                    {
                        "id": f"source-{instance['variantKey']}",
                        "sourceType": "raiderio_observed_profile",
                        "sourceKey": reference["sourceKey"],
                        "seasonRevision": "season-17-active",
                        "status": "verified",
                        "updatedAt": "2026-07-14T00:00:00+00:00",
                    }
                ],
            )
        )

    intent = {
        "schemaRevision": "selection-intent-v1",
        "authoredAgainst": {
            "seasonRevision": "season-17-active",
            "gearCatalogRevision": "gear-release-17",
        },
        "eligibilityContext": {
            "classKey": reference["classKey"],
            "specKey": reference["specKey"],
            "level": reference["level"],
        },
        "slots": slots,
    }
    dependency_vector = {
        "seasonRevision": "season-17-active",
        "gearCatalogReleaseId": "gear-release-17",
        "gearCatalogRevision": "gear-release-17",
        "gearRuleRevision": "gear-rule-matrix-v1",
        "resolverContractRevision": "gear-resolver-contract-v1",
        "serializerRevision": "websim-profile-compat-v1",
        "simcRuntimeRevision": "simc-v1",
        "statPolicyRevision": "stat-snapshot-policy-v1",
        "selectionSchemaRevision": "selection-intent-v1",
        "capabilityRevision": gear_socket_authority.CAPABILITY_REVISION,
    }
    runtime = {
        "dependencyRevisions": copy.deepcopy(dependency_vector),
        "requestedClassSpec": "mage:frost",
        "playableClassSpecs": {"mage": ["frost"]},
        "ruleParameters": {
            "inventoryTypesBySlot": {
                slot: [
                    "weapon"
                    if slot == "main_hand"
                    else slot
                ]
                for slot in slots
            },
            "allowedArmorTypesByClass": {"mage": ["Cloth"]},
            "armorRestrictedSlots": sorted(armor_slots),
            "allowedWeaponTypesByClassSpec": {"mage:frost": ["Staff"]},
            "dualWieldByClassSpec": {"mage:frost": False},
            "weaponModesByClassSpec": {"mage:frost": "caster_1h_or_staff"},
            "requiredSlots": list(reference["requiredSlots"]),
            "uniqueLimits": {},
            "uniqueGemLimits": {},
            "runeforgeAllowedClassSpecs": [],
            "embellishmentLimit": reference["expectedTotals"]["embellishmentsMax"],
            "catalystRevision": "catalyst-proof-v1",
            "crossSlotBlockers": [],
            "setAggregationInputs": [],
            "sourceRefIds": ["evidence:runtime:rules"],
        },
        "capabilities": {
            "serializer": {
                "enabled": True,
                "revision": "websim-profile-compat-v1",
            },
            "catalyst": {"enabled": False, "revision": "catalyst-proof-v1"},
        },
        "sourceRefs": [
            {
                "id": "evidence:runtime:rules",
                "sourceType": "backend_policy",
                "sourceRevision": "gear-rule-matrix-v1",
            }
        ],
    }
    context = pg_gear_authority_loader.build_gear_authority_context_from_rows(
        intent,
        runtime,
        manifest={
            "contractRevision": "active-season-manifest-v1",
            "manifestType": "active",
            "formalActiveManifest": True,
            "seasonRevision": "season-17-active",
            "gearCatalogReleaseId": "gear-release-17",
            "gearCatalogRevision": "gear-release-17",
        },
        dependency_vector=dependency_vector,
        item_rows=item_rows,
        option_rows=[(option_id, record) for option_id, record in option_records.items()],
    )
    return {
        "intent": intent,
        "authorityContext": context,
        "referenceContract": reference,
        "socketInstances": socket_fixture["expectedInstances"],
        "sourceSnapshot": socket_fixture["snapshot"],
    }


class GearResolverTest(unittest.TestCase):
    def fixture(self):
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        fixture["authorityContext"]["dependencyVector"]["capabilityRevision"] = (
            gear_socket_authority.LEGACY_CAPABILITY_REVISION
        )
        return fixture

    def resolve(self, fixture=None):
        fixture = fixture or self.fixture()
        return gear_resolver.resolve(fixture["intent"], fixture["authorityContext"])

    def add_gem_option(
        self,
        fixture,
        *,
        option_id,
        simc_options,
        stat_deltas=None,
        source_ref_id="evidence:option:second-gem",
    ):
        fixture["authorityContext"]["optionsById"][option_id] = {
            "optionId": option_id,
            "optionType": "gem",
            "statDeltas": stat_deltas or {},
            "simcOptions": simc_options,
            "uniqueGroupId": "",
            "uniqueLimit": 0,
            "sourceRefIds": [source_ref_id],
        }
        fixture["authorityContext"]["evidenceRecordsById"][source_ref_id] = {
            "id": source_ref_id,
            "sourceType": "catalog_option",
            "sourceRevision": "gear-r17",
        }
        allowed = fixture["authorityContext"]["itemsById"]["item-set-head"][
            "allowedGemOptionIds"
        ]
        if option_id not in allowed:
            allowed.append(option_id)

    def enable_embellishment_slots(self, fixture, slots):
        for slot in slots:
            selection = fixture["intent"]["slots"][slot]
            item = fixture["authorityContext"]["itemsById"][selection["itemId"]]
            option_id = f"embellishment-{slot}"
            source_ref_id = f"evidence:option:{option_id}"
            fixture["authorityContext"]["optionsById"][option_id] = {
                "optionId": option_id,
                "optionType": "embellishment",
                "statDeltas": {},
                "simcOptions": {"embellishment": option_id},
                "sourceRefIds": [source_ref_id],
            }
            fixture["authorityContext"]["evidenceRecordsById"][source_ref_id] = {
                "id": source_ref_id,
                "sourceType": "catalog_option",
                "sourceRevision": "gear-r17",
            }
            item["baseCapabilities"]["canEmbellish"] = True
            item["allowedEmbellishmentOptionIds"] = [option_id]
        return fixture

    def mark_source_only_built_in_embellishment(
        self,
        fixture,
        slot,
        value="built_in_embellishment",
    ):
        fixture["authorityContext"]["dependencyVector"]["capabilityRevision"] = (
            gear_socket_authority.CAPABILITY_REVISION
        )
        selection = fixture["intent"]["slots"][slot]
        variant = fixture["authorityContext"]["variantsByKey"][
            selection["variantKey"]
        ]
        variant["simcOptions"]["embellishment"] = value
        variant["enhancementManagement"] = {
            "schemaRevision": "gear-enhancement-management-v1",
            "authorityRevision": gear_socket_authority.CAPABILITY_REVISION,
            "fields": {"embellishment": "source_only"},
        }
        return fixture

    def midnight_mage_fixture(self, selected_gem_count=0):
        return build_midnight_mage_resolver_fixture(selected_gem_count)

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

    def test_canonical_gem_uniqueness_requires_explicit_positive_integer_limit(self):
        intent = {
            "slots": {
                "neck": {"itemId": "item-neck", "variantKey": "", "gemOptionIds": ["candidate"]},
                "finger1": {"itemId": "item-ring", "variantKey": "", "gemOptionIds": ["candidate"]},
            }
        }
        base_authority = {
            "itemsById": {
                "item-neck": {"itemId": "item-neck", "socketCount": 1, "allowedGemOptionIds": ["candidate"]},
                "item-ring": {"itemId": "item-ring", "socketCount": 1, "allowedGemOptionIds": ["candidate"]},
            },
            "variantsByKey": {},
            "optionsById": {
                "candidate": {"optionType": "gem", "uniqueGroupId": "explicit_group"}
            },
            "ruleParameters": {"uniqueGemLimits": {}},
        }
        cases = (
            ("missing group", {"uniqueGroupId": "", "uniqueLimit": 1}, {}, False),
            ("boolean group", {"uniqueGroupId": True, "uniqueLimit": 1}, {}, False),
            ("numeric group", {"uniqueGroupId": 123, "uniqueLimit": 1}, {}, False),
            ("missing option limit", {"uniqueGroupId": "explicit_group"}, {}, False),
            ("junk option limit", {"uniqueGroupId": "explicit_group", "uniqueLimit": "1bad"}, {}, False),
            ("zero option limit", {"uniqueGroupId": "explicit_group", "uniqueLimit": 0}, {}, False),
            ("negative option limit", {"uniqueGroupId": "explicit_group", "uniqueLimit": -1}, {}, False),
            ("boolean option limit", {"uniqueGroupId": "explicit_group", "uniqueLimit": True}, {}, False),
            ("positive option limit", {"uniqueGroupId": "explicit_group", "uniqueLimit": 1}, {}, True),
            ("junk configured limit", {"uniqueGroupId": "explicit_group"}, {"explicit_group": "1bad"}, False),
            ("zero configured limit", {"uniqueGroupId": "explicit_group"}, {"explicit_group": 0}, False),
            ("negative configured limit", {"uniqueGroupId": "explicit_group"}, {"explicit_group": -1}, False),
            ("boolean configured limit", {"uniqueGroupId": "explicit_group"}, {"explicit_group": True}, False),
            ("non-map configured limits", {"uniqueGroupId": "explicit_group"}, [], False),
            ("positive configured limit", {"uniqueGroupId": "explicit_group"}, {"explicit_group": 1}, True),
            ("valid option with zero configured limit", {"uniqueGroupId": "explicit_group", "uniqueLimit": 1}, {"explicit_group": 0}, True),
            ("valid option with boolean configured limit", {"uniqueGroupId": "explicit_group", "uniqueLimit": 1}, {"explicit_group": True}, True),
        )
        for name, option, configured_limits, expected_blocked in cases:
            with self.subTest(name=name):
                authority = copy.deepcopy(base_authority)
                authority["optionsById"]["candidate"] = option
                authority["ruleParameters"]["uniqueGemLimits"] = configured_limits
                problems = gear_rule_matrix._socket_and_gem(intent, authority)
                self.assertEqual(
                    any(problem["code"] == "GEAR_GEM_UNIQUE_LIMIT_EXCEEDED" for problem in problems),
                    expected_blocked,
                )

        for first_limit, second_limit in ((1, 2), (2, 1)):
            with self.subTest(order=(first_limit, second_limit)):
                authority = copy.deepcopy(base_authority)
                authority["optionsById"] = {
                    "first": {
                        "optionType": "gem",
                        "uniqueGroupId": "explicit_group",
                        "uniqueLimit": first_limit,
                    },
                    "second": {
                        "optionType": "gem",
                        "uniqueGroupId": "explicit_group",
                        "uniqueLimit": second_limit,
                    },
                }
                authority["itemsById"]["item-neck"]["allowedGemOptionIds"] = ["first"]
                authority["itemsById"]["item-ring"]["allowedGemOptionIds"] = ["second"]
                ordered_intent = copy.deepcopy(intent)
                ordered_intent["slots"]["neck"]["gemOptionIds"] = ["first"]
                ordered_intent["slots"]["finger1"]["gemOptionIds"] = ["second"]

                problems = gear_rule_matrix._socket_and_gem(ordered_intent, authority)
                unique_problem = next(
                    problem
                    for problem in problems
                    if problem["code"] == "GEAR_GEM_UNIQUE_LIMIT_EXCEEDED"
                )
                self.assertEqual(unique_problem["meta"]["limit"], 1)

        mixed_group_authority = copy.deepcopy(base_authority)
        mixed_group_authority["optionsById"] = {
            "first": {"optionType": "gem", "uniqueGroupId": "explicit_group", "uniqueLimit": 2},
            "second": {"optionType": "gem", "uniqueGroupId": 123, "uniqueLimit": 1},
        }
        mixed_group_authority["itemsById"]["item-neck"]["allowedGemOptionIds"] = ["first"]
        mixed_group_authority["itemsById"]["item-ring"]["allowedGemOptionIds"] = ["second"]
        mixed_group_intent = copy.deepcopy(intent)
        mixed_group_intent["slots"]["neck"]["gemOptionIds"] = ["first"]
        mixed_group_intent["slots"]["finger1"]["gemOptionIds"] = ["second"]
        self.assertFalse(
            any(
                problem["code"] == "GEAR_GEM_UNIQUE_LIMIT_EXCEEDED"
                for problem in gear_rule_matrix._socket_and_gem(
                    mixed_group_intent,
                    mixed_group_authority,
                )
            )
        )

    def test_canonical_unique_equipped_config_requires_positive_integer_limit(self):
        intent = {
            "slots": {
                "finger1": {"itemId": "item-ring-one"},
                "finger2": {"itemId": "item-ring-two"},
            }
        }
        base_authority = {
            "itemsById": {
                "item-ring-one": {"uniqueGroupId": "explicit_group"},
                "item-ring-two": {"uniqueGroupId": "explicit_group"},
            },
            "ruleParameters": {"uniqueLimits": {}},
        }
        for name, limit, expected_blocked in (
            ("missing", None, False),
            ("junk", "1bad", False),
            ("zero", 0, False),
            ("negative", -1, False),
            ("boolean", True, False),
            ("positive", 1, True),
        ):
            with self.subTest(name=name):
                authority = copy.deepcopy(base_authority)
                if limit is not None:
                    authority["ruleParameters"]["uniqueLimits"]["explicit_group"] = limit
                problems = gear_rule_matrix._unique_equipped(intent, authority)
                self.assertEqual(
                    any(problem["code"] == "GEAR_UNIQUE_GROUP_LIMIT_EXCEEDED" for problem in problems),
                    expected_blocked,
                )

        non_map = copy.deepcopy(base_authority)
        non_map["ruleParameters"]["uniqueLimits"] = []
        self.assertFalse(
            any(
                problem["code"] == "GEAR_UNIQUE_GROUP_LIMIT_EXCEEDED"
                for problem in gear_rule_matrix._unique_equipped(intent, non_map)
            )
        )

        for invalid_group in (True, 123):
            with self.subTest(invalid_group=invalid_group):
                authority = copy.deepcopy(base_authority)
                authority["itemsById"]["item-ring-two"]["uniqueGroupId"] = invalid_group
                authority["ruleParameters"]["uniqueLimits"] = {"explicit_group": 1}
                self.assertFalse(
                    any(
                        problem["code"] == "GEAR_UNIQUE_GROUP_LIMIT_EXCEEDED"
                        for problem in gear_rule_matrix._unique_equipped(intent, authority)
                    )
                )

    def test_public_resolver_enforces_only_explicit_positive_gem_group_minimums(self):
        for name, projected_limit, expected_status in (
            ("missing", 0, "verified"),
            ("invalid projected to zero", 0, "verified"),
            ("positive", 1, "blocked"),
        ):
            with self.subTest(name=name):
                fixture = self.fixture()
                head_variant = fixture["authorityContext"]["variantsByKey"]["variant-set-head"]
                head_variant["capabilityOverrides"] = {"socketCount": 2}
                head_variant["overlay"]["capabilityOverrides"] = {}
                fixture["intent"]["slots"]["head"]["gemOptionIds"] = ["gem-haste", "gem-haste"]
                option = fixture["authorityContext"]["optionsById"]["gem-haste"]
                option["uniqueGroupId"] = "explicit_group"
                option["uniqueLimit"] = projected_limit

                result = self.resolve(fixture)

                self.assertEqual(result["status"], expected_status)
                blocked = any(
                    problem["code"] == "GEAR_GEM_UNIQUE_LIMIT_EXCEEDED"
                    for problem in result["problems"]
                )
                self.assertEqual(blocked, expected_status == "blocked")
                self.assertEqual(
                    result["profileReadiness"]["simcReady"],
                    expected_status == "verified",
                )

        for first_limit, second_limit in ((1, 2), (2, 1)):
            with self.subTest(order=(first_limit, second_limit)):
                fixture = self.fixture()
                head_variant = fixture["authorityContext"]["variantsByKey"]["variant-set-head"]
                head_variant["capabilityOverrides"] = {"socketCount": 2}
                head_variant["overlay"]["capabilityOverrides"] = {}
                first = fixture["authorityContext"]["optionsById"]["gem-haste"]
                first["uniqueGroupId"] = "explicit_group"
                first["uniqueLimit"] = first_limit
                self.add_gem_option(
                    fixture,
                    option_id="gem-second",
                    simc_options={"gem_id": "240900"},
                )
                second = fixture["authorityContext"]["optionsById"]["gem-second"]
                second["uniqueGroupId"] = "explicit_group"
                second["uniqueLimit"] = second_limit
                fixture["intent"]["slots"]["head"]["gemOptionIds"] = [
                    "gem-haste",
                    "gem-second",
                ]

                result = self.resolve(fixture)

                self.assertEqual(result["status"], "blocked")
                problem = next(
                    problem
                    for problem in result["problems"]
                    if problem["code"] == "GEAR_GEM_UNIQUE_LIMIT_EXCEEDED"
                )
                self.assertEqual(problem["meta"]["limit"], 1)
                self.assertFalse(result["profileReadiness"]["simcReady"])

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

    def test_missing_selected_enhancement_static_facts_degrades_only_the_attribute_panel(self):
        fixture = self.fixture()
        fixture["authorityContext"]["optionsById"]["gem-haste"].pop("statDeltas")

        result = self.resolve(fixture)

        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["attributeStaticFacts"]["status"], "unavailable")
        self.assertEqual(
            result["attributeStaticFacts"]["problems"][0]["code"],
            "ATTRIBUTE_STATIC_FACTS_UNAVAILABLE",
        )

    def test_slot_pipeline_applies_base_variant_overlay_capabilities_then_enhancements(self):
        result = self.resolve()
        head = result["resolvedSlots"]["head"]

        self.assertEqual(head["resolutionStages"], ["base", "variant", "overlay", "capabilities", "enhancements"])
        self.assertEqual(head["itemStaticStats"], {"haste": 25, "stamina": 130, "strength": 90})
        self.assertEqual(head["resolvedStats"], {"haste": 35, "stamina": 130, "strength": 90})
        self.assertEqual(head["effectiveCapabilities"]["socketCount"], 1)
        self.assertEqual(head["selectedOptions"]["gemOptionIds"], ["gem-haste"])
        self.assertEqual(
            head["simcOptions"],
            {"bonus_id": "head-bonus", "gem_id": "gem-haste", "ilevel": "289"},
        )
        gem_result = next(rule for rule in result["ruleResults"] if rule["ruleId"] == "socket_and_gem")
        self.assertEqual(gem_result["status"], "verified")

    def test_multiple_selected_gems_preserve_order_and_replace_variant_raw_sequences(self):
        fixture = self.fixture()
        head_variant = fixture["authorityContext"]["variantsByKey"]["variant-set-head"]
        head_variant["capabilityOverrides"] = {"socketCount": 2}
        head_variant["overlay"]["capabilityOverrides"] = {}
        head_variant["simcOptions"].update(
            {
                "gem_id": "variant-raw-one/variant-raw-two",
                "gem_bonus_id": "raw-bonus-one/raw-bonus-two",
                "gem_ilevel": "600/601",
            }
        )
        fixture["authorityContext"]["optionsById"]["gem-haste"]["simcOptions"] = {
            "gem_id": "240892",
            "gem_bonus_id": "9727",
            "gem_ilevel": "707",
        }
        self.add_gem_option(
            fixture,
            option_id="gem-versatility",
            simc_options={
                "gem_id": "240983",
                "gem_bonus_id": "9728",
                "gem_ilevel": "708",
            },
            stat_deltas={"versatility": 8},
        )
        fixture["intent"]["slots"]["head"]["gemOptionIds"] = [
            "gem-haste",
            "gem-versatility",
        ]

        result = self.resolve(fixture)
        head = result["resolvedSlots"]["head"]

        self.assertEqual(result["status"], "verified")
        self.assertEqual(
            head["selectedOptions"]["gemOptionIds"],
            ["gem-haste", "gem-versatility"],
        )
        self.assertEqual(head["simcOptions"]["gem_id"], "240892/240983")
        self.assertEqual(head["simcOptions"]["gem_bonus_id"], "9727/9728")
        self.assertEqual(head["simcOptions"]["gem_ilevel"], "707/708")
        self.assertEqual(result["constraints"]["slots"]["head"]["socketRemaining"], 0)

    def test_mixed_presence_gem_sequences_are_omitted_instead_of_compacted(self):
        fixture = self.fixture()
        head_variant = fixture["authorityContext"]["variantsByKey"]["variant-set-head"]
        head_variant["capabilityOverrides"] = {"socketCount": 2}
        head_variant["overlay"]["capabilityOverrides"] = {}
        head_variant["simcOptions"].update(
            {
                "gem_id": "variant-raw-one/variant-raw-two",
                "gem_bonus_id": "raw-bonus-one/raw-bonus-two",
                "gem_ilevel": "600/601",
            }
        )
        fixture["authorityContext"]["optionsById"]["gem-haste"]["simcOptions"] = {
            "gem_id": "A",
            "gem_ilevel": "707",
        }
        self.add_gem_option(
            fixture,
            option_id="gem-versatility",
            simc_options={"gem_id": "B", "gem_bonus_id": "B-bonus"},
        )
        fixture["intent"]["slots"]["head"]["gemOptionIds"] = [
            "gem-haste",
            "gem-versatility",
        ]

        result = self.resolve(fixture)
        simc_options = result["resolvedSlots"]["head"]["simcOptions"]

        self.assertEqual(result["status"], "verified")
        self.assertEqual(simc_options["gem_id"], "A/B")
        self.assertNotIn("gem_bonus_id", simc_options)
        self.assertNotIn("gem_ilevel", simc_options)

    def test_duplicate_selected_gem_identity_preserves_multiplicity_and_occurrence_facts(self):
        fixture = self.fixture()
        head_variant = fixture["authorityContext"]["variantsByKey"]["variant-set-head"]
        head_variant["capabilityOverrides"] = {"socketCount": 2}
        head_variant["overlay"]["capabilityOverrides"] = {}
        head_variant["simcOptions"]["gem_id"] = "variant-raw-one/variant-raw-two"
        fixture["intent"]["slots"]["head"]["gemOptionIds"] = [
            "gem-haste",
            "gem-haste",
        ]

        result = self.resolve(fixture)
        head = result["resolvedSlots"]["head"]

        self.assertEqual(result["status"], "verified")
        self.assertEqual(
            head["selectedOptions"]["gemOptionIds"],
            ["gem-haste", "gem-haste"],
        )
        self.assertEqual(head["simcOptions"]["gem_id"], "gem-haste/gem-haste")
        self.assertEqual(head["resolvedStats"]["haste"], 45)
        self.assertEqual(
            head["statDeltas"]["enhancements"],
            [
                {"optionId": "gem-haste", "statDeltas": {"haste": 10}},
                {"optionId": "gem-haste", "statDeltas": {"haste": 10}},
            ],
        )
        self.assertEqual(head["sourceRefIds"].count("evidence:option:gem"), 1)

    def test_selected_canonical_gems_clear_unproven_variant_sequence_fields(self):
        fixture = self.fixture()
        head_variant = fixture["authorityContext"]["variantsByKey"]["variant-set-head"]
        head_variant["simcOptions"].update(
            {
                "gem_id": "variant-raw-gem",
                "gem_bonus_id": "variant-raw-bonus",
                "gem_ilevel": "600",
            }
        )

        result = self.resolve(fixture)
        simc_options = result["resolvedSlots"]["head"]["simcOptions"]

        self.assertEqual(result["status"], "verified")
        self.assertEqual(simc_options["gem_id"], "gem-haste")
        self.assertNotIn("gem_bonus_id", simc_options)
        self.assertNotIn("gem_ilevel", simc_options)
        self.assertEqual(simc_options["bonus_id"], "head-bonus")

    def test_empty_gem_selection_preserves_verified_variant_raw_gem_sequences(self):
        fixture = self.fixture()
        head_variant = fixture["authorityContext"]["variantsByKey"]["variant-set-head"]
        head_variant["simcOptions"].update(
            {
                "gem_id": "240892/240983",
                "gem_bonus_id": "9727/9728",
                "gem_ilevel": "707/708",
            }
        )
        fixture["intent"]["slots"]["head"]["gemOptionIds"] = []

        result = self.resolve(fixture)
        simc_options = result["resolvedSlots"]["head"]["simcOptions"]

        self.assertEqual(result["status"], "verified")
        self.assertEqual(simc_options["gem_id"], "240892/240983")
        self.assertEqual(simc_options["gem_bonus_id"], "9727/9728")
        self.assertEqual(simc_options["gem_ilevel"], "707/708")

    def test_multi_gem_serialization_keeps_capacity_and_unknown_option_guards_fail_closed(self):
        over_capacity = self.fixture()
        over_capacity["intent"]["slots"]["head"]["gemOptionIds"] = [
            "gem-haste",
            "gem-haste",
        ]

        capacity_result = self.resolve(over_capacity)

        self.assertEqual(capacity_result["status"], "blocked")
        self.assertTrue(
            any(
                problem["code"] == "GEAR_GEM_SOCKET_CAPACITY_EXCEEDED"
                for problem in capacity_result["problems"]
            )
        )

        unknown = self.fixture()
        unknown["intent"]["slots"]["head"]["gemOptionIds"] = ["forged-gem-option"]

        unknown_result = self.resolve(unknown)

        self.assertEqual(unknown_result["status"], "blocked")
        self.assertTrue(
            any(
                problem["code"] == "GEAR_GEM_OPTION_UNKNOWN"
                for problem in unknown_result["problems"]
            )
        )

    def test_raw_client_gem_fact_never_gains_resolver_authority(self):
        fixture = self.fixture()
        fixture["intent"]["slots"]["head"]["gem_id"] = "240892/240983"

        result = self.resolve(fixture)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["resolvedSlots"], {})
        self.assertTrue(any(problem["code"] == "UNKNOWN_FIELD" for problem in result["problems"]))

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

    def test_midnight_mage_template_resolves_socket_counts_1_2_1_1_2_1(self):
        result = self.resolve(self.midnight_mage_fixture())

        self.assertEqual(result["status"], "verified")
        self.assertEqual(
            [
                result["constraints"]["slots"][slot]["socketCount"]
                for slot in ("head", "neck", "wrist", "waist", "finger1", "finger2")
            ],
            [1, 2, 1, 1, 2, 1],
        )

    def test_midnight_mage_reference_resolves_complete_editable_8_6_2_enhancements(self):
        fixture = build_midnight_mage_resolver_fixture(
            selected_gem_count=8,
            include_reference_enhancements=True,
        )
        result = self.resolve(fixture)
        reference = fixture["referenceContract"]

        self.assertEqual(reference["templateId"], "observed_profile_mage_frost")
        self.assertEqual(reference["sourceKey"], "raiderio_observed_profile")
        self.assertEqual(
            fixture["authorityContext"]["optionsById"]["gem-240983"][
                "uniqueGroupId"
            ],
            "primary_stat_gem",
        )
        self.assertEqual(
            fixture["authorityContext"]["optionsById"]["gem-240983"][
                "uniqueLimit"
            ],
            1,
        )
        self.assertEqual(result["status"], "verified")
        self.assertTrue(result["profileReadiness"]["simcReady"])
        self.assertEqual(
            result["profileReadiness"]["requiredSlots"],
            sorted(reference["requiredSlots"]),
        )
        self.assertEqual(
            result["profileReadiness"]["readySlots"],
            sorted(reference["requiredSlots"]),
        )
        self.assertEqual(len(result["serializerInput"]["gearItems"]), 15)
        self.assertEqual(
            [
                result["constraints"]["slots"][instance["slot"]]["socketCount"]
                for instance in fixture["socketInstances"]
            ],
            [instance["socketCount"] for instance in fixture["socketInstances"]],
        )
        self.assertEqual(
            [
                option_id
                for instance in fixture["socketInstances"]
                for option_id in result["resolvedSlots"][instance["slot"]][
                    "selectedOptions"
                ]["gemOptionIds"]
            ],
            [
                f"gem-{gem_id}"
                for instance in fixture["socketInstances"]
                for gem_id in instance["gemIds"]
            ],
        )
        self.assertEqual(
            sum(
                bool(slot["selectedOptions"]["enchantOptionId"])
                for slot in result["resolvedSlots"].values()
            ),
            reference["expectedTotals"]["enchantsUsed"],
        )
        self.assertEqual(
            [
                slot
                for slot, enhancement in reference["canonicalEnhancementBySlot"].items()
                if enhancement.get("enchantId")
            ],
            ["back", "chest", "legs", "feet", "finger1", "finger2"],
        )
        self.assertEqual(
            sum(
                bool(slot["selectedOptions"]["embellishmentOptionId"])
                for slot in result["resolvedSlots"].values()
            ),
            reference["expectedTotals"]["embellishmentsUsed"],
        )
        self.assertEqual(
            result["resolvedSlots"]["neck"]["simcOptions"]["gem_id"],
            "240892/240900",
        )
        self.assertEqual(
            result["resolvedSlots"]["finger1"]["simcOptions"]["gem_id"],
            "240892/240983",
        )
        self.assertEqual(
            result["resolvedSlots"]["back"]["simcOptions"]["enchant_id"],
            "4897",
        )
        self.assertEqual(
            result["resolvedSlots"]["wrist"]["simcOptions"]["embellishment"],
            "arcanoweave_lining",
        )

    def test_midnight_mage_empty_canonical_selections_remove_managed_raw_fields_only(self):
        fixture = build_midnight_mage_resolver_fixture(
            selected_gem_count=8,
            include_reference_enhancements=True,
        )
        fixture["intent"]["slots"]["head"]["gemOptionIds"] = []
        fixture["intent"]["slots"]["back"]["enchantOptionId"] = ""
        fixture["intent"]["slots"]["back"]["embellishmentOptionId"] = ""

        result = self.resolve(fixture)

        self.assertEqual(result["status"], "verified")
        self.assertEqual(
            result["resolvedSlots"]["head"]["selectedOptions"]["gemOptionIds"],
            [],
        )
        self.assertEqual(
            result["resolvedSlots"]["back"]["selectedOptions"]["enchantOptionId"],
            "",
        )
        self.assertEqual(
            result["resolvedSlots"]["back"]["selectedOptions"]["embellishmentOptionId"],
            "",
        )
        self.assertNotIn("gem_id", result["resolvedSlots"]["head"]["simcOptions"])
        self.assertNotIn("enchant_id", result["resolvedSlots"]["back"]["simcOptions"])
        self.assertNotIn("embellishment", result["resolvedSlots"]["back"]["simcOptions"])
        self.assertEqual(result["resolvedSlots"]["head"]["simcOptions"]["enchant_id"], "8017")
        self.assertEqual(result["resolvedSlots"]["shoulder"]["simcOptions"]["enchant_id"], "8001")
        self.assertEqual(result["resolvedSlots"]["waist"]["simcOptions"]["enchant_id"], "4223")
        self.assertEqual(result["resolvedSlots"]["main_hand"]["simcOptions"]["enchant_id"], "8039/8052")
        classifications_by_slot = {
            slot: fixture["authorityContext"]["variantsByKey"][selection["variantKey"]][
                "enhancementManagement"
            ]["fields"]
            for slot, selection in fixture["intent"]["slots"].items()
            if "enhancementManagement"
            in fixture["authorityContext"]["variantsByKey"][selection["variantKey"]]
        }
        self.assertEqual(classifications_by_slot["head"]["gem_id"], "editor_managed")
        self.assertEqual(classifications_by_slot["head"]["enchant_id"], "source_only")
        self.assertEqual(classifications_by_slot["shoulder"]["enchant_id"], "source_only")
        self.assertEqual(classifications_by_slot["waist"]["enchant_id"], "source_only")
        self.assertEqual(classifications_by_slot["main_hand"]["enchant_id"], "source_only")
        self.assertEqual(classifications_by_slot["back"]["enchant_id"], "editor_managed")
        self.assertEqual(classifications_by_slot["back"]["embellishment"], "editor_managed")
        serializer_by_slot = {
            item["slot"]: item for item in result["serializerInput"]["gearItems"]
        }
        self.assertNotIn("gem_id", serializer_by_slot["head"]["simcOptions"])
        self.assertNotIn("enchant_id", serializer_by_slot["back"]["simcOptions"])
        self.assertNotIn("embellishment", serializer_by_slot["back"]["simcOptions"])
        self.assertEqual(serializer_by_slot["head"]["simcOptions"]["enchant_id"], "8017")
        self.assertEqual(serializer_by_slot["main_hand"]["simcOptions"]["enchant_id"], "8039/8052")

    def test_v2_unresolved_or_missing_management_drops_raw_while_v1_preserves_legacy_raw(self):
        unresolved = build_midnight_mage_resolver_fixture(
            selected_gem_count=8,
            include_reference_enhancements=True,
        )
        back_key = unresolved["intent"]["slots"]["back"]["variantKey"]
        back_variant = unresolved["authorityContext"]["variantsByKey"][back_key]
        back_variant["simcOptions"]["enchant_id"] = "9999"
        back_variant["enhancementManagement"]["fields"]["enchant_id"] = "unresolved_drop"
        unresolved["intent"]["slots"]["back"]["enchantOptionId"] = ""

        unresolved_result = self.resolve(unresolved)

        self.assertNotIn(
            "enchant_id",
            unresolved_result["resolvedSlots"]["back"]["simcOptions"],
        )
        self.assertNotIn(
            "enchant_id",
            next(
                item["simcOptions"]
                for item in unresolved_result["serializerInput"]["gearItems"]
                if item["slot"] == "back"
            ),
        )

        missing = build_midnight_mage_resolver_fixture(
            selected_gem_count=8,
            include_reference_enhancements=True,
        )
        head_key = missing["intent"]["slots"]["head"]["variantKey"]
        missing["authorityContext"]["variantsByKey"][head_key].pop(
            "enhancementManagement", None
        )
        missing["intent"]["slots"]["head"]["gemOptionIds"] = []

        missing_result = self.resolve(missing)

        self.assertNotIn("gem_id", missing_result["resolvedSlots"]["head"]["simcOptions"])
        self.assertNotIn("enchant_id", missing_result["resolvedSlots"]["head"]["simcOptions"])

        legacy = copy.deepcopy(missing)
        legacy["authorityContext"]["dependencyVector"]["capabilityRevision"] = (
            gear_socket_authority.LEGACY_CAPABILITY_REVISION
        )

        legacy_result = self.resolve(legacy)

        self.assertEqual(legacy_result["resolvedSlots"]["head"]["simcOptions"]["gem_id"], "240916")
        self.assertEqual(legacy_result["resolvedSlots"]["head"]["simcOptions"]["enchant_id"], "8017")

    def test_v2_forged_source_only_gem_marker_cannot_reach_serializer(self):
        fixture = build_midnight_mage_resolver_fixture(
            selected_gem_count=0,
            include_reference_enhancements=False,
        )
        head_selection = fixture["intent"]["slots"]["head"]
        head_item = fixture["authorityContext"]["itemsById"][
            head_selection["itemId"]
        ]
        head_variant = fixture["authorityContext"]["variantsByKey"][
            head_selection["variantKey"]
        ]
        head_item["baseCapabilities"]["socketCount"] = 0
        head_variant["capabilityOverrides"]["socketCount"] = 0
        head_variant["enhancementManagement"]["fields"]["gem_id"] = "source_only"

        result = self.resolve(fixture)

        self.assertEqual(result["status"], "verified")
        self.assertNotIn("gem_id", result["resolvedSlots"]["head"]["simcOptions"])
        serializer_head = next(
            item
            for item in result["serializerInput"]["gearItems"]
            if item["slot"] == "head"
        )
        self.assertNotIn("gem_id", serializer_head["simcOptions"])

    def test_eight_canonical_gems_are_editable_and_ninth_is_blocked(self):
        accepted = self.resolve(self.midnight_mage_fixture(selected_gem_count=8))
        blocked = self.resolve(self.midnight_mage_fixture(selected_gem_count=9))

        self.assertEqual(accepted["status"], "verified")
        self.assertEqual(
            sum(
                len(slot["selectedOptions"]["gemOptionIds"])
                for slot in accepted["resolvedSlots"].values()
            ),
            8,
        )
        self.assertEqual(blocked["status"], "blocked")
        self.assertTrue(
            any(
                problem["code"] == "GEAR_GEM_SOCKET_CAPACITY_EXCEEDED"
                for problem in blocked["problems"]
            )
        )

    def test_constraints_publish_backend_owned_embellishment_limit(self):
        fixture = self.fixture()

        result = self.resolve(fixture)

        self.assertEqual(result["status"], "verified")
        self.assertEqual(
            result["constraints"].get("embellishmentMax"),
            fixture["authorityContext"]["ruleParameters"]["embellishmentLimit"],
        )
        self.assertEqual(result["constraints"]["embellishmentMax"], 2)

        fixture["authorityContext"]["ruleParameters"]["embellishmentLimit"] = 1
        authority_changed = self.resolve(fixture)
        self.assertEqual(authority_changed["status"], "verified")
        self.assertEqual(authority_changed["constraints"]["embellishmentMax"], 1)

    def test_constraints_keep_embellishment_limit_for_zero_one_and_two_selections(self):
        fixture = self.enable_embellishment_slots(self.fixture(), ["head", "chest"])

        for selected_count in range(3):
            with self.subTest(selected_count=selected_count):
                candidate = copy.deepcopy(fixture)
                for slot in ("head", "chest")[:selected_count]:
                    candidate["intent"]["slots"][slot]["embellishmentOptionId"] = (
                        f"embellishment-{slot}"
                    )

                result = self.resolve(candidate)

                self.assertEqual(result["status"], "verified")
                self.assertEqual(result["constraints"]["embellishmentMax"], 2)

    def test_embellishment_over_limit_blocks_without_changing_authoritative_max(self):
        fixture = self.enable_embellishment_slots(
            self.fixture(), ["head", "chest", "main_hand"]
        )
        for slot in ("head", "chest", "main_hand"):
            fixture["intent"]["slots"][slot]["embellishmentOptionId"] = (
                f"embellishment-{slot}"
            )

        result = self.resolve(fixture)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["constraints"]["embellishmentMax"], 2)
        self.assertTrue(
            any(
                problem["code"] == "GEAR_CRAFT_EMBELLISHMENT_LIMIT_EXCEEDED"
                for problem in result["problems"]
            )
        )

    def test_v2_source_only_built_in_embellishment_occupies_global_limit(self):
        fixture = self.enable_embellishment_slots(
            self.mark_source_only_built_in_embellishment(self.fixture(), "head"),
            ["chest", "main_hand"],
        )

        for selected_count, expected_status in ((0, "verified"), (1, "verified"), (2, "blocked")):
            with self.subTest(selected_count=selected_count):
                candidate = copy.deepcopy(fixture)
                for slot in ("chest", "main_hand")[:selected_count]:
                    candidate["intent"]["slots"][slot]["embellishmentOptionId"] = (
                        f"embellishment-{slot}"
                    )

                result = self.resolve(candidate)

                self.assertEqual(result["status"], expected_status)
                self.assertEqual(result["constraints"]["embellishmentMax"], 2)
                self.assertEqual(result["constraints"]["embellishmentBuiltInUsed"], 1)
                self.assertEqual(
                    result["constraints"]["embellishmentSelectedUsed"],
                    selected_count,
                )
                self.assertEqual(
                    result["constraints"]["embellishmentUsed"],
                    selected_count + 1,
                )
                self.assertEqual(
                    result["resolvedSlots"]["head"]["simcOptions"]["embellishment"],
                    "built_in_embellishment",
                )
                exceeded = [
                    problem
                    for problem in result["problems"]
                    if problem["code"] == "GEAR_CRAFT_EMBELLISHMENT_LIMIT_EXCEEDED"
                ]
                self.assertEqual(bool(exceeded), selected_count == 2)
                if exceeded:
                    self.assertEqual(exceeded[0]["meta"], {"count": 3, "limit": 2})

    def test_legacy_or_unclassified_raw_embellishment_is_not_counted_as_built_in(self):
        fixture = self.fixture()
        head_key = fixture["intent"]["slots"]["head"]["variantKey"]
        fixture["authorityContext"]["variantsByKey"][head_key]["simcOptions"][
            "embellishment"
        ] = "legacy_unknown_raw"

        result = self.resolve(fixture)

        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["constraints"]["embellishmentBuiltInUsed"], 0)
        self.assertEqual(result["constraints"]["embellishmentSelectedUsed"], 0)
        self.assertEqual(result["constraints"]["embellishmentUsed"], 0)
        self.assertEqual(
            result["resolvedSlots"]["head"]["simcOptions"]["embellishment"],
            "legacy_unknown_raw",
        )

    def test_source_only_built_in_slot_rejects_overlapping_editable_embellishment(self):
        fixture = self.enable_embellishment_slots(
            self.mark_source_only_built_in_embellishment(self.fixture(), "head"),
            ["head"],
        )
        fixture["intent"]["slots"]["head"]["embellishmentOptionId"] = (
            "embellishment-head"
        )

        result = self.resolve(fixture)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["aggregateLegality"]["status"], "blocked")
        self.assertEqual(result["constraints"]["embellishmentBuiltInUsed"], 1)
        self.assertEqual(result["constraints"]["embellishmentSelectedUsed"], 1)
        self.assertEqual(result["constraints"]["embellishmentUsed"], 2)
        self.assertTrue(
            any(
                problem["code"]
                == "GEAR_CRAFT_BUILT_IN_EMBELLISHMENT_CONFLICT"
                for problem in result["problems"]
            )
        )

    def test_invalid_v2_management_drops_raw_and_cannot_create_built_in_usage_or_conflict(self):
        invalid_cases = {
            "missing marker": None,
            "forged schema": {"schemaRevision": "forged-v0"},
            "wrong authority": {
                "authorityRevision": gear_socket_authority.LEGACY_CAPABILITY_REVISION,
            },
            "missing field": {"fields": {}},
            "extra field": {
                "fields": {
                    "embellishment": "source_only",
                    "enchant_id": "source_only",
                },
            },
            "invalid enum": {"fields": {"embellishment": "trust_me"}},
        }
        for name, mutation in invalid_cases.items():
            with self.subTest(name=name):
                fixture = self.enable_embellishment_slots(
                    self.mark_source_only_built_in_embellishment(
                        self.fixture(),
                        "head",
                    ),
                    ["head"],
                )
                variant_key = fixture["intent"]["slots"]["head"]["variantKey"]
                variant = fixture["authorityContext"]["variantsByKey"][variant_key]
                if mutation is None:
                    variant.pop("enhancementManagement", None)
                else:
                    for key, value in mutation.items():
                        variant["enhancementManagement"][key] = value

                without_selection = self.resolve(copy.deepcopy(fixture))

                self.assertEqual(without_selection["status"], "verified")
                self.assertEqual(
                    without_selection["constraints"]["embellishmentBuiltInUsed"],
                    0,
                )
                self.assertEqual(
                    without_selection["constraints"]["embellishmentSelectedUsed"],
                    0,
                )
                self.assertEqual(
                    without_selection["constraints"]["embellishmentUsed"],
                    0,
                )
                self.assertNotIn(
                    "embellishment",
                    without_selection["resolvedSlots"]["head"]["simcOptions"],
                )

                fixture["intent"]["slots"]["head"]["embellishmentOptionId"] = (
                    "embellishment-head"
                )

                result = self.resolve(fixture)

                self.assertEqual(result["status"], "verified")
                self.assertEqual(result["constraints"]["embellishmentBuiltInUsed"], 0)
                self.assertEqual(result["constraints"]["embellishmentSelectedUsed"], 1)
                self.assertEqual(result["constraints"]["embellishmentUsed"], 1)
                self.assertEqual(
                    result["resolvedSlots"]["head"]["simcOptions"]["embellishment"],
                    "embellishment-head",
                )
                self.assertFalse(any(
                    problem["code"]
                    == "GEAR_CRAFT_BUILT_IN_EMBELLISHMENT_CONFLICT"
                    for problem in result["problems"]
                ))

    def test_client_cannot_publish_an_embellishment_limit(self):
        fixture = self.fixture()
        fixture["intent"]["embellishmentMax"] = 99

        result = self.resolve(fixture)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["constraints"], {"slots": {}})
        self.assertTrue(
            any(problem["code"] == "UNKNOWN_FIELD" for problem in result["problems"])
        )

    def test_empty_snapshot_does_not_claim_an_unvalidated_embellishment_limit(self):
        fixture = self.fixture()
        fixture["authorityContext"].pop("ruleParameters")

        result = self.resolve(fixture)

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["constraints"], {"slots": {}})

    def test_invalid_authority_embellishment_limit_blocks_without_publishing_max(self):
        for invalid_limit in (True, -1):
            with self.subTest(invalid_limit=invalid_limit):
                fixture = self.fixture()
                fixture["authorityContext"]["ruleParameters"]["embellishmentLimit"] = (
                    invalid_limit
                )

                result = self.resolve(fixture)

                self.assertEqual(result["status"], "blocked")
                self.assertNotIn("embellishmentMax", result["constraints"])
                self.assertTrue(
                    any(
                        problem["code"] == "GEAR_CRAFT_AUTHORITY_UNAVAILABLE"
                        for problem in result["problems"]
                    )
                )

    def test_constraints_use_exact_variant_override_without_promoting_raw_simc_options(self):
        fixture = self.fixture()
        head_variant = fixture["authorityContext"]["variantsByKey"]["variant-set-head"]
        head_variant["capabilityOverrides"] = {"socketCount": 2}
        head_variant["overlay"]["capabilityOverrides"] = {}
        head_variant["simcOptions"].update(
            {"gem_id": "240892/240900", "enchant_id": "forged-raw-enchant"}
        )
        fixture["intent"]["slots"]["head"]["gemOptionIds"] = []

        result = self.resolve(fixture)
        constraints = result["constraints"]["slots"]["head"]
        resolved = result["resolvedSlots"]["head"]

        self.assertEqual(result["status"], "verified")
        self.assertEqual(constraints["socketCount"], 2)
        self.assertEqual(constraints["socketRemaining"], 2)
        self.assertFalse(constraints["canEnchant"])
        self.assertFalse(constraints["hasSelectedEnchant"])
        self.assertEqual(resolved["selectedOptions"]["gemOptionIds"], [])
        self.assertEqual(resolved["selectedOptions"]["enchantOptionId"], "")

        forged = copy.deepcopy(fixture)
        forged["intent"]["slots"]["head"]["enchantOptionId"] = "forged-enchant-option"
        forged_result = self.resolve(forged)

        self.assertEqual(forged_result["status"], "blocked")
        self.assertTrue(
            any(
                problem["code"] == "GEAR_ENCHANT_OPTION_UNKNOWN"
                for problem in forged_result["problems"]
            )
        )
        self.assertNotEqual(
            forged_result["resolvedSlots"]["head"]["simcOptions"].get("enchant_id"),
            "forged-enchant-option",
        )

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
            "itemStaticStats",
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
