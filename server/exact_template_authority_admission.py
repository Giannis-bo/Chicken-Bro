#!/usr/bin/env python3
"""One explicit server-side admission step for saved Exact template sources."""

from __future__ import annotations

import re
from typing import Any, Mapping

try:
    from .exact_template_authority_binding import (
        ExactTemplateAuthorityBindingError,
        RemoteTemplateSource,
        seal_exact_template_authority_binding,
    )
    from .gear_exact_template_options import bind_exact_template_authority
    from .gear_resolved_loadout import build_resolved_loadout_from_registry
    from .gear_resolver import resolve
except ImportError:  # pragma: no cover - direct server runtime compatibility
    from exact_template_authority_binding import (
        ExactTemplateAuthorityBindingError,
        RemoteTemplateSource,
        seal_exact_template_authority_binding,
    )
    from gear_exact_template_options import bind_exact_template_authority
    from gear_resolved_loadout import build_resolved_loadout_from_registry
    from gear_resolver import resolve


_EXACT_ITEM_KEY = re.compile(r"^exact-item-instance:sha256:[0-9a-f]{64}$")


def _text(value: Any) -> str:
    return value if type(value) is str else ""


def _blocked(*codes: str) -> dict[str, Any]:
    normalized = sorted({code for code in codes if _text(code)})
    return {
        "status": "blocked",
        "problemCodes": normalized or ["EXACT_SOURCE_AUTHORITY_REQUIRED"],
        "problems": [],
    }


def _bound_group(
    registry: Any,
    template_authority_identity: Any,
    expected_slots: tuple[str, ...],
) -> tuple[str, dict[str, str]] | None:
    if not isinstance(registry, Mapping):
        return None
    identity = _text(template_authority_identity)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for raw in registry.get("templateReferences") or []:
        row = dict(raw) if isinstance(raw, Mapping) else {}
        if (
            _text(row.get("templateScope")) == "community"
            and _text(row.get("templateAuthorityIdentity")) == identity
            and _text(row.get("templateContentHash"))
        ):
            grouped.setdefault(_text(row["templateContentHash"]), []).append(row)
    if len(grouped) != 1:
        return None
    content_hash, rows = next(iter(grouped.items()))
    exact_by_slot: dict[str, str] = {}
    for row in rows:
        slot = _text(row.get("slot"))
        exact_key = _text(row.get("exactItemInstanceKey"))
        if (
            slot in exact_by_slot
            or slot not in expected_slots
            or _EXACT_ITEM_KEY.fullmatch(exact_key) is None
        ):
            return None
        exact_by_slot[slot] = exact_key
    if set(exact_by_slot) != set(expected_slots):
        return None
    return content_hash, exact_by_slot


def admit_saved_remote_template(
    source: RemoteTemplateSource,
    *,
    exact_registry: Any,
    catalog: Any,
    authority_context: Any,
    bundle_store: Any,
    resolver_revision: str,
    simc_runtime_revision: str,
) -> dict[str, Any]:
    """Prove and seal a source relation immediately after saved-source reload.

    The caller is responsible for calling this only from the save/reload
    admission path.  This function does not offer a public or runtime fallback
    that discovers a template from source intent alone.
    """

    if type(source) is not RemoteTemplateSource:
        return _blocked("EXACT_SOURCE_AUTHORITY_REQUIRED")
    binder = bind_exact_template_authority(
        source.selection_intent,
        authority_context,
        exact_registry,
        catalog,
    )
    if not isinstance(binder, Mapping) or binder.get("status") != "verified":
        codes = (
            binder.get("problemCodes")
            if isinstance(binder, Mapping) and isinstance(binder.get("problemCodes"), list)
            else []
        )
        return _blocked(*[_text(code) for code in codes], "EXACT_SOURCE_AUTHORITY_REQUIRED")
    expected_slots = tuple(source.selection_intent["slots"])
    group = _bound_group(
        exact_registry,
        binder.get("templateAuthorityIdentity"),
        expected_slots,
    )
    if group is None:
        return _blocked("EXACT_TEMPLATE_AUTHORITY_AMBIGUOUS")
    template_content_hash, exact_item_by_slot = group
    resolver_snapshot = resolve(
        binder.get("selectionIntent"),
        binder.get("authorityContext"),
    )
    loadout = build_resolved_loadout_from_registry(
        resolver_snapshot=resolver_snapshot,
        exact_registry=exact_registry,
        template_scope="community",
        template_authority_identity=_text(binder.get("templateAuthorityIdentity")),
    )
    if not isinstance(loadout, Mapping) or loadout.get("status") != "ready":
        codes = (
            loadout.get("problemCodes")
            if isinstance(loadout, Mapping) and isinstance(loadout.get("problemCodes"), list)
            else []
        )
        return _blocked(*[_text(code) for code in codes], "EXACT_SOURCE_AUTHORITY_REQUIRED")
    ordered_slots = loadout.get("orderedSlots")
    if not isinstance(ordered_slots, list):
        return _blocked("EXACT_SOURCE_AUTHORITY_REQUIRED")
    pairs: list[dict[str, str]] = []
    seen_slots: set[str] = set()
    try:
        for row in ordered_slots:
            item = dict(row) if isinstance(row, Mapping) else {}
            slot = _text(item.get("slot"))
            exact_key = _text(item.get("exactItemInstanceKey"))
            if (
                slot not in exact_item_by_slot
                or exact_item_by_slot[slot] != exact_key
                or slot in seen_slots
            ):
                return _blocked("EXACT_SOURCE_AUTHORITY_REQUIRED")
            seen_slots.add(slot)
            bundle = bundle_store.load_verified_bundle_for_exact_item(
                exact_key,
                gear_rule_revision=_text(
                    binder.get("authorityContext", {}).get("dependencyVector", {}).get("gearRuleRevision")
                    if isinstance(binder.get("authorityContext"), Mapping)
                    else ""
                ),
                resolver_revision=resolver_revision,
                simc_runtime_revision=simc_runtime_revision,
            )
            envelope = getattr(bundle, "envelope", None)
            envelope_key = _text(getattr(envelope, "content_key", ""))
            if not envelope_key:
                return _blocked("EXACT_SOURCE_AUTHORITY_REQUIRED")
            pairs.append({"slot": slot, "exactAuthorityEnvelopeKey": envelope_key})
    except Exception:
        return _blocked("EXACT_SOURCE_AUTHORITY_REQUIRED")
    if set(seen_slots) != set(expected_slots):
        return _blocked("EXACT_SOURCE_AUTHORITY_REQUIRED")
    registry_revision = _text(exact_registry.get("registryRevision")) if isinstance(exact_registry, Mapping) else ""
    rule_revision = _text(
        binder.get("authorityContext", {}).get("dependencyVector", {}).get("gearRuleRevision")
        if isinstance(binder.get("authorityContext"), Mapping)
        else ""
    )
    try:
        document = seal_exact_template_authority_binding(
            source,
            {
                "gearExactRegistryRevision": registry_revision,
                "gearRuleRevision": rule_revision,
                "resolverRevision": resolver_revision,
                "simcRuntimeRevision": simc_runtime_revision,
                "templateAuthorityIdentity": _text(binder.get("templateAuthorityIdentity")),
                "templateContentHash": template_content_hash,
                "exactAuthorityBySlot": pairs,
            },
        )
    except ExactTemplateAuthorityBindingError:
        return _blocked("EXACT_SOURCE_AUTHORITY_REQUIRED")
    return {
        "status": "verified",
        "document": document,
        "problemCodes": [],
        "problems": [],
    }


__all__ = ("admit_saved_remote_template",)
