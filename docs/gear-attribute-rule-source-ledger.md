# Gear Attribute Rule Source Ledger

这份账本是装备模拟“非战斗常态属性面板”的生产启用闸门。只有同时具备可审计规则来源、`verified` 黄金样本和跨端 fixture 的 `ruleContext` 才能进入公开 `attributeCalculator`。`fixture_only` 仅可用于本地单元测试，不能发布到小程序。

| ruleContext | attributeRuleRevision | status | sourceRefs | goldenSampleIds | owner | lastVerifiedAt | coverage |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `mage:frost:90:dwarf` | — | `blocked_pending_rule_source` | Armory `https://worldofwarcraft.blizzard.com/en-us/character/kr/azshara/%EC%B9%B4%EB%A5%B4%EA%BD%81%EC%8A%A4` and authorized Battle.net Profile API (2026-07-17T09:12:43Z; active loadout rechecked 2026-07-17T09:24:32Z) | `mage-frost-armory-2026-07-17t091243z` (`candidate`) | 装备模拟 | — | 已确认法师/冰霜/矮人/90 级、Spellslinger 活动配置码、15 件实际装备、bonus IDs、宝石/附魔 IDs 与未舍入面板；仍缺可发布的 variant 解析、每项强化数值、稳定被动与天赋效果分类/映射和通用 rating 换算 |
| `mage:arcane:90:night_elf` | — | `blocked_pending_rule_source` | Armory `https://worldofwarcraft.blizzard.com/en-gb/character/eu/blackrock/Heated` (2026-07-17 captured); authorized Battle.net Profile API (2026-07-17T04:43:43Z; active loadout rechecked 2026-07-17T09:35:57Z); Raider.IO `https://raider.io/api/v1/characters/profile?region=eu&realm=blackrock&name=Heated&fields=gear%2Ctalents%2Cmythic_plus_scores_by_season%3Acurrent` (2026-07-17 captured) | `mage-arcane-armory-2026-07-17t041853z` (`candidate`) | 装备模拟 | — | 官方 API 已确认种族/专精、15 件实际装备、bonus IDs、宝石/附魔 IDs、Spellslinger 活动配置码及未舍入面板；仍无可发布的 variant 解析、所有附魔数值、全种族/专精基础与 rating 换算、稳定与条件效果分类/映射规则 |

## 2026-07-17 授权候选采集

- 用户已明确授权将英雄榜/官方角色资料写入仓库。原始、可机读的候选记录保存在 `tests/fixtures/gear-attribute-armory-v1.json`。
- `Heated / EU Blackrock / 90 Night Elf Arcane Mage` 的官方页面在 `2026-07-17T04:18:53Z` 可访问：291 装等，面板为智力 `2,462`、耐力 `22,938`、暴击 `19%`、急速 `23%`、精通 `37%`、全能 `7%`，并保存每个可见装备 tooltip 的静态词条和条件效果文本。经用户授权，云端既有 Battle.net OAuth 在 `2026-07-17T04:43:43Z` 只读抓到同一角色的官方 Profile：15 件实际装备（另有不计入装备模拟的衬衣/战袍）、每件 item level/bonus ID/宝石/附魔 ID，以及未舍入的急速 `802 → 23.003637%`、精通 `785 → 37.04609%` 等面板值；在 `2026-07-17T09:35:57Z` 又确认当前为 Arcane Spellslinger 活动配置。全能通过官方 `versatility=385` 和独立的 `versatility_damage_done_bonus=7.1296296` 正确归一为 `385 → 7.1296296%`，与英雄榜截图的 `7%` 一致。Raider.IO profile API 于 `2026-07-17T04:25:50Z` 返回同一角色、种族、当前专精及 15 件相同名称/装等的装备。三者能交叉确认候选输入与输出，但都不构成通用 variant 或非战斗属性公式来源。
- 原候选 `카르공스 / KR Azshara / Frost Mage` 的 URL 在早期抓取时返回 `404`，保留为失败证据。经只读官方 Profile 适配器修复 URL 编码、本地化名称、`rating_normalized` 和 `enchantments` 字段后，`카르꽁스 / KR Azshara / Frost Mage` 于 `2026-07-17T09:12:43Z` 被重新确认：矮人、90 级、15 件实际装备（无副手）、精确 bonus/宝石/附魔 IDs，面板为智力 `2,485`、耐力 `23,001`、暴击 `861 → 25.717392%`、急速 `669 → 21.033895%`、精通 `1,040 → 53.773914%`。这与用户英雄榜截图的智力 `2,485`、耐力 `23,001`、暴击 `26%`、急速 `21%`、精通 `54%` 相符；但它是 2026-07-17 的当前角色快照，不能替换产品中 2026-07-16 的旧 Raider.IO 社区模板面板。
- 三条记录均为 `candidate`。样本注册表校验要求 `candidate` 明示缺口，并阻止它满足 `verified` 规则的 `goldenSampleIds`；没有完整、可复核的换算与输入证据时，公开 `attributeCalculator` 继续返回 `rule_unavailable`。

## 录入要求

- `sourceRefs` 必须能指向具体的规则来源或可复核的官方证据，不能只写“英雄榜截图”或角色名。
- `goldenSampleIds` 必须绑定完整角色身份、抓取时间、等级、种族、专精、天赋、装备/强化快照和英雄榜属性。
- 写入任何网络来源内容前，必须先获得用户对“将网络来源写入仓库”的明确许可；在此之前只能保留本地 synthetic fixture。
- 任一来源、样本或跨端 fixture 失效时，规则状态退回 `blocked_pending_source_capture`，公开接口返回 `ATTRIBUTE_RULE_UNAVAILABLE`。
