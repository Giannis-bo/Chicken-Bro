# Chickenbro 路线图

更新日期：2026-09-20。产品聚焦 Web 对话与云端 SimulationCraft，使用 QQ 登录。

## 已完成

| 能力 | 当前交付 |
| --- | --- |
| 账号与历史 | QQ 网站登录，聊天、图片与模拟记录按账号隔离，跨浏览器读取自己的历史 |
| 对话体验 | 流式回复、研究进展、截图提问、会话切换与回复状态恢复、回答反馈、七种插画主题 |
| 研究与日志 | 实时搜索、WCL 战斗视图和窗口统计、跨轮研究范围管理、历史证据复用与按需研究流程；[修复同一玩家跨来源重复计额](../artifacts/verification/2026-09-17-research-player-identity/README.md) |
| 云端模拟 | Raider.IO 角色导入，输出与坦克专精，装备与天赋场景、自定义施法、食物／属性实验及任务对照；[指定阶段初始资源、增益、冷却和短窗口统计](../artifacts/verification/2026-09-20-phase-state-release/README.md) |
| 连续实验 | Chat 单轮与跨轮 SimC 任务不限次数，保留任务历史、幂等与账号隔离 |
| 引擎与目录 | SimulationCraft 对应游戏构建 `12.1.0.69814`，同步匹配的天赋、装备和中文目录，兼容英雄树免费点 |
| 运营与质量 | 只读运营后台、反馈归集、Badcase 通用修复与条件发布流程 |

各项发布身份和验证记录见[项目状态](project-state.json)，功能合同见[架构](chickenbro-simc-architecture.md)。

## 正在推进

- [Badcase 持续改进](plans/2026-09-08-badcase-workflow.md)：根据实际反馈定位通用问题，完成限定验证后按授权发布。
- [私有副本保留与到期处置](badcase-workflow-operations.md#保留与独立处置对账)：按现有登记核对到期时间、哈希、活动引用与恢复条件。

## 后续

- **模拟资料完整性**：补齐制造／特殊装备版本、附魔品质效果、完整首领阶段及部分饰品机制的可验证资料，按[跟进条件](plans/2026-09-11-remaining-issues-status.md)推进。
- **复杂研究效率**：根据已有配对评测，优先核对流程读取往返与缓存成本；具体优化范围待确认。[评测记录](../artifacts/verification/2026-09-12-agent-benchmark/README.md)

[计划索引](plans/README.md) · [验证矩阵](verification-matrix.md) · [生产 Runbook](chickenbro-simc-production-runbook.md)
