import copy
import json
import unittest
from pathlib import Path

from server.s2_official_api_fact_snapshot import (
    OfficialFactSnapshotContractError,
    build_official_api_fact_snapshot,
    canonical_json_sha256,
    request_key,
    validate_capture_manifest,
    validate_official_api_fact_snapshot,
    validate_official_fact_scope,
    validate_product_content_scope,
)


ROOT = Path(__file__).resolve().parents[1]
SCOPE_PATH = (
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


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def manifest_fixture():
    path = "/data/wow/journal/instance/index"
    query = {"namespace": "static-12.1.0_68914-us", "locale": "en_US"}
    namespace = "static-12.1.0_68914-us"
    key = request_key(
        path,
        query,
        namespace=namespace,
        region="us",
        locale="en_US",
    )
    return {
        "schemaRevision": "s2-official-api-capture-manifest-v1",
        "seasonKey": "midnight-season-2",
        "status": "captured",
        "region": "us",
        "locale": "en_US",
        "namespace": namespace,
        "entries": [
            {
                "requestKey": key,
                "path": path,
                "query": query,
                "namespace": namespace,
                "region": "us",
                "locale": "en_US",
                "responsePath": "raw/0001.json",
                "responseSha256": "a" * 64,
                "responseBytes": 128,
                "capturedAt": "2026-08-17T10:00:00Z",
                "pagination": {"page": 1, "pageCount": 1, "complete": True},
                "paginationParentRequestKey": None,
            }
        ],
    }


def item_fact_fixture():
    return {
        "itemId": "268226",
        "factOwner": "blizzard_game_data_api",
        "status": "verified",
        "sourceMemberships": [
            {
                "logicalSource": "raid",
                "rawSourceType": "lair",
                "rawSourceKey": "lair:the-tidebound-grotto",
                "officialEvidenceRefs": ["official:journal:1317:2849"],
            },
            {
                "logicalSource": "tier_set",
                "rawSourceType": "tier_set",
                "rawSourceKey": "tier_set:example",
                "officialEvidenceRefs": ["official:set:2065"],
            },
        ],
        "fieldStatuses": {
            "itemIdentity": "verified",
            "sourceMembership": "verified",
        },
        "officialEvidenceRefs": [
            "official:item:268226",
            "official:journal:1317:2849",
            "official:set:2065",
        ],
    }


class S2OfficialFactSnapshotTest(unittest.TestCase):
    def test_canonical_json_hash_ignores_mapping_order(self):
        self.assertEqual(
            canonical_json_sha256({"b": 2, "a": {"d": 4, "c": 3}}),
            canonical_json_sha256({"a": {"c": 3, "d": 4}, "b": 2}),
        )

    def test_scope_contract_has_exactly_four_logical_sources_and_keeps_lair_raw(self):
        scope = validate_product_content_scope(load_json(SCOPE_PATH))
        fact_scope = validate_official_fact_scope(load_json(FACT_SCOPE_PATH))

        self.assertEqual(
            scope["logicalSourceKeys"],
            [
                "crafted:midnight-season-2",
                "mythic_plus:midnight-season-2",
                "raid:midnight-season-2",
                "tier_set:midnight-season-2",
            ],
        )
        self.assertTrue(scope["lairRawSourceTypePreserved"])
        self.assertTrue(scope["tierSetIsIndependentMembershipDimension"])
        self.assertEqual(
            scope["journalInstanceSelections"]["mythic_plus"],
            [1030, 1041, 1202, 1304, 1309, 1311, 1313, 1322],
        )
        self.assertEqual(
            fact_scope["nonMembershipKinds"],
            ["great_vault"],
        )

    def test_scope_contract_rejects_out_of_scope_logical_source(self):
        scope = load_json(SCOPE_PATH)
        scope["logicalSourceKeys"].append("dungeon:midnight-season-2")

        with self.assertRaisesRegex(
            OfficialFactSnapshotContractError,
            "exactly four logical sources",
        ):
            validate_product_content_scope(scope)

    def test_scope_contract_rejects_game_facts_in_product_selector(self):
        scope = load_json(SCOPE_PATH)
        scope["journalInstanceSelections"]["raid"][0]["itemIds"] = ["268226"]

        with self.assertRaisesRegex(
            OfficialFactSnapshotContractError,
            "must not contain game facts",
        ):
            validate_product_content_scope(scope)

    def test_capture_manifest_rejects_incomplete_pagination(self):
        manifest = manifest_fixture()
        manifest["entries"][0]["pagination"]["complete"] = False

        with self.assertRaisesRegex(
            OfficialFactSnapshotContractError,
            "pagination",
        ):
            validate_capture_manifest(manifest)

    def test_capture_manifest_request_key_is_content_bound(self):
        manifest = manifest_fixture()
        manifest["entries"][0]["query"] = {
            "namespace": "static-12.1.0_68914-us",
            "locale": "zh_CN",
        }

        with self.assertRaisesRegex(
            OfficialFactSnapshotContractError,
            "requestKey",
        ):
            validate_capture_manifest(manifest)

    def test_snapshot_preserves_lair_and_tier_set_memberships_on_one_item(self):
        scope = load_json(SCOPE_PATH)
        fact_scope = load_json(FACT_SCOPE_PATH)
        snapshot = build_official_api_fact_snapshot(
            product_scope=scope,
            fact_scope=fact_scope,
            capture_manifest=manifest_fixture(),
            scope_counts={
                "candidate": {
                    "raid": 1,
                    "mythic_plus": 0,
                    "crafted": 0,
                    "tier_set": 1,
                },
                "admitted": {
                    "raid": 1,
                    "mythic_plus": 0,
                    "crafted": 0,
                    "tier_set": 1,
                },
            },
            source_facts=[
                {
                    "logicalSource": "raid",
                    "rawSourceType": "lair",
                    "rawSourceKey": "lair:the-tidebound-grotto",
                    "status": "verified",
                    "officialEvidenceRefs": ["official:journal:1317:2849"],
                }
            ],
            item_facts=[item_fact_fixture()],
        )

        memberships = snapshot["itemFacts"][0]["sourceMemberships"]
        self.assertEqual(
            {(row["logicalSource"], row["rawSourceType"]) for row in memberships},
            {("raid", "lair"), ("tier_set", "tier_set")},
        )
        self.assertEqual(snapshot["status"], "verified")
        self.assertEqual(snapshot["counts"]["officialScopeAdmittedCountByKind"]["raid"], 1)
        self.assertIsNone(snapshot["counts"]["simcReadyCountByKind"]["raid"])
        validate_official_api_fact_snapshot(snapshot, scope=scope)

    def test_snapshot_revision_ignores_capture_time_and_response_path(self):
        scope = load_json(SCOPE_PATH)
        fact_scope = load_json(FACT_SCOPE_PATH)
        kwargs = {
            "product_scope": scope,
            "fact_scope": fact_scope,
            "scope_counts": {
                "candidate": {"raid": 1, "mythic_plus": 0, "crafted": 0, "tier_set": 0},
                "admitted": {"raid": 1, "mythic_plus": 0, "crafted": 0, "tier_set": 0},
            },
            "source_facts": [
                {
                    "logicalSource": "raid",
                    "rawSourceType": "raid",
                    "rawSourceKey": "raid:venomous-abyss",
                    "status": "verified",
                    "officialEvidenceRefs": ["official:journal:1320"],
                }
            ],
            "item_facts": [],
        }
        first_manifest = manifest_fixture()
        second_manifest = copy.deepcopy(first_manifest)
        second_manifest["entries"][0]["capturedAt"] = "2026-08-18T10:00:00Z"
        second_manifest["entries"][0]["responsePath"] = "raw/renamed-response.json"

        first = build_official_api_fact_snapshot(
            capture_manifest=first_manifest,
            **kwargs,
        )
        second = build_official_api_fact_snapshot(
            capture_manifest=second_manifest,
            **kwargs,
        )

        self.assertEqual(
            first["officialApiFactSnapshotRevision"],
            second["officialApiFactSnapshotRevision"],
        )

    def test_snapshot_marks_unresolved_official_fields_partial_without_simc_upgrade(self):
        scope = load_json(SCOPE_PATH)
        fact_scope = load_json(FACT_SCOPE_PATH)
        unresolved = {
            "subjectKey": "item:268226",
            "field": "terminalTrack",
            "status": "UNVERIFIED",
            "reasonCode": "OFFICIAL_API_FIELD_MISSING",
            "officialEvidenceRefs": ["official:item:268226"],
        }
        snapshot = build_official_api_fact_snapshot(
            product_scope=scope,
            fact_scope=fact_scope,
            capture_manifest=manifest_fixture(),
            scope_counts={
                "candidate": {"raid": 1, "mythic_plus": 0, "crafted": 0, "tier_set": 1},
                "admitted": {"raid": 0, "mythic_plus": 0, "crafted": 0, "tier_set": 0},
            },
            source_facts=[],
            item_facts=[],
            unresolved_facts=[unresolved],
        )

        self.assertEqual(snapshot["status"], "partial")
        self.assertEqual(snapshot["unresolvedFacts"], [unresolved])
        self.assertEqual(snapshot["counts"]["unverifiedCount"], 1)
        self.assertEqual(snapshot["counts"]["simcReadyCount"], 0)

    def test_snapshot_rejects_non_blizzard_fact_owner(self):
        item = item_fact_fixture()
        item["factOwner"] = "simc"

        with self.assertRaisesRegex(
            OfficialFactSnapshotContractError,
            "factOwner",
        ):
            build_official_api_fact_snapshot(
                product_scope=load_json(SCOPE_PATH),
                fact_scope=load_json(FACT_SCOPE_PATH),
                capture_manifest=manifest_fixture(),
                scope_counts={
                    "candidate": {"raid": 1, "mythic_plus": 0, "crafted": 0, "tier_set": 1},
                    "admitted": {"raid": 1, "mythic_plus": 0, "crafted": 0, "tier_set": 1},
                },
                source_facts=[],
                item_facts=[item],
            )


if __name__ == "__main__":
    unittest.main()
