"""Ordered transactional runner for the clean Chickenbro product lineage."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


_MIGRATION_NAME = re.compile(r"^[0-9]{4}_[a-z0-9_]+\.sql$")


def _migration_paths(migration_dir: Path) -> tuple[Path, ...]:
    directory = Path(migration_dir)
    if not directory.is_dir():
        raise ValueError("migration directory does not exist")
    paths = tuple(
        sorted(
            path
            for path in directory.iterdir()
            if path.is_file() and _MIGRATION_NAME.fullmatch(path.name)
        )
    )
    if not paths:
        raise ValueError("no product migrations found")
    return paths


def _migration_registry_exists(connection: Any) -> bool:
    row = connection.execute(
        "SELECT pg_catalog.to_regclass(%s)",
        ("ops.schema_migrations",),
    ).fetchone()
    return bool(row and row[0])


def _migration_is_applied(connection: Any, migration_id: str) -> bool:
    if not _migration_registry_exists(connection):
        return False
    row = connection.execute(
        "SELECT 1 FROM ops.schema_migrations WHERE id = %s",
        (migration_id,),
    ).fetchone()
    return row is not None


def _record_migration(connection: Any, migration_id: str) -> None:
    connection.execute(
        """
        INSERT INTO ops.schema_migrations (id, description)
        VALUES (%s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        (migration_id, f"Apply clean product migration {migration_id}"),
    )


def apply_product_migrations(connection: Any, migration_dir: Path) -> tuple[str, ...]:
    """Apply unapplied product migrations in filename order, one transaction each."""

    applied: list[str] = []
    for path in _migration_paths(Path(migration_dir)):
        migration_id = path.stem
        sql = path.read_text(encoding="utf-8")
        if not sql.strip():
            raise ValueError(f"product migration is empty: {path.name}")
        with connection.transaction():
            if _migration_is_applied(connection, migration_id):
                continue
            connection.execute(sql)
            _record_migration(connection, migration_id)
        applied.append(migration_id)
    return tuple(applied)
