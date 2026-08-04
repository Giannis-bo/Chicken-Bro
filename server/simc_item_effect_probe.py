#!/usr/bin/env python3
"""Pure differential evidence evaluator for governed SimC item effects."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any, Mapping

try:
    from .simc_item_effect_support import (
        seal_effect_record,
        valid_effect_tokens,
        valid_runtime_revision,
        validate_effect_record,
    )
except ImportError:
    from simc_item_effect_support import (
        seal_effect_record,
        valid_effect_tokens,
        valid_runtime_revision,
        validate_effect_record,
    )


_MANIFEST_KEYS = frozenset({
    "subjectKind", "subjectKey", "subjectVariantSignature", "simcRuntimeRevision",
    "effectType", "expectedActionTokens", "expectedBuffTokens", "controlSnapshotKey",
    "experimentSnapshotKey", "verifiedAt",
})
_EFFECT_TYPES = frozenset({"on_use", "proc", "buff"})
_SUBJECT_KINDS = frozenset({"item", "gem", "enchant", "embellishment", "crafted_effect", "set_bonus"})
_SNAPSHOT_KEY_PATTERN = re.compile(r"^simulation-snapshot:sha256:[0-9a-f]{64}$")
_VARIANT_PATTERN = re.compile(r"^(?:exact|[a-z_]+-variant):sha256:[0-9a-f]{64}$")


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _tokens(value: Any) -> list[str] | None:
    if not valid_effect_tokens(value):
        return None
    return list(value)


def _report_tokens(value: Any) -> list[str] | None:
    return list(value) if valid_effect_tokens(value, allow_empty=True) else None


def _warnings(value: Any) -> list[str] | None:
    if not isinstance(value, list) or len(value) > 32:
        return None
    total_bytes = 0
    for warning in value:
        if not isinstance(warning, str) or warning != warning.strip() or not warning:
            return None
        encoded = warning.encode("utf-8")
        if len(encoded) > 512 or any(ord(character) < 32 or ord(character) == 127 for character in warning):
            return None
        total_bytes += len(encoded)
    return list(value) if total_bytes <= 4096 else None


def _canonical_text(value: Any, *, max_bytes: int = 256) -> str | None:
    if not isinstance(value, str) or not value or value != value.strip():
        return None
    if len(value.encode("utf-8")) > max_bytes:
        return None
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        return None
    return value


def _timestamp(value: Any) -> bool:
    text = _canonical_text(value, max_bytes=64)
    if text is None or not text.endswith("Z"):
        return False
    try:
        return datetime.fromisoformat(text[:-1] + "+00:00").tzinfo is not None
    except ValueError:
        return False


def _unknown(reason: str) -> dict[str, Any]:
    return {"schemaRevision": "simc-item-effect-probe-v1", "status": "unknown", "reason": reason}


def evaluate_effect_probe(manifest: Any, experiment: Any, control: Any) -> dict[str, Any]:
    """Seal only a complete experiment/control token differential."""

    if not isinstance(manifest, Mapping) or set(manifest) != _MANIFEST_KEYS:
        return _unknown("MANIFEST_FIELDS_INVALID")
    if manifest.get("effectType") not in _EFFECT_TYPES or manifest.get("subjectKind") not in _SUBJECT_KINDS:
        return _unknown("EFFECT_TYPE_INVALID")
    actions, buffs = _tokens(manifest.get("expectedActionTokens")), _tokens(manifest.get("expectedBuffTokens"))
    if not actions or not buffs or not all(_canonical_text(manifest.get(field)) is not None for field in _MANIFEST_KEYS if field not in {"expectedActionTokens", "expectedBuffTokens"}):
        return _unknown("MANIFEST_EVIDENCE_INCOMPLETE")
    if not valid_runtime_revision(manifest.get("simcRuntimeRevision")):
        return _unknown("RUNTIME_INVALID")
    if not _VARIANT_PATTERN.fullmatch(manifest["subjectVariantSignature"]) or not _SNAPSHOT_KEY_PATTERN.fullmatch(manifest["experimentSnapshotKey"]) or not _SNAPSHOT_KEY_PATTERN.fullmatch(manifest["controlSnapshotKey"]) or not _timestamp(manifest.get("verifiedAt")):
        return _unknown("MANIFEST_SEAL_INVALID")
    if not isinstance(experiment, Mapping) or not isinstance(control, Mapping):
        return _unknown("REPORT_INVALID")
    if manifest["experimentSnapshotKey"] == manifest["controlSnapshotKey"]:
        return _unknown("SNAPSHOT_CONTROL_NOT_DISTINCT")
    runtime = manifest["simcRuntimeRevision"]
    if experiment.get("runtimeRevision") != runtime or control.get("runtimeRevision") != runtime:
        return _unknown("RUNTIME_MISMATCH")
    if experiment.get("snapshotKey") != manifest["experimentSnapshotKey"] or control.get("snapshotKey") != manifest["controlSnapshotKey"]:
        return _unknown("SNAPSHOT_IDENTITY_MISMATCH")
    if experiment.get("timedOut") is not False or control.get("timedOut") is not False:
        return _unknown("PROBE_TIMEOUT")
    if type(experiment.get("exitCode")) is not int or type(control.get("exitCode")) is not int or experiment.get("exitCode") != 0 or control.get("exitCode") != 0:
        return _unknown("PROBE_EXIT_FAILED")
    experiment_warnings = _warnings(experiment.get("warnings"))
    control_warnings = _warnings(control.get("warnings"))
    if experiment_warnings is None or control_warnings is None:
        return _unknown("REPORT_INVALID")
    if experiment_warnings or control_warnings:
        return _unknown("ITEM_RESOLUTION_WARNING")
    report_sequences = (
        _report_tokens(experiment.get("actions")),
        _report_tokens(experiment.get("buffs")),
        _report_tokens(control.get("actions")),
        _report_tokens(control.get("buffs")),
    )
    if any(sequence is None for sequence in report_sequences):
        return _unknown("REPORT_INVALID")
    experiment_actions, experiment_buffs, control_actions, control_buffs = (
        set(sequence) for sequence in report_sequences
    )
    if not set(actions) <= experiment_actions or not set(buffs) <= experiment_buffs:
        return _unknown("EXPECTED_TOKEN_MISSING")
    if set(actions) & control_actions or set(buffs) & control_buffs:
        return _unknown("CONTROL_TOKEN_PRESENT")
    record = {
        "schemaRevision": "simc-item-effect-record-v1", "status": "verified",
        "subjectKind": manifest["subjectKind"], "subjectKey": manifest["subjectKey"],
        "subjectVariantSignature": manifest["subjectVariantSignature"],
        "hasDynamicEffect": True,
        "simcRuntimeRevision": runtime, "effectType": manifest["effectType"],
        "expectedActionTokens": actions, "expectedBuffTokens": buffs,
        "experimentSnapshotKey": manifest["experimentSnapshotKey"], "controlSnapshotKey": manifest["controlSnapshotKey"],
        "verifiedAt": manifest["verifiedAt"],
    }
    sealed = seal_effect_record(record)
    return sealed if validate_effect_record(sealed, runtime_revision=runtime) else _unknown("SEALED_RECORD_INVALID")


__all__ = ("evaluate_effect_probe",)
