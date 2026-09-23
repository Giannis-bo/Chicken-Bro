# QQ 群文字通道实施记录

2026-09-23。用户在设计与环境准备后明确要求“可以，接入”。

## 实现

- `server/app/channels/qq` 连接 NapCat 的 loopback OneBot 11，以独立 token 验证真实 bot 身份、在线状态与群成员关系。
- 仅指定群、新鲜真实 @ 触发；私聊、自发消息、普通聊天不进入模型。文本上限 4000 字，图片/文件明确提示当前不支持。
- bot/group/sender 映射服务端 UUID；每用户/游戏/代次独立上下文。不签发 Web session，不绑定网站 QQ OAuth 身份。
- 使用原 ChatApplication durable admission 和 Worker；0015 增量迁移保存来源 actor、inbox/outbox/群身份/会话映射。
- 1 个进行中请求，每人 1 个等待，全通道 10 个等待；每人每分钟最多接收 12 次触发（包含命令）。
- `/游戏 wow|poe2`、`/新会话`、`/状态`、`/帮助`；超过 30 秒且有公开进展时最多追加一条进展。
- 幂等涵盖 Chat 提交后 inbox 绑定前的进程中断。消息在等待 OneBot 回执期间同步持久化；撤销白名单/禁用身份后停止派发旧排队请求。
- 回复以纯文本段发送，引用触发消息；不解析 CQ 控制码。最多 5 条，每条 1500 字。不确定回执停止该答案的自动重发与后续片段，支持主动 `/状态` 取回。

## 验证

所有 Python 执行及数据库测试均在云端已有 `/opt/chickenbro-runtime` 中进行，未新增运行依赖。

- 完整后端：878 tests，877 passed，1 skipped。跳过的是仅 Windows 执行的目录 junction 检查。
- QQ/OneBot/真实 PostgreSQL/durable 定向集合：27 tests passed。
- 正式 Worker 范围、心跳隔离与原运行 readiness：20 tests passed。
- 独立代码审查发现并修复两项：等待回执时断线丢入站消息、撤销白名单后仍执行排队请求；对应回归先失败后通过。
- Candidate 真实 QQ 提问完成一次模型回答，接收提示可见；最终答案回执进入 uncertain。最初误将 NapCat 本地历史的唯一消息记录作为送达证据，人工改为 sent；用户随后截图证明群内只有接收提示，已撤回这个送达判断并恢复 uncertain。单次明确恢复发送取得 retcode=1200、QQ 内核 result=1006514（网络连接异常），未送达最终答案。
- 重启通道进程后保持原 run/outbox，无新增生成和重复消息。未再次重启 NapCat。
- 独立正式 QQ 数据库已经创建并启用，网站生产 API/Worker PID、启动时间与 backend/Web 指针保持不变。正式群消息验收未通过：QQ 管理状态曾显示在线，但实际内核消息连接异常，新消息未入站。后续密码回退已通过重启自动登录验证，当前正式通道已恢复，等待群收发复验。

结构化运行身份和各阶段统计：[candidate-runtime.json](candidate-runtime.json)。源码以基底提交加逐文件 SHA-256 标识，当前修改未提交 Git，不把基底提交冒充新增代码已提交。

## 部署与持久化

| 项目 | 位置 |
| --- | --- |
| 正式源码 | `/opt/chickenbro-qq-current` → `/opt/chickenbro-qq-releases/20260923-text-v1` |
| 正式独立 DB | `chickenbro_qq_channel` |
| 正式服务 | `chickenbro-qq-channel`、`chickenbro-qq-worker`；已启用开机恢复 |
| 通道配置 | `/etc/chickenbro-qq-channel/channel.json`；指定群白名单；当前 enabled=true，故障恢复时曾暂停 |
| 私有环境与凭据 | `/etc/chickenbro-qq-channel/production.env`，systemd LoadCredential；数据库票据限定 QQ 独立库，私有目录/0600 |
| 状态与模型任务 | `/var/lib/chickenbro/qq-channel` |
| Worker 工具入口 | `127.0.0.1:18795`，现有 capability/owner 检查 |
| Candidate | `chickenbro_qq_channel_candidate_20260923` 与两个 candidate 服务；验证后已停止并关闭候选业务开关 |
| 自动化测试 | `chickenbro_qq_channel_tests_20260923`，不连接实际 QQ |

正式通道新增 `WOW_WORKER_V2_SCOPE=qq_group`，只允许指定独立 DB，并使用 `/var/lib/chickenbro/qq-channel/worker-heartbeat.json`；默认 Web Worker 路径不变。候选实际群测试数据保留在 Candidate，没有迁入正式库。

## 恢复与剩余边界

停止 `chickenbro-qq-channel` 可立即暂停接收和发送；待 Chat/SimC/PoB 在途任务排空后再停止 `chickenbro-qq-worker`。不停止网站现有服务，不删除 QQ 登录卷或新业务数据。开关/白名单修改后重启通道进程生效。

正式库初始快照保存在 `/var/lib/chickenbro/qq-channel-recovery/20260923-text-v1`，已独立恢复到 `chickenbro_qq_channel_restore_20260923`，核对 16 条迁移、4 张通道表；快照当时没有业务记录。这证明初始结构可恢复，不代表后续新增数据已备份。恢复时不能用初始快照覆盖新增群消息。

NapCat 自动登录已追加密码回退，固定镜像下新容器启动和容器重启均通过免扫码登录验证。凭据使用服务器 root/0600 私有文件只读挂载，在进程环境中加载；未保存明文密码，未写入 Docker Config.Env。整机重启未执行；验证码或设备确认仍需人工处理。详见 [automatic-login-recovery.json](automatic-login-recovery.json)。通道服务重连不反复尝试密码登录。已确认发送错误为 QQ 内核 1006514 网络连接异常；容器 DNS/HTTPS 连通，未见 OOM/pids 限额事件，根因继续定位，当前错误日志只增加受控错误类别/数值 retcode，不记录消息正文或凭据。

图片、群文件、网站账号绑定、跨群共享上下文未开放。群消息中的任意用户文字不获得部署、shell、凭据读取或群管理权限。

## 证据更正

用户截图显示 12:29、12:33:49 两条新 @ 未获回复，12:22 仅有接收确认。历史 `candidateReceiptReconciliation` 只证明本地缓存含发送记录，不能作为对端可见或 QQ 实际发送成功的证据，现标记为撤回。源码和数据库合同测试仍有效，端到端业务验收未通过。

## 正式通道用户验收

2026-09-23 14:01 的真实 hello 提问已完成模型生成，并取得接收提示和最终回答的显式 OneBot 发送回执。用户随后明确确认“OK，现在消息通道已经OK。”，记录于 [production-hello.json](production-hello.json)。此前 Candidate 最终答案未送达及本地历史证据撤回保持不变；本次验收仅覆盖正式文字消息通道，不包含后续拟人陪伴、主动水群或表情包能力。
