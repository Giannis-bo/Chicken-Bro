# Reused Legacy Dungeon Current-Season Candidate Review

Generated: 2026-06-23T09:09:42Z

Scope: production read-only DB `/opt/wow-mini-program/server/data/wow_news.sqlite3`; production SimC `/opt/wow-simc/current/simc` (`SimulationCraft 1205-01 / 12.0.5.67823`).

Status: derived manual-review candidates only. No database write, no sync, no deploy, and no catalog promotion. `298` is shown only for main-hand weapons and trinkets under the existing special-lane review rule.

## 2026-06-23 Validation Update

This report is now a `journal_candidate` / downfilter artifact for reused legacy dungeons. The tables below are useful SimC evidence, but the Pit `49` rows and Seat `44` rows are not accepted current-season loot counts.

Reusable validation scheme:

1. Treat raw Battle.net Journal loot as the upper bound (`raw_journal` / `journal_candidate`).
2. Treat local verified observed variants as the lower bound (`observed_confirmed`), not as a complete loot table.
3. Use a current-season loot reference table or item-page cross-source evidence as the middle set (`source_reference`) before producing accepted manual-review candidates.
4. Keep guide/item-page disagreements as `source_discrepancy` and record why the item is included or blocked.
5. Run SimC only for the source-reference target set when preparing accepted manual review; keep rows `partial` until deterministic SimC variant preset evidence exists.

Updated source-reference targets:

| Instance | Raw Journal Rows | First local filter | Observed lower bound | Source-reference target | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| Pit of Saron / 萨隆矿坑 | 74 | 49 | 13 | 24 | First local filter removed 133xxx duplicate-name bucket, but another 25 rows are still overbroad versus current-season reference. |
| Seat of the Triumvirate / 执政团之座 | 44 | 44 | 6 | 35 | Current-season guide gives 34; `258523 / 奈扎尔的虚空爪` is included through item-page cross-reference to `总督奈扎尔`. |
| Skyreach / 通天峰 | 230 | 28 | 10 | 28 | Current-season rewards guide and item-page cross-check accept the 252xxx/258xxx local-current subset; the other 202 rows remain `excluded_legacy_bucket`. |

Source-reference candidate ids:

- Pit of Saron: `50228`, `49812`, `49823`, `49825`, `49809`, `50263`, `49805`, `50264`, `49806`, `49817`, `49824`, `50233`, `49810`, `49811`, `49819`, `50234`, `50272`, `49808`, `252421`, `50259`, `49807`, `50227`, `49802`, `49813`.
- Seat of the Triumvirate: `151309`, `151308`, `151311`, `151337`, `151299`, `151303`, `151305`, `151300`, `151304`, `151336`, `151315`, `151318`, `151316`, `151314`, `151317`, `151323`, `151325`, `151321`, `151326`, `151338`, `151333`, `151331`, `151329`, `151332`, `151327`, `151330`, `151307`, `151312`, `151310`, `151340`, `258524`, `258525`, `258516`, `258514`, `258523`.
- Skyreach: `252411`, `252418`, `252420`, `258046`, `258047`, `258048`, `258049`, `258050`, `258218`, `258412`, `258436`, `258438`, `258472`, `258484`, `258574`, `258575`, `258576`, `258577`, `258578`, `258579`, `258580`, `258581`, `258582`, `258583`, `258584`, `258585`, `258586`, `258587`.

## Original Local Filter Summary

This table records the first local id-bucket filter. It is no longer the accepted current-season candidate summary for Pit or Seat.

| Instance | Raw Journal Rows | Local Candidate Rows | Excluded Rows | Filter rule |
| --- | ---: | ---: | ---: | --- |
| Pit of Saron / 萨隆矿坑 | 74 | 49 | 25 | 保留 498xx / 502xx / 252421 史诗候选；排除 133xxx 同名精良重复行。该 49 行现在只算 `journal_candidate` 上限。 |
| Skyreach / 通天峰 | 230 | 28 | 202 | 保留 252xxx / 258xxx 当前候选；排除 109xxx / 110xxx / 112xxx 历史或 WoD 通用地下城池。 |
| Seat of the Triumvirate / 执政团之座 | 44 | 44 | 0 | 第一轮本地规则未排除任何行；该 44 行现在只算 `journal_candidate` 上限。 |

SimC cells: ok `375`, no-static-stat `20`, errors `0`, elapsed `55.2s`.

## Pit of Saron / 萨隆矿坑

| itemId | 装备 | Boss/source | 类型 | inventory | slot | socket | current state | blocker | observed ilvl | 263 | 276 | 289 | 298 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 49801 | 不传之秘 | 熔炉之主加弗斯特 | 武器 / 法杖 | 双手 | main_hand | - | partial | missing deterministic SimC variant preset | - | 智力 335；耐力 1281；爆击 116；急速 94 | 智力 378；耐力 1507；爆击 124；急速 101 | 智力 427；耐力 1768；爆击 133；急速 108 | 智力 465；耐力 1974；爆击 139；急速 113 |
| 49802 | 千钧 | 熔炉之主加弗斯特 | 武器 / 锤 | 双手 | main_hand | - | partial | missing deterministic SimC variant preset | 298 | 力量 97；耐力 1281；爆击 93；急速 50 | 力量 110；耐力 1507；爆击 100；急速 54 | 力量 124；耐力 1768；爆击 107；急速 58 | 力量 135；耐力 1974；爆击 112；急速 60 |
| 49803 | 红玉骨戒 | 熔炉之主加弗斯特 | 护甲 / 其它 | 手指 | finger1 | socket | partial | missing deterministic SimC variant preset | - | 敏捷 55；耐力 721；爆击 46；急速 50 | 敏捷 62；耐力 848；爆击 52；急速 56 | 敏捷 70；耐力 995；爆击 58；急速 63 | - |
| 49804 | 闪亮的镜盔 | 熔炉之主加弗斯特 | 护甲 / 锁甲 | 头部 | head | socket | partial | missing deterministic SimC variant preset | - | 耐力 1246；急速 54；全能 73 | 耐力 1471；急速 59；全能 79 | 耐力 1730；急速 64；全能 84 | - |
| 49805 | 踏冰软鞋 | 熔炉之主加弗斯特 | 护甲 / 布甲 | 脚部 | feet | - | partial | missing deterministic SimC variant preset | - | 智力 73；耐力 961；爆击 58；急速 49 | 智力 82；耐力 1130；爆击 63；急速 53 | 智力 93；耐力 1326；爆击 67；急速 56 | - |
| 49806 | 鞭笞者的黑色腰带 | 熔炉之主加弗斯特 | 护甲 / 皮甲 | 腰部 | waist | - | partial | missing deterministic SimC variant preset | - | 耐力 961；爆击 52；急速 56 | 耐力 1130；爆击 55；急速 60 | 耐力 1326；爆击 59；急速 64 | - |
| 49807 | 科瑞克的甲虫刀 | 伊克和科瑞克 | 武器 / 匕首 | 单手 | main_hand | - | partial | missing deterministic SimC variant preset | 298 | 敏捷 49；耐力 640；爆击 33；急速 39 | 敏捷 55；耐力 754；爆击 35；急速 42 | 敏捷 62；耐力 884；爆击 38；急速 45 | 敏捷 67；耐力 987；爆击 39；急速 47 |
| 49808 | 曲金腰带 | 伊克和科瑞克 | 护甲 / 板甲 | 腰部 | waist | - | partial | missing deterministic SimC variant preset | 289 | 耐力 961；爆击 49；急速 58 | 耐力 1130；爆击 53；急速 63 | 耐力 1326；爆击 56；急速 67 | - |
| 49809 | 墓苔护腕 | 伊克和科瑞克 | 护甲 / 布甲 | 腕部 | wrist | - | partial | missing deterministic SimC variant preset | - | 智力 55；耐力 721；急速 39；全能 42 | 智力 62；耐力 848；急速 41；全能 45 | 智力 70；耐力 995；急速 44；全能 48 | - |
| 49810 | 凶尸腰索 | 伊克和科瑞克 | 护甲 / 锁甲 | 腰部 | waist | - | verified | - | 289 | 耐力 961；爆击 56；急速 52 | 耐力 1130；爆击 60；急速 55 | 耐力 1326；爆击 64；急速 59 | - |
| 49811 | 黑色龙皮褶裙 | 伊克和科瑞克 | 护甲 / 锁甲 | 腿部 | legs | - | partial | missing deterministic SimC variant preset | 289 | 耐力 1281；爆击 84；全能 59 | 耐力 1507；爆击 90；全能 64 | 耐力 1768；爆击 96；全能 68 | - |
| 49812 | 被盗的婚戒 | 伊克和科瑞克 | 护甲 / 其它 | 手指 | finger1 | socket | verified | - | 289,276 | 耐力 721；爆击 139；急速 105 | 耐力 848；爆击 156；急速 117 | 耐力 995；爆击 173；急速 130 | - |
| 49813 | 霜灾火枪 | 天灾领主泰兰努斯 | 武器 / 枪械 | 远程 | main_hand | - | partial | missing deterministic SimC variant preset | - | 敏捷 97；耐力 1281；急速 90；精通 53 | 敏捷 110；耐力 1507；急速 97；精通 57 | 敏捷 124；耐力 1768；急速 103；精通 61 | 敏捷 135；耐力 1974；急速 108；精通 64 |
| 49816 | 天灾领主的冰封胸甲 | 天灾领主泰兰努斯 | 护甲 / 板甲 | 胸部 | chest | socket | partial | missing deterministic SimC variant preset | - | 耐力 1228；爆击 55；闪避 75；招架 62 | 耐力 1452；爆击 59；闪避 81；招架 67 | 耐力 1711；爆击 63；闪避 86；招架 72 | - |
| 49817 | 蓬松的龙皮护腿 | 天灾领主泰兰努斯 | 护甲 / 皮甲 | 腿部 | legs | - | verified | - | 289 | 耐力 1281；急速 69；精通 75 | 耐力 1507；急速 74；精通 80 | 耐力 1768；急速 79；精通 86 | - |
| 49818 | 苦痛刺圈 | 天灾领主泰兰努斯 | 护甲 / 其它 | 颈部 | neck | socket | partial | missing deterministic SimC variant preset | - | 力量 55；耐力 721；爆击 56；急速 37 | 力量 62；耐力 848；爆击 62；急速 42 | 力量 70；耐力 995；爆击 69；急速 46 | - |
| 49819 | 骷髅领主的狼牙头盔 | 天灾领主泰兰努斯 | 护甲 / 板甲 | 头部 | head | - | partial | missing deterministic SimC variant preset | - | 耐力 1281；爆击 66；急速 78 | 耐力 1507；爆击 70；急速 84 | 耐力 1768；爆击 75；急速 89 | - |
| 49820 | 古德利亚的幽灵护腕 | 天灾领主泰兰努斯 | 护甲 / 锁甲 | 腕部 | wrist | - | partial | missing deterministic SimC variant preset | - | 耐力 721；爆击 32；急速 60 | 耐力 848；爆击 34；急速 64 | 耐力 995；爆击 37；急速 69 | - |
| 49821 | 冰魂护佑者 | 天灾领主泰兰努斯 | 护甲 / 盾牌 | 副手 | off_hand | - | partial | missing deterministic SimC variant preset | - | 力量 49；智力 149；耐力 640；爆击 32；全能 39 | 力量 55；智力 168；耐力 754；爆击 34；全能 41 | 力量 62；智力 190；耐力 884；爆击 36；全能 44 | - |
| 49822 | 霜织丝裤 | 天灾领主泰兰努斯 | 护甲 / 布甲 | 腿部 | legs | socket | partial | missing deterministic SimC variant preset | - | 智力 97；耐力 1246；爆击 67；急速 72 | 智力 110；耐力 1471；爆击 73；急速 77 | 智力 124；耐力 1730；爆击 78；急速 82 | - |
| 49823 | 阵亡主教斗篷 | 天灾领主泰兰努斯 | 护甲 / 布甲 | 背部 | back | - | partial | missing deterministic SimC variant preset | - | 耐力 721；爆击 37；全能 44 | 耐力 848；爆击 40；全能 47 | 耐力 995；爆击 42；全能 50 | - |
| 49824 | 被遗弃的瓦格里之角 | 天灾领主泰兰努斯 | 护甲 / 锁甲 | 头部 | head | - | partial | missing deterministic SimC variant preset | 289 | 耐力 1281；爆击 66；急速 78 | 耐力 1507；爆击 70；急速 84 | 耐力 1768；爆击 75；急速 89 | - |
| 49825 | 灰骨法袍 | 天灾领主泰兰努斯 | 护甲 / 布甲 | 胸部 | chest | - | partial | missing deterministic SimC variant preset | - | 智力 97；耐力 1281；爆击 69；急速 75 | 智力 110；耐力 1507；爆击 74；急速 80 | 智力 124；耐力 1768；爆击 79；急速 86 | - |
| 49826 | 蒙霜披风 | 天灾领主泰兰努斯 | 护甲 / 锁甲 | 胸部 | chest | - | partial | missing deterministic SimC variant preset | - | 耐力 1281；急速 77；全能 63 | 耐力 1507；急速 83；全能 68 | 耐力 1768；急速 88；全能 72 | - |
| 50227 | 医用长针 | 熔炉之主加弗斯特 | 武器 / 匕首 | 单手 | main_hand | - | partial | missing deterministic SimC variant preset | 298 | 智力 235；耐力 640；爆击 42；全能 30 | 智力 265；耐力 754；爆击 45；全能 32 | 智力 299；耐力 884；爆击 48；全能 34 | 智力 325；耐力 987；爆击 50；全能 36 |
| 50228 | 尖刺伊米亚颈饰 | 熔炉之主加弗斯特 | 护甲 / 其它 | 颈部 | neck | socket | partial | missing deterministic SimC variant preset | 289 | 耐力 721；爆击 157；急速 87 | 耐力 848；爆击 176；急速 98 | 耐力 995；爆击 195；急速 108 | - |
| 50229 | 寒冰深渊腿甲 | 熔炉之主加弗斯特 | 护甲 / 板甲 | 腿部 | legs | socket | partial | missing deterministic SimC variant preset | - | 耐力 1255；急速 70；全能 72 | 耐力 1480；急速 75；全能 77 | 耐力 1740；急速 80；全能 82 | - |
| 50230 | 轻盈追踪臂铠 | 熔炉之主加弗斯特 | 护甲 / 板甲 | 腕部 | wrist | - | partial | missing deterministic SimC variant preset | - | 耐力 721；爆击 40；急速 40 | 耐力 848；爆击 43；急速 43 | 耐力 995；爆击 46；急速 46 | - |
| 50233 | 被遗弃的瓦格里肩甲 | 熔炉之主加弗斯特 | 护甲 / 锁甲 | 肩部 | shoulder | - | partial | missing deterministic SimC variant preset | - | 耐力 961；爆击 70；急速 38 | 耐力 1130；爆击 75；急速 40 | 耐力 1326；爆击 80；急速 43 | - |
| 50234 | 霜血肩甲 | 熔炉之主加弗斯特 | 护甲 / 板甲 | 肩部 | shoulder | - | verified | - | 289 | 耐力 961；爆击 38；精通 70 | 耐力 1130；爆击 40；精通 75 | 耐力 1326；爆击 43；精通 80 | - |
| 50235 | 伊克的烂指 | 伊克和科瑞克 | 护甲 / 其它 | 饰品 | trinket1 | - | partial | missing deterministic SimC variant preset | - | 闪避 102 | 闪避 110 | 闪避 117 | 闪避 122 |
| 50259 | 永冻冰晶 | 天灾领主泰兰努斯 | 护甲 / 其它 | 饰品 | trinket1 | - | partial | missing deterministic SimC variant preset | - | 智力 93 | 智力 104 | 智力 118 | 智力 128 |
| 50262 | 邪冰重弩 | 伊克和科瑞克 | 武器 / 弩 | 远程 | main_hand | - | partial | missing deterministic SimC variant preset | - | 敏捷 97；耐力 1217；爆击 58；急速 80 | 敏捷 110；耐力 1432；爆击 62；急速 86 | 敏捷 124；耐力 1680；爆击 66；急速 92 | 敏捷 135；耐力 1875；爆击 69；急速 96 |
| 50263 | 降魔束带 | 伊克和科瑞克 | 护甲 / 布甲 | 腰部 | waist | - | partial | missing deterministic SimC variant preset | - | 智力 73；耐力 961；急速 52；全能 56 | 智力 82；耐力 1130；急速 55；全能 60 | 智力 93；耐力 1326；急速 59；全能 64 | - |
| 50264 | 碎羽护腕 | 伊克和科瑞克 | 护甲 / 皮甲 | 腕部 | wrist | - | partial | missing deterministic SimC variant preset | 289 | 耐力 721；爆击 47；急速 33 | 耐力 848；爆击 51；急速 36 | 耐力 995；爆击 54；急速 38 | - |
| 50265 | 硝制食尸鬼皮护腿 | 伊克和科瑞克 | 护甲 / 锁甲 | 腿部 | legs | - | partial | missing deterministic SimC variant preset | - | 耐力 1281；急速 75；全能 67 | 耐力 1507；急速 81；全能 71 | 耐力 1768；急速 86；全能 76 | - |
| 50266 | 上古冰熊之皮 | 伊克和科瑞克 | 护甲 / 布甲 | 胸部 | chest | - | partial | missing deterministic SimC variant preset | - | 智力 97；耐力 1281；爆击 82；急速 55 | 智力 110；耐力 1507；爆击 88；急速 59 | 智力 124；耐力 1768；爆击 94；急速 63 | - |
| 50267 | 枭首 | 天灾领主泰兰努斯 | 武器 / 斧 | 双手 | main_hand | socket | partial | missing deterministic SimC variant preset | - | 力量 93；耐力 1281；爆击 50；急速 82 | 力量 106；耐力 1507；爆击 54；急速 88 | 力量 120；耐力 1768；爆击 59；急速 94 | 力量 131；耐力 1974；爆击 62；急速 98 |
| 50268 | 霜牙之爪 | 天灾领主泰兰努斯 | 武器 / 剑 | 单手 | main_hand | - | partial | missing deterministic SimC variant preset | - | 力量 49；耐力 640；闪避 45；招架 22 | 力量 55；耐力 754；闪避 49；招架 23 | 力量 62；耐力 884；闪避 52；招架 25 | 力量 67；耐力 987；闪避 54；招架 26 |
| 50269 | 缝合场护腿 | 天灾领主泰兰努斯 | 护甲 / 皮甲 | 腿部 | legs | - | partial | missing deterministic SimC variant preset | - | 耐力 1281；爆击 72；急速 72 | 耐力 1507；爆击 77；急速 77 | 耐力 1768；爆击 82；急速 82 | - |
| 50270 | 腐甲腰带 | 天灾领主泰兰努斯 | 护甲 / 锁甲 | 腰部 | waist | - | partial | missing deterministic SimC variant preset | - | 耐力 961；爆击 47；急速 58 | 耐力 1130；爆击 51；急速 62 | 耐力 1326；爆击 54；急速 66 | - |
| 50271 | 败坏灵魂指环 | 天灾领主泰兰努斯 | 护甲 / 其它 | 手指 | finger1 | socket | partial | missing deterministic SimC variant preset | - | 敏捷 55；耐力 721；爆击 54；急速 39 | 敏捷 62；耐力 848；爆击 61；急速 44 | 敏捷 70；耐力 995；爆击 68；急速 49 | - |
| 50272 | 冰龙胸骨 | 天灾领主泰兰努斯 | 护甲 / 板甲 | 胸部 | chest | - | partial | missing deterministic SimC variant preset | - | 耐力 1281；爆击 75；急速 69 | 耐力 1507；爆击 80；急速 74 | 耐力 1768；爆击 86；急速 79 | - |
| 50273 | 雕纹石像鬼骨杖 | 天灾领主泰兰努斯 | 武器 / 法杖 | 双手 | main_hand | - | partial | missing deterministic SimC variant preset | - | 智力 335；耐力 1281；爆击 101；急速 77 | 智力 378；耐力 1507；爆击 109；急速 83 | 智力 427；耐力 1768；爆击 116；急速 88 | 智力 465；耐力 1974；爆击 121；急速 92 |
| 50283 | 泥流之靴 | 天灾领主泰兰努斯 | 护甲 / 锁甲 | 脚部 | feet | - | partial | missing deterministic SimC variant preset | - | 耐力 961；爆击 51；急速 55 | 耐力 1130；爆击 55；急速 60 | 耐力 1326；爆击 59；急速 64 | - |
| 50284 | 锈蚀的冰封护手 | 天灾领主泰兰努斯 | 护甲 / 板甲 | 手部 | hands | - | partial | missing deterministic SimC variant preset | - | 耐力 961；爆击 54；全能 54 | 耐力 1130；爆击 58；全能 58 | 耐力 1326；爆击 62；全能 62 | - |
| 50285 | 冰缚铜甲 | 天灾领主泰兰努斯 | 护甲 / 板甲 | 胸部 | chest | - | partial | missing deterministic SimC variant preset | - | 耐力 1281；爆击 105；闪避 60 | 耐力 1507；爆击 113；闪避 64 | 耐力 1768；爆击 121；闪避 68 | - |
| 50286 | 主教的雪鞋 | 天灾领主泰兰努斯 | 护甲 / 布甲 | 脚部 | feet | - | partial | missing deterministic SimC variant preset | - | 智力 73；耐力 961；急速 51；全能 55 | 智力 82；耐力 1130；急速 55；全能 60 | 智力 93；耐力 1326；急速 59；全能 64 | - |
| 252421 | 腐烂液球 | 伊克和科瑞克 | 护甲 / 其它 | 饰品 | trinket1 | - | partial | missing deterministic SimC variant preset | 298 | no-static-stat | no-static-stat | no-static-stat | no-static-stat |

## Skyreach / 通天峰

| itemId | 装备 | Boss/source | 类型 | inventory | slot | socket | current state | blocker | observed ilvl | 263 | 276 | 289 | 298 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 252411 | 光耀日长石 | 鲁克兰 | 护甲 / 其它 | 饰品 | trinket1 | - | partial | missing deterministic SimC variant preset | 298 | 智力 93 | 智力 104 | 智力 118 | 智力 128 |
| 252418 | 太阳之核点燃器 | 阿拉卡纳斯 | 护甲 / 其它 | 饰品 | trinket1 | - | partial | missing deterministic SimC variant preset | - | no-static-stat | no-static-stat | no-static-stat | no-static-stat |
| 252420 | 太阳耀斑棱镜 | 高阶贤者维里克斯 | 护甲 / 其它 | 饰品 | trinket1 | - | partial | missing deterministic SimC variant preset | 298 | no-static-stat | no-static-stat | no-static-stat | no-static-stat |
| 258046 | 斩轮大剑 | 兰吉特 | 武器 / 剑 | 双手 | main_hand | - | partial | missing deterministic SimC variant preset | - | 力量 97；耐力 1281；精通 78；全能 66 | 力量 110；耐力 1507；精通 84；全能 70 | 力量 124；耐力 1768；精通 89；全能 75 | 力量 135；耐力 1974；精通 93；全能 79 |
| 258047 | 狂怒构装体之杖 | 阿拉卡纳斯 | 武器 / 法杖 | 双手 | main_hand | - | partial | missing deterministic SimC variant preset | - | 智力 335；耐力 1281；急速 75；精通 69 | 智力 378；耐力 1507；急速 80；精通 74 | 智力 427；耐力 1768；急速 86；精通 79 | 智力 465；耐力 1974；急速 90；精通 82 |
| 258048 | 折喙者弯刀 | 鲁克兰 | 武器 / 剑 | 单手 | main_hand | - | partial | missing deterministic SimC variant preset | - | 力量 49；耐力 640；爆击 37；全能 34 | 力量 55；耐力 754；爆击 40；全能 37 | 力量 62；耐力 884；爆击 43；全能 39 | 力量 67；耐力 987；爆击 45；全能 41 |
| 258049 | 维里克斯的不屈壁垒 | 高阶贤者维里克斯 | 护甲 / 盾牌 | 副手 | off_hand | - | partial | missing deterministic SimC variant preset | - | 力量 49；智力 149；耐力 640；爆击 37；精通 34 | 力量 55；智力 168；耐力 754；爆击 40；精通 37 | 力量 62；智力 190；耐力 884；爆击 43；精通 39 | - |
| 258050 | 高阶贤者的奥法拳套 | 高阶贤者维里克斯 | 武器 / 拳套 | 单手 | main_hand | - | partial | missing deterministic SimC variant preset | 298 | 智力 235；耐力 640；爆击 37；急速 34 | 智力 265；耐力 754；爆击 40；急速 37 | 智力 299；耐力 884；爆击 43；急速 39 | 智力 325；耐力 987；爆击 45；急速 41 |
| 258218 | 碎天者之刃 | 兰吉特 | 武器 / 剑 | 单手 | main_hand | - | verified | - | 298 | 智力 235；耐力 640；爆击 33；精通 39 | 智力 265；耐力 754；爆击 35；精通 42 | 智力 299；耐力 884；爆击 38；精通 45 | 智力 325；耐力 987；爆击 39；精通 47 |
| 258412 | 塑风者十字弩 | 兰吉特 | 武器 / 弩 | 远程 | main_hand | - | partial | missing deterministic SimC variant preset | 298 | 敏捷 97；耐力 1281；爆击 59；全能 84 | 敏捷 110；耐力 1507；爆击 64；全能 90 | 敏捷 124；耐力 1768；爆击 68；全能 96 | 敏捷 135；耐力 1974；爆击 71；全能 101 |
| 258436 | 灼日之锋 | 阿拉卡纳斯 | 武器 / 匕首 | 单手 | main_hand | - | partial | missing deterministic SimC variant preset | - | 敏捷 49；耐力 640；急速 45；精通 27 | 敏捷 55；耐力 754；急速 48；精通 29 | 敏捷 62；耐力 884；急速 52；精通 31 | 敏捷 67；耐力 987；急速 54；精通 32 |
| 258438 | 炽热日爪 | 鲁克兰 | 武器 / 拳套 | 单手 | main_hand | - | partial | missing deterministic SimC variant preset | 298 | 敏捷 49；耐力 640；急速 27；精通 45 | 敏捷 55；耐力 754；急速 29；精通 48 | 敏捷 62；耐力 884；急速 31；精通 52 | 敏捷 67；耐力 987；急速 32；精通 54 |
| 258472 | 鲁克兰的阳炎圣物 | 鲁克兰 | 护甲 / 其它 | 副手物品 | off_hand | - | partial | missing deterministic SimC variant preset | - | 智力 149；耐力 640；急速 27；精通 45 | 智力 168；耐力 754；急速 29；精通 48 | 智力 190；耐力 884；急速 31；精通 52 | - |
| 258484 | 维里克斯的炎枪 | 高阶贤者维里克斯 | 武器 / 长柄武器 | 双手 | main_hand | - | partial | missing deterministic SimC variant preset | - | 敏捷 97；耐力 1281；爆击 93；急速 50 | 敏捷 110；耐力 1507；爆击 100；急速 54 | 敏捷 124；耐力 1768；爆击 107；急速 58 | 敏捷 135；耐力 1974；爆击 112；急速 60 |
| 258574 | 流光裹腿 | 兰吉特 | 护甲 / 布甲 | 腿部 | legs | - | partial | missing deterministic SimC variant preset | - | 智力 97；耐力 1281；急速 78；全能 66 | 智力 110；耐力 1507；急速 84；全能 70 | 智力 124；耐力 1768；急速 89；全能 75 | - |
| 258575 | 刚鳞大氅 | 兰吉特 | 护甲 / 布甲 | 背部 | back | - | verified | - | 289 | 耐力 721；爆击 44；精通 37 | 耐力 848；爆击 47；精通 40 | 耐力 995；爆击 50；精通 42 | - |
| 258576 | 锐眼胸甲 | 阿拉卡纳斯 | 护甲 / 锁甲 | 胸部 | chest | - | partial | missing deterministic SimC variant preset | - | 耐力 1281；爆击 78；急速 66 | 耐力 1507；爆击 84；急速 70 | 耐力 1768；爆击 89；急速 75 | - |
| 258577 | 炽燃焦点长靴 | 阿拉卡纳斯 | 护甲 / 皮甲 | 脚部 | feet | - | partial | missing deterministic SimC variant preset | - | 耐力 961；爆击 56；精通 52 | 耐力 1130；爆击 60；精通 55 | 耐力 1326；爆击 64；精通 59 | - |
| 258578 | 缚光者护肩 | 阿拉卡纳斯 | 护甲 / 布甲 | 肩部 | shoulder | - | partial | missing deterministic SimC variant preset | - | 智力 73；耐力 961；急速 58；精通 49 | 智力 82；耐力 1130；急速 63；精通 53 | 智力 93；耐力 1326；急速 67；精通 56 | - |
| 258579 | 裂胆巨盔 | 阿拉卡纳斯 | 护甲 / 板甲 | 头部 | head | - | partial | missing deterministic SimC variant preset | - | 耐力 1281；精通 84；全能 59 | 耐力 1507；精通 90；全能 64 | 耐力 1768；精通 96；全能 68 | - |
| 258580 | 闪耀光芒护腕 | 鲁克兰 | 护甲 / 布甲 | 腕部 | wrist | - | partial | missing deterministic SimC variant preset | - | 智力 55；耐力 721；精通 49；全能 32 | 智力 62；耐力 848；精通 53；全能 34 | 智力 70；耐力 995；精通 56；全能 36 | - |
| 258581 | 血羽披肩 | 鲁克兰 | 护甲 / 皮甲 | 肩部 | shoulder | - | partial | missing deterministic SimC variant preset | 289 | 耐力 961；精通 68；全能 40 | 耐力 1130；精通 73；全能 43 | 耐力 1326；精通 78；全能 46 | - |
| 258582 | 刚鳞长靴 | 鲁克兰 | 护甲 / 锁甲 | 脚部 | feet | - | partial | missing deterministic SimC variant preset | - | 耐力 961；精通 58；全能 49 | 耐力 1130；精通 63；全能 53 | 耐力 1326；精通 67；全能 56 | - |
| 258583 | 猩红手甲 | 鲁克兰 | 护甲 / 板甲 | 手部 | hands | - | partial | missing deterministic SimC variant preset | 289 | 耐力 961；爆击 61；精通 47 | 耐力 1130；爆击 65；精通 50 | 耐力 1326；爆击 70；精通 54 | - |
| 258584 | 缚光者便鞋 | 高阶贤者维里克斯 | 护甲 / 布甲 | 脚部 | feet | - | partial | missing deterministic SimC variant preset | - | 智力 73；耐力 961；急速 56；精通 52 | 智力 82；耐力 1130；急速 60；精通 55 | 智力 93；耐力 1326；急速 64；精通 59 | - |
| 258585 | 锐眼头盔 | 高阶贤者维里克斯 | 护甲 / 锁甲 | 头部 | head | - | partial | missing deterministic SimC variant preset | - | 耐力 1281；爆击 78；精通 66 | 耐力 1507；爆击 84；精通 70 | 耐力 1768；爆击 89；精通 75 | - |
| 258586 | 血羽护胸 | 高阶贤者维里克斯 | 护甲 / 皮甲 | 胸部 | chest | - | partial | missing deterministic SimC variant preset | 289 | 耐力 1281；急速 84；精通 59 | 耐力 1507；急速 90；精通 64 | 耐力 1768；急速 96；精通 68 | - |
| 258587 | 灼烧射线肩甲 | 高阶贤者维里克斯 | 护甲 / 板甲 | 肩部 | shoulder | - | partial | missing deterministic SimC variant preset | - | 耐力 961；急速 49；精通 58 | 耐力 1130；急速 53；精通 63 | 耐力 1326；急速 56；精通 67 | - |

## Seat of the Triumvirate / 执政团之座

| itemId | 装备 | Boss/source | 类型 | inventory | slot | socket | current state | blocker | observed ilvl | 263 | 276 | 289 | 298 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 151299 | 总督的幽影护肩 | 总督奈扎尔 | 护甲 / 布甲 | 肩部 | shoulder | - | partial | missing deterministic SimC variant preset | - | 智力 73；耐力 961；急速 61；精通 46 | 智力 82；耐力 1130；急速 66；精通 49 | 智力 93；耐力 1326；急速 71；精通 53 | - |
| 151300 | 晋升者裹手 | 晋升者祖拉尔 | 护甲 / 布甲 | 手部 | hands | - | partial | missing deterministic SimC variant preset | 289 | 智力 73；耐力 961；爆击 58；精通 49 | 智力 82；耐力 1130；爆击 63；精通 53 | 智力 93；耐力 1326；爆击 67；精通 56 | - |
| 151301 | 滋长绝望软鞋 | 鲁拉 | 护甲 / 布甲 | 脚部 | feet | - | partial | missing deterministic SimC variant preset | - | 智力 73；耐力 961；急速 38；全能 69 | 智力 82；耐力 1130；急速 41；全能 74 | 智力 93；耐力 1326；急速 44；全能 79 | - |
| 151302 | 瓦解现实束带 | 鲁拉 | 护甲 / 布甲 | 腰部 | waist | - | partial | missing deterministic SimC variant preset | - | 智力 73；耐力 961；精通 57；全能 51 | 智力 82；耐力 1130；精通 61；全能 54 | 智力 93；耐力 1326；精通 65；全能 58 | - |
| 151303 | 虚空扭曲者长袍 | 萨普瑞什 | 护甲 / 布甲 | 胸部 | chest | - | partial | missing deterministic SimC variant preset | - | 智力 97；耐力 1281；爆击 78；急速 66 | 智力 110；耐力 1507；爆击 84；急速 70 | 智力 124；耐力 1768；爆击 89；急速 75 | - |
| 151304 | 征服者的长裤 | 晋升者祖拉尔 | 护甲 / 布甲 | 腿部 | legs | - | partial | missing deterministic SimC variant preset | - | 智力 97；耐力 1281；精通 78；全能 66 | 智力 110；耐力 1507；精通 84；全能 70 | 智力 124；耐力 1768；精通 89；全能 75 | - |
| 151305 | 熵能裹腕 | 总督奈扎尔 | 护甲 / 布甲 | 腕部 | wrist | - | partial | missing deterministic SimC variant preset | 289 | 智力 55；耐力 721；急速 33；精通 47 | 智力 62；耐力 848；急速 36；精通 51 | 智力 70；耐力 995；急速 38；精通 54 | - |
| 151307 | 虚空追猎者的契约 | 萨普瑞什 | 护甲 / 其它 | 饰品 | trinket1 | - | partial | missing deterministic SimC variant preset | - | no-static-stat | no-static-stat | no-static-stat | no-static-stat |
| 151308 | 艾瑞达斯贵族印戒 | 晋升者祖拉尔 | 护甲 / 其它 | 手指 | finger1 | socket | verified | - | 289,276 | 耐力 721；爆击 95；全能 149 | 耐力 848；爆击 106；全能 167 | 耐力 995；爆击 118；全能 185 | - |
| 151309 | 扭曲虚空项链 | 总督奈扎尔 | 护甲 / 其它 | 颈部 | neck | socket | partial | missing deterministic SimC variant preset | 289 | 耐力 721；急速 137；全能 107 | 耐力 848；急速 153；全能 120 | 耐力 995；急速 170；全能 133 | - |
| 151310 | 现实突破者 | 总督奈扎尔 | 护甲 / 其它 | 饰品 | trinket1 | - | partial | missing deterministic SimC variant preset | - | 智力 93 | 智力 104 | 智力 118 | 智力 128 |
| 151311 | 执政团指轮 | 鲁拉 | 护甲 / 其它 | 手指 | finger1 | socket | verified | - | 289,276 | 耐力 721；急速 139；全能 105 | 耐力 848；急速 156；全能 117 | 耐力 995；急速 173；全能 130 | - |
| 151312 | 纯净虚空之瓶 | 晋升者祖拉尔 | 护甲 / 其它 | 饰品 | trinket1 | - | partial | missing deterministic SimC variant preset | - | no-static-stat | no-static-stat | no-static-stat | no-static-stat |
| 151313 | 虚空之拥外套 | 鲁拉 | 护甲 / 皮甲 | 胸部 | chest | - | verified | - | 289 | 耐力 1281；爆击 51；全能 92 | 耐力 1507；爆击 55；全能 99 | 耐力 1768；爆击 59；全能 106 | - |
| 151314 | 位移追猎者皮裤 | 萨普瑞什 | 护甲 / 皮甲 | 腿部 | legs | - | partial | missing deterministic SimC variant preset | - | 耐力 1281；精通 86；全能 57 | 耐力 1507；精通 92；全能 62 | 耐力 1768；精通 99；全能 66 | - |
| 151315 | 黑暗束缚护腕 | 晋升者祖拉尔 | 护甲 / 皮甲 | 腕部 | wrist | - | partial | missing deterministic SimC variant preset | - | 耐力 721；爆击 30；急速 51 | 耐力 848；爆击 32；急速 54 | 耐力 995；爆击 34；急速 58 | - |
| 151316 | 幽影鞭笞者腰带 | 总督奈扎尔 | 护甲 / 皮甲 | 腰部 | waist | - | partial | missing deterministic SimC variant preset | - | 耐力 961；急速 45；全能 63 | 耐力 1130；急速 48；全能 68 | 耐力 1326；急速 51；全能 72 | - |
| 151317 | 渗透恐惧薄靴 | 总督奈扎尔 | 护甲 / 皮甲 | 脚部 | feet | - | partial | missing deterministic SimC variant preset | - | 耐力 961；精通 45；全能 63 | 耐力 1130；精通 48；全能 68 | 耐力 1326；精通 51；全能 72 | - |
| 151318 | 黑暗遮蔽手套 | 萨普瑞什 | 护甲 / 皮甲 | 手部 | hands | - | partial | missing deterministic SimC variant preset | - | 耐力 961；爆击 49；急速 58 | 耐力 1130；爆击 53；急速 63 | 耐力 1326；爆击 56；急速 67 | - |
| 151319 | 暮光之锋护肩 | 鲁拉 | 护甲 / 皮甲 | 肩部 | shoulder | - | partial | missing deterministic SimC variant preset | - | 耐力 961；爆击 60；精通 48 | 耐力 1130；爆击 64；精通 51 | 耐力 1326；爆击 69；精通 55 | - |
| 151320 | 虚空涂层战靴 | 晋升者祖拉尔 | 护甲 / 锁甲 | 脚部 | feet | - | partial | missing deterministic SimC variant preset | - | 耐力 961；急速 61；精通 47 | 耐力 1130；急速 65；精通 50 | 耐力 1326；急速 70；精通 54 | - |
| 151321 | 黯牙鳞甲护腕 | 萨普瑞什 | 护甲 / 锁甲 | 腕部 | wrist | - | partial | missing deterministic SimC variant preset | - | 耐力 721；爆击 51；精通 30 | 耐力 848；爆击 54；精通 32 | 耐力 995；爆击 58；精通 34 | - |
| 151322 | 虚空之触手套 | 鲁拉 | 护甲 / 锁甲 | 手部 | hands | - | partial | missing deterministic SimC variant preset | - | 耐力 961；精通 46；全能 61 | 耐力 1130；精通 49；全能 66 | 耐力 1326；精通 53；全能 71 | - |
| 151323 | 虚空猎手肩甲 | 萨普瑞什 | 护甲 / 锁甲 | 肩部 | shoulder | - | partial | missing deterministic SimC variant preset | - | 耐力 961；急速 58；精通 49 | 耐力 1130；急速 63；精通 53 | 耐力 1326；急速 67；精通 56 | - |
| 151324 | 幽影血统头盔 | 鲁拉 | 护甲 / 锁甲 | 头部 | head | - | partial | missing deterministic SimC variant preset | - | 耐力 1281；急速 79；精通 65 | 耐力 1507；急速 85；精通 69 | 耐力 1768；急速 90；精通 74 | - |
| 151325 | 虚空之环长袍 | 总督奈扎尔 | 护甲 / 锁甲 | 胸部 | chest | - | partial | missing deterministic SimC variant preset | - | 耐力 1281；精通 84；全能 59 | 耐力 1507；精通 90；全能 64 | 耐力 1768；精通 96；全能 68 | - |
| 151326 | 约束能量腰带 | 晋升者祖拉尔 | 护甲 / 锁甲 | 腰部 | waist | - | partial | missing deterministic SimC variant preset | - | 耐力 961；急速 45；全能 63 | 耐力 1130；急速 48；全能 68 | 耐力 1326；急速 51；全能 72 | - |
| 151327 | 影卫腰带 | 萨普瑞什 | 护甲 / 板甲 | 腰部 | waist | - | partial | missing deterministic SimC variant preset | - | 耐力 961；急速 42；精通 65 | 耐力 1130；急速 45；精通 70 | 耐力 1326；急速 48；精通 75 | - |
| 151328 | 失落希望臂甲 | 鲁拉 | 护甲 / 板甲 | 腕部 | wrist | - | partial | missing deterministic SimC variant preset | - | 耐力 721；爆击 29；急速 51 | 耐力 848；爆击 32；急速 55 | 耐力 995；爆击 34；急速 59 | - |
| 151329 | 黑暗之触胸甲 | 晋升者祖拉尔 | 护甲 / 板甲 | 胸部 | chest | - | partial | missing deterministic SimC variant preset | - | 耐力 1281；急速 64；精通 80 | 耐力 1507；急速 68；精通 86 | 耐力 1768；急速 73；精通 92 | - |
| 151330 | 陷阱干扰靴 | 萨普瑞什 | 护甲 / 板甲 | 脚部 | feet | - | partial | missing deterministic SimC variant preset | - | 耐力 961；精通 45；全能 63 | 耐力 1130；精通 48；全能 68 | 耐力 1326；精通 51；全能 72 | - |
| 151331 | 破碎者护肩 | 晋升者祖拉尔 | 护甲 / 板甲 | 肩部 | shoulder | - | partial | missing deterministic SimC variant preset | - | 耐力 961；爆击 46；全能 61 | 耐力 1130；爆击 49；全能 66 | 耐力 1326；爆击 53；全能 71 | - |
| 151332 | 灵爪手甲 | 总督奈扎尔 | 护甲 / 板甲 | 手部 | hands | - | partial | missing deterministic SimC variant preset | - | 耐力 961；急速 58；全能 49 | 耐力 1130；急速 63；全能 53 | 耐力 1326；急速 67；全能 56 | - |
| 151333 | 黑暗使徒之冠 | 总督奈扎尔 | 护甲 / 板甲 | 头部 | head | - | partial | missing deterministic SimC variant preset | - | 耐力 1281；爆击 84；精通 59 | 耐力 1507；爆击 90；精通 64 | 耐力 1768；爆击 96；精通 68 | - |
| 151336 | 虚空之鞭兜帽 | 晋升者祖拉尔 | 护甲 / 皮甲 | 头部 | head | - | partial | missing deterministic SimC variant preset | - | 耐力 1281；爆击 78；急速 66 | 耐力 1507；爆击 84；急速 70 | 耐力 1768；爆击 89；急速 75 | - |
| 151337 | 织影者之冠 | 萨普瑞什 | 护甲 / 布甲 | 头部 | head | - | partial | missing deterministic SimC variant preset | - | 智力 97；耐力 1281；爆击 59；精通 84 | 智力 110；耐力 1507；爆击 64；精通 90 | 智力 124；耐力 1768；爆击 68；精通 96 | - |
| 151338 | 黑暗位移护腿 | 总督奈扎尔 | 护甲 / 锁甲 | 腿部 | legs | - | partial | missing deterministic SimC variant preset | - | 耐力 1281；爆击 83；急速 60 | 耐力 1507；爆击 89；急速 65 | 耐力 1768；爆击 95；急速 69 | - |
| 151339 | 终极牺牲腿甲 | 鲁拉 | 护甲 / 板甲 | 腿部 | legs | - | partial | missing deterministic SimC variant preset | - | 耐力 1281；爆击 76；精通 68 | 耐力 1507；爆击 81；精通 73 | 耐力 1768；爆击 87；精通 78 | - |
| 151340 | 鲁拉的回响 | 鲁拉 | 护甲 / 其它 | 饰品 | trinket1 | - | partial | missing deterministic SimC variant preset | - | 智力 93 | 智力 104 | 智力 118 | 智力 128 |
| 258514 | 祖拉尔的暗影尖塔 | 晋升者祖拉尔 | 武器 / 法杖 | 双手 | main_hand | - | partial | missing deterministic SimC variant preset | - | 智力 335；耐力 1281；爆击 56；精通 87 | 智力 378；耐力 1507；爆击 60；精通 93 | 智力 427；耐力 1768；爆击 65；精通 100 | 智力 465；耐力 1974；爆击 67；精通 104 |
| 258516 | 萨普瑞什的凝视魔棒 | 萨普瑞什 | 武器 / 魔杖 | 远程 | main_hand | - | partial | missing deterministic SimC variant preset | - | 智力 235；耐力 640；爆击 45；全能 27 | 智力 265；耐力 754；爆击 48；全能 29 | 智力 299；耐力 884；爆击 52；全能 31 | 智力 325；耐力 987；爆击 54；全能 32 |
| 258523 | 奈扎尔的虚空爪 | 总督奈扎尔 | 护甲 / 其它 | 副手物品 | off_hand | - | partial | missing deterministic SimC variant preset | - | 智力 149；耐力 640；爆击 42；精通 30 | 智力 168；耐力 754；爆击 45；精通 32 | 智力 190；耐力 884；爆击 48；精通 34 | - |
| 258524 | 黑暗总督之握 | 总督奈扎尔 | 武器 / 拳套 | 单手 | main_hand | - | partial | missing deterministic SimC variant preset | - | 敏捷 49；耐力 640；精通 45；全能 27 | 敏捷 55；耐力 754；精通 48；全能 29 | 敏捷 62；耐力 884；精通 52；全能 31 | 敏捷 67；耐力 987；精通 54；全能 32 |
| 258525 | 无尽之夜权杖 | 鲁拉 | 武器 / 锤 | 单手 | main_hand | - | partial | missing deterministic SimC variant preset | - | 力量 49；耐力 640；爆击 28；急速 44 | 力量 55；耐力 754；爆击 30；急速 47 | 力量 62；耐力 884；爆击 32；急速 50 | 力量 67；耐力 987；爆击 34；急速 52 |
