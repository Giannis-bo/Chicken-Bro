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
| `websim_gear_sources` | 当前赛季掉落来源、套装来源、观测来源引用、governed 制造业来源 | 只保存 accepted current source；复用旧副本的 `journal_candidate` / `excluded_legacy_bucket` 不应进入正式候选；制造业必须是带 `sourceRefs` / `trackEvidence` 的 `source_type='crafted'` |
| `websim_gear_variants` | 玩家可见的装备变体：`itemId + slot + sourceType + difficultyKey + itemLevel`，制造业还包含 `crafted_stats` 维度 | `verified` 必须有 DB 内的 `itemStats` 或 `statSummary`；缺属性只能是 `partial` / `blocked`；制造业不得把 `itemId + ilevel` 或 Battle.net preview stats 包装成 verified |
| `websim_item_sets` / `websim_item_set_items` | 套装与套装部位 membership | membership 不是装等变体；套装部位仍必须写入 `websim_gear_variants` |
| `websim_gear_mod_options` | 宝石、附魔、制造业属性搭配等可选项 | 只保存真实插槽、可附魔部位或明确服务端数据支持的选项；`crafted_stats` 缺 SimC 映射或缺目标装备属性时不能进入可应用 UI |
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

## 制造业入库逻辑

制造业装备作为一等 `crafted` catalog source 入库，不恢复旧的 ungoverned crafted seed。旧环境变量 `WOW_WEBSIM_CRAFTED_GEAR_SEED` 仍必须被忽略；同步普通装备目录时只允许保留 governed crafted rows，非 governed 旧行要被清理。

制造业受控输入当前有三类：

- 首选 `python3 server/crafted_gear_backfill.py --from-metadata --db server/data/wow_news.sqlite3`，从既有 `websim_items.payload_json` 中带 `modified_crafting_stat` / `modifiedCraftingStat` 的 Battle.net metadata 生成 catalog item。
- 已有 SimC profile preset 中带 `crafted_stats` 的装备行可作为 profile evidence，用于补充 `sourceRefs`、已观测 `bonus_id`、已观测装等和已观测属性搭配。
- 极少数 metadata 无法自动识别、但已经人工确认属于本赛季制造业目录的物品，只能放入本地 curated allowlist；每条必须带 itemId、slot、证据类型和是否支持虚空晋升。当前盾牌 `251105 / 破法者之盾` 属于这类受控补录。

制造业轨道使用内部 key，公开展示仍复用玩家熟悉标签：

| 展示 | 内部 `difficulty_key` | 公开 `difficultyKey` | 装等 | 生成条件 |
| --- | --- | --- | --- | --- |
| 神话 | `crafted_myth` | `myth` | 285 | 带制造业 metadata 或受控补录的装备 |
| 虚空晋升 | `crafted_void_upgrade` | `void_upgrade` | 295 | 仅武器、盾牌，或有 profile evidence 明确支持虚空晋升的制造物品 |

制造业不能机械套普通装备轨道，也不能生成普通 `289` / `298`。非武器、非盾牌或无证据装备不得生成 `295`。如果未来赛季规则新增 `crafted_champion` / `crafted_hero` 等轨道，必须先补证据和装等表，再开放入库。

制造业属性搭配按 SimC `crafted_stats` 校验，当前标准组合是：

| `crafted_stats` | 展示 |
| --- | --- |
| `32/36` | 暴击 + 急速 |
| `32/40` | 暴击 + 全能 |
| `32/49` | 暴击 + 精通 |
| `36/40` | 急速 + 全能 |
| `36/49` | 急速 + 精通 |
| `40/49` | 全能 + 精通 |

`websim_gear_variants` 必须按 `item_id + slot + source_type='crafted' + difficulty_key + item_level + crafted_stats` 写入。每个组合都要走 SimC JSON gear output 解析链路，profile 行包含 `id`、`ilevel`、`crafted_stats` 以及必要的 `bonus_id`。只有 SimC 返回目标装备 `itemStats` / `statSummary` 时才写 `verified`，并在 payload 中保留 `statSource='simulationcraft'`、`derivedVariantSource='simulationcraft_crafted_item_probe'`、`craftedStatKey`、`craftedStatLabel` 和 `crafted_stats`；否则写 `partial` 并记录 blocker。

回填同一制造物品前必须先删除该 `item_id` 下旧的 `source_type='crafted'` variants，避免 profile slot 和 metadata slot 归一化差异留下 stale 行。compact gear payload 对制造业要把内部多条 `crafted_stats` 变体折叠成“装等轨道 `variants[]` + 当前轨道下 `craftedStatOptions[]`”。如果同一 item 同时存在 dungeon / crafted 等来源，制造业视图只能公开 crafted variants，不能把普通 `263 / 276 / 289` 轨道混入属性搭配 UI。

## 入库流程

1. 更新当前赛季 allowlist：M+、团本、套装 ID、赛季 revision。
2. 同步 Battle.net Journal 和 item set。Journal 行只作为原始输入，复用旧副本必须先经过 `source_reference` / `source_discrepancy` 校验。
3. 执行 `sync_websim_gear_catalog`。正式 `websim_gear_sources` 只保留 active accepted source。
4. 对大秘境和团本逐实例执行官方装等探针回填，写入 `websim_gear_variants`。
5. 对当前职业套装执行套装装等探针回填。套装不允许只保留最高装等，至少应有普通三档；有证据的部位再补 `void_upgrade`。
6. 执行 observed profile 属性同步。Raider.IO / WCL 只提供观测配置和校验引用，属性必须来自 SimC JSON gear output 或已验证同装等 sibling。
7. 如果本次更新包含制造业，执行 `crafted_gear_backfill.py --from-metadata` 或受控 `--seed-json`，并确认 generated item、track、`crafted_stats` 组合全部来自证据。
8. 构建 `gearCatalog` sync state，并审计 health。
9. 发布前跑全职业 / 全专精 compact gear smoke，确认前端读模型可完整读出等级和属性。

## 发布前硬性审计

每次大版本、赛季或大批装备更新前，至少确认：

- `verified` 官方装等变体缺属性数为 `0`。
- `verified` dungeon / raid / tier_set / observed_profile 变体缺属性数为 `0`。
- 已存在正装等变体的 item，不再保留 `needs-variant` 占位。
- 复用旧副本的 `journal_candidate` / `excluded_legacy_bucket` 不进入 `websim_gear_sources`。
- 旧展示标签残留为 `0`，例如 `虚空强化` 必须统一为 `虚空晋升`。
- 当前职业套装部位至少三档装等覆盖；`partial` / `blocked` 为 `0`，除非发布报告明确列出原因和补齐路径。
- 制造业 `source_type='crafted'` item 覆盖符合本次受控目录，verified variant 必须都有 `statSource='simulationcraft'` 和目标装备属性；普通制造装备不出现 `289` / `298`，只有明确支持虚空晋升的武器或盾牌出现 `295`。
- 制造业六类 `crafted_stats` option 在 `websim_gear_mod_options` 有覆盖，compact payload 中每个制造轨道都有 `craftedStatOptions`，且未选中 verified 属性搭配时前端不能应用或保存。
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
- 制造业先跑 `crafted_gear_backfill.py --from-metadata --dry-run` 审计 item / slot / track / crafted stat option 计数，再写库；写库后用 SQL 确认 crafted 装等只包含 `285` / `295`，`partial` 为预期值。
- 发布前保留 DB 备份路径、入库命令、health 摘要、compact smoke 摘要。
- 发现 SimC 不支持的新副本或新 item document 时，不用线上请求兜底计算；保持 `partial` / `blocked` 并上报。
