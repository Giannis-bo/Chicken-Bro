#!/usr/bin/env python3
"""Capture a cursor-bounded official Blizzard equippable-item search range."""

from __future__ import annotations

import argparse
import base64
import ctypes
import gc
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.season_pve_official_capture import (  # noqa: E402
    OfficialCaptureContractError,
    validate_official_item_range_page,
)


SCHEMA_REVISION = "season-pve-official-item-range-v1"


def _json_bytes(value):
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _sha256(value):
    return hashlib.sha256(value).hexdigest()


def _release_page_memory():
    """Return per-page JSON allocations before advancing the cursor."""

    gc.collect()
    try:
        trim = ctypes.CDLL(None).malloc_trim
    except (AttributeError, OSError):
        return
    trim.argtypes = [ctypes.c_size_t]
    trim.restype = ctypes.c_int
    trim(0)


def _instant(value, label):
    raw = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as error:
        raise OfficialCaptureContractError(
            f"{label} requires an ISO-8601 instant"
        ) from error
    if parsed.tzinfo is None:
        raise OfficialCaptureContractError(f"{label} requires a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_environment_file(path):
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
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"'", '"'}
        ):
            value = value[1:-1]
        os.environ[key] = value


class _Writer:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def write_json(self, relative_path, payload):
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        body = _json_bytes(payload)
        temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
        with temporary.open("wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        if hasattr(os, "posix_fadvise") and hasattr(
            os,
            "POSIX_FADV_DONTNEED",
        ):
            with path.open("rb") as handle:
                os.posix_fadvise(
                    handle.fileno(),
                    0,
                    0,
                    os.POSIX_FADV_DONTNEED,
                )
        return {
            "relativePath": path.relative_to(self.root).as_posix(),
            "sha256": _sha256(body),
            "bytes": len(body),
        }


class _Client:
    def __init__(
        self,
        *,
        region,
        locale,
        timeout_seconds,
        retries,
        max_response_bytes,
        page_size,
    ):
        self.region = region
        self.locale = locale
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.max_response_bytes = max_response_bytes
        self.page_size = page_size
        self.token = self._oauth_token()

    def _read_json(self, request, label):
        last_error = None
        for attempt in range(1, self.retries + 1):
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    body = response.read(self.max_response_bytes + 1)
                if len(body) > self.max_response_bytes:
                    raise OfficialCaptureContractError(
                        f"{label} exceeds {self.max_response_bytes} bytes"
                    )
                payload = json.loads(body.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise OfficialCaptureContractError(
                        f"{label} response must be an object"
                    )
                return payload
            except (
                HTTPError,
                URLError,
                TimeoutError,
                json.JSONDecodeError,
            ) as error:
                last_error = error
                if attempt < self.retries:
                    time.sleep(min(2 ** (attempt - 1), 4))
        raise OfficialCaptureContractError(
            f"{label} failed after {self.retries} attempts: "
            f"{type(last_error).__name__}"
        ) from last_error

    def _oauth_token(self):
        client_id = (
            os.environ.get("WOW_BLIZZARD_CLIENT_ID")
            or os.environ.get("WOW_BNET_CLIENT_ID")
            or ""
        ).strip()
        client_secret = (
            os.environ.get("WOW_BLIZZARD_CLIENT_SECRET")
            or os.environ.get("WOW_BNET_CLIENT_SECRET")
            or ""
        ).strip()
        if not client_id or not client_secret:
            raise OfficialCaptureContractError(
                "Blizzard API credentials are not configured"
            )
        credentials = base64.b64encode(
            f"{client_id}:{client_secret}".encode("utf-8")
        ).decode("ascii")
        payload = self._read_json(
            Request(
                "https://oauth.battle.net/token",
                data=urlencode(
                    {"grant_type": "client_credentials"}
                ).encode("utf-8"),
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": (
                        "wow-mini-program-season-pve-item-audit/1.0"
                    ),
                },
                method="POST",
            ),
            "Blizzard OAuth",
        )
        token = str(payload.get("access_token") or "").strip()
        if not token:
            raise OfficialCaptureContractError(
                "Blizzard OAuth response omitted access_token"
            )
        return token

    def item_range(self, start_id, end_id):
        params = {
            "namespace": f"static-{self.region}",
            "locale": self.locale,
            "id": f"[{start_id},{end_id}]",
            "is_equippable": "true",
            "_pageSize": self.page_size,
            "_page": 1,
            "orderby": "id",
        }
        path = "/data/wow/search/item"
        url = (
            f"https://{self.region}.api.blizzard.com"
            f"{quote(path, safe='/%')}?{urlencode(params)}"
        )
        return self._read_json(
            Request(
                url,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "User-Agent": (
                        "wow-mini-program-season-pve-item-audit/1.0"
                    ),
                },
            ),
            f"official item range {start_id}-{end_id}",
        )


def capture(args):
    _load_environment_file(args.env_file)
    captured_at = _instant(args.captured_at, "captured-at")
    if args.start_id < 1 or args.end_id < args.start_id:
        raise OfficialCaptureContractError(
            "item range requires positive ordered bounds"
        )
    if (
        args.timeout_seconds < 1
        or args.timeout_seconds > 120
        or args.retries < 1
        or args.retries > 5
        or args.max_pages < 1
        or args.max_pages > 500
        or args.page_size < 1
        or args.page_size > 1000
        or args.max_response_bytes < 1024 * 1024
        or args.max_response_bytes > 16 * 1024 * 1024
        or args.max_total_bytes < 1024 * 1024
        or args.max_total_bytes > 1024 * 1024 * 1024
        or args.minimum_item_count < 0
        or args.minimum_item_count > 1000000
        or args.delay_seconds < 0
        or args.delay_seconds > 5
    ):
        raise OfficialCaptureContractError(
            "capture limits are outside the bounded safety policy"
        )
    output_root = Path(args.output).expanduser().resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise OfficialCaptureContractError(
            "capture output must be an empty isolated directory"
        )
    writer = _Writer(output_root)
    client = _Client(
        region=args.region,
        locale=args.locale,
        timeout_seconds=args.timeout_seconds,
        retries=args.retries,
        max_response_bytes=args.max_response_bytes,
        page_size=args.page_size,
    )
    cursor = args.start_id
    pages = []
    seen_ids = set()
    response_bytes = 0
    terminal = False
    while not terminal:
        if len(pages) >= args.max_pages:
            raise OfficialCaptureContractError(
                "official item range exceeded max-pages"
            )
        payload = client.item_range(cursor, args.end_id)
        validated = validate_official_item_range_page(
            payload,
            start_id=cursor,
            end_id=args.end_id,
            expected_page_size=args.page_size,
        )
        item_ids = [int(row["id"]) for row in validated["rows"]]
        duplicates = sorted(set(item_ids) & seen_ids, key=int)
        if duplicates:
            raise OfficialCaptureContractError(
                "official item range repeated item ids across cursors"
            )
        seen_ids.update(item_ids)
        relative_path = (
            "raw/game-data/items/equippable-range/"
            f"cursor-{cursor}.json"
        )
        record = writer.write_json(relative_path, payload)
        response_bytes += record["bytes"]
        if response_bytes > args.max_total_bytes:
            raise OfficialCaptureContractError(
                "official item range exceeded max-total-bytes"
            )
        pages.append(
            {
                **record,
                "cursor": cursor,
                "itemCount": len(item_ids),
                "firstItemId": str(item_ids[0]) if item_ids else "",
                "lastItemId": str(item_ids[-1]) if item_ids else "",
                "resultCountCapped": validated["resultCountCapped"],
            }
        )
        terminal = validated["terminal"]
        next_cursor = validated["nextCursor"]
        del payload
        del validated
        del item_ids
        _release_page_memory()
        if not terminal:
            cursor = next_cursor
            if args.delay_seconds:
                time.sleep(args.delay_seconds)
    if len(seen_ids) < args.minimum_item_count:
        raise OfficialCaptureContractError(
            "official item range did not reach minimum-item-count"
        )
    summary = {
        "schemaVersion": 1,
        "schemaRevision": SCHEMA_REVISION,
        "status": "captured",
        "capturedAt": captured_at,
        "region": args.region,
        "locale": args.locale,
        "range": {
            "startItemId": args.start_id,
            "endItemId": args.end_id,
            "equippable": True,
        },
        "pageCount": len(pages),
        "itemCount": len(seen_ids),
        "responseBytes": response_bytes,
        "firstItemId": str(min(seen_ids)) if seen_ids else "",
        "lastItemId": str(max(seen_ids)) if seen_ids else "",
        "itemIndexComplete": True,
        "sourceMembershipComplete": False,
        "membershipComplete": False,
        "reasonCode": "OFFICIAL_ITEM_RANGE_HAS_NO_SOURCE_MEMBERSHIP",
        "captureImplementation": {
            "schemaRevision": SCHEMA_REVISION,
            "scriptSha256": _sha256(
                Path(__file__).resolve().read_bytes()
            ),
            "validatorOwnerSha256": _sha256(
                (
                    ROOT / "server" / "season_pve_official_capture.py"
                ).read_bytes()
            ),
        },
        "captureLimits": {
            "pageSize": args.page_size,
            "maxPages": args.max_pages,
            "maxResponseBytes": args.max_response_bytes,
            "maxTotalResponseBytes": args.max_total_bytes,
            "minimumItemCount": args.minimum_item_count,
            "delaySeconds": args.delay_seconds,
        },
        "pages": pages,
    }
    summary_record = writer.write_json(
        "official-item-range-capture.json",
        summary,
    )
    manifest = {
        "schemaVersion": 1,
        "schemaRevision": SCHEMA_REVISION,
        "status": "captured",
        "capturedAt": captured_at,
        "itemCount": len(seen_ids),
        "pageCount": len(pages),
        "responseBytes": response_bytes,
        "responses": pages,
        "summary": summary_record,
    }
    writer.write_json("capture-manifest.json", manifest)
    return {
        "schemaRevision": SCHEMA_REVISION,
        "status": "captured",
        "capturedAt": captured_at,
        "range": summary["range"],
        "pageCount": len(pages),
        "itemCount": len(seen_ids),
        "responseBytes": response_bytes,
        "membershipComplete": False,
        "reasonCode": summary["reasonCode"],
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--start-id", type=int, required=True)
    parser.add_argument("--end-id", type=int, required=True)
    parser.add_argument("--captured-at", required=True)
    parser.add_argument("--env-file")
    parser.add_argument("--region", default="us")
    parser.add_argument("--locale", default="en_US")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--page-size", type=int, default=250)
    parser.add_argument(
        "--max-response-bytes",
        type=int,
        default=8 * 1024 * 1024,
    )
    parser.add_argument(
        "--max-total-bytes",
        type=int,
        default=512 * 1024 * 1024,
    )
    parser.add_argument("--minimum-item-count", type=int, default=1)
    parser.add_argument("--delay-seconds", type=float, default=0.2)
    return parser.parse_args(argv)


def main(argv=None):
    result = capture(parse_args(argv))
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OfficialCaptureContractError, OSError) as error:
        print(
            json.dumps(
                {
                    "schemaRevision": SCHEMA_REVISION,
                    "status": "blocked",
                    "reasonCode": "OFFICIAL_ITEM_RANGE_CAPTURE_FAILED",
                    "error": str(error)[:500],
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        raise SystemExit(2)
