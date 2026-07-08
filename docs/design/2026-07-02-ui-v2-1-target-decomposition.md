# UI v2.1 Target Decomposition

## Purpose

本文件是 v2.1 开工门禁。它把三张已确认的 imagegen 目标图拆成真实小程序可实现的结构、组件、材质和数据边界。

本轮不接受“工程可运行”作为完成标准。每个主屏必须在目标图还原、真实数据边界和多尺寸适配上同时过关。

## Design Read

- 页面类型：C 端 WoW 小程序真实产品重设计。
- 用户：需要快速判断资讯重点、当前专精状态和下一步动作的普通玩家，同时保留资深玩家能展开追证据的密度。
- 视觉语言：暗黑幻想 App 控制台，暗铁、金色、厚面板、图标底座、强主视觉和证据账本。
- 设计参数：`DESIGN_VARIANCE 7`、`MOTION_INTENSITY 2`、`VISUAL_DENSITY 9`。
- 模式：Redesign-overhaul，但保留当前 IA、真实接口、状态机、证据边界和动作路径。

## Locked Inputs

| 类型 | 路径 |
| --- | --- |
| 资讯目标图 | `artifacts/ui-visual-targets/20260702-pretty-direction/news-target.png` |
| 职业 tab 目标图 | `artifacts/ui-visual-targets/20260702-pretty-direction/builds-target.png` |
| 工作台目标图 | `artifacts/ui-visual-targets/20260702-pretty-direction/workbench-target.png` |
| v2 当前资讯截图 | `artifacts/miniprogram-screenshots/20260702-ui-v2-restoration/screenshots/001_news_home_top.png` |
| v2 当前资讯下滚截图 | `artifacts/miniprogram-screenshots/20260702-ui-v2-restoration/screenshots/002_news_home_scrolled.png` |
| v2 当前职业 tab 截图 | `artifacts/miniprogram-screenshots/20260702-ui-v2-restoration/screenshots/003_builds_tab.png` |
| v2 当前工作台截图 | `artifacts/miniprogram-screenshots/20260702-ui-v2-restoration/screenshots/004_workbench_first_screen.png` |
| v2 当前工作台展开截图 | `artifacts/miniprogram-screenshots/20260702-ui-v2-restoration/screenshots/005_workbench_evidence_expanded.png` |
| v2.1 切片 manifest | `assets/generated/ui-v2-1-slices/20260702/manifest.json` |
| v2.1 baseline score | `artifacts/ui-v2-1-strict-restoration/baseline-score.json` |

## Normalization Contract

目标图包含手机外壳或整机效果，真实验收截图来自微信开发者工具小程序画面。v2.1 统一用脚本把目标图裁切到小程序内屏区域，再缩放到 `780px` 宽作为视觉基准。

脚本：`artifacts/ui-v2-1-strict-restoration/prepare-target-assets.py`

| 屏幕 | 目标图原始尺寸 | 目标裁切框 | 标准化目标 | 当前截图 | baseline overlay |
| --- | ---: | --- | --- | --- | --- |
| 资讯首页 | `853x1844` | `[58, 58, 797, 1788]` | `780x1826` | `780x1524` | `artifacts/ui-v2-1-strict-restoration/baseline-overlays/news-baseline-overlay.png` |
| 职业专精 tab | `899x1749` | `[30, 0, 869, 1749]` | `780x1626` | `780x1524` | `artifacts/ui-v2-1-strict-restoration/baseline-overlays/builds-baseline-overlay.png` |
| 当前专精工作台 | `853x1844` | `[29, 0, 824, 1844]` | `780x1809` | `780x1688` | `artifacts/ui-v2-1-strict-restoration/baseline-overlays/workbench-baseline-overlay.png` |

当前 v2 baseline proxy：

| 屏幕 | RMSE | Edge diff | 结论 |
| --- | ---: | ---: | --- |
| 资讯首页 | `52.28` | `67.22` | 未达目标图级别，主视觉和重点列表比例仍偏离 |
| 职业专精 tab | `49.42` | `67.89` | 未达目标图级别，三段式结构比例和面板家具不足 |
| 当前专精工作台 | `63.88` | `70.61` | 未达目标图级别，顶部对象卡、判定 slab、模块 dock 和证据区都偏离 |

这些数值只用于证明 v2 baseline 不合格，不是最终 90 分验收算法。

## Global Implementation Rules

1. 先按本文件实现结构比例，再接入视觉切片，再补状态变体。
2. 目标图中所有职业、专精、天赋、装备、来源、文章、DPS、评分、提升优先级和 readiness 相关内容都不可信，不得作为事实。
3. `productionUse=true` 切片只能作为低透明材质层、面板纹理、光影边缘或装饰底座。
4. `productionUse=false` 切片只做参考，不能进入 WXML 或 WXSS。
5. 真实 WoW 图标来自 `gameAsset.iconUrl`、WebSim/Battle.net 读模型或已验证官方 icon-name 映射。
6. 长文本必须用固定行数、渐隐或省略处理，不能撑破目标图比例。
7. 缺图 fallback 必须是文字或低语义材质，不能用生成图伪装真实对象。
8. 资讯下滚、工作台证据展开、blocked、partial、stale、ready 必须使用同一套组件尺寸和状态色。
9. 验收截图必须来自真实微信开发者工具项目，不用 Web preview 替代。

## Screen: News Home

### Target Structure

| 层 | 标准化坐标 | 目标作用 | 实现映射 |
| --- | --- | --- | --- |
| App shell | `[0, 0, 780, 1826]` | 整机暗铁外壳、边角微光、底部 tab 承托 | `news-shell` 背景层和 `surface-material` |
| Nav safe area | `[0, 0, 780, 170]` | 顶部留白、标题居中、右侧胶囊按钮空间 | 小程序导航区，不允许内容压入 |
| Intelligence panel | `[19, 180, 759, 341]` | 今日情报台、来源/任务/副本/活动摘要 | `news-command`，真实 counts 来自 payload |
| Hero visual | `[16, 359, 765, 767]` | 首屏主视觉冲击力，承载最重要资讯 | `banner-card`，真实图优先，无图才用材质 fallback |
| Channel dock | `[22, 794, 757, 930]` | 6 个图标频道，一眼看到信息分类 | `channel-grid`，目标是徽章底座而非普通按钮 |
| Ranked feed | `[16, 945, 763, 1691]` | 今日重点列表，图像化行和强排序 | `highlight-list`，下滚状态也必须保留图像/排序/来源层级 |
| Bottom tab | `[0, 1690, 780, 1826]` | 原生 App 感底部承托 | 保持真实 tabBar，不用图片伪造 tab |

### Current v2 Gaps

| 维度 | 当前问题 | v2.1 要求 |
| --- | --- | --- |
| 布局比例 | 情报台、主视觉、频道、列表之间间距仍像普通页面 | 首屏必须按目标图形成 `情报台 -> 主视觉 -> 频道 dock -> 重点列表` |
| 主视觉 | 有了大图，但目标图的边框厚度、暗角、标题压图层级不足 | 主视觉用固定高度和内阴影，标题区必须有暗底保护 |
| 频道 dock | 当前更像数据快捷项 | 必须变成图标徽章底座，不靠文字面积撑开 |
| 重点列表 | 当前已非全黑，但视觉记忆点弱 | 列表行必须有 rank、缩略视觉、tag、标题、meta、收藏/查看动作 |
| 适配 | 只看了 780 宽截图 | 必须验证 375、390、430 等价视口和长标题 |

### Slice Usage

| slice | production | 用途 |
| --- | --- | --- |
| `news_shell_corner_material` | yes | 页面 shell 角落暗铁底纹 |
| `news_command_frame_material` | yes | 情报台顶部边框和材质 |
| `news_hero_atmosphere_material` | yes | 无真实图时的主视觉氛围 fallback |
| `news_channel_frame_material` | yes | 频道 dock 上沿边框材质 |
| `news_ranked_feed_frame_material` | yes | 今日重点列表外框材质 |
| `news_full_layout_reference` | no | 只参考整屏比例，禁止生产使用 |

## Screen: Builds Tab

### Target Structure

| 层 | 标准化坐标 | 目标作用 | 实现映射 |
| --- | --- | --- | --- |
| App shell | `[0, 0, 780, 1626]` | 暗铁边框、顶部安全区、整屏厚度 | `builds-shell` 和材质层 |
| Nav safe area | `[0, 0, 780, 150]` | 标题和帮助按钮，不压内容 | 小程序导航与页面标题 |
| Spec console | `[0, 156, 780, 433]` | 职业/专精对象卡，真实图标和四模块短状态 | `builds-hero`，真实 `specIconUrl` |
| Workbench panel | `[1, 458, 779, 1001]` | 当前专精工作台最高优先入口，4 行状态列表 | `workbench-entry`，大面板加行分隔 |
| Workflow timeline | `[1, 1024, 779, 1543]` | 天赋、装备、SimC、任务的流程路径 | `query-section`，timeline 而不是普通卡片列表 |

### Current v2 Gaps

| 维度 | 当前问题 | v2.1 要求 |
| --- | --- | --- |
| 三段式比例 | 当前顶部和工作台已接近，但流程区仍卡片堆叠感强 | 严格还原 `对象卡 -> 工作台大面板 -> timeline` |
| 图标底座 | 真实图标有了，但底座厚度、金属环和阴影不足 | 真实图标必须套目标图式 socket，不使用目标图内生成图标 |
| 工作台入口 | 当前四模块状态有信息，但视觉上仍像列表 | 需要大面板内行状态、右侧语义状态和箭头层级 |
| 流程区 | 当前流程信息多，但缺少目标图的左侧轨道 | 加 timeline 轨道和统一操作按钮尺寸 |
| 适配 | 小屏长文案可能压按钮 | 行内文案固定 2 行，按钮固定宽度，meta 横向不换乱 |

### Slice Usage

| slice | production | 用途 |
| --- | --- | --- |
| `builds_shell_corner_material` | yes | 页面 shell 角落暗铁纹理 |
| `builds_spec_console_panel_material` | yes | 对象卡右侧低语义面板纹理 |
| `builds_workbench_frame_material` | yes | 工作台大面板上沿框体材质 |
| `builds_workflow_frame_material` | yes | 构筑流程大面板边框材质 |
| `builds_full_layout_reference` | no | 只参考整屏比例，禁止生产使用 |
| `builds_icon_socket_reference` | no | 只参考尺寸，禁止生产使用 |

## Screen: Workbench

### Target Structure

| 层 | 标准化坐标 | 目标作用 | 实现映射 |
| --- | --- | --- | --- |
| App shell | `[0, 0, 780, 1809]` | 页面边缘、顶部安全区、角落装饰 | `workbench-shell` 与材质层 |
| Nav safe area | `[0, 0, 780, 205]` | 返回、标题、右侧图标按钮 | 自定义导航，按钮不得压装饰 |
| Identity panel | `[0, 203, 780, 416]` | 当前专精对象和一句用途说明 | `workbench-cockpit`，真实 `specIconUrl` 和状态 badge |
| Verdict slab | `[2, 437, 550, 861]` 主体，右侧插画区 `[556, 488, 736, 689]` | readiness 结论、blocker、下一步动作 | `verdict-card`，插画区可换成真实状态 glyph 或低语义材质 |
| Module dock | `[2, 886, 777, 1130]` | 天赋、装备、SimC、队长四模块卡 | `module-card-grid`，四等分，固定高度 |
| Evidence ledger | `[0, 1156, 779, 1732]` | 证据来源、覆盖率、说明行 | `evidence-section`，展开态继承同一行模型 |

### Current v2 Gaps

| 维度 | 当前问题 | v2.1 要求 |
| --- | --- | --- |
| 顶部安全区 | 当前真实截图有大黑 nav，但目标图按钮和标题更精细 | 返回、标题、右侧动作必须有明确坐标和安全距离 |
| Identity panel | 当前对象卡信息过多且偏表单 | 改成目标图的大对象卡：真实图标、专精名、短说明、状态 badge |
| Verdict slab | 当前把输入、场景、阻断都塞进同一首屏区域 | verdict 只做结论、核心 blocker、下一步按钮，其他进入 evidence |
| Module dock | 当前四模块信息密集但卡片太小、信息挤 | 四卡固定高度，图标大、状态短、指标少而清晰 |
| Evidence ledger | 当前证据区过早露出且像普通表格 | 首屏只露出证据区开头，展开后才出现覆盖率、checkedAt、blockers |
| 事实边界 | 当前没有伪造强结论，这点必须保留 | 不得新增 DPS、评分、S/A、提升优先级 |

### Slice Usage

| slice | production | 用途 |
| --- | --- | --- |
| `workbench_shell_corner_material` | yes | 页面 shell 角落暗铁纹理 |
| `workbench_identity_panel_material` | yes | 对象卡右侧纹理 |
| `workbench_verdict_slab_material` | yes | readiness slab 暗红氛围 |
| `workbench_module_frame_material` | yes | 四模块 dock 上沿边框材质 |
| `workbench_evidence_frame_material` | yes | 证据账本面板上沿材质 |
| `workbench_full_layout_reference` | no | 只参考整屏比例，禁止生产使用 |
| `workbench_generated_status_icon_reference` | no | 只参考插画尺寸，禁止生产使用 |

## Required States

| 状态 | 必须覆盖的屏幕 | 验收点 |
| --- | --- | --- |
| 首屏正常 | news、builds、workbench | 目标图比例、材质、主视觉、模块层级 |
| 下滚 | news | 今日重点列表不全黑，rank、图、来源、动作可扫读 |
| 证据展开 | workbench | evidence ledger 行模型清晰，不挤压顶部结构 |
| blocked | workbench | 不像错误页，明确缺什么、影响什么、下一步去哪 |
| partial | workbench | 不输出强结论，显示部分可用和补齐动作 |
| stale | workbench | 提示过期证据和刷新/查看来源动作 |
| ready | workbench | 进入 SimC 校验，不提前显示 DPS 或综合评分 |
| 缺图 | news、builds、workbench | 使用文字 fallback 或低语义材质，不伪装真实图标 |
| 长文本 | news、builds、workbench | 不溢出，不压按钮，不改变区块比例 |

## 90 Point Gate

每个主屏单独评分。主屏包括资讯首页、职业专精 tab、当前专精工作台。关键状态用同一表附加评分。

| 大项 | 分值 | 80% 地板 | 90% 通过标准 |
| --- | ---: | --- | --- |
| 布局还原 | 30 | 24 | 主区块顺序、比例、首屏露出量贴近目标图 |
| 视觉层次 | 25 | 20 | shell、面板、光影、边框、材质形成目标图式厚度 |
| 组件细节 | 20 | 16 | 图标底座、按钮、badge、dock、列表行、证据行都有精细尺寸 |
| 信息保真 | 15 | 12 | 保留快速扫读信息，不伪造强结论，不删关键动作 |
| 适配质量 | 10 | 8 | 375、390、430 等价视口和长文本/缺图/状态切换不崩 |

通过必须同时满足：

- 单屏总分 `>= 90`。
- 每个大项都达到 80% 地板。
- 没有一票否决项。

## Veto Items

任一出现即失败：

- 返回按钮压装饰或文字。
- 标题模糊、文字溢出、按钮挤压。
- 页面仍像普通黑金卡片堆叠。
- 工作台删掉快速扫读信息。
- 资讯下滚重点列表层级不清或接近全黑。
- imagegen 素材冒充真实 WoW 职业、专精、天赋、装备、来源或事实图。
- 出现 `DPS`、`综合评分`、`S 级`、`A 级`、`提升优先级` 等无证据强结论。
- 截图不是来自真实微信开发者工具。
- 只用工程测试替代视觉验收。

## Implementation Order

1. 用 `prepare-target-assets.py` 生成标准化目标图、baseline overlay 和切片 manifest。
2. 先改 `pages/news/news`，验收首屏和下滚列表。
3. 再改 `pages/builds/builds`，验收三段式结构。
4. 最后改 `pages/builds/workbench`，验收首屏、证据展开和四种状态。
5. 生成 375、390、430 等价截图或可证明的缩放截图。
6. 生成目标图/实现图/overlay/四列对比/评分表。
7. 跑前端回归、静态扫描和 `git diff --check`。
8. 更新 roadmap 证据。
