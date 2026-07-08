# UI v2.1 Strict Cut Execution

## Scope

本轮只以三张已确认目标图为视觉基准：

- `artifacts/ui-v2-1-strict-restoration/normalized-targets/news-target-780.png`
- `artifacts/ui-v2-1-strict-restoration/normalized-targets/builds-target-780.png`
- `artifacts/ui-v2-1-strict-restoration/normalized-targets/workbench-target-780.png`

目标不是给旧页面补边框，而是按目标图重建页面骨架、槽位、素材层和真实数据层。

## Required Inputs

| Artifact | Role |
| --- | --- |
| `artifacts/ui-v2-1-strict-restoration/target-decomposition.json` | 逐屏目标坐标、rpx 映射、selector、数据边界 |
| `assets/generated/ui-v2-1-slices/20260703/strict-production-manifest.json` | 生产可用切片、reference-only 切片、事实边界 |
| `docs/design/2026-07-03-ui-v2-1-target-layout-contract.md` | 区块高度和首屏露出约束 |
| `docs/ui-style-guide.md` | 数据可信 UI、真实图标、移动端密度和文案规则 |

## Design Read

- 产品类型：WoW 玩家小程序工具，不是网页 demo。
- 视觉方向：游戏 Companion App + 高密度证据驾驶舱。
- 设计参数：`DESIGN_VARIANCE=7`、`MOTION_INTENSITY=2`、`VISUAL_DENSITY=9`。
- 主题：单一暗色主题，暗铁底、魔兽金强调、状态色只表达真实状态。
- 模式：Redesign-overhaul，保留 IA、接口、状态机、动作路径和证据边界。

## Hard Rules

1. 页面结构先服从目标图槽位，再填入真实数据。
2. 任何区块不得因为内容增长撑破目标高度；长文本必须省略、限行或进入二级区域。
3. 快速扫读信息不能被删除，只能移动到目标图允许的槽位。
4. imagegen 素材只用于低语义材质、面板、边缘、socket、按钮底板和氛围 fallback。
5. 真实 WoW 图标只来自 `gameAsset.iconUrl`、WebSim/Battle.net 读模型或已验证官方 icon-name 映射。
6. 未具备完整 SimC-ready 天赋和装备前，不显示 DPS、综合评分、S/A 级或提升优先级。
7. 旧的黑金卡片堆叠不是可接受中间态；每个页面必须呈现目标图里的 App shell、底板和槽位关系。

## Page Rebuild Contract

### News Home

| Target region | Production selector | Non-negotiable |
| --- | --- | --- |
| Intelligence panel | `.news-command` | 左侧 emblem、四个快速 counters、更新时间和状态同屏 |
| Hero visual | `.banner-card` | 固定大视觉高度，真实图优先，缺图才用低语义氛围 fallback |
| Channel dock | `.channel-grid` | 六个徽章底座，不做普通按钮网格 |
| Ranked feed | `.highlight-list` | rank、缩略视觉、tag、标题、meta、动作必须在下滚后仍清楚 |

### Builds Tab

| Target region | Production selector | Non-negotiable |
| --- | --- | --- |
| Spec console | `.builds-spec-console` | 真实专精图标 + 专精身份 + 四模块短状态 |
| Workbench panel | `.workbench-entry` | 最高优先级入口，保留快速事实和四模块状态，不隐藏关键扫读信息 |
| Workflow timeline | `.query-section` | 左侧轨道 + 四步流程 + 固定动作按钮，不回到普通卡片列表 |

### Current Spec Workbench

| Target region | Production selector | Non-negotiable |
| --- | --- | --- |
| Identity panel | `.workbench-cockpit` | 真实专精图标、职业专精名、短说明、紧凑选择控件 |
| Verdict slab | `.verdict-slab` | 只表达可否模拟、主阻断、影响和下一步，不输出强结论 |
| Module dock | `.module-band` | 天赋、装备、SimC、队长四卡固定高度，指标短而可扫读 |
| Evidence ledger | `.evidence-section` | 证据行承载 coverage、checkedAt、模板数、blockers，展开态不挤压上方 |

## State Coverage

必须覆盖：

- `news_top`
- `news_scrolled_ranked_feed`
- `news_missing_image_fallback`
- `news_long_text`
- `builds_top`
- `builds_long_text`
- `builds_missing_icon_fallback`
- `workbench_blocked`
- `workbench_partial`
- `workbench_stale`
- `workbench_ready`
- `workbench_evidence_expanded`
- `workbench_missing_icon_fallback`
- `workbench_long_text`

## Visual Gate

每个主屏独立评分：

| Category | Weight | Floor |
| --- | ---: | ---: |
| Layout restoration | 30 | 80% |
| Visual hierarchy | 25 | 80% |
| Component detail | 20 | 80% |
| Information fidelity | 15 | 80% |
| Responsive quality | 10 | 80% |

通过标准：

- 单屏总分 `>= 90`。
- 所有 category 达到 floor。
- 真实微信开发者工具截图覆盖 375x812、390x844、430x932 或等价缩放。
- 输出目标图、实现图、overlay、四列对比和逐项评分表。

## Veto

任一出现即失败：

- 返回按钮压装饰或文字。
- 标题模糊。
- 元素溢出或按钮挤压。
- 普通黑金卡片堆叠。
- 工作台快速扫读信息被删除。
- 资讯下滚重点列表层级不清或接近全黑。
- imagegen 冒充真实 WoW 资产或来源事实。
- 出现无证据 DPS、综合评分、S/A 级、提升优先级。
- 只用工程测试替代视觉验收。

## Implementation Order

1. 对照 `target-decomposition.json` 更新页面结构。
2. 对照 `strict-production-manifest.json` 清理 reference-only 生产引用。
3. 重建 `pages/news/news` 的 shell、hero、channel dock 和 ranked feed。
4. 重建 `pages/builds/builds` 的 spec console、workbench panel 和 workflow timeline。
5. 重建 `pages/builds/workbench` 的 identity、verdict、module dock 和 evidence ledger。
6. 跑前端回归、强结论扫描、`git diff --check`。
7. 用真实微信开发者工具生成截图和 scorecard。
8. 更新 roadmap 证据。
