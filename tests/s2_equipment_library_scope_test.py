import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "server" / "data" / "midnight-season-2" / "source-policy.json"


class S2EquipmentLibraryScopeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))

    def test_midnight_s2_scope_is_four_logical_sources(self):
        self.assertEqual(
            self.policy["sourcePolicyRevision"],
            "midnight-season-2-equipment-library-scope-v2",
        )
        scope = self.policy["scopeContract"]
        expected = [
            "raid:midnight-season-2",
            "mythic_plus:midnight-season-2",
            "crafted:midnight-season-2",
            "tier_set:midnight-season-2",
        ]
        self.assertEqual(scope["logicalSourceCount"], 4)
        self.assertEqual(scope["logicalSourceKeys"], expected)
        self.assertTrue(scope["raidIncludesLair"])
        self.assertTrue(scope["lairRawSourceTypePreserved"])
        self.assertTrue(scope["tierSetIsIndependentMembershipDimension"])

        self.assertEqual(
            [source["sourceKey"] for source in self.policy["sources"]],
            expected,
        )
        raid = self.policy["sources"][0]
        self.assertEqual(raid["productLabel"], "团本（包括巢穴）")
        self.assertEqual(raid["rawSourceTypes"], ["raid", "lair"])
        self.assertIn("lair:the-tidebound-grotto", raid["rawSourceKeys"])

    def test_excluded_sources_are_not_required_membership_sources(self):
        excluded = set(self.policy["scopeContract"]["excludedSourceTypes"])
        self.assertEqual(
            excluded,
            {"dungeon", "delve", "prey", "great_vault", "world_content"},
        )
        self.assertFalse(
            any(source["sourceType"] in excluded for source in self.policy["sources"])
        )

    def test_db2_policy_is_bounded_and_does_not_change_product_scope(self):
        db2 = self.policy["db2Policy"]
        self.assertEqual(db2["status"], "authorized_bounded")
        self.assertEqual(db2["allowlistRef"], "db2-field-allowlist-v1.json")
        self.assertEqual(
            db2["allowlistRevision"],
            "s2-limited-client-db2-field-allowlist-v1",
        )
        self.assertEqual(db2["authority"], "official_client_db2")
        self.assertEqual(db2["transportRole"], "transport_only")
        self.assertFalse(db2["rawDb2Persisted"])
        self.assertEqual(db2["queryOperator"], "exact")
        self.assertEqual(db2["clientBuild"], "12.1.0.69299")
        self.assertNotIn("great_vault", db2["allowedTargetScope"])
        self.assertEqual(
            set(db2["allowedPurposeKeys"]),
            {
                "crafted_recipe_output_quality",
                "crafted_secondary_and_embellishment_compatibility",
                "item_static_attributes_and_variant_edges",
                "tier_set_conversion_preservation",
                "mythic_plus_cap_track",
                "source_context_map_difficulty",
                "mythic_plus_journal_item_scope",
                "item_bonus_tree_composition_and_level_delta",
                "enhancement_identity_and_simc_serialization",
            },
        )

    def test_mythic_plus_journal_item_scope_is_exact_and_fail_closed(self):
        mplus = next(
            source
            for source in self.policy["sources"]
            if source["sourceType"] == "mythic_plus"
        )
        journal = mplus["journalItemScope"]
        self.assertEqual(journal["table"], "JournalEncounterItem")
        self.assertEqual(journal["authority"], "official_client_db2")
        self.assertIn("DifficultyMask=-1", journal["includeWhen"])
        self.assertIn("nonnegative", journal["excludeWhen"])
        self.assertEqual(journal["unknownPolicy"], "UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
