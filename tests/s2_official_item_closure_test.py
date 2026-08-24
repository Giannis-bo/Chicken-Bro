import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "capture-s2-official-item-closure.py"


def load_capture_module():
    spec = importlib.util.spec_from_file_location("s2_official_item_closure", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body


class S2OfficialItemClosureTest(unittest.TestCase):
    def test_allow_missing_records_404_as_partial_without_fake_item(self):
        module = load_capture_module()

        def fake_urlopen(request, timeout):
            url = request.full_url
            if url == "https://oauth.battle.net/token":
                return FakeResponse(b'{"access_token":"test-token"}')
            if "/item/100?" in url:
                return FakeResponse(b'{"id":100,"name":"Observed modifier"}')
            if "/item/101?" in url:
                raise HTTPError(
                    url,
                    404,
                    "Not Found",
                    hdrs=None,
                    fp=io.BytesIO(b"not found"),
                )
            raise AssertionError(url)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "capture"
            env_file = Path(directory) / "env"
            env_file.write_text(
                "WOW_BLIZZARD_CLIENT_ID=test-id\n"
                "WOW_BLIZZARD_CLIENT_SECRET=test-secret\n",
                encoding="utf-8",
            )
            with patch.object(module, "urlopen", side_effect=fake_urlopen):
                result = module.capture_item_closure(
                    item_ids=["100", "101"],
                    output_root=root,
                    env_file=env_file,
                    client_build="12.1.0.68914",
                    namespace="static-12.1.0_68914-us",
                    workers=1,
                    allow_missing=True,
                )

            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["itemCount"], 1)
            self.assertEqual(result["missingCount"], 1)
            manifest = json.loads(
                (root / "capture-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["status"], "partial")
            self.assertEqual(manifest["missingItems"][0]["itemId"], "101")
            self.assertEqual(manifest["missingItems"][0]["httpStatus"], 404)
            self.assertEqual(len(manifest["entries"]), 1)
            self.assertEqual(
                json.loads((root / "raw" / "100.json").read_text())["id"],
                100,
            )
            self.assertFalse((root / "raw" / "101.json").exists())


if __name__ == "__main__":
    unittest.main()
