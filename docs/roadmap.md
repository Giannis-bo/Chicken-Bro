# WOW Mini Program Roadmap

Active frontend ownership is explicit: `apps/mini-taro` owns the active 14-route runtime and `packages/api-client/src` owns typed transport. The root `app.json` and `pages/` tree remain compatibility consumers only, preserving the 14-route surface without receiving new first-level ownership. The machine-readable route matrix is `docs/project-owner-map.json`.

状态：`active`
更新时间：`2026-08-06`

## 本文职责

本文件只回答三个问题：产品要解决什么、当前主线是什么、下一阶段按什么顺序推进。

执行步骤只进入 `docs/plans/README.md` 白名单；设计事实只进入 `DESIGN.md` 与 `docs/design/current-ui/`；接口、运行和部署细节留在稳定架构或 runbook。历史过程、否定式约定、截图账本和阶段证据由 Git 与 release packet 保存。

## 产品方向

面向 WoW 玩家构建一体化分析工作台，把资讯、职业构筑、装备、SimC、任务结果和证据受限的 AI 建议连接成一条可复用路径：

`理解版本 -> 选择构筑 -> 保存模板 -> 执行模拟 -> 解释结果 -> 继续优化`

产品以四个一级入口组织：资讯、职业专精、智能分析、我的。PVE、WCL 和 WebSim 历史能力保留，但在真实数据源、用户价值和发布门禁明确前不恢复为一级入口。

装备模拟的稳定承诺采用 Exact-first：优先保证精确装备组合经后端 Resolve 后生成不可变的 SimulationSnapshot，并由绑定版本的 SimC 可复现执行；完整且可执行的 ExactItemInstance 不因尚未进入 Catalog 而被阻断。Catalog 独立作为“已验证可选装备目录”，首期聚焦大秘境、团本和制造三个来源子集，并按来源分别报告 `complete`、`partial` 或 `blocked`；任何进入模拟器可换装 Catalog 的 BrowseVariant 都必须能生成至少一个 SimC-ready ExactItemInstance，纯展示但不可模拟的物品不得混入可换装候选。新出现的精确装备只能先进入隔离 observation queue，完成来源、变体、规则和 SimC 预检后再通过不可变 CatalogRevision 发布；不得因一次用户请求直接热补正式库。在没有可枚举且获授权的完整权威源前，不承诺未经限定的“当前赛季全部 PVE 装备”。详细边界见 [Exact-first Catalog 设计](plans/2026-08-04-equipment-simulator-exact-first-catalog-design.md)，分段实施和停止门禁见 [实施计划](plans/2026-08-04-equipment-simulator-exact-first-implementation.md)。

## 当前能力边界

| 能力 | 当前判断 | 下一步边界 |
| --- | --- | --- |
| 资讯 | 已有首页、列表、中文详情、来源与发布状态 | 保持来源、翻译和内容状态可追踪 |
| 职业构筑 | canonical resolver、Manifest v2、社区模板原子导入、精确装备与强化、异步属性快照和 Taro typed API 已完成并通过真实微信主路径 | 维持单一后端装备事实与当前赛季证据，不为来源缺口补值 |
| SimC 与任务 | 26 个支持专精的确定性输入、真实执行、任务保存和结构化报告已验证；14 个不支持专精在执行前确定性阻断 | 持续保证输入可执行、数字有证据、失败可解释 |
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
| 已完成 | 构筑到模拟闭环稳定 | 天赋/装备模板可确定性保存、加载、转换、校验、提交和复盘；装备目录按 CatalogRevision 发布，普通升级轨道只暴露最高 rank BrowseVariant，制造品质和虚空晋升分别使用不伪造 rank 的 canonical progression state，制造副属性属于 EnhancementSelection，社区和个人模板保留 ExactItemInstance；真实玩家先沉淀为可重放 snapshot，再按当前 authority 编译天赋/装备 projection；每日 80 槽 TemplateSet 对成功槽更新、失败槽保留同槽 LKG 并标记过期，完整校验后原子切换；任意专精展示两个可导入装备模板，任意 Hero 展示一个同玩家可导入天赋模板；完整 SimC 只在玩家请求时运行；不可执行状态 fail closed。2026-07-29 装备模拟目标架构 v1 的 Phase 0-4 已完整归档：正式 Manifest v2 在 generation 35 原子绑定 Catalog、Exact、Gear、Community、Talent 与 SimC runtime；Catalog 含 566 个 ItemDefinition、4718 个 BrowseVariant，Exact Registry 含 749 个 ExactItemInstance 与 141 个 EnhancementSelection；40/40 专精、80 个社区模板、37 个 ready loadout、21 个支持专精 ready snapshot、26/26 真实 SimC、14/14 前置阻断、CAS v1 回滚/v2 恢复、官方微信社区导入/保存/SimC 接力、CI、生产和三方 runtime 身份门禁全部通过。55 条来源歧义继续保持 literal partial，全局健康仍如实为 partial。 | [装备模拟目标架构](plans/2026-07-28-equipment-simulator-target-architecture.md)、[Phase 4 归档证据](../artifacts/releases/2026-07-29-equipment-simulator-phase4-manifest-cutover/evidence.json)、[Phase 3 归档证据](../artifacts/releases/2026-07-29-equipment-simulator-phase3-resolved-snapshot/evidence.json)、[Phase 2 归档证据](../artifacts/releases/2026-07-29-equipment-simulator-phase2-exact-enhancement/evidence.json)、[Phase 1 归档证据](../artifacts/releases/2026-07-29-equipment-simulator-phase1-catalog-contract/evidence.json)、[Phase 0 归档证据](../artifacts/releases/2026-07-28-equipment-simulator-phase0-unblock/evidence.json)、[Observed Build Registry 设计](plans/2026-07-23-observed-build-registry-design.md)、[共享玩家切换计划](plans/2026-07-23-observed-build-registry-cutover-implementation.md)、[社区装备回填修复计划](plans/2026-07-25-community-gear-backfill-fairness.md)、[社区模板 Runbook](community-template-import-full-chain-runbook.md)、[simulator-simc-end-to-end.md](simulator-simc-end-to-end.md) |
| 正在推进 | Exact-first 与三来源 Catalog 解耦 | Task 3A delivery closure、Task 4P、Task 4L pure-domain、Task 3B persistence delivery closure 和 Task 4W delivery closure 均已完成；Task 3A 的第八次 candidate `t3a260805163536` 与 Task 3A/3B/4W 正式 packet 均保持 `runtime_verified / candidate_verified`、closure `pending`，不代表用户闭环。Task 5A 已完成 local source/profile/job/API/client binding，ready path 仍 literal blocked。Task 5B 的后续 authority 覆盖不阻塞 baseline；Task 5C 已合入 `f4dbb13c`，其 final candidate runtime 保持 `runtime_verified / candidate_verified`。production foundation 已将候选等价 runtime 与 `0030`--`0035` 以 runtime-verified 落入正式 PostgreSQL，provider/worker/timer 保持禁用；aggregate preflight 的所有 admission gate 为零，完整 source 继续 literal blocked，不创建 task。只有后来命中完整 owner source 后才单独授权 activation 与现有页面真实微信验收。Catalog/Manifest pointer、generation 35、async backflow 和 Task 6C 仍不在范围。 | [持久化与运行链重排](plans/2026-08-04-equipment-simulator-exact-first-persistence-resequence.md)、[Task 5A 设计](plans/2026-08-07-equipment-simulator-exact-first-task5a-api-runtime.md)、[Task 5B authority-source contract](plans/2026-08-07-equipment-simulator-exact-first-task5b-active-authority-source.md)、[Task 5C 设计](plans/2026-08-10-equipment-simulator-exact-first-task5c-runtime-authority-release-design.md)、[Task 5C evidence](../artifacts/releases/2026-08-10-equipment-simulator-exact-first-task5c-runtime-authority-release/evidence.json)、[Production foundation design](plans/2026-08-10-exact-first-production-foundation-deployment-design.md)、[implementation plan](plans/2026-08-10-exact-first-production-foundation-deployment-implementation.md)、[requirement](../artifacts/releases/2026-08-10-equipment-simulator-exact-first-production-foundation-deployment/requirement.json)、[evidence](../artifacts/releases/2026-08-10-equipment-simulator-exact-first-production-foundation-deployment/evidence.json)、[Task 3A evidence](../artifacts/releases/2026-08-04-equipment-simulator-exact-first/evidence.json)、[Task 3B evidence](../artifacts/releases/2026-08-06-equipment-simulator-exact-first-task3b/evidence.json)、[Task 4W evidence](../artifacts/releases/2026-08-06-equipment-simulator-exact-first-task4w/evidence.json) |
| P1 | 证据化报告 | 玩家可见数字来自 runner、日志或明确参考源；模型只负责解释 | `server/simulator_payload.py` |
| 已完成 | Exact-first Production Foundation Deployment | Task 5C 候选等价 runtime 与 `0030`--`0035` 已以可回滚、无 backflow 方式落入正式 PostgreSQL；provider/worker 保持 disabled，首 source aggregate preflight 为零。它完成了可上线体验的真实底座，不把零 eligible source 包装为失败或用户 Exact 闭环。 | [设计](plans/2026-08-10-exact-first-production-foundation-deployment-design.md) · [实施计划](plans/2026-08-10-exact-first-production-foundation-deployment-implementation.md) · [requirement](../artifacts/releases/2026-08-10-equipment-simulator-exact-first-production-foundation-deployment/requirement.json) · [evidence](../artifacts/releases/2026-08-10-equipment-simulator-exact-first-production-foundation-deployment/evidence.json) |
| P1 | 发布与可观测 | 核心 API、刷新任务、SimC 和数据健康有可重复 smoke、超时与故障定位 | [remote-debugging.md](remote-debugging.md)、[verification-matrix.md](verification-matrix.md) |
| P1 | SQLite 全面退役 | 后端、worker、同步、CLI、测试和迁移工具只保留 PostgreSQL 持久层；缺少 PostgreSQL 配置 fail closed，业务单测使用无 SQL 语义的有界 store fake，SQL/事务合同由 PostgreSQL 专项测试与真实候选证明；历史 release 证据可以保留，但没有 SQLite 可执行入口、环境变量或运行目录依赖 | [退役设计](plans/2026-08-02-sqlite-complete-retirement-design.md)、[数据库架构](database-architecture.md) |
| 正在推进 | 炸鸡队长统一 ChatBot | 队长已收敛为会话、新话题和存档三个入口；用户自然咨询正式服/PTR 时，受控来源 Agent 自动调用允许且新鲜的社区来源、个人数据或分析任务，不强迫提交 WCL 链接。云端 Codex 执行器已完成代理选路修复、服务重启和端到端候选 smoke，现已启用；来源记忆通过受控同步与带版本时间的事实摘要持续更新，不训练模型权重。能力演化控制面 Phase 1 的 owner-bound Trace、确定性 Outcome、文本不可反查投影和离线 Eval 已归档；Phase 2 也已归档：现有 Raider.IO 与 Warcraft Logs Tool 已迁移为 PostgreSQL 不可变 Manifest/Registry Release 驱动发现，执行继续绑定仓库内 adapter，个人模板和 SimC 仍是 context evidence。当前 Smart Question Chain 以通用 QuestionFrame、按证据需求的能力规划、受控官方当前/PTR来源和 Trace observation 替代“未命中就泛化直聊”；不为单一职业或问法写死回答。Evidence Planner 第一切片已候选验证，真实 WeChat 验收待办；新增第三方来源先进入独立 SourceContract。Toolsmith、Champion/Candidate、shadow、canary 和 promotion 仍保持隔离的后续阶段。owner、授权、版本、来源、新鲜度、候选身份和失败回退必须可验证 | [后端架构](plans/2026-07-24-chickenbro-chatbot-design.md) · [Smart Question Chain 设计](plans/2026-08-03-chickenbro-smart-question-chain-design.md) · [Evidence Planner 设计](plans/2026-08-04-chickenbro-evidence-planner-design.md) · [Evidence Planner 候选证据](../artifacts/releases/2026-08-04-chickenbro-evidence-planner/evidence.json) · [实施计划](plans/2026-08-03-chickenbro-smart-question-chain-implementation.md) · [能力演化控制面设计](plans/2026-08-02-chickenbro-capability-evolution-design.md) · [Phase 1 归档证据](../artifacts/releases/2026-08-02-chickenbro-observability-phase1/evidence.json) · [Phase 2 归档证据](../artifacts/releases/2026-08-02-chickenbro-tool-registry-phase2/evidence.json) |
| 等待用户验收 | 炸鸡队长 Evidence Planner | 保持来源与场景硬边界，把单次 capability 命中升级为可组合证据维度、`answered/partial/researching/blocked` outcome 与跨轮重新规划；第一切片只复用现有官方、Raider.IO 与 WCL 受控来源，第三方来源需先完成独立 SourceContract | [设计](plans/2026-08-04-chickenbro-evidence-planner-design.md) · [实施计划](plans/2026-08-04-chickenbro-evidence-planner-implementation.md) · [候选证据](../artifacts/releases/2026-08-04-chickenbro-evidence-planner/evidence.json) |
| 已完成 | 炸鸡队长 Codex 自主研究循环 | Codex 自主理解研究目标、使用原生网页检索和可选受控 ToolBox、根据观察迭代并自然判断结论；ToolBox 仅提供原子执行能力。职业、版本、场景、站点和固定问法不再成为回答路由。生产使用 `gpt-5.6-luna` 原生 Agent：同一回合自行决定 native web search、通用公开网页快照或服务已持有的大秘境同职责快照，后端只执行有界只读读取、安全限制、会话和 MCP observation 展示；不为 Archon、Raider.IO、WCL 或某职业写固定 adapter/答案。真实微信已验证当前强度、跨问题追问、来源呈现与长对话输入框可用；main、正式服务和普通/流式 smoke 已完成。全局数据健康仍如实为 `partial`，与本功能发布结论分开记录 | [设计](plans/2026-08-04-chickenbro-agentic-research-design.md) · [实施计划](plans/2026-08-04-chickenbro-agentic-research-loop-implementation.md) · [发布证据](../artifacts/releases/2026-08-05-chickenbro-native-agent/evidence.json) · [通用网页 Tool 合同](plans/2026-08-04-chickenbro-generic-public-web-research-tool.md) |
| P2 | 个人化工作台 | 角色、收藏、模板和任务历史围绕微信账号 owner 组织 | `apps/mini-taro/src/pages/profile/`、`server/news_backend.py` |
| P2 | PVE / WCL 恢复决策 | 明确数据授权、样本窗口、入口价值和失败边界 | `pages/pve/`、`pages/simulator/wcl.*` |
| 待决策 | 产品命名与首页权重 | 确定一句对外定位和第一主线，并同步 README 与导航文案 | [ideas.md](roadmap/ideas.md) |

## 装备模拟状态分层

| 层级 | 状态 | 当前含义 | 权威入口 |
| --- | --- | --- | --- |
| 长期目标合同 | 已完成 | 用户主链、40/26/14 能力边界、后端可信边界、fail-closed 状态和验收矩阵已经批准并持续有效；它不是活动执行计划 | [目标架构](plans/2026-07-28-equipment-simulator-target-architecture.md) |
| v1 已完成基线 | 已完成 | Phase 0-4 已在 generation 35 归档；该结论只证明目标架构 v1 的发布闭环，不把全局 `partial` 包装成健康，也不代表今后没有缺陷纠偏 | [机器状态](project-state.json)、[Phase 4 证据](../artifacts/releases/2026-07-29-equipment-simulator-phase4-manifest-cutover/evidence.json) |
| Catalog Browse 纠偏 | 正在推进 | 当前候选只修复 Browse membership、最高 rank 和装备类型门禁；正式 Manifest 在最终微信验收和 Harness 关闭前保持 generation 35，不重开已归档 Phase 0-4 | [当前纠偏计划](plans/2026-07-29-manifest-catalog-progression-display-contract.md) |
| 端到端完整性复核 Goal | 暂缓 | 三枚 exact-build TACT key 或 64 条权威解密记录不可获得，Goal 继续保持 `blocked`；已验证的 fail-closed 实现、测试与脱敏证据可进入主干，但这不建立 19 类 Universe 闭包、40 专精真实微信矩阵、正式候选、生产 promotion 或 Goal 完成。只在取得获批 authority 后恢复 | [Goal 控制计划](plans/2026-07-29-equipment-simulator-e2e-completeness-goal.md) |
| `gear_detail` UI 验收 | 正在推进 | 14 路由 Target-First 重建继续独立推进；当前 `gear_detail` 运行态仍为 `UNVERIFIED`，Phase 4 的社区导入/保存/SimC 接力验收不能替代本轮完整视觉和核心交互验收 | [UI 计划](plans/ui-reconstruction.md)、[运行态账本](design/current-ui/runtime-review-status.json) |

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
