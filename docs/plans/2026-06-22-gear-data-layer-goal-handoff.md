# Gear Data Layer Goal Handoff

Keyword: `GEAR-DATA-LAYER-HANDOFF-2026-06-22`

This handoff freezes the long-running equipment data-layer goal at a safe
handoff point. The original goal is not marked complete because the official
season gear catalog still has deterministic SimC variant gaps. It is safe to
continue normal development from the latest `main` and split the remaining work
into smaller background jobs.

## Current Repository State

- Latest merged commit: `675e197 feat: stabilize season gear catalog sync`.
- Local and remote `main` were aligned when this handoff was written.
- The long goal was stopped as `blocked`, not `complete`.
- No production sync or database mutation is required just to continue from this
  document.

## Goal Progress

### Delivered

- Built the season-owned gear catalog around Battle.net, Raider.IO observed
  gear, SimC metadata, and local SQLite cache state.
- Added readiness separation between data trust and simulation executability:
  `dataReadiness` can be verified while `simulationReadiness` remains partial.
- Added Battle.net item metadata validation for item stats, armor type, weapon
  type, inventory slot, and source linkage.
- Preserved current-season dungeon, raid, and tier-set source records instead of
  treating display-only fallback data as verified simulation variants.
- Added socket and enchant mod-option metadata coverage, including gem metadata
  validation for socket options.
- Added official/observed source separation so Raider.IO player gear can
  backfill evidence without polluting official season readiness.
- Added observed-cache anti-downgrade protection so interrupted or partial
  Raider.IO scans do not replace a larger verified observed cache.
- Added Blizzard Journal interruption protection so a killed refresh does not
  clear existing verified dungeon, raid, and loot rows.
- Narrowed `gear_catalog_refresh_reason` so Blizzard Journal is not refetched
  only because SimC variant readiness is partial.
- Added WebSim sync stage JSONL progress events and `WOW_WEBSIM_SKIP_RAIDERIO=1`
  for safe smoke checks without triggering long Raider.IO scans.
- Demoted individual Raider.IO profile request timeouts into batch errors so one
  slow profile does not crash the whole sync.
- Surfaced gear catalog, Raider.IO target coverage, and readiness details through
  `/api/data/health`.
- Updated mini-program detail behavior so partial or non-executable gear
  candidates cannot be applied/saved as if they were SimC-ready.

### Production Snapshot At Handoff

The latest verified production health snapshot recorded for this goal:

- `gear_catalog.status`: `partial`
- `dataReadiness.status`: `verified`
- `simulationReadiness.status`: `partial`
- `itemCount`: 959
- `sourceCount`: 1649
- `officialVariantCount`: 1492
- `officialVerifiedVariantCount`: 1110
- `officialPartialVariantCount`: 382
- `observedVariantCount`: 2425
- `verifiedObservedVariantCount`: 2425
- Current-season Mythic+ coverage: 8/8
- Current-expansion raid coverage: 4/4
- Journal loot coverage: 783/783
- Item metadata: 959/959 verified
- Stat, armor, weapon, and slot mismatch counts: 0
- Socket options: 38 options covering 16 slots
- Enchant options: 53 options covering 8 slots
- Known remaining blocker: `missing deterministic SimC variant preset`

These numbers are a handoff snapshot. Recheck `/api/data/health` before using
them as current production truth.

### Verification Already Run

- `python -m py_compile server/websim_payload.py server/raiderio_payload.py server/websim_sync.py server/news_backend.py`
- `python -m unittest tests.websim_payload_test -v`
- `python -m unittest tests.raiderio_payload_test -v`
- `python -m unittest tests.websim_sync_test -v`
- Focused regression suite for timeout handling and Blizzard Journal skip logic.
- Production smoke on a temporary database with Raider.IO skipped.
- Production health checks after restore and redeploy.

## Why The Goal Is Blocked

The data layer is usable as a verified catalog, but the full simulator objective
still depends on 382 official source variants that do not have deterministic
SimC-ready item presets. The missing part is not basic metadata; it is the
current-season instance variant tuple that SimC can execute reliably, such as
the concrete `ilevel`, `bonus_id`, `gem_id`, and `enchant_id` combination.

Battle.net dungeon preview data is not enough for these items because several
sampled previews still point at stale or low-level historical variants. Do not
promote those previews into verified current-season SimC variants unless a more
authoritative source or real observed profile proves the tuple.

## Next ToDo

### P0: Cursorized Observed Variant Backfill

- Add a persistent cursor for Raider.IO target profile expansion so each run
  resumes from the last target offset instead of starting from zero.
- Keep each run short and bounded by a separate target-scan budget, not the main
  WebSim cache sync budget.
- Record cursor fields in cache state, for example last target item offset, last
  profile offset, next offset, last run status, and matched target item count.
- Expose the cursor and progress in `/api/data/health`.
- Preserve the current anti-downgrade rule: partial observed payloads must not
  replace a larger verified observed cache.
- Add tests proving that a second run resumes from the stored cursor and can
  eventually wrap around.
- Keep this as an independent background job or clearly separated sync phase so
  normal WebSim refreshes do not block on low-hit-rate profile scans.

### P0: Deterministic SimC Variant Promotion

- Promote an official source variant only when the backfill has a real
  SimC-executable tuple from observed gear or another trusted current-season
  source.
- Keep official readiness separate from observed evidence counts.
- Verify promoted tuples with SimC where practical before marking candidates
  `simcReady=true`.
- Add regression coverage for main-hand/off-hand compatibility and socketed
  variants.

### P1: WCL Gear Evidence Path

- Evaluate Warcraft Logs gear evidence as a second source for hard-to-hit items.
- Preserve the same trust contract: WCL can provide evidence, but it must not
  fabricate official season variants.
- Record source, report, fight, character, timestamp, and confidence boundary for
  any WCL-derived variant.

### P1: Production Operations

- Do not run another unbounded full sync from an interactive goal.
- Use SQLite backup API or a safe copy procedure before production DB probes.
- Prefer temporary database smoke tests first:
  `WOW_WEBSIM_SKIP_RAIDERIO=1 python3 server/websim_sync.py`.
- Only trigger production Raider.IO/WCL backfill after the cursor and per-run
  budget are in place.
- Watch `wow-websim-sync.service` journal for stage JSONL events if a sync is
  needed.

### P2: UI And Operator Follow-Up

- Keep partial gear candidates visible only with clear non-executable status.
- Add operator-facing copy for why some official items are data-verified but not
  simulation-ready.
- Consider a small dashboard panel for target backfill progress, matched item
  count, cursor position, and next scheduled run.

## Suggested Continuation Command

After pulling on another machine, use:

```powershell
rg "GEAR-DATA-LAYER-HANDOFF-2026-06-22" docs server tests
```

Start from this file, then inspect:

- `server/raiderio_payload.py`
- `server/websim_payload.py`
- `server/websim_sync.py`
- `server/news_backend.py`
- `tests/raiderio_payload_test.py`
- `tests/websim_payload_test.py`
- `tests/websim_sync_test.py`

The next implementation should begin with tests for the Raider.IO target cursor
and bounded background backfill.
