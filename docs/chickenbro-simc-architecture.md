# 炸鸡队长与 SimC 双端架构

状态：当前执行权威

本架构定义重构后的唯一产品边界：微信小程序和 Web 只提供炸鸡队长会话与 SimC 任务。两端使用不同的客户端会话，但服务端都把它们解析成同一个内部 `user_id`，因此共享同一份服务端业务历史。

本文件同时是目标架构说明和接口参考。当前实现状态必须结合 [project-state.json](project-state.json) 判断；“目标”不代表已经部署、切流或通过用户验收。

## 用户承诺

同一微信用户登录任一端后，可以看到并继续自己的全部有效会话，也可以查看自己的全部有效 SimC 快照、任务、尝试和结果。任一端创建的数据在另一端以相同 ID、顺序、状态和结果出现。

以下内容不属于“同步所有数据”：OpenID、`session_key`、Cookie、Bearer、微信 access token、第三方凭据、模型思维链、内部日志、prototype/demo 数据，以及迁移完整性校验拒绝的旧记录。

## 当前实现与目标的边界

| 能力 | 当前仓库基础 | 正式目标 | 解锁阶段 |
| --- | --- | --- | --- |
| Principal | 正式 Mini Bearer、Web Cookie、Origin/CSRF 与混合凭据拒绝已在本地候选实现 | 真实微信凭据、候选与生产验收 | Phase 2 已实现；Phase 5 验收待执行 |
| Web 小程序确认 | browser verifier、opaque scene、原子单次交换、HttpOnly Cookie、审计与重放拒绝已实现 | 真实二维码确认和独立 Web Session 验收 | Phase 2 已实现；Phase 5 验收待执行 |
| Chat | 正式 `/api/v2/chat/**`、owner-scoped 历史、稳定游标、幂等发送与持久化回放已实现 | 候选/生产双端真实数据验收 | Phase 3 已实现；Phase 5 验收待执行 |
| SimC | 正式 `/api/v2/simc/**`、快照/readiness/compiler、PostgreSQL queue、Worker 与语义结果已实现 | 云端真实 runtime、任务终态和跨端结果验收 | Phase 4 已实现；Phase 5 验收待执行 |
| 客户端 | 活跃 Taro shell 已收敛为 5 条路由、2 Tab 与正式 Web Shell；旧文件仅作为待清理目标留存 | 候选构建、真实设备与登录验收 | Phase 5 本地实现完成；外部验收待执行 |
| 数据面 | 干净 schema、白名单迁移和核对代码已实现；生产仍依赖 legacy `wow_test` | 创建、迁移并切换只含 Identity、Chat、SimC、Ops 的 `chickenbro_prod` | Phase 2 本地实现完成；Phase 5 云端执行待门禁 |
| 旧系统 | 精确本地/云端清单和 fail-closed apply 已实现；旧系统仍承担生产与回滚职责 | 门禁通过后精确退役，Git 历史承担归档 | Phase 6 实现完成；apply 待 Phase 5 与恢复验证 |

旧 prototype 文件仍在本地精确删除清单中，但已经从正式 application composition 和客户端调用图断开；`/api/v2/prototype/**` 不属于正式 API。HTTP 200、systemd active、候选首页可达或本地测试通过都不能把表中“目标”提升为生产完成。

## 运行拓扑

```text
微信小程序 -- Mini Bearer -----\
                               > API/BFF -> Principal(user_id, session_kind)
Web/H5 ---- HttpOnly Cookie ---/                   |
                                                   +-> Identity
                                                   +-> Chat -> Codex Adapter
                                                   +-> SimC -> ops.job_queue -> Worker
                                                                  |            |
                                                                  |            +-> cloud SimulationCraft
                                                                  +-> Raider.IO / WCL adapters
```

部署单元固定为一个模块化单体 API、一个独立 Worker、一套 PostgreSQL 和一个已安装的云端 SimulationCraft runtime。不引入第二种数据库、Redis、Celery、Kafka、长期双写或通用插件平台。

## 依赖方向

```text
UI -> typed API client -> API route -> application -> domain -> port <- adapter
```

依赖只允许向右：

- Domain 不导入 FastAPI、Pydantic、Psycopg、Taro、Codex、Raider.IO、WCL 或 SimC 实现。
- API route 只做传输解析、Principal/CSRF 校验、公开错误映射和 use-case 调用。
- Application 负责事务顺序、幂等、状态机和 owner-scoped 调用。
- Repository/Adapter 实现 port；它们不能绕过 application 直接改变其他业务 owner。
- 所有 Chat/SimC 查询和写入必须从已认证 `Principal.user_id` 注入 owner；客户端传入的 `user_id` 永不可信。

## 目标 Owner

| Owner | 事实与写入边界 | 当前代码/控制面 |
| --- | --- | --- |
| `identity` | 内部用户、微信身份映射、独立客户端会话、Web 登录票据 | `server/app/identity` |
| `chat` | 会话、消息、AgentRun、Codex 流终态 | `server/app/chickenbro` |
| `simc` | 来源快照、任务、尝试、结果、runtime identity 与受管 runtime 更新 | `server/app/simulation`、`server/chickenbro_simc_runtime_update.sh` |
| `worker` | `ops.job_queue` lease、重试、取消和 handler dispatch | `server/app/worker` |
| `dual_client` | Mini/Web 路由、认证 transport、共享 view model | `apps/mini-taro/src`、`packages/api-client/src`、`packages/domain/src` |
| `migration` | 白名单、source-to-target 映射、全量/delta 和核对报告 | [生产 Runbook](chickenbro-simc-production-runbook.md) |
| `deployment` | Candidate、切流、Nginx/systemd/DSN identity 和回滚 | [生产 Runbook](chickenbro-simc-production-runbook.md) |
| `legacy_retirement` | 精确 keep/migrate/delete、调用图、清理与恢复证据 | [处置规则](refactor/chickenbro-simc-disposition-rules.json) |

[project-owner-map.json](project-owner-map.json) 与 [backend-owner-map.json](backend-owner-map.json) 是当前代码 owner 与验证入口；不在这两个 map、当前路线图或 Runbook 可达图中的旧 owner 记录没有新实现、promotion 或范围扩张权。

## 身份与会话

### Principal

Domain 只接收：

```text
Principal {
  user_id: UUID
  session_kind: mini_bearer | web_cookie
}
```

共享的是 `user_id` 和业务数据，不是 Cookie、Bearer、OpenID 或其他凭据。一个请求只能使用一种 credential transport；同时携带两种凭据、把 Mini token 放进 Cookie 或把 Web token 放进 Bearer 都必须失败。

### 小程序登录

```text
wx.login
  -> POST /api/v2/auth/wechat/mini/exchange
  -> 服务端 code2Session
  -> identity.user_identities(provider=wechat_mini, provider_subject=OpenID)
  -> Mini Bearer Session
```

OpenID 只存在于服务端 identity adapter/repository 边界。`session_key` 不写业务表、不进客户端、不进日志。

### Web 由小程序确认

```text
浏览器创建 login session + browser verifier
  -> 服务端生成短期 opaque scene ticket 的小程序码
  -> 小程序以当前 Mini Principal 明确确认
  -> ticket 绑定相同 user_id
  -> 原浏览器凭 verifier 一次性交换 Web Cookie
```

票据只保存 ticket/verifier/idempotency hash、状态、过期时间和确认 user。目标状态机是：

```text
pending -> confirmed -> consumed
pending -> cancelled | expired
confirmed -> cancelled | expired
```

Phase 2 的 product schema、domain、repository 与 application 已把正式终态统一为 `consumed`；legacy `0039` 中的 `exchanged` 只作为迁移输入保留，不能进入新库或正式 API 状态。

Web Session Cookie 固定为 HttpOnly、Secure 的 `__Host-chickenbro-session`；双提交 CSRF Cookie 固定为 JavaScript 可读、Secure 的 `__Host-chickenbro-csrf`。两者均为 SameSite=Lax、Path=/、无 Domain。Cookie 写请求还必须通过精确 Origin/Host 与常量时间 CSRF 比对；Mini 写请求只使用 Bearer，不使用 Web Cookie/CSRF。混合 Cookie/Bearer 或跨 transport 使用 token 固定拒绝。

二维码确认、取消和过期必须使用带当前状态、verifier 与 deadline 条件的原子 UPDATE；`confirmed -> consumed` 与 Web Session 签发必须在同一个 PostgreSQL 语句/事务中完成。读取后关闭连接的 `FOR UPDATE` 不构成状态锁，禁止作为防重放依据。会话解析还必须联查 `identity.users.status='active'`，禁用账号不能继续使用旧 token。

认证决策只写脱敏、定长的 `ops.audit_events`：request ID、已认证时的内部 user ID、session kind、状态码、时间和粗粒度 reason code。运行角色只有 SELECT/INSERT 权限，不得更新或删除审计证据；token、Cookie、OpenID、session key、verifier、ticket 和 secret 不得进入审计 payload。

## 数据模型

干净生产库名为 `chickenbro_prod`，只允许以下业务表：

| Schema | 表 | 核心不变量 |
| --- | --- | --- |
| `identity` | `users` | `id` 是唯一业务 owner |
| `identity` | `user_identities` | `(provider, app_context, provider_subject)` 唯一；不按昵称猜合并 |
| `identity` | `auth_sessions` | 只存 token hash；Mini/Web 独立撤销和过期 |
| `identity` | `web_login_sessions` | ticket/verifier hash、状态与单次消费 |
| `chat` | `conversations` | 每行绑定一个 owner，active/archived |
| `chat` | `messages` | owner/conversation 一致；正文追加写；客户端消息 ID 幂等 |
| `chat` | `agent_runs` | 用户/助手消息关联；成功前助手消息必须已持久化 |
| `simc` | `source_snapshots` | 不可变；来源、revision、raw hash、provenance 完整 |
| `simc` | `simulation_jobs` | owner、snapshot、scenario/compiler/runtime identity 固定 |
| `simc` | `simulation_attempts` | 每次 Worker 尝试独立记录，不用 return code 代替业务成功 |
| `simc` | `simulation_results` | 不可变；有效指标、profile hash 和 runtime provenance |
| `ops` | `schema_migrations` | 干净 schema identity |
| `ops` | `job_queue` | lease/retry/cancel；只承载目标异步命令 |
| `ops` | `audit_events` | 脱敏安全、迁移和切流事件 |
| `ops` | `usage_counters` | 有界用量计数，不承载产品事实 |

禁止在新库创建 `content`、`cache`、`knowledge`、`analytics`、旧 `app`、WebSim、gear 或 talent schema/table。

`wow_app` 只获得业务运行所需的 SELECT/INSERT/UPDATE；Identity、Chat、SimC、job queue 与 usage counters 均无直接 DELETE，schema/database CREATE 也保持关闭。账号或历史删除只能由后续受控清理或管理角色路径完成。

## Chat 语义

Chat 的服务端事实流是：

1. 验证 owner、conversation、消息长度、`Idempotency-Key` 和 `clientMessageId`。
2. 追加用户消息并创建 `streaming` AgentRun。
3. 只调用原生 Codex adapter，按严格递增 sequence 输出 SSE。
4. 完整且合法的 assistant 文本先持久化，再把 AgentRun 置为 `succeeded`。
5. Codex 不可用、超时、输出非法或持久化失败时，用户消息保留，AgentRun 进入明确失败；不切换普通 LLM，不写模板答案。

列表按 `(updated_at, id)` 使用稳定游标。重连从持久化消息/AgentRun 恢复，不能再次调用模型伪造相同 run。第二个用户访问第一个用户的 ID 时对外返回 404，避免枚举。

## SimC 语义

SimC 的服务端事实流是：

1. Raider.IO/WCL adapter 产生候选来源快照。
2. 唯一 readiness validator 给出 `READY_FOR_SIMC` 或稳定 blocker。
3. 唯一 compiler 固定 scenario、profile hash、compiler revision 和 runtime revision。
4. Application 按 owner + idempotency 创建 job，并向 `ops.job_queue` 写入同 ID 命令。
5. Worker 持有有效 lease 后才把 job 置为 running，记录独立 attempt，调用已安装的云端 SimC。
6. return code、stdout 和最终指标经过语义解析；只有正数有效 DPS/HPS、匹配 identity 和无致命诊断才可写不可变 result 并置成功。

正式主链不重新接入旧 Gear Catalog、Talent Catalog、Resolver、Manifest 或 WebSim profile。来源数据不完整、权限受限、角色不存在和 provider 不可用必须保持不同 blocker。

### SimC 运行时维护

`/opt/wow-simc/current` 仍是唯一受管 SimC runtime 指针，但旧 `wow-simc-runtime-update` 与版本检查 timer 不再拥有它。新 owner 是 `server/chickenbro_simc_runtime_update.sh` 和静态、手工触发的 `chickenbro-simc-runtime-update.service`。

更新器不解析“最新分支”，只接受操作者明确给出的 40 位 commit 和当前 commit 乐观锁。默认 dry-run 不联网、不下载、不构建、不切换；apply 才允许从固定 `simulationcraft/simc` commit 下载源码，在同一文件系统的临时目录构建与校验，并原子切换 `current`。新建 release 保存 commit、source archive SHA 和 binary SHA；首次接管的旧 release 若找不到原始 archive，会明确记录 `legacy-unavailable`，但仍绑定实际 binary SHA。旧 release 不删除，更新器也不启停 API/Worker。由任务结果绑定 runtime revision，而不是把 service 成功或 binary return code 当成业务成功。

## Worker Lease

`ops.job_queue` 使用 PostgreSQL `FOR UPDATE SKIP LOCKED` 认领：

- queued 且到达 `available_at` 的 job 可以认领；过期 running lease 可以重新认领。
- 认领原子增加 attempt，并写 `lease_owner`、`lease_expires_at`、heartbeat。
- heartbeat/succeed/fail 只有当前 lease owner 能更新；影响行数不是 1 时抛 `LostLeaseError`。
- retryable 错误只在 `attempt < max_attempts` 且未取消时回到 queued。
- 最后一次 attempt 因 Worker 中断而 lease 过期时，恢复领取只原子收口未完成 attempt 与业务 job 为 `ATTEMPT_EXHAUSTED`，不再执行 SimC。
- 未注册 handler 固定失败为 `UNKNOWN_JOB_HANDLER`，不能无限重试。
- 取消 queued job 立即终态；running job 只记录 cancel request，由 handler/lease 路径收口。

Worker active 只证明进程活着。业务成功还需要 job/result/attempt 与 compiler/runtime identity 的一致证据。

## 正式 API 参考

### 正式身份 API

| Method | Path | Credential | 用途 |
| --- | --- | --- | --- |
| POST | `/api/v2/auth/wechat/mini/exchange` | public + 微信 code | 建立 Mini Session |
| POST | `/api/v2/auth/wechat/mini/web-login-confirm` | Mini Bearer | 确认 browser-bound Web ticket |
| POST | `/api/v2/auth/wechat/web/login-sessions` | exact Web Origin | 创建短期登录票据 |
| GET | `/api/v2/auth/wechat/web/login-sessions/{id}` | browser verifier | 查询票据状态 |
| POST | `/api/v2/auth/wechat/web/login-sessions/{id}/exchange` | exact Origin + verifier | 单次换取 Web Cookie |
| POST | `/api/v2/auth/wechat/web/login-sessions/{id}/cancel` | exact Origin + verifier | 取消票据 |
| GET | `/api/v2/me` | Mini Bearer 或 Web Cookie | 读取当前内部账号摘要 |
| POST | `/api/v2/auth/logout` | 当前客户端会话 | 只撤销当前会话 |

### 正式 Chat API

| Method | Path | 语义 |
| --- | --- | --- |
| GET | `/api/v2/chat/conversations?cursor=&limit=` | owner-scoped 稳定游标列表 |
| POST | `/api/v2/chat/conversations` | 幂等创建会话 |
| GET | `/api/v2/chat/conversations/{conversation_id}` | 会话与持久化消息 |
| POST | `/api/v2/chat/conversations/{conversation_id}/messages/stream` | 幂等消息 + 严格 SSE |

### 正式 SimC API

| Method | Path | 语义 |
| --- | --- | --- |
| POST | `/api/v2/simc/snapshots` | 解析来源并保存不可变快照 |
| GET | `/api/v2/simc/snapshots/{snapshot_id}` | owner-scoped 快照/readiness |
| GET | `/api/v2/simc/jobs?cursor=&limit=` | owner-scoped 稳定任务历史 |
| POST | `/api/v2/simc/jobs` | 幂等提交 ready snapshot |
| GET | `/api/v2/simc/jobs/{job_id}` | job、attempt、result 和 provenance |

### 健康 API

| Method | Path | 证明范围 |
| --- | --- | --- |
| GET | `/health` | API 进程 liveness，不证明业务可用 |
| GET | `/api/v2/health/readiness` | 分组件状态；必须逐项检查 code/status |

任何正式客户端调用 `/api/v2/prototype/**` 都是阻断性缺陷。

## 双端路由

小程序最终只注册：

```text
pages/chickenbro/index       # Tab: 队长
pages/simc/index             # Tab: SimC
pages/simc/tasks
pages/simc/task-detail
pages/auth/web-login-confirm # 辅助认证，不进 TabBar
```

Web 复用相同 domain guard、typed client 与 Chat/SimC feature model，但使用独立 Web Shell 和 Cookie/CSRF transport。客户端本地存储只保存有界 Mini Session 或渲染缓存；刷新后的业务事实必须从服务端重建。

## 迁移与切流

迁移只接受能精确绑定正式 `wechat_mini` identity 且通过 owner、外键、顺序、终态和内容 hash 校验的 Chat/SimC 记录。旧 auth session、prototype、news、WebSim、gear、talent 和无法确定 owner 的记录全部拒绝。

流程固定为一次 candidate 全量、一次写栅栏后的只读 delta、逐域核对和单写入口切换。新系统接受第一条正式写入后，legacy 永久保持只读；不得回开旧库写入口、长期双写或做反向猜测同步。详细步骤见 [生产 Runbook](chickenbro-simc-production-runbook.md)。

## 信任与完成边界

- 自动测试不能代替真实微信登录、扫码确认和跨端用户验收。
- Candidate、生产切流、legacy 删除是三个独立门禁。
- 没有独立恢复副本和恢复验证时，不得用删除旧数据解决容量问题。
- 删除必须绑定精确 manifest SHA、零活动引用、零连接/open handle 和书面回滚窗口状态。
- 最终完成需要本地 `main`、`origin/main`、云端部署、migration identity、API/Worker smoke 和真实双端业务验收分别有证据。

## 相关文档

- [生产 Runbook](chickenbro-simc-production-runbook.md)
- [验证矩阵](verification-matrix.md)
- [项目状态](project-state.json)
- [当前计划白名单](plans/README.md)
- [批准规格](superpowers/specs/2026-09-02-chickenbro-simc-total-rebuild-design.md)
