#!/usr/bin/env python3
"""Build a read-only, secret-safe inventory of the known Chickenbro cloud host."""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence


ALLOWED_STATUS = frozenset({"reachable", "partial", "unreachable"})
SECRET_FIELD_NAMES = frozenset(
    {
        "authorization",
        "cookie",
        "credential",
        "credentials",
        "databaseurl",
        "dsn",
        "environment",
        "openid",
        "password",
        "pgpass",
        "privatekey",
        "secret",
        "sessionkey",
        "token",
        "unionid",
    }
)
SNAPSHOT_FIELDS = frozenset(
    {
        "status",
        "observedAt",
        "host",
        "targetIdentity",
        "rootFilesystem",
        "rootFreeBytes",
        "currentDatabaseBytes",
        "databases",
        "units",
        "listeners",
        "directories",
        "identities",
        "probeErrors",
    }
)
EXPECTED_TARGET_IDENTITY = {
    "provider": "tencent_cvm",
    "instanceId": "ins-93tgv1rb",
    "region": "ap-shanghai",
    "zone": "ap-shanghai-2",
    "publicAddress": "124.223.51.33",
    "sshTarget": "wow-lighthouse",
    "refreshRequiredBeforeApply": True,
}
DIRECTORY_PATHS = (
    "/opt/wow-mini-program",
    "/opt/wow-simc",
    "/opt/wow-v2-staging",
    "/var/backups/wow-mini-program",
    "/var/backups/wow-v2",
    "/var/lib/postgresql",
    "/var/lib/wow-backend",
    "/var/www/chickenbro-web",
    "/var/www/chickenbro-web-candidate",
)
IDENTITY_FILES = {
    "deployRevision": "/opt/wow-mini-program/.deploy-revision",
    "simcCommit": "/opt/wow-simc/.commit",
}
SAFE_NAME = re.compile(r"^[A-Za-z0-9_.@+-]+$")
SAFE_PATH = re.compile(r"^/[A-Za-z0-9_./+-]*$")
SAFE_ADDRESS = re.compile(r"^[A-Za-z0-9.*:%_-]+$")
SAFE_IDENTITY = re.compile(r"^[A-Za-z0-9._+@-]{1,160}$")
RFC3339_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")


def _normalized_field_name(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _reject_secret_fields(value: object, location: str = "snapshot") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if _normalized_field_name(key) in SECRET_FIELD_NAMES:
                raise ValueError(f"secret-bearing field rejected at {location}.{key}")
            _reject_secret_fields(nested, f"{location}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _reject_secret_fields(nested, f"{location}[{index}]")
    elif isinstance(value, str):
        if re.search(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s/@:]+:[^\s/@]+@", value):
            raise ValueError(f"secret-bearing field value rejected at {location}")
        if "-----BEGIN " in value or re.search(r"(?i)^Bearer\s+\S+", value):
            raise ValueError(f"secret-bearing field value rejected at {location}")


def _nonnegative_integer(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a non-negative integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must be a non-negative integer") from error
    if parsed < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return parsed


def _safe_string(value: object, field: str, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f"{field} contains an unsupported value")
    return value


def _normalize_rows(
    rows: object,
    *,
    field: str,
    required_fields: Sequence[str],
    integer_fields: Sequence[str] = (),
    sort_key,
) -> list[dict[str, object]]:
    if rows is None:
        return []
    if not isinstance(rows, list):
        raise ValueError(f"{field} must be a list")
    normalized: list[dict[str, object]] = []
    expected = set(required_fields)
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping) or set(row) != expected:
            raise ValueError(f"{field}[{index}] must contain exactly {sorted(expected)}")
        current: dict[str, object] = {}
        for key in required_fields:
            value = row[key]
            if key in integer_fields:
                current[key] = _nonnegative_integer(value, f"{field}[{index}].{key}")
            else:
                current[key] = value
        normalized.append(current)
    return sorted(normalized, key=sort_key)


def capacity_gate(inventory: Mapping[str, object]) -> str:
    if inventory.get("status") == "unreachable":
        return "unverified_unreachable"
    root_free_bytes = _nonnegative_integer(inventory.get("rootFreeBytes", 0), "rootFreeBytes")
    database_bytes = _nonnegative_integer(
        inventory.get("currentDatabaseBytes", 0), "currentDatabaseBytes"
    )
    if root_free_bytes and database_bytes and root_free_bytes <= database_bytes:
        return "blocked_until_whitelist_recovery_and_exact_capacity_cleanup_or_storage_expansion"
    return "capacity_preflight_required"


def build_inventory(snapshot: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(snapshot, Mapping):
        raise ValueError("snapshot must be a mapping")
    _reject_secret_fields(snapshot)
    unknown_fields = set(snapshot) - SNAPSHOT_FIELDS
    if unknown_fields:
        raise ValueError(f"unsupported snapshot fields: {sorted(unknown_fields)}")

    status = snapshot.get("status", "partial")
    if status not in ALLOWED_STATUS:
        raise ValueError(f"unsupported inventory status: {status}")
    observed_at = snapshot.get("observedAt", "")
    if not isinstance(observed_at, str) or not RFC3339_UTC.fullmatch(observed_at):
        raise ValueError("observedAt must be an RFC3339 UTC timestamp")
    host = _safe_string(snapshot.get("host", "wow-lighthouse"), "host", SAFE_NAME)
    target_identity = snapshot.get("targetIdentity")
    if target_identity is not None:
        if not isinstance(target_identity, Mapping) or dict(target_identity) != EXPECTED_TARGET_IDENTITY:
            raise ValueError("target identity does not match the reviewed Tencent CVM")
        target_identity = dict(target_identity)

    raw_filesystem = snapshot.get("rootFilesystem") or {
        "path": "/",
        "sizeBytes": 0,
        "usedBytes": 0,
        "freeBytes": snapshot.get("rootFreeBytes", 0),
    }
    if not isinstance(raw_filesystem, Mapping) or set(raw_filesystem) != {
        "path",
        "sizeBytes",
        "usedBytes",
        "freeBytes",
    }:
        raise ValueError("rootFilesystem must contain path, sizeBytes, usedBytes, and freeBytes")
    root_filesystem = {
        "path": _safe_string(raw_filesystem["path"], "rootFilesystem.path", SAFE_PATH),
        "sizeBytes": _nonnegative_integer(raw_filesystem["sizeBytes"], "rootFilesystem.sizeBytes"),
        "usedBytes": _nonnegative_integer(raw_filesystem["usedBytes"], "rootFilesystem.usedBytes"),
        "freeBytes": _nonnegative_integer(raw_filesystem["freeBytes"], "rootFilesystem.freeBytes"),
    }
    root_free_bytes = _nonnegative_integer(
        snapshot.get("rootFreeBytes", root_filesystem["freeBytes"]), "rootFreeBytes"
    )
    if root_free_bytes != root_filesystem["freeBytes"]:
        raise ValueError("rootFreeBytes must equal rootFilesystem.freeBytes")
    current_database_bytes = _nonnegative_integer(
        snapshot.get("currentDatabaseBytes", 0), "currentDatabaseBytes"
    )

    databases = _normalize_rows(
        snapshot.get("databases"),
        field="databases",
        required_fields=("name", "sizeBytes", "connections"),
        integer_fields=("sizeBytes", "connections"),
        sort_key=lambda row: str(row["name"]),
    )
    for index, row in enumerate(databases):
        row["name"] = _safe_string(row["name"], f"databases[{index}].name", SAFE_NAME)

    units = _normalize_rows(
        snapshot.get("units"),
        field="units",
        required_fields=("name", "loadState", "activeState", "unitFileState"),
        sort_key=lambda row: str(row["name"]),
    )
    for index, row in enumerate(units):
        for key in ("name", "loadState", "activeState", "unitFileState"):
            row[key] = _safe_string(row[key], f"units[{index}].{key}", SAFE_NAME)

    listeners = _normalize_rows(
        snapshot.get("listeners"),
        field="listeners",
        required_fields=("address", "port", "processName"),
        integer_fields=("port",),
        sort_key=lambda row: (int(row["port"]), str(row["address"]), str(row["processName"])),
    )
    for index, row in enumerate(listeners):
        row["address"] = _safe_string(row["address"], f"listeners[{index}].address", SAFE_ADDRESS)
        row["processName"] = _safe_string(
            row["processName"], f"listeners[{index}].processName", SAFE_NAME
        )
        if int(row["port"]) > 65535:
            raise ValueError(f"listeners[{index}].port is outside the TCP port range")

    directories = _normalize_rows(
        snapshot.get("directories"),
        field="directories",
        required_fields=("path", "sizeBytes"),
        integer_fields=("sizeBytes",),
        sort_key=lambda row: str(row["path"]),
    )
    for index, row in enumerate(directories):
        row["path"] = _safe_string(row["path"], f"directories[{index}].path", SAFE_PATH)

    identities = _normalize_rows(
        snapshot.get("identities"),
        field="identities",
        required_fields=("name", "value"),
        sort_key=lambda row: str(row["name"]),
    )
    for index, row in enumerate(identities):
        row["name"] = _safe_string(row["name"], f"identities[{index}].name", SAFE_NAME)
        row["value"] = _safe_string(
            row["value"], f"identities[{index}].value", SAFE_IDENTITY
        )

    probe_errors = _normalize_rows(
        snapshot.get("probeErrors"),
        field="probeErrors",
        required_fields=("probe", "errorCode"),
        sort_key=lambda row: (str(row["probe"]), str(row["errorCode"])),
    )
    for index, row in enumerate(probe_errors):
        row["probe"] = _safe_string(row["probe"], f"probeErrors[{index}].probe", SAFE_NAME)
        row["errorCode"] = _safe_string(
            row["errorCode"], f"probeErrors[{index}].errorCode", SAFE_NAME
        )

    inventory: dict[str, object] = {
        "schemaVersion": 1,
        "status": status,
        "observedAt": observed_at,
        "host": host,
        "rootFilesystem": root_filesystem,
        "rootFreeBytes": root_free_bytes,
        "currentDatabaseBytes": current_database_bytes,
        "databases": databases,
        "units": units,
        "listeners": listeners,
        "directories": directories,
        "identities": identities,
        "probeErrors": probe_errors,
    }
    if target_identity is not None:
        inventory = {
            "schemaVersion": inventory["schemaVersion"],
            "status": inventory["status"],
            "observedAt": inventory["observedAt"],
            "host": inventory["host"],
            "targetIdentity": target_identity,
            **{key: value for key, value in inventory.items() if key not in {"schemaVersion", "status", "observedAt", "host"}},
        }
    inventory["capacityGate"] = capacity_gate(inventory)
    return inventory


def _run(command: Sequence[str], *, timeout: int = 20) -> tuple[int, str]:
    try:
        result = subprocess.run(
            list(command),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={"PATH": os.environ.get("PATH", "/usr/sbin:/usr/bin:/sbin:/bin"), "LC_ALL": "C"},
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 127, ""
    return result.returncode, result.stdout


def _error(errors: list[dict[str, str]], probe: str, code: str) -> None:
    errors.append({"probe": probe, "errorCode": code})


def _collect_filesystem(errors: list[dict[str, str]]) -> dict[str, object]:
    returncode, stdout = _run(("df", "-B1", "--output=size,used,avail,target", "/"))
    rows = [line.split() for line in stdout.splitlines()[1:] if line.strip()]
    if returncode != 0 or not rows or len(rows[-1]) != 4:
        _error(errors, "filesystem", "probe_failed")
        return {"path": "/", "sizeBytes": 0, "usedBytes": 0, "freeBytes": 0}
    size, used, free, mount = rows[-1]
    try:
        return {
            "path": mount,
            "sizeBytes": int(size),
            "usedBytes": int(used),
            "freeBytes": int(free),
        }
    except ValueError:
        _error(errors, "filesystem", "invalid_result")
        return {"path": "/", "sizeBytes": 0, "usedBytes": 0, "freeBytes": 0}


def _collect_databases(errors: list[dict[str, str]]) -> list[dict[str, object]]:
    sql = (
        "SELECT d.datname, pg_database_size(d.datname), count(a.pid) "
        "FROM pg_database d LEFT JOIN pg_stat_activity a ON a.datname=d.datname "
        "WHERE NOT d.datistemplate GROUP BY d.datname ORDER BY d.datname"
    )
    returncode, stdout = _run(
        ("sudo", "-n", "-u", "postgres", "psql", "-d", "postgres", "-At", "-F", "\t", "-c", sql)
    )
    if returncode != 0:
        _error(errors, "databases", "probe_failed")
        return []
    databases: list[dict[str, object]] = []
    for line in stdout.splitlines():
        columns = line.split("\t")
        if len(columns) != 3:
            _error(errors, "databases", "invalid_result")
            return []
        try:
            databases.append(
                {"name": columns[0], "sizeBytes": int(columns[1]), "connections": int(columns[2])}
            )
        except ValueError:
            _error(errors, "databases", "invalid_result")
            return []
    return databases


def _collect_units(errors: list[dict[str, str]]) -> list[dict[str, str]]:
    returncode, stdout = _run(
        ("systemctl", "list-unit-files", "wow-*", "--no-legend", "--no-pager")
    )
    if returncode != 0:
        _error(errors, "units", "probe_failed")
        return []
    units: list[dict[str, str]] = []
    for line in stdout.splitlines():
        columns = line.split()
        if not columns or not columns[0].startswith("wow-"):
            continue
        name = columns[0]
        show_code, show_stdout = _run(
            (
                "systemctl",
                "show",
                name,
                "--no-pager",
                "--property=LoadState",
                "--property=ActiveState",
                "--property=UnitFileState",
            )
        )
        if show_code != 0:
            _error(errors, "units", "unit_state_failed")
            continue
        values = {}
        for item in show_stdout.splitlines():
            key, separator, value = item.partition("=")
            if separator and key in {"LoadState", "ActiveState", "UnitFileState"}:
                values[key] = value or "unknown"
        units.append(
            {
                "name": name,
                "loadState": values.get("LoadState", "unknown"),
                "activeState": values.get("ActiveState", "unknown"),
                "unitFileState": values.get("UnitFileState", "unknown"),
            }
        )
    return units


def _split_listener_address(value: str) -> tuple[str, int] | None:
    address, separator, raw_port = value.rpartition(":")
    if not separator:
        return None
    address = address.strip("[]") or "*"
    try:
        return address, int(raw_port)
    except ValueError:
        return None


def _collect_listeners(errors: list[dict[str, str]]) -> list[dict[str, object]]:
    returncode, stdout = _run(("ss", "-H", "-ltnp"))
    if returncode != 0:
        _error(errors, "listeners", "probe_failed")
        return []
    listeners: list[dict[str, object]] = []
    for line in stdout.splitlines():
        columns = line.split(maxsplit=6)
        if len(columns) < 5:
            continue
        parsed = _split_listener_address(columns[3])
        if not parsed:
            continue
        address, port = parsed
        process_name = "unknown"
        if len(columns) == 7:
            match = re.search(r'\(\("([^"\\]+)"', columns[6])
            if match:
                process_name = match.group(1)
        listeners.append({"address": address, "port": port, "processName": process_name})
    return listeners


def _collect_directories(errors: list[dict[str, str]]) -> list[dict[str, object]]:
    directories: list[dict[str, object]] = []
    for directory in DIRECTORY_PATHS:
        if not Path(directory).exists():
            continue
        returncode, stdout = _run(("sudo", "-n", "du", "-sb", "--", directory), timeout=45)
        columns = stdout.split()
        if returncode != 0 or not columns:
            _error(errors, "directories", "path_probe_failed")
            continue
        try:
            directories.append({"path": directory, "sizeBytes": int(columns[0])})
        except ValueError:
            _error(errors, "directories", "invalid_result")
    return directories


def _collect_identities(errors: list[dict[str, str]]) -> list[dict[str, str]]:
    identities: list[dict[str, str]] = []
    for name, filename in IDENTITY_FILES.items():
        path = Path(filename)
        if not path.is_file():
            continue
        try:
            value = path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            _error(errors, "identities", "identity_read_failed")
            continue
        if not SAFE_IDENTITY.fullmatch(value):
            _error(errors, "identities", "identity_rejected")
            continue
        identities.append({"name": name, "value": value})
    return identities


def _collect_target_identity(errors: list[dict[str, str]]) -> dict[str, object] | None:
    endpoints = {
        "instanceId": "http://metadata.tencentyun.com/latest/meta-data/instance-id",
        "region": "http://metadata.tencentyun.com/latest/meta-data/placement/region",
        "zone": "http://metadata.tencentyun.com/latest/meta-data/placement/zone",
    }
    observed: dict[str, object] = {
        "provider": "tencent_cvm",
        "publicAddress": "124.223.51.33",
        "sshTarget": "wow-lighthouse",
        "refreshRequiredBeforeApply": True,
    }
    for field, endpoint in endpoints.items():
        returncode, stdout = _run(("curl", "-fsS", "--max-time", "3", endpoint), timeout=5)
        value = stdout.strip()
        if returncode != 0 or not SAFE_IDENTITY.fullmatch(value):
            _error(errors, "target_identity", f"{field}_probe_failed")
            return None
        observed[field] = value
    if observed != EXPECTED_TARGET_IDENTITY:
        _error(errors, "target_identity", "identity_mismatch")
        return None
    return observed


def collect_snapshot() -> dict[str, object]:
    errors: list[dict[str, str]] = []
    root_filesystem = _collect_filesystem(errors)
    databases = _collect_databases(errors)
    target_identity = _collect_target_identity(errors)
    snapshot: dict[str, object] = {
        "status": "reachable",
        "observedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "host": socket.gethostname().split(".", 1)[0],
        "rootFilesystem": root_filesystem,
        "rootFreeBytes": root_filesystem["freeBytes"],
        "currentDatabaseBytes": sum(int(row["sizeBytes"]) for row in databases),
        "databases": databases,
        "units": _collect_units(errors),
        "listeners": _collect_listeners(errors),
        "directories": _collect_directories(errors),
        "identities": _collect_identities(errors),
        "probeErrors": errors,
    }
    if target_identity is not None:
        snapshot["targetIdentity"] = target_identity
    if errors:
        snapshot["status"] = "partial"
    return build_inventory(snapshot)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", help="required safety acknowledgement")
    parser.add_argument("--output", required=True, help="'-' for stdout or a JSON file path")
    args = parser.parse_args(argv)
    if not args.read_only:
        parser.error("--read-only is required")

    inventory = collect_snapshot()
    payload = json.dumps(inventory, ensure_ascii=True, indent=2) + "\n"
    if args.output == "-":
        print(payload, end="")
    else:
        Path(args.output).write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
