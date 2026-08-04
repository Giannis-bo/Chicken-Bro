#!/usr/bin/env python3
"""Pure differential evidence evaluator for governed SimC item effects."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


_MANIFEST_KEYS = frozenset({
    "subjectKind", "subjectKey", "subjectVariantSignature", "simcRuntimeRevision",
    "effectType", "expectedActionTokens", "expectedBuffTokens", "controlSnapshotKey",
    "experimentSnapshotKey", "verifiedAt",
})
_EFFECT_TYPES = frozenset({"on_use", "proc", "buff"})
_SUBJECT_KINDS = frozenset({"item", "gem", "enchant", "embellishment", "crafted_effect", "set_bonus"})


def _text(value: Any) -> str:
    return str(value or "").strip()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _tokens(value: Any) -> list[str] | None:
    if not isinstance(value, list) or not value:
        return None
    values = [_text(item) for item in value]
    return values if all(values) else None


def _unknown(reason: str) -> dict[str, Any]:
    return {"schemaRevision": "simc-item-effect-probe-v1", "status": "unknown", "reason": reason}


def evaluate_effect_probe(manifest: Any, experiment: Any, control: Any) -> dict[str, Any]:
    """Seal only a complete experiment/control token differential."""

    if not isinstance(manifest, Mapping) or set(manifest) != _MANIFEST_KEYS:
        return _unknown("MANIFEST_FIELDS_INVALID")
    if _text(manifest.get("effectType")) not in _EFFECT_TYPES or _text(manifest.get("subjectKind")) not in _SUBJECT_KINDS:
        return _unknown("EFFECT_TYPE_INVALID")
    actions, buffs = _tokens(manifest.get("expectedActionTokens")), _tokens(manifest.get("expectedBuffTokens"))
    if not actions or not buffs or not all(_text(manifest.get(field)) for field in _MANIFEST_KEYS if field not in {"expectedActionTokens", "expectedBuffTokens"}):
        return _unknown("MANIFEST_EVIDENCE_INCOMPLETE")
    if not isinstance(experiment, Mapping) or not isinstance(control, Mapping):
        return _unknown("REPORT_INVALID")
    runtime = _text(manifest["simcRuntimeRevision"])
    if _text(experiment.get("runtimeRevision")) != runtime or _text(control.get("runtimeRevision")) != runtime:
        return _unknown("RUNTIME_MISMATCH")
    if _text(experiment.get("snapshotKey")) != _text(manifest["experimentSnapshotKey"]) or _text(control.get("snapshotKey")) != _text(manifest["controlSnapshotKey"]):
        return _unknown("SNAPSHOT_IDENTITY_MISMATCH")
    if experiment.get("timedOut") or control.get("timedOut"):
        return _unknown("PROBE_TIMEOUT")
    if experiment.get("warnings") or control.get("warnings"):
        return _unknown("ITEM_RESOLUTION_WARNING")
    experiment_actions = set(_tokens(experiment.get("actions")) or [])
    experiment_buffs = set(_tokens(experiment.get("buffs")) or [])
    control_actions = set(_tokens(control.get("actions")) or [])
    control_buffs = set(_tokens(control.get("buffs")) or [])
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
    record["supportRecordKey"] = "simc-item-effect-record:sha256:" + hashlib.sha256(_canonical(record)).hexdigest()
    return record


__all__ = ("evaluate_effect_probe",)
