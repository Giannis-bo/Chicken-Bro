# Community Template Enhancement Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import evidence-backed community-template gems, enchants, and embellishments into the canonical equipment workbench, while keeping unmatched observed facts visible and non-editable.

**Architecture:** PostgreSQL Gear Authority derives truthful enhancement capabilities from verified item metadata plus exact verified variant facts. The mini-program hydrates only affected slot details, reconciles raw observed values to verified option identities, submits only identities through Selection Intent, and renders counts and editor state from the matching canonical Resolve snapshot. Unmatched values live in a separate read-only import-evidence state and never enter Selection Intent.

**Tech Stack:** Python 3 `unittest`, Node.js `node:test`, CommonJS WeChat mini-program page modules, PostgreSQL Gear Authority Context, canonical gear resolver.

## Global Constraints

- Follow test-driven development: add one focused failing test, run it and confirm the expected failure, then implement the minimum production change.
- Never synthesize an option identity from a raw `gem_id`, `enchant_id`, or `embellishment` value.
- Never place unmatched raw values in Selection Intent; retain them only in read-only `communityEnhancementImportState`.
- Keep the backend as the final capability, legality, and SimC serialization authority.
- Preserve lazy slot-detail loading and stale-request guards.
- Do not regenerate Gear Releases or write production data unless code-only candidate proof shows it is necessary and the step is explicitly recorded.
- Keep `WOW_DEPLOY_START_ASYNC_SYNCS=0` for candidate deployment.

---

### Task 1: Project authoritative item and exact-variant enhancement capabilities

**Files:**
- Modify: `tests/pg_gear_authority_loader_test.py`
- Modify: `tests/gear_resolver_test.py`
- Modify: `server/pg_gear_authority_loader.py`

- [x] Add `test_item_capabilities_are_derived_from_verified_metadata` with a verified finger item whose payload contains authoritative slot/type/socket metadata but no pre-materialized `baseCapabilities`; assert projected `socketCount`, `canEnchant`, and the corresponding Resolve constraints are non-zero/true.
- [x] Run `python3 -m unittest tests.pg_gear_authority_loader_test.PgGearAuthorityLoaderTest.test_item_capabilities_are_derived_from_verified_metadata` and confirm it fails because `_project_item` currently defaults the fields to zero/false.
- [x] Import `item_mod_capabilities` from `server.websim_payload` and add `_project_base_capabilities(payload, canonical_slot, type_metadata)` that merges derived capability facts with explicit verified payload fields without allowing a false client default to erase a derived true fact:

```python
derived = item_mod_capabilities(
    payload=payload,
    slot=canonical_slot,
    item={"slot": canonical_slot, **type_metadata},
)
socket_count = max(_non_negative_int(explicit.get("socketCount")), _non_negative_int(derived.get("socketCount")))
return {
    **explicit,
    "socketCount": socket_count,
    "canEnchant": explicit.get("canEnchant") is True or derived.get("canEnchant") is True,
    "canEmbellish": explicit.get("canEmbellish") is True or derived.get("canEmbellish") is True,
}
```

- [x] Add `test_exact_verified_variant_gems_raise_only_variant_socket_capacity` and assert a verified variant with `simcOptions.gem_id = "240892/240900"` receives `capabilityOverrides.socketCount == 2`, while the base item and a second variant without the evidence remain unchanged.
- [x] Run the new variant test and confirm it fails before implementation.
- [x] Add `_variant_capability_overrides(payload, simc_options)` that merges verified explicit overrides and raises only exact-variant capabilities proven by its stored `simcOptions`: ordered gem-token count may raise `socketCount`; `embellishment`/`crafted_stats` may set `canEmbellish`; raw enchant does not expand option applicability.
- [x] Add/extend a resolver test that asserts constraints use the exact variant override while an unselected or forged raw option remains unavailable.
- [x] Run `python3 -m unittest tests.pg_gear_authority_loader_test tests.gear_resolver_test` and expect all tests to pass.
- [x] Commit: `fix: derive canonical enhancement capabilities`

### Task 2: Make multiple gem option identities first-class frontend state

**Files:**
- Modify: `tests/builds-page.test.js`
- Modify: `pages/builds/detail.js`

- [x] Replace the old regression expectation `gear community template import ignores raw embedded SimC enhancements without option identities` with a lower-level failing test proving normalized records preserve ordered `gemOptionIds` and legacy `socketOptionId` remains readable.
- [x] Run `node --test --test-name-pattern="multiple gem option identities" tests/builds-page.test.js` and confirm it fails because `normalizedEnhancementBySlot` currently drops `gemOptionIds`.
- [x] Add `normalizedOptionIdentityList(value)` and update `normalizedEnhancementBySlot`, `optionIdentityEnhancementBySlot`, `enhancementRecordSelectedCount`, and `compactEnhancementRecord` to preserve ordered, multiplicity-bearing `gemOptionIds` (two identical identities represent two occupied sockets):

```js
function normalizedOptionIdentityList(value) {
  return (Array.isArray(value) ? value : [])
    .map(cleanGearString)
    .filter(Boolean)
}
```

- [x] Update `enhancementOptionSelected`, `enhancementSelectionFromOption`, `removeEnhancementType`, `prunedEnhancementBySlot`, and gem toggle behavior so selecting one gem toggles only that identity, preserves other gems, and never exceeds the slot's canonical `socketCount`.
- [x] Add failing-then-passing tests for two selected gems, one-gem removal, legacy scalar compatibility, and capacity overflow producing a blocker instead of silent truncation.
- [x] Run `node --test --test-name-pattern="gem option|community template" tests/builds-page.test.js` and expect all matching tests to pass.
- [x] Commit: `fix: support canonical multi-gem selections`

### Task 3: Reconcile community-template raw facts to verified option identities

**Files:**
- Modify: `tests/builds-page.test.js`
- Modify: `pages/builds/detail.js`

- [x] Add a failing integration test using a community template whose gear items contain `gem_id = "240892/240900"`, `enchant_id = "7967"`, and `embellishment = "arcanoweave_lining"`; provide slot-detail options with stable `optionKey`, visible/readable labels, exact `simcOptions`, and assert the Resolve request contains ordered `gemOptionIds`, `enchantOptionId`, and `embellishmentOptionId`.
- [x] Run `node --test --test-name-pattern="reconciles observed enhancements" tests/builds-page.test.js` and confirm the Resolve request currently contains no enhancement identities.
- [x] Add `communityTemplateRawEnhancementBySlot(template)` to merge explicit template facts with raw gear-item facts, using `simcOptionTokens(value)` for slash/comma/space-separated gems.
- [x] Add `communityEnhancementAffectedSlots(template)` and `loadCommunityTemplateEnhancementDetails(page, template)`; fetch only affected slots where `gearPayloadNeedsSlotDetail(page, slot)` is true, reuse `loadGearSlotDetailForPage`, and convert each failure into unresolved evidence instead of rejecting the whole import.
- [x] Add `reconcileCommunityTemplateEnhancements(gearPayload, selectedGearBySlot, rawBySlot)` returning exactly:

```js
{
  enhancementBySlot: {
    finger1: { gemOptionIds: ['gem-240892', 'gem-240900'], enchantOptionId: 'ring-enchant-7967' }
  },
  unresolvedBySlot: {
    back: { gemIds: [], enchantIds: [], embellishments: ['arcanoweave_lining'], readOnly: true }
  },
  warnings: ['1 个槽位的社区强化缺少当前可编辑证据，已按只读事实保留。']
}
```

- [x] Require exact normalized SimC-value match, stable option identity, visible/readable display evidence, and current slot/item applicability. Never fall back to using raw value as option identity.
- [x] Change `applyGearCommunityTemplate` to await weapon-repair details and affected enhancement details, reconcile once against the latest payload, set import evidence state with an import serial, and call Resolve with identities only.
- [x] Add tests that only affected incomplete slots are requested, complete slots are not re-fetched, and a slot-detail failure still imports gear with an unresolved warning.
- [x] Run `node --test --test-name-pattern="community template" tests/builds-page.test.js` and expect all matching tests to pass.
- [x] Commit: `fix: reconcile observed community enhancements`

### Task 4: Render canonical counts plus read-only inherited facts

**Files:**
- Modify: `tests/builds-page.test.js`
- Modify: `pages/builds/detail.js`
- Modify: `pages/builds/detail.wxml`
- Modify: `pages/builds/detail.wxss`

- [x] Add a failing page test asserting a successful canonical snapshot with two resolved gem identities, one enchant identity, one embellishment identity, and truthful constraints renders non-zero summary counts and selected editor options.
- [x] Add a failing page/WXML test asserting an unmatched inherited fact keeps its equipment slot in `gearEnhancementSheet.equipmentRows`, sets `activeInheritedRows`, and displays `已继承，当前目录不可编辑` without exposing a forged selectable button.
- [x] Run the two focused tests and confirm counts/rows are currently missing.
- [x] Define page state:

```js
communityEnhancementImportState: {
  templateId: '',
  serial: 0,
  resolvedGearSignature: '',
  unresolvedBySlot: {},
  warnings: []
}
```

- [x] Bind the state to the successful matching Resolve snapshot only. Clear it on reset, saved-template import, spec change, and a newer community import; ignore stale Resolve responses whose import serial/signature no longer matches.
- [x] Keep `canonicalGearAttributePanel` counts based only on `resolvedSlots[*].selectedOptions`; merge unresolved facts only into a separate `inheritedCount`/warning label so the trusted `used/max` values stay canonical.
- [x] Extend `buildGearEnhancementSheetForPage` to union canonical configurable slots, hydrated option slots, and unresolved inherited slots. Build `activeInheritedRows` with generic Chinese type labels and `readOnly: true`; do not render raw identifiers.
- [x] Add WXML/CSS for the read-only inherited block and ensure the confirm button never serializes it.
- [x] Add tests for closing the sheet discarding draft edits, selecting a verified replacement clearing only that inherited type after successful Resolve, and stale Resolve not clearing newer import evidence.
- [x] Run `node --test tests/builds-page.test.js` and expect all tests to pass.
- [x] Commit: `fix: show inherited enhancement evidence`

### Task 5: Full local verification and local CR

**Files:**
- Modify: `docs/roadmap.md`
- Modify: `docs/superpowers/plans/2026-07-13-community-template-enhancement-import.md`

- [x] Run `python3 -m unittest tests.pg_gear_authority_loader_test tests.gear_resolver_test`.
- [x] Run `node --test tests/builds-page.test.js tests/gear-workbench-state.test.js`.
- [x] Read `docs/harness.md`, run the frontend/backend/full Harness profiles required by the changed paths, and record exact results.
- [x] Run `git diff --check` and inspect `git diff --stat`, `git status --short --branch`, and the complete diff against `origin/main`.
- [x] Perform local CR against the approved design: confirm no raw option trust, no silent gem truncation, no stale response overwrite, no unrelated files, and canonical counts remain snapshot-owned.
- [x] Fix every technically valid finding and rerun affected tests.
- [x] Update the roadmap entry with local evidence and leave runtime status `正在推进` until candidate smoke passes.
- [x] Mark completed plan checkboxes and commit: `docs: record community enhancement verification`

### Task 6: Candidate deployment and live proof

**Files:**
- Modify if required by the deployment runbook: `docs/roadmap.md`

- [x] Record the candidate branch and commit, deployed runtime file hashes/build identity, pre-deploy backup, current service identity, and rollback target.
- [x] Deploy the candidate to the known cloud path with `WOW_DEPLOY_START_ASYNC_SYNCS=0`; do not trigger release regeneration or asynchronous sync.
- [x] Restart only the existing affected services and verify service/log health.
- [x] HTTP smoke `/api/websim/gear?class=mage&spec=frost&compact=1&mode=initial`, affected slot detail endpoints, and `/api/websim/gear/resolve` for `observed_profile_mage_frost`.
- [x] Verify live Resolve returns truthful socket/enchant/embellishment constraints and matched `selectedOptions` without relying on forged raw client values.
- [x] Verify in the real mini-program that community import produces non-zero canonical enhancement counts, matched options are selected, affected slots are listed, and unmatched facts are readable/non-editable.
- [x] Record rollback command/path and candidate evidence in `docs/roadmap.md`, then mark the correction `已完成` only if every smoke passes.
- [x] Commit and push final evidence; prepare the branch/PR handoff without merging unless the user authorizes merge.
