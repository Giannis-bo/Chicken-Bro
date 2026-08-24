#!/usr/bin/env python3
"""Capture the explicitly authorized, field-scoped S2 DB2 evidence graph."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.s2_limited_db2 import (  # noqa: E402
    LimitedDb2Error,
    build_bounded_db2_query_plan,
    capture_bounded_db2_evidence,
    collect_s2_official_db2_targets,
    validate_db2_field_allowlist,
)


DEFAULT_ALLOWLIST = (
    ROOT
    / "server"
    / "data"
    / "midnight-season-2"
    / "db2-field-allowlist-v1.json"
)


class WagoDb2FindReader:
    """Read only the fixed Wago exact-filter endpoint; raw rows stay in memory."""

    def __init__(self, *, timeout_seconds: int = 20):
        self.timeout_seconds = max(1, int(timeout_seconds))

    def get(self, request: dict, *, page: int):
        parsed = urlsplit(str(request["url"]))
        query = dict(request["query"])
        if page > 1:
            query["page"] = page
        url = urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), "")
        )
        last_error = None
        for attempt in range(3):
            try:
                http_request = Request(
                    url,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "wow-s2-limited-db2-capture/1",
                        "Connection": "close",
                    },
                )
                with urlopen(http_request, timeout=self.timeout_seconds) as response:
                    body = response.read()
                payload = json.loads(body.decode("utf-8"))
                return {
                    "url": url,
                    "bodySha256": hashlib.sha256(body).hexdigest(),
                    "bodyBytes": len(body),
                    "payload": payload,
                }
            except Exception as error:  # pragma: no cover - live network path
                last_error = error
                if attempt < 2:
                    time.sleep(2**attempt)
        raise LimitedDb2Error(f"Wago DB2 exact query failed: {last_error}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture bounded Midnight Season 2 DB2 evidence."
    )
    parser.add_argument(
        "--official-capture-manifest",
        required=True,
        help="capture-manifest.json from the completed Blizzard API capture",
    )
    parser.add_argument(
        "--allowlist",
        default=str(DEFAULT_ALLOWLIST),
        help="bounded DB2 field allowlist JSON",
    )
    parser.add_argument("--output-root")
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="bounded concurrent exact requests; default: 1",
    )
    parser.add_argument(
        "--item-id",
        action="append",
        default=[],
        help="restrict to an item id already present in the official capture; repeatable",
    )
    parser.add_argument(
        "--recipe-id",
        action="append",
        default=[],
        help="restrict to a recipe id already present in the official capture; repeatable",
    )
    parser.add_argument(
        "--mythic-plus-season-id",
        action="append",
        default=[],
        help="restrict to a Mythic+ season id already present in the official capture; repeatable",
    )
    parser.add_argument(
        "--display-season-id",
        action="append",
        default=[],
        help="capture an explicitly authorized DisplaySeason id derived from the current official Mythic+ season; repeatable",
    )
    parser.add_argument(
        "--map-id",
        action="append",
        default=[],
        help="capture an exact MapDifficulty graph for an explicitly allowlisted official Journal map id; repeatable",
    )
    parser.add_argument(
        "--journal-encounter-id",
        action="append",
        default=[],
        help="restrict to a Journal encounter id already present in the official capture; repeatable",
    )
    parser.add_argument(
        "--item-scaling-config-id",
        action="append",
        default=[],
        help="capture an exact ItemScalingConfig id derived from an allowlisted ItemBonus edge; repeatable",
    )
    parser.add_argument(
        "--only-item-scaling-config",
        action="store_true",
        help="ignore official item/recipe/season roots and capture only explicit ItemScalingConfig foreign keys",
    )
    parser.add_argument(
        "--only-display-season",
        action="store_true",
        help="ignore official roots and capture only explicit DisplaySeason ids",
    )
    parser.add_argument(
        "--only-journal-encounter",
        action="store_true",
        help="ignore other official roots and capture only JournalEncounterItem rows for captured encounters",
    )
    parser.add_argument(
        "--item-bonus-list-group-id",
        action="append",
        default=[],
        help="capture an exact ItemBonusListGroup id derived from an allowlisted bonus-tree edge; repeatable",
    )
    parser.add_argument(
        "--only-item-bonus-list-group",
        action="store_true",
        help="ignore official item/recipe/season roots and capture only explicit ItemBonusListGroup foreign keys",
    )
    parser.add_argument(
        "--item-bonus-tree-id",
        action="append",
        default=[],
        help="capture an exact ItemBonusTree root derived from an allowlisted ItemXBonusTree edge; repeatable",
    )
    parser.add_argument(
        "--only-item-bonus-tree",
        action="store_true",
        help="ignore official item/recipe/season roots and capture only explicit ItemBonusTree roots",
    )
    parser.add_argument(
        "--item-context",
        action="append",
        default=[],
        help="capture an exact ItemCreationContext row for an explicitly scoped item-context value; repeatable",
    )
    parser.add_argument(
        "--only-item-creation-context",
        action="store_true",
        help="ignore official item/recipe/season roots and capture only explicit ItemCreationContext values",
    )
    parser.add_argument(
        "--modified-crafting-reagent-item-id",
        action="append",
        default=[],
        help="capture an exact ModifiedCraftingReagentItem id derived from an allowlisted crafting-item edge; repeatable",
    )
    parser.add_argument(
        "--only-modified-crafting-reagent-item",
        action="store_true",
        help="ignore official item/recipe/season roots and capture only explicit ModifiedCraftingReagentItem foreign keys",
    )
    parser.add_argument(
        "--modified-crafting-category-id",
        action="append",
        default=[],
        help="capture an exact ModifiedCraftingCategory and its reagent-item rows derived from official slot-type compatibility; repeatable",
    )
    parser.add_argument(
        "--only-modified-crafting-category",
        action="store_true",
        help="ignore official item/recipe/season roots and capture only explicit ModifiedCraftingCategory ids",
    )
    parser.add_argument(
        "--enchant-id",
        action="append",
        default=[],
        help="capture an exact SpellItemEnchantment id explicitly authorized for equipment serialization; repeatable",
    )
    parser.add_argument(
        "--only-enchant",
        action="store_true",
        help="ignore official roots and capture only explicit SpellItemEnchantment ids",
    )
    parser.add_argument(
        "--spell-id",
        action="append",
        default=[],
        help="capture an exact crafting-option Spell and its SpellEffect rows; repeatable",
    )
    parser.add_argument(
        "--only-spell",
        action="store_true",
        help="ignore official roots and capture only explicit crafting-option spell ids",
    )
    parser.add_argument(
        "--crafting-data-id",
        action="append",
        default=[],
        help="capture exact CraftingData and CraftingDataItemQuality rows; repeatable",
    )
    parser.add_argument(
        "--only-crafting-data",
        action="store_true",
        help="ignore official roots and capture only explicit CraftingData ids",
    )
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--dry-run-request-plan", action="store_true")
    return parser


def _load_json(path: str) -> dict:
    return json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))


def _restrict_targets(targets: dict, args: argparse.Namespace) -> dict:
    selectors = {
        "itemIds": list(args.item_id),
        "recipeIds": list(args.recipe_id),
        "mythicPlusSeasonIds": list(args.mythic_plus_season_id),
        "displaySeasonIds": list(args.display_season_id),
        "mapIds": list(args.map_id),
        "journalEncounterIds": list(args.journal_encounter_id),
    }
    if not any(selectors.values()) and not args.display_season_id:
        return targets

    restricted = {}
    for key, requested in selectors.items():
        allowed = set(targets.get(key, []))
        normalized = []
        for value in requested:
            text = str(value).strip()
            if not text.isdigit() or int(text) <= 0:
                raise LimitedDb2Error(f"{key} selector must be a positive integer id")
            canonical = str(int(text))
            if canonical not in allowed:
                raise LimitedDb2Error(
                    f"{key} selector {canonical} is not present in official capture"
                )
            normalized.append(canonical)
        restricted[key] = sorted(set(normalized), key=int)
    if args.display_season_id:
        normalized_display = []
        for value in args.display_season_id:
            text = str(value).strip()
            if not text.isdigit() or int(text) <= 0:
                raise LimitedDb2Error(
                    "display-season-id selector must be a positive integer id"
                )
            normalized_display.append(str(int(text)))
        restricted["displaySeasonIds"] = sorted(set(normalized_display), key=int)
    return restricted


def _add_bounded_foreign_key_targets(targets: dict, args: argparse.Namespace) -> dict:
    values = []
    for value in args.item_scaling_config_id:
        text = str(value).strip()
        if not text.isdigit() or int(text) <= 0:
            raise LimitedDb2Error(
                "item-scaling-config-id must be a positive integer id"
            )
        values.append(str(int(text)))
    result = dict(targets)
    context_values = []
    for value in args.item_context:
        text = str(value).strip()
        if not text.isdigit() or int(text) < 0:
            raise LimitedDb2Error(
                "item-context must be a non-negative integer context value"
            )
        context_values.append(str(int(text)))
    if context_values:
        result["itemContextValues"] = sorted(set(context_values), key=int)
    tree_values = []
    for value in args.item_bonus_tree_id:
        text = str(value).strip()
        if not text.isdigit() or int(text) <= 0:
            raise LimitedDb2Error("item-bonus-tree-id must be a positive integer id")
        tree_values.append(str(int(text)))
    if tree_values:
        result["itemBonusTreeIds"] = sorted(set(tree_values), key=int)
    map_values = []
    for value in args.map_id:
        text = str(value).strip()
        if not text.isdigit() or int(text) <= 0:
            raise LimitedDb2Error("map-id must be a positive integer id")
        map_values.append(str(int(text)))
    if map_values:
        result["mapIds"] = sorted(set(map_values), key=int)
    if values:
        result["itemScalingConfigIds"] = sorted(set(values), key=int)
    group_values = []
    for value in args.item_bonus_list_group_id:
        text = str(value).strip()
        if not text.isdigit() or int(text) <= 0:
            raise LimitedDb2Error(
                "item-bonus-list-group-id must be a positive integer id"
            )
        group_values.append(str(int(text)))
    if group_values:
        result["itemBonusListGroupIds"] = sorted(set(group_values), key=int)
    modifier_values = []
    for value in args.modified_crafting_reagent_item_id:
        text = str(value).strip()
        if not text.isdigit() or int(text) <= 0:
            raise LimitedDb2Error(
                "modified-crafting-reagent-item-id must be a positive integer id"
            )
        modifier_values.append(str(int(text)))
    if modifier_values:
        result["modifiedCraftingReagentItemIds"] = sorted(
            set(modifier_values), key=int
        )
    category_values = []
    for value in args.modified_crafting_category_id:
        text = str(value).strip()
        if not text.isdigit() or int(text) <= 0:
            raise LimitedDb2Error(
                "modified-crafting-category-id must be a positive integer id"
            )
        category_values.append(str(int(text)))
    if category_values:
        result["modifiedCraftingCategoryIds"] = sorted(
            set(category_values), key=int
        )
    enchant_values = []
    for value in args.enchant_id:
        text = str(value).strip()
        if not text.isdigit() or int(text) <= 0:
            raise LimitedDb2Error("enchant-id must be a positive integer id")
        enchant_values.append(str(int(text)))
    if enchant_values:
        result["enchantIds"] = sorted(set(enchant_values), key=int)
    spell_values = []
    for value in args.spell_id:
        text = str(value).strip()
        if not text.isdigit() or int(text) <= 0:
            raise LimitedDb2Error("spell-id must be a positive integer id")
        spell_values.append(str(int(text)))
    if spell_values:
        result["spellIds"] = sorted(set(spell_values), key=int)
    crafting_data_values = []
    for value in args.crafting_data_id:
        text = str(value).strip()
        if not text.isdigit() or int(text) <= 0:
            raise LimitedDb2Error("crafting-data-id must be a positive integer id")
        crafting_data_values.append(str(int(text)))
    if crafting_data_values:
        result["craftingDataIds"] = sorted(set(crafting_data_values), key=int)
    return result


def _select_scaling_config_only(targets: dict, args: argparse.Namespace) -> dict:
    only_modes = [
        args.only_item_scaling_config,
        args.only_item_bonus_list_group,
        args.only_item_bonus_tree,
        args.only_item_creation_context,
        args.only_modified_crafting_reagent_item,
        args.only_modified_crafting_category,
        args.only_display_season,
        args.only_journal_encounter,
        args.only_enchant,
        args.only_spell,
        args.only_crafting_data,
    ]
    if sum(bool(value) for value in only_modes) > 1:
        raise LimitedDb2Error(
            "only one bounded DB2 --only mode may be selected"
        )
    if args.only_modified_crafting_reagent_item:
        if args.modified_crafting_category_id:
            raise LimitedDb2Error(
                "--only-modified-crafting-reagent-item cannot be combined with category selectors"
            )
        if args.item_id or args.recipe_id or args.mythic_plus_season_id or args.display_season_id or args.map_id:
            raise LimitedDb2Error(
                "--only-modified-crafting-reagent-item cannot be combined with official root selectors"
            )
        return {
            "itemIds": [],
            "recipeIds": [],
            "mythicPlusSeasonIds": [],
            "displaySeasonIds": [],
        }
    if args.only_enchant:
        if (
            args.item_id
            or args.recipe_id
            or args.mythic_plus_season_id
            or args.display_season_id
            or args.map_id
            or args.item_scaling_config_id
            or args.item_bonus_list_group_id
            or args.item_bonus_tree_id
            or args.item_context
            or args.modified_crafting_reagent_item_id
            or args.modified_crafting_category_id
        ):
            raise LimitedDb2Error(
                "--only-enchant cannot be combined with other selectors"
            )
        if not args.enchant_id:
            raise LimitedDb2Error("--only-enchant requires enchant selectors")
        return {
            "itemIds": [],
            "recipeIds": [],
            "mythicPlusSeasonIds": [],
            "displaySeasonIds": [],
        }
    if args.only_spell:
        if (
            args.item_id
            or args.recipe_id
            or args.mythic_plus_season_id
            or args.display_season_id
            or args.map_id
            or args.item_scaling_config_id
            or args.item_bonus_list_group_id
            or args.item_bonus_tree_id
            or args.item_context
            or args.modified_crafting_reagent_item_id
            or args.modified_crafting_category_id
            or args.enchant_id
        ):
            raise LimitedDb2Error("--only-spell cannot be combined with other selectors")
        if not args.spell_id:
            raise LimitedDb2Error("--only-spell requires spell selectors")
        return {
            "itemIds": [],
            "recipeIds": [],
            "mythicPlusSeasonIds": [],
            "displaySeasonIds": [],
        }
    if args.only_crafting_data:
        if (
            args.item_id
            or args.recipe_id
            or args.mythic_plus_season_id
            or args.display_season_id
            or args.map_id
            or args.item_scaling_config_id
            or args.item_bonus_list_group_id
            or args.item_bonus_tree_id
            or args.item_context
            or args.modified_crafting_reagent_item_id
            or args.modified_crafting_category_id
            or args.enchant_id
            or args.spell_id
        ):
            raise LimitedDb2Error(
                "--only-crafting-data cannot be combined with other selectors"
            )
        if not args.crafting_data_id:
            raise LimitedDb2Error(
                "--only-crafting-data requires crafting-data selectors"
            )
        return {
            "itemIds": [],
            "recipeIds": [],
            "mythicPlusSeasonIds": [],
            "displaySeasonIds": [],
        }
    if args.only_modified_crafting_category:
        if args.item_id or args.recipe_id or args.mythic_plus_season_id or args.display_season_id or args.map_id:
            raise LimitedDb2Error(
                "--only-modified-crafting-category cannot be combined with official root selectors"
            )
        if not args.modified_crafting_category_id:
            raise LimitedDb2Error(
                "--only-modified-crafting-category requires category selectors"
            )
        return {
            "itemIds": [],
            "recipeIds": [],
            "mythicPlusSeasonIds": [],
            "displaySeasonIds": [],
        }
    if args.only_item_bonus_list_group:
        if args.item_id or args.recipe_id or args.mythic_plus_season_id or args.display_season_id or args.map_id:
            raise LimitedDb2Error(
                "--only-item-bonus-list-group cannot be combined with official root selectors"
            )
        return {
            "itemIds": [],
            "recipeIds": [],
            "mythicPlusSeasonIds": [],
            "displaySeasonIds": [],
        }
    if args.only_item_bonus_tree:
        if args.item_id or args.recipe_id or args.mythic_plus_season_id or args.display_season_id or args.map_id:
            raise LimitedDb2Error(
                "--only-item-bonus-tree cannot be combined with official root selectors"
            )
        if not args.item_bonus_tree_id:
            raise LimitedDb2Error(
                "--only-item-bonus-tree requires tree selectors"
            )
        return {
            "itemIds": [],
            "recipeIds": [],
            "mythicPlusSeasonIds": [],
            "displaySeasonIds": [],
        }
    if args.only_display_season:
        if (
            args.item_id
            or args.recipe_id
            or args.mythic_plus_season_id
            or args.map_id
            or args.item_scaling_config_id
            or args.item_bonus_list_group_id
            or args.item_bonus_tree_id
            or args.item_context
            or args.modified_crafting_reagent_item_id
            or args.modified_crafting_category_id
        ):
            raise LimitedDb2Error(
                "--only-display-season cannot be combined with other selectors"
            )
        if not args.display_season_id:
            raise LimitedDb2Error(
                "--only-display-season requires DisplaySeason selectors"
            )
        return {
            "itemIds": [],
            "recipeIds": [],
            "mythicPlusSeasonIds": [],
            "displaySeasonIds": list(args.display_season_id),
            "journalEncounterIds": [],
        }
    if args.only_journal_encounter:
        if (
            args.item_id
            or args.recipe_id
            or args.mythic_plus_season_id
            or args.display_season_id
            or args.map_id
            or args.item_scaling_config_id
            or args.item_bonus_list_group_id
            or args.item_bonus_tree_id
            or args.item_context
            or args.modified_crafting_reagent_item_id
            or args.modified_crafting_category_id
            or args.enchant_id
            or args.spell_id
            or args.crafting_data_id
        ):
            raise LimitedDb2Error(
                "--only-journal-encounter cannot be combined with other selectors"
            )
        return {
            "itemIds": [],
            "recipeIds": [],
            "mythicPlusSeasonIds": [],
            "displaySeasonIds": [],
            "journalEncounterIds": list(args.journal_encounter_id)
            or list(targets.get("journalEncounterIds") or []),
        }
    if args.only_item_creation_context:
        if (
            args.item_id
            or args.recipe_id
            or args.mythic_plus_season_id
            or args.display_season_id
            or args.map_id
            or args.item_scaling_config_id
            or args.item_bonus_list_group_id
            or args.item_bonus_tree_id
            or args.modified_crafting_reagent_item_id
            or args.modified_crafting_category_id
        ):
            raise LimitedDb2Error(
                "--only-item-creation-context cannot be combined with other selectors"
            )
        if not args.item_context:
            raise LimitedDb2Error(
                "--only-item-creation-context requires context selectors"
            )
        return {
            "itemIds": [],
            "recipeIds": [],
            "mythicPlusSeasonIds": [],
            "displaySeasonIds": [],
        }
    if not args.only_item_scaling_config:
        return targets
    if (
        args.item_id
        or args.recipe_id
        or args.mythic_plus_season_id
        or args.display_season_id
        or args.map_id
        or args.item_bonus_list_group_id
        or args.item_bonus_tree_id
        or args.modified_crafting_reagent_item_id
        or args.modified_crafting_category_id
    ):
        raise LimitedDb2Error(
            "--only-item-scaling-config cannot be combined with official root selectors"
        )
    return {
        "itemIds": [],
        "recipeIds": [],
        "mythicPlusSeasonIds": [],
        "displaySeasonIds": [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.live and args.dry_run_request_plan:
        parser.error("--live and --dry-run-request-plan are mutually exclusive")
    if args.live and not args.output_root:
        parser.error("--live requires --output-root")
    if not args.live and args.output_root:
        parser.error("--output-root is only valid with --live")

    try:
        allowlist = validate_db2_field_allowlist(_load_json(args.allowlist))
        targets = collect_s2_official_db2_targets(
            _load_json(args.official_capture_manifest)
        )
        targets = _select_scaling_config_only(targets, args)
        targets = _add_bounded_foreign_key_targets(targets, args)
        targets = _restrict_targets(targets, args)
        plan = build_bounded_db2_query_plan(
            targets=targets,
            allowlist=allowlist,
        )
        if not args.live:
            print(
                json.dumps(
                    {
                        "status": "dry_run",
                        "seasonKey": allowlist["seasonKey"],
                        "clientBuild": allowlist["clientBuild"],
                        "targets": targets,
                        "initialRequestCount": len(plan),
                        "networkCalls": 0,
                        "requests": [
                            {
                                "table": row["table"],
                                "filterField": row["filterField"],
                                "targetValue": row["targetValue"],
                                "targetKind": row["targetKind"],
                                "operator": row["operator"],
                            }
                            for row in plan
                        ],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 0

        result = capture_bounded_db2_evidence(
            plan=plan,
            output_root=Path(args.output_root),
            reader=WagoDb2FindReader(timeout_seconds=args.timeout_seconds),
            allowlist=allowlist,
            workers=args.workers,
        )
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "outputRoot": str(Path(args.output_root).expanduser().resolve()),
                    "requestCount": result["requestCount"],
                    "tables": result["tables"],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except (LimitedDb2Error, OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
