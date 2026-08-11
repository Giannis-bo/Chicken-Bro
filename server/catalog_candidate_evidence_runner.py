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
_EXPECTED_SPEC_COUNT = 40

RequestJson = Callable[..., Any]
ProfileContextFactory = Callable[..., Any]
SelectionIntentFactory = Callable[..., Any]
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


def _exception_problem(code: str, component: str, error: BaseException) -> dict[str, Any]:
    return _problem(
        code,
        f"{component} raised an exception",
        component=component,
        exceptionType=type(error).__name__,
    )


def _exception_component(code: str) -> dict[str, Any]:
    return {
        "status": "blocked",
        "failureCodes": [code],
    }


def _safe_pointer_snapshot(
    pointer_reader: PointerReader,
    fallback: Any,
) -> tuple[Any, dict[str, Any] | None]:
    if not callable(pointer_reader):
        return _canonical(fallback), _problem(
            "CATALOG_CANDIDATE_EVIDENCE_POINTER_READER_MISSING",
            "pointer_reader must be callable",
            component="pointer",
        )
    try:
        return _canonical(pointer_reader()), None
    except Exception as error:
        return _canonical(fallback), _exception_problem(
            "CATALOG_CANDIDATE_EVIDENCE_POINTER_READER_EXCEPTION",
            "pointer_reader",
            error,
        )


def _canonical_expected_specs(
    expected_specs: Iterable[tuple[str, str]],
) -> tuple[list[tuple[str, str]], list[dict[str, Any]]]:
    problems: list[dict[str, Any]] = []
    canonical: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    try:
        raw_specs = list(expected_specs)
    except Exception as error:
        return [], [
            _exception_problem(
                "CATALOG_CANDIDATE_EVIDENCE_EXPECTED_SPECS_EXCEPTION",
                "expected_specs",
                error,
            )
        ]

    for index, raw_pair in enumerate(raw_specs):
        if not isinstance(raw_pair, (tuple, list)) or len(raw_pair) != 2:
            problems.append(
                _problem(
                    "CATALOG_CANDIDATE_EVIDENCE_EXPECTED_SPECS_PAIR_INVALID",
                    "expected_specs must contain two-field class/spec pairs",
                    index=index,
                )
            )
            continue
        class_key = _text(raw_pair[0])
        spec_key = _text(raw_pair[1])
        if not class_key or not spec_key:
            problems.append(
                _problem(
                    "CATALOG_CANDIDATE_EVIDENCE_EXPECTED_SPECS_PAIR_INVALID",
                    "expected_specs class/spec fields must be non-empty",
                    index=index,
                )
            )
            continue
        pair = (class_key, spec_key)
        if pair in seen:
            problems.append(
                _problem(
                    "CATALOG_CANDIDATE_EVIDENCE_EXPECTED_SPECS_DUPLICATE",
                    "expected_specs must contain unique class/spec pairs",
                    classKey=class_key,
                    specKey=spec_key,
                )
            )
            continue
        seen.add(pair)
        canonical.append(pair)

    canonical.sort()
    if len(canonical) != _EXPECTED_SPEC_COUNT:
        problems.append(
            _problem(
                "CATALOG_CANDIDATE_EVIDENCE_EXPECTED_SPECS_COUNT_INVALID",
                "expected_specs must contain exactly 40 unique non-empty class/spec pairs",
                expectedCount=_EXPECTED_SPEC_COUNT,
                actualCount=len(canonical),
            )
        )
    return canonical, problems


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


def _validate_active_pointer_snapshot(
    pointer_mapping: Mapping[str, Any],
) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []
    for field, code in (
        (
            "manifestRevision",
            "CATALOG_CANDIDATE_EVIDENCE_POINTER_ACTIVE_MANIFEST_INVALID",
        ),
        (
            "gearCatalogRevision",
            "CATALOG_CANDIDATE_EVIDENCE_POINTER_ACTIVE_CATALOG_REVISION_INVALID",
        ),
        (
            "gearExactRegistryRevision",
            "CATALOG_CANDIDATE_EVIDENCE_POINTER_ACTIVE_EXACT_REVISION_INVALID",
        ),
    ):
        value = pointer_mapping.get(field)
        if not isinstance(value, str) or not value.strip():
            problems.append(
                _problem(
                    code,
                    f"active pointer {field} must be a non-empty string",
                    component="pointer_before",
                    field=field,
                )
            )

    generation_value = pointer_mapping.get("generation")
    if generation_value is None:
        generation_value = pointer_mapping.get("pointerGeneration")
    if _int_or_none(generation_value) is None:
        problems.append(
            _problem(
                "CATALOG_CANDIDATE_EVIDENCE_POINTER_ACTIVE_GENERATION_INVALID",
                "active pointer generation must be an integer",
                component="pointer_before",
                field="generation",
            )
        )
    return problems


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

    pointer_structure_problems = _validate_active_pointer_snapshot(pointer_mapping)
    if pointer_structure_problems:
        return pointer_structure_problems

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
            # The active pointer is intentionally allowed to remain on the
            # retail Manifest while candidate APIs expose a preview Manifest.
            # Its own structure is validated above; candidate identity is
            # checked on HTTP/Resolver/Profile component evidence instead.
            continue
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


def _selection_intent_for_relation_context(
    *,
    season_revision: str,
    catalog_revision: str,
    class_key: str,
    spec_key: str,
    level: int,
    slot: str,
    item_id: str,
    browse_variant_key: str,
    selection_intent_factory: SelectionIntentFactory | None = None,
    hand_pair_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a full-loadout intent while replacing only one BrowseVariant.

    Resolver/Profile readiness is intentionally loadout-scoped.  A single
    BrowseVariant relation therefore needs a complete, same-candidate base
    intent.  Exact enhancement selections from that base are removed so an
    observed Exact template is never mixed with a candidate Browse choice.
    """

    if not callable(selection_intent_factory):
        return _selection_intent_for_context(
            season_revision=season_revision,
            catalog_revision=catalog_revision,
            class_key=class_key,
            spec_key=spec_key,
            level=level,
            slot=slot,
            item_id=item_id,
            browse_variant_key=browse_variant_key,
        )

    base = _mapping(
        selection_intent_factory(
            class_key=_text(class_key),
            spec_key=_text(spec_key),
        )
    )
    base_slots = base.get("slots")
    if not isinstance(base_slots, Mapping) or not base_slots:
        raise ValueError("selection_intent_factory must return a non-empty slots mapping")

    base_eligibility = _mapping(base.get("eligibilityContext"))
    for field, expected in (
        ("classKey", _text(class_key)),
        ("specKey", _text(spec_key)),
    ):
        actual = _text(base_eligibility.get(field))
        if actual and actual != expected:
            raise ValueError(
                f"selection_intent_factory eligibility {field} does not match relation context"
            )

    slots: dict[str, dict[str, str]] = {}
    for raw_slot, raw_selection in sorted(base_slots.items()):
        base_slot = _text(raw_slot)
        selection = _mapping(raw_selection)
        base_item_id = _text(selection.get("itemId"))
        base_variant_key = _text(selection.get("variantKey"))
        if not base_slot or not base_item_id or not base_variant_key:
            raise ValueError(
                "selection_intent_factory returned a slot without itemId/variantKey"
            )
        # Keep only identity fields.  This deliberately removes exact option
        # IDs before the candidate BrowseVariant is sent to Resolver/Profile.
        slots[base_slot] = {
            "itemId": base_item_id,
            "variantKey": base_variant_key,
        }
    slots[_text(slot)] = {
        "itemId": _text(item_id),
        "variantKey": _text(browse_variant_key),
    }
    pair_context = _mapping(hand_pair_context)
    for raw_slot, raw_companion in pair_context.items():
        companion_slot = _text(raw_slot)
        if not companion_slot or companion_slot == _text(slot):
            continue
        if raw_companion is None:
            slots.pop(companion_slot, None)
            continue
        companion = _mapping(raw_companion)
        companion_item_id = _text(companion.get("itemId"))
        companion_variant_key = _text(companion.get("variantKey"))
        if companion_item_id and companion_variant_key:
            slots[companion_slot] = {
                "itemId": companion_item_id,
                "variantKey": companion_variant_key,
            }

    return {
        "schemaRevision": _text(base.get("schemaRevision")) or "selection-intent-v1",
        "authoredAgainst": {
            "seasonRevision": _text(season_revision),
            "gearCatalogRevision": _text(catalog_revision),
        },
        "eligibilityContext": {
            "classKey": _text(class_key),
            "specKey": _text(spec_key),
            "level": int(level),
        },
        "slots": slots,
    }


def _extract_relation_contexts(
    *,
    catalog: Mapping[str, Any],
    records: list[dict[str, Any]],
    get_profile_context: Callable[[str, str], dict[str, Any]],
    selection_intent_factory: SelectionIntentFactory | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    season_revision = _text(catalog.get("seasonRevision"))
    catalog_revision = _text(catalog.get("catalogRevision"))
    variant_index = _catalog_variant_index(catalog)
    candidates: dict[str, list[tuple[tuple[str, str, str, str], dict[str, Any]]]] = {}
    problems: list[dict[str, Any]] = []
    profile_context_exception_keys: set[tuple[str, str]] = set()
    selection_intent_exception_keys: set[tuple[str, str]] = set()

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
                    try:
                        profile_context = get_profile_context(class_key, spec_key)
                    except Exception as error:
                        exception_key = (class_key, spec_key)
                        if exception_key not in profile_context_exception_keys:
                            profile_context_exception_keys.add(exception_key)
                            problems.append(
                                _exception_problem(
                                    "CATALOG_CANDIDATE_EVIDENCE_PROFILE_CONTEXT_FACTORY_EXCEPTION",
                                    "profile_context_factory",
                                    error,
                                )
                                | {
                                    "classKey": class_key,
                                    "specKey": spec_key,
                                }
                            )
                        continue
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
                        "handedness": _text(
                            item.get("handedness")
                            or variant.get("handedness")
                        ),
                        "profileLevel": level,
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

    one_hand_main_by_class_spec: dict[
        tuple[str, str], tuple[tuple[str, str], dict[str, str]]
    ] = {}
    off_hand_by_class_spec: dict[
        tuple[str, str], tuple[tuple[str, str], dict[str, str]]
    ] = {}
    for raw_candidates in candidates.values():
        for _sort_key, context in raw_candidates:
            class_spec = (
                _text(context.get("classKey")),
                _text(context.get("specKey")),
            )
            candidate = {
                "itemId": _text(context.get("itemId")),
                "variantKey": _text(context.get("browseVariantKey")),
            }
            candidate_rank = (
                candidate["variantKey"],
                candidate["itemId"],
            )
            handedness = _text(context.get("handedness")).lower().replace("-", "_")
            if (
                _text(context.get("slot")) == "main_hand"
                and handedness in {"one_hand", "onehand"}
            ):
                current = one_hand_main_by_class_spec.get(class_spec)
                if current is None or candidate_rank < current[0]:
                    one_hand_main_by_class_spec[class_spec] = (
                        candidate_rank,
                        candidate,
                    )
            elif (
                _text(context.get("slot")) == "off_hand"
                and handedness in {"one_hand", "onehand", "off_hand", "offhand"}
            ):
                current = off_hand_by_class_spec.get(class_spec)
                if current is None or candidate_rank < current[0]:
                    off_hand_by_class_spec[class_spec] = (
                        candidate_rank,
                        candidate,
                    )

    for context in relation_contexts:
        class_key = _text(context.get("classKey"))
        spec_key = _text(context.get("specKey"))
        level = _int_or_none(context.get("profileLevel"))
        slot = _text(context.get("slot"))
        item_id = _text(context.get("itemId"))
        browse_variant_key = _text(context.get("browseVariantKey"))
        handedness = _text(context.get("handedness")).lower().replace("-", "_")
        hand_pair_context: dict[str, Any] = {}
        class_spec = (class_key, spec_key)
        if slot == "main_hand" and handedness in {"two_hand", "twohand"}:
            hand_pair_context["off_hand"] = None
        elif (
            slot == "main_hand"
            and handedness in {"one_hand", "onehand"}
            and class_spec in off_hand_by_class_spec
        ):
            hand_pair_context["off_hand"] = off_hand_by_class_spec[class_spec][1]
        elif slot == "off_hand" and class_spec in one_hand_main_by_class_spec:
            hand_pair_context["main_hand"] = one_hand_main_by_class_spec[class_spec][1]
        try:
            context["selectionIntent"] = _selection_intent_for_relation_context(
                season_revision=season_revision,
                catalog_revision=catalog_revision,
                class_key=class_key,
                spec_key=spec_key,
                level=level or 0,
                slot=slot,
                item_id=item_id,
                browse_variant_key=browse_variant_key,
                selection_intent_factory=selection_intent_factory,
                hand_pair_context=hand_pair_context,
            )
        except Exception as error:
            exception_key = (class_key, spec_key)
            if exception_key not in selection_intent_exception_keys:
                selection_intent_exception_keys.add(exception_key)
                problems.append(
                    _exception_problem(
                        "CATALOG_CANDIDATE_EVIDENCE_SELECTION_INTENT_FACTORY_EXCEPTION",
                        "selection_intent_factory",
                        error,
                    )
                    | {
                        "classKey": class_key,
                        "specKey": spec_key,
                    }
                )
            continue
        context.pop("profileLevel", None)
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
            "failureCodes": [],
        }

        def blocked(code: str) -> dict[str, Any]:
            entry["status"] = "blocked"
            entry["failureCodes"] = sorted(
                set(
                    _text(value)
                    for value in list(entry.get("failureCodes") or []) + [code]
                    if _text(value)
                )
            )
            return _canonical(entry)

        context = _mapping(indexed.get(key))
        if (
            _text(context.get("itemId")) != _text(item_id)
            or _text(context.get("classKey")) != _text(class_key)
            or _text(context.get("specKey")) != _text(spec_key)
            or _text(context.get("slot")) != _text(slot)
        ):
            return blocked("CATALOG_CANDIDATE_EVIDENCE_VARIANT_RELATION_CONTEXT_MISMATCH")

        try:
            profile_context = get_profile_context(_text(class_key), _text(spec_key))
        except Exception:
            return blocked(
                "CATALOG_CANDIDATE_EVIDENCE_VARIANT_PROFILE_CONTEXT_FACTORY_EXCEPTION"
            )
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
            return blocked("CATALOG_CANDIDATE_EVIDENCE_VARIANT_PROFILE_REQUEST_EXCEPTION")

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
            return blocked("CATALOG_CANDIDATE_EVIDENCE_VARIANT_PROFILE_NOT_READY")

        try:
            executed = _mapping(simc_executor(profile_text))
        except Exception:
            return blocked("CATALOG_CANDIDATE_EVIDENCE_VARIANT_SIMC_EXECUTOR_EXCEPTION")
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
        expected_runtime_revision = _text(expected_identity.get("simcRuntimeRevision"))
        actual_runtime_revision = _text(executed.get("simcRuntimeRevision"))
        if actual_runtime_revision != expected_runtime_revision:
            entry["expectedSimcRuntimeRevision"] = expected_runtime_revision
            entry["failureCodes"] = [
                "CATALOG_CANDIDATE_EVIDENCE_VARIANT_SIMC_RUNTIME_REVISION_MISMATCH"
            ]
            entry["status"] = "blocked"
        else:
            entry["failureCodes"] = []
        return _canonical(entry)

    return smoke


def run_catalog_candidate_evidence(
    *,
    load_catalog: Callable[[], Any],
    load_exact_registry: Callable[[], Any],
    request_json: RequestJson,
    profile_context_factory: ProfileContextFactory,
    selection_intent_factory: SelectionIntentFactory | None = None,
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
    pointer_before, pointer_before_problem = _safe_pointer_snapshot(pointer_reader, {})
    pointer_after = _canonical(pointer_before)
    if pointer_before_problem:
        return _runner_report(
            status="blocked",
            expected_identity=normalized_identity,
            problems=[pointer_before_problem],
            pointer_before=pointer_before,
            pointer_after=pointer_after,
            component_evidence={
                "pointer": _exception_component(pointer_before_problem["code"]),
            },
            component_statuses={"pointer": "blocked"},
        )

    def blocked_report(
        problems: list[dict[str, Any]],
        *,
        component_evidence: Mapping[str, Any] | None = None,
        component_statuses: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        stable_after, pointer_after_problem = _safe_pointer_snapshot(
            pointer_reader,
            pointer_before,
        )
        all_problems = list(problems)
        evidence = dict(component_evidence or {})
        statuses = dict(component_statuses or {})
        if pointer_after_problem:
            all_problems.append(pointer_after_problem)
            evidence["pointer"] = _exception_component(pointer_after_problem["code"])
            statuses["pointer"] = "blocked"
        return _runner_report(
            status="blocked",
            expected_identity=normalized_identity,
            problems=all_problems,
            pointer_before=pointer_before,
            pointer_after=stable_after,
            component_evidence=evidence,
            component_statuses=statuses,
        )

    if identity_problems:
        return blocked_report(
            identity_problems,
        )

    canonical_expected_specs, expected_specs_problems = _canonical_expected_specs(
        expected_specs
    )
    if expected_specs_problems:
        return blocked_report(
            expected_specs_problems,
            component_evidence={
                "expectedSpecs": canonical_expected_specs,
            },
            component_statuses={"expectedSpecs": "blocked"},
        )

    try:
        catalog = _canonical(load_catalog())
    except Exception as error:
        code = "CATALOG_CANDIDATE_EVIDENCE_CATALOG_LOADER_EXCEPTION"
        return blocked_report(
            [_exception_problem(code, "load_catalog", error)],
            component_evidence={
                "catalog": _exception_component(code),
                "exact_registry_report": {},
            },
            component_statuses={
                "catalog": "blocked",
                "exact_registry_report": "",
            },
        )

    try:
        exact_registry = _canonical(load_exact_registry())
    except Exception as error:
        code = "CATALOG_CANDIDATE_EVIDENCE_EXACT_REGISTRY_LOADER_EXCEPTION"
        return blocked_report(
            [_exception_problem(code, "load_exact_registry", error)],
            component_evidence={
                "catalog": catalog,
                "exact_registry_report": _exception_component(code),
            },
            component_statuses={
                "catalog": _text(_mapping(catalog).get("status")),
                "exact_registry_report": "blocked",
            },
        )

    input_problems = _validate_inputs(
        catalog=catalog,
        exact_registry=exact_registry,
        pointer_before=pointer_before,
        expected_identity=normalized_identity,
    )
    if input_problems:
        return blocked_report(
            input_problems,
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
    try:
        catalog_http_report = _canonical(
            run_catalog_http_matrix(
                recording_request_json,
                catalog=_mapping(catalog),
                expected_specs=canonical_expected_specs,
                manifest_revision=_text(normalized_identity.get("manifestRevision")),
                pointer_generation=_int_or_none(normalized_identity.get("pointerGeneration")) or 0,
                gear_release_id=_text(normalized_identity.get("gearReleaseId")),
                community_release_id=_text(normalized_identity.get("communityReleaseId")),
                catalog_revision=_text(normalized_identity.get("gearCatalogRevision")),
                exact_registry_revision=_text(normalized_identity.get("gearExactRegistryRevision")),
                observed_at=_text(observed_at),
            )
        )
    except Exception as error:
        code = "CATALOG_CANDIDATE_EVIDENCE_HTTP_MATRIX_EXCEPTION"
        catalog_http_report = _exception_component(code)
        return blocked_report(
            [_exception_problem(code, "run_catalog_http_matrix", error)],
            component_evidence={
                "catalog": catalog,
                "catalog_http_report": catalog_http_report,
                "expectedSpecs": canonical_expected_specs,
                "exact_registry_report": exact_registry,
            },
            component_statuses={
                "catalog": _text(_mapping(catalog).get("status")),
                "catalog_http_report": "blocked",
                "exact_registry_report": _text(_mapping(exact_registry).get("status")),
            },
        )
    if not isinstance(catalog_http_report, Mapping):
        code = "CATALOG_CANDIDATE_EVIDENCE_HTTP_MATRIX_REPORT_INVALID"
        catalog_http_report = _exception_component(code)
        return blocked_report(
            [_problem(code, "run_catalog_http_matrix must return a mapping")],
            component_evidence={
                "catalog": catalog,
                "catalog_http_report": catalog_http_report,
                "expectedSpecs": canonical_expected_specs,
                "exact_registry_report": exact_registry,
            },
            component_statuses={
                "catalog": _text(_mapping(catalog).get("status")),
                "catalog_http_report": "blocked",
                "exact_registry_report": _text(_mapping(exact_registry).get("status")),
            },
        )
    if (
        _text(_mapping(catalog_http_report).get("status")) != "pass"
        or (_int_or_none(_mapping(catalog_http_report).get("failureCount")) or 0) != 0
    ):
        relation_contexts = _relation_contexts_from_override(observed_relation_contexts)
        counts = _catalog_gate_counts(
            catalog_http_report=_mapping(catalog_http_report),
            materialization_report={},
            relation_contexts=relation_contexts,
            expected_identity=normalized_identity,
        )
        return blocked_report(
            [
                _problem(
                    "CATALOG_CANDIDATE_EVIDENCE_HTTP_MATRIX_NOT_PASS",
                    "HTTP completeness matrix must stay pass with zero failures",
                    status=_text(_mapping(catalog_http_report).get("status")) or "missing",
                    failureCount=_int_or_none(_mapping(catalog_http_report).get("failureCount")),
                )
            ],
            component_evidence={
                "catalog": catalog,
                "catalog_http_report": catalog_http_report,
                "catalog_gate_counts": counts,
                "expectedSpecs": canonical_expected_specs,
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
        try:
            relation_contexts, relation_problems = _extract_relation_contexts(
                catalog=_mapping(catalog),
                records=records,
                get_profile_context=get_profile_context,
                selection_intent_factory=selection_intent_factory,
            )
        except Exception as error:
            code = "CATALOG_CANDIDATE_EVIDENCE_PROFILE_CONTEXT_EXTRACTION_EXCEPTION"
            return blocked_report(
                [_exception_problem(code, "relation_context_extraction", error)],
                component_evidence={
                    "catalog": catalog,
                    "catalog_http_report": catalog_http_report,
                    "expectedSpecs": canonical_expected_specs,
                    "exact_registry_report": exact_registry,
                },
                component_statuses={
                    "catalog": _text(_mapping(catalog).get("status")),
                    "catalog_http_report": _text(_mapping(catalog_http_report).get("status")),
                    "exact_registry_report": _text(_mapping(exact_registry).get("status")),
                },
            )
    if relation_problems:
        return blocked_report(
            relation_problems,
            component_evidence={
                "catalog": catalog,
                "catalog_http_report": catalog_http_report,
                "catalog_gate_counts": {
                    "relationContexts": _canonical(relation_contexts),
                },
                "expectedSpecs": canonical_expected_specs,
                "exact_registry_report": exact_registry,
            },
            component_statuses={
                "catalog": _text(_mapping(catalog).get("status")),
                "catalog_http_report": _text(_mapping(catalog_http_report).get("status")),
                "exact_registry_report": _text(_mapping(exact_registry).get("status")),
            },
        )

    try:
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
    except Exception as error:
        code = "CATALOG_CANDIDATE_EVIDENCE_MATERIALIZATION_RUNNER_EXCEPTION"
        return blocked_report(
            [_exception_problem(code, "build_materialization_runner", error)],
            component_evidence={
                "catalog": catalog,
                "catalog_http_report": catalog_http_report,
                "catalog_gate_counts": _catalog_gate_counts(
                    catalog_http_report=_mapping(catalog_http_report),
                    materialization_report={},
                    relation_contexts=relation_contexts,
                    expected_identity=normalized_identity,
                ),
                "materialization_report": _exception_component(code),
                "expectedSpecs": canonical_expected_specs,
                "exact_registry_report": exact_registry,
            },
            component_statuses={
                "catalog": _text(_mapping(catalog).get("status")),
                "catalog_http_report": _text(_mapping(catalog_http_report).get("status")),
                "materialization_report": "blocked",
                "exact_registry_report": _text(_mapping(exact_registry).get("status")),
            },
        )
    try:
        materialization_report = _canonical(
            build_materialization_matrix(
                _mapping(catalog),
                relation_contexts,
                materializer,
            )
        )
    except Exception as error:
        code = "CATALOG_CANDIDATE_EVIDENCE_MATERIALIZATION_MATRIX_EXCEPTION"
        return blocked_report(
            [_exception_problem(code, "build_materialization_matrix", error)],
            component_evidence={
                "catalog": catalog,
                "catalog_http_report": catalog_http_report,
                "catalog_gate_counts": _catalog_gate_counts(
                    catalog_http_report=_mapping(catalog_http_report),
                    materialization_report={},
                    relation_contexts=relation_contexts,
                    expected_identity=normalized_identity,
                ),
                "materialization_report": _exception_component(code),
                "expectedSpecs": canonical_expected_specs,
                "exact_registry_report": exact_registry,
            },
            component_statuses={
                "catalog": _text(_mapping(catalog).get("status")),
                "catalog_http_report": _text(_mapping(catalog_http_report).get("status")),
                "materialization_report": "blocked",
                "exact_registry_report": _text(_mapping(exact_registry).get("status")),
            },
        )
    if not isinstance(materialization_report, Mapping):
        code = "CATALOG_CANDIDATE_EVIDENCE_MATERIALIZATION_MATRIX_REPORT_INVALID"
        materialization_report = _exception_component(code)
        return blocked_report(
            [_problem(code, "build_materialization_matrix must return a mapping")],
            component_evidence={
                "catalog": catalog,
                "catalog_http_report": catalog_http_report,
                "materialization_report": materialization_report,
                "expectedSpecs": canonical_expected_specs,
                "exact_registry_report": exact_registry,
            },
            component_statuses={
                "catalog": _text(_mapping(catalog).get("status")),
                "catalog_http_report": _text(_mapping(catalog_http_report).get("status")),
                "materialization_report": "blocked",
                "exact_registry_report": _text(_mapping(exact_registry).get("status")),
            },
        )
    catalog_gate_counts = _catalog_gate_counts(
        catalog_http_report=_mapping(catalog_http_report),
        materialization_report=_mapping(materialization_report),
        relation_contexts=relation_contexts,
        expected_identity=normalized_identity,
    )
    try:
        simc_26_14_report = _canonical(
            run_simc_execution_matrix(
                request_json,
                simc_executor,
                expected_specs=canonical_expected_specs,
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
    except Exception as error:
        code = "CATALOG_CANDIDATE_EVIDENCE_SIMC_EXECUTION_MATRIX_EXCEPTION"
        return blocked_report(
            [_exception_problem(code, "run_simc_execution_matrix", error)],
            component_evidence={
                "catalog": catalog,
                "catalog_http_report": catalog_http_report,
                "catalog_gate_counts": catalog_gate_counts,
                "materialization_report": materialization_report,
                "simc_execution_matrix_report": _exception_component(code),
                "expectedSpecs": canonical_expected_specs,
                "exact_registry_report": exact_registry,
            },
            component_statuses={
                "catalog": _text(_mapping(catalog).get("status")),
                "catalog_http_report": _text(_mapping(catalog_http_report).get("status")),
                "materialization_report": _text(_mapping(materialization_report).get("status")),
                "simc_execution_matrix_report": "blocked",
                "exact_registry_report": _text(_mapping(exact_registry).get("status")),
            },
        )
    if not isinstance(simc_26_14_report, Mapping):
        code = "CATALOG_CANDIDATE_EVIDENCE_SIMC_EXECUTION_MATRIX_REPORT_INVALID"
        simc_26_14_report = _exception_component(code)
        return blocked_report(
            [_problem(code, "run_simc_execution_matrix must return a mapping")],
            component_evidence={
                "catalog": catalog,
                "catalog_http_report": catalog_http_report,
                "catalog_gate_counts": catalog_gate_counts,
                "materialization_report": materialization_report,
                "simc_execution_matrix_report": simc_26_14_report,
                "expectedSpecs": canonical_expected_specs,
                "exact_registry_report": exact_registry,
            },
            component_statuses={
                "catalog": _text(_mapping(catalog).get("status")),
                "catalog_http_report": _text(_mapping(catalog_http_report).get("status")),
                "materialization_report": _text(_mapping(materialization_report).get("status")),
                "simc_execution_matrix_report": "blocked",
                "exact_registry_report": _text(_mapping(exact_registry).get("status")),
            },
        )
    variant_smoke_callback = _build_variant_smoke_callback(
        request_json=request_json,
        simc_executor=simc_executor,
        relation_contexts=relation_contexts,
        get_profile_context=get_profile_context,
        expected_identity=normalized_identity,
    )
    try:
        variant_simc_report = _canonical(
            build_variant_simc_matrix(
                materialization_report,
                variant_smoke_callback,
            )
        )
    except Exception as error:
        code = "CATALOG_CANDIDATE_EVIDENCE_VARIANT_SIMC_MATRIX_EXCEPTION"
        return blocked_report(
            [_exception_problem(code, "build_variant_simc_matrix", error)],
            component_evidence={
                "catalog": catalog,
                "catalog_http_report": catalog_http_report,
                "catalog_gate_counts": catalog_gate_counts,
                "materialization_report": materialization_report,
                "variant_simc_report": _exception_component(code),
                "simc_execution_matrix_report": simc_26_14_report,
                "expectedSpecs": canonical_expected_specs,
                "exact_registry_report": exact_registry,
            },
            component_statuses={
                "catalog": _text(_mapping(catalog).get("status")),
                "catalog_http_report": _text(_mapping(catalog_http_report).get("status")),
                "materialization_report": _text(_mapping(materialization_report).get("status")),
                "variant_simc_report": "blocked",
                "simc_execution_matrix_report": _text(_mapping(simc_26_14_report).get("status")),
                "exact_registry_report": _text(_mapping(exact_registry).get("status")),
            },
        )
    if not isinstance(variant_simc_report, Mapping):
        code = "CATALOG_CANDIDATE_EVIDENCE_VARIANT_SIMC_MATRIX_REPORT_INVALID"
        variant_simc_report = _exception_component(code)
        return blocked_report(
            [_problem(code, "build_variant_simc_matrix must return a mapping")],
            component_evidence={
                "catalog": catalog,
                "catalog_http_report": catalog_http_report,
                "catalog_gate_counts": catalog_gate_counts,
                "materialization_report": materialization_report,
                "variant_simc_report": variant_simc_report,
                "simc_execution_matrix_report": simc_26_14_report,
                "expectedSpecs": canonical_expected_specs,
                "exact_registry_report": exact_registry,
            },
            component_statuses={
                "catalog": _text(_mapping(catalog).get("status")),
                "catalog_http_report": _text(_mapping(catalog_http_report).get("status")),
                "materialization_report": _text(_mapping(materialization_report).get("status")),
                "variant_simc_report": "blocked",
                "simc_execution_matrix_report": _text(_mapping(simc_26_14_report).get("status")),
                "exact_registry_report": _text(_mapping(exact_registry).get("status")),
            },
        )

    pointer_after, pointer_after_problem = _safe_pointer_snapshot(
        pointer_reader,
        pointer_before,
    )
    if pointer_after_problem:
        return _runner_report(
            status="blocked",
            expected_identity=normalized_identity,
            problems=[pointer_after_problem],
            pointer_before=pointer_before,
            pointer_after=pointer_after,
            component_evidence={
                "catalog": catalog,
                "catalog_http_report": catalog_http_report,
                "catalog_gate_counts": catalog_gate_counts,
                "materialization_report": materialization_report,
                "variant_simc_report": variant_simc_report,
                "simc_execution_matrix_report": simc_26_14_report,
                "expectedSpecs": canonical_expected_specs,
                "exact_registry_report": exact_registry,
                "pointer": _exception_component(pointer_after_problem["code"]),
            },
            component_statuses={
                "catalog": _text(_mapping(catalog).get("status")),
                "catalog_http_report": _text(_mapping(catalog_http_report).get("status")),
                "materialization_report": _text(_mapping(materialization_report).get("status")),
                "variant_simc_report": _text(_mapping(variant_simc_report).get("status")),
                "simc_execution_matrix_report": _text(_mapping(simc_26_14_report).get("status")),
                "exact_registry_report": _text(_mapping(exact_registry).get("status")),
                "pointer": "blocked",
            },
        )

    try:
        assembled = assemble_evidence(
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
    except Exception as error:
        code = "CATALOG_CANDIDATE_EVIDENCE_ASSEMBLER_EXCEPTION"
        return _runner_report(
            status="blocked",
            expected_identity=normalized_identity,
            problems=[_exception_problem(code, "assemble_evidence", error)],
            pointer_before=pointer_before,
            pointer_after=pointer_after,
            component_evidence={
                "catalog": catalog,
                "catalog_http_report": catalog_http_report,
                "catalog_gate_counts": catalog_gate_counts,
                "materialization_report": materialization_report,
                "variant_simc_report": variant_simc_report,
                "simc_execution_matrix_report": simc_26_14_report,
                "expectedSpecs": canonical_expected_specs,
                "exact_registry_report": exact_registry,
                "assembler": _exception_component(code),
            },
            component_statuses={
                "catalog": _text(_mapping(catalog).get("status")),
                "catalog_http_report": _text(_mapping(catalog_http_report).get("status")),
                "materialization_report": _text(_mapping(materialization_report).get("status")),
                "variant_simc_report": _text(_mapping(variant_simc_report).get("status")),
                "simc_execution_matrix_report": _text(_mapping(simc_26_14_report).get("status")),
                "exact_registry_report": _text(_mapping(exact_registry).get("status")),
                "assembler": "blocked",
            },
        )
    if not isinstance(assembled, Mapping):
        code = "CATALOG_CANDIDATE_EVIDENCE_ASSEMBLER_REPORT_INVALID"
        return _runner_report(
            status="blocked",
            expected_identity=normalized_identity,
            problems=[_problem(code, "assemble_evidence must return a mapping")],
            pointer_before=pointer_before,
            pointer_after=pointer_after,
            component_evidence={
                "catalog": catalog,
                "catalog_http_report": catalog_http_report,
                "catalog_gate_counts": catalog_gate_counts,
                "materialization_report": materialization_report,
                "variant_simc_report": variant_simc_report,
                "simc_execution_matrix_report": simc_26_14_report,
                "expectedSpecs": canonical_expected_specs,
                "exact_registry_report": exact_registry,
                "assembler": _exception_component(code),
            },
            component_statuses={
                "catalog": _text(_mapping(catalog).get("status")),
                "catalog_http_report": _text(_mapping(catalog_http_report).get("status")),
                "materialization_report": _text(_mapping(materialization_report).get("status")),
                "variant_simc_report": _text(_mapping(variant_simc_report).get("status")),
                "simc_execution_matrix_report": _text(_mapping(simc_26_14_report).get("status")),
                "exact_registry_report": _text(_mapping(exact_registry).get("status")),
                "assembler": "blocked",
            },
        )
    return _canonical(assembled)


__all__ = [
    "CATALOG_CANDIDATE_EVIDENCE_RUNNER_SCHEMA_REVISION",
    "run_catalog_candidate_evidence",
]
