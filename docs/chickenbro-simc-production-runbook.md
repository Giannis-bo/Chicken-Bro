# Chickenbro 生产 Runbook

适用于 Web/QQ、Chat 和云端 SimC。按当前任务授权及[验证矩阵](verification-matrix.md)操作；Badcase 持续授权范围见[工作流](plans/2026-09-08-badcase-workflow.md)。发布不自动授权新数据删除、依赖安装或基础设施变更。

## 运行身份与配置

操作前核对 `wow-lighthouse` 对应实例、代码/Web 指针、systemd API/Worker 有效工作目录与配置来源、数据库、实际文件和制品哈希。正式库为 `chickenbro_prod`，网站为 `https://www.chickenbro.cloud/`，readiness 为 `/api/v2/health/readiness`；这些是核对入口，不是本次健康证明。

- QQ 服务端配置为 `WOW_QQ_APPID`、`WOW_QQ_APP_KEY`、`WOW_QQ_REDIRECT_URI`，部署记录使用 root/0600 `/etc/chickenbro-qq.env`；正式 callback 为 `https://www.chickenbro.cloud/api/v2/auth/qq/callback`。不打印秘密值、DSN 或 token。
- 核对当前实际启用的 Codex、Chat 持久化、compiler、引擎与管理员配置；不从旧发布目录名推断当前版本。`WOW_ADMIN_USER_ID` 必须是经核验的内部 QQ owner，不能用昵称、QQ 数字或固定测试账号代替。
- Candidate 使用独立数据库、Cookie、目录和端口；涉及真实 QQ 授权时使用已登记 callback。测试环境见[测试账号说明](test-account-login.md)。

## 发布流程

1. 绑定本次源码、实际生产基底、完整差异、配置和逐文件制品清单，排除其他任务 WIP；运行受影响测试，准备旧代码/Web、精确 drop-in 清单及可核验恢复材料。
2. 在隔离 Candidate 验证受影响合同与真实业务，记录未覆盖项。涉及数据库迁移时先验证前后版本兼容与恢复方案，不能仅依赖应用回退。
3. 使用本批受审查且哈希固定的执行器。在发布锁内重查基底，有界等待 Chat execution、SimC 与队列安全排空；不能为了窗口强杀任务。
4. 按清单切换受控文件或指针，API/Worker 同时加载匹配源码与配置，Web 与接口合同一致。readiness 后继续核对真实业务、公网 Web 文件和系统有效配置。
5. 在事先固定的错误、延迟、队列阈值及观察时长内完成验收。保存本次运行身份、真实回执和独立语义结论；不以重启、HTTP 200 或脚本成功代替业务通过。

## 失败与恢复

先核对本批发布锁与当前身份，再按本批 manifest 恢复旧文件或指针、移除仅本批新增的 drop-in。恢复后重新核对 API/Worker/Web、配置和真实业务。若目标已被其他发布改变或恢复失败，停止继续切换并报告。

保护在途任务和新增写入。应用回退不等于数据库回退；不得用旧 dump 覆盖生产新数据，也不能随意撤销已应用迁移。Worker 中断依租约明确失败，不承诺恢复模型会话。记录失败、恢复结果与未验证范围，失败批次不盲重发。

## 数据与文件处置

每次删除使用本次明确授权的精确清单，不重放历史清理脚本或借用历史无备份授权。

- 核对目标 owner/provider、外键、JSON 任务引用、队列与图片；确认无活动 Chat、execution、SimC 或 lease，且不会继续产生目标业务。
- 删除前建立私有恢复材料，独立恢复到隔离环境并核对。最终事务重查清单与活动状态，按实际依赖顺序处置，保留审计、usage 和应保留记录的前后核验。
- 恢复数据时先在隔离库核对备份、清单与当前键冲突，再按明确方案恢复目标记录，不覆盖其他用户新写入。
- 到期私有副本遵循[保留与对账流程](badcase-workflow-operations.md#保留与独立处置对账)；生产数据、源码、发布 manifest 与恢复材料不因同目录存放而连带删除。

## 发布记录

操作前通过[项目状态](project-state.json)定位所需批次，再读取对应 manifest、执行器与恢复材料，核对实际生产指针。

| 日期 | 已交付内容 | 批次证据 |
| --- | --- | --- |
| 2026-09-17 | 已采样玩家跨来源身份与额度复用 | [玩家身份修复](../artifacts/verification/2026-09-17-research-player-identity/README.md) |
| 2026-09-15 | SimC 引擎与匹配目录更新，游戏构建 `12.1.0.69814` | [引擎与目录](../artifacts/verification/2026-09-15-simc-update/README.md) |
| 2026-09-14 | Chat 连续模拟不限任务次数 | [连续模拟](../artifacts/verification/2026-09-14-simc-quota/README.md) |
| 2026-09-13 | 鸡哥直接结论表达 | [回答表达](../artifacts/verification/2026-09-13-direct-conclusions/README.md) |
| 2026-09-12 | 核心规则与按需研究流程 | [研究流程](../artifacts/verification/2026-09-12-agent-skills/README.md) |
| 2026-09-11 | Web 会话返回后恢复回复状态 | [会话状态](../artifacts/verification/2026-09-11-chat-return-state/README.md) |

恢复须使用目标批次的固定 manifest，并确认当前运行身份满足执行器前置条件。引擎及绑定目录共同变更时，恢复也需共同核对；具体恢复验证范围见相应记录。

## POE2 正式运行（2026-09-21）

发布源 `77cee1603`，详细身份和验收见[发布记录](../artifacts/releases/2026-09-21-poe2/README.md)。API/Worker 共用现有正式服务，PoB 使用 `/opt/chickenbro-poe2-runtime/7d6f530c`，仅通过两个服务的 `99-poe2-20260921.conf` 增加 `POE2_*` 配置；Lua 动态库环境仅传入 PoB 子进程。

私有恢复包在 `/var/lib/chickenbro/releases/poe2-20260921`，含旧指针、精确文件清单、配置摘要及数据库备份；正式库备份已在独立库恢复并应用新增迁移。回退需先持有发布锁并确认无在途任务，再停服务、恢复清单中的旧 backend/Web 指针、移除本次两个准确命名的 drop-in、reload/start 并验证。保留新增 schema 与发布后业务数据，不用旧备份覆盖生产。未执行正式回退演练。
