# 官方 QQ 帮助按能力分组

用户要求：`/帮助` 按角色查询和战斗分析分组，让用户快速找到命令。已更新原单群 Candidate；实际群内展示待用户实测。

角色查询组按角色资料与近期成绩、团本成绩、大米成绩分别展示完整命令，再列可选条件、快捷筛选与地域。战斗分析组区分整场摘要和人物详情，说明大腿／毒瘤用途、详情上下文、人数与整场范围。`/状态` 和 `/帮助` 入口留在末尾。

## 验证

- [45项相关云端检查](cloud-tests.log)通过，无skipped；覆盖默认短介绍、完整帮助入库回复、角色命令、战斗命令及 v8 角色绑定。没有新增测试或运行本地应用测试。
- 静态AST比对确认只改 HELP／BATTLE_HELP 文案赋值，解析、模型与查询逻辑保持。原默认57字介绍保留。
- [26文件清单](runtime-manifest.json)精确变更 query_commands.py、battle_commands.py；部署前核对旧SHA、staging SHA、原工作目录、单群配置与空队列，核验旧副本后仅重启官方channel。
- [部署回执](deployment.json)、[最终读回](final-check.json)确认26文件匹配、gatewayReady、queryOnly、单群和战斗 v8。帮助489字符、单条消息，六命令分组顺序与默认短回复均核验；完整帮助原文保存在最终读回的 helpContent。
- Web API／Web worker／官方AIworker PID保持2319609／2319544／267252；Web来源和通道配置SHA保持。未主动发送QQ验证消息。

原WIP副本见 [before-manifest.json](before-manifest.json)。云端旧文件副本位于 `/etc/chickenbro-qq-official/help-grouping-backup-20261016T081443Z`，旧SHA已核验，未做恢复演练。未改数据库schema、凭据；未提交、推送或合入。
