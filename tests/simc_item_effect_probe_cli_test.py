import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.simc_item_effect_probe_test import CONTROL, EXPERIMENT, MANIFEST


class SimcItemEffectProbeCliTest(unittest.TestCase):
    def test_cli_only_reads_local_inputs_and_prints_canonical_evaluator_result(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            paths = {}
            for name, payload in (("manifest", MANIFEST), ("experiment", EXPERIMENT), ("control", CONTROL)):
                path = Path(directory) / f"{name}.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                paths[name] = path
            completed = subprocess.run(
                ["python3", "scripts/simc-item-effect-probe.py", "--manifest", str(paths["manifest"]), "--experiment-report", str(paths["experiment"]), "--control-report", str(paths["control"]), "--runtime-revision", MANIFEST["simcRuntimeRevision"]],
                cwd=root, capture_output=True, text=True, check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["status"], "verified")

    def test_cli_unknown_emits_no_stdout_and_returns_nonzero(self):
        self._assert_cli_failure({**EXPERIMENT, "actions": []}, RUNTIME=MANIFEST["simcRuntimeRevision"])

    def test_cli_binds_manifest_and_reports_to_independent_current_runtime(self):
        self._assert_cli_failure(EXPERIMENT, RUNTIME="other-runtime")

    def test_cli_rejects_unsealable_manifest_without_stdout(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            paths = {}
            for name, payload in (("manifest", {**MANIFEST, "verifiedAt": "not-a-time"}), ("experiment", EXPERIMENT), ("control", CONTROL)):
                path = Path(directory) / f"{name}.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                paths[name] = path
            completed = subprocess.run(["python3", "scripts/simc-item-effect-probe.py", "--manifest", str(paths["manifest"]), "--experiment-report", str(paths["experiment"]), "--control-report", str(paths["control"]), "--runtime-revision", MANIFEST["simcRuntimeRevision"]], cwd=root, capture_output=True, text=True, check=False)
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "")

    def test_cli_rejects_malformed_token_and_boolean_exit_without_stdout(self):
        self._assert_cli_failure({**EXPERIMENT, "exitCode": False}, RUNTIME=MANIFEST["simcRuntimeRevision"])

    def _assert_cli_failure(self, experiment, *, RUNTIME):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            paths = {}
            for name, payload in (("manifest", MANIFEST), ("experiment", experiment), ("control", CONTROL)):
                path = Path(directory) / f"{name}.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                paths[name] = path
            completed = subprocess.run(["python3", "scripts/simc-item-effect-probe.py", "--manifest", str(paths["manifest"]), "--experiment-report", str(paths["experiment"]), "--control-report", str(paths["control"]), "--runtime-revision", RUNTIME], cwd=root, capture_output=True, text=True, check=False)
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "")
