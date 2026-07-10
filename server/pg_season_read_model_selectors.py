#!/usr/bin/env python3
import json
from datetime import datetime, timezone

try:
    from .websim_payload import (
        DEFAULT_LOCALE,
        current_season_payload,
        normalize_current_season_raid_pool_payload,
    )
except ImportError:
    from websim_payload import (
        DEFAULT_LOCALE,
        current_season_payload,
        normalize_current_season_raid_pool_payload,
    )


def _json_value(value, fallback):
    if isinstance(value, (dict, list)):
        return value
    try:
        parsed = json.loads(value or "")
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed is not None else fallback


def _datetime_value(value):
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def build_active_season_read_model(row, dungeon_rows, *, now=None):
    if not row:
        return {}
    payload = _json_value(row[8], {})
    if not isinstance(payload, dict) or not payload.get("seasonRevision"):
        payload = current_season_payload(
            season_id=row[0],
            season_label=row[1],
            locale=row[3] or DEFAULT_LOCALE,
            dungeons=[],
            data_status=row[4],
            verified_at=str(row[5] or ""),
            expires_at=str(row[6] or ""),
            source_refs=_json_value(row[7], []),
        )
    payload["seasonId"] = row[0]
    payload["id"] = row[0]
    payload["seasonLabel"] = row[1]
    payload["label"] = row[1]
    payload["seasonRevision"] = row[2]
    payload["revision"] = row[2]
    payload["locale"] = row[3] or DEFAULT_LOCALE
    expires_at = _datetime_value(row[6])
    now_value = _datetime_value(now) or datetime.now(timezone.utc)
    expired = bool(expires_at and expires_at <= now_value)
    payload["dataStatus"] = "stale" if expired else row[4]
    payload["verifiedAt"] = str(row[5] or "")
    payload["expiresAt"] = str(row[6] or "")
    payload["sourceRefs"] = _json_value(row[7], [])
    if expired:
        errors = payload.get("errors") if isinstance(payload.get("errors"), list) else []
        payload["errors"] = [*errors, "season cache expired"]
    payload["dungeons"] = [
        {
            "id": dungeon_row[0],
            "dungeonId": dungeon_row[0],
            "instanceId": dungeon_row[1],
            "name": dungeon_row[2],
            "shortName": dungeon_row[3],
            "timerSeconds": dungeon_row[4],
            "sourceRefs": payload["sourceRefs"],
            "payload": _json_value(dungeon_row[5], {}),
        }
        for dungeon_row in dungeon_rows or []
    ]
    normalize_current_season_raid_pool_payload(payload)
    return payload
