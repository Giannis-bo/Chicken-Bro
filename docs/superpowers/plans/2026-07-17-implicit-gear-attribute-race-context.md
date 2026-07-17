# 隐式装备属性种族上下文 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让社区装备模板静默继承受证据约束的来源种族，所有手动路径稳定使用人类，并移除装备页种族交互。

**Architecture:** Raider.IO 采集到的 `raceKey` 经 observed-profile ref 和社区模板进入新的 sealed import-evidence v2；Release projector 只向导入 envelope 提供已封存的属性角色上下文。`pages/builds/detail.*` 将该上下文作为与装备选择正交的本地状态，导入后保持，其他起点建立人类默认。没有新请求、SimC 或 Release 写路径。

**Tech Stack:** Python 3、PostgreSQL JSONB existing payloads、Node built-in test runner、微信小程序 WXML/JS。

## Global Constraints

- 不修改 `pages/simulator/simc.*`、SimC worker、winner audit、Release election 或 Manifest pointer。
- 不增加数据库迁移；现有 JSONB/payload 和后续 Release refresh 负责承载新事实。
- 历史 v1 community import evidence 必须可读，并明确回退 `human/default_human`。
- 不得在 import/换装/属性刷新中发起 profile、Raider.IO、Battle.net 或 SimC 请求。
- 不触碰用户工作树中的 `project.config.json`。

---

### Task 1: Capture and preserve an observed source race

**Files:**
- Modify: `server/raiderio_payload.py`
- Modify: `server/postgres_cache_store.py`
- Modify: `server/websim_payload.py`
- Test: `tests/raiderio_payload_test.py`
- Test: `tests/websim_payload_test.py`

**Interfaces:**
- Produces: observed `raceKey` in the normalized profile, `observedProfileRefs`, template `payload.character`, and compact community-template payload.
- Consumes: raw profile `race` field from the already-permitted Raider.IO profile response.

- [ ] **Step 1: Write failing capture/projection tests.**

```python
def test_profile_summary_normalizes_source_race_and_observed_template_preserves_it(self):
    profile = sample_profile_payload()
    profile["race"] = {"name": "Night Elf", "slug": "night-elf"}
    summary = raiderio_payload.profile_summary(profile)
    self.assertEqual(summary["raceKey"], "night_elf")
    template = websim_payload.gear_community_template_from_observed_items(
        observed_items_with_ref(raceKey="night_elf"), "mage", "frost"
    )
    self.assertEqual(template["payload"]["character"]["raceKey"], "night_elf")
```

Also assert an absent/invalid raw race omits `raceKey`, and compact/persisted templates preserve a valid key without exposing raw profile payloads.

- [ ] **Step 2: Run the new tests and observe RED.**

```bash
python3 -m unittest -q tests.raiderio_payload_test tests.websim_payload_test
```

Expected: assertions fail because profile and template projections do not yet contain `raceKey`.

- [ ] **Step 3: Implement the minimal bounded projection.**

Add a local race normalizer in `raiderio_payload.py` that accepts only lower-case underscore identifiers derived from a profile's race slug/name. Preserve `raceKey` only through the existing observed profile refs, `normalize_source_refs`, single-profile template identity, template payload and compact template projection. Do not fetch or infer it from URL, class or faction.

- [ ] **Step 4: Run focused GREEN checks.**

```bash
python3 -m unittest -q tests.raiderio_payload_test tests.websim_payload_test
```

Expected: all pass; missing race remains absent rather than invented.

### Task 2: Seal a race-aware import context while retaining old Releases

**Files:**
- Modify: `server/gear_release.py`
- Modify: `server/gear_release_tool.py`
- Modify: `server/community_template_import.py`
- Test: `tests/gear_release_test.py`
- Test: `tests/gear_release_tool_test.py`
- Test: `tests/community_template_import_test.py`

**Interfaces:**
- Produces: v2 sealed import evidence containing `sourceRaceKey`, and public `template.attributeCharacterContext`.
- Consumes: template payload's observed `character.raceKey`; v1 evidence stays valid with default context.

- [ ] **Step 1: Write failing v2 and backward-compatibility tests.**

```python
def test_v2_evidence_binds_source_race_and_public_import_exposes_source_context(self):
    evidence = community_template_import_evidence_from_template(
        template_with_source_race("night_elf"), gear_release_id="gear-r1", gear_snapshot=snapshot
    )
    self.assertEqual(evidence["schemaRevision"], "community-template-import-evidence-v2")
    self.assertEqual(evidence["sourceRaceKey"], "night_elf")
    source = build_community_template_import_source(winner_with(evidence), variants, options, items=items)
    self.assertEqual(source["template"]["attributeCharacterContext"], {
        "schemaRevision": "gear-attribute-character-v1", "raceKey": "night_elf", "origin": "source_profile"
    })

def test_v1_evidence_projects_human_default_context(self):
    source = build_community_template_import_source(winner_with(v1_evidence), variants, options, items=items)
    self.assertEqual(source["template"]["attributeCharacterContext"]["raceKey"], "human")
    self.assertEqual(source["template"]["attributeCharacterContext"]["origin"], "default_human")
```

Also assert a changed v2 source race changes the evidence fingerprint, malformed v2 keys are rejected, and the public data contains only the bounded context.

- [ ] **Step 2: Run the new tests and observe RED.**

```bash
python3 -m unittest -q tests.gear_release_test tests.gear_release_tool_test tests.community_template_import_test
```

Expected: v2/race assertions fail while existing v1 assertions remain green.

- [ ] **Step 3: Implement versioned evidence and projector fallback.**

Emit `community-template-import-evidence-v2` for new observed templates. Include only a valid `sourceRaceKey` in its canonical fingerprint; validate it in `gear_release.py`. Accept v1 and v2 in readers; map v1/missing/invalid values to `{raceKey: "human", origin: "default_human"}`. `community_template_import_public_data()` may expose this context only inside its already-bounded template object.

- [ ] **Step 4: Run focused GREEN checks.**

```bash
python3 -m unittest -q tests.gear_release_test tests.gear_release_tool_test tests.community_template_import_test
```

Expected: v1 import behavior is retained, v2 source context is sealed, and no Release mutation happens during read.

### Task 3: Make the equipment page hold an implicit context and remove the selector

**Files:**
- Modify: `pages/builds/detail.js`
- Modify: `pages/builds/detail.wxml`
- Modify: `pages/builds/detail.wxss`
- Test: `tests/builds-page.test.js`

**Interfaces:**
- Consumes: `template.attributeCharacterContext` from the sealed community import envelope or compact template.
- Produces: `gearAttributeCharacterContext` page state and a local calculator input `{raceKey}`.

- [ ] **Step 1: Write failing page behavior tests.**

```javascript
test('community import keeps its sealed source race while later equipment changes recalculate', async () => {
  const page = pageWithVerifiedCommunityImport({
    attributeCharacterContext: { schemaRevision: 'gear-attribute-character-v1', raceKey: 'night_elf', origin: 'source_profile' }
  })
  await pageConfig.applyGearCommunityTemplate.call(page, eventFor('observed-frost'))
  assert.equal(page.data.gearAttributeCharacterContext.raceKey, 'night_elf')
  await pageConfig.selectGearCandidate.call(page, changedItemEvent)
  assert.equal(page.data.gearAttributeCharacterContext.raceKey, 'night_elf')
})

test('manual and legacy community paths use human without rendering a race selector', () => {
  const state = pageConfig.refreshGearAttributePanel.call(pageWithoutImportContext)
  assert.equal(state.status, 'calculated')
  assert.equal(page.data.gearAttributeCharacterContext.raceKey, 'human')
  assert.doesNotMatch(readDetailWxml(), /请选择种族|gearAttributeRaceSheet/)
})
```

Cover reset and saved-template reapply; persist `attributeCharacterContext` alongside saved `importOrigin`. Assert no selector handler, sheet state or race row remains, and the existing community import test still records exactly one import request.

- [ ] **Step 2: Run the new page tests and observe RED.**

```bash
node --test tests/builds-page.test.js --test-name-pattern="source race|manual and legacy"
```

Expected: tests fail because the page requires an explicit `selectedRaceKey` and renders the selector.

- [ ] **Step 3: Implement the smallest local state transition.**

Create one `gearAttributeCharacterContextForData()` helper returning a validated sealed context or human default. Replace `selectedRaceKey`/`selectedRaceName`/race sheet state with `gearAttributeCharacterContext`; all calculator calls receive only its `raceKey`. Adopt the envelope context in `commitImportedCommunityTemplate`, preserve it during gear changes and saved-template replay, and create a human default on reset/manual paths. Delete only the detail-page selector WXML/WXSS/methods; do not touch the standalone SimC page.

- [ ] **Step 4: Run focused GREEN checks.**

```bash
node --test tests/builds-page.test.js
```

Expected: import inheritance, hand-edited preservation, human defaults, saved replay and selector removal all pass without new network calls.

### Task 4: Verify the runtime boundary and record the new candidate requirement

**Files:**
- Modify: `docs/roadmap.md`
- Modify: `artifacts/releases/2026-07-17-real-time-gear-stat-engine/requirement.json`
- Modify: `artifacts/releases/2026-07-17-real-time-gear-stat-engine/evidence.json`
- Create: `artifacts/releases/2026-07-17-real-time-gear-stat-engine/evidence/implicit-race-context-candidate.json`

- [ ] **Step 1: Run related regression and Harness verification.**

```bash
python3 -m unittest -q tests.raiderio_payload_test tests.websim_payload_test tests.gear_release_test tests.gear_release_tool_test tests.community_template_import_test tests.gear_runtime_test tests.news_backend_test
node --test tests/builds-page.test.js tests/frontend-api-client.test.js tests/project-harness.test.js
node scripts/verify-project.js --profile full --release artifacts/releases/2026-07-17-real-time-gear-stat-engine --base origin/main
git diff --check
```

- [ ] **Step 2: Candidate deployment and smoke.**

From a clean candidate worktree, back up the runtime and PostgreSQL database, deploy with `WOW_DEPLOY_START_ASYNC_SYNCS=0`, and prove: import endpoint remains one request; a source-race template returns sealed context; a legacy/missing-race template returns human default; `/api/websim/gear` and `/health` remain responsive; no SimC/worker/sync starts; runtime file parity and rollback path are recorded. Do not force a global community refresh solely to populate historical races.

- [ ] **Step 3: Local CR and user acceptance.**

Review that race never becomes a new network input, Release mutation, SimC input path, or rendered equipment-page control. Wait for explicit post-test user acceptance before merge/push.
