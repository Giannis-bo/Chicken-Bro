#!/usr/bin/env python3
"""Capture official S2 modified-crafting slot compatibility responses."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.s2_official_modified_crafting import (  # noqa: E402
    OfficialModifiedCraftingError,
    build_slot_type_request_plan,
    capture_modified_crafting_slot_types,
    extract_slot_type_ids,
)
from server.websim_payload import (  # noqa: E402
    blizzard_credentials_configured,
    blizzard_get,
    get_blizzard_access_token,
)


def _load_env(path: Path | None, *, stdin: bool = False) -> None:
    if stdin:
        lines = sys.stdin.read().splitlines()
    elif path is None:
        return
    else:
        lines = path.expanduser().resolve().read_text(encoding="utf-8").splitlines()
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


class _BlizzardReader:
    def __init__(self, *, region: str, locale: str):
        self.region = region
        self.locale = locale
        self.token = get_blizzard_access_token(region)

    def get(self, path, *, namespace, region, locale, query):
        if (region, locale) != (self.region, self.locale):
            raise OfficialModifiedCraftingError("reader region/locale drifted")
        last_error = None
        for attempt in range(3):
            try:
                payload = blizzard_get(
                    path,
                    self.token,
                    region=region,
                    locale=locale,
                    params=query,
                    namespace=namespace,
                )
                if not isinstance(payload, dict) or str(payload.get("id")) != path.rsplit("/", 1)[-1]:
                    raise OfficialModifiedCraftingError(
                        f"official slot-type identity mismatch: {path}"
                    )
                return payload
            except Exception as error:  # pragma: no cover - live network path
                last_error = error
                if attempt < 2:
                    time.sleep(2**attempt)
        raise OfficialModifiedCraftingError(
            f"official slot-type request failed: {path}: {last_error}"
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-capture", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument(
        "--env-stdin",
        action="store_true",
        help="read the existing KEY=VALUE environment from stdin without persisting credentials locally",
    )
    parser.add_argument("--region", default="us")
    parser.add_argument("--locale", default="en_US")
    parser.add_argument("--namespace", default="static-12.1.0_68914-us")
    parser.add_argument("--captured-at")
    parser.add_argument("--live", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.env_file and args.env_stdin:
        raise SystemExit("--env-file and --env-stdin are mutually exclusive")
    try:
        slot_type_ids = extract_slot_type_ids(args.source_capture)
        plan = build_slot_type_request_plan(
            slot_type_ids,
            region=args.region,
            locale=args.locale,
            namespace=args.namespace,
        )
        if not args.live:
            print(
                json.dumps(
                    {
                        "status": "dry_run",
                        "sourceCapture": str(args.source_capture.expanduser().resolve()),
                        "slotTypeIds": slot_type_ids,
                        "requestCount": len(plan),
                        "requests": [
                            {"path": row["path"], "namespace": row["namespace"]}
                            for row in plan
                        ],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 0
        _load_env(args.env_file, stdin=args.env_stdin)
        if not blizzard_credentials_configured():
            raise OfficialModifiedCraftingError(
                "S2_OFFICIAL_MODIFIED_CRAFTING_CREDENTIALS_UNAVAILABLE"
            )
        result = capture_modified_crafting_slot_types(
            source_capture_root=args.source_capture,
            output_root=args.output_root,
            reader=_BlizzardReader(region=args.region, locale=args.locale),
            region=args.region,
            locale=args.locale,
            namespace=args.namespace,
            captured_at=args.captured_at,
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (OfficialModifiedCraftingError, OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
