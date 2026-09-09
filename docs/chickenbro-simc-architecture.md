# Chickenbro Web-only / QQ 架构

状态：2026-09-09 已授权重构，当前代码与真实上线验证状态见 [计划](plans/2026-09-09-web-only-qq.md)。

## 当前目标与身份边界

Web 是唯一产品客户端；保留 Taro H5、React、typed domain/API client 及服务端 Chat/SimC/Worker。小程序专用页面不进入 H5 可执行路由，微信换码和扫码确认入口退役。

QQ 网站授权流程：用户点击登录 → 同源 POST 创建随机一次性 state 和 HttpOnly 浏览器绑定 → QQ 官方授权 → 固定后端 callback 校验 state、绑定、时效及应用身份 → 服务端映射 QQ OpenID → 签发 Web Session / CSRF Cookie → 返回网站。

正式回调：`https://www.chickenbro.cloud/api/v2/auth/qq/callback`。错误只使用固定同源页面和有限错误码，不能由客户端任意指定跳转。授权码、AppKey、QQ token 不进入日志、前端响应或业务数据；登录尝试的消费必须在数据库中原子进行，跨进程也只能成功一次。

`identity.users.id` 继续拥有 Chat/SimC 数据。QQ 按 provider/appid/openid 创建单独用户；旧微信历史保留但不迁移、不按昵称头像合并。旧微信认证和 Mini Bearer 不得获得 QQ Web 身份。已有测试账号仅限显式隔离环境。

既有 Web Cookie 的 Secure、HttpOnly、SameSite=Lax、Path=/ 和 Origin/CSRF 写请求防护保留。保留账号级单回复互斥、Chat/SimC 幂等、队列租约、第二用户隔离及云端 SimC 语义验证。

## 历史 1.0 双端架构参考

以下内容解释 1.0 的实现与历史验收；其中 Mini、微信登录、跨端合同均已被上面的当前产品决定取代，不可用于恢复小程序产品或授权删除旧数据。

# 炸鸡队长与 SimC 双端架构

状态：历史 1.0 实现参考，当前边界以上文 Web-only / QQ 为准

本架构定义重构后的唯一产品边界：微信小程序和 Web 只提供炸鸡队长会话与 SimC 任务。两端使用不同的客户端会话，但服务端都把它们解析成同一个内部 `user_id`，因此共享同一份服务端业务历史。

本文件是 1.0 实现说明与接口参考。产品验收、仓库提交、在线部署与微信公开版本分别以 [项目状态](project-state.json) 和 [版本说明](releases/1.0.md) 记录。

## 用户承诺

同一微信用户登录任一端后，可以看到并继续自己的全部有效会话，也可以查看自己的全部有效 SimC 快照、任务、尝试和结果。任一端创建的数据在另一端以相同 ID、顺序、状态和结果出现。

以下内容不属于“同步所有数据”：OpenID、`session_key`、Cookie、Bearer、微信 access token、第三方凭据、模型思维链、内部日志、prototype/demo 数据，以及迁移完整性校验拒绝的旧记录。

## 1.0 当前实现

2026-09-08 用户确认 1.0 当前实现完成。以下描述仓库行为；各运行面的部署身份与平台发布状态见 [1.0 说明](releases/1.0.md)。早期六阶段迁移/清理已经完成，`project-state.json.refactorEvidence` 保留 2026-09-04 历史证据，不作为现在的在线清单。

| 能力 | 当前实现 |
| --- | --- |
| Identity | Mini Bearer 与 Web HttpOnly Cookie 分离，Origin/CSRF、单次票据及服务端 owner 映射 |
| Chat | 服务端共享历史、幂等发送、持久化回放、公开进展/完成时间、账号级单回复、软删除、双端共享且不可修改的回答解决情况反馈 |
| SimC | Raider.IO 导入快照（保留历史 WCL 快照）、readiness、compiler、PostgreSQL queue、云端 Worker、语义结果、任务 ID 换装重跑 |
| Mini | 5 条页面路由、2 个 Tab；历史抽屉、FAQ/更新日志、任务 ID 复制；取消账号与外观面板 |
| Web | `/` 对话、`/simc` 模拟、`/?view=faq` FAQ；扫码登录、账号菜单、七种静态插画主题 |
| 数据面 | 正式产品仅 Identity/Chat/SimC/Ops，`chickenbro_prod`；旧 `wow_test` 和 legacy 运行面已退役 |

当前 Mini 页面没有头像选择入口；移除设置面板不改变身份服务、已保存头像数据与 Web 会话隔离。Mini 不再提供主动退出/主题选择入口，已有 signedOut 恢复及设备主题读取兼容保留。两端共享的是业务数据，不包括设备本地外观状态。

## 运行拓扑

```text
微信小程序 -- Mini Bearer -----\
                               > API/BFF -> Principal(user_id, session_kind)
Web/H5 ---- HttpOnly Cookie ---/                   |
                                                   +-> Identity
                                                   +-> Chat -> chat.executions -> Worker -> Codex Adapter
                                                   +-> SimC -> ops.job_queue -> Worker
                                                                  |            |
                                                                  |            +-> cloud SimulationCraft
                                                                  +-> Raider.IO adapter
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
| `worker` | `ops.job_queue` lease、重试和 handler dispatch | `server/app/worker` |
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

二维码和 scene 明文只存在于生成它们的 API 进程内，数据库仍只保存 hash。进程内对同一 verifier 与 `Idempotency-Key` 的创建请求串行合并；二维码重放缓存同时受票据 TTL 和固定条目上限约束，进入 `cancelled`、`expired` 或 `consumed` 后立即释放。PostgreSQL 插入使用唯一约束兜住跨进程竞争；竞争失败或同一幂等创建请求跨越进程重启时，服务端返回 `WEB_LOGIN_RESTART_REQUIRED`。Web 端只在这个明确不可恢复的错误下丢弃旧请求身份并生成新二维码，普通网络结果不确定时仍复用原 verifier 与 `Idempotency-Key`。

Web 登录检查、二维码创建、状态轮询、确认交换、取消和退出共用单调 intent generation；新用户操作和页面卸载会使旧响应失效。观察到 `confirmed` 后立即停止状态轮询，只由 exchange 响应落 Cookie 并恢复账户；晚到的 `pending`/`consumed` 状态不能复活终态二维码，也不能抢在 `Set-Cookie` 前把界面错误地退回未登录。

Web Session Cookie 固定为 HttpOnly、Secure 的 `__Host-chickenbro-session`；双提交 CSRF Cookie 固定为 JavaScript 可读、Secure 的 `__Host-chickenbro-csrf`。两者均为 SameSite=Lax、Path=/、无 Domain。Cookie 写请求还必须通过精确 Origin/Host 与常量时间 CSRF 比对；Mini 写请求只使用 Bearer，不使用 Web Cookie/CSRF。混合 Cookie/Bearer 或跨 transport 使用 token 固定拒绝。

Identity API 的请求体拒绝额外字段，并在调用微信 provider 前完成 verifier、code 与 scene 的长度和字符边界校验。双端 response guard 只接受每个端点约定的精确字段集合和可选 `requestId`；任何额外的 `userId`、OpenID、token 或其他身份字段都按非法响应失败关闭。

账号头像是可选的 Identity 展示字段，不是登录条件。当前 Mini 未挂载头像选择组件；历史 `chooseAvatar` 组件与头像 API 合同保留兼容，不能据其代码存在宣称现有页面提供选择入口。头像上传路径接收主动选择并压缩后的图片；服务端只接受有界 PNG/JPEG 数据，剥离元数据并按 Principal 更新 `identity.users.avatar_data_url`。两端通过独立认证读取，响应禁止缓存；不返回公共图片 URL，也不根据昵称或图片推断身份。原 `/me` 合同保持兼容。

公开展示名与 `identity.users.display_name` 共用 256 字符上限；正式迁移、API 和双端 response guard 必须接受完整的合法持久化范围，不能因客户端采用更窄的历史边界而阻断已迁移用户登录。客户端只展示该字段，不把它当作账号合并或授权依据。

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
| `ops` | `job_queue` | lease/retry；只承载目标异步命令 |
| `ops` | `audit_events` | 脱敏安全、迁移和切流事件 |
| `ops` | `usage_counters` | 有界用量计数，不承载产品事实 |

禁止在新库创建 `content`、`cache`、`knowledge`、`analytics`、旧 `app`、WebSim、gear 或 talent schema/table。

`wow_app` 只获得业务运行所需的 SELECT/INSERT/UPDATE；Identity、Chat、SimC、job queue 与 usage counters 均无直接 DELETE，schema/database CREATE 也保持关闭。对话删除通过业务层 owner 校验与 archived 状态软删除，使用 UPDATE；物理清理仍由独立受控路径完成。

## Chat 语义

Chat 的服务端事实流是：

1. 验证 owner、conversation、消息长度、`Idempotency-Key` 和 `clientMessageId`。
2. 同一事务追加用户消息、`streaming` AgentRun 与 `pending` execution；准入总量最多 32。
3. 独立 Worker 的 Chat lane 领取一次执行权，只调用原生 Codex adapter；API 订阅持久化公开进展/正文，以严格递增 sequence 输出 SSE。
4. 完整且合法的 assistant 文本先持久化，再把 AgentRun 置为 `succeeded`。
5. Codex 不可用、超时、输出非法或持久化失败时，用户消息保留，AgentRun 进入明确失败；不切换普通 LLM，不写模板答案。

2026-09-07 新增公开摘要与回复时间契约（API/Web 已部署，小程序已上传验证版，用户验收待完成）：新客户端在 Chat GET/stream 使用 `includeProgress=true`，接收独立 `progress` 事件、终态 `completedAt`/`durationMs` 与历史消息的 `progress` 对象。公开摘要仅来自 Codex `item/reasoning/summaryTextDelta`；最多 16000 个 Unicode code point，先保存至 owner-scoped AgentRun 后发送。超限仅截断摘要，不终止正文。原始思维链、commentary 和工具 payload 仍不公开。耗时从服务端 `started_at`/`finished_at` 计算，失败展示由 AgentRun 投影，不伪造 assistant 正文。旧客户端不显式启用时继续接收原事件、连续序号和历史字段。

列表按 `(updated_at, id)` 使用稳定游标。重连从持久化消息/AgentRun 恢复，不能再次调用模型伪造相同 run。第二个用户访问第一个用户的 ID 时对外返回 404，避免枚举。

启用 `WOW_CHAT_DURABLE_ENABLED=1` 时，API 断流、退出或重启只影响订阅，不能取消已落库执行。未领取任务可由 Worker 领取；已领取任务不自动重放。Worker 以 30 秒租约、10 秒心跳和随机令牌保护写入，拿到行锁后再次核对实际时间。Worker 中断后，Worker sweeper 或 owner 的历史读取/订阅/发送将过期执行收口为可重试的 `CODEX_EXECUTION_FAILED`；超过 540 秒未领取的准入也明确失败。已提交成功答案但尚未确认 execution 的情况保留成功。旧模式和未含 execution 的历史仍兼容原回放。

Worker 自有 loopback 工具网关与短期能力，不依赖 API 进程内 token。每次运行最多记录 128 次有界工具调用结果，仅服务端可见；SimC 写入使用同一个租约保护连接及原有幂等合同。结果不用于自动重放未知副作用，也不声称任意恢复 Codex 会话。WCL 静态战斗上下文仅在单个 run 内按报告/战斗/角色复用 60 秒，事件筛选仍独立查询；独立查询最多合并 3 个，游标翻页保持顺序。研究预算耗尽或结果过大明确返回不足，不伪造完整证据。

会话标题与 `chat.conversations.title` 共用 256 字符上限；正式迁移、创建 API、application 和双端 response guard 必须接受同一完整范围。白名单迁移允许保留空标题，双端对空标题统一显示“炸鸡队长对话”，但不改写持久化事实。

## SimC 语义

SimC 的服务端事实流是：

1. Raider.IO/WCL adapter 产生候选来源快照。
2. 唯一 readiness validator 给出 `READY_FOR_SIMC` 或稳定 blocker。
3. 唯一 compiler 固定 scenario、profile hash、compiler revision 和 runtime revision。
4. Application 按 owner + idempotency 创建 job，并向 `ops.job_queue` 写入同 ID 命令。
5. Worker 持有有效 lease 后才把 job 置为 running，记录独立 attempt，调用已安装的云端 SimC。
6. return code、stdout 和最终指标经过语义解析；只有正数有效 DPS/HPS、匹配 identity 和无致命诊断才可写不可变 result 并置成功。
7. Application 在列表和详情读取时再次核对成功状态、result owner/job、JSON 与列指标、独立 `provenance_json`、不可变 source snapshot、profile/compiler/runtime/scenario；四层来源 revision/hash 任一不一致统一返回 `SIMC_RESULT_INVALID`，不能以 200 成功或不完整结果交给任一客户端。可进入 ready/result 公共契约的 source revision 上限固定为 160 字符。

正式主链不重新接入旧 Gear Catalog、Talent Catalog、Resolver、Manifest 或 WebSim profile。来源数据不完整、权限受限、角色不存在和 provider 不可用必须保持不同 blocker。

### SimC 运行时维护

`/opt/wow-simc/current` 仍是唯一受管 SimC runtime 指针，但旧 `wow-simc-runtime-update` 与版本检查 timer 不再拥有它。新 owner 是 `server/chickenbro_simc_runtime_update.sh` 和静态、手工触发的 `chickenbro-simc-runtime-update.service`。

更新器不解析“最新分支”，只接受操作者明确给出的 40 位 commit 和当前 commit 乐观锁。默认 dry-run 不联网、不下载、不构建、不切换；apply 才允许从固定 `simulationcraft/simc` commit 下载源码，在同一文件系统的临时目录构建与校验，并原子切换 `current`。新建 release 保存 commit、source archive SHA 和 binary SHA；首次接管的旧 release 若找不到原始 archive，会明确记录 `legacy-unavailable`，但仍绑定实际 binary SHA。旧 release 不删除，更新器也不启停 API/Worker。由任务结果绑定 runtime revision，而不是把 service 成功或 binary return code 当成业务成功。

## Worker Lease

`ops.job_queue` 使用 PostgreSQL `FOR UPDATE SKIP LOCKED` 认领：

- queued 且到达 `available_at` 的 job 可以认领；过期 running lease 可以重新认领。
- 认领原子增加 attempt，并写 `lease_owner`、`lease_expires_at`、heartbeat。
- heartbeat/succeed/fail 只有当前 lease owner 能更新；影响行数不是 1 时抛 `LostLeaseError`。
- retryable 错误只在 `attempt < max_attempts` 时回到 queued。
- 最后一次 attempt 因 Worker 中断而 lease 过期时，恢复领取只原子收口未完成 attempt 与业务 job 为 `ATTEMPT_EXHAUSTED`，不再执行 SimC。
- 未注册 handler 固定失败为 `UNKNOWN_JOB_HANDLER`，不能无限重试。

当前正式 SimC API 不提供任务取消。`simulation_jobs.cancelled` 只用于保存通过白名单验收的历史终态；新任务队列不暴露只更新 queue、不同时更新业务 job 的半成品取消操作。后续若增加取消，必须先定义公开 API，并在同一事务中收口 queue、attempt 与 `simulation_jobs`。

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
| GET | `/api/v2/me/avatar` | Mini Bearer 或 Web Cookie | 读取当前账号已选择的头像，仅本人可读 |
| PUT | `/api/v2/me/avatar` | Mini Bearer | 保存用户主动选择的 PNG/JPEG 头像 |
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

正式 readiness 只从可重复验证的本地运行条件生成：数据库执行只读 `SELECT 1`；Worker 在成功访问队列后写入当前环境和固定 Worker ID 专用、0600、原子替换的心跳文件，并在长任务 lease 续约时刷新；Codex 的已启用状态、实际可执行文件 SHA-256 与配置 revision 必须一致；Raider.IO 所需 HTTP dependency 必须可加载；WCL 必须具备完整 v2 OAuth client credentials，Chat 与 SimC 共用服务端短期 token provider；SimC 的 `current` 必须解析到 content-addressed release，`.commit`、`binary.sha256`、source archive identity、实际 binary hash、compiler revision 与支持 spec 必须相符；微信组件只核对小程序凭据配置。Worker unit 每次启动先删除本环境旧心跳，避免上一进程的短期残留冒充新进程。

这些 probe 不在每个 readiness 请求中访问 Raider.IO、WCL、微信或 Codex 上游，也不执行真实模拟。`ready` 只说明候选具备发起正式链路的本地配置、身份和 Worker liveness；真实 provider 响应、Codex SSE、SimC 语义结果、扫码和跨端同步仍必须由候选自动化与真实用户验收分别证明。

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

Web 复用相同 domain guard、typed client 与 Chat/SimC feature model，但使用独立 Web Shell 和 Cookie/CSRF transport。客户端本地存储只保存有界 Mini Session 或渲染缓存；刷新后的业务事实必须从服务端重建。所有异步列表、详情、来源解析、任务提交、轮询和流恢复都遵循“最后一次用户意图获胜”：旧响应可以在不冲突时补充服务端列表，但不得覆盖较新的选择、流、阶段或错误状态；页面卸载后未完成响应一律失效。同一时刻的重复 Chat 创建、消息发送和 SimC 提交还必须在客户端合并，并由服务端幂等键再次兜底。

## 迁移与切流

迁移只接受能精确绑定正式 `wechat_mini` identity 且通过 owner、外键、顺序、终态和内容 hash 校验的 Chat/SimC 记录。旧 auth session、prototype、news、WebSim、gear、talent 和无法确定 owner 的记录全部拒绝。

流程固定为一次 candidate 全量、一次写栅栏后的只读 delta、逐域核对和单写入口切换。新系统接受第一条正式写入后，legacy 永久保持只读；不得回开旧库写入口、长期双写或做反向猜测同步。详细步骤见 [生产 Runbook](chickenbro-simc-production-runbook.md)。

## 信任与完成边界

- 自动测试不能代替真实微信登录、扫码确认和跨端用户验收；本轮用户已明确授权测试版登录跳过，验收报告必须写 `loginMode=user_authorized_skipped` 和 `realWechatQrLogin.status=skipped`，不得把跳过写成扫码成功。
- Candidate、生产切流、legacy 删除是三个独立门禁。
- 默认没有独立恢复副本和恢复验证时，不得用删除旧数据解决容量问题；本轮用户已明确授权无备份永久清理，但只允许通过带有不可逆确认词的精确脚本，并且仍受迁移核对、生产验收、首条新写入、稳定健康和零引用门禁约束。
- 删除必须绑定精确 manifest SHA、零活动引用、零连接/open handle 和书面回滚窗口状态。
- 最终完成需要本地 `main`、`origin/main`、云端部署、migration identity、API/Worker smoke 和真实双端业务验收分别有证据。

## 相关文档

- [生产 Runbook](chickenbro-simc-production-runbook.md)
- [验证矩阵](verification-matrix.md)
- [项目状态](project-state.json)
- [当前计划白名单](plans/README.md)
- [批准规格](superpowers/specs/2026-09-02-chickenbro-simc-total-rebuild-design.md)
