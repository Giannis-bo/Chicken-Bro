#!/usr/bin/env python3
"""Capture the frozen Midnight Season 2 official Game Data request graph.

The default mode is a network-free request-plan preview.  ``--live`` is an
explicit, operator-run action that reads the existing Blizzard credentials and
writes only the caller-selected raw capture directory plus its manifest.
"""

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

from server.s2_official_api_capture import (  # noqa: E402
    OfficialApiCaptureError,
    build_official_request_plan,
    capture_official_request_plan,
)
from server.s2_official_api_fact_snapshot import (  # noqa: E402
    validate_product_content_scope,
)
from server.websim_payload import (  # noqa: E402
    blizzard_credentials_configured,
    blizzard_get,
    get_blizzard_access_token,
)


class _DryRunReader:
    def get(self, path, *, namespace, region, locale, query):  # pragma: no cover
        raise AssertionError("dry-run request plan must not call the reader")


class _ExistingBlizzardReader:
    def __init__(self, *, region: str, locale: str):
        self.region = region
        self.locale = locale
        self.token = get_blizzard_access_token(region)

    def get(self, path, *, namespace, region, locale, query):
        if region != self.region or locale != self.locale:
            raise OfficialApiCaptureError("reader region/locale drifted")
        for attempt in range(3):
            try:
                return blizzard_get(
                    path,
                    self.token,
                    region=region,
                    locale=locale,
                    params=query,
                    namespace=namespace,
                )
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2**attempt)
        raise AssertionError("unreachable")


def _load_environment_file(path: str | None) -> None:
    if not path:
        return
    source = Path(path).expanduser().resolve()
    for raw_line in source.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture the S2 four-category official Blizzard Game Data graph."
    )
    parser.add_argument("--scope", required=True, help="product content scope JSON")
    parser.add_argument(
        "--source-policy",
        default=str(ROOT / "server/data/midnight-season-2/source-policy.json"),
        help="official S2 source policy containing classSetNames",
    )
    parser.add_argument("--region", default="us")
    parser.add_argument("--locale", default="en_US")
    parser.add_argument("--env-file")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--dry-run-request-plan", action="store_true")
    parser.add_argument("--output-root")
    return parser


def _read_scope(path: str) -> dict:
    scope_path = Path(path).expanduser().resolve()
    return validate_product_content_scope(
        json.loads(scope_path.read_text(encoding="utf-8"))
    )


def _read_item_set_names(path: str) -> list[str]:
    policy_path = Path(path).expanduser().resolve()
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    names = payload.get("classSetNames") if isinstance(payload, dict) else None
    if not isinstance(names, list):
        raise OfficialApiCaptureError(
            "S2_OFFICIAL_CAPTURE_SET_POLICY_UNAVAILABLE: classSetNames is required"
        )
    normalized = [str(name).strip() for name in names if str(name or "").strip()]
    if not normalized or len(normalized) != len(set(normalized)):
        raise OfficialApiCaptureError(
            "S2_OFFICIAL_CAPTURE_SET_POLICY_INVALID: classSetNames is not unique"
        )
    return normalized


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.live and args.dry_run_request_plan:
        parser.error("--live and --dry-run-request-plan are mutually exclusive")
    live = bool(args.live)
    if live and not args.output_root:
        parser.error("--live requires --output-root")
    if not live and args.output_root:
        parser.error("--output-root is only valid with --live")

    try:
        scope = _read_scope(args.scope)
        plan = build_official_request_plan(
            product_scope=scope,
            reader=_DryRunReader(),
            region=args.region,
            locale=args.locale,
        )
        if not live:
            print(
                json.dumps(
                    {
                        "status": "dry_run",
                        "seasonKey": scope["seasonKey"],
                        "requestCount": len(plan),
                        "requests": [
                            {
                                "path": row["path"],
                                "namespace": row["namespace"],
                                "region": row["region"],
                                "locale": row["locale"],
                                "query": row["query"],
                            }
                            for row in plan
                        ],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 0

        _load_environment_file(args.env_file)
        if not blizzard_credentials_configured():
            raise OfficialApiCaptureError(
                "S2_OFFICIAL_CAPTURE_CREDENTIALS_UNAVAILABLE: "
                "existing Blizzard credentials are not configured"
            )
        reader = _ExistingBlizzardReader(region=args.region, locale=args.locale)
        item_set_names = _read_item_set_names(args.source_policy)
        result = capture_official_request_plan(
            plan=plan,
            output_root=Path(args.output_root),
            reader=reader,
            item_set_names=item_set_names,
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (OfficialApiCaptureError, OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
