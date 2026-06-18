# PVE 职业天梯 UI 与数据契约

## 目标

PVE 专区的「职业天梯」模块使用移动端排行页承载专精强度概览。页面先按角色展示 Archon 风格的 tier board，再在同页展示与当前角色分组对齐的 Warcraft Logs 移动端统计图。

## 小程序交互

- 顶部保留 PVE 详情页黑底和赛季信息。
- `DPS / 坦克 / 治疗` 使用三段式角色切换。
- Archon 概览按 `S / A / B / C` 分层，每个专精使用职业色胶囊、图标、M+ Score 和样本数。
- 默认选中当前角色第一名；点击任意专精后，Archon 胶囊和 WCL 统计图行同步高亮。
- WCL 面板从 Web 端宽表转成移动端 chart table：顶部保留 `Points / All Dungeons / All Keystone Levels / All Percentiles / 2 Weeks / Current Standings / Normalized Scores` 的连续筛选条；每个专精一行展示职业色名称、P50/P75/P95 range、median marker、score dot、`Score`、`Max`、`Parses`。
- WCL 行按 Archon 当前角色分组派生，DPS / 坦克 / 治疗切换时同步替换明细列表，避免 WCL 分类和强度概览脱节。
- 来源校验区展示 Archon 与 WCL 的域名、状态、检查时间、分析窗口和样本量。

## 数据契约

`GET /api/pve/module?key=specLadder` 保留旧的 `items` 兼容字段，并新增：

- `roles`: `dps / tank / healer` 三个角色入口，包含数量、更新时间和默认激活状态。
- `defaultRole`: 默认角色，当前为 `dps`。
- `selectedSpecId`: 默认选中专精。
- `archonTierSummary`: 按角色分组的 Archon tier board。
- `wclDetailsBySpec`: 以 `specId` 为 key 的 WCL 明细。
- `sourceChecks`: Archon 和 Warcraft Logs 的来源校验状态。

后续真实 API 接入时可扩展查询参数：

```text
GET /api/pve/module?key=specLadder&role=dps&dungeon=all&keyRange=high&window=14d
```

## 来源规则

- 强度概览只接受 `archon.gg` 来源。
- 明细数值只接受 `warcraftlogs.com` 来源。
- `verified` 表示来源域名、窗口和样本字段完整；API 未接入前数据仍是 fixture，可被采集层替换。
- `blocked` 或 `stale` 状态不得展示强结论，只能展示来源不足或数据过期。
- Archon/WCL 数据在正式采集前不得被文案描述为已经验证的真实赛季结论；当前小程序只把 UI 框架、字段契约和来源状态机制落地。

## 验证

- `tests/pve-page.test.js` 覆盖三角色数据、Archon tier、WCL 明细、来源域名和小程序 UI 标记。
- 小屏布局通过移动端 chart table、两行筛选条、固定宽度 spec 列和可收缩 range 区适配，避免 Web 宽表撑破页面。
