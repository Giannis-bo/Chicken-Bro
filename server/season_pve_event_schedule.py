"""Time-bound official event selection for current-season PVE capture."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from server.season_pve_official_capture import OfficialCaptureContractError


def _text(value: Any) -> str:
    return str(value or "").strip()


def _audit_instant(value: Any, label: str) -> datetime:
    raw = _text(value)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as error:
        raise OfficialCaptureContractError(
            f"{label} requires an ISO-8601 instant"
        ) from error
    if parsed.tzinfo is None:
        raise OfficialCaptureContractError(
            f"{label} requires a timezone"
        )
    return parsed.astimezone(timezone.utc)


def select_active_timewalking_rotation(
    rotations: Any,
    as_of: Any,
) -> dict[str, Any]:
    """Select the one official event rotation active at the audit instant."""

    if not isinstance(rotations, list) or not rotations:
        raise OfficialCaptureContractError(
            "timewalking rotations must be a non-empty list"
        )
    resolved_as_of = _audit_instant(as_of, "timewalking as-of")
    normalized = []
    seen_keys = set()
    for raw_rotation in rotations:
        if not isinstance(raw_rotation, dict):
            raise OfficialCaptureContractError(
                "timewalking rotation must be an object"
            )
        rotation_key = _text(raw_rotation.get("rotationKey"))
        dungeon_names = raw_rotation.get("dungeonNames")
        if (
            not rotation_key
            or rotation_key in seen_keys
            or not isinstance(dungeon_names, list)
            or not dungeon_names
        ):
            raise OfficialCaptureContractError(
                "timewalking rotation requires a unique key and dungeons"
            )
        resolved_names = [_text(name) for name in dungeon_names]
        if (
            any(not name for name in resolved_names)
            or len(set(resolved_names)) != len(resolved_names)
        ):
            raise OfficialCaptureContractError(
                f"timewalking rotation {rotation_key} has invalid dungeons"
            )
        starts_at = _audit_instant(
            raw_rotation.get("startsAt"),
            f"timewalking rotation {rotation_key} startsAt",
        )
        ends_at = _audit_instant(
            raw_rotation.get("endsAt"),
            f"timewalking rotation {rotation_key} endsAt",
        )
        if ends_at <= starts_at:
            raise OfficialCaptureContractError(
                f"timewalking rotation {rotation_key} has invalid window"
            )
        seen_keys.add(rotation_key)
        normalized.append(
            {
                **raw_rotation,
                "rotationKey": rotation_key,
                "startsAt": starts_at.isoformat().replace("+00:00", "Z"),
                "endsAt": ends_at.isoformat().replace("+00:00", "Z"),
                "dungeonNames": resolved_names,
                "_startsAt": starts_at,
                "_endsAt": ends_at,
            }
        )
    active = [
        row
        for row in normalized
        if row["_startsAt"] <= resolved_as_of < row["_endsAt"]
    ]
    if len(active) != 1:
        raise OfficialCaptureContractError(
            "timewalking as-of requires exactly one active rotation"
        )
    selected = dict(active[0])
    selected.pop("_startsAt")
    selected.pop("_endsAt")
    return selected
