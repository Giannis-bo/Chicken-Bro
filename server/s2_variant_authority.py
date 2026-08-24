"""Field-scoped authority adapter for Midnight Season 2 item tracks.

The item bonus graph tells us which bonus-list branches exist.  It does not,
by itself, name a public S2 track.  This adapter only promotes a branch after
the exact group entry, extended-cost row, Mistcrest currency row, and numeric
item-level evidence agree.  Historical tracks remain explicit exclusions and
unqualified branches remain blocked.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from typing import Any


_TRACK_NAMES = {
    "adventurer": "Adventurer",
    "veteran": "Veteran",
    "champion": "Champion",
    "hero": "Hero",
    "myth": "Myth",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _rows_for(
    db2_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    table: str,
    field: str,
    value: str,
) -> list[Mapping[str, Any]]:
    return [
        row
        for row in db2_rows.get(table, [])
        if _text(row.get(field)) == value
    ]


def _row_ref(
    row: Mapping[str, Any],
    *,
    table: str,
    refs: Mapping[tuple[str, str], Sequence[str]] | None,
) -> list[str]:
    if refs is None:
        return []
    key = json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return list(refs.get((table, key), []))


def _base_result() -> dict[str, Any]:
    return {
        "status": "UNVERIFIED",
        "reasonCode": "VARIANT_TRACK_AUTHORITY_UNVERIFIED",
        "trackStatus": "UNVERIFIED",
        "sourceEligibilityStatus": "UNVERIFIED",
        "trackKey": None,
        "rank": None,
        "maxRank": None,
        "itemLevel": None,
        "currencyTypeId": None,
        "currencyName": None,
        "currencyDescription": None,
        "extendedCostIds": [],
        "evidenceKeys": {
            "groupId": None,
            "groupEntryId": None,
            "extendedCostIds": [],
            "currencyTypeIds": [],
        },
        "evidenceRefs": [],
    }


def classify_variant_upgrade(
    variant: Mapping[str, Any],
    *,
    db2_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    db2_refs: Mapping[tuple[str, str], Sequence[str]] | None = None,
) -> dict[str, Any]:
    """Classify one graph branch without inventing missing game facts."""

    result = _base_result()
    group_id = _text(variant.get("bonusListGroupId"))
    result["evidenceKeys"]["groupId"] = group_id or None
    if not group_id:
        return result

    group_entry = variant.get("bonusListGroupEntry")
    if not isinstance(group_entry, Mapping):
        result["reasonCode"] = "OFFICIAL_DB2_BONUS_LIST_GROUP_ENTRY_MISSING"
        return result
    group_entry_id = _positive_int(group_entry.get("ID"))
    result["evidenceKeys"]["groupEntryId"] = str(group_entry_id) if group_entry_id else None

    group_entries = _rows_for(
        db2_rows,
        "ItemBonusListGroupEntry",
        "ItemBonusListGroupID",
        group_id,
    )
    evidence_refs = set()
    group_fact = (variant.get("upgradeGroupEvidence") or {}).get("groupFact")
    if isinstance(group_fact, Mapping):
        evidence_refs.update(_row_ref(group_fact, table="ItemBonusListGroup", refs=db2_refs))
    for row in group_entries:
        evidence_refs.update(_row_ref(row, table="ItemBonusListGroupEntry", refs=db2_refs))
    evidence_refs.update(
        (variant.get("upgradeGroupEvidence") or {}).get("evidenceRefs") or []
    )
    result["evidenceRefs"] = sorted(evidence_refs)
    if not group_entries:
        result["reasonCode"] = "OFFICIAL_DB2_BONUS_LIST_GROUP_ENTRIES_MISSING"
        return result

    bonus_list_ids = {
        _text(value)
        for value in variant.get("bonusListIds") or []
        if _text(value)
    }
    matching_entries = [
        row
        for row in group_entries
        if _text(row.get("ItemBonusListID")) in bonus_list_ids
        or (
            group_entry_id is not None
            and _positive_int(row.get("ID")) == group_entry_id
        )
    ]
    if len(matching_entries) != 1:
        result["reasonCode"] = "OFFICIAL_DB2_BONUS_LIST_GROUP_ENTRY_AMBIGUOUS"
        return result
    selected_entry = matching_entries[0]
    evidence_refs.update(
        _row_ref(selected_entry, table="ItemBonusListGroupEntry", refs=db2_refs)
    )

    extended_cost_ids = sorted(
        {
            _text(row.get("ItemExtendedCostID"))
            for row in group_entries
            if _positive_int(row.get("ItemExtendedCostID"))
        },
        key=int,
    )
    result["extendedCostIds"] = extended_cost_ids
    result["evidenceKeys"]["extendedCostIds"] = extended_cost_ids
    if not extended_cost_ids:
        condition_facts = (variant.get("upgradeGroupEvidence") or {}).get("conditionFacts") or []
        if any(
            "no longer be upgraded" in _text(row.get("Failure_description_lang")).lower()
            for row in condition_facts
            if isinstance(row, Mapping)
        ):
            result.update(
                {
                    "status": "excluded",
                    "reasonCode": "OUT_OF_SCOPE_NON_S2_VARIANT_GROUP",
                    "trackStatus": "excluded",
                    "sourceEligibilityStatus": "excluded",
                }
            )
            return result
        result["reasonCode"] = "OFFICIAL_DB2_UPGRADE_EXTENDED_COST_MISSING"
        return result

    costs = [
        row
        for row in db2_rows.get("ItemExtendedCost", [])
        if _text(row.get("ID")) in set(extended_cost_ids)
    ]
    if len(costs) != len(extended_cost_ids):
        result["reasonCode"] = "OFFICIAL_DB2_UPGRADE_EXTENDED_COST_FACT_MISSING"
        return result
    for row in costs:
        evidence_refs.update(_row_ref(row, table="ItemExtendedCost", refs=db2_refs))
    currency_ids = sorted(
        {
            _text(row.get("CurrencyID_0"))
            for row in costs
            if _positive_int(row.get("CurrencyID_0"))
        },
        key=int,
    )
    result["evidenceKeys"]["currencyTypeIds"] = currency_ids
    if len(currency_ids) != 1:
        result["reasonCode"] = "OFFICIAL_DB2_UPGRADE_CURRENCY_AMBIGUOUS"
        return result

    currency_id = currency_ids[0]
    currencies = _rows_for(db2_rows, "CurrencyTypes", "ID", currency_id)
    if len(currencies) != 1:
        result["reasonCode"] = "OFFICIAL_DB2_UPGRADE_CURRENCY_FACT_MISSING"
        return result
    currency = currencies[0]
    evidence_refs.update(_row_ref(currency, table="CurrencyTypes", refs=db2_refs))
    result["evidenceRefs"] = sorted(evidence_refs)
    name = _text(currency.get("Name_lang"))
    description = _text(currency.get("Description_lang"))
    if "Midnight Season 2" not in description:
        result.update(
            {
                "status": "excluded",
                "reasonCode": "OUT_OF_SCOPE_NON_S2_VARIANT_GROUP",
                "trackStatus": "excluded",
                "currencyTypeId": currency_id,
                "currencyName": name,
                "currencyDescription": description,
            }
        )
        return result

    track_key = next(
        (
            key
            for key, label in _TRACK_NAMES.items()
            if name.startswith(f"{label} ")
        ),
        None,
    )
    if track_key is None:
        result["reasonCode"] = "OFFICIAL_DB2_S2_TRACK_NAME_UNRECOGNIZED"
        return result

    rank = _positive_int(selected_entry.get("SequenceValue"))
    max_rank = max(
        (
            _positive_int(row.get("SequenceValue")) or 0
            for row in group_entries
        ),
        default=0,
    )
    levels = sorted(
        {
            _positive_int(row.get("itemLevel"))
            for row in variant.get("itemScalingEvidence") or []
            if _positive_int(row.get("itemLevel"))
            and _text(row.get("status")) == "verified"
            and _positive_int(row.get("type")) in {49, 51}
        }
    )
    if rank is None or max_rank < rank or len(levels) != 1:
        result["reasonCode"] = "OFFICIAL_DB2_S2_VARIANT_NUMERIC_FACT_INCOMPLETE"
        return result

    result.update(
        {
            "status": "verified",
            "reasonCode": None,
            "trackStatus": "verified",
            "sourceEligibilityStatus": "verified",
            "trackKey": track_key,
            "rank": rank,
            "maxRank": max_rank,
            "itemLevel": levels[0],
            "currencyTypeId": currency_id,
            "currencyName": name,
            "currencyDescription": description,
        }
    )
    return result
