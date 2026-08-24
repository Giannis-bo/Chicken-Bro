# 计划索引

只有“当前执行计划”表中的条目拥有执行权。不要按日期扫描本目录，也不要从目录存在、Git
历史或旧 release packet 恢复已归档阶段。稳定参考只解释现有实现边界，不是执行授权。

## 当前执行计划

| 领域 | 状态 | 入口 |
| --- | --- | --- |
| 14 路由 Target-First 生产重建与主干能力接入 | 正在推进 | [ui-reconstruction.md](ui-reconstruction.md) |
| 天赋模板闭环恢复与社区 winner 新鲜度 | 正在推进 | [2026-07-20-talent-template-recovery.md](2026-07-20-talent-template-recovery.md) |
| 装备模板保存、导入、清空与天赋 winner 投影 | 正在推进 | [2026-07-22-gear-template-projection.md](2026-07-22-gear-template-projection.md) |
| 社区装备 SimC 回填公平性与导入门禁 | 正在推进 | [2026-07-25-community-gear-backfill-fairness.md](2026-07-25-community-gear-backfill-fairness.md) |
| Taro 装备候选与强化编辑恢复 | 正在推进 | [设计](2026-07-24-taro-gear-editor-recovery-design.md) · [实施计划](2026-07-24-taro-gear-editor-recovery-implementation.md) |
| Manifest 装备详情与 Catalog Browse 完整性修复 | 正在推进 | [实施计划](2026-07-29-manifest-catalog-progression-display-contract.md) |
| 装备模拟端到端完整性验证 Goal | 暂缓 / `blocked`，等待获批 authority | [Goal 控制计划](2026-07-29-equipment-simulator-e2e-completeness-goal.md) |
| 装备模拟 Exact-first | 正在推进；`0030`--`0035` production foundation 为 `runtime_verified`，但首 source aggregate 为零，provider/worker 保持 disabled，ready path 继续 literal `blocked` | [当前顺序与边界](2026-08-04-equipment-simulator-exact-first-persistence-resequence.md) · [Runtime Authority 设计](2026-08-10-equipment-simulator-exact-first-task5c-runtime-authority-release-design.md) · [生产基础证据](../../artifacts/releases/2026-08-10-equipment-simulator-exact-first-production-foundation-deployment/evidence.json) |
| 当前赛季 PVE 装备 Universe 与逐项差集 | 暂缓 | [实施计划](2026-07-29-season-pve-universe-reconciliation.md) |
| S2 四类范围装备库完整闭环 | v73 已验证并发布到 Active Manifest generation 41；用户已确认最新微信预览可收尾，closure packet 对未单独录证的社区导入/登录态保存保留显式 waiver | [实施计划](2026-08-13-s2-official-api-fact-snapshot-implementation.md) · [closure evidence](../artifacts/releases/2026-08-24-s2-equipment-library-ui-closure/evidence.json)；Candidate 说明见 `server/data/midnight-season-2/README.md` |
| Observed Build Registry 与 80 槽 TemplateSet | 正在推进 | [设计](2026-07-23-observed-build-registry-design.md) · [核心切片](2026-07-23-observed-build-registry-core-implementation.md) · [共享玩家切换](2026-07-23-observed-build-registry-cutover-implementation.md) |
| builds_home 职业命令卡组 | 正在推进 | [builds-home-command-deck.md](builds-home-command-deck.md) |
| 炸鸡队长统一 ChatBot 与受控分析工具 | 正在推进；已交付表面、流式与已发布 Tool 的事实边界，Phase 3--5 仍未授权 | [后端架构](2026-07-24-chickenbro-chatbot-design.md) · [聊天表面设计](2026-08-01-chickenbro-chat-surface-design.md) · [聊天表面实施](2026-08-01-chickenbro-chat-surface-implementation.md) · [来源驱动 Agent](2026-08-01-chickenbro-source-agent-implementation.md) · [能力演化控制面](2026-08-02-chickenbro-capability-evolution-design.md) · [流式生产证据](../../artifacts/releases/2026-08-03-chickenbro-streaming-scroll/evidence.json) |
| 炸鸡队长 Smart Question Chain 与 Evidence Planner | 正在推进；Evidence Planner 的真实 WeChat 验收待办 | [Question Chain 设计](2026-08-03-chickenbro-smart-question-chain-design.md) · [实施计划](2026-08-03-chickenbro-smart-question-chain-implementation.md) · [Evidence Planner 设计](2026-08-04-chickenbro-evidence-planner-design.md) · [实施计划](2026-08-04-chickenbro-evidence-planner-implementation.md) · [公开网页 Tool 合同](2026-08-04-chickenbro-generic-public-web-research-tool.md) |
| SQLite 全面退役 | 下一步 | [退役设计](2026-08-02-sqlite-complete-retirement-design.md) |

## 稳定架构与交付基线

本节的链接是当前实现仍需引用的稳定设计或可复核交付证据；它们不重新打开已完成的
实施计划。

| 领域 | 状态 | 入口 |
| --- | --- | --- |
| 装备模拟长期目标合同 | 已完成 / 仍有效 | [目标架构](2026-07-28-equipment-simulator-target-architecture.md) |
| 至暗之夜 S2 有限 List A 与社区 Exact | v73 Candidate 执行与 Active Manifest generation 41 发布完成；后端浏览/导入/混合替换已 live verified；用户确认最新微信预览可收尾 | [当前设计](2026-08-13-s2-selectable-catalog-community-exact-design.md) · [closure evidence](../artifacts/releases/2026-08-24-s2-equipment-library-ui-closure/evidence.json) |
| S2 三件样本最短发布闭环 | 三样本 golden prefix 已纳入并由 v73 release packet 继承；正式指针已发布，范围仍为团本（包括巢穴）、大秘境、制造业和套装 | [三件样本设计](2026-08-14-s2-three-sample-release-closure-design.md) · [live smoke](../artifacts/releases/2026-08-21-s2-equipment-library-candidate-v73/live-smoke-v1.json) |
| 装等轨道规则输入 | 已完成 / 当前规则输入 | [Track Authority 纠偏](2026-07-28-equipment-simulator-track-authority-correction.md) |
| 至暗之夜 S2 End Game 已构建候选 | 历史 `blocked` / 无继续执行权；不得直接 promotion 或续跑 | [设计](../superpowers/specs/2026-08-12-midnight-season-2-data-repository-design.md) · [实施记录](../superpowers/plans/2026-08-12-midnight-season-2-data-repository.md) · [候选证据](../../artifacts/releases/2026-08-12-midnight-season-2-data-foundation/evidence.json) |
| Exact-first Runtime Authority 候选 | 已完成候选 / 未授权 activation | [Task 5C 证据](../../artifacts/releases/2026-08-10-equipment-simulator-exact-first-task5c-runtime-authority-release/evidence.json) |
| 炸鸡队长原生 Agent 运行边界 | 已完成 / 当前架构参考 | [设计](2026-08-04-chickenbro-agentic-research-design.md) · [发布证据](../../artifacts/releases/2026-08-05-chickenbro-native-agent/evidence.json) |
| Chickenbro Tool Registry Phase 1--2 | 已完成 / 归档证据 | [Phase 1](../../artifacts/releases/2026-08-02-chickenbro-observability-phase1/evidence.json) · [Phase 2](../../artifacts/releases/2026-08-02-chickenbro-tool-registry-phase2/evidence.json) |

此索引必须覆盖保留在 `docs/plans/` 的全部 Markdown 文件。新的多步骤计划先进入“当前执行计划”；
其中标为“待用户明确启动”的条目只拥有计划复核权，不能据此开始实现、联网、发布或切换；已启动条目仍
必须遵守各自的阶段边界。完成、停止
或被替代后，删除实施文档并把仍有现行价值的规则收敛到 architecture、runbook、roadmap 或上述稳定参考。
Git 历史与 release packet 承担过程归档。
