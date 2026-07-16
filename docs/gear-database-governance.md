# 装备自建数据库治理标准

> 适用范围：职业详情页装备模拟、WebSim gear API、装备来源与变体健康检查。12.1 大量装备更新时，按本文作为入库、审计、发布和问题上报标准。
> 全链路手册：装备模拟从上游 API 到校验、审计、入库、全职业专精适配、前端展示、serializer、发布和回滚，按 [装备模拟全链路 Runbook](gear-simulation-full-chain-runbook.md) 执行。
> 当前运行时：`WOW_DATABASE_RUNTIME=postgres_only` 下，装备 / 天赋 / season read model 必须从 PostgreSQL cache store 读取；SQLite 只作为历史备份、迁移源或离线审计输入，不作为 fallback。

## 目标

- 前端展示的装备明细、装等分级和属性都必须来自数据库读模型。
- 线上请求不能为了展示再临时计算装备属性；SimC / Battle.net / Raider.IO / WCL 等外层服务只负责入库前的数据生产、校验和对账。
- DB 可以保存 `partial` / `blocked` 数据，但必须带 blocker，并在 health、发布报告或维护结论里明确告知 owner。线上可放心使用的目标是玩家可见装备明细全部为 `verified`。

## 核心表职责

| 表 | 职责 | 可信边界 |
| --- | --- | --- |
| `websim_items` | 物品 canonical 元数据、中文名、图标、槽位、护甲/武器类型、preview payload | 只能做元数据和低等级 preview 参考，不能伪装成当前实例属性 |
| `websim_gear_sources` | 当前赛季掉落来源、套装来源、观测来源引用、governed 制造业来源 | 只保存 accepted current source；复用旧副本的 `journal_candidate` / `excluded_legacy_bucket` 不应进入正式候选；制造业必须是带 `sourceRefs` / `trackEvidence` 的 `source_type='crafted'` |
| `websim_gear_variants` | 玩家可见的装备变体：`itemId + slot + sourceType + difficultyKey + itemLevel`；普通可选属性制造业还包含 `crafted_stats` 维度；自带美化固定属性制造业允许无 `crafted_stats`，但必须有专用 SimC 探针证据 | `verified` 必须有 DB 内的 `itemStats` 或 `statSummary`；缺属性只能是 `partial` / `blocked`；制造业不得把 Battle.net preview stats 包装成 verified，固定属性自带美化制造业也必须由 SimC JSON 返回目标装备属性 |
| `websim_item_sets` / `websim_item_set_items` | 套装与套装部位 membership | membership 不是装等变体；套装部位仍必须写入 `websim_gear_variants` |
| `websim_gear_mod_options` | 宝石、附魔、制造业属性搭配等可选项 | 只保存真实插槽、可附魔部位或明确服务端数据支持的选项；`crafted_stats` 缺 SimC 映射或缺目标装备属性时不能进入可应用 UI |
| `websim_loot` / `websim_instances` / `websim_encounters` | Battle.net Journal 原始缓存 | 可作为同步输入，不直接等于玩家可见 accepted gear source |
| `websim_sync_state` | catalog 健康、覆盖率、blocker 汇总 | 发布和巡检必须读取此表或 `/api/data/health` |

## 变体契约

每条玩家可见装备变体至少应具备：

- `item_id`、`slot`、`source_type`、`difficulty_key`、`item_level`。
- `status`：`verified`、`partial` 或 `blocked`。
- `payload_json.itemStats` 或 `payload_json.statSummary`。没有属性时不得是 `verified`。
- `payload_json.derivedVariantSource`：官方装等探针写 `simulationcraft_item_level_probe`；普通可选属性制造业写 `simulationcraft_crafted_item_probe`；自带美化固定属性制造业写 `simulationcraft_preembellished_item_probe`。
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

## 后台门禁装备库口径

后台门禁治理台的 `装备库` 主视图是 `/api/websim/gear` 小程序可展示读模型的治理镜像，不是 `websim_gear_variants` 原始行浏览器。owner 在主表看到的可见性必须与玩家实际能在小程序候选中看到的装备一致。

- 主表按 `itemId + slot` 聚合变体，并选择 verified / SimC-ready 的代表变体作为装备状态、可见性和 block 文案来源。
- PostgreSQL runtime store 必须先按 DB 条件读取完整候选集合，再做副本、装备名、分类和可见性筛选；不能先按最近更新时间截断一批变体再在内存筛选。
- 同一装备同时存在 `needs-variant`、`partial` 或 blocker 占位变体和 verified 可用变体时，主表以 verified 可用变体为准；占位变体只进入计数、诊断或后续明细视图。
- 掉落来源列展示 owner 需要的去重装等轨道，例如 `虚空晋升 298`、`神话 289`、`英雄 276`、`勇士 263`；同一 item level 下多条 `observed_profile` 技术变体只折叠为一条 `ilvl xxx` 或对应人类可读轨道。
- 真正没有 verified / SimC-ready 变体的装备仍保持 fail-closed，显示 blocked 或不可见，并保留具体 blocker。

## 制造业入库逻辑

制造业装备作为一等 `crafted` catalog source 入库，不恢复旧的 ungoverned crafted seed。旧环境变量 `WOW_WEBSIM_CRAFTED_GEAR_SEED` 仍必须被忽略；同步普通装备目录时只允许保留 governed crafted rows，非 governed 旧行要被清理。

制造业受控输入当前有三类：

- 首选 PG-native 同步/迁移链路从 `cache.websim_items.payload_json` 中带 `modified_crafting_stat` / `modifiedCraftingStat` 的 Battle.net metadata 生成 catalog item。历史命令 `WOW_SQLITE_MIGRATION_SOURCE=1 python3 server/crafted_gear_backfill.py --from-metadata --db server/data/wow_news.sqlite3` 只能用于离线迁移源或本地审计，不得作为线上 runtime job。
- 已有 SimC profile preset 中带 `crafted_stats` 的装备行可作为 profile evidence，用于补充 `sourceRefs`、已观测 `bonus_id`、已观测装等和已观测属性搭配。
- 极少数 metadata 无法自动识别、但已经人工确认属于本赛季制造业目录的物品，只能放入本地 curated allowlist；每条必须带 itemId、slot、证据类型和是否支持虚空晋升。当前 Midnight 普通 PVE 制造业 curated allowlist 为空；`251105 / 破法者之盾` 已确认为副本掉落，不能作为制造业补录，真实制造盾牌是 `237831 / 破法者的责难`。

当前 Midnight 普通 PVE 制造业目录必须按 `server/crafted_gear_backfill.py` 中的 governed allowlist 入库：

- 锻造：`237828-237850`。
- 裁缝：`239648-239656`。
- 珠宝：`240949`、`240950`。
- 制皮：`244569-244584`。
- 铭文：`245769`、`245770`、`245771`、`265337`。

以下 itemId 即使在 metadata、profile preset 或 observed 样本中出现，也不能生成 `source_type='crafted'` source 或普通制造业 `crafted_stats` 变体：`228843`、`239678`、`240951`、`240952`、`244764`、`251105`、`260370`、`260371`、`260372`、`260373`、`260374`、`260375`、`260377`。`244774 / 以太流明践踏靴` 是工程单副属性制造装备，当前两副属性 `crafted_stats` 链路不支持，必须保持 blocked/unsupported，不能用假双属性选项入库。

制造业轨道使用内部 key，公开展示仍复用玩家熟悉标签：

| 展示 | 内部 `difficulty_key` | 公开 `difficultyKey` | 装等 | 生成条件 |
| --- | --- | --- | --- | --- |
| 神话 | `crafted_myth` | `myth` | 285 | 带制造业 metadata 或受控补录的装备 |
| 虚空晋升 | `crafted_void_upgrade` | `void_upgrade` | 295 | 仅武器、盾牌，或有 profile evidence 明确支持虚空晋升的制造物品 |

制造业不能机械套普通装备轨道，也不能生成普通 `289` / `298`。非武器、非盾牌或无证据装备不得生成 `295`。如果未来赛季规则新增 `crafted_champion` / `crafted_hero` 等轨道，必须先补证据和装等表，再开放入库。

### 普通可选属性制造装备

普通可选属性制造装备按 SimC `crafted_stats` 校验，当前标准组合是：

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

### 自带美化固定属性制造装备

自带美化固定属性制造装备不能套用“必须选择 `crafted_stats`”的普通制造业规则，也不能把 Optional Reagent 美化当成该装备自带词缀。它只有同时满足以下条件时，才能进入 `source_type='crafted'` 并作为可应用候选：

- `websim_items.payload_json` 保留 Battle.net item metadata，且 `preview_item.limit_category`、`limitCategory` 或等价字段能识别为 Unique-Equipped Embellished / `装备唯一：美化（2）`。
- `websim_gear_sources` 有 governed crafted source，例如 `crafted-governed-<itemId>`，并在 payload 里记录 `sourceRefs`、`trackEvidence` 或人工确认来源；Method / Wowhead / guide 只能作为筛选和交叉参考，不能替代 Battle.net metadata 的最终写库门禁。
- `websim_gear_variants` 使用固定属性探针，`derivedVariantSource='simulationcraft_preembellished_item_probe'`、`source_type='crafted'`、`simcIlevelOnly=true`，且 SimC JSON gear output 返回目标装备的 `itemStats` / `statSummary` 后才写 `verified`。
- 标准字段必须一路保留：`hasBuiltInEmbellishment=true`、`builtInEmbellishmentLabel='美化'`、`embellishmentSource='built_in'`。如果暂时没有精确 SimC embellishment token，不得伪造 `embellishment=...`，只用于 UI 标记和 2 件上限计数。

固定属性自带美化制造业的 variant key 应显式区分普通 `crafted_stats` 变体，例如 `crafted-preembellished-itemlevel-<itemId>-<slot>-<difficulty>-<ilevel>`。compact payload 中 `craftedStatOptions=[]` 是正确状态，但必须有 verified `variants[]`、`simcReady=true`、自带美化字段和 crafted source；前端看到这类装备时直接允许应用已验证轨道，不要求玩家再选属性搭配。

这类装备选择后会自动计入 `美化 x/2`，该槽位不能再展示独立美化可选项；如果用户切换装备导致旧的独立美化配置不兼容，前端必须裁剪 `enhancementBySlot` 并重新计算属性概览。Optional Reagent 美化仍只走 `websim_gear_mod_options`，和自带美化字段分开建模。

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

## 周期性装备更新执行手册

后续每次赛季、热修或制造业清单更新，都按“筛选 -> 只读审计 -> 分类入库 -> 读取验收 -> 发布记录”的顺序执行。任何一步出现缺证据或 blocker，都保持 `partial` / `blocked` 并上报，不用前端或线上请求临时兜底。

### 0. 变更分类与筛选

- 先确认本次更新属于哪一类：M+ / 团本 journal loot、职业套装、普通可选属性制造业、自带美化固定属性制造业、宝石 / 附魔 / Optional Reagent，或以上多类组合。
- 更新赛季 allowlist、实例 ID、套装 ID、制造业目录和装等轨道时，必须记录 revision、检查日期和来源。旧赛季条目不能混入 Midnight 当前赛季筛选结果。
- guide、社区表格、Method / Wowhead 文章只能用于发现候选；正式写库门禁仍是 Battle.net metadata、Journal / item set、SimC JSON gear output、Wago DB2 或项目内 curated allowlist 中明确声明的证据。
- 不允许在前端按装备名、itemId 或文案硬编码分类。筛选、徽标、计数和可应用状态都必须来自后端结构化字段。

### 1. 写库前只读审计

- 先备份实际写入的 SQLite / PostgreSQL target，并记录备份路径；没有备份不写库。
- 只读查询当前 `websim_items`、`websim_gear_sources`、`websim_gear_variants`、`websim_gear_mod_options` 的总量、目标 item 命中情况、已有 source / variant 状态和 stale 行。
- 审计重点包括：缺 metadata、sourceType 污染、旧 `needs-variant`、旧赛季 source、旧展示标签、verified 缺属性、crafted 轨道异常装等、`crafted_stats` 应有未有或不该有却残留。
- 对新增候选先生成 dry-run 差异：新增 item 数、source 数、variant 数、mod option 数、verified / partial / blocked 数、top blockers。dry-run 中无法解释的行不能进入正式写库。

### 2. 分类入库规则

- M+ / 团本 / 套装：Battle.net Journal 或 item set 只负责来源与 membership，玩家可见装等属性必须通过 `simulationcraft_item_level_probe` 或同等确定性 SimC 链路写入 `websim_gear_variants`。
- 普通可选属性制造业：从 `modified_crafting_stat` / `modifiedCraftingStat` metadata、SimC preset `crafted_stats` 或 curated allowlist 生成 governed crafted source；每个 `item + track + crafted_stats` 组合都必须由 `simulationcraft_crafted_item_probe` 验证，compact 中每条可选轨道应有 6 个标准 `craftedStatOptions`。
- 自带美化固定属性制造业：必须有 Battle.net 自带美化标记和 governed crafted source；每个 `item + track` 由 `simulationcraft_preembellished_item_probe` 写 verified 固定属性 variant，`craftedStatOptions=[]`，但保留 `hasBuiltInEmbellishment` 等字段。
- 宝石 / 附魔 / Optional Reagent：写入 `websim_gear_mod_options`，display label、状态、证据来源都由后端给出；不能从前端把 `gem_id`、`enchant_id` 或 `embellishment` key 翻译成玩家文案。

### 3. 读取链路验收

- 后端读链路必须覆盖 `get_websim_gear_catalog_items`、`active_catalog_sources_for_replacement`、`collapse_catalog_variants_for_display`、`catalog_variant_usable_for_replacement`、`compact_crafted_gear_variants`、`normalize_gear_item` 和 compact candidate serializer。
- compact payload 需要保留 source filter 计数、`sourceTypes`、verified 轨道、`simcReady`、`statSummary`、`craftedStatOptions` 或固定属性例外、自带美化字段、mod option display 字段。
- 前端只消费 compact payload。替换装备 sheet 的“全部 / 大秘境 / 团本 / 套装 / 制造业”计数、候选徽标、已选装备卡片、属性概览和强化配置 sheet 都要来自同一份结构化数据。
- 选择带自带美化的装备后，属性概览必须同步变更 `美化 x/2`；超过 2 件时显示 blocker，不允许保存为可用模板；切换掉装备后计数回落并重新开放可用的独立美化选项。

### 4. 发布与回滚记录

- 发布记录至少包含：备份路径、执行命令、写入数量、verified / partial / blocked 统计、top blockers、抽样职业专精、API smoke URL、前端行为验收结果。
- `server/deploy_lighthouse.sh` 默认不应覆盖生产 `server/data`；任何网络拉取、依赖安装、下载数据文件或生产远端变更，都必须先经过 owner 明确授权。
- 如果需要回滚生产 DB，先停止服务，再用备份文件恢复、修正 owner/group、重启服务并重新跑 `/health`、`/api/data/health` 和 compact payload smoke。回滚是生产操作，必须单独说明原因和影响面。
- 文档与 roadmap 要在同一轮记录本次更新的证据链，避免下次周期性更新只能从聊天记录找上下文。

## 发布前硬性审计

每次大版本、赛季或大批装备更新前，至少确认：

- `verified` 官方装等变体缺属性数为 `0`。
- `verified` dungeon / raid / tier_set / observed_profile 变体缺属性数为 `0`。
- 已存在正装等变体的 item，不再保留 `needs-variant` 占位。
- 复用旧副本的 `journal_candidate` / `excluded_legacy_bucket` 不进入 `websim_gear_sources`。
- 旧展示标签残留为 `0`，例如 `虚空强化` 必须统一为 `虚空晋升`。
- 当前职业套装部位至少三档装等覆盖；`partial` / `blocked` 为 `0`，除非发布报告明确列出原因和补齐路径。
- 制造业 `source_type='crafted'` item 覆盖符合本次受控目录，verified variant 必须都有 `statSource='simulationcraft'` 和目标装备属性；普通制造装备不出现 `289` / `298`，只有明确支持虚空晋升的武器或盾牌出现 `295`。
- 普通可选属性制造业六类 `crafted_stats` option 在 `websim_gear_mod_options` 有覆盖，compact payload 中每个普通制造轨道都有 `craftedStatOptions`，且未选中 verified 属性搭配时前端不能应用或保存。
- 自带美化固定属性制造业的 `craftedStatOptions=[]` 只能在 `derivedVariantSource='simulationcraft_preembellished_item_probe'`、verified 固定属性轨道和 `hasBuiltInEmbellishment=true` 同时存在时接受；候选行、已选装备卡片和属性概览必须显示并计入“美化”。
- source filter 计数、候选徽标、强化配置可用项都来自后端结构化字段，前端没有新增按装备名或 itemId 判断的特殊逻辑。
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
- 制造业先按类别拆开 dry-run：普通可选属性制造业跑 `crafted_gear_backfill.py --from-metadata --dry-run` 审计 item / slot / track / crafted stat option 计数；自带美化固定属性制造业先审计 Battle.net 自带美化 metadata、governed source 和 fixed-stat SimC probe 结果。写库后用 SQL 确认 crafted 装等只包含当前赛季允许轨道，`partial` 为预期值。
- 发布前保留 DB 备份路径、入库命令、health 摘要、compact smoke 摘要。
- 发现 SimC 不支持的新副本或新 item document 时，不用线上请求兜底计算；保持 `partial` / `blocked` 并上报。
