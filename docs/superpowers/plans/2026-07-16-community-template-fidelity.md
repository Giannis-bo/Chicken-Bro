# Community Template Fidelity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every successful community-template import an atomic, evidence-complete reproduction of the observed player's exact equipment, item levels, images and canonical enhancements.

**Architecture:** Keep resolver-facing `selection-intent-v1` unchanged. During Community Release construction, materialize a sealed `community-template-import-evidence-v1` alongside the intent; the scoped importer validates that evidence against the same immutable Gear Release and returns a v2 sealed display projection. The mini-program commits that projection without candidate fallback, while saved templates either revalidate their labelled source or rehydrate every legacy slot from an exact current Variant.

**Tech Stack:** Python 3, PostgreSQL immutable Gear/Community Releases, existing Resolver/Manifest contracts, WeChat Mini Program JavaScript, Node test runner, Python `unittest`.

## Global Constraints

- Only public `raiderio_observed_profile` winners may use the community-import action.
- The import request stays PostgreSQL-only, release-scoped and read-only; it performs no external fetch, sync, release promotion or broad candidate catalog expansion.
- `selection-intent-v1` remains the only Resolver input. Observed item level and image evidence live in sealed Community Release payload data, never in client-authored Intent.
- Generic Item metadata may supply a verified localized name and image for the same `itemId`; `cache.websim_gear_release_items.item_level` is never a selected-instance item-level authority.
- Missing or unverified sealed image metadata blocks import; a transient client/CDN image-load failure may use visual retry/fallback but never changes verified import state or item facts.
- A community import is only `verified` or `blocked`. It never commits a partial set, raw upstream enhancement value, generic fallback level or absent image.
- Gem occurrence order and duplicate values remain exact; capacity comes from existing exact Variant/global capability evidence and Resolver constraints.
- New community-origin saves store source identity. Legacy saves may only rehydrate each slot from an exact current `itemId + variantKey`; otherwise their entire apply is blocked.
- No migration is needed: `cache.websim_community_release_templates.payload_json` already stores sealed Community Release payloads. New evidence is additive and old releases remain browseable but not importable.
- Runtime changes require final CI plus one candidate deployment and real WeChat acceptance before merge. The import button remains unavailable while the active Manifest lacks v2 import evidence; only a shadowed and validated v2 Community Release may enable it. Keep `WOW_DEPLOY_START_ASYNC_SYNCS=0` for that candidate.

---

### Task 1: Materialize and gate immutable import evidence during Community Release construction

**Files:**
- Modify: `server/gear_release_tool.py:939-1035`, `server/gear_release_tool.py:1265-1435`
- Modify: `server/gear_release.py:520-540`, `server/gear_release.py:640-700`
- Modify: `tests/gear_release_tool_test.py:328-560`, `tests/gear_release_test.py`

**Interfaces:**
- Consumes: observed template `gearItems`, its selected `selection-intent-v1`, and the exact staged Gear Release snapshot.
- Produces: `candidate["importEvidence"]` with schema `community-template-import-evidence-v1`, stable source fingerprint, and per-slot `{itemId, variantKey, observedItemLevel, iconUrl}`.
- Produces: Community Release row `payload.importEvidence`; a selected observed winner without complete evidence is rejected before it can become an importable Release.

- [ ] **Step 1: Write failing evidence-materialization tests**

Add fixtures where an observed head has raw level `292`, the exact Variant is `292`, the generic Item is `197`, and its verified payload has a non-empty icon. Assert that the generated evidence records `292`, the exact identity and icon; assert the generic `197` is absent from the evidence. Add negative cases for missing raw item level, missing exact Variant, Variant level mismatch and missing verified image.

```python
evidence = community_template_import_evidence_from_template(
    template, gear_release_id="gear-release:target", gear_snapshot=snapshot
)
self.assertEqual(evidence["slots"]["head"]["observedItemLevel"], 292)
self.assertEqual(evidence["slots"]["head"]["iconUrl"], "https://example.test/head.jpg")
self.assertRaises(GearReleaseIntegrityError, community_template_import_evidence_from_template, bad_template, gear_release_id="gear-release:target", gear_snapshot=snapshot)
```

- [ ] **Step 2: Run the new tests and confirm they fail before implementation**

Run: `python3 -m unittest tests.gear_release_tool_test tests.gear_release_test`

Expected: the new helper is unavailable or the positive/negative evidence assertions fail.

- [ ] **Step 3: Add the pure evidence builder and release validation**

In `server/gear_release_tool.py`, define and export:

```python
COMMUNITY_TEMPLATE_IMPORT_EVIDENCE_REVISION = "community-template-import-evidence-v1"

def community_template_import_evidence_from_template(template, *, gear_release_id, gear_snapshot):
    """Seal observed per-slot display facts without changing Resolver Intent."""
    # Match every selected v1 slot to exactly one observed gearItem and exact verified Variant.
    # Require positive observedItemLevel == variant.itemLevel and a verified Item iconUrl.
    # Return only schemaRevision, sourceFingerprint and sorted bounded slot records.
```

Call it from `_template_candidate`, store its return as `importEvidence`, and have `_release_rows_from_election` place the elected evidence in `payload.importEvidence`, not in `selectionIntent`. In `server/gear_release.py`, validate this object for observed winners, include it in semantic change comparison, and reject a candidate whose evidence does not exactly agree with its v1 selected identity and Gear Release revision. Do not change `gear_contracts.py` or permit the evidence object in a client Intent.

- [ ] **Step 4: Run focused release tests and inspect the candidate payload**

Run: `python3 -m unittest tests.gear_release_tool_test tests.gear_release_test`

Expected: PASS; the prepared Community Release fixture contains `payload.importEvidence.schemaRevision == "community-template-import-evidence-v1"`, while its Resolver Intent remains `selection-intent-v1`.

- [ ] **Step 5: Commit the release-evidence slice**

```bash
git add server/gear_release_tool.py server/gear_release.py tests/gear_release_tool_test.py tests/gear_release_test.py
git commit -m "feat: seal observed community import evidence"
```

### Task 2: Make the scoped importer project only evidence-complete exact display facts

**Files:**
- Modify: `server/gear_release_store.py:1470-1705`
- Modify: `server/community_template_import.py:1-310`
- Modify: `server/postgres_cache_store.py:1175-1290`
- Test: `tests/community_template_import_test.py`, `tests/gear_release_store_test.py`, `tests/postgres_cache_store_test.py`

**Interfaces:**
- Consumes: one active Manifest binding, one observed winner's `selection-intent-v1` plus `payload.importEvidence`, exact scoped Variant/Item/Option rows, and existing source labels.
- Produces: `websim-community-template-import-v2` source data with `importedGearBySlot`, a clean v1 Resolver Intent, and no successful `partial` state.
- Produces: stable bounded blocked codes for evidence failure; cache identity includes the import contract revision.

- [ ] **Step 1: Write failing projector/store tests for the root regression and fail-closed cases**

Replace the current partial-success fixture with a complete v1 Intent plus v1 import evidence. Add tests for:

```python
source = build_community_template_import_source(winner, variants_292, options, items=[generic_item_197])
self.assertEqual(source["importedGearBySlot"]["head"]["itemLevel"], 292)
self.assertEqual(source["importedGearBySlot"]["head"]["ilevel"], 292)
self.assertEqual(source["importedGearBySlot"]["head"]["iconUrl"], VERIFIED_ICON)

for broken in (missing_level, mismatched_variant_level, missing_icon, unmapped_gem):
    self.assertEqual(build_community_template_import_source(broken, variants, options)["status"], "blocked")
```

Also assert a v1 Community Release without `payload.importEvidence` remains readable by browse paths but returns `template_import_evidence_incomplete` for import; no test may expect `status == "partial"` from import projection.

- [ ] **Step 2: Run focused importer/store tests and confirm they fail**

Run: `python3 -m unittest tests.community_template_import_test tests.gear_release_store_test tests.postgres_cache_store_test`

Expected: the v2 field, generic-level precedence and strict blocked assertions fail against the v1 projector.

- [ ] **Step 3: Implement the strict v2 projector and scoped read contract**

In `server/community_template_import.py`:

```python
COMMUNITY_TEMPLATE_IMPORT_CONTRACT_REVISION = "websim-community-template-import-v2"

# For each selection-intent-v1 slot:
# 1. require matching payload.importEvidence slot;
# 2. require evidence observedItemLevel == exact Variant itemLevel;
# 3. require evidence iconUrl and same-item verified metadata;
# 4. reconcile every selected enhancement occurrence; any rejection returns _blocked(problem);
# 5. emit importedGearBySlot with identical itemLevel and ilevel.
```

Keep `selectionIntent` clean and v1. Change `build_community_template_selection_intent` to return an Intent only for `verified` source data. Change `community_template_import_public_data` to return `importedGearBySlot`, template profile/gear fingerprint and Manifest binding; omit `unresolvedBySlot` and warnings from successful output.

In `server/gear_release_store.py`, keep the existing exact `(itemId, variantKey)` scoped read and row-hash checks, but explicitly retain `payload.importEvidence` on the winner and Item payload image metadata. Do not read, compare or forward generic Item `itemLevel` into the projection. In `server/postgres_cache_store.py`, include `COMMUNITY_TEMPLATE_IMPORT_CONTRACT_REVISION` in `_community_template_import_cache_fingerprint` so v1 cached payloads cannot serve the v2 client.

- [ ] **Step 4: Run focused importer/store tests and inspect bounded output**

Run: `python3 -m unittest tests.community_template_import_test tests.gear_release_store_test tests.postgres_cache_store_test`

Expected: PASS; JSON output includes no raw unmatched enhancement token, no broad candidate list, no `partial` success, and no `197` when exact selected evidence is `292`.

- [ ] **Step 5: Commit the scoped-projection slice**

```bash
git add server/community_template_import.py server/gear_release_store.py server/postgres_cache_store.py tests/community_template_import_test.py tests/gear_release_store_test.py tests/postgres_cache_store_test.py
git commit -m "fix: preserve exact community template display facts"
```

### Task 3: Enforce two-state import semantics through runtime, cache and HTTP envelope

**Files:**
- Modify: `server/gear_runtime.py:245-425`
- Test: `tests/community_template_import_test.py`, `tests/gear_runtime_test.py`, `tests/news_backend_test.py`

**Interfaces:**
- Consumes: a v2 verified projector source or a blocked source from the scoped cache-store context.
- Produces: `community-template-import-envelope-v1` containing only verified v2 data or a bounded blocked/unavailable problem; verified cache entries only.

- [ ] **Step 1: Write failing runtime-envelope tests**

Add tests that a source with unmapped enhancement, missing icon or missing import evidence returns HTTP `200`, envelope `status == "blocked"`, no `data.selectedGearBySlot`/`data.importedGearBySlot` payload and no cache write. Add the positive assertion:

```python
self.assertEqual(envelope["status"], "verified")
self.assertEqual(envelope["data"]["contractRevision"], "websim-community-template-import-v2")
self.assertEqual(envelope["data"]["importedGearBySlot"]["head"]["itemLevel"], 292)
self.assertEqual(store.cached[0][1]["data"]["status"], "verified")
```

- [ ] **Step 2: Run runtime/API tests and confirm they fail**

Run: `python3 -m unittest tests.community_template_import_test tests.gear_runtime_test tests.news_backend_test`

Expected: old runtime still emits the `partial` envelope or v1 contract data.

- [ ] **Step 3: Remove the partial import success path**

In `server/gear_runtime.py`, accept only a v2 `verified` source and Resolver snapshot as cacheable success. Delete the `source_status == "partial"` envelope branch. Keep `blocked` for evidence/Resolver conflict and `unavailable` only for service/authority failures. Preserve existing request validation, queue timing, `Server-Timing`, request ID and no-write behavior.

Do not change the route path or client request shape in `server/news_backend.py`; extend its endpoint test only to pin v2 verified/block response semantics.

- [ ] **Step 4: Run runtime/API tests and verify cache behavior**

Run: `python3 -m unittest tests.community_template_import_test tests.gear_runtime_test tests.news_backend_test`

Expected: PASS; only a fully verified v2 response is cached, and every evidence problem preserves the previously committed client state.

- [ ] **Step 5: Commit the runtime-contract slice**

```bash
git add server/gear_runtime.py tests/community_template_import_test.py tests/gear_runtime_test.py tests/news_backend_test.py
git commit -m "fix: block incomplete community template imports"
```

### Task 4: Commit sealed imported display state and safely replay saved templates in the mini-program

**Files:**
- Modify: `pages/builds/detail.js:439-545`, `pages/builds/detail.js:3310-3375`, `pages/builds/detail.js:3529-3565`, `pages/builds/detail.js:6808-6865`
- Test: `tests/builds-page.test.js:13420-15020`

**Interfaces:**
- Consumes: a `websim-community-template-import-v2` verified envelope with `importedGearBySlot`, template profile/gear fingerprints and a verified Resolver snapshot.
- Produces: selected slot rows whose `itemLevel`, `ilevel`, name and image come directly from sealed import data; `metadata.importOrigin` for new community-origin saves.
- Produces: saved-template replay that reimports a labelled community source or exact-variant rehydrates every legacy slot before Resolve.

- [ ] **Step 1: Write failing frontend regression tests**

Update the atomic-import harness to return v2 `importedGearBySlot` containing selected level `292`, image URL and a generic page candidate at `197`. Assert cards and `selectedGearBySlot` retain `292` and the sealed icon. Assert `matchingGearCandidateForItem` cannot alter those fields.

Add saved-template cases:

```javascript
assert.deepEqual(saved.metadata.importOrigin, {
  contractRevision: 'websim-community-template-import-v2',
  templateId: 'observed_profile_mage_frost',
  profileHash: 'profile-fingerprint',
  gearHash: 'gear-fingerprint',
  manifestRevision: 'manifest-mage-frost-import'
})
assert.match(toasts.at(-1).title, /源模板已变化|无法验证|暂不可导入/)
```

Cover a legacy saved `197` snapshot that exact-variant rehydrates to `292`, and a legacy snapshot with one missing exact Variant that leaves all current selection state unchanged and reports one blocked apply.

- [ ] **Step 2: Run the frontend test file and confirm it fails**

Run: `node --test tests/builds-page.test.js`

Expected: v1 envelope assertions, candidate merge behavior and missing-origin save metadata fail.

- [ ] **Step 3: Replace candidate fallback with sealed import display state**

In `pages/builds/detail.js`:

```javascript
function sealedImportedGearSelectionForPage(importedGearBySlot) {
  // Require slot, itemId, variantKey, equal positive itemLevel/ilevel,
  // displayName and iconUrl for every record. Do not call matchingGearCandidateForItem.
}
```

Make `validCommunityImportEnvelope` require the v2 data revision and `importedGearBySlot`. Update `commitImportedCommunityTemplate` to use the sealed function, retain normal `attachGearGameAsset` rendering, and store `{ templateId, profileHash, gearHash, manifestRevision, contractRevision }` in `communityEnhancementImportState`.

When `gearTemplateSaveDraft` saves a current community import, add that state as `metadata.importOrigin`. Refactor `applySavedGearTemplate` into two paths:

1. labelled `importOrigin`: re-run the atomic import, require all saved origin fields to equal the returned v2 template identity, then reuse the normal atomic commit; mismatch or block leaves the old workbench unchanged;
2. legacy/no-origin: rehydrate *every* selected slot from an exact current candidate identity, replacing only display fields from the exact Variant and verified Item image. If any slot cannot be matched exactly, toast and return without resolving or changing the workbench. Then use the existing normal saved-template Resolve path.

Do not change ordinary slot editing, personal-template labels, request timeout or the community-template sheet's importing fence.

- [ ] **Step 4: Run the frontend test file and inspect the saved payloads**

Run: `node --test tests/builds-page.test.js`

Expected: PASS; the v2 import renders sealed image/level, both replay paths are atomic, duplicates/8-8/6-8/2-2 enhancement behavior remains green, and no legacy `197` is committed.

- [ ] **Step 5: Commit the mini-program slice**

```bash
git add pages/builds/detail.js tests/builds-page.test.js
git commit -m "fix: render and replay verified community templates"
```

### Task 5: Run regression gates, record candidate proof, and close only with real player evidence

**Files:**
- Modify after verified delivery only: `docs/roadmap.md`
- Create after verified delivery only: `artifacts/releases/2026-07-16-community-template-fidelity/requirement.json`
- Create after verified delivery only: `artifacts/releases/2026-07-16-community-template-fidelity/evidence.json`

**Interfaces:**
- Consumes: final PR head, immutable candidate Community/Gear Release pair, a frozen observed reference and real WeChat output.
- Produces: evidence-backed current-roadmap completion record or an honest blocked/partial release finding; no release is marked complete from local tests alone.

- [ ] **Step 1: Run targeted local regressions after the final implementation commit**

Run:

```bash
python3 -m unittest tests.gear_release_tool_test tests.gear_release_test tests.community_template_import_test tests.gear_release_store_test tests.postgres_cache_store_test tests.gear_runtime_test tests.news_backend_test
node --test tests/builds-page.test.js
git diff --check
```

Expected: all targeted tests pass and diff check reports no whitespace errors. If `tests/project-state.test.js` still fails on the pre-existing roadmap-top index condition, record it separately; do not weaken the import contract or claim the Harness profile is green.

- [ ] **Step 2: Run the final local review and CI gate**

Inspect the complete diff against this design: no generic Item level is read by import projection; no raw enhancement values cross the API; no `partial` successful import remains; imported cards bypass candidate fallback; old saves are exact-rehydrated or blocked. Run the repository's final CI/full entrypoint once for the final runtime head.

Expected: no Critical or Important local review finding. Any unrelated existing Harness failure remains explicitly separated from this feature's targeted proof.

- [ ] **Step 3: Deploy one candidate and switch only after v2 Release evidence is ready**

Run the repository candidate path with async sync disabled:

```bash
WOW_DEPLOY_SKIP_BOOTSTRAP=1 WOW_DEPLOY_START_ASYNC_SYNCS=0 ./server/deploy_lighthouse.sh
```

Before the deploy, record final branch/commit, runtime file hashes, current Active Manifest identity and rollback command. Do not start a Community sync, backfill or release promotion from the deploy command.

On the candidate, keep the import action unavailable while the active Manifest points to v1 evidence. Materialize an inactive v2 Community Release, run the exact-slot source-evidence shadow and record its Release ID. Only then perform the controlled Manifest switch and enable v2 import. If materialization, shadow, Manifest identity or client/server contract parity fails, leave browse available and keep the import action unavailable; do not invoke v1 import behavior.

- [ ] **Step 4: Execute candidate smoke and real WeChat acceptance**

Verify against the frozen observed reference:

1. Every required slot is present; a two-handed profile legitimately omits only its incompatible off-hand.
2. Each card's exact item level and image equals the sealed expected vector; a generic `197` cannot appear where selected evidence is `292`.
3. Ordered and duplicate gems, enchants, embellishments and Resolver capacity totals match the observed/canonical evidence.
4. An intentionally missing image *metadata*, raw option or mismatched level blocks the entire import and preserves the prior build; a simulated client image-load failure preserves the sealed item level and verified import state.
5. Save/replay succeeds only for a matching `importOrigin`; legacy exact rehydration fixes the fixture, while a missing Variant blocks it.
6. Resolve/Profile, 40-spec public observed-only shadow, timer/backflow/log state and rollback availability remain healthy.

- [ ] **Step 5: Publish only verified evidence and commit the closure record**

Write requirement/evidence artifacts with exact candidate identity, test output, manifest/release IDs, slot vector, WeChat screenshots/action ledger, timer/log truth and rollback path. Update the roadmap row from `正在推进` only when all items above are evidenced; otherwise record the precise blocker. Commit with:

```bash
git add docs/roadmap.md artifacts/releases/2026-07-16-community-template-fidelity
git commit -m "docs: record community template fidelity evidence"
```
