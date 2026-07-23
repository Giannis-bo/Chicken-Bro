#!/usr/bin/env python3
"""Pure 80-slot TemplateSet construction, LKG, and promotion policy."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Mapping

try:
    from .observed_build_projection import (
        publication_change_kind,
        validate_projection,
    )
    from .observed_build_registry import slot_key
except ImportError:
    from observed_build_projection import publication_change_kind, validate_projection
    from observed_build_registry import slot_key


OBSERVED_BUILD_TEMPLATE_SET_SCHEMA_REVISION = "observed-build-template-set-v1"
OBSERVED_BUILD_TEMPLATE_SET_ID_PREFIX = "template-set:sha256:"
EXPECTED_TEMPLATE_SLOT_COUNT = 80

_ENTRY_STATUSES = {"verified", "stale_lkg", "pending_collection"}
_TEMPLATE_SET_ID_PATTERN = re.compile(r"template-set:sha256:[0-9a-f]{64}")
_PROJECTION_ID_PATTERN = re.compile(r"build-projection:sha256:[0-9a-f]{64}")
_SNAPSHOT_ID_PATTERN = re.compile(r"observed-build:sha256:[0-9a-f]{64}")
_SHA256_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")


def _canonical(value: Any) -> Any:
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    )


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _required_text(value: Any, name: str) -> str:
    normalized = _text(value)
    if not normalized or len(normalized) > 512:
        raise ValueError(f"{name} must be a bounded non-empty string")
    return normalized


def _expected_slots(value: Any) -> tuple[list[dict[str, str]], list[str]]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("expected_slots must be a list")
    slots = [_canonical(slot) for slot in value]
    keys = [slot_key(slot) for slot in slots]
    if len(slots) != EXPECTED_TEMPLATE_SLOT_COUNT:
        raise ValueError(f"expected_slots must contain exactly {EXPECTED_TEMPLATE_SLOT_COUNT} entries")
    if len(set(keys)) != len(keys):
        raise ValueError("expected_slots must contain unique slots")
    ordered = sorted(zip(keys, slots), key=lambda item: item[0])
    return [slot for _, slot in ordered], [key for key, _ in ordered]


def _template_set_identity_payload(template_set: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaRevision": template_set.get("schemaRevision"),
        "expectedSlotKeys": template_set.get("expectedSlotKeys"),
        "dependencyVector": template_set.get("dependencyVector"),
        "entries": template_set.get("entries"),
    }


def _expected_template_set_id(template_set: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        _canonical_bytes(_template_set_identity_payload(template_set))
    ).hexdigest()
    return OBSERVED_BUILD_TEMPLATE_SET_ID_PREFIX + digest


def _entry_problem(projection: Mapping[str, Any] | None) -> dict[str, Any]:
    problems = (
        projection.get("problems")
        if isinstance(projection, Mapping)
        and isinstance(projection.get("problems"), list)
        else []
    )
    first = next((problem for problem in problems if isinstance(problem, dict)), None)
    if first:
        return _canonical(first)
    return {
        "code": "projection_blocked",
        "stage": "projection",
        "message": "Observed build projection is blocked.",
    }


def _pending_entry(slot: dict[str, str], problem: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "slot": _canonical(slot),
        "slotKey": slot_key(slot),
        "status": "pending_collection",
        "snapshotId": "",
        "projectionId": "",
        "problem": _canonical(
            problem
            if isinstance(problem, dict)
            else {
                "code": "pending_collection",
                "stage": "collection",
                "message": "No verified observed build is available for this slot.",
            }
        ),
    }


def _verified_entry(slot: dict[str, str], projection: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "slot": _canonical(slot),
        "slotKey": slot_key(slot),
        "status": "verified",
        "snapshotId": _text(projection.get("snapshotId")),
        "projectionId": _text(projection.get("projectionId")),
        "problem": {},
    }


def _lkg_entry(
    slot: dict[str, str],
    active_entry: Mapping[str, Any],
    blocked_projection: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "slot": _canonical(slot),
        "slotKey": slot_key(slot),
        "status": "stale_lkg",
        "snapshotId": _text(active_entry.get("snapshotId")),
        "projectionId": _text(active_entry.get("projectionId")),
        "problem": _entry_problem(blocked_projection),
    }


def _active_entries(
    active_set: Any,
    expected_keys: list[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if active_set is None:
        return {}, {}
    if not isinstance(active_set, dict):
        raise ValueError("active_set must be an object")
    entries = active_set.get("entries")
    if not isinstance(entries, list):
        raise ValueError("active_set entries must be a list")
    by_key: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("active TemplateSet LKG entries must be objects")
        key = _text(entry.get("slotKey"))
        try:
            actual_key = slot_key(entry.get("slot"))
        except ValueError as error:
            raise ValueError("active TemplateSet LKG must be same-slot") from error
        if key != actual_key or key not in expected_keys or key in by_key:
            raise ValueError("active TemplateSet LKG must be same-slot")
        by_key[key] = _canonical(entry)
    if set(by_key) != set(expected_keys):
        raise ValueError("active TemplateSet LKG must cover the same expected slots")
    return by_key, _canonical(
        active_set.get("dependencyVector")
        if isinstance(active_set.get("dependencyVector"), dict)
        else {}
    )


def _candidate_by_key(
    candidates_by_slot: Any,
    expected_keys: list[str],
    dependency_vector: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if not isinstance(candidates_by_slot, Mapping):
        raise ValueError("candidates_by_slot must be an object")
    normalized: dict[str, dict[str, Any]] = {}
    for raw_key, projection in candidates_by_slot.items():
        key = _text(raw_key)
        if key not in expected_keys:
            raise ValueError(f"candidate slot is not expected: {key}")
        if not isinstance(projection, dict):
            raise ValueError(f"candidate projection must be an object: {key}")
        issues = validate_projection(projection)
        if issues:
            raise ValueError(
                f"candidate projection integrity failed for {key}: "
                + ", ".join(issue["code"] for issue in issues)
            )
        if _text(projection.get("slotKey")) != key:
            raise ValueError(f"candidate projection must match slot: {key}")
        if projection.get("dependencyVector") != dependency_vector:
            raise ValueError(f"candidate projection dependency mismatch for slot: {key}")
        normalized[key] = _canonical(projection)
    return normalized


def _counts(entries: list[dict[str, Any]]) -> dict[str, int]:
    return {
        status: sum(entry.get("status") == status for entry in entries)
        for status in ("verified", "stale_lkg", "pending_collection")
    }


def build_template_set(
    *,
    expected_slots: list[dict[str, Any]],
    candidates_by_slot: Mapping[str, dict[str, Any]],
    active_set: dict[str, Any] | None,
    dependency_vector: dict[str, Any],
    source_run_id: str,
) -> dict[str, Any]:
    """Build a complete candidate set while carrying only same-slot LKG."""

    ordered_slots, expected_keys = _expected_slots(expected_slots)
    normalized_dependencies = _canonical(
        dependency_vector if isinstance(dependency_vector, dict) else {}
    )
    publication_change_kind(normalized_dependencies, normalized_dependencies)
    candidates = _candidate_by_key(
        candidates_by_slot,
        expected_keys,
        normalized_dependencies,
    )
    active_entries, active_dependencies = _active_entries(active_set, expected_keys)
    same_dependencies = not active_set or active_dependencies == normalized_dependencies
    entries: list[dict[str, Any]] = []
    for slot in ordered_slots:
        key = slot_key(slot)
        candidate = candidates.get(key)
        active_entry = active_entries.get(key)
        if candidate and candidate.get("status") == "verified":
            entries.append(_verified_entry(slot, candidate))
            continue
        if candidate:
            if (
                same_dependencies
                and active_entry
                and active_entry.get("status") in {"verified", "stale_lkg"}
                and _SNAPSHOT_ID_PATTERN.fullmatch(_text(active_entry.get("snapshotId")))
                and _PROJECTION_ID_PATTERN.fullmatch(_text(active_entry.get("projectionId")))
            ):
                entries.append(_lkg_entry(slot, active_entry, candidate))
            else:
                entries.append(_pending_entry(slot, _entry_problem(candidate)))
            continue
        if same_dependencies and active_entry:
            entries.append(copy.deepcopy(active_entry))
        else:
            entries.append(_pending_entry(slot))

    template_set = {
        "schemaRevision": OBSERVED_BUILD_TEMPLATE_SET_SCHEMA_REVISION,
        "templateSetId": "",
        "contentHash": "",
        "expectedSlotKeys": expected_keys,
        "dependencyVector": normalized_dependencies,
        "sourceRunId": _required_text(source_run_id, "source_run_id"),
        "entries": entries,
        "counts": _counts(entries),
    }
    template_set["contentHash"] = _sha256(
        _template_set_identity_payload(template_set)
    )
    template_set["templateSetId"] = _expected_template_set_id(template_set)
    issues = validate_template_set(template_set, ordered_slots)
    if issues:
        raise ValueError(
            "TemplateSet integrity failed: "
            + ", ".join(issue["code"] for issue in issues)
        )
    return template_set


def _issue(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def validate_template_set(
    template_set: Any,
    expected_slots: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Validate detached TemplateSet structure and content identity."""

    if not isinstance(template_set, dict):
        return [_issue("TEMPLATE_SET_INVALID", "templateSet", "TemplateSet must be an object.")]
    issues: list[dict[str, str]] = []
    try:
        _, expected_keys = _expected_slots(expected_slots)
    except ValueError as error:
        return [_issue("TEMPLATE_SET_EXPECTED_SLOTS_INVALID", "expectedSlots", str(error))]
    if template_set.get("schemaRevision") != OBSERVED_BUILD_TEMPLATE_SET_SCHEMA_REVISION:
        issues.append(
            _issue(
                "TEMPLATE_SET_SCHEMA_INVALID",
                "templateSet.schemaRevision",
                "TemplateSet schema revision is unsupported.",
            )
        )
    try:
        publication_change_kind(
            template_set.get("dependencyVector"),
            template_set.get("dependencyVector"),
        )
    except ValueError as error:
        issues.append(
            _issue(
                "TEMPLATE_SET_DEPENDENCIES_INVALID",
                "templateSet.dependencyVector",
                str(error),
            )
        )
    try:
        _required_text(template_set.get("sourceRunId"), "sourceRunId")
    except ValueError as error:
        issues.append(
            _issue(
                "TEMPLATE_SET_SOURCE_RUN_INVALID",
                "templateSet.sourceRunId",
                str(error),
            )
        )
    if template_set.get("expectedSlotKeys") != expected_keys:
        issues.append(
            _issue(
                "TEMPLATE_SET_EXPECTED_SLOTS_MISMATCH",
                "templateSet.expectedSlotKeys",
                "TemplateSet expected slot keys do not match the current matrix.",
            )
        )
    entries = template_set.get("entries")
    if not isinstance(entries, list):
        return issues + [
            _issue(
                "TEMPLATE_SET_ENTRIES_INVALID",
                "templateSet.entries",
                "TemplateSet entries must be a list.",
            )
        ]
    seen: set[str] = set()
    actual_keys: list[str] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            issues.append(
                _issue(
                    "TEMPLATE_SET_ENTRY_INVALID",
                    f"templateSet.entries[{index}]",
                    "TemplateSet entry must be an object.",
                )
            )
            continue
        key = _text(entry.get("slotKey"))
        actual_keys.append(key)
        if key in seen:
            issues.append(
                _issue(
                    "TEMPLATE_SET_SLOT_DUPLICATE",
                    f"templateSet.entries[{index}].slotKey",
                    f"TemplateSet slot is duplicated: {key}",
                )
            )
        seen.add(key)
        try:
            actual_key = slot_key(entry.get("slot"))
        except ValueError:
            actual_key = ""
        if actual_key != key:
            issues.append(
                _issue(
                    "TEMPLATE_SET_ENTRY_SLOT_MISMATCH",
                    f"templateSet.entries[{index}].slot",
                    "TemplateSet entry slot does not match its slot key.",
                )
            )
        status = _text(entry.get("status"))
        if status not in _ENTRY_STATUSES:
            issues.append(
                _issue(
                    "TEMPLATE_SET_ENTRY_STATUS_INVALID",
                    f"templateSet.entries[{index}].status",
                    "TemplateSet entry status is invalid.",
                )
            )
            continue
        snapshot_id = _text(entry.get("snapshotId"))
        projection_id = _text(entry.get("projectionId"))
        problem = entry.get("problem")
        problem = problem if isinstance(problem, dict) else {}
        if status in {"verified", "stale_lkg"}:
            if (
                not _SNAPSHOT_ID_PATTERN.fullmatch(snapshot_id)
                or not _PROJECTION_ID_PATTERN.fullmatch(projection_id)
            ):
                issues.append(
                    _issue(
                        "TEMPLATE_SET_ENTRY_REFERENCE_INVALID",
                        f"templateSet.entries[{index}]",
                        "Verified and stale LKG entries require snapshot and projection IDs.",
                    )
                )
        elif snapshot_id or projection_id:
            issues.append(
                _issue(
                    "TEMPLATE_SET_PENDING_REFERENCE_INVALID",
                    f"templateSet.entries[{index}]",
                    "Pending entries cannot reference a snapshot or projection.",
                )
            )
        if status == "verified" and problem:
            issues.append(
                _issue(
                    "TEMPLATE_SET_VERIFIED_PROBLEM_INVALID",
                    f"templateSet.entries[{index}].problem",
                    "Verified entries cannot contain a problem.",
                )
            )
        if status != "verified" and not _text(problem.get("code")):
            issues.append(
                _issue(
                    "TEMPLATE_SET_PROBLEM_MISSING",
                    f"templateSet.entries[{index}].problem",
                    "Stale and pending entries require a structured problem.",
                )
            )
    for key in sorted(set(expected_keys).difference(actual_keys)):
        issues.append(
            _issue(
                "TEMPLATE_SET_SLOT_MISSING",
                "templateSet.entries",
                f"TemplateSet slot is missing: {key}",
            )
        )
    for key in sorted(set(actual_keys).difference(expected_keys)):
        issues.append(
            _issue(
                "TEMPLATE_SET_SLOT_UNEXPECTED",
                "templateSet.entries",
                f"TemplateSet slot is unexpected: {key}",
            )
        )
    if template_set.get("counts") != _counts(
        [entry for entry in entries if isinstance(entry, dict)]
    ):
        issues.append(
            _issue(
                "TEMPLATE_SET_COUNTS_MISMATCH",
                "templateSet.counts",
                "TemplateSet counts do not match its entries.",
            )
        )
    expected_hash = _sha256(_template_set_identity_payload(template_set))
    if (
        not _SHA256_PATTERN.fullmatch(_text(template_set.get("contentHash")))
        or template_set.get("contentHash") != expected_hash
    ):
        issues.append(
            _issue(
                "TEMPLATE_SET_CONTENT_HASH_MISMATCH",
                "templateSet.contentHash",
                "TemplateSet content does not match its hash.",
            )
        )
    expected_id = _expected_template_set_id(template_set)
    if (
        not _TEMPLATE_SET_ID_PATTERN.fullmatch(_text(template_set.get("templateSetId")))
        or template_set.get("templateSetId") != expected_id
    ):
        issues.append(
            _issue(
                "TEMPLATE_SET_ID_MISMATCH",
                "templateSet.templateSetId",
                "TemplateSet content does not match its content-addressed ID.",
            )
        )
    return issues


def promotion_decision(
    *,
    active_set: dict[str, Any] | None,
    candidate_set: dict[str, Any],
) -> dict[str, Any]:
    """Classify one already-built candidate without moving any pointer."""

    expected_slots = (
        [entry.get("slot") for entry in candidate_set.get("entries") or []]
        if isinstance(candidate_set, dict)
        else []
    )
    issues = validate_template_set(candidate_set, expected_slots)
    if issues:
        return {"action": "blocked", "problems": issues}
    if active_set is None:
        return {"action": "controlled_cutover", "reason": "initial_activation"}
    if candidate_set.get("templateSetId") == active_set.get("templateSetId"):
        return {"action": "no_op", "reason": "content_unchanged"}
    change_kind = publication_change_kind(
        active_set.get("dependencyVector"),
        candidate_set.get("dependencyVector"),
    )
    if change_kind == "dependency_cutover":
        return {"action": "controlled_cutover", "reason": "dependency_drift"}
    return {"action": "auto_promote", "reason": "observed_only"}


__all__ = (
    "EXPECTED_TEMPLATE_SLOT_COUNT",
    "OBSERVED_BUILD_TEMPLATE_SET_ID_PREFIX",
    "OBSERVED_BUILD_TEMPLATE_SET_SCHEMA_REVISION",
    "build_template_set",
    "promotion_decision",
    "validate_template_set",
)
