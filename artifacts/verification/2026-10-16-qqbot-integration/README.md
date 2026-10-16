# 官方 QQBot 集成验证（2026-10-16）

本轮将原官方 QQBot 工作区的当前功能、测试及历史证据整理到 main 基线 `6b11e9db6`，云端继续原单测试群 `1127827451`。Web 双游戏产品与 QQ 网站登录继续原部署。

- 官方 Trigger、持久 inbox/outbox 与独立 `000`–`004` schema 已解除个人 QQ/NapCat 依赖；保留既有官方数据和表名。
- 战斗 v8 与默认引导 v2 改用通用无工具接口，强制关闭继承 MCP、搜索与内置工具。Web 默认模型路径不变。
- 修复撤群后新成员可进入的缺口；持久撤群状态覆盖已有成员、新成员与重启。
- 保留原单群白名单、真实 @、只读 WoW 查询与原发送预算；无自由 Chat、主动发送或新群扩展。

## 云端验证

QQBot 全量 221/221 测试通过（含最小权限数据库回归）；共享后端 889 项中 888 项通过，1 项为 Windows junction 平台跳过；控制检查 63/63。实际角色来源、WCL 战斗与两次无工具模型调用均通过。[来源与模型](source-model.json)、[QQBot测试](qqbot-tests.log)、[后端测试](backend-tests.log)、[控制检查](control-tests.log)、[最小权限](runtime-role-test.log)。本轮没有向 QQ 群发送验证消息，未新增群端人工验收声明。

## 部署与恢复

仅更新原官方 Candidate 的 37 个源码／SQL文件，应用加法迁移 `004`；45 个旧版源码／脚本／SQL文件移入 root 私有恢复目录。官方 channel 与 worker 新进程正常，网关重新就绪，queryOnly、单群与工具禁用保持。[部署逐文件SHA](deployment.json)。

570 个文件独立解包恢复一致，38 张表的数据库独立恢复指纹一致，备份留在 `/var/lib/chickenbro-retirement/qqbot-integration-20261016`；未切回演练。[恢复记录](recovery.json)、[执行器](release_ops.py)、[独立复审](review.md)。

Web API/Worker PID 和目录保持，1811 个后端文件与 15 个 Web 文件 SHA 保持；[公开静态文件](public-web.json) 15/15 一致。原官方 WIP 289 文件逐项匹配且原工作区未改动，[保护记录](wip-preservation.json)。

Git 提交、合入和远端身份见最终 `closure.json`。
