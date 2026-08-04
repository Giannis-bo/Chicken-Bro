import unittest
import hashlib

from server.simc_item_effect_support import resolve_exact_item_effect_support


RUNTIME = "simc-2026.08.04"
ITEM = {
    "itemId": "1001",
    "exactVariantSignature": "exact-variant:sha256:" + ("1" * 64),
    "enhancementSelection": {
        "gemIds": ["gem-a", "gem-b"],
        "enchantId": "ench-a",
        "embellishmentIds": ["emb-a"],
        "craftedStats": ["crit"],
    },
    "craftedEffectIds": ["craft-a"],
}


def static_record(subject):
    return {
        **subject, "schemaRevision": "simc-item-effect-authority-v1",
        "hasDynamicEffect": False,
        "supportRecordKey": "simc-item-effect-record:sha256:" + hashlib.sha256(f"{subject['subjectKind']}:{subject['subjectKey']}".encode()).hexdigest(),
        "verifiedAt": "2026-08-04T00:00:00Z",
    }


class SimcItemEffectSupportTest(unittest.TestCase):
    def test_enumerates_item_gems_enchant_embellishment_and_crafted_effect(self):
        result = resolve_exact_item_effect_support(
            ITEM, runtime_revision=RUNTIME, support_records=[]
        )
        self.assertEqual(
            [(entry["subjectKind"], entry["subjectKey"]) for entry in result["subjects"]],
            [
                ("item", "1001"), ("gem", "gem-a"), ("gem", "gem-b"),
                ("enchant", "ench-a"), ("embellishment", "emb-a"),
                ("crafted_effect", "craft-a"),
            ],
        )
        self.assertEqual(result["status"], "unknown")

    def test_static_authority_requires_explicit_no_dynamic_effect(self):
        subjects = resolve_exact_item_effect_support(
            ITEM, runtime_revision=RUNTIME, support_records=[]
        )["subjects"]
        unresolved = resolve_exact_item_effect_support(
            ITEM,
            runtime_revision=RUNTIME,
            support_records=[
                {**subjects[0]},
                *(static_record(subject) for subject in subjects[1:]),
            ],
        )
        self.assertEqual(unresolved["status"], "unknown")

    def test_aggregates_verified_unknown_unsupported_and_runtime_mismatch_fail_closed(self):
        initial = resolve_exact_item_effect_support(ITEM, runtime_revision=RUNTIME, support_records=[])
        records = [static_record(subject) for subject in initial["subjects"]]
        verified = resolve_exact_item_effect_support(ITEM, runtime_revision=RUNTIME, support_records=records)
        self.assertEqual(verified["status"], "verified")

        dynamic_subject = verified["subjects"][0]
        dynamic = {**dynamic_subject, "hasDynamicEffect": True}
        governed = {
            **dynamic_subject,
            "schemaRevision": "simc-item-effect-record-v1",
            "hasDynamicEffect": True,
            "status": "verified",
            "simcRuntimeRevision": RUNTIME,
            "supportRecordKey": "simc-item-effect-record:sha256:" + ("2" * 64),
            "verifiedAt": "2026-08-04T00:00:00Z",
            "effectType": "on_use",
            "experimentSnapshotKey": "simulation-snapshot:sha256:" + ("4" * 64),
            "controlSnapshotKey": "simulation-snapshot:sha256:" + ("5" * 64),
            "expectedActionTokens": ["action"],
            "expectedBuffTokens": ["buff"],
        }
        dynamic_verified = resolve_exact_item_effect_support(
            ITEM, runtime_revision=RUNTIME,
            support_records=[dynamic, governed, *records[1:]],
        )
        self.assertEqual(dynamic_verified["status"], "verified")

        exit_only = resolve_exact_item_effect_support(
            ITEM, runtime_revision=RUNTIME,
            support_records=[dynamic, {**governed, "exitCode": 0}, *records[1:]],
        )
        self.assertEqual(exit_only["status"], "unknown")

        mismatch = resolve_exact_item_effect_support(
            ITEM, runtime_revision=RUNTIME,
            support_records=[dynamic, {**governed, "simcRuntimeRevision": "other"}, *records[1:]],
        )
        self.assertEqual(mismatch["status"], "unknown")

        unsupported = resolve_exact_item_effect_support(
            ITEM, runtime_revision=RUNTIME,
            support_records=[{**dynamic_subject, "schemaRevision": "simc-item-effect-record-v1", "hasDynamicEffect": True, "status": "unsupported", "simcRuntimeRevision": RUNTIME, "supportRecordKey": "simc-item-effect-record:sha256:" + ("3" * 64), "unsupportedReason": "NOT_IMPLEMENTED"}, *records[1:]],
        )
        self.assertEqual(unsupported["status"], "unsupported")

    def test_gem_subject_signature_binds_id_bonus_id_and_item_level(self):
        first = resolve_exact_item_effect_support(ITEM, runtime_revision=RUNTIME, support_records=[])
        changed = resolve_exact_item_effect_support({**ITEM, "enhancementSelection": {**ITEM["enhancementSelection"], "gemBonusIds": ["bonus-a", "bonus-b"], "gemItemLevels": [91, 90]}}, runtime_revision=RUNTIME, support_records=[])
        self.assertNotEqual(first["subjects"][1]["subjectVariantSignature"], changed["subjects"][1]["subjectVariantSignature"])

    def test_runtime_mismatched_unsupported_record_is_unknown(self):
        subjects = resolve_exact_item_effect_support(ITEM, runtime_revision=RUNTIME, support_records=[])["subjects"]
        result = resolve_exact_item_effect_support(ITEM, runtime_revision=RUNTIME, support_records=[{**subjects[0], "schemaRevision": "simc-item-effect-record-v1", "hasDynamicEffect": True, "status": "unsupported", "simcRuntimeRevision": "old", "supportRecordKey": "simc-item-effect-record:sha256:" + ("3" * 64), "unsupportedReason": "NOT_IMPLEMENTED"}, *(static_record(subject) for subject in subjects[1:])])
        self.assertEqual(result["status"], "unknown")

    def test_dynamic_record_requires_strict_governed_schema_and_key(self):
        subjects = resolve_exact_item_effect_support(ITEM, runtime_revision=RUNTIME, support_records=[])["subjects"]
        malformed = {**subjects[0], "hasDynamicEffect": True, "status": "verified", "simcRuntimeRevision": RUNTIME, "supportRecordKey": "x", "verifiedAt": "y"}
        result = resolve_exact_item_effect_support(ITEM, runtime_revision=RUNTIME, support_records=[{**subjects[0], "hasDynamicEffect": True}, malformed, *(static_record(subject) for subject in subjects[1:])])
        self.assertEqual(result["status"], "unknown")

    def test_static_no_dynamic_effect_authority_has_bindable_record_identity(self):
        subjects = resolve_exact_item_effect_support(ITEM, runtime_revision=RUNTIME, support_records=[])["subjects"]
        result = resolve_exact_item_effect_support(ITEM, runtime_revision=RUNTIME, support_records=[*(static_record(subject) for subject in subjects)])
        self.assertEqual(result["status"], "verified")
        self.assertEqual(len(result["supportRecordKeys"]), len(subjects))
