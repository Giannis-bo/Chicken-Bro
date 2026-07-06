# 12.1 Catalyst Inherited Stats and SimC Design

## 背景

2026-07-06 讨论确认：Midnight 12.1 的 Catalyst / 套装转化机制会改变装备建模方式。PTR 说明显示，转化出的职业套装护甲会继承被转化装备的副属性、三绿字属性和部分 cantrip 效果。也就是说，套装件不能再被简单理解为“固定 itemId + 固定绿字”的模板。

相关外部证据：

- Blizzard PTR notes / reward update：12.1 Catalyst 转化后的 class set armor 会继承原装备属性和部分特殊效果。
- SimulationCraft addon 已出现 `redirected_base_stats` 导出逻辑，用来表达 12.1 这类“套装物品基础属性重定向到原装备属性”的装备实例。
- SimC profile 的装备行本质是实例行：`slot=item_name,id=...,ilevel=...,bonus_id=...,gem_id=...,enchant_id=...` 以及后续扩展字段共同决定最终模拟装备。

本设计只记录模型和门禁，不做代码实现、不采集 PTR 数据。

## 核心结论

12.1 后，套装转化应被建模为“装备实例上的套装覆盖层”，而不是新建一批固定属性套装模板。

旧理解：

- 套装来源主要是 `source_type='tier_set'`。
- 套装部位属性来自套装 item 的固定变体。
- 前端按 item-set metadata 统计已选套装件数。

12.1 后需要支持：

- 一件 M+ / raid / crafted / other eligible 装备可以通过 Catalyst 获得套装身份。
- 装备原始属性、bonus、插槽、附魔、crafted_stats、美化和部分特殊效果仍来自原装备实例。
- 套装 2/4 件统计来自“已选装备是否带当前职业套装覆盖层”，不能只看 `sourceType='tier_set'`。
- SimC serializer 必须保留 `redirected_base_stats` 等实例级字段，不能用前端字符串拼接或固定套装 stats 伪造。

## 数据模型原则

装备实例应拆成三层：

1. Base item：原装备实例，包含 `itemId`、slot、ilevel、bonus_id、gem_id、enchant_id、crafted_stats、embellishment、itemStats / statSummary。
2. Tier overlay：套装身份覆盖层，包含 `catalystConverted=true`、`itemSetId`、`itemSetName`、`tierClass`、`tierSlot`、`tierBonusEligible`、`conversionSource`。
3. SimC instance options：真实可执行字段，包含 `redirected_base_stats` 以及未来 SimC 为 Catalyst 继承属性新增的等价字段。

`sourceType` 仍表达装备来源，不应被套装覆盖层污染：

- 一件由 M+ 装备转化来的套装，来源仍可以是 `dungeon`，但额外带 tier overlay。
- 一件 raid 掉落的原生套装，来源可以是 `tier_set` 或 raid/tier 的 accepted source，同时也带 tier overlay。
- UI 的“来源筛选”和“套装件数统计”必须分别读取不同字段。

## SimC Profile 规则

后端 serializer 是唯一可以生成最终 SimC 装备行的地方。

必须支持：

- parser / normalizer 接受 `redirected_base_stats`。
- `gearBySlot` 结构化快照保存该字段。
- profile serializer 原样写回已验证的 `redirected_base_stats`。
- template signature / stat snapshot signature 纳入该字段，避免属性快照错复用。
- `build_websim_gear_stats_response` 和 SimC 任务详情回放使用同一套字段。

不允许：

- 前端手工拼 `redirected_base_stats`。
- 用固定 `stats=` 替代缺失的继承属性。
- 只因为装备有 item-set membership 就假定它拥有正确的套装转化属性。
- 用 `set_bonus` 手动覆盖普通玩家装备，除非未来补齐 verified set membership -> SimC token 映射和独立 blocker。

## 装备模板影响

装备模板必须保存结构化实例，而不是只保存 “套装部位 + 装等”：

- `gearBySlot[slot]` 需要保留 base item 和 tier overlay。
- `enhancementBySlot` 继续只保存宝石、附魔、美化等主动配置，不承载套装转化。
- `metadata.gearSnapshot` 和 `metadata.statSnapshot` 必须包含 `catalogRevision` 和 SimC instance signature。
- 老模板如果缺 `redirected_base_stats`，不能在 12.1 后静默升级成“已转化套装”；只能按历史模板展示或要求用户重新选择/导入。

模板展示上：

- 套装件数可以显示为 `tierSetCount`，但计算来源是后端结构化 tier overlay。
- 历史 S1 模板切到 S2 后仍按保存时 catalog 解释；重新模拟前需要迁移或重建。
- 如果保存的转化装备缺 `redirected_base_stats` 或 SimC 不支持该字段，serializer 必须 fail-closed。

## 读模型与 UI 边界

后端 compact payload 需要最终能表达：

- `tierOverlay` / `tierSetMembership`：该装备是否提供当前职业套装件。
- `tierBonusEligible`：该槽位是否计入 2/4 件效果。
- `catalystConverted`：是否由 Catalyst 转化而来。
- `simcOptions.redirected_base_stats`：只有 verified / executable 时下发。
- `sourceTypes`：仍用于来源筛选，不和套装覆盖层混在一起。

前端只负责展示：

- 已选装备的套装件数。
- 已转化 / 原生套装标记。
- 如果装备缺继承属性证据或 SimC-ready 字段，展示 blocker 或不可保存状态。

前端不负责：

- 判断哪些装备能被 Catalyst 转化。
- 推导 `redirected_base_stats`。
- 根据 itemId、装备名或套装名硬编码套装件数。

## 与 12.1 PTR Catalog 的关系

本设计依附于 12.1 Hybrid Catalog 隔离方案：

- PTR 阶段可以在 staging catalog 中记录 Catalyst candidate 和 `ptr_executable`。
- PTR `ptr_executable` 只表示内部 SimC PTR/nightly 可执行，不等于正式 `verified`。
- 12.1 live 后必须重新用 Battle.net live metadata、稳定 SimC、Wago/curated evidence 验证，再允许进入 active retail catalog。

`redirected_base_stats` 支持是 12.1 S2 切换的 SimC version gate 之一。装备库数据齐全但 SimC 不支持该字段时，S2 不能进入正式 sim-ready path。

## 验收标准

实现时至少需要覆盖：

- SimC parser 能识别并保留 `redirected_base_stats`。
- `SIMC_GEAR_OPTION_ALIASES` / serializer allowlist 允许该字段，但未知字段仍 fail-closed。
- 保存装备模板后，`gearBySlot` 能保留 base item、tier overlay 和 SimC instance options。
- 套装件数按 tier overlay 统计，而不是只按 `sourceType='tier_set'`。
- M+ / raid / crafted 来源转化为套装后，来源筛选仍显示原来源，套装统计仍正确。
- 缺 `redirected_base_stats` 的转化装备不能被包装成 verified SimC-ready。
- 40 职业专精 compact gear traversal 和 `/api/websim/profile` smoke 能覆盖有/无 Catalyst 转化的装备。

## 后续实施提示

后续实现前应先做 TDD：

1. 添加 SimC line fixture：包含 `redirected_base_stats` 的 12.1 Catalyst 转化装备。
2. 添加 template snapshot fixture：保存后再生成 profile，字段不能丢。
3. 添加 read-model fixture：同一装备同时带原来源和 tier overlay，来源筛选与套装计数互不污染。
4. 添加 blocker fixture：缺 `redirected_base_stats`、错职业套装、错槽位或 SimC 不支持时阻断保存/模拟。
