# WOW 小程序 UI 系统重建完整 Goal

## Summary

将当前 UI 工作从 `pass36 局部修复 / 像素调参 / 单页 scorecard` 重置为 `WOW 小程序 UI 系统重建`。旧 pass36/pass37 产物只保留为失败证据和诊断输入，不再作为通过依据。

目标是交付一版完整、真实可用、有 App 感、组件化、可验证的 WoW 小程序 UI vNext，覆盖首页资讯、职业专精、当前专精工作台、天赋、装备、SimC、炸鸡队长、任务、我的模板，并通过真实微信小程序截图、组件裁切、overlay、route smoke 和 scorecard 验收。

## Active Two-Part Goal

### Part 1: Codex Goal

Codex 当前执行 goal：停止以 pass36/pass37 局部修补、像素调参、单页 scorecard 或主观“变好看”为推进方式。当前线程只按 `WOW 小程序 UI 系统重建` 执行：先建立可复用、可测量、可解释的 UI 生产系统，再在单 surface active implementation permit 下接入真实页面。

执行顺序固定为：问题登记 -> 组件 owner -> imagegen 低语义素材 manifest -> 真实 WoW 素材 source map -> target lock -> 单 surface implementation permit -> component/browser precheck -> 真实微信小程序截图 -> overlay/red-zone/scorecard -> route smoke -> DevTools action ledger。没有 active permit 时，不做页面级 WXML/WXSS 修补；没有真实小程序运行证据时，不声称 `runtime_verified` 或 `final_accepted`。

### Part 2: Project Documentation Goal

项目文档 goal：把上述 UI 系统重建作为长期产品与工程控制面写进 `docs/roadmap.md`、`docs/roadmap/ideas.md`、`docs/plans/`、`docs/design/` 和测试。文档只记录方向、边界、证据、状态和下一步，不把 Codex 自信、imagegen 整页图、浏览器预检、旧 pass scorecard、单页截图或主观评分当成真实小程序验收。

状态晋级必须按证据分层：`draft / design_candidate / target_lock_proposal / component_contract_draft / asset_manifest_draft / component_precheck / runtime_verified / final_accepted`。任何 `runtime_verified / final_accepted` 都必须能回链到真实微信小程序截图、目标图、实现图、组件 crop、overlay、red-zone、scorecard、route smoke 和 DevTools action ledger。

## Current Two-Part Contract

1. Codex execution goal: 当前线程只按 `UI system rebuild` 方法推进。先建 owner、manifest、target lock、单 surface permit、component/browser precheck、真实小程序截图和 route smoke，再做页面接入；没有 active permit 时不得继续页面级拼形状或像素补丁。
2. Project documentation goal: 项目文档只记录长期方向和证据状态。roadmap、ideas、plans、design 和测试只能按证据升级，不能把 Codex 自信、imagegen 整页图、浏览器预检、旧 pass scorecard、单页截图或主观评分写成真实小程序验收。

## Design Read

Reading this as: a redesign-overhaul of a dense consumer mini program for WoW players, with a high-density Azeroth control-room language, leaning toward a custom component system rather than page-level patching.

Dial values for subsequent UI work: `DESIGN_VARIANCE=7`, `MOTION_INTENSITY=4`, `VISUAL_DENSITY=9`. This means the product should feel more authored and game-native than the current page set, but implementation must stay readable, compact, route-safe and evidence-driven on real mobile viewports.

## Goal Sync Snapshot

- Current Codex tool goal: `active`, objective already points to `WOW 小程序 UI 系统重建`.
- Codex tool limitation: an unfinished active goal cannot be rewritten through the goal tool; the current tool objective is directionally correct but not the exact two-part wording. Therefore this document and the two-part sync document are the exact project-side contract for the current active goal.
- Required split: `Codex Active Goal` defines how Codex executes the work in this thread; `Project Documentation Goal` defines what the repo roadmap, plans, design docs and tests are allowed to claim.
- 2026-07-07 two-part sync: [WOW 小程序 UI 系统重建 Two-Part Goal Sync](2026-07-07-wow-ui-system-two-part-goal-sync.md) records the copyable Codex goal first, then the project documentation goal, and keeps page integration blocked until target lock and active permit exist.
- 2026-07-07 activation guard: [WOW UI System Activation Guard](../design/2026-07-07-wow-ui-system-activation-guard.md) records `activationAllowed=false` because the target-locked decision record and first active implementation permit are absent.
- Non-goal: continuing pass36/pass37 pixel repair, single-page score chasing, page-private geometry patches, or treating imagegen full-screen mockups as production UI.

## Codex Active Goal

Tool status: Codex thread goal is currently `active` and already points to `WOW 小程序 UI 系统重建`. The Codex goal tool does not support rewriting the objective while an active goal is unfinished, so this file is the precise copyable goal contract for subsequent work.

### Copyable Goal

Codex 当前执行目标：停止 pass36/pass37 局部修补、像素调参和单页 scorecard 路线，改为先重建 WOW 小程序 UI 生产系统，再用该系统重做核心页面。执行时必须先完成盘点、问题登记、组件 owner、素材 manifest、target lock、implementation permit、browser/component precheck、真实小程序截图和 route smoke；页面实现只能在单 surface active permit 下进行，页面层不得继续拼状态徽章、按钮、卡片、素材留白、聊天气泡或组件内部几何。没有真实微信小程序截图、组件 crop、overlay、red-zone、scorecard、route smoke 和 DevTools action ledger 时，不得标记 runtime_verified 或 final_accepted。

### Short Version

Codex 当前执行目标：把 WOW 小程序 UI 优化从 pass36/pass37 局部修补重置为 UI 系统重建。先建立可验证的 App 级 UI 生产系统，再重做核心页面；每一步按“组件 owner -> 素材 manifest -> target lock -> 单 surface permit -> component/browser precheck -> 真实小程序截图 -> route smoke”推进。没有 active permit 不做页面级修补；没有真实小程序截图、组件 crop、overlay/red-zone、scorecard、route smoke 和 DevTools action ledger，不得标记 runtime_verified 或 final_accepted。

### Execution Contract

- Codex 执行目标只负责“怎么推进这次工作”：先建立可验证 UI 生产系统，再进入页面实现。
- 当前主线不再追 pass36/pass37 局部通过，不再靠单页截图、主观分数或像素补丁证明成功。
- Codex 可以推进文档、组件合同、素材 manifest、harness、测试、browser/component precheck 和验证脚本。
- 核心页面 WXML/WXSS 只能在单 surface active implementation permit 下修改。
- 每一步必须解释它如何避免已发生的问题复发：边距错乱、素材压内容、状态盾牌分裂、按钮压缩、卡片堆叠、重复 chrome、字体过小、队长页缺设计和路由未验证。

## Project Documentation Goal

项目文档目标：把 UI 系统重建写进 `docs/roadmap.md`、`docs/roadmap/ideas.md`、`docs/plans/`、`docs/design/` 和测试证据。文档只按证据升级状态，明确区分 `draft / design_candidate / target_lock_proposal / component_contract_draft / component_precheck / runtime_verified / final_accepted`，不能把 Codex 自信、浏览器预检、旧 pass scorecard、单页截图、主观评分或 imagegen 整页图当成真实小程序验收。

文档控制面只负责“这个项目长期承认什么方向和证据”：

- `docs/roadmap.md` 和 `docs/roadmap/ideas.md` 记录方向、状态、证据链接和待决策项。
- `docs/plans/` 记录执行 goal、阶段盘点、implementation permit 和历史失败证据。
- `docs/design/` 记录设计候选、target lock proposal、组件合同、素材 manifest 和 route smoke plan。
- 文档状态不得越级：没有真实运行证据时只能写 `draft / design_candidate / target_lock_proposal / component_contract_draft / asset_manifest_draft / route_smoke_plan_draft / component_harness_draft`。
- 任何 `runtime_verified / final_accepted` 必须对应真实微信小程序截图、组件 crop、overlay、red-zone、scorecard、route smoke 和 DevTools action ledger。

## Two-Part Goal Contract

1. Codex 执行 goal：控制当前工作方法，禁止继续 page-level 拼形状和旧 pass 局部修补，推动 owner、manifest、permit、precheck、runtime evidence。
2. 项目文档 goal：控制长期方向和证据晋级，禁止把草稿、浏览器预检、旧 scorecard、单页截图、主观评分或 imagegen 整页图写成 runtime verified / final accepted。

这条是线程执行目标和项目文档控制面的共同口径。它不把某个页面、某张设计图、某次 scorecard 当成最终目标，也不允许项目文档越级替代真实运行证据。

## Key Changes

- 重置执行目标：停止“继续修 pass36”的旧目标，替换为“先重建 UI 系统，再重做页面”。本地文档、线程 goal、执行计划必须一致，避免后续又被拉回旧局部验收线。
- 先解决系统问题：建立 `AppShell / PageFrame / WowPanel / MaterialImage / GameObjectIcon / StatusVisual / ActionButton / ModuleCard / ChannelDock / RankedFeed / EvidenceLedger / ChatShell` 等基础 owner，页面只组合组件、绑定数据和处理路由。
- 禁止页面级拼形状：核心页面不得继续用页面私有 class 修状态徽章、按钮、卡片、素材留白、gutter、输入区或聊天气泡。现有 `builds`、`workbench`、`chickenbro/simulator` 是重点返工对象。
- 队长页升为一等 surface：炸鸡队长不再只是聊天功能页，必须纳入完整设计和验收，覆盖 tab 首屏、工作台上下文承接、空会话、生成中、完成回复、失败态、回答依据、话题抽屉、新话题、输入区聚焦和长消息滚动。
- imagegen 改为真实素材工作流：整页图只做 reference；生产只使用 manifest 内的低语义切片，包括 panel、border、texture、socket、state-base、state-atomic、decorative。真实 WoW 职业、专精、天赋、装备、来源 logo 和事实图标只能来自真实接口、Battle.net/WebSim 映射、仓库验证资产或用户提供素材。
- 状态视觉组件化：`blocked / partial / ready / stale / source_reference / unknown` 必须共用同一组件合同。允许 `layered` 或 `atomic` 两种模式，但底座、glyph、整图、中心点、尺寸和透明边界都必须由组件 owner 管理，不能再出现盾牌和叹号分裂。
- 保留底部 tab 小程序形态：不得伪造系统状态栏、时间、电量、Wi-Fi、胶囊；页面布局必须围绕真实微信 tabBar、safe-area、顶部导航和键盘避让设计。
- 设计先行但必须可切：每个核心 surface 至少先产出 2-3 个差异明显的候选方向，用户确认后锁定一个 `target_locked`，再做红线、组件拆解、素材切片和适配策略。
- DevTools 低扰动验证：默认禁止关闭、重启、清缓存、切 appid、切项目、删除用户目录、粗暴 `cli open/close/auto`。所有 DevTools 动作写入 action ledger；`captureSafe=false` 时只能做 browser/component evidence。
- 不允许主观通过：禁止“差不多”“90 分左右”“看起来更好”。所有通过必须有真实截图、目标图、实现图、组件 crop、overlay、red-zone、scorecard 和 route smoke。

## Implementation Plan

### Phase 1: Inventory And Freeze

- 盘点当前页面、组件、素材、截图、scorecard、DevTools action。
- 冻结核心页面 WXML/WXSS 补丁，除非有新的 implementation permit。
- 将旧 pass36/pass37 标记为失败证据或诊断证据。

### Phase 2: Current Problem Register

- 输出当前问题清单：goal 不一致、组件 owner 缺失、页面拼形状、状态视觉失败、队长页未系统设计、底部 tab/导航边界不清、imagegen 生产流不合格、DevTools 流程扰动、route smoke 缺失。
- 任何后续执行必须先能解释这些问题为什么不会复发。

### Phase 3: Design Candidates

- 为以下 surface 产出候选并锁定方向：资讯首页、职业专精 tab、当前专精工作台、炸鸡队长、SimC 承接、任务/我的一致性。
- 候选必须使用相同产品事实，不伪造数据或真实 WoW 对象。
- 用户确认后，只保留一个 `target_locked`，其余进入 reference/quarantine。

### Phase 4: Foundation Components

- 建立组件合同和 fixture 矩阵，覆盖 compact / standard / large、长文本、缺图、空态、loading、error、blocked、partial、ready、stale、source_reference。
- 组件通过前不得接入页面。

### Phase 5: Asset Slicing And Manifest

- 用 imagegen 产出低语义素材并切片，建立生产 manifest、quarantine manifest、真实 WoW 素材 source map、文件大小预算和 fit 策略。
- 整页目标图、含文字图、含事实图、含伪真实图标的图只能作为 reference/quarantine。

### Phase 6: Surface Rebuild With Permits

- 每次只开放一个 implementation permit，声明目标 surface、owner 组件、允许文件、禁止文件、数据边界、素材条目、route smoke 和失败回退。
- 页面不得重写组件内部几何。

### Phase 7: Runtime Verification

- 先 browser/component precheck，再真实微信小程序截图。
- 每个核心场景输出当前/目标/实现对比、组件 crop、overlay、red-zone、scorecard、route smoke manifest 和 DevTools ledger。

## Test Plan

- 静态架构测试：检查核心页面是否使用 foundation components，禁止页面层重复实现 `Panel / Status / Button / Module / Evidence / Chat` 结构。
- 素材边界测试：扫描生产 WXML/WXSS/JS，禁止引用 reference-only、quarantine、整页目标图、伪 chrome、含文字或含事实的 imagegen 图。
- 数据可信测试：页面不得出现无来源 `DPS`、`综合评分`、`S/A 级`、`提升优先级`、伪官方来源、伪真实图标。
- 布局预检：browser harness 检查 gutter、slot rect、按钮高度、状态中心点、文本 overflow、横向溢出、图片 fit。
- 真实小程序截图：覆盖首页/资讯、职业 tab、工作台五状态、天赋、装备、SimC、队长、任务、我的模板，并包含 compact / standard / large 视口。
- 路由 smoke：覆盖进入、返回、tab 切换、频道切换、展开/收起、工作台到装备/天赋/SimC/队长、队长新话题/抽屉/输入区、任务详情、模板操作。
- DevTools 安全审计：每次真实验证都必须有 action ledger、captureSafe 记录、端口状态、禁止动作检查和登录态事故复盘入口。

## Acceptance Criteria

- active thread goal、本地 goal 文档、执行计划三者一致，不再以 pass36 局部目标驱动执行。
- 基础组件 owner 能解释并防止既有问题复发：边距错乱、状态盾牌分裂、按钮压缩、卡片堆叠、重复 chrome、字体过小、素材压内容。
- 队长页完成系统设计和验收，不再是旧聊天壳；回答依据映射为用户语言，不直接暴露 raw `answerSource / confidence / job.status`。
- imagegen 资产全部经过切片、语义降级、manifest、压缩和 fit 策略，真实 WoW 对象不由 imagegen 伪造。
- 所有核心页面保留真实功能和底部 tab 体验，首屏信息不因“变干净”被删掉。
- 每个核心 surface 都有真实小程序截图、组件 crop、overlay、red-zone、scorecard 和 route smoke。
- 没有严格证据时只能标记 `draft / design_locked / component_precheck / source evidence`，不能标记 `runtime_verified / final_accepted`。

## Active Goal Alignment

- 2026-07-07 当前 Codex 工具 active goal 已是 `WOW 小程序 UI 系统重建` 方向；本文件把它拆成 `Codex Active Goal` 和 `Project Documentation Goal` 两层，作为后续执行和文档同步的对齐口径。
- 仓库内本文件、Phase 1/2 inventory 文档和后续 implementation permit 必须与 active thread goal 保持一致。
- 旧 pass36/pass37 目标只作为失败证据、诊断证据和历史上下文，不再作为当前验收线或继续局部修补的依据。

## Assumptions

- 本轮不优先追求 pass36 旧 scorecard 通过，而是先让 UI 生产系统正确。
- 当前已有组件可以复用一部分，但需要重新定义 ownership；不能因为组件目录存在就视为组件化完成。
- 微信开发者工具登录态是用户资产，验证流程默认低扰动。
- imagegen 继续使用，而且是必要能力，但只作为素材生产和视觉语言探索，不负责真实数据、真实图标和业务判断。
- 后端接口和核心数据模型默认不改；如页面无法表达必要状态，另开后端契约计划。
