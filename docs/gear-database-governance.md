# 装备自建数据库治理标准

> 适用范围：职业详情页装备模拟、WebSim gear API、装备来源与变体健康检查。12.1 大量装备更新时，按本文作为入库、审计、发布和问题上报标准。

## 目标

- 前端展示的装备明细、装等分级和属性都必须来自数据库读模型。
- 线上请求不能为了展示再临时计算装备属性；SimC / Battle.net / Raider.IO / WCL 等外层服务只负责入库前的数据生产、校验和对账。
- DB 可以保存 `partial` / `blocked` 数据，但必须带 blocker，并在 health、发布报告或维护结论里明确告知 owner。线上可放心使用的目标是玩家可见装备明细全部为 `verified`。

## 核心表职责

| 表 | 职责 | 可信边界 |
| --- | --- | --- |
| `websim_items` | 物品 canonical 元数据、中文名、图标、槽位、护甲/武器类型、preview payload | 只能做元数据和低等级 preview 参考，不能伪装成当前实例属性 |
| `websim_gear_sources` | 当前赛季掉落来源、套装来源、观测来源引用 | 只保存 accepted current source；复用旧副本的 `journal_candidate` / `excluded_legacy_bucket` 不应进入正式候选 |
| `websim_gear_variants` | 玩家可见的装备变体：`itemId + slot + sourceType + difficultyKey + itemLevel` | `verified` 必须有 DB 内的 `itemStats` 或 `statSummary`；缺属性只能是 `partial` / `blocked` |
| `websim_item_sets` / `websim_item_set_items` | 套装与套装部位 membership | membership 不是装等变体；套装部位仍必须写入 `websim_gear_variants` |
| `websim_gear_mod_options` | 宝石、附魔等可选项 | 只保存真实插槽、可附魔部位或明确服务端数据支持的选项 |
| `websim_loot` / `websim_instances` / `websim_encounters` | Battle.net Journal 原始缓存 | 可作为同步输入，不直接等于玩家可见 accepted gear source |
| `websim_sync_state` | catalog 健康、覆盖率、blocker 汇总 | 发布和巡检必须读取此表或 `/api/data/health` |

## 变体契约

每条玩家可见装备变体至少应具备：

- `item_id`、`slot`、`source_type`、`difficulty_key`、`item_level`。
- `status`：`verified`、`partial` 或 `blocked`。
- `payload_json.itemStats` 或 `payload_json.statSummary`。没有属性时不得是 `verified`。
- `payload_json.derivedVariantSource`：官方装等探针写 `simulationcraft_item_level_probe`。
- `payload_json.statSource`：当前装备属性以 `simulationcraft` 为主。
- `blockers_json`：`partial` / `blocked` 必须写具体原因。

当前赛季普通轨道是：

| 展示 | `difficulty_key` | 装等 |
| --- | --- | --- |
| 勇士 | `champion` | 263 |
| 英雄 | `hero` | 276 |
| 神话 | `myth` | 289 |
| 虚空晋升 | `void_upgrade` | 298 |

`298` 不是普通神话满级。只有存在赛季规则或明确证据的武器、饰品、孢陨幽境特殊掉落、套装特殊部位，才能写 `void_upgrade`。12.1 开季时必须先更新轨道配置和证据规则，再跑入库。

## 入库流程

1. 更新当前赛季 allowlist：M+、团本、套装 ID、赛季 revision。
2. 同步 Battle.net Journal 和 item set。Journal 行只作为原始输入，复用旧副本必须先经过 `source_reference` / `source_discrepancy` 校验。
3. 执行 `sync_websim_gear_catalog`。正式 `websim_gear_sources` 只保留 active accepted source。
4. 对大秘境和团本逐实例执行官方装等探针回填，写入 `websim_gear_variants`。
5. 对当前职业套装执行套装装等探针回填。套装不允许只保留最高装等，至少应有普通三档；有证据的部位再补 `void_upgrade`。
6. 执行 observed profile 属性同步。Raider.IO / WCL 只提供观测配置和校验引用，属性必须来自 SimC JSON gear output 或已验证同装等 sibling。
7. 构建 `gearCatalog` sync state，并审计 health。
8. 发布前跑全职业 / 全专精 compact gear smoke，确认前端读模型可完整读出等级和属性。

## 发布前硬性审计

每次大版本、赛季或大批装备更新前，至少确认：

- `verified` 官方装等变体缺属性数为 `0`。
- `verified` dungeon / raid / tier_set / observed_profile 变体缺属性数为 `0`。
- 已存在正装等变体的 item，不再保留 `needs-variant` 占位。
- 复用旧副本的 `journal_candidate` / `excluded_legacy_bucket` 不进入 `websim_gear_sources`。
- 旧展示标签残留为 `0`，例如 `虚空强化` 必须统一为 `虚空晋升`。
- 当前职业套装部位至少三档装等覆盖；`partial` / `blocked` 为 `0`，除非发布报告明确列出原因和补齐路径。
- `/api/data/health` 的 `gear_catalog` blocker 都能解释到具体 source / item / variant。
- 当前 `WOW_CLASSES` 全职业 / 专精矩阵 `/api/websim/gear?compact=1` smoke 无请求错误、无 incompatible 候选回流、无玩家可见 verified 缺属性。

## partial / blocked 上报标准

如果出现非 `verified`，必须报告：

- 副本或套装名称。
- `itemId`、物品名、槽位。
- 变体：`difficultyKey`、装等、sourceType。
- blocker 原文。
- 是否会进入前端玩家可见候选。
- 补齐路径：SimC 支持缺口、Battle.net source drift、复用旧副本 reference 缺口、observed profile 缺 SimC JSON，或本地同步 bug。

只有这些信息都明确后，才能判断是接受为已知 blocker、继续回填，还是阻断发布。

## 12.1 操作清单

- 先更新赛季池和装等轨道，不沿用 12.0.5 的 263 / 276 / 289 / 298 假设。
- 先跑 dry-run 审计，确认 `websim_loot` 原始行和 accepted `websim_gear_sources` 行数差异。
- 每个副本单独回填、单独记录 verified / partial / blocker，避免一次大同步掩盖问题。
- 套装先确认 item set ID 和 5 件职业部位，再回填装等变体。
- 发布前保留 DB 备份路径、入库命令、health 摘要、compact smoke 摘要。
- 发现 SimC 不支持的新副本或新 item document 时，不用线上请求兜底计算；保持 `partial` / `blocked` 并上报。
