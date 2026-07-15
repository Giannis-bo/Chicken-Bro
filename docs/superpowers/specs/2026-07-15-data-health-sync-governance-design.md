# Data Health Sync Governance Design

## Status

`approved_for_implementation` — the user approved the direction on 2026-07-15 and explicitly authorized implementation under Harness v0.6.

## Current truth and root cause

`docs/project-state.json` names Harness v0.6 as the active delivery contract. The archived talent-link incident proves that a damaged PostgreSQL talent graph needs one controlled SimC-only recovery, not a deploy-triggered or full data refresh. `server/data_health_followup.py` currently starts gear backfill, the full `wow-websim-sync.service`, and stat-weight sync solely from health status and blocker text. It records neither input revision nor a prior attempt, so an unchanged partial catalog can restart the same heavy chain every two hours.

`server/websim_sync.py` already supports `WOW_WEBSIM_SKIP_BLIZZARD=1` and `WOW_WEBSIM_SKIP_RAIDERIO=1`, but there is no dedicated systemd unit for that narrow path. The existing `cache.websim_sync_state` repository is the write owner for persistent sync state; health/admin remains a consumer of it.

## Requirement contract

### User scenario and promise

Operators can distinguish a code-only bugfix from a proved materialized-data incident. The timer observes health every two hours but does not repeatedly launch heavyweight collection for an unchanged blocker. A confirmed talent-graph incident has a named, locked, SimC-only recovery path.

### In scope

- Persist a revision-gated follow-up ledger in the existing PostgreSQL `websim_sync_state` repository.
- Make first observation baseline-only; only an explicit `refreshNeeded`, a changed domain input revision, or a manual forced action can start a heavy job.
- Remove automatic full WebSim continuation from health follow-up; the existing daily WebSim timer remains the normal full/reconciliation path.
- Add a manually invoked, globally locked `wow-talent-graph-recovery.service` that skips Blizzard and Raider.IO.
- Publish the current decision/result in `/api/data/health`, the timer journal, runbook, roadmap, and release evidence.

### Non-goals

- No schema migration: the existing sync-state JSON record is reused.
- No wholesale Journal/loot incremental-write rewrite, no new external data source, and no deletion policy change.
- No automated talent recovery: a graph repair still requires read-only preflight and an explicit operator action.
- No deploy-triggered asynchronous sync, no public payload semantic change, and no change to the daily `wow-websim-sync.timer` cadence.

## Alternatives considered

| Option | Result |
| --- | --- |
| Keep status-only health retry and shorten its interval | Rejected: preserves the root cause and can increase repeated load. |
| Disable all follow-up automation permanently | Rejected: loses bounded recovery for new, objectively changed input. |
| Revision-gated ledger plus narrow manual recovery | Selected: fail-closed on missing state, preserves daily reconciliation, and separates data repair from normal bugfix deployment. |

## Architecture

```text
/api/data/health
  -> data_health_followup policy (read health + sync-state ledger)
  -> first sighting: record baseline, report-only
  -> changed revision or refreshNeeded: claim one domain action in ledger
  -> systemd unit
       -> observed gear backfill OR stat weights

manual proof of talent graph damage
  -> backup + read-only LKG/candidate preflight
  -> --force-action talent_graph_recovery
  -> wow-talent-graph-recovery.service
  -> shared sync lock + SimC/TraitEdge only
```

### Domain fingerprints

The policy must derive a stable fingerprint from explicit domain input revisions only, never `checkedAt`, transient counts, or a blocker string.

- `gear_observed_backfill`: `gear_catalog.details.catalogContract.revision`, falling back to `variantRevision` then `itemDatabaseRevision`.
- `stat_weights_sync`: the ordered non-empty revision tuple exposed by stat-weight health (`inputRevision`, `gearCatalogRevision`, `raiderioRevision`, `simcRuntimeRevision`).
- `simc_runtime_update`: the available runtime target revision/commit from the SimC health gate.

If no explicit input revision exists, the policy is `report_only` and exposes a manual blocker; it never invents a fingerprint from status text. Full `websim_sync` has no auto-follow-up path.

### Ledger semantics

The single state key `data_health_followup_v1` contains per-action `lastSeenRevision`, `lastAttemptedRevision`, `lastDecision`, `lastDecisionAt`, and bounded report-only reasons. The first sighting writes `lastSeenRevision` but schedules nothing. A new revision is allowed once and is claimed before systemd is started. The same revision thereafter remains report-only, including after an asynchronous worker failure; an operator must repair/force it or wait for a new input revision. This is deliberately fail-closed.

### Ownership and observability

`PostgresCacheStore` remains the sync-state write owner. `data_health_followup.py` is an orchestrator and may only read/write `data_health_followup_v1`; it cannot alter catalog quality or clear another job's blockers. `news_backend.py` adds a consumer-only health component that reports the saved decision, revisions, and report-only reasons. The CLI emits the complete plan/result JSON to the systemd journal.

### Failure handling and rollback

No PostgreSQL state store, absent revision, malformed health payload, or unknown force action yields a non-destructive report-only result. The recovery unit uses the existing global lock. Rollback is `config_disable` (disable the follow-up timer/unit), `code_rollback`, and `data_restore` using the preflight backup; `resync_repair` remains available only after a new validated preflight.

## Acceptance evidence

- TDD covers first observation, unchanged revision, changed revision, explicit refresh, absent revision, unknown force action, and forced talent recovery.
- Unit tests prove no policy path automatically selects `wow-websim-sync.service`.
- Unit/deploy tests prove the narrow recovery has both skip flags and the shared lock; daily full sync remains installed but inactive after candidate smoke.
- PostgreSQL store tests prove the ledger remains JSONB sync-state data and the health component is consumer-only.
- Candidate deployment records backup, exact runtime parity, no deploy-triggered async sync, health/API smoke, unit/timer status, journal decision, and rollback path before merge.
