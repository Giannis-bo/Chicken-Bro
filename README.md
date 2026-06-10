# WOW Mini Program

魔兽世界辅助小程序，面向正式服与测试服玩家，提供资讯追踪、职业专精查询、大秘境 / 团本数据专区，以及带 AI 辅助能力的构筑模拟器。

## 项目目标

首版围绕 4 个核心能力展开：

1. **资讯追踪**：关注最新正式服以及测试服资讯，包括游戏玩法、版本变动和职业强度变化。
2. **职业专精查询**：学习最高端玩家的职业专精构筑，包括天赋构筑、装备获取、属性权重和输出循环。
3. **大秘境和团队 raid 专区**：按当前赛季展示大秘境队伍天梯、职业天梯、赛季副本，以及团队 raid 首杀战报和 boss 攻略入口。
4. **构筑模拟器**：提供 AI 功能辅助玩家跑 SimCraft、分析 WCL 数据、比较配装收益和定位战斗问题。

## 当前界面

小程序目前采用 5 个底部 tab：

| Tab | 页面 | 说明 |
| --- | --- | --- |
| 最新资讯 | `pages/news/news` | 由 Lighthouse 轻量后端提供正式服、测试服、职业强度动态与来源记录 |
| 职业专精 | `pages/builds/builds` | 高端玩家构筑、天赋构筑、装备获取、属性权重与输出循环 |
| 副本 | `pages/pve/pve` | 当前赛季大秘境专区、团队 raid 专区、来源和分析窗口 |
| 模拟器 | `pages/simulator/simulator` | SimCraft、WCL、配装对比、AI 分析建议 |
| 我的 | `pages/profile/profile` | 角色偏好、收藏职业、订阅与数据源设置 |

## 目录结构

```text
.
├── app.js
├── app.json
├── app.wxss
├── components/
│   └── navigation-bar/
├── pages/
│   ├── builds/
│   ├── news/
│   ├── profile/
│   ├── pve/
│   └── simulator/
├── project.config.json
└── sitemap.json
```

## 本地开发

1. 使用微信开发者工具导入本目录。
2. AppID 使用 `project.config.json` 中的当前配置，或按需要替换为自己的小程序 AppID。
3. 在开发者工具中编译预览。

本仓库不提交 `project.private.config.json`，该文件属于本地开发者工具个人配置。

## 后端服务

统一后端入口为 `server/news_backend.py`，本地启动：

```bash
WOW_NEWS_PORT=8787 python3 server/news_backend.py
```

当前 API：

- `GET /health`
- `GET /api/news/home`
- `POST /api/news/refresh?mode=manual`
- `GET /api/news/list`
- `GET /api/news/article?id=...`
- `GET /api/builds/home`
- `GET /api/builds/intel`
- `GET /api/builds/detail?id=法师-冰霜`
- `GET /api/pve/home`
- `GET /api/pve/module?key=bossGuides`
- `GET /api/simulator/home`
- `POST /api/simulator/analyze`

小程序默认在开发版访问 `http://124.223.51.33`。体验版/正式版需要通过 `getApp().globalData.backendApiBaseUrl`、本地缓存 `wow_backend_api_base_url`，或构建环境变量 `WOW_BACKEND_API_BASE_URL` 配置 HTTPS 合法域名；未配置时会使用本地 fallback payload，避免空屏。

LLM 和 SimCraft 由服务器环境控制：

- `WOW_LLM_API_URL`：OpenAI-compatible chat completions endpoint。
- `WOW_LLM_API_KEY`：LLM API key，不提交到仓库。
- `WOW_LLM_MODEL`：默认 `deepseek-v4-flash`。
- `WOW_SIMC_BIN`：默认 `/opt/wow-simc/current/simc`，部署脚本会从官方源码构建 CLI。
- `WOW_SIMC_VERSION_FILE`：默认 `/var/lib/wow-backend/simc-version.json`，由定时任务写入当前镜像 tag 与最新 tag。
- `WOW_CODEX_BIN`：默认 `/usr/local/bin/codex`，用于低频 Agent Worker。
- `WOW_CODEX_HOME`：默认 `/home/ubuntu/.codex`，只存服务器本地 Codex 配置和认证缓存。
- `WOW_CODEX_JOBS_DIR`：默认 `/var/lib/wow-backend/codex-jobs`，每个 Codex job 使用独立目录。
- `WOW_CODEX_SANDBOX`：默认 `workspace-write`；后端用户任务不要使用 `danger-full-access`。

生产环境密钥放在服务器 `/etc/wow-backend.env`，例如：

```bash
WOW_LLM_API_URL=https://api.deepseek.com/chat/completions
WOW_LLM_MODEL=deepseek-v4-flash
WOW_LLM_API_KEY=...
```

Codex CLI 认证也只放服务器本地。推荐两种方式：

```bash
# 方式一：API key，适合后端自动化
printf '%s' "$OPENAI_API_KEY" | codex login --with-api-key

# 方式二：ChatGPT / Codex access token，适合需要走 ChatGPT workspace 身份的私有 runner
printf '%s' "$CODEX_ACCESS_TOKEN" | codex login --with-access-token
```

不要把 `~/.codex/auth.json`、`CODEX_ACCESS_TOKEN` 或 API key 提交到仓库或写进小程序端。

## 轻量云部署

服务器默认目标为腾讯轻量云 `ubuntu@124.223.51.33`：

```bash
./server/deploy_lighthouse.sh
```

脚本会上传当前工作区、安装 Python/Node/Nginx、Codex CLI 与 SimCraft 构建依赖，从官方 `simulationcraft/simc` 仓库的 `midnight` 分支构建 CLI-only `simc`，注册 `wow-simc-version-check.timer` 每 12 小时检测 GitHub 分支版本，注册 `wow-backend` systemd service，并用 Nginx 将 80 端口代理到本机 `8787`。如服务器或用户变化，可通过环境变量覆盖：

```bash
WOW_LIGHTHOUSE_HOST=124.223.51.33 WOW_LIGHTHOUSE_USER=ubuntu ./server/deploy_lighthouse.sh
```

部署后在服务器上验证 Codex：

```bash
codex --version
codex login status
CODEX_HOME=/home/ubuntu/.codex python3 - <<'PY'
from server.codex_worker import run_codex_job
print(run_codex_job("只回复 OK", jobs_dir="/var/lib/wow-backend/codex-jobs", timeout_seconds=120)["status"])
PY
```

## 后续方向

- 为统一后端补充正式域名、HTTPS、微信 request 合法域名配置和刷新记录管理视图。
- 建立职业、专精、天赋、装备和副本数据模型，详见 `docs/builds-architecture.md`。
- 将当前 JS payload 迁移到数据库化采集任务，接入大秘境榜单、玩家分数和团本进度数据。
- 深化 SimCraft 配置生成、WCL 日志解析和 AI 分析链路。
- 增加角色绑定、订阅提醒和收藏管理。
