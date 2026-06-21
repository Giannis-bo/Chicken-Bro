# 数据库架构与账号数据边界

当前后端继续使用单个 SQLite 数据库，默认由 `WOW_NEWS_DB` 指向。近期不切换数据库；先把表域、迁移记录、owner 规则和备份流程固定下来。

## 数据域

| 域 | 表 | 数据性质 | 规则 |
| --- | --- | --- | --- |
| Identity | `wechat_users`, `auth_tokens` | 持久账号与会话 | `auth_tokens.user_id` 必须指向 `wechat_users.id`，过期 token 会被清理。 |
| User Data | `user_build_templates`, `simulator_tasks` | 用户资产 | 写接口必须有账号 token，或显式 guest policy；列表/详情/删除只能访问当前 owner。 |
| News | `news_articles`, `news_sources`, `news_raw_articles`, `news_article_evidence`, `news_refresh_runs` | 可审计内容发布 | 公共 payload 只发布通过授权、官方校验和 source translation 门禁的内容。 |
| WebSim/Game Cache | `websim_*`, Raider.IO/stat weight cache | 可重建 Season Data Cache | 缺凭据、过期或对账失败时必须降级为 `partial`、`stale` 或 `blocked`；本地只保存规范化证据、索引、读取模型和健康状态，不作为人工维护的真理库。 |
| Analytics | `analytics_*` | 事件与聚合 | 不存用户提交的 prompt/profile 原文；可归档，不能混入用户资产表。 |
| Ops | `schema_migrations`, `websim_sync_state` | 运维控制面 | 记录已初始化的 schema 能力和同步状态。 |

## Migration 规则

- `db_connection()` 必须启用 `PRAGMA foreign_keys = ON`、`busy_timeout` 和 WAL。
- `init_db()` 先创建 `schema_migrations`，再创建业务表，最后写入当前 schema 标记。
- 当前标记：
  - `core_schema_v1`
  - `user_build_templates_v1`
- 新增用户写表前必须先补 migration 标记、owner 字段、外键和权限测试。

## 个人模板接口

- `GET /api/me/build-templates`
- `GET /api/me/build-templates?type=talent|gear`
- `POST /api/me/build-templates`
- `DELETE /api/me/build-templates?id=...`

所有接口都通过 `Authorization: Bearer <token>` 鉴权。`POST` 按 `user_id + type + rawString` 去重更新，返回服务端模板 `id`，并保留前端本地 `clientId` 以便合并。其他账号删除同一模板 id 会返回 not found。

小程序端仍先写本地 `wow_build_templates_v1`，然后尝试同步到远端。`requestJson` 在明文 HTTP + auth 场景会拒绝发送 Bearer token 并走 fallback，因此开发 IP 调试不会泄露账号 token；体验版/正式版需要配置 HTTPS 合法域名才会启用账号同步。

## 数据健康接口

`GET /api/data/health` 是只读聚合接口，不主动触发外部同步。它汇总新闻发布门禁、Raider.IO 缓存、WebSim 赛季、WebSim 同步、社区模板、Stat Weights、Warcraft Logs credentials 和 Battle.net API 配置状态。

装备、宝石、附魔和变体属于 `Season Data Cache` 的核心读模型。每条可被前端或 SimC 链路消费的数据都应能追溯到 `sourceType`、`sourceStatus`、`seasonRevision`、`checkedAt`、`status` 和 `blockers`；缺少确定 `bonus_id/gem_id/enchant_id/crafted_stats` 等 SimC 字段时保持 `partial` 或 `blocked`，不得把展示候选标为可执行。

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
curl -fsS http://124.223.51.33/health
curl -fsS http://124.223.51.33/api/news/home
curl -fsS http://124.223.51.33/api/websim/bootstrap
```
