#!/usr/bin/env python3
from contextlib import contextmanager
from dataclasses import dataclass
import os
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SQLITE_PATH = BASE_DIR / "data" / "wow_news.sqlite3"


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
