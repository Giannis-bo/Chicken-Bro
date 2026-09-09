# 文档地图

> 当前方向（2026-09-09）：仅 Web Chat/SimC，登录改为 QQ；小程序停止交付。旧微信历史保留，不迁移到新 QQ 账号。实施状态见 [QQ 重构计划](plans/2026-09-09-web-only-qq.md)。 以下双端内容属于 1.0 历史。

当前产品版本：**1.0，用户已验收**。产品介绍从根目录 [README](../README.md) 开始；本文导航区分当前说明、工程规则与历史证据。

## 使用产品

- [使用指南](user-guide.md)：登录、对话、历史、模拟、任务 ID 与帮助。
- [1.0 版本说明](releases/1.0.md)：已验收范围、最后调整、已知限制与发布边界。

## 开发与当前事实

1. [项目状态](project-state.json)：1.0 里程碑与历史证据引用。
2. [Roadmap](roadmap.md)：已完成范围与待决策事项。
3. [开发指南](development.md)：代码入口、已有依赖、测试和预览。
4. [当前架构](chickenbro-simc-architecture.md)：Identity、Chat、SimC、Worker 与双端合同。
5. [验证矩阵](verification-matrix.md)：本地、运行态、用户验收与恢复证据。
6. [生产 Runbook](chickenbro-simc-production-runbook.md)：运行身份、增量发布、回滚和历史迁移操作。

## 控制面与历史追溯

- [Harness](harness.md)、[项目 Owner Map](project-owner-map.json)、[后端 Owner Map](backend-owner-map.json)。
- [计划白名单](plans/README.md)：已确认计划及当前收尾结论；不按目录存在与否推断执行授权。
- [1.0 历史进度](roadmap-history-v1.md)：保留原始过程，不以旧“正在推进”覆盖当前结论。
- [最初规格](superpowers/specs/2026-09-02-chickenbro-simc-total-rebuild-design.md)：由后续明确产品决定补充与取代。
- [本轮验证](../artifacts/verification/2026-09-08-v1-close/README.md)、[COS 写权限整改](../artifacts/security/2026-09-08-cos-write-hardening/report.md)。

## 历史清理与恢复证据

[处置规则](refactor/chickenbro-simc-disposition-rules.json)、[逐文件清单](refactor/chickenbro-simc-refactor-inventory.json)、[云端快照](refactor/chickenbro-simc-cloud-inventory.json)、[退役清单](refactor/chickenbro-simc-cloud-cleanup-manifest.json)、[容量清单](refactor/chickenbro-simc-capacity-cleanup-manifest.json)、[恢复清单](refactor/chickenbro-simc-recovery-inventory.json)保留各自绑定日期与 SHA 的历史意义。

它们不是当前实时资产目录，也不是重新删除的授权。新操作必须先刷新事实并执行当前门禁；未经本轮确认的下载、安装、拉取或破坏性清理不能因文档收尾而自动执行。
