#!/usr/bin/env python3
"""Build the stable crafted PVE membership from isolated official evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.crafted_pve_membership import (  # noqa: E402
    build_crafted_pve_membership,
)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def crafted_source_from_snapshot(snapshot):
    for raw_source in snapshot.get("sources") or []:
        source = raw_source if isinstance(raw_source, dict) else {}
        if source.get("sourceType") == "crafted":
            return source
    raise ValueError("official source snapshot has no crafted source")


def filtered_official_search(page_root: Path, item_ids: set[str]):
    results = {}
    for path in sorted(page_root.glob("cursor-*.json")):
        payload = read_json(path)
        for raw_result in payload.get("results") or []:
            result = raw_result if isinstance(raw_result, dict) else {}
            data = (
                result.get("data")
                if isinstance(result.get("data"), dict)
                else result
            )
            item_id = str(data.get("id") or "").strip()
            if item_id not in item_ids:
                continue
            if item_id in results:
                raise ValueError(
                    f"duplicate official item {item_id} across range pages"
                )
            results[item_id] = result
    missing = sorted(item_ids - set(results), key=int)
    if missing:
        raise ValueError(
            f"official equippable range is missing {len(missing)} items: "
            f"{missing[:12]}"
        )
    return {
        "results": [results[item_id] for item_id in sorted(results, key=int)]
    }


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(body, encoding="utf-8")
    temporary.replace(path)


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-snapshot", type=Path, required=True)
    parser.add_argument("--official-item-page-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--season-revision", default="midnight-season-1")
    parser.add_argument("--as-of", default="2026-07-30")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    snapshot = read_json(args.source_snapshot)
    crafted_source = crafted_source_from_snapshot(snapshot)
    item_ids = {
        str(item_id)
        for member in crafted_source.get("rawMembers") or []
        for item_id in member.get("candidateItemIds") or []
        if str(item_id).strip()
    }
    official_search = filtered_official_search(
        args.official_item_page_root,
        item_ids,
    )
    payload = build_crafted_pve_membership(
        crafted_source,
        official_search,
        season_revision=args.season_revision,
        as_of=args.as_of,
    )
    write_json(args.output, payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": str(args.output),
                "summary": payload["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
