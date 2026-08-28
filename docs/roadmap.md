# WOW Mini Program Roadmap

活动前端由 `apps/mini-taro` 负责，`packages/api-client/src` 负责 typed transport；根目录
`app.json` 与 `pages/` 只保留 14 路由兼容职责。机器可读 owner 矩阵见
[project-owner-map.json](project-owner-map.json)。

状态：`active`
更新时间：`2026-08-27`

## 本文职责

本文只保留产品方向、当前优先级和用户可见完成标准。执行步骤进入
[plans/README.md](plans/README.md)；接口、运行和部署细节进入 architecture 或 runbook；
过程记录由 Git 与 release packet 保存。

## 产品方向

面向 WoW 玩家构建一体化分析工作台，把资讯、职业构筑、装备、SimC、任务结果和受证据约束的
AI 建议串成可复用路径：

`理解版本 -> 选择构筑 -> 保存模板 -> 执行模拟 -> 解释结果 -> 继续优化`

一级入口保持资讯、职业专精、智能分析、我的。PVE、WCL 和旧 WebSim 能力在数据授权、用户价值与
发布门禁同时明确前不恢复为一级入口。

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
| 至暗之夜 S2 | 正在推进；30555 current-runtime 的装备 Candidate、正式 Gear/Catalog/Community/Exact dormant pair、当前 Talent Catalog 和 Candidate Manifest v2 已在云端闭合，gen41 暂保留 | 装备库范围仍固定为团本（含巢穴）、大秘境、制造业、套装四个逻辑来源。closure v6 的 416/416 canonical item、15,572/15,572 public variants、1,665/1,665 crafted quality templates 和 74 个 enhancement options 已在 30555 上通过 533/533 矩阵、17,237/17,237 数值 readback，并生成 416 items、17,237 variants、74 options 的 verified runtime snapshot；23,348 个明确越界变体继续排除。云端 SimC 为 12.1.0.69497/30555eff，updateAvailable=false。Talent Catalog 已写入 PostgreSQL：5,227 节点、8,411 dependencies、4,947 dependencyNodes、40/40 profile specs、55 profiles，明确记录 13 个 runtime-baseline 和 MID1 退休批次；Talent revision 为 `websim-talent-catalog-v1-525bac297675`。Candidate Manifest v2 为 `season-manifest:sha256:46c76d033f6582dea26eba467d0c231245cfc8ee6f090da256f9899ff39c69e7`，绑定当前 Talent/Gear/Catalog/Community/Exact，且未切换 Active。API 读模型/校验/profile 冒烟通过 fail-closed 边界，但 spell/formula readiness 仍为 partial；Community 有效库仍为 80/80 Hero slots、40/40 specs（72 Raider.IO、8 WCL），2026-08-28 最新扫描锁定 WCL zone55/partition1 后仍为 79/80，aggregate sourceStatus=partial。官方当前季节只读探针已验证 season18，但 PostgreSQL Journal/装备明细刷新在 256 上限下发生可证明截断，1024 上限完整尝试又在 20 分钟安全边界停止，未写入半成品。生产装备读模型、stale season、gear refresh、legality authority、Catalyst、Talent spell/media 完整性和 Active Manifest promotion 仍未闭合。rebind 索引、Candidate Manifest、云端 recovery 及新外部证据已记录在 freshness evidence | [freshness evidence](../artifacts/releases/2026-08-25-s2-freshness-rebase/evidence.json) · [cloud closure index](../artifacts/releases/2026-08-25-s2-freshness-rebase/normalized/s2-equipment-library-closure-v6-cloud-index-v1.json) · [source policy](../server/data/midnight-season-2/source-policy.json) · [project-state](project-state.json) |
| Exact-first runtime | `0030`--`0035` foundation `runtime_verified`；provider/worker disabled、eligible source 为零 | 仅在完整 owner source 出现后另开 activation 与真实微信验收合同 |
| 炸鸡队长 | 聊天表面、流式与原生 Agent 已有交付证据；Smart Question/Evidence Planner 仍有待验收范围 | 新来源和 Phase 3--5 必须单独授权、审阅和发布 |
| 数据与发布 | PostgreSQL-only、Harness、验证矩阵、Taro owner 与 release packet 机制已建立 | 按 caller-proof 与新鲜验证逐项淘汰兼容面 |

## 当前优先级

| 优先级 | 里程碑 | 完成标准 | 权威入口 |
| --- | --- | --- | --- |
| P0 | 14 路由 UI 系统重建 | 共享 chrome、核心交互和全部 14 路由的真实微信运行态逐项复核；`gear_detail` 保持“候选 -> 后端合法配置 -> 显式应用 -> Resolve” | [UI 计划](plans/ui-reconstruction.md)、[current-ui](design/current-ui/README.md) |
| P0 | 至暗之夜 S2 四类范围装备库与社区 Exact | v73 数据候选、release gate、正式 Active Manifest generation 41、后端浏览/导入/混合替换和小程序构建已验证；用户已确认最新微信预览可收尾；社区导入与登录态保存的逐路径记录按 closure packet 显式 waiver，不升级为未执行的独立证据 | [当前设计](plans/2026-08-13-s2-selectable-catalog-community-exact-design.md)、[closure evidence](https://api.chickenbro.cloud/wow-evidence/releases/2026-08-24-s2-equipment-library-evidence-v2/artifacts/releases/2026-08-24-s2-equipment-library-ui-closure/evidence.json)、[Candidate README](../server/data/midnight-season-2/README.md) |
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
| 至暗之夜 S2 End Game 数据候选 | 正在推进；当前 Talent/Candidate Manifest 已封存，但生产/Active 门禁仍阻断 | 云端 PostgreSQL 已写入当前 SimC/TraitEdge Talent Catalog；Candidate Manifest v2 与 S2 Gear/Catalog/Community/Exact dormant pair 已完成绑定，未发生 pointer mutation 或 Active promotion。官方当前 season18 只读证据已刷新，但完整 Journal/装备明细同步因接口耗时边界未闭合；spell/media 完整性、stale season、装备生产读模型、Community aggregate、legality、Catalyst 和生产 preset 仍是独立门禁 | [freshness evidence](../artifacts/releases/2026-08-25-s2-freshness-rebase/evidence.json) |
| S2 四类范围装备库完整闭环 | 正在推进生产门禁；30555 current-runtime Candidate、正式 dormant pair 与 Candidate Manifest v2 已通过，gen41 暂保留 | 官方 S2 closure v6 的四类范围仍为 416/416 canonical items、15,572/15,572 public variants、1,665/1,665 crafted quality templates、74/74 enhancement probes，30555 当前矩阵 533/533 批、数值 readback 17,237/17,237、runtime snapshot 416 items/17,237 variants/74 options 均 verified，23,348 个明确越界变体仍排除。当前 Talent Catalog 已在云端 PG 更新为 5,227 节点、55 profiles、40/40 specs，Candidate Manifest v2 已绑定当前 talent revision；其中 13 个 profile 是 runtime-baseline，不能升级为推荐模板。新外部证据已锁定 WCL zone55/partition1；官方 season18 探针 verified，但 Journal/装备明细完整刷新仍被截断/耗时门禁阻断且没有写入半成品。下一步只剩生产装备读模型/旧 profile 处置、stale season、gear refresh、Community sourceStatus、legality、Catalyst、spell/media 完整性与 Active Manifest gates；当前不切换 gen41。证据路径、报告 ID 和 SHA 已记录在 freshness evidence | [freshness evidence](../artifacts/releases/2026-08-25-s2-freshness-rebase/evidence.json) · [cloud closure index](../artifacts/releases/2026-08-25-s2-freshness-rebase/normalized/s2-equipment-library-closure-v6-cloud-index-v1.json) · [source policy](../server/data/midnight-season-2/source-policy.json) · [project-state](project-state.json) |
| 端到端完整性 Goal | 暂缓 / `blocked` | 缺获批 authority 时，不以现有测试替代 Universe 闭包或完整微信矩阵 | [Goal](plans/2026-07-29-equipment-simulator-e2e-completeness-goal.md) |
| `gear_detail` UI 验收 | 用户已确认收尾（保留手工 waiver） | typed API、替换/导入/保存代码路径与本地构建已验证；用户确认最新微信预览可收尾；社区导入与 authenticated save 未另行录制逐路径证据 | [状态账本](design/current-ui/runtime-review-status.json) · [closure evidence](https://api.chickenbro.cloud/wow-evidence/releases/2026-08-24-s2-equipment-library-evidence-v2/artifacts/releases/2026-08-24-s2-equipment-library-ui-closure/evidence.json) |

## 维护规则

- roadmap 保持方向与边界，不追加执行流水。
- 当前计划必须进入白名单；完成、停止或替代后删除其实施文档，Git 即过程归档。
- 稳定事实进入 architecture、governance、runbook 或 `project-state.json`；证据只链接存在且有 owner 的文件。
- 新想法先进入 [ideas.md](roadmap/ideas.md)，确认优先级后才进入本表。
