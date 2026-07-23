#!/usr/bin/env python3
"""PostgreSQL repository for the immutable observed-build registry."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

try:
    from .observed_build_projection import validate_projection
    from .observed_build_registry import (
        OBSERVED_BUILD_SOURCE_CHECK_SCHEMA_REVISION,
        slot_key,
        validate_observed_snapshot,
    )
    from .observed_build_template_set import (
        EXPECTED_TEMPLATE_SLOT_COUNT,
        validate_template_set,
    )
except ImportError:
    from observed_build_projection import validate_projection
    from observed_build_registry import (
        OBSERVED_BUILD_SOURCE_CHECK_SCHEMA_REVISION,
        slot_key,
        validate_observed_snapshot,
    )
    from observed_build_template_set import (
        EXPECTED_TEMPLATE_SLOT_COUNT,
        validate_template_set,
    )


_SNAPSHOT_ID = re.compile(r"observed-build:sha256:[0-9a-f]{64}")
_PROJECTION_ID = re.compile(r"build-projection:sha256:[0-9a-f]{64}")
_TEMPLATE_SET_ID = re.compile(r"template-set:sha256:[0-9a-f]{64}")
_CHECK_STATUSES = {"captured", "changed", "unchanged", "failed"}


class ObservedBuildIntegrityError(RuntimeError):
    """Raised when stored content disagrees with its content-addressed identity."""


class ObservedBuildPointerConflict(RuntimeError):
    """Raised when a caller attempts to move a stale pointer generation."""


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


def _row_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _json_value(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _sealed_row_matches(
    stored_json: Any,
    stored_hash: Any,
    expected: dict[str, Any],
    expected_hash: str,
) -> bool:
    return (
        _canonical(_json_value(stored_json)) == expected
        and _text(stored_hash) == expected_hash
    )


def _pointer_row(row: Any) -> dict[str, Any]:
    values = list(row or [])
    if len(values) < 6:
        return {}
    return {
        "scope": _text(values[0]),
        "generation": int(values[1]),
        "activeTemplateSetId": _text(values[2]),
        "rollbackTemplateSetId": _text(values[3]),
        "updatedBy": _text(values[4]),
        "updatedAt": _text(values[5]),
    }


def _required_text(value: Any, name: str, *, limit: int = 512) -> str:
    normalized = _text(value)
    if not normalized or len(normalized) > limit:
        raise ObservedBuildIntegrityError(
            f"{name} must be a bounded non-empty string"
        )
    return normalized


def _expected_slots_from_set(template_set: dict[str, Any]) -> list[dict[str, Any]]:
    entries = template_set.get("entries")
    if not isinstance(entries, list):
        raise ObservedBuildIntegrityError("TemplateSet entries must be a list")
    return [
        _canonical(entry.get("slot"))
        for entry in entries
        if isinstance(entry, dict)
    ]


class ObservedBuildStore:
    """Own the additive PG write/read boundary for observed-build artifacts."""

    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    def connection(self):
        return self._connection_factory()

    def seal_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        expected = _canonical(snapshot)
        issues = validate_observed_snapshot(expected)
        if issues:
            raise ObservedBuildIntegrityError(
                "snapshot integrity failed: "
                + ", ".join(issue["code"] for issue in issues)
            )
        slot = expected["slot"]
        source = expected["source"]
        row_hash = _row_hash(expected)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO cache.observed_build_snapshots (
                        snapshot_id, schema_revision, slot_key,
                        class_key, spec_key, hero_key, scenario_key,
                        source_key, source_identity, profile_url,
                        profile_hash, talent_hash, gear_hash, source_revision,
                        snapshot_json, row_hash
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s,
                        %s::jsonb, %s
                    )
                    ON CONFLICT (snapshot_id) DO NOTHING
                    RETURNING snapshot_json, row_hash
                    """,
                    (
                        expected["snapshotId"],
                        expected["schemaRevision"],
                        slot_key(slot),
                        slot["classKey"],
                        slot["specKey"],
                        slot["heroKey"],
                        slot["scenarioKey"],
                        source["sourceKey"],
                        source["sourceIdentity"],
                        source["profileUrl"],
                        expected["profileHash"],
                        expected["talentHash"],
                        expected["gearHash"],
                        expected["sourceRevision"],
                        _json(expected),
                        row_hash,
                    ),
                )
                row = cur.fetchone()
                if row is None:
                    cur.execute(
                        """
                        SELECT snapshot_json, row_hash
                        FROM cache.observed_build_snapshots
                        WHERE snapshot_id = %s
                        """,
                        (expected["snapshotId"],),
                    )
                    row = cur.fetchone()
                if row is None or not _sealed_row_matches(
                    row[0], row[1], expected, row_hash
                ):
                    raise ObservedBuildIntegrityError(
                        "existing snapshot ID has different sealed content"
                    )
        return expected

    def record_snapshot_check(self, check: dict[str, Any]) -> dict[str, Any]:
        expected = _canonical(check)
        if expected.get("schemaRevision") != OBSERVED_BUILD_SOURCE_CHECK_SCHEMA_REVISION:
            raise ObservedBuildIntegrityError("snapshot check schema is unsupported")
        status = _text(expected.get("status"))
        if status not in _CHECK_STATUSES:
            raise ObservedBuildIntegrityError("snapshot check status is unsupported")
        run_id = _required_text(expected.get("runId"), "runId")
        checked_at = _required_text(expected.get("checkedAt"), "checkedAt")
        try:
            actual_slot_key = slot_key(expected.get("slot"))
        except ValueError as error:
            raise ObservedBuildIntegrityError("snapshot check slot is invalid") from error
        if actual_slot_key != _text(expected.get("slotKey")):
            raise ObservedBuildIntegrityError("snapshot check slot identity mismatch")
        snapshot_id = _text(expected.get("snapshotId"))
        problem = expected.get("problem")
        if not isinstance(problem, dict):
            raise ObservedBuildIntegrityError("snapshot check problem must be an object")
        if status == "failed":
            if snapshot_id or not problem:
                raise ObservedBuildIntegrityError(
                    "failed snapshot check requires a problem and no snapshot"
                )
        elif not _SNAPSHOT_ID.fullmatch(snapshot_id) or problem:
            raise ObservedBuildIntegrityError(
                "successful snapshot check requires one snapshot and no problem"
            )
        slot = expected["slot"]
        row_hash = _row_hash(expected)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ops.observed_build_snapshot_checks (
                        run_id, schema_revision, slot_key,
                        class_key, spec_key, hero_key, scenario_key,
                        snapshot_id, status, checked_at,
                        problem_json, check_json, row_hash
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s::timestamptz,
                        %s::jsonb, %s::jsonb, %s
                    )
                    RETURNING check_id
                    """,
                    (
                        run_id,
                        expected["schemaRevision"],
                        expected["slotKey"],
                        slot["classKey"],
                        slot["specKey"],
                        slot["heroKey"],
                        slot["scenarioKey"],
                        snapshot_id or None,
                        status,
                        checked_at,
                        _json(problem),
                        _json(expected),
                        row_hash,
                    ),
                )
                row = cur.fetchone()
                if row is None:
                    raise ObservedBuildIntegrityError(
                        "snapshot check insert returned no identity"
                    )
        return {**expected, "checkId": int(row[0])}

    def seal_projection(self, projection: dict[str, Any]) -> dict[str, Any]:
        expected = _canonical(projection)
        issues = validate_projection(expected)
        if issues:
            raise ObservedBuildIntegrityError(
                "projection integrity failed: "
                + ", ".join(issue["code"] for issue in issues)
            )
        row_hash = _row_hash(expected)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO cache.observed_build_projections (
                        projection_id, snapshot_id, schema_revision, slot_key,
                        dependency_hash, dependency_vector_json,
                        status, importable, projection_json, row_hash
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s::jsonb,
                        %s, %s, %s::jsonb, %s
                    )
                    ON CONFLICT (projection_id) DO NOTHING
                    RETURNING projection_json, row_hash
                    """,
                    (
                        expected["projectionId"],
                        expected["snapshotId"],
                        expected["schemaRevision"],
                        expected["slotKey"],
                        expected["dependencyHash"],
                        _json(expected["dependencyVector"]),
                        expected["status"],
                        expected["importable"],
                        _json(expected),
                        row_hash,
                    ),
                )
                row = cur.fetchone()
                if row is None:
                    cur.execute(
                        """
                        SELECT projection_json, row_hash
                        FROM cache.observed_build_projections
                        WHERE projection_id = %s
                        """,
                        (expected["projectionId"],),
                    )
                    row = cur.fetchone()
                if row is None or not _sealed_row_matches(
                    row[0], row[1], expected, row_hash
                ):
                    raise ObservedBuildIntegrityError(
                        "existing projection ID has different sealed content"
                    )
        return expected

    def seal_template_set(self, template_set: dict[str, Any]) -> dict[str, Any]:
        expected = _canonical(template_set)
        expected_slots = _expected_slots_from_set(expected)
        issues = validate_template_set(expected, expected_slots)
        if issues:
            raise ObservedBuildIntegrityError(
                "TemplateSet integrity failed: "
                + ", ".join(issue["code"] for issue in issues)
            )
        row_hash = _row_hash(expected)
        dependency_hash = _row_hash(expected["dependencyVector"])
        inserted = False
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO cache.observed_build_template_sets (
                        template_set_id, schema_revision, content_hash,
                        dependency_hash, dependency_vector_json,
                        source_run_id, counts_json, template_set_json, row_hash
                    ) VALUES (
                        %s, %s, %s, %s, %s::jsonb,
                        %s, %s::jsonb, %s::jsonb, %s
                    )
                    ON CONFLICT (template_set_id) DO NOTHING
                    RETURNING template_set_id
                    """,
                    (
                        expected["templateSetId"],
                        expected["schemaRevision"],
                        expected["contentHash"],
                        dependency_hash,
                        _json(expected["dependencyVector"]),
                        expected["sourceRunId"],
                        _json(expected["counts"]),
                        _json(expected),
                        row_hash,
                    ),
                )
                inserted = cur.fetchone() is not None
                if inserted:
                    for entry in expected["entries"]:
                        slot = entry["slot"]
                        entry_hash = _row_hash(entry)
                        cur.execute(
                            """
                            INSERT INTO cache.observed_build_template_set_slots (
                                template_set_id, slot_key,
                                class_key, spec_key, hero_key, scenario_key,
                                status, snapshot_id, projection_id,
                                problem_json, slot_json, row_hash
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s::jsonb, %s::jsonb, %s
                            )
                            """,
                            (
                                expected["templateSetId"],
                                entry["slotKey"],
                                slot["classKey"],
                                slot["specKey"],
                                slot["heroKey"],
                                slot["scenarioKey"],
                                entry["status"],
                                entry.get("snapshotId") or None,
                                entry.get("projectionId") or None,
                                _json(entry.get("problem") or {}),
                                _json(entry),
                                entry_hash,
                            ),
                        )
                else:
                    cur.execute(
                        """
                        SELECT template_set_json, row_hash
                        FROM cache.observed_build_template_sets
                        WHERE template_set_id = %s
                        """,
                        (expected["templateSetId"],),
                    )
                    existing = cur.fetchone()
                    if existing is None or not _sealed_row_matches(
                        existing[0], existing[1], expected, row_hash
                    ):
                        raise ObservedBuildIntegrityError(
                            "existing TemplateSet ID has different sealed content"
                        )
                cur.execute(
                    """
                    SELECT count(*)
                    FROM cache.observed_build_template_set_slots
                    WHERE template_set_id = %s
                    """,
                    (expected["templateSetId"],),
                )
                count_row = cur.fetchone()
                if (
                    count_row is None
                    or int(count_row[0]) != EXPECTED_TEMPLATE_SLOT_COUNT
                ):
                    raise ObservedBuildIntegrityError(
                        "sealed TemplateSet must contain exactly 80 slot rows"
                    )
        return expected

    def load_template_set(self, template_set_id: str) -> dict[str, Any]:
        normalized_id = _text(template_set_id)
        if not _TEMPLATE_SET_ID.fullmatch(normalized_id):
            raise ObservedBuildIntegrityError("valid TemplateSet ID is required")
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    """
                    SELECT template_set_json, row_hash
                    FROM cache.observed_build_template_sets
                    WHERE template_set_id = %s
                    """,
                    (normalized_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return {}
                template_set = _canonical(_json_value(row[0]))
                if (
                    _row_hash(template_set) != _text(row[1])
                    or template_set.get("templateSetId") != normalized_id
                ):
                    raise ObservedBuildIntegrityError(
                        "stored TemplateSet row failed integrity validation"
                    )
                cur.execute(
                    """
                    SELECT count(*)
                    FROM cache.observed_build_template_set_slots
                    WHERE template_set_id = %s
                    """,
                    (normalized_id,),
                )
                count_row = cur.fetchone()
                if (
                    count_row is None
                    or int(count_row[0]) != EXPECTED_TEMPLATE_SLOT_COUNT
                ):
                    raise ObservedBuildIntegrityError(
                        "stored TemplateSet does not have exactly 80 slot rows"
                    )
                issues = validate_template_set(
                    template_set,
                    _expected_slots_from_set(template_set),
                )
                if issues:
                    raise ObservedBuildIntegrityError(
                        "stored TemplateSet failed structural validation"
                    )
                return template_set

    def compare_and_swap_pointer(
        self,
        scope: str,
        expected_generation: int,
        template_set_id: str,
        actor: str,
    ) -> dict[str, Any]:
        normalized_scope = _required_text(scope, "scope", limit=80)
        normalized_actor = _required_text(actor, "actor", limit=160)
        normalized_id = _text(template_set_id)
        if not _TEMPLATE_SET_ID.fullmatch(normalized_id):
            raise ObservedBuildIntegrityError("valid TemplateSet ID is required")
        if isinstance(expected_generation, bool):
            raise ObservedBuildIntegrityError("expected generation must be an integer")
        try:
            generation = int(expected_generation)
        except (TypeError, ValueError, OverflowError) as error:
            raise ObservedBuildIntegrityError(
                "expected generation must be an integer"
            ) from error
        if generation < 0:
            raise ObservedBuildIntegrityError(
                "expected generation must not be negative"
            )
        with self.connection() as conn:
            with conn.cursor() as cur:
                if generation == 0:
                    cur.execute(
                        """
                        INSERT INTO cache.observed_build_template_set_pointer (
                            scope, generation, active_template_set_id,
                            rollback_template_set_id, updated_by, updated_at
                        ) VALUES (%s, 1, %s, NULL, %s, now())
                        ON CONFLICT (scope) DO NOTHING
                        RETURNING scope, generation, active_template_set_id,
                                  rollback_template_set_id, updated_by, updated_at
                        """,
                        (normalized_scope, normalized_id, normalized_actor),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE cache.observed_build_template_set_pointer
                        SET generation = generation + 1,
                            rollback_template_set_id = active_template_set_id,
                            active_template_set_id = %s,
                            updated_by = %s,
                            updated_at = now()
                        WHERE scope = %s AND generation = %s
                        RETURNING scope, generation, active_template_set_id,
                                  rollback_template_set_id, updated_by, updated_at
                        """,
                        (
                            normalized_id,
                            normalized_actor,
                            normalized_scope,
                            generation,
                        ),
                    )
                row = cur.fetchone()
                if row is None:
                    raise ObservedBuildPointerConflict(
                        f"pointer generation conflict for {normalized_scope}"
                    )
        return _pointer_row(row)

    def rollback_pointer(
        self,
        scope: str,
        expected_generation: int,
        actor: str,
    ) -> dict[str, Any]:
        normalized_scope = _required_text(scope, "scope", limit=80)
        normalized_actor = _required_text(actor, "actor", limit=160)
        if isinstance(expected_generation, bool):
            raise ObservedBuildIntegrityError("expected generation must be an integer")
        try:
            generation = int(expected_generation)
        except (TypeError, ValueError, OverflowError) as error:
            raise ObservedBuildIntegrityError(
                "expected generation must be an integer"
            ) from error
        if generation < 1:
            raise ObservedBuildIntegrityError(
                "rollback requires a positive expected generation"
            )
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE cache.observed_build_template_set_pointer
                    SET generation = generation + 1,
                        active_template_set_id = rollback_template_set_id,
                        rollback_template_set_id = active_template_set_id,
                        updated_by = %s,
                        updated_at = now()
                    WHERE scope = %s
                      AND generation = %s
                      AND rollback_template_set_id IS NOT NULL
                    RETURNING scope, generation, active_template_set_id,
                              rollback_template_set_id, updated_by, updated_at
                    """,
                    (normalized_actor, normalized_scope, generation),
                )
                row = cur.fetchone()
                if row is None:
                    raise ObservedBuildPointerConflict(
                        f"pointer rollback conflict for {normalized_scope}"
                    )
        return _pointer_row(row)


__all__ = (
    "ObservedBuildIntegrityError",
    "ObservedBuildPointerConflict",
    "ObservedBuildStore",
)
