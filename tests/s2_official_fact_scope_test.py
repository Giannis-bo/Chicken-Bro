import json
import unittest
from pathlib import Path

from server.s2_official_fact_scope import (
    S2OfficialFactScopeError,
    classify_official_source,
    load_official_fact_scope,
    load_product_content_scope,
    require_official_mythic_cap,
)


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_SCOPE_PATH = (
    ROOT
    / "server"
    / "data"
    / "midnight-season-2"
    / "s2-product-content-scope-v1.json"
)
FACT_SCOPE_PATH = (
    ROOT
    / "server"
    / "data"
    / "midnight-season-2"
    / "official-fact-scope-v1.json"
)


class S2OfficialFactScopeTest(unittest.TestCase):
    def test_loaders_return_the_frozen_four_category_scope(self):
        product_scope = load_product_content_scope(PRODUCT_SCOPE_PATH)
        fact_scope = load_official_fact_scope(FACT_SCOPE_PATH)

        self.assertEqual(product_scope["logicalSourceCount"], 4)
        self.assertEqual(fact_scope["authority"]["kind"], "blizzard_game_data_api")
        self.assertEqual(fact_scope["nonMembershipKinds"], ["great_vault"])

    def test_mythic_plus_requires_official_category_and_mode(self):
        scope = load_product_content_scope(PRODUCT_SCOPE_PATH)
        fact_scope = load_official_fact_scope(FACT_SCOPE_PATH)

        result = classify_official_source(
            official_relation={
                "journalInstanceId": 1030,
                "journalCategory": "DUNGEON",
                "mode": "MYTHIC_KEYSTONE",
                "rawSourceType": "mythic_plus",
                "memberCount": 1,
            },
            product_scope=scope,
            scope=fact_scope,
        )

        self.assertEqual(result["status"], "verified_nonempty")
        self.assertEqual(result["logicalSource"], "mythic_plus")

        drifted = {
            "journalInstanceId": 1030,
            "journalCategory": "DUNGEON",
            "mode": "NORMAL",
            "rawSourceType": "mythic_plus",
            "memberCount": 1,
        }
        self.assertEqual(
            classify_official_source(
                official_relation=drifted,
                product_scope=scope,
                scope=fact_scope,
            )["status"],
            "UNVERIFIED",
        )

    def test_lair_is_grouped_as_raid_but_raw_lair_is_preserved(self):
        result = classify_official_source(
            official_relation={
                "journalInstanceId": 1317,
                "encounterId": 2849,
                "journalCategory": "RAID",
                "mode": "MYTHIC",
                "rawSourceType": "lair",
                "memberCount": 1,
            },
            product_scope=load_product_content_scope(PRODUCT_SCOPE_PATH),
            scope=load_official_fact_scope(FACT_SCOPE_PATH),
        )

        self.assertEqual(result["status"], "verified_nonempty")
        self.assertEqual(result["logicalSource"], "raid")
        self.assertEqual(result["rawSourceType"], "lair")

    def test_unselected_journal_and_great_vault_are_not_memberships(self):
        product_scope = load_product_content_scope(PRODUCT_SCOPE_PATH)
        fact_scope = load_official_fact_scope(FACT_SCOPE_PATH)

        out_of_scope = classify_official_source(
            official_relation={
                "journalInstanceId": 9999,
                "journalCategory": "RAID",
                "mode": "MYTHIC",
                "rawSourceType": "raid",
                "memberCount": 1,
            },
            product_scope=product_scope,
            scope=fact_scope,
        )
        self.assertEqual(out_of_scope["status"], "excluded")
        self.assertEqual(out_of_scope["reasonCode"], "OUT_OF_SCOPE_PRODUCT_CONTENT")

        great_vault = classify_official_source(
            official_relation={
                "sourceKind": "great_vault",
                "memberCount": 1,
            },
            product_scope=product_scope,
            scope=fact_scope,
        )
        self.assertEqual(great_vault["status"], "excluded")
        self.assertEqual(great_vault["reasonCode"], "NON_MEMBERSHIP_GREAT_VAULT")

    def test_delves_preys_and_world_content_have_explicit_exclusion_reasons(self):
        product_scope = load_product_content_scope(PRODUCT_SCOPE_PATH)
        fact_scope = load_official_fact_scope(FACT_SCOPE_PATH)
        for source_kind, reason in (
            ("delve", "OUT_OF_SCOPE_DELVE"),
            ("prey", "OUT_OF_SCOPE_PREY"),
            ("world_content", "OUT_OF_SCOPE_WORLD_CONTENT"),
        ):
            with self.subTest(source_kind=source_kind):
                result = classify_official_source(
                    official_relation={"sourceKind": source_kind, "memberCount": 1},
                    product_scope=product_scope,
                    scope=fact_scope,
                )
                self.assertEqual(result["status"], "excluded")
                self.assertEqual(result["reasonCode"], reason)

    def test_track_gate_is_fail_closed(self):
        self.assertEqual(
            require_official_mythic_cap(None),
            {
                "status": "UNVERIFIED",
                "reasonCode": "S2_OFFICIAL_TRACK_UNAVAILABLE",
            },
        )
        self.assertEqual(
            require_official_mythic_cap({"mythicCapable": False}),
            {
                "status": "excluded",
                "reasonCode": "EXCLUDED_NOT_MYTHIC_CAPABLE",
            },
        )
        self.assertEqual(
            require_official_mythic_cap({"mythicCapable": True}),
            {"status": "verified"},
        )

    def test_loader_rejects_non_json_scope_payload(self):
        with self.assertRaises(S2OfficialFactScopeError):
            load_product_content_scope(PRODUCT_SCOPE_PATH.parent / "source-policy.json")


if __name__ == "__main__":
    unittest.main()
