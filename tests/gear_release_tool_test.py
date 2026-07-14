import copy
import io
import json
import subprocess
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from server import gear_release
from tests.gear_resolver_test import build_midnight_mage_resolver_fixture


class FakeReleaseStore:
    def __init__(self, gear_snapshot, templates=None):
        self.gear_snapshot = gear_snapshot
        self.templates = templates or []
        self.gear_seals = []
        self.community_seals = []
        self.requested_specs = []

    def snapshot_staging_gear(self):
        return copy.deepcopy(self.gear_snapshot)

    def snapshot_staging_community_templates(self, expected_specs):
        self.requested_specs = list(expected_specs)
        return copy.deepcopy(self.templates)

    def seal_gear_release(self, release, snapshot, **kwargs):
        self.gear_seals.append((copy.deepcopy(release), copy.deepcopy(snapshot), copy.deepcopy(kwargs)))
        return {"status": "inserted", "releaseId": release["releaseId"]}

    def seal_community_release(self, release, rows, **kwargs):
        self.community_seals.append((copy.deepcopy(release), copy.deepcopy(rows), copy.deepcopy(kwargs)))
        return {"status": "inserted", "releaseId": release["releaseId"]}


def build_midnight_mage_release_fixture():
    resolver_fixture = build_midnight_mage_resolver_fixture(
        8,
        include_reference_enhancements=True,
    )
    authority = resolver_fixture["authorityContext"]
    reference = resolver_fixture["referenceContract"]
    intent = resolver_fixture["intent"]
    items = []
    sources = []
    variants = []
    for item_id, item in authority["itemsById"].items():
        slot = (item.get("allowedSlots") or [""])[0]
        items.append({
            "itemId": item_id,
            "name": item.get("displayName") or item_id,
            "slot": slot,
            "sourceStatus": "verified",
            "payload": {
                field: copy.deepcopy(item.get(field))
                for field in (
                    "inventoryType",
                    "allowedSlots",
                    "allowedClassKeys",
                    "allowedSpecKeys",
                    "armorType",
                    "weaponType",
                    "handedness",
                    "baseStats",
                    "baseCapabilities",
                )
            },
        })
        sources.append({
            "sourceId": f"source-{item_id}",
            "itemId": item_id,
            "sourceType": "observed_profile",
            "sourceKey": reference["sourceKey"],
            "seasonRevision": "season-17-active",
            "payload": {"status": "verified", "sourceStatus": "verified"},
        })
    for variant_key, variant in authority["variantsByKey"].items():
        slot = next(
            raw_slot
            for raw_slot, selection in intent["slots"].items()
            if selection["variantKey"] == variant_key
        )
        payload = {
            "resolvedStats": copy.deepcopy(variant.get("resolvedStats") or {}),
            "capabilityOverrides": copy.deepcopy(variant.get("capabilityOverrides") or {}),
        }
        if variant.get("enhancementManagement"):
            payload["enhancementManagement"] = copy.deepcopy(
                variant["enhancementManagement"]
            )
        raw_enchant = str((variant.get("simcOptions") or {}).get("enchant_id") or "").strip()
        item_level = int(variant.get("itemLevel") or 0)
        if raw_enchant and (
            slot not in set(reference["enchantEligibleSlots"])
            or (slot == "main_hand" and "/" in raw_enchant)
        ):
            payload.update({
                "statSource": "simulationcraft",
                "statDisplayStatus": "verified_variant",
                "itemStats": [{"type": "intellect", "value": 100}],
                "simcItemId": variant["itemId"],
                "simcItemLevel": item_level,
                "simcEncodedItem": (
                    f"observed_item,id={variant['itemId']},"
                    f"ilevel={item_level},enchant_id={raw_enchant}"
                ),
            })
        variants.append({
            "variantId": f"row-{variant_key}",
            "itemId": variant["itemId"],
            "variantKey": variant_key,
            "slot": slot,
            "sourceType": "observed_profile",
            "itemLevel": item_level,
            "simcOptions": copy.deepcopy(variant.get("simcOptions") or {}),
            "status": "verified",
            "blockers": [],
            "payload": payload,
        })
    options = []
    for option_key, option in authority["optionsById"].items():
        option_type = "socket" if option.get("optionType") == "gem" else option.get("optionType")
        options.append({
            "optionId": f"row-{option_key}",
            "optionKey": option_key,
            "optionType": option_type,
            "name": option.get("displayName") or option_key,
            "applicableSlots": copy.deepcopy(option.get("applicableSlots") or []),
            "simcOptions": copy.deepcopy(option.get("simcOptions") or {}),
            "status": "verified",
            "isVisible": True,
            "payload": {
                "statDeltas": copy.deepcopy(option.get("statDeltas") or {}),
                "uniqueGroup": option.get("uniqueGroupId") or "",
                "uniqueLimit": option.get("uniqueLimit") or 0,
            },
        })
    gear_items = []
    source_enhancements = reference["sourceEnhancementBySlot"]
    for slot in reference["requiredSlots"]:
        selection = intent["slots"][slot]
        raw_enhancement = source_enhancements.get(slot, {})
        raw = {
            "slot": slot,
            "itemId": selection["itemId"],
            "variantKey": selection["variantKey"],
        }
        if raw_enhancement.get("gemIds"):
            raw["gem_id"] = "/".join(raw_enhancement["gemIds"])
        if raw_enhancement.get("enchantIds"):
            raw["enchant_id"] = "/".join(raw_enhancement["enchantIds"])
        if raw_enhancement.get("embellishment"):
            raw["embellishment"] = raw_enhancement["embellishment"]
        gear_items.append(raw)
    template = {
        "templateId": reference["templateId"],
        "classKey": reference["classKey"],
        "specKey": reference["specKey"],
        "sourceKey": reference["sourceKey"],
        "sourceUrl": "https://raider.io/characters/cn/reference-mage",
        "sourceStatus": "synced",
        "status": "complete",
        "signature": "gear:mage:frost:reference",
        "sampleCount": 1,
        "profileHash": "profile:mage:frost:reference",
        "gearHash": "gear:mage:frost:reference",
        "gearItems": gear_items,
        "readySlotCount": len(reference["requiredSlots"]),
        "missingSlots": [],
        "sourceRefs": [{
            "sourceType": reference["sourceKey"],
            "sourceUrl": "https://raider.io/characters/cn/reference-mage",
            "sampleCount": 1,
        }],
        "payload": {
            "templateEvidence": {
                "sampleCount": 1,
                "profileHash": "profile:mage:frost:reference",
                "gearHash": "gear:mage:frost:reference",
            }
        },
        "updatedAt": "2026-07-14T00:00:00+00:00",
        "expiresAt": "2026-07-28T00:00:00+00:00",
    }
    return {
        "resolverFixture": resolver_fixture,
        "snapshot": {
            "items": items,
            "sources": sources,
            "variants": variants,
            "options": options,
        },
        "template": template,
    }

class GearReleaseToolTest(unittest.TestCase):
    def dependencies(self):
        return {
            "gearRuleRevision": "gear-rule-matrix-v1",
            "resolverContractRevision": "gear-resolver-contract-v1",
            "serializerRevision": "websim-profile-compat-v1",
            "simcRuntimeRevision": "simc-r1",
            "statPolicyRevision": "stat-snapshot-policy-v1",
            "selectionSchemaRevision": "selection-intent-v1",
            "capabilityRevision": "gear-capability-v1",
        }

    def snapshot(self):
        return {
            "items": [{"itemId": "item-a", "name": "A", "slot": "head", "sourceStatus": "verified", "payload": {}, "updatedAt": "2026-07-11T05:00:00+00:00"}],
            "sources": [{"sourceId": "source-a", "itemId": "item-a", "sourceType": "observed_profile", "sourceKey": "profile:a", "payload": {"status": "verified"}, "updatedAt": "2026-07-11T05:00:00+00:00"}],
            "variants": [{"variantId": "variant-a-id", "itemId": "item-a", "variantKey": "variant-a", "slot": "head", "sourceType": "observed_profile", "itemLevel": 289, "simcOptions": {"ilevel": "289"}, "status": "verified", "blockers": [], "payload": {"resolvedStats": {"intellect": 100}}, "updatedAt": "2026-07-11T05:00:00+00:00"}],
            "options": [],
        }

    def template(self, template_id="template-a", source_key="raiderio_observed_profile"):
        return {
            "templateId": template_id,
            "classKey": "mage",
            "specKey": "arcane",
            "name": "Observed A",
            "sourceKey": source_key,
            "sourceName": "Raider.IO",
            "sourceUrl": "https://raider.io/characters/cn/a",
            "sourceStatus": "synced",
            "status": "complete",
            "signature": "gear:a",
            "sourceRefs": [{"sampleCount": 1, "sourceUrl": "https://raider.io/characters/cn/a"}],
            "gearItems": [
                {
                    "slot": "head",
                    "itemId": "item-a",
                    "variantKey": "variant-a",
                    "itemStats": [{"key": "intellect", "value": 999999}],
                    "simcReady": True,
                    "gem_id": "forged-raw-gem",
                    "enchant_id": "forged-raw-enchant",
                }
            ],
            "readySlotCount": 16,
            "missingSlots": [],
            "payload": {
                "templateEvidence": {
                    "status": "observed_verified",
                    "profileHash": "profile:a",
                    "gearHash": "gear:a",
                    "sampleCount": 1,
                }
            },
            "updatedAt": "2026-07-11T05:00:00+00:00",
            "expiresAt": "2026-07-25T05:00:00+00:00",
            "scanRunId": "scan-a",
        }

    def verified_result(self, gear_release_id):
        return {
            "status": "verified",
            "aggregateLegality": {"status": "verified", "problemCodes": []},
            "profileReadiness": {"status": "verified", "simcReady": True, "missingSlots": []},
            "resolvedGearSignature": "sha256:resolved-a",
            "dependencyVector": {
                **self.dependencies(),
                "seasonRevision": "season-17",
                "gearCatalogReleaseId": gear_release_id,
                "gearCatalogRevision": gear_release_id,
            },
            "eligibilityContext": {"classKey": "mage", "specKey": "arcane", "level": 90},
            "resolvedSlots": {"head": {"itemId": "item-a", "variantKey": "variant-a", "resolvedStats": {"intellect": 100}}},
            "staticAttributes": {"intellect": 100},
            "setState": {"itemSetCounts": {}},
            "constraints": {"slots": {}},
            "serializerInput": {"gearItems": [{"slot": "head", "itemId": "item-a"}]},
            "problems": [],
        }

    def test_template_intent_contains_only_exact_server_allowed_selection_fields(self):
        from server.gear_release_tool import selection_intent_from_template

        intent = selection_intent_from_template(
            self.template(),
            gear_release_id="gear-release:sha256:target",
            season_revision="season-17",
            level=90,
        )

        self.assertEqual(set(intent), {"schemaRevision", "authoredAgainst", "eligibilityContext", "slots"})
        self.assertEqual(intent["slots"]["head"], {
            "itemId": "item-a",
            "variantKey": "variant-a",
            "gemOptionIds": [],
            "enchantOptionId": "",
            "embellishmentOptionId": "",
            "craftedOptionId": "",
            "catalystOptionId": "",
        })
        self.assertNotIn("999999", str(intent))
        self.assertNotIn("forged", str(intent))

    def test_template_intent_reconciles_ordered_duplicate_enhancements_to_unique_verified_options(self):
        from server.gear_release_tool import selection_intent_from_template
        from server.gear_socket_authority import CAPABILITY_REVISION

        snapshot = self.snapshot()
        snapshot["items"][0]["slot"] = "back"
        snapshot["items"][0]["payload"] = {
            "baseCapabilities": {
                "socketCount": 2,
                "canEnchant": True,
                "canEmbellish": True,
            }
        }
        snapshot["variants"][0].update({
            "slot": "back",
            "simcOptions": {
                "ilevel": "289",
                "gem_id": "240892/240892",
                "enchant_id": "4897",
                "embellishment": "arcanoweave_lining",
            },
            "payload": {
                "resolvedStats": {"intellect": 100},
                "capabilityOverrides": {"socketCount": 2},
                "enhancementManagement": {
                    "schemaRevision": "gear-enhancement-management-v1",
                    "authorityRevision": CAPABILITY_REVISION,
                    "fields": {
                        "gem_id": "editor_managed",
                        "enchant_id": "editor_managed",
                        "embellishment": "editor_managed",
                    },
                },
            },
        })
        snapshot["options"] = [
            {
                "optionId": "option-gem-240892",
                "optionKey": "gem-240892",
                "optionType": "socket",
                "name": "Canonical gem 240892",
                "applicableSlots": ["back"],
                "simcOptions": {"gem_id": "240892"},
                "status": "verified",
                "isVisible": True,
                "payload": {},
            },
            {
                "optionId": "option-enchant-4897",
                "optionKey": "enchant-back-4897",
                "optionType": "enchant",
                "name": "Canonical enchant 4897",
                "applicableSlots": ["back"],
                "simcOptions": {"enchant_id": "4897"},
                "status": "verified",
                "isVisible": True,
                "payload": {},
            },
            {
                "optionId": "option-embellishment-lining",
                "optionKey": "embellishment-arcanoweave-lining",
                "optionType": "embellishment",
                "name": "Arcanoweave Lining",
                "applicableSlots": ["back"],
                "simcOptions": {"embellishment": "arcanoweave_lining"},
                "status": "verified",
                "isVisible": True,
                "payload": {},
            },
            {
                "optionId": "option-forged-top-level",
                "optionKey": "forged-top-level-option",
                "optionType": "socket",
                "name": "Must not be trusted",
                "applicableSlots": ["back"],
                "simcOptions": {"gem_id": "999999"},
                "status": "verified",
                "isVisible": True,
                "payload": {},
            },
        ]
        template = self.template()
        template["gearItems"] = [{
            "slot": "back",
            "itemId": "item-a",
            "variantKey": "variant-a",
            "gem_id": "240892/240892",
            "enchant_id": "4897",
            "embellishment": "arcanoweave_lining",
            "gemOptionIds": ["forged-top-level-option"],
            "enchantOptionId": "forged-top-level-option",
            "embellishmentOptionId": "forged-top-level-option",
        }]

        intent = selection_intent_from_template(
            template,
            gear_release_id="gear-release:sha256:target",
            season_revision="season-17",
            level=90,
            gear_snapshot=snapshot,
            capability_revision=CAPABILITY_REVISION,
        )

        self.assertEqual(intent["slots"]["back"]["gemOptionIds"], [
            "gem-240892",
            "gem-240892",
        ])
        self.assertEqual(intent["slots"]["back"]["enchantOptionId"], "enchant-back-4897")
        self.assertEqual(
            intent["slots"]["back"]["embellishmentOptionId"],
            "embellishment-arcanoweave-lining",
        )
        self.assertNotIn("forged-top-level-option", str(intent))

    def test_template_intent_drops_ambiguous_or_unverified_raw_enhancement_matches(self):
        from server.gear_release_tool import selection_intent_from_template
        from server.gear_socket_authority import CAPABILITY_REVISION

        snapshot = self.snapshot()
        snapshot["items"][0]["payload"] = {
            "baseCapabilities": {"socketCount": 1, "canEnchant": False, "canEmbellish": False}
        }
        snapshot["variants"][0]["simcOptions"] = {"ilevel": "289", "gem_id": "240892"}
        snapshot["variants"][0]["payload"] = {
            "resolvedStats": {"intellect": 100},
            "capabilityOverrides": {"socketCount": 1},
            "enhancementManagement": {
                "schemaRevision": "gear-enhancement-management-v1",
                "authorityRevision": CAPABILITY_REVISION,
                "fields": {"gem_id": "editor_managed"},
            },
        }
        snapshot["options"] = [
            {
                "optionId": f"option-{suffix}",
                "optionKey": f"gem-240892-{suffix}",
                "optionType": "socket",
                "name": suffix,
                "applicableSlots": ["head"],
                "simcOptions": {"gem_id": "240892"},
                "status": status,
                "isVisible": True,
                "payload": {},
            }
            for suffix, status in (("a", "verified"), ("b", "verified"), ("blocked", "blocked"))
        ]
        template = self.template()
        template["gearItems"][0]["gem_id"] = "240892"

        intent = selection_intent_from_template(
            template,
            gear_release_id="gear-release:sha256:target",
            season_revision="season-17",
            level=90,
            gear_snapshot=snapshot,
            capability_revision=CAPABILITY_REVISION,
        )

        self.assertEqual(intent["slots"]["head"]["gemOptionIds"], [])

    def test_community_release_blocks_template_gems_beyond_materialized_capacity(self):
        from server.gear_release_store import GearReleaseIntegrityError, gear_snapshot_summary
        from server.gear_release_tool import build_legacy_community_release
        from server.gear_socket_authority import CAPABILITY_REVISION

        snapshot = self.snapshot()
        snapshot["items"][0]["payload"] = {
            "baseCapabilities": {
                "socketCount": 1,
                "canEnchant": False,
                "canEmbellish": False,
            }
        }
        snapshot["variants"][0]["simcOptions"] = {"ilevel": "289", "gem_id": "240892"}
        snapshot["variants"][0]["payload"] = {
            "resolvedStats": {"intellect": 100},
            "capabilityOverrides": {"socketCount": 1},
            "enhancementManagement": {
                "schemaRevision": "gear-enhancement-management-v1",
                "authorityRevision": CAPABILITY_REVISION,
                "fields": {"gem_id": "editor_managed"},
            },
        }
        snapshot["options"] = [{
            "optionId": "option-gem-240892",
            "optionKey": "gem-240892",
            "optionType": "socket",
            "name": "Canonical gem 240892",
            "applicableSlots": ["head"],
            "simcOptions": {"gem_id": "240892"},
            "status": "verified",
            "isVisible": True,
            "payload": {},
        }]
        template = self.template()
        template["gearItems"][0]["gem_id"] = "240892/240892"
        dependencies = {**self.dependencies(), "capabilityRevision": CAPABILITY_REVISION}
        gear = gear_release.build_release(
            release_kind="gear",
            season_revision="season-17",
            schema_revision="gear-release-v1",
            content=gear_snapshot_summary(snapshot),
            dependency_revisions=dependencies,
            release_status="validated",
            source={"sourceRevision": "capacity-contradiction-test"},
        )
        store = FakeReleaseStore(snapshot, [template])

        with self.assertRaisesRegex(
            GearReleaseIntegrityError,
            "template gem sequence conflicts with materialized socket capacity",
        ):
            build_legacy_community_release(
                store,
                gear_release_descriptor=gear,
                gear_snapshot=snapshot,
                dependency_revisions=dependencies,
                expected_specs=[("mage", "arcane")],
                now="2026-07-14T01:00:00+00:00",
            )

        self.assertEqual(store.community_seals, [])

    def test_community_release_blocks_conflicting_gem_sources_when_one_exceeds_capacity(self):
        from server.gear_release_store import GearReleaseIntegrityError, gear_snapshot_summary
        from server.gear_release_tool import build_legacy_community_release
        from server.gear_socket_authority import CAPABILITY_REVISION

        snapshot = self.snapshot()
        snapshot["items"][0]["payload"] = {
            "baseCapabilities": {
                "socketCount": 1,
                "canEnchant": False,
                "canEmbellish": False,
            }
        }
        snapshot["variants"][0]["simcOptions"] = {"ilevel": "289", "gem_id": "240892"}
        snapshot["variants"][0]["payload"] = {
            "resolvedStats": {"intellect": 100},
            "capabilityOverrides": {"socketCount": 1},
            "enhancementManagement": {
                "schemaRevision": "gear-enhancement-management-v1",
                "authorityRevision": CAPABILITY_REVISION,
                "fields": {"gem_id": "editor_managed"},
            },
        }
        snapshot["options"] = [{
            "optionId": "option-gem-240892",
            "optionKey": "gem-240892",
            "optionType": "socket",
            "name": "Canonical gem 240892",
            "applicableSlots": ["head"],
            "simcOptions": {"gem_id": "240892"},
            "status": "verified",
            "isVisible": True,
            "payload": {},
        }]
        template = self.template()
        template["gearItems"][0]["gem_id"] = "240892"
        template["enhancementBySlot"] = {
            "head": {"gem_id": "240892/240892"},
        }
        dependencies = {**self.dependencies(), "capabilityRevision": CAPABILITY_REVISION}
        gear = gear_release.build_release(
            release_kind="gear",
            season_revision="season-17",
            schema_revision="gear-release-v1",
            content=gear_snapshot_summary(snapshot),
            dependency_revisions=dependencies,
            release_status="validated",
            source={"sourceRevision": "multi-source-capacity-contradiction-test"},
        )
        store = FakeReleaseStore(snapshot, [template])

        with self.assertRaisesRegex(
            GearReleaseIntegrityError,
            "template gem sequence conflicts with materialized socket capacity",
        ):
            build_legacy_community_release(
                store,
                gear_release_descriptor=gear,
                gear_snapshot=snapshot,
                dependency_revisions=dependencies,
                expected_specs=[("mage", "arcane")],
                now="2026-07-14T01:00:00+00:00",
            )

        self.assertEqual(store.community_seals, [])

    def test_v2_release_blocks_raw_gems_without_materialized_socket_capacity(self):
        from server.gear_release_store import GearReleaseIntegrityError
        from server.gear_release_tool import _materialize_enhancement_management
        from server.gear_socket_authority import CAPABILITY_REVISION

        snapshot = self.snapshot()
        snapshot["items"][0]["payload"] = {
            "baseCapabilities": {"socketCount": 0, "canEnchant": False, "canEmbellish": False}
        }
        snapshot["variants"][0]["simcOptions"] = {
            "ilevel": "289",
            "gem_id": "240892/not-a-gem",
        }
        snapshot["variants"][0]["payload"] = {
            "resolvedStats": {"intellect": 100},
            "capabilityOverrides": {"socketCount": 0},
        }

        with self.assertRaisesRegex(
            GearReleaseIntegrityError,
            "raw gem sequence conflicts with materialized socket capacity",
        ):
            _materialize_enhancement_management(snapshot, CAPABILITY_REVISION)

    def test_exact_midnight_mage_candidate_seals_complete_editable_enhancement_intent(self):
        from server import gear_resolver
        from server.gear_release_store import build_candidate_authority_context
        from server.gear_release_tool import (
            build_legacy_community_release,
            prepare_staging_gear_release,
            selection_intent_from_template,
        )
        from server.gear_socket_authority import CAPABILITY_REVISION
        from server.websim_payload import gear_resolver_runtime_authority

        fixture = build_midnight_mage_release_fixture()
        resolver_fixture = fixture["resolverFixture"]
        authority = resolver_fixture["authorityContext"]
        reference = resolver_fixture["referenceContract"]
        dependencies = {
            key: value
            for key, value in authority["dependencyVector"].items()
            if key not in {
                "seasonRevision",
                "gearCatalogReleaseId",
                "gearCatalogRevision",
            }
        }
        store = FakeReleaseStore(fixture["snapshot"], [fixture["template"]])
        prepared_gear = prepare_staging_gear_release(
            store,
            season_revision="season-17-active",
            dependency_revisions=dependencies,
            socket_bonus_minimums={"9300": 1},
        )
        managed_by_slot = {
            row["slot"]: row["payload"].get("enhancementManagement", {}).get("fields", {})
            for row in prepared_gear["snapshot"]["variants"]
        }
        self.assertEqual(managed_by_slot["head"]["enchant_id"], "source_only")
        self.assertEqual(managed_by_slot["shoulder"]["enchant_id"], "source_only")
        self.assertEqual(managed_by_slot["waist"]["enchant_id"], "source_only")
        self.assertEqual(managed_by_slot["main_hand"]["enchant_id"], "source_only")
        intent = selection_intent_from_template(
            fixture["template"],
            gear_release_id=prepared_gear["release"]["releaseId"],
            season_revision="season-17-active",
            level=reference["level"],
            gear_snapshot=prepared_gear["snapshot"],
            capability_revision=CAPABILITY_REVISION,
        )

        self.assertEqual(intent["slots"], resolver_fixture["intent"]["slots"])
        self.assertEqual(
            sum(len(selection["gemOptionIds"]) for selection in intent["slots"].values()),
            8,
        )
        self.assertEqual(
            sum(bool(selection["enchantOptionId"]) for selection in intent["slots"].values()),
            6,
        )
        self.assertEqual(
            sum(bool(selection["embellishmentOptionId"]) for selection in intent["slots"].values()),
            2,
        )
        self.assertEqual(intent["slots"]["finger1"]["gemOptionIds"], [
            "gem-240892",
            "gem-240983",
        ])
        runtime = gear_resolver_runtime_authority(
            "mage",
            "frost",
            simc_runtime_revision=dependencies["simcRuntimeRevision"],
        )
        runtime["dependencyRevisions"] = dict(dependencies)
        production_authority = build_candidate_authority_context(
            prepared_gear["snapshot"],
            intent,
            runtime,
            prepared_gear["release"],
        )
        production_snapshot = gear_resolver.resolve(intent, production_authority)
        self.assertEqual(production_snapshot["status"], "verified")
        serializer_by_slot = {
            item["slot"]: item
            for item in production_snapshot["serializerInput"]["gearItems"]
        }
        self.assertEqual(serializer_by_slot["head"]["simcOptions"]["enchant_id"], "8017")
        self.assertEqual(serializer_by_slot["shoulder"]["simcOptions"]["enchant_id"], "8001")
        self.assertEqual(serializer_by_slot["waist"]["simcOptions"]["enchant_id"], "4223")
        self.assertEqual(serializer_by_slot["main_hand"]["simcOptions"]["enchant_id"], "8039/8052")
        prepared = build_legacy_community_release(
            store,
            gear_release_descriptor=prepared_gear["release"],
            gear_snapshot=prepared_gear["snapshot"],
            dependency_revisions=dependencies,
            expected_specs=[("mage", "frost")],
            now="2026-07-14T01:00:00+00:00",
            level=reference["level"],
        )

        self.assertEqual(prepared["election"]["status"], "validated")
        self.assertEqual(prepared["rows"][0]["selectionIntent"], intent)
        self.assertEqual(prepared["seal"]["status"], "inserted")
        self.assertEqual(len(store.community_seals), 1)

    def test_build_legacy_gear_release_snapshots_and_seals_inactive_candidate(self):
        from server.gear_release_tool import build_legacy_gear_release

        store = FakeReleaseStore(self.snapshot())
        result = build_legacy_gear_release(
            store,
            season_revision="season-17",
            dependency_revisions=self.dependencies(),
            source_revision="legacy-import-r0",
            socket_bonus_minimums={"9300": 1},
        )

        release = result["release"]
        self.assertEqual(release["releaseKind"], "gear")
        self.assertEqual(release["releaseStatus"], "validated")
        self.assertEqual(release["source"]["sourceRevision"], "legacy-import-r0")
        self.assertEqual(result["seal"]["status"], "inserted")
        self.assertEqual(len(store.gear_seals), 1)
        self.assertNotIn("manifest", result)
        self.assertNotIn("pointer", result)

    def test_prepare_staging_gear_release_materializes_socket_facts_before_hash(self):
        from server.gear_release_store import gear_snapshot_summary
        from server.gear_release_tool import prepare_staging_gear_release

        snapshot = self.snapshot()
        snapshot["variants"][0]["simcOptions"]["bonus_id"] = "9300"
        raw_summary = gear_snapshot_summary(snapshot)

        try:
            result = prepare_staging_gear_release(
                FakeReleaseStore(snapshot),
                season_revision="midnight-season-1",
                dependency_revisions=self.dependencies(),
                socket_bonus_minimums={"9300": 2},
            )
        except TypeError as exc:
            self.fail(f"prepare_staging_gear_release must accept socket evidence: {exc}")

        materialized = result["snapshot"]
        self.assertNotIn("capabilityOverrides", materialized["variants"][0])
        self.assertNotIn("socketEvidence", materialized["variants"][0])
        self.assertEqual(
            materialized["variants"][0]["payload"]["capabilityOverrides"]["socketCount"],
            2,
        )
        self.assertEqual(result["release"]["content"], gear_snapshot_summary(materialized))
        self.assertNotEqual(result["release"]["content"]["snapshotHash"], raw_summary["snapshotHash"])
        source_evidence = result["release"]["source"]["sourceEvidence"]
        self.assertEqual(source_evidence["simcRuntimeRevision"], "simc-r1")
        self.assertTrue(source_evidence["socketProbeDigest"].startswith("sha256:"))
        self.assertTrue(source_evidence["materializedSocketFactDigest"].startswith("sha256:"))

    def test_prepare_staging_gear_release_seals_only_v2_exact_editor_managed_enchants(self):
        from server.gear_release_tool import prepare_staging_gear_release
        from server.gear_socket_authority import CAPABILITY_REVISION, LEGACY_CAPABILITY_REVISION

        snapshot = self.snapshot()
        snapshot["items"][0]["slot"] = "back"
        snapshot["items"][0]["payload"]["baseCapabilities"] = {
            "socketCount": 0,
            "canEmbellish": False,
        }
        snapshot["variants"] = [
            {
                **snapshot["variants"][0],
                "variantId": "variant-back",
                "variantKey": "variant-back",
                "slot": "back",
                "simcOptions": {
                    "ilevel": "289",
                    "enchant_id": "4897",
                    "embellishment": "arcanoweave_lining",
                },
            },
            {
                **snapshot["variants"][0],
                "variantId": "variant-slot-mismatch",
                "variantKey": "variant-slot-mismatch",
                "slot": "shoulder",
                "sourceType": "dungeon",
                "simcOptions": {"ilevel": "289", "enchant_id": "4897"},
            },
            {
                **snapshot["variants"][0],
                "variantId": "variant-item-slot-fallback",
                "variantKey": "variant-item-slot-fallback",
                "slot": "",
                "simcOptions": {"ilevel": "289", "enchant_id": "4897"},
            },
            {
                **snapshot["variants"][0],
                "variantId": "variant-source-only-enchant",
                "variantKey": "variant-source-only-enchant",
                "slot": "main_hand",
                "simcOptions": {"ilevel": "298", "enchant_id": "8039/8052"},
                "itemLevel": 298,
                "payload": {
                    "resolvedStats": {"intellect": 100},
                    "statSource": "simulationcraft",
                    "statDisplayStatus": "verified_variant",
                    "itemStats": [{"type": "intellect", "value": 100}],
                    "simcItemId": "item-a",
                    "simcItemLevel": 298,
                    "simcEncodedItem": "item_a,id=item-a,ilevel=298,enchant_id=8039/8052",
                },
            },
            {
                **snapshot["variants"][0],
                "variantId": "variant-observed-editable-unmatched",
                "variantKey": "variant-observed-editable-unmatched",
                "slot": "back",
                "simcOptions": {"ilevel": "289", "enchant_id": "9999"},
            },
            {
                **snapshot["variants"][0],
                "variantId": "variant-observed-nonenchant-overlap",
                "variantKey": "variant-observed-nonenchant-overlap",
                "slot": "head",
                "simcOptions": {"ilevel": "289", "enchant_id": "7777"},
                "payload": {
                    "resolvedStats": {"intellect": 100},
                    "statSource": "simulationcraft",
                    "statDisplayStatus": "verified_variant",
                    "itemStats": [{"type": "intellect", "value": 100}],
                    "simcItemId": "item-a",
                    "simcItemLevel": 289,
                    "simcEncodedItem": "item_a,id=item-a,ilevel=289,enchant_id=7777",
                },
            },
            {
                **snapshot["variants"][0],
                "variantId": "variant-observed-nonenchant-unknown",
                "variantKey": "variant-observed-nonenchant-unknown",
                "slot": "head",
                "simcOptions": {"ilevel": "289", "enchant_id": "999999"},
            },
            {
                **snapshot["variants"][0],
                "variantId": "variant-observed-composite-unknown",
                "variantKey": "variant-observed-composite-unknown",
                "slot": "main_hand",
                "simcOptions": {"ilevel": "289", "enchant_id": "999998/999999"},
            },
            {
                **snapshot["variants"][0],
                "variantId": "variant-untrusted-nonenchant-overlap",
                "variantKey": "variant-untrusted-nonenchant-overlap",
                "slot": "head",
                "sourceType": "dungeon",
                "simcOptions": {"ilevel": "289", "enchant_id": "7777"},
            },
            {
                **snapshot["variants"][0],
                "variantId": "variant-built-in-embellishment",
                "variantKey": "variant-built-in-embellishment",
                "slot": "back",
                "simcOptions": {"ilevel": "289", "embellishment": "built_in_effect"},
                "payload": {
                    "resolvedStats": {"intellect": 100},
                    "hasBuiltInEmbellishment": True,
                    "builtInEmbellishment": "built_in_effect",
                },
            },
            {
                **snapshot["variants"][0],
                "variantId": "variant-unknown-capable-embellishment",
                "variantKey": "variant-unknown-capable-embellishment",
                "slot": "back",
                "simcOptions": {"ilevel": "289", "embellishment": "unknown_effect"},
                "payload": {
                    "resolvedStats": {"intellect": 100},
                    "capabilityOverrides": {"canEmbellish": True},
                },
            },
            {
                **snapshot["variants"][0],
                "variantId": "variant-string-false-built-in",
                "variantKey": "variant-string-false-built-in",
                "slot": "back",
                "simcOptions": {"ilevel": "289", "embellishment": "not_built_in"},
                "payload": {
                    "resolvedStats": {"intellect": 100},
                    "hasBuiltInEmbellishment": "false",
                },
            },
        ]

        snapshot["options"] = [
            {
                "optionId": "option-back-4897",
                "optionKey": "enchant-back-4897",
                "optionType": "enchant",
                "name": "Canonical back enchant 4897",
                "applicableSlots": ["back"],
                "simcOptions": {"enchant_id": "4897"},
                "status": "verified",
                "isVisible": True,
                "payload": {},
                "updatedAt": "2026-07-11T05:00:00+00:00",
            },
            {
                "optionId": "option-hidden-main-hand-composite",
                "optionKey": "enchant-main-hand-composite",
                "optionType": "enchant",
                "name": "Hidden composite",
                "applicableSlots": ["main_hand"],
                "simcOptions": {"enchant_id": "8039/8052"},
                "status": "verified",
                "isVisible": False,
                "payload": {},
                "updatedAt": "2026-07-11T05:00:00+00:00",
            },
            {
                "optionId": "option-overlapping-nonenchant-7777",
                "optionKey": "enchant-overlapping-nonenchant-7777",
                "optionType": "enchant",
                "name": "Overlapping non-enchant option",
                "applicableSlots": ["*"],
                "simcOptions": {"enchant_id": "7777"},
                "status": "verified",
                "isVisible": True,
                "payload": {},
                "updatedAt": "2026-07-11T05:00:00+00:00",
            },
            {
                "optionId": "option-arcanoweave-lining",
                "optionKey": "embellishment-arcanoweave-lining",
                "optionType": "embellishment",
                "name": "Arcanoweave Lining",
                "applicableSlots": ["back", "wrist"],
                "simcOptions": {"embellishment": "arcanoweave_lining"},
                "status": "verified",
                "isVisible": True,
                "payload": {},
                "updatedAt": "2026-07-11T05:00:00+00:00",
            },
            {
                "optionId": "option-built-in-overlap",
                "optionKey": "embellishment-built-in-overlap",
                "optionType": "embellishment",
                "name": "Catalog overlap with built-in effect",
                "applicableSlots": ["back"],
                "simcOptions": {"embellishment": "built_in_effect"},
                "status": "verified",
                "isVisible": True,
                "payload": {},
                "updatedAt": "2026-07-11T05:00:00+00:00",
            },
        ]

        dependencies = {**self.dependencies(), "capabilityRevision": CAPABILITY_REVISION}
        managed = prepare_staging_gear_release(
            FakeReleaseStore(snapshot),
            season_revision="midnight-season-1",
            dependency_revisions=dependencies,
            socket_bonus_minimums={"9300": 1},
        )["snapshot"]
        variants = {row["variantKey"]: row for row in managed["variants"]}
        self.assertEqual(
            variants["variant-back"]["payload"]["enhancementManagement"],
            {
                "schemaRevision": "gear-enhancement-management-v1",
                "authorityRevision": CAPABILITY_REVISION,
                "fields": {
                    "enchant_id": "editor_managed",
                    "embellishment": "editor_managed",
                },
            },
        )
        self.assertEqual(
            variants["variant-item-slot-fallback"]["payload"]["enhancementManagement"],
            {
                "schemaRevision": "gear-enhancement-management-v1",
                "authorityRevision": CAPABILITY_REVISION,
                "fields": {"enchant_id": "editor_managed"},
            },
        )
        self.assertEqual(
            variants["variant-slot-mismatch"]["payload"]["enhancementManagement"]["fields"],
            {"enchant_id": "unresolved_drop"},
        )
        self.assertEqual(
            variants["variant-source-only-enchant"]["payload"]["enhancementManagement"]["fields"],
            {"enchant_id": "source_only"},
        )
        self.assertEqual(
            variants["variant-observed-editable-unmatched"]["payload"]["enhancementManagement"]["fields"],
            {"enchant_id": "unresolved_drop"},
        )
        self.assertEqual(
            variants["variant-observed-nonenchant-overlap"]["payload"]["enhancementManagement"]["fields"],
            {"enchant_id": "source_only"},
        )
        self.assertEqual(
            variants["variant-observed-nonenchant-unknown"]["payload"]["enhancementManagement"]["fields"],
            {"enchant_id": "unresolved_drop"},
        )
        self.assertEqual(
            variants["variant-observed-composite-unknown"]["payload"]["enhancementManagement"]["fields"],
            {"enchant_id": "unresolved_drop"},
        )
        self.assertEqual(
            variants["variant-untrusted-nonenchant-overlap"]["payload"]["enhancementManagement"]["fields"],
            {"enchant_id": "unresolved_drop"},
        )
        self.assertEqual(
            variants["variant-built-in-embellishment"]["payload"]["enhancementManagement"]["fields"],
            {"embellishment": "source_only"},
        )
        self.assertEqual(
            variants["variant-unknown-capable-embellishment"]["payload"]["enhancementManagement"]["fields"],
            {"embellishment": "unresolved_drop"},
        )
        self.assertEqual(
            variants["variant-string-false-built-in"]["payload"]["enhancementManagement"]["fields"],
            {"embellishment": "unresolved_drop"},
        )

        forged_v1 = copy.deepcopy(snapshot)
        forged_v1["variants"][0]["payload"]["enhancementManagement"] = {
            "schemaRevision": "gear-enhancement-management-v1",
            "authorityRevision": CAPABILITY_REVISION,
            "fields": {"enchant_id": "editor_managed"},
        }
        legacy_dependencies = {
            **self.dependencies(),
            "capabilityRevision": LEGACY_CAPABILITY_REVISION,
        }
        legacy = prepare_staging_gear_release(
            FakeReleaseStore(forged_v1),
            season_revision="midnight-season-1",
            dependency_revisions=legacy_dependencies,
            socket_bonus_minimums={"9300": 1},
        )["snapshot"]
        self.assertTrue(all(
            "enhancementManagement" not in row["payload"]
            for row in legacy["variants"]
        ))

    def test_v2_built_in_embellishment_merges_item_and_variant_immutable_evidence(self):
        from server.gear_release_store import GearReleaseIntegrityError
        from server.gear_release_tool import _materialize_enhancement_management
        from server.gear_socket_authority import CAPABILITY_REVISION

        def item(item_id, payload):
            return {
                "itemId": item_id,
                "name": item_id,
                "slot": "back",
                "sourceStatus": "verified",
                "payload": payload,
            }

        def variant(item_id, variant_key, payload=None):
            return {
                "variantId": f"{variant_key}-id",
                "itemId": item_id,
                "variantKey": variant_key,
                "slot": "back",
                "sourceType": "observed_profile",
                "itemLevel": 289,
                "simcOptions": {
                    "ilevel": "289",
                    "embellishment": "built_in_effect",
                },
                "status": "verified",
                "payload": payload or {},
            }

        snapshot = {
            "items": [
                item("item-exact", {
                    "hasBuiltInEmbellishment": True,
                    "builtInEmbellishment": "built_in_effect",
                }),
                item("item-source", {"embellishmentSource": "built_in"}),
                item("item-flag-only", {"hasBuiltInEmbellishment": True}),
                item("item-string-false", {"hasBuiltInEmbellishment": "false"}),
                item("item-mismatch", {
                    "hasBuiltInEmbellishment": True,
                    "builtInEmbellishment": "different_effect",
                }),
                item("item-conflict", {
                    "hasBuiltInEmbellishment": True,
                    "builtInEmbellishment": "built_in_effect",
                }),
                item("item-source-mismatch", {
                    "builtInEmbellishment": "different_effect",
                    "embellishmentSource": "built_in",
                }),
            ],
            "variants": [
                variant("item-exact", "variant-item-exact"),
                variant("item-source", "variant-item-source"),
                variant("item-flag-only", "variant-item-flag-only"),
                variant("item-string-false", "variant-string-false"),
                variant("item-mismatch", "variant-mismatch"),
                variant("item-conflict", "variant-conflict", {
                    "hasBuiltInEmbellishment": True,
                    "builtInEmbellishment": "different_effect",
                }),
                variant("item-source-mismatch", "variant-source-mismatch"),
            ],
            "options": [{
                "optionId": "option-overlap",
                "optionKey": "embellishment-overlap",
                "optionType": "embellishment",
                "name": "Overlapping catalog option",
                "applicableSlots": ["back"],
                "simcOptions": {"embellishment": "built_in_effect"},
                "status": "verified",
                "isVisible": True,
                "payload": {},
            }],
        }

        safe_variant_keys = {
            "variant-item-exact",
            "variant-item-source",
            "variant-item-flag-only",
            "variant-string-false",
        }
        safe_snapshot = copy.deepcopy(snapshot)
        safe_snapshot["variants"] = [
            row
            for row in safe_snapshot["variants"]
            if row["variantKey"] in safe_variant_keys
        ]
        safe_item_ids = {row["itemId"] for row in safe_snapshot["variants"]}
        safe_snapshot["items"] = [
            row
            for row in safe_snapshot["items"]
            if row["itemId"] in safe_item_ids
        ]
        materialized = _materialize_enhancement_management(
            safe_snapshot,
            CAPABILITY_REVISION,
        )
        classifications = {
            row["variantKey"]: row["payload"]["enhancementManagement"]["fields"][
                "embellishment"
            ]
            for row in materialized["variants"]
        }

        self.assertEqual(classifications["variant-item-exact"], "source_only")
        self.assertEqual(classifications["variant-item-source"], "source_only")
        self.assertEqual(classifications["variant-item-flag-only"], "source_only")
        self.assertEqual(classifications["variant-string-false"], "editor_managed")

        for variant_key in (
            "variant-mismatch",
            "variant-conflict",
            "variant-source-mismatch",
        ):
            with self.subTest(conflict=variant_key):
                conflict_snapshot = copy.deepcopy(snapshot)
                conflict_snapshot["variants"] = [
                    row
                    for row in conflict_snapshot["variants"]
                    if row["variantKey"] == variant_key
                ]
                conflict_item_id = conflict_snapshot["variants"][0]["itemId"]
                conflict_snapshot["items"] = [
                    row
                    for row in conflict_snapshot["items"]
                    if row["itemId"] == conflict_item_id
                ]
                with self.assertRaisesRegex(
                    GearReleaseIntegrityError,
                    "built-in embellishment evidence conflicts",
                ):
                    _materialize_enhancement_management(
                        conflict_snapshot,
                        CAPABILITY_REVISION,
                    )

    def test_materialized_socket_facts_round_trip_through_release_row_payloads(self):
        from server.gear_release_store import GearReleaseStore, canonical_row_hash
        from server.gear_release_tool import prepare_staging_gear_release
        from server.gear_socket_authority import CAPABILITY_REVISION, SOCKET_FACT_SCHEMA_REVISION

        snapshot = self.snapshot()
        snapshot["items"][0]["slot"] = "finger1"
        snapshot["items"][0]["itemLevel"] = None
        snapshot["items"][0]["payload"]["preview_item"] = {"sockets": []}
        snapshot["items"][0]["payload"]["baseCapabilities"] = {
            "canEnchant": True,
            "canEmbellish": True,
        }
        snapshot["variants"][0]["slot"] = "finger1"
        snapshot["variants"][0]["label"] = ""
        snapshot["variants"][0]["difficultyKey"] = ""
        snapshot["variants"][0]["simcOptions"]["bonus_id"] = "9300"
        snapshot["variants"][0]["payload"]["capabilityOverrides"] = {
            "canEnchant": False,
            "customAuthority": "preserved",
        }
        prepared = prepare_staging_gear_release(
            FakeReleaseStore(snapshot),
            season_revision="midnight-season-1",
            dependency_revisions=self.dependencies(),
            socket_bonus_minimums={"9300": 2},
        )

        class CapturingCursor:
            def __init__(self):
                self.batches = {}

            def executemany(self, statement, rows):
                if "websim_gear_release_items" in statement:
                    self.batches["items"] = list(rows)
                elif "websim_gear_release_variants" in statement:
                    self.batches["variants"] = list(rows)

        cursor = CapturingCursor()
        GearReleaseStore._insert_gear_rows(
            cursor,
            "gear-release:sha256:round-trip",
            prepared["snapshot"],
        )
        item_params = cursor.batches["items"][0]
        variant_params = cursor.batches["variants"][0]
        item_round_trip = {
            "itemId": str(item_params[1] or "").strip(),
            "name": str(item_params[2] or "").strip(),
            "slot": str(item_params[3] or "").strip(),
            "itemLevel": None if item_params[4] is None else int(item_params[4] or 0),
            "sourceStatus": str(item_params[5] or "").strip(),
            "payload": json.loads(item_params[6]),
            "updatedAt": str(item_params[7] or "").strip(),
        }
        variant_round_trip = {
            "variantId": str(variant_params[1] or "").strip(),
            "itemId": str(variant_params[2] or "").strip(),
            "variantKey": str(variant_params[3] or "").strip(),
            "slot": str(variant_params[4] or "").strip(),
            "label": str(variant_params[5] or "").strip(),
            "sourceType": str(variant_params[6] or "").strip(),
            "difficultyKey": str(variant_params[7] or "").strip(),
            "itemLevel": int(variant_params[8] or 0),
            "simcOptions": json.loads(variant_params[9]),
            "status": str(variant_params[10] or "").strip(),
            "blockers": json.loads(variant_params[11]),
            "payload": json.loads(variant_params[12]),
            "updatedAt": str(variant_params[13] or "").strip(),
        }

        self.assertEqual(canonical_row_hash(item_round_trip), item_params[8])
        self.assertEqual(canonical_row_hash(variant_round_trip), variant_params[14])
        self.assertEqual(item_round_trip, prepared["snapshot"]["items"][0])
        self.assertEqual(variant_round_trip, prepared["snapshot"]["variants"][0])
        item_payload = item_round_trip["payload"]
        variant_payload = variant_round_trip["payload"]
        self.assertEqual(item_payload["baseCapabilities"]["socketCount"], 1)
        self.assertEqual(variant_payload["capabilityOverrides"]["socketCount"], 2)
        self.assertTrue(item_payload["baseCapabilities"]["canEnchant"])
        self.assertTrue(item_payload["baseCapabilities"]["canEmbellish"])
        self.assertFalse(variant_payload["capabilityOverrides"]["canEnchant"])
        self.assertEqual(
            variant_payload["capabilityOverrides"]["customAuthority"],
            "preserved",
        )
        self.assertEqual(item_payload["socketEvidence"]["schemaRevision"], SOCKET_FACT_SCHEMA_REVISION)
        self.assertEqual(variant_payload["socketEvidence"]["schemaRevision"], SOCKET_FACT_SCHEMA_REVISION)
        self.assertEqual(item_payload["socketEvidence"]["authorityRevision"], CAPABILITY_REVISION)
        self.assertEqual(variant_payload["socketEvidence"]["authorityRevision"], CAPABILITY_REVISION)
        self.assertIn("preview_item", item_payload)
        self.assertIn("resolvedStats", variant_payload)

    def test_identical_socket_evidence_reuses_content_hash(self):
        from server.gear_release_tool import prepare_staging_gear_release

        snapshot = self.snapshot()
        snapshot["variants"][0]["simcOptions"]["bonus_id"] = "9300"
        results = []
        for socket_bonus_minimums in (
            {"9300": 2, "9400": 1},
            {"9400": 1, "9300": 2},
        ):
            try:
                results.append(
                    prepare_staging_gear_release(
                        FakeReleaseStore(snapshot),
                        season_revision="midnight-season-1",
                        dependency_revisions=self.dependencies(),
                        socket_bonus_minimums=socket_bonus_minimums,
                    )
                )
            except TypeError as exc:
                self.fail(f"prepare_staging_gear_release must accept socket evidence: {exc}")

        first, second = results
        self.assertEqual(first["release"]["contentHash"], second["release"]["contentHash"])
        self.assertEqual(first["release"]["releaseId"], second["release"]["releaseId"])
        self.assertEqual(first["release"]["source"], second["release"]["source"])

    def test_simc_probe_parses_only_socket_effects(self):
        from server import gear_release_tool

        load_probe = getattr(gear_release_tool, "load_simc_socket_bonus_minimums", None)
        self.assertTrue(callable(load_probe), "candidate release tooling must expose a bounded SimC socket probe")
        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="\n".join(
                    (
                        "bonus_id={ 523 }, socket={ 1 }",
                        "bonus_id={ 8781 }, socket={ 2 }",
                        "bonus_id=9300 effect=socket=2",
                        "bonus_id=9400 effect=item_level minimum_total=99",
                        "bonus_id=9500 effect=no socket minimum_total=5",
                    )
                ),
                stderr="",
            )

        parsed = load_probe("/fake/simc", runner=runner)

        self.assertEqual(parsed, {"523": 1, "8781": 2, "9300": 2})
        self.assertEqual(calls[0][0], ["/fake/simc", "show_bonus_ids=1"])
        self.assertTrue(calls[0][1]["capture_output"])
        self.assertTrue(calls[0][1]["text"])
        self.assertGreater(calls[0][1]["timeout"], 0)
        self.assertLessEqual(calls[0][1]["timeout"], 60)

        def raising(error):
            def fail(*_args, **_kwargs):
                raise error

            return fail

        secret_binary = "/secret/runtime/simc"
        failure_message = "SimC socket probe failed"
        failures = (
            ("blank binary", "", lambda *_args, **_kwargs: self.fail("blank binary must fail before runner")),
            (
                "timeout",
                secret_binary,
                raising(subprocess.TimeoutExpired([secret_binary], 30, output="secret stdout", stderr="secret stderr")),
            ),
            ("os error", secret_binary, raising(OSError("secret filesystem detail"))),
            ("generic error", secret_binary, raising(RuntimeError("secret runner detail"))),
            (
                "nonzero",
                secret_binary,
                lambda command, **_kwargs: subprocess.CompletedProcess(
                    command, 7, stdout="secret stdout", stderr="secret stderr"
                ),
            ),
            *(
                (
                    f"invalid return code {returncode!r}",
                    secret_binary,
                    lambda command, returncode=returncode, **_kwargs: subprocess.CompletedProcess(
                        command,
                        returncode,
                        stdout="bonus_id=9300 effect=socket=2",
                        stderr="secret stderr",
                    ),
                )
                for returncode in (None, True, False)
            ),
            (
                "oversize",
                secret_binary,
                lambda command, **_kwargs: subprocess.CompletedProcess(
                    command, 0, stdout="x" * (4 * 1024 * 1024 + 1), stderr="secret stderr"
                ),
            ),
            (
                "unparseable",
                secret_binary,
                lambda command, **_kwargs: subprocess.CompletedProcess(
                    command, 0, stdout="secret unparseable output", stderr="secret stderr"
                ),
            ),
        )
        for label, binary, failing_runner in failures:
            with self.subTest(label=label):
                with self.assertRaises(RuntimeError) as caught:
                    load_probe(binary, runner=failing_runner)
                self.assertEqual(str(caught.exception), failure_message)
                self.assertNotIn("secret", str(caught.exception).lower())

    def test_build_legacy_gear_release_blocks_empty_or_orphan_snapshot(self):
        from server.gear_release_store import GearReleaseIntegrityError
        from server.gear_release_tool import build_legacy_gear_release

        for snapshot in (
            {"items": [], "sources": [], "variants": [], "options": []},
            {"items": [], "sources": [], "variants": [{"variantId": "v", "itemId": "missing", "variantKey": "v"}], "options": []},
        ):
            with self.subTest(snapshot=snapshot):
                with self.assertRaises(GearReleaseIntegrityError):
                    build_legacy_gear_release(
                        FakeReleaseStore(snapshot),
                        season_revision="season-17",
                        dependency_revisions=self.dependencies(),
                        socket_bonus_minimums={"9300": 1},
                    )

    def test_build_legacy_gear_release_blocks_blank_required_identifiers(self):
        from server.gear_release_store import GearReleaseIntegrityError
        from server.gear_release_tool import build_legacy_gear_release

        mutations = (
            ("items", "itemId"),
            ("sources", "sourceId"),
            ("sources", "sourceKey"),
            ("variants", "variantId"),
            ("variants", "variantKey"),
        )
        for collection, field in mutations:
            with self.subTest(collection=collection, field=field):
                snapshot = self.snapshot()
                snapshot[collection][0][field] = ""
                with self.assertRaises(GearReleaseIntegrityError):
                    build_legacy_gear_release(
                        FakeReleaseStore(snapshot),
                        season_revision="season-17",
                        dependency_revisions=self.dependencies(),
                        socket_bonus_minimums={"9300": 1},
                    )

    def test_build_legacy_community_release_revalidates_and_seals_winner(self):
        from server.gear_release_store import gear_snapshot_summary
        from server.gear_release_tool import build_legacy_community_release

        snapshot = self.snapshot()
        gear = gear_release.build_release(
            release_kind="gear",
            season_revision="season-17",
            schema_revision="gear-release-v1",
            content=gear_snapshot_summary(snapshot),
            dependency_revisions=self.dependencies(),
            release_status="validated",
            source={"sourceRevision": "legacy-import-r0"},
        )
        store = FakeReleaseStore(snapshot, [self.template()])
        calls = []

        result = build_legacy_community_release(
            store,
            gear_release_descriptor=gear,
            gear_snapshot=snapshot,
            dependency_revisions=self.dependencies(),
            expected_specs=[("mage", "arcane")],
            now="2026-07-11T06:00:00+00:00",
            resolver_for_spec=lambda class_key, spec_key, intent: calls.append((class_key, spec_key, intent)) or self.verified_result(gear["releaseId"]),
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(store.requested_specs, [("mage", "arcane")])
        self.assertEqual(result["election"]["status"], "validated")
        self.assertEqual(result["election"]["winnerSpecCount"], 1)
        self.assertEqual(result["release"]["releaseKind"], "community")
        self.assertEqual(result["release"]["validatedAgainstReleaseId"], gear["releaseId"])
        self.assertEqual(result["rows"][0]["role"], "winner")
        self.assertEqual(result["rows"][0]["semanticGearSignature"].startswith("sha256:"), True)
        self.assertEqual(len(store.community_seals), 1)
        self.assertNotIn("pointer", result)

    def test_build_legacy_community_release_keeps_rejected_internal_and_degraded(self):
        from server.gear_release_store import gear_snapshot_summary
        from server.gear_release_tool import build_legacy_community_release

        snapshot = self.snapshot()
        gear = gear_release.build_release(
            release_kind="gear",
            season_revision="season-17",
            schema_revision="gear-release-v1",
            content=gear_snapshot_summary(snapshot),
            dependency_revisions=self.dependencies(),
            release_status="validated",
            source={"sourceRevision": "legacy-import-r0"},
        )
        invalid = self.template(source_key="season_recommendation")
        store = FakeReleaseStore(snapshot, [invalid])
        result = build_legacy_community_release(
            store,
            gear_release_descriptor=gear,
            gear_snapshot=snapshot,
            dependency_revisions=self.dependencies(),
            expected_specs=[("mage", "arcane")],
            now="2026-07-11T06:00:00+00:00",
            resolver_for_spec=lambda *_args: self.fail("invalid source must not reach Resolver"),
        )

        self.assertEqual(result["release"]["releaseStatus"], "degraded")
        self.assertEqual(result["election"]["winnerSpecCount"], 0)
        self.assertEqual(result["rows"][0]["role"], "rejected")
        self.assertEqual(store.community_seals[0][2]["gate_result"]["winnerSpecCount"], 0)

    def test_build_legacy_community_release_rejects_duplicate_template_ids(self):
        from server.gear_release_store import GearReleaseIntegrityError, gear_snapshot_summary
        from server.gear_release_tool import build_legacy_community_release

        snapshot = self.snapshot()
        gear = gear_release.build_release(
            release_kind="gear",
            season_revision="season-17",
            schema_revision="gear-release-v1",
            content=gear_snapshot_summary(snapshot),
            dependency_revisions=self.dependencies(),
            release_status="validated",
            source={"sourceRevision": "legacy-import-r0"},
        )
        templates = [self.template(), self.template()]
        with self.assertRaises(GearReleaseIntegrityError):
            build_legacy_community_release(
                FakeReleaseStore(snapshot, templates),
                gear_release_descriptor=gear,
                gear_snapshot=snapshot,
                dependency_revisions=self.dependencies(),
                expected_specs=[("mage", "arcane")],
                now="2026-07-11T06:00:00+00:00",
                resolver_for_spec=lambda *_args: self.fail("duplicates must fail before Resolver"),
            )

    def test_shadow_command_is_read_only_and_requires_explicit_release_pair(self):
        from server import gear_release_tool

        class ShadowStore:
            def gear_authority_cache_metrics(self):
                return {"entryCount": 32, "byteSize": 1024, "maxEntries": 32, "maxBytes": 4096}

            def shadow_read_statement_metrics(self):
                return {"total": 203, "transactionControl": 81, "readQueries": 122}

        output = io.StringIO()
        with patch.object(
            gear_release_tool,
            "_shadow_store_from_environment",
            return_value=ShadowStore(),
        ), patch.object(
            gear_release_tool.gear_release_shadow,
            "run_release_shadow",
            return_value={"status": "pass", "publicReadCount": 40, "blockers": []},
        ) as shadow, redirect_stdout(output):
            status = gear_release_tool.main([
                "shadow",
                "--gear-release-id", "gear-release:a",
                "--community-release-id", "community-release:a",
                "--simc-runtime-revision", "simc-r1",
            ])

        self.assertEqual(status, 0)
        rendered = json.loads(output.getvalue())
        self.assertEqual(rendered["status"], "pass")
        self.assertEqual(rendered["authorityCache"]["entryCount"], 32)
        self.assertEqual(rendered["databaseStatements"]["readQueries"], 122)
        shadow.assert_called_once()
        self.assertEqual(shadow.call_args.kwargs["gear_release_id"], "gear-release:a")
        self.assertEqual(shadow.call_args.kwargs["community_release_id"], "community-release:a")
        self.assertIs(shadow.call_args.kwargs.get("expect_formal_active"), False)

        with self.assertRaises(SystemExit):
            gear_release_tool.main(["shadow", "--simc-runtime-revision", "simc-r1"])

    def test_shadow_command_can_explicitly_expect_formal_active(self):
        from server import gear_release_tool

        output = io.StringIO()
        with patch.object(
            gear_release_tool,
            "_shadow_store_from_environment",
            return_value=object(),
        ), patch.object(
            gear_release_tool.gear_release_shadow,
            "run_release_shadow",
            return_value={"status": "pass", "publicReadCount": 40, "blockers": []},
        ) as shadow, redirect_stdout(output):
            try:
                status = gear_release_tool.main([
                    "shadow",
                    "--gear-release-id", "gear-release:a",
                    "--community-release-id", "community-release:a",
                    "--simc-runtime-revision", "simc-r1",
                    "--expect-formal-active",
                ])
            except SystemExit as error:
                self.fail(f"shadow CLI rejected --expect-formal-active: {error}")

        self.assertEqual(status, 0)
        self.assertIs(shadow.call_args.kwargs.get("expect_formal_active"), True)

    def test_promote_command_atomically_seals_manifest_and_cas_pointer(self):
        from server import gear_release_tool
        from server.gear_release_store import community_rows_summary, gear_snapshot_summary

        snapshot = self.snapshot()
        gear = gear_release.build_release(
            release_kind="gear",
            season_revision="season-17",
            schema_revision="gear-release-v1",
            content=gear_snapshot_summary(snapshot),
            dependency_revisions=self.dependencies(),
            release_status="validated",
            source={"sourceRevision": "legacy-import-r0"},
        )
        community_rows = [{
            "templateId": "template-a", "classKey": "mage", "specKey": "arcane",
            "role": "winner", "electionRank": 1, "sourceKey": "observed",
        }]
        community = gear_release.build_release(
            release_kind="community",
            season_revision="season-17",
            schema_revision="community-release-v1",
            content=community_rows_summary(community_rows),
            dependency_revisions=self.dependencies(),
            release_status="validated",
            source={"sourceRevision": "legacy-import-r0"},
            validated_against_release_id=gear["releaseId"],
        )

        class CutoverStore:
            def __init__(self):
                self.activation = None

            def get_release(self, release_id):
                return {gear["releaseId"]: gear, community["releaseId"]: community}.get(release_id, {})

            def seal_manifest_and_compare_and_swap_pointer(self, manifest, command, *, updated_by):
                self.activation = (manifest, command, updated_by)
                return {"manifest": {"status": "inserted"}, "pointer": {"generation": 1}}

        store = CutoverStore()
        output = io.StringIO()
        with patch.object(gear_release_tool, "_store_from_environment", return_value=store), patch.object(
            gear_release_tool,
            "runtime_dependency_revisions",
            return_value=self.dependencies(),
        ), redirect_stdout(output):
            status = gear_release_tool.main([
                "promote",
                "--season-revision", "season-17",
                "--simc-runtime-revision", "simc-r1",
                "--gear-release-id", gear["releaseId"],
                "--community-release-id", community["releaseId"],
                "--talent-catalog-revision", "talent-r1",
                "--expected-generation", "0",
                "--updated-by", "candidate-test",
            ])

        self.assertEqual(status, 0)
        manifest, command, updated_by = store.activation
        self.assertTrue(manifest["formalActiveManifest"])
        self.assertEqual(command["manifestRevision"], manifest["manifestRevision"])
        self.assertEqual(command["expectedGeneration"], 0)
        self.assertEqual(updated_by, "candidate-test")
        self.assertEqual(json.loads(output.getvalue())["pointer"]["generation"], 1)

    def test_rollback_command_advances_to_explicit_transitional_pointer(self):
        from server import gear_release_tool

        class CutoverStore:
            def __init__(self):
                self.mutation = None

            def compare_and_swap_pointer(self, command, *, updated_by):
                self.mutation = (command, updated_by)
                return {"status": "updated", "pointerMode": "transitional", "generation": 2}

        store = CutoverStore()
        output = io.StringIO()
        with patch.object(gear_release_tool, "_store_from_environment", return_value=store), redirect_stdout(output):
            status = gear_release_tool.main([
                "rollback",
                "--target-mode", "transitional",
                "--expected-generation", "1",
                "--updated-by", "candidate-test",
            ])

        self.assertEqual(status, 0)
        command, updated_by = store.mutation
        self.assertEqual(command["action"], "rollback")
        self.assertEqual(command["targetMode"], "transitional")
        self.assertEqual(command["manifestRevision"], "")
        self.assertEqual(command["expectedGeneration"], 1)
        self.assertEqual(updated_by, "candidate-test")


if __name__ == "__main__":
    unittest.main()
