# Chickenbro 路线图

更新日期：2026-09-21。生产提供 Web 对话与云端 SimulationCraft，使用 QQ 登录；双游戏与 POE2 扩展在独立 Candidate 中验证。

## 已完成

| 能力 | 当前交付 |
| --- | --- |
| 账号与历史 | QQ 网站登录，聊天、图片与模拟记录按账号隔离，跨浏览器读取自己的历史 |
| 对话体验 | 流式回复、研究进展、截图提问、会话切换与回复状态恢复、回答反馈、七种插画主题 |
| 研究与日志 | 实时搜索、WCL 战斗视图和窗口统计、跨轮研究范围管理、历史证据复用与按需研究流程；[修复同一玩家跨来源重复计额](../artifacts/verification/2026-09-17-research-player-identity/README.md) |
| 云端模拟 | Raider.IO 角色导入，输出与坦克专精，装备与天赋场景、自定义施法、食物／属性实验及任务对照 |
| 连续实验 | Chat 单轮与跨轮 SimC 任务不限次数，保留任务历史、幂等与账号隔离 |
| 引擎与目录 | SimulationCraft 对应游戏构建 `12.1.0.69814`，同步匹配的天赋、装备和中文目录，兼容英雄树免费点 |
| 运营与质量 | 只读运营后台、反馈归集、Badcase 通用修复与条件发布流程 |

各项发布身份和验证记录见[项目状态](project-state.json)，功能合同见[架构](chickenbro-simc-architecture.md)。

## 正在推进

- [双游戏与 POE2 首版](plans/2026-09-18-poe2-dual-module.md)：独立会话、权威来源问答、云端 PoB 构筑导入/有限比较/导出与制作路线顾问；隔离 Candidate 等待用户验收，暂不提交合入或切换生产。
- [POE2 构筑入口](plans/2026-09-20-poe2-pob-only.md)：按最新要求改为国际服 PoB 字符串单入口，说明 ninja 复制位置；成功展示等级、职业和升华，确认后继续对比。云端真实字符串、手机布局及新导入流程已验证，等待用户验收。[验证记录](../artifacts/verification/2026-09-20-poe2-pob-only/README.md)。此前角色链接后台和历史资料保留，Web 不再提供链接导入。
- [国服简体术语](plans/2026-09-20-poe2-cn-terms.md)：对话默认国服名称，POE2工具与Web共享核实词表；用户构筑技能/辅助、职业升华、常用配置中文展示及真实Chat已在Candidate验证。[证据](../artifacts/verification/2026-09-20-poe2-cn-terms/README.md)
- [Badcase 持续改进](plans/2026-09-08-badcase-workflow.md)：根据实际反馈定位通用问题，完成限定验证后按授权发布。
- [私有副本保留与到期处置](badcase-workflow-operations.md#保留与独立处置对账)：按现有登记核对到期时间、哈希、活动引用与恢复条件。

- **POE2 构筑两步与天赋中文**：导入即展示角色、属性、技能、天赋，对比页内查看调整结果；当前完整主树与升华 4,544 节点中文化，保留武器组、搜索与节点详情。已完成云端 Candidate 真实导入与对比验证，等待用户验收。[范围](plans/2026-09-21-poe2-two-step-cn.md)、[证据](../artifacts/verification/2026-09-21-poe2-two-step-cn/README.md)。图上点选编辑为后续范围。

POE2 已在 Candidate 验证基线与相同方案复用、跨轮 Chat 方案预算（12 次/轮、60 方案/研究、120 执行尝试；30 方案软提醒）。读取与复用不扣额度，Web 手动计算保持现有策略。[范围](plans/2026-09-21-poe2-research-budget.md)、[证据](../artifacts/verification/2026-09-21-poe2-research-budget/README.md)。

## 后续

- **模拟资料完整性**：补齐制造／特殊装备版本、附魔品质效果、完整首领阶段及部分饰品机制的可验证资料，按[跟进条件](plans/2026-09-11-remaining-issues-status.md)推进。
- **复杂研究效率**：根据已有配对评测，优先核对流程读取往返与缓存成本；具体优化范围待确认。[评测记录](../artifacts/verification/2026-09-12-agent-benchmark/README.md)

[计划索引](plans/README.md) · [验证矩阵](verification-matrix.md) · [生产 Runbook](chickenbro-simc-production-runbook.md)
