import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from server.s2_crafted_compatibility import (
    S2CraftedCompatibilityError,
    build_crafted_slot_category_targets,
)
from server.s2_official_api_fact_snapshot import request_key


def _write_json(path: Path, value):
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return body


def _entry(path: str, relative: str, body: bytes):
    namespace = "static-12.1.0_68914-us"
    return {
        "requestKey": request_key(path, {}, namespace=namespace, region="us", locale="en_US"),
        "path": path,
        "namespace": namespace,
        "region": "us",
        "locale": "en_US",
        "query": {},
        "responsePath": relative,
        "responseSha256": hashlib.sha256(body).hexdigest(),
        "responseBytes": len(body),
        "capturedAt": "2026-08-19T00:00:00Z",
        "pagination": {"page": 1, "pageCount": 1, "complete": True},
        "paginationParentRequestKey": None,
    }


def _manifest(entries):
    return {
        "schemaRevision": "s2-official-api-capture-manifest-v1",
        "seasonKey": "midnight-season-2",
        "status": "captured",
        "region": "us",
        "locale": "en_US",
        "namespace": "static-12.1.0_68914-us",
        "namespaces": ["static-12.1.0_68914-us"],
        "entries": entries,
    }


def _prepare(root: Path):
    recipe_root = root / "recipes"
    slot_root = root / "slots"
    recipe_raw = recipe_root / "raw"
    slot_raw = slot_root / "raw"
    recipe_raw.mkdir(parents=True)
    slot_raw.mkdir(parents=True)
    recipe = {
        "id": 100,
        "modified_crafting_slots": [
            {"display_order": 0, "slot_type": {"id": 502, "name": "Add Embellishment"}},
            {"display_order": 1, "slot_type": {"id": 459, "name": "Amplify Secondary Stat"}},
        ],
    }
    recipe_body = _write_json(recipe_raw / "100.json", recipe)
    _write_json(recipe_root / "capture-manifest.json", _manifest([
        _entry("/data/wow/recipe/100", "raw/100.json", recipe_body),
    ]))
    slot_entries = []
    for slot_id, categories in {
        459: [{"id": 869, "name": "Flux Cogwheel"}],
        502: [{"id": 854, "name": "Lucky Keychain"}],
    }.items():
        payload = {"id": slot_id, "name": "slot", "compatible_categories": categories}
        relative = f"raw/{slot_id}.json"
        body = _write_json(slot_raw / f"{slot_id}.json", payload)
        slot_entries.append(_entry(
            f"/data/wow/modified-crafting/reagent-slot-type/{slot_id}",
            relative,
            body,
        ))
    _write_json(slot_root / "capture-manifest.json", _manifest(slot_entries))
    targets = {
        "schemaRevision": "s2-crafted-output-targets-v1",
        "status": "verified",
        "recipeOutputEdges": [
            {"recipeId": "100", "itemId": "200", "status": "verified"},
        ],
    }
    targets_path = root / "targets.json"
    _write_json(targets_path, targets)
    return recipe_root, slot_root, targets_path


class S2CraftedCompatibilityTest(unittest.TestCase):
    def test_builds_category_targets_only_for_crafted_equipment_recipes(self):
        with tempfile.TemporaryDirectory() as directory:
            recipe_root, slot_root, targets = _prepare(Path(directory))

            result = build_crafted_slot_category_targets(
                recipe_capture_root=recipe_root,
                slot_capture_root=slot_root,
                crafted_targets=targets,
            )

            self.assertEqual(result["status"], "verified")
            self.assertEqual(result["equipmentRecipeCount"], 1)
            self.assertEqual(result["roleIds"], ["459", "502"])
            self.assertEqual(result["categoryIds"], ["854", "869"])
            self.assertEqual(result["categories"]["869"]["roleIds"], ["459"])
            self.assertEqual(result["categories"]["854"]["recipeIds"], ["100"])

    def test_fails_when_an_equipment_recipe_slot_type_response_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            recipe_root, slot_root, targets = _prepare(Path(directory))
            manifest_path = slot_root / "capture-manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["entries"] = [row for row in manifest["entries"] if not row["path"].endswith("/459")]
            _write_json(manifest_path, manifest)

            with self.assertRaisesRegex(S2CraftedCompatibilityError, "slot type 459"):
                build_crafted_slot_category_targets(
                    recipe_capture_root=recipe_root,
                    slot_capture_root=slot_root,
                    crafted_targets=targets,
                )


if __name__ == "__main__":
    unittest.main()
