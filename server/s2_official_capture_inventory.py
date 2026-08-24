"""Build a read-only source-membership inventory from official API capture.

The inventory is evidence, not a Catalog or Exact registry.  It records the
official item identities and memberships visible in the captured Journal and
item-set graphs, while keeping terminal variants, tracks, crafted outputs and
SimC readiness explicitly unresolved when the API does not expose them.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

try:
    from .s2_official_api_fact_snapshot import (
        LAIR_ENCOUNTER_ID,
        LAIR_INSTANCE_ID,
        MYTHIC_PLUS_INSTANCE_IDS,
        RAID_INSTANCE_ID,
        validate_capture_manifest,
        validate_product_content_scope,
    )
except ImportError:  # pragma: no cover - supports direct module execution
    from s2_official_api_fact_snapshot import (
        LAIR_ENCOUNTER_ID,
        LAIR_INSTANCE_ID,
        MYTHIC_PLUS_INSTANCE_IDS,
        RAID_INSTANCE_ID,
        validate_capture_manifest,
        validate_product_content_scope,
    )


SCHEMA_REVISION = "s2-official-capture-inventory-v1"
REPORT_PREFIX = "s2-official-capture-inventory:sha256:"
_ID_PATTERN = re.compile(r"^[1-9][0-9]*$")


class OfficialCaptureInventoryError(ValueError):
    """Raised when an official capture cannot be audited safely."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _id(value: Any, label: str) -> str:
    text = _text(value)
    if not _ID_PATTERN.fullmatch(text):
        raise OfficialCaptureInventoryError(f"{label} must be a positive integer id")
    return str(int(text))


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise OfficialCaptureInventoryError(f"{label} must be an object")
    return dict(value)


def _load_json(value: Any, label: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    try:
        payload = json.loads(Path(value).expanduser().read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise OfficialCaptureInventoryError(f"unable to load {label}") from error
    return _mapping(payload, label)


def _safe_response_path(root: Path, relative_path: Any) -> Path:
    relative = Path(_text(relative_path))
    if relative.is_absolute():
        raise OfficialCaptureInventoryError("capture response path must be relative")
    candidate = (root / relative).resolve()
    resolved_root = root.resolve()
    if candidate == resolved_root or resolved_root not in candidate.parents:
        raise OfficialCaptureInventoryError("capture response path escapes capture root")
    if not candidate.is_file():
        raise OfficialCaptureInventoryError(
            f"capture response file is missing: {relative.as_posix()}"
        )
    return candidate


def _load_capture(
    capture_root: Path,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, list[str]]]:
    root = Path(capture_root).expanduser().resolve()
    try:
        manifest_payload = json.loads(
            (root / "capture-manifest.json").read_text(encoding="utf-8")
        )
        manifest = validate_capture_manifest(manifest_payload)
    except (OSError, ValueError) as error:
        raise OfficialCaptureInventoryError("official capture manifest is invalid") from error
    if manifest.get("status") != "captured":
        raise OfficialCaptureInventoryError("official capture manifest must be captured")

    responses: dict[str, dict[str, Any]] = {}
    response_refs: dict[str, list[str]] = defaultdict(list)
    for entry in manifest["entries"]:
        path = _text(entry.get("path"))
        response_path = _safe_response_path(root, entry.get("responsePath"))
        body = response_path.read_bytes()
        if len(body) != entry.get("responseBytes"):
            raise OfficialCaptureInventoryError(
                f"official response byte count mismatch: {path}"
            )
        if hashlib.sha256(body).hexdigest() != entry.get("responseSha256"):
            raise OfficialCaptureInventoryError(
                f"official response hash mismatch: {path}"
            )
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as error:
            raise OfficialCaptureInventoryError(
                f"official response is not valid JSON: {path}"
            ) from error
        payload = _mapping(payload, f"official response {path}")
        if path in responses and responses[path] != payload:
            raise OfficialCaptureInventoryError(
                f"duplicate official response path has different payload: {path}"
            )
        responses[path] = payload
        response_refs[path].append(_text(entry.get("responsePath")))
    return dict(manifest), responses, dict(response_refs)


def _mode_types(instance: Mapping[str, Any]) -> set[str]:
    result: set[str] = set()
    for row in instance.get("modes") or []:
        if isinstance(row, Mapping):
            mode = row.get("mode") if isinstance(row.get("mode"), Mapping) else row
            if isinstance(mode, Mapping) and _text(mode.get("type")):
                result.add(_text(mode.get("type")))
    return result


def _evidence(path: str, pointer: str, refs: Mapping[str, list[str]]) -> list[str]:
    return sorted(
        {
            f"official-api:{path}#{pointer}",
            *(
                f"official-api-response:{response_path}"
                for response_path in refs.get(path, [])
            ),
        }
    )


def _source_descriptor(instance_id: int) -> tuple[str, str, str, str] | None:
    if instance_id in MYTHIC_PLUS_INSTANCE_IDS:
        return "mythic_plus", "mythic_plus", "DUNGEON", "MYTHIC_KEYSTONE"
    if instance_id == LAIR_INSTANCE_ID:
        return "raid", "lair", "RAID", "MYTHIC"
    if instance_id == RAID_INSTANCE_ID:
        return "raid", "raid", "RAID", "MYTHIC"
    return None


def _hash_report(report: Mapping[str, Any]) -> str:
    payload = {
        key: value
        for key, value in report.items()
        if key not in {"reportId", "generatedAt"}
    }
    body = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"{REPORT_PREFIX}{hashlib.sha256(body).hexdigest()}"


def build_official_capture_inventory(
    capture_root: Path,
    *,
    product_scope: Mapping[str, Any] | str | Path,
    source_policy: Mapping[str, Any] | str | Path,
) -> dict[str, Any]:
    scope = validate_product_content_scope(_load_json(product_scope, "product scope"))
    policy = _load_json(source_policy, "source policy")
    manifest, responses, response_refs = _load_capture(capture_root)
    blocker_codes: set[str] = set()
    source_rows: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    source_item_ids: dict[str, set[str]] = defaultdict(set)

    selected_instance_ids = set(MYTHIC_PLUS_INSTANCE_IDS) | {
        LAIR_INSTANCE_ID,
        RAID_INSTANCE_ID,
    }
    for instance_id in sorted(selected_instance_ids):
        descriptor = _source_descriptor(instance_id)
        if descriptor is None:
            continue
        logical_source, raw_source_type, expected_category, expected_mode = descriptor
        instance_path = f"/data/wow/journal-instance/{instance_id}"
        instance = responses.get(instance_path)
        if instance is None:
            blocker_codes.add("OFFICIAL_SOURCE_CAPTURE_INCOMPLETE")
            continue
        if _text((instance.get("category") or {}).get("type")) != expected_category:
            blocker_codes.add("OFFICIAL_SOURCE_CATEGORY_UNVERIFIED")
        if expected_mode not in _mode_types(instance):
            blocker_codes.add("OFFICIAL_SOURCE_MODE_UNVERIFIED")
        encounter_rows = instance.get("encounters")
        if not isinstance(encounter_rows, list):
            blocker_codes.add("OFFICIAL_SOURCE_ENCOUNTER_GRAPH_MISSING")
            continue
        for encounter_index, encounter_ref in enumerate(encounter_rows):
            if not isinstance(encounter_ref, Mapping):
                blocker_codes.add("OFFICIAL_SOURCE_ENCOUNTER_GRAPH_MISSING")
                continue
            encounter_id = encounter_ref.get("id")
            try:
                normalized_encounter_id = _id(encounter_id, "encounterId")
            except OfficialCaptureInventoryError:
                blocker_codes.add("OFFICIAL_SOURCE_ENCOUNTER_GRAPH_MISSING")
                continue
            if instance_id == LAIR_INSTANCE_ID and int(normalized_encounter_id) != LAIR_ENCOUNTER_ID:
                blocker_codes.add("OFFICIAL_LAIR_ENCOUNTER_MISMATCH")
                continue
            encounter_path = f"/data/wow/journal-encounter/{normalized_encounter_id}"
            encounter = responses.get(encounter_path)
            if encounter is None:
                blocker_codes.add("OFFICIAL_SOURCE_ENCOUNTER_CAPTURE_INCOMPLETE")
                continue
            if _text((encounter.get("instance") or {}).get("id")) != str(instance_id):
                blocker_codes.add("OFFICIAL_SOURCE_ENCOUNTER_INSTANCE_MISMATCH")
            items = encounter.get("items")
            if not isinstance(items, list):
                blocker_codes.add("OFFICIAL_SOURCE_ITEM_GRAPH_MISSING")
                continue
            raw_source_key = (
                f"{raw_source_type}:journal-instance:{instance_id}:encounter:{normalized_encounter_id}"
            )
            for item_index, item_row in enumerate(items):
                if not isinstance(item_row, Mapping) or not isinstance(item_row.get("item"), Mapping):
                    blocker_codes.add("OFFICIAL_SOURCE_ITEM_ID_MISSING")
                    continue
                item_payload = item_row["item"]
                try:
                    item_id = _id(item_payload.get("id"), "itemId")
                except OfficialCaptureInventoryError:
                    blocker_codes.add("OFFICIAL_SOURCE_ITEM_ID_MISSING")
                    continue
                key = (logical_source, raw_source_type, raw_source_key, item_id)
                item_path = f"/data/wow/item/{item_id}"
                item_response = responses.get(item_path)
                item_identity_status = "verified" if item_response is not None else "UNVERIFIED"
                if item_response is None:
                    blocker_codes.add("OFFICIAL_ITEM_PAYLOAD_CAPTURE_INCOMPLETE")
                row = source_rows.get(key)
                if row is None:
                    row = {
                        "logicalSource": logical_source,
                        "rawSourceType": raw_source_type,
                        "rawSourceKey": raw_source_key,
                        "itemId": item_id,
                        "itemName": _text(item_payload.get("name")),
                        "sourceMembershipStatus": "verified",
                        "itemIdentityStatus": item_identity_status,
                        "variantStatus": "UNVERIFIED",
                        "trackStatus": "UNVERIFIED",
                        "enhancementCompatibilityStatus": "UNVERIFIED",
                        "simcReadiness": "blocked",
                        "officialEvidenceRefs": [],
                    }
                    source_rows[key] = row
                elif item_identity_status == "UNVERIFIED":
                    row["itemIdentityStatus"] = "UNVERIFIED"
                row["officialEvidenceRefs"] = sorted(
                    set(row["officialEvidenceRefs"])
                    | set(
                        _evidence(
                            encounter_path,
                            f"/items/{item_index}/item/id",
                            response_refs,
                        )
                    )
                    | set(_evidence(item_path, "/id", response_refs))
                )
                source_item_ids[logical_source].add(item_id)

    tier_rows: dict[tuple[str, str], dict[str, Any]] = {}
    tier_set_facts: list[dict[str, Any]] = []
    tier_item_ids: set[str] = set()
    for set_path in sorted(
        path
        for path in responses
        if path.startswith("/data/wow/item-set/") and path.rsplit("/", 1)[-1].isdigit()
    ):
        set_id = _id(set_path.rsplit("/", 1)[-1], "itemSetId")
        item_set = responses[set_path]
        effects = item_set.get("effects")
        effect_status = (
            "verified"
            if isinstance(effects, list)
            and effects
            and all(
                isinstance(effect, Mapping)
                and isinstance(effect.get("required_count"), int)
                and _text(effect.get("display_string"))
                for effect in effects
            )
            else "UNVERIFIED"
        )
        if effect_status != "verified":
            blocker_codes.add("TIER_SET_EFFECT_UNVERIFIED")
        tier_set_facts.append(
            {
                "setId": set_id,
                "setName": _text(item_set.get("name")),
                "setEffectStatus": effect_status,
                "effectCount": len(effects) if isinstance(effects, list) else 0,
                "officialEvidenceRefs": _evidence(set_path, "/effects", response_refs),
            }
        )
        items = item_set.get("items")
        if not isinstance(items, list):
            blocker_codes.add("TIER_SET_ITEM_GRAPH_MISSING")
            continue
        for item_index, item_row in enumerate(items):
            if not isinstance(item_row, Mapping):
                blocker_codes.add("TIER_SET_ITEM_ID_MISSING")
                continue
            try:
                item_id = _id(item_row.get("id"), "tierSetItemId")
            except OfficialCaptureInventoryError:
                blocker_codes.add("TIER_SET_ITEM_ID_MISSING")
                continue
            item_path = f"/data/wow/item/{item_id}"
            item_identity_status = "verified" if item_path in responses else "UNVERIFIED"
            if item_identity_status != "verified":
                blocker_codes.add("OFFICIAL_ITEM_PAYLOAD_CAPTURE_INCOMPLETE")
            key = (set_id, item_id)
            row = tier_rows.setdefault(
                key,
                {
                    "logicalSource": "tier_set",
                    "rawSourceType": "tier_set",
                    "rawSourceKey": f"tier_set:item-set:{set_id}",
                    "itemId": item_id,
                    "setId": set_id,
                    "setName": _text(item_set.get("name")),
                    "tierSetMembershipStatus": "verified",
                    "setEffectStatus": effect_status,
                    "itemIdentityStatus": item_identity_status,
                    "variantStatus": "UNVERIFIED",
                    "conversionStatus": "UNVERIFIED",
                    "simcReadiness": "blocked",
                    "officialEvidenceRefs": [],
                },
            )
            row["officialEvidenceRefs"] = sorted(
                set(row["officialEvidenceRefs"])
                | set(_evidence(set_path, f"/items/{item_index}/id", response_refs))
                | set(_evidence(item_path, "/id", response_refs))
            )
            tier_item_ids.add(item_id)

    crafted_recipes: list[dict[str, Any]] = []
    for recipe_path in sorted(
        path
        for path in responses
        if path.startswith("/data/wow/recipe/") and path.rsplit("/", 1)[-1].isdigit()
    ):
        recipe = responses[recipe_path]
        recipe_id = _id(recipe_path.rsplit("/", 1)[-1], "recipeId")
        crafted_recipes.append(
            {
                "logicalSource": "crafted",
                "rawSourceType": "crafted",
                "rawSourceKey": f"crafted:recipe:{recipe_id}",
                "recipeId": recipe_id,
                "recipeName": _text(recipe.get("name")),
                "modifiedCraftingSlotCount": len(recipe.get("modified_crafting_slots") or [])
                if isinstance(recipe.get("modified_crafting_slots"), list)
                else 0,
                "reagentCount": len(recipe.get("reagents") or [])
                if isinstance(recipe.get("reagents"), list)
                else 0,
                "itemId": None,
                "status": "blocked",
                "outputStatus": "blocked",
                "reasonCode": "OFFICIAL_API_RECIPE_OUTPUT_MISSING",
                "variantStatus": "UNVERIFIED",
                "enhancementCompatibilityStatus": "UNVERIFIED",
                "simcReadiness": "blocked",
                "officialEvidenceRefs": _evidence(recipe_path, "/id", response_refs),
            }
        )
    if crafted_recipes:
        blocker_codes.add("OFFICIAL_API_RECIPE_OUTPUT_MISSING")

    observed_ids_by_source = {
        "raid": sorted(source_item_ids.get("raid", set()), key=int),
        "mythic_plus": sorted(source_item_ids.get("mythic_plus", set()), key=int),
        "crafted": None,
        "tier_set": sorted(tier_item_ids, key=int),
    }
    all_observed_item_ids = set().union(
        *(set(value or []) for value in observed_ids_by_source.values())
    )
    excluded_types = list(
        ((policy.get("scopeContract") or {}).get("excludedSourceTypes") or [])
    )
    if not excluded_types:
        excluded_types = ["dungeon", "delve", "prey", "great_vault", "world_content"]
    coverage_counts = {
        "fourSourceCandidateTotal": {
            "value": None,
            "status": "blocked",
            "reasonCode": "OFFICIAL_API_VARIANT_AND_CRAFTED_OUTPUT_COVERAGE_INCOMPLETE",
        },
        "observedOfficialItemIdentityCount": len(all_observed_item_ids),
        "observedOfficialItemIdentityCountByLogicalSource": {
            key: (len(value) if value is not None else None)
            for key, value in observed_ids_by_source.items()
        },
        "sourceMembershipEdgeCount": len(source_rows),
        "sourceMembershipEdgeCountByLogicalSource": {
            "raid": sum(1 for row in source_rows.values() if row["logicalSource"] == "raid"),
            "mythic_plus": sum(
                1 for row in source_rows.values() if row["logicalSource"] == "mythic_plus"
            ),
            "crafted": len(crafted_recipes),
            "tier_set": len(tier_rows),
        },
        "craftedRecipeRootCount": len(crafted_recipes),
        "tierSetMembershipCount": len(tier_rows),
        "officialIdentityVerifiedCount": len(all_observed_item_ids),
        "finalVariantVerifiedCount": 0,
        "unverifiedVariantCount": len(all_observed_item_ids),
        "blockedCraftedOutputCount": len(crafted_recipes),
        "simcReadyCount": 0,
        "candidateIncludedCount": 0,
        "excludedCount": {
            source_type: {
                "value": None,
                "status": "excluded",
                "reasonCode": "OUT_OF_SCOPE_SOURCE_TYPE",
            }
            for source_type in excluded_types
        },
    }
    logical_sources = [
        _text(key).split(":", 1)[0]
        for key in scope["logicalSourceKeys"]
    ]
    report = {
        "schemaRevision": SCHEMA_REVISION,
        "status": "partial" if all_observed_item_ids else "blocked",
        "seasonKey": scope["seasonKey"],
        "captureRoot": Path(capture_root).name,
        "captureManifestSchemaRevision": _text(manifest.get("schemaRevision")),
        "captureRequestCount": len(manifest.get("entries") or []),
        "authority": {
            "factOwner": "blizzard_game_data_api",
            "rawCapturePersisted": True,
            "thirdPartyFactAuthority": False,
        },
        "scopeContract": {
            "logicalSources": logical_sources,
            "raidIncludesLair": True,
            "lairRawSourceTypePreserved": True,
            "tierSetIsIndependentMembershipDimension": True,
            "excludedSourceTypes": excluded_types,
        },
        "sourceMemberships": sorted(
            source_rows.values(),
            key=lambda row: (
                row["logicalSource"],
                row["rawSourceType"],
                row["rawSourceKey"],
                int(row["itemId"]),
            ),
        ),
        "tierSetFacts": sorted(tier_set_facts, key=lambda row: int(row["setId"])),
        "tierSetMemberships": sorted(
            tier_rows.values(),
            key=lambda row: (int(row["setId"]), int(row["itemId"])),
        ),
        "craftedRecipes": crafted_recipes,
        "coverageCounts": coverage_counts,
        "blockerCodes": sorted(blocker_codes),
        "notARelease": True,
        "activeManifestChanged": False,
        "productionWritten": False,
    }
    report["reportId"] = _hash_report(report)
    return report


__all__ = [
    "OfficialCaptureInventoryError",
    "REPORT_PREFIX",
    "SCHEMA_REVISION",
    "build_official_capture_inventory",
]
