# POE2 Task 2 Chat 实施报告

## 结果

- Chat 会话新增不可变 `game=wow|poe2`，创建和列表默认 `wow`；旧会话经迁移默认归属 `wow`。
- 创建、列表和详情响应返回 `game`；列表按账号和 game 过滤。相同幂等键更换 game 返回 `IDEMPOTENCY_CONFLICT`。
- 发消息时从服务端持久化会话重新读取 game，并把该值写入 prompt 与受信工具上下文；消息正文中的 `game=...` 不能覆盖。
- Codex 按 game 加载独立规则、skill 枚举和 MCP 工具白名单。POE2 不列出或执行 WCL、Raider.IO、SimC；WoW 不列出或执行 POE2 工具。
- POE2 工具 hook：`poe2_import/list/get/calculate/compare/job_get/export/crafting_import_link`，通过账号与 run 绑定 capability 调用内部 gateway。
- POE2 导入在 MCP 边界仅接受 PoB 2 分享码或根节点严格为 `PathOfBuilding2` 的可解析 XML 正文；PoE1 `PathOfBuilding`、嵌套/注释子串、尾随脏数据、URL 和路径在进入 gateway 前拒绝。
- 运行时构造的 MCP `env_vars` 明确转发 `CHICKENBRO_GAME`；旧 profile 经 adapter 重写后，toolbox 子进程会消费服务端持久化 game，不会回退到 `wow`。
- 新增 POE2 构筑分析与制作流程。制作顾问要求版本、来源、失败分支和停止条件；权重未核验时不输出精确概率，数值仅使用真实成功任务结果。

## 接口交接

- `NativeCodexChatAdapter` 新增 `poe2_gateway` 与 `poe2_gateway_url`。
- gateway capability context 为 `ChatToolContext(principal, conversation_id, run_id, game)`。
- 子进程变量：`CHICKENBRO_POE2_GATEWAY_URL`、`CHICKENBRO_POE2_GATEWAY_TOKEN`。
- 固定内部路径 `/api/v2/internal/chickenbro/poe2-tool`，header `X-Chickenbro-POE2-Gateway`，请求体 `{"operation": ..., "arguments": ...}`。
- Candidate loopback 端口 `8796` 已加入有限本机 gateway 白名单；公网主机、含认证信息 URL、错误路径及其他端口仍拒绝。
- operations：`import`, `list`, `get`, `calculate`, `compare`, `job_get`, `export`, `crafting_import_link`。

## TDD 与云端证据

- RED：云端 `/opt/chickenbro-candidates/poe2-20260918/chat-tests` 首轮 6 项失败，分别显示 application/API/MCP 缺少 game 与 POE2 gateway 能力。
- 第二个 RED：URL/路径导入用例确认旧实现会把不可信 source 转发到 gateway。
- 评审 RED：旧 profile 的 toolbox `env_vars` 缺少 `CHICKENBRO_GAME`；PoE1、嵌套和注释诱导 XML 会被旧子串判断错误接受。
- Candidate RED：`127.0.0.1:8796` 未在有限本机 gateway 白名单内，部署后 capability 请求会被拒绝；补入确切端口后复验通过。
- GREEN：使用 `/opt/chickenbro-runtime/bin/python` 运行 Chat application/API、Codex adapter、native MCP、skill、schema、owner repository 与 durable PostgreSQL 测试模块，共 `171` 项通过，`11` 项跳过。新增消费配置回归从 POE2 adapter/context 生成实际 toolbox config，并通过转发环境调用 native `tools/list`，确认包含 `poe2_calculate` 且不含 `query_warcraftlogs_report`。
- 跳过项原因：该独立测试目录未配置 `CHICKENBRO_TEST_DATABASE_URL`，因此未在本任务中执行真实 PostgreSQL 持久化套件；迁移和 SQL 形状由 schema 与 repository 合约测试覆盖。
- 未在本地运行测试、构建或代码；未改生产、未提交、未推送、未合入。

## 改动文件

- `server/app/api/routes/chat.py`
- `server/app/chickenbro/domain.py`
- `server/app/chickenbro/repository.py`
- `server/app/chickenbro/application.py`
- `server/app/chickenbro/codex_adapter.py`
- `server/app/chickenbro/agent_skills.py`
- `server/app/chickenbro/agent/POE2.md`
- `server/app/chickenbro/agent/skills/poe2-build-analysis.md`
- `server/app/chickenbro/agent/skills/poe2-crafting.md`
- `server/chickenbro_native_mcp.py`
- `server/migrations/product/0011_poe2.sql`
- `tests/app_poe2_chat_isolation_test.py`
- `tests/app_chickenbro_application_test.py`
- `tests/app_chickenbro_codex_adapter_test.py`
- `tests/app_chickenbro_owner_isolation_test.py`

## 集成关注点

- Task 3 需在 application/dependencies/main 接入 `poe2_gateway`，并由 gateway 对参数结构、owner、conversation/run、幂等和构筑来源再次校验；MCP 只承担工具可见性和第一层输入边界。
- Candidate 应在独立数据库实际应用 `0011_poe2.sql` 后补跑 PostgreSQL Chat 创建、列表、历史与 owner 回归，再绑定本次源码/迁移身份。
