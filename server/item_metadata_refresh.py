#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path

try:
    from .db import database_config_from_env
    from .postgres_cache_sync import (
        cache_store_from_env,
        refresh_websim_item_metadata_gaps_postgres,
        refresh_websim_item_metadata_item_gaps_postgres,
        refresh_websim_item_metadata_postgres,
    )
    from .websim_payload import DEFAULT_LOCALE, DEFAULT_REGION
except ImportError:
    from db import database_config_from_env
    from postgres_cache_sync import (
        cache_store_from_env,
        refresh_websim_item_metadata_gaps_postgres,
        refresh_websim_item_metadata_item_gaps_postgres,
        refresh_websim_item_metadata_postgres,
    )
    from websim_payload import DEFAULT_LOCALE, DEFAULT_REGION


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Refresh Battle.net item metadata into the PostgreSQL WebSim item cache."
    )
    parser.add_argument("--item-id", action="append", default=[], help="Refresh a specific item id. Can be repeated.")
    parser.add_argument("--from-community-template-gaps", action="store_true", help="Refresh item metadata gaps found in active community gear templates.")
    parser.add_argument("--from-websim-item-gaps", action="store_true", help="Refresh used WebSim item rows missing official shape, display name, or icon metadata.")
    parser.add_argument("--limit", type=int, default=200, help="Maximum template metadata gaps to scan or refresh.")
    parser.add_argument("--region", default="", help="Battle.net region.")
    parser.add_argument("--locale", default="", help="Battle.net locale.")
    parser.add_argument("--env-file", default="", help="Load KEY=VALUE settings from an env file before connecting.")
    parser.add_argument("--dry-run", action="store_true", help="Only print the target refs without fetching or writing metadata.")
    return parser.parse_args(argv)


def _postgres_required():
    config = database_config_from_env()
    if config.backend != "postgres" or not config.database_url:
        raise RuntimeError("item metadata refresh requires PostgreSQL runtime and WOW_DATABASE_URL")
    return config


def load_env_file(path):
    if not path:
        return {}
    loaded = {}
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        os.environ[key] = value
        loaded[key] = value
    return loaded


def _manual_refs(item_ids):
    return [{"itemId": str(item_id).strip()} for item_id in item_ids or [] if str(item_id or "").strip()]


def main(argv=None):
    args = parse_args(argv)
    load_env_file(args.env_file)
    args.region = args.region or os.environ.get("WOW_REGION", DEFAULT_REGION)
    args.locale = args.locale or os.environ.get("WOW_LOCALE", DEFAULT_LOCALE)
    _postgres_required()
    store = cache_store_from_env()
    gap_sources = [args.from_community_template_gaps, args.from_websim_item_gaps]
    if sum(1 for enabled in gap_sources if enabled) > 1:
        print("error: choose only one gap source", file=sys.stderr)
        return 2
    if args.from_community_template_gaps:
        if args.dry_run:
            gaps = store.community_gear_template_item_metadata_gaps(limit=args.limit)
            print(json.dumps({"dryRun": True, "runner": "postgres", "gapCount": len(gaps), "gaps": gaps}, ensure_ascii=False, indent=2))
            return 0
        payload = refresh_websim_item_metadata_gaps_postgres(
            limit=args.limit,
            region=args.region,
            locale=args.locale,
            store=store,
        )
    elif args.from_websim_item_gaps:
        if args.dry_run:
            gaps = store.websim_item_metadata_gaps(limit=args.limit)
            print(json.dumps({"dryRun": True, "runner": "postgres", "gapCount": len(gaps), "gaps": gaps}, ensure_ascii=False, indent=2))
            return 0
        payload = refresh_websim_item_metadata_item_gaps_postgres(
            limit=args.limit,
            region=args.region,
            locale=args.locale,
            store=store,
        )
    else:
        refs = _manual_refs(args.item_id)
        if not refs:
            print("error: pass --item-id, --from-community-template-gaps, or --from-websim-item-gaps", file=sys.stderr)
            return 2
        if args.dry_run:
            print(json.dumps({"dryRun": True, "runner": "postgres", "refs": refs}, ensure_ascii=False, indent=2))
            return 0
        payload = refresh_websim_item_metadata_postgres(
            refs,
            region=args.region,
            locale=args.locale,
            store=store,
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not payload.get("errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())
