#!/usr/bin/env python3
"""Pure differential evaluator for governed SimC item-effect evidence."""

from __future__ import annotations

try:
    from .gear_canonical_kernel import (
        CanonicalIssue,
        CanonicalResult,
        CanonicalValueError,
        canonical_identity_token,
        canonical_int,
        canonical_mapping,
        canonical_ordered_list,
        canonical_report_token,
    )
    from .simc_item_effect_support import (
        EFFECT_RECORD_SCHEMA_REVISION,
        _canonical_effect_tokens,
        _canonical_snapshot_key,
        _canonical_subject_kind,
        _canonical_timestamp,
        _canonical_variant_signature,
        _canonical_runtime,
        seal_effect_record,
    )
except ImportError:
    from gear_canonical_kernel import (
        CanonicalIssue,
        CanonicalResult,
        CanonicalValueError,
        canonical_identity_token,
        canonical_int,
        canonical_mapping,
        canonical_ordered_list,
        canonical_report_token,
    )
    from simc_item_effect_support import (
        EFFECT_RECORD_SCHEMA_REVISION,
        _canonical_effect_tokens,
        _canonical_snapshot_key,
        _canonical_subject_kind,
        _canonical_timestamp,
        _canonical_variant_signature,
        _canonical_runtime,
        seal_effect_record,
    )


_MANIFEST_KEYS = frozenset({
    "subjectKind", "subjectKey", "subjectVariantSignature",
    "simcRuntimeRevision", "effectType", "expectedActionTokens",
    "expectedBuffTokens", "controlSnapshotKey", "experimentSnapshotKey",
    "verifiedAt",
})
_REPORT_KEYS = frozenset({
    "runtimeRevision", "snapshotKey", "actions", "buffs", "warnings",
    "timedOut", "exitCode", "dps",
})
_EFFECT_TYPES = frozenset({"on_use", "proc", "buff"})
_MAX_WARNINGS = 32
_MAX_WARNING_SEQUENCE_BYTES = 4096


def _blocked(code: str, path: str, recovery_action: str) -> CanonicalResult:
    return CanonicalResult(
        "blocked",
        None,
        (CanonicalIssue(code, path, recovery_action),),
    )


def _warning(value: object, path: str) -> str:
    return canonical_report_token(value, path=path, max_bytes=512)


def _canonical_warnings(value: object, *, path: str) -> list[str]:
    warnings = canonical_ordered_list(
        value, path=path, item_rule=_warning, max_items=_MAX_WARNINGS,
    )
    if sum(len(warning.encode("utf-8")) for warning in warnings) > _MAX_WARNING_SEQUENCE_BYTES:
        raise CanonicalValueError("WARNING_SEQUENCE_BOUNDS", path)
    return list(warnings)


def _validate_manifest(
    value: object,
    *,
    runtime_revision: object,
) -> dict[str, object]:
    raw = canonical_mapping(
        value, path="probe.manifest", exact_keys=_MANIFEST_KEYS,
    )
    runtime = _canonical_runtime(
        runtime_revision, path="probe.runtimeRevision",
    )
    manifest_runtime = _canonical_runtime(
        raw["simcRuntimeRevision"], path="probe.manifest.simcRuntimeRevision",
    )
    if runtime != manifest_runtime:
        raise CanonicalValueError(
            "RUNTIME_MISMATCH", "probe.manifest.simcRuntimeRevision",
        )
    effect_type = canonical_identity_token(
        raw["effectType"], path="probe.manifest.effectType",
    )
    if effect_type not in _EFFECT_TYPES:
        raise CanonicalValueError(
            "INVALID_EFFECT_TYPE", "probe.manifest.effectType",
        )
    experiment_key = _canonical_snapshot_key(
        raw["experimentSnapshotKey"],
        path="probe.manifest.experimentSnapshotKey",
    )
    control_key = _canonical_snapshot_key(
        raw["controlSnapshotKey"],
        path="probe.manifest.controlSnapshotKey",
    )
    if experiment_key == control_key:
        raise CanonicalValueError(
            "SNAPSHOT_CONTROL_NOT_DISTINCT",
            "probe.manifest.controlSnapshotKey",
        )
    rebuilt = {
        "subjectKind": _canonical_subject_kind(
            raw["subjectKind"], path="probe.manifest.subjectKind",
        ),
        "subjectKey": canonical_identity_token(
            raw["subjectKey"], path="probe.manifest.subjectKey",
        ),
        "subjectVariantSignature": _canonical_variant_signature(
            raw["subjectVariantSignature"],
            path="probe.manifest.subjectVariantSignature",
        ),
        "simcRuntimeRevision": manifest_runtime,
        "effectType": effect_type,
        "expectedActionTokens": _canonical_effect_tokens(
            raw["expectedActionTokens"],
            path="probe.manifest.expectedActionTokens",
        ),
        "expectedBuffTokens": _canonical_effect_tokens(
            raw["expectedBuffTokens"],
            path="probe.manifest.expectedBuffTokens",
        ),
        "controlSnapshotKey": control_key,
        "experimentSnapshotKey": experiment_key,
        "verifiedAt": _canonical_timestamp(
            raw["verifiedAt"], path="probe.manifest.verifiedAt",
        ),
    }
    if dict(raw) != rebuilt:
        raise CanonicalValueError(
            "MANIFEST_PAYLOAD_MISMATCH", "probe.manifest",
        )
    return rebuilt


def _validate_report(
    value: object,
    *,
    path: str,
    runtime_revision: str,
    snapshot_key: str,
) -> dict[str, object]:
    raw = canonical_mapping(value, path=path, exact_keys=_REPORT_KEYS)
    runtime = _canonical_runtime(
        raw["runtimeRevision"], path=f"{path}.runtimeRevision",
    )
    if runtime != runtime_revision:
        raise CanonicalValueError("RUNTIME_MISMATCH", f"{path}.runtimeRevision")
    report_snapshot_key = _canonical_snapshot_key(
        raw["snapshotKey"], path=f"{path}.snapshotKey",
    )
    if report_snapshot_key != snapshot_key:
        raise CanonicalValueError(
            "SNAPSHOT_IDENTITY_MISMATCH", f"{path}.snapshotKey",
        )
    if type(raw["timedOut"]) is not bool:
        raise CanonicalValueError("INVALID_BOOLEAN", f"{path}.timedOut")
    exit_code = canonical_int(
        raw["exitCode"], path=f"{path}.exitCode", minimum=-255, maximum=255,
    )
    dps = canonical_int(
        raw["dps"], path=f"{path}.dps", minimum=0, maximum=1_000_000_000,
    )
    rebuilt = {
        "runtimeRevision": runtime,
        "snapshotKey": report_snapshot_key,
        "actions": _canonical_effect_tokens(
            raw["actions"], path=f"{path}.actions", allow_empty=True,
        ),
        "buffs": _canonical_effect_tokens(
            raw["buffs"], path=f"{path}.buffs", allow_empty=True,
        ),
        "warnings": _canonical_warnings(
            raw["warnings"], path=f"{path}.warnings",
        ),
        "timedOut": raw["timedOut"],
        "exitCode": exit_code,
        "dps": dps,
    }
    if dict(raw) != rebuilt:
        raise CanonicalValueError("REPORT_PAYLOAD_MISMATCH", path)
    return rebuilt


def evaluate_effect_probe(
    manifest: object,
    experiment: object,
    control: object,
    *,
    runtime_revision: object,
) -> CanonicalResult:
    """Seal one complete experiment/control differential or block it."""

    try:
        canonical_manifest = _validate_manifest(
            manifest, runtime_revision=runtime_revision,
        )
        runtime = canonical_manifest["simcRuntimeRevision"]
        canonical_experiment = _validate_report(
            experiment,
            path="probe.experiment",
            runtime_revision=runtime,
            snapshot_key=canonical_manifest["experimentSnapshotKey"],
        )
        canonical_control = _validate_report(
            control,
            path="probe.control",
            runtime_revision=runtime,
            snapshot_key=canonical_manifest["controlSnapshotKey"],
        )
    except CanonicalValueError as error:
        return _blocked(
            error.code,
            error.path,
            "Regenerate the local probe inputs without normalization or extra fields.",
        )
    if canonical_experiment["timedOut"] or canonical_control["timedOut"]:
        return _blocked(
            "PROBE_TIMEOUT",
            "probe.report.timedOut",
            "Run both SimC reports to a clean terminal result.",
        )
    if (
        canonical_experiment["exitCode"] != 0
        or canonical_control["exitCode"] != 0
    ):
        return _blocked(
            "PROBE_EXIT_FAILED",
            "probe.report.exitCode",
            "Run both SimC reports to a clean zero exit.",
        )
    if canonical_experiment["warnings"] or canonical_control["warnings"]:
        return _blocked(
            "ITEM_RESOLUTION_WARNING",
            "probe.report.warnings",
            "Resolve every SimC item warning before creating effect evidence.",
        )
    missing_action = next(
        (
            token for token in canonical_manifest["expectedActionTokens"]
            if token not in canonical_experiment["actions"]
        ),
        None,
    )
    missing_buff = next(
        (
            token for token in canonical_manifest["expectedBuffTokens"]
            if token not in canonical_experiment["buffs"]
        ),
        None,
    )
    if missing_action is not None or missing_buff is not None:
        return _blocked(
            "EXPECTED_TOKEN_MISSING",
            "probe.experiment",
            "Capture every governed action and buff token in the experiment.",
        )
    if any(
        token in canonical_control["actions"]
        for token in canonical_manifest["expectedActionTokens"]
    ) or any(
        token in canonical_control["buffs"]
        for token in canonical_manifest["expectedBuffTokens"]
    ):
        return _blocked(
            "CONTROL_TOKEN_PRESENT",
            "probe.control",
            "Use a control snapshot without the governed effect tokens.",
        )
    record_payload = {
        "schemaRevision": EFFECT_RECORD_SCHEMA_REVISION,
        "status": "verified",
        "subjectKind": canonical_manifest["subjectKind"],
        "subjectKey": canonical_manifest["subjectKey"],
        "subjectVariantSignature": canonical_manifest[
            "subjectVariantSignature"
        ],
        "hasDynamicEffect": True,
        "simcRuntimeRevision": runtime,
        "effectType": canonical_manifest["effectType"],
        "expectedActionTokens": canonical_manifest["expectedActionTokens"],
        "expectedBuffTokens": canonical_manifest["expectedBuffTokens"],
        "experimentSnapshotKey": canonical_manifest["experimentSnapshotKey"],
        "controlSnapshotKey": canonical_manifest["controlSnapshotKey"],
        "verifiedAt": canonical_manifest["verifiedAt"],
    }
    result = seal_effect_record(record_payload, runtime_revision=runtime)
    if type(result) is CanonicalResult:
        return result
    return _blocked(
        "SEALED_RECORD_INVALID",
        "probe.record",
        "Regenerate the governed probe evidence.",
    )


__all__ = ("evaluate_effect_probe",)
