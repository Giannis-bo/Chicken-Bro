#!/usr/bin/env python3
from contextlib import contextmanager
from dataclasses import dataclass
import os
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SQLITE_PATH = BASE_DIR / "data" / "wow_news.sqlite3"
POSTGRES_RUNTIME_MODES = {"postgres_personal", "postgres_only"}


@dataclass(frozen=True)
class DatabaseConfig:
    backend: str
    sqlite_path: Path | None = None
    database_url: str = ""


def database_config_from_env():
    database_url = os.environ.get("WOW_DATABASE_URL", "").strip()
    if database_url:
        return DatabaseConfig(backend="postgres", database_url=database_url)
    return DatabaseConfig(
        backend="sqlite",
        sqlite_path=Path(os.environ.get("WOW_NEWS_DB", DEFAULT_SQLITE_PATH)),
    )


def bool_env(name, default=False):
    value = str(os.environ.get(name, "")).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def database_runtime_mode():
    return os.environ.get("WOW_DATABASE_RUNTIME", "").strip()


def sqlite_runtime_disabled():
    return bool_env("WOW_SQLITE_RUNTIME_DISABLED") or database_runtime_mode() == "postgres_only"


def sqlite_migration_source_enabled():
    return bool_env("WOW_SQLITE_MIGRATION_SOURCE") or bool_env("WOW_ALLOW_SQLITE_MIGRATION_SOURCE")


def require_sqlite_runtime_enabled(context="SQLite runtime"):
    if sqlite_runtime_disabled() and not sqlite_migration_source_enabled():
        raise RuntimeError(
            f"{context} cannot use SQLite when PG-only runtime is enabled; "
            "use PostgreSQL runtime tooling or set WOW_SQLITE_MIGRATION_SOURCE=1 for explicit offline migration input"
        )
    return True


def postgres_runtime_enabled(config=None):
    active_config = config or database_config_from_env()
    return active_config.backend == "postgres" and database_runtime_mode() in POSTGRES_RUNTIME_MODES


def postgres_only_runtime_enabled(config=None):
    active_config = config or database_config_from_env()
    return active_config.backend == "postgres" and database_runtime_mode() == "postgres_only"


def configure_sqlite_connection(conn):
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def sqlite_connection(path):
    sqlite_path = Path(path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_path, timeout=30)
    configure_sqlite_connection(conn)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def connect_postgres(database_url):
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("psycopg is required for PostgreSQL runtime connections") from exc
    return psycopg.connect(database_url)
