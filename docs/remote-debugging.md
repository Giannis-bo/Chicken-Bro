# 远程调试与部署 Runbook

本文记录已知云服务器的稳定入口、路径、部署和 smoke。不要在仓库、命令输出、日志或截图中记录私钥、密码、token、API secret、`CODEX_ACCESS_TOKEN` 或 `~/.codex/auth.json`。

## 服务器入口

- SSH alias：`wow-lighthouse`
- SSH user/host：`ubuntu@124.223.51.33`
- Public base URL：`https://api.chickenbro.cloud`
- Direct IP diagnostic：`http://124.223.51.33`，仅限无凭据开发/故障探测
- Project：`/opt/wow-mini-program`
- Backend service：`wow-backend`
- Environment：`/etc/wow-backend.env`
- PostgreSQL：`127.0.0.1:5432`
- SimC runtime：`/opt/wow-simc/current/simc`

优先使用已配置的 alias：

```bash
ssh wow-lighthouse
```

新机器首次连接前，在云厂商控制台核对 host key，再写入 `known_hosts`。不要关闭 `StrictHostKeyChecking`。

## Runtime 边界

- 服务环境必须使用 `WOW_DATABASE_RUNTIME=postgres_only`。
- SQLite 文件只可作为显式离线迁移源或备份，不得设置为线上 fallback。
- 密钥和 DSN 只保存在服务环境或 `PGPASSFILE`，检查时必须脱敏。
- Routine SSH、备份、迁移、同步、服务重启和 smoke 遵循 `AGENTS.md` 的云端授权规则。
- 本地下载、任意第三方下载、依赖安装、repo/branch 修改仍遵循网络审批规则。

## 部署身份与目录卫生

生产代码身份必须由“不可变 Git identity + deployable tracked set 的逐文件 hash + 任一 runtime override
的路径/hash/验证状态”共同描述。若目录中存在 `.deploy-revision`，它也只能作为辅助标记；当前部署
脚本不创建该文件，历史 marker 可能滞后，不能单独证明 `/opt/wow-mini-program` 等于某个 Git commit。
热部署或 tar overlay 也不会自动删除 Git 中已移除的文件，因此“新文件 hash 匹配”与“旧残留已清除”
是两项独立检查。

每次核对或清理至少执行以下边界：

1. 本地先记录 `git status --short --branch`、HEAD、`origin/main` 和本次允许部署的 dirty file；不得覆盖无关 WIP。
2. 云端分别核对 tracked 文件 hash、`.deploy-revision`、systemd 实际 `ExecStart`、运行中 open handle 和 `/api/data/health`；mixed tree 必须明确标为 `待收口`。
3. 用当前 Git tracked set 计算候选残留，并显式保留 `artifacts/`、`backups/`、`.codex-backups/`、`logs/` 与 `server/data/`。`.deploy-revision` 必须单独核对 consumer 和真实性；只有确认无 consumer 且值失真时才按精确清单删除。未知 secret、PG 数据、正式 evidence、Exact-first foundation 和仍承担回滚职责的版本不得按“untracked”删除。
4. 删除只能针对已审阅的精确文件/目录清单；先记录 path、bytes、mtime、reason，再核对没有 systemd 引用或 open handle。不要对宽泛根目录使用递归删除。
5. 清理后重新计算残留差集，并复核磁盘、service、failed units、loopback/public health、核心 API 与 Active/Candidate/rollback SimC 指针。

当前部署快照只记录在 `docs/project-state.json` 的 `runtimeBaseline.cloudDeployment`，避免本 runbook
复制易过期的 SHA、磁盘数和健康计数。目录清理完成不代表代码已发布、测试已同步、Manifest 已切换
或业务健康已转绿。

## 常用检查

```bash
ssh wow-lighthouse
cd /opt/wow-mini-program
curl -fsS http://127.0.0.1:8787/health
sudo systemctl status wow-backend --no-pager
sudo journalctl -u wow-backend -n 120 --no-pager
```

脱敏检查环境：

```bash
sudo awk -F= '/^WOW_DATABASE_RUNTIME=|^WOW_DATABASE_URL=|^WOW_CHICKENBRO_CODEX_ENABLED=/{print $1"="($1=="WOW_DATABASE_URL" ? "<redacted>" : $2)}' /etc/wow-backend.env
```

Public smoke：

```bash
curl -fsS https://api.chickenbro.cloud/health
curl -fsS https://api.chickenbro.cloud/api/data/health
curl -fsS https://api.chickenbro.cloud/api/news/home
curl -fsS https://api.chickenbro.cloud/api/websim/bootstrap
curl -fsS 'https://api.chickenbro.cloud/api/websim/talents?class=mage&spec=frost'
curl -fsS 'https://api.chickenbro.cloud/api/websim/gear?class=mage&spec=frost&compact=1'
```

HTTP 200 只证明请求可达；还要检查 `status`、`blockers`、`checkedAt`、来源和关键 payload 字段。直接 IP 的 HTTP 探针不得携带 Bearer/admin token。

## 部署

完整入口：

```bash
./server/deploy_lighthouse.sh
```

复用远端依赖的热部署：

```bash
WOW_DEPLOY_SKIP_BOOTSTRAP=1 ./server/deploy_lighthouse.sh
```

部署前：

1. 核对 diff 和本次文件范围。
2. 运行对应本地测试与 `git diff --check`。
3. 如涉及 schema、数据写入或同步，备份实际 PostgreSQL target。
4. 备份将修改的 service environment。
5. 说明是否启动异步同步任务。

部署脚本必须保留 Git 已跟踪的 `server/data` 静态控制合同，同时排除 runtime SQLite、
`apps/mini-taro/dist`、`apps/mini-taro/.swc`、任意 `project.private.config.json` 和其他本地开发产物。
部署后检查 service、nginx、journal、health、核心 API、deployable tracked set hash 以及实际改动对应的业务流。

## 同步与 Timer

当前系统使用的任务包括：

- `wow-websim-sync.timer`
- `wow-stat-weights-sync.timer`
- `wow-community-template-sync.timer`
- `wow-season-recommended-gear-sync.timer`
- `wow-data-health-followup.timer`

`wow-data-health-followup` 可以根据 `/api/data/health` 续跑仓库已配置的安全任务。当 health 绑定正式
Active Manifest 时，发现 `updateAvailable=true` 只能记录
`simc_runtime_update:active_manifest_cutover_required`，不得由 follow-up 自动切换 SimC；候选构建与
Active cutover 必须继续遵守 Manifest runtime identity 和 release gate。若 `active_manifest` 状态缺失
或无法判定，同样以 `active_manifest_state_unavailable` fail closed，不生成自动更新 action。修改
repo/branch 或引入其他
下载源不在既有权限内。

同步完成后检查：

```bash
sudo systemctl list-timers --all --no-pager | rg 'wow-'
sudo systemctl --failed --no-pager
sudo journalctl -u wow-websim-sync -u wow-stat-weights-sync -u wow-community-template-sync -n 120 --no-pager
```

不要仅凭 service `success` 提升数据状态；以 PostgreSQL read model 和 `/api/data/health` 为准。

## 数据与 Schema 变更

按 [PostgreSQL Runtime and Migration Runbook](postgres-identity-migration-runbook.md) 执行。最少要求：

- exact target；
- PostgreSQL backup；
- migration/dry-run output；
- count、owner 和 foreign-key verification；
- service restart；
- owner flow、health 与业务 API smoke；
- rollback path。

SQLite 备份只能用于重新迁移或离线审计，不能恢复为 runtime fallback。

## 回滚

### 代码部署失败

回退代码或重新部署上一版，保持可信 DB 不变；重启服务并复核 health 与核心 API。

### Schema 或数据污染

停止相关写任务，保留异常状态供审计，恢复部署前 PostgreSQL 备份和环境，再运行完整 smoke。

### 环境错误

恢复部署前环境文件，确认 DSN 脱敏且仍是 PostgreSQL-only，重启并检查 journal。

## 安全风险

Public base URL 当前使用 `https://api.chickenbro.cloud`，其微信 request/downloadFile 域名批准与发布状态以 `docs/project-state.json` 为准。直接 IP 仍是明文 HTTP 诊断入口，任何 Bearer/admin token 都不得发送到该地址；管理入口还必须具备访问控制和 token 轮换。Token 只能保存在服务端环境或受信任的本地安全存储中。
