# Manifest Catalog Progression Display Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make equipment detail show backend-owned named progression choices and the exact selected variant's specialization-correct stats, while failing closed on contradictory catalog evidence.

**Architecture:** The Manifest release retains immutable BrowseVariant progression and static facts. The selector/WebSim compact boundary specializes and semantically groups the returned variants: tertiary-only observations collapse deterministically, while a conflicting logical progression becomes one non-selectable public conflict. Taro renders the selected compact variant until canonical Resolve becomes authoritative after Apply.

**Tech Stack:** Python `unittest`, PostgreSQL read-model selector, WebSim compact payload, TypeScript/Vitest, Taro, Harness release packet.

## Global Constraints

- Do not alter Catalog/Gear Release/Manifest pointers, source ingestion, schema, resolver, SimC, TemplateSet, or persisted player data.
- Taro must not derive progression, source identity, primary-stat identity, or static facts.
- A logical progression may collapse only when `itemLevel` and non-tertiary static facts agree. `leech`, `avoidance`, and `speed` are tertiary-only differences; a core-stat or level conflict must remain blocked.
- Resolve remains authoritative after Apply. No download, install, deployment, or catalog rebuild occurs before local verification and a new candidate.

### Task 1: Project immutable progression and primary-stat facts

**Files:**
- Modify: `tests/gear_release_store_test.py:2447`
- Modify: `tests/pg_gear_read_model_selectors_test.py:880`
- Modify: `server/gear_release_store.py:733-801`
- Modify: `server/pg_gear_read_model_selectors.py:825-870`

**Interfaces:** Consumes `BrowseVariant.progressionState`, static facts, class, and spec; produces items/variants with `progressionState` and `primaryStatKey`.

- [x] Write failing tests asserting `hero 6/6` survives release projection and a Frost death knight receives `primaryStatKey == "strength"` on both item and variant.
- [x] Run `python3 -m unittest tests.gear_release_store_test.GearReleaseStoreTest.test_manifest_catalog_snapshot_projects_canonical_browse_membership tests.pg_gear_read_model_selectors_test.PgGearReadModelSelectorsTest.test_manifest_catalog_public_item_uses_verified_static_facts_without_battle_net_diagnostics -v` and require a failure for missing specialization projection.
- [x] Implement only the selector-side call to the existing primary-stat display helper for the candidate and each returned variant; retain release-owned `progressionState` in variant payload.
- [x] Re-run the command and require `OK`.

### Task 2: Compact one safe user choice per progression

**Files:**
- Modify: `tests/websim_payload_test.py`
- Modify: `server/websim_payload.py:23755-24249`

**Interfaces:** Consumes specialized variant stats and `progressionState`; produces `displayProgression`, named labels, one selected key for equivalent observations, or one blocked conflict with safe Chinese copy.

- [x] Write a failing equivalent-observation test: multiple `myth 6/6` rows with identical core facts and tertiary-only differences return one compact row.
- [x] Write a failing conflict test: two `myth 6/6` rows with different item levels/core facts return one blocked row with `该等级轨道的已核验属性存在冲突，暂不可选择`.
- [x] Run `python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_compact_manifest_variants_preserve_named_progression_and_primary_stat tests.websim_payload_test.WebSimPayloadTest.test_compact_manifest_variants_fail_closed_on_conflicting_progression_facts -v` and require both failures.
- [x] Add compact progression display fields and backend grouping at the public boundary; no frontend key/difficulty inference and no arbitrary conflicting source key.
- [x] Re-run the command and require `OK`.

### Task 3: Display the selected compact variant before Apply

**Files:**
- Modify: `apps/mini-taro/src/pages/builds/gear-detail-editor-model.test.ts`
- Modify: `apps/mini-taro/src/pages/builds/gear-detail-editor-model.ts:3-220`
- Modify: `apps/mini-taro/src/pages/builds/gear-detail-model.test.ts:665`
- Modify: `apps/mini-taro/src/pages/builds/gear-detail-model.ts:641-655`
- Modify: `apps/mini-taro/src/pages/builds/detail.tsx:307-312`

**Interfaces:** Consumes selected compact `itemStats`, `statSummary`, `primaryStatKey`, `displayProgression`; produces a display-only local candidate draft that uses the same backend fields.

- [x] Write a failing test that selects `hero-289` and expects `materializeCandidateDraft` to contain its `itemStats`, `primaryStatKey: "strength"`, and `statSummary: "力量 124；急速 108"` rather than the parent summary.
- [x] Run `npm run test:taro -- apps/mini-taro/src/pages/builds/gear-detail-editor-model.test.ts apps/mini-taro/src/pages/builds/gear-detail-model.test.ts` and require failure for missing selected stats.
- [x] Preserve raw selected-variant display fields in the draft and build the active editor detail item from that materialized draft. Do not mutate the source candidate or treat it as post-Resolve equipment truth.
- [x] Re-run the command and require `OK`.

### Task 4: Verify and prepare a single new candidate

**Files:**
- Modify: `artifacts/releases/2026-07-29-manifest-catalog-detail-contract/evidence.json`
- Modify: `artifacts/releases/2026-07-29-manifest-catalog-detail-contract/manifest.json`

- [x] Run focused backend suites and Taro tests: `python3 -m unittest tests.gear_release_store_test tests.pg_gear_read_model_selectors_test tests.websim_payload_test` and `npm run test:taro -- apps/mini-taro/src/pages/builds/gear-detail-editor-model.test.ts apps/mini-taro/src/pages/builds/gear-detail-model.test.ts apps/mini-taro/src/pages/builds/gear-detail-page-contract.test.ts`.
- [x] Run `node scripts/project-harness.js --json --write --date 2026-07-29 --slug manifest-catalog-detail-contract`, `node scripts/project-harness.js --json --check-requirement --requirement-file artifacts/releases/2026-07-29-manifest-catalog-detail-contract/requirement.json`, and `git diff --check`.
- [x] After final runtime commit, deploy the immutable `14078788` candidate and smoke `268283`/`250033` for named progression, no duplicate observed rows, primary and selected-stat changes, safe conflict, runtime identity, timer backflow, and rollback. The active candidate is read-only and no candidate-specific timer exists.
- [ ] Obtain explicit WeChat acceptance for the four release-packet acceptance items before merge.
