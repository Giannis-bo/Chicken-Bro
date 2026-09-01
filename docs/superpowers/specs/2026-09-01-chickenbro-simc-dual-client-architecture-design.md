# 炸鸡队长与 SimC 双端精简架构设计

日期：2026-09-01
状态：架构已确认；技术细节由 Codex 按最佳实践收敛；不授予部署或生产切换权
范围：微信小程序、独立 Web、统一微信账号、炸鸡队长、Raider.IO/WCL 角色快照、SimC 任务

## 1. 结论

下一代产品只保留两个业务域：炸鸡队长和 SimC。资讯、天赋模拟、装备模拟、旧 WebSim 工作台及其一级入口全部退出目标产品；登录、历史记录、任务查询、运行健康和审计属于共享基础能力，不形成新的业务模块。

客户端继续使用一套 Taro/React 业务代码，分别构建微信小程序和部署在独立 HTTPS 网址的 Web/H5。两端各自完成微信认证并持有独立会话，通过同一个内部 `user_id` 共享炸鸡队长会话记录和 SimC 任务记录。

后端采用模块化单体 API、独立异步 Worker、共享 PostgreSQL 和既有云端 SimulationCraft runtime。代码在一个仓库内保持清晰领域边界，不立即引入微服务、Redis、Kafka、Celery、独立数据库或通用插件平台。

炸鸡队长保留当前原生 Codex 对话方向：Codex 是理解、分析和工具选择主体。后端只保留身份、隐私、只读工具权限、请求预算、超时、流式协议和持久化边界，不再用问题分类树、数字白名单或逐 claim 门禁替 Codex 决定答案。Codex 不可用时明确失败，不静默换成另一套 LLM 或伪造确定性回答。

SimC 采用两个来源 Adapter、一个统一 `CharacterSnapshot`、一个 readiness validator、一个 profile compiler 和一个云端执行器。Raider.IO 与 WCL 不直接拼接最终 profile，也不复用旧装备/天赋模拟的 Catalog、Resolver 或 Manifest 作为新链路的事实来源。

## 2. 用户目标和完成体验

### 2.1 用户目标

玩家在小程序或独立 Web 中登录同一个微信账号后，可以：

1. 在任一端继续同一组炸鸡队长会话；
2. 提交 Raider.IO 或 WCL 链接，生成来源语义明确的角色快照；
3. 在输入完整后创建 SimC 任务，查看排队、运行、失败和完成状态；
4. 在任一端查看相同的 SimC 历史和结果；
5. 把一个已有 SimC 结果交给炸鸡队长解释，而不复制完整 profile 或跨域泄露数据。

### 2.2 用户可见完成标准

- 小程序和 Web 的登录会话可以分别失效，但两端识别为同一内部用户；
- 两端展示相同 owner 下的会话和 SimC 任务，且不能读取其他用户数据；
- 炸鸡队长自然对话可流式返回，失败时保留真实用户消息并提供可重试状态；
- 合法链接、来源可访问、快照完整和 SimC-ready 是四个不同结论；
- WCL 快照明确标注 report、revision、fight、actor 和抓取时间；
- Raider.IO 快照明确标注最近抓取时间和国服隐私/授权状态；
- SimC 只有在 profile 完整、runtime 支持且最终输出包含有效语义指标时才显示成功；
- 旧资讯、天赋模拟和装备模拟不再出现在新导航、新 API 或新数据主链中。

## 3. 非目标

本架构不包含：

- 把小程序 Cookie、`session_key`、OpenID 或微信 access token直接复用到 Web；
- 让 Codex 直接访问数据库、Shell、服务器文件、密钥或任意写操作；
- 用 Raider.IO/WCL 覆盖、证明或恢复旧装备 Catalog；
- 从 WCL 快照承诺复刻日志 DPS、完整战斗脚本或团队增益；
- 在第一版加入多租户组织、付费计费、通用工作流引擎、向量数据库或消息中间件；
- 在新链路稳定前删除生产 last-known-good 或切换正式域名流量；
- 把当前测试数据迁移完整性作为上线门槛。现有数据可重建，但新 schema 和 owner 规则按正式产品质量实现。

## 4. 架构决策

### 4.1 方案比较

| 方案 | 判断 |
| --- | --- |
| 模块化单体 API + 独立 Worker | 采用。复用现有 Python/PostgreSQL/SimC 运行环境，边界清晰且运维成本可控 |
| 立即拆分 Identity、Chat、SimC 微服务 | 不采用。当前规模不足以抵消分布式事务、队列、观测和部署成本 |
| 保留 `news_backend.py` 并仅删除路由 | 不采用。会继续把身份、聊天、SimC、来源和旧模块耦合在一个超大文件中 |

### 4.2 顶层拓扑

```mermaid
flowchart TB
  W[独立 Web/H5] --> B[API / BFF]
  M[微信小程序] --> B
  B --> I[Identity]
  B --> C[Chickenbro]
  B --> S[Simulation]
  I --> P[(PostgreSQL)]
  C --> P
  S --> P
  C --> X[Codex Adapter]
  X --> O[Codex]
  S --> J[PostgreSQL Job Queue]
  J --> R[Worker Runtime]
  R --> A[Raider.IO Adapter]
  R --> L[WCL Adapter]
  R --> E[SimC Adapter]
  E --> SC[/opt/wow-simc/current]
```

逻辑组件不是网络服务边界。`Identity`、`Chickenbro` 和 `Simulation` 在同一 API 部署单元内，通过应用端口协作；Worker 使用同一套领域代码执行异步命令。

## 5. 部署单元

### 5.1 Web/H5

- `apps/mini-taro` 继续构建 `h5`；
- 独立域名由 Nginx 提供静态文件和 HTTPS；
- Web 域名将 `/api/` 与 `/auth/` 反向代理到 API，使浏览器使用同源 HttpOnly Cookie，避免在前端 JavaScript 中持久化 Web token；
- 首版保留 hash router，减少服务器 rewrite 和 OAuth 回调耦合；页面导航细节后续独立设计。

### 5.2 微信小程序

- 使用同一 Taro feature、domain model 和 typed API client；
- 平台层调用 `wx.login`，将短期 code 交给后端；
- 使用项目 Bearer token，不持有微信 `session_key` 或第三方凭据；
- 小程序专有能力限制在 `platform/weapp`，业务组件不直接调用 `wx.*`。

### 5.3 API

- 新 API 使用 Python ASGI 架构，实施时采用 FastAPI、Pydantic 和 Uvicorn；
- 原因是类型化路由、依赖注入、SSE、OpenAPI、错误映射和测试隔离优于当前 `http.server` 路由大文件；
- 新 API 暂以 `/api/v2` 并行提供，旧 API 在切流前保持 last-known-good；
- 新依赖的下载和安装在实施计划中单独遵守网络审批规则，本设计不执行安装。

### 5.4 Worker

- Worker 与 API 使用同一 Python package 和 PostgreSQL；
- 使用 `FOR UPDATE SKIP LOCKED` 领取任务，配合 lease、heartbeat、有限重试、取消标记和幂等键；
- 首版不引入 Redis/Celery；真实负载证明 PostgreSQL 队列不足后才评估替换；
- SimC 和来源解析必须走 Worker；短时 Codex 对话继续由 API 流式执行，避免首字延迟和跨进程 token relay。

### 5.5 PostgreSQL 与 SimC

- PostgreSQL 是唯一正式持久层，不保留 SQLite 正式路径；
- 继续使用云端 `/opt/wow-simc/current/simc`，每个结果绑定 runtime revision、compiler revision 和输入 hash；
- 新角色链接链路不依赖旧 Gear Catalog、WebSim Profile、Observed Build Registry 或 Active Manifest；旧链路只在迁移期作为隔离的 legacy runtime 存在。

## 6. 代码和组件边界

目标后端布局：

```text
server/app/
  main.py
  api/
    dependencies.py
    errors.py
    routes/
  identity/
    domain.py
    application.py
    ports.py
    repository.py
  chickenbro/
    domain.py
    application.py
    ports.py
    repository.py
    streaming.py
  simulation/
    domain.py
    application.py
    ports.py
    repository.py
    snapshot.py
    readiness.py
    compiler.py
  integrations/
    wechat_mini.py
    wechat_web.py
    codex.py
    raiderio.py
    warcraftlogs.py
    simulationcraft.py
  platform/
    postgres.py
    config.py
    logging.py
    health.py
  worker/
    main.py
    leases.py
    handlers.py
```

目标前端布局：

```text
apps/mini-taro/src/
  app/
  platform/
    weapp/
    h5/
  features/
    identity/
    chickenbro/
    simulation/
    profile/
  shared/
packages/
  api-client/
  domain/
  design-system/
```

依赖方向固定为：

```text
UI -> typed API client -> API/BFF -> application -> domain -> ports <- adapters
```

强制规则：

- Domain 不导入 FastAPI、PostgreSQL driver、Taro、WCL、Raider.IO、Codex 或 SimC 实现；
- Adapter 可以依赖 Domain port 和规范化 DTO，但不能直接写业务表；
- API route 只做传输、鉴权、校验和 use case 调用，不包含来源或 SimC 规则；
- Worker handler 只领取并执行领域命令，不拥有来源判断；
- `Chickenbro` 只能通过 `SimulationReadPort` 获取 owner-bound 结果，不能查询 `simc` schema；
- 业务表只保存内部 `user_id`，不以 OpenID、UnionID、昵称或客户端 ID 作为 owner。

## 7. 数据所有权

一套 PostgreSQL 实例内使用四个逻辑 schema：

| Schema | Owner | 核心记录 |
| --- | --- | --- |
| `identity` | Identity | users、user_identities、auth_sessions、oauth_states |
| `chat` | Chickenbro | conversations、messages、agent_runs |
| `simc` | Simulation | source_snapshots、simulation_jobs、simulation_results |
| `ops` | Platform | job_leases、audit_events、usage_counters、outbox_events |

### 7.1 追加与不可变规则

- 消息正文、已冻结 `CharacterSnapshot`、SimC profile、运行结果和终态审计只追加，不原地改写；
- conversation 标题、归档状态、OAuth state、任务 lease 等控制字段可以更新；
- 用户补齐输入时生成新的 snapshot revision，不修改已经执行过的 revision；
- 任务结果以 `(user_id, snapshot_id, scenario_hash, runtime_revision, compiler_revision)` 幂等；
- “历史记录”是 `chat` 和 `simc` 的聚合读模型，不复制出第三份历史事实。

## 8. 身份与跨端账号

### 8.1 身份模型

`identity.users.id` 是唯一业务身份。`identity.user_identities` 至少保存：

```text
provider
app_context
provider_subject (OpenID)
unionid
profile_json
```

小程序和 Web 的 OpenID 通常不同。解析顺序为：

1. 先按 `provider + app_context + OpenID` 查找精确 identity；
2. 当 UnionID 存在时，按同一微信开放平台上下文归并到已有 `user_id`；
3. 若 UnionID 冲突，阻断登录归并并写审计，绝不覆盖；
4. UnionID 缺失且两端已有独立账号时，通过双方已认证的显式绑定流程归并；
5. 不使用昵称、头像、服务器角色名或相似 OpenID 猜测同一用户。

### 8.2 小程序登录

```text
wx.login -> /api/v2/auth/wechat/mini/exchange
-> jscode2session -> Identity Resolver -> project Bearer token
```

`session_key` 仅在服务端用于微信能力，不进入客户端、日志或业务表。

### 8.3 Web 扫码登录

```text
/auth/wechat/web/start
-> 生成一次性 state
-> 微信网站应用 snsapi_login
-> /auth/wechat/web/callback
-> code exchange
-> Identity Resolver
-> HttpOnly Secure SameSite=Lax session cookie
```

OAuth state 使用短 TTL、一次性消费和 hash 持久化。Web Cookie 与小程序 Bearer token 独立撤销；共享的是 `user_id` 和业务数据，不是登录态本身。微信开放平台、网站应用审核、UnionID 和回调域名规则在实施前重新核对官方文档。

## 9. 炸鸡队长

### 9.1 领域对象

- `Conversation`：owner、标题、归档状态、创建/更新时间；
- `Message`：conversation、role、正文、客户端幂等 ID、创建时间；
- `AgentRun`：输入 message、Codex runtime、状态、耗时、失败原因、可公开工具观察摘要。

### 9.2 主链

```text
认证用户消息
-> 追加 user Message
-> 创建 AgentRun
-> Codex Adapter 流式执行
-> SSE delta
-> 追加 assistant Message
-> AgentRun terminal
```

Codex 接收当前会话的有界历史、用户明确附加的 SimC 结果引用和可用只读工具。后端不再预生成问题专用 ResearchPlan、不按职业/问法路由固定工具、不要求模型输出内部 JSON，也不以数字白名单或逐 claim 格式拒绝自然回答。

仍然保留的系统边界：

- owner 和授权校验；
- 私有数据最小化；
- 工具 allowlist、只读级别、超时、成本和并发预算；
- SSRF、任意 SQL/Shell/文件和写操作隔离；
- SSE request/session/event/sequence 完整性；
- secret、思维链和原始私有来源不落库；
- 失败不保存 assistant Message，不伪造 fallback 回答。

Codex 是唯一推理/回答 provider。若 Codex 不可用，`AgentRun=failed`，客户端展示重试，不静默切换普通 LLM 或模板回答。

## 10. Simulation

### 10.1 领域组件

- `CharacterSourceRouter`：只根据已校验 URL host/path 选择 Adapter；
- `RaiderIOCharacterAdapter`：产生最近抓取角色快照；
- `WclCharacterAdapter`：产生特定 report/fight/actor 战斗快照；
- `CharacterSnapshot`：来源无关、不可变的规范化输入；
- `SimcReadinessValidator`：逐字段和 runtime 支持校验；
- `SimcProfileCompiler`：唯一 profile 序列化 owner；
- `SimulationJobService`：幂等任务创建、取消和 owner 查询；
- `SimulationCraftAdapter`：stdin 执行、输出解析、超时和 runtime provenance。

### 10.2 `CharacterSnapshot` 最小合同

```text
identity: name, region, realm, class, spec, race, level
talents: import code / canonical talent representation
gear: slot, item id, item level, bonus ids, gems, enchants
source: provider, source url, fetched at, raw hash
runtime: supported expansion/build intent
wcl provenance: report, revision, fight, actor, guid (WCL only)
raiderio provenance: last crawled at, privacy/access state (Raider.IO only)
```

Adapter 只能产生 snapshot candidate，不得返回最终 SimC 字符串。所有来源通过同一个 validator 和 compiler。

### 10.3 来源语义

- Raider.IO：精确解析 region/realm/name 的最近角色观察；不是全服模糊搜索，也不保证游戏内当前状态；
- WCL：精确到报告、revision、fight 和 actor 的战斗快照；角色页、report 存在或 HTTP 200 不等于快照完整；
- WCL 未提供种族时必须进入 `INCOMPLETE_FOR_SIMC`，由用户确认后生成新 revision；
- WCL `playerDetails` 可能变化，用户选定后立即保存规范化快照、原始 hash 和 provenance；
- 不允许把两个来源静默拼成“纯 WCL”或“纯 Raider.IO”快照。若未来允许补充来源，必须显式记录 mixed provenance。

WCL 的 fight 选择、玩家列表和种族确认 UI 属于后续子设计；本父级架构已经提供 `candidate -> incomplete -> revised snapshot -> ready` 的稳定接口，因此这些细节不会改变组件边界。

### 10.4 Readiness

统一状态：

```text
INVALID_LINK
CHARACTER_NOT_FOUND
ACCESS_RESTRICTED
SNAPSHOT_UNAVAILABLE
INCOMPLETE_FOR_SIMC
READY_FOR_SIMC
```

`READY_FOR_SIMC` 至少要求身份、class/spec/race/level、必需装备槽、Bonus/gem/enchant 语义、天赋、来源 provenance、compiler 支持和当前 runtime 支持全部通过。

### 10.5 Profile 和结果语义

- profile 由 compiler 按确定顺序生成并 hash；
- `SimulationScenario` 是独立输入，不写回角色快照；首个实现使用服务器拥有的稳定场景 preset，交互参数后续设计；
- SimC return code 0、stdout 非空或出现任意数字都不构成成功；
- 成功必须包含被严格解析的最终 DPS/指标、正确 actor、非 `race=none`、无致命输入诊断和匹配 runtime revision；
- WCL 快照模拟描述“该构筑在所选 SimC 场景中的预测”，不描述日志实际战斗表现。

## 11. API 和流式合同

高层 API surface：

```text
POST /api/v2/auth/wechat/mini/exchange
GET  /auth/wechat/web/start
GET  /auth/wechat/web/callback
POST /api/v2/auth/logout
GET  /api/v2/me

POST /api/v2/conversations
GET  /api/v2/conversations
GET  /api/v2/conversations/{id}
POST /api/v2/conversations/{id}/messages/stream

POST /api/v2/simc/sources
GET  /api/v2/simc/snapshots/{id}
POST /api/v2/simc/snapshots/{id}/revisions
POST /api/v2/simc/jobs
GET  /api/v2/simc/jobs
GET  /api/v2/simc/jobs/{id}
POST /api/v2/simc/jobs/{id}/cancel
```

所有 owner-bound route 从认证上下文取得 `user_id`，忽略并拒绝客户端提交的 owner 字段。写请求使用 `Idempotency-Key`。错误响应包含稳定 error code、可公开 message 和 request ID，不返回 secret、原始第三方响应或内部堆栈。

SSE 事件至少包含 `requestId / conversationId / runId / sequence / type`。合法类型为 `started`、`delta`、`completed` 和 `failed`；sequence 严格递增，空字符串 delta 非法，但只包含换行或缩进的 Markdown chunk 合法。

## 12. 状态机与错误处理

### 12.1 AgentRun

```text
streaming -> succeeded
streaming -> failed
```

只有持久化 assistant Message 后才能 `succeeded`。客户端断开不自动把成功改为失败；服务端继续到受控终态或按取消预算终止。

### 12.2 SourceSnapshot

```text
resolving -> incomplete -> ready
resolving -> ready
resolving -> failed
incomplete -> revised snapshot
```

补充输入创建新 revision。旧 snapshot 保留其来源语义和 hash。

### 12.3 SimulationJob

```text
queued -> running -> succeeded
queued -> cancelled
running -> failed
running -> cancelled
```

失败按 retry policy 创建新的 attempt，不回写旧 attempt。重复提交相同幂等身份时返回已有 active/terminal job。

### 12.4 错误原则

- transport 200 与业务成功分离；
- 来源不可访问、输入不完整、runtime 不支持、执行超时和结果无指标使用不同 error code；
- 只对明确可重试的网络/临时错误有限重试；认证、权限、INVALID_LINK 和输入缺失不重试；
- 不使用旧缓存、默认角色、默认种族、生成模板或另一数据源掩盖失败；
- API liveness、业务 readiness、外部来源 health 和任务结果分别报告。

## 13. 安全与隐私

- 只允许 `https` 且 host/path 匹配 Raider.IO/WCL allowlist 的链接，禁止重定向到非 allowlist host；
- 第三方 API key、OAuth secret、Codex 配置和 SimC binary 路径仅在服务端；
- 原始来源 payload 与生成 profile 视为 owner-bound 个人数据；日志只保留 hash、状态和脱敏摘要；
- Web 使用同源代理、HttpOnly Secure Cookie、CSRF/Origin 校验和严格 CORS；
- 小程序 Bearer token 只发送给 HTTPS 正式 API；
- 普通用户身份与 `WOW_ADMIN_TOKEN` 管理身份完全分离；
- 不保存模型思维链；Agent trace 只保留运行版本、工具名、公开状态、耗时和引用标识；
- 私有 WCL 报告不在首个公开链接版本中自动读取，未来须有独立用户 OAuth/授权合同。

## 14. 可观测性

至少提供：

- `/health`：进程和数据库 liveness；
- `/api/v2/health/readiness`：Identity、Codex、来源 Adapter、Worker、SimC runtime 的分组件状态；
- request ID、user hash、domain、operation、latency、terminal state 的结构化日志；
- Worker queue depth、oldest queued age、lease expiry、retry/failure count；
- Agent first-token latency、stream completion率、Codex failure/timeout；
- 来源解析成功率、各 readiness 状态计数；
- SimC runtime revision、任务成功率、超时率、无指标结果数。

日志和指标不能包含 OpenID、UnionID、角色完整 profile、聊天正文、第三方 token 或 WCL 私有内容。

## 15. 迁移与退役策略

整体重构分成可独立验证的子项目，避免在一个提交中重写全部系统。

### 阶段 A：新骨架

- 建立 `server/app`、ASGI API、统一配置、错误模型、PostgreSQL repositories 和 Worker lease；
- 新 `/api/v2` 不接正式导航，不改变旧 API/Active runtime；
- 建立模块依赖测试，禁止新代码导入 legacy `news_backend.py` 业务函数。

### 阶段 B：Identity

- 建立 provider-aware identity resolver、Web OAuth 和小程序 exchange；
- 测试数据允许重建，不进行复杂历史账号迁移；
- 双端同一 `user_id` 通过后再允许新业务写入。

### 阶段 C：Chickenbro

- 抽取当前原生 Codex runner、会话持久化和流式合同到新模块；
- 删除新主链中的规则树和普通 LLM fallback；
- 通过旧/新契约对照和真实流式 smoke 后切换 Chickenbro route。

### 阶段 D：Simulation

- 实现来源 Router、两个 Adapter、统一 Snapshot/Validator/Compiler、任务 Worker 和结果模型；
- 使用云端 SimC 做真实 profile semantic smoke；
- 新链路不导入旧 WebSim、装备库、天赋模拟或 Manifest owner。

### 阶段 E：双端客户端

- 新建精简 App Shell 和 feature routes；
- Web 部署独立域名并完成微信扫码回调；
- 小程序和 H5 对相同账号执行会话/任务交叉读取验收。

### 阶段 F：切流与删除

- 候选 API/Worker/Web/小程序完成 owner、流式、来源、SimC、失败和回滚 smoke；
- 用户验收后切换正式入口；
- 删除资讯、天赋模拟、装备模拟、新产品不再引用的前端路由、API route、定时任务和数据 owner；
- 保留一个已验证部署包作为短期回滚，不保留双写或无限 legacy compatibility；
- 删除完成后重新生成 roadmap、owner map、route contract、verification matrix 和部署清单。

旧模块的最终删除是本项目完成条件，但不是新骨架第一步。删除前必须证明新路径可独立运行，避免一次性失去可回滚系统。

## 16. 验证策略

### 16.1 单元与契约

- Domain 状态机、identity merge conflict、snapshot revision、readiness、compiler 和 job idempotency；
- Adapter fixture 不联网测试，覆盖正常、缺字段、403/404、限流、过期和 schema 漂移；
- API schema、owner isolation、Cookie/Bearer 分离、SSE sequence 和错误码；
- 模块依赖测试确保 domain 不导入 framework/adapter/legacy owner。

### 16.2 集成

- PostgreSQL schema、事务、`SKIP LOCKED`、lease recovery、取消和重试；
- Codex stream 写入与断线恢复；
- Raider.IO/WCL 通过云端已配置凭据进行只读 smoke，永不输出 secret；
- SimC stdin profile、runtime identity、DPS 解析、`race=none` 阻断、无指标/超时失败。

### 16.3 双端端到端

- 小程序登录创建/解析用户，Web 扫码登录解析为同一 `user_id`；
- 小程序发起会话，Web 可见并续问；反向同样成立；
- 一端提交 SimC，另一端看到相同任务状态和结果；
- 未登录、UnionID 缺失、来源受限、快照不完整、Worker 重启、Codex 超时和 SimC 失败均有明确恢复路径；
- Web 正式域名、HTTPS、OAuth state、Cookie、CORS/Origin 和反向代理在 candidate 环境验证。

### 16.4 发布门槛

- 使用 Harness 的当前真相、任务级 verification profile、candidate deployment 和 rollback evidence；
- 后端/API/PG/Worker/域名变更在 merge 前进行 candidate smoke；
- 小程序切流必须完成构建、真实 DevTools 和用户验收；
- H5 必须完成主流桌面浏览器和移动浏览器 smoke；
- HTTP 200、测试通过、systemd active、SimC returncode 0 或 Candidate 存在均不单独代表产品完成。

## 17. 后续子设计

父级架构确认后，实施按以下独立子项目推进，每个子项目只细化自身交互和测试，不改变本文组件边界：

1. 平台骨架与 `/api/v2`/Worker；
2. 微信双端 Identity 和显式绑定；
3. Chickenbro 模块抽取与 Codex-only 主链；
4. Raider.IO/WCL Snapshot 输入和 SimC Worker；
5. 精简 Taro App Shell、独立 Web 部署与最终 legacy 删除。

WCL fight/玩家选择、种族确认的页面细节，SimC 场景 preset、任务结果页面和最终导航属于对应子项目。它们只能在本文端口、状态机和数据所有权内实现。

## 18. 父级架构完成标准

本架构实现完成必须同时满足：

- 新 API 不再依赖 `news_backend.py`、`simulator_payload.py` 中的 legacy 业务 owner；
- 新客户端只注册炸鸡队长、SimC 和共享账号/历史支持页面；
- 小程序/Web 同一微信用户映射为同一内部 `user_id`；
- 对话和 SimC 历史双端一致且 owner 隔离；
- Codex-only 对话主链可流式运行，失败不伪造回答；
- 两个来源 Adapter 都只能输出统一 Snapshot candidate；
- readiness/编译/Worker/SimC 结果链有真实云端语义验证；
- 资讯、天赋模拟、装备模拟和相关定时/数据 owner 从正式运行路径删除；
- candidate、回滚、用户验收和 main/production parity 有独立证据；
- roadmap、project-state、owner map、route contract 和 runbook 与新 Active runtime 一致。

## 19. 当前实现依据

- Taro 已支持 `build:weapp` 和 `build:h5`：`apps/mini-taro/package.json`；
- 当前 H5/WeApp 共用编译配置：`apps/mini-taro/config/index.ts`；
- 当前 14 路由和四个一级入口：`apps/mini-taro/src/app.config.ts`；
- 当前后端路由、身份、聊天和 SimC 高度集中：`server/news_backend.py`；
- 当前 SimC 辅助逻辑集中：`server/simulator_payload.py`；
- 现有正式身份表：`server/migrations/postgres/0001_identity_app_content_cache_knowledge_analytics_ops.sql`；
- 当前原生 Codex 方向：`docs/plans/2026-08-04-chickenbro-agentic-research-design.md`；
- 当前 SimC 真实性边界：`docs/simulator-simc-end-to-end.md`。

本文在新架构实施并切流前不替代当前生产事实。当前 Active runtime、14 路由和旧 API 仍按 `docs/project-state.json` 与 `docs/roadmap.md` 如实报告。
