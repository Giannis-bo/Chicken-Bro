import copy
import json
import unittest

from server import gear_loadout_effect_authority, gear_resolver
from server.gear_canonical_kernel import CanonicalValueError, seal_canonical_document
from server.simc_item_effect_support import seal_effect_record
from tests.gear_resolver_test import GearResolverTest


def resolver_snapshot():
    """Create a real current ``resolve_v2`` result with an active set effect."""
    fixture = GearResolverTest().fixture()
    return gear_resolver.resolve_v2(
        fixture["intent"], fixture["authorityContext"],
    )


def descriptor(item_set_id, pieces, subject_key):
    return {
        "subjectKind": "set_bonus",
        "itemSetId": item_set_id,
        "pieces": pieces,
        "subjectKey": subject_key,
    }


def snapshot_with_descriptors(descriptors):
    """Keep a real resolver result while varying its active ordered set state."""
    snapshot = copy.deepcopy(resolver_snapshot())
    ordered = sorted(
        descriptors,
        key=lambda value: (
            value["subjectKind"],
            value["itemSetId"],
            value["pieces"],
            value["subjectKey"],
        ),
    )
    effects = [{
        "effectId": value["subjectKey"],
        "itemSetId": value["itemSetId"],
        "pieces": value["pieces"],
        "sourceRefIds": [],
    } for value in ordered]
    snapshot["setState"]["activeDynamicEffects"] = effects
    snapshot["loadoutEffectSubjects"] = copy.deepcopy(ordered)
    snapshot["v2EffectBoundary"]["setState"] = copy.deepcopy(snapshot["setState"])
    snapshot["v2EffectBoundary"]["subjects"] = copy.deepcopy(ordered)
    return snapshot


def signature_for(snapshot, value):
    boundary = snapshot["v2EffectBoundary"]
    return seal_canonical_document(
        document_kind="loadout_effect_subject_signature",
        schema_revision="loadout-effect-subject-signature-v1",
        key_prefix="set_bonus-variant:sha256:",
        payload={
            "schemaRevision": "loadout-effect-subject-signature-v1",
            "subjectKind": value["subjectKind"],
            "subjectKey": value["subjectKey"],
            "itemSetId": value["itemSetId"],
            "pieces": value["pieces"],
            "resolvedGearSignature": boundary["resolvedGearSignature"],
            "gearRuleRevision": boundary["gearRuleRevision"],
            "resolverRevision": boundary["resolverRevision"],
            "simcRuntimeRevision": boundary["simcRuntimeRevision"],
        },
    ).content_key


def record_for(
    snapshot,
    value,
    *,
    unsupported=False,
    verified_at="2026-08-06T00:00:00Z",
):
    runtime = snapshot["v2EffectBoundary"]["simcRuntimeRevision"]
    payload = {
        "schemaRevision": "simc-item-effect-record-v1",
        "status": "unsupported" if unsupported else "verified",
        "subjectKind": value["subjectKind"],
        "subjectKey": value["subjectKey"],
        "subjectVariantSignature": signature_for(snapshot, value),
        "hasDynamicEffect": True if unsupported else False,
        "simcRuntimeRevision": runtime,
        "verifiedAt": verified_at,
    }
    if unsupported:
        payload["unsupportedReason"] = "RUNTIME_GAP"
    result = seal_effect_record(payload, runtime_revision=runtime)
    if result.status != "verified":
        raise AssertionError(result.issues)
    return result.document


def records_for(
    snapshot,
    *,
    unsupported_at=None,
    verified_at="2026-08-06T00:00:00Z",
):
    return [
        record_for(
            snapshot,
            value,
            unsupported=index == unsupported_at,
            verified_at=verified_at,
        )
        for index, value in enumerate(snapshot["loadoutEffectSubjects"])
    ]


def active_resolver_fixture(*, repeated_subject=False):
    """Return real Resolver inputs whose v2 boundary has loadout effects."""
    fixture = GearResolverTest().fixture()
    dependency = fixture["authorityContext"]["dependencyVector"]
    dependency["resolverContractRevision"] = "resolver-v2"
    dependency["simcRuntimeRevision"] = "simc-runtime-v2"
    fixture["intent"]["slots"] = {
        "head": fixture["intent"]["slots"]["head"],
    }
    fixture["authorityContext"]["ruleParameters"]["requiredSlots"] = ["head"]
    thresholds = fixture["authorityContext"]["ruleParameters"][
        "setAggregationInputs"
    ][0]["thresholds"]
    thresholds[0]["pieces"] = 1
    if repeated_subject:
        thresholds.extend([copy.deepcopy(thresholds[0]), copy.deepcopy(thresholds[0])])
    return fixture


def active_resolver_authority(*, repeated_subject=False, unsupported_at=None):
    """Resolve one genuine sealed authority for real active Resolver inputs."""
    fixture = active_resolver_fixture(repeated_subject=repeated_subject)
    blocked = gear_resolver.resolve_v2(
        fixture["intent"], fixture["authorityContext"],
    )
    outcome = gear_loadout_effect_authority.resolve_loadout_effect_authority(
        blocked,
        records=records_for(blocked, unsupported_at=unsupported_at),
    )
    return fixture, blocked, outcome


class GearLoadoutEffectAuthorityTest(unittest.TestCase):
    def test_resolver_only_matching_verified_authority_unblocks_active_subjects(self):
        """Would fail if malformed or context-mismatched authority could make v2 ready."""
        fixture, blocked, verified = active_resolver_authority()
        mismatched_snapshot = snapshot_with_descriptors([
            descriptor("set-other", 1, "set-other-1pc"),
        ])
        mismatched = gear_loadout_effect_authority.resolve_loadout_effect_authority(
            mismatched_snapshot,
            records=records_for(mismatched_snapshot),
        )
        unknown = gear_loadout_effect_authority.resolve_loadout_effect_authority(
            blocked,
            records=[],
        )

        for label, authority in (
            ("absent", None),
            ("malformed", {"status": "verified"}),
            ("mismatched", mismatched.document),
            ("unknown", unknown),
        ):
            with self.subTest(label):
                result = gear_resolver.resolve_v2(
                    fixture["intent"],
                    fixture["authorityContext"],
                    loadout_effect_authority=authority,
                )
                self.assertEqual(result["status"], "blocked")
                self.assertIn(
                    "LOADOUT_EFFECT_AUTHORITY_REQUIRED", result["problemCodes"],
                )
                self.assertEqual(result["v2EffectBoundary"]["status"], "blocked")
                self.assertNotIn(
                    "loadoutEffectAuthorityKey", result["v2EffectBoundary"],
                )

        ready = gear_resolver.resolve_v2(
            fixture["intent"],
            fixture["authorityContext"],
            loadout_effect_authority=verified.document,
        )
        self.assertEqual(ready["status"], "verified")
        self.assertTrue(ready["profileReadiness"]["simcReady"])
        self.assertNotIn("LOADOUT_EFFECT_AUTHORITY_REQUIRED", ready.get("problemCodes", []))
        self.assertEqual(ready["v2EffectBoundary"]["status"], "verified")
        self.assertEqual(
            ready["v2EffectBoundary"]["loadoutEffectAuthorityKey"],
            verified.document.content_key,
        )
        self.assertEqual(set(ready["v2EffectBoundary"]), {
            "schemaRevision", "status", "resolvedGearSignature", "setState",
            "subjects", "gearRuleRevision", "resolverRevision",
            "simcRuntimeRevision", "loadoutEffectAuthorityKey",
        })
        self.assertEqual(
            ready["v2EffectBoundary"]["subjects"], ready["loadoutEffectSubjects"],
        )

    def test_resolver_keeps_sealed_unsupported_authority_literally_blocked(self):
        """Would fail if sealed unsupported evidence were treated as verified or unknown."""
        fixture, _, unsupported = active_resolver_authority(unsupported_at=0)

        result = gear_resolver.resolve_v2(
            fixture["intent"],
            fixture["authorityContext"],
            loadout_effect_authority=unsupported.document,
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("LOADOUT_EFFECT_UNSUPPORTED", result["problemCodes"])
        self.assertNotIn("LOADOUT_EFFECT_AUTHORITY_REQUIRED", result["problemCodes"])
        self.assertEqual(result["v2EffectBoundary"]["status"], "blocked")
        self.assertNotIn(
            "loadoutEffectAuthorityKey", result["v2EffectBoundary"],
        )

    def test_complete_verified_aggregate_reloads_exact_bytes_and_key(self):
        snapshot = snapshot_with_descriptors([
            descriptor("set-a", 2, "set-a-2pc"),
            descriptor("set-b", 1, "set-b-1pc"),
        ])
        records = records_for(snapshot)

        outcome = gear_loadout_effect_authority.resolve_loadout_effect_authority(
            snapshot, records=records,
        )

        self.assertEqual(outcome.status, "verified")
        self.assertEqual(outcome.issues, ())
        self.assertEqual(
            outcome.document.document_kind, "loadout_effect_authority",
        )
        self.assertRegex(
            outcome.document.content_key,
            r"^loadout-effect-authority:sha256:[0-9a-f]{64}$",
        )
        payload = json.loads(outcome.document.canonical_bytes)
        self.assertEqual(set(payload), {
            "schemaRevision", "status", "resolvedGearSignature",
            "gearRuleRevision", "resolverRevision", "simcRuntimeRevision",
            "subjects", "supportRecords",
        })
        self.assertEqual(payload["status"], "verified")
        self.assertEqual(
            [entry["supportRecordKey"] for entry in payload["supportRecords"]],
            [record.content_key for record in records],
        )
        self.assertEqual(
            gear_loadout_effect_authority.reload_loadout_effect_authority(
                outcome.document.canonical_bytes,
                outcome.document.content_key,
                resolver_snapshot=snapshot,
            ),
            outcome.document,
        )
        self.assertTrue(
            gear_loadout_effect_authority.verify_loadout_effect_authority(
                outcome.document, resolver_snapshot=snapshot,
            )
        )

    def test_reload_rehydrates_each_embedded_record_instead_of_trusting_its_json(self):
        snapshot = snapshot_with_descriptors([
            descriptor("set-a", 2, "set-a-2pc"),
        ])
        outcome = gear_loadout_effect_authority.resolve_loadout_effect_authority(
            snapshot, records=records_for(snapshot),
        )
        hostile_payload = json.loads(outcome.document.canonical_bytes)
        hostile_payload["supportRecords"][0]["verifiedAt"] = "2026-08-06T01:00:00Z"
        hostile = seal_canonical_document(
            document_kind="loadout_effect_authority",
            schema_revision="loadout-effect-authority-v1",
            key_prefix="loadout-effect-authority:sha256:",
            payload=hostile_payload,
        )

        self.assertFalse(
            gear_loadout_effect_authority.verify_loadout_effect_authority(
                hostile, resolver_snapshot=snapshot,
            )
        )
        with self.assertRaises(CanonicalValueError):
            gear_loadout_effect_authority.reload_loadout_effect_authority(
                hostile.canonical_bytes,
                hostile.content_key,
                resolver_snapshot=snapshot,
            )

    def test_rejects_missing_extra_reordered_or_substituted_records(self):
        snapshot = snapshot_with_descriptors([
            descriptor("set-a", 2, "set-a-2pc"),
            descriptor("set-b", 1, "set-b-1pc"),
        ])
        records = records_for(snapshot)
        unrelated = record_for(
            snapshot, descriptor("set-c", 3, "set-c-3pc"),
        )
        cases = (
            (records[:-1], "missing"),
            ([*records, records[0]], "extra"),
            (list(reversed(records)), "reordered"),
            ([unrelated, records[1]], "substituted"),
        )

        for candidate, name in cases:
            with self.subTest(name=name):
                outcome = gear_loadout_effect_authority.resolve_loadout_effect_authority(
                    snapshot, records=candidate,
                )
                self.assertEqual(outcome.status, "unknown")
                self.assertIsNone(outcome.document)
                self.assertTrue(outcome.issues)

    def test_preserves_repeated_same_key_occurrences_positionally(self):
        snapshot = snapshot_with_descriptors([
            descriptor("set-a", 2, "set-a-2pc"),
            descriptor("set-a", 2, "set-a-2pc"),
        ])
        record = record_for(snapshot, snapshot["loadoutEffectSubjects"][0])

        outcome = gear_loadout_effect_authority.resolve_loadout_effect_authority(
            snapshot, records=[record, record],
        )

        self.assertEqual(outcome.status, "verified")
        payload = json.loads(outcome.document.canonical_bytes)
        self.assertEqual(len(payload["subjects"]), 2)
        self.assertEqual(
            [entry["supportRecordKey"] for entry in payload["subjects"]],
            [record.content_key, record.content_key],
        )

    def test_rejects_descriptor_signature_and_context_drift(self):
        baseline = snapshot_with_descriptors([descriptor("set-a", 2, "set-a-2pc")])
        baseline_records = records_for(baseline)

        descriptor_drift = copy.deepcopy(baseline)
        descriptor_drift["loadoutEffectSubjects"][0]["subjectKey"] = "other"
        descriptor_drift["v2EffectBoundary"]["subjects"][0]["subjectKey"] = "other"
        signature_drift = [record_for(
            baseline, descriptor("set-a", 3, "set-a-2pc"),
        )]
        revision_drift = copy.deepcopy(baseline)
        revision_drift["dependencyVector"]["gearRuleRevision"] = "gear-rule-v2"
        revision_drift["v2EffectBoundary"]["gearRuleRevision"] = "gear-rule-v2"
        runtime_drift = copy.deepcopy(baseline)
        runtime_drift["dependencyVector"]["simcRuntimeRevision"] = "simc-runtime-v2"
        runtime_drift["v2EffectBoundary"]["simcRuntimeRevision"] = "simc-runtime-v2"
        resolved_signature_drift = copy.deepcopy(baseline)
        resolved_signature_drift["resolvedGearSignature"] = "resolved-gear-v2"
        resolved_signature_drift["v2EffectBoundary"]["resolvedGearSignature"] = "resolved-gear-v2"
        cases = (
            (descriptor_drift, baseline_records, "descriptor"),
            (baseline, signature_drift, "signature"),
            (revision_drift, baseline_records, "revision"),
            (runtime_drift, baseline_records, "runtime"),
            (resolved_signature_drift, baseline_records, "resolved signature"),
        )

        for snapshot, records, name in cases:
            with self.subTest(name=name):
                outcome = gear_loadout_effect_authority.resolve_loadout_effect_authority(
                    snapshot, records=records,
                )
                self.assertEqual(outcome.status, "unknown")
                self.assertIsNone(outcome.document)

    def test_unsupported_evidence_seals_an_unsupported_aggregate(self):
        snapshot = snapshot_with_descriptors([
            descriptor("set-a", 2, "set-a-2pc"),
            descriptor("set-b", 1, "set-b-1pc"),
        ])

        outcome = gear_loadout_effect_authority.resolve_loadout_effect_authority(
            snapshot, records=records_for(snapshot, unsupported_at=1),
        )

        self.assertEqual(outcome.status, "unsupported")
        self.assertIsNotNone(outcome.document)
        self.assertTrue(outcome.issues)
        self.assertEqual(
            json.loads(outcome.document.canonical_bytes)["status"],
            "unsupported",
        )

    def test_accepts_128_occurrences_and_rejects_129(self):
        def occurrences(count):
            return [
                descriptor(
                    f"set-{index:03}", (index % 16) + 1,
                    f"effect-{index:03}",
                )
                for index in range(count)
            ]

        accepted = snapshot_with_descriptors(occurrences(128))
        accepted_outcome = (
            gear_loadout_effect_authority.resolve_loadout_effect_authority(
                accepted, records=records_for(accepted),
            )
        )
        rejected = snapshot_with_descriptors(occurrences(129))
        rejected_outcome = (
            gear_loadout_effect_authority.resolve_loadout_effect_authority(
                rejected, records=records_for(rejected),
            )
        )

        self.assertEqual(accepted_outcome.status, "verified")
        self.assertEqual(rejected_outcome.status, "unknown")
        self.assertIsNone(rejected_outcome.document)

    def test_rejects_unmodelled_tier_cross_slot_and_loadout_subject_kinds(self):
        for kind in ("tier", "cross_slot", "loadout"):
            with self.subTest(kind=kind):
                snapshot = snapshot_with_descriptors([
                    descriptor("set-a", 2, "set-a-2pc"),
                ])
                records = records_for(snapshot)
                snapshot["loadoutEffectSubjects"][0]["subjectKind"] = kind
                snapshot["v2EffectBoundary"]["subjects"][0]["subjectKind"] = kind
                outcome = gear_loadout_effect_authority.resolve_loadout_effect_authority(
                    snapshot, records=records,
                )
                self.assertEqual(outcome.status, "unknown")
                self.assertIsNone(outcome.document)


if __name__ == "__main__":
    unittest.main()
