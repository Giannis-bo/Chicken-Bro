import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.s2_official_capture_inventory_test import prepare_capture


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts/build-s2-official-capture-inventory.py"
SCOPE = ROOT / "server/data/midnight-season-2/s2-product-content-scope-v1.json"
POLICY = ROOT / "server/data/midnight-season-2/source-policy.json"


class S2OfficialCaptureInventoryCliTest(unittest.TestCase):
    def test_cli_writes_non_promotable_partial_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            capture_root = Path(directory) / "capture"
            prepare_capture(capture_root)
            with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as output_directory:
                output = Path(output_directory) / "inventory.json"
                result = subprocess.run(
                    [
                        sys.executable,
                        str(CLI),
                        "--capture-root",
                        str(capture_root),
                        "--scope",
                        str(SCOPE),
                        "--source-policy",
                        str(POLICY),
                        "--output",
                        str(output),
                    ],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )

                self.assertEqual(result.returncode, 3, result.stderr)
                payload = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(payload["status"], "partial")
                self.assertTrue(payload["notARelease"])
                self.assertNotIn("simcRuntime", payload)

    def test_cli_rejects_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            capture_root = Path(directory) / "capture"
            prepare_capture(capture_root)
            with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as output_directory:
                output = Path(output_directory) / "inventory.json"
                output.write_text("{}", encoding="utf-8")
                result = subprocess.run(
                    [
                        sys.executable,
                        str(CLI),
                        "--capture-root",
                        str(capture_root),
                        "--scope",
                        str(SCOPE),
                        "--source-policy",
                        str(POLICY),
                        "--output",
                        str(output),
                    ],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("already exists", result.stderr)


if __name__ == "__main__":
    unittest.main()
