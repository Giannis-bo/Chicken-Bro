# WoW 小程序 UI v3 信息资产盘点

> 本文是 UI v3 的第一步输入：先锁定当前真实页面的信息骨架，再进入视觉语言、imagegen 素材工作流和小程序实现。后续设计必须从本库存派生，不能为了视觉效果删除有用的快速浏览信息。

## 目标边界

- 目标：把现有黑金卡片式工具页升级为有 App 感、有 WoW 识别度、信息密度更高的 C 端小程序。
- 方法：保留当前真实截图里的任务结构和证据信息，重做页面层级、组件语言、布局资产和状态感知。
- 范围：资讯首页、职业专精 tab、当前专精工作台、SimC 交接、炸鸡队长交接、任务列表、个人模板。
- 限制：不输出无来源 DPS、评分、S/A 级、提升优先级；不使用 imagegen 生成真实职业/专精/天赋/装备图标；不做纯背景换皮。

## 当前证据

| 场景 | 真实截图 | 当前价值 | v3 处理 |
| --- | --- | --- | --- |
| 资讯首页顶部 | `artifacts/miniprogram-screenshots/20260630-workbench-redesign/screenshots/001_news_home_top.png` | 有来源数、频道数、重点数、hero 新闻和频道入口 | 保留资讯战情摘要，压缩大面积背景，增强编辑感和来源可信层级 |
| 资讯首页滚动后 | `artifacts/miniprogram-screenshots/20260630-workbench-redesign/screenshots/002_news_home_scrolled.png` | 今日重点列表具备标题、频道、日期、摘要、来源 | 保留列表信息，解决深色卡片堆叠和平铺感，强化列表可扫读 |
| 职业专精 tab | `artifacts/miniprogram-screenshots/20260630-workbench-redesign/screenshots/003_builds_tab.png` | 工作台入口和四个旧入口都存在 | 保留主入口 + 旧流程入口，增加账号/模板/最近任务快照 |
| 工作台首屏 | `artifacts/miniprogram-screenshots/20260630-workbench-redesign/screenshots/004_workbench_first_screen.png` | 当前对象、readiness、主阻断、下一步、四模块、模板均在首屏 | 作为 v3 主信息骨架，不得删减快速浏览信息 |
| 工作台证据展开 | `artifacts/miniprogram-screenshots/20260630-workbench-redesign/screenshots/005_workbench_evidence_expanded.png` | 展示覆盖率、检查时间、装备槽位、缺口、目录、属性快照、队长规则 | 保留为资深玩家二级证据区，改成更像证据抽屉 |
| 工作台阻断装备态 | `artifacts/miniprogram-screenshots/20260630-workbench-redesign/screenshots/006_workbench_blocked_gear.png` | 可验证 blocked 分支 | 保留缺口与去向，不做错误页 |
| 工作台 partial 天赋态 | `artifacts/miniprogram-screenshots/20260630-workbench-redesign/screenshots/007_workbench_partial_talent.png` | 可验证 partial 分支 | 保留可用但不完整的证据语义 |
| 天赋模拟器 | `artifacts/miniprogram-screenshots/20260630-workbench-redesign/screenshots/008_talent_simulator.png` | 已具备真实天赋树和节点形状 | v3 不重造天赋树，只做入口、状态和返回工作台的一致性 |
| 装备模拟器 | `artifacts/miniprogram-screenshots/20260630-workbench-redesign/screenshots/009_gear_simulator.png` | 装备候选和真实图标来自接口 | v3 保留真实图标和候选可信边界，优化和工作台的连贯导航 |
| SimC 页 | `artifacts/miniprogram-screenshots/20260630-workbench-redesign/screenshots/010_simc.png` | 模板组合、场景、增益、摘要、阻断、提交任务完整 | v3 做成工作台后的校验舱，不在缺输入时显示强结果 |
| 任务列表 | `artifacts/miniprogram-screenshots/20260630-workbench-redesign/screenshots/011_tasks.png` | 任务状态和空态路径明确 | v3 统一任务状态视觉，与 SimC/工作台互相回链 |
| 炸鸡队长 | `artifacts/miniprogram-screenshots/20260630-workbench-redesign/screenshots/012_chickenbro.png` | 有上下文、建议追问、回答依据、限制 | v3 强化“解释证据”角色，不替代评分或模拟结论 |
| 个人模板 | `artifacts/miniprogram-screenshots/20260630-workbench-redesign/screenshots/013_profile_templates.png` | 模板数、最近模板、删除管理存在 | v3 和工作台模板状态统一，保留微信头像/昵称设置 |
| 工作台 ready 态 | `artifacts/miniprogram-screenshots/20260630-workbench-redesign/screenshots/014_workbench_ready.png` | 可验证 ready_to_simulate 分支 | v3 ready 态只给“去 SimC 校验”，不提前给结果分 |

## 全局信息资产

| 信息资产 | 来源 | 必须保留 | v3 表达 |
| --- | --- | --- | --- |
| 当前职业 / 专精 / 英雄天赋 | `fallbackBuildsHome()`、`requestBuildsHome()`、`selectedSpec`、`talentsPayload` | 是 | 顶部对象牌、真实图标或中性文字 fallback |
| 场景 | `scenarioOptions: single / aoe_5 / mythic_plus` | 是 | 紧凑 segmented control，不做大卡片 |
| readiness | `buildWorkbenchState()` 聚合态 | 是 | 首屏主结论，状态色跨页面统一 |
| 主 blocker | `primaryBlockers()`、gear/talent blockers | 是 | 首屏直接显示缺什么和去哪补 |
| 下一步 action | `primaryAction` | 是 | 每页一个主 CTA，按钮文案短 |
| 四模块状态 | talent / gear / SimC / Chickenbro | 是 | 视觉上像工作流状态轨或模块 dock，不做普通卡片墙 |
| 证据明细 | `evidenceRows` | 是 | 默认摘要，展开给覆盖率、检查时间、缺口、目录、属性快照 |
| 本地/账号模板 | `listBuildTemplates()`、`fetchBuildTemplates()` | 是 | 工作台、SimC、个人页共享同一模板状态 |
| 真实对象图标 | `gameAsset.iconUrl`、装备 `iconUrl` | 是 | 仅用于对象识别，不用 imagegen 替代 |
| 数据可信状态 | `verified / partial / source_reference / blocked / stale` | 是 | 颜色、文案、边框和 CTA 语义统一 |
| imagegen 素材 | `assets/generated/ui-redesign/**/manifest.json` | 否，按需 | 只能是抽象材质和布局资产，不承载事实 |

## 当前专精工作台

### 必须保留

- 页面标题：`当前专精工作台`。
- 当前对象：职业、专精、英雄天赋、场景。
- readiness badge：`可提交模拟 / 阻断 / 部分可用 / 需刷新 / 来源参考`。
- 证据更新时间：例如 `证据更新 07-01 13:32`。
- 职业 picker、专精 picker、场景切换。
- 模拟准备结论：headline、summary、主阻断、主 action。
- 下一步：最多 2 个 blocker，包含缺什么、影响什么、去哪补。
- 工作流状态：天赋、装备、SimC、队长四模块。
- 模板状态：天赋模板数、装备模板数、入口。
- 证据明细：天赋状态、节点覆盖、法术覆盖、模板数、检查时间、装备槽位、缺口、装备目录、属性快照、队长规则。

### 当前问题

- 首屏信息是完整的，但所有块都像同等级卡片，主结论和四模块之间缺少明确的视觉节奏。
- 同一张材质图被重复用于背景、hero、slab、证据区，素材角色不清。
- 状态颜色存在，但边框和大面积红/黄线条让页面紧张感过强，扫读时会被边界抢注意力。
- 工作流状态有数值优势，例如 `天赋 110 节点`、装备目录覆盖数、缺失部位列表，但当前文案容易把目录覆盖误写成装备槽位，排版也没有把“对象-状态-动作”形成稳定读法。
- `队长` 已被约束为解释证据，但视觉上还不像一个可追问的智能助手入口。

### v3 处理

- 首屏改为“对象牌 + readiness slab + 工作流状态轨 + 证据摘要”的固定结构。
- 保留 `天赋 110 节点`、`法术覆盖 72/110`、装备目录覆盖、已装备缺口、`模板数` 等快速信息。
- 把四模块改成连续流程：天赋 -> 装备 -> SimC -> 队长，每个模块展示状态、短指标、入口。
- 阻断不是错误页：blocked 态仍是工作台核心决策态。
- 资深信息进入证据抽屉，但首屏必须保留摘要。

## 资讯首页

### 必须保留

- 情报摘要：状态、标题、来源数、频道数、最近刷新时间、重点数。
- hero 新闻：频道、日期、标题、摘要、来源名称、来源说明。
- 频道入口：频道名、更新数、描述。
- 今日重点：频道、日期、标题、摘要、来源名称、来源说明。

### 当前问题

- 滚动后的重点列表信息完整，但深色卡片重复堆叠，缺少新闻编辑产品的层级。
- 左侧状态轨和红色频道 pill 比正文更抢眼。
- 来源可信信息有价值，但现在被压在卡片底部，用户扫读时先看到的是装饰边。

### v3 处理

- 保留首屏情报摘要和列表密度，不改成大 banner。
- 今日重点列表改为更强的编辑排版：频道/日期成为 meta rail，标题成为主视觉，来源作为固定脚注。
- `Blizzard News / Blizzard Forums` 等来源只来自 payload，不用生成图标或伪 logo。
- 滚动后不能出现大面积纯黑或同质卡片墙。

## 职业专精 Tab

### 必须保留

- 页面标题：`职业专精`。
- 职业控制台 hero：标题、描述。
- 当前专精工作台入口：当前 spec、标题、描述、进入按钮、天赋/装备/SimC/队长标签。
- 构筑流程入口：天赋构筑、装备模拟、模拟 SimC、任务列表。
- 旧入口继续存在，但下沉。

### 当前问题

- 工作台入口有，但缺少当前账号状态，例如模板数、最近任务、ready/blocked 状态。
- 构筑流程入口仍像普通工具列表，没有表达“这是一个连续任务链”。
- 首屏 WoW 感主要来自背景材质和金色边框，缺少真实对象信号。

### v3 处理

- 工作台入口成为首屏最高优先级，但补充模板、最近任务、当前 readiness 快照。
- 构筑流程做成任务链，而不是四张独立卡。
- 保留旧四入口，确保用户能直接进入单点工具。

## SimC 交接

### 必须保留

- 职业、种族选择。
- 天赋模板、装备模板选择和数量。
- 场景预设。
- 战斗增益与临时 buff。
- 确认摘要：职业、种族、天赋、装备、场景。
- 阻断原因。
- 底部固定操作：校验组合、提交任务、任务限制。

### 当前问题

- 和工作台的信息语言还不连续：从“补齐证据”进入 SimC 后，缺少清楚的交接上下文。
- `summaryStatPanel` 可以展示结构化摘要，但必须避免在证据不足时给强结果。
- 底部按钮清晰，但页面中段视觉节奏偏表单化。

### v3 处理

- 从工作台进入时顶部展示 `from=workbench` 的校验上下文：当前 spec、场景、输入来源。
- 模板选择继续保持表单效率，不改成概念卡。
- blocked 态明确回到工作台或对应补齐页。
- 没有完整 SimC-ready 输入前，不显示结果性评分。

## 炸鸡队长交接

### 必须保留

- 上下文对象：`当前解释对象`。
- 建议追问。
- 左右聊天气泡。
- 回答依据：answerSource、confidence、priorityActions、evidenceRefs、limitations。
- 生成状态、错误状态、job 状态。
- 底部固定输入、新话题、话题抽屉。

### 当前问题

- 队长的产品角色已经正确：解释证据和阻断，不替代结论。
- 首屏视觉仍偏普通聊天页，WoW 题材感主要靠背景，不靠信息结构。
- 建议问题和回答依据可以更像“战术顾问面板”，但不能压过聊天。

### v3 处理

- 工作台进入时让上下文面板更明确，显示 bounded context 摘要，不传 raw profile。
- 建议追问保留为 chip，但分组为“为什么阻断 / 去哪里补 / 能否模拟”。
- 回答依据改成可折叠证据条，突出 limitations，防止用户误把解释当评分。

## 任务与个人模板

### 任务列表必须保留

- 任务总数。
- 加载态、空态。
- 任务 title、status、tags、desc、completionTime。
- 空态路径：去 SimC、工作台。

### 个人模板必须保留

- 微信头像、昵称。
- 模板指标：天赋、装备等数量。
- 个人模板库：天赋模板、装备模板、最近模板、保存时间、删除。
- 设置与管理入口。

### v3 处理

- 任务页和个人页不做重设计主战场，但需要统一视觉系统。
- 个人模板数必须和工作台、SimC 的模板状态同源表达。
- 空态继续给行动路径，不做纯装饰空状态。

## 真实素材规则

| 类型 | 可用来源 | 禁止 |
| --- | --- | --- |
| 职业/专精/天赋图标 | API `gameAsset.iconUrl`、WebSim/Battle.net read model、受控真实资产索引 | imagegen 伪造图标、用抽象图标冒充真实天赋 |
| 装备图标 | `/api/websim/gear` 的 equipped/candidate `gameAsset.iconUrl` | imagegen 生成装备图标 |
| 来源名称 | 新闻 payload、接口 sourceName/sourceNote | 伪 Blizzard logo、伪官方标识 |
| 状态与阻断 | `buildWorkbenchState()`、WebSim/SimC read model | 从效果图或文案硬造 |
| 材质/布局资产 | imagegen 生成的暗铁、奥术、战情板、状态轨、证据抽屉背景 | 承载数据、承载真实对象、替代业务组件 |

## imagegen 素材缺口

当前素材只有两类：`azeroth-console-material-mobile.jpg` 和 `evidence-state-strip-mobile.jpg`。v3 需要更像真实 App 设计素材工作流，建议补齐以下抽象布局资产：

| 资产 | 用途 | 要求 |
| --- | --- | --- |
| `command-board-material` | 资讯情报头、职业控制台头 | 暗铁战情板，不含文字、logo、图标 |
| `readiness-slab-material` | 工作台主结论 | 可承载状态边缘光，但不预置状态文案 |
| `workflow-rail-material` | 天赋/装备/SimC/队长状态轨 | 纵向或横向模块槽，不含假图标 |
| `evidence-drawer-material` | 证据明细展开区 | 更安静，利于表格行阅读 |
| `task-tabletop-material` | 任务与个人模板辅助背景 | 低对比，不抢正文 |
| `empty-state-material` | 空态和 blocked 辅助氛围 | 不做插画主角，不生成 WoW 对象 |

## v3 设计输入结论

1. 工作台首屏的信息骨架是正确方向，v3 必须保留并强化，不得退回“素材堆叠”。
2. 资讯、职业 tab、SimC、队长、任务、个人页要共享同一套状态语言和组件语法。
3. imagegen 要从“整图效果”转为“抽象布局资产生产”，每个资产要有命名、用途、禁用范围和 manifest。
4. 真实 WoW 对象必须来自真实素材链路；没有真实图标时使用文字 fallback。
5. 后续效果图必须成对展示 current vs target，并说明 target 在信息密度、状态感知、题材感和操作效率上强在哪里。

## 自检

- 已覆盖当前官方小程序截图 manifest 的全部 14 个场景。
- 已引用真实页面结构：`pages/builds/workbench.*`、`pages/builds/workbench-state.js`、`pages/builds/builds.wxml`、`pages/news/news.wxml`、`pages/simulator/simc.wxml`、`pages/simulator/chickenbro.wxml`、`pages/simulator/tasks.wxml`、`pages/profile/profile.wxml`。
- 未把 v2.1/v2.2/v2.3 或 imagegen 图当最终 UI。
- 未新增无来源评分、DPS、S/A 级或提升优先级。
- 已明确后续 UI 需要保留工作台快速浏览信息。
