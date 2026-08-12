"""Canonical Season 2 tier-set membership and set-bonus evidence."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


SCHEMA_REVISION = "season-set-membership-v1"
SET_MEMBERSHIP_REVISION_PREFIX = "s2-sets:sha256:"
S2_SEASON_PREFIX = "season-midnight-season-2:"


def _text(value: Any) -> str:
    return str(value or "").strip()


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


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        _canonical(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _tokens(value: Any) -> list[str]:
    if isinstance(value, str):
        values = value.replace(",", "/").split("/")
    elif isinstance(value, (list, tuple, set, frozenset)):
        values = list(value)
    else:
        return []
    return sorted({_text(item) for item in values if _text(item)})


def _problem(code: str, message: str, path: str = "") -> dict[str, str]:
    result = {"code": code, "message": message}
    if path:
        result["path"] = path
    return result


def _binding_problems(binding: Any) -> tuple[str, list[dict[str, str]]]:
    row = binding if isinstance(binding, Mapping) else {}
    season_revision = _text(row.get("seasonRevision"))
    problems: list[dict[str, str]] = []
    if _text(row.get("seasonId")) != "midnight-season-2":
        problems.append(_problem(
            "SET_SEASON_ID_INVALID",
            "Set membership requires midnight-season-2.",
            "seasonId",
        ))
    if _text(row.get("scope")) != "end_game":
        problems.append(_problem(
            "SET_SCOPE_INVALID",
            "Set membership requires the complete end_game scope.",
            "scope",
        ))
    if not season_revision.startswith(S2_SEASON_PREFIX):
        problems.append(_problem(
            "SET_SEASON_REVISION_INVALID",
            "Set membership requires an S2 season revision.",
            "seasonRevision",
        ))
    if _text(row.get("status")).lower() != "verified":
        problems.append(_problem(
            "SET_BINDING_NOT_VERIFIED",
            "Set membership binding is not verified.",
            "status",
        ))
    return season_revision, problems


def _normalize_bonus_evidence(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        row["sourceRefs"] = _tokens(row.get("sourceRefs"))
        if "pieces" in row:
            try:
                row["pieces"] = int(row["pieces"])
            except (TypeError, ValueError, OverflowError):
                pass
        result.append(_canonical(row))
    return sorted(
        result,
        key=lambda row: (
            str(row.get("pieces", "")),
            _text(row.get("effectId")),
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        ),
    )


def _normalize_set_row(
    raw: Any,
    season_revision: str,
    index: int,
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    row = raw if isinstance(raw, Mapping) else {}
    problems: list[dict[str, str]] = []
    set_id = _text(
        row.get("setId")
        or row.get("itemSetId")
        or row.get("set_id")
    )
    path = f"setRows[{index}]"
    if not set_id:
        return None, [_problem(
            "SET_ID_MISSING",
            "Every tier-set row requires one canonical setId.",
            f"{path}.setId",
        )]
    row_revision = _text(row.get("seasonRevision"))
    if row_revision and row_revision != season_revision:
        problems.append(_problem(
            "SET_SEASON_REVISION_MISMATCH",
            "Tier-set row belongs to another season revision.",
            f"{path}.seasonRevision",
        ))
    status = _text(row.get("evidenceStatus") or row.get("status") or "verified").lower()
    if status != "verified":
        problems.append(_problem(
            "SET_EVIDENCE_NOT_VERIFIED",
            "Tier-set identity must be backed by verified evidence.",
            f"{path}.evidenceStatus",
        ))
    class_keys = _tokens(row.get("classKeys") or row.get("classes"))
    item_ids = _tokens(row.get("itemIds") or row.get("items"))
    source_refs = _tokens(row.get("sourceRefs") or row.get("sourceRefIds"))
    if not item_ids:
        problems.append(_problem(
            "SET_ITEM_IDS_MISSING",
            "Tier-set identity requires at least one itemId.",
            f"{path}.itemIds",
        ))
    if not source_refs:
        problems.append(_problem(
            "SET_SOURCE_REFS_MISSING",
            "Tier-set identity requires source references.",
            f"{path}.sourceRefs",
        ))
    if problems:
        return None, problems
    return {
        "setId": set_id,
        "itemSetId": set_id,
        "setName": _text(row.get("setName") or row.get("name")),
        "classKeys": class_keys,
        "itemIds": item_ids,
        "sourceRefs": source_refs,
        "setBonusEvidence": _normalize_bonus_evidence(row.get("setBonusEvidence")),
        "seasonRevision": season_revision,
        "status": "verified",
    }, []


def validate_set_membership(value: Any) -> list[dict[str, str]]:
    row = value if isinstance(value, Mapping) else {}
    problems: list[dict[str, str]] = []
    if _text(row.get("schemaRevision")) != SCHEMA_REVISION:
        problems.append(_problem(
            "SET_MEMBERSHIP_SCHEMA_INVALID",
            "Set membership schema revision is invalid.",
        ))
    season_revision = _text(row.get("seasonRevision"))
    if not season_revision.startswith(S2_SEASON_PREFIX):
        problems.append(_problem(
            "SET_MEMBERSHIP_SEASON_REVISION_INVALID",
            "Set membership season revision is invalid.",
        ))
    if not _text(row.get("setMembershipRevision")).startswith(SET_MEMBERSHIP_REVISION_PREFIX):
        problems.append(_problem(
            "SET_MEMBERSHIP_REVISION_INVALID",
            "Set membership requires a content revision.",
        ))
    if not isinstance(row.get("sets"), list):
        problems.append(_problem(
            "SET_MEMBERSHIP_SETS_MALFORMED",
            "Set membership sets must be a list.",
        ))
    if not isinstance(row.get("itemsById"), Mapping):
        problems.append(_problem(
            "SET_MEMBERSHIP_ITEMS_MALFORMED",
            "Set membership item index must be an object.",
        ))
    return problems


def build_set_membership(season_binding: Any, set_rows: Any) -> dict[str, Any]:
    """Build one deterministic S2 set identity/index and keep conflicts visible."""

    season_revision, problems = _binding_problems(season_binding)
    rows = set_rows if isinstance(set_rows, list) else []
    if not isinstance(set_rows, list):
        problems.append(_problem(
            "SET_ROWS_MALFORMED",
            "Tier-set rows must be a list.",
        ))

    normalized: dict[str, dict[str, Any]] = {}
    item_memberships: dict[str, set[str]] = {}
    for index, raw in enumerate(rows):
        record, row_problems = _normalize_set_row(raw, season_revision, index)
        problems.extend(row_problems)
        if record is None:
            continue
        set_id = record["setId"]
        existing = normalized.get(set_id)
        if existing is None:
            normalized[set_id] = record
        else:
            existing["classKeys"] = _tokens([*existing["classKeys"], *record["classKeys"]])
            existing["itemIds"] = _tokens([*existing["itemIds"], *record["itemIds"]])
            existing["sourceRefs"] = _tokens([*existing["sourceRefs"], *record["sourceRefs"]])
            existing["setBonusEvidence"] = _normalize_bonus_evidence(
                [*existing["setBonusEvidence"], *record["setBonusEvidence"]]
            )
        for item_id in record["itemIds"]:
            item_memberships.setdefault(item_id, set()).add(set_id)

    blocked_item_ids = sorted(
        item_id
        for item_id, set_ids in item_memberships.items()
        if len(set_ids) > 1
    )
    for item_id in blocked_item_ids:
        problems.append(_problem(
            "SET_MEMBERSHIP_CONFLICT",
            "One item is associated with multiple canonical tier-set IDs.",
            f"itemsById.{item_id}",
        ))

    sets = [_canonical(normalized[key]) for key in sorted(normalized)]
    items_by_id: dict[str, dict[str, Any]] = {}
    for set_record in sets:
        for item_id in set_record["itemIds"]:
            if item_id in blocked_item_ids:
                continue
            items_by_id[item_id] = {
                "itemId": item_id,
                "itemSetId": set_record["setId"],
                "setId": set_record["setId"],
                "setName": set_record["setName"],
                "classKeys": list(set_record["classKeys"]),
                "sourceRefs": list(set_record["sourceRefs"]),
                "setBonusEvidence": list(set_record["setBonusEvidence"]),
                "seasonRevision": season_revision,
                "status": "verified",
            }

    identity = {
        "schemaRevision": SCHEMA_REVISION,
        "seasonRevision": season_revision,
        "sets": sets,
        "itemsById": items_by_id,
        "blockedItemIds": blocked_item_ids,
    }
    revision = SET_MEMBERSHIP_REVISION_PREFIX + hashlib.sha256(
        _canonical_bytes(identity)
    ).hexdigest()
    blocker_codes = sorted({
        _text(problem.get("code"))
        for problem in problems
        if _text(problem.get("code"))
    })
    result = {
        "schemaRevision": SCHEMA_REVISION,
        "status": "verified" if not blocker_codes else "blocked",
        "seasonRevision": season_revision,
        "setMembershipRevision": revision,
        "sets": sets,
        "itemsById": items_by_id,
        "blockedItemIds": blocked_item_ids,
        "blockerCodes": blocker_codes,
        "problems": sorted(
            (_canonical(problem) for problem in problems),
            key=lambda problem: (
                _text(problem.get("code")),
                _text(problem.get("path")),
            ),
        )[:40],
        "coverage": {
            "setCount": len(sets),
            "itemCount": len(items_by_id),
            "blockedItemCount": len(blocked_item_ids),
        },
    }
    return _canonical(result)


__all__ = (
    "SCHEMA_REVISION",
    "SET_MEMBERSHIP_REVISION_PREFIX",
    "build_set_membership",
    "validate_set_membership",
)
