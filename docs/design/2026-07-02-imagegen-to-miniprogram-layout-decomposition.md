# Imagegen 目标图到小程序真实布局拆解

## 目标

imagegen 图只作为视觉目标和构图参考, 不能直接作为真实 UI 壳。真实小程序实现必须把静态图拆成可响应、可复用、可验证的组件结构。

本轮拆解对象:

- `artifacts/ui-visual-targets/20260702-pretty-direction/builds-target.png`
- `artifacts/ui-visual-targets/20260702-pretty-direction/news-target.png`
- `artifacts/ui-visual-targets/20260702-pretty-direction/workbench-target.png`
- 落地页: `pages/builds/builds`, `pages/news/news`, `pages/builds/workbench`

## 拆解原则

- 保留 UI 框架, 不保留假事实。
- 图中的职业、专精、天赋、装备图标全部视为占位构图, 真实实现只能使用真实资产或文字 fallback。
- 图中的状态只保留语义位置, 不能伪造 readiness、评分、缺口数量或模拟结果。
- 背景材质只转译为 CSS 层级、边框、暗铁面板和 icon socket, 不使用整页 imagegen 背景。
- 所有文字必须能在小程序宽度内截断或换行, 不允许压到安全区、标题或按钮。
- imagegen 给出的“配图/图标位”只能转译成真实资产槽。接口没有真实图片时展示短文字 fallback, 不用生成图或假图补位。
- 模块状态不使用装饰点。状态必须绑定到卡片边、badge 或状态文案, 且颜色沿用 `docs/ui-style-guide.md`。

## 信息窗口内部布局规则

imagegen 能给出外层构图, 但小程序实现必须继续把每个信息窗口拆成可扫读的信息层:

- 顶部摘要窗不只展示大标题, 还要展示真实 payload 统计: 职业数、专精数、流程入口数。
- 工作台入口必须拆成 `判断对象 / 证据范围 / 输出边界`, 避免用户误以为首页已经完成 readiness 计算。
- 四模块状态带必须区分对象、状态和证据类型: 例如天赋读取 WebSim / 模板, 装备读取 16 槽 / 模板, SimC 依赖固定模板, 队长只解释证据。
- 流程列表每行必须包含 `阶段 / 范围 / 证据 / 影响`, 让新手知道下一步去哪, 也让资深玩家快速判断这个入口会影响哪个决策。
- 同一信息窗内不要只用一种 badge 表达所有信息: 阶段用金色, 证据/来源用蓝色, 普通范围用中性灰, 阻断或等待状态按数据可信 UI 语义上色。
- builds tab 仍不直接输出 DPS、综合评分、S/A 级、提升优先级或可模拟结论。真实 readiness 只进入 `pages/builds/workbench` 后计算。

## 职业专精 Tab 元素映射

| 目标图元素 | 小程序结构 | 实现文件 | 适配规则 |
| --- | --- | --- | --- |
| 顶部安全区与标题 | `navigation-bar` | `pages/builds/builds.wxml` | 继续使用原生导航容器, 不把返回或菜单画进页面内容。 |
| 页面摘要 | `.builds-hero`, `.builds-hero-chip-row` | `pages/builds/builds.wxml`, `pages/builds/builds.wxss` | 两列 grid: 左文案和真实 payload chips, 右真实专精计数。高度压缩, 不做大 banner。 |
| 专精头像圆框 | `.spec-icon-socket` | `pages/builds/builds.wxml`, `pages/builds/builds.wxss` | 当前只放文字 fallback, 后续可替换为真实专精图标。 |
| 当前职业/专精 | `.entry-kicker` | `pages/builds/builds.js` | 来自 `classOptions` 默认专精, 不写死为图片事实。 |
| readiness badge | `.entry-status` | `pages/builds/builds.js` | builds tab 只显示 `等待证据`, 真实 readiness 进入工作台后计算。 |
| 工作台说明 | `.entry-desc`, `.entry-blocker` | `pages/builds/builds.js` | 只说明进入后校验证据, 不输出可模拟、缺几件或提升结论。 |
| 工作台事实窗 | `.entry-fact-grid` | `pages/builds/builds.js`, `pages/builds/builds.wxml`, `pages/builds/builds.wxss` | 固定展示判断对象、证据范围、输出边界, 防止漂亮入口遮住产品任务。 |
| 主行动按钮 | `.entry-action` | `pages/builds/builds.wxml` | 保持短文案 `进入`, 点击路由不变。 |
| 四模块状态带 | `.workbench-module-grid`, `.module-meta` | `pages/builds/builds.js`, `pages/builds/builds.wxml` | 固定 4 列, 每列有 icon socket、标题、状态和证据/输入 meta。状态是首页保守状态。 |
| 构筑流程 | `.query-section`, `.query-card`, `.query-meta-row` | `pages/builds/builds.wxml`, `pages/builds/builds.wxss` | 旧四入口保留, 每行展示阶段、范围、证据、影响和短动作。 |
| 图中金属边框 | CSS border / inset shadow | `pages/builds/builds.wxss` | 用结构化 CSS 表达, 不用整张背景图。 |

## 当前实现边界

已实现:

- 移除 `builds-shell-bg`、`builds-hero-material`、`workbench-entry-material`。
- 新增 `buildHomeOverview()` 和结构化 `workbenchEntry.modules`。
- 工作台入口具备专精 socket、状态 badge、判断对象、证据范围、输出边界、主行动和四模块状态带。
- 构筑流程改为高密度证据列表, 每行包含阶段、范围、证据来源、影响和动作。
- 测试锁定无 generated 背景、旧入口保留、四模块状态 grid、内部事实窗、流程证据 meta 和紧凑卡片高度。
- 资讯首页新增真实图片槽与文字 fallback: hero、频道、重点列表均可承接真实图片字段, 当前 payload 无图时不伪造配图。
- 当前专精工作台移除旧 `ui-redesign` 整图素材, 改为 CSS 金属面板、状态 slab、2x2 模块卡片和证据账本。
- SimC 模块 fallback 改为 `Sim`, 避免单字 `S` 被误读为评级。
- 已通过当前已打开的微信开发者工具复用真实 AppID 项目完成 14 个官方小程序场景截图, manifest 为 `artifacts/miniprogram-screenshots/20260702-ui-implementation-v1/manifest.json`。
- 已生成主对比图 `artifacts/miniprogram-screenshots/20260702-ui-implementation-v1/comparison-main-current-target-implemented.png` 和全场景 before/after 对比图 `artifacts/miniprogram-screenshots/20260702-ui-implementation-v1/comparison-all-scenes-current-implemented.png`。

未实现:

- 未接入真实职业/专精图标。当前只使用文字 fallback。
- 未在 builds tab 直接请求天赋/装备 readiness。真实判断仍在 `pages/builds/workbench`。

## 资讯首页元素映射

| 目标图元素 | 小程序结构 | 实现文件 | 适配规则 |
| --- | --- | --- | --- |
| 顶部情报控制台 | `.news-command`, `.news-command-emblem` | `pages/news/news.*` | 保留今日重点、来源数、频道数、更新时间；徽章是情报 fallback, 不代表真实图标。 |
| 主视觉新闻 | `.banner-card`, `.banner-visual-shell` | `pages/news/news.*` | 有 `imageUrl/cover/thumbnail` 时显示真实图；无图时显示频道/标签文字 fallback。 |
| 频道入口 | `.channel-grid`, `.channel-icon-socket` | `pages/news/news.*` | 一行紧凑展示, update dot 仅表示真实更新计数。 |
| 今日重点列表 | `.highlight-card`, `.highlight-visual` | `pages/news/news.*` | 保留 rank、来源、日期、摘要和动作；缩略槽不使用假图片。 |

## 当前专精工作台元素映射

| 目标图元素 | 小程序结构 | 实现文件 | 适配规则 |
| --- | --- | --- | --- |
| 顶部专精对象卡 | `.workbench-cockpit`, `.spec-medallion` | `pages/builds/workbench.*` | 导航仍由原生 navigation-bar 处理；专精图标缺失时只显示文字 fallback。 |
| readiness 结论 slab | `.verdict-slab`, `.verdict-marker` | `pages/builds/workbench.*` | 显示能否模拟和主阻断；不显示 DPS、评分、提升优先级。 |
| 四模块状态带 | `.module-card-grid`, `.module-card` | `pages/builds/workbench.*` | 2x2 卡片保留图标槽、状态、指标、说明和动作；状态色绑定顶部语义边。 |
| 证据账本 | `.evidence-section`, `.evidence-row` | `pages/builds/workbench.*` | 默认展示前几行, 展开后给 coverage、checkedAt、catalogStatus、statSnapshot、模板计数和 blockers。 |

## 后续工作台拆解规则

`workbench-target.png` 后续应按同样方式拆分:

- 安全区导航。
- 当前专精对象卡。
- readiness 结论 slab。
- 下一步 CTA。
- 四模块状态带。
- 证据列表。

不得照搬:

- 生成图里的假冰霜图标。
- 假装备缺口数量。
- 假来源数量。
- 任何 DPS、评分、S/A 级或提升优先级。
