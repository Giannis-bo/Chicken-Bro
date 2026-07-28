import copy
import json
import unittest

from server.gear_exact_item_registry import (
    build_exact_item_registry,
    verify_exact_item_registry,
)
from tests.gear_exact_item_instance_test import (
    CATALOG_REVISION,
    CURRENT_BINDING,
    exact_row,
)


def template(*, slot="head", item_id="1001", variant_key="observed-hero-3", **extra):
    return {
        "templateId": "source-template-should-not-be-persisted",
        "displayName": "Observed player",
        "updatedAt": "2026-07-29T01:00:00Z",
        "gearItems": [{
            "slot": slot,
            "itemId": item_id,
            "variantKey": variant_key,
            "gemIds": ["240892", "240897"],
            "gemBonusIds": ["1514", "1514"],
            "gemItemLevels": ["90", "90"],
            "enchantId": "7443",
            "craftedStats": ["36", "32"],
            "embellishmentIds": ["999002", "999001"],
        }],
        **extra,
    }


class GearExactItemRegistryTest(unittest.TestCase):
    def test_only_referenced_instances_are_materialized_and_deduplicated(self):
        second = exact_row(
            itemId="2002",
            variantKey="unreferenced-hero-3",
        )
        community = [
            template(classKey="mage", specKey="frost"),
            template(
                classKey="mage",
                specKey="fire",
                displayName="Same gear, another label",
            ),
        ]

        result = build_exact_item_registry(
            CURRENT_BINDING,
            catalog_revision=CATALOG_REVISION,
            exact_rows=[second, exact_row()],
            community_templates=community,
            personal_templates=[],
        )

        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["summary"]["sourceExactRowCount"], 2)
        self.assertEqual(result["summary"]["referencedExactRowCount"], 1)
        self.assertEqual(result["summary"]["exactItemInstanceCount"], 1)
        self.assertEqual(result["summary"]["enhancementSelectionCount"], 1)
        self.assertEqual(result["summary"]["templateReferenceCount"], 2)
        self.assertEqual(result["summary"]["unreferencedExactRowCount"], 1)
        self.assertEqual(
            result["templateReferences"][0]["exactItemInstanceKey"],
            result["templateReferences"][1]["exactItemInstanceKey"],
        )
        self.assertNotEqual(
            result["templateReferences"][0]["templateContentHash"],
            result["templateReferences"][1]["templateContentHash"],
        )
        self.assertEqual(verify_exact_item_registry(result), [])

    def test_personal_owner_and_display_provenance_never_leave_projector(self):
        first = build_exact_item_registry(
            CURRENT_BINDING,
            catalog_revision=CATALOG_REVISION,
            exact_rows=[exact_row()],
            community_templates=[template()],
            personal_templates=[
                template(
                    userId="secret-account-a",
                    ownerName="Secret Character",
                    accessToken="secret-token-a",
                )
            ],
        )
        second_personal = template(
            userId="secret-account-b",
            ownerName="Other Character",
            accessToken="secret-token-b",
            updatedAt="2026-07-30T01:00:00Z",
        )
        second = build_exact_item_registry(
            CURRENT_BINDING,
            catalog_revision=CATALOG_REVISION,
            exact_rows=[copy.deepcopy(exact_row())],
            community_templates=[copy.deepcopy(template())],
            personal_templates=[second_personal],
        )

        self.assertEqual(first["registryRevision"], second["registryRevision"])
        self.assertEqual(first["status"], "verified")
        serialized = json.dumps(first, ensure_ascii=False)
        for forbidden in (
            "secret-account-a",
            "Secret Character",
            "secret-token-a",
            "source-template-should-not-be-persisted",
            "Observed player",
        ):
            self.assertNotIn(forbidden, serialized)
        personal_refs = [
            row
            for row in first["templateReferences"]
            if row["templateScope"] == "personal"
        ]
        self.assertEqual(len(personal_refs), 1)
        self.assertEqual(
            personal_refs[0]["templateContentHash"],
            second["templateReferences"][-1]["templateContentHash"],
        )

    def test_input_order_does_not_change_registry_identity(self):
        community = [template(slot="head"), template(slot="chest")]
        first = build_exact_item_registry(
            CURRENT_BINDING,
            catalog_revision=CATALOG_REVISION,
            exact_rows=[exact_row()],
            community_templates=community,
            personal_templates=[],
        )
        second = build_exact_item_registry(
            CURRENT_BINDING,
            catalog_revision=CATALOG_REVISION,
            exact_rows=list(reversed([exact_row()])),
            community_templates=list(reversed(community)),
            personal_templates=[],
        )

        self.assertEqual(first["registryRevision"], second["registryRevision"])
        self.assertEqual(first["templateReferences"], second["templateReferences"])

    def test_missing_community_and_ambiguous_source_fail_closed_without_drop(self):
        duplicate = copy.deepcopy(exact_row())
        duplicate["staticStats"]["stamina"] = 999
        missing = build_exact_item_registry(
            CURRENT_BINDING,
            catalog_revision=CATALOG_REVISION,
            exact_rows=[exact_row()],
            community_templates=[],
            personal_templates=[],
        )
        ambiguous = build_exact_item_registry(
            CURRENT_BINDING,
            catalog_revision=CATALOG_REVISION,
            exact_rows=[exact_row(), duplicate],
            community_templates=[template()],
            personal_templates=[],
        )

        self.assertEqual(missing["status"], "blocked")
        self.assertIn("EXACT_REGISTRY_COMMUNITY_MISSING", missing["problemCodes"])
        self.assertEqual(ambiguous["status"], "blocked")
        self.assertEqual(ambiguous["summary"]["templateItemCount"], 1)
        self.assertEqual(ambiguous["summary"]["templateReferenceCount"], 1)
        self.assertEqual(ambiguous["summary"]["blockedReferenceCount"], 1)
        self.assertIn("EXACT_REGISTRY_SOURCE_AMBIGUOUS", ambiguous["problemCodes"])

    def test_explicit_enhancement_mismatch_blocks_reference(self):
        mismatched = template()
        mismatched["gearItems"][0]["enchantId"] = "9999"

        result = build_exact_item_registry(
            CURRENT_BINDING,
            catalog_revision=CATALOG_REVISION,
            exact_rows=[exact_row()],
            community_templates=[mismatched],
            personal_templates=[],
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["summary"]["templateItemCount"], 1)
        self.assertEqual(result["summary"]["templateReferenceCount"], 1)
        self.assertEqual(result["summary"]["exactItemInstanceCount"], 0)
        self.assertIn(
            "EXACT_ENHANCEMENT_SOURCE_MISMATCH",
            result["problemCodes"],
        )


if __name__ == "__main__":
    unittest.main()
