# Manifest Catalog Browse Integrity and Detail Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make equipment detail consume a Catalog where only verified BrowseVariants are selectable, normal tracks publish only their maximum rank, and type-unknown armor never leaks across classes.

**Architecture:** The Manifest release remains the public reader, but the Catalog Builder becomes the membership boundary: `exact_instance` rows remain Exact Registry inputs and cannot seed BrowseVariants. A v3 BrowseVariant identity is `(catalogRevision, itemId, progressionState)` with one non-crafted source shape; a type-unknown armor or weapon item is explicitly excluded from candidate Browse membership and independently hidden by the legacy/WebSim read boundary until a later governed source repair supplies the missing type fact. Taro continues to render only backend-returned compact facts until canonical Resolve becomes authoritative after Apply. A sealed Exact-only import may be recovered through the matching Exact Registry and existing Resolver/ResolvedLoadout/SimC contracts, but this task must not change Resolver selection or legality rules, SimC compiler semantics, or publish the Exact instance as a Browse choice.

**Tech Stack:** Python `unittest`, PostgreSQL read-model selector, WebSim compact payload, TypeScript/Vitest, Taro, Harness release packet.

## Global Constraints

- Build and seal only a dormant Catalog v3 / Exact Registry candidate first; do not switch the active Manifest pointer, alter source ingestion, Resolver selection/legality rules, SimC compiler semantics, TemplateSet, or persisted player data before the full candidate matrix and explicit user acceptance.
- `exact_instance` rows may remain exact evidence inputs where Track Authority explicitly permits them, but they must never create, extend, or select a public BrowseVariant.
- A normal `upgrade_track` BrowseVariant must be the bound maximum rank. A second logical state with different item level or core facts blocks the candidate Catalog; it must never be compacted by choosing one shape.
- For non-portable armor and weapon slots, missing type facts are an explicit Catalog exclusion and public read-model hide condition. No metadata fetch, sync, backfill, or external download is part of this repair.
- Taro must not derive progression, source identity, primary-stat identity, or static facts.
- A logical progression may collapse only when `itemLevel` and non-tertiary static facts agree. `leech`, `avoidance`, and `speed` are tertiary-only differences; a core-stat or level conflict must remain blocked.
- Resolve remains authoritative after Apply. No download, install, source sync, active-pointer switch, or production deployment occurs before local verification and one new immutable candidate.

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

### Task 4: Verify and prepare the superseded presentation candidate

**Files:**
- Modify: `artifacts/releases/2026-07-29-manifest-catalog-detail-contract/evidence.json`
- Modify: `artifacts/releases/2026-07-29-manifest-catalog-detail-contract/manifest.json`

- [x] Run focused backend suites and Taro tests: `python3 -m unittest tests.gear_release_store_test tests.pg_gear_read_model_selectors_test tests.websim_payload_test` and `npm run test:taro -- apps/mini-taro/src/pages/builds/gear-detail-editor-model.test.ts apps/mini-taro/src/pages/builds/gear-detail-model.test.ts apps/mini-taro/src/pages/builds/gear-detail-page-contract.test.ts`.
- [x] Run `node scripts/project-harness.js --json --write --date 2026-07-29 --slug manifest-catalog-detail-contract`, `node scripts/project-harness.js --json --check-requirement --requirement-file artifacts/releases/2026-07-29-manifest-catalog-detail-contract/requirement.json`, and `git diff --check`.
- [x] The immutable `14078788` candidate was deployed and inspected. Its Frost death knight presentation smoke passed, but the later Mage audit proved the underlying Catalog still leaked ExactItemInstances and unverified equipment types; it is superseded and cannot receive manual acceptance.
- [ ] Obtain explicit WeChat acceptance for the six final release-packet acceptance items from Task 8 before merge.

### Task 5: Restore Catalog-only Browse membership and state identity

**Files:**
- Modify: `tests/gear_catalog_revision_test.py:217-540`
- Modify: `server/gear_catalog_revision.py:30-220,430-940,990-1085`

**Interfaces:** Consumes a sealed Gear Release snapshot whose variant rows are classified as `browse` or `exact_instance`. Produces a Catalog v3 where every `browseVariantKey` derives only from `(catalogRevision, itemId, progressionState)`, every normal track is its governed max rank, `sourceFamilies == ["browse"]`, and each exact row remains outside `browseVariants`.

- [x] **Step 1: Write failing regression tests**

```python
def test_exact_instances_do_not_create_or_extend_browse_variants(self):
    rows = regular_rows()
    rows["variants"].append(verified_exact_row("1001", item_level=276))
    result = build_catalog_revision(CURRENT_BINDING, rows)
    self.assertEqual(result["status"], "verified")
    self.assertEqual(len(result["browseVariants"]), 1)
    self.assertEqual(result["browseVariants"][0]["sourceFamilies"], ["browse"])
    self.assertEqual(result["contentSummary"]["exactDerivedVariantCount"], 0)

def test_duplicate_normal_progression_with_a_second_shape_blocks_catalog(self):
    rows = regular_rows()
    rows["variants"].append({**rows["variants"][0], "variantKey": "hero-other", "staticStats": {"haste_rating": 121}})
    result = build_catalog_revision(CURRENT_BINDING, rows)
    self.assertEqual(result["status"], "blocked")
    self.assertIn("CATALOG_VARIANT_CANONICAL_DUPLICATE", result["problemCodes"])
```

- [x] **Step 2: Run the two focused tests and verify RED**

Run: `python3 -m unittest tests.gear_catalog_revision_test.GearCatalogRevisionTest.test_exact_instances_do_not_create_or_extend_browse_variants tests.gear_catalog_revision_test.GearCatalogRevisionTest.test_duplicate_normal_progression_with_a_second_shape_blocks_catalog -v`

Observed: exact-instance leakage and v2 shape identity failed RED. The pre-existing mapping audit already blocked the second-shape fixture; it remains an independent retained guard.

- [x] **Step 3: Implement the smallest Catalog v3 boundary**

```python
# candidate_rows is populated exclusively by rowFamily == "browse".
# Exact rows are counted for Exact Registry/audit provenance but never added.
identity = {
    "catalogRevision": catalog_revision,
    "itemId": item_id,
    "progressionState": progression_state,
}
```

Set `CATALOG_SCHEMA_REVISION` and `CATALOG_BUILDER_REVISION` to v3, retain v1/v2 verification only for archived reads, and make the v3 verifier reject duplicate `(itemId, progressionState)` identities before any seal. Do not add a migration: the existing primary key protects the v3 key, while immutable v2 historical rows remain readable.

- [x] **Step 4: Run the focused tests and verify GREEN**

Run: `python3 -m unittest tests.gear_catalog_revision_test -v`

Expected: all Catalog revision tests pass, including the replacement tests for the retired exact-to-Browse behavior.

- [x] **Step 5: Commit the Builder boundary**

```bash
git add server/gear_catalog_revision.py tests/gear_catalog_revision_test.py
git commit -m "fix: keep exact instances out of catalog browse variants"
```

Committed as `9d9ab597`; the follow-up type-membership exclusion is in `3fc97f21`.

### Task 6: Fail closed on unverified equipment eligibility at the public read boundary

**Files:**
- Modify: `tests/websim_payload_test.py:8288-8445,12320-12335`
- Modify: `server/websim_payload.py:17354-17560,17765-17835`

**Interfaces:** Consumes normalized item type facts plus source/variant class context. Produces only `compatibility.status == "compatible"` candidates for non-portable equipment slots; a missing armor/weapon type or a class-ambiguous tier source is absent from the selectable public catalog, while portable universal slots remain available.

- [x] **Step 1: Write failing public-boundary tests**

```python
def test_websim_gear_hides_nonportable_catalog_item_without_verified_armor_type(self):
    item = catalog_item(slot="head", armor_type="", class_keys=["mage"])
    self.assertIsNone(enrich_catalog_item(item, mage_sources, mage_variants, [], [], [], "mage", "frost"))

def test_catalog_keeps_portable_ring_without_armor_type(self):
    item = catalog_item(slot="finger1", armor_type="")
    self.assertIsNotNone(enrich_catalog_item(item, sources, variants, [], [], [], "mage", "frost"))
```

Add a third regression for a `tier_set` source with no verified class context: it must not become a cross-class candidate merely because the armor type is otherwise valid.

- [x] **Step 2: Run the focused tests and verify RED**

Run: `python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_websim_gear_hides_nonportable_catalog_item_without_verified_armor_type tests.websim_payload_test.WebSimPayloadTest.test_catalog_keeps_portable_ring_without_armor_type tests.websim_payload_test.WebSimPayloadTest.test_catalog_context_requires_verified_class_for_tier_set -v`

Observed: the unknown-type head and context-free tier source failed RED; the portable ring was already green, preserving its intended exception.

- [x] **Step 3: Implement the narrow compatibility gate**

```python
compatibility = catalog_compatibility(item, sources, variants, class_key, spec_key)
if compatibility["status"] != "compatible":
    return None
```

Make `catalog_compatibility` return `unknown` (not falsely `incompatible`) for an armor/weapon slot without its governing type fact, and make `catalog_context_compatible` reject context-free `tier_set` rows. Keep portable slots and explicitly compatible raid/dungeon equipment behavior unchanged. Do not turn missing metadata into a player-facing Battle.net error; the candidate is simply absent.

- [x] **Step 4: Run focused and neighboring regressions**

Run: `python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_websim_gear_filters_localized_non_class_armor_catalog_candidates tests.websim_payload_test.WebSimPayloadTest.test_websim_gear_filters_verified_loot_candidates_outside_active_season_instances tests.websim_payload_test.WebSimPayloadTest.test_catalog_context_allows_same_class_observed_armor_across_specs -v`

Expected: known cloth/mage and portable behavior remain, while known leather/mail and type-unknown armor are absent.

- [x] **Step 5: Commit the public eligibility boundary**

```bash
git add server/websim_payload.py tests/websim_payload_test.py
git commit -m "fix: hide catalog candidates without verified equipment eligibility"
```

Committed as `3fc97f21`, followed by `417e5691` to make projected Catalog type facts participate in the same compatibility rule and retain valid governed controls.

### Task 7: Seal a dormant Catalog v3 and validate its dependency chain

**Files:**
- Modify: `artifacts/releases/2026-07-29-manifest-catalog-detail-contract/requirement.json`
- Modify: `artifacts/releases/2026-07-29-manifest-catalog-detail-contract/evidence.json`
- Modify: `artifacts/releases/2026-07-29-manifest-catalog-detail-contract/manifest.json`

**Interfaces:** Consumes the existing active Gear Release as immutable input. Produces one dormant Catalog v3 and matching Exact Registry candidate, or a literal blocked audit with no active-pointer change.

- [x] **Step 1: Run the local Builder/authority suites**

Run: `python3 -m unittest tests.gear_track_authority_test tests.gear_catalog_migration_audit_test tests.gear_catalog_revision_test tests.gear_catalog_revision_store_test tests.gear_exact_item_registry_test -v`

Expected: `OK`; no database write or active-pointer mutation occurs in these tests.

- [x] **Step 2: Run the read-only candidate-source audit**

Run: `GET /api/websim/gear?class=mage&spec=frost&mode=slot&slot=head` against the immutable candidate and record the 250033/268283 raw variants, type status, and any normal-track state collision in the evidence packet.

Observed: compact read-only audit of superseded `14078788` showed `250033` and `268283` with `armorType: null` and compatibility `compatible`; it also exposed public Myth 2/6 and a blocked Myth 6/6 conflict. No source sync, backfill, or pointer command ran.

- [x] **Step 3: Seal and shadow-check only the dormant revisions**

Run: `WOW_DATABASE_RUNTIME=postgres_only python3 scripts/gear-catalog-revision.py --output <candidate-report>` followed by `WOW_DATABASE_RUNTIME=postgres_only python3 scripts/gear-exact-item-instance.py --output <candidate-report>` in the isolated candidate environment.

Observed: the first v3 builder shadow correctly blocked because it did not project existing official BNet `item_class` / `item_subclass` facts. `da051891` adds that projection through the existing normalizer. Its builder-v4 Catalog `4c85363…bd9f68ed` passes all 40 specs with zero unmapped/aliased candidates; matching Exact Registry `cadc4f…305082` is deterministic and explicitly `partial` only for 55 `ENHANCEMENT_SINGLE_VALUE_MALFORMED` references. The active pointer remained generation 35 throughout.

- [x] **Step 4: Regenerate and verify the same task packet**

Run: `node scripts/project-harness.js --json --write --date 2026-07-29 --slug manifest-catalog-detail-contract --requirement-file artifacts/releases/2026-07-29-manifest-catalog-detail-contract/requirement.json --evidence-file artifacts/releases/2026-07-29-manifest-catalog-detail-contract/evidence.json`

Expected: one task-scoped packet records the superseded `14078788` candidate and the new candidate as pending; no second packet is introduced on this branch.

Observed: the same packet was regenerated and the complete Harness check passed with the final candidate recorded as `preview_verified`, runtime identity bound to `da051891`, and manual acceptance still pending.

### Task 8: Deploy one final immutable Catalog candidate and obtain WeChat evidence

**Files:**
- Modify: `artifacts/releases/2026-07-29-manifest-catalog-detail-contract/evidence.json`
- Modify: `artifacts/releases/2026-07-29-manifest-catalog-detail-contract/manifest.json`

**Interfaces:** Consumes the final committed runtime head and dormant candidate dependency vector. Produces a candidate-only public API and WeChat build bound to one commit, one Catalog v3, and one Manifest dependency vector; active production remains on the prior Manifest until closure.

- [x] **Step 1: Run the final scoped local checks before candidate deployment**

Run: `python3 -m unittest tests.gear_catalog_revision_test tests.gear_catalog_revision_store_test tests.gear_track_authority_test tests.pg_gear_read_model_selectors_test tests.websim_payload_test` and `git diff --check`

Observed: all 513 affected Python contracts passed at `da051891`; Python emitted pre-existing SQLite `ResourceWarning` diagnostics but no test failure.

- [x] **Step 2: Candidate deploy and protect against backflow**

Run: deploy the final immutable commit with `WOW_DEPLOY_START_ASYNC_SYNCS=0`; record runtime file/hash parity, candidate service identity, dormant Catalog/Exact Registry identities, unchanged active Manifest generation, and the previous candidate rollback service.

Expected: no active pointer switch, sync, backfill, cleanup, or timer-owned state write occurs.

Observed: `wow-backend-manifest-catalog-detail-da051891.service` runs only from its isolated candidate root on port 18788 with `WOW_GEAR_MANIFEST_PREVIEW_REVISION=78916c…ed560` and `WOW_DEPLOY_START_ASYNC_SYNCS=0`. The candidate is bound to `da051891` / tree `be621753…daa91`; the retail pointer remains generation 35. The superseded `14078788` service remains active as rollback/diagnostic evidence.

- [x] **Step 3: Smoke the actual user cases**

Run: request Mage Arcane, Fire, and Frost head candidates plus a valid cloth control; inspect `250033` and `268283`, all normal upgrade states, exact community import of a Myth 2/6 instance, and a source/type-unknown candidate.

Expected: `250033`/`268283` are absent until their type/class facts are governed; no public normal track has `rank < maxRank`, one logical state never has two core-fact shapes, the exact import retains its real Myth 2/6 identity outside Browse, and the valid cloth control remains selectable.

Observed: Arcane, Fire, and Frost each return eight Cloth head candidates, all exclude `250033`/`268283`, and the sample Cloth head has only Mythic/Hero/Champion 6/6 Browse states. Exact Registry retains `250033` Myth 2/6 but the Catalog has no Myth 2/6 Browse row for it.

- [x] **Step 4: Refresh DevTools and request explicit user acceptance**

Run: `WOW_BACKEND_API_BASE_URL=http://127.0.0.1:<candidate-tunnel-port> npm run refresh:weapp`

Expected: the built bundle records the final commit; the user verifies Mage filtering, named canonical progression, selected-variant stats, source/diagnostic safety, and no exact-instance leakage before any merge.

Observed: `WOW_BACKEND_API_BASE_URL=http://127.0.0.1:18788 npm run refresh:weapp` rebuilt the 214-file WeChat bundle at `da051891` and opened DevTools. Explicit acceptance of Task 4's six-item matrix remains pending.

### Task 9: Rebind the correction to the current runtime head

**Files:**
- Modify: `server/websim_payload.py`
- Modify: `tests/websim_payload_test.py`
- Modify: `tests/pg_gear_read_model_selectors_test.py`
- Modify: `tests/postgres_cache_store_test.py`
- Modify: `tests/gear_exact_template_options_test.py`
- Modify: `artifacts/releases/2026-07-29-manifest-catalog-detail-contract/requirement.json`
- Modify: `artifacts/releases/2026-07-29-manifest-catalog-detail-contract/evidence.json`

**Interfaces:** Consumes a candidate that claims Manifest Catalog provenance or a sealed Exact-only import. Produces a public Browse candidate only when the selected BrowseVariant carries the matching verified Catalog revision/key/evidence chain, while preserving an Exact-only import through the existing authority, Resolve, ResolvedLoadout, and SimC contracts without publishing it to Browse.

- [x] Add RED regressions proving verified-looking static stats cannot clear a claimed Catalog provenance mismatch and cannot make that row visible as a replacement.
- [x] Require matching `manifest_catalog_v2` evidence status, Catalog revision, selected BrowseVariant key, and selected-variant evidence before a Catalog-claimed row can be trusted. Keep legacy rows on their existing trust path; this task does not claim the later full Catalog cutover.
- [x] Add a real-code regression that projects and binds an Exact-only community import, resolves it, builds a ResolvedLoadout and SimulationSnapshot, emits the canonical SimC item line, and proves the same Exact instance remains absent from Browse.
- [x] Run `python3 -m unittest tests.gear_attribute_preview_fixture_test tests.gear_exact_template_options_test tests.pg_gear_read_model_selectors_test tests.postgres_cache_store_test tests.websim_payload_test`.

Observed: 651 affected tests pass on the current working tree. Python still emits pre-existing unclosed-SQLite `ResourceWarning` diagnostics; this is not represented as a clean resource result.

- [x] Seal the current immutable runtime head, Catalog, Exact Registry, Manifest, API candidate, and WeChat bundle after the cloud root filesystem returned to the Goal's safe threshold. Candidate commit `3f01df0bbb7b85f2581779d3ea15c82702d27796` / tree `f0872fdd1d62d0c32f6cb6aab301b315a550705d` is bound to Manifest `cd547cc3ab4cbad9cd3f04a2b2dec12a11970f51b11a8c68607550d58dfc89f3`, Catalog `b0de0d64c5eda2b443902576663d93c7761719cc0d1dbc0a98b5bc1a34373461`, Exact `56417e51a17cad7e42fad8a0fee4f0d092eda081a0f43cf53cc6c3b0af883c7b`, Community `686708be049323a979b66bfba42cae3f2b80f7337e740d26b299fd73e0665804`, and SimC `b92847e847c9a6c354d4ba2130abd37f1ccf72d8`.
- [x] Complete automatic candidate proof: 1,304/1,304 Resolver/Profile materializations, 26/26 supported SimC specs, 14/14 deterministic unsupported blocks, 674/674 supported BrowseVariant real-SimC smokes, zero non-simulatable contexts, zero silent fills, zero missing provenance, zero HTTP completeness failures, and unchanged active generation-35 pointer.
- [x] Prepare the same-identity live WeChat acceptance surface: DevTools RC 2.02.2607271 is open on AppID `wx17543b6fc4305479` and the candidate `dist/weapp`; local-only `urlCheck=false` is applied to the ignored runtime config while repository source remains `urlCheck=true`. Mage/Arcane routes and the `spellslinger` community import load, and the head chooser exposes six Browse candidates with governed 6/6 tracks.
- [ ] Execute the six current-packet WeChat acceptance items against that exact bundle identity. The candidate bundle is rebuilt with `sourceHash sha256:3621ba4cb0715536f58d72abe62de65f74a15d023ab58fd33e79c65352ae786d`; a fresh community-template import now shows backend-owned static secondary facts in all 16 equipped rows, and the head chooser exposes six candidates with governed 6/6 tracks. Automated endpoint discovery found no reusable DevTools endpoint and refused to relaunch, so no manual result is inferred. The earlier `da051891` candidate and bundle remain superseded.

Current stop: the current candidate is runtime-verified and intentionally remains dormant on port `18794`; the active generation-35 Manifest/Catalog/Exact pointer is unchanged. A fresh community-template import proves the per-item static-fact path is visible; the aggregate summary remains literal `待校验` because the candidate reports `formalActiveManifest=false`, and this is not replaced by frontend inference. The six-item WeChat acceptance remains pending and no user result is inferred. After acceptance, clean-Harness/CR and merge closure still apply. This correction packet still cannot prove the independent current-season PVE universe or the Goal-level 40-specialization real-WeChat matrix; those are controlled by `docs/plans/2026-07-29-equipment-simulator-e2e-completeness-goal.md`. Do not reinterpret this candidate as a full PVE Universe or Exact-first v2 release.
