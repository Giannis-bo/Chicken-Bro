"""Bounded official evidence for Midnight S2 crafting reagent compatibility.

Recipe payloads name the slot roles accepted by a recipe.  Blizzard's
``modified-crafting/reagent-slot-type`` endpoint owns the legal category
compatibility for each role.  This module joins those two official API facts
and persists the slot-type responses through the existing raw-capture writer;
it does not infer compatibility from names, SimC, or DB2 labels.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Protocol

from server.s2_official_api_capture import (
    OfficialApiCaptureError,
    capture_official_request_plan,
)
from server.s2_official_api_fact_snapshot import (
    request_key,
    validate_capture_manifest,
)


SCHEMA_REVISION = "s2-official-modified-crafting-slot-capture-v1"
_ID_PATTERN = re.compile(r"^[1-9][0-9]*$")
_RECIPE_PATH = re.compile(r"^/data/wow/recipe/([1-9][0-9]*)$")
_SLOT_TYPE_PATH = re.compile(
    r"^/data/wow/modified-crafting/reagent-slot-type/([1-9][0-9]*)$"
)


class OfficialModifiedCraftingError(ValueError):
    """Raised when official crafting compatibility evidence is not closed."""


class OfficialReader(Protocol):
    def get(
        self,
        path: str,
        *,
        namespace: str,
        region: str,
        locale: str,
        query: dict,
    ) -> dict:
        """Read one official Blizzard Game Data response."""


def _canonical(value: Any) -> Any:
    return json.loads(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _positive_id(value: Any, label: str) -> str:
    text = _text(value)
    if not _ID_PATTERN.fullmatch(text):
        raise OfficialModifiedCraftingError(f"{label} must be a positive integer id")
    return str(int(text))


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise OfficialModifiedCraftingError(f"{label} is invalid") from error
    if not isinstance(value, Mapping):
        raise OfficialModifiedCraftingError(f"{label} must be an object")
    return dict(value)


def _safe_response_path(root: Path, relative: Any) -> Path:
    value = _text(relative)
    candidate = (root / value).resolve()
    resolved_root = root.resolve()
    if not value or Path(value).is_absolute() or candidate == resolved_root or resolved_root not in candidate.parents:
        raise OfficialModifiedCraftingError("recipe response path must stay inside capture root")
    if not candidate.is_file():
        raise OfficialModifiedCraftingError(f"recipe response is missing: {value}")
    return candidate


def _load_source_manifest(source_capture_root: Path) -> tuple[dict[str, Any], Path]:
    root = Path(source_capture_root).expanduser().resolve()
    manifest_path = root / "capture-manifest.json"
    try:
        raw_manifest = _read_json(manifest_path, "source capture manifest")
        manifest = validate_capture_manifest(raw_manifest)
    except Exception as error:
        if isinstance(error, OfficialModifiedCraftingError):
            raise
        raise OfficialModifiedCraftingError("source capture manifest is invalid") from error
    if manifest["status"] != "captured":
        raise OfficialModifiedCraftingError("source recipe capture must be captured")
    return manifest, root


def extract_slot_type_ids(source_capture_root: Path) -> list[str]:
    """Extract the exact slot-role IDs present in captured recipe payloads."""

    manifest, root = _load_source_manifest(source_capture_root)
    slot_type_ids: set[str] = set()
    recipe_count = 0
    for entry in manifest["entries"]:
        match = _RECIPE_PATH.fullmatch(_text(entry.get("path")))
        if not match:
            continue
        recipe_count += 1
        response_path = _safe_response_path(root, entry.get("responsePath"))
        body = response_path.read_bytes()
        if len(body) != int(entry["responseBytes"]):
            raise OfficialModifiedCraftingError(
                f"recipe response byte drift: {entry['path']}"
            )
        if hashlib.sha256(body).hexdigest() != entry["responseSha256"]:
            raise OfficialModifiedCraftingError(
                f"recipe response hash drift: {entry['path']}"
            )
        payload = _read_json(response_path, f"recipe response {entry['path']}")
        if _text(payload.get("id")) != match.group(1):
            raise OfficialModifiedCraftingError(f"recipe id mismatch: {entry['path']}")
        slots = payload.get("modified_crafting_slots")
        if slots is None:
            continue
        if not isinstance(slots, list):
            raise OfficialModifiedCraftingError(
                f"recipe modified_crafting_slots must be a list or null: {entry['path']}"
            )
        for index, slot in enumerate(slots):
            if not isinstance(slot, Mapping):
                raise OfficialModifiedCraftingError(
                    f"recipe slot must be an object: {entry['path']}[{index}]"
                )
            slot_type = slot.get("slot_type")
            if not isinstance(slot_type, Mapping):
                raise OfficialModifiedCraftingError(
                    f"recipe slot_type must be an object: {entry['path']}[{index}]"
                )
            slot_type_ids.add(
                _positive_id(
                    slot_type.get("id"),
                    f"{entry['path']} modified_crafting_slots[{index}].slot_type.id",
                )
            )
    if recipe_count == 0:
        raise OfficialModifiedCraftingError(
            "source capture has no official recipe responses"
        )
    if not slot_type_ids:
        raise OfficialModifiedCraftingError(
            "source recipe capture has no modified crafting slot types"
        )
    return sorted(slot_type_ids, key=int)


def build_slot_type_request_plan(
    slot_type_ids: list[str] | tuple[str, ...],
    *,
    region: str = "us",
    locale: str = "en_US",
    namespace: str = "static-12.1.0_68914-us",
) -> list[dict[str, Any]]:
    """Build exact, deduplicated official reagent-slot-type requests."""

    normalized = sorted(
        {_positive_id(value, "slot_type_id") for value in slot_type_ids},
        key=int,
    )
    if not normalized:
        raise OfficialModifiedCraftingError("slot_type_ids must not be empty")
    if not _text(region) or not _text(locale) or not _text(namespace):
        raise OfficialModifiedCraftingError("region, locale, and namespace are required")
    plan = []
    for slot_type_id in normalized:
        path = f"/data/wow/modified-crafting/reagent-slot-type/{slot_type_id}"
        plan.append(
            {
                "requestKey": request_key(
                    path,
                    {},
                    namespace=namespace,
                    region=region,
                    locale=locale,
                ),
                "path": path,
                "namespace": namespace,
                "region": region,
                "locale": locale,
                "query": {},
                "paginationParentRequestKey": None,
            }
        )
    return plan


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_bytes(value) + b"\n")


def capture_modified_crafting_slot_types(
    *,
    source_capture_root: Path,
    output_root: Path,
    reader: OfficialReader,
    region: str = "us",
    locale: str = "en_US",
    namespace: str = "static-12.1.0_68914-us",
    captured_at: str | None = None,
) -> dict[str, Any]:
    """Persist the slot-type API closure bound to the captured recipe graph."""

    source_manifest, source_root = _load_source_manifest(source_capture_root)
    slot_type_ids = extract_slot_type_ids(source_root)
    plan = build_slot_type_request_plan(
        slot_type_ids,
        region=region,
        locale=locale,
        namespace=namespace,
    )
    try:
        capture_result = capture_official_request_plan(
            plan=plan,
            output_root=Path(output_root),
            reader=reader,
            captured_at=captured_at,
        )
    except OfficialApiCaptureError as error:
        raise OfficialModifiedCraftingError(str(error)) from error

    output = Path(output_root).expanduser().resolve()
    metadata = {
        "schemaRevision": SCHEMA_REVISION,
        "status": capture_result["status"],
        "seasonKey": "midnight-season-2",
        "capturePurpose": "official_modified_crafting_slot_type_compatibility",
        "sourceCaptureManifestSha256": hashlib.sha256(
            _canonical_bytes(source_manifest)
        ).hexdigest(),
        "sourceCaptureRoot": Path(source_capture_root).expanduser().resolve().name,
        "sourceRecipeCount": sum(
            1 for entry in source_manifest["entries"] if _RECIPE_PATH.fullmatch(_text(entry.get("path")))
        ),
        "slotTypeIds": slot_type_ids,
        "requestCount": len(plan),
        "rawResponseCount": capture_result["requestCount"],
        "region": region,
        "locale": locale,
        "namespace": namespace,
    }
    _write_json(output / "slot-type-capture.json", metadata)
    return {
        "status": metadata["status"],
        "outputRoot": str(output),
        "slotTypeIds": slot_type_ids,
        "requestCount": len(plan),
        "sourceRecipeCount": metadata["sourceRecipeCount"],
    }


__all__ = [
    "OfficialModifiedCraftingError",
    "SCHEMA_REVISION",
    "build_slot_type_request_plan",
    "capture_modified_crafting_slot_types",
    "extract_slot_type_ids",
]
