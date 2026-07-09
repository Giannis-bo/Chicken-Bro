#!/usr/bin/env python3
import unittest


class PgGearTemplateSelectorsTest(unittest.TestCase):
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
