# Gear Observed Variant Backfill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the equipment database able to improve observed gear variant coverage in production through a short, resumable, independently observable background job, without relying on a full season sync or weakening the current data trust boundaries.

**Architecture:** Keep the existing SQLite Season Data Cache as the source of truth for local generated data. Add an independent Raider.IO observed-variant backfill path that scans target items with a persistent cursor, writes only evidence-backed observed rows in additive mode, promotes official variants only when deterministic tuple evidence exists, and exposes progress through the read-only data health endpoint.

**Tech Stack:** Python backend, SQLite, `unittest`, existing `server/websim_payload.py` gear catalog tables, existing `server/raiderio_payload.py` Raider.IO cache helpers, `server/news_backend.py` `/api/data/health`, systemd service/timer files under `server/`.

## Current Context

The handoff in `docs/plans/2026-06-22-gear-data-layer-goal-handoff.md` says the equipment layer has already shipped a season-owned gear catalog around Battle.net items, Raider.IO observed gear, SimC metadata, SQLite cache state, and `/api/data/health` readiness reporting.

The current production blocker is not basic item metadata. The blocker is missing deterministic variant tuples such as bonus IDs, modifier IDs, sockets, upgrade metadata, and main/offhand evidence for some item variants. Those variants must remain `partial` or `blocked` until real observed or SimC-verified evidence exists.

The roadmap and DB architecture docs already establish the boundaries:

- `docs/roadmap.md`: Season Data Cache is rebuildable sync/index/audit data, and equipment data must carry source, season revision, checked time, status, and blocker information.
- `docs/database-architecture.md`: `/api/data/health` is read-only and must not trigger external sync; missing SimC fields cannot be presented as real conclusions.
- Existing SQLite remains the right immediate target. This plan does not introduce Postgres or a second primary DB.

## Non-Goals

- Do not run production backfills as part of implementation.
- Do not fetch live Raider.IO or Battle.net data in tests.
- Do not convert the app to a new DB engine.
- Do not promote Battle.net preview-only or stale inferred variants into official simulator-ready variants.
- Do not change player-facing simulator language to imply generated or partial variants are confirmed real results.

## Target Outcome

After implementation:

- A new independent backfill runner can be invoked in bounded batches.
- The runner uses a persistent cursor and can resume after timeout, deploy, or process interruption.
- Existing observed variant data is not wiped by small incremental batches.
- `/api/data/health` reports observed backfill cursor/progress/error state without triggering sync.
- Production operators can enable a short systemd timer for the new job separately from the full WebSim sync.
- Official variant promotion remains evidence-gated and deterministic.

## Data Contract

Add an observed backfill state object stored in the existing local DB in `websim_sync_state` under the key:

```text
gear_observed_backfill
```

Minimum fields:

```json
{
  "schemaVersion": 1,
  "provider": "raiderio",
  "providers": {
    "raiderio": {"status": "idle|running|ok|partial|error"},
    "wcl": {"status": "not_implemented"}
  },
  "cursor": {
    "targetItemHash": "sha256-of-ordered-target-items",
    "targetItemCount": 0,
    "targetOffset": 0,
    "profileOffset": 0
  },
  "matchedTargetItemIds": [],
  "lastRunStatus": "idle|running|ok|partial|error",
  "lastRunStartedAt": null,
  "lastRunFinishedAt": null,
  "processedTargetItemCount": 0,
  "processedProfileCount": 0,
  "lastError": null,
  "wrappedAt": null
}
```

Cursor rules:

- `targetItemHash` changes reset offsets because the target set changed.
- `targetOffset` advances through deterministic target-item order.
- `profileOffset` advances through the Raider.IO candidate profile window.
- A run can return `partial` and persist the next cursor before exiting.
- Wrapping is expected; record `wrappedAt` and continue from zero instead of treating wrap as a failure.

## Implementation Tasks

### Task 1: Add Additive Observed Variant Sync Mode

Files:

- `server/websim_payload.py`
- `tests/websim_payload_test.py`

Problem:

`sync_observed_gear_variants` currently behaves like a whole-batch replacement path. It performs anti-downgrade checks against the full existing observed cache and deletes existing observed rows before inserting the new set. That is appropriate for the current full cached Raider.IO sync, but it is wrong for cursorized backfill because each run only sees a small target/profile window.

Steps:

1. Add failing tests in `tests/websim_payload_test.py`.

   Test names:

   ```python
   test_sync_observed_gear_variants_can_incrementally_upsert_without_replacing_cache
   test_sync_observed_gear_variants_replace_mode_keeps_existing_anti_downgrade_behavior
   ```

   Test requirements:

   - Seed an existing observed profile variant for item A.
   - Run `sync_observed_gear_variants(..., replace=False)` with a payload containing item B only.
   - Assert both item A and item B observed rows remain.
   - Assert source refs, variant IDs, bonus IDs, modifier IDs, observed context, and status fields are preserved.
   - In replacement mode, keep existing anti-downgrade behavior: a smaller or weaker full payload must not replace a richer existing observed cache.

2. Run the targeted tests and confirm they fail because `replace=False` does not exist yet:

   ```bash
   python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_sync_observed_gear_variants_can_incrementally_upsert_without_replacing_cache -v
   python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_sync_observed_gear_variants_replace_mode_keeps_existing_anti_downgrade_behavior -v
   ```

3. Update `sync_observed_gear_variants` in `server/websim_payload.py`.

   Expected shape:

   ```python
   def sync_observed_gear_variants(
       conn,
       payload,
       *,
       season_revision,
       checked_at,
       replace=True,
   ):
       ...
   ```

   Behavior:

   - `replace=True`: preserve current behavior for the full cached Raider.IO path.
   - `replace=False`: skip whole-cache anti-downgrade, skip delete-all observed rows, and upsert only incoming observed sources/variants.
   - Use existing source/variant upsert logic; avoid duplicating schema mapping.
   - Do not change official variant readiness calculations.

4. Re-run the new tests and the existing related gear catalog tests:

   ```bash
   python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_sync_observed_gear_variants_can_incrementally_upsert_without_replacing_cache -v
   python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_sync_observed_gear_variants_replace_mode_keeps_existing_anti_downgrade_behavior -v
   python3 -m unittest tests.raiderio_payload_test.RaiderIOPayloadTest.test_sync_raiderio_cache_uses_partial_gear_variants_as_target_items -v
   python3 -m unittest tests.raiderio_payload_test.RaiderIOPayloadTest.test_db_target_item_ids_round_robins_partial_items_by_source_and_slot -v
   ```

### Task 2: Add Gear Observed Backfill Cursor State Helpers

Files:

- `server/websim_payload.py`
- `tests/websim_payload_test.py`

Steps:

1. Add failing tests in `tests/websim_payload_test.py`.

   Test names:

   ```python
   test_gear_observed_backfill_state_defaults_when_missing
   test_gear_observed_backfill_state_persists_in_websim_sync_state
   test_gear_observed_backfill_cursor_resets_when_target_hash_changes
   test_gear_observed_backfill_profile_window_resumes_and_wraps
   ```

   Test requirements:

   - Missing state returns schema-versioned defaults.
   - Persisted state round-trips through the DB.
   - Target item set changes reset offsets.
   - Cursor windows are deterministic and wrap cleanly.
   - No external HTTP calls are made.

2. Run targeted tests and confirm they fail:

   ```bash
   python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_gear_observed_backfill_state_defaults_when_missing -v
   python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_gear_observed_backfill_state_persists_in_websim_sync_state -v
   python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_gear_observed_backfill_cursor_resets_when_target_hash_changes -v
   python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_gear_observed_backfill_profile_window_resumes_and_wraps -v
   ```

3. Implement state helpers in `server/websim_payload.py`.

   Suggested functions:

   ```python
   GEAR_OBSERVED_BACKFILL_SYNC_KEY = "gear_observed_backfill"

   def read_gear_observed_backfill_state(conn, target_item_ids=None, provider="raiderio"):
       ...

   def write_gear_observed_backfill_state(conn, state):
       ...

   def normalize_gear_observed_backfill_state(raw_state, target_item_ids=None, provider="raiderio"):
       ...

   def build_gear_observed_backfill_window(target_item_ids, candidate_profiles, state, *, target_limit, profile_limit):
       ...
   ```

   Implementation notes:

   - Reuse `ensure_websim_tables`.
   - Store state JSON with `set_sync_state(conn, "gear_observed_backfill", state)`.
   - Keep Raider.IO as the v1 provider and WCL as a `not_implemented` provider status.
   - Keep state read/write local and deterministic.
   - Hash ordered target item IDs with SHA-256 over a stable JSON representation.

4. Re-run all new tests plus existing target item selection tests:

   ```bash
   python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_gear_observed_backfill_state_defaults_when_missing -v
   python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_gear_observed_backfill_state_persists_in_websim_sync_state -v
   python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_gear_observed_backfill_cursor_resets_when_target_hash_changes -v
   python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_gear_observed_backfill_profile_window_resumes_and_wraps -v
   python3 -m unittest tests.raiderio_payload_test.RaiderIOPayloadTest.test_sync_raiderio_cache_uses_partial_gear_variants_as_target_items -v
   python3 -m unittest tests.raiderio_payload_test.RaiderIOPayloadTest.test_db_target_item_ids_round_robins_partial_items_by_source_and_slot -v
   ```

### Task 3: Create Independent Backfill Runner

Files:

- `server/gear_observed_backfill.py`
- `tests/gear_observed_backfill_test.py`
- `server/websim_payload.py`
- `server/raiderio_payload.py`

Steps:

1. Add failing runner tests.

   Test names:

   ```python
   test_observed_backfill_runner_updates_only_window_and_persists_cursor
   test_observed_backfill_runner_does_not_trigger_full_websim_sync_or_journal_fetch
   test_observed_backfill_runner_marks_partial_error_without_losing_cursor
   test_observed_backfill_runner_promotes_only_with_deterministic_tuple_evidence
   ```

   Test requirements:

   - Use temp SQLite DB.
   - Use fake/mocked Raider.IO candidate profiles and payload data.
   - Prove only the cursor window is processed.
   - Prove existing observed cache survives.
   - Prove runner calls additive observed sync.
   - Prove no Blizzard journal sync, full `sync_websim_gear_catalog`, or network fetch occurs unless explicitly mocked for the small Raider.IO window.
   - Prove state is persisted on both success and partial failure.

2. Run targeted tests and confirm they fail:

   ```bash
   python3 -m unittest tests.gear_observed_backfill_test -v
   ```

3. Implement `server/gear_observed_backfill.py`.

   CLI shape:

   ```bash
   python3 server/gear_observed_backfill.py \
     --db "${WOW_NEWS_DB}" \
     --target-limit 80 \
     --profile-limit 40 \
     --timeout-seconds 600 \
     --json
   ```

   Runner responsibilities:

   - Open the existing SQLite DB.
   - Ensure required tables exist.
   - Read target item IDs from existing gear catalog state using current Raider.IO target selection logic.
   - Read/persist observed backfill cursor state.
   - Build a bounded target/profile window.
   - Fetch or assemble only the requested Raider.IO profile window.
   - Call `sync_observed_gear_variants(..., replace=False)`.
   - Call the existing deterministic promotion function after additive sync.
   - Update gear catalog counts/state if the local helper already exists; otherwise leave health to compute from tables.
   - Emit stage events as JSON lines to stderr.
   - Emit one final JSON summary to stdout.
   - Return non-zero only for real runner failures; partial data misses should be represented in state and summary.

   Output summary fields:

   ```json
   {
     "status": "ok|partial|error",
     "targetItemCount": 0,
     "processedTargetItemIds": [],
     "processedProfileCount": 0,
     "observedVariantRowsUpserted": 0,
     "officialVariantsPromoted": 0,
     "cursor": {},
     "durationSeconds": 0.0
   }
   ```

4. Re-run runner tests:

   ```bash
   python3 -m unittest tests.gear_observed_backfill_test -v
   ```

### Task 4: Expose Backfill Progress in Data Health

Files:

- `server/news_backend.py`
- `server/websim_payload.py`
- `tests/news_backend_test.py`

Steps:

1. Add failing health tests.

   Test names:

   ```python
   test_data_health_payload_includes_observed_backfill_state_without_syncing
   test_data_health_payload_includes_observed_backfill_defaults_without_syncing
   ```

   Test requirements:

   - Seed a backfill state row in `websim_sync_state`.
   - Build `/api/data/health` payload.
   - Assert payload includes an `observedBackfill` object under `gear_catalog.details`.
   - Assert `allow_sync=False` behavior remains unchanged.
   - Assert missing state renders explicit defaults instead of omitting the section.

2. Run targeted tests and confirm they fail:

   ```bash
   python3 -m unittest tests.news_backend_test.NewsBackendTest.test_data_health_payload_includes_observed_backfill_state_without_syncing -v
   python3 -m unittest tests.news_backend_test.NewsBackendTest.test_data_health_payload_includes_observed_backfill_defaults_without_syncing -v
   ```

3. Update health payload.

   Suggested shape:

   ```json
   {
     "gear_catalog": {
       "details": {
         "observedBackfill": {
           "provider": "raiderio",
           "providers": {"raiderio": {"status": "idle"}, "wcl": {"status": "not_implemented"}},
           "lastRunStatus": "idle|running|ok|partial|error",
           "processedTargetItemCount": 0,
           "processedProfileCount": 0,
           "matchedTargetItemIds": [],
           "lastRunStartedAt": null,
           "lastRunFinishedAt": null,
           "lastError": null,
           "cursor": {
             "targetItemHash": "",
             "targetItemCount": 0,
             "targetOffset": 0,
             "profileOffset": 0
           }
         }
       }
     }
   }
   ```

   Keep payload compact. Do not expose raw candidate profiles or secrets.

4. Re-run targeted tests:

   ```bash
   python3 -m unittest tests.news_backend_test.NewsBackendTest.test_data_health_payload_includes_observed_backfill_state_without_syncing -v
   python3 -m unittest tests.news_backend_test.NewsBackendTest.test_data_health_payload_includes_observed_backfill_defaults_without_syncing -v
   ```

### Task 5: Add Short Systemd Service and Timer

Files:

- `server/wow-gear-observed-backfill.service`
- `server/wow-gear-observed-backfill.timer`
- `server/deploy_lighthouse.sh`
- `tests/deploy_lighthouse_test.py`

Steps:

1. Inspect current deploy script before editing:

   ```bash
   sed -n '1,240p' server/deploy_lighthouse.sh
   ```

2. Add failing deploy/config tests in `tests/deploy_lighthouse_test.py`.

   Test names:

   ```python
   test_observed_backfill_service_uses_independent_runner_with_short_timeout
   test_deploy_script_installs_observed_backfill_timer_without_enabling_unbounded_sync
   ```

   Test requirements:

   - Service invokes `server/gear_observed_backfill.py`, not `server/websim_sync.py`.
   - Service uses `flock` or equivalent lock protection.
   - Service has short timeout and bounded environment defaults.
   - Timer schedule is separate from `wow-websim-sync.timer`.
   - Deploy script installs service/timer files.
   - Deploy script does not automatically enable or start `wow-gear-observed-backfill.timer` or `.service`.

3. Run targeted tests and confirm they fail:

   ```bash
   python3 -m unittest tests.deploy_lighthouse_test.DeployLighthouseScriptTest.test_observed_backfill_service_uses_independent_runner_with_short_timeout -v
   python3 -m unittest tests.deploy_lighthouse_test.DeployLighthouseScriptTest.test_deploy_script_installs_observed_backfill_timer_without_enabling_unbounded_sync -v
   ```

4. Add service file.

   Expected properties:

   - `Type=oneshot`
   - `TimeoutStartSec=10min` or similarly bounded
   - environment defaults for `WOW_GEAR_OBSERVED_BACKFILL_TARGET_LIMIT`, `WOW_GEAR_OBSERVED_BACKFILL_PROFILE_LIMIT`, and timeout
   - uses existing DB env convention through `WOW_NEWS_DB`
   - uses lock file separate from or compatible with current WebSim sync lock
   - logs JSON output to journald

5. Add timer file.

   Expected properties:

   - Runs more frequently than the full sync but remains bounded, such as every 30-60 minutes with randomized delay.
   - `Persistent=true`
   - Does not overlap due to service lock.

6. Update deployment script only if service installation is managed there today.

7. Re-run targeted deploy tests:

   ```bash
   python3 -m unittest tests.deploy_lighthouse_test.DeployLighthouseScriptTest.test_observed_backfill_service_uses_independent_runner_with_short_timeout -v
   python3 -m unittest tests.deploy_lighthouse_test.DeployLighthouseScriptTest.test_deploy_script_installs_observed_backfill_timer_without_enabling_unbounded_sync -v
   ```

### Task 6: Add Local Runbook and Verification Notes

Files:

- `docs/plans/2026-06-22-gear-observed-variant-backfill.md`
- Optional: `docs/database-architecture.md` if the implementation adds a stable new operational contract.

Steps:

1. Add an implementation evidence section to this plan after code lands.

   Include:

   - New runner command.
   - New health payload shape.
   - New service/timer names.
   - Local test commands and results.
   - Any remaining production blockers.

2. Do not add remote commands as completed evidence unless they were actually run.

3. Production runbook must start with a DB backup/copy step and require explicit approval before remote writes.

   Example shape only:

   ```bash
   # Example only. Do not run without explicit approval.
   ssh ubuntu@124.223.51.33 'cp "$WOW_NEWS_DB" "$WOW_NEWS_DB.backup.$(date +%Y%m%d-%H%M%S)"'
   ssh ubuntu@124.223.51.33 'sudo systemctl start wow-gear-observed-backfill.service'
   ssh ubuntu@124.223.51.33 'curl -fsS http://127.0.0.1:3000/api/data/health'
   ```

4. If network reads are needed for live verification, ask before any remote-write operation and do not save downloaded content locally without approval.

## Verification Plan

Run focused tests while implementing:

```bash
python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_sync_observed_gear_variants_can_incrementally_upsert_without_replacing_cache -v
python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_sync_observed_gear_variants_preserves_larger_verified_cache_from_smaller_payload -v
python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_gear_observed_backfill_state_defaults_when_missing -v
python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_gear_observed_backfill_state_persists_in_websim_sync_state -v
python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_gear_observed_backfill_cursor_resets_when_target_hash_changes -v
python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_gear_observed_backfill_profile_window_resumes_and_wraps -v
python3 -m unittest tests.gear_observed_backfill_test -v
python3 -m unittest tests.news_backend_test.NewsBackendTest.test_data_health_payload_includes_observed_backfill_state_without_syncing -v
python3 -m unittest tests.news_backend_test.NewsBackendTest.test_data_health_payload_includes_observed_backfill_defaults_without_syncing -v
python3 -m unittest tests.deploy_lighthouse_test.DeployLighthouseScriptTest.test_observed_backfill_service_uses_independent_runner_with_short_timeout -v
python3 -m unittest tests.deploy_lighthouse_test.DeployLighthouseScriptTest.test_deploy_script_installs_observed_backfill_timer_without_enabling_or_starting -v
git diff --check
```

Before push or production deployment, run the broader suite:

```bash
python3 -m unittest discover -s tests -p '*_test.py'
node --test tests/*.test.js
python3 server/simulator_e2e_smoke.py
git diff --check
```

Before any commit/push in this repo, run CodeRabbit review per current project workflow and fix technically valid findings before re-verifying.

## Implementation Evidence

Implemented locally on 2026-06-22:

- Added `server/gear_observed_backfill.py` with a bounded Raider.IO provider v1 and a fake-provider-friendly runner entrypoint.
- Added `sync_observed_gear_variants(..., replace=False)` so cursor batches can upsert observed evidence without deleting the verified observed cache.
- Added `websim_sync_state.key='gear_observed_backfill'` state helpers with provider status, cursor offsets, processed counts, matched target IDs, and WCL reserved as `not_implemented`.
- Exposed `gear_catalog.details.observedBackfill` in `/api/data/health` without triggering sync.
- Added `wow-gear-observed-backfill.service` and `.timer`; deploy installs them but does not enable or start them.

Local focused verification run in this implementation:

```bash
python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_sync_observed_gear_variants_can_incrementally_upsert_without_replacing_cache tests.websim_payload_test.WebSimPayloadTest.test_sync_observed_gear_variants_preserves_larger_verified_cache_from_smaller_payload tests.websim_payload_test.WebSimPayloadTest.test_sync_observed_gear_variants_preserves_verified_cache_when_raiderio_source_is_partial tests.websim_payload_test.WebSimPayloadTest.test_gear_observed_backfill_state_defaults_when_missing tests.websim_payload_test.WebSimPayloadTest.test_gear_observed_backfill_state_persists_in_websim_sync_state tests.websim_payload_test.WebSimPayloadTest.test_gear_observed_backfill_cursor_resets_when_target_hash_changes tests.websim_payload_test.WebSimPayloadTest.test_gear_observed_backfill_profile_window_resumes_and_wraps -v
python3 -m unittest tests.gear_observed_backfill_test -v
python3 -m unittest tests.news_backend_test.NewsBackendTest.test_data_health_payload_includes_observed_backfill_defaults_without_syncing tests.news_backend_test.NewsBackendTest.test_data_health_payload_includes_observed_backfill_state_without_syncing tests.news_backend_test.NewsBackendTest.test_data_health_payload_includes_gear_catalog_component tests.news_backend_test.NewsBackendTest.test_data_health_payload_exposes_raiderio_target_item_coverage -v
python3 -m unittest tests.deploy_lighthouse_test.DeployLighthouseScriptTest.test_observed_backfill_service_uses_independent_runner_with_short_timeout tests.deploy_lighthouse_test.DeployLighthouseScriptTest.test_deploy_script_installs_observed_backfill_timer_without_enabling_or_starting tests.deploy_lighthouse_test.DeployLighthouseScriptTest.test_websim_sync_service_budget_covers_full_season_gear_catalog -v
```

No production backfill, remote write, deploy, or external data download was run as part of this implementation.

## Rollback Plan

- The new runner is independent; disabling `wow-gear-observed-backfill.timer` stops the new path.
- Additive observed sync preserves existing rows, so a failed small run should not delete the prior observed cache.
- Backfill state lives under `websim_sync_state.key='gear_observed_backfill'` and can be reset by deleting that row after a DB backup.
- Existing full WebSim sync keeps `replace=True` and remains the compatibility path.

## Acceptance Criteria

- Unit tests prove additive observed upsert does not wipe existing observed cache.
- Unit tests prove replacement mode still blocks downgrades.
- Unit tests prove cursor state persists, resumes, resets on target hash change, and wraps.
- Runner tests prove bounded processing and no accidental full sync or journal fetch.
- Health tests prove `/api/data/health` exposes progress without syncing.
- Deploy tests prove the new service/timer is independent and bounded.
- Docs state that production execution requires explicit approval, backup first, and health verification afterward.
