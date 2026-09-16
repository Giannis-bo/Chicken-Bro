# 文档地图

当前产品：Web Chat、云端 SimC、QQ 网站登录。按使用、开发和运营场景选择入口。

| 要做的事 | 入口与职责 |
| --- | --- |
| 使用产品 | [使用指南](user-guide.md)：登录、对话、历史与模拟 |
| 了解当前方向 | [路线图](roadmap.md)：已完成能力、持续改进与后续事项 |
| 确认任务范围 | [计划白名单](plans/README.md)：持续工作流、跟进事项与已落地能力 |
| 查精确状态与证据 | [项目状态](project-state.json)：按事项定位交付身份、验证和恢复记录 |
| 开发或验证 | [开发指南](development.md)：入口和命令；[验证矩阵](verification-matrix.md)：按影响选检查 |
| 理解实现 | [架构](chickenbro-simc-architecture.md)、[项目 owners](project-owner-map.json)、[后端 owners](backend-owner-map.json) |
| 发布或恢复 | [生产 Runbook](chickenbro-simc-production-runbook.md)；[测试环境](test-account-login.md) |
| 自动修复反馈 | [Badcase 工作流](plans/2026-09-08-badcase-workflow.md)、[执行说明](badcase-workflow-operations.md)、[证据合同](badcase-evidence-contract.md) |
| 核对控制面 | [Harness](harness.md)：检查工具与机器合同 |

## 状态记录怎么读

`project-state.json` 是机器兼容的事实账本，保留了历史字段，不能通读后将所有授权叠加。`targetProduct` 描述当前产品，`executionAuthority` 指向执行入口；`incrementalWork` 和相关事项给出各批次证据。`delivery`、`gates`、`refactorEvidence`、`productRelease` 与 `historicalRebuild` 中注明的历史范围不授权新操作。运行身份在操作前重新核对。

## 文档维护规则

- 工作流写通用步骤、合同、权限、验收及停止条件，不追加具体题目、会话引用、单次例外或逐轮消耗。
- 路线图写确认的方向；活动计划写本任务范围和结果；精确证据、授权凭据与预算写对应记录。声明本地、Candidate、线上、用户验收和恢复时分别给依据。
- 同一规则只在职责文档维护，其他入口引用。改标题或拆分内容时检查链接，并登记新增文件的 owner 与保留规则。
- 历史计划、发布包和恢复证明保留原记录，通过[历史索引](plans/README-history-20260911.md)按需查阅；原记录保留各批次的条件、结果与验证范围。
