# Midnight 制造业装备整库审计与生产修正记录

> 状态：已完成生产审计、定向修正、整库回填、热部署和线上 compact 验收。
> 日期：2026-06-25。
> 目的：确保 Midnight 当前赛季制造业装备库整体准确，不按单件装备打补丁。

## 结论

本轮把制造业装备拆成两条受控链路：

- 普通可选属性制造装备：54 件，全部来自当前赛季 PVE recipe allowlist，使用 6 组标准 `crafted_stats`，玩家可选属性。
- 自带美化固定属性制造装备：30 件，全部有 Battle.net `装备唯一：美化（2）` metadata 和固定属性 SimC probe，玩家不可再选该槽位独立美化。

生产当前应有 `source_type='crafted'` 装备来源 84 条，verified crafted variants 470 条，partial crafted variants 0 条。被误归类或当前链路不支持的 item 已从 crafted source/variant 中清除。

## 当前普通 PVE 制造业 allowlist

这批由 `server/crafted_gear_backfill.py` 中 `CURRENT_PVE_CRAFTED_METADATA_ITEMS` 控制。只有在这个 allowlist 中，且 metadata/SimC 证据可通过的物品，才允许由 `--from-metadata` 生成普通制造业来源和属性搭配。

| 专业 | itemId 范围 / 列表 | 说明 |
|---|---|---|
| 锻造 | `237828-237850` | 板甲、武器、盾牌；真实制造盾牌是 `237831 / 破法者的责难` |
| 裁缝 | `239648-239656` | 布甲普通制造装备 |
| 珠宝 | `240949`、`240950` | 普通制造戒指、项链；PvP competitor 首饰排除 |
| 制皮 | `244569-244584` | 皮甲、锁甲普通制造装备 |
| 铭文 | `245769`、`245770`、`245771`、`265337` | 副手、武器、弓 |

## 自带美化制造装备

自带美化装备继续沿用 `docs/plans/2026-06-25-midnight-preembellished-crafted-gear-ingestion.md` 中的 30 件清单。它们不进入普通双属性 `crafted_stats` 逻辑，而是写 fixed-stat crafted variant：

- `derivedVariantSource=simulationcraft_preembellished_item_probe`
- `simcIlevelOnly=true`
- `hasBuiltInEmbellishment=true`
- `builtInEmbellishmentLabel=美化`
- `embellishmentSource=built_in`

## 排除与 blocked 清单

以下 itemId 不能以制造业身份进入生产读模型：

| itemId | 处理 | 原因 |
|---|---|---|
| `228843` | 排除 | 旧团本 / 旧随机属性条目 |
| `239678` | 排除 | PvP competitor 条目 |
| `240951`、`240952` | 排除 | PvP competitor 首饰，不是当前 PVE 制造目录 |
| `244764` | 排除 | PvP competitor 条目 |
| `251105` | 排除 crafted，仅保留真实掉落来源 | `破法者之盾` 是副本掉落盾牌，不是制造业盾牌 |
| `260370-260375`、`260377` | 排除 crafted | Midnight 团本 BoE / random-stat observed 条目，不是制造业来源 |
| `244774` | blocked / unsupported | 工程单副属性制造装备；当前 UI 和 SimC backfill 只支持双副属性 `crafted_stats` |

`244774 / 以太流明践踏靴` 后续要单独做“单副属性制造装备”链路，不能临时用 6 组双属性 option 兜底。

## 生产操作记录

生产备份：

- `/opt/wow-mini-program/backups/wow_news-before-crafted-audit-fix-20260625T093130Z.sqlite3`

生产修正：

- 补齐 27 件普通制造装备 metadata，其中 25 件为缺失 metadata，`239650` 与 `244578` 为旧占位 metadata 刷新。
- 删除 14 个错误 / 不支持 item 的 crafted source 和 variants：`228843`、`239678`、`240951`、`240952`、`244764`、`251105`、`260370`、`260371`、`260372`、`260373`、`260374`、`260375`、`260377`、`244774`。
- 执行 `python3 server/crafted_gear_backfill.py --db /opt/wow-mini-program/server/data/wow_news.sqlite3 --from-metadata`。
- 热部署：`WOW_DEPLOY_SKIP_BOOTSTRAP=1 WOW_DEPLOY_START_ASYNC_SYNCS=0 ./server/deploy_lighthouse.sh`。

生产回填输出：

- 普通制造业 items：54。
- 普通制造业 tracks：`crafted_myth=54`、`crafted_void_upgrade=19`。
- 普通制造业 verified variants：438。
- 自带美化 fixed-stat crafted variants：32。
- 合计 crafted verified variants：470。
- 合计 crafted distinct sources：84。
- crafted partial variants：0。

## 线上验证

生产 SQL 审计结果：

- `craftedSources=84`
- `craftedDistinctItems=84`
- `craftedVariants=470`
- `craftedVerifiedVariants=470`
- `craftedPartialVariants=0`
- `badSources=0`
- `badVariants=0`

线上 health：

- `/health` 返回 `ok=true`。
- `/api/data/health` 中 `details.sourceCoverage.crafted=84`。
- `/api/data/health` 中 `details.modOptionCoverage.crafted_stats.optionCount=6`。
- `variantReadiness` 当前为 `verified=2386 / partial=294 / blocked=0 / total=2680`。`gear_catalog` 仍为全局 partial，blocker 来自既有 observed / metadata / season source 缺口，不是本轮制造业修正。

线上 compact 抽样：

- `hunter/marksmanship` 腰部制造业只返回 `244611 / 世界照护者的树皮腰扣` 和 `244581 / 远行者的战利品腰带`；`260375 / 怒雷腰带` 不再以 crafted 身份出现。
- `paladin/protection`、`shaman/elemental`、`warrior/protection` 的副手制造业返回 `237831 / 破法者的责难` 与自带美化 `244472 / 骑士指挥官的雄关`；`251105 / 破法者之盾` 只以 dungeon 来源出现。
- `mage/frost` 腰部返回 `239649 / 殉难者的裹腰`、`239664 / 奥纹束带`、`239663 / 阳炎腰带`。
- 抽样坏 ID 集合 `228843`、`239678`、`240951`、`240952`、`244764`、`251105`、`260370-260375`、`260377`、`244774` 没有任何一条以 `sourceTypes` 包含 `crafted` 的 compact 候选回流。

## 2026-06-26 独立美化映射复审

本轮在整库制造业来源审计之后，继续复审“制造业装备 + Optional Reagent 美化”的对应关系，重点修正副手槽位不能只按 `off_hand` 粗粒度判断的问题。

当前独立美化 catalog 为 11 个 Midnight optional reagent：

| 类型 | simc key | 当前适用范围 |
|---|---|---|
| 护甲 | `arcanoweave_lining`、`sunfire_silk_lining` | 护甲槽位；盾牌按 armor-like 处理，可展示；Held In Off-hand 不展示 |
| 通用装备 | `blessed_pango_charm`、`prismatic_focusing_iris`、`stabilizing_gemstone_bandolier` | 未自带美化的制造装备通用槽位，包括首饰、武器、盾牌和 Held In Off-hand |
| 武器 / 护甲 | `devouring_banding`、`primal_spore_binding` | 武器、护甲、盾牌、Held In Off-hand |
| 武器 / Held In Off-hand | `darkmoon_sigil_blood`、`darkmoon_sigil_hunt`、`darkmoon_sigil_rot`、`darkmoon_sigil_void` | 武器和 Held In Off-hand；盾牌不展示 |

证据链拆分如下：

- SimC：确认 11 个 key 是当前可序列化的 Midnight embellishment profile 字段。
- Wowhead：交叉确认每个 optional reagent 当前 tooltip 的适用范围。
- Method：只作为其明确列出的 Blessed Pango Charm、Devouring Banding、Primal Spore Binding 和四个 Darkmoon Sigil 的交叉证据，不再用 Method 页面缺失来否定 Wowhead/SimC 均可确认的条目。
- Battle.net metadata：用于区分 shield 与 Held In Off-hand、副手归一化、自带美化和装备本体中文展示。

生产刷新后再次抽样：

- `shaman/elemental`：`245769 / 艾林哈籁灯笼 / Held In Off-hand` 返回暗月、武器/护甲和通用装备类美化，不返回奥纹/阳炎；`237831 / 破法者的责难 / Shield` 返回护甲、武器/护甲和通用装备类美化，不返回暗月；`244472 / 骑士指挥官的雄关` 因自带美化不返回独立美化。
- `paladin/protection`：制造盾牌规则与 `shaman/elemental` 一致，不出现暗月徽记。
- `mage/frost`：Held In Off-hand 规则与 `shaman/elemental` 一致，暗月徽记可选，护甲内衬不可选。

本轮不新增制造业来源 item，不改变 84 件 crafted source 口径；只修正强化配置读模型、前端交互过滤和生产 `websim_gear_mod_options` 当前赛季默认 seed。

## 后续更新规则

- 每次周期性更新先更新 allowlist/exclusion，再 dry-run，不允许直接按装备名或截图修前端。
- 普通制造业只接受当前 PVE allowlist、Battle.net metadata、SimC `crafted_stats` probe 三者一致的结果。
- 自带美化制造业必须保留 Battle.net unique-equipped embellishment metadata 和 fixed-stat SimC probe。
- PvP、团本 BoE random-stat、observed source pending、旧赛季 item 即使出现 `crafted_stats` 或 crafting-like metadata，也不能自动归类为制造业。
- 新增工程单副属性制造装备前，先实现独立 stat-option 模型、compact payload 表达和 UI 校验，再解除 `244774` 这类 blocked 清单。
