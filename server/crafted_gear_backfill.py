#!/usr/bin/env python3
import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

try:
    from . import websim_payload
except ImportError:
    import websim_payload


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("WOW_NEWS_DB", BASE_DIR / "data" / "wow_news.sqlite3"))
DEFAULT_SQLITE_BUSY_TIMEOUT_MS = int(os.environ.get("WOW_CRAFTED_GEAR_BACKFILL_SQLITE_BUSY_TIMEOUT_MS", "30000"))
DEFAULT_SIMC_BIN = os.environ.get("WOW_SIMC_BIN", "/opt/wow-simc/current/simc")

CRAFTED_STAT_ID_LABELS = {
    "32": ("crit", "暴击"),
    "36": ("haste", "急速"),
    "40": ("versatility", "全能"),
    "49": ("mastery", "精通"),
}
STANDARD_CRAFTED_STATS_VALUES = ("32/36", "32/40", "32/49", "36/40", "36/49", "40/49")
DEFAULT_CRAFTED_METADATA_SLOTS = (
    "head",
    "neck",
    "shoulder",
    "back",
    "chest",
    "wrist",
    "hands",
    "waist",
    "legs",
    "feet",
    "finger1",
    "finger2",
    "main_hand",
    "off_hand",
)
CRAFTING_STAT_METADATA_KEYS = {
    "modified_crafting_stat",
    "modifiedCraftingStat",
    "modified_crafting_stats",
    "modifiedCraftingStats",
}
CURATED_CRAFTED_METADATA_ITEMS = {
    "251105": {
        "slot": "off_hand",
        "sourceType": "local_curated_crafted_catalog",
        "sourceLabel": "Local curated crafted catalog: shield",
        "profession": "metadata_catalog",
        "supportsVoidUpgrade": True,
        "evidence": "curated_crafted_shield",
    },
}


def connect_backfill_db(db_path=DB_PATH):
    timeout_ms = max(1000, int(DEFAULT_SQLITE_BUSY_TIMEOUT_MS or 30000))
    conn = sqlite3.connect(db_path, timeout=max(1, timeout_ms // 1000))
    conn.execute(f"PRAGMA busy_timeout = {timeout_ms}")
    return conn


def ensure_simc_env():
    if os.environ.get("WOW_SIMC_BIN"):
        return
    if DEFAULT_SIMC_BIN and Path(DEFAULT_SIMC_BIN).exists():
        os.environ["WOW_SIMC_BIN"] = str(DEFAULT_SIMC_BIN)


def canonical_crafted_stats_value(value):
    text = websim_payload.normalize_option_value(value)
    if not text:
        return ""
    parts = [part for part in text.split("/") if part]
    if len(parts) != 2:
        return ""
    if any(part not in CRAFTED_STAT_ID_LABELS for part in parts):
        return ""
    return "/".join(sorted(parts, key=lambda part: int(part)))


def crafted_stats_option(value, *, observed=False):
    canonical = canonical_crafted_stats_value(value)
    if not canonical:
        return None
    parts = canonical.split("/")
    keys = [CRAFTED_STAT_ID_LABELS[part][0] for part in parts]
    labels = [CRAFTED_STAT_ID_LABELS[part][1] for part in parts]
    return {
        "key": "-".join(keys),
        "label": " + ".join(labels),
        "value": canonical,
        "status": "verified",
        "payload": {
            "statIds": parts,
            "source": "simulationcraft_profile_preset",
            "observedInProfilePreset": bool(observed),
        },
    }


def profile_source_ref(preset_id, class_key, spec_key, name):
    preset_id = str(preset_id or "").strip()
    return {
        "id": preset_id,
        "sourceType": "simulationcraft_profile_preset",
        "sourceLabel": f"SimulationCraft preset: {str(name or preset_id or 'crafted preview').strip()}",
        "classKey": str(class_key or "").strip(),
        "specKey": str(spec_key or "").strip(),
    }


def _merge_source_ref(refs, ref):
    ref_id = str((ref or {}).get("id") or "").strip()
    if ref_id and any(str(existing.get("id") or "").strip() == ref_id for existing in refs):
        return
    refs.append(ref)


def _first_sorted(values):
    normalized = sorted({str(value or "").strip() for value in values if str(value or "").strip()})
    return normalized[0] if normalized else ""


def _track_for_item(item, difficulty_key, item_level, label, observed_levels):
    track = {
        "difficultyKey": difficulty_key,
        "itemLevel": item_level,
        "label": label,
        "trackEvidence": [
            {
                "source": "simulationcraft_profile_preset",
                "observedItemLevels": sorted(int(level) for level in observed_levels if int(level or 0) > 0),
            }
        ],
    }
    bonus_id = _first_sorted(item.get("bonusIdsByLevel", {}).get(str(item_level), [])) or _first_sorted(item.get("bonusIds", []))
    if bonus_id:
        track["bonus_id"] = bonus_id
    return track


def _metadata_contains_crafting_stat(value, depth=0):
    if depth > 8:
        return False
    if isinstance(value, dict):
        for key, child in value.items():
            if key in CRAFTING_STAT_METADATA_KEYS and child not in (None, "", [], {}):
                return True
            if _metadata_contains_crafting_stat(child, depth + 1):
                return True
    if isinstance(value, list):
        return any(_metadata_contains_crafting_stat(child, depth + 1) for child in value)
    return False


def metadata_payload_has_modified_crafting_stat(payload):
    return _metadata_contains_crafting_stat(payload if isinstance(payload, dict) else {})


def metadata_source_ref(item_id, metadata, *, evidence="modified_crafting_stat"):
    metadata = metadata if isinstance(metadata, dict) else {}
    source_label = "Battle.net item metadata"
    if evidence:
        source_label = f"{source_label}: {evidence}"
    return {
        "id": f"battle-net-item-{item_id}-{websim_payload.slugify(evidence, 'metadata')}",
        "sourceType": "battle_net_item_metadata",
        "sourceLabel": source_label,
        "itemId": str(item_id or "").strip(),
        "metadataStatus": str(metadata.get("metadataStatus") or "").strip(),
        "metadataSource": str(metadata.get("metadataSource") or "").strip(),
        "metadataLocale": str(metadata.get("metadataLocale") or "").strip(),
    }


def curated_source_ref(item_id, curated):
    curated = curated if isinstance(curated, dict) else {}
    return {
        "id": f"curated-crafted-{item_id}",
        "sourceType": str(curated.get("sourceType") or "local_curated_crafted_catalog"),
        "sourceLabel": str(curated.get("sourceLabel") or "Local curated crafted catalog"),
        "itemId": str(item_id or "").strip(),
        "evidence": str(curated.get("evidence") or "curated_crafted_item"),
    }


def metadata_track_evidence(slot, supports_void_upgrade, *, source="battle_net_item_metadata", evidence="modified_crafting_stat"):
    evidence = {
        "source": source,
        "evidence": evidence,
        "slot": slot,
        "itemLevelRules": {"crafted_myth": 285},
    }
    if supports_void_upgrade:
        evidence["itemLevelRules"]["crafted_void_upgrade"] = 295
        evidence["voidUpgradeRule"] = "weapon_or_shield_or_profile_evidence"
    else:
        evidence["voidUpgradeRule"] = "not_weapon_or_shield"
    return evidence


def crafted_metadata_supports_void_upgrade(metadata, profile_item=None):
    profile_item = profile_item if isinstance(profile_item, dict) else {}
    if profile_item.get("supportsVoidUpgrade"):
        return True
    metadata = metadata if isinstance(metadata, dict) else {}
    curated = CURATED_CRAFTED_METADATA_ITEMS.get(str(metadata.get("itemId") or "").strip())
    if curated and "supportsVoidUpgrade" in curated:
        return bool(curated.get("supportsVoidUpgrade"))
    payload = metadata.get("payload") if isinstance(metadata.get("payload"), dict) else {}
    slot = websim_payload.normalize_slot(metadata.get("slot")) or websim_payload.item_slot_from_payload(payload)
    if slot not in {"main_hand", "off_hand"}:
        return False
    item_class = payload.get("item_class") if isinstance(payload.get("item_class"), dict) else {}
    if websim_payload.payload_item_class_is_weapon(item_class):
        return True
    type_metadata = websim_payload.item_type_metadata_from_payload(payload)
    return str(type_metadata.get("weaponType") or "").strip().lower() == "shield"


def metadata_crafted_track(difficulty_key, item_level, label, evidence, profile_track=None):
    track = {
        "difficultyKey": difficulty_key,
        "itemLevel": item_level,
        "label": label,
        "trackEvidence": [evidence],
    }
    if isinstance(profile_track, dict):
        for key in ("bonus_id", "bonusId"):
            value = websim_payload.normalize_option_value(profile_track.get(key))
            if value:
                track["bonus_id"] = value
                break
        profile_evidence = profile_track.get("trackEvidence")
        if isinstance(profile_evidence, list):
            track["trackEvidence"].extend(profile_evidence)
    return track


def metadata_tracks_for_item(supports_void_upgrade, evidence, profile_item=None):
    profile_item = profile_item if isinstance(profile_item, dict) else {}
    profile_tracks = {
        str(track.get("difficultyKey") or ""): track
        for track in (profile_item.get("allowedTracks") or [])
        if isinstance(track, dict)
    }
    tracks = [
        metadata_crafted_track(
            "crafted_myth",
            285,
            "神话 285",
            evidence,
            profile_tracks.get("crafted_myth"),
        )
    ]
    if supports_void_upgrade:
        tracks.append(
            metadata_crafted_track(
                "crafted_void_upgrade",
                295,
                "虚空晋升 295",
                evidence,
                profile_tracks.get("crafted_void_upgrade"),
            )
        )
    return tracks


def _catalog_item_from_aggregate(conn, item_id, aggregate, *, stat_scope="all"):
    metadata = websim_payload.existing_websim_item_metadata(conn, item_id) or {}
    metadata_payload = metadata.get("payload") if isinstance(metadata.get("payload"), dict) else {}
    slot = (
        websim_payload.normalize_slot(aggregate.get("slot"))
        or websim_payload.normalize_slot(metadata.get("slot"))
        or websim_payload.item_slot_from_payload(metadata_payload)
    )
    if not slot:
        return None
    observed_levels = sorted(level for level in aggregate.get("itemLevels", set()) if int(level or 0) > 0)
    tracks = [_track_for_item(aggregate, "crafted_myth", 285, "神话 285", observed_levels)]
    supports_void_upgrade = slot in {"main_hand", "off_hand"} and 295 in observed_levels
    if supports_void_upgrade:
        tracks.append(_track_for_item(aggregate, "crafted_void_upgrade", 295, "虚空晋升 295", observed_levels))
    observed_stats = set(aggregate.get("craftedStats", set()))
    if stat_scope == "observed":
        stat_values = sorted(observed_stats)
    else:
        stat_values = list(STANDARD_CRAFTED_STATS_VALUES)
    stat_options = [crafted_stats_option(value, observed=value in observed_stats) for value in stat_values]
    stat_options = [option for option in stat_options if option]
    if not stat_options:
        return None
    source_refs = aggregate.get("sourceRefs") or []
    return {
        "itemId": item_id,
        "name": str(
            metadata.get("displayName")
            or metadata.get("name")
            or aggregate.get("name")
            or f"item_{item_id}"
        ),
        "slot": slot,
        "sourceId": f"crafted-preview-{item_id}",
        "sourceLabel": "制造装备",
        "profession": "profile_preview",
        "recipeId": "",
        "status": "verified",
        "supportsVoidUpgrade": supports_void_upgrade,
        "allowedTracks": tracks,
        "allowedCraftedStats": stat_options,
        "sourceRefs": source_refs,
        "trackEvidence": [
            {
                "source": "simulationcraft_profile_preset",
                "profileCount": len(source_refs),
                "observedItemLevels": observed_levels,
                "observedCraftedStats": sorted(observed_stats),
                "craftedStats": [option["value"] for option in stat_options],
            }
        ],
    }


def crafted_catalog_items_from_simc_presets(conn, *, item_ids=None, limit=None, stat_scope="all"):
    websim_payload.ensure_websim_tables(conn)
    stat_scope = "observed" if stat_scope == "observed" else "all"
    target_ids = {
        websim_payload.normalize_option_value(item_id)
        for item_id in (item_ids or [])
        if websim_payload.normalize_option_value(item_id)
    }
    rows = conn.execute(
        """
        SELECT id, class_key, spec_key, name, profile
        FROM websim_profile_presets
        WHERE profile LIKE '%crafted_stats%'
        ORDER BY class_key, spec_key, id
        """
    ).fetchall()
    aggregates = {}
    for preset_id, class_key, spec_key, name, profile in rows:
        ref = profile_source_ref(preset_id, class_key, spec_key, name)
        for line in str(profile or "").splitlines():
            if "crafted_stats" not in line:
                continue
            item = websim_payload.parse_simc_gear_line(line, class_key, spec_key, name, preset_id)
            if not item:
                continue
            item_id = websim_payload.normalize_option_value(item.get("itemId") or item.get("id"))
            if not item_id or (target_ids and item_id not in target_ids):
                continue
            option = crafted_stats_option(item.get("crafted_stats"), observed=True)
            if not option:
                continue
            aggregate = aggregates.setdefault(
                item_id,
                {
                    "itemId": item_id,
                    "name": item.get("name") or "",
                    "slot": item.get("slot") or "",
                    "craftedStats": set(),
                    "itemLevels": set(),
                    "bonusIds": set(),
                    "bonusIdsByLevel": {},
                    "sourceRefs": [],
                },
            )
            aggregate["craftedStats"].add(option["value"])
            item_level = int(item.get("ilevel") or item.get("itemLevel") or 0)
            if item_level:
                aggregate["itemLevels"].add(item_level)
            bonus_id = websim_payload.normalize_option_value(item.get("bonus_id") or item.get("bonusId"))
            if bonus_id:
                aggregate["bonusIds"].add(bonus_id)
                if item_level:
                    aggregate["bonusIdsByLevel"].setdefault(str(item_level), set()).add(bonus_id)
            if not aggregate.get("name") and item.get("name"):
                aggregate["name"] = item.get("name")
            if not aggregate.get("slot") and item.get("slot"):
                aggregate["slot"] = item.get("slot")
            _merge_source_ref(aggregate["sourceRefs"], ref)

    items = []
    for item_id in sorted(aggregates, key=lambda value: int(value) if str(value).isdigit() else str(value)):
        item = _catalog_item_from_aggregate(conn, item_id, aggregates[item_id], stat_scope=stat_scope)
        if item:
            items.append(item)
        if limit and len(items) >= int(limit):
            break
    return items


def crafted_catalog_items_from_metadata(conn, *, item_ids=None, slots=None, limit=None, stat_scope="all", include_profile_evidence=True):
    websim_payload.ensure_websim_tables(conn)
    stat_scope = "observed" if stat_scope == "observed" else "all"
    target_ids = {
        websim_payload.normalize_option_value(item_id)
        for item_id in (item_ids or [])
        if websim_payload.normalize_option_value(item_id)
    }
    target_slots = {
        websim_payload.normalize_slot(slot)
        for slot in (slots or DEFAULT_CRAFTED_METADATA_SLOTS)
        if websim_payload.normalize_slot(slot)
    }
    profile_items_by_id = {}
    if include_profile_evidence:
        for item in crafted_catalog_items_from_simc_presets(conn, item_ids=item_ids, stat_scope=stat_scope):
            profile_items_by_id[item["itemId"]] = item
    rows = conn.execute(
        """
        SELECT id, name, slot, payload_json
        FROM websim_items
        WHERE payload_json LIKE '%modified_crafting_stat%'
           OR payload_json LIKE '%modifiedCraftingStat%'
           OR payload_json LIKE '%modified_crafting_stats%'
           OR payload_json LIKE '%modifiedCraftingStats%'
        ORDER BY CAST(id AS INTEGER), id
        """
    ).fetchall()
    curated_ids = sorted(
        item_id
        for item_id in CURATED_CRAFTED_METADATA_ITEMS
        if not target_ids or item_id in target_ids
    )
    if curated_ids:
        placeholders = ",".join("?" for _ in curated_ids)
        rows = [
            *rows,
            *conn.execute(
                f"""
                SELECT id, name, slot, payload_json
                FROM websim_items
                WHERE id IN ({placeholders})
                ORDER BY CAST(id AS INTEGER), id
                """,
                curated_ids,
            ).fetchall(),
        ]
    items = []
    seen_item_ids = set()
    for row in rows:
        item_id = websim_payload.normalize_option_value(row[0])
        if not item_id or (target_ids and item_id not in target_ids):
            continue
        if item_id in seen_item_ids:
            continue
        seen_item_ids.add(item_id)
        curated = CURATED_CRAFTED_METADATA_ITEMS.get(item_id) or {}
        metadata = websim_payload.existing_websim_item_metadata(conn, item_id) or {}
        metadata_payload = metadata.get("payload") if isinstance(metadata.get("payload"), dict) else {}
        has_modified_crafting_stat = metadata_payload_has_modified_crafting_stat(metadata_payload)
        if not has_modified_crafting_stat and not curated:
            continue
        slot = (
            websim_payload.normalize_slot(curated.get("slot"))
            or websim_payload.normalize_slot(row[2])
            or websim_payload.normalize_slot(metadata.get("slot"))
            or websim_payload.item_slot_from_payload(metadata_payload)
        )
        if not slot or (target_slots and slot not in target_slots):
            continue
        profile_item = profile_items_by_id.get(item_id) or {}
        supports_void_upgrade = crafted_metadata_supports_void_upgrade(metadata, profile_item)
        evidence_source = str(curated.get("sourceType") or "battle_net_item_metadata")
        evidence_key = str(curated.get("evidence") or "modified_crafting_stat")
        evidence = metadata_track_evidence(
            slot,
            supports_void_upgrade,
            source=evidence_source,
            evidence=evidence_key,
        )
        source_refs = []
        if curated:
            source_refs.append(curated_source_ref(item_id, curated))
        source_refs.append(
            metadata_source_ref(
                item_id,
                metadata,
                evidence="modified_crafting_stat" if has_modified_crafting_stat else "",
            )
        )
        for ref in profile_item.get("sourceRefs") or []:
            if isinstance(ref, dict):
                _merge_source_ref(source_refs, ref)
        if stat_scope == "observed" and profile_item.get("allowedCraftedStats"):
            stat_options = profile_item["allowedCraftedStats"]
        else:
            stat_options = [crafted_stats_option(value, observed=False) for value in STANDARD_CRAFTED_STATS_VALUES]
            stat_options = [option for option in stat_options if option]
        type_metadata = websim_payload.item_type_metadata_from_payload(metadata_payload)
        items.append(
            {
                "itemId": item_id,
                "name": str(metadata.get("displayName") or metadata.get("name") or row[1] or f"item_{item_id}"),
                "slot": slot,
                "sourceId": f"crafted-preview-{item_id}",
                "sourceLabel": "制造装备",
                "profession": str(profile_item.get("profession") or curated.get("profession") or "metadata_catalog"),
                "recipeId": str(profile_item.get("recipeId") or curated.get("recipeId") or ""),
                "status": "verified",
                "supportsVoidUpgrade": supports_void_upgrade,
                "allowedTracks": metadata_tracks_for_item(supports_void_upgrade, evidence, profile_item),
                "allowedCraftedStats": stat_options,
                "sourceRefs": source_refs,
                "trackEvidence": [evidence, *(profile_item.get("trackEvidence") or [])],
                "armorType": type_metadata.get("armorType") or "",
                "weaponType": type_metadata.get("weaponType") or "",
            }
        )
        if limit and len(items) >= int(limit):
            break
    return items


def load_seed_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        payload = payload.get("items") or payload.get("craftedItems") or []
    return [item for item in (payload or []) if isinstance(item, dict)]


def summarize_items(items):
    slot_counts = {}
    track_counts = {}
    stat_option_values = set()
    for item in items or []:
        slot_counts[item.get("slot") or ""] = slot_counts.get(item.get("slot") or "", 0) + 1
        for track in item.get("allowedTracks") or []:
            key = str(track.get("difficultyKey") or "")
            track_counts[key] = track_counts.get(key, 0) + 1
        for option in item.get("allowedCraftedStats") or []:
            if option.get("value"):
                stat_option_values.add(option["value"])
    return {
        "items": len(items or []),
        "slots": dict(sorted(slot_counts.items())),
        "tracks": dict(sorted(track_counts.items())),
        "craftedStatOptions": sorted(stat_option_values),
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Backfill governed crafted gear catalog variants.")
    parser.add_argument("--db", default=str(DB_PATH), help="Path to wow_news.sqlite3")
    parser.add_argument("--from-metadata", action="store_true", help="Build crafted catalog items from existing websim_items metadata with modified_crafting_stat.")
    parser.add_argument("--from-simc-presets", action="store_true", help="Build crafted preview catalog items from existing SimC profile presets.")
    parser.add_argument("--seed-json", help="Path to a controlled crafted catalog seed JSON file.")
    parser.add_argument("--item-id", action="append", default=[], help="Only include the given item id. Can be repeated.")
    parser.add_argument("--slot", action="append", default=[], help="Only include the given canonical slot. Can be repeated.")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of crafted items to process.")
    parser.add_argument("--stat-scope", choices=["all", "observed"], default="all", help="Use all six standard crafted stat pairs or only pairs observed in profile presets.")
    parser.add_argument("--dry-run", action="store_true", help="Print the import summary without writing DB rows or running SimC probes.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if not args.from_metadata and not args.from_simc_presets and not args.seed_json:
        print("error: pass --from-metadata, --from-simc-presets, or --seed-json", file=sys.stderr)
        return 2
    conn = connect_backfill_db(args.db)
    try:
        if args.seed_json:
            items = load_seed_json(args.seed_json)
            if args.item_id:
                allowed = {websim_payload.normalize_option_value(item_id) for item_id in args.item_id}
                items = [
                    item
                    for item in items
                    if websim_payload.normalize_option_value(item.get("itemId") or item.get("item_id") or item.get("id")) in allowed
                ]
            if args.limit:
                items = items[: max(0, int(args.limit))]
        elif args.from_metadata:
            items = crafted_catalog_items_from_metadata(
                conn,
                item_ids=args.item_id,
                slots=args.slot or None,
                limit=max(0, int(args.limit or 0)) or None,
                stat_scope=args.stat_scope,
            )
        else:
            items = crafted_catalog_items_from_simc_presets(
                conn,
                item_ids=args.item_id,
                limit=max(0, int(args.limit or 0)) or None,
                stat_scope=args.stat_scope,
            )
        summary = summarize_items(items)
        if args.dry_run:
            print(json.dumps({"dryRun": True, **summary, "itemsPreview": items[:20]}, ensure_ascii=False, indent=2))
            return 0
        ensure_simc_env()
        counts = websim_payload.backfill_crafted_item_level_variants(conn, items)
        print(json.dumps({"dryRun": False, **summary, "backfill": counts}, ensure_ascii=False, indent=2))
        return 0 if not counts.get("errors") else 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
