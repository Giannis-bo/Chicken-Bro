# 计划白名单

1.0 当前实现已于 2026-09-08 获用户整体验收，见 [版本说明](../releases/1.0.md)。下列计划的已交付范围统一收尾；尚未实现的历史设想、平台公开发布和运维调查不因整体验收而自动完成。后续变更必须获得新的用户授权。只有本索引列出的计划可用于追溯已确认范围。不要按日期扫描目录，也不要从 Git 历史或旧 release packet 恢复被取代的方案。稳定架构由 [当前架构](../chickenbro-simc-architecture.md) 解释，生产操作由 [生产 Runbook](../chickenbro-simc-production-runbook.md) 解锁，证据等级由 [验证矩阵](../verification-matrix.md) 决定。

| 阶段 | 状态 | 计划 |
| --- | --- | --- |
| 1. 控制面与精确清单 | `已完成` | [实施计划](../superpowers/plans/2026-09-02-chickenbro-simc-rebuild-01-control-plane.md) |
| 2. 干净数据面与 Identity | `已完成 / 历史迁移已核对` | [实施计划](../superpowers/plans/2026-09-02-chickenbro-simc-rebuild-02-identity-data.md) |
| 3. 正式 Chat | `已完成 / 已验收范围` | [实施计划](../superpowers/plans/2026-09-02-chickenbro-simc-rebuild-03-chat.md) |
| 4. 正式 SimC | `已完成 / 已验收范围` | [实施计划](../superpowers/plans/2026-09-02-chickenbro-simc-rebuild-04-simc.md) |
| 5. 双端、迁移与切流 | `已完成 / accepted_write` | [实施计划](../superpowers/plans/2026-09-02-chickenbro-simc-rebuild-05-dual-client-migration-cutover.md) |
| 6. Legacy 退役 | `已完成 / 旧系统已退役` | [实施计划](../superpowers/plans/2026-09-02-chickenbro-simc-rebuild-06-legacy-retirement.md) |

用户对整体目标的授权不绕过阶段依赖。Candidate、生产切流和本地/云端删除分别由容量、独立恢复、迁移核对、真实用户验收、稳定健康和精确 manifest 解锁。

## 用户确认的后续任务

- `已完成`：[Web 插画主题](2026-09-07-web-illustration-themes.md)，七主题及 COS/CDN 加速已发布，2026-09-08 用户明确验收并授权合入。
- `已完成`：[Web 删除会话](2026-09-07-chat-delete.md)，用户确认垃圾桶入口、二次确认、软删除及正在回复保护。

- `已完成`：[同账号单个活动回复](2026-09-07-chat-account-limit.md)，用户确认 Mini/Web 同账号同时仅允许一个生成中的回复，其他发送明确提示等待。

- `已完成`：[双端聊天过程与时间](2026-09-07-chat-progress-timing.md)，用户确认公开摘要流式展开、结束折叠、回复完成时间与耗时及历史恢复。

- `已完成 / 1.0 已交付范围`：[双端账号头像](2026-09-07-shared-account-avatar.md)，历史头像保存与 Web 显示能力保留；最新 Mini 界面已取消头像选择入口。

- `已完成 / 1.0 已交付范围`：[未登录 Web 首页](2026-09-07-web-login-home.md)，2026-09-07 用户要求重做未登录首页并在右上角展示完整登录二维码。

- `已完成 / 1.0 已交付范围`：[小程序移动端交互优化](2026-09-07-mini-mobile-interaction.md)，2026-09-07 用户授权整体优化 Mini，后续扩展为模拟能力对齐及双端版本文案统一；最新范围和本地提交检查见计划末尾。

- `已完成 / 1.0 已交付范围`：[全职业 SimC 国服名称](2026-09-06-simc-localization.md)，2026-09-06 用户批准版本化名称库、服务端统一解析及全专精覆盖验证方案。

- `已完成 / 1.0 已交付范围`：[SimC 模拟工作台](2026-09-06-simc-workbench.md)，2026-09-06 用户已授权实施。
- `已完成 / 1.0 已交付范围`：[鸡哥 SimC 工具](2026-09-06-chickenbro-simc-tools.md)，已有部署与真实模拟验证，当前实现获 1.0 整体验收。

- `已完成 / 1.0 已交付范围`：[鸡哥研究质量](2026-09-06-chickenbro-research-quality.md)，2026-09-06 用户已授权实施。

- `已完成 / 1.0 已交付范围`：[测试账号快捷登录](2026-09-05-test-account-login.md)，2026-09-05 用户已授权实施。
- `已完成 / 1.0 已交付范围`：[炸鸡队长运行规则](2026-09-05-chickenbro-agent-rules.md)，2026-09-05 用户已授权实施。

- `已完成`：[WCL 历史战斗天赋](2026-09-08-wcl-fight-talents.md)，正式发布及真实任务验证通过，用户接受并授权合入仓库。

最新产品决定：小程序“账号与外观”面板取消，仅保留 FAQ 与更新日志；历史计划中的主题/主动退出对齐要求被此决定取代。源码收尾与微信公开发布分别记录。

- `正在推进`：2026-09-08 用户授权 1.0 最终发布：双端新增 9 月 8 日上线日志，合入提交并发布最新 Web、上传 Mini，核对后端源码一致性；微信平台审核/公开发布须按实际状态记录。见 [1.0 说明](../releases/1.0.md)。
