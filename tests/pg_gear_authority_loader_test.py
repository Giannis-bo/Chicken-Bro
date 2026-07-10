import copy
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
                "allowedWeaponTypesByClassSpec": {"warrior:fury": ["sword"]},
                "dualWieldByClassSpec": {"warrior:fury": True},
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

    def test_loader_uses_array_parameters_not_per_slot_sql(self):
        cursor, _context = self.load()
        self.assertIn("unnest(%s::text[], %s::text[])", cursor.statements[1])
        self.assertIn("ANY(%s::text[])", cursor.statements[2])
        self.assertEqual(cursor.params[1], (["item-head"], ["variant-head"]))
        self.assertEqual(cursor.params[2], (["gem-haste"],))

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

    def test_complete_authority_context_may_cache_but_transient_unavailable_does_not(self):
        cache = pg_gear_authority_loader.AuthorityContextCache(max_entries=4, max_bytes=100000)
        self.load(cursor=self.cursor(item_rows=[]), cache=cache)
        cursor, _context = self.load(cursor=self.cursor(item_rows=[]), cache=cache)
        self.assertEqual(len(cursor.statements), 3)


if __name__ == "__main__":
    unittest.main()
