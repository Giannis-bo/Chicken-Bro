"""Controlled Blizzard Game Data capture for the Midnight Season 2 scope.

This module owns only the read-and-record boundary.  It deliberately does not
normalize item facts, build a Catalog, call SimC, or change an active release.
The request graph starts from the frozen four-category selector and may expand
only through canonical Blizzard Game Data references found in responses.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol
from urllib.parse import parse_qs, urlsplit

from server.s2_official_api_fact_snapshot import (
    CAPTURE_MANIFEST_SCHEMA_REVISION,
    SEASON_KEY,
    request_key,
    validate_capture_manifest,
    validate_product_content_scope,
)


class BlizzardGameDataReader(Protocol):
    def get(
        self,
        path: str,
        *,
        namespace: str,
        region: str,
        locale: str,
        query: dict,
    ) -> dict:
        """Read one official Blizzard Game Data response."""


class OfficialApiCaptureError(ValueError):
    """Raised when capture would leave the official-fact boundary."""


_ALLOWED_PATH_PATTERNS = (
    re.compile(r"^/data/wow/journal-instance/\d+$"),
    re.compile(r"^/data/wow/journal-encounter/\d+$"),
    re.compile(r"^/data/wow/item/\d+$"),
    re.compile(r"^/data/wow/item-set/(?:index|\d+)$"),
    re.compile(r"^/data/wow/profession/(?:index|\d+)$"),
    re.compile(r"^/data/wow/profession/\d+/skill-tier/\d+$"),
    re.compile(r"^/data/wow/recipe/\d+$"),
    re.compile(r"^/data/wow/modified-crafting/reagent-slot-type/\d+$"),
    re.compile(r"^/data/wow/mythic-keystone/season/(?:index|\d+)$"),
    re.compile(r"^/data/wow/mythic-keystone/period/\d+$"),
    re.compile(r"^/data/wow/mythic-keystone/dungeon/\d+$"),
)
_SENSITIVE_QUERY_KEYS = frozenset(
    {
        "access_token",
        "authorization",
        "client_secret",
        "password",
        "token",
    }
)
_BOOTSTRAP_INSTANCE_NAMESPACE = "static"
_BOOTSTRAP_DYNAMIC_NAMESPACE = "dynamic"
_GEAR_PRODUCING_PROFESSION_IDS = frozenset(
    {
        "164",  # Blacksmithing
        "165",  # Leatherworking
        "171",  # Alchemy
        "197",  # Tailoring
        "202",  # Engineering
        "333",  # Enchanting
        "755",  # Jewelcrafting
        "773",  # Inscription
    }
)


def _text(value: Any, label: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise OfficialApiCaptureError(f"{label} is required")
    return result


def _canonical(value: Any) -> Any:
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _instant(value: str | None = None) -> str:
    raw = value or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise OfficialApiCaptureError("capturedAt must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _namespace(region: str, namespace_type: str) -> str:
    return f"{namespace_type}-{region}"


def _is_official_namespace(value: Any, region: str) -> bool:
    namespace = str(value or "").strip()
    if not re.fullmatch(r"(?:static|dynamic)-[A-Za-z0-9_.-]+", namespace):
        return False
    return namespace.endswith(f"-{region}")


def _is_allowed_path(path: str) -> bool:
    return any(pattern.fullmatch(path) for pattern in _ALLOWED_PATH_PATTERNS)


def _validate_request(
    row: Mapping[str, Any],
    *,
    region: str,
    locale: str,
) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        raise OfficialApiCaptureError("request plan entry must be an object")
    path = _text(row.get("path"), "request path")
    if not path.startswith("/data/wow/") or not _is_allowed_path(path):
        raise OfficialApiCaptureError(
            f"S2_OFFICIAL_CAPTURE_NON_OFFICIAL_PATH: {path}"
        )
    request_region = _text(row.get("region", region), "request region")
    request_locale = _text(row.get("locale", locale), "request locale")
    if request_region != region or request_locale != locale:
        raise OfficialApiCaptureError("request plan region/locale drifted")
    namespace = _text(row.get("namespace"), "request namespace")
    if not _is_official_namespace(namespace, region):
        raise OfficialApiCaptureError(
            f"S2_OFFICIAL_CAPTURE_NON_OFFICIAL_NAMESPACE: {namespace}"
        )
    query = row.get("query") or {}
    if not isinstance(query, Mapping):
        raise OfficialApiCaptureError("request query must be an object")
    normalized_query = dict(query)
    for key in normalized_query:
        if str(key).casefold() in _SENSITIVE_QUERY_KEYS:
            raise OfficialApiCaptureError("request query must not contain credentials")
        if str(key) in {"namespace", "locale"}:
            raise OfficialApiCaptureError(
                "request query must not duplicate namespace or locale"
            )
    parent = row.get("paginationParentRequestKey")
    if parent is not None and not str(parent).strip():
        raise OfficialApiCaptureError(
            "paginationParentRequestKey must be null or non-empty"
        )
    return {
        "requestKey": request_key(
            path,
            normalized_query,
            namespace=namespace,
            region=region,
            locale=locale,
        ),
        "path": path,
        "namespace": namespace,
        "region": region,
        "locale": locale,
        "query": _canonical(normalized_query),
        "paginationParentRequestKey": str(parent).strip() if parent else None,
    }


def _seed(path: str, *, namespace: str, region: str, locale: str) -> dict[str, Any]:
    return _validate_request(
        {
            "path": path,
            "namespace": namespace,
            "region": region,
            "locale": locale,
            "query": {},
            "paginationParentRequestKey": None,
        },
        region=region,
        locale=locale,
    )


def build_official_request_plan(
    *,
    product_scope: Mapping[str, Any],
    reader: BlizzardGameDataReader,
    region: str = "us",
    locale: str = "en_US",
) -> list[dict[str, Any]]:
    """Build the uncapped official bootstrap plan for the four-category scope."""

    scope = validate_product_content_scope(product_scope)
    if not callable(getattr(reader, "get", None)):
        raise OfficialApiCaptureError("reader must provide get()")
    region = _text(region, "region")
    locale = _text(locale, "locale")
    static_namespace = _namespace(region, _BOOTSTRAP_INSTANCE_NAMESPACE)
    dynamic_namespace = _namespace(region, _BOOTSTRAP_DYNAMIC_NAMESPACE)

    paths: list[tuple[str, str]] = []
    selections = scope["journalInstanceSelections"]
    for instance_id in selections["mythic_plus"]:
        paths.append((f"/data/wow/journal-instance/{instance_id}", static_namespace))
    for selection in selections["lair"]:
        paths.append(
            (
                f"/data/wow/journal-instance/{selection['journalInstanceId']}",
                static_namespace,
            )
        )
    for selection in selections["raid"]:
        paths.append(
            (
                f"/data/wow/journal-instance/{selection['journalInstanceId']}",
                static_namespace,
            )
        )
    paths.extend(
        [
            ("/data/wow/item-set/index", static_namespace),
            ("/data/wow/profession/index", static_namespace),
            ("/data/wow/mythic-keystone/season/index", dynamic_namespace),
        ]
    )
    plan = [
        _seed(path, namespace=namespace, region=region, locale=locale)
        for path, namespace in paths
    ]
    if len({row["requestKey"] for row in plan}) != len(plan):
        raise OfficialApiCaptureError("official bootstrap request plan has duplicates")
    return plan


def _reference_strings(value: Any):
    if isinstance(value, Mapping):
        href = value.get("href")
        if isinstance(href, str):
            yield href
        key = value.get("key")
        if isinstance(key, Mapping) and isinstance(key.get("href"), str):
            yield key["href"]
        for child in value.values():
            yield from _reference_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _reference_strings(child)


def _reference_request(
    raw_reference: str,
    *,
    parent: Mapping[str, Any],
) -> dict[str, Any] | None:
    parts = urlsplit(raw_reference)
    raw_path = parts.path
    if parts.netloc or parts.scheme:
        host = (parts.hostname or "").casefold()
        expected_host = f"{parent['region']}.api.blizzard.com".casefold()
        if host != expected_host:
            if "/data/wow/" in raw_path:
                raise OfficialApiCaptureError(
                    "S2_OFFICIAL_CAPTURE_NON_OFFICIAL_REFERENCE: "
                    f"{raw_reference} is not an official reference"
                )
            return None
    elif not raw_reference.startswith("/data/wow/"):
        return None

    if not raw_path.startswith("/data/wow/"):
        return None
    if not _is_allowed_path(raw_path):
        return None

    query: dict[str, Any] = {}
    parsed_query = parse_qs(parts.query, keep_blank_values=True)
    namespace = str(parent["namespace"])
    locale = str(parent["locale"])
    for key, values in parsed_query.items():
        if key.casefold() in _SENSITIVE_QUERY_KEYS:
            raise OfficialApiCaptureError("official reference query contains credentials")
        if len(values) != 1:
            raise OfficialApiCaptureError(
                f"official reference query has duplicate key: {key}"
            )
        value = values[0]
        if key == "namespace":
            namespace = value
        elif key == "locale":
            locale = value
        else:
            query[key] = value
    if not _is_official_namespace(namespace, str(parent["region"])):
        raise OfficialApiCaptureError(
            f"S2_OFFICIAL_CAPTURE_NON_OFFICIAL_NAMESPACE: {namespace}"
        )
    if locale != parent["locale"]:
        raise OfficialApiCaptureError("official reference locale drifted")
    return _validate_request(
        {
            "path": raw_path,
            "namespace": namespace,
            "region": parent["region"],
            "locale": locale,
            "query": query,
            "paginationParentRequestKey": parent["requestKey"],
        },
        region=str(parent["region"]),
        locale=str(parent["locale"]),
    )


def _pagination(response: Mapping[str, Any]) -> tuple[int, int]:
    page = response.get("page")
    page_count = response.get("pageCount")
    if page is None and page_count is None:
        return 1, 1
    if (
        isinstance(page, bool)
        or not isinstance(page, int)
        or page <= 0
        or isinstance(page_count, bool)
        or not isinstance(page_count, int)
        or page_count <= 0
    ):
        raise OfficialApiCaptureError(
            "S2_OFFICIAL_CAPTURE_INCOMPLETE_PAGINATION: invalid page/pageCount"
        )
    if page > page_count:
        raise OfficialApiCaptureError(
            "S2_OFFICIAL_CAPTURE_INCOMPLETE_PAGINATION: page exceeds pageCount"
        )
    return page, page_count


def _item_id_from_path(path: str) -> str:
    match = re.fullmatch(r"/data/wow/item/(\d+)", path)
    return match.group(1) if match else ""


def _item_set_id_from_path(path: str) -> str:
    match = re.fullmatch(r"/data/wow/item-set/(\d+)", path)
    return match.group(1) if match else ""


def _profession_id_from_path(path: str) -> str:
    match = re.fullmatch(r"/data/wow/profession/(\d+)", path)
    return match.group(1) if match else ""


def _profession_skill_tier_id_from_path(path: str) -> str:
    match = re.fullmatch(r"/data/wow/profession/\d+/skill-tier/(\d+)", path)
    return match.group(1) if match else ""


def _midnight_skill_tier_ids(response: Mapping[str, Any]) -> set[str]:
    selected: set[str] = set()
    rows = response.get("skill_tiers")
    if not isinstance(rows, list):
        return selected
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if "midnight" not in _canonical_name(row.get("name")):
            continue
        direct_id = row.get("id")
        if isinstance(direct_id, int) and not isinstance(direct_id, bool) and direct_id > 0:
            selected.add(str(direct_id))
            continue
        for raw_reference in _reference_strings(row):
            match = re.search(
                r"/data/wow/profession/\d+/skill-tier/(\d+)(?:\?|$)",
                raw_reference,
            )
            if match:
                selected.add(match.group(1))
    return selected


def _current_mythic_season_id(response: Mapping[str, Any]) -> str:
    current = response.get("current_season")
    if not isinstance(current, Mapping):
        raise OfficialApiCaptureError(
            "S2_OFFICIAL_CAPTURE_SCOPE_MISMATCH: mythic season index has no current_season"
        )
    value = current.get("id")
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise OfficialApiCaptureError(
            "S2_OFFICIAL_CAPTURE_SCOPE_MISMATCH: current mythic season id is invalid"
        )
    return str(value)


def _validate_midnight_s2_season(response: Mapping[str, Any], *, season_id: str) -> None:
    season_name = _canonical_name(response.get("season_name"))
    if "midnight season 2" not in season_name:
        raise OfficialApiCaptureError(
            "S2_OFFICIAL_CAPTURE_SCOPE_MISMATCH: "
            f"current mythic season {season_id} is not Midnight Season 2"
        )


def _canonical_name(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


def _item_set_index_ids(
    response: Mapping[str, Any],
    item_set_names: set[str] | None,
) -> set[str]:
    if item_set_names is None:
        return set()
    selected: set[str] = set()
    rows = response.get("item_sets")
    if not isinstance(rows, list):
        return selected
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if _canonical_name(row.get("name")) not in item_set_names:
            continue
        direct_id = row.get("id")
        if isinstance(direct_id, int) and not isinstance(direct_id, bool) and direct_id > 0:
            selected.add(str(direct_id))
            continue
        for raw_reference in _reference_strings(row):
            match = re.search(r"/data/wow/item-set/(\d+)(?:\?|$)", raw_reference)
            if match:
                selected.add(match.group(1))
    return selected


def _item_set_item_ids(response: Mapping[str, Any]) -> set[str]:
    item_ids: set[str] = set()
    rows = response.get("items")
    if not isinstance(rows, list):
        return item_ids
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        direct_id = row.get("id")
        if isinstance(direct_id, int) and not isinstance(direct_id, bool) and direct_id > 0:
            item_ids.add(str(direct_id))
            continue
        for raw_reference in _reference_strings(row):
            match = re.search(r"/data/wow/item/(\d+)(?:\?|$)", raw_reference)
            if match:
                item_ids.add(match.group(1))
    return item_ids


def _atomic_write(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_bytes(body)
    os.replace(temporary, path)


def _capture_failure_code(error: Exception) -> str:
    match = re.match(r"(S2_[A-Z0-9_]+)", str(error))
    return match.group(1) if match else "S2_OFFICIAL_CAPTURE_BLOCKED"


def _write_capture_failure(
    root: Path,
    *,
    request: Mapping[str, Any],
    error: Exception,
    raw_response_count: int,
) -> None:
    failure = {
        "schemaRevision": "s2-official-api-capture-failure-v1",
        "seasonKey": SEASON_KEY,
        "status": "blocked",
        "errorCode": _capture_failure_code(error),
        "failedRequest": {
            "requestKey": request["requestKey"],
            "path": request["path"],
            "namespace": request["namespace"],
            "region": request["region"],
            "locale": request["locale"],
            "query": request["query"],
        },
        "rawResponseCount": raw_response_count,
        "capturedAt": _instant(),
    }
    _atomic_write(root / "capture-failure.json", _canonical_bytes(failure))


def _capture_root(path: Path) -> Path:
    root = Path(path).expanduser().resolve()
    if root.exists() and not root.is_dir():
        raise OfficialApiCaptureError("capture output root must be a directory")
    if root.exists():
        existing = list(root.iterdir())
        if existing:
            raise OfficialApiCaptureError(
                "S2_OFFICIAL_CAPTURE_INCOMPLETE_MANIFEST: capture root must be empty"
            )
    root.mkdir(parents=True, exist_ok=True)
    return root


def capture_official_request_plan(
    *,
    plan: list[Mapping[str, Any]],
    output_root: Path,
    reader: BlizzardGameDataReader,
    captured_at: str | None = None,
    item_set_names: list[str] | None = None,
) -> dict[str, Any]:
    """Fetch the complete discovered graph and write an immutable raw manifest."""

    if not isinstance(plan, list) or not plan:
        raise OfficialApiCaptureError("capture request plan must be a non-empty list")
    root = _capture_root(Path(output_root))
    capture_time = _instant(captured_at)
    normalized_item_set_names = None
    if item_set_names is not None:
        normalized_item_set_names = {
            _canonical_name(name)
            for name in item_set_names
            if _canonical_name(name)
        }
        if not normalized_item_set_names:
            raise OfficialApiCaptureError(
                "item_set_names must contain at least one non-empty name"
            )
    queue = deque(
        (
            _validate_request(
                row,
                region=_text(row.get("region"), "request region"),
                locale=_text(row.get("locale"), "request locale"),
            ),
            False,
        )
        for row in plan
    )
    entries: dict[str, dict[str, Any]] = {}
    selected_item_ids: set[str] = set()
    pending_item_set_children: dict[str, tuple[set[str], list[dict[str, Any]]]] = {}
    expanded_item_sets: set[str] = set()
    allowed_item_set_ids: set[str] = set()
    current_mythic_season_id: str | None = None
    allowed_midnight_skill_tier_ids: set[str] = set()

    def flush_pending_item_sets() -> None:
        for set_key, (set_item_ids, children) in list(
            pending_item_set_children.items()
        ):
            if set_key in expanded_item_sets:
                pending_item_set_children.pop(set_key, None)
                continue
            if selected_item_ids.intersection(set_item_ids):
                expanded_item_sets.add(set_key)
                pending_item_set_children.pop(set_key, None)
                queue.extend((child, False) for child in children)

    while queue:
        request, deferred_item_set = queue.popleft()
        key = request["requestKey"]
        if key in entries:
            continue
        try:
            response = reader.get(
                request["path"],
                namespace=request["namespace"],
                region=request["region"],
                locale=request["locale"],
                query=dict(request["query"]),
            )
        except OfficialApiCaptureError as error:
            _write_capture_failure(
                root,
                request=request,
                error=error,
                raw_response_count=len(entries),
            )
            raise
        except Exception as error:  # pragma: no cover - network adapter detail
            wrapped = OfficialApiCaptureError(
                f"S2_OFFICIAL_CAPTURE_REQUEST_FAILED: {request['path']}"
            )
            _write_capture_failure(
                root,
                request=request,
                error=wrapped,
                raw_response_count=len(entries),
            )
            raise wrapped from error
        if not isinstance(response, Mapping):
            raise OfficialApiCaptureError(
                f"S2_OFFICIAL_CAPTURE_INVALID_RESPONSE: {request['path']}"
            )
        normalized_response = _canonical(response)
        body = _canonical_bytes(normalized_response)
        response_path = Path("raw") / f"{key.rsplit(':', 1)[-1]}.json"
        absolute_response_path = root / response_path
        if absolute_response_path.exists():
            raise OfficialApiCaptureError(
                "S2_OFFICIAL_CAPTURE_INCOMPLETE_MANIFEST: response path collision"
            )
        _atomic_write(absolute_response_path, body)
        page, page_count = _pagination(normalized_response)
        entries[key] = {
            **request,
            "responsePath": response_path.as_posix(),
            "responseSha256": hashlib.sha256(body).hexdigest(),
            "responseBytes": len(body),
            "capturedAt": capture_time,
            "pagination": {"page": page, "pageCount": page_count, "complete": True},
        }

        if request["path"] == "/data/wow/mythic-keystone/season/index":
            current_mythic_season_id = _current_mythic_season_id(normalized_response)
        season_detail_id = re.fullmatch(
            r"/data/wow/mythic-keystone/season/(\d+)", request["path"]
        )
        if season_detail_id and season_detail_id.group(1) == current_mythic_season_id:
            _validate_midnight_s2_season(
                normalized_response,
                season_id=season_detail_id.group(1),
            )

        is_item_set_detail = bool(
            re.fullmatch(r"/data/wow/item-set/\d+", request["path"])
        )
        if request["path"] == "/data/wow/item-set/index":
            allowed_item_set_ids.update(
                _item_set_index_ids(normalized_response, normalized_item_set_names)
            )
        if re.fullmatch(r"/data/wow/profession/\d+", request["path"]):
            allowed_midnight_skill_tier_ids.update(
                _midnight_skill_tier_ids(normalized_response)
            )
        item_set_ids = (
            _item_set_item_ids(normalized_response) if is_item_set_detail else set()
        )
        defer_item_children = (
            is_item_set_detail
            and deferred_item_set
            and not selected_item_ids.intersection(item_set_ids)
        )
        deferred_children: list[dict[str, Any]] = []

        if page < page_count:
            next_query = dict(request["query"])
            next_query["_page"] = page + 1
            queue.append(
                (
                    _validate_request(
                        {
                            **request,
                            "query": next_query,
                            "paginationParentRequestKey": key,
                        },
                        region=request["region"],
                        locale=request["locale"],
                    ),
                    deferred_item_set,
                )
            )
        for raw_reference in dict.fromkeys(_reference_strings(normalized_response)):
            child = _reference_request(raw_reference, parent=request)
            if child is None or child["requestKey"] in entries:
                continue
            child_path = child["path"]
            child_item_id = _item_id_from_path(child_path)
            child_item_set_id = _item_set_id_from_path(child_path)
            child_profession_id = _profession_id_from_path(child_path)
            child_skill_tier_id = _profession_skill_tier_id_from_path(child_path)
            child_mythic_season_id = re.fullmatch(
                r"/data/wow/mythic-keystone/season/(\d+)", child_path
            )
            if (
                request["path"] == "/data/wow/mythic-keystone/season/index"
                and child_mythic_season_id
                and child_mythic_season_id.group(1) != current_mythic_season_id
            ):
                continue
            if child_item_id and request["path"].startswith(
                "/data/wow/journal-encounter/"
            ):
                selected_item_ids.add(child_item_id)
                flush_pending_item_sets()
            if request["path"] == "/data/wow/item-set/index" and re.fullmatch(
                r"/data/wow/item-set/\d+", child_path
            ):
                if (
                    normalized_item_set_names is not None
                    and child_item_set_id not in allowed_item_set_ids
                ):
                    continue
                queue.append((child, normalized_item_set_names is None))
                continue
            if child_profession_id and child_profession_id not in _GEAR_PRODUCING_PROFESSION_IDS:
                continue
            if (
                child_skill_tier_id
                and child_skill_tier_id not in allowed_midnight_skill_tier_ids
            ):
                continue
            if child_item_set_id and normalized_item_set_names is not None:
                if child_item_set_id not in allowed_item_set_ids:
                    continue
                queue.append((child, False))
                continue
            if defer_item_children and child_item_id:
                deferred_children.append(child)
                continue
            queue.append((child, False))
        if defer_item_children:
            pending_item_set_children[key] = (item_set_ids, deferred_children)
            flush_pending_item_sets()

    normalized_entries = sorted(entries.values(), key=lambda row: row["requestKey"])
    namespaces = sorted({row["namespace"] for row in normalized_entries})
    manifest = {
        "schemaRevision": CAPTURE_MANIFEST_SCHEMA_REVISION,
        "seasonKey": SEASON_KEY,
        "status": "captured",
        "region": str(normalized_entries[0]["region"]),
        "locale": str(normalized_entries[0]["locale"]),
        "namespace": namespaces[0] if len(namespaces) == 1 else "multiple",
        "namespaces": namespaces,
        "entries": normalized_entries,
    }
    validate_capture_manifest(manifest)
    _atomic_write(
        root / "capture-manifest.json",
        _canonical_bytes(manifest),
    )
    return {
        "status": "captured",
        "seasonKey": SEASON_KEY,
        "requestCount": len(normalized_entries),
        "namespaces": namespaces,
        "outputRoot": str(root),
    }
