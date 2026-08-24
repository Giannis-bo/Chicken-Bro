"""Bounded, field-scoped DB2 evidence capture for Midnight Season 2.

This module is intentionally narrower than a DB2 importer.  It can query only
exact ids discovered from the frozen Blizzard API capture or from an explicit
foreign-key edge in the allowlist.  The transport may return a wider DB2 row,
but only allowlisted fields are projected to disk; the transport mirror never
becomes the game-fact authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode


SCHEMA_REVISION = "s2-limited-client-db2-field-allowlist-v1"
CAPTURE_ADAPTER_REVISION = "s2-limited-db2-capture-adapter-v2"
_EXPECTED_TABLES_DIGEST = (
    "30a83bf243b9dd393e2dcd412c0f8c0ea919d40f823c8dce4f7107da26bd49bf"
)
_ID_PATTERN = re.compile(r"^[1-9][0-9]*$")


class LimitedDb2Error(ValueError):
    """Raised when a DB2 request or projection leaves the bounded contract."""


def _canonical(value: Any) -> Any:
    return json.loads(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _id(value: Any, label: str) -> str:
    if isinstance(value, bool) or value is None:
        raise LimitedDb2Error(f"{label} must be a positive integer id")
    text = str(value).strip()
    if not _ID_PATTERN.fullmatch(text):
        raise LimitedDb2Error(f"{label} must be a positive integer id")
    return text


def _target_value(value: Any, label: str, *, allow_zero: bool = False) -> str:
    """Validate an exact query value, including the DB2 default context sentinel."""

    if allow_zero and not isinstance(value, bool) and str(value).strip() == "0":
        return "0"
    return _id(value, label)


def validate_db2_field_allowlist(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise LimitedDb2Error("DB2 field allowlist must be an object")
    if payload.get("schemaVersion") != 1:
        raise LimitedDb2Error("DB2 field allowlist schemaVersion is invalid")
    if payload.get("schemaRevision") != SCHEMA_REVISION:
        raise LimitedDb2Error("DB2 field allowlist revision is invalid")
    if payload.get("seasonKey") != "midnight-season-2":
        raise LimitedDb2Error("DB2 field allowlist season is invalid")
    if not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", str(payload.get("clientBuild") or "")):
        raise LimitedDb2Error("DB2 clientBuild is invalid")

    authority = payload.get("authority")
    if not isinstance(authority, Mapping) or authority.get("kind") != "official_client_db2":
        raise LimitedDb2Error("DB2 authority must be official_client_db2")
    if authority.get("mirrorRole") != "transport_only":
        raise LimitedDb2Error("DB2 mirror must be transport-only")
    if authority.get("rawDb2Persisted") is not False:
        raise LimitedDb2Error("raw DB2 persistence is not allowed")
    if authority.get("thirdPartySchemaIsFactAuthority") is not False:
        raise LimitedDb2Error("third-party schema cannot be fact authority")

    contract = payload.get("queryContract")
    if not isinstance(contract, Mapping):
        raise LimitedDb2Error("DB2 query contract is required")
    if contract.get("endpointTemplate") != "https://wago.tools/api/db2-find/{table}":
        raise LimitedDb2Error("DB2 endpoint is not the bounded find endpoint")
    if contract.get("permittedFilterOperators") != ["exact"]:
        raise LimitedDb2Error("DB2 query must permit exact only")
    if contract.get("allowFullTableCsv") is not False:
        raise LimitedDb2Error("DB2 full-table CSV is not allowed")
    if contract.get("allowUnboundedSearch") is not False:
        raise LimitedDb2Error("DB2 unbounded search is not allowed")

    tables = payload.get("tables")
    if not isinstance(tables, Mapping) or not tables:
        raise LimitedDb2Error("DB2 tables allowlist is required")
    if canonical_json_sha256(tables) != _EXPECTED_TABLES_DIGEST:
        raise LimitedDb2Error("DB2 field allowlist contains an unapproved field")
    normalized_tables: dict[str, Any] = {}
    for table, raw_spec in tables.items():
        table_name = str(table).strip()
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", table_name):
            raise LimitedDb2Error("DB2 table name is invalid")
        if not isinstance(raw_spec, Mapping):
            raise LimitedDb2Error(f"DB2 table spec is invalid: {table_name}")
        key_field = str(raw_spec.get("keyField") or "").strip()
        filter_fields = raw_spec.get("filterFields")
        fields = raw_spec.get("fields")
        if (
            not key_field
            or not isinstance(filter_fields, list)
            or not filter_fields
            or not isinstance(fields, list)
            or not fields
        ):
            raise LimitedDb2Error(f"DB2 field allowlist is incomplete: {table_name}")
        normalized_filter_fields = [str(value).strip() for value in filter_fields]
        normalized_fields = [str(value).strip() for value in fields]
        if (
            len(set(normalized_filter_fields)) != len(normalized_filter_fields)
            or len(set(normalized_fields)) != len(normalized_fields)
            or any(not value or value == "*" for value in normalized_fields)
            or key_field not in normalized_fields
            or any(value not in normalized_fields for value in normalized_filter_fields)
        ):
            raise LimitedDb2Error(f"DB2 field allowlist is invalid: {table_name}")
        normalized_tables[table_name] = {
            **dict(raw_spec),
            "keyField": key_field,
            "filterFields": normalized_filter_fields,
            "fields": normalized_fields,
        }

    root_queries = payload.get("rootQueries")
    relations = payload.get("foreignKeyQueries")
    if not isinstance(root_queries, list) or not isinstance(relations, list):
        raise LimitedDb2Error("DB2 query graph is incomplete")
    allowed_target_kinds = set(contract.get("allowedTargetKinds") or [])
    for query in root_queries:
        if not isinstance(query, Mapping):
            raise LimitedDb2Error("DB2 root query is invalid")
        table = str(query.get("table") or "")
        field = str(query.get("filterField") or "")
        target_kind = str(query.get("targetKind") or "")
        if table not in normalized_tables or field not in normalized_tables[table]["filterFields"]:
            raise LimitedDb2Error("DB2 root query leaves field allowlist")
        if target_kind not in allowed_target_kinds:
            raise LimitedDb2Error("DB2 root query target kind is invalid")
        if not str(query.get("targetKey") or "").strip():
            raise LimitedDb2Error("DB2 root query target key is required")
    for relation in relations:
        if not isinstance(relation, Mapping):
            raise LimitedDb2Error("DB2 foreign-key query is invalid")
        from_table = str(relation.get("fromTable") or "")
        to_table = str(relation.get("toTable") or "")
        from_field = str(relation.get("fromField") or "")
        to_field = str(relation.get("toFilterField") or "")
        if (
            from_table not in normalized_tables
            or to_table not in normalized_tables
            or from_field not in normalized_tables[from_table]["fields"]
            or to_field not in normalized_tables[to_table]["filterFields"]
        ):
            raise LimitedDb2Error("DB2 foreign-key query leaves field allowlist")
        when = relation.get("when")
        if when is not None and not isinstance(when, Mapping):
            raise LimitedDb2Error("DB2 foreign-key condition is invalid")
        if isinstance(when, Mapping) and any(
            str(field) not in normalized_tables[from_table]["fields"] for field in when
        ):
            raise LimitedDb2Error("DB2 foreign-key condition leaves field allowlist")

    return {
        **dict(payload),
        "tables": normalized_tables,
        "rootQueries": [_canonical(row) for row in root_queries],
        "foreignKeyQueries": [_canonical(row) for row in relations],
    }


def _query_plan_row(
    *,
    table: str,
    filter_field: str,
    target_value: str,
    target_kind: str,
    allowlist: Mapping[str, Any],
) -> dict[str, Any]:
    tables = allowlist["tables"]
    spec = tables[table]
    if filter_field not in spec["filterFields"]:
        raise LimitedDb2Error(f"DB2 filter field is not allowlisted: {table}.{filter_field}")
    target_value = _target_value(
        target_value,
        f"{table}.{filter_field} target",
        allow_zero=table == "ItemCreationContext" and filter_field == "ItemContext",
    )
    query = {
        "build": allowlist["clientBuild"],
        f"filter[{filter_field}]": f"exact:{target_value}",
    }
    url = allowlist["queryContract"]["endpointTemplate"].format(table=table)
    request_key = canonical_json_sha256(
        {
            "url": url,
            "query": query,
        }
    )
    return {
        "requestKey": request_key,
        "url": f"{url}?{urlencode(query)}",
        "table": table,
        "filterField": filter_field,
        "targetValue": target_value,
        "targetKind": target_kind,
        "operator": "exact",
        "query": query,
        "fields": list(spec["fields"]),
    }


def collect_s2_official_db2_targets(manifest: Mapping[str, Any]) -> dict[str, list[str]]:
    """Extract DB2 roots only from the captured official API request paths."""

    if not isinstance(manifest, Mapping) or manifest.get("status") != "captured":
        raise LimitedDb2Error("official API capture must be captured")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise LimitedDb2Error("official API capture entries are required")
    target_sets = {
        "itemIds": set(),
        "recipeIds": set(),
        "mythicPlusSeasonIds": set(),
        "journalEncounterIds": set(),
    }
    patterns = {
        "itemIds": re.compile(r"^/data/wow/item/([1-9][0-9]*)$"),
        "recipeIds": re.compile(r"^/data/wow/recipe/([1-9][0-9]*)$"),
        "mythicPlusSeasonIds": re.compile(
            r"^/data/wow/mythic-keystone/season/([1-9][0-9]*)$"
        ),
        "journalEncounterIds": re.compile(
            r"^/data/wow/journal-encounter/([1-9][0-9]*)$"
        ),
    }
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise LimitedDb2Error("official API capture entry is invalid")
        path = str(entry.get("path") or "")
        for target_key, pattern in patterns.items():
            match = pattern.fullmatch(path)
            if match:
                target_sets[target_key].add(match.group(1))
                break
    return {
        key: sorted(values, key=int)
        for key, values in target_sets.items()
    }


def build_bounded_db2_query_plan(
    *,
    targets: Mapping[str, Any],
    allowlist: Mapping[str, Any],
) -> list[dict[str, Any]]:
    normalized_allowlist = validate_db2_field_allowlist(allowlist)
    result: dict[str, dict[str, Any]] = {}
    for raw_query in normalized_allowlist["rootQueries"]:
        values = targets.get(str(raw_query["targetKey"]), [])
        if values is None:
            continue
        if not isinstance(values, list):
            raise LimitedDb2Error(f"DB2 target list is invalid: {raw_query['targetKey']}")
        allow_zero = (
            str(raw_query.get("table")) == "ItemCreationContext"
            and str(raw_query.get("filterField")) == "ItemContext"
        )
        for value in sorted(
            {
                _target_value(
                    item,
                    raw_query["targetKey"],
                    allow_zero=allow_zero,
                )
                for item in values
            },
            key=int,
        ):
            row = _query_plan_row(
                table=str(raw_query["table"]),
                filter_field=str(raw_query["filterField"]),
                target_value=value,
                target_kind=str(raw_query["targetKind"]),
                allowlist=normalized_allowlist,
            )
            result[row["requestKey"]] = row
    return list(
        sorted(
            result.values(),
            key=lambda row: (
                str(row["table"]),
                str(row["filterField"]),
                int(row["targetValue"]),
                str(row["requestKey"]),
            ),
        )
    )


def expand_bounded_db2_query_plan(
    plan: list[Mapping[str, Any]],
    *,
    captured_rows: Mapping[str, list[Mapping[str, Any]]],
    allowlist: Mapping[str, Any],
) -> list[dict[str, Any]]:
    normalized_allowlist = validate_db2_field_allowlist(allowlist)
    result = {str(row["requestKey"]): dict(row) for row in plan}
    for relation in normalized_allowlist["foreignKeyQueries"]:
        from_table = str(relation["fromTable"])
        to_table = str(relation["toTable"])
        from_field = str(relation["fromField"])
        when = relation.get("when") or {}
        for raw_row in captured_rows.get(from_table, []):
            if not isinstance(raw_row, Mapping):
                raise LimitedDb2Error(f"captured DB2 row is invalid: {from_table}")
            if any(raw_row.get(str(field)) != value for field, value in when.items()):
                continue
            value = raw_row.get(from_field)
            if value in (None, "", 0, "0"):
                continue
            normalized_value = _id(value, f"{from_table}.{from_field}")
            row = _query_plan_row(
                table=to_table,
                filter_field=str(relation["toFilterField"]),
                target_value=normalized_value,
                target_kind="allowlisted_foreign_key",
                allowlist=normalized_allowlist,
            )
            result[row["requestKey"]] = row
    return list(
        sorted(
            result.values(),
            key=lambda row: (
                str(row["table"]),
                str(row["filterField"]),
                int(row["targetValue"]),
                str(row["requestKey"]),
            ),
        )
    )


def project_db2_row(
    *,
    table: str,
    row: Mapping[str, Any],
    allowlist: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_allowlist = validate_db2_field_allowlist(allowlist)
    if table not in normalized_allowlist["tables"]:
        raise LimitedDb2Error(f"DB2 table is not allowlisted: {table}")
    if not isinstance(row, Mapping):
        raise LimitedDb2Error(f"DB2 row is not an object: {table}")
    fields = normalized_allowlist["tables"][table]["fields"]
    return {field: row[field] for field in fields if field in row}


def _capture_timestamp(value: str | None) -> str:
    raw = value or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise LimitedDb2Error("capturedAt must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _field_coverage(
    rows: list[Mapping[str, Any]],
    fields: list[str],
) -> dict[str, dict[str, int]]:
    return {
        field: {
            "presentRows": sum(1 for row in rows if field in row),
            "missingRows": sum(1 for row in rows if field not in row),
        }
        for field in fields
    }


def _page_request_key(request: Mapping[str, Any], page: int) -> str:
    return canonical_json_sha256(
        {
            "requestKey": request["requestKey"],
            "page": page,
            "query": request["query"],
        }
    )


def _capture_request_pages(
    *,
    request: Mapping[str, Any],
    reader: Any,
    allowlist: Mapping[str, Any],
    captured_at: str,
) -> dict[str, Any]:
    """Fetch and validate every page for one exact request.

    This helper has no filesystem side effects.  Keeping network I/O separate
    from response persistence lets the caller use a small bounded worker pool
    while retaining deterministic, audited response files and fail-closed
    behavior.
    """

    normalized_allowlist = validate_db2_field_allowlist(allowlist)
    table = str(request.get("table") or "")
    filter_field = str(request.get("filterField") or "")
    if table not in normalized_allowlist["tables"]:
        raise LimitedDb2Error(f"DB2 table is not allowlisted: {table}")
    if filter_field not in normalized_allowlist["tables"][table]["filterFields"]:
        raise LimitedDb2Error(
            f"DB2 filter field is not allowlisted: {table}.{filter_field}"
        )
    if request.get("operator") != "exact":
        raise LimitedDb2Error("DB2 request operator must be exact")
    if "csv" in str(request.get("url") or "").casefold():
        raise LimitedDb2Error("DB2 CSV transport is not allowed")

    all_projected_rows: list[dict[str, Any]] = []
    response_records: list[dict[str, Any]] = []
    page = 1
    last_page = 1
    total = None
    while page <= last_page:
        try:
            response = reader.get(request, page=page)
        except Exception as error:
            raise LimitedDb2Error(
                "S2_LIMITED_DB2_REQUEST_FAILED: "
                f"{table}.{filter_field}={request['targetValue']}: {error}"
            ) from error
        if not isinstance(response, Mapping):
            raise LimitedDb2Error(
                "S2_LIMITED_DB2_RESPONSE_INVALID: response must be an object"
            )
        payload = response.get("payload")
        if not isinstance(payload, Mapping) or not isinstance(payload.get("data"), list):
            raise LimitedDb2Error(
                f"S2_LIMITED_DB2_RESPONSE_INVALID: {table} page {page} data is missing"
            )
        raw_total = payload.get("total")
        raw_last_page = payload.get("last_page", payload.get("pageCount", 1))
        if (
            not isinstance(raw_total, int)
            or isinstance(raw_total, bool)
            or raw_total < 0
            or not isinstance(raw_last_page, int)
            or isinstance(raw_last_page, bool)
            or raw_last_page < 1
            or raw_last_page > 100
        ):
            raise LimitedDb2Error(
                f"S2_LIMITED_DB2_RESPONSE_INVALID: {table} pagination is invalid"
            )
        if total is None:
            total = raw_total
            last_page = raw_last_page
        elif total != raw_total or last_page != raw_last_page:
            raise LimitedDb2Error(
                f"S2_LIMITED_DB2_RESPONSE_INVALID: {table} pagination drifted"
            )
        if total > 5000:
            raise LimitedDb2Error(
                f"S2_LIMITED_DB2_RESPONSE_UNBOUNDED: {table} exact filter returned too many rows"
            )

        projected_rows = []
        for raw_row in payload["data"]:
            if not isinstance(raw_row, Mapping):
                raise LimitedDb2Error(
                    f"S2_LIMITED_DB2_RESPONSE_INVALID: {table} row is not an object"
                )
            projected = project_db2_row(
                table=table,
                row=raw_row,
                allowlist=normalized_allowlist,
            )
            if filter_field not in projected:
                raise LimitedDb2Error(
                    f"S2_LIMITED_DB2_RESPONSE_INVALID: {table} row misses {filter_field}"
                )
            projected_rows.append(projected)
        all_projected_rows.extend(projected_rows)

        response_hash = str(response.get("bodySha256") or "")
        if not re.fullmatch(r"[0-9a-f]{64}", response_hash):
            raise LimitedDb2Error(
                f"S2_LIMITED_DB2_RESPONSE_INVALID: {table} body hash is invalid"
            )
        response_bytes = response.get("bodyBytes")
        if (
            not isinstance(response_bytes, int)
            or isinstance(response_bytes, bool)
            or response_bytes < 0
        ):
            raise LimitedDb2Error(
                f"S2_LIMITED_DB2_RESPONSE_INVALID: {table} body size is invalid"
            )

        response_query = {
            **dict(request["query"]),
            **({"page": page} if page > 1 else {}),
        }
        response_records.append(
            {
                "schemaRevision": "s2-limited-db2-response-v1",
                "adapterRevision": CAPTURE_ADAPTER_REVISION,
                "allowlistRevision": normalized_allowlist["schemaRevision"],
                "capturedAt": captured_at,
                "table": table,
                "filterField": filter_field,
                "targetValue": request["targetValue"],
                "targetKind": request["targetKind"],
                "operator": "exact",
                "query": response_query,
                "page": page,
                "lastPage": last_page,
                "total": total,
                "sourceUrl": str(response.get("url") or request["url"]),
                "bodySha256": response_hash,
                "bodyBytes": response_bytes,
                "fields": list(request["fields"]),
                "fieldCoverage": _field_coverage(projected_rows, request["fields"]),
                "rows": projected_rows,
            }
        )
        page += 1

    return {
        "request": dict(request),
        "rows": all_projected_rows,
        "responseRecords": response_records,
    }


def capture_bounded_db2_evidence(
    *,
    plan: list[Mapping[str, Any]],
    output_root: Path,
    reader: Any,
    allowlist: Mapping[str, Any],
    captured_at: str | None = None,
    workers: int = 1,
) -> dict[str, Any]:
    """Capture exact-filtered DB2 rows and expand only allowlisted joins."""

    normalized_allowlist = validate_db2_field_allowlist(allowlist)
    if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
        raise LimitedDb2Error("workers must be a positive integer")
    if not callable(getattr(reader, "get", None)):
        raise LimitedDb2Error("DB2 reader must provide get()")
    output_root = Path(output_root).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    if any(output_root.iterdir()):
        raise LimitedDb2Error("DB2 output root must be empty")
    captured_at = _capture_timestamp(captured_at)

    pending = {
        str(row["requestKey"]): dict(row)
        for row in plan
    }
    processed: set[str] = set()
    captured_rows: dict[str, list[dict[str, Any]]] = {}
    entries: list[dict[str, Any]] = []
    response_index = 0

    try:
        while pending:
            batch_keys = [
                key for key in sorted(pending)
                if key not in processed
            ][:workers]
            if not batch_keys:
                pending = {
                    key: value
                    for key, value in pending.items()
                    if key not in processed
                }
                continue
            batch = [pending.pop(key) for key in batch_keys]
            with ThreadPoolExecutor(max_workers=min(workers, len(batch))) as pool:
                futures = [
                    pool.submit(
                        _capture_request_pages,
                        request=request,
                        reader=reader,
                        allowlist=normalized_allowlist,
                        captured_at=captured_at,
                    )
                    for request in batch
                ]
                results = [future.result() for future in futures]

            # Persist a completed batch in request-key order.  Network
            # completion order never affects evidence paths or manifest order.
            results.sort(key=lambda result: str(result["request"]["requestKey"]))
            for result in results:
                request = result["request"]
                table = str(request["table"])
                for response_record in result["responseRecords"]:
                    response_index += 1
                    response_path = Path("responses") / f"{response_index:06d}.json"
                    response_record = {
                        **response_record,
                        "responsePath": str(response_path),
                    }
                    destination = output_root / response_path
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_text(
                        json.dumps(
                            response_record,
                            ensure_ascii=False,
                            indent=2,
                            sort_keys=True,
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                    entries.append(
                        {
                            "requestKey": _page_request_key(
                                request, response_record["page"]
                            ),
                            "parentRequestKey": request["requestKey"],
                            "table": table,
                            "filterField": request["filterField"],
                            "targetValue": request["targetValue"],
                            "targetKind": request["targetKind"],
                            "operator": "exact",
                            "query": response_record["query"],
                            "responsePath": str(response_path),
                            "sourceUrl": response_record["sourceUrl"],
                            "bodySha256": response_record["bodySha256"],
                            "bodyBytes": response_record["bodyBytes"],
                            "rowCount": len(response_record["rows"]),
                            "total": response_record["total"],
                            "page": response_record["page"],
                            "lastPage": response_record["lastPage"],
                        }
                    )

                captured_rows.setdefault(table, [])
                existing_rows = {
                    canonical_json_sha256(row)
                    for row in captured_rows[table]
                }
                for row in result["rows"]:
                    row_hash = canonical_json_sha256(row)
                    if row_hash not in existing_rows:
                        captured_rows[table].append(row)
                        existing_rows.add(row_hash)
                processed.add(str(request["requestKey"]))

            expanded = expand_bounded_db2_query_plan(
                list(pending.values()) + batch,
                captured_rows=captured_rows,
                allowlist=normalized_allowlist,
            )
            for expanded_request in expanded:
                expanded_key = str(expanded_request["requestKey"])
                if expanded_key not in processed:
                    pending[expanded_key] = expanded_request

        entries.sort(key=lambda row: row["requestKey"])
        manifest = {
            "schemaRevision": "s2-limited-db2-capture-manifest-v1",
            "adapterRevision": CAPTURE_ADAPTER_REVISION,
            "allowlistRevision": normalized_allowlist["schemaRevision"],
            "seasonKey": normalized_allowlist["seasonKey"],
            "clientBuild": normalized_allowlist["clientBuild"],
            "status": "captured",
            "capturedAt": captured_at,
            "authority": normalized_allowlist["authority"],
            "rawDb2Persisted": False,
            "requestCount": len(entries),
            "responseCount": len(entries),
            "tables": sorted({row["table"] for row in entries}),
            "entries": entries,
        }
        (output_root / "capture-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return manifest
    except Exception as error:
        if isinstance(error, LimitedDb2Error):
            message = str(error)
        else:
            message = f"S2_LIMITED_DB2_CAPTURE_FAILED: {error}"
        failure = {
            "schemaRevision": "s2-limited-db2-capture-failure-v1",
            "seasonKey": normalized_allowlist["seasonKey"],
            "clientBuild": normalized_allowlist["clientBuild"],
            "status": "blocked",
            "errorCode": (
                "S2_LIMITED_DB2_REQUEST_FAILED"
                if "S2_LIMITED_DB2_REQUEST_FAILED" in message
                else "S2_LIMITED_DB2_CAPTURE_FAILED"
            ),
            "message": message,
            "requestCountBeforeFailure": len(entries),
        }
        (output_root / "capture-failure.json").write_text(
            json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        manifest_path = output_root / "capture-manifest.json"
        if manifest_path.exists():
            manifest_path.unlink()
        raise LimitedDb2Error(message) from error


__all__ = [
    "LimitedDb2Error",
    "CAPTURE_ADAPTER_REVISION",
    "SCHEMA_REVISION",
    "build_bounded_db2_query_plan",
    "canonical_json_sha256",
    "capture_bounded_db2_evidence",
    "collect_s2_official_db2_targets",
    "expand_bounded_db2_query_plan",
    "project_db2_row",
    "validate_db2_field_allowlist",
]
