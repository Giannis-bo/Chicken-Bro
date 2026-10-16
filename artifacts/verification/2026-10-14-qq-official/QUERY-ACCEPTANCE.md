# 官方 QQBot 角色查询：真实群验收

2026-10-15 用户已确认收到原版角色查询回复。当前 Candidate 已更新为 **Markdown、团本／大秘境各最近 5 场**；以[新版验收步骤和证据](../2026-10-15-qq-query-markdown/README.md)为准，以下保留首版来源与部署记录。

2026-10-14，三个命令已部署到官方 QQ 独立 Candidate，并在 AppID `102828220` 的群聊指令面板保存、启用。仅允许炸鸡test（`1127827451`），真实群业务验收为 **pending**。源码留在 `codex/qq-official`，未提交、推送或合入。

## 命令

```text
/角色查询 角色名 服务器名 [地域=国服]
/角色团本查询 角色名 服务器名 [团本=名称] [Boss=名称] [难度=英雄] [地域=国服]
/角色大米查询 角色名 服务器名 [副本=名称] [层数=12] [地域=国服]
```

地域支持国服/cn、美服/us、欧服/eu、台服/tw、韩服/kr，默认国服。带空格的名称加双引号。Boss/团本/副本支持精确英文名或目录编号，已确认的国服名称也可用；多义简称返回候选。未指定内容时采用实时 WCL 当前目录及默认分区，回复明确标注分区，旧分区成绩不冒充当前分区成绩。

后台设置均为「发送指令」、非管理员专属、已启用。说明分别为「查询角色资料与WCL成绩」「查询团本成绩，支持指定首领」「查询大米成绩，支持副本层数」，平台实际计数为 21/30、25/30、25/30。已保存截图：[slash-menu.png](slash-menu.png)。

## 两位真实用户的验收步骤

均在炸鸡test 操作，至少第二位是普通成员。每人同时保留一项查询，完成后再发下一条。

1. **菜单与缺参**：桌面 QQ 在输入框上方点击「机器人指令」图标（机器人头像状，在连续互通图标右侧），可看到三个指定入口。2026-10-15 已在炸鸡test 实际打开，见 [desktop-slash-menu.png](desktop-slash-menu.png)。选中命令后确认消息包含从 QQ 成员候选选取的真实 `@炸鸡`，再发送；也可直接 `@炸鸡 /角色查询`，应提示补齐角色名和服务器，不进入普通 AI 问答、不发固定「排队」确认、不沿用他人的角色。单独输入 `/` 自动弹出面板的行为尚未验证，不作为通用桌面端验收前提。
2. **角色资料**：发送 `@炸鸡 /角色查询 Giannis 白银之手`。核对种族、职业、专精、英雄天赋、装备等级和成绩摘要，含资料来源及时间。本次只读样本是黑铁矮人、萨满祭司、元素、先知、装等 327，Raider.IO 资料时间为 2026-10-13 22:51 北京时间。验收以当时最新来源为准，不固定这些数值。
3. **团本/Boss**：发送 `@炸鸡 /角色团本查询 Giannis 白银之手 Boss=内克扎莉 难度=英雄`。当前目录为烈毒之渊 `12.1.5`；样本无该分区成绩，应显示「暂无公开记录」，不能变成 0 分。再用确有当前公开成绩的角色查询，核对 Boss、难度、记录专精、DPS/HPS、百分位及颜色。有具体最高记录时核对时间和报告链接；WCL 汇总未给时间时明确显示「来源未提供」。团本正成绩的真实群展示待此次验收。
4. **指定大米副本/层数**：发送 `@炸鸡 /角色大米查询 Giannis 白银之手 副本=诸王之眠 层数=12`。只能展示 +12，含记录专精、DPS/HPS、限时状态、分数颜色、时间和报告链接。部署后 2026-10-14 21:40 的来源读取为元素、DPS、+12、限时、`95.65488409730952（橙分）`，对应 2026-09-04 22:10 记录。使用 **WCL 同层、角色排名、历史百分位** 核对，不能拿全层总览或 Parses 口径代替。
5. **异常与范围**：分别测试缺服务器、未知副本、重复层数、`/游戏 poe2` 和「帮我跑模拟」。应提示补齐、候选或当前查询范围，不启动 AI/SimC/PoB。无记录与网络查询失败应有不同提示。
6. **第二用户并发/状态**：两人同时查不同角色，各条回复应绑定原提问，不能串角色。分别 `@炸鸡 /状态`，只返回本人最近查询；普通成员能使用三个菜单入口。

保存关键回复截图和提问时间。异常反馈提供完整命令及实际回复，便于对账 inbox/outbox 和来源范围。用户明确完成上述步骤后才标记 `user_accepted`。

## 2026-10-15 桌面入口核对

- 新版管理页刷新后重新选择群聊场景，三个指令仍保存且启用。官方 `GET /v2/panels?scope=group&limit=20` 返回一个已生效的群聊面板，版本 1，包含这三个 command，更新时间为 2026-10-14 21:47:55 +08:00。参考[官方查询接口](https://bot.q.qq.com/wiki/develop/api-v2/autogen/api/v2_panels.get.html)。
- 在本机桌面 QQ 的炸鸡test 群点击「机器人指令」图标，实际展示 `/角色查询`、`/角色团本查询`、`/角色大米查询` 及各自说明；仅核对面板，未代用户发送消息。
- 用户 10:27 发送的 `/角色查询 Giannis 白银之手` 未带真实 @；Candidate inbox 仍只有 2026-10-14 的三条接入记录，该查询未被接入。当前网关订阅和解析限定 `GROUP_AT_MESSAGE_CREATE`，手工发送普通斜杠文本不能触发查询。官方网关 READY，queryOnly=true，白名单数量 1。
- 当前证据确认桌面菜单可见，角色查询群端回复、第二用户隔离与完整业务验收仍待完成。本次无运行代码、配置、服务或数据库改动。

## 已验证的工程范围

- 云端 76 项测试通过：解析/格式、身份与来源错误、原始小数判色、不适用难度、多个当前团本、历史治疗 HPS、SQL 幂等/第二用户/租约 fencing/撤销/过期取回，以及既有官方协议、配置、QQ、跨客户端和 native MCP 回归。Starlette/httpx 有既有弃用提示。
- 独立只读代码审查及复查完成，实质问题已处理。
- 专用业务库 `chickenbro_qq_official_candidate` 仅新增 `002_queries.sql`，测试库为 `chickenbro_qq_official_tests`。两个线程读取公开数据，网关继续心跳，查询不创建 Chat/SimC/PoB 任务。
- Candidate 的 14 个运行文件与 [query-source-manifest.json](query-source-manifest.json) 哈希一致；网关 READY、queryOnly=true、白名单数量 1。见 [query-deployment-result.json](query-deployment-result.json)。
- 真实国服来源结果：[query-source-smoke.json](query-source-smoke.json)；部署后使用官方 channel 自身读取配置：[query-deployed-source-smoke.json](query-deployed-source-smoke.json)。这些是来源读取证据，尚不是群端收发验收。
- 网站 API/Worker PID 为 `1195642`/`1195577`、官方 AI Worker 为 `267252`，均未变化。网站 readiness HTTP 200；旧 NapCat channel/worker 均 inactive。Web 无源码或构建变更。
- 私有回退副本：服务器 `/etc/chickenbro-qq-official/query-backup-20261014T133748Z`；源文件和 runtime.env 副本哈希已核对。停止接入只需停官方 QQ channel，保留数据和回退副本，网站无需重启。本次未执行恢复演练。
- 首包含 macOS AppleDouble 元数据，在文件清单校验处被拒绝，未应用源码/迁移/配置；改为 14 个普通文件精确包后部署成功。初始 `compare:Parses` 的统一 100 探针只用于诊断，不用于验收；最终为 `compare:Rankings + byBracket:true + Historical`，已验证真实分档百分位。

云端测试命令：

```sh
cd /opt/chickenbro-qq-official-query-staging-20261014
sudo -u postgres env QQ_OFFICIAL_TEST_DSN=postgresql:///chickenbro_qq_official_tests \
  /opt/chickenbro-qq-official-runtime/bin/python -m unittest \
  tests.app_qq_character_commands_test tests.app_qq_character_source_test \
  tests.app_qq_character_postgres_test tests.app_qq_official_test \
  tests.app_qq_official_postgres_test tests.app_config_test \
  tests.app_qq_channel_test tests.app_qq_onebot_test \
  tests.app_chat_cross_client_test tests.app_chickenbro_native_mcp_test
```

不得改用业务/生产数据库运行测试。
