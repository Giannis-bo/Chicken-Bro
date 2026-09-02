# 计划白名单

只有下列六份计划拥有当前执行权。不要按日期扫描目录，也不要从 Git 历史或旧 release packet 恢复被取代的方案。稳定架构由 [当前架构](../chickenbro-simc-architecture.md) 解释，生产操作由 [生产 Runbook](../chickenbro-simc-production-runbook.md) 解锁，证据等级由 [验证矩阵](../verification-matrix.md) 决定。

| 阶段 | 状态 | 计划 |
| --- | --- | --- |
| 1. 控制面与精确清单 | `已完成` | [实施计划](../superpowers/plans/2026-09-02-chickenbro-simc-rebuild-01-control-plane.md) |
| 2. 干净数据面与 Identity | `本地已验证 / Candidate apply 阻塞` | [实施计划](../superpowers/plans/2026-09-02-chickenbro-simc-rebuild-02-identity-data.md) |
| 3. 正式 Chat | `本地已验证` | [实施计划](../superpowers/plans/2026-09-02-chickenbro-simc-rebuild-03-chat.md) |
| 4. 正式 SimC | `本地已验证` | [实施计划](../superpowers/plans/2026-09-02-chickenbro-simc-rebuild-04-simc.md) |
| 5. 双端、迁移与切流 | `本地已验证 / Live 验收阻塞` | [实施计划](../superpowers/plans/2026-09-02-chickenbro-simc-rebuild-05-dual-client-migration-cutover.md) |
| 6. Legacy 退役 | `正在推进清单闭环 / Apply 锁定` | [实施计划](../superpowers/plans/2026-09-02-chickenbro-simc-rebuild-06-legacy-retirement.md) |

用户对整体目标的授权不绕过阶段依赖。Candidate、生产切流和本地/云端删除分别由容量、独立恢复、迁移核对、真实用户验收、稳定健康和精确 manifest 解锁。
