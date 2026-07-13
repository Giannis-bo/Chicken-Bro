# LAND & DEPLOY REPORT

- PR: #84 — fix: preserve talent-tree links with PostgreSQL LKG guards
- Branch: `codex/fix-talent-tree-links` → `main`
- Candidate: `28f3c54e2f78dd991df78b055f4ce361104980b8`
- Candidate tree: `e5a73ca89d2120df2394e2dffb55d8430ed1de9c`
- Merged: no; draft PR remains gated on real WeChat verification

## Timing

- Candidate backup and deploy: 2026-07-13 CST.
- Controlled sync: one locked SimC-only run after read-only preflight.
- Canary: single-pass production API, PostgreSQL and operations verification.

## Verification

- Local: targeted Python 855/855, gear compatibility 16/16, deploy contracts 15/15.
- Full Project Harness: 130/130 commands; Node 432/432; Python 1412/1412 with 1 skipped.
- Review: final independent CR found no remaining P0/P1.
- Runtime parity: `news_backend.py`, `postgres_cache_store.py`, `postgres_cache_sync.py`, `websim_payload.py`, repository unit and installed `wow-websim-sync.service` matched the exact candidate by SHA-256.
- Data preflight: live baseline was 5246 talents, 4949 dependency nodes, 8465 dependencies, 49 profiles and 32 profile specs; candidate extraction had 5246 talents, 50 profiles, 40 specs and 80 hero trees with no TraitEdge error.
- Controlled sync: structure and graph digests were unchanged; profiles advanced 49 → 50; `simc.errors=[]`; no blocked lastAttempt.
- Talent canary: `mage/frost/spellslinger` returned 110 nodes, 106 parent-bearing nodes and 186 dependencies with tree/rule/encoding/SimC readiness true. A live Raider.IO community template encoded class, spec and hero lines. Legacy Profile returned encoded talent lines from PostgreSQL authority.
- Gear compatibility canary: Resolve/Profile returned 15/15, `problems=[]`, `embellishmentMax=2`, ordered gems `240892/240983`, enchants `7967/4897` and `arcanoweave_lining`.
- Health: `/health=200`; data health remained truthfully partial only for the existing gear catalog blocker. Backend, gear-stat worker and nginx were active, failed units and new error logs were zero.
- Scheduled state: all five timers were restored enabled/active; associated sync services were inactive and the shared lock was free.
- Frontend: not yet claimed. The exact clean worktree still requires user-run WeChat DevTools verification of connector lines and imported gem/enchant/embellishment UI before merge.
- Harness note: `manifest.json` uses generic `dataHealth` and `deploySmoke` placeholders; release-specific current runtime evidence is recorded in `evidence.json` and this report.

## Rollback

- Backup: `/opt/wow-mini-program/backups/talent-lkg-candidate-30da707-20260713T150936Z`. It was created before the final two candidate corrections and remains intentionally unchanged with its checksum manifest; it is the valid predeploy rollback state, not the final candidate identity.
- The backup contains the predeploy runtime files, installed unit, checksummed dumps for all three affected PostgreSQL tables, WebSim state JSON and predeploy counts.
- Normal rollback: restore the backed-up runtime files and unit, restart `wow-backend.service`, then restore the original timer state.
- Data rollback: use the checksummed table dumps only if the controlled sync data must be restored; the candidate smoke showed unchanged talent graph digests.

## Verdict

CANDIDATE RUNTIME VERIFIED; MERGE PENDING. Production API/data/operations gates passed, but real WeChat UI evidence is still required before PR #84 can be merged.
