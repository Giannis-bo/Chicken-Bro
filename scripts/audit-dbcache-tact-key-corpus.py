#!/usr/bin/env python3

import argparse
import csv
import hashlib
import importlib.util
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


MODULE_PATH = Path(__file__).with_name(
    "build-dbcache-tact-key-coverage-audit.py"
)
MODULE_SPEC = importlib.util.spec_from_file_location(
    "dbcache_tact_key_coverage",
    MODULE_PATH,
)
DB_CACHE_AUDIT = importlib.util.module_from_spec(MODULE_SPEC)
assert MODULE_SPEC.loader is not None
MODULE_SPEC.loader.exec_module(DB_CACHE_AUDIT)

ALLOWED_LIST_HOST = "www.raidbots.com"
ALLOWED_CACHE_HOST = "storage.googleapis.com"
ALLOWED_CACHE_PREFIXES = (
    "/raidbots-static/",
    "/raidbots-dbcache-temp/",
)
MAX_LIST_BYTES = 2 * 1024 * 1024
MAX_CACHE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_CACHE_BYTES = 512 * 1024 * 1024


class CorpusResourceBudgetExceeded(ValueError):
    pass


def _sha256(payload):
    return hashlib.sha256(payload).hexdigest()


def _validate_https_url(url, *, host, path_prefixes=None):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != host:
        raise ValueError(f"unexpected HTTPS source URL: {url}")
    decoded_path = urllib.parse.unquote(parsed.path)
    if path_prefixes and not any(
        decoded_path.startswith(prefix) for prefix in path_prefixes
    ):
        raise ValueError(f"unexpected source path: {url}")


def fetch_bytes(url, max_bytes, timeout=60):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "wow-mini-program-goal-audit/1"},
    )
    last_error = None
    for _attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                content_length = response.headers.get("Content-Length")
                if (
                    content_length is not None
                    and int(content_length) > max_bytes
                ):
                    raise ValueError(
                        f"response exceeds byte limit before read: {url}"
                    )
                payload = response.read(max_bytes + 1)
                if len(payload) > max_bytes:
                    raise ValueError(f"response exceeds byte limit: {url}")
                return payload
        except (
            TimeoutError,
            socket.timeout,
            urllib.error.URLError,
        ) as error:
            last_error = error
    raise RuntimeError(f"failed to fetch source after retries: {url}") from last_error


def _load_target_rows(static_coverage_audit_path, expected_build):
    path = Path(static_coverage_audit_path)
    static_audit = json.loads(path.read_text(encoding="utf-8"))
    if not str(static_audit.get("build", "")).endswith(
        f".{expected_build}"
    ):
        raise ValueError("static coverage audit build does not match")
    target_rows = static_audit.get("coverage", {}).get("targetKeys")
    if not isinstance(target_rows, list) or not target_rows:
        raise ValueError("static coverage audit has no target keys")
    result = []
    for row in target_rows:
        tact_key_id = str(row.get("tactKeyId") or "").lower()
        blte_key_id = DB_CACHE_AUDIT._wdc5_to_blte_key_id(tact_key_id)
        record_count = row.get("recordCount")
        if not isinstance(record_count, int) or record_count < 1:
            raise ValueError(f"invalid target record count: {tact_key_id}")
        result.append(
            {
                "tactKeyId": tact_key_id,
                "blteKeyId": blte_key_id,
                "recordCount": record_count,
                "tables": sorted(set(row.get("tables") or [])),
            }
        )
    return result


def _load_base_key_state(tact_key_csv_path, tact_key_lookup_csv_path):
    key_material_record_ids = set()
    with Path(tact_key_csv_path).open(
        encoding="utf-8",
        newline="",
    ) as handle:
        for row in csv.DictReader(handle):
            record_id = int(row["id"])
            values = [int(row[f"key_{index}"]) for index in range(1, 17)]
            if record_id in key_material_record_ids:
                raise ValueError(f"duplicate base TactKey record ID: {record_id}")
            if not all(0 <= value <= 255 for value in values):
                raise ValueError(
                    f"invalid base TactKey byte for record ID: {record_id}"
                )
            key_material_record_ids.add(record_id)

    lookup_by_record_id = {}
    with Path(tact_key_lookup_csv_path).open(
        encoding="utf-8",
        newline="",
    ) as handle:
        for row in csv.DictReader(handle):
            record_id = int(row["id"])
            values = [
                int(row[f"key_name_{index}"]) for index in range(1, 9)
            ]
            if record_id in lookup_by_record_id:
                raise ValueError(
                    f"duplicate base TactKeyLookup record ID: {record_id}"
                )
            if not all(0 <= value <= 255 for value in values):
                raise ValueError(
                    "invalid base TactKeyLookup byte for record ID: "
                    f"{record_id}"
                )
            lookup_by_record_id[record_id] = bytes(values).hex()
    return key_material_record_ids, lookup_by_record_id


def build_corpus_audit(
    *,
    list_payload,
    list_url,
    list_output_path,
    static_coverage_audit_path,
    expected_build,
    expected_version,
    expected_verified,
    max_files,
    max_total_cache_bytes=MAX_TOTAL_CACHE_BYTES,
    cache_fetcher,
    base_key_material_record_ids=None,
    base_lookup_by_record_id=None,
    base_tact_key_csv_path=None,
    base_tact_key_lookup_csv_path=None,
):
    _validate_https_url(list_url, host=ALLOWED_LIST_HOST)
    source_list = json.loads(list_payload)
    descriptors = source_list.get("data")
    if not isinstance(descriptors, list):
        raise ValueError("DBCache list response has no data list")
    selected = []
    seen_urls = set()
    for descriptor in descriptors:
        if (
            descriptor.get("build") != expected_build
            or descriptor.get("version") != expected_version
            or descriptor.get("verified") is not expected_verified
        ):
            continue
        url = str(descriptor.get("url") or "")
        _validate_https_url(
            url,
            host=ALLOWED_CACHE_HOST,
            path_prefixes=ALLOWED_CACHE_PREFIXES,
        )
        if url in seen_urls:
            raise ValueError(f"duplicate DBCache URL in source list: {url}")
        seen_urls.add(url)
        selected.append(descriptor)
        if len(selected) >= max_files:
            break
    if not selected:
        raise ValueError("DBCache list has no selected exact-build cache")

    target_rows = _load_target_rows(
        static_coverage_audit_path,
        expected_build,
    )
    target_blte_ids = {row["blteKeyId"] for row in target_rows}
    cache_audits = []
    union_present = set()
    total_cache_bytes = 0
    failed_count = 0
    broadcast_text_entry_count = 0
    broadcast_text_tact_key_entry_count = 0
    resource_budget_exceeded = False
    for index, descriptor in enumerate(selected, start=1):
        url = descriptor["url"]
        try:
            remaining_bytes = max_total_cache_bytes - total_cache_bytes
            if resource_budget_exceeded or remaining_bytes <= 0:
                raise CorpusResourceBudgetExceeded(
                    "DBCache corpus total byte limit exhausted"
                )
            payload = cache_fetcher(
                url,
                min(MAX_CACHE_BYTES, remaining_bytes),
            )
            if len(payload) > remaining_bytes:
                raise CorpusResourceBudgetExceeded(
                    "DBCache corpus total byte limit exceeded"
                )
            scan = DB_CACHE_AUDIT.scan_xfth_target_keys(
                payload,
                expected_build=expected_build,
                target_blte_key_ids=target_blte_ids,
                base_key_material_record_ids=base_key_material_record_ids,
                base_lookup_by_record_id=base_lookup_by_record_id,
            )
            present = set(scan["presentTargetBlteKeyIds"])
            union_present.update(present)
            total_cache_bytes += len(payload)
            broadcast_text_entry_count += scan[
                "broadcastTextEntryCount"
            ]
            broadcast_text_tact_key_entry_count += scan[
                "broadcastTextTactKeyEntryCount"
            ]
            cache_audits.append(
                {
                    "index": index,
                    "status": "verified",
                    "url": url,
                    "created": descriptor.get("created"),
                    "declaredEntries": descriptor.get("entries"),
                    "declaredPushIds": descriptor.get("pushIds"),
                    "bytes": len(payload),
                    "sha256": _sha256(payload),
                    "header": scan["header"],
                    "targetTableEntryCount": scan[
                        "targetTableEntryCount"
                    ],
                    "joinedHotfixKeyCount": scan["joinedHotfixKeyCount"],
                    "broadcastTextEntryCount": scan[
                        "broadcastTextEntryCount"
                    ],
                    "broadcastTextTactKeyEntryCount": scan[
                        "broadcastTextTactKeyEntryCount"
                    ],
                    "availableKeyIdentityCount": scan[
                        "availableKeyIdentityCount"
                    ],
                    "presentTargetBlteKeyIds": sorted(present),
                    "rawPersistedAfterAudit": False,
                }
            )
        except Exception as error:
            if isinstance(error, CorpusResourceBudgetExceeded):
                resource_budget_exceeded = True
            failed_count += 1
            cache_audits.append(
                {
                    "index": index,
                    "status": "failed",
                    "url": url,
                    "created": descriptor.get("created"),
                    "reasonCode": type(error).__name__,
                    "rawPersistedAfterAudit": False,
                }
            )
        if index % 10 == 0 or index == len(selected):
            print(
                json.dumps(
                    {
                        "processed": index,
                        "selected": len(selected),
                        "failed": failed_count,
                        "unionTargetKeyCount": len(union_present),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )

    audited_targets = []
    covered_record_count = 0
    for row in target_rows:
        present = row["blteKeyId"] in union_present
        audited_targets.append(
            {
                **row,
                "presentInCorpusUnion": present,
            }
        )
        if present:
            covered_record_count += row["recordCount"]
    target_record_count = sum(row["recordCount"] for row in target_rows)
    missing_key_count = len(target_rows) - len(union_present)
    blockers = []
    if failed_count:
        blockers.append("DBCACHE_CORPUS_FETCH_INCOMPLETE")
    if resource_budget_exceeded:
        blockers.append("DBCACHE_CORPUS_RESOURCE_BUDGET_EXCEEDED")
    if missing_key_count:
        blockers.append("DBCACHE_CORPUS_TACT_KEYS_INCOMPLETE")
    status = (
        "complete"
        if not blockers
        else ("partial" if union_present else "blocked")
    )
    static_path = Path(static_coverage_audit_path)
    static_payload = static_path.read_bytes()
    input_evidence = {
        "staticCoverageAudit": {
            "path": static_path.name,
            "bytes": len(static_payload),
            "sha256": _sha256(static_payload),
        }
    }
    for input_name, input_path in (
        ("baseTactKeyCsv", base_tact_key_csv_path),
        ("baseTactKeyLookupCsv", base_tact_key_lookup_csv_path),
    ):
        if input_path is None:
            continue
        resolved_input_path = Path(input_path)
        input_payload = resolved_input_path.read_bytes()
        input_evidence[input_name] = {
            "path": resolved_input_path.name,
            "bytes": len(input_payload),
            "sha256": _sha256(input_payload),
            "keyMaterialEmittedByAudit": False,
        }
    return {
        "schemaVersion": 1,
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "build": f"12.0.7.{expected_build}",
        "authority": {
            "type": (
                "verified_third_party_client_hotfix_cache_corpus"
                if expected_verified
                else "unverified_opt_in_client_hotfix_cache_corpus"
            ),
            "provider": "Raidbots",
            "collector": "Raidbots" if expected_verified else "Raider.IO opt-in users",
            "upstreamBytes": (
                "Blizzard server-delivered World of Warcraft client hotfix caches"
            ),
            "collectionProvenance": "third_party",
            "mayEstablishOfficialSeasonMembership": False,
            "auditContainsKeyMaterial": False,
            "rawCachesPersistedAfterAudit": False,
            "scanMode": (
                "serial_in_memory_tact_key_tables_and_"
                "broadcast_text_optional_data"
            ),
        },
        "sourceList": {
            "path": Path(list_output_path).name,
            "url": list_url,
            "bytes": len(list_payload),
            "sha256": _sha256(list_payload),
            "reportedEntryCount": len(descriptors),
            "selectedExactBuildEntryCount": len(selected),
            "selectionLimit": max_files,
        },
        "inputs": input_evidence,
        "corpus": {
            "summary": {
                "selectedCacheCount": len(selected),
                "fetchedCacheCount": len(selected) - failed_count,
                "failedCacheCount": failed_count,
                "totalFetchedBytes": total_cache_bytes,
                "totalFetchByteLimit": max_total_cache_bytes,
                "broadcastTextEntryCount": broadcast_text_entry_count,
                "broadcastTextTactKeyEntryCount": (
                    broadcast_text_tact_key_entry_count
                ),
                "targetKeyCount": len(target_rows),
                "targetRecordCount": target_record_count,
                "unionAvailableTargetKeyCount": len(union_present),
                "unionMissingTargetKeyCount": missing_key_count,
                "unionCoveredTargetRecordCount": covered_record_count,
                "unionMissingTargetRecordCount": (
                    target_record_count - covered_record_count
                ),
            },
            "targetKeys": audited_targets,
            "cacheAudits": cache_audits,
            "blockers": blockers,
        },
        "conclusion": (
            "the full selected exact-build cache corpus contains every target key"
            if status == "complete"
            else "the full selected exact-build cache corpus does not close every target key"
        ),
        "productionMutation": False,
        "releasePointerMutation": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list-url", required=True)
    parser.add_argument("--static-coverage-audit", required=True, type=Path)
    parser.add_argument("--base-tact-key-csv", required=True, type=Path)
    parser.add_argument(
        "--base-tact-key-lookup-csv",
        required=True,
        type=Path,
    )
    parser.add_argument("--expected-build", required=True, type=int)
    parser.add_argument("--expected-version", default="retail")
    parser.add_argument(
        "--expected-verified",
        required=True,
        choices=("true", "false"),
    )
    parser.add_argument("--max-files", type=int, default=100)
    parser.add_argument(
        "--max-total-cache-bytes",
        type=int,
        default=MAX_TOTAL_CACHE_BYTES,
    )
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--list-output", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.max_files < 1 or args.max_files > 100:
        parser.error("--max-files must be between 1 and 100")
    if not 1 <= args.max_total_cache_bytes <= MAX_TOTAL_CACHE_BYTES:
        parser.error(
            "--max-total-cache-bytes must be between 1 and "
            f"{MAX_TOTAL_CACHE_BYTES}"
        )
    _validate_https_url(args.list_url, host=ALLOWED_LIST_HOST)
    list_payload = fetch_bytes(
        args.list_url,
        MAX_LIST_BYTES,
        timeout=args.timeout,
    )
    args.list_output.write_bytes(list_payload)
    (
        base_key_material_record_ids,
        base_lookup_by_record_id,
    ) = _load_base_key_state(
        args.base_tact_key_csv,
        args.base_tact_key_lookup_csv,
    )
    audit = build_corpus_audit(
        list_payload=list_payload,
        list_url=args.list_url,
        list_output_path=args.list_output,
        static_coverage_audit_path=args.static_coverage_audit,
        expected_build=args.expected_build,
        expected_version=args.expected_version,
        expected_verified=args.expected_verified == "true",
        max_files=args.max_files,
        max_total_cache_bytes=args.max_total_cache_bytes,
        base_key_material_record_ids=base_key_material_record_ids,
        base_lookup_by_record_id=base_lookup_by_record_id,
        base_tact_key_csv_path=args.base_tact_key_csv,
        base_tact_key_lookup_csv_path=args.base_tact_key_lookup_csv,
        cache_fetcher=lambda url, max_bytes: fetch_bytes(
            url,
            max_bytes,
            timeout=args.timeout,
        ),
    )
    args.output.write_text(
        json.dumps(audit, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(audit["corpus"]["summary"], sort_keys=True))
    raise SystemExit(0 if audit["status"] == "complete" else 2)


if __name__ == "__main__":
    main()
