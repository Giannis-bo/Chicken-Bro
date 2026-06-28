# PostgreSQL Identity Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the project toward PostgreSQL plus strong user identity while preserving the current SQLite runtime until an explicit production cutover is approved.

**Architecture:** Add a compatibility database layer first, then land repeatable PostgreSQL schema and migration artifacts beside the existing SQLite schema. Runtime behavior stays SQLite by default while tests prove owner boundaries, SimC task snapshots, Chickenbro session isolation, analytics hygiene, and rollback boundaries.

**Tech Stack:** Python standard library `sqlite3`, optional `psycopg` v3 for PostgreSQL integration, HTTP backend in `server/news_backend.py`, WebSim data layer in `server/websim_payload.py`, Python `unittest`, Node `node:test`, and SQL migration files.

---

## Confirmation Gate

This plan is ready for review, but implementation must not start until the owner confirms Phase 1. It does not authorize deployment, production database writes, online PostgreSQL changes, or a systemd environment switch.

When Phase 1 starts, keep these invariants true:

- SQLite remains the default runtime through `WOW_NEWS_DB`.
- No production database is modified.
- Guest data and old auth tokens are not migrated.
- Personal write assets remain owner-scoped by `user_id`.
- `simulator_tasks.summary_json` remains the task list read model.
- SimC task details remain snapshot-based and strip internal profile/debug fields.
- Chickenbro execution stays in the current web-backend model.
- Embedding and independent worker support are schema/runbook reservations only.

## Implementation Notes 2026-06-27

- Phase 1 has landed as a SQLite-first compatibility layer, PostgreSQL target schema artifact, worker-ready `simulator_tasks` compatibility fields, focused tests, and local rollback/runbook docs.
- Phase 2 foundation has landed as read-only identity shadow and data-copy dry-run artifacts. `identity_shadow_plan.py` builds stable formal-user PG UUID/provider identity mappings and owner impact counts; `data_copy_plan.py` emits reviewable JSON/SQL for formal-owner identity/app/knowledge rows while excluding guest users, guest-owned assets, and legacy auth tokens.
- Phase 3 foundation has landed as `shadow_migrate.py`, a guarded data-copy executor that reuses the copy plan, verifies target counts, rolls back on mismatch, blocks production-like DSNs by default, and supports legacy SQLite `simulator_tasks` tables without worker-ready columns.
- Phase 4 foundation has landed as PostgreSQL personal-store, analytics-store, content-store, and cache runtime seams. `WOW_DATABASE_RUNTIME=postgres_personal` keeps SQLite available as fallback while routing identity/auth/profile, build-template CRUD, SimC task enqueue/list/detail plus in-process runner state writes, Chickenbro session/message/job/user-context persistence, analytics event writes/admin analytics reads including simulator task snapshot cross-read, news refresh/public article reads, data-health `websim_sync` / `gearCatalog` sync-state reads, active season reads, `/api/websim/loot`, `/api/websim/gear`, and `/api/websim/talents` reads through PostgreSQL tables when PG cache data is verified. `0003_build_template_config_hash_unique.sql` changes PG build-template dedupe to `user_id + template_type + config_hash`; `0004_chickenbro_runtime_fields.sql` adds Chickenbro message-job linkage and bounded context storage while preserving the current Chickenbro web-backend execution model for this phase; `0005_content_runtime_fields.sql` adds content runtime fields, discovery queue, refresh runs, and `wow_app` sequence grants; `0006_websim_season_loot_cache.sql` adds the season/journal/loot read model; `0007_websim_gear_catalog_cache.sql` extends PG gear source/variant/global mod-option cache tables; `0008_websim_talent_cache.sql` extends PG talent nodes, spell details, profile presets, and community talent templates for the current SQLite read model.
- Owner note: during this goal the owner authorized cloud-server execution without further confirmation. PostgreSQL 16.14 was installed on `wow-lighthouse`; `wow_dev`, `wow_test`, and `wow_prod` were created; and `0001` through `0009` were applied to all three databases.
- Production now runs the `postgres_personal` hybrid runtime. SQLite-compatible deployments/restarts were performed first; after fresh reconciliation and temporary service rehearsal, `/etc/wow-backend.env` was updated with `WOW_DATABASE_URL=postgresql://wow_app@127.0.0.1:5432/wow_prod`, `WOW_DATABASE_RUNTIME=postgres_personal`, and `PGPASSFILE=/home/ubuntu/.pgpass`; rollback env backup is `/etc/wow-backend.env.before-pg-runtime-20260627T200625Z`. A shadow migration precheck found that the old guest filter missed the fixed `guest-simulator` openid; after a regression test and script fix, the erroneous guest-owned shadow rows were cleaned from `wow_test` and `wow_prod`, and the corrected executable shadow migration records `verifiedRows=0`, `guestUsers=13`, `guestOwnedRows=52`, and `guest_identity_rows=0` for both databases. Cloud smokes verified the personal-store seam, Chickenbro profile/session/message/job owner isolation, analytics event/admin summary/simulator seam, content refresh/article read seam, and WebSim cache sync-state health seam with temporary users/events/content/cache rows and cleanup or restore.
- A temporary cloud hybrid service rehearsal ran on `127.0.0.1:8788` with `WOW_DATABASE_URL=$WOW_PG_APP_DSN_TEST`, `WOW_DATABASE_RUNTIME=postgres_personal`, collectors disabled, and the production SQLite cache path. It verified public reads from SQLite plus analytics and Chickenbro writes to `wow_test` PG, then terminated and cleaned all smoke rows. The production service on `8787` remained active with `WOW_DATABASE_URL` absent.
- Public content/cache shadow copy has now been executed into both `wow_test` and `wow_prod` without switching runtime. Source backup: `/opt/wow-mini-program/backups/wow_news-before-public-content-cache-copy-20260627T180920Z.sqlite3`; each target verified `12044` rows across `content.sources`, `content.raw_articles`, `content.article_evidence`, `content.articles`, `content.discovery_queue`, `content.refresh_runs`, `cache.websim_sync_state`, and `cache.raiderio_cache`, while `identity.users` and `identity.user_identities` remained `0`. Real-data rehearsals fixed the `content.sources.source_key` idempotency/UUID rule and preserved duplicate historical `content.article_evidence` rows by SQLite id-derived UUID.
- A follow-up temporary HTTP rehearsal on `127.0.0.1:8788` used `wow_test` PG with `WOW_DATABASE_RUNTIME=postgres_personal` to verify PG-only content detail/list reads, PG cache-backed `/api/data/health`, and Bearer-authenticated `/api/me/build-templates` create/list/delete. Result: `pgOnlyArticleVisible=true`, `websimStatus=verified`, `gearRevision=codex-hybrid-http-smoke`, `unauthTemplates=401`, `createdTemplateRemote=true`, `templateRowsAfterDelete=0`; all temporary article/raw/identity/template rows were cleaned and port `8788` was closed.
- WebSim season/loot read-model follow-up has now been executed into both `wow_test` and `wow_prod` without switching runtime. The same source backup produced a `13944`-row guarded copy including `cache.websim_items=1272`, `cache.websim_season_state=1`, `cache.websim_season_dungeons=8`, `cache.websim_instances=12`, `cache.websim_encounters=39`, and `cache.websim_loot=568`; `wow_test` syncRunId `be614be8-4022-496c-94ca-fa38538a7353`, `wow_prod` syncRunId `86702d49-867d-4c22-b538-b26ab88d824a`. A `wow_test` hybrid helper smoke temporarily extended the copied active-season expiry, verified `seasonStatus=verified` and `lootItems=24`, then restored the original expiry.
- WebSim gear catalog read-model follow-up has now been executed into both `wow_test` and `wow_prod` without switching runtime. The same source backup produced a `19073`-row guarded copy including `cache.websim_gear_sources=1050`, `cache.websim_gear_variants=4017`, and `cache.websim_gear_mod_options=62`; `wow_test` syncRunId `48877f93-8a49-41a9-8132-f47c78950a13`, `wow_prod` syncRunId `06ec3afd-0e2f-41e8-9b7d-6a8bc29f705f`. A `wow_test` backend-level helper smoke temporarily extended the copied active-season expiry, verified `runtime_websim_gear_payload(..., compact=True)` used PG with `nonemptySlots=16` and `catalogItems=120`, then restored the original expiry.
- WebSim talent read-model follow-up has now been executed into both `wow_test` and `wow_prod` without switching runtime. The same source backup produced a `27950`-row guarded copy including `cache.websim_talents=5246`, `cache.websim_spell_details=3240`, `cache.websim_profile_presets=49`, and `cache.websim_community_talent_templates=342`; `wow_test` syncRunId `c351e99c-db7f-4720-a5c3-812df3eaa0ca`, `wow_prod` syncRunId `6b9a3819-552d-4bb1-a99e-40cf2cb3b23e`. A `wow_test` backend-level helper smoke temporarily extended the copied active-season expiry, verified `runtime_websim_talents_payload(..., "spellslinger")` used PG with `nodeCount=110`, `presetCount=2`, and `communityTemplateCount=4`, then restored the original expiry.
- Cutover-time public/cache reconciliation now has an explicit `--reconcile-public-cache` mode in `shadow_migrate.py`: public `content.*` and `cache.*` rows are upserted while personal `identity/app/knowledge` rows remain insert-only. Fresh production backup `/opt/wow-mini-program/backups/wow_news-before-pg-fresh-reconcile-20260627T195118Z.sqlite3` reconciled `wow_prod` with `syncRunId=ef08bca3-f16b-43ba-a1e3-de2e0a18ccd2`, `reconcileMode=public_cache`, and `verifiedRows=27950`.
- A 3-cycle temporary production-DSN rehearsal on `127.0.0.1:8788` verified PG-backed data health marker reads, public WebSim gear/talents/loot, Bearer profile/template CRUD, SimC task list/detail snapshot reads, Chickenbro message/session/job, and analytics event writes; cleanup left no temporary identity rows/events and restored the cache marker.
- Production main-service smoke after the hybrid runtime switch verified `wow-backend=active`, public URL 200s, PG cache marker visibility through `/api/data/health`, authenticated profile/template CRUD, SimC task list/detail snapshot reads, Chickenbro session/job persistence, analytics event writes, and cleanup (`userIdentityRows=0`, `analyticsRows=0`, restored marker).

## Current SQLite Map

Primary SQLite entry:

- `server/news_backend.py`
  - `DB_PATH = Path(os.environ.get("WOW_NEWS_DB", BASE_DIR / "data" / "wow_news.sqlite3"))`
  - `db_connection()` opens SQLite and enables `PRAGMA busy_timeout`, `foreign_keys`, and WAL.
  - `init_db()` creates `schema_migrations`, news/content tables, `wechat_users`, `auth_tokens`, `simulator_tasks`, `user_build_templates`, Chickenbro tables, WebSim tables, and analytics tables.

Secondary schema helpers:

- `server/websim_payload.py::ensure_websim_tables`
  - Creates `websim_sync_state`, season, item, gear source/variant/mod option, talent, community template, asset, and translation tables.
- `server/analytics.py::ensure_analytics_tables`
  - Creates event, anonymous-to-user link, and daily metric tables.
- `server/raiderio_payload.py::ensure_raiderio_tables`
  - Creates Raider.IO cache table and has SQLite table-introspection helpers.
- `server/stat_weights_payload.py::ensure_stat_weight_tables`
  - Creates stat-weight cache and run tables.

Direct SQLite scripts:

- `server/websim_sync.py`
- `server/community_template_sync.py`
- `server/stat_weights_sync.py`
- `server/crafted_gear_backfill.py`
- `server/gear_observed_backfill.py`
- `server/community_talent_sources/raiderio.py`

Test initialization paths:

- `tests/news_backend_test.py`
  - Sets `WOW_NEWS_DB` to a temporary `.sqlite3`, reloads `server.news_backend`, and calls `init_db()`.
- `tests/websim_payload_test.py`
  - Sets `WOW_NEWS_DB`, reloads backend and WebSim modules, calls `backend.init_db()`, then uses direct `sqlite3.connect(self.db_path)` in many focused tests.
- `tests/stat_weights_payload_test.py` and `tests/raiderio_payload_test.py`
  - Use temporary SQLite files and direct `sqlite3.connect`.
- `tests/gear_observed_backfill_test.py`
  - Tests SQLite lock retry behavior and read-only URI connection behavior.

SQLite-specific code to isolate before PostgreSQL:

- `PRAGMA table_info`, `PRAGMA database_list`, `sqlite_master`, `AUTOINCREMENT`, `INSERT OR IGNORE`, SQLite JSON functions such as `json_extract`, `?` parameter markers, direct SQLite read-only URI mode, WAL/busy timeout settings, and tests asserting exact PRAGMA behavior.

## Phase Overview

### Phase 1: Compatibility Layer And Schema Artifacts

Purpose: make PostgreSQL implementation possible without changing production behavior.

Deliverables:

- A small database utility module that preserves SQLite defaults and exposes backend/dialect helpers.
- A migration layout for SQLite compatibility and PostgreSQL target schema.
- PostgreSQL SQL files for `identity`, `app`, `content`, `cache`, `knowledge`, `analytics`, and `ops` schemas.
- Tests proving existing SQLite init still passes and PostgreSQL schema artifacts contain the required owner, snapshot, and worker-ready fields.
- Documentation/runbook updates only; no deployment.

### Phase 2: Strong Identity Foundation

Purpose: move from `wechat_users` as the identity root toward `identity.users` plus provider identities.

Deliverables:

- `identity.users`, `identity.user_identities`, `identity.auth_tokens` target schema.
- Migration mapping from formally authenticated SQLite users to PG users.
- No guest users, guest tasks, guest Chickenbro sessions, or old tokens migrated.
- Login/token APIs still work in SQLite fallback.
- Tests for token isolation, template owner isolation, and no token leakage over insecure HTTP.

### Phase 3: User Assets And Build Archives

Purpose: introduce the backend aggregation layer for build archives without adding a new front-end workspace page.

Deliverables:

- `app.build_templates` and `app.build_archives` target schema.
- Archive writes only on template save and final SimC submit.
- Dedup by `user_id + name + config_hash`.
- Current-state and history snapshots preserved.
- Tests for owner isolation and no long-term writes during browse/preview/confirm.

### Phase 4: SimC Task Snapshot And Worker-Ready Fields

Purpose: preserve the current SimC task behavior while making PostgreSQL task rows ready for a future worker.

Deliverables:

- `app.simulator_tasks` target schema with `request_json`, `analysis_json`, `summary_json`, and worker-ready fields.
- Worker-ready fields: `queued_at`, `started_at`, `finished_at`, `attempt`, `locked_by`, `heartbeat_at`, `cancel_requested`, `last_error`.
- Current web-backend runner remains unchanged.
- Task list reads `summary_json`.
- Task detail uses stored task snapshot and strips `profile`, `draftProfile`, raw SimC output, LLM, Codex, and `allowedNumbers`.
- Tests for queued/running/completed/failed summaries and snapshot immutability after template edits.

### Phase 5: Chickenbro Multi-Session And Knowledge Boundaries

Purpose: preserve current execution while making sessions, personal context, public knowledge, and future worker behavior explicit.

Deliverables:

- `app.chickenbro_sessions`, `app.chickenbro_messages`, `app.chickenbro_actions`, and `app.agent_jobs` target schema.
- `knowledge.user_context_summaries` owner-scoped schema.
- `knowledge.public_documents` and `knowledge.public_document_chunks` schema using PostgreSQL full-text search and structured tags.
- Optional embedding columns are present only if cheap, nullable, and unused by runtime.
- Tests for session owner isolation, no raw logs/full SimC profile in long-term memory, and public knowledge not receiving personal context automatically.

### Phase 6: Content, Analytics, Ops, Backup, And Cutover Readiness

Purpose: make migration and eventual cutover observable and reversible.

Deliverables:

- `content.sources`, `content.raw_articles`, `content.article_evidence`, `content.articles`.
- `analytics.events`, `analytics.user_links`, `analytics.daily_metrics`.
- `ops.schema_migrations`, `ops.sync_runs`, `ops.agent_jobs`, `ops.audit_logs`, `ops.health_snapshots`.
- SQLite backup runbook and PG `pg_dump` runbook.
- Shadow migration script with counts and checksums.
- Production cutover checklist that requires explicit owner approval before running.

## Detailed Task Plan

### Task 1: Add Database Compatibility Utilities

**Files:**

- Create: `server/db.py`
- Test: `tests/database_adapter_test.py`
- Modify later: `server/news_backend.py`

- [ ] **Step 1: Write failing tests for backend detection and SQLite connection pragmas**

Add `tests/database_adapter_test.py` with tests that prove SQLite is still default and that `WOW_DATABASE_URL` selects PostgreSQL only when explicitly configured.

```python
import os
import tempfile
import unittest
from pathlib import Path


class DatabaseAdapterTest(unittest.TestCase):
    def test_sqlite_is_default_backend(self):
        from server import db

        with tempfile.TemporaryDirectory() as tmp:
            os.environ.pop("WOW_DATABASE_URL", None)
            os.environ["WOW_NEWS_DB"] = str(Path(tmp) / "wow.sqlite3")
            config = db.database_config_from_env()
            self.assertEqual(config.backend, "sqlite")
            self.assertTrue(str(config.sqlite_path).endswith("wow.sqlite3"))

    def test_postgres_requires_explicit_database_url(self):
        from server import db

        os.environ["WOW_DATABASE_URL"] = "postgresql://wow_app@localhost/wow_test"
        try:
            config = db.database_config_from_env()
        finally:
            os.environ.pop("WOW_DATABASE_URL", None)
        self.assertEqual(config.backend, "postgres")
        self.assertIn("wow_test", config.database_url)
```

Run:

```bash
python -m unittest tests.database_adapter_test
```

Expected: fail because `server/db.py` does not exist.

- [ ] **Step 2: Implement minimal adapter without changing existing runtime**

Create `server/db.py` with:

```python
from contextlib import contextmanager
from dataclasses import dataclass
import os
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


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
        sqlite_path=Path(os.environ.get("WOW_NEWS_DB", BASE_DIR / "data" / "wow_news.sqlite3")),
    )


def configure_sqlite_connection(conn):
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def sqlite_connection(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    configure_sqlite_connection(conn)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 3: Run focused tests**

Run:

```bash
python -m unittest tests.database_adapter_test
python -m unittest tests.news_backend_test.NewsBackendTest.test_init_db_records_schema_migrations_and_enforces_foreign_keys
```

Expected: both pass; `news_backend.py` still owns current runtime.

### Task 2: Route `news_backend.db_connection` Through The Adapter

**Files:**

- Modify: `server/news_backend.py`
- Test: `tests/news_backend_test.py`, `tests/database_adapter_test.py`

- [ ] **Step 1: Add a regression test that `news_backend.db_connection` still uses SQLite fallback**

Extend `tests/database_adapter_test.py`:

```python
    def test_news_backend_db_connection_uses_sqlite_fallback(self):
        import importlib
        import server.news_backend as backend

        with tempfile.TemporaryDirectory() as tmp:
            os.environ.pop("WOW_DATABASE_URL", None)
            os.environ["WOW_NEWS_DB"] = str(Path(tmp) / "news.sqlite3")
            backend = importlib.reload(backend)
            backend.init_db()
            with backend.db_connection() as conn:
                foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            self.assertEqual(foreign_keys, 1)
```

Expected: pass before implementation, then remain passing after the adapter import.

- [ ] **Step 2: Replace local SQLite connection setup with adapter helper**

Change `server/news_backend.py` so `db_connection()` delegates SQLite setup:

```python
from server.db import database_config_from_env, sqlite_connection


DB_CONFIG = database_config_from_env()
DB_PATH = DB_CONFIG.sqlite_path or Path(os.environ.get("WOW_NEWS_DB", BASE_DIR / "data" / "wow_news.sqlite3"))


@contextmanager
def db_connection():
    config = database_config_from_env()
    if config.backend != "sqlite":
        raise RuntimeError("PostgreSQL runtime is not enabled in this phase")
    with sqlite_connection(config.sqlite_path) as conn:
        yield conn
```

This intentionally rejects PostgreSQL runtime during Phase 1 while allowing schema files and optional tests to be added safely.

- [ ] **Step 3: Run owner and migration smoke tests**

Run:

```bash
python -m unittest tests.database_adapter_test
python -m unittest tests.news_backend_test.NewsBackendTest.test_init_db_records_schema_migrations_and_enforces_foreign_keys
python -m unittest tests.news_backend_test.NewsBackendTest.test_user_build_templates_are_synced_and_isolated_by_owner
```

Expected: pass.

### Task 3: Add PostgreSQL Schema Migration Artifacts

**Files:**

- Create: `server/migrations/postgres/0001_identity_app_content_cache_knowledge_analytics_ops.sql`
- Create: `tests/postgres_schema_test.py`
- Modify: `docs/database-architecture.md`

- [ ] **Step 1: Write schema artifact tests**

Create `tests/postgres_schema_test.py`:

```python
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "server" / "migrations" / "postgres" / "0001_identity_app_content_cache_knowledge_analytics_ops.sql"


class PostgresSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = SCHEMA.read_text(encoding="utf-8")

    def test_declares_required_schemas(self):
        for name in ("identity", "app", "content", "cache", "knowledge", "analytics", "ops"):
            self.assertIn(f"CREATE SCHEMA IF NOT EXISTS {name};", self.sql)

    def test_user_assets_have_user_id_owner(self):
        for table in (
            "app.build_templates",
            "app.build_archives",
            "app.simulator_tasks",
            "app.chickenbro_sessions",
            "app.chickenbro_messages",
            "knowledge.user_context_summaries",
        ):
            section_start = self.sql.index(f"CREATE TABLE IF NOT EXISTS {table}")
            section = self.sql[section_start:self.sql.index(");", section_start)]
            self.assertIn("user_id", section)
            self.assertIn("REFERENCES identity.users", section)

    def test_simc_tasks_have_summary_snapshot_and_worker_ready_fields(self):
        start = self.sql.index("CREATE TABLE IF NOT EXISTS app.simulator_tasks")
        section = self.sql[start:self.sql.index(");", start)]
        for field in (
            "request_json",
            "analysis_json",
            "summary_json",
            "queued_at",
            "started_at",
            "finished_at",
            "attempt",
            "locked_by",
            "heartbeat_at",
            "cancel_requested",
            "last_error",
        ):
            self.assertIn(field, section)

    def test_embedding_is_reserved_not_required(self):
        self.assertIn("embedding_status", self.sql)
        self.assertIn("DEFAULT 'disabled'", self.sql)
```

Run:

```bash
python -m unittest tests.postgres_schema_test
```

Expected: fail because the SQL file does not exist.

- [ ] **Step 2: Add PostgreSQL SQL migration**

The SQL file must include:

```sql
CREATE SCHEMA IF NOT EXISTS identity;
CREATE SCHEMA IF NOT EXISTS app;
CREATE SCHEMA IF NOT EXISTS content;
CREATE SCHEMA IF NOT EXISTS cache;
CREATE SCHEMA IF NOT EXISTS knowledge;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS ops;
```

It must define at minimum:

- `identity.users`
- `identity.user_identities`
- `identity.auth_tokens`
- `app.build_templates`
- `app.build_archives`
- `app.simulator_tasks`
- `app.chickenbro_sessions`
- `app.chickenbro_messages`
- `app.chickenbro_actions`
- `app.agent_jobs`
- `content.sources`
- `content.raw_articles`
- `content.article_evidence`
- `content.articles`
- `cache.websim_sync_state`
- `cache.websim_items`
- `cache.websim_gear_sources`
- `cache.websim_gear_variants`
- `cache.websim_gear_mod_options`
- `cache.websim_talents`
- `cache.websim_community_talent_templates`
- `cache.raiderio_cache`
- `cache.stat_weight_cache`
- `knowledge.public_documents`
- `knowledge.public_document_chunks`
- `knowledge.user_context_summaries`
- `analytics.events`
- `analytics.user_links`
- `analytics.daily_metrics`
- `ops.schema_migrations`
- `ops.sync_runs`
- `ops.audit_logs`
- `ops.health_snapshots`

Use `jsonb` for JSON payloads, `timestamptz` for timestamps, `uuid` or text IDs consistently, and explicit foreign keys for owner-scoped data.

- [ ] **Step 3: Run schema artifact tests**

Run:

```bash
python -m unittest tests.postgres_schema_test
```

Expected: pass without requiring a local PostgreSQL server.

### Task 4: Preserve SQLite Runtime While Adding Worker-Ready Columns

**Files:**

- Modify: `server/news_backend.py`
- Test: `tests/news_backend_test.py`
- Docs: `docs/database-architecture.md`

- [ ] **Step 1: Add SQLite migration test for task worker-ready columns**

Extend `tests/news_backend_test.py::test_init_db_records_schema_migrations_and_enforces_foreign_keys` or add a focused test:

```python
    def test_simulator_tasks_include_worker_ready_columns(self):
        self.backend.init_db()
        with self.backend.db_connection() as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(simulator_tasks)").fetchall()}
        for field in (
            "queued_at",
            "started_at",
            "finished_at",
            "attempt",
            "locked_by",
            "heartbeat_at",
            "cancel_requested",
            "last_error",
        ):
            self.assertIn(field, columns)
```

Expected: fail before schema change.

- [ ] **Step 2: Add migration marker and compatible columns**

Update `SCHEMA_MIGRATIONS` in `server/news_backend.py`:

```python
("simulator_task_worker_ready_v1", "Simulator tasks reserve worker-ready queue governance fields.")
```

Update `ensure_simulator_task_columns(conn)` to add:

```python
"queued_at": "TEXT NOT NULL DEFAULT ''",
"started_at": "TEXT NOT NULL DEFAULT ''",
"finished_at": "TEXT NOT NULL DEFAULT ''",
"attempt": "INTEGER NOT NULL DEFAULT 0",
"locked_by": "TEXT NOT NULL DEFAULT ''",
"heartbeat_at": "TEXT NOT NULL DEFAULT ''",
"cancel_requested": "INTEGER NOT NULL DEFAULT 0",
"last_error": "TEXT NOT NULL DEFAULT ''",
```

Keep the existing runner logic unchanged.

- [ ] **Step 3: Populate existing runner updates without changing execution model**

When inserting a queued SimC template task in `enqueue_simcraft_template_task`, set `queued_at = now`. When marking running in `mark_simcraft_template_task_running`, set `started_at = now` and increment `attempt` only once per runner claim. When finishing in `run_simcraft_template_task`, set `finished_at = finished_at` and `last_error` for failed tasks.

Keep `analysis_json.taskTiming` and `summary_json.timing` as the player-facing contract.

- [ ] **Step 4: Run focused tests**

Run:

```bash
python -m unittest tests.news_backend_test.NewsBackendTest.test_simulator_tasks_include_worker_ready_columns
python -m unittest tests.news_backend_test.NewsBackendTest.test_simcraft_template_final_submit_queues_task_without_running_llm
python -m unittest tests.news_backend_test.NewsBackendTest.test_simcraft_template_runner_updates_summary
```

If the exact test names differ, use:

```bash
python -m unittest tests.news_backend_test
```

Expected: pass.

### Task 5: Lock SimC Summary And Snapshot Invariants

**Files:**

- Modify: `tests/news_backend_test.py`
- Modify only if needed: `server/news_backend.py`

- [ ] **Step 1: Add a regression test that task list prefers stored summary**

Write a test that creates a `simcraft_template` task with a distinctive `summary_json`, then mutates the original template row. `list_simulator_tasks()` must still return summary data from the stored task summary and snapshot, not the changed template.

Core assertion:

```python
self.assertEqual(task["simcReportSummary"]["build"]["specName"], "元素")
self.assertNotEqual(task["simcReportSummary"]["build"]["specName"], "changed-after-submit")
```

- [ ] **Step 2: Add a detail snapshot test**

Create a queued/completed task whose `request_json.templateContext` has copied template metadata. Mutate `user_build_templates.metadata_json` after task creation. `get_simulator_task()` must return the task snapshot, not the updated template row.

- [ ] **Step 3: Run focused tests**

Run:

```bash
python -m unittest tests.news_backend_test
node --test tests/simulator-page.test.js tests/frontend-api-client.test.js
```

Expected: pass.

### Task 6: Prepare Chickenbro Strong-Identity And Multi-Session Schema

**Files:**

- Modify: `server/news_backend.py`
- Modify: `tests/news_backend_test.py`
- Update: `docs/database-architecture.md`

- [ ] **Step 1: Add tests for no-guest future policy switches**

Add tests that document current behavior and future switch:

```python
    def test_chickenbro_guest_policy_is_explicit(self):
        with self.assertRaises(PermissionError):
            self.backend.resolve_chickenbro_user(access_token="", guest_id="", create_guest=False)
```

Add a separate test for current explicit guest behavior so the later strong-login cutover can change one gate intentionally.

- [ ] **Step 2: Add action-list and worker-ready fields without changing execution**

Add SQLite-compatible columns or JSON fields only if needed by the public contract. Prefer `payload_json` for current SQLite compatibility and model the richer shape in PostgreSQL schema.

Fields reserved in PostgreSQL:

- `app.chickenbro_actions.session_id`
- `app.chickenbro_actions.user_id`
- `app.chickenbro_actions.status`
- `app.chickenbro_actions.evidence_refs_json`
- `app.agent_jobs.attempt`
- `app.agent_jobs.locked_by`
- `app.agent_jobs.heartbeat_at`
- `app.agent_jobs.cancel_requested`
- `app.agent_jobs.last_error`

- [ ] **Step 3: Run Chickenbro tests**

Run:

```bash
python -m unittest tests.news_backend_test
node --test tests/simulator-page.test.js
```

Expected: pass.

### Task 7: Add Migration And Cutover Runbook

**Files:**

- Create: `docs/postgres-identity-migration-runbook.md`
- Modify: `docs/database-architecture.md`
- Modify: `docs/roadmap.md`

- [ ] **Step 1: Write runbook sections**

The runbook must include:

- Local-only Phase 1 setup.
- SQLite backup command.
- PG database and schema setup.
- Shadow migration command templates with no production execution.
- Verification commands.
- Rollback decision tree.
- Explicit "requires owner approval" gates for production backup, production PG creation, data copy, systemd switch, and deployment.

- [ ] **Step 2: Update database architecture doc**

Add a section naming the dual-runtime transition:

- SQLite remains default.
- PG schema files are target-state artifacts.
- `WOW_DATABASE_URL` is not a production cutover switch until the runbook says so.

- [ ] **Step 3: Update roadmap evidence only after implementation lands**

Do not mark Phase 1 complete until tests pass. When complete, add a concise evidence row to `docs/roadmap.md` with file and test evidence.

### Task 8: Optional PostgreSQL Integration Test Gate

**Files:**

- Create: `tests/postgres_integration_test.py`
- Update: `docs/postgres-identity-migration-runbook.md`

- [ ] **Step 1: Add skipped-by-default integration test**

Use `WOW_PG_TEST_DSN`. If it is missing, skip.

```python
import os
import unittest


@unittest.skipUnless(os.environ.get("WOW_PG_TEST_DSN"), "WOW_PG_TEST_DSN is not configured")
class PostgresIntegrationTest(unittest.TestCase):
    def test_postgres_migration_file_applies(self):
        import psycopg
        from pathlib import Path

        sql = Path("server/migrations/postgres/0001_identity_app_content_cache_knowledge_analytics_ops.sql").read_text(encoding="utf-8")
        with psycopg.connect(os.environ["WOW_PG_TEST_DSN"]) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                cur.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'identity'")
                self.assertIsNotNone(cur.fetchone())
```

- [ ] **Step 2: Document that this test is optional until PG is provisioned**

Run without DSN:

```bash
python -m unittest tests.postgres_integration_test
```

Expected: skipped, not failed.

Run with DSN:

```bash
$env:WOW_PG_TEST_DSN="postgresql://wow_migrator@localhost/wow_test"
python -m unittest tests.postgres_integration_test
```

Expected: pass only on an explicitly configured local PG test database.

## Verification Ladder

Run after Phase 1 implementation:

```bash
python -m unittest tests.database_adapter_test
python -m unittest tests.postgres_schema_test
python -m unittest tests.postgres_personal_store_test
python -m unittest tests.postgres_analytics_store_test
python -m unittest tests.postgres_content_store_test
python -m unittest tests.news_backend_test
python -m unittest tests.websim_payload_test
python -m unittest tests.stat_weights_payload_test
python -m unittest tests.raiderio_payload_test
python -m unittest tests.gear_observed_backfill_test
node --test tests/build-template-storage.test.js tests/profile-auth.test.js tests/frontend-api-client.test.js tests/simulator-page.test.js tests/builds-page.test.js
git diff --check
```

Optional when local PG exists:

```bash
python -m unittest tests.postgres_integration_test
```

Do not use production smoke, SSH, deploy scripts, systemd edits, or remote DB writes in Phase 1 unless the owner explicitly requests them.

## Can Implement Directly After Confirmation

These items are safe to start once the owner confirms Phase 1 because they do not require production access, deployment, or a PostgreSQL server:

- Add `server/db.py` with SQLite-first database configuration helpers.
- Add `tests/database_adapter_test.py` to prove SQLite remains the default and PostgreSQL requires explicit `WOW_DATABASE_URL`.
- Route `server/news_backend.py::db_connection()` through the adapter while rejecting PostgreSQL runtime in Phase 1.
- Add `server/migrations/postgres/0001_identity_app_content_cache_knowledge_analytics_ops.sql` as a target-state artifact only.
- Add `tests/postgres_schema_test.py` to validate schema text for identity ownership, SimC snapshot fields, Chickenbro session/worker-ready fields, content/cache/knowledge/analytics/ops coverage, and disabled embedding status.
- Add SQLite-compatible `simulator_tasks` worker-ready columns if the owner confirms that Phase 1 should include this compatibility migration.
- Add or tighten SimC task summary and snapshot regression tests without changing the public SimC execution model.
- Add `docs/postgres-identity-migration-runbook.md` with local-only setup, backup, shadow migration, verification, rollback, and explicit production approval gates.
- Update `docs/database-architecture.md` to describe the dual-runtime transition.
- Update `docs/roadmap.md` only after Phase 1 verification passes.

## Must-Decide Before Code Starts

- Dependency location for `psycopg` v3, because this repo currently has no Python requirements file.
- Final env names: recommended `WOW_DATABASE_URL` for PG and existing `WOW_NEWS_DB` for SQLite fallback.
- Whether Phase 1 should only add schema artifacts or also add SQLite worker-ready columns.
- Whether explicit guest writes remain temporarily allowed in SQLite after Phase 1, or are blocked behind a feature flag.
- Whether `identity.users.id` should preserve existing integer user IDs during migration or use fresh UUIDs with a mapping table.
- Whether local PG integration tests should be optional via `WOW_PG_TEST_DSN` or required for every development environment.

## Online Risk Register

- systemd service files currently point at a SQLite file path and must not be switched without a production cutover plan.
- Sync timers and backfill scripts use file locks and SQLite backup habits; PG requires separate lock/advisory-lock and `pg_dump` runbooks.
- WebSim/Season Data Cache is large and evidence-sensitive; migration must produce source/variant/mod option counts and blocker samples before trust.
- Old tokens are intentionally not migrated; cutover causes visible re-login.
- Guest tasks and guest Chickenbro sessions are intentionally not migrated; support/debug messaging must be ready.
- SQLite JSON and introspection SQL appear in data scripts and tests; moving runtime before isolating them risks silent data drift.
