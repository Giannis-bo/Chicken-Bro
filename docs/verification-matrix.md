# Project Harness Verification Matrix

本文件只定义当前验证入口和证据边界。历史阶段使用过的命令由对应 release packet 与 Git 保存，不在这里累计。

## Profiles

| Profile | 覆盖范围 | 当前自动化入口 |
| --- | --- | --- |
| `harness` | 状态、owner map、schema、release packet、diff | `node scripts/verify-project.js --profile harness` |
| `backend` | Python 后端、PostgreSQL read model、API 和 worker | `node scripts/verify-project.js --profile backend` |
| `frontend` | 旧兼容前端、Taro typed contract、架构审计、TypeScript 和 Vitest | `node scripts/verify-project.js --profile frontend` |
| `full` | Harness、后端和适合 CI 的前端自动检查；不含 UI 架构审计 | `node scripts/verify-project.js --profile full` |

`--release` 缺省时读取 `docs/project-state.json.activeReleaseArtifact`。用 `--dry-run --json` 查看确切命令，不执行。

## 选择规则

- 开发中先跑最小相关测试，不在每个小改动后串行跑 `frontend`、`backend`、`full`。
- 最终候选只跑一次 `full`；它已包含 Harness、Node、Python、Taro 类型/单元测试、JSON、语法和 diff 检查，但不包含 UI 架构审计。
- `audit:ui-architecture` 只在 UI owner、共享 chrome、路由合同或设计系统边界变化时显式运行，不作为 GitHub CI 阻断项。
- 纯文档或 owner map 变更跑 `harness`；不因此重复业务全量。
- 自动测试证明合同和代码结构，不授予视觉、生产数据或线上运行通过。

## Taro UI

UI 阶段显式验证：

```bash
npm run audit:ui-architecture
npm run typecheck
npm run test:taro
npm run verify:ui-baselines
npm run verify:ui-interactions
```

`verify:ui-baselines` 只做 target/runtime 结构预检；`verify:ui-interactions` 记录当前固定批次的真实微信核心交互，并随批次推进扩充到 14 路由。像素验收必须使用当前 target registry 对应的真实微信运行态。每个路由最终只保留一次视觉复核和一个核心交互结果。

本地微信链路保持一个 Taro watch。验证脚本默认扫描并复用 `9420-9460` 内已监听的 automation 端口，不依赖固定 `9421`，也不调用可能重载窗口的 CLI `auto`；需要连接指定会话时设置 `WECHAT_AUTOMATOR_ENDPOINT`。只有一次性建立会话时才显式设置 `WECHAT_AUTOMATOR_LAUNCH=1`，需要覆盖项目或 CLI 路径时分别设置 `WECHAT_AUTOMATOR_PROJECT`、`WECHAT_DEVTOOLS_CLI`。连接异常先检查 watch、开发者工具、项目路径和端口状态，不通过循环重启恢复。成功的结构预检必须输出设备、逐路由几何和 `failures`；没有输出不得视为通过。

## Canonical gear

装备改动至少覆盖以下分层合同：

```bash
python3 -m unittest \
  tests.gear_contracts_test \
  tests.gear_rule_matrix_test \
  tests.gear_evidence_ledger_test \
  tests.gear_resolver_test \
  tests.gear_result_envelope_test \
  tests.pg_gear_authority_loader_test \
  tests.gear_release_test \
  tests.gear_release_store_test \
  tests.gear_release_shadow_test \
  tests.gear_release_refresh_test \
  tests.community_template_import_test \
  tests.gear_stat_snapshot_test \
  tests.gear_stat_snapshot_store_test \
  tests.gear_stat_snapshot_api_test \
  tests.gear_stat_snapshot_worker_test
node --test tests/gear-workbench-state.test.js tests/frontend-api-client.test.js tests/builds-page.test.js
npx vitest run packages/domain/src/gear-intent.test.ts packages/api-client/src/transport.test.ts packages/api-client/src/websim.test.ts
```

必须核对：

- malformed intent 为 400，revision conflict 为 409，authority unavailable 为 503；结构化 problem 不得被 transport fallback 吞掉。
- 旧 `pages/` 与活动 Taro 都只提交 identifier intent，最终事实来自同一 resolver/release authority。
- community import 原子采用或 fail closed；不允许逐槽静默丢失。
- stat snapshot 只接受 signature 匹配的 verified 结果，202 有界轮询，旧响应不能覆盖新选择。
- `/api/websim/gear/stats` 只验证兼容性；活动 Taro 必须走 `/stat-snapshots`。

## Runtime evidence

涉及 backend/API、PG、同步、timer、部署或用户可见运行态时，最终候选还需记录：

- 候选 commit 与实际部署 tree/hash 一致；
- `/health`、`/api/data/health` 和受影响 API 内容 smoke；
- PostgreSQL-only、active manifest、timer/backflow、worker 与近期日志状态；
- 写入前备份和 rollback target；
- 用户可见 UI 使用真实微信环境验证，不以浏览器或截图脚本代替。

远端 smoke、迁移和生产写入不由本 profile 自动触发。

## CI

`.github/workflows/project-harness.yml` 只运行一个 `full` profile。任何测试、JSON、owner map、Harness packet、TypeScript、架构审计、语法或 whitespace 失败都必须返回非零；CI 不部署、不 SSH、不安装依赖、不迁移、不触发同步。
