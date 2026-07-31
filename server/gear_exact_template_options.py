#!/usr/bin/env python3
"""Manifest-bound projection of observed exact enhancements into Selection Intent.

The public editor continues to carry only option identities.  This module turns
verified Exact Registry facts into deterministic, import-only option identities
and revalidates those identities against the whole template before Resolver
authority is extended.  Raw SimC values never become client-authored authority.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Iterable, Mapping


EXACT_TEMPLATE_OPTION_PREFIX = "exact-option:sha256:"
EXACT_TEMPLATE_OPTION_PATTERN = re.compile(
    r"^exact-option:sha256:[0-9a-f]{64}$"
)
_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_ENHANCEMENT_FIELDS = (
    "gemOptionIds",
    "enchantOptionId",
    "embellishmentOptionId",
    "craftedOptionId",
    "catalystOptionId",
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


def _blocked(*problems: Mapping[str, Any]) -> dict[str, Any]:
    normalized = sorted(
        {
            json.dumps(
                _canonical(problem),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ): _canonical(problem)
            for problem in problems
        }.values(),
        key=lambda problem: (
            _text(problem.get("code")),
            _text(problem.get("path")),
            _text(problem.get("message")),
        ),
    )
    return {
        "status": "blocked",
        "problemCodes": sorted(
            {
                _text(problem.get("code"))
                for problem in normalized
                if _text(problem.get("code"))
            }
        ),
        "problems": normalized,
    }


def _unique_index(
    rows: Any,
    key_field: str,
) -> dict[str, dict[str, Any]] | None:
    result: dict[str, dict[str, Any]] = {}
    for raw in rows or []:
        # Sealed registries are immutable and byte-verified by their store.
        # Keep read-only references here; JSON-detaching hundreds of rows for
        # every import dominated the candidate request CPU budget.
        row = raw if isinstance(raw, dict) else {}
        key = _text(row.get(key_field))
        if not key or key in result:
            return None
        result[key] = row
    return result


def _catalog_source_aliases(
    catalog: Any,
) -> tuple[dict[tuple[str, str], str], list[dict[str, str]]]:
    value = catalog if isinstance(catalog, Mapping) else {}
    aliases: dict[tuple[str, str], str] = {}
    problems: list[dict[str, str]] = []
    for index, raw in enumerate(value.get("browseVariants") or []):
        row = raw if isinstance(raw, Mapping) else {}
        browse_key = _text(row.get("browseVariantKey"))
        item_id = _text(row.get("itemId"))
        if (
            not browse_key
            or not item_id
            or row.get("evidenceStatus") != "verified"
        ):
            continue
        for source_key in row.get("sourceVariantKeys") or []:
            source = _text(source_key)
            if not source:
                continue
            key = (item_id, source)
            previous = aliases.get(key)
            if previous and previous != browse_key:
                problems.append(
                    _problem(
                        "EXACT_TEMPLATE_CATALOG_ALIAS_AMBIGUOUS",
                        f"gearCatalog.browseVariants[{index}]",
                        "One exact source variant maps to multiple Catalog variants.",
                    )
                )
            aliases[key] = browse_key
    return aliases, problems


def _option(
    *,
    registry_revision: str,
    authority_identity: str,
    reference: Mapping[str, Any],
    exact_key: str,
    selection_key: str,
    option_type: str,
    field: str,
    index: int,
    simc_options: Mapping[str, Any],
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    slot = _text(reference.get("slot"))
    item_id = _text(reference.get("itemId"))
    identity = {
        "registryRevision": registry_revision,
        "templateAuthorityIdentity": authority_identity,
        "slot": slot,
        "itemId": item_id,
        "exactItemInstanceKey": exact_key,
        "enhancementSelectionKey": selection_key,
        "field": field,
        "index": index,
        "simcOptions": _canonical(simc_options),
    }
    option_id = _hash(EXACT_TEMPLATE_OPTION_PREFIX, identity)
    evidence_id = _hash(
        "exact-option-evidence:sha256:",
        {
            "optionId": option_id,
            "referenceRowHash": _text(reference.get("rowHash")),
        },
    )
    display_type = {
        "gem": "宝石",
        "enchant": "附魔",
        "crafted": "制造属性",
        "embellishment": "美化",
    }.get(option_type, "强化")
    display_value = "/".join(
        _text(value)
        for value in simc_options.values()
        if _text(value)
    )
    option = {
        "optionId": option_id,
        "optionType": option_type,
        "displayName": (
            f"已导入{display_type} {display_value}"
            if display_value
            else f"已导入{display_type}"
        ),
        "applicableSlots": [slot],
        # Catalog exact shapes already own the observed static item facts.  The
        # import-only option carries serializer identity and must not add those
        # facts a second time.
        "statDeltas": {},
        "attributeStaticFactsStatus": "not_applicable",
        "simcOptions": _canonical(simc_options),
        "uniqueGroupId": "",
        "uniqueLimit": 0,
        "sourceRefIds": [evidence_id],
        "authorityKind": "manifest_exact_template",
    }
    evidence = {
        "id": evidence_id,
        "sourceType": "manifest_exact_registry",
        "sourceRevision": registry_revision,
        "optionId": option_id,
        "referenceRowHash": _text(reference.get("rowHash")),
    }
    return option_id, option, evidence


def _enhancement_projection(
    *,
    registry_revision: str,
    authority_identity: str,
    reference: Mapping[str, Any],
    exact_key: str,
    selection_key: str,
    selection: Mapping[str, Any],
    managed_fields: set[str],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    fields = {
        "gemOptionIds": [],
        "enchantOptionId": "",
        "embellishmentOptionId": "",
        "craftedOptionId": "",
        "catalystOptionId": "",
    }
    options: dict[str, Any] = {}
    evidence: dict[str, Any] = {}
    gem_ids = (
        [_text(value) for value in selection.get("gemIds") or []]
        if "gemOptionIds" in managed_fields
        else []
    )
    gem_bonus_ids = [
        _text(value) for value in selection.get("gemBonusIds") or []
    ]
    gem_levels = [
        _text(value) for value in selection.get("gemItemLevels") or []
    ]
    for index, gem_id in enumerate(gem_ids):
        simc = {"gem_id": gem_id}
        if index < len(gem_bonus_ids) and gem_bonus_ids[index]:
            simc["gem_bonus_id"] = gem_bonus_ids[index]
        if index < len(gem_levels) and gem_levels[index]:
            simc["gem_ilevel"] = gem_levels[index]
        option_id, option, record = _option(
            registry_revision=registry_revision,
            authority_identity=authority_identity,
            reference=reference,
            exact_key=exact_key,
            selection_key=selection_key,
            option_type="gem",
            field="gemOptionIds",
            index=index,
            simc_options=simc,
        )
        fields["gemOptionIds"].append(option_id)
        options[option_id] = option
        evidence[record["id"]] = record

    scalar_specs = (
        ("enchantId", "enchantOptionId", "enchant", "enchant_id"),
        (
            "craftedStats",
            "craftedOptionId",
            "crafted",
            "crafted_stats",
        ),
        (
            "embellishmentIds",
            "embellishmentOptionId",
            "embellishment",
            "embellishment",
        ),
    )
    for source_field, intent_field, option_type, simc_field in scalar_specs:
        if intent_field not in managed_fields:
            continue
        raw = selection.get(source_field)
        if isinstance(raw, (list, tuple)):
            tokens = [_text(value) for value in raw if _text(value)]
            value = "/".join(tokens)
        else:
            value = _text(raw)
        if not value:
            continue
        option_id, option, record = _option(
            registry_revision=registry_revision,
            authority_identity=authority_identity,
            reference=reference,
            exact_key=exact_key,
            selection_key=selection_key,
            option_type=option_type,
            field=intent_field,
            index=0,
            simc_options={simc_field: value},
        )
        fields[intent_field] = option_id
        options[option_id] = option
        evidence[record["id"]] = record
    return fields, options, evidence


def _refs_for_identity(
    registry: Mapping[str, Any],
    authority_identity: str,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for raw in registry.get("templateReferences") or []:
        row = _canonical(raw) if isinstance(raw, Mapping) else {}
        if (
            _text(row.get("templateScope")) == "community"
            and _text(row.get("templateAuthorityIdentity"))
            == authority_identity
        ):
            grouped.setdefault(
                _text(row.get("templateContentHash")),
                [],
            ).append(row)
    if len(grouped) != 1:
        code = (
            "EXACT_TEMPLATE_AUTHORITY_MISSING"
            if not grouped
            else "EXACT_TEMPLATE_AUTHORITY_AMBIGUOUS"
        )
        return [], [
            _problem(
                code,
                "exactRegistry.templateReferences",
                "One server template identity must bind exactly one exact content group.",
            )
        ]
    return next(iter(grouped.values())), []


def community_template_exact_import_readiness(
    exact_registry: Any,
    template_authority_identity: Any,
) -> dict[str, Any]:
    """Return the public import availability for one sealed community template.

    This is a deliberately smaller preflight than ``project_exact_template_intent``:
    browse needs to avoid offering an import that the exact projection will reject,
    without exposing the source Selection Intent or Exact instance identities.  The
    import endpoint still performs the full projection and remains the authority.
    """

    registry = exact_registry if isinstance(exact_registry, Mapping) else {}
    authority_identity = _text(template_authority_identity)
    if not _SHA256_PATTERN.fullmatch(authority_identity):
        return {
            "status": "blocked",
            "problemCodes": ["EXACT_TEMPLATE_AUTHORITY_INVALID"],
        }
    refs, problems = _refs_for_identity(registry, authority_identity)
    if problems:
        return {
            "status": "blocked",
            "problemCodes": sorted(
                {
                    _text(problem.get("code"))
                    for problem in problems
                    if _text(problem.get("code"))
                }
            ),
        }
    slots: set[str] = set()
    for reference in refs:
        slot = _text(reference.get("slot"))
        if not slot or slot in slots:
            return {
                "status": "blocked",
                "problemCodes": ["EXACT_TEMPLATE_SLOT_AMBIGUOUS"],
            }
        slots.add(slot)
        if (
            reference.get("validationStatus") != "verified"
            or reference.get("problemCodes")
            or not _text(reference.get("exactItemInstanceKey"))
        ):
            return {
                "status": "partial",
                "problemCodes": ["EXACT_TEMPLATE_REFERENCE_NOT_VERIFIED"],
            }
    return {"status": "verified", "problemCodes": []}


def _project_identity(
    selection_intent: Any,
    exact_registry: Any,
    catalog: Any,
    authority_identity: str,
) -> dict[str, Any]:
    intent = (
        copy.deepcopy(selection_intent)
        if isinstance(selection_intent, Mapping)
        else {}
    )
    registry = (
        exact_registry if isinstance(exact_registry, Mapping) else {}
    )
    catalog_value = catalog if isinstance(catalog, Mapping) else {}
    if not _SHA256_PATTERN.fullmatch(authority_identity):
        return _blocked(
            _problem(
                "EXACT_TEMPLATE_AUTHORITY_INVALID",
                "templateAuthorityIdentity",
                "A server-issued template authority identity is required.",
            )
        )
    authored = (
        intent.get("authoredAgainst")
        if isinstance(intent.get("authoredAgainst"), Mapping)
        else {}
    )
    if _text(registry.get("catalogRevision")) != _text(
        authored.get("gearCatalogRevision")
    ):
        return _blocked(
            _problem(
                "EXACT_TEMPLATE_CATALOG_REVISION_CONFLICT",
                "selectionIntent.authoredAgainst.gearCatalogRevision",
                "Selection Intent and Exact Registry Catalog revisions differ.",
            )
        )
    if (
        _text(catalog_value.get("catalogRevision"))
        != _text(registry.get("catalogRevision"))
    ):
        return _blocked(
            _problem(
                "EXACT_TEMPLATE_CATALOG_REVISION_CONFLICT",
                "gearCatalog.catalogRevision",
                "Catalog and Exact Registry revisions differ.",
            )
        )
    refs, ref_problems = _refs_for_identity(registry, authority_identity)
    if ref_problems:
        return _blocked(*ref_problems)
    aliases, alias_problems = _catalog_source_aliases(catalog_value)
    if alias_problems:
        return _blocked(*alias_problems)
    catalog_browse_item_ids = {
        _text(row.get("browseVariantKey")): _text(row.get("itemId"))
        for row in (catalog_value.get("browseVariants") or [])
        if isinstance(row, Mapping)
        and row.get("evidenceStatus") == "verified"
        and _text(row.get("browseVariantKey"))
        and _text(row.get("itemId"))
    }
    instances = _unique_index(
        registry.get("exactItemInstances"),
        "exactItemInstanceKey",
    )
    selections = _unique_index(
        registry.get("enhancementSelections"),
        "enhancementSelectionKey",
    )
    if instances is None or selections is None:
        return _blocked(
            _problem(
                "EXACT_TEMPLATE_REGISTRY_IDENTITY_INVALID",
                "exactRegistry",
                "Exact instance or enhancement identities are invalid.",
            )
        )

    slots = intent.get("slots") if isinstance(intent.get("slots"), Mapping) else {}
    refs_by_slot: dict[str, dict[str, Any]] = {}
    for reference in refs:
        slot = _text(reference.get("slot"))
        if not slot or slot in refs_by_slot:
            return _blocked(
                _problem(
                    "EXACT_TEMPLATE_SLOT_AMBIGUOUS",
                    f"exactRegistry.templateReferences.{slot or 'unknown'}",
                    "One exact template must contain one reference per slot.",
                )
            )
        if (
            reference.get("validationStatus") != "verified"
            or reference.get("problemCodes")
            or not _text(reference.get("exactItemInstanceKey"))
        ):
            return _blocked(
                _problem(
                    "EXACT_TEMPLATE_REFERENCE_NOT_VERIFIED",
                    f"exactRegistry.templateReferences.{slot}",
                    "Partial or blocked exact evidence cannot become an import option.",
                )
            )
        refs_by_slot[slot] = reference
    if set(refs_by_slot) != set(slots):
        return _blocked(
            _problem(
                "EXACT_TEMPLATE_SLOT_SET_MISMATCH",
                "selectionIntent.slots",
                "Selection Intent and exact template slot sets differ.",
            )
        )

    projected = copy.deepcopy(intent)
    projected_slots = projected["slots"]
    options: dict[str, Any] = {}
    evidence: dict[str, Any] = {}
    visible: dict[str, Any] = {}
    for slot in sorted(refs_by_slot):
        reference = refs_by_slot[slot]
        current = slots.get(slot) if isinstance(slots.get(slot), Mapping) else {}
        item_id = _text(reference.get("itemId"))
        source_variant = _text(reference.get("sourceVariantKey"))
        browse_key = aliases.get((item_id, source_variant))
        selected_variant = _text(current.get("variantKey"))
        rebound_source_variant = _text(
            current.get("_catalogSourceVariantKey")
        )
        catalog_rebound = (
            not browse_key
            and rebound_source_variant == source_variant
            and catalog_browse_item_ids.get(selected_variant) == item_id
        )
        if (
            _text(current.get("itemId")) != item_id
            or (
                selected_variant != (browse_key or source_variant)
                and not catalog_rebound
            )
        ):
            return _blocked(
                _problem(
                    "EXACT_TEMPLATE_CATALOG_SELECTION_MISMATCH",
                    f"selectionIntent.slots.{slot}",
                    "The exact template item is outside the selected Catalog variant.",
                )
            )
        exact_key = _text(reference.get("exactItemInstanceKey"))
        instance = instances.get(exact_key)
        if (
            not isinstance(instance, Mapping)
            or _text(instance.get("itemId")) != item_id
        ):
            return _blocked(
                _problem(
                    "EXACT_TEMPLATE_INSTANCE_UNAVAILABLE",
                    f"exactRegistry.exactItemInstances.{exact_key}",
                    "The referenced exact item instance is unavailable.",
                )
            )
        selection_key = _text(instance.get("enhancementSelectionKey"))
        selection_row = selections.get(selection_key)
        exact_selection = (
            selection_row.get("selection")
            if isinstance(selection_row, Mapping)
            and isinstance(selection_row.get("selection"), Mapping)
            else None
        )
        if exact_selection is None:
            return _blocked(
                _problem(
                    "EXACT_TEMPLATE_ENHANCEMENT_UNAVAILABLE",
                    f"exactRegistry.enhancementSelections.{selection_key}",
                    "The referenced exact enhancement selection is unavailable.",
                )
            )
        fields, slot_options, slot_evidence = _enhancement_projection(
            registry_revision=_text(registry.get("registryRevision")),
            authority_identity=authority_identity,
            reference=reference,
            exact_key=exact_key,
            selection_key=selection_key,
            selection=exact_selection,
            managed_fields={
                _text(field)
                for field in reference.get(
                    "editorManagedEnhancementFields"
                )
                or []
                if _text(field) in _ENHANCEMENT_FIELDS
            },
        )
        projected_slots[slot].update(fields)
        options.update(slot_options)
        evidence.update(slot_evidence)
        if slot_options:
            visible[slot] = {
                option_id: {
                    "optionKey": option_id,
                    "optionType": option["optionType"],
                    "name": option["displayName"],
                }
                for option_id, option in sorted(slot_options.items())
            }
    return {
        "status": "verified",
        "templateAuthorityIdentity": authority_identity,
        "selectionIntent": _canonical(projected),
        "optionsById": _canonical(options),
        "evidenceRecordsById": _canonical(evidence),
        "visibleOptionsBySlot": _canonical(visible),
        "problemCodes": [],
        "problems": [],
    }


def project_exact_template_intent(
    selection_intent: Any,
    exact_registry: Any,
    catalog: Any,
    template_authority_identity: Any,
) -> dict[str, Any]:
    """Project one server-identified template onto exact import-only options."""

    return _project_identity(
        selection_intent,
        exact_registry,
        catalog,
        _text(template_authority_identity),
    )


def has_exact_template_option(selection_intent: Any) -> bool:
    intent = (
        selection_intent if isinstance(selection_intent, Mapping) else {}
    )
    slots = intent.get("slots") if isinstance(intent.get("slots"), Mapping) else {}
    for selection in slots.values():
        if not isinstance(selection, Mapping):
            continue
        values: list[Any] = list(selection.get("gemOptionIds") or [])
        values.extend(selection.get(field) for field in _ENHANCEMENT_FIELDS[1:])
        if any(
            EXACT_TEMPLATE_OPTION_PATTERN.fullmatch(_text(value))
            for value in values
            if _text(value)
        ):
            return True
    return False


def _enhancement_semantics(intent: Mapping[str, Any]) -> dict[str, Any]:
    slots = intent.get("slots") if isinstance(intent.get("slots"), Mapping) else {}
    return {
        slot: {
            field: _canonical(selection.get(field))
            for field in _ENHANCEMENT_FIELDS
        }
        for slot, selection in sorted(slots.items())
        if isinstance(selection, Mapping)
    }


def _preserves_exact_projection(
    projected_intent: Mapping[str, Any],
    current_intent: Mapping[str, Any],
) -> bool:
    projected = _enhancement_semantics(projected_intent)
    current = _enhancement_semantics(current_intent)
    if set(projected) != set(current):
        return False
    for slot, projected_selection in projected.items():
        current_selection = current.get(slot) or {}
        for field in _ENHANCEMENT_FIELDS:
            projected_value = projected_selection.get(field)
            current_value = current_selection.get(field)
            projected_values = (
                projected_value
                if isinstance(projected_value, list)
                else [projected_value]
            )
            current_values = (
                current_value
                if isinstance(current_value, list)
                else [current_value]
            )
            projected_exact = [
                _text(value)
                for value in projected_values
                if EXACT_TEMPLATE_OPTION_PATTERN.fullmatch(_text(value))
            ]
            current_exact = [
                _text(value)
                for value in current_values
                if EXACT_TEMPLATE_OPTION_PATTERN.fullmatch(_text(value))
            ]
            if projected_exact:
                # Exact option identities remain valid only inside their
                # originating whole-template projection.  The editor may,
                # however, replace or remove an imported enhancement with a
                # normal catalog option; the Resolver will validate that
                # catalog option against the injected canonical authority.
                # Retain the strict boundary for any exact identities that
                # remain in the edited selection.
                if any(value not in projected_exact for value in current_exact):
                    return False
            elif current_exact:
                return False
    return True


def _base_template_identity_candidates(
    intent: Mapping[str, Any],
    registry: Mapping[str, Any],
    catalog: Any,
) -> list[str]:
    """Narrow whole-template candidates without rebuilding Exact indexes."""

    slots = (
        intent.get("slots")
        if isinstance(intent.get("slots"), Mapping)
        else {}
    )
    aliases, alias_problems = _catalog_source_aliases(catalog)
    if alias_problems or not slots:
        return []
    grouped: dict[
        str,
        dict[str, list[Mapping[str, Any]]],
    ] = {}
    for raw in registry.get("templateReferences") or []:
        if not isinstance(raw, Mapping):
            continue
        identity = _text(raw.get("templateAuthorityIdentity"))
        content_hash = _text(raw.get("templateContentHash"))
        if (
            _text(raw.get("templateScope")) != "community"
            or not _SHA256_PATTERN.fullmatch(identity)
            or not content_hash
        ):
            continue
        grouped.setdefault(identity, {}).setdefault(
            content_hash,
            [],
        ).append(raw)
    matches = []
    for identity, content_groups in grouped.items():
        if len(content_groups) != 1:
            continue
        refs = next(iter(content_groups.values()))
        if len(refs) != len(slots):
            continue
        seen_slots = set()
        matched = True
        for reference in refs:
            slot = _text(reference.get("slot"))
            current = slots.get(slot)
            item_id = _text(reference.get("itemId"))
            source_variant = _text(
                reference.get("sourceVariantKey")
            )
            browse_key = aliases.get((item_id, source_variant))
            expected_variant = browse_key or source_variant
            if (
                not slot
                or slot in seen_slots
                or not isinstance(current, Mapping)
                or _text(current.get("itemId")) != item_id
                or _text(current.get("variantKey")) != expected_variant
            ):
                matched = False
                break
            seen_slots.add(slot)
        if matched and seen_slots == set(slots):
            matches.append(identity)
    return sorted(matches)


def _inject_authority(
    authority_context: Any,
    projection: Mapping[str, Any],
    exact_registry: Mapping[str, Any],
) -> dict[str, Any]:
    context = (
        copy.deepcopy(authority_context)
        if isinstance(authority_context, Mapping)
        else {}
    )
    options = context.setdefault("optionsById", {})
    evidence = context.setdefault("evidenceRecordsById", {})
    options.update(copy.deepcopy(projection.get("optionsById") or {}))
    evidence.update(
        copy.deepcopy(projection.get("evidenceRecordsById") or {})
    )
    intent = projection["selectionIntent"]
    items = context.setdefault("itemsById", {})
    variants = context.setdefault("variantsByKey", {})

    def extend_capabilities(
        owner: dict[str, Any],
        capabilities: dict[str, Any],
        selection: Mapping[str, Any],
        slot: str,
        inherited: Mapping[str, Any] | None = None,
    ) -> None:
        option_specs = (
            (
                "gemOptionIds",
                "allowedGemOptionIds",
                "socketCount",
                {"gem"},
            ),
            (
                "enchantOptionId",
                "allowedEnchantOptionIds",
                "canEnchant",
                {"enchant", "runeforge"},
            ),
            (
                "embellishmentOptionId",
                "allowedEmbellishmentOptionIds",
                "canEmbellish",
                {"embellishment"},
            ),
            (
                "craftedOptionId",
                "allowedCraftedOptionIds",
                "",
                {"crafted"},
            ),
        )
        inherited_capabilities = (
            inherited if isinstance(inherited, Mapping) else {}
        )

        def verified_allowed(
            values: Iterable[Any],
            option_types: set[str],
        ) -> list[str]:
            allowed_ids = []
            for value in values or []:
                option_id = _text(value)
                option = options.get(option_id)
                applicable = (
                    option.get("applicableSlots")
                    if isinstance(option, Mapping)
                    else []
                )
                if (
                    not option_id
                    or not isinstance(option, Mapping)
                    or _text(option.get("optionType")) not in option_types
                    or (
                        applicable
                        and slot not in applicable
                        and "*" not in applicable
                    )
                ):
                    continue
                allowed_ids.append(option_id)
            return allowed_ids

        for (
            intent_field,
            allowed_field,
            capability_field,
            option_types,
        ) in option_specs:
            raw = selection.get(intent_field)
            selected = raw if isinstance(raw, list) else [raw]
            selected = [
                _text(value)
                for value in selected
                if EXACT_TEMPLATE_OPTION_PATTERN.fullmatch(_text(value))
            ]
            if not selected:
                continue
            allowed = sorted(
                {
                    *verified_allowed(
                        owner.get(allowed_field) or [],
                        option_types,
                    ),
                    *verified_allowed(
                        capabilities.get(allowed_field) or [],
                        option_types,
                    ),
                    *verified_allowed(
                        inherited_capabilities.get(allowed_field) or [],
                        option_types,
                    ),
                    # An editor-managed Exact option proves the effective
                    # capability even when the base Catalog item does not
                    # own it (for example, a socket granted by the observed
                    # item instance). Publish every canonical option that is
                    # applicable to this slot so the player can replace the
                    # imported value; the Resolver remains the authority for
                    # legality, capacity, uniqueness, and aggregate limits.
                    *verified_allowed(options, option_types),
                    *verified_allowed(selected, option_types),
                }
            )
            owner[allowed_field] = allowed
            capabilities[allowed_field] = list(allowed)
            if capability_field == "socketCount":
                count = max(
                    int(owner.get("socketCount") or 0),
                    int(capabilities.get("socketCount") or 0),
                    len(selected),
                )
                owner["socketCount"] = count
                capabilities["socketCount"] = count
            elif capability_field:
                owner[capability_field] = True
                capabilities[capability_field] = True

    for slot, selection in intent["slots"].items():
        item = items.get(selection["itemId"])
        item_capabilities = None
        if isinstance(item, dict):
            item_capabilities = item.setdefault(
                "baseCapabilities",
                {},
            )
            extend_capabilities(
                item,
                item_capabilities,
                selection,
                slot,
            )
        variant = variants.get(selection["variantKey"])
        if isinstance(variant, dict):
            overrides = variant.setdefault(
                "capabilityOverrides",
                {},
            )
            # Variant overrides are applied after item capabilities, so exact
            # import permissions must be present at this final stage as well.
            extend_capabilities(
                overrides,
                overrides,
                selection,
                slot,
                inherited=item_capabilities,
            )

    exact_option_ids = set(projection.get("optionsById") or {})
    context["missingFields"] = sorted(
        {
            _text(path)
            for path in context.get("missingFields") or []
            if _text(path)
            and not (
                _text(path).startswith("optionsById.")
                and _text(path)[len("optionsById.") :] in exact_option_ids
            )
        }
    )
    vector = context.setdefault("dependencyVector", {})
    manifest = (
        context.get("manifest")
        if isinstance(context.get("manifest"), Mapping)
        else {}
    )
    vector["templateOriginSignature"] = projection[
        "templateAuthorityIdentity"
    ]
    community_revision = _text(
        manifest.get("communityTemplateReleaseId")
        or manifest.get("communityTemplateRevision")
    )
    if community_revision:
        vector["communityTemplateRevision"] = community_revision
    gear_release_id = _text(manifest.get("gearCatalogReleaseId"))
    if gear_release_id:
        vector["validatedAgainstGearReleaseId"] = gear_release_id
    registry_revision = _text(exact_registry.get("registryRevision"))
    if registry_revision:
        vector["gearExactRegistryRevision"] = registry_revision
    return _canonical(context)


def bind_exact_template_authority(
    selection_intent: Any,
    authority_context: Any,
    exact_registry: Any,
    catalog: Any,
    template_authority_identity: Any = "",
) -> dict[str, Any]:
    """Bind a saved Intent to exactly one whole-template Exact authority."""

    intent = (
        _canonical(selection_intent)
        if isinstance(selection_intent, Mapping)
        else {}
    )
    registry = exact_registry if isinstance(exact_registry, Mapping) else {}
    expected_identity = _text(template_authority_identity)
    identities = (
        [expected_identity]
        if _SHA256_PATTERN.fullmatch(expected_identity)
        else _base_template_identity_candidates(
            intent,
            registry,
            catalog,
        )
    )
    matches: list[dict[str, Any]] = []
    for identity in identities:
        projection = _project_identity(
            intent,
            registry,
            catalog,
            identity,
        )
        if (
            projection.get("status") == "verified"
            and _preserves_exact_projection(
                projection["selectionIntent"],
                intent,
            )
        ):
            matches.append(projection)
    if len(matches) == 1:
        bound_selection_intent = _canonical(intent)
        for selection in (
            bound_selection_intent.get("slots") or {}
        ).values():
            if isinstance(selection, dict):
                selection.pop("_catalogSourceVariantKey", None)
        return {
            "status": "verified",
            "templateAuthorityIdentity": matches[0][
                "templateAuthorityIdentity"
            ],
            "selectionIntent": bound_selection_intent,
            "authorityContext": _inject_authority(
                authority_context,
                matches[0],
                registry,
            ),
            "problemCodes": [],
            "problems": [],
        }
    if len(matches) > 1:
        return _blocked(
            _problem(
                "EXACT_TEMPLATE_SELECTION_AMBIGUOUS",
                "selectionIntent",
                "Selection Intent matches multiple exact template authorities.",
            )
        )
    if has_exact_template_option(intent):
        return _blocked(
            _problem(
                "EXACT_TEMPLATE_OPTION_NOT_AUTHORIZED",
                "selectionIntent.slots",
                "An exact import option is stale, forged, or mixed across templates.",
            )
        )
    return {
        "status": "not_applicable",
        "selectionIntent": intent,
        "authorityContext": _canonical(authority_context),
        "problemCodes": [],
        "problems": [],
    }


__all__ = (
    "EXACT_TEMPLATE_OPTION_PREFIX",
    "bind_exact_template_authority",
    "community_template_exact_import_readiness",
    "has_exact_template_option",
    "project_exact_template_intent",
)
