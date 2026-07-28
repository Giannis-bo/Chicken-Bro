#!/usr/bin/env python3
"""Append-only PostgreSQL owner for ResolvedLoadout and SimulationSnapshot."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

try:
    from .gear_resolved_loadout import verify_resolved_loadout
    from .simulation_snapshot import verify_simulation_snapshot
except ImportError:
    from gear_resolved_loadout import verify_resolved_loadout
    from simulation_snapshot import verify_simulation_snapshot


RESULT_IDENTITY_PATTERN = re.compile(r"^simc-result:sha256:[0-9a-f]{64}$")


class SimulationSnapshotIntegrityError(RuntimeError):
    pass


def _text(value: Any) -> str:
    return str(value or "").strip()


def _canonical(value: Any) -> Any:
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    )


def _json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _json_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return _canonical(value)
    return json.loads(value)


def _row_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


class SimulationSnapshotStore:
    """Seal and exactly reload immutable execution inputs and result bindings."""

    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    def connection(self):
        return self._connection_factory()

    @staticmethod
    def _validate_loadout(value: Any) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            raise SimulationSnapshotIntegrityError("ready ResolvedLoadout is required")
        row = _canonical(value)
        issues = verify_resolved_loadout(row)
        if issues:
            raise SimulationSnapshotIntegrityError(
                "ResolvedLoadout integrity check failed: " + ",".join(issues)
            )
        return row

    @staticmethod
    def _validate_snapshot(value: Any) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            raise SimulationSnapshotIntegrityError(
                "ready SimulationSnapshot is required"
            )
        row = _canonical(value)
        if row.get("status") != "ready" or row.get("resultIdentity"):
            raise SimulationSnapshotIntegrityError(
                "only an unexecuted ready SimulationSnapshot may be sealed"
            )
        issues = verify_simulation_snapshot(row)
        if issues:
            raise SimulationSnapshotIntegrityError(
                "SimulationSnapshot integrity check failed: " + ",".join(issues)
            )
        return row

    @staticmethod
    def _load_loadout_with_cursor(cur: Any, key: str) -> dict[str, Any]:
        cur.execute(
            """
            /* simulation_snapshot_loadout_load */
            SELECT
                resolved_loadout_key,
                schema_revision,
                catalog_revision,
                gear_rule_revision,
                exact_registry_revision,
                class_key,
                spec_key,
                loadout_json::text,
                row_hash
            FROM cache.websim_gear_resolved_loadouts
            WHERE resolved_loadout_key = %s
            """,
            (key,),
        )
        stored = cur.fetchone()
        if not stored:
            return {}
        row = _json_value(stored[7])
        if (
            _text(row.get("resolvedLoadoutKey")) != _text(stored[0])
            or _text(row.get("schemaRevision")) != _text(stored[1])
            or _text(row.get("catalogRevision")) != _text(stored[2])
            or _text(row.get("gearRuleRevision")) != _text(stored[3])
            or _text(row.get("exactRegistryRevision")) != _text(stored[4])
            or _text(row.get("eligibilityContext", {}).get("classKey"))
            != _text(stored[5])
            or _text(row.get("eligibilityContext", {}).get("specKey"))
            != _text(stored[6])
            or _text(row.get("rowHash")) != _text(stored[8])
            or verify_resolved_loadout(row)
        ):
            raise SimulationSnapshotIntegrityError(
                "sealed ResolvedLoadout integrity mismatch"
            )
        return row

    @staticmethod
    def _load_snapshot_with_cursor(cur: Any, key: str) -> dict[str, Any]:
        cur.execute(
            """
            /* simulation_snapshot_load */
            SELECT
                simulation_snapshot_key,
                schema_revision,
                resolved_loadout_key,
                talent_profile_key,
                compiler_revision,
                simc_runtime_revision,
                canonical_input_hash,
                catalog_revision,
                gear_rule_revision,
                snapshot_json::text,
                row_hash
            FROM cache.websim_simulation_snapshots
            WHERE simulation_snapshot_key = %s
            """,
            (key,),
        )
        stored = cur.fetchone()
        if not stored:
            return {}
        row = _json_value(stored[9])
        if (
            _text(row.get("simulationSnapshotKey")) != _text(stored[0])
            or _text(row.get("schemaRevision")) != _text(stored[1])
            or _text(row.get("resolvedLoadoutKey")) != _text(stored[2])
            or _text(row.get("talentProfileKey")) != _text(stored[3])
            or _text(row.get("compilerRevision")) != _text(stored[4])
            or _text(row.get("simcRuntimeRevision")) != _text(stored[5])
            or _text(row.get("canonicalInputHash")) != _text(stored[6])
            or _text(row.get("catalogRevision")) != _text(stored[7])
            or _text(row.get("gearRuleRevision")) != _text(stored[8])
            or _text(row.get("rowHash")) != _text(stored[10])
            or verify_simulation_snapshot(row)
        ):
            raise SimulationSnapshotIntegrityError(
                "sealed simulation snapshot integrity mismatch"
            )
        return row

    @staticmethod
    def _load_result_with_cursor(cur: Any, key: str) -> dict[str, Any]:
        cur.execute(
            """
            /* simulation_snapshot_result_load */
            SELECT
                simulation_snapshot_key,
                result_identity,
                result_status,
                result_json::text,
                row_hash
            FROM cache.websim_simulation_snapshot_results
            WHERE simulation_snapshot_key = %s
            """,
            (key,),
        )
        stored = cur.fetchone()
        if not stored:
            return {}
        result = _json_value(stored[3])
        semantics = {
            "simulationSnapshotKey": _text(stored[0]),
            "resultIdentity": _text(stored[1]),
            "status": _text(stored[2]),
            "result": result,
        }
        if (
            _text(result.get("resultIdentity")) != semantics["resultIdentity"]
            or _text(result.get("status")) != semantics["status"]
            or _row_hash(semantics) != _text(stored[4])
        ):
            raise SimulationSnapshotIntegrityError(
                "sealed simulation result integrity mismatch"
            )
        return semantics

    def load_loadout(self, key: str) -> dict[str, Any]:
        with self.connection() as connection:
            with connection.cursor() as cur:
                return self._load_loadout_with_cursor(cur, _text(key))

    def load_snapshot(self, key: str, *, include_result: bool = True) -> dict[str, Any]:
        with self.connection() as connection:
            with connection.cursor() as cur:
                row = self._load_snapshot_with_cursor(cur, _text(key))
                if not row or not include_result:
                    return row
                result = self._load_result_with_cursor(cur, _text(key))
                if not result:
                    return row
                return {
                    **row,
                    "status": "executed",
                    "snapshotRowHash": row["rowHash"],
                    "resultIdentity": result["resultIdentity"],
                    "result": result["result"],
                }

    def seal_loadout(self, value: Any) -> dict[str, Any]:
        row = self._validate_loadout(value)
        eligibility = row["eligibilityContext"]
        params = (
            row["resolvedLoadoutKey"],
            row["schemaRevision"],
            row["catalogRevision"],
            row["gearRuleRevision"],
            row["exactRegistryRevision"],
            _text(eligibility.get("classKey")),
            _text(eligibility.get("specKey")),
            _json(row),
            row["rowHash"],
        )
        with self.connection() as connection:
            with connection.cursor() as cur:
                cur.execute(
                    """
                    /* simulation_snapshot_loadout_insert */
                    INSERT INTO cache.websim_gear_resolved_loadouts (
                        resolved_loadout_key,
                        schema_revision,
                        catalog_revision,
                        gear_rule_revision,
                        exact_registry_revision,
                        class_key,
                        spec_key,
                        loadout_json,
                        row_hash
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    params,
                )
                sealed = self._load_loadout_with_cursor(
                    cur, row["resolvedLoadoutKey"]
                )
                if sealed != row:
                    raise SimulationSnapshotIntegrityError(
                        "sealed ResolvedLoadout identity conflict"
                    )
                return sealed

    def seal_snapshot(self, value: Any) -> dict[str, Any]:
        row = self._validate_snapshot(value)
        params = (
            row["simulationSnapshotKey"],
            row["schemaRevision"],
            row["resolvedLoadoutKey"],
            row["talentProfileKey"],
            row["compilerRevision"],
            row["simcRuntimeRevision"],
            row["canonicalInputHash"],
            row["catalogRevision"],
            row["gearRuleRevision"],
            _json(row),
            row["rowHash"],
        )
        with self.connection() as connection:
            with connection.cursor() as cur:
                if not self._load_loadout_with_cursor(
                    cur, row["resolvedLoadoutKey"]
                ):
                    raise SimulationSnapshotIntegrityError(
                        "sealed ResolvedLoadout is required before snapshot"
                    )
                cur.execute(
                    """
                    /* simulation_snapshot_insert */
                    INSERT INTO cache.websim_simulation_snapshots (
                        simulation_snapshot_key,
                        schema_revision,
                        resolved_loadout_key,
                        talent_profile_key,
                        compiler_revision,
                        simc_runtime_revision,
                        canonical_input_hash,
                        catalog_revision,
                        gear_rule_revision,
                        snapshot_json,
                        row_hash
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    params,
                )
                sealed = self._load_snapshot_with_cursor(
                    cur, row["simulationSnapshotKey"]
                )
                if sealed != row:
                    raise SimulationSnapshotIntegrityError(
                        "sealed simulation snapshot identity conflict"
                    )
                return sealed

    def bind_result(self, snapshot_key: str, result_value: Any) -> dict[str, Any]:
        key = _text(snapshot_key)
        result = _canonical(result_value) if isinstance(result_value, Mapping) else {}
        result_identity = _text(result.get("resultIdentity"))
        status = _text(result.get("status"))
        if (
            not RESULT_IDENTITY_PATTERN.fullmatch(result_identity)
            or status not in {"completed", "failed"}
        ):
            raise SimulationSnapshotIntegrityError(
                "terminal content-addressed SimC result is required"
            )
        semantics = {
            "simulationSnapshotKey": key,
            "resultIdentity": result_identity,
            "status": status,
            "result": result,
        }
        params = (
            key,
            result_identity,
            status,
            _json(result),
            _row_hash(semantics),
        )
        with self.connection() as connection:
            with connection.cursor() as cur:
                snapshot = self._load_snapshot_with_cursor(cur, key)
                if not snapshot:
                    raise SimulationSnapshotIntegrityError(
                        "sealed simulation snapshot is required before result"
                    )
                cur.execute(
                    """
                    /* simulation_snapshot_result_insert */
                    INSERT INTO cache.websim_simulation_snapshot_results (
                        simulation_snapshot_key,
                        result_identity,
                        result_status,
                        result_json,
                        row_hash
                    ) VALUES (%s, %s, %s, %s::jsonb, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    params,
                )
                sealed = self._load_result_with_cursor(cur, key)
                if sealed != semantics:
                    raise SimulationSnapshotIntegrityError(
                        "result binding conflict"
                    )
                return {
                    **snapshot,
                    "status": "executed",
                    "snapshotRowHash": snapshot["rowHash"],
                    "resultIdentity": result_identity,
                    "result": result,
                }


__all__ = (
    "SimulationSnapshotIntegrityError",
    "SimulationSnapshotStore",
)
