# QQ 小号 + NapCat 通道设计与环境准备

日期：2026-09-23。状态：普通 QQ 小号 + NapCat 文字通道已实现，用户已明确确认消息通道正常；正式回答及用户验收见 [production-hello.json](../../artifacts/verification/2026-09-23-qq-napcat/production-hello.json)。密码回退已通过容器重启自动登录验证。下文保留首版通道设计；用户新提出的陪伴角色、主动参与和表情包方向仍在讨论，尚未改变运行行为。

用户在环境与设计完成后明确要求“可以，接入”。本批继续交付文字通道、0015 增量迁移和独立 Candidate 联调；网站账号绑定与图片输入留待后续。正式 Web/生产数据库保持原状态。

## 场景与默认交互

群友在允许的群里 `@鸡哥 问题`，鸡哥确认接收，调用既有 Chat/Worker 的搜索、WCL、SimC 或 PoB 能力，再向原群回复。只有触发消息和该群友的连续问答进入模型。

首版建议：

- 一个测试群，群白名单；私聊和自动插话默认关闭。
- 仅真实消息段中的 `at.qq == self_id` 触发，文字中伪造 CQ 码不算 @；忽略自身消息。
- 会话键包含机器人、群、发送者、游戏和会话代次。不同群、不同群友、WoW/POE2 分离。
- 默认游戏 WoW；`@鸡哥 /游戏 poe2` 切到自己的 POE2 会话，`/游戏 wow` 切回；切换不修改已有会话的固定游戏。
- `/新会话` 增加会话代次，保留历史；`/状态` 查询自己的任务；`/帮助` 显示用法。
- 首版文字，随后加入受限截图提问。群文件、语音、自动群管理、随机插话、共享长期记忆、跨群读取不在首版。
- 首次使用提示“提问和回复会在本群公开”；不默认抓取、存储或总结全群闲聊。

用户已提供机器人 QQ 号、测试群号、管理员 QQ 号，准确值已写入服务器私有配置。允许群为空、机器人身份未确认或开关关闭时，适配器必须拒绝业务处理。QQ 密码不进入部署文件和记录。

## 选定结构

```text
QQ 群
  ↕ QQ 客户端连接
NapCat 容器（独立登录数据，无鸡哥 DB/模型/云凭据）
  ↕ OneBot 11 正向 WebSocket，127.0.0.1:13001，独立 token
鸡哥 QQ 通道服务（宿主机独立进程）
  → 可信事件校验、群白名单、身份解析、幂等 inbox、会话映射
  → ChatApplication.create_conversation / start_delivery
  → 既有 durable Chat execution 与 Worker
  → 通道 outbox → send_group_msg → QQ 群
```

采用正向 WebSocket，原因是同机部署可直接连接宿主机 loopback 映射，不需要额外暴露反向 WebSocket 接收器或调整现有 Nginx。OneBot 既传事件也接收 API 请求，以 `echo` 关联回执。

备选的反向 WebSocket 适合跨机器接入；当前无此需求。额外引入完整 AI 机器人框架会增加第二套会话、工具和任务生命周期，因此本方案直接接鸡哥应用层。

## 环境与隔离

- 云主机：`wow-lighthouse`，已核实 `ins-93tgv1rb` / `ap-shanghai`，Ubuntu 24.04 x86_64，4 CPU、约 3.6 GiB RAM。
- 镜像来源：NapCat 项目文档指定的 `mlikiowa/napcat-docker`；下载后锁定 RepoDigest，运行不追随 `latest`。
- 不安装新的 Docker/Compose；使用现有 Docker 与受控启动脚本。
- 容器名：`chickenbro-napcat`；独立 bridge 网络 `chickenbro-qq-channel`。
- 容器限制：1 CPU、768 MiB 内存、内存加 swap 总计 1 GiB、256 PIDs、64 MiB shm；按登录后的实测再评估。
- 容器非 privileged，不挂 Docker socket、宿主机源码、数据库配置或模型凭据。
- 管理页：`127.0.0.1:16099 → 6099`，仅通过 SSH 隧道打开。OneBot：`127.0.0.1:13001 → 3001`，须单独 token。
- 运行清单和脚本：`/opt/chickenbro-qq-channel`；持久数据：`/var/lib/chickenbro-qq-channel/{qq,config,plugins}`。
- 凭据：`/etc/chickenbro-qq-channel`，root/0700；配置文件 0600，不入 Git、不打印 token/二维码到工具输出。
- NapCat 上游控制台可能输出 WebUI 密钥或登录二维码，Docker 日志驱动设为 `none`；QQ/NapCat 自身文件日志须关闭或留在私有目录中，后续只收集脱敏状态。
- 公网不新增监听或安全组端口；不变更现有 Web、API、Worker、数据库及 Nginx。
- 部署前后检查生产 readiness、API/Worker PID/启动时间、代码/Web 指针；这只证明本次环境准备未观察到服务状态变化，不代替业务验收。

容器私有网络用于分离服务发现；它不是宿主机内网访问的完整安全边界。进入真实群前，应验证 QQ 图片下载的地址限制和适配器权限；NapCat 本身不持有生产秘密。

## 身份与数据合同

网站现有 `SessionKind` 只有 `web_cookie`，`ChatExecutionWorker` 也以该值构造执行身份。接入必须新增明确的可信通道 actor/来源语义，并让 Worker 从持久化来源恢复，不能把所有群友放进机器人账号，不能伪造网站 Cookie。

建议首版为 `(bot_id, group_id, sender_qq)` 建立独立内部 `identity.users.id`，再按游戏和代次映射 conversation。这样同一 QQ 在不同群的工具资产也隔离。群号和 QQ 号作为字符串验证，始终来自通过 token 验证的连接和 OneBot 事件。

新增通道身份表，不借用 `provider='qq'` 的 QQ 互联 OpenID 字段。网站 HTTP 认证仍仅接受现有 Cookie；通道身份不能直接访问 Web/admin。

建议新增 `channel` schema：

| 表 | 关键约束与职责 |
| --- | --- |
| principals | 唯一 `(channel, bot_id, group_id, sender_id)` → 内部 user_id；标记 active/disabled |
| conversations | 唯一 `(principal_id, game, generation)` → conversation_id；持久化当前代次 |
| inbox | 唯一 `(channel, bot_id, group_id, message_id)`；保存有界触发内容、状态、run_id、接收时间 |
| outbox | 唯一 `(inbox_id, reply_kind, part_index)`；状态 pending/sending/sent/uncertain/failed，保存 send message_id |

0015 迁移已在独立测试库与 Candidate 数据库应用，创建上述 qq_channel 表及 chat.executions.actor_kind；原 Web 默认为 web_cookie，QQ Worker 从持久化来源恢复 qq_group。也已应用到独立正式 QQ 数据库 chickenbro_qq_channel；网站 chickenbro_prod 未修改。

网站账号绑定后续单独设计：用登录态生成短时一次性绑定码验证两端持有人；绑定不自动合并群会话，也不允许把网站私有历史、角色或构筑直接发到群中。首版不提供已有网站构筑 ID 的跨 owner 读取。

## 幂等、排队与回复

1. 验证 token、事件类型、`self_id`、群白名单、发送者和 @，拒绝过期事件及超限输入。
2. 仅接纳 120 秒以内的触发消息；重连后的重复消息由 inbox 唯一键阻止。
3. 以确定性哈希生成满足既有 8–128 字符约束的 Chat 幂等键；inbox 和 run 关联可在重启后重新对账，不能重复执行工具。
4. 首版 QQ 通道最多一个进行中的 AI 请求，每个群友最多一个待处理请求，全通道队列上限 10；超限明确提示稍后重试。该限制只约束 QQ 通道，保留 Web 现有规则。
5. 先发一条简短接收确认；耗时超过 30 秒且有新进展时最多补一条；答案按段落拆为最多 5 条、每条最多 1500 字，超长保留结论并提示缩小问题。图片结果后续再加入。
6. 输出按 OneBot 消息段发送纯文本，禁止把模型文本解释成 CQ 控制码、任意 @、群管理命令或文件路径。
7. 收到成功响应且带有效 message_id 后才能标记 sent。响应超时但请求可能已发送时标记 uncertain，不自动重复发长答案；可通过 `/状态` 明确查询和再次取回。
8. OneBot 重连指数退避 1–60 秒；QQ 退出登录时暂停派发，不无限登录重试。进程重启后恢复 inbox/outbox，不盲重放发送或模拟副作用。
9. 收发状态日志只保留关联 ID、耗时、错误码和脱敏 owner 摘要；不记录全群正文、账号密码、登录票据、图片临时 URL 或 token。

OneBot API 回执仅说明发送请求成功。真实验收还要求第二个 QQ 账号在群客户端实际看到正确回复。

## 图片与工具边界

截图阶段复用鸡哥图片大小、数量、解码与 owner 约束。只下载受信 QQ 媒体 HTTPS 地址，逐次校验重定向、DNS 和私网地址，设置大小/时间上限，禁止下载任意内网 URL 或本地路径。图片只关联触发的群友会话。

群输入和转发内容视为用户数据，不获得部署、shell、凭据读取或群管理权限。沿用既有工具白名单和 owner-scoped capability；用户指定任务编号、构筑 ID 或他人 QQ 号不能改变授权主体。

PoB 长字符串超出当前 Chat 4000 字限制时，给出当前支持入口提示；支持群文件导入应另做解析、大小与所有权设计，不通过截断假装导入成功。

## 后续实现分层

| 阶段 | 文件归属 | 完成条件 |
| --- | --- | --- |
| 环境准备（本次） | `server/qq-channel/`、本设计、脱敏环境证据 | 摘要固定；容器受限；面板 loopback；登录/业务状态准确分列 |
| 通道接入 | 新增 `server/app/channels/qq/{onebot,policy,repository,service}.py` | 假消息合同、token/self_id 校验、白名单、分段、去重与不确定回执通过 |
| 身份与 Chat | `server/app/identity/domain.py`、新增通道身份应用、`server/app/chickenbro/worker.py`、durable 来源、增量迁移 | Candidate 两群/两用户/两游戏隔离，原 Web Cookie/CSRF/admin 保持拒绝边界 |
| 测试群联调 | 独立 Candidate 配置与真实小号 | 真实 @→生成→群可见答案，追问、重连、重启及限流均有证据 |
| 正式开放 | 生产 Runbook、owner maps、验证矩阵与通道开关 | 用户确认测试群体验，完成发布所需身份、回退、业务证据后开放指定群 |

复用点已经核查：`ChatApplication.create_conversation`、`start_delivery`、持久 execution、原 Worker；不另起通用 Agent 或复制模型配置。业务接入时需要审查 `server/app/main.py` 的依赖装配，提取可复用组装函数，不能为了拿应用对象启动第二个公开 HTTP 服务。

## 验收清单

- [x] 手机 QQ 扫码后，NapCat 返回已登录；`get_login_info` 的 self_id 与指定小号一致；目标群成员关系和指定群主已核实。
- [ ] 非允许群、私聊、未 @、机器人自身消息都不产生 AI run。
- [ ] 两位群友在同群连续提问，内容、角色、构筑和任务不串；同一群友跨群也隔离。
- [ ] WoW/POE2 固定游戏、`/新会话` 和 `/状态` 行为符合约定。
- [ ] 重复事件、重启、断线重连不会重复生成或重复提交 SimC/PoB。
- [ ] 群内实际可见一条接收确认和最终答案；发送回执丢失进入 uncertain。
- [ ] 长耗时工具任务可查询；超限和失败有明确状态，无刷屏重试。
- [ ] 原 Web QQ 登录、聊天、SimC/PoB owner 隔离相关合同通过；发生客户端改动时才补 Web 构建。

## 运维与恢复

环境回退为停止 `chickenbro-napcat`，保留登录卷、配置、镜像摘要和记录。停止不删除数据。更新前停容器，对登录卷和配置建立私有快照，固定旧镜像；需独立验证可恢复后再清理任何副本。

管理入口通过：`ssh -N -L 16099:127.0.0.1:16099 wow-lighthouse`，浏览器访问 `http://127.0.0.1:16099/webui/`。面板密钥在服务器私有文件中；扫码时只展示当前二维码，避免将密钥放 URL 或提交到证据。初次登录完成前不启动通道业务服务。

## 上游依据

- [NapCat Docker 项目](https://github.com/NapNeko/NapCat-Docker)：镜像来源、持久化目录、WebUI。
- [NapCat 网络配置](https://napneko.github.io/config/basic)：正向/反向 WebSocket 和 token。
- [NapCat 安全说明](https://napneko.github.io/other/security)：账号登录、OneBot 鉴权和管理面板。

实际运行摘要、版本、端口和检查结果见[本批环境记录](../../artifacts/verification/2026-09-23-qq-napcat/environment.json)。NapCat `4.18.28`、Linux QQ `3.2.30-50969` 已启动，已核对管理鉴权、资源限制与生产进程/指针未变。QQ 已扫码在线，OneBot 授权读取与无凭据拒绝通过，模型生成已通过；截图确认只有接收提示可见，最终答案尚未送达，业务验收未通过。仅用扫码票据时的重启失败记录保留在[历史恢复记录](../../artifacts/verification/2026-09-23-qq-napcat/restart-recovery.json)；后续加入服务器私有密码回退，新容器启动及容器重启均无需扫码登录，见[自动登录验证](../../artifacts/verification/2026-09-23-qq-napcat/automatic-login-recovery.json)。整机重启未执行。上游文档用于部署合同，不能代替本机验证。

## 本批实现与验证

通道组合入口独立放在 `server/app/channels/qq/runtime.py`，直接组装 durable ChatApplication；因此无需改动 Web FastAPI 的组合入口或公开路由。现有 Worker 复用模型、研究、SimC/PoB 工具，使用 Candidate 专用 18795 loopback 网关。运行状态和代码身份见[实施记录](../../artifacts/verification/2026-09-23-qq-napcat/implementation.md)。

- Candidate 源码：`/opt/chickenbro-candidates/qq-channel-20260923`，数据库 `chickenbro_qq_channel_candidate_20260923`。
- 自动化测试库：`chickenbro_qq_channel_tests_20260923`；均与网站生产数据分离。
- `chickenbro-qq-channel-candidate` 负责 OneBot、队列和回复；`chickenbro-qq-worker-candidate` 复用现有 Worker。
- Candidate 私有配置为 `candidate-channel.json`，正式配置 `channel.json` 已配置指定群；网络异常恢复时曾关闭业务开关，自动登录恢复后已重新开启正式群通道。配置变更后重启通道服务生效；停止服务立即停止接收与发送。
- 启动使用 PostgreSQL 会话锁保持单实例。派发前重新核对群白名单和身份启用状态；收到的群消息在等待 OneBot 回执期间也同步持久化。
- Chat 已提交而 inbox 未绑定时，通过原始幂等键、owner、会话、正文对账恢复；不会重复模型或工具执行。
- Worker 有新公开进展且超过 30 秒时，最多追加一次进展通知。
- 发送超时/回执无效/发送中重启进入 uncertain，同批后续片段停止自动发送，群友可用 `/状态` 主动取回最近结果。
