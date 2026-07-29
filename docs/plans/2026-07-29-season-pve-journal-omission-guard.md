# Season PVE Journal Omission Guard

> **Harness slice:** Strict, scheduled Journal discovery/write-path repair.

**Goal:** Prevent PostgreSQL Journal ingestion from silently omitting capped,
failed, or fallback source relations, replacing the last-known-good Journal
tables with an incomplete snapshot, or allowing the derived Catalog state to
describe the surviving subset as verified.

## User-visible harm

An omitted Journal instance, encounter, or item never reaches staging. The
equipment simulator can then show a plausible non-empty list while silently
missing current-season PVE gear. A 40-specialization traversal of that same
subset cannot detect the upstream omission.

## Root cause

The PostgreSQL path differed from the older SQLite path:

- `fetch_websim_journal_data_postgres` discarded skipped encounter counts and
  silently continued after the item cap;
- an empty discovered raid pool could be replaced by static fallback refs
  without a fallback gap;
- `sync_websim_cache_postgres` ignored discovery counts and always called the
  replacing writer;
- `replace_websim_journal_data` cleared the current Journal tables without an
  input-completeness gate;
- `rebuild_websim_gear_catalog_from_loot` judged only the surviving rows, so a
  non-empty subset could retain a verified source status.

## Contract

The PostgreSQL Journal discovery result must carry:

- configured dungeon/raid-instance, encounter, and item limits;
- exact omitted counts for each capped boundary;
- one machine-readable gap for every cap, fetch failure, or fallback;
- one membership gap whenever the expected current-season raid pool is only
  partially discovered, even if at least one raid ref survived;
- stable blocker codes and literal `sourceStatus=blocked` while any gap exists;
- `membershipComplete=true` only when all four boundary limit/truncation
  counters, fetch-failure count, diagnostic lists, and zero-gap/zero-blocker
  evidence exist.

Only a complete discovery result may enter
`PostgresCacheStore.replace_websim_journal_data`. Both the sync orchestrator
and the writer enforce this. An incomplete result preserves the existing
Journal and derived Catalog rows and records blocked sync state.

## Tasks

### Task 1 — Reproduce the silent omission

- [x] RED: encounter and item caps are absent from PostgreSQL discovery counts.
- [x] RED: incomplete discovery still invokes Journal replacement and Catalog
  rebuild.
- [x] RED: the writer executes SQL for a capped discovery snapshot.
- [x] RED: static raid-ref fallback is not represented as a blocker.
- [x] RED: a partially discovered raid pool is treated as complete.
- [x] RED: success flags can bypass the writer without four-boundary counts.

### Task 2 — Repair the fact-owner chain

- [x] Emit cap, fetch-failure, and fallback gaps from PostgreSQL discovery.
- [x] Add one pure Journal discovery completeness contract.
- [x] Reject incomplete discovery in the sync orchestrator.
- [x] Reject incomplete discovery before the writer opens a transaction or
  emits SQL.
- [x] Reject partial raid membership and structurally incomplete discovery
  evidence.
- [x] Preserve the last-known-good Journal and Catalog state.

### Task 3 — Verify without external fetch

- [x] Run deterministic fixture-based sync/store tests.
- [x] Run full adjacent backend and Harness verification on exact head.
- [ ] Deploy one immutable candidate with async syncs disabled.
- [ ] Run synthetic blocked/verified contract smokes in the candidate without
  invoking Blizzard or writing PostgreSQL.
- [ ] Verify production and candidate health plus rollback identity.

## Stop lines

- no Blizzard/API download or source sync before explicit network-data
  approval;
- no PostgreSQL data mutation, backfill, Catalog build, active pointer, timer,
  or Manifest change in verification;
- no compatibility path that treats missing counts as complete;
- no merge before exact-head CI and immutable candidate evidence.
