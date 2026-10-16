# 官方 QQ 测试群接入验证

**最新首版已限定为三个角色查询命令，已部署官方 Candidate 并保存群聊斜杠菜单。工程证据与真实群验收步骤见 [QUERY-ACCEPTANCE.md](QUERY-ACCEPTANCE.md)。下文保留初次接入基线。**

2026-10-14，用户授权开始接入，并创建测试群 `1127827451`（炸鸡test），以群主身份加入官方机器人。用户另授权仅向官方机器人专用云端环境安装 WebSocket 客户端。

## 已验证

- 官方机器人凭据已在 root/0600 私有文件中保存并验证 Token 获取成功；未把密钥写入源码、日志或本记录。
- 真实网关鉴权 READY 成功。实际网关为 `api.sgroup.qq.com`，与文档示例新域名兼容。
- 用户在已确认测试群发送 @，据真实事件绑定 group_openid；群事件中的 group_id 也是 OpenID，未拿数字群号冒充。
- Cloud baseline：原 QQ policy/OneBot/config 15 tests passed。
- Cloud targeted final：官方纯协议、独立 PostgreSQL、部署环境继承、config、旧 QQ、companion、Chat 跨客户端、native MCP 共 70 tests passed；Starlette/httpx 存在依赖弃用提示。
- 扩大验证首次发现云端部分源码打包缺少 native profile 模板；补齐已跟踪模板后上述 68 项全部通过。
- `@炸鸡 帮助`：Candidate inbox 为 done、command outbox 为 sent 且存在真实回执。用户回答“可以回复了！”并提供群端截图，帮助收发标记 user_accepted。
- 网站 API/Worker PID 核对仍为 `1195642` / `1195577`；原 QQ channel/worker 保持 inactive。
- 首次真实模型测试失败为 `CODEX_OUTPUT_INVALID`，无工具/模拟副作用；专用环境缺少源服务 HTTP(S)/ALL/NO_PROXY 和 CODEX_HOME 配置。已通过有界环境组合函数保留这些配置，并加回归测试；等待原测试运行终态后重启本次官方服务。
- 修正模型连接后，真实群提问运行 succeeded，耗时 11.48 秒，答案发送成功且有回执。用户回答“能回复了”，并提供群内 AI 能力介绍截图，基本 AI 问答标记 user_accepted。
- 截图中的“排队”来自无条件接收确认。新增 PostgreSQL 回归先复现固定确认，再修正官方通道；普通问答无 canned ack，答案以序号 1 正常发送。排空 Candidate 后仅重启官方 channel 应用修改，未重启网站及官方 AI worker。

## 验证范围

官方机器人仅服务一个测试群，使用 `chickenbro_qq_official_candidate`；数据库测试在独立 `chickenbro_qq_official_tests`，没有复制生产数据。源码见 [实施记录](../../../docs/plans/2026-10-14-qq-official.md)。

当前尚待验证：第二真实群用户、真实游戏工具/SimC/PoB、去掉固定确认后的新一轮群端截图。模型连接修正后的服务重启已通过真实 AI 群回复；纯协议/SQL 隔离验证不冒充完整业务验收。

源码处于独立 `codex/qq-official` 工作区，未提交、推送或合入。官方服务已在指定测试群启动，未配置开机启动，也未公开开放其他群或私聊。
