# 炸鸡队长双游戏首版实施计划

> 当前状态（2026-09-21）：已完成。用户已验收并授权发布，运行源码 `77cee1603` 已上线，提交与合入已完成；见[正式发布记录](../../artifacts/releases/2026-09-21-poe2/README.md)。下文 Candidate、禁止提交与待验收等表述记录此前阶段，不代表当前状态。

> 使用 subagent-driven-development 逐项执行和评审。所有运行、下载、构建与测试仅在云端；不提交、推送或合入。

**Goal:** 交付可供用户验收的独立 POE2 Candidate，支持问答、构筑诊断/对比/导出及制作路线顾问。

**Architecture:** 共用 QQ 身份与 Chat 基础设施，会话固定 game=wow|poe2；游戏独立提示词、工具与数据。PoB 2 作为云端隔离进程执行，输入/结果/版本持久化，Web 使用 typed API。

**Tech Stack:** 现有 FastAPI/PostgreSQL/Taro React，云端 LuaJIT + 固定版本 PathOfBuilding-PoE2。

**Spec:** 本次对话中用户确认的六部分设计；下列范围是该设计的执行合同。

## 全局约束

- 已有魔兽会话默认为 wow；切换游戏不改变会话的所属游戏。
- 账号由服务端 Principal 决定，客户端不得指定 owner。任务、构筑、缓存均绑定 owner/game。
- 首版国际服、中文交互；保存游戏版本、赛季、引擎版本、输入和配置来源。
- 禁止价格/交易、未公开 API、游戏客户端自动操作；GGG 自动绑定不作为首版依赖。
- 制作顾问提供有来源的路线和 Craft of Exile 文本导入；未验证权重不提供精确概率。
- 云端运行所有依赖、工具、测试与构建；本地只编辑/读取源文件及传送代码。
- Candidate 不切换生产；独立目录、数据库、端口和 Cookie，保留可恢复旧状态。
- 不 git commit/push/merge；用户测试验收后另行授权收尾。

## Task 1: 云端 PoB 技术验证与引擎适配

Files: `server/app/poe2/engine.py`, `server/app/poe2/bridge.lua`, `tests/app_poe2_engine_test.py`, 云端 upstream/evidence 目录。

接口：`calculate(source: str, changes: dict | None) -> dict`。返回构筑摘要、stats、有效配置、unsupported、引擎身份和 exportCode；输入限长/解压限额、拒绝不受信路径与代码。无网络计算进程限时限内存；每任务独立构筑状态。

- [x] 在云端固定上游 commit，安装隔离 LuaJIT 运行环境，读取上游测试构筑和 headless 入口。
- [x] 先写导入/计算/装备变化/导出重导入/非法输入测试，在云端确认缺失能力失败。
- [x] 实现最小桥接及 Python 适配，返回真实计算结果与缺失机制，不臆造指标。
- [x] 用上游固定测试构筑独立计算作基准；保存首轮耗时/峰值内存、计算一致性及跨任务无污染证据。

## Task 2: Chat 游戏隔离与 POE2 研究工具

Files: `server/app/chickenbro/{domain,repository,application,codex_adapter,agent_skills}.py`, `server/app/chickenbro/agent/`, `server/chickenbro_native_mcp.py`, `server/migrations/product/0011_poe2.sql`, `server/app/api/routes/chat.py`, 相关后端测试。

接口：创建/列表接受 `game`，值仅 wow/poe2，默认 wow；会话响应添加 game。发消息及工具上下文从持久化会话读取 game，不信任消息传入覆盖。POE2 不暴露 WCL/SimC 工具，WoW 不暴露 POE2 工具。研究证据保持会话范围。POE2 研究流程覆盖版本/来源/诊断/有限对比/制作；数值只引用真实任务结果。

- [x] 写游戏创建/列表/跨游戏工具拒绝/旧会话兼容测试，在云端先确认失败。
- [x] 增量迁移 game 字段，贯通创建、历史与持久化执行上下文。
- [x] 按 game 选择提示词/skill/toolbox；实现 POE2 权威来源与制作顾问流程。
- [x] 云端运行 Chat、工具、持久化及 owner 回归，复核历史 wow 行为。

## Task 3: POE2 构筑与计算任务 API

Files: `server/app/poe2/{domain,application,repository,worker,tools}.py`, `server/app/api/routes/poe2.py`, `server/app/main.py`, `server/app/api/dependencies.py`, `server/app/worker/`, POE2 API/数据库测试。

接口：`/api/v2/poe2/builds` 导入/列表；`/builds/{id}` 读取；`/jobs` 幂等提交 `buildId,changes`；`/jobs/{id}` 状态/结果；`/compare` 对比同基线结果；`/builds/{id}/export` 导出；`/crafting/import-link` 生成正确编码的 CoE 链接。工具网关复用 application。UUID owner 校验，结果保留版本与输入 hash。候选 changes 限定装备/技能选择/配置/天赋已验证操作。

- [x] 写第二账号拒绝、幂等冲突、任务租约失败、不可比结果拒绝测试并在云端确认失败。
- [x] 实现 owner-scoped 存储、任务队列、engine 调用及结果语义验证。
- [x] 使用两账号真实 PostgreSQL 验证隔离、持久化和重试；接入 Chat 工具。

## Task 4: Web 双游戏工作区与构筑工作台

Files: `packages/domain/src/{chat,poe2}.ts`, `packages/api-client/src/{chat,poe2}.ts`, `apps/mini-taro/src/web/{WebShell,WebChat,WebPoe2}.tsx` 及导航/样式/测试。

接口：与 Task 2/3 JSON 合同一致；游戏切换带 game 查询参数/独立导航状态，会话列表按游戏读取。POE2 页面提供分享码/XML导入、构筑列表、计算状态、改动输入、对比、导出和装备文本 CoE 跳转。保留原有魔兽入口。

- [x] 写切换/历史/导入失败/轮询终态/第二账号状态清理测试，云端运行确认失败。
- [x] 实现 typed API 与可操作页面，支持窄屏、错误/空态和版本展示。
- [x] 云端组件测试/typecheck/lint/H5 build；浏览器运行也在云端验证。

## Task 5: Candidate 集成、审查与用户验收交付

Files: `server/poe2_candidate_runtime.py`, 必要部署脚本、`artifacts/verification/2026-09-18-poe2/README.md`, 当前架构/owner/项目状态/路线图。

- [x] 在独立 Candidate 数据库应用迁移，部署 API/Chat/PoB worker 及 Web，保留 manifest 与恢复入口。
- [x] 在云端运行受影响后端/数据库/Web/控制面检查及固定业务 smoke。
- [x] 独立评审完整 diff，修复重要问题，保留失败与复验结果。
- [x] 验证用户可访问的测试入口、两游戏导航、真实 Chat 来源、真实构筑计算/对比/导出、两账号隔离。
- [x] 记录源码文件清单 hash、引擎 commit、制品 hash、任务回执、限制及测试步骤；交付后等待用户验收，不提交合入。
