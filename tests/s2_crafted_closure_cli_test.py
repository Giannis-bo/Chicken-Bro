import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from tests.s2_crafted_closure_fixture import (
    SIMC_COMMIT,
    write_crafted_capture,
    write_simc_probe,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build-s2-crafted-closure.py"


class S2CraftedClosureCliTest(unittest.TestCase):
    def test_cli_writes_partial_report_without_promoting_it(self):
        spec = importlib.util.spec_from_file_location("s2_crafted_closure_cli", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            fixture_root = Path(directory)
            capture_root = write_crafted_capture(fixture_root / "capture")
            output = fixture_root / "crafted-closure.json"
            code = module.main(
                [
                    "--capture-root",
                    str(capture_root),
                    "--recipe-id",
                    "52446",
                    "--output",
                    str(output),
                ],
                repo_root=ROOT,
            )
            self.assertEqual(code, 3)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "partial")
            self.assertTrue(report["notARelease"])
            self.assertFalse(report["activeManifestChanged"])
            self.assertFalse(report["productionWritten"])

    def test_cli_binds_optional_simc_probe_identity_and_blockers(self):
        spec = importlib.util.spec_from_file_location("s2_crafted_closure_cli", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            fixture_root = Path(directory)
            capture_root = write_crafted_capture(fixture_root / "capture")
            simc_probe = write_simc_probe(fixture_root / "simc-probe.json")
            output = fixture_root / "crafted-closure-with-simc.json"
            code = module.main(
                [
                    "--capture-root",
                    str(capture_root),
                    "--recipe-id",
                    "52446",
                    "--simc-probe",
                    str(simc_probe),
                    "--output",
                    str(output),
                ],
                repo_root=ROOT,
            )
            self.assertEqual(code, 3)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(
                report["simcReadiness"]["runtimeRevision"],
                SIMC_COMMIT,
            )
            self.assertIn(
                "SIMC_CLIENT_BUILD_MISMATCH",
                report["simcReadiness"]["blockerCodes"],
            )


if __name__ == "__main__":
    unittest.main()
