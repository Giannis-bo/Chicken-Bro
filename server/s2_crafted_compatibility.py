"""Join official S2 crafted-equipment recipes to legal reagent categories."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

from server.s2_official_api_fact_snapshot import validate_capture_manifest


SCHEMA_REVISION = "s2-crafted-slot-category-targets-v1"
_ID_PATTERN = re.compile(r"^[1-9][0-9]*$")
_RECIPE_PATH = re.compile(r"^/data/wow/recipe/([1-9][0-9]*)$")
_SLOT_PATH = re.compile(
    r"^/data/wow/modified-crafting/reagent-slot-type/([1-9][0-9]*)$"
)


class S2CraftedCompatibilityError(ValueError):
    """Raised when a crafted compatibility join cannot be proven."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _id(value: Any, label: str) -> str:
    value = _text(value)
    if not _ID_PATTERN.fullmatch(value):
        raise S2CraftedCompatibilityError(f"{label} must be a positive integer id")
    return str(int(value))


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise S2CraftedCompatibilityError(f"{label} is invalid") from error
    if not isinstance(value, Mapping):
        raise S2CraftedCompatibilityError(f"{label} must be an object")
    return dict(value)


def _read_capture(
    capture_root: Path,
    *,
    path_pattern: re.Pattern[str],
    label: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    root = Path(capture_root).expanduser().resolve()
    manifest_path = root / "capture-manifest.json"
    raw_manifest = _read_json(manifest_path, f"{label} manifest")
    try:
        manifest = validate_capture_manifest(raw_manifest)
    except Exception as error:
        raise S2CraftedCompatibilityError(f"{label} manifest is invalid") from error
    if manifest["status"] != "captured":
        raise S2CraftedCompatibilityError(f"{label} manifest must be captured")
    payloads: dict[str, dict[str, Any]] = {}
    for entry in manifest["entries"]:
        match = path_pattern.fullmatch(_text(entry.get("path")))
        if not match:
            continue
        relative = _text(entry.get("responsePath"))
        candidate = (root / relative).resolve()
        if (
            not relative
            or Path(relative).is_absolute()
            or candidate == root
            or root not in candidate.parents
            or not candidate.is_file()
        ):
            raise S2CraftedCompatibilityError(
                f"{label} response path escapes capture root: {entry['path']}"
            )
        body = candidate.read_bytes()
        if len(body) != int(entry["responseBytes"]):
            raise S2CraftedCompatibilityError(f"{label} response byte drift: {entry['path']}")
        if hashlib.sha256(body).hexdigest() != entry["responseSha256"]:
            raise S2CraftedCompatibilityError(f"{label} response hash drift: {entry['path']}")
        payload = _read_json(candidate, f"{label} response {entry['path']}")
        payload_id = _id(payload.get("id"), f"{label} response id")
        if payload_id != match.group(1):
            raise S2CraftedCompatibilityError(f"{label} response id mismatch: {entry['path']}")
        previous = payloads.get(payload_id)
        if previous is not None and _canonical_bytes(previous) != _canonical_bytes(payload):
            raise S2CraftedCompatibilityError(f"{label} payload conflict: {payload_id}")
        payloads[payload_id] = payload
    return payloads, manifest


def _load_targets(value: Mapping[str, Any] | Path) -> dict[str, Any]:
    if isinstance(value, Mapping):
        payload = dict(value)
    else:
        payload = _read_json(Path(value).expanduser().resolve(), "crafted targets")
    if payload.get("status") != "verified":
        raise S2CraftedCompatibilityError("crafted output targets must be verified")
    if not isinstance(payload.get("recipeOutputEdges"), list):
        raise S2CraftedCompatibilityError("crafted output targets must contain recipeOutputEdges")
    return payload


def build_crafted_slot_category_targets(
    *,
    recipe_capture_root: Path,
    slot_capture_root: Path,
    crafted_targets: Mapping[str, Any] | Path,
) -> dict[str, Any]:
    """Build the finite category target set for official crafted equipment."""

    recipes, recipe_manifest = _read_capture(
        recipe_capture_root,
        path_pattern=_RECIPE_PATH,
        label="recipe capture",
    )
    slots, slot_manifest = _read_capture(
        slot_capture_root,
        path_pattern=_SLOT_PATH,
        label="slot-type capture",
    )
    targets = _load_targets(crafted_targets)

    equipment_recipe_to_items: dict[str, set[str]] = defaultdict(set)
    for index, edge in enumerate(targets["recipeOutputEdges"]):
        if not isinstance(edge, Mapping):
            raise S2CraftedCompatibilityError(f"crafted output edge {index} is invalid")
        recipe_id = _id(edge.get("recipeId"), f"crafted output edge {index}.recipeId")
        item_id = _id(edge.get("itemId"), f"crafted output edge {index}.itemId")
        if _text(edge.get("status")) != "verified":
            raise S2CraftedCompatibilityError(
                f"crafted output edge {recipe_id}/{item_id} is not verified"
            )
        equipment_recipe_to_items[recipe_id].add(item_id)

    role_recipes: dict[str, set[str]] = defaultdict(set)
    role_names: dict[str, str] = {}
    role_categories: dict[str, set[str]] = defaultdict(set)
    role_category_names: dict[tuple[str, str], str] = {}
    category_roles: dict[str, set[str]] = defaultdict(set)
    category_recipes: dict[str, set[str]] = defaultdict(set)
    category_names: dict[str, str] = {}
    recipes_without_slots: list[str] = []

    for recipe_id, item_ids in sorted(equipment_recipe_to_items.items(), key=lambda pair: int(pair[0])):
        recipe = recipes.get(recipe_id)
        if recipe is None:
            raise S2CraftedCompatibilityError(
                f"crafted output recipe {recipe_id} is missing from official recipe capture"
            )
        slots_value = recipe.get("modified_crafting_slots")
        if slots_value is None:
            recipes_without_slots.append(recipe_id)
            continue
        if not isinstance(slots_value, list):
            raise S2CraftedCompatibilityError(
                f"recipe {recipe_id} modified_crafting_slots must be a list or null"
            )
        for slot_index, recipe_slot in enumerate(slots_value):
            if not isinstance(recipe_slot, Mapping):
                raise S2CraftedCompatibilityError(
                    f"recipe {recipe_id} slot {slot_index} is invalid"
                )
            slot_type = recipe_slot.get("slot_type")
            if not isinstance(slot_type, Mapping):
                raise S2CraftedCompatibilityError(
                    f"recipe {recipe_id} slot {slot_index} has no slot_type"
                )
            role_id = _id(slot_type.get("id"), f"recipe {recipe_id} slot {slot_index}.slot_type.id")
            role_name = _text(slot_type.get("name"))
            if not role_name:
                raise S2CraftedCompatibilityError(
                    f"recipe {recipe_id} slot {slot_index}.slot_type.name is required"
                )
            role_names.setdefault(role_id, role_name)
            if role_names[role_id] != role_name:
                raise S2CraftedCompatibilityError(f"slot type {role_id} name conflicts")
            role_recipes[role_id].add(recipe_id)
            slot_payload = slots.get(role_id)
            if slot_payload is None:
                raise S2CraftedCompatibilityError(
                    f"slot type {role_id} response is missing for recipe {recipe_id}"
                )
            compatible = slot_payload.get("compatible_categories")
            if not isinstance(compatible, list):
                raise S2CraftedCompatibilityError(
                    f"slot type {role_id} compatible_categories is missing"
                )
            for category_index, category in enumerate(compatible):
                if not isinstance(category, Mapping):
                    raise S2CraftedCompatibilityError(
                        f"slot type {role_id} category {category_index} is invalid"
                    )
                category_id = _id(
                    category.get("id"),
                    f"slot type {role_id} category {category_index}.id",
                )
                category_name = _text(category.get("name"))
                if not category_name:
                    raise S2CraftedCompatibilityError(
                        f"slot type {role_id} category {category_id}.name is required"
                    )
                category_names.setdefault(category_id, category_name)
                if category_names[category_id] != category_name:
                    raise S2CraftedCompatibilityError(
                        f"category {category_id} name conflicts"
                    )
                role_category_names[(role_id, category_id)] = category_name
                role_categories[role_id].add(category_id)
                category_roles[category_id].add(role_id)
                category_recipes[category_id].update(item_ids and {recipe_id} or set())

    if not equipment_recipe_to_items:
        raise S2CraftedCompatibilityError("crafted output targets contain no equipment recipes")

    categories = {}
    for category_id in sorted(category_names, key=int):
        categories[category_id] = {
            "id": category_id,
            "name": category_names[category_id],
            "roleIds": sorted(category_roles[category_id], key=int),
            "recipeIds": sorted(category_recipes[category_id], key=int),
            "evidenceStatus": "verified",
            "compatibilityOwner": "blizzard_game_data_api.modified_crafting.reagent_slot_type.compatible_categories",
        }

    roles = []
    for role_id in sorted(role_names, key=int):
        roles.append(
            {
                "id": role_id,
                "name": role_names[role_id],
                "recipeIds": sorted(role_recipes[role_id], key=int),
                "categoryIds": sorted(role_categories[role_id], key=int),
                "evidenceStatus": "verified",
            }
        )

    return {
        "schemaRevision": SCHEMA_REVISION,
        "status": "verified",
        "seasonKey": "midnight-season-2",
        "authority": "blizzard_game_data_api",
        "recipeCaptureRoot": Path(recipe_capture_root).expanduser().resolve().name,
        "slotCaptureRoot": Path(slot_capture_root).expanduser().resolve().name,
        "recipeCaptureManifestSha256": hashlib.sha256(
            _canonical_bytes(recipe_manifest)
        ).hexdigest(),
        "slotCaptureManifestSha256": hashlib.sha256(
            _canonical_bytes(slot_manifest)
        ).hexdigest(),
        "equipmentRecipeCount": len(equipment_recipe_to_items),
        "equipmentOutputItemCount": len({item_id for items in equipment_recipe_to_items.values() for item_id in items}),
        "recipeCountWithoutModifiedCraftingSlots": len(recipes_without_slots),
        "recipesWithoutModifiedCraftingSlots": recipes_without_slots,
        "roleIds": sorted(role_names, key=int),
        "categoryIds": sorted(category_names, key=int),
        "roles": roles,
        "categories": categories,
        "equipmentRecipes": [
            {
                "recipeId": recipe_id,
                "itemIds": sorted(item_ids, key=int),
                "roleIds": sorted(
                    [role_id for role_id, recipe_ids in role_recipes.items() if recipe_id in recipe_ids],
                    key=int,
                ),
                "evidenceStatus": "verified",
            }
            for recipe_id, item_ids in sorted(equipment_recipe_to_items.items(), key=lambda pair: int(pair[0]))
        ],
    }


__all__ = [
    "SCHEMA_REVISION",
    "S2CraftedCompatibilityError",
    "build_crafted_slot_category_targets",
]
