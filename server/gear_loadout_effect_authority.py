#!/usr/bin/env python3
"""Canonical loadout-scoped SimC effect authority for Resolver v2 subjects."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
import re
from typing import Any, Literal

try:
    from .gear_canonical_kernel import (
        CanonicalIssue,
        CanonicalValueError,
        SealedCanonicalDocument,
        _rehydrate_canonical_document,
        canonical_identity_token,
        canonical_int,
        canonical_json_bytes,
        canonical_mapping,
        canonical_ordered_list,
        seal_canonical_document,
        verify_sealed_document,
    )
    from .simc_item_effect_support import reload_effect_record
except ImportError:
    from gear_canonical_kernel import (
        CanonicalIssue,
        CanonicalValueError,
        SealedCanonicalDocument,
        _rehydrate_canonical_document,
        canonical_identity_token,
        canonical_int,
        canonical_json_bytes,
        canonical_mapping,
        canonical_ordered_list,
        seal_canonical_document,
        verify_sealed_document,
    )
    from simc_item_effect_support import reload_effect_record


LOADOUT_EFFECT_AUTHORITY_SCHEMA_REVISION = "loadout-effect-authority-v1"
LOADOUT_EFFECT_AUTHORITY_DOCUMENT_KIND = "loadout_effect_authority"
LOADOUT_EFFECT_AUTHORITY_KEY_PREFIX = "loadout-effect-authority:sha256:"
LOADOUT_EFFECT_SUBJECT_SCHEMA_REVISION = "loadout-effect-subject-signature-v1"
LOADOUT_EFFECT_SUBJECT_DOCUMENT_KIND = "loadout_effect_subject_signature"
LOADOUT_EFFECT_SUBJECT_KEY_PREFIX = "set_bonus-variant:sha256:"
_RESOLVER_EFFECT_BOUNDARY_SCHEMA_REVISION = "gear-resolver-v2-effect-boundary-v1"
_MAX_SUBJECTS = 128
_AGGREGATE_KEYS = frozenset({
    "schemaRevision", "status", "resolvedGearSignature", "gearRuleRevision",
    "resolverRevision", "simcRuntimeRevision", "subjects", "supportRecords",
})
_SUBJECT_KEYS = frozenset({
    "subjectKind", "subjectKey", "subjectVariantSignature", "status",
    "supportRecordKey",
})
_DESCRIPTOR_KEYS = frozenset({
    "subjectKind", "itemSetId", "pieces", "subjectKey",
})
_BOUNDARY_KEYS = frozenset({
    "schemaRevision", "status", "resolvedGearSignature", "setState",
    "subjects", "gearRuleRevision", "resolverRevision", "simcRuntimeRevision",
})
_RECORD_KEY_PATTERN = re.compile(r"^simc-item-effect-record:sha256:[0-9a-f]{64}$")
_SIGNATURE_PATTERN = re.compile(r"^set_bonus-variant:sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class LoadoutEffectAuthorityOutcome:
    status: Literal["verified", "unsupported", "unknown"]
    document: SealedCanonicalDocument | None
    issues: tuple[CanonicalIssue, ...]

    def __post_init__(self) -> None:
        if self.status == "verified":
            if (
                type(self.document) is not SealedCanonicalDocument
                or type(self.issues) is not tuple
                or self.issues
            ):
                raise ValueError("Verified loadout effect authority requires one sealed document.")
            return
        if self.status == "unsupported":
            if (
                type(self.document) is not SealedCanonicalDocument
                or type(self.issues) is not tuple
                or not self.issues
            ):
                raise ValueError("Unsupported loadout effect authority requires sealed evidence and issues.")
            return
        if self.status == "unknown":
            if self.document is not None or type(self.issues) is not tuple or not self.issues:
                raise ValueError("Unknown loadout effect authority requires issues and no document.")
            return
        raise ValueError("Loadout effect authority status is invalid.")


@dataclass(frozen=True)
class _ResolverContext:
    resolved_gear_signature: str
    gear_rule_revision: str
    resolver_revision: str
    simc_runtime_revision: str
    descriptors: tuple[dict[str, object], ...]


def _issue(code: str, path: str, recovery_action: str) -> CanonicalIssue:
    return CanonicalIssue(code, path, recovery_action)


def _unknown(error: CanonicalValueError) -> LoadoutEffectAuthorityOutcome:
    return LoadoutEffectAuthorityOutcome(
        "unknown",
        None,
        (_issue(
            error.code,
            error.path,
            "Recreate the loadout effect authority from the current Resolver v2 snapshot.",
        ),),
    )


def _descriptor(value: object, *, path: str) -> dict[str, object]:
    raw = canonical_mapping(value, path=path, exact_keys=_DESCRIPTOR_KEYS)
    kind = canonical_identity_token(raw["subjectKind"], path=f"{path}.subjectKind")
    if kind != "set_bonus":
        raise CanonicalValueError("UNMODELLED_LOADOUT_EFFECT_SUBJECT", f"{path}.subjectKind")
    return {
        "subjectKind": kind,
        "itemSetId": canonical_identity_token(raw["itemSetId"], path=f"{path}.itemSetId"),
        "pieces": canonical_int(
            raw["pieces"], path=f"{path}.pieces", minimum=1, maximum=16,
        ),
        "subjectKey": canonical_identity_token(raw["subjectKey"], path=f"{path}.subjectKey"),
    }


def _active_effect_descriptors(value: object) -> tuple[dict[str, object], ...]:
    if type(value) is not list:
        raise CanonicalValueError("INVALID_ORDERED_LIST", "resolverSnapshot.setState.activeDynamicEffects")
    descriptors: list[dict[str, object]] = []
    for index, effect in enumerate(value):
        if not isinstance(effect, Mapping):
            raise CanonicalValueError(
                "INVALID_MAPPING", f"resolverSnapshot.setState.activeDynamicEffects[{index}]",
            )
        if effect.get("subjectKind", "set_bonus") != "set_bonus":
            raise CanonicalValueError(
                "UNMODELLED_LOADOUT_EFFECT_SUBJECT",
                f"resolverSnapshot.setState.activeDynamicEffects[{index}].subjectKind",
            )
        descriptors.append({
            "subjectKind": "set_bonus",
            "itemSetId": canonical_identity_token(
                effect.get("itemSetId"),
                path=f"resolverSnapshot.setState.activeDynamicEffects[{index}].itemSetId",
            ),
            "pieces": canonical_int(
                effect.get("pieces"),
                path=f"resolverSnapshot.setState.activeDynamicEffects[{index}].pieces",
                minimum=1,
                maximum=16,
            ),
            "subjectKey": canonical_identity_token(
                effect.get("effectId"),
                path=f"resolverSnapshot.setState.activeDynamicEffects[{index}].effectId",
            ),
        })
    return tuple(sorted(
        descriptors,
        key=lambda descriptor: (
            descriptor["subjectKind"], descriptor["itemSetId"],
            descriptor["pieces"], descriptor["subjectKey"],
        ),
    ))


def _resolver_context(resolver_snapshot: object) -> _ResolverContext:
    if type(resolver_snapshot) is not dict:
        raise CanonicalValueError("INVALID_MAPPING", "resolverSnapshot")
    boundary = canonical_mapping(
        resolver_snapshot.get("v2EffectBoundary"),
        path="resolverSnapshot.v2EffectBoundary",
        exact_keys=_BOUNDARY_KEYS,
    )
    if boundary["schemaRevision"] != _RESOLVER_EFFECT_BOUNDARY_SCHEMA_REVISION:
        raise CanonicalValueError(
            "SCHEMA_REVISION_MISMATCH", "resolverSnapshot.v2EffectBoundary.schemaRevision",
        )
    if boundary["status"] != "blocked" or resolver_snapshot.get("status") != "blocked":
        raise CanonicalValueError("INVALID_RESOLVER_EFFECT_BOUNDARY", "resolverSnapshot.v2EffectBoundary.status")
    dependency = resolver_snapshot.get("dependencyVector")
    if not isinstance(dependency, Mapping):
        raise CanonicalValueError("INVALID_MAPPING", "resolverSnapshot.dependencyVector")
    resolved_signature = canonical_identity_token(
        resolver_snapshot.get("resolvedGearSignature"),
        path="resolverSnapshot.resolvedGearSignature",
    )
    revisions = {
        "gear_rule_revision": canonical_identity_token(
            boundary["gearRuleRevision"],
            path="resolverSnapshot.v2EffectBoundary.gearRuleRevision",
        ),
        "resolver_revision": canonical_identity_token(
            boundary["resolverRevision"],
            path="resolverSnapshot.v2EffectBoundary.resolverRevision",
        ),
        "simc_runtime_revision": canonical_identity_token(
            boundary["simcRuntimeRevision"],
            path="resolverSnapshot.v2EffectBoundary.simcRuntimeRevision",
        ),
    }
    if (
        boundary["resolvedGearSignature"] != resolved_signature
        or dependency.get("gearRuleRevision") != revisions["gear_rule_revision"]
        or dependency.get("resolverContractRevision") != revisions["resolver_revision"]
        or dependency.get("simcRuntimeRevision") != revisions["simc_runtime_revision"]
    ):
        raise CanonicalValueError("RESOLVER_CONTEXT_MISMATCH", "resolverSnapshot")
    descriptors = canonical_ordered_list(
        resolver_snapshot.get("loadoutEffectSubjects"),
        path="resolverSnapshot.loadoutEffectSubjects",
        item_rule=lambda item, path: _descriptor(item, path=path),
        max_items=_MAX_SUBJECTS,
    )
    if not descriptors:
        raise CanonicalValueError("LOADOUT_EFFECT_SUBJECTS_REQUIRED", "resolverSnapshot.loadoutEffectSubjects")
    boundary_descriptors = canonical_ordered_list(
        boundary["subjects"],
        path="resolverSnapshot.v2EffectBoundary.subjects",
        item_rule=lambda item, path: _descriptor(item, path=path),
        max_items=_MAX_SUBJECTS,
    )
    set_state = resolver_snapshot.get("setState")
    if not isinstance(set_state, Mapping) or boundary["setState"] != set_state:
        raise CanonicalValueError("RESOLVER_CONTEXT_MISMATCH", "resolverSnapshot.setState")
    active_descriptors = _active_effect_descriptors(set_state.get("activeDynamicEffects"))
    ordered = tuple(sorted(
        descriptors,
        key=lambda descriptor: (
            descriptor["subjectKind"], descriptor["itemSetId"],
            descriptor["pieces"], descriptor["subjectKey"],
        ),
    ))
    if descriptors != ordered or boundary_descriptors != descriptors or active_descriptors != descriptors:
        raise CanonicalValueError("LOADOUT_EFFECT_DESCRIPTOR_SEQUENCE_MISMATCH", "resolverSnapshot")
    return _ResolverContext(
        resolved_signature,
        revisions["gear_rule_revision"],
        revisions["resolver_revision"],
        revisions["simc_runtime_revision"],
        descriptors,
    )


def _signature_for(context: _ResolverContext, descriptor: Mapping[str, object]) -> str:
    return seal_canonical_document(
        document_kind=LOADOUT_EFFECT_SUBJECT_DOCUMENT_KIND,
        schema_revision=LOADOUT_EFFECT_SUBJECT_SCHEMA_REVISION,
        key_prefix=LOADOUT_EFFECT_SUBJECT_KEY_PREFIX,
        payload={
            "schemaRevision": LOADOUT_EFFECT_SUBJECT_SCHEMA_REVISION,
            "subjectKind": descriptor["subjectKind"],
            "subjectKey": descriptor["subjectKey"],
            "itemSetId": descriptor["itemSetId"],
            "pieces": descriptor["pieces"],
            "resolvedGearSignature": context.resolved_gear_signature,
            "gearRuleRevision": context.gear_rule_revision,
            "resolverRevision": context.resolver_revision,
            "simcRuntimeRevision": context.simc_runtime_revision,
        },
    ).content_key


def _rehydrated_record_payload(
    record: object,
    *,
    runtime_revision: str,
    path: str,
) -> tuple[SealedCanonicalDocument, dict[str, object]]:
    if type(record) is not SealedCanonicalDocument:
        raise CanonicalValueError("INVALID_EFFECT_RECORD", path)
    reloaded = reload_effect_record(
        record.canonical_bytes,
        record.content_key,
        runtime_revision=runtime_revision,
    )
    return reloaded, json.loads(reloaded.canonical_bytes)


def _raw_support_record(value: object, path: str) -> dict[str, object]:
    if type(value) is not dict:
        raise CanonicalValueError("INVALID_MAPPING", path)
    return value


def _validate_loadout_effect_authority_payload(
    value: object,
    *,
    resolver_snapshot: object,
) -> dict[str, object]:
    context = _resolver_context(resolver_snapshot)
    raw = canonical_mapping(
        value, path="loadoutEffectAuthority", exact_keys=_AGGREGATE_KEYS,
    )
    if raw["schemaRevision"] != LOADOUT_EFFECT_AUTHORITY_SCHEMA_REVISION:
        raise CanonicalValueError("SCHEMA_REVISION_MISMATCH", "loadoutEffectAuthority.schemaRevision")
    status = canonical_identity_token(raw["status"], path="loadoutEffectAuthority.status")
    if status not in {"verified", "unsupported"}:
        raise CanonicalValueError("INVALID_LOADOUT_EFFECT_AUTHORITY_STATUS", "loadoutEffectAuthority.status")
    identity_fields = (
        ("resolvedGearSignature", context.resolved_gear_signature),
        ("gearRuleRevision", context.gear_rule_revision),
        ("resolverRevision", context.resolver_revision),
        ("simcRuntimeRevision", context.simc_runtime_revision),
    )
    for field, expected in identity_fields:
        if canonical_identity_token(raw[field], path=f"loadoutEffectAuthority.{field}") != expected:
            raise CanonicalValueError("LOADOUT_EFFECT_CONTEXT_MISMATCH", f"loadoutEffectAuthority.{field}")
    subject_values = canonical_ordered_list(
        raw["subjects"],
        path="loadoutEffectAuthority.subjects",
        item_rule=lambda item, path: canonical_mapping(item, path=path, exact_keys=_SUBJECT_KEYS),
        max_items=_MAX_SUBJECTS,
    )
    record_values = canonical_ordered_list(
        raw["supportRecords"],
        path="loadoutEffectAuthority.supportRecords",
        item_rule=_raw_support_record,
        max_items=_MAX_SUBJECTS,
    )
    if not subject_values or len(subject_values) != len(record_values) or len(subject_values) != len(context.descriptors):
        raise CanonicalValueError("LOADOUT_EFFECT_SEQUENCE_MISMATCH", "loadoutEffectAuthority")
    rebuilt_subjects: list[dict[str, object]] = []
    rebuilt_records: list[dict[str, object]] = []
    has_unsupported = False
    for index, (descriptor, subject, record_with_key) in enumerate(zip(
        context.descriptors, subject_values, record_values, strict=True,
    )):
        subject_path = f"loadoutEffectAuthority.subjects[{index}]"
        record_path = f"loadoutEffectAuthority.supportRecords[{index}]"
        support_key = canonical_identity_token(
            record_with_key.get("supportRecordKey"), path=f"{record_path}.supportRecordKey",
        )
        if _RECORD_KEY_PATTERN.fullmatch(support_key) is None:
            raise CanonicalValueError("INVALID_EFFECT_RECORD_KEY", f"{record_path}.supportRecordKey")
        record_payload = dict(record_with_key)
        record_payload.pop("supportRecordKey", None)
        reloaded = reload_effect_record(
            canonical_json_bytes(record_payload),
            support_key,
            runtime_revision=context.simc_runtime_revision,
        )
        canonical_record = json.loads(reloaded.canonical_bytes)
        kind = canonical_identity_token(subject["subjectKind"], path=f"{subject_path}.subjectKind")
        subject_key = canonical_identity_token(subject["subjectKey"], path=f"{subject_path}.subjectKey")
        signature = canonical_identity_token(
            subject["subjectVariantSignature"], path=f"{subject_path}.subjectVariantSignature",
        )
        if _SIGNATURE_PATTERN.fullmatch(signature) is None:
            raise CanonicalValueError("INVALID_LOADOUT_EFFECT_SIGNATURE", f"{subject_path}.subjectVariantSignature")
        subject_status = canonical_identity_token(subject["status"], path=f"{subject_path}.status")
        subject_record_key = canonical_identity_token(subject["supportRecordKey"], path=f"{subject_path}.supportRecordKey")
        expected_signature = _signature_for(context, descriptor)
        if (
            kind != descriptor["subjectKind"]
            or subject_key != descriptor["subjectKey"]
            or signature != expected_signature
            or (kind, subject_key, signature) != (
                canonical_record["subjectKind"], canonical_record["subjectKey"],
                canonical_record["subjectVariantSignature"],
            )
            or subject_status != canonical_record["status"]
            or subject_record_key != support_key
        ):
            raise CanonicalValueError("LOADOUT_EFFECT_RECORD_MISMATCH", subject_path)
        has_unsupported = has_unsupported or subject_status == "unsupported"
        rebuilt_subjects.append({
            "subjectKind": kind,
            "subjectKey": subject_key,
            "subjectVariantSignature": signature,
            "status": subject_status,
            "supportRecordKey": support_key,
        })
        rebuilt_records.append({**canonical_record, "supportRecordKey": support_key})
    expected_status = "unsupported" if has_unsupported else "verified"
    if status != expected_status:
        raise CanonicalValueError("LOADOUT_EFFECT_STATUS_MISMATCH", "loadoutEffectAuthority.status")
    rebuilt = {
        "schemaRevision": LOADOUT_EFFECT_AUTHORITY_SCHEMA_REVISION,
        "status": status,
        "resolvedGearSignature": context.resolved_gear_signature,
        "gearRuleRevision": context.gear_rule_revision,
        "resolverRevision": context.resolver_revision,
        "simcRuntimeRevision": context.simc_runtime_revision,
        "subjects": rebuilt_subjects,
        "supportRecords": rebuilt_records,
    }
    if dict(raw) != rebuilt:
        raise CanonicalValueError("LOADOUT_EFFECT_PAYLOAD_MISMATCH", "loadoutEffectAuthority")
    return rebuilt


def loadout_effect_subject_signatures(resolver_snapshot: Any) -> tuple[str, ...]:
    """Return Task 4L's exact ordered signature witness for one Resolver snapshot."""

    context = _resolver_context(resolver_snapshot)
    return tuple(_signature_for(context, descriptor) for descriptor in context.descriptors)


def resolve_loadout_effect_authority(
    resolver_snapshot: Any,
    *,
    records: Sequence[SealedCanonicalDocument],
) -> LoadoutEffectAuthorityOutcome:
    """Resolve one complete ordered loadout effect aggregate from sealed records."""
    try:
        context = _resolver_context(resolver_snapshot)
        if not isinstance(records, Sequence) or isinstance(records, (str, bytes, bytearray)):
            raise CanonicalValueError("INVALID_EFFECT_RECORD_SEQUENCE", "loadoutEffectAuthority.records")
        if len(records) != len(context.descriptors):
            raise CanonicalValueError("LOADOUT_EFFECT_RECORD_SEQUENCE_MISMATCH", "loadoutEffectAuthority.records")
        subjects: list[dict[str, object]] = []
        support_records: list[dict[str, object]] = []
        has_unsupported = False
        for index, (descriptor, record) in enumerate(zip(context.descriptors, records, strict=True)):
            reloaded, payload = _rehydrated_record_payload(
                record,
                runtime_revision=context.simc_runtime_revision,
                path=f"loadoutEffectAuthority.records[{index}]",
            )
            signature = _signature_for(context, descriptor)
            if (
                payload["subjectKind"] != descriptor["subjectKind"]
                or payload["subjectKey"] != descriptor["subjectKey"]
                or payload["subjectVariantSignature"] != signature
            ):
                raise CanonicalValueError(
                    "LOADOUT_EFFECT_RECORD_MISMATCH",
                    f"loadoutEffectAuthority.records[{index}]",
                )
            has_unsupported = has_unsupported or payload["status"] == "unsupported"
            subjects.append({
                "subjectKind": descriptor["subjectKind"],
                "subjectKey": descriptor["subjectKey"],
                "subjectVariantSignature": signature,
                "status": payload["status"],
                "supportRecordKey": reloaded.content_key,
            })
            support_records.append({**payload, "supportRecordKey": reloaded.content_key})
        status = "unsupported" if has_unsupported else "verified"
        payload = {
            "schemaRevision": LOADOUT_EFFECT_AUTHORITY_SCHEMA_REVISION,
            "status": status,
            "resolvedGearSignature": context.resolved_gear_signature,
            "gearRuleRevision": context.gear_rule_revision,
            "resolverRevision": context.resolver_revision,
            "simcRuntimeRevision": context.simc_runtime_revision,
            "subjects": subjects,
            "supportRecords": support_records,
        }
        _validate_loadout_effect_authority_payload(
            payload, resolver_snapshot=resolver_snapshot,
        )
        document = seal_canonical_document(
            document_kind=LOADOUT_EFFECT_AUTHORITY_DOCUMENT_KIND,
            schema_revision=LOADOUT_EFFECT_AUTHORITY_SCHEMA_REVISION,
            payload=payload,
            key_prefix=LOADOUT_EFFECT_AUTHORITY_KEY_PREFIX,
        )
    except (CanonicalValueError, TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
        if isinstance(error, CanonicalValueError):
            return _unknown(error)
        return _unknown(CanonicalValueError("INVALID_LOADOUT_EFFECT_INPUT", "loadoutEffectAuthority"))
    if status == "unsupported":
        return LoadoutEffectAuthorityOutcome(
            "unsupported",
            document,
            (_issue(
                "LOADOUT_EFFECT_UNSUPPORTED",
                "loadoutEffectAuthority.subjects",
                "Choose a loadout with support in the governed SimC runtime.",
            ),),
        )
    return LoadoutEffectAuthorityOutcome("verified", document, ())


def reload_loadout_effect_authority(
    canonical_bytes: bytes,
    content_key: str,
    *,
    resolver_snapshot: Any,
) -> SealedCanonicalDocument:
    """Reload an aggregate while rehydrating every embedded effect record."""
    return _rehydrate_canonical_document(
        canonical_bytes=canonical_bytes,
        content_key=content_key,
        document_kind=LOADOUT_EFFECT_AUTHORITY_DOCUMENT_KIND,
        schema_revision=LOADOUT_EFFECT_AUTHORITY_SCHEMA_REVISION,
        key_prefix=LOADOUT_EFFECT_AUTHORITY_KEY_PREFIX,
        payload_validator=lambda payload: _validate_loadout_effect_authority_payload(
            payload, resolver_snapshot=resolver_snapshot,
        ),
    )


def verify_loadout_effect_authority(
    document: Any,
    *,
    resolver_snapshot: Any,
) -> bool:
    """Return whether one sealed aggregate rebinds to the current v2 snapshot."""
    return verify_sealed_document(
        document,
        document_kind=LOADOUT_EFFECT_AUTHORITY_DOCUMENT_KIND,
        schema_revision=LOADOUT_EFFECT_AUTHORITY_SCHEMA_REVISION,
        key_prefix=LOADOUT_EFFECT_AUTHORITY_KEY_PREFIX,
        payload_validator=lambda payload: _validate_loadout_effect_authority_payload(
            payload, resolver_snapshot=resolver_snapshot,
        ),
    )


__all__ = (
    "LoadoutEffectAuthorityOutcome",
    "loadout_effect_subject_signatures",
    "resolve_loadout_effect_authority",
    "reload_loadout_effect_authority",
    "verify_loadout_effect_authority",
)
