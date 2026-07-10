# 历史计划索引

`docs/plans/` 是实施证据归档区。这里的文件记录过往计划、审计、交接和阶段性实现路径，帮助追溯“当时为什么这么做”。它们不是产品或运行时决策的第一入口；需要当前结论时，先看 [../project-state.json](../project-state.json)、[../roadmap.md](../roadmap.md) 和下面列出的架构 / runbook。

## 管理规则

- 现有日期计划作为历史实施证据保留。
- 不为了匹配当前行为而改写旧计划。
- 行为变更时优先更新当前契约文档。
- 只有新的多步骤工作确实无法由现有 runbook 或架构文档承载时，才新增日期计划。
- 计划落地或被取代后，在本索引里记录状态和当前入口。

## 当前真实入口

| 领域 | 现在看这里 |
| --- | --- |
| 当前机器可读状态和 active release artifact | [../project-state.json](../project-state.json) |
| 产品状态和里程碑 | [../roadmap.md](../roadmap.md) |
| 想法池和已采纳索引 | [../roadmap/ideas.md](../roadmap/ideas.md) |
| 职业专精、装备 / 天赋 / SimC 入口 | [../builds-architecture.md](../builds-architecture.md) |
| 数据库和 PostgreSQL-only 运行时 | [../database-architecture.md](../database-architecture.md) |
| 装备库治理 | [../gear-database-governance.md](../gear-database-governance.md) |
| 装备模拟发布流程 | [../gear-simulation-full-chain-runbook.md](../gear-simulation-full-chain-runbook.md) |
| 天赋模拟发布流程 | [../talent-simulation-full-chain-runbook.md](../talent-simulation-full-chain-runbook.md) |
| 社区模板导入 | [../community-template-import-full-chain-runbook.md](../community-template-import-full-chain-runbook.md) |
| SimC 任务链路 | [../simulator-simc-end-to-end.md](../simulator-simc-end-to-end.md) |
| 资讯内容架构 | [../news-architecture.md](../news-architecture.md) |
| 云端运维 | [../remote-debugging.md](../remote-debugging.md) |
| UI 规则 | [../ui-style-guide.md](../ui-style-guide.md) |

## 计划归档

| 计划 | 状态 | 当前入口 |
| --- | --- | --- |
| [2026-07-10-equipment-simulator-capability-delivery-plan.md](2026-07-10-equipment-simulator-capability-delivery-plan.md) | 正在推进 / Phase 0-5 delivery index | [../project-state.json](../project-state.json), [../roadmap.md](../roadmap.md), [../harness.md](../harness.md) |
| [2026-07-10-equipment-simulator-phase0-safety-plan.md](2026-07-10-equipment-simulator-phase0-safety-plan.md) | 下一步 / Phase 0 三个候选部署小 PR | [2026-07-10-equipment-simulator-capability-delivery-plan.md](2026-07-10-equipment-simulator-capability-delivery-plan.md), [2026-07-10-equipment-simulator-capability-architecture-design.md](2026-07-10-equipment-simulator-capability-architecture-design.md) |
| [2026-07-10-equipment-simulator-capability-architecture-design.md](2026-07-10-equipment-simulator-capability-architecture-design.md) | 书面规格已批准 / 待实施计划 / 未实施 | [../roadmap.md](../roadmap.md), [../harness.md](../harness.md), [../../TODOS.md](../../TODOS.md) |
| [2026-07-10-project-harness-normalization-goal-plan.md](2026-07-10-project-harness-normalization-goal-plan.md) | 已完成 / closure audit archived | [../project-state.json](../project-state.json), [../harness.md](../harness.md), [../roadmap.md](../roadmap.md), [../project-owner-map.json](../project-owner-map.json), [../../artifacts/releases/2026-07-10-project-harness-normalization/closure-audit.json](../../artifacts/releases/2026-07-10-project-harness-normalization/closure-audit.json) |
| [2026-07-09-harness-guided-project-optimization-plan.md](2026-07-09-harness-guided-project-optimization-plan.md) | Phase 0 + Phase 1 已完成 / 当前 UI 基线已验收 | [../harness.md](../harness.md), [../roadmap.md](../roadmap.md) |
| [2026-07-09-docs-implementation-current-truth-review.md](2026-07-09-docs-implementation-current-truth-review.md) | 当前对账索引 / 已同步 accepted baseline | [../roadmap.md](../roadmap.md), [../harness.md](../harness.md) |
| [2026-06-09-specializations-tab.md](2026-06-09-specializations-tab.md) | 已落地 | [../builds-architecture.md](../builds-architecture.md), [../roadmap.md](../roadmap.md) |
| [2026-06-09-unified-backend-cloud-deploy.md](2026-06-09-unified-backend-cloud-deploy.md) | 已落地 | [../remote-debugging.md](../remote-debugging.md), [../../README.md](../../README.md#轻量云部署) |
| [2026-06-11-simc-flow-risk-avoidance.md](2026-06-11-simc-flow-risk-avoidance.md) | 已落地为契约基线 | [../simulator-simc-end-to-end.md](../simulator-simc-end-to-end.md), [../roadmap.md](../roadmap.md) |
| [2026-06-17-builds-inline-gear-simulator-design.md](2026-06-17-builds-inline-gear-simulator-design.md) | 已落地 | [../builds-architecture.md](../builds-architecture.md), [../gear-simulation-full-chain-runbook.md](../gear-simulation-full-chain-runbook.md) |
| [2026-06-17-database-architecture-governance.md](2026-06-17-database-architecture-governance.md) | 已落地，现由 PostgreSQL-only 运行时取代 | [../database-architecture.md](../database-architecture.md) |
| [2026-06-18-pve-spec-ladder-ui-contract.md](2026-06-18-pve-spec-ladder-ui-contract.md) | 历史 UI / 数据契约 | [../roadmap.md](../roadmap.md), [../ui-style-guide.md](../ui-style-guide.md) |
| [2026-06-19-integrated-analysis-workbench-design.md](2026-06-19-integrated-analysis-workbench-design.md) | 部分落地，产品方向已拆分 | [../roadmap.md](../roadmap.md), [../simulator-simc-end-to-end.md](../simulator-simc-end-to-end.md) |
| [2026-06-21-parallel-optimization-control.md](2026-06-21-parallel-optimization-control.md) | 历史协调计划 | [../roadmap.md](../roadmap.md), [../roadmap/ideas.md](../roadmap/ideas.md) |
| [2026-06-22-gear-data-layer-goal-handoff.md](2026-06-22-gear-data-layer-goal-handoff.md) | 历史交接 | [../gear-database-governance.md](../gear-database-governance.md), [../gear-simulation-full-chain-runbook.md](../gear-simulation-full-chain-runbook.md) |
| [2026-06-22-gear-observed-variant-backfill.md](2026-06-22-gear-observed-variant-backfill.md) | 历史实施计划 | [../gear-database-governance.md](../gear-database-governance.md), [../gear-simulation-full-chain-runbook.md](../gear-simulation-full-chain-runbook.md) |
| [2026-06-22-talent-catalog-health-contract.md](2026-06-22-talent-catalog-health-contract.md) | 已落地为 health 契约 | [../talent-simulation-full-chain-runbook.md](../talent-simulation-full-chain-runbook.md), [../roadmap.md](../roadmap.md) |
| [2026-06-23-current-change-rollup.md](2026-06-23-current-change-rollup.md) | 历史汇总 | [../roadmap.md](../roadmap.md) |
| [2026-06-23-reused-dungeon-current-season-candidates.md](2026-06-23-reused-dungeon-current-season-candidates.md) | 历史审计 | [../gear-database-governance.md](../gear-database-governance.md), [../gear-simulation-full-chain-runbook.md](../gear-simulation-full-chain-runbook.md) |
| [2026-06-23-season-gear-instance-slice-plan.md](2026-06-23-season-gear-instance-slice-plan.md) | 历史切片计划 | [../gear-database-governance.md](../gear-database-governance.md), [../roadmap.md](../roadmap.md) |
| [2026-06-24-gear-enhancement-config-design.md](2026-06-24-gear-enhancement-config-design.md) | 已落地为装备强化模型 | [../gear-simulation-full-chain-runbook.md](../gear-simulation-full-chain-runbook.md), [../gear-database-governance.md](../gear-database-governance.md) |
| [2026-06-25-gear-database-implementation-plan-v2.md](2026-06-25-gear-database-implementation-plan-v2.md) | 历史实施计划 | [../gear-database-governance.md](../gear-database-governance.md) |
| [2026-06-25-midnight-crafted-gear-full-audit.md](2026-06-25-midnight-crafted-gear-full-audit.md) | 历史审计 | [../gear-database-governance.md](../gear-database-governance.md), [../gear-simulation-full-chain-runbook.md](../gear-simulation-full-chain-runbook.md) |
| [2026-06-25-midnight-preembellished-crafted-gear-ingestion.md](2026-06-25-midnight-preembellished-crafted-gear-ingestion.md) | 历史导入计划 | [../gear-database-governance.md](../gear-database-governance.md), [../gear-simulation-full-chain-runbook.md](../gear-simulation-full-chain-runbook.md) |
| [2026-06-26-gear-stat-simc-json-snapshot.md](2026-06-26-gear-stat-simc-json-snapshot.md) | 已落地为属性快照行为 | [../gear-simulation-full-chain-runbook.md](../gear-simulation-full-chain-runbook.md), [../builds-architecture.md](../builds-architecture.md) |
| [2026-06-26-spec-gear-display-and-stat-rules.md](2026-06-26-spec-gear-display-and-stat-rules.md) | 已落地为装备展示规则 | [../builds-architecture.md](../builds-architecture.md), [../gear-simulation-full-chain-runbook.md](../gear-simulation-full-chain-runbook.md) |
| [2026-06-26-spec-weapon-equipment-rules.md](2026-06-26-spec-weapon-equipment-rules.md) | 已落地为武器 / 装备规则 | [../gear-simulation-full-chain-runbook.md](../gear-simulation-full-chain-runbook.md), [../builds-architecture.md](../builds-architecture.md) |
| [2026-06-27-postgres-identity-migration-decision-record.md](2026-06-27-postgres-identity-migration-decision-record.md) | 已接受的决策记录 | [../database-architecture.md](../database-architecture.md), [../postgres-identity-migration-runbook.md](../postgres-identity-migration-runbook.md) |
| [2026-06-27-postgres-identity-migration-implementation-plan.md](2026-06-27-postgres-identity-migration-implementation-plan.md) | 历史分阶段计划，现由 PostgreSQL-only 运行时取代 | [../database-architecture.md](../database-architecture.md), [../postgres-identity-migration-runbook.md](../postgres-identity-migration-runbook.md) |
| [2026-06-29-admin-gate-visualization-design.md](2026-06-29-admin-gate-visualization-design.md) | 已落地为 admin gates 表面 | [../database-architecture.md](../database-architecture.md), [../remote-debugging.md](../remote-debugging.md) |
| [2026-07-01-data-loading-performance-design.md](2026-07-01-data-loading-performance-design.md) | 历史性能计划 | [../roadmap.md](../roadmap.md), [../database-architecture.md](../database-architecture.md) |
| [2026-07-03-postgres-only-cutover.md](2026-07-03-postgres-only-cutover.md) | 已落地的切换记录 | [../database-architecture.md](../database-architecture.md), [../postgres-identity-migration-runbook.md](../postgres-identity-migration-runbook.md) |
| [2026-07-03-wechat-ai-miniprogram-integration-research.md](2026-07-03-wechat-ai-miniprogram-integration-research.md) | 研究 / 后续方向 | [../roadmap/ideas.md](../roadmap/ideas.md) |
| [2026-07-04-community-template-incremental-refresh-design.md](2026-07-04-community-template-incremental-refresh-design.md) | 已落地为同步策略 | [../community-template-import-full-chain-runbook.md](../community-template-import-full-chain-runbook.md), [../roadmap.md](../roadmap.md) |
| [2026-07-05-gear-template-first-sync-incremental-design.md](2026-07-05-gear-template-first-sync-incremental-design.md) | 已落地为社区装备模板同步记录 | [../community-template-import-full-chain-runbook.md](../community-template-import-full-chain-runbook.md), [../gear-simulation-full-chain-runbook.md](../gear-simulation-full-chain-runbook.md) |
