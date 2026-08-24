"""Resolve official crafted-equipment compatibility into auditable options."""

from __future__ import annotations

import json
import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_REVISION = "s2-crafted-compatibility-evidence-v1"
SECONDARY_ROLE_IDS = frozenset({"393", "459"})
EMBELLISHMENT_ROLE_IDS = frozenset({"389", "390", "391", "499", "501", "502"})
CREST_ROLE_IDS = frozenset({"392"})
SPARK_ROLE_IDS = frozenset({"401", "500"})
SOCKET_ROLE_IDS = frozenset({"427", "428"})
EMPOWER_ROLE_IDS = frozenset({"469", "470"})
ENHANCEMENT_ROLE_IDS = frozenset(
    SECONDARY_ROLE_IDS
    | EMBELLISHMENT_ROLE_IDS
    | CREST_ROLE_IDS
    | SPARK_ROLE_IDS
    | SOCKET_ROLE_IDS
    | EMPOWER_ROLE_IDS
)
OUT_OF_SCOPE_CATEGORY_REASONS = {
    "740": "OUT_OF_SCOPE_PREVIOUS_SEASON_SPARK",
    "901": "OUT_OF_SCOPE_PREVIOUS_SEASON_CREST",
    "902": "OUT_OF_SCOPE_DUNGEON_UPGRADE_CATEGORY",
}


class S2CraftedCompatibilityEvidenceError(ValueError):
    """Raised when a crafted compatibility evidence join is malformed."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _canonical(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _id(value: Any, label: str) -> str:
    text = _text(value)
    if not text.isdigit() or int(text) <= 0:
        raise S2CraftedCompatibilityEvidenceError(f"{label} must be a positive integer id")
    return str(int(text))


def _row_refs(
    row: Mapping[str, Any],
    *,
    table: str,
    db2_refs: Mapping[tuple[str, str], Sequence[str]],
) -> set[str]:
    key = json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return set(db2_refs.get((table, key), []))


def _official_option_fact(item_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    modified = payload.get("modified_crafting") if isinstance(payload.get("modified_crafting"), Mapping) else {}
    category = modified.get("category") if isinstance(modified.get("category"), Mapping) else {}
    item_class = payload.get("item_class") if isinstance(payload.get("item_class"), Mapping) else {}
    item_subclass = payload.get("item_subclass") if isinstance(payload.get("item_subclass"), Mapping) else {}
    quality = payload.get("quality") if isinstance(payload.get("quality"), Mapping) else {}
    return {
        "itemId": item_id,
        "name": _text(payload.get("name")),
        "isEquippable": payload.get("is_equippable") is True,
        "itemClassId": item_class.get("id"),
        "itemSubclassId": item_subclass.get("id"),
        "quality": _text(quality.get("type")),
        "modifiedCraftingCategoryId": _text(category.get("id")) or None,
        "evidenceStatus": "verified",
    }


def _category_status(
    category_id: str,
    *,
    target: Mapping[str, Any],
    db2_category: Mapping[str, Any] | None,
    option_items: list[dict[str, Any]],
    currency_options: list[dict[str, Any]],
    missing_ids: set[str],
    conflicts: list[str],
    requires_option_identity: bool,
) -> tuple[str, str | None]:
    excluded_reason = OUT_OF_SCOPE_CATEGORY_REASONS.get(category_id)
    if excluded_reason:
        return "excluded", excluded_reason
    target_role_ids = {_text(value) for value in target.get("roleIds") or []}
    if target_role_ids and target_role_ids <= SOCKET_ROLE_IDS:
        # Socket categories are virtual compatibility edges.  The official
        # slot-type response proves the role/category edge; it does not name a
        # public reagent item, so an Item identity is not required here.
        return "verified", "SOCKET_VIRTUAL_CATEGORY_EDGE"
    if db2_category is None and not requires_option_identity:
        return "observed", "CRAFTED_CATEGORY_DB2_DEFINITION_MISSING_NON_PUBLIC_INPUT"
    if db2_category is None:
        return "UNVERIFIED", "CRAFTED_CATEGORY_DB2_DEFINITION_MISSING"
    if currency_options:
        if all(_text(option.get("evidenceStatus")) == "verified" for option in currency_options):
            return "verified", "CRAFTED_CURRENCY_REAGENT_EDGE"
        return "UNVERIFIED", "CRAFTED_CURRENCY_IDENTITY_UNVERIFIED"
    if not option_items and not requires_option_identity:
        return "observed", "CRAFTED_CATEGORY_OPTION_ITEMS_NOT_REQUIRED_FOR_INPUT"
    if not option_items:
        return "UNVERIFIED", "CRAFTED_CATEGORY_OPTION_ITEMS_MISSING"
    if missing_ids and requires_option_identity:
        return "UNVERIFIED", "CRAFTED_OPTION_ITEM_OFFICIAL_IDENTITY_MISSING"
    if conflicts:
        return "blocked", "CRAFTED_OPTION_CATEGORY_CONFLICT"
    return "verified", None


def _compatibility_for_roles(
    *,
    recipe_id: str,
    role_ids: set[str],
    selected_role_ids: frozenset[str],
    roles_by_id: Mapping[str, Mapping[str, Any]],
    categories: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    relevant_roles = sorted(role_ids & selected_role_ids, key=int)
    if not relevant_roles:
        return {
            "status": "not_applicable",
            "roleIds": [],
            "categoryIds": [],
            "options": [],
            "evidenceRefs": [],
        }
    category_ids: set[str] = set()
    for role_id in relevant_roles:
        role = roles_by_id.get(role_id) or {}
        category_ids.update(_text(value) for value in role.get("categoryIds") or [])
    selected_categories = [categories[category_id] for category_id in sorted(category_ids, key=int) if category_id in categories]
    options = []
    refs: set[str] = set()
    statuses = []
    reasons = []
    for category in selected_categories:
        statuses.append(_text(category.get("status")))
        if category.get("reasonCode"):
            reasons.append(category["reasonCode"])
        refs.update(category.get("evidenceRefs") or [])
        if category.get("status") == "verified":
            options.extend(
                {
                    **dict(option),
                    "categoryId": category["categoryId"],
                    "roleIds": category.get("roleIds") or [],
                    "kind": "item",
                }
                for option in category.get("optionItems") or []
            )
            options.extend(
                {
                    **dict(option),
                    "categoryId": category["categoryId"],
                    "roleIds": category.get("roleIds") or [],
                    "kind": "currency",
                }
                for option in category.get("currencyOptions") or []
            )
    options.sort(
        key=lambda row: (
            int(row["categoryId"]),
            0 if row.get("kind") == "item" else 1,
            int(row.get("itemId") or row.get("currencyTypeId") or 0),
        )
    )
    if any(status == "blocked" for status in statuses):
        status = "blocked"
    elif any(status == "UNVERIFIED" for status in statuses):
        status = "UNVERIFIED"
    elif not [status for status in statuses if status != "excluded"]:
        status = "excluded"
    else:
        status = "verified"
    return {
        "status": status,
        "roleIds": relevant_roles,
        "categoryIds": sorted(category_ids, key=int),
        "options": options,
        "reasonCode": sorted(set(reasons))[0] if reasons else None,
        "evidenceRefs": sorted(refs),
    }


def build_crafted_compatibility_evidence(
    targets: Mapping[str, Any],
    *,
    db2_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    db2_refs: Mapping[tuple[str, str], Sequence[str]],
    official_items: Mapping[str, Mapping[str, Any]],
    official_refs: Mapping[str, Sequence[str]],
    official_missing: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Join slot categories, bounded DB2 option edges, and API identities."""

    if _text(targets.get("status")) != "verified":
        raise S2CraftedCompatibilityEvidenceError("crafted compatibility targets must be verified")
    target_categories = targets.get("categories")
    target_roles = targets.get("roles")
    target_recipes = targets.get("equipmentRecipes")
    if not isinstance(target_categories, Mapping) or not isinstance(target_roles, list) or not isinstance(target_recipes, list):
        raise S2CraftedCompatibilityEvidenceError("crafted compatibility targets are incomplete")

    db2_categories = {
        _id(row.get("ID"), "ModifiedCraftingCategory.ID"): dict(row)
        for row in db2_rows.get("ModifiedCraftingCategory", [])
        if row.get("ID") not in (None, "", 0, "0")
    }
    modifier_categories = {
        _id(row.get("ID"), "ModifiedCraftingReagentItem.ID"): _id(
            row.get("ModifiedCraftingCategoryID"),
            "ModifiedCraftingReagentItem.ModifiedCraftingCategoryID",
        )
        for row in db2_rows.get("ModifiedCraftingReagentItem", [])
        if row.get("ID") not in (None, "", 0, "0")
        and row.get("ModifiedCraftingCategoryID") not in (None, "", 0, "0")
    }
    category_item_ids: dict[str, set[str]] = defaultdict(set)
    category_refs: dict[str, set[str]] = defaultdict(set)
    currency_by_id = {
        _id(row.get("ID"), "CurrencyTypes.ID"): dict(row)
        for row in db2_rows.get("CurrencyTypes", [])
        if row.get("ID") not in (None, "", 0, "0")
    }
    category_currency_options: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in db2_rows.get("ModifiedCraftingReagentItem", []):
        if row.get("ID") in (None, "", 0, "0"):
            continue
        modifier_id = _id(row.get("ID"), "ModifiedCraftingReagentItem.ID")
        category_id = modifier_categories.get(modifier_id)
        if category_id:
            category_refs[category_id].update(
                _row_refs(row, table="ModifiedCraftingReagentItem", db2_refs=db2_refs)
            )
    for row in db2_rows.get("ModifiedCraftingItem", []):
        if row.get("ItemID") in (None, "", 0, "0") or row.get("ModifiedCraftingReagentItemID") in (None, "", 0, "0"):
            continue
        item_id = _id(row.get("ItemID"), "ModifiedCraftingItem.ItemID")
        modifier_id = _id(row.get("ModifiedCraftingReagentItemID"), "ModifiedCraftingItem.ModifiedCraftingReagentItemID")
        category_id = modifier_categories.get(modifier_id)
        if category_id:
            category_item_ids[category_id].add(item_id)
            category_refs[category_id].update(_row_refs(row, table="ModifiedCraftingItem", db2_refs=db2_refs))
    for row in db2_rows.get("CraftingReagentQuality", []):
        if row.get("ModifiedCraftingCategoryID") in (None, "", 0, "0"):
            continue
        category_id = _id(row.get("ModifiedCraftingCategoryID"), "CraftingReagentQuality.ModifiedCraftingCategoryID")
        category_refs[category_id].update(_row_refs(row, table="CraftingReagentQuality", db2_refs=db2_refs))
        if row.get("ItemID") not in (None, "", 0, "0"):
            item_id = _id(row.get("ItemID"), "CraftingReagentQuality.ItemID")
            category_item_ids[category_id].add(item_id)
        currency_id = row.get("CurrencyTypesID")
        if currency_id not in (None, "", 0, "0"):
            normalized_currency_id = _id(currency_id, "CraftingReagentQuality.CurrencyTypesID")
            currency = currency_by_id.get(normalized_currency_id)
            currency_refs = _row_refs(row, table="CraftingReagentQuality", db2_refs=db2_refs)
            if currency is not None:
                currency_refs.update(
                    _row_refs(currency, table="CurrencyTypes", db2_refs=db2_refs)
                )
            category_currency_options[category_id].append(
                {
                    "currencyTypeId": normalized_currency_id,
                    "name": _text((currency or {}).get("Name_lang")),
                    "quality": (currency or {}).get("Quality"),
                    "currencyCategoryId": (currency or {}).get("CategoryID"),
                    "description": _text((currency or {}).get("Description_lang")),
                    "orderIndex": row.get("OrderIndex"),
                    "maxDifficultyAdjustment": row.get("MaxDifficultyAdjustment"),
                    "reagentEffectPct": row.get("ReagentEffectPct"),
                    "evidenceStatus": "verified" if currency is not None else "UNVERIFIED",
                    "evidenceRefs": sorted(currency_refs),
                }
            )

    missing_by_id = {
        _id(row.get("itemId"), "official missing itemId"): dict(row)
        for row in official_missing
        if row.get("itemId") not in (None, "", 0, "0")
    }
    categories: dict[str, dict[str, Any]] = {}
    blockers: set[str] = set()
    exclusions: list[dict[str, Any]] = []
    for category_id in sorted((_id(value, "target category id") for value in targets.get("categoryIds") or []), key=int):
        target_category = target_categories.get(category_id) or {}
        db2_category = db2_categories.get(category_id)
        option_ids = sorted(category_item_ids.get(category_id, set()), key=int)
        option_items = []
        currency_options = sorted(
            category_currency_options.get(category_id, []),
            key=lambda row: (int(row.get("orderIndex") or 0), int(row["currencyTypeId"])),
        )
        missing_ids = set()
        conflicts = []
        for item_id in option_ids:
            payload = official_items.get(item_id)
            if payload is None:
                missing_ids.add(item_id)
                continue
            fact = _official_option_fact(item_id, payload)
            official_category_id = fact.get("modifiedCraftingCategoryId")
            if official_category_id and official_category_id != category_id:
                conflicts.append(item_id)
                continue
            option_items.append(
                {
                    **fact,
                    "evidenceRefs": sorted(
                        set(official_refs.get(item_id, [])) | category_refs.get(category_id, set())
                    ),
                }
            )
        status, reason = _category_status(
            category_id,
            target=target_category,
            db2_category=db2_category,
            option_items=option_items,
            currency_options=currency_options,
            missing_ids=missing_ids,
            conflicts=conflicts,
            requires_option_identity=bool(
                {
                    _text(value) for value in target_category.get("roleIds") or []
                }
                & ENHANCEMENT_ROLE_IDS
            ),
        )
        if status == "UNVERIFIED":
            blockers.add(reason or "CRAFTED_CATEGORY_UNVERIFIED")
        if status == "blocked":
            blockers.add(reason or "CRAFTED_CATEGORY_BLOCKED")
        if status == "excluded":
            exclusions.append(
                {
                    "categoryId": category_id,
                    "reasonCode": reason,
                    "evidenceRefs": sorted(category_refs.get(category_id, set())),
                }
            )
        categories[category_id] = {
            "categoryId": category_id,
            "name": _text(target_category.get("name")) or _text((db2_category or {}).get("DisplayName_lang")),
            "roleIds": sorted({_text(value) for value in target_category.get("roleIds") or []}, key=int),
            "recipeIds": sorted({_text(value) for value in target_category.get("recipeIds") or []}, key=int),
            "status": status,
            "reasonCode": reason,
            "db2EvidenceRefs": sorted(category_refs.get(category_id, set())),
            "optionItemIds": option_ids,
            "missingOptionItemIds": sorted(missing_ids, key=int),
            "conflictingOptionItemIds": sorted(conflicts, key=int),
            "optionItems": sorted(option_items, key=lambda row: int(row["itemId"])),
            "currencyTypeIds": [row["currencyTypeId"] for row in currency_options],
            "currencyOptions": currency_options,
            "evidenceRefs": sorted(
                category_refs.get(category_id, set())
                | {
                    f"official-api:/data/wow/modified-crafting/reagent-slot-type/{role_id}#/compatible_categories"
                    for role_id in target_category.get("roleIds") or []
                }
            ),
        }

    roles_by_id = {
        _id(row.get("id"), "target role id"): dict(row)
        for row in target_roles
    }
    recipes = []
    for raw_recipe in target_recipes:
        recipe_id = _id(raw_recipe.get("recipeId"), "target recipe id")
        role_ids = {_text(value) for value in raw_recipe.get("roleIds") or []}
        secondary = _compatibility_for_roles(
            recipe_id=recipe_id,
            role_ids=role_ids,
            selected_role_ids=SECONDARY_ROLE_IDS,
            roles_by_id=roles_by_id,
            categories=categories,
        )
        embellishment = _compatibility_for_roles(
            recipe_id=recipe_id,
            role_ids=role_ids,
            selected_role_ids=EMBELLISHMENT_ROLE_IDS,
            roles_by_id=roles_by_id,
            categories=categories,
        )
        enhancement = _compatibility_for_roles(
            recipe_id=recipe_id,
            role_ids=role_ids,
            selected_role_ids=ENHANCEMENT_ROLE_IDS,
            roles_by_id=roles_by_id,
            categories=categories,
        )
        recipes.append(
            {
                "recipeId": recipe_id,
                "itemIds": sorted({_id(value, "target recipe itemId") for value in raw_recipe.get("itemIds") or []}, key=int),
                "roleIds": sorted(role_ids, key=int),
                "secondaryStatCompatibility": secondary,
                "embellishmentCompatibility": embellishment,
                "enhancementCompatibility": enhancement,
                "evidenceStatus": "verified"
                if all(value["status"] in {"verified", "not_applicable", "excluded"} for value in (secondary, embellishment, enhancement))
                else "UNVERIFIED",
            }
        )

    # Explicit out-of-scope categories are complete exclusions, not unresolved
    # facts.  They remain visible in the report while the in-scope contract can
    # close as verified when no blocker remains.
    status = "verified" if not blockers else "partial"
    return {
        "schemaRevision": SCHEMA_REVISION,
        "seasonKey": "midnight-season-2",
        "status": status,
        "authority": "blizzard_game_data_api + official_client_db2",
        "categories": categories,
        "roles": [
            {
                "roleId": role_id,
                "name": _text(role.get("name")),
                "categoryIds": sorted({_text(value) for value in role.get("categoryIds") or []}, key=int),
                "recipeIds": sorted({_text(value) for value in role.get("recipeIds") or []}, key=int),
                "evidenceStatus": "verified",
            }
            for role_id, role in sorted(roles_by_id.items(), key=lambda pair: int(pair[0]))
        ],
        "recipes": recipes,
        "blockerCodes": sorted(blockers),
        "exclusions": exclusions,
        "coverage": {
            "categoryCount": len(categories),
            "categoryVerifiedCount": sum(1 for row in categories.values() if row["status"] == "verified"),
            "categoryUnverifiedCount": sum(1 for row in categories.values() if row["status"] == "UNVERIFIED"),
            "categoryBlockedCount": sum(1 for row in categories.values() if row["status"] == "blocked"),
            "categoryExcludedCount": sum(1 for row in categories.values() if row["status"] == "excluded"),
            "recipeCount": len(recipes),
            "recipeCompatibilityVerifiedCount": sum(1 for row in recipes if row["evidenceStatus"] == "verified"),
        },
    }


def _safe_capture_file(root: Path, relative: Any, label: str) -> Path:
    value = _text(relative)
    candidate = (root / value).resolve()
    resolved_root = root.resolve()
    if not value or Path(value).is_absolute() or candidate == resolved_root or resolved_root not in candidate.parents or not candidate.is_file():
        raise S2CraftedCompatibilityEvidenceError(
            f"{label} response path escapes capture root"
        )
    return candidate


def load_db2_capture(capture_root: Path) -> tuple[dict[str, list[dict[str, Any]]], dict[tuple[str, str], list[str]], dict[str, Any]]:
    """Load projected DB2 rows and field-level response references."""

    root = Path(capture_root).expanduser().resolve()
    try:
        manifest = json.loads((root / "capture-manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise S2CraftedCompatibilityEvidenceError("DB2 capture manifest is invalid") from error
    if not isinstance(manifest, Mapping) or manifest.get("status") != "captured":
        raise S2CraftedCompatibilityEvidenceError("DB2 capture must be captured")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise S2CraftedCompatibilityEvidenceError("DB2 capture entries are required")
    rows_by_table: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    refs: dict[tuple[str, str], list[str]] = defaultdict(list)
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise S2CraftedCompatibilityEvidenceError("DB2 capture entry is invalid")
        table = _text(entry.get("table"))
        response_path = _safe_capture_file(root, entry.get("responsePath"), f"DB2 {table}")
        try:
            response = json.loads(response_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise S2CraftedCompatibilityEvidenceError(f"DB2 response is invalid: {table}") from error
        if not isinstance(response, Mapping) or not isinstance(response.get("rows"), list):
            raise S2CraftedCompatibilityEvidenceError(f"DB2 response rows are missing: {table}")
        for row_index, row in enumerate(response["rows"]):
            if not isinstance(row, Mapping):
                raise S2CraftedCompatibilityEvidenceError(f"DB2 row is invalid: {table}")
            normalized = dict(row)
            key = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            rows_by_table[table][key] = normalized
            refs[(table, key)].append(
                f"db2-response:{root.name}/{Path(entry['responsePath']).as_posix()}#/rows/{row_index}"
            )
    return (
        {table: list(rows.values()) for table, rows in rows_by_table.items()},
        {key: sorted(set(value)) for key, value in refs.items()},
        dict(manifest),
    )


def load_official_item_capture(
    capture_root: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]], list[dict[str, Any]], dict[str, Any]]:
    """Load captured item identities while retaining explicit missing/blocker rows."""

    root = Path(capture_root).expanduser().resolve()
    try:
        manifest = json.loads((root / "capture-manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise S2CraftedCompatibilityEvidenceError("official option item manifest is invalid") from error
    if not isinstance(manifest, Mapping) or manifest.get("status") not in {"captured", "partial"}:
        raise S2CraftedCompatibilityEvidenceError("official option item capture must be captured or partial")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise S2CraftedCompatibilityEvidenceError("official option item entries are required")
    items: dict[str, dict[str, Any]] = {}
    refs: dict[str, list[str]] = defaultdict(list)
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise S2CraftedCompatibilityEvidenceError("official option item entry is invalid")
        path = _text(entry.get("path"))
        if not path.startswith("/data/wow/item/"):
            continue
        item_id = _id(path.rsplit("/", 1)[-1], "official item path")
        response_path = _safe_capture_file(root, entry.get("responsePath"), f"official item {item_id}")
        body = response_path.read_bytes()
        if len(body) != int(entry.get("responseBytes")) or hashlib.sha256(body).hexdigest() != _text(entry.get("responseSha256")):
            raise S2CraftedCompatibilityEvidenceError(f"official option item response integrity drift: {item_id}")
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as error:
            raise S2CraftedCompatibilityEvidenceError(f"official option item response is invalid: {item_id}") from error
        if not isinstance(payload, Mapping) or _text(payload.get("id")) != item_id:
            raise S2CraftedCompatibilityEvidenceError(f"official option item id mismatch: {item_id}")
        items[item_id] = dict(payload)
        refs[item_id].extend(
            [
                f"official-api:/data/wow/item/{item_id}#/id",
                f"official-api-response:{root.name}/{Path(entry['responsePath']).as_posix()}",
            ]
        )
    missing = [
        dict(row)
        for key in ("missingItems", "blockedItems")
        for row in manifest.get(key) or []
        if isinstance(row, Mapping)
    ]
    return items, {key: sorted(set(value)) for key, value in refs.items()}, missing, dict(manifest)


def build_crafted_compatibility_evidence_from_captures(
    *,
    targets: Mapping[str, Any] | Path,
    db2_capture_root: Path,
    official_item_capture_root: Path,
) -> dict[str, Any]:
    if isinstance(targets, Mapping):
        target_payload = dict(targets)
    else:
        try:
            target_payload = json.loads(Path(targets).expanduser().resolve().read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise S2CraftedCompatibilityEvidenceError("crafted compatibility targets are invalid") from error
    db2_rows, db2_refs, db2_manifest = load_db2_capture(db2_capture_root)
    official_items, official_refs, official_missing, official_manifest = load_official_item_capture(official_item_capture_root)
    report = build_crafted_compatibility_evidence(
        target_payload,
        db2_rows=db2_rows,
        db2_refs=db2_refs,
        official_items=official_items,
        official_refs=official_refs,
        official_missing=official_missing,
    )
    report["inputs"] = {
        "compatibilityTargets": Path(targets).expanduser().resolve().name if not isinstance(targets, Mapping) else "inline",
        "db2CaptureRoot": Path(db2_capture_root).expanduser().resolve().name,
        "db2CaptureManifestSha256": hashlib.sha256(
            json.dumps(db2_manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "officialItemCaptureRoot": Path(official_item_capture_root).expanduser().resolve().name,
        "officialItemCaptureStatus": official_manifest.get("status"),
        "officialItemCaptureManifestSha256": hashlib.sha256(
            json.dumps(official_manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "officialItemMissingCount": sum(1 for row in official_missing if row.get("status") == "not_found"),
        "officialItemBlockedCount": sum(1 for row in official_missing if row.get("status") != "not_found"),
    }
    return report


__all__ = [
    "SCHEMA_REVISION",
    "S2CraftedCompatibilityEvidenceError",
    "build_crafted_compatibility_evidence",
    "build_crafted_compatibility_evidence_from_captures",
    "load_db2_capture",
    "load_official_item_capture",
]
