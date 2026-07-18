# WOW Mini Program

魔兽世界辅助小程序，面向正式服与测试服玩家，提供资讯追踪、职业专精查询、WebSim / SimC 构筑模拟，以及“炸鸡队长”智能分析聊天入口。

## 项目目标

当前小程序主流程围绕 4 个底部 tab 展开：

1. **资讯追踪**：关注最新正式服以及测试服资讯，包括游戏玩法、版本变动和职业强度变化。
2. **职业专精查询与模拟**：学习职业 / 专精入口，进入天赋模拟器、装备模拟、SimC 任务提交和任务列表。
3. **智能分析**：直接进入“炸鸡队长”聊天，后端优先走 Codex，失败或证据不足时清晰降级。
4. **我的**：角色偏好、收藏职业、订阅与个人模板 / 任务资产的账号化边界。

PVE 专区、WCL 深度日志复盘、完整公共知识库和复杂后台管理仍保留为后续 / 待规划能力；已有代码和接口只作为历史、后台或兼容入口，不再作为当前 tab 主流程。

## 当前界面

小程序目前采用 4 个底部 tab：

| Tab | 页面 | 说明 |
| --- | --- | --- |
| 最新资讯 | `pages/news/news` | 由 Lighthouse 轻量后端提供正式服、测试服、职业强度动态、完整中文详情与来源记录 |
| 职业专精 | `pages/builds/builds` | 当前主入口为天赋构筑、装备模拟、模拟 SimC、任务列表；热门专精、属性权重和输出循环仍按证据状态保留为后续能力 |
| 智能分析 | `pages/simulator/simulator` | 直接渲染“炸鸡队长”聊天页，支持左右气泡、底部输入、新话题和话题抽屉；`/api/simulator/home` 仅作为兼容 payload |
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
│   │   ├── detail.*             # 装备模拟和保留的职业详情容器
│   │   ├── intel.*              # 职业情报页
│   │   ├── talent-simulator.*   # 原生 WebSim 天赋模拟器
│   │   └── websim-api.js
│   ├── common/                  # API、鉴权、埋点、本地模板和游戏资产工具
│   ├── news/
│   ├── profile/
│   ├── pve/                     # 已有页面，当前未注册为 tab，后续待规划恢复
│   └── simulator/
│       ├── simulator.*          # 智能分析入口，直接复用炸鸡队长聊天控制器
│       ├── chickenbro-chat.js   # 炸鸡队长共享聊天状态/请求/降级逻辑
│       ├── chickenbro.*         # 炸鸡队长独立页面，同一聊天体验
│       ├── simc.*               # SimC 模板确认/任务提交，由职业专精入口进入
│       ├── tasks.*              # SimC 任务列表
│       ├── wcl.*                # WCL 日志入口，当前未注册到小程序 pages
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

文档入口见 [docs/README.md](docs/README.md)。当前长期方向以 [docs/roadmap.md](docs/roadmap.md) 为准；`docs/plans/README.md` 是当前计划白名单，未列入白名单的日期计划不拥有执行权，历史追溯使用 Git。

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
- 职业专精 / PVE：`GET /api/builds/home`、`GET /api/builds/intel`、`GET /api/builds/detail?id=法师-冰霜`、`GET /api/builds/stat-weights/refresh-runs/latest`、`GET /api/pve/home`、`GET /api/pve/module?key=bossGuides`。PVE 接口保留兼容与后台验证，当前没有底部 tab。
- WebSim / 天赋 / 装备：`GET /api/websim/bootstrap`、`GET /api/websim/assets`、`GET /api/websim/talents`、`GET /api/websim/talents/import`、`GET /api/talents/tree`、`GET /api/websim/gear?class=mage&spec=frost&compact=1&mode=initial`、`GET /api/websim/gear?class=mage&spec=frost&compact=1&mode=slot&slot=head`、`GET /api/websim/loot?instanceId=...`、`POST /api/websim/profile`、`POST /api/websim/gear/stats`、`POST /api/websim/simulate`、`POST /api/talents/validate`、`POST /api/talents/export`、`POST /api/talents/import`
- 账号与模板：`POST /api/auth/wechat-login`、`POST /api/me/profile`、`GET /api/me/build-templates?type=talent`、`POST /api/me/build-templates`、`DELETE /api/me/build-templates?id=...`
- 智能分析 / SimC：`GET /api/simulator/home`、`POST /api/simulator/analyze`、`GET /api/simulator/tasks?guest=1`、`GET /api/simulator/task?id=...&guest=1`。当前 `pages/simulator/simulator` 不再先展示模块卡片，而是直接进入 Chickenbro；SimC 页面从职业专精入口进入。
- 炸鸡队长：`POST /api/chickenbro/messages`、`POST /api/chickenbro/sessions`、`GET /api/chickenbro/sessions?id=...`、`GET /api/chickenbro/jobs?id=...`、`GET /api/chickenbro/profiles?classKey=...&specKey=...`
- 埋点和管理：`POST /api/analytics/events`、`GET /admin/analytics`、`GET /api/admin/analytics/*`、`POST /api/admin/analytics/rollup`、`GET /admin/gates`、`GET /api/admin/gates/*`

账号写接口统一使用 Bearer token。小程序 API client 在明文 HTTP + auth 场景会拒绝发送 token 并回退到本地数据；个人模板会先写入本地 `wow_build_templates_v1`，只有 HTTPS/合法域名可用时才同步到 `/api/me/build-templates`。

小程序默认通过已登记的 HTTPS 合法域名 `https://api.chickenbro.cloud` 访问轻量云后端。体验版/正式版仍可通过 `getApp().globalData.backendApiBaseUrl`、本地缓存 `wow_backend_api_base_url`，或构建环境变量 `WOW_BACKEND_API_BASE_URL` 显式覆盖；未配置可用地址时会使用本地 fallback payload，避免空屏。

资讯详情公共 payload 只发布同时满足 `contentStatus=ready`、`licenseStatus=approved`、`verificationStatus=official_verified`、`translationStatus=llm`、`translationFidelity=source_translation`、`sourceTier=official` 的文章：中文标题为主，保留 `originalTitle` 作为原题副标题，正文仅使用 `bodyBlocksZh` 块级渲染，tag 使用 `tagItems` 中文 chip，`sourceBadges` 与来源信息一并保留，公共 API 不返回原文正文。自动采集首版优先覆盖 Blizzard 官方文章；Wowhead / Icy Veins 等第三方来源未确认授权前只做 reference-only 发现/佐证，不进入公共 payload；正文抓取、LLM 逐块直译、授权门禁、官方校验或质检失败时记录在 refresh run 中，不发布给前端。

后台门禁治理台 `/admin/gates` 面向 owner 查看新闻、天赋和装备数据从上游、规则审计、证据链、入库到前端/SimC 消费的状态。`/api/admin/gates/summary|records|queue|diagnoses` 都需要 admin Bearer token；在 `WOW_DATABASE_RUNTIME=postgres_only` 下，records / record detail / queue 走 PostgreSQL content/cache runtime store，诊断写入 `ops.admin_gate_diagnoses` 并审计到 `ops.audit_logs`。缺少 PG runtime store 时接口返回 blocked / runtimeBlockers，不回退 SQLite。左侧“新闻资讯 / 天赋树 / 装备库 / 装备模板”会按 `domain` 过滤记录；新闻按分类、状态、发布情况筛选，天赋按职业、状态、小程序可见性筛选，装备库按掉落来源、具体掉落来源、装备分类和小程序可见性筛选，装备模板按职业、小程序是否可见筛选。装备库主表对齐 `/api/websim/gear` 的小程序可展示口径：同一 `itemId + slot` 的多个变体聚合成一条主记录，优先展示 verified / SimC-ready 代表变体；`needs-variant`、`partial` 或 `observed_profile` 技术占位只作为诊断证据，不会把整件装备显示成不可见。掉落来源列展示去重后的装等轨道 chip，并隐藏重复副本名和 raw variant id。“待诊断阻断项”是独立工作台，不再作为总览页常驻右栏。治理台状态统一显示为 `english（中文）`，例如 `blocked（已阻断）`。诊断写入只记录人工判断和审计日志，不会把 `blocked` / `partial` 改成 `verified`，也不会绕过系统门禁发布内容或启动 SimC。

SimC 模板链路分为“确认”和“任务执行”两段：`mode=simcraft_template` 的确认阶段只做后端解析、装备属性快照校验、已知 SimC 兼容性阻断和紧凑 `simcReport`，不调用 LLM 或 Codex Worker；最终提交在校验通过后创建后台 `simulator_tasks`，由 runner 异步执行并把结果写回任务列表/详情。相同玩家同一时间最多保留 2 个 `queued/running` 模板任务，相同 fingerprint 会复用活动任务；单体、5目标 AOE、近似大秘境的 `fight_style/desired_targets/max_time/iterations=10000` 不因超时而降级。当前已知 `邪恶死亡骑士 + 天启骑士` 在 upstream SimC 会崩溃，后端会在属性快照和模板确认阶段直接返回中文 blocker，不启动 SimC。WCL 分析当前完成 report URL/code/fight 解析、v2 OAuth 凭据识别和 GraphQL 探针；缺凭据时返回 `blocked/missing_credentials`，凭据已配置但缺 report evidence / combatantinfo 抽取时仍返回 `partial` 或 evidence blocker，不会调用 LLM 伪造日志结论。

炸鸡队长链路使用独立 `/api/chickenbro/*`。前端只发送短消息和有限上下文，完整 raw log、完整 SimC profile、token 和 secret 不进入小程序或 Codex prompt。后端负责 scope 判断、bounded context、Codex runner、schema 校验、数字白名单、owner/guest 隔离和 fallback。当前线上可通过 `WOW_CHICKENBRO_CODEX_ENABLED=1` 进入 direct Codex chat 体验：没有 published profile 时也可以先让 Codex 做魔兽范围内的自然对话，但不得把通用知识包装成本地证据；Codex 不可用、超时、schema 不合规或输出未经批准的数字时返回 deterministic fallback。

LLM 和 SimCraft 由服务器环境控制：

- `WOW_LLM_API_URL`：OpenAI-compatible chat completions endpoint。
- `WOW_LLM_API_KEY`：LLM API key，不提交到仓库。
- `WOW_LLM_MODEL`：默认 `deepseek-v4-flash`。
- `WOW_NEWS_RETRY_MAX_ATTEMPTS`：新闻 discovery queue 中 retryable 条目的最大翻译/发布重试次数，默认 `3`；超过后进入 blocked/report，避免日常 follow-up 无限重试同一条失败新闻。
- `WOW_BLIZZARD_CLIENT_ID` / `WOW_BLIZZARD_CLIENT_SECRET`：Battle.net API client credentials，仅放服务器；缺失时 WebSim 赛季、装备和天赋数据会进入 `blocked` 状态，不展示可能过期的副本池。
- `WOW_BLIZZARD_REGION`：默认 `us`。
- `WOW_BLIZZARD_LOCALE`：默认 `zh_CN`；`WOW_BLIZZARD_LOCALES` 默认 `zh_CN,zh_TW,en_US`，用于官方中文优先、本地化缺失时回退。
- `WOW_WARCRAFTLOGS_CLIENT_ID` / `WOW_WARCRAFTLOGS_CLIENT_SECRET`：Warcraft Logs v2 API credentials；缺失时 WCL 分析和 data health 明确标为 `missing_credentials`。线上当前已配置 v2 OAuth，GraphQL endpoint 可访问，但社区模板和日志复盘仍需要 report evidence / combatantinfo 抽取能力才能从 `partial` 升级为 verified。
- `WOW_WARCRAFTLOGS_API_KEY`：Warcraft Logs v1 API key；可作为 v1 REST 凭据被 health/WCL 启动层识别，但完整日志 GraphQL 抽取仍需要后续实现或 v2 OAuth 凭据。
- `WOW_ADMIN_TOKEN`：后台门禁治理台固定 admin token；未设置时兼容回退到 `WOW_ANALYTICS_ADMIN_TOKEN`。只允许保存在服务器环境或本地安全记录中，不提交仓库，不放进小程序端。
- `WOW_SIMC_BIN`：默认 `/opt/wow-simc/current/simc`，部署脚本会从官方源码构建 CLI。
- `WOW_SIMC_VERSION_FILE`：默认 `/var/lib/wow-backend/simc-version.json`，由定时任务写入当前镜像 tag 与最新 tag。
- `WOW_SIMC_TEMPLATE_TIMEOUT_SECONDS`：模板任务 SimC 进程超时的统一覆盖；未设置时按场景使用单体 `120` 秒、5目标 AOE `180` 秒、近似大秘境 `240` 秒。
- `WOW_SIMC_TEMPLATE_STAT_WEIGHTS_TIMEOUT_SECONDS`：属性权重模板任务的专用超时覆盖；未设置时默认 `360` 秒。
- `WOW_SIMC_TEMPLATE_ACTIVE_TASK_LIMIT`：同一玩家同时 `queued/running` 的模板任务上限，默认 `2`。
- `WOW_WEBSIM_GEAR_STATS_TIMEOUT_SECONDS`：装备属性快照预检超时，默认 `45` 秒；该值不限制后台模板任务执行。
- `WOW_CODEX_BIN`：默认 `/usr/local/bin/codex`，用于低频 Agent Worker。
- `WOW_CODEX_HOME`：默认 `/home/ubuntu/.codex`，只存服务器本地 Codex 配置和认证缓存。
- `WOW_CODEX_JOBS_DIR`：默认 `/var/lib/wow-backend/codex-jobs`，每个 Codex job 使用独立目录。
- `WOW_CODEX_SANDBOX`：默认 `workspace-write`；后端用户任务不要使用 `danger-full-access`。
- `WOW_CHICKENBRO_CODEX_ENABLED`：设为 `1` 时，Chickenbro 消息会在 scope 和 owner/guest 门禁通过后尝试走 Codex runner；未设置或 Codex 不可用时走 deterministic fallback。

数据库运行时当前为 PostgreSQL-only：`WOW_DATABASE_RUNTIME=postgres_only`（或本地验证时 `WOW_SQLITE_RUNTIME_DISABLED=1`）会让身份、个人模板、SimC 任务、Chickenbro 会话 / job、analytics、news content、Raider.IO/stat weight cache、WebSim/cache 读模型、health 和 admin gates 都通过 PostgreSQL store。SQLite 只允许作为一次性迁移源、历史备份或离线审计输入；线上公开接口、同步任务和健康检查不能读取 SQLite 或用 SQLite fallback 掩盖 PG 数据缺口。WebSim PG cache 包含装备来源/变体/改造选项、天赋、赛季/掉落、`cache.websim_community_gear_templates`、`cache.stat_weight_cache` 和 `cache.websim_asset_registry`；装备接口在 season stale 时仍返回完整 schema 和当前 PG 状态。PG-only 同步入口走 `server/postgres_cache_sync.py`：WebSim SimC generated data 会直接写 `cache.websim_talents` / `cache.websim_profile_presets` / `cache.websim_spell_details`，Blizzard journal 子阶段会写 PG season/dungeon/instance/encounter/item/loot rows 并从 loot 派生 `gearCatalog` skeleton，stat weights、community templates、Raider.IO observed backfill 和显式 seed crafted backfill 也写入 PostgreSQL cache/sync state；缺样本、缺 seed、缺抽取或缺 SimC evidence 时必须写 PostgreSQL `blocked` / `partial` root cause，不允许回 SQLite。

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

部署脚本会安装并启用 PG-native 日常 timers：`wow-websim-sync.timer`、`wow-stat-weights-sync.timer`、`wow-community-template-sync.timer`、`wow-season-recommended-gear-sync.timer` 和 `wow-data-health-followup.timer`，这些 unit 不配置 `WOW_NEWS_DB`。`wow-data-health-followup.timer` 每 2 小时检查 `/api/data/health`，并续跑安全阻塞项：新闻 queue refresh、装备 observed backfill、WebSim sync、stat weights sync，以及配置好的 SimC runtime update。`wow-gear-observed-backfill.service` 会安装；部署脚本不直接启用它的 timer，通常由 health follow-up 在装备库 partial/stale/blocked 时触发。默认部署只重启后端并做轻量 smoke，不额外 no-block 启动一次同步服务；只有显式设置 `WOW_DEPLOY_START_ASYNC_SYNCS=1` 时才会在 smoke 后启动 `wow-websim-sync`、`wow-stat-weights-sync` 和 `wow-community-template-sync`。如服务器或用户变化，可通过环境变量覆盖：

```bash
WOW_LIGHTHOUSE_HOST=124.223.51.33 WOW_LIGHTHOUSE_USER=ubuntu ./server/deploy_lighthouse.sh
```

远程调试登录、常用路径和运维命令见 [docs/remote-debugging.md](docs/remote-debugging.md)。

生产外网出口默认使用云服务器本机 `mihomo.service`：后端、WebSim sync、stat weights、community template sync、gear observed backfill、SimC version check 和 SimC runtime update 都在 systemd unit 中设置 `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY=127.0.0.1:7890`，覆盖 Blizzard / Battle.net、Raider.IO、Warcraft Logs、Wago、GitHub、LLM 和 Codex worker 等海外调用。只访问本机 health 的 `wow-data-health-followup.service` 和只消费 PostgreSQL read model 的 `wow-season-recommended-gear-sync.service` 不需要代理。

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
