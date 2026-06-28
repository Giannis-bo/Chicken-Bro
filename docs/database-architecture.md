# 数据库架构与账号数据边界

当前后端继续使用单个 SQLite 数据库，默认由 `WOW_NEWS_DB` 指向。近期不切换数据库；先把表域、迁移记录、owner 规则和备份流程固定下来。

> 2026-06-27 方向更新：下一阶段主库已确认迁移到 PostgreSQL，并强引入用户身份、构筑档案、SimC 快照、Chickenbro 多会话、公共知识库、analytics 和 ops 分域。当前运行时仍是 SQLite；PG 目标态和迁移边界见 [PostgreSQL 迁移与产品架构决策纪要](plans/2026-06-27-postgres-identity-migration-decision-record.md)。

## Dual Runtime Transition

2026-06-28 dev-debug update: after the production hybrid cutover rehearsal, the active service was intentionally repointed to `wow_test` because the mini program is still in WeChat Developer Tools testing and not formally launched. Current personal writes should use `WOW_DATABASE_URL=postgresql://wow_app@127.0.0.1:5432/wow_test` with `WOW_DATABASE_RUNTIME=postgres_personal`; `wow_prod` must not receive developer-testing personal assets until a formal launch cutover is approved. The accidental `wow_prod` personal rows from this phase were backed up and cleaned, leaving `identity.users=0`, `app.build_templates=0`, and `app.simulator_tasks=0` in `wow_prod`.

Phase 1 originally kept SQLite as the only enabled runtime. As of the 2026-06-28 production cutover, the cloud service runs the `postgres_personal` hybrid runtime: `WOW_DATABASE_URL=postgresql://wow_app@127.0.0.1:5432/wow_prod` and `WOW_DATABASE_RUNTIME=postgres_personal` route identity/auth/profile, personal assets, SimC task enqueue/list/detail snapshots and in-process runner state writes, Chickenbro persistence, analytics, content, and WebSim read-model seams through PostgreSQL while `WOW_NEWS_DB` remains the SQLite fallback for routes that have not moved behind a PostgreSQL store seam.

The PostgreSQL target-state artifact is [0001_identity_app_content_cache_knowledge_analytics_ops.sql](../server/migrations/postgres/0001_identity_app_content_cache_knowledge_analytics_ops.sql). It defines the future `identity`, `app`, `content`, `cache`, `knowledge`, `analytics`, and `ops` schemas, but it is not applied by `init_db()` and is not a runtime switch. Runtime grants are tracked in [0002_runtime_privileges.sql](../server/migrations/postgres/0002_runtime_privileges.sql). The migration and rollback process is governed by [PostgreSQL Identity Migration Runbook](postgres-identity-migration-runbook.md).

Phase 2 identity planning starts with the read-only shadow inventory script [identity_shadow_plan.py](../server/migrations/postgres/identity_shadow_plan.py). It maps formal `wechat_users` rows to stable PG UUIDs, emits `wechat_openid` / `wechat_unionid` provider identities, counts owner-scoped assets by formal vs guest owner, and intentionally skips guest identities and legacy auth tokens. It does not copy data and does not connect to PostgreSQL.

The Phase 2 dry-run copy artifact [data_copy_plan.py](../server/migrations/postgres/data_copy_plan.py) extends that identity map into reviewable JSON or SQL for formal-owner rows in `identity.users`, `identity.user_identities`, `app.build_templates`, `app.simulator_tasks`, `app.chickenbro_sessions`, `app.chickenbro_messages`, `app.agent_jobs`, and `knowledge.user_context_summaries`, plus public/non-owner rows in `content.sources`, `content.raw_articles`, `content.article_evidence`, `content.articles`, `content.discovery_queue`, `content.refresh_runs`, `cache.websim_sync_state`, `cache.websim_items`, `cache.websim_gear_sources`, `cache.websim_gear_variants`, `cache.websim_gear_mod_options`, `cache.websim_talents`, `cache.websim_profile_presets`, `cache.websim_spell_details`, `cache.websim_community_talent_templates`, `cache.websim_season_state`, `cache.websim_season_dungeons`, `cache.websim_instances`, `cache.websim_encounters`, `cache.websim_loot`, and `cache.raiderio_cache`. It opens SQLite read-only, excludes guest owners and legacy auth tokens, and does not connect to PostgreSQL by itself.

Phase 3 adds [shadow_migrate.py](../server/migrations/postgres/shadow_migrate.py), a guarded executor for approved local/staging PostgreSQL targets. It reuses the data-copy plan, inserts tables in dependency order, verifies copied row counts, rolls back on mismatch, and blocks production-like database names unless an explicit `--allow-production` flag is used. The executor supports legacy SQLite source databases where `simulator_tasks` does not yet have worker-ready columns by deriving `queued_at` from `created_at` and using safe defaults for later worker fields.

Phase 4 adds [postgres_personal_store.py](../server/postgres_personal_store.py), [postgres_analytics_store.py](../server/postgres_analytics_store.py), [postgres_content_store.py](../server/postgres_content_store.py), and [postgres_cache_store.py](../server/postgres_cache_store.py), PostgreSQL runtime seams for strong-identity personal assets, analytics events, public news content, and WebSim cache reads. When `WOW_DATABASE_URL` is present and `WOW_DATABASE_RUNTIME=postgres_personal`, identity, auth token hash storage, user profile updates, build-template CRUD, SimC task enqueue/list/detail and in-process runner `queued -> running -> completed/failed` writes, Chickenbro session/message/job/user-context persistence, analytics event writes/admin reads including simulator task snapshot cross-read, news refresh/public article reads, data-health WebSim `websim_sync` / `gearCatalog` sync-state reads, active season reads, `/api/websim/loot`, `/api/websim/gear`, and `/api/websim/talents` reads use PostgreSQL while SQLite remains the fallback for non-converted domains. `0004_chickenbro_runtime_fields.sql` keeps Chickenbro worker-ready by adding message-to-agent-job linkage and bounded context storage, `0005_content_runtime_fields.sql` adds the current news read-model fields, discovery queue, refresh runs, and sequence grants needed by `wow_app`, `0006_websim_season_loot_cache.sql` adds the PG season/journal/loot read model, `0007_websim_gear_catalog_cache.sql` extends PG gear source/variant/global mod-option cache tables, `0008_websim_talent_cache.sql` extends PG talent nodes, spell details, profile presets, and community talent templates for the current SQLite read model, and `0009_runtime_reconcile_privileges.sql` grants `wow_migrator` the permissions needed for cutover-time public/cache reconciliation. Chickenbro execution still remains on the current synchronous web-backend model in this phase. This is the production hybrid runtime, not a full backend `db_connection()` cutover.

Cloud provision status as of 2026-06-28: `wow-lighthouse` has PostgreSQL 16.14 installed, listening only on `127.0.0.1:5432`; `wow_dev`, `wow_test`, and `wow_prod` exist with `0001` through `0009` applied. Shadow migration rehearsal corrected a legacy guest-detection bug: the fixed openid `guest-simulator` and derived `guest-simulator-*` identities are now both excluded, erroneous guest-owned shadow rows were cleaned from `wow_test` and `wow_prod`, and the corrected backup run records `verifiedRows=0`, `guestUsers=13`, `guestOwnedRows=52`, and `guest_identity_rows=0` in both databases. A guarded public content/cache copy from `/opt/wow-mini-program/backups/wow_news-before-public-content-cache-copy-20260627T180920Z.sqlite3` inserted and verified `12044` non-owner rows in both `wow_test` and `wow_prod`; follow-up WebSim season/loot, gear-catalog, and talent read-model copies from the same backup verified `27950` total rows with `cache.websim_items=1272`, `cache.websim_season_state=1`, `cache.websim_season_dungeons=8`, `cache.websim_instances=12`, `cache.websim_encounters=39`, `cache.websim_loot=568`, `cache.websim_gear_sources=1050`, `cache.websim_gear_variants=4017`, `cache.websim_gear_mod_options=62`, `cache.websim_talents=5246`, `cache.websim_spell_details=3240`, `cache.websim_profile_presets=49`, and `cache.websim_community_talent_templates=342`, while `identity.users` and `identity.user_identities` remain `0`. Cutover-time reconciliation from `/opt/wow-mini-program/backups/wow_news-before-pg-fresh-reconcile-20260627T195118Z.sqlite3` refreshed public/cache rows in `wow_prod` with `syncRunId=ef08bca3-f16b-43ba-a1e3-de2e0a18ccd2`, `reconcileMode=public_cache`, and `verifiedRows=27950`. A 3-cycle temporary `postgres_personal` backend on `127.0.0.1:8788` verified authenticated production-DSN public/cache/personal/SimC/Chickenbro/analytics flows and cleaned all smoke rows. Production `wow-backend` now has `WOW_DATABASE_URL=postgresql://wow_app@127.0.0.1:5432/wow_prod`, `WOW_DATABASE_RUNTIME=postgres_personal`, and `PGPASSFILE=/home/ubuntu/.pgpass`; rollback env backup is `/etc/wow-backend.env.before-pg-runtime-20260627T200625Z`. Main-service smoke verified PG cache marker reads, authenticated profile/template CRUD, SimC task list/detail snapshot reads, Chickenbro session/job persistence, analytics event write, and cleanup; public `http://124.223.51.33/health`, `/api/news/home`, `/api/websim/gear?class=mage&spec=frost&compact=1`, and `/api/websim/talents?class=mage&spec=frost&hero=spellslinger` return `200`. `identity.users=0`, rehearsal identities/events are cleaned, `content.articles=24`, `cache.websim_gear_variants=4017`, and `cache.websim_talents=5246`.

## 数据域

| 域 | 表 | 数据性质 | 规则 |
| --- | --- | --- | --- |
| Identity | `wechat_users`, `auth_tokens` | 持久账号与会话 | `auth_tokens.user_id` 必须指向 `wechat_users.id`，过期 token 会被清理。 |
| User Data | `user_build_templates`, `simulator_tasks`, `chickenbro_sessions`, `chickenbro_messages`, `chickenbro_user_profiles` | 用户资产 | 写接口必须有账号 token，或显式 guest policy；列表/详情/删除只能访问当前 owner 或当前 guest id。`simulator_tasks.summary_json` 保存任务列表所需的紧凑读模型，避免列表依赖完整 request/analysis 反解析。炸鸡队长长期记忆只保存结构化角色、场景、偏好和历史摘要，不把原始日志或完整 SimC profile 写入长期画像。 |
| News | `news_articles`, `news_sources`, `news_raw_articles`, `news_article_evidence`, `news_refresh_runs` | 可审计内容发布 | 公共 payload 只发布通过授权、官方校验和 source translation 门禁的内容。 |
| WebSim/Game Cache | `websim_sync_state`, `websim_season_state`, `websim_season_dungeons`, `websim_instances`, `websim_encounters`, `websim_loot`, `websim_items`, `websim_item_aliases`, `websim_gear_sources`, `websim_gear_variants`, `websim_gear_mod_options`, `websim_item_sets`, `websim_talents`, `websim_spell_details`, `websim_profile_presets`, `websim_community_*`, `websim_asset_registry`, `websim_translations`, Raider.IO/stat weight cache, `chickenbro_spec_profiles` | 可重建 Season Data Cache | 缺凭据、过期或对账失败时必须降级为 `partial`、`stale` 或 `blocked`；本地只保存规范化证据、索引、读取模型和健康状态，不作为人工维护的真理库。炸鸡队长 `published` 画像可支撑结论，`partial` 只做背景，`stale/blocked/needs_review` 不进入结论链路。 |
| Analytics | `analytics_events`, `analytics_user_links`, `analytics_daily_metrics` | 事件与聚合 | 事件接口记录页面、功能、会话和客户端 hash；不存用户提交的 prompt/profile 原文；可归档，不能混入用户资产表。 |
| Ops | `schema_migrations`, `websim_sync_state`, `agent_jobs` | 运维控制面 | 记录已初始化的 schema 能力、同步状态和后台 agent 任务状态。`agent_jobs` 记录 queued/running/succeeded/failed/timed_out 和 bounded context/result，用户可见历史仍由对应业务表承载。 |

## Migration 规则

- `db_connection()` 必须启用 `PRAGMA foreign_keys = ON`、`busy_timeout` 和 WAL。
- `init_db()` 先创建 `schema_migrations`，再创建业务表，最后写入当前 schema 标记。
- 当前标记：
  - `core_schema_v1`
  - `user_build_templates_v1`
  - `chickenbro_backend_v1`
  - `simulator_task_summary_v1`
  - `simulator_task_worker_ready_v1`
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

`GET /api/data/health` 是只读聚合接口，不主动触发外部同步。它汇总新闻发布门禁、Raider.IO 缓存、WebSim 赛季、WebSim 同步、`gear_catalog`、`talent_catalog`、社区模板、Stat Weights、Warcraft Logs credentials 和 Battle.net API 配置状态。

当前组件 key 以线上 payload 为准：`backend`、`news`、`raiderio`、`websim_season`、`websim_sync`、`gear_catalog`、`talent_catalog`、`community_templates`、`stat_weights`、`wcl_credentials`、`blizzard_api`。

装备、宝石、附魔和变体属于 `Season Data Cache` 的核心读模型。每条可被前端或 SimC 链路消费的数据都应能追溯到 `sourceType`、`sourceStatus`、`seasonRevision`、`checkedAt`、`status` 和 `blockers`；缺少确定 `bonus_id/gem_id/enchant_id/crafted_stats` 等 SimC 字段时保持 `partial` 或 `blocked`，不得把展示候选标为可执行。装备实例属性的生产来源限定为 SimC JSON gear output 或 Battle.net Game Data，Raider.IO/WCL 角色 API 只能提供观测到的 itemId、装等、bonus/gem/enchant 配置、角色链接和校验引用，不能反填为生产属性。

目标态是线上可放心消费的装备明细变体全部为 `verified`。`partial` / `blocked` 可以作为同步、回填和对账的中间态入库，但不能静默进入玩家可见结论；任何新增或残留的 `partial`、`blocked` 或 blocker 都必须在 `/api/data/health`、同步日志和交付说明中列出 item、slot、variant、source 和 blocker，并提交给项目 owner 一起分析根因和补齐路径。若上线前仍存在玩家可见 `partial` / `blocked`，必须说明影响范围，并把相关页面展示降级为来源或属性缺口。

读接口只能格式化和裁剪 DB 中已存在的装备明细，不得在请求时补造缺失难度 / 装等轨道，也不得临时借用兄弟变体属性来伪装当前变体已验证。任何补齐动作都必须发生在同步、回填或对账服务中，写回 DB 后再作为 `verified` 读取。

线上当前已验证当前赛季来源覆盖：M+ `8/8`、团本 `4/4`、journal loot `verified`；整体 health 仍可能是 `partial`，主要因为 deterministic SimC variant preset、天赋 spell detail、社区模板/WCL 凭据或 stat weight 等后续数据缺口。文档和 UI 必须表达这个分层，不得把“赛季来源覆盖已齐”包装成“所有装备/模拟数据已完全 verified”。

核心 catalog 组件应在 `details.catalogContract` 下暴露统一只读契约：`status`、`checkedAt`、`schemaRevision`、`revision`、`sourceStatus`、`coverage`、`topBlockers`、`lastError` 和 `staleAfter`。`talent_catalog` 当前由本地 `websim_talents`、`websim_spell_details`、`websim_profile_presets`、`websim_community_talent_templates` 与 `websim_sync` 状态派生；缺官方对账凭据时保持 `pending_official_audit` / `partial`，不得把 SimC/Wago 派生数据静默标为官方 verified。

状态只允许使用：

- `verified`
- `partial`
- `stale`
- `blocked`
- `missing_credentials`
- `pending_official_audit`

任何 key/token/secret 文本都必须在 payload 中被脱敏。

## 备份和上线检查

上线前：

```bash
python -m unittest tests.news_backend_test.NewsBackendTest.test_init_db_records_schema_migrations_and_enforces_foreign_keys
python -m unittest tests.news_backend_test.NewsBackendTest.test_user_build_templates_are_synced_and_isolated_by_owner
node --test tests/build-template-storage.test.js
```

远端变更前备份 SQLite：

```bash
ssh wow-lighthouse 'sudo install -d -m 700 -o ubuntu -g ubuntu /opt/wow-mini-program/backups && sudo cp /opt/wow-mini-program/server/data/wow_news.sqlite3 /opt/wow-mini-program/backups/wow_news.sqlite3.$(date -u +%Y%m%dT%H%M%SZ)'
```

部署后 smoke：

```bash
curl -fsS http://124.223.51.33/api/news/home
curl -fsS http://124.223.51.33/api/game/season
curl -fsS http://124.223.51.33/api/data/health
curl -fsS http://124.223.51.33/api/websim/bootstrap
```
