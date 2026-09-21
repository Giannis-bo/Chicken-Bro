# POE2 Task 3 独立评审

结论：**需要修复**。本轮静态读取 Task 3 application/repository/worker/gateway/API/迁移、启动集成与相关测试。未执行本地代码、测试或构建；以下发现可由控制流和 SQL 直接确认。

## Chat 前置修复复核

截至本轮最终读取，两个修复均未落到当前工作树：

- `server/app/chickenbro/codex_adapter.py:200-206` 的 MCP `env_vars` 仍缺少 `CHICKENBRO_GAME`；此前 P1 仍成立。
- `server/chickenbro_native_mcp.py:343-349` 仍使用 `<PathOfBuilding` 子串判断，未严格校验 `PathOfBuilding2` 根节点。Task 3 的 `engine.decode_build()` 已有严格根节点校验，能够阻止 PoE1 实际导入，但 Chat 边界修复尚未完成。

## Blockers

### [P1] POE2 Chat 导入/读取需适配现有网关大小边界

- 位置：`server/app/chickenbro/worker_gateway.py:148-156`；`server/app/poe2/tools.py:49-52`。
- 新增 POE2 route 沿用 `Content-Length <= 32768`。POE2 工具与引擎允许最高 2 MB 的 source；大于 32 KiB 的合法 XML/分享码经 durable Chat 导入时，会在进入 application 前直接返回 422。
- 同时 import/get 无条件 `include_source=True`。压缩分享码可以小于 32 KiB，但解压 XML 超过 `ToolRecorder` 的 180000 字节结果限额后，成功导入响应会被整包换成 partial，连新 buildId 都丢失（同文件第 68–70 行）；get 也无法读取该构筑信息。
- 修复：为 POE2 请求设置与 source 契约及 JSON 编码一致的有界限额；Chat import/get 返回有界摘要、ID 与 provenance，避免无条件回传完整 XML。云端覆盖超过 32 KiB 的合法导入，以及压缩后较小但展开后超过 180 KB 的构筑。

### [P2] 第三次租约过期后任务永久停留 running

- 位置：`server/app/poe2/repository.py:116-123`。
- `claim_next()` 仅选择 `attempt_count < 3`，每次 claim 又递增计数。当第三次执行进程退出或失去租约，任务成为 `running/attempt_count=3`；以后所有 claim 都忽略它，且没有 recovery/sweeper 把它转为 failed。`_finish()` 又拒绝过期租约，因此该任务无法再到终态，客户端持续显示运行中。
- 修复：原子终结达到重试上限且租约过期的任务，写入稳定的公开失败码并清空租约。云端 PostgreSQL 回归应覆盖三次 claim/expiry 后的终态及幂等重放。

### [P2] fencing 使用可复用 worker 名称，不能区分同名执行实例

- 位置：`server/app/poe2/repository.py:139-142`；启动来源 `server/app/worker/main.py:215`。
- 完成写入只比较 `lease_owner=worker_id` 和当前到期时间；生产构造又固定为 `'poe2-'+args.worker_id`。两个同配置 worker 实例重叠运行时，旧实例租约到期、同名新实例 reclaim 后，旧实例调用 complete 仍匹配新的有效租约，能够覆盖新执行的结果。现有测试只用不同名称 worker-a/worker-b，覆盖不到此情形。
- 修复：每次 claim 分配不可复用 token/epoch，complete/fail 必须携带并匹配本次 token；或至少使用每进程唯一身份并明确保证实例不复用，但每 claim fencing 更完整。云端补同名 reclaim 后旧 claim completion 被拒绝用例。

## 其余检查与证据边界

- 账号来自 Principal；build/job 读写、列表、submit 的 INSERT SELECT 均带 owner 条件。任务幂等由 `(user_id,idempotency_key)` 唯一约束和请求 hash 比较在事务内实现，未发现跨账号读取路径。
- API 写入使用既有 Origin/CSRF 依赖；durable Chat 的 POE2 application 使用受 Chat lease 保护的 connection，tool recorder 同样受该 connection 限制。POE2 token 只由受信 game context 签发，固定 loopback 路由区分 gateway kind。
- 常驻 worker 启动了 POE2 lane；`--once` 仍仅执行原 SimC 队列，因此 Candidate 验证应使用常驻 lane 或显式 `Poe2Worker.run_once()`。当前 45 秒引擎 timeout/60 秒 lease 的时间余量不构成独立必改问题，但真实任务耗时需要验证。
- 实现报告已有真实 PostgreSQL owner/idempotency/不同 worker fencing 测试；真实 PoB + 持久化 worker smoke 首次失败，尚无成功证据。修复后需在云端复跑上述定向用例，并跑实际 worker import → queue → succeeded → read/export，绑定引擎与源代码身份后才能交付 Candidate 验收。
