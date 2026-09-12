# 鸡哥按需流程与核心规则精简

用户于 2026-09-12 批准此前评估方案，并授权实施、提交、合入和发布。

目标：保留既有业务与证据边界，核心规则只保留通用决策；四份受版本控制的流程按需读取，减少无关上下文。

架构：核心 AGENTS.md 提供流程索引；read_chickenbro_skill 仅按固定名称读取同一 release 的 UTF-8 文件，返回版本摘要，不接受路径、URL 或用户内容。工具结果不提升用户/网页指令权限。原有十五个工具、权限与预算不变，不启用通用文件读取或插件。

技术：Python 标准库、现有 MCP 与 Chat adapter、Markdown、现有隔离 Candidate。

设计依据：本任务上一轮已批准的三层方案：核心规则 / 按需流程 / 工具与服务端合同。

- [x] 1. TDD：只读技能名称白名单、参数拒绝、大小/编码/缺失失败、工具集兼容与无上游副作用。新增 server/app/chickenbro/agent_skills.py、tests/app_chickenbro_agent_skills_test.py，修改 server/chickenbro_native_mcp.py。
- [x] 2. 精简 agent/AGENTS.md，四份流程放入 agent/skills/{mechanics,wcl-analysis,rankings,simc-experiment}.md。保留历史修复要求；统一每研究累计四任务，核心 UTF-8 目标不超过 10KB，每份流程不超过 16KB。测试实际 LF/CRLF 文件及加载余量。
- [ ] 3. 定向与后端/控制面测试、独立代码和规则覆盖审查；旧版/新版同模型有限对照，记录原始 usage、耗时、工具/skill 选择、答案与失败。固定20题不冒充全量运行。
- [ ] 4. 当前运行身份与精确文件核验，Candidate 业务验证，保留旧版和恢复清单；空闲门禁切换 API/Worker；线上真实 skill 调用、Chat/SimC读取与第二账号隔离、Web 哈希验证。
- [ ] 5. 更新证据与状态，合入推送 main，核对 local/remote/runtime；安全清理本任务 worktree，原 stash 不动。

不新增数据库、依赖、模型分类器或业务权限；不在本地运行 SimC。不宣称节省 token 等于质量提高；真实模型对照和部署证据分别记录。
