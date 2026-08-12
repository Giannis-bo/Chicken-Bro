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


def policy(*source_keys, season_revision="season-midnight-s1-r1", scope="current"):
    return {
        "schemaVersion": 1,
        "seasonRevision": season_revision,
        "sourcePolicyRevision": "season-pve-source-policy-v1",
        "status": "approved",
        "scope": scope,
        "sources": [
            {
                "sourceKey": key,
                "sourceType": key.split(":", 1)[0],
                "required": True,
                "membershipMode": "direct_drop",
                "authorityRefs": [f"official:{key}"],
                "effectiveWindow": {
                    "startsAt": "2026-07-01T00:00:00Z",
                    "endsAt": "2026-08-31T23:59:59Z",
                },
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


def staging(*members, season_revision="season-midnight-s1-r1"):
    return {
        "schemaVersion": 1,
        "seasonRevision": season_revision,
        "members": [
            {
                **row,
                "status": "verified",
                "sourceId": f"staging:{item_relation_key(row)}",
            }
            for row in members
        ],
    }


def catalog(*members, season_revision="season-midnight-s1-r1"):
    return {
        "schemaVersion": 1,
        "seasonRevision": season_revision,
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
    def test_endgame_mode_includes_complete_pool_without_effective_window(self):
        season_revision = "season-midnight-season-2:fixture"
        source_policy = policy(
            "raid:venomous-abyss",
            season_revision=season_revision,
            scope="end_game",
        )
        source_policy["sources"][0].pop("effectiveWindow")
        discovered = source(
            "raid:venomous-abyss",
            members=[
                member(
                    "2001",
                    source_key="raid:venomous-abyss",
                    instance_id="venomous-abyss",
                )
            ],
        )

        result = build_season_pve_universe(
            source_policy,
            discovery(
                discovered,
                season_revision=season_revision,
            ),
            staging(
                member(
                    "2001",
                    source_key="raid:venomous-abyss",
                    instance_id="venomous-abyss",
                ),
                season_revision=season_revision,
            ),
            catalog(
                member(
                    "2001",
                    source_key="raid:venomous-abyss",
                    instance_id="venomous-abyss",
                ),
                season_revision=season_revision,
            ),
            mode="end_game",
        )

        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["scope"], "end_game")
        self.assertNotIn(
            "SOURCE_OUTSIDE_EFFECTIVE_WINDOW",
            result["blockerCodes"],
        )

    def test_endgame_mode_blocks_mixed_s1_revision_instead_of_comparing_seasons(self):
        season_revision = "season-midnight-season-2:fixture"
        source_policy = policy(
            "raid:venomous-abyss",
            season_revision=season_revision,
            scope="end_game",
        )
        source_policy["sources"][0].pop("effectiveWindow")
        discovered = member(
            "2001",
            source_key="raid:venomous-abyss",
            instance_id="venomous-abyss",
        )

        result = build_season_pve_universe(
            source_policy,
            discovery(
                source("raid:venomous-abyss", members=[discovered]),
                season_revision=season_revision,
            ),
            staging(discovered),
            catalog(discovered),
            mode="end_game",
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("SEASON_REVISION_MISMATCH", result["blockerCodes"])

    def test_unapproved_source_policy_cannot_claim_verified_universe(self):
        source_policy = policy("raid:voidspire")
        source_policy["status"] = "draft"

        result = build_season_pve_universe(
            source_policy,
            discovery(source("raid:voidspire", members=[member("1001")])),
            staging(member("1001")),
            catalog(member("1001")),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("SOURCE_POLICY_NOT_APPROVED", result["blockerCodes"])

    def test_missing_source_effective_window_blocks_current_obtainability(self):
        source_policy = policy("raid:voidspire")
        source_policy["sources"][0].pop("effectiveWindow")

        result = build_season_pve_universe(
            source_policy,
            discovery(source("raid:voidspire", members=[member("1001")])),
            staging(member("1001")),
            catalog(member("1001")),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn(
            "SOURCE_EFFECTIVE_WINDOW_MISSING",
            result["blockerCodes"],
        )
        source_row = next(
            row for row in result["ledger"] if row["memberType"] == "source"
        )
        self.assertEqual(source_row["outcome"], "blocked")
        self.assertEqual(
            source_row["reasonCode"],
            "SOURCE_EFFECTIVE_WINDOW_MISSING",
        )

    def test_source_outside_effective_window_is_excluded_from_current_universe(self):
        source_policy = policy(
            "raid:voidspire",
            "timewalking_event:turbulent",
        )
        source_policy["sources"][1]["effectiveWindow"] = {
            "startsAt": "2026-06-30T00:00:00Z",
            "endsAt": "2026-07-28T23:59:59Z",
        }
        active_member = member("1001")

        result = build_season_pve_universe(
            source_policy,
            discovery(source("raid:voidspire", members=[active_member])),
            staging(active_member),
            catalog(active_member),
        )

        self.assertEqual(result["status"], "verified")
        source_row = next(
            row
            for row in result["ledger"]
            if row["memberType"] == "source"
            and row["sourceKey"] == "timewalking_event:turbulent"
        )
        self.assertEqual(source_row["outcome"], "excluded")
        self.assertEqual(
            source_row["reasonCode"],
            "SOURCE_OUTSIDE_EFFECTIVE_WINDOW",
        )

    def test_invalid_source_effective_window_blocks_instead_of_guessing(self):
        source_policy = policy("raid:voidspire")
        source_policy["sources"][0]["effectiveWindow"] = {
            "startsAt": "2026-08-01T00:00:00Z",
            "endsAt": "2026-07-01T00:00:00Z",
        }

        result = build_season_pve_universe(
            source_policy,
            discovery(),
            staging(),
            catalog(),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn(
            "SOURCE_EFFECTIVE_WINDOW_INVALID",
            result["blockerCodes"],
        )

    def test_open_ended_season_window_is_active_until_officially_superseded(self):
        source_policy = policy("raid:voidspire")
        source_policy["sources"][0]["effectiveWindow"] = {
            "startsAt": "2026-03-17T00:00:00Z",
            "endPolicy": "until_officially_superseded",
        }
        discovered = member("1001")

        result = build_season_pve_universe(
            source_policy,
            discovery(source("raid:voidspire", members=[discovered])),
            staging(discovered),
            catalog(discovered),
        )

        self.assertEqual(result["status"], "verified")
        source_row = next(
            row for row in result["ledger"] if row["memberType"] == "source"
        )
        self.assertEqual(source_row["effectiveWindowState"], "active")
        self.assertEqual(
            source_row["effectiveEndPolicy"],
            "until_officially_superseded",
        )
        self.assertEqual(source_row["effectiveEndsAt"], "")

    def test_unknown_open_ended_policy_blocks_instead_of_inventing_an_end(self):
        source_policy = policy("raid:voidspire")
        source_policy["sources"][0]["effectiveWindow"] = {
            "startsAt": "2026-03-17T00:00:00Z",
            "endPolicy": "assume_forever",
        }

        result = build_season_pve_universe(
            source_policy,
            discovery(),
            staging(),
            catalog(),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn(
            "SOURCE_EFFECTIVE_WINDOW_INVALID",
            result["blockerCodes"],
        )

    def test_no_active_required_source_blocks_empty_current_universe(self):
        source_policy = policy("timewalking_event:turbulent")
        source_policy["sources"][0]["effectiveWindow"] = {
            "startsAt": "2026-06-30T00:00:00Z",
            "endsAt": "2026-07-28T23:59:59Z",
        }

        result = build_season_pve_universe(
            source_policy,
            discovery(),
            staging(),
            catalog(),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("NO_ACTIVE_REQUIRED_SOURCES", result["blockerCodes"])

    def test_item_relation_requires_full_source_identity_and_progression_kind(self):
        complete = member("1001")
        for field in (
            "instanceId",
            "encounterId",
            "difficultyKey",
        ):
            invalid = dict(complete)
            invalid.pop(field)
            with self.subTest(field=field):
                with self.assertRaisesRegex(
                    UniverseContractError,
                    field,
                ):
                    item_relation_key(invalid)

        invalid_progression = copy.deepcopy(complete)
        invalid_progression["progressionState"].pop("kind")
        with self.assertRaisesRegex(
            UniverseContractError,
            "progressionState.kind",
        ):
            item_relation_key(invalid_progression)

    def test_discovery_member_source_must_match_its_container(self):
        mismatched = member("1001", source_key="delve:season-1")

        with self.assertRaisesRegex(
            UniverseContractError,
            "does not match container",
        ):
            build_season_pve_universe(
                policy("raid:voidspire"),
                discovery(source("raid:voidspire", members=[mismatched])),
                staging(),
                catalog(),
            )

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

    def test_official_evidence_gap_keeps_its_upstream_reason_code(self):
        result = build_season_pve_universe(
            policy("raid:voidspire"),
            discovery(
                source(
                    status="captured_partial",
                    gaps=[
                        {
                            "kind": (
                                "official_journal_difficulty_"
                                "membership_unavailable"
                            ),
                            "boundary": (
                                "journal_relation_to_difficulty"
                            ),
                            "identity": (
                                "OFFICIAL_JOURNAL_DIFFICULTY_"
                                "MEMBERSHIP_UNAVAILABLE"
                            ),
                            "evidenceRef": "official:snapshot",
                        }
                    ],
                )
            ),
            staging(),
            catalog(),
        )

        gap_row = next(
            row
            for row in result["ledger"]
            if row["memberType"] == "gap"
        )
        self.assertEqual(
            gap_row["reasonCode"],
            "OFFICIAL_JOURNAL_DIFFICULTY_MEMBERSHIP_UNAVAILABLE",
        )

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

        invalid_time = dict(valid)
        invalid_time["decidedAt"] = "not-an-instant"
        with self.assertRaisesRegex(
            UniverseContractError,
            "decidedAt requires an ISO-8601 instant",
        ):
            build_season_pve_universe(
                policy("raid:voidspire"),
                discovery(source(members=[excluded])),
                staging(),
                catalog(),
                exclusions=[invalid_time],
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
        self.assertEqual(
            real_policy["status"],
            "required_membership_discovery",
        )
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

        for source_row in real_policy["sources"]:
            window = source_row.get("effectiveWindow")
            self.assertIsInstance(window, dict)
            self.assertTrue(window.get("startsAt"))
            self.assertTrue(
                bool(window.get("endsAt"))
                ^ (
                    window.get("endPolicy")
                    == "until_officially_superseded"
                )
            )
            self.assertTrue(window.get("startPrecision"))

    def test_real_policy_current_guard_reports_exact_window_and_approval_blockers(self):
        real_policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        result = build_season_pve_universe(
            real_policy,
            {
                "schemaVersion": 1,
                "seasonRevision": real_policy["seasonRevision"],
                "sourcePolicyRevision": real_policy["sourcePolicyRevision"],
                "asOf": "2026-07-29T14:30:00Z",
                "sources": [],
            },
            {
                "schemaVersion": 1,
                "seasonRevision": real_policy["seasonRevision"],
                "members": [],
            },
            {
                "schemaVersion": 1,
                "seasonRevision": real_policy["seasonRevision"],
                "catalogRevision": "blocked:not-independently-captured",
                "members": [],
            },
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(
            result["blockerCodes"],
            [
                "SOURCE_DISCOVERY_MISSING",
                "SOURCE_POLICY_NOT_APPROVED",
            ],
        )
        self.assertEqual(result["counts"]["sourceMembers"], 19)
        self.assertEqual(result["counts"]["blocked"], 20)
        self.assertEqual(
            {
                row["sourceKey"]
                for row in result["ledger"]
                if row.get("reasonCode")
                == "SOURCE_DISCOVERY_MISSING"
            },
            {
                source_row["sourceKey"]
                for source_row in real_policy["sources"]
            },
        )

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
