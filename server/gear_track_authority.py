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
    "resolve_exact_instance_progression",
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
    rank: int | None = None
    bonusIds: tuple[str, ...] = ()
    trackAuthorityRevision: str | None = None


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
_EXACT_TRACK_MARKERS = {
    "champion": frozenset({"13448"}),
    "hero": frozenset({"13334"}),
    "myth": frozenset({"13335", "13440"}),
}
_EXACT_TRACK_LADDERS = {
    "champion": {
        246: 1,
        250: 2,
        253: 3,
        256: 4,
        259: 5,
        263: 6,
    },
    "hero": {
        259: 1,
        263: 2,
        266: 3,
        269: 4,
        272: 5,
        276: 6,
    },
    "myth": {
        272: 1,
        276: 2,
        279: 3,
        282: 4,
        285: 5,
        289: 6,
    },
}
_ASCENDANT_BONUS_ORIGINS = {
    "13653": ("upgrade_track", 285),
    "13654": ("upgrade_track", 298),
    "13655": ("crafted_quality", 295),
}
_ASCENDANT_SLOTS = frozenset({
    "main_hand",
    "off_hand",
    "trinket",
    "trinket1",
    "trinket2",
})


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


def _problem(code: str, message: str, path: str = "") -> dict[str, str]:
    result = {"code": code, "message": message}
    if path:
        result["path"] = path
    return result


def _blocked(
    code: str,
    message: str,
    *,
    rule_revision: str = TRACK_AUTHORITY_RULE_REVISION,
) -> dict[str, Any]:
    return {
        "status": "blocked",
        "schemaRevision": TRACK_AUTHORITY_SCHEMA_REVISION,
        "ruleRevision": rule_revision,
        "problems": [_problem(code, message)],
    }


def _blocked_with_progression(
    code: str,
    message: str,
    record: _TrackRecord,
    progression_state: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        **_blocked(
            code,
            message,
            rule_revision=record.trackAuthorityRevision or TRACK_AUTHORITY_RULE_REVISION,
        ),
        "recordKey": record.recordKey,
        "progressionState": dict(progression_state),
    }


def _public_record(
    record: _TrackRecord,
    *,
    season_revision: str | None = None,
    gear_rule_revision: str | None = None,
) -> dict[str, Any]:
    payload = asdict(record)
    payload["seasonRevision"] = season_revision or _SEASON_REVISION
    payload["gearRuleRevision"] = gear_rule_revision or _GEAR_RULE_REVISION
    payload["eligibleSourceTypes"] = list(record.eligibleSourceTypes)
    payload["eligibleSlots"] = list(record.eligibleSlots)
    payload["sourceRefIds"] = list(record.sourceRefIds)
    if record.maxRank is None:
        payload.pop("maxRank")
    if record.originKind is None:
        payload.pop("originKind")
    if record.qualityKey is None:
        payload.pop("qualityKey")
    if record.rank is None:
        payload.pop("rank")
    if not record.bonusIds:
        payload.pop("bonusIds")
    if record.trackAuthorityRevision is None:
        payload.pop("trackAuthorityRevision")
    payload.pop("seasonRevision", None)
    payload.pop("gearRuleRevision", None)
    payload["seasonRevision"] = season_revision or _SEASON_REVISION
    payload["gearRuleRevision"] = gear_rule_revision or _GEAR_RULE_REVISION
    return payload


def _binding_source_refs(binding: Mapping[str, Any]) -> list[Any]:
    value = binding.get("sourceRefs")
    if isinstance(value, list):
        return [_canonical(source) for source in value if source]
    return []


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _canonical(value[key])
            for key in sorted(value, key=lambda item: str(item))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, set):
        return sorted(_canonical(item) for item in value)
    return value


def _text_list(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        values = value.replace(",", "/").split("/")
    elif isinstance(value, (list, tuple, set, frozenset)):
        values = list(value)
    else:
        return ()
    return tuple(sorted({_text(item) for item in values if _text(item)}))


def _data_record(
    raw: Any,
    *,
    index: int,
    season_revision: str,
    gear_rule_revision: str,
    track_authority_revision: str,
) -> tuple[_TrackRecord | None, list[dict[str, str]]]:
    row = raw if isinstance(raw, Mapping) else {}
    problems: list[dict[str, str]] = []
    path = f"records[{index}]"
    record_key = _text(row.get("recordKey"))
    track_key = _text(row.get("publicTrackKey") or row.get("trackKey")).lower()
    progression_kind = _text(row.get("progressionKind")).lower()
    if not record_key:
        problems.append(_problem("TRACK_AUTHORITY_RECORD_KEY_MISSING", "S2 track record requires recordKey."))
    if not track_key:
        problems.append(_problem("TRACK_AUTHORITY_TRACK_KEY_MISSING", "S2 track record requires trackKey."))
    if progression_kind not in {"upgrade_track", "crafted_quality", "ascendant", "season_special"}:
        problems.append(_problem("TRACK_AUTHORITY_PROGRESSION_KIND_INVALID", "S2 track progression kind is not governed."))

    record_season = _text(row.get("seasonRevision"))
    if record_season != season_revision:
        problems.append(_problem("TRACK_AUTHORITY_SEASON_REVISION_MISMATCH", "S2 track record belongs to another season revision.", f"{path}.seasonRevision"))
    record_rule = _text(row.get("gearRuleRevision"))
    if record_rule != gear_rule_revision:
        problems.append(_problem("TRACK_AUTHORITY_GEAR_RULE_REVISION_MISMATCH", "S2 track record belongs to another gear-rule revision.", f"{path}.gearRuleRevision"))
    evidence_status = _text(row.get("evidenceStatus") or row.get("status")).lower()
    if evidence_status != "verified":
        problems.append(_problem("TRACK_AUTHORITY_RECORD_NOT_VERIFIED", "S2 track record evidence is not verified.", f"{path}.evidenceStatus"))

    item_level = _positive_int(row.get("itemLevel"))
    if item_level is None:
        problems.append(_problem("TRACK_AUTHORITY_ITEM_LEVEL_MISSING", "S2 track record requires an exact itemLevel.", f"{path}.itemLevel"))
    max_rank = _positive_int(row.get("maxRank"))
    rank = _positive_int(row.get("rank"))
    if progression_kind == "upgrade_track":
        if max_rank is None:
            problems.append(_problem("TRACK_AUTHORITY_MAX_RANK_MISSING", "Upgrade track requires maxRank.", f"{path}.maxRank"))
        if rank is None:
            problems.append(_problem("TRACK_AUTHORITY_RANK_MISSING", "Upgrade track requires rank.", f"{path}.rank"))
        if max_rank is not None and rank is not None and rank > max_rank:
            problems.append(_problem("TRACK_AUTHORITY_RANK_INVALID", "Track rank cannot exceed maxRank.", f"{path}.rank"))

    source_refs = _text_list(row.get("sourceRefIds") or row.get("sourceRefs"))
    if not source_refs:
        problems.append(_problem("TRACK_AUTHORITY_SOURCE_REFS_MISSING", "S2 track record requires source references.", f"{path}.sourceRefs"))
    eligible_sources = _text_list(row.get("eligibleSourceTypes"))
    eligible_slots = _text_list(row.get("eligibleSlots"))
    if not isinstance(row.get("eligibleSourceTypes"), (list, tuple, set, frozenset, str)):
        problems.append(_problem("TRACK_AUTHORITY_SOURCE_ELIGIBILITY_MISSING", "S2 track record requires source eligibility.", f"{path}.eligibleSourceTypes"))
    if not isinstance(row.get("eligibleSlots"), (list, tuple, set, frozenset, str)):
        problems.append(_problem("TRACK_AUTHORITY_SLOT_ELIGIBILITY_MISSING", "S2 track record requires slot eligibility.", f"{path}.eligibleSlots"))

    bonus_ids = _text_list(row.get("bonusIds"))
    bonus_evidence = row.get("bonusEvidence")
    if isinstance(bonus_evidence, list):
        for evidence in bonus_evidence:
            if isinstance(evidence, Mapping):
                bonus_ids = tuple(sorted({*bonus_ids, *_text_list(evidence.get("bonusIds"))}))
    if progression_kind in {"upgrade_track", "ascendant"} and not bonus_ids:
        problems.append(_problem("TRACK_AUTHORITY_BONUS_EVIDENCE_MISSING", "S2 upgrade records require explicit bonus evidence.", f"{path}.bonusEvidence"))

    if problems:
        return None, problems
    return _TrackRecord(
        recordKey=record_key,
        publicTrackKey=track_key,
        progressionKind=progression_kind,
        itemLevel=item_level,
        maxRank=max_rank,
        eligibleSourceTypes=eligible_sources,
        eligibleSlots=eligible_slots,
        originKind=_text(row.get("originKind")) or None,
        qualityKey=_text(row.get("qualityKey")) or None,
        sourceRefIds=source_refs,
        evidenceStatus="verified",
        rank=rank,
        bonusIds=bonus_ids,
        trackAuthorityRevision=track_authority_revision,
    ), []


def _build_data_driven_authority(
    binding: Mapping[str, Any],
    records: list[Any],
) -> dict[str, Any]:
    season_revision = _text(binding.get("seasonRevision"))
    gear_rule_revision = _text(binding.get("gearRuleRevision"))
    track_authority_revision = _text(binding.get("trackAuthorityRevision"))
    problems: list[dict[str, str]] = []
    if not track_authority_revision:
        problems.append(_problem("TRACK_AUTHORITY_REVISION_MISSING", "S2 binding requires trackAuthorityRevision."))
    if not gear_rule_revision:
        problems.append(_problem("TRACK_AUTHORITY_GEAR_RULE_REVISION_MISSING", "S2 binding requires gearRuleRevision."))
    normalized: list[_TrackRecord] = []
    seen_keys: set[str] = set()
    seen_track_ranks: set[tuple[str, int, str]] = set()
    for index, raw in enumerate(records):
        record, record_problems = _data_record(
            raw,
            index=index,
            season_revision=season_revision,
            gear_rule_revision=gear_rule_revision,
            track_authority_revision=track_authority_revision,
        )
        problems.extend(record_problems)
        if record is None:
            continue
        if record.recordKey in seen_keys:
            problems.append(_problem("TRACK_AUTHORITY_RECORD_DUPLICATE", "S2 track recordKey is duplicated."))
        seen_keys.add(record.recordKey)
        if record.rank is not None:
            identity = (record.publicTrackKey, record.rank, record.progressionKind)
            if identity in seen_track_ranks:
                problems.append(_problem("TRACK_AUTHORITY_RANK_DUPLICATE", "S2 track contains duplicate track/rank records."))
            seen_track_ranks.add(identity)
        normalized.append(record)
    base = {
        "schemaRevision": TRACK_AUTHORITY_SCHEMA_REVISION,
        "ruleRevision": track_authority_revision,
        "trackAuthorityRevision": track_authority_revision,
        "seasonRevision": season_revision,
        "gearRuleRevision": gear_rule_revision,
        "sourceRefs": _binding_source_refs(binding),
        "records": [
            _public_record(
                record,
                season_revision=season_revision,
                gear_rule_revision=gear_rule_revision,
            )
            for record in normalized
        ],
    }
    return {
        **base,
        "status": "verified" if not problems and normalized else "blocked",
        "problems": sorted(
            (_canonical(problem) for problem in problems),
            key=lambda problem: (
                _text(problem.get("code")),
                _text(problem.get("path")),
            ),
        )[:40],
    }


def _legacy_track_authority(binding: Mapping[str, Any]) -> dict[str, Any]:
    season_revision = _text(binding.get("seasonRevision"))
    gear_rule_revision = _text(binding.get("gearRuleRevision"))
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


def track_authority_for_binding(
    binding: Any,
    records: Any = None,
) -> dict[str, Any]:
    """Return exact S1 legacy or explicit data-driven S2 Track Authority."""

    row = binding if isinstance(binding, Mapping) else {}
    season_revision = _text(row.get("seasonRevision"))
    if season_revision.startswith("season-midnight-season-2:"):
        selected_records = records
        if selected_records is None:
            selected_records = row.get("trackRecords")
        if not isinstance(selected_records, list) or not selected_records:
            return {
                "schemaRevision": TRACK_AUTHORITY_SCHEMA_REVISION,
                "ruleRevision": _text(row.get("trackAuthorityRevision")),
                "trackAuthorityRevision": _text(row.get("trackAuthorityRevision")),
                "seasonRevision": season_revision,
                "gearRuleRevision": _text(row.get("gearRuleRevision")),
                "sourceRefs": _binding_source_refs(row),
                "status": "blocked",
                "records": [],
                "problems": [_problem(
                    "TRACK_AUTHORITY_RECORDS_MISSING",
                    "S2 Track Authority requires explicit end game track records.",
                )],
            }
        return _build_data_driven_authority(row, selected_records)
    return _legacy_track_authority(row)


def _records_from_authority(authority: Mapping[str, Any]) -> tuple[_TrackRecord, ...]:
    records = authority.get("records")
    if not isinstance(records, list):
        return ()
    result: list[_TrackRecord] = []
    for raw in records:
        if not isinstance(raw, Mapping):
            continue
        result.append(_TrackRecord(
            recordKey=_text(raw.get("recordKey")),
            publicTrackKey=_text(raw.get("publicTrackKey") or raw.get("trackKey")).lower(),
            progressionKind=_text(raw.get("progressionKind")).lower(),
            itemLevel=_positive_int(raw.get("itemLevel")) or 0,
            maxRank=_positive_int(raw.get("maxRank")),
            eligibleSourceTypes=_text_list(raw.get("eligibleSourceTypes")),
            eligibleSlots=_text_list(raw.get("eligibleSlots")),
            originKind=_text(raw.get("originKind")) or None,
            qualityKey=_text(raw.get("qualityKey")) or None,
            sourceRefIds=_text_list(raw.get("sourceRefIds") or raw.get("sourceRefs")),
            evidenceStatus=_text(raw.get("evidenceStatus") or raw.get("status")) or "verified",
            rank=_positive_int(raw.get("rank")),
            bonusIds=_text_list(raw.get("bonusIds")),
            trackAuthorityRevision=_text(authority.get("ruleRevision")) or None,
        ))
    return tuple(result)


def _record_for_row(
    row: Mapping[str, Any],
    records: tuple[_TrackRecord, ...] | None = None,
) -> _TrackRecord | None:
    track_key = _text(row.get("trackKey")).lower()
    source_type = _text(row.get("sourceType")).lower()
    pool = records if records is not None else _RECORDS
    candidates = [
        record
        for record in pool
        if record.publicTrackKey == track_key or record.recordKey == track_key
    ]
    if source_type == "crafted":
        crafted = [
            record
            for record in candidates
            if record.progressionKind in {"crafted_quality", "ascendant"}
        ]
        if crafted:
            candidates = crafted
    item_level = _positive_int(row.get("itemLevel"))
    exact_level = [record for record in candidates if record.itemLevel == item_level]
    if exact_level:
        candidates = exact_level
    if records is not None:
        eligible = [
            record
            for record in candidates
            if (
                not record.eligibleSourceTypes
                or not source_type
                or source_type in record.eligibleSourceTypes
            )
            and (
                not record.eligibleSlots
                or not _normalized_slot(row.get("slot"))
                or _normalized_slot(row.get("slot")) in record.eligibleSlots
            )
        ]
        if eligible:
            candidates = eligible
        # Browse authority exposes only the governed maximum of a normal
        # upgrade track. Lower-rank rows remain exact-instance evidence.
        maximum = [
            record
            for record in candidates
            if record.progressionKind != "upgrade_track"
            or record.rank is None
            or record.maxRank is None
            or record.rank == record.maxRank
        ]
        if maximum:
            candidates = maximum
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda record: (
            record.rank if record.rank is not None else (record.maxRank or 0),
            record.recordKey,
        ),
        reverse=True,
    )[0]


def _authority_blocked_result(authority: Mapping[str, Any]) -> dict[str, Any]:
    problems = authority.get("problems")
    if not isinstance(problems, list) or not problems:
        problems = [_problem(
            "TRACK_AUTHORITY_BINDING_UNSUPPORTED",
            "No verified Track Authority matches the exact season and gear-rule revision.",
        )]
    return {
        "status": "blocked",
        "schemaRevision": TRACK_AUTHORITY_SCHEMA_REVISION,
        "ruleRevision": _text(authority.get("ruleRevision")) or TRACK_AUTHORITY_RULE_REVISION,
        "problems": [_canonical(problem) for problem in problems],
    }


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


def _bonus_ids(row: Mapping[str, Any]) -> set[str]:
    value = row.get("bonusIds")
    if isinstance(value, str):
        return {
            part.strip()
            for part in value.replace(",", "/").split("/")
            if part.strip()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return {_text(part) for part in value if _text(part)}
    simc_options = row.get("simcOptions")
    if not isinstance(simc_options, Mapping):
        simc_options = row.get("simc_options")
    if isinstance(simc_options, Mapping):
        return _bonus_ids({"bonusIds": simc_options.get("bonus_id")})
    return set()


def _verified_exact_result(
    record_key: str,
    progression_state: Mapping[str, Any],
    *,
    rule_revision: str = TRACK_AUTHORITY_RULE_REVISION,
) -> dict[str, Any]:
    return {
        "status": "verified",
        "schemaRevision": TRACK_AUTHORITY_SCHEMA_REVISION,
        "ruleRevision": rule_revision,
        "recordKey": record_key,
        "progressionState": dict(progression_state),
        "problems": [],
    }


def _row_payload_value(row: Mapping[str, Any], key: str) -> Any:
    value = row.get(key)
    if value is not None:
        return value
    payload = row.get("payload")
    if isinstance(payload, Mapping):
        return payload.get(key)
    return None


def _resolve_community_observed_exact(
    authority: Mapping[str, Any],
    row: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Bind an observed profile to an Exact-only, non-official progression.

    Community observations do not have enough authoritative evidence to claim
    an S2 upgrade track.  They can still be simulated when their exact
    identity is verified, so represent that fact with an explicit progression
    state that cannot be confused with a Browse track.
    """

    source_type = _text(_row_payload_value(row, "sourceType")).lower()
    truth_scope = _text(_row_payload_value(row, "truthScope")).lower()
    official_fact_status = _text(
        _row_payload_value(row, "officialFactStatus")
    ).upper()
    membership_kind = _text(_row_payload_value(row, "membershipKind")).lower()
    editable = _row_payload_value(row, "editable")
    is_community_marked = (
        source_type == "observed_profile"
        or truth_scope == "community_observed"
        or membership_kind == "imported_exact"
    )
    if not is_community_marked:
        return None
    if (
        source_type != "observed_profile"
        or truth_scope != "community_observed"
        or official_fact_status != "UNVERIFIED"
        or membership_kind != "imported_exact"
        or editable is not False
    ):
        rule_revision = _text(authority.get("ruleRevision")) or TRACK_AUTHORITY_RULE_REVISION
        return _blocked(
            "TRACK_AUTHORITY_COMMUNITY_EVIDENCE_INVALID",
            "Community exact progression requires an immutable observed-profile truth boundary.",
            rule_revision=rule_revision,
        )
    return _verified_exact_result(
        "community_observed_exact",
        {
            "kind": "community_observed",
            "trackKey": "community_observed_exact",
            "sourceType": "observed_profile",
            "truthScope": "community_observed",
            "officialFactStatus": "UNVERIFIED",
        },
        rule_revision=_text(authority.get("ruleRevision")) or TRACK_AUTHORITY_RULE_REVISION,
    )


def _resolve_data_driven_exact_instance(
    authority: Mapping[str, Any],
    row: Mapping[str, Any],
) -> dict[str, Any]:
    rule_revision = _text(authority.get("ruleRevision")) or TRACK_AUTHORITY_RULE_REVISION
    item_level = _positive_int(row.get("itemLevel"))
    if item_level is None:
        return _blocked(
            "TRACK_AUTHORITY_EXACT_ILEVEL_UNSUPPORTED",
            "S2 exact-instance progression requires an exact item level.",
            rule_revision=rule_revision,
        )
    records = _records_from_authority(authority)
    bonus_ids = _bonus_ids(row)
    slot = _normalized_slot(row.get("slot"))
    source_type = _text(row.get("sourceType")).lower()
    candidates = []
    for record in records:
        if record.itemLevel != item_level:
            continue
        if record.bonusIds and not bonus_ids.intersection(record.bonusIds):
            continue
        if not record.bonusIds:
            continue
        if record.eligibleSlots and slot not in record.eligibleSlots:
            continue
        if record.eligibleSourceTypes and source_type and source_type not in record.eligibleSourceTypes:
            continue
        candidates.append(record)
    if len(candidates) > 1:
        return _blocked(
            "TRACK_AUTHORITY_EXACT_TRACK_EVIDENCE_AMBIGUOUS",
            "S2 exact-instance bonus evidence matches multiple Track Authority records.",
            rule_revision=rule_revision,
        )
    if not candidates:
        return _blocked(
            "TRACK_AUTHORITY_EXACT_TRACK_EVIDENCE_MISSING",
            "S2 exact-instance evidence does not identify one governed track record.",
            rule_revision=rule_revision,
        )
    record = candidates[0]
    if record.progressionKind in {"crafted_quality", "ascendant"} and _dedicated_rank(row)[0]:
        return _blocked(
            "TRACK_AUTHORITY_EXACT_RANK_FORBIDDEN",
            "S2 crafted and Ascendant exact progression does not carry a rank.",
            rule_revision=rule_revision,
        )
    if record.progressionKind in {"crafted_quality", "ascendant"} and record.eligibleSourceTypes:
        if source_type == "crafted" and row.get("hasCraftedSource") is not True:
            return _blocked(
                "TRACK_AUTHORITY_EXACT_CRAFTED_SOURCE_MISSING",
                "Crafted S2 exact progression requires a verified crafted source.",
                rule_revision=rule_revision,
            )
    progression_state: dict[str, Any] = {
        "kind": record.progressionKind,
        "trackKey": record.publicTrackKey,
    }
    if record.progressionKind == "upgrade_track":
        progression_state.update({
            "rank": record.rank or record.maxRank,
            "maxRank": record.maxRank,
        })
    if record.originKind:
        progression_state["originKind"] = record.originKind
    if record.qualityKey:
        progression_state["qualityKey"] = record.qualityKey
    return _verified_exact_result(
        record.recordKey,
        progression_state,
        rule_revision=rule_revision,
    )


def resolve_legacy_browse_progression(
    binding: Any,
    row: Any,
) -> dict[str, Any]:
    """Resolve one legacy aggregate Browse row into a progression state."""

    authority = track_authority_for_binding(binding)
    if authority["status"] != "verified":
        return _authority_blocked_result(authority)
    if not isinstance(row, Mapping):
        return _blocked(
            "TRACK_AUTHORITY_ROW_MALFORMED",
            "Legacy Browse progression input must be an object.",
        )

    is_s2 = _text(authority.get("seasonRevision")).startswith("season-midnight-season-2:")
    records = _records_from_authority(authority) if is_s2 else None
    record = _record_for_row(row, records)
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
            rule_revision=_text(authority.get("ruleRevision")) or TRACK_AUTHORITY_RULE_REVISION,
        )

    if is_s2 and record.eligibleSourceTypes and _text(row.get("sourceType")).lower() not in record.eligibleSourceTypes:
        return _blocked_with_progression(
            "TRACK_AUTHORITY_SOURCE_UNSUPPORTED",
            "Legacy Browse row source is outside the governed S2 track eligibility.",
            record,
            {"kind": record.progressionKind, "trackKey": record.publicTrackKey},
        )
    normalized_row_slot = _normalized_slot(row.get("slot"))
    if is_s2 and record.eligibleSlots and normalized_row_slot not in record.eligibleSlots:
        return _blocked_with_progression(
            "TRACK_AUTHORITY_SLOT_UNSUPPORTED",
            "Legacy Browse row slot is outside the governed S2 track eligibility.",
            record,
            {"kind": record.progressionKind, "trackKey": record.publicTrackKey},
        )

    rank_is_present, dedicated_rank = _dedicated_rank(row)
    if record.progressionKind == "upgrade_track":
        progression_state = {
            "kind": "upgrade_track",
            "trackKey": record.publicTrackKey,
            "rank": record.maxRank,
            "maxRank": record.maxRank,
        }
        if rank_is_present and dedicated_rank != record.maxRank:
            return _blocked_with_progression(
                "TRACK_AUTHORITY_RANK_MISMATCH",
                "Dedicated track rank does not match the bound maximum rank.",
                record,
                progression_state,
            )
    else:
        progression_state = {
            "kind": record.progressionKind,
            "trackKey": record.publicTrackKey,
        }
        if record.originKind:
            progression_state["originKind"] = record.originKind
        if record.qualityKey:
            progression_state["qualityKey"] = record.qualityKey
        if rank_is_present:
            return _blocked_with_progression(
                "TRACK_AUTHORITY_RANK_FORBIDDEN",
                "Crafted quality and Ascendant progression states do not carry rank.",
                record,
                progression_state,
            )
        slot = _normalized_slot(row.get("slot"))
        if record.recordKey == "crafted_myth" and not _has_crafted_stats(row):
            return _blocked_with_progression(
                "TRACK_AUTHORITY_CRAFTED_STATS_MISSING",
                "Crafted-quality legacy rows require one explicit crafted-stat selection.",
                record,
                progression_state,
            )
        if record.recordKey == "void_upgrade" and not (
            slot in record.eligibleSlots
            or row.get("hasVoidInstanceSource") is True
            or row.get("hasObservedAscendantEvidence") is True
        ):
            return _blocked_with_progression(
                "TRACK_AUTHORITY_ASCENDANT_ELIGIBILITY_UNPROVEN",
                "Ordinary Ascendant eligibility lacks a governed slot, source, or observed exact-instance fact.",
                record,
                progression_state,
            )
        if record.recordKey == "crafted_void_upgrade":
            if slot not in record.eligibleSlots:
                return _blocked_with_progression(
                    "TRACK_AUTHORITY_CRAFTED_SLOT_UNSUPPORTED",
                    "Crafted Ascendant eligibility is restricted to governed weapon slots.",
                    record,
                    progression_state,
                )
            if not _has_crafted_stats(row):
                return _blocked_with_progression(
                    "TRACK_AUTHORITY_CRAFTED_STATS_MISSING",
                    "Crafted Ascendant rows require one explicit crafted-stat selection.",
                    record,
                    progression_state,
                )
            if row.get("hasTrackEvidence") is not True:
                return _blocked_with_progression(
                    "TRACK_AUTHORITY_TRACK_EVIDENCE_MISSING",
                    "Crafted Ascendant rows require explicit verified track evidence.",
                    record,
                    progression_state,
                )

    return {
        "status": "verified",
        "schemaRevision": TRACK_AUTHORITY_SCHEMA_REVISION,
        "ruleRevision": _text(authority.get("ruleRevision")) or TRACK_AUTHORITY_RULE_REVISION,
        "recordKey": record.recordKey,
        "progressionState": progression_state,
        "problems": [],
    }


def resolve_exact_instance_progression(
    binding: Any,
    row: Any,
) -> dict[str, Any]:
    """Resolve a sealed exact instance without deriving from generic rank fields."""

    authority = track_authority_for_binding(binding)
    if authority["status"] != "verified":
        return _authority_blocked_result(authority)
    if not isinstance(row, Mapping):
        return _blocked(
            "TRACK_AUTHORITY_ROW_MALFORMED",
            "Exact-instance progression input must be an object.",
        )
    if (
        _text(row.get("rowFamily")) != "exact_instance"
        or _text(row.get("status")).lower() != "verified"
    ):
        return _blocked(
            "TRACK_AUTHORITY_EXACT_VARIANT_UNVERIFIED",
            "Exact-instance progression requires a verified exact variant.",
        )
    if not _text(row.get("itemId")) or not _text(row.get("variantKey")):
        return _blocked(
            "TRACK_AUTHORITY_EXACT_IDENTITY_MISSING",
            "Exact-instance progression requires itemId and variantKey.",
        )

    if _text(authority.get("seasonRevision")).startswith("season-midnight-season-2:"):
        community_result = _resolve_community_observed_exact(authority, row)
        if community_result is not None:
            return community_result
        return _resolve_data_driven_exact_instance(authority, row)

    item_level = _positive_int(row.get("itemLevel"))
    bonus_ids = _bonus_ids(row)
    ascendant_markers = sorted(
        bonus_ids.intersection(_ASCENDANT_BONUS_ORIGINS)
    )
    if len(ascendant_markers) > 1:
        return _blocked(
            "TRACK_AUTHORITY_EXACT_TRACK_EVIDENCE_AMBIGUOUS",
            "Exact-instance bonus evidence identifies multiple Ascendant origins.",
        )
    if ascendant_markers:
        marker = ascendant_markers[0]
        origin_kind, expected_level = _ASCENDANT_BONUS_ORIGINS[marker]
        if item_level != expected_level:
            return _blocked(
                "TRACK_AUTHORITY_ILEVEL_MISMATCH",
                "Exact Ascendant item level does not match its governed bonus evidence.",
            )
        slot = _normalized_slot(row.get("slot"))
        if slot not in _ASCENDANT_SLOTS:
            return _blocked(
                "TRACK_AUTHORITY_ASCENDANT_ELIGIBILITY_UNPROVEN",
                "Ascendant exact instances require a governed weapon or trinket slot.",
            )
        if (
            origin_kind == "crafted_quality"
            and row.get("hasCraftedSource") is not True
        ):
            return _blocked(
                "TRACK_AUTHORITY_EXACT_CRAFTED_SOURCE_MISSING",
                "Crafted Ascendant exact instances require a verified crafted source for the same item.",
            )
        return _verified_exact_result(
            f"exact_ascendant_{marker}",
            {
                "kind": "ascendant",
                "trackKey": "void_upgrade",
                "originKind": origin_kind,
            },
        )

    if (
        item_level == 298
        and "13335" in bonus_ids
    ):
        return _verified_exact_result(
            "exact_myth_6_special_raid",
            {
                "kind": "upgrade_track",
                "trackKey": "myth",
                "rank": 6,
                "maxRank": 6,
            },
        )

    if item_level == 285 and "13622" in bonus_ids:
        if row.get("hasCraftedSource") is not True:
            return _blocked(
                "TRACK_AUTHORITY_EXACT_CRAFTED_SOURCE_MISSING",
                "Crafted exact-instance progression requires a verified crafted source for the same item.",
            )
        return _verified_exact_result(
            "exact_crafted_myth",
            {
                "kind": "crafted_quality",
                "trackKey": "myth",
                "qualityKey": "radiance_max",
            },
        )

    candidate_tracks = [
        track_key
        for track_key, markers in _EXACT_TRACK_MARKERS.items()
        if bonus_ids.intersection(markers)
        and item_level in _EXACT_TRACK_LADDERS[track_key]
    ]
    if len(candidate_tracks) > 1:
        return _blocked(
            "TRACK_AUTHORITY_EXACT_TRACK_EVIDENCE_AMBIGUOUS",
            "Exact-instance bonus evidence matches multiple upgrade tracks.",
        )
    if len(candidate_tracks) == 1:
        track_key = candidate_tracks[0]
        rank = _EXACT_TRACK_LADDERS[track_key][item_level]
        return _verified_exact_result(
            f"exact_{track_key}_{rank}",
            {
                "kind": "upgrade_track",
                "trackKey": track_key,
                "rank": rank,
                "maxRank": 6,
            },
        )

    supported_levels = {
        level
        for ladder in _EXACT_TRACK_LADDERS.values()
        for level in ladder
    }
    if item_level not in supported_levels:
        return _blocked(
            "TRACK_AUTHORITY_EXACT_ILEVEL_UNSUPPORTED",
            "The verified exact item level is outside all governed current-season upgrade ladders.",
        )
    return _blocked(
        "TRACK_AUTHORITY_EXACT_TRACK_EVIDENCE_MISSING",
        "Exact-instance item level is shared by upgrade tracks and lacks a governed track bonus marker.",
    )
