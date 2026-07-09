#!/usr/bin/env python3
import json
import unittest


class PgGearTemplateSelectorsTest(unittest.TestCase):
    def test_build_official_item_metadata_by_id_read_model_filters_unofficial_rows(self):
        from server.pg_gear_template_selectors import build_official_item_metadata_by_id_read_model

        official_payload = {
            "displayName": "Crown of the Violet Tower",
            "quality": "Epic",
            "inventory_type": {"type": "INVTYPE_HEAD", "name": "Head"},
            "item_class": {"name": "Armor"},
            "item_subclass": {"name": "Cloth"},
            "_metadata": {
                "source": "Battle.net Game Data API",
                "metadataStatus": "verified",
                "iconUrl": "https://render.worldofwarcraft.com/item/crown.jpg",
                "locale": "zh_CN",
                "englishName": "Crown of the Violet Tower",
            },
        }
        verified_official_shape_payload = {
            "localizedName": "Verified Shape Helm",
            "inventoryType": {"type": "INVTYPE_HEAD"},
            "itemClass": {"name": "Armor"},
        }
        unofficial_payload = {
            "displayName": "Community Guess Helm",
            "_metadata": {"source": "community_guess", "metadataStatus": "partial"},
        }
        rows = [
            ("190001", "Fallback Crown", "head", 639, json.dumps(official_payload), "verified"),
            ("190002", "Verified Shape Helm", "head", "626", json.dumps(verified_official_shape_payload), "verified"),
            ("190003", "Community Guess Helm", "head", 610, json.dumps(unofficial_payload), "partial"),
            ("190004", "Malformed", "head", 610, "{not-json", "verified"),
        ]

        metadata_by_id = build_official_item_metadata_by_id_read_model(rows)

        self.assertEqual(set(metadata_by_id), {"190001", "190002"})
        self.assertEqual(metadata_by_id["190001"]["itemId"], "190001")
        self.assertEqual(metadata_by_id["190001"]["displayName"], "Crown of the Violet Tower")
        self.assertEqual(metadata_by_id["190001"]["itemLevel"], 639)
        self.assertEqual(metadata_by_id["190001"]["quality"], "Epic")
        self.assertEqual(metadata_by_id["190001"]["iconUrl"], "https://render.worldofwarcraft.com/item/crown.jpg")
        self.assertEqual(metadata_by_id["190001"]["metadataSource"], "Battle.net Game Data API")
        self.assertEqual(metadata_by_id["190001"]["metadataStatus"], "verified")
        self.assertEqual(metadata_by_id["190001"]["metadataLocale"], "zh_CN")
        self.assertEqual(metadata_by_id["190001"]["englishName"], "Crown of the Violet Tower")
        self.assertEqual(metadata_by_id["190001"]["armorType"], "Cloth")
        self.assertEqual(metadata_by_id["190002"]["metadataSource"], "Battle.net Game Data API")

    def test_build_hydrated_community_gear_items_read_model_applies_official_metadata(self):
        from server.pg_gear_template_selectors import build_hydrated_community_gear_items_read_model

        gear_items_json = json.dumps([
            {"itemId": "190001", "slot": "head", "displayName": "Sparse Crown"},
            {"itemId": "190099", "slot": "neck", "displayName": "Unmatched Pendant"},
            "bad-item",
            {"id": "190002", "slot": "hands", "displayName": "Sparse Gloves"},
        ])
        official_metadata_by_id = {
            "190001": {
                "itemId": "190001",
                "displayName": "Crown of the Violet Tower",
                "slot": "head",
                "itemLevel": 639,
                "quality": "Epic",
                "iconUrl": "https://render.worldofwarcraft.com/item/crown.jpg",
                "metadataStatus": "verified",
                "metadataSource": "Battle.net Game Data API",
                "metadataLocale": "zh_CN",
            },
            "190002": {
                "itemId": "190002",
                "displayName": "Gloves of the Violet Tower",
                "slot": "hands",
                "itemLevel": 636,
                "quality": "Epic",
                "metadataStatus": "verified",
                "metadataSource": "Battle.net Game Data API",
            },
        }

        hydrated = build_hydrated_community_gear_items_read_model(gear_items_json, official_metadata_by_id)

        self.assertEqual(len(hydrated), 3)
        self.assertEqual(hydrated[0]["itemId"], "190001")
        self.assertEqual(hydrated[0]["displayName"], "Crown of the Violet Tower")
        self.assertEqual(hydrated[0]["localizedName"], "Crown of the Violet Tower")
        self.assertEqual(hydrated[0]["iconUrl"], "https://render.worldofwarcraft.com/item/crown.jpg")
        self.assertEqual(hydrated[0]["quality"], "Epic")
        self.assertEqual(hydrated[0]["metadataSource"], "Battle.net Game Data API")
        self.assertEqual(hydrated[0]["gameAsset"]["status"], "verified")
        self.assertEqual(hydrated[1]["displayName"], "Unmatched Pendant")
        self.assertNotIn("metadataSource", hydrated[1])
        self.assertEqual(hydrated[2]["itemId"], "190002")
        self.assertEqual(hydrated[2]["displayName"], "Gloves of the Violet Tower")

    def test_collect_community_template_item_refs_read_model_flattens_gear_item_rows(self):
        from server.pg_gear_template_selectors import collect_community_template_item_refs_read_model

        rows = [
            ("template-a", json.dumps([
                {"itemId": "190001", "slot": "head"},
                "not-an-item",
                {"itemId": "190002", "slot": "hands"},
            ])),
            ("template-b", "{not-json"),
            ("template-c", json.dumps({"not": "a-list"})),
            ("template-d", json.dumps([{"itemId": "190003", "slot": "neck"}])),
        ]

        item_refs = collect_community_template_item_refs_read_model(rows, gear_items_index=1)

        self.assertEqual(
            item_refs,
            [
                {"itemId": "190001", "slot": "head"},
                {"itemId": "190002", "slot": "hands"},
                {"itemId": "190003", "slot": "neck"},
            ],
        )

    def test_build_public_gear_template_read_model_compacts_payload_without_public_baseline(self):
        from server.pg_gear_template_selectors import build_public_gear_template_read_model

        active_observed = {
            "id": "observed-profile-mage-arcane",
            "classKey": "mage",
            "specKey": "arcane",
            "sourceKey": "raiderio_observed_profile",
            "sourceStatus": "synced",
            "status": "complete",
            "sourceUrl": "https://raider.io/characters/cn/realm/Arcaneproof",
            "sampleCount": 1,
            "scanRunId": "scan-mage-arcane",
            "readySlotCount": 16,
            "missingSlots": [],
            "payload": {
                "fetchedAt": "2026-07-09T00:00:00+00:00",
                "profileHash": "profile:mage:arcane:observed",
                "gearHash": "gear:mage:arcane:observed",
                "character": {
                    "name": "Arcaneproof",
                    "region": "cn",
                    "realmSlug": "realm",
                },
            },
            "gearItems": [{"slot": "head", "itemId": "540101", "simcReady": True}],
            "rawString": "head=observed_hood,id=540101",
        }
        recommended_bis = {
            "id": "recommended-bis-mage-arcane",
            "classKey": "mage",
            "specKey": "arcane",
            "sourceKey": "recommended_bis",
            "sourceStatus": "synced",
            "status": "complete",
            "readySlotCount": 16,
            "gearItems": [{"slot": "head", "itemId": "540201", "simcReady": True}],
        }
        season_recommendation = {
            "id": "season-recommendation-mage-arcane",
            "classKey": "mage",
            "specKey": "arcane",
            "sourceKey": "season_recommendation",
            "sourceStatus": "synced",
            "status": "complete",
            "readySlotCount": 16,
            "gearItems": [{"slot": "head", "itemId": "540301", "simcReady": True}],
        }

        read_model = build_public_gear_template_read_model(
            [recommended_bis, active_observed, season_recommendation],
            "mage",
            "arcane",
            compact=True,
            compact_template=lambda template: {"id": template["id"], "sourceKey": template["sourceKey"]},
            sync_state_builder=lambda templates: {
                "selectedTemplateIds": [template["id"] for template in templates],
            },
            legality_gate=lambda template, _class_key, _spec_key: template,
        )

        self.assertEqual(
            [template["id"] for template in read_model["selectedCommunityTemplates"]],
            ["observed-profile-mage-arcane"],
        )
        self.assertEqual(read_model["selectedBaselineTemplates"], [])
        self.assertEqual(
            read_model["payloadCommunityTemplates"],
            [{"id": "observed-profile-mage-arcane", "sourceKey": "raiderio_observed_profile"}],
        )
        self.assertEqual(read_model["payloadBaselineTemplates"], [])
        self.assertEqual(
            read_model["communityTemplateSync"],
            {"selectedTemplateIds": ["observed-profile-mage-arcane"]},
        )

    def test_select_public_gear_templates_keeps_observed_only_and_empty_public_baseline(self):
        from server.pg_gear_template_selectors import select_public_gear_templates_for_spec

        active_observed = {
            "id": "observed-profile-mage-arcane",
            "classKey": "mage",
            "specKey": "arcane",
            "sourceKey": "raiderio_observed_profile",
            "sourceStatus": "synced",
            "status": "complete",
            "sourceUrl": "https://raider.io/characters/cn/realm/Arcaneproof",
            "sampleCount": 1,
            "scanRunId": "scan-mage-arcane",
            "readySlotCount": 16,
            "missingSlots": [],
            "payload": {
                "fetchedAt": "2026-07-09T00:00:00+00:00",
                "profileHash": "profile:mage:arcane:observed",
                "gearHash": "gear:mage:arcane:observed",
                "character": {
                    "name": "Arcaneproof",
                    "region": "cn",
                    "realmSlug": "realm",
                },
            },
            "gearItems": [{"slot": "head", "itemId": "540101", "simcReady": True}],
            "rawString": "head=observed_hood,id=540101",
        }
        source_less_observed = {
            **active_observed,
            "id": "observed-profile-mage-arcane-source-less",
            "sourceUrl": "",
            "sampleCount": 0,
            "payload": {},
        }
        recommended_bis = {
            "id": "recommended-bis-mage-arcane",
            "classKey": "mage",
            "specKey": "arcane",
            "sourceKey": "recommended_bis",
            "sourceStatus": "synced",
            "status": "complete",
            "readySlotCount": 16,
            "gearItems": [{"slot": "head", "itemId": "540201", "simcReady": True}],
        }
        season_recommendation = {
            "id": "season-recommendation-mage-arcane",
            "classKey": "mage",
            "specKey": "arcane",
            "sourceKey": "season_recommendation",
            "sourceStatus": "synced",
            "status": "complete",
            "readySlotCount": 16,
            "gearItems": [{"slot": "head", "itemId": "540301", "simcReady": True}],
        }

        selected = select_public_gear_templates_for_spec(
            [source_less_observed, recommended_bis, active_observed, season_recommendation],
            "mage",
            "arcane",
            legality_gate=lambda template, _class_key, _spec_key: template,
        )

        self.assertEqual([template["id"] for template in selected["communityTemplates"]], ["observed-profile-mage-arcane"])
        self.assertEqual(selected["baselineTemplates"], [])


if __name__ == "__main__":
    unittest.main()
