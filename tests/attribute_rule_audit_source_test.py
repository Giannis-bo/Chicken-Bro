#!/usr/bin/env python3
import unittest
from unittest.mock import patch

from server.attribute_rule_audit_source import AttributeAuditSourceUnavailable, fetch_official_profile


class AttributeRuleAuditSourceTest(unittest.TestCase):
    def test_missing_structured_identity_is_rejected_without_oauth(self):
        with patch("server.attribute_rule_audit_source.get_blizzard_access_token") as token:
            with self.assertRaisesRegex(AttributeAuditSourceUnavailable, "OFFICIAL_PROFILE_IDENTITY_INVALID"):
                fetch_official_profile({"region": "eu", "realmSlug": "blackrock"})
        token.assert_not_called()

    def test_profile_equipment_and_statistics_are_normalized_without_exposing_token_or_raw_body(self):
        profile = {
            "character_class": {"name": "Mage"},
            "active_spec": {"name": "Arcane"},
            "race": {"name": "Night Elf"},
            "level": 90,
        }
        equipment = {
            "equipped_items": [
                {
                    "slot": {"type": "HEAD"},
                    "item": {"id": 250060},
                    "level": {"value": 289},
                    "bonus_list": [6652],
                    "sockets": [{"item": {"id": 240914}}, {"item": {"id": 240914}}],
                    "enchantments": [{"enchantment_id": 8017}, {"enchantment_id": 8001}],
                }
            ]
        }
        statistics = {
            "health": 458760,
            "power": 342615,
            "intellect": {"base": 620, "effective": 2462},
            "stamina": {"base": 4600, "effective": 22938},
            "spell_crit": {"rating_normalized": 558, "value": 19.130434},
            "spell_haste": {"rating_normalized": 802, "value": 23.003637},
            "mastery": {"rating_normalized": 785, "value": 37.04609},
            "versatility": 385,
            "versatility_damage_done_bonus": 7.1296296,
            "avoidance": {"rating_normalized": 127, "rating_bonus": 3.4510376},
            "lifesteal": {"rating_normalized": 166, "value": 2.4057627},
            "speed": {"rating_normalized": 55, "rating_bonus": 4.7825403},
        }
        specializations = {
            "active_specialization": {"id": 62, "name": "Arcane"},
            "specializations": [
                {
                    "specialization": {"id": 62, "name": "Arcane"},
                    "loadouts": [{
                        "is_active": True,
                        "talent_loadout_code": "C4DAMhlVtghLZL4RZzExaQoBY",
                        "selected_hero_talent_tree": {"name": "Spellslinger"},
                    }],
                },
                {
                    "specialization": {"id": 64, "name": "Frost"},
                    "loadouts": [{
                        "is_active": True,
                        "talent_loadout_code": "wrong-specialization-loadout",
                        "selected_hero_talent_tree": {"name": "Frostfire"},
                    }],
                },
            ],
        }
        calls = []

        def api(path, token, **kwargs):
            calls.append((path, token, kwargs))
            if path.endswith("/equipment"):
                return equipment
            if path.endswith("/statistics"):
                return statistics
            if path.endswith("/specializations"):
                return specializations
            return profile

        with patch("server.attribute_rule_audit_source.get_blizzard_access_token", return_value="secret-token"), patch(
            "server.attribute_rule_audit_source.blizzard_get", side_effect=api
        ):
            result = fetch_official_profile({
                "region": "kr", "realmSlug": "azshara", "characterName": "카르꽁스", "locale": "ko_KR"
            })

        self.assertEqual(result["profile"]["character"], {
            "classKey": "mage", "specKey": "arcane", "raceKey": "night_elf", "level": 90
        })
        self.assertEqual(result["profile"]["equipment"][0], {
            "slot": "head", "itemId": "250060", "itemLevel": 289,
            "bonusIds": ["6652"], "gemIds": ["240914", "240914"], "enchantIds": ["8001", "8017"],
        })
        self.assertEqual(result["profile"]["talentLoadout"], {
            "specKey": "arcane",
            "heroKey": "spellslinger",
            "talentLoadoutCode": "C4DAMhlVtghLZL4RZzExaQoBY",
        })
        self.assertEqual(result["panel"], {
            "primary": {"rawValue": 2462},
            "stamina": {"rawValue": 22938},
            "resources": {
                "health": {"rawValue": 458760},
                "mana": {"rawValue": 342615},
            },
            "secondary": [
                {"key": "crit", "rawValue": 558, "convertedValue": "19.130434%", "displayUnit": "percent"},
                {"key": "haste", "rawValue": 802, "convertedValue": "23.003637%", "displayUnit": "percent"},
                {"key": "mastery", "rawValue": 785, "convertedValue": "37.04609%", "displayUnit": "percent"},
                {"key": "versatility", "rawValue": 385, "convertedValue": "7.1296296%", "displayUnit": "percent"},
                {"key": "avoidance", "rawValue": 127, "convertedValue": "3.4510376%", "displayUnit": "percent"},
                {"key": "leech", "rawValue": 166, "convertedValue": "2.4057627%", "displayUnit": "percent"},
                {"key": "speed", "rawValue": 55, "convertedValue": "4.7825403%", "displayUnit": "percent"},
            ],
        })
        self.assertEqual(len(calls), 4)
        self.assertTrue(any(path.endswith("/specializations") for path, _, _ in calls))
        self.assertTrue(any(path.endswith("/statistics") for path, _, _ in calls))
        self.assertTrue(all(kwargs["locale"] == "en_US" for _, _, kwargs in calls))
        self.assertNotIn("secret-token", str(result))

    def test_upstream_failure_is_reduced_to_safe_code(self):
        with patch("server.attribute_rule_audit_source.get_blizzard_access_token", side_effect=RuntimeError("token=top-secret")):
            with self.assertRaisesRegex(AttributeAuditSourceUnavailable, "OFFICIAL_PROFILE_AUTH_UNAVAILABLE") as raised:
                fetch_official_profile({
                    "region": "eu", "realmSlug": "blackrock", "characterName": "Heated", "locale": "en_GB"
                })
        self.assertNotIn("top-secret", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
