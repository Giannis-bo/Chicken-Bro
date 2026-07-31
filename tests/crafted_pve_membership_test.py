import json
import tempfile
import unittest
from pathlib import Path

from server.crafted_pve_membership import (
    CraftedPveMembershipError,
    build_crafted_pve_membership,
    load_crafted_pve_membership,
)


class CraftedPveMembershipTest(unittest.TestCase):
    def test_build_membership_requires_one_official_item_for_every_recipe(self):
        crafted_source = {
            "rawMembers": [
                {
                    "candidateItemIds": ["1001"],
                    "clientBuild": "12.0.7.68887",
                    "evidenceRef": "official-client-db2-v1/current-client-crafted-membership.json#item=1001",
                    "profession": "Engineering",
                    "category": "Goggles",
                    "recipeId": "5001",
                    "name": "Amplified Goggles",
                    "membershipStatus": "verified_output_item",
                    "modifiedCraftingSlotNames": [
                        "Amplify Secondary Stat",
                        "Add Embellishment",
                    ],
                },
                {
                    "candidateItemIds": ["1002"],
                    "clientBuild": "12.0.7.68887",
                    "evidenceRef": "official-client-db2-v1/current-client-crafted-membership.json#item=1002",
                    "profession": "Alchemy",
                    "category": "Trinkets",
                    "recipeId": "5002",
                    "name": "Fixed Trinket",
                    "membershipStatus": "verified_output_item",
                    "modifiedCraftingSlotNames": [],
                },
            ]
        }
        official_search = {
            "results": [
                {
                    "data": {
                        "id": 1001,
                        "is_equippable": True,
                        "required_level": 90,
                        "name": {"en_US": "Amplified Goggles", "zh_CN": "增幅护目镜"},
                        "inventory_type": {"type": "HEAD"},
                        "item_class": {"id": 4, "name": {"en_US": "Armor"}},
                        "item_subclass": {"id": 4, "name": {"en_US": "Plate"}},
                    },
                    "key": {"href": "https://us.api.blizzard.com/data/wow/item/1001"},
                },
                {
                    "data": {
                        "id": 1002,
                        "is_equippable": True,
                        "required_level": 90,
                        "name": {"en_US": "Fixed Trinket", "zh_CN": "固定饰品"},
                        "inventory_type": {"type": "TRINKET"},
                        "item_class": {"id": 4, "name": {"en_US": "Armor"}},
                        "item_subclass": {"id": 0, "name": {"en_US": "Miscellaneous"}},
                    },
                    "key": {"href": "https://us.api.blizzard.com/data/wow/item/1002"},
                },
            ]
        }

        result = build_crafted_pve_membership(
            crafted_source,
            official_search,
            season_revision="midnight-season-1",
            as_of="2026-07-30",
        )

        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["summary"]["itemCount"], 2)
        self.assertEqual(
            result["summary"]["bySecondaryStatMode"],
            {
                "amplify_one_secondary": 1,
                "fixed_or_recipe_defined_stats": 1,
            },
        )
        self.assertEqual(result["items"][0]["slot"], "head")
        self.assertEqual(result["items"][0]["name"], "增幅护目镜")
        self.assertEqual(result["items"][0]["secondaryStatMode"], "amplify_one_secondary")
        self.assertTrue(result["items"][0]["canAddEmbellishment"])
        self.assertEqual(result["items"][1]["slot"], "trinket1")

        official_search["results"].pop()
        with self.assertRaisesRegex(
            CraftedPveMembershipError,
            "missing official item search record 1002",
        ):
            build_crafted_pve_membership(
                crafted_source,
                official_search,
                season_revision="midnight-season-1",
                as_of="2026-07-30",
            )

    def test_loader_rejects_duplicate_or_count_mismatch(self):
        payload = {
            "schemaVersion": 1,
            "schemaRevision": "midnight-season-1-crafted-pve-membership-v1",
            "seasonRevision": "midnight-season-1",
            "asOf": "2026-07-30",
            "status": "verified",
            "progressionStatus": "blocked",
            "progressionReasonCodes": [
                "OFFICIAL_PROGRESSION_STATE_UNAVAILABLE",
            ],
            "summary": {
                "itemCount": 2,
                "bySecondaryStatMode": {"customize_two_secondary": 2},
            },
            "items": [
                {
                    "itemId": "1001",
                    "recipeId": "5001",
                    "name": "One",
                    "slot": "head",
                    "profession": "tailoring",
                    "secondaryStatMode": "customize_two_secondary",
                    "membershipStatus": "verified_output_item",
                    "clientBuild": "12.0.7.68887",
                    "evidenceRef": "official-client-db2-v1/current-client-crafted-membership.json#item=1001",
                    "officialItemRef": "https://us.api.blizzard.com/data/wow/item/1001",
                },
                {
                    "itemId": "1001",
                    "recipeId": "5002",
                    "name": "Duplicate",
                    "slot": "hands",
                    "profession": "tailoring",
                    "secondaryStatMode": "customize_two_secondary",
                    "membershipStatus": "verified_output_item",
                    "clientBuild": "12.0.7.68887",
                    "evidenceRef": "official-client-db2-v1/current-client-crafted-membership.json#item=1001",
                    "officialItemRef": "https://us.api.blizzard.com/data/wow/item/1001",
                },
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "membership.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                CraftedPveMembershipError,
                "duplicate itemId 1001",
            ):
                load_crafted_pve_membership(path)

    def test_loader_rejects_membership_with_unbound_authority_identity(self):
        payload = {
            "schemaVersion": 1,
            "schemaRevision": "midnight-season-1-crafted-pve-membership-v1",
            "seasonRevision": "midnight-season-1",
            "asOf": "2026-07-30",
            "status": "verified",
            "progressionStatus": "blocked",
            "progressionReasonCodes": [
                "OFFICIAL_PROGRESSION_STATE_UNAVAILABLE",
            ],
            "summary": {
                "itemCount": 1,
                "bySecondaryStatMode": {"customize_two_secondary": 1},
            },
            "items": [
                {
                    "itemId": "1001",
                    "recipeId": "5001",
                    "name": "One",
                    "slot": "head",
                    "profession": "tailoring",
                    "secondaryStatMode": "customize_two_secondary",
                    "membershipStatus": "verified_output_item",
                    "clientBuild": "12.0.7.68887",
                    "evidenceRef": "official-client-db2-v1/current-client-crafted-membership.json#item=1001",
                    "officialItemRef": "https://us.api.blizzard.com/data/wow/item/1001",
                },
            ],
        }
        invalid_cases = (
            ("seasonRevision", "", "missing seasonRevision"),
            ("asOf", "", "missing asOf"),
            ("progressionStatus", "ready", "progressionStatus must be blocked"),
            (
                "progressionReasonCodes",
                [],
                "OFFICIAL_PROGRESSION_STATE_UNAVAILABLE",
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "membership.json"
            for field, value, message in invalid_cases:
                with self.subTest(field=field):
                    candidate = json.loads(json.dumps(payload))
                    candidate[field] = value
                    path.write_text(json.dumps(candidate), encoding="utf-8")
                    with self.assertRaisesRegex(
                        CraftedPveMembershipError,
                        message,
                    ):
                        load_crafted_pve_membership(path)

            item_invalid_cases = (
                ("itemId", "not-an-id", "invalid itemId"),
                ("recipeId", "0", "invalid recipeId"),
                (
                    "membershipStatus",
                    "observed",
                    "membershipStatus must be verified_output_item",
                ),
                ("clientBuild", "", "missing clientBuild"),
                ("evidenceRef", "", "missing evidenceRef"),
                ("officialItemRef", "", "missing officialItemRef"),
            )
            for field, value, message in item_invalid_cases:
                with self.subTest(item_field=field):
                    candidate = json.loads(json.dumps(payload))
                    candidate["items"][0][field] = value
                    path.write_text(json.dumps(candidate), encoding="utf-8")
                    with self.assertRaisesRegex(
                        CraftedPveMembershipError,
                        message,
                    ):
                        load_crafted_pve_membership(path)

    def test_checked_in_membership_is_complete_current_client_projection(self):
        payload = load_crafted_pve_membership()

        self.assertEqual(payload["status"], "verified")
        self.assertEqual(payload["summary"]["itemCount"], 172)
        self.assertEqual(
            payload["summary"]["bySecondaryStatMode"],
            {
                "amplify_one_secondary": 38,
                "customize_two_secondary": 106,
                "fixed_or_recipe_defined_stats": 28,
            },
        )
        by_id = {item["itemId"]: item for item in payload["items"]}
        self.assertEqual(len(by_id), 172)
        self.assertEqual(
            by_id["244774"]["secondaryStatMode"],
            "amplify_one_secondary",
        )
        self.assertEqual(
            payload["progressionStatus"],
            "blocked",
        )


if __name__ == "__main__":
    unittest.main()
