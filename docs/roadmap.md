# WOW Mini Program Roadmap

Active frontend ownership is explicit: `apps/mini-taro` owns the active 14-route runtime and `packages/api-client/src` owns typed transport. The root `app.json` and `pages/` tree remain compatibility consumers only, preserving the 14-route surface without receiving new first-level ownership. The machine-readable route matrix is `docs/project-owner-map.json`.

状态：`active`
更新时间：`2026-07-28`

## 本文职责

本文件只回答三个问题：产品要解决什么、当前主线是什么、下一阶段按什么顺序推进。

执行步骤只进入 `docs/plans/README.md` 白名单；设计事实只进入 `DESIGN.md` 与 `docs/design/current-ui/`；接口、运行和部署细节留在稳定架构或 runbook。历史过程、否定式约定、截图账本和阶段证据由 Git 与 release packet 保存。

## 产品方向

面向 WoW 玩家构建一体化分析工作台，把资讯、职业构筑、装备、SimC、任务结果和证据受限的 AI 建议连接成一条可复用路径：

`理解版本 -> 选择构筑 -> 保存模板 -> 执行模拟 -> 解释结果 -> 继续优化`

产品以四个一级入口组织：资讯、职业专精、智能分析、我的。PVE、WCL 和 WebSim 历史能力保留，但在真实数据源、用户价值和发布门禁明确前不恢复为一级入口。

## 当前能力边界

| 能力 | 当前判断 | 下一步边界 |
| --- | --- | --- |
| 资讯 | 已有首页、列表、中文详情、来源与发布状态 | 保持来源、翻译和内容状态可追踪 |
| 职业构筑 | canonical resolver、release train、社区模板原子导入、异步属性快照和 Taro typed API 接合已完成 | 在真实微信候选中验证构筑主路径；不能引入第二套本地装备事实 |
| SimC 与任务 | 已有确定性转换、执行、任务保存和结构化报告基础 | 输入可执行、数字有证据、失败可解释 |
| 炸鸡队长 | 已有证据受限对话、数字白名单和确定性降级 | 统一为单一 ChatBot，以受控 Tool 查询个人模板、SimC 任务和允许的外部来源，重分析进入通用 Worker |
| 个人模板 | 已有微信账号、天赋/装备模板汇总与同步基础 | 数据保持 owner 隔离，再扩展收藏、角色和订阅 |
| 数据与发布 | PostgreSQL-only、read-model selector、Harness、验证矩阵、Taro/兼容 owner、CI 与 caller-proof 淘汰合同已建立 | 按 compatibility retirement 合同逐项证明无调用方后再淘汰兼容面 |
| PVE / WCL | 历史实现保留，当前不是首版主入口 | 授权数据、样本窗口、可信状态和恢复验收同时明确后再启用 |

## 当前优先级

| 优先级 | 里程碑 | 完成标准 | 权威入口 |
| --- | --- | --- | --- |
| 已完成 | 主干架构接合 | Taro 已接入 resolver、community import、stat snapshot；Harness 已把 Taro 定义为活动 UI owner，旧 `pages/` 只保留兼容职责 | [装备 runbook](gear-simulation-full-chain-runbook.md)、[owner map](project-owner-map.json)、[验证矩阵](verification-matrix.md) |
| P0 | 14 路由 UI 系统重建 | 共享 chrome、控件和素材槽先在微信三基线成立，再按固定批次传播；14 路由各完成一次真实运行态复核和核心交互验证；`builds_home` 收敛为职业选择器、四个平级工具入口和三条最近 SimC 任务预览；`gear_detail` 的换装固定为“候选 → 后端返回的合法等级/变体配置 → 显式应用 → canonical Resolve”，不得点击候选即写入；当且仅当后端确认目标槽位合法、全局唯一阻塞原因为其他必填槽位未补齐时，允许该槽位留在本地组装清单，但绝不把它当作完整可模拟配置；强化固定为“类别 → 兼容的已选装备 → 跨装备本地草稿 → 一次完整 canonical Resolve 确认”；装备槽位以小部位名、大装备名、真实副属性标签和右上角已确认强化状态建立信息层级，不得把制造属性、候选属性或前端推断冒充当前装备事实 | [DESIGN.md](../DESIGN.md)、[current-ui](design/current-ui/README.md)、[当前计划](plans/ui-reconstruction.md)、[builds_home 设计](design/current-ui/routes/builds-home/product-design.md) |
| 已完成 | 文档控制面收敛 | roadmap 无执行流水；plans 只有活动入口；Harness 状态、稳定合同和 release evidence 各有唯一 owner | 本文件、[plans/README.md](plans/README.md)、[project-state.json](project-state.json) |
| 已完成 | Harness v0.6.2 证据绑定 | PR #93 已让 CI 绑定任务自己的 requirement/evidence/manifest；runtime、verification 与 closure identity 分离，人工验收和 `not_run_user_waived` 进入可校验矩阵，且没有增加重复 full、额外评审或运行时改动 | [Harness](harness.md)、[验证矩阵](verification-matrix.md)、[归档证据](../artifacts/releases/2026-07-19-harness-v0-6-2-control-plane-cleanup/evidence.json) |
| 已完成 | Harness v0.6.3 当前事实与 DX 收口 | 当前事实顺序、Taro 开发入口、活动文档可达性、本地假失败和 CLI fail-fast 规则保持一致；不增加新流程或重复验证 | [Harness](harness.md)、[文档地图](README.md)、[release packet](../artifacts/releases/2026-07-20-harness-v0-6-3-docs-dx/evidence.json) |
| 已完成 | Harness v0.6.4 微信预览刷新 | 微信前端验收合入后，在最新 `main` 上统一重建、校验并刷新 DevTools；跨电脑 CLI 缺失时明确人工接管，不把本地交付动作冒充验收 | [Harness](harness.md)、[文档地图](README.md)、[release packet](../artifacts/releases/2026-07-20-harness-v0-6-4-wechat-preview-refresh/evidence.json) |
| P1 | 构筑到模拟闭环稳定 | 天赋/装备模板可确定性保存、加载、转换、校验、提交和复盘；装备目录按 CatalogRevision 发布，每件装备每条合法轨道只暴露最高 rank BrowseVariant，社区和个人模板保留 ExactItemInstance；真实玩家先沉淀为可重放 snapshot，再按当前 authority 编译天赋/装备 projection；每日 80 槽 TemplateSet 对成功槽更新、失败槽保留同槽 LKG 并标记过期，完整校验后原子切换；任意专精展示两个可导入装备模板，任意 Hero 展示一个同玩家可导入天赋模板；完整 SimC 只在玩家请求时运行；不可执行状态 fail closed。社区装备的有界 SimC 回填必须公平轮转候选资料池；缺少精确变体证据时不展示导入入口，不能用默认变体替代。2026-07-25 零售 80/80 导入审计、回滚位和首次游标轮转已记录。2026-07-28 Catalog 只读 Phase 0 口径校正完成且结果仍为 `blocked`：46,631 条旧变体被互斥分为 1,678 条 Browse、44,651 条 observed Exact、291 条占位和 11 条预览引用；全部 Browse 行缺少专用轨道 rank，48 条同时缺静态属性。Community Release、40 专精初始候选均未通过，资源与调用方仍为 `partial`；`allowedNextPlan=none`，必须先补齐这些当前数据事实，不能进入合同、schema 或 API 迁移。 | [装备模拟目标架构](plans/2026-07-28-equipment-simulator-target-architecture.md)、[Catalog 迁移 Phase 0](plans/2026-07-28-equipment-simulator-catalog-migration-phase0-implementation.md)、[Phase 0 审计](../artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0/runtime-readonly-audit.json)、[Phase 1 决策](../artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0/phase1-decision.json)、[Observed Build Registry 设计](plans/2026-07-23-observed-build-registry-design.md)、[共享玩家切换计划](plans/2026-07-23-observed-build-registry-cutover-implementation.md)、[社区装备回填修复计划](plans/2026-07-25-community-gear-backfill-fairness.md)、[零售 live smoke](../artifacts/releases/2026-07-25-community-gear-backfill-fairness/retail-live-smoke.json)、[社区模板 Runbook](community-template-import-full-chain-runbook.md)、[simulator-simc-end-to-end.md](simulator-simc-end-to-end.md) |
| P1 | 证据化报告 | 玩家可见数字来自 runner、日志或明确参考源；模型只负责解释 | `server/simulator_payload.py` |
| P1 | 发布与可观测 | 核心 API、刷新任务、SimC 和数据健康有可重复 smoke、超时与故障定位 | [remote-debugging.md](remote-debugging.md)、[verification-matrix.md](verification-matrix.md) |
| 下一步 | 炸鸡队长统一 ChatBot | 对外保持单一聊天入口；普通版本问答、个人模板与任务查询、允许来源查询走轻量 Tool；SimC 对比和 WCL 深度分析走 PostgreSQL 任务与一个通用 Worker；owner、版本、证据、新鲜度和失败降级可验证 | [统一 ChatBot 设计](plans/2026-07-24-chickenbro-chatbot-design.md) |
| P2 | 个人化工作台 | 角色、收藏、模板和任务历史围绕微信账号 owner 组织 | `apps/mini-taro/src/pages/profile/`、`server/news_backend.py` |
| P2 | PVE / WCL 恢复决策 | 明确数据授权、样本窗口、入口价值和失败边界 | `pages/pve/`、`pages/simulator/wcl.*` |
| 待决策 | 产品命名与首页权重 | 确定一句对外定位和第一主线，并同步 README 与导航文案 | [ideas.md](roadmap/ideas.md) |

## UI 交付路径

1. 用 canonical target 固化全量目标与设计语言；目标图决定可见结构和几何，真实 API/domain 决定内容与行为。
2. 从全量目标提取共享 owner 合同，由 `audit:ui-architecture` 阻断 route-private chrome、安全区和原生控件回流。
3. 在真实微信运行态验证 `news_home`、`simulator_home`、`news_detail`；结构预检后再做 target/runtime 像素复核。
4. 三基线成立后，按 news、builds、simulation/profile 固定批次传播。
5. 每个路由只做一次最终视觉复核和一个核心交互验证；单元测试不授予视觉通过。
6. 微信预览产物必须以源码内容哈希和构建时 Git identity 绑定当前 `apps/mini-taro/dist/weapp`；本地/远端 `main` 一致只能证明源码同步，不能证明 DevTools 正在消费最新包。

## 维护规则

- roadmap 控制在 150 行以内，只保留方向、优先级、能力边界和完成标准。
- 当前执行计划只允许出现在计划白名单；被替代后删除，Git 即历史。
- 稳定事实写肯定式合同；临时踩坑和否定式过程不进入长期控制面。
- 证据只指向当前存在且有 owner 的文件，不链接已删除计划或一次性截图目录。
- 新想法先进入 [ideas.md](roadmap/ideas.md)，确认优先级后再进入里程碑。
