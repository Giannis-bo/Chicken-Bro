# WOW Mini Program Roadmap

活动前端由 `apps/mini-taro` 负责，`packages/api-client/src` 负责 typed transport；根目录
`app.json` 与 `pages/` 只保留 14 路由兼容职责。机器可读 owner 矩阵见
[project-owner-map.json](project-owner-map.json)。

状态：`active`
更新时间：`2026-08-12`

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

装备模拟坚持 Exact-first：最终装备、强化、套装和 SimC 输入都由后端可追溯 authority 决定；
Catalog 只收录已验证可选装备。缺少来源、变体、轨道、套装或运行时 identity 时必须
`partial`、`blocked` 或 `UNVERIFIED`，不能用 S1、社区样本或前端推断补齐。

## 当前能力边界

| 能力 | 当前判断 | 下一步边界 |
| --- | --- | --- |
| 职业构筑与 SimC | Manifest v2、canonical resolver、精确装备/强化、任务保存和 26/14 执行边界已验证 | 保持单一后端事实与可解释 fail-closed |
| 至暗之夜 S2 | End Game 仓库候选已构建；官方 capture capped，Track/Set/Option authority 未闭合，候选为 `blocked` | 完成可枚举的官方 capture 与 SimC/track/set identity 后，才可重新构建候选 |
| Exact-first runtime | `0030`--`0035` foundation `runtime_verified`；provider/worker disabled、eligible source 为零 | 仅在完整 owner source 出现后另开 activation 与真实微信验收合同 |
| 炸鸡队长 | 聊天表面、流式与原生 Agent 已有交付证据；Smart Question/Evidence Planner 仍有待验收范围 | 新来源和 Phase 3--5 必须单独授权、审阅和发布 |
| 数据与发布 | PostgreSQL-only、Harness、验证矩阵、Taro owner 与 release packet 机制已建立 | 按 caller-proof 与新鲜验证逐项淘汰兼容面 |

## 当前优先级

| 优先级 | 里程碑 | 完成标准 | 权威入口 |
| --- | --- | --- | --- |
| P0 | 14 路由 UI 系统重建 | 共享 chrome、核心交互和全部 14 路由的真实微信运行态逐项复核；`gear_detail` 保持“候选 -> 后端合法配置 -> 显式应用 -> Resolve” | [UI 计划](plans/ui-reconstruction.md)、[current-ui](design/current-ui/README.md) |
| P0 | 至暗之夜 S2 End Game 数据候选 | 候选已构建但为 `blocked`；重新讨论完整官方 capture 方案前不再执行。只有 source membership、item/variant、宝石/附魔/美化、套装和轨道完整绑定后才可重建 candidate；Active Manifest 保持不变 | [S2 设计](superpowers/specs/2026-08-12-midnight-season-2-data-repository-design.md)、[候选证据](../artifacts/releases/2026-08-12-midnight-season-2-data-foundation/evidence.json) |
| P1 | Exact-first 与三来源 Catalog | production foundation 不等于玩家 Exact 闭环；零 eligible source 与 disabled provider/worker 必须持续如实返回 `blocked` | [当前边界](plans/2026-08-04-equipment-simulator-exact-first-persistence-resequence.md)、[生产证据](../artifacts/releases/2026-08-10-equipment-simulator-exact-first-production-foundation-deployment/evidence.json) |
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
| S2 End Game 候选 | `blocked` | 只生成隔离诊断；没有 pointer mutation、promotion 或生产写入 | [S2 evidence](../artifacts/releases/2026-08-12-midnight-season-2-data-foundation/evidence.json) |
| 端到端完整性 Goal | 暂缓 / `blocked` | 缺获批 authority 时，不以现有测试替代 Universe 闭包或完整微信矩阵 | [Goal](plans/2026-07-29-equipment-simulator-e2e-completeness-goal.md) |
| `gear_detail` UI 验收 | 正在推进 | 当前运行态为 `UNVERIFIED`；历史导入/保存/SimC 验收不能替代本轮视觉与核心交互验收 | [状态账本](design/current-ui/runtime-review-status.json) |

## 维护规则

- roadmap 保持方向与边界，不追加执行流水。
- 当前计划必须进入白名单；完成、停止或替代后删除其实施文档，Git 即过程归档。
- 稳定事实进入 architecture、governance、runbook 或 `project-state.json`；证据只链接存在且有 owner 的文件。
- 新想法先进入 [ideas.md](roadmap/ideas.md)，确认优先级后才进入本表。
