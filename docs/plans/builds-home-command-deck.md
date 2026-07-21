# Builds Home 职业命令卡组 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将“专精”首页重构为职业选择器和四张平级命令卡，同时保持天赋、装备和 SimC 的既有 `spec` 启动协议。

**Architecture:** 首页只保存职业与每职业最近有效专精的轻量偏好。点击三个模拟入口时，shared pure resolver 用当前 canonical `builds.home` catalog 解析一个有效 `spec`，再沿用现有路由参数；任务不接收上下文。新的 `BuildClassSelector` 和 `BuildCommandDeck` 是该路由的组合组件，页面不再渲染旧概览、网格、工作台、重复列表或流程时间线。

**Tech Stack:** Taro + React + TypeScript、Vitest、现有 `@wow-mini/design-system`、canonical `builds.home` payload、Current UI Control Plane、WeChat DevTools。

## Global Constraints

- 只修改活动 Taro runtime `apps/mini-taro`、typed route/storage contract、current-ui route contract 和当前计划；根 `pages/` 保持兼容消费者。
- 不新增后端 API、模板 owner、任务 owner、SimC 提交语义或本地装备事实。
- 首页 ready 状态只展示职业胶囊和天赋/装备/SimC/任务四张卡；无编号、状态标签、模板准备信息、工作台横幅、重复入口或流程时间线。
- SimC 始终可进入；模板缺失只能在 SimC 页面表达和处理。
- `tasks_list` 不接收 `spec` 或职业参数；三个模拟入口继续只接收已解析的 `spec`。
- canonical target 的几何必须在隔离 target-only context 中测量；不得从 runtime、旧 CSS、概念稿或旧 redline 推导。
- 纯文档/合同变更只跑 Harness 定向验证；运行时变更在最终候选只跑一次适用 frontend profile，并完成真实 DevTools 核心路径。

---

## File Structure

| 文件 | 职责 |
| --- | --- |
| `apps/mini-taro/src/pages/_shared/build-context.ts` | 保持纯函数：职业选择、有效专精解析、无效偏好回退。 |
| `apps/mini-taro/src/pages/_shared/build-context-storage.ts` | 读取/写入 `selectedClassKey` 与 `lastSpecByClass`，不含 catalog 或导航逻辑。 |
| `apps/mini-taro/src/pages/builds/builds-home-model.ts` | 生成职业胶囊、13 职业选项和四张静态命令卡的展示模型。 |
| `packages/design-system/src/components/BuildClassSelector.tsx` | 职业胶囊和三列职业底部面板。 |
| `packages/design-system/src/components/BuildCommandDeck.tsx` | 四张横向命令卡和统一点击语义。 |
| `packages/design-system/src/components/BuildsHomeCommandDeck.module.scss` | 两个新 owner 的材质、布局、选中态和小屏几何。 |
| `apps/mini-taro/src/pages/builds/builds.tsx` | 首页 composition、职业持久化、启动专精解析和导航。 |
| `apps/mini-taro/src/pages/builds/builds-home.module.scss` | 首页只保留卡组和 selector 的 route-level 视口布局。 |
| `apps/mini-taro/src/pages/builds/talent-simulator.tsx`、`detail.tsx`、`simulator/simc.tsx` | 在工具内部确认专精后回写最近专精偏好。 |
| `packages/domain/src/route-contract.ts` | 为首页偏好登记 storage contract，并把其声明为 builds-home storage。 |
| `docs/design/current-ui/routes/builds-home/*.json` | 用新的 canonical target 更新 inventory、geometry、truth/component/asset contract。 |
| `docs/design/current-ui/*-contract.json` | 更新 builds-home 的 route geometry、语义区域、选中态和核心交互。 |

## Task 1: 生成新 canonical target 并更新目标合同

**Files:**

- Modify: `artifacts/ui-visual-targets/current/builds-home.png`
- Modify: `docs/design/current-ui/target-registry.json`
- Modify: `docs/design/current-ui/routes/builds-home/target-inventory.json`
- Modify: `docs/design/current-ui/routes/builds-home/target-geometry.json`
- Modify: `docs/design/current-ui/routes/builds-home/truth-adaptation.json`
- Modify: `docs/design/current-ui/routes/builds-home/component-contract.json`
- Modify: `docs/design/current-ui/routes/builds-home/asset-contract.json`
- Modify: `docs/design/current-ui/core-interaction-contract.json`
- Modify: `docs/design/current-ui/route-geometry-contract.json`
- Modify: `docs/design/current-ui/runtime-region-mapping-contract.json`
- Modify: `docs/design/current-ui/selected-control-contract.json`
- Test: `tests/project-state.test.js`

**Consumes:** 已确认的 [产品设计](../design/current-ui/routes/builds-home/product-design.md)。

**Produces:** `builds_home` 的新目标图、仅从该图测得的区域边界，以及四个命令卡和职业选择的可审计 UI 合同。

- [ ] **Step 1: 在隔离 target-only context 制作并确认目标图**

  以 390 CSS px 宽、首屏可见标题/职业胶囊/四卡/四列 TabBar 的构图制作新的 `builds-home.png`。目标图只表达以下 ready state：

  ```text
  职业专精        [职业图标 法师 ▾]
  天赋模拟        设计、导入与保存天赋模板                 ›
  装备模拟        搭配装备与增强方案                       ›
  SimC 模拟       组合模板并发起模拟                       ›
  任务查看        查看模拟任务与结果                       ›
  资讯 | 专精(唯一选中) | 队长 | 我的
  ```

  不读取现有 `builds-home.png`、runtime 截图、页面 CSS 或组件尺寸；记录 target 的 SHA-256、像素尺寸、测量时间和 `runtimeInputsUsed=false`。

- [ ] **Step 2: 对新 target 做独立 measurement**

  在 `target-inventory.json` 和 `target-geometry.json` 中仅登记从目标图读取的 region：`page_header`、`class_selector`、`command_deck`、`product_tab_bar`。在替换合同前运行：

  目标 measurement 只证明新 target 的几何事实，不授予 runtime、架构审计或微信视觉通过。

- [ ] **Step 3: 更新合同到新 topology**

  将 `component-contract.json` 的 stable region topology 固定为 header、class selector、command deck、tab bar；将 item IDs 固定为 `talents`、`gear`、`simc`、`tasks`；移除旧 overview/workspace/list/workflow owner 要求。`core-interaction-contract.json` 把 builds-home 核心交互改为点击 `data-role="build-class-selector"` 后选择一个职业并更新唯一选中态；`route-geometry-contract.json` 要求 `class_selector` 与 `command_deck`。

  `truth-adaptation.json` 明确：职业 catalog 来自 `BuildsHomePayload.classOptions`；首页不声明 source、template、任务或 SimC readiness；任务只导航到 `tasks_list`。`selected-control-contract.json` 为职业网格声明唯一选中态，且选中描边不改变任何 cell 或胶囊的 bounds。

- [ ] **Step 4: 验证合同控制面**

  ```bash
  node --test tests/project-state.test.js tests/project-harness.test.js
  npm run audit:ui-architecture
  ```

  预期：文档控制面测试通过；架构审计结果只作为当前 source 与新合同的差异报告，不得被表述为视觉通过。

- [ ] **Step 5: Commit**

  ```bash
  git add artifacts/ui-visual-targets/current/builds-home.png docs/design/current-ui
  git commit -m "design(ui): update builds home command deck target"
  ```

## Task 2: 建立职业上下文和启动专精 resolver

**Files:**

- Modify: `packages/domain/src/route-contract.ts`
- Modify: `apps/mini-taro/src/pages/_shared/build-context.ts`
- Create: `apps/mini-taro/src/pages/_shared/build-context-storage.ts`
- Create: `apps/mini-taro/src/pages/_shared/build-context.test.ts`
- Test: `apps/mini-taro/src/pages/_shared/build-context.test.ts`

**Consumes:** `BuildsHomePayload.classOptions` 和既有 `defaultSpecId`。

**Produces:** 纯 `resolveBuildsHomeLaunch`、持久化 `BuildsHomeContext` 和登记的 `builds.homeContext` storage key。

- [ ] **Step 1: 写 resolver 与 storage 的失败测试**

  ```ts
  it('keeps a valid remembered specialization for the selected class', () => {
    const launch = resolveBuildsHomeLaunch(payload(), {
      selectedClassKey: 'mage',
      lastSpecByClass: { mage: '法师-奥术' },
    })
    expect(launch?.selection.specId).toBe('法师-奥术')
  })

  it('falls back to the first valid specialization of the selected class', () => {
    const launch = resolveBuildsHomeLaunch(payload(), {
      selectedClassKey: 'mage',
      lastSpecByClass: { mage: '失效-专精' },
    })
    expect(launch?.selection.specId).toBe('法师-冰霜')
  })

  it('does not create a launch context when every class has no specialization', () => {
    expect(resolveBuildsHomeLaunch(emptyPayload(), emptyBuildsHomeContext())).toBeNull()
  })
  ```

- [ ] **Step 2: 运行测试确认失败**

  ```bash
  npm run test:taro -- apps/mini-taro/src/pages/_shared/build-context.test.ts
  ```

  预期：失败，因为 `resolveBuildsHomeLaunch`、`emptyBuildsHomeContext` 和 storage adapter 尚不存在。

- [ ] **Step 3: 最小实现纯 resolver 与 storage adapter**

  在 `route-contract.ts` 加入：

  ```ts
  { id: 'builds.homeContext', key: 'wow_builds_home_context_v1' }
  ```

  在 `build-context.ts` 导出：

  ```ts
  export interface BuildsHomeContext {
    selectedClassKey?: string
    lastSpecByClass: Readonly<Record<string, string>>
  }

  export interface BuildsHomeLaunch {
    classKey: string
    selection: SpecSelection
  }

  export function emptyBuildsHomeContext(): BuildsHomeContext
  export function resolveBuildsHomeLaunch(home: BuildsHomePayload, context: BuildsHomeContext): BuildsHomeLaunch | null
  ```

  在 `build-context-storage.ts` 导出：

  ```ts
  export function readBuildsHomeContext(storage?: StorageAdapter): BuildsHomeContext
  export function selectBuildsHomeClass(classKey: string, storage?: StorageAdapter): BuildsHomeContext
  export function rememberBuildsHomeSpec(
    selection: Pick<SpecSelection, 'classKey' | 'specId'>,
    context?: BuildsHomeContext,
    storage?: StorageAdapter,
  ): BuildsHomeContext
  ```

  `readBuildsHomeContext` 只接受 JSON object、非空 string class/spec key；损坏或旧结构返回 `emptyBuildsHomeContext()`。`resolveBuildsHomeLaunch` 先使用有效的 `selectedClassKey` 和其有效记忆，再使用该职业第一个有效专精；失效职业回退到含 `defaultSpecId` 的职业，再回退到首个有专精的职业。

- [ ] **Step 4: 运行 resolver 测试**

  ```bash
  npm run test:taro -- apps/mini-taro/src/pages/_shared/build-context.test.ts
  ```

  预期：所有 resolver、损坏存储、跨职业隔离和全量缺失案例通过。

- [ ] **Step 5: Commit**

  ```bash
  git add packages/domain/src/route-contract.ts apps/mini-taro/src/pages/_shared/build-context.ts apps/mini-taro/src/pages/_shared/build-context-storage.ts apps/mini-taro/src/pages/_shared/build-context.test.ts
  git commit -m "feat(builds): add class launch context"
  ```

## Task 3: 用纯命令卡模型替换首页展示模型

**Files:**

- Modify: `apps/mini-taro/src/pages/builds/builds-home-model.ts`
- Modify: `apps/mini-taro/src/pages/builds/builds-home-model.test.ts`

**Consumes:** `resolveBuildsHomeLaunch`、`BuildsHomePayload.quickActions`、职业 catalog。

**Produces:** 无状态标签的 `classOptions`、`selectedClassKey`、`launchSpecId` 和固定四项 `commandItems`。

- [ ] **Step 1: 写失败模型测试**

  ```ts
  it('renders exactly four command cards without status or readiness fields', () => {
    const model = buildBuildsHomeModel({ payload: payload(), routeState: 'ready', context: emptyBuildsHomeContext() })
    expect(model.commandItems.map((item) => item.id)).toEqual(['talents', 'gear', 'simc', 'tasks'])
    expect(JSON.stringify(model.commandItems)).not.toMatch(/stateLabel|statusLabel|准备|未校验/u)
  })

  it('keeps tasks independent while simulators expose the resolved launch spec', () => {
    const model = buildBuildsHomeModel({ payload: payload(), routeState: 'ready', context: { selectedClassKey: 'mage', lastSpecByClass: {} } })
    expect(model.commandItems.find((item) => item.id === 'tasks')?.specId).toBeUndefined()
    expect(model.commandItems.find((item) => item.id === 'simc')?.specId).toBe('法师-冰霜')
  })
  ```

- [ ] **Step 2: 运行测试确认失败**

  ```bash
  npm run test:taro -- apps/mini-taro/src/pages/builds/builds-home-model.test.ts
  ```

  预期：失败，因为旧 model 仍生成 `specialization`、`evidenceItems`、`workspace` 和 `workflow`。

- [ ] **Step 3: 最小改写 model**

  将旧的 `BuildsHomeEvidenceView`、workspace、workflow 和来源/ready copy 删除，改为：

  ```ts
  export interface BuildsHomeCommandItem {
    id: 'talents' | 'gear' | 'simc' | 'tasks'
    title: '天赋模拟' | '装备模拟' | 'SimC 模拟' | '任务查看'
    detail: string
    glyphAssetId: ProductionAssetId
    fallbackGlyphAssetId: ProductionAssetId
    specId?: string
    disabled: boolean
  }
  ```

  `classOptions` 每项包含 `classKey`、职业名、可选 icon URL、`disabled` 与 `selected`；只有没有有效专精的职业被置灰。loading/error/blocked 继续交给 route-level state，不向 command item 注入标签。

- [ ] **Step 4: 运行模型测试**

  ```bash
  npm run test:taro -- apps/mini-taro/src/pages/builds/builds-home-model.test.ts apps/mini-taro/src/pages/_shared/build-context.test.ts
  ```

  预期：固定顺序、职业回退、任务无 `specId`、三个模拟器有有效 `specId` 和旧模型回归测试全部通过。

- [ ] **Step 5: Commit**

  ```bash
  git add apps/mini-taro/src/pages/builds/builds-home-model.ts apps/mini-taro/src/pages/builds/builds-home-model.test.ts
  git commit -m "feat(builds): model command deck home"
  ```

## Task 4: 新增职业选择器和命令卡共享组件

**Files:**

- Create: `packages/design-system/src/components/BuildClassSelector.tsx`
- Create: `packages/design-system/src/components/BuildCommandDeck.tsx`
- Create: `packages/design-system/src/components/BuildsHomeCommandDeck.module.scss`
- Modify: `packages/design-system/src/index.ts`
- Create: `packages/design-system/src/components/BuildsHomeCommandDeck.test.ts`

**Consumes:** Task 3 的 `classOptions`、`commandItems` 和现有 `ProductionAssetGlyph`、`SystemGlyph`、`ControlButton`、`ForgedPanel`。

**Produces:** `data-role="build-class-selector"`、`data-role="build-class-option"`、`data-role="build-command-card"` 三类稳定交互标记。

- [ ] **Step 1: 写共享组件 contract 测试**

  ```ts
  expect(read('BuildClassSelector.tsx')).toContain('data-role="build-class-selector"')
  expect(read('BuildClassSelector.tsx')).toContain('data-role="build-class-option"')
  expect(read('BuildCommandDeck.tsx')).toContain('data-role="build-command-card"')
  expect(read('BuildCommandDeck.tsx')).not.toMatch(/stateLabel|statusLabel|准备状态/u)
  ```

- [ ] **Step 2: 运行测试确认失败**

  ```bash
  npm run test:taro -- packages/design-system/src/components/BuildsHomeCommandDeck.test.ts
  ```

  预期：失败，因为组件和稳定选择器尚不存在。

- [ ] **Step 3: 实现 `BuildClassSelector`**

  组件 props 固定为：

  ```ts
  export interface BuildClassSelectorOption {
    id: string
    label: string
    iconUrl?: string
    disabled: boolean
    selected: boolean
  }

  export interface BuildClassSelectorProps {
    options: readonly BuildClassSelectorOption[]
    disabled?: boolean
    value: string
    onSelect: (id: string) => void
  }
  ```

  用本地 `open` state 渲染职业胶囊、遮罩和三列面板。每次点击可用 option 先调用 `onSelect(id)` 再关闭面板；遮罩和取消按钮只关闭。职业 icon 优先用 catalog 的 `iconUrl`，加载失败时显示职业名称首字的金属圆形 fallback。选中态只能改变颜色/描边，不改变 grid cell 或标题胶囊的几何。

- [ ] **Step 4: 实现 `BuildCommandDeck`**

  ```ts
  export interface BuildCommandDeckItem {
    id: 'talents' | 'gear' | 'simc' | 'tasks'
    title: string
    detail: string
    glyphAssetId: ProductionAssetId
    fallbackGlyphAssetId: ProductionAssetId
    disabled: boolean
  }

  export function BuildCommandDeck(props: {
    items: readonly BuildCommandDeckItem[]
    loading?: boolean
    onSelect: (id: BuildCommandDeckItem['id']) => void
  }): JSX.Element
  ```

  卡片必须按传入数组顺序渲染四次；每张使用 `ControlButton`、左图标、中间 title/detail、右侧 `utility-glyph-family.chevron-right`。不渲染任何状态、数量、编号或 SimC 专有标记。

- [ ] **Step 5: 导出并验证组件**

  ```bash
  npm run test:taro -- packages/design-system/src/components/BuildsHomeCommandDeck.test.ts
  ```

  预期：稳定 data-role、无状态字段和共享 exports 全部通过。

- [ ] **Step 6: Commit**

  ```bash
  git add packages/design-system/src/components/BuildClassSelector.tsx packages/design-system/src/components/BuildCommandDeck.tsx packages/design-system/src/components/BuildsHomeCommandDeck.module.scss packages/design-system/src/components/BuildsHomeCommandDeck.test.ts packages/design-system/src/index.ts
  git commit -m "feat(ui): add builds command deck components"
  ```

## Task 5: 重组首页并保持现有导航协议

**Files:**

- Modify: `apps/mini-taro/src/pages/builds/builds.tsx`
- Modify: `apps/mini-taro/src/pages/builds/builds-home.module.scss`
- Create: `apps/mini-taro/src/pages/builds/builds-home-page-contract.test.ts`

**Consumes:** Tasks 2–4。

**Produces:** 只包含 class selector 和 command deck 的 `BuildsHomePage`，以及三个模拟器的既有 `spec` navigation。

- [ ] **Step 1: 写页面 contract 失败测试**

  ```ts
  expect(source).toContain('<BuildClassSelector')
  expect(source).toContain('<BuildCommandDeck')
  expect(source).not.toContain('BuildSpecializationOverview')
  expect(source).not.toContain('BuildEvidenceNavigator')
  expect(source).not.toContain('BuildWorkspaceEntry')
  expect(source).not.toContain('BuildWorkflowTimeline')
  expect(source).toContain("id === 'tasks' ? {} : { spec: item.specId }")
  ```

- [ ] **Step 2: 运行测试确认失败**

  ```bash
  npm run test:taro -- apps/mini-taro/src/pages/builds/builds-home-page-contract.test.ts
  ```

  预期：失败，因为旧页面仍含五个冗余 region。

- [ ] **Step 3: 最小重组 `BuildsHomePage`**

  - 删除 `Picker`、旧五个 builds-home owner imports、`openWorkflow` 与 `useWorkspaceAction`。
  - 用 `readBuildsHomeContext()` 初始化 context；职业选择时调用 `selectBuildsHomeClass()` 后更新 React state。
  - 调用 `buildBuildsHomeModel({ payload, routeState, context })`。
  - 对天赋/装备/SimC 调用既有 `navigateTo`，参数分别为 `{ spec: item.specId }`、`{ spec: item.specId, query: 'gear' }`、`{ spec: item.specId, from: 'builds' }`；任务调用 `navigateTo('/pages/simulator/tasks', { from: 'builds' })`。
  - analytics 保持 `builds_query_open`，只在三个模拟项包含解析后的 `specId`。
  - 通过 `RouteStage`/共享 error state 表达 loading、blocked、error；ready 卡片不含状态 copy。

- [ ] **Step 4: 实现首页 route CSS**

  `surface` 只保留 `classSelectorRegion` 与 `commandDeckRegion`。使用 `min-height: 0`、`overflow: hidden`、弹性卡片行和 shell content viewport，使 390×830 基线以及最小支持安全区下第四张卡不被 TabBar 覆盖；没有 `overflow-y: auto` 或 route-private fixed TabBar。

- [ ] **Step 5: 运行页面与模型测试**

  ```bash
  npm run test:taro -- apps/mini-taro/src/pages/builds/builds-home-page-contract.test.ts apps/mini-taro/src/pages/builds/builds-home-model.test.ts apps/mini-taro/src/pages/_shared/build-context.test.ts
  ```

  预期：四卡 composition、任务独立导航、职业持久化和无旧 owner imports 全部通过。

- [ ] **Step 6: Commit**

  ```bash
  git add apps/mini-taro/src/pages/builds/builds.tsx apps/mini-taro/src/pages/builds/builds-home.module.scss apps/mini-taro/src/pages/builds/builds-home-page-contract.test.ts
  git commit -m "feat(builds): compose class command deck home"
  ```

## Task 6: 从三个模拟工具回写最近专精

**Files:**

- Modify: `apps/mini-taro/src/pages/builds/talent-simulator.tsx`
- Modify: `apps/mini-taro/src/pages/builds/detail.tsx`
- Modify: `apps/mini-taro/src/pages/simulator/simc.tsx`
- Modify: `apps/mini-taro/src/pages/builds/talent-simulator-page-contract.test.ts`
- Modify: `apps/mini-taro/src/pages/simulator/simc-page-contract.test.ts`
- Create: `apps/mini-taro/src/pages/builds/build-context-writeback.test.ts`

**Consumes:** Task 2 的 `rememberBuildsHomeSpec`。

**Produces:** 任一工具加载或切换到有效专精后，下一次首页启动继承该职业最近专精。

- [ ] **Step 1: 写失败测试**

  ```ts
  it('records the resolved specialization without sharing hero, template, draft, or submission state', () => {
    const context = rememberBuildsHomeSpec({ classKey: 'mage', specId: '法师-火焰' }, emptyBuildsHomeContext(), memoryStorage())
    expect(context.lastSpecByClass).toEqual({ mage: '法师-火焰' })
    expect(JSON.stringify(context)).not.toMatch(/hero|template|draft|submission/u)
  })

  expect(read('talent-simulator.tsx')).toContain('rememberBuildsHomeSpec(data.selection)')
  expect(read('detail.tsx')).toContain('rememberBuildsHomeSpec(data.selection)')
  expect(read('simc.tsx')).toContain('rememberBuildsHomeSpec(data.selection)')
  ```

- [ ] **Step 2: 运行测试确认失败**

  ```bash
  npm run test:taro -- apps/mini-taro/src/pages/builds/build-context-writeback.test.ts apps/mini-taro/src/pages/builds/talent-simulator-page-contract.test.ts apps/mini-taro/src/pages/simulator/simc-page-contract.test.ts
  ```

  预期：失败，因为三个工具尚未写回 shared context。

- [ ] **Step 3: 最小添加 writeback effect**

  在每个页面中，在该页 `data.selection` 已完成且 class/spec identity 变化时调用：

  ```ts
  const resolvedClassKey = data?.selection.classKey
  const resolvedSpecId = data?.selection.specId
  useEffect(() => {
    if (data?.selection) rememberBuildsHomeSpec(data.selection)
  }, [resolvedClassKey, resolvedSpecId])
  ```

  不修改 hero selector、template selector、SimC buildContext 或 gear draft；writeback 不触发 `route.load()`、导航或后端请求。

- [ ] **Step 4: 运行工具 contract 测试**

  ```bash
  npm run test:taro -- apps/mini-taro/src/pages/builds/build-context-writeback.test.ts apps/mini-taro/src/pages/builds/talent-simulator-page-contract.test.ts apps/mini-taro/src/pages/simulator/simc-page-contract.test.ts
  ```

  预期：三个工具均只回写 class/spec 映射，现有专精、英雄、模板和 SimC contract 继续通过。

- [ ] **Step 5: Commit**

  ```bash
  git add apps/mini-taro/src/pages/builds/talent-simulator.tsx apps/mini-taro/src/pages/builds/detail.tsx apps/mini-taro/src/pages/simulator/simc.tsx apps/mini-taro/src/pages/builds/build-context-writeback.test.ts apps/mini-taro/src/pages/builds/talent-simulator-page-contract.test.ts apps/mini-taro/src/pages/simulator/simc-page-contract.test.ts
  git commit -m "feat(builds): remember simulator specialization context"
  ```

## Task 7: 运行时验证、候选微信检查和收口

**Files:**

- Modify only if verification reveals a scoped defect: Task 2–6 ownership files and builds-home current-ui contracts.
- Test: targeted Vitest files、`npm run typecheck`、`npm run audit:ui-architecture`、`npm run verify:ui-route-geometry`、`npm run verify:ui-selected-states`。

**Consumes:** Tasks 1–6 的完整 candidate。

**Produces:** 可审计的本地验证、真实微信核心路径结果和用户 acceptance 所需的清晰证据。

- [ ] **Step 1: 跑完整定向测试集**

  ```bash
  npm run test:taro -- apps/mini-taro/src/pages/_shared/build-context.test.ts apps/mini-taro/src/pages/builds/builds-home-model.test.ts apps/mini-taro/src/pages/builds/builds-home-page-contract.test.ts apps/mini-taro/src/pages/builds/build-context-writeback.test.ts packages/design-system/src/components/BuildsHomeCommandDeck.test.ts apps/mini-taro/src/pages/builds/talent-simulator-page-contract.test.ts apps/mini-taro/src/pages/simulator/simc-page-contract.test.ts
  ```

  预期：全部通过。

- [ ] **Step 2: 跑前端静态和 UI 合同验证**

  ```bash
  npm run typecheck
  npm run audit:ui-architecture
  npm run verify:ui-route-geometry
  npm run verify:ui-selected-states
  ```

  预期：命令 exit 0；任何 contracts/evidence 缺口保持 `UNVERIFIED`，不把静态通过表述为微信视觉通过。

- [ ] **Step 3: 构建候选小程序并进行真实 DevTools 检查**

  ```bash
  npm run build:weapp
  UI_REVIEW_ROUTES=specialization_home/builds_home npm run capture:ui-review-cache
  ```

  预期：build 通过；在真实 DevTools 中验证四卡首屏、职业面板、选择职业、天赋/装备/SimC 带入最近专精、任务不带参数。捕获失败或 DevTools 不可用时保持 `UNVERIFIED` 并明确人工接管，不伪造截图或 acceptance。

- [ ] **Step 4: 本地 CR 与最终 commit**

  ```bash
  git diff main...HEAD --check
  git diff main...HEAD -- apps/mini-taro/src/pages/builds packages/design-system/src/components packages/domain/src/route-contract.ts docs/design/current-ui
  git status --short
  git add apps/mini-taro/src/pages/_shared/build-context.ts apps/mini-taro/src/pages/_shared/build-context-storage.ts apps/mini-taro/src/pages/_shared/build-context.test.ts apps/mini-taro/src/pages/builds/builds.tsx apps/mini-taro/src/pages/builds/builds-home-model.ts apps/mini-taro/src/pages/builds/builds-home.module.scss apps/mini-taro/src/pages/builds/talent-simulator.tsx apps/mini-taro/src/pages/builds/detail.tsx apps/mini-taro/src/pages/simulator/simc.tsx apps/mini-taro/src/pages/builds/builds-home-page-contract.test.ts apps/mini-taro/src/pages/builds/build-context-writeback.test.ts apps/mini-taro/src/pages/builds/builds-home-model.test.ts apps/mini-taro/src/pages/builds/talent-simulator-page-contract.test.ts apps/mini-taro/src/pages/simulator/simc-page-contract.test.ts packages/design-system/src/components/BuildClassSelector.tsx packages/design-system/src/components/BuildCommandDeck.tsx packages/design-system/src/components/BuildsHomeCommandDeck.module.scss packages/design-system/src/components/BuildsHomeCommandDeck.test.ts packages/design-system/src/index.ts packages/domain/src/route-contract.ts docs/design/current-ui artifacts/ui-visual-targets/current/builds-home.png
  git diff --cached --quiet || git commit -m "feat(builds): finalize class command deck"
  ```

  预期：无未解决的 P0/P1 本地 CR finding；只提交本计划范围内文件。

- [ ] **Step 5: 请求真实用户验收**

  报告 commit、验证命令、DevTools 状态和以下人工检查：职业面板仅含职业；四张卡首屏可见且无纵向滑动；SimC 首页无模板状态；任务不继承职业；三个模拟工具能继承最近专精。等待用户明确“已测试通过”“可以收尾”或等价授权后，才执行 Harness 的合并、推送和 DevTools 刷新收口。
