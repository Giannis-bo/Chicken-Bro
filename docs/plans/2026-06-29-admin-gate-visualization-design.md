# 后台门禁可视化管理系统一期设计

## 目标

一期建设完整后台管理系统的信息架构，但只实现“门禁治理台 + 验证 gap 诊断闭环”。后台用于看清新闻、天赋、装备库和装备模板这些相对静态内容从上游、规则审计、证据链、入库到前端/SimC 消费的状态。

核心产品规则：

- 系统门禁是消费事实。
- 人工判断是诊断事实。
- 人工诊断不得把 `blocked` / `partial` 改成 `verified`。
- 人工诊断不得让被系统阻断的数据直接进入前端强展示或 SimC 执行。
- 只有后续 sync、backfill、audit 或 serializer 重验通过后，数据才能自然进入可展示或可消费状态。

## 一期后台形态

入口：

- `GET /admin/gates`
- `GET /api/admin/gates/summary`
- `GET /api/admin/gates/records`
- `GET /api/admin/gates/records/{domain}:{targetType}:{targetId}`
- `GET /api/admin/gates/queue`
- `GET /api/admin/gates/diagnoses`
- `POST /api/admin/gates/diagnoses`

鉴权：

- 使用 `Authorization: Bearer <token>`。
- 优先读取 `WOW_ADMIN_TOKEN`。
- 为兼容现有 analytics admin，可回退到 `WOW_ANALYTICS_ADMIN_TOKEN`。

后台导航预留：

- 总览
- 新闻资讯
- 天赋树
- 装备库
- 装备模板
- 待诊断阻断项
- 诊断记录
- 系统状态

同步触发、回填触发、retry、发布/回滚、CMS、角色体系都不在一期实现。

## 数据视图

每条记录统一展示五段：

1. 上游原始数据摘要
2. 规则审计
3. 证据链
4. 入库状态
5. 前端/SimC 消费状态

原始数据只展示脱敏摘要。后台不展示完整新闻原文、完整 SimC profile、token、raw request 或用户私密内容。

一期覆盖：

- 新闻：discovery queue、public articles、refresh gate 状态。
- 天赋：完整天赋树覆盖、社区天赋模板。
- 装备库：全量 `gear_variant` 装备，展示装备名称、部位、掉落来源、状态、职业、小程序可见性和 Block 原因。
- 装备模板：`community_gear_template`，展示职业、状态、小程序是否可见、来源和 Blockers。
- Health 摘要：default gear/template evidence audit 和 data-health 模块状态。

## 验证 Gap 诊断

当 owner 判断“数据看起来没问题但系统卡住”时，不提供人工放行按钮，而是记录系统验证 gap。

支持的诊断类型：

- `system_gap_suspected`
- `evidence_missing`
- `rule_too_strict`
- `parser_or_mapping_bug`
- `stale_or_not_resynced`
- `source_conflict_needs_policy`

诊断写入：

- `admin_gate_diagnoses`
- `ops_audit_logs`

诊断不会写回原始记录，不会修改 `sourceStatus`、`status`、health component 或公开 API payload。

当底层记录经过后续修复并重验为可通过状态后，诊断记录在后台自动显示为 `resolved`，并从诊断队列移除。

## 状态解释

消费状态继续遵循系统门禁：

- `verified`：可支撑当前消费结论。
- `partial`：有证据但不能支撑强结论。
- `blocked`：不能进入强展示或执行链路。
- `missing_credentials`：外部凭证缺失。
- `pending_official_audit`：缺官方对账。
- `source_reference`：只能作为参考来源。

诊断队列严重级别按影响面解释：

- 阻断前端发布
- 阻断前端模板展示
- 阻断 SimC 或强结论
- 只影响诊断记录

## 总览布局调整 / 2026-06-30

总览页不再放置常驻右侧诊断队列。治理台页面采用“左导航 + 主工作区”的两栏结构：

- `总览` 只展示治理驾驶舱、状态计数和模块概览，不展示全量记录表。
- `新闻资讯` / `天赋树` / `装备库` 进入记录工作台，并按 domain 过滤 records。
- `待诊断阻断项` 独立承载原 queue 卡片和提交诊断表单。
- `诊断记录` 独立展示人工诊断历史。
- `系统状态` 独立展示 health / runtime 摘要。

后台页面中的系统状态码保持英文原值，但统一在旁边显示中文解释，例如 `verified（已验证）`、`blocked（已阻断）`、`missing_credentials（缺少凭据）`、`pending_official_audit（待官方校验）`、`source_reference（仅作参考）`。严重级别也显示中文含义，避免 owner 只看到内部枚举。模块概览使用 owner-facing 中文模块名和常见 blocker 中文解释，保留原始英文标题在 API `rawTitle` 字段中用于排查。

## 记录分类与筛选 / 2026-06-30

记录工作台不再所有模块共用同一个搜索栏。每个高频模块使用和表格展示字段一致的 key/value 筛选：

- `新闻资讯`：分类、状态、发布情况；分类包含正式服动态、测试服前瞻、职业强度变化，发布情况区分已发布和未发布。
- `天赋树`：职业、状态、小程序可见性；表格同步展示阻断原因和小程序端是否可见。
- `装备库`：掉落来源、职业、小程序可见性；只审计 `gear_variant` 全量装备。
- `装备模板`：职业、小程序是否可见；只审计 `community_gear_template`。

所有记录页默认每页 20 条，支持上一页、下一页和调整单页展示数量。分页只影响治理台展示，不改变底层 records / queue 的只读事实来源。

## 实施状态 / 2026-06-29

- 已实现 `/admin/gates` 管理页和 summary、records、record detail、queue、diagnoses API。
- 已新增 SQLite fallback `admin_gate_diagnoses` / `ops_audit_logs` 和 PG runtime `ops.admin_gate_diagnoses` / `ops.audit_logs`，分别通过 `admin_gate_diagnostics_v1` 和 `0010_admin_gate_diagnostics` 初始化。
- 左侧“新闻资讯 / 天赋树 / 装备库 / 装备模板”导航已绑定点击事件，并按 `domain=news|talents|gear|gear_templates` 过滤记录；“总览”清空 domain 过滤。
- 总览页已移除右侧常驻 queue，`待诊断阻断项` 作为独立主视图；页面状态文案统一中英双显。2026-06-30 线上 smoke 验证 `/admin/gates=200`、旧右栏 DOM 不存在、旧队列名不存在、新队列名和状态中文存在；浏览器截图确认总览页 `queueView` 为 `display=none`。后续调整已移除总览页全量记录区域，并把模块概览标题与常见 blocker 文案中文化；线上 smoke 验证 summary 模块标题为中文、WCL blocker 已中文化，浏览器截图确认总览页 `recordsView` 为 `display=none`。
- 记录工作台已完成新闻分类/发布状态、天赋职业/小程序可见性、装备库掉落来源/职业/小程序可见性，以及装备模板职业/小程序是否可见筛选；线上 smoke 验证 `gear_templates` 总数 65、死亡骑士 7、已可见 20、不可见 45。
- 已热部署到 `http://124.223.51.33/admin/gates`；线上 smoke 验证页面包含导航绑定、`domain=gear` records 返回、无 token 返回 `401`、`/health` 正常。
- 本地回归：`python3 -m unittest tests.news_backend_test`。

## 数据源统一 / 2026-06-30

- `WOW_DATABASE_RUNTIME=postgres_personal` 下，`records` / record detail / `queue` 已改为从 PostgreSQL runtime store 读取：新闻来自 `content.discovery_queue` / `content.articles`，天赋与装备来自 `cache.websim_*` 读模型。
- 人工诊断在 PG runtime 下写入 `ops.admin_gate_diagnoses`，审计复用 `ops.audit_logs`；SQLite `admin_gate_diagnoses` / `ops_audit_logs` 只作为无 PG runtime 时的 fallback。
- 该调整避免治理台展示 SQLite fallback 视角、而小程序线上消费 PG `wow_test` 视角的分叉。
- 已部署到云服务器：备份路径 `/opt/wow-mini-program/backups/admin-gate-data-source-20260630T025732Z/`，active `wow_test` 已应用 `0010_admin_gate_diagnostics.sql`，`wow-backend` 重启后为 `active`。线上 smoke 验证 public `/health`、`/admin/gates`、admin summary 401/200、gear records/detail `runtimeStore=postgres_cache`、queue schema，以及受控诊断写入、审计和清理。

## 验收

- 未授权访问 `/api/admin/gates/*` 返回 `401`。
- records / queue / summary 只读，不触发 sync、fetch、LLM 或 SimC。
- PG runtime 下 records / record detail / queue / diagnoses 与线上 content/cache/ops runtime store 保持同源，不回读 SQLite fallback。
- 诊断写入后，原始记录状态不变。
- 诊断写入同时产生 audit log。
- 原始数据摘要脱敏，不泄露 token、完整正文、完整 profile 或 raw request。
- 底层记录重验通过后，诊断自动显示为 resolved。
