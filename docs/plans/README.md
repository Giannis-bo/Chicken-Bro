# 计划索引

只有“当前执行计划”表中的条目拥有顺序执行权。不要按日期扫描本目录，也不要从目录存在、Git
历史或旧 release packet 恢复已归档阶段。稳定参考只解释现有实现或迁移期回滚边界，不是执行授权。

当前实现只能由 [炸鸡队长与 SimC 双端架构](../chickenbro-simc-architecture.md) 解释，生产操作只能由
[生产迁移、切流与恢复 Runbook](../chickenbro-simc-production-runbook.md) 解锁，验证等级以
[Verification Matrix](../verification-matrix.md) 为准。旧计划中的命令、owner、route、schema 或服务名与这三份
权威冲突时，一律按 legacy factual baseline 处理，不得继续执行。

## 当前执行计划

| 阶段 | 状态 | 入口 |
| --- | --- | --- |
| 1. 控制面与精确清单 | `已完成`；逐文件清单、脱敏云端盘点、唯一架构/Runbook/owner 与 Phase 1 packet 已在 clean HEAD 通过 | [实施计划](../superpowers/plans/2026-09-02-chickenbro-simc-rebuild-01-control-plane.md) |
| 2. 干净数据面与 Identity | `本地已验证 / Candidate 阻塞`；schema/Identity/API security/dry-run 与云端隔离 dependency-loaded backend profile 已通过，真实 PG candidate 仍由容量和独立恢复 gate 阻止 apply 与 Phase 2 完成 | [实施计划](../superpowers/plans/2026-09-02-chickenbro-simc-rebuild-02-identity-data.md) |
| 3. 正式 Chat | `下一步`；Phase 2 身份/数据 owner 通过后执行 | [实施计划](../superpowers/plans/2026-09-02-chickenbro-simc-rebuild-03-chat.md) |
| 4. 正式 SimC | `下一步`；只使用云端 SimulationCraft，candidate 语义验证先于切流 | [实施计划](../superpowers/plans/2026-09-02-chickenbro-simc-rebuild-04-simc.md) |
| 5. 双端、迁移与切流 | `下一步`；容量、独立备份、candidate、真实双端验收和写栅栏全部通过后才可 apply | [实施计划](../superpowers/plans/2026-09-02-chickenbro-simc-rebuild-05-dual-client-migration-cutover.md) |
| 6. Legacy 退役 | `后续`；切流稳定、恢复验证和清理 manifest 无 blocker 后才可精确删除 | [实施计划](../superpowers/plans/2026-09-02-chickenbro-simc-rebuild-06-legacy-retirement.md) |

用户已确认书面规格并要求以持续 Goal 推进整体完成。该授权覆盖六个阶段，但不绕过阶段依赖：当前只有
Phase 2 本地实现、dry-run 和云端隔离 dependency-loaded backend profile 已验证；真实 PG candidate、切流和删除分别由各自 requirement、容量、备份、回滚、真实验收
和精确 manifest 解锁，不能提前 apply。

## 待退役文档索引（全部无当前执行权）

下表只用于定位仍需从现有实现抽取的事实、迁移期 last-known-good 和最终清理目标。它们全部被
2026-09-02 重构设计取代，不能继续实施、promotion 或扩展。

| 领域 | 状态 | 入口 |
| --- | --- | --- |
| 炸鸡队长与 SimC 双端精简平台骨架 | 已被当前重构设计取代；已有 v2 核心仅作为抽取与迁移输入 | [旧父级架构](../superpowers/specs/2026-09-01-chickenbro-simc-dual-client-architecture-design.md) · [旧平台骨架实施计划](../superpowers/plans/2026-09-01-chickenbro-simc-platform-foundation.md) |
| 炸鸡队长公网 Web 与小程序确认登录 | 已被当前重构设计取代；ticket/Cookie 边界保留为实现输入，候选和真实扫码仍不能冒充正式验收 | [旧设计](../superpowers/specs/2026-09-01-chickenbro-web-mini-login-design.md) · [旧实施计划](../superpowers/plans/2026-09-01-chickenbro-web-mini-login.md) · [旧候选隔离计划](../superpowers/plans/2026-09-02-chickenbro-web-login-candidate-isolation.md) |
| 炸鸡队长 Web prototype、Codex 对话与角色 SimC | 已被当前重构设计取代；prototype bypass、demo owner 和 prototype 数据明确待删除 | [旧设计](../superpowers/specs/2026-09-01-chickenbro-web-prototype-design.md) · [旧实施计划](../superpowers/plans/2026-09-01-chickenbro-web-prototype.md) |
| 14 路由 Target-First 生产重建与主干能力接入 | 暂缓；当前 14 路由仅作为迁移期 last-known-good，不再扩展 | [ui-reconstruction.md](ui-reconstruction.md) |
| 天赋模板闭环恢复与社区 winner 新鲜度 | 暂缓；目标产品已移除天赋模拟 | [2026-07-20-talent-template-recovery.md](2026-07-20-talent-template-recovery.md) |
| 装备模板保存、导入、清空与天赋 winner 投影 | 暂缓；目标产品已移除天赋/装备模拟 | [2026-07-22-gear-template-projection.md](2026-07-22-gear-template-projection.md) |
| 社区装备 SimC 回填公平性与导入门禁 | 暂缓；只保留历史边界，不再新增执行 | [2026-07-25-community-gear-backfill-fairness.md](2026-07-25-community-gear-backfill-fairness.md) |
| Taro 装备候选与强化编辑恢复 | 暂缓；只保留迁移期线上事实 | [设计](2026-07-24-taro-gear-editor-recovery-design.md) · [实施计划](2026-07-24-taro-gear-editor-recovery-implementation.md) |
| Manifest 装备详情与 Catalog Browse 完整性修复 | 暂缓；目标产品不再扩展 Catalog Browse | [实施计划](2026-07-29-manifest-catalog-progression-display-contract.md) |
| 装备模拟端到端完整性验证 Goal | 暂缓 / `blocked`，等待获批 authority | [Goal 控制计划](2026-07-29-equipment-simulator-e2e-completeness-goal.md) |
| 装备模拟 Exact-first | 暂缓；`0030`--`0035` production foundation 只保留为迁移期证据，provider/worker 继续 disabled | [当前顺序与边界](2026-08-04-equipment-simulator-exact-first-persistence-resequence.md) · [Runtime Authority 设计](2026-08-10-equipment-simulator-exact-first-task5c-runtime-authority-release-design.md) · [生产基础证据](../../artifacts/releases/2026-08-10-equipment-simulator-exact-first-production-foundation-deployment/evidence.json) |
| 当前赛季 PVE 装备 Universe 与逐项差集 | 暂缓 | [实施计划](2026-07-29-season-pve-universe-reconciliation.md) |
| S2 四类范围装备库完整闭环 | 暂缓；生产 v73 / Active Manifest generation 41 继续作为 last-known-good，不再 promotion 或扩展 | [当前设计](2026-08-13-s2-selectable-catalog-community-exact-design.md) · [Active closure](https://api.chickenbro.cloud/wow-evidence/releases/2026-08-24-s2-equipment-library-evidence-v2/artifacts/releases/2026-08-24-s2-equipment-library-ui-closure/evidence.json) · [freshness Candidate](../../artifacts/releases/2026-08-25-s2-freshness-rebase/evidence.json) |
| Observed Build Registry 与 80 槽 TemplateSet | 暂缓；目标产品不再消费该模板链 | [设计](2026-07-23-observed-build-registry-design.md) · [核心切片](2026-07-23-observed-build-registry-core-implementation.md) · [共享玩家切换](2026-07-23-observed-build-registry-cutover-implementation.md) |
| builds_home 职业命令卡组 | 暂缓；目标产品已移除构筑首页 | [builds-home-command-deck.md](builds-home-command-deck.md) |
| 炸鸡队长统一 ChatBot 与受控分析工具 | 被新父级架构替代；旧表面、流式和原生 Agent 证据仅供抽取参考，Phase 3--5 不再执行 | [后端架构](2026-07-24-chickenbro-chatbot-design.md) · [聊天表面设计](2026-08-01-chickenbro-chat-surface-design.md) · [聊天表面实施](2026-08-01-chickenbro-chat-surface-implementation.md) · [来源驱动 Agent](2026-08-01-chickenbro-source-agent-implementation.md) · [能力演化控制面](2026-08-02-chickenbro-capability-evolution-design.md) · [流式生产证据](../../artifacts/releases/2026-08-03-chickenbro-streaming-scroll/evidence.json) |
| 炸鸡队长 Smart Question Chain 与 Evidence Planner | 暂缓；新主链采用 Codex-only，不继续扩展规则树和逐 claim 门禁 | [Question Chain 设计](2026-08-03-chickenbro-smart-question-chain-design.md) · [实施计划](2026-08-03-chickenbro-smart-question-chain-implementation.md) · [Evidence Planner 设计](2026-08-04-chickenbro-evidence-planner-design.md) · [实施计划](2026-08-04-chickenbro-evidence-planner-implementation.md) · [公开网页 Tool 合同](2026-08-04-chickenbro-generic-public-web-research-tool.md) |
| SQLite 全面退役 | 并入新平台骨架与最终 legacy 删除，不单独推进 | [退役设计](2026-08-02-sqlite-complete-retirement-design.md) |

## 稳定架构与交付基线

本节的链接是当前实现仍需引用的稳定设计或可复核交付证据；它们不重新打开已完成的
实施计划。

| 领域 | 状态 | 入口 |
| --- | --- | --- |
| 装备模拟长期目标合同 | 已完成 / 仍有效 | [目标架构](2026-07-28-equipment-simulator-target-architecture.md) |
| 至暗之夜 S2 有限 List A 与社区 Exact | v73 / Active generation 41 发布完成；后端浏览/导入/混合替换已 live verified；用户 acceptance 与 waiver 按 closure packet 保留 | [当前设计](2026-08-13-s2-selectable-catalog-community-exact-design.md) · [Active closure](https://api.chickenbro.cloud/wow-evidence/releases/2026-08-24-s2-equipment-library-evidence-v2/artifacts/releases/2026-08-24-s2-equipment-library-ui-closure/evidence.json) |
| 至暗之夜 S2 freshness Candidate | `Candidate` / dormant；30555 replay、416-item snapshot、Talent Catalog 与 Candidate Manifest 已验证，未切换 Active。证据中的 30555 是候选运行时，不是当前生产运行时 | [freshness evidence](../../artifacts/releases/2026-08-25-s2-freshness-rebase/evidence.json) |
| S2 三件样本最短发布闭环 | 三样本 golden prefix 已纳入并由 v73 release packet 继承；正式指针已发布，范围仍为团本（包括巢穴）、大秘境、制造业和套装 | [三件样本设计](2026-08-14-s2-three-sample-release-closure-design.md) · [live smoke](https://api.chickenbro.cloud/wow-evidence/releases/2026-08-24-s2-equipment-library-evidence-v2/artifacts/releases/2026-08-21-s2-equipment-library-candidate-v73/live-smoke-v1.json) |
| 装等轨道规则输入 | 已完成 / 当前规则输入 | [Track Authority 纠偏](2026-07-28-equipment-simulator-track-authority-correction.md) |
| 至暗之夜 S2 End Game 已构建候选 | 历史 `blocked` / 无继续执行权；不得直接 promotion 或续跑 | [设计](../superpowers/specs/2026-08-12-midnight-season-2-data-repository-design.md) · [实施记录](../superpowers/plans/2026-08-12-midnight-season-2-data-repository.md) · [候选证据](../../artifacts/releases/2026-08-12-midnight-season-2-data-foundation/evidence.json) |
| S2 官方 API 事实快照阶段 1 | 历史 `blocked` / 已停止；v8 raw 与 bounded probes 只保留为字段级证据，不拥有当前执行或 promotion 权限 | [阶段 1 实施记录](2026-08-13-s2-official-api-fact-snapshot-implementation.md) |
| Exact-first Runtime Authority 候选 | 已完成候选 / 未授权 activation | [Task 5C 证据](../../artifacts/releases/2026-08-10-equipment-simulator-exact-first-task5c-runtime-authority-release/evidence.json) |
| 炸鸡队长原生 Agent 运行边界 | 已完成 / 当前架构参考 | [设计](2026-08-04-chickenbro-agentic-research-design.md) · [发布证据](../../artifacts/releases/2026-08-05-chickenbro-native-agent/evidence.json) |
| Chickenbro Tool Registry Phase 1--2 | 已完成 / 归档证据 | [Phase 1](../../artifacts/releases/2026-08-02-chickenbro-observability-phase1/evidence.json) · [Phase 2](../../artifacts/releases/2026-08-02-chickenbro-tool-registry-phase2/evidence.json) |

此索引必须覆盖保留在 `docs/plans/` 的全部 Markdown 文件。当前六份计划按阶段顺序执行；后续阶段在前置
门禁未闭合时只有计划权，不能据此提前发布、切换、迁移或删除。完成、停止或被替代后，删除实施文档并把仍有现行价值的规则收敛到 architecture、runbook、
roadmap 或上述稳定参考。Git 历史与 release packet 承担过程归档。
