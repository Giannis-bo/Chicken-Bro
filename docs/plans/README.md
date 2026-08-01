# 计划索引

只有“当前执行计划”表中的条目拥有执行权。不要按日期扫描本目录，也不要从目录存在、Git
历史、旧 release packet 或下方稳定参考恢复已归档阶段。

## 当前执行计划

| 领域 | 状态 | 入口 |
| --- | --- | --- |
| 14 路由 Target-First 生产重建与主干能力接入 | 正在推进 | [ui-reconstruction.md](ui-reconstruction.md) |
| 天赋模板闭环恢复与社区 winner 新鲜度 | 正在推进 | [2026-07-20-talent-template-recovery.md](2026-07-20-talent-template-recovery.md) |
| 装备模板保存、导入、清空与天赋 winner 投影 | 正在推进 | [2026-07-22-gear-template-projection.md](2026-07-22-gear-template-projection.md) |
| 社区装备 SimC 回填公平性与导入门禁 | 正在推进 | [2026-07-25-community-gear-backfill-fairness.md](2026-07-25-community-gear-backfill-fairness.md) |
| Taro 装备候选与强化编辑恢复 | 正在推进 | [设计](2026-07-24-taro-gear-editor-recovery-design.md) · [实施计划](2026-07-24-taro-gear-editor-recovery-implementation.md) |
| 装备强化资格与已确认标记对齐 | 正在推进 | [实施计划](2026-07-29-gear-enhancement-rule-alignment.md) |
| Manifest 装备详情与 Catalog Browse 完整性修复 | 正在推进 | [实施计划](2026-07-29-manifest-catalog-progression-display-contract.md) |
| 装备模拟端到端完整性验证 Goal | 暂缓 | [Goal 控制计划](2026-07-29-equipment-simulator-e2e-completeness-goal.md) |
| WebSim / stat-weight 定时同步日志有界化 | 已完成 | [实施计划](2026-07-29-sync-log-bounding.md) · [live evidence](../../artifacts/releases/2026-07-29-sync-log-bounding/evidence.json) |
| 当前赛季 PVE 装备 Universe 与逐项差集 | 暂缓 | [实施计划](2026-07-29-season-pve-universe-reconciliation.md) |
| 当前赛季 PVE Journal 静默遗漏门禁 | 已完成 | [实施计划](2026-07-29-season-pve-journal-omission-guard.md) · [live evidence](../../artifacts/releases/2026-07-29-season-pve-journal-omission-guard/evidence.json) |
| Observed Build Registry 与 80 槽 TemplateSet 重构 | 正在推进 | [设计](2026-07-23-observed-build-registry-design.md) · [核心切片实施计划](2026-07-23-observed-build-registry-core-implementation.md) · [共享玩家切换计划](2026-07-23-observed-build-registry-cutover-implementation.md) |
| builds_home 职业命令卡组 | 正在推进 | [builds-home-command-deck.md](builds-home-command-deck.md) |
| 炸鸡队长统一 ChatBot 与受控分析工具 | 下一步 | [2026-07-24-chickenbro-chatbot-design.md](2026-07-24-chickenbro-chatbot-design.md) |

## 稳定目标与归档基线

本节只提供长期目标和已完成基线的可达入口，不授予执行权，也不把后续缺陷纠偏或 UI
验收包装成已归档阶段的续跑。

| 领域 | 状态 | 入口 |
| --- | --- | --- |
| 装备模拟长期目标合同 | 已完成 | [目标架构](2026-07-28-equipment-simulator-target-architecture.md) |
| 装备模拟 v1 基线 | 已完成 | [Phase 4 归档证据](../../artifacts/releases/2026-07-29-equipment-simulator-phase4-manifest-cutover/evidence.json) · [Track Authority 规则输入](2026-07-28-equipment-simulator-track-authority-correction.md) · [Phase 3 归档证据](../../artifacts/releases/2026-07-29-equipment-simulator-phase3-resolved-snapshot/evidence.json) · [Phase 2 归档证据](../../artifacts/releases/2026-07-29-equipment-simulator-phase2-exact-enhancement/evidence.json) · [Phase 1 归档证据](../../artifacts/releases/2026-07-29-equipment-simulator-phase1-catalog-contract/evidence.json) · [Phase 0 归档证据](../../artifacts/releases/2026-07-28-equipment-simulator-phase0-unblock/evidence.json) |

新的多步骤计划必须先在“当前执行计划”登记。计划完成或被替代后，从当前执行表移除；
稳定结论进入 architecture、runbook、roadmap 或本页明确标注为无执行权的稳定参考。
