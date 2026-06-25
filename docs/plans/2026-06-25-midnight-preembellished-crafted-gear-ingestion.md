# Midnight 自带美化制造装备入库方案

> 状态：已完成生产入库、后端读模型修正、热部署和线上验证。
> 来源：2026-06-25 本地讨论，围绕 Midnight Season 1 制造业自带美化装备的完整入库与装备模拟联动。
> 后续：2026-06-25 已完成 Midnight 制造业整库审计，当前 crafted 总来源为 84；普通可选属性制造业、错误排除清单和 `251105` 纠偏见 `docs/plans/2026-06-25-midnight-crafted-gear-full-audit.md`。

## 目标

只处理 Midnight Season 1 的制造业自带美化装备，不纳入 TWW 旧赛季条目，也不把普通可加 Optional Reagent 的空白制造装备误标成自带美化。

这批装备进入生产库后必须同时满足：

- 替换装备 sheet 能在“制造业”筛选中看到候选。
- 候选行和已选装备卡片显示“美化”徽标。
- 选择装备后属性概览自动把自带美化计入 `美化 x/2`。
- 固定属性自带美化装备可被应用为可执行装备配置，不因为缺 `crafted_stats` 被挡在前端外。

## 证据链

入库采用三层证据：

1. Method Midnight pre-embellished gear 列表确认这批是当前赛季自带美化装备。
2. Wowhead Midnight crafted gear / embellishment 资料用于交叉确认分类和上下游口径。
3. Battle.net Game Data API item metadata 是最终生产写入依据。只有 `preview_item.limit_category=装备唯一：美化（2）` 或等价 Unique-Equipped Embellished 标记存在时，才写入 `crafted` source 和 `built-in embellishment` 标准字段。

来源链接：

- https://www.method.gg/guides/list-of-all-midnight-embellishments
- https://www.wowhead.com/news/best-early-season-crafted-gear-and-embellishments-for-all-classes-midnight-380801

## 入库清单

| itemId | 中文名 | 槽位 | 轨道 |
|---|---|---|---|
| 241340 | 魔导师的炼金石 | trinket1/trinket2 | 神话 285 |
| 244472 | 骑士指挥官的雄关 | off_hand | 虚空晋升 295、神话 285 |
| 244463 | 密谋小径健足靴 | feet | 神话 285 |
| 244679 | 密谋小径鱼钩 | main_hand | 虚空晋升 295、神话 285 |
| 246305 | 暗月统御：鲜血 | trinket1/trinket2 | 神话 285 |
| 246304 | 暗月统御：狩猎 | trinket1/trinket2 | 神话 285 |
| 246306 | 暗月统御：腐烂 | trinket1/trinket2 | 神话 285 |
| 246307 | 暗月统御：虚空 | trinket1/trinket2 | 神话 285 |
| 251513 | 神灵崇拜者的指环 | finger1/finger2 | 神话 285 |
| 241140 | 艾泽拉斯祝福印戒 | finger1/finger2 | 神话 285 |
| 241139 | 萨拉斯凤凰饰环 | neck | 神话 285 |
| 251073 | 虚空石护盾阵列 | neck | 神话 285 |
| 244606 | 妖纹束腰 | waist | 神话 285 |
| 244612 | 径巷行者的偏斜腕甲 | wrist | 神话 285 |
| 244613 | 径巷行者的保险护胸 | chest | 神话 285 |
| 244614 | 径巷行者的迅影手套 | hands | 神话 285 |
| 244601 | 世界之树根须裹足 | feet | 神话 285 |
| 244605 | 掷斧腕带 | wrist | 神话 285 |
| 244602 | 游侠将军之握 | hands | 神话 285 |
| 244611 | 世界照护者的树皮腰扣 | waist | 神话 285 |
| 244610 | 世界照护者的根须便鞋 | feet | 神话 285 |
| 244609 | 世界照护者的树干板甲 | chest | 神话 285 |
| 239660 | 奥纹护腕 | wrist | 神话 285 |
| 239661 | 奥纹披风 | back | 神话 285 |
| 239664 | 奥纹束带 | waist | 神话 285 |
| 239662 | 奥纹软鞋 | feet | 神话 285 |
| 239657 | 阳炎护腕 | wrist | 神话 285 |
| 239658 | 阳炎披风 | back | 神话 285 |
| 239663 | 阳炎腰带 | waist | 神话 285 |
| 239659 | 阳炎软鞋 | feet | 神话 285 |

## 数据写入方案

### 1. Metadata

生产库先写 `websim_items`，以 Battle.net metadata 作为官方中文名、图标、槽位、护甲/武器类型、preview stats 和自带美化标记来源。

本轮 30 件全部确认：

- `preview_item.limit_category=装备唯一：美化（2）`
- `hasBuiltInEmbellishment=true`
- `builtInEmbellishmentLabel=美化`
- `embellishmentSource=built_in`

### 2. Crafted source

每件写入一条 governed source：

- `id=crafted-governed-<itemId>`
- `source_type=crafted`
- `source_label=制造装备`
- `payload.status=verified`
- `payload.sourceRefs` 记录 Battle.net、Method、Wowhead 证据
- `payload.variantPolicy=source_only_until_deterministic_current_level_variant_evidence`

这层只负责“制造业来源”和“自带美化装备”身份，不伪造 `crafted_stats`。

### 3. Fixed-stat crafted variants

这批装备不是普通 missive 可选属性制造件，不能要求玩家选择 `crafted_stats`。因此新增固定属性 crafted variant：

- `derivedVariantSource=simulationcraft_preembellished_item_probe`
- `source_type=crafted`
- `simcOptions={"ilevel": "285"}`，武器/盾牌额外 `{"ilevel": "295"}`
- `simcIlevelOnly=true`
- `statSource=simulationcraft`
- `statDisplayStatus=verified_variant`

后端读模型允许这种 verified fixed-stat crafted variant 进入 compact payload；其他来源的 `simcIlevelOnly` 仍保持原有阻断，避免普通不完整候选被误判为可保存。

## 生产操作记录

生产备份：

- `/opt/wow-mini-program/backups/wow_news-before-midnight-preembellished-crafted-20260625T082750Z.sqlite3`

生产写入结果：

- 30/30 件 Battle.net metadata 写入成功。
- 30/30 件写入 `crafted-governed-*` source。
- 32/32 条 crafted fixed-stat variant 通过 SimC JSON probe，`partial=0`。
- `craftedDistinctTotal` 从 42 增至 71。

热部署：

```bash
WOW_DEPLOY_SKIP_BOOTSTRAP=1 WOW_DEPLOY_START_ASYNC_SYNCS=0 ./server/deploy_lighthouse.sh
```

部署只复用已有依赖和 SimC，不触发 bootstrap、下载或异步同步。

## 验证结果

本地测试：

- `python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_crafted_fixed_stat_variant_without_crafted_stats_is_usable`
- `python3 -m unittest tests.websim_payload_test -k crafted`
- `node --test tests/builds-page.test.js`
- `git diff --check`

生产验证：

- `/health` 返回 `ok=true`。
- `/api/data/health` 可访问；gear catalog 仍为 `partial`，但这是既有全局 blocker，不是本批入库失败。
- `hunter/marksmanship`、`mage/frost`、`paladin/protection`、`rogue/assassination`、`shaman/elemental`、`priest/discipline` compact payload 抽样中，命中的自带美化制造候选全部满足：
  - `sourceTypes` 包含 `crafted`
  - `hasBuiltInEmbellishment=true`
  - `builtInEmbellishmentLabel=美化`
  - `simcReady=true`
  - `variant=myth-285` 或武器/盾牌的 `crafted-void_upgrade-295`

武器/盾牌专项验证：

- `244472 / 骑士指挥官的雄关 / off_hand` 返回 `虚空晋升 295` 与 `神话 285` 两条 verified 轨道。
- `244679 / 密谋小径鱼钩 / main_hand` 返回 `虚空晋升 295` 与 `神话 285` 两条 verified 轨道。

## 后续边界

- 这批装备不显示 `crafted_stats` 属性搭配选择，因为当前证据链显示它们是固定属性自带美化装备。
- 如果后续官方或 SimC 证据证明某件自带美化装备也支持 missive，可单独补 `crafted_stats` variant，不从前端猜。
- Optional Reagent 美化仍走 `websim_gear_mod_options`，和自带美化装备分开建模。

## 周期性复用模板

后续 Midnight 当前赛季制造业清单发生变化时，复用本方案但不要复用旧结论。每次更新都从上游筛选重新开始，以生产 DB 只读审计和 SimC probe 结果作为写库依据。

### 1. 筛选候选

- 只筛 Midnight 当前赛季制造业装备；TWW 或历史赛季装备即使带美化，也不进入本清单。
- Method / Wowhead / guide 用于发现候选和人工对账；最终写库候选必须能在 Battle.net item metadata 中查到当前物品。
- 按装备类型先分组：普通可选属性制造装备、自带美化固定属性制造装备、Optional Reagent 美化。三类不能混入同一个入库逻辑。

### 2. 写库门禁

自带美化固定属性制造装备必须同时满足：

- `websim_items.payload_json` 中有 `preview_item.limit_category=装备唯一：美化（2）` 或英文等价 Unique-Equipped Embellished 标记。
- 有 governed `source_type='crafted'` source，source payload 记录 Battle.net metadata 和上游人工筛选来源。
- `simulationcraft_preembellished_item_probe` 能在目标装等返回该 item 的 `itemStats` / `statSummary`。
- compact payload 能保留 `hasBuiltInEmbellishment=true`、`builtInEmbellishmentLabel=美化`、`embellishmentSource=built_in`。

没有这些证据时，只能写 `partial` / `blocked` 或先停在待确认清单，不允许为了 UI 完整而伪造 `crafted_stats`、`embellishment` token 或当前实例属性。

### 3. 入库前审计

每次正式写库前记录：

- 生产 DB 备份路径。
- 目标 item 当前是否已有 `websim_items`、`websim_gear_sources`、`websim_gear_variants`。
- 新增 / 更新 / 跳过的 item、source、variant 数量。
- `source_type='crafted'` 下是否存在旧赛季、旧标签、旧 `needs-variant`、错误 `289/298` 轨道或 verified 缺属性行。
- 本次 dry-run 中所有 `partial` / `blocked` 的 itemId、slot、装等和 blocker。

### 4. 读取与 UI 验收

写库和部署后至少抽样：

- `/api/data/health` 的 gear catalog 状态和 top blockers。
- `/api/websim/gear?compact=1` 中目标 item 是否进入正确槽位、`sourceTypes` 是否包含 `crafted`、`simcReady` 是否为 true。
- 替换装备 sheet 的“制造业”计数是否增加，候选行和已选装备卡片是否显示“美化”。
- 选择该装备后属性概览是否自动计入 `美化 x/2`。
- 强化配置 sheet 是否隐藏同槽位独立美化选项；切换掉装备后是否重新开放符合条件的独立美化选项。

### 5. 回滚边界

代码部署和 DB 写入分开判断。若只是 compact 读取逻辑问题，优先回滚代码；若写入了错误 item/source/variant，先保留错误样本和 SQL 证据，再由 owner 决定恢复备份或执行定向修正。恢复生产 DB 前必须停止服务，恢复后重新跑 `/health`、`/api/data/health` 和 compact payload smoke。
