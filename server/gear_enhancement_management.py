#!/usr/bin/env python3
"""Pure v2 governance for raw SimC enhancement fields."""

from __future__ import annotations

from typing import Any, Mapping

try:
    from .gear_socket_authority import CAPABILITY_REVISION
except ImportError:
    from gear_socket_authority import CAPABILITY_REVISION


GEM_SIMC_SEQUENCE_FIELDS = ("gem_id", "gem_bonus_id", "gem_ilevel")
ENHANCEMENT_SIMC_FIELDS = (
    *GEM_SIMC_SEQUENCE_FIELDS,
    "enchant_id",
    "embellishment",
)
ENHANCEMENT_MANAGEMENT_SCHEMA_REVISION = "gear-enhancement-management-v1"
ENHANCEMENT_MANAGEMENT_CLASSIFICATIONS = frozenset({
    "editor_managed",
    "source_only",
    "unresolved_drop",
})


def _raw_field_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def present_enhancement_simc_fields(simc_options: Any) -> set[str]:
    """Return every present governed field, including malformed non-strings."""

    options = simc_options if isinstance(simc_options, Mapping) else {}
    return {
        field
        for field in ENHANCEMENT_SIMC_FIELDS
        if _raw_field_present(options.get(field))
    }


def validated_enhancement_management_fields(
    simc_options: Any,
    management: Any,
    capability_revision: Any,
) -> dict[str, str]:
    """Validate the complete release-owned v2 marker without coercion.

    Any mismatch invalidates the whole marker.  Callers can then drop all raw
    governed fields rather than partially trusting forged or stale metadata.
    """

    if capability_revision != CAPABILITY_REVISION or not isinstance(management, Mapping):
        return {}
    if management.get("schemaRevision") != ENHANCEMENT_MANAGEMENT_SCHEMA_REVISION:
        return {}
    if management.get("authorityRevision") != CAPABILITY_REVISION:
        return {}
    fields = management.get("fields")
    if not isinstance(fields, Mapping):
        return {}
    expected_fields = present_enhancement_simc_fields(simc_options)
    if set(fields) != expected_fields:
        return {}
    if any(
        not isinstance(value, str)
        or value not in ENHANCEMENT_MANAGEMENT_CLASSIFICATIONS
        for value in fields.values()
    ):
        return {}
    if any(fields.get(field) == "source_only" for field in GEM_SIMC_SEQUENCE_FIELDS):
        return {}
    return {
        field: fields[field]
        for field in ENHANCEMENT_SIMC_FIELDS
        if field in fields
    }


def project_validated_enhancement_management(
    simc_options: Any,
    management: Any,
    capability_revision: Any,
) -> dict[str, Any] | None:
    fields = validated_enhancement_management_fields(
        simc_options,
        management,
        capability_revision,
    )
    if not fields:
        return None
    return {
        "schemaRevision": ENHANCEMENT_MANAGEMENT_SCHEMA_REVISION,
        "authorityRevision": CAPABILITY_REVISION,
        "fields": fields,
    }


def seal_enhancement_management(
    simc_options: Any,
    classifications: Any,
    capability_revision: Any,
) -> dict[str, Any] | None:
    """Build a release-owned marker only when it exactly governs raw fields."""

    candidate = {
        "schemaRevision": ENHANCEMENT_MANAGEMENT_SCHEMA_REVISION,
        "authorityRevision": CAPABILITY_REVISION,
        "fields": dict(classifications) if isinstance(classifications, Mapping) else {},
    }
    return project_validated_enhancement_management(
        simc_options,
        candidate,
        capability_revision,
    )
