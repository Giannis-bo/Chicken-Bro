# POE2 构筑与任务 API 实施报告

## 结果

- 新增 owner-scoped 不可变构筑、异步计算任务、原子幂等、租约 fencing、任务历史、对比、导出和 Craft of Exile 文本导入链接。
- 新增 `/api/v2/poe2` builds/jobs/compare/export/crafting API；读请求使用现有 Principal，写请求使用现有 Web Origin + CSRF 认证依赖。
- 新增仅允许 `game=poe2` 的 Chat capability gateway，并接入 API 进程和 durable Chat worker 的 loopback tool server。
- POE2 使用独立 `poe2.jobs` claim/lease。现有 `ops.job_queue` claim 不按 domain 过滤，直接复用会让 SimC worker 抢走 POE2 任务。
- 首版 POE2 worker 单线程；每次调用 `PobEngine.calculate(source, changes)`，不共享构筑可变状态。

## 数据与接口约束

- `poe2.builds` 保存 owner、title、规范 XML、game version、league、输入 SHA、引擎版本、原始导出码和摘要；导入后不可修改。
- `poe2.jobs` 的 `(user_id, idempotency_key)` 唯一。事务内同时比较 `buildId + changes` 请求哈希：相同请求返回原任务，不同请求返回 `409 POE2_IDEMPOTENCY_CONFLICT`。
- 构筑、任务读取和列表均带 `user_id` 条件；其他账号得到 404，不泄露资源存在性。
- claim 使用 `FOR UPDATE SKIP LOCKED`；完成/失败必须匹配仍有效的 `lease_owner` 和 `lease_expires_at`，过期 worker 无法落结果。
- changes 最终由 engine `validate_changes` 约束。当前 application/API 不复制字段白名单，可随 Task 1 的 `skillGroups` 安全规范同步生效。

## 云端验证

环境：`wow-lighthouse:/opt/chickenbro-candidates/poe2-20260918/jobs-tests/source`；数据库：独立 `chickenbro_poe2_jobs_test`；Python：`/opt/chickenbro-runtime/bin/python`。未运行本地测试、构建或运行时。

- 迁移：0001–0012 对空数据库依次应用成功。
- TDD red：临时反转 repository 的请求哈希冲突判断后，同 key 同 payload replay 用例失败；随后恢复源码。
- Green：`tests.app_poe2_jobs_unit_test` + `tests.app_poe2_jobs_postgres_test`，4/4 通过，0.980s。
- 回归：POE2 application/engine/chat isolation/jobs、Codex adapter、通用 API 与身份/CSRF，95/95 通过，3.388s。
- 静态导入：`compileall` 覆盖 POE2、API route、main、Chat worker gateway、worker main，通过。
- 真实 PostgreSQL 覆盖两个 owner、相同请求 replay、冲突请求、owner-hidden 404、buildId 历史过滤、单 claim、租约过期 reclaim 和旧 worker completion fencing。
- 真实持久化 worker smoke：固定引擎 `v0.23.1@7d6f530cbdab20389ff8bc6ba97a37ac27f74e41`，使用上游 `build-1.xml` 依次完成真实导入计算、入队、独立 worker claim、第二次真实计算、结果持久化和 owner 读取；1/1 通过，6.376s。结果的 `inputSha256` 与不可变构筑一致，Life/EnergyShield 为正，引擎身份与环境一致。该 fixture 是上游验证样本，不代表用户构筑验收。
- 评审 blocker 修复回归：74/74 通过，0.824s。第三次过期租约会原子转为 `failed / POE2_ATTEMPTS_EXHAUSTED`；生产 POE2 worker 使用进程唯一 identity，避免同名重启绕过 fencing。
- POE2 Chat import 接收上限为 4.1MB JSON envelope，native client 使用 UTF-8 JSON，覆盖 2MB source 及转义开销；import/get 工具只返回构筑摘要。大于 170KB 的 Chat export 返回包含 buildId、实际大小和 `POE2_EXPORT_TOO_LARGE` 的明确阻断包，完整分享码继续由 owner-authenticated HTTP export 按需读取，避免 recorder/native MCP 静默丢包。
- 部署权限复验：0012 明确授权 `wow_app` 使用 `poe2` schema、对 builds 执行 SELECT/INSERT、对 jobs 执行 SELECT/INSERT/UPDATE。云端连接后 `SET ROLE wow_app` 运行 PostgreSQL owner/idempotency/lease 测试 3/3 通过，0.338s；相同实际角色运行真实 PoB 持久化 worker smoke 1/1 通过，6.169s。超级用户仅用于测试 owner fixture 的创建与清理。

## 未闭合证据与评审关注

- Worker 计算上限 45 秒，租约 60 秒；当前余量有限。后续可增加 POE2 lease heartbeat，或把租约固定提高到覆盖进程清理时间。
- `import_build` 会先执行一次真实计算以持久化摘要/原始 export/provenance；这是有意的同步成本，API Candidate 应验证请求超时配置。
- 本报告之后按计划执行独立 diff 评审；Critical/Important 问题需修复并重新运行相应云端测试。
