#!/usr/bin/env python3
"""Fixed PostgreSQL function boundary for Exact remote-template bindings."""

from __future__ import annotations

from typing import Any
import uuid

try:
    from .exact_template_authority_binding import (
        ExactTemplateAuthorityBindingError,
        RemoteTemplateSource,
        binding_matches_remote_template_source,
        exact_template_authority_binding_payload,
        owner_key_hash_for_user_id,
        reload_exact_template_authority_binding,
    )
    from .gear_canonical_kernel import CanonicalValueError, SealedCanonicalDocument, canonical_identity_token
except ImportError:  # pragma: no cover - direct server runtime compatibility
    from exact_template_authority_binding import (
        ExactTemplateAuthorityBindingError,
        RemoteTemplateSource,
        binding_matches_remote_template_source,
        exact_template_authority_binding_payload,
        owner_key_hash_for_user_id,
        reload_exact_template_authority_binding,
    )
    from gear_canonical_kernel import CanonicalValueError, SealedCanonicalDocument, canonical_identity_token


class ExactTemplateAuthorityBindingStoreIntegrityError(RuntimeError):
    """The bounded binding function surface returned unsafe or drifted data."""


def _owner_id(value: Any) -> str:
    if type(value) is not str:
        raise ExactTemplateAuthorityBindingStoreIntegrityError("invalid owner id")
    try:
        parsed = uuid.UUID(value)
    except (AttributeError, TypeError, ValueError) as error:
        raise ExactTemplateAuthorityBindingStoreIntegrityError(
            "invalid owner id",
        ) from error
    canonical = str(parsed)
    if canonical != value:
        raise ExactTemplateAuthorityBindingStoreIntegrityError("invalid owner id")
    return canonical


def _source_for_owner(owner_id: Any, source: Any) -> tuple[str, RemoteTemplateSource]:
    owner = _owner_id(owner_id)
    if type(source) is not RemoteTemplateSource:
        raise ExactTemplateAuthorityBindingStoreIntegrityError(
            "remote template source must be typed",
        )
    try:
        expected_hash = owner_key_hash_for_user_id(owner)
    except ExactTemplateAuthorityBindingError as error:
        raise ExactTemplateAuthorityBindingStoreIntegrityError(
            "invalid owner id",
        ) from error
    if source.owner_key_hash != expected_hash:
        raise ExactTemplateAuthorityBindingStoreIntegrityError(
            "owner/source scope mismatch",
        )
    return owner, source


def _expected_authority(
    *,
    gear_exact_registry_revision: Any,
    gear_rule_revision: Any,
    resolver_revision: Any,
    simc_runtime_revision: Any,
) -> dict[str, str]:
    raw = {
        "gearExactRegistryRevision": gear_exact_registry_revision,
        "gearRuleRevision": gear_rule_revision,
        "resolverRevision": resolver_revision,
        "simcRuntimeRevision": simc_runtime_revision,
    }
    try:
        return {
            field: canonical_identity_token(value, path=f"authority.{field}")
            for field, value in raw.items()
        }
    except CanonicalValueError as error:
        raise ExactTemplateAuthorityBindingStoreIntegrityError(
            "invalid expected authority revision",
        ) from error


def _row_document(
    row: Any,
    source: RemoteTemplateSource,
    expected_authority: dict[str, str] | None = None,
) -> SealedCanonicalDocument:
    if type(row) not in {tuple, list} or len(row) != 2:
        raise ExactTemplateAuthorityBindingStoreIntegrityError(
            "binding function row is invalid",
        )
    try:
        document = reload_exact_template_authority_binding(row[0], row[1])
    except ExactTemplateAuthorityBindingError as error:
        raise ExactTemplateAuthorityBindingStoreIntegrityError(
            "binding function bytes/key drift",
        ) from error
    if not binding_matches_remote_template_source(document, source):
        raise ExactTemplateAuthorityBindingStoreIntegrityError(
            "binding function source scope drift",
        )
    if expected_authority is not None:
        actual = exact_template_authority_binding_payload(document)["authority"]
        for field, expected in expected_authority.items():
            if actual.get(field) != expected:
                raise ExactTemplateAuthorityBindingStoreIntegrityError(
                    "binding function authority revision drift",
                )
    return document


class ExactTemplateAuthorityBindingStore:
    """Use only owner-scoped 0033 SECURITY DEFINER functions for bindings."""

    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    def connection(self):
        return self._connection_factory()

    def admit(
        self,
        owner_id: Any,
        source: Any,
        document: Any,
    ) -> SealedCanonicalDocument:
        owner, typed_source = _source_for_owner(owner_id, source)
        if type(document) is not SealedCanonicalDocument:
            raise ExactTemplateAuthorityBindingStoreIntegrityError(
                "binding document must be sealed",
            )
        if not binding_matches_remote_template_source(document, typed_source):
            raise ExactTemplateAuthorityBindingStoreIntegrityError(
                "binding document source scope mismatch",
            )
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT binding_key, binding_bytes
                    FROM ops.websim_exact_template_binding_admit(
                        %s::uuid, %s::uuid, %s, %s, %s, %s
                    )
                    """,
                    (
                        owner,
                        typed_source.template_id,
                        typed_source.template_config_hash,
                        typed_source.source_payload_hash,
                        typed_source.selection_signature,
                        document.canonical_bytes,
                    ),
                )
                return _row_document(cur.fetchone(), typed_source)

    def read(
        self,
        owner_id: Any,
        source: Any,
        *,
        gear_exact_registry_revision: Any,
        gear_rule_revision: Any,
        resolver_revision: Any,
        simc_runtime_revision: Any,
    ) -> SealedCanonicalDocument | None:
        owner, typed_source = _source_for_owner(owner_id, source)
        expected = _expected_authority(
            gear_exact_registry_revision=gear_exact_registry_revision,
            gear_rule_revision=gear_rule_revision,
            resolver_revision=resolver_revision,
            simc_runtime_revision=simc_runtime_revision,
        )
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT binding_key, binding_bytes
                    FROM ops.websim_exact_template_binding_read(
                        %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        owner,
                        typed_source.template_id,
                        typed_source.template_config_hash,
                        typed_source.source_payload_hash,
                        typed_source.selection_signature,
                        expected["gearExactRegistryRevision"],
                        expected["gearRuleRevision"],
                        expected["resolverRevision"],
                        expected["simcRuntimeRevision"],
                    ),
                )
                rows = cur.fetchall()
        if not rows:
            return None
        if len(rows) != 1:
            raise ExactTemplateAuthorityBindingStoreIntegrityError(
                "binding function result is not unique",
            )
        return _row_document(rows[0], typed_source, expected)


__all__ = (
    "ExactTemplateAuthorityBindingStore",
    "ExactTemplateAuthorityBindingStoreIntegrityError",
)
