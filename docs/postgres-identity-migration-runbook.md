# PostgreSQL Identity Migration Runbook

This runbook governs the phased PostgreSQL and strong-identity migration. Phase 1 is local-only: it adds compatibility code, target schema artifacts, tests, and rollback boundaries while keeping SQLite as the runtime database. Later phases may provision PostgreSQL and run approved shadow migrations, but runtime cutover still requires a dated cutover section and verified rollback path.

## Non-Negotiable Gates

Owner approval is required before any of these actions:

- Production SQLite backup.
- Production PostgreSQL database creation.
- Production data copy or shadow migration.
- systemd environment switch to `WOW_DATABASE_URL`.
- Deployment or service restart.

Do not treat `WOW_DATABASE_URL` as a production cutover switch until this runbook is updated with a dated cutover section and the owner approves that section.

2026-06-27 owner note: for this active goal, the owner authorized cloud-server PostgreSQL provisioning, planned migration rehearsal, and execution according to the agent's plan without another confirmation. This authorization has been used for PostgreSQL installation, database/schema provisioning, `wow_test` / `wow_prod` guarded shadow migrations, public content/cache data copy, and SQLite-compatible `wow-backend` deployment/restart. It has not been used to switch `WOW_DATABASE_URL` or production runtime to PostgreSQL.

## Phase 1 Local Setup

Phase 1 uses SQLite by default:

```bash
python -m unittest tests.database_adapter_test
python -m unittest tests.postgres_schema_test
python -m unittest tests.news_backend_test.NewsBackendTest.test_init_db_records_schema_migrations_and_enforces_foreign_keys
python -m unittest tests.news_backend_test.NewsBackendTest.test_simulator_tasks_include_worker_ready_columns
```

Expected result:

- `WOW_NEWS_DB` continues to select the SQLite file.
- `WOW_DATABASE_URL` selects PostgreSQL config but `server.news_backend.db_connection()` rejects PostgreSQL runtime with `PostgreSQL runtime is not enabled in this phase`.
- `server/migrations/postgres/0001_identity_app_content_cache_knowledge_analytics_ops.sql` exists as a target-state artifact.
- `simulator_tasks` keeps current SQLite behavior and adds worker-ready compatibility columns.

## SQLite Backup Template

Local backup:

```bash
powershell -NoProfile -Command "Copy-Item -LiteralPath $env:WOW_NEWS_DB -Destination ($env:WOW_NEWS_DB + '.backup-' + (Get-Date -Format yyyyMMddTHHmmssZ))"
```

Production backup requires owner approval before running:

```bash
ssh wow-lighthouse 'sudo install -d -m 700 -o ubuntu -g ubuntu /opt/wow-mini-program/backups && sudo cp /opt/wow-mini-program/server/data/wow_news.sqlite3 /opt/wow-mini-program/backups/wow_news-before-postgres-identity-$(date -u +%Y%m%dT%H%M%SZ).sqlite3'
```

## PostgreSQL Schema Setup Template

Use only a local or disposable test database unless the owner explicitly approves production work:

```bash
createdb wow_pg_identity_local
psql wow_pg_identity_local -f server/migrations/postgres/0001_identity_app_content_cache_knowledge_analytics_ops.sql
psql wow_pg_identity_local -f server/migrations/postgres/0002_runtime_privileges.sql
```

Optional integration test:

```bash
python -m unittest tests.postgres_integration_test
```

Expected without `WOW_PG_TEST_DSN`: skipped.

Expected with explicit local DSN:

```bash
$env:WOW_PG_TEST_DSN="postgresql://wow_migrator@localhost/wow_pg_identity_local"
python -m unittest tests.postgres_integration_test
```

## Phase 2 Identity Shadow Plan

The identity shadow plan is a read-only inventory step. It does not connect to PostgreSQL and does not write to SQLite.

Run it against a local SQLite file or an approved backup copy:

```bash
python server/migrations/postgres/identity_shadow_plan.py path/to/wow_news.sqlite3
```

The JSON output includes:

- `users`: formal `wechat_users` mapped to stable PostgreSQL UUIDs.
- `userIdentities`: provider identity rows for `wechat_openid` and, when present, `wechat_unionid`.
- `ownerTables`: formal and guest-owned row counts for `user_build_templates`, `simulator_tasks`, `chickenbro_sessions`, `chickenbro_messages`, `agent_jobs`, and `chickenbro_user_profiles`.
- `skipped.guestUsers`: guest identities intentionally excluded from migration.
- `skipped.authTokens`: legacy tokens intentionally excluded from migration.

Expected policy:

- Migrate formally authenticated users only.
- Do not migrate guest users.
- Do not migrate legacy auth tokens.
- Count guest-owned assets for support and product messaging, but do not copy them into PG.
- Use stable generated PG UUIDs so repeated dry runs produce the same mapping.

## Phase 2 Data Copy Dry Run

The data copy plan extends the identity shadow inventory into reviewable JSON or SQL. It still does not connect to PostgreSQL and does not write to SQLite.

JSON review:

```bash
python server/migrations/postgres/data_copy_plan.py path/to/wow_news.sqlite3
```

SQL review:

```bash
python server/migrations/postgres/data_copy_plan.py --format sql path/to/wow_news.sqlite3 > postgres-copy-dry-run.sql
```

The current dry-run copy plan includes formal-owner rows for:

- `identity.users`
- `identity.user_identities`
- `app.build_templates`
- `app.simulator_tasks`
- `app.chickenbro_sessions`
- `app.chickenbro_messages`
- `app.agent_jobs`
- `knowledge.user_context_summaries`

It also includes public/non-owner rows for:

- `content.sources`
- `content.raw_articles`
- `content.article_evidence`
- `content.articles`
- `content.discovery_queue`
- `content.refresh_runs`
- `cache.websim_sync_state`
- `cache.websim_items`
- `cache.websim_season_state`
- `cache.websim_season_dungeons`
- `cache.websim_instances`
- `cache.websim_encounters`
- `cache.websim_loot`
- `cache.raiderio_cache`

The plan excludes:

- guest users,
- guest-owned assets,
- legacy auth tokens,
- production execution.

The SQL output is intentionally plain review SQL. Do not run it against production. A future executable migration must add transaction ownership, conflict policy, count verification, checksum verification, and explicit owner approval before any production database is touched.

## Phase 3 Guarded Shadow Migration

`shadow_migrate.py` executes the reviewed data-copy plan against an approved non-runtime PostgreSQL database. It:

- Read from a copied SQLite file or read-only SQLite connection.
- Writes only to a local or approved PostgreSQL target.
- Migrate formal authenticated users only.
- Exclude guest users, guest SimC tasks, guest Chickenbro sessions, and old auth tokens.
- Verifies copied row counts by target table before committing.
- Rolls back on count mismatch or PostgreSQL errors.
- Blocks production-like database names such as `wow_prod` unless an operator passes `--allow-production`.
- Stop on missing owner references instead of inventing users.
- Uses table-specific idempotency keys where the target schema has a natural key, for example `content.sources.source_key`, `cache.websim_season_state.key`, and `cache.raiderio_cache.cache_key`.
- Refreshes `content.refresh_runs` sequence state after copying historical ids.

Dry-run command:

```bash
python server/migrations/postgres/shadow_migrate.py --sqlite path/to/wow_news.sqlite3 --postgres "$env:WOW_PG_TEST_DSN" --dry-run
```

Execution command for a staging/test database:

```bash
python server/migrations/postgres/shadow_migrate.py --sqlite path/to/wow_news.sqlite3 --postgres "$env:WOW_PG_TEST_DSN"
```

## Cloud Provision Evidence 2026-06-27

Completed under explicit owner authorization for this active goal:

- Installed PostgreSQL `16.14 (Ubuntu 16.14-0ubuntu0.24.04.1)` on `wow-lighthouse`.
- Confirmed PostgreSQL listens only on `127.0.0.1:5432`.
- Created roles `wow_migrator` and `wow_app`.
- Stored local PostgreSQL credentials in `/etc/wow-postgres/credentials.env` with `root:ubuntu` ownership and `0640` permissions.
- Created databases `wow_dev`, `wow_test`, and `wow_prod`.
- Applied `0001_identity_app_content_cache_knowledge_analytics_ops.sql`, `0002_runtime_privileges.sql`, `0003_build_template_config_hash_unique.sql`, `0004_chickenbro_runtime_fields.sql`, `0005_content_runtime_fields.sql`, and `0006_websim_season_loot_cache.sql` to all three databases.
- Verified `wow_test` can connect as `wow_migrator` and `wow_app`; `wow_app` can insert into `ops.sync_runs` inside a rollback-only smoke transaction.
- Created source SQLite backup `/opt/wow-mini-program/backups/wow_news-before-postgres-shadow-20260627T152530Z.sqlite3`.
- Generated copy-plan summary from that backup: `formalUsers=1`, `guestUsers=12`, `totalRows=10`, `identity.users=1`, `identity.user_identities=1`, `app.simulator_tasks=8`, `guestOwnedRows=44`, `authTokens=0`.
- Executed guarded shadow migration only into `wow_test`; result `verifiedRows=10`, `identity.users=1`, `identity.user_identities=1`, `app.simulator_tasks=8`, `guest_identity_rows=0`, `sync_runs=1`.

Correction on 2026-06-28:

- A `wow_prod` non-runtime shadow migration precheck found the legacy fixed guest openid `guest-simulator` was not covered by the old `guest-simulator-` prefix filter. The apparent `formalUsers=1` / `app.simulator_tasks=8` rows were guest-owned rows and should not have been migrated.
- Added a regression test and fixed `server/migrations/postgres/identity_shadow_plan.py` so both `guest-simulator` and `guest-simulator-*` are excluded.
- Cleaned the erroneous shadow copy from `wow_test` and `wow_prod`: each cleanup deleted `1` guest user and `1` old `postgres_shadow_migration` sync run, cascading the guest-owned simulator tasks.
- Re-ran the corrected shadow migration from `/opt/wow-mini-program/backups/wow_news-before-wow-prod-shadow-20260627T174600Z.sqlite3` into `wow_test` and `wow_prod`. Both corrected runs produced `verifiedRows=0`, `rowsByTable={}`, `guestUsers=13`, `guestOwnedRows=52`, and `guest_identity_rows=0`.

Not done:

- No `WOW_DATABASE_URL` was added to `/etc/wow-backend.env`.
- A SQLite-compatible code deployment/restart was performed after backing up SQLite; no systemd PostgreSQL runtime switch was performed.
- No identity or personal app rows are currently copied into `wow_prod`; `identity.users`, `identity.user_identities`, and personal app tables remain empty except for temporary smoke rows that were cleaned up. Public content/cache rows are covered by the dedicated evidence section below.

## SQLite-Compatible Deployment Evidence 2026-06-27

Completed under the same active-goal authorization:

- Created pre-deploy SQLite backup `/opt/wow-mini-program/backups/wow_news-before-postgres-compat-deploy-20260627T153422Z.sqlite3`.
- Deployed the compatibility-layer code while keeping `/etc/wow-backend.env` free of `WOW_DATABASE_URL`.
- Fixed and redeployed a direct-script import regression for the systemd entrypoint (`python3 /opt/wow-mini-program/server/news_backend.py`).
- Restarted `wow-backend`; service remained `active`, listening on `127.0.0.1:8787`.
- Smoke verified `wow-backend` active plus `GET /api/builds/home`, `GET /api/news/home`, and `GET /api/data/health`.
- Verified production SQLite `simulator_tasks` has `queued_at`, `started_at`, `finished_at`, `attempt`, `locked_by`, `heartbeat_at`, `cancel_requested`, and `last_error`.
- Superseded by the 2026-06-28 correction above: `wow_test` and `wow_prod` now have no migrated identity or simulator task business rows from the shadow backup, and each has a corrected 0-row `postgres_shadow_migration` sync run.

## PostgreSQL Personal Runtime Seam Evidence 2026-06-27

Completed under the same active-goal authorization:

- Added `server/postgres_personal_store.py` as a PostgreSQL repository for strong-identity personal assets.
- Added `WOW_DATABASE_RUNTIME=postgres_personal` as a hybrid rehearsal mode: personal identity/template/SimC task paths can use PostgreSQL while public content/cache paths still use SQLite.
- Auth tokens are stored in PostgreSQL as SHA-256 token hashes, not raw bearer tokens.
- Build templates dedupe by `(user_id, template_type, config_hash)` through `0003_build_template_config_hash_unique.sql`, allowing the same visible name for different saved configurations.
- SimC task enqueue/list/detail can use PostgreSQL `app.simulator_tasks` JSONB request/analysis/summary snapshots; task details do not depend on later template edits.
- Post-cutover CR added PG-backed SimC runner coverage: `run_simcraft_template_task` now uses the personal store in `postgres_personal` runtime to read queued tasks, write running summaries, and persist completed/failed summaries without falling back to the SQLite task table.
- Chickenbro keeps the current web-backend execution model in this phase. `0004_chickenbro_runtime_fields.sql` adds `app.chickenbro_messages.agent_job_id` and `app.agent_jobs.bounded_context_json`; the hybrid runtime seam now has PG repository methods for sessions, messages, jobs, and structured user context.
- Cloud `wow_test` smoke created a temporary PG user, authenticated by hashed token, updated profile metadata, saved two same-name/different-config templates, inserted/listed/read an active SimC task, then deleted the temporary user. Result: `authed=true`, `updatedNickname=Codex Smoke`, `templateCount=2`, `taskRows=1`, `activeRows=1`, `detailFound=true`.
- Deployed the SQLite-compatible personal-store code after backing up SQLite to `/opt/wow-mini-program/backups/wow_news-before-postgres-personal-store-deploy-20260627T161245Z.sqlite3`; `wow-backend` restarted with `WOW_DATABASE_URL` still absent, `GET /api/builds/home`, `GET /api/news/home`, and `GET /api/data/health` returned usable JSON, and `server/postgres_personal_store.py` imports on the cloud host.

## PostgreSQL Chickenbro Runtime Seam Evidence 2026-06-28

Completed under the same active-goal authorization:

- Added PG-backed Chickenbro repository methods in `server/postgres_personal_store.py` for `knowledge.user_context_summaries`, `app.chickenbro_sessions`, `app.chickenbro_messages`, and `app.agent_jobs`.
- Routed `create_chickenbro_session`, `send_chickenbro_message`, `get_chickenbro_session`, `get_chickenbro_job`, and PG guest lookup through the personal store when `WOW_DATABASE_RUNTIME=postgres_personal`.
- The route keeps the current synchronous web-backend agent execution model: bounded context is still assembled in `server/news_backend.py`, Codex/fallback behavior is unchanged, and only the runtime persistence target changes in hybrid mode.
- Owner isolation is enforced by `user_id` filters on session/message/job reads and updates; a `wow_test` smoke confirmed another user cannot read the smoke job.
- Cloud `wow_test` smoke created temporary PG users, authenticated by hashed token, stored a Chickenbro profile summary, created a session, inserted user and assistant messages linked to an agent job, updated the job to `succeeded`, verified `messageCount=2`, `assistantAgentJob=true`, `ownerIsolation=true`, then deleted the temporary users.
- Deployed the SQLite-compatible code to `/opt/wow-mini-program` after backing up current runtime files under `/opt/wow-mini-program/.codex-backups/20260628003357`; a follow-up Chickenbro default-title encoding fix backed up `news_backend.py` under `/opt/wow-mini-program/.codex-backups/20260628004120`. `wow-backend` restarted with `WOW_DATABASE_URL` still absent. Smoke: `backend=active`, `env_database_url=absent`, `data_health=partial`, `builds_home=ok`, `news_home=ok`.
- Verified PG state after smoke cleanup: `wow_test_counts=4,1,0,0` and `wow_prod_counts=4,0,0,0` for `schema_migrations,identity.users,app.chickenbro_sessions,codex-chickenbro-smoke-identities`.

## PostgreSQL Analytics Runtime Seam Evidence 2026-06-28

Completed under the same active-goal authorization:

- Added `server/postgres_analytics_store.py` for the `analytics.events`, `analytics.user_links`, and `analytics.daily_metrics` target schema.
- Routed `/api/analytics/events` through the PG analytics store when `WOW_DATABASE_RUNTIME=postgres_personal`; SQLite remains the default when the runtime flag is absent.
- Routed admin analytics `summary`, `pages`, `features`, `events`, `users`, `rollup`, and `simulator` through the PG analytics store in hybrid mode. The simulator report reads `app.simulator_tasks.summary_json/request_json/analysis_json` snapshots plus `analytics.events` counters, so admin task reporting no longer depends on the SQLite task table when `WOW_DATABASE_RUNTIME=postgres_personal`.
- PG events use deterministic UUIDs derived from client event ids for dedupe, store `clientIdHash`, `sessionIdHash`, page, platform, and sanitized properties in `payload_json`, and do not store raw `prompt`, `openid`, tokens, or SimC profile text.
- Local TDD evidence for the simulator cross-read seam: `tests.postgres_analytics_store_test.PostgresAnalyticsStoreTest.test_simulator_report_reads_app_tasks_snapshots_and_event_jsonb` failed before implementation with missing `analytics_simulator`, and `tests.database_adapter_test.DatabaseAdapterTest.test_news_backend_routes_admin_analytics_simulator_to_postgres_store` failed because the route still returned SQLite fallback data; both passed after the PG store method and route branch were added.
- Cloud `wow_test` smoke inserted two unique analytics events plus one duplicate, verified `inserted=2`, `ignored=1`, `summaryPvAtLeastOne=true`, `topEventSeen=true`, `pageSeen=true`, `featureSeen=true`, `promptLeaked=false`, `openidLeaked=false`, then deleted the smoke events and user.
- Verified smoke cleanup: `analytics_smoke_counts=0,0` for temporary analytics events and identities.
- Deployed the SQLite-compatible code to `/opt/wow-mini-program` after backing up current runtime files under `/opt/wow-mini-program/.codex-backups/20260628004959`; `wow-backend` restarted with `WOW_DATABASE_URL` still absent. Smoke: `backend=active`, `env_database_url=absent`, `data_health=partial`, `builds_home=ok`, `news_home=ok`.
- Deployed the simulator cross-read route/store follow-up after backing up runtime files under `/opt/wow-mini-program/.codex-backups/20260627172857`; a psycopg placeholder regression was caught by `wow_test` smoke and fixed after backing up the intermediate store under `/opt/wow-mini-program/.codex-backups/20260627173249`.
- Cloud `wow_test` backend-level hybrid smoke inserted a temporary PG user, simulator task snapshot, and `simc_smoke_pg` analytics event, then called `/api/admin/analytics/simulator` through `server.news_backend.admin_analytics_response` with `WOW_DATABASE_RUNTIME=postgres_personal`. Result: `status=200`, `taskCount=1`, `completedSimulations=1`, `profileSource=summary-smoke`, `specId=arcane-smoke`, `dps=654321`, `eventSeen=true`, cleanup `cleanupCounts=[1,1,1,1]`.
- Restarted production `wow-backend` without adding `WOW_DATABASE_URL`; smoke verified `systemctl is-active wow-backend=active`, `env_database_url=absent`, `builds_home=ok`, `news_home=ok`, and `/api/data/health` returned `data_health=ok`.

## PostgreSQL Content Runtime Seam Evidence 2026-06-28

Completed under the same active-goal authorization:

- Added `server/postgres_content_store.py` for the `content.sources`, `content.raw_articles`, `content.article_evidence`, `content.articles`, `content.discovery_queue`, and `content.refresh_runs` target schema.
- Added `0005_content_runtime_fields.sql` for current public-article runtime fields, discovery queue, refresh runs, and sequence grants required by the `wow_app` role. Root cause for the sequence grant was found during cloud smoke: `content.refresh_runs` uses a `bigserial` sequence created after the original `0002` runtime grants.
- Routed `refresh_articles`, `latest_refresh_state`, `latest_refresh_run_payload`, `load_articles`, and `get_article_detail` through the PG content store when `WOW_DATABASE_RUNTIME=postgres_personal`; SQLite remains the default and production still does not set `WOW_DATABASE_URL`.
- Cloud `wow_test` direct content-store smoke verified discovery queue write/read, raw article/evidence persistence, public article read/detail, refresh run insert/read, `translationFidelity=source_translation`, and cleanup `cleanupCounts=[0,0,0,0]`.
- Cloud backend-level hybrid smoke imported `server/news_backend.py` with `WOW_DATABASE_URL=$WOW_PG_APP_DSN_TEST` and `WOW_DATABASE_RUNTIME=postgres_personal`, patched the collector to a single temporary article, and verified `refreshMode=scheduled`, `homeContainsArticle=true`, `detailFound=true`, `latestPublishedAtLeastOne=true`, then cleaned the temporary PG content rows with `cleanupCounts=[0,0,0]`.
- Deployed the SQLite-compatible content-store code to `/opt/wow-mini-program` after backing up current runtime files under `/opt/wow-mini-program/.codex-backups/20260627170930`; `wow-backend` restarted with `WOW_DATABASE_URL` still absent. Smoke: `backend=active`, `env_database_url=absent`, `data_health=partial`, `builds_home=ok`, `news_home=ok`.
- Verified `0005_content_runtime_fields` is recorded in `wow_dev`, `wow_test`, and `wow_prod`; no production content runtime switch was performed.

## PostgreSQL WebSim Cache Sync-State Seam Evidence 2026-06-28

Completed under the same active-goal authorization:

- Added `server/postgres_cache_store.py` for the `cache.websim_sync_state` target schema.
- Routed `/api/data/health` WebSim sync-state reads through the PG cache store when `WOW_DATABASE_RUNTIME=postgres_personal` and PG has `websim_sync` / `gearCatalog` state. Missing PG state falls back to the current SQLite read path.
- Scope was intentionally limited to sync-state health reporting at this checkpoint. Later checkpoints in this runbook extend the PG cache seam to active season, loot, gear catalog, and talent reads; full runtime cutover remains future work.
- Local TDD evidence: `tests.postgres_cache_store_test.PostgresCacheStoreTest.test_sync_state_round_trip_uses_cache_schema_jsonb` failed before `server.postgres_cache_store` existed; `tests.database_adapter_test.DatabaseAdapterTest.test_news_backend_data_health_prefers_postgres_cache_sync_state` failed while health still used SQLite state. Both passed after the PG store and health priority path were added.
- Cloud `wow_test` backend-level hybrid smoke temporarily wrote PG `websim_sync` and `gearCatalog` state keys, called `server.news_backend.build_data_health_payload` with `WOW_DATABASE_RUNTIME=postgres_personal`, verified `websimStatus=verified`, `websimGearItemCount=756`, `websimObservedVariantCount=2388`, `gearStatus=partial`, `gearItemCount=756`, and `gearRevision=pg-cache-items-smoke`, then restored/deleted the smoke keys with `cleanupCounts=[1,1]`.
- Deployed the SQLite-compatible code to `/opt/wow-mini-program` after backing up current runtime files under `/opt/wow-mini-program/.codex-backups/20260627174111`; `wow-backend` restarted with `WOW_DATABASE_URL` still absent. Smoke: `backend=active`, `env_database_url=absent`, `builds_home=ok`, `news_home=ok`, `data_health=ok`.

## PostgreSQL WebSim Season/Loot Read-Model Evidence 2026-06-28

Completed under the same active-goal authorization, without switching production runtime:

- Added `0006_websim_season_loot_cache.sql` for `cache.websim_season_state`, `cache.websim_season_dungeons`, `cache.websim_instances`, `cache.websim_encounters`, and `cache.websim_loot`, reusing `cache.websim_items` from the initial cache schema.
- Extended `server/postgres_cache_store.py` with PG-backed `get_active_season_payload`, `get_websim_instances`, and `get_websim_loot` methods. The backend now routes `runtime_season_payload` and `/api/websim/loot` through PG first when `WOW_DATABASE_RUNTIME=postgres_personal`, then falls back to SQLite when PG cache data is missing, expired, or not verified.
- Extended `data_copy_plan.py` and `shadow_migrate.py` so the public/non-owner copy plan exports `cache.websim_items`, season state, season dungeons, journal instances, encounters, and loot in FK-safe order. `cache.websim_season_state` uses `key` as its idempotency conflict column.
- Local TDD evidence: targeted RED tests first failed for the missing `0006` migration, missing `PostgresCacheStore` season/loot methods, backend SQLite fallback use, and absent copy-plan tables; after implementation, the targeted tests passed. Regression evidence: `python -m unittest tests.postgres_cache_store_test tests.database_adapter_test tests.postgres_schema_test tests.postgres_identity_shadow_plan_test tests.postgres_shadow_migration_test` returned `50 OK`; all PG-related tests returned `64 OK, skipped=1`; `python -m unittest tests.news_backend_test` returned `155 OK`; `py_compile` passed for the touched backend and migration scripts.
- Applied `0006_websim_season_loot_cache.sql` to `wow_dev`, `wow_test`, and `wow_prod`. The existing backup `/opt/wow-mini-program/backups/wow_news-before-public-content-cache-copy-20260627T180920Z.sqlite3` contains `websim_items=1272`, `websim_season_state=1`, `websim_season_dungeons=8`, `websim_instances=12`, `websim_encounters=39`, and `websim_loot=568`; referential precheck found `0` missing loot item, instance, encounter, or encounter-instance references.
- Guarded copy into `wow_test`: `syncRunId=be614be8-4022-496c-94ca-fa38538a7353`, `verifiedRows=13944`, with new WebSim cache counts `cache.websim_items=1272`, `cache.websim_season_state=1`, `cache.websim_season_dungeons=8`, `cache.websim_instances=12`, `cache.websim_encounters=39`, and `cache.websim_loot=568`.
- Guarded copy into `wow_prod` with explicit production allowance: `syncRunId=86702d49-867d-4c22-b538-b26ab88d824a`, `verifiedRows=13944`, same WebSim cache counts as `wow_test`; `identity.users=0`, `identity.user_identities=0`, and `content.refresh_runs_id_seq.last_value=1991` matched `MAX(id)=1991` in both databases.
- Cloud `wow_test` hybrid smoke temporarily extended the copied active season expiry, called `server.news_backend.runtime_season_payload()` and `runtime_websim_loot_payload()` with `WOW_DATABASE_RUNTIME=postgres_personal`, and verified `seasonRevision=season-17-f131dd36ddf1`, `seasonStatus=verified`, `lootItems=24`, and `expiresRestored=true`.
- Deployed the SQLite-compatible code to `/opt/wow-mini-program` after backing up current runtime files under `/opt/wow-mini-program/.codex-backups/20260627185157-websim-season-loot-pg`; `wow-backend` restarted with `WOW_DATABASE_URL` and `WOW_DATABASE_RUNTIME` absent. Smoke: `backend=active`, `GET /api/builds/home=200`, `GET /api/news/home=200`, and `GET /api/data/health=200`.

## PostgreSQL WebSim Gear Catalog Read-Model Evidence 2026-06-28

Completed under the same active-goal authorization, without switching production runtime:

- Added `0007_websim_gear_catalog_cache.sql` to extend the existing PG gear catalog cache tables with SQLite-compatible source, variant, and global mod-option columns. `cache.websim_gear_mod_options.variant_id` is now nullable so the current standalone SQLite option catalog can be copied without inventing a fake variant owner.
- Extended `data_copy_plan.py` so public/non-owner copy plans include `cache.websim_gear_sources`, `cache.websim_gear_variants`, and `cache.websim_gear_mod_options` after `cache.websim_items`, using stable SQLite-id-derived PG UUIDs and preserving `simc_options_json`, `blockers_json`, and `applicable_slots_json`.
- Extended `server/postgres_cache_store.py` with `get_websim_gear()` and added `server.news_backend.runtime_websim_gear_payload()` so `/api/websim/gear` can read PG-first in `WOW_DATABASE_RUNTIME=postgres_personal` mode, then fall back to SQLite when PG has no verified season, no usable gear items, or any read error.
- Local TDD evidence: targeted RED tests first failed for the missing `0007` migration, missing gear copy-plan tables, missing `PostgresCacheStore.get_websim_gear`, and missing backend runtime seam. After implementation, the targeted tests passed; `python -m unittest tests.postgres_schema_test tests.postgres_identity_shadow_plan_test tests.postgres_cache_store_test tests.database_adapter_test` returned `50 OK`; `python -m py_compile server/news_backend.py server/postgres_cache_store.py server/migrations/postgres/data_copy_plan.py server/migrations/postgres/shadow_migrate.py` passed; `git diff --check` passed with only existing Windows CRLF warnings.
- Applied `0007_websim_gear_catalog_cache.sql` to `wow_dev`, `wow_test`, and `wow_prod`.
- Source backup `/opt/wow-mini-program/backups/wow_news-before-public-content-cache-copy-20260627T180920Z.sqlite3` contains `websim_gear_sources=1050`, `websim_gear_variants=4017`, and `websim_gear_mod_options=62`; precheck found `sources_missing_items=0` and `variants_missing_items=0`. Variant status counts were `verified=3252` and `partial=765`; mod options were `socket=20`, `enchant=25`, `embellishment=11`, and `crafted_stats=6`, all `verified`.
- Guarded copy into `wow_test`: `syncRunId=48877f93-8a49-41a9-8132-f47c78950a13`, `verifiedRows=19073`, including `cache.websim_gear_sources=1050`, `cache.websim_gear_variants=4017`, and `cache.websim_gear_mod_options=62`.
- Guarded copy into `wow_prod` with explicit production allowance: `syncRunId=06ec3afd-0e2f-41e8-9b7d-6a8bc29f705f`, `verifiedRows=19073`, with the same gear catalog counts. Both `wow_test` and `wow_prod` recorded `schema_0007=1`, `missing_source_items=0`, `missing_variant_items=0`, `identity.users=0`, and `identity.user_identities=0`.
- Cloud `wow_test` helper smoke temporarily extended the copied active season expiry, called `PostgresCacheStore.get_websim_gear("mage", "frost", compact=True)`, and verified `dataStatus=verified`, `nonemptySlots=16`, `catalogItems=120`, first item `sourceCount=1`, first item `variantCount=3`, then restored the original expiry.
- Cloud backend-level helper smoke imported `server.news_backend` with `WOW_DATABASE_URL=postgresql:///wow_test` and `WOW_DATABASE_RUNTIME=postgres_personal`, called `runtime_websim_gear_payload("mage", "frost", compact=True)`, verified `usedPostgres=true`, `nonemptySlots=16`, and `catalogItems=120`, then restored the original expiry.
- Deployed the SQLite-compatible code to `/opt/wow-mini-program` after backing up current runtime files under `/opt/wow-mini-program/.codex-backups/20260628-websim-gear-pg`; `wow-backend` restarted with `WOW_DATABASE_URL` and `WOW_DATABASE_RUNTIME` absent. Smoke: `GET /api/builds/home=200`, `GET /api/news/home=200`, `GET /api/data/health=200`, and `GET /api/websim/gear?class=mage&spec=frost&compact=1=200`.

## PostgreSQL WebSim Talent Read-Model Evidence 2026-06-28

Completed under the same active-goal authorization, without switching production runtime:

- Added `0008_websim_talent_cache.sql` to extend `cache.websim_talents` with SQLite-compatible node fields, add `cache.websim_profile_presets` and `cache.websim_spell_details`, and extend `cache.websim_community_talent_templates` with hero/scenario/template/import/state/source fields.
- Extended `data_copy_plan.py` so public/non-owner copy plans include `cache.websim_talents`, `cache.websim_profile_presets`, `cache.websim_spell_details`, and `cache.websim_community_talent_templates`, preserving talent state/source refs as jsonb and using stable SQLite-id-derived UUIDs for community templates.
- Extended `server/postgres_cache_store.py` with `get_websim_talents()` and added `server.news_backend.runtime_websim_talents_payload()` so `/api/talents/tree` and `/api/websim/talents` can read PG-first in `WOW_DATABASE_RUNTIME=postgres_personal` mode, then fall back to SQLite when PG has no verified season, no nodes, or any read error.
- Local TDD evidence: targeted RED tests first failed for the missing `0008` migration, missing talent copy-plan tables, missing `PostgresCacheStore.get_websim_talents`, and missing backend runtime seam. After implementation, the targeted tests passed; `python -m unittest tests.postgres_schema_test tests.postgres_identity_shadow_plan_test tests.postgres_cache_store_test tests.database_adapter_test` returned `54 OK`.
- Applied `0008_websim_talent_cache.sql` to `wow_dev`, `wow_test`, and `wow_prod`.
- Source backup `/opt/wow-mini-program/backups/wow_news-before-public-content-cache-copy-20260627T180920Z.sqlite3` contains `websim_talents=5246`, `websim_spell_details=3240`, `websim_profile_presets=49`, and `websim_community_talent_templates=342`. Community template status counts were `verified=313` and `blocked=29`; source statuses were `synced=341` and `partial=1`.
- Guarded copy into `wow_test`: `syncRunId=c351e99c-db7f-4720-a5c3-812df3eaa0ca`, `verifiedRows=27950`, including `cache.websim_talents=5246`, `cache.websim_spell_details=3240`, `cache.websim_profile_presets=49`, and `cache.websim_community_talent_templates=342`.
- Guarded copy into `wow_prod` with explicit production allowance: `syncRunId=6b9a3819-552d-4bb1-a99e-40cf2cb3b23e`, `verifiedRows=27950`, with the same talent read-model counts. Both `wow_test` and `wow_prod` recorded `schema_0008=1`, `identity.users=0`, and `identity.user_identities=0`.
- Cloud backend-level helper smoke imported `server.news_backend` with `WOW_DATABASE_URL=postgresql:///wow_test` and `WOW_DATABASE_RUNTIME=postgres_personal`, temporarily extended the active season expiry, called `runtime_websim_talents_payload("mage", "frost", "spellslinger")`, verified `usedPostgres=true`, `nodeCount=110`, `presetCount=2`, `communityTemplateCount=4`, and restored the original expiry.
- Deployed the SQLite-compatible code to `/opt/wow-mini-program` after backing up current runtime files under `/opt/wow-mini-program/.codex-backups/20260628-websim-talent-pg`; `wow-backend` restarted with `WOW_DATABASE_URL` and `WOW_DATABASE_RUNTIME` absent. Smoke: `GET /api/builds/home=200`, `GET /api/news/home=200`, `GET /api/data/health=200`, `GET /api/websim/gear?class=mage&spec=frost&compact=1=200`, and `GET /api/websim/talents?class=mage&spec=frost&hero=spellslinger=200`.

## PostgreSQL Public Content/Cache Shadow Copy Evidence 2026-06-28

Completed under the same active-goal authorization, without switching production runtime:

- Created source SQLite backup `/opt/wow-mini-program/backups/wow_news-before-public-content-cache-copy-20260627T180920Z.sqlite3`.
- Generated copy-plan summary from that backup: `formalUsers=0`, `guestUsers=13`, `guestOwnedRows=52`, `errors=[]`, `totalRows=12044`.
- Public/cache rows in the plan: `content.sources=4`, `content.raw_articles=29`, `content.article_evidence=9962`, `content.articles=24`, `content.discovery_queue=28`, `content.refresh_runs=1991`, `cache.websim_sync_state=5`, `cache.raiderio_cache=1`.
- Cloud rehearsal caught and fixed two real-data migration issues before `wow_prod` copy:
  - `content.sources` must use the same deterministic UUID rule as `PostgresContentStore.content_uuid("content.sources", source_key)` and migrate idempotently by `source_key`; otherwise existing seeded PG source rows conflict on `sources_source_key_key`.
  - `content.article_evidence` must keep one stable UUID per SQLite evidence row id. The runtime evidence-key UUID would collapse duplicate historical `(article_id, evidence_url, checked_at)` rows from `9962` planned rows to `323` distinct ids.
- Added local regressions for both rules in `tests.postgres_identity_shadow_plan_test` and `tests.postgres_shadow_migration_test`.
- Executed guarded copy into `wow_test`: `syncRunId=c6c63d54-b67c-465d-bd43-57e47844183e`, `verifiedRows=12044`, row counts matched the plan, `identity.users=0`, `identity.user_identities=0`, and `content.refresh_runs_id_seq.last_value=1991` matched `MAX(id)=1991`.
- Executed guarded copy into `wow_prod` with explicit production allowance: `syncRunId=ce284fec-2003-4b4d-b665-fc9207aea2ff`, `verifiedRows=12044`, row counts matched the plan, `identity.users=0`, `identity.user_identities=0`, and `content.refresh_runs_id_seq.last_value=1991` matched `MAX(id)=1991`.
- Confirmed production service stayed on SQLite runtime: `/etc/wow-backend.env` has no `WOW_DATABASE_URL` or `WOW_DATABASE_RUNTIME`, `wow-backend` remained `active`, and it listened on `127.0.0.1:8787`.
- Production SQLite-runtime smoke after the PG copy: `GET /api/builds/home` returned `200` with `28449` bytes, `GET /api/news/home` returned `200` with `98649` bytes, and `GET /api/data/health` returned `200` with `66640` bytes. Data health reported `overallStatus=partial`, consistent with existing component-level verified/partial/blocked/missing-credential states.

## Temporary Hybrid Service Rehearsal 2026-06-28

Completed under the same active-goal authorization:

- Started a temporary backend process on `127.0.0.1:8788` with `WOW_DATABASE_URL=$WOW_PG_APP_DSN_TEST`, `WOW_DATABASE_RUNTIME=postgres_personal`, collectors disabled, and the production SQLite cache path for public reads.
- Did not edit systemd units or `/etc/wow-backend.env`; the production `wow-backend` service stayed on port `8787` with `WOW_DATABASE_URL` absent.
- Smoke verified the mixed runtime path: `hybridReady=true`, `newsHome=true`, `dataHealth=partial`, `analyticsInserted=1`, `analyticsPgRows=1`, `chickenJobStatus=succeeded`, `chickenPgSessions=1`, `sessionMessages=2`.
- The temporary process was terminated after the smoke; port `8788` was closed.
- Cleanup verification: `hybrid_cleanup_counts=0,0,0` for temporary analytics events, temporary guest identities, and Chickenbro sessions.
- Production service verification after rehearsal: `backend8787=active`, `env_database_url=absent`.

Follow-up after the public content/cache shadow copy:

- Started another temporary backend process on `127.0.0.1:8788` with `WOW_DATABASE_URL=$WOW_PG_APP_DSN_TEST`, `WOW_DATABASE_RUNTIME=postgres_personal`, collectors disabled, and production SQLite retained only for fallback domains.
- Seeded temporary PG-only content, PG cache sync-state values, and a temporary PG identity/auth token in `wow_test`, then verified them through HTTP rather than direct function calls.
- Smoke result: `hybridReady=true`, `articleDetailStatus=200`, `articleListStatus=200`, `pgOnlyArticleVisible=true`, `detailFidelity=source_translation`, `healthStatus=200`, `healthOverallStatus=partial`, `websimStatus=verified`, `gearRevision=codex-hybrid-http-smoke`, `unauthTemplates=401`, `createTemplateStatus=200`, `createdTemplateRemote=true`, `listTemplateStatus=200`, `deleteTemplateStatus=200`, and `templateRowsAfterDelete=0`.
- Cleanup verification: `port8788Open=false`, `articleRows=0`, `rawRows=0`, `identityRows=0`, `templateRows=0`, and `gearRevisionRestored=websim-gear-catalog-v1-ff90b4bb5eb6`.

Follow-up cutover evidence:

- Added `--reconcile-public-cache` to `shadow_migrate.py`; this keeps identity/app/knowledge personal rows insert-only while refreshing existing `content.*` and `cache.*` rows for cutover-time public/cache reconciliation.
- Added `0009_runtime_reconcile_privileges.sql` so `wow_migrator` can run the guarded copy/upsert path without using the postgres superuser. Applied `0009` to `wow_dev`, `wow_test`, and `wow_prod`.
- Created fresh source backup `/opt/wow-mini-program/backups/wow_news-before-pg-fresh-reconcile-20260627T195118Z.sqlite3`.
- Executed fresh `wow_prod` reconciliation with `--allow-production --reconcile-public-cache`: `syncRunId=ef08bca3-f16b-43ba-a1e3-de2e0a18ccd2`, `reconcileMode=public_cache`, `verifiedRows=27950`, `identity.users=0`, `content.articles=24`, `cache.websim_gear_variants=4017`, and `cache.websim_talents=5246`.
- A 3-cycle temporary backend rehearsal on `127.0.0.1:8788` used `WOW_DATABASE_URL=$WOW_PG_APP_DSN_PROD`, `WOW_DATABASE_RUNTIME=postgres_personal`, production SQLite fallback, and a temporary PG `gearCatalog` marker. Each cycle verified public news/builds, PG-backed `/api/data/health`, `/api/websim/gear`, `/api/websim/talents`, `/api/websim/loot`, Bearer profile/template CRUD, PG simulator task list/detail from snapshot, Chickenbro message/session/job, and analytics event write. Cleanup left `userIdentityRows=0`, `analyticsRows=0`, and restored the gear marker.

## Production Hybrid Runtime Cutover 2026-06-28

Completed under the active-goal authorization:

- Created `/etc/wow-postgres.env` with root-only DSNs for app and migrator roles, then configured `/home/ubuntu/.pgpass` (`ubuntu:ubuntu`, mode `600`) so systemd can use `WOW_DATABASE_URL=postgresql://wow_app@127.0.0.1:5432/wow_prod` without putting the password in `/etc/wow-backend.env`.
- Backed up the previous service environment to `/etc/wow-backend.env.before-pg-runtime-20260627T200625Z`.
- Updated `/etc/wow-backend.env` with `WOW_DATABASE_URL=postgresql://wow_app@127.0.0.1:5432/wow_prod`, `WOW_DATABASE_RUNTIME=postgres_personal`, and `PGPASSFILE=/home/ubuntu/.pgpass`, then restarted `wow-backend`.
- Public smoke after restart: `wow-backend=active`; localhost `GET /health`, `/api/builds/home`, `/api/news/home`, `/api/data/health`, `/api/websim/gear?class=mage&spec=frost&compact=1`, and `/api/websim/talents?class=mage&spec=frost&hero=spellslinger` all returned `200`.
- Main-service protected PG smoke on `127.0.0.1:8787` created a temporary PG formal user/token, verified `/api/data/health` read a temporary PG cache marker, enforced unauthenticated template `401`, updated profile, saved/listed/deleted a build template, read a seeded SimC task list/detail snapshot, created/read a Chickenbro session/job, and wrote an analytics event. Cleanup left `userIdentityRows=0`, `analyticsRows=0`, and restored the PG cache marker.
- Public URL smoke after cutover: `http://124.223.51.33/health`, `/api/news/home`, `/api/websim/gear?class=mage&spec=frost&compact=1`, and `/api/websim/talents?class=mage&spec=frost&hero=spellslinger` all returned `200`.

## Dev-Debug Runtime Repoint 2026-06-28

The mini program is still in WeChat Developer Tools testing and is not formally launched. To keep developer-testing personal data out of `wow_prod`, the active `wow-backend` service was repointed to `WOW_DATABASE_URL=postgresql://wow_app@127.0.0.1:5432/wow_test` while keeping `WOW_DATABASE_RUNTIME=postgres_personal` and `PGPASSFILE=/home/ubuntu/.pgpass`.

- Before cleanup, `wow_prod` had `identity.users=1`, `identity.user_identities=1`, `app.simulator_tasks=2`, and `app.build_templates=0`; the two remote templates reported by the tester were not present in PostgreSQL and were likely only in the mini program local `wow_build_templates_v1` cache.
- The affected production personal rows were backed up to `/opt/wow-mini-program/backups/wow_prod-personal-test-assets-before-clean-20260628T020757Z.sql`.
- Cleanup used count assertions before deleting the one test identity, cascading the two SimC task rows. Post-cleanup `wow_prod` personal counts were `identity.users=0`, `identity.user_identities=0`, `identity.auth_tokens=0`, `app.build_templates=0`, `app.simulator_tasks=0`, `app.chickenbro_sessions=0`, `app.chickenbro_messages=0`, `app.agent_jobs=0`, and `knowledge.user_context_summaries=0`.
- The previous service env was backed up to `/etc/wow-backend.env.before-wow-test-runtime-20260628T020838Z`, then `/etc/wow-backend.env` was updated to point at `wow_test` and `wow-backend` was restarted.
- Verification after restart: service `active`; `/health`, `/api/news/home`, `/api/websim/gear?class=mage&spec=frost&compact=1`, and `/api/simulator/home` returned `200`; both `wow_prod` and `wow_test` reported `identity.users=0`, `app.build_templates=0`, and `app.simulator_tasks=0` immediately after the switch.

Follow-up stuck-task fix:

- Two dev-debug SimC template tasks submitted to `wow_test` at `2026-06-28 10:14 +08` remained `queued` because the deployed `server/news_backend.py` and `server/postgres_personal_store.py` were behind the local post-cutover code. The request path inserted into PostgreSQL, but the background runner still used the old SQLite-only lookup and logged `KeyError: 'simcraft template task not found'`.
- Local regression coverage for the intended behavior passed: `python -m unittest tests.database_adapter_test.DatabaseAdapterTest.test_news_backend_runs_simcraft_template_task_from_postgres_personal_store tests.postgres_personal_store_test.PostgresPersonalStoreTest.test_simcraft_template_runner_methods_use_postgres_task_table`.
- Hot update scope was limited to `server/news_backend.py` and `server/postgres_personal_store.py`; remote originals were backed up under `/opt/wow-mini-program/.codex-backups/20260628T022140Z-pg-simc-runner`, `python3 -m py_compile` passed for both files, and `wow-backend` restarted `active`.
- The two queued rows were then rerun with the full service SimC environment. Final `wow_test.app.simulator_tasks` statuses were `completed`, with DPS `73504.874` and `73450.168`; `last_error` was empty for both rows.

Still not done:

- This is a `postgres_personal` hybrid production runtime, not a full backend `db_connection()` cutover. SQLite remains the fallback for routes that have not been moved behind a PostgreSQL store seam.
- Guest-owned historical data and legacy auth tokens remain intentionally unmigrated. If formal authenticated SQLite users appear later, run a fresh identity/app reconciliation before relying on those rows in PG.
- Embedding Provider and independent worker execution remain planned but not implemented.

## Runtime Cutover Checklist

The hybrid production runtime cutover is complete. Any future full PostgreSQL `db_connection()` cutover still requires:

- Fresh production SQLite backup path recorded in `docs/roadmap.md`.
- PostgreSQL schema and privileges re-verified on the target database.
- Production `wow_prod` data-copy reconciliation executed and counts reviewed, including any formal-user rows and public content/cache deltas after the last copy.
- Re-login messaging ready because old tokens are not migrated.
- Guest task/session behavior documented because guest data is not migrated.
- systemd environment backed up before changes.
- Staging or temporary service rehearsal with authenticated personal flows and rollback smoke.
- Owner approval immediately before replacing the remaining SQLite fallback paths.

## Rollback Decision Tree

- If local schema tests fail, revert the schema artifact or fix the SQL before any PG use.
- If SQLite tests fail, keep `WOW_DATABASE_URL` unset and fix the adapter or SQLite compatibility migration.
- If optional PG integration fails, do not cut over; inspect SQL/dialect issues against local PG only.
- If a future shadow migration has count or checksum drift, discard the target PG database and rerun from a fresh SQLite copy.
- If the current hybrid production runtime fails, restore `/etc/wow-backend.env.before-pg-runtime-20260627T200625Z` to `/etc/wow-backend.env`, restart `wow-backend`, verify the service is active, and run core SQLite smoke checks.
- If a future full PostgreSQL cutover fails, unset `WOW_DATABASE_URL`, restore the previous systemd environment, restart the service, verify `wow-backend` is active, and run core SQLite smoke checks.

## Verification Ladder

Run before marking Phase 1 complete:

```bash
python -m unittest tests.database_adapter_test
python -m unittest tests.postgres_schema_test
python -m unittest tests.postgres_personal_store_test
python -m unittest tests.postgres_analytics_store_test
python -m unittest tests.postgres_content_store_test
python -m unittest tests.postgres_cache_store_test
python -m unittest tests.postgres_identity_shadow_plan_test
python -m unittest tests.postgres_shadow_migration_test
python -m unittest tests.news_backend_test
python -m unittest tests.websim_payload_test
python -m unittest tests.stat_weights_payload_test
python -m unittest tests.raiderio_payload_test
python -m unittest tests.gear_observed_backfill_test
node --test tests/build-template-storage.test.js tests/profile-auth.test.js tests/frontend-api-client.test.js tests/simulator-page.test.js tests/builds-page.test.js
python -m unittest tests.postgres_integration_test
git diff --check
```

Do not expand beyond the current `postgres_personal` hybrid runtime, replace remaining SQLite fallback paths, copy additional production data into `wow_prod`, or restart production services for another database cutover unless the cutover section above is updated and verified.
