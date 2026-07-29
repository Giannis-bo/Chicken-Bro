#!/usr/bin/env python3
"""Candidate-only preview fixture must never alter the normal public path."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from server.gear_attribute_preview_fixture import (
    PREVIEW_ENV,
    PREVIEW_TEMPLATE_ID,
    append_preview_template,
    preview_community_import,
    preview_template_for_payload,
)


PAYLOAD = {
    "classKey": "mage",
    "specKey": "frost",
    "manifestRevision": "season-manifest:sha256:preview",
    "pointerGeneration": 17,
    "seasonRevision": "season-preview",
    "gearCatalogRevision": "gear-preview",
    "formalActiveManifest": True,
    "communityTemplates": [{"id": "real-template"}],
}


class GearAttributePreviewFixtureTest(unittest.TestCase):
    def test_preview_is_inert_without_candidate_environment_flag(self):
        with patch.dict(os.environ, {PREVIEW_ENV: "0"}, clear=False):
            self.assertIsNone(preview_template_for_payload(PAYLOAD))
            self.assertEqual(append_preview_template(PAYLOAD), PAYLOAD)
            self.assertIsNone(preview_community_import({}, PAYLOAD, "request-a"))

    def test_enabled_preview_keeps_internal_armory_fixture_out_of_public_community_templates(self):
        with patch.dict(os.environ, {PREVIEW_ENV: "1"}, clear=False):
            template = preview_template_for_payload(PAYLOAD)
            self.assertIsNotNone(template)
            self.assertEqual(template["id"], PREVIEW_TEMPLATE_ID)
            self.assertEqual(template["attributeCharacterContext"]["raceKey"], "dwarf")
            self.assertEqual(template["readySlotCount"], 15)
            self.assertEqual(len(template["gearItems"]), 15)

            augmented = append_preview_template(PAYLOAD)
            self.assertEqual(augmented["communityTemplates"], [{"id": "real-template"}])
            response = preview_community_import({
                "classKey": "mage", "specKey": "frost", "templateId": PREVIEW_TEMPLATE_ID,
                "expectedManifestRevision": PAYLOAD["manifestRevision"],
            }, augmented, "request-preview")

        self.assertIsNotNone(response)
        status, envelope, timings = response
        self.assertEqual(status, 200)
        self.assertEqual(envelope["status"], "verified")
        self.assertEqual(envelope["data"]["manifest"]["manifestRevision"], PAYLOAD["manifestRevision"])
        snapshot = envelope["data"]["resolvedSnapshot"]
        self.assertEqual(snapshot["attributeStaticFacts"]["status"], "verified")
        self.assertEqual(snapshot["staticAttributes"], {
            "intellect": 1748, "stamina": 18400, "crit_rating": 861,
            "haste_rating": 637, "mastery_rating": 1040, "avoidance_rating": 470,
            "leech_rating": 55,
        })
        self.assertEqual(len(envelope["data"]["importedGearBySlot"]), 15)
        self.assertEqual(timings["cache"], "miss")

    def test_preview_rejects_a_stale_manifest_or_unexpected_request_fields(self):
        with patch.dict(os.environ, {PREVIEW_ENV: "1"}, clear=False):
            self.assertIsNone(preview_community_import({
                "classKey": "mage", "specKey": "frost", "templateId": PREVIEW_TEMPLATE_ID,
                "expectedManifestRevision": "stale",
            }, PAYLOAD, "request-stale"))
            self.assertIsNone(preview_community_import({
                "classKey": "mage", "specKey": "frost", "templateId": PREVIEW_TEMPLATE_ID,
                "expectedManifestRevision": PAYLOAD["manifestRevision"], "unexpected": True,
            }, PAYLOAD, "request-unexpected"))


if __name__ == "__main__":
    unittest.main()
