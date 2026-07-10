# Equipment Simulator Capability Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This Goal uses inline execution; do not dispatch subagents unless the user later explicitly requests it.

**Goal:** Deliver the approved trustworthy equipment workbench architecture through Phase 0–5, including TDD implementation, Harness evidence, candidate deployment, PR merge, live smoke, and current-truth documentation closure, while leaving the deferred 12.1 Catalyst retained-secondary-stat overlay disabled.

**Architecture:** Use a strangler sequence inside the existing modular monolith. First close current production safety gaps, then introduce contracts, a pure canonical resolver, resolve/profile/frontend consumers, immutable gear/community releases, and finally an asynchronous PostgreSQL-backed SimC stat-snapshot worker. Every runtime slice stays backend-owned, PostgreSQL-only, fail-closed, and is candidate-deployed before merge.

**Tech Stack:** Python 3 `unittest`, PostgreSQL runtime stores, `ThreadingHTTPServer`, SimulationCraft JSON output, Node.js `node:test`, WeChat Mini Program JavaScript, systemd, repo-native Harness v0.5, GitHub PRs.

## Global Constraints

- The product is a trustworthy equipment configuration workbench, not a DPS comparison surface, optimizer, or system BiS generator.
- Public community templates come only from current legal real-player observed sources; `recommended_bis`, `season_recommendation`, `default_template`, `simc_preset`, and `baseline_blocked` remain outside the public entry.
- Selection Intent is the only allowed client input model and is always untrusted.
- Manual configuration and community templates must use the same canonical Resolver.
- The frontend never assembles SimC profiles and must stop owning final legality, Tier identity, set counts, aggregate attributes, or SimC readiness.
- Dynamic set effects are not converted into static attributes or DPS.
- Historical Resolved Snapshots are audit-only; every new SimC execution re-resolves the Intent.
- Missing authority fails closed; PostgreSQL-only runtime never falls back to SQLite.
- Deploy with `WOW_DEPLOY_SKIP_BOOTSTRAP=1` and `WOW_DEPLOY_START_ASYNC_SYNCS=0` unless a phase explicitly requires an async job trigger.
- Phase 6 `preserve_base_secondary_stats` remains disabled until its external proof matrix is complete; it is not a completion condition for this Goal.
- Do not add microservices, Redis, Celery, an event bus, event sourcing, a general rule DSL, or a second frontend state framework.
- Runtime PRs must use a current Strict requirement/evidence packet, local CR, the applicable verification profile, candidate deployment, timer/backflow inspection, rollback evidence, merge, live smoke, and current-truth updates.

---

## Current Truth Baseline

- Approved design: `docs/plans/2026-07-10-equipment-simulator-capability-architecture-design.md`.
- Current Harness: `docs/harness.md` v0.5.
- Current state index: `docs/project-state.json`; feature iteration is `allowed_under_harness`.
- Accepted public entry: active `raiderio_observed_profile` only; public baseline default empty.
- Runtime boundary: `WOW_DATABASE_RUNTIME=postgres_only`; SQLite is migration/audit-only.
- Initial local baseline on `main@47d2d31`:
  - `python3 -m unittest tests.websim_payload_test tests.postgres_cache_store_test tests.news_backend_test` -> 713 tests, pass.
  - `node --test tests/builds-page.test.js tests/frontend-api-client.test.js` -> 148 tests, pass.
  - `node --test tests/project-harness.test.js` -> 12 tests, pass.
  - `git diff --check` -> pass.
- The approved design commits `53d0a87` and `47d2d31` were pushed to `origin/main` before implementation planning.
- `.superpowers/` is untracked discussion residue and must not be staged, committed, deleted, or copied into an implementation worktree.

## Delivery Index

| Phase | Deliverable | Runtime slices | Exit evidence |
| --- | --- | --- | --- |
| Phase 0 | Production safety corrections | 0A PG enhancement authority guard; 0B Catalyst false-green guard; 0C legacy stat lightweight/concurrency guard | Three merged candidate-verified PRs; old `/gear/stats` shape preserved; Phase 0 release evidence archived |
| Phase 1 | Contracts and rule authority | Dependency Vector/signatures; Rule Matrix; Result Envelope/Authority Context | Characterization/red tests; contract owners recorded; no resolver/runtime cutover yet |
| Phase 2 | Canonical Resolver | Pure `server/gear_resolver.py`; bounded PG Authority Context loader; facade parity | Resolver/Evidence Ledger verified; zero DB access in Resolver; legacy facade parity |
| Phase 3 | Resolve/Profile/frontend workbench | `/gear/resolve`; `/profile` re-resolve; structured problems; pure workbench state; remove frontend final-fact inference | Real API and mini-program evidence; 409/503 retained; stale response race tests; candidate cutover |
| Phase 4 | Release train/community migration | Immutable release registry; active manifest; candidate/election/standby; shadow compare; scheduled refresh | All public winners legal; absent specs empty; manifest pointer rollback; timer/backflow proof |
| Phase 5 | Asynchronous SimC stat snapshots | PG job/snapshot store; systemd worker; new endpoint; health; frontend cutover | 200/202/503 contract; single-flight/lease/reclaim proof; worker/runtime/40-spec matrix; legacy endpoint retained |
| Phase 6 | Deferred external dependency | No implementation in this Goal | Capability remains disabled and documented without false verified state |

## Phase Plan Lifecycle

- [ ] Complete and merge the current phase before writing the next phase's detailed executable plan.
- [ ] Save each detailed plan under `docs/plans/` and register it in `docs/plans/README.md`.
- [ ] Use exact paths, interfaces, red/green commands, expected failures, candidate smoke, timer/backflow checks, rollback, documentation updates, and commit boundaries.
- [ ] Keep one active Goal for Phase 0–5; do not create a new Goal for a phase or PR slice.
- [ ] Do not mark the Goal complete after planning, Phase 0, local verification, PR creation, or candidate deployment alone.

## Runtime Slice Protocol

Each runtime slice follows this order:

- [ ] Rebase the slice plan on current `main` using read-only status/log checks and `git pull --ff-only` only when safe.
- [ ] Use `superpowers:using-git-worktrees` to create an isolated `codex/` branch/worktree.
- [ ] Create the slice's Strict `requirement.json` and initial `evidence.json` under `artifacts/releases/<date>-<slug>/`.
- [ ] Run `node scripts/project-harness.js --check` and confirm the packet is `implementation_allowed` before implementation.
- [ ] Use `superpowers:test-driven-development`: add one behavior test, run it and record the expected red failure, add the minimum implementation, then run the green target.
- [ ] Run the targeted backend/frontend tests and the verification profile named by the requirement packet.
- [ ] Update the relevant project/backend owner-map characterization, verification matrix, roadmap status, runbook statement, project-state active artifact, and slice evidence.
- [ ] Run local CR against the approved design, phase non-goals, public observed-only contract, PG-only contract, and changed-file scope.
- [ ] Run `git diff --check`, syntax/JSON checks, and `node scripts/project-harness.js --check` again.
- [ ] Commit only the slice files; never add `.superpowers/`.
- [ ] Push the `codex/` branch and open a PR.
- [ ] Candidate-deploy the exact PR commit with async sync startup disabled.
- [ ] Record branch/commit identity, local/remote runtime hashes, `/health`, `/api/data/health`, changed API behavior, public gear initial/slot behavior, systemd/timers, recent logs, and rollback.
- [ ] Confirm existing timer/sync/backfill/cleanup behavior cannot reintroduce the old unsafe state; do not trigger async refresh unless the slice requires it.
- [ ] Merge only after candidate verification passes.
- [ ] Fast-forward local `main`, prove `HEAD == origin/main`, run post-merge live smoke, and archive the evidence packet.
- [ ] Start the next approved slice without requesting routine approval.

## Phase 0 Slice Order

The exact executable plan is `docs/plans/2026-07-10-equipment-simulator-phase0-safety-plan.md`.

1. **0A — PostgreSQL enhancement authority guard**
   - Reject client-only gem/enchant/embellishment evidence whenever no server catalog authority was attached.
   - Preserve SQLite/catalog-backed valid enhancement behavior.
   - Do not add the Phase 2 Authority Context loader.
2. **0B — Catalyst false-green guard**
   - Keep `redirected_base_stats` parse compatibility.
   - Make the 12.1 Catalyst capability and season cutover gate blocked until the complete proof matrix exists.
   - Do not expose conversion UI.
3. **0C — Legacy stat endpoint containment**
   - Keep the legacy 200 response schema.
   - Generate the stat request with the `stat_snapshot_v1` flavor and `iterations=1`.
   - Serialize in-process legacy SimC stat execution with a global concurrency limit of one.
   - Do not add `/gear/stat-snapshots`, job tables, or a Worker.

## Phase 1 Planning Contract

The Phase 1 detailed plan must create focused modules for contracts without activating the new resolver route. It must define exact Python data shapes for:

- `DependencyVector`;
- `selection_signature(intent, eligibility_context)`;
- `resolved_gear_signature(selection_signature, dependency_vector)`;
- `profile_signature(resolved_signature, character_context, talent_hash, serializer_revision, simc_runtime_revision, stat_policy_revision)`;
- `AuthorityContext`;
- ordered Rule Matrix evaluators;
- Result Envelope and structured problem kinds.

Characterization must cover malformed intent, revision conflict, missing authority, illegal selection, and current facade behavior. Phase 1 may introduce contracts and evaluators but must not move the frontend or activate `/resolve`.

## Phase 2 Planning Contract

The Phase 2 detailed plan must define:

- `resolve(selection_intent, authority_context) -> resolved_snapshot` in `server/gear_resolver.py`;
- zero database calls and no connection argument inside the Resolver;
- bounded Authority Context loading in one read-only PostgreSQL transaction and no per-slot query growth;
- Base -> Variant -> Tier/Catalyst Overlay -> Effective Capabilities -> Enhancements ordering;
- cross-slot legality, unique limits, canonical `itemSetId`, deterministic static attributes, profile readiness, constraints, and five typed Evidence Claim groups;
- `server/websim_payload.py` as a compatibility facade with golden payload parity.

## Phase 3 Planning Contract

The Phase 3 detailed plan must define:

- `POST /api/websim/gear/resolve` and `/profile` resolver reuse;
- `requestJson(..., { responseMode: 'structured-problem' })` preserving valid 409/503 envelopes;
- `pages/builds/gear-workbench-state.js` with confirmed/draft Intent, serial, intent version, last verified snapshot, problems, and offline/read-only state;
- stale response rejection and 409 re-resolve behavior;
- removal of frontend final legality, Tier, set-count, total-stat, and SimC-readiness inference;
- real mini-program evidence because the accepted 14-route baseline does not prove this new UI behavior.

## Phase 4 Planning Contract

The Phase 4 detailed plan must define:

- immutable gear/community releases and a release registry;
- one active retail Season Manifest that atomically binds compatible releases;
- candidate, standby, per-spec election, `legacy-import-r0`, preflight-before-write, and shadow compare;
- `observed_provisional` exclusion from public winners;
- degraded release semantics when a spec has no legal winner;
- daily/weekly/revision-triggered refresh and risk-classified promotion;
- pointer rollback and explicit no-silent-legacy-fallback behavior.

## Phase 5 Planning Contract

The Phase 5 detailed plan must define:

- separate PostgreSQL stat snapshot/job migrations and store interfaces;
- `wow-gear-stat-snapshot-worker.service` with lease, heartbeat, expiration reclaim, one child by default, queue/per-client limits, and health;
- `POST /api/websim/gear/stat-snapshots` returning 200 verified, 202 pending, or structured 503;
- server-generated signatures and cross-process single-flight;
- frontend cutover to the new API while the old `/gear/stats` stays compatible;
- 40-spec Resolver/Serializer/minimal executability and `stat_snapshot_v1` JSON evidence, without DPS comparison.

## Final Goal Closure Gate

The Goal can be marked complete only when all conditions below are proven:

- [ ] Phase 0–5 implementation PRs are merged.
- [ ] Every runtime phase has exact candidate-deployment evidence.
- [ ] Local `main`, `origin/main`, and production runtime identity match.
- [ ] Public community entry contains only legal observed winners; a missing spec is empty.
- [ ] Resolver, Rule Matrix, Evidence Ledger, Manifest, structured-problem client, and async snapshot worker have real verification.
- [ ] The 40-spec Resolver/Serializer/minimal SimC executability matrix passes, or each non-ready case has an explicitly allowed blocker from the approved specification.
- [ ] Roadmap, project-state, runbook, owner maps, verification matrix, deferred-work record, and release artifacts reflect actual state.
- [ ] The 12.1 Catalyst retained-secondary-stat overlay remains disabled and is not reported as a current capability.
