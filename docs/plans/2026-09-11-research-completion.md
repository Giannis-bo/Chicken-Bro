# 有限研究完整解答 Implementation Plan

> 按已获用户授权在当前独立工作区逐项实施，不重复审批。方法：writing-plans、TDD、定向复核；隔离和发布按项目 runbook。

**Goal:** 让固定日志/角色的正常问题与追问复用已有证据并完成必要取数，同时继续阻止无界采样。
**Architecture:** 研究范围跨轮持久限制；来源次数/事件工作量改为每个服务端 run 的执行保护，历史总消耗不清零。持久工具结果提供同账号同对话的紧凑证据和成功概览复用；治疗直接读聚合表，错误先校验再预留。
**Tech Stack:** Python、PostgreSQL、现有 WCL GraphQL、现有 Codex App Server，无新增依赖。
**Spec:** 本任务上一轮 `artifacts/verification/2026-09-11-research-feedback-diagnosis/README.md`；用户本轮明确授权落地和发布。

## 范围与预算

- 保护其他任务 WIP；不安装或本地运行 SimC；不改变治疗专精不支持模拟的事实。
- 10 玩家、3 战斗、3 榜单比较组和4个新模拟仍跨研究累计，公开网页现有边界保留；48来源子查询/20,000事件请求单位/360秒只限制单轮执行。正常用户主动继续可补同一有限范围，不允许自动拆 Top100；服务端 run 身份控制重置，不由模型参数控制。
- 最多6次真实产品模型回复、18次直接WCL验证请求、0新增SimC。模型工具调用受产品自身每轮保护；分别记录，不把直接查询预算误称全部上游调用预算。已有原始工具结果复用不计新上游。
- 验收：原始问题+属性追问；无数据泄漏；非法参数不扣上游；旧账本48已满仍可新轮补有限对象；同run重建不刷新执行计数；Top100无采样；实际治疗表非事件小计。

## 执行步骤

- [ ] 1. tests/app_research_completion_test.py、tests/app_research_lifecycle_postgres_test.py 先覆盖错误计费、持久续查、同run恢复、账号隔离和普通actor身份合并；实现 research_budget.py、research_lifecycle.py、source_gateway.py 的边界与结构化错误。断言非法请求后 `budget.calls == 0`，新run继续已知角色成功、额外第11人仍阻断。
- [ ] 2. tests/app_research_evidence_test.py 先覆盖历史属性恢复与紧凑投影；实现 research_evidence.py 和 repository/application 接线，恢复旧持久研究建立前的同对话证据。只白名单业务字段，结果作为非指令数据进入模型；字节、行数、角色数明确有界。ToolRecorder 对已完成战斗的近期成功概览做同owner/conversation复用，记录命中来源，不调用上游。
- [ ] 3. tests/app_wcl_healing_test.py 先覆盖 whole-fight聚合口径、缺字段、窗口范围、响应裁剪；wcl_source.py/source_gateway.py/MCP 增加 healing 视图，兼容 overview+Healing，带来源覆盖信息。用官方schema和有限实查确定字段，不能假定 missing=0。
- [ ] 4. 新增向前兼容 migration 保存 run usage 与工具请求元信息；codex_stdio/adapter 消费白名单token usage事件并持久化，未提供时保持unknown。更新运行提示词按目标→已有证据→必要缺口规划，优先聚合，不扩大无关研究。
- [ ] 5. 定向测试→真实PostgreSQL→后端回归→本地diff审查→隔离Candidate原题与变体→合入main/push→排空门禁下API/Worker匹配发布→线上正常追问、隔离及公网Web文件核验；保留旧backend/Web和精确恢复manifest。未改Web仍验证既有产物，不声称新增人工QQ验收或回滚演练。

所有结果绑定实际源码；失败保留，不靠扩大模型预算制造通过。
