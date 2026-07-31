import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import unittest

from server import gear_resolver, gear_socket_authority, pg_gear_authority_loader


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
            "capabilityRevision": gear_socket_authority.CAPABILITY_REVISION,
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
        if runtime is None:
            runtime = self.runtime_authority(
                capabilityRevision=gear_socket_authority.LEGACY_CAPABILITY_REVISION
            )
        context = pg_gear_authority_loader.load_gear_authority_context(
            cursor,
            intent or self.intent(),
            runtime,
            cache=cache,
        )
        return cursor, context

    def released_context(
        self,
        *,
        capability_revision,
        item_rows=None,
        option_rows=None,
        intent=None,
        runtime=None,
    ):
        runtime = runtime or self.runtime_authority()
        catalog_revision = self.catalog_revision()
        dependency_vector = {
            "seasonRevision": "season-17-active",
            "gearCatalogReleaseId": "gear-release-17",
            "gearCatalogRevision": catalog_revision,
            **runtime["dependencyRevisions"],
            "capabilityRevision": capability_revision,
        }
        return pg_gear_authority_loader.build_gear_authority_context_from_rows(
            intent or self.intent(),
            runtime,
            manifest={
                "contractRevision": "active-season-manifest-v1",
                "manifestType": "active",
                "formalActiveManifest": True,
                "seasonRevision": "season-17-active",
                "gearCatalogReleaseId": "gear-release-17",
                "gearCatalogRevision": catalog_revision,
            },
            dependency_vector=dependency_vector,
            item_rows=item_rows if item_rows is not None else [self.item_row()],
            option_rows=option_rows if option_rows is not None else [],
        )

    def test_released_context_projects_immutable_editor_managed_simc_fields(self):
        def row_for(management):
            return self.item_row(variant={
                "simcOptions": {
                    "ilevel": "289",
                    "bonus_id": "head-bonus",
                    "enchant_id": "4897",
                },
                "payload": {
                    "resolvedStats": {"strength": 90, "stamina": 130},
                    "itemSetId": "set:authority",
                    "enhancementManagement": management,
                },
            })

        valid_management = {
            "schemaRevision": "gear-enhancement-management-v1",
            "authorityRevision": gear_socket_authority.CAPABILITY_REVISION,
            "fields": {"enchant_id": "editor_managed"},
        }

        context = self.released_context(
            capability_revision=gear_socket_authority.CAPABILITY_REVISION,
            item_rows=[row_for(valid_management)],
            option_rows=[],
        )

        self.assertEqual(
            context["variantsByKey"]["variant-head"]["enhancementManagement"],
            valid_management,
        )

        invalid = self.released_context(
            capability_revision=gear_socket_authority.CAPABILITY_REVISION,
            item_rows=[row_for({**valid_management, "schemaRevision": "forged-v0"})],
            option_rows=[],
        )
        self.assertNotIn(
            "enhancementManagement",
            invalid["variantsByKey"]["variant-head"],
        )

        invalid_enum = self.released_context(
            capability_revision=gear_socket_authority.CAPABILITY_REVISION,
            item_rows=[row_for({
                **valid_management,
                "fields": {"enchant_id": "trust_me"},
            })],
            option_rows=[],
        )
        self.assertNotIn(
            "enhancementManagement",
            invalid_enum["variantsByKey"]["variant-head"],
        )

        legacy = self.released_context(
            capability_revision=gear_socket_authority.LEGACY_CAPABILITY_REVISION,
            item_rows=[row_for(valid_management)],
            option_rows=[],
        )
        self.assertNotIn(
            "enhancementManagement",
            legacy["variantsByKey"]["variant-head"],
        )

    def test_exact_import_scope_links_all_release_verified_applicable_editor_options(self):
        exact_option_id = "exact-option:sha256:" + ("a" * 64)
        intent = self.intent(slots={
            "head": {
                "itemId": "item-head",
                "variantKey": "variant-head",
                "gemOptionIds": [],
                "enchantOptionId": exact_option_id,
                "embellishmentOptionId": "",
                "craftedOptionId": "",
                "catalystOptionId": "",
            },
        })
        item_row = self.item_row(item={
            "payload": {
                "inventoryType": "head",
                "armorType": "plate",
                "baseStats": {"strength": 80, "stamina": 120},
                "itemSetId": "set:authority",
                "canEnchant": True,
            },
        })
        official_record = self.option_row(
            optionKey="official-head-enchant",
            optionType="enchant",
            name="Official Head Enchant",
            applicableSlots=["head"],
            simcOptions={"enchant_id": "official"},
        )[1]
        official = ("official-head-enchant", official_record)
        wrong_slot_record = self.option_row(
            optionKey="official-back-enchant",
            optionType="enchant",
            name="Official Back Enchant",
            applicableSlots=["back"],
            simcOptions={"enchant_id": "back"},
        )[1]
        wrong_slot = ("official-back-enchant", wrong_slot_record)

        context = pg_gear_authority_loader.build_gear_authority_context_from_rows(
            intent,
            self.runtime_authority(),
            manifest={
                "contractRevision": "active-season-manifest-v1",
                "manifestType": "active",
                "formalActiveManifest": True,
                "seasonRevision": "season-17-active",
                "gearCatalogReleaseId": "gear-release-17",
                "gearCatalogRevision": self.catalog_revision(),
            },
            dependency_vector={
                "seasonRevision": "season-17-active",
                "gearCatalogReleaseId": "gear-release-17",
                "gearCatalogRevision": self.catalog_revision(),
                **self.runtime_authority()["dependencyRevisions"],
            },
            item_rows=[item_row],
            option_rows=[official, wrong_slot],
            link_all_applicable_options=True,
        )

        self.assertEqual(
            context["itemsById"]["item-head"]["baseCapabilities"][
                "allowedEnchantOptionIds"
            ],
            ["official-head-enchant"],
        )
        self.assertEqual(
            context["itemsById"]["item-head"]["allowedEnchantOptionIds"],
            ["official-head-enchant"],
        )
        self.assertIn("official-head-enchant", context["optionsById"])
        self.assertIn("official-back-enchant", context["optionsById"])
        self.assertIn(
            f"optionsById.{exact_option_id}",
            context["missingFields"],
        )

    def test_v2_source_only_built_in_projects_noneditable_resolver_capability(self):
        management = {
            "schemaRevision": "gear-enhancement-management-v1",
            "authorityRevision": gear_socket_authority.CAPABILITY_REVISION,
            "fields": {"embellishment": "source_only"},
        }
        row = self.item_row(
            item={
                "payload": {
                    "inventoryType": "head",
                    "armorType": "plate",
                    "baseStats": {"strength": 80, "stamina": 120},
                    "itemSetId": "set:authority",
                    "socketCount": 1,
                    "canEnchant": False,
                    "canEmbellish": True,
                },
            },
            variant={
                "simcOptions": {
                    "ilevel": "289",
                    "bonus_id": "head-bonus",
                    "embellishment": "built_in_effect",
                },
                "payload": {
                    "resolvedStats": {"strength": 90, "stamina": 130},
                    "itemSetId": "set:authority",
                    "capabilityOverrides": {"canEmbellish": True},
                    "enhancementManagement": management,
                },
            },
        )
        intent = self.intent()
        intent["slots"]["head"]["gemOptionIds"] = []
        context = self.released_context(
            capability_revision=gear_socket_authority.CAPABILITY_REVISION,
            item_rows=[row],
            option_rows=[self.option_row()],
            intent=intent,
        )

        result = gear_resolver.resolve(intent, context)

        self.assertEqual(
            context["variantsByKey"]["variant-head"]["enhancementManagement"],
            management,
        )
        self.assertFalse(
            context["variantsByKey"]["variant-head"]["capabilityOverrides"][
                "canEmbellish"
            ]
        )
        self.assertEqual(result["status"], "verified")
        self.assertFalse(result["constraints"]["slots"]["head"]["canEmbellish"])
        self.assertEqual(result["constraints"]["embellishmentBuiltInUsed"], 1)
        self.assertEqual(result["constraints"]["embellishmentSelectedUsed"], 0)
        self.assertEqual(result["constraints"]["embellishmentUsed"], 1)

    def test_v2_noncrafted_metadata_cannot_grant_editable_embellishment(self):
        management = {
            "schemaRevision": "gear-enhancement-management-v1",
            "authorityRevision": gear_socket_authority.CAPABILITY_REVISION,
            "fields": {"embellishment": "editor_managed"},
        }
        row = self.item_row(
            item={
                "payload": {
                    "inventoryType": "head",
                    "armorType": "plate",
                    "baseStats": {"strength": 80, "stamina": 120},
                    "itemSetId": "set:authority",
                    "baseCapabilities": {"canEmbellish": True},
                    "canEmbellish": True,
                    "socketCount": 1,
                    "canEnchant": False,
                },
            },
            variant={
                "sourceType": "dungeon",
                "simcOptions": {
                    "ilevel": "289",
                    "crafted_stats": "32/36",
                    "embellishment": "forged-embellishment",
                },
                "payload": {
                    "resolvedStats": {"strength": 90, "stamina": 130},
                    "capabilityOverrides": {"canEmbellish": True},
                    "enhancementManagement": management,
                },
            },
        )

        context = self.released_context(
            capability_revision=gear_socket_authority.CAPABILITY_REVISION,
            item_rows=[row],
        )

        self.assertFalse(
            context["itemsById"]["item-head"]["baseCapabilities"]["canEmbellish"]
        )
        self.assertFalse(
            context["variantsByKey"]["variant-head"]["capabilityOverrides"]["canEmbellish"]
        )

    def test_v2_unresolved_embellishment_conflict_drops_raw_and_cannot_create_capability_or_usage(self):
        management = {
            "schemaRevision": "gear-enhancement-management-v1",
            "authorityRevision": gear_socket_authority.CAPABILITY_REVISION,
            "fields": {"embellishment": "unresolved_drop"},
        }
        row = self.item_row(
            item={
                "payload": {
                    "inventoryType": "head",
                    "armorType": "plate",
                    "baseStats": {"strength": 80, "stamina": 120},
                    "itemSetId": "set:authority",
                    "socketCount": 1,
                    "canEnchant": False,
                    "canEmbellish": True,
                },
            },
            variant={
                "simcOptions": {
                    "ilevel": "289",
                    "bonus_id": "head-bonus",
                    "embellishment": "conflicting_effect",
                },
                "payload": {
                    "resolvedStats": {"strength": 90, "stamina": 130},
                    "itemSetId": "set:authority",
                    "capabilityOverrides": {"canEmbellish": False},
                    "enhancementManagement": management,
                },
            },
        )
        intent = self.intent()
        intent["slots"]["head"]["gemOptionIds"] = []
        context = self.released_context(
            capability_revision=gear_socket_authority.CAPABILITY_REVISION,
            item_rows=[row],
            option_rows=[self.option_row()],
            intent=intent,
        )

        result = gear_resolver.resolve(intent, context)

        self.assertFalse(
            context["variantsByKey"]["variant-head"]["capabilityOverrides"][
                "canEmbellish"
            ]
        )
        self.assertEqual(result["status"], "verified")
        self.assertFalse(result["constraints"]["slots"]["head"]["canEmbellish"])
        self.assertEqual(result["constraints"]["embellishmentBuiltInUsed"], 0)
        self.assertEqual(result["constraints"]["embellishmentSelectedUsed"], 0)
        self.assertEqual(result["constraints"]["embellishmentUsed"], 0)
        self.assertNotIn(
            "embellishment",
            result["resolvedSlots"]["head"]["simcOptions"],
        )
        self.assertNotIn("conflicting_effect", str(result["serializerInput"]))

    def test_v2_unknown_unresolved_embellishment_drops_raw_but_keeps_proven_editability(self):
        management = {
            "schemaRevision": "gear-enhancement-management-v1",
            "authorityRevision": gear_socket_authority.CAPABILITY_REVISION,
            "fields": {"embellishment": "unresolved_drop"},
        }
        row = self.item_row(
            item={
                "payload": {
                    "inventoryType": "head",
                    "armorType": "plate",
                    "baseStats": {"strength": 80, "stamina": 120},
                    "itemSetId": "set:authority",
                    "socketCount": 1,
                    "canEnchant": False,
                    "canEmbellish": True,
                },
            },
            variant={
                "sourceType": "crafted",
                "simcOptions": {
                    "ilevel": "289",
                    "bonus_id": "head-bonus",
                    "embellishment": "unknown_catalog_effect",
                },
                "payload": {
                    "resolvedStats": {"strength": 90, "stamina": 130},
                    "itemSetId": "set:authority",
                    "capabilityOverrides": {"canEmbellish": True},
                    "enhancementManagement": management,
                },
            },
        )
        intent = self.intent()
        intent["slots"]["head"]["gemOptionIds"] = []
        context = self.released_context(
            capability_revision=gear_socket_authority.CAPABILITY_REVISION,
            item_rows=[row],
            option_rows=[self.option_row()],
            intent=intent,
        )

        result = gear_resolver.resolve(intent, context)

        self.assertTrue(
            context["variantsByKey"]["variant-head"]["capabilityOverrides"][
                "canEmbellish"
            ]
        )
        self.assertEqual(result["status"], "verified")
        self.assertTrue(result["constraints"]["slots"]["head"]["canEmbellish"])
        self.assertEqual(result["constraints"]["embellishmentUsed"], 0)
        self.assertNotIn(
            "embellishment",
            result["resolvedSlots"]["head"]["simcOptions"],
        )
        self.assertNotIn("unknown_catalog_effect", str(result["serializerInput"]))

    def test_loader_projects_only_strict_positive_integer_unique_limits(self):
        for name, raw_limit, expected in (
            ("boolean", True, 0),
            ("float", 1.5, 0),
            ("junk", "1bad", 0),
            ("leading zero", "01", 0),
            ("zero", 0, 0),
            ("negative", -1, 0),
            ("integer", 1, 1),
            ("decimal string", "2", 2),
        ):
            with self.subTest(name=name):
                item_row = list(copy.deepcopy(self.item_row()))
                item_row[2]["payload"]["uniqueGroupId"] = "item_group"
                item_row[2]["payload"]["uniqueLimit"] = raw_limit
                option_row = self.option_row(
                    payload={
                        "statDeltas": {},
                        "uniqueGroup": "gem_group",
                        "uniqueLimit": raw_limit,
                    }
                )

                _cursor, context = self.load(
                    cursor=self.cursor(
                        item_rows=[tuple(item_row)],
                        option_rows=[option_row],
                    )
                )

                self.assertEqual(
                    context["itemsById"]["item-head"]["uniqueLimit"],
                    expected,
                )
                self.assertEqual(
                    context["optionsById"]["gem-haste"]["uniqueLimit"],
                    expected,
                )

        for name, raw_group, expected in (
            ("boolean", True, ""),
            ("float", 1.5, ""),
            ("numeric", 123, ""),
            ("blank", "   ", ""),
            ("trimmed string", " explicit_group ", "explicit_group"),
        ):
            with self.subTest(group=name):
                item_row = list(copy.deepcopy(self.item_row()))
                item_row[2]["payload"]["uniqueGroupId"] = raw_group
                item_row[2]["payload"]["uniqueLimit"] = 1
                option_row = self.option_row(
                    simcOptions={"gem_id": "240983"},
                    payload={
                        "statDeltas": {},
                        "uniqueGroup": raw_group,
                        "uniqueLimit": 1,
                    },
                )
                _cursor, context = self.load(
                    cursor=self.cursor(
                        item_rows=[tuple(item_row)],
                        option_rows=[option_row],
                    )
                )
                self.assertEqual(
                    context["itemsById"]["item-head"]["uniqueGroupId"],
                    expected,
                )
                self.assertEqual(
                    context["optionsById"]["gem-haste"]["uniqueGroupId"],
                    expected,
                )

        _cursor, no_metadata = self.load(
            cursor=self.cursor(
                option_rows=[
                    self.option_row(
                        simcOptions={"gem_id": "240983"},
                        payload={"statDeltas": {}},
                    )
                ]
            )
        )
        self.assertEqual(
            no_metadata["optionsById"]["gem-haste"]["uniqueGroupId"],
            "",
        )
        self.assertEqual(
            no_metadata["optionsById"]["gem-haste"]["uniqueLimit"],
            0,
        )

    def test_loader_aggregates_option_unique_metadata_and_drops_group_conflicts(self):
        for name, top_limit in (
            ("top two payload one", 2),
            ("top junk payload one", "junk"),
            ("top bool payload one", True),
        ):
            with self.subTest(name=name):
                option_id, record = self.option_row(
                    uniqueGroup="explicit_group",
                    uniqueLimit=top_limit,
                    payload={
                        "statDeltas": {},
                        "uniqueGroup": "explicit_group",
                        "uniqueLimit": 1,
                    },
                )
                _cursor, context = self.load(
                    cursor=self.cursor(option_rows=[(option_id, record)])
                )
                self.assertEqual(
                    context["optionsById"]["gem-haste"]["uniqueGroupId"],
                    "explicit_group",
                )
                self.assertEqual(
                    context["optionsById"]["gem-haste"]["uniqueLimit"],
                    1,
                )

        option_id, conflicting = self.option_row(
            uniqueGroup="group_a",
            uniqueLimit=1,
            payload={
                "statDeltas": {},
                "uniqueGroup": "group_b",
                "uniqueLimit": 1,
            },
        )
        _cursor, context = self.load(
            cursor=self.cursor(option_rows=[(option_id, conflicting)])
        )
        self.assertNotIn("gem-haste", context["optionsById"])
        self.assertNotIn(
            "gem-haste",
            context["itemsById"]["item-head"]["allowedGemOptionIds"],
        )

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
                    "capabilityRevision",
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

    def test_item_capabilities_are_derived_from_verified_metadata(self):
        from server import gear_resolver

        ring = self.item_row(
            item={
                "slot": "finger1",
                "payload": {
                    "inventory_type": {"type": "FINGER", "name": "Finger"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 0, "name": "Miscellaneous"},
                    "sockets": [{"socket_type": {"type": "PRISMATIC"}}],
                },
            }
        )
        intent = self.intent(
            {
                "finger1": {
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
        runtime = self.runtime_authority(
            capabilityRevision=gear_socket_authority.LEGACY_CAPABILITY_REVISION
        )
        runtime["ruleParameters"]["inventoryTypesBySlot"] = {"finger1": ["finger1"]}
        runtime["ruleParameters"]["requiredSlots"] = ["finger1"]

        _cursor, context = self.load(
            cursor=self.cursor(item_rows=[ring], option_rows=[]),
            intent=intent,
            runtime=runtime,
        )
        item = context["itemsById"]["item-head"]
        snapshot = gear_resolver.resolve(intent, context)

        self.assertEqual(item["baseCapabilities"]["socketCount"], 1)
        self.assertTrue(item["baseCapabilities"]["canEnchant"])
        self.assertEqual(item["socketCount"], 1)
        self.assertEqual(snapshot["constraints"]["slots"]["finger1"]["socketCount"], 1)
        self.assertTrue(snapshot["constraints"]["slots"]["finger1"]["canEnchant"])

    def test_v2_base_capability_uses_materialized_item_socket_fact(self):
        valid_evidence = {
            "schemaRevision": gear_socket_authority.SOCKET_FACT_SCHEMA_REVISION,
            "authorityRevision": gear_socket_authority.CAPABILITY_REVISION,
            "minimumTotal": 2,
            "claims": [
                {
                    "minimumTotal": 2,
                    "scope": "exact_item",
                    "source": "official_item_payload",
                    "sourceRevision": "official-item-r1",
                }
            ],
        }
        row = self.item_row(
            item={
                "payload": {
                    "inventoryType": "head",
                    "armorType": "plate",
                    "baseStats": {"strength": 80},
                    "baseCapabilities": {
                        "socketCount": 2,
                        "canEnchant": True,
                        "canEmbellish": True,
                    },
                    "socketEvidence": valid_evidence,
                    "socketCount": 1,
                }
            },
            sources=[
                {
                    "id": "source-row-crafted-head",
                    "sourceType": "crafted",
                    "status": "verified",
                }
            ],
        )

        context = self.released_context(
            capability_revision=gear_socket_authority.CAPABILITY_REVISION,
            item_rows=[row],
        )

        capabilities = context["itemsById"]["item-head"]["baseCapabilities"]
        self.assertEqual(capabilities["socketCount"], 2)
        self.assertTrue(capabilities["canEnchant"])
        self.assertTrue(capabilities["canEmbellish"])

        invalid_facts = (
            ("missing", None, 2),
            (
                "wrong-schema",
                {**valid_evidence, "schemaRevision": "future-socket-fact"},
                2,
            ),
            (
                "wrong-authority",
                {**valid_evidence, "authorityRevision": "future-capability"},
                2,
            ),
            ("contradictory-total", {**valid_evidence, "minimumTotal": 1}, 2),
            ("missing-provenance", {**valid_evidence, "claims": []}, 2),
            (
                "malformed-provenance",
                {
                    **valid_evidence,
                    "claims": [
                        {
                            "minimumTotal": 2,
                            "scope": "",
                            "source": "official_item_payload",
                            "sourceRevision": "official-item-r1",
                        }
                    ],
                },
                2,
            ),
            ("boolean-count", valid_evidence, True),
            ("string-count", valid_evidence, "2"),
            ("negative-count", {**valid_evidence, "minimumTotal": -1}, -1),
        )
        for label, evidence, socket_count in invalid_facts:
            with self.subTest(label=label):
                payload = {
                    "inventoryType": "head",
                    "armorType": "plate",
                    "baseStats": {"strength": 80},
                    "baseCapabilities": {
                        "socketCount": socket_count,
                        "canEnchant": True,
                        "canEmbellish": True,
                    },
                }
                if evidence is not None:
                    payload["socketEvidence"] = evidence
                invalid = self.item_row(
                    item={"payload": payload},
                    sources=[
                        {
                            "id": "source-row-crafted-head",
                            "sourceType": "crafted",
                            "status": "verified",
                        }
                    ],
                )
                invalid_context = self.released_context(
                    capability_revision=gear_socket_authority.CAPABILITY_REVISION,
                    item_rows=[invalid],
                )
                invalid_capabilities = invalid_context["itemsById"]["item-head"][
                    "baseCapabilities"
                ]
                self.assertEqual(invalid_capabilities["socketCount"], 0)
                self.assertTrue(invalid_capabilities["canEnchant"])
                self.assertTrue(invalid_capabilities["canEmbellish"])

    def test_v2_authority_carries_only_verified_radiant_jewelbinder_eligibility(self):
        eligibility = {
            "schemaRevision": gear_socket_authority.SOCKET_ELIGIBILITY_SCHEMA_REVISION,
            "status": "verified",
            "eligibility": "active_pve_catalog",
            "sourceRevision": "season-17-active",
            "sourceIds": ["tier-set-item-head"],
            "sourceTypes": ["tier_set"],
        }
        socket_evidence = {
            "schemaRevision": gear_socket_authority.SOCKET_FACT_SCHEMA_REVISION,
            "authorityRevision": gear_socket_authority.CAPABILITY_REVISION,
            "minimumTotal": 1,
            "claims": [{
                "minimumTotal": 1,
                "scope": "season_slot",
                "source": "midnight_s1_radiant_jewelbinder",
                "sourceRevision": "season-17-active",
            }],
        }
        row = self.item_row()
        row[2]["payload"].update({
            "baseCapabilities": {"socketCount": 1},
            "socketEvidence": socket_evidence,
            "socketEligibility": eligibility,
        })

        context = self.released_context(
            capability_revision=gear_socket_authority.CAPABILITY_REVISION,
            item_rows=[row],
        )
        self.assertTrue(
            context["itemsById"]["item-head"][
                "radiantJewelbinderSocketEligibility"
            ]
        )

        invalid = copy.deepcopy(row)
        invalid[2]["payload"]["socketEligibility"]["sourceTypes"] = ["pvp"]
        invalid_context = self.released_context(
            capability_revision=gear_socket_authority.CAPABILITY_REVISION,
            item_rows=[invalid],
        )
        self.assertNotIn(
            "radiantJewelbinderSocketEligibility",
            invalid_context["itemsById"]["item-head"],
        )

    def test_v2_exact_variant_uses_materialized_socket_override(self):
        from server import gear_resolver

        valid_evidence = {
            "schemaRevision": gear_socket_authority.SOCKET_FACT_SCHEMA_REVISION,
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
        }
        row = self.item_row(
            item={
                "payload": {
                    "inventoryType": "head",
                    "armorType": "plate",
                    "baseStats": {"strength": 80},
                    "baseCapabilities": {"socketCount": 1},
                    "socketEvidence": {
                        "schemaRevision": gear_socket_authority.SOCKET_FACT_SCHEMA_REVISION,
                        "authorityRevision": gear_socket_authority.CAPABILITY_REVISION,
                        "minimumTotal": 1,
                        "claims": [
                            {
                                "minimumTotal": 1,
                                "scope": "exact_item",
                                "source": "official_item_payload",
                                "sourceRevision": "official-item-r1",
                            }
                        ],
                    },
                }
            },
            variant={
                "simcOptions": {"ilevel": "289", "gem_id": "240892/240900/240983"},
                "payload": {
                    "resolvedStats": {"strength": 90},
                    "capabilityOverrides": {
                        "socketCount": 2,
                        "canEmbellish": False,
                    },
                    "socketEvidence": valid_evidence,
                    "overlay": {
                        "status": "verified",
                        "sourceRefIds": ["evidence:pg:source:source-row-head"],
                        "statDeltas": {"haste": 5},
                        "capabilityOverrides": {
                            "socketCount": 9,
                            "canEmbellish": True,
                        },
                    },
                },
            },
        )
        one_socket = copy.deepcopy(list(row))
        one_socket[1] = "variant-head-one"
        one_socket[3]["id"] = "variant-row-head-one"
        one_socket[3]["variantKey"] = "variant-head-one"
        one_socket[3]["simcOptions"] = {"ilevel": "289", "gem_id": "240892/240900"}
        one_socket[3]["payload"]["capabilityOverrides"]["socketCount"] = 1
        one_socket[3]["payload"]["socketEvidence"]["minimumTotal"] = 1
        one_socket[3]["payload"]["socketEvidence"]["claims"][0][
            "minimumTotal"
        ] = 1

        context = self.released_context(
            capability_revision=gear_socket_authority.CAPABILITY_REVISION,
            item_rows=[row, tuple(one_socket)],
        )

        overrides = context["variantsByKey"]["variant-head"]["capabilityOverrides"]
        self.assertEqual(overrides["socketCount"], 2)
        self.assertFalse(overrides["canEmbellish"])
        self.assertEqual(
            context["variantsByKey"]["variant-head-one"]["capabilityOverrides"][
                "socketCount"
            ],
            1,
        )

        gem_ids = ["gem-haste", "gem-mastery", "gem-crit"]
        intent = self.intent()
        intent["slots"]["head"]["gemOptionIds"] = gem_ids
        option_rows = []
        for index, option_id in enumerate(gem_ids, start=1):
            _default_key, option = self.option_row(
                id=f"option-row-{option_id}",
                optionKey=option_id,
                name=f"Gem {index}",
                simcOptions={"gem_id": str(240000 + index)},
            )
            option_rows.append((option_id, option))
        chain_context = self.released_context(
            capability_revision=gear_socket_authority.CAPABILITY_REVISION,
            item_rows=[row],
            option_rows=option_rows,
            intent=intent,
        )

        snapshot = gear_resolver.resolve(intent, chain_context)

        self.assertEqual(snapshot["status"], "blocked")
        self.assertEqual(
            snapshot["constraints"]["slots"]["head"]["socketCount"],
            2,
        )
        socket_rule = next(
            result
            for result in snapshot["ruleResults"]
            if result["ruleId"] == "socket_and_gem"
        )
        self.assertEqual(socket_rule["status"], "blocked")
        self.assertEqual(
            socket_rule["problems"][0]["code"],
            "GEAR_GEM_SOCKET_CAPACITY_EXCEEDED",
        )
        projected_overlay = chain_context["variantsByKey"]["variant-head"][
            "overlay"
        ]
        self.assertEqual(projected_overlay["statDeltas"], {"haste": 5})
        self.assertTrue(
            projected_overlay["capabilityOverrides"]["canEmbellish"]
        )
        self.assertNotIn(
            "socketCount",
            projected_overlay["capabilityOverrides"],
        )

        zero_socket = copy.deepcopy(list(row))
        zero_socket[1] = "variant-head-zero"
        zero_socket[3]["id"] = "variant-row-head-zero"
        zero_socket[3]["variantKey"] = "variant-head-zero"
        zero_socket[3]["payload"]["capabilityOverrides"]["socketCount"] = 0
        zero_socket[3]["payload"]["socketEvidence"]["minimumTotal"] = 0
        zero_socket[3]["payload"]["socketEvidence"]["claims"] = []
        zero_context = self.released_context(
            capability_revision=gear_socket_authority.CAPABILITY_REVISION,
            item_rows=[tuple(zero_socket)],
        )
        self.assertNotIn(
            "socketCount",
            zero_context["variantsByKey"]["variant-head-zero"][
                "capabilityOverrides"
            ],
        )

        invalid_facts = (
            ("missing", None, 2),
            (
                "wrong-schema",
                {**valid_evidence, "schemaRevision": "future-socket-fact"},
                2,
            ),
            (
                "wrong-authority",
                {**valid_evidence, "authorityRevision": "future-capability"},
                2,
            ),
            ("contradictory-total", {**valid_evidence, "minimumTotal": 1}, 2),
            ("missing-provenance", {**valid_evidence, "claims": []}, 2),
            (
                "malformed-provenance",
                {
                    **valid_evidence,
                    "claims": [
                        {
                            "minimumTotal": 2,
                            "scope": "exact_variant",
                            "source": "",
                            "sourceRevision": "observed-variant-r1",
                        }
                    ],
                },
                2,
            ),
            ("boolean-count", valid_evidence, True),
            ("string-count", valid_evidence, "2"),
            ("negative-count", {**valid_evidence, "minimumTotal": -1}, -1),
        )
        for label, evidence, socket_count in invalid_facts:
            with self.subTest(label=label):
                invalid = copy.deepcopy(list(row))
                invalid[3]["payload"]["capabilityOverrides"]["socketCount"] = (
                    socket_count
                )
                if evidence is None:
                    invalid[3]["payload"].pop("socketEvidence")
                else:
                    invalid[3]["payload"]["socketEvidence"] = evidence
                invalid_context = self.released_context(
                    capability_revision=gear_socket_authority.CAPABILITY_REVISION,
                    item_rows=[tuple(invalid)],
                )
                invalid_overrides = invalid_context["variantsByKey"]["variant-head"][
                    "capabilityOverrides"
                ]
                self.assertNotIn("socketCount", invalid_overrides)
                self.assertFalse(invalid_overrides["canEmbellish"])

    def test_v2_raw_gem_sequence_without_socket_fact_does_not_create_capacity(self):
        from server import gear_resolver

        row = self.item_row(
            item={
                "payload": {
                    "inventoryType": "head",
                    "armorType": "plate",
                    "baseStats": {"strength": 80},
                    "baseCapabilities": {"socketCount": 1},
                    "socketEvidence": {
                        "schemaRevision": gear_socket_authority.SOCKET_FACT_SCHEMA_REVISION,
                        "authorityRevision": gear_socket_authority.CAPABILITY_REVISION,
                        "minimumTotal": 1,
                        "claims": [
                            {
                                "minimumTotal": 1,
                                "scope": "exact_item",
                                "source": "official_item_payload",
                                "sourceRevision": "official-item-r1",
                            }
                        ],
                    },
                }
            },
            variant={
                "simcOptions": {"ilevel": "289", "gem_id": "240892/240900"},
                "payload": {
                    "resolvedStats": {"strength": 90},
                    "capabilityOverrides": {"canEmbellish": False},
                },
            },
        )
        intent = self.intent()
        intent["slots"]["head"]["gemOptionIds"] = []

        context = self.released_context(
            capability_revision=gear_socket_authority.CAPABILITY_REVISION,
            item_rows=[row],
            intent=intent,
        )
        snapshot = gear_resolver.resolve(intent, context)

        self.assertEqual(context["itemsById"]["item-head"]["socketCount"], 1)
        overrides = context["variantsByKey"]["variant-head"]["capabilityOverrides"]
        self.assertNotIn("socketCount", overrides)
        self.assertFalse(overrides["canEmbellish"])
        self.assertEqual(snapshot["status"], "verified")
        self.assertEqual(snapshot["constraints"]["slots"]["head"]["socketCount"], 1)

    def test_v2_same_authority_context_keeps_exact_and_raw_sibling_socket_capacity_isolated(self):
        from server import gear_resolver

        zero_socket_evidence = {
            "schemaRevision": gear_socket_authority.SOCKET_FACT_SCHEMA_REVISION,
            "authorityRevision": gear_socket_authority.CAPABILITY_REVISION,
            "minimumTotal": 0,
            "claims": [],
        }
        exact_socket_evidence = {
            "schemaRevision": gear_socket_authority.SOCKET_FACT_SCHEMA_REVISION,
            "authorityRevision": gear_socket_authority.CAPABILITY_REVISION,
            "minimumTotal": 1,
            "claims": [
                {
                    "minimumTotal": 1,
                    "scope": "exact_variant",
                    "source": "observed_gem_occupancy",
                    "sourceRevision": "same-context-sibling-fixture-v1",
                }
            ],
        }
        item_payload = {
            "inventoryType": "head",
            "armorType": "plate",
            "baseStats": {},
            "baseCapabilities": {"socketCount": 0},
            "socketEvidence": zero_socket_evidence,
        }
        exact_row = self.item_row(
            item={"payload": item_payload},
            variant={
                "simcOptions": {"ilevel": "289", "gem_id": "240983"},
                "payload": {
                    "resolvedStats": {},
                    "capabilityOverrides": {"socketCount": 1},
                    "socketEvidence": exact_socket_evidence,
                },
            },
        )
        raw_row = list(copy.deepcopy(exact_row))
        raw_row[1] = "variant-head-raw-sibling"
        raw_row[3]["id"] = "variant-row-head-raw-sibling"
        raw_row[3]["variantKey"] = "variant-head-raw-sibling"
        raw_row[3]["payload"] = {"resolvedStats": {}}

        exact_intent = self.intent()
        exact_intent["slots"]["head"]["gemOptionIds"] = []
        context = self.released_context(
            capability_revision=gear_socket_authority.CAPABILITY_REVISION,
            item_rows=[exact_row, tuple(raw_row)],
            intent=exact_intent,
        )
        raw_intent = copy.deepcopy(exact_intent)
        raw_intent["slots"]["head"]["variantKey"] = "variant-head-raw-sibling"

        exact_snapshot = gear_resolver.resolve(exact_intent, context)
        raw_snapshot = gear_resolver.resolve(raw_intent, context)

        self.assertEqual(
            sorted(context["variantsByKey"]),
            ["variant-head", "variant-head-raw-sibling"],
        )
        self.assertEqual(exact_snapshot["status"], "verified")
        self.assertEqual(raw_snapshot["status"], "verified")
        self.assertEqual(
            exact_snapshot["constraints"]["slots"]["head"]["socketCount"],
            1,
        )
        self.assertEqual(
            raw_snapshot["constraints"]["slots"]["head"]["socketCount"],
            0,
        )
        self.assertNotIn(
            "socketCount",
            context["variantsByKey"]["variant-head-raw-sibling"]["capabilityOverrides"],
        )

    def test_v2_cross_class_and_dual_wield_samples_keep_socket_facts_exact_variant_only(self):
        from server import gear_resolver

        def zero_socket_evidence():
            return {
                "schemaRevision": gear_socket_authority.SOCKET_FACT_SCHEMA_REVISION,
                "authorityRevision": gear_socket_authority.CAPABILITY_REVISION,
                "minimumTotal": 0,
                "claims": [],
            }

        def exact_socket_evidence():
            return {
                "schemaRevision": gear_socket_authority.SOCKET_FACT_SCHEMA_REVISION,
                "authorityRevision": gear_socket_authority.CAPABILITY_REVISION,
                "minimumTotal": 1,
                "claims": [
                    {
                        "minimumTotal": 1,
                        "scope": "exact_variant",
                        "source": "observed_gem_occupancy",
                        "sourceRevision": "cross-class-fixture-v1",
                    }
                ],
            }

        class_samples = (
            ("mage", "frost", "cloth"),
            ("rogue", "assassination", "leather"),
            ("hunter", "beast_mastery", "mail"),
            ("warrior", "fury", "plate"),
        )
        for class_key, spec_key, armor_type in class_samples:
            with self.subTest(armor_type=armor_type):
                runtime = self.runtime_authority()
                runtime["requestedClassSpec"] = f"{class_key}:{spec_key}"
                runtime["playableClassSpecs"] = {class_key: [spec_key]}
                runtime["ruleParameters"]["inventoryTypesBySlot"] = {"head": ["head"]}
                runtime["ruleParameters"]["allowedArmorTypesByClass"] = {
                    class_key: [armor_type]
                }
                runtime["ruleParameters"]["armorRestrictedSlots"] = ["head"]
                runtime["ruleParameters"]["allowedWeaponTypesByClassSpec"] = {
                    f"{class_key}:{spec_key}": []
                }
                runtime["ruleParameters"]["dualWieldByClassSpec"] = {
                    f"{class_key}:{spec_key}": False
                }
                runtime["ruleParameters"]["weaponModesByClassSpec"] = {
                    f"{class_key}:{spec_key}": "none"
                }
                runtime["ruleParameters"]["requiredSlots"] = ["head"]
                base_intent = self.intent()
                base_intent["eligibilityContext"] = {
                    "classKey": class_key,
                    "specKey": spec_key,
                    "level": 90,
                }
                base_intent["slots"]["head"]["gemOptionIds"] = []
                item_payload = {
                    "inventoryType": "head",
                    "armorType": armor_type,
                    "allowedClassKeys": [class_key],
                    "allowedSpecKeys": [spec_key],
                    "baseStats": {},
                    "baseCapabilities": {"socketCount": 0},
                    "socketEvidence": zero_socket_evidence(),
                }
                exact_row = self.item_row(
                    item={"payload": item_payload},
                    variant={
                        "simcOptions": {"ilevel": "289", "gem_id": "240983"},
                        "payload": {
                            "resolvedStats": {},
                            "capabilityOverrides": {"socketCount": 1},
                            "socketEvidence": exact_socket_evidence(),
                        },
                    },
                )
                raw_intent = copy.deepcopy(base_intent)
                raw_intent["slots"]["head"]["variantKey"] = "variant-head-raw-only"
                raw_row = list(copy.deepcopy(exact_row))
                raw_row[1] = "variant-head-raw-only"
                raw_row[3]["id"] = f"variant-{armor_type}-raw-only"
                raw_row[3]["variantKey"] = "variant-head-raw-only"
                raw_row[3]["payload"] = {"resolvedStats": {}}
                shared_context = self.released_context(
                    capability_revision=gear_socket_authority.CAPABILITY_REVISION,
                    item_rows=[exact_row, tuple(raw_row)],
                    intent=base_intent,
                    runtime=runtime,
                )
                exact_snapshot = gear_resolver.resolve(base_intent, shared_context)
                raw_snapshot = gear_resolver.resolve(raw_intent, shared_context)

                self.assertEqual(
                    sorted(shared_context["variantsByKey"]),
                    ["variant-head", "variant-head-raw-only"],
                )
                self.assertEqual(exact_snapshot["status"], "verified")
                self.assertEqual(
                    exact_snapshot["constraints"]["slots"]["head"]["socketCount"],
                    1,
                )
                self.assertEqual(raw_snapshot["status"], "verified")
                self.assertEqual(
                    raw_snapshot["constraints"]["slots"]["head"]["socketCount"],
                    0,
                )
                self.assertNotIn(
                    "socketCount",
                    shared_context["variantsByKey"]["variant-head-raw-only"][
                        "capabilityOverrides"
                    ],
                )

        runtime = self.runtime_authority()
        runtime["ruleParameters"]["inventoryTypesBySlot"] = {
            "main_hand": ["weapon"],
            "off_hand": ["weapon"],
        }
        runtime["ruleParameters"]["armorRestrictedSlots"] = []
        runtime["ruleParameters"]["requiredSlots"] = ["main_hand", "off_hand"]
        weapon_item_payload = {
            "inventoryType": "weapon",
            "weaponType": "sword",
            "handedness": "one_hand",
            "allowedSlots": ["main_hand", "off_hand"],
            "allowedClassKeys": ["warrior"],
            "allowedSpecKeys": ["fury"],
            "baseStats": {},
            "baseCapabilities": {"socketCount": 0},
            "socketEvidence": zero_socket_evidence(),
        }
        exact_weapon_row = self.item_row(
            item={"slot": "main_hand", "payload": weapon_item_payload},
            variant={
                "slot": "main_hand",
                "simcOptions": {"ilevel": "289", "gem_id": "240983"},
                "payload": {
                    "resolvedStats": {},
                    "capabilityOverrides": {"socketCount": 1},
                    "socketEvidence": exact_socket_evidence(),
                },
            },
        )
        raw_weapon_row = list(copy.deepcopy(exact_weapon_row))
        raw_weapon_row[1] = "variant-off-hand-raw-only"
        raw_weapon_row[3]["id"] = "variant-off-hand-raw-only-row"
        raw_weapon_row[3]["variantKey"] = "variant-off-hand-raw-only"
        raw_weapon_row[3]["slot"] = "off_hand"
        raw_weapon_row[3]["payload"] = {"resolvedStats": {}}
        weapon_intent = self.intent(
            {
                "main_hand": {
                    "itemId": "item-head",
                    "variantKey": "variant-head",
                    "gemOptionIds": [],
                    "enchantOptionId": "",
                    "embellishmentOptionId": "",
                    "craftedOptionId": "",
                    "catalystOptionId": "",
                },
                "off_hand": {
                    "itemId": "item-head",
                    "variantKey": "variant-off-hand-raw-only",
                    "gemOptionIds": [],
                    "enchantOptionId": "",
                    "embellishmentOptionId": "",
                    "craftedOptionId": "",
                    "catalystOptionId": "",
                },
            }
        )
        weapon_context = self.released_context(
            capability_revision=gear_socket_authority.CAPABILITY_REVISION,
            item_rows=[exact_weapon_row, tuple(raw_weapon_row)],
            intent=weapon_intent,
            runtime=runtime,
        )
        weapon_snapshot = gear_resolver.resolve(weapon_intent, weapon_context)

        self.assertEqual(
            weapon_context["itemsById"]["item-head"]["allowedSlots"],
            ["main_hand", "off_hand"],
        )
        self.assertEqual(weapon_snapshot["status"], "verified")
        self.assertEqual(
            weapon_snapshot["constraints"]["slots"]["main_hand"]["socketCount"],
            1,
        )
        self.assertEqual(
            weapon_snapshot["constraints"]["slots"]["off_hand"]["socketCount"],
            0,
        )

    def test_v1_release_preserves_legacy_projection_during_rollout(self):
        row = self.item_row(
            item={
                "payload": {
                    "inventory_type": {"type": "FINGER", "name": "Finger"},
                    "sockets": [{"socket_type": {"type": "PRISMATIC"}}],
                }
            },
            variant={
                "simcOptions": {
                    "ilevel": "289",
                    "gem_id": "240892/240900",
                    "crafted_stats": "32/36",
                },
                "payload": {
                    "overlay": {
                        "status": "verified",
                        "capabilityOverrides": {
                            "socketCount": 9,
                            "canEmbellish": False,
                        },
                    }
                },
            },
        )

        context = self.released_context(
            capability_revision=gear_socket_authority.LEGACY_CAPABILITY_REVISION,
            item_rows=[row],
        )

        item = context["itemsById"]["item-head"]
        overrides = context["variantsByKey"]["variant-head"]["capabilityOverrides"]
        self.assertEqual(item["baseCapabilities"]["socketCount"], 1)
        self.assertTrue(item["baseCapabilities"]["canEnchant"])
        self.assertEqual(overrides["socketCount"], 2)
        self.assertTrue(overrides["canEmbellish"])
        legacy_overlay = context["variantsByKey"]["variant-head"]["overlay"]
        self.assertEqual(
            legacy_overlay["capabilityOverrides"]["socketCount"],
            9,
        )
        self.assertFalse(
            legacy_overlay["capabilityOverrides"]["canEmbellish"]
        )

    def test_exact_verified_variant_gems_raise_only_variant_socket_capacity(self):
        ring = list(self.item_row(
            item={
                "slot": "finger1",
                "payload": {
                    "inventory_type": {"type": "FINGER", "name": "Finger"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 0, "name": "Miscellaneous"},
                    "sockets": [{"socket_type": {"type": "PRISMATIC"}}],
                },
            },
            variant={"simcOptions": {"ilevel": "289", "gem_id": "240892/240900"}},
        ))
        second = copy.deepcopy(ring)
        second[1] = "variant-head-no-gems"
        second[3]["id"] = "variant-row-head-no-gems"
        second[3]["variantKey"] = "variant-head-no-gems"
        second[3]["simcOptions"] = {"ilevel": "289"}

        _cursor, context = self.load(
            cursor=self.cursor(item_rows=[tuple(ring), tuple(second)], option_rows=[]),
        )

        self.assertEqual(context["itemsById"]["item-head"]["baseCapabilities"]["socketCount"], 1)
        self.assertEqual(
            context["variantsByKey"]["variant-head"]["capabilityOverrides"].get("socketCount"),
            2,
        )
        self.assertEqual(
            context["variantsByKey"]["variant-head-no-gems"]["capabilityOverrides"],
            {},
        )

    def test_exact_verified_crafted_variant_enables_embellishment_capability(self):
        for option_name, option_value in (
            ("embellishment", "shadowflame_armor_patch"),
            ("crafted_stats", "32/36"),
        ):
            with self.subTest(option_name=option_name):
                row = self.item_row(
                    variant={
                        "sourceType": "crafted",
                        "simcOptions": {"ilevel": "289", option_name: option_value},
                    },
                )

                _cursor, context = self.load(
                    cursor=self.cursor(item_rows=[row], option_rows=[]),
                )

                self.assertTrue(
                    context["variantsByKey"]["variant-head"]["capabilityOverrides"].get(
                        "canEmbellish"
                    )
                )

    def test_raw_variant_enchant_does_not_expand_option_applicability(self):
        row = self.item_row(
            variant={"simcOptions": {"ilevel": "289", "enchant_id": "forged-raw-enchant"}},
        )

        _cursor, context = self.load(
            cursor=self.cursor(item_rows=[row], option_rows=[]),
        )

        self.assertNotIn(
            "canEnchant",
            context["variantsByKey"]["variant-head"]["capabilityOverrides"],
        )

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

    def test_loader_preserves_missing_selected_option_static_facts_for_attribute_downgrade(self):
        option = self.option_row(payload={})
        _cursor, context = self.load(cursor=self.cursor(option_rows=[option]))

        self.assertEqual(
            context["optionsById"]["gem-haste"]["attributeStaticFactsStatus"],
            "unavailable",
        )
        snapshot = gear_resolver.resolve(self.intent(), context)
        self.assertEqual(snapshot["status"], "verified")
        self.assertEqual(snapshot["attributeStaticFacts"]["status"], "unavailable")

    def test_loader_projects_verified_static_facts_from_exact_gem_identifier(self):
        option_id = "official-gem-240914"
        option = self.option_row(
            optionKey=option_id,
            simcOptions={"gem_id": "240914"},
            payload={
                "statSummary": "+999 Intellect",
                "evidenceSource": "display_only_fixture",
            },
        )
        intent = self.intent(
            {
                "head": {
                    "itemId": "item-head",
                    "variantKey": "variant-head",
                    "gemOptionIds": [option_id],
                    "enchantOptionId": "",
                    "embellishmentOptionId": "",
                    "craftedOptionId": "",
                    "catalystOptionId": "",
                }
            }
        )

        _cursor, context = self.load(
            cursor=self.cursor(option_rows=[(option_id, option[1])]),
            intent=intent,
        )

        projected = context["optionsById"][option_id]
        self.assertEqual(projected["attributeStaticFactsStatus"], "verified")
        self.assertEqual(
            projected["statDeltas"],
            {"crit_rating": 7, "versatility_rating": 16},
        )
        self.assertNotIn("999", json.dumps(projected))

    def test_loader_projects_verified_static_facts_from_exact_enchant_identifier(self):
        option_id = "official-enchant-8017"
        option = self.option_row(
            optionKey=option_id,
            optionType="enchant",
            simcOptions={"enchant_id": "8017"},
            payload={"statSummary": "+999 Mastery"},
        )
        intent = self.intent(
            {
                "head": {
                    "itemId": "item-head",
                    "variantKey": "variant-head",
                    "gemOptionIds": [],
                    "enchantOptionId": option_id,
                    "embellishmentOptionId": "",
                    "craftedOptionId": "",
                    "catalystOptionId": "",
                }
            }
        )

        _cursor, context = self.load(
            cursor=self.cursor(option_rows=[(option_id, option[1])]),
            intent=intent,
        )

        projected = context["optionsById"][option_id]
        self.assertEqual(projected["attributeStaticFactsStatus"], "verified")
        self.assertEqual(projected["statDeltas"], {"avoidance_rating": 37})
        self.assertNotIn("999", json.dumps(projected))

    def test_loader_projects_mage_primary_enchant_against_eligibility_context(self):
        option_id = "official-enchant-7935"
        option = self.option_row(
            optionKey=option_id,
            optionType="enchant",
            simcOptions={"enchant_id": "7935"},
            payload={"statSummary": "+999 Agility"},
        )
        intent = self.intent(
            {
                "head": {
                    "itemId": "item-head",
                    "variantKey": "variant-head",
                    "gemOptionIds": [],
                    "enchantOptionId": option_id,
                    "embellishmentOptionId": "",
                    "craftedOptionId": "",
                    "catalystOptionId": "",
                }
            }
        )
        intent["eligibilityContext"] = {
            "classKey": "mage",
            "specKey": "frost",
            "level": 90,
        }

        _cursor, context = self.load(
            cursor=self.cursor(option_rows=[(option_id, option[1])]),
            intent=intent,
        )

        projected = context["optionsById"][option_id]
        self.assertEqual(projected["attributeStaticFactsStatus"], "verified")
        self.assertEqual(projected["statDeltas"], {"intellect": 41, "stamina": 115})
        self.assertNotIn("999", json.dumps(projected))

    def test_loader_keeps_known_conditional_enchant_explicitly_non_panel(self):
        option_id = "official-enchant-8039"
        option = self.option_row(
            optionKey=option_id,
            optionType="enchant",
            simcOptions={"enchant_id": "8039"},
            payload={"statSummary": "+999 Haste"},
        )
        intent = self.intent(
            {
                "head": {
                    "itemId": "item-head",
                    "variantKey": "variant-head",
                    "gemOptionIds": [],
                    "enchantOptionId": option_id,
                    "embellishmentOptionId": "",
                    "craftedOptionId": "",
                    "catalystOptionId": "",
                }
            }
        )

        _cursor, context = self.load(
            cursor=self.cursor(option_rows=[(option_id, option[1])]),
            intent=intent,
        )

        projected = context["optionsById"][option_id]
        self.assertEqual(projected["attributeStaticFactsStatus"], "not_applicable")
        self.assertEqual(projected["statDeltas"], {})
        self.assertEqual(projected["attributeEffectClassification"], "conditional")
        self.assertNotIn("999", json.dumps(projected))

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

        runtime = self.runtime_authority()
        runtime["dependencyRevisions"].pop("capabilityRevision")
        _cursor, context = self.load(
            cursor=self.cursor(item_rows=[], option_rows=[]), runtime=runtime
        )
        self.assertIn(
            "runtimeAuthority.dependencyRevisions.capabilityRevision",
            context["missingFields"],
        )

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

    def test_loader_exposes_only_verified_item_media_for_import_projection(self):
        item = self.item_row(item={
            "payload": {
                "inventoryType": "head",
                "armorType": "plate",
                "baseStats": {"strength": 80, "stamina": 120},
                "itemSetId": "set:authority",
                "socketCount": 1,
                "canEnchant": False,
                "_metadata": {
                    "iconUrl": "https://render.worldofwarcraft.com/us/icons/56/inv_helm.jpg",
                    "gameAsset": {
                        "status": "verified",
                        "source": "blizzard",
                        "iconUrl": "https://render.worldofwarcraft.com/us/icons/56/inv_helm.jpg",
                    },
                },
            },
        })

        _cursor, context = self.load(cursor=self.cursor(item_rows=[item]))

        self.assertEqual(context["itemsById"]["item-head"]["iconUrl"], "https://render.worldofwarcraft.com/us/icons/56/inv_helm.jpg")
        self.assertEqual(context["itemsById"]["item-head"]["gameAsset"], {
            "status": "verified",
            "source": "blizzard",
            "iconUrl": "https://render.worldofwarcraft.com/us/icons/56/inv_helm.jpg",
        })

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
