import copy
import re
import unittest

from server.gear_catalog_revision import (
    build_catalog_revision,
    catalog_browse_variant_key,
    verify_catalog_revision,
)


CURRENT_BINDING = {
    "manifestRevision": "season-manifest:sha256:" + ("1" * 64),
    "gearReleaseId": "gear-release:sha256:" + ("2" * 64),
    "gearReleaseContentHash": "sha256:" + ("3" * 64),
    "gearReleaseSchemaRevision": "websim-gear-release-v4",
    "seasonRevision": "season-17-f131dd36ddf1",
    "gearRuleRevision": "gear-rule-matrix-v1",
    "dependencyVector": {
        "gearRuleRevision": "gear-rule-matrix-v1",
        "trackAuthorityRevision": "midnight-season-1-track-authority-v1",
    },
    "sourceSummary": {
        "sourceMode": "sealed_gear_release",
        "contentSummary": {"itemCount": 1, "variantCount": 1},
    },
}


def source(item_id, suffix="raid"):
    return {
        "sourceId": f"source-{item_id}-{suffix}",
        "itemId": item_id,
        "sourceType": "raid",
        "sourceKey": suffix,
        "instanceId": "1302",
        "encounterId": "3010",
        "difficultyKey": "mythic",
        "seasonRevision": CURRENT_BINDING["seasonRevision"],
        "status": "verified",
        "sourceLabel": "Display-only label",
        "updatedAt": "2026-07-29T10:00:00+08:00",
    }


def regular_rows():
    return {
        "items": [
            {
                "itemId": "1001",
                "name": "Verified Helm",
                "slot": "head",
                "itemLevel": 276,
                "sourceStatus": "verified",
                "payload": {
                    "iconUrl": "/runtime-media/item/1001.webp",
                    "armorType": "Cloth",
                    "inventoryType": "head",
                    "requiredClassIds": [2],
                    "displayLabel": "Ignored transient label",
                    "updatedAt": "2026-07-29T10:00:00+08:00",
                },
                "hasSourceRefs": True,
                "hasVariantRefs": True,
            }
        ],
        "sources": [source("1001")],
        "variants": [
            {
                "variantId": "variant-hero-6",
                "variantKey": "hero-6",
                "itemId": "1001",
                "rowFamily": "browse",
                "trackKey": "hero",
                "trackRank": 6,
                "itemLevel": 276,
                "slot": "head",
                "sourceType": "raid",
                "bonusIds": ["9001", "9002"],
                "staticStats": {
                    "haste_rating": 120,
                    "mastery_rating": 80,
                },
                "status": "verified",
            }
        ],
        "options": [],
    }


def crafted_rows():
    rows = {
        "items": [
            {
                "itemId": "crafted-1",
                "name": "Crafted Helm",
                "slot": "head",
                "itemLevel": 285,
                "sourceStatus": "verified",
                "payload": {
                    "armorType": "Cloth",
                    "inventoryType": "head",
                },
                "hasSourceRefs": True,
                "hasVariantRefs": True,
            }
        ],
        "sources": [
            {
                **source("crafted-1", "crafted"),
                "sourceType": "crafted",
                "instanceId": "",
                "encounterId": "",
                "difficultyKey": "",
            }
        ],
        "variants": [],
        "options": [],
    }
    for index in range(6):
        rows["variants"].append(
            {
                "variantId": f"crafted-1-{index}",
                "variantKey": f"crafted-1-stats-{index}",
                "itemId": "crafted-1",
                "rowFamily": "browse",
                "trackKey": "myth",
                "itemLevel": 285,
                "slot": "head",
                "sourceType": "crafted",
                "bonusIds": ["13622"],
                "simcOptions": {
                    "crafted_stats": f"{32 + index}/{36 + index}",
                },
                "staticStats": {
                    "stamina": 100,
                    "haste_rating": 20 + index,
                },
                "status": "verified",
            }
        )
    return rows


class GearCatalogRevisionTest(unittest.TestCase):
    def test_same_content_has_same_catalog_identity_and_derived_browse_key(self):
        first = build_catalog_revision(CURRENT_BINDING, regular_rows())
        second_binding = {
            **CURRENT_BINDING,
            "manifestRevision": "season-manifest:sha256:" + ("4" * 64),
            "gearReleaseId": "gear-release:sha256:" + ("5" * 64),
        }
        second_rows = regular_rows()
        second_rows["items"][0]["payload"]["updatedAt"] = (
            "2026-07-29T12:00:00+08:00"
        )
        second_rows["items"][0]["payload"]["displayLabel"] = "Different label"
        second_rows["sources"][0]["sourceLabel"] = "Different source label"
        second_rows["sources"][0]["updatedAt"] = "2026-07-29T12:00:00+08:00"
        second_rows["variants"][0]["bonusIds"] = ["9002", "9001"]
        second = build_catalog_revision(second_binding, second_rows)

        self.assertEqual(first["status"], "verified")
        self.assertEqual(second["status"], "verified")
        self.assertEqual(first["catalogRevision"], second["catalogRevision"])
        self.assertNotEqual(
            first["provenance"]["sourceGearReleaseId"],
            second["provenance"]["sourceGearReleaseId"],
        )
        self.assertRegex(
            first["catalogRevision"],
            r"^gear-catalog:sha256:[0-9a-f]{64}$",
        )
        variant = first["browseVariants"][0]
        self.assertNotIn("variantShapeKey", variant)
        self.assertEqual(
            variant["browseVariantKey"],
            catalog_browse_variant_key(
                first["catalogRevision"],
                variant["itemId"],
                variant["progressionState"],
            ),
        )
        self.assertRegex(
            variant["browseVariantKey"],
            r"^browse-variant:sha256:[0-9a-f]{64}$",
        )
        self.assertEqual(verify_catalog_revision(first), [])

    def test_verification_canonicalizes_persisted_member_order(self):
        rows = regular_rows()
        rows["items"].append(
            {
                "itemId": "1002",
                "name": "Verified Shoulders",
                "slot": "shoulder",
                "itemLevel": 276,
                "sourceStatus": "verified",
                "payload": {"armorType": "Cloth"},
                "hasSourceRefs": True,
                "hasVariantRefs": True,
            }
        )
        rows["sources"].append(source("1002"))
        rows["variants"].append(
            {
                **rows["variants"][0],
                "variantId": "variant-hero-6-shoulder",
                "variantKey": "hero-6-shoulder",
                "itemId": "1002",
                "slot": "shoulder",
            }
        )
        result = build_catalog_revision(CURRENT_BINDING, rows)
        persisted = copy.deepcopy(result)
        persisted["itemDefinitions"].reverse()
        persisted["browseVariants"].reverse()

        self.assertEqual(result["status"], "verified")
        self.assertEqual(verify_catalog_revision(persisted), [])

    def test_observed_exact_instance_authorizes_ordinary_ascendant(self):
        rows = regular_rows()
        rows["variants"] = [
            {
                "variantId": "ascendant-browse",
                "variantKey": "ascendant-browse",
                "itemId": "1001",
                "rowFamily": "browse",
                "trackKey": "void_upgrade",
                "itemLevel": 298,
                "slot": "chest",
                "sourceType": "raid",
                "bonusIds": [],
                "staticStats": {"stamina": 120},
                "status": "verified",
            },
            {
                "variantId": "ascendant-observed",
                "variantKey": "ascendant-observed",
                "itemId": "1001",
                "rowFamily": "exact_instance",
                "itemLevel": 298,
                "slot": "chest",
                "sourceType": "observed_profile",
                "bonusIds": [],
                "staticStats": {"stamina": 120},
                "status": "verified",
            },
        ]
        rows["items"][0]["slot"] = "chest"
        rows["items"][0]["itemLevel"] = 298

        result = build_catalog_revision(CURRENT_BINDING, rows)

        self.assertEqual(result["status"], "verified")
        self.assertEqual(len(result["browseVariants"]), 1)
        self.assertEqual(
            result["browseVariants"][0]["progressionKind"],
            "ascendant",
        )

    def test_crafted_stat_choices_collapse_without_entering_static_facts(self):
        result = build_catalog_revision(CURRENT_BINDING, crafted_rows())

        self.assertEqual(result["status"], "verified")
        self.assertEqual(len(result["browseVariants"]), 1)
        self.assertEqual(
            result["browseVariants"][0]["staticFacts"],
            {"stamina": 100},
        )
        self.assertEqual(
            result["browseVariants"][0]["sourceVariantKeys"],
            [f"crafted-1-stats-{index}" for index in range(6)],
        )
        self.assertEqual(
            result["contentSummary"]["craftedEnhancementSelectionRowCount"],
            6,
        )
        self.assertEqual(
            result["contentSummary"]["collapsedCraftedVariantRowCount"],
            5,
        )
        serialized = str(result["browseVariants"][0])
        self.assertNotIn("crafted_stats", serialized)
        self.assertNotIn("haste_rating", serialized)

    def test_crafted_invariant_fact_conflict_blocks_entire_catalog(self):
        rows = crafted_rows()
        rows["variants"][-1]["staticStats"]["stamina"] = 101

        result = build_catalog_revision(CURRENT_BINDING, rows)

        self.assertEqual(result["status"], "blocked")
        self.assertNotIn("catalogRevision", result)
        self.assertIn(
            "CATALOG_CRAFTED_INVARIANT_FACT_CONFLICT",
            result["problemCodes"],
        )

    def test_duplicate_noncrafted_progression_blocks_entire_catalog(self):
        rows = regular_rows()
        duplicate = copy.deepcopy(rows["variants"][0])
        duplicate["variantId"] = "variant-hero-6-duplicate"
        duplicate["variantKey"] = "hero-6-duplicate"
        rows["variants"].append(duplicate)

        result = build_catalog_revision(CURRENT_BINDING, rows)

        self.assertEqual(result["status"], "blocked")
        self.assertIn(
            "CATALOG_VARIANT_CANONICAL_DUPLICATE",
            result["problemCodes"],
        )

    def test_missing_source_static_fact_or_track_authority_fails_closed(self):
        cases = []

        no_source = regular_rows()
        no_source["sources"] = []
        cases.append(("CATALOG_ITEM_SOURCE_MISSING", no_source, CURRENT_BINDING))

        no_stats = regular_rows()
        no_stats["variants"][0]["staticStats"] = {}
        cases.append(
            ("CATALOG_VARIANT_STATIC_STATS_MISSING", no_stats, CURRENT_BINDING)
        )

        wrong_rule = {
            **CURRENT_BINDING,
            "gearRuleRevision": "gear-rule-matrix-unknown",
        }
        cases.append(
            ("TRACK_AUTHORITY_BINDING_UNSUPPORTED", regular_rows(), wrong_rule)
        )

        for code, rows, binding in cases:
            with self.subTest(code=code):
                result = build_catalog_revision(binding, rows)
                self.assertEqual(result["status"], "blocked")
                self.assertIn(code, result["problemCodes"])
                self.assertNotIn("catalogRevision", result)

    def test_item_membership_requires_browse_usage(self):
        rows = regular_rows()
        rows["items"].extend(
            [
                {
                    "itemId": "exact-only",
                    "name": "Observed Exact Item",
                    "slot": "finger1",
                    "itemLevel": 272,
                    "sourceStatus": "unknown",
                    "hasSourceRefs": True,
                    "hasVariantRefs": True,
                },
                {
                    "itemId": "unreferenced-metadata",
                    "name": "Historical Metadata",
                    "slot": "main_hand",
                    "sourceStatus": "unknown",
                    "hasSourceRefs": False,
                    "hasVariantRefs": False,
                },
                {
                    "itemId": "source-only",
                    "name": "Source Without Verified Variant",
                    "slot": "trinket1",
                    "sourceStatus": "verified",
                    "hasSourceRefs": True,
                    "hasVariantRefs": False,
                },
            ]
        )
        rows["sources"].extend(
            [
                {
                    **source("exact-only", "observed"),
                    "sourceType": "observed_profile",
                },
                source("source-only", "source-only"),
            ]
        )
        rows["variants"].append(
            {
                "variantId": "observed-exact-only",
                "variantKey": "observed-exact-only",
                "itemId": "exact-only",
                "rowFamily": "exact_instance",
                "itemLevel": 272,
                "slot": "finger1",
                "sourceType": "observed_profile",
                "bonusIds": ["13335"],
                "staticStats": {"haste_rating": 90},
                "status": "verified",
            }
        )

        result = build_catalog_revision(CURRENT_BINDING, rows)

        self.assertEqual(result["status"], "verified")
        definitions = {
            row["itemId"]: row
            for row in result["itemDefinitions"]
        }
        self.assertEqual(set(definitions), {"1001"})
        exact_variants = [
            row
            for row in result["browseVariants"]
            if row["itemId"] == "exact-only"
        ]
        self.assertEqual(exact_variants, [])
        self.assertEqual(
            result["contentSummary"]["excludedDormantItemCount"],
            3,
        )

    def test_exact_instances_do_not_create_or_extend_browse_variants(self):
        rows = regular_rows()
        first = {
            "variantId": "observed-hero-6-a",
            "variantKey": "observed-hero-6-a",
            "itemId": "1001",
            "rowFamily": "exact_instance",
            "itemLevel": 276,
            "slot": "head",
            "sourceType": "observed_profile",
            "bonusIds": ["13334", "9001"],
            "staticStats": {
                "haste_rating": 120,
                "mastery_rating": 80,
            },
            "simcOptions": {
                "ilevel": "276",
                "bonus_id": "13334/9001",
                "gem_id": "240892",
            },
            "status": "verified",
        }
        second = copy.deepcopy(first)
        second["variantId"] = "observed-hero-6-b"
        second["variantKey"] = "observed-hero-6-b"
        second["simcOptions"]["gem_id"] = "240897"
        rows["variants"].extend([first, second])

        result = build_catalog_revision(CURRENT_BINDING, rows)

        self.assertEqual(result["status"], "verified")
        self.assertEqual(len(result["browseVariants"]), 1)
        self.assertEqual(
            result["browseVariants"][0]["sourceFamilies"],
            ["browse"],
        )
        self.assertEqual(
            result["browseVariants"][0]["sourceVariantKeys"],
            ["hero-6"],
        )
        self.assertEqual(
            result["contentSummary"]["exactDerivedVariantCount"],
            0,
        )

    def test_exact_instances_do_not_create_browse_variants(self):
        rows = regular_rows()
        rows["variants"] = []
        for suffix, stats in (
            ("haste", {"stamina": 100, "haste_rating": 80}),
            ("mastery", {"stamina": 100, "mastery_rating": 80}),
        ):
            rows["variants"].append(
                {
                    "variantId": f"observed-{suffix}",
                    "variantKey": f"observed-{suffix}",
                    "itemId": "1001",
                    "rowFamily": "exact_instance",
                    "itemLevel": 276,
                    "slot": "head",
                    "sourceType": "observed_profile",
                    "bonusIds": ["13334", "9001"],
                    "staticStats": stats,
                    "simcOptions": {
                        "ilevel": "276",
                        "bonus_id": "13334/9001",
                    },
                    "status": "verified",
                }
            )

        result = build_catalog_revision(CURRENT_BINDING, rows)

        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["browseVariants"], [])
        self.assertEqual(result["itemDefinitions"], [])
        self.assertEqual(result["contentSummary"]["exactDerivedVariantCount"], 0)
        self.assertEqual(verify_catalog_revision(result), [])

    def test_duplicate_normal_progression_with_a_second_shape_blocks_catalog(
        self,
    ):
        rows = regular_rows()
        duplicate = copy.deepcopy(rows["variants"][0])
        duplicate["variantId"] = "variant-hero-6-other-shape"
        duplicate["variantKey"] = "hero-6-other-shape"
        duplicate["staticStats"] = {
            "haste_rating": 121,
            "mastery_rating": 80,
        }
        rows["variants"].append(duplicate)

        result = build_catalog_revision(CURRENT_BINDING, rows)

        self.assertEqual(result["status"], "blocked")
        self.assertIn(
            "CATALOG_VARIANT_CANONICAL_DUPLICATE",
            result["problemCodes"],
        )

    def test_type_unknown_nonportable_item_is_excluded_from_browse_membership(
        self,
    ):
        rows = regular_rows()
        rows["items"][0]["payload"].pop("armorType")

        result = build_catalog_revision(CURRENT_BINDING, rows)

        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["itemDefinitions"], [])
        self.assertEqual(result["browseVariants"], [])
        self.assertEqual(result["contentSummary"]["typeExcludedItemCount"], 1)
        self.assertEqual(
            result["contentSummary"]["typeExcludedBrowseRowCount"],
            1,
        )

    def test_catalog_identity_does_not_include_derived_browse_key(self):
        result = build_catalog_revision(CURRENT_BINDING, regular_rows())
        tampered = copy.deepcopy(result)
        tampered["browseVariants"][0]["browseVariantKey"] = (
            "browse-variant:sha256:" + ("f" * 64)
        )

        problems = verify_catalog_revision(tampered)

        self.assertIn("CATALOG_BROWSE_VARIANT_KEY_MISMATCH", problems)
        self.assertNotIn("CATALOG_REVISION_MISMATCH", problems)


if __name__ == "__main__":
    unittest.main()
