import importlib
import unittest


class GearLegalityTest(unittest.TestCase):
    def setUp(self):
        try:
            self.legality = importlib.import_module("server.gear_legality")
        except ImportError as exc:
            self.fail(f"gear legality evaluator module is missing: {exc}")

    def test_elemental_shaman_allows_fist_weapon_main_hand(self):
        result = self.legality.gear_legality_for_item(
            "shaman",
            "elemental",
            "main_hand",
            {"itemId": "250001", "name": "Storm Fist", "weaponType": "Fist Weapon"},
        )

        self.assertEqual(result["status"], "legal")
        self.assertEqual(result["reasons"], [])

    def test_mistweaver_monk_allows_fist_weapon_main_hand(self):
        result = self.legality.gear_legality_for_item(
            "monk",
            "mistweaver",
            "main_hand",
            {"itemId": "258050", "name": "Arcanic of the High Sage", "weaponType": "Fist Weapon"},
        )

        self.assertEqual(result["status"], "legal")
        self.assertEqual(result["reasons"], [])

    def test_enhancement_shaman_blocks_shield_offhand(self):
        result = self.legality.gear_legality_for_item(
            "shaman",
            "enhancement",
            "off_hand",
            {"itemId": "250002", "name": "Wrong Shield", "weaponType": "Shield"},
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blockedSlots"], ["off_hand"])
        self.assertEqual(result["reasons"][0]["reason"], "weapon_type_not_allowed_for_spec_slot")
        self.assertEqual(result["reasons"][0]["severity"], "blocker")

    def test_caster_two_hand_main_hand_blocks_selected_offhand(self):
        result = self.legality.gear_legality_for_template(
            "shaman",
            "elemental",
            [
                {"slot": "main_hand", "itemId": "250003", "name": "Legal Staff", "weaponType": "Staff"},
                {
                    "slot": "off_hand",
                    "itemId": "250004",
                    "name": "Held Tome",
                    "weaponType": "Held In Off-hand",
                },
            ],
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blockedSlots"], ["off_hand"])
        self.assertIn("two_hand_main_hand_occupies_offhand", {item["reason"] for item in result["reasons"]})

    def test_mail_spec_blocks_cloth_armor_slot(self):
        result = self.legality.gear_legality_for_item(
            "shaman",
            "elemental",
            "head",
            {"itemId": "250005", "name": "Wrong Hood", "armorType": "Cloth"},
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blockedSlots"], ["head"])
        self.assertEqual(result["reasons"][0]["reason"], "armor_type_not_allowed_for_class")


if __name__ == "__main__":
    unittest.main()
