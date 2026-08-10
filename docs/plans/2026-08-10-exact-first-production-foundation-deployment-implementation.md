# Exact-first Production Foundation Deployment Implementation Plan

> **For agentic workers:** execute sequentially in one isolated worktree. The task has one production database target; do not use parallel deployers. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the already candidate-verified Exact-first runtime and migrations `0030`--`0035` to production while proving that provider, worker and all asynchronous writers remain disabled.

**Architecture:** The task changes no runtime source. A surgical runbook copies only the merged runtime from `f4dbb13c`, records file-hash parity because the remote release directory is not a Git checkout, takes a PostgreSQL backup, applies the append-only migration chain once, and restarts only `wow-backend`. A subsequent aggregate preflight is read-only and cannot create a release, binding, job or worker activity.

**Tech Stack:** existing bash/SSH, PostgreSQL `psql`/`pg_dump`, systemd, Python 3, repository Harness; no dependency installation and no local PostgreSQL.

## Global Constraints

- Use `/Users/boyuan/Documents/wow_mini_program/.worktrees/codex-exact-first-production-foundation-admission` at merged runtime `f4dbb13c`; verify that its runtime tree equals Task 5C candidate runtime `70e37b6f` before remote writes.
- Do not call `server/deploy_lighthouse.sh`; it touches unrelated timers/services. Do not install, download, fetch third-party data, start async sync/backfill, modify Catalog/Manifest/generation 35, or change mini-program source.
- Production database begins at `0029`; backup before write, apply only ordered `0030`--`0035` under one `psql -1 -v ON_ERROR_STOP=1` transaction, then verify exactly 35 ledger rows.
- Exact provider remains the existing default `None`; exact HTTP must continue to return `EXACT_AUTHORITY_UNAVAILABLE`. Do not install/enable/start `wow-gear-exact-authority-worker`.

### Task 1: Freeze Source, Capacity and Rollback Inputs

**Files:**
- Read: `server/`, `server/migrations/postgres/0030_websim_exact_authority_bundle.sql` through `0035_websim_exact_runtime_authority_release.sql`
- Read: `artifacts/releases/2026-08-10-equipment-simulator-exact-first-task5c-runtime-authority-release/evidence.json`
- Write remotely: one timestamped PostgreSQL custom-format backup and one 0700 deployment evidence directory under `/var/lib/wow-backend/`.

**Interfaces:**
- Consumes: candidate commit/tree and migration `0035` SHA from Task 5C evidence.
- Produces: redacted preflight record containing capacity, backend/timer/worker states, ledger count/max, runtime file hashes and backup path.

- [x] **Step 1: Verify runtime equivalence locally**

Run:

```bash
git diff --quiet 70e37b6fd88bee7dc0004d4cba6fec5aef820e02 \
  f4dbb13c2536eab3ae11367410fe79f1e1a2d2f1 -- server apps/mini-taro packages
```

Expected: exit `0`; any runtime diff stops the task and requires a new candidate.

- [x] **Step 2: Capture production preflight before writes**

Run read-only SSH checks for `df`, load, available memory, `wow-backend`, exact-worker unit state, timer list, `WOW_DATABASE_RUNTIME`, migration max/count and absence of `0035` release tables. Record only counts/statuses; never DSN or personal rows.

Expected: root free space is at least the Task 5C candidate's recorded `5,072,632 KiB`, backend is active, its current `/health` returns HTTP `200` at the service's verified local listener `127.0.0.1:8787`, worker inactive/absent, ledger is `0029`/29, and provider remains disabled. Any lower capacity or failed health check stops before backup or transfer.

- [x] **Step 3: Make a recoverable database backup**

Derive the database name only in remote process memory from `WOW_DATABASE_URL`; invoke `sudo -u postgres pg_dump --format=custom --file <timestamped-0700-path> <database>`, validate with `pg_restore --list`, and record its SHA-256/path without credentials.

Expected: one non-empty validated backup before any migration. Backup failure stops the task with zero migration writes.

### Task 2: Surgical Runtime Transfer and Append-only Migration

**Files:**
- Runtime transfer source: existing repository `server/` at `f4dbb13c`; no source modification. `apps/mini-taro/` and `packages/` are verified unchanged against the candidate but are not transferred by this backend-only task.
- Remote target: `/opt/wow-mini-program` plus a timestamped local-file rollback directory under `/var/lib/wow-backend/`.

**Interfaces:**
- Consumes: Task 1 backup and exact file SHA-256 inventory.
- Produces: production ledger `0030`--`0035`, matching runtime file hashes, one restarted backend, unchanged timer/worker state.

- [x] **Step 1: Stage and verify runtime bytes**

Create a remote 0700 staging directory, transfer the merged repository source without `.git`, `server/data`, caches or credentials, and record SHA-256 for each runtime file changed between the previous deployed baseline and `f4dbb13c`. Copy prior target files to the rollback directory before replacement. Write a remote release stamp containing the immutable commit/tree only after all hashes match.

Expected: source parity is proven by file hashes, not a false remote Git claim. A transfer/hash mismatch restores copied files and stops before migration.

- [x] **Step 2: Apply the exact migration chain once**

Use `sudo -u postgres psql -1 -v ON_ERROR_STOP=1 -d <production-db>` with ordered files `0030_websim_exact_authority_bundle.sql`, `0031_websim_exact_snapshot_v2.sql`, `0032_websim_exact_import_jobs.sql`, `0033_websim_exact_template_authority_binding.sql`, `0034_websim_exact_job_snapshot_binding.sql`, `0035_websim_exact_runtime_authority_release.sql`.

Expected: transaction commits only when all six files pass. Requery `ops.schema_migrations` for 35 rows, max `0035_websim_exact_runtime_authority_release`, exact new table/function ACLs, and no mutation of Catalog/Manifest/generation 35.

- [x] **Step 3: Restart only the backend and smoke the disabled boundary**

Run `systemctl restart wow-backend`; do not run `enable`, `start`, `restart` or `daemon-reload` for any timer or Exact worker. Verify `http://127.0.0.1:8787/health`, existing public simulator home, PostgreSQL-only runtime mode, 35 migration rows, `wow-gear-exact-authority-worker` inactive/absent and Exact confirm unavailable/blocked with no task row.

Expected: backend recovers; provider remains disabled and no user-facing Exact-ready claim is emitted.

### Task 3: Bounded First-source Readiness Audit

**Files:**
- Read: `cache.websim_gear_exact_*`, `cache.websim_canonical_documents`, `cache.websim_exact_authority_bundles`, `app.websim_exact_template_authority_bindings`, `ops.websim_exact_runtime_resolver_contexts`, `ops.websim_exact_runtime_authority_releases`, `ops.websim_exact_runtime_occurrence_index_entries`, and `app.build_templates`.
- Write: task evidence only after aggregate, redacted counts are independently verified.

**Interfaces:**
- Consumes: post-migration schema and owner-scoped saved source contracts.
- Produces: `eligible_source_count` and reason-class counts; never a release, binding, job, provider or worker state change.

- [x] **Step 1: Count each gate independently**

Query aggregate counts for: full verified community template groups; authenticated remote gear/talent templates; 0030 Authority Bundles; 0033 bindings; 0035 resolver contexts/releases/occurrence-index rows; and any source that is exactly one-to-one across every gate. Do not select user ids, template ids, profile values, raw authority bytes or `latest` rows.

Expected: every count is evidence only. A count of zero is a valid terminal result, not an error to repair by inference.

- [x] **Step 2: Apply the stop rule**

If `eligible_source_count=0`, preserve provider/worker disabled, create zero jobs and report the concrete missing gate classes. If the count is positive, stop this task before activation and open a separately allowlisted one-source provider/worker task with its own candidate, rollback and four existing-page manual acceptance items.

Expected: no migration/deploy signal is presented as a player-ready Exact loop.

Recorded result: `eligible_source_count=0`; saved gear/talent templates, authority bundles, bindings, resolver contexts, releases, occurrence-index entries and import jobs were all zero. Provider/worker remain disabled and this task starts no activation follow-up.

## Plan Self-review

- Task 1 makes the production target and rollback evidence explicit before a write.
- Task 2 changes only the already candidate-verified runtime/migration foundation and proves no timer/worker/provider expansion.
- Task 3 has a finite output even when no eligible source exists; Task 5E is neither read nor required.
