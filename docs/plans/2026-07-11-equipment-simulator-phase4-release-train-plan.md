# Equipment Simulator Phase 4 Release Train Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan Slice by Slice. Every production change is TDD-first and every completion claim requires `superpowers:verification-before-completion`.

**Goal:** Replace the mutable live PostgreSQL gear/community read combination with immutable, release-scoped Gear and Community Releases selected by one Active Retail Season Manifest; migrate the current legal observed templates through the canonical Resolver as `legacy-import-r0`; prove old/new parity in shadow; cut over atomically with pointer rollback; and make scheduled refresh write candidates before any risk-classified promotion.

**Architecture:** Keep the modular monolith and existing PostgreSQL-only runtime. Mutable sync tables remain staging inputs. A new pure `gear_release.py` domain owns canonical release IDs, manifest validation, election and shadow-diff policy. A new PostgreSQL release repository owns immutable release rows and the single mutable active pointer. Browse and Authority Context readers become release-scoped only after a valid pointer exists; once cut over, missing or inconsistent release data fails closed and never falls back to staging. Five Strict Slices isolate domain policy, schema/import, shadow reads, atomic cutover and scheduled refresh.

**Tech Stack:** Python 3 standard library and `unittest`; PostgreSQL through existing `psycopg`; SQL migrations under `server/migrations/postgres`; repository-native Harness; existing Lighthouse deploy/systemd path; Node `node:test` for current-truth and contract checks.

---

## Approved boundary and current facts

This plan implements Phase 4 of `docs/plans/2026-07-10-equipment-simulator-capability-architecture-design.md`; it does not reopen the approved product design.

Phase 3 establishes:

- the active gear page emits exact `selection-intent-v1` and treats it as untrusted;
- `/api/websim/gear/resolve` and canonical `/api/websim/profile` re-load PostgreSQL authority and run the pure Resolver;
- final legality, deterministic attributes, set state, constraints and readiness are server-owned;
- save/Profile/SimC actions bind the current resolved signature and Dependency Vector;
- public templates remain one real-player observed winner per spec with public baseline empty;
- `compatibility-pg-live-v1` is explicitly transitional and `formalActiveManifest=false`;
- PostgreSQL staging tables are mutable sync output and are not immutable releases;
- Phase 6 Catalyst remains disabled and fail-closed.

Phase 4 may add migrations, candidate writes, release tooling and scheduled release jobs. It must not add a second database, Redis, Celery, a microservice, an optimizer, DPS comparison, public recommended/baseline templates, frontend profile assembly or Catalyst activation.

## Locked release model

### Mutable staging versus immutable releases

Existing tables such as `cache.websim_items`, `cache.websim_gear_sources`, `cache.websim_gear_variants`, `cache.websim_gear_mod_options` and `cache.websim_community_gear_templates` remain mutable staging inputs populated by existing sync paths.

Public readers must eventually read only release-scoped tables:

```text
mutable staging
  -> deterministic snapshot + preflight
  -> immutable gear/community release rows
  -> immutable season manifest
  -> one mutable retail pointer
  -> release-scoped browse + Resolver authority
```

The release builder never updates or deletes sealed release content. Rebuilding identical content reuses the same hash-derived release ID. A hash collision with different canonical content is a hard integrity failure.

### PostgreSQL schema

Migration `0013_websim_release_train.sql` creates:

- `cache.websim_release_registry`
  - `release_id` primary key;
  - `release_kind` in `gear|community`;
  - `season_revision`, `schema_revision`, `content_hash`;
  - `parent_release_id`, nullable `validated_against_release_id`;
  - `release_status` in `validated|degraded|blocked`;
  - immutable `dependency_vector_json`, `gate_result_json`, `source_json` and timestamps.
- `cache.websim_gear_release_items`
- `cache.websim_gear_release_sources`
- `cache.websim_gear_release_variants`
- `cache.websim_gear_release_mod_options`
  - every primary/unique key includes `release_id`;
  - payloads preserve current canonical fields needed by browse and Authority Context.
- `cache.websim_community_release_templates`
  - `release_id`, class/spec, template ID, `winner|standby|rejected` role;
  - exact `selection_intent_json`, resolved gear signature, provenance/evidence and rejection problems;
  - at most one public winner per release/class/spec.
- `cache.websim_season_manifests`
  - immutable manifest revision, season revision, gear release ID, optional community release ID;
  - rule, serializer, SimC, talent, capability and selection-schema revisions;
  - nullable rollback manifest revision and canonical manifest hash.
- `cache.websim_active_manifest_pointer`
  - exactly one `retail` row with manifest revision, monotonic generation and update metadata.
- `cache.websim_release_events`
  - append-only build, validation, shadow, promotion, rollback and rejection facts.

Release content tables grant the runtime role `SELECT, INSERT` only. The pointer grants the minimal update required for compare-and-swap promotion. No Phase 4 cleanup job deletes historical releases.

### Formal Active Season Manifest

The public manifest contract is:

```json
{
  "schemaRevision": "active-season-manifest-v1",
  "manifestRevision": "season-manifest:sha256:...",
  "seasonRevision": "...",
  "gearCatalogReleaseId": "gear-release:sha256:...",
  "communityTemplateReleaseId": "community-release:sha256:...",
  "talentCatalogRevision": "...",
  "dependencyRevisions": {
    "gearRuleRevision": "...",
    "resolverContractRevision": "...",
    "serializerRevision": "...",
    "simcRuntimeRevision": "...",
    "statPolicyRevision": "...",
    "selectionSchemaRevision": "selection-intent-v1",
    "capabilityRevision": "..."
  },
  "rollbackManifestRevision": "..."
}
```

`gearCatalogRevision` in Resolver authoring context becomes the exact Gear Release ID. `formalActiveManifest=true` is allowed only when the manifest, referenced release registry rows, release bindings and content integrity all pass. A request reads the pointer/manifest once in its read-only transaction and constrains all later rows by release ID.

### Community election and `legacy-import-r0`

Every candidate template is converted to exact Selection Intent and run through the current Resolver against one Gear Release. Election eligibility requires:

- active retail season match;
- allowed real-player observed source and non-empty provenance URL/hash/sample evidence;
- non-expired evidence;
- full canonical slot coverage after handedness rules;
- `aggregateLegality=legal` and matching resolved signature;
- exact `validatedAgainstGearReleaseId` binding;
- no client-owned final facts.

Per spec, deterministic ordering selects one winner and retains legal lower-ranked candidates as internal standby. Illegal, stale, source-invalid or binding-mismatched rows are rejected, never public partial templates.

The first Community Release source revision is `legacy-import-r0`. It reads the current active observed-only rows, re-authors exact Intents, re-runs the Resolver against the candidate Gear Release, and stores only newly proven winners/standbys. The word “legacy” describes provenance, not trust: no row is grandfathered.

### Shadow compare and promotion

Shadow compare covers all 40 specs and records:

- public winner presence/count;
- exact selected item/variant/option Intent;
- resolved gear signature and legality;
- source key, source URL, profile/gear hash and sample evidence;
- public baseline count (must remain zero);
- gear browse item/variant/option identity;
- Resolver/Profile outcomes and Dependency Vector.

Expected revision-label changes are normalized separately. Any illegal winner, release-binding mismatch, public non-observed source, baseline leak, integrity failure or cross-reader mixed release blocks promotion.

Promotion inserts an immutable manifest and compare-and-swaps the retail pointer in one transaction. Rollback compare-and-swaps the pointer to `rollbackManifestRevision`; it never rewrites release content.

### Scheduled refresh policy

- Existing external sync jobs continue to write staging only.
- The Phase 4 release refresh consumes staging after sync and always creates/validates an inactive candidate first.
- Same-Gear-Release community changes may auto-promote only after full election and shadow gates.
- If a new candidate loses a still-legal active winner, promotion is blocked and the active winner remains.
- If an active winner becomes illegal or expired, the new release may publish that spec empty and report degraded; it must not substitute a baseline.
- Low-risk additive Gear changes may auto-promote only after 40-spec Resolver/Profile/browse regression and compatible Community Release validation.
- New season, rule, serializer, schema, capability or high-risk gear changes remain controlled cutovers.
- Deployment keeps `WOW_DEPLOY_START_ASYNC_SYNCS=0`; deploy never becomes a release refresh trigger.

---

## Slice 4A — Pure release contracts

Create Strict packet `artifacts/releases/2026-07-11-equipment-simulator-phase4a-release-contracts` before production edits.

**Expected files:**

- Create: `server/gear_release.py`
- Create: `tests/gear_release_test.py`
- Modify: `docs/gear-simulation-full-chain-runbook.md`
- Modify: owner maps only for the new domain boundary

### Task 1: Red contract tests

Add failing tests for:

- canonical hash-derived Gear/Community Release IDs;
- field allowlists and deterministic ordering;
- manifest validation and exact release binding;
- one winner per spec plus internal standby/rejected rows;
- illegal/stale/source-invalid candidate rejection;
- carry-forward only after current Resolver revalidation;
- shadow diff classifications and promotion blockers;
- immutable pointer promotion/rollback command objects;
- public observed-only and baseline-empty invariants;
- Catalyst capability cannot become verified from parser allowlist.

### Task 2: Implement pure domain

`gear_release.py` must be pure: no SQL, connection, store, HTTP, filesystem, environment, clock or subprocess argument. Time and current dependency revisions are explicit inputs. It owns:

- release/manifest canonicalization and signatures;
- candidate election policy;
- release integrity validation;
- shadow comparison;
- risk classification and promotion decision.

It calls the existing pure Resolver through an injected callable; it does not duplicate legality rules.

### Task 3: Verify and merge dormant domain

Run focused tests, backend/full profiles, local CR and exact-head CI. Candidate deployment must prove runtime parity even though the module is dormant; highest evidence is candidate/local/CI, not active release behavior.

---

## Slice 4B — Immutable PostgreSQL registry and legacy import

Open a new Strict packet after 4A is archived.

**Expected files:**

- Create: `server/migrations/postgres/0013_websim_release_train.sql`
- Create: `server/gear_release_store.py`
- Create: `server/gear_release_tool.py`
- Create: `tests/gear_release_store_test.py`
- Modify: `tests/postgres_schema_test.py`
- Modify: `tests/postgres_cache_store_test.py` only for adapter characterization

### Task 4: Red schema and repository tests

Prove:

- all release content keys are release-scoped;
- one partial unique winner constraint per release/class/spec;
- registry/content rows are append-only and hash checked;
- manifest FK/binding constraints reject mixed Gear/Community releases;
- pointer compare-and-swap rejects stale generation;
- failed build/preflight leaves active pointer unchanged;
- repeated identical import is idempotent;
- differing content under one release ID fails closed;
- reader role permissions do not allow release content update/delete.

### Task 5: Implement repository and tooling

`gear_release_store.py` is the sole SQL owner for release tables and pointer mutation. `gear_release_tool.py` provides explicit commands:

```text
build-legacy-gear
build-legacy-community --gear-release ID
validate --release ID
show --release ID
shadow --manifest FILE_OR_ID
promote --manifest ID --expected-generation N
rollback --expected-generation N
```

The first two builders snapshot current staging in one repeatable-read/read-only source transaction, canonicalize outside SQL, then insert immutable content in one write transaction. They do not mutate staging, public readers or the active pointer.

### Task 6: Candidate migration and import gate

Candidate deploy must:

- back up code and PostgreSQL schema/data needed for migration recovery;
- apply migration 0013;
- prove existing runtime remains on transitional readers;
- build Gear `legacy-import-r0` and Community `legacy-import-r0` inactive releases;
- re-resolve 40/40 public observed Intents;
- record winner/standby/rejected counts, query plans, content hashes and zero active-pointer change;
- prove legacy/public/Profile/stats/Catalyst/timers/logs unchanged.

Rollback for this Slice is code rollback plus leaving unused additive tables in place; destructive migration rollback requires explicit approval and is not the normal path.

---

## Slice 4C — Release-scoped shadow readers

Open a new Strict runtime packet after 4B import evidence is archived.

**Expected files:**

- Modify: `server/pg_gear_authority_loader.py`
- Modify: `server/postgres_cache_store.py`
- Modify: `server/pg_gear_read_model_selectors.py`
- Modify: `server/gear_runtime.py`
- Modify: focused loader/store/runtime tests

### Task 7: Characterize old reader and add red shadow tests

Tests must show a candidate manifest can be read without changing public output, while proving:

- one pointer/manifest lookup per request transaction;
- every release query contains the same Gear Release ID;
- Community Release rows are bound to that Gear Release;
- missing referenced rows, content hash mismatch or mixed IDs return Authority unavailable;
- once a formal pointer is selected, no staging fallback is reachable;
- transitional behavior remains unchanged when no active pointer exists before cutover.

### Task 8: Implement release-scoped projections

Add explicit release-reader methods rather than conditionally editing staging SQL fragments in many places. Candidate shadow calls both readers and returns a bounded internal diff; public routes continue using transitional reads during this Slice.

Authority cache keys include manifest revision and Gear Release ID. A pointer change naturally invalidates incompatible cache entries; no global mutable cache flush is required for correctness.

### Task 9: Candidate 40-spec shadow gate

At exact candidate head:

- run old/new initial and representative slot browse for 40 specs;
- run candidate Release Intents through Resolve and canonical Profile;
- compare public winner, signature, legality and provenance;
- prove baseline=0 and observed-only;
- measure cold/warm query count, p95 and cache size;
- inject missing/mixed release failures;
- keep active pointer absent/unchanged;
- record timer/backflow/log/rollback evidence.

Merge only with no blocking shadow diff.

---

## Slice 4D — Atomic Active Manifest cutover

Open a new Strict runtime packet after the shadow reader is merged and live.

**Expected files:**

- Modify: `server/postgres_cache_store.py`
- Modify: `server/pg_gear_authority_loader.py`
- Modify: `server/news_backend.py`
- Modify: health/admin projection files/tests as required
- Modify: `docs/gear-simulation-full-chain-runbook.md`

### Task 10: Red cutover and fail-closed tests

Prove:

- manifest insert and retail pointer compare-and-swap are atomic;
- `formalActiveManifest=true` only for a valid active pointer;
- Resolver context publishes exact Gear Release ID;
- old Intent receives one 409 revision rebase and then resolves;
- browse, Resolve and Profile in one request cannot mix release IDs;
- invalid/missing manifest produces 503, never staging fallback;
- rollback pointer restores the prior complete combination;
- health/admin report active, rollback and candidate facts without false green.

### Task 11: Exact candidate cutover rehearsal

On candidate deployment:

1. create/reuse validated imported Gear and Community Releases;
2. create an inactive manifest with explicit rollback target;
3. run full shadow and negative matrices;
4. compare-and-swap the pointer;
5. run real WeChat pending→409 rebase→verified path if the client still holds the transitional revision;
6. prove 40/40 browse/Resolve and truthful Profile outcomes;
7. exercise pointer rollback and re-promotion once;
8. record identities, generations, hashes, database rows, service state and logs.

If any cutover check fails, roll the pointer back before code rollback. Never repair public state by editing release rows.

### Task 12: Merge and clean-main live cutover

After exact-head CI, merge and deploy clean main with async sync disabled. Rebuild/reuse identical releases, repeat the pointer cutover, then repeat lightweight 40-spec, negative, legacy, real mini-program, timer/log and runtime parity smoke. Archive the transitional compatibility manifest label; do not delete staging readers or tables yet.

---

## Slice 4E — Scheduled candidate refresh and risk-classified promotion

Open the final Phase 4 Strict packet after active Manifest cutover is stable.

**Expected files:**

- Create: `server/gear_release_refresh.py`
- Create: `server/wow-gear-release-refresh.service`
- Create: `server/wow-gear-release-refresh.timer`
- Create: `tests/gear_release_refresh_test.py`
- Modify: deploy unit installation and health/admin projections
- Modify: runbook, owner maps, verification matrix and roadmap evidence

### Task 13: Red refresh policy tests

Cover:

- sync output always becomes inactive candidate first;
- same-gear Community candidate full pass can auto-promote;
- coverage regression with still-legal active winner blocks promotion;
- newly illegal/expired active winner is removed without baseline fallback;
- additive Gear change requires full 40-spec compatibility;
- season/rule/serializer/schema/capability/high-risk change remains manual;
- lease/single-run behavior prevents overlapping release builds;
- failure preserves active pointer and records bounded blocker/event;
- deploy never starts the refresh service;
- Catalyst remains disabled.

### Task 14: Implement bounded job and operations surfaces

The timer consumes existing staging only and performs no external download. Use the existing systemd/runtime lock conventions. Health/admin expose:

- active manifest/release IDs and pointer generation;
- last candidate and gate status;
- winner/standby/rejected/empty spec counts;
- last shadow diff and promotion reason;
- rollback target;
- next/last timer state;
- explicit degraded/blocked problems.

Do not expose raw SQL, DSN, traceback or unbounded evidence.

### Task 15: Final Phase 4 candidate, merge and live gate

Prove:

- manual candidate build and safe auto-promotion decision fixtures;
- timer/service installed but not deploy-triggered;
- one controlled timer run creates the expected candidate/event;
- public 40/40 or explicit degraded empty-spec truth with zero illegal winners;
- canonical Profile/legacy stats compatibility;
- query/SLO/cache budgets;
- active/rollback pointer integrity;
- PG-only, health/admin, logs and exact runtime hashes.

After merge, run one clean-main controlled refresh and post-merge smoke, archive all Phase 4 Slices, advance current truth to Phase 5, and write the detailed async SimC snapshot plan. Phase 4 completion is not Goal completion.

---

## Verification commands by Slice

Use focused tests first, then the relevant profile:

```bash
python3 -m unittest tests.gear_release_test
python3 -m unittest tests.gear_release_store_test tests.postgres_schema_test tests.postgres_cache_store_test
python3 -m unittest tests.pg_gear_authority_loader_test tests.gear_runtime_test tests.news_backend_test
python3 -m unittest tests.gear_release_refresh_test
node --test tests/project-state.test.js tests/project-owner-map.test.js tests/backend-owner-map.test.js
node scripts/verify-project.js --profile backend --release <slice-release> --base origin/main
node scripts/verify-project.js --profile full --release <slice-release> --base origin/main
node scripts/project-harness.js --check --requirement-file <slice-release>/requirement.json --evidence-file <slice-release>/evidence.json --base origin/main
git diff --check
```

Local CR before every commit/push/deploy must inspect:

- immutable-content SQL and permissions;
- release ID/content hash recomputation;
- every public/staging fallback branch;
- all active-pointer writes and compare-and-swap predicates;
- Gear/Community binding in every query;
- public template source filters;
- Resolver and Profile dependency-vector ownership;
- timer/deploy separation;
- rollback path and evidence truth.

## Phase 4 completion checklist

- [ ] Pure release/election/shadow policy has complete focused coverage.
- [ ] Gear and Community releases are immutable and hash-addressed.
- [ ] The Active Retail Season Manifest atomically binds Gear and Community Releases.
- [ ] Public browse and Resolver authority are scoped to one manifest/release combination.
- [ ] `legacy-import-r0` revalidates current data; it does not grandfather it.
- [ ] Shadow compare covers all 40 specs and blocks illegal/mixed release output.
- [ ] Public templates remain real-player observed-only and baseline-empty.
- [ ] Promotion and rollback only move the pointer.
- [ ] Scheduled refresh writes candidates first and follows risk classification.
- [ ] No deploy-triggered sync/release refresh exists.
- [ ] Health/admin expose honest active/candidate/degraded/blocked state.
- [ ] Legacy Profile and `/gear/stats` remain compatible for Phase 5 migration.
- [ ] Query, latency, cache, process, timer, log and rollback gates pass.
- [ ] Catalyst retained-secondary-stat remains disabled and fail-closed.
- [ ] Every runtime Slice has candidate identity, exact-head CI, post-merge parity and archived evidence.

## Explicit non-goals

- No DPS comparison, optimizer or system BiS.
- No public `season_recommendation`, `recommended_bis`, default or SimC preset template.
- No frontend SimC profile assembly.
- No immediate deletion of staging/legacy tables or endpoints.
- No Redis, Celery, event bus, microservice or generic rules DSL.
- No Phase 5 SimC queue/Worker implementation.
- No Phase 6 Catalyst UI or retained-secondary-stat activation.
