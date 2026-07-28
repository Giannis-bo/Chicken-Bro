"""Pure current-season progression authority for legacy Browse rows.

The legacy Gear Release stores several progression families in the same
``trackKey``/``trackRank`` shape.  This module is deliberately pure and
fail-closed: it binds one exact season/rule pair to immutable records, ignores
generic payload rank, and emits a discriminated progression state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


TRACK_AUTHORITY_SCHEMA_REVISION = "gear-track-authority-v1"
TRACK_AUTHORITY_RULE_REVISION = "midnight-season-1-track-authority-v1"
_SEASON_REVISION = "season-17-f131dd36ddf1"
_GEAR_RULE_REVISION = "gear-rule-matrix-v1"

__all__ = (
    "TRACK_AUTHORITY_SCHEMA_REVISION",
    "TRACK_AUTHORITY_RULE_REVISION",
    "track_authority_for_binding",
    "resolve_legacy_browse_progression",
)


@dataclass(frozen=True)
class _TrackRecord:
    recordKey: str
    publicTrackKey: str
    progressionKind: str
    itemLevel: int
    maxRank: int | None
    eligibleSourceTypes: tuple[str, ...]
    eligibleSlots: tuple[str, ...]
    originKind: str | None
    qualityKey: str | None
    sourceRefIds: tuple[str, ...]
    evidenceStatus: str = "verified"


_SOURCE_REFS = (
    {
        "id": "blizzard-midnight-content-update-notes",
        "url": "https://news.blizzard.com/en-us/article/24244646/midnight-content-update-notes",
        "supports": "Current standard upgrade tracks have six ranks.",
    },
    {
        "id": "blizzard-12-0-5-content-update-notes",
        "url": "https://news.blizzard.com/en-us/article/24271855/12-0-5-content-update-notes",
        "supports": "Myth starts at 1/6 and fully upgraded Hero, Myth, or maximum-quality crafted items can progress to Ascendant.",
    },
)

_STANDARD_SOURCE_REFS = (_SOURCE_REFS[0]["id"],)
_ASCENDANT_SOURCE_REFS = (_SOURCE_REFS[1]["id"],)
_RECORDS = (
    _TrackRecord(
        "champion",
        "champion",
        "upgrade_track",
        263,
        6,
        (),
        (),
        None,
        None,
        _STANDARD_SOURCE_REFS,
    ),
    _TrackRecord(
        "hero",
        "hero",
        "upgrade_track",
        276,
        6,
        (),
        (),
        None,
        None,
        _STANDARD_SOURCE_REFS,
    ),
    _TrackRecord(
        "myth",
        "myth",
        "upgrade_track",
        289,
        6,
        (),
        (),
        None,
        None,
        _STANDARD_SOURCE_REFS,
    ),
    _TrackRecord(
        "crafted_myth",
        "myth",
        "crafted_quality",
        285,
        None,
        ("crafted",),
        (),
        None,
        "radiance_max",
        _ASCENDANT_SOURCE_REFS,
    ),
    _TrackRecord(
        "void_upgrade",
        "void_upgrade",
        "ascendant",
        298,
        None,
        (),
        ("main_hand", "trinket", "trinket1", "trinket2"),
        "upgrade_track",
        None,
        _ASCENDANT_SOURCE_REFS,
    ),
    _TrackRecord(
        "crafted_void_upgrade",
        "void_upgrade",
        "ascendant",
        295,
        None,
        ("crafted",),
        ("main_hand", "off_hand"),
        "crafted_quality",
        None,
        _ASCENDANT_SOURCE_REFS,
    ),
)
_RECORDS_BY_KEY = {record.recordKey: record for record in _RECORDS}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalized_slot(value: Any) -> str:
    slot = _text(value).lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "mainhand": "main_hand",
        "offhand": "off_hand",
        "trinket_1": "trinket1",
        "trinket_2": "trinket2",
    }
    return aliases.get(slot, slot)


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if parsed > 0 else None


def _dedicated_rank(row: Mapping[str, Any]) -> tuple[bool, int | None]:
    raw_rank = row.get("trackRank")
    if raw_rank is None or _text(raw_rank) in {"", "0"}:
        return False, None
    return True, _positive_int(raw_rank)


def _problem(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _blocked(code: str, message: str) -> dict[str, Any]:
    return {
        "status": "blocked",
        "schemaRevision": TRACK_AUTHORITY_SCHEMA_REVISION,
        "ruleRevision": TRACK_AUTHORITY_RULE_REVISION,
        "problems": [_problem(code, message)],
    }


def _public_record(record: _TrackRecord) -> dict[str, Any]:
    payload = asdict(record)
    payload["seasonRevision"] = _SEASON_REVISION
    payload["gearRuleRevision"] = _GEAR_RULE_REVISION
    payload["eligibleSourceTypes"] = list(record.eligibleSourceTypes)
    payload["eligibleSlots"] = list(record.eligibleSlots)
    payload["sourceRefIds"] = list(record.sourceRefIds)
    if record.maxRank is None:
        payload.pop("maxRank")
    if record.originKind is None:
        payload.pop("originKind")
    if record.qualityKey is None:
        payload.pop("qualityKey")
    return payload


def track_authority_for_binding(binding: Any) -> dict[str, Any]:
    """Return the exact verified Track Authority or a blocked binding."""

    row = binding if isinstance(binding, Mapping) else {}
    season_revision = _text(row.get("seasonRevision"))
    gear_rule_revision = _text(row.get("gearRuleRevision"))
    base = {
        "schemaRevision": TRACK_AUTHORITY_SCHEMA_REVISION,
        "ruleRevision": TRACK_AUTHORITY_RULE_REVISION,
        "seasonRevision": season_revision,
        "gearRuleRevision": gear_rule_revision,
        "sourceRefs": [dict(source) for source in _SOURCE_REFS],
    }
    if (
        season_revision != _SEASON_REVISION
        or gear_rule_revision != _GEAR_RULE_REVISION
    ):
        return {
            **base,
            "status": "blocked",
            "records": [],
            "problems": [
                _problem(
                    "TRACK_AUTHORITY_BINDING_UNSUPPORTED",
                    "No verified Track Authority matches the exact season and gear-rule revision.",
                )
            ],
        }
    return {
        **base,
        "status": "verified",
        "records": [_public_record(record) for record in _RECORDS],
        "problems": [],
    }


def _record_for_row(row: Mapping[str, Any]) -> _TrackRecord | None:
    track_key = _text(row.get("trackKey")).lower()
    source_type = _text(row.get("sourceType")).lower()
    if source_type == "crafted" and track_key == "myth":
        return _RECORDS_BY_KEY["crafted_myth"]
    if source_type == "crafted" and track_key == "void_upgrade":
        return _RECORDS_BY_KEY["crafted_void_upgrade"]
    return _RECORDS_BY_KEY.get(track_key)


def _has_crafted_stats(row: Mapping[str, Any]) -> bool:
    simc_options = row.get("simcOptions")
    if not isinstance(simc_options, Mapping):
        simc_options = row.get("simc_options")
    if not isinstance(simc_options, Mapping):
        return False
    value = simc_options.get("crafted_stats")
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple)):
        return bool(value) and all(bool(_text(entry)) for entry in value)
    return False


def resolve_legacy_browse_progression(
    binding: Any,
    row: Any,
) -> dict[str, Any]:
    """Resolve one legacy aggregate Browse row into a progression state."""

    authority = track_authority_for_binding(binding)
    if authority["status"] != "verified":
        return _blocked(
            "TRACK_AUTHORITY_BINDING_UNSUPPORTED",
            "No verified Track Authority matches the exact season and gear-rule revision.",
        )
    if not isinstance(row, Mapping):
        return _blocked(
            "TRACK_AUTHORITY_ROW_MALFORMED",
            "Legacy Browse progression input must be an object.",
        )

    record = _record_for_row(row)
    if record is None:
        return _blocked(
            "TRACK_AUTHORITY_TRACK_UNSUPPORTED",
            "Legacy Browse row does not identify a supported current-season track.",
        )

    item_level = _positive_int(row.get("itemLevel"))
    if item_level != record.itemLevel:
        return _blocked(
            "TRACK_AUTHORITY_ILEVEL_MISMATCH",
            "Legacy Browse item level does not match the bound Track Authority record.",
        )

    rank_is_present, dedicated_rank = _dedicated_rank(row)
    if record.progressionKind == "upgrade_track":
        if rank_is_present and dedicated_rank != record.maxRank:
            return _blocked(
                "TRACK_AUTHORITY_RANK_MISMATCH",
                "Dedicated track rank does not match the bound maximum rank.",
            )
        progression_state = {
            "kind": "upgrade_track",
            "trackKey": record.publicTrackKey,
            "rank": record.maxRank,
            "maxRank": record.maxRank,
        }
    else:
        if rank_is_present:
            return _blocked(
                "TRACK_AUTHORITY_RANK_FORBIDDEN",
                "Crafted quality and Ascendant progression states do not carry rank.",
            )
        slot = _normalized_slot(row.get("slot"))
        if record.recordKey == "crafted_myth" and not _has_crafted_stats(row):
            return _blocked(
                "TRACK_AUTHORITY_CRAFTED_STATS_MISSING",
                "Crafted-quality legacy rows require one explicit crafted-stat selection.",
            )
        if record.recordKey == "void_upgrade" and not (
            slot in record.eligibleSlots
            or row.get("hasVoidInstanceSource") is True
            or row.get("hasObservedAscendantEvidence") is True
        ):
            return _blocked(
                "TRACK_AUTHORITY_ASCENDANT_ELIGIBILITY_UNPROVEN",
                "Ordinary Ascendant eligibility lacks a governed slot, source, or observed exact-instance fact.",
            )
        if record.recordKey == "crafted_void_upgrade":
            if slot not in record.eligibleSlots:
                return _blocked(
                    "TRACK_AUTHORITY_CRAFTED_SLOT_UNSUPPORTED",
                    "Crafted Ascendant eligibility is restricted to governed weapon slots.",
                )
            if not _has_crafted_stats(row):
                return _blocked(
                    "TRACK_AUTHORITY_CRAFTED_STATS_MISSING",
                    "Crafted Ascendant rows require one explicit crafted-stat selection.",
                )
            if row.get("hasTrackEvidence") is not True:
                return _blocked(
                    "TRACK_AUTHORITY_TRACK_EVIDENCE_MISSING",
                    "Crafted Ascendant rows require explicit verified track evidence.",
                )
        progression_state = {
            "kind": record.progressionKind,
            "trackKey": record.publicTrackKey,
        }
        if record.originKind:
            progression_state["originKind"] = record.originKind
        if record.qualityKey:
            progression_state["qualityKey"] = record.qualityKey

    return {
        "status": "verified",
        "schemaRevision": TRACK_AUTHORITY_SCHEMA_REVISION,
        "ruleRevision": TRACK_AUTHORITY_RULE_REVISION,
        "recordKey": record.recordKey,
        "progressionState": progression_state,
        "problems": [],
    }
