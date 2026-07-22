# 装备模板保存、导入、清空与天赋 winner 投影 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 玩家可以保存完整装备配置、显式导入自己的模板或两个社区真人模板，并清空当前装备；社区装备模板复用天赋模拟的 80 个职业-专精-英雄天赋来源角色。

**Architecture:** 天赋 election 是来源角色和排序的唯一 owner。装备侧把同一 hero 的候选序列投影为一个合法 gear winner：首位 talent winner 的已采集装备通过 canonical resolver 与 provenance 校验时直接复用；否则只在该 hero 的原序列内继续选取下一个装备合法的来源角色，不修改天赋 winner。社区 Gear Release 从“每专精一个 winner + baseline 计数”升级为“每职业-专精两个 hero-slot winner”，继续使用 immutable release、原子导入和现有 resolver。

**Tech Stack:** Python 3 server and PostgreSQL release store, typed TypeScript domain/API client, Taro/React, Vitest/Node tests, existing Gear Release and Harness candidate smoke.

## Global Constraints

- 分类为 Strict；用户于 2026-07-22 确认：装备 fallback 只改变装备 projection winner，不改变天赋 winner。
- 社区公开装备只允许 raiderio_observed_profile，且必须通过当前 canonical resolver、完整槽位和 provenance 校验；baseline、推荐模板、匿名或不完整快照不得补位。
- 正常路径复用天赋 80 个 winner 的角色 identity、来源 URL、profile hash 与已采集 snapshot；不得引入独立的社区装备排名或第三套采集源。
- 每个 (classKey, specKey, heroKey) 有一个合法 gear projection winner；每个 (classKey, specKey) 在社区导入页按两个 hero slot 展示两个可导入真人模板。候选耗尽时公开 pending_collection，不能伪造第二张卡。
- POST /api/websim/gear/community-import 继续是社区导入唯一 authority；前端不得本地拼接 canonical import。
- 保存模板必须持久化 gearBySlot 与 enhancementBySlot；重置是清空当前 draft，不是恢复 initial server loadout。
- 不增加运行时同步、数据下载或自动 backfill；候选发布前保持 WOW_DEPLOY_START_ASYNC_SYNCS=0。
- 现有用户工作树中职业选择、装备槽布局相关的未提交修改不属于本任务，不得回退或覆盖。

## Requirement Contract

**用户场景：** 玩家在装备模拟页面已经选择职业与专精，想保存当前配置、明确选择自己的历史模板或两位高端社区玩家模板，然后一键清空整套装备重新搭配。

**用户侧承诺：** 保存后重新进入页面仍可导入同一套装备和强化；导入不会偷偷选择第一张模板；社区每张卡清楚显示所属 hero、真人来源和状态，且导入结果由后端原子校验；点击“重置”后 16 个装备槽和所有强化都为空。

**非目标：** 不做装备评分/BiS 推荐，不改变天赋 winner，不把天赋候选以外的角色塞入装备页，不公开 baseline，不允许前端判装备合法性，不删除个人模板，也不在本任务中触发生产采集。

**反例与防护：**

1. 旧 80/80 = 40 真人 + 40 baseline 被误当成两位真人模板：改为 40 专精 x 2 hero-slot = 80 真人 gear projection winner，baseline 从公开计数和导入列表移除。
2. 顶部天赋 winner 装备缺槽，却被另一职业/专精或 baseline 静默补足：只从相同 (class,spec,hero,scenario) 排序序列递补；没有合格候选则显示待采集。
3. 已保存模板导入漏掉宝石、附魔和装饰：保存 raw payload 使用版本化 draft，同时保留 resolved intent/proof；导入兼容旧版仅装备 JSON，并重新 resolver 校验。

## Impact Map and Ownership

| 分类 | 面 | 决策 |
| --- | --- | --- |
| must_change | 天赋候选 -> gear projection | 新建 server/community_winner_projection.py 纯函数拥有同 hero 候选投影、递补理由和 provenance 绑定；天赋 election 仍拥有排名与 winner。 |
| must_change | Gear Release / PG read model | server/gear_release.py、server/gear_release_tool.py、server/gear_release_store.py 和 server/pg_gear_template_selectors.py 发布并读取两个 hero-slot winner。 |
| must_change | 公开 API / typed transport | server/websim_payload.py、domain/API normalizer 暴露 hero、真人身份、projection 状态和两个 template ID；community import 继续按 exact ID 原子执行。 |
| must_change | 装备页动作 | apps/mini-taro/src/pages/builds/detail.tsx 与新建纯 model 显式分组导入，保存 versioned draft，清空而不是恢复 initial loadout。 |
| must_not_change | 天赋 winner、个人 owner 隔离、resolver 规则 | 不从 gear fallback 回写天赋记录；个人模板仍由 /api/me/build-templates owner-scoped；resolver 是唯一合法性 owner。 |
| risk_unknown | talent winner 原始候选是否包含可复用 gear capture | 先以 characterization test 和 staging snapshot 核对 profileHash/sourceUrl/heroKey；无 capture 记录 SOURCE_GEAR_CAPTURE_MISSING，不发新排名。 |
| evidence_required | 发布与运行 | candidate release 必须有 80 hero-slot winner、无 public baseline、两个 exact import、失败递补 trace、API/health/timer backflow 与微信四条交互证据。 |

**Engineering health:** server/websim_payload.py、server/gear_release_store.py、server/postgres_cache_sync.py 都是热点；投影与 row-shape 规则放到新纯模块及 gear_release_tool.py adapter，避免把新 election 分支继续堆进 serializer/store。预期为 health_watch，以 characterization、query-count 和 candidate smoke 降低风险。

**Rollback:** code_rollback 到前一 release reader；若新 Community Release 已封存但未 pointer promotion，保持旧 pointer；若 UI 文案或两个模板呈现异常，feature_hide 仅隐藏社区分组，个人模板保存/导入和清空继续可用；错误候选记录用 resync_repair 生成新 immutable release，绝不原地改 active release。

## File Structure

| 文件 | 责任 |
| --- | --- |
| server/community_winner_projection.py | 纯 hero-slot projection：接收已排序 talent candidates 与已捕获装备，产出 winner/standby/rejected 及稳定 evidence。 |
| server/gear_release.py | 将 community release coverage/invariant 从 spec winner 改为 hero-slot winner，并保留 v1 release 的只读兼容。 |
| server/gear_release_tool.py | 从天赋 candidate source 生成两类 projection slot、封装 release rows 和 gate summary。 |
| server/gear_release_store.py | 按 (class,spec) 读取两个 winner，检查 content schema 对应的 1/2 slot invariant，并让 exact-ID 原子导入接受两个 winner 中任意一个。 |
| server/pg_gear_template_selectors.py / server/websim_payload.py | 只将已发布 hero projection template 公开为 payload；移除 baseline 对 80/80 公共覆盖的影响。 |
| packages/domain/src/entities.ts / packages/api-client/src/websim.ts | 声明并严格归一化 hero/projection/provenance 字段。 |
| apps/mini-taro/src/pages/builds/gear-template-import-model.ts | 纯 saved draft parser、筛选、导入分组和中文展示标签。 |
| apps/mini-taro/src/pages/builds/detail.tsx | 调用 model 和后端 actions；不再自动挑第一张；清空 draft。 |
| tests/*gear*、apps/mini-taro/src/pages/builds/*test.ts | 选举、release、API、保存/导入/清空的回归证据。 |

## Implementation Tasks

### Task 1: Freeze the hero-slot projection contract

**Files:**
- Create: server/community_winner_projection.py
- Create: tests/community_winner_projection_test.py
- Modify: server/gear_public_contract.py
- Modify: tests/gear_public_contract_test.py

**Consumes:** ordered talent candidates with classKey, specKey, heroKey, scenarioKey, candidateId, sourceUrl, profileHash, rankingEvidence; captured observed gear by the same identity.

**Produces:** project_hero_slot(candidates, gear_by_identity, validate) returning winner, standbys, rejected, where winner always carries heroKey, talentWinnerId, talentCandidateRank, gearProjectionMode, sourceUrl, profileHash, gearHash, and importEvidence.

- [x] **Step 1: Write the failing projection tests**

~~~python
def test_projection_reuses_rank_one_talent_winner_when_its_gear_is_legal():
    result = project_hero_slot(talent_candidates("mage", "frost", "frostfire"), gear_by_identity, validate)
    assert result["winner"]["candidateId"] == "talent-rank-1"
    assert result["winner"]["gearProjectionMode"] == "talent_winner"

def test_projection_skips_only_illegal_gear_and_keeps_talent_winner_immutable():
    result = project_hero_slot(talent_candidates_with_illegal_rank_one(), gear_by_identity, validate)
    assert result["winner"]["candidateId"] == "talent-rank-2"
    assert result["winner"]["talentWinnerId"] == "talent-rank-1"
    assert result["winner"]["gearProjectionMode"] == "gear_fallback"

def test_projection_never_uses_baseline_or_a_different_hero_when_candidates_are_exhausted():
    result = project_hero_slot(exhausted_frostfire_candidates(), gear_by_identity, validate)
    assert result["winner"] is None
    assert result["slotStatus"] == "pending_collection"
~~~

- [x] **Step 2: Run test to verify it fails**

Run: python3 -m unittest tests.community_winner_projection_test -v  
Expected: import failure because community_winner_projection does not yet exist.

- [x] **Step 3: Implement the minimal pure projection**

~~~python
def project_hero_slot(candidates, gear_by_identity, validate):
    ranked = sorted(candidates, key=lambda item: int(item["talentCandidateRank"]))
    talent_winner_id = ranked[0]["candidateId"] if ranked else ""
    rejected = []
    for candidate in ranked:
        verdict = validate(candidate, gear_by_identity.get(candidate_identity(candidate)))
        if verdict["status"] == "verified":
            return {"winner": {**candidate, **verdict["template"],
                    "talentWinnerId": talent_winner_id,
                    "gearProjectionMode": "talent_winner" if candidate["candidateId"] == talent_winner_id else "gear_fallback"},
                    "standbys": [], "rejected": rejected, "slotStatus": "covered"}
        rejected.append({**candidate, "problems": verdict["problems"]})
    return {"winner": None, "standbys": [], "rejected": rejected, "slotStatus": "pending_collection"}
~~~

- [x] **Step 4: Define public policy and verify**

~~~python
COMMUNITY_GEAR_TEMPLATE_SLOTS_PER_SPEC = 2
COMMUNITY_GEAR_TEMPLATE_COUNTING_POLICY = (
    "40 class-specs x 2 hero-talent source winners; only legal raiderio_observed_profile gear is public"
)
~~~

gear_public_contract.py rejects a baseline, missing heroKey, source-less record, or pending_collection projection. Run: python3 -m unittest tests.community_winner_projection_test tests.gear_public_contract_test -v. Expected: PASS.

### Task 2: Seal and read two immutable Community Release winners per spec

**Files:**
- Modify: server/gear_release.py
- Modify: server/gear_release_tool.py
- Modify: server/gear_release_store.py
- Test: tests/gear_release_test.py
- Test: tests/gear_release_store_test.py
- Test: tests/gear_release_tool_test.py

**Consumes:** Task 1 hero-slot result, active Gear Release snapshot, exact talent candidate provenance.

**Produces:** community-release-content-v2 with winnerSlots = [{classKey,specKey,heroKey}], exactly one winner per expected hero slot and zero public baseline slots; v1 releases remain readable until their atomic pointer replacement.

- [x] **Step 1: Write failing release invariants**

~~~python
def test_v2_release_requires_two_distinct_hero_winners_for_each_spec():
    result = prepare_staging_community_release(
        store=store,
        gear_release_descriptor=gear_release,
        gear_snapshot=gear_snapshot,
        dependency_revisions=dependencies,
        expected_hero_slots=expected_hero_slots(),
        now=NOW,
    )
    assert result["gate"]["winnerSlotCount"] == 80
    assert result["gate"]["missingHeroSlots"] == []

def test_store_reads_both_hero_winners_and_exact_import_accepts_each_id():
    templates = store.load_active_gear_read_model(binding, "mage", "frost")["communityTemplates"]
    assert [item["heroKey"] for item in templates] == ["frostfire", "spellslinger"]
    assert store.load_active_community_template_import(binding, "mage", "frost", templates[1]["id"])["winner"]["heroKey"] == "spellslinger"

def test_v2_coverage_never_counts_baseline_as_a_missing_hero_replacement():
    assert v2_coverage(rows_with_one_real_and_one_baseline)["status"] == "partial"
~~~

- [x] **Step 2: Run test to verify it fails**

Run: python3 -m unittest tests.gear_release_test tests.gear_release_store_test tests.gear_release_tool_test -v  
Expected: failures citing one-winner-per-spec invariant or missing heroKey.

- [x] **Step 3: Change release row and summary schema**

~~~python
def community_rows_summary_v2(rows):
    canonical_rows = [dict(row) for row in rows if isinstance(row, dict)]
    winner_slots = sorted({
        (row["classKey"], row["specKey"], row["heroKey"])
        for row in canonical_rows if row.get("role") == "winner"
    })
    standby_count = sum(row.get("role") == "standby" for row in canonical_rows)
    rejected_count = sum(row.get("role") == "rejected" for row in canonical_rows)
    return {"schemaRevision": "community-release-content-v2",
            "winnerSlots": [{"classKey": c, "specKey": s, "heroKey": h} for c, s, h in winner_slots],
            "counts": {"total": len(canonical_rows), "winner": len(winner_slots), "standby": standby_count, "rejected": rejected_count}}
~~~

Store heroKey, talentWinnerId, talentCandidateRank, gearProjectionMode, and importEvidence in sealed payload_json; no migration is needed because access remains by (release_id,class_key,spec_key,template_id) and release content hash commits these fields. Keep v1 summary validation for the current active release during rollout.

- [x] **Step 4: Build rows from talent candidate slots**

~~~python
projection_slots = expected_hero_slots_from_talent_catalog(expected_specs)
projection = project_hero_slots(talent_candidates_by_slot, observed_gear_by_identity, resolve_candidate)
rows = release_rows_from_projection(projection)
~~~

prepare_staging_community_release accepts expected_hero_slots; it rejects a duplicate hero, class/spec/hero/scenario mismatch, missing source identity, or baseline. electionRank is scoped to one hero slot.

- [x] **Step 5: Read/import both winners and verify**

GearReleaseStore.load_active_gear_read_model returns the one or two rows allowed by the release content schema in (heroKey,electionRank,templateId) order, validates all row hashes, and load_active_community_template_import accepts either exact ID only after checking sealed hero projection evidence.

Run: python3 -m unittest tests.gear_release_test tests.gear_release_store_test tests.gear_release_tool_test tests.community_winner_projection_test -v. Expected: PASS for 80 slots, gear-only fallback, v1 compatibility, either exact import and baseline rejection.

- [x] **Step 6: Persist the full election order without a separate gear ranking**

Keep the compact, ordered Raider.IO candidate sequence on each persisted talent winner payload (`gearProjectionCandidates`) and read that exact sequence back through `GearReleaseStore`.  The sequence includes the immutable player identity and its rank, is not capped to the first 10 rows, and the observed-gear store keeps one candidate per `(class, spec, sourceIdentity)` even when two players have identical items.  This lets gear-only fallback continue the original talent election without recollecting or reranking players.

The legacy one-player pilot cleanup may still remove hidden baseline/recommendation residue, but must never delete a different `raiderio_observed_profile` row or its observed variants for the same spec.

Run: `python3 -m unittest tests.postgres_cache_store_test tests.gear_release_store_test tests.websim_payload_test -v`. Expected: PASS, including both same-spec observed-player candidates and an uncapped persisted fallback sequence.

### Task 3: Project the published API and health coverage honestly

**Files:**
- Modify: server/pg_gear_template_selectors.py
- Modify: server/websim_payload.py
- Modify: server/postgres_cache_sync.py
- Test: tests/pg_gear_template_selectors_test.py
- Test: tests/websim_payload_test.py
- Test: tests/postgres_cache_sync_test.py
- Test: tests/news_backend_test.py

**Consumes:** Task 2 sealed Community Release rows.

**Produces:** WebsimGearPayload.communityTemplates returns both valid hero templates, compact and full payload retain provenance, and health/preflight reports requiredHeroSlotCount=80 rather than a baseline-filled claim.

- [ ] **Step 1: Write failing API and coverage tests**

~~~python
def test_public_gear_payload_exposes_two_hero_projection_templates_with_provenance():
    payload = get_websim_gear(conn, "mage", "frost", compact=True)
    assert [(item["heroKey"], item["playerName"]) for item in payload["communityTemplates"]] == [
        ("frostfire", "RankOne"), ("spellslinger", "RankTwo")]

def test_gear_coverage_is_partial_when_one_hero_slot_is_pending_even_if_baseline_exists():
    summary = community_gear_import_coverage_summary(
        expected_hero_slots=expected_hero_slots(),
        covered_hero_slots=expected_hero_slots()[:-1],
        pending_hero_slots=[expected_hero_slots()[-1]],
        baseline_available_specs=all_spec_ids(),
    )
    assert summary["requiredHeroSlotCount"] == 80
    assert summary["coveredHeroSlotCount"] == 79
    assert summary["status"] == "partial"
~~~

- [ ] **Step 2: Run test to verify it fails**

Run: python3 -m unittest tests.pg_gear_template_selectors_test tests.websim_payload_test tests.postgres_cache_sync_test tests.news_backend_test -v  
Expected: failures because selection returns one winner and coverage still accepts fallback baseline.

- [ ] **Step 3: Extend public projection fields**

~~~python
public_template = {**public_template,
    "heroKey": projection["heroKey"],
    "heroLabel": hero_tree_label(projection["heroKey"]),
    "playerName": projection["playerName"],
    "serverName": projection["serverName"],
    "region": projection["region"],
    "gearProjectionMode": projection["gearProjectionMode"],
    "freshnessStatus": projection["freshnessStatus"]}
~~~

Do not serialize standbys, candidate ranking internals or rejected players. A pending_collection slot may show hero label and blocker but must set canApplyGear=false.

- [ ] **Step 4: Replace public counting semantics and run tests**

Group daily preflight, guard status and target queue by (classKey,specKey,heroKey). Their next action is repair_source_gear_capture or collect_same_hero_candidate, never build_baseline_template for public import.

Run: python3 -m unittest tests.pg_gear_template_selectors_test tests.websim_payload_test tests.postgres_cache_sync_test tests.news_backend_test tests.community_template_import_test -v. Expected: PASS with two templates when covered and no public baseline.

### Task 4: Make typed client and local saved draft lossless

**Files:**
- Modify: packages/domain/src/entities.ts
- Modify: packages/api-client/src/websim.ts
- Create: apps/mini-taro/src/pages/builds/gear-template-import-model.ts
- Create: apps/mini-taro/src/pages/builds/gear-template-import-model.test.ts
- Test: packages/api-client/src/websim.test.ts

**Consumes:** Task 3 public community template payload and existing BuildTemplate records.

**Produces:** strict typed community fields and parseGearTemplateDraft(rawString, metadata) that accepts both legacy gear-only saves and versioned gear+enhancement saves.

- [x] **Step 1: Write failing model tests**

~~~ts
it('round-trips a complete gear draft including enhancements', () => {
  const saved = serializeGearTemplateDraft({ gearBySlot: { head: helm }, enhancementBySlot: { head: enchant } })
  expect(parseGearTemplateDraft(saved, {})).toEqual({ gearBySlot: { head: helm }, enhancementBySlot: { head: enchant } })
})
it('keeps legacy gear-only templates importable and filters saved templates to active class/spec', () => {
  expect(savedGearTemplatesForSelection(templates, 'mage', 'frost')).toHaveLength(1)
  expect(parseGearTemplateDraft(JSON.stringify({ head: helm }), {}).enhancementBySlot).toEqual({})
})
it('labels both community options with hero and real-player provenance without picking either one', () => {
  expect(communityGearImportOptions(twoWinners).map((item) => item.label)).toEqual([
    '霜火 · RankOne · Raider.IO', '法术投射者 · RankTwo · Raider.IO'])
})
~~~

- [x] **Step 2: Run test to verify it fails**

Run: npm run test -- apps/mini-taro/src/pages/builds/gear-template-import-model.test.ts packages/api-client/src/websim.test.ts  
Expected: module-not-found and missing typed field failures.

- [x] **Step 3: Add versioned saved-draft contract**

~~~ts
export interface GearTemplateDraft {
  schemaRevision: 'gear-template-draft-v2'
  gearBySlot: Readonly<Record<string, GearItemReference>>
  enhancementBySlot: Readonly<Record<string, GearEnhancementSelection>>
}
export function serializeGearTemplateDraft(draft: Omit<GearTemplateDraft, 'schemaRevision'>): string {
  return JSON.stringify({ schemaRevision: 'gear-template-draft-v2', ...draft })
}
~~~

Parser order is v2 raw draft, legacy top-level gear JSON, then existing metadata fallback. It rejects malformed item/enhancement rather than copying unknown data into workbench.

- [x] **Step 4: Add typed projection fields and verify**

Add optional gearProjectionMode, talentWinnerId, freshnessStatus, playerName, serverName, and region to CommunityTemplateReference; normalizer permits only safe scalar values and no server-only evidence object.

Run: npm run test -- apps/mini-taro/src/pages/builds/gear-template-import-model.test.ts packages/api-client/src/websim.test.ts && npm run typecheck. Expected: PASS.

### Task 5: Change the three equipment-page actions

**Files:**
- Modify: apps/mini-taro/src/pages/builds/detail.tsx
- Modify: apps/mini-taro/src/pages/builds/gear-detail-page-contract.test.ts
- Modify: docs/design/current-ui/routes/gear-detail/truth-adaptation.json
- Modify: docs/design/current-ui/routes/gear-detail/component-contract.json
- Modify: docs/design/current-ui/core-interaction-contract.json

**Consumes:** Task 4 draft parser/serializer and import option model; existing GearRequestFence and atomic community endpoint.

**Produces:** save current complete draft; import chooses one explicit source group then one explicit template; reset empties the current draft and all derived UI state.

- [x] **Step 1: Write failing route contract tests**

~~~ts
it('does not automatically import the first community or saved template', () => {
  expect(source).toContain('chooseGearTemplateImport')
  expect(source).not.toContain('const communityTemplate = data?.gear.communityTemplates.find')
})
it('saves the versioned gear/enhancement draft and clears rather than restores initial loadout', () => {
  expect(source).toContain("schemaRevision: 'gear-template-draft-v2'")
  expect(source).toContain('setEquipped({})')
  expect(source).toContain('setEnhancements({})')
  expect(source).not.toContain('setEquipped(initial)')
})
~~~

- [x] **Step 2: Run test to verify it fails**

Run: npm run test -- apps/mini-taro/src/pages/builds/gear-detail-page-contract.test.ts  
Expected: failures because current action imports the first item and reset restores equippedSet.

- [x] **Step 3: Save complete current configuration**

After resolveSelection verifies current draft, call templates.upsert with rawString: serializeGearTemplateDraft({ gearBySlot: equipped, enhancementBySlot: enhancements }); keep resolver intent/signature/stat snapshot in metadata. Saving stays disabled when no item is selected or resolver returns a problem.

- [x] **Step 4: Require explicit import choice**

~~~ts
const source = await chooseActionSheetEntry([
  { kind: 'saved', label: '我的保存（' + savedOptions.length + '）' },
  { kind: 'community', label: '社区高端玩家（' + communityOptions.length + '）' },
], (item) => item.label)
const selected = source?.kind === 'community'
  ? await chooseActionSheetEntry(communityOptions, (item) => item.label)
  : await chooseActionSheetEntry(savedOptions, (item) => item.label)
~~~

Saved imports parse full draft then call resolveSelection; community imports call communityTemplateImport only with selected exact ID and current manifest revision. Both retain request-fence stale protection and source-specific notice.

- [x] **Step 5: Clear rather than restore**

~~~ts
const reset = () => {
  requestFence.current.replaceDraft()
  candidateRequestId.current += 1
  setEquipped({})
  setEnhancements({})
  setCanonical({ loading: false })
  setStats({ loading: false })
  setCandidateOpen(false)
  setCandidates([])
  setSelectedSlot('')
  setDirty(Boolean(readiness.selectedCount))
  setWorkbenchNotice('已清空当前全部装备配置')
}
~~~

Disable reset when no item is selected. Do not restore server stat snapshot, replacement candidates, or initial loadout after clearing.

- [x] **Step 6: Update contracts and run tests**

Keep the existing three bottom action slots and target geometry. Record explicit source selection, payload-owned community provenance, and empty draft state.

Run: npm run test -- apps/mini-taro/src/pages/builds/gear-detail-page-contract.test.ts apps/mini-taro/src/pages/builds/gear-template-import-model.test.ts tests/builds-page.test.js tests/gear-workbench-state.test.js. Expected: PASS.

### Task 6: Verify, candidate smoke, and record release

**Files:**
- Create: artifacts/releases/2026-07-22-gear-template-projection/requirement.json
- Create: artifacts/releases/2026-07-22-gear-template-projection/evidence.json
- Create: artifacts/releases/2026-07-22-gear-template-projection/manifest.json
- Modify: docs/roadmap.md
- Modify: docs/roadmap/ideas.md

**Consumes:** Tasks 1–5 and final clean candidate head.

**Produces:** one task-scoped Harness packet, candidate evidence and user acceptance ledger. External collector/backfill is not_run unless user separately authorizes it.

- [x] **Step 1: Run development and final local verification**

~~~bash
python3 -m unittest tests.community_winner_projection_test tests.gear_public_contract_test \
  tests.gear_release_test tests.gear_release_store_test tests.gear_release_tool_test \
  tests.pg_gear_template_selectors_test tests.websim_payload_test \
  tests.community_template_import_test tests.postgres_cache_sync_test tests.news_backend_test -v
npm run test -- apps/mini-taro/src/pages/builds/gear-template-import-model.test.ts apps/mini-taro/src/pages/builds/gear-detail-page-contract.test.ts
npm run typecheck
npm run audit:ui-architecture
git diff --check
~~~

2026-07-22 local evidence: the scoped Python suite (including projection, release, PG selectors/sync, payload and import) passed; the two Taro page/model tests passed; `npm run typecheck`, `npm run lint`, and `git diff --check` passed.  `npm run audit:ui-architecture` still reports the pre-existing unrelated `TalentSimulatorComponents.module.scss` shared-width-clamping finding; it is not part of this task's diff.  The user-owned `apps/mini-taro/project.config.json` remains excluded from task changes.

- [x] **Step 2: Perform local code review**

Reject any diff that (a) exposes a baseline in communityTemplates, (b) lets frontend rank/select winners, (c) mutates talent winners from gear legality, (d) imports without exact ID/manifest binding, or (e) makes reset restore equippedSet.

Review correction: candidate fallback order is now persisted on the elected Talent row, observed profiles retain player identity through PG and SQLite paths, no source list is truncated, and the old single-player pilot cleanup no longer deletes other real observed players.

- [ ] **Step 3: Candidate deploy and smoke final head**

Record final commit/tree identity, keep WOW_DEPLOY_START_ASYNC_SYNCS=0, and inspect /health, /api/data/health, compact/full gear payload with two distinct heroKey, both exact community imports, rank-one-illegal fallback trace, 80 legal hero slots/no public baseline, timer/backflow, resolver and rollback identity. If a candidate source-set is incomplete, do not promote its Community Release.

- [ ] **Step 4: Run real WeChat key-path acceptance**

1. Select gear + enhancement, save, reload, and import that saved template with both retained.
2. Choose “导入 -> 我的保存” and explicitly select a non-first valid save.
3. Choose “导入 -> 社区高端玩家” and separately import each hero-labeled winner.
4. Choose “重置” and observe all 16 slots, enhancements, level and derived stats clear without restoring initial gear.

Record each result as accepted, pending, or explicit user waiver. Tests, HTTP 200, coverage 80/80, or a screenshot alone do not grant user acceptance.

## Self-Review

- **Spec coverage:** Tasks 4–5 implement save/import/clear; Tasks 1–3 turn shared 80 talent source identities into two legal equipment templates per class-spec; Task 6 covers current data truth, candidate release and real WeChat acceptance.
- **Trust coverage:** every public community branch is observed-only, resolver-verified, exact-ID imported and hero-scoped; fallback cannot alter talent truth or use baseline.
- **Compatibility coverage:** Task 2 makes the new reader understand active v1 release during code rollout, while v2 promotion is blocked until all required hero slots are valid.
- **Type consistency:** heroKey, talentWinnerId, gearProjectionMode, gearBySlot, and enhancementBySlot use the same spelling in source, release, API, model and page tasks.
