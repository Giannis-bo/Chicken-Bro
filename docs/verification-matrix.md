# Chickenbro Verification Matrix

状态：当前执行权威

本文件只定义双端 Chat/SimC 重构的验证入口。验证等级相互独立：本地通过不代表 candidate，通过 candidate 不代表生产切流，生产可用也不代表真实用户已接受。

## 证据等级

| 等级 | 能证明 | 不能证明 |
| --- | --- | --- |
| `local_verified` | 当前 commit 的合同、代码、测试和构建通过 | 云端数据、真实微信、生产流量 |
| `candidate_verified` | 隔离 DB/API/Worker/Web 与回滚通过 | 已切生产、用户已接受 |
| `live_verified` | 指定生产 identity 的业务 smoke 通过 | 用户双端体验已完成 |
| `user_accepted` | 用户明确完成真实 Mini/Web 验收 | 自动替代备份、恢复或清理证据 |
| `recovery_verified` | 独立介质可恢复为可核对的隔离副本 | 当前线上业务体验 |

`skipped`、`partial`、`blocked`、dry-run、HTTP 200、systemd active、Candidate 或 SimC return code 0 都不是成功等级。

## 本地验证入口

```bash
npm run test:control
npm run test:backend
npm run test:migration
npm run test:ops
npm run test:taro
npm run typecheck
npm run lint
npm run build:weapp
npm run build:h5
git diff --check
```

本地不能安装或运行 SimulationCraft。SimC 语义结果只在云端受控 runtime 上验证。

## 阶段矩阵

| 阶段 | 当前状态 | 自动证据 | 运行态/人工门禁 |
| --- | --- | --- | --- |
| 1. 控制面 | `local_verified` | 状态、Owner Map、规则、逐文件清单、Harness | 云端清单只读且脱敏 |
| 2. 数据与 Identity | `local_verified_candidate_apply_blocked` | product schema、Identity、Origin/CSRF、迁移与 provisioning dry-run | 独立恢复、容量、隔离 PostgreSQL candidate |
| 3. Chat | `local_verified` | owner scope、SSE、幂等重放、API/client、Codex 失败语义 | Candidate Codex、同 owner 双端历史 |
| 4. SimC | `local_verified` | Snapshot、readiness、compiler、queue/lease、Worker、API/client、结果语义 | 云端 SimC 正数指标和 provenance |
| 5. 双端与切流 | `local_verified_live_acceptance_blocked` | 5 pages/2 tabs、Web 登录、白名单迁移、candidate/cutover dry-run | 真实扫码、双向 Chat/SimC、第二用户隔离、写栅栏和首条新写入 |
| 6. Legacy 退役 | `local_and_cloud_cleanup_controls_verified_apply_blocked` | caller/link graph、逐文件 SHA、本地与云端 exact-target dry-run | Phase 5 完成、零引用/连接、restore、稳定窗口、清理后再次验收 |

## Candidate 与切流

Candidate 部署前必须刷新云端只读清单并通过容量及白名单恢复门禁。部署与切流命令默认 dry-run；apply 只能使用审核过的 commit、inventory SHA 和对应恢复身份。生产切流和 legacy 退役本轮可在用户明确授权后使用 `--no-independent-backup --irreversible-no-backup-confirmation I_UNDERSTAND_NO_BACKUP_IS_IRREVERSIBLE`，该模式只免除独立备份/恢复副本，不免除迁移核对、真实双端业务验收、首条新写入、稳定健康和零引用检查。

```bash
bash server/deploy_chickenbro_candidate_lighthouse.sh --dry-run
bash server/cutover_chickenbro_lighthouse.sh --dry-run
```

真实验收至少覆盖：Mini 登录；小程序确认 Web 登录；Mini 创建 Chat 后 Web 可见并续聊；Web 创建 Chat 后 Mini 可见并续聊；任一端创建 SimC 后另一端看到同一任务、状态和结果；第二用户隔离；两端独立退出。

## 精确清理

本地清单必须绑定当前 commit 和每个文件的 SHA，且 `review=0`、`blocked=0`。实际 apply 在 Phase 5 acceptance 前必须拒绝。

```bash
node scripts/build-chickenbro-simc-refactor-inventory.js \
  --rules docs/refactor/chickenbro-simc-disposition-rules.json \
  --output docs/refactor/chickenbro-simc-refactor-inventory.json
node scripts/apply-chickenbro-simc-local-cleanup.js \
  --inventory docs/refactor/chickenbro-simc-refactor-inventory.json \
  --dry-run
```

云端退休同样默认 dry-run，并保护 `chickenbro_prod`、`chickenbro-api.service`、`chickenbro-worker.service`、当前 Web/Mini identity、Nginx/TLS 与 `/opt/wow-simc/current`。数据库删除还要求零连接、零配置引用；独立恢复验证由默认恢复模式或本轮显式无备份授权二选一。

## 最终完成

最终 evidence 必须同时包含：本地全套验证；candidate identity；白名单全量 + fenced delta 核对；生产切流和首条新写入；云端语义 SimC；本地/云端精确清理结果；隔离恢复演练；清理后真实 Mini/Web 验收；本地 `main`、`origin/main`、部署文件和 migration identity 一致；回滚窗口到期并按 manifest 退役。

任何一项缺失都不能把整体目标标为完成。相关入口：[当前架构](chickenbro-simc-architecture.md) · [生产 Runbook](chickenbro-simc-production-runbook.md) · [计划白名单](plans/README.md)
