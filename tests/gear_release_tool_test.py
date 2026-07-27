import copy
import hashlib
import io
import json
import subprocess
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from server import gear_release
from tests.gear_resolver_test import build_midnight_mage_resolver_fixture


def canonical_digest(value):
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class FakeReleaseStore:
    def __init__(self, gear_snapshot, templates=None, talent_candidates=None):
        self.gear_snapshot = gear_snapshot
        self.templates = templates or []
        self.talent_candidates = talent_candidates or []
        self.community_hero_projection_enabled = talent_candidates is not None
        self.gear_seals = []
        self.community_seals = []
        self.requested_specs = []
        self.evidence_bundles = []

    def snapshot_staging_gear(self):
        return copy.deepcopy(self.gear_snapshot)

    def snapshot_staging_community_templates(self, expected_specs):
        self.requested_specs = list(expected_specs)
        return copy.deepcopy(self.templates)

    def snapshot_staging_community_talent_candidates(self, expected_specs):
        self.requested_specs = list(expected_specs)
        return copy.deepcopy(self.talent_candidates)

    def seal_gear_release(self, release, snapshot, **kwargs):
        self.gear_seals.append((copy.deepcopy(release), copy.deepcopy(snapshot), copy.deepcopy(kwargs)))
        return {"status": "inserted", "releaseId": release["releaseId"]}

    def seal_community_release(self, release, rows, **kwargs):
        self.community_seals.append((copy.deepcopy(release), copy.deepcopy(rows), copy.deepcopy(kwargs)))
        return {"status": "inserted", "releaseId": release["releaseId"]}

    def persist_gear_evidence_bundle(
        self,
        *,
        artifacts,
        observations,
        facts,
        gaps,
        now,
    ):
        self.evidence_bundles.append(
            {
                "artifacts": copy.deepcopy(artifacts),
                "observations": copy.deepcopy(observations),
                "facts": copy.deepcopy(facts),
                "gaps": copy.deepcopy(gaps),
                "now": now,
            }
        )
        return {
            "artifacts": {
                "persisted": len(artifacts),
                "identities": sorted(
                    row["artifactId"] for row in artifacts
                ),
                "identityDigest": canonical_digest(sorted(
                    row["artifactId"] for row in artifacts
                )),
            },
            "observations": {
                "persisted": len(observations),
                "identities": sorted(
                    row["observationId"] for row in observations
                ),
                "identityDigest": canonical_digest(sorted(
                    row["observationId"] for row in observations
                )),
            },
            "facts": {
                "persisted": len(facts),
                "identities": sorted(
                    (
                        row["factKey"],
                        row["factValueHash"],
                        row["provenanceHash"],
                    )
                    for row in facts
                ),
                "identityDigest": canonical_digest(sorted(
                    (
                        row["factKey"],
                        row["factValueHash"],
                        row["provenanceHash"],
                    )
                    for row in facts
                )),
            },
            "gaps": {
                "inserted": len(gaps),
                "reused": 0,
                "requested": len(gaps),
                "identities": sorted(
                    row["gapKey"] for row in gaps
                ),
                "identityDigest": canonical_digest(sorted(
                    row["gapKey"] for row in gaps
                )),
            },
        }


def socket_probe_evidence(minimums=None, revision="simc-fixture-r1"):
    return {
        "schemaRevision": "simc-socket-bonus-evidence-v1",
        "status": "verified",
        "sourceType": "simc_bonus_probe",
        "sourceIdentity": "simulationcraft:show_bonus_ids",
        "sourceRevision": revision,
        "sourceScope": "exact_variant",
        "minimums": copy.deepcopy(minimums or {"9300": 1}),
    }


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
                    "sourceIdentity": f"battle-net:item:{gem_id}",
                    "sourceRevision": "battle-net-item-2026-07-14",
                },
            },
            "item_class": {"id": 3, "name": "Gem"},
            "preview_item": preview_item,
        },
        "updatedAt": "2026-07-14T05:00:00+00:00",
    }


def build_midnight_mage_release_fixture(*, canonical_consumer=True):
    resolver_fixture = build_midnight_mage_resolver_fixture(
        8,
        include_reference_enhancements=True,
        canonical_consumer=canonical_consumer,
    )
    authority = resolver_fixture["authorityContext"]
    reference = resolver_fixture["referenceContract"]
    intent = resolver_fixture["intent"]
    items = []
    sources = []
    variants = []

    def allowed_enhancement_rules(owner, slot):
        def exact_slot_options(field):
            if (
                field == "allowedGemOptionIds"
                and (
                    (owner.get("capabilityFacts") or {})
                    .get("socket", {})
                    .get("status")
                    == "verified"
                )
            ):
                return sorted(
                    option_id
                    for option_id, option in authority[
                        "optionsById"
                    ].items()
                    if option.get("optionType") == "gem"
                )
            return sorted(
                option_id
                for option_id in owner.get(field) or []
                if slot
                in (
                    authority["optionsById"].get(option_id, {}).get(
                        "applicableSlots"
                    )
                    or []
                )
            )

        rules = [
            {
                "capabilityFactType": "socket_count",
                "optionIds": exact_slot_options("allowedGemOptionIds"),
                "slot": slot,
            },
            {
                "capabilityFactType": "enchant_capability",
                "optionIds": exact_slot_options(
                    "allowedEnchantOptionIds"
                ),
                "slot": slot,
            },
            {
                "capabilityFactType": "embellishment_capability",
                "optionIds": sorted(
                    {
                        *exact_slot_options(
                            "allowedEmbellishmentOptionIds"
                        ),
                        *exact_slot_options("allowedCraftedOptionIds"),
                    }
                ),
                "slot": slot,
            },
        ]
        return [rule for rule in rules if rule["optionIds"]]

    for item_id, item in authority["itemsById"].items():
        slot = (item.get("allowedSlots") or [""])[0]
        equipment_identity = {
            "inventoryType": item.get("inventoryType") or slot,
            "armorType": item.get("armorType") or "",
            "weaponType": item.get("weaponType") or "",
            "handedness": item.get("handedness") or "",
        }
        if slot == "main_hand":
            equipment_identity.update({
                "inventoryType": "weapon",
                "weaponType": "Staff",
                "handedness": "two_hand",
            })
        items.append({
            "itemId": item_id,
            "name": item.get("displayName") or item_id,
            "slot": slot,
            "sourceStatus": "verified",
            "payload": {
                "_metadata": {
                    "iconUrl": f"https://render.worldofwarcraft.com/icons/{item_id}.jpg",
                    "gameAsset": {
                        "source": "blizzard",
                        "status": "verified",
                        "sourceIdentity": f"battle-net:item:{item_id}",
                        "sourceRevision": "battle-net-item-2026-07-14",
                    },
                },
                "canonicalEvidence": {
                    "sourceType": "season_rule",
                    "sourceIdentity": f"midnight-item-capability:{item_id}",
                    "sourceRevision": "season-17-active",
                    "sourceScope": "base_item",
                    "status": "verified",
                    "claims": [
                        "enchant_capability",
                        "embellishment_capability",
                        "allowed_enhancement_options",
                    ],
                },
                "allowedEnhancementRules": allowed_enhancement_rules(
                    item,
                    slot,
                ),
                "equipmentUniqueness": (
                    {
                        "isUnique": True,
                        "groupId": item["uniqueGroupId"],
                        "limit": item["uniqueLimit"],
                    }
                    if item.get("uniqueGroupId")
                    and item.get("uniqueLimit")
                    else {"isUnique": False}
                ),
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
                **equipment_identity,
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
            "sourceRevision": "simc-midnight-fixture-r1",
            "resolvedStats": copy.deepcopy(variant.get("resolvedStats") or {}),
            "capabilityOverrides": copy.deepcopy(variant.get("capabilityOverrides") or {}),
            "canonicalEvidence": {
                "sourceType": "season_rule",
                "sourceIdentity": f"midnight-capability:{variant_key}",
                "sourceRevision": "season-17-active",
                "sourceScope": "exact_variant",
                "status": "verified",
                "claims": [
                    "slot_compatibility",
                    "socket_count",
                    "enchant_capability",
                    "embellishment_capability",
                    "allowed_enhancement_options",
                ],
            },
            "allowedEnhancementRules": allowed_enhancement_rules(
                variant,
                slot,
            ),
            "identityEvidence": {
                "sourceType": "battle_net_item",
                "sourceIdentity": f"battle-net:item:{variant['itemId']}",
                "sourceRevision": "battle-net-item-2026-07-14",
                "sourceScope": "exact_variant",
                "status": "verified",
            },
            "statEvidence": {
                "sourceType": "simc_item_probe",
                "sourceIdentity": f"simc-item:{variant_key}",
                "sourceRevision": "simc-midnight-fixture-r1",
                "sourceScope": "exact_variant",
                "status": "verified",
                "claims": [
                    "static_stats",
                    "variant_track",
                    "executable_item_options",
                    "enhancement_echo",
                ],
            },
        }
        if variant.get("enhancementManagement"):
            payload["enhancementManagement"] = copy.deepcopy(
                variant["enhancementManagement"]
            )
        raw_enchant = str((variant.get("simcOptions") or {}).get("enchant_id") or "").strip()
        raw_embellishment = str(
            (variant.get("simcOptions") or {}).get("embellishment") or ""
        ).strip()
        item_level = int(variant.get("itemLevel") or 0)
        if raw_enchant or raw_embellishment:
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
            "difficultyKey": "observed",
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
                "optionEvidence": {
                    "sourceType": "simc_item_probe",
                    "sourceIdentity": f"simc-option:{option_key}",
                    "sourceRevision": "simc-midnight-fixture-r1",
                    "sourceScope": "option",
                    "status": "verified",
                },
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
    def test_full_release_defaults_to_the_low_memory_evidence_batch_budget(self):
        from server import gear_release_tool

        self.assertEqual(gear_release_tool._FULL_RELEASE_EVIDENCE_BATCH_SIZE, 32)

    def test_option_batch_does_not_materialize_unrelated_catalog_rows(self):
        """An option-only evidence batch must not retain the full gear catalog."""
        from server.gear_release_tool import _compile_release_gear_evidence

        class UnrelatedCatalog:
            def __iter__(self):
                raise AssertionError("option evidence must not read this catalog")

        option = build_midnight_mage_release_fixture()["snapshot"]["options"][0]
        compiled = _compile_release_gear_evidence(
            {
                "items": UnrelatedCatalog(),
                "sources": UnrelatedCatalog(),
                "variants": UnrelatedCatalog(),
                "options": [option],
            },
            season_revision="midnight-season-1",
            source_revision="legacy-import-r0",
            captured_at="2026-07-27T00:00:00+00:00",
            socket_bonus_minimums={
                "9300": {
                    "minimumTotal": 1,
                    "sourceRevision": "simc-fixture-r1",
                },
            },
            socket_bonus_evidence=socket_probe_evidence(),
            categories=("options",),
        )

        self.assertEqual(
            [
                (fact["subjectKey"], fact["factType"], fact["status"])
                for fact in compiled["facts"]
            ],
            [
                (
                    "option:embellishment-arcanoweave_lining",
                    "enhancement_option",
                    "verified",
                )
            ],
        )

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
            "items": [{"itemId": "item-a", "name": "A", "slot": "head", "sourceStatus": "verified", "payload": {"_metadata": {"iconUrl": "https://render.worldofwarcraft.com/icons/item-a.jpg", "gameAsset": {"source": "blizzard", "status": "verified", "sourceIdentity": "battle-net:item:item-a", "sourceRevision": "battle-net-item-2026-07-11"}}, "canonicalEvidence": {"sourceType": "season_rule", "sourceIdentity": "season-rule:item-a", "sourceRevision": "season-rule-fixture-r1", "sourceScope": "base_item", "status": "verified", "claims": ["enchant_capability", "embellishment_capability"]}}, "updatedAt": "2026-07-11T05:00:00+00:00"}],
            "sources": [{"sourceId": "source-a", "itemId": "item-a", "sourceType": "observed_profile", "sourceKey": "profile:a", "payload": {"status": "verified"}, "updatedAt": "2026-07-11T05:00:00+00:00"}],
            "variants": [{"variantId": "variant-a-id", "itemId": "item-a", "variantKey": "variant-a", "slot": "head", "sourceType": "observed_profile", "itemLevel": 289, "simcOptions": {"ilevel": "289"}, "status": "verified", "blockers": [], "payload": {"sourceRevision": "simc-item-2026-07-11", "resolvedStats": {"intellect": 100}, "canonicalEvidence": {"sourceType": "season_rule", "sourceIdentity": "season-rule:variant-a", "sourceRevision": "season-17", "sourceScope": "exact_variant", "status": "verified", "claims": ["slot_compatibility"]}, "statEvidence": {"sourceType": "simc_item_probe", "sourceIdentity": "simc-item:variant-a", "sourceRevision": "simc-item-2026-07-11", "sourceScope": "exact_variant", "status": "verified", "claims": ["static_stats", "variant_track"]}}, "updatedAt": "2026-07-11T05:00:00+00:00"}],
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
        for variant in fixture["snapshot"]["variants"]:
            payload = (
                variant["payload"]
                if isinstance(variant.get("payload"), dict)
                else {}
            )
            if isinstance(payload.get("resolvedStats"), dict):
                payload["statSource"] = "simulationcraft"
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
            socket_bonus_minimums=socket_probe_evidence(),
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
            "primary_stat_gem",
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
            socket_bonus_minimums=socket_probe_evidence(),
        )

        release = result["release"]
        self.assertEqual(release["releaseKind"], "gear")
        self.assertEqual(release["releaseStatus"], "validated")
        self.assertEqual(release["source"]["sourceRevision"], "legacy-import-r0")
        self.assertEqual(result["seal"]["status"], "inserted")
        self.assertEqual(len(store.gear_seals), 1)
        self.assertNotIn("manifest", result)
        self.assertNotIn("pointer", result)

    def test_prepare_staging_gear_release_compiles_requested_facts_in_one_batch(self):
        from server import gear_fact_compiler
        from server.gear_release_tool import prepare_staging_gear_release

        with patch(
            "server.gear_release_tool.gear_fact_compiler.compile_facts_by_subject",
            wraps=gear_fact_compiler.compile_facts_by_subject,
        ) as compile_batch:
            prepare_staging_gear_release(
                FakeReleaseStore(self.snapshot()),
                season_revision="season-17",
                dependency_revisions=self.dependencies(),
                socket_bonus_minimums=socket_probe_evidence(),
            )

        self.assertEqual(compile_batch.call_count, 1)

    def test_prepare_streaming_batches_preserve_cross_batch_option_authority(self):
        """A bounded build may not lose an option fact needed by a later rule."""

        from server.gear_release_tool import prepare_staging_gear_release

        snapshot = self.snapshot()
        item_payload = snapshot["items"][0]["payload"]
        item_payload["baseCapabilities"] = {
            "socketCount": 1,
            "canEnchant": True,
            "canEmbellish": False,
        }
        variant_payload = snapshot["variants"][0]["payload"]
        variant_payload["capabilityOverrides"] = {
            "socketCount": 1,
            "canEnchant": True,
            "canEmbellish": False,
        }
        snapshot["variants"][0]["simcOptions"]["bonus_id"] = "9300"
        variant_payload["canonicalEvidence"]["claims"] = [
            "slot_compatibility",
            "socket_count",
            "enchant_capability",
            "embellishment_capability",
            "allowed_enhancement_options",
        ]
        variant_payload["allowedEnhancementRules"] = [
            {
                "capabilityFactType": "socket_count",
                "optionIds": ["gem-a"],
                "slot": "head",
            }
        ]
        snapshot["options"] = [
            {
                "optionId": "gem-a",
                "variantId": "variant-a-id",
                "optionKey": "gem-a",
                "optionType": "gem",
                "name": "Gem A",
                "applicableSlots": ["head"],
                "simcOptions": {"gem_id": "240000"},
                "status": "verified",
                "isVisible": True,
                "payload": {
                    "evidenceSource": "simulationcraft",
                    "optionEvidence": {
                        "sourceType": "simc_item_probe",
                        "sourceIdentity": "simc-option:gem-a",
                        "sourceRevision": "simc-options-2026-07-11",
                        "sourceScope": "option",
                        "status": "verified",
                    },
                },
                "updatedAt": "2026-07-11T05:00:00+00:00",
            }
        ]
        for option_key in ("gem-b", "gem-c"):
            option = copy.deepcopy(snapshot["options"][0])
            option.update({
                "optionId": option_key,
                "optionKey": option_key,
                "name": option_key.upper(),
                "simcOptions": {"gem_id": str(240000 + len(snapshot["options"]))},
            })
            option["payload"]["optionEvidence"]["sourceIdentity"] = (
                "simc-option:" + option_key
            )
            snapshot["options"].append(option)
        now = "2026-07-27T06:00:00+00:00"
        baseline = prepare_staging_gear_release(
            FakeReleaseStore(snapshot),
            season_revision="season-17",
            dependency_revisions=self.dependencies(),
            socket_bonus_minimums=socket_probe_evidence(),
            evidence_now=now,
        )
        streamed_store = FakeReleaseStore(snapshot)
        from server import gear_fact_compiler

        with patch(
            "server.gear_release_tool.gear_fact_compiler.compile_facts_by_subject",
            wraps=gear_fact_compiler.compile_facts_by_subject,
        ) as compile_batches:
            streamed = prepare_staging_gear_release(
                streamed_store,
                season_revision="season-17",
                dependency_revisions=self.dependencies(),
                socket_bonus_minimums=socket_probe_evidence(),
                evidence_now=now,
                evidence_batch_size=1,
            )

        self.assertEqual(streamed["snapshot"], baseline["snapshot"])
        self.assertEqual(streamed["release"], baseline["release"])
        variant_facts = {
            fact["factType"]: fact
            for fact in streamed["snapshot"]["variants"][0]["payload"][
                "canonicalFacts"
            ]
        }
        self.assertEqual(
            variant_facts["allowed_enhancement_options"]["status"],
            "verified",
        )
        self.assertEqual(
            variant_facts["allowed_enhancement_options"]["value"],
            ["gem-a"],
        )
        persisted_fact_identities = {
            fact["factKey"]
            for bundle in streamed_store.evidence_bundles
            for fact in bundle["facts"]
        }
        self.assertEqual(
            persisted_fact_identities,
            {
                identity[0]
                for identity in baseline["gate"]["evidenceCompilation"]["facts"][
                    "identities"
                ]
            },
        )
        option_artifact_ids = [
            row["artifactId"]
            for bundle in streamed_store.evidence_bundles
            for row in bundle["artifacts"]
            if "enhancementOption" in row["payload"]
        ]
        option_observation_ids = [
            row["observationId"]
            for bundle in streamed_store.evidence_bundles
            for row in bundle["observations"]
            if row["subjectKey"].startswith("option:")
        ]
        self.assertEqual(len(option_artifact_ids), len(set(option_artifact_ids)))
        self.assertEqual(
            len(option_observation_ids), len(set(option_observation_ids))
        )
        non_option_batches = [
            call.kwargs
            for call in compile_batches.call_args_list
            if not all(
                subject_key.startswith("option:")
                for subject_key in call.kwargs["fact_types_by_subject"]
            )
        ]
        self.assertTrue(non_option_batches)
        self.assertEqual(
            len(
                {
                    id(batch["precompiled_facts_by_subject_fact"])
                    for batch in non_option_batches
                }
            ),
            1,
        )
        for batch in non_option_batches:
            self.assertFalse(
                any(
                    row["subjectKey"].startswith("option:")
                    for row in batch["observations"]
                )
            )
            self.assertFalse(
                any(
                    "enhancementOption" in row["payload"]
                    for row in batch["artifacts"]
                )
            )
            self.assertEqual(
                set(batch["precompiled_facts_by_subject_fact"]),
                {
                    ("option:gem-a", "enhancement_option"),
                    ("option:gem-b", "enhancement_option"),
                    ("option:gem-c", "enhancement_option"),
                },
            )

    def test_prepare_staging_gear_release_materializes_socket_facts_before_hash(self):
        from server.gear_release_store import gear_snapshot_summary
        from server.gear_release_tool import (
            _compile_release_gear_evidence,
            prepare_staging_gear_release,
        )

        snapshot = self.snapshot()
        snapshot["variants"][0]["simcOptions"]["bonus_id"] = "9300"
        raw_summary = gear_snapshot_summary(snapshot)

        try:
            result = prepare_staging_gear_release(
                FakeReleaseStore(snapshot),
                season_revision="midnight-season-1",
                dependency_revisions=self.dependencies(),
                socket_bonus_minimums=socket_probe_evidence({"9300": 2}),
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

    def test_prepare_staging_gear_release_seals_safe_canonical_fact_projection(self):
        from server.gear_release_tool import (
            _compile_release_gear_evidence,
            prepare_staging_gear_release,
        )

        snapshot = self.snapshot()
        snapshot["items"][0]["payload"]["baseCapabilities"] = {
            "socketCount": 1,
            "canEnchant": True,
            "canEmbellish": False,
        }
        snapshot["variants"][0]["payload"]["capabilityOverrides"] = {
            "socketCount": 1,
            "canEnchant": True,
            "canEmbellish": False,
        }
        snapshot["options"] = [
            {
                "optionId": "gem-a",
                "variantId": "variant-a-id",
                "optionKey": "gem-a",
                "optionType": "gem",
                "name": "Gem A",
                "applicableSlots": ["head"],
                "simcOptions": {"gem_id": "240000"},
                "status": "verified",
                "isVisible": True,
                "payload": {
                    "evidenceSource": "simulationcraft",
                    "optionEvidence": {
                        "sourceType": "simc_item_probe",
                        "sourceIdentity": "simc-option:gem-a",
                        "sourceRevision": "simc-options-2026-07-11",
                        "sourceScope": "option",
                        "status": "verified",
                    },
                },
                "updatedAt": "2026-07-11T05:00:00+00:00",
            }
        ]
        store = FakeReleaseStore(snapshot)

        first = prepare_staging_gear_release(
            store,
            season_revision="midnight-season-1",
            dependency_revisions=self.dependencies(),
            socket_bonus_minimums=socket_probe_evidence(),
            evidence_now="2026-07-26T02:00:00+00:00",
        )
        second = prepare_staging_gear_release(
            store,
            season_revision="midnight-season-1",
            dependency_revisions=self.dependencies(),
            socket_bonus_minimums=socket_probe_evidence(),
            evidence_now="2026-07-26T03:00:00+00:00",
        )

        for category in ("items", "variants", "options"):
            facts = first["snapshot"][category][0]["payload"]["canonicalFacts"]
            self.assertTrue(facts, category)
            self.assertTrue(
                any(fact["status"] == "verified" for fact in facts),
                category,
            )
            for fact in facts:
                self.assertIn(
                    fact["status"],
                    {
                        "verified",
                        "unresolved_missing",
                        "unresolved_conflict",
                    },
                )
                self.assertIn("factKey", fact)
                self.assertIn("factValueHash", fact)
                self.assertIn("provenanceHash", fact)
                self.assertNotIn("artifactId", fact)
                self.assertNotIn("payload", fact)
                self.assertLessEqual(len(fact["observationRefs"]), 8)
        encoded = json.dumps(first["snapshot"], sort_keys=True)
        self.assertNotIn("gear-evidence-artifact-v1", encoded)
        source_evidence = first["release"]["source"]["sourceEvidence"]
        self.assertTrue(source_evidence["compilerPolicyDigest"].startswith("sha256:"))
        self.assertTrue(source_evidence["canonicalFactDigest"].startswith("sha256:"))
        self.assertEqual(first["release"]["contentHash"], second["release"]["contentHash"])
        self.assertEqual(first["release"]["releaseId"], second["release"]["releaseId"])
        self.assertEqual(
            first["release"]["source"]["sourceEvidence"],
            second["release"]["source"]["sourceEvidence"],
        )
        self.assertEqual(len(store.evidence_bundles), 2)
        for bundle in store.evidence_bundles:
            artifact_ids = {row["artifactId"] for row in bundle["artifacts"]}
            self.assertTrue(artifact_ids)
            self.assertTrue(
                all(row["artifactId"] in artifact_ids for row in bundle["observations"])
            )
            observation_ids = {
                row["observationId"] for row in bundle["observations"]
            }
            self.assertTrue(
                all(
                    set(row["observationRefs"]).issubset(observation_ids)
                    for row in bundle["facts"]
                )
            )

    def test_seal_requires_declared_canonical_fact_tuples_in_registry(self):
        from server.gear_release_store import (
            GearReleaseIntegrityError,
            GearReleaseStore,
        )
        from server.gear_release_tool import prepare_staging_gear_release

        prepared = prepare_staging_gear_release(
            FakeReleaseStore(self.snapshot()),
            season_revision="midnight-season-1",
            dependency_revisions=self.dependencies(),
            socket_bonus_minimums=socket_probe_evidence(),
            evidence_now="2026-07-26T02:00:00+00:00",
        )

        class FactCursor:
            def __init__(self, rows):
                self.rows = rows
                self.params = None

            def execute(self, _statement, params):
                self.params = params

            def fetchall(self):
                return list(self.rows)

        projected_facts = {
            fact["factKey"]: fact
            for category in ("items", "variants", "options")
            for row in prepared["snapshot"][category]
            for fact in row["payload"]["canonicalFacts"]
        }
        persisted_rows = [
            (
                fact["factKey"],
                fact["schemaRevision"],
                fact["subjectKey"],
                fact["factType"],
                fact["value"],
                fact["status"],
                fact["observationRefs"],
                fact["factValueHash"],
                fact["provenanceHash"],
                fact["compilerRuleRevision"],
            )
            for fact in projected_facts.values()
        ]
        persisted = FactCursor(persisted_rows)
        GearReleaseStore._verify_projected_canonical_facts(
            persisted,
            prepared["release"],
            prepared["snapshot"],
        )
        self.assertTrue(persisted.params)

        with self.assertRaisesRegex(
            GearReleaseIntegrityError,
            "not persisted",
        ):
            GearReleaseStore._verify_projected_canonical_facts(
                FactCursor([]),
                prepared["release"],
                prepared["snapshot"],
            )

        forged_release = copy.deepcopy(prepared["release"])
        forged_release["source"]["sourceEvidence"][
            "canonicalFactDigest"
        ] = "sha256:" + ("0" * 64)
        with self.assertRaisesRegex(
            GearReleaseIntegrityError,
            "digest does not match",
        ):
            GearReleaseStore._verify_projected_canonical_facts(
                FactCursor(persisted_rows),
                forged_release,
                prepared["snapshot"],
            )

        forged_snapshot = copy.deepcopy(prepared["snapshot"])
        forged_fact = next(
            fact
            for category in ("items", "variants", "options")
            for row in forged_snapshot[category]
            for fact in row["payload"]["canonicalFacts"]
            if fact["status"] == "verified"
        )
        forged_fact["value"] = {"forged": True}
        with self.assertRaisesRegex(
            GearReleaseIntegrityError,
            "hashes do not match",
        ):
            GearReleaseStore._verify_projected_canonical_facts(
                FactCursor(persisted_rows),
                prepared["release"],
                forged_snapshot,
            )

        missing_digest_release = copy.deepcopy(prepared["release"])
        missing_digest_release["source"]["sourceEvidence"].pop(
            "canonicalFactDigest"
        )
        with self.assertRaisesRegex(
            GearReleaseIntegrityError,
            "require a canonical Fact digest",
        ):
            GearReleaseStore._verify_projected_canonical_facts(
                FactCursor(persisted_rows),
                missing_digest_release,
                prepared["snapshot"],
            )

    def test_legacy_shadow_reuses_its_owned_materialized_snapshot(self):
        from server import gear_release_tool
        from server import gear_socket_authority

        materialize_calls = []
        project_calls = []
        real_materialize = gear_socket_authority.materialize_gear_socket_facts
        real_project = gear_release_tool._project_socket_facts_into_release_payloads

        def materialize(snapshot, **kwargs):
            materialize_calls.append(kwargs)
            return real_materialize(snapshot, **kwargs)

        def project(snapshot, **kwargs):
            project_calls.append(kwargs)
            return real_project(snapshot, **kwargs)

        with patch.object(
            gear_socket_authority,
            "materialize_gear_socket_facts",
            side_effect=materialize,
        ), patch.object(
            gear_release_tool,
            "_project_socket_facts_into_release_payloads",
            side_effect=project,
        ):
            legacy = gear_release_tool._legacy_shadow_snapshot(
                self.snapshot(),
                season_revision="midnight-season-1",
                capability_revision=self.dependencies()["capabilityRevision"],
                socket_bonus_evidence=socket_probe_evidence(),
            )

        self.assertTrue(legacy["items"])
        self.assertEqual(materialize_calls, [{
            "season_revision": "midnight-season-1",
            "socket_bonus_minimums": {
                "9300": {
                    "minimumTotal": 1,
                    "sourceRevision": "simc-fixture-r1",
                },
            },
            "in_place": True,
        }])
        self.assertEqual(project_calls, [{"in_place": True}])

    def test_streaming_shadow_batch_matches_the_full_legacy_shadow(self):
        from server import gear_fact_shadow
        from server import gear_release_tool

        raw_snapshot = self.snapshot()
        evidence = socket_probe_evidence()
        normalized_minimums = {
            bonus_id: {
                "minimumTotal": minimum,
                "sourceRevision": evidence["sourceRevision"],
            }
            for bonus_id, minimum in evidence["minimums"].items()
        }
        full_legacy = gear_release_tool._legacy_shadow_snapshot(
            raw_snapshot,
            season_revision="midnight-season-1",
            capability_revision=self.dependencies()["capabilityRevision"],
            socket_bonus_evidence=evidence,
        )

        for category, _offset, rows, compiled in (
            gear_release_tool._stream_release_evidence_batches(
                raw_snapshot,
                season_revision="midnight-season-1",
                source_revision="legacy-import-r0",
                captured_at="2026-07-27T00:00:00+00:00",
                socket_bonus_minimums=normalized_minimums,
                socket_bonus_evidence=evidence,
                batch_size=1,
            )
        ):
            with self.subTest(category=category):
                batch_legacy = (
                    gear_release_tool._legacy_shadow_snapshot_for_evidence_batch(
                        raw_snapshot,
                        category=category,
                        rows=rows,
                        season_revision="midnight-season-1",
                        capability_revision=self.dependencies()["capabilityRevision"],
                        socket_bonus_evidence=evidence,
                    )
                )
                expected = gear_fact_shadow.compare_legacy_and_canonical(
                    full_legacy,
                    compiled["facts"],
                    expected_fact_types_by_subject=(
                        compiled["expectedFactTypesBySubject"]
                    ),
                    include_comparisons=False,
                )
                actual = gear_fact_shadow.compare_legacy_and_canonical(
                    batch_legacy,
                    compiled["facts"],
                    expected_fact_types_by_subject=(
                        compiled["expectedFactTypesBySubject"]
                    ),
                    include_comparisons=False,
                )
                self.assertEqual(actual, expected)

    def test_streaming_variant_shadow_keeps_gem_items_and_shared_options(self):
        from server import gear_fact_shadow
        from server import gear_release_tool
        from server.gear_socket_authority import CAPABILITY_REVISION

        raw_snapshot = build_midnight_mage_release_fixture()["snapshot"]
        evidence = socket_probe_evidence()
        normalized_minimums = {
            bonus_id: {
                "minimumTotal": minimum,
                "sourceRevision": evidence["sourceRevision"],
            }
            for bonus_id, minimum in evidence["minimums"].items()
        }
        full_legacy = gear_release_tool._legacy_shadow_snapshot(
            raw_snapshot,
            season_revision="season-17-active",
            capability_revision=CAPABILITY_REVISION,
            socket_bonus_evidence=evidence,
        )
        variant_batch = next(
            batch
            for batch in gear_release_tool._stream_release_evidence_batches(
                raw_snapshot,
                season_revision="season-17-active",
                source_revision="legacy-import-r0",
                captured_at="2026-07-27T00:00:00+00:00",
                socket_bonus_minimums=normalized_minimums,
                socket_bonus_evidence=evidence,
                batch_size=128,
            )
            if batch[0] == "variants"
        )
        category, _offset, rows, compiled = variant_batch
        batch_legacy = gear_release_tool._legacy_shadow_snapshot_for_evidence_batch(
            raw_snapshot,
            category=category,
            rows=rows,
            season_revision="season-17-active",
            capability_revision=CAPABILITY_REVISION,
            socket_bonus_evidence=evidence,
        )

        self.assertEqual(
            gear_fact_shadow.compare_legacy_and_canonical(
                batch_legacy,
                compiled["facts"],
                expected_fact_types_by_subject=(
                    compiled["expectedFactTypesBySubject"]
                ),
                include_comparisons=False,
            ),
            gear_fact_shadow.compare_legacy_and_canonical(
                full_legacy,
                compiled["facts"],
                expected_fact_types_by_subject=(
                    compiled["expectedFactTypesBySubject"]
                ),
                include_comparisons=False,
            ),
        )

    def test_store_seal_requires_complete_authoritative_canonical_gate(self):
        from server.gear_release_store import (
            GearReleaseIntegrityError,
            GearReleaseStore,
        )
        from server.gear_release_tool import (
            _legacy_shadow_snapshot,
            prepare_staging_gear_release,
        )

        raw_snapshot = self.snapshot()
        prepared = prepare_staging_gear_release(
            FakeReleaseStore(raw_snapshot),
            season_revision="midnight-season-1",
            dependency_revisions=self.dependencies(),
            socket_bonus_minimums=socket_probe_evidence(),
            evidence_now="2026-07-26T02:00:00+00:00",
        )
        validator = getattr(
            GearReleaseStore,
            "_validate_canonical_gear_gate",
            None,
        )
        self.assertTrue(
            callable(validator),
            "GearReleaseStore seal must own the canonical gate",
        )
        legacy_snapshot = _legacy_shadow_snapshot(
            raw_snapshot,
            season_revision="midnight-season-1",
            capability_revision=self.dependencies()[
                "capabilityRevision"
            ],
            socket_bonus_evidence=socket_probe_evidence(),
        )
        validator(
            prepared["release"],
            prepared["snapshot"],
            prepared["gate"],
            legacy_snapshot,
        )

        cases = []
        missing_shadow = copy.deepcopy(prepared["gate"])
        missing_shadow.pop("factShadow")
        cases.append(("shadow", prepared["release"], prepared["snapshot"], missing_shadow))
        blocked_shadow = copy.deepcopy(prepared["gate"])
        blocked_shadow["factShadow"]["blockers"] = [{
            "code": "CANONICAL_FACT_REGRESSION",
        }]
        cases.append(("shadow blocker", prepared["release"], prepared["snapshot"], blocked_shadow))
        missing_receipt = copy.deepcopy(prepared["gate"])
        missing_receipt.pop("evidencePersistence")
        cases.append(("receipt", prepared["release"], prepared["snapshot"], missing_receipt))
        missing_policy_digest = copy.deepcopy(prepared["release"])
        missing_policy_digest["source"]["sourceEvidence"].pop(
            "compilerPolicyDigest"
        )
        cases.append(("policy digest", missing_policy_digest, prepared["snapshot"], prepared["gate"]))
        missing_fact_digest = copy.deepcopy(prepared["release"])
        missing_fact_digest["source"]["sourceEvidence"].pop(
            "canonicalFactDigest"
        )
        cases.append(("fact digest", missing_fact_digest, prepared["snapshot"], prepared["gate"]))
        forged_policy_digest = copy.deepcopy(prepared["release"])
        forged_policy_digest["source"]["sourceEvidence"][
            "compilerPolicyDigest"
        ] = "not-a-digest"
        cases.append(("forged policy digest", forged_policy_digest, prepared["snapshot"], prepared["gate"]))
        empty_facts = copy.deepcopy(prepared["snapshot"])
        empty_facts["items"][0]["payload"]["canonicalFacts"] = []
        cases.append(("canonical facts", prepared["release"], empty_facts, prepared["gate"]))

        for label, release, snapshot, gate in cases:
            with self.subTest(label=label):
                with self.assertRaises(GearReleaseIntegrityError):
                    validator(
                        release,
                        snapshot,
                        gate,
                        legacy_snapshot,
                    )

    def test_store_gate_rejects_tampered_compact_streaming_receipt(self):
        from server.gear_release_store import (
            GearReleaseIntegrityError,
            GearReleaseStore,
        )
        from server.gear_release_tool import (
            _legacy_shadow_snapshot,
            prepare_staging_gear_release,
        )

        raw_snapshot = self.snapshot()
        prepared = prepare_staging_gear_release(
            FakeReleaseStore(raw_snapshot),
            season_revision="season-17",
            dependency_revisions=self.dependencies(),
            socket_bonus_minimums=socket_probe_evidence(),
            evidence_now="2026-07-27T06:00:00+00:00",
            evidence_batch_size=1,
        )
        legacy_snapshot = _legacy_shadow_snapshot(
            raw_snapshot,
            season_revision="season-17",
            capability_revision=self.dependencies()["capabilityRevision"],
            socket_bonus_evidence=socket_probe_evidence(),
        )

        GearReleaseStore._validate_canonical_gear_gate(
            prepared["release"],
            prepared["snapshot"],
            prepared["gate"],
            legacy_snapshot,
        )

        tampered_gate = copy.deepcopy(prepared["gate"])
        tampered_gate["evidencePersistence"]["facts"][
            "sequenceDigest"
        ] = "sha256:" + ("0" * 64)
        with self.assertRaisesRegex(
            GearReleaseIntegrityError,
            "streaming evidence persistence receipt",
        ):
            GearReleaseStore._validate_canonical_gear_gate(
                prepared["release"],
                prepared["snapshot"],
                tampered_gate,
                legacy_snapshot,
            )

    def test_release_store_persists_registry_owners_before_gap_enqueue(self):
        from server.gear_release_store import GearReleaseStore

        events = []

        class EvidenceStore:
            def __init__(self, connection_factory):
                self.connection_factory = connection_factory

            def persist_artifact(self, row):
                events.append(("artifact", row["artifactId"]))

            def persist_observation(self, row):
                events.append(("observation", row["observationId"]))

            def persist_fact(self, row):
                events.append(("fact", row["factKey"]))

        class GapStore:
            def __init__(self, connection_factory):
                self.connection_factory = connection_factory

            def enqueue_gaps(self, rows, *, now):
                events.append(("gaps", len(rows), now))
                return {"inserted": len(rows), "reused": 0}

        with (
            patch(
                "server.gear_evidence_store.GearEvidenceStore",
                EvidenceStore,
            ),
            patch(
                "server.gear_evidence_gap_store.GearEvidenceGapStore",
                GapStore,
            ),
        ):
            result = GearReleaseStore(lambda: None).persist_gear_evidence_bundle(
                artifacts=[{"artifactId": "artifact-a"}],
                observations=[{"observationId": "observation-a"}],
                facts=[{"factKey": "fact-a"}],
                gaps=[{"gapKey": "gap-a"}],
                now="2026-07-26T02:00:00+00:00",
            )

        self.assertEqual(
            events,
            [
                ("artifact", "artifact-a"),
                ("observation", "observation-a"),
                ("fact", "fact-a"),
                ("gaps", 1, "2026-07-26T02:00:00+00:00"),
            ],
        )
        self.assertEqual(result["gaps"]["inserted"], 1)
        self.assertEqual(result["gaps"]["reused"], 0)
        self.assertEqual(result["gaps"]["requested"], 1)
        self.assertTrue(
            result["gaps"]["identityDigest"].startswith("sha256:")
        )

    def test_unresolved_fact_enqueues_only_bounded_gap_requirement(self):
        from server.gear_release_tool import prepare_staging_gear_release

        snapshot = self.snapshot()
        snapshot["options"] = [
            {
                "optionId": "incomplete-option",
                "variantId": "variant-a-id",
                "optionKey": "incomplete-option",
                "optionType": "gem",
                "name": "Incomplete",
                "applicableSlots": ["head"],
                "simcOptions": {},
                "status": "blocked",
                "isVisible": False,
                "payload": {},
                "updatedAt": "2026-07-11T05:00:00+00:00",
            }
        ]
        store = FakeReleaseStore(snapshot)

        prepared = prepare_staging_gear_release(
            store,
            season_revision="midnight-season-1",
            dependency_revisions=self.dependencies(),
            socket_bonus_minimums=socket_probe_evidence(),
            evidence_now="2026-07-26T02:00:00+00:00",
        )

        canonical_facts = prepared["snapshot"]["options"][0]["payload"][
            "canonicalFacts"
        ]
        self.assertEqual(len(canonical_facts), 1)
        self.assertEqual(canonical_facts[0]["status"], "unresolved_missing")
        self.assertIsNone(canonical_facts[0]["value"])
        self.assertGreaterEqual(prepared["gate"]["evidenceGapCount"], 1)
        gap = next(
            row
            for row in store.evidence_bundles[0]["gaps"]
            if row["missingRequirement"]["subjectKey"]
            == "option:incomplete-option"
        )
        self.assertEqual(
            set(gap),
            {
                "schemaRevision",
                "gapKey",
                "factKey",
                "status",
                "problemCode",
                "missingRequirement",
                "attempt",
                "nextAttemptAt",
            },
        )
        self.assertEqual(
            set(gap["missingRequirement"]),
            {
                "subjectKey",
                "factType",
                "seasonRevision",
                "compilerRuleRevision",
                "requiredInputKey",
                "sourceType",
                "sourceScope",
            },
        )
        self.assertEqual(gap["missingRequirement"]["sourceType"], "battle_net_item")
        self.assertEqual(gap["missingRequirement"]["sourceScope"], "option")
        self.assertNotIn("value", json.dumps(gap, sort_keys=True).lower())

    def test_unattributed_legacy_shapes_cannot_establish_fact_provenance(self):
        from server.gear_release_tool import prepare_staging_gear_release

        snapshot = self.snapshot()
        snapshot["items"][0]["payload"].pop("canonicalEvidence", None)
        snapshot["items"][0]["payload"]["baseCapabilities"] = {
            "canEnchant": True,
        }
        variant_payload = snapshot["variants"][0]["payload"]
        variant_payload.pop("canonicalEvidence", None)
        variant_payload.pop("statEvidence", None)
        variant_payload["capabilityOverrides"] = {"canEnchant": True}
        snapshot["options"] = [{
            "optionId": "shape-only-option",
            "variantId": "variant-a-id",
            "optionKey": "shape-only-option",
            "optionType": "enchant",
            "name": "Shape only",
            "applicableSlots": ["head"],
            "simcOptions": {"enchant_id": "9999"},
            "status": "verified",
            "isVisible": True,
            "payload": {},
            "updatedAt": "2026-07-11T05:00:00+00:00",
        }]

        prepared = prepare_staging_gear_release(
            FakeReleaseStore(snapshot),
            season_revision="season-17",
            dependency_revisions=self.dependencies(),
            socket_bonus_minimums=socket_probe_evidence(),
            evidence_now="2026-07-26T02:00:00+00:00",
        )

        facts = {
            (fact["subjectKey"], fact["factType"]): fact
            for category in ("items", "variants", "options")
            for row in prepared["snapshot"][category]
            for fact in row["payload"]["canonicalFacts"]
        }
        for identity in (
            ("item:item-a", "enchant_capability"),
            ("item:item-a/variant:variant-a", "enchant_capability"),
            ("item:item-a/variant:variant-a", "static_stats"),
            ("option:shape-only-option", "enhancement_option"),
        ):
            self.assertEqual(facts[identity]["status"], "unresolved_missing")
            self.assertIsNone(facts[identity]["value"])

    def test_plain_socket_minimum_mapping_is_rejected(self):
        from server.gear_release_store import GearReleaseIntegrityError
        from server.gear_release_tool import prepare_staging_gear_release

        with self.assertRaisesRegex(
            GearReleaseIntegrityError,
            "verified SimC socket bonus evidence envelope is required",
        ):
            prepare_staging_gear_release(
                FakeReleaseStore(self.snapshot()),
                season_revision="season-17",
                dependency_revisions=self.dependencies(),
                socket_bonus_minimums={"9300": 1},
            )

    def test_cache_timestamp_cannot_replace_official_source_revision(self):
        from server.gear_release_tool import prepare_staging_gear_release

        snapshot = self.snapshot()
        game_asset = snapshot["items"][0]["payload"]["_metadata"][
            "gameAsset"
        ]
        game_asset.pop("sourceRevision", None)
        game_asset["sourceIdentity"] = "battle-net:item:item-a"

        prepared = prepare_staging_gear_release(
            FakeReleaseStore(snapshot),
            season_revision="season-17",
            dependency_revisions=self.dependencies(),
            socket_bonus_minimums=socket_probe_evidence(),
        )
        identity_fact = next(
            fact
            for fact in prepared["snapshot"]["items"][0]["payload"][
                "canonicalFacts"
            ]
            if fact["factType"] == "item_identity"
        )
        self.assertEqual(identity_fact["status"], "unresolved_missing")
        self.assertIsNone(identity_fact["value"])

    def test_release_local_battle_net_identity_is_rejected(self):
        from server.gear_release_tool import prepare_staging_gear_release

        snapshot = self.snapshot()
        snapshot["items"][0]["payload"]["_metadata"]["gameAsset"][
            "sourceIdentity"
        ] = "gear-release:item:item-a"

        prepared = prepare_staging_gear_release(
            FakeReleaseStore(snapshot),
            season_revision="season-17",
            dependency_revisions=self.dependencies(),
            socket_bonus_minimums=socket_probe_evidence(),
        )
        identity_fact = next(
            fact
            for fact in prepared["snapshot"]["items"][0]["payload"][
                "canonicalFacts"
            ]
            if fact["factType"] == "item_identity"
        )
        self.assertEqual(identity_fact["status"], "unresolved_missing")

    def test_battle_net_identity_must_be_bound_to_item_row(self):
        from server.gear_release_tool import prepare_staging_gear_release

        snapshot = self.snapshot()
        snapshot["items"][0]["payload"]["_metadata"]["gameAsset"][
            "sourceIdentity"
        ] = "battle-net:item:different-item"

        prepared = prepare_staging_gear_release(
            FakeReleaseStore(snapshot),
            season_revision="season-17",
            dependency_revisions=self.dependencies(),
            socket_bonus_minimums=socket_probe_evidence(),
        )
        identity_fact = next(
            fact
            for fact in prepared["snapshot"]["items"][0]["payload"][
                "canonicalFacts"
            ]
            if fact["factType"] == "item_identity"
        )
        self.assertEqual(identity_fact["status"], "unresolved_missing")

    def test_250033_socket_correction_keeps_official_artifact_identity(self):
        from server.gear_release_tool import prepare_staging_gear_release

        snapshot = self.snapshot()
        item = snapshot["items"][0]
        item["itemId"] = "250033"
        item["payload"]["hasSocket"] = False
        item["payload"]["preview_item"] = {"sockets": [{}]}
        item["payload"]["_metadata"]["gameAsset"].update({
            "sourceIdentity": "battle-net:item:250033",
            "sourceRevision": "battle-net-item-250033-r1",
        })
        snapshot["sources"][0]["itemId"] = "250033"
        snapshot["variants"][0]["itemId"] = "250033"

        store = FakeReleaseStore(snapshot)
        prepared = prepare_staging_gear_release(
            store,
            season_revision="season-17",
            dependency_revisions=self.dependencies(),
            socket_bonus_minimums=socket_probe_evidence(),
        )

        socket_fact = next(
            fact
            for fact in prepared["snapshot"]["items"][0]["payload"][
                "canonicalFacts"
            ]
            if fact["factType"] == "socket_count"
        )
        self.assertEqual(socket_fact["status"], "verified")
        self.assertEqual(socket_fact["value"], 1)
        socket_artifacts = [
            artifact
            for artifact in store.evidence_bundles[0]["artifacts"]
            if artifact["payload"].get("factType") == "socket_count"
        ]
        self.assertTrue(socket_artifacts)
        self.assertEqual(
            {artifact["sourceIdentity"] for artifact in socket_artifacts},
            {"battle-net:item:250033"},
        )
        socket_claims = prepared["snapshot"]["items"][0]["payload"][
            "socketEvidence"
        ]["claims"]
        self.assertEqual(
            {
                (
                    claim["sourceType"],
                    claim["sourceIdentity"],
                    claim["sourceRevision"],
                    claim["scope"],
                )
                for claim in socket_claims
            },
            {
                (
                    "battle_net_item",
                    "battle-net:item:250033",
                    "battle-net-item-250033-r1",
                    "exact_item",
                )
            },
        )
        self.assertFalse(any(
            artifact["sourceIdentity"].startswith("gear-release:socket:")
            for artifact in socket_artifacts
        ))

    def test_unverified_observed_gem_occupancy_holds_socket_capacity_pending(self):
        """Raw equipped gems are a replayable constraint, never socket proof."""
        from server import gear_fact_compiler
        from server.gear_release_tool import (
            _compile_release_gear_evidence,
            prepare_staging_gear_release,
        )

        snapshot = self.snapshot()
        variant = snapshot["variants"][0]
        subject_key = "item:item-a/variant:variant-a"
        variant["simcOptions"].update(
            {
                "bonus_id": "9300",
                "gem_id": "240892/240918",
            }
        )
        # A verified stat probe does not by itself attest socket capacity.
        # Equipped gems remain a legacy observation until a dedicated socket
        # probe is supplied.

        compiled = _compile_release_gear_evidence(
            snapshot,
            season_revision="season-17",
            source_revision="legacy-import-r0",
            captured_at="2026-07-27T01:02:03+00:00",
            socket_bonus_minimums={
                "9300": {
                    "minimumTotal": 1,
                    "sourceRevision": "simc-fixture-r1",
                }
            },
            socket_bonus_evidence=socket_probe_evidence(),
        )

        socket_fact = next(
            fact
            for fact in compiled["facts"]
            if fact["subjectKey"] == subject_key
            and fact["factType"] == "socket_count"
        )
        self.assertEqual(
            (socket_fact["status"], socket_fact["value"]),
            ("unresolved_missing", None),
        )
        self.assertEqual(
            socket_fact["problemCode"],
            "unverified_observed_capacity",
        )
        constraint_artifact = next(
            artifact
            for artifact in compiled["artifacts"]
            if artifact["sourceType"] == "legacy_observed_variant"
        )
        constraint_observation = next(
            observation
            for observation in compiled["observations"]
            if observation["artifactId"] == constraint_artifact["artifactId"]
        )
        self.assertEqual(
            constraint_observation["observedValue"],
            2,
        )
        self.assertIn(
            constraint_observation["observationId"],
            socket_fact["observationRefs"],
        )
        self.assertEqual(
            {
                artifact["sourceType"]
                for artifact in compiled["artifacts"]
                if artifact.get("payload", {}).get("factType") == "socket_count"
            },
            {"legacy_observed_variant", "simc_bonus_probe"},
        )
        gap = next(
            gap
            for gap in gear_fact_compiler.evidence_gaps_from_facts(
                compiled["facts"]
            )
            if gap["factKey"] == socket_fact["factKey"]
        )
        self.assertEqual(
            gap["missingRequirement"],
            {
                "subjectKey": subject_key,
                "factType": "socket_count",
                "seasonRevision": "season-17",
                "compilerRuleRevision": "gear-socket-count-policy-v2",
                "requiredInputKey": "trusted_exact_item_probe",
            },
        )
        from server.gear_release_tool import _gear_evidence_gap_records

        gap_record = next(
            record
            for record in _gear_evidence_gap_records(
                compiled["facts"],
                now="2026-07-27T01:02:03+00:00",
            )
            if record["factKey"] == socket_fact["factKey"]
        )
        self.assertEqual(gap_record["status"], "manual_pending")

        # The fail-closed Fact is a legitimate candidate state, not a shadow
        # regression back to the legacy gem count.
        prepared = prepare_staging_gear_release(
            FakeReleaseStore(copy.deepcopy(snapshot)),
            season_revision="season-17",
            dependency_revisions=self.dependencies(),
            socket_bonus_minimums=socket_probe_evidence(),
            evidence_now="2026-07-27T01:02:03+00:00",
        )
        prepared_socket_fact = next(
            fact
            for fact in prepared["snapshot"]["variants"][0]["payload"][
                "canonicalFacts"
            ]
            if fact["factType"] == "socket_count"
        )
        self.assertEqual(
            (prepared_socket_fact["status"], prepared_socket_fact["value"]),
            ("unresolved_missing", None),
        )
        self.assertEqual(prepared["gate"]["factShadow"]["status"], "pass")
        self.assertNotIn(
            "socketCount",
            prepared["snapshot"]["variants"][0]["payload"].get(
                "capabilityOverrides", {}
            ),
        )

    def test_candidate_recompile_explicitly_compiles_collected_bonus_evidence_for_250033(self):
        """A recovered Artifact changes only the prepared candidate input."""
        from server.gear_evidence_registry import (
            build_evidence_artifact,
            build_evidence_observation,
        )
        from server.gear_release_tool import (
            _compile_release_gear_evidence,
            prepare_staging_gear_release,
        )

        snapshot = self.snapshot()
        snapshot["items"][0]["itemId"] = "250033"
        snapshot["items"][0]["payload"]["hasSocket"] = False
        snapshot["items"][0]["payload"]["_metadata"]["gameAsset"].update({
            "sourceIdentity": "battle-net:item:250033",
            "sourceRevision": "battle-net-item-250033-r1",
        })
        snapshot["sources"][0]["itemId"] = "250033"
        snapshot["variants"][0].update({
            "itemId": "250033",
            "variantKey": "void_upgrade-298",
            "hasSocket": False,
        })
        subject_key = "item:250033/variant:void_upgrade-298"
        artifact = build_evidence_artifact(
            source_type="simc_bonus_probe",
            source_identity="simulationcraft:show_bonus_ids",
            source_revision="simc-midnight-fixture-r1",
            season_revision="season-17",
            captured_at="2026-07-27T01:02:03+00:00",
            payload={
                "bonusId": 298,
                "factType": "socket_count",
                "socketCount": 1,
                "subjectKey": subject_key,
            },
        )
        observation = build_evidence_observation(
            artifact_id=artifact["artifactId"],
            subject_key=subject_key,
            fact_type="socket_count",
            observed_value=1,
            parser_revision="simc-bonus-probe-observer-v1",
            source_scope="exact_variant",
            status="accepted",
        )

        probe_evidence = socket_probe_evidence()
        baseline = _compile_release_gear_evidence(
            copy.deepcopy(snapshot),
            season_revision="season-17",
            source_revision="legacy-import-r0",
            captured_at="2026-07-27T01:02:03+00:00",
            socket_bonus_minimums={
                bonus_id: {
                    "minimumTotal": minimum,
                    "sourceRevision": probe_evidence["sourceRevision"],
                }
                for bonus_id, minimum in probe_evidence["minimums"].items()
            },
            socket_bonus_evidence=probe_evidence,
        )
        baseline_socket_fact = next(
            fact
            for fact in baseline["facts"]
            if fact["subjectKey"] == subject_key and fact["factType"] == "socket_count"
        )
        self.assertEqual((baseline_socket_fact["status"], baseline_socket_fact["value"]), ("unresolved_missing", None))

        store = FakeReleaseStore(snapshot)
        with patch(
            "server.gear_release_tool.gear_fact_shadow.compare_legacy_and_canonical",
            return_value={"status": "pass", "blockers": []},
        ):
            prepared = prepare_staging_gear_release(
                store,
                season_revision="season-17",
                dependency_revisions=self.dependencies(),
                socket_bonus_minimums=probe_evidence,
                extra_artifacts=[artifact],
                extra_observations=[observation],
            )

        socket_fact = next(
            fact
            for fact in prepared["snapshot"]["variants"][0]["payload"]["canonicalFacts"]
            if fact["factType"] == "socket_count"
        )
        self.assertEqual((socket_fact["status"], socket_fact["value"]), ("verified", 1))
        bundle = store.evidence_bundles[0]
        self.assertIn(artifact["artifactId"], [row["artifactId"] for row in bundle["artifacts"]])
        self.assertIn(observation["observationId"], [row["observationId"] for row in bundle["observations"]])

    def test_shadow_regression_blocks_before_release_seal(self):
        from server.gear_release_store import GearReleaseIntegrityError
        from server.gear_release_tool import build_legacy_gear_release

        store = FakeReleaseStore(self.snapshot())
        with patch(
            "server.gear_release_tool.gear_fact_shadow.compare_legacy_and_canonical",
            return_value={
                "status": "blocked",
                "blockers": [{"code": "CANONICAL_FACT_REGRESSION"}],
            },
        ):
            with self.assertRaisesRegex(
                GearReleaseIntegrityError,
                "canonical fact shadow blocked candidate",
            ):
                build_legacy_gear_release(
                    store,
                    season_revision="midnight-season-1",
                    dependency_revisions=self.dependencies(),
                    socket_bonus_minimums=socket_probe_evidence(),
                )

        self.assertEqual(store.gear_seals, [])

    def test_prepare_fails_closed_without_registry_persistence_owner(self):
        from server.gear_release_store import GearReleaseIntegrityError
        from server.gear_release_tool import prepare_staging_gear_release

        class SnapshotOnlyStore:
            def snapshot_staging_gear(inner_self):
                return copy.deepcopy(self.snapshot())

        with self.assertRaisesRegex(
            GearReleaseIntegrityError,
            "Gear Evidence Registry persistence owner is required",
        ):
            prepare_staging_gear_release(
                SnapshotOnlyStore(),
                season_revision="midnight-season-1",
                dependency_revisions=self.dependencies(),
                socket_bonus_minimums=socket_probe_evidence(),
                evidence_now="2026-07-26T02:00:00+00:00",
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
            socket_bonus_minimums=socket_probe_evidence(),
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
            "canEnchant": True,
            "canEmbellish": True,
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
        for option in snapshot["options"]:
            option["payload"]["optionEvidence"] = {
                "sourceType": "simc_item_probe",
                "sourceIdentity": f"simc-option:{option['optionId']}",
                "sourceRevision": "simc-options-2026-07-11",
                "sourceScope": "option",
                "status": "verified",
            }
        for variant in snapshot["variants"]:
            payload = (
                variant["payload"]
                if isinstance(variant.get("payload"), dict)
                else {}
            )
            if variant["variantKey"] in {
                "variant-observed-nonenchant-overlap",
                "variant-built-in-embellishment",
            }:
                overrides = (
                    payload["capabilityOverrides"]
                    if isinstance(payload.get("capabilityOverrides"), dict)
                    else {}
                )
                if variant["variantKey"] == "variant-observed-nonenchant-overlap":
                    overrides["canEnchant"] = False
                else:
                    overrides["canEmbellish"] = False
                payload["capabilityOverrides"] = overrides
            claims = ["slot_compatibility"]
            overrides = payload.get("capabilityOverrides")
            if isinstance(overrides, dict):
                if "canEnchant" in overrides:
                    claims.append("enchant_capability")
                if "canEmbellish" in overrides:
                    claims.append("embellishment_capability")
            payload["canonicalEvidence"] = {
                "sourceType": "season_rule",
                "sourceIdentity": f"season-rule:{variant['variantId']}",
                "sourceRevision": "midnight-season-1",
                "sourceScope": "exact_variant",
                "status": "verified",
                "claims": claims,
            }
            if isinstance(payload.get("simcEncodedItem"), str):
                payload["sourceRevision"] = "simc-echo-2026-07-11"
                payload["statEvidence"] = {
                    "sourceType": "simc_item_probe",
                    "sourceIdentity": f"simc-echo:{variant['variantId']}",
                    "sourceRevision": "simc-echo-2026-07-11",
                    "sourceScope": "exact_variant",
                    "status": "verified",
                    "claims": [
                        "static_stats",
                        "variant_track",
                        "enhancement_echo",
                    ],
                }
            variant["payload"] = payload

        dependencies = {**self.dependencies(), "capabilityRevision": CAPABILITY_REVISION}
        managed = prepare_staging_gear_release(
            FakeReleaseStore(snapshot),
            season_revision="midnight-season-1",
            dependency_revisions=dependencies,
            socket_bonus_minimums=socket_probe_evidence(),
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
            {"embellishment": "unresolved_drop"},
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
            socket_bonus_minimums=socket_probe_evidence(),
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
        snapshot["variants"][0]["payload"]["canonicalEvidence"]["claims"].append(
            "enchant_capability"
        )
        snapshot["variants"][0]["payload"]["statSource"] = "simulationcraft"
        prepared = prepare_staging_gear_release(
            FakeReleaseStore(snapshot),
                season_revision="midnight-season-1",
                dependency_revisions=self.dependencies(),
                socket_bonus_minimums=socket_probe_evidence({"9300": 2}),
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
            socket_probe_evidence({"9300": 2, "9400": 1}),
            socket_probe_evidence({"9400": 1, "9300": 2}),
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

        parsed = load_probe(
            "/fake/simc",
            source_identity="simulationcraft:show_bonus_ids",
            source_revision="simc-commit-a",
            runner=runner,
        )

        self.assertEqual(
            parsed,
            socket_probe_evidence(
                {"523": 1, "8781": 2, "9300": 2},
                revision="simc-commit-a",
            ),
        )
        self.assertEqual(calls[0][0], ["/fake/simc", "show_bonus_ids=1"])
        self.assertTrue(calls[0][1]["capture_output"])
        self.assertTrue(calls[0][1]["text"])
        self.assertGreater(calls[0][1]["timeout"], 0)
        self.assertLessEqual(calls[0][1]["timeout"], 60)

        with self.assertRaisesRegex(
            RuntimeError,
            "SimC socket probe failed",
        ):
            load_probe("/fake/simc", runner=runner)

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
                    load_probe(
                        binary,
                        source_identity="simulationcraft:show_bonus_ids",
                        source_revision="simc-commit-a",
                        runner=failing_runner,
                    )
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
                        socket_bonus_minimums=socket_probe_evidence(),
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
                        socket_bonus_minimums=socket_probe_evidence(),
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

    def test_community_release_projects_two_hero_slots_from_talent_candidates(self):
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
        talent_candidates = [
            {"id": "talent-frost-top", "classKey": "mage", "specKey": "arcane", "heroKey": "sunfury", "scenarioKey": "mythic_plus", "sourceKey": "raiderio", "sourceIdentity": frost_top["sourceIdentity"], "talentCandidateRank": 1},
            {"id": "talent-frost-fallback", "classKey": "mage", "specKey": "arcane", "heroKey": "sunfury", "scenarioKey": "mythic_plus", "sourceKey": "raiderio", "sourceIdentity": frost_fallback["sourceIdentity"], "talentCandidateRank": 2},
            {"id": "talent-spell", "classKey": "mage", "specKey": "arcane", "heroKey": "spellslinger", "scenarioKey": "mythic_plus", "sourceKey": "raiderio", "sourceIdentity": spell["sourceIdentity"], "talentCandidateRank": 1},
        ]
        store = FakeReleaseStore(snapshot, [frost_top, frost_fallback, spell], talent_candidates)

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
        self.assertEqual(result["release"]["schemaRevision"], "community-release-v2")
        self.assertEqual(set(winners), {"sunfury", "spellslinger"})
        self.assertEqual(winners["sunfury"]["payload"]["talentWinnerId"], "talent-frost-top")
        self.assertEqual(winners["sunfury"]["payload"]["gearProjectionMode"], "gear_fallback")
        self.assertEqual(winners["sunfury"]["payload"]["gearSourceTemplateId"], "frost-fallback")
        self.assertEqual(winners["spellslinger"]["payload"]["gearProjectionMode"], "talent_winner")
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

        snapshot = self.snapshot()
        gear = gear_release.build_release(
            release_kind="gear",
            season_revision="season-17",
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

        snapshot = self.snapshot()
        gear = gear_release.build_release(
            release_kind="gear",
            season_revision="season-17",
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
        ), patch.object(
            gear_release_tool,
            "build_legacy_community_release",
            return_value=community_result,
        ), redirect_stdout(output):
            status = gear_release_tool.main([
                "build-legacy-all",
                "--season-revision", "season-17",
                "--simc-runtime-revision", "simc-r1",
            ])

        self.assertEqual(status, 0)
        rendered = json.loads(output.getvalue())
        self.assertEqual(rendered["community"]["gate"]["rankOneRejections"], [evidence])

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
