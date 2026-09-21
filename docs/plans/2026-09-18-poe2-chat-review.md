# POE2 Task 2 独立评审

结论：**需要修复**。本次仅静态读取 Task 2 源码、diff、实现报告及新增测试；未执行代码、测试或构建。

## 可执行发现

### [P1] 将受信 game 透传至实际 MCP 子进程

- 位置：`server/app/chickenbro/codex_adapter.py:200-206`。
- `_load_profile()` 扩展了 toolbox 的 `env_vars`，但缺少 `CHICKENBRO_GAME`。`stream()` 在第 585 行仅把该值写入 Codex app-server 的父进程环境；MCP 子进程需要通过该白名单接收它。沿用已有 profile 时，toolbox 因缺少该变量而在 `server/chickenbro_native_mcp.py:524` 默认采用 `wow`。
- 影响：POE2 会话实际拿到 WoW 工具列表和 skill 枚举，无法调用 POE2 工具，并可调用仍获 source capability 支持的 WCL/Raider.IO 工具，违反 Task 2 的跨游戏能力隔离要求。
- 修复：将 `CHICKENBRO_GAME` 纳入运行时构造的 toolbox 环境白名单，保证使用持久化会话推导的值。补充云端回归，从 POE2 adapter/context 和旧 profile 出发验证实际 toolbox 子进程的 tools/list 与跨游戏拒绝；直接传 `handle_rpc_request(game="poe2")` 的单测覆盖不到环境转发缺口。

## 合同与质量判断

- 创建与列表默认 `wow`，Literal/领域枚举限制合法值；迁移为历史行补 `wow`，列表同时约束 owner/game，详情仍约束 owner。会话没有改变 game 的写入入口；创建幂等冲突也不会覆盖既有 game。
- `execute_run()` 重新读取持久化会话并向 prompt/tool context 传入 game，正文无法改变它；该入口也覆盖 durable 执行路径。
- 独立 POE2 提示词与 skill 覆盖国际服中文、版本/赛季/来源、真实结果、有限对比、制作失败分支/停止条件及未验证权重限制。公开研究继续使用通用入口。
- POE2 capability 的签发/撤销和固定本机 gateway 路径已留 hook；Task 3 尚未完成的 gateway 实现不计为本任务缺陷。该 gateway 集成时仍须校验 owner、conversation/run、game 与参数。
- POE2 导入 XML 校正由实现代理进行中：截至本轮最后读取，`server/chickenbro_native_mcp.py:343-349` 仍为子串检查，尚未看到严格 `PathOfBuilding2` 根节点校正；此项需在合并本评审结论前复读确认。

## 证据范围

实现报告记录云端 169 项通过、11 项跳过；本评审未重跑。真实 PostgreSQL 测试因缺少测试数据库配置而跳过，不能视作持久化集成通过。Candidate 阶段仍需实际迁移后的两游戏/两账号数据库与真实 MCP 工具链验证。
