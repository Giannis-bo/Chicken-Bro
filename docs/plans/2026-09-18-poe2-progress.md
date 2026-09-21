# SDD ledger — plan: docs/plans/2026-09-18-poe2-dual-module.md

> 当前状态（2026-09-21）：已完成。用户已验收并授权发布，运行源码 `77cee1603` 已上线，提交与合入已完成；见[正式发布记录](../../artifacts/releases/2026-09-21-poe2/README.md)。下文 Candidate、禁止提交与待验收等表述记录此前阶段，不代表当前状态。

Base: fe0e398697bf31791d213a5845a0818cf54572df
Local: .worktrees/poe2-20260918 (codex/poe2-20260918)
Cloud: /opt/chickenbro-candidates/poe2-20260918

Ruling: 用户禁止提交合入，使用未提交 diff 和源文件 manifest 作审查/运行身份，不执行技能的提交步骤。
Ruling: 用户要求避免本地执行，测试/构建/引擎/辅助运行放到云端，本地只进行文件操作和传输。
Ruling: 创建独立 worktree 属于保护主工作区的必要可逆操作，按既有授权继续。

| Tasks | Shared interface/files | Review |
| --- | --- | --- |
| 1/3 | calculate(source,changes), normalized result | 固定引擎版本和基线 hash；Task 3 使用 Task 1 实际支持项 |
| 2/3 | native MCP game routing | Task 2 提供选择和隔离，Task 3 提供 POE2 工具实现，顺序整合 |
| 2/4 | game create/list/response | 默认 wow，前端兼容旧响应，响应新字段 validator 同步 |
| 3/4 | POE2 API JSON | Task 3 定义合同后 Task 4 接入 |
| 1/2/3/4/5 | tests vs spec | 云端执行；模拟测试不替代真实引擎、模型及数据库证据 |

Task 1: complete — 固定 v0.23.1/7d6f530，LuaJIT 独立运行目录。真实上游独立样本对照、装备/技能/天赋变化、导出再导入、跨任务无污染与 seccomp 断网测试通过。串行锁、45 秒/1 GiB 上限。合成样本不等同玩家实装验收。
Task 2: complete — 持久化 game、独立 prompt/skills/tools；已修 MCP env forwarding、严格 XML 根校验、bounded POE2 工具批准。真实检索（3 search / 1 open）、构筑读取、两次计算与比较均已回执核验。
Task 3: complete — 独立 DB、owner、CSRF、幂等、租约/重试耗尽终态；以 wow_app 实际角色完成 PG 和真实 worker 验证。评审的权限、请求限额及 worker identity 问题已修。
Task 4: complete — typed API、双游戏保留会话、工作台、导出/比较/制作入口。完整前端 289 项通过，最终 UI 组件、类型、lint、H5 构建与云端浏览器复验。
Task 5: complete — Candidate 已部署，API/真实 Chat/浏览器 13 检查通过；表单样式、制作路线实测及交付 manifest 已完成。公网 15 个制品逐项匹配；生产 Nginx 除新增 Candidate include 外与备份一致。生产主入口未切换；用户验收 pending。

Final crafting: 首轮后备搜索无关结果导致额度耗尽，已改为原生检索优先、限定 POE2 权威来源；最终 23 项提示词/工具测试通过。真实模型返回生命/双抗戒指的通货顺序、失败分支、停止条件与 CoE 导入链接，明确区分现行数据库与历史版本快照；未声称验证制作概率。

Independent review: chat-review、jobs-review、final-review 原发现均已修复；后续真实链路另发现 MCP 写工具审批合同和 Taro 原生表单样式转换，均有定向修复与复验。

Regression: 既有后端相关套件 713 tests / 1 skipped；全 npm test:backend 初次因未上传历史 Badcase artifacts 在收集阶段失败，排除不受影响的 tests.badcase_* 后通过。未将跳过项或初次失败计为成功。
