"""Bounded dormant candidate evidence orchestration for Task 9."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import parse_qs, urlparse

from .catalog_candidate_evidence_assembly import (
    assemble_catalog_candidate_evidence,
)
from .gear_catalog_http_completeness_matrix import CANONICAL_GEAR_SLOTS
from .gear_catalog_http_completeness_matrix import (
    run_catalog_http_completeness_matrix,
)
from .gear_variant_materialization_matrix import (
    build_gear_variant_materialization_matrix,
)
from .gear_variant_materialization_runner import (
    build_gear_variant_materialization_runner,
)
from .gear_variant_simc_matrix import build_gear_variant_simc_matrix
from .simc_execution_matrix import run_simc_execution_matrix


CATALOG_CANDIDATE_EVIDENCE_RUNNER_SCHEMA_REVISION = (
    "gear-catalog-candidate-evidence-runner-v1"
)

_INPUT_IDENTITY_FIELDS = (
    "manifestRevision",
    "pointerGeneration",
    "gearCatalogRevision",
    "gearExactRegistryRevision",
    "simcRuntimeRevision",
)
_HTTP_IDENTITY_FIELDS = (
    "gearReleaseId",
    "communityReleaseId",
)
_HTTP_MIXED_REVISION_CODES = {
    "CATALOG_HTTP_CANDIDATE_BINDING_REQUIRED",
    "CATALOG_HTTP_MANIFEST_MISMATCH",
    "CATALOG_HTTP_POINTER_GENERATION_MISMATCH",
    "CATALOG_HTTP_GEAR_RELEASE_MISMATCH",
    "CATALOG_HTTP_COMMUNITY_RELEASE_MISMATCH",
    "CATALOG_HTTP_CATALOG_REVISION_MISMATCH",
    "CATALOG_HTTP_EXACT_REGISTRY_MISMATCH",
    "CATALOG_HTTP_SOURCE_CATALOG_INVALID",
}
_READY_STATUSES = {"resolved", "verified"}
_PRESERVED_STATUSES = ("partial", "blocked", "UNVERIFIED", "pending")

RequestJson = Callable[..., Any]
ProfileContextFactory = Callable[..., Any]
PointerReader = Callable[[], Any]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


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


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _problem(code: str, message: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "message": message, **details}


def _identity_value(field: str, value: Any) -> Any:
    if field == "pointerGeneration":
        return _int_or_none(value)
    return _text(value)


def _report_id(payload: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return f"gear-catalog-candidate-evidence-runner:sha256:{digest}"


def _runner_report(
    *,
    status: str,
    expected_identity: Mapping[str, Any],
    problems: list[dict[str, Any]],
    pointer_before: Any,
    pointer_after: Any,
    component_evidence: Mapping[str, Any] | None = None,
    component_statuses: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    report = {
        "schemaRevision": CATALOG_CANDIDATE_EVIDENCE_RUNNER_SCHEMA_REVISION,
        "status": _text(status) or "blocked",
        "problems": _canonical(problems),
        "expectedIdentity": _canonical(expected_identity),
        "pointerBefore": _canonical(pointer_before),
        "pointerAfter": _canonical(pointer_after),
        "componentEvidence": _canonical(component_evidence or {}),
        "componentStatuses": _canonical(component_statuses or {}),
    }
    report["reportId"] = _report_id(report)
    return report


def _preserved_status(*values: Any) -> str:
    for raw in values:
        if raw in _PRESERVED_STATUSES:
            return str(raw)
    return "blocked"


def _validate_expected_identity(expected_identity: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    identity = dict(_mapping(expected_identity))
    problems: list[dict[str, Any]] = []
    for field in _INPUT_IDENTITY_FIELDS + _HTTP_IDENTITY_FIELDS:
        normalized = _identity_value(field, identity.get(field))
        if normalized in (None, ""):
            problems.append(
                _problem(
                    "CATALOG_CANDIDATE_EVIDENCE_EXPECTED_IDENTITY_FIELD_MISSING",
                    f"expected_identity.{field} is required",
                    field=field,
                )
            )
    return identity, problems


def _input_identity_mismatch(
    *,
    component: str,
    field: str,
    expected: Any,
    actual: Any,
) -> dict[str, Any]:
    return _problem(
        "CATALOG_CANDIDATE_EVIDENCE_INPUT_IDENTITY_MISMATCH",
        f"{component}.{field} does not match expected identity",
        component=component,
        field=field,
        expected=expected,
        actual=actual,
    )


def _validate_inputs(
    *,
    catalog: Any,
    exact_registry: Any,
    pointer_before: Any,
    expected_identity: Mapping[str, Any],
) -> list[dict[str, Any]]:
    catalog_mapping = _mapping(catalog)
    exact_mapping = _mapping(exact_registry)
    pointer_mapping = _mapping(pointer_before)
    problems: list[dict[str, Any]] = []

    if not catalog_mapping:
        problems.append(
            _problem(
                "CATALOG_CANDIDATE_EVIDENCE_CATALOG_MISSING",
                "sealed catalog is required",
            )
        )
    if not exact_mapping:
        problems.append(
            _problem(
                "CATALOG_CANDIDATE_EVIDENCE_EXACT_REGISTRY_MISSING",
                "sealed exact registry is required",
            )
        )
    if not pointer_mapping:
        problems.append(
            _problem(
                "CATALOG_CANDIDATE_EVIDENCE_POINTER_MISSING",
                "active pointer snapshot is required",
            )
        )
    if problems:
        return problems

    for field in _INPUT_IDENTITY_FIELDS:
        expected = _identity_value(field, expected_identity.get(field))
        if field == "gearCatalogRevision":
            actual = _identity_value(field, catalog_mapping.get("catalogRevision"))
            if actual != expected:
                problems.append(
                    _input_identity_mismatch(
                        component="catalog",
                        field="catalogRevision",
                        expected=expected,
                        actual=actual,
                    )
                )
        elif field == "gearExactRegistryRevision":
            actual = _identity_value(
                field,
                exact_mapping.get("gearExactRegistryRevision")
                or exact_mapping.get("registryRevision"),
            )
            if actual != expected:
                problems.append(
                    _input_identity_mismatch(
                        component="exact_registry",
                        field="gearExactRegistryRevision",
                        expected=expected,
                        actual=actual,
                    )
                )
        elif field == "manifestRevision":
            actual = _identity_value(field, pointer_mapping.get("manifestRevision"))
            if actual != expected:
                problems.append(
                    _input_identity_mismatch(
                        component="pointer_before",
                        field="manifestRevision",
                        expected=expected,
                        actual=actual,
                    )
                )
        elif field == "pointerGeneration":
            actual = _identity_value(
                field,
                pointer_mapping.get("generation") or pointer_mapping.get("pointerGeneration"),
            )
            if actual != expected:
                problems.append(
                    _input_identity_mismatch(
                        component="pointer_before",
                        field="generation",
                        expected=expected,
                        actual=actual,
                    )
                )
    if not _text(catalog_mapping.get("seasonRevision")):
        problems.append(
            _problem(
                "CATALOG_CANDIDATE_EVIDENCE_CATALOG_SEASON_REVISION_MISSING",
                "sealed catalog must expose seasonRevision",
            )
        )
    return problems


def _recording_request_json(
    request_json: RequestJson,
) -> tuple[RequestJson, list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []

    def wrapped(method: str, path: str, payload: Any, headers: Any):
        result = request_json(method, path, payload, headers)
        if (
            method == "GET"
            and path.startswith("/api/websim/gear?")
            and isinstance(result, tuple)
            and len(result) in {2, 3}
        ):
            payload_value = result[1] if len(result) >= 2 else {}
            query = parse_qs(urlparse(path).query)
            slot_values = query.get("slot") or [""]
            records.append(
                {
                    "classKey": _text((query.get("class") or [""])[0]),
                    "specKey": _text((query.get("spec") or [""])[0]),
                    "requestedSlot": _text(slot_values[0]),
                    "payload": _canonical(payload_value if isinstance(payload_value, Mapping) else {}),
                }
            )
        return result

    return wrapped, records


def _build_profile_context_cache(
    profile_context_factory: ProfileContextFactory,
) -> Callable[[str, str], dict[str, Any]]:
    cache: dict[tuple[str, str], dict[str, Any]] = {}

    def get_profile_context(class_key: str, spec_key: str) -> dict[str, Any]:
        key = (_text(class_key), _text(spec_key))
        if key in cache:
            return cache[key]
        raw = profile_context_factory(class_key=key[0], spec_key=key[1])
        context = dict(_canonical(raw)) if isinstance(raw, Mapping) else {}
        cache[key] = context
        return context

    return get_profile_context


def _catalog_variant_index(catalog: Mapping[str, Any]) -> dict[str, str]:
    index: dict[str, str] = {}
    for raw in catalog.get("browseVariants") or []:
        row = _mapping(raw)
        key = _text(row.get("browseVariantKey"))
        item_id = _text(row.get("itemId"))
        if key and item_id and key not in index:
            index[key] = item_id
    return index


def _selection_intent_for_context(
    *,
    season_revision: str,
    catalog_revision: str,
    class_key: str,
    spec_key: str,
    level: int,
    slot: str,
    item_id: str,
    browse_variant_key: str,
) -> dict[str, Any]:
    return {
        "schemaRevision": "selection-intent-v1",
        "authoredAgainst": {
            "seasonRevision": _text(season_revision),
            "gearCatalogRevision": _text(catalog_revision),
        },
        "eligibilityContext": {
            "classKey": _text(class_key),
            "specKey": _text(spec_key),
            "level": int(level),
        },
        "slots": {
            _text(slot): {
                "itemId": _text(item_id),
                "variantKey": _text(browse_variant_key),
            }
        },
    }


def _extract_relation_contexts(
    *,
    catalog: Mapping[str, Any],
    records: list[dict[str, Any]],
    get_profile_context: Callable[[str, str], dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    season_revision = _text(catalog.get("seasonRevision"))
    catalog_revision = _text(catalog.get("catalogRevision"))
    variant_index = _catalog_variant_index(catalog)
    candidates: dict[str, list[tuple[tuple[str, str, str, str], dict[str, Any]]]] = {}
    problems: list[dict[str, Any]] = []

    for record in records:
        class_key = _text(record.get("classKey"))
        spec_key = _text(record.get("specKey"))
        requested_slot = _text(record.get("requestedSlot"))
        payload = _mapping(record.get("payload"))
        groups = payload.get("replacementCandidates")
        if not isinstance(groups, list):
            continue
        for raw_group in groups:
            group = _mapping(raw_group)
            slot = _text(group.get("slot"))
            if not slot or slot != requested_slot:
                continue
            items = group.get("items") if isinstance(group.get("items"), list) else []
            for raw_item in items:
                item = _mapping(raw_item)
                item_id = _text(item.get("itemId") or item.get("id"))
                variants = item.get("variants") if isinstance(item.get("variants"), list) else []
                for raw_variant in variants:
                    variant = _mapping(raw_variant)
                    browse_variant_key = _text(
                        variant.get("variantKey")
                        or variant.get("key")
                        or variant.get("id")
                    )
                    variant_item_id = _text(variant.get("itemId") or item_id)
                    if not browse_variant_key or not item_id or not variant_item_id:
                        continue
                    if variant_index.get(browse_variant_key) != variant_item_id:
                        continue
                    profile_context = get_profile_context(class_key, spec_key)
                    level = _int_or_none(profile_context.get("level"))
                    if level is None or level <= 0:
                        problems.append(
                            _problem(
                                "CATALOG_CANDIDATE_EVIDENCE_PROFILE_CONTEXT_LEVEL_MISSING",
                                "profile_context_factory must return an explicit positive level",
                                classKey=class_key,
                                specKey=spec_key,
                            )
                        )
                        continue
                    context = {
                        "browseVariantKey": browse_variant_key,
                        "itemId": variant_item_id,
                        "classKey": class_key,
                        "specKey": spec_key,
                        "slot": slot,
                        "selectionIntent": _selection_intent_for_context(
                            season_revision=season_revision,
                            catalog_revision=catalog_revision,
                            class_key=class_key,
                            spec_key=spec_key,
                            level=level,
                            slot=slot,
                            item_id=variant_item_id,
                            browse_variant_key=browse_variant_key,
                        ),
                    }
                    sort_key = (class_key, spec_key, slot, variant_item_id)
                    candidates.setdefault(browse_variant_key, []).append((sort_key, context))

    relation_contexts: list[dict[str, Any]] = []
    for browse_variant_key in sorted(candidates):
        ranked = sorted(
            {
                (
                    key,
                    json.dumps(
                        value,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                )
                for key, value in candidates[browse_variant_key]
            }
        )
        if not ranked:
            continue
        relation_contexts.append(json.loads(ranked[0][1]))
    return relation_contexts, problems


def _relation_contexts_from_override(value: Any) -> list[dict[str, Any]]:
    contexts: list[dict[str, Any]] = []
    for raw in value or []:
        if isinstance(raw, Mapping):
            contexts.append(dict(_canonical(raw)))
    contexts.sort(key=lambda row: _text(row.get("browseVariantKey")))
    return contexts


def _count_failure_family(failure_codes: Mapping[str, Any], predicate: Callable[[str], bool]) -> int:
    count = 0
    for raw_code, raw_value in failure_codes.items():
        code = _text(raw_code)
        value = _int_or_none(raw_value)
        if code and value is not None and predicate(code):
            count += value
    return count


def _catalog_gate_counts(
    *,
    catalog_http_report: Mapping[str, Any],
    materialization_report: Mapping[str, Any],
    relation_contexts: list[dict[str, Any]],
    expected_identity: Mapping[str, Any],
) -> dict[str, Any]:
    failure_codes = (
        catalog_http_report.get("failureCodes")
        if isinstance(catalog_http_report.get("failureCodes"), Mapping)
        else {}
    )
    return {
        "manifestRevision": _text(expected_identity.get("manifestRevision")),
        "pointerGeneration": _int_or_none(expected_identity.get("pointerGeneration")),
        "gearCatalogRevision": _text(expected_identity.get("gearCatalogRevision")),
        "gearExactRegistryRevision": _text(expected_identity.get("gearExactRegistryRevision")),
        "catalog_non_simulatable_count": _int_or_none(
            materialization_report.get("catalog_non_simulatable_count")
        ) or 0,
        "silent_default_fill_count": _int_or_none(
            materialization_report.get("silent_default_fill_count")
        ) or 0,
        "type_unknown_nonportable_visible_count": _count_failure_family(
            failure_codes,
            lambda code: "TYPE_UNKNOWN" in code or "NONPORTABLE" in code,
        ),
        "progression_conflict_count": _count_failure_family(
            failure_codes,
            lambda code: "PROGRESSION" in code,
        ),
        "mixed_revision_count": _count_failure_family(
            failure_codes,
            lambda code: code in _HTTP_MIXED_REVISION_CODES,
        ),
        "missing_provenance_count": _int_or_none(
            materialization_report.get("missing_provenance_count")
        ) or 0,
        "relationContexts": _canonical(relation_contexts),
    }


def _validate_profile_identity(release_context: Mapping[str, Any], expected_identity: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    for field in _INPUT_IDENTITY_FIELDS:
        expected = _identity_value(field, expected_identity.get(field))
        actual = _identity_value(field, release_context.get(field))
        if expected not in (None, "") and actual != expected:
            failures.append("CATALOG_CANDIDATE_EVIDENCE_VARIANT_PROFILE_IDENTITY_MISMATCH")
            break
    return failures


def _build_variant_smoke_callback(
    *,
    request_json: RequestJson,
    simc_executor: Callable[[str], Mapping[str, Any]],
    relation_contexts: list[dict[str, Any]],
    get_profile_context: Callable[[str, str], dict[str, Any]],
    expected_identity: Mapping[str, Any],
) -> Callable[..., dict[str, Any]]:
    indexed = {
        _text(row.get("browseVariantKey")): dict(row)
        for row in relation_contexts
        if _text(row.get("browseVariantKey"))
    }

    def smoke(
        *,
        item_id: Any,
        browse_variant_key: Any,
        class_key: Any,
        spec_key: Any,
        slot: Any,
    ) -> dict[str, Any]:
        key = _text(browse_variant_key)
        entry = {
            "status": "blocked",
            "itemId": _text(item_id),
            "browseVariantKey": key,
            "classKey": _text(class_key),
            "specKey": _text(spec_key),
            "slot": _text(slot),
            "ran": False,
            "timedOut": None,
            "hasDps": None,
            "executionMode": "",
            "simcRuntimeRevision": "",
            "iterations": None,
            "maxTimeSeconds": None,
        }
        context = _mapping(indexed.get(key))
        if (
            _text(context.get("itemId")) != _text(item_id)
            or _text(context.get("classKey")) != _text(class_key)
            or _text(context.get("specKey")) != _text(spec_key)
            or _text(context.get("slot")) != _text(slot)
        ):
            return _canonical(entry)

        profile_context = get_profile_context(_text(class_key), _text(spec_key))
        try:
            http_status, payload, _latency = request_json(
                "POST",
                "/api/websim/profile",
                {
                    "selectionIntent": _canonical(context.get("selectionIntent")),
                    "profileContext": _canonical(profile_context),
                },
                {"Content-Type": "application/json"},
            )
        except Exception:
            return _canonical(entry)

        envelope = _mapping(payload)
        data = _mapping(envelope.get("data"))
        readiness = _mapping(data.get("profileReadiness"))
        profile_text = data.get("profile") if isinstance(data.get("profile"), str) else ""
        release_context = _mapping(envelope.get("releaseContext"))
        status = _text(data.get("status") or envelope.get("status"))
        preserved_status = _preserved_status(
            _text(data.get("status")),
            _text(envelope.get("status")),
            _text(readiness.get("status")),
        )
        if (
            http_status != 200
            or _text(envelope.get("status")) not in _READY_STATUSES
            or _text(data.get("status")) not in _READY_STATUSES
            or _text(readiness.get("status")) != "verified"
            or readiness.get("simcReady") is not True
            or not profile_text.strip()
            or _validate_profile_identity(release_context, expected_identity)
        ):
            entry["status"] = preserved_status if preserved_status != "blocked" else _text(status) or "blocked"
            return _canonical(entry)

        try:
            executed = _mapping(simc_executor(profile_text))
        except Exception:
            return _canonical(entry)
        entry.update(
            {
                "status": _text(executed.get("status")) or "verified",
                "ran": executed.get("ran"),
                "timedOut": executed.get("timedOut"),
                "hasDps": executed.get("hasDps"),
                "executionMode": _text(executed.get("executionMode")),
                "simcRuntimeRevision": _text(executed.get("simcRuntimeRevision")),
                "iterations": _int_or_none(executed.get("iterations")),
                "maxTimeSeconds": _int_or_none(executed.get("maxTimeSeconds")),
            }
        )
        return _canonical(entry)

    return smoke


def run_catalog_candidate_evidence(
    *,
    load_catalog: Callable[[], Any],
    load_exact_registry: Callable[[], Any],
    request_json: RequestJson,
    profile_context_factory: ProfileContextFactory,
    simc_executor: Callable[[str], Mapping[str, Any]],
    pointer_reader: PointerReader,
    expected_specs: Iterable[tuple[str, str]],
    expected_identity: Mapping[str, Any],
    observed_at: str,
    run_catalog_http_matrix: Callable[..., dict[str, Any]] = run_catalog_http_completeness_matrix,
    build_materialization_runner: Callable[..., Any] = build_gear_variant_materialization_runner,
    build_materialization_matrix: Callable[..., dict[str, Any]] = build_gear_variant_materialization_matrix,
    run_simc_execution_matrix: Callable[..., dict[str, Any]] = run_simc_execution_matrix,
    build_variant_simc_matrix: Callable[..., dict[str, Any]] = build_gear_variant_simc_matrix,
    assemble_evidence: Callable[..., dict[str, Any]] = assemble_catalog_candidate_evidence,
    observed_relation_contexts: Any = None,
) -> dict[str, Any]:
    normalized_identity, identity_problems = _validate_expected_identity(expected_identity)
    pointer_before = _canonical(pointer_reader()) if callable(pointer_reader) else {}
    pointer_after = _canonical(pointer_before)
    if identity_problems:
        return _runner_report(
            status="blocked",
            expected_identity=normalized_identity,
            problems=identity_problems,
            pointer_before=pointer_before,
            pointer_after=pointer_after,
        )

    catalog = _canonical(load_catalog())
    exact_registry = _canonical(load_exact_registry())
    input_problems = _validate_inputs(
        catalog=catalog,
        exact_registry=exact_registry,
        pointer_before=pointer_before,
        expected_identity=normalized_identity,
    )
    if input_problems:
        return _runner_report(
            status="blocked",
            expected_identity=normalized_identity,
            problems=input_problems,
            pointer_before=pointer_before,
            pointer_after=pointer_after,
            component_evidence={
                "catalog": catalog,
                "exact_registry_report": exact_registry,
            },
            component_statuses={
                "catalog": _text(_mapping(catalog).get("status")),
                "exact_registry_report": _text(_mapping(exact_registry).get("status")),
            },
        )

    get_profile_context = _build_profile_context_cache(profile_context_factory)
    recording_request_json, records = _recording_request_json(request_json)
    catalog_http_report = _canonical(
        run_catalog_http_matrix(
            recording_request_json,
            catalog=_mapping(catalog),
            expected_specs=list(expected_specs),
            manifest_revision=_text(normalized_identity.get("manifestRevision")),
            pointer_generation=_int_or_none(normalized_identity.get("pointerGeneration")) or 0,
            gear_release_id=_text(normalized_identity.get("gearReleaseId")),
            community_release_id=_text(normalized_identity.get("communityReleaseId")),
            catalog_revision=_text(normalized_identity.get("gearCatalogRevision")),
            exact_registry_revision=_text(normalized_identity.get("gearExactRegistryRevision")),
            observed_at=_text(observed_at),
        )
    )
    if (
        _text(_mapping(catalog_http_report).get("status")) != "pass"
        or (_int_or_none(_mapping(catalog_http_report).get("failureCount")) or 0) != 0
    ):
        pointer_after = _canonical(pointer_reader())
        relation_contexts = _relation_contexts_from_override(observed_relation_contexts)
        counts = _catalog_gate_counts(
            catalog_http_report=_mapping(catalog_http_report),
            materialization_report={},
            relation_contexts=relation_contexts,
            expected_identity=normalized_identity,
        )
        return _runner_report(
            status="blocked",
            expected_identity=normalized_identity,
            problems=[
                _problem(
                    "CATALOG_CANDIDATE_EVIDENCE_HTTP_MATRIX_NOT_PASS",
                    "HTTP completeness matrix must stay pass with zero failures",
                    status=_text(_mapping(catalog_http_report).get("status")) or "missing",
                    failureCount=_int_or_none(_mapping(catalog_http_report).get("failureCount")),
                )
            ],
            pointer_before=pointer_before,
            pointer_after=pointer_after,
            component_evidence={
                "catalog": catalog,
                "catalog_http_report": catalog_http_report,
                "catalog_gate_counts": counts,
                "exact_registry_report": exact_registry,
            },
            component_statuses={
                "catalog": _text(_mapping(catalog).get("status")),
                "catalog_http_report": _text(_mapping(catalog_http_report).get("status")),
                "exact_registry_report": _text(_mapping(exact_registry).get("status")),
            },
        )

    if observed_relation_contexts is not None:
        relation_contexts = _relation_contexts_from_override(observed_relation_contexts)
        relation_problems: list[dict[str, Any]] = []
    else:
        relation_contexts, relation_problems = _extract_relation_contexts(
            catalog=_mapping(catalog),
            records=records,
            get_profile_context=get_profile_context,
        )
    if relation_problems:
        pointer_after = _canonical(pointer_reader())
        return _runner_report(
            status="blocked",
            expected_identity=normalized_identity,
            problems=relation_problems,
            pointer_before=pointer_before,
            pointer_after=pointer_after,
            component_evidence={
                "catalog": catalog,
                "catalog_http_report": catalog_http_report,
                "catalog_gate_counts": {
                    "relationContexts": _canonical(relation_contexts),
                },
                "exact_registry_report": exact_registry,
            },
            component_statuses={
                "catalog": _text(_mapping(catalog).get("status")),
                "catalog_http_report": _text(_mapping(catalog_http_report).get("status")),
                "exact_registry_report": _text(_mapping(exact_registry).get("status")),
            },
        )

    materializer = build_materialization_runner(
        request_json=request_json,
        profile_context_factory=lambda **kwargs: get_profile_context(
            _text(kwargs.get("class_key")), _text(kwargs.get("spec_key"))
        ),
        expected_release_context={
            field: normalized_identity[field]
            for field in _INPUT_IDENTITY_FIELDS
            if field in normalized_identity
        },
    )
    materialization_report = _canonical(
        build_materialization_matrix(
            _mapping(catalog),
            relation_contexts,
            materializer,
        )
    )
    catalog_gate_counts = _catalog_gate_counts(
        catalog_http_report=_mapping(catalog_http_report),
        materialization_report=_mapping(materialization_report),
        relation_contexts=relation_contexts,
        expected_identity=normalized_identity,
    )
    simc_26_14_report = _canonical(
        run_simc_execution_matrix(
            request_json,
            simc_executor,
            expected_specs=list(expected_specs),
            manifest_revision=_text(normalized_identity.get("manifestRevision")),
            pointer_generation=_int_or_none(normalized_identity.get("pointerGeneration")) or 0,
            gear_release_id=_text(normalized_identity.get("gearReleaseId")),
            community_release_id=_text(normalized_identity.get("communityReleaseId")),
            catalog_revision=_text(normalized_identity.get("gearCatalogRevision")),
            exact_registry_revision=_text(normalized_identity.get("gearExactRegistryRevision")),
            simc_runtime_revision=_text(normalized_identity.get("simcRuntimeRevision")),
            observed_at=_text(observed_at),
        )
    )
    variant_smoke_callback = _build_variant_smoke_callback(
        request_json=request_json,
        simc_executor=simc_executor,
        relation_contexts=relation_contexts,
        get_profile_context=get_profile_context,
        expected_identity=normalized_identity,
    )
    variant_simc_report = _canonical(
        build_variant_simc_matrix(
            materialization_report,
            variant_smoke_callback,
        )
    )
    pointer_after = _canonical(pointer_reader())
    return _canonical(
        assemble_evidence(
            catalog=catalog,
            catalog_http_report=catalog_http_report,
            catalog_gate_counts=catalog_gate_counts,
            materialization_report=materialization_report,
            variant_simc_report=variant_simc_report,
            simc_execution_matrix_report=simc_26_14_report,
            exact_registry_report=exact_registry,
            expected_identity={
                field: normalized_identity[field]
                for field in _INPUT_IDENTITY_FIELDS
                if field in normalized_identity
            },
            pointer_before=pointer_before,
            pointer_after=pointer_after,
        )
    )


__all__ = [
    "CATALOG_CANDIDATE_EVIDENCE_RUNNER_SCHEMA_REVISION",
    "run_catalog_candidate_evidence",
]
