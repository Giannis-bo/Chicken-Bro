# Project Harness Verification Matrix

状态：当前执行权威

本文件只定义炸鸡队长 + SimC 双端重构的当前验证入口和证据边界。历史命令保存在 Git 与对应 release packet，不再拥有新实现权。

## Harness Profiles

| Profile | 覆盖范围 | 自动化入口 |
| --- | --- | --- |
| `harness` | 当前状态、owner map、schema、release packet、diff | `node scripts/verify-project.js --profile harness --release <task-release>` |
| `backend` | Python 应用、PostgreSQL、API、Worker | `node scripts/verify-project.js --profile backend --release <task-release>` |
| `frontend` | Taro/typed client、TypeScript、Vitest、H5/WeApp 机械检查 | `node scripts/verify-project.js --profile frontend --release <task-release>` |
| `full` | Harness + backend + frontend 的 CI 自动检查 | `node scripts/verify-project.js --profile full --release <task-release>` |

本地可以显式传 `--release`。PR CI 必须使用 `--release-from-changes --base origin/main` 从 diff 解析唯一完整任务 packet，不读取本地默认值。用 `--dry-run --json` 查看命令而不执行。

## 证据等级

| 等级 | 能证明什么 | 不能证明什么 |
| --- | --- | --- |
| `local_verified` | 代码/合同在当前 commit 通过本地定向测试 | 数据库已迁移、云端已部署、真实微信可用 |
| `candidate_verified` | 隔离 candidate 的代码、DB、API/Worker 和回滚通过 | 公网生产已切流、真实用户已接受 |
| `live_verified` | 指定生产 identity 的实际业务路径通过 | 用户已完成双端主观/行为验收 |
| `user_accepted` | 用户明确确认真实 Mini/Web 路径 | 自动替代恢复、隔离、备份或清理证据 |

`skipped`、`partial`、`blocked`、HTTP 200、systemd active、SimC return code 0、Candidate 或 preview 都不是成功等级。

## 六阶段矩阵

| Phase | 当前状态 | 自动验证 | 运行态/人工门禁 | 回滚/停止边界 |
| --- | --- | --- | --- | --- |
| 1. 控制面 | 已完成 / `local_verified` | inventory、云端脱敏、project-state、Harness packet | 云端只读快照 | 未改业务运行时/数据 |
| 2. Identity/数据面 | `local_verified`；candidate apply 容量/恢复 blocked | product schema、identity repo/app/API、Origin/CSRF、provision dry-run | FastAPI/真实 PG、独立备份、恢复、candidate DB | 不切正式 DSN；blocked 不算 Phase 完成 |
| 3. Chat | 等待 Phase 2 | owner/repo/app/SSE/API/typed client、第二用户隔离 | candidate Codex 与双端同 owner | 不接公网生产流量 |
| 4. SimC | 等待 Phase 3 | snapshot/readiness/compiler/repo/queue/worker/API/client | cloud SimC 语义结果、candidate task parity | 不切公网生产流量 |
| 5. 双端/迁移/切流 | 等待 2--4 | 精确 5 routes/2 tabs、Web Shell、migration/reconciliation、deploy/cutover dry-run | 真实扫码、跨端 Chat/SimC、写栅栏 | 首条新写入前/后采用不同回滚规则 |
| 6. Legacy 退役 | 等待稳定窗口 | caller/link graph、cleanup manifest、dry-run、最终精简 full | 零引用/连接/open handle、恢复验证、用户接受 | 精确删除；禁止宽泛递归 |

## Phase 1：控制面

当前可执行命令：

```bash
node --test tests/chickenbro-simc-refactor-inventory.test.js
python3 -m unittest tests.chickenbro_simc_cloud_inventory_test -v
node --test tests/project-state.test.js
node scripts/project-harness.js --check-requirement \
  --requirement-file artifacts/releases/2026-09-02-chickenbro-simc-control-plane/requirement.json
git diff --check
```

验收：本地 inventory 绑定完整 commit 和逐文件 SHA，`unresolvedCount=0`；云端快照 secret-safe 且有真实 `observedAt`；capacity gate 如实反映阻塞；architecture/runbook/owner map/verification matrix 指向同一目标。

## Phase 2：Identity 与干净数据面

目标自动验证：

```bash
python3 -m unittest \
  tests.product_schema_test \
  tests.app_identity_application_test \
  tests.app_identity_repository_test \
  tests.app_identity_api_test \
  tests.app_csrf_test -v
node --test tests/provision-chickenbro-database.test.js
node scripts/verify-project.js --profile backend \
  --release artifacts/releases/2026-09-02-chickenbro-simc-identity-data
```

上述新测试/packet 在对应阶段落地前缺失应当失败，不能记为 skipped pass。PostgreSQL 集成测试必须运行在隔离 candidate，不能用 mock-only 代替 schema/privilege/owner 证明。

必须覆盖：

- Mini Bearer 与 Web Cookie 独立签发、过期、撤销；
- 同一微信 identity 映射一个内部 `user_id`；
- 多 transport、错 transport、错 verifier、过期、取消、重复消费 fail-closed；
- Cookie 写请求 Origin/Host/CSRF；Mini 请求不携带 Cookie；
- auth audit 不含 token/Cookie/OpenID/session_key/verifier/ticket/secret；
- `chickenbro_prod` 只有允许 schema/table，runtime role 最小权限；
- capacity、独立设备、备份和恢复仍 blocked 时 provisioning 不 apply。

## Phase 3：正式 Chat

目标自动验证：

```bash
python3 -m unittest \
  tests.app_chat_repository_test \
  tests.app_chat_application_test \
  tests.app_chat_api_test \
  tests.app_chat_cross_client_test -v
npm run test:taro -- \
  packages/domain/src/chat.test.ts \
  packages/api-client/src/chat.test.ts
```

必须覆盖 owner-scoped list/get/create、第二用户 404、稳定游标、`Idempotency-Key`、`clientMessageId`、严格 SSE sequence、断线持久化回放、assistant 先持久化后 success，以及 Codex unavailable/timeout/invalid output 的真实失败。任何普通 LLM 或模板 fallback 都失败。

Candidate 证据需绑定 Mini/Web 两种 session 的同 owner 证明、候选 DB/commit/API identity、Codex configured/unavailable 路径和回滚；不切公网生产。

## Phase 4：正式 SimC

目标自动验证：

```bash
python3 -m unittest \
  tests.app_simc_source_adapter_test \
  tests.app_simc_readiness_test \
  tests.app_simc_compiler_test \
  tests.app_simc_repository_test \
  tests.app_simc_worker_test \
  tests.app_simc_api_test \
  tests.app_simc_cross_client_test -v
npm run test:taro -- \
  packages/domain/src/simc.test.ts \
  packages/api-client/src/simc.test.ts
```

必须覆盖来源 URL allowlist、角色不存在/权限受限/来源不可用/缺字段的不同 blocker、不可变 snapshot revision、compiler/runtime pin、idempotent job、lease/retry/cancel/lost lease、第二用户隔离、跨端相同 job ID、有效正数 DPS/HPS、profile hash 和 provenance。return code 0 而无有效指标必须失败。

只使用云端已安装 SimulationCraft。不得在本地安装或运行 SimC；Candidate smoke 记录 binary/runtime revision 与实际结果语义。

## Phase 5：双端、迁移与切流

目标前端自动验证：

```bash
npm run test:taro -- \
  apps/mini-taro/src/features \
  apps/mini-taro/src/pages/chickenbro \
  apps/mini-taro/src/pages/simc \
  apps/mini-taro/src/web \
  apps/mini-taro/src/tab-bar-items.test.ts \
  apps/mini-taro/src/tab-bar-state.test.ts
npm run typecheck
npm run lint
npm --workspace @wow-mini/mini-taro run build:h5
npm --workspace @wow-mini/mini-taro run build:weapp
```

必须断言目标路由精确为：

```text
pages/chickenbro/index
pages/simc/index
pages/simc/tasks
pages/simc/task-detail
pages/auth/web-login-confirm
```

Tab 精确为 `队长 | SimC`；Web 只有正式登录、队长、SimC、账号和退出；源码/构建不得含 prototype bypass、news、builds、gear、talent、profile 一级入口。

迁移自动验证：

```bash
python3 -m unittest tests.legacy_product_migration_test -v
node --test tests/deploy-chickenbro-candidate.test.js tests/cutover-chickenbro.test.js
```

核对必须分别证明 Identity、Chat、SimC、Ops 的 candidate/accepted/rejected 数量、owner、外键、顺序、终态、内容 hash 和 idempotent mapping；只比总行数失败。

人工/运行态必须完成：真实 Mini 登录；真实小程序确认 Web 登录；Mini 创建 Chat、Web 可见并续聊；Web 创建 Chat、Mini 可见并续聊；任一端创建 SimC job，另一端看到相同 ID/状态/result；第二用户隔离；两端独立退出。用户明确确认前状态只能是 `user_acceptance_pending`。

## Phase 6：Legacy 退役

目标自动验证：

```bash
node --test tests/chickenbro-simc-caller-graph.test.js
node scripts/build-chickenbro-simc-caller-graph.js \
  --inventory docs/refactor/chickenbro-simc-refactor-inventory.json \
  --output docs/refactor/chickenbro-simc-caller-graph.json
node --test tests/chickenbro-simc-cleanup.test.js
bash server/cleanup_chickenbro_legacy_lighthouse.sh \
  --manifest docs/refactor/chickenbro-simc-cloud-cleanup-manifest.json \
  --dry-run
```

删除前要求：调用图/文档链接图零保留引用、manifest SHA 匹配、零连接/open handle、无 systemd/Nginx/env 引用、独立 restore identity、回滚窗口状态和用户 acceptance。每次删除只接受精确文件/目录/数据库/unit 名称。

## 最终 Full Profile

最终完成证据至少包含：

1. Python：所有 `server/app` 正式 Identity/Chat/SimC/Worker、migration/reconciliation、provision/deploy/cleanup 合同测试。
2. Node/Taro：domain/API client、Mini/Web feature、精确 route/tab、no-prototype 和 owner map/Harness 测试。
3. 构建：production H5 与 WeApp，记录 commit、环境边界和产物 hash；没有依赖安装/download 隐式发生。
4. Candidate：隔离 DB/API/Worker/Nginx、真实微信登录、Codex、云端 SimC、第二用户隔离和回滚。
5. Migration：全量 + fenced delta 的逐域 accepted/rejected/hash reconciliation。
6. Cutover：唯一写入口、`firstNewProductionWriteAt`、post-write 回滚限制和生产 smoke。
7. Cleanup：本地/云端精确 manifest 执行后 inventory、零旧 route/service/timer/database/directory。
8. Parity：本地 `main`、`origin/main`、云端 deployable set、migration identity 和运行时 identity 分别一致。
9. Recovery：独立备份与实际恢复演练。
10. User acceptance：真实 Mini/Web 双向 Chat 与 SimC 明确通过。

任何一项缺失都不能把 Goal 标为 complete。

## 选择规则

- 开发中只跑最小相关测试；每个阶段封包前跑一次适用 Harness profile。
- 纯文档/owner map 跑 Phase 1 focused + `harness`，不冒充 backend/frontend/live 验证。
- 旧 14-route、gear/talent/WebSim 测试在 legacy 仍承担回滚时可以作为回归基线，但不再是目标产品验收。
- 自动化不触发 SSH 写入、数据库迁移、服务重启、正式切流或删除；这些操作由对应 runbook/apply gate 驱动。
- 证据中的 secret 只记录 configured/missing、permission、length 或 hash identity，不记录值。

## CI

`.github/workflows/project-harness.yml` 继续运行一个 `full` profile，并从 PR diff 绑定唯一任务 release packet。任何 packet 选择/交叉绑定、clean verification HEAD、测试、JSON、owner map、TypeScript、语法或 whitespace 失败都必须返回非零。CI 不部署、不 SSH、不迁移、不触发同步、不删除。

相关入口：[当前架构](chickenbro-simc-architecture.md) · [生产 Runbook](chickenbro-simc-production-runbook.md) · [计划白名单](plans/README.md)
