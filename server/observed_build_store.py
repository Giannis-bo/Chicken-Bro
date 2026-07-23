#!/usr/bin/env python3
"""PostgreSQL repository for the immutable observed-build registry."""

from __future__ import annotations

from contextlib import contextmanager
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
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
_SLUG = re.compile(r"[a-z][a-z0-9_]{0,79}")
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


def _validated_pointer_row(row: Any, *, expected_scope: str) -> dict[str, Any]:
    try:
        pointer = _pointer_row(row)
    except (TypeError, ValueError, OverflowError) as error:
        raise ObservedBuildIntegrityError(
            "stored observed-build pointer failed integrity validation"
        ) from error
    if not pointer:
        return {}
    rollback_id = pointer.get("rollbackTemplateSetId")
    if (
        pointer.get("scope") != expected_scope
        or pointer.get("generation", 0) < 1
        or not _TEMPLATE_SET_ID.fullmatch(
            _text(pointer.get("activeTemplateSetId"))
        )
        or (
            rollback_id
            and not _TEMPLATE_SET_ID.fullmatch(_text(rollback_id))
        )
        or (
            rollback_id
            and rollback_id == pointer.get("activeTemplateSetId")
        )
    ):
        raise ObservedBuildIntegrityError(
            "stored observed-build pointer failed integrity validation"
        )
    return pointer


def _required_text(value: Any, name: str, *, limit: int = 512) -> str:
    normalized = _text(value)
    if not normalized or len(normalized) > limit:
        raise ObservedBuildIntegrityError(
            f"{name} must be a bounded non-empty string"
        )
    return normalized


def _optional_slug(value: Any, name: str) -> str:
    normalized = _text(value)
    if normalized and not _SLUG.fullmatch(normalized):
        raise ObservedBuildIntegrityError(
            f"{name} must be empty or a canonical slug"
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


def _template_set_identity(template_set: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaRevision": template_set.get("schemaRevision"),
        "expectedSlotKeys": template_set.get("expectedSlotKeys"),
        "dependencyVector": template_set.get("dependencyVector"),
        "entries": template_set.get("entries"),
    }


def _validated_stored_template_set(
    row: Any,
    *,
    expected_id: str,
) -> dict[str, Any]:
    if not row or len(row) < 2:
        raise ObservedBuildIntegrityError("stored TemplateSet row is missing")
    stored = _canonical(_json_value(row[0]))
    if (
        not isinstance(stored, dict)
        or _row_hash(stored) != _text(row[1])
        or stored.get("templateSetId") != expected_id
    ):
        raise ObservedBuildIntegrityError(
            "stored TemplateSet row failed integrity validation"
        )
    issues = validate_template_set(stored, _expected_slots_from_set(stored))
    if issues:
        raise ObservedBuildIntegrityError(
            "stored TemplateSet failed structural validation"
        )
    return stored


def _validated_snapshot_row(
    stored_json: Any,
    stored_hash: Any,
) -> dict[str, Any]:
    snapshot = _canonical(_json_value(stored_json))
    if (
        not isinstance(snapshot, dict)
        or _text(stored_hash) != _row_hash(snapshot)
        or validate_observed_snapshot(snapshot)
    ):
        raise ObservedBuildIntegrityError(
            "stored observed-build snapshot failed integrity validation"
        )
    return snapshot


def _validated_projection_row(
    stored_json: Any,
    stored_hash: Any,
) -> dict[str, Any]:
    projection = _canonical(_json_value(stored_json))
    if (
        not isinstance(projection, dict)
        or _text(stored_hash) != _row_hash(projection)
        or validate_projection(projection)
    ):
        raise ObservedBuildIntegrityError(
            "stored observed-build projection failed integrity validation"
        )
    return projection


def _validate_template_set_slot_rows(cur: Any, template_set: dict[str, Any]) -> None:
    template_set_id = template_set["templateSetId"]
    cur.execute(
        """
        SELECT count(*)
        FROM cache.observed_build_template_set_slots
        WHERE template_set_id = %s
        """,
        (template_set_id,),
    )
    count_row = cur.fetchone()
    if count_row is None or int(count_row[0]) != EXPECTED_TEMPLATE_SLOT_COUNT:
        raise ObservedBuildIntegrityError(
            "sealed TemplateSet must contain exactly 80 slot rows"
        )
    cur.execute(
        """
        SELECT slot_key, slot_json, row_hash
        FROM cache.observed_build_template_set_slots
        WHERE template_set_id = %s
        ORDER BY slot_key
        """,
        (template_set_id,),
    )
    rows = cur.fetchall()
    expected_by_key = {
        entry["slotKey"]: entry
        for entry in template_set["entries"]
        if isinstance(entry, dict)
    }
    if len(rows) != EXPECTED_TEMPLATE_SLOT_COUNT:
        raise ObservedBuildIntegrityError(
            "sealed TemplateSet slot rows failed integrity validation"
        )
    seen: set[str] = set()
    for row in rows:
        if not row or len(row) < 3:
            raise ObservedBuildIntegrityError(
                "sealed TemplateSet slot rows failed integrity validation"
            )
        key = _text(row[0])
        expected = expected_by_key.get(key)
        if (
            expected is None
            or key in seen
            or _canonical(_json_value(row[1])) != expected
            or _text(row[2]) != _row_hash(expected)
        ):
            raise ObservedBuildIntegrityError(
                "sealed TemplateSet slot rows failed integrity validation"
            )
        seen.add(key)
    if seen != set(expected_by_key):
        raise ObservedBuildIntegrityError(
            "sealed TemplateSet slot rows failed integrity validation"
        )


class ObservedBuildStore:
    """Own the additive PG write/read boundary for observed-build artifacts."""

    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    @contextmanager
    def connection(self):
        conn = self._connection_factory()
        try:
            yield conn
            if hasattr(conn, "commit"):
                conn.commit()
        except Exception:
            if hasattr(conn, "rollback"):
                conn.rollback()
            raise

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
                        source_identity,
                        dependency_hash, dependency_vector_json,
                        status, importable, projection_json, row_hash
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s::jsonb,
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
                        expected["sourceIdentity"],
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
        sealed = expected
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
                                status, source_identity, snapshot_id, projection_id,
                                problem_json, slot_json, row_hash
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s
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
                                entry.get("sourceIdentity") or None,
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
                    sealed = _validated_stored_template_set(
                        existing,
                        expected_id=expected["templateSetId"],
                    )
                    if _template_set_identity(sealed) != _template_set_identity(
                        expected
                    ):
                        raise ObservedBuildIntegrityError(
                            "existing TemplateSet ID has different sealed content"
                        )
                _validate_template_set_slot_rows(cur, sealed)
        return sealed

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
                template_set = _validated_stored_template_set(
                    row,
                    expected_id=normalized_id,
                )
                _validate_template_set_slot_rows(cur, template_set)
                return template_set

    @staticmethod
    def _load_pointer_with_cursor(
        cur: Any,
        scope: str,
    ) -> dict[str, Any]:
        cur.execute(
            """
            SELECT scope, generation, active_template_set_id,
                   rollback_template_set_id, updated_by, updated_at
            FROM cache.observed_build_template_set_pointer
            WHERE scope = %s
            """,
            (scope,),
        )
        return _validated_pointer_row(
            cur.fetchone(),
            expected_scope=scope,
        )

    @staticmethod
    def _load_template_set_with_cursor(
        cur: Any,
        template_set_id: str,
    ) -> dict[str, Any]:
        cur.execute(
            """
            SELECT template_set_json, row_hash
            FROM cache.observed_build_template_sets
            WHERE template_set_id = %s
            """,
            (template_set_id,),
        )
        row = cur.fetchone()
        template_set = _validated_stored_template_set(
            row,
            expected_id=template_set_id,
        )
        _validate_template_set_slot_rows(cur, template_set)
        return template_set

    def load_pointer(self, scope: str) -> dict[str, Any]:
        """Read one bounded pointer without following its immutable records."""

        normalized_scope = _required_text(scope, "scope", limit=80)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                return self._load_pointer_with_cursor(
                    cur,
                    normalized_scope,
                )

    @staticmethod
    def _entry_matches(
        entry: dict[str, Any],
        class_key: str,
        spec_key: str,
        hero_key: str,
    ) -> bool:
        slot = entry.get("slot") if isinstance(entry.get("slot"), dict) else {}
        return (
            (not class_key or slot.get("classKey") == class_key)
            and (not spec_key or slot.get("specKey") == spec_key)
            and (not hero_key or slot.get("heroKey") == hero_key)
        )

    @staticmethod
    def _validated_active_record(
        row: Any,
        expected_entry: dict[str, Any],
        expected_dependencies: dict[str, Any],
    ) -> dict[str, Any]:
        if not row or len(row) < 6:
            raise ObservedBuildIntegrityError(
                "active observed-build record is incomplete"
            )
        entry = _canonical(_json_value(row[0]))
        if (
            not isinstance(entry, dict)
            or entry != expected_entry
            or _text(row[1]) != _row_hash(entry)
            or entry.get("status") not in {"verified", "stale_lkg"}
        ):
            raise ObservedBuildIntegrityError(
                "active TemplateSet slot failed integrity validation"
            )
        snapshot = _validated_snapshot_row(row[2], row[3])
        projection = _validated_projection_row(row[4], row[5])
        source_identity = _text(entry.get("sourceIdentity"))
        if (
            entry.get("snapshotId") != snapshot.get("snapshotId")
            or entry.get("projectionId") != projection.get("projectionId")
            or entry.get("slotKey") != slot_key(snapshot.get("slot"))
            or entry.get("slotKey") != projection.get("slotKey")
            or projection.get("snapshotId") != snapshot.get("snapshotId")
            or projection.get("sourceIdentity") != source_identity
            or projection.get("dependencyVector") != expected_dependencies
            or _text(
                (snapshot.get("source") or {}).get("sourceIdentity")
            )
            != source_identity
            or projection.get("status") != "verified"
            or projection.get("importable") is not True
        ):
            raise ObservedBuildIntegrityError(
                "active observed-build record references do not match"
            )
        return {
            "entry": entry,
            "snapshot": snapshot,
            "projection": projection,
        }

    def load_active_records(
        self,
        scope: str,
        class_key: str = "",
        spec_key: str = "",
        hero_key: str = "",
    ) -> dict[str, Any]:
        """Read one active TemplateSet and matching records in one snapshot."""

        normalized_scope = _required_text(scope, "scope", limit=80)
        normalized_class = _optional_slug(class_key, "class_key")
        normalized_spec = _optional_slug(spec_key, "spec_key")
        normalized_hero = _optional_slug(hero_key, "hero_key")
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
                )
                pointer = self._load_pointer_with_cursor(
                    cur,
                    normalized_scope,
                )
                if not pointer:
                    return {
                        "pointer": {},
                        "templateSet": {},
                        "records": [],
                    }
                template_set = self._load_template_set_with_cursor(
                    cur,
                    pointer["activeTemplateSetId"],
                )
                if int(
                    (template_set.get("counts") or {}).get(
                        "pending_collection"
                    )
                    or 0
                ):
                    raise ObservedBuildIntegrityError(
                        "active TemplateSet cannot contain pending collection slots"
                    )
                expected_entries = [
                    entry
                    for entry in template_set.get("entries") or []
                    if isinstance(entry, dict)
                    and self._entry_matches(
                        entry,
                        normalized_class,
                        normalized_spec,
                        normalized_hero,
                    )
                ]
                clauses = ["slot.template_set_id = %s"]
                params: list[Any] = [pointer["activeTemplateSetId"]]
                for column, value in (
                    ("class_key", normalized_class),
                    ("spec_key", normalized_spec),
                    ("hero_key", normalized_hero),
                ):
                    if value:
                        clauses.append(f"slot.{column} = %s")
                        params.append(value)
                cur.execute(
                    f"""
                    /* observed_build_active_records */
                    SELECT slot.slot_json, slot.row_hash,
                           snapshot.snapshot_json, snapshot.row_hash,
                           projection.projection_json, projection.row_hash
                    FROM cache.observed_build_template_set_slots slot
                    JOIN cache.observed_build_snapshots snapshot
                      ON snapshot.snapshot_id = slot.snapshot_id
                     AND snapshot.slot_key = slot.slot_key
                     AND snapshot.source_identity = slot.source_identity
                    JOIN cache.observed_build_projections projection
                      ON projection.projection_id = slot.projection_id
                     AND projection.snapshot_id = slot.snapshot_id
                     AND projection.slot_key = slot.slot_key
                     AND projection.source_identity = slot.source_identity
                    WHERE {" AND ".join(clauses)}
                      AND slot.status IN ('verified', 'stale_lkg')
                    ORDER BY slot.slot_key
                    """,
                    tuple(params),
                )
                rows = cur.fetchall()
                expected_by_key = {
                    entry["slotKey"]: entry
                    for entry in expected_entries
                }
                records = []
                seen = set()
                for row in rows:
                    raw_entry = _json_value(row[0]) if row else {}
                    key = _text(
                        raw_entry.get("slotKey")
                        if isinstance(raw_entry, dict)
                        else ""
                    )
                    expected = expected_by_key.get(key)
                    if expected is None or key in seen:
                        raise ObservedBuildIntegrityError(
                            "active observed-build record is not in its TemplateSet"
                        )
                    records.append(
                        self._validated_active_record(
                            row,
                            expected,
                            template_set.get("dependencyVector") or {},
                        )
                    )
                    seen.add(key)
                if seen != set(expected_by_key):
                    raise ObservedBuildIntegrityError(
                        "active observed-build records are incomplete"
                    )
                return {
                    "pointer": pointer,
                    "templateSet": template_set,
                    "records": records,
                }

    def load_active_projection(
        self,
        scope: str,
        projection_id: str,
        class_key: str,
        spec_key: str,
    ) -> dict[str, Any]:
        """Return one exact projection only when it is active for the spec."""

        normalized_id = _text(projection_id)
        if not _PROJECTION_ID.fullmatch(normalized_id):
            raise ObservedBuildIntegrityError(
                "valid projection ID is required"
            )
        records = self.load_active_records(
            scope,
            class_key=class_key,
            spec_key=spec_key,
        )
        if not records["pointer"]:
            return {}
        matches = [
            record
            for record in records["records"]
            if record["projection"].get("projectionId") == normalized_id
        ]
        if len(matches) != 1:
            raise ObservedBuildIntegrityError(
                "observed-build projection is not active for this scope and spec"
            )
        return matches[0]

    def load_latest_verified_projections(
        self,
        dependency_hash: str,
        checked_since: str,
    ) -> dict[str, dict[str, Any]]:
        """Read the newest verified candidate per slot after a source check."""

        normalized_hash = _text(dependency_hash)
        if not _SHA256.fullmatch(normalized_hash):
            raise ObservedBuildIntegrityError(
                "valid dependency hash is required"
            )
        normalized_since = _required_text(
            checked_since,
            "checked_since",
            limit=80,
        )
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
                )
                cur.execute(
                    """
                    /* observed_build_latest_verified_projections */
                    SELECT DISTINCT ON (projection.slot_key)
                           projection.slot_key,
                           projection.projection_json,
                           projection.row_hash
                    FROM cache.observed_build_projections projection
                    JOIN ops.observed_build_snapshot_checks snapshot_check
                      ON snapshot_check.snapshot_id = projection.snapshot_id
                     AND snapshot_check.slot_key = projection.slot_key
                    WHERE projection.dependency_hash = %s
                      AND projection.status = 'verified'
                      AND projection.importable IS TRUE
                      AND snapshot_check.status IN ('captured', 'changed', 'unchanged')
                      AND snapshot_check.checked_at >= %s::timestamptz
                    ORDER BY projection.slot_key,
                             snapshot_check.checked_at DESC,
                             projection.created_at DESC,
                             projection.projection_id
                    """,
                    (normalized_hash, normalized_since),
                )
                output: dict[str, dict[str, Any]] = {}
                for row in cur.fetchall():
                    if not row or len(row) < 3:
                        raise ObservedBuildIntegrityError(
                            "latest verified projection row is incomplete"
                        )
                    key = _text(row[0])
                    projection = _validated_projection_row(
                        row[1],
                        row[2],
                    )
                    if (
                        not key
                        or key in output
                        or projection.get("slotKey") != key
                        or projection.get("dependencyHash")
                        != normalized_hash
                        or projection.get("status") != "verified"
                        or projection.get("importable") is not True
                    ):
                        raise ObservedBuildIntegrityError(
                            "latest verified projection row does not match its query"
                        )
                    output[key] = projection
                return output

    def health_summary(self, scope: str) -> dict[str, Any]:
        """Expose bounded active-set health without returning player payloads."""

        normalized_scope = _required_text(scope, "scope", limit=80)
        empty_counts = {
            "verified": 0,
            "stale_lkg": 0,
            "pending_collection": 0,
        }
        try:
            active = self.load_active_records(normalized_scope)
        except ObservedBuildIntegrityError:
            return {
                "status": "blocked",
                "scope": normalized_scope,
                "active": False,
                "generation": 0,
                "activeTemplateSetId": "",
                "recordCount": 0,
                "sourceIdentityCount": 0,
                "total": EXPECTED_TEMPLATE_SLOT_COUNT,
                "gearCompleteSpecs": 0,
                "counts": empty_counts,
                "problemCodes": ["registry_integrity_failed"],
                "blockers": [
                    "active observed-build registry failed integrity validation"
                ],
            }
        pointer = active["pointer"]
        if not pointer:
            return {
                "status": "pre_cutover",
                "scope": normalized_scope,
                "active": False,
                "generation": 0,
                "activeTemplateSetId": "",
                "recordCount": 0,
                "sourceIdentityCount": 0,
                "total": EXPECTED_TEMPLATE_SLOT_COUNT,
                "gearCompleteSpecs": 0,
                "counts": empty_counts,
                "problemCodes": [],
                "blockers": [
                    "observed-build TemplateSet pointer is inactive"
                ],
            }
        template_set = active["templateSet"]
        records = active["records"]
        entries = [
            entry
            for entry in template_set.get("entries") or []
            if isinstance(entry, dict)
        ]
        counts = _canonical(template_set.get("counts") or {})
        stale_count = int(counts.get("stale_lkg") or 0)
        record_count = len(records)
        complete = record_count == EXPECTED_TEMPLATE_SLOT_COUNT
        entries_by_spec: dict[str, list[dict[str, Any]]] = {}
        for entry in entries:
            slot = (
                entry.get("slot")
                if isinstance(entry.get("slot"), dict)
                else {}
            )
            spec_id = (
                f"{_text(slot.get('classKey'))}:"
                f"{_text(slot.get('specKey'))}"
            )
            entries_by_spec.setdefault(spec_id, []).append(entry)
        gear_complete_specs = sum(
            len(spec_entries) == 2
            and all(
                entry.get("status") in {"verified", "stale_lkg"}
                and _text(entry.get("projectionId"))
                for entry in spec_entries
            )
            for spec_entries in entries_by_spec.values()
        )
        problem_codes: list[str] = []
        for entry in entries:
            problem = (
                entry.get("problem")
                if isinstance(entry.get("problem"), dict)
                else {}
            )
            code = _text(problem.get("code"))
            if code and code not in problem_codes:
                problem_codes.append(code[:120])
            if len(problem_codes) >= 12:
                break
        status = (
            "blocked"
            if not complete
            else "partial"
            if stale_count
            else "verified"
        )
        blockers = []
        if not complete:
            blockers.append(
                "active observed-build TemplateSet does not expose 80 records"
            )
        if stale_count:
            blockers.append(
                f"{stale_count} observed-build slots are serving last-known-good records"
            )
        return {
            "status": status,
            "scope": normalized_scope,
            "active": complete,
            "generation": pointer.get("generation"),
            "activeTemplateSetId": pointer.get("activeTemplateSetId"),
            "dependencyHash": _row_hash(
                template_set.get("dependencyVector") or {}
            ),
            "total": EXPECTED_TEMPLATE_SLOT_COUNT,
            "gearCompleteSpecs": gear_complete_specs,
            "recordCount": record_count,
            "sourceIdentityCount": len(
                {
                    _text(
                        record["projection"].get("sourceIdentity")
                    )
                    for record in records
                    if _text(
                        record["projection"].get("sourceIdentity")
                    )
                }
            ),
            "counts": counts,
            "problemCodes": problem_codes,
            "updatedAt": pointer.get("updatedAt"),
            "blockers": blockers,
        }

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
