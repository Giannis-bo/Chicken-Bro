import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import unittest

from server import pg_gear_authority_loader


class FakeCursor:
    def __init__(self, revision_rows=None, item_rows=None, option_rows=None):
        self.revision_rows = list(revision_rows or [])
        self.item_rows = list(item_rows or [])
        self.option_rows = list(option_rows or [])
        self.current_rows = []
        self.statements = []
        self.params = []

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        self.statements.append(normalized)
        self.params.append(tuple(params or ()))
        if "gear_authority_revision" in normalized:
            self.current_rows = copy.deepcopy(self.revision_rows)
        elif "gear_authority_items_variants" in normalized:
            self.current_rows = copy.deepcopy(self.item_rows)
        elif "gear_authority_options" in normalized:
            self.current_rows = copy.deepcopy(self.option_rows)
        else:
            raise AssertionError(f"Unexpected SQL: {normalized}")

    def fetchone(self):
        return self.current_rows.pop(0) if self.current_rows else None

    def fetchall(self):
        rows = list(self.current_rows)
        self.current_rows = []
        return rows


class PgGearAuthorityLoaderTest(unittest.TestCase):
    def test_loader_imports_in_direct_server_runtime_mode(self):
        server_dir = Path(__file__).resolve().parents[1] / "server"

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import postgres_cache_store; print(postgres_cache_store.AuthorityContextCache.__name__)",
            ],
            cwd=server_dir,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "AuthorityContextCache")

    def intent(self, slots=None):
        slots = slots or {
            "head": {
                "itemId": "item-head",
                "variantKey": "variant-head",
                "gemOptionIds": ["gem-haste"],
                "enchantOptionId": "",
                "embellishmentOptionId": "",
                "craftedOptionId": "",
                "catalystOptionId": "",
            }
        }
        return {
            "schemaRevision": "selection-intent-v1",
            "authoredAgainst": {
                "seasonRevision": "season-17-active",
                "gearCatalogRevision": self.catalog_revision(),
            },
            "eligibilityContext": {"classKey": "warrior", "specKey": "fury", "level": 90},
            "slots": slots,
        }

    def runtime_authority(self, **revision_overrides):
        revisions = {
            "gearRuleRevision": "gear-rule-matrix-v1",
            "resolverContractRevision": "gear-resolver-contract-v1",
            "serializerRevision": "websim-profile-compat-v1",
            "simcRuntimeRevision": "simc-v1",
            "statPolicyRevision": "stat-snapshot-policy-v1",
            "selectionSchemaRevision": "selection-intent-v1",
        }
        revisions.update(revision_overrides)
        return {
            "dependencyRevisions": revisions,
            "ruleParameters": {
                "inventoryTypesBySlot": {"head": ["head"]},
                "allowedArmorTypesByClass": {"warrior": ["plate"]},
                "armorRestrictedSlots": ["head", "shoulder", "chest", "wrist", "hands", "waist", "legs", "feet"],
                "allowedWeaponTypesByClassSpec": {"warrior:fury": ["sword"]},
                "dualWieldByClassSpec": {"warrior:fury": True},
                "weaponModesByClassSpec": {"warrior:fury": "dual_wield_2h"},
                "requiredSlots": ["head"],
                "uniqueLimits": {},
                "uniqueGemLimits": {},
                "runeforgeAllowedClassSpecs": [],
                "embellishmentLimit": 2,
                "catalystRevision": "catalyst-proof-v1",
                "crossSlotBlockers": [],
                "setAggregationInputs": [],
                "sourceRefIds": ["evidence:runtime:rules"],
            },
            "capabilities": {
                "serializer": {"enabled": True, "revision": "websim-profile-compat-v1"},
                "catalyst": {"enabled": False, "revision": "catalyst-proof-v1"},
            },
            "playableClassSpecs": {"warrior": ["fury", "arms", "protection"]},
            "requestedClassSpec": "warrior:fury",
            "sourceRefs": [
                {
                    "id": "evidence:runtime:rules",
                    "sourceType": "backend_policy",
                    "sourceRevision": "gear-rule-matrix-v1",
                }
            ],
        }

    def revision_row(self, *, season_revision="season-17-active", item_count=10):
        return (
            season_revision,
            {"status": "partial", "schemaRevision": "legacy-gear-v1"},
            {"status": "partial"},
            item_count,
            "2026-07-10T10:00:00+00:00",
            20,
            "2026-07-10T10:01:00+00:00",
            5,
            "2026-07-10T10:02:00+00:00",
            12,
            "2026-07-10T10:03:00+00:00",
        )

    def catalog_revision(self, revision_row=None):
        row = revision_row or self.revision_row()
        return pg_gear_authority_loader.compatibility_catalog_revision(row)

    def item_row(self, **overrides):
        item = {
            "id": "item-head",
            "name": "Authority Helm",
            "slot": "head",
            "itemLevel": 289,
            "sourceStatus": "verified",
            "payload": {
                "inventoryType": "head",
                "armorType": "plate",
                "weaponType": "",
                "handedness": "",
                "baseStats": {"strength": 80, "stamina": 120},
                "itemSetId": "set:authority",
                "socketCount": 1,
                "canEnchant": False,
            },
        }
        variant = {
            "id": "variant-row-head",
            "itemId": "item-head",
            "slot": "head",
            "variantKey": "variant-head",
            "itemLevel": 289,
            "simcOptions": {"ilevel": "289", "bonus_id": "head-bonus"},
            "status": "verified",
            "blockers": [],
            "payload": {
                "resolvedStats": {"strength": 90, "stamina": 130},
                "itemSetId": "set:authority",
            },
        }
        sources = [
            {
                "id": "source-row-head",
                "sourceType": "dungeon",
                "sourceKey": "dungeon:head",
                "seasonRevision": "season-17-active",
                "status": "verified",
                "updatedAt": "2026-07-10T10:03:00+00:00",
            }
        ]
        item.update(overrides.pop("item", {}))
        variant.update(overrides.pop("variant", {}))
        sources = overrides.pop("sources", sources)
        return ("item-head", "variant-head", item, variant, sources)

    def option_row(self, **overrides):
        option = {
            "id": "option-row-gem",
            "optionKey": "gem-haste",
            "optionType": "socket",
            "name": "Haste Gem",
            "applicableSlots": ["head"],
            "simcOptions": {"gem_id": "gem-haste"},
            "status": "verified",
            "isVisible": True,
            "payload": {"statDeltas": {"haste": 10}},
            "updatedAt": "2026-07-10T10:02:00+00:00",
        }
        option.update(overrides)
        return ("gem-haste", option)

    def cursor(self, *, revision_rows=None, item_rows=None, option_rows=None):
        return FakeCursor(
            revision_rows=revision_rows or [self.revision_row()],
            item_rows=item_rows if item_rows is not None else [self.item_row()],
            option_rows=option_rows if option_rows is not None else [self.option_row()],
        )

    def load(self, cursor=None, intent=None, runtime=None, cache=None):
        cursor = cursor or self.cursor()
        context = pg_gear_authority_loader.load_gear_authority_context(
            cursor,
            intent or self.intent(),
            runtime or self.runtime_authority(),
            cache=cache,
        )
        return cursor, context

    def test_loader_executes_three_cold_queries_for_one_or_sixteen_slots(self):
        cursor, _context = self.load()
        self.assertEqual(len(cursor.statements), 3)

        slot_names = (
            "head", "neck", "shoulder", "back", "chest", "wrist", "hands", "waist",
            "legs", "feet", "finger1", "finger2", "trinket1", "trinket2", "main_hand", "off_hand",
        )
        slots = {}
        for index, slot in enumerate(slot_names):
            slots[slot] = {
                "itemId": f"item-{index}",
                "variantKey": f"variant-{index}",
                "gemOptionIds": [],
                "enchantOptionId": "",
                "embellishmentOptionId": "",
                "craftedOptionId": "",
                "catalystOptionId": "",
            }
        cursor, _context = self.load(cursor=self.cursor(item_rows=[], option_rows=[]), intent=self.intent(slots))
        self.assertEqual(len(cursor.statements), 3)

    def test_resolver_authoring_context_matches_loader_revision_identity(self):
        revision_row = self.revision_row()
        runtime = self.runtime_authority()
        cursor, authority = self.load(
            cursor=self.cursor(revision_rows=[revision_row]),
            runtime=runtime,
        )

        resolver_context = pg_gear_authority_loader.resolver_authoring_context(
            revision_row,
            runtime,
        )

        self.assertEqual(resolver_context["contractRevision"], "gear-resolver-context-v1")
        self.assertFalse(resolver_context["formalActiveManifest"])
        self.assertEqual(
            resolver_context["authoredAgainst"],
            {
                "seasonRevision": authority["manifest"]["seasonRevision"],
                "gearCatalogRevision": authority["manifest"]["gearCatalogRevision"],
            },
        )
        self.assertEqual(
            resolver_context["dependencyRevisions"],
            {
                key: authority["dependencyVector"][key]
                for key in (
                    "gearRuleRevision",
                    "resolverContractRevision",
                    "serializerRevision",
                    "simcRuntimeRevision",
                    "statPolicyRevision",
                    "selectionSchemaRevision",
                )
            },
        )
        self.assertEqual(cursor.statements[0].count("gear_authority_revision"), 1)

    def test_resolver_authoring_context_fails_closed_on_missing_revision_authority(self):
        missing_season = list(self.revision_row())
        missing_season[0] = ""
        self.assertIsNone(
            pg_gear_authority_loader.resolver_authoring_context(
                tuple(missing_season),
                self.runtime_authority(),
            )
        )

        missing_runtime = self.runtime_authority(simcRuntimeRevision="")
        self.assertIsNone(
            pg_gear_authority_loader.resolver_authoring_context(
                self.revision_row(),
                missing_runtime,
            )
        )

    def test_loader_uses_array_parameters_not_per_slot_sql(self):
        cursor, _context = self.load()
        self.assertIn("unnest(%s::text[], %s::text[])", cursor.statements[1])
        self.assertIn("ANY(%s::text[])", cursor.statements[2])
        self.assertIn("REGEXP_REPLACE", cursor.statements[1])
        self.assertIn("LIMIT 8", cursor.statements[1])
        self.assertEqual(cursor.params[1], (["item-head"], ["variant-head"]))
        self.assertEqual(cursor.params[2], (["gem-haste"],))

    def test_loader_deduplicates_reused_item_variant_pairs_before_array_query(self):
        reused = self.intent()["slots"]["head"]
        intent = self.intent({"finger1": reused, "finger2": copy.deepcopy(reused)})

        cursor, _context = self.load(cursor=self.cursor(), intent=intent)

        self.assertEqual(cursor.params[1], (["item-head"], ["variant-head"]))

    def test_loader_accepts_the_existing_public_normalized_variant_alias(self):
        requested_key = (
            "observed-profile-2e3bad4f2811-observed_profile-wrist-289-"
            "bonus_id:6652/13335gem_id:240216ilevel:289"
        )
        authority_key = (
            'observed-profile-2e3bad4f2811-observed_profile-wrist-289-'
            '{"bonus_id": "6652/13335", "gem_id": "240216", "ilevel": "289"}'
        )
        intent = self.intent()
        intent["slots"]["head"]["variantKey"] = requested_key
        row = list(self.item_row())
        row[1] = requested_key
        row[3]["variantKey"] = authority_key

        _cursor, context = self.load(cursor=self.cursor(item_rows=[tuple(row)]), intent=intent)

        self.assertEqual(set(context["variantsByKey"]), {requested_key})
        self.assertEqual(context["variantsByKey"][requested_key]["simcOptions"]["bonus_id"], "head-bonus")
        self.assertEqual(context["missingFields"], [])

    def test_loader_still_accepts_an_exact_raw_authority_variant_key(self):
        authority_key = 'observed-profile-head-289-{"bonus_id":"123","ilevel":"289"}'
        intent = self.intent()
        intent["slots"]["head"]["variantKey"] = authority_key
        row = list(self.item_row())
        row[1] = authority_key
        row[3]["variantKey"] = authority_key

        _cursor, context = self.load(cursor=self.cursor(item_rows=[tuple(row)]), intent=intent)

        self.assertEqual(set(context["variantsByKey"]), {authority_key})
        self.assertEqual(context["missingFields"], [])

    def test_loader_blocks_semantically_divergent_public_variant_aliases(self):
        requested_key = "observed-profile-head-289-bonus_id:123ilevel:289"
        first = list(self.item_row())
        first[1] = requested_key
        first[3]["variantKey"] = 'observed-profile-head-289-{"bonus_id":"123","ilevel":"289"}'
        second = copy.deepcopy(first)
        second[3]["id"] = "variant-row-head-collision"
        second[3]["variantKey"] = 'observed-profile-head-289-{"bonus_id": "123", "ilevel": "289"}'
        second[3]["simcOptions"]["bonus_id"] = "different-authority"
        intent = self.intent()
        intent["slots"]["head"]["variantKey"] = requested_key

        _cursor, context = self.load(
            cursor=self.cursor(item_rows=[tuple(first), tuple(second)]),
            intent=intent,
        )

        self.assertNotIn(requested_key, context["variantsByKey"])
        self.assertIn(f"variantsByKey.{requested_key}", context["missingFields"])

    def test_loader_merges_semantically_identical_public_variant_alias_rows(self):
        requested_key = "observed-profile-head-289-bonus_id:123ilevel:289"
        first = list(self.item_row())
        first[1] = requested_key
        first[3]["variantKey"] = 'observed-profile-head-289-{"bonus_id":"123","ilevel":"289"}'
        second = copy.deepcopy(first)
        second[3]["id"] = "variant-row-head-duplicate"
        second[3]["variantKey"] = 'observed-profile-head-289-{"bonus_id": "123", "ilevel": "289"}'
        intent = self.intent()
        intent["slots"]["head"]["variantKey"] = requested_key

        _cursor, context = self.load(
            cursor=self.cursor(item_rows=[tuple(first), tuple(second)]),
            intent=intent,
        )

        self.assertIn(requested_key, context["variantsByKey"])
        self.assertEqual(context["missingFields"], [])
        self.assertIn(
            "evidence:pg:variant:variant-row-head-duplicate",
            context["variantsByKey"][requested_key]["sourceRefIds"],
        )

    def test_loader_never_matches_a_normalized_alias_from_the_wrong_item(self):
        requested_key = "observed-profile-head-289-bonus_id:123ilevel:289"
        row = list(self.item_row())
        row[1] = requested_key
        row[3]["itemId"] = "wrong-item"
        row[3]["variantKey"] = 'observed-profile-head-289-{"bonus_id":"123","ilevel":"289"}'
        intent = self.intent()
        intent["slots"]["head"]["variantKey"] = requested_key

        _cursor, context = self.load(cursor=self.cursor(item_rows=[tuple(row)]), intent=intent)

        self.assertNotIn(requested_key, context["variantsByKey"])
        self.assertIn(f"variantsByKey.{requested_key}", context["missingFields"])

    def test_loader_warm_hit_executes_revision_query_only(self):
        cache = pg_gear_authority_loader.AuthorityContextCache(max_entries=4, max_bytes=100000)
        first, context = self.load(cache=cache)
        second, warm = self.load(cursor=self.cursor(), cache=cache)
        self.assertEqual(len(first.statements), 3)
        self.assertEqual(len(second.statements), 1)
        self.assertEqual(warm, context)

    def test_revision_change_invalidates_cached_context(self):
        cache = pg_gear_authority_loader.AuthorityContextCache(max_entries=4, max_bytes=100000)
        self.load(cache=cache)
        changed = self.revision_row(item_count=11)
        intent = self.intent()
        intent["authoredAgainst"]["gearCatalogRevision"] = self.catalog_revision(changed)
        cursor, _context = self.load(
            cursor=self.cursor(revision_rows=[changed]), intent=intent, cache=cache
        )
        self.assertEqual(len(cursor.statements), 3)

    def test_sync_state_change_invalidates_cached_context(self):
        cache = pg_gear_authority_loader.AuthorityContextCache(max_entries=4, max_bytes=100000)
        self.load(cache=cache)
        changed = list(self.revision_row())
        changed[1] = {"status": "verified", "schemaRevision": "legacy-gear-v1"}
        changed = tuple(changed)
        intent = self.intent()
        intent["authoredAgainst"]["gearCatalogRevision"] = self.catalog_revision(changed)

        cursor, context = self.load(
            cursor=self.cursor(revision_rows=[changed]), intent=intent, cache=cache
        )

        self.assertEqual(len(cursor.statements), 3)
        self.assertEqual(context["manifest"]["sourceStates"]["gearCatalog"]["status"], "verified")

    def test_loader_builds_exact_authority_context_maps(self):
        _cursor, context = self.load()
        self.assertEqual(context["contractRevision"], "gear-authority-context-v1")
        self.assertEqual(context["manifest"]["contractRevision"], "compatibility-pg-live-v1")
        self.assertEqual(context["manifest"]["seasonRevision"], "season-17-active")
        self.assertEqual(set(context["itemsById"]), {"item-head"})
        self.assertEqual(set(context["variantsByKey"]), {"variant-head"})
        self.assertEqual(set(context["optionsById"]), {"gem-haste"})
        self.assertEqual(context["variantsByKey"]["variant-head"]["resolvedStats"], {"strength": 90, "stamina": 130})
        self.assertEqual(context["optionsById"]["gem-haste"]["optionType"], "gem")
        self.assertEqual(context["missingFields"], [])

    def test_loader_projects_existing_structured_item_metadata_and_equivalent_slots(self):
        ring = self.item_row(
            item={
                "slot": "finger1",
                "payload": {
                    "inventory_type": {"type": "FINGER", "name": "Finger"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 0, "name": "Miscellaneous"},
                },
            }
        )

        _cursor, context = self.load(cursor=self.cursor(item_rows=[ring]))

        item = context["itemsById"]["item-head"]
        self.assertEqual(item["inventoryType"], "finger1")
        self.assertEqual(item["allowedSlots"], ["finger1", "finger2"])

    def test_loader_projects_two_hand_weapon_type_and_handedness_from_item_payload(self):
        staff = self.item_row(
            item={
                "slot": "main_hand",
                "payload": {
                    "inventory_type": {"type": "TWOHWEAPON", "name": "Two-Hand"},
                    "item_class": {"id": 2, "name": "Weapon"},
                    "item_subclass": {"id": 10, "name": "Staff"},
                },
            }
        )

        _cursor, context = self.load(cursor=self.cursor(item_rows=[staff]))

        item = context["itemsById"]["item-head"]
        self.assertEqual(item["inventoryType"], "weapon")
        self.assertEqual(item["weaponType"], "Staff")
        self.assertEqual(item["handedness"], "two_hand")

    def test_loader_allows_two_hand_weapon_in_offhand_for_authorized_fury_mode(self):
        weapon = self.item_row(
            item={
                "slot": "main_hand",
                "payload": {
                    "inventory_type": {"type": "TWOHWEAPON", "name": "Two-Hand"},
                    "item_class": {"id": 2, "name": "Weapon"},
                    "item_subclass": {"name": "Two-Handed Sword"},
                },
            }
        )
        intent = self.intent(
            {
                "off_hand": {
                    "itemId": "item-head",
                    "variantKey": "variant-head",
                    "gemOptionIds": [],
                    "enchantOptionId": "",
                    "embellishmentOptionId": "",
                    "craftedOptionId": "",
                    "catalystOptionId": "",
                }
            }
        )

        _cursor, context = self.load(cursor=self.cursor(item_rows=[weapon]), intent=intent)

        self.assertEqual(context["itemsById"]["item-head"]["handedness"], "two_hand")
        self.assertEqual(context["itemsById"]["item-head"]["allowedSlots"], ["main_hand", "off_hand"])

    def test_loader_allows_one_hand_weapon_authority_in_either_hand(self):
        sword = self.item_row(
            item={
                "slot": "main_hand",
                "payload": {
                    "inventory_type": {"type": "WEAPON", "name": "One-Hand"},
                    "item_class": {"id": 2, "name": "Weapon"},
                    "item_subclass": {"id": 7, "name": "One-Handed Sword"},
                },
            }
        )

        _cursor, context = self.load(cursor=self.cursor(item_rows=[sword]))

        item = context["itemsById"]["item-head"]
        self.assertEqual(item["inventoryType"], "weapon")
        self.assertEqual(item["allowedSlots"], ["main_hand", "off_hand"])
        self.assertEqual(item["handedness"], "one_hand")

    def test_loader_projects_canonical_battle_net_tier_set_membership(self):
        tier = list(self.item_row(
            sources=[
                {
                    "id": "tier-source-head",
                    "sourceType": "tier_set",
                    "sourceKey": "set-1983-item-head",
                    "seasonRevision": "season-17-active",
                    "status": "unknown",
                    "sourceStatus": "unknown",
                    "payload": {
                        "authority": "Battle.net Game Data API",
                        "setId": "1983",
                        "setName": "Authority Regalia",
                    },
                    "updatedAt": "2026-07-10T10:03:00+00:00",
                }
            ],
        ))
        tier[2]["itemSetIds"] = ["1983"]
        tier[2]["payload"].pop("itemSetId", None)
        tier[3]["payload"].pop("itemSetId", None)

        _cursor, context = self.load(cursor=self.cursor(item_rows=[tuple(tier)]))

        self.assertEqual(context["itemsById"]["item-head"]["itemSetId"], "1983")
        self.assertEqual(context["variantsByKey"]["variant-head"]["itemSetId"], "")
        self.assertIn("DISTINCT ON (candidate.source_type)", pg_gear_authority_loader.SELECTED_ITEM_VARIANT_SQL)
        self.assertIn("Battle.net Game Data API", pg_gear_authority_loader.SELECTED_ITEM_VARIANT_SQL)

    def test_loader_blocks_conflicting_canonical_item_set_memberships(self):
        conflicting = list(self.item_row())
        conflicting[2]["itemSetIds"] = ["1983", "1984"]
        conflicting[2]["payload"].pop("itemSetId", None)

        _cursor, context = self.load(cursor=self.cursor(item_rows=[tuple(conflicting)]))

        self.assertNotIn("item-head", context["itemsById"])
        self.assertIn("itemsById.item-head", context["missingFields"])

    def test_loaded_context_resolves_without_facade_or_client_authority(self):
        from server import gear_resolver

        _cursor, context = self.load()
        snapshot = gear_resolver.resolve(self.intent(), context)

        self.assertEqual(snapshot["status"], "verified")
        self.assertTrue(snapshot["profileReadiness"]["simcReady"])
        self.assertEqual(snapshot["staticAttributes"], {"haste": 10, "stamina": 130, "strength": 90})
        self.assertEqual(len(snapshot["ruleResults"]), 10)
        self.assertEqual(tuple(snapshot["evidenceLedger"]["claimGroups"]), (
            "identity_options",
            "provenance",
            "legality",
            "static_attributes",
            "profile_executability",
        ))

    def test_loader_normalizes_structured_item_stats_without_parsing_display_text(self):
        from server import gear_resolver

        structured = self.item_row(
            variant={
                "payload": {
                    "itemStats": [
                        {"key": "strength", "label": "力量", "value": 90},
                        {"key": "stamina", "label": "耐力", "value": 130},
                    ],
                    "statSummary": "力量 900000",
                    "itemSetId": "set:authority",
                }
            }
        )
        _cursor, context = self.load(cursor=self.cursor(item_rows=[structured]))
        self.assertEqual(
            context["variantsByKey"]["variant-head"]["resolvedStats"],
            {"stamina": 130, "strength": 90},
        )

        display_only = self.item_row(
            variant={"payload": {"statSummary": "力量 900000", "itemSetId": "set:authority"}}
        )
        _cursor, context = self.load(cursor=self.cursor(item_rows=[display_only]))
        self.assertNotIn("resolvedStats", context["variantsByKey"]["variant-head"])
        self.assertNotIn("900000", json.dumps(context))
        snapshot = gear_resolver.resolve(self.intent(), context)
        self.assertEqual(snapshot["status"], "blocked")
        self.assertTrue(
            any(
                problem["code"] == "GEAR_VARIANT_STATS_UNAVAILABLE"
                for problem in snapshot["problems"]
            )
        )

        option = self.option_row(
            payload={
                "itemStats": [{"key": "haste", "label": "急速", "value": 10}],
                "statSummary": "急速 900000",
            }
        )
        _cursor, context = self.load(cursor=self.cursor(option_rows=[option]))
        self.assertEqual(context["optionsById"]["gem-haste"]["statDeltas"], {"haste": 10})
        self.assertNotIn("900000", json.dumps(context))

    def test_structured_variant_item_stats_are_resolved_once_not_reapplied_as_delta(self):
        from server import gear_resolver

        structured = self.item_row(
            variant={
                "payload": {
                    "itemStats": [
                        {"key": "strength", "label": "力量", "value": 90},
                        {"key": "stamina", "label": "耐力", "value": 130},
                    ],
                    "itemSetId": "set:authority",
                }
            }
        )

        _cursor, context = self.load(cursor=self.cursor(item_rows=[structured]))
        snapshot = gear_resolver.resolve(self.intent(), context)

        self.assertEqual(context["variantsByKey"]["variant-head"]["statDeltas"], {})
        self.assertEqual(
            snapshot["staticAttributes"],
            {"haste": 10, "stamina": 130, "strength": 90},
        )

    def test_invalid_structured_option_stats_remain_authority_blockers(self):
        from server import gear_resolver

        invalid_option = self.option_row(
            payload={
                "itemStats": [
                    {"key": "haste", "label": "急速", "value": "10"},
                ]
            }
        )

        _cursor, context = self.load(cursor=self.cursor(option_rows=[invalid_option]))
        snapshot = gear_resolver.resolve(self.intent(), context)

        self.assertEqual(snapshot["status"], "blocked")
        self.assertTrue(
            any(
                problem["code"] == "GEAR_STATIC_ATTRIBUTES_UNAVAILABLE"
                for problem in snapshot["problems"]
            )
        )

    def test_loader_rejects_unverified_item_variant_or_hidden_option_rows(self):
        item_row = self.item_row(item={"sourceStatus": "partial"})
        _cursor, context = self.load(cursor=self.cursor(item_rows=[item_row]))
        self.assertNotIn("item-head", context["itemsById"])
        self.assertIn("itemsById.item-head", context["missingFields"])

        variant_row = self.item_row(variant={"status": "partial"})
        _cursor, context = self.load(cursor=self.cursor(item_rows=[variant_row]))
        self.assertNotIn("variant-head", context["variantsByKey"])
        self.assertIn("variantsByKey.variant-head", context["missingFields"])

        _cursor, context = self.load(cursor=self.cursor(option_rows=[self.option_row(isVisible=False)]))
        self.assertNotIn("gem-haste", context["optionsById"])
        self.assertIn("optionsById.gem-haste", context["missingFields"])

    def test_loader_requires_explicit_verified_source_evidence(self):
        source_without_status = self.item_row(
            sources=[
                {
                    "id": "source-row-head",
                    "sourceType": "dungeon",
                    "sourceKey": "dungeon:head",
                    "seasonRevision": "season-17-active",
                    "updatedAt": "2026-07-10T10:03:00+00:00",
                }
            ]
        )

        _cursor, context = self.load(cursor=self.cursor(item_rows=[source_without_status]))

        self.assertNotIn("item-head", context["itemsById"])
        self.assertIn("itemsById.item-head", context["missingFields"])
        self.assertIn("payload_json->>'sourceStatus'", pg_gear_authority_loader.SELECTED_ITEM_VARIANT_SQL)
        self.assertIn("'unknown'", pg_gear_authority_loader.SELECTED_ITEM_VARIANT_SQL)

    def test_loader_accepts_verified_status_without_upgrading_source_reference(self):
        source = self.item_row(
            sources=[
                {
                    "id": "source-row-head",
                    "sourceType": "observed_profile",
                    "sourceKey": "observed:head",
                    "seasonRevision": "season-17-active",
                    "status": "verified",
                    "sourceStatus": "source_reference",
                    "updatedAt": "2026-07-10T10:03:00+00:00",
                }
            ]
        )

        _cursor, context = self.load(cursor=self.cursor(item_rows=[source]))

        self.assertIn("item-head", context["itemsById"])
        self.assertEqual(context["missingFields"], [])
        self.assertIn("payload_json->>'status'", pg_gear_authority_loader.SELECTED_ITEM_VARIANT_SQL)
        evidence = context["evidenceRecordsById"]["evidence:pg:source:source-row-head"]
        self.assertEqual(evidence["sourceStatus"], "source_reference")
        self.assertEqual(evidence["verificationStatus"], "verified")

    def test_loader_accepts_explicit_verified_source_status(self):
        source = self.item_row(
            sources=[
                {
                    "id": "source-row-head",
                    "sourceType": "dungeon",
                    "sourceKey": "dungeon:head",
                    "seasonRevision": "season-17-active",
                    "status": "source_reference",
                    "sourceStatus": "verified",
                    "updatedAt": "2026-07-10T10:03:00+00:00",
                }
            ]
        )

        _cursor, context = self.load(cursor=self.cursor(item_rows=[source]))

        self.assertIn("item-head", context["itemsById"])
        self.assertEqual(context["missingFields"], [])

    def test_loader_records_missing_item_variant_option_and_runtime_authority(self):
        runtime = self.runtime_authority()
        runtime["dependencyRevisions"].pop("simcRuntimeRevision")
        _cursor, context = self.load(
            cursor=self.cursor(item_rows=[], option_rows=[]), runtime=runtime
        )
        self.assertIn("itemsById.item-head", context["missingFields"])
        self.assertIn("variantsByKey.variant-head", context["missingFields"])
        self.assertIn("optionsById.gem-haste", context["missingFields"])
        self.assertIn("runtimeAuthority.dependencyRevisions.simcRuntimeRevision", context["missingFields"])

    def test_loader_never_uses_client_option_payload_as_authority(self):
        intent = self.intent()
        intent["slots"]["head"]["stats"] = {"strength": 999999}
        cursor = self.cursor()
        with self.assertRaises(ValueError):
            self.load(cursor=cursor, intent=intent)
        self.assertEqual(cursor.statements, [])

    def test_loader_projects_canonical_item_set_and_evidence_record_ids(self):
        _cursor, context = self.load()
        self.assertEqual(context["itemsById"]["item-head"]["itemSetId"], "set:authority")
        self.assertEqual(context["variantsByKey"]["variant-head"]["itemSetId"], "set:authority")
        item_refs = context["itemsById"]["item-head"]["sourceRefIds"]
        self.assertEqual(item_refs, ["evidence:pg:source:source-row-head"])
        self.assertIn(item_refs[0], context["evidenceRecordsById"])
        self.assertIn("evidence:pg:variant:variant-row-head", context["evidenceRecordsById"])
        self.assertIn("evidence:pg:option:gem-haste", context["evidenceRecordsById"])

    def test_loader_marks_manifest_as_compatibility_not_formal_active(self):
        _cursor, context = self.load()
        manifest = context["manifest"]
        self.assertEqual(manifest["manifestType"], "compatibility")
        self.assertFalse(manifest["formalActiveManifest"])
        self.assertTrue(manifest["gearCatalogReleaseId"].startswith("compatibility:"))
        self.assertNotIn("activeManifest", json.dumps(context))

    def test_cache_enforces_entry_and_serialized_byte_limits(self):
        cache = pg_gear_authority_loader.AuthorityContextCache(max_entries=2, max_bytes=80)
        self.assertTrue(cache.put("a", {"value": "a" * 10}))
        self.assertTrue(cache.put("b", {"value": "b" * 10}))
        self.assertTrue(cache.put("c", {"value": "c" * 10}))
        self.assertIsNone(cache.get("a"))
        self.assertLessEqual(cache.entry_count, 2)
        self.assertLessEqual(cache.byte_size, 80)
        self.assertFalse(cache.put("too-large", {"value": "x" * 100}))

    def test_cache_returns_detached_canonical_values(self):
        cache = pg_gear_authority_loader.AuthorityContextCache(max_entries=2, max_bytes=1000)
        original = {"nested": {"b": 2, "a": 1}}
        self.assertTrue(cache.put("detached", original))
        original["nested"]["a"] = 999
        first = cache.get("detached")
        first["nested"]["b"] = 999
        second = cache.get("detached")
        self.assertEqual(second, {"nested": {"a": 1, "b": 2}})

    def test_cache_is_thread_safe_and_stays_within_both_bounds(self):
        cache = pg_gear_authority_loader.AuthorityContextCache(max_entries=16, max_bytes=4096)
        self.assertTrue(hasattr(cache, "_lock"))

        def exercise(worker_id):
            for index in range(250):
                key = f"{worker_id}:{index % 24}"
                cache.put(key, {"worker": worker_id, "index": index, "value": "x" * 20})
                value = cache.get(key)
                if value is not None:
                    self.assertEqual(value["worker"], worker_id)

        with ThreadPoolExecutor(max_workers=16) as executor:
            list(executor.map(exercise, range(16)))

        self.assertLessEqual(cache.entry_count, cache.max_entries)
        self.assertLessEqual(cache.byte_size, cache.max_bytes)

    def test_cache_key_contains_full_dependency_vector_and_selection_signature(self):
        cache = pg_gear_authority_loader.AuthorityContextCache(max_entries=8, max_bytes=200000)
        self.load(cache=cache)

        changed_runtime = self.runtime_authority(statPolicyRevision="stat-snapshot-policy-v2")
        cursor, _context = self.load(cursor=self.cursor(), runtime=changed_runtime, cache=cache)
        self.assertEqual(len(cursor.statements), 3)

        changed_intent = self.intent()
        changed_intent["eligibilityContext"]["specKey"] = "arms"
        cursor, _context = self.load(cursor=self.cursor(), intent=changed_intent, cache=cache)
        self.assertEqual(len(cursor.statements), 3)

    def test_candidate_cache_key_is_scoped_to_exact_release_and_runtime_vector(self):
        intent = self.intent()
        runtime = self.runtime_authority()

        release_a = pg_gear_authority_loader.candidate_authority_cache_key(
            intent, runtime, "gear-release:a"
        )
        release_b = pg_gear_authority_loader.candidate_authority_cache_key(
            intent, runtime, "gear-release:b"
        )
        changed_runtime = pg_gear_authority_loader.candidate_authority_cache_key(
            intent,
            self.runtime_authority(statPolicyRevision="stat-snapshot-policy-v2"),
            "gear-release:a",
        )

        self.assertNotEqual(release_a, release_b)
        self.assertNotEqual(release_a, changed_runtime)

    def test_complete_authority_context_may_cache_but_transient_unavailable_does_not(self):
        cache = pg_gear_authority_loader.AuthorityContextCache(max_entries=4, max_bytes=100000)
        self.load(cursor=self.cursor(item_rows=[]), cache=cache)
        cursor, _context = self.load(cursor=self.cursor(item_rows=[]), cache=cache)
        self.assertEqual(len(cursor.statements), 3)


if __name__ == "__main__":
    unittest.main()
