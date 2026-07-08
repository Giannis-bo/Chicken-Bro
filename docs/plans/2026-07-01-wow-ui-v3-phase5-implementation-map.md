# WoW 小程序 UI v3 Phase 5 实施映射

> 本文是 Phase 5 开工前的实施地图。依据：[v3 设计语言](../design/2026-07-01-wow-ui-v3-design-language.md)、[v3 Phase 4 评测记录](../reviews/2026-07-01-wow-ui-v3-phase4-review.md)、[v3 对比图 manifest](../../artifacts/ui-v3-comparison/20260701-phase3/manifest.json)。
> 约束：用户确认修正版 v3 目标稿前，不改真实小程序页面。

> 2026-07-02 更新：用户否定原 v3 目标图，原因是布局乱、内部元素溢出、背景杂乱，且整体不如早前重 UI 资产方向。随后 v3.1 重 UI 壳图也被否定，原因是返回按钮与顶部装饰/文字冲突、文字发虚、间距混乱，且继续向更差方向发展。Phase 5 不再以 `artifacts/ui-v3-comparison/20260701-phase3` 或 `artifacts/ui-v3-1-comparison/20260702-heavy-ui-reset` 为实施确认稿；下一步必须先产出真实小程序尺寸的低保真结构线框，通过布局 CR 后再进入视觉稿。

## 当前判断

现有代码已经有一版工作台、职业 tab、资讯、SimC 和 Chickenbro 的暗色控制台结构，适合直接演进到 v3，不需要重造页面或改后端。主要差距是：

- 页面仍使用 `assets/generated/ui-redesign/20260701/*` 旧素材，而不是 v3 抽象布局素材。
- 工作台状态模型里仍有 `iconFallback: 'S'` 和 `formatCount(..., ' 槽')` 这类会被误读的表达。
- 职业 tab 的工作台入口只有泛化标签，没有 readiness、模板数和状态驱动 CTA。
- 资讯滚动列表仍是 highlight card 堆叠，还没有成为 source ledger。
- SimC 页面结构已接近目标，但 context bridge、公共目录 vs 个人模板文案仍需收敛。
- Chickenbro 页面已有证据区，但 answerSource/confidence/job 等字段需要产品化映射，不能暴露工程口径。
- 原 v3 与 v3.1 目标图均不能直接实施。下一步必须先解决真实组件盒模型、导航安全区、返回按钮、标题、间距和首屏信息顺序。

## 实施总原则

- 不改后端数据模型，除非前端无法表达必要状态。
- 保留现状快速浏览信息，不为了视觉删掉模板数、checkedAt、blockers、coverage、来源。
- 不引入假职业、假专精、假天赋、假装备图标。
- 不出现无证据 DPS、综合评分、S/A 级、提升优先级。
- imagegen 素材只能作为低透明背景、轨道、面板、空态或布局承托。
- 真实对象图标优先来自 `gameAsset.iconUrl`、接口 `iconUrl` 或受控真实资产索引；缺图用文字 fallback。

## 实施切片

### 1. Shared v3 Surface

目标：先统一素材和状态 token，后续页面不再各自调一套黑金卡。

文件：

- `app.wxss`
- `pages/common/game-asset.js`
- `assets/generated/ui-v3/20260701/manifest.json`
- 页面 WXSS 中引用旧素材的位置

动作：

- 新增或整理 v3 语义类：`v3-cockpit`、`v3-object-plate`、`v3-readiness-slab`、`v3-status-rail`、`v3-evidence-drawer`、`v3-source-ledger`、`v3-context-bridge`。
- 页面素材迁移到 `assets/generated/ui-v3/20260701/*`：
  - `command-board-material-mobile.jpg`
  - `readiness-slab-material-mobile.jpg`
  - `workflow-rail-material-mobile.jpg`
  - `evidence-drawer-material-mobile.jpg`
  - `context-bridge-material-mobile.jpg`
  - `source-ledger-material-mobile.jpg`
- 保留旧 `ui-redesign` 素材为历史探索，不再用于 v3 页面主结构。
- 所有背景图必须有独立 scrim，文本不可直接压在图片上。

验收：

- WXML/WXSS 不把 imagegen 素材当真实对象图标。
- 所有固定底部 action 和 chat composer 使用 `env(safe-area-inset-bottom)`。

### 2. 当前专精工作台

目标：优先实施 v3 主体验，让首屏回答“当前能否模拟、为什么、下一步去哪”。

文件：

- `pages/builds/workbench-state.js`
- `pages/builds/workbench.wxml`
- `pages/builds/workbench.wxss`
- `tests/builds-workbench-state.test.js`
- `tests/builds-page.test.js`

动作：

- 修改 `buildSimcState()`：SimC fallback 从 `S` 改为 `Sim` 或中性模拟器文字，避免 S 级误读。
- 拆分装备表达：
  - `catalogCoverageLabel`：装备目录覆盖，例如 `目录 190/206`。
  - `equippedCoverageLabel`：已装备槽位，例如 `已装备 7/16`。
  - `missingSlotsLabel`：头部、颈部、肩部等缺口。
  - 不再把目录覆盖写成“装备槽位”。
- 工作台首屏保留：
  - 当前职业 / 专精 / 英雄天赋 / 场景。
  - readiness。
  - checkedAt。
  - 主 blocker。
  - 主 action。
  - 天赋、装备、SimC、队长四模块。
  - 模板数。
  - 证据摘要。
- 证据展开分组为天赋证据、装备证据、队长规则。
- 长缺口默认截断，证据展开展示完整列表。

验收：

- WXML 不出现 `190/206 槽`、`S 级`、`提升优先级`。
- `blocked` 态不是错误页，仍显示 action 与模块状态。
- `source_reference`、`partial`、`blocked`、`verified` 色彩语义一致。

### 3. 职业专精 Tab

目标：从工具入口集合升级为当前专精工作流入口，旧四入口仍保留。

文件：

- `pages/builds/builds.js`
- `pages/builds/builds.wxml`
- `pages/builds/builds.wxss`
- `tests/builds-page.test.js`

动作：

- `buildWorkbenchEntry()` 增加状态字段：
  - `stateLabel`
  - `stateClass`
  - `primaryActionLabel`
  - `templateCounts`
  - `specIconUrl` 或文字 fallback
- blocked 态 CTA 显示 `补装备` 或 `继续补齐`，ready 态显示 `去校验`。
- 避免过度承诺 WCL、高端玩家、最优构筑；改成“来源状态明确的天赋目录与个人模板”。
- 工作流入口文案保持：天赋构筑、装备模拟、模拟 SimC、任务列表。

验收：

- 工作台入口仍在构筑流程入口之前。
- 旧四入口仍存在。
- 主 CTA 和 readiness 状态绑定，不再只写 `进入`。

### 4. 资讯首页和滚动列表

目标：让资讯成为 source ledger，而不是深色卡片流。

文件：

- `pages/news/news.js`
- `pages/news/news.wxml`
- `pages/news/news.wxss`
- `tests/news-page-style.test.js`

动作：

- 顶部继续保留来源数、频道数、重点数、更新时间。
- hero 新闻不占满首屏，下方露出频道和今日重点。
- 今日重点改为 source ledger：
  - 频道 / 日期为 meta rail。
  - 标题为主扫读目标。
  - 摘要次之。
  - sourceName/sourceNote 固定在脚注。
- 不生成 Blizzard logo 或伪官方标识。
- 不把设计说明文案写进 App。

验收：

- 不出现“频道 / 日期 / 标题...”这类设计说明。
- 来源名称只来自 payload。
- 滚动后不再是同质黑卡堆叠。

### 5. SimC 承接态

目标：从工作台进入 SimC 时，让用户知道正在校验哪套输入，以及为什么暂不能提交。

文件：

- `pages/simulator/simc.js`
- `pages/simulator/simc.wxml`
- `pages/simulator/simc.wxss`
- `tests/simulator-page.test.js`

动作：

- 顶部 `template-hero` 改为 `context bridge`：
  - 来自当前专精工作台。
  - 职业 / 专精 / 场景。
  - 当前阻断状态。
- 职业、种族、天赋模板、装备模板保持可操作控件，不摘要化。
- 缺个人模板时明确给 `去保存天赋`、`去补装备`。
- 阻断原因必须区分：
  - 公共天赋目录可编码。
  - 个人天赋模板 0。
  - 个人装备模板 0。
- 未完整输入前不显示结果性强结论。

验收：

- selector sheet 交互测试继续通过。
- 底部 action bar safe-area 继续生效。
- 缺模板态仍不能提交任务。

### 6. Chickenbro 承接态

目标：强化证据教练，而不是万能聊天或评分器。

文件：

- `pages/simulator/chickenbro.js`
- `pages/simulator/chickenbro.wxml`
- `pages/simulator/chickenbro.wxss`
- `pages/simulator/chickenbro-chat.js`
- `tests/simulator-page.test.js`

动作：

- 顶部 context bridge 保留当前解释对象。
- suggested prompts 分为：
  - 为什么阻断。
  - 去哪里补。
  - 能否模拟。
- 回答依据区映射产品文案：
  - 来源类型。
  - 证据引用。
  - 解释范围。
  - 限制。
  - 主要缺口。
- 不直接暴露 raw `answerSource`、`confidence`、`job.status`，除非已经映射为用户可理解状态。
- composer 保持 fixed 并处理 safe-area。

验收：

- 不展示 raw profile、raw SimC、内部字段。
- limitations 可见。
- 回答依据不表现为 verified 结果。

### 7. 任务列表和我的模板一致性

目标：只做一致性修补，不扩大范围。

文件：

- `pages/simulator/tasks.*`
- `pages/profile/profile.*`
- `tests/profile-auth.test.js`
- `tests/simulator-page.test.js`

动作：

- 任务空态保留 `去 SimC / 工作台` 路径。
- 模板卡片状态和工作台模板状态同源表达。
- 不用装饰素材替代删除、管理和同步状态。

验收：

- 任务列表、个人模板在 Phase 6 截图 manifest 中覆盖。

## 测试计划

Phase 5 实施完成后至少运行：

```bash
node --test tests/builds-workbench-state.test.js tests/builds-page.test.js tests/frontend-api-client.test.js
node --test tests/simulator-page.test.js tests/news-page-style.test.js tests/ui-style-guide-implementation.test.js tests/profile-auth.test.js
git diff --check
```

静态扫描：

```bash
rg -n "综合评分|S 级|A级|S/A 级|提升优先级|190/206 槽|频道 / 日期 / 标题|Codex / fallback" pages tests
```

预期：

- 测试里的历史 DPS 样例可以存在于后端/客户端契约测试，但 v3 页面首屏和阻断态不得展示无证据 DPS 结果。
- 小程序页面不出现设计板说明文案。
- 素材路径迁移到 `assets/generated/ui-v3/20260701`。

## 微信开发者工具验证

Phase 6 必须复用已打开、已登录的微信开发者工具会话，不反复关闭用户当前小程序。

截图覆盖：

- 资讯首页首屏。
- 资讯滚动列表。
- 职业专精 tab。
- 工作台首屏。
- 工作台证据展开。
- 工作台 blocked 装备态。
- 工作台 partial 天赋态。
- 工作台 ready 态。
- 天赋模拟器入口态。
- 装备模拟入口态。
- SimC 工作台承接态。
- Chickenbro 工作台承接态。
- 任务列表。
- 我的模板。

manifest 要求：

- `status: complete`。
- 每个场景有本地截图路径、时间、验证状态。
- 不允许黑屏、伪状态栏、内部字段、脚手架文案、假时间。

## 2026-07-02 开工前基线

已验证：

```bash
node --test tests/builds-workbench-state.test.js tests/builds-page.test.js tests/frontend-api-client.test.js
node --test tests/simulator-page.test.js tests/news-page-style.test.js tests/ui-style-guide-implementation.test.js tests/profile-auth.test.js
git diff --check
```

结果：

- 第一组 `135` 个 Node 用例通过。
- 第二组 `68` 个 Node 用例通过。
- `git diff --check` 通过。

当前代码仍需 Phase 5 消除的风险：

- `pages/builds/workbench-state.js` 仍有 `iconFallback: 'S'`，容易被误读成 S 级评分。
- `pages/builds/workbench-state.js` 仍把装备目录覆盖写成 `formatCount(..., ' 槽')`，容易把 catalog coverage 误解为玩家已装备槽位。
- `pages/builds/*`、`pages/news/*`、`pages/simulator/*`、`pages/profile/*` 仍引用 `assets/generated/ui-redesign/20260701/*`，尚未迁移到 v3 抽象布局素材。
- `pages/simulator/chickenbro.wxml` 和 `pages/simulator/simulator.wxml` 仍直接展示 `answerSource`、`confidence`、`job.status` 这类工程口径，需要映射成用户可理解的证据字段。
- 当前页面代码尚未出现 `assets/generated/ui-v3`、`v3-cockpit`、`v3-status-rail`、`v3-source-ledger`、`v3-context-bridge`、`v3-evidence-drawer` 等 v3 语义接入。

## 开工门槛

Phase 5 只有在用户确认新的结构线框和视觉目标稿后开始。当前不得直接实施 v3 或 v3.1 图稿。

新的确认顺序：

1. 先产出真实小程序尺寸的低保真结构线框，覆盖工作台首屏、证据展开、资讯滚动列表、职业 tab、SimC 承接、Chickenbro 承接。
2. 布局 CR 必须通过：返回按钮不压装饰，标题清晰，安全区正确，文字不溢出，模块间距稳定，底部 tab 不伪造。
3. 再加局部材质和真实图标规则，形成高保真目标稿。
4. 用户确认后再进入真实页面实施。

实施优先级仍为：

1. 当前专精工作台。
2. 职业专精 tab。
3. 资讯首页和滚动重点列表。
4. SimC / Chickenbro 承接态。
5. 任务和我的模板一致性修补。
