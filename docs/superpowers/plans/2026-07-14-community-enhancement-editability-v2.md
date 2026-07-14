# Community Enhancement Editability v2 Implementation Plan

> **Execution note:** Use `superpowers:executing-plans` for implementation, `superpowers:test-driven-development` for every production change, and `superpowers:verification-before-completion` before any completion claim. Work only in the isolated branch/worktree named below.

**Goal:** Import community-template gems, enchants, and embellishments as ordinary editable canonical selections, backed by a versioned static socket authority, with the Frost Mage reference resolving and rendering `8/8`, `6/8`, and `2/2`.

**Architecture:** Candidate refresh collects bounded evidence once, a new pure socket owner converts every source to a minimum-total claim and materializes final facts into an immutable Gear Release, and request-time PG/Resolver code consumes only the active release. `capabilityRevision` fences signatures and enables a v1/v2-compatible rollout. The frontend keeps occurrence-aware drafts and commits only verified `resolvedSlots[*].selectedOptions`.

**Tech stack:** Python 3 `unittest`; Node `node:test`; WeChat mini-program JS/WXML/WXSS; PostgreSQL immutable Gear/Community Release + Manifest pointer; existing Project Harness; existing deployment scripts/systemd services.

**Design:** [Community Enhancement Editability v2](../specs/2026-07-14-community-enhancement-editability-v2-design.md)

**Harness packet:** [requirement](../../../artifacts/releases/2026-07-14-community-enhancement-editability/requirement.json) · [evidence](../../../artifacts/releases/2026-07-14-community-enhancement-editability/evidence.json)

**Execution workspace:** `/Users/boyuan/Documents/wow_mini_program/.worktrees/fix-community-enhancement-editability` on `codex/fix-community-enhancement-editability`, based on `origin/main@2e7db63361944a786422771a8f8358a0d5d20366`.

**Hard boundaries:** Preserve observed-only public templates, PG-only runtime, backend-owned legality/Profile serialization, Catalyst fail-closed behavior, lazy slot hydration, and stale-response fencing. Do not add a SQL migration, runtime external fetch, broad gear redesign, deploy-triggered async sync, or merge before exact-candidate real WeChat evidence.

---

## Task 1: Add the pure static socket authority and executable Mage fixture

**Files:**

- Create: `server/gear_socket_authority.py`
- Create: `tests/gear_socket_authority_test.py`
- Create: `tests/fixtures/midnight-mage-frost-socket-evidence-v1.json`
- Modify: `docs/project-owner-map.json`
- Modify: `docs/backend-owner-map.json`
- Modify: `tests/project-owner-map.test.js`
- Modify: `tests/backend-owner-map.test.js`

**Step 1: Write the failing pure tests**

Add these tests before production code:

- `test_nested_battle_net_socket_array_preserves_zero_one_two`
- `test_midnight_jewelry_floor_does_not_generalize_two_sockets`
- `test_exact_variant_sources_are_minimum_totals_and_never_sum`
- `test_gem_sequence_is_exact_variant_lower_bound_only`
- `test_unknown_season_and_unknown_bonus_fail_closed`
- `test_materializer_does_not_mutate_snapshot`
- `test_mage_fixture_materializes_1_2_1_1_2_1`

The fixture must identify the six socket-bearing exact instances in this order: `head`, `neck`, `wrist`, `waist`, `finger1`, `finger2`; expected capacities are `[1, 2, 1, 1, 2, 1]`. Include one different ring with only the one-socket floor so item scoping is explicit.

**Step 2: Prove RED**

Run:

```bash
python3 -m unittest tests.gear_socket_authority_test
```

Expected: failure because the module/functions do not exist or the current behavior cannot prove the fixture.

**Step 3: Implement the smallest pure owner**

Export exactly:

```python
LEGACY_CAPABILITY_REVISION = 'gear-capability-matrix-v1'
CAPABILITY_REVISION = 'gear-capability-matrix-v2'
SUPPORTED_CAPABILITY_REVISIONS = (LEGACY_CAPABILITY_REVISION, CAPABILITY_REVISION)
SOCKET_FACT_SCHEMA_REVISION = 'gear-socket-fact-v1'

count_payload_socket_entries(payload)
parse_simc_socket_bonus_minimums(output)
derive_item_socket_fact(...)
derive_variant_socket_fact(...)
materialize_gear_socket_facts(snapshot, ...)
```

Every claim must be a proven total lower bound and final capacity must be `max(claim.minimumTotal)`. Never sum season, item, variant, bonus, or observed claims. `gem_id` tokens may strengthen only the exact variant lower bound. Unknown season/bonus inputs must remain fail-closed.

Update both owner maps so the new module is the socket-fact owner inside the existing canonical gear/release domains; add its test file to the owner verification lists. Do not create a parallel product domain.

**Step 4: Prove GREEN and owner coverage**

```bash
python3 -m unittest tests.gear_socket_authority_test
node --test tests/project-owner-map.test.js tests/backend-owner-map.test.js
```

Expected: all pass, including non-mutation and `[1,2,1,1,2,1]`.

**Step 5: Commit**

```bash
git add server/gear_socket_authority.py tests/gear_socket_authority_test.py tests/fixtures/midnight-mage-frost-socket-evidence-v1.json docs/project-owner-map.json docs/backend-owner-map.json tests/project-owner-map.test.js tests/backend-owner-map.test.js
git commit -m 'feat: add static socket authority'
```

## Task 2: Materialize socket facts before Gear Release identity is computed

**Files:**

- Modify: `server/gear_release_tool.py`
- Modify: `server/gear_release_refresh.py`
- Modify: `tests/gear_release_tool_test.py`
- Modify: `tests/gear_release_refresh_test.py`

**Step 1: Write release-builder RED tests**

Add:

- `test_prepare_staging_gear_release_materializes_socket_facts_before_hash`
- `test_identical_socket_evidence_reuses_content_hash`
- `test_simc_probe_parses_only_socket_effects`
- `test_socket_fact_change_is_capability_change_and_requires_manual_cutover`
- `test_socket_bonus_probe_failure_keeps_active_pointer_unchanged`

Use injected runner output; tests must not invoke a real binary or network.

**Step 2: Prove RED**

```bash
python3 -m unittest tests.gear_release_tool_test tests.gear_release_refresh_test
```

Expected: the new tests fail because staging snapshots are currently validated/hashed before socket materialization and refresh has no bounded socket probe.

**Step 3: Add candidate-time acquisition and materialization**

In `gear_release_tool.py`:

- add `load_simc_socket_bonus_minimums(simc_binary, *, runner=subprocess.run)`;
- run bounded `show_bonus_ids=1` only during candidate construction;
- parse with `gear_socket_authority.parse_simc_socket_bonus_minimums`;
- add an explicit `socket_bonus_minimums` input to `prepare_staging_gear_release`;
- call `materialize_gear_socket_facts` before `validate_gear_snapshot`, summary, snapshot hash, and release ID generation;
- record SimC revision and a deterministic socket-probe digest in release source evidence.

In `gear_release_refresh.py`, thread the probe result through `build_staging_candidates` and `_run_from_environment`. Probe/parse/materialization failure must return a bounded failed/blocked event without sealing or moving the active pointer. Classify a capability-revision or materialized socket-fact change as manual-required.

**Step 4: Prove GREEN**

```bash
python3 -m unittest tests.gear_release_tool_test tests.gear_release_refresh_test
```

Expected: all pass; identical evidence is content-address stable and a changed fact cannot auto-promote.

**Step 5: Commit**

```bash
git add server/gear_release_tool.py server/gear_release_refresh.py tests/gear_release_tool_test.py tests/gear_release_refresh_test.py
git commit -m 'feat: materialize socket authority in gear releases'
```

## Task 3: Bind `capabilityRevision` through runtime identity with a safe v1/v2 window

**Files:**

- Modify: `server/websim_payload.py`
- Modify: `server/gear_release_tool.py`
- Modify: `server/gear_release_store.py`
- Modify: `server/pg_gear_authority_loader.py`
- Modify: `server/gear_contracts.py`
- Modify: `server/gear_runtime.py`
- Modify: `tests/websim_payload_test.py`
- Modify: `tests/gear_release_store_test.py`
- Modify: `tests/pg_gear_authority_loader_test.py`
- Modify: `tests/gear_contracts_test.py`
- Modify: `tests/gear_runtime_test.py`

**Step 1: Write dependency-vector RED tests**

Add:

- `test_dependency_vector_requires_capability_revision`
- `test_resolved_gear_signature_changes_with_capability_revision`
- `test_active_reader_accepts_supported_v1_manifest_during_v2_rollout`
- `test_active_reader_rejects_unsupported_capability_revision`
- `test_release_context_exposes_capability_revision`
- `test_runtime_authority_advertises_current_and_supported_capability_revisions`

**Step 2: Prove RED**

```bash
python3 -m unittest tests.gear_contracts_test tests.gear_release_store_test tests.gear_runtime_test tests.pg_gear_authority_loader_test tests.websim_payload_test
```

Expected: focused new assertions fail; record any unrelated baseline failure separately before continuing.

**Step 3: Propagate the revision exactly once**

- `websim_payload.py::gear_resolver_runtime_authority` returns current v2 `dependencyRevisions.capabilityRevision` and `supportedCapabilityRevisions=[v1,v2]` from the new owner module.
- `gear_release_tool.py::runtime_dependency_revisions` consumes runtime authority; remove its local v1 constant.
- `gear_release_store.py::_active_runtime_dependencies` keeps strict equality for the existing revision fields, accepts only a manifest capability revision in the runtime supported set, and returns the manifest revision so signatures anchor the active release.
- Add `capabilityRevision` to `pg_gear_authority_loader.py::_REQUIRED_RUNTIME_REVISIONS`, `gear_contracts.py::_REQUIRED_DEPENDENCY_FIELDS`/`resolved_gear_signature`, and `gear_runtime.py::_release_context`.

Do not require active manifest v2 at reader-deploy time. That would create an outage before pointer cutover.

**Step 4: Prove GREEN**

```bash
python3 -m unittest tests.gear_contracts_test tests.gear_release_store_test tests.gear_runtime_test tests.pg_gear_authority_loader_test tests.websim_payload_test
```

**Step 5: Commit**

```bash
git add server/websim_payload.py server/gear_release_tool.py server/gear_release_store.py server/pg_gear_authority_loader.py server/gear_contracts.py server/gear_runtime.py tests/websim_payload_test.py tests/gear_release_store_test.py tests/pg_gear_authority_loader_test.py tests/gear_contracts_test.py tests/gear_runtime_test.py
git commit -m 'feat: bind gear capability revision'
```

## Task 4: Make the PG loader consume v2 released facts and stop request-time inference

**Files:**

- Modify: `server/pg_gear_authority_loader.py`
- Modify: `tests/pg_gear_authority_loader_test.py`
- Modify: `tests/gear_resolver_test.py`
- Modify: `tests/gear_rule_matrix_test.py`

**Step 1: Write versioned-consumer RED tests**

Add:

- `test_v2_base_capability_uses_materialized_item_socket_fact`
- `test_v2_exact_variant_uses_materialized_socket_override`
- `test_v2_raw_gem_sequence_without_socket_fact_does_not_create_capacity`
- `test_v1_release_preserves_legacy_projection_during_rollout`
- `test_midnight_mage_template_resolves_socket_counts_1_2_1_1_2_1`
- `test_eight_canonical_gems_are_editable_and_ninth_is_blocked`
- `test_socket_rule_uses_v2_exact_variant_capacity`

**Step 2: Prove RED**

```bash
python3 -m unittest tests.pg_gear_authority_loader_test tests.gear_resolver_test tests.gear_rule_matrix_test
```

**Step 3: Implement the version branch**

Pass manifest `capabilityRevision` into `_project_base_capabilities`, `_variant_capability_overrides`, and `_project_variant`.

- v1: preserve the existing projection solely for active-pointer rollback.
- v2: accept only materialized `baseCapabilities.socketCount` and `capabilityOverrides.socketCount` with `socketEvidence.schemaRevision=gear-socket-fact-v1` and `authorityRevision=gear-capability-matrix-v2`.
- Delete v2 request-time capacity raising from raw `gem_id` token count.
- Keep `gear_resolver.py::derive_effective_capabilities` and `gear_rule_matrix.py::_effective_item_for_selection` as consumers; do not add a second inference table there.

**Step 4: Prove GREEN**

```bash
python3 -m unittest tests.pg_gear_authority_loader_test tests.gear_resolver_test tests.gear_rule_matrix_test
```

Expected: Mage vector passes, eight canonical occurrences pass, ninth is blocked, raw-only v2 data cannot invent capacity, v1 remains readable.

**Step 5: Commit**

```bash
git add server/pg_gear_authority_loader.py tests/pg_gear_authority_loader_test.py tests/gear_resolver_test.py tests/gear_rule_matrix_test.py
git commit -m 'fix: consume released socket authority'
```

## Task 5: Preserve exact socket counts and ordered gem occurrences in source/public payloads

**Files:**

- Modify: `server/websim_payload.py`
- Modify: `server/raiderio_payload.py`
- Modify: `tests/websim_payload_test.py`
- Modify: `tests/raiderio_payload_test.py`

**Step 1: Write RED tests**

Add:

- `test_item_socket_capacity_counts_nested_official_socket_entries`
- `test_two_socket_ring_is_not_collapsed_to_one`
- `test_enrich_catalog_item_preserves_socket_count`
- `test_ring_socket_capacity_does_not_generalize_across_item_ids`
- `test_extract_gear_preserves_duplicate_gem_occurrences_in_order`

**Step 2: Prove RED**

```bash
python3 -m unittest tests.raiderio_payload_test tests.websim_payload_test
```

**Step 3: Fix projection, not authority ownership**

Change `item_payload_has_socket`, `item_socket_capacity`, `item_mod_capabilities`, and `enrich_catalog_item` so nested official socket arrays retain count and `modCapabilities` reconstruction cannot drop `socketCount`. Remove the fixed-one jewelry collapse. Public payload is first-paint information only; exact editing capacity remains canonical Resolve output.

Change `raiderio_option_ids(value, keys=None)` to accept an explicit keyword-only deduplication policy. Keep the current default for bonus/enchant callers, but call it with deduplication disabled for `gems[]` in `extract_raiderio_item_enhancements`. Filter empty/zero values while preserving source order and duplicate occurrences.

**Step 4: Prove GREEN and commit**

```bash
python3 -m unittest tests.raiderio_payload_test tests.websim_payload_test
git add server/websim_payload.py server/raiderio_payload.py tests/websim_payload_test.py tests/raiderio_payload_test.py
git commit -m 'fix: preserve socket and gem occurrence facts'
```

## Task 6: Establish verified snapshot as the only committed frontend enhancement source

**Files:**

- Modify: `pages/builds/detail.js`
- Modify: `pages/builds/gear-workbench-state.js`
- Modify: `tests/builds-page.test.js`
- Modify: `tests/gear-workbench-state.test.js`

**Step 1: Write RED tests**

Add:

- `gear selection intent preserves ordered duplicate gem option ids`
- `verified Resolve selectedOptions are the only committed enhancement state`
- `gear template save serializes verified canonical enhancements instead of submitted draft`

Make the fake server return option identities different from the submitted draft; save and visible committed state must use the server values.

**Step 2: Prove RED**

```bash
node --test --test-name-pattern='selection intent preserves ordered duplicate|only committed enhancement|serializes verified canonical' tests/gear-workbench-state.test.js tests/builds-page.test.js
```

**Step 3: Add canonical projection and fenced commit helpers**

In `detail.js` add:

```javascript
enhancementBySlotFromResolvedSnapshot(snapshot)
commitVerifiedEnhancementSnapshot(page, request, snapshot, context)
```

The projection reads only `resolvedSlots[slot].selectedOptions`, preserving ordered duplicate `gemOptionIds`; it never reads raw `simcOptions`. The commit must first pass existing `acceptedVerifiedGearResolve(...)` serial/intentVersion/current-snapshot fencing. Keep submitted intent separate from committed visible enhancement state.

**Step 4: Prove GREEN and commit**

```bash
node --test --test-name-pattern='selection intent preserves ordered duplicate|only committed enhancement|serializes verified canonical' tests/gear-workbench-state.test.js tests/builds-page.test.js
git add pages/builds/detail.js pages/builds/gear-workbench-state.js tests/builds-page.test.js tests/gear-workbench-state.test.js
git commit -m 'fix: commit verified enhancement snapshots'
```

## Task 7: Make sheet confirmation an atomic draft-to-Resolve transaction

**Files:**

- Modify: `pages/builds/detail.js`
- Modify: `pages/builds/detail.wxml`
- Modify: `tests/builds-page.test.js`

**Step 1: Write RED tests**

Add:

- `enhancement confirm keeps committed state unchanged while Resolve is pending`
- `enhancement confirm atomically commits canonical options after verified Resolve`
- `blocked enhancement Resolve preserves committed state and editable draft`
- `closing enhancement sheet discards an unconfirmed draft`

Use a deferred Promise and assert that summary, save, and Profile stay on the old verified state while the sheet contains the new draft.

**Step 2: Prove RED**

```bash
node --test --test-name-pattern='committed state unchanged|atomically commits|preserves committed state|discards an unconfirmed' tests/builds-page.test.js
```

**Step 3: Implement atomic confirmation**

- Add `submitting:false` to `emptyGearEnhancementSheet`.
- In canonical mode, build `confirmedEnhancementBySlot` from the resolved snapshot; the sheet draft remains local.
- `confirmGearEnhancementSheet` validates the draft, sets only `submitting:true`, and calls Resolve with an `atomicEnhancementCommit` context. It must not write `data.enhancementBySlot` or close the sheet before verification.
- `confirmAndResolveGearIntent` must omit the pending enhancement patch for this context. On verified response, call the fenced commit helper, rebuild rows/panel, then close. On blocked/offline/revision failure, keep old committed state, restore `submitting:false`, retain draft and active slot, and show structured problems.
- Disable the WXML confirm button while submitting.

**Step 4: Prove GREEN and commit**

```bash
node --test --test-name-pattern='committed state unchanged|atomically commits|preserves committed state|discards an unconfirmed' tests/builds-page.test.js
git add pages/builds/detail.js pages/builds/detail.wxml tests/builds-page.test.js
git commit -m 'fix: resolve enhancement drafts atomically'
```

## Task 8: Edit gems by `socketIndex` and preserve duplicate occurrences

**Files:**

- Modify: `pages/builds/detail.js`
- Modify: `pages/builds/detail.wxml`
- Modify: `pages/builds/detail.wxss`
- Modify: `tests/builds-page.test.js`

**Step 1: Write RED tests**

Add:

- `full gem slot replaces one gem by socket index without changing used count`
- `duplicate gem replacement changes only the addressed occurrence`
- `removing one duplicate gem keeps the other occurrence`
- `socket-index edit preserves ordered gems through Resolve and reopen`
- `unique gem replacement excludes the current socket from group counting`

Replace the old identity-toggle assertion with occurrence/index semantics; retain an overflow blocker regression.

**Step 2: Prove RED**

```bash
node --test --test-name-pattern='socket index|addressed occurrence|duplicate gem|unique gem replacement' tests/builds-page.test.js
```

**Step 3: Implement occurrence-aware rows**

Add pure helpers:

```javascript
gemOptionIdsForRecord(record)
replaceGemOptionAtIndex(record, socketIndex, optionId, socketCapacity)
removeGemOptionAtIndex(record, socketIndex)
buildGemSocketRows(slot, item, options, selected, uniqueGroups)
```

Render one row per canonical socket (`0..socketCount-1`) and carry `data-socket-index`. Replacement at an occupied index is allowed at 8/8; append is allowed only at the next empty index and below capacity; removal uses `splice`, never ID-based `filter`. Unique-group calculation subtracts the current occurrence before judging replacement.

**Step 4: Prove GREEN and commit**

```bash
node --test --test-name-pattern='socket index|addressed occurrence|duplicate gem|unique gem replacement' tests/builds-page.test.js
git add pages/builds/detail.js pages/builds/detail.wxml pages/builds/detail.wxss tests/builds-page.test.js
git commit -m 'fix: edit gems by socket occurrence'
```

## Task 9: Allow full-capacity enchant/embellishment replacement and remove inherited UI

**Files:**

- Modify: `pages/builds/detail.js`
- Modify: `pages/builds/detail.wxml`
- Modify: `pages/builds/detail.wxss`
- Modify: `tests/builds-page.test.js`

**Step 1: Write RED replacement tests**

Add:

- `embellishment cap allows replacement in an occupied slot`
- `embellishment cap blocks only a third occupied slot`
- `enchant replacement keeps used count stable at six of eight`

Rewrite the old cap test so alternatives in an occupied embellishment slot are enabled while an empty third slot is disabled.

**Step 2: Write RED product-copy/unknown-value tests**

Add:

- `community enhancement UI contains no inherited or non-editable product copy`
- `unmatched community option stays out of Intent and leaves canonical slot editable`
- `unmatched community option does not alter canonical used or max counts`
- `unmatched community option shows a generic recovery warning without raw ids`

Convert every v1 inherited/read-only test into a v2 assertion; do not merely delete coverage.

**Step 3: Prove RED**

```bash
node --test --test-name-pattern='embellishment cap|enchant replacement|no inherited|unmatched community' tests/builds-page.test.js
```

**Step 4: Implement product semantics**

- For embellishments, disable an unselected option only when its slot is empty and global used count is already at max. Occupied-slot alternatives remain enabled; selected options remain removable.
- Enchant and embellishment selection replace their single value rather than append.
- Delete `inheritedEnhancementCountByType`, `withInheritedEnhancementCount`, `inheritedEnhancementTypeRows`, `inheritedEnhancementRowsBySlot`, sheet inherited fields, WXML inherited block, and corresponding WXSS.
- Delete inherited-only replacement plumbing (`communityReplacementBindingForPage`, replacement targets, and unresolved-after-replacement logic) after equivalent generic import/fencing coverage is green.
- Unknown raw values stay internal for telemetry only; they do not affect counts, controls, Intent, Profile, or WXML. Show generic copy such as `部分宝石、附魔或美化未能识别，已留空，请重新选择。`

**Step 5: Prove GREEN and commit**

```bash
node --test --test-name-pattern='embellishment cap|enchant replacement|no inherited|unmatched community' tests/builds-page.test.js
git add pages/builds/detail.js pages/builds/detail.wxml pages/builds/detail.wxss tests/builds-page.test.js
git commit -m 'fix: make imported enhancements normally editable'
```

## Task 10: Recompute changed gear slots and close all stale-response races

**Files:**

- Modify: `pages/builds/detail.js`
- Modify: `tests/builds-page.test.js`

**Step 1: Write gear-replacement RED tests**

Add:

- `gear replacement clears enhancements only for the changed item instance before Resolve`
- `gear variant replacement clears the changed slot even when item id is unchanged`
- `two-socket ring to one-socket ring recomputes canonical gem max and leaves no stale second gem`
- `gear replacement preserves enhancements on untouched slots`
- `canonical snapshot capability overrides frontend fallback slot assumptions`

**Step 2: Write fencing RED tests**

Add/update:

- `older verified enhancement Resolve cannot commit over a newer draft`
- `older community import Resolve cannot commit over a newer import`
- `slower slot hydration cannot overwrite the selected template`
- `spec change invalidates pending enhancement commit`
- `double confirm sends one active enhancement commit`

**Step 3: Prove RED**

```bash
node --test --test-name-pattern='gear replacement|two-socket ring|older verified enhancement|older community import|slower slot hydration|spec change invalidates|double confirm' tests/builds-page.test.js
```

**Step 4: Implement exact-instance clearing and fencing**

Add `gearInstanceIdentity(item)`, `changedGearSlots(before, after)`, and `enhancementBySlotWithoutChangedGear(enhancement, slots)`. Include variant identity and weapon-rule removal of off-hand. Clear only changed slots before Resolve; after verification, commit only canonical selected options/capacity.

Every commit must satisfy existing accepted Resolve fencing, current community-import serial when applicable, and current `gearSelectionKey`. Spec/reset/saved-template/new-community-import invalidates the pending editor context. `submitting` blocks double confirm. Canonical constraints must override frontend fallback slot tables.

**Step 5: Prove GREEN and commit**

```bash
node --test --test-name-pattern='gear replacement|two-socket ring|older verified enhancement|older community import|slower slot hydration|spec change invalidates|double confirm' tests/builds-page.test.js
git add pages/builds/detail.js tests/builds-page.test.js
git commit -m 'fix: fence enhancement edits across gear changes'
```

## Task 11: Lock the complete Mage case and cross-layer parity

**Files:**

- Modify: `tests/builds-page.test.js`
- Modify: `tests/gear-workbench-state.test.js`
- Modify: `tests/pg_gear_authority_loader_test.py`
- Modify: `tests/gear_resolver_test.py`
- Modify: `tests/websim_payload_test.py`
- Modify: `tests/raiderio_payload_test.py`
- Modify: `tests/fixtures/midnight-mage-frost-socket-evidence-v1.json`

**Step 1: Add the full integration tests**

Frontend names:

- `mage frost observed community template imports editable 8 of 8 gems 6 of 8 enchants and 2 of 2 embellishments`
- `mage frost imported enhancements remain identical across panel sheet Resolve and Profile intent`
- `mage frost full-cap edits remain editable after close reopen and save reapply`

Backend assertions:

- exact capacities remain `[1,2,1,1,2,1]`;
- eight ordered canonical gem occurrences are accepted, ninth blocked;
- six canonical enchants and two canonical embellishments survive Resolve/Profile without raw client trust;
- duplicate gem occurrence order is retained.

Add cross-class samples for every armor type plus dual-wield/off-hand. They may reuse existing fixtures but must prove no slot-wide socket generalization.

**Step 2: Prove RED, then implement only missing integration glue**

```bash
node --test --test-name-pattern='mage frost' tests/gear-workbench-state.test.js tests/builds-page.test.js
python3 -m unittest tests.raiderio_payload_test tests.pg_gear_authority_loader_test tests.gear_resolver_test tests.websim_payload_test
```

Expected RED cause must be recorded. Do not weaken exact fixture values to make the test pass.

**Step 3: Prove the complete targeted matrix**

```bash
node --test tests/gear-workbench-state.test.js tests/builds-page.test.js
python3 -m unittest tests.raiderio_payload_test tests.gear_socket_authority_test tests.gear_release_tool_test tests.gear_release_refresh_test tests.gear_contracts_test tests.gear_release_store_test tests.gear_runtime_test tests.pg_gear_authority_loader_test tests.gear_resolver_test tests.gear_rule_matrix_test tests.websim_payload_test
```

**Step 4: Commit**

```bash
git status --short
git add tests/builds-page.test.js tests/gear-workbench-state.test.js tests/raiderio_payload_test.py tests/pg_gear_authority_loader_test.py tests/gear_resolver_test.py tests/websim_payload_test.py tests/fixtures/midnight-mage-frost-socket-evidence-v1.json
git commit -m 'test: lock editable mage enhancement parity'
```

If integration glue changed a production file during this task, add that exact file explicitly after inspecting `git status --short`; never stage a directory or unrelated work.

## Task 12: Run local CR, full verification, and promote evidence to `local_verified`

**Files:**

- Modify: `artifacts/releases/2026-07-14-community-enhancement-editability/evidence.json`
- Regenerate: `artifacts/releases/2026-07-14-community-enhancement-editability/manifest.json`
- Modify if current truth changed: `docs/roadmap.md`, `docs/project-state.json`

**Step 1: Inspect the whole branch diff against its base**

```bash
git status --short --branch
git diff --stat origin/main...HEAD
git diff origin/main...HEAD -- server pages/builds tests docs artifacts/releases/2026-07-14-community-enhancement-editability
git diff origin/main...HEAD --check
```

Local CR must explicitly look for: max-vs-sum errors, item-to-slot generalization, request-time external work, v2-only reader outage, missing revision identity, raw value entering Intent, Set/dedupe/filter loss of duplicate gems, pre-Resolve UI commit, selected option disabled at capacity, stale request commit, broad SQL/write/sync scope, and inherited product copy.

**Step 2: Run profiles**

```bash
node scripts/verify-project.js --profile frontend --release artifacts/releases/2026-07-14-community-enhancement-editability --base origin/main
node scripts/verify-project.js --profile backend --release artifacts/releases/2026-07-14-community-enhancement-editability --base origin/main
node scripts/verify-project.js --profile full --release artifacts/releases/2026-07-14-community-enhancement-editability --base origin/main
```

Fix valid findings TDD-first and rerun the affected focused tests plus full profile.

**Step 3: Update evidence truthfully**

Set evidence to `local_verified`, record exact command counts/results and current implementation commit/tree, keep candidate/real-WeChat items `not_run`, and retain open runtime risks.

Regenerate and check:

```bash
node scripts/project-harness.js --write --date 2026-07-14 --slug community-enhancement-editability --requirement-file artifacts/releases/2026-07-14-community-enhancement-editability/requirement.json --evidence-file artifacts/releases/2026-07-14-community-enhancement-editability/evidence.json
node scripts/project-harness.js --check --requirement-file artifacts/releases/2026-07-14-community-enhancement-editability/requirement.json --evidence-file artifacts/releases/2026-07-14-community-enhancement-editability/evidence.json --base origin/main
git diff --check
```

**Step 4: Commit and publish a draft PR**

```bash
git add artifacts/releases/2026-07-14-community-enhancement-editability docs/project-state.json docs/roadmap.md
git commit -m 'docs: record local enhancement v2 evidence'
git push -u origin codex/fix-community-enhancement-editability
```

Create/update a draft PR. Do not mark ready and do not merge.

## Task 13: Deploy the compatible reader, build inactive v2 releases, and shadow before cutover

**Files/evidence:**

- Runtime files changed by Tasks 1–11
- Existing `server/deploy_lighthouse.sh`
- Existing `server/gear_release_refresh.py`
- Existing `server/gear_release_tool.py`
- Modify: `artifacts/releases/2026-07-14-community-enhancement-editability/evidence.json`

**Step 1: Freeze candidate identities and rollback**

Record two immutable code identities: the Task 3 compatibility-reader commit/tree and the final feature candidate commit/tree. Also record changed runtime file hashes, active Manifest revision/generation, active Gear/Community Release IDs, SimC runtime revision, services/timers/locks, and a checksummed remote backup. If the talent-link branch remains unmerged, build detached isolated composite candidates; do not modify the root talent branch and do not deploy clean main over it.

**Step 2: Deploy the exact Task 3 compatibility-reader commit**

Create a detached worktree/build at the exact Task 3 commit, not final feature HEAD. Use the established candidate path with:

```bash
WOW_DEPLOY_SKIP_BOOTSTRAP=1 WOW_DEPLOY_START_ASYNC_SYNCS=0 ./server/deploy_lighthouse.sh
```

Prove runtime SHA parity and that the existing active v1 Manifest returns the same health, initial, Resolve, Profile, dependency-vector and signature facts. Do not run release refresh until this compatibility smoke passes. Remove this temporary reader-only worktree after its evidence is archived.

**Step 3: Deploy the final feature candidate while v1 remains active**

Deploy the final candidate with the same async-off command. Prove its exact runtime parity and repeat the v1 API/read-model smoke. The explicit v1 branches in loader/store code must keep the active pointer readable; any outage or v1 API regression blocks v2 release generation and rolls code back. This step does not claim v2 WeChat behavior because the v2 pointer is not active yet.

**Step 4: Generate inactive v2 candidates**

Run the existing refresh under its production environment/lock with an explicit operator identity:

```bash
python3 server/gear_release_refresh.py --json --updated-by candidate-community-enhancement-v2
```

Record SimC revision, socket-probe digest, new Gear Release ID, Community Release ID, candidate Manifest revision, risk classification, and active pointer before/after. Expected: `manual_required`/capability change, active pointer unchanged.

**Step 5: Run 40-spec shadow and exact negative checks**

Use the new inactive release IDs:

```bash
python3 server/gear_release_tool.py shadow --gear-release-id <GEAR_RELEASE_ID> --community-release-id <COMMUNITY_RELEASE_ID> --simc-runtime-revision <SIMC_REVISION> --level 90
```

Require 40 observed winners, baseline 0, no new blockers, no write statements, and existing honest Profile outcomes (32 verified and 8 explicit fail-closed unless current production truth has changed). Freeze the reference tuple for `observed_profile_mage_frost`: `templateId`, `sourceKey=raiderio_observed_profile`, `profileHash`, `gearHash`, Gear Release ID, Community Release ID and candidate Manifest revision. Only this tuple carries the fixed Mage `[1,2,1,1,2,1]`, 8/8 accepted, ninth gem blocked, 6/8 and 2/2 acceptance. Other Mage templates require complete editable import but may have different counts.

**Step 6: Manual CAS cutover**

Only after shadow pass, use the existing `promote` command with the captured expected generation and rollback Manifest revision. Immediately prove the pointer generation/revisions and API identity. Any probe, materialization, signature, shadow, or smoke failure leaves the old pointer active.

**Step 7: Pointer-first rollback drill**

Verify the exact rollback command can CAS the pointer back to the previous v1 Manifest. Do not execute a destructive data restore unless pointer rollback or reader rollback actually requires it.

## Task 14: Real WeChat acceptance, final evidence, merge, and post-merge smoke

**Files:**

- Modify: `artifacts/releases/2026-07-14-community-enhancement-editability/evidence.json`
- Regenerate: `artifacts/releases/2026-07-14-community-enhancement-editability/manifest.json`
- Modify: `docs/roadmap.md`
- Modify: `docs/project-state.json` only when lifecycle status changes

**Step 1: Open the exact clean candidate project in WeChat DevTools**

Compile from the exact candidate/composite worktree, not the root development branch. Capture candidate signature/commit in the evidence.

**Step 2: Run the user matrix**

At minimum verify:

- import the exact candidate-frozen `observed_profile_mage_frost` tuple and verify its sourceKey, profileHash, gearHash and release IDs first;
- for that exact tuple, panel and sheet show 15/15 gear, gems 8/8, enchants 6/8, embellishments 2/2;
- no inherited/non-editable copy;
- all selected controls are operable;
- replace one gem at 8/8, including one duplicate occurrence, and remain 8/8;
- replace one enchant and remain 6/8;
- replace one occupied embellishment and remain 2/2; empty third slot stays blocked;
- close discards an unconfirmed draft;
- blocked/offline attempt keeps the old verified state;
- two-socket/one-socket gear replacement recalculates without stale gems;
- reopen and saved-template round trip preserve canonical order.

Then sample at least one other active Mage community template, if one exists. It must import completely and remain editable, but it is not required to match the fixed reference counts.

**Step 3: Run production operations smoke**

Verify `/health`, `/api/data/health`, initial/slot/Resolve/Profile, runtime file parity, backend/worker/nginx state, `NRestarts`, failed units, error-priority logs, all existing timers, sync services inactive after candidate work, shared lock free, and no deploy-triggered async backflow.

**Step 4: Promote evidence honestly**

If candidate/API/operations and real WeChat all pass, set evidence to `live_verified`; otherwise leave it at the highest proven level and keep merge blocked. Include screenshots, release identities, pointer generation, rollback target, runtime hashes, timer/log state, and known residual risks.

Regenerate the manifest and rerun full/Harness checks:

```bash
node scripts/project-harness.js --write --date 2026-07-14 --slug community-enhancement-editability --requirement-file artifacts/releases/2026-07-14-community-enhancement-editability/requirement.json --evidence-file artifacts/releases/2026-07-14-community-enhancement-editability/evidence.json
node scripts/project-harness.js --check --requirement-file artifacts/releases/2026-07-14-community-enhancement-editability/requirement.json --evidence-file artifacts/releases/2026-07-14-community-enhancement-editability/evidence.json --base origin/main
node scripts/verify-project.js --profile full --release artifacts/releases/2026-07-14-community-enhancement-editability --base origin/main
git diff --check
```

**Step 5: Final local CR, ready PR, merge, and clean-main proof**

Update the draft PR with exact evidence, wait for CI, mark ready only after no blocker remains, then merge the approved gear fix first. If talent work still exists, merge updated main into its isolated branch and prove final-tree parity before that separate merge. After this feature merges, run clean-main runtime/API/operations smoke and archive the v2 packet; do not delete v1 historical evidence.

---

## Completion definition

Completion requires all of the following, not merely green unit tests:

- static v2 socket facts are release-materialized and request-time external fetch is absent;
- v1/v2 rollout and pointer rollback are proven;
- Mage exact capacity is `[1,2,1,1,2,1]` and 8/8/6/8/2/2 is canonical;
- all imported enhancements are editable with occurrence-safe full-cap replacement;
- raw/unmatched values never become trusted Intent or user-facing inherited facts;
- blocked/offline/stale Resolve cannot pollute committed state;
- frontend/backend/full Harness, local CR, candidate deployment, 40-spec shadow, real WeChat, timer/log/backflow, rollback, CI, and post-merge smoke all have recorded evidence.
