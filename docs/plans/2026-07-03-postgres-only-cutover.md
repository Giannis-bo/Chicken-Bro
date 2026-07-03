# PostgreSQL-only Runtime Cutover Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove SQLite from online runtime paths and deploy the backend in PostgreSQL-only mode with explicit blocked/stale status instead of SQLite fallback.

**Architecture:** Keep SQLite only as an explicit migration or backup input. Add a strict runtime mode (`WOW_DATABASE_RUNTIME=postgres_only` or `WOW_SQLITE_RUNTIME_DISABLED=1`) that makes any backend SQLite connection fail. Route public APIs, admin gates, health, WebSim cache reads, personal data, content, analytics, and ops through PostgreSQL stores. If PostgreSQL data is missing, stale, blocked, or partial, return that status and blockers rather than reading SQLite.

**Tech Stack:** Python stdlib backend, PostgreSQL via `psycopg`, existing PostgreSQL store modules, SQL migrations under `server/migrations/postgres/`, Python `unittest`, Node `node:test`, systemd service/timer deployment on `wow-lighthouse`.

## Current SQLite Entry Inventory

- `server/news_backend.py`
  - `db_connection()` still opens the SQLite file when `WOW_DATABASE_RUNTIME=postgres_personal`.
  - Public fallback calls remain in content refresh state, builds/PVE Raider.IO enrichment, WebSim season/loot/gear/talents/import, data health, admin gate fallback, and legacy personal/auth/task paths when no PG store is present.
- Sync and backfill scripts
  - `server/websim_sync.py`, `server/community_template_sync.py`, `server/stat_weights_sync.py`, `server/stat_weights_payload.py`, `server/crafted_gear_backfill.py`, `server/gear_observed_backfill.py`, and `server/community_talent_sources/raiderio.py` open SQLite directly through `WOW_NEWS_DB` or explicit `--db`.
- Migration-only scripts
  - `server/migrations/postgres/data_copy_plan.py`, `identity_shadow_plan.py`, and `shadow_migrate.py` intentionally open SQLite read-only as a migration source and remain allowed only when invoked explicitly.
- Tests
  - Existing unit tests use temporary SQLite files to validate legacy schema and migration compatibility. New PG-only tests must assert runtime code does not touch these paths when strict mode is active.

## Implementation Tasks

### Task 1: Add PG-only runtime guard tests

**Files:**
- Modify: `tests/database_adapter_test.py`
- Modify: `tests/news_backend_test.py`

**Steps:**
1. Add a failing test proving `postgres_only` creates PG stores while `db_connection()` is forbidden.
2. Add failing tests for WebSim talents/gear/import and health that patch SQLite connection helpers to raise and expect PG payloads or explicit blocked payloads.
3. Add a failing test proving public runtime does not honor `WOW_ALLOW_SQLITE_PUBLIC_CACHE_FALLBACK` when `postgres_only` is active.

### Task 2: Implement runtime mode helpers

**Files:**
- Modify: `server/db.py`
- Modify: `server/news_backend.py`

**Steps:**
1. Add `sqlite_runtime_disabled()` and `postgres_runtime_enabled()` helpers.
2. Make `db_connection()` raise a clear runtime error when strict mode disables SQLite.
3. Allow PG store factories for `WOW_DATABASE_RUNTIME=postgres_only` as well as the legacy hybrid `postgres_personal`.

### Task 3: Remove WebSim public fallback

**Files:**
- Modify: `server/news_backend.py`

**Steps:**
1. In PG-only mode, `runtime_season_payload`, `runtime_websim_loot_payload`, `runtime_websim_gear_payload`, `runtime_websim_talents_payload`, and `runtime_websim_talent_import_payload` must return PG payloads or explicit blocked payloads without calling `init_db()` or `db_connection()`.
2. Preserve hybrid behavior for `postgres_personal` until deployment switches to `postgres_only`.

### Task 4: Make data health PG-only aware

**Files:**
- Modify: `server/news_backend.py`
- Modify: `server/postgres_cache_store.py`

**Steps:**
1. Add PG read helpers for Raider.IO and stat weight cache state when needed.
2. Build `/api/data/health` from PostgreSQL stores in strict mode.
3. Missing PG rows should produce `blocked` or `stale` components with root-cause blockers, not trigger SQLite reads.

### Task 5: Fence sync and backfill scripts

**Files:**
- Modify: `server/websim_sync.py`
- Modify: `server/community_template_sync.py`
- Modify: `server/stat_weights_sync.py`
- Modify as needed: service unit files and migration docs

**Steps:**
1. Strict runtime scripts must not open SQLite accidentally.
2. Migration/backfill scripts may read SQLite only through explicit migration flags or documented offline invocation.
3. Service units should use PG-only runtime configuration and not set `WOW_NEWS_DB` as online state.

### Task 6: Update docs and deployment runbook

**Files:**
- Modify: `docs/database-architecture.md`
- Modify: `docs/roadmap.md`
- Modify: relevant runbooks/README files

**Steps:**
1. Replace hybrid runtime wording with PG-only target-state wording.
2. Document SQLite as historical backup or explicit migration source only.
3. Record backup, migration, deployment, smoke, and rollback boundaries.

### Task 7: Verify, review, deploy

**Steps:**
1. Run targeted Python tests, Node tests for affected API clients/pages, `py_compile`, and `git diff --check`.
2. Do a local CR against the plan and roadmap boundaries.
3. On `wow-lighthouse`, back up PostgreSQL and the historical SQLite file, deploy code, set `WOW_DATABASE_RUNTIME=postgres_only`, restart services, inspect logs, and smoke `/health`, `/api/data/health`, news, WebSim talents/gear/profile/simulate, and admin gates.
4. Sample all class/spec talent templates and confirm player-consumable templates are verified or explicitly blocked with root cause.

## 2026-07-03 Implementation Notes

### Runtime guard

- `server/db.py` now recognizes `WOW_DATABASE_RUNTIME=postgres_only` and `WOW_SQLITE_RUNTIME_DISABLED=1`.
- `server/news_backend.py::db_connection()` raises when SQLite runtime is disabled.
- `WOW_SQLITE_MIGRATION_SOURCE=1` / `WOW_ALLOW_SQLITE_MIGRATION_SOURCE=1` are reserved for explicit migration/offline source reads and must not be set in online service env.

### PG-only route coverage

- Public content/news routes return PostgreSQL content-store payloads or explicit blocked state when PG content store is unavailable.
- Raider.IO-backed builds/PVE routes, stat-weight latest state, WebSim bootstrap/assets/loot/gear/talents/import, profile, gear stats, simulate, and `/api/talents/validate|export|import` avoid SQLite in strict mode.
- `/api/data/health` uses PostgreSQL content/cache state in strict mode and reports blocked/stale/partial root causes instead of falling back.
- Admin gate summary/records/detail/queue/diagnoses use PostgreSQL content/cache/ops stores in strict mode; missing stores surface `runtimeBlockers`.

### PG read models and migration coverage

- Added `0012_websim_asset_registry.sql` for `cache.websim_asset_registry`.
- Extended `data_copy_plan.py` and `shadow_migrate.py` to reconcile `cache.stat_weight_cache` and `cache.websim_asset_registry`.
- `PostgresCacheStore` now serves Raider.IO cache, stat weight payload/latest state, WebSim bootstrap, WebSim assets, and detail stat-weight enrichment from PostgreSQL cache tables.

### PG-native script runners

- `websim_sync.py`, `community_template_sync.py`, `stat_weights_sync.py`, `crafted_gear_backfill.py`, and `gear_observed_backfill.py` now branch to `server/postgres_cache_sync.py` when `WOW_DATABASE_RUNTIME=postgres_only`.
- `websim_sync.py` performs a real PG-native SimC generated-data refresh into `cache.websim_talents`, `cache.websim_profile_presets`, and `cache.websim_spell_details`, then writes Blizzard season/journal/loot/item rows into PostgreSQL cache tables and rebuilds a loot-derived `gearCatalog` skeleton from `cache.websim_loot`.
- `stat_weights_sync.py` now runs the real Raider.IO profile selection + SimC scale-factor builder in PG-only mode, reuses previous PG stat-weight payloads only for fresh translation fallback, writes `cache.stat_weight_cache`, and updates `stat_weights_sync` without SQLite.
- `community_template_sync.py` now loads Raider.IO/manual/WCL/WebSim baseline talent sources plus PG profile presets, writes `cache.websim_community_talent_templates` / `cache.websim_community_gear_templates`, and records source-level blocked/partial causes in PG sync state.
- `gear_observed_backfill.py` writes Raider.IO observed profile gear into `cache.websim_items`, `cache.websim_gear_sources`, and `cache.websim_gear_variants` in PG-only mode.
- `crafted_gear_backfill.py` has an explicit PG-native seed runner: when `WOW_CRAFTED_GEAR_SEED_JSON` provides governed crafted rows it writes the same PG gear cache; without seed rows it remains fail-closed with a blocked root cause rather than opening SQLite.
- Migration-only reads are still allowed when the command is explicitly marked as a SQLite migration source.

### Local verification commands

```bash
python3 -m unittest tests.database_adapter_test tests.postgres_only_scripts_test tests.news_backend_test.NewsBackendTest.test_pg_only_runtime_ignores_sqlite_public_cache_fallback_flag_for_gear tests.news_backend_test.NewsBackendTest.test_pg_only_runtime_returns_blocked_talent_payload_without_sqlite_fallback tests.news_backend_test.NewsBackendTest.test_pg_only_runtime_returns_blocked_talent_import_without_sqlite_fallback tests.news_backend_test.NewsBackendTest.test_pg_only_data_health_uses_postgres_state_without_sqlite tests.news_backend_test.NewsBackendTest.test_pg_only_admin_gate_records_do_not_fallback_to_sqlite_when_runtime_store_missing tests.news_backend_test.NewsBackendTest.test_pg_only_admin_gate_queue_do_not_fallback_to_sqlite_when_runtime_store_missing tests.news_backend_test.NewsBackendTest.test_pg_only_admin_gate_detail_do_not_fallback_to_sqlite_when_runtime_store_missing tests.news_backend_test.NewsBackendTest.test_pg_only_websim_profile_route_does_not_open_sqlite tests.news_backend_test.NewsBackendTest.test_pg_only_websim_gear_stats_route_returns_blocked_without_sqlite tests.news_backend_test.NewsBackendTest.test_pg_only_public_builds_and_pve_routes_do_not_open_sqlite tests.news_backend_test.NewsBackendTest.test_pg_only_websim_bootstrap_and_assets_routes_do_not_open_sqlite tests.news_backend_test.NewsBackendTest.test_pg_only_talent_mutation_routes_do_not_open_sqlite tests.news_backend_test.NewsBackendTest.test_pg_only_stat_weight_latest_route_do_not_open_sqlite tests.news_backend_test.NewsBackendTest.test_pg_only_websim_simulate_route_do_not_open_sqlite tests.news_backend_test.NewsBackendTest.test_pg_only_news_routes_return_blocked_without_sqlite_when_content_store_missing -v
python3 -m unittest tests.postgres_cache_sync_test tests.postgres_cache_store_test -v
python3 -m unittest tests.postgres_cache_sync_test tests.postgres_cache_store_test tests.postgres_only_scripts_test tests.stat_weights_payload_test -v
python3 -m unittest tests.websim_payload_test tests.websim_sync_test tests.gear_observed_backfill_test tests.stat_weights_payload_test -v
python3 -m unittest tests.postgres_cache_store_test tests.postgres_identity_shadow_plan_test tests.postgres_schema_test tests.postgres_shadow_migration_test -v
python3 -m py_compile server/db.py server/news_backend.py server/postgres_cache_store.py server/postgres_cache_sync.py server/websim_payload.py server/websim_sync.py server/community_template_sync.py server/stat_weights_sync.py server/stat_weights_payload.py server/crafted_gear_backfill.py server/gear_observed_backfill.py
git diff --check
```

### Cloud deployment checklist

1. Back up current PostgreSQL target with `pg_dump` and copy historical `/opt/wow-mini-program/server/data/wow_news.sqlite3` into `/opt/wow-mini-program/backups/`.
2. Apply repo-owned PostgreSQL migration `0012_websim_asset_registry.sql`.
3. Run fresh public/cache reconciliation from the copied SQLite migration source into the active PG target, including `cache.stat_weight_cache` and `cache.websim_asset_registry`.
4. Deploy code, set `WOW_DATABASE_RUNTIME=postgres_only`, keep `WOW_SQLITE_MIGRATION_SOURCE` unset in `/etc/wow-backend.env`, install/enable the PG-native sync timers, and restart `wow-backend`.
5. Verify logs and HTTP smoke: `/health`, `/api/data/health`, `/api/news/home`, builds/PVE, `/api/websim/bootstrap`, `/api/websim/assets`, talents, gear, loot, profile, gear stats, simulate, and admin gates.
6. Sample the talent-template read model across all class/specs and confirm player-consumable active templates are `verified`, while new `blocked` rows expose current root causes.

## 2026-07-03 Cloud Cutover Evidence

### Remote backup and migration

- Remote host: `wow-lighthouse`, public base `http://124.223.51.33`.
- Active PostgreSQL target during cutover: `wow_test`.
- Backup directory: `/opt/wow-mini-program/backups/postgres-only-cutover-20260703T041953Z`.
- Backup artifacts:
  - `wow_test.dump`
  - `wow_news.sqlite3.before-pg-only-cutover`
  - `wow-backend.env.before-pg-only-cutover`
- Applied `0012_websim_asset_registry`; `ops.schema_migrations` contains one `0012_websim_asset_registry` row.
- Reconciled public/cache data from the copied SQLite migration source with `WOW_SQLITE_MIGRATION_SOURCE=1`; final reconcile `syncRunId=3c6d92cf-dff0-453e-baa5-adc33d212a21`, `verifiedRows=31905`.
- Final copied row highlights:
  - `cache.websim_talents=5246`
  - `cache.websim_asset_registry=5391`
  - `cache.stat_weight_cache=120`
  - `cache.websim_community_talent_templates=511` copied; active post-expiry state is `verified=116`, `blocked=8`.

### Runtime state

- `wow-backend` is active with `WOW_DATABASE_RUNTIME=postgres_only`.
- `WOW_NEWS_DB`, `WOW_SQLITE_MIGRATION_SOURCE`, and `WOW_ALLOW_SQLITE_MIGRATION_SOURCE` are not present in the online service environment.
- Initial PG-only cutover disabled the legacy SQLite-era timers. The follow-up PG-native runner change restores `wow-websim-sync.timer`, `wow-stat-weights-sync.timer`, `wow-community-template-sync.timer`, and `wow-gear-observed-backfill.timer` with `WOW_DATABASE_RUNTIME=postgres_only` and no `WOW_NEWS_DB`.
- Final journal smoke window after deployment shows 200 responses for health, data health, news, builds/PVE, WebSim talents/gear/profile/simulate, and admin gates; no new SQLite startup/runtime error appeared after the final restart.

### HTTP smoke

Local loopback and public `http://124.223.51.33` smoke both returned 0 failures for:

- `/health`
- `/api/data/health?audit=1`
- `/api/news/home`
- `/api/builds/home`
- `/api/pve/home`
- `/api/websim/bootstrap`
- `/api/websim/assets?limit=5`
- `/api/websim/loot?slot=head`
- `/api/websim/talents?class=mage&spec=frost&hero=frostfire`
- `/api/talents/tree?class=mage&spec=frost&hero=frostfire`
- `/api/websim/talents/import?class=mage&spec=frost&hero=frostfire`
- `/api/websim/gear?class=mage&spec=frost&compact=1&mode=initial`
- `POST /api/websim/profile`
- `POST /api/websim/gear/stats`
- `POST /api/websim/simulate`
- `/api/admin/gates/summary`
- `/api/admin/gates/records?domain=talents&limit=5`
- `/api/admin/gates/queue?limit=5`

Talent endpoint matrix sampled all PG talent class/spec combinations plus active community hero combos:

- `combos=88`
- `endpointFailures=0`
- `nodesReturned=10013`
- `communityTemplatesReturned=271`
- `verifiedCommunityTemplatesReturned=271`
- `nonVerifiedCommunityTemplatesReturned=0`

### Current data-health caveats

The cutover target is PG-only runtime, not a claim that all upstream data is currently fresh or fully verified. Current remote payloads intentionally expose these blockers instead of falling back to SQLite:

- `/api/data/health?audit=1` overall status is `partial`.
- Initial cutover smoke found the WebSim season row expired. The PG-native Blizzard journal follow-up later refreshed active season to `season-17-f131dd36ddf1`, `data_status=verified`, `expires_at=2026-07-04 14:39:38+08`.
- Talent endpoints return PG nodes and only verified community templates, but `talentStatus=simc` can still appear while spell descriptions/icons have unresolved formula text or official audit evidence is pending.
- `cache.stat_weight_cache` has `verified=11`, `partial=18`, `blocked=91`, so stat-weight consumers must continue surfacing `partial` or `blocked` instead of inventing weights.
- Active community talent templates in PG are `verified=116`, `blocked=8`; blocked rows are visible through admin gates and should be treated as current governance work, not hidden by SQLite fallback.

## 2026-07-03 PG-native WebSim Journal Follow-up Evidence

- Pre-deploy PG backup: `/opt/wow-mini-program/backups/pg-native-websim-20260703T063449Z/wow_test.dump`.
- Hot deploy used `WOW_DEPLOY_SKIP_BOOTSTRAP=1 WOW_DEPLOY_START_ASYNC_SYNCS=0`, so it did not download packages or start long async sync jobs automatically.
- Default `wow-websim-sync.service` was started after deploy and completed the SimC PG substage (`talents=5246`, `profiles=50`, `spellDetails=3221`) but was manually stopped while still in the full-limit Blizzard stage. This left a transient `signal` result; `systemctl reset-failed wow-websim-sync.service` cleared the failed state and timers remained enabled.
- A bounded PG-only smoke then ran `server/websim_sync.py` with `WOW_WEBSIM_SYNC_INSTANCE_LIMIT=1`, `WOW_WEBSIM_SYNC_RAID_INSTANCE_LIMIT=0`, `WOW_WEBSIM_SYNC_ENCOUNTER_LIMIT=2`, `WOW_WEBSIM_SYNC_ITEM_LIMIT=12`, and `WOW_WEBSIM_SKIP_RAIDERIO=1`.
- Bounded smoke result: Blizzard stage completed with `instances=1`, `encounters=2`, `loot=12`, `items=12`; PG row counts showed `cache.websim_loot=12`, loot-derived `cache.websim_gear_sources=12`, and loot-derived `needs-variant` rows `12`.
- Final smoke: `/health=200`, `/api/data/health=200 overall partial`, `/api/websim/loot?slot=head` returned one verified head item, `/api/websim/talents?class=mage&spec=frost&hero=spellslinger` returned `nodes=110` and `communityTemplates=3`, and public `/api/websim/gear?class=mage&spec=frost&compact=1&mode=initial` returned `slots=16`, `replacementCandidates=16`, `catalogStatus=partial`, `dataStatus=verified`, `communityTemplates=2`.

## 2026-07-03 PG-native Public Cache Writer Follow-up

- Local implementation now covers stat-weight row generation, community talent/gear template row writers, Raider.IO observed gear row writers, and explicit-seed crafted gear row writers in PostgreSQL. These paths write `cache.stat_weight_cache`, `cache.websim_community_talent_templates`, `cache.websim_community_gear_templates`, `cache.websim_items`, `cache.websim_gear_sources`, and `cache.websim_gear_variants` without opening SQLite.
- Stat weights use the same SimC builder as the legacy path, but the previous payload is supplied from PG instead of `build_stat_weight_cache` SQLite rows.
- Community gear templates are built from PG `cache.websim_profile_presets`; no fallback presets are used to invent templates when PG has no profile seed.
- Crafted backfill is PG-native but seed-bound: without `WOW_CRAFTED_GEAR_SEED_JSON`, the runner records a blocked root cause rather than pretending crafted variants were generated.
- Local verification: `python3 -m unittest tests.database_adapter_test tests.postgres_only_scripts_test tests.postgres_cache_sync_test tests.postgres_cache_store_test tests.stat_weights_payload_test ... -v` passed 92 targeted tests; `node --test tests/deploy-script.test.js`, targeted `py_compile`, and `git diff --check` passed.
- Cloud backup before deploy: `/opt/wow-mini-program/backups/pg-native-public-cache-20260703T070000Z/wow_test.dump`.
- Hot deploy used `WOW_DEPLOY_SKIP_BOOTSTRAP=1 WOW_DEPLOY_START_ASYNC_SYNCS=0`; no package/bootstrap/download path was run, and async jobs were not auto-started.
- Remote service/timer env check: `wow-backend`, `wow-websim-sync`, `wow-stat-weights-sync`, `wow-community-template-sync`, and `wow-gear-observed-backfill` expose `WOW_DATABASE_RUNTIME=postgres_only` and no `WOW_NEWS_DB` / SQLite runtime env.
- Remote PG-native smoke: community sync completed with talent templates `total=70 verified=40 blocked=30`, gear templates `total=37 verified=20 partial=17`, source status `partial` because WCL credentials were not configured at that moment; observed backfill wrote `itemCount=213`, `sourceCount=213`, `variantCount=213`, status `partial`; crafted backfill had no `WOW_CRAFTED_GEAR_SEED_JSON`, so it recorded `blocked` without SQLite; stat-weight smoke limited to one spec wrote 3 blocked scenarios with `raiderioStatus=synced`.
- Remote PG row counts after smoke: `cache.stat_weight_cache` `verified=11 partial=15 blocked=94`; active community talent rows `verified=156 blocked=38`; community gear rows `complete=20 partial=17`; `cache.websim_gear_variants` has `observed_profile=1595` and `crafted=438` rows.
- HTTP smoke after deploy: `/health=200 ok=true`, `/api/data/health=200 overall partial`, `/admin/gates=200`, `/api/websim/talents?class=mage&spec=frost&hero=spellslinger=200 nodes=110 communityTemplates=3`, `/api/websim/gear?class=mage&spec=frost&compact=1&mode=initial=200 slots=16 dataStatus=verified catalogStatus=partial communityTemplates=2`, and `/api/builds/stat-weights/refresh-runs/latest=200 sourceStatus=partial acceptedCount=26 blockedCount=94`.

## 2026-07-03 WCL Credential and Live PG-only Confirmation

- Warcraft Logs v2 OAuth credentials were configured in `/etc/wow-backend.env` after a local and remote credential probe. Both probes returned OAuth `200` with a Bearer token and GraphQL `200` for a minimal `__typename` query. The runtime env exposes `WOW_WARCRAFTLOGS_CLIENT_ID` and `WOW_WARCRAFTLOGS_CLIENT_SECRET` to `wow-backend`; logs and command output must keep the secret redacted.
- `wow-backend` was restarted after the env change and remained active. `/api/data/health` now reports `wcl_credentials.details.configured=true`, `credentialMode=v2_oauth`, `api=warcraftlogs-v2-graphql`, with no credential blocker.
- A follow-up PG-native community-template smoke no longer reports missing credentials. It still records `partial` because the current runner has no combatantinfo template seed/report extraction available for the sync run. This is an extraction capability gap, not a key configuration issue.
- Live PG-only confirmation: the `wow-backend` process has `WOW_DATABASE_RUNTIME=postgres_only` and `WOW_DATABASE_URL`, with no `WOW_NEWS_DB` / `WOW_SQLITE_MIGRATION_SOURCE`; `wow-websim-sync`, `wow-stat-weights-sync`, `wow-community-template-sync`, and `wow-gear-observed-backfill` units also expose `WOW_DATABASE_RUNTIME=postgres_only`.
- Live public/admin smoke: `/health=200`, `/admin/gates=200`, and admin-token requests to `/api/admin/gates/summary`, `/api/admin/gates/records?limit=5`, and `/api/admin/gates/queue?limit=5` returned `200`; admin records total was `882`, and the queue still surfaced blocked records.
- Current `/api/data/health` remains `overall=partial`: `backend`, `raiderio`, `websim_season`, and WCL credentials are usable; `news` is partial due Blizzard News fetch/publish blockers; `websim_sync` is blocked by `gear catalog is partial`; `gear_catalog` has `itemCount=12`, `variantCount=12`, `verifiedCount=0`, `partialCount=12`; `community_templates` remains partial because WCL extraction is missing and active templates still include blocked rows; `stat_weights` remains blocked for the latest smoke state.
- Operational conclusion: online mini-program APIs and the admin gate platform are using PostgreSQL as the single runtime read model. Data consistency is acceptable only in the fail-closed sense: PostgreSQL is the source of truth and exposes verified/partial/blocked root causes honestly. It is not a claim that every user-visible game datum is fully verified or converged.
