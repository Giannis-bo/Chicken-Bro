import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from server.s2_official_capture_inventory import (
    OfficialCaptureInventoryError,
    build_official_capture_inventory,
)
from server.s2_official_api_fact_snapshot import request_key


ROOT = Path(__file__).resolve().parents[1]
SCOPE_PATH = ROOT / "server/data/midnight-season-2/s2-product-content-scope-v1.json"
POLICY_PATH = ROOT / "server/data/midnight-season-2/source-policy.json"


def _write_json(path: Path, value) -> tuple[str, int]:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return hashlib.sha256(body).hexdigest(), len(body)


def _entry(root: Path, ordinal: int, path: str, payload: dict) -> dict:
    response_path = root / "raw" / f"{ordinal:04d}.json"
    response_sha256, response_bytes = _write_json(response_path, payload)
    namespace = "static-12.1.0_68914-us"
    return {
        "requestKey": request_key(
            path,
            {},
            namespace=namespace,
            region="us",
            locale="en_US",
        ),
        "path": path,
        "query": {},
        "namespace": namespace,
        "region": "us",
        "locale": "en_US",
        "responsePath": response_path.relative_to(root).as_posix(),
        "responseSha256": response_sha256,
        "responseBytes": response_bytes,
        "capturedAt": "2026-08-19T10:00:00Z",
        "pagination": {"page": 1, "pageCount": 1, "complete": True},
        "paginationParentRequestKey": None,
    }


def prepare_capture(root: Path) -> None:
    entries = []
    ordinal = 1
    mplus_ids = [1030, 1041, 1202, 1304, 1309, 1311, 1313, 1322]
    for index, instance_id in enumerate(mplus_ids):
        encounter_id = 5000 + instance_id
        instance = {
            "id": instance_id,
            "name": f"M+ {instance_id}",
            "category": {"type": "DUNGEON"},
            "modes": [{"mode": {"type": "MYTHIC_KEYSTONE"}}],
            "encounters": [{"id": encounter_id}],
        }
        entries.append(_entry(root, ordinal, f"/data/wow/journal-instance/{instance_id}", instance))
        ordinal += 1
        item_id = 1001 if index == 0 else None
        encounter = {
            "id": encounter_id,
            "name": f"M+ boss {encounter_id}",
            "category": {"type": "DUNGEON"},
            "instance": {"id": instance_id},
            "items": ([{"item": {"id": item_id, "name": "M+ item"}}] if item_id else []),
        }
        entries.append(_entry(root, ordinal, f"/data/wow/journal-encounter/{encounter_id}", encounter))
        ordinal += 1

    lair_encounter_id = 2849
    entries.append(
        _entry(
            root,
            ordinal,
            "/data/wow/journal-instance/1317",
            {
                "id": 1317,
                "name": "The Tidebound Grotto",
                "category": {"type": "RAID"},
                "modes": [{"mode": {"type": "MYTHIC"}}],
                "encounters": [{"id": lair_encounter_id}],
            },
        )
    )
    ordinal += 1
    entries.append(
        _entry(
            root,
            ordinal,
            f"/data/wow/journal-encounter/{lair_encounter_id}",
            {
                "id": lair_encounter_id,
                "name": "Nymrissa Wavecaller",
                "category": {"type": "RAID"},
                "instance": {"id": 1317},
                "items": [{"item": {"id": 1002, "name": "Lair item"}}],
            },
        )
    )
    ordinal += 1

    raid_encounter_ids = [6001, 6002, 6003, 6004, 6005, 6006, 6007, 6008]
    entries.append(
        _entry(
            root,
            ordinal,
            "/data/wow/journal-instance/1320",
            {
                "id": 1320,
                "name": "The Venomous Abyss",
                "category": {"type": "RAID"},
                "modes": [{"mode": {"type": "MYTHIC"}}],
                "encounters": [{"id": encounter_id} for encounter_id in raid_encounter_ids],
            },
        )
    )
    ordinal += 1
    for index, encounter_id in enumerate(raid_encounter_ids):
        entries.append(
            _entry(
                root,
                ordinal,
                f"/data/wow/journal-encounter/{encounter_id}",
                {
                    "id": encounter_id,
                    "name": f"Raid boss {encounter_id}",
                    "category": {"type": "RAID"},
                    "instance": {"id": 1320},
                    "items": ([{"item": {"id": 1003, "name": "Raid item"}}] if index == 0 else []),
                },
            )
        )
        ordinal += 1

    entries.append(
        _entry(
            root,
            ordinal,
            "/data/wow/item-set/2065",
            {
                "id": 2065,
                "name": "Ophidian Oracle's Prophecy",
                "items": [{"id": 1002, "name": "Lair item"}],
                "effects": [{"required_count": 2, "display_string": "Set effect"}],
            },
        )
    )
    ordinal += 1
    for item_id, name in [(1001, "M+ item"), (1002, "Lair item"), (1003, "Raid item")]:
        entries.append(
            _entry(
                root,
                ordinal,
                f"/data/wow/item/{item_id}",
                {"id": item_id, "name": name},
            )
        )
        ordinal += 1
    entries.append(
        _entry(
            root,
            ordinal,
            "/data/wow/recipe/52446",
            {
                "id": 52446,
                "name": "Quel'dorei Softsteppers",
                "modified_crafting_slots": [{"slot_type": {"id": 459}}],
                "reagents": [],
            },
        )
    )

    manifest = {
        "schemaRevision": "s2-official-api-capture-manifest-v1",
        "seasonKey": "midnight-season-2",
        "status": "captured",
        "region": "us",
        "locale": "en_US",
        "namespace": "static-12.1.0_68914-us",
        "entries": entries,
    }
    _write_json(root / "capture-manifest.json", manifest)


class S2OfficialCaptureInventoryTest(unittest.TestCase):
    def test_inventory_preserves_four_source_membership_and_blocks_unresolved_recipe_output(self):
        with tempfile.TemporaryDirectory() as directory:
            capture_root = Path(directory) / "capture"
            prepare_capture(capture_root)

            report = build_official_capture_inventory(
                capture_root,
                product_scope=ROOT / "server/data/midnight-season-2/s2-product-content-scope-v1.json",
                source_policy=POLICY_PATH,
            )

            self.assertEqual(report["status"], "partial")
            self.assertEqual(
                report["coverageCounts"]["observedOfficialItemIdentityCountByLogicalSource"],
                {"crafted": None, "mythic_plus": 1, "raid": 2, "tier_set": 1},
            )
            self.assertEqual(report["coverageCounts"]["craftedRecipeRootCount"], 1)
            self.assertEqual(report["coverageCounts"]["tierSetMembershipCount"], 1)
            self.assertEqual(report["coverageCounts"]["simcReadyCount"], 0)
            self.assertTrue(report["notARelease"])
            self.assertFalse(report["activeManifestChanged"])
            raw_source_types = {
                (row["logicalSource"], row["rawSourceType"])
                for row in report["sourceMemberships"]
            }
            self.assertIn(("raid", "lair"), raw_source_types)
            self.assertIn(("raid", "raid"), raw_source_types)
            self.assertIn(("mythic_plus", "mythic_plus"), raw_source_types)
            self.assertEqual(report["craftedRecipes"][0]["status"], "blocked")
            self.assertIn("OFFICIAL_API_RECIPE_OUTPUT_MISSING", report["blockerCodes"])

    def test_inventory_rejects_response_hash_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            capture_root = Path(directory) / "capture"
            prepare_capture(capture_root)
            manifest_path = capture_root / "capture-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["entries"][0]["responseSha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(OfficialCaptureInventoryError, "hash"):
                build_official_capture_inventory(
                    capture_root,
                    product_scope=ROOT / "server/data/midnight-season-2/s2-product-content-scope-v1.json",
                    source_policy=POLICY_PATH,
                )


if __name__ == "__main__":
    unittest.main()
