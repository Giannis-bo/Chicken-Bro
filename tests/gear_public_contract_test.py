#!/usr/bin/env python3
import unittest

from server import gear_public_contract
from server import websim_payload


class GearPublicContractTest(unittest.TestCase):
    def test_public_contract_module_matches_websim_payload_observed_only_policy(self):
        active_observed = {
            "id": "observed-profile-mage-frost",
            "classKey": "mage",
            "specKey": "frost",
            "sourceKey": "raiderio_observed_profile",
            "sourceStatus": "synced",
            "status": "complete",
            "sourceUrl": "https://raider.io/characters/cn/realm/Magefrost",
            "sampleCount": 1,
            "scanRunId": "scan-mage-frost",
            "readySlotCount": 16,
            "missingSlots": [],
            "payload": {
                "fetchedAt": "2026-07-09T00:00:00+00:00",
                "profileHash": "profile:mage:frost:active",
                "gearHash": "gear:mage:frost:active",
                "character": {
                    "name": "Magefrost",
                    "region": "cn",
                    "realmSlug": "realm",
                },
            },
            "gearItems": [
                {"slot": "head", "itemId": "540001", "simcReady": True},
                {"slot": "main_hand", "itemId": "540002", "simcReady": True},
            ],
            "rawString": "head=observed_hood,id=540001\nmain_hand=observed_wand,id=540002",
        }
        source_less_observed = {
            **active_observed,
            "id": "observed-profile-mage-frost-source-less",
            "sourceUrl": "",
            "sampleCount": 0,
            "payload": {},
        }
        recommended_bis = {
            "id": "recommended-bis-mage-frost",
            "classKey": "mage",
            "specKey": "frost",
            "sourceKey": "recommended_bis",
            "sourceStatus": "synced",
            "status": "complete",
            "readySlotCount": 16,
        }
        season_recommendation = {
            "id": "season-recommendation-mage-frost",
            "classKey": "mage",
            "specKey": "frost",
            "sourceKey": "season_recommendation",
            "sourceStatus": "synced",
            "status": "complete",
            "readySlotCount": 16,
        }
        templates = [source_less_observed, recommended_bis, active_observed, season_recommendation]

        module_visible = gear_public_contract.public_gear_templates_for_spec(templates, "mage", "frost")
        websim_visible = websim_payload.public_gear_templates_for_spec(templates, "mage", "frost")

        self.assertEqual([template["id"] for template in module_visible], ["observed-profile-mage-frost"])
        self.assertEqual([template["id"] for template in websim_visible], [template["id"] for template in module_visible])
        self.assertEqual(gear_public_contract.public_baseline_fallback_templates_for_spec("mage", "frost"), [])
        self.assertEqual(websim_payload.public_baseline_fallback_templates_for_spec("mage", "frost"), [])

    def test_public_contract_module_matches_websim_payload_template_evidence_sources(self):
        active_observed = {
            "id": "observed-profile-mage-arcane-evidence",
            "classKey": "mage",
            "specKey": "arcane",
            "sourceKey": "raiderio_observed_profile",
            "sourceStatus": "synced",
            "status": "complete",
            "sampleCount": 1,
            "readySlotCount": 16,
            "missingSlots": [],
            "payload": {
                "templateEvidence": {
                    "profileHash": "profile:mage:arcane:evidence",
                    "gearHash": "gear:mage:arcane:evidence",
                },
            },
            "sourceRefs": [
                {
                    "sourceUrl": "https://raider.io/characters/cn/realm/Arcaneproof",
                    "fetchedAt": "2026-07-09T00:00:00+00:00",
                }
            ],
            "gearItems": [{"slot": "head", "itemId": "540101", "simcReady": True}],
        }

        module_visible = gear_public_contract.public_gear_templates_for_spec([active_observed], "mage", "arcane")
        websim_visible = websim_payload.public_gear_templates_for_spec([active_observed], "mage", "arcane")

        self.assertEqual([template["id"] for template in module_visible], [template["id"] for template in websim_visible])


if __name__ == "__main__":
    unittest.main()
