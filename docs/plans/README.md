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
| 装备模拟 Exact-first 与三来源 Catalog | 正在推进（Task 3A 已完成收尾：历史 candidate `t3a260805163536` 仍为 `runtime_verified`，closure `pending`；Task 4P/4L pure-domain 已归档。Task 3B 的先前 cloud PostgreSQL candidate 因后续 direct-server import 修复失效，当前为 `local_verified`，必须以新隔离资源复验 final HEAD；2026-08-06 用户授权已清理 /var/tmp 下归档的 Task 3A/3B candidate source/bundle/output，根盘余量约 5.6 GiB，候选数据库保留 non-reusable；新的 candidate 仍待执行；没有 production migration、runtime consumer 或用户可见动作，generation 35 未改写；4W、5A、6C 和任何用户可见/生产动作仍未授权） | [设计](2026-08-04-equipment-simulator-exact-first-catalog-design.md) · [原实施计划](2026-08-04-equipment-simulator-exact-first-implementation.md) · [持久化与运行链重排](2026-08-04-equipment-simulator-exact-first-persistence-resequence.md) · [Task 4L plan](2026-08-06-equipment-simulator-exact-first-task4l-loadout-effect-authority.md) · [Task 3A evidence](../../artifacts/releases/2026-08-04-equipment-simulator-exact-first/evidence.json) · [Task 4P evidence](../../artifacts/releases/2026-08-05-equipment-simulator-exact-first-task4p/evidence.json) · [Task 4L evidence](../../artifacts/releases/2026-08-06-equipment-simulator-exact-first-task4l/evidence.json) · [Task 3B evidence](../../artifacts/releases/2026-08-06-equipment-simulator-exact-first-task3b/evidence.json) |
| 装备模拟 Canonical Kernel 重设计 | 已完成（pure foundation + source_change_control_only；不含 runtime/release） | [重设计](2026-08-04-equipment-simulator-canonical-kernel-redesign.md) · [已停止的原实施计划](2026-08-04-equipment-simulator-canonical-kernel-implementation.md) · [owner change-control](2026-08-04-equipment-simulator-canonical-owner-change-control.md) · [重复 effect subject 纠偏](2026-08-04-equipment-simulator-duplicate-effect-subject-correction.md) |
| WebSim / stat-weight 定时同步日志有界化 | 已完成 | [实施计划](2026-07-29-sync-log-bounding.md) · [live evidence](../../artifacts/releases/2026-07-29-sync-log-bounding/evidence.json) |
| 当前赛季 PVE 装备 Universe 与逐项差集 | 暂缓 | [实施计划](2026-07-29-season-pve-universe-reconciliation.md) |
| 当前赛季 PVE Journal 静默遗漏门禁 | 已完成 | [实施计划](2026-07-29-season-pve-journal-omission-guard.md) · [live evidence](../../artifacts/releases/2026-07-29-season-pve-journal-omission-guard/evidence.json) |
| Observed Build Registry 与 80 槽 TemplateSet 重构 | 正在推进 | [设计](2026-07-23-observed-build-registry-design.md) · [核心切片实施计划](2026-07-23-observed-build-registry-core-implementation.md) · [共享玩家切换计划](2026-07-23-observed-build-registry-cutover-implementation.md) |
| builds_home 职业命令卡组 | 正在推进 | [builds-home-command-deck.md](builds-home-command-deck.md) |
| 炸鸡队长统一 ChatBot 与受控分析工具 | 正在推进（Phase 2 已归档；流式交互生产已验证；能力演化 Phase 3–5 未授权） | [后端架构](2026-07-24-chickenbro-chatbot-design.md) · [Phase 1 极简聊天表面](2026-08-01-chickenbro-chat-surface-design.md) · [聊天表面实施计划](2026-08-01-chickenbro-chat-surface-implementation.md) · [来源驱动 Agent 实施计划](2026-08-01-chickenbro-source-agent-implementation.md) · [流式体验设计](2026-08-03-chickenbro-streaming-scroll-design.md) · [流式体验实施计划](2026-08-03-chickenbro-streaming-scroll-implementation.md) · [生产证据](../../artifacts/releases/2026-08-03-chickenbro-streaming-scroll/evidence.json) · [能力演化控制面设计](2026-08-02-chickenbro-capability-evolution-design.md) · [能力演化 Phase 1 实施计划](2026-08-02-chickenbro-observability-phase1-implementation.md) |
| 炸鸡队长 Smart Question Chain | 正在推进（补充通用公开网页研究 Tool；真实 WeChat 验收仍待办） | [设计](2026-08-03-chickenbro-smart-question-chain-design.md) · [实施计划](2026-08-03-chickenbro-smart-question-chain-implementation.md) · [Evidence Planner 设计](2026-08-04-chickenbro-evidence-planner-design.md) · [Evidence Planner 实施计划](2026-08-04-chickenbro-evidence-planner-implementation.md) · [通用网页 Tool 合同](2026-08-04-chickenbro-generic-public-web-research-tool.md) · [自主研究循环设计](2026-08-04-chickenbro-agentic-research-design.md) · [自主研究循环实施计划](2026-08-04-chickenbro-agentic-research-loop-implementation.md) |
| 炸鸡队长 Codex 自主研究循环 | 已完成（用户验收原生 Codex Agent 的强度问答、跨问题追问与长对话输入区；main、正式部署和普通/流式 smoke 均已记录） | [设计](2026-08-04-chickenbro-agentic-research-design.md) · [实施计划](2026-08-04-chickenbro-agentic-research-loop-implementation.md) · [发布证据](../../artifacts/releases/2026-08-05-chickenbro-native-agent/evidence.json) · [通用网页 Tool 合同](2026-08-04-chickenbro-generic-public-web-research-tool.md) |
| SQLite 全面退役 | 下一步 | [退役设计](2026-08-02-sqlite-complete-retirement-design.md) |

## 已确认方向（未授权实施）

| 领域 | 状态 | 入口 |
| --- | --- | --- |

## 稳定目标与归档基线

本节只提供长期目标和已完成基线的可达入口，不授予执行权，也不把后续缺陷纠偏或 UI
验收包装成已归档阶段的续跑。

| 领域 | 状态 | 入口 |
| --- | --- | --- |
| 装备模拟长期目标合同 | 已完成 | [目标架构](2026-07-28-equipment-simulator-target-architecture.md) |
| 装备模拟 v1 基线 | 已完成 | [Phase 4 归档证据](../../artifacts/releases/2026-07-29-equipment-simulator-phase4-manifest-cutover/evidence.json) · [Track Authority 规则输入](2026-07-28-equipment-simulator-track-authority-correction.md) · [Phase 3 归档证据](../../artifacts/releases/2026-07-29-equipment-simulator-phase3-resolved-snapshot/evidence.json) · [Phase 2 归档证据](../../artifacts/releases/2026-07-29-equipment-simulator-phase2-exact-enhancement/evidence.json) · [Phase 1 归档证据](../../artifacts/releases/2026-07-29-equipment-simulator-phase1-catalog-contract/evidence.json) · [Phase 0 归档证据](../../artifacts/releases/2026-07-28-equipment-simulator-phase0-unblock/evidence.json) |
| 炸鸡队长 Tool Registry Phase 2 基线 | 已完成 | [设计](2026-08-02-chickenbro-tool-registry-phase2-design.md) · [实施记录](2026-08-02-chickenbro-tool-registry-phase2-implementation.md) · [归档证据](../../artifacts/releases/2026-08-02-chickenbro-tool-registry-phase2/evidence.json) |

新的多步骤计划必须先在“当前执行计划”登记。计划完成或被替代后，从当前执行表移除；
稳定结论进入 architecture、runbook、roadmap 或本页明确标注为无执行权的稳定参考。
