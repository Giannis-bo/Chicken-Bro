# Gear Attribute Rule Source Ledger

这份账本是装备模拟“非战斗常态属性面板”的生产启用闸门。只有同时具备可审计规则来源、`verified` 黄金样本和跨端 fixture 的 `ruleContext` 才能进入公开 `attributeCalculator`；`fixture_only` 仅用于本地测试。

| ruleContext | attributeRuleRevision | status | goldenSampleIds | lastVerifiedAt | coverage |
| --- | --- | --- | --- | --- | --- |
| `mage:frost:90:dwarf` | `midnight-mage-attributes-r1` | `verified_limited_context` | `mage-frost-armory-2026-07-17t091243z` | 2026-07-17 | 90 级矮人冰法；源角色导入且 sealed talent context 完整时，展示本地即时常态面板。 |
| `mage:arcane:90:night_elf` | `midnight-mage-attributes-r1` | `verified_limited_context` | `mage-arcane-armory-2026-07-17t041853z` | 2026-07-17 | 90 级暗夜精灵奥法；源角色导入且 sealed talent context 完整时，展示本地即时常态面板。 |

## 当前发布边界

- 规则包在 `server/gear_attribute_rulebook.py`，前端本地解释器与 Python 参考解释器共享 `gear-attribute-calculation-v1` 语义；换装不会等待或触发 SimC。
- 已发布上下文只覆盖上表两个“职业 + 专精 + 等级 + 种族”组合。手动默认人类、火法、其它种族，或没有封存来源天赋事实的旧模板，继续返回 `属性资料待补齐`，不能用相邻种族或专精的规则猜测数值。
- 面板还要求当前 Resolver 返回 `attributeStaticFacts.status=verified`。选中的装备、宝石、附魔或美化缺少 canonical 静态事实时，同样降级；这条限制保护任意换装组合，不会把旧展示词条当成最终属性。
- `Arcane Familiar` 会被记录为条件效果，不计入奥法英雄榜常态法力；其余未映射的效果也显式保留为条件项，绝不静默加到面板。

## 证据链

- 两个黄金样本均保存于 `tests/fixtures/gear-attribute-armory-v1.json`，包含官方角色链接、抓取时间、90 级身份、15 件装备、官方 item level / bonus ID / 宝石 / 附魔实例、由 `itemId + itemLevel + sorted bonusIds` 组成的可复核 `variantKey`，以及未舍入英雄榜面板。样本校验器会从同一次官方实例重建该 key；任一 item、装等或 bonus 不一致都会拒绝提升为 `verified`。
- 官方 Profile 逐件结构化词条提供静态输入；固定宝石/附魔事实由 `server/gear_attribute_static_facts.py` 以结构化 ID 投影。`240967` 仅投影已核验的 `+23` 主属性，颜色相关暴击效果标为 non-panel，不能伪造为零或常驻。
- 受控只读 SimC `12.0.7.68453` 源码/DBC 仅用于规则审计：90 级法术暴击/精通 `46`、急速 `44`、全能 `54`，并使用二级曲线 `21024` 与三级曲线 `21025`。它不在玩家换装请求路径中。
- 封存的来源配置码在服务端被解码成 stable-effect IDs：两例共享 `Arcane Intellect 3%`、`Inspired Intellect 2%`、`Tome of Rhonin 2%` 暴击、`Tome of Antonidas 2%` 急速、`Charm of Medivh 3%` 精通；冰法额外使用 `Winter's Blessing`，奥法额外使用 `Arcane Tempo`。法师专精精通系数作为同一 sealed context 的常驻被动。

## 回归与精度

- `tests/fixtures/gear-attribute-official-cases-v1.json` 固化两名官方角色的输入、预期输出和英雄榜面板；Python 与小程序 JS 引擎都必须逐对象一致，并逐字段保持小于等于 `0.01` 个百分点的展示误差。小程序页回归同时覆盖“导入冰法黄金样本 → 本地把急速词条加 100”：无需 SimC 请求，种族和 sealed 效果保持，面板立即重算。
- Frost Dwarf：智力 `2485`、耐力 `23001`、生命 `460020`、急速 `21.033895%`、精通 `53.773913%`；与官方未舍入值的差异仅为显示精度。
- Arcane Night Elf：智力 `2462`、耐力 `22938`、生命 `458760`、法力 `342615`、全能 `7.129630%`；急速 `23.003655%` 对官方 `23.003637%` 的差异为 `0.000018` 个百分点。

## 长期校验机制

- 当后台巡检选举到新的社区 winner 时，只读抓取其可审计来源资料并形成 candidate fixture；不影响 winner 的正常发布或用户请求。
- 新 candidate 只有在实例静态事实、种族/等级、sealed 天赋效果、规则包计算和英雄榜字段逐项比对通过后，才能提升为 `verified` 并扩展公开上下文；失败则保留候选与差异记录，不回写现有规则。
- 规则、fixture、静态事实或曲线变更时必须重跑 Python/JS 双端回归。任一来源或样本失效，相关 context 退回不可用并继续 fail-closed。
