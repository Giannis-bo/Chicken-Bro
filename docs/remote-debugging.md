# 远程调试与部署 Runbook

本文记录已知云服务器的稳定入口、路径、部署和 smoke。不要在仓库、命令输出、日志或截图中记录私钥、密码、token、API secret、`CODEX_ACCESS_TOKEN` 或 `~/.codex/auth.json`。

## 服务器入口

- SSH alias：`wow-lighthouse`
- SSH user/host：`ubuntu@124.223.51.33`
- Public base URL：`http://124.223.51.33`
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
curl -fsS http://124.223.51.33/health
curl -fsS http://124.223.51.33/api/data/health
curl -fsS http://124.223.51.33/api/news/home
curl -fsS http://124.223.51.33/api/websim/bootstrap
curl -fsS 'http://124.223.51.33/api/websim/talents?class=mage&spec=frost'
curl -fsS 'http://124.223.51.33/api/websim/gear?class=mage&spec=frost&compact=1'
```

HTTP 200 只证明请求可达；还要检查 `status`、`blockers`、`checkedAt`、来源和关键 payload 字段。

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

部署脚本不得上传本地 `server/data`。部署后检查 service、nginx、journal、health、核心 API 和实际改动对应的业务流。

## 同步与 Timer

当前系统使用的任务包括：

- `wow-websim-sync.timer`
- `wow-stat-weights-sync.timer`
- `wow-community-template-sync.timer`
- `wow-season-recommended-gear-sync.timer`
- `wow-data-health-followup.timer`

`wow-data-health-followup` 可以根据 `/api/data/health` 续跑仓库已配置的安全任务。SimC runtime 只有在配置源不变且 health 报告 `updateAvailable=true` 时，才由既有 service 构建并原子切换 `/opt/wow-simc/current`；修改 repo/branch 或引入其他下载源不在该权限内。

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

Public base URL 当前是 HTTP。任何带 Bearer/admin token 的浏览器请求都不得发送到明文 HTTP；管理入口应在 HTTPS、访问控制和 token 轮换完成后使用。Token 只能保存在服务端环境或受信任的本地安全存储中。
