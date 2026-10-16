# 官方 QQ 默认回复精简

用户授权：默认问题如“你都能干啥”简短介绍能力，完整命令格式放到 `/帮助`。

当前原单群 Candidate 已更新，群端新文案待用户实测。默认回复：

> 我是炸鸡，能查魔兽角色资料、团本和大米成绩，也能分析 WCL 战斗日志，点评大腿和毒瘤。
> 具体命令格式看 /帮助。

未识别文本或命令返回该介绍；`/帮助` 继续返回原完整说明，已知命令的缺参提示继续指出所需参数。没有记录时 `/状态` 改为“你还没有查询记录。发送 /帮助 查看用法。”。queryOnly、通用AI关闭、单测试群及已验收的战斗分析 v8 保持。

## 验证与更新

- [云端初始失败](red.log)：4项新检查中3项复现旧长回复；修改后[23项针对性检查](targeted.log)通过。
- [207项相关云端检查](cloud-tests.log)通过，无skipped：覆盖官方通道、角色查询、默认介绍／完整帮助、无查询／AI任务创建、PostgreSQL隔离与战斗 v8。没有运行本地应用测试。
- 对照当前WIP副本审阅差异：仅新增简介常量、替换默认兜底及空状态提示。原帮助文案与既有命令路由保留。
- [26文件清单](runtime-manifest.json)仅2文件变更：query_commands.py、query_repository.py。部署前核对旧SHA、staging SHA、原服务工作目录、单群及空队列，核验旧文件副本后仅重启官方channel。
- [部署回执](deployment.json)、[部署后读回](final-check.json)：26文件匹配，gatewayReady、queryOnly、单群、战斗展示 v8；原问题及同类输入返回短介绍，完整帮助保留。
- Web API／Web worker／官方AIworker PID保持2319609／2319544／267252，Web来源与官方通道配置SHA保持；无凭据和数据库schema变更。QQ验证消息发送0。

回退副本：`/etc/chickenbro-qq-official/default-reply-backup-20261016T080735Z`，旧SHA已核验，未做恢复演练。现有WIP副本见 [before-manifest.json](before-manifest.json)。继续保留原工作区、分支 `codex/qq-official` 与未提交、未推送、未合入状态。
