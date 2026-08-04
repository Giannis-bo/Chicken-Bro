import unittest

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
    return {**subject, "hasDynamicEffect": False}


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
            "hasDynamicEffect": True,
            "status": "verified",
            "simcRuntimeRevision": RUNTIME,
            "supportRecordKey": "simc-item-effect-record:sha256:" + ("2" * 64),
            "verifiedAt": "2026-08-04T00:00:00Z",
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
            support_records=[{**dynamic_subject, "status": "unsupported"}, *records[1:]],
        )
        self.assertEqual(unsupported["status"], "unsupported")
