import unittest

from server.simc_item_effect_probe import evaluate_effect_probe
from server.simc_item_effect_support import resolve_exact_item_effect_support


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
EXPERIMENT = {"runtimeRevision": RUNTIME, "snapshotKey": MANIFEST["experimentSnapshotKey"], "actions": ["Thunderclap"], "buffs": ["Thunderclap Buff"], "warnings": [], "timedOut": False, "exitCode": 0, "dps": 100}
CONTROL = {"runtimeRevision": RUNTIME, "snapshotKey": MANIFEST["controlSnapshotKey"], "actions": [], "buffs": [], "warnings": [], "timedOut": False, "exitCode": 0, "dps": 90}


class SimcItemEffectProbeTest(unittest.TestCase):
    def test_only_complete_differential_evidence_seals_a_verified_record(self):
        result = evaluate_effect_probe(MANIFEST, EXPERIMENT, CONTROL)
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["simcRuntimeRevision"], RUNTIME)
        self.assertTrue(result["supportRecordKey"].startswith("simc-item-effect-record:sha256:"))

    def test_exit_code_or_dps_difference_does_not_prove_effect_support(self):
        result = evaluate_effect_probe(
            MANIFEST,
            {**EXPERIMENT, "actions": [], "buffs": [], "dps": 999},
            CONTROL,
        )
        self.assertEqual(result["status"], "unknown")

    def test_rejects_manifest_allowlist_runtime_identity_warnings_timeout_and_missing_tokens(self):
        for manifest, experiment, control in (
            ({**MANIFEST, "unexpected": True}, EXPERIMENT, CONTROL),
            ({**MANIFEST, "simcRuntimeRevision": "other"}, EXPERIMENT, CONTROL),
            (MANIFEST, {**EXPERIMENT, "snapshotKey": "simulation-snapshot:sha256:" + ("4" * 64)}, CONTROL),
            (MANIFEST, {**EXPERIMENT, "warnings": ["item-resolution warning"]}, CONTROL),
            (MANIFEST, {**EXPERIMENT, "timedOut": True}, CONTROL),
            (MANIFEST, {**EXPERIMENT, "actions": []}, CONTROL),
            (MANIFEST, EXPERIMENT, {**CONTROL, "buffs": ["Thunderclap Buff"]}),
        ):
            result = evaluate_effect_probe(manifest, experiment, control)
            self.assertEqual(result["status"], "unknown")

    def test_probe_requires_distinct_experiment_and_control_snapshots(self):
        result = evaluate_effect_probe({**MANIFEST, "controlSnapshotKey": MANIFEST["experimentSnapshotKey"]}, EXPERIMENT, {**CONTROL, "snapshotKey": MANIFEST["experimentSnapshotKey"]})
        self.assertEqual(result["status"], "unknown")

    def test_nonzero_exit_cannot_seal_verified_record(self):
        result = evaluate_effect_probe(MANIFEST, {**EXPERIMENT, "exitCode": 1}, CONTROL)
        self.assertEqual(result["status"], "unknown")

    def test_probe_rejects_unsealable_manifest_identity_timestamp_and_tokens(self):
        for manifest in (
            {**MANIFEST, "experimentSnapshotKey": "experiment"},
            {**MANIFEST, "subjectVariantSignature": "not-a-variant"},
            {**MANIFEST, "verifiedAt": "not-a-time"},
            {**MANIFEST, "expectedActionTokens": [123]},
        ):
            self.assertEqual(evaluate_effect_probe(manifest, EXPERIMENT, CONTROL)["status"], "unknown")

    def test_verified_probe_record_is_immediately_accepted_by_effect_support(self):
        record = evaluate_effect_probe(MANIFEST, EXPERIMENT, CONTROL)
        support = resolve_exact_item_effect_support({"itemId": "1001", "exactVariantSignature": MANIFEST["subjectVariantSignature"], "enhancementSelection": {}}, runtime_revision=RUNTIME, support_records=[record])
        self.assertEqual(support["status"], "verified")
