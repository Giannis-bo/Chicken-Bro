import unittest

from server.gear_track_authority import (
    TRACK_AUTHORITY_RULE_REVISION,
    TRACK_AUTHORITY_SCHEMA_REVISION,
    resolve_exact_instance_progression,
    resolve_legacy_browse_progression,
    track_authority_for_binding,
)


CURRENT_BINDING = {
    "seasonRevision": "season-17-f131dd36ddf1",
    "gearRuleRevision": "gear-rule-matrix-v1",
}


def _problem_codes(result):
    return [problem.get("code") for problem in result.get("problems", [])]


class GearTrackAuthorityTest(unittest.TestCase):
    def test_verified_exact_instance_uses_bound_level_and_source_evidence(self):
        regular = resolve_exact_instance_progression(
            CURRENT_BINDING,
            {
                "rowFamily": "exact_instance",
                "status": "verified",
                "itemId": "1001",
                "variantKey": "observed-289-a",
                "itemLevel": 289,
                "slot": "head",
                "bonusIds": ["13440"],
            },
        )
        crafted = resolve_exact_instance_progression(
            CURRENT_BINDING,
            {
                "rowFamily": "exact_instance",
                "status": "verified",
                "itemId": "1002",
                "variantKey": "observed-285-b",
                "itemLevel": 285,
                "slot": "chest",
                "hasCraftedSource": True,
                "bonusIds": ["13622"],
            },
        )
        ascendant = resolve_exact_instance_progression(
            CURRENT_BINDING,
            {
                "rowFamily": "exact_instance",
                "status": "verified",
                "itemId": "1003",
                "variantKey": "observed-298-c",
                "itemLevel": 298,
                "slot": "trinket1",
                "bonusIds": ["13654"],
            },
        )

        self.assertEqual(
            regular["progressionState"],
            {
                "kind": "upgrade_track",
                "trackKey": "myth",
                "rank": 6,
                "maxRank": 6,
            },
        )
        self.assertEqual(
            crafted["progressionState"],
            {
                "kind": "crafted_quality",
                "trackKey": "myth",
                "qualityKey": "radiance_max",
            },
        )
        self.assertEqual(
            ascendant["progressionState"],
            {
                "kind": "ascendant",
                "trackKey": "void_upgrade",
                "originKind": "upgrade_track",
            },
        )

    def test_exact_instance_fails_closed_without_identity_or_crafted_source(self):
        missing_identity = resolve_exact_instance_progression(
            CURRENT_BINDING,
            {
                "rowFamily": "exact_instance",
                "status": "verified",
                "itemId": "1001",
                "itemLevel": 289,
                "bonusIds": ["13440"],
            },
        )
        unproven_crafted = resolve_exact_instance_progression(
            CURRENT_BINDING,
            {
                "rowFamily": "exact_instance",
                "status": "verified",
                "itemId": "1002",
                "variantKey": "observed-285-b",
                "itemLevel": 285,
                "slot": "chest",
                "hasCraftedSource": False,
                "bonusIds": ["13622"],
            },
        )
        unsupported_level = resolve_exact_instance_progression(
            CURRENT_BINDING,
            {
                "rowFamily": "exact_instance",
                "status": "verified",
                "itemId": "1003",
                "variantKey": "observed-246-c",
                "itemLevel": 246,
                "slot": "head",
            },
        )

        self.assertEqual(
            _problem_codes(missing_identity),
            ["TRACK_AUTHORITY_EXACT_IDENTITY_MISSING"],
        )
        self.assertEqual(
            _problem_codes(unproven_crafted),
            ["TRACK_AUTHORITY_EXACT_CRAFTED_SOURCE_MISSING"],
        )
        self.assertEqual(
            _problem_codes(unsupported_level),
            ["TRACK_AUTHORITY_EXACT_TRACK_EVIDENCE_MISSING"],
        )

    def test_exact_upgrade_rank_requires_track_marker_and_bound_ladder(self):
        myth_five = resolve_exact_instance_progression(
            CURRENT_BINDING,
            {
                "rowFamily": "exact_instance",
                "status": "verified",
                "itemId": "1001",
                "variantKey": "observed-285-a",
                "itemLevel": 285,
                "slot": "finger1",
                "bonusIds": ["13335"],
            },
        )
        hero_six = resolve_exact_instance_progression(
            CURRENT_BINDING,
            {
                "rowFamily": "exact_instance",
                "status": "verified",
                "itemId": "1002",
                "variantKey": "observed-276-b",
                "itemLevel": 276,
                "slot": "hands",
                "bonusIds": ["13334"],
            },
        )
        myth_two = resolve_exact_instance_progression(
            CURRENT_BINDING,
            {
                "rowFamily": "exact_instance",
                "status": "verified",
                "itemId": "1003",
                "variantKey": "observed-276-c",
                "itemLevel": 276,
                "slot": "head",
                "bonusIds": ["13440"],
            },
        )
        ambiguous = resolve_exact_instance_progression(
            CURRENT_BINDING,
            {
                "rowFamily": "exact_instance",
                "status": "verified",
                "itemId": "1004",
                "variantKey": "observed-276-d",
                "itemLevel": 276,
                "slot": "waist",
                "bonusIds": [],
            },
        )

        self.assertEqual(myth_five["progressionState"]["trackKey"], "myth")
        self.assertEqual(myth_five["progressionState"]["rank"], 5)
        self.assertEqual(hero_six["progressionState"]["trackKey"], "hero")
        self.assertEqual(hero_six["progressionState"]["rank"], 6)
        self.assertEqual(myth_two["progressionState"]["trackKey"], "myth")
        self.assertEqual(myth_two["progressionState"]["rank"], 2)
        self.assertEqual(
            _problem_codes(ambiguous),
            ["TRACK_AUTHORITY_EXACT_TRACK_EVIDENCE_MISSING"],
        )

    def test_exact_ascendant_bonus_controls_origin_and_eligibility(self):
        hero = resolve_exact_instance_progression(
            CURRENT_BINDING,
            {
                "rowFamily": "exact_instance",
                "status": "verified",
                "itemId": "1001",
                "variantKey": "observed-285-a",
                "itemLevel": 285,
                "slot": "trinket1",
                "bonusIds": ["13653"],
            },
        )
        crafted = resolve_exact_instance_progression(
            CURRENT_BINDING,
            {
                "rowFamily": "exact_instance",
                "status": "verified",
                "itemId": "1002",
                "variantKey": "observed-295-b",
                "itemLevel": 295,
                "slot": "trinket2",
                "bonusIds": ["13622", "13655"],
                "hasCraftedSource": True,
            },
        )
        invalid_slot = resolve_exact_instance_progression(
            CURRENT_BINDING,
            {
                "rowFamily": "exact_instance",
                "status": "verified",
                "itemId": "1003",
                "variantKey": "observed-285-c",
                "itemLevel": 285,
                "slot": "chest",
                "bonusIds": ["13653"],
            },
        )

        self.assertEqual(
            hero["progressionState"],
            {
                "kind": "ascendant",
                "trackKey": "void_upgrade",
                "originKind": "upgrade_track",
            },
        )
        self.assertEqual(
            crafted["progressionState"]["originKind"],
            "crafted_quality",
        )
        self.assertEqual(
            _problem_codes(invalid_slot),
            ["TRACK_AUTHORITY_ASCENDANT_ELIGIBILITY_UNPROVEN"],
        )

    def test_exact_special_raid_level_keeps_myth_rank_when_no_ascendant_bonus(self):
        resolved = resolve_exact_instance_progression(
            CURRENT_BINDING,
            {
                "rowFamily": "exact_instance",
                "status": "verified",
                "itemId": "1001",
                "variantKey": "observed-298-special",
                "itemLevel": 298,
                "slot": "chest",
                "bonusIds": ["13335"],
            },
        )

        self.assertEqual(
            resolved["progressionState"],
            {
                "kind": "upgrade_track",
                "trackKey": "myth",
                "rank": 6,
                "maxRank": 6,
            },
        )

    def test_current_binding_exposes_verified_versioned_records(self):
        authority = track_authority_for_binding(CURRENT_BINDING)

        self.assertEqual(authority["status"], "verified")
        self.assertEqual(authority["schemaRevision"], TRACK_AUTHORITY_SCHEMA_REVISION)
        self.assertEqual(authority["ruleRevision"], TRACK_AUTHORITY_RULE_REVISION)
        self.assertEqual(authority["seasonRevision"], CURRENT_BINDING["seasonRevision"])
        self.assertEqual(authority["gearRuleRevision"], CURRENT_BINDING["gearRuleRevision"])
        self.assertEqual(len(authority["records"]), 6)
        self.assertGreaterEqual(len(authority["sourceRefs"]), 2)
        self.assertTrue(
            all(record["evidenceStatus"] == "verified" for record in authority["records"])
        )

    def test_regular_track_uses_bound_max_rank_and_ignores_generic_rank(self):
        resolved = resolve_legacy_browse_progression(
            CURRENT_BINDING,
            {
                "difficultyKey": "hero",
                "trackKey": "hero",
                "itemLevel": 276,
                "trackRank": 0,
                "rank": 527,
                "slot": "head",
                "sourceType": "raid",
            },
        )

        self.assertEqual(resolved["status"], "verified")
        self.assertEqual(
            resolved["progressionState"],
            {
                "kind": "upgrade_track",
                "trackKey": "hero",
                "rank": 6,
                "maxRank": 6,
            },
        )
        self.assertNotEqual(resolved["progressionState"]["rank"], 527)
        self.assertEqual(resolved["problems"], [])

    def test_unknown_binding_fails_closed(self):
        resolved = resolve_legacy_browse_progression(
            {
                "seasonRevision": "season-unknown",
                "gearRuleRevision": "gear-rule-matrix-v1",
            },
            {
                "trackKey": "hero",
                "itemLevel": 276,
            },
        )

        self.assertEqual(resolved["status"], "blocked")
        self.assertEqual(
            _problem_codes(resolved),
            ["TRACK_AUTHORITY_BINDING_UNSUPPORTED"],
        )
        self.assertNotIn("progressionState", resolved)

    def test_regular_track_item_level_mismatch_fails_closed(self):
        resolved = resolve_legacy_browse_progression(
            CURRENT_BINDING,
            {
                "trackKey": "hero",
                "itemLevel": 275,
                "trackRank": 6,
                "slot": "head",
                "sourceType": "raid",
            },
        )

        self.assertEqual(resolved["status"], "blocked")
        self.assertEqual(
            _problem_codes(resolved),
            ["TRACK_AUTHORITY_ILEVEL_MISMATCH"],
        )

    def test_regular_track_dedicated_rank_mismatch_fails_closed(self):
        resolved = resolve_legacy_browse_progression(
            CURRENT_BINDING,
            {
                "trackKey": "hero",
                "itemLevel": 276,
                "trackRank": 5,
                "slot": "head",
                "sourceType": "raid",
            },
        )

        self.assertEqual(resolved["status"], "blocked")
        self.assertEqual(
            _problem_codes(resolved),
            ["TRACK_AUTHORITY_RANK_MISMATCH"],
        )

    def test_crafted_quality_has_no_rank_and_requires_crafted_stats(self):
        crafted = resolve_legacy_browse_progression(
            CURRENT_BINDING,
            {
                "trackKey": "myth",
                "itemLevel": 285,
                "trackRank": 0,
                "slot": "head",
                "sourceType": "crafted",
                "simcOptions": {"crafted_stats": "32/36"},
            },
        )
        missing_stats = resolve_legacy_browse_progression(
            CURRENT_BINDING,
            {
                "trackKey": "myth",
                "itemLevel": 285,
                "slot": "head",
                "sourceType": "crafted",
                "simcOptions": {},
            },
        )

        self.assertEqual(crafted["status"], "verified")
        self.assertEqual(
            crafted["progressionState"],
            {
                "kind": "crafted_quality",
                "trackKey": "myth",
                "qualityKey": "radiance_max",
            },
        )
        self.assertNotIn("rank", crafted["progressionState"])
        self.assertEqual(missing_stats["status"], "blocked")
        self.assertEqual(
            _problem_codes(missing_stats),
            ["TRACK_AUTHORITY_CRAFTED_STATS_MISSING"],
        )

    def test_ordinary_ascendant_requires_governed_eligibility(self):
        supported_slot = resolve_legacy_browse_progression(
            CURRENT_BINDING,
            {
                "trackKey": "void_upgrade",
                "itemLevel": 298,
                "slot": "main_hand",
                "sourceType": "dungeon",
            },
        )
        governed_instance = resolve_legacy_browse_progression(
            CURRENT_BINDING,
            {
                "trackKey": "void_upgrade",
                "itemLevel": 298,
                "slot": "chest",
                "sourceType": "raid",
                "hasVoidInstanceSource": True,
            },
        )
        observed_exact = resolve_legacy_browse_progression(
            CURRENT_BINDING,
            {
                "trackKey": "void_upgrade",
                "itemLevel": 298,
                "slot": "head",
                "sourceType": "tier_set",
                "hasObservedAscendantEvidence": True,
            },
        )
        unproven = resolve_legacy_browse_progression(
            CURRENT_BINDING,
            {
                "trackKey": "void_upgrade",
                "itemLevel": 298,
                "slot": "chest",
                "sourceType": "raid",
            },
        )

        for resolved in (supported_slot, governed_instance, observed_exact):
            self.assertEqual(resolved["status"], "verified")
            self.assertEqual(
                resolved["progressionState"],
                {
                    "kind": "ascendant",
                    "trackKey": "void_upgrade",
                    "originKind": "upgrade_track",
                },
            )
            self.assertNotIn("rank", resolved["progressionState"])
        self.assertEqual(unproven["status"], "blocked")
        self.assertEqual(
            _problem_codes(unproven),
            ["TRACK_AUTHORITY_ASCENDANT_ELIGIBILITY_UNPROVEN"],
        )

    def test_crafted_ascendant_requires_track_evidence_and_weapon_slot(self):
        crafted_void = resolve_legacy_browse_progression(
            CURRENT_BINDING,
            {
                "trackKey": "void_upgrade",
                "itemLevel": 295,
                "slot": "off_hand",
                "sourceType": "crafted",
                "hasTrackEvidence": True,
                "simcOptions": {"crafted_stats": "32/36"},
            },
        )
        missing_track_evidence = resolve_legacy_browse_progression(
            CURRENT_BINDING,
            {
                "trackKey": "void_upgrade",
                "itemLevel": 295,
                "slot": "off_hand",
                "sourceType": "crafted",
                "hasTrackEvidence": False,
                "simcOptions": {"crafted_stats": "32/36"},
            },
        )
        unsupported_slot = resolve_legacy_browse_progression(
            CURRENT_BINDING,
            {
                "trackKey": "void_upgrade",
                "itemLevel": 295,
                "slot": "head",
                "sourceType": "crafted",
                "hasTrackEvidence": True,
                "simcOptions": {"crafted_stats": "32/36"},
            },
        )

        self.assertEqual(crafted_void["status"], "verified")
        self.assertEqual(
            crafted_void["progressionState"],
            {
                "kind": "ascendant",
                "trackKey": "void_upgrade",
                "originKind": "crafted_quality",
            },
        )
        self.assertNotIn("rank", crafted_void["progressionState"])
        self.assertEqual(
            _problem_codes(missing_track_evidence),
            ["TRACK_AUTHORITY_TRACK_EVIDENCE_MISSING"],
        )
        self.assertEqual(
            _problem_codes(unsupported_slot),
            ["TRACK_AUTHORITY_CRAFTED_SLOT_UNSUPPORTED"],
        )

    def test_crafted_and_ascendant_rank_is_forbidden(self):
        for row in (
            {
                "trackKey": "myth",
                "itemLevel": 285,
                "trackRank": 6,
                "slot": "head",
                "sourceType": "crafted",
                "simcOptions": {"crafted_stats": "32/36"},
            },
            {
                "trackKey": "void_upgrade",
                "itemLevel": 298,
                "trackRank": 6,
                "slot": "main_hand",
                "sourceType": "raid",
            },
        ):
            with self.subTest(row=row):
                resolved = resolve_legacy_browse_progression(CURRENT_BINDING, row)
                self.assertEqual(resolved["status"], "blocked")
                self.assertEqual(
                    _problem_codes(resolved),
                    ["TRACK_AUTHORITY_RANK_FORBIDDEN"],
                )


if __name__ == "__main__":
    unittest.main()
