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

    def test_build_community_gear_template_read_model_preserves_payload_evidence(self):
        from server.pg_gear_template_selectors import build_community_gear_template_read_model

        payload = {
            "scenarioKey": "mythic_plus",
            "enhancementReadiness": {"status": "verified", "socket": {"ready": True}},
            "templateEvidence": {"source": "raiderio", "profileHash": "profile:mage:frost:observed"},
            "sampleCount": "3",
            "profileHash": "profile:mage:frost:observed",
            "gearHash": "gear:mage:frost:observed",
        }
        gear_items = [
            {"itemId": "190001", "slot": "head", "displayName": "Sparse Crown"},
        ]
        official_metadata_by_id = {
            "190001": {
                "itemId": "190001",
                "displayName": "Crown of the Violet Tower",
                "slot": "head",
                "quality": "Epic",
                "iconUrl": "https://render.worldofwarcraft.com/item/crown.jpg",
                "metadataStatus": "verified",
                "metadataSource": "Battle.net Game Data API",
            },
        }
        row = (
            "template-mage-frost-observed",
            "mage",
            "frost",
            "Observed Frost Mage",
            "raiderio_observed_profile",
            "Raider.IO observed profile",
            "https://raider.io/characters/cn/realm/Frostproof",
            "synced",
            "complete",
            "sig:mage:frost",
            json.dumps([{"sourceKey": "raiderio", "sourceUrl": "https://raider.io/characters/cn/realm/Frostproof"}]),
            json.dumps(gear_items),
            "head=crown_of_the_violet_tower,id=190001",
            "16",
            json.dumps(["off_hand"]),
            "mplus",
            json.dumps(payload),
            "2026-07-09T12:00:00+00:00",
            "",
            "scan-run-1",
        )
        repair_inputs = []

        def coverage_repair(template):
            repair_inputs.append(template["id"])
            repaired = {**template}
            repaired["missingSlots"] = []
            repaired["readySlotCount"] = 16
            repaired["occupiedSlots"] = {"off_hand": {"slot": "main_hand", "itemId": "190001"}}
            return repaired

        template = build_community_gear_template_read_model(
            row,
            official_metadata_by_id,
            coverage_repair=coverage_repair,
        )

        self.assertEqual(repair_inputs, ["template-mage-frost-observed"])
        self.assertEqual(template["id"], "template-mage-frost-observed")
        self.assertEqual(template["sourceKey"], "raiderio_observed_profile")
        self.assertEqual(template["gearItems"][0]["displayName"], "Crown of the Violet Tower")
        self.assertEqual(template["gearItems"][0]["iconUrl"], "https://render.worldofwarcraft.com/item/crown.jpg")
        self.assertEqual(template["sourceRefs"][0]["sourceKey"], "raiderio")
        self.assertEqual(template["scenarioKey"], "mythic_plus")
        self.assertEqual(template["enhancementReadiness"], payload["enhancementReadiness"])
        self.assertEqual(template["templateEvidence"], payload["templateEvidence"])
        self.assertEqual(template["sampleCount"], 3)
        self.assertEqual(template["profileHash"], "profile:mage:frost:observed")
        self.assertEqual(template["gearHash"], "gear:mage:frost:observed")
        self.assertEqual(template["templateRevision"], "community-template-v1")
        self.assertEqual(template["missingSlots"], [])
        self.assertEqual(template["readySlotCount"], 16)
        self.assertTrue(template["canApplyGear"])

    def test_build_community_gear_templates_read_model_delegates_rows_to_dedupe(self):
        from server.pg_gear_template_selectors import build_community_gear_templates_read_model

        def make_row(template_id, item_id, updated_at):
            payload = {
                "sampleCount": 1,
                "profileHash": f"profile:{template_id}",
                "gearHash": f"gear:{template_id}",
            }
            return (
                template_id,
                "mage",
                "frost",
                f"Observed {template_id}",
                "raiderio_observed_profile",
                "Raider.IO observed profile",
                f"https://raider.io/characters/cn/realm/{template_id}",
                "synced",
                "complete",
                f"sig:{template_id}",
                json.dumps([{"sourceKey": "raiderio", "sourceUrl": f"https://raider.io/characters/cn/realm/{template_id}"}]),
                json.dumps([{"itemId": item_id, "slot": "head", "displayName": f"Sparse {template_id}"}]),
                f"head=item_{item_id},id={item_id}",
                16,
                json.dumps([]),
                "mplus",
                json.dumps(payload),
                updated_at,
                "",
                "scan-run-1",
            )

        official_metadata_by_id = {
            "190001": {
                "itemId": "190001",
                "displayName": "Crown of the Violet Tower",
                "slot": "head",
                "metadataStatus": "verified",
                "metadataSource": "Battle.net Game Data API",
            },
            "190002": {
                "itemId": "190002",
                "displayName": "Hood of the Violet Tower",
                "slot": "head",
                "metadataStatus": "verified",
                "metadataSource": "Battle.net Game Data API",
            },
        }
        repair_inputs = []
        dedupe_inputs = []

        def coverage_repair(template):
            repair_inputs.append(template["id"])
            return {**template, "repairMarker": True}

        def dedupe_templates(templates):
            dedupe_inputs.append([template["id"] for template in templates])
            return [templates[-1]]

        templates = build_community_gear_templates_read_model(
            [
                make_row("template-a", "190001", "2026-07-09T12:00:00+00:00"),
                make_row("template-b", "190002", "2026-07-09T12:01:00+00:00"),
            ],
            official_metadata_by_id,
            coverage_repair=coverage_repair,
            dedupe_templates=dedupe_templates,
        )

        self.assertEqual(repair_inputs, ["template-a", "template-b"])
        self.assertEqual(dedupe_inputs, [["template-a", "template-b"]])
        self.assertEqual([template["id"] for template in templates], ["template-b"])
        self.assertEqual(templates[0]["gearItems"][0]["displayName"], "Hood of the Violet Tower")
        self.assertTrue(templates[0]["repairMarker"])

    def test_build_admin_gear_template_queue_rows_read_model_preserves_blockers_after_repair(self):
        from server.pg_gear_template_selectors import build_admin_gear_template_queue_rows_read_model

        def make_row(template_id, source_key, status, missing_slots, payload):
            return (
                template_id,
                "mage",
                "frost",
                f"Template {template_id}",
                source_key,
                "Template Source",
                "",
                "partial" if status == "partial" else "synced",
                status,
                f"sig:{template_id}",
                json.dumps([]),
                json.dumps([{"itemId": "190001", "slot": "main_hand", "displayName": "Sparse Staff"}]),
                "main_hand=sparse_staff,id=190001",
                16 - len(missing_slots),
                json.dumps(missing_slots),
                "daily",
                json.dumps(payload),
                "2026-07-09T12:00:00+00:00",
                "",
                "scan-run-1",
            )

        repair_inputs = []

        def coverage_repair(template):
            repair_inputs.append(template["id"])
            if template["id"] != "baseline-repaired":
                return template
            repaired = {**template}
            repaired["missingSlots"] = []
            repaired["readySlotCount"] = 16
            repaired["status"] = "complete"
            repaired["sourceStatus"] = "synced"
            return repaired

        queue_rows = build_admin_gear_template_queue_rows_read_model(
            [
                make_row("observed-partial", "raiderio_observed_profile", "partial", ["neck", "trinket1"], {"blockers": ["parser blocked"]}),
                make_row("baseline-repaired", "simc_preset", "partial", ["off_hand"], {"blockers": []}),
            ],
            {},
            coverage_repair=coverage_repair,
        )

        self.assertEqual(repair_inputs, ["observed-partial", "baseline-repaired"])
        self.assertEqual(
            queue_rows,
            [
                ("gear_templates", "partial", ["parser blocked", "missing slots: neck, trinket1"]),
                ("gear_templates", "complete", []),
            ],
        )

    def test_build_admin_gear_template_display_records_read_model_groups_display_slots(self):
        from server.pg_gear_template_selectors import build_admin_gear_template_display_records_read_model

        raw_blocked = {
            "id": "raw-blocked-template",
            "classKey": "mage",
            "specKey": "frost",
            "sourceKey": "unknown_source",
            "status": "blocked",
        }
        community_old = {
            "id": "observed-old",
            "classKey": "mage",
            "specKey": "frost",
            "sourceKey": "raiderio_observed_profile",
            "status": "partial",
            "rawString": "head=old,id=1",
        }
        community_new = {
            **community_old,
            "id": "observed-new",
            "status": "complete",
            "rawString": "head=new,id=2",
        }
        baseline_old = {
            "id": "baseline-old",
            "classKey": "mage",
            "specKey": "frost",
            "sourceKey": "simc_preset",
            "status": "complete",
        }
        baseline_new = {
            **baseline_old,
            "id": "baseline-new",
        }
        community_calls = []
        baseline_calls = []

        def community_selector(candidates, class_key, spec_key, strict_active=True):
            community_calls.append(([template["id"] for template in candidates], class_key, spec_key, strict_active))
            return [candidates[-1]]

        def baseline_selector(candidates):
            baseline_calls.append([template["id"] for template in candidates])
            return [candidates[-1]]

        display_records = build_admin_gear_template_display_records_read_model(
            [raw_blocked, community_old, community_new, baseline_old, baseline_new],
            community_selector=community_selector,
            baseline_selector=baseline_selector,
        )

        self.assertEqual([template["id"] for template in display_records], ["raw-blocked-template", "observed-new", "baseline-new"])
        self.assertEqual(community_calls, [(["observed-old", "observed-new"], "mage", "frost", False)])
        self.assertEqual(baseline_calls, [["baseline-old", "baseline-new"]])

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
