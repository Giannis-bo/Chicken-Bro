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

    def test_profile_and_equipment_are_normalized_without_exposing_token_or_raw_body(self):
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
                    "enchantment": {"enchantment_id": 8017},
                }
            ]
        }
        calls = []

        def api(path, token, **kwargs):
            calls.append((path, token, kwargs))
            return equipment if path.endswith("/equipment") else profile

        with patch("server.attribute_rule_audit_source.get_blizzard_access_token", return_value="secret-token"), patch(
            "server.attribute_rule_audit_source.blizzard_get", side_effect=api
        ):
            result = fetch_official_profile({
                "region": "eu", "realmSlug": "blackrock", "characterName": "Heated", "locale": "en_GB"
            })

        self.assertEqual(result["profile"]["character"], {
            "classKey": "mage", "specKey": "arcane", "raceKey": "night_elf", "level": 90
        })
        self.assertEqual(result["profile"]["equipment"][0], {
            "slot": "head", "itemId": "250060", "itemLevel": 289,
            "bonusIds": ["6652"], "gemIds": ["240914", "240914"], "enchantIds": ["8017"],
        })
        self.assertEqual(result["panel"], {})
        self.assertEqual(len(calls), 2)
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
