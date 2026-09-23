# QQ 主动参与启用与规划对账

2026-09-23。当前用户授权实施全部七项陪伴角色计划。核对发现主目录文档停在实施前，而隔离工作树及云端已完成角色 v1、表情 v2、自然回复 v3；本批接续现有代码完成剩余主动开关与修复，保留此前成果。

## 本批实现

- 主动判断仅处理来源时间在最近 120 秒的新事件，过期观察推进游标；这是消息新鲜度约束，不是发言冷却或次数配额。
- 关闭主动开关后，遗留 pending/running 主动响应转为 silent，待发送主动草稿停止；sending/uncertain 和实际专业任务保持原语义。
- 允许群的 @ 待答或待发送时优先回应；撤销群的积压不阻塞当前群。发送认领时再次核对。
- 新增可信 knownBotQQs 可排除已知机器人，正文不能修改配置。默认空列表，未擅自把群友归类为机器人。

## 验证

- 四项 PG 回归先失败（旧观察、禁用遗留队列与出站、旧队列、跨群优先级），修复后通过；复审发现撤销群积压范围问题，新增回归先失败后通过。已知机器人入站测试先失败后通过。
- 云端隔离 QQ Python/PG 定向集合最终 80 项通过，无跳过；主目录与隔离工作树的 16 项状态、owner、保留与链接检查通过。之前角色工具、owner、真实 SimC 等证据见上级 README，未冒充本批重跑。
- [真实模型 Candidate](candidate.json)：非 @ 新话题完成主动回复；关闭主动开关后的 @ 仍正常回应并记住本人称呼。只出现 userMessage/agentMessage 类型，无工具调用；transport 为 record_only，没有向真实群发测试消息。
- 独立只读复审关闭上述问题，最终无新增 P1/P2。

## 发布与验收

[发布记录](release.json)与[逐文件清单](release-manifest.json)：正式源码为 /opt/chickenbro-qq-releases/20260923-companion-active-v4，共 236 项 server 文件。使用共享发布锁，核对旧版本、排空 QQ 任务，备份当前 QQ 库并独立恢复逐表核对后切换。无新迁移。先确认关闭主动的模式在线，再开启 proactiveEnabled=true。网站 API/Worker PID、代码/Web 指针及 NapCat 启动时间保持一致。

用户在本任务确认群内 @ 后的文字和表情可见，并随后明确这不包含主动发言；按此范围登记。真实主动参与、群友记忆和 SimC 的群端体验仍按后续自然消息核对，不把 Candidate 或开关开启当作人工验收。

## 回退

可信配置将 proactiveEnabled 设为 false 后重启 QQ channel；保留观察、@ 回复、数据库及实际专业任务。严重问题按 release.json 的 oldRelease、backup/channel.json 和 backup/production.env 恢复 QQ 代码及配置，保留新写入。原生产基底为 companion-social-v3，未回退数据库。

Git 源码尚未提交或推送；本次同步原主目录前逐文件核对早期工作树基线并留存覆盖前快照。

[最终只读回查](live-readback.json)：236 项正式哈希匹配、proactiveEnabled=true，QQ 两服务 active，Candidate 两服务 inactive；观察截至回查时没有新的自然主动回复，未宣称主动群端验收通过。
