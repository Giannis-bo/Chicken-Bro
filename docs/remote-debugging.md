# 远程调试登录记录

本文记录 WOW 小程序后端轻量云的远程调试入口。不要在本文或仓库中记录私钥、密码、API key、`CODEX_ACCESS_TOKEN`、`~/.codex/auth.json` 等敏感内容。

## 目标服务器

- 云厂商：腾讯轻量云
- SSH：`ubuntu@124.223.51.33`
- HTTP：`http://124.223.51.33`
- 后端健康检查：`curl -fsS http://124.223.51.33/health`
- 当前已知 host key：`ED25519 SHA256:qKAZEsRSoaAWDhWj1OSGogjMKRzYLy/vPWirfagkdXs`

仓库记录显示 `root` 登录不稳定或不可用，稳定路径使用 `ubuntu` 用户。

## 登录方式

当前机器已配置 SSH alias，后续远程调试优先使用：

```bash
ssh wow-lighthouse
```

等价的显式 SSH key 登录方式：

```bash
ssh -o StrictHostKeyChecking=yes -i ~/.ssh/wow_lighthouse_ed25519 ubuntu@124.223.51.33
```

本机 SSH 配置位于 `~/.ssh/config`：

```sshconfig
Host wow-lighthouse 124.223.51.33
    HostName 124.223.51.33
    User ubuntu
    IdentityFile ~/.ssh/wow_lighthouse_ed25519
    IdentitiesOnly yes
    StrictHostKeyChecking yes
```

首次在一台新机器上连接前，先确认 `known_hosts` 已存在记录：

```bash
ssh-keygen -F 124.223.51.33 -l
```

如果没有记录，可以在确认服务商控制台指纹后添加 host key，再连接。部署脚本默认要求 `StrictHostKeyChecking=yes`，因此不要依赖交互式首次信任。

部署脚本支持通过环境变量指定认证材料：

```bash
WOW_LIGHTHOUSE_KEY=/path/to/private_key ./server/deploy_lighthouse.sh
```

密码登录只作为临时兜底。交互调试可直接运行 `ssh ubuntu@124.223.51.33` 后输入密码；部署脚本的密码模式需要本机安装 `sshpass` 并设置 `WOW_LIGHTHOUSE_PASSWORD`，不要把该变量写入仓库。

## 远程路径

- 项目目录：`/opt/wow-mini-program`
- systemd service：`wow-backend`
- 生产环境变量：`/etc/wow-backend.env`
- Codex home：`/home/ubuntu/.codex`
- Codex job 目录：`/var/lib/wow-backend/codex-jobs`
- 历史 SQLite 数据目录：`/opt/wow-mini-program/server/data`，只作为迁移源、离线审计和回滚备份，不作为线上 runtime。
- PostgreSQL：本机 `127.0.0.1:5432`，PG-only runtime 使用 `WOW_DATABASE_RUNTIME=postgres_only` 和 `/etc/wow-backend.env` 中的 `WOW_DATABASE_URL`；不得在 systemd 环境设置 `WOW_SQLITE_MIGRATION_SOURCE`。

## 常用调试命令

```bash
ssh wow-lighthouse
cd /opt/wow-mini-program
curl -fsS http://127.0.0.1:8787/health
sudo systemctl status wow-backend --no-pager
sudo journalctl -u wow-backend -n 120 --no-pager
sudo systemctl restart wow-backend
sudo awk -F= '/^WOW_DATABASE_RUNTIME=|^WOW_DATABASE_URL=|^WOW_CHICKENBRO_CODEX_ENABLED=/{print $1"="($1=="WOW_DATABASE_URL" ? "<redacted>" : $2)}' /etc/wow-backend.env
sudo awk -F= '/^WOW_WARCRAFTLOGS_CLIENT_ID=|^WOW_WARCRAFTLOGS_CLIENT_SECRET=/{print $1"="($1 ~ /SECRET/ ? "<redacted>" : "<configured>")}' /etc/wow-backend.env
```

本地验证远程 API：

```bash
curl -fsS http://124.223.51.33/health
curl -fsS http://124.223.51.33/api/game/season
curl -fsS http://124.223.51.33/api/data/health
python3 server/simulator_e2e_smoke.py --base-url http://124.223.51.33 --timeout 90
```

热部署优先复用远程已有依赖：

账号表、schema 或 PG-only cutover 变更上线前，先备份历史 SQLite 文件和当前 PostgreSQL target。SQLite 备份只用于回滚或一次性迁移，不允许恢复成 runtime fallback：

```bash
ssh wow-lighthouse 'sudo install -d -m 700 -o ubuntu -g ubuntu /opt/wow-mini-program/backups && sudo cp /opt/wow-mini-program/server/data/wow_news.sqlite3 /opt/wow-mini-program/backups/wow_news.sqlite3.$(date -u +%Y%m%dT%H%M%SZ)'
```

```bash
WOW_DEPLOY_SKIP_BOOTSTRAP=1 ./server/deploy_lighthouse.sh
```

当前部署脚本的默认行为：

- 上传当前工作区到 `/opt/wow-mini-program`，不上传 `server/data`。
- 热部署模式要求远端已有 Python、curl、systemd 和 `/opt/wow-simc/current/simc`。
- 部署会重启 `wow-backend` 和 nginx，并 smoke 本机 `/health`、`/api/builds/home`、`/api/pve/home`、`/api/simulator/home`、`/api/websim/bootstrap`、`/websim/`，最后再从本机验证公网 `/health`。
- 部署默认启用 PG-native 日常 timer：`wow-websim-sync.timer`、`wow-stat-weights-sync.timer`、`wow-community-template-sync.timer`、`wow-season-recommended-gear-sync.timer` 和 `wow-data-health-followup.timer`。只有显式设置 `WOW_DEPLOY_START_ASYNC_SYNCS=1` 才会在部署后立刻启动 `wow-websim-sync`、`wow-stat-weights-sync` 和 `wow-community-template-sync` 服务。`wow-gear-observed-backfill` 会安装 unit；常规部署脚本不直接启用它的 timer，但 `wow-data-health-followup` 会在 `/api/data/health` 判定装备库 partial/stale/blocked 时触发该 service。
- `wow-data-health-followup.timer` 每 2 小时检查一次 `/api/data/health` 并续跑安全任务：新闻 refresh、装备 observed backfill、WebSim sync、stat weights sync。新闻 refresh 默认只处理 1 条 queue/retryable backlog，超过 `WOW_NEWS_RETRY_MAX_ATTEMPTS` 的 LLM 翻译失败会转为 blocked/report，避免无限重试。若 `/api/data/health` 报告配置好的 SimC runtime `updateAvailable=true`，它会先触发 `wow-simc-runtime-update.service`，由该 service 在已知云服务器上下载配置源、构建、切换 `/opt/wow-simc/current` 并刷新 version state；依赖 SimC 的 WebSim/stat/gear 重建留到下一轮 health follow-up 继续处理。
- 历史 `wow-news-backend.service` 属于旧 `/home/ubuntu/wow-news-backend` 部署路径，当前云上已 mask 为 `/dev/null`，不得重新启用。日常新闻刷新 cron 应指向 `/opt/wow-mini-program/server/refresh_cron.sh`，由统一后端 `wow-backend.service` 处理。
- 线上数据写入、SQLite 历史备份读取、PostgreSQL schema 变更、受控同步、环境变量修改或数据库 target 切换前，先说明范围并备份相关数据库。

PG-only 部署后必须额外验证：

```bash
ssh wow-lighthouse 'sudo awk -F= "/^WOW_DATABASE_RUNTIME=|^WOW_DATABASE_URL=|^WOW_SQLITE_MIGRATION_SOURCE=/{print \$1\"=\"(\$1==\"WOW_DATABASE_URL\" ? \"<redacted>\" : \$2)}" /etc/wow-backend.env'
curl -fsS http://124.223.51.33/api/data/health
curl -fsS http://124.223.51.33/api/websim/assets
curl -fsS 'http://124.223.51.33/api/websim/talents?class=mage&spec=frost&hero=frostfire'
curl -fsS 'http://124.223.51.33/api/websim/gear?class=mage&spec=frost&compact=1&mode=initial'
```

期望 `WOW_DATABASE_RUNTIME=postgres_only`，没有线上 `WOW_SQLITE_MIGRATION_SOURCE`，日志中没有 runtime SQLite fallback。WCL v2 credentials 配好后只能证明 OAuth/GraphQL 可用；如果 `/api/data/health` 的 `community_templates` 仍因 `combatantinfo template seed/report extraction` 为 `partial`，那是抽取链路缺口，不是凭据缺失。

完整部署入口：

```bash
./server/deploy_lighthouse.sh
```

## 当前认证状态

2026-06-12 从当前 Codex Windows 环境验证：

- `124.223.51.33:22` 可达。
- `http://124.223.51.33/health` 返回 `{"ok": true, "service": "wow-backend"}`。
- 当前用户的 `known_hosts` 已记录该服务器 ED25519 host key。
- 仓库未发现提交的 SSH 私钥、密码或 `WOW_LIGHTHOUSE_PASSWORD` 实际值。
- 已在当前机器生成专用私钥 `~/.ssh/wow_lighthouse_ed25519`，公钥指纹为 `SHA256:WAm+gfCOGxoyMM8uP9hldV9agTm4M66SGs5G15+as7c`。
- 已把该公钥添加到远端 `ubuntu` 用户的 `~/.ssh/authorized_keys`。
- 已配置本机 SSH alias `wow-lighthouse`，并让 `124.223.51.33` 也匹配同一条 SSH 配置，部署脚本可直接复用该密钥。
- 已验证 `ssh wow-lighthouse` 可以非交互登录；远端主机为 `VM-4-8-ubuntu`，`wow-backend` 为 `active`，`ubuntu` 用户具备免密 sudo。
- 密码只用于本次引导密钥登录，不记录在仓库或本文档中。

远程下载、安装、`git pull/fetch`、依赖安装、修改生产环境变量前，先确认本次操作范围。例外：当用户明确要求处理 SimC 更新、WebSim/SimC readiness、赛季切换阻塞，或已授权 health follow-up 自动处理 SimC runtime 时，可以直接在已知云服务器上更新配置好的 SimulationCraft runtime；不要把这个例外扩展到本机下载、任意第三方下载、依赖安装或修改 SimC repo/branch。

## 已知风险

- 2026-06-12 / 2026-06-29：`/admin/analytics` 和 `/admin/gates` 管理页当前通过 `http://124.223.51.33` 暴露，浏览器提交 `WOW_ANALYTICS_ADMIN_TOKEN` 或 `WOW_ADMIN_TOKEN` 时会经过明文 HTTP 传输。token 只应保存在服务器 `/etc/wow-backend.env`、本机安全记录或受信任浏览器本地存储中，不要写入仓库、日志或截图。
- 上线前加固项：为管理页接入 HTTPS 正式域名；在 nginx 层增加访问控制，例如 IP 白名单、Basic Auth 或仅内网/VPN 访问；完成切换后轮换 `WOW_ANALYTICS_ADMIN_TOKEN` 和 `WOW_ADMIN_TOKEN`。
