# 2026-06-23 Current Change Rollup

This note summarizes the current dirty worktree before final review, deploy, and landing.

## Scope Summary

- Review workflow: `AGENTS.md` now states CodeRabbit is not a required gate; commits, deploys, and handoff should rely on local tests, smoke checks, diff review, runtime logs, and user-requested review tools.
- Deploy workflow: `server/deploy_lighthouse.sh` validates deploy env values, supports hot deploy via `WOW_DEPLOY_SKIP_BOOTSTRAP=1`, performs service smoke checks before optional async sync starts, and requires explicit `WOW_DEPLOY_START_ASYNC_SYNCS=1` before kicking long sync jobs.
- Current season pool: `server/game-season.js` and `server/websim_payload.py` carry the confirmed Midnight Season 1 M+ and raid pools; Manaforge Omega is blocked as the current-season raid fallback.
- Gear trust model: `server/websim_payload.py` separates accepted `source_reference` from `journal_candidate`, `excluded_legacy_bucket`, `observed_confirmed`, and `source_discrepancy`; raw Battle.net Journal data is retained for traceability but no longer accepted as current-season M+ coverage.
- Reused legacy dungeon correction: Pit of Saron, Seat of the Triumvirate, and Skyreach now have explicit source-reference item id sets. Production DB write preserved raw rows while promoting only accepted current-season items.
- Gear health and traversal: `/api/data/health` now uses the standalone `gearCatalog` sync state when present, so health reflects the latest targeted gear catalog state instead of stale nested `websim_sync.gearCatalog` snapshots.
- Observed gear stat provenance: `server/gear_observed_backfill.py` and `server/websim_payload.py` can parse SimulationCraft JSON gear output for observed variants, preserve `simulationcraft` stat evidence, mark failed SimC item/profile resolution, and avoid treating Raider.IO/WCL profile APIs as production stat sources.
- Raider.IO payload trimming and sync guards: `server/raiderio_payload.py` keeps build summaries compact by default and only includes heavy details when requested; cache/sync paths include deadline/concurrency/error handling and observed-cache downgrade protection.
- Builds gear UI: `pages/builds/detail.js` distinguishes missing stats from missing drop sources, keeps heavy candidate payloads out of `setData`, enriches sparse selected items from cached candidates, handles optional off-hand saves, preserves socket/enchant selections, and blocks or warns on untrusted templates without pretending partial evidence is verified.
- Tests: WebSim, news backend, Raider.IO, observed backfill, deploy script, builds home/page, and related payload tests were expanded around trust-state boundaries, health state selection, compact gear payloads, source filters, deterministic SimC readiness, and current-season pool blockers.

## Production Data Actions Already Performed

- Backup before reused-dungeon write: `/opt/wow-mini-program/backups/wow_news.sqlite3.20260623T100725Z.pre-reused-legacy-source-reference.bak`
- Pit of Saron: `24 source_reference`, `25 journal_candidate`, `25 excluded_legacy_bucket`.
- Seat of the Triumvirate: `34 source_reference`, `1 source_discrepancy`, `9 journal_candidate`.
- Skyreach: `28 source_reference`, `202 excluded_legacy_bucket`.
- Accepted reused-dungeon variants updated: `141`; restored `62` deterministic variants to `verified`; kept `79` as `partial` with `missing deterministic SimC variant preset`.
- Production `/api/data/health` after health-state fix: M+ coverage `8/8`, M+ `sourceItemCount=203`; raid source coverage remains outside this reused-dungeon write scope.
- Production compact gear traversal: `40` class/spec combinations, `failureCount=0`, candidate rows `75-99`.

## Files By Area

- Policy/docs: `AGENTS.md`, `docs/roadmap.md`, `docs/roadmap/ideas.md`, `docs/plans/2026-06-23-season-gear-instance-slice-plan.md`, `docs/plans/2026-06-23-reused-dungeon-current-season-candidates.md`.
- Frontend: `pages/builds/detail.js`.
- Backend API/sync/deploy: `server/news_backend.py`, `server/websim_payload.py`, `server/gear_observed_backfill.py`, `server/raiderio_payload.py`, `server/game-season.js`, `server/builds/home-payload.js`, `server/deploy_lighthouse.sh`.
- Tests: `tests/websim_payload_test.py`, `tests/news_backend_test.py`, `tests/gear_observed_backfill_test.py`, `tests/raiderio_payload_test.py`, `tests/builds-page.test.js`, `tests/builds-home-payload.test.js`, `tests/deploy-script.test.js`.

## Landing Checklist

- Run local review over the full diff, with special attention to production DB safety, stale sync state, long-running sync timers, user data ownership, LLM trust boundaries, and source/status wording.
- Re-run required local tests before deployment:
  - `python3 -m unittest tests.websim_payload_test`
  - `python3 -m unittest tests.news_backend_test`
  - `node --test tests/builds-page.test.js`
  - `git diff --check`
- Deploy with hot mode only, without bootstrap/download/install and without starting async sync jobs:
  - `WOW_DEPLOY_SKIP_BOOTSTRAP=1 ./server/deploy_lighthouse.sh`
- After deploy, verify:
  - `/api/game/season`
  - `/api/data/health`
  - all `40` class/spec compact gear traversal
- Stage, commit, and push only after deploy verification passes and the final scope is confirmed.
