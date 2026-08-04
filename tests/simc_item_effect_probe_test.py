import json
import unittest

from server.simc_item_effect_probe import evaluate_effect_probe
from server.simc_item_effect_support import seal_effect_record, verify_effect_record


RUNTIME = "simc-2026.08.04"
MANIFEST = {
    "subjectKind": "item",
    "subjectKey": "1001",
    "subjectVariantSignature": "exact-variant:sha256:" + ("1" * 64),
    "simcRuntimeRevision": RUNTIME,
    "effectType": "on_use",
    "expectedActionTokens": ["Thunderclap"],
    "expectedBuffTokens": ["Thunderclap Buff"],
    "controlSnapshotKey": "simulation-snapshot:sha256:" + ("2" * 64),
    "experimentSnapshotKey": "simulation-snapshot:sha256:" + ("3" * 64),
    "verifiedAt": "2026-08-04T00:00:00Z",
}
EXPERIMENT = {
    "runtimeRevision": RUNTIME,
    "snapshotKey": MANIFEST["experimentSnapshotKey"],
    "actions": ["Thunderclap"],
    "buffs": ["Thunderclap Buff"],
    "warnings": [],
    "timedOut": False,
    "exitCode": 0,
    "dps": 100,
}
CONTROL = {
    "runtimeRevision": RUNTIME,
    "snapshotKey": MANIFEST["controlSnapshotKey"],
    "actions": [],
    "buffs": [],
    "warnings": [],
    "timedOut": False,
    "exitCode": 0,
    "dps": 90,
}


class SimcItemEffectProbeTest(unittest.TestCase):
    def test_only_complete_differential_evidence_uses_shared_record_seal(self):
        result = evaluate_effect_probe(
            MANIFEST, EXPERIMENT, CONTROL, runtime_revision=RUNTIME,
        )
        self.assertEqual(result.status, "verified")
        self.assertTrue(
            verify_effect_record(result.document, runtime_revision=RUNTIME)
        )
        expected = seal_effect_record(
            {
                "schemaRevision": "simc-item-effect-record-v1",
                "status": "verified",
                "subjectKind": "item",
                "subjectKey": "1001",
                "subjectVariantSignature": "exact-variant:sha256:" + ("1" * 64),
                "hasDynamicEffect": True,
                "simcRuntimeRevision": RUNTIME,
                "effectType": "on_use",
                "expectedActionTokens": ["Thunderclap"],
                "expectedBuffTokens": ["Thunderclap Buff"],
                "experimentSnapshotKey": "simulation-snapshot:sha256:" + ("3" * 64),
                "controlSnapshotKey": "simulation-snapshot:sha256:" + ("2" * 64),
                "verifiedAt": "2026-08-04T00:00:00Z",
            },
            runtime_revision=RUNTIME,
        )
        self.assertEqual(result.document, expected.document)

    def test_exit_code_or_dps_difference_does_not_prove_effect_support(self):
        result = evaluate_effect_probe(
            MANIFEST,
            {**EXPERIMENT, "actions": [], "buffs": [], "dps": 999},
            CONTROL,
            runtime_revision=RUNTIME,
        )
        self.assertEqual(result.status, "blocked")
        self.assertIsNone(result.document)
        self.assertEqual(result.issues[0].code, "EXPECTED_TOKEN_MISSING")

    def test_probe_rejects_non_exact_boolean_integer_list_and_string_types(self):
        cases = (
            (MANIFEST, {**EXPERIMENT, "timedOut": 0}, CONTROL),
            (MANIFEST, {**EXPERIMENT, "exitCode": False}, CONTROL),
            (MANIFEST, {**EXPERIMENT, "exitCode": 0.0}, CONTROL),
            (MANIFEST, {**EXPERIMENT, "warnings": ""}, CONTROL),
            (MANIFEST, {**EXPERIMENT, "actions": ()}, CONTROL),
            (MANIFEST, {**EXPERIMENT, "snapshotKey": 3}, CONTROL),
            (MANIFEST, {**EXPERIMENT, "dps": True}, CONTROL),
            (MANIFEST, {**EXPERIMENT, "dps": 100.0}, CONTROL),
        )
        for manifest, experiment, control in cases:
            with self.subTest(experiment=experiment):
                result = evaluate_effect_probe(
                    manifest, experiment, control, runtime_revision=RUNTIME,
                )
                self.assertEqual(result.status, "blocked")

    def test_probe_rejects_control_characters_and_bounds_in_every_identity(self):
        invalid_strings = (
            " padded", "padded ", "bad\rvalue", "bad\nvalue",
            "bad\u0085value", "bad\u0090value", "bad\u2028value",
            "bad\u2029value", "bad\u200dvalue", "x" * 257,
        )
        for field in (
            "subjectKey", "subjectVariantSignature", "simcRuntimeRevision",
            "experimentSnapshotKey", "controlSnapshotKey",
        ):
            for value in invalid_strings:
                manifest = {**MANIFEST, field: value}
                experiment = {
                    **EXPERIMENT,
                    "runtimeRevision": value
                    if field == "simcRuntimeRevision" else RUNTIME,
                    "snapshotKey": value
                    if field == "experimentSnapshotKey"
                    else EXPERIMENT["snapshotKey"],
                }
                control = {
                    **CONTROL,
                    "runtimeRevision": value
                    if field == "simcRuntimeRevision" else RUNTIME,
                    "snapshotKey": value
                    if field == "controlSnapshotKey"
                    else CONTROL["snapshotKey"],
                }
                runtime = value if field == "simcRuntimeRevision" else RUNTIME
                with self.subTest(field=field, value=ascii(value)):
                    result = evaluate_effect_probe(
                        manifest,
                        experiment,
                        control,
                        runtime_revision=runtime,
                    )
                    self.assertEqual(result.status, "blocked")

    def test_probe_rejects_malformed_action_buff_and_warning_arrays(self):
        for field, value in (
            ("actions", ["action\u2028token"]),
            ("actions", [" action"]),
            ("buffs", ["buff\u0085token"]),
            ("warnings", ["warning\u200dtext"]),
            ("warnings", ["x" * 513]),
            ("actions", ["x" * 257]),
            ("actions", ["x"] * 33),
        ):
            result = evaluate_effect_probe(
                MANIFEST,
                {**EXPERIMENT, field: value},
                CONTROL,
                runtime_revision=RUNTIME,
            )
            self.assertEqual(result.status, "blocked", (field, value))

    def test_probe_binds_independent_runtime_and_exact_report_key_sets(self):
        for manifest, experiment, control, runtime in (
            ({**MANIFEST, "extra": True}, EXPERIMENT, CONTROL, RUNTIME),
            (MANIFEST, {**EXPERIMENT, "extra": True}, CONTROL, RUNTIME),
            (MANIFEST, EXPERIMENT, {key: value for key, value in CONTROL.items() if key != "dps"}, RUNTIME),
            (MANIFEST, EXPERIMENT, CONTROL, "other-runtime"),
            ({**MANIFEST, "simcRuntimeRevision": "other-runtime"}, EXPERIMENT, CONTROL, RUNTIME),
        ):
            result = evaluate_effect_probe(
                manifest, experiment, control, runtime_revision=runtime,
            )
            self.assertEqual(result.status, "blocked")

    def test_probe_requires_distinct_snapshots_and_clean_successful_reports(self):
        cases = (
            (
                {**MANIFEST, "controlSnapshotKey": MANIFEST["experimentSnapshotKey"]},
                EXPERIMENT,
                {**CONTROL, "snapshotKey": MANIFEST["experimentSnapshotKey"]},
            ),
            (MANIFEST, {**EXPERIMENT, "timedOut": True}, CONTROL),
            (MANIFEST, {**EXPERIMENT, "exitCode": 1}, CONTROL),
            (MANIFEST, {**EXPERIMENT, "warnings": ["item resolution warning"]}, CONTROL),
            (MANIFEST, EXPERIMENT, {**CONTROL, "buffs": ["Thunderclap Buff"]}),
        )
        for manifest, experiment, control in cases:
            result = evaluate_effect_probe(
                manifest, experiment, control, runtime_revision=RUNTIME,
            )
            self.assertEqual(result.status, "blocked")

    def test_probe_never_returns_raw_manifest_or_report_content_in_issues(self):
        secret = "private-profile-token"
        result = evaluate_effect_probe(
            {**MANIFEST, "subjectKey": secret + "\n"},
            EXPERIMENT,
            CONTROL,
            runtime_revision=RUNTIME,
        )
        self.assertEqual(result.status, "blocked")
        encoded_issues = json.dumps(
            [issue.__dict__ for issue in result.issues],
            sort_keys=True,
        )
        self.assertNotIn(secret, encoded_issues)
