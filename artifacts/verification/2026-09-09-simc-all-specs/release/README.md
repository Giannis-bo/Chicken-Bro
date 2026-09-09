# SimC 全专精生产发布 · 2026-09-09

用户明确授权“OK，提交，合入，发布”。已完成 `local_verified` 和 `live_verified`；未冒称独立 DB/API Candidate、真人 QQ 登录、用户手工验收或恢复演练。

## 提交与运行身份

- 实现提交：`0649a2e858f51d633380873912ef75a8c91687ea`，基于 `ee8272baf`，已提交并推送 main。发布记录的后续文档提交不改变运行源码。
- 后端：`/opt/chickenbro-releases/simc-all-0649a2e858f51d633380873912ef75a8c91687ea`。
- Web：`/var/www/chickenbro-web/releases/simc-all-0649a2e858f51d633380873912ef75a8c91687ea`。
- API 和 Worker 最后生效环境文件均为 `/etc/chickenbro-simc-all-0649a2e858f51.env`，`WOW_SIMC_SUPPORTED_SPECS=all`。各自 drop-in 为 `99-zzzz-simc-all-0649a2e858f51.conf`。
- 保留 G2 独立 Worker 工具监听端口 28794：先启动 Worker 并确认监听归属，再开启 API。未改认证、Chat、数据库 schema 或 SimC 引擎。
- 新后端在已核验旧版本基础上覆盖 5 个本轮 Python 文件与 4 个 service 模板；其余文件保持精确 SHA。846 个后端文件、13 个 Web 本地及公网 HTTPS 文件全部核对通过；见 [manifest](manifest.json)、[线上身份](live-identity.json)。

## 业务验收

[正式 HTTP smoke](public-smoke.jsonl) 使用两个新建测试账号，经正常 Cookie、Origin、CSRF 和幂等合同调用网站 API，测试结束撤销会话。测试数据保留在测试账号，未写入真实用户历史。

- 原始野德“魔魔糊胡萝卜”：`READY_FOR_SIMC`、无 missingFields/blocker；任务 `e9593517-d535-45fb-b3ba-62dd5f99d498` 经真实队列和 Worker 完成，保存有效报告，DPS `158196.03305803594`。场景为 100 次、60 秒、单目标，只用于发布验证。
- 保存结果的 snapshot、来源原始 SHA、profile SHA、compiler/runtime revision 与场景身份相互一致。
- 同一幂等键只得到同一任务；第二账号无法读取快照/任务，不能枚举其他账号历史。
- 实时恢复德 `Elunesix` 来源返回 `HEALER_SPEC_UNSUPPORTED`；提交返回合同规定的 HTTP 409 / `SNAPSHOT_NOT_READY`，数据库确认没有创建该治疗快照的模拟任务。Web 将专精错误显示为“SimC 不支持治疗专精进行模拟”，组件测试与线上构建文件身份均通过。
- 首次 smoke 已完成野德和隔离检查，但测试脚本把既有 `SNAPSHOT_NOT_READY` HTTP 状态误写为 422；实际按合同返回 409。修正测试预期后完整重跑通过，没有为测试改产品合同。首次输出保留于 `public-smoke-first.jsonl`。
- 33 个非治疗专精的有界云端正数 DPS 与解析验证见上级 [summary](../summary.json)。治疗 7 专精由分类/编译拒绝测试覆盖，不运行治疗模拟。增辉与坦克的模型局限仍显示在产品中。

## 本地验证

隔离 worktree 中基于最新 main 集成：482 个后端、286 个前端、62 个控制面测试通过；typecheck、lint、H5 构建通过。日志为本目录 `integrated-*.log`。H5 有两条既有包体积警告。本轮不修改持久化 schema 或 QQ 登录，未重跑迁移专项/真人 QQ 登录。

## 回滚边界

切换前 chat/simc/ops 活跃任务均为 0；持数据库写入围栏停止 API/Worker后切换，见 [切换记录](promote.jsonl)。旧配置和下列版本保留，没有删除业务数据、旧发布或引擎。

- 旧后端：`/opt/chickenbro-releases/g2-08404a091a6dc9a08bcf65a759b47763c2942711`。
- 旧 Web：`/var/www/chickenbro-web/releases/first-chat-cb0395f302aed134675c277dce7d5e8ddbc5123a`。
- 已准备 `deploy.py <manifest> rollback`，要求当前指针仍匹配本次版本且无活动任务，恢复两个旧指针、移除本次两个 drop-in，再按 Worker/API 顺序启动；旧环境文件重新生效。当前线上业务已通过，未执行生产回滚，也未声称 recovery_verified。

工作区其他任务的 Mini 退役、云端 Codex 清理及未跟踪证据均保留，不纳入本次发布。
