# WoW 小程序 UI v3 设计语言

> 本文承接 [v3 信息资产盘点](2026-07-01-wow-ui-v3-information-inventory.md)。v3 的目标不是把页面变“更黑更金”，而是把真实可用的信息骨架设计成一个成熟的移动端 WoW 构筑与模拟 App。

## Design Read

Reading this as: 面向 WoW C 端玩家的移动端构筑与模拟工作台 redesign，要求高信息密度、强题材识别、真实证据边界，倾向“艾泽拉斯分析控制台”而不是 landing page、后台 dashboard 或页游皮肤。

## Taste Dials

| 维度 | 值 | 解释 |
| --- | --- | --- |
| `DESIGN_VARIANCE` | 6/10 | 允许非模板化布局、状态轨和模块舱，但页面结构必须稳定复用 |
| `MOTION_INTENSITY` | 2/10 | 微信小程序优先稳定，只做点击反馈、展开收起、状态切换 |
| `VISUAL_DENSITY` | 8/10 | 首屏必须能看到对象、readiness、主阻断、下一步和模块状态 |
| `MATERIALITY` | 7/10 | 可以有暗铁、奥术、战情板材质，但材质服务信息，不压信息 |

## 核心原则

1. 信息保真优先：现状里能帮助玩家快速判断的信息必须保留或以更强方式表达。
2. 证据驾驶舱，不是卡片墙：核心页面由对象、状态、证据、动作组成，而不是同质黑卡堆叠。
3. WoW 感来自真实对象和工业幻想材质：真实图标来自接口，imagegen 只做非事实布局资产。
4. 状态就是导航：blocked、partial、source_reference、verified、stale 必须直接告诉用户下一步去哪。
5. 新手默认看结论和动作，资深玩家展开看 evidence ledger。
6. 装饰必须有角色：每一张材质、每一道轨、每一个边框都要承担层级、分组或状态表达。

## 页面壳

### App Shell

- 全局为暗色固定主题，不做页面间大幅变色。
- 页面底不是纯黑，采用近黑暗铁底：`#070706`、`#0B0907`、`#10100E`。
- 页面背景材质只出现一层，透明度低，避免每个 section 都贴同一张图。
- 内容区继续使用 `page-shell + page-scroll + page-content`，不破坏小程序滚动结构。
- 顶部 navigation bar 保持克制，标题不承担主视觉，主视觉交给页面内 cockpit。

### Layout Rhythm

- 页面横向 padding：`24rpx` 默认，复杂工作台可用 `28rpx`。
- section 间距：`18-22rpx`。
- 普通模块 padding：`18-22rpx`。
- Hero / cockpit 不做大 banner，首屏必须露出下一块内容。
- 普通卡片圆角控制在 `10-14rpx`；模块舱可以略锐，底部 sheet 可更圆。
- 数值、状态和 action 尽量同排，减少纵向解释文案。

## 信息架构组件

### 1. Cockpit

用途：页面首屏对象识别区。

必须展示：

- 当前对象：职业、专精、英雄天赋或页面主题。
- 当前场景或上下文。
- 关键状态 badge。
- 更新时间或来源摘要。

视觉规则：

- 不是大图 hero，而是紧凑控制台头。
- 可以使用 `command-board-material` 或 `app-shell-material` 作为低透明材质。
- 标题、状态、对象图标必须比材质更醒目。
- 真实职业/专精/天赋/装备图标缺失时，用文字 fallback，不用 imagegen 补图标。

### 2. Object Plate

用途：表达“当前正在判断谁”。

结构：

- 左侧真实图标或文字徽记。
- 中部主对象名，例如 `法师 · 冰霜`。
- 次级对象，例如 `法术投射者 · 单体`。
- 右侧 readiness badge。

规则：

- 对象名不被装饰边框切碎。
- 状态 badge 使用语义色，不使用绿色表达普通可点击。
- 图片只来自 `gameAsset.iconUrl` 或受控真实资产索引。

### 3. Readiness Slab

用途：首屏最重要的判断区。

必须回答：

- 当前能不能模拟。
- 如果不能，缺什么。
- 下一步去哪。

结构：

- 左侧状态轨或状态角。
- 中部 headline + summary + 主 blocker。
- 右侧主 action。

规则：

- blocked 态不是错误页，仍然是工作台正常状态。
- slab 不显示无证据强结果。
- 红色只做阻断信号，不铺满整块。
- 主 action 文案短，例如 `补装备`、`补天赋`、`去校验`、`看证据`。

### 4. Status Rail

用途：把天赋、装备、SimC、队长变成连续流程。

结构：

- 细竖轨或横轨表达流程。
- 每个节点包含状态点、真实图标或 fallback、模块名、短指标、短动作。
- 节点顺序固定：天赋 -> 装备 -> SimC -> 队长。

规则：

- 不做四张等权大卡。
- 指标优先同排，但字段必须贴近真实模型，例如 `天赋 110 节点`、`装备目录 190/206`、`已装备缺口 头部/颈部/...`。
- 每个节点必须保留状态和入口。
- 队长节点文案必须体现“解释证据，不替代结论”。

### 5. Module Dock

用途：在职业 tab、工作台、SimC 上承托多个相关功能入口。

规则：

- Dock 是“同一任务链上的模块舱”，不是功能宫格。
- 同类模块使用相同高度、图标位和右侧动作位。
- 允许使用暗铁模块舱材质，但不能让每个模块都像独立广告卡。

### 6. Evidence Drawer

用途：资深玩家展开看来源、覆盖率、检查时间、阻断。

结构：

- 顶部一行：标题 + 展开/收起。
- 内部按 `天赋证据 / 装备证据 / 队长规则` 分组。
- 每行三段：label、value、status。

规则：

- 默认摘要区就要露出关键证据信息，不能把可信边界全藏深。
- 展开区更安静，减少强边框和大面积颜色。
- `source_reference` 用蓝色；`partial` 用黄色；`blocked` 用红色；`verified` 用绿色。
- 行高稳定，长缺口文本可两行截断，并提供展开。

### 7. Source Ledger

用途：资讯列表、证据行、回答依据的来源表达。

结构：

- source name。
- source note。
- checkedAt / publishedAt。
- status。

规则：

- 来源名称来自 payload，不生成伪 logo。
- 列表中来源信息不压标题，但必须可扫读。
- 不把 reference-only 包装成 verified。

### 8. Action Slab

用途：告诉用户下一步。

规则：

- 每个主场景只有一个主 action。
- 次 action 放入 blocker 行、module 行或底部 action bar。
- 主 action 必须和 readiness 状态绑定。
- 按钮文案 2-4 字优先，最长不超过 6 个中文字。

### 9. Context Bridge

用途：从工作台跳到 SimC 或 Chickenbro 时保持上下文。

必须展示：

- 来源：`来自当前专精工作台`。
- 对象：职业、专精、英雄天赋、场景。
- 当前 evidence 状态。
- 可执行动作或限制。

规则：

- SimC 交接强调“校验组合”。
- Chickenbro 交接强调“解释证据”。
- 不传 raw profile 给可视 UI，不展示内部字段。

## 状态色

| 状态 | 主色 | 用途 | 禁止 |
| --- | --- | --- | --- |
| `verified` | `#58C98E` | 已验证、可提交、可执行 | 普通可点击、普通成功感装饰 |
| `ready_to_simulate` | `#58C98E` | 当前输入可进入 SimC 校验 | 直接显示模拟结果 |
| `blocked` | `#FF6B64` | 阻断、缺口、不可提交 | 整屏红、错误页化 |
| `partial` | `#F8B700` / `#F2A65A` | 部分可用、需补齐、当前选中 | 伪装成已验证 |
| `source_reference` | `#54C0FF` / `#5E8DFF` | 来源参考、非可执行证据 | 表现为官方结论 |
| `stale` | `#B48CFF` | 过期、需要刷新 | 和 blocked 混用 |

使用规则：

- 状态色优先用于文本、细轨、状态点、小 badge。
- 大面积背景仍使用暗铁/近黑，不让状态色污染整页。
- 金色既是 WoW 主强调，也是 partial/selected/CTA，要通过位置区分含义。
- 同一个状态跨页面文案和颜色必须一致。

## 字体与密度

- 小程序使用系统字体，不引入外部字体。
- 页面级主标题：`40-48rpx`，只在 cockpit 使用。
- section 标题：`30-34rpx`。
- 模块标题：`28-32rpx`。
- 正文：`24-28rpx`。
- meta / status：`22-24rpx`。
- 关键数字可用更粗字重，但不得形成无来源评分感。
- 不使用负 letter spacing；中文文本不做花哨排版。
- 按钮高度常规 `60-68rpx`，底部主 action 可到 `76rpx`。

## 真实图标规则

| 对象 | 来源 | fallback |
| --- | --- | --- |
| 天赋节点 | `/api/websim/talents nodes[].gameAsset.iconUrl` | 天赋名首字或 `天` |
| 装备 | `/api/websim/gear equippedSet / replacementCandidates gameAsset.iconUrl` | 装备槽位字 |
| 职业 / 专精 | 受控真实资产索引或接口 iconUrl | 职业/专精首字组合 |
| 新闻来源 | payload sourceName/sourceNote | 文本来源，不做伪 logo |
| 状态 | 前端语义 token | 色点、轨道、文字 badge |

禁止：

- 用 imagegen 生成职业、专精、天赋、装备、法术图标。
- 用抽象底图裁切出图标。
- 用来源 logo 占位冒充真实合作或官方来源。
- 用装饰图标表达未验证结论。

## imagegen 材质规则

imagegen 是素材工作流，不是事实来源。

允许：

- 页面底图。
- 战情板、状态轨、模块舱、证据抽屉、任务台面。
- blocked / partial / source_reference / verified 的抽象氛围。
- 空态的抽象档案架、控制台占位。

禁止：

- 真实 WoW 对象图标。
- 来源 logo。
- 业务数字、榜单、评分、DPS、S/A 级、提升优先级。
- 看起来像真实游戏截图、真实 SimC 报告或真实数据后台的图。

落地：

- 每个 imagegen 产物必须进入 manifest。
- manifest 记录 sourceType、productionUse、intendedUse、forbiddenUse、realWowObjectInclusion。
- 进入代码前压缩，优先 JPG/WebP，小程序包体必须复核。
- 材质透明度默认低，文字层必须有独立 scrim。

## 页面配方

### 当前专精工作台首屏

目标：第一眼知道“当前能否模拟，为什么，下一步去哪”。

结构：

1. Cockpit：Object Plate + readiness badge + checkedAt。
2. Segmented controls：职业、专精、场景。
3. Readiness Slab：headline、summary、primary blocker、主 action。
4. Blocker Strip：最多 2 条 blocker，每条有 action。
5. Status Rail：天赋、装备、SimC、队长。
6. Template Shelf：天赋模板数、装备模板数、入口。
7. Evidence Summary：默认展示 4-5 行关键证据。

必须保留：

- `天赋 110 节点`、`法术覆盖 72/110` 这类快速指标。
- 装备目录覆盖、已装备槽位、缺口、属性快照。不要把 `190/206` 这类目录覆盖叫作装备槽位。
- 队长“限证据 / 可解释证据”边界。

### 当前专精工作台证据展开

目标：资深玩家能追溯 readiness。

结构：

- Evidence Drawer 分组：天赋证据、装备证据、队长规则。
- 每组内部使用 ledger rows。
- 长缺口可以收起摘要，展开完整列表。

视觉：

- 比首屏更安静，减少装饰边。
- 蓝色 reference 行不抢过 blocked 行。
- blocked 行突出缺口和影响。

### 职业专精 Tab

目标：从功能集合变成构筑工作流入口。

结构：

1. Compact Cockpit：职业控制台，不做大 banner。
2. Current Workbench Entry：当前 spec、readiness 快照、模板数、最近任务或待补状态。
3. Workflow Dock：天赋、装备、SimC、任务，表示连续任务链。
4. 旧入口保留，位置下沉。

新增信息：

- 本地/账号模板概览。
- 最近 SimC 任务状态。
- 当前专精 readiness 简短状态。

### 资讯首页

目标：像 WoW 情报产品，不像深色卡片新闻流。

首屏：

- Command Board：来源、频道、重点、更新时间。
- Hero News：一条主新闻，不占满首屏。
- Channel Strip：横向频道入口。
- 今日重点露出第一条。

滚动列表：

- 使用 Source Ledger List。
- 频道/日期形成固定 meta rail。
- 标题主导，摘要次之，来源脚注稳定。
- 不再让红色 pill 和左侧竖条抢正文。

### SimC 工作台承接态

目标：从工作台进入后，用户知道正在校验哪套输入。

结构：

1. Context Bridge：来自工作台、对象、场景、输入状态。
2. Selector Stack：职业、种族、天赋模板、装备模板。
3. Scenario and Buff Controls。
4. Confirm Summary。
5. Blocked Panel 或 Result Panel。
6. Sticky Action Bar。

规则：

- 表单保持高效，不做概念化大卡。
- blocked 时给回补入口。
- 未完成输入前不显示结果性强结论。
- 必须区分公共目录可用和个人模板可提交：天赋目录 partial 不等于个人天赋模板已保存，装备目录 partial 不等于 16 槽装备模板已就绪。

### Chickenbro 工作台承接态

目标：把队长做成证据教练，而不是万能评分器。

结构：

1. Context Bridge：当前解释对象。
2. Suggested Prompts：为什么阻断、去哪补、能否模拟。
3. Chat Area：左右气泡不变。
4. Evidence Accordion：回答依据、限制、priority actions。
5. Fixed Composer。

规则：

- 上下文面板不压过第一条聊天内容。
- limitations 必须可见。
- 回答依据不能表现成 verified 结果。

### 任务列表与个人模板

目标：一致性修补，不抢主战场。

任务列表：

- 任务数、状态、tags、完成时间保留。
- 空态保持 `去 SimC / 工作台` 双路径。
- 状态色与工作台一致。

个人模板：

- 微信头像、昵称、模板数保留。
- 模板卡和工作台模板状态统一。
- 删除操作保持明确，不用装饰图替代。

## 组件反模式

禁止在 v3 中继续出现：

- 每个 section 都是同一张深色卡。
- 每个卡都套大圆角、金边、背景图。
- 用红色边框包住整屏表达 blocked。
- 只为“好看”删掉模板数、缺口、覆盖率、checkedAt。
- 用伪游戏图标替代真实 iconUrl。
- 效果图只有目标图，没有 current vs target。
- 效果图里的注释和真实页面内容混在一起。

## 实施预检

实施任何页面前检查：

1. 首屏是否保留当前页面的信息资产。
2. 状态是否直接导向下一步。
3. 是否避免黑卡片墙。
4. imagegen 素材是否有明确用途和 manifest。
5. 真实图标是否来自真实来源或中性 fallback。
6. 是否没有无证据 DPS、综合评分、S/A 级、提升优先级。
7. 是否能在微信开发者工具真实项目中验证，而不是 HTML demo。
