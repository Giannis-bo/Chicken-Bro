import unittest
import hashlib
import json

from server.gear_canonical_kernel import (
    CanonicalValueError,
    SealedCanonicalDocument,
    seal_canonical_document,
    verify_sealed_document,
)
from server.gear_exact_item_instance import seal_exact_item
from server.simc_item_effect_support import (
    _validate_effect_aggregate_payload,
    derive_exact_effect_subjects,
    resolve_exact_effect_support,
    resolve_exact_item_effect_support,
    valid_effect_tokens,
    valid_runtime_revision,
    verify_effect_record,
    validate_effect_record,
)
from server.simc_item_effect_support import seal_effect_record


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
}
EXACT_SLOT = {
    "itemId": "1001",
    "declaredItemLevel": 266,
    "bonusIds": ["13334"],
    "context": "heroic",
    "gemIds": ["240892"],
    "gemBonusIds": ["1514"],
    "gemItemLevels": [90],
    "enchantId": "7443",
    "craftedStats": ["crit", "haste"],
    "embellishmentIds": ["999001"],
    "redirectedBaseStats": [],
}


def exact_document(**overrides):
    result = seal_exact_item({**EXACT_SLOT, **overrides})
    if result.status != "verified":
        raise AssertionError(result.issues)
    return result.document


def canonical_record_payload(subject, **overrides):
    payload = {
        "schemaRevision": "simc-item-effect-record-v1",
        "status": "verified",
        "subjectKind": subject.kind,
        "subjectKey": subject.key,
        "subjectVariantSignature": subject.variant_signature,
        "hasDynamicEffect": False,
        "simcRuntimeRevision": RUNTIME,
        "verifiedAt": "2026-08-04T00:00:00Z",
    }
    payload.update(overrides)
    return payload


def canonical_record(subject, **overrides):
    result = seal_effect_record(
        canonical_record_payload(subject, **overrides),
        runtime_revision=RUNTIME,
    )
    if result.status != "verified":
        raise AssertionError(result.issues)
    return result.document


def static_record(subject):
    return seal_effect_record({
        **{field: subject[field] for field in ("subjectKind", "subjectKey", "subjectVariantSignature")},
        "schemaRevision": "simc-item-effect-authority-v1",
        "hasDynamicEffect": False,
        "simcRuntimeRevision": RUNTIME,
        "verifiedAt": "2026-08-04T00:00:00Z",
    })


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
                ("crafted_effect", "crit"),
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
        governed = seal_effect_record({
            **dynamic_subject,
            "schemaRevision": "simc-item-effect-record-v1",
            "hasDynamicEffect": True,
            "status": "verified",
            "simcRuntimeRevision": RUNTIME,
            "verifiedAt": "2026-08-04T00:00:00Z",
            "effectType": "on_use",
            "experimentSnapshotKey": "simulation-snapshot:sha256:" + ("4" * 64),
            "controlSnapshotKey": "simulation-snapshot:sha256:" + ("5" * 64),
            "expectedActionTokens": ["action"],
            "expectedBuffTokens": ["buff"],
        })
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
            support_records=[seal_effect_record({**dynamic_subject, "schemaRevision": "simc-item-effect-record-v1", "hasDynamicEffect": True, "status": "unsupported", "simcRuntimeRevision": RUNTIME, "unsupportedReason": "NOT_IMPLEMENTED", "verifiedAt": "2026-08-04T00:00:00Z"}), *records[1:]],
        )
        self.assertEqual(unsupported["status"], "unsupported")

    def test_gem_subject_signature_binds_id_bonus_id_and_item_level(self):
        first = resolve_exact_item_effect_support(ITEM, runtime_revision=RUNTIME, support_records=[])
        for selection in (
            {**ITEM["enhancementSelection"], "gemIds": ["gem-other", "gem-b"]},
            {**ITEM["enhancementSelection"], "gemBonusIds": ["bonus-a", "bonus-b"]},
            {**ITEM["enhancementSelection"], "gemItemLevels": [91, 90]},
        ):
            changed = resolve_exact_item_effect_support({**ITEM, "enhancementSelection": selection}, runtime_revision=RUNTIME, support_records=[])
            self.assertNotEqual(first["subjects"][1]["subjectVariantSignature"], changed["subjects"][1]["subjectVariantSignature"])

    def test_runtime_mismatched_unsupported_record_is_unknown(self):
        subjects = resolve_exact_item_effect_support(ITEM, runtime_revision=RUNTIME, support_records=[])["subjects"]
        result = resolve_exact_item_effect_support(ITEM, runtime_revision=RUNTIME, support_records=[seal_effect_record({**subjects[0], "schemaRevision": "simc-item-effect-record-v1", "hasDynamicEffect": True, "status": "unsupported", "simcRuntimeRevision": "old", "unsupportedReason": "NOT_IMPLEMENTED", "verifiedAt": "2026-08-04T00:00:00Z"}), *(static_record(subject) for subject in subjects[1:])])
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

    def test_static_record_is_runtime_bound_and_content_addressed(self):
        subjects = resolve_exact_item_effect_support(ITEM, runtime_revision=RUNTIME, support_records=[])["subjects"]
        stale = {**static_record(subjects[0]), "simcRuntimeRevision": "old"}
        forged = {**static_record(subjects[0]), "simcRuntimeRevision": RUNTIME, "supportRecordKey": "simc-item-effect-record:sha256:" + ("f" * 64)}
        for record in (stale, forged):
            result = resolve_exact_item_effect_support(ITEM, runtime_revision=RUNTIME, support_records=[record, *(static_record(subject) for subject in subjects[1:])])
            self.assertEqual(result["status"], "unknown")

    def test_dynamic_record_recomputes_content_key_and_rejects_same_key_different_content(self):
        subjects = resolve_exact_item_effect_support(ITEM, runtime_revision=RUNTIME, support_records=[])["subjects"]
        dynamic = {**subjects[0], "schemaRevision": "simc-item-effect-record-v1", "hasDynamicEffect": True, "status": "verified", "simcRuntimeRevision": RUNTIME, "supportRecordKey": "simc-item-effect-record:sha256:" + ("f" * 64), "verifiedAt": "2026-08-04T00:00:00Z", "effectType": "on_use", "experimentSnapshotKey": "simulation-snapshot:sha256:" + ("4" * 64), "controlSnapshotKey": "simulation-snapshot:sha256:" + ("5" * 64), "expectedActionTokens": ["action"], "expectedBuffTokens": ["buff"]}
        altered = {**dynamic, "expectedBuffTokens": ["different"]}
        for record in (dynamic, altered):
            result = resolve_exact_item_effect_support(ITEM, runtime_revision=RUNTIME, support_records=[record, *(static_record(subject) for subject in subjects[1:])])
            self.assertEqual(result["status"], "unknown")

    def test_gem_signature_uses_canonical_hash_without_delimiter_collisions(self):
        first = resolve_exact_item_effect_support({**ITEM, "enhancementSelection": {**ITEM["enhancementSelection"], "gemIds": ["a"], "gemBonusIds": ["b:c"], "gemItemLevels": ["d"]}}, runtime_revision=RUNTIME, support_records=[])
        second = resolve_exact_item_effect_support({**ITEM, "enhancementSelection": {**ITEM["enhancementSelection"], "gemIds": ["a"], "gemBonusIds": ["b"], "gemItemLevels": ["c:d"]}}, runtime_revision=RUNTIME, support_records=[])
        self.assertNotEqual(first["subjects"][1]["subjectVariantSignature"], second["subjects"][1]["subjectVariantSignature"])

    def test_unsupported_record_is_included_in_aggregate_identity(self):
        subject = resolve_exact_item_effect_support(ITEM, runtime_revision=RUNTIME, support_records=[])["subjects"][0]
        def unsupported(reason, verified_at):
            return seal_effect_record({**{field: subject[field] for field in ("subjectKind", "subjectKey", "subjectVariantSignature")}, "schemaRevision": "simc-item-effect-record-v1", "status": "unsupported", "hasDynamicEffect": True, "simcRuntimeRevision": RUNTIME, "unsupportedReason": reason, "verifiedAt": verified_at})
        first = resolve_exact_item_effect_support(ITEM, runtime_revision=RUNTIME, support_records=[unsupported("NOT_IMPLEMENTED", "2026-08-04T00:00:00Z"), *(static_record(value) for value in resolve_exact_item_effect_support(ITEM, runtime_revision=RUNTIME, support_records=[])["subjects"][1:])])
        second = resolve_exact_item_effect_support(ITEM, runtime_revision=RUNTIME, support_records=[unsupported("RUNTIME_GAP", "2026-08-04T01:00:00Z"), *(static_record(value) for value in resolve_exact_item_effect_support(ITEM, runtime_revision=RUNTIME, support_records=[])["subjects"][1:])])
        self.assertEqual(first["status"], "unsupported")
        self.assertTrue(first["supportRecordKeys"])
        self.assertNotEqual(first["effectSupportKey"], second["effectSupportKey"])

    def test_effect_records_reject_empty_runtime_and_malformed_tokens(self):
        subject = resolve_exact_item_effect_support(ITEM, runtime_revision=RUNTIME, support_records=[])["subjects"][0]
        bad = seal_effect_record({**{field: subject[field] for field in ("subjectKind", "subjectKey", "subjectVariantSignature")}, "schemaRevision": "simc-item-effect-record-v1", "status": "verified", "hasDynamicEffect": True, "simcRuntimeRevision": "", "effectType": "on_use", "experimentSnapshotKey": "simulation-snapshot:sha256:" + ("4" * 64), "controlSnapshotKey": "simulation-snapshot:sha256:" + ("5" * 64), "expectedActionTokens": ["bad\ntoken"], "expectedBuffTokens": ["buff"], "verifiedAt": "2026-08-04T00:00:00Z"})
        result = resolve_exact_item_effect_support(ITEM, runtime_revision="", support_records=[bad])
        self.assertEqual(result["status"], "unknown")

    def test_runtime_and_effect_token_limits_apply_to_raw_untrimmed_bytes(self):
        for runtime in (f" {RUNTIME}", f"{RUNTIME} ", f"{RUNTIME}\n", (" " * 2000) + RUNTIME):
            self.assertFalse(valid_runtime_revision(runtime), runtime)
        for tokens in (
            [" action"], ["action "], ["action\n"],
            [(" " * 10000) + "action"],
        ):
            self.assertFalse(valid_effect_tokens(tokens), tokens)

    def test_validate_effect_record_rejects_raw_padded_or_malformed_record_identities(self):
        subject = resolve_exact_item_effect_support(
            ITEM, runtime_revision=RUNTIME, support_records=[],
        )["subjects"][0]
        valid = static_record(subject)
        for field, replacements in (
            ("supportRecordKey", (
                f" {valid['supportRecordKey']}", f"{valid['supportRecordKey']} ",
                f"{valid['supportRecordKey']}\n", "x" * 300,
            )),
            ("subjectKey", (" 1001", "1001 ", "1001\n", "x" * 300)),
            ("simcRuntimeRevision", (
                f" {RUNTIME}", f"{RUNTIME} ", f"{RUNTIME}\n", "x" * 300,
            )),
        ):
            for replacement in replacements:
                record = {**valid, field: replacement}
                if field != "supportRecordKey":
                    record = seal_effect_record({
                        key: value for key, value in record.items()
                        if key != "supportRecordKey"
                    })
                runtime = replacement if field == "simcRuntimeRevision" else RUNTIME
                self.assertFalse(
                    validate_effect_record(record, runtime_revision=runtime),
                    (field, replacement),
                )

    def test_validate_effect_record_rejects_raw_malformed_snapshot_identities(self):
        subject = resolve_exact_item_effect_support(
            ITEM, runtime_revision=RUNTIME, support_records=[],
        )["subjects"][0]
        base = {
            **subject,
            "schemaRevision": "simc-item-effect-record-v1",
            "status": "verified",
            "hasDynamicEffect": True,
            "simcRuntimeRevision": RUNTIME,
            "effectType": "on_use",
            "expectedActionTokens": ["action"],
            "expectedBuffTokens": ["buff"],
            "experimentSnapshotKey": "simulation-snapshot:sha256:" + ("4" * 64),
            "controlSnapshotKey": "simulation-snapshot:sha256:" + ("5" * 64),
            "verifiedAt": "2026-08-04T00:00:00Z",
        }
        for field in ("experimentSnapshotKey", "controlSnapshotKey"):
            original = base[field]
            for replacement in (
                f" {original}", f"{original} ", f"{original}\n", "x" * 300,
            ):
                self.assertFalse(
                    validate_effect_record(
                        seal_effect_record({**base, field: replacement}),
                        runtime_revision=RUNTIME,
                    ),
                    (field, replacement),
                )

    def test_resolver_does_not_trim_runtime_or_subject_identity_when_matching(self):
        subjects = resolve_exact_item_effect_support(
            ITEM, runtime_revision=RUNTIME, support_records=[],
        )["subjects"]
        records = [static_record(subject) for subject in subjects]
        for invalid_runtime in (
            f" {RUNTIME} ", f"{RUNTIME}\n", "runtime\x00revision", "x" * 300,
        ):
            invalid_runtime_records = [
                seal_effect_record({
                    **{key: value for key, value in record.items() if key != "supportRecordKey"},
                    "simcRuntimeRevision": invalid_runtime,
                })
                for record in records
            ]
            self.assertEqual(
                resolve_exact_item_effect_support(
                    ITEM,
                    runtime_revision=invalid_runtime,
                    support_records=invalid_runtime_records,
                )["status"],
                "unknown",
                invalid_runtime,
            )
        padded_subject = seal_effect_record({
            **{key: value for key, value in records[0].items() if key != "supportRecordKey"},
            "subjectKey": " 1001 ",
        })
        self.assertEqual(
            resolve_exact_item_effect_support(
                ITEM,
                runtime_revision=RUNTIME,
                support_records=[padded_subject, *records[1:]],
            )["status"],
            "unknown",
        )


class SealedSimcItemEffectSupportTest(unittest.TestCase):
    def test_subjects_are_derived_only_from_reverified_sealed_exact(self):
        exact = exact_document()
        subjects = derive_exact_effect_subjects(exact)
        self.assertEqual(
            [(subject.kind, subject.key) for subject in subjects],
            [
                ("item", "1001"),
                ("gem", "240892"),
                ("enchant", "7443"),
                ("embellishment", "999001"),
                ("crafted_effect", "crit"),
                ("crafted_effect", "haste"),
            ],
        )
        expected_gem_payload = {
            "bonusIds": ["1514"],
            "id": "240892",
            "itemLevel": 90,
        }
        expected_gem_signature = "gem-variant:sha256:" + hashlib.sha256(
            json.dumps(
                expected_gem_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(subjects[1].variant_signature, expected_gem_signature)

        for invalid in (
            json.loads(exact.canonical_bytes),
            seal_canonical_document(
                document_kind="other",
                schema_revision=exact.schema_revision,
                payload=json.loads(exact.canonical_bytes),
                key_prefix="exact-item-instance:sha256:",
            ),
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(CanonicalValueError):
                    derive_exact_effect_subjects(invalid)

        tampered = object.__new__(SealedCanonicalDocument)
        object.__setattr__(tampered, "document_kind", exact.document_kind)
        object.__setattr__(tampered, "schema_revision", exact.schema_revision)
        object.__setattr__(
            tampered,
            "canonical_bytes",
            exact.canonical_bytes.replace(b'"1001"', b'"1002"'),
        )
        object.__setattr__(tampered, "content_key", exact.content_key)
        with self.assertRaises(CanonicalValueError):
            derive_exact_effect_subjects(tampered)

    def test_each_crafted_stat_requires_its_own_record(self):
        exact = exact_document()
        subjects = derive_exact_effect_subjects(exact)
        records = [
            canonical_record(subject)
            for subject in subjects
            if not (subject.kind == "crafted_effect" and subject.key == "haste")
        ]
        outcome = resolve_exact_effect_support(
            exact,
            runtime_revision=RUNTIME,
            records=records,
        )
        self.assertEqual(outcome.status, "unknown")
        self.assertIsNone(outcome.document)
        self.assertEqual(outcome.issues[0].code, "EFFECT_RECORD_MISSING")

    def test_static_dynamic_and_unsupported_records_share_one_seal(self):
        subject = derive_exact_effect_subjects(exact_document())[0]
        static = seal_effect_record(
            canonical_record_payload(subject), runtime_revision=RUNTIME,
        )
        dynamic = seal_effect_record(
            canonical_record_payload(
                subject,
                hasDynamicEffect=True,
                effectType="on_use",
                expectedActionTokens=["Thunderclap"],
                expectedBuffTokens=["Thunderclap Buff"],
                experimentSnapshotKey="simulation-snapshot:sha256:" + "4" * 64,
                controlSnapshotKey="simulation-snapshot:sha256:" + "5" * 64,
            ),
            runtime_revision=RUNTIME,
        )
        unsupported = seal_effect_record(
            canonical_record_payload(
                subject,
                status="unsupported",
                hasDynamicEffect=True,
                unsupportedReason="NOT_IMPLEMENTED",
            ),
            runtime_revision=RUNTIME,
        )
        for result in (static, dynamic, unsupported):
            with self.subTest(result=result):
                self.assertEqual(result.status, "verified")
                self.assertEqual(result.document.document_kind, "effect_record")
                self.assertEqual(
                    result.document.schema_revision,
                    "simc-item-effect-record-v1",
                )
                self.assertRegex(
                    result.document.content_key,
                    r"^simc-item-effect-record:sha256:[0-9a-f]{64}$",
                )
                self.assertTrue(
                    verify_effect_record(
                        result.document, runtime_revision=RUNTIME,
                    )
                )

    def test_record_boundary_rejects_unicode_padding_types_and_oversize(self):
        subject = derive_exact_effect_subjects(exact_document())[0]
        invalid_strings = (
            " padded", "padded ", "bad\rvalue", "bad\nvalue",
            "bad\u0085value", "bad\u0090value", "bad\u2028value",
            "bad\u2029value", "bad\u200dvalue", "x" * 257,
        )
        for field in (
            "subjectKey", "subjectVariantSignature", "simcRuntimeRevision",
        ):
            for value in (*invalid_strings, 7):
                with self.subTest(field=field, value=ascii(value)):
                    result = seal_effect_record(
                        canonical_record_payload(subject, **{field: value}),
                        runtime_revision=value if field == "simcRuntimeRevision" else RUNTIME,
                    )
                    self.assertEqual(result.status, "blocked")

        dynamic = canonical_record_payload(
            subject,
            hasDynamicEffect=True,
            effectType="on_use",
            expectedActionTokens=["Thunderclap"],
            expectedBuffTokens=["Thunderclap Buff"],
            experimentSnapshotKey="simulation-snapshot:sha256:" + "4" * 64,
            controlSnapshotKey="simulation-snapshot:sha256:" + "5" * 64,
        )
        for field in ("experimentSnapshotKey", "controlSnapshotKey"):
            for value in (*invalid_strings, False):
                with self.subTest(field=field, value=ascii(value)):
                    self.assertEqual(
                        seal_effect_record(
                            {**dynamic, field: value}, runtime_revision=RUNTIME,
                        ).status,
                        "blocked",
                    )

    def test_record_reload_rejects_forged_key_content_kind_schema_and_prefix(self):
        subject = derive_exact_effect_subjects(exact_document())[0]
        document = canonical_record(subject)
        payload = json.loads(document.canonical_bytes)
        wrong_documents = (
            seal_canonical_document(
                document_kind="other",
                schema_revision=document.schema_revision,
                payload=payload,
                key_prefix="simc-item-effect-record:sha256:",
            ),
            seal_canonical_document(
                document_kind="effect_record",
                schema_revision="wrong-schema",
                payload=payload,
                key_prefix="simc-item-effect-record:sha256:",
            ),
            seal_canonical_document(
                document_kind="effect_record",
                schema_revision=document.schema_revision,
                payload=payload,
                key_prefix="attacker:sha256:",
            ),
        )
        for forged in wrong_documents:
            self.assertFalse(
                verify_effect_record(forged, runtime_revision=RUNTIME)
            )

        for field, replacement in (
            ("canonical_bytes", document.canonical_bytes.replace(b'"verified"', b'"unsupported"')),
            ("content_key", " simc-item-effect-record:sha256:" + "f" * 64),
            ("content_key", "simc-item-effect-record:sha256:" + "f" * 64 + "\u2028"),
        ):
            forged = object.__new__(SealedCanonicalDocument)
            object.__setattr__(forged, "document_kind", document.document_kind)
            object.__setattr__(forged, "schema_revision", document.schema_revision)
            object.__setattr__(forged, "canonical_bytes", document.canonical_bytes)
            object.__setattr__(forged, "content_key", document.content_key)
            object.__setattr__(forged, field, replacement)
            self.assertFalse(
                verify_effect_record(forged, runtime_revision=RUNTIME)
            )

    def test_verified_aggregate_is_sealed_and_rejects_raw_records(self):
        exact = exact_document(craftedStats=[])
        subjects = derive_exact_effect_subjects(exact)
        records = [canonical_record(subject) for subject in subjects]
        outcome = resolve_exact_effect_support(
            exact, runtime_revision=RUNTIME, records=records,
        )
        self.assertEqual(outcome.status, "verified")
        self.assertEqual(outcome.issues, ())
        self.assertEqual(outcome.document.document_kind, "effect_aggregate")
        self.assertRegex(
            outcome.document.content_key,
            r"^simc-item-effect-support:sha256:[0-9a-f]{64}$",
        )
        payload = json.loads(outcome.document.canonical_bytes)
        self.assertEqual(payload["status"], "verified")
        self.assertEqual(payload["exactItemInstanceKey"], exact.content_key)
        self.assertEqual(len(payload["subjects"]), len(subjects))
        self.assertEqual(len(payload["supportRecords"]), len(subjects))
        self.assertEqual(
            resolve_exact_effect_support(
                exact, runtime_revision=RUNTIME, records=tuple(records),
            ).document,
            outcome.document,
        )

        raw = json.loads(records[0].canonical_bytes)
        invalid = resolve_exact_effect_support(
            exact,
            runtime_revision=RUNTIME,
            records=[raw, *records[1:]],
        )
        self.assertEqual(invalid.status, "unknown")
        self.assertIsNone(invalid.document)
        self.assertEqual(invalid.issues[0].code, "INVALID_EFFECT_RECORD")

    def test_aggregate_reload_binds_exact_runtime_kind_schema_prefix_and_bytes(self):
        exact = exact_document(craftedStats=[])
        records = [
            canonical_record(subject)
            for subject in derive_exact_effect_subjects(exact)
        ]
        document = resolve_exact_effect_support(
            exact, runtime_revision=RUNTIME, records=records,
        ).document

        def verifies(candidate, *, bound_exact=exact, runtime=RUNTIME):
            return verify_sealed_document(
                candidate,
                document_kind="effect_aggregate",
                schema_revision="simc-item-effect-support-v1",
                key_prefix="simc-item-effect-support:sha256:",
                payload_validator=lambda payload: _validate_effect_aggregate_payload(
                    payload,
                    exact=bound_exact,
                    runtime_revision=runtime,
                ),
            )

        self.assertTrue(verifies(document))
        self.assertFalse(verifies(document, bound_exact=exact_document(itemId="1002")))
        self.assertFalse(verifies(document, runtime="other-runtime"))
        payload = json.loads(document.canonical_bytes)
        for forged in (
            seal_canonical_document(
                document_kind="other",
                schema_revision=document.schema_revision,
                payload=payload,
                key_prefix="simc-item-effect-support:sha256:",
            ),
            seal_canonical_document(
                document_kind="effect_aggregate",
                schema_revision="wrong-schema",
                payload=payload,
                key_prefix="simc-item-effect-support:sha256:",
            ),
            seal_canonical_document(
                document_kind="effect_aggregate",
                schema_revision=document.schema_revision,
                payload=payload,
                key_prefix="attacker:sha256:",
            ),
        ):
            self.assertFalse(verifies(forged))

        tampered = object.__new__(SealedCanonicalDocument)
        object.__setattr__(tampered, "document_kind", document.document_kind)
        object.__setattr__(tampered, "schema_revision", document.schema_revision)
        object.__setattr__(
            tampered,
            "canonical_bytes",
            document.canonical_bytes.replace(b'"verified"', b'"unsupported"', 1),
        )
        object.__setattr__(tampered, "content_key", document.content_key)
        self.assertFalse(verifies(tampered))

    def test_unsupported_evidence_and_required_subjects_are_identity_bearing(self):
        exact = exact_document(craftedStats=[])
        subjects = derive_exact_effect_subjects(exact)

        def aggregate(reason, verified_at):
            unsupported = seal_effect_record(
                canonical_record_payload(
                    subjects[0],
                    status="unsupported",
                    hasDynamicEffect=True,
                    unsupportedReason=reason,
                    verifiedAt=verified_at,
                ),
                runtime_revision=RUNTIME,
            ).document
            return resolve_exact_effect_support(
                exact,
                runtime_revision=RUNTIME,
                records=[unsupported, *(canonical_record(subject) for subject in subjects[1:])],
            )

        first = aggregate("NOT_IMPLEMENTED", "2026-08-04T00:00:00Z")
        second = aggregate("RUNTIME_GAP", "2026-08-04T01:00:00Z")
        self.assertEqual(first.status, "unsupported")
        self.assertEqual(second.status, "unsupported")
        self.assertIsNotNone(first.document)
        self.assertNotEqual(
            first.document.content_key, second.document.content_key,
        )
        payload = json.loads(first.document.canonical_bytes)
        self.assertEqual(payload["status"], "unsupported")
        self.assertEqual(len(payload["subjects"]), len(subjects))
        self.assertEqual(
            payload["supportRecords"][0]["unsupportedReason"],
            "NOT_IMPLEMENTED",
        )
        self.assertEqual(
            payload["supportRecords"][0]["verifiedAt"],
            "2026-08-04T00:00:00Z",
        )
        self.assertEqual(
            payload["subjects"][0]["supportRecordKey"],
            first.document and json.loads(
                first.document.canonical_bytes
            )["supportRecords"][0]["supportRecordKey"],
        )

    def test_invalid_runtime_wrong_sequence_and_wrong_exact_fail_closed(self):
        exact = exact_document(craftedStats=[])
        subjects = derive_exact_effect_subjects(exact)
        records = [canonical_record(subject) for subject in subjects]
        for runtime in (
            f" {RUNTIME}", f"{RUNTIME} ", f"{RUNTIME}\n",
            f"{RUNTIME}\u0085", f"{RUNTIME}\u2028", f"{RUNTIME}\u200d",
            "x" * 257, False,
        ):
            with self.subTest(runtime=ascii(runtime)):
                outcome = resolve_exact_effect_support(
                    exact, runtime_revision=runtime, records=records,
                )
                self.assertEqual(outcome.status, "unknown")
                self.assertIsNone(outcome.document)
        self.assertEqual(
            resolve_exact_effect_support(
                exact, runtime_revision=RUNTIME, records={"records": records},
            ).status,
            "unknown",
        )
        self.assertEqual(
            resolve_exact_effect_support(
                json.loads(exact.canonical_bytes),
                runtime_revision=RUNTIME,
                records=records,
            ).status,
            "unknown",
        )
