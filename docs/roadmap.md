# Chickenbro 路线图

## 已完成

- G7 日志施法归因修复已上线（`f1f0f0a0d`）：不把日志频次或同步事件直接当作按键习惯；两次完整Candidate及公网高分对照验收通过，保留失败与适用边界。[记录](../artifacts/verification/2026-09-10-badcase-g7/release/README.md)。

- [WCL 工具效率优化](plans/2026-09-10-wcl-tool-efficiency.md)：按需视图、单轮去重和有界窗口统计已合入推送并发布（`f95f6bbe2`）；隔离图片/Chat/SimC、隔离及公网 WCL 与账号隔离通过，Web 14 文件一致。复用 667 项后端与 63 项控制面测试，按用户要求停止扩样本。[发布证据](../artifacts/verification/2026-09-10-wcl-tool-efficiency/release/README.md)。

- [Badcase 复盘](plans/2026-09-08-badcase-workflow.md)：扫描、诊断、批准与条件发布闭环已落地，两条G6排行榜修复已正式发布；线上两题、Chat/SimC/owner及Web14文件验收通过。自动化00点执行成功、06点因额度失败；G7和另1条反馈待后续处理。[发布证据](../artifacts/verification/2026-09-09-badcase-workflow/production-final-release.json)。

- [运营后台](plans/2026-09-09-admin-ops.md)：QQ唯一管理员、只读用户/Chat/SimC数据、北京时间趋势；已发布并完成真实本人权限、非管理员拒绝、业务和SQL对账。[证据](../artifacts/verification/2026-09-09-admin-ops/README.md)。

- [SimC 场景实验](plans/2026-09-09-simc-scenario-experiments.md)：已合入推送并发布（`7ef8a5dfd`）；天赋节点/整套替换、同进度饰品候选、预检重跑和对照已通过隔离及公网真实模型验收。[发布证据](../artifacts/verification/2026-09-09-simc-scenario-experiments/release/README.md)。制造/特殊装备版本仍未全面覆盖。

- Web 是唯一产品客户端；QQ 网站授权登录已上线，用户本轮确认已顺利使用 QQ 登录。服务端内部账号拥有 Chat/SimC 历史，跨用户隔离，不自动绑定旧微信账号。
- Chat 支持流式回复、历史继续、归档、账号级单回复、不可修改的回答解决情况反馈、截图提问，以及持久化生成与独立 Worker。
- SimC 支持 Raider.IO 导入、参数设置、队列进度、报告、任务 ID 复制及对话中的换装重跑。WCL 用于战斗研究和历史资料；新角色导入不接受 WCL。
- Web 提供七种插画主题、独立 FAQ 和更新日志。当前源码和各次运行版本的证据见[项目状态](project-state.json)，不把一次发布的 SHA 当成所有运行面的统一身份。

- 输出与坦克全专精支持已发布，治疗明确拒绝；原始功能发布源码 `0649a2e858f5`；本轮清理发布延续该能力。全专精及公网验收见[发布记录](../artifacts/verification/2026-09-09-simc-all-specs/release/README.md)。

- [小程序清理](plans/2026-09-09-mini-retirement.md)：源码和 Web 已合入、推送及发布（`7adcdeffa`）；隔离及公网真实图片/SimC、CSRF、账号隔离和幂等验证通过；用户确认的 186 个仅微信账号及业务数据已从正式库删除，私有备份独立恢复、演练及保留记录核对通过。18 个 QQ 与 14 个无关联账号保留。公网 14 个 Web 文件与发布清单一致，旧代码/Web 版本保留用于回滚。

## 正在推进

- [Chat 有界研究](plans/2026-09-10-bounded-research.md)：Top10 与查询/实验预算已完成本地及针对性隔离模型验证；补齐原生网页搜索绕过预算的入口，用户已确认并授权提交发布，发布检查中。


## 下一步

本轮 WCL 工具效率优化已发布并完成自动业务验证；后续新功能按用户新授权推进。详见[本轮发布记录](../artifacts/verification/2026-09-10-wcl-tool-efficiency/release/README.md)。

## 暂缓与待决策

- 暂缓新增新闻、装备库、天赋库、旧模拟器及插件 `/simc` 文本导入。
- COS 历史匿名写入调查、日志及版本恢复能力见[历史安全记录](../artifacts/security/2026-09-08-cos-write-hardening/report.md)。

[架构](chickenbro-simc-architecture.md) · [验证矩阵](verification-matrix.md) · [生产 Runbook](chickenbro-simc-production-runbook.md) · [计划白名单](plans/README.md)

1.0 双端交付、小程序上传和早期迁移均属于[历史记录](roadmap-pre-mini-retirement.md)，不再存在当前微信审核或上传待办。
