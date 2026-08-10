#!/usr/bin/env python3
"""Fail-closed replay of a saved template's already-admitted Exact authority.

This module deliberately does not import registry matching or admission logic.
It can only re-read an owner-scoped saved template, find one matching sealed
binding, and rehydrate the bundle keys recorded by that binding at its pinned
revisions.  It is an internal materialization input, never a public payload.
"""

from __future__ import annotations

from typing import Any

try:
    from .exact_template_authority_binding import (
        ExactTemplateAuthorityBindingError,
        binding_matches_remote_template_source,
        canonical_remote_template_source,
        exact_template_authority_binding_payload,
    )
    from .exact_template_authority_binding_store import (
        ExactTemplateAuthorityBindingStoreIntegrityError,
    )
except ImportError:  # pragma: no cover - direct server runtime compatibility
    from exact_template_authority_binding import (
        ExactTemplateAuthorityBindingError,
        binding_matches_remote_template_source,
        canonical_remote_template_source,
        exact_template_authority_binding_payload,
    )
    from exact_template_authority_binding_store import (
        ExactTemplateAuthorityBindingStoreIntegrityError,
    )


_PROBLEM = "EXACT_SOURCE_AUTHORITY_REQUIRED"


def _blocked() -> dict[str, Any]:
    return {
        "status": "blocked",
        "problemCodes": [_PROBLEM],
        "problems": [{"code": _PROBLEM}],
    }


class ExactTemplateAuthoritySourceReader:
    """Read one fully sealed source-to-bundle closure without discovery."""

    def __init__(self, *, personal_store: Any, binding_store: Any, bundle_store: Any):
        self._personal_store = personal_store
        self._binding_store = binding_store
        self._bundle_store = bundle_store

    def read(
        self,
        owner_id: Any,
        template_id: Any,
        *,
        gear_exact_registry_revision: Any,
        gear_rule_revision: Any,
        resolver_revision: Any,
        simc_runtime_revision: Any,
    ) -> dict[str, Any]:
        """Return a reverified internal closure, otherwise literal blocked.

        Every error deliberately collapses to the source-authority boundary: no
        raw source, SQL error, identity, or alternative matching hint becomes
        observable to a caller.
        """

        try:
            raw_source = self._personal_store.load_remote_gear_template_for_exact(
                owner_id,
                template_id,
            )
            if raw_source is None:
                return _blocked()
            source = canonical_remote_template_source(raw_source)
            document = self._binding_store.read(
                owner_id,
                source,
                gear_exact_registry_revision=gear_exact_registry_revision,
                gear_rule_revision=gear_rule_revision,
                resolver_revision=resolver_revision,
                simc_runtime_revision=simc_runtime_revision,
            )
            if document is None or not binding_matches_remote_template_source(
                document,
                source,
            ):
                return _blocked()
            payload = exact_template_authority_binding_payload(document)
            authority = payload["authority"]
            expected_authority = {
                "gearExactRegistryRevision": gear_exact_registry_revision,
                "gearRuleRevision": gear_rule_revision,
                "resolverRevision": resolver_revision,
                "simcRuntimeRevision": simc_runtime_revision,
            }
            if any(
                authority.get(field) != expected
                for field, expected in expected_authority.items()
            ):
                return _blocked()
            slot_bundles: list[dict[str, Any]] = []
            for relation in payload["exactAuthorityBySlot"]:
                envelope_key = relation["exactAuthorityEnvelopeKey"]
                bundle = self._bundle_store.load_verified_bundle(
                    envelope_key,
                    gear_rule_revision=gear_rule_revision,
                    resolver_revision=resolver_revision,
                    simc_runtime_revision=simc_runtime_revision,
                )
                if getattr(getattr(bundle, "envelope", None), "content_key", None) != envelope_key:
                    return _blocked()
                slot_bundles.append({
                    "slot": relation["slot"],
                    "exactAuthorityEnvelopeKey": envelope_key,
                    "bundle": bundle,
                })
            return {
                "status": "verified",
                "source": source,
                "binding": document,
                "slotBundles": tuple(slot_bundles),
                "problemCodes": [],
                "problems": [],
            }
        except (
            AttributeError,
            ExactTemplateAuthorityBindingError,
            ExactTemplateAuthorityBindingStoreIntegrityError,
            TypeError,
            ValueError,
        ):
            return _blocked()
        except Exception:
            # Store-specific integrity errors must never induce a runtime
            # registry fallback or leak a persistence detail.
            return _blocked()


__all__ = ("ExactTemplateAuthoritySourceReader",)
