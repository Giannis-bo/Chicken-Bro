import unittest

from server.gear_release_tool import normalize_gear_snapshot_for_release
from server.s2_equipment_library_candidate import (
    build_s2_track_authority,
    project_s2_catalog_rows,
)


def _variant(
    item_id,
    variant_key,
    *,
    source_type="raid",
    track_key="champion",
    rank=8,
    max_rank=8,
    item_level=315,
    status="verified",
):
    return {
        "variantId": f"variant:{variant_key}",
        "itemId": item_id,
        "variantKey": variant_key,
        "slot": "head",
        "sourceType": source_type,
        "sourceKey": f"{source_type}:s2",
        "itemLevel": item_level,
        "simcOptions": {"id": item_id, "ilevel": str(item_level), "bonus_id": "13448"},
        "status": status,
        "blockers": [],
        "payload": {
            "canonicalSimcInput": {
                "itemId": item_id,
                "itemLevel": item_level,
                "bonusIds": ["13448"],
                "slot": "head",
                "simcOptions": {"id": item_id, "ilevel": str(item_level), "bonus_id": "13448"},
            },
            "resolvedStats": {"intellect": 120, "stamina": 400},
            "trackKey": track_key,
            "rank": rank,
            "maxRank": max_rank,
        },
    }


class S2EquipmentLibraryCandidateTest(unittest.TestCase):
    def test_catalog_projection_keeps_max_progression_crafted_and_tier_static_rows(self):
        snapshot = {
            "items": [],
            "sources": [],
            "variants": [
                _variant("1001", "champion-rank-1", rank=1, item_level=292),
                _variant("1001", "champion-rank-8", rank=8, item_level=315),
                _variant(
                    "1002",
                    "tier-a",
                    source_type="tier_set",
                    track_key="",
                    rank=None,
                    max_rank=None,
                    item_level=219,
                ),
                _variant(
                    "1002",
                    "tier-b",
                    source_type="tier_set",
                    track_key="",
                    rank=None,
                    max_rank=None,
                    item_level=219,
                ),
                _variant(
                    "1003",
                    "crafted-quality-5",
                    source_type="crafted",
                    track_key="crafted_quality",
                    rank=None,
                    max_rank=None,
                    item_level=318,
                ),
            ],
        }

        rows = project_s2_catalog_rows(snapshot)

        self.assertEqual(
            [(row["itemId"], row["variantKey"]) for row in rows],
            [
                ("1001", "champion-rank-8"),
                ("1002", "tier-a"),
                ("1003", "crafted-quality-5"),
            ],
        )
        self.assertTrue(all(row["rowFamily"] == "browse" for row in rows))
        self.assertEqual(rows[0]["bonusIds"], ["13448"])
        self.assertEqual(rows[2]["sourceType"], "crafted")

    def test_track_authority_is_bound_to_verified_max_rank_evidence(self):
        candidate = {
            "reportId": "s2-candidate:test",
            "variants": [
                {
                    "itemId": "1001",
                    "itemSlot": "head",
                    "trackKey": "champion",
                    "rank": 8,
                    "maxRank": 8,
                    "canonicalSimcInput": {
                        "itemLevel": 315,
                        "bonusIds": ["13448"],
                    },
                    "simcReadiness": "ready",
                }
            ],
            "mythicPlusCapTrackEvidence": {
                "trackFacts": [
                    {
                        "trackKey": "champion",
                        "maxRank": 8,
                        "evidenceRefs": ["db2:test#/row/0"],
                        "status": "verified",
                    }
                ]
            },
        }

        authority = build_s2_track_authority(
            candidate,
            season_revision="season-midnight-season-2:test",
            gear_rule_revision="gear-rule-matrix-v1",
            track_authority_revision="midnight-season-2-track-authority:test",
        )

        self.assertEqual(authority["status"], "verified")
        self.assertEqual(len(authority["records"]), 1)
        self.assertEqual(authority["records"][0]["itemLevel"], 315)
        self.assertEqual(authority["records"][0]["rank"], 8)

    def test_community_exact_rows_never_expand_catalog(self):
        observed = _variant(
            "2001",
            "observed-exact",
            source_type="observed_profile",
        )
        observed["rowFamily"] = "exact_instance"
        rows = project_s2_catalog_rows({"variants": [observed]})
        self.assertEqual(rows, [])

    def test_selection_only_crafted_stats_remain_exact_only(self):
        crafted = _variant(
            "2002",
            "crafted-secondary-only",
            source_type="crafted",
            track_key="crafted_quality",
            rank=None,
            max_rank=None,
        )
        crafted["payload"]["resolvedStats"] = {"versatility_rating": 120}

        rows = project_s2_catalog_rows({"variants": [crafted]})

        self.assertEqual(rows, [])

    def test_release_projection_drops_catalog_only_fields_before_hashing(self):
        snapshot = {
            "items": [{
                "itemId": "3001",
                "name": "Observed",
                "slot": "head",
                "itemLevel": "315",
                "sourceStatus": "verified",
                "payload": {"baseStats": {"intellect": 1}},
                "blockers": [],
                "catalogOnly": True,
            }],
            "sources": [],
            "variants": [{
                "variantId": "variant:observed",
                "itemId": "3001",
                "variantKey": "observed",
                "slot": "head",
                "label": "Observed",
                "sourceType": "observed_profile",
                "difficultyKey": "",
                "itemLevel": "315",
                "simcOptions": {"id": "3001"},
                "status": "verified",
                "blockers": [],
                "payload": {},
                "rowFamily": "exact_instance",
                "staticStats": {"intellect": 1},
            }],
            "options": [],
        }

        projected = normalize_gear_snapshot_for_release(snapshot)

        self.assertEqual(
            set(projected["items"][0]),
            {"itemId", "name", "slot", "itemLevel", "sourceStatus", "payload", "updatedAt"},
        )
        self.assertEqual(
            set(projected["variants"][0]),
            {
                "variantId", "itemId", "variantKey", "slot", "label", "sourceType",
                "difficultyKey", "itemLevel", "simcOptions", "status", "blockers",
                "payload", "updatedAt",
            },
        )
        self.assertEqual(projected["variants"][0]["itemLevel"], 315)


if __name__ == "__main__":
    unittest.main()
