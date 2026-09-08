# 计划白名单

只有下列六份重构计划及用户确认的后续任务计划拥有当前执行权。不要按日期扫描目录，也不要从 Git 历史或旧 release packet 恢复被取代的方案。稳定架构由 [当前架构](../chickenbro-simc-architecture.md) 解释，生产操作由 [生产 Runbook](../chickenbro-simc-production-runbook.md) 解锁，证据等级由 [验证矩阵](../verification-matrix.md) 决定。

| 阶段 | 状态 | 计划 |
| --- | --- | --- |
| 1. 控制面与精确清单 | `已完成` | [实施计划](../superpowers/plans/2026-09-02-chickenbro-simc-rebuild-01-control-plane.md) |
| 2. 干净数据面与 Identity | `正在推进 / 白名单恢复已验证` | [实施计划](../superpowers/plans/2026-09-02-chickenbro-simc-rebuild-02-identity-data.md) |
| 3. 正式 Chat | `本地已验证` | [实施计划](../superpowers/plans/2026-09-02-chickenbro-simc-rebuild-03-chat.md) |
| 4. 正式 SimC | `本地已验证` | [实施计划](../superpowers/plans/2026-09-02-chickenbro-simc-rebuild-04-simc.md) |
| 5. 双端、迁移与切流 | `本地已验证 / Live 验收阻塞` | [实施计划](../superpowers/plans/2026-09-02-chickenbro-simc-rebuild-05-dual-client-migration-cutover.md) |
| 6. Legacy 退役 | `容量预清理已解锁 / 完整 Apply 锁定` | [实施计划](../superpowers/plans/2026-09-02-chickenbro-simc-rebuild-06-legacy-retirement.md) |

用户对整体目标的授权不绕过阶段依赖。Candidate、生产切流和本地/云端删除分别由容量、独立恢复、迁移核对、真实用户验收、稳定健康和精确 manifest 解锁。

## 用户确认的后续任务

- `正在推进`：[Web 插画主题](2026-09-07-web-illustration-themes.md)，七主题已发布；2026-09-08 用户确认将七张插画迁移至现有 COS/CDN，正在验证加速效果。
- `已完成`：[Web 删除会话](2026-09-07-chat-delete.md)，用户确认垃圾桶入口、二次确认、软删除及正在回复保护。

- `已完成`：[同账号单个活动回复](2026-09-07-chat-account-limit.md)，用户确认 Mini/Web 同账号同时仅允许一个生成中的回复，其他发送明确提示等待。

- `已完成`：[双端聊天过程与时间](2026-09-07-chat-progress-timing.md)，用户确认公开摘要流式展开、结束折叠、回复完成时间与耗时及历史恢复。

- `正在推进`：[双端账号头像](2026-09-07-shared-account-avatar.md)，用户确认在小程序主动选择，Mini/Web 共用且可跳过。

- `正在推进`：[未登录 Web 首页](2026-09-07-web-login-home.md)，2026-09-07 用户要求重做未登录首页并在右上角展示完整登录二维码。

- `正在推进`：[小程序移动端交互优化](2026-09-07-mini-mobile-interaction.md)，2026-09-07 用户授权整体优化 Mini，后续扩展为模拟能力对齐及双端版本文案统一；最新范围和本地提交检查见计划末尾。

- `正在推进`：[全职业 SimC 国服名称](2026-09-06-simc-localization.md)，2026-09-06 用户批准版本化名称库、服务端统一解析及全专精覆盖验证方案。

- `正在推进`：[SimC 模拟工作台](2026-09-06-simc-workbench.md)，2026-09-06 用户已授权实施。
- `正在推进`：[鸡哥 SimC 工具](2026-09-06-chickenbro-simc-tools.md)，测试部署与真实四项模拟已验证，待用户验收。

- `正在推进`：[鸡哥研究质量](2026-09-06-chickenbro-research-quality.md)，2026-09-06 用户已授权实施。

- `正在推进`：[测试账号快捷登录](2026-09-05-test-account-login.md)，2026-09-05 用户已授权实施。
- `正在推进`：[炸鸡队长运行规则](2026-09-05-chickenbro-agent-rules.md)，2026-09-05 用户已授权实施。

- `已完成`：[WCL 历史战斗天赋](2026-09-08-wcl-fight-talents.md)，正式发布及真实任务验证通过，用户接受并授权合入仓库。
