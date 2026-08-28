import copy
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import patch

from server import gear_release
from tests.gear_resolver_test import build_midnight_mage_resolver_fixture


class FakeReleaseStore:
    def __init__(self, gear_snapshot, templates=None, talent_candidates=None):
        self.gear_snapshot = gear_snapshot
        self.templates = templates or []
        self.talent_candidates = talent_candidates or []
        self.community_hero_projection_enabled = talent_candidates is not None
        self.gear_seals = []
        self.community_seals = []
        self.requested_specs = []

    def snapshot_staging_gear(self):
        return copy.deepcopy(self.gear_snapshot)

    def snapshot_staging_community_templates(self, expected_specs):
        self.requested_specs = list(expected_specs)
        return copy.deepcopy(self.templates)

    def snapshot_staging_community_builder_templates(self, expected_specs):
        self.requested_specs = list(expected_specs)
        return copy.deepcopy(
            getattr(self, "builder_templates", self.templates)
        )

    def snapshot_staging_community_templates_by_ids(self, template_ids):
        self.requested_template_ids = sorted(template_ids)
        requested = set(template_ids)
        return copy.deepcopy([
            template
            for template in self.templates
            if template.get("templateId") in requested
        ])

    def snapshot_staging_community_talent_candidates(self, expected_specs):
        self.requested_specs = list(expected_specs)
        return copy.deepcopy(self.talent_candidates)

    def seal_gear_release(self, release, snapshot, **kwargs):
        self.gear_seals.append((copy.deepcopy(release), copy.deepcopy(snapshot), copy.deepcopy(kwargs)))
        return {"status": "inserted", "releaseId": release["releaseId"]}

    def seal_community_release(self, release, rows, **kwargs):
        self.community_seals.append((copy.deepcopy(release), copy.deepcopy(rows), copy.deepcopy(kwargs)))
        return {"status": "inserted", "releaseId": release["releaseId"]}


def verified_official_gem_item(gem_id, name=None):
    display_name = name or f"Verified gem {gem_id}"
    preview_item = {
        "gem_properties": {"effect": f"Verified effect {gem_id}"},
    }
    if str(gem_id) in {"240967", "240969", "240971", "240983", "241144"}:
        preview_item["limit_category"] = "装备唯一：萨拉斯钻石 （1）"
    return {
        "itemId": str(gem_id),
        "name": display_name,
        "slot": "",
        "sourceStatus": "unknown",
        "payload": {
            "_links": {
                "self": {
                    "href": f"https://us.api.blizzard.com/data/wow/item/{gem_id}",
                }
            },
            "_metadata": {
                "source": "Battle.net Game Data API",
                "iconUrl": f"https://render.worldofwarcraft.com/{gem_id}.jpg",
                "gameAsset": {
                    "source": "blizzard",
                    "status": "verified",
                },
            },
            "item_class": {"id": 3, "name": "Gem"},
            "preview_item": preview_item,
        },
        "updatedAt": "2026-07-14T05:00:00+00:00",
    }


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
                "_metadata": {
                    "iconUrl": f"https://render.worldofwarcraft.com/icons/{item_id}.jpg",
                    "gameAsset": {"source": "blizzard", "status": "verified"},
                },
                **{
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
            encoded_options = {
                key: value
                for key, value in (variant.get("simcOptions") or {}).items()
                if str(key or "").strip() and str(value or "").strip()
            }
            encoded_options["ilevel"] = str(item_level)
            payload.update({
                "statSource": "simulationcraft",
                "statDisplayStatus": "verified_variant",
                "itemStats": [{"type": "intellect", "value": 100}],
                "simcItemId": variant["itemId"],
                "simcItemLevel": item_level,
                "simcEncodedItem": (
                    f"observed_item,id={variant['itemId']},"
                    + ",".join(
                        f"{key}={encoded_options[key]}"
                        for key in sorted(encoded_options)
                    )
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
    items.extend(
        verified_official_gem_item(gem_id)
        for gem_id in sorted({
            str((option.get("simcOptions") or {}).get("gem_id") or "").strip()
            for option in authority["optionsById"].values()
            if option.get("optionType") == "gem"
            and str((option.get("simcOptions") or {}).get("gem_id") or "").strip()
        })
    )
    gear_items = []
    source_enhancements = reference["sourceEnhancementBySlot"]
    for slot in reference["requiredSlots"]:
        selection = intent["slots"][slot]
        raw_enhancement = source_enhancements.get(slot, {})
        raw = {
            "slot": slot,
            "itemId": selection["itemId"],
            "variantKey": selection["variantKey"],
            "itemLevel": int(
                authority["variantsByKey"][selection["variantKey"]]["itemLevel"]
            ),
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
    CURRENT_SEASON_REVISION = "season-17-f131dd36ddf1"

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
            "items": [{"itemId": "item-a", "name": "A", "slot": "head", "sourceStatus": "verified", "payload": {"_metadata": {"iconUrl": "https://render.worldofwarcraft.com/icons/item-a.jpg", "gameAsset": {"source": "blizzard", "status": "verified"}}}, "updatedAt": "2026-07-11T05:00:00+00:00"}],
            "sources": [{"sourceId": "source-a", "itemId": "item-a", "sourceType": "observed_profile", "sourceKey": "profile:a", "payload": {"status": "verified"}, "updatedAt": "2026-07-11T05:00:00+00:00"}],
            "variants": [{"variantId": "variant-a-id", "itemId": "item-a", "variantKey": "variant-a", "slot": "head", "sourceType": "observed_profile", "itemLevel": 289, "simcOptions": {"ilevel": "289"}, "status": "verified", "blockers": [], "payload": {"resolvedStats": {"intellect": 100}}, "updatedAt": "2026-07-11T05:00:00+00:00"}],
            "options": [],
        }

    def exact_progression_snapshot(self):
        snapshot = self.snapshot()
        snapshot["variants"][0]["simcOptions"] = {
            "ilevel": "289",
            "bonus_id": "13335",
        }
        return snapshot

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
                    "itemLevel": 289,
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

    def test_import_evidence_seals_observed_level_not_generic_item_level(self):
        from server.gear_release_tool import (
            COMMUNITY_TEMPLATE_IMPORT_EVIDENCE_REVISION,
            community_template_import_evidence_from_template,
        )

        template = self.template()
        template["gearItems"][0].pop("itemLevel")
        template["gearItems"][0]["ilevel"] = "292"
        snapshot = self.snapshot()
        snapshot["items"][0].update({
            "itemLevel": 197,
            "payload": {
                "_metadata": {
                    "iconUrl": "https://render.worldofwarcraft.com/icons/item-a.jpg",
                    "gameAsset": {"source": "blizzard", "status": "verified"},
                },
            },
        })
        snapshot["variants"][0]["itemLevel"] = 292
        snapshot["variants"][0]["simcOptions"]["ilevel"] = "292"

        evidence = community_template_import_evidence_from_template(
            template,
            gear_release_id="gear-release:sha256:target",
            gear_snapshot=snapshot,
        )

        self.assertEqual(
            evidence["schemaRevision"],
            COMMUNITY_TEMPLATE_IMPORT_EVIDENCE_REVISION,
        )
        self.assertTrue(evidence["sourceFingerprint"].startswith("sha256:"))
        self.assertEqual(evidence["slots"], {
            "head": {
                "itemId": "item-a",
                "variantKey": "variant-a",
                "observedItemLevel": 292,
                "iconUrl": "https://render.worldofwarcraft.com/icons/item-a.jpg",
            },
        })
        self.assertNotIn("197", str(evidence))

    def test_import_evidence_binds_verified_source_race_into_v3_fingerprint(self):
        from server.gear_release_tool import community_template_import_evidence_from_template

        template = self.template()
        template["attributeCharacterContext"] = {
            "schemaRevision": "gear-attribute-character-v1",
            "raceKey": "night_elf",
            "origin": "source_profile",
        }
        snapshot = self.snapshot()

        evidence = community_template_import_evidence_from_template(
            template,
            gear_release_id="gear-release:sha256:target",
            gear_snapshot=snapshot,
        )
        human_template = copy.deepcopy(template)
        human_template["attributeCharacterContext"]["raceKey"] = "human"
        human_evidence = community_template_import_evidence_from_template(
            human_template,
            gear_release_id="gear-release:sha256:target",
            gear_snapshot=snapshot,
        )

        self.assertEqual(evidence["schemaRevision"], "community-template-import-evidence-v3")
        self.assertEqual(evidence["sourceRaceKey"], "night_elf")
        self.assertEqual(evidence["sourceRaceOrigin"], "source_profile")
        self.assertNotEqual(evidence["sourceFingerprint"], human_evidence["sourceFingerprint"])

    def test_import_evidence_v3_seals_verified_source_stable_effects_into_fingerprint(self):
        from server.gear_release_tool import community_template_import_evidence_from_template

        template = self.template()
        template["attributeCharacterContext"] = {
            "schemaRevision": "gear-attribute-character-v1",
            "raceKey": "dwarf",
            "origin": "source_profile",
        }
        template["attributeStableEffectContext"] = {
            "schemaRevision": "gear-attribute-stable-effects-v1",
            "status": "verified",
            "origin": "source_profile",
            "effectIds": ["mage:inspired_intellect", "mage:tome_of_antonidas"],
            "loadoutSignature": "sha256:" + "b" * 64,
        }
        template["payload"] = {"rawImportCode": "CAE_SOURCE_LOADOUT_MUST_NOT_LEAK"}

        evidence = community_template_import_evidence_from_template(
            template,
            gear_release_id="gear-release:sha256:target",
            gear_snapshot=self.snapshot(),
        )
        changed = copy.deepcopy(template)
        changed["attributeStableEffectContext"]["effectIds"] = ["mage:inspired_intellect"]
        changed_evidence = community_template_import_evidence_from_template(
            changed,
            gear_release_id="gear-release:sha256:target",
            gear_snapshot=self.snapshot(),
        )

        self.assertEqual(evidence["schemaRevision"], "community-template-import-evidence-v3")
        self.assertEqual(evidence["sourceStableEffects"], template["attributeStableEffectContext"])
        self.assertNotEqual(evidence["sourceFingerprint"], changed_evidence["sourceFingerprint"])
        self.assertNotIn("CAE_SOURCE_LOADOUT_MUST_NOT_LEAK", json.dumps(evidence, sort_keys=True))

    def test_import_evidence_rejects_conflicting_observed_item_level_spellings(self):
        from server.gear_release_store import GearReleaseIntegrityError
        from server.gear_release_tool import community_template_import_evidence_from_template

        template = self.template()
        template["gearItems"][0]["itemLevel"] = 292
        template["gearItems"][0]["ilevel"] = "289"
        snapshot = self.snapshot()
        snapshot["variants"][0]["itemLevel"] = 292

        with self.assertRaises(GearReleaseIntegrityError):
            community_template_import_evidence_from_template(
                template,
                gear_release_id="gear-release:sha256:target",
                gear_snapshot=snapshot,
            )

    def test_observed_template_canonicalizes_legacy_variant_key_by_profile_identity(self):
        from server.gear_release_tool import (
            community_template_import_evidence_from_template,
            selection_intent_from_template,
        )

        profile_url = "https://raider.io/characters/kr/azshara/target-player"
        legacy_variant_key = (
            "observed-profile-target-observed_profile-head-292-"
            "bonus_id:40enchant_id:8017ilevel:292"
        )
        canonical_variant_key = (
            "observed-profile-target-observed_profile-head-292-"
            '{"bonus_id": "40", "enchant_id": "8017", "ilevel": "292"}'
        )
        template = self.template()
        template["gearItems"][0].pop("gem_id", None)
        template["gearItems"][0].update({
            "itemLevel": 292,
            "variantKey": legacy_variant_key,
            "bonus_id": "40",
            "enchant_id": "8017",
            "observedProfileRefs": [{"profileUrl": profile_url}],
        })
        snapshot = self.snapshot()
        snapshot["variants"][0].update({
            "itemLevel": 292,
            "variantKey": canonical_variant_key,
            "sourceType": "observed_profile",
            "simcOptions": {"ilevel": "292", "bonus_id": "40", "enchant_id": "8017"},
            "payload": {"profileUrl": profile_url},
        })
        other_profile_variant = copy.deepcopy(snapshot["variants"][0])
        other_profile_variant.update({
            "variantId": "other-profile-variant",
            "variantKey": canonical_variant_key.replace("target", "other"),
            "payload": {"profileUrl": "https://raider.io/characters/us/illidan/not-target"},
        })
        snapshot["variants"].append(other_profile_variant)

        intent = selection_intent_from_template(
            template,
            gear_release_id="gear-release:sha256:target",
            season_revision="season-17",
            level=90,
            gear_snapshot=snapshot,
            capability_revision="gear-capability-matrix-v2",
        )
        evidence = community_template_import_evidence_from_template(
            template,
            gear_release_id="gear-release:sha256:target",
            gear_snapshot=snapshot,
        )

        self.assertEqual(intent["slots"]["head"]["variantKey"], canonical_variant_key)
        self.assertEqual(evidence["slots"]["head"]["variantKey"], canonical_variant_key)
        self.assertEqual(evidence["slots"]["head"]["observedItemLevel"], 292)

        template_without_variant_key = copy.deepcopy(template)
        template_without_variant_key["gearItems"][0].pop("variantKey")
        missing_key_intent = selection_intent_from_template(
            template_without_variant_key,
            gear_release_id="gear-release:sha256:target",
            season_revision="season-17",
            level=90,
            gear_snapshot=snapshot,
            capability_revision="gear-capability-matrix-v2",
        )
        missing_key_evidence = community_template_import_evidence_from_template(
            template_without_variant_key,
            gear_release_id="gear-release:sha256:target",
            gear_snapshot=snapshot,
        )

        self.assertEqual(missing_key_intent["slots"]["head"]["variantKey"], canonical_variant_key)
        self.assertEqual(missing_key_evidence["slots"]["head"]["variantKey"], canonical_variant_key)

    def test_observed_template_can_use_same_instance_catalog_evidence_from_another_profile(self):
        from server.gear_release_tool import community_template_import_evidence_from_template

        template = self.template()
        template["gearItems"][0].pop("gem_id", None)
        template["gearItems"][0].pop("enchant_id", None)
        template["gearItems"][0].pop("variantKey")
        template["gearItems"][0].update({
            "itemLevel": 292,
            "bonus_id": "40",
            "observedProfileRefs": [{"profileUrl": "https://raider.io/characters/kr/azshara/target-player"}],
        })
        snapshot = self.snapshot()
        snapshot["variants"][0].update({
            "itemLevel": 292,
            "variantKey": 'observed-profile-other-observed_profile-head-292-{"bonus_id": "40", "ilevel": "292"}',
            "sourceType": "observed_profile",
            "simcOptions": {"ilevel": "292", "bonus_id": "40"},
            "payload": {"profileUrl": "https://raider.io/characters/us/illidan/not-target"},
        })

        evidence = community_template_import_evidence_from_template(
            template,
            gear_release_id="gear-release:sha256:target",
            gear_snapshot=snapshot,
        )

        self.assertEqual(
            evidence["slots"]["head"]["variantKey"],
            'observed-profile-other-observed_profile-head-292-{"bonus_id": "40", "ilevel": "292"}',
        )

    def test_observed_template_matches_item_level_alias_and_ignores_default_false_capability(self):
        from server.gear_release_store import CandidateGearAuthorityIndex, gear_snapshot_summary
        from server.gear_release_tool import (
            community_template_import_evidence_from_template,
            selection_intent_from_template,
        )

        template = self.template()
        item = template["gearItems"][0]
        item.pop("variantKey")
        item.pop("gem_id")
        item.pop("enchant_id")
        item.update({
            "itemLevel": 292,
            "bonus_id": "40",
            "observedProfileRefs": [{
                "profileUrl": "https://raider.io/characters/kr/azshara/target-player",
            }],
        })
        snapshot = self.snapshot()
        snapshot["variants"][0].update({
            "itemLevel": 292,
            "variantKey": "observed-target",
            "simcOptions": {"bonus_id": "40"},
            "sourceType": "observed_profile",
            "payload": {"resolvedStats": {"intellect": 100}},
        })
        duplicate = copy.deepcopy(snapshot["variants"][0])
        duplicate.update({
            "variantId": "observed-target-default-false",
            "variantKey": "observed-target-default-false",
            "payload": {
                "resolvedStats": {"intellect": 100},
                "capabilityOverrides": {"requiresCraftedOption": False},
            },
        })
        snapshot["variants"].append(duplicate)

        evidence = community_template_import_evidence_from_template(
            template,
            gear_release_id="gear-release:sha256:target",
            gear_snapshot=snapshot,
        )
        prepared_index = CandidateGearAuthorityIndex(
            snapshot,
            gear_release.build_release(
                release_kind="gear",
                season_revision="season-17",
                schema_revision="gear-release-v1",
                content=gear_snapshot_summary(snapshot),
                dependency_revisions=self.dependencies(),
                release_status="validated",
                source={"sourceRevision": "test"},
            ),
        )
        intent = selection_intent_from_template(
            template,
            gear_release_id=prepared_index.release["releaseId"],
            season_revision="season-17",
            level=90,
            capability_revision="gear-capability-matrix-v2",
            prepared_index=prepared_index,
        )

        self.assertEqual(evidence["slots"]["head"]["variantKey"], "observed-target")
        self.assertEqual(evidence["slots"]["head"]["observedItemLevel"], 292)
        self.assertEqual(intent["slots"]["head"]["variantKey"], "observed-target")

    def test_observed_template_canonicalizes_identical_target_profile_duplicates(self):
        from server.gear_release_tool import community_template_import_evidence_from_template

        template = self.template()
        template["gearItems"][0].pop("gem_id", None)
        template["gearItems"][0].pop("enchant_id", None)
        template["gearItems"][0].pop("variantKey")
        template["gearItems"][0].update({
            "itemLevel": 292,
            "bonus_id": "40",
            "observedProfileRefs": [{"profileUrl": "https://raider.io/characters/kr/azshara/target-player"}],
        })
        snapshot = self.snapshot()
        canonical_variant_key = 'observed-profile-target-a-observed_profile-head-292-{"bonus_id": "40", "ilevel": "292"}'
        snapshot["variants"][0].update({
            "itemLevel": 292,
            "variantKey": canonical_variant_key,
            "sourceType": "observed_profile",
            "simcOptions": {"ilevel": "292", "bonus_id": "40"},
            "payload": {"profileUrl": "https://raider.io/characters/kr/azshara/target-player"},
        })
        duplicate = copy.deepcopy(snapshot["variants"][0])
        duplicate.update({
            "variantId": "target-profile-duplicate-variant",
            "variantKey": 'observed-profile-target-b-observed_profile-head-292-{"bonus_id": "40", "ilevel": "292"}',
        })
        snapshot["variants"].append(duplicate)

        evidence = community_template_import_evidence_from_template(
            template,
            gear_release_id="gear-release:sha256:target",
            gear_snapshot=snapshot,
        )

        self.assertEqual(evidence["slots"]["head"]["variantKey"], canonical_variant_key)

    def test_observed_template_blocks_target_profile_duplicates_with_different_resolver_facts(self):
        from server.gear_release_store import GearReleaseIntegrityError
        from server.gear_release_tool import community_template_import_evidence_from_template

        template = self.template()
        template["gearItems"][0].pop("gem_id", None)
        template["gearItems"][0].pop("enchant_id", None)
        template["gearItems"][0].pop("variantKey")
        template["gearItems"][0].update({
            "itemLevel": 292,
            "bonus_id": "40",
            "observedProfileRefs": [{"profileUrl": "https://raider.io/characters/kr/azshara/target-player"}],
        })
        snapshot = self.snapshot()
        snapshot["variants"][0].update({
            "itemLevel": 292,
            "variantKey": 'observed-profile-target-a-observed_profile-head-292-{"bonus_id": "40", "ilevel": "292"}',
            "sourceType": "observed_profile",
            "simcOptions": {"ilevel": "292", "bonus_id": "40"},
            "payload": {"profileUrl": "https://raider.io/characters/kr/azshara/target-player"},
        })
        conflicting = copy.deepcopy(snapshot["variants"][0])
        conflicting.update({
            "variantId": "target-profile-conflicting-variant",
            "variantKey": 'observed-profile-target-b-observed_profile-head-292-{"bonus_id": "40", "ilevel": "292"}',
            "payload": {
                "profileUrl": "https://raider.io/characters/kr/azshara/target-player",
                "capabilityOverrides": {"socketCount": 1},
            },
        })
        snapshot["variants"].append(conflicting)

        with self.assertRaises(GearReleaseIntegrityError):
            community_template_import_evidence_from_template(
                template,
                gear_release_id="gear-release:sha256:target",
                gear_snapshot=snapshot,
            )

    def test_observed_template_blocks_cross_profile_catalog_rows_with_different_resolver_facts(self):
        from server.gear_release_store import GearReleaseIntegrityError
        from server.gear_release_tool import community_template_import_evidence_from_template

        template = self.template()
        template["gearItems"][0].pop("gem_id", None)
        template["gearItems"][0].pop("enchant_id", None)
        template["gearItems"][0].pop("variantKey")
        template["gearItems"][0].update({
            "itemLevel": 292,
            "bonus_id": "40",
            "observedProfileRefs": [{"profileUrl": "https://raider.io/characters/kr/azshara/target-player"}],
        })
        snapshot = self.snapshot()
        snapshot["variants"][0].update({
            "itemLevel": 292,
            "variantKey": 'observed-profile-other-a-observed_profile-head-292-{"bonus_id": "40", "ilevel": "292"}',
            "sourceType": "observed_profile",
            "simcOptions": {"ilevel": "292", "bonus_id": "40"},
            "payload": {"profileUrl": "https://raider.io/characters/us/illidan/not-target-a"},
        })
        conflicting = copy.deepcopy(snapshot["variants"][0])
        conflicting.update({
            "variantId": "other-profile-conflicting-variant",
            "variantKey": 'observed-profile-other-b-observed_profile-head-292-{"bonus_id": "40", "ilevel": "292"}',
            "payload": {
                "profileUrl": "https://raider.io/characters/us/illidan/not-target-b",
                "capabilityOverrides": {"socketCount": 1},
            },
        })
        snapshot["variants"].append(conflicting)

        with self.assertRaises(GearReleaseIntegrityError):
            community_template_import_evidence_from_template(
                template,
                gear_release_id="gear-release:sha256:target",
                gear_snapshot=snapshot,
            )

    def test_import_evidence_seals_target_verified_icon_when_catalog_metadata_is_missing(self):
        from server.gear_release_tool import community_template_import_evidence_from_template

        icon_url = "https://render.worldofwarcraft.com/icons/item-a-observed.jpg"
        template = self.template()
        template["gearItems"][0].update({
            "iconUrl": icon_url,
            "gameAsset": {
                "status": "verified",
                "entityType": "item",
                "entityId": "item-a",
                "iconUrl": icon_url,
            },
        })
        snapshot = self.snapshot()
        snapshot["items"][0]["payload"] = {}

        evidence = community_template_import_evidence_from_template(
            template,
            gear_release_id="gear-release:sha256:target",
            gear_snapshot=snapshot,
        )

        self.assertEqual(evidence["slots"]["head"]["iconUrl"], icon_url)

    def test_import_evidence_rejects_unbound_target_icon_when_catalog_metadata_is_missing(self):
        from server.gear_release_store import GearReleaseIntegrityError
        from server.gear_release_tool import community_template_import_evidence_from_template

        template = self.template()
        template["gearItems"][0].update({
            "iconUrl": "https://render.worldofwarcraft.com/icons/other-item.jpg",
            "gameAsset": {
                "status": "verified",
                "entityType": "item",
                "entityId": "item-other",
                "iconUrl": "https://render.worldofwarcraft.com/icons/other-item.jpg",
            },
        })
        snapshot = self.snapshot()
        snapshot["items"][0]["payload"] = {}

        with self.assertRaises(GearReleaseIntegrityError):
            community_template_import_evidence_from_template(
                template,
                gear_release_id="gear-release:sha256:target",
                gear_snapshot=snapshot,
            )

    def test_import_evidence_rejects_incomplete_or_mismatched_observed_facts(self):
        from server.gear_release_store import GearReleaseIntegrityError
        from server.gear_release_tool import community_template_import_evidence_from_template

        def complete_inputs():
            template = self.template()
            template["gearItems"][0]["itemLevel"] = 292
            snapshot = self.snapshot()
            snapshot["items"][0]["payload"] = {
                "_metadata": {
                    "iconUrl": "https://render.worldofwarcraft.com/icons/item-a.jpg",
                    "gameAsset": {"source": "blizzard", "status": "verified"},
                },
            }
            snapshot["variants"][0]["itemLevel"] = 292
            return template, snapshot

        mutations = {
            "missing_observed_level": lambda template, snapshot: template["gearItems"][0].pop("itemLevel"),
            "missing_exact_variant": lambda template, snapshot: snapshot.__setitem__("variants", []),
            "variant_level_mismatch": lambda template, snapshot: snapshot["variants"][0].__setitem__("itemLevel", 291),
            "missing_verified_icon": lambda template, snapshot: snapshot["items"][0]["payload"]["_metadata"].pop("iconUrl"),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                template, snapshot = complete_inputs()
                mutate(template, snapshot)
                with self.assertRaises(GearReleaseIntegrityError):
                    community_template_import_evidence_from_template(
                        template,
                        gear_release_id="gear-release:sha256:target",
                        gear_snapshot=snapshot,
                    )

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

    def test_v2_materialization_makes_gems_universal_but_keeps_socket_capacity_authoritative(self):
        from server.gear_release_store import GearReleaseIntegrityError
        from server.gear_release_tool import (
            GearReleaseIntegrityError,
            _materialize_enhancement_management,
            selection_intent_from_template,
        )
        from server.gear_socket_authority import (
            CAPABILITY_REVISION,
            LEGACY_CAPABILITY_REVISION,
        )

        snapshot = self.snapshot()
        snapshot["items"][0]["payload"] = {
            "_metadata": {
                "iconUrl": "https://render.worldofwarcraft.com/icons/item-a.jpg",
                "gameAsset": {"source": "blizzard", "status": "verified"},
            },
            "baseCapabilities": {
                "socketCount": 1,
                "canEnchant": False,
                "canEmbellish": False,
            }
        }
        snapshot["variants"][0]["simcOptions"] = {
            "ilevel": "289",
            "gem_id": "240892",
        }
        snapshot["variants"][0]["payload"] = {
            "resolvedStats": {"intellect": 100},
            "capabilityOverrides": {"socketCount": 1},
        }
        snapshot["options"] = [{
            "optionId": "option-gem-240892",
            "optionKey": "gem-240892",
            "optionType": "socket",
            "name": "Canonical gem 240892",
            "applicableSlots": ["neck", "finger1", "finger2"],
            "simcOptions": {"gem_id": "240892"},
            "status": "verified",
            "isVisible": True,
            "payload": {},
        }]
        snapshot["items"].append(verified_official_gem_item("240892"))
        template = self.template()
        template["gearItems"][0]["gem_id"] = "240892"

        materialized = _materialize_enhancement_management(
            snapshot,
            CAPABILITY_REVISION,
        )
        intent = selection_intent_from_template(
            template,
            gear_release_id="gear-release:sha256:target",
            season_revision="season-17",
            level=90,
            gear_snapshot=materialized,
            capability_revision=CAPABILITY_REVISION,
        )

        self.assertEqual(materialized["options"][0]["applicableSlots"], ["*"])
        self.assertEqual(intent["slots"]["head"]["gemOptionIds"], ["gem-240892"])

        no_socket_snapshot = copy.deepcopy(snapshot)
        no_socket_snapshot["items"][0]["payload"]["baseCapabilities"]["socketCount"] = 0
        no_socket_snapshot["variants"][0]["payload"]["capabilityOverrides"]["socketCount"] = 0
        with self.assertRaisesRegex(
            GearReleaseIntegrityError,
            "raw gem sequence conflicts with materialized socket capacity",
        ):
            _materialize_enhancement_management(
                no_socket_snapshot,
                CAPABILITY_REVISION,
            )

        legacy = _materialize_enhancement_management(
            snapshot,
            LEGACY_CAPABILITY_REVISION,
        )
        self.assertEqual(
            legacy["options"][0]["applicableSlots"],
            ["neck", "finger1", "finger2"],
        )

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

    def test_single_winner_release_skips_invalid_public_template_with_gate_evidence(self):
        from server.gear_release_store import gear_snapshot_summary
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
        snapshot["variants"][0]["simcOptions"] = {
            "ilevel": "289",
            "gem_id": "240892",
        }
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
        template = self.template(template_id="observed-public")
        template["gearItems"][0]["gem_id"] = "240892/240892"
        dependencies = {
            **self.dependencies(),
            "capabilityRevision": CAPABILITY_REVISION,
        }
        gear = gear_release.build_release(
            release_kind="gear",
            season_revision="season-17",
            schema_revision="gear-release-v1",
            content=gear_snapshot_summary(snapshot),
            dependency_revisions=dependencies,
            release_status="validated",
            source={"sourceRevision": "single-winner-preflight-test"},
        )
        store = FakeReleaseStore(snapshot, [template])
        store.community_skip_invalid_public_template_evidence = True

        result = build_legacy_community_release(
            store,
            gear_release_descriptor=gear,
            gear_snapshot=snapshot,
            dependency_revisions=dependencies,
            expected_specs=[("mage", "arcane")],
            now="2026-07-14T01:00:00+00:00",
        )

        self.assertEqual(result["gate"]["status"], "degraded")
        self.assertEqual(
            result["gate"]["missingSpecs"],
            [{"classKey": "mage", "specKey": "arcane"}],
        )
        self.assertEqual(result["gate"]["preflightRejectedCount"], 1)
        self.assertEqual(
            result["gate"]["preflightRejectedTemplates"][0]["templateId"],
            "observed-public",
        )
        self.assertIn(
            "template gem sequence conflicts with materialized socket capacity",
            result["gate"]["preflightRejectedTemplates"][0]["detail"],
        )
        self.assertEqual(len(store.community_seals), 1)
        self.assertEqual(
            store.community_seals[0][2]["gate_result"]["status"],
            "degraded",
        )

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

    def test_non_public_template_gem_conflict_is_rejected_without_blocking_release(self):
        from server.gear_release_store import gear_snapshot_summary
        from server.gear_release_tool import build_legacy_community_release
        from server.gear_socket_authority import CAPABILITY_REVISION

        snapshot = self.snapshot()
        snapshot["items"][0]["payload"] = {
            "_metadata": {
                "iconUrl": "https://render.worldofwarcraft.com/icons/item-a.jpg",
                "gameAsset": {"source": "blizzard", "status": "verified"},
            },
            "baseCapabilities": {
                "socketCount": 0,
                "canEnchant": False,
                "canEmbellish": False,
            }
        }
        snapshot["variants"][0]["payload"] = {
            "resolvedStats": {"intellect": 100},
            "capabilityOverrides": {"socketCount": 0},
        }
        public_template = self.template(template_id="observed-public")
        public_template["gearItems"][0]["gem_id"] = ""
        non_public_template = self.template(
            template_id="recommended-conflict",
            source_key="recommended_bis",
        )
        non_public_template["gearItems"][0]["gem_id"] = "240892"
        dependencies = {
            **self.dependencies(),
            "capabilityRevision": CAPABILITY_REVISION,
        }
        gear = gear_release.build_release(
            release_kind="gear",
            season_revision="season-17",
            schema_revision="gear-release-v1",
            content=gear_snapshot_summary(snapshot),
            dependency_revisions=dependencies,
            release_status="validated",
            source={"sourceRevision": "non-public-capacity-contradiction-test"},
        )
        store = FakeReleaseStore(
            snapshot,
            [public_template, non_public_template],
        )
        resolver_calls = []

        result = build_legacy_community_release(
            store,
            gear_release_descriptor=gear,
            gear_snapshot=snapshot,
            dependency_revisions=dependencies,
            expected_specs=[("mage", "arcane")],
            now="2026-07-14T01:00:00+00:00",
            resolver_for_spec=lambda class_key, spec_key, intent: (
                resolver_calls.append((class_key, spec_key, intent))
                or self.verified_result(gear["releaseId"])
            ),
        )

        self.assertEqual(result["release"]["releaseStatus"], "validated")
        self.assertEqual(len(resolver_calls), 1)
        self.assertEqual(
            result["election"]["winners"][0]["candidateId"],
            "observed-public",
        )
        rejected = next(row for row in result["rows"] if row["role"] == "rejected")
        self.assertEqual(rejected["templateId"], "recommended-conflict")
        self.assertEqual(rejected["selectionIntent"], {})
        self.assertIn(
            "COMMUNITY_SOURCE_NOT_PUBLIC",
            {problem["code"] for problem in rejected["problems"]},
        )
        self.assertEqual(len(store.community_seals), 1)

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

    def test_v2_materializes_verified_official_observed_gem_as_editable_option(self):
        from server.gear_release_tool import (
            GearReleaseIntegrityError,
            _materialize_enhancement_management,
            selection_intent_from_template,
        )
        from server.gear_socket_authority import CAPABILITY_REVISION

        snapshot = self.snapshot()
        snapshot["items"][0]["payload"] = {
            "baseCapabilities": {
                "socketCount": 1,
                "canEnchant": False,
                "canEmbellish": False,
            }
        }
        snapshot["variants"][0]["simcOptions"] = {
            "ilevel": "289",
            "gem_id": "241144",
        }
        snapshot["variants"][0]["payload"] = {
            "resolvedStats": {"intellect": 100},
            "capabilityOverrides": {"socketCount": 1},
        }
        snapshot["items"].append({
            "itemId": "241144",
            "name": "Enduring Heliotrope",
            "slot": "",
            "sourceStatus": "unknown",
            "payload": {
                "_links": {
                    "self": {
                        "href": "https://us.api.blizzard.com/data/wow/item/241144",
                    }
                },
                "_metadata": {
                    "source": "Battle.net Game Data API",
                    "iconUrl": "https://render.worldofwarcraft.com/gem.jpg",
                    "gameAsset": {
                        "source": "blizzard",
                        "status": "verified",
                    },
                },
                "item_class": {"id": 3, "name": "Gem"},
                "item_subclass": {"id": 9, "name": "Other"},
                "preview_item": {
                    "gem_properties": {
                        "effect": "+20 Primary Stat and 5% damage reduction",
                    },
                    "limit_category": "装备唯一：萨拉斯钻石 （1）",
                },
            },
            "updatedAt": "2026-07-14T05:00:00+00:00",
        })

        materialized = _materialize_enhancement_management(
            snapshot,
            CAPABILITY_REVISION,
        )

        option = next(
            row
            for row in materialized["options"]
            if row.get("optionKey") == "gem-241144"
        )
        self.assertEqual(option["simcOptions"], {"gem_id": "241144"})
        self.assertEqual(option["applicableSlots"], ["*"])
        self.assertEqual(option["status"], "verified")
        self.assertTrue(option["isVisible"])
        self.assertEqual(option["payload"]["uniqueLimit"], 1)
        self.assertTrue(option["payload"]["uniqueGroup"].startswith("official-gem-limit:"))
        self.assertEqual(
            materialized["variants"][0]["payload"]["enhancementManagement"]["fields"]["gem_id"],
            "editor_managed",
        )

        template = self.template()
        template["gearItems"][0]["gem_id"] = "241144"
        template["gearItems"][0]["enchant_id"] = ""
        intent = selection_intent_from_template(
            template,
            gear_release_id="gear-release:sha256:official-gem",
            season_revision="season-17",
            level=90,
            gear_snapshot=materialized,
            capability_revision=CAPABILITY_REVISION,
        )
        self.assertEqual(intent["slots"]["head"]["gemOptionIds"], ["gem-241144"])

        corrupted_existing = copy.deepcopy(snapshot)
        corrupted_existing["options"] = [{
            "optionId": "forged-existing-gem",
            "optionKey": "gem-241144",
            "optionType": "socket",
            "name": "Forged existing diamond",
            "applicableSlots": ["finger1"],
            "simcOptions": {"gem_id": "241144"},
            "status": "verified",
            "isVisible": True,
            "payload": {
                "displayName": "Forged existing diamond",
                "displayLabel": "Forged",
                "displayStatus": "verified",
                "uniqueGroup": "forged-group",
                "uniqueLimit": 99,
            },
        }]
        repaired = _materialize_enhancement_management(
            corrupted_existing,
            CAPABILITY_REVISION,
        )
        repaired_options = [
            row
            for row in repaired["options"]
            if (row.get("simcOptions") or {}).get("gem_id") == "241144"
        ]
        self.assertEqual(len(repaired_options), 1)
        self.assertEqual(repaired_options[0]["optionId"], "official-gem-241144")
        self.assertEqual(
            repaired_options[0]["payload"]["uniqueGroup"],
            "official-gem-limit:thalassian-diamond",
        )
        self.assertEqual(repaired_options[0]["payload"]["uniqueLimit"], 1)

        ordinary = copy.deepcopy(snapshot)
        ordinary["variants"][0]["simcOptions"]["gem_id"] = "240892"
        ordinary_gem_item = ordinary["items"][-1]
        ordinary_gem_item["itemId"] = "240892"
        ordinary_gem_item["name"] = "Quick Onyx"
        ordinary_gem_item["payload"]["_links"]["self"]["href"] = (
            "https://us.api.blizzard.com/data/wow/item/240892"
        )
        ordinary_gem_item["payload"]["preview_item"].pop("limit_category", None)
        ordinary["options"] = [{
            "optionId": "wowhead-live-gem-240892",
            "optionKey": "gem-240892",
            "optionType": "socket",
            "name": "Quick Onyx",
            "applicableSlots": ["*"],
            "simcOptions": {"gem_id": "240892"},
            "status": "verified",
            "isVisible": True,
            "payload": {
                "displayName": "Quick Onyx",
                "displayLabel": "+12 Haste (live tooltip)",
                "displayStatus": "verified",
                "statSummary": "+12 Haste (live tooltip)",
                "evidenceSource": "wowhead_live_tooltip",
                "uniqueGroup": "forged-group",
                "uniqueLimit": 99,
            },
        }]
        ordinary_materialized = _materialize_enhancement_management(
            ordinary,
            CAPABILITY_REVISION,
        )
        ordinary_options = [
            row
            for row in ordinary_materialized["options"]
            if (row.get("simcOptions") or {}).get("gem_id") == "240892"
        ]
        self.assertEqual(len(ordinary_options), 1)
        self.assertEqual(
            ordinary_options[0]["optionId"],
            "official-gem-240892",
        )
        self.assertEqual(ordinary_options[0]["optionKey"], "gem-240892")
        self.assertEqual(ordinary_options[0]["simcOptions"], {"gem_id": "240892"})
        self.assertEqual(
            ordinary_options[0]["payload"]["statSummary"],
            "+12 Haste (live tooltip)",
        )
        self.assertEqual(
            ordinary_options[0]["payload"]["evidenceSource"],
            "wowhead_live_tooltip",
        )
        self.assertNotIn("uniqueGroup", ordinary_options[0]["payload"])
        self.assertNotIn("uniqueLimit", ordinary_options[0]["payload"])

        unavailable_official = copy.deepcopy(ordinary)
        unavailable_official["items"] = unavailable_official["items"][:-1]
        unavailable_materialized = _materialize_enhancement_management(
            unavailable_official,
            CAPABILITY_REVISION,
        )
        self.assertFalse(
            any(
                row.get("optionKey") == "gem-240892"
                for row in unavailable_materialized["options"]
            )
        )

        for mutate_seed in (
            lambda option: option.update(optionKey="gem-forged"),
            lambda option: option["simcOptions"].update(enchant_id="9999"),
            lambda option: option["simcOptions"].update(gem_id="240 892"),
        ):
            with self.subTest(malformed_live_seed=mutate_seed):
                malformed_seed = copy.deepcopy(ordinary)
                mutate_seed(malformed_seed["options"][0])
                rematerialized = _materialize_enhancement_management(
                    malformed_seed,
                    CAPABILITY_REVISION,
                )
                rematerialized_options = [
                    row
                    for row in rematerialized["options"]
                    if row.get("optionKey") == "gem-240892"
                ]
                self.assertEqual(len(rematerialized_options), 1)
                self.assertEqual(
                    rematerialized_options[0]["optionId"],
                    "official-gem-240892",
                )
                self.assertEqual(
                    rematerialized_options[0]["simcOptions"],
                    {"gem_id": "240892"},
                )
                self.assertNotEqual(
                    rematerialized_options[0]["payload"]["statSummary"],
                    "+12 Haste (live tooltip)",
                )

        categorized_ordinary = copy.deepcopy(ordinary)
        categorized_ordinary["items"][-1]["payload"]["preview_item"]["limit_category"] = (
            "Unique-Equipped: Thalassian Diamond (1)"
        )
        categorized_materialized = _materialize_enhancement_management(
            categorized_ordinary,
            CAPABILITY_REVISION,
        )
        categorized_options = [
            row
            for row in categorized_materialized["options"]
            if (row.get("simcOptions") or {}).get("gem_id") == "240892"
        ]
        self.assertEqual(len(categorized_options), 1)
        self.assertEqual(categorized_options[0]["optionId"], "official-gem-240892")
        self.assertEqual(
            categorized_options[0]["payload"]["uniqueGroup"],
            "official-gem-limit:thalassian-diamond",
        )
        self.assertEqual(categorized_options[0]["payload"]["uniqueLimit"], 1)

        multi_field_category = copy.deepcopy(ordinary)
        multi_field_category["items"][-1]["payload"]["preview_item"][
            "limit_category"
        ] = {
            "display_string": "Unique-Equipped: Thalassian Diamond (1)",
            "name": "装备唯一：萨拉斯钻石（1）",
        }
        multi_field_materialized = _materialize_enhancement_management(
            multi_field_category,
            CAPABILITY_REVISION,
        )
        multi_field_option = next(
            row
            for row in multi_field_materialized["options"]
            if row.get("optionKey") == "gem-240892"
        )
        self.assertEqual(multi_field_option["payload"]["uniqueLimit"], 1)
        self.assertEqual(
            multi_field_option["payload"]["uniqueGroup"],
            "official-gem-limit:thalassian-diamond",
        )

        for invalid_category in (
            "Unique-Equipped: Thalassian Diamond (99)",
            "Unique-Equipped: Unknown Diamond (1)",
            "Explicit but malformed unique marker",
            {"unexpected": "Unique-Equipped: Thalassian Diamond (1)"},
            {
                "display_string": "Unique-Equipped: Thalassian Diamond (1)",
                "name": "Unique-Equipped: Unknown Diamond (1)",
            },
            ["Unique-Equipped: Thalassian Diamond (1)"],
            1,
        ):
            with self.subTest(invalid_ordinary_category=invalid_category):
                invalid_ordinary = copy.deepcopy(ordinary)
                invalid_ordinary["items"][-1]["payload"]["preview_item"][
                    "limit_category"
                ] = invalid_category
                invalid_materialized = _materialize_enhancement_management(
                    invalid_ordinary,
                    CAPABILITY_REVISION,
                )
                self.assertEqual(
                    [
                        row
                        for row in invalid_materialized["options"]
                        if row.get("optionKey") == "gem-240892"
                    ],
                    [],
                )

        conflicting_ordinary = copy.deepcopy(ordinary)
        conflicting_ordinary["items"] = conflicting_ordinary["items"][:-1]
        conflicting_ordinary["options"][0]["simcOptions"]["gem_id"] = "240983"
        with self.assertRaisesRegex(
            GearReleaseIntegrityError,
            "gem option identity conflicts with cached option",
        ):
            _materialize_enhancement_management(
                conflicting_ordinary,
                CAPABILITY_REVISION,
            )

        for limit_category, subclass_id, expected_unique_group in (
            (
                {"display_string": "装备唯一：萨拉斯钻石 （1）"},
                9,
                "official-gem-limit:thalassian-diamond",
            ),
            (
                "Unique-Equipped: Thalassian Diamond (1)",
                0,
                "official-gem-limit:thalassian-diamond",
            ),
            (
                "裝備唯一：薩拉斯鑽石（1）",
                0,
                "official-gem-limit:thalassian-diamond",
            ),
            ("Unique-Equippedness: Thalassian Diamond (1)", 9, ""),
            ("装备唯一性说明：萨拉斯钻石（1）", 9, ""),
            ("Unique-Equipped: Unknown Diamond (1)", 9, ""),
            ("Not Unique Cosmetic (1)", 9, ""),
        ):
            with self.subTest(
                limit_category=limit_category,
                subclass_id=subclass_id,
            ):
                categorized = copy.deepcopy(snapshot)
                categorized["items"][-1]["payload"]["preview_item"]["limit_category"] = limit_category
                categorized["items"][-1]["payload"]["item_subclass"]["id"] = subclass_id
                if not expected_unique_group:
                    with self.assertRaises(GearReleaseIntegrityError):
                        _materialize_enhancement_management(
                            categorized,
                            CAPABILITY_REVISION,
                        )
                    continue
                rematerialized = _materialize_enhancement_management(
                    categorized,
                    CAPABILITY_REVISION,
                )
                rematerialized_options = [
                    row
                    for row in rematerialized["options"]
                    if row.get("optionKey") == "gem-241144"
                ]
                self.assertEqual(
                    rematerialized_options[0]["payload"]["uniqueGroup"],
                    expected_unique_group,
                )

    def test_v2_does_not_materialize_observed_gem_without_verified_official_gem_metadata(self):
        from server.gear_release_tool import (
            GearReleaseIntegrityError,
            _materialize_enhancement_management,
        )
        from server.gear_socket_authority import CAPABILITY_REVISION

        for metadata_status, game_asset_status, game_asset_source, item_class_id, evidence_ref, metadata_source in (
            ("partial", "partial", "blizzard", 3, "https://us.api.blizzard.com/data/wow/item/241144", "Battle.net Game Data API"),
            ("verified", "partial", "third_party", 3, "https://us.api.blizzard.com/data/wow/item/241144", "Battle.net Game Data API"),
            ("", "verified", "third_party", 3, "https://us.api.blizzard.com/data/wow/item/241144", "Battle.net Game Data API"),
            ("", "verified", "blizzard", 4, "https://us.api.blizzard.com/data/wow/item/241144", "Battle.net Game Data API"),
            ("", "verified", "blizzard", 3, "https://us.api.blizzard.com/data/wow/item/241145", "Battle.net Game Data API"),
            ("", "verified", "blizzard", 3, "https://us.api.blizzard.com/data/wow/item/241144", "Not Battle.net Game Data API / forged"),
        ):
            with self.subTest(
                metadata_status=metadata_status,
                game_asset_status=game_asset_status,
                game_asset_source=game_asset_source,
                item_class_id=item_class_id,
                evidence_ref=evidence_ref,
                metadata_source=metadata_source,
            ):
                snapshot = self.snapshot()
                snapshot["items"][0]["payload"] = {
                    "baseCapabilities": {"socketCount": 1},
                }
                snapshot["variants"][0]["simcOptions"] = {
                    "ilevel": "289",
                    "gem_id": "241144",
                }
                snapshot["variants"][0]["payload"] = {
                    "resolvedStats": {"intellect": 100},
                    "capabilityOverrides": {"socketCount": 1},
                }
                snapshot["items"].append({
                    "itemId": "241144",
                    "name": "Unverified gem",
                    "slot": "",
                    "sourceStatus": "unknown",
                    "payload": {
                        "_links": {
                            "self": {
                                "href": evidence_ref,
                            }
                        },
                        "_metadata": {
                            "status": metadata_status,
                            "source": metadata_source,
                            "iconUrl": "https://render.worldofwarcraft.com/gem.jpg",
                            "gameAsset": {
                                "source": game_asset_source,
                                "status": game_asset_status,
                            },
                        },
                        "item_class": {"id": item_class_id, "name": "Gem"},
                        "preview_item": {
                            "gem_properties": {"effect": "+20 Primary Stat"},
                            "limit_category": "Unique-Equipped: Thalassian Diamond (1)",
                        },
                    },
                    "updatedAt": "2026-07-14T05:00:00+00:00",
                })

                with self.assertRaises(GearReleaseIntegrityError):
                    _materialize_enhancement_management(
                        snapshot,
                        CAPABILITY_REVISION,
                    )

    def test_v2_weapon_enchant_source_only_requires_exact_simc_echo(self):
        from server.gear_release_tool import _materialize_enhancement_management
        from server.gear_socket_authority import CAPABILITY_REVISION

        snapshot = self.snapshot()
        snapshot["items"][0]["slot"] = "main_hand"
        snapshot["items"][0]["payload"] = {
            "baseCapabilities": {"socketCount": 0, "canEnchant": True},
        }

        def variant(
            key,
            slot,
            raw_enchant,
            encoded_enchant,
            *,
            raw_bonus="",
            encoded_bonus="",
        ):
            simc_options = {"ilevel": "298", "enchant_id": raw_enchant}
            if raw_bonus:
                simc_options["bonus_id"] = raw_bonus
            encoded_parts = [
                "item_a",
                "id=item-a",
                "ilevel=298",
                f"enchant_id={encoded_enchant}",
            ]
            if encoded_bonus:
                encoded_parts.append(f"bonus_id={encoded_bonus}")
            return {
                **copy.deepcopy(snapshot["variants"][0]),
                "variantId": key,
                "variantKey": key,
                "slot": slot,
                "itemLevel": 298,
                "simcOptions": simc_options,
                "payload": {
                    "resolvedStats": {"strength": 100},
                    "statSource": "simulationcraft",
                    "statDisplayStatus": "verified_variant",
                    "itemStats": [{"type": "strength", "value": 100}],
                    "simcItemId": "item-a",
                    "simcItemLevel": 298,
                    "simcEncodedItem": ",".join(encoded_parts),
                },
            }

        duplicate_encoded = variant(
            "offhand-duplicate-encoded",
            "off_hand",
            "8041/8052",
            "8041/8052",
        )
        duplicate_encoded["payload"]["simcEncodedItem"] = (
            "item_a,id=item-a,ilevel=298,enchant_id=9999,"
            "enchant_id=8041/8052"
        )
        snapshot["variants"] = [
            variant("offhand-composite", "off_hand", "8039/8052", "8039/8052"),
            variant("mainhand-single", "main_hand", "6245", "6245"),
            variant("offhand-mismatch", "off_hand", "8041/8052", "8041/9999"),
            duplicate_encoded,
            variant(
                "offhand-destructive-normalization",
                "off_hand",
                "80 41/8052",
                "8041/8052",
            ),
            variant(
                "offhand-bonus-mismatch",
                "off_hand",
                "8041/8052",
                "8041/8052",
                raw_bonus="40/13335",
                encoded_bonus="41/13335",
            ),
        ]
        raw_id_mismatch = variant(
            "offhand-raw-id-mismatch",
            "off_hand",
            "3368/8052",
            "3368/8052",
        )
        raw_id_mismatch["simcOptions"]["id"] = "item-b"
        snapshot["variants"].append(raw_id_mismatch)
        for suffix, raw_key in (("empty", ""), ("blank", "   ")):
            blank_key = variant(
                f"offhand-{suffix}-raw-key",
                "off_hand",
                f"337{3 if suffix == 'empty' else 4}/8052",
                f"337{3 if suffix == 'empty' else 4}/8052",
            )
            blank_key["simcOptions"][raw_key] = "evil"
            snapshot["variants"].append(blank_key)
        raw_ilevel_leading_zero = variant(
            "offhand-raw-ilevel-leading-zero",
            "off_hand",
            "3375/8052",
            "3375/8052",
        )
        raw_ilevel_leading_zero["simcOptions"]["ilevel"] = "0298"
        snapshot["variants"].append(raw_ilevel_leading_zero)
        encoded_ilevel_leading_zero = variant(
            "offhand-encoded-ilevel-leading-zero",
            "off_hand",
            "3376/8052",
            "3376/8052",
        )
        encoded_ilevel_leading_zero["payload"]["simcEncodedItem"] = (
            "item_a,id=item-a,ilevel=0298,enchant_id=3376/8052"
        )
        snapshot["variants"].append(encoded_ilevel_leading_zero)
        raw_value_whitespace = variant(
            "offhand-raw-value-whitespace",
            "off_hand",
            "3377/8052",
            "3377/8052",
        )
        raw_value_whitespace["simcOptions"]["enchant_id"] = " 3377/8052 "
        snapshot["variants"].append(raw_value_whitespace)
        encoded_value_whitespace = variant(
            "offhand-encoded-value-whitespace",
            "off_hand",
            "3378/8052",
            "3378/8052",
        )
        encoded_value_whitespace["payload"]["simcEncodedItem"] = (
            "item_a,id=item-a,ilevel=298,enchant_id= 3378/8052"
        )
        snapshot["variants"].append(encoded_value_whitespace)
        encoded_part_whitespace = variant(
            "offhand-encoded-part-whitespace",
            "off_hand",
            "3379/8052",
            "3379/8052",
        )
        encoded_part_whitespace["payload"]["simcEncodedItem"] = (
            "item_a,id=item-a,ilevel=298, enchant_id=3379/8052"
        )
        snapshot["variants"].append(encoded_part_whitespace)
        for suffix, padding in (("leading", "  "), ("trailing", "  ")):
            encoded_outer_whitespace = variant(
                f"offhand-encoded-{suffix}-whitespace",
                "off_hand",
                f"338{1 if suffix == 'leading' else 2}/8052",
                f"338{1 if suffix == 'leading' else 2}/8052",
            )
            encoded = encoded_outer_whitespace["payload"]["simcEncodedItem"]
            encoded_outer_whitespace["payload"]["simcEncodedItem"] = (
                f"{padding}{encoded}" if suffix == "leading" else f"{encoded}{padding}"
            )
            snapshot["variants"].append(encoded_outer_whitespace)
        raw_field_whitespace = variant(
            "offhand-raw-field-whitespace",
            "off_hand",
            "3380/8052",
            "3380/8052",
        )
        raw_field_whitespace["simcOptions"][" crafted_stats "] = "32/36"
        snapshot["variants"].append(raw_field_whitespace)

        materialized = _materialize_enhancement_management(
            snapshot,
            CAPABILITY_REVISION,
        )
        fields_by_key = {
            row["variantKey"]: row["payload"]["enhancementManagement"]["fields"]
            for row in materialized["variants"]
        }
        self.assertEqual(fields_by_key["offhand-composite"]["enchant_id"], "source_only")
        self.assertEqual(fields_by_key["mainhand-single"]["enchant_id"], "source_only")
        self.assertEqual(fields_by_key["offhand-mismatch"]["enchant_id"], "unresolved_drop")
        self.assertEqual(
            fields_by_key["offhand-duplicate-encoded"]["enchant_id"],
            "unresolved_drop",
        )
        self.assertEqual(
            fields_by_key["offhand-destructive-normalization"]["enchant_id"],
            "unresolved_drop",
        )
        self.assertEqual(
            fields_by_key["offhand-bonus-mismatch"]["enchant_id"],
            "unresolved_drop",
        )
        self.assertEqual(
            fields_by_key["offhand-raw-id-mismatch"]["enchant_id"],
            "unresolved_drop",
        )
        for key in (
            "offhand-empty-raw-key",
            "offhand-blank-raw-key",
            "offhand-raw-ilevel-leading-zero",
            "offhand-encoded-ilevel-leading-zero",
            "offhand-raw-value-whitespace",
            "offhand-encoded-value-whitespace",
            "offhand-encoded-part-whitespace",
            "offhand-encoded-leading-whitespace",
            "offhand-encoded-trailing-whitespace",
            "offhand-raw-field-whitespace",
        ):
            with self.subTest(non_exact_simc_option=key):
                self.assertEqual(fields_by_key[key]["enchant_id"], "unresolved_drop")

    def test_v2_exact_variant_can_reuse_only_semantically_identical_simc_echo(self):
        from server.gear_release_tool import _materialize_enhancement_management
        from server.gear_socket_authority import CAPABILITY_REVISION

        snapshot = self.snapshot()
        snapshot["items"][0]["slot"] = "shoulder"
        snapshot["items"][0]["payload"] = {
            "baseCapabilities": {"socketCount": 0, "canEnchant": False},
        }
        base = {
            **copy.deepcopy(snapshot["variants"][0]),
            "slot": "shoulder",
            "itemLevel": 289,
            "simcOptions": {
                "ilevel": "289",
                "bonus_id": "40/13577/13335",
                "enchant_id": "8001",
            },
            "payload": {
                "resolvedStats": {"intellect": 100},
                "statSource": "simulationcraft",
                "statDisplayStatus": "verified_variant",
            },
        }
        exact = {
            **copy.deepcopy(base),
            "variantId": "exact",
            "variantKey": "exact-key",
        }
        semantic_twin = {
            **copy.deepcopy(base),
            "variantId": "semantic-twin",
            "variantKey": "alternate-key-format",
            "simcOptions": {
                **base["simcOptions"],
                "bonus_id": "40/13335/13577",
            },
            "payload": {
                **base["payload"],
                "itemStats": [{"type": "intellect", "value": 100}],
                "simcItemId": "item-a",
                "simcItemLevel": 289,
                "simcEncodedItem": (
                    "item_a,id=item-a,ilevel=289,"
                    "bonus_id=40/13335/13577,enchant_id=8001"
                ),
            },
        }
        divergent = {
            **copy.deepcopy(exact),
            "variantId": "divergent",
            "variantKey": "divergent-key",
            "simcOptions": {
                **exact["simcOptions"],
                "bonus_id": "41/13577/13335",
            },
        }
        snapshot["variants"] = [exact, semantic_twin, divergent]

        materialized = _materialize_enhancement_management(
            snapshot,
            CAPABILITY_REVISION,
        )
        fields_by_key = {
            row["variantKey"]: row["payload"]["enhancementManagement"]["fields"]
            for row in materialized["variants"]
        }
        self.assertEqual(fields_by_key["exact-key"]["enchant_id"], "source_only")
        self.assertEqual(fields_by_key["alternate-key-format"]["enchant_id"], "source_only")
        self.assertEqual(fields_by_key["divergent-key"]["enchant_id"], "unresolved_drop")

    def test_exact_midnight_mage_candidate_keeps_source_only_embellishments_out_of_editable_intent(self):
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
        for option in fixture["snapshot"]["options"]:
            if option.get("optionType") == "socket":
                option["applicableSlots"] = ["neck", "finger1", "finger2"]
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
        self.assertTrue(all(
            option["applicableSlots"] == ["*"]
            for option in prepared_gear["snapshot"]["options"]
            if option.get("optionType") == "socket"
        ))
        primary_stat_option = next(
            option
            for option in prepared_gear["snapshot"]["options"]
            if option.get("optionKey") == "gem-240983"
        )
        self.assertEqual(
            primary_stat_option["payload"]["uniqueGroup"],
            "official-gem-limit:thalassian-diamond",
        )
        self.assertEqual(primary_stat_option["payload"]["uniqueLimit"], 1)
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
            0,
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
        duplicate_primary_stat_intent = copy.deepcopy(intent)
        duplicate_primary_stat_intent["slots"]["head"]["gemOptionIds"] = [
            "gem-240983"
        ]
        duplicate_primary_stat_authority = build_candidate_authority_context(
            prepared_gear["snapshot"],
            duplicate_primary_stat_intent,
            runtime,
            prepared_gear["release"],
        )
        duplicate_primary_stat_snapshot = gear_resolver.resolve(
            duplicate_primary_stat_intent,
            duplicate_primary_stat_authority,
        )
        self.assertEqual(duplicate_primary_stat_snapshot["status"], "blocked")
        self.assertIn(
            "GEAR_GEM_UNIQUE_LIMIT_EXCEEDED",
            {
                problem["code"]
                for problem in duplicate_primary_stat_snapshot["problems"]
            },
        )
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
        self.assertEqual(
            prepared["rows"][0]["payload"]["importEvidence"]["schemaRevision"],
            "community-template-import-evidence-v3",
        )
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

    def test_materialized_socket_fact_digest_streams_the_legacy_exact_hash(self):
        from server import gear_release_tool

        snapshot = self.snapshot()
        snapshot["items"][0]["payload"]["baseCapabilities"] = {
            "socketCount": 1
        }
        snapshot["items"][0]["payload"]["socketEvidence"] = {
            "minimumTotal": 1,
            "claims": [{"source": "item"}],
        }
        snapshot["variants"][0]["payload"]["capabilityOverrides"] = {
            "socketCount": 2
        }
        snapshot["variants"][0]["payload"]["socketEvidence"] = {
            "minimumTotal": 2,
            "claims": [{"source": "variant"}],
        }
        expected = gear_release_tool._materialized_socket_fact_digest(
            snapshot
        )

        with patch.object(
            gear_release_tool,
            "_canonical_digest",
            side_effect=AssertionError(
                "socket fact digest must not encode one full duplicate graph"
            ),
        ):
            actual = gear_release_tool._materialized_socket_fact_digest(
                snapshot
            )

        self.assertEqual(actual, expected)

    def test_community_builder_projection_blocks_template_scope_drift(self):
        from server.gear_release_store import gear_snapshot_summary
        from server.gear_release_tool import (
            GearReleaseIntegrityError,
            prepare_staging_community_release,
        )

        snapshot = self.snapshot()
        descriptor = gear_release.build_release(
            release_kind="gear",
            season_revision="season-17",
            schema_revision="gear-release-v1",
            content=gear_snapshot_summary(snapshot),
            dependency_revisions=self.dependencies(),
            release_status="validated",
            source={"sourceRevision": "test"},
        )
        snapshot["_releaseProjection"] = {
            "schemaRevision": "community-builder-release-projection-v2",
            "referenceItemIds": ["item-other"],
        }

        with self.assertRaisesRegex(
            GearReleaseIntegrityError,
            "misses staging template item scope: item-a",
        ):
            prepare_staging_community_release(
                FakeReleaseStore(
                    snapshot,
                    templates=[self.template()],
                ),
                gear_release_descriptor=descriptor,
                gear_snapshot=snapshot,
                dependency_revisions=self.dependencies(),
                expected_specs=[("mage", "arcane")],
                now="2026-07-29T00:00:00+00:00",
            )

    def test_prepare_staging_gear_release_excludes_noncombat_cosmetic_rows(self):
        from server.gear_release_tool import prepare_staging_gear_release

        snapshot = self.snapshot()
        snapshot["items"].append(
            {
                "itemId": "268280",
                "name": "Cosmetic Helm",
                "slot": "head",
                "sourceStatus": "verified",
                "payload": {
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 5, "name": "Cosmetic"},
                },
                "updatedAt": "2026-07-28T12:00:00+00:00",
            }
        )
        snapshot["sources"].append(
            {
                "sourceId": "source-cosmetic",
                "itemId": "268280",
                "sourceType": "raid",
                "sourceKey": "raid:1305:268280",
                "instanceId": "1305",
                "payload": {"status": "verified"},
                "updatedAt": "2026-07-28T12:00:00+00:00",
            }
        )
        snapshot["variants"].append(
            {
                "variantId": "variant-cosmetic",
                "itemId": "268280",
                "variantKey": "champion-263",
                "slot": "head",
                "sourceType": "raid",
                "difficultyKey": "champion",
                "itemLevel": 263,
                "simcOptions": {"ilevel": "263"},
                "status": "partial",
                "blockers": ["SimC JSON did not include target item stats"],
                "payload": {},
                "updatedAt": "2026-07-28T12:00:00+00:00",
            }
        )
        snapshot["options"].append(
            {
                "optionId": "option-cosmetic",
                "variantId": "variant-cosmetic",
                "optionKey": "cosmetic-option",
                "optionType": "socket",
                "name": "Must be excluded",
                "applicableSlots": ["head"],
                "simcOptions": {},
                "status": "verified",
                "isVisible": True,
                "payload": {},
                "updatedAt": "2026-07-28T12:00:00+00:00",
            }
        )

        prepared = prepare_staging_gear_release(
            FakeReleaseStore(snapshot),
            season_revision="season-17",
            dependency_revisions=self.dependencies(),
            socket_bonus_minimums={"9300": 1},
        )

        sealed = prepared["snapshot"]
        self.assertNotIn("268280", {row["itemId"] for row in sealed["items"]})
        self.assertNotIn("268280", {row["itemId"] for row in sealed["sources"]})
        self.assertNotIn("268280", {row["itemId"] for row in sealed["variants"]})
        self.assertNotIn(
            "option-cosmetic",
            {row["optionId"] for row in sealed["options"]},
        )
        source_evidence = prepared["release"]["source"]["sourceEvidence"]
        self.assertEqual(source_evidence["excludedNonCombatItemCount"], 1)
        self.assertTrue(
            source_evidence["excludedNonCombatItemDigest"].startswith("sha256:")
        )

    def test_prepare_staging_gear_release_reuses_one_mutable_snapshot_projection(self):
        from server import gear_release_tool

        snapshot = self.snapshot()
        with (
            patch.object(
                gear_release_tool.gear_socket_authority,
                "materialize_gear_socket_facts",
                wraps=gear_release_tool.gear_socket_authority.materialize_gear_socket_facts,
            ) as socket_materializer,
            patch.object(
                gear_release_tool,
                "_project_socket_facts_into_release_payloads",
                wraps=gear_release_tool._project_socket_facts_into_release_payloads,
            ) as socket_projector,
            patch.object(
                gear_release_tool,
                "_materialize_enhancement_management",
                wraps=gear_release_tool._materialize_enhancement_management,
            ) as enhancement_materializer,
        ):
            prepared = gear_release_tool.prepare_staging_gear_release(
                FakeReleaseStore(snapshot),
                season_revision="season-17",
                dependency_revisions=self.dependencies(),
                socket_bonus_minimums={"9300": 1},
            )

        self.assertEqual(prepared["gate"]["status"], "validated")
        self.assertFalse(socket_materializer.call_args.kwargs["copy_snapshot"])
        self.assertFalse(socket_projector.call_args.kwargs["copy_snapshot"])
        self.assertFalse(
            enhancement_materializer.call_args.kwargs["copy_snapshot"]
        )

    def test_current_pve_socket_eligibility_is_sealed_in_release_item_payload(self):
        from server.gear_release_tool import prepare_staging_gear_release

        revision = "season-17-f131dd36ddf1"
        snapshot = self.snapshot()
        snapshot["items"][0]["itemId"] = "249970"
        snapshot["items"][0]["name"] = "冷厉骑手的尖冠"
        snapshot["items"][0]["payload"]["preview_item"] = {"sockets": []}
        snapshot["variants"][0]["itemId"] = "249970"
        snapshot["variants"][0]["slot"] = "head"
        snapshot["sources"] = [
            {
                "sourceId": "tier-set-249970",
                "itemId": "249970",
                "sourceType": "tier_set",
                "sourceKey": "tier-set:249970",
                "seasonRevision": revision,
                "payload": {"status": "verified"},
            }
        ]

        prepared = prepare_staging_gear_release(
            FakeReleaseStore(snapshot),
            season_revision=revision,
            dependency_revisions=self.dependencies(),
            socket_bonus_minimums={"9300": 1},
        )

        item_payload = prepared["snapshot"]["items"][0]["payload"]
        self.assertEqual(item_payload["baseCapabilities"]["socketCount"], 1)
        self.assertEqual(
            item_payload["socketEligibility"],
            {
                "schemaRevision": "gear-socket-eligibility-v1",
                "status": "verified",
                "eligibility": "active_pve_catalog",
                "sourceRevision": revision,
                "sourceIds": ["tier-set-249970"],
                "sourceTypes": ["tier_set"],
            },
        )

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

    def test_community_release_reuses_one_candidate_authority_index_for_all_templates(self):
        from server import gear_release_tool
        from server.gear_release_store import CandidateGearAuthorityIndex, gear_snapshot_summary

        snapshot = self.snapshot()
        gear = gear_release.build_release(
            release_kind="gear",
            season_revision="season-17",
            schema_revision="gear-release-v1",
            content=gear_snapshot_summary(snapshot),
            dependency_revisions=self.dependencies(),
            release_status="validated",
            source={"sourceRevision": "prepared-index-test"},
        )
        second = self.template("template-b")
        second["sourceUrl"] = "https://raider.io/characters/cn/b"
        store = FakeReleaseStore(snapshot, [self.template(), second])

        with patch.object(
            gear_release_tool,
            "CandidateGearAuthorityIndex",
            wraps=CandidateGearAuthorityIndex,
        ) as index_factory, patch.object(
            gear_release_tool,
            "selection_intent_from_template",
            wraps=gear_release_tool.selection_intent_from_template,
        ) as selection_intent, patch.object(
            gear_release_tool,
            "community_template_import_evidence_from_template",
            wraps=gear_release_tool.community_template_import_evidence_from_template,
        ) as import_evidence:
            result = gear_release_tool.prepare_staging_community_release(
                store,
                gear_release_descriptor=gear,
                gear_snapshot=snapshot,
                dependency_revisions=self.dependencies(),
                expected_specs=[("mage", "arcane")],
                now="2026-07-11T06:00:00+00:00",
                resolver_for_spec=lambda *_args: self.verified_result(gear["releaseId"]),
            )

        self.assertEqual(result["election"]["status"], "validated")
        self.assertEqual(index_factory.call_count, 1)
        prepared = selection_intent.call_args_list[0].kwargs["prepared_index"]
        self.assertTrue(all(
            call.kwargs["prepared_index"] is prepared
            for call in selection_intent.call_args_list
        ))
        self.assertTrue(all(
            call.kwargs["prepared_index"] is prepared
            for call in import_evidence.call_args_list
        ))

    def test_reused_candidate_authority_index_preserves_outputs_and_release_identity(self):
        from server import gear_release_tool
        from server.gear_release_store import (
            CandidateGearAuthorityIndex,
            GearReleaseIntegrityError,
            gear_snapshot_summary,
        )

        snapshot = self.snapshot()
        gear = gear_release.build_release(
            release_kind="gear",
            season_revision="season-17",
            schema_revision="gear-release-v1",
            content=gear_snapshot_summary(snapshot),
            dependency_revisions=self.dependencies(),
            release_status="validated",
            source={"sourceRevision": "prepared-index-identity-test"},
        )
        prepared = CandidateGearAuthorityIndex(snapshot, gear)
        plain_intent = gear_release_tool.selection_intent_from_template(
            self.template(),
            gear_release_id=gear["releaseId"],
            season_revision=gear["seasonRevision"],
            level=90,
            gear_snapshot=snapshot,
            capability_revision=self.dependencies()["capabilityRevision"],
        )
        indexed_intent = gear_release_tool.selection_intent_from_template(
            self.template(),
            gear_release_id=gear["releaseId"],
            season_revision=gear["seasonRevision"],
            level=90,
            gear_snapshot=snapshot,
            capability_revision=self.dependencies()["capabilityRevision"],
            prepared_index=prepared,
        )
        plain_evidence = gear_release_tool.community_template_import_evidence_from_template(
            self.template(),
            gear_release_id=gear["releaseId"],
            gear_snapshot=snapshot,
        )
        indexed_evidence = gear_release_tool.community_template_import_evidence_from_template(
            self.template(),
            gear_release_id=gear["releaseId"],
            gear_snapshot=snapshot,
            prepared_index=prepared,
        )

        self.assertEqual(indexed_intent, plain_intent)
        self.assertEqual(indexed_evidence, plain_evidence)

        other = gear_release.build_release(
            release_kind="gear",
            season_revision="season-other",
            schema_revision="gear-release-v1",
            content=gear_snapshot_summary(snapshot),
            dependency_revisions=self.dependencies(),
            release_status="validated",
            source={"sourceRevision": "prepared-index-other-release"},
        )
        other_prepared = CandidateGearAuthorityIndex(snapshot, other)
        with self.assertRaises(GearReleaseIntegrityError):
            gear_release_tool.selection_intent_from_template(
                self.template(),
                gear_release_id=gear["releaseId"],
                season_revision=gear["seasonRevision"],
                level=90,
                gear_snapshot=snapshot,
                prepared_index=other_prepared,
            )
        with self.assertRaises(GearReleaseIntegrityError):
            gear_release_tool.community_template_import_evidence_from_template(
                self.template(),
                gear_release_id=gear["releaseId"],
                gear_snapshot=snapshot,
                prepared_index=other_prepared,
            )

    def test_prepared_index_resolves_missing_variant_key_without_rescanning_item_variants(self):
        from server import gear_release_tool
        from server.gear_release_store import CandidateGearAuthorityIndex, gear_snapshot_summary

        snapshot = self.snapshot()
        profile_url = "https://raider.io/characters/cn/example"
        snapshot["variants"][0].update({
            "sourceType": "observed_profile",
            "simcOptions": {"ilevel": "289"},
            "payload": {
                "profileUrl": profile_url,
                "resolvedStats": {"intellect": 100},
            },
        })
        template = self.template()
        template["gearItems"][0].pop("variantKey")
        template["gearItems"][0].pop("gem_id", None)
        template["gearItems"][0].pop("enchant_id", None)
        template["gearItems"][0]["observedProfileRefs"] = [{
            "profileUrl": profile_url,
        }]
        gear = gear_release.build_release(
            release_kind="gear",
            season_revision="season-17",
            schema_revision="gear-release-v1",
            content=gear_snapshot_summary(snapshot),
            dependency_revisions=self.dependencies(),
            release_status="validated",
            source={"sourceRevision": "prepared-observed-index-test"},
        )
        prepared = CandidateGearAuthorityIndex(snapshot, gear)

        class NoRescan(list):
            def __iter__(self):
                raise AssertionError("prepared observed lookup must not rescan variants")

        prepared.variants_by_item["item-a"] = NoRescan(
            prepared.variants_by_item["item-a"]
        )
        intent = gear_release_tool.selection_intent_from_template(
            template,
            gear_release_id=gear["releaseId"],
            season_revision=gear["seasonRevision"],
            level=90,
            gear_snapshot=snapshot,
            prepared_index=prepared,
        )

        self.assertEqual(intent["slots"]["head"]["variantKey"], "variant-a")

    def test_community_candidate_exact_progression_requires_governed_bonus_evidence(self):
        from server import gear_release_tool
        from server.gear_release_store import CandidateGearAuthorityIndex, gear_snapshot_summary

        snapshot = self.snapshot()
        gear = gear_release.build_release(
            release_kind="gear",
            season_revision=self.CURRENT_SEASON_REVISION,
            schema_revision="gear-release-v1",
            content=gear_snapshot_summary(snapshot),
            dependency_revisions=self.dependencies(),
            release_status="validated",
            source={"sourceRevision": "exact-progression-test"},
        )
        prepared = CandidateGearAuthorityIndex(snapshot, gear)
        candidate = gear_release_tool._template_candidate(
            self.template(),
            gear_release_id=gear["releaseId"],
            season_revision=gear["seasonRevision"],
            level=90,
            gear_snapshot=snapshot,
            capability_revision=self.dependencies()["capabilityRevision"],
            prepared_index=prepared,
        )

        blocked = gear_release_tool.community_candidate_exact_progression_problems(
            candidate,
            gear_snapshot=snapshot,
            gear_release_descriptor=gear,
            prepared_index=prepared,
        )

        self.assertEqual(
            [problem["code"] for problem in blocked],
            ["TRACK_AUTHORITY_EXACT_TRACK_EVIDENCE_MISSING"],
        )
        self.assertEqual(
            blocked[0]["path"],
            "candidate.selectionIntent.slots.head",
        )

        exact_snapshot = self.exact_progression_snapshot()
        exact_gear = gear_release.build_release(
            release_kind="gear",
            season_revision=self.CURRENT_SEASON_REVISION,
            schema_revision="gear-release-v1",
            content=gear_snapshot_summary(exact_snapshot),
            dependency_revisions=self.dependencies(),
            release_status="validated",
            source={"sourceRevision": "exact-progression-test"},
        )
        exact_prepared = CandidateGearAuthorityIndex(exact_snapshot, exact_gear)
        exact_candidate = gear_release_tool._template_candidate(
            self.template(),
            gear_release_id=exact_gear["releaseId"],
            season_revision=exact_gear["seasonRevision"],
            level=90,
            gear_snapshot=exact_snapshot,
            capability_revision=self.dependencies()["capabilityRevision"],
            prepared_index=exact_prepared,
        )
        self.assertEqual(
            gear_release_tool.community_candidate_exact_progression_problems(
                exact_candidate,
                gear_snapshot=exact_snapshot,
                gear_release_descriptor=exact_gear,
                prepared_index=exact_prepared,
            ),
            [],
        )

    def test_s2_community_candidate_exact_progression_uses_bound_track_authority(self):
        from server import gear_release_tool
        from server.gear_release_store import CandidateGearAuthorityIndex, gear_snapshot_summary

        season_revision = "season-midnight-season-2:fixture"
        track_revision = "midnight-season-2-track-authority-v1"
        gear_rule_revision = "midnight-season-2-gear-rule-v1"
        snapshot = self.exact_progression_snapshot()
        snapshot["variants"][0]["payload"].update({
            "truthScope": "community_observed",
            "officialFactStatus": "UNVERIFIED",
            "membershipKind": "imported_exact",
            "editable": False,
        })
        gear = gear_release.build_release(
            release_kind="gear",
            season_revision=season_revision,
            schema_revision="gear-release-v1",
            content=gear_snapshot_summary(snapshot),
            dependency_revisions={
                **self.dependencies(),
                "gearRuleRevision": gear_rule_revision,
                "trackAuthorityRevision": track_revision,
            },
            release_status="validated",
            source={"sourceRevision": "s2-community-exact-progression-test"},
        )
        gear.update({
            "gearRuleRevision": gear_rule_revision,
            "trackAuthorityRevision": track_revision,
            "trackRecords": [{
                "recordKey": "s2_myth_1",
                "publicTrackKey": "myth",
                "progressionKind": "upgrade_track",
                "rank": 1,
                "maxRank": 8,
                "itemLevel": 289,
                "eligibleSourceTypes": ["observed_profile"],
                "eligibleSlots": ["head"],
                "sourceRefs": ["fixture:s2-track"],
                "bonusIds": ["13335"],
                "evidenceStatus": "verified",
                "seasonRevision": season_revision,
                "gearRuleRevision": gear_rule_revision,
            }],
        })
        prepared = CandidateGearAuthorityIndex(snapshot, gear)
        candidate = gear_release_tool._template_candidate(
            self.template(),
            gear_release_id=gear["releaseId"],
            season_revision=season_revision,
            level=90,
            gear_snapshot=snapshot,
            capability_revision=self.dependencies()["capabilityRevision"],
            prepared_index=prepared,
        )

        self.assertEqual(
            gear_release_tool.community_candidate_exact_progression_problems(
                candidate,
                gear_snapshot=snapshot,
                gear_release_descriptor=gear,
                prepared_index=prepared,
            ),
            [],
        )

    def test_community_hero_projection_skips_exact_progression_rejection(self):
        from server import gear_release_tool
        from server.gear_release_store import gear_snapshot_summary
        from server.gear_release_tool import build_legacy_community_release

        snapshot = self.exact_progression_snapshot()
        gear = gear_release.build_release(
            release_kind="gear",
            season_revision=self.CURRENT_SEASON_REVISION,
            schema_revision="gear-release-v1",
            content=gear_snapshot_summary(snapshot),
            dependency_revisions=self.dependencies(),
            release_status="validated",
            source={"sourceRevision": "exact-progression-election-test"},
        )
        top = self.template("arcane-top")
        top["sourceIdentity"] = "raiderio:cn|realm|arcane-top"
        top["payload"]["sourceIdentity"] = top["sourceIdentity"]
        fallback = self.template("arcane-fallback")
        fallback["sourceIdentity"] = "raiderio:cn|realm|arcane-fallback"
        fallback["payload"]["sourceIdentity"] = fallback["sourceIdentity"]
        other_hero = self.template("arcane-other-hero")
        other_hero["sourceIdentity"] = "raiderio:cn|realm|arcane-other"
        other_hero["payload"]["sourceIdentity"] = other_hero["sourceIdentity"]
        talents = [
            {"id": "talent-top", "classKey": "mage", "specKey": "arcane", "heroKey": "sunfury", "scenarioKey": "mythic_plus", "sourceKey": "raiderio", "sourceIdentity": top["sourceIdentity"], "talentCandidateRank": 1},
            {"id": "talent-fallback", "classKey": "mage", "specKey": "arcane", "heroKey": "sunfury", "scenarioKey": "mythic_plus", "sourceKey": "raiderio", "sourceIdentity": fallback["sourceIdentity"], "talentCandidateRank": 2},
            {"id": "talent-other", "classKey": "mage", "specKey": "arcane", "heroKey": "spellslinger", "scenarioKey": "mythic_plus", "sourceKey": "raiderio", "sourceIdentity": other_hero["sourceIdentity"], "talentCandidateRank": 1},
        ]
        store = FakeReleaseStore(
            snapshot,
            [top, fallback, other_hero],
            talents,
        )
        exact_validator = gear_release_tool.community_candidate_exact_progression_problems

        def reject_top(candidate, **kwargs):
            if candidate.get("candidateId") == "arcane-top":
                return [{
                    "code": "TRACK_AUTHORITY_EXACT_TRACK_EVIDENCE_MISSING",
                    "path": "candidate.selectionIntent.slots.head",
                    "message": "Exact track evidence is missing.",
                }]
            return exact_validator(candidate, **kwargs)

        with patch.object(
            gear_release_tool,
            "community_candidate_exact_progression_problems",
            side_effect=reject_top,
        ):
            result = build_legacy_community_release(
                store,
                gear_release_descriptor=gear,
                gear_snapshot=snapshot,
                dependency_revisions=self.dependencies(),
                expected_specs=[("mage", "arcane")],
                now="2026-07-11T06:00:00+00:00",
                resolver_for_spec=lambda *_args: self.verified_result(gear["releaseId"]),
            )

        winners = {
            row["payload"]["heroKey"]: row["payload"]
            for row in result["rows"]
            if row["role"] == "winner"
        }
        self.assertEqual(
            winners["sunfury"]["gearSourceTemplateId"],
            "arcane-fallback",
        )
        rejection = next(
            row
            for row in result["election"]["rejected"]
            if row.get("candidateId") == "talent-top"
        )
        self.assertEqual(
            rejection["problems"][0]["code"],
            "TRACK_AUTHORITY_EXACT_TRACK_EVIDENCE_MISSING",
        )

    def test_community_projection_reserves_exact_valid_active_winner_for_its_hero(self):
        from server import gear_release_tool
        from server.gear_release_store import (
            CandidateGearAuthorityIndex,
            gear_snapshot_summary,
        )
        from server.gear_release_tool import build_legacy_community_release

        snapshot = self.exact_progression_snapshot()
        invalid_item = copy.deepcopy(snapshot["items"][0])
        invalid_item.update({
            "itemId": "item-b",
            "name": "B",
        })
        snapshot["items"].append(invalid_item)
        invalid_source = copy.deepcopy(snapshot["sources"][0])
        invalid_source.update({
            "sourceId": "source-b",
            "itemId": "item-b",
        })
        snapshot["sources"].append(invalid_source)
        invalid_variant = copy.deepcopy(snapshot["variants"][0])
        invalid_variant.update({
            "variantId": "variant-b-id",
            "itemId": "item-b",
            "variantKey": "variant-b",
            "simcOptions": {"ilevel": "289"},
        })
        snapshot["variants"].append(invalid_variant)
        gear = gear_release.build_release(
            release_kind="gear",
            season_revision=self.CURRENT_SEASON_REVISION,
            schema_revision="gear-release-v1",
            content=gear_snapshot_summary(snapshot),
            dependency_revisions=self.dependencies(),
            release_status="validated",
            source={"sourceRevision": "active-reservation-test"},
        )
        reserved = self.template("reserved-sunfury")
        reserved["sourceIdentity"] = "raiderio:cn|realm|reserved"
        reserved["payload"]["sourceIdentity"] = reserved["sourceIdentity"]
        invalid_active = self.template("invalid-spellslinger")
        invalid_active["sourceIdentity"] = "raiderio:cn|realm|invalid"
        invalid_active["payload"]["sourceIdentity"] = invalid_active[
            "sourceIdentity"
        ]
        invalid_active["gearItems"][0].update({
            "itemId": "item-b",
            "variantKey": "variant-b",
        })
        fallback = self.template("fallback-spellslinger")
        fallback["sourceIdentity"] = "raiderio:cn|realm|fallback"
        fallback["payload"]["sourceIdentity"] = fallback["sourceIdentity"]
        prepared = CandidateGearAuthorityIndex(snapshot, gear)

        def active_winner(template, hero_key):
            candidate = gear_release_tool._template_candidate(
                template,
                gear_release_id=gear["releaseId"],
                season_revision=gear["seasonRevision"],
                level=90,
                gear_snapshot=snapshot,
                capability_revision=self.dependencies()[
                    "capabilityRevision"
                ],
                prepared_index=prepared,
            )
            return {
                "templateId": (
                    "community-gear:mage:arcane:"
                    f"{hero_key}:{template['templateId']}"
                ),
                "classKey": "mage",
                "specKey": "arcane",
                "role": "winner",
                "sourceKey": candidate["sourceKey"],
                "selectionIntent": candidate["selectionIntent"],
                "importEvidence": candidate["importEvidence"],
                "payload": {
                    "heroKey": hero_key,
                    "gearSourceTemplateId": template["templateId"],
                },
            }

        active_community_id = "community-release:active-reservation"
        active_pair = {
            "communityRelease": {
                "releaseId": active_community_id,
                "schemaRevision": "community-release-v2",
                "validatedAgainstReleaseId": gear["releaseId"],
            },
            "winners": [
                active_winner(invalid_active, "spellslinger"),
                active_winner(reserved, "sunfury"),
            ],
        }

        class ActiveReleaseStore(FakeReleaseStore):
            def load_active_manifest_binding(self):
                return {
                    "formalActiveManifest": True,
                    "manifest": {
                        "gearCatalogReleaseId": gear["releaseId"],
                        "communityTemplateReleaseId": active_community_id,
                    },
                }

            def load_community_release(
                self,
                gear_release_id,
                community_release_id,
            ):
                self.active_pair_request = (
                    gear_release_id,
                    community_release_id,
                )
                return copy.deepcopy(active_pair)

        talents = [
            {"id": "talent-spell-reserved", "classKey": "mage", "specKey": "arcane", "heroKey": "spellslinger", "scenarioKey": "mythic_plus", "sourceKey": "raiderio", "sourceIdentity": reserved["sourceIdentity"], "talentCandidateRank": 1},
            {"id": "talent-spell-fallback", "classKey": "mage", "specKey": "arcane", "heroKey": "spellslinger", "scenarioKey": "mythic_plus", "sourceKey": "raiderio", "sourceIdentity": fallback["sourceIdentity"], "talentCandidateRank": 2},
            {"id": "talent-sun-reserved", "classKey": "mage", "specKey": "arcane", "heroKey": "sunfury", "scenarioKey": "mythic_plus", "sourceKey": "raiderio", "sourceIdentity": reserved["sourceIdentity"], "talentCandidateRank": 1},
        ]
        store = ActiveReleaseStore(
            snapshot,
            [reserved, invalid_active, fallback],
            talents,
        )

        result = build_legacy_community_release(
            store,
            gear_release_descriptor=gear,
            gear_snapshot=snapshot,
            dependency_revisions=self.dependencies(),
            expected_specs=[("mage", "arcane")],
            now="2026-07-11T06:00:00+00:00",
            resolver_for_spec=lambda *_args: self.verified_result(
                gear["releaseId"]
            ),
        )

        winners = {
            row["payload"]["heroKey"]: row["payload"]
            for row in result["rows"]
        }
        self.assertEqual(
            winners["spellslinger"]["gearSourceTemplateId"],
            "fallback-spellslinger",
        )
        self.assertEqual(
            winners["sunfury"]["gearSourceTemplateId"],
            "reserved-sunfury",
        )
        self.assertEqual(
            winners["sunfury"]["gearProjectionMode"],
            "gear_fallback",
        )
        self.assertEqual(result["gate"]["activeWinnerReservationCount"], 1)
        self.assertEqual(result["gate"]["activeWinnerCarryForwardCount"], 1)

    def test_community_release_projects_two_hero_slots_from_talent_candidates(self):
        from server import gear_release_tool
        from server.gear_release_store import gear_snapshot_summary
        from server.gear_release_tool import build_legacy_community_release

        snapshot = self.exact_progression_snapshot()
        gear = gear_release.build_release(
            release_kind="gear",
            season_revision=self.CURRENT_SEASON_REVISION,
            schema_revision="gear-release-v1",
            content=gear_snapshot_summary(snapshot),
            dependency_revisions=self.dependencies(),
            release_status="validated",
            source={"sourceRevision": "hero-projection-test"},
        )
        frost_top = self.template("frost-top", "season_recommendation")
        frost_top["sourceIdentity"] = "raiderio:cn|realm|frost-top"
        frost_top["payload"]["sourceIdentity"] = frost_top["sourceIdentity"]
        frost_fallback = self.template("frost-fallback")
        frost_fallback["sourceIdentity"] = "raiderio:cn|realm|frost-fallback"
        frost_fallback["payload"]["sourceIdentity"] = frost_fallback["sourceIdentity"]
        spell = self.template("spellslinger")
        spell["sourceIdentity"] = "raiderio:cn|realm|spellslinger"
        spell["payload"]["sourceIdentity"] = spell["sourceIdentity"]
        spell["gearItems"][0]["displayName"] = "Hydrated full winner item"
        talent_candidates = [
            {"id": "talent-frost-top", "classKey": "mage", "specKey": "arcane", "heroKey": "sunfury", "scenarioKey": "mythic_plus", "sourceKey": "raiderio", "sourceIdentity": frost_top["sourceIdentity"], "talentCandidateRank": 1},
            {"id": "talent-frost-fallback", "classKey": "mage", "specKey": "arcane", "heroKey": "sunfury", "scenarioKey": "mythic_plus", "sourceKey": "raiderio", "sourceIdentity": frost_fallback["sourceIdentity"], "talentCandidateRank": 2},
            {"id": "talent-spell", "classKey": "mage", "specKey": "arcane", "heroKey": "spellslinger", "scenarioKey": "mythic_plus", "sourceKey": "raiderio", "sourceIdentity": spell["sourceIdentity"], "talentCandidateRank": 1},
        ]
        store = FakeReleaseStore(snapshot, [frost_top, frost_fallback, spell], talent_candidates)
        store.builder_templates = copy.deepcopy(store.templates)
        for template in store.builder_templates:
            for item in template.get("gearItems") or []:
                item.pop("displayName", None)

        with patch.object(
            gear_release_tool,
            "_template_candidate",
            wraps=gear_release_tool._template_candidate,
        ) as candidate_builder:
            result = build_legacy_community_release(
                store,
                gear_release_descriptor=gear,
                gear_snapshot=snapshot,
                dependency_revisions=self.dependencies(),
                expected_specs=[("mage", "arcane")],
                now="2026-07-11T06:00:00+00:00",
                resolver_for_spec=lambda *_args: self.verified_result(gear["releaseId"]),
            )

        winners = {row["payload"]["heroKey"]: row for row in result["rows"] if row["role"] == "winner"}
        self.assertEqual(candidate_builder.call_count, 2)
        self.assertEqual(result["release"]["schemaRevision"], "community-release-v2")
        self.assertEqual(set(winners), {"sunfury", "spellslinger"})
        self.assertEqual(winners["sunfury"]["payload"]["talentWinnerId"], "talent-frost-top")
        self.assertEqual(winners["sunfury"]["payload"]["gearProjectionMode"], "gear_fallback")
        self.assertEqual(winners["sunfury"]["payload"]["gearSourceTemplateId"], "frost-fallback")
        self.assertEqual(winners["spellslinger"]["payload"]["gearProjectionMode"], "talent_winner")
        self.assertEqual(
            winners["spellslinger"]["payload"]["gearItems"][0]["displayName"],
            "Hydrated full winner item",
        )
        self.assertEqual(
            store.requested_template_ids,
            ["frost-fallback", "spellslinger"],
        )
        self.assertEqual(
            winners["spellslinger"]["payload"]["importEvidence"]["schemaRevision"],
            "community-template-import-evidence-v3",
        )
        self.assertEqual(result["gate"]["winnerHeroSlotCount"], 2)
        rank_one_rejection = next(
            row for row in result["election"]["rejected"]
            if row.get("candidateId") == "talent-frost-top"
        )
        self.assertEqual(rank_one_rejection["sourceIdentity"], frost_top["sourceIdentity"])
        self.assertEqual(
            rank_one_rejection["sourceUrl"],
            "https://raider.io/characters/cn/realm/frost-top",
        )
        self.assertEqual(rank_one_rejection["problems"][0]["code"], "GEAR_CAPTURE_MISSING")
        rank_one_gate_evidence = result["gate"]["rankOneRejections"][0]
        self.assertEqual(
            rank_one_gate_evidence,
            {
                "candidateId": "talent-frost-top",
                "sourceIdentity": frost_top["sourceIdentity"],
                "sourceUrl": "https://raider.io/characters/cn/realm/frost-top",
                "problems": [{"code": "GEAR_CAPTURE_MISSING"}],
            },
        )
        sealed = store.community_seals[0][2]
        self.assertEqual(sealed["gate_result"]["rankOneRejections"], [rank_one_gate_evidence])
        self.assertEqual(sealed["event"]["gate"]["rankOneRejections"], [rank_one_gate_evidence])

    def test_community_hero_projection_uses_the_matching_spec_when_one_player_has_multiple_templates(self):
        from server.gear_release_store import gear_snapshot_summary
        from server.gear_release_tool import build_legacy_community_release

        snapshot = self.exact_progression_snapshot()
        gear = gear_release.build_release(
            release_kind="gear",
            season_revision=self.CURRENT_SEASON_REVISION,
            schema_revision="gear-release-v1",
            content=gear_snapshot_summary(snapshot),
            dependency_revisions=self.dependencies(),
            release_status="validated",
            source={"sourceRevision": "hero-projection-spec-match-test"},
        )
        identity = "raiderio:cn|realm|multi-spec-player"
        arcane = self.template("arcane-template")
        arcane["sourceIdentity"] = identity
        arcane["payload"]["sourceIdentity"] = identity
        frost = self.template("frost-template")
        frost["classKey"] = "mage"
        frost["specKey"] = "frost"
        frost["sourceIdentity"] = identity
        frost["payload"]["sourceIdentity"] = identity
        frost["updatedAt"] = "2026-07-12T00:00:00+00:00"
        spellslinger = self.template("spellslinger-template")
        spellslinger["sourceIdentity"] = "raiderio:cn|realm|spellslinger-player"
        spellslinger["payload"]["sourceIdentity"] = spellslinger["sourceIdentity"]
        talents = [
            {"id": "talent-sunfury", "classKey": "mage", "specKey": "arcane", "heroKey": "sunfury", "scenarioKey": "mythic_plus", "sourceKey": "raiderio", "sourceIdentity": identity, "talentCandidateRank": 1},
            {"id": "talent-spellslinger", "classKey": "mage", "specKey": "arcane", "heroKey": "spellslinger", "scenarioKey": "mythic_plus", "sourceKey": "raiderio", "sourceIdentity": spellslinger["sourceIdentity"], "talentCandidateRank": 1},
        ]
        store = FakeReleaseStore(snapshot, [frost, arcane, spellslinger], talents)

        result = build_legacy_community_release(
            store,
            gear_release_descriptor=gear,
            gear_snapshot=snapshot,
            dependency_revisions=self.dependencies(),
            expected_specs=[("mage", "arcane")],
            now="2026-07-11T06:00:00+00:00",
            resolver_for_spec=lambda *_args: self.verified_result(gear["releaseId"]),
        )

        winners = {row["payload"]["heroKey"]: row for row in result["rows"] if row["role"] == "winner"}
        self.assertEqual(winners["sunfury"]["payload"]["gearSourceTemplateId"], "arcane-template")

    def test_community_hero_projection_re_elects_a_real_player_within_the_same_spec_when_hero_source_is_not_importable(self):
        from server.gear_release_store import gear_snapshot_summary
        from server.gear_release_tool import build_legacy_community_release

        snapshot = self.exact_progression_snapshot()
        gear = gear_release.build_release(
            release_kind="gear",
            season_revision=self.CURRENT_SEASON_REVISION,
            schema_revision="gear-release-v1",
            content=gear_snapshot_summary(snapshot),
            dependency_revisions=self.dependencies(),
            release_status="validated",
            source={"sourceRevision": "hero-projection-spec-re-election-test"},
        )
        fallback = self.template("arcane-spec-fallback")
        fallback["sourceIdentity"] = "raiderio:cn|realm|arcane-fallback"
        fallback["payload"]["sourceIdentity"] = fallback["sourceIdentity"]
        spellslinger = self.template("spellslinger-template")
        spellslinger["sourceIdentity"] = "raiderio:cn|realm|spellslinger-player"
        spellslinger["payload"]["sourceIdentity"] = spellslinger["sourceIdentity"]
        talents = [
            {"id": "wcl-sunfury", "classKey": "mage", "specKey": "arcane", "heroKey": "sunfury", "scenarioKey": "mythic_plus", "sourceKey": "warcraftlogs", "sourceIdentity": "", "talentCandidateRank": 1},
            {"id": "rio-spellslinger", "classKey": "mage", "specKey": "arcane", "heroKey": "spellslinger", "scenarioKey": "mythic_plus", "sourceKey": "raiderio", "sourceIdentity": spellslinger["sourceIdentity"], "talentCandidateRank": 1},
        ]
        store = FakeReleaseStore(snapshot, [fallback, spellslinger], talents)

        result = build_legacy_community_release(
            store,
            gear_release_descriptor=gear,
            gear_snapshot=snapshot,
            dependency_revisions=self.dependencies(),
            expected_specs=[("mage", "arcane")],
            now="2026-07-11T06:00:00+00:00",
            resolver_for_spec=lambda *_args: self.verified_result(gear["releaseId"]),
        )

        winners = {row["payload"]["heroKey"]: row for row in result["rows"] if row["role"] == "winner"}
        sunfury = winners["sunfury"]["payload"]
        self.assertEqual(sunfury["gearSourceTemplateId"], "arcane-spec-fallback")
        self.assertEqual(sunfury["talentWinnerId"], "wcl-sunfury")
        self.assertEqual(sunfury["gearProjectionMode"], "gear_fallback")
        self.assertEqual(sunfury["gearProjectionFallbackScope"], "class_spec")

    def test_build_legacy_all_cli_emits_rank_one_rejection_gate_evidence(self):
        from server import gear_release_tool, simulator_payload

        evidence = {
            "candidateId": "talent-frost-top",
            "sourceIdentity": "raiderio:cn|realm|frost-top",
            "sourceUrl": "https://raider.io/characters/cn/realm/frost-top",
            "problems": [{"code": "GEAR_CAPTURE_MISSING"}],
        }
        gear_result = {
            "release": {"releaseId": "gear-release:test"},
            "snapshot": {},
            "gate": {"status": "validated"},
            "seal": {"status": "inserted"},
        }
        community_result = {
            "release": {"releaseId": "community-release:test"},
            "gate": {
                "status": "validated",
                "rankOneRejectionCount": 1,
                "rankOneRejections": [evidence],
                "rankOneRejectionTruncatedCount": 0,
            },
            "seal": {"status": "inserted"},
        }
        output = io.StringIO()
        with patch.object(gear_release_tool, "_store_from_environment", return_value=object()), patch.object(
            gear_release_tool,
            "runtime_dependency_revisions",
            return_value=self.dependencies(),
        ), patch.object(
            simulator_payload,
            "simc_binary",
            return_value="/tmp/simc",
        ), patch.object(
            gear_release_tool,
            "load_simc_socket_bonus_minimums",
            return_value={},
        ), patch.object(
            gear_release_tool,
            "build_legacy_gear_release",
            return_value=gear_result,
        ) as build_gear, patch.object(
            gear_release_tool,
            "build_legacy_community_release",
            return_value=community_result,
        ) as build_community, redirect_stdout(output):
            status = gear_release_tool.main([
                "build-legacy-all",
                "--season-revision", "season-17",
                "--simc-runtime-revision", "simc-r1",
                "--source-revision", "phase0-unblock-r1",
            ])

        self.assertEqual(status, 0)
        rendered = json.loads(output.getvalue())
        self.assertEqual(rendered["community"]["gate"]["rankOneRejections"], [evidence])
        self.assertEqual(
            build_gear.call_args.kwargs["source_revision"],
            "phase0-unblock-r1",
        )
        self.assertEqual(
            build_community.call_args.kwargs["source_revision"],
            "phase0-unblock-r1",
        )

    def test_build_legacy_community_cli_uses_one_exact_inactive_gear_release(self):
        from server import gear_release_tool

        gear = {
            "releaseId": "gear-release:exact",
            "releaseKind": "gear",
            "releaseStatus": "validated",
            "seasonRevision": "season-17",
            "dependencyRevisions": self.dependencies(),
        }
        snapshot = self.snapshot()

        class Store:
            def get_release(self, release_id):
                return gear if release_id == gear["releaseId"] else {}

            def snapshot_gear_release_for_community_builder(self, release_id):
                return snapshot if release_id == gear["releaseId"] else {}

        community_result = {
            "release": {"releaseId": "community-release:exact"},
            "gate": {
                "status": "validated",
                "winnerSpecCount": 40,
                "winnerHeroSlotCount": 80,
            },
            "seal": {"status": "inserted"},
        }
        output = io.StringIO()
        with patch.object(
            gear_release_tool,
            "_store_from_environment",
            return_value=Store(),
        ), patch.object(
            gear_release_tool,
            "build_legacy_community_release",
            return_value=community_result,
        ) as build_community, redirect_stdout(output):
            status = gear_release_tool.main(
                [
                    "build-legacy-community",
                    "--gear-release-id",
                    "gear-release:exact",
                    "--simc-runtime-revision",
                    "simc-r1",
                    "--source-revision",
                    "phase0-unblock-r1",
                ]
            )

        self.assertEqual(status, 0)
        self.assertEqual(
            json.loads(output.getvalue())["community"]["release"]["releaseId"],
            "community-release:exact",
        )
        self.assertEqual(
            build_community.call_args.kwargs["gear_release_descriptor"],
            gear,
        )
        self.assertIs(
            build_community.call_args.kwargs["gear_snapshot"],
            snapshot,
        )
        self.assertEqual(
            build_community.call_args.kwargs["source_revision"],
            "phase0-unblock-r1",
        )

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

    def test_shadow_command_writes_only_bounded_aggregate_evidence(self):
        from server import gear_release_tool

        class ShadowStore:
            def gear_authority_cache_metrics(self):
                return {
                    "entryCount": 2,
                    "byteSize": 512,
                    "maxEntries": 32,
                    "maxBytes": 4096,
                }

            def shadow_read_statement_metrics(self):
                return {
                    "total": 7,
                    "transactionControl": 2,
                    "readQueries": 5,
                    "writeStatements": 0,
                }

        shadow_result = {
            "schemaRevision": "gear-release-shadow-execution-v2",
            "status": "blocked",
            "gearReleaseId": "gear-release:a",
            "communityReleaseId": "community-release:a",
            "baselineMode": "formal_gear_only_candidate_preview",
            "candidatePreview": True,
            "publicReadCount": 40,
            "importReadCount": 80,
            "blockers": [
                {
                    "code": "PROFILE_PARITY_MISMATCH",
                    "path": "specs.mage.frost",
                    "detail": "Candidate Profile differs from preview.",
                },
                {
                    "code": "PROFILE_PARITY_MISMATCH",
                    "path": "specs.mage.arcane",
                    "detail": "Candidate Profile differs from preview.",
                },
            ],
            "specResults": [
                {
                    "classKey": "mage",
                    "specKey": "frost",
                    "status": "blocked",
                    "heroSlotResults": [
                        {
                            "templateId": "private-template-identity",
                            "status": "blocked",
                        }
                    ],
                }
            ],
            "report": {
                "status": "blocked",
                "expectedSpecCount": 40,
                "expectedHeroSlotCount": 80,
                "candidateWinnerCount": 80,
            },
            "performance": {"totalDurationMs": 1234},
        }

        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "shadow-evidence.json"
            output = io.StringIO()
            with patch.object(
                gear_release_tool,
                "_shadow_store_from_environment",
                return_value=ShadowStore(),
            ), patch.object(
                gear_release_tool.gear_release_shadow,
                "run_release_shadow",
                return_value=shadow_result,
            ), redirect_stdout(output):
                status = gear_release_tool.main([
                    "shadow",
                    "--gear-release-id",
                    "gear-release:a",
                    "--community-release-id",
                    "community-release:a",
                    "--simc-runtime-revision",
                    "simc-r1",
                    "--output-file",
                    str(output_path),
                ])

            rendered = json.loads(output.getvalue())
            saved = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(status, 2)
        self.assertEqual(rendered, saved)
        self.assertEqual(rendered["specResultCount"], 1)
        self.assertEqual(rendered["passingSpecCount"], 0)
        self.assertEqual(
            rendered["blockerCodes"],
            {"PROFILE_PARITY_MISMATCH": 2},
        )
        self.assertEqual(len(rendered["blockerSamples"]), 2)
        self.assertEqual(rendered["databaseStatements"]["writeStatements"], 0)
        self.assertNotIn("specResults", rendered)
        self.assertNotIn("private-template-identity", json.dumps(rendered))

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

    def test_seal_manifest_v2_does_not_move_the_retail_pointer(self):
        from server import gear_release_tool
        from server.gear_release_store import (
            community_rows_summary,
            gear_snapshot_summary,
        )

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
        community = gear_release.build_release(
            release_kind="community",
            season_revision="season-17",
            schema_revision="community-release-v1",
            content=community_rows_summary([{
                "templateId": "template-a",
                "classKey": "mage",
                "specKey": "arcane",
                "role": "winner",
                "electionRank": 1,
                "sourceKey": "observed",
            }]),
            dependency_revisions=self.dependencies(),
            release_status="validated",
            source={"sourceRevision": "legacy-import-r0"},
            validated_against_release_id=gear["releaseId"],
        )
        catalog_revision = "gear-catalog:sha256:" + ("a" * 64)
        exact_revision = (
            "gear-exact-registry:sha256:" + ("b" * 64)
        )

        class SealStore:
            def get_release(self, release_id):
                return {
                    gear["releaseId"]: gear,
                    community["releaseId"]: community,
                }.get(release_id, {})

            def seal_manifest(self, manifest):
                self.manifest = manifest
                return {
                    "status": "inserted",
                    "manifestRevision": manifest["manifestRevision"],
                }

            def seal_manifest_and_compare_and_swap_pointer(self, *_args, **_kwargs):
                raise AssertionError("candidate seal must not move the pointer")

        store = SealStore()
        output = io.StringIO()
        with patch.object(
            gear_release_tool,
            "_store_from_environment",
            return_value=store,
        ), patch.object(
            gear_release_tool,
            "runtime_dependency_revisions",
            return_value=self.dependencies(),
        ), redirect_stdout(output):
            status = gear_release_tool.main([
                "seal-manifest",
                "--season-revision", "season-17",
                "--simc-runtime-revision", "simc-r1",
                "--gear-release-id", gear["releaseId"],
                "--community-release-id", community["releaseId"],
                "--talent-catalog-revision", "talent-r1",
                "--gear-catalog-revision", catalog_revision,
                "--gear-exact-registry-revision", exact_revision,
                "--rollback-manifest-revision", "manifest-v1",
            ])

        self.assertEqual(status, 0)
        self.assertEqual(
            store.manifest["schemaRevision"],
            "active-season-manifest-v2",
        )
        self.assertEqual(
            store.manifest["gearCatalogRevision"],
            catalog_revision,
        )
        self.assertEqual(
            store.manifest["gearExactRegistryRevision"],
            exact_revision,
        )
        self.assertEqual(
            json.loads(output.getvalue())["manifestRevision"],
            store.manifest["manifestRevision"],
        )

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
