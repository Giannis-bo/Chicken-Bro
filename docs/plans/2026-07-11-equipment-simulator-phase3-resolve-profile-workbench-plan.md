# Equipment Simulator Phase 3 Resolve/Profile Workbench Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task by task. Every feature or bug-fix step is TDD-first and every completion claim requires `superpowers:verification-before-completion`.

**Goal:** Activate the canonical PostgreSQL-backed gear Resolver through a structured `/api/websim/gear/resolve` contract, make the new-mode `/api/websim/profile` re-resolve Selection Intent server-side, preserve 409/503 Result Envelopes through the mini-program transport, and cut the gear page over to a pure workbench state whose final legality, Tier/set state, deterministic totals and SimC readiness come only from the server.

**Architecture:** Continue the approved strangler architecture inside the modular monolith. Slice 3A adds one runtime orchestration boundary over the existing Phase 2 store/Resolver/facade and keeps the legacy profile request shape unchanged. Slice 3B adds an opt-in structured-problem transport and a dependency-free pure frontend state module without activating the page. Slice 3C integrates that state into the existing gear detail surface, keeps browse/candidate presentation local, but removes local ownership of final facts. Each Slice has its own Strict packet, PR, local CR, GitHub Harness and candidate gate before merge.

**Tech Stack:** Python 3 standard library and `unittest`; PostgreSQL through the existing `psycopg` connection factory; Node.js `node:test`; WeChat mini-program CommonJS modules; repository-native Project Harness; existing Lighthouse deploy/systemd path.

---

## Approved boundary and current facts

This plan implements the already-approved design in `docs/plans/2026-07-10-equipment-simulator-capability-architecture-design.md`. It does not reopen product design.

Phase 2 establishes these immutable inputs:

- `selection-intent-v1`, `gear-authority-context-v1`, `gear-resolved-snapshot-v1`, `gear-result-envelope-v1` and the required Dependency Vector revisions already exist.
- `gear_resolver.resolve()` and the Evidence Ledger remain pure: no connection, store, route, file or clock argument.
- `PostgresCacheStore.get_gear_authority_context()` is the only selected-gear PostgreSQL boundary; cold reads use exactly three static domain queries in one read-only transaction and warm reads only recheck revision.
- `gear_resolver_runtime_authority()` is the backend policy adapter and `build_websim_profile_response_from_resolved_snapshot()` is the structured serializer facade.
- `compatibility-pg-live-v1` remains transitional and `formalActiveManifest=false`; Phase 3 must not pretend it is the Phase 4 Active Season Manifest.
- Public gear browse remains exactly one active `raiderio_observed_profile` template per spec with no public baseline.
- Phase 6 Catalyst remains disabled and fail-closed.

Phase 3 must not add a migration, write path, sync, backfill, cleanup, queue, Worker, service, timer, Redis, Celery, event bus, rule DSL, DPS comparison, BiS recommendation or formal release registry.

## Chosen approach

Three approaches were considered against the approved design:

1. **One large backend-and-page cutover PR.** This minimizes temporary dormant code but exceeds the review boundary and makes route, transport and UI rollback inseparable.
2. **Recommended: three strangler Slices.** Activate and prove the backend API first, merge a dormant transport/state layer second, then cut over the page in a final candidate. This isolates failure domains and keeps every PR reviewable.
3. **Frontend-only adapter over the legacy `/gear/stats` and `/profile` shapes.** This is smaller but violates the canonical Resolver boundary and would preserve client ownership of final facts.

Use approach 2.

## Contract decisions locked by this plan

### Resolver authoring context

`GET /api/websim/gear?mode=initial|slot` gains an additive `resolverContext` object so the client can author a valid Intent without guessing revisions:

```json
{
  "contractRevision": "gear-resolver-context-v1",
  "formalActiveManifest": false,
  "selectionSchemaRevision": "selection-intent-v1",
  "authoredAgainst": {
    "seasonRevision": "...",
    "gearCatalogRevision": "compatibility-pg:..."
  },
  "dependencyRevisions": {
    "gearRuleRevision": "gear-rule-matrix-v1",
    "resolverContractRevision": "gear-resolver-contract-v1",
    "serializerRevision": "websim-profile-compat-v1",
    "simcRuntimeRevision": "...",
    "statPolicyRevision": "stat-snapshot-policy-v1",
    "selectionSchemaRevision": "selection-intent-v1"
  }
}
```

The value comes from the same revision row and runtime authority used by the loader. It is never assembled from frontend constants. Missing revision authority makes `resolverContext` unavailable/blocked; it must not fall back to `websim-gear-catalog-v1` or stale local storage.

### Resolve request and response

`POST /api/websim/gear/resolve` accepts the Selection Intent as the entire JSON body. It rejects wrappers and client-supplied final facts through the existing parser.

It returns `gear-result-envelope-v1`:

- `200 resolved` with `data` equal to the canonical Resolved Snapshot;
- `200 blocked` for a well-formed but illegal selection;
- `400 blocked` for `INVALID_INTENT`;
- `409 blocked` for `REVISION_CONFLICT`, with current server revisions in `releaseContext`;
- `503 unavailable` for `AUTHORITY_UNAVAILABLE`;
- `500 unavailable` only for a sanitized unclassified internal failure.

The route never runs SimC and never returns DPS or a recommendation.

### Profile compatibility mode

`POST /api/websim/profile` becomes dual-mode during the strangler:

- A body without `selectionIntent` retains the exact legacy 200 response shape and current behavior for old clients.
- A body with exact keys `selectionIntent` and optional `profileContext` enters canonical mode. The server re-loads authority, re-runs the Resolver, and only then calls the existing resolved-snapshot facade. It never accepts a client Resolved Snapshot or serializer input.
- Canonical mode returns a Result Envelope and preserves the same 400/409/503 semantics as `/resolve`. On success, `data` is the current profile response with the server `resolvedGearSignature`, profile readiness and Evidence Ledger.
- `profileContext` accepts exactly `name`, `race`, `scenarioKey`, `heroKey`, `talents`, `talentImport`, `websimExportCode` and `talentState`. `classKey`, `specKey` and `level` come from the resolved eligibility context. Gear facts, preparation authority, enhancement authority, serializer input, evidence, readiness and resolved slots are discarded if supplied there.

### 409 behavior

The workbench preserves item/variant/option choices on a 409. It rebases only `authoredAgainst` from the envelope `releaseContext`, increments `intentVersion`, and performs at most one automatic re-resolve for that user confirmation. A second conflict remains visible and read-only; it cannot loop. No profile or SimC action is enabled until the rebased Intent receives a matching verified snapshot.

### Frontend truth boundary

The frontend may continue to:

- browse candidates, source labels and variant choices;
- format server numbers and problem text for display;
- keep draft choices and local template compatibility fields;
- use local constraints as draft affordances, never as final truth.

The frontend must no longer claim final:

- slot/class/spec/weapon legality;
- Tier identity or item-set piece count;
- deterministic total attributes;
- profile readiness or SimC eligibility.

Those values come only from the current matching Resolved Snapshot. A stale last verified snapshot may be shown as read-only evidence but cannot enable save-as-verified, profile generation, stat execution or SimC handoff for a newer Intent.

---

## Slice 3A — Backend resolver and profile API

**Strict packet:** `artifacts/releases/2026-07-11-equipment-simulator-phase3a-resolve-profile-api`

**Expected production files:**

- Create: `server/gear_runtime.py`
- Modify: `server/pg_gear_authority_loader.py`
- Modify: `server/postgres_cache_store.py`
- Modify: `server/news_backend.py`

**Expected test files:**

- Modify: `tests/pg_gear_authority_loader_test.py`
- Modify: `tests/postgres_cache_store_test.py`
- Create: `tests/gear_runtime_test.py`
- Modify: `tests/news_backend_test.py`

### Task 1: Lock the public authoring context with failing tests

- [ ] Add a loader test proving a single revision row produces exactly the same season/catalog/dependency identity for both the full Authority Context and the public resolver authoring context.
- [ ] Add collision/missing revision tests proving the public context fails closed and retains `formalActiveManifest=false`.
- [ ] Add a store test requiring one `SET TRANSACTION READ ONLY` plus one revision query, one commit on success, rollback on failure and zero writes.
- [ ] Add a runtime gear payload test requiring additive `resolverContext` on both initial and slot responses without changing observed-only/baseline-empty fields.

Run the red tests:

```bash
python3 -m unittest \
  tests.pg_gear_authority_loader_test \
  tests.postgres_cache_store_test.PostgresCacheStoreTest.test_gear_resolver_context_is_one_read_only_revision_query \
  tests.news_backend_test.NewsBackendTest.test_runtime_websim_gear_attaches_backend_resolver_context
```

Expected: FAIL because the public authoring context does not exist.

### Task 2: Implement one shared revision projection

- [ ] Extract a pure revision-row projection in `server/pg_gear_authority_loader.py`; both `load_gear_authority_context()` and the public context path must call it.
- [ ] Add `PostgresCacheStore.get_gear_resolver_context(runtime_authority)` using one caller-owned read-only transaction and the existing static revision SQL.
- [ ] Add bounded validation for every required runtime revision and return no context when any required value is absent.
- [ ] Attach the context in `runtime_websim_gear_payload()` only when the PostgreSQL payload exists and context is complete. Do not fall back to SQLite or fabricate constants.

Run:

```bash
python3 -m unittest tests.pg_gear_authority_loader_test tests.postgres_cache_store_test tests.news_backend_test
```

Expected: PASS, with current public payload regression tests unchanged.

Commit:

```bash
git add server/pg_gear_authority_loader.py server/postgres_cache_store.py server/news_backend.py \
  tests/pg_gear_authority_loader_test.py tests/postgres_cache_store_test.py tests/news_backend_test.py
git commit -m "feat: publish gear resolver authoring context"
```

### Task 3: Define the runtime orchestrator with red tests

Create `tests/gear_runtime_test.py` with fake store/facade boundaries. Cover:

- [ ] malformed Intent -> 400 `INVALID_INTENT` envelope without calling store;
- [ ] legal Intent -> one context load, one pure resolve, 200 `resolved` envelope;
- [ ] illegal Intent -> 200 `blocked` with ordered problems and snapshot data;
- [ ] stale authored revision -> 409 and current `releaseContext`;
- [ ] missing selected authority -> 503, not a client fallback;
- [ ] store exception -> sanitized 503 without DSN, SQL or traceback leakage;
- [ ] unexpected exception -> sanitized 500;
- [ ] canonical profile mode reuses the same resolve function and passes only the server snapshot to the facade;
- [ ] forged `resolvedSnapshot`, `serializerInput`, `resolvedSlots`, `enhancementBySlot` and `evidenceLedger` in profile input never reach the facade;
- [ ] legacy profile mode is explicitly not handled by the new orchestrator.

Run:

```bash
python3 -m unittest tests.gear_runtime_test
```

Expected: FAIL because `server/gear_runtime.py` does not exist.

### Task 4: Implement `server/gear_runtime.py`

The module owns request orchestration only:

```python
resolve_selection_intent(
    raw_intent,
    *,
    store,
    simc_runtime_revision,
    request_id,
) -> tuple[int, dict]

build_profile_from_selection_intent(
    raw_request,
    *,
    store,
    simc_runtime_revision,
    request_id,
    profile_builder,
) -> tuple[int, dict]
```

- [ ] Parse Intent before reading class/spec.
- [ ] Derive runtime authority only from backend helpers and current SimC revision.
- [ ] Call the existing store exactly once and the pure Resolver exactly once.
- [ ] Build `releaseContext` from the returned manifest/dependency vector.
- [ ] Project only the exact `profileContext` allowlist: `name`, `race`, `scenarioKey`, `heroKey`, `talents`, `talentImport`, `websimExportCode`, `talentState`.
- [ ] Map snapshot problems through `result_envelope()` and `http_status_for_envelope()`.
- [ ] Never catch and reinterpret an illegal result as authority failure.
- [ ] Keep error details bounded and secret-free.
- [ ] Keep the module independent of HTTP handler classes and database constructors so tests can use fakes.

Run:

```bash
python3 -m unittest tests.gear_runtime_test tests.gear_contracts_test tests.gear_result_envelope_test tests.gear_resolver_test
```

Expected: PASS.

Commit:

```bash
git add server/gear_runtime.py tests/gear_runtime_test.py
git commit -m "feat: orchestrate canonical gear resolution"
```

### Task 5: Activate routes while preserving legacy profile

Add route-level tests first in `tests/news_backend_test.py`:

- [ ] `POST /api/websim/gear/resolve` returns actual mapped 200/400/409/503 statuses and the exact envelope body.
- [ ] Request IDs are present and stable within one response.
- [ ] PostgreSQL-only mode requires `cache_data_store()` and never opens SQLite.
- [ ] Canonical `/profile` with `selectionIntent` returns the structured envelope.
- [ ] Legacy `/profile` without `selectionIntent` remains byte-shape compatible and returns 200.
- [ ] `/gear/stats`, public gear, health, Catalyst and current task routes remain unchanged.

Run the new tests and confirm red. Then:

- [ ] Import the orchestrator in both package and direct-server modes.
- [ ] Add a small request-id helper using the existing UUID support.
- [ ] Derive current SimC revision as `simcRuntimeRevision -> localTag -> sourceCommit`; missing values produce Authority unavailable, never a made-up revision.
- [ ] Route only PostgreSQL canonical mode through `cache_data_store()`.
- [ ] Call `json_response()` with the orchestrator's HTTP status; do not collapse to 200.
- [ ] Leave the legacy profile branch exactly where it is for bodies without `selectionIntent`.

Run:

```bash
python3 -m unittest tests.gear_runtime_test tests.news_backend_test tests.websim_payload_test tests.postgres_cache_store_test
python3 -m py_compile server/gear_runtime.py server/pg_gear_authority_loader.py server/postgres_cache_store.py server/news_backend.py
```

Commit:

```bash
git add server/news_backend.py tests/news_backend_test.py
git commit -m "feat: expose canonical gear resolve api"
```

### Task 6: Slice 3A local verification and CR

Run:

```bash
python3 -m unittest \
  tests.gear_contracts_test \
  tests.gear_result_envelope_test \
  tests.gear_rule_matrix_test \
  tests.gear_evidence_ledger_test \
  tests.gear_resolver_test \
  tests.pg_gear_authority_loader_test \
  tests.gear_runtime_test
python3 -m unittest tests.websim_payload_test tests.postgres_cache_store_test tests.news_backend_test
node --test tests/project-harness.test.js tests/backend-owner-map.test.js tests/project-owner-map.test.js tests/project-state.test.js
node scripts/verify-project.js --profile backend \
  --release artifacts/releases/2026-07-11-equipment-simulator-phase3a-resolve-profile-api \
  --base origin/main
node scripts/verify-project.js --profile full \
  --release artifacts/releases/2026-07-11-equipment-simulator-phase3a-resolve-profile-api \
  --base origin/main
git diff --check
```

Local CR must confirm:

- Resolver/Ledger remain pure and unchanged in ownership.
- One selected-gear PG boundary remains; public context uses only the revision query.
- Resolve/profile orchestration cannot accept a client snapshot or final facts.
- Legacy profile stays unchanged for old bodies.
- 400/409/503 are not flattened.
- No migration, write, sync, Worker, frontend cutover, Phase 4 Manifest or Catalyst activation exists.

### Task 7: Slice 3A PR and candidate gate

- [ ] Push a dedicated Slice 3A branch and open a non-draft PR only after local CR.
- [ ] Wait for GitHub Project Harness on the exact head.
- [ ] Candidate-deploy with `WOW_DEPLOY_SKIP_BOOTSTRAP=1 WOW_DEPLOY_START_ASYNC_SYNCS=0`.
- [ ] Record exact branch/head/tree and runtime hashes.
- [ ] Build all 40 public observed Intents from live `resolverContext`; require 40/40 `/resolve` HTTP 200 resolved, matching class/spec, no problems and profile readiness truthful.
- [ ] Run canonical `/profile` for a bounded representative armor/weapon matrix and all public winners marked ready; verify it re-resolves and uses server serializer input. Do not run SimC in `/resolve`.
- [ ] Probe malformed 400, stale 409, wrong-slot 200 blocked and missing authority 503.
- [ ] Re-run sequential cold/warm p50/p95/p99 and bounded concurrency bursts 1/5/20. Keep cold p95 <=500ms and warm p95 <=200ms, record query count/cache bytes, and stop if PG/service health degrades.
- [ ] Prove legacy `/profile` response shape, `/gear/stats`, health, Catalyst, 40-spec public initial/slot and task routes remain unchanged.
- [ ] Prove `WOW_DATABASE_RUNTIME=postgres_only`, one-thread idle state after probes, no deploy-triggered sync/backflow, truthful timers/logs and code-only rollback.
- [ ] Merge only after candidate and final-head CI pass; fast-forward main, prove tree parity, redeploy the clean equivalent tree and repeat lightweight API/40-spec/timer/log smoke.
- [ ] Archive Slice 3A and advance current truth to Slice 3B.

---

## Slice 3B — Structured transport and pure workbench state

Create a new Strict packet before editing runtime files.

**Files:**

- Modify: `pages/common/api-client.js`
- Modify: `pages/builds/websim-api.js`
- Create: `pages/builds/gear-workbench-state.js`
- Modify: `tests/frontend-api-client.test.js`
- Create: `tests/gear-workbench-state.test.js`

### Task 8: Preserve structured non-2xx bodies in `requestJson`

Write failing tests first for opt-in `responseMode: 'structured-problem'`:

- [ ] valid 409 and 503 `gear-result-envelope-v1` bodies survive with `fromFallback=false`, original `httpStatus`, empty transport error and no fallback call;
- [ ] 202 pending survives identically for Phase 5 reuse;
- [ ] a 200 blocked envelope survives;
- [ ] malformed non-2xx JSON, network failure and timeout use fallback and set transport/offline error;
- [ ] default response mode preserves every existing caller behavior;
- [ ] auth and analytics headers remain unchanged.

Implement one envelope validator local to `api-client.js`; do not import gear-page code.

Run:

```bash
node --test tests/frontend-api-client.test.js
```

Commit:

```bash
git add pages/common/api-client.js tests/frontend-api-client.test.js
git commit -m "feat: preserve structured api problems"
```

### Task 9: Add canonical websim client functions

Write failing client-wrapper tests, then add:

```javascript
requestWebsimGearResolve(selectionIntent)
requestWebsimProfileFromIntent(selectionIntent, profileContext)
```

- [ ] Both use POST and `responseMode: 'structured-problem'`.
- [ ] Resolve sends the exact Intent as the body with no wrapper.
- [ ] Profile sends only `{ selectionIntent, profileContext }`.
- [ ] Validators require `gear-result-envelope-v1` and keep 409/503 bodies.
- [ ] Existing `requestWebsimProfile()` and `requestWebsimGearStats()` remain compatible.

Run:

```bash
node --test tests/frontend-api-client.test.js
```

Commit:

```bash
git add pages/builds/websim-api.js tests/frontend-api-client.test.js
git commit -m "feat: add canonical gear api clients"
```

### Task 10: Implement the pure workbench state TDD-first

`pages/builds/gear-workbench-state.js` has no `wx`, storage, network, clock or page imports.

Required state:

```javascript
{
  confirmedIntent,
  draftIntent,
  intentVersion,
  latestResolveSerial,
  resolveStatus,
  activeRequest,
  currentSnapshot,
  lastVerifiedSnapshot,
  problems,
  offline,
  readOnly,
  revisionRetryCount,
  statSnapshotSignature,
  statSnapshotStatus
}
```

Required pure operations:

- `createGearWorkbenchState(resolverContext, initialIntent)`;
- `editGearIntent(state, updater)`;
- `confirmGearIntent(state)`;
- `beginGearResolve(state)` returning `{ state, request }` with serial/version/Intent;
- `applyGearResolveResult(state, request, transportResult)`;
- `rebaseGearIntentRevisions(state, releaseContext)`;
- `gearWorkbenchCanUseVerifiedSnapshot(state)`;
- `gearWorkbenchCanRunProfile(state)`;
- `gearWorkbenchView(state)` returning compact display-only fields.

Tests must prove:

- [ ] draft edits do not mutate confirmed Intent or last verified snapshot;
- [ ] confirm increments `intentVersion` exactly once;
- [ ] stale serial or old intent version is ignored without state mutation;
- [ ] verified result becomes current and last verified;
- [ ] 200 blocked keeps problems and does not replace last verified;
- [ ] 409 preserves choices, allows one revision-only rebase/retry and then stops;
- [ ] 503 is structured unavailable/read-only, not network offline;
- [ ] network/invalid response is offline/read-only;
- [ ] dirty, resolving, blocked, stale or unavailable state cannot run profile/SimC;
- [ ] stat snapshot status stays separate from raw Resolver readiness;
- [ ] all operations are deterministic and do not mutate input objects.

Run red, implement, then:

```bash
node --test tests/gear-workbench-state.test.js tests/frontend-api-client.test.js
```

Commit:

```bash
git add pages/builds/gear-workbench-state.js tests/gear-workbench-state.test.js
git commit -m "feat: model canonical gear workbench state"
```

### Task 11: Slice 3B verification, review and merge

Run targeted Node tests, frontend profile, full profile, JSON/Harness and `git diff --check`. Local CR must confirm default API behavior is unchanged and the new state module remains dormant. Merge after exact-head CI. Because Slice 3B has no active page consumer, do not claim mini-program runtime verification; record its highest evidence honestly and advance to Slice 3C.

---

## Slice 3C — Gear page cutover

Create a new Strict runtime packet before editing the page.

**Expected files:**

- Modify: `pages/builds/detail.js`
- Modify: `pages/builds/detail.wxml`
- Modify only if needed for existing-token styling: `pages/builds/detail.wxss`
- Modify: `tests/builds-page.test.js`
- Modify: `tests/frontend-api-client.test.js`

Do not introduce a second frontend state framework or a page redesign.

### Task 12: Characterize and break the frontend final-fact inference

Add failing tests that demonstrate the required boundary:

- [ ] forged client `itemStats`, `statSummary`, `itemSetName`, `simcReady`, readiness and legality cannot change the final attribute panel, set count, save gate or SimC gate;
- [ ] final totals come from `ResolvedSnapshot.staticAttributes`;
- [ ] set display comes from `ResolvedSnapshot.setState`;
- [ ] final legal/readiness state comes from `aggregateLegality`, `profileReadiness` and structured problems;
- [ ] browse candidate labels remain visible but are not final verification;
- [ ] no legacy local helper can mark an unverified current Intent ready.

Keep these tests red until page integration is complete.

### Task 13: Build exact Selection Intent from page choices

- [ ] Add one serializer that accepts `resolverContext`, selected items and selected option IDs and emits only the exact Selection Intent keys.
- [ ] Item rows contribute only `itemId` and `variantKey`; enhancement state contributes only option IDs. Names, stats, SimC options, set fields, source labels and readiness are excluded.
- [ ] Initialize the workbench only after the initial gear payload supplies a complete backend `resolverContext`.
- [ ] Keep the full workbench and Evidence Ledger on `this.gearWorkbenchState`, not in `setData`; expose only `gearWorkbenchView` and bounded problem rows.
- [ ] If context is missing, show structured unavailable/read-only state and do not fabricate revisions.

Run focused page tests after each red-to-green step.

### Task 14: Resolve every confirmed edit with race protection

Route these existing user confirmations through one `confirmAndResolveGearIntent()` path:

- [ ] initial observed template/equipped selection;
- [ ] candidate apply;
- [ ] variant apply;
- [ ] enhancement sheet confirm;
- [ ] community template import;
- [ ] saved template import;
- [ ] reset.

The path must:

1. update draft choices;
2. confirm and increment `intentVersion`;
3. begin resolve and capture serial/version;
4. show a bounded pending state;
5. ignore stale responses;
6. apply server result;
7. perform at most one 409 revision-only rebase/retry;
8. never start profile/stat/SimC work before a matching verified snapshot.

Tests must force responses to complete out of order and prove the newest Intent wins.

Commit the intent/race slice separately.

### Task 15: Replace final panel and gates with server snapshot facts

- [ ] Replace final local stat aggregation with formatting of `staticAttributes`.
- [ ] Replace local Tier/set counting with `setState.itemSetCounts` and server effect evidence.
- [ ] Replace final slot/legal status with `resolvedSlots[].legality`, `aggregateLegality` and problem codes.
- [ ] Replace final readiness and two-hand required-slot inference with `profileReadiness`.
- [ ] Derive socket/enchant/embellishment display from server `constraints`; local sheet rules remain draft affordances only.
- [ ] Keep the legacy stat snapshot panel separate. If `/gear/stats` is still requested before Phase 5, build its gear items from the matching snapshot `serializerInput`, never from client-final facts, and never let its status override Resolver readiness.
- [ ] Save/handoff may preserve legacy `gearBySlot` and `enhancementBySlot` for old-client compatibility, but verified/complete metadata must additionally bind `selectionIntent`, `resolvedGearSignature` and Dependency Vector from the matching server snapshot.
- [ ] `openSimcWithBuildContext()` must remain disabled for dirty/stale/blocked/offline/unavailable state and include canonical Intent/signature when enabled.

Delete or demote unused final-inference helpers only after tests prove no active caller depends on them. Do not remove candidate presentation helpers merely because they share names with final facts.

### Task 16: Render structured problem and read-only states

Use the existing page hierarchy and visual tokens:

- [ ] pending: “正在校验当前装备配置”; final actions disabled;
- [ ] blocked: bounded Chinese problem rows keyed by stable problem code/path;
- [ ] revision conflict: “装备数据已更新，正在重新校验” for the one retry, then explicit read-only conflict if it repeats;
- [ ] authority unavailable: server problem shown, last verified snapshot labeled read-only;
- [ ] network/offline: transport warning shown separately from server 503;
- [ ] verified: resolved signature/readiness drives actions; do not show a false global “verified” if stat snapshot is still pending.

Do not expose raw SQL, DSN, traceback, internal source payload or unbounded Evidence Ledger text in WXML.

### Task 17: Slice 3C local verification and CR

Run:

```bash
node --test tests/gear-workbench-state.test.js tests/frontend-api-client.test.js tests/builds-page.test.js
python3 -m unittest tests.gear_runtime_test tests.news_backend_test tests.websim_payload_test tests.postgres_cache_store_test
node scripts/verify-project.js --profile frontend \
  --release artifacts/releases/2026-07-11-equipment-simulator-phase3c-workbench-cutover \
  --base origin/main
node scripts/verify-project.js --profile full \
  --release artifacts/releases/2026-07-11-equipment-simulator-phase3c-workbench-cutover \
  --base origin/main
git diff --check
```

Local CR must explicitly inspect every caller of:

- `buildGearAttributePanel`;
- local Tier/set helpers;
- local gear template readiness helpers;
- `gearStatsRequestForPage`;
- save/import/reset paths;
- `openSimcWithBuildContext`.

No final fact may remain client-owned.

### Task 18: Real mini-program and candidate cutover gate

- [ ] Confirm current WeChat DevTools health before opening/capturing; preserve login/project state and use the repository's current screenshot/route evidence workflow.
- [ ] Capture the real gear page against the exact candidate backend for: initial verified observed Intent, one confirmed item/variant edit through pending to resolved, and one read-only/problem presentation when safely reproducible without production mutation.
- [ ] Record route/action ledger, screenshot paths, backend branch/head/tree and current payload signatures. Static/browser-only fixtures do not count as mini-program runtime evidence.
- [ ] If a safe real blocked UI case cannot be produced, record that limitation and use direct candidate API evidence for 400/409/503; do not fabricate a screenshot or weaken the server gate.
- [ ] Repeat the 40/40 observed Intent resolve matrix, representative canonical profile matrix, stale/illegal/missing-authority probes, SLO/query/cache checks, legacy profile/stats compatibility, public initial/slot, Catalyst, timer/backflow, logs and rollback.
- [ ] Confirm no stale response overwrote the newest Intent in real interaction evidence.
- [ ] Merge only after exact-head CI and candidate proof. Fast-forward main, prove tree/runtime parity, redeploy clean main, repeat API/mini-program/lightweight 40-spec/timer/log smoke, and archive all three Phase 3 Slices.

---

## Phase 3 completion checklist

- [ ] Public browse supplies backend resolver authoring context without claiming a formal Active Manifest.
- [ ] `/gear/resolve` maps 200/400/409/503 through the exact Result Envelope.
- [ ] Canonical `/profile` re-resolves Intent and ignores client snapshots/final facts.
- [ ] Legacy `/profile` and `/gear/stats` remain compatible.
- [ ] Structured non-2xx bodies survive the opt-in frontend transport.
- [ ] Pure workbench state rejects stale serial/version responses.
- [ ] 409 preserves choices and retries revisions at most once.
- [ ] 503 and offline are distinct; both keep stale evidence read-only.
- [ ] Final legality, Tier/set count, deterministic totals and readiness are server-owned.
- [ ] Save/profile/SimC actions require a matching current verified snapshot.
- [ ] Public templates remain observed-only and baseline-empty 40/40.
- [ ] Resolver query/SLO/cache budgets remain within the approved limits.
- [ ] Real mini-program evidence proves the active cutover.
- [ ] Every runtime Slice has candidate identity, CI, post-merge parity, timer/log and rollback evidence.
- [ ] No migration, write, sync, Worker, formal Phase 4 Manifest or Phase 6 Catalyst activation entered Phase 3.

After Phase 3 is archived, advance current truth to `equipment_simulator_phase4`, write the Phase 4 detailed release-train plan under `superpowers:writing-plans`, and continue the active Phase 0–5 Goal. Phase 3 completion is not Goal completion.
