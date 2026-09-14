# Chickenbro 路线图

当前产品为 Web Chat 与云端 SimC，使用 QQ 网站登录。本文只记录已确认的产品方向和下一步；精确批次、历史失败及分层证据见[项目状态](project-state.json)，不把某次发布身份当作当前所有运行面的身份。

## 已完成

- Chat SimC 次数上限已取消（`22037c2a`）：单轮与跨轮均不限任务次数，保留历史记录、幂等和账号隔离；Candidate 与线上均验证历史四次后继续模拟成功。[发布记录](../artifacts/verification/2026-09-14-simc-quota/README.md)。

- 通用研究证据与语义优化已完成限定验证与发布；固定20题未全跑，详见[任务记录](plans/2026-09-11-research-generalization.md)。

- 鸡哥直接结论表达已发布（`730882f2`）：核心、WCL与答案修正路径禁止无关免责和预防性反驳；后端、控制面、Candidate及线上真实回答验收通过。[记录](plans/2026-09-13-direct-conclusions.md)。

- 鸡哥复杂研究配对评测完成：48次固定运行全部质量通过，同题配对耗时中位增加9.62%，未达全面提速门槛；另有8条真实Candidate诊断。优先验证流程读取往返与缓存成本，未追加产品优化。[评测记录](../artifacts/verification/2026-09-12-agent-benchmark/README.md)。

- 鸡哥按需流程已发布（`2294cb95`）：核心规则缩小74%，四类流程受控按需读取，统一跨轮预算并绑定调用证据。最终后端801通过/1平台跳过，5条Candidate与3条线上通过；复杂问题存在额外读取往返，不宣称普遍提速。[发布记录](../artifacts/verification/2026-09-12-agent-skills/README.md)。

- Web 会话切换修复已发布（`0f8b3ce9`）：删除两处研究额度说明，返回进行中的会话恢复等待、进度和流式回复，结束后可继续提问。279 项本地测试、实际构建与公网页面隔离交互验证通过，13 个公网文件匹配。[发布记录](../artifacts/verification/2026-09-11-chat-return-state/README.md)。

- Web/QQ、账号隔离、历史与截图对话、持久化生成、回答反馈及只读运营后台已交付；小程序产品已退役。
- SimC 支持 Raider.IO 导入、输出/坦克专精、装备与天赋场景、自定义施法、食物/属性实验及任务对照；治疗模拟不支持，WCL 用于研究而非新角色导入。
- 研究支持实时搜索、有界 WCL 视图与窗口统计、跨轮范围预算及历史证据复用；具体能力与未验证边界见[架构](chickenbro-simc-architecture.md)。
- [Badcase 自动修复工作流](plans/2026-09-08-badcase-workflow.md)持续执行通用修复、有限验证与条件发布；各问题是否闭环按持久状态核验。

## 正在推进

当前无本轮未完成实施项。

## 下一步

- 按已有保留登记，在到期且满足哈希、活动引用和恢复门禁后处置私有副本；由现有 Badcase 调度续办，状态见[收尾记录](../artifacts/verification/2026-09-11-project-closure/README.md)。
- 资料缺口按[剩余事项](plans/2026-09-11-remaining-issues-status.md)的恢复条件推进，不自动扩大实验预算。

## 待决策与暂缓

制造/特殊装备版本、附魔各品质、完整首领阶段与部分饰品机制仍有事实缺口；有限条件实验不能证明普遍结论。原生网页计量与跨独立研究账号额度也不属于已完成覆盖。

新增新闻、装备库、天赋库、旧模拟器及插件 `/simc` 导入暂缓。其他未确认方向与明确关闭事项见[想法记录](roadmap/ideas.md)，不转为自动待办。

[计划索引](plans/README.md) · [验证矩阵](verification-matrix.md) · [生产 Runbook](chickenbro-simc-production-runbook.md) · [历史路线图](roadmap-history-20260911.md)
