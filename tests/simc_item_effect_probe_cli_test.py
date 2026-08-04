import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from server.simc_item_effect_probe import evaluate_effect_probe
from tests.simc_item_effect_probe_test import CONTROL, EXPERIMENT, MANIFEST, RUNTIME


class SimcItemEffectProbeCliTest(unittest.TestCase):
    def test_cli_prints_only_the_verified_canonical_record_bytes(self):
        completed = self._run_payloads(
            manifest=MANIFEST,
            experiment=EXPERIMENT,
            control=CONTROL,
            runtime=RUNTIME,
        )
        expected = evaluate_effect_probe(
            MANIFEST, EXPERIMENT, CONTROL, runtime_revision=RUNTIME,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout, expected.document.canonical_bytes)
        self.assertEqual(completed.stderr, b"")

    def test_cli_blocked_paths_have_empty_stdout_and_reason_code_only(self):
        cases = (
            (MANIFEST, {**EXPERIMENT, "actions": []}, CONTROL, RUNTIME),
            (MANIFEST, {**EXPERIMENT, "timedOut": 0}, CONTROL, RUNTIME),
            (MANIFEST, {**EXPERIMENT, "exitCode": False}, CONTROL, RUNTIME),
            (MANIFEST, {**EXPERIMENT, "warnings": ""}, CONTROL, RUNTIME),
            (MANIFEST, {**EXPERIMENT, "actions": ["action\u2028token"]}, CONTROL, RUNTIME),
            (MANIFEST, EXPERIMENT, CONTROL, "other-runtime"),
        )
        for manifest, experiment, control, runtime in cases:
            with self.subTest(experiment=experiment, runtime=runtime):
                completed = self._run_payloads(
                    manifest=manifest,
                    experiment=experiment,
                    control=control,
                    runtime=runtime,
                )
                self._assert_private_failure(completed)

    def test_cli_rejects_padded_control_and_oversize_runtime_without_echo(self):
        for runtime in (
            f" {RUNTIME}", f"{RUNTIME} ", f"{RUNTIME}\n",
            f"{RUNTIME}\u0085", f"{RUNTIME}\u2028", f"{RUNTIME}\u200d",
            "x" * 257,
        ):
            completed = self._run_payloads(
                manifest={**MANIFEST, "simcRuntimeRevision": runtime},
                experiment={**EXPERIMENT, "runtimeRevision": runtime},
                control={**CONTROL, "runtimeRevision": runtime},
                runtime=runtime,
            )
            self._assert_private_failure(completed)

    def test_cli_diagnostics_never_echo_manifest_profile_or_report_content(self):
        secret = "private-profile-secret"
        completed = self._run_payloads(
            manifest={**MANIFEST, "subjectKey": secret + "\n"},
            experiment={**EXPERIMENT, "warnings": [secret]},
            control=CONTROL,
            runtime=RUNTIME,
        )
        self._assert_private_failure(completed)
        self.assertNotIn(secret.encode("utf-8"), completed.stderr)
        self.assertNotIn(b"subjectKey", completed.stderr)
        self.assertNotIn(b"warnings", completed.stderr)

    def test_cli_invalid_json_and_missing_file_are_private_errors(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "private-profile.json"
            invalid.write_text('{"secret":', encoding="utf-8")
            valid = Path(directory) / "valid.json"
            valid.write_text(json.dumps(EXPERIMENT), encoding="utf-8")
            missing = Path(directory) / "missing-private-profile.json"
            for manifest_path in (invalid, missing):
                completed = subprocess.run(
                    [
                        "python3", "scripts/simc-item-effect-probe.py",
                        "--manifest", str(manifest_path),
                        "--experiment-report", str(valid),
                        "--control-report", str(valid),
                        "--runtime-revision", RUNTIME,
                    ],
                    cwd=root,
                    capture_output=True,
                    check=False,
                )
                self._assert_private_failure(completed)
                self.assertNotIn(str(manifest_path).encode("utf-8"), completed.stderr)

    def test_cli_argument_error_is_one_stable_reason_code(self):
        root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            ["python3", "scripts/simc-item-effect-probe.py"],
            cwd=root,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, b"")
        self.assertEqual(completed.stderr, b"CLI_ARGUMENT_INVALID\n")

    def _run_payloads(self, *, manifest, experiment, control, runtime):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            paths = {}
            for name, payload in (
                ("manifest", manifest),
                ("experiment", experiment),
                ("control", control),
            ):
                path = Path(directory) / f"{name}.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                paths[name] = path
            return subprocess.run(
                [
                    "python3", "scripts/simc-item-effect-probe.py",
                    "--manifest", str(paths["manifest"]),
                    "--experiment-report", str(paths["experiment"]),
                    "--control-report", str(paths["control"]),
                    "--runtime-revision", runtime,
                ],
                cwd=root,
                capture_output=True,
                check=False,
            )

    def _assert_private_failure(self, completed):
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, b"")
        self.assertRegex(completed.stderr, rb"^[A-Z][A-Z0-9_]*\n$")
