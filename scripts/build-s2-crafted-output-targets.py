#!/usr/bin/env python3
"""Derive crafted output item IDs from the bounded S2 DB2 evidence graph."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load_rows(
    capture_root: Path,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    root = Path(capture_root).expanduser().resolve()
    manifest = json.loads((root / "capture-manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "captured":
        raise ValueError("DB2 capture manifest must be captured")
    rows: dict[str, list[dict[str, Any]]] = {}
    for entry in manifest.get("entries") or []:
        response_path = Path(str(entry.get("responsePath") or ""))
        response = (root / response_path).resolve()
        if response_path.is_absolute() or root not in response.parents:
            raise ValueError("DB2 response path escapes capture root")
        payload = json.loads(response.read_text(encoding="utf-8"))
        table = str(payload.get("table") or "")
        for row in payload.get("rows") or []:
            if isinstance(row, dict):
                rows.setdefault(table, []).append(row)
    for table, table_rows in list(rows.items()):
        unique: dict[str, dict[str, Any]] = {}
        for row in table_rows:
            unique[_canonical(row)] = row
        rows[table] = list(unique.values())
    return rows, manifest


def _recipe_without_output_record(
    *,
    recipe_id: str,
    spell_id: str,
    effect_rows: list[dict[str, Any]],
    crafting_data: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    effect_codes = sorted(
        {
            str(row.get("Effect"))
            for row in effect_rows
            if row.get("Effect") not in (None, "")
        },
        key=lambda value: int(value) if value.isdigit() else value,
    )
    crafting_data_ids = sorted(
        {
            str(int(row.get("EffectMiscValue_0")))
            for row in effect_rows
            if row.get("Effect") == 288
            and row.get("EffectMiscValue_0") not in (None, "", 0, "0")
        },
        key=int,
    )
    create_item_target_values = [
        str(row.get("EffectMiscValue_0") or "0")
        for row in effect_rows
        if row.get("Effect") == 288
    ]
    output_ids = sorted(
        {
            str(int(crafting_data[data_id].get("CraftedItemID")))
            for data_id in crafting_data_ids
            if data_id in crafting_data
            and crafting_data[data_id].get("CraftedItemID") not in (None, "", 0, "0")
        },
        key=int,
    )
    if output_ids:
        raise ValueError("recipe without output record received an output item")

    known_non_item_effects = {"3", "53", "296", "297", "301"}
    if effect_codes and set(effect_codes).issubset(known_non_item_effects):
        classification_status = "verified"
        reason_code = "OUT_OF_SCOPE_NON_EQUIPMENT_RECIPE"
    elif effect_codes == ["288"] and crafting_data_ids and all(
        data_id in crafting_data
        and crafting_data[data_id].get("CraftedItemID") in (None, "", 0, "0")
        for data_id in crafting_data_ids
    ):
        classification_status = "verified"
        reason_code = "OFFICIAL_DB2_CRAFTING_DATA_HAS_NO_ITEM_OUTPUT"
    elif effect_codes == ["288"] and create_item_target_values and all(
        value == "0" for value in create_item_target_values
    ):
        classification_status = "verified"
        reason_code = "OFFICIAL_DB2_CREATE_ITEM_EFFECT_HAS_NO_OUTPUT_TARGET"
    else:
        classification_status = "UNVERIFIED"
        reason_code = "OFFICIAL_DB2_RECIPE_OUTPUT_EDGE_UNRESOLVED"

    return {
        "recipeId": recipe_id,
        "spellId": spell_id,
        "effectCodes": effect_codes,
        "craftingDataIds": crafting_data_ids,
        "craftingDataOutputItemIds": output_ids,
        "createItemEffectTargetValues": create_item_target_values,
        "classificationStatus": classification_status,
        "reasonCode": reason_code,
        "evidenceTables": ["SkillLineAbility", "SpellEffect", "CraftingData"],
    }


def derive_crafted_output_targets(capture_root: Path) -> dict[str, Any]:
    rows, manifest = _load_rows(capture_root)
    spells = {
        str(row["ID"]): str(row["Spell"])
        for row in rows.get("SkillLineAbility", [])
        if row.get("ID") not in (None, "") and row.get("Spell") not in (None, "", 0, "0")
    }
    crafting_data = {
        str(row["ID"]): row
        for row in rows.get("CraftingData", [])
        if row.get("ID") not in (None, "")
    }
    effect_data: dict[str, set[str]] = {}
    spell_effect_rows: dict[str, list[dict[str, Any]]] = {}
    for row in rows.get("SpellEffect", []):
        spell_id = str(row.get("SpellID"))
        spell_effect_rows.setdefault(spell_id, []).append(row)
        if row.get("Effect") != 288:
            continue
        value = row.get("EffectMiscValue_0")
        if value in (None, "", 0, "0"):
            continue
        effect_data.setdefault(str(row.get("SpellID")), set()).add(str(int(value)))

    recipe_output_edges = []
    recipes_without_output = []
    recipe_without_output_records = []
    for recipe_id, spell_id in sorted(spells.items(), key=lambda pair: int(pair[0])):
        crafting_ids = sorted(effect_data.get(spell_id, set()), key=int)
        output_ids = sorted(
            {
                str(int(crafting_data[crafting_id].get("CraftedItemID")))
                for crafting_id in crafting_ids
                if crafting_id in crafting_data
                and crafting_data[crafting_id].get("CraftedItemID")
                not in (None, "", 0, "0")
            },
            key=int,
        )
        if not output_ids:
            recipes_without_output.append(recipe_id)
            recipe_without_output_records.append(
                _recipe_without_output_record(
                    recipe_id=recipe_id,
                    spell_id=spell_id,
                    effect_rows=spell_effect_rows.get(spell_id, []),
                    crafting_data=crafting_data,
                )
            )
        for item_id in output_ids:
            recipe_output_edges.append(
                {
                    "recipeId": recipe_id,
                    "spellId": spell_id,
                    "craftingDataIds": crafting_ids,
                    "itemId": item_id,
                    "status": "verified",
                    "evidenceTables": ["SkillLineAbility", "SpellEffect", "CraftingData"],
                }
            )
    item_ids = sorted({row["itemId"] for row in recipe_output_edges}, key=int)
    unresolved_records = [
        row
        for row in recipe_without_output_records
        if row["classificationStatus"] != "verified"
    ]
    return {
        "schemaRevision": "s2-crafted-output-targets-v1",
        "status": "verified" if item_ids and not unresolved_records else "partial" if item_ids else "blocked",
        "sourceCaptureRoot": str(Path(capture_root).expanduser().resolve()),
        "sourceDb2Build": str(
            manifest.get("clientBuild")
            or manifest.get("sourceDb2Build")
            or ""
        ),
        "recipeRootCount": len(spells),
        "recipeOutputEdgeCount": len(recipe_output_edges),
        "recipeWithoutOutputCount": len(recipes_without_output),
        "recipesWithoutOutput": recipes_without_output,
        "recipeWithoutOutputRecords": recipe_without_output_records,
        "classifiedRecipeWithoutOutputCount": len(recipe_without_output_records) - len(unresolved_records),
        "unresolvedRecipeWithoutOutputCount": len(unresolved_records),
        "craftedOutputItemCount": len(item_ids),
        "craftedOutputItemIds": item_ids,
        "recipeOutputEdges": recipe_output_edges,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = derive_crafted_output_targets(args.capture_root)
    output = (args.output if args.output.is_absolute() else ROOT / args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError("crafted output target report already exists")
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": output.relative_to(ROOT).as_posix(),
                "status": report["status"],
                "craftedOutputItemCount": report["craftedOutputItemCount"],
                "recipeOutputEdgeCount": report["recipeOutputEdgeCount"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "verified" else 3


if __name__ == "__main__":
    raise SystemExit(main())
