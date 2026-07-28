import copy
import re
import unittest

from server.gear_catalog_migration_audit import (
    audit_catalog_mapping,
    audit_resource_baseline,
    audit_spec_coverage,
    audit_template_exactness,
    build_phase0_report,
    validate_phase0_report,
)


def complete_catalog_rows():
    return {
        "items": [
            {
                "itemId": "1001",
                "slot": "head",
                "name": "Verified Helm",
                "payload": {"sourceStatus": "verified"},
            }
        ],
        "variants": [
            {
                "variantId": "hero-1",
                "itemId": "1001",
                "rowFamily": "browse",
                "trackKey": "hero",
                "trackRank": 6,
                "itemLevel": 285,
                "bonusIds": ["9001", "9002"],
                "staticStats": {"haste_rating": 120, "mastery_rating": 80},
            }
        ],
        "options": [
            {
                "optionId": "gem-1",
                "optionKey": "gem:240892",
                "optionType": "gem",
                "status": "verified",
            }
        ],
    }


def exact_template(template_id="template-1"):
    return {
        "templateIdentity": template_id,
        "displayName": "Ignored display label",
        "updatedAt": "2026-07-28T10:00:00+08:00",
        "gearItems": [
            {
                "slot": "head",
                "itemId": "1001",
                "bonusIds": ["9002", "9001"],
                "trackKey": "hero",
                "rank": 3,
                "ilevel": 278,
                "gemIds": [],
                "enchantId": "",
                "craftedStats": [],
                "embellishmentIds": [],
            }
        ],
    }


def complete_spec_rows():
    return [
        {
            "classKey": f"class-{index // 4}",
            "specKey": f"spec-{index}",
            "status": "verified",
            "candidateCount": 12,
            "blockerCodes": [],
        }
        for index in range(40)
    ]


def complete_resource_rows():
    return {
        "databaseRelationsBytes": 1024,
        "activeMaterializationBytes": 512,
        "rollbackMaterializationBytes": 256,
        "diagnosticBytesObserved": 64,
        "filesystemTotalBytes": 10_000,
        "filesystemUsedBytes": 4_000,
        "filesystemFreeBytes": 6_000,
        "filesystemUsedPercent": 40.0,
        "peakRssObservedBytes": 2048,
        "temporaryBytesObserved": 1024,
    }


def complete_inputs():
    return {
        "catalog": audit_catalog_mapping(
            {
                "manifestRevision": "season-manifest:sha256:" + ("1" * 64),
                "gearReleaseId": "gear-release:sha256:" + ("2" * 64),
            },
            complete_catalog_rows(),
        ),
        "templates": audit_template_exactness(
            [exact_template("community-1")],
            [exact_template("personal-1")],
        ),
        "coverage": audit_spec_coverage(complete_spec_rows()),
        "resources": audit_resource_baseline(complete_resource_rows()),
        "callers": {
            "schemaRevision": "gear-catalog-callers-v1",
            "reportId": "gear-catalog-callers:sha256:" + ("3" * 64),
            "status": "verified",
            "runtimeCallerCount": 3,
            "unresolvedCount": 0,
        },
    }


class GearCatalogMigrationAuditTest(unittest.TestCase):
    def test_same_inputs_have_same_report_id_despite_observation_time(self):
        first = build_phase0_report(
            **complete_inputs(),
            observed_at="2026-07-28T10:00:00+08:00",
        )
        second = build_phase0_report(
            **complete_inputs(),
            observed_at="2026-07-28T11:00:00+08:00",
        )

        self.assertEqual(first["reportId"], second["reportId"])
        self.assertNotEqual(first["observedAt"], second["observedAt"])
        self.assertRegex(
            first["reportId"],
            r"^catalog-migration-audit:sha256:[0-9a-f]{64}$",
        )

    def test_blocked_spec_is_not_counted_as_covered(self):
        result = audit_spec_coverage(
            [
                {
                    "classKey": "mage",
                    "specKey": "frost",
                    "status": "verified",
                    "candidateCount": 12,
                },
                {
                    "classKey": "warrior",
                    "specKey": "arms",
                    "status": "blocked",
                    "candidateCount": 0,
                },
            ]
        )

        self.assertEqual(result["verifiedSpecCount"], 1)
        self.assertEqual(result["blockedSpecCount"], 1)
        self.assertFalse(result["complete"])
        self.assertEqual(result["status"], "blocked")

    def test_missing_peak_rss_stays_unknown(self):
        rows = complete_resource_rows()
        rows["peakRssObservedBytes"] = None

        result = audit_resource_baseline(rows)

        self.assertEqual(result["peakRss"]["status"], "unknown")
        self.assertIsNone(result["peakRss"]["bytes"])
        self.assertEqual(result["status"], "partial")
        self.assertIn("RESOURCE_BASELINE_UNKNOWN", result["problemCodes"])

    def test_browse_variant_requires_track_rank_ilevel_bonus_ids_and_static_stats(self):
        rows = complete_catalog_rows()
        rows["variants"][0].pop("trackRank")
        rows["variants"][0].pop("staticStats")

        result = audit_catalog_mapping(
            {"manifestRevision": "manifest-1", "gearReleaseId": "release-1"},
            rows,
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["mappedVariantCount"], 0)
        self.assertIn("CATALOG_VARIANT_RANK_MISSING", result["problemCodes"])
        self.assertIn("CATALOG_VARIANT_STATIC_STATS_MISSING", result["problemCodes"])

    def test_exact_instance_ranking_field_never_becomes_browse_track_rank(self):
        rows = complete_catalog_rows()
        browse = rows["variants"][0]
        rows["variants"].append(
            {
                "variantId": "observed-profile-instance",
                "itemId": "1001",
                "rowFamily": "exact_instance",
                "difficultyKey": "observed_profile",
                "rank": 527,
                "rankingEvidence": {"rank": 527, "score": 3400},
                "itemLevel": 278,
                "bonusIds": ["9100"],
            }
        )

        result = audit_catalog_mapping(
            {"manifestRevision": "manifest-1", "gearReleaseId": "release-1"},
            rows,
        )

        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["variantTotal"], 2)
        self.assertEqual(result["browseVariantTotal"], 1)
        self.assertEqual(result["mappedBrowseVariantCount"], 1)
        self.assertEqual(result["excludedExactInstanceCount"], 1)
        self.assertNotIn("CATALOG_VARIANT_TRACK_MISSING", result["problemCodes"])
        self.assertNotIn("CATALOG_VARIANT_RANK_MISSING", result["problemCodes"])

    def test_generic_rank_never_satisfies_browse_track_rank(self):
        rows = complete_catalog_rows()
        browse = rows["variants"][0]
        browse.pop("trackRank")
        browse["rank"] = 527

        result = audit_catalog_mapping(
            {"manifestRevision": "manifest-1", "gearReleaseId": "release-1"},
            rows,
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["mappedBrowseVariantCount"], 0)
        self.assertIn("CATALOG_VARIANT_RANK_MISSING", result["problemCodes"])

    def test_unreferenced_empty_slot_item_is_explicitly_excluded(self):
        rows = complete_catalog_rows()
        rows["items"].append(
            {
                "itemId": "metadata-only",
                "slot": "",
                "hasSourceRefs": False,
                "hasVariantRefs": False,
            }
        )

        result = audit_catalog_mapping(
            {"manifestRevision": "manifest-1", "gearReleaseId": "release-1"},
            rows,
        )

        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["mappedItemCount"], 1)
        self.assertEqual(result["excludedNonCatalogItemCount"], 1)
        self.assertNotIn("CATALOG_ITEM_SLOT_MISSING", result["problemCodes"])

    def test_referenced_empty_slot_item_remains_blocked(self):
        rows = complete_catalog_rows()
        rows["items"].append(
            {
                "itemId": "referenced-without-slot",
                "slot": "",
                "hasSourceRefs": True,
                "hasVariantRefs": False,
            }
        )

        result = audit_catalog_mapping(
            {"manifestRevision": "manifest-1", "gearReleaseId": "release-1"},
            rows,
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result.get("excludedNonCatalogItemCount", -1), 0)
        self.assertIn("CATALOG_ITEM_SLOT_MISSING", result["problemCodes"])

    def test_placeholder_and_preview_rows_are_explicit_non_browse_exclusions(self):
        rows = complete_catalog_rows()
        rows["variants"].extend(
            [
                {
                    "variantId": "needs-variant",
                    "itemId": "1001",
                    "rowFamily": "placeholder",
                    "difficultyKey": "needs-variant",
                    "itemLevel": 0,
                    "bonusIds": [],
                    "staticStats": {},
                },
                {
                    "variantId": "battle-net-preview",
                    "itemId": "1001",
                    "rowFamily": "reference",
                    "difficultyKey": "battle_net_preview",
                    "itemLevel": 250,
                    "bonusIds": [],
                    "staticStats": {},
                },
            ]
        )

        result = audit_catalog_mapping(
            {"manifestRevision": "manifest-1", "gearReleaseId": "release-1"},
            rows,
        )

        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["variantTotal"], 3)
        self.assertEqual(result["browseVariantTotal"], 1)
        self.assertEqual(result["mappedBrowseVariantCount"], 1)
        self.assertEqual(result["excludedPlaceholderVariantCount"], 1)
        self.assertEqual(result["excludedReferenceVariantCount"], 1)

    def test_duplicate_highest_rank_for_one_item_track_is_blocked(self):
        rows = complete_catalog_rows()
        duplicate = copy.deepcopy(rows["variants"][0])
        duplicate["variantId"] = "hero-duplicate"
        duplicate["bonusIds"] = ["9010"]
        rows["variants"].append(duplicate)

        result = audit_catalog_mapping(
            {"manifestRevision": "manifest-1", "gearReleaseId": "release-1"},
            rows,
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["mappedVariantCount"], 0)
        self.assertIn("CATALOG_VARIANT_HIGHEST_RANK_AMBIGUOUS", result["problemCodes"])

    def test_catalog_problem_evidence_is_counted_and_sample_bounded(self):
        rows = complete_catalog_rows()
        rows["variants"] = [
            {
                "variantId": f"invalid-{index}",
                "itemId": "1001",
                "rowFamily": "browse",
                "trackKey": "hero",
                "trackRank": index + 1,
                "itemLevel": 285,
                "bonusIds": ["9001"],
            }
            for index in range(50)
        ]

        result = audit_catalog_mapping(
            {"manifestRevision": "manifest-1", "gearReleaseId": "release-1"},
            rows,
        )

        self.assertEqual(
            result["problemCounts"]["CATALOG_VARIANT_STATIC_STATS_MISSING"],
            50,
        )
        self.assertLessEqual(len(result["problems"]), 20)

    def test_exact_template_preserves_intermediate_rank_and_allows_empty_enhancements(self):
        result = audit_template_exactness(
            [exact_template("community-hero-3")],
            [exact_template("personal-hero-3")],
        )

        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["community"]["exactCount"], 1)
        self.assertEqual(result["personal"]["exactCount"], 1)
        self.assertEqual(result["community"]["blockedCount"], 0)

    def test_missing_track_rank_is_partial_and_malformed_explicit_gem_is_blocked(self):
        missing_rank = exact_template("missing-rank")
        missing_rank["gearItems"][0].pop("rank")
        malformed_gem = exact_template("malformed-gem")
        malformed_gem["gearItems"][0]["gemIds"] = ["240892", None]

        result = audit_template_exactness([missing_rank, malformed_gem], [])

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["community"]["partialCount"], 1)
        self.assertEqual(result["community"]["blockedCount"], 1)
        self.assertIn("TEMPLATE_EXACT_TRACK_RANK_MISSING", result["problemCodes"])
        self.assertIn("TEMPLATE_EXACT_GEM_IDS_MALFORMED", result["problemCodes"])

    def test_missing_active_community_templates_are_blocked_but_personal_can_be_empty(self):
        result = audit_template_exactness([], [])

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["community"]["status"], "blocked")
        self.assertEqual(result["personal"]["status"], "verified")
        self.assertIn(
            "TEMPLATE_EXACT_COMMUNITY_MISSING",
            result["problemCodes"],
        )

    def test_template_samples_are_anonymous_sorted_deduplicated_and_capped(self):
        templates = [exact_template(f"template-{index}") for index in range(25)]
        templates.append(copy.deepcopy(templates[0]))

        result = audit_template_exactness(templates, [])
        samples = result["community"]["sampleHashes"]

        self.assertEqual(len(samples), 20)
        self.assertEqual(samples, sorted(set(samples)))
        self.assertTrue(all(re.fullmatch(r"sha256:[0-9a-f]{64}", value) for value in samples))
        self.assertTrue(all("template-" not in value for value in samples))

    def test_display_label_and_database_row_id_do_not_change_report_identity(self):
        inputs = complete_inputs()
        first = build_phase0_report(
            **inputs,
            observed_at="2026-07-28T10:00:00+08:00",
        )
        changed_inputs = copy.deepcopy(inputs)
        changed_inputs["templates"]["community"]["displayLabel"] = "new label"
        changed_inputs["templates"]["community"]["databaseRowId"] = "row-999"
        second = build_phase0_report(
            **changed_inputs,
            observed_at="2026-07-28T10:00:00+08:00",
        )

        self.assertEqual(first["reportId"], second["reportId"])

    def test_report_status_precedence_and_validation(self):
        inputs = complete_inputs()
        inputs["resources"] = audit_resource_baseline(
            {**complete_resource_rows(), "temporaryBytesObserved": None}
        )
        report = build_phase0_report(
            **inputs,
            observed_at="2026-07-28T10:00:00+08:00",
        )

        self.assertEqual(report["status"], "partial")
        self.assertEqual(validate_phase0_report(report), [])

        damaged = copy.deepcopy(report)
        damaged["catalogMapping"] = {}
        issues = validate_phase0_report(damaged)
        self.assertIn("AUDIT_SECTION_INVALID", [issue["code"] for issue in issues])


if __name__ == "__main__":
    unittest.main()
