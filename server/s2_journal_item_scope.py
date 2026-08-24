"""Scope adapter for official Journal encounter-item rows.

The Blizzard Journal API exposes an encounter's item identities, but it does
not expose the difficulty mask carried by the client loot-table row.  This
adapter uses only the bounded official-client DB2 ``JournalEncounterItem``
capture to keep difficulty-specific dungeon entries out of the M+ membership
set.  It does not infer an item level, track, or bonus semantics.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any


_ENCOUNTER_KEY = re.compile(r"(?:^|:)encounter:([1-9][0-9]*)$")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _row_ref(
    row: Mapping[str, Any],
    *,
    refs: Mapping[tuple[str, str], Sequence[str]],
) -> list[str]:
    key = json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return list(refs.get(("JournalEncounterItem", key), []))


def _base_result(*, item_id: str, encounter_id: str | None) -> dict[str, Any]:
    return {
        "status": "UNVERIFIED",
        "includeInMythicPlusMembership": False,
        "reasonCode": "OFFICIAL_DB2_JOURNAL_ENCOUNTER_ITEM_ROW_MISSING",
        "authority": "official_client_db2.JournalEncounterItem",
        "itemId": item_id,
        "journalEncounterId": encounter_id,
        "difficultyMasks": [],
        "rows": [],
        "evidenceRefs": [],
        "policy": "include_when_any_matching_row_has_DifficultyMask_minus_one",
    }


def classify_mythic_plus_journal_item_scope(
    membership: Mapping[str, Any],
    *,
    db2_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    db2_refs: Mapping[tuple[str, str], Sequence[str]],
) -> dict[str, Any]:
    """Classify one M+ Journal membership without projecting track facts.

    A matching ``DifficultyMask=-1`` row is the current Journal all-
    difficulty entry used by the frozen S2 M+ pool.  A membership that only
    has non-negative difficulty-specific rows is explicitly excluded.  Missing
    or malformed evidence remains ``UNVERIFIED`` and is never included.
    """

    item_id = _text(membership.get("itemId"))
    raw_source_key = _text(membership.get("rawSourceKey"))
    match = _ENCOUNTER_KEY.search(raw_source_key)
    encounter_id = match.group(1) if match else None
    result = _base_result(item_id=item_id, encounter_id=encounter_id)
    if not item_id or encounter_id is None:
        result["reasonCode"] = "MYTHIC_PLUS_JOURNAL_SOURCE_KEY_UNPARSABLE"
        return result

    matching_rows = [
        dict(row)
        for row in db2_rows.get("JournalEncounterItem", [])
        if isinstance(row, Mapping)
        and _text(row.get("JournalEncounterID")) == encounter_id
        and _text(row.get("ItemID")) == item_id
    ]
    result["rows"] = matching_rows
    result["evidenceRefs"] = sorted(
        {
            ref
            for row in matching_rows
            for ref in _row_ref(row, refs=db2_refs)
            if _text(ref)
        }
    )
    if not matching_rows:
        return result

    masks: list[int] = []
    for row in matching_rows:
        value = row.get("DifficultyMask")
        if isinstance(value, bool):
            result["reasonCode"] = "OFFICIAL_DB2_JOURNAL_DIFFICULTY_MASK_INVALID"
            return result
        try:
            mask = int(value)
        except (TypeError, ValueError):
            result["reasonCode"] = "OFFICIAL_DB2_JOURNAL_DIFFICULTY_MASK_INVALID"
            return result
        if mask < -1:
            result["reasonCode"] = "OFFICIAL_DB2_JOURNAL_DIFFICULTY_MASK_INVALID"
            return result
        masks.append(mask)
    result["difficultyMasks"] = sorted(set(masks))
    if -1 in masks:
        result.update(
            {
                "status": "verified",
                "includeInMythicPlusMembership": True,
                "reasonCode": None,
            }
        )
        return result

    result.update(
        {
            "status": "excluded",
            "reasonCode": "OUT_OF_SCOPE_NON_MPLUS_JOURNAL_DIFFICULTY_MASK",
        }
    )
    return result


__all__ = ["classify_mythic_plus_journal_item_scope"]
