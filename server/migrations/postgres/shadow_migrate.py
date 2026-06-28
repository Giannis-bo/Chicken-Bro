#!/usr/bin/env python3
import argparse
import json
import shlex
import sqlite3
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.migrations.postgres import data_copy_plan


SCHEMA_REVISION = "postgres-shadow-migration-v1"
PRODUCTION_DATABASE_NAMES = {"wow_prod", "prod", "production"}
SERIAL_SEQUENCE_TABLES = {
    "content.refresh_runs": ("content.refresh_runs", "id"),
}
PRIMARY_KEY_COLUMNS = {
    "content.sources": "source_key",
    "cache.websim_season_state": "key",
    "cache.raiderio_cache": "cache_key",
}
RECONCILE_NATURAL_KEY_COLUMNS = {
    "cache.websim_gear_variants": ("item_id", "variant_key"),
    "cache.websim_gear_mod_options": ("variant_id", "option_key"),
}
PUBLIC_CACHE_SCHEMA_PREFIXES = ("content.", "cache.")


class ProductionMigrationBlocked(RuntimeError):
    pass


class CountMismatch(RuntimeError):
    pass


def database_name_from_dsn(dsn):
    parsed = urlparse(dsn)
    if parsed.scheme:
        return parsed.path.lstrip("/").split("?", 1)[0]
    for token in shlex.split(dsn):
        if token.startswith("dbname="):
            return token.split("=", 1)[1]
    return ""


def ensure_dsn_allowed(dsn, allow_production=False):
    database = database_name_from_dsn(dsn)
    if not allow_production and database in PRODUCTION_DATABASE_NAMES:
        raise ProductionMigrationBlocked(
            f"PostgreSQL database '{database}' requires explicit owner-approved production migration"
        )
    return True


def ordered_tables(plan):
    return [
        table
        for table in data_copy_plan.SQL_COLUMNS
        if plan["tables"].get(table)
    ]


def sql_placeholder(column):
    if column in data_copy_plan.JSON_COLUMNS:
        return "%s::jsonb"
    return "%s"


def pg_value(column, value):
    if column in data_copy_plan.JSON_COLUMNS:
        return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True)
    return value


def public_cache_table(table):
    return table.startswith(PUBLIC_CACHE_SCHEMA_PREFIXES)


def upsert_assignments(table, conflict_column):
    assignments = []
    for column in data_copy_plan.SQL_COLUMNS[table]:
        if column == conflict_column or column == "id":
            continue
        assignments.append(f"{column} = EXCLUDED.{column}")
    return ", ".join(assignments)


def insert_statement(table, reconcile_public_cache=False):
    columns = data_copy_plan.SQL_COLUMNS[table]
    placeholders = ", ".join(sql_placeholder(column) for column in columns)
    conflict_column = PRIMARY_KEY_COLUMNS.get(table, "id")
    conflict_clause = f"ON CONFLICT ({conflict_column}) DO NOTHING"
    if reconcile_public_cache and public_cache_table(table):
        assignments = upsert_assignments(table, conflict_column)
        if assignments:
            conflict_clause = f"ON CONFLICT ({conflict_column}) DO UPDATE SET {assignments}"
    return (
        f"INSERT INTO {table} ({', '.join(columns)}) "
        f"VALUES ({placeholders}) "
        f"{conflict_clause}"
    )


def delete_conflicting_public_cache_rows(cur, table, rows):
    natural_columns = RECONCILE_NATURAL_KEY_COLUMNS.get(table)
    if not natural_columns or not rows:
        return 0
    conflict_column = PRIMARY_KEY_COLUMNS.get(table, "id")
    deleted = 0
    predicates = " AND ".join(f"{column} = %s" for column in natural_columns)
    for row in rows:
        natural_values = [pg_value(column, row.get(column)) for column in natural_columns]
        cur.execute(
            f"DELETE FROM {table} WHERE {predicates} AND {conflict_column} <> %s",
            [*natural_values, pg_value(conflict_column, row.get(conflict_column))],
        )
        deleted += 1
    return deleted


def verify_table_count(cur, table, rows):
    if not rows:
        return 0
    key_column = PRIMARY_KEY_COLUMNS.get(table, "id")
    ids = [row[key_column] for row in rows]
    placeholders = ", ".join(["%s"] * len(ids))
    cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {key_column} IN ({placeholders})", ids)
    count = cur.fetchone()[0]
    if count != len(ids):
        raise CountMismatch(f"{table} expected {len(ids)} copied rows, found {count}")
    return count


def refresh_serial_sequence(cur, table):
    target = SERIAL_SEQUENCE_TABLES.get(table)
    if not target:
        return
    table_name, column_name = target
    cur.execute(
        f"""
        SELECT setval(
            pg_get_serial_sequence('{table_name}', '{column_name}'),
            GREATEST((SELECT COALESCE(MAX({column_name}), 1) FROM {table_name}), 1),
            true
        )
        """
    )


def validate_plan(plan):
    errors = plan.get("errors") or []
    if errors:
        raise ValueError(f"copy plan has errors: {errors}")
    if plan.get("schemaRevision") != data_copy_plan.SCHEMA_REVISION:
        raise ValueError(f"unsupported copy plan revision: {plan.get('schemaRevision')}")


def execute_copy_plan(pg_conn, plan, source_sqlite_path="", reconcile_public_cache=False):
    validate_plan(plan)
    rows_by_table = {}
    verified_rows = 0
    sync_run_id = str(uuid.uuid4())
    try:
        with pg_conn.cursor() as cur:
            for table in ordered_tables(plan):
                rows = plan["tables"][table]
                if reconcile_public_cache and public_cache_table(table):
                    delete_conflicting_public_cache_rows(cur, table, rows)
                statement = insert_statement(table, reconcile_public_cache=reconcile_public_cache)
                columns = data_copy_plan.SQL_COLUMNS[table]
                for row in rows:
                    params = [pg_value(column, row.get(column)) for column in columns]
                    cur.execute(statement, params)
                rows_by_table[table] = verify_table_count(cur, table, rows)
                refresh_serial_sequence(cur, table)
                verified_rows += rows_by_table[table]
            cur.execute(
                """
                INSERT INTO ops.sync_runs (
                    id, sync_type, status, counts_json, error
                ) VALUES (%s, 'postgres_shadow_migration', 'completed', %s::jsonb, '')
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    sync_run_id,
                    json.dumps(
                        {
                            "schemaRevision": SCHEMA_REVISION,
                            "copyPlanRevision": plan["schemaRevision"],
                            "reconcileMode": "public_cache" if reconcile_public_cache else "insert_only",
                            "sourceSqlitePath": source_sqlite_path,
                            "rowsByTable": rows_by_table,
                            "verifiedRows": verified_rows,
                            "skipped": plan.get("skipped", {}),
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                ),
            )
        pg_conn.commit()
    except Exception:
        pg_conn.rollback()
        raise
    return {
        "schemaRevision": SCHEMA_REVISION,
        "copyPlanRevision": plan["schemaRevision"],
        "reconcileMode": "public_cache" if reconcile_public_cache else "insert_only",
        "sourceSqlitePath": source_sqlite_path,
        "rowsByTable": rows_by_table,
        "verifiedRows": verified_rows,
        "syncRunId": sync_run_id,
    }


def connect_postgres(dsn):
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("psycopg is required to execute PostgreSQL shadow migration") from exc
    return psycopg.connect(dsn)


def build_plan(sqlite_path):
    with sqlite3.connect(f"file:{Path(sqlite_path)}?mode=ro", uri=True) as conn:
        return data_copy_plan.build_postgres_copy_plan(conn)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Execute a guarded PostgreSQL shadow migration from SQLite.")
    parser.add_argument("--sqlite", required=True, help="Path to a SQLite backup or local database opened read-only.")
    parser.add_argument("--postgres", required=True, help="Target PostgreSQL DSN.")
    parser.add_argument("--dry-run", action="store_true", help="Build and print the copy plan without connecting to PG.")
    parser.add_argument(
        "--allow-production",
        action="store_true",
        help="Allow a production-like database name after explicit owner approval.",
    )
    parser.add_argument(
        "--reconcile-public-cache",
        action="store_true",
        help=(
            "Refresh existing content.* and cache.* rows during cutover-time reconciliation. "
            "Personal identity/app/knowledge rows remain insert-only."
        ),
    )
    args = parser.parse_args(argv)

    ensure_dsn_allowed(args.postgres, allow_production=args.allow_production)
    plan = build_plan(args.sqlite)
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    with connect_postgres(args.postgres) as pg_conn:
        result = execute_copy_plan(
            pg_conn,
            plan,
            source_sqlite_path=args.sqlite,
            reconcile_public_cache=args.reconcile_public_cache,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
