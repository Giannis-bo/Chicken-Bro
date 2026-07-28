#!/usr/bin/env python3
"""Privacy-safe dormant registry for template-referenced exact gear instances."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from .gear_exact_item_instance import build_exact_item_instance


EXACT_ITEM_REGISTRY_SCHEMA_REVISION = "gear-exact-item-registry-v1"
EXACT_TEMPLATE_REFERENCE_SCHEMA_REVISION = "gear-exact-template-reference-v1"
REGISTRY_REVISION_PATTERN = re.compile(
    r"^gear-exact-registry:sha256:[0-9a-f]{64}$"
)
_HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_ENHANCEMENT_FIELDS = (
    "gemIds",
    "gemBonusIds",
    "gemItemLevels",
    "enchantId",
    "craftedStats",
    "embellishmentIds",
)


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


def _bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _hash(prefix: str, value: Any) -> str:
    return prefix + hashlib.sha256(_bytes(value)).hexdigest()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _problem(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _source_enhancement(row: Mapping[str, Any]) -> dict[str, Any]:
    options = (
        row.get("simcOptions")
        if isinstance(row.get("simcOptions"), Mapping)
        else {}
    )
    return {
        "gemIds": options.get("gem_id"),
        "gemBonusIds": options.get("gem_bonus_id"),
        "gemItemLevels": options.get("gem_ilevel"),
        "enchantId": options.get("enchant_id"),
        "craftedStats": options.get("crafted_stats"),
        "embellishmentIds": options.get("embellishment"),
    }


def _explicit_enhancement(
    item: Mapping[str, Any],
    exact_row: Mapping[str, Any],
) -> dict[str, Any] | None:
    if not any(field in item for field in _ENHANCEMENT_FIELDS):
        return None
    source = _source_enhancement(exact_row)
    return {
        field: item.get(field) if field in item else source.get(field)
        for field in _ENHANCEMENT_FIELDS
    }


def _template_item_semantics(item: Any) -> dict[str, Any]:
    row = dict(item) if isinstance(item, Mapping) else {}
    result = {
        "slot": _text(row.get("slot")),
        "itemId": _text(row.get("itemId") or row.get("id")),
        "variantKey": _text(row.get("variantKey")),
    }
    for field in (
        "observedItemLevel",
        "ilevel",
        "itemLevel",
        "progressionState",
    ):
        if field in row:
            result[field] = _canonical(row.get(field))
    for field in ("gemIds", "gemBonusIds", "gemItemLevels"):
        if field in row:
            value = row.get(field)
            if isinstance(value, str):
                value = value.split("/")
            result[field] = [
                _text(token)
                for token in value or []
                if _text(token)
            ]
    for field in ("bonusIds", "craftedStats", "embellishmentIds"):
        if field in row:
            value = row.get(field)
            if isinstance(value, str):
                value = value.split("/")
            result[field] = sorted({
                _text(token)
                for token in value or []
                if _text(token)
            })
    if "enchantId" in row:
        result["enchantId"] = _text(row.get("enchantId"))
    return result


def _template_content_hash(template: Mapping[str, Any]) -> str:
    items = [
        _template_item_semantics(item)
        for item in template.get("gearItems") or []
    ]
    items.sort(
        key=lambda row: (
            _text(row.get("slot")),
            _text(row.get("itemId")),
            _text(row.get("variantKey")),
            json.dumps(row, sort_keys=True, separators=(",", ":")),
        )
    )
    return _hash("sha256:", {
        "classKey": _text(template.get("classKey")),
        "specKey": _text(template.get("specKey")),
        "heroKey": _text(template.get("heroKey")),
        "scenarioKey": _text(template.get("scenarioKey")),
        "gearItems": items,
    })


def _reference_row(
    *,
    catalog_revision: str,
    scope: str,
    content_hash: str,
    slot: str,
    item_id: str,
    variant_key: str,
    status: str,
    exact_key: str = "",
    problem_codes: list[str] | None = None,
) -> dict[str, Any]:
    row = {
        "schemaRevision": EXACT_TEMPLATE_REFERENCE_SCHEMA_REVISION,
        "catalogRevision": catalog_revision,
        "templateScope": scope,
        "templateContentHash": content_hash,
        "slot": slot,
        "itemId": item_id,
        "sourceVariantKey": variant_key,
        "exactItemInstanceKey": exact_key,
        "validationStatus": status,
        "problemCodes": sorted(set(problem_codes or [])),
    }
    return {
        **row,
        "rowHash": _hash("sha256:", row),
    }


def _registry_semantics(registry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schemaRevision": _text(registry.get("schemaRevision")),
        "catalogRevision": _text(registry.get("catalogRevision")),
        "seasonRevision": _text(registry.get("seasonRevision")),
        "gearRuleRevision": _text(registry.get("gearRuleRevision")),
        "enhancementSelections": _canonical(
            registry.get("enhancementSelections") or []
        ),
        "exactItemInstances": _canonical(
            registry.get("exactItemInstances") or []
        ),
        "validations": _canonical(registry.get("validations") or []),
        "templateReferences": _canonical(
            registry.get("templateReferences") or []
        ),
    }


def build_exact_item_registry(
    binding: Any,
    *,
    catalog_revision: str,
    exact_rows: Any,
    community_templates: Any,
    personal_templates: Any,
) -> dict[str, Any]:
    """Materialize only exact instances referenced by structured templates."""

    active = dict(binding) if isinstance(binding, Mapping) else {}
    sources = [row for row in exact_rows or [] if isinstance(row, Mapping)]
    community = [
        row for row in community_templates or [] if isinstance(row, Mapping)
    ]
    personal = [
        row for row in personal_templates or [] if isinstance(row, Mapping)
    ]
    source_index: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in sources:
        key = (_text(row.get("itemId")), _text(row.get("variantKey")))
        if all(key):
            source_index.setdefault(key, []).append(row)

    problems: list[dict[str, str]] = []
    if not community:
        problems.append(_problem(
            "EXACT_REGISTRY_COMMUNITY_MISSING",
            "communityTemplates",
            "At least one sealed Community gear template is required.",
        ))

    selection_rows: dict[str, dict[str, Any]] = {}
    instance_rows: dict[str, dict[str, Any]] = {}
    validation_rows: dict[tuple[str, str, str], dict[str, Any]] = {}
    references: list[dict[str, Any]] = []
    referenced_source_keys: set[tuple[str, str]] = set()
    template_count = 0
    template_item_count = 0
    classified_template_count = 0
    verified_template_item_count = 0
    blocked_template_item_count = 0

    for scope, templates in (("community", community), ("personal", personal)):
        for template_index, template in enumerate(templates):
            template_count += 1
            classified_template_count += 1
            content_hash = _template_content_hash(template)
            items = template.get("gearItems")
            if not isinstance(items, list) or not items:
                problem = _problem(
                    "EXACT_REGISTRY_TEMPLATE_ITEMS_MISSING",
                    f"{scope}[{template_index}].gearItems",
                    "A structured gear template must contain at least one item.",
                )
                problems.append(problem)
                references.append(_reference_row(
                    catalog_revision=catalog_revision,
                    scope=scope,
                    content_hash=content_hash,
                    slot="",
                    item_id="",
                    variant_key="",
                    status="blocked",
                    problem_codes=[problem["code"]],
                ))
                continue

            for item_index, raw_item in enumerate(items):
                template_item_count += 1
                item = dict(raw_item) if isinstance(raw_item, Mapping) else {}
                slot = _text(item.get("slot"))
                item_id = _text(item.get("itemId") or item.get("id"))
                variant_key = _text(item.get("variantKey"))
                path = f"{scope}[{template_index}].gearItems[{item_index}]"
                item_problems: list[dict[str, str]] = []
                if not slot or not item_id or not variant_key:
                    item_problems.append(_problem(
                        "EXACT_REGISTRY_TEMPLATE_IDENTITY_MISSING",
                        path,
                        "Template item requires slot, itemId and variantKey.",
                    ))
                candidates = source_index.get((item_id, variant_key), [])
                if not item_problems and not candidates:
                    item_problems.append(_problem(
                        "EXACT_REGISTRY_SOURCE_MISSING",
                        path,
                        "Template exact identity is absent from the sealed source.",
                    ))
                elif not item_problems and len(candidates) > 1:
                    item_problems.append(_problem(
                        "EXACT_REGISTRY_SOURCE_AMBIGUOUS",
                        path,
                        "Template exact identity resolves to multiple sealed source rows.",
                    ))

                built: dict[str, Any] = {}
                if not item_problems:
                    source = candidates[0]
                    built = build_exact_item_instance(
                        active,
                        source,
                        catalog_revision=catalog_revision,
                        enhancement_selection=_explicit_enhancement(item, source),
                    )
                    if built.get("status") != "verified":
                        item_problems.extend(
                            dict(problem)
                            for problem in built.get("problems") or []
                            if isinstance(problem, Mapping)
                        )

                if item_problems:
                    blocked_template_item_count += 1
                    problems.extend(item_problems)
                    references.append(_reference_row(
                        catalog_revision=catalog_revision,
                        scope=scope,
                        content_hash=content_hash,
                        slot=slot,
                        item_id=item_id,
                        variant_key=variant_key,
                        status="blocked",
                        problem_codes=[
                            _text(problem.get("code"))
                            for problem in item_problems
                        ],
                    ))
                    continue

                referenced_source_keys.add((item_id, variant_key))
                selection = dict(built["enhancementSelectionRow"])
                instance = dict(built["instanceRow"])
                validation = dict(built["validation"])
                selection_rows[selection["enhancementSelectionKey"]] = selection
                instance_rows[instance["exactItemInstanceKey"]] = instance
                validation_key = (
                    validation["exactItemInstanceKey"],
                    validation["catalogRevision"],
                    validation["gearRuleRevision"],
                )
                previous = validation_rows.get(validation_key)
                if previous is not None and previous != validation:
                    conflict = _problem(
                        "EXACT_REGISTRY_VALIDATION_CONFLICT",
                        path,
                        "One exact identity produced conflicting Catalog-bound facts.",
                    )
                    problems.append(conflict)
                    blocked_template_item_count += 1
                    references.append(_reference_row(
                        catalog_revision=catalog_revision,
                        scope=scope,
                        content_hash=content_hash,
                        slot=slot,
                        item_id=item_id,
                        variant_key=variant_key,
                        status="blocked",
                        problem_codes=[conflict["code"]],
                    ))
                    continue
                validation_rows[validation_key] = validation
                verified_template_item_count += 1
                references.append(_reference_row(
                    catalog_revision=catalog_revision,
                    scope=scope,
                    content_hash=content_hash,
                    slot=slot,
                    item_id=item_id,
                    variant_key=variant_key,
                    status="verified",
                    exact_key=instance["exactItemInstanceKey"],
                ))

    references_by_hash = {
        row["rowHash"]: row
        for row in references
    }
    references = list(references_by_hash.values())
    references.sort(
        key=lambda row: (
            row["templateScope"],
            row["templateContentHash"],
            row["slot"],
            row["itemId"],
            row["sourceVariantKey"],
            row["rowHash"],
        )
    )
    selections = sorted(
        selection_rows.values(),
        key=lambda row: row["enhancementSelectionKey"],
    )
    instances = sorted(
        instance_rows.values(),
        key=lambda row: row["exactItemInstanceKey"],
    )
    validations = sorted(
        validation_rows.values(),
        key=lambda row: (
            row["exactItemInstanceKey"],
            row["catalogRevision"],
            row["gearRuleRevision"],
        ),
    )
    blocked_reference_count = sum(
        row["validationStatus"] == "blocked" for row in references
    )
    summary = {
        "sourceExactRowCount": len(sources),
        "referencedExactRowCount": len(referenced_source_keys),
        "unreferencedExactRowCount": max(
            0,
            len(sources) - len(referenced_source_keys),
        ),
        "templateCount": template_count,
        "classifiedTemplateCount": classified_template_count,
        "templateItemCount": template_item_count,
        "classifiedTemplateItemCount": template_item_count,
        "verifiedTemplateItemCount": verified_template_item_count,
        "blockedTemplateItemCount": blocked_template_item_count,
        "templateReferenceCount": len(references),
        "verifiedReferenceCount": len(references) - blocked_reference_count,
        "blockedReferenceCount": blocked_reference_count,
        "enhancementSelectionCount": len(selections),
        "exactItemInstanceCount": len(instances),
        "validationCount": len(validations),
    }
    result = {
        "schemaRevision": EXACT_ITEM_REGISTRY_SCHEMA_REVISION,
        "status": "blocked" if problems else "verified",
        "catalogRevision": _text(catalog_revision),
        "seasonRevision": _text(active.get("seasonRevision")),
        "gearRuleRevision": _text(active.get("gearRuleRevision")),
        "enhancementSelections": selections,
        "exactItemInstances": instances,
        "validations": validations,
        "templateReferences": references,
        "summary": summary,
        "problemCodes": sorted({
            _text(problem.get("code"))
            for problem in problems
            if _text(problem.get("code"))
        }),
        "problems": _canonical(problems),
    }
    result["registryRevision"] = _hash(
        "gear-exact-registry:sha256:",
        _registry_semantics(result),
    )
    return result


def verify_exact_item_registry(registry: Any) -> list[str]:
    """Verify canonical keys, row hashes, counts and registry identity."""

    if not isinstance(registry, Mapping):
        return ["EXACT_REGISTRY_OBJECT_INVALID"]
    problems: list[str] = []
    revision = _text(registry.get("registryRevision"))
    expected_revision = _hash(
        "gear-exact-registry:sha256:",
        _registry_semantics(registry),
    )
    if not REGISTRY_REVISION_PATTERN.fullmatch(revision):
        problems.append("EXACT_REGISTRY_REVISION_INVALID")
    elif revision != expected_revision:
        problems.append("EXACT_REGISTRY_REVISION_MISMATCH")
    rows = [
        *(registry.get("enhancementSelections") or []),
        *(registry.get("exactItemInstances") or []),
        *(registry.get("validations") or []),
        *(registry.get("templateReferences") or []),
    ]
    for row in rows:
        if not isinstance(row, Mapping) or not _HASH_PATTERN.fullmatch(
            _text(row.get("rowHash"))
        ):
            problems.append("EXACT_REGISTRY_ROW_HASH_INVALID")
            continue
        without_hash = {
            key: value for key, value in row.items() if key != "rowHash"
        }
        if _hash("sha256:", without_hash) != row.get("rowHash"):
            problems.append("EXACT_REGISTRY_ROW_HASH_MISMATCH")
    summary = registry.get("summary") or {}
    expected_counts = {
        "enhancementSelectionCount": len(
            registry.get("enhancementSelections") or []
        ),
        "exactItemInstanceCount": len(
            registry.get("exactItemInstances") or []
        ),
        "validationCount": len(registry.get("validations") or []),
        "templateReferenceCount": len(
            registry.get("templateReferences") or []
        ),
    }
    for key, expected in expected_counts.items():
        if summary.get(key) != expected:
            problems.append("EXACT_REGISTRY_SUMMARY_MISMATCH")
            break
    return sorted(set(problems))


__all__ = (
    "EXACT_ITEM_REGISTRY_SCHEMA_REVISION",
    "EXACT_TEMPLATE_REFERENCE_SCHEMA_REVISION",
    "REGISTRY_REVISION_PATTERN",
    "build_exact_item_registry",
    "verify_exact_item_registry",
)
