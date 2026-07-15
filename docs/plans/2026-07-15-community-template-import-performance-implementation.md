# Community Template Atomic Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the slow community-template `initial + N × mode=slot` hydration fan-out with one backend-resolved import request that preserves observed-only provenance, canonical enhancement editability, Resolver authority, and stale-response fencing.

**Architecture:** A pure projector reconstructs a canonical Selection Intent only from one sealed observed winner plus release-scoped authoritative variants/options. A new scoped Release read binds that source and the Resolver authority context to the same Active Manifest. The runtime returns a compact import envelope, a separate bounded cache stores only verified immutable snapshots, and the mini-program adopts that verified snapshot atomically; normal slot editing remains lazy through the existing `mode=slot` route.

**Tech Stack:** Python 3 `unittest`; Node `node:test`; WeChat mini-program JavaScript/WXML; PostgreSQL immutable Gear/Community Releases plus Active Manifest; existing Resolver and Project Harness; existing candidate deployment scripts and systemd services.

## Global Constraints

- Keep the public entry limited to active `raiderio_observed_profile` winners; baseline, `season_recommendation`, and recommended-BiS records remain unavailable to this route.
- The request body is exactly `classKey`, `specKey`, `templateId`, and optional `expectedManifestRevision`; the client never submits selected items, raw enhancement values, option IDs, or constraints as authority.
- Bind the template, Gear Release, Community Release, pointer generation, and Resolver authority to one formal Active Manifest. Missing, mixed, stale, or invalid binding fails closed.
- Preserve `mode=initial` and `mode=slot` behavior. The new route is import-only; a later explicit slot edit may load only that selected slot.
- Do not add migrations, release/pointer writes, sync/backfill/cleanup work, deploy-triggered async execution, runtime external fetches, or SQLite fallback.
- Keep raw unknown enhancement strings out of the response, Intent, WXML, Profile, SimC, analytics, logs, and `Server-Timing`; expose only bounded type/count warnings.
- Cache only verified immutable import snapshots. The key binds manifest revision, pointer generation, class, spec, template ID, and `websim-community-template-import-v1`; it is separate from the 80-entry generic gear-payload LRU.
- Every production task is test-first. Run the stated failing test before its implementation, then rerun it green. Commit each independently reviewable task.
- Before merge, run backend, frontend, and full Harness profiles, deploy the exact PR head as a candidate with `WOW_DEPLOY_START_ASYNC_SYNCS=0`, collect cold/warm timings and a real WeChat import-plus-slot-edit proof, then record evidence and rollback.

**Approved design:** [Community Template Import Performance Design](../superpowers/specs/2026-07-15-community-template-import-performance-design.md)

**Harness packet:** [requirement](../../artifacts/releases/2026-07-15-community-template-import-performance/requirement.json) · [evidence target](../../artifacts/releases/2026-07-15-community-template-import-performance/evidence.json)

**Execution branch:** `codex/community-template-import-performance-design` at `b53794d`; create a dedicated execution worktree/branch from this commit before production code changes.

---

### Task 1: Establish the pure community-import projector and its ownership boundary

**Files:**

- Create: `server/community_template_import.py`
- Create: `tests/community_template_import_test.py`
- Modify: `docs/project-owner-map.json`
- Modify: `docs/backend-owner-map.json`
- Modify: `tests/project-owner-map.test.js`
- Modify: `tests/backend-owner-map.test.js`

**Interfaces:**

- Consumes: an immutable winner row (`templateId`, `classKey`, `specKey`, `sourceKey`, `selectionIntent`), selected immutable variants, and immutable option rows from Task 2.
- Produces: `build_community_template_import_source`, `build_community_template_selection_intent`, `community_template_import_problem`, and `community_template_import_public_data`.
- Does not consume: database connections, HTTP handlers, clocks, environment variables, pointer commands, or frontend payloads.

- [ ] **Step 1: Write failing projector tests**

Create `tests/community_template_import_test.py` with these isolated cases:

- `test_observed_winner_projects_only_bound_variants_and_visible_options`: exact winner yields only its selected variant IDs and visible option keys.
- `test_non_observed_or_non_winner_source_is_blocked_before_intent_creation`: a baseline or standby row returns `template_not_active`.
- `test_duplicate_gem_option_ids_preserve_source_order`: `['gem-a', 'gem-a']` remains exactly that sequence.
- `test_unknown_raw_enhancement_values_become_counts_not_output_values`: output contains `{gemCount: 1}` and excludes the source value.
- `test_forged_template_option_identity_is_not_copied_to_selection_intent`: forged values do not occur in the built Intent.
- `test_slot_inapplicable_or_hidden_option_is_reported_as_unresolved`: the chosen slot has a bounded unresolved count.
- `test_projector_has_no_database_or_http_side_effects`: immutable input snapshots are byte-for-byte unchanged after projection.

Use a Frost Mage fixture with two identical gem occurrences and a forged option ID in the stored payload. Assert the output Intent retains only the verified option keys and the public result has `unresolvedBySlot[slot]` counts, never the forged or raw string.

- [ ] **Step 2: Prove RED**

Run:

```bash
python3 -m unittest tests.community_template_import_test
```

Expected: import failure because `server.community_template_import` does not yet exist.

- [ ] **Step 3: Implement the smallest pure owner**

Export these stable values and callable signatures:

```python
COMMUNITY_TEMPLATE_IMPORT_CONTRACT_REVISION = "websim-community-template-import-v1"
PUBLIC_OBSERVED_SOURCE_KEY = "raiderio_observed_profile"

build_community_template_import_source(winner, variants, options)
build_community_template_selection_intent(source)
community_template_import_public_data(source, resolved_snapshot, release_context)
community_template_import_problem(code, title, *, retryable=False)
```

`build_community_template_import_source` must require exactly one `role == "winner"` and `sourceKey == "raiderio_observed_profile"`; require the row class/spec to match the request; select variants by the stored canonical `itemId` and `variantKey`; and accept an option only when its `optionKey` is non-empty, `status == "verified"`, `isVisible is True`, and `applicableSlots` contains the exact slot or `*`. Reconstruct a new Intent from those verified identities rather than copying `payload`, `simcOptions`, or raw source fields. Preserve duplicate gems in list order. Convert rejected gem/enchant/embellishment source facts into integer counts per slot.

`community_template_import_public_data` must expose only `template`, `manifest`, `selectedGearBySlot`, `resolvedSnapshot`, `unresolvedBySlot`, and `warnings`. Build selected display rows from immutable item/variant facts and selected option labels from the Resolver snapshot; do not include `selectionIntent`, raw option values, SQL records, or release-internal rows.

- [ ] **Step 4: Add the owner-map characterization**

Add `server/community_template_import.py` to the existing canonical gear/Release read-model domains rather than creating a second product domain. State that it is the pure template-to-canonical-selection projector, while `server/gear_release_store.py` remains the immutable read owner and `server/gear_runtime.py` plus `server/gear_resolver.py` remain final legality/resolution owners. Add `tests/community_template_import_test.py` to the matching characterization arrays and add a map test that rejects an unowned projector path.

- [ ] **Step 5: Prove GREEN and commit**

```bash
python3 -m unittest tests.community_template_import_test
node --test tests/project-owner-map.test.js tests/backend-owner-map.test.js
git add server/community_template_import.py tests/community_template_import_test.py docs/project-owner-map.json docs/backend-owner-map.json tests/project-owner-map.test.js tests/backend-owner-map.test.js
git commit -m "feat: add pure community template import projector"
```

### Task 2: Add one Active-Manifest-bound scoped import read

**Files:**

- Modify: `server/gear_release_store.py`
- Modify: `tests/gear_release_store_test.py`

**Interfaces:**

- Consumes: `binding`, `class_key`, `spec_key`, and `template_id`.
- Produces: `GearReleaseStore.load_active_community_template_import(binding, class_key, spec_key, template_id) -> dict` with the exact winner, selected variants/items/sources/options, and the already-validated binding identity.
- Rejects: non-formal bindings, mixed release IDs, non-winners, non-observed sources, row-hash mismatches, missing selected variant/item/source rows, and more than one selected winner.

- [ ] **Step 1: Write scoped-read RED tests**

Add these methods to `tests/gear_release_store_test.py`:

- `test_active_community_import_reads_one_bound_observed_winner_and_selected_rows`
- `test_active_community_import_rejects_template_id_not_owned_by_requested_spec`
- `test_active_community_import_rejects_non_observed_or_non_winner_row`
- `test_active_community_import_rejects_mixed_manifest_release_or_row_hash`
- `test_active_community_import_never_queries_broad_slot_catalog`

Use the existing fake cursor recorder. Assert the Community query contains `release_id`, `class_key`, `spec_key`, `template_id`, `role = 'winner'`, and `source_key = 'raiderio_observed_profile'`; assert the selected Gear queries bind only the item IDs and variant IDs named by the sealed winner Intent. Assert no query fetches all variants/options for a class/spec.

- [ ] **Step 2: Prove RED**

```bash
python3 -m unittest tests.gear_release_store_test.GearReleaseStoreTest.test_active_community_import_reads_one_bound_observed_winner_and_selected_rows
```

Expected: failure because the scoped reader is absent.

- [ ] **Step 3: Implement the repeatable-read scoped reader**

Add this method adjacent to `load_active_public_gear`:

```python
def load_active_community_template_import(
    self, binding: dict[str, Any], class_key: str, spec_key: str, template_id: str
) -> dict[str, Any]:
    """Read one observed winner and only its import authority from one active binding."""
```

Start with the same formal-binding and Gear/Community-release identity checks as `load_active_public_gear`. In one `REPEATABLE READ, READ ONLY` transaction, load exactly one winner row, verify its `row_hash`, derive the selected `(itemId, variantKey)` pairs from its sealed `selection_intent_json`, then load and hash-check only the matching variant, item, source, and option rows. Reject a selected item/variant mismatch rather than filling it from a broad catalog. Return canonicalized records under `winner`, `variants`, `items`, `sources`, `options`, `binding`; do not call `load_active_public_gear` and do not materialize `replacementCandidates`, `slotGroups`, or a whole catalog.

- [ ] **Step 4: Prove GREEN and commit**

```bash
python3 -m unittest tests.gear_release_store_test
git add server/gear_release_store.py tests/gear_release_store_test.py
git commit -m "feat: add scoped community import release reader"
```

### Task 3: Bind the projector and Resolver through one cached import runtime path

**Files:**

- Modify: `server/postgres_cache_store.py`
- Modify: `server/gear_runtime.py`
- Modify: `tests/postgres_cache_store_test.py`
- Modify: `tests/gear_runtime_test.py`
- Modify: `tests/community_template_import_test.py`

**Interfaces:**

- Consumes: request fields `{classKey, specKey, templateId, expectedManifestRevision?}`, current SimC runtime revision, and `PostgresCacheStore`.
- Produces: `import_community_template` returning `(http_status, envelope, timings)`, where `timings` has only `{queueMs, releaseReadMs, reconcileMs, resolveMs, serializeMs, cache}`.
- Produces: `PostgresCacheStore.get_community_template_import_context`, which loads one manifest binding once, derives runtime authority, uses Task 2’s source, and supplies the corresponding Resolver context.

- [ ] **Step 1: Write cache/runtime RED tests**

Add these tests:

- `test_import_runtime_uses_one_binding_for_source_and_resolver_context`
- `test_verified_import_is_cached_by_manifest_generation_and_template_identity`
- `test_pointer_generation_or_manifest_revision_invalidates_import_cache`
- `test_blocked_unavailable_and_malformed_imports_are_not_cached`
- `test_expected_manifest_mismatch_returns_structured_blocked_problem`
- `test_import_runtime_preserves_duplicate_gems_and_resolver_signature`
- `test_import_runtime_returns_only_bounded_timing_fields`

The cache test must make two equal calls and assert one scoped read, then change only `pointerGeneration` and assert a miss. The mismatch test must assert a structured `manifest_mismatch` problem and no legacy `mode=slot` fallback data.

- [ ] **Step 2: Prove RED**

```bash
python3 -m unittest tests.postgres_cache_store_test tests.gear_runtime_test tests.community_template_import_test
```

Expected: new import context and runtime functions are unavailable.

- [ ] **Step 3: Add a separate immutable import cache and same-binding context**

In `server/postgres_cache_store.py`, add separate module-level storage rather than changing `PG_GEAR_PAYLOAD_CACHE`:

Add `PG_COMMUNITY_TEMPLATE_IMPORT_CACHE = {}`, `PG_COMMUNITY_TEMPLATE_IMPORT_CACHE_MAX = 64`, `_pg_community_template_import_cache_get(fingerprint)`, and `_pg_community_template_import_cache_put(fingerprint, payload)`.

Use the established pop-and-reinsert LRU behavior and deep copies. Build the fingerprint from `manifestRevision`, `pointerGeneration`, `classKey`, `specKey`, `templateId`, and `COMMUNITY_TEMPLATE_IMPORT_CONTRACT_REVISION`. Never insert non-`verified` data, exception output, malformed data, or a result with unresolved coverage that the runtime classifies as blocked.

Add `get_community_template_import_context`. It must call `_active_manifest_binding_for_authority()` exactly once, reject a non-formal binding, enforce `expectedManifestRevision` before expensive reads, call Task 2’s reader, build the pure import source, and call `load_active_authority_context` with that same binding. Return the source, authority context, release context, cache identity, and millisecond read timing.

In `server/gear_runtime.py`, add `import_community_template(raw_request, *, store, simc_runtime_revision, request_id, clock=time.perf_counter)`, returning `(http_status, envelope, timings)`.

Validate the exact allowed request keys and playable class/spec before calling the store. Resolve only the projector’s newly built canonical Intent with `gear_resolver.resolve`; format the public data through Task 1. Return structured `template_not_active`, `template_inapplicable`, `manifest_mismatch`, `template_import_blocked`, or `template_import_unresolved` problems as appropriate. Do not call `_resolve_selection_intent`, because it would re-read authority through a second binding.

The HTTP payload returned from this function has one stable outer shape:

```python
{
    "contractRevision": "community-template-import-envelope-v1",
    "status": "verified",  # or partial, blocked, unavailable
    "requestId": request_id,
    "releaseContext": release_context,
    "problems": [],
    "data": {
        "contractRevision": COMMUNITY_TEMPLATE_IMPORT_CONTRACT_REVISION,
        "status": "verified",
        "template": {}, "manifest": {}, "selectedGearBySlot": {},
        "resolvedSnapshot": {}, "unresolvedBySlot": {}, "warnings": [],
    },
}
```

`data` is present for verified and partial responses; blocked/unavailable responses use the same outer envelope with an empty data object and structured `problems`.

- [ ] **Step 4: Prove GREEN and commit**

```bash
python3 -m unittest tests.postgres_cache_store_test tests.gear_runtime_test tests.community_template_import_test
git add server/postgres_cache_store.py server/gear_runtime.py tests/postgres_cache_store_test.py tests/gear_runtime_test.py tests/community_template_import_test.py
git commit -m "feat: resolve cached community template imports"
```

### Task 4: Expose the import endpoint and bounded timing headers

**Files:**

- Modify: `server/news_backend.py`
- Modify: `tests/news_backend_test.py`

**Interfaces:**

- Consumes: `POST /api/websim/gear/community-import` with the Task 3 request body.
- Produces: a structured `community-template-import-envelope-v1` response with verified/partial/blocked status and optional `Server-Timing` values.
- Preserves: existing `/api/websim/gear`, `/api/websim/gear/resolve`, `/api/websim/profile`, and gzip/CORS behavior.

- [ ] **Step 1: Write route and header RED tests**

Add these `NewsBackendTest` methods:

- `test_community_import_route_passes_only_allowed_fields_to_runtime`
- `test_community_import_route_returns_runtime_problem_without_legacy_slot_fallback`
- `test_community_import_route_emits_numeric_server_timing_without_template_content`
- `test_json_response_keeps_existing_gzip_and_cors_headers_when_extra_headers_are_supplied`
- `test_community_import_build_wait_is_measured_around_existing_worker_limiter`

Patch `import_community_template` and `time.perf_counter` in the route test. Assert the timing header has only `queue`, `release_read`, `reconcile`, `resolve`, `serialize`, and `cache` tokens; it must not contain template ID, class/spec, raw values, SQL, or exception text.

- [ ] **Step 2: Prove RED**

```bash
python3 -m unittest tests.news_backend_test.NewsBackendTest.test_community_import_route_emits_numeric_server_timing_without_template_content
```

Expected: the route and optional response headers do not exist.

- [ ] **Step 3: Implement the additive route**

Extend `json_response(handler, status, payload, *, extra_headers=None)` without changing existing callers by inserting `for name, value in (extra_headers or {}).items(): handler.send_header(name, value)` immediately before `Content-Length`.

Validate header names in this helper against `{"Server-Timing"}` so route code cannot introduce arbitrary response headers. In `do_POST`, call `read_json_body(self)` once, wrap `import_community_template` in the existing `run_websim_gear_build`, measure queue time before/after the limiter, and pass only a generated request ID plus `cache_data_store()` and `current_gear_simc_runtime_revision()` into the runtime. Format finite non-negative durations as fixed three-decimal millisecond values; set `cache;desc=hit` or `cache;desc=miss` only. Do not log or return a raw request body.

- [ ] **Step 4: Prove GREEN and commit**

```bash
python3 -m unittest tests.news_backend_test
python3 -m py_compile server/news_backend.py server/gear_runtime.py server/postgres_cache_store.py server/gear_release_store.py server/community_template_import.py
git add server/news_backend.py tests/news_backend_test.py
git commit -m "feat: expose atomic community template import"
```

### Task 5: Add the one-request mini-program transport contract

**Files:**

- Modify: `pages/builds/websim-api.js`
- Modify: `tests/frontend-api-client.test.js`

**Interfaces:**

- Produces: `requestWebsimCommunityTemplateImport(params)` returning the existing `requestJson` transport result shape.
- Sends: `POST /api/websim/gear/community-import`, `timeout: 30000`, `responseMode: 'structured-problem'`, and exactly `{classKey, specKey, templateId, expectedManifestRevision}`.
- Does not use: `fallbackWebsimGear`, `requestWebsimGear`, local raw template data, or a synthetic success payload.

- [ ] **Step 1: Write API-client RED tests**

Add these tests to `tests/frontend-api-client.test.js`:

- `community template import uses the one-request structured endpoint`
- `community template import never forwards forged payload fields`
- `community template import keeps blocked structured problems instead of gear fallback`

Capture the `wx.request` options. Call the wrapper with extra `gearBySlot`, raw enhancement, and option-ID properties; assert the URL, `POST`, 30-second timeout, response mode, and that the transmitted data has exactly the four contract keys. For a 409/503 envelope, assert `fromFallback === false` and retain the server problem code.

- [ ] **Step 2: Prove RED**

```bash
node --test --test-name-pattern='community template import' tests/frontend-api-client.test.js
```

Expected: the exported wrapper is unavailable.

- [ ] **Step 3: Implement the narrow wrapper**

Add this function beside `requestWebsimGearResolve` and export it:

```javascript
function requestWebsimCommunityTemplateImport(params) {
  const source = params || {}
  const data = {
    classKey: String(source.classKey || ''),
    specKey: String(source.specKey || ''),
    templateId: String(source.templateId || ''),
    expectedManifestRevision: String(source.expectedManifestRevision || '')
  }
  return requestJson('/api/websim/gear/community-import', {
    method: 'POST', data, timeout: 30000, responseMode: 'structured-problem',
    validate: (value) => value && value.contractRevision === 'community-template-import-envelope-v1'
  })
}
```

Build `data` only from the four listed properties, so any caller-only extra property cannot cross the transport boundary. Do not provide a data fallback.

- [ ] **Step 4: Prove GREEN and commit**

```bash
node --test tests/frontend-api-client.test.js
git add pages/builds/websim-api.js tests/frontend-api-client.test.js
git commit -m "feat: add community template import client"
```

### Task 6: Atomically adopt the verified import snapshot in the workbench

**Files:**

- Modify: `pages/builds/gear-workbench-state.js`
- Modify: `pages/builds/detail.js`
- Modify: `tests/gear-workbench-state.test.js`
- Modify: `tests/builds-page.test.js`

**Interfaces:**

- Consumes: a verified import envelope containing `selectedGearBySlot`, `resolvedSnapshot`, `manifest`, bounded unresolved counts, and warnings.
- Produces: `adoptVerifiedCommunityImport(state, selectionIntent, snapshot, releaseContext)` and a detail-page `applyGearCommunityTemplate` path that commits once only when its import serial, interaction generation, selection key, and manifest identity still match.
- Preserves: `enhancementBySlotFromResolvedSnapshot`, `commitVerifiedEnhancementSnapshot`, saved-template behavior, subsequent selected-slot lazy loading, and all existing Resolve fences.

- [ ] **Step 1: Write adoption/fencing RED tests**

Add pure state tests:

- `adopt verified community import creates a verified workbench state without a second Resolve`
- `adopt verified community import rejects malformed selected options or manifest mismatch`

Add page tests:

- `community import makes one import request and no mode slot request`
- `community import commits canonical 8/8 gems, 6/8 enchants, and 2/2 embellishments`
- `blocked community import preserves the prior verified build and keeps the sheet open`
- `older community import response cannot overwrite a newer import`
- `post-import enhancement editing requests only the selected slot`

Reuse the existing Frost Mage fixture but inject `requestWebsimCommunityTemplateImport`; make `requestWebsimGear` throw if it is called during import. For the post-import edit assertion, open one enhancement slot and assert exactly `mode: 'slot', slot: 'finger1'`.

- [ ] **Step 2: Prove RED**

```bash
node --test --test-name-pattern='adopt verified community import|community import makes one import request|post-import enhancement' tests/gear-workbench-state.test.js tests/builds-page.test.js
```

Expected: the state adoption API and one-request behavior are unavailable.

- [ ] **Step 3: Add a verified-state adoption API**

In `gear-workbench-state.js`, add and export `adoptVerifiedCommunityImport(state, selectionIntent, snapshot, releaseContext)`. It returns a cloned unchanged/blocked state when the snapshot is not verified, selected options are malformed, or the release context has no manifest revision; otherwise it returns the verified state described below.

It must clone inputs, require `snapshot.status === 'verified'`, validate every selected option through the existing resolved-option shape checks, and require a non-empty `resolvedGearSignature`. It creates a confirmed/verified state with `currentSnapshot` and `lastVerifiedSnapshot` set to the imported snapshot, `resolveStatus: 'verified'`, no active request, and the reconstructed canonical Intent. It never creates a pending request or invokes a transport callback.

In `detail.js`, import `requestWebsimCommunityTemplateImport`, add `communityTemplateImporting: false` to page data, and replace only the community-template branch of `applyGearCommunityTemplate` with this sequence:

```javascript
const context = captureGearInteractionContext(this, { communityImport: { templateId, serial: importSerial } })
this.setData({ communityTemplateImporting: true })
return requestWebsimCommunityTemplateImport({ classKey, specKey, templateId, expectedManifestRevision })
  .then((result) => commitImportedCommunityTemplate(this, result, context))
  .finally(() => clearImportingOnlyIfCurrent(this, context))
```

`commitImportedCommunityTemplate` must verify the import serial/generation/selection key and manifest revision before it mutates state. Rebuild the client Intent only from `selectedGearBySlot` and `enhancementBySlotFromResolvedSnapshot(resolvedSnapshot)` plus the existing `resolverContext`; adopt it through the new workbench API; then set selected gear, canonical enhancements, derived state, workbench data, empty slot/enhancement sheets, and a closed community sheet in one `setData` call. Retain `communityEnhancementImportState` only for bounded unresolved counts/warnings and the accepted `resolvedGearSignature`.

Remove `loadCommunityTemplateEnhancementDetails` and `loadCommunityTemplateWeaponRepairDetails` from this import flow. Leave either helper in place only for an independently proven normal-editor caller. On any blocked/partial/unavailable/malformed response, do not change the current selection/workbench; clear only the spinner and show a retryable plain message.

- [ ] **Step 4: Prove GREEN and commit**

```bash
node --test tests/gear-workbench-state.test.js tests/builds-page.test.js
git add pages/builds/gear-workbench-state.js pages/builds/detail.js tests/gear-workbench-state.test.js tests/builds-page.test.js
git commit -m "feat: atomically apply community import snapshots"
```

### Task 7: Make import progress and recovery visible without leaking backend vocabulary

**Files:**

- Modify: `pages/builds/detail.wxml`
- Modify: `tests/builds-page.test.js`

**Interfaces:**

- Consumes: `communityTemplateImporting` and each template’s existing `canApplyGear` state.
- Produces: a non-reentrant import button with user-facing text `正在导入并校验强化…`, while preserving the existing unavailable/legality presentation.

- [ ] **Step 1: Write WXML behavior RED tests**

Add assertions that the community apply button:

- `community template button disables during import and keeps user-facing progress copy`
- `community template import failure restores the original apply action label`

The first test reads `detail.wxml` and asserts `disabled="{{!item.canApplyGear || communityTemplateImporting}}"`; the second exercises a structured blocked result and confirms the page state returns to `communityTemplateImporting === false` without closing the sheet.

- [ ] **Step 2: Prove RED**

```bash
node --test --test-name-pattern='button disables during import|failure restores' tests/builds-page.test.js
```

- [ ] **Step 3: Implement only the presentation boundary**

Replace the template button expression with:

```xml
<button class="gear-community-template-apply"
  disabled="{{!item.canApplyGear || communityTemplateImporting}}"
  data-id="{{item.id}}" bindtap="applyGearCommunityTemplate">
  {{communityTemplateImporting ? '正在导入并校验强化…' : item.actionLabel}}
</button>
```

Do not render Manifest, Release, cache, Resolver, queue, or timing terms. Keep the existing CSS unless a screenshot or manual device proof identifies a concrete clipping regression.

- [ ] **Step 4: Prove GREEN and commit**

```bash
node --test tests/builds-page.test.js
git add pages/builds/detail.wxml tests/builds-page.test.js
git commit -m "feat: show community import progress"
```

### Task 8: Complete Harness verification, candidate evidence, and release closure

**Files:**

- Create: `artifacts/releases/2026-07-15-community-template-import-performance/evidence.json`
- Modify: `artifacts/releases/2026-07-15-community-template-import-performance/requirement.json`
- Modify: `docs/superpowers/specs/2026-07-15-community-template-import-performance-design.md`
- Modify: `docs/roadmap.md`

**Interfaces:**

- Consumes: exact PR-head SHA, local test/CR output, candidate timing samples, HTTP/API results, 40-spec shadow, timer/log state, and real WeChat import/edit evidence.
- Produces: a truthfully complete Harness evidence packet; no evidence field may claim a candidate, deploy, WeChat, or merge result before it happened.

- [ ] **Step 1: Run scoped local verification and local CR**

```bash
python3 -m unittest \
  tests.community_template_import_test \
  tests.gear_release_store_test \
  tests.postgres_cache_store_test \
  tests.gear_runtime_test \
  tests.news_backend_test
node --test \
  tests/frontend-api-client.test.js \
  tests/gear-workbench-state.test.js \
  tests/builds-page.test.js
python3 -m py_compile \
  server/community_template_import.py \
  server/gear_release_store.py \
  server/postgres_cache_store.py \
  server/gear_runtime.py \
  server/news_backend.py
git diff --check
git status --short --branch
```

Review every changed line against the requirement: one request, one binding, observed-only, no raw values, no generic-cache budget sharing, no write side effects, and preserved initial/slot behavior. Fix local findings before the next command.

- [ ] **Step 2: Run Harness profiles from the exact release packet**

```bash
node scripts/verify-project.js --profile backend \
  --release artifacts/releases/2026-07-15-community-template-import-performance \
  --base origin/main
node scripts/verify-project.js --profile frontend \
  --release artifacts/releases/2026-07-15-community-template-import-performance \
  --base origin/main
node scripts/verify-project.js --profile full \
  --release artifacts/releases/2026-07-15-community-template-import-performance \
  --base origin/main
```

Expected: all selected commands pass, changed critical paths resolve to valid owners, and the release packet remains inside the repository. Do not write final evidence until the exact commands and their outputs are available.

- [ ] **Step 3: Deploy the exact PR head as a candidate only after deployment/smoke authorization**

Use the repository candidate path with async sync disabled:

```bash
WOW_DEPLOY_START_ASYNC_SYNCS=0 bash server/deploy_lighthouse.sh
```

Record the branch, commit, deployed runtime-file hashes, PostgreSQL-only environment, Active Manifest revision/pointer generation, and rollback command before testing. Do not trigger sync, backfill, cleanup, candidate release generation, or pointer changes.

- [ ] **Step 4: Collect candidate performance and compatibility evidence**

For one observed Frost Mage and the original Elemental Shaman reference, collect multiple cold and warm calls to `POST /api/websim/gear/community-import`; save HTTP status, elapsed milliseconds, response size, `Server-Timing`, cache state, and the one-request client trace. Verify separately:

```text
1. no request reaches the 30-second client timeout or cancellation state;
2. initial and explicit selected-slot requests retain their prior response contract;
3. 40/40 public templates remain observed-only and Resolve/Profile-compatible;
4. service status, timers, backflow state, and relevant logs remain truthful;
5. real WeChat imports Frost Mage with 8/8 gems, 6/8 enchants, 2/2 embellishments, then edits one selected slot.
```

Set the numeric cold/warm p50 and p95 in evidence from these samples. Do not invent an SLO or infer it from a gzip transfer size.

- [ ] **Step 5: Write evidence, final review, merge, and post-merge smoke**

Create `evidence.json` with factual local/candidate/post-merge results, command outputs or artifact paths, timing samples, exact identities, rollback outcome, and real WeChat acceptance. Change requirement/design/roadmap status to the actual reached state only. Then run:

```bash
node scripts/project-harness.js --check \
  --requirement-file artifacts/releases/2026-07-15-community-template-import-performance/requirement.json \
  --evidence-file artifacts/releases/2026-07-15-community-template-import-performance/evidence.json \
  --base origin/main
git diff --check
git diff --cached --check
```

After explicit user post-test acceptance, follow the repository closure sequence: final local CR, commit, fast-forward merge to `main`, rerun scoped verification on merge, push, verify local/`origin/main` SHA parity, remove the task branch/worktree, and run the post-merge live smoke against the same import, initial/slot, observed-only, timer/log, and rollback boundaries.

## Completion Definition

The change is complete only when a real observed community template imports through one request into a backend-resolved canonical snapshot, the mini-program remains responsive and retains its editable selected gems/enchants/embellishments, later editing loads only the selected slot, every failure preserves the prior verified configuration, and exact candidate plus post-merge evidence proves the performance, trust, compatibility, and rollback contracts. A local test pass or a 200 response alone is not completion.
