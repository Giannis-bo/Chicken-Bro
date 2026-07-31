"""Pure contracts for official current-season PVE source capture.

The network capture CLI lives in ``scripts/capture-season-pve-official-snapshot.py``.
This module deliberately owns only deterministic selection and validation so
that a source response cannot be promoted merely because HTTP returned 200.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


class OfficialCaptureContractError(ValueError):
    """Raised when an official response cannot prove capture completeness."""


_TYPOGRAPHIC_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "\u2032": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u201f": '"',
        "\u2033": '"',
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
    }
)


def canonical_official_name(value: Any) -> str:
    """Normalize typography without discarding business-significant words."""

    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.translate(_TYPOGRAPHIC_TRANSLATION)
    return re.sub(r"\s+", " ", text).strip().casefold()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _ref_id(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    direct = _text(value.get("id"))
    if direct:
        return direct
    href = _text(((value.get("key") or {}).get("href")))
    match = re.search(r"/(\d+)(?:\?|$)", href)
    return match.group(1) if match else ""


def _localized_name(value: Any) -> str:
    if isinstance(value, dict):
        for locale in ("en_US", "en_GB"):
            if _text(value.get(locale)):
                return _text(value.get(locale))
        return next((_text(item) for item in value.values() if _text(item)), "")
    return _text(value)


def journal_loot_reference(value: Any) -> dict[str, str]:
    """Return both Blizzard's loot-relation key and the referenced item key."""

    row = value if isinstance(value, dict) else {}
    loot_relation_id = _text(row.get("id"))
    item = row.get("item") if isinstance(row.get("item"), dict) else {}
    item_id = _ref_id(item)
    if not loot_relation_id or not item_id:
        raise OfficialCaptureContractError(
            "official Journal loot row requires relation id and item id"
        )
    return {
        "lootRelationId": loot_relation_id,
        "itemId": item_id,
        "itemName": _text(item.get("name")),
    }


def bounded_capture_result(summary: Any) -> dict[str, Any]:
    """Build a small console result without serializing the full evidence graph."""

    if not isinstance(summary, dict):
        raise OfficialCaptureContractError("capture summary must be an object")
    journal = summary.get("journalCapture")
    profession = summary.get("professionCapture")
    class_sets = summary.get("classSetCapture")
    gaps = summary.get("gaps")
    if not isinstance(journal, dict) or not isinstance(gaps, list):
        raise OfficialCaptureContractError(
            "capture summary requires journalCapture and gaps"
        )
    return {
        key: summary[key]
        for key in (
            "schemaRevision",
            "status",
            "capturedAt",
            "asOf",
            "requestCount",
            "requestBytes",
            "officialItemSearch",
            "mythicSeason",
        )
    } | {
        "journalCapture": {
            key: journal.get(key)
            for key in ("instanceCount", "encounterCount", "itemCount")
        },
        "professionCapture": {
            key: (profession or {}).get(key)
            for key in (
                "recipeCount",
                "exactNameCandidateCount",
                "membershipComplete",
            )
        },
        "classSetCapture": {
            "setCount": (class_sets or {}).get("setCount"),
        },
        "gapCount": len(gaps),
    }


def index_official_item_search(
    payload: Any,
) -> dict[str, list[dict[str, Any]]]:
    """Validate and index the one-page level-90 equippable Item Search result."""

    if not isinstance(payload, dict):
        raise OfficialCaptureContractError(
            "official item search payload must be an object"
        )
    results = payload.get("results")
    if not isinstance(results, list):
        raise OfficialCaptureContractError(
            "official item search results must be a list"
        )
    page = payload.get("page")
    page_count = payload.get("pageCount")
    page_size = payload.get("pageSize")
    if page != 1 or page_count != 1:
        raise OfficialCaptureContractError(
            "official item search must fit in exactly one captured page"
        )
    if payload.get("resultCountCapped") is True:
        raise OfficialCaptureContractError(
            "official item search result is capped"
        )
    if (
        not isinstance(page_size, int)
        or isinstance(page_size, bool)
        or page_size != len(results)
    ):
        raise OfficialCaptureContractError(
            "official item search pageSize does not match captured rows"
        )

    indexed: dict[str, list[dict[str, Any]]] = {}
    seen_ids = set()
    for raw_row in results:
        data = (
            raw_row.get("data")
            if isinstance(raw_row, dict)
            and isinstance(raw_row.get("data"), dict)
            else {}
        )
        item_id = _text(data.get("id"))
        name = _localized_name(data.get("name"))
        if not item_id or not name:
            raise OfficialCaptureContractError(
                "official item search row requires id and English name"
            )
        if item_id in seen_ids:
            raise OfficialCaptureContractError(
                f"official item search has duplicate item id {item_id}"
            )
        seen_ids.add(item_id)
        if data.get("required_level") != 90 or data.get("is_equippable") is not True:
            raise OfficialCaptureContractError(
                f"official item search row {item_id} violates level-90 equipment scope"
            )
        indexed.setdefault(canonical_official_name(name), []).append(data)
    for rows in indexed.values():
        rows.sort(key=lambda row: int(row["id"]))
    return dict(sorted(indexed.items()))


def exact_item_search_matches(
    payload: Any,
    expected_name: Any,
) -> list[dict[str, Any]]:
    """Return uncapped equippable exact-name rows from one official search page."""

    if not isinstance(payload, dict) or not isinstance(
        payload.get("results"),
        list,
    ):
        raise OfficialCaptureContractError(
            "official exact item search requires results"
        )
    results = payload["results"]
    page_size = payload.get("pageSize")
    if (
        payload.get("page") != 1
        or payload.get("pageCount") != 1
        or payload.get("resultCountCapped") is True
        or not isinstance(page_size, int)
        or isinstance(page_size, bool)
        or page_size < len(results)
    ):
        raise OfficialCaptureContractError(
            "official exact item search is incomplete or capped"
        )
    target = canonical_official_name(expected_name)
    if not target:
        raise OfficialCaptureContractError(
            "official exact item search requires a target name"
        )
    matches = []
    seen_ids = set()
    for raw_row in results:
        data = (
            raw_row.get("data")
            if isinstance(raw_row, dict)
            and isinstance(raw_row.get("data"), dict)
            else {}
        )
        item_id = _text(data.get("id"))
        if (
            not item_id
            or data.get("is_equippable") is not True
            or canonical_official_name(_localized_name(data.get("name")))
            != target
        ):
            continue
        if item_id in seen_ids:
            raise OfficialCaptureContractError(
                f"official exact item search has duplicate item id {item_id}"
            )
        seen_ids.add(item_id)
        matches.append(data)
    return sorted(matches, key=lambda row: int(row["id"]))


def recipe_candidates_from_complete_item_index(
    item_index: Any,
    recipe_name: Any,
) -> dict[str, Any]:
    """Project recipe-name candidates only from a previously complete index.

    Blizzard Item Search is fuzzy and may cap broad name queries even when the
    caller quotes a value.  A per-recipe search therefore cannot close a
    membership gap.  The capture path may use only the already validated,
    uncapped level-90 equippable index; other data sources remain discovery
    evidence and must not be relabelled as official recipe membership.
    """

    if not isinstance(item_index, dict):
        raise OfficialCaptureContractError(
            "official item index must be an object"
        )
    name = canonical_official_name(recipe_name)
    if not name:
        raise OfficialCaptureContractError(
            "recipe candidate projection requires a recipe name"
        )
    raw_matches = item_index.get(name, [])
    if not isinstance(raw_matches, list):
        raise OfficialCaptureContractError(
            "official item index candidate rows must be a list"
        )
    matches = list(raw_matches)
    method = (
        "level_90_equippable_name_unique"
        if len(matches) == 1
        else "level_90_equippable_name_ambiguous"
        if matches
        else "none"
    )
    return {
        "candidateJoinMethod": method,
        "matches": matches,
    }


def validate_official_item_range_page(
    payload: Any,
    *,
    start_id: int,
    end_id: int,
    expected_page_size: int | None = None,
) -> dict[str, Any]:
    """Validate one cursor-bounded official Item Search response."""

    if (
        not isinstance(start_id, int)
        or isinstance(start_id, bool)
        or not isinstance(end_id, int)
        or isinstance(end_id, bool)
        or start_id < 1
        or end_id < start_id
    ):
        raise OfficialCaptureContractError(
            "official item range requires positive ordered bounds"
        )
    if (
        expected_page_size is not None
        and (
            not isinstance(expected_page_size, int)
            or isinstance(expected_page_size, bool)
            or expected_page_size < 1
        )
    ):
        raise OfficialCaptureContractError(
            "official item range expected page size is invalid"
        )
    if not isinstance(payload, dict) or not isinstance(
        payload.get("results"),
        list,
    ):
        raise OfficialCaptureContractError(
            "official item range response requires results"
        )
    results = payload["results"]
    page_size = payload.get("pageSize")
    max_page_size = payload.get("maxPageSize")
    page_count = payload.get("pageCount")
    result_count_capped = payload.get("resultCountCapped")
    valid_page_count = (
        page_count == 0
        if not results
        else (
            isinstance(page_count, int)
            and not isinstance(page_count, bool)
            and page_count >= 1
        )
    )
    if (
        payload.get("page") != 1
        or not valid_page_count
        or not isinstance(page_size, int)
        or isinstance(page_size, bool)
        or page_size != len(results)
        or not isinstance(max_page_size, int)
        or isinstance(max_page_size, bool)
        or max_page_size < 1
        or page_size > max_page_size
        or (
            "resultCountCapped" in payload
            and not isinstance(result_count_capped, bool)
        )
    ):
        raise OfficialCaptureContractError(
            "official item range page metadata is incomplete"
        )
    rows = []
    previous_id = start_id - 1
    for raw_row in results:
        data = (
            raw_row.get("data")
            if isinstance(raw_row, dict)
            and isinstance(raw_row.get("data"), dict)
            else {}
        )
        item_id = data.get("id")
        if (
            not isinstance(item_id, int)
            or isinstance(item_id, bool)
            or item_id < start_id
            or item_id > end_id
            or item_id <= previous_id
            or data.get("is_equippable") is not True
        ):
            raise OfficialCaptureContractError(
                "official item range rows require ordered in-range equipment"
            )
        previous_id = item_id
        rows.append(data)
    capped = result_count_capped is True
    capped_page_size = (
        expected_page_size
        if expected_page_size is not None
        else max_page_size
    )
    if capped and len(rows) != capped_page_size:
        raise OfficialCaptureContractError(
            "official item range cap does not fill requested page size"
        )
    if capped and not rows:
        raise OfficialCaptureContractError(
            "official item range cannot advance an empty capped page"
        )
    terminal = (
        not rows
        or rows[-1]["id"] >= end_id
        or (not capped and page_count == 1)
    )
    return {
        "rows": rows,
        "terminal": terminal,
        "nextCursor": (
            None
            if terminal
            else rows[-1]["id"] + 1
        ),
        "resultCountCapped": capped,
    }


_EQUIPMENT_RECIPE_CATEGORIES = {
    "blacksmithing": {
        "weapons",
        "armor",
    },
    "leatherworking": {
        "leather armor",
        "mail armor",
    },
    "tailoring": {
        "garments",
        "sunfire silk garments",
        "arcanoweave garments",
    },
    "engineering": {
        "cloth equipment",
        "leather equipment",
        "mail equipment",
        "plate equipment",
        "guns",
    },
    "enchanting": {
        "wands",
    },
    "jewelcrafting": {
        "regal rings",
        "luxurious lockets",
    },
    "alchemy": {
        "alchemist stones",
    },
    "inscription": {
        "weapons",
        "trinkets",
    },
}


def equipment_recipe_refs(
    profession_name: Any,
    skill_tier: Any,
) -> list[dict[str, str]]:
    """Select PVE power-equipment recipes without admitting PvP/tool rows."""

    profession = _text(profession_name)
    allowed_categories = _EQUIPMENT_RECIPE_CATEGORIES.get(
        canonical_official_name(profession),
        set(),
    )
    if not allowed_categories:
        raise OfficialCaptureContractError(
            f"unsupported equipment profession {profession or 'missing'}"
        )
    if not isinstance(skill_tier, dict) or not isinstance(
        skill_tier.get("categories"),
        list,
    ):
        raise OfficialCaptureContractError(
            f"{profession} skill tier requires categories"
        )
    rows = []
    seen = set()
    for category in skill_tier["categories"]:
        if not isinstance(category, dict):
            raise OfficialCaptureContractError(
                f"{profession} category must be an object"
            )
        category_name = _text(category.get("name"))
        if canonical_official_name(category_name) not in allowed_categories:
            continue
        recipes = category.get("recipes")
        if not isinstance(recipes, list):
            raise OfficialCaptureContractError(
                f"{profession}/{category_name} recipes must be a list"
            )
        for recipe in recipes:
            recipe_id = _ref_id(recipe)
            recipe_name = _text(
                recipe.get("name") if isinstance(recipe, dict) else ""
            )
            if not recipe_id or not recipe_name:
                raise OfficialCaptureContractError(
                    f"{profession}/{category_name} recipe requires id and name"
                )
            if "competitor" in canonical_official_name(recipe_name):
                continue
            if recipe_id in seen:
                raise OfficialCaptureContractError(
                    f"duplicate official recipe id {recipe_id}"
                )
            seen.add(recipe_id)
            rows.append(
                {
                    "profession": profession,
                    "category": category_name,
                    "recipeId": recipe_id,
                    "name": recipe_name,
                }
            )
    return sorted(
        rows,
        key=lambda row: (
            row["profession"],
            row["category"],
            int(row["recipeId"]),
        ),
    )


def _instance_row(value: Any) -> dict[str, str]:
    row = value if isinstance(value, dict) else {}
    return {
        "instanceId": _ref_id(row),
        "name": _text(row.get("name")),
    }


def _dedupe_instances(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    indexed = {}
    for row in rows:
        if row["instanceId"] and row["name"]:
            indexed[row["instanceId"]] = row
    return [
        indexed[key]
        for key in sorted(
            indexed,
            key=lambda value: int(value) if value.isdigit() else value,
        )
    ]


def select_journal_targets(
    *,
    mythic_dungeons: Any,
    midnight_expansion: Any,
    journal_instance_index: Any,
    timewalking_names: list[str],
) -> dict[str, Any]:
    """Partition current Journal targets by source without silent omission."""

    if not isinstance(mythic_dungeons, list):
        raise OfficialCaptureContractError("mythic_dungeons must be a list")
    if not isinstance(midnight_expansion, dict):
        raise OfficialCaptureContractError(
            "midnight_expansion must be an object"
        )
    if not isinstance(journal_instance_index, dict) or not isinstance(
        journal_instance_index.get("instances"),
        list,
    ):
        raise OfficialCaptureContractError(
            "journal_instance_index requires instances"
        )

    mythic_plus = []
    gaps = []
    for dungeon in mythic_dungeons:
        raw_instance = (
            dungeon.get("dungeon")
            if isinstance(dungeon, dict)
            and isinstance(dungeon.get("dungeon"), dict)
            else {}
        )
        row = _instance_row(raw_instance)
        if not row["instanceId"] or not row["name"]:
            gaps.append(
                {
                    "reasonCode": "MYTHIC_DUNGEON_JOURNAL_ID_MISSING",
                    "name": _text(
                        dungeon.get("name")
                        if isinstance(dungeon, dict)
                        else ""
                    ),
                }
            )
            continue
        mythic_plus.append(row)

    midnight_dungeon = [
        _instance_row(row)
        for row in midnight_expansion.get("dungeons") or []
    ]
    midnight_raid = []
    midnight_world_boss = []
    for raw_row in midnight_expansion.get("raids") or []:
        row = _instance_row(raw_row)
        if canonical_official_name(row["name"]) == "midnight":
            midnight_world_boss.append(row)
        else:
            midnight_raid.append(row)

    journal_by_name: dict[str, list[dict[str, str]]] = {}
    for raw_row in journal_instance_index["instances"]:
        row = _instance_row(raw_row)
        if not row["instanceId"] or not row["name"]:
            continue
        journal_by_name.setdefault(
            canonical_official_name(row["name"]),
            [],
        ).append(row)
    timewalking = []
    for name in timewalking_names:
        matches = journal_by_name.get(canonical_official_name(name), [])
        if not matches:
            gaps.append(
                {
                    "reasonCode": "OFFICIAL_JOURNAL_INSTANCE_NOT_FOUND",
                    "name": _text(name),
                }
            )
            continue
        timewalking.extend(matches)

    return {
        "mythic_plus": _dedupe_instances(mythic_plus),
        "midnight_dungeon": _dedupe_instances(midnight_dungeon),
        "midnight_raid": _dedupe_instances(midnight_raid),
        "midnight_world_boss": _dedupe_instances(midnight_world_boss),
        "timewalking": _dedupe_instances(timewalking),
        "gaps": sorted(
            gaps,
            key=lambda row: (
                row["reasonCode"],
                canonical_official_name(row.get("name")),
            ),
        ),
    }
