# WOW Mini Program

魔兽世界辅助小程序，面向正式服与测试服玩家，提供资讯追踪、职业专精查询、大秘境 / 团本数据专区，以及带 AI 辅助能力的构筑模拟器。

## 项目目标

首版围绕 4 个核心能力展开：

1. **资讯追踪**：关注最新正式服以及测试服资讯，包括游戏玩法、版本变动和职业强度变化。
2. **职业专精查询**：学习最高端玩家的职业专精构筑，包括天赋构筑、装备模拟、属性权重和输出循环。
3. **大秘境和团队 raid 专区**：按当前赛季展示大秘境队伍天梯、职业天梯、赛季副本，以及团队 raid 首杀战报和 boss 攻略入口。
4. **构筑模拟器**：提供 AI 功能辅助玩家跑 SimCraft、分析 WCL 数据、比较配装收益和定位战斗问题。

## 当前界面

小程序目前采用 5 个底部 tab：

| Tab | 页面 | 说明 |
| --- | --- | --- |
| 最新资讯 | `pages/news/news` | 由 Lighthouse 轻量后端提供正式服、测试服、职业强度动态、完整中文详情与来源记录 |
| 职业专精 | `pages/builds/builds` | 高端玩家构筑、天赋构筑、装备模拟、属性权重与输出循环 |
| PVE专区 | `pages/pve/pve` | 当前赛季大秘境专区、团队 raid 专区、来源和分析窗口 |
| 智能分析 | `pages/simulator/simulator` | SimCraft、WCL、配装对比、AI 分析建议；职业专精详情可带入天赋/装备上下文生成 SimC 任务 |
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
│   │   ├── builds.*             # 职业专精入口
│   │   ├── detail.*             # 属性、循环、装备模拟详情
│   │   ├── intel.*              # 职业情报页
│   │   ├── talent-simulator.*   # 原生 WebSim 天赋模拟器
│   │   └── websim-api.js
│   ├── common/                  # API、鉴权、埋点、本地模板和游戏资产工具
│   ├── news/
│   ├── profile/
│   ├── pve/
│   └── simulator/
│       ├── simulator.*          # 智能分析入口
│       ├── simc.*               # SimC 对话/提交
│       ├── wcl.*                # WCL 日志入口
│       ├── chickenbro.*         # 炸鸡队长证据教练
│       └── task-detail.*        # 已保存任务详情
├── project.config.json
├── server/
│   ├── news_backend.py          # 统一 HTTP 后端
│   ├── websim_payload.py        # Season Data Cache / WebSim / 装备和天赋契约
│   ├── simulator_payload.py     # SimC/WCL/LLM 报告边界
│   ├── analytics.py             # 事件采集与管理报表
│   └── *.service / *.timer      # 生产 systemd jobs
├── docs/
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

当前 API 按域分组：

- 基础与健康：`GET /health`、`GET /api/data/health`、`GET /api/game/season`
- 资讯：`GET /api/news/home`、`GET /api/news/list`、`GET /api/news/article?id=...`、`GET /api/news/refresh-runs/latest`、`POST /api/news/refresh?mode=scheduled`
- 职业专精 / PVE：`GET /api/builds/home`、`GET /api/builds/intel`、`GET /api/builds/detail?id=法师-冰霜`、`GET /api/builds/stat-weights/refresh-runs/latest`、`GET /api/pve/home`、`GET /api/pve/module?key=bossGuides`
- WebSim / 天赋 / 装备：`GET /api/websim/bootstrap`、`GET /api/websim/assets`、`GET /api/websim/talents`、`GET /api/talents/tree`、`GET /api/websim/gear?class=mage&spec=frost&compact=1`、`GET /api/websim/loot?instanceId=...`、`POST /api/websim/profile`、`POST /api/websim/gear/stats`、`POST /api/websim/simulate`、`POST /api/talents/validate`、`POST /api/talents/export`、`POST /api/talents/import`
- 账号与模板：`POST /api/auth/wechat-login`、`POST /api/me/profile`、`GET /api/me/build-templates?type=talent`、`POST /api/me/build-templates`、`DELETE /api/me/build-templates?id=...`
- 智能分析：`GET /api/simulator/home`、`POST /api/simulator/analyze`、`GET /api/simulator/tasks?guest=1`、`GET /api/simulator/task?id=...&guest=1`
- 炸鸡队长：`POST /api/chickenbro/messages`、`POST /api/chickenbro/sessions`、`GET /api/chickenbro/sessions?id=...`、`GET /api/chickenbro/jobs?id=...`、`GET /api/chickenbro/profiles?classKey=...&specKey=...`
- 埋点和管理：`POST /api/analytics/events`、`GET /admin/analytics`、`GET /api/admin/analytics/*`、`POST /api/admin/analytics/rollup`

账号写接口统一使用 Bearer token。小程序 API client 在明文 HTTP + auth 场景会拒绝发送 token 并回退到本地数据；个人模板会先写入本地 `wow_build_templates_v1`，只有 HTTPS/合法域名可用时才同步到 `/api/me/build-templates`。

- `GET /api/simulator/home`
- `POST /api/simulator/analyze`
- `GET /api/simulator/tasks?guest=1`
- `GET /api/simulator/task?id=...&guest=1`

小程序默认在开发版访问 `http://124.223.51.33`。体验版/正式版需要通过 `getApp().globalData.backendApiBaseUrl`、本地缓存 `wow_backend_api_base_url`，或构建环境变量 `WOW_BACKEND_API_BASE_URL` 配置 HTTPS 合法域名；未配置时会使用本地 fallback payload，避免空屏。

资讯详情公共 payload 只发布同时满足 `contentStatus=ready`、`licenseStatus=approved`、`verificationStatus=official_verified`、`translationStatus=llm`、`translationFidelity=source_translation`、`sourceTier=official` 的文章：中文标题为主，保留 `originalTitle` 作为原题副标题，正文仅使用 `bodyBlocksZh` 块级渲染，tag 使用 `tagItems` 中文 chip，`sourceBadges` 与来源信息一并保留，公共 API 不返回原文正文。自动采集首版优先覆盖 Blizzard 官方文章；Wowhead / Icy Veins 等第三方来源未确认授权前只做 reference-only 发现/佐证，不进入公共 payload；正文抓取、LLM 逐块直译、授权门禁、官方校验或质检失败时记录在 refresh run 中，不发布给前端。

SimC 分析返回 `evidenceState`、`runPolicy`、`allowedNumbers` 和结构化 `report`；LLM 报告只能引用 allowedNumbers 内的数字，否则回退后端 deterministic report。WCL 分析当前只完成 report URL/code/fight 解析和缺凭据阻断；没有 `WOW_WARCRAFTLOGS_CLIENT_ID` / `WOW_WARCRAFTLOGS_CLIENT_SECRET` 时返回 `blocked/missing_credentials`，不会调用 LLM 伪造日志结论。

LLM 和 SimCraft 由服务器环境控制：

- `WOW_LLM_API_URL`：OpenAI-compatible chat completions endpoint。
- `WOW_LLM_API_KEY`：LLM API key，不提交到仓库。
- `WOW_LLM_MODEL`：默认 `deepseek-v4-flash`。
- `WOW_BLIZZARD_CLIENT_ID` / `WOW_BLIZZARD_CLIENT_SECRET`：Battle.net API client credentials，仅放服务器；缺失时 WebSim 赛季、装备和天赋数据会进入 `blocked` 状态，不展示可能过期的副本池。
- `WOW_BLIZZARD_REGION`：默认 `us`。
- `WOW_BLIZZARD_LOCALE`：默认 `zh_CN`；`WOW_BLIZZARD_LOCALES` 默认 `zh_CN,zh_TW,en_US`，用于官方中文优先、本地化缺失时回退。
- `WOW_WARCRAFTLOGS_CLIENT_ID` / `WOW_WARCRAFTLOGS_CLIENT_SECRET`：Warcraft Logs v2 API credentials；缺失时 WCL 分析和 data health 明确标为 `missing_credentials`。
- `WOW_WARCRAFTLOGS_API_KEY`：Warcraft Logs v1 API key；可作为 v1 REST 凭据被 health/WCL 启动层识别，但完整日志 GraphQL 抽取仍需要后续实现或 v2 OAuth 凭据。
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
WOW_BLIZZARD_CLIENT_ID=...
WOW_BLIZZARD_CLIENT_SECRET=...
WOW_BLIZZARD_LOCALE=zh_CN
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

脚本会上传当前工作区到 `/opt/wow-mini-program`，注册 `wow-backend` systemd service，并用 Nginx 将 80 端口代理到本机 `8787`。完整 bootstrap 模式会安装 Python/Node/Nginx、Codex CLI 与 SimCraft 构建依赖，从官方 `simulationcraft/simc` 仓库的 `midnight` 分支构建 CLI-only `simc`，并注册 `wow-simc-version-check.timer` 每 12 小时检测 GitHub 分支版本。

日常热部署优先复用远程已有依赖：

```bash
WOW_DEPLOY_SKIP_BOOTSTRAP=1 ./server/deploy_lighthouse.sh
```

部署脚本默认只重启后端并做轻量 smoke，不会自动启动长耗时同步任务；只有显式设置 `WOW_DEPLOY_START_ASYNC_SYNCS=1` 时才会启动 `wow-websim-sync`、`wow-stat-weights-sync` 和 `wow-community-template-sync`。如服务器或用户变化，可通过环境变量覆盖：

```bash
WOW_LIGHTHOUSE_HOST=124.223.51.33 WOW_LIGHTHOUSE_USER=ubuntu ./server/deploy_lighthouse.sh
```

远程调试登录、常用路径和运维命令见 [docs/remote-debugging.md](docs/remote-debugging.md)。

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
- 继续补齐 Season Data Cache 的 deterministic SimC 变体、宝石/附魔元数据、赛季漂移监控和告警。
- 深化 WCL GraphQL 日志抽取、同类样本窗口、炸鸡队长证据编排和结构化报告。
- 增加角色绑定、订阅提醒、收藏管理和跨端个人资产同步。
