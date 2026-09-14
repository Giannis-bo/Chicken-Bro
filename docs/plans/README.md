# 计划白名单

本索引区分持续工作流、当前授权任务与历史交付。只有当前用户授权的范围可以继续执行；计划、旧状态、历史发布及单次例外均不产生新增授权。不要通过遍历旧计划寻找待执行任务。

## 持续工作流

- [Badcase 自动修复](2026-09-08-badcase-workflow.md)：通用工具修复、有界验证和条件发布；命令及证据见[执行说明](../badcase-workflow-operations.md)。
- [开发](../development.md)、[验证](../verification-matrix.md)、[生产操作](../chickenbro-simc-production-runbook.md)：按当前任务影响选用，不重放历史迁移流程。

## 当前任务与后续

| 状态 | 范围 | 记录 |
| --- | --- | --- |
| 后续 | 有限修复后的资料及外部条件缺口；不把历史 Goal 完成当作全部泛化完成 | [剩余事项](2026-09-11-remaining-issues-status.md) |
| 后续 | 已登记私有副本的到期处置；未到期不删除，不重置保留时钟 | [收尾与恢复条件](../../artifacts/verification/2026-09-11-project-closure/README.md) |

## 已完成与历史追溯

- `已完成 / 已合入推送并发布`：[鸡哥直接结论表达](2026-09-13-direct-conclusions.md)，核心、WCL及答案修正路径禁止无关防御性陈述；Candidate7条、独立修正及线上4条通过，运行源码730882f2。

- `已完成 / 评测未达提速门槛`：[复杂研究效率配对基准](2026-09-12-agent-performance-benchmark.md)，固定资料与真实链路、质量优先，不授权自动修改生产行为。

- `已完成 / 已合入推送并发布`：[鸡哥按需流程与核心规则精简](2026-09-12-agent-skills.md)，2026-09-12 用户批准实施、提交、合入和发布。

- `已完成 / 已合入推送并发布`：[通用研究证据与语义优化](2026-09-11-research-generalization.md)，五项优化、固定评测及隔离/线上验证。

当前功能和合同见[架构](../chickenbro-simc-architecture.md)，交付身份与分层验证见[项目状态](../project-state.json)。下列计划只用于查询其已确认范围、证据及限制，不是新的执行队列。

| 范围 | 计划 |
| --- | --- |
| Web/QQ 与小程序退役 | [QQ 登录](2026-09-09-web-only-qq.md)、[限定清理](2026-09-09-mini-retirement.md) |
| Chat 研究 | [有限研究完整解答](2026-09-11-research-completion.md)、[跨轮预算](2026-09-11-persistent-research-budget.md)、[有界研究与搜索](2026-09-10-bounded-research.md)、[WCL 效率](2026-09-10-wcl-tool-efficiency.md) |
| Chat 交付 | [持久化生成](2026-09-09-g2-durable-generation.md)、[截图](2026-09-09-chat-images.md)、[回答反馈](2026-09-08-chat-feedback.md) |
| 模拟与运营 | [场景实验](2026-09-09-simc-scenario-experiments.md)、[专精支持](2026-09-09-simc-all-specs.md)、[运营后台](2026-09-09-admin-ops.md) |
| 早期功能、六阶段重构与有限实验 | [完整历史索引](README-history-20260911.md)、[1.0 说明](../releases/1.0.md) |

历史索引保留原白名单的全部引用。旧 Mini 构建、微信审核/上传、双端迁移及无备份清理授权只属于历史范围；未验证项和旧失败不能因文档归档而改判完成。
