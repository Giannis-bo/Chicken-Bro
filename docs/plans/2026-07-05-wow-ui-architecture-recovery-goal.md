# WOW 小程序 UI 架构返工目标

## Summary

本轮目标从“继续修 UI v2.1 pass36 的局部还原”升级为“重建小程序 UI 架构、素材切分、组件契约、交互路由与真实渲染验收流程”。后续不再以单个页面、单个徽章或单张效果图作为目标，而是先建立可扩展的组件系统，再把资讯、职业 tab、当前专精工作台、模拟器、队长、任务和个人页纳入同一套设计与验证约束。

核心判断：当前问题不是某个 `rpx` 或某张素材没调好，而是前端层级、素材职责、组件状态模型、真实小程序验证链路没有被严格设计。后续必须按“目标拆解 -> 组件契约 -> 素材切片 -> 真实实现 -> 截图量化 -> 路由验证”的流程推进，不能再直接在页面上缝补样式。

本文件是后续 UI 返工的执行 goal。线程内旧 goal 仍保持 active，但实际推进、验收和复盘以本文件的更新约束为准。

## 2026-07-05 Constraint Upgrade

这次更新把 goal 从“方向正确”收紧为“可执行、可拦截、可验收”的工作契约。后续任何 UI 交付都必须先满足本节，不能用主观审美分、单张截图或局部组件成功替代。

### Goal Lock

- 本轮不再创建横向 skill 评测目标。taste-skill、imagegen、subagent 只能作为设计辅助和审计工具，不能重新变成目标本身。
- 本轮不再接受“在现有页面继续缝补”的实现路径。每次实现前必须先完成目标图拆解、组件契约、素材职责和场景矩阵。
- 本轮不再接受“效果图很好但实现差很多”的落差。imagegen 目标图必须被拆成可落地的组件和素材切片，再进入代码。
- 本轮不再接受“看起来比上一版强”的验收口径。所有通过结论必须同时有当前图、目标图、实现图、组件 crop、overlay、红区和 scorecard。
- 本轮不再接受“浏览器能看就行”的替代验证。浏览器只能作为预检，最终验收必须来自真实微信小程序截图和路由 smoke。

### Hard Stop Gates

任一 gate 未满足时，当前页面或组件必须停在 `diagnosis` 或 `source/browser evidence`，不得继续宣称进入最终实现或验收。

- 没有当前真实截图和用户红区问题图，不允许开始页面级重构。
- 没有目标图或目标组件图，不允许开始视觉还原。
- 没有组件尺寸表、图层表和素材切片表，不允许写核心 WXML/WXSS。
- 没有真实 WoW 素材来源清单，不允许把任何图标当作职业、专精、天赋、装备或来源事实使用。
- 没有生产资产 manifest，不允许把 imagegen 资产接入业务页面。
- 没有组件 harness crop，不允许接入真实页面。
- 没有真实小程序截图，不允许给最终视觉分。
- 没有 route smoke，不允许宣布页面可用。
- 没有 DevTools 操作审计，不允许解释登录态失效或模拟器无响应。
- 同一个基础布局问题连续两轮没有修好，必须停止调参，回到组件契约或素材切片重做。

### Quantitative Acceptance Floor

90% 还原必须由可量化指标支撑。以下任一失败，页面不得通过：

- 页面业务内容统一 gutter 偏差不得超过 8rpx；同一页面相邻模块左右边界偏差不得超过 6rpx。
- 组件外框、图标槽、按钮槽、状态槽必须有固定宽高；实现尺寸相对目标偏差不得超过 6%，核心状态组件不得超过 4%。
- 状态 glyph 中心偏差不得超过 4rpx；盾牌、圆章、叹号、问号、OK、锁等必须由同一个状态组件定位。
- 主标题、状态结论、主行动按钮不得低于 32rpx；正文关键信息不得低于 28rpx；meta 信息低于 22rpx 时必须证明不承担主阅读任务。
- 主要按钮视觉高度不得低于 72rpx，触控高度不得低于 64rpx；按钮文案不得被压缩、换行或贴边。
- 横向卡片必须有固定列宽、最小高度、图标槽和文本截断策略；不得靠 flex 自然挤压。
- 所有图片必须声明 `contain`、`cover`、九宫格或裁切策略；不得靠原图天然尺寸撑布局。
- 单个生产 bitmap 资产默认不得超过 100KB；超过时必须说明为什么无法压缩且不影响 DevTools 稳定。
- 页面不得出现重复系统状态栏、重复胶囊、伪时间、伪电量、伪 Wi-Fi 或伪微信原生导航。

### Required Artifact Set

每个核心页面都必须输出同一套 artifact，缺一项就不能进入最终验收：

- `current/`: 当前真实小程序截图和组件 crop。
- `target/`: 用户认可的目标图或目标组件图。
- `decomposition/`: app shell、page shell、material、content、state、interaction 图层拆解。
- `assets/`: imagegen 原图、切片、压缩图、职责说明、尺寸策略和真实素材来源。
- `implementation/`: 实现后的真实小程序截图和组件 crop。
- `overlays/`: 当前 vs 目标、目标 vs 实现、红区问题图。
- `scorecard/`: 量化评分、失败项、允许偏差和下一步修复项。
- `routes/`: 点击、切换、展开、返回、跨页跳转 smoke manifest。
- `devtools/`: 低扰动 health、captureSafe、窗口状态、端口状态、禁止动作审计。

### Scenario Matrix Floor

本轮至少覆盖以下真实小程序场景。缺失场景只能列为 blocker，不能从总分里消失。

- 首页首屏。
- 首页下滚后的频道 dock 与今日重点列表。
- 资讯列表、频道切换、资讯详情进入与返回。
- 职业专精 tab 首屏、职业切换、专精切换。
- 当前专精工作台首屏。
- 工作台 evidence 展开。
- 工作台 `blocked / partial / stale / ready_to_simulate / source_reference` 五状态。
- 工作台跳转装备、天赋、SimC、队长并返回。
- 天赋模拟器导入、保存、缺失态。
- 装备模拟器槽位选择、缺失态、保存。
- SimC 校验页、阻断态、可提交态、任务详情。
- 炸鸡队长入口、聊天页、新话题、输入区聚焦。
- 个人模板页、空态、列表态、删除或同步状态。

### Imagegen Production Rule

imagegen 继续使用，但只按真实 app 设计素材工作流进入生产：

1. imagegen 先产出目标方向或低语义素材，不直接产出业务事实。
2. 每张图必须拆为 app shell、panel、border、texture、socket、state-base、glyph、decorative 等职责。
3. 真实 WoW 图标必须来自真实接口、WebSim/Battle.net 映射或仓库验证资产，不能由 imagegen 伪造。
4. 状态底座和状态 glyph 必须分离。叹号、问号、OK、锁、队长标识必须可替换且居中规则一致。
5. 生产页面只能引用 manifest 允许的切片。参考图、整页效果图、含文字或含业务结论的图不得进入生产。
6. 每个生产素材必须有组件槽位尺寸和适配策略，不允许进入代码后再靠页面级绝对定位修补。

### DevTools Safety Rule

微信开发者工具验证必须先保护用户状态，再追求自动化效率。

- 默认允许：读取当前窗口、低扰动 health check、端口探测、在 `captureSafe=true` 后截图和点击。
- 默认禁止：`cli open`、`cli close`、`cli auto` 循环、清缓存、重登、切 appid、切项目、关闭窗口、重启工具、删除用户目录。
- 用户已授权的高扰动动作只能用于当前诊断目标，脚本必须写入动作、时间、理由和结果，不能变成默认流程。
- 如果登录态失效，先审计最近动作是否触发 DevTools 生命周期、项目切换、缓存清理、多实例或端口抢占；不能直接归因给微信机制。
- 如果模拟器无响应，先检查大图资产、无限循环、长同步计算、setData 过载、定时器和自动化重复点击，再继续 UI 验证。

### Rework Discipline

- 一个问题连续两轮没有实质改善，必须换思路，不能继续微调同一套 CSS。
- 单个组件超过 60 分钟仍解决不了基础对齐、尺寸或层级问题，必须输出原因和替代方案，包括是否需要重切素材、重写组件或降低视觉目标。
- 每次迭代必须保留前后对比，不能覆盖旧截图后只展示最新图。
- 任何“完成”结论必须同时列出未通过场景、未跑场景和仍然只停留在 browser evidence 的场景。

## 2026-07-06 Constraint Upgrade

这次更新把 goal 进一步收紧为“架构优先、素材可控、验证闭环”的执行合约。触发原因是：当前问题已经不是单个页面或单个状态徽章，而是整个小程序的 UI 分层、组件几何、素材切片、真实渲染和路由验证链路都没有形成稳定生产流程。后续不得继续把局部调参当作主线。

### Reset Scope

- 本轮目标不是“把当前页面修得稍微好看”，而是建立可复用的小程序 UI 生产系统，再用它重做首页、资讯、职业 tab、当前专精工作台、模拟器、队长、任务和个人页。
- 任何页面级改动都必须证明它来自组件系统，而不是页面内临时拼形状。
- `pass36` 只能保留为历史证据和失败样本；新的执行口径按 `pass37 architecture-first` 推进。
- 旧的高分、90% 还原、视觉通过结论全部作废，除非重新通过本节的证据链。

### Architecture-First Gate

没有完成以下架构输入前，不允许继续写核心页面 WXML/WXSS：

- `AppShell`：真实小程序导航、安全区、底部 tab、滚动容器归属清楚，禁止重复系统状态栏、伪时间、伪电量、伪 Wi-Fi、伪胶囊。
- `PageFrame`：统一页面 gutter、模块栅格、首屏密度、滚动节奏和背景层级。
- `WowPanel`：面板外框、九宫格或 contain 策略、内距、标题区、body 区、overflow 策略固定。
- `StatusBadge`：状态底座、glyph、文案、动作入口可替换；叹号、问号、OK、锁、队长标识必须共用同一几何规则。
- `ChannelDock` / `RankedFeed` / `ModuleDock` / `EvidenceLedger` / `WorkbenchHero`：必须先有组件尺寸表、状态表和长文本策略，再接入页面。

页面只负责组合组件和绑定真实数据；组件内部不得依赖父级负 margin、页面级绝对定位或背景图留白来修视觉。

### Design Translation Gate

目标图不能直接等于实现方案。每个页面进入代码前必须产出：

- 当前真实截图、用户红区问题图、目标图或目标组件图。
- 目标图红线标注：外框、gutter、图标槽、状态槽、按钮槽、字号、行高、模块间距。
- 组件分解表：每个视觉块属于 app shell、page shell、material、content、state、interaction 中哪一层。
- 适配策略：至少说明 compact / standard / large 视口下哪些尺寸固定、哪些区域弹性、哪些内容截断。
- 目标偏差说明：为了小程序真实约束而调整目标时，必须先写入 scorecard，不能实现后用“适配”解释错位。

如果目标图无法被拆解成组件、素材和布局约束，它只能作为 mood reference，不能作为验收目标。

### Imagegen Asset Gate

imagegen 必须按真实 app 素材工作流使用：

- 可进生产的 imagegen 资产只包括低语义 material、panel、border、texture、socket、state-base、decorative 和可替换 glyph。
- 任何真实 WoW 职业、专精、天赋、装备、来源 logo、新闻事实、readiness、评分、DPS、提升优先级都不能由 imagegen 伪造。
- 状态底座和 glyph 必须拆开。类似“盾牌 + 叹号”的组件必须是固定容器内的底座 `contain` 加 glyph 居中，不得把状态烘焙进底图。
- 所有生产图片必须进入 manifest，记录原图、切片、透明边界、目标组件、槽位尺寸、文件大小、适配策略和语义等级。
- 含文字、业务结论、真实图标、状态判断或不可替换 glyph 的整页效果图只能进入 reference/quarantine，不得被业务页面引用。

### Implementation Gate

任何核心组件进入页面前必须先通过组件级实现检查：

- WXML 必须能看出 material/content/state/interaction 分层。
- WXSS 必须声明固定尺寸、内距、行高、图片 fit、文本截断、overflow 和触控热区。
- 状态、按钮、图标、tab、卡片不得靠内容自然撑开；必须有明确 slot。
- 不允许用连续微调 `top/left/margin` 猜位置；内部绝对定位只允许出现在固定尺寸组件内，并且要有中心点或边界公式。
- 不允许为了截图好看写死假的业务数据、假评分、假状态、假图标或假来源。
- 同一组件必须覆盖 ready、blocked、partial、stale、source_reference、unknown、缺图、长文本和空态。

### Verification Gate

验证分为四级，不能跳级：

1. `design_locked`：目标图、红线、组件契约、素材 manifest 完整。
2. `component_precheck`：浏览器 harness 或等价工具证明组件 rect、overflow、slot 和 crop 正常。
3. `runtime_verified`：真实微信小程序截图、组件 crop、overlay、scorecard 和 route smoke 通过。
4. `final_accepted`：所有核心场景矩阵完成，未通过项列为 blocker，用户认可当前方向。

没有真实小程序截图时，最多只能标记为 `component_precheck` 或 `source/browser evidence`。任何 browser harness、HTML demo、OS fallback 截图、旧缓存图，都不能替代 `runtime_verified`。

### DevTools Safety Gate

微信开发者工具只能在低扰动、安全状态下参与验证：

- 默认只允许读取窗口、读取端口、health check、在 `captureSafe=true` 后截图和点击当前小程序。
- 默认禁止 `cli open`、`cli close`、`cli auto` 循环、登录探测、清缓存、重启、切 appid、切项目、删除用户目录、关闭窗口。
- 任何可能影响登录态的动作必须显式记录命令、时间、理由、风险和结果；不能把一次授权扩展成永久默认动作。
- 如果登录态失效，必须先审计最近脚本是否触发生命周期动作、多实例、缓存变更、项目切换或端口抢占，不能直接归因给微信机制。
- 如果模拟器无响应，必须先检查生产资产体积、同步计算、死循环、定时器、`setData` 过载和自动化重复点击，再继续截图验证。

### Cross-Page Product Gate

视觉通过必须同时证明信息架构和路径可用：

- 首页必须证明频道 dock、今日重点、下滚列表、资讯详情进入与返回可用。
- 职业 tab 必须证明职业切换、专精切换、工作台入口、旧入口下沉但仍可达。
- 当前专精工作台必须证明五状态、证据展开、装备/天赋/SimC/队长跳转与返回。
- 模拟器必须证明阻断态、可提交态、任务列表、任务详情路径。
- 队长必须证明入口、聊天页、新话题、输入区聚焦和长消息滚动。
- 个人页必须证明模板空态、列表态、删除或同步状态。

单个页面漂亮不代表全局通过；单个静态截图漂亮不代表产品可用。

### Failure Escalation

- 同一基础布局问题两轮未改善，立即停止页面调参，回到组件契约或素材切片重做。
- 单个组件 60 分钟仍不能解决边距、对齐、contain、overflow 或状态居中，必须输出失败原因和替代方案。
- 一个页面 2 小时内没有拿到可量化进展，必须切换到另一个候选方案横向推进，不能继续死磕一个坏方向。
- 任何“越改越差”的迹象出现时，必须保留当前产物为失败样本，重新从目标图拆解和组件架构开始。

### Reporting Language

后续汇报只能使用以下状态词：

- `draft`：想法或设计草图，还没拆组件。
- `design_locked`：目标、红线、组件契约和素材 manifest 已锁。
- `component_precheck`：组件 harness 通过，但还没真实小程序验收。
- `runtime_verified`：真实小程序截图、crop、overlay、scorecard 和 route smoke 通过。
- `blocked`：被 DevTools、素材、接口、组件契约或路由问题阻断。
- `final_accepted`：完整场景矩阵通过，并且用户认可。

禁止使用“差不多”“应该可以”“90 分左右”“基本还原”“看起来更好”这类没有证据支撑的通过表述。

## 2026-07-06 Recovery Lock

这次更新把 goal 从“约束更严格”继续收紧为“先修生产流程，再修页面”。触发原因是：状态盾牌、频道 dock、列表、工作台卡片、重复系统 chrome、登录态失效和模拟器无响应都暴露出同一个问题：页面正在承担组件系统、素材系统、状态系统、导航系统和验证系统的职责。后续不允许继续把业务页面当作调参画布。

### Active Goal Override

- 线程内 active goal 仍是早期 `pass36/pass37` 描述，工具层不能直接改写 active objective；本文件是当前执行 goal 的事实来源。
- 后续汇报、计划、验收和复盘必须引用本文件最新的 `pass37 strict-system-contract` 约束，而不是旧 goal 里的宽松措辞。
- 旧截图、旧高分、旧 browser audit、旧 component precheck 只能作为证据输入；不能自动继承为通过结论。

### Page Editing Freeze

除非满足本节条件，否则不得继续修改核心页面的 WXML/WXSS：

- 有明确的重构工单，写清楚页面、组件、目标图、当前问题、验收产物和不改范围。
- 有组件票据，写清楚固定尺寸、slot、状态、长文本、缺图、空态、点击热区和 overflow 策略。
- 有素材票据，写清楚 imagegen 切片、真实 WoW 素材来源、manifest、文件大小、透明边界和 `contain / cover / slice` 策略。
- 有数据票据，写清楚真实接口字段、本地模板字段、fallback 字段和禁止伪造字段。
- 有路由票据，写清楚进入、返回、展开、切换、跨页跳转和失败态路径。
- 有验证票据，写清楚 browser precheck、真实小程序截图、crop、overlay、scorecard、route smoke 和 DevTools 安全日志。

没有这些票据时，只能写分析文档、组件契约、素材 manifest、测试或 harness，不能继续在页面里调 `margin/padding/top/left`。

### Foundation Components First

以下基础组件必须优先稳定，页面只能组合它们：

- `AppNav`: 只处理真实小程序导航、安全区、返回、标题和胶囊避让；禁止伪时间、电量、Wi-Fi 和重复系统栏。
- `PageFrame`: 只处理页面 gutter、滚动容器、背景层、section 节奏和首屏密度。
- `WowPanel`: 只处理面板外框、材质、九宫格或 contain、内距、标题区、body 区和裁切。
- `MaterialImage`: 只处理低语义素材的 fit、透明边界、九宫格、压缩预算和 fallback。
- `GameObjectIcon`: 只处理真实职业、专精、天赋、装备、新闻缩略图和缺图 fallback，不接受 imagegen 伪造真实对象。
- `StatusBadge`: 只处理状态底座、glyph、颜色、文案和可选动作。盾牌、叹号、问号、OK、锁、队长标识必须共享同一个固定容器和中心点公式。
- `ActionButton`: 只处理主按钮、次按钮、disabled、loading、图标、触控热区和文字截断。
- `ModuleCard`: 只处理横向工作流卡片的图标槽、标题、指标、状态和入口，禁止把内容垂直堆成一坨。

任一页面如果绕过这些基础组件重新拼形状，直接判定为返工失败。

### State Component Contract

状态组件必须成为独立系统，不能再靠背景图或页面绝对定位拼出来：

- 底座和 glyph 永远分层。底座可以是 imagegen material；glyph 必须可替换、可居中、可按状态换色。
- 状态容器必须声明固定宽高、中心点、glyph 最大尺寸、文案区、动作区和安全内距。
- `blocked / partial / ready / stale / source_reference / unknown` 必须使用同一套几何规则。
- 任何“盾牌在一边、叹号在另一边”的实现直接失败；任何把叹号烘焙进盾牌底图的实现也直接失败。
- 状态组件必须有单独 crop、目标 overlay、中心点测量和多 glyph fixture，不能只在整页截图里通过。

### Layout Quality Stop List

以下问题只要出现在真实小程序截图里，对应页面不得进入 `runtime_verified`：

- 页面业务模块左右顶到屏幕边缘，或模块之间左右边界不在同一 gutter 系统。
- 职业、专精、tab label、状态文案、按钮文案不在所属槽位内居中或对齐。
- 按钮被压扁、文案贴边、outline 独立漂浮、触控热区不足。
- 工作流卡片主次不明，只剩图标、标题、指标纵向堆叠。
- 主标题、状态结论、主行动、关键指标字号过小，无法在手机尺寸下直接扫读。
- 素材层遮挡内容层，或内容位置依赖背景图空白。
- 横向滚动、列表行、卡片和 tab 靠 flex 自然挤压导致不同视口错位。
- 页面出现重复系统状态栏、伪电量、伪 Wi-Fi、伪胶囊或假导航。

### DevTools Incident Protocol

只要出现登录态失效、模拟器无响应、黑屏、自动化 endpoint 不可用，必须按事故处理：

- 先冻结高扰动动作，不继续尝试 `open/close/restart/cache/login/project switch`。
- 记录最近 30 分钟内所有 DevTools 相关命令、脚本、端口探测、截图和点击动作。
- 区分四类原因：自动化生命周期动作、项目/appid/缓存变更、多实例或端口抢占、微信自身会话机制。
- 如果我们执行过可能影响登录态的动作，默认先归因到流程问题，必须修流程再继续。
- 如果低扰动 health 不能证明 `captureSafe=true`，只能做 source/browser/component evidence，不能继续真实截图验收。
- 模拟器无响应时先检查资产体积、同步计算、循环、定时器、重复点击、`setData` 体积和页面递归渲染。

### Alternative Validation Lane

如果真实 DevTools 在当前时段不稳定，可以建立浏览器/adapter 预检 lane，但它不能替代小程序验收：

- 预检 lane 必须尽量复用真实 WXML/WXSS/JS 映射，不能写一个脱离源码的漂亮 HTML demo。
- 预检 lane 只负责发现 rect、overflow、slot、文本、素材 fit 和 crop 问题。
- 预检 lane 的输出状态最多是 `component_precheck` 或 `source/browser evidence`。
- 真实小程序恢复后，必须重新跑 runtime screenshot、component crop、overlay、scorecard 和 route smoke。

### Recovery Execution Order

后续执行顺序固定为：

1. 锁定当前真实截图和用户红区，确认不是旧缓存或 browser 替代图。
2. 锁定目标图，拆红线、组件、素材、状态、数据和路由。
3. 先实现基础组件和素材 manifest，再接页面。
4. 每个组件先单独 crop 和 overlay，再进入页面。
5. 页面接入后先 browser precheck，再真实小程序截图。
6. 真实截图失败时先回组件或素材，不继续在页面上随机调参。
7. route smoke 失败时页面视觉分不能通过。
8. 任何阶段超过时间阈值仍无量化进展，必须输出失败原因和替代路线。

## 2026-07-06 Strict System Contract

这次更新把 goal 从“先修生产流程”继续收紧为“没有系统契约就不能继续做页面”。触发原因是：工作台状态盾牌、资讯频道 dock、今日重点列表、重复系统 chrome、边距溢出、字号过小、登录态失效和模拟器无响应，都说明问题已经跨越单个页面，属于 UI 架构、素材架构、验证架构共同失控。

### Failure Diagnosis Lock

以下问题不得再被解释为“局部样式没调好”：

- 状态徽章分裂成底图和漂浮 glyph，说明 `StatusBadge` 组件几何失败。
- 页面左右顶边、模块错开、内容贴边，说明 `PageFrame` gutter 和 `WowPanel` 内距所有权失败。
- 字号过小、卡片主次不明，说明信息架构和组件排版失败。
- 重复时间、电量、Wi-Fi、胶囊，说明 `AppNav` / 原生 chrome 边界失败。
- 按钮被压扁、outline 漂浮，说明 `ActionButton` slot 和触控热区失败。
- Browser 预检好看但小程序坏，说明验证 lane 没有复用真实组件约束。
- 频繁登录失效、模拟器无响应，说明自动化流程必须先被审计，不能继续当作普通环境噪声。

只要这些问题重复出现，页面实现必须暂停，回到对应基础组件、素材切片或验证脚本，不得继续在业务页面上改 `margin/padding/top/left`。

### Production Entry Checklist

任何核心页面进入 WXML/WXSS 实现前，必须同时具备以下 6 个输入包；缺一项只能停在 `draft` 或 `design_locked`：

- `architecture packet`：页面使用哪些基础组件、页面只负责哪些组合、哪些视觉职责禁止在页面层实现。
- `asset packet`：imagegen 低语义素材、真实 WoW 图标来源、切片边界、透明留白、文件大小、fit 策略和 manifest。
- `component packet`：每个组件的固定尺寸、slot、状态、长文本、缺图、空态、点击热区和 overflow 策略。
- `data packet`：真实接口字段、本地模板字段、fallback 字段、禁止伪造字段和状态判断来源。
- `route packet`：进入、返回、tab 切换、展开、跨页跳转、失败态和恢复路径。
- `verification packet`：当前图、目标图、实现图、组件 crop、overlay、scorecard、route smoke、DevTools action log。

没有这些输入包时，允许做文档、harness、组件 fixture、素材 manifest 和测试；不允许继续改核心页面布局。

### Component Ownership Lock

页面不得再承担基础 UI 职责：

- `AppNav` owns：原生导航避让、返回、标题、安全区、胶囊距离；页面不得伪造系统状态栏。
- `PageFrame` owns：全局 gutter、滚动容器、背景层、section 间距；页面不得自己定义左右边界体系。
- `WowPanel` owns：面板材质、边框、九宫格或 contain、标题区、body 区、裁切和内距。
- `MaterialImage` owns：所有低语义 imagegen 素材的 fit、透明边界、压缩预算和 fallback。
- `GameObjectIcon` owns：真实职业、专精、天赋、装备、新闻缩略图和缺图 fallback。
- `StatusBadge` owns：状态底座、glyph、中心点、颜色、文案和动作；叹号、问号、OK、锁、队长标识必须共用同一 slot。
- `ActionButton` owns：主按钮、次按钮、disabled、loading、图标、触控热区、文本截断和按压态。
- `ModuleCard` owns：横向卡片图标槽、标题、指标、状态、入口和固定列宽。
- `EvidenceLedger` owns：证据行、来源状态、checkedAt、coverage、blockers、展开收起和长文本策略。

如果某个页面没有使用对应基础组件，而是在页面内重新拼同类结构，该页面不能进入 `runtime_verified`。

### Pixel And Layout Measurement Lock

视觉评分必须从测量结果产生，不得人工给高分：

- 每个页面必须有当前图、目标图、实现图三方对照；缺任何一方不得打分。
- 目标 vs 实现必须输出 overlay 和红区；红区必须标明组件名、slot、偏差值和修复归属。
- 页面 gutter、模块边界、按钮高度、图标槽、状态中心点、字号、行高和文本溢出必须可测量。
- 组件分数不能被整页氛围图掩盖；状态组件、导航、频道 dock、重点列表、工作流卡片、证据行必须分别给通过/失败。
- 90% 还原只允许在真实小程序截图、组件 crop、overlay 和 route smoke 全部存在后出现；browser harness 最高只能给 `component_precheck`。
- 任一核心组件低于通过线，整页不得用平均分通过。

### Route And Interaction Lock

“页面看起来对”不等于产品完成。每个核心页面必须至少验证：

- 当前页面首屏、下滚、展开/收起、切换和空态。
- 页面内主行动、次行动、返回、tab 切换和跨页跳转。
- 进入目标页后能识别来源，返回后状态不丢失。
- 阻断态、缺图、长文本、接口失败、模板为空和加载中。
- 工作台相关路径必须覆盖装备、天赋、SimC、队长四条跳转与返回。

没有 route smoke 的视觉稿，只能算静态实现，不能算真实可用 UI。

### DevTools Automation Lock

DevTools 自动化必须改成“审计优先、低扰动默认”：

- 所有 DevTools 相关脚本必须写入 action log，记录时间、命令、目标、是否高扰动、是否触碰登录态、结果。
- 默认禁止 `cli open`、`cli close`、`cli auto` 循环、清缓存、切项目、切 appid、重启、重登、删除用户目录。
- 用户一次性允许高扰动动作，不等于后续默认允许；每次高扰动动作都必须有当次理由和日志。
- 登录态失效时，先排查最近 action log、窗口实例、端口、项目配置、缓存目录和脚本调用，再判断是否可能是微信自身机制。
- 模拟器无响应时，先排查同步计算、定时器、重复点击、页面递归、`setData` 体积、大图资产和图片解码，再继续截图。
- 如果不能证明 `captureSafe=true`，不得运行真实点击和截图；只能停在 source/browser evidence。

### Multi-Candidate Recovery Rule

当一个方向连续失败时，必须并行保留替代方案，而不是死磕同一个坏实现：

- 同一组件两轮仍有基础边距、居中、fit、overflow、字号问题，必须重建组件契约或素材切片。
- 单个页面两小时内没有可量化改善，必须暂停页面实现，产出至少两个可执行替代 layout 方案。
- 替代方案必须差异明显：例如素材驱动、组件驱动、信息密度驱动，而不是同一布局换颜色。
- 被淘汰方案必须保留为失败样本，记录失败原因，避免后续回到同一个坑。

### Completion Definition

本轮真正的完成不是某一张图“看起来还行”，而是：

- 基础组件系统稳定，并能解释之前出现的盾牌、边距、字号、重复 chrome、卡片堆叠问题为什么不会复发。
- imagegen 素材进入 manifest，可切、可复用、可替换，不再把整页效果图当生产图。
- 真实 WoW 素材来源清楚，不由 imagegen 臆造职业、专精、天赋、装备或事实。
- 首页、资讯、职业 tab、当前专精工作台、模拟器、队长、任务、个人页都进入同一场景矩阵。
- 每个核心场景都有真实小程序截图、组件 crop、overlay、scorecard 和 route smoke。
- DevTools 自动化不再破坏用户登录态；若登录态失效，action log 能证明是否由我们触发。

## 2026-07-06 Execution Control Lock

这次更新继续收紧 goal：`packet complete` 只是进入实现前的最低条件，不等于可以直接改页面。后续任何核心 WXML/WXSS 改动都必须先拿到受控 implementation permit。没有 permit 时，只能做文档、组件契约、harness、素材 manifest、source scan 或测试，不能继续在生产页面上调样式。

### Execution Control Lock

- 页面不是调参画布。页面只能组合基础组件、绑定真实数据和路由，不负责修组件内部几何。
- 每次生产改动必须先声明唯一 surface、唯一主组件 owner、允许文件、禁止文件、目标红线、素材来源、数据边界和路由 smoke。
- 任何没有 owner 的视觉块不能进入页面；任何 owner 只靠 class 命名、没有 slot/尺寸/状态证据，也不能算通过。
- `PageFrame`、`WowPanel`、`StatusBadge`、`ActionButton`、`ModuleCard` 这类基础结构不得在页面层重新拼一份。
- 如果一处改动同时影响 material、content、state、interaction 四层，必须拆成多个组件/素材任务，不能一次混改。

### Implementation Permit

每次允许改核心页面前，必须有一个 permit，至少包含：

- target surface 和 route。
- 本次唯一主组件 owner，以及涉及的辅助组件。
- 当前真实截图；如果拿不到真实截图，必须写明只能停在 source/browser evidence。
- 目标图或目标组件 crop。
- redline、slot measurement、字号、按钮、图标槽和状态槽约束。
- 允许修改的生产文件。
- 禁止修改的生产文件和 no-touch 区域。
- imagegen / 真实 WoW 素材 manifest 条目、文件大小和 fit 策略。
- 真实接口字段、本地字段、fallback 字段和禁止伪造字段。
- route smoke 计划，包括进入、切换、展开、跳转、返回、失败态。
- rollback 或 quarantine 方案，确保失败样本不会被覆盖。

没有 permit 的 WXML/WXSS 改动，默认判定为流程失败，即使截图局部变好也不能进入验收。

### Evidence Promotion

证据状态只能按以下顺序晋级，不能跳级：

- `draft -> design_locked`：必须具备当前图或 blocker、目标/红线、组件契约、素材/数据/路由边界。此阶段禁止页面实现。
- `design_locked -> component_precheck`：必须具备组件 harness、slot rect、text metrics、asset fit、glyph center 检查。此阶段禁止 runtime 通过声明。
- `component_precheck -> source_integrated`：必须具备 implementation permit、生产 ownership hook、source scan 和 browser layout audit。此阶段禁止页面级拼形状。
- `source_integrated -> runtime_verified`：必须具备 `captureSafe=true`、新鲜真实小程序截图、组件 crop、overlay、scorecard 和 route smoke。OS fallback、browser-only 和旧缓存图禁止晋级。
- `runtime_verified -> final_accepted`：必须具备完整场景矩阵、零容忍失败为空、用户认可。失败场景不能从总分里消失。

### Zero-Tolerance Runtime Failures

以下问题一旦出现在真实小程序截图、route smoke 或 DevTools action log 中，对应 surface 必须降级，不允许平均分放行：

- 重复系统 chrome、伪时间、伪电量、伪 Wi-Fi、伪胶囊。
- 页面业务模块顶边、gutter 分裂、模块边界错位。
- 状态 glyph 漂移、底座和 glyph 分裂、语义状态烘焙进底图。
- 按钮被压缩、outline 漂浮、触控热区不达标。
- 关键文字溢出、贴边、字号低于阅读底线。
- imagegen 伪造真实 WoW 职业、专精、天赋、装备、新闻事实或来源。
- 生产页面引用 manifest 外素材或 reference-only 效果图。
- 关键 route smoke 缺失，或进入目标页后无法返回/状态丢失。
- DevTools 登录态相关动作没有 action log，或高扰动动作被当作默认流程。

### Timebox And Alternative Rule

- 同一组件同一几何问题连续两轮未改善，必须停止调 CSS，回到组件契约或素材切片。
- 单个组件 60 分钟没有可测量改善，必须输出失败原因、替代组件方案和是否需要重切素材。
- 单个页面 2 小时没有可测量改善，必须暂停当前方向，同时提出至少两个差异明显的 layout 方案。
- 失败产物必须保留为样本，不能覆盖后假装没有发生。
- 替代方案必须在信息架构、素材策略或组件结构上真的不同，不能只是同一套布局换颜色。

## 2026-07-06 Foundation Reset Lock

这次更新把 goal 从“带 permit 的受控实现”继续收紧为“先完成系统地基，再恢复任何页面实现”。触发原因是：资讯页、工作台、频道 dock、状态盾牌和 DevTools 验证问题已经证明，当前 permit 仍然会把执行拉回单页面调 CSS。后续所有旧 permit 先暂停，不能继续作为生产页面写入依据。

### Permit Suspension

- 现有 `news_home_and_feed` implementation permit 立即降级为 `implementation_permit_suspended`。
- `implementation_permit_suspended` 只保留为历史证据和问题边界，不允许继续修改 `pages/news/news.wxss`、`components/channel-dock/*`、`components/ranked-feed/*` 或任何核心页面样式。
- 任何旧的 `scopedSourceEditsAllowed=true` 结论作废；新的默认值必须是 `scopedSourceEditsAllowed=false`。
- 重新开 permit 前，必须先通过 `Foundation Reset Gate`；不能在同一个旧 permit 上补字段后继续执行。
- 如果实现已经进入坏方向，必须保留失败截图、失败 crop、失败 CSS diff 和失败原因，不能覆盖后继续当作同一路线。

### Foundation Reset Gate

以下 8 项全部完成前，核心页面 WXML/WXSS 保持冻结：

- `component source contract`：基础组件必须有真实源码入口、清晰 props/slot/状态表和 owner，不能只有页面 class 或设计文档。
- `asset slice manifest`：imagegen 低语义素材、真实 WoW 图标、透明边界、文件大小、fit 策略、语义等级和 quarantine 状态必须进入 manifest。
- `component fixture matrix`：每个基础组件必须覆盖 ready、blocked、partial、stale、source_reference、unknown、缺图、长文本、空态、compact/standard/large。
- `measurement pipeline`：必须能输出 target/current/implementation rect、gutter、字号、按钮高度、glyph center、overflow、overlay 和红区归属。
- `route smoke harness`：必须覆盖首页、资讯、职业 tab、工作台、模拟器、队长、个人页的进入、切换、展开、跳转、返回和失败态。
- `devtools action ledger`：所有 DevTools 相关动作必须写入 action log；没有 `captureSafe=true` 时只能停在 source/browser evidence。
- `cross-surface shell audit`：AppNav、PageFrame、WowPanel、StatusBadge、ActionButton、ModuleCard 等基础组件必须能解释重复 chrome、顶边、错位、压缩按钮、状态漂移为什么不会复发。
- `re-permit decision record`：重新允许某个 surface 实现前，必须写明为什么恢复、从哪个新 permit 开始、允许文件、不改范围、验证产物和失败回退。

### Page Freeze While Resetting

- 允许做：文档、组件契约、真实素材清单、imagegen 切片、manifest、fixture、browser harness、measurement script、route smoke plan、测试。
- 禁止做：直接改核心页面 WXML/WXSS、在页面层修状态徽章、用页面 margin/padding 顶布局、把整页效果图接入生产、绕过组件 source contract 调样式。
- 如需验证想法，必须在组件 fixture 或隔离 harness 中做；fixture 通过只能晋级到 `component_precheck`，不能直接进入页面。
- 只有 `Foundation Reset Gate` 通过后，才能为一个 surface 新建 permit；新 permit 必须重新声明当前目标、组件 owner、素材、数据、路由和验收矩阵。

### Updated Next Step

当前下一步不是继续修资讯页 CSS，而是产出 `pass37 foundation reset package`：

- 列出全小程序基础组件真实源码落点和缺口。
- 列出当前生产素材与 imagegen 切片 manifest 的缺口。
- 建立至少 AppNav、PageFrame、WowPanel、MaterialImage、GameObjectIcon、StatusBadge、ActionButton、ModuleCard、EvidenceLedger 的 fixture 矩阵。
- 建立 target/current/implementation 的测量和 overlay 输出规则。
- 建立低扰动 DevTools action ledger，并把登录态/模拟器无响应作为验证流程事故处理。
- 重新生成 readiness report，让旧 permit 显示为 `implementation_permit_suspended`，而不是下一步执行入口。

## 2026-07-06 Architecture Reset Gate v2

这次更新继续收紧 goal：当前失败不是某一个页面没调好，而是“目标图 -> 素材 -> 组件 -> 页面 -> 路由 -> 真机截图”的生产链路没有稳定下来。后续不能再把页面当作画布，也不能用单个局部组件修复来证明整体方向正确。

### Root Cause Override

以下问题必须归因到系统层，不得继续按局部 CSS 处理：

- 页面内容顶边、模块错位、边距不统一：归因到 `PageFrame / WowPanel` ownership 失败。
- 状态盾牌、叹号、问号、OK、锁错位：归因到 `StatusVisual / StatusBadge` contract 失败。
- 字号过小、卡片内容堆叠、重点不可扫读：归因到信息架构和组件排版失败。
- 背景杂乱、素材压住内容、元素像贴片：归因到 asset slicing 和 material/content 分层失败。
- 重复时间、电量、Wi-Fi、胶囊：归因到 `AppNav` 与微信原生 chrome 边界失败。
- 真实截图与目标图差距大却给高分：归因到 measurement pipeline 失败。
- 登录态频繁失效或模拟器无响应：归因到 DevTools workflow incident，除非 action ledger 能证明不是我们触发。

只要同类问题复现，本轮实现必须停止页面调参，回到对应组件、素材或验证链路。

### Real Component Gate

`PageFrame`、`WowPanel`、`GameObjectIcon`、`StatusBadge`、`ActionButton`、`ModuleCard`、`EvidenceLedger` 必须成为真实可复用组件或明确的基础 runtime owner。仅靠页面 class、全局样式、helper mapping 或设计文档不再算通过。

重新打开任何页面级 permit 前，至少要满足：

- 组件有真实源码入口，包含 `json/js/wxml/wxss` 或等价 runtime owner。
- 组件拥有固定尺寸、slot、状态、长文本、缺图、空态、点击热区和 overflow 策略。
- 组件能在 fixture 中单独裁切，不依赖业务页面背景或父级绝对定位。
- 页面只能组合组件和绑定真实数据，不得重新实现组件内部几何。
- 如果某基础组件暂时只能是 helper 或 class contract，必须在 reset package 中保持 blocker，不能被算进 permit 通过项。

### State Visual Contract v2

状态视觉允许两种生产模式，但都必须由同一个组件 owner 管理：

- `layered`：无语义底座素材 + 可替换 glyph。适合需要统一底座、换叹号/问号/OK/锁的状态。
- `atomic`：整枚状态图标作为一个可替换资产，例如完整的“盾牌 + 叹号”。适合 imagegen 或手工切出的单枚图标，但必须按状态族提供同尺寸、同透明边界、同 `contain` 策略的变体。

无论选择哪种模式，都必须满足：

- 页面中只能出现一个状态视觉组件实例，不能把底座和 glyph 分别放在两个页面元素里。
- 容器宽高、透明边界、中心点、glyph 或整图最大尺寸必须固定。
- `blocked / partial / ready / stale / source_reference / unknown` 至少要有 fixture；未来换问号、OK、锁时不得改页面布局。
- 状态图标不能包含业务文字、DPS、评分、readiness 结论或真实 WoW 对象图标。
- 真实小程序 crop 必须测量中心偏差、尺寸偏差和 overflow；只看整页截图不算通过。

这条替代早先过度僵硬的“必须拆底座和 glyph”表述：工程目标不是形式上拆层，而是状态视觉必须可替换、可居中、可适配、可复用，并且不再由页面拼接。

### Design Candidate Gate

每个核心 surface 进入实现前，必须先出可比较的设计候选，而不是盯着一个坏方向死磕：

- 至少 2 个候选，优先 3 个候选；候选之间必须在信息架构、素材密度、首屏节奏或导航结构上有真实差异。
- 候选必须来自同一套产品事实和真实 WoW 素材边界，不能为了视觉效果伪造职业、天赋、装备、新闻事实或评分。
- 用户确认目标方向后，只保留一个为 `target_locked`，其余进入 reference/quarantine，不能混着实现。
- `target_locked` 后必须产出红线、组件拆解、素材切片和适配策略，不能直接把整张目标图当背景。

### Asset Slicing Gate v2

imagegen 仍然必须使用，但进入生产前必须完成切片和语义降级：

- 整页效果图只能做 reference；生产代码只能引用 manifest 中的切片。
- 每个切片必须标记为 `material / object / state-base / state-atomic / glyph / decorative / reference-only / quarantined`。
- `state-atomic` 资产允许包含完整状态图标，但必须是可替换状态族，不得和文字、业务结论或真实对象混在一起。
- 真实 WoW 职业、专精、天赋、装备、新闻来源图标必须来自真实接口、Battle.net/WebSim 映射、仓库验证资产或用户明确提供素材。
- 背景、面板、边框、纹理必须有 `contain / cover / slice / repeat` 策略和文件大小预算；素材不得靠天然空白替内容让位。
- 任何 manifest 外素材进入生产页面，直接降级为 `blocked_asset_contract_violation`。

### Measurement Gate v2

以后不能再口头说“90%”或“差不多”。每次视觉结论必须有同一套测量证据：

- 当前真实截图、目标图、实现截图三方必须齐全；缺一项不得打最终分。
- 每个核心组件必须有 crop、target crop、overlay 和 red-zone。
- red-zone 必须写清：组件名、slot 名、偏差类型、偏差值、归属 owner、修复方式。
- 必测项包括 gutter、模块边界、面板内距、图标槽、状态中心点、按钮高度、字号、行高、文本 overflow、图片 fit、重复 chrome。
- 任一零容忍项出现，页面直接失败，不允许用平均分盖过去。
- browser harness 最高只能给 `component_precheck`；真实小程序截图、crop、overlay 和 route smoke 不全时，禁止给最终分。

### Route Coverage Gate v2

这次 UI 返工必须证明“像 App 一样可用”，不只是截图好看：

- 每个核心 surface 必须先有 route map，再进入页面实现。
- route smoke 至少覆盖进入、返回、tab 切换、展开/收起、主行动、次行动、失败态恢复。
- 工作台必须覆盖装备、天赋、SimC、队长四条跳转与返回。
- 首页/资讯必须覆盖频道 dock、今日重点列表、详情进入、详情返回和下滚状态。
- 职业 tab 必须覆盖职业切换、专精切换、工作台入口和旧入口可达。
- 模拟器、队长、任务、个人页不能从本轮验收矩阵里消失；暂未做必须列 blocker。

### DevTools Preservation Gate v2

微信开发者工具当前登录态必须被当作用户资产保护：

- 默认流程不得关闭、重启、清缓存、重新登录、切 appid、切项目、打开新项目实例或删除用户目录。
- 所有 DevTools 相关动作必须写入 action ledger，区分 read-only、low-impact、high-impact。
- 已获得的一次授权只覆盖当次明确动作，不得变成后续默认高扰动权限。
- 如果登录态失效，先审计我们最近是否执行过生命周期、缓存、项目、端口、多实例相关动作；没有 action ledger 不得甩给微信机制。
- 如果模拟器无响应，先检查图片体积、同步计算、递归渲染、定时器、重复点击、`setData` 体积和长列表渲染，再继续视觉验证。
- `captureSafe=false` 时只能做 source/browser/component evidence，不能继续点击和截图验证。

### Restart Condition

满足任一条件，必须重开 surface 方案，不得继续在同一路线缝补：

- 同一布局问题连续两轮真实截图仍存在。
- 同一组件 60 分钟内不能解决基础尺寸、居中、contain、overflow 或字体问题。
- 页面实现与目标图核心结构差距明显，但 scorecard 仍试图给高分。
- 用户指出的问题属于层级、素材、组件或路由系统，而当前改动只在页面 CSS 上补丁。
- 新增修复制造了新的重复 chrome、边距分裂、状态错位、按钮压缩或文本溢出。

重开方案时必须保留失败截图、失败 diff、失败原因和替代路线，不能覆盖后继续伪装成同一条进度。

## Updated Working Goal

重建 WOW 小程序的前端 UI 生产链路，而不是继续在现有页面上局部修补。最终交付必须同时满足：

- 执行口径更新为 `pass37 strict-system-contract + execution-control-lock + foundation-reset-lock + architecture-reset-gate-v2`：先完成系统地基、素材、组件、测量、路由和 DevTools action ledger，再为具体 surface 重新生成 scoped implementation permit，之后才允许页面实现。
- 设计目标完整：每个核心页面都有当前真实截图、目标图、组件拆解图和问题红区。
- 素材链路完整：imagegen 只进入可切分、可复用、可适配的素材工作流，不把静态效果图直接当页面。
- 组件架构完整：页面只能组合稳定基础组件，再接真实业务数据和路由。
- 小程序验证完整：所有核心场景都用真实微信小程序截图、组件 crop、overlay、scorecard 和 route smoke 验收。
- 登录态保护完整：验证过程不得因为自动化脚本破坏微信开发者工具登录态、项目状态或用户当前窗口。

如果上述任一项缺失，本轮只能标记为 `source/browser evidence`、`component_precheck`、`implementation_permit_suspended` 或 `diagnosis`，不得标记视觉通过、90% 还原或完成。

## Design Read

- 产品类型：微信小程序原生 C 端工具型 App，不是网页 landing、不做纯营销视觉。
- 目标用户：普通 WoW 玩家和资深构筑玩家，共用一个高密度但可扫读的信息架构。
- 视觉方向：魔兽题材感 + 现代移动 App 可用性，强调真实对象图标、清晰状态、可操作路径。
- 密度方向：首屏高密度驾驶舱，但不牺牲边距、字号、层级和触控可用性。
- 设计约束：可以重 UI、可以有材质底图，但底图只能服务结构和氛围，不能吞掉内容层、状态层和交互层。

## Hard Constraints

- 不再把状态结论、叹号、问号、OK、锁、评分等语义画死在背景素材里。
- 所有状态组件必须拆成：固定容器、无语义底座素材、状态 glyph、状态文案、可选交互入口。
- imagegen 只生成低语义 UI 材质：面板、边框、底座、空 socket、纹理、氛围底图、状态底座。
- imagegen 可以生成通用 glyph 或可复用装饰符号，但必须作为独立资产接入组件，不得和业务底座、真实图标、文字或状态结论烘焙在同一张图里。
- imagegen 不生成真实 WoW 职业、专精、天赋、装备、来源 logo、新闻事实、DPS、评分、提升优先级或 readiness 结论。
- 魔兽真实图标必须来自接口、Battle.net/WebSim 读模型、真实 `gameAsset.iconUrl` 或仓库内已验证映射。
- 任何 UI 不得伪造系统 chrome：不得重复时间、电量、Wi-Fi、胶囊、系统导航栏或微信原生状态栏。
- 浏览器预览只能作为预检，不能替代真实微信小程序截图。
- DevTools 验证不得默认关闭、重启、清缓存、重新登录或破坏用户当前登录态；只有明确授权才允许高扰动动作。
- 没有 `captureSafe=true`、真实场景截图、组件裁切、overlay、scorecard 和路由 smoke，不得宣称视觉验收通过。
- 单个组件看起来可接受不代表页面通过；单个页面看起来可接受不代表全小程序通过。

## Non-Negotiable Execution Rules

- 禁止直接在业务页面里靠反复调 `margin/padding/top/left` 猜 UI。任何核心区域返工前，必须先有组件契约、尺寸表和素材切片表。
- 禁止用整张 imagegen 效果图铺底后在上面堆文字。效果图必须拆成 app shell、panel、texture、icon slot、state base、glyph、content 和 interaction。
- 禁止把浏览器截图、静态 HTML、OS fallback 图或旧缓存截图当作小程序事实。它们只能帮助定位问题，不能进入最终通过证据。
- 禁止在验证脚本里自动关闭、重启、清缓存、切换项目、重新登录微信开发者工具。若 `captureSafe=false`，脚本必须停止在诊断层，不得强行修复登录态。
- 禁止只验证静态首屏。任何页面通过前，必须验证主要点击、展开、切换、返回和跨页跳转。
- 禁止以“差不多”“比上一版好”作为通过理由。必须有当前图、目标图、实现图、overlay、红区和 scorecard。
- 禁止把单一页面局部优化包装成全局 UI 优化。首页、资讯、职业 tab、工作台、模拟器、队长、任务和个人页必须进入同一套审计矩阵。
- 禁止为追求视觉强度牺牲可读性。首屏关键结论、主按钮、模块标题、状态和指标必须在真实手机尺寸下直接可读。

## Failure Corrections

以下问题一旦出现，直接判定本轮实现未通过，不允许用“接近”“差不多”放行：

- 页面模块左右顶到屏幕边缘，和全局背景、面板边框或安全区错位。
- 文本没有在所属组件内垂直/水平对齐，例如职业、专精、tab label、模块标题偏移。
- 状态底座和 glyph 被拆散成互不受控的两个视觉元素，例如盾牌和叹号错位。
- 按钮被内容压缩、outline 失控、点击热区小于组件视觉预期。
- 工作流卡片只有纵向堆字，没有主次信息、状态、指标和入口层级。
- 字号普遍过小，玩家需要放大才能读首屏关键结论。
- 素材像背景贴片堆叠，而不是受组件尺寸、裁切和层级约束。
- 页面能截图但关键跳转、展开、切换、返回没有验证。
- 浏览器 harness 看起来正常，但真实小程序黑屏、错位、缓存旧图或登录态被破坏。

## Source Of Truth

- 产品事实以当前代码、真实接口、`docs/roadmap.md`、`docs/ui-style-guide.md` 和已确认产品简报为准。
- 视觉目标以已选 imagegen 目标图、用户标注截图、当前真实小程序截图共同作为参考，但 imagegen 图不提供事实、数据或真实图标来源。
- 真实对象图标以接口返回、Battle.net/WebSim 映射、仓库内已验证资产为准。
- 当前真实小程序截图是布局问题的事实来源；浏览器图只用于快速定位，不用于最终验收。
- 任意评分、readiness、DPS、提升优先级、S/A 级必须来自明确证据链；缺证据时只能展示 blocker、partial、stale 或 source_reference。

## UI Architecture

### Layer Model

每个页面必须按固定层级实现：

1. App shell：导航、安全区、全局背景、页面边界。
2. Page shell：页面级布局、滚动容器、首屏密度、统一 gutter。
3. Material layer：低语义 bitmap 材质，仅负责框架、质感、分区。
4. Content layer：真实业务数据、真实图标、标题、状态文案。
5. State layer：状态 glyph、badge、blocking/partial/ready/stale/source-reference 语义。
6. Interaction layer：按钮、picker、tab、展开、跳转、反馈。

任何素材如果同时承担 material 和 state/content 职责，必须拆分。任何组件如果必须依赖整页背景才显得正常，必须重做。

### Layout Contract

- 页面级内容必须有统一 gutter；除全局背景和明确的沉浸式首屏外，业务模块不得贴屏边。
- 每个模块必须有自己的固定外框、内距、内容区和溢出策略。
- 所有组件默认 `box-sizing: border-box`，内部 image 使用 `contain` 或明确裁切规则，不允许随内容撑开容器。
- 状态 glyph 必须由组件居中定位，中心偏差不得超过 4rpx。
- 触控目标高度不得低于 64rpx；主要按钮不得被压缩成不可识别的条状。
- 首屏关键标题、状态结论和行动按钮不得低于可读字号；辅助 meta 才允许小字号。
- 横向多卡组件必须定义列宽、间距、最大/最小高度和文本截断，不允许靠 flex 自然挤压。
- 页面滚动区、固定导航、底部 tab、安全区必须各自归属清晰，不能互相覆盖。
- App shell 只能有一套状态栏/导航栏归属。使用自定义导航时必须显式避让微信胶囊和安全区；使用原生导航时不得再绘制假时间、电量、Wi-Fi 或胶囊。
- 页面外框、业务面板和材质边框必须在同一 gutter 系统内对齐；若目标是全幅材质，也必须说明哪些层可全幅、哪些内容层仍受 gutter 约束。
- 文字不能依赖背景图留白“碰巧不挡住”。所有标题、meta、指标、按钮文案都必须拥有自己的布局区域、行高和截断策略。
- 图标槽、按钮槽、状态槽必须有固定宽高和对齐规则；不得由图片天然尺寸、文字长度或 flex 挤压决定最终大小。

### Asset Contract

每张素材必须写入或可追踪到资产职责：

- `material`: 面板、边框、底座、纹理、空槽、背景氛围。
- `object`: 职业、专精、天赋、装备、新闻缩略图等真实对象。
- `state-base`: 无语义状态底座，例如盾牌空底座。
- `glyph`: blocked/ready/partial/stale/source_reference 的状态符号。
- `decorative`: 非信息装饰，只能低权重出现，不能影响阅读。

禁止项：

- 背景图里带业务文字、状态结论、可变数字、真实来源 logo 或真实 WoW 图标。
- 用 imagegen 伪造法师冰霜天赋、装备、新闻来源或游戏内图标。
- 为了好看把状态 glyph 烘焙进底座，导致问号、叹号、OK、锁无法复用同一组件。
- 图片比例不固定，靠视觉猜测摆放，导致不同视口错位。

每个 imagegen 资产进入代码前必须补齐资产清单：

- 原始生成图路径。
- 切片名称和职责。
- 透明边界或九宫格策略。
- 目标组件和槽位尺寸。
- `contain / cover / slice / repeat` 策略。
- 是否包含语义；如果包含语义，必须说明为什么不能由组件层表达。
- 真实 WoW 素材来源；若不是真实来源，必须标记为 material/decorative，不能用于对象事实。

## Component Contract

后续先做组件契约，再写页面。每个核心组件必须能单独裁切检查，不能只在整页里“看起来还行”。

- `WowPanel`：统一面板边框、内距、材质承重、clip/overflow、标题区和 body 区。
- `StatusBadge`：固定比例底座 + glyph 居中层，可扩展 `blocked / partial / ready / stale / source_reference / unknown`。
- `ModuleDock`：固定卡片尺寸、图标槽、标题、短指标、状态 badge、点击入口。
- `RankedFeed`：固定 5 行榜单、缩略图槽、频道 badge、标题、meta、收藏位。
- `ChannelDock`：固定 6 tab、图标底座、标签、选中态、禁止伪统计 badge。
- `EvidenceLedger`：证据行、来源状态、checkedAt、coverage、blockers、展开态。
- `WorkbenchHero`：当前职业/专精/英雄天赋、场景、readiness、主行动。
- `AppNav`：真实小程序导航占位、安全区、返回/标题/胶囊避让，不伪造系统栏。

组件交付要求：

- WXML 结构必须显式体现 material/content/state/interaction 分层。
- WXSS 必须声明固定尺寸、内距、行高、图片 fit、文本截断和溢出处理。
- JS 只接收业务数据和状态，不在组件内硬编码假的内容或假的评分。
- 每个组件至少有一个浏览器 harness crop 和一个真实小程序 crop。
- 每个组件必须有最小、标准、长文本、缺图、blocked、partial、ready、stale/source_reference 的样例状态，不能只为当前截图状态写死。
- 状态类组件必须通过同一个底座承载不同 glyph。叹号、问号、OK、锁、队长等符号都必须可替换且保持居中。
- 组件内部不得依赖父页面的负 margin、绝对定位补偿或隐藏 overflow 来“修视觉”。父页面只负责摆放组件，不负责修组件内部错位。

## Scope

### 必须覆盖的页面

- 资讯首页顶部。
- 资讯首页下滚后的频道 dock 与今日重点列表。
- 职业专精 tab。
- 当前专精工作台首屏。
- 当前专精工作台 evidence 展开。
- 当前专精工作台 `blocked / partial / stale / ready_to_simulate / source_reference` 状态。
- 天赋模拟器。
- 装备模拟器。
- SimC 校验页。
- SimC 任务列表与任务详情。
- 炸鸡队长入口与聊天页。
- 个人模板页。

### 必须覆盖的交互

- 底部 tab 切换。
- 职业、专精、英雄天赋、场景切换。
- 工作台主行动跳转到装备、天赋、SimC、队长。
- evidence 展开/收起。
- 资讯频道切换、新闻列表滚动、新闻详情进入/返回。
- 模板保存、导入、缺失态、阻断态。
- SimC 校验、提交阻断、任务进入详情。
- 炸鸡队长新话题、会话返回、输入区聚焦和长消息滚动。

### 必须覆盖的验收视图

- 当前真实小程序截图。
- 用户认可的目标图或目标组件图。
- 组件拆解图：material/content/state/interaction 分层。
- 实现后的真实小程序截图。
- 当前 vs 目标 overlay。
- 目标 vs 实现 overlay。
- 红区问题图。
- 组件 crop 图。
- 路由 smoke manifest。

没有这些视图，不得进入最终验收。

## Execution Workflow

每个页面或组件必须按以下顺序推进：

1. 截取当前真实小程序图，标出红区问题。
2. 选定目标图或目标组件，拆成外框、材质、真实图标、文字、状态、交互层。
3. 输出组件尺寸表和资产切片表，再开始写 WXML/WXSS。
4. 先在组件 harness 验证 rect、overflow、字号、居中和素材 contain。
5. 再接入真实页面，验证页面 gutter、模块节奏、滚动和层级。
6. 浏览器预检通过后，才进入 DevTools 真实截图。
7. 真实小程序截图生成当前/目标/overlay/红区对比和 scorecard。
8. 路由 smoke 验证关键点击路径，不允许只验静态截图。

如果同一个视觉问题连续两轮仍未修好，必须停止继续调参，回到组件契约和素材切片重新设计。

执行过程中必须保持两条并行证据线：

- Design evidence：目标图、切片图、组件尺寸、资产清单、交互流程。
- Runtime evidence：源码、浏览器 harness、真实小程序截图、crop、overlay、route smoke。

Design evidence 不能替代 Runtime evidence；Runtime evidence 也不能在没有设计拆解时直接通过。

## Validation Gates

### 代码级

- Node 单测覆盖组件契约、状态模型、页面注册、路由参数、禁用强结论文案。
- WXML/WXSS 扫描禁止伪系统 chrome、假图标、假来源、假评分、假 readiness。
- 固定尺寸组件必须有 rect gate：宽高、padding、overflow、内部元素 containment。
- 组件不得把底座、glyph、文字、按钮混进同一张素材。
- `git diff --check` 必须通过。

### 浏览器预检

- 用真实 WXSS/WXML 映射生成组件 harness。
- 对核心组件做 DOM rect、横向 overflow、文本溢出、状态层级检查。
- 生成目标/当前/overlay/红区裁切图。
- 浏览器预检只能标记 `source/browser evidence`，不得写成最终验收。

### 小程序真实验收

- 只在 DevTools `captureSafe=true` 时运行真实截图。
- 不得关闭、重启、清缓存、切项目、重新登录或主动破坏用户当前 DevTools 状态，除非用户明确授权。
- 至少覆盖 compact / standard / large 三类视口。
- 至少覆盖 9 个核心场景 x 3 视口的截图矩阵。
- 需要真实小程序截图、组件裁切、overlay、scorecard、manifest。
- 路由 smoke 必须证明关键跳转路径可用。
- 任一场景使用 OS fallback、旧缓存、黑屏截图、source-only 图，不得计入最终通过。
- 登录态失效必须先作为自动化流程事故排查，不能默认归因给微信机制。排查项包括：是否启动了新 DevTools 实例、是否调用了 CLI open/close/reset/cache/login、是否切换 appid/project、是否清了用户目录、是否同时存在多个 DevTools 窗口。
- 如果需要高扰动动作，必须先写明动作、风险、回滚方式和为什么低扰动方案不足；得到用户明确同意后才执行。

### Visual Scorecard

视觉分不得靠主观口头判断，必须有可追踪评分项：

- 几何还原：模块边界、内距、行高、图标槽、按钮高度和中心点。
- 内容层级：标题、状态、指标、meta、行动入口是否一眼可扫。
- 素材还原：底图比例、裁切、透明边界、contain、层级遮挡。
- 状态表达：状态底座、glyph、文案、颜色是否统一且可复用。
- 交互可用：点击热区、跳转、展开、返回、滚动是否真实可用。

任何页面低于 90/100 不得标记为通过。若核心组件低于 90/100，该页面自动不通过。

90 分不是口头分，必须由以下硬指标共同支撑：

- 页面 gutter、模块边界、组件外框、图标槽、按钮槽和状态槽不得出现肉眼可见错位；关键边界偏差需要在 scorecard 里记录。
- 状态 glyph 中心偏差不得超过 4rpx；按钮、tab、卡片内部主轴对齐不得靠目测通过。
- 横向 overflow、文字顶边、文字贴边、按钮压缩、内容遮挡、重复系统 chrome 任一出现，相关页面直接失败。
- 如果目标图是 imagegen 生成图，实现图可以为适配小程序做理性调整，但调整必须在 scorecard 标注；不能用“适配”掩盖基础比例和层级失败。
- 如果未拿到真实小程序截图，只能给 source/browser 预估分，不能给最终视觉分。

## Acceptance Criteria

- 组件层：核心组件单独裁切后，边距、比例、状态、文本层级清晰，无内部溢出。
- 页面层：首页、职业 tab、工作台不再像素材堆叠或黑金卡片拼贴，而是统一 app shell 下的高密度工具 UI。
- 素材层：每张 imagegen 资产都有职责和边界；真实对象图标不由 imagegen 伪造。
- 状态层：`blocked / partial / ready / stale / source_reference` 均可通过同一组件系统表达。
- 交互层：关键页面跳转、返回、展开、切换、模板和 SimC 入口经过真实小程序 smoke。
- 验收层：没有真实 DevTools 截图与 overlay，不允许给 90% 或通过结论。

本轮“完成”只表示以下全部达成：

- 目标设计与小程序实现之间的主要组件达到可量化 90% 以上还原。
- 资讯首页、下滚列表、职业 tab、工作台、SimC、队长、任务、个人页均完成真实小程序截图矩阵。
- 至少一个完整用户路径从首页/职业 tab 进入工作台，再进入装备/天赋/SimC/队长并返回，经 route smoke 验证。
- 自动化验证不再造成 DevTools 登录态丢失；若微信自身失效，日志能证明自动化没有触发高扰动动作。
- 所有未完成或未通过场景明确列为 blocker，不隐藏在总分里。

## Immediate Next Step

`pass37 strict-system-contract` 已覆盖旧 `architecture-first` 和 `recovery-lock` 的宽松部分。下一步不是继续把 `ChannelDock`、`RankedFeed`、工作台或任意单页局部调好，而是先把本文件的系统契约转成机器可读输入包和拦截检查：

1. 生成 `pass37-strict-system-contract` artifact，覆盖 failure diagnosis、production entry checklist、component ownership、pixel measurement、route smoke 和 DevTools automation lock。
2. 更新 recovery tickets：每个 surface 必须补齐 `architecture / asset / component / data / route / verification` 六类 packet，缺 packet 时页面 WXML/WXSS 进入编辑冻结。
3. 更新 page integration map：页面接入必须证明使用基础组件 ownership，不能只加 class 或继续在页面内拼形状。
4. 更新 browser/component precheck：预检必须输出组件 crop、slot rect、overflow、fake chrome、text size、glyph center 和素材 fit 结果。
5. 更新 DevTools safety check：所有截图、点击和端口动作必须产出 action log；`captureSafe=false` 时不得进入 runtime 验收。
6. 只有上述拦截检查通过后，才选择第一个 surface 进入真实页面重构和小程序截图验收。

## Current Checkpoint

2026-07-06 goal 约束已升级：

- 本文件新增 `2026-07-06 Constraint Upgrade`，正式把执行口径切到 `pass37 architecture-first`。
- 旧 `pass36` 视觉通过、高分和 90% 还原口径全部降级为历史证据，必须重新通过目标红线、组件契约、素材 manifest、真实小程序截图和 route smoke。
- 下一步不再继续页面级调参，而是先产出 pass37 输入包：页面架构表、组件红线表、素材 manifest、验证矩阵和 DevTools 低扰动边界。
- 在真实小程序 runtime proof 缺失前，任何产物最多只能标记为 `design_locked`、`component_precheck` 或 `source/browser evidence`。

2026-07-06 recovery-lock 约束已追加：

- 当前执行口径从 `pass37 architecture-first` 收紧为 `pass37 recovery-lock`。
- 线程内 active goal 不能由工具直接改写，但本文件明确成为后续执行、验收和复盘的事实来源。
- 核心页面 WXML/WXSS 进入冻结态：没有重构工单、组件票据、素材票据、数据票据、路由票据和验证票据，不得继续页面调参。
- 基础组件优先级被锁定为 `AppNav`、`PageFrame`、`WowPanel`、`MaterialImage`、`GameObjectIcon`、`StatusBadge`、`ActionButton`、`ModuleCard`、`EvidenceLedger`。
- 状态组件必须拆分底座和 glyph，并通过固定容器、中心点公式、多状态 fixture、crop 和 overlay 验收；盾牌和叹号错位或烘焙为同一图都直接失败。
- DevTools 登录态失效、模拟器无响应、黑屏和 endpoint 不可用都升级为 incident protocol，不再用模糊解释带过。
- 浏览器/adapter lane 只作为预检，不能替代真实微信小程序截图、组件 crop、overlay、scorecard 和 route smoke。

2026-07-06 strict-system-contract 约束已追加：

- 当前执行口径从 `pass37 recovery-lock` 再收紧为 `pass37 strict-system-contract`。
- 目标不再是“修好某个页面”，而是先让架构、素材、组件、数据、路由、验证六类 packet 变成核心页面实现的前置条件。
- 新增 failure diagnosis lock：状态徽章错位、页面顶边、字号过小、重复 chrome、按钮压缩、browser/小程序不一致、登录态失效都必须归到具体系统层，不允许继续说成局部样式问题。
- 新增 component ownership lock：`AppNav`、`PageFrame`、`WowPanel`、`MaterialImage`、`GameObjectIcon`、`StatusBadge`、`ActionButton`、`ModuleCard`、`EvidenceLedger` 必须拥有对应 UI 职责，页面绕过组件拼同类结构直接失败。
- 新增 pixel and layout measurement lock：90% 还原只能由真实小程序截图、组件 crop、overlay、红区和 route smoke 支撑，任一核心组件低于通过线，整页不得平均分通过。
- 新增 route and interaction lock：视觉通过必须覆盖首屏、下滚、展开、切换、返回、跨页跳转、失败态和恢复路径。
- 新增 DevTools automation lock：所有 DevTools 相关动作必须记录 action log；默认禁止 open/close/auto 循环、清缓存、重启、重登、切项目、切 appid 和删除用户目录。
- 后续第一步改为生成和接入 strict-system-contract 的机器可读 artifact 与拦截检查，而不是继续页面级修补。

2026-07-06 pass37 strict-system-contract artifact 已落地：

- 新增 `artifacts/ui-v2-1-strict-restoration/create-pass37-strict-system-contract.js`，把 strict-system-contract 从文档约束变成机器可读 artifact，不触碰 DevTools，不生成 runtime screenshot。
- 产物位于 `artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-strict-system-contract.json` 和 `.md`。
- artifact 状态为 `strict_system_contract_locked`，`requiredPackets=6`、`componentOwners=9`、`failureDiagnosisLocks=7`、`pixelMeasurementRules=8`、`routeInteractionRequirements=10`、`executionControlLocks=8`、`implementationPermitRequirements=11`、`evidencePromotionRules=5`、`zeroToleranceRuntimeFailures=9`、`devtoolsProhibitedActions=9`、`failures=0`。
- `systemLock` 现在明确 `editPermitRequired=true`、`pageLevelTuningAllowed=false`；packet complete 不再等于可以直接改页面。
- `create-pass36-final-readiness-report.js` 已接入 `latestPass37StrictSystemContract`；总 readiness 仍为 `incomplete`，但 objective requirements 会显示 `pass37_strict_system_contract=strict_system_contract_locked`。
- `tests/ui-v2-1-strict-cut-contract.test.js` 已覆盖 required packets、`StatusBadge` / `EvidenceLedger` ownership、execution control lock、implementation permit、evidence promotion、zero-tolerance failures、DevTools 禁止动作、readiness 集成、source-only 边界和无 DevTools 控制。

2026-07-06 execution-control-lock 约束已追加：

- 新增 `2026-07-06 Execution Control Lock`，明确任何核心 WXML/WXSS 改动前必须有 scoped implementation permit。
- permit 必须绑定 target surface、route、主组件 owner、当前图或 source-only blocker、目标 crop、redline、允许文件、禁止文件、素材 manifest、真实数据字段、route smoke 和 rollback/quarantine 方案。
- 证据晋级被锁定为 `draft -> design_locked -> component_precheck -> source_integrated -> runtime_verified -> final_accepted`，禁止 browser-only、OS fallback、旧缓存图跳级。
- 零容忍失败包括重复系统 chrome、gutter 分裂、状态 glyph 漂移、按钮压缩、关键文字溢出、imagegen 伪造 WoW 事实、manifest 外素材、route smoke 缺失和未记录的 DevTools 登录态动作。
- `pass36-final-readiness-report` 已刷新，下一步明确为：下次生产 UI edit 前先创建一个只覆盖单个 surface 的 implementation permit。

2026-07-06 pass37 news surface implementation permit 已挂起：

- `artifacts/ui-v2-1-strict-restoration/create-pass37-news-surface-implementation-permit.js` 仍保留 `news_home_and_feed` 的历史边界证据，但它不再授权 source edit。
- 产物位于 `artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-news-surface-implementation-permit.json` 和 `.md`。
- permit 当前状态为 `implementation_permit_suspended`，`surfaceId=news_home_and_feed`、`route=pages/news/news`、`primaryOwner=PageFrame`、`scopedSourceEditsAllowed=false`、`unscopedPageWritesAllowed=false`、`allowedFiles=4`、`forbiddenFiles=6`、`targetComponents=2`、`routeSmokeItems=4`、`assetGroups=2`、`failures=0`。
- `allowedFiles` 只作为历史范围记录，不允许继续修改 `pages/news/news.wxss`、`components/channel-dock/channel-dock.wxss`、`components/ranked-feed/ranked-feed.wxss` 或 `app.wxss`；必须等 `Foundation Reset Gate` 通过后重新生成 fresh permit。
- permit 明确当前 runtime evidence 仍是 `runtime_reviewed_failed`，`visual-scorecard-pass36l` 仍低于 90；它不代表 runtime verified，也不代表可以继续 source integration。
- `create-pass36-final-readiness-report.js` 已接入 `latestPass37NewsSurfaceImplementationPermit`；总 readiness 仍为 `incomplete`，objective requirements 会显示 `pass37_news_surface_implementation_permit=implementation_permit_suspended`。
- `tests/ui-v2-1-strict-cut-contract.test.js` 已覆盖 permit 的 suspended 状态、owner、allowed/forbidden 历史文件、redline metrics、asset groups、route smoke、当前失败 runtime 证据、readiness 集成和无 DevTools 控制。

2026-07-06 pass37 foundation reset package 已落地：

- 新增 `artifacts/ui-v2-1-strict-restoration/create-pass37-foundation-reset-package.js`，把 `Foundation Reset Gate` 从文档要求变成机器可读 artifact，不触碰 DevTools，不生成 runtime screenshot。
- 产物位于 `artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-foundation-reset-package.json` 和 `.md`。
- package 当前状态为 `foundation_reset_ready_for_fresh_permit`，这是 source-only 地基复位通过后的状态：`blockedGates=0`、`partialGates=0`、`sourceComponents=9`、`componentSourceGaps=0`、`expectedFixtures=324`、`missingFixtureCount=0`、`routeSmokeItems=29`、`pageWritesAllowed=false`、`scopedSourceEditsAllowed=false`、`failures=0`。
- `PageFrame`、`WowPanel`、`GameObjectIcon` 已从全局 class / helper ownership 补成真实基础组件源码；`pass37-devtools-action-ledger` 已建立并锁定后续 DevTools 动作字段；`workbench_verdict` manifest 已禁止 single-piece business status badge；`pass37-foundation-fixture-matrix` 已覆盖 9 个基础组件 x 12 个状态 x 3 个视口共 324 个 fixture；`pass37-measurement-pipeline` 已锁定 12 个测量项和 5 个核心 surface 的 target/current/implementation 证据契约；`pass37-route-smoke-harness` 已把 29 条 route smoke 计划转成 source-only 可执行清单；`pass37-cross-surface-shell-audit` 已把重复 chrome、贴边、状态漂移、CTA 压缩、卡片堆叠和证据溢出 6 类系统风险绑定到真实组件与产物证据；`pass37-repermit-decision-record` 已把 `news_home_and_feed` 的 fresh permit 决策锁定。
- `create-pass36-final-readiness-report.js` 已接入 `latestPass37FoundationResetPackage`；总 readiness 仍为 `incomplete`，但下一步已从“继续补 reset blocker”改为“使用 locked fresh `news_home_and_feed` permit 做 scoped source integration，然后补 source scan / browser layout audit / runtime capture”。
- `tests/ui-v2-1-strict-cut-contract.test.js` 已覆盖 foundation reset package 的 gate 状态、组件缺口、fixture 缺口、DevTools action ledger 缺口、readiness 集成、无 DevTools 控制和禁止 source edit 边界。

2026-07-06 architecture-reset-gate-v2 约束已追加：

- 当前执行口径从 `foundation-reset-lock` 再收紧为 `architecture-reset-gate-v2`，明确本轮核心问题是 UI 生产链路失控，不是单页 CSS 没调准。
- 新增 `Root Cause Override`：边距、状态图标、字号、素材贴片、重复 chrome、高分误判、登录态失效都必须归到具体系统层，不能继续用局部样式解释。
- 新增 `Real Component Gate`：`PageFrame`、`WowPanel`、`GameObjectIcon` 等不能只靠 class、helper 或文档冒充组件 owner；缺真实 runtime owner 时必须继续保留 blocker。
- 新增 `State Visual Contract v2`：状态视觉允许 `layered` 或 `atomic` 两种生产模式。完整“盾牌 + 叹号”图标可以作为状态族资产进入组件，但必须由同一组件固定尺寸、`contain`、居中和换状态，页面不得拆开摆。
- 新增 `Design Candidate Gate`：核心 surface 实现前至少 2 个，优先 3 个真实差异候选；用户确认后只保留一个 `target_locked`，其余 reference/quarantine。
- 新增 `Asset Slicing Gate v2`、`Measurement Gate v2`、`Route Coverage Gate v2` 和 `DevTools Preservation Gate v2`，把 imagegen 切片、90% 测量、全路由 smoke 和登录态保护升级为 permit 前置条件。
- 新增 `Restart Condition`：同一问题两轮未改善、组件 60 分钟无量化进展、目标与实现差距明显仍给高分、或页面 CSS 补丁继续制造新错位时，必须重开 surface 方案。

2026-07-06 pass37 DevTools action ledger 已落地：

- 新增 `artifacts/ui-v2-1-strict-restoration/create-pass37-devtools-action-ledger.js`，生成 `pass37-devtools-action-ledger.json` 和 `.md`，不触碰 DevTools，不生成 runtime screenshot。
- ledger 状态为 `action_ledger_present`，`entryFields=7`、`entries=0`、`devtoolsTouched=false`、`runtimeScreenshot=false`、`captureSafeRequiredForRuntime=true`、`failures=0`。
- 后续任何 DevTools 命令、connector probe、截图尝试、点击、端口探测、项目打开、登录检查、缓存或 appid 操作，都必须按字段写入 ledger；本轮源码阶段明确记录为没有 DevTools action。

2026-07-06 pass37 foundation fixture matrix 已落地：

- 新增 `artifacts/ui-v2-1-strict-restoration/create-pass37-foundation-fixture-matrix.js`，生成 `pass37-foundation-fixture-matrix.json` 和 `.md`，不触碰 DevTools，不生成 runtime screenshot。
- matrix 状态为 `foundation_fixture_matrix_locked`，覆盖 9 个基础组件、12 个状态、3 个视口，共 324 个 fixture，`devtoolsTouched=false`、`runtimeScreenshot=false`、`strictGateEligible=false`、`failures=0`。
- 该产物只证明 fixture enumeration 和组件级断言完整，仍不是 `runtime_verified`；真实小程序截图、overlay、scorecard 和 route smoke 仍是后续验收要求。

2026-07-06 pass37 measurement pipeline 已落地：

- 新增 `artifacts/ui-v2-1-strict-restoration/create-pass37-measurement-pipeline.js`，生成 `pass37-measurement-pipeline.json` 和 `.md`，不触碰 DevTools，不生成 runtime screenshot。
- pipeline 状态为 `measurement_pipeline_complete`，覆盖 `current screenshot`、`target screenshot`、`implementation screenshot`、`component crop`、`target crop`、`overlay`、`red-zone owner table`、`gutter and panel bounds`、`status center point`、`font and overflow scan`、`image fit scan`、`route smoke result` 共 12 项。
- pipeline 覆盖 `news_home_and_feed`、`builds_tab`、`current_spec_workbench`、`simulator_and_captain`、`profile_templates` 5 个核心 surface；它只把测量契约升到 `component_precheck`，不允许无 runtime 打最终分。
- 当时 reset package 的 `measurement_pipeline` gate 可进入 `component_precheck`；后续 route smoke、cross-surface shell audit 与 re-permit decision 已在 2026-07-07 检查点补齐，当前 source-only reset blocker 已清零。

2026-07-07 pass37 route smoke harness 已落地：

- 新增 `artifacts/ui-v2-1-strict-restoration/create-pass37-route-smoke-harness.js`，生成 `pass37-route-smoke-harness.json` 和 `.md`，不触碰 DevTools，不生成 runtime screenshot，不执行点击。
- harness 状态为 `route_smoke_harness_executable`，覆盖 `news_home_and_feed`、`builds_tab`、`current_spec_workbench`、`simulator_and_captain`、`profile_templates` 5 个 surface。
- 29 条 route smoke 计划全部转成 scenario，`executableScenarios=29`、`failedScenarios=0`、`missingRouteVariants=0`，每条都有 return-state assertion 和 failure-state assertion。
- 该产物只证明 source-only 静态可达与可执行清单完整，仍不是 `runtime_verified`；真实点击、返回、截图和 route result 必须等 `captureSafe=true` 后写入 DevTools action ledger 再执行。
- reset package 的 `route_smoke_harness` gate 现在可进入 `component_precheck`；后续 `repermit_decision_record` 已在 2026-07-07 fresh permit 检查点补齐。

2026-07-07 pass37 cross-surface shell audit 已落地：

- 新增 `artifacts/ui-v2-1-strict-restoration/create-pass37-cross-surface-shell-audit.js`，生成 `pass37-cross-surface-shell-audit.json` 和 `.md`，不触碰 DevTools，不生成 runtime screenshot。
- audit 状态为 `cross_surface_shell_audit_source_ready`，覆盖 6 类跨页面 UI 系统风险：`duplicate_chrome`、`edge_collision`、`status_drift`、`compressed_cta`、`card_pileup`、`evidence_overflow`。
- 6 类风险全部绑定真实 owner：`AppNav`、`PageFrame/WowPanel`、`StatusBadge`、`ActionButton`、`ModuleCard`、`EvidenceLedger`；页面不得重新用局部 WXML/WXSS 拆 status base/glyph、伪造系统 chrome、压缩按钮、自由堆卡片或自定义证据行。
- audit 同时检查 `foundation_fixture_matrix`、`measurement_pipeline`、`route_smoke_harness`、`page_integration_map` 四类产物证据，`artifactEvidenceReady=4/4`、`guardedRisks=6/6`、`fakeChromeHits=0`、`runtimeVerified=false`、`finalScoreAllowedWithoutRuntime=false`。
- reset package 的 `cross_surface_shell_audit` gate 现在可进入 `source_contract_present`；后续 `repermit_decision_record` 已补齐，`partialGates=0`、`blockedGates=0`。

2026-07-07 pass37 fresh news permit 与 re-permit decision 已落地：

- 新增 `artifacts/ui-v2-1-strict-restoration/create-pass37-news-surface-fresh-implementation-permit.js`，生成 `pass37-news-surface-fresh-implementation-permit.json` 和 `.md`，不触碰 DevTools，不生成 runtime screenshot。
- fresh permit 状态为 `fresh_implementation_permit_locked`，只覆盖 `news_home_and_feed` / `pages/news/news`，`primaryOwner=PageFrame`，`scopedSourceEditsAllowed=true`、`unscopedPageWritesAllowed=false`。
- fresh permit 允许 7 个文件：`pages/news/news.wxml`、`pages/news/news.wxss`、`components/channel-dock/channel-dock.wxml`、`components/channel-dock/channel-dock.wxss`、`components/ranked-feed/ranked-feed.wxml`、`components/ranked-feed/ranked-feed.wxss`、`app.wxss`。
- fresh permit 禁止 7 个 no-touch 文件，包括 `pages/news/news.js`、`pages/news/news-api.js`、`components/channel-dock/channel-dock.js`、`components/ranked-feed/ranked-feed.js`、`server/news_backend.py`、reference-only target image 和历史 HTML demo。
- 新增 `artifacts/ui-v2-1-strict-restoration/create-pass37-repermit-decision-record.js`，生成 `pass37-repermit-decision-record.json` 和 `.md`。
- re-permit decision 状态为 `repermit_decision_record_locked`，确认 7/7 个非 re-permit foundation gates 已就绪，旧 `implementation_permit_suspended` 不可复用，fresh permit 可开始 scoped source integration。
- reset package 已更新为 `foundation_reset_ready_for_fresh_permit`；architecture reset gate v2 仍保持 `pageWritesAllowed=false`、`scopedSourceEditsAllowed=false`，但 `freshPermitAllowed=true`，表示只能通过 fresh permit 的 allowed file list 开始下一步。

2026-07-06 pass37 recovery tickets 已落地：

- 新增 `artifacts/ui-v2-1-strict-restoration/create-pass37-recovery-tickets.js`，把 recovery-lock 从文档约束变成机器可读 artifact，不触碰 DevTools，不生成 runtime screenshot。
- 产物位于 `artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-recovery-tickets.json` 和 `.md`。
- 票据状态为 `recovery_tickets_locked`，覆盖 5 个页面域、9 个基础组件、6 类票据、30 张具体票据，`failures=0`。
- 5 个页面域分别是：首页/资讯首页与下滚列表、职业专精 tab、当前专精工作台、SimC/任务/炸鸡队长、个人模板页。
- 9 个基础组件被锁定为 `AppNav`、`PageFrame`、`WowPanel`、`MaterialImage`、`GameObjectIcon`、`StatusBadge`、`ActionButton`、`ModuleCard`、`EvidenceLedger`。
- 每个页面域都必须具备 `architecture / asset / component / data / route / verification` 票据后，才允许继续核心 WXML/WXSS 改动。
- `create-pass36-final-readiness-report.js` 已接入 `latestPass37RecoveryTickets`；总 readiness 仍为 `incomplete`，但 objective requirements 会显示 `pass37_recovery_tickets=recovery_tickets_locked`。
- `tests/ui-v2-1-strict-cut-contract.test.js` 已覆盖 recovery tickets 的冻结状态、票据数量、基础组件、工作台状态边界、imagegen 语义边界、runtime 证据边界和无 DevTools 控制。

2026-07-06 pass37 foundation contracts 已落地：

- 新增 `artifacts/ui-v2-1-strict-restoration/create-pass37-foundation-contracts.js`，把 9 个基础组件的职责、slot、几何约束、状态覆盖、source boundary 和 next harness 固化为机器可读 artifact。
- 产物位于 `artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-foundation-contracts.json` 和 `.md`。
- 契约状态为 `foundation_contract_locked`，覆盖 9 个基础组件、5 个页面域、32 条 `keep / replace / quarantine` 条目，`failures=0`。
- `keep` 条目保护真实数据、路由、接口和状态模型；`replace` 条目标出仍需从页面内迁出的拼形状 WXML/WXSS；`quarantine` 条目隔离整页 reference、HTML demo 和烘焙状态图。
- `StatusBadge` contract 已显式要求底座/glyph 分层、多 glyph 中心点和禁止 baked semantic status image。
- `create-pass36-final-readiness-report.js` 已接入 `latestPass37FoundationContracts`；总 readiness 仍为 `incomplete`，但 objective requirements 会显示 `pass37_foundation_contracts=foundation_contract_locked`。
- `tests/ui-v2-1-strict-cut-contract.test.js` 已覆盖基础组件列表、StatusBadge 分层边界、keep/replace/quarantine 数量、工作台隔离项、readiness 集成和无 DevTools 控制。

2026-07-06 pass37 foundation harness 已落地：

- 新增 `artifacts/ui-v2-1-strict-restoration/run-pass37-foundation-harness.js`，把 9 个基础组件契约渲染为 source-only browser fixture board，导出组件 crop、contact sheet 和几何检查，不触碰 DevTools。
- 产物位于 `artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-foundation-harness/`。
- harness 状态为 `foundation_harness`，`checks=14/14`、`crops=9`、`failures=0`、`devtoolsTouched=false`、`runtimeScreenshot=false`、`strictGateEligible=false`。
- crop 覆盖 `AppNav`、`PageFrame`、`WowPanel`、`MaterialImage`、`GameObjectIcon`、`StatusBadge`、`ActionButton`、`ModuleCard`、`EvidenceLedger`。
- `StatusBadge` 已通过底座/glyph 中心点检查；`ActionButton` 已通过按钮触控高度检查；可见文本检查明确禁止假系统状态栏、伪时间、电量、Wi-Fi 和 phone chrome。
- `create-pass36-final-readiness-report.js` 已接入 `latestPass37FoundationHarness`；总 readiness 仍为 `incomplete`，但 objective requirements 会显示 `pass37_foundation_harness=foundation_harness`。
- 该产物仍只是 source/component evidence，不是 `runtime_verified`。真实小程序截图、overlay、scorecard 和 route smoke 仍是后续 blocker。

2026-07-06 pass37 page integration map 已落地：

- 新增 `artifacts/ui-v2-1-strict-restoration/create-pass37-page-integration-map.js`，读取 recovery tickets、foundation contracts 和 foundation harness，生成页面接入矩阵，不触碰 DevTools，不生成 runtime screenshot。
- 产物位于 `artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-page-integration-map.json` 和 `.md`。
- map 状态为 `page_integration_mapped`，覆盖 5 个 surface、9 个基础组件、45 个 crop-backed component binding、45 个 ownership-backed binding、5 个 packet-complete surface，`failures=0`。
- 每个 surface 都已对齐 `architecture / asset / component / data / route / verification` 六类 packet；任一 packet 缺失或 component binding 只停留在 class 绑定，都不能通过 page integration map。
- 每个 surface 都声明了 data/route/object source interface、keep targets、replace targets、quarantine targets、接入前证据和接入后证据。
- `news_home_and_feed`、`builds_tab`、`current_spec_workbench`、`simulator_and_captain`、`profile_templates` 都已逐项绑定 `AppNav`、`PageFrame`、`WowPanel`、`MaterialImage`、`GameObjectIcon`、`StatusBadge`、`ActionButton`、`ModuleCard`、`EvidenceLedger`。
- `create-pass36-final-readiness-report.js` 已接入 `latestPass37PageIntegrationMap`；总 readiness 仍为 `incomplete`，但 objective requirements 会显示 `pass37_page_integration_map=page_integration_mapped`。
- 该产物仍只是 source integration map，不是 `runtime_verified`。下一步必须选择单个 surface 做受控组件化接入，并在接入后补 browser precheck 和真实小程序 runtime evidence。

2026-07-06 pass37 架构输入包已落地：

- 新增 `artifacts/ui-v2-1-strict-restoration/create-pass37-architecture-input-package.js`，生成 `pass37 architecture-first` 输入包，不触碰 DevTools，不生成 runtime screenshot。
- 产物位于 `artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-architecture-input-package.json` 和 `.md`。
- 输入包状态为 `design_locked`，包含 9 个页面架构条目、9 个组件契约、9 类必需 artifact、14 个状态覆盖项。
- 输入包明确 runtime gate 仍为 `incomplete`，不能替代真实微信小程序截图、组件 crop、overlay、scorecard 或 route smoke。
- `create-pass36-final-readiness-report.js` 已接入 `latestPass37ArchitectureInputPackage`；总 readiness 仍为 `incomplete`，但 objective requirements 会显示 `pass37_architecture_input=design_locked`。
- `tests/ui-v2-1-strict-cut-contract.test.js` 已覆盖 pass37 状态词、页面架构、组件契约、必需 artifact、imagegen 禁入项和 DevTools 禁止动作。

2026-07-06 pass37 组件红线已落地：

- 新增 `artifacts/ui-v2-1-strict-restoration/create-pass37-component-redlines.js`，从 pass37 输入包生成组件红线、fixture 清单和 fixture board，不触碰 DevTools，不生成 runtime screenshot。
- 产物位于 `artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-component-redlines.json`、`.md` 和 `pass37-component-redlines-fixtures.html`。
- 红线状态为 `design_locked`，覆盖 9 个组件、9 个 fixture state、3 个视口、243 个 harness fixture，缺失目标区域为 0。
- 关键目标框已锁定：`ChannelDock=707x131rpx`、`RankedFeed=719x717rpx`、`ModuleDock=745x235rpx`、`EvidenceLedger=749x553rpx`，`StatusBadge` 已绑定 `workbench.verdict_slab` 上下文并保留 `glyphCenterDrift <= 4rpx` 检查。
- `create-pass36-final-readiness-report.js` 已接入 `latestPass37ComponentRedlines`；总 readiness 仍为 `incomplete`，但 objective requirements 会显示 `pass37_component_redlines=design_locked`。
- `tests/ui-v2-1-strict-cut-contract.test.js` 已覆盖组件红线尺寸、fixture 数量、source-only 边界、无 DevTools 执行动作和无 fake runtime 验收。

2026-07-06 pass37 browser harness component precheck 已落地：

- 新增 `artifacts/ui-v2-1-strict-restoration/run-pass37-component-precheck.js`，用 Playwright 渲染 pass37 组件 fixture board，导出组件 crop、contact sheet 和 rect/overflow/source-only 检查，不触碰 DevTools。
- 产物位于 `artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-component-precheck/`。
- precheck 状态为 `component_precheck`，`checks=13/13`、`crops=9`、`failures=0`、`devtoolsTouched=false`、`runtimeScreenshot=false`、`strictGateEligible=false`。
- precheck 已输出 strict measurements：每个 component check 带 `textMetrics`、`slotRects`、`assetFit`；`StatusBadge` 额外输出 `glyphCenter.driftPx=0`，对应用户指出的盾牌/glyph 分层问题。
- contact sheet 已生成：`pass37-component-crop-contact-sheet.png`；单组件 crop 包括 `AppNav`、`PageFrame`、`WowPanel`、`StatusBadge`、`ChannelDock`、`RankedFeed`、`ModuleDock`、`EvidenceLedger`、`WorkbenchHero`。
- `create-pass36-final-readiness-report.js` 已接入 `latestPass37ComponentPrecheck`；总 readiness 仍为 `incomplete`，但 objective requirements 会显示 `pass37_component_precheck=component_precheck`。
- `tests/ui-v2-1-strict-cut-contract.test.js` 已覆盖 precheck 计划、目标尺寸文本、9 张 crop、contact sheet、无 DevTools 控制和 strictGateEligible=false。

2026-07-06 pass37 资讯组件实现映射已落地：

- 新增 `artifacts/ui-v2-1-strict-restoration/create-pass37-implementation-map.js`，把 `ChannelDock` 和 `RankedFeed` 的目标红线、slot、真实生产文件、数据来源、禁止实现动作和下一步检查绑定起来。
- 产物位于 `artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-implementation-map.json` 和 `.md`。
- 映射状态为 `implementation_mapped`，覆盖 2 个资讯组件、13 个 slot、11 个生产文件，`failures=0`、`devtoolsTouched=false`、`runtimeScreenshot=false`、`strictGateEligible=false`。
- `ChannelDock` 已绑定 `news.channel_dock=707x131rpx`、6 个真实 tab、`NEWS_TAB_DEFS`、`buildNewsTabs(source)`、`articleMatchesTab(article, key)` 和 `openNewsTab(event)`。
- `RankedFeed` 已绑定 `news.ranked_feed=719x717rpx`、5 行固定 feed、`RANKED_FOCUS_COUNT=5`、`buildRankedHighlights(source)`、`normalizeRankedHighlight(item, index)` 和 `source_reference` 缺口行规则。
- 映射明确 imagegen 只能供应低语义框架、socket、trim 和 fallback thumbnail，不能证明频道内容、文章事实、阅读量、DPS、评分、tier 或 readiness。
- `create-pass36-final-readiness-report.js` 已接入 `latestPass37ImplementationMap`；总 readiness 仍为 `incomplete`，但 objective requirements 会显示 `pass37_implementation_map=implementation_mapped`。
- `tests/ui-v2-1-strict-cut-contract.test.js` 已覆盖实现映射、目标尺寸、生产文件、数据来源、slot 选择器、source-only 边界、无 DevTools 控制和 readiness 集成。

2026-07-06 pass37 资讯组件 browser layout audit 已落地：

- 新增 `artifacts/ui-v2-1-strict-restoration/run-pass37-news-implementation-layout-audit.js`，用真实资讯组件 WXSS 和 implementation map 渲染 `ChannelDock` / `RankedFeed`，做 DOM rect、overflow、fake chrome、强结论文案和 crop 检查。
- 产物位于 `artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-news-implementation-layout-audit/`。
- 审计状态为 `browser_layout_audit`，`checks=11/11`、`crops=4`、`failures=0`、`devtoolsTouched=false`、`runtimeScreenshot=false`、`strictGateEligible=false`。
- `ChannelDock` crop 已收窄到约 `366-368px`，对应 pass37 `news.channel_dock=707x131rpx` 的红线方向，不再沿用旧 `calc(100% - 14rpx)` 的贴边宽度。
- actual browser harness 已补齐 `ranked-feed-root`，让预检对象和生产组件根结构一致。
- `pages/news/news.wxss` 已把 `.news-channel-section` 从 `calc(100% - 14rpx)` 调整为 `calc(100% - 42rpx)` 并居中，优先修复用户指出的频道区贴边问题。
- `news_home_and_feed` 已开始按 `pass37-page-integration-map` 做受控接入：`pages/news/news.wxml` 增加 `pass37-page-frame`、`pass37-page-frame__content`、`pass37-wow-panel--channel`、`pass37-wow-panel--ranked-feed`；`ChannelDock` 和 `RankedFeed` 组件增加 `pass37-module-dock` 与 `pass37-module-card` slot。
- `app.wxss` 新增 pass37 foundation slot 基础样式，只声明 `box-sizing`、`min-width`、`overflow` 等结构边界，不改真实数据、不改路由、不引入新素材。
- `run-pass37-news-implementation-layout-audit.js` 已接入 `pass37-page-integration-map`，新增 `page_integration_map_is_ready` 和 `news_surface_foundation_slots_present` 两个 browser precheck。
- `run-pass37-news-implementation-layout-audit.js` 已追加 `page_integration_strict_system_gate_is_ready`，要求 `packetCompleteSurfaces=5`、`ownershipBackedBindings=45` 和 `sourceRecoveryTicketTypes=architecture/asset/component/data/route/verification` 后，资讯 browser audit 才能通过。
- `create-pass36-final-readiness-report.js` 已接入 `latestPass37NewsImplementationLayoutAudit`；总 readiness 仍为 `incomplete`，但 objective requirements 会显示 `pass37_news_implementation_layout_audit=browser_layout_audit`。
- `tests/ui-v2-1-strict-cut-contract.test.js`、`tests/news-page-style.test.js` 和 `tests/ui-v2-1-browser-harness.test.js` 已覆盖该 audit、收窄后的 dock 宽度、`ranked-feed-root`、source-only 边界和无 DevTools 控制。

2026-07-07 pass37 资讯组件 source integration 二次收紧已落地：

- `components/channel-dock/channel-dock.wxss` 已降低 dock、轨道、选中态和类别色的发光强度，保留 6 个真实 tab 与原有数据/路由绑定，不再让频道区呈现通用发光按钮感。
- `components/ranked-feed/ranked-feed.wxss` 已把今日重点行从旧 `46rpx 104rpx minmax(0, 1fr) 32rpx / 108rpx` 调整为 `52rpx 116rpx minmax(0, 1fr) 32rpx / 116rpx`，扩大缩略图、rank、title 和 meta 的可扫读空间，同时保留 5 行固定 feed、真实文章优先和 source_reference 禁推荐规则。
- `pass36-static-scope-audit.js`、`create-pass37-implementation-map.js`、`run-pass37-news-implementation-layout-audit.js`、`tests/news-page-style.test.js`、`tests/ui-style-guide-implementation.test.js` 和 `tests/ui-v2-1-strict-cut-contract.test.js` 已同步更新，避免测试继续锁住旧压缩比例。
- `create-pass36m-source-preview.py` 和 `create-pass36n-source-preview.py` 已修复为读取 `pages/news/news.wxss` + `components/channel-dock/channel-dock.wxss` + `components/ranked-feed/ranked-feed.wxss`；source preview manifest 不再因为组件化而漏掉真实 CSS 选择器。
- 新增 `artifacts/ui-v2-1-strict-restoration/create-pass37-news-target-delta-audit.py`，生成 `pass37-news-target-delta-audit.json`、`.md`、目标/当前/heatmap 对比 board 和组件 heatmap；该产物只记录 source/browser 目标差异，不触碰 DevTools，不生成 runtime screenshot，也不作为最终 score。
- 最新 `pass37-news-implementation-layout-audit` 仍为 `browser_layout_audit`，`checks=11/11`、`failures=0`、`devtoolsTouched=false`、`runtimeScreenshot=false`、`strictGateEligible=false`。
- 验证：`node --test tests/news-page-style.test.js tests/ui-style-guide-implementation.test.js tests/ui-v2-1-browser-harness.test.js tests/ui-v2-1-strict-cut-contract.test.js` 70/70 通过；`node --test tests/builds-page.test.js tests/simulator-page.test.js tests/project-config.test.js tests/frontend-api-client.test.js` 215/215 通过；`git diff --check` 通过。

2026-07-05 首个样例已按新约束落地到代码层：

- 新增 `components/status-badge/`，把状态徽章拆成固定容器、无语义盾牌底座、状态 glyph、可选文案。
- 工作台不再使用 `verdict_status_badge_blocked_component` 这类“盾牌 + 叹号”合成状态图。
- `pages/builds/workbench-state.js` 只输出 `statusBadgeBaseUrl`、状态、glyph 和文案，不再输出状态合成图路径。
- 浏览器 harness 与 27 场景浏览器矩阵均改为同一个 `StatusBadge` DOM 结构。
- 测试已反向禁止 `statusEmblemUrl`、`verdict-status-badge-art`、`verdict-sigil` 等旧路径回归。

2026-07-05 资讯页重复组件已推进到 source/browser evidence 阶段：

- `ChannelDock` 和 `RankedFeed` 已从页面内联结构抽成组件，并在 `pages/news/news.json` 注册。
- `pages/news/news.wxss` 已清理掉 `.news-tab-*`、`.focus-*`、`ranked-feed` 内部样式，页面层只保留外壳和 section wrapper。
- pass36 静态审计已把 `components/channel-dock/*` 与 `components/ranked-feed/*` 纳入资讯页 scoped source，材质层预算从页面单文件 11 层拆成 page 5 + dock 3 + ranked 3。
- `tests/news-page-style.test.js`、`tests/ui-style-guide-implementation.test.js`、`tests/ui-v2-1-browser-harness.test.js`、`tests/ui-v2-1-strict-cut-contract.test.js` 已覆盖组件注册、组件 WXML/WXSS、素材边界和 source-only 验收边界。
- 浏览器 harness 与 27 场景浏览器矩阵已基于最新组件 CSS 重新生成；它们仍然只是 browser evidence，不替代真实微信小程序截图。
- 这些组件仍必须补齐真实小程序 crop、overlay、scorecard 和路由 smoke 后才可放行。

2026-07-05 DevTools 与素材预算 checkpoint：

- `devtools-health-check.js` 已补充 automator 失败分类，当前报告会输出 `healthCategory`、`automator.diagnosis` 和安全动作记录。
- 最新低扰动报告位于 `artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/devtools-health-pass36w/devtools-health-1783266046450.json`。
- 本次报告显示：只有一个可见微信开发者工具窗口，无多实例风险，未运行 CLI 登录探测，未调用 open/close/quit/login/cache reset/project switch/cleanup；`captureSafe=false` 的分类为 `candidate_ports_not_miniprogram_automator`。
- `panel_workbench_verdict_base_no_status_v3.png` 已从 175KB 压到 54KB，恢复生产 imagegen material 的 100KB 预算闸门，降低 DevTools 模拟器卡死风险。
- `pass36ap-automation-recovery-package` 已更新为 `blocked_automator_endpoint_unavailable`，旧 `pass36aq-devtools-login-required` 只作为历史证据保留；当前 health 已证明可见窗口恢复，因此它不得继续覆盖最新 endpoint 诊断。
- `pass36-final-readiness-report` 已刷新，Latest Automation Recovery 明确显示 `healthCategory=candidate_ports_not_miniprogram_automator`；最终状态仍为 `incomplete`。

2026-07-06 素材拆分工作流 checkpoint：

- 新增 `artifacts/ui-v2-1-strict-restoration/audit-pass36-asset-slice-workflow.js`，把 imagegen 生产素材从主观口径推进为可执行审计。
- 审计覆盖 `strict-production-manifest.json`、`target-decomposition.json` 和当前生产 WXML/WXSS/JS 引用，检查 production assets、reference-only assets、高语义合成图、素材预算和目标拆解 material 覆盖。
- `pass36x-asset-slice-workflow-audit` 已写入 `artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/`，状态为 `pass`，`devtoolsTouched=false`，`runtimeScreenshot=false`。
- 当前统计：65 个生产素材、68 个生产引用、0 个 manifest 外引用、0 个 reference-only 生产引用、0 个 material coverage 缺失、8 个高语义草稿被隔离为 quarantined draft。
- `verdict_status_badge_blocked_component_*`、`verdict_status_emblem_blocked_v1`、`workbench_generated_status_icon_reference` 和整页 reference 图被明确隔离，不能进入生产页面。
- `create-pass36-final-readiness-report.js` 已纳入 `latestAssetSliceWorkflowAudit`，目标需求里的“真实素材/imagegen 素材拆分工作流”现在可标记为 `source_contract_passed`，但仍明确 runtime rendering proof 缺失。
- `tests/ui-v2-1-strict-cut-contract.test.js` 和 `tests/project-config.test.js` 已覆盖该审计脚本、readiness 集成、reference-only 禁用和高语义状态图隔离。

2026-07-06 DevTools 端口与窗口诊断 checkpoint：

- `devtools-health-check.js` 新增 `automator.portProfiles`，对候选端口做低扰动分类，不再只输出笼统的 `candidate_ports_not_miniprogram_automator`。
- 端口 profile 会标出 `devtools_cli_control_port`、`websocket_like_endpoint`、`listening_http_unclassified`、`wechat_listening_unknown`、`not_listening_now` 和真实 `miniprogram_automator_runtime_candidate` 等类别，并保留 automator 连接尝试错误。
- 最新低扰动报告位于 `artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/devtools-health-pass36y/devtools-health-1783267913658.json`。
- 该报告未执行 login/open/close/cache/reset/project switch；`safety.cliLifecycleCommandsUsed=[]`，`loginAffectingProbeUsed=false`。
- 当前事实变为：`captureSafe=false`，`healthCategory=no_visible_devtools_window`，System Events 看到 0 个可见微信开发者工具窗口。
- 端口剖面显示：`9854:not_listening_now`，`44524:websocket_like_endpoint` 但 `Tool.getInfo` 超时，`48016/16727:listening_http_unclassified` 且 socket hang up，多个 403/404 端口不是 runtime automator。
- `create-pass36-automation-recovery-package.js` 已修正旧 login-required 误归因：只有明确 `devtools_login_false` 才保持 `blocked_devtools_login_required`；当前 `no_visible_devtools_window` 会压下旧 `pass36aq-devtools-login-required`。
- 最新 `pass36ap-automation-recovery-package` 状态为 `blocked_no_visible_devtools_window`，`devtoolsLoginRequiredSuppressedByCurrentHealth=true`；`pass36-final-readiness-report` 已同步显示该状态和端口 profile。

本检查点仍不是视觉验收：

- 基础组件源码 owner、素材语义、fixture matrix、measurement pipeline、route smoke harness、cross-surface shell audit、fresh news permit 和 re-permit decision 均已补齐；下一步是按 fresh permit 做 scoped source integration，而不是继续使用旧 suspended permit。
- 浏览器预检通过只能证明源码和 DOM 分层更稳定，不能替代微信小程序真实渲染。
- 最新低扰动 DevTools health 仍为 `captureSafe=false`，尚未得到真实小程序截图、组件裁切、overlay、scorecard 或路由 smoke。
