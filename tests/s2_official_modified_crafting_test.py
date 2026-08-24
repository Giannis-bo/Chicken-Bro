import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from server.s2_official_modified_crafting import (
    OfficialModifiedCraftingError,
    build_slot_type_request_plan,
    capture_modified_crafting_slot_types,
    extract_slot_type_ids,
)
from server.s2_official_api_fact_snapshot import request_key


def _write_json(path: Path, value):
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return body


def _capture_entry(path: str, response_path: str, body: bytes):
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
        "namespace": namespace,
        "region": "us",
        "locale": "en_US",
        "query": {},
        "responsePath": response_path,
        "responseSha256": hashlib.sha256(body).hexdigest(),
        "responseBytes": len(body),
        "capturedAt": "2026-08-19T00:00:00Z",
        "pagination": {"page": 1, "pageCount": 1, "complete": True},
        "paginationParentRequestKey": None,
    }


def _prepare_recipe_capture(root: Path):
    raw = root / "raw"
    raw.mkdir(parents=True)
    recipes = [
        (52446, {"id": 52446, "modified_crafting_slots": [{"slot_type": {"id": 400}}]}),
        (52472, {"id": 52472, "modified_crafting_slots": [{"slot_type": {"id": 502}}, {"slot_type": {"id": 396}}]}),
        (51520, {"id": 51520, "modified_crafting_slots": None}),
    ]
    entries = []
    for recipe_id, payload in recipes:
        relative = f"raw/{recipe_id}.json"
        body = _write_json(root / relative, payload)
        entries.append(_capture_entry(f"/data/wow/recipe/{recipe_id}", relative, body))
    _write_json(
        root / "capture-manifest.json",
        {
            "schemaRevision": "s2-official-api-capture-manifest-v1",
            "seasonKey": "midnight-season-2",
            "status": "captured",
            "region": "us",
            "locale": "en_US",
            "namespace": "static-12.1.0_68914-us",
            "namespaces": ["static-12.1.0_68914-us"],
            "entries": entries,
        },
    )


class _Reader:
    def __init__(self):
        self.calls = []

    def get(self, path, *, namespace, region, locale, query):
        self.calls.append((path, namespace, region, locale, query))
        slot_id = int(path.rsplit("/", 1)[-1])
        return {
            "id": slot_id,
            "name": f"slot-{slot_id}",
            "compatible_categories": [{"id": 854, "name": "Lucky Keychain"}],
        }


class S2OfficialModifiedCraftingTest(unittest.TestCase):
    def test_extracts_exact_recipe_slot_type_ids_and_ignores_recipes_without_slots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            _prepare_recipe_capture(root)

            self.assertEqual(extract_slot_type_ids(root), ["396", "400", "502"])

    def test_rejects_a_recipe_slot_without_a_positive_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            _prepare_recipe_capture(root)
            recipe = root / "raw/52446.json"
            payload = json.loads(recipe.read_text())
            payload["modified_crafting_slots"][0]["slot_type"] = {}
            body = _write_json(recipe, payload)
            manifest_path = root / "capture-manifest.json"
            manifest = json.loads(manifest_path.read_text())
            entry = next(row for row in manifest["entries"] if row["path"].endswith("/52446"))
            entry["responseBytes"] = len(body)
            entry["responseSha256"] = hashlib.sha256(body).hexdigest()
            _write_json(manifest_path, manifest)

            with self.assertRaisesRegex(OfficialModifiedCraftingError, "slot_type.id"):
                extract_slot_type_ids(root)

    def test_builds_only_exact_official_slot_type_paths(self):
        plan = build_slot_type_request_plan(["502", "400", "502"])

        self.assertEqual([row["path"] for row in plan], [
            "/data/wow/modified-crafting/reagent-slot-type/400",
            "/data/wow/modified-crafting/reagent-slot-type/502",
        ])
        self.assertEqual(plan[0]["query"], {})
        self.assertEqual(plan[0]["namespace"], "static-12.1.0_68914-us")
        self.assertEqual(
            plan[0]["requestKey"],
            request_key(
                plan[0]["path"],
                {},
                namespace="static-12.1.0_68914-us",
                region="us",
                locale="en_US",
            ),
        )

    def test_capture_persists_raw_slot_responses_and_source_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            output = Path(directory) / "output"
            _prepare_recipe_capture(source)
            reader = _Reader()

            result = capture_modified_crafting_slot_types(
                source_capture_root=source,
                output_root=output,
                reader=reader,
                captured_at="2026-08-19T01:00:00Z",
            )

            self.assertEqual(result["status"], "captured")
            self.assertEqual(result["slotTypeIds"], ["396", "400", "502"])
            self.assertEqual(len(reader.calls), 3)
            metadata = json.loads((output / "slot-type-capture.json").read_text())
            self.assertEqual(metadata["sourceRecipeCount"], 3)
            self.assertEqual(metadata["slotTypeIds"], ["396", "400", "502"])
            self.assertTrue((output / "capture-manifest.json").exists())
            self.assertEqual(len(list((output / "raw").glob("*.json"))), 3)


if __name__ == "__main__":
    unittest.main()
