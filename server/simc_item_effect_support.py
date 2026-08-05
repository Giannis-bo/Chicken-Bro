#!/usr/bin/env python3
"""Canonical, content-addressed SimC effect authority for one sealed Exact item."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
import re
from typing import Literal

try:
    from .gear_canonical_kernel import (
        CanonicalIssue,
        CanonicalResult,
        CanonicalValueError,
        SealedCanonicalDocument,
        _rehydrate_canonical_document,
        canonical_identity_token,
        canonical_mapping,
        canonical_ordered_list,
        canonical_report_token,
        seal_canonical_document,
        verified_payload_copy,
        verify_sealed_document,
    )
    from .gear_exact_item_instance import (
        EXACT_ITEM_DOCUMENT_KIND,
        EXACT_ITEM_IDENTITY_SCHEMA_REVISION,
        EXACT_ITEM_KEY_PREFIX,
        _validate_exact_item_payload,
    )
except ImportError:
    from gear_canonical_kernel import (
        CanonicalIssue,
        CanonicalResult,
        CanonicalValueError,
        SealedCanonicalDocument,
        _rehydrate_canonical_document,
        canonical_identity_token,
        canonical_mapping,
        canonical_ordered_list,
        canonical_report_token,
        seal_canonical_document,
        verified_payload_copy,
        verify_sealed_document,
    )
    from gear_exact_item_instance import (
        EXACT_ITEM_DOCUMENT_KIND,
        EXACT_ITEM_IDENTITY_SCHEMA_REVISION,
        EXACT_ITEM_KEY_PREFIX,
        _validate_exact_item_payload,
    )


EFFECT_RECORD_SCHEMA_REVISION = "simc-item-effect-record-v1"
EFFECT_SUPPORT_SCHEMA_REVISION = "simc-item-effect-support-v1"
EFFECT_RECORD_DOCUMENT_KIND = "effect_record"
EFFECT_AGGREGATE_DOCUMENT_KIND = "effect_aggregate"
EFFECT_RECORD_KEY_PREFIX = "simc-item-effect-record:sha256:"
EFFECT_AGGREGATE_KEY_PREFIX = "simc-item-effect-support:sha256:"
EFFECT_SUBJECT_KINDS = (
    "item", "gem", "enchant", "embellishment", "crafted_effect", "set_bonus",
)

_STATIC_RECORD_KEYS = frozenset({
    "schemaRevision", "status", "subjectKind", "subjectKey",
    "subjectVariantSignature", "hasDynamicEffect", "simcRuntimeRevision",
    "verifiedAt",
})
_DYNAMIC_RECORD_KEYS = frozenset({
    *_STATIC_RECORD_KEYS,
    "effectType", "expectedActionTokens", "expectedBuffTokens",
    "experimentSnapshotKey", "controlSnapshotKey",
})
_UNSUPPORTED_RECORD_KEYS = frozenset({
    *_STATIC_RECORD_KEYS, "unsupportedReason",
})
_AGGREGATE_KEYS = frozenset({
    "schemaRevision", "status", "exactItemInstanceKey",
    "simcRuntimeRevision", "subjects", "supportRecords",
})
_AGGREGATE_SUBJECT_KEYS = frozenset({
    "subjectKind", "subjectKey", "subjectVariantSignature", "status",
    "supportRecordKey",
})
_SNAPSHOT_KEY_PATTERN = re.compile(
    r"^simulation-snapshot:sha256:[0-9a-f]{64}$"
)
_VARIANT_SIGNATURE_PATTERN = re.compile(
    r"^(?:exact|[a-z_]+-variant):sha256:[0-9a-f]{64}$"
)
_EXACT_KEY_PATTERN = re.compile(
    r"^exact-item-instance:sha256:[0-9a-f]{64}$"
)
_RECORD_KEY_PATTERN = re.compile(
    r"^simc-item-effect-record:sha256:[0-9a-f]{64}$"
)
_EFFECT_TYPES = frozenset({"on_use", "proc", "buff"})
_MAX_EFFECT_TOKENS = 32
_MAX_EFFECT_SEQUENCE_BYTES = 4096


@dataclass(frozen=True)
class EffectSubject:
    kind: Literal[
        "item", "gem", "enchant", "embellishment", "crafted_effect",
        "set_bonus",
    ]
    key: str
    variant_signature: str


@dataclass(frozen=True)
class EffectSupportOutcome:
    status: Literal["verified", "unknown", "unsupported"]
    document: SealedCanonicalDocument | None
    issues: tuple[CanonicalIssue, ...]

    def __post_init__(self) -> None:
        if self.status == "verified":
            if (
                type(self.document) is not SealedCanonicalDocument
                or type(self.issues) is not tuple
                or self.issues
            ):
                raise ValueError(
                    "Verified effect support requires one sealed aggregate."
                )
            return
        if self.status == "unsupported":
            if (
                type(self.document) is not SealedCanonicalDocument
                or type(self.issues) is not tuple
                or not self.issues
            ):
                raise ValueError(
                    "Unsupported effect support requires sealed evidence and issues."
                )
            return
        if self.status == "unknown":
            if (
                self.document is not None
                or type(self.issues) is not tuple
                or not self.issues
            ):
                raise ValueError(
                    "Unknown effect support requires issues and no document."
                )
            return
        raise ValueError("Effect support status must be verified, unknown, or unsupported.")


def _issue(code: str, path: str, recovery_action: str) -> CanonicalIssue:
    return CanonicalIssue(code, path, recovery_action)


def _blocked(error: CanonicalValueError) -> CanonicalResult:
    return CanonicalResult(
        "blocked",
        None,
        (_issue(
            error.code,
            error.path,
            "Recreate the effect evidence from canonical Exact and runtime inputs.",
        ),),
    )


def _unknown(code: str, path: str, recovery_action: str) -> EffectSupportOutcome:
    return EffectSupportOutcome(
        "unknown", None, (_issue(code, path, recovery_action),),
    )


def _canonical_runtime(value: object, *, path: str) -> str:
    return canonical_identity_token(value, path=path, max_bytes=256)


def _canonical_subject_kind(value: object, *, path: str) -> str:
    kind = canonical_identity_token(value, path=path)
    if kind not in EFFECT_SUBJECT_KINDS:
        raise CanonicalValueError("INVALID_EFFECT_SUBJECT_KIND", path)
    return kind


def _canonical_variant_signature(value: object, *, path: str) -> str:
    signature = canonical_identity_token(value, path=path)
    if _VARIANT_SIGNATURE_PATTERN.fullmatch(signature) is None:
        raise CanonicalValueError("INVALID_EFFECT_VARIANT_SIGNATURE", path)
    return signature


def _canonical_snapshot_key(value: object, *, path: str) -> str:
    snapshot_key = canonical_identity_token(value, path=path)
    if _SNAPSHOT_KEY_PATTERN.fullmatch(snapshot_key) is None:
        raise CanonicalValueError("INVALID_SNAPSHOT_KEY", path)
    return snapshot_key


def _canonical_timestamp(value: object, *, path: str) -> str:
    timestamp = canonical_identity_token(value, path=path, max_bytes=64)
    if not timestamp.endswith("Z"):
        raise CanonicalValueError("INVALID_TIMESTAMP", path)
    try:
        parsed = datetime.fromisoformat(timestamp[:-1] + "+00:00")
    except ValueError as error:
        raise CanonicalValueError("INVALID_TIMESTAMP", path) from error
    if parsed.tzinfo is None:
        raise CanonicalValueError("INVALID_TIMESTAMP", path)
    return timestamp


def _canonical_effect_token(value: object, path: str) -> str:
    return canonical_report_token(value, path=path, max_bytes=256)


def _canonical_effect_tokens(
    value: object,
    *,
    path: str,
    allow_empty: bool = False,
) -> list[str]:
    tokens = canonical_ordered_list(
        value,
        path=path,
        item_rule=_canonical_effect_token,
        max_items=_MAX_EFFECT_TOKENS,
    )
    if not allow_empty and not tokens:
        raise CanonicalValueError("EFFECT_TOKENS_REQUIRED", path)
    if sum(len(token.encode("utf-8")) for token in tokens) > _MAX_EFFECT_SEQUENCE_BYTES:
        raise CanonicalValueError("EFFECT_TOKEN_SEQUENCE_BOUNDS", path)
    return list(tokens)


def _validate_effect_record_payload(
    value: object,
    *,
    runtime_revision: object,
) -> dict[str, object]:
    if type(value) is not dict:
        raise CanonicalValueError("INVALID_MAPPING", "effectRecord")
    status = value.get("status")
    has_dynamic_effect = value.get("hasDynamicEffect")
    if status == "verified" and has_dynamic_effect is False:
        expected_keys = _STATIC_RECORD_KEYS
    elif status == "verified" and has_dynamic_effect is True:
        expected_keys = _DYNAMIC_RECORD_KEYS
    elif status == "unsupported" and has_dynamic_effect is True:
        expected_keys = _UNSUPPORTED_RECORD_KEYS
    else:
        raise CanonicalValueError(
            "INVALID_EFFECT_RECORD_STATUS", "effectRecord.status",
        )
    raw = canonical_mapping(
        value, path="effectRecord", exact_keys=expected_keys,
    )
    if raw["schemaRevision"] != EFFECT_RECORD_SCHEMA_REVISION:
        raise CanonicalValueError(
            "SCHEMA_REVISION_MISMATCH", "effectRecord.schemaRevision",
        )
    runtime = _canonical_runtime(
        runtime_revision, path="effectRecord.runtimeRevision",
    )
    payload_runtime = _canonical_runtime(
        raw["simcRuntimeRevision"], path="effectRecord.simcRuntimeRevision",
    )
    if payload_runtime != runtime:
        raise CanonicalValueError(
            "EFFECT_RUNTIME_MISMATCH", "effectRecord.simcRuntimeRevision",
        )
    kind = _canonical_subject_kind(
        raw["subjectKind"], path="effectRecord.subjectKind",
    )
    subject_key = canonical_identity_token(
        raw["subjectKey"], path="effectRecord.subjectKey",
    )
    variant_signature = _canonical_variant_signature(
        raw["subjectVariantSignature"],
        path="effectRecord.subjectVariantSignature",
    )
    verified_at = _canonical_timestamp(
        raw["verifiedAt"], path="effectRecord.verifiedAt",
    )
    rebuilt: dict[str, object] = {
        "schemaRevision": EFFECT_RECORD_SCHEMA_REVISION,
        "status": status,
        "subjectKind": kind,
        "subjectKey": subject_key,
        "subjectVariantSignature": variant_signature,
        "hasDynamicEffect": has_dynamic_effect,
        "simcRuntimeRevision": payload_runtime,
        "verifiedAt": verified_at,
    }
    if status == "verified" and has_dynamic_effect is True:
        effect_type = canonical_identity_token(
            raw["effectType"], path="effectRecord.effectType",
        )
        if effect_type not in _EFFECT_TYPES:
            raise CanonicalValueError(
                "INVALID_EFFECT_TYPE", "effectRecord.effectType",
            )
        experiment_key = _canonical_snapshot_key(
            raw["experimentSnapshotKey"],
            path="effectRecord.experimentSnapshotKey",
        )
        control_key = _canonical_snapshot_key(
            raw["controlSnapshotKey"],
            path="effectRecord.controlSnapshotKey",
        )
        if experiment_key == control_key:
            raise CanonicalValueError(
                "SNAPSHOT_CONTROL_NOT_DISTINCT",
                "effectRecord.controlSnapshotKey",
            )
        rebuilt.update({
            "effectType": effect_type,
            "expectedActionTokens": _canonical_effect_tokens(
                raw["expectedActionTokens"],
                path="effectRecord.expectedActionTokens",
            ),
            "expectedBuffTokens": _canonical_effect_tokens(
                raw["expectedBuffTokens"],
                path="effectRecord.expectedBuffTokens",
            ),
            "experimentSnapshotKey": experiment_key,
            "controlSnapshotKey": control_key,
        })
    elif status == "unsupported":
        rebuilt["unsupportedReason"] = canonical_identity_token(
            raw["unsupportedReason"],
            path="effectRecord.unsupportedReason",
        )
    if dict(raw) != rebuilt:
        raise CanonicalValueError(
            "EFFECT_RECORD_PAYLOAD_MISMATCH", "effectRecord",
        )
    return rebuilt


def seal_effect_record(
    record_payload: object,
    *,
    runtime_revision: str,
) -> CanonicalResult:
    """Seal one strict static, dynamic, or unsupported effect record."""

    try:
        payload = _validate_effect_record_payload(
            record_payload, runtime_revision=runtime_revision,
        )
        document = seal_canonical_document(
            document_kind=EFFECT_RECORD_DOCUMENT_KIND,
            schema_revision=EFFECT_RECORD_SCHEMA_REVISION,
            payload=payload,
            key_prefix=EFFECT_RECORD_KEY_PREFIX,
        )
        return CanonicalResult("verified", document, ())
    except CanonicalValueError as error:
        return _blocked(error)


def verify_effect_record(
    document: object,
    *,
    runtime_revision: object,
) -> bool:
    """Reload one record with explicit kind/schema/prefix/runtime binding."""

    return verify_sealed_document(
        document,
        document_kind=EFFECT_RECORD_DOCUMENT_KIND,
        schema_revision=EFFECT_RECORD_SCHEMA_REVISION,
        key_prefix=EFFECT_RECORD_KEY_PREFIX,
        payload_validator=lambda payload: _validate_effect_record_payload(
            payload, runtime_revision=runtime_revision,
        ),
    )


def reload_effect_record(
    canonical_bytes: bytes,
    content_key: str,
    *,
    runtime_revision: str,
) -> SealedCanonicalDocument:
    """Reload one runtime-bound effect record from exact persisted bytes."""

    return _rehydrate_canonical_document(
        canonical_bytes=canonical_bytes,
        content_key=content_key,
        document_kind=EFFECT_RECORD_DOCUMENT_KIND,
        schema_revision=EFFECT_RECORD_SCHEMA_REVISION,
        key_prefix=EFFECT_RECORD_KEY_PREFIX,
        payload_validator=lambda payload: _validate_effect_record_payload(
            payload,
            runtime_revision=runtime_revision,
        ),
    )


def _verified_effect_record_payload_copy(
    document: SealedCanonicalDocument,
    *,
    runtime_revision: object,
) -> dict[str, object]:
    return verified_payload_copy(
        document,
        document_kind=EFFECT_RECORD_DOCUMENT_KIND,
        schema_revision=EFFECT_RECORD_SCHEMA_REVISION,
        key_prefix=EFFECT_RECORD_KEY_PREFIX,
        payload_validator=lambda payload: _validate_effect_record_payload(
            payload, runtime_revision=runtime_revision,
        ),
    )


def derive_exact_effect_subjects(
    exact: SealedCanonicalDocument,
) -> tuple[EffectSubject, ...]:
    """Derive the deterministic required subjects from one reverified Exact."""

    payload = verified_payload_copy(
        exact,
        document_kind=EXACT_ITEM_DOCUMENT_KIND,
        schema_revision=EXACT_ITEM_IDENTITY_SCHEMA_REVISION,
        key_prefix=EXACT_ITEM_KEY_PREFIX,
        payload_validator=_validate_exact_item_payload,
    )
    item_variant_payload = {
        "itemId": payload["itemId"],
        "bonusIds": list(payload["bonusIds"]),
        "context": payload["context"],
        "itemLevel": payload["itemLevel"],
        "redirectedBaseStats": list(payload["redirectedBaseStats"]),
    }
    subjects = [EffectSubject(
        "item",
        payload["itemId"],
        seal_canonical_document(
            document_kind="effect_subject_signature",
            schema_revision="effect-subject-signature-v1",
            payload=item_variant_payload,
            key_prefix="exact-variant:sha256:",
        ).content_key,
    )]
    gem_bonus_ids = payload["gemBonusIds"]
    gem_item_levels = payload["gemItemLevels"]
    for index, gem_id in enumerate(payload["gemIds"]):
        gem_payload = {
            "id": gem_id,
            "bonusIds": [gem_bonus_ids[index]] if gem_bonus_ids else [],
            "itemLevel": gem_item_levels[index] if gem_item_levels else None,
        }
        subjects.append(EffectSubject(
            "gem",
            gem_id,
            seal_canonical_document(
                document_kind="effect_subject_signature",
                schema_revision="effect-subject-signature-v1",
                payload=gem_payload,
                key_prefix="gem-variant:sha256:",
            ).content_key,
        ))
    if payload["enchantId"]:
        subjects.append(EffectSubject(
            "enchant",
            payload["enchantId"],
            seal_canonical_document(
                document_kind="effect_subject_signature",
                schema_revision="effect-subject-signature-v1",
                payload={"id": payload["enchantId"]},
                key_prefix="enchant-variant:sha256:",
            ).content_key,
        ))
    for kind, field, prefix in (
        ("embellishment", "embellishmentIds", "embellishment-variant:sha256:"),
        ("crafted_effect", "craftedStats", "crafted_effect-variant:sha256:"),
    ):
        for key in payload[field]:
            subjects.append(EffectSubject(
                kind,
                key,
                seal_canonical_document(
                    document_kind="effect_subject_signature",
                    schema_revision="effect-subject-signature-v1",
                    payload={"id": key},
                    key_prefix=prefix,
                ).content_key,
            ))
    return tuple(subjects)


def _subject_identity(subject: EffectSubject) -> tuple[str, str, str]:
    return subject.kind, subject.key, subject.variant_signature


def _record_subject_identity(payload: Mapping[str, object]) -> tuple[object, object, object]:
    return (
        payload["subjectKind"],
        payload["subjectKey"],
        payload["subjectVariantSignature"],
    )


def _validate_effect_aggregate_payload(
    value: object,
    *,
    exact: SealedCanonicalDocument,
    runtime_revision: object,
) -> dict[str, object]:
    expected_subjects = derive_exact_effect_subjects(exact)
    raw = canonical_mapping(
        value, path="effectAggregate", exact_keys=_AGGREGATE_KEYS,
    )
    if raw["schemaRevision"] != EFFECT_SUPPORT_SCHEMA_REVISION:
        raise CanonicalValueError(
            "SCHEMA_REVISION_MISMATCH", "effectAggregate.schemaRevision",
        )
    status = canonical_identity_token(
        raw["status"], path="effectAggregate.status",
    )
    if status not in {"verified", "unsupported"}:
        raise CanonicalValueError(
            "INVALID_EFFECT_AGGREGATE_STATUS", "effectAggregate.status",
        )
    exact_key = canonical_identity_token(
        raw["exactItemInstanceKey"],
        path="effectAggregate.exactItemInstanceKey",
    )
    if _EXACT_KEY_PATTERN.fullmatch(exact_key) is None:
        raise CanonicalValueError(
            "INVALID_EXACT_ITEM_KEY", "effectAggregate.exactItemInstanceKey",
        )
    if exact_key != exact.content_key:
        raise CanonicalValueError(
            "EXACT_ITEM_BINDING_MISMATCH",
            "effectAggregate.exactItemInstanceKey",
        )
    runtime = _canonical_runtime(
        raw["simcRuntimeRevision"],
        path="effectAggregate.simcRuntimeRevision",
    )
    expected_runtime = _canonical_runtime(
        runtime_revision, path="effectAggregate.expectedRuntimeRevision",
    )
    if runtime != expected_runtime:
        raise CanonicalValueError(
            "EFFECT_RUNTIME_MISMATCH",
            "effectAggregate.simcRuntimeRevision",
        )
    subject_values = canonical_ordered_list(
        raw["subjects"],
        path="effectAggregate.subjects",
        item_rule=lambda subject, path: canonical_mapping(
            subject, path=path, exact_keys=_AGGREGATE_SUBJECT_KEYS,
        ),
        max_items=128,
    )
    record_values = canonical_ordered_list(
        raw["supportRecords"],
        path="effectAggregate.supportRecords",
        item_rule=lambda record, path: canonical_mapping(
            record,
            path=path,
            exact_keys=frozenset(record).union({"supportRecordKey"})
            if type(record) is dict
            else frozenset(),
        ),
        max_items=128,
    )
    if (
        not subject_values
        or len(subject_values) != len(record_values)
        or len(subject_values) != len(expected_subjects)
    ):
        raise CanonicalValueError(
            "EFFECT_AGGREGATE_SEQUENCE_MISMATCH", "effectAggregate",
        )
    rebuilt_subjects: list[dict[str, object]] = []
    rebuilt_records: list[dict[str, object]] = []
    has_unsupported = False
    for index, (expected_subject, subject, record_with_key) in enumerate(
        zip(expected_subjects, subject_values, record_values, strict=True)
    ):
        record = dict(record_with_key)
        support_key = canonical_identity_token(
            record.pop("supportRecordKey", None),
            path=f"effectAggregate.supportRecords[{index}].supportRecordKey",
        )
        if _RECORD_KEY_PATTERN.fullmatch(support_key) is None:
            raise CanonicalValueError(
                "INVALID_EFFECT_RECORD_KEY",
                f"effectAggregate.supportRecords[{index}].supportRecordKey",
            )
        canonical_record = _validate_effect_record_payload(
            record, runtime_revision=runtime,
        )
        rebuilt_document = seal_canonical_document(
            document_kind=EFFECT_RECORD_DOCUMENT_KIND,
            schema_revision=EFFECT_RECORD_SCHEMA_REVISION,
            payload=canonical_record,
            key_prefix=EFFECT_RECORD_KEY_PREFIX,
        )
        if rebuilt_document.content_key != support_key:
            raise CanonicalValueError(
                "EFFECT_RECORD_KEY_MISMATCH",
                f"effectAggregate.supportRecords[{index}].supportRecordKey",
            )
        subject_kind = _canonical_subject_kind(
            subject["subjectKind"],
            path=f"effectAggregate.subjects[{index}].subjectKind",
        )
        subject_key = canonical_identity_token(
            subject["subjectKey"],
            path=f"effectAggregate.subjects[{index}].subjectKey",
        )
        subject_signature = _canonical_variant_signature(
            subject["subjectVariantSignature"],
            path=f"effectAggregate.subjects[{index}].subjectVariantSignature",
        )
        subject_status = canonical_identity_token(
            subject["status"],
            path=f"effectAggregate.subjects[{index}].status",
        )
        subject_record_key = canonical_identity_token(
            subject["supportRecordKey"],
            path=f"effectAggregate.subjects[{index}].supportRecordKey",
        )
        if (
            (subject_kind, subject_key, subject_signature)
            != _record_subject_identity(canonical_record)
            or (subject_kind, subject_key, subject_signature)
            != _subject_identity(expected_subject)
            or subject_status != canonical_record["status"]
            or subject_record_key != support_key
        ):
            raise CanonicalValueError(
                "EFFECT_AGGREGATE_RECORD_MISMATCH",
                f"effectAggregate.subjects[{index}]",
            )
        has_unsupported = has_unsupported or subject_status == "unsupported"
        rebuilt_subjects.append({
            "subjectKind": subject_kind,
            "subjectKey": subject_key,
            "subjectVariantSignature": subject_signature,
            "status": subject_status,
            "supportRecordKey": support_key,
        })
        rebuilt_records.append({**canonical_record, "supportRecordKey": support_key})
    expected_status = "unsupported" if has_unsupported else "verified"
    if status != expected_status:
        raise CanonicalValueError(
            "EFFECT_AGGREGATE_STATUS_MISMATCH", "effectAggregate.status",
        )
    rebuilt = {
        "schemaRevision": EFFECT_SUPPORT_SCHEMA_REVISION,
        "status": status,
        "exactItemInstanceKey": exact_key,
        "simcRuntimeRevision": runtime,
        "subjects": rebuilt_subjects,
        "supportRecords": rebuilt_records,
    }
    if dict(raw) != rebuilt:
        raise CanonicalValueError(
            "EFFECT_AGGREGATE_PAYLOAD_MISMATCH", "effectAggregate",
        )
    return rebuilt


def reload_effect_aggregate(
    canonical_bytes: bytes,
    content_key: str,
    *,
    exact: SealedCanonicalDocument,
    runtime_revision: str,
    records: tuple[SealedCanonicalDocument, ...],
) -> SealedCanonicalDocument:
    """Reload an Exact/runtime-bound aggregate with exact ordered records."""

    if type(records) is not tuple:
        raise CanonicalValueError(
            "INVALID_EFFECT_RECORD_SEQUENCE", "effectAggregate.records",
        )
    verified_record_list: list[SealedCanonicalDocument] = []
    for index, record in enumerate(records):
        if type(record) is not SealedCanonicalDocument:
            raise CanonicalValueError(
                "INVALID_EFFECT_RECORD",
                f"effectAggregate.records[{index}]",
            )
        verified_record_list.append(reload_effect_record(
            record.canonical_bytes,
            record.content_key,
            runtime_revision=runtime_revision,
        ))
    verified_records = tuple(verified_record_list)

    def validate(value: object) -> object:
        payload = _validate_effect_aggregate_payload(
            value,
            exact=exact,
            runtime_revision=runtime_revision,
        )
        stored_keys = tuple(
            entry["supportRecordKey"] for entry in payload["supportRecords"]
        )
        expected_keys = tuple(record.content_key for record in verified_records)
        if stored_keys != expected_keys:
            raise CanonicalValueError(
                "EFFECT_AGGREGATE_RECORD_SEQUENCE_MISMATCH",
                "effectAggregate.supportRecords",
            )
        return payload

    return _rehydrate_canonical_document(
        canonical_bytes=canonical_bytes,
        content_key=content_key,
        document_kind=EFFECT_AGGREGATE_DOCUMENT_KIND,
        schema_revision=EFFECT_SUPPORT_SCHEMA_REVISION,
        key_prefix=EFFECT_AGGREGATE_KEY_PREFIX,
        payload_validator=validate,
    )


def resolve_exact_effect_support(
    exact: SealedCanonicalDocument,
    *,
    runtime_revision: object,
    records: Sequence[SealedCanonicalDocument],
) -> EffectSupportOutcome:
    """Resolve one Exact item from sealed, runtime-bound effect records only."""

    try:
        subjects = derive_exact_effect_subjects(exact)
        runtime = _canonical_runtime(
            runtime_revision, path="effectSupport.runtimeRevision",
        )
    except CanonicalValueError as error:
        return _unknown(
            error.code,
            error.path,
            "Re-import the Exact item and select one canonical runtime.",
        )
    if not isinstance(records, Sequence) or isinstance(
        records, (str, bytes, bytearray)
    ):
        return _unknown(
            "INVALID_EFFECT_RECORD_SEQUENCE",
            "effectSupport.records",
            "Supply a list or tuple of sealed effect records.",
        )
    expected_identities = [_subject_identity(subject) for subject in subjects]
    matched_records: list[
        tuple[SealedCanonicalDocument, dict[str, object]]
    ] = []
    for index, document in enumerate(records):
        if not verify_effect_record(document, runtime_revision=runtime):
            return _unknown(
                "INVALID_EFFECT_RECORD",
                f"effectSupport.records[{index}]",
                "Regenerate the record from the current governed runtime.",
            )
        try:
            payload = _verified_effect_record_payload_copy(
                document, runtime_revision=runtime,
            )
        except CanonicalValueError:
            return _unknown(
                "INVALID_EFFECT_RECORD",
                f"effectSupport.records[{index}]",
                "Regenerate the record from the current governed runtime.",
            )
        identity = _record_subject_identity(payload)
        if index >= len(expected_identities):
            code = (
                "DUPLICATE_EFFECT_RECORD"
                if identity in expected_identities
                else "UNEXPECTED_EFFECT_RECORD"
            )
            return _unknown(
                code,
                f"effectSupport.records[{index}]",
                "Supply exactly one record for each Exact-derived subject position.",
            )
        if identity == expected_identities[index]:
            matched_records.append((document, payload))
            continue
        if identity not in expected_identities:
            return _unknown(
                "UNEXPECTED_EFFECT_RECORD",
                f"effectSupport.records[{index}]",
                "Supply records only for subjects derived from this Exact item.",
            )
        if identity in expected_identities[index + 1:]:
            return _unknown(
                "NON_CANONICAL_EFFECT_RECORD_ORDER",
                f"effectSupport.records[{index}]",
                "Supply records in the Exact-derived subject order.",
            )
        return _unknown(
            "DUPLICATE_EFFECT_RECORD",
            f"effectSupport.records[{index}]",
            "Supply exactly one record for each Exact-derived subject position.",
        )
    if len(matched_records) < len(subjects):
        missing = subjects[len(matched_records)]
        return _unknown(
            "EFFECT_RECORD_MISSING",
            f"effectSupport.subjects.{missing.kind}",
            "Run the governed effect probe for every required subject.",
        )
    aggregate_subjects = []
    aggregate_records = []
    has_unsupported = False
    for subject, (document, payload) in zip(
        subjects, matched_records, strict=True,
    ):
        has_unsupported = has_unsupported or payload["status"] == "unsupported"
        aggregate_subjects.append({
            "subjectKind": subject.kind,
            "subjectKey": subject.key,
            "subjectVariantSignature": subject.variant_signature,
            "status": payload["status"],
            "supportRecordKey": document.content_key,
        })
        aggregate_records.append({
            **payload,
            "supportRecordKey": document.content_key,
        })
    aggregate_status = "unsupported" if has_unsupported else "verified"
    aggregate_payload = {
        "schemaRevision": EFFECT_SUPPORT_SCHEMA_REVISION,
        "status": aggregate_status,
        "exactItemInstanceKey": exact.content_key,
        "simcRuntimeRevision": runtime,
        "subjects": aggregate_subjects,
        "supportRecords": aggregate_records,
    }
    try:
        _validate_effect_aggregate_payload(
            aggregate_payload,
            exact=exact,
            runtime_revision=runtime,
        )
        document = seal_canonical_document(
            document_kind=EFFECT_AGGREGATE_DOCUMENT_KIND,
            schema_revision=EFFECT_SUPPORT_SCHEMA_REVISION,
            payload=aggregate_payload,
            key_prefix=EFFECT_AGGREGATE_KEY_PREFIX,
        )
    except CanonicalValueError as error:
        return _unknown(
            error.code,
            error.path,
            "Regenerate all effect records from the sealed Exact item.",
        )
    if aggregate_status == "unsupported":
        return EffectSupportOutcome(
            "unsupported",
            document,
            (_issue(
                "EFFECT_SUBJECT_UNSUPPORTED",
                "effectSupport.subjects",
                "Choose an Exact item supported by the current SimC runtime.",
            ),),
        )
    return EffectSupportOutcome("verified", document, ())


__all__ = (
    "EFFECT_AGGREGATE_DOCUMENT_KIND",
    "EFFECT_AGGREGATE_KEY_PREFIX",
    "EFFECT_RECORD_DOCUMENT_KIND",
    "EFFECT_RECORD_KEY_PREFIX",
    "EFFECT_RECORD_SCHEMA_REVISION",
    "EFFECT_SUBJECT_KINDS",
    "EFFECT_SUPPORT_SCHEMA_REVISION",
    "EffectSubject",
    "EffectSupportOutcome",
    "derive_exact_effect_subjects",
    "resolve_exact_effect_support",
    "reload_effect_aggregate",
    "reload_effect_record",
    "seal_effect_record",
    "verify_effect_record",
)
