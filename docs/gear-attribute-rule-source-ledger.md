# Gear Attribute Rule Source Ledger

这份账本是装备模拟“非战斗常态属性面板”的生产启用闸门。只有同时具备可审计规则来源、`verified` 黄金样本和跨端 fixture 的 `ruleContext` 才能进入公开 `attributeCalculator`。`fixture_only` 仅可用于本地单元测试，不能发布到小程序。

| ruleContext | attributeRuleRevision | status | sourceRefs | goldenSampleIds | owner | lastVerifiedAt | coverage |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `mage:frost:90:*` | — | `blocked_pending_source_capture` | — | — | 装备模拟 | — | 等级、种族、稳定被动、主/耐力/资源、全部绿字换算均待官方来源与黄金样本确认 |
| `mage:arcane:90:*` | — | `blocked_pending_source_capture` | — | — | 装备模拟 | — | 等级、种族、稳定被动、主/耐力/资源、全部绿字换算均待官方来源与黄金样本确认 |

## 录入要求

- `sourceRefs` 必须能指向具体的规则来源或可复核的官方证据，不能只写“英雄榜截图”或角色名。
- `goldenSampleIds` 必须绑定完整角色身份、抓取时间、等级、种族、专精、天赋、装备/强化快照和英雄榜属性。
- 写入任何网络来源内容前，必须先获得用户对“将网络来源写入仓库”的明确许可；在此之前只能保留本地 synthetic fixture。
- 任一来源、样本或跨端 fixture 失效时，规则状态退回 `blocked_pending_source_capture`，公开接口返回 `ATTRIBUTE_RULE_UNAVAILABLE`。
