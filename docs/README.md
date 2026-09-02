# 文档地图

本目录只保留 Chickenbro 双端 Chat/SimC 重构的当前权威。被取代的方案、旧产品说明、历史 UI 证据和一次性执行记录由 Git 历史归档，不再留在最终工作树中。

## 阅读顺序

1. [项目状态](project-state.json)：当前阶段、已验证范围和未解锁门禁。
2. [Roadmap](roadmap.md)：用户价值、阶段状态和整体完成标准。
3. [当前架构](chickenbro-simc-architecture.md)：Identity、Chat、SimC、Worker、API 与双端边界。
4. [生产 Runbook](chickenbro-simc-production-runbook.md)：备份、迁移、candidate、切流、回滚与精确清理。
5. [验证矩阵](verification-matrix.md)：本地、candidate、live、恢复与用户验收证据。
6. [计划白名单](plans/README.md)：唯一可顺序执行的六阶段计划。

## 控制面

- [Harness](harness.md)
- [项目 Owner Map](project-owner-map.json)
- [后端 Owner Map](backend-owner-map.json)
- [已确认规格](superpowers/specs/2026-09-02-chickenbro-simc-total-rebuild-design.md)

## 清理与恢复证据

- [本地处置规则](refactor/chickenbro-simc-disposition-rules.json)：最终只有 `keep` 或 `delete`，未知路径 fail closed。
- [逐文件清单](refactor/chickenbro-simc-refactor-inventory.json)：绑定 Git commit、文件 SHA 和 caller/link 证明。
- [云端只读清单](refactor/chickenbro-simc-cloud-inventory.json)：当前服务、数据库、目录和容量事实。
- [云端退役清单](refactor/chickenbro-simc-cloud-cleanup-manifest.json)：逐个旧 unit、数据库、配置与目录的当前门禁；默认只读。
- [容量候选清单](refactor/chickenbro-simc-capacity-cleanup-manifest.json)：仅列精确候选，不授予删除。
- [恢复通道清单](refactor/chickenbro-simc-recovery-inventory.json)：独立介质与 restore 证明状态。

`delete`、`candidate_only`、dry-run 或磁盘可回收都不是 apply 授权。实际清理必须同时满足当前 Runbook、阶段 acceptance、恢复验证和精确 manifest。
