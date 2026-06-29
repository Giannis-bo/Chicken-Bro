# 后台门禁可视化管理系统一期设计

## 目标

一期建设完整后台管理系统的信息架构，但只实现“门禁治理台 + 验证 gap 诊断闭环”。后台用于看清新闻、天赋、装备三类相对静态内容从上游、规则审计、证据链、入库到前端/SimC 消费的状态。

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
- 验证 gap 诊断队列
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
- 装备：社区装备模板、装备变体、default gear/template evidence audit 的 health 摘要。

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

## 实施状态 / 2026-06-29

- 已实现 `/admin/gates` 管理页和 summary、records、record detail、queue、diagnoses API。
- 已新增 `admin_gate_diagnoses` 和 `ops_audit_logs`，并通过 `admin_gate_diagnostics_v1` migration 标记初始化。
- 左侧“新闻资讯 / 天赋树 / 装备库”导航已绑定点击事件，并按 `domain=news|talents|gear` 过滤记录；“总览”清空 domain 过滤。
- 已热部署到 `http://124.223.51.33/admin/gates`；线上 smoke 验证页面包含导航绑定、`domain=gear` records 返回、无 token 返回 `401`、`/health` 正常。
- 本地回归：`python3 -m unittest tests.news_backend_test`。

## 验收

- 未授权访问 `/api/admin/gates/*` 返回 `401`。
- records / queue / summary 只读，不触发 sync、fetch、LLM 或 SimC。
- 诊断写入后，原始记录状态不变。
- 诊断写入同时产生 audit log。
- 原始数据摘要脱敏，不泄露 token、完整正文、完整 profile 或 raw request。
- 底层记录重验通过后，诊断自动显示为 resolved。
