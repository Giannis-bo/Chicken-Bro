#!/usr/bin/env python3
"""PostgreSQL boundary for immutable Exact Runtime Authority Releases.

The store accepts only already-sealed Task 5C documents.  It deliberately
does not discover an active release: a binding with zero or multiple release
memberships is an integrity failure for every caller.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
import uuid

try:
    from .exact_runtime_authority_release import (
        RuntimeAuthorityReleaseError,
        reload_runtime_authority_release,
        reload_runtime_occurrence_index_entry,
        reload_runtime_resolver_context,
        runtime_authority_release_payload,
        runtime_occurrence_index_entry_payload,
        runtime_resolver_context_payload,
    )
    from .gear_canonical_kernel import SealedCanonicalDocument
    from .gear_exact_authority_store import (
        GearExactAuthorityStore,
        GearExactAuthorityStoreIntegrityError,
    )
except ImportError:  # pragma: no cover - direct server runtime compatibility
    from exact_runtime_authority_release import (
        RuntimeAuthorityReleaseError,
        reload_runtime_authority_release,
        reload_runtime_occurrence_index_entry,
        reload_runtime_resolver_context,
        runtime_authority_release_payload,
        runtime_occurrence_index_entry_payload,
        runtime_resolver_context_payload,
    )
    from gear_canonical_kernel import SealedCanonicalDocument
    from gear_exact_authority_store import (
        GearExactAuthorityStore,
        GearExactAuthorityStoreIntegrityError,
    )


_BINDING_KEY = re.compile(r"^exact-template-authority-binding:sha256:[0-9a-f]{64}$")


class RuntimeAuthorityReleaseIntegrityError(RuntimeError):
    """Persisted release membership is absent, ambiguous, partial, or drifted."""


@dataclass(frozen=True)
class RuntimeAuthorityReleaseMembership:
    resolver_context: SealedCanonicalDocument
    release: SealedCanonicalDocument


def _owner_id(value: object) -> str:
    if type(value) is not str:
        raise RuntimeAuthorityReleaseIntegrityError("invalid owner id")
    try:
        parsed = uuid.UUID(value)
    except (AttributeError, TypeError, ValueError) as error:
        raise RuntimeAuthorityReleaseIntegrityError("invalid owner id") from error
    canonical = str(parsed)
    if canonical != value:
        raise RuntimeAuthorityReleaseIntegrityError("invalid owner id")
    return canonical


def _binding_key(value: object) -> str:
    if type(value) is not str or _BINDING_KEY.fullmatch(value) is None:
        raise RuntimeAuthorityReleaseIntegrityError("invalid binding key")
    return value


def _canonical_bytes(value: object, *, field: str) -> bytes:
    if type(value) is bytes:
        return value
    if isinstance(value, memoryview):
        return value.tobytes()
    raise RuntimeAuthorityReleaseIntegrityError(f"invalid {field}")


def _verified_membership(
    resolver_context: object,
    release: object,
) -> RuntimeAuthorityReleaseMembership:
    if type(resolver_context) is not SealedCanonicalDocument:
        raise RuntimeAuthorityReleaseIntegrityError("resolver context must be sealed")
    if type(release) is not SealedCanonicalDocument:
        raise RuntimeAuthorityReleaseIntegrityError("runtime authority release must be sealed")
    try:
        context_payload = runtime_resolver_context_payload(resolver_context)
        release_payload = runtime_authority_release_payload(release)
    except RuntimeAuthorityReleaseError as error:
        raise RuntimeAuthorityReleaseIntegrityError(
            "runtime authority document typed reload failed",
        ) from error
    if release_payload["resolverContextKey"] != resolver_context.content_key:
        raise RuntimeAuthorityReleaseIntegrityError("release/context key drift")
    context_sha256 = "sha256:" + hashlib.sha256(
        resolver_context.canonical_bytes,
    ).hexdigest()
    if release_payload["resolverContextSha256"] != context_sha256:
        raise RuntimeAuthorityReleaseIntegrityError("release/context hash drift")
    release_vector = release_payload["dependencyVector"]
    for key in (
        "seasonRevision",
        "gearRuleRevision",
        "resolverRevision",
        "simcRuntimeRevision",
    ):
        if release_vector.get(key) != context_payload.get(key):
            raise RuntimeAuthorityReleaseIntegrityError("release/context vector drift")
    return RuntimeAuthorityReleaseMembership(
        resolver_context=resolver_context,
        release=release,
    )


def _membership_row(row: object) -> RuntimeAuthorityReleaseMembership:
    if type(row) not in {tuple, list} or len(row) != 4:
        raise RuntimeAuthorityReleaseIntegrityError("release membership row is invalid")
    try:
        context = reload_runtime_resolver_context(
            _canonical_bytes(row[1], field="resolver context bytes"),
            row[0],
        )
        release = reload_runtime_authority_release(
            _canonical_bytes(row[3], field="runtime authority release bytes"),
            row[2],
        )
    except (RuntimeAuthorityReleaseError, TypeError, ValueError) as error:
        raise RuntimeAuthorityReleaseIntegrityError(
            "release membership bytes/key drift",
        ) from error
    return _verified_membership(context, release)


class RuntimeAuthorityReleaseStore:
    """Use only the owner-scoped 0035 SECURITY DEFINER release functions."""

    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    def connection(self):
        return self._connection_factory()

    @staticmethod
    def _validated_entries(
        release: SealedCanonicalDocument,
        occurrence_entries: object,
    ) -> tuple[SealedCanonicalDocument, ...]:
        if type(occurrence_entries) not in {tuple, list}:
            raise RuntimeAuthorityReleaseIntegrityError(
                "occurrence entries must be an ordered tuple or list",
            )
        entries = tuple(occurrence_entries)
        signatures: set[str] = set()
        for index, document in enumerate(entries):
            if type(document) is not SealedCanonicalDocument:
                raise RuntimeAuthorityReleaseIntegrityError(
                    "occurrence entry must be sealed",
                )
            try:
                payload = runtime_occurrence_index_entry_payload(document)
            except RuntimeAuthorityReleaseError as error:
                raise RuntimeAuthorityReleaseIntegrityError(
                    "occurrence entry typed reload failed",
                ) from error
            if payload["runtimeAuthorityReleaseKey"] != release.content_key:
                raise RuntimeAuthorityReleaseIntegrityError(
                    f"occurrence release drift at position {index}",
                )
            signature = payload["subjectVariantSignature"]
            if signature in signatures:
                raise RuntimeAuthorityReleaseIntegrityError(
                    f"occurrence membership is not unique at position {index}",
                )
            signatures.add(signature)
        return entries

    def admit(
        self,
        owner_id: object,
        binding_key: object,
        *,
        resolver_context: object,
        release: object,
        occurrence_entries: object,
    ) -> RuntimeAuthorityReleaseMembership:
        """Admit one exact release closure and rehydrate its readback in one transaction."""

        owner = _owner_id(owner_id)
        binding = _binding_key(binding_key)
        membership = _verified_membership(resolver_context, release)
        entries = self._validated_entries(membership.release, occurrence_entries)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        resolver_context_key,
                        resolver_context_bytes,
                        runtime_authority_release_key,
                        runtime_authority_release_bytes
                    FROM ops.websim_exact_runtime_authority_release_admit(
                        %s::uuid, %s, %s, %s, %s::bytea[]
                    )
                    """,
                    (
                        owner,
                        binding,
                        membership.resolver_context.canonical_bytes,
                        membership.release.canonical_bytes,
                        [entry.canonical_bytes for entry in entries],
                    ),
                )
                return _membership_row(cur.fetchone())

    def read_unique_for_binding(
        self,
        owner_id: object,
        binding_key: object,
    ) -> RuntimeAuthorityReleaseMembership:
        """Read exactly one release, never using current/latest selection semantics."""

        owner = _owner_id(owner_id)
        binding = _binding_key(binding_key)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        resolver_context_key,
                        resolver_context_bytes,
                        runtime_authority_release_key,
                        runtime_authority_release_bytes
                    FROM ops.websim_exact_runtime_authority_release_read(
                        %s::uuid, %s
                    )
                    """,
                    (owner, binding),
                )
                rows = cur.fetchall()
        if not rows:
            raise RuntimeAuthorityReleaseIntegrityError(
                "runtime authority release membership is missing",
            )
        if len(rows) != 1:
            raise RuntimeAuthorityReleaseIntegrityError(
                "runtime authority release membership is not unique",
            )
        return _membership_row(rows[0])

    def read_occurrences(
        self,
        owner_id: object,
        binding_key: object,
        release: object,
    ) -> tuple[SealedCanonicalDocument, ...]:
        """Read the whole release-scoped index; callers retain occurrence order later."""

        owner = _owner_id(owner_id)
        binding = _binding_key(binding_key)
        if type(release) is not SealedCanonicalDocument:
            raise RuntimeAuthorityReleaseIntegrityError("runtime authority release must be sealed")
        try:
            runtime_authority_release_payload(release)
        except RuntimeAuthorityReleaseError as error:
            raise RuntimeAuthorityReleaseIntegrityError(
                "runtime authority release typed reload failed",
            ) from error
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT runtime_occurrence_index_entry_key, runtime_occurrence_index_entry_bytes
                    FROM ops.websim_exact_runtime_authority_release_occurrences_read(
                        %s::uuid, %s, %s
                    )
                    """,
                    (owner, binding, release.content_key),
                )
                rows = cur.fetchall()
        entries: list[SealedCanonicalDocument] = []
        for row in rows:
            if type(row) not in {tuple, list} or len(row) != 2:
                raise RuntimeAuthorityReleaseIntegrityError(
                    "occurrence index row is invalid",
                )
            try:
                entry = reload_runtime_occurrence_index_entry(
                    _canonical_bytes(row[1], field="occurrence index bytes"),
                    row[0],
                )
            except (RuntimeAuthorityReleaseError, TypeError, ValueError) as error:
                raise RuntimeAuthorityReleaseIntegrityError(
                    "occurrence index bytes/key drift",
                ) from error
            entries.append(entry)
        return self._validated_entries(release, tuple(entries))

    def load_effect_records(
        self,
        release: object,
        occurrence_entries: object,
    ) -> tuple[SealedCanonicalDocument, ...]:
        """Typed-reload every index record at the release's exact SimC revision."""

        if type(release) is not SealedCanonicalDocument:
            raise RuntimeAuthorityReleaseIntegrityError("runtime authority release must be sealed")
        try:
            release_payload = runtime_authority_release_payload(release)
        except RuntimeAuthorityReleaseError as error:
            raise RuntimeAuthorityReleaseIntegrityError(
                "runtime authority release typed reload failed",
            ) from error
        entries = self._validated_entries(release, occurrence_entries)
        if not entries:
            return ()
        payloads = tuple(runtime_occurrence_index_entry_payload(entry) for entry in entries)
        record_keys = tuple(payload["effectRecordKey"] for payload in payloads)
        try:
            records = GearExactAuthorityStore(
                self._connection_factory,
            ).load_effect_records(
                record_keys,
                simc_runtime_revision=release_payload["dependencyVector"]["simcRuntimeRevision"],
            )
        except (GearExactAuthorityStoreIntegrityError, AttributeError, TypeError, ValueError) as error:
            raise RuntimeAuthorityReleaseIntegrityError(
                "release occurrence effect record typed reload failed",
            ) from error
        for payload, record in zip(payloads, records, strict=True):
            actual_hash = "sha256:" + hashlib.sha256(record.canonical_bytes).hexdigest()
            if record.content_key != payload["effectRecordKey"] or actual_hash != payload["effectRecordSha256"]:
                raise RuntimeAuthorityReleaseIntegrityError(
                    "release occurrence effect record drift",
                )
        return records


__all__ = (
    "RuntimeAuthorityReleaseIntegrityError",
    "RuntimeAuthorityReleaseMembership",
    "RuntimeAuthorityReleaseStore",
)
