#!/usr/bin/env python3
"""Canonical Runtime Authority Release documents for Exact-first materialization.

This owner seals only already-proven server facts.  It neither discovers a
release nor reads mutable Catalog, Manifest, cache, or process state.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

try:
    from .gear_canonical_kernel import (
        CanonicalIssue,
        CanonicalResult,
        CanonicalValueError,
        SealedCanonicalDocument,
        _rehydrate_canonical_document,
        canonical_identity_token,
        canonical_json_bytes,
        canonical_mapping,
        seal_canonical_document,
        verified_payload_copy,
        verify_sealed_document,
    )
    from .gear_exact_import_job_store import DEPENDENCY_VECTOR_KEYS
    from .gear_loadout_effect_authority import loadout_effect_subject_signatures
    from .simc_item_effect_support import reload_effect_record
except ImportError:  # pragma: no cover - direct server runtime compatibility
    from gear_canonical_kernel import (
        CanonicalIssue,
        CanonicalResult,
        CanonicalValueError,
        SealedCanonicalDocument,
        _rehydrate_canonical_document,
        canonical_identity_token,
        canonical_json_bytes,
        canonical_mapping,
        seal_canonical_document,
        verified_payload_copy,
        verify_sealed_document,
    )
    from gear_exact_import_job_store import DEPENDENCY_VECTOR_KEYS
    from gear_loadout_effect_authority import loadout_effect_subject_signatures
    from simc_item_effect_support import reload_effect_record


RUNTIME_RESOLVER_CONTEXT_SCHEMA_REVISION = "exact-runtime-resolver-context-v1"
RUNTIME_AUTHORITY_RELEASE_SCHEMA_REVISION = "exact-runtime-authority-release-v1"
RUNTIME_OCCURRENCE_INDEX_ENTRY_SCHEMA_REVISION = (
    "exact-runtime-occurrence-index-entry-v1"
)
RUNTIME_RESOLVER_CONTEXT_DOCUMENT_KIND = "exact_runtime_resolver_context"
RUNTIME_AUTHORITY_RELEASE_DOCUMENT_KIND = "exact_runtime_authority_release"
RUNTIME_OCCURRENCE_INDEX_ENTRY_DOCUMENT_KIND = "exact_runtime_occurrence_index_entry"
RUNTIME_RESOLVER_CONTEXT_KEY_PREFIX = "exact-runtime-resolver-context:sha256:"
RUNTIME_AUTHORITY_RELEASE_KEY_PREFIX = "exact-runtime-authority-release:sha256:"
RUNTIME_OCCURRENCE_INDEX_ENTRY_KEY_PREFIX = (
    "exact-runtime-occurrence-index-entry:sha256:"
)

_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_CONTEXT_KEY = re.compile(r"^exact-runtime-resolver-context:sha256:[0-9a-f]{64}$")
_RELEASE_KEY = re.compile(r"^exact-runtime-authority-release:sha256:[0-9a-f]{64}$")
_EFFECT_RECORD_KEY = re.compile(r"^simc-item-effect-record:sha256:[0-9a-f]{64}$")
_SUBJECT_SIGNATURE = re.compile(r"^[a-z_]+-variant:sha256:[0-9a-f]{64}$")
_RESOLVED_GEAR_SIGNATURE = re.compile(r"^sha256:[0-9a-f]{64}$")
_CONTEXT_KEYS = frozenset({
    "schemaRevision",
    "producerIdentity",
    "producerRevision",
    "seasonRevision",
    "gearRuleRevision",
    "resolverRevision",
    "simcRuntimeRevision",
    "resolverAuthorityContext",
})
_RELEASE_KEYS = frozenset({
    "schemaRevision",
    "producerIdentity",
    "producerRevision",
    "resolverContextKey",
    "resolverContextSha256",
    "dependencyVector",
})
_INDEX_ENTRY_KEYS = frozenset({
    "schemaRevision",
    "producerIdentity",
    "producerRevision",
    "runtimeAuthorityReleaseKey",
    "subjectVariantSignature",
    "resolvedGearSignature",
    "effectRecordKey",
    "effectRecordSha256",
})
_SENSITIVE_KEYS = frozenset({
    "rawProfile",
    "rawString",
    "playerName",
    "characterName",
    "realm",
    "server",
    "userId",
    "userUuid",
    "userUUID",
    "ownerId",
})


class RuntimeAuthorityReleaseError(ValueError):
    """A Runtime Authority Release fact is malformed, incomplete, or drifted."""


@dataclass(frozen=True)
class _IndexEntry:
    runtime_authority_release_key: str
    subject_variant_signature: str
    resolved_gear_signature: str
    effect_record_document_key: str
    effect_record_sha256: str


def _error(code: str, path: str) -> RuntimeAuthorityReleaseError:
    return RuntimeAuthorityReleaseError(f"{code} at {path}")


def _identity(value: object, *, path: str) -> str:
    try:
        return canonical_identity_token(value, path=path, max_bytes=256)
    except CanonicalValueError as error:
        raise _error(error.code, path) from error


def _sha256(value: object, *, path: str) -> str:
    normalized = _identity(value, path=path)
    if _SHA256.fullmatch(normalized) is None:
        raise _error("INVALID_SHA256", path)
    return normalized


def _document_key(
    value: object,
    *,
    path: str,
    pattern: re.Pattern[str],
    code: str,
) -> str:
    normalized = _identity(value, path=path)
    if pattern.fullmatch(normalized) is None:
        raise _error(code, path)
    return normalized


def _blocked(error: RuntimeAuthorityReleaseError) -> CanonicalResult:
    return CanonicalResult(
        "blocked",
        None,
        (CanonicalIssue(
            "RUNTIME_AUTHORITY_RELEASE_REQUIRED",
            "runtimeAuthorityRelease",
            str(error),
        ),),
    )


def _contains_sensitive_key(value: object, path: str = "resolverAuthorityContext") -> str | None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if key in _SENSITIVE_KEYS:
                return f"{path}.{key}"
            nested_path = _contains_sensitive_key(nested, f"{path}.{key}")
            if nested_path is not None:
                return nested_path
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            nested_path = _contains_sensitive_key(nested, f"{path}[{index}]")
            if nested_path is not None:
                return nested_path
    return None


def _dependency_vector(value: object, *, path: str) -> dict[str, str]:
    if type(value) is not dict or set(value) != DEPENDENCY_VECTOR_KEYS:
        raise _error("DEPENDENCY_VECTOR_KEY_SET_MISMATCH", path)
    return {
        key: _identity(value[key], path=f"{path}.{key}")
        for key in sorted(DEPENDENCY_VECTOR_KEYS)
    }


def _resolver_context_payload(value: object) -> dict[str, object]:
    try:
        raw = canonical_mapping(value, path="resolverContext", exact_keys=_CONTEXT_KEYS)
    except CanonicalValueError as error:
        raise _error(error.code, error.path) from error
    schema_revision = _identity(raw["schemaRevision"], path="resolverContext.schemaRevision")
    if schema_revision != RUNTIME_RESOLVER_CONTEXT_SCHEMA_REVISION:
        raise _error("SCHEMA_REVISION_MISMATCH", "resolverContext.schemaRevision")
    resolver_authority_context = raw["resolverAuthorityContext"]
    if type(resolver_authority_context) is not dict:
        raise _error("INVALID_RESOLVER_AUTHORITY_CONTEXT", "resolverContext.resolverAuthorityContext")
    sensitive_path = _contains_sensitive_key(resolver_authority_context)
    if sensitive_path is not None:
        raise _error("SENSITIVE_RESOLVER_CONTEXT", sensitive_path)
    try:
        canonical_json_bytes(resolver_authority_context)
    except CanonicalValueError as error:
        raise _error(error.code, error.path) from error
    context_vector = resolver_authority_context.get("dependencyVector")
    if type(context_vector) is not dict:
        raise _error("RESOLVER_CONTEXT_VECTOR_REQUIRED", "resolverContext.resolverAuthorityContext.dependencyVector")
    normalized = {
        "schemaRevision": schema_revision,
        "producerIdentity": _identity(raw["producerIdentity"], path="resolverContext.producerIdentity"),
        "producerRevision": _identity(raw["producerRevision"], path="resolverContext.producerRevision"),
        "seasonRevision": _identity(raw["seasonRevision"], path="resolverContext.seasonRevision"),
        "gearRuleRevision": _identity(raw["gearRuleRevision"], path="resolverContext.gearRuleRevision"),
        "resolverRevision": _identity(raw["resolverRevision"], path="resolverContext.resolverRevision"),
        "simcRuntimeRevision": _identity(raw["simcRuntimeRevision"], path="resolverContext.simcRuntimeRevision"),
        "resolverAuthorityContext": resolver_authority_context,
    }
    for key in ("seasonRevision", "gearRuleRevision", "simcRuntimeRevision"):
        if context_vector.get(key) != normalized[key]:
            raise _error("RESOLVER_CONTEXT_VECTOR_DRIFT", f"resolverContext.resolverAuthorityContext.dependencyVector.{key}")
    resolver_contract_revision = context_vector.get("resolverContractRevision")
    if (
        resolver_contract_revision is not None
        and resolver_contract_revision != normalized["resolverRevision"]
    ):
        raise _error(
            "RESOLVER_CONTEXT_VECTOR_DRIFT",
            "resolverContext.resolverAuthorityContext.dependencyVector.resolverContractRevision",
        )
    return normalized


def _runtime_authority_release_payload(value: object) -> dict[str, object]:
    try:
        raw = canonical_mapping(value, path="runtimeAuthorityRelease", exact_keys=_RELEASE_KEYS)
    except CanonicalValueError as error:
        raise _error(error.code, error.path) from error
    schema_revision = _identity(raw["schemaRevision"], path="runtimeAuthorityRelease.schemaRevision")
    if schema_revision != RUNTIME_AUTHORITY_RELEASE_SCHEMA_REVISION:
        raise _error("SCHEMA_REVISION_MISMATCH", "runtimeAuthorityRelease.schemaRevision")
    return {
        "schemaRevision": schema_revision,
        "producerIdentity": _identity(raw["producerIdentity"], path="runtimeAuthorityRelease.producerIdentity"),
        "producerRevision": _identity(raw["producerRevision"], path="runtimeAuthorityRelease.producerRevision"),
        "resolverContextKey": _document_key(
            raw["resolverContextKey"],
            path="runtimeAuthorityRelease.resolverContextKey",
            pattern=_CONTEXT_KEY,
            code="INVALID_RESOLVER_CONTEXT_KEY",
        ),
        "resolverContextSha256": _sha256(
            raw["resolverContextSha256"],
            path="runtimeAuthorityRelease.resolverContextSha256",
        ),
        "dependencyVector": _dependency_vector(
            raw["dependencyVector"], path="runtimeAuthorityRelease.dependencyVector",
        ),
    }


def _occurrence_index_entry_payload(value: object) -> dict[str, object]:
    try:
        raw = canonical_mapping(value, path="runtimeOccurrenceIndexEntry", exact_keys=_INDEX_ENTRY_KEYS)
    except CanonicalValueError as error:
        raise _error(error.code, error.path) from error
    schema_revision = _identity(raw["schemaRevision"], path="runtimeOccurrenceIndexEntry.schemaRevision")
    if schema_revision != RUNTIME_OCCURRENCE_INDEX_ENTRY_SCHEMA_REVISION:
        raise _error("SCHEMA_REVISION_MISMATCH", "runtimeOccurrenceIndexEntry.schemaRevision")
    signature = _identity(
        raw["subjectVariantSignature"],
        path="runtimeOccurrenceIndexEntry.subjectVariantSignature",
    )
    if _SUBJECT_SIGNATURE.fullmatch(signature) is None:
        raise _error("INVALID_SUBJECT_VARIANT_SIGNATURE", "runtimeOccurrenceIndexEntry.subjectVariantSignature")
    resolved_gear_signature = _sha256(
        raw["resolvedGearSignature"],
        path="runtimeOccurrenceIndexEntry.resolvedGearSignature",
    )
    if _RESOLVED_GEAR_SIGNATURE.fullmatch(resolved_gear_signature) is None:
        raise _error("INVALID_RESOLVED_GEAR_SIGNATURE", "runtimeOccurrenceIndexEntry.resolvedGearSignature")
    return {
        "schemaRevision": schema_revision,
        "producerIdentity": _identity(raw["producerIdentity"], path="runtimeOccurrenceIndexEntry.producerIdentity"),
        "producerRevision": _identity(raw["producerRevision"], path="runtimeOccurrenceIndexEntry.producerRevision"),
        "runtimeAuthorityReleaseKey": _document_key(
            raw["runtimeAuthorityReleaseKey"],
            path="runtimeOccurrenceIndexEntry.runtimeAuthorityReleaseKey",
            pattern=_RELEASE_KEY,
            code="INVALID_RUNTIME_AUTHORITY_RELEASE_KEY",
        ),
        "subjectVariantSignature": signature,
        "resolvedGearSignature": resolved_gear_signature,
        "effectRecordKey": _document_key(
            raw["effectRecordKey"],
            path="runtimeOccurrenceIndexEntry.effectRecordKey",
            pattern=_EFFECT_RECORD_KEY,
            code="INVALID_EFFECT_RECORD_KEY",
        ),
        "effectRecordSha256": _sha256(
            raw["effectRecordSha256"],
            path="runtimeOccurrenceIndexEntry.effectRecordSha256",
        ),
    }


def _payload_copy(
    document: object,
    *,
    document_kind: str,
    schema_revision: str,
    key_prefix: str,
    payload_validator: Callable[[object], dict[str, object]],
) -> dict[str, object]:
    try:
        return payload_validator(verified_payload_copy(
            document,
            document_kind=document_kind,
            schema_revision=schema_revision,
            key_prefix=key_prefix,
            payload_validator=payload_validator,
        ))
    except (CanonicalValueError, RuntimeAuthorityReleaseError) as error:
        raise _error("INVALID_RUNTIME_AUTHORITY_RELEASE_DOCUMENT", "document") from error


def seal_runtime_resolver_context(value: object) -> CanonicalResult:
    """Seal a complete, privacy-safe resolver authority context or block it."""

    try:
        payload = _resolver_context_payload(value)
        document = seal_canonical_document(
            document_kind=RUNTIME_RESOLVER_CONTEXT_DOCUMENT_KIND,
            schema_revision=RUNTIME_RESOLVER_CONTEXT_SCHEMA_REVISION,
            payload=payload,
            key_prefix=RUNTIME_RESOLVER_CONTEXT_KEY_PREFIX,
        )
    except (CanonicalValueError, RuntimeAuthorityReleaseError) as error:
        return _blocked(
            error if isinstance(error, RuntimeAuthorityReleaseError)
            else _error(error.code, error.path),
        )
    return CanonicalResult("verified", document, ())


def reload_runtime_resolver_context(
    canonical_bytes: bytes,
    content_key: str,
) -> SealedCanonicalDocument:
    """Reload a persisted resolver context from exactly its canonical bytes/key."""

    try:
        return _rehydrate_canonical_document(
            canonical_bytes=canonical_bytes,
            content_key=content_key,
            document_kind=RUNTIME_RESOLVER_CONTEXT_DOCUMENT_KIND,
            schema_revision=RUNTIME_RESOLVER_CONTEXT_SCHEMA_REVISION,
            key_prefix=RUNTIME_RESOLVER_CONTEXT_KEY_PREFIX,
            payload_validator=_resolver_context_payload,
        )
    except (CanonicalValueError, RuntimeAuthorityReleaseError) as error:
        raise _error("INVALID_RUNTIME_RESOLVER_CONTEXT", "resolverContext") from error


def runtime_resolver_context_payload(document: object) -> dict[str, object]:
    return _payload_copy(
        document,
        document_kind=RUNTIME_RESOLVER_CONTEXT_DOCUMENT_KIND,
        schema_revision=RUNTIME_RESOLVER_CONTEXT_SCHEMA_REVISION,
        key_prefix=RUNTIME_RESOLVER_CONTEXT_KEY_PREFIX,
        payload_validator=_resolver_context_payload,
    )


def verify_runtime_resolver_context(document: object) -> bool:
    """Return whether one resolver context retains its sealed canonical identity."""

    return verify_sealed_document(
        document,
        document_kind=RUNTIME_RESOLVER_CONTEXT_DOCUMENT_KIND,
        schema_revision=RUNTIME_RESOLVER_CONTEXT_SCHEMA_REVISION,
        key_prefix=RUNTIME_RESOLVER_CONTEXT_KEY_PREFIX,
        payload_validator=_resolver_context_payload,
    )


def seal_runtime_authority_release(
    value: object,
    *,
    resolver_context: SealedCanonicalDocument,
) -> CanonicalResult:
    """Seal one eight-vector release that names an exact resolver context."""

    try:
        context = runtime_resolver_context_payload(resolver_context)
        if type(value) is not dict:
            raise _error("INVALID_RUNTIME_AUTHORITY_RELEASE", "runtimeAuthorityRelease")
        payload = dict(value)
        payload["resolverContextKey"] = resolver_context.content_key
        payload["resolverContextSha256"] = "sha256:" + hashlib.sha256(
            resolver_context.canonical_bytes,
        ).hexdigest()
        normalized = _runtime_authority_release_payload(payload)
        vector = normalized["dependencyVector"]
        if (
            normalized["producerIdentity"] != context["producerIdentity"]
            or normalized["producerRevision"] != context["producerRevision"]
        ):
            raise _error("RELEASE_PRODUCER_DRIFT", "runtimeAuthorityRelease")
        for key in (
            "seasonRevision",
            "gearRuleRevision",
            "resolverRevision",
            "simcRuntimeRevision",
        ):
            if vector[key] != context[key]:
                raise _error("RELEASE_CONTEXT_VECTOR_DRIFT", f"runtimeAuthorityRelease.dependencyVector.{key}")
        document = seal_canonical_document(
            document_kind=RUNTIME_AUTHORITY_RELEASE_DOCUMENT_KIND,
            schema_revision=RUNTIME_AUTHORITY_RELEASE_SCHEMA_REVISION,
            payload=normalized,
            key_prefix=RUNTIME_AUTHORITY_RELEASE_KEY_PREFIX,
        )
    except (CanonicalValueError, RuntimeAuthorityReleaseError) as error:
        return _blocked(
            error if isinstance(error, RuntimeAuthorityReleaseError)
            else _error(error.code, error.path),
        )
    return CanonicalResult("verified", document, ())


def reload_runtime_authority_release(
    canonical_bytes: bytes,
    content_key: str,
) -> SealedCanonicalDocument:
    """Reload release bytes/key without selecting an active or latest release."""

    try:
        return _rehydrate_canonical_document(
            canonical_bytes=canonical_bytes,
            content_key=content_key,
            document_kind=RUNTIME_AUTHORITY_RELEASE_DOCUMENT_KIND,
            schema_revision=RUNTIME_AUTHORITY_RELEASE_SCHEMA_REVISION,
            key_prefix=RUNTIME_AUTHORITY_RELEASE_KEY_PREFIX,
            payload_validator=_runtime_authority_release_payload,
        )
    except (CanonicalValueError, RuntimeAuthorityReleaseError) as error:
        raise _error("INVALID_RUNTIME_AUTHORITY_RELEASE", "runtimeAuthorityRelease") from error


def runtime_authority_release_payload(document: object) -> dict[str, object]:
    return _payload_copy(
        document,
        document_kind=RUNTIME_AUTHORITY_RELEASE_DOCUMENT_KIND,
        schema_revision=RUNTIME_AUTHORITY_RELEASE_SCHEMA_REVISION,
        key_prefix=RUNTIME_AUTHORITY_RELEASE_KEY_PREFIX,
        payload_validator=_runtime_authority_release_payload,
    )


def verify_runtime_authority_release(document: object) -> bool:
    """Return whether one release retains its sealed canonical identity."""

    return verify_sealed_document(
        document,
        document_kind=RUNTIME_AUTHORITY_RELEASE_DOCUMENT_KIND,
        schema_revision=RUNTIME_AUTHORITY_RELEASE_SCHEMA_REVISION,
        key_prefix=RUNTIME_AUTHORITY_RELEASE_KEY_PREFIX,
        payload_validator=_runtime_authority_release_payload,
    )


def seal_runtime_occurrence_index_entry(
    release: SealedCanonicalDocument,
    *,
    subject_variant_signature: object,
    resolved_gear_signature: object,
    effect_record: SealedCanonicalDocument,
    producer_identity: object,
    producer_revision: object,
) -> CanonicalResult:
    """Seal one release-scoped occurrence -> typed effect record relation."""

    try:
        release_payload = runtime_authority_release_payload(release)
        if (
            producer_identity != release_payload["producerIdentity"]
            or producer_revision != release_payload["producerRevision"]
        ):
            raise _error("OCCURRENCE_PRODUCER_DRIFT", "runtimeOccurrenceIndexEntry")
        record = reload_effect_record(
            effect_record.canonical_bytes,
            effect_record.content_key,
            runtime_revision=release_payload["dependencyVector"]["simcRuntimeRevision"],
        )
        record_payload = json.loads(record.canonical_bytes)
        if record_payload["subjectVariantSignature"] != subject_variant_signature:
            raise _error("OCCURRENCE_RECORD_SIGNATURE_DRIFT", "runtimeOccurrenceIndexEntry.subjectVariantSignature")
        payload = _occurrence_index_entry_payload({
            "schemaRevision": RUNTIME_OCCURRENCE_INDEX_ENTRY_SCHEMA_REVISION,
            "producerIdentity": producer_identity,
            "producerRevision": producer_revision,
            "runtimeAuthorityReleaseKey": release.content_key,
            "subjectVariantSignature": subject_variant_signature,
            "resolvedGearSignature": resolved_gear_signature,
            "effectRecordKey": record.content_key,
            "effectRecordSha256": "sha256:" + hashlib.sha256(record.canonical_bytes).hexdigest(),
        })
        document = seal_canonical_document(
            document_kind=RUNTIME_OCCURRENCE_INDEX_ENTRY_DOCUMENT_KIND,
            schema_revision=RUNTIME_OCCURRENCE_INDEX_ENTRY_SCHEMA_REVISION,
            payload=payload,
            key_prefix=RUNTIME_OCCURRENCE_INDEX_ENTRY_KEY_PREFIX,
        )
    except (CanonicalValueError, RuntimeAuthorityReleaseError, TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
        if isinstance(error, RuntimeAuthorityReleaseError):
            return _blocked(error)
        if isinstance(error, CanonicalValueError):
            return _blocked(_error(error.code, error.path))
        return _blocked(_error("INVALID_RUNTIME_OCCURRENCE_INDEX_ENTRY", "runtimeOccurrenceIndexEntry"))
    return CanonicalResult("verified", document, ())


def reload_runtime_occurrence_index_entry(
    canonical_bytes: bytes,
    content_key: str,
) -> SealedCanonicalDocument:
    """Reload one occurrence relation from its canonical bytes/key only."""

    try:
        return _rehydrate_canonical_document(
            canonical_bytes=canonical_bytes,
            content_key=content_key,
            document_kind=RUNTIME_OCCURRENCE_INDEX_ENTRY_DOCUMENT_KIND,
            schema_revision=RUNTIME_OCCURRENCE_INDEX_ENTRY_SCHEMA_REVISION,
            key_prefix=RUNTIME_OCCURRENCE_INDEX_ENTRY_KEY_PREFIX,
            payload_validator=_occurrence_index_entry_payload,
        )
    except (CanonicalValueError, RuntimeAuthorityReleaseError) as error:
        raise _error("INVALID_RUNTIME_OCCURRENCE_INDEX_ENTRY", "runtimeOccurrenceIndexEntry") from error


def runtime_occurrence_index_entry_payload(document: object) -> dict[str, object]:
    return _payload_copy(
        document,
        document_kind=RUNTIME_OCCURRENCE_INDEX_ENTRY_DOCUMENT_KIND,
        schema_revision=RUNTIME_OCCURRENCE_INDEX_ENTRY_SCHEMA_REVISION,
        key_prefix=RUNTIME_OCCURRENCE_INDEX_ENTRY_KEY_PREFIX,
        payload_validator=_occurrence_index_entry_payload,
    )


def verify_runtime_occurrence_index_entry(document: object) -> bool:
    """Return whether one release occurrence relation remains canonical."""

    return verify_sealed_document(
        document,
        document_kind=RUNTIME_OCCURRENCE_INDEX_ENTRY_DOCUMENT_KIND,
        schema_revision=RUNTIME_OCCURRENCE_INDEX_ENTRY_SCHEMA_REVISION,
        key_prefix=RUNTIME_OCCURRENCE_INDEX_ENTRY_KEY_PREFIX,
        payload_validator=_occurrence_index_entry_payload,
    )


def _index_entry(document: object) -> _IndexEntry:
    payload = runtime_occurrence_index_entry_payload(document)
    return _IndexEntry(
        runtime_authority_release_key=payload["runtimeAuthorityReleaseKey"],
        subject_variant_signature=payload["subjectVariantSignature"],
        resolved_gear_signature=payload["resolvedGearSignature"],
        effect_record_document_key=payload["effectRecordKey"],
        effect_record_sha256=payload["effectRecordSha256"],
    )


def _verify_snapshot_release_vector(
    resolver_snapshot: object,
    release_payload: Mapping[str, object],
) -> None:
    if type(resolver_snapshot) is not dict:
        raise _error("INVALID_RESOLVER_SNAPSHOT", "resolverSnapshot")
    snapshot_vector = resolver_snapshot.get("dependencyVector")
    boundary = resolver_snapshot.get("v2EffectBoundary")
    if type(snapshot_vector) is not dict or type(boundary) is not dict:
        raise _error("RELEASE_SNAPSHOT_VECTOR_DRIFT", "resolverSnapshot")
    release_vector = release_payload["dependencyVector"]
    if type(release_vector) is not dict:
        raise _error("INVALID_RUNTIME_AUTHORITY_RELEASE", "runtimeAuthorityRelease.dependencyVector")
    observed = {
        "seasonRevision": snapshot_vector.get("seasonRevision"),
        "gearRuleRevision": snapshot_vector.get("gearRuleRevision"),
        "resolverRevision": boundary.get("resolverRevision"),
        "simcRuntimeRevision": snapshot_vector.get("simcRuntimeRevision"),
    }
    for key, value in observed.items():
        if value != release_vector.get(key):
            raise _error("RELEASE_SNAPSHOT_VECTOR_DRIFT", f"resolverSnapshot.{key}")


def resolve_release_effect_records(
    release: SealedCanonicalDocument,
    *,
    resolver_snapshot: object,
    index_entries: Sequence[SealedCanonicalDocument],
    record_loader: Callable[[str], SealedCanonicalDocument],
) -> tuple[SealedCanonicalDocument, ...]:
    """Load exactly one release-indexed effect record per ordered occurrence."""

    try:
        release_payload = runtime_authority_release_payload(release)
        _verify_snapshot_release_vector(resolver_snapshot, release_payload)
        signatures = loadout_effect_subject_signatures(resolver_snapshot)
        snapshot_gear_signature = _sha256(
            resolver_snapshot["resolvedGearSignature"],
            path="resolverSnapshot.resolvedGearSignature",
        )
        if not isinstance(index_entries, Sequence) or isinstance(index_entries, (str, bytes, bytearray)):
            raise _error("INVALID_OCCURRENCE_INDEX_SEQUENCE", "indexEntries")
        indexed: dict[str, _IndexEntry] = {}
        for position, document in enumerate(index_entries):
            entry = _index_entry(document)
            if entry.runtime_authority_release_key != release.content_key:
                raise _error("OCCURRENCE_RELEASE_DRIFT", f"indexEntries[{position}]")
            if entry.resolved_gear_signature != snapshot_gear_signature:
                raise _error("OCCURRENCE_GEAR_SIGNATURE_DRIFT", f"indexEntries[{position}]")
            if entry.subject_variant_signature in indexed:
                raise _error("OCCURRENCE_INDEX_AMBIGUOUS", f"indexEntries[{position}]")
            indexed[entry.subject_variant_signature] = entry
        if set(indexed) != set(signatures):
            raise _error("OCCURRENCE_INDEX_COVERAGE_MISMATCH", "indexEntries")
        records = []
        runtime_revision = release_payload["dependencyVector"]["simcRuntimeRevision"]
        for position, signature in enumerate(signatures):
            entry = indexed[signature]
            loaded = record_loader(entry.effect_record_document_key)
            if type(loaded) is not SealedCanonicalDocument:
                raise _error("INVALID_EFFECT_RECORD_LOADER_RESULT", f"records[{position}]")
            record = reload_effect_record(
                loaded.canonical_bytes,
                loaded.content_key,
                runtime_revision=runtime_revision,
            )
            if (
                record.content_key != entry.effect_record_document_key
                or "sha256:" + hashlib.sha256(record.canonical_bytes).hexdigest()
                != entry.effect_record_sha256
            ):
                raise _error("EFFECT_RECORD_SUBSTITUTION", f"records[{position}]")
            payload = json.loads(record.canonical_bytes)
            if payload["subjectVariantSignature"] != signature:
                raise _error("EFFECT_RECORD_SIGNATURE_DRIFT", f"records[{position}]")
            records.append(record)
    except (CanonicalValueError, RuntimeAuthorityReleaseError, TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
        if isinstance(error, RuntimeAuthorityReleaseError):
            raise error
        if isinstance(error, CanonicalValueError):
            raise _error(error.code, error.path) from error
        raise _error("INVALID_RELEASE_EFFECT_RECORDS", "releaseEffectRecords") from error
    return tuple(records)


__all__ = (
    "RUNTIME_AUTHORITY_RELEASE_DOCUMENT_KIND",
    "RUNTIME_AUTHORITY_RELEASE_KEY_PREFIX",
    "RUNTIME_AUTHORITY_RELEASE_SCHEMA_REVISION",
    "RUNTIME_OCCURRENCE_INDEX_ENTRY_DOCUMENT_KIND",
    "RUNTIME_OCCURRENCE_INDEX_ENTRY_KEY_PREFIX",
    "RUNTIME_OCCURRENCE_INDEX_ENTRY_SCHEMA_REVISION",
    "RUNTIME_RESOLVER_CONTEXT_DOCUMENT_KIND",
    "RUNTIME_RESOLVER_CONTEXT_KEY_PREFIX",
    "RUNTIME_RESOLVER_CONTEXT_SCHEMA_REVISION",
    "RuntimeAuthorityReleaseError",
    "reload_runtime_authority_release",
    "reload_runtime_occurrence_index_entry",
    "reload_runtime_resolver_context",
    "resolve_release_effect_records",
    "runtime_authority_release_payload",
    "runtime_occurrence_index_entry_payload",
    "runtime_resolver_context_payload",
    "seal_runtime_authority_release",
    "seal_runtime_occurrence_index_entry",
    "seal_runtime_resolver_context",
    "verify_runtime_authority_release",
    "verify_runtime_occurrence_index_entry",
    "verify_runtime_resolver_context",
)
