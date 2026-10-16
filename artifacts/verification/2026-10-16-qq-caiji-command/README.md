# 斜杠入口改名：战斗分析-菜鸡

用户要求将“战斗分析-毒瘤”改成“战斗分析-菜鸡”。核对实际旧入口为 `/战斗详情-毒瘤`，已在会话说明按用户指定的新名称 `/战斗分析-菜鸡` 实施。原单群 Candidate 和群聊指令面板已更新，QQ客户端实际菜单显示待用户确认。

## 改动与边界

- 新入口仍映射 battle_review，同一用户／群／报告／场次的原问题复盘与缓存保持。旧 `/战斗详情-毒瘤` 留作输入兼容，不在新帮助或菜单展示。
- `/帮助`、摘要详情入口、详情标题、默认介绍用词和口语化引导的真实命令列表同步。大腿入口不变，六条菜单顺序和其他五条配置保持。
- v8分析、事实绑定、模型规则文件和缓存版本保持；口语化引导v2、无工具、无自由聊天边界保持。没有回写历史请求、结果或证据文案。

## 验证和交付

- 调整既有命令与PostgreSQL上下文检查覆盖新名称和旧别名，[初始失败](red.log)复现旧入口与文案；[66项针对性检查](targeted.log)、[220项云端回归](cloud-tests.log)通过，无skipped。未运行本地应用测试。
- [28文件清单](runtime-manifest.json)精确更新4文件：battle_commands.py、query_commands.py、guidance.md、runtime.py。旧SHA、staging、单群、原工作目录和空队列检查后核验旧副本，仅重启官方channel。[部署回执](deployment.json)。
- [最终检查](final-check.json)：28文件匹配、网关READY、queryOnly、单群；新旧输入产生相同 battle_review 请求，帮助489字、新入口与无工具提示白名单一致。诸王之眠报告 YptH9vaxBChMTn7b 第1场 v8缓存直接复用，新增模型调用0；新摘要入口和“战斗分析·菜鸡”标题通过，三项服务PID及Web来源保持。
- 原Chrome管理页的群聊场景编辑原第六条命令，仅修改名称。先保存编辑弹窗，再保存整个面板；确认“有改动”及保存按钮消失，六条命令保持启用。当前版本使用UI保存与读回，没有宣称本轮API读回。[菜单记录](menu.json)、[截图](menu-saved-crop.jpg)。未开新标签页，未主动发送QQ验证消息。

云端回退副本 `/etc/chickenbro-qq-official/caiji-command-backup-20261016T084505Z` 已核验旧SHA，未做恢复演练。菜单可编辑原第六条名称恢复，原配置记录在 menu.json。没有数据库schema或凭据变更；未提交、推送或合入。原WIP副本见 [before-manifest.json](before-manifest.json)。
