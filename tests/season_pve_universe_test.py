import copy
import json
import unittest
from pathlib import Path

from server.season_pve_universe import (
    UniverseContractError,
    bounded_universe_report,
    build_season_pve_universe,
    item_relation_key,
)


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "server" / "data" / "midnight-season-1-pve-source-policy.json"


def source(source_key="raid:voidspire", *, status="verified", members=None, gaps=None):
    member_rows = list(members or [])
    return {
        "sourceKey": source_key,
        "status": status,
        "capturedAt": "2026-07-29T12:00:00Z",
        "validUntil": "2026-07-30T12:00:00Z",
        "evidenceRef": f"official:{source_key}",
        "authorityRefs": [f"official:{source_key}"],
        "membershipComplete": True,
        "declaredMemberCount": len(member_rows),
        "members": member_rows,
        "gaps": list(gaps or []),
    }


def member(
    item_id,
    *,
    source_key="raid:voidspire",
    instance_id="voidspire",
    encounter_id="boss-1",
    difficulty_key="heroic",
    progression_state=None,
):
    return {
        "sourceKey": source_key,
        "instanceId": instance_id,
        "encounterId": encounter_id,
        "difficultyKey": difficulty_key,
        "itemId": str(item_id),
        "progressionState": progression_state
        or {
            "kind": "upgrade_track",
            "trackKey": "hero",
            "rank": 1,
            "rankMax": 6,
        },
        "evidenceRef": f"journal:{instance_id}:{encounter_id}:{item_id}",
    }


def policy(*source_keys):
    return {
        "schemaVersion": 1,
        "seasonRevision": "season-midnight-s1-r1",
        "sourcePolicyRevision": "season-pve-source-policy-v1",
        "sources": [
            {
                "sourceKey": key,
                "sourceType": key.split(":", 1)[0],
                "required": True,
                "membershipMode": "direct_drop",
                "authorityRefs": [f"official:{key}"],
            }
            for key in source_keys
        ],
    }


def discovery(*sources, season_revision="season-midnight-s1-r1"):
    return {
        "schemaVersion": 1,
        "seasonRevision": season_revision,
        "sourcePolicyRevision": "season-pve-source-policy-v1",
        "asOf": "2026-07-29T13:00:00Z",
        "sources": list(sources),
    }


def staging(*members):
    return {
        "schemaVersion": 1,
        "seasonRevision": "season-midnight-s1-r1",
        "members": [
            {
                **row,
                "status": "verified",
                "sourceId": f"staging:{item_relation_key(row)}",
            }
            for row in members
        ],
    }


def catalog(*members):
    return {
        "schemaVersion": 1,
        "seasonRevision": "season-midnight-s1-r1",
        "catalogRevision": "gear-catalog:sha256:" + ("a" * 64),
        "members": [
            {
                **row,
                "status": "verified",
                "browseVariantKeys": [
                    "browse-variant:sha256:" + ("b" * 64),
                ],
            }
            for row in members
        ],
    }


class SeasonPveUniverseTest(unittest.TestCase):
    def test_empty_required_source_cannot_claim_verified_membership(self):
        result = build_season_pve_universe(
            policy("raid:voidspire"),
            discovery(source("raid:voidspire")),
            staging(),
            catalog(),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn(
            "SOURCE_EMPTY_MEMBERSHIP_UNPROVEN",
            result["blockerCodes"],
        )

    def test_expired_or_evidenceless_source_snapshot_stays_blocked(self):
        expired = source("raid:voidspire", members=[member("1001")])
        expired["validUntil"] = "2026-07-29T12:59:59Z"
        expired.pop("evidenceRef")

        result = build_season_pve_universe(
            policy("raid:voidspire"),
            discovery(expired),
            staging(member("1001")),
            catalog(member("1001")),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertTrue(
            {
                "SOURCE_EVIDENCE_INCOMPLETE",
                "SOURCE_DISCOVERY_EXPIRED",
            }
            & set(result["blockerCodes"])
        )

    def test_source_authority_coverage_must_match_policy(self):
        discovered = source("raid:voidspire", members=[member("1001")])
        discovered["authorityRefs"] = ["unrelated:mirror"]

        result = build_season_pve_universe(
            policy("raid:voidspire"),
            discovery(discovered),
            staging(member("1001")),
            catalog(member("1001")),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn(
            "SOURCE_AUTHORITY_COVERAGE_MISMATCH",
            result["blockerCodes"],
        )

    def test_non_list_members_are_rejected_instead_of_becoming_empty(self):
        malformed = source("raid:voidspire")
        malformed["members"] = {"itemId": "1001"}
        malformed["declaredMemberCount"] = 0

        with self.assertRaisesRegex(
            UniverseContractError,
            "members must be a list",
        ):
            build_season_pve_universe(
                policy("raid:voidspire"),
                discovery(malformed),
                staging(),
                catalog(),
            )

    def test_progression_state_is_part_of_item_relation_identity(self):
        hero = member(
            "1001",
            progression_state={
                "kind": "upgrade_track",
                "trackKey": "hero",
                "rank": 1,
                "rankMax": 6,
            },
        )
        myth = member(
            "1001",
            progression_state={
                "kind": "upgrade_track",
                "trackKey": "myth",
                "rank": 1,
                "rankMax": 6,
            },
        )

        self.assertNotEqual(item_relation_key(hero), item_relation_key(myth))

    def test_downstream_member_absent_from_discovery_is_blocked_once(self):
        discovered = member("1001")
        downstream_only = member("1002")
        result = build_season_pve_universe(
            policy("raid:voidspire"),
            discovery(source("raid:voidspire", members=[discovered])),
            staging(discovered, downstream_only),
            catalog(discovered, downstream_only),
        )

        orphan_rows = [
            row
            for row in result["ledger"]
            if row.get("itemId") == "1002"
        ]
        self.assertEqual(len(orphan_rows), 1)
        self.assertEqual(orphan_rows[0]["outcome"], "blocked")
        self.assertEqual(
            orphan_rows[0]["reasonCode"],
            "DOWNSTREAM_MEMBER_NOT_DISCOVERED",
        )
        self.assertTrue(orphan_rows[0]["presentInStaging"])
        self.assertTrue(orphan_rows[0]["presentInCatalog"])

    def test_catalog_membership_without_one_browse_variant_stays_blocked(self):
        discovered = member("1001")
        catalog_snapshot = catalog(discovered)
        catalog_snapshot["members"][0]["browseVariantKeys"] = []

        result = build_season_pve_universe(
            policy("raid:voidspire"),
            discovery(source("raid:voidspire", members=[discovered])),
            staging(discovered),
            catalog_snapshot,
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn(
            "CATALOG_BROWSE_VARIANT_CARDINALITY_MISMATCH",
            result["blockerCodes"],
        )

    def test_missing_required_source_discovery_blocks_universe(self):
        result = build_season_pve_universe(
            policy("raid:voidspire", "delve:season-1"),
            discovery(source("raid:voidspire")),
            staging(),
            catalog(),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("SOURCE_DISCOVERY_MISSING", result["blockerCodes"])
        missing = [
            row
            for row in result["ledger"]
            if row["reasonCode"] == "SOURCE_DISCOVERY_MISSING"
        ]
        self.assertEqual(
            [(row["memberType"], row["sourceKey"]) for row in missing],
            [("source", "delve:season-1")],
        )

    def test_verified_label_without_complete_membership_proof_stays_blocked(self):
        incomplete = source("raid:voidspire")
        incomplete.pop("membershipComplete")
        incomplete.pop("declaredMemberCount")

        result = build_season_pve_universe(
            policy("raid:voidspire"),
            discovery(incomplete),
            staging(),
            catalog(),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn(
            "SOURCE_MEMBERSHIP_COMPLETENESS_UNPROVEN",
            result["blockerCodes"],
        )

    def test_declared_member_count_mismatch_stays_blocked(self):
        only_member = member("1001")
        mismatched = source(
            "raid:voidspire",
            members=[only_member],
        )
        mismatched["declaredMemberCount"] = 2

        result = build_season_pve_universe(
            policy("raid:voidspire"),
            discovery(mismatched),
            staging(only_member),
            catalog(only_member),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn(
            "SOURCE_MEMBER_COUNT_MISMATCH",
            result["blockerCodes"],
        )

    def test_cap_pagination_fetch_and_fallback_gaps_are_ledger_members(self):
        gap_rows = [
            {
                "kind": "cap",
                "boundary": "item",
                "omittedCount": 3,
                "evidenceRef": "run:cap",
            },
            {
                "kind": "pagination",
                "boundary": "encounter",
                "cursor": "next-2",
                "evidenceRef": "run:page",
            },
            {
                "kind": "fetch_failure",
                "boundary": "instance",
                "identity": "instance-9",
                "evidenceRef": "run:fetch",
            },
            {
                "kind": "fallback",
                "boundary": "source",
                "identity": "cached-copy",
                "evidenceRef": "run:fallback",
            },
        ]
        result = build_season_pve_universe(
            policy("raid:voidspire"),
            discovery(
                source(
                    status="partial",
                    gaps=gap_rows,
                )
            ),
            staging(),
            catalog(),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(
            {
                row["reasonCode"]
                for row in result["ledger"]
                if row["memberType"] == "gap"
            },
            {
                "SOURCE_CAP_TRUNCATED",
                "SOURCE_PAGINATION_INCOMPLETE",
                "SOURCE_FETCH_FAILED",
                "SOURCE_FALLBACK_USED",
            },
        )
        self.assertEqual(result["counts"]["gapMembers"], 4)

    def test_each_discovered_item_is_included_or_blocked_at_exact_missing_layer(self):
        included = member("1001")
        staging_missing = member("1002")
        catalog_missing = member("1003")
        result = build_season_pve_universe(
            policy("raid:voidspire"),
            discovery(
                source(
                    members=[included, staging_missing, catalog_missing],
                )
            ),
            staging(included, catalog_missing),
            catalog(included),
        )

        outcomes = {
            row.get("itemId"): (row["outcome"], row.get("reasonCode"))
            for row in result["ledger"]
            if row["memberType"] == "item_relation"
        }
        self.assertEqual(outcomes["1001"], ("included", ""))
        self.assertEqual(
            outcomes["1002"],
            ("blocked", "STAGING_RELATION_MISSING"),
        )
        self.assertEqual(
            outcomes["1003"],
            ("blocked", "CATALOG_MEMBERSHIP_MISSING"),
        )
        self.assertEqual(result["status"], "blocked")

    def test_governed_exclusion_requires_reason_owner_evidence_and_decision_time(self):
        excluded = member("1009")
        valid = {
            "memberKey": item_relation_key(excluded),
            "reasonCode": "COSMETIC_NOT_COMBAT_GEAR",
            "factOwner": "season-pve-source-policy-v1",
            "evidenceRef": "item:1009:class",
            "decidedAt": "2026-07-29T13:00:00Z",
        }
        result = build_season_pve_universe(
            policy("raid:voidspire"),
            discovery(source(members=[excluded])),
            staging(),
            catalog(),
            exclusions=[valid],
        )

        item_row = next(
            row for row in result["ledger"] if row["memberType"] == "item_relation"
        )
        self.assertEqual(item_row["outcome"], "excluded")
        self.assertEqual(item_row["reasonCode"], "COSMETIC_NOT_COMBAT_GEAR")
        self.assertEqual(result["status"], "verified")

        for missing_field in (
            "reasonCode",
            "factOwner",
            "evidenceRef",
            "decidedAt",
        ):
            invalid = dict(valid)
            invalid.pop(missing_field)
            with self.subTest(missing_field=missing_field):
                with self.assertRaisesRegex(
                    UniverseContractError,
                    missing_field,
                ):
                    build_season_pve_universe(
                        policy("raid:voidspire"),
                        discovery(source(members=[excluded])),
                        staging(),
                        catalog(),
                        exclusions=[invalid],
                    )

    def test_revision_is_deterministic_across_input_order(self):
        first = member("1010", encounter_id="boss-2")
        second = member("1008", encounter_id="boss-1")
        crafted = member(
            "1020",
            source_key="crafted:midnight",
            instance_id="profession",
            encounter_id="recipe-20",
            difficulty_key="quality-1",
            progression_state={
                "kind": "crafted",
                "trackKey": "crafted",
                "rankMax": 6,
            },
        )
        policy_rows = policy("raid:voidspire", "crafted:midnight")
        policy_rows["sources"][0]["authorityRefs"] = [
            "official:b",
            "official:a",
        ]
        raid_discovery = source(
            "raid:voidspire",
            members=[first, second],
        )
        raid_discovery["authorityRefs"] = ["official:b", "official:a"]
        discovered = discovery(
            raid_discovery,
            source("crafted:midnight", members=[crafted]),
        )
        first_result = build_season_pve_universe(
            policy_rows,
            discovered,
            staging(first, second, crafted),
            catalog(first, second, crafted),
        )
        reordered_policy = copy.deepcopy(policy_rows)
        reordered_policy["sources"] = list(
            reversed(reordered_policy["sources"])
        )
        for policy_source in reordered_policy["sources"]:
            policy_source["authorityRefs"] = list(
                reversed(policy_source["authorityRefs"])
            )
        second_result = build_season_pve_universe(
            reordered_policy,
            {
                **discovered,
                "sources": [
                    discovered["sources"][1],
                    {
                        **discovered["sources"][0],
                        "members": [second, first],
                    },
                ],
            },
            staging(second, first, crafted),
            catalog(second, first, crafted),
        )

        self.assertEqual(first_result["status"], "verified")
        self.assertEqual(
            first_result["universeRevision"],
            second_result["universeRevision"],
        )
        self.assertEqual(first_result["ledger"], second_result["ledger"])

    def test_revision_drift_blocks_instead_of_comparing_different_seasons(self):
        result = build_season_pve_universe(
            policy("raid:voidspire"),
            discovery(
                source("raid:voidspire"),
                season_revision="season-midnight-s2-r1",
            ),
            staging(),
            catalog(),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("SEASON_REVISION_MISMATCH", result["blockerCodes"])

    def test_real_policy_covers_all_officially_named_acquisition_families(self):
        real_policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        source_types = {
            row["sourceType"]
            for row in real_policy["sources"]
            if row.get("required")
        }

        self.assertTrue(
            {
                "raid",
                "mythic_plus",
                "dungeon",
                "delve",
                "world_boss",
                "prey",
                "great_vault",
                "crafted",
                "renown_vendor",
                "tier_set_vendor",
                "catalyst",
                "voidforge",
                "world_content",
                "timewalking_event",
            }.issubset(source_types)
        )
        for source_row in real_policy["sources"]:
            self.assertTrue(source_row["authorityRefs"])
            self.assertTrue(source_row["membershipMode"])

    def test_bounded_report_never_prints_an_unbounded_ledger(self):
        rows = [
            {
                "memberKey": f"member-{index:03d}",
                "memberType": "item_relation",
                "sourceKey": "raid:voidspire",
                "itemId": str(1000 + index),
                "outcome": "blocked",
                "reasonCode": "STAGING_RELATION_MISSING",
            }
            for index in range(25)
        ]
        report = {
            "schemaVersion": 1,
            "status": "blocked",
            "universeRevision": "season-pve-universe:sha256:" + ("c" * 64),
            "seasonRevision": "season-midnight-s1-r1",
            "sourcePolicyRevision": "season-pve-source-policy-v1",
            "catalogRevision": "",
            "counts": {
                "total": 25,
                "included": 0,
                "excluded": 0,
                "blocked": 25,
                "sourceMembers": 0,
                "itemMembers": 25,
                "gapMembers": 0,
            },
            "blockerCodes": ["STAGING_RELATION_MISSING"],
            "ledger": rows,
        }

        bounded = bounded_universe_report(report, max_ledger_rows=3)

        self.assertEqual(len(bounded["ledger"]), 3)
        self.assertEqual(bounded["diagnostics"]["ledgerRowsTotal"], 25)
        self.assertEqual(bounded["diagnostics"]["ledgerRowsEmitted"], 3)
        self.assertTrue(bounded["diagnostics"]["truncated"])

    def test_bounded_report_omits_nested_progression_payload(self):
        report = {
            "schemaVersion": 1,
            "status": "blocked",
            "ledger": [
                {
                    "memberKey": "member-1",
                    "memberType": "item_relation",
                    "sourceKey": "raid:voidspire",
                    "itemId": "1001",
                    "progressionState": {
                        "kind": "upgrade_track",
                        "rawPayload": "must-never-reach-bounded-output",
                    },
                    "progressionStateKey": "progression-state:sha256:"
                    + ("d" * 64),
                    "outcome": "blocked",
                    "reasonCode": "STAGING_RELATION_MISSING",
                }
            ],
        }

        bounded = bounded_universe_report(report)

        serialized = json.dumps(bounded, sort_keys=True)
        self.assertNotIn("must-never-reach-bounded-output", serialized)
        self.assertIn("progression-state:sha256:", serialized)


if __name__ == "__main__":
    unittest.main()
