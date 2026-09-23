# NapCat 环境

本目录保存 NapCat 环境和 QQ 通道 systemd 服务。文字适配器位于 `server/app/channels/qq`，复用现有 Chat/Worker；当前运行状态见[实施记录](../../artifacts/verification/2026-09-23-qq-napcat/implementation.md)。

设计与范围见 [QQ 通道设计](../../docs/plans/2026-09-23-qq-napcat-channel.md)。

## 首次部署

在 `wow-lighthouse` 核实实例、资源、生产状态及端口后，将本目录的三个文件 `image-lock.json`、`prepare-host.sh`、`start-napcat.sh` 放到新的临时部署目录。

提前拉取 `image-lock.json` 指定的完整镜像引用；脚本不自动下载或使用最新标签。以 root 执行 `prepare-host.sh`，随后运行 `/opt/chickenbro-qq-channel/start-napcat.sh`。已有目录、用户、容器或网络会使准备停止，避免覆盖登录状态。

准备脚本生成独立 WebUI/OneBot 密钥并保存于 `/etc/chickenbro-qq-channel/credentials.json`（root/0600）。`channel.json` 中 `enabled=false`，群白名单为空；这是后续适配器的部署配置，当前没有业务进程消费它。

## 登录与验证

```sh
ssh -N -L 16099:127.0.0.1:16099 wow-lighthouse
```

访问 `http://127.0.0.1:16099/webui/`。管理员在私有终端读取 WebUI 密钥，输入面板后使用小号手机 QQ 扫码。凭据不要粘贴到聊天、Git、截图或 URL 中。

账号登录后使用 `sudo python3 /opt/chickenbro-qq-channel/verify-onebot.py` 只读核对实际 QQ 号、目标群成员关系及指定群主；脚本不发送消息。账号专属 OneBot 配置可能覆盖 `onebot11.json`，必须回读实际 3001 监听与 token 校验，分别验证未授权连接拒绝、授权连接成功；不能仅检查 JSON。

收到用户指定的小号、测试群与管理员后，可以预先配置 `botQQ`、`allowedGroups`、`adminQQs`，并核对登录身份。只有适配器实现并通过 Candidate/测试群验收后才开启正式群业务；参数已配置不代表业务开关已开启。

检查容器时使用选择性 inspect，不打印全部 Config.Env、配置正文或原始日志。`--log-driver none` 避免上游启动输出的 token/登录二维码进入 Docker 日志；NapCat fileLog/consoleLog 已关闭。

## 停止和恢复

`sudo docker stop chickenbro-napcat` 停止通道环境并保留卷；`sudo docker start chickenbro-napcat` 恢复。不要删除登录目录或运行 docker volume prune。版本更新另建私有快照和精确恢复清单，再按固定镜像更新。

容器重启策略为 `unless-stopped`，会随 Docker 恢复已启动的容器；人工停止后不自动恢复。

2026-09-23 实测：仅使用已扫码票据时，重启后的快捷登录失败。补充密码回退后，新容器启动和随后一次容器重启均无需扫码恢复登录；重复重启检查在启动约 30 秒后确认 WebUI ready、正确 QQ 身份、OneBot online 和目标群。见[自动登录验证](../../artifacts/verification/2026-09-23-qq-napcat/automatic-login-recovery.json)。整机重启未执行。

密码回退使用服务器私有 `/etc/chickenbro-qq-channel/login.env`，仅含 `NAPCAT_QUICK_ACCOUNT` 和 `NAPCAT_QUICK_PASSWORD_MD5`。该文件必须 root/0600，以只读方式挂载到容器 `/run/secrets/napcat-login.env`；启动包装器在进程环境中加载，凭据值不放进 Docker Config.Env、启动参数、Git 或证据。MD5 仍属于登录凭据，按密码保护；不保存明文密码。此能力已包含在固定的 NapCat 4.18.28 中，无需升级依赖。

正常启动先尝试快捷登录，失败后尝试密码回退。若 QQ 返回验证码或新设备确认，需人工完成验证；不循环重启或重复密码尝试。只读 WebUI/OneBot 在线检查不代表群消息已送达，仍需群端可见回复。

此次保留的旧容器 `chickenbro-napcat-before-autologin-20260923` 已停止且 restart=no；旧启动脚本为 `/opt/chickenbro-qq-channel/start-napcat.before-autologin.sh`。回退必须先停止当前容器，不可让两个容器同时打开同一 QQ 数据目录。

## 通道服务

正式 systemd 单元为 `chickenbro-qq-channel.service` 与 `chickenbro-qq-worker.service`；源码指针 `/opt/chickenbro-qq-current`，独立正式数据库 `chickenbro_qq_channel`。环境文件 `production.env` 为 root/0600，包含既有服务模型/来源配置及限定 QQ 数据库的 `PGPASSFILE`，通过 systemd 加载，不打印其正文。WebUI/OneBot token 与 channel.json 使用 LoadCredential。正式 Worker scope=qq_group，心跳、模型任务目录与网站分离。

应用 0015 迁移、核对固定源码 SHA、独立数据库和新端口后，才能开启指定群。候选单元使用 candidate.env/candidate-channel.json，独立候选 DB。候选与正式共用 18795 工具端口和 bot，因此必须排空并停止候选，再启动正式服务。

`sudo systemctl stop chickenbro-qq-channel` 暂停群接入；等待在途任务完成后可停止 `chickenbro-qq-worker`。恢复用 start。白名单与 enabled 修改后需 restart 通道进程；不要重启 NapCat 来刷新业务配置。首次环境验证器 `verify-environment.py` 的 businessDisabled 检查仅用于尚未开启业务的准备阶段；正式运行证据单列。

## 陪伴角色模式

可信 `channel.json` 使用 `mode=companion`、`proactiveEnabled=true/false`，同时 `production.env` 设置 `WOW_QQ_COMPANION_ENABLED=1`；不一致时通道拒绝启动。legacy 模式使用原文字通道，环境开关必须为 0 或省略。修改后只重启 QQ 接入/Worker，NapCat 和网站保持原进程。

companion 接收白名单群所有消息，真实 @ 优先且必答；未 @ 的参与由模型判断，无固定发言冷却或次数配额。3 秒/10 秒窗口仅合并输入。社交与专业运行各一个执行槽，社交没有工具；QQ 专业运行按 run/owner 持久 scope 限制来源与 SimC，禁用 PoE2 和系统工具。

缓存按群限 7 天/5,000 条，输入近 2 小时/80 条；持久记忆仅本人明确称呼、偏好和角色，支持本人修正/遗忘。共享上下文从观察按需取用，不额外保留个人事实摘要副本。表情从本目录 manifest 校验后以内联 base64 发给本机 NapCat，不接受模型文件路径或 URL。回执不明记录 uncertain，不自动重发。

切换前暂停 QQ 接入、排空运行、备份并独立恢复验证正式 QQ 数据库。增量迁移 0016/0017/0018 后切新源码；先关主动参与验证 @，再开主动参与。回退关闭主动参与或切旧代码/legacy 配置；保留新表和数据。独立 Candidate 仅使用记录 transport 和 18796 工具端口，不启动第二个群 sender。

## 主动参与当前运行合同

2026-09-23 已开启 proactiveEnabled。仅来源时间最近 120 秒的新消息可触发主动决定，旧话题只推进观察游标；这不限制发言频率。关闭开关后遗留主动队列和待发草稿停止，@ 仍优先回应。可通过可信 knownBotQQs 数组排除已知机器人；配置不从聊天内容读取。最新证据见 [启用记录](../../artifacts/verification/2026-09-23-qq-companion/activation/README.md)。

社交消息默认直接发送，模型可用 quote=true 明确引用当前触发消息；发送目标由后端绑定。0020 在 outbox 持久化 quote_reply，历史/专业回复保持原合同，社交长回复仅首段可引用。
