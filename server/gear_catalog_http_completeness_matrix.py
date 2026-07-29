"""Aggregate-only Catalog-to-HTTP completeness matrix for all specializations."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlencode


RequestJson = Callable[
    [str, str, dict[str, Any] | None, dict[str, str]],
    tuple[int, dict[str, Any], float],
]

CANONICAL_GEAR_SLOTS = (
    "head",
    "neck",
    "shoulder",
    "back",
    "chest",
    "wrist",
    "hands",
    "waist",
    "legs",
    "feet",
    "finger1",
    "finger2",
    "trinket1",
    "trinket2",
    "main_hand",
    "off_hand",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _integer(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


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


def _failure(
    code: str,
    class_key: str,
    spec_key: str,
    *,
    slot: str = "",
    item_id: str = "",
) -> dict[str, str]:
    return {
        "code": _text(code) or "CATALOG_HTTP_MATRIX_BLOCKED",
        "classKey": _text(class_key),
        "specKey": _text(spec_key),
        **({"slot": _text(slot)} if _text(slot) else {}),
        **({"itemId": _text(item_id)} if _text(item_id) else {}),
    }


def _percentile(values: list[float], percentile: int) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    index = max(
        0,
        min(
            len(ordered) - 1,
            ((len(ordered) * percentile + 99) // 100) - 1,
        ),
    )
    return round(ordered[index], 3)


def _catalog_indexes(
    catalog: Mapping[str, Any],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, set[str]],
    list[str],
]:
    problems: list[str] = []
    definitions: dict[str, dict[str, Any]] = {}
    for raw in catalog.get("itemDefinitions") or []:
        row = dict(raw) if isinstance(raw, Mapping) else {}
        item_id = _text(row.get("itemId"))
        if not item_id or item_id in definitions:
            problems.append("CATALOG_ITEM_DEFINITION_ID_INVALID")
            continue
        definitions[item_id] = row

    variants: dict[str, dict[str, Any]] = {}
    by_item: dict[str, set[str]] = {}
    for raw in catalog.get("browseVariants") or []:
        row = dict(raw) if isinstance(raw, Mapping) else {}
        key = _text(row.get("browseVariantKey"))
        item_id = _text(row.get("itemId"))
        if (
            not key
            or key in variants
            or item_id not in definitions
        ):
            problems.append("CATALOG_BROWSE_VARIANT_ID_INVALID")
            continue
        variants[key] = row
        by_item.setdefault(item_id, set()).add(key)

    for item_id in definitions:
        if not by_item.get(item_id):
            problems.append("CATALOG_ITEM_WITHOUT_BROWSE_VARIANT")
    return definitions, variants, by_item, sorted(set(problems))


def _binding_failures(
    payload: Mapping[str, Any],
    *,
    manifest_revision: str,
    pointer_generation: int,
    gear_release_id: str,
    community_release_id: str,
    catalog_revision: str,
    exact_registry_revision: str,
) -> list[str]:
    failures = []
    checks = (
        (
            payload.get("candidatePreview") is True
            and payload.get("formalActiveManifest") is False,
            "CATALOG_HTTP_CANDIDATE_BINDING_REQUIRED",
        ),
        (
            _text(payload.get("manifestRevision"))
            == manifest_revision,
            "CATALOG_HTTP_MANIFEST_MISMATCH",
        ),
        (
            _integer(payload.get("pointerGeneration"))
            == pointer_generation,
            "CATALOG_HTTP_POINTER_GENERATION_MISMATCH",
        ),
        (
            _text(payload.get("gearCatalogReleaseId"))
            == gear_release_id,
            "CATALOG_HTTP_GEAR_RELEASE_MISMATCH",
        ),
        (
            _text(payload.get("communityTemplateReleaseId"))
            == community_release_id,
            "CATALOG_HTTP_COMMUNITY_RELEASE_MISMATCH",
        ),
        (
            _text(payload.get("gearCatalogRevision"))
            == catalog_revision,
            "CATALOG_HTTP_CATALOG_REVISION_MISMATCH",
        ),
        (
            _text(payload.get("gearExactRegistryRevision"))
            == exact_registry_revision,
            "CATALOG_HTTP_EXACT_REGISTRY_MISMATCH",
        ),
    )
    for condition, code in checks:
        if not condition:
            failures.append(code)
    return failures


def run_catalog_http_completeness_matrix(
    request_json: RequestJson,
    *,
    catalog: Mapping[str, Any],
    expected_specs: Iterable[tuple[str, str]],
    manifest_revision: str,
    pointer_generation: int,
    gear_release_id: str,
    community_release_id: str,
    catalog_revision: str,
    exact_registry_revision: str,
    observed_at: str,
) -> dict[str, Any]:
    """Cross-check all 40 full public payloads against one sealed Catalog."""

    expected = sorted({
        (_text(class_key), _text(spec_key))
        for class_key, spec_key in expected_specs
        if _text(class_key) and _text(spec_key)
    })
    definitions, variants, variants_by_item, catalog_problems = (
        _catalog_indexes(catalog)
    )
    failures: list[dict[str, str]] = [
        _failure(code, "", "")
        for code in catalog_problems
    ]
    if (
        _text(catalog.get("status")) != "verified"
        or _text(catalog.get("catalogRevision")) != catalog_revision
    ):
        failures.append(_failure(
            "CATALOG_HTTP_SOURCE_CATALOG_INVALID",
            "",
            "",
        ))

    observed_items: set[str] = set()
    observed_variants: set[str] = set()
    passing_specs = 0
    observed_spec_slots = 0
    nonempty_spec_slots = 0
    visible_item_relations = 0
    visible_variant_relations = 0
    latencies: list[float] = []

    for class_key, spec_key in expected:
        query = urlencode({
            "class": class_key,
            "spec": spec_key,
            "compact": "1",
            "mode": "full",
        })
        try:
            status, payload, duration_ms = request_json(
                "GET",
                f"/api/websim/gear?{query}",
                None,
                {"X-Wow-Platform": "miniprogram"},
            )
        except Exception:
            status, payload, duration_ms = 0, {}, 0.0
        payload = payload if isinstance(payload, dict) else {}
        latencies.append(float(duration_ms or 0))
        spec_failures: list[dict[str, str]] = []
        if status != 200:
            spec_failures.append(_failure(
                "CATALOG_HTTP_REQUEST_FAILED",
                class_key,
                spec_key,
            ))
        for code in _binding_failures(
            payload,
            manifest_revision=manifest_revision,
            pointer_generation=pointer_generation,
            gear_release_id=gear_release_id,
            community_release_id=community_release_id,
            catalog_revision=catalog_revision,
            exact_registry_revision=exact_registry_revision,
        ):
            spec_failures.append(_failure(
                code,
                class_key,
                spec_key,
            ))

        groups = (
            payload.get("replacementCandidates")
            if isinstance(payload.get("replacementCandidates"), list)
            else []
        )
        group_slots = [
            _text(group.get("slot"))
            for group in groups
            if isinstance(group, Mapping)
        ]
        if (
            tuple(group_slots) != CANONICAL_GEAR_SLOTS
            or len(set(group_slots)) != len(CANONICAL_GEAR_SLOTS)
        ):
            spec_failures.append(_failure(
                "CATALOG_HTTP_SLOT_TOPOLOGY_INVALID",
                class_key,
                spec_key,
            ))
        observed_spec_slots += len(group_slots)

        for raw_group in groups:
            group = (
                dict(raw_group)
                if isinstance(raw_group, Mapping)
                else {}
            )
            slot = _text(group.get("slot"))
            items = (
                group.get("items")
                if isinstance(group.get("items"), list)
                else []
            )
            if items:
                nonempty_spec_slots += 1
            seen_group_items: set[str] = set()
            for raw_item in items:
                item = (
                    dict(raw_item)
                    if isinstance(raw_item, Mapping)
                    else {}
                )
                item_id = _text(item.get("itemId") or item.get("id"))
                visible_item_relations += 1
                if (
                    not item_id
                    or item_id in seen_group_items
                    or item_id not in definitions
                ):
                    spec_failures.append(_failure(
                        "CATALOG_HTTP_ITEM_RELATION_INVALID",
                        class_key,
                        spec_key,
                        slot=slot,
                        item_id=item_id,
                    ))
                    continue
                seen_group_items.add(item_id)
                observed_items.add(item_id)
                compatibility = (
                    item.get("compatibility")
                    if isinstance(item.get("compatibility"), Mapping)
                    else {}
                )
                if (
                    _text(item.get("slot")) != slot
                    or _text(compatibility.get("classKey"))
                    != class_key
                    or _text(compatibility.get("specKey"))
                    != spec_key
                    or _text(compatibility.get("status"))
                    != "compatible"
                ):
                    spec_failures.append(_failure(
                        "CATALOG_HTTP_ITEM_COMPATIBILITY_INVALID",
                        class_key,
                        spec_key,
                        slot=slot,
                        item_id=item_id,
                    ))

                item_variants = (
                    item.get("variants")
                    if isinstance(item.get("variants"), list)
                    else []
                )
                actual_keys: set[str] = set()
                for raw_variant in item_variants:
                    variant = (
                        dict(raw_variant)
                        if isinstance(raw_variant, Mapping)
                        else {}
                    )
                    key = _text(
                        variant.get("variantKey")
                        or variant.get("key")
                        or variant.get("id")
                    )
                    visible_variant_relations += 1
                    expected_variant = variants.get(key)
                    if (
                        not key
                        or key in actual_keys
                        or not expected_variant
                        or _text(variant.get("itemId")) != item_id
                        or _text(variant.get("status")) != "verified"
                        or _integer(variant.get("itemLevel"))
                        != _integer(expected_variant.get("itemLevel"))
                        or _text(variant.get("sourceType"))
                        != _text(expected_variant.get("sourceType"))
                        or _canonical(variant.get("progressionState"))
                        != _canonical(
                            expected_variant.get("progressionState")
                        )
                    ):
                        spec_failures.append(_failure(
                            "CATALOG_HTTP_VARIANT_RELATION_INVALID",
                            class_key,
                            spec_key,
                            slot=slot,
                            item_id=item_id,
                        ))
                        continue
                    actual_keys.add(key)
                    observed_variants.add(key)
                if actual_keys != variants_by_item.get(item_id, set()):
                    spec_failures.append(_failure(
                        "CATALOG_HTTP_ITEM_VARIANT_SET_INCOMPLETE",
                        class_key,
                        spec_key,
                        slot=slot,
                        item_id=item_id,
                    ))
                if _text(item.get("defaultVariantKey")) not in actual_keys:
                    spec_failures.append(_failure(
                        "CATALOG_HTTP_DEFAULT_VARIANT_INVALID",
                        class_key,
                        spec_key,
                        slot=slot,
                        item_id=item_id,
                    ))

        if not spec_failures:
            passing_specs += 1
        failures.extend(spec_failures)

    missing_items = sorted(set(definitions) - observed_items)
    extra_items = sorted(observed_items - set(definitions))
    missing_variants = sorted(set(variants) - observed_variants)
    extra_variants = sorted(observed_variants - set(variants))
    for code, values in (
        ("CATALOG_HTTP_UNIVERSE_ITEM_MISSING", missing_items),
        ("CATALOG_HTTP_UNIVERSE_ITEM_EXTRA", extra_items),
        ("CATALOG_HTTP_UNIVERSE_VARIANT_MISSING", missing_variants),
        ("CATALOG_HTTP_UNIVERSE_VARIANT_EXTRA", extra_variants),
    ):
        if values:
            failures.append(_failure(code, "", "", item_id=values[0]))

    failure_codes: dict[str, int] = {}
    for failure in failures:
        code = failure["code"]
        failure_codes[code] = failure_codes.get(code, 0) + 1
    expected_spec_slots = len(expected) * len(CANONICAL_GEAR_SLOTS)
    status = (
        "pass"
        if (
            not failures
            and passing_specs == len(expected)
            and observed_spec_slots == expected_spec_slots
            and observed_items == set(definitions)
            and observed_variants == set(variants)
        )
        else "blocked"
    )
    stable = {
        "schemaRevision": (
            "gear-catalog-http-completeness-matrix-v1"
        ),
        "status": status,
        "bindingMode": "candidate_preview",
        "manifestRevision": _text(manifest_revision),
        "pointerGeneration": _integer(pointer_generation),
        "gearReleaseId": _text(gear_release_id),
        "communityReleaseId": _text(community_release_id),
        "catalogRevision": _text(catalog_revision),
        "exactRegistryRevision": _text(exact_registry_revision),
        "specCoverage": {
            "expectedSpecCount": len(expected),
            "passingSpecCount": passing_specs,
            "expectedSpecSlotCount": expected_spec_slots,
            "observedSpecSlotCount": observed_spec_slots,
            "nonemptySpecSlotCount": nonempty_spec_slots,
        },
        "catalogUniverse": {
            "expectedItemCount": len(definitions),
            "observedItemCount": len(observed_items),
            "missingItemCount": len(missing_items),
            "extraItemCount": len(extra_items),
            "expectedVariantCount": len(variants),
            "observedVariantCount": len(observed_variants),
            "missingVariantCount": len(missing_variants),
            "extraVariantCount": len(extra_variants),
        },
        "relations": {
            "visibleItemRelationCount": visible_item_relations,
            "visibleVariantRelationCount": (
                visible_variant_relations
            ),
        },
        "failureCount": len(failures),
        "failureCodes": {
            code: failure_codes[code]
            for code in sorted(failure_codes)
        },
        "failureSamples": failures[:20],
    }
    digest = hashlib.sha256(
        json.dumps(
            stable,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        **stable,
        "reportId": (
            "gear-catalog-http-completeness:sha256:" + digest
        ),
        "observedAt": _text(observed_at),
        "performance": {
            "sampleCount": len(latencies),
            "p50Ms": _percentile(latencies, 50),
            "p95Ms": _percentile(latencies, 95),
            "maxMs": (
                round(max(latencies), 3) if latencies else 0
            ),
        },
    }


__all__ = (
    "CANONICAL_GEAR_SLOTS",
    "run_catalog_http_completeness_matrix",
)
