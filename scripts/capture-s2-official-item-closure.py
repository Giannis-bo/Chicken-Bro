#!/usr/bin/env python3
"""Capture official Blizzard item payloads discovered by the bounded DB2 graph."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError


SEASON_KEY = "midnight-season-2"
MANIFEST_REVISION = "s2-official-api-capture-manifest-v1"


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _request_key(path: str, *, namespace: str, region: str, locale: str) -> str:
    identity = {
        "path": path,
        "query": {},
        "namespace": namespace,
        "region": region,
        "locale": locale,
    }
    return "request:sha256:" + hashlib.sha256(_canonical(identity).encode("utf-8")).hexdigest()


def _load_env(path: Path | None = None, *, stdin: bool = False) -> None:
    if stdin:
        lines = sys.stdin.read().splitlines()
    elif path is not None:
        lines = path.read_text(encoding="utf-8").splitlines()
    else:
        lines = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            os.environ[key] = value


def _token(region: str) -> str:
    import base64

    import urllib.parse

    client_id = os.environ.get("WOW_BLIZZARD_CLIENT_ID") or os.environ.get("WOW_BNET_CLIENT_ID")
    client_secret = os.environ.get("WOW_BLIZZARD_CLIENT_SECRET") or os.environ.get("WOW_BNET_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("Blizzard credentials are unavailable")
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    body = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode("utf-8")
    request = Request(
        "https://oauth.battle.net/token",
        data=body,
        headers={
            "Authorization": "Basic " + basic,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urlopen(request, timeout=int(os.environ.get("WOW_BLIZZARD_TIMEOUT_SECONDS", "90"))) as response:
        payload = json.loads(response.read().decode("utf-8"))
    access_token = payload.get("access_token")
    if not access_token:
        raise RuntimeError("Blizzard OAuth response did not include access_token")
    return str(access_token)


def _fetch_item(
    item_id: str,
    *,
    token: str,
    namespace: str,
    region: str,
    locale: str,
    allow_missing: bool = False,
    allow_http_errors: bool = False,
) -> tuple[str, dict | None, dict | None]:
    path = "/data/wow/item/" + item_id
    query = urlencode({"namespace": namespace, "locale": locale})
    url = f"https://{region}.api.blizzard.com{path}?{query}"
    last_error = None
    for attempt in range(4):
        try:
            request = Request(url, headers={"Authorization": "Bearer " + token})
            with urlopen(request, timeout=int(os.environ.get("WOW_BLIZZARD_TIMEOUT_SECONDS", "90"))) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict) or str(payload.get("id")) != item_id:
                raise RuntimeError("official item identity mismatch")
            return item_id, payload, None
        except HTTPError as error:  # pragma: no cover - live network path
            if allow_missing and error.code == 404:
                return (
                    item_id,
                    None,
                    {
                        "itemId": item_id,
                        "path": path,
                        "namespace": namespace,
                        "region": region,
                        "locale": locale,
                        "status": "not_found",
                        "httpStatus": 404,
                    },
                )
            if allow_http_errors:
                return (
                    item_id,
                    None,
                    {
                        "itemId": item_id,
                        "path": path,
                        "namespace": namespace,
                        "region": region,
                        "locale": locale,
                        "status": "blocked",
                        "httpStatus": error.code,
                    },
                )
            last_error = error
            if attempt < 3:
                time.sleep(2**attempt)
        except Exception as error:  # pragma: no cover - live network path
            if allow_http_errors:
                return (
                    item_id,
                    None,
                    {
                        "itemId": item_id,
                        "path": path,
                        "namespace": namespace,
                        "region": region,
                        "locale": locale,
                        "status": "blocked",
                        "errorType": type(error).__name__,
                    },
                )
            last_error = error
            if attempt < 3:
                time.sleep(2**attempt)
    raise RuntimeError(f"official item {item_id} failed: {last_error}")


def capture_item_closure(
    *,
    item_ids: list[str],
    output_root: Path,
    env_file: Path | None,
    region: str = "us",
    locale: str = "en_US",
    client_build: str = "12.1.0.68914",
    namespace: str | None = None,
    workers: int = 8,
    allow_missing: bool = False,
    env_stdin: bool = False,
    allow_http_errors: bool = False,
) -> dict:
    if not item_ids or len(set(item_ids)) != len(item_ids):
        raise ValueError("item_ids must be a non-empty unique list")
    if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
        raise ValueError("workers must be a positive integer")
    root = Path(output_root).expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("official item capture output root must be empty")
    root.mkdir(parents=True, exist_ok=True)
    _load_env(
        Path(env_file).expanduser().resolve() if env_file is not None else None,
        stdin=env_stdin,
    )
    os.environ.setdefault("WOW_BLIZZARD_TIMEOUT_SECONDS", "90")
    namespace = namespace or f"static-{client_build}-{region}"
    token = _token(region)
    captured_at = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(workers, len(item_ids))) as pool:
        futures = [
            pool.submit(
                _fetch_item,
                item_id,
                token=token,
                namespace=namespace,
                region=region,
                locale=locale,
                allow_missing=allow_missing,
                allow_http_errors=allow_http_errors,
            )
            for item_id in item_ids
        ]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    missing_items = []
    blocked_items = []
    successful_results = []
    for item_id, payload, missing in results:
        if missing is not None:
            if missing.get("status") == "not_found":
                missing_items.append(missing)
            else:
                blocked_items.append(missing)
            continue
        successful_results.append((item_id, payload))
    successful_results.sort(key=lambda pair: int(pair[0]))
    missing_items.sort(key=lambda row: int(row["itemId"]))
    entries = []
    for item_id, payload in successful_results:
        body = _canonical(payload).encode("utf-8")
        relative = Path("raw") / f"{item_id}.json"
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_bytes(body)
        path = f"/data/wow/item/{item_id}"
        entries.append(
            {
                "requestKey": _request_key(path, namespace=namespace, region=region, locale=locale),
                "path": path,
                "namespace": namespace,
                "region": region,
                "locale": locale,
                "query": {},
                "paginationParentRequestKey": None,
                "responsePath": relative.as_posix(),
                "responseSha256": hashlib.sha256(body).hexdigest(),
                "responseBytes": len(body),
                "capturedAt": captured_at,
                "pagination": {"complete": True, "page": 1, "pageCount": 1},
            }
        )
    manifest = {
        "schemaRevision": MANIFEST_REVISION,
        "seasonKey": SEASON_KEY,
        "status": "partial" if missing_items or blocked_items else "captured",
        "region": region,
        "locale": locale,
        "namespace": namespace,
        "namespaces": [namespace],
        "capturePurpose": "db2_discovered_crafted_output_items",
        "sourceDb2Build": client_build,
        "entries": entries,
        "missingItems": missing_items,
        "blockedItems": blocked_items,
    }
    (root / "capture-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "status": "partial" if missing_items or blocked_items else "captured",
        "outputRoot": str(root),
        "itemCount": len(entries),
        "missingCount": len(missing_items),
        "missingItemIds": [row["itemId"] for row in missing_items],
        "blockedCount": len(blocked_items),
        "blockedItemIds": [row["itemId"] for row in blocked_items],
        "manifestSha256": hashlib.sha256((root / "capture-manifest.json").read_bytes()).hexdigest(),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--item-ids-file", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument(
        "--env-stdin",
        action="store_true",
        help="read the existing KEY=VALUE environment from stdin without persisting credentials locally",
    )
    parser.add_argument("--region", default="us")
    parser.add_argument("--locale", default="en_US")
    parser.add_argument("--client-build", default="12.1.0.68914")
    parser.add_argument("--namespace")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="record exact HTTP 404 item identities as partial exclusions instead of failing the whole capture",
    )
    parser.add_argument(
        "--allow-http-errors",
        action="store_true",
        help="record non-404 official item HTTP/request failures as blockedItems and keep the capture partial",
    )
    parser.add_argument("--live", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.env_file and args.env_stdin:
        raise SystemExit("--env-file and --env-stdin are mutually exclusive")
    if args.live and not args.env_file and not args.env_stdin:
        raise SystemExit("--live requires --env-file or --env-stdin")
    if not args.live:
        print(json.dumps({"status": "dry_run", "networkCalls": 0}, sort_keys=True))
        return 0
    payload = json.loads(args.item_ids_file.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        item_ids = payload.get("craftedOutputItemIds")
        if item_ids is None:
            item_ids = payload.get("itemIds")
    else:
        item_ids = payload
    item_ids = [str(value) for value in item_ids or []]
    result = capture_item_closure(
        item_ids=item_ids,
        output_root=args.output_root,
        env_file=args.env_file,
        region=args.region,
        locale=args.locale,
        client_build=args.client_build,
        namespace=args.namespace,
        workers=args.workers,
        allow_missing=args.allow_missing,
        env_stdin=args.env_stdin,
        allow_http_errors=args.allow_http_errors,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
