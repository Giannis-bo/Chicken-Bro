import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CAPTURE_ROOT = (
    ROOT
    / "artifacts"
    / "releases"
    / "2026-08-19-s2-limited-db2-field-expansion"
    / "recipe-52446-min5"
)
SCRIPT = ROOT / "scripts" / "build-s2-crafted-closure.py"
SIMC_PROBE = (
    ROOT
    / "artifacts"
    / "releases"
    / "2026-08-19-s2-limited-db2-field-expansion"
    / "recipe-52446-min6"
    / "simc-probe.json"
)


class S2CraftedClosureCliTest(unittest.TestCase):
    def test_cli_writes_partial_report_without_promoting_it(self):
        spec = importlib.util.spec_from_file_location("s2_crafted_closure_cli", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            output = Path(directory) / "crafted-closure.json"
            code = module.main(
                [
                    "--capture-root",
                    str(CAPTURE_ROOT),
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
            output = Path(directory) / "crafted-closure-with-simc.json"
            code = module.main(
                [
                    "--capture-root",
                    str(CAPTURE_ROOT),
                    "--recipe-id",
                    "52446",
                    "--simc-probe",
                    str(SIMC_PROBE),
                    "--output",
                    str(output),
                ],
                repo_root=ROOT,
            )
            self.assertEqual(code, 3)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(
                report["simcReadiness"]["runtimeRevision"],
                "f50a2121bf894570146507496f3e113bff68e445",
            )
            self.assertIn(
                "SIMC_CLIENT_BUILD_MISMATCH",
                report["simcReadiness"]["blockerCodes"],
            )


if __name__ == "__main__":
    unittest.main()
