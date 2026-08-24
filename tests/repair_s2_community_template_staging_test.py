import importlib.util
import unittest
from pathlib import Path

from server.websim_payload import CANONICAL_GEAR_SLOTS


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "repair-s2-community-template-staging.py"
SPEC = importlib.util.spec_from_file_location("repair_s2_community_template_staging", SCRIPT)
repair = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(repair)


class RepairS2CommunityTemplateStagingTest(unittest.TestCase):
    def test_derived_template_carries_observed_profile_and_gear_evidence(self):
        profile_url = "https://raider.io/characters/cn/arygos/Observed"
        rows = {}
        for index, slot in enumerate(CANONICAL_GEAR_SLOTS, start=1):
            payload = {
                "classKey": "mage",
                "specKey": "fire",
                "profileUrl": profile_url,
                "sourceIdentity": "raiderio:cn|arygos|observed",
                "characterName": "Observed",
                "region": "cn",
                "realmSlug": "arygos",
                "rank": 3,
                "score": 4200.5,
                "maxKeyLevel": 24,
                "itemStats": {"intellect": 100},
                "iconUrl": f"https://render.example/{index}.jpg",
            }
            if slot in {"main_hand", "off_hand"}:
                payload["weaponType"] = "One-Handed Sword"
            rows[slot] = {
                "slot": slot,
                "itemId": str(250000 + index),
                "itemLevel": 300,
                "variantKey": f"observed-{slot}-{index}",
                "simcOptions": {"bonus_id": str(index), "gem_id": "240908"},
                "status": "verified",
                "blockers": [],
                "payload": payload,
            }

        template = repair._repair_template(
            "mage",
            "fire",
            profile_url,
            rows,
            updated_at="2026-08-21T16:34:30+08:00",
            expires_at="2026-09-04T16:34:30+08:00",
        )

        self.assertEqual(template["sampleCount"], 1)
        self.assertTrue(template["profileHash"].startswith("profile:mage:fire:"))
        self.assertEqual(template["gearHash"], template["signature"])
        self.assertEqual(template["sourceRefs"][0]["sampleCount"], 1)
        self.assertEqual(template["sourceRefs"][0]["profileHash"], template["profileHash"])
        self.assertEqual(template["sourceRefs"][0]["gearHash"], template["gearHash"])
        self.assertEqual(template["payload"]["templateEvidence"]["profileHash"], template["profileHash"])
        self.assertEqual(template["gearItems"][0]["bonus_id"], "1")
        self.assertEqual(template["gearItems"][0]["observedProfileRefs"][0]["sourceIdentity"], "raiderio:cn|arygos|observed")


if __name__ == "__main__":
    unittest.main()
