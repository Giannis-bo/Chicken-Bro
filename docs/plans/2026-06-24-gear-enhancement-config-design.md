# 装备强化配置方案

> 状态：v1.1 已完成生产热部署、生产数据刷新、本地回归和实施证据补录。
> 来源：2026-06-24 本地讨论，围绕装备模拟如何处理宝石、附魔、美化、饰品特效和套装效果。

## 背景

装备模拟需要从“展示候选装备”继续推进到“可被 SimC 消费的完整配置”。普通静态属性可以由装备变体读取模型提供，但饰品特效、美化、附魔 proc、套装效果不是简单属性相加。它们必须进入 SimC profile，或由 SimC 根据装备实例自动推导，否则模拟结果会和玩家预期不一致。

当前决策是把装备选择和强化配置分层：装备模拟主流程负责 16 个装备槽位，强化配置负责玩家主动加工行为，套装和饰品特效尽量自动推导。

## 产品方案

1. 装备模拟默认展示 16 个 canonical 槽位，由玩家自行选择装备、来源和装等变体。
2. 套装数量由已选装备自动计算，不增加普通玩家手动开关；首版强化配置 UI 不提供套装配置项。
3. 饰品特效由 SimC 基于饰品装备实例自动处理。玩家只选择 `trinket1` / `trinket2` 的装备本体；首版不单独暴露饰品特效或使用策略配置。
4. 宝石、附魔、美化进入独立的“强化配置”入口。该入口只展示当前已选装备中支持配置的部位。
5. 强化配置按槽位回写，最终保存为可由后端序列化成 SimC profile 的装备配置快照。

## UI 边界

装备模拟主界面保持以 16 槽装备为中心，避免把宝石、附魔、美化、套装细节塞进每个装备候选 sheet。v1 在装备栏上方新增属性概览，集中展示整体装等、按职业专精判断的主属性、耐力、急速、暴击、精通、全能，以及 `美化 已使用/2`、`宝石 已选/可配置`、`附魔 已选/可配置`。生命值、法力值和护甲不进入首版概览。

“强化配置”入口放在属性概览旁边。打开后，用户进入一个按能力分组的配置界面：

- 宝石：仅展示有真实插槽或已验证可加插槽的部位。
- 附魔：仅展示当前版本明确可附魔的部位。
- 美化：仅展示可制造或已带制造字段的装备部位。
- 套装：不作为普通配置项；相关推导继续留在后端 / SimC 边界，避免普通玩家伪造套装效果。

强化配置 sheet 已按两层交互实现：上层展示当前已选装备里可强化的槽位，装备卡展示该槽位同时支持的 `宝石 / 附魔 / 美化` 能力；选中装备后，下层按能力分组展示该装备全部可配选项。同一槽位可以同时配置宝石、附魔和美化，例如制造戒指可以同时出现三组。用户点击选项时只写入 sheet 内的 draft 状态并高亮选中，点击底部“确认”后才写回 `enhancementBySlot` 和属性概览；点击“关闭”会丢弃未确认修改，避免玩家以为选择已经保存但实际没有提交。

换装备后，原强化配置必须重新校验：如果新装备不支持原宝石、附魔或美化，配置应被清除或标为 blocker，不能静默保留到 SimC profile。

## 品质选择规则

首版强化配置 catalog 只保留二星品质，不支持一星 / 低品质选项。虽然宝石和附魔的一星、二星会对应不同 `item_id`、`gem_id` 或 `enchant_id`，且 SimC 数值不同，但产品层面不提供低品质模拟入口，避免 UI、模板保存和 profile 生成出现额外分支。

- 宝石：只导入 PVE Quality 2/2 宝石 item id，最终 profile 写对应二星 `gem_id`。当前生产 socket catalog 收敛为 20 个单颗宝石 seed，覆盖项链与双戒指；PVP 宝石、observed 多宝石组合和缺可读属性值的宝石不进入玩家可选项。主属性宝石按当前赛季唯一规则处理，已选 1 颗后前端禁用其他主属性宝石，后端 serializer 继续把超过 1 颗的快照判为 blocker。
- 附魔：只导入二星附魔 item id / `SpellItemEnchantmentID`，最终 profile 写对应二星 `enchant_id`。
- 美化：UI 只展示二星 Optional Reagent；SimC 序列化仍按归一化 `embellishment=...` 写入，因为同一美化的一星 / 二星在 SimC 侧共享同一个美化效果 key。

如果后续证据源中仍出现一星 item id，只作为上游数据识别线索或审计材料，不进入玩家可选项、不写入保存模板，也不作为 profile serializer 的 fallback。

## 美化规则

美化分两类处理：

- 装备自带美化：制造业装备本体已经带 `limit_category=装备唯一：美化（2）` 或等价 Battle.net preview 标记，玩家选中装备后自动计入美化数量限制，不进入“强化配置”二次选择。
- 独立美化试剂：Optional Reagent，由玩家在“强化配置”里按槽位选择，最终写入对应装备行的 `embellishment=...`。同一装备已经自带美化时，不允许再叠加独立美化。

美化数量限制优先作为前端 UI 约束处理：每个角色最多生效 2 个美化，计数同时包含装备自带美化和玩家在“强化配置”里添加的独立美化。强化配置入口应展示当前 `已使用 / 2`，达到 2 个后禁用其他独立美化选择；如果换装备后因为自带美化增加导致总数超过 2，相关配置应标为 blocker，提示玩家移除装备或清理独立美化。

独立美化选项需要建立当前赛季制造美化 catalog，不能只靠 observed profile 反哺。证据链按优先级保留：

- SimC `embellishment_data_ptr.inc`：提供 `simc_key`、`bonus_id`、`effect_id`、`spell_id`，决定 profile 可消费字段。
- Wago DB2 `ModifiedCraftingCategory` / `ModifiedCraftingItem` / `ModifiedCraftingReagentItem`：提供 reagent item id、category id、item bonus tree 和可用范围。
- Wowhead / Method：作为人可读交叉证据，验证“自带美化”与“optional reagent”分类和适用范围文案。
- Battle.net item preview：识别装备自带美化、官方中文名、品质、图标、物品类型和唯一装备限制。

首版按 `slot_group` 过滤，不直接在 UI 写死每个 item：

- `armor`：护甲类槽位，覆盖 `head/shoulder/back/chest/wrist/hands/waist/legs/feet`，例如 `arcanoweave_lining`、`sunfire_silk_lining`。
- `weapon_offhand`：武器与 Held In Off-hand 副手，覆盖 `main_hand` 以及 item type 为 `INVTYPE_HOLDABLE` / Held In Off-hand 的 `off_hand`，例如 `darkmoon_sigil_hunt`、`darkmoon_sigil_blood`、`darkmoon_sigil_rot`、`darkmoon_sigil_void`。盾牌不走暗月徽记链路。
- `weapon_armor`：武器与护甲，覆盖 `main_hand/off_hand` 加护甲槽，例如 `devouring_banding`、`primal_spore_binding`。
- `equipment`：大多数未美化装备，覆盖制造装备中可插入美化槽的通用部位，例如 `blessed_pango_charm`、`prismatic_focusing_iris`、`stabilizing_gemstone_bandolier`。
- `engineering_boots`：工程靴子，UI 等价 `feet`，例如 `kinetic_ankle_primers`。
- `engineering_equipment`：工程制造装备，需结合具体工程配方槽位校验，例如 `b1p_scorcher_of_souls`、`hu5h_nonchalant_pup`、`b0p_curator_of_booms`。

后端保存时应记录 `simc_key`、展示名、item ids、`bonus_id`、`effect_id`、`spell_id`、DB2 category id、可用范围文案、`slot_group`、来源引用、状态和 blockers。前端只消费后端校验后的 options，不自行猜测适用范围。

副手需要按装备类型二次分流，不能只看 `off_hand` 槽位。当前实现把盾牌视为 armor-like 可强化装备：可选 `armor`、`weapon_armor`、`equipment` 类美化，但不展示暗月徽记；Held In Off-hand 副手可选 `weapon_offhand`、`weapon_armor`、`equipment` 类美化，但不展示奥纹/阳炎这类护甲内衬。自带美化盾牌或副手继续只计入自带美化，不再提供独立美化选项。

## 数据模型

保存时不要让前端直接拼 SimC 字符串。v1 保存结构化快照：

```json
{
  "schemaRevision": "websim-gear-enhancement-snapshot-v1",
  "gearBySlot": {},
  "enhancementBySlot": {
    "main_hand": { "enchant_id": "8039" },
    "finger1": { "enchant_id": "example" },
    "back": { "embellishment": "blue_silken_lining" }
  }
}
```

字段含义：

- `gearBySlot`：16 槽装备选择，保留 slot、item id、ilevel、bonus/gem/enchant/crafted fields、来源和可信状态。
- `enhancementBySlot`：玩家主动配置的宝石、附魔、美化，必须绑定到具体 slot。
- `schemaRevision`：快照版本，当前为 `websim-gear-enhancement-snapshot-v1`。
- `readiness`：不由前端保存；后端 serializer 在确认 / 执行 SimC 前重新校验，任何缺字段、槽位不兼容、重复美化、低品质或 SimC 不支持都进入 blockers。
- `derivedSetBonuses`：不进入 v1 保存 payload。后续如果要显式写 SimC `set_bonus` token，需要单独补权威映射和 blocker。

强化配置读模型统一从后端 `websim_gear_mod_options` 输出可展示字段：

- `displayLabel`：玩家可读展示值。宝石显示属性值，例如 `+32主属性`、`+16精通 +7暴击`；附魔和美化显示中文名称，例如 `朗多雷之锐`、`奥纹内衬`。
- `displayKind`：`stat` 或 `name`，用于前端只做薄展示，不从 ID 猜文案。
- `displayStatus`：必须为 `verified` 才进入强化配置 UI。
- `evidenceSource` / `sourceRefs`：记录展示证据来源。
- `simcOptions`：继续保留可执行字段，保存和 serializer 只消费这些字段，不保存展示名。

宝石需要特别处理数据漂移：Battle.net item metadata 仍是宝石名称、图标、item class 和缓存完整性的证据，但当前 `preview_item.gem_properties.effect` 对同一批宝石存在旧数值。服务端因此维护 20 个 PVE Quality 2/2 宝石的 live tooltip `statSummary/displayLabel` 覆盖；当单颗宝石 seed 带 verified 覆盖值时，`display_ready_socket_mod_option` 与 health coverage 优先使用该值，避免 UI 展示 `+14/+6` 这类旧属性。

## SimC 序列化规则

后端是唯一 profile serializer。最终 profile 生成规则：

- 装备行写入 `slot=name,id=...,ilevel=...,bonus_id=...` 等实例字段。
- 宝石 / 附魔 / 美化回写到对应装备行，例如 `gem_id`、`gem_bonus_id`、`enchant_id`、`crafted_stats`、`embellishment`。
- 套装首版不提供手动配置，也不由前端保存 token；如后续需要显式 `set_bonus=...` 行，必须由已选装备和已验证 token 映射推导，缺映射则 profile 阻断。
- 饰品只写装备实例字段，特效交给 SimC 自身处理；首版不增加手动 `use` / `equip` proc 编辑。
- 生成 profile 必须继续区分小程序配置快照和玩家官方 `/simc` 导出。小程序配置可以是可执行输入，但不能包装成真实角色最高保真快照。

## 信任边界

- 展示型装备、partial 变体或缺实例字段的装备不得进入可执行 profile。
- `itemId + ilevel` 只能作为属性候选或入库探针，不等于完整特效已验证。
- 宝石、附魔、美化选项必须来自真实插槽、可附魔部位、制造字段或明确服务端数据支持。
- 套装触发必须由已选装备和已验证 set membership 推导。
- SimC 报错、warning、缺支持或 profile 生成失败时，前端只能展示 blocked / partial，不能输出 DPS 或强结论。

## v1 本地实现收口

- 后端：`websim_gear_mod_options` 继续作为 catalog 表，新增 `embellishment` 类型与二星 Optional Reagent seed；mod option coverage 纳入 `crafted_stats` 和 `embellishment`；profile serializer 支持从结构化 `gearBySlot/enhancementBySlot` 快照读取宝石、附魔、美化并回写到装备行。
- 后端：SimC 模板确认链路识别结构化装备快照，复用后端 serializer 生成 `simcItems/profile`，不再要求前端保存可执行 profile 字符串。
- 后端：美化计数包含装备自带美化和独立美化，超过 2 个进入 enhancement blocker；同一装备自带美化时不允许再叠加独立美化。
- 后端：附魔通过 Wago DB2 / SimC evidence 补齐中文名，无法解析为中文可读名的 observed 附魔不进入 UI；美化 seed 改为服务端维护中文 displayName 和 SimC key；前端不再维护名称兜底映射。
- 后端：20 个 PVE Quality 2/2 宝石 seed 由服务端维护 live tooltip `statSummary`，公网 compact payload 已验证包含 `+32主属性`、`+16精通 +7暴击`，不再展示旧的 `+14精通 +6暴击`。
- 前端：装备页新增属性概览，强化配置入口从底部 action bar 移到概览旁边；强化 sheet 按可强化装备和当前装备配置两层展示，按宝石、附魔、美化分组，只显示当前已选装备支持且后端提供可读证据的选项。
- 前端：强化 sheet 使用 draft 状态承接选项点击，底部“确认”按钮提交后才写回 `enhancementBySlot`；关闭 sheet 不保存未确认修改。
- 前端：保存装备模板时写结构化 `gearBySlot/enhancementBySlot` 快照，`metadata.enhancementBySlot` 保留结构化选择；`rawString/profile` 的可执行 SimC 输出仍由后端确定性生成。
- 生产：已执行后端热部署和生产 SQLite 刷新。相关备份包括 `/opt/wow-mini-program/backups/wow_news-before-rank-two-gems-20260625T045237Z.sqlite3`、`/opt/wow-mini-program/backups/wow_news-before-readable-mod-options-20260625T050309Z.sqlite3`、`/opt/wow-mini-program/backups/wow_news-before-live-gem-tooltips-20260625T060131Z.sqlite3`。
- 验证：`tests/websim_payload_test.py`、`tests/news_backend_test.py`、`tests/builds-page.test.js` 覆盖 catalog 入库、二星过滤、美化上限、换装备 blocker、profile serializer、强化配置入口、可配置槽位过滤、同槽宝石/附魔/美化三组展示、确认按钮 draft 写回、美化 2 个上限和保存 payload。生产 `/api/data/health` 中 `modOptionStatus=verified`，公网 `/api/websim/gear?class=mage&spec=frost&compact=1` 验证 `neck/finger1/finger2` 均返回 20 个宝石选项。

## v1.1 Midnight 制造美化映射收口

本轮修正目标是把“制造业装备能否配置美化”从截图驱动改为后端统一读模型：同一个装备按钮、强化配置 sheet、属性概览和 SimC serializer 都消费同一份 `websim_gear_mod_options` 与装备 metadata 判定结果。

当前生产默认独立美化 catalog 收敛为 11 个 Midnight optional reagent：

- 护甲类：`arcanoweave_lining`、`sunfire_silk_lining`。
- 通用装备类：`blessed_pango_charm`、`prismatic_focusing_iris`、`stabilizing_gemstone_bandolier`。
- 武器/护甲类：`devouring_banding`、`primal_spore_binding`。
- 武器/Held In Off-hand 类：`darkmoon_sigil_blood`、`darkmoon_sigil_hunt`、`darkmoon_sigil_rot`、`darkmoon_sigil_void`。

旧 TWW 默认美化 `dawnthread_lining`、`duskthread_lining`、`elemental_focusing_lens` 不再作为 Midnight 默认可选种子；代码仅保留历史快照展示兼容，不让它们进入当前赛季玩家可选项。

适用范围以三层证据合并：

- SimC `embellishment_data_ptr.inc` 决定 profile 可消费 key、bonus/effect/spell 字段。
- Wowhead 当前物品页提供 optional reagent 文案和适用范围，作为 slot group 的人可读证据。
- Method 列表只用于其明确列出的 Midnight optional reagent 交叉确认，不把 Method 没列出的条目误报为缺失；Battle.net metadata 继续用于装备本体类型、图标、中文名、自带美化和唯一装备限制识别。

实现边界：

- 后端 `server/websim_payload.py` 负责归一化装备类型、过滤独立美化、统计自带美化和生成 serializer blocker。
- 前端 `pages/builds/detail.js` 只镜像后端规则做交互即时反馈；最终保存和 SimC profile 仍以后端校验为准。
- 装备按钮右上角根据当前槽位实际配置展示 `宝石`、`附魔`、`美化` 标签；标签来自已确认的 `enhancementBySlot` 与装备自带美化，不从全局计数反推。
- 换装备时会重新裁剪不兼容配置，避免出现概览 `宝石 0/0`、`附魔 0/0` 但装备卡仍残留标签的状态。

生产操作与证据：

- 备份：`/opt/wow-mini-program/backups/wow_news-before-midnight-embellishment-options-20260626T015048Z.sqlite3`。
- 热部署：`WOW_DEPLOY_SKIP_BOOTSTRAP=1 WOW_DEPLOY_START_ASYNC_SYNCS=0 ./server/deploy_lighthouse.sh`。
- 数据刷新：刷新 11 个 embellishment option seed 后，补跑 Wago 附魔中文名同步，避免 observed enchant 因缺 display name 被 health 统计为 0。
- 线上 health：`/health` 返回 OK；`/api/data/health` 中 `sourceCoverage.crafted=84`，`modOptionCoverage.socket=20`、`enchant=21`、`embellishment=11`、`crafted_stats=6`。
- 线上 compact 抽样：`shaman/elemental` 的制造项链、戒指、武器、盾牌、Held In Off-hand 副手均按装备类型返回美化选项；盾牌不出现暗月徽记，Held In Off-hand 不出现奥纹/阳炎内衬；自带美化装备返回空独立美化列表但继续计入 `美化 1/2`。

## v1.2 强化统计与标签机制复核

本轮复核源于属性概览中“未配置却显示已满”、附魔上限误算、宝石 tag 丢失等 UI 问题。最终收口是：宝石、附魔、美化、套装对外都可以显示为简单计数，但底层必须分别走各自证据链，不能共用一个前端槽位常量。

- 宝石：对外仍是 `0/3`、`3/3`，但这 3 来自后端 `SOCKET_OPTION_GEAR_SLOT_CAPACITY` 当前规则：项链、戒指 1、戒指 2 各 `socketCount=1`。前端已移除本地 `neck/finger1/finger2` 容量表，只消费 `modCapabilities.socketCount`、socket 数组或旧 payload 的明确 `hasSocket=true` 兼容兜底。属性概览的已使用数只统计用户确认写回的 `enhancementBySlot`，不会把装备原始 `gem_id` 或候选 option 当成已配置。
- 附魔：腿部护甲片归入 `enchant`，和其他装备附魔一样最终写 `enchant_id`。UI 上限不等于后端 `ENCHANTABLE_GEAR_SLOTS` 的全集，而是当前已选装备中存在 display-ready `enchantOptions` 或受控兼容兜底的可配置行；Held In Off-hand、盾牌和不适用副手武器附魔继续按装备类型过滤。
- 美化：计数继续为自带美化 + 独立美化，最大 2。自带美化只以装备 tag 和属性概览计数出现，不在同一装备上继续提供独立美化选择；独立美化达到上限时前端禁用，后端 serializer 仍负责最终 blocker。
- 套装：不进入 `enhancementBySlot`，也不进入“配置宝石、附魔”sheet。属性概览按当前已选装备的 item-set metadata 自动统计同套装件数，上限 5；未来若要显式 `set_bonus`，必须单独补权威映射和 blocker。
- 金色 tag：装备卡右上角标签来自“当前槽位已确认的 `enhancementBySlot` 与当前装备仍匹配”或装备自带美化，不从全局计数倒推。选择宝石/附魔/美化后，只有点击“确认”写回后才显示；换装备后若 option 不再匹配，会裁剪 stale 配置并同步移除 tag。
- 复核测试：`tests/builds-page.test.js` 覆盖 `socketCount` 证据链、腿部护甲片附魔上限、项链/双戒指宝石 tag、同戒指宝石/附魔/美化共存、主属性宝石唯一和自带美化计数；`tests/websim_payload_test.py` 覆盖 socket 不从 observed gem 反推、display-ready 门禁、附魔/美化过滤、serializer blocker 和套装 backfill。

## 后续切片建议

1. **套装推导**：从已选装备的 item set metadata 计算 2/4 件状态，补 SimC `set_bonus` token 映射和 blocker。
2. **catalog 扩展**：继续补齐二星宝石、二星附魔和更多二星 Optional Reagent 的生产证据链，缺 DB2/SimC/Battle.net 证据的条目保持 blocked，不进入玩家可选项。
3. **线上验收**：生产 SQLite 备份后再执行 catalog 入库和部署，验证 `/health`、`/api/data/health`、真实职业专精 `/api/websim/gear?...compact=1` 以及小程序预览侧真实强化选项。
4. **高级模式评估**：是否需要给维护者而非普通玩家提供套装或饰品策略 override，需要单独设计权限、审计和 blocker。

## 待确认问题

- 当前版本套装 `set_bonus` token 的权威来源与映射维护方式。
- 是否需要首版支持“高级模式”手动 override 套装或饰品使用策略。默认建议暂缓。
