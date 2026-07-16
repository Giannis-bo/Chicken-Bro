# 数据库架构与账号数据边界

线上和测试 runtime 必须使用 `WOW_DATABASE_RUNTIME=postgres_only`。身份、账号资料、个人模板、SimC 任务、Chickenbro、analytics、news、WebSim/cache、health、admin gates 和同步状态全部通过 PostgreSQL store 读写。SQLite 只允许作为显式离线迁移源、审计输入或备份，不能参与 runtime、health、fallback 或状态裁决。

## PostgreSQL-only Runtime

Runtime stores are [postgres_personal_store.py](../server/postgres_personal_store.py), [postgres_analytics_store.py](../server/postgres_analytics_store.py), [postgres_content_store.py](../server/postgres_content_store.py), [postgres_cache_store.py](../server/postgres_cache_store.py), and [postgres_ops_store.py](../server/postgres_ops_store.py). Missing store wiring is an operational blocker, not permission to read SQLite.

PostgreSQL schema and privileges are defined by the ordered SQL files under [server/migrations/postgres](../server/migrations/postgres). [identity_shadow_plan.py](../server/migrations/postgres/identity_shadow_plan.py) and [data_copy_plan.py](../server/migrations/postgres/data_copy_plan.py) provide read-only migration inventory; [shadow_migrate.py](../server/migrations/postgres/shadow_migrate.py) is the guarded copy executor. The current migration and rollback procedure is [PostgreSQL Runtime and Migration Runbook](postgres-identity-migration-runbook.md).

`server/postgres_cache_sync.py` is the PostgreSQL-native entrypoint for WebSim, stat-weight, community-template, observed-gear and crafted-gear jobs. A stage that lacks source, sample, credential, SimC output or parseable evidence records `partial` / `blocked` in PostgreSQL and stops; it does not open SQLite.

## 数据域

| 域 | 表 | 数据性质 | 规则 |
| --- | --- | --- | --- |
| Identity | `wechat_users`, `auth_tokens` | 持久账号与会话 | `auth_tokens.user_id` 必须指向 `wechat_users.id`，过期 token 会被清理。 |
| User Data | `user_build_templates`, `simulator_tasks`, `chickenbro_sessions`, `chickenbro_messages`, `chickenbro_user_profiles` | 用户资产 | 写接口必须有账号 token，或显式 guest policy；列表/详情/删除只能访问当前 owner 或当前 guest id。`simulator_tasks.summary_json` 保存任务列表所需的紧凑读模型，避免列表依赖完整 request/analysis 反解析。炸鸡队长长期记忆只保存结构化角色、场景、偏好和历史摘要，不把原始日志或完整 SimC profile 写入长期画像。 |
| News | `news_articles`, `news_sources`, `news_raw_articles`, `news_article_evidence`, `news_refresh_runs` | 可审计内容发布 | 公共 payload 只发布通过授权、官方校验和 source translation 门禁的内容。 |
| WebSim/Game Cache | `websim_sync_state`, `websim_season_state`, `websim_season_dungeons`, `websim_instances`, `websim_encounters`, `websim_loot`, `websim_items`, `websim_item_aliases`, `websim_gear_sources`, `websim_gear_variants`, `websim_gear_mod_options`, `websim_item_sets`, `websim_talents`, `websim_spell_details`, `websim_profile_presets`, `websim_community_*`, `websim_asset_registry`, `websim_translations`, Raider.IO/stat weight cache, `chickenbro_spec_profiles` | 可重建 Season Data Cache | 缺凭据、过期或对账失败时必须降级为 `partial`、`stale` 或 `blocked`；本地只保存规范化证据、索引、读取模型和健康状态，不作为人工维护的真理库。炸鸡队长 `published` 画像可支撑结论，`partial` 只做背景，`stale/blocked/needs_review` 不进入结论链路。 |
| Analytics | `analytics_events`, `analytics_user_links`, `analytics_daily_metrics` | 事件与聚合 | 事件接口记录页面、功能、会话和客户端 hash；不存用户提交的 prompt/profile 原文；可归档，不能混入用户资产表。 |
| Ops | `schema_migrations`, `websim_sync_state`, `agent_jobs`, `ops.admin_gate_diagnoses`, `ops.audit_logs` | 运维控制面 | 记录已初始化的 schema 能力、同步状态、后台 agent 任务状态、门禁 gap 诊断和运维审计。`agent_jobs` 记录 queued/running/succeeded/failed/timed_out 和 bounded context/result，用户可见历史仍由对应业务表承载；`ops.admin_gate_diagnoses` 只保存人工诊断事实，不修改源记录、health component 或公开 payload。 |

## Runtime and Migration 规则

- Online runtime must set `WOW_DATABASE_RUNTIME=postgres_only`; `WOW_SQLITE_RUNTIME_DISABLED=1` is an equivalent hard guard for local and test runs.
- `db_connection()` is legacy SQLite plumbing and must raise in PG-only runtime. It is allowed only for legacy tests, local SQLite inspection, or explicitly marked migration-source runs.
- `WOW_NEWS_DB` points to a historical SQLite file only. It must not be used as a live read/write source under systemd, health checks, public API routes, sync tasks, or admin gates.
- `WOW_SQLITE_MIGRATION_SOURCE=1` / `WOW_ALLOW_SQLITE_MIGRATION_SOURCE=1` may be used by one-shot migration/backup scripts that read SQLite and write PostgreSQL. Do not set these flags in the online service environment.
- `init_db()` remains a legacy SQLite initializer for historical compatibility tests; PostgreSQL schema is applied through SQL migrations and `shadow_migrate.py`/psql deployment steps.
- Online sync units (`wow-websim-sync.timer`, `wow-stat-weights-sync.timer`, `wow-community-template-sync.timer`, and the installed-on-demand `wow-gear-observed-backfill` unit) are PostgreSQL-native jobs. They must not set `WOW_NEWS_DB`; if a substage cannot produce verified rows yet, it records a PostgreSQL `blocked` / `partial` sync-state payload instead of failing into SQLite.
- 新增用户写表前必须先补 migration 标记、owner 字段、外键和权限测试。

## SimC 任务表边界

`simulator_tasks` 是玩家可见模拟历史的用户资产表。它同时承载 legacy simulator 任务和当前 `mode=simcraft_template` 模板任务，所有读写都必须先通过账号 token 或显式 guest policy 限定 owner。

字段职责：

- `request_json`：保存 normalized 请求。对模板任务，它包含 slim `templateContext`、race/scenario、`simcTaskFingerprint`、后台 runner 所需 profile，以及可用于详情属性回填的 `metadata.gearSnapshot`。公共详情响应必须剥离 profile、guestId 和内部执行标记。
- `analysis_json`：保存任务当前执行状态和完整后端分析结果。对模板任务，玩家侧只公开重新规范化后的 `simcReport`，并移除 `llm`、`codex`、`allowedNumbers`、raw SimC stdout、`draftProfile` 等调试/内部字段。
- `summary_json`：保存任务列表紧凑读模型，由 `simulator_task_summary_v1` 迁移添加。它只服务列表标题、状态、标签、场景、完成时间和兼容性字段；列表不得依赖完整 `analysis_json` 反解析，也不得触发装备属性计算。
- `queued_at` / `started_at` / `finished_at` / `attempt` / `locked_by` / `heartbeat_at` / `cancel_requested` / `last_error`：由 `simulator_task_worker_ready_v1` 迁移添加的 SQLite 兼容字段。当前 web-backend runner 只填充 queued/start/finish/attempt/error；`locked_by`、`heartbeat_at` 和 `cancel_requested` 预留给后续独立 worker，不在当前阶段改变执行模型。

模板任务的状态流为 `queued -> running -> completed/failed`。`simcTaskFingerprint` 用于复用同一 owner 下仍处于 `queued/running` 的 active task，避免重复插入。后台 runner 更新状态时必须同步刷新 `analysis_json` 和 `summary_json`。

详情页可以做一次受控回填：当 `analysis_json.simcReport.build.statSnapshot` 缺失，但 `request_json` 仍有完整 `gearSnapshot + talent rawString + class/spec/race/scenario` 时，`backfill_simcraft_template_detail_stat_snapshot` 可调用装备 stats 读模型生成 verified compact `statSnapshot`，并写回 `analysis_json`。这个回填只发生在单任务详情，不应放入任务列表、health 或批量读取路径。

## 个人模板接口

- `GET /api/me/build-templates`
- `GET /api/me/build-templates?type=talent|gear`
- `POST /api/me/build-templates`
- `DELETE /api/me/build-templates?id=...`

所有接口都通过 `Authorization: Bearer <token>` 鉴权。`POST` 按 `user_id + type + rawString` 去重更新，返回服务端模板 `id`，并保留前端本地 `clientId` 以便合并。其他账号删除同一模板 id 会返回 not found。

小程序端仍先写本地 `wow_build_templates_v1`，然后尝试同步到远端。`requestJson` 在明文 HTTP + auth 场景会拒绝发送 Bearer token 并走 fallback，因此开发 IP 调试不会泄露账号 token；体验版/正式版需要配置 HTTPS 合法域名才会启用账号同步。

## 数据健康接口

`GET /api/data/health` 是只读聚合接口，不主动触发外部同步。PG-only 下它只读取 PostgreSQL stores，不打开 SQLite，也不使用旧 `websim_sync_state` 快照遮蔽当前 PG read-model 缺口。它汇总新闻发布门禁、Raider.IO 缓存、WebSim 赛季、WebSim 同步、`gear_catalog`、`talent_catalog`、模板到 SimC 桥接、社区模板、Stat Weights、Warcraft Logs credentials 和 Battle.net API 配置状态。

组件 key 以实时 payload 为准，当前包括 `backend`、`news`、`raiderio`、`websim_season`、`websim_sync`、`gear_catalog`、`talent_catalog`、`template_simc_bridge`、`community_templates`、`stat_weights`、`wcl_credentials` 和 `blizzard_api`。文档不固定某次 counts 或 overall status；UI 和运维判断必须读取当前 `status`、`details`、`blockers` 与 `checkedAt`。

装备、宝石、附魔和变体属于 `Season Data Cache` 的核心读模型。每条可被前端或 SimC 链路消费的数据都应能追溯到 `sourceType`、`sourceStatus`、`seasonRevision`、`checkedAt`、`status` 和 `blockers`；缺少确定 `bonus_id/gem_id/enchant_id/crafted_stats` 等 SimC 字段时保持 `partial` 或 `blocked`，不得把展示候选标为可执行。装备实例属性的生产来源限定为 SimC JSON gear output 或 Battle.net Game Data，Raider.IO/WCL 角色 API 只能提供观测到的 itemId、装等、bonus/gem/enchant 配置、角色链接和校验引用，不能反填为生产属性。

目标态是线上可放心消费的装备明细变体全部为 `verified`。`partial` / `blocked` 可以作为同步、回填和对账的中间态入库，但不能静默进入玩家可见结论；任何新增或残留的 `partial`、`blocked` 或 blocker 都必须在 `/api/data/health`、同步日志和交付说明中列出 item、slot、variant、source 和 blocker，并提交给项目 owner 一起分析根因和补齐路径。若上线前仍存在玩家可见 `partial` / `blocked`，必须说明影响范围，并把相关页面展示降级为来源或属性缺口。

读接口只能格式化和裁剪 DB 中已存在的装备明细，不得在请求时补造缺失难度 / 装等轨道，也不得临时借用兄弟变体属性来伪装当前变体已验证。任何补齐动作都必须发生在同步、回填或对账服务中，写回 DB 后再作为 `verified` 读取。PG-only 下 `/api/websim/gear` 在 season stale 时仍返回完整 `slots`、`equippedSet`、`readiness`、候选组和 `communityTemplates` schema，把 stale/partial 体现在 `dataStatus`、`catalogStatus`、`catalogBlockers` 和 health summary；`WOW_ALLOW_SQLITE_PUBLIC_CACHE_FALLBACK` 在 PG-only 下无效，不能因为 stale 自动读取 SQLite 旧缓存并掩盖 PG read-model 状态。

赛季来源覆盖、catalog 完整度、SimC variant、spell detail、社区模板、crafted seed 和 stat weights 是独立门禁。一个组件 verified 不能提升其他组件；线上状态始终以 `/api/game/season` 与 `/api/data/health` 的实时 payload 为准。

核心 catalog 组件应在 `details.catalogContract` 下暴露统一只读契约：`status`、`checkedAt`、`schemaRevision`、`revision`、`sourceStatus`、`coverage`、`topBlockers`、`lastError` 和 `staleAfter`。`talent_catalog` 当前由本地 `websim_talents`、`websim_spell_details`、`websim_profile_presets`、`websim_community_talent_templates` 与 `websim_sync` 状态派生；缺官方对账凭据时保持 `pending_official_audit` / `partial`，不得把 SimC/Wago 派生数据静默标为官方 verified。

状态只允许使用：

- `verified`
- `partial`
- `stale`
- `blocked`
- `missing_credentials`
- `pending_official_audit`

任何 key/token/secret 文本都必须在 payload 中被脱敏。

## 后台门禁诊断表

`/admin/gates` 和 `/api/admin/gates/*` 是 owner-facing 只读治理台与诊断入口。`summary`、`records`、record detail 和 `queue` 只读取新闻、天赋、装备和 health 现有状态，不触发 sync、fetch、LLM 或 SimC；records 当前按 `news`、`talents`、`gear`、`gear_templates` 四个 domain 展开，分别对应新闻资讯、天赋树、装备库和装备模板。`WOW_DATABASE_RUNTIME=postgres_only` 下 records / record detail / queue 使用 PostgreSQL content/cache runtime store，`POST /api/admin/gates/diagnoses` 写入 `ops.admin_gate_diagnoses` 并审计到 `ops.audit_logs`。缺少 PG runtime store 时接口必须返回 blocked / runtimeBlockers，不能回退到 SQLite `admin_gate_diagnoses` / `ops_audit_logs`。

诊断表的信任边界：

- `target_domain` / `target_type` / `target_id` 指向被诊断的系统记录。
- `reason` / `note` / `diagnosis_type` 表示人工判断，不能覆盖 `sourceStatus`、`status`、blocker 或 health component。
- `record_fingerprint` 记录诊断时的系统门禁快照；底层记录后续重验通过时，队列层可以把诊断显示为 resolved，但不需要人工改源数据。
- 诊断 payload 只能保存脱敏摘要、状态和 blocker，不保存完整新闻原文、完整 SimC profile、token、raw request 或用户私密内容。

## 备份和上线检查

上线前：

```bash
python -m unittest tests.news_backend_test.NewsBackendTest.test_init_db_records_schema_migrations_and_enforces_foreign_keys
python -m unittest tests.news_backend_test.NewsBackendTest.test_user_build_templates_are_synced_and_isolated_by_owner
node --test tests/build-template-storage.test.js
```

远端变更前备份历史 SQLite 文件，作为迁移/回滚证据；如果本次会写入 PostgreSQL，也要同时备份当前 target：

```bash
ssh wow-lighthouse 'sudo install -d -m 700 -o ubuntu -g ubuntu /opt/wow-mini-program/backups && sudo cp /opt/wow-mini-program/server/data/wow_news.sqlite3 /opt/wow-mini-program/backups/wow_news.sqlite3.$(date -u +%Y%m%dT%H%M%SZ)'
```

部署后 smoke：

```bash
curl -fsS http://124.223.51.33/api/news/home
curl -fsS http://124.223.51.33/api/game/season
curl -fsS http://124.223.51.33/api/data/health
curl -fsS http://124.223.51.33/api/websim/bootstrap
curl -fsS http://124.223.51.33/api/websim/assets
curl -fsS 'http://124.223.51.33/api/websim/talents?class=mage&spec=frost&hero=frostfire'
curl -fsS 'http://124.223.51.33/api/websim/gear?class=mage&spec=frost&compact=1&mode=initial'
curl -fsS -X POST http://124.223.51.33/api/websim/profile -H 'Content-Type: application/json' --data '{"classKey":"mage","specKey":"frost","talents":{"rawString":"CYEA"},"gearBySlot":{}}'
```

Smoke 结果必须同时检查服务环境：`WOW_DATABASE_RUNTIME=postgres_only`，`WOW_SQLITE_MIGRATION_SOURCE` 未设置，日志中没有 `SQLite runtime is disabled` 以外的运行时 SQLite fallback 痕迹。
