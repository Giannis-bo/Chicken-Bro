# WOW Mini Program Roadmap

活动前端由 `apps/mini-taro` 负责，`packages/api-client/src` 负责 typed transport；根目录
`app.json` 与 `pages/` 只保留 14 路由兼容职责。机器可读 owner 矩阵见
[project-owner-map.json](project-owner-map.json)。

状态：`active`
更新时间：`2026-08-28`

## 本文职责

本文只保留产品方向、当前优先级和用户可见完成标准。执行步骤进入
[plans/README.md](plans/README.md)；接口、运行和部署细节进入 architecture 或 runbook；
过程记录由 Git 与 release packet 保存。

## 产品方向

面向 WoW 玩家构建一体化分析工作台，把资讯、职业构筑、装备、SimC、任务结果和受证据约束的
AI 建议串成可复用路径：

`理解版本 -> 选择构筑 -> 保存模板 -> 执行模拟 -> 解释结果 -> 继续优化`

活动 Taro 一级入口保持“资讯、专精、队长、我的”。根目录兼容配置仍保留“最新资讯、职业专精、
智能分析、我的”旧文案，但 14 条路径与活动 Taro 完全同序；兼容文案不是当前产品导航权威。
PVE、WCL 和旧 WebSim 能力在数据授权、用户价值与发布门禁同时明确前不恢复为一级入口。

装备模拟坚持 Exact-first：官方 API 快照是 S2 item、variant、轨道、来源、套装、制造和强化游戏事实
的唯一裁决源；Catalog 只能从其中已验证且在范围内的事实派生，不能由 SimC、Raider.IO、S1 或前端
补齐。至暗之夜 S2 装备库的范围固定为四个逻辑来源：团本（包括巢穴）、大秘境、制造业和套装；
其中“巢穴”在产品层归入团本，但官方原始 `lair` 来源必须保留，套装是独立 membership 维度而不是
原始掉落来源的替代。当前执行目标是闭合这四类范围内的完整装备库，不扩展为全赛季十来源集合；
`publicSimcReadyRate=100%` 与官方范围的候选/纳入/排除指标必须分别报告。社区模板中 Catalog 外的
真实装备只能作为 `community_observed` 的只读 Exact 实例展示、计算和模拟，不能扩张候选列表或升级
为官方事实；缺少精确变体或运行时 identity 时必须 `partial`、`blocked` 或 `UNVERIFIED`。

## 当前能力边界

| 能力 | 当前判断 | 下一步边界 |
| --- | --- | --- |
| 职业构筑与 SimC | Manifest v2、canonical resolver、精确装备/强化、任务保存和 26/14 执行边界已验证 | 保持单一后端事实与可解释 fail-closed |
| 至暗之夜 S2 | Active 与 Candidate 分层推进；生产仍是正式 Active Manifest generation 41，30555 freshness Candidate 已封存但未 promotion | Active 当前绑定 SimC 12.1.0.69299/f50a，`updateAvailable=true`，全局 `/api/data/health=partial`。2026-08-28 刷新后 season 18、WebSim sync 与生产 Gear Catalog 已 `verified`（567 items、20,910/20,910 variants）；Stat Weights 为新鲜 `partial`（23 accepted / 97 blocked），Community Templates 仍因 WCL combatantinfo seed/report 缺口和 Active observed compile 完整性门禁保持 `partial`，gear release catch-up 超时且没有改写 Active。Candidate Manifest `season-manifest:sha256:46c76d...` 未切换 Active；legality、Catalyst、spell/media、Community 与 cutover 继续独立裁决 | [cloud refresh evidence](../artifacts/releases/2026-08-28-cloud-main-data-refresh/evidence.json) · [freshness evidence](../artifacts/releases/2026-08-25-s2-freshness-rebase/evidence.json) · [source policy](../server/data/midnight-season-2/source-policy.json) |
| Exact-first runtime | `0030`--`0035` foundation `runtime_verified`；provider/worker disabled、eligible source 为零 | 仅在完整 owner source 出现后另开 activation 与真实微信验收合同 |
| 炸鸡队长 | 聊天表面、流式与原生 Agent 已有交付证据；Smart Question/Evidence Planner 仍有待验收范围 | 新来源和 Phase 3--5 必须单独授权、审阅和发布 |
| 数据与发布 | PostgreSQL-only、Harness、验证矩阵、Taro owner 与 release packet 机制已建立 | 按 caller-proof 与新鲜验证逐项淘汰兼容面 |

## 当前实际状态分层

| 层 | 状态 | 当前事实 |
| --- | --- | --- |
| UI 源码与路由 | `active_unverified` | 活动 owner 是 `apps/mini-taro`，14 条 Taro/兼容路径完全同序；架构审计为 14 routes、14 contracts、284 checks、0 findings。视觉账本仍是 14 条 `UNVERIFIED`，历史 6 条接受和 8 条 waiver 不能改写为当前 14/14 通过。 |
| S2 生产 | `partial` | 正式 Active Manifest generation 41 保持不变并继续绑定 f50a SimC；season 18、WebSim sync、Gear Catalog 已新鲜 `verified`，Stat Weights 新鲜 `partial`，Community Templates、gear release refresh 与 cutover readiness 仍未闭合。 |
| S2 freshness | `Candidate` | 30555 replay、dormant release pair、Talent Catalog 与 Candidate Manifest 已验证；没有 Active pointer mutation。 |
| 云端代码身份 | `已完成` | 仓库最新树已用 no-bootstrap、no-async hot deploy 发布；deployable tracked set 逐文件 hash 与云端一致，`data_health_followup.py` 和 `postgres_cache_store.py` 均回到仓库 owner。部署脚本新增真实 tar 归档回归测试，忽略的微信产物与私有配置不再进入 backend archive。代码一致不提升业务数据状态；全局 health 仍为 `partial`。 |
| 云端卫生 | `已完成（限定范围）` | 2026-08-28 已清除无引用候选、旧 SimC 可重建版本、Git 已删除的部署残留、178 份被当前 S2 恢复点替代的旧代码/数据备份，以及本次 tar overlay 重新带入的 `apps/mini-taro/dist`、`.swc` macOS 编译缓存与两份 `project.private.config.json`；部署排除已补测试防复发。正式 evidence、PG 数据与经 `pg_restore --list` 验证的最新 1.16 GB 恢复点、Exact-first foundation、Active/Candidate/单一 rollback 均保留。备份与数据刷新后磁盘为 77% 使用、16G 可用；清理不等于 Active promotion。 |

## 当前优先级

| 优先级 | 里程碑 | 完成标准 | 权威入口 |
| --- | --- | --- | --- |
| P0 | 14 路由 UI 系统重建 | 共享 chrome、核心交互和全部 14 路由的真实微信运行态逐项复核；`gear_detail` 保持“候选 -> 后端合法配置 -> 显式应用 -> Resolve” | [UI 计划](plans/ui-reconstruction.md)、[current-ui](design/current-ui/README.md) |
| P0 | 至暗之夜 S2 四类范围装备库与社区 Exact | v73 已发布为 Active generation 41；30555 freshness 结果仅作为 dormant Candidate。生产 season/WebSim/Gear Catalog 已刷新 verified；下一步聚焦 Community combatantinfo/observed compile 输入、Stat Weights 97 个 blocked 结果、gear release timeout、legality/Catalyst 与 cutover gates，再另行决定 promotion；既有用户 acceptance 与 waiver 边界保持不变 | [当前设计](plans/2026-08-13-s2-selectable-catalog-community-exact-design.md)、[cloud refresh evidence](../artifacts/releases/2026-08-28-cloud-main-data-refresh/evidence.json)、[closure evidence](https://api.chickenbro.cloud/wow-evidence/releases/2026-08-24-s2-equipment-library-evidence-v2/artifacts/releases/2026-08-24-s2-equipment-library-ui-closure/evidence.json) |
| P1 | Exact-first 与四类范围 Catalog | production foundation 不等于玩家 Exact 闭环；零 eligible source 与 disabled provider/worker 必须持续如实返回 `blocked` | [当前边界](plans/2026-08-04-equipment-simulator-exact-first-persistence-resequence.md)、[生产证据](../artifacts/releases/2026-08-10-equipment-simulator-exact-first-production-foundation-deployment/evidence.json) |
| P1 | Catalog Browse 纠偏 | 修复 Browse membership、最高 rank 与装备类型门禁；不重开 generation 35 的归档基线 | [当前计划](plans/2026-07-29-manifest-catalog-progression-display-contract.md) |
| P1 | 炸鸡队长统一 ChatBot | 保持 owner、授权、来源、新鲜度和失败回退可验证；Evidence Planner 真实 WeChat 验收仍待办 | [ChatBot 架构](plans/2026-07-24-chickenbro-chatbot-design.md)、[Evidence Planner](plans/2026-08-04-chickenbro-evidence-planner-design.md) |
| P1 | SQLite 全面退役 | runtime、worker、同步、CLI 与测试只保留 PostgreSQL 正式路径 | [退役设计](plans/2026-08-02-sqlite-complete-retirement-design.md) |
| P2 | 个人化工作台 | 角色、收藏、模板与任务历史围绕微信账号 owner 组织 | `apps/mini-taro/src/pages/profile/` |
| 待决策 | 产品命名与首页权重 | 确定一句对外定位和第一主线，并同步 README 与导航文案 | [ideas.md](roadmap/ideas.md) |

## 装备模拟状态分层

| 层级 | 状态 | 当前含义 | 权威入口 |
| --- | --- | --- | --- |
| 长期目标合同 | 已完成 | v1 的用户主链、40/26/14 能力边界和 fail-closed 合同持续有效；不授予新执行权 | [目标架构](plans/2026-07-28-equipment-simulator-target-architecture.md) |
| v1 已完成基线 | 已完成 | generation 35 的 Manifest v2 已归档；全局数据健康仍为 `partial` | [project-state.json](project-state.json) |
| 至暗之夜 S2 End Game 数据候选 | 正在推进；Candidate 已封存，Active 门禁仍阻断 | PG 中存在新 Talent Catalog 与 dormant Gear/Catalog/Community/Exact pair；Candidate Manifest 完成绑定，但没有 pointer mutation。生产 season 18、WebSim 与 Gear Catalog 已在 2026-08-28 刷新 verified；Community aggregate/observed compile、Stat Weights、gear release timeout、spell/media、legality、Catalyst 与 cutover 仍是独立门禁 | [cloud refresh evidence](../artifacts/releases/2026-08-28-cloud-main-data-refresh/evidence.json) · [freshness evidence](../artifacts/releases/2026-08-25-s2-freshness-rebase/evidence.json) |
| S2 四类范围装备库完整闭环 | 正在推进生产门禁；30555 Candidate 已通过，Active generation 41 保留 | Candidate 数量与 replay 均 verified，但 30555 是证据绑定的 Candidate runtime，不是当前 Active runtime。生产继续以 generation 41/f50a 提供服务；最新 health 仍为 `partial`，新 SimC tag 只报告 `active_manifest_cutover_required`。必须先闭合 Community、Stat Weights、gear release、legality、Catalyst、spell/media 与 cutover gates，当前不切换 Active | [cloud refresh evidence](../artifacts/releases/2026-08-28-cloud-main-data-refresh/evidence.json) · [project-state](project-state.json) |
| 端到端完整性 Goal | 暂缓 / `blocked` | 缺获批 authority 时，不以现有测试替代 Universe 闭包或完整微信矩阵 | [Goal](plans/2026-07-29-equipment-simulator-e2e-completeness-goal.md) |
| `gear_detail` UI 验收 | 用户已确认收尾（保留手工 waiver） | typed API、替换/导入/保存代码路径与本地构建已验证；用户确认最新微信预览可收尾；社区导入与 authenticated save 未另行录制逐路径证据 | [状态账本](design/current-ui/runtime-review-status.json) · [closure evidence](https://api.chickenbro.cloud/wow-evidence/releases/2026-08-24-s2-equipment-library-evidence-v2/artifacts/releases/2026-08-24-s2-equipment-library-ui-closure/evidence.json) |

## 维护规则

- roadmap 保持方向与边界，不追加执行流水。
- 当前计划必须进入白名单；完成、停止或替代后删除其实施文档，Git 即过程归档。
- 稳定事实进入 architecture、governance、runbook 或 `project-state.json`；证据只链接存在且有 owner 的文件。
- 新想法先进入 [ideas.md](roadmap/ideas.md)，确认优先级后才进入本表。
