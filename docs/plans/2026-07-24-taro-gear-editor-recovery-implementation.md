# Taro 装备候选与强化编辑恢复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在活动 Taro `gear_detail` 中恢复“候选装备 → 后端合法等级轨道 → 显式应用 → canonical Resolve”以及“宝石/附魔/美化草稿 → 显式确认 → canonical Resolve”的可验证闭环。

**Architecture:** `detail.tsx` 只保存已确认装备、编辑草稿和请求时序；新的纯模型把后端候选 `variants` 和增强项投影为可选视图，并仅在确认时生成下一份 `gearBySlot` / `enhancementBySlot`。新的 design-system 编辑面板复用既有工作台区域，不拥有 API 或合法性。`gearResolve` 是唯一提交入口，成功才写入已确认状态。

**Tech Stack:** Taro 4、React、strict TypeScript、Vitest、`@wow-mini/domain`、`@wow-mini/design-system`、现有 `wowApi.websim.gear` 与 `gearResolve`。

## Global Constraints

- 只修改活动 owner `apps/mini-taro`、其 design-system 编辑表面、当前 UI 合同与本任务 release packet；`pages/builds/detail.js` 仅作语义参考，不能成为实现 owner。
- 初始编辑状态只读 `equippedSet`；`compact` catalog、候选数量和 item `simcReady` 不能被当作已装备、合法或就绪事实。
- 页面不得推断等级轨道、socket 数、唯一宝石、美化上限、来源质量或最终属性；只消费 `mode=slot` 返回的候选、`variants` 和 option fields。
- 每次候选/强化确认均调用 canonical `gearResolve`；只有 `status=resolved` 且 snapshot `verified` 才能提交本地已确认状态。
- 当前 `craftedStatOptions` 没有 Resolver 可校验的 ID，必须只读展示，不能映射为 `craftedOptionId` 或自造 `variantKey`。若此约束必须改变，停止本计划并按 Strict 开立后端 contract 任务。
- 外层页面继续锁定滚动；候选、详情和强化的滚动只能落在 `equipment_slots_panel` 内。
- 保留用户已有的 `apps/mini-taro/project.config.json` 本地修改，不得 stage、格式化或覆盖。

---

## File Structure

| 文件 | 责任 |
| --- | --- |
| `apps/mini-taro/src/pages/builds/gear-detail-editor-model.ts` | 安全解析候选轨道、候选草稿/应用投影、逐 socket 和单值增强草稿变更；不发请求。 |
| `apps/mini-taro/src/pages/builds/gear-detail-editor-model.test.ts` | 轨道、候选确认、强化草稿和失败不提交的纯函数回归。 |
| `apps/mini-taro/src/pages/builds/gear-detail-editor-commit-model.ts` | Resolve 成功、失败、409 与 stale completion 对已确认装备/强化和编辑草稿的纯状态转换。 |
| `apps/mini-taro/src/pages/builds/gear-detail-editor-commit-model.test.ts` | 草稿不提前提交、同槽强化清除、跨槽保留、失败/409/stale 不污染已确认状态的行为回归。 |
| `packages/design-system/src/components/GearEditorSheets.tsx` | 候选详情/轨道与强化编辑的 Taro 操作表面和 source-owned selector。 |
| `packages/design-system/src/components/GearEditorSheets.module.scss` | 编辑面板仅在工作台内部覆盖和滚动的视觉规则。 |
| `apps/mini-taro/src/pages/builds/detail.tsx` | 草稿生命周期、slot hydration、fence、Resolve 成功提交和错误反馈。 |
| `apps/mini-taro/src/pages/builds/gear-detail-model.ts` | 完整多 socket 已选态投影，玩家文案“美化”。 |
| `apps/mini-taro/src/pages/builds/gear-detail-model.test.ts` | 多 socket 选择态与“美化”摘要的显示合同。 |
| `apps/mini-taro/src/pages/builds/gear-detail-page-contract.test.ts` | 活动 owner、显式 apply/confirm、编辑面板与无 legacy 回流的结构合同。 |
| `docs/design/current-ui/{core-interaction-contract,selected-control-contract}.json` | 装备页真实微信核心交互和多 socket selected boundary。 |
| `docs/design/current-ui/routes/gear-detail/{truth-adaptation,component-contract}.json` | 编辑草稿、Resolver owner 与 workbench 内滚动的当前事实。 |
| `artifacts/releases/2026-07-24-taro-gear-editor-recovery/{requirement,evidence,manifest}.json` | Standard 任务 requirement、运行/验证/closure evidence 和不可变 manifest。 |

## Task 1: 冻结 Harness 任务合同和当前 UI 交互合同

**Files:**

- Create: `artifacts/releases/2026-07-24-taro-gear-editor-recovery/requirement.json`
- Modify: `docs/design/current-ui/core-interaction-contract.json`
- Modify: `docs/design/current-ui/selected-control-contract.json`
- Modify: `docs/design/current-ui/routes/gear-detail/truth-adaptation.json`
- Modify: `docs/design/current-ui/routes/gear-detail/component-contract.json`

**Interfaces:**

- Consumes: 已确认设计 `docs/plans/2026-07-24-taro-gear-editor-recovery-design.md`。
- Produces: `frontend_user_visible` 的 Standard requirement，以及 `gear_candidate_variant_apply`、`gear_enhancement_confirm` 两条冻结的人工验收项。

- [ ] **Step 1: 写入 requirement.json 的用户承诺与人工验收集合**

```json
{
  "schemaVersion": 1,
  "slug": "taro-gear-editor-recovery",
  "classification": "Standard",
  "status": "implementation_allowed",
  "goal": "Restore explicit candidate variant application and draft-confirmed gear enhancements in the active Taro gear detail route.",
  "manualAcceptanceContract": {
    "required": true,
    "requiredItemIds": [
      "gear_candidate_variant_apply",
      "gear_enhancement_confirm"
    ]
  },
  "releaseTrigger": "frontend_user_visible",
  "rollback": ["code_rollback"]
}
```

`impactMap.mustNotChange` 必须逐项列出 `server/`、PG、public payload、resolver owner、legacy page 和用户的 `project.config.json`；`evidenceRequired` 必须列出定向 Vitest、UI architecture audit、候选 head WeChat smoke 与两条人工验收项。

- [ ] **Step 2: 在 current UI 合同中替换不足的装备页交互覆盖**

将原本只覆盖职业 picker 的 `gear_detail` 交互保留，并新增：

```json
{
  "route": "gear_detail",
  "selectorValue": "gear-candidate-apply",
  "name": "choose a candidate, choose a returned variant, then apply it",
  "expected": "candidate click alone does not alter the equipped slot; only apply after a returned variant resolves updates the slot"
}
```

以及以 `gear-enhancement-confirm` 为 selector 的强化草稿确认项。`selected-control-contract.json` 中 `gear-enhancement-option` 保持单个编辑槽位内至多一个 active，但新增 `gear-enhancement-socket` 的 `boundaryMode=isolated`，允许多个 socket 各有一个选中项。

- [ ] **Step 3: 更新 route truth/component 合同**

明确 `GearEditorSheets` 的 owner 是工作台内部的候选详情和强化草稿；写入以下规则：

```text
candidate click -> local draft only
apply / confirm -> gearResolve -> verified snapshot -> committed UI
craftedStatOptions without a resolver-owned identifier -> display only, no selectable action
```

不要更改 target-only geometry、八个外层 region、16 个槽位或页面滚动规则。

- [ ] **Step 4: 验证 requirement 与 JSON 合同可解析**

Run:

```bash
node --check scripts/project-harness.js
node -e "for (const f of process.argv.slice(1)) JSON.parse(require('node:fs').readFileSync(f, 'utf8'));" \
  artifacts/releases/2026-07-24-taro-gear-editor-recovery/requirement.json \
  docs/design/current-ui/core-interaction-contract.json \
  docs/design/current-ui/selected-control-contract.json \
  docs/design/current-ui/routes/gear-detail/truth-adaptation.json \
  docs/design/current-ui/routes/gear-detail/component-contract.json
```

Expected: exit `0`; requirement 的两个 item id 不重复且后续 evidence 将逐项登记。

## Task 2: 建立纯候选轨道与强化草稿模型（TDD）

**Files:**

- Create: `apps/mini-taro/src/pages/builds/gear-detail-editor-model.ts`
- Create: `apps/mini-taro/src/pages/builds/gear-detail-editor-model.test.ts`
- Modify: `apps/mini-taro/src/pages/builds/gear-detail-model.ts`
- Modify: `apps/mini-taro/src/pages/builds/gear-detail-model.test.ts`

**Interfaces:**

- Consumes: `GearItemReference`、`GearEnhancementSelection` 和后端字段 `variants[]` / `craftedStatOptions[]`。
- Produces: `createCandidateDraft`, `selectCandidateVariant`, `candidateDraftCanApply`, `materializeCandidateDraft`, `setGemAtSocket`, `setSingleEnhancement`, `emptyEnhancementSelection`。

- [ ] **Step 1: 写失败的轨道/草稿测试**

```ts
it('keeps a candidate local until an explicit variant-backed apply', () => {
  const draft = createCandidateDraft('main_hand', weaponWithHeroAndMythTracks)
  expect(candidateDraftCanApply(draft)).toBe(false)

  const selected = selectCandidateVariant(draft, 'myth-289')
  expect(candidateDraftCanApply(selected)).toBe(true)
  expect(materializeCandidateDraft(selected)).toMatchObject({
    itemId: 'weapon-1', variantKey: 'myth-289', ilevel: 289,
  })
})

it('does not turn display-only craftedStatOptions into a resolver selection', () => {
  const draft = selectCandidateVariant(createCandidateDraft('main_hand', craftedWeapon), 'crafted-myth-285')
  expect(draft.craftedStatOptions).toHaveLength(2)
  expect(materializeCandidateDraft(draft)).not.toHaveProperty('craftedOptionId')
})
```

增加多 socket 测试：`setGemAtSocket(selection, 1, 'gem-b')` 只替换第二位；传入空 ID 移除对应位置；附魔/美化切换不影响 gems。运行：

```bash
npx vitest run apps/mini-taro/src/pages/builds/gear-detail-editor-model.test.ts
```

Expected: FAIL，因为模块尚不存在。

- [ ] **Step 2: 实现只消费后端字段的纯模型**

```ts
export interface GearCandidateDraft {
  readonly slot: string
  readonly candidate: GearItemReference
  readonly selectedVariantKey: string
  readonly variants: readonly GearCandidateVariantView[]
  readonly craftedStatOptions: readonly GearCraftedStatView[]
}

export function candidateDraftCanApply(draft: GearCandidateDraft): boolean {
  return Boolean(draft.selectedVariantKey && draft.variants.some((item) => item.key === draft.selectedVariantKey && item.state !== 'blocked'))
}
```

解析 `variants` 时只读取 array/object/string/number 的安全值，过滤 `needs-variant` 占位符，保留后端 `key|variantKey`、`difficultyLabel`、`itemLevel|ilevel`、状态和 blockers。`materializeCandidateDraft` 必须合并所选轨道的 item level、variant key、verified display fields 和 candidate 的 option arrays；不能把 `craftedStatOptions[].key`、`simcOptions` 或任意未知字段转换为 `craftedOptionId`。

`gear-detail-model.ts` 中将 `embellishment` 的用户标签改为 `美化`，并为 socket 摘要返回完整 `gemOptionIds` 的选中数量/标签，不再仅用第一个 gem 隐藏多插槽状态。

- [ ] **Step 3: 运行模型测试并做类型检查**

Run:

```bash
npx vitest run apps/mini-taro/src/pages/builds/gear-detail-editor-model.test.ts apps/mini-taro/src/pages/builds/gear-detail-model.test.ts
npm run typecheck
```

Expected: 两个测试文件通过，TypeScript 无错误。

## Task 3: 实现工作台内的候选详情与强化编辑表面（TDD）

**Files:**

- Create: `packages/design-system/src/components/GearEditorSheets.tsx`
- Create: `packages/design-system/src/components/GearEditorSheets.module.scss`
- Modify: `apps/mini-taro/src/pages/builds/gear-detail-page-contract.test.ts`

**Interfaces:**

- Consumes: Task 2 的 `GearCandidateDraft`、增强草稿和 view models。
- Produces: `GearCandidateEditorSheet` (`onSelectCandidate`、`onSelectVariant`、`onApply`、`onClose`) 与 `GearEnhancementEditorSheet` (`onSetGem`、`onSetSingle`、`onConfirm`、`onClose`)。

- [ ] **Step 1: 为 source-owned 交互标记写失败的页面合同测试**

```ts
expect(editorComponentSource).toContain('data-role="gear-candidate-row"')
expect(editorComponentSource).toContain('data-role="gear-candidate-variant"')
expect(editorComponentSource).toContain('data-action-id="gear-candidate-apply"')
expect(editorComponentSource).toContain('data-role="gear-enhancement-socket"')
expect(editorComponentSource).toContain('data-action-id="gear-enhancement-confirm"')
```

本任务只验证新组件的 source-owned controls 与工作台内滚动结构；候选 click 只更新 draft、而 `onApply` / `onConfirm` 才调用 `resolveSelection` 的页面断言留到 Task 4。运行：

```bash
npx vitest run apps/mini-taro/src/pages/builds/gear-detail-page-contract.test.ts
```

Expected: FAIL，因为新编辑组件和显式 action 尚不存在。

- [ ] **Step 2: 实现两个内部 sheet**

候选 sheet 每行只选择候选，右侧/下方显示候选来源、装等、属性摘要、blocker、后端轨道和 display-only 制造属性。轨道控件只渲染 `variants`；`应用`始终显示，只有 `candidateDraftCanApply` 为真且不 loading 时可点。

```tsx
<ControlButton
  data-action-id="gear-candidate-apply"
  data-role="gear-candidate-apply"
  disabled={!canApply || loading}
  onClick={onApply}
>
  应用装备
</ControlButton>
```

强化 sheet 按 `gemOptionIds.length` 渲染 socket 行；每行的 options 使用 `data-role="gear-enhancement-socket"` 和独立 `data-socket-index`。附魔和美化各使用单值选择区；取消不调用父级提交函数，确认按钮唯一使用 `data-action-id="gear-enhancement-confirm"`。样式用绝对覆盖的 `workbenchSheet` 和内部 `ScrollView`，不得添加 viewport 级弹窗或外层滚动。

- [ ] **Step 3: 让页面合同转绿并运行 UI 架构审计**

Run:

```bash
npx vitest run apps/mini-taro/src/pages/builds/gear-detail-page-contract.test.ts
npm run audit:ui-architecture
```

Expected: route owner 仍是 Taro / design-system，候选表面仍在 `equipment_slots_panel`，无 legacy source owner 回流。

## Task 4: 将 Taro 页面改为“草稿—Resolve—提交”状态机（TDD）

**Files:**

- Modify: `apps/mini-taro/src/pages/builds/detail.tsx`
- Modify: `apps/mini-taro/src/pages/builds/gear-detail-page-contract.test.ts`
- Modify: `apps/mini-taro/src/pages/builds/gear-request-fence.ts`（仅当现有 fence 无法区分 slot hydrate / resolve 时）
- Modify: `packages/design-system/src/components/GearDetailComponents.tsx`
- Modify: `scripts/verify-ui-interactions.js`
- Modify: `tests/taro-gear-editor-contracts.test.js`
- Create: `apps/mini-taro/src/pages/builds/gear-detail-editor-commit-model.ts`
- Create: `apps/mini-taro/src/pages/builds/gear-detail-editor-commit-model.test.ts`

**Interfaces:**

- Consumes: Task 2 model、Task 3 sheets、`wowApi.websim.gear({ compact:false, mode:'slot', slot })`、`GearRequestFence`、`gearResolve`。
- Produces: 已确认 `equipped` / `enhancements` 与可取消 `candidateDraft` / `enhancementDraft`；Resolve 仅在 apply/confirm 生效。

- [ ] **Step 1: 写失败的流程合同测试**

```ts
expect(pageSource).toContain('setCandidateDraft')
expect(pageSource).toContain('setEnhancementDraft')
expect(pageSource).toMatch(/const applyCandidateDraft = async \(\)[\s\S]*?await resolveSelection\(/u)
expect(pageSource).toMatch(/const confirmEnhancementDraft = async \(\)[\s\S]*?await resolveSelection\(/u)
expect(pageSource).toMatch(/const chooseCandidate = \(id: string\)[\s\S]*?setCandidateDraft/u)
expect(pageSource).not.toMatch(/const chooseCandidate = async[\s\S]*?await resolveSelection/u)
```

增加断言：`chooseEnhancement` 不能直接 Resolve；409 通过 `route.load()` 丢弃两个草稿；关闭/重置/导入递增 candidate request identity 并清空两类草稿。

写失败的纯行为测试并要求页面消费该 helper：未 Resolve、network/503 或 stale completion 时 candidate/enhancement draft 与已确认 `equipped` / `enhancements` 都保持；409 只清两个草稿并要求 reload；verified candidate completion 只替换目标 slot 并清空该 slot 强化；verified enhancement completion 只替换目标 slot 强化并保留其他 slot。无 `variants` 的后端合法候选仍产生 base materialization 并保留显式 Apply；交互 verifier 只在返回 variants 时选择轨道。

再为真实微信 smoke 写失败断言：每个 `gear-slot-row` 必须发布 `data-committed-item-id`，候选 row 发布 `data-candidate-item-id`，并且工作台发布 `data-gear-resolve-state`。`verify-ui-interactions.js` 的 `gear_detail` 分支在选候选/轨道后读取主手的 committed id，必须仍等于 apply 前值；点击 apply 后必须等待 `data-gear-resolve-state="verified"` 且 committed id 等于该候选 id。任何 Resolve 拒绝、409 或 stale completion 都不能把草稿 item id 发布为 committed id。

- [ ] **Step 2: 用 slot hydration 生成编辑输入**

将 `chooseSlot` 抽为“打开候选 sheet + 请求/缓存该 slot detail”；候选 request 返回后仅更新该 slot 的 editor data。打开强化条时，如果当前已装备物品没有完整 option arrays，先复用相同的 slot hydration，在响应中按 itemId 和已确认 variantKey 找精确候选；找不到时展示后端数据不足提示并禁用确认。

```ts
const applyCandidateDraft = async () => {
  const draft = candidateDraft
  const item = draft && materializeCandidateDraft(draft)
  if (!draft || !item) return
  const nextEquipped = { ...equipped, [draft.slot]: item }
  const nextEnhancements = removeSlotEnhancements(enhancements, draft.slot)
  const resolved = await resolveSelection(nextEquipped, nextEnhancements)
  if (resolved.status !== 'resolved') return
  setEquipped(nextEquipped)
  setEnhancements(nextEnhancements)
  setCandidateDraft(null)
}
```

候选 row、轨道和强化 option 只调用 `set*Draft`。`confirmEnhancementDraft` 以同样模式执行一次 Resolve，成功后才 `setEnhancements(next)`. 503/network 仅保留草稿和已确认 state；409 清草稿并 reload；stale completion 不更新任何 state。

`GearSlotWorkbench` 从已确认 `equipped` 接收并发布 `data-committed-item-id`，不得从 candidate draft 读取。页面把 canonical snapshot 的 verified / loading / error 状态映射为 `data-gear-resolve-state`；candidate sheet 关闭只能发生在 verified completion 后。更新微信交互执行器，按上一步的 stable markers 断言 draft 不提前提交、verified completion 后才提交，不能再只用“应用按钮消失”作为成功证据。

`data-gear-resolve-state` 在加载期间必须为 `resolving`，不能复用旧 snapshot 的 `verified`；额外发布 current resolved slot item ID。交互执行器在 apply 前记录 committed ID 与 resolved slot ID，apply 后要求新 `verified` completion 的 resolved slot item ID 与 candidate item ID 一致、且 committed ID 同时变为该值。这样旧 verified snapshot 或乐观提交不能伪造本次成功。

- [ ] **Step 3: 回归页面、模型和类型测试**

Run:

```bash
npx vitest run \
  apps/mini-taro/src/pages/builds/gear-detail-editor-model.test.ts \
  apps/mini-taro/src/pages/builds/gear-detail-model.test.ts \
  apps/mini-taro/src/pages/builds/gear-detail-page-contract.test.ts
npm run typecheck
npx eslint \
  apps/mini-taro/src/pages/builds/detail.tsx \
  apps/mini-taro/src/pages/builds/gear-detail-editor-model.ts \
  apps/mini-taro/src/pages/builds/gear-detail-model.ts \
  packages/design-system/src/components/GearEditorSheets.tsx --max-warnings=0
```

Expected: 所有 targeted tests、typecheck 和 lint 通过。

## Task 5: 固化 release evidence 并做最终前端验证

**Files:**

- Create: `artifacts/releases/2026-07-24-taro-gear-editor-recovery/evidence.json`
- Create: `artifacts/releases/2026-07-24-taro-gear-editor-recovery/manifest.json`
- Modify: `docs/plans/2026-07-24-taro-gear-editor-recovery-design.md`

**Interfaces:**

- Consumes: Task 1 requirement、最终 branch head、Task 2–4 tests。
- Produces: `local_verified` packet；runtime identity 保持 `pending` 直到精确候选 head 的真实微信 smoke。

- [ ] **Step 1: 运行最终本地验证矩阵**

Run:

```bash
git diff --check
npm run audit:ui-architecture
npm run typecheck
npm run test:taro
npm run build:weapp
node scripts/project-harness.js --json --write --date 2026-07-24 --slug taro-gear-editor-recovery
node scripts/project-harness.js --check \
  --requirement-file artifacts/releases/2026-07-24-taro-gear-editor-recovery/requirement.json \
  --evidence-file artifacts/releases/2026-07-24-taro-gear-editor-recovery/evidence.json \
  --manifest-file artifacts/releases/2026-07-24-taro-gear-editor-recovery/manifest.json \
  --base origin/main
```

Expected: format, architecture, type, unit and production WeChat build pass; manifest/evidence bind the clean exact head. Do not claim WeChat user acceptance from these commands.

- [ ] **Step 2: 完成一次本地 CR**

检查 diff 是否仅包含本计划 files、release packet、当前 UI 合同和活动 Taro/design-system owner；确认没有 `server/`、`pages/`、`project.config.json`、generated `dist/weapp` 或未经批准的依赖/下载内容。复跑任一被 CR 修正的定向测试。

- [ ] **Step 3: 记录候选 head 的待验收项**

在 evidence 中将 `gear_candidate_variant_apply` 与 `gear_enhancement_confirm` 保持 `pending`，直到真实微信端按精确 PR head 验证：

1. 主手候选点击不换装；选择一条后端返回的等级轨道并“应用”后才更新。
2. 无多轨道候选仍需要显式“应用”。
3. 多 socket 宝石、附魔和美化可编辑；取消无影响，确认后才更新；Resolver 拒绝时已确认装备不变。

只有用户明确回复“我已测试通过”“可以收尾”或“合入吧”后，才按 Harness User Acceptance Closure 更新 evidence、提交、合入和刷新 DevTools。

## Plan Self-Review

- Spec coverage: Task 2 覆盖候选轨道、显式应用、多个 gem 与“美化”显示；Task 3 覆盖当前 UI 内编辑控件；Task 4 覆盖 Resolver 成功/失败/409/fence；Task 1/5 覆盖合同、release、验证与人工验收。
- Intentional exclusion: 当前制造属性没有 canonical Resolver ID，因此不创建前端映射、不会把展示 `key` 写入 `craftedOptionId`；这保持 fail-closed，并避免隐性后端 scope expansion。
- Type consistency: `GearCandidateDraft` 在 Task 2 定义，Task 3 只消费，Task 4 只在 `materializeCandidateDraft` 成功后调用 Resolve；增强草稿始终是 `GearEnhancementSelection`。
- 占位标记扫描：未发现需要补充的占位步骤；每个代码任务都给出了接口、测试、命令和预期结果。
