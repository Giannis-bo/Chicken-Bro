import copy
import unittest

from server.s2_community_exact import (
    S2CommunityExactError,
    merge_s2_community_exact_snapshot,
    select_s2_bindable_community_templates,
)


def base_snapshot():
    return {
        "items": [{
            "itemId": "1001",
            "name": "Official Helm",
            "slot": "head",
            "sourceStatus": "verified",
            "payload": {"baseCapabilities": {"socketCount": 0}},
        }],
        "sources": [{
            "sourceId": "s2-source-1001",
            "itemId": "1001",
            "sourceType": "raid",
            "sourceKey": "raid:s2",
            "payload": {"status": "verified"},
        }],
        "variants": [{
            "variantId": "browse-1001",
            "itemId": "1001",
            "variantKey": "s2-browse-1001",
            "slot": "head",
            "sourceType": "raid",
            "itemLevel": 344,
            "rowFamily": "browse",
            "simcOptions": {"ilevel": "344", "bonus_id": "9001"},
            "status": "verified",
            "blockers": [],
            "payload": {"resolvedStats": {"stamina": 200}},
        }],
        "options": [],
    }


def community_snapshot():
    return {
        "items": [{
            "itemId": "2001",
            "name": "Observed Cloak",
            "slot": "back",
            "sourceStatus": "verified",
            "payload": {
                "baseCapabilities": {"socketCount": 0},
                "gameAsset": {
                    "status": "verified",
                    "source": "blizzard",
                    "iconUrl": "https://render.worldofwarcraft.com/us/icons/56/item-2001.jpg",
                },
                "iconUrl": "https://render.worldofwarcraft.com/us/icons/56/item-2001.jpg",
            },
        }],
        "sources": [{
            "sourceId": "observed-source-2001",
            "itemId": "2001",
            "sourceType": "observed_profile",
            "sourceKey": "raiderio:observed",
            "payload": {"status": "verified"},
        }],
        "variants": [{
            "variantId": "observed-2001",
            "itemId": "2001",
            "variantKey": "observed-2001-v1",
            "slot": "back",
            "sourceType": "observed_profile",
            "itemLevel": 298,
            "simcOptions": {"ilevel": "298", "bonus_id": "8001/8002"},
            "status": "verified",
            "blockers": [],
            "payload": {
                "itemStats": {"intellect": 120, "stamina": 300},
                "simcReady": True,
            },
        }],
        "options": [],
    }


class S2CommunityExactTest(unittest.TestCase):
    def test_merges_only_referenced_observed_rows_and_binds_missing_variant_key(self):
        template = {
            "templateId": "community-1",
            "classKey": "mage",
            "specKey": "frost",
            "sourceKey": "raiderio_observed_profile",
            "gearItems": [{
                "slot": "back",
                "itemId": "2001",
                "ilevel": "298",
                "bonus_id": "8001/8002",
            }],
        }
        result = merge_s2_community_exact_snapshot(
            base_snapshot(),
            community_snapshot(),
            [template],
        )

        self.assertEqual(result["binding"]["selectedExactRowCount"], 1)
        self.assertEqual(
            result["templates"][0]["gearItems"][0]["variantKey"],
            "observed-2001-v1",
        )
        self.assertEqual(
            [(row["itemId"], row["variantKey"], row["rowFamily"])
             for row in result["snapshot"]["variants"]],
            [
                ("1001", "s2-browse-1001", "browse"),
                ("2001", "observed-2001-v1", "exact_instance"),
            ],
        )
        observed = result["snapshot"]["variants"][1]
        self.assertEqual(observed["staticStats"]["intellect"], 120)
        self.assertEqual(observed["payload"]["truthScope"], "community_observed")
        observed_item = next(row for row in result["snapshot"]["items"] if row["itemId"] == "2001")
        self.assertEqual(
            observed_item["payload"]["_metadata"]["gameAsset"]["status"],
            "verified",
        )
        self.assertFalse(any(row["itemId"] == "2001" for row in result["snapshot"]["variants"][:1]))

    def test_does_not_mutate_inputs(self):
        base = base_snapshot()
        staging = community_snapshot()
        templates = [{
            "templateId": "community-1",
            "classKey": "mage",
            "specKey": "frost",
            "sourceKey": "raiderio_observed_profile",
            "gearItems": [{"slot": "back", "itemId": "2001", "ilevel": "298", "bonus_id": "8001/8002"}],
        }]
        originals = copy.deepcopy((base, staging, templates))
        merge_s2_community_exact_snapshot(base, staging, templates)
        self.assertEqual((base, staging, templates), originals)

    def test_rejects_ambiguous_observed_identity(self):
        staging = community_snapshot()
        staging["variants"].append({
            **copy.deepcopy(staging["variants"][0]),
            "variantId": "observed-2001-v2",
            "variantKey": "observed-2001-v2",
            "payload": {"itemStats": {"intellect": 121}, "simcReady": True},
        })
        template = {
            "templateId": "community-1",
            "classKey": "mage",
            "specKey": "frost",
            "sourceKey": "raiderio_observed_profile",
            "gearItems": [{"slot": "back", "itemId": "2001", "ilevel": "298", "bonus_id": "8001/8002"}],
        }
        with self.assertRaisesRegex(S2CommunityExactError, "ambiguous"):
            merge_s2_community_exact_snapshot(base_snapshot(), staging, [template])

    def test_accepts_simc_list_stats_from_community_variant(self):
        staging = community_snapshot()
        staging["variants"][0]["payload"]["itemStats"] = [
            {"key": "intellect", "label": "Intellect", "value": 120},
            {"key": "stamina", "label": "Stamina", "value": 300},
        ]
        template = {
            "templateId": "community-1",
            "classKey": "mage",
            "specKey": "frost",
            "sourceKey": "raiderio_observed_profile",
            "gearItems": [{"slot": "back", "itemId": "2001", "ilevel": "298", "bonus_id": "8001/8002"}],
        }

        result = merge_s2_community_exact_snapshot(
            base_snapshot(),
            staging,
            [template],
        )

        observed = result["snapshot"]["variants"][1]
        self.assertEqual(observed["staticStats"], {"intellect": 120, "stamina": 300})

    def test_materializes_observed_gem_occupancy_for_exact_socket_capacity(self):
        staging = community_snapshot()
        staging["variants"][0]["simcOptions"]["gem_id"] = "240898"
        staging["variants"][0]["payload"]["capabilityOverrides"] = {
            "requiresCraftedOption": False,
        }
        template = {
            "templateId": "community-1",
            "classKey": "mage",
            "specKey": "frost",
            "sourceKey": "raiderio_observed_profile",
            "gearItems": [{
                "slot": "back",
                "itemId": "2001",
                "ilevel": "298",
                "bonus_id": "8001/8002",
                "gem_id": "240898",
            }],
        }

        result = merge_s2_community_exact_snapshot(
            base_snapshot(),
            staging,
            [template],
        )

        observed = result["snapshot"]["variants"][1]
        self.assertEqual(
            observed["payload"]["capabilityOverrides"]["socketCount"],
            1,
        )
        self.assertEqual(
            observed["payload"]["socketEvidence"]["claims"][0]["source"],
            "observed_gem_occupancy",
        )

    def test_treats_default_false_capability_override_as_same_identity(self):
        staging = community_snapshot()
        staging["variants"].append({
            **copy.deepcopy(staging["variants"][0]),
            "variantId": "observed-2001-v2",
            "variantKey": "observed-2001-v2",
            "payload": {
                "itemStats": {"intellect": 120, "stamina": 300},
                "simcReady": True,
                "capabilityOverrides": {"requiresCraftedOption": False},
            },
        })
        template = {
            "templateId": "community-1",
            "classKey": "mage",
            "specKey": "frost",
            "sourceKey": "raiderio_observed_profile",
            "gearItems": [{"slot": "back", "itemId": "2001", "ilevel": "298", "bonus_id": "8001/8002"}],
        }

        result = merge_s2_community_exact_snapshot(
            base_snapshot(),
            staging,
            [template],
        )

        self.assertEqual(result["binding"]["selectedExactRowCount"], 1)

    def test_enriches_existing_item_with_verified_staging_media(self):
        staging = community_snapshot()
        icon_url = "https://render.worldofwarcraft.com/us/icons/56/item-1001.jpg"
        staging["items"].append({
            "itemId": "1001",
            "name": "Official Helm",
            "slot": "head",
            "payload": {
                "_metadata": {
                    "iconUrl": icon_url,
                    "gameAsset": {
                        "status": "verified",
                        "source": "blizzard",
                        "iconUrl": icon_url,
                    },
                },
            },
        })
        staging["sources"].append({
            "sourceId": "observed-source-1001",
            "itemId": "1001",
            "sourceType": "observed_profile",
            "sourceKey": "raiderio:observed",
            "payload": {"status": "verified"},
        })
        staging["variants"].append({
            "variantId": "observed-1001",
            "itemId": "1001",
            "variantKey": "observed-1001-v1",
            "slot": "head",
            "sourceType": "observed_profile",
            "itemLevel": 298,
            "simcOptions": {"ilevel": "298", "bonus_id": "8001"},
            "status": "verified",
            "blockers": [],
            "payload": {"itemStats": {"intellect": 120}},
        })
        template = {
            "templateId": "community-1001",
            "classKey": "mage",
            "specKey": "frost",
            "sourceKey": "raiderio_observed_profile",
            "gearItems": [{
                "slot": "head",
                "itemId": "1001",
                "ilevel": "298",
                "bonus_id": "8001",
            }],
        }

        result = merge_s2_community_exact_snapshot(
            base_snapshot(),
            staging,
            [template],
        )

        payload = result["snapshot"]["items"][0]["payload"]
        self.assertEqual(payload["baseCapabilities"], {"socketCount": 0})
        self.assertEqual(payload["_metadata"]["iconUrl"], icon_url)
        self.assertEqual(payload["_metadata"]["gameAsset"]["status"], "verified")

    def test_selects_only_fresh_templates_with_bindable_exact_items(self):
        fresh = {
            "templateId": "fresh",
            "classKey": "mage",
            "specKey": "frost",
            "status": "complete",
            "expiresAt": "2026-08-22T00:00:00+08:00",
            "gearItems": [{"slot": "back", "itemId": "2001", "ilevel": "298", "bonus_id": "8001/8002"}],
        }
        stale = {**copy.deepcopy(fresh), "templateId": "stale", "expiresAt": "2026-08-20T00:00:00+08:00"}
        missing_stats = {
            **copy.deepcopy(fresh),
            "templateId": "missing-stats",
            "gearItems": [{"slot": "back", "itemId": "2001", "ilevel": "299", "bonus_id": "8001/8002"}],
        }
        staging = community_snapshot()

        selected = select_s2_bindable_community_templates(
            [fresh, stale, missing_stats],
            staging["variants"],
            now="2026-08-21T00:00:00+08:00",
        )

        self.assertEqual([row["templateId"] for row in selected], ["fresh"])


if __name__ == "__main__":
    unittest.main()
