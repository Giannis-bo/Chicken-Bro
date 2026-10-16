# 官方炸鸡 QQBot

当前只服务原测试群 `1127827451` 对应的单一 `group_openid`，通过群内真实 @ 接收消息。群配置与凭据由云端 root 私有文件管理；QQ 网站 OAuth 属于独立身份入口。

当前命令：`/帮助`、`/状态`、`/角色查询`、`/角色团本查询`、`/角色大米查询`、`/战斗分析`、`/战斗详情-大腿`、`/战斗分析-菜鸡`。角色类结果采用 `markdown_recent3_v1`，战斗类采用 v8 中文证据叙述；非命令由无工具、无多轮记忆的模型给出范围内用法引导。准确命令语法以 `query_commands.py` 的 HELP 为准。快捷团本编号从实时目录解析。

保持原单群白名单，不开放自由 Chat、私聊、主动发送、新群、POE2 或 SimC。`GROUP_DEL_ROBOT` 持久禁用该群，重启或新成员不会恢复授权。

## 存储与验证

`000_schema.sql` 至 `004_group_revocations.sql` 仅用于官方独立数据库，按文件名顺序执行。保留 `qq_channel` 表名兼容现有数据，源码不依赖已退役个人 QQ 模块；不得加入 Web 的产品迁移序列。

云端使用专用测试数据库运行：

```sh
QQ_OFFICIAL_TEST_DSN=postgresql:///chickenbro_qq_official_integration_tests_20261016 npm run test:qqbot
```

测试数据库与当前 Candidate 数据库分离。状态恢复、查询租约、跨群／跨用户隔离、发送不确定状态及撤群均有数据库回归。`probe.py` 用于只读首次事件绑定；不得同时启动第二个实际 sender。

`deploy*.py` 为早期分次交付执行记录，参数与文件集不代表当前完整版本。后续维护以[集成记录](../../artifacts/verification/2026-10-16-qqbot-integration/README.md)及[Runbook](../../docs/chickenbro-simc-production-runbook.md)为准。
