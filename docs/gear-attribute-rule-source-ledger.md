# Gear Attribute Rule Source Ledger

这份账本是装备模拟“非战斗常态属性面板”的生产启用闸门。只有同时具备可审计规则来源、`verified` 黄金样本和跨端 fixture 的 `ruleContext` 才能进入公开 `attributeCalculator`。`fixture_only` 仅可用于本地单元测试，不能发布到小程序。

| ruleContext | attributeRuleRevision | status | sourceRefs | goldenSampleIds | owner | lastVerifiedAt | coverage |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `mage:frost:90:*` | — | `blocked_pending_source_capture` | `https://worldofwarcraft.blizzard.com/ko-kr/character/kr/azshara/%EC%B9%B4%EB%A5%B4%EA%B3%B5%EC%8A%A4` (2026-07-17 capture returned 404) | `mage-frost-armory-2026-07-17t041853z` (`candidate`) | 装备模拟 | — | 当前角色资料不可得；种族、装备实例、强化、天赋、属性面板、稳定被动和全部换算仍未证实 |
| `mage:arcane:90:night_elf` | — | `blocked_pending_source_capture` | Armory `https://worldofwarcraft.blizzard.com/en-gb/character/eu/blackrock/Heated` (2026-07-17 captured); Raider.IO `https://raider.io/api/v1/characters/profile?region=eu&realm=blackrock&name=Heated&fields=gear%2Ctalents%2Cmythic_plus_scores_by_season%3Acurrent` (2026-07-17 captured) | `mage-arcane-armory-2026-07-17t041853z` (`candidate`) | 装备模拟 | — | Armory/社区资料交叉确认角色、15 件装备名称与装等；已补 itemId、宝石/附魔 ID，但 variant、部分附魔数值、基础属性、rating 换算、条件效果分类仍未证实 |

## 2026-07-17 授权候选采集

- 用户已明确授权将英雄榜/官方角色资料写入仓库。原始、可机读的候选记录保存在 `tests/fixtures/gear-attribute-armory-v1.json`。
- `Heated / EU Blackrock / 90 Night Elf Arcane Mage` 的官方页面在 `2026-07-17T04:18:53Z` 可访问：291 装等，面板为智力 `2,462`、耐力 `22,938`、暴击 `19%`、急速 `23%`、精通 `37%`、全能 `7%`，并保存每个可见装备 tooltip 的静态词条和条件效果文本。Raider.IO profile API 于 `2026-07-17T04:25:50Z` 返回同一角色、种族、当前专精及 15 件相同名称/装等的装备，补齐 itemId、gemId 和 enchantId；它不提供 variant 或非战斗属性公式。
- `카르공스 / KR Azshara / Frost Mage` 的原官方 URL 在同一抓取时点返回 `404`。此前截图只能作为讨论中的历史对照，不足以补齐当前装备、种族、强化或计算规则；该候选不包含任何可发布的最终属性输入。
- 两条记录均为 `candidate`。样本注册表校验要求 `candidate` 明示缺口，并阻止它满足 `verified` 规则的 `goldenSampleIds`；没有完整、可复核的换算与输入证据时，公开 `attributeCalculator` 继续返回 `rule_unavailable`。

## 录入要求

- `sourceRefs` 必须能指向具体的规则来源或可复核的官方证据，不能只写“英雄榜截图”或角色名。
- `goldenSampleIds` 必须绑定完整角色身份、抓取时间、等级、种族、专精、天赋、装备/强化快照和英雄榜属性。
- 写入任何网络来源内容前，必须先获得用户对“将网络来源写入仓库”的明确许可；在此之前只能保留本地 synthetic fixture。
- 任一来源、样本或跨端 fixture 失效时，规则状态退回 `blocked_pending_source_capture`，公开接口返回 `ATTRIBUTE_RULE_UNAVAILABLE`。
