# Database Architecture Governance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the backend database understandable, account-safe, and ready for user CRUD without prematurely replacing SQLite.

**Architecture:** Keep the current single SQLite database for the near term, but add explicit domain boundaries, migration tracking, ownership rules, and operational safeguards. Treat user data as durable, WebSim/game data as rebuildable cache, analytics as append/rollup data, and sync state as operational metadata.

**Tech Stack:** Python stdlib HTTP backend, SQLite WAL, WeChat login tokens, mini-program `wx` storage/API client, Node tests, Python `unittest`.

## Current State

The backend currently stores all persistent data in `WOW_NEWS_DB`, defaulting to `server/data/wow_news.sqlite3` locally and `/opt/wow-mini-program/server/data/wow_news.sqlite3` in systemd.

Current table groups:

| Domain | Tables | Durability |
| --- | --- | --- |
| News | `news_articles`, `news_refresh_runs` | Rebuildable from collectors plus seed/fallback data. |
| Account/Auth | `wechat_users`, `auth_tokens` | Durable user identity and session data. |
| User tasks | `simulator_tasks` | Durable user-owned history. |
| WebSim/game cache | `websim_*` tables | Mostly rebuildable cache, except manually curated community template fixtures until source sync is stable. |
| Analytics | `analytics_events`, `analytics_user_links`, `analytics_daily_metrics` | Append/rollup data; can be archived. |

The current approach is acceptable for MVP, but the project now needs schema governance before adding account-backed templates, roles, favorites, subscriptions, and richer task history.

## Target Rules

- Do not migrate away from SQLite as the first move.
- Add migration/version tracking before adding more user-owned tables.
- Enable SQLite foreign key enforcement in every backend connection.
- Every user-write table must have a clear owner: usually `user_id`, with an explicit guest policy only where product needs it.
- Keep public/reference data separate from user-private data in naming, tests, and access paths.
- Treat `websim_*` data as cache unless a table is explicitly marked curated/durable.
- Avoid adding more opaque `payload_json` as the only source of truth for CRUD-heavy user data.
- Add backups before any migration touching user-owned data.

## Proposed Domain Model

| Domain | Prefix / Tables | Owner rule | Notes |
| --- | --- | --- | --- |
| Identity | `wechat_users`, `auth_tokens` | `auth_tokens.user_id -> wechat_users.id` | Existing base. Add token cleanup and indexes if needed. |
| User content | `user_build_templates`, `user_favorites`, `user_characters`, `user_subscriptions` | Required `user_id` | New CRUD surface. No cross-account reads/writes. |
| User jobs | `simulator_tasks`, future `analysis_jobs` | Required `user_id` or explicit guest user | Existing `simulator_tasks` already has owner filtering. |
| Reference content | `news_*`, `websim_community_talent_templates` | No user owner | Public read model, source/status must be visible. |
| Game cache | `websim_items`, `websim_talents`, `websim_loot`, `websim_season_*`, etc. | No user owner | Rebuildable from SimC/Blizzard/Wago/manual fixtures. |
| Analytics | `analytics_*` | Optional `user_id`; hashed client/session IDs | Do not store openid in event payload. |
| Ops | `schema_migrations`, `websim_sync_state` | No user owner | Schema and sync control plane. |

## Implementation Tasks

### Task 1: Add a Database Architecture Doc

**Files:**
- Create: `docs/database-architecture.md`
- Reference: `server/news_backend.py`
- Reference: `server/websim_payload.py`
- Reference: `server/analytics.py`

**Step 1: Write the domain inventory**

Document each table group, owner rule, rebuildability, and backup requirement.

**Step 2: Add an ownership matrix**

Include a matrix for upcoming CRUD features:

| Feature | Storage | Owner | Guest behavior |
| --- | --- | --- | --- |
| Talent template | `user_build_templates` | Required | Local preview only, login before sync. |
| Gear template | `user_build_templates` | Required | Local preview only, login before sync. |
| Character profile | `user_characters` | Required | None. |
| Favorite spec | `user_favorites` | Required | None. |
| Subscription | `user_subscriptions` | Required | None. |

**Step 3: Verify docs**

Run:

```bash
rg -n "user_build_templates|schema_migrations|foreign key|owner" docs/database-architecture.md
```

Expected: the new doc names the owner and migration rules explicitly.

### Task 2: Introduce Schema Migration Tracking

**Files:**
- Modify: `server/news_backend.py`
- Test: `tests/news_backend_test.py`

**Step 1: Write a failing test**

Add a test that calls `init_db()` and asserts the migration table exists:

```python
def test_schema_migrations_table_is_created(self):
    with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        ).fetchall()
    self.assertEqual(len(rows), 1)
```

Run:

```bash
python3 -m unittest tests.news_backend_test.NewsBackendTest.test_schema_migrations_table_is_created
```

Expected before implementation: FAIL.

**Step 2: Implement migration metadata**

Add `ensure_schema_migrations(conn)` and call it from `init_db()` before domain table creation:

```python
def ensure_schema_migrations(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )
```

**Step 3: Verify**

Run:

```bash
python3 -m unittest tests.news_backend_test.NewsBackendTest.test_schema_migrations_table_is_created
```

Expected: PASS.

### Task 3: Enforce Foreign Keys on Every Connection

**Files:**
- Modify: `server/news_backend.py`
- Modify: `server/websim_payload.py`
- Test: `tests/news_backend_test.py`
- Test: `tests/websim_payload_test.py`

**Step 1: Write a failing backend test**

Add a test that inserts an invalid `simulator_tasks.user_id` and expects SQLite to reject it after `PRAGMA foreign_keys = ON`.

**Step 2: Centralize SQLite pragmas**

先全仓搜索生产代码里的 `sqlite3.connect()`，确认除 `server/news_backend.py` 和 `server/websim_payload.py` 外没有其他绕过统一连接入口的调用；测试文件里的直连只用于断言和 fixture，不作为生产连接入口。

In `server/news_backend.py`, update `db_connection()` to run:

```python
conn.execute("PRAGMA busy_timeout = 30000")
conn.execute("PRAGMA journal_mode = WAL")
conn.execute("PRAGMA foreign_keys = ON")
```

In `server/websim_payload.py`, update standalone `sqlite3.connect()` sync paths to also enable `foreign_keys`. If future production files add direct SQLite connections, Task 3 must cover them in the same pass.

**Step 3: Verify**

Run:

```bash
python3 -m unittest tests.news_backend_test.NewsBackendTest.test_simulator_tasks_reject_unknown_user
python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_sync_connection_enables_foreign_keys
```

Expected: both PASS.

### Task 4: Add Account-Owned Build Template Tables

**Files:**
- Modify: `server/news_backend.py`
- Test: `tests/news_backend_test.py`

**Step 1: Write failing schema tests**

Assert `user_build_templates` exists and has:

- `id`
- `user_id`
- `template_type`
- `title`
- `class_key`
- `spec_key`
- `hero_key`
- `scenario_key`
- `raw_string`
- `simc_lines_json`
- `status`
- `payload_json`
- `created_at`
- `updated_at`

**Step 2: Implement table and indexes**

Add the table with:

```sql
FOREIGN KEY(user_id) REFERENCES wechat_users(id)
```

Add indexes:

```sql
CREATE INDEX IF NOT EXISTS idx_user_build_templates_user_type
ON user_build_templates(user_id, template_type, updated_at)
```

**Step 3: Verify**

Run:

```bash
python3 -m unittest tests.news_backend_test.NewsBackendTest.test_user_build_templates_schema
```

Expected: PASS.

### Task 5: Add Account-Owned Template CRUD APIs

**Files:**
- Modify: `server/news_backend.py`
- Modify: `pages/common/api-client.js`
- Modify: `pages/common/build-template-storage.js`
- Test: `tests/news_backend_test.py`
- Test: `tests/frontend-api-client.test.js`
- Test: `tests/build-template-storage.test.js`

**Step 1: Write backend permission tests**

Cover:

- Creating a template requires Bearer auth.
- Listing returns only current user's templates.
- Updating another user's template returns unauthorized/not found.
- Deleting another user's template returns unauthorized/not found.

**Step 2: Add endpoints**

Use account-owned routes:

- `GET /api/me/build-templates`
- `POST /api/me/build-templates`
- `PUT /api/me/build-templates?id=...`
- `DELETE /api/me/build-templates?id=...`

All routes must authenticate through `bearer_token_from_headers()` and `authenticate_token()`.

**Step 3: Update mini-program storage boundary**

Keep current local storage as offline draft/cache, but add explicit sync functions:

- `listRemoteBuildTemplates()`
- `saveRemoteBuildTemplate()`
- `deleteRemoteBuildTemplate()`
- `migrateLocalTemplatesToAccount()`

**Step 4: Verify**

Run:

```bash
node --test tests/build-template-storage.test.js tests/frontend-api-client.test.js
python3 -m unittest tests.news_backend_test.NewsBackendTest
```

Expected: relevant auth/template tests PASS.

### Task 6: Add Backup and Migration Runbook

**Files:**
- Modify: `docs/remote-debugging.md`
- Modify: `README.md`

**Step 1: Document backup command**

Add the current SQLite backup shape:

```bash
sqlite3 /opt/wow-mini-program/server/data/wow_news.sqlite3 ".backup '/var/lib/wow-backend/backups/wow_news-$(date +%Y%m%d-%H%M%S).sqlite3'"
```

**Step 2: Document pre-migration checklist**

Checklist:

- Stop write-heavy sync timer if needed.
- Backup SQLite file.
- Run migration locally against a copy.
- Run targeted auth/template/task tests.
- Smoke `/health`, `/api/news/home`, `/api/websim/bootstrap`, `/api/simulator/tasks`.

**Step 3: Verify**

Run:

```bash
rg -n "sqlite3 .*\\.backup|pre-migration|WOW_NEWS_DB" README.md docs/remote-debugging.md
```

Expected: backup and migration checks are documented.

### Task 7: Decide When to Split Storage

**Files:**
- Modify: `docs/database-architecture.md`
- Modify: `docs/roadmap.md`

**Step 1: Add split criteria**

Do not split the database until one of these is true:

- Analytics volume slows user CRUD.
- WebSim sync locks block interactive requests.
- Backup/restore needs differ materially between durable user data and rebuildable cache.
- The app needs managed DB features: online migrations, replicas, stronger access controls, or observability.

**Step 2: Define likely split path**

Preferred future split:

- `app.sqlite3` or Postgres: identity, user templates, roles, favorites, subscriptions, task history.
- `cache.sqlite3`: WebSim/game cache, source sync state.
- `analytics.sqlite3` or external warehouse: events and rollups.

**Step 3: Verify**

Run:

```bash
rg -n "app.sqlite3|cache.sqlite3|analytics.sqlite3|Postgres|split criteria" docs/database-architecture.md docs/roadmap.md
```

Expected: split criteria are explicit, not implied.

## Execution Order

1. Documentation and domain inventory.
2. Migration table and foreign key enforcement.
3. Account-owned build template table.
4. Template CRUD APIs and mini-program sync.
5. Backup/runbook updates.
6. Split criteria review after real usage grows.

## Acceptance Criteria

- `docs/database-architecture.md` explains current and target DB boundaries.
- `schema_migrations` exists.
- SQLite foreign keys are enforced on backend and sync connections.
- New user-owned tables require `user_id`.
- Template CRUD cannot cross account boundaries.
- Local templates can be migrated to the logged-in WeChat account.
- Backup and rollback commands are documented.
- The roadmap clearly states that SQLite remains acceptable short term, with defined split criteria.
