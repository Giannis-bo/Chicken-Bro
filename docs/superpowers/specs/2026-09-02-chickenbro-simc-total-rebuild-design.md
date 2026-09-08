# 炸鸡队长与 SimC 双端彻底重构设计

> 1.0 结论（2026-09-08）：用户已接受当前实现。本规格保留最初范围，后续明确决定与 [1.0 说明](../../releases/1.0.md) 优先；小程序账号与外观面板已取消，微信公开发布仍为独立步骤。

日期：2026-09-02
状态：书面规格已复核；用户已授权以持续 Goal 顺序推进整体实施；当前仅 Phase 1 控制面可执行，切流与删除仍受各阶段门禁约束
范围：微信小程序、独立 Web、身份、炸鸡队长会话、SimC 任务、文档/代码/云端 legacy 退役

## 1. 决策

目标产品只有两个业务域：

1. 炸鸡队长会话；
2. SimC 模拟任务。

Identity、任务队列、健康检查、审计和历史查询是支撑能力，不形成新的产品模块。资讯、职业构筑、
天赋模拟、装备模拟、旧 WebSim、旧数据刷新链和 prototype bypass 全部退出最终产品。

Web 与小程序不共享 Cookie、Bearer token、OpenID、`session_key` 或微信 access token。两端分别建立
安全会话，但认证后都解析为同一个内部 `user_id`。所有会话、消息、SimC 快照、任务和结果都由服务端
按这个 `user_id` 持有，因此两端看到同一份完整业务历史。

本次采用“保留已验证的新 v2 核心，重建干净生产数据面，再切流并删除 legacy”的方案。不会在旧
`news_backend.py` 上继续删路由，也不会因为“彻底重构”而重写已经符合目标边界的 `server/app` 纯领域、
PostgreSQL lease、登录票据和 SimC 结果语义。

## 2. 用户完成体验

### 2.1 登录与跨端历史

小程序用户通过 `wx.login` 建立 Mini Session。PC Web 显示一次性小程序码，用户扫码后在炸鸡队长
小程序中明确确认，Web 随后获得自己的 HttpOnly Web Session。两端独立退出和过期，但都对应同一
内部用户。

登录任一端后，用户可以：

- 看到全部有效会话、用户消息和助手消息；
- 在另一端继续已有会话，消息顺序和终态一致；
- 看到全部 owner-bound SimC 输入快照、排队/运行/失败/完成任务和结果；
- 从任一端创建任务，在另一端查看同一个任务的实时状态和最终结果；
- 把一个已有 SimC 结果附加给炸鸡队长解释，而不复制 profile 或跨用户泄露数据。

“全部”只指用户拥有且通过迁移/新 schema 完整性校验的业务数据。模型思维链、密钥、OpenID、微信
`session_key`、Cookie、第三方 token、内部日志和被完整性校验拒绝的旧测试数据不属于同步内容。

### 2.2 最终导航

微信小程序只保留两个 Tab：

```text
队长 | SimC
```

目标业务路由为：

```text
pages/chickenbro/index
pages/simc/index
pages/simc/tasks
pages/simc/task-detail
pages/auth/web-login-confirm   # 辅助认证页，不进入 TabBar
```

Web 使用同一套 Taro feature/domain/typed client，提供登录、队长、SimC 列表和任务详情视图。账号状态、
退出和错误恢复放在 App Shell 中，不保留旧“我的”、资讯、专精、装备工作台或 prototype 一级入口。

## 3. 方案选择

| 方案 | 判断 | 原因 |
| --- | --- | --- |
| 新 v2 核心 + 干净数据库 + 验证后切流/退役 | 采用 | 能复用已经验证的领域和安全边界，同时真正删除旧 owner、表、服务和文档 |
| 在现有 `wow_test`/legacy 后端中原地删表删路由 | 不采用 | 生产与测试语义混合，回滚困难，容易误删仍被调用的数据 |
| 新建另一个仓库并从零重写 | 不采用 | 会丢失已验证的登录票据、Owner 隔离、Worker lease、Codex 和 SimC 语义，不增加用户价值 |
| 把小程序 token 传给 Web | 不采用 | 扩大 token 暴露和重放面，且无法独立撤销两端会话 |
| 网站应用 OAuth/`snsapi_login`/UnionID 前置 | 不采用 | 当前个人主体不依赖该资格；小程序确认已能把 Web Session 绑定到同一 `user_id` |

## 4. 目标拓扑

```text
WeChat Mini Program ---- Mini Bearer -----\
                                          > API/BFF -> Principal(user_id)
Web/H5 -- Mini-confirmed HttpOnly Cookie -/              |
                                                         +-> Identity
                                                         +-> Chat -> Codex Adapter
                                                         +-> SimC -> PostgreSQL Queue -> Worker
                                                                                   -> Raider.IO/WCL
                                                                                   -> SimulationCraft
```

部署保持一个模块化单体 API、一个独立 Worker、一套 PostgreSQL 和一个云端 SimulationCraft runtime。
不引入微服务、Redis、Celery、Kafka、第二套数据库产品或通用插件平台。

目标代码依赖方向固定为：

```text
UI -> typed API client -> API routes -> application -> domain -> ports <- adapters
```

Domain 不导入 FastAPI、Pydantic、Psycopg、Taro、Codex、WCL、Raider.IO 或 SimC 实现。API route 只做
传输、鉴权和 use-case 调用；Adapter 不直接写业务表；所有业务 owner 从认证 Principal 注入。

## 5. 身份设计

### 5.1 唯一业务身份

`identity.users.id` 是唯一业务 owner。`identity.user_identities` 只保存服务端身份映射：

```text
provider = wechat_mini
app_context = 当前小程序 AppID 上下文
provider_subject = 当前小程序 OpenID
user_id = 内部 UUID
```

UnionID 只可作为未来可选信息，缺失不阻断登录。昵称、头像、角色名或相似标识不能用于猜测合并账号。

### 5.2 小程序登录

```text
wx.login
-> POST /api/v2/auth/wechat/mini/exchange
-> 服务端 code2Session
-> 精确解析/创建内部 user_id
-> 签发 Mini Bearer Session
```

`session_key` 和微信服务端凭据只在服务端内存/受控配置边界中使用，不进入客户端、日志或业务表。

### 5.3 Web 由小程序确认登录

```text
Web 创建 browser-bound login ticket
-> 服务端返回只含 opaque scene ticket 的小程序码
-> 用户扫码进入 pages/auth/web-login-confirm
-> 小程序用当前 Mini Session 展示并明确确认
-> ticket 绑定同一 user_id
-> 原浏览器一次性交换 HttpOnly Secure SameSite=Lax Cookie
```

`scene` 只放不超过 32 个可见字符的随机 ticket。持久层只保存 ticket/verifier hash、状态、过期时间、
确认 user、消费/取消时间。状态机固定为：

```text
pending -> confirmed -> consumed
pending -> cancelled
pending -> expired
confirmed -> cancelled
confirmed -> expired
```

错 verifier、过期、取消、重复确认和重复消费全部 fail-closed。Web Cookie 与 Mini Bearer 独立撤销；
共享的是 `user_id` 和业务数据，不是客户端登录凭据。

业务 API 可以从两种会话建立相同的 `Principal`，但 Web 客户端只使用 Cookie，小程序只使用 Bearer，
Domain 永远看不到原始凭据。Cookie 认证的写请求必须同时通过精确 `Origin`/`Host` 校验和 CSRF 防护；
CORS 只允许正式 Web origin 且不使用通配符。Cookie 固定为 HttpOnly、Secure、最小 Path/Domain、有限
TTL，服务端只保存 session token hash。登录、换票、退出、撤销和可疑重放写入脱敏审计，不记录 ticket、
verifier、Cookie、Bearer、OpenID 或 `session_key` 明文。

## 6. Chat 领域

只保留：

- `chat.conversations`：owner、标题、active/archived、时间；
- `chat.messages`：conversation、owner、role、正文、客户端幂等 ID、时间；
- `chat.agent_runs`：输入/输出消息关联、Codex revision、状态和公开错误。

消息正文追加写入。只有 assistant 消息持久化成功后，AgentRun 才能进入 `succeeded`。Codex 不可用、
超时、输出非法或持久化失败时保留用户消息并进入明确失败，不切换普通 LLM，不写模板答案。

双端列表使用稳定游标和 `updated_at/id` 排序；发消息使用 `Idempotency-Key` 与 `clientMessageId`；当前回答
使用严格递增 sequence 的 SSE。客户端缓存只用于渲染和断线恢复，不是历史事实源。

## 7. SimC 领域

只保留：

- `simc.source_snapshots`：不可变、带来源和抓取 provenance 的角色输入；
- `simc.simulation_jobs`：owner、snapshot、scenario、compiler/runtime identity、状态；
- `simc.simulation_attempts`：每次 Worker 尝试、lease 和公开错误；
- `simc.simulation_results`：不可变 profile hash、有效指标和完整 runtime provenance；
- `ops.job_queue`：仅承载 Chat/SimC 必需的异步命令。

Raider.IO 与 WCL Adapter 只能产生 `CharacterSnapshot` candidate。统一 readiness validator 和唯一 compiler
决定能否执行；不得把旧 Gear Catalog、Talent Catalog、Resolver、Manifest 或 WebSim profile 重新接入
新主链。

SimC return code 0、stdout 非空、HTTP 200 或 systemd active 都不是业务成功。成功必须包含正确 actor、
有效最终指标、非 `race=none`、匹配的 input/compiler/runtime identity 和无致命诊断。

## 8. 新生产数据库与历史迁移

### 8.1 新数据面

建立独立的干净生产数据库 `chickenbro_prod`，只包含：

```text
identity: users, user_identities, auth_sessions, web_login_sessions
chat: conversations, messages, agent_runs
simc: source_snapshots, simulation_jobs, simulation_attempts, simulation_results
ops: schema_migrations, job_queue, audit_events, usage_counters
```

应用继续使用 least-privilege runtime role；schema 变更使用 management/migrator role。新数据库不创建
`content`、`cache`、`knowledge`、`analytics`、旧 `app` 或 WebSim/gear/talent 表。

### 8.2 迁移白名单

迁移采用显式 classifier，输出每张表的 `candidate/accepted/rejected` 数量和拒绝原因。允许迁移：

1. 能精确关联到 `wechat_mini` identity 且不是 prototype 的正式用户；
2. `chat.*` 中属于这些用户、角色/顺序/终态合法的会话和消息；
3. `simc.*` 中属于这些用户、输入和结果语义合法的快照、任务、尝试和结果；
4. 旧 `app.chickenbro_*` 与 `app.simulator_tasks` 中能确定 owner、顺序、输入和终态的记录，转换为新模型；
5. 为解释一个已迁移结果所必需的最小 provenance/hash。

不迁移：

- prototype/demo owner、prototype session 和候选扫码记录；
- 旧 auth token、Cookie、session 或其他凭据，所有用户在切流后重新登录；
- 无法精确解析 owner、角色、消息顺序或 SimC 语义的记录；
- news/content/cache/WebSim/gear/talent/stat-weight/observed-build/evidence 数据；
- 运行日志、模型思维链、原始 secret 或无限期第三方 payload。

拒绝记录只进入不含行内容的脱敏迁移报告，不写入新生产库，也不因为被拒绝而建立数据备份。迁移包含一次候选全量和切流窗口内的一次
只读 delta；没有长期双写。迁移器为每条接受记录保存不可变的 source table/source primary key 到 target
UUID 映射，重复执行必须幂等。切流前按用户、会话、消息、快照、任务、尝试和结果分别核对接受/拒绝计数、
owner、外键、顺序、终态和内容 hash，不能只比较数据库总行数。

## 9. 2026-09-02 云端只读盘点

以下是设计输入，不是删除授权；执行前必须重新盘点。

- 根盘 69GB，已用 58GB，可用 8.1GB，使用率 88%；
- PostgreSQL 目录约 37GB；
- `wow_test` 约 15GB，当前同时被 `wow-backend` 与正式 `wow-v2-api` 使用，不能按名称当作测试库删除；
- `wow_test` 中有 222 users、163 identities、192 legacy Chickenbro sessions、526 legacy messages、
  47 v2 conversations、33 v2 messages、2 SimC jobs 和 2 SimC results；是否可迁移由白名单逐行判定；
- `wow_v2_candidate` 约 10MB，有 1 user、2 auth sessions、12 Web login sessions，Chat/SimC 业务记录为 0；
- 四个 `wow_gear_evidence_*` 数据库合计约 21GB，盘点时连接数为 0，但仍存在旧 env 文件；
- 活动运行单元包括 legacy `wow-backend`、`wow-v2-api`、`wow-v2-worker`、候选 API、旧 Gear worker 和
  多个 WebSim/gear/community/stat-weight/talent timer；
- `www.chickenbro.cloud`、v2 readiness 和 legacy health 可达不代表真实扫码、跨端历史或正式切流完成。

当前 8.1GB 可用空间小于现用数据库约 15GB，不能在同一根盘上安全并存完整新库、旧库回滚和迁移临时
空间。容量纠正路径固定为：从保持只读的 `wow_test` 把有效业务白名单迁入干净 `chickenbro_prod`，核对后
导出该小型目标、执行 `pg_restore --list`，再恢复到独立验证库并第二次核对；只有这份 hash-bound 恢复清单
成立，且 fresh live probe 确认四个精确 `wow_gear_evidence_*` 库及对应四个 `/etc/wow-backend-candidate-gear-evidence-r*.env`
无连接、无 systemd/Nginx/process/open-handle 引用并先移除 env 伴随项时，才可按精确字面量做容量预清理。
这些明确拒绝的 evidence/test 内容不备份；替代路径是扩容。`wow_test` 在真实双端验收前始终只读且受保护。

## 10. 文档清理

最终工作树只保留能解释当前产品、运行和交付的文档：

- `README.md`、`AGENTS.md`；
- `docs/project-state.json`、`docs/roadmap.md`、`docs/harness.md`、`docs/verification-matrix.md`；
- 精简后的 owner map、API/DB schema；
- 一份当前架构、一份身份说明、一份 SimC 语义说明、一份生产运维/恢复 runbook；
- 当前任务的 requirement/evidence/manifest 和最终 cleanup manifest。

删除旧资讯、14 路由重建、天赋、装备、WebSim、S2 Catalog、旧 ChatBot 规则树、prototype bypass 和已完成
候选的设计/实施文档；删除不再被当前文档引用的历史 release packet 和 UI evidence。Git 历史承担归档，
不得为了保留过程记录继续污染当前控制面。

删除前必须生成文档链接图，证明每个删除文件没有来自保留文档、代码注释、Harness 或 release packet 的
活动引用。直接属于当前运行回滚证据的文件要到新生产切流和回滚窗口闭合后再删。

## 11. 代码清理

### 11.1 保留并收敛

- `server/app/{identity,chickenbro,simulation,worker,platform,integrations}`；
- 小程序码、Codex、Raider.IO、WCL 和 SimulationCraft 的最小 Adapter；
- `apps/mini-taro` 中新的双 Tab App Shell、认证辅助页和共享 Chat/SimC feature；
- `packages/api-client`、`packages/domain` 与仍有调用者的最小 design-system；
- Harness、部署、迁移和验证脚本。

### 11.2 删除

- `server/news_backend.py` 及旧 news/content、WebSim、gear、talent、stat-weight、observed-build、Catalog、
  Manifest 和旧同步链调用树；
- `/api/v2/prototype/**`、prototype principal/repository、bypass UI 和 prototype 数据；
- 根目录兼容 `pages/`、`components/`、`custom-tab-bar/`、`websim/` 与旧 14 路由；
- `apps/mini-taro` 的 news/builds/profile/旧 simulator 路由与无调用组件；
- 旧测试、fixture、脚本、service/timer 和 package exports；
- 未被最终构建、测试、部署或运行时 caller graph 消费的依赖。

删除顺序由 caller-proof 决定：先让新代码无 legacy import，再删除入口，再删除实现和测试，最后删除数据
owner。不得用兼容 shim、空实现或永久 feature flag 假装完成清理。

## 12. 云端退役与清理

云端退役分为“容量前置清理”和“切流后 legacy 退役”。容量前置清理只允许四个精确 hash-suffixed
`wow_gear_evidence_*` 数据库及其四个精确 env 伴随项；这些数据已被明确拒绝，因此不建立恢复副本。
执行前必须先完成业务白名单的迁移、第一次核对、目标库 dump/list、distinct restore 和第二次核对，并刷新
exact Tencent CVM identity、库大小、连接、配置、systemd/Nginx/process/open-handle 引用。不能触碰
`wow_test`、正式部署、唯一 SimC runtime 或当前回滚包。随后按以下顺序执行：

1. 建立并验证 `chickenbro_prod`，从只读 `wow_test` 执行业务白名单迁移与双重核对，生成 hash-bound 恢复清单；
2. 在 reviewed capacity scope 中先移除四个无消费者 env 并确认 absent，再按精确库名释放拒绝 evidence 数据占用，或选择扩容；
3. 容量重新满足后部署 candidate，并在切流窗口执行只读 delta 迁移；
4. 切换 API/Worker DSN，验证跨端历史、Codex、SimC、owner 隔离和回滚；
5. 为已接受生产数据保留经过恢复验证的短期回滚包；
6. 停止并禁用 legacy `wow-backend`、旧 Gear worker 和所有 news/WebSim/gear/community/stat-weight/talent timer；
7. 移除 candidate API、candidate DB、prototype 数据和无引用 env；
8. 删除 exact-first 临时 DB、旧 `wow_prod`，以及最终不再承担回滚的 `wow_test`；
9. 删除 `/opt` 中旧 candidate/staging/backup 目录、旧 `/var/lib/wow-backend` 数据、旧静态 assets/evidence；
10. 回滚窗口结束后按精确 manifest 删除回滚包，再检查磁盘、数据库、监听、systemd、Nginx、证书、API、Worker 和跨端验收。

数据库和目录删除只能使用审阅过的精确名称，禁止宽泛递归删除。容量 scope 未完成白名单恢复证明及 fresh
连接/引用证明时不得执行 DROP；完整退役未完成已接受生产数据恢复、用户验收或回滚演练时，不得停止正式
入口或删除旧环境。

## 13. 实施分解

本项目不是一个大提交，按以下六个可独立验收的 Strict 子项目推进：

1. **控制面与清理清单**：新 current truth、caller graph、docs/code/cloud keep-delete-migrate manifest；
2. **干净数据面与 Identity**：`chickenbro_prod`、小程序登录、Web 小程序确认、正式 Principal；
3. **Chat 正式路径**：正式 owner 路由、历史列表、SSE、Codex-only 与跨端会话；
4. **SimC 正式路径**：来源 Snapshot、readiness、compiler、Worker、结果历史与跨端任务；
5. **双端精简客户端与迁移切流**：双 Tab、小程序确认页、Web Cookie、历史迁移、candidate 和用户验收；
6. **Legacy 退役**：文档、代码、服务、timer、数据库、静态数据和备份清理，最终 parity 与恢复证明。

每个子项目有独立 requirement、验证、candidate/rollback 和提交。任何阶段的测试通过不自动授权下一阶段
的数据删除或生产切流。

## 14. 验收矩阵

### 14.1 身份与同步

- 同一微信用户的小程序与 Web 在服务端解析为同一 `user_id`；
- 小程序创建会话，Web 可见并续聊；Web 创建会话，小程序可见并续聊；
- 任一端创建 SimC 任务，另一端看到同一 job id、状态、输入 provenance 和结果；
- 两端独立 logout；ticket 过期、重放、错 verifier 和重复消费全部失败；
- 第二个微信用户无法枚举、读取或修改第一个用户的任何 Chat/SimC 记录。

### 14.2 Chat 与 SimC 真实性

- SSE sequence、断线恢复、消息幂等和 assistant 终态持久化通过；
- Codex 不可用时明确失败，不切换普通 LLM 或模板；
- Raider.IO/WCL 缺字段、权限受限和来源不可用分别报告；
- 只有 `READY_FOR_SIMC` 快照进入 Worker；
- SimC 成功包含有效语义指标和完整 input/compiler/runtime identity。

### 14.3 清理完成

- 新客户端只注册目标五条路由和两个 Tab；
- 正式 API 无 prototype、news、build、gear、talent 或 legacy WebSim route；
- 生产进程无 `news_backend.py`、旧 worker/timer 或旧数据库连接；
- `chickenbro_prod` 不包含旧 schema/table；
- 精确删除清单中的旧数据库、目录、服务和 env 均不存在；
- 保留文档无断链，owner map、verification matrix、部署/恢复 runbook 与实际运行一致；
- 本地 `main`、`origin/main`、部署文件 identity、数据库 migration identity 和运行 smoke 分别有证据；
- 用户明确确认真实小程序与 Web 的跨端会话和 SimC 路径后，才允许最终退役回滚包。

## 15. 回滚与完成定义

切流使用明确写栅栏：先把 legacy 置为只读，记录水位，执行最终 delta 与核对，再把唯一写入口切到
`chickenbro_prod`。新系统接受第一条正式写入前，可以原子恢复上一部署包和旧库写入口；接受第一条正式
写入后，不得把旧库重新开放为可写，也不做反向数据猜测或双向同步。此后的故障恢复优先修复/回滚新代码；
必要时只提供 legacy 只读降级页，同时保护新库写入日志并恢复到新的主数据面，避免双主、覆盖或历史分叉。

本项目只有在新双端路径用户验收、正式切流、legacy 文档/代码/云资源精确删除、恢复验证、最终健康和
Git/生产 parity 全部完成后，才能标记 `已完成`。Candidate、HTTP 200、测试通过、systemd active、
SimC return code 0、备份存在或磁盘空间回收都不能单独代表完成。
