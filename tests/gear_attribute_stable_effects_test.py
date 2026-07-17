#!/usr/bin/env python3
"""Contracts for sealed stable attribute effects from a source talent loadout."""

from __future__ import annotations

import json
import inspect
import unittest
from unittest.mock import patch

from server import websim_payload


class GearAttributeStableEffectsTest(unittest.TestCase):
    def test_source_talent_loadout_projects_only_its_selected_mage_effects(self):
        derive = getattr(websim_payload, "derive_gear_attribute_stable_effect_context", None)
        self.assertTrue(callable(derive))
        decoded = {
            "status": "decoded",
            "classKey": "mage",
            "specKey": "frost",
            "sourcePath": "/opt/wow-simc/current/engine/dbc/generated/trait_data.inc",
            "loadout": [
                {
                    "entryId": 101,
                    "node": {"entries": [{"id": 101, "spell": {"id": 458437}}]},
                },
                {
                    "entryId": 102,
                    "node": {
                        "entries": [
                            {"id": 102, "spell": {"id": 382490}},
                            {"id": 103, "spell": {"id": 999999}},
                        ]
                    },
                },
                {
                    "entryId": 104,
                    "node": {"entries": [{"id": 104, "spell": {"id": 382493}}]},
                },
                {
                    "entryId": 105,
                    "node": {"entries": [{"id": 105, "spell": {"id": 417489}}]},
                },
                {
                    "entryId": 106,
                    "node": {"entries": [{"id": 106, "spell": {"id": 1244107}}]},
                },
            ],
        }

        with patch.object(websim_payload, "decode_external_talent_import_code", return_value=decoded):
            context = derive(
                {"rawImportCode": "CAE_SOURCE_LOADOUT_MUST_NOT_LEAK"},
                "mage",
                "frost",
            )

        self.assertEqual(context["schemaRevision"], "gear-attribute-stable-effects-v1")
        self.assertEqual(context["status"], "verified")
        self.assertEqual(context["origin"], "source_profile")
        self.assertEqual(
            context["effectIds"],
            [
                "mage:arcane_intellect",
                "mage:charm_of_medivh",
                "mage:frost_mastery",
                "mage:frost_winters_blessing",
                "mage:inspired_intellect",
                "mage:tome_of_antonidas",
                "mage:tome_of_rhonin",
            ],
        )
        self.assertTrue(context["loadoutSignature"].startswith("sha256:"))
        self.assertNotIn("CAE_SOURCE_LOADOUT_MUST_NOT_LEAK", json.dumps(context, sort_keys=True))

    def test_arcane_source_loadout_includes_its_spec_only_haste_effect(self):
        derive = getattr(websim_payload, "derive_gear_attribute_stable_effect_context", None)
        self.assertTrue(callable(derive))
        decoded = {
            "status": "decoded",
            "classKey": "mage",
            "specKey": "arcane",
            "loadout": [
                {"entryId": 201, "node": {"entries": [{"id": 201, "spell": {"id": 1244107}}]}},
                {"entryId": 202, "node": {"entries": [{"id": 202, "spell": {"id": 383980}}]}},
                {"entryId": 203, "node": {"entries": [{"id": 203, "spell": {"id": 205022}}]}},
            ],
        }

        with patch.object(websim_payload, "decode_external_talent_import_code", return_value=decoded):
            context = derive(
                {"rawImportCode": "CAE_ARCANE_SOURCE_LOADOUT_MUST_NOT_LEAK"},
                "mage",
                "arcane",
            )

        self.assertEqual(
            context["effectIds"],
            [
                "mage:arcane_familiar",
                "mage:arcane_intellect",
                "mage:arcane_mastery",
                "mage:arcane_tempo",
                "mage:charm_of_medivh",
            ],
        )

    def test_observed_template_source_keeps_only_the_sealed_stable_effect_context(self):
        context = {
            "schemaRevision": "gear-attribute-stable-effects-v1",
            "status": "verified",
            "origin": "source_profile",
            "effectIds": ["mage:inspired_intellect"],
            "loadoutSignature": "sha256:" + "a" * 64,
        }

        refs = websim_payload.observed_profile_template_source_refs([
            {
                "observedProfileRefs": [{
                    "profileUrl": "https://raider.io/characters/kr/azshara/frost",
                    "sourceName": "Raider.IO observed profile",
                    "attributeStableEffectContext": context,
                    "rawImportCode": "CAE_SOURCE_LOADOUT_MUST_NOT_LEAK",
                }],
            }
        ])

        self.assertIn("attributeStableEffectContext", refs[0])
        self.assertEqual(refs[0].get("attributeStableEffectContext"), context)
        self.assertNotIn("rawImportCode", json.dumps(refs, sort_keys=True))

    def test_observed_template_seals_source_profile_stable_effect_context(self):
        build_template = websim_payload.gear_community_template_from_observed_items
        self.assertIn("source_profile", inspect.signature(build_template).parameters)
        decoded = {
            "status": "decoded",
            "classKey": "mage",
            "specKey": "frost",
            "loadout": [
                {"entryId": 1, "node": {"entries": [{"id": 1, "spell": {"id": 458437}}]}},
            ],
        }
        source_profile = {
            "talentLoadout": {"rawImportCode": "CAE_SOURCE_LOADOUT_MUST_NOT_LEAK"},
        }
        items = [{
            "slot": "head",
            "simcSlot": "head",
            "id": "270001",
            "itemId": "270001",
            "name": "observed_head",
            "displayName": "Observed Head",
            "simcName": "observed_head",
            "simcReady": True,
            "bonus_id": "6652",
            "observedProfileRefs": [{
                "profileUrl": "https://raider.io/characters/kr/azshara/frost",
                "sourceName": "Raider.IO observed profile",
            }],
        }]

        with patch.object(websim_payload, "decode_external_talent_import_code", return_value=decoded):
            template = build_template(items, "mage", "frost", source_profile=source_profile)

        self.assertEqual(
            template["attributeStableEffectContext"]["effectIds"],
            ["mage:arcane_intellect", "mage:frost_mastery", "mage:inspired_intellect"],
        )
        self.assertNotIn("CAE_SOURCE_LOADOUT_MUST_NOT_LEAK", json.dumps(template, sort_keys=True))
        compact = websim_payload.compact_community_gear_template(
            websim_payload.normalize_community_gear_template(template)
        )
        self.assertIn("attributeStableEffectContext", compact)
        self.assertEqual(
            compact.get("attributeStableEffectContext"),
            template["attributeStableEffectContext"],
        )


if __name__ == "__main__":
    unittest.main()
