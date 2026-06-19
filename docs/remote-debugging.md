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
- SQLite 数据目录：`/opt/wow-mini-program/server/data`

## 常用调试命令

```bash
ssh wow-lighthouse
cd /opt/wow-mini-program
curl -fsS http://127.0.0.1:8787/health
sudo systemctl status wow-backend --no-pager
sudo journalctl -u wow-backend -n 120 --no-pager
sudo systemctl restart wow-backend
```

本地验证远程 API：

```bash
curl -fsS http://124.223.51.33/health
python3 server/simulator_e2e_smoke.py --base-url http://124.223.51.33 --timeout 90
```

热部署优先复用远程已有依赖：

账号表或 schema 变更上线前先备份 SQLite：

```bash
ssh wow-lighthouse 'sudo install -d -m 700 -o ubuntu -g ubuntu /opt/wow-mini-program/backups && sudo cp /opt/wow-mini-program/server/data/wow_news.sqlite3 /opt/wow-mini-program/backups/wow_news.sqlite3.$(date -u +%Y%m%dT%H%M%SZ)'
```

```bash
WOW_DEPLOY_SKIP_BOOTSTRAP=1 ./server/deploy_lighthouse.sh
```

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

远程下载、安装、`git pull/fetch`、依赖安装、修改生产环境变量前，先确认本次操作范围。

## 已知风险

- 2026-06-12：`/admin/analytics` 管理报表当前通过 `http://124.223.51.33/admin/analytics` 暴露，浏览器提交 `WOW_ANALYTICS_ADMIN_TOKEN` 时会经过明文 HTTP 传输。该 token 只应保存在服务器 `/etc/wow-backend.env` 或本地安全记录中，不要写入仓库、日志或截图。
- 上线前加固项：为管理报表接入 HTTPS 正式域名；在 nginx 层增加访问控制，例如 IP 白名单、Basic Auth 或仅内网/VPN 访问；完成切换后轮换 `WOW_ANALYTICS_ADMIN_TOKEN`。
