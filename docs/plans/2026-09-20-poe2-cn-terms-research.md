# POE2 简体术语核查（2026-09-20）

状态：供 Candidate 中文展示实现参考；未提交。

## 结论

已核实 69 条有限名称对应：38 个去重技能/辅助名称、8 个已显示基础职业、23 个升华名称。实际用户导入证据中的重复宝石应复用同一个精确名称映射，保留罗马等级。JSON：[2026-09-20-poe2-cn-terms-research.json](2026-09-20-poe2-cn-terms-research.json)。

采用 PoE2DB 的 `cn` 数据区简体名称。未使用 `tw` 文本机械转简体，未引入全量词库。资料页含数据和 Community Wiki 两部分：职业名称以数据区及单项页标题为准；例如 Character_class 底部旧社区段落的“僧侣/女术者”与数据区“行者/魔巫”有差异。

## 来源与核查方法

访问日期：2026-09-20。四个索引入口用于限定核查范围；JSON 每条附具体单项页面，按相同英文 URL 标识与中文标题或 BaseType 对应核实。

- [技能宝石索引](https://poe2db.tw/cn/Skill_Gems)
- [辅助宝石索引](https://poe2db.tw/cn/Support_Gems)
- [职业数据区](https://poe2db.tw/cn/Character_class)
- [升华数据区](https://poe2db.tw/cn/Ascendancy_class)

资料为社区游戏数据参考站的当前快照，页面未提供统一且可固定的完整补丁标识；不能把这次名称核查说成国服客户端逐项验证，也不据此证明国服与国际服机制、可用职业和数值同步。JSON 的 gameVersion 仅记录当前系列语境，实际精确版本未锁定。名称用于展示，原始英文、gemId/skillId 和计算输入必须保留。

云端直接 HTTP 读取上述页面返回 403，随后通过 web 工具访问同站页面完成核查，未扩大到其他词库。用户真实输入覆盖依据：`/opt/chickenbro-candidates/poe2-20260918/evidence/link-research/user-ninja-code-result-20260920.json`；读取该文件发现截图之外还有 Virtuous Barrier、Eternal Rage、Spear Throw，均已补入。

## 关键边界与歧义处理

- Gemling Legionnaire = 古灵使徒斗士；Mercenary = 佣兵。Monk = 行者，Sorceress = 魔巫；不要把繁体常见名“古靈軍團/僧侶/女術者”转字后用作默认简体。
- Heavy Swing 页面标题仍是英文，但 [Attribute/BaseType](https://poe2db.tw/cn/Heavy_Swing) 明确为“沉重挥舞”，ItemType 为 Metadata/Items/Gems/SupportGemHeavySwing。
- Uruk's Smelting 的实际页面是 [Uruks_Smelting](https://poe2db.tw/cn/Uruks_Smelting)，对应“厄罗克的熔炼术”；含撇号的猜测 URL 失败后已按索引链接纠正。
- Companion: Diretusk Boar 由技能索引中的“伙伴：{0}”模板与 [Diretusk Boar = 恐牙野猪](https://poe2db.tw/cn/Diretusk_Boar) 组合为“伙伴：恐牙野猪”。这是两个明确事实的组合展示，JSON 注明来源。
- 表内所有截图名称已核实；表外宝石、装备底材、词缀和未来新增职业未核实，保留原始名称，不能编译或猜译。
- Lich 与 Abyssal Lich 为独立名称映射；这里只报告名称，不断言其版本关系或同时可选状态。
- 未复制技能描述、数值表、全量物品或第三方词库；只保存本任务有限的名称事实对应与引用。

## 有限映射表

| 类型 | 英文 | 简体 |
| --- | --- | --- |
| gem | Shield Wall | 盾墙 |
| gem | Sunder | 大地震击 |
| gem | Herald of Blood | 赤血之捷 |
| gem | Fortifying Cry | 坚韧战吼 |
| gem | Wind Dancer | 风舞者 |
| gem | Companion: Diretusk Boar | 伙伴：恐牙野猪 |
| gem | Herald of Plague | 荒芜之捷 |
| gem | Attrition | 持久鏖战 |
| gem | Time of Need | 紧急时刻 |
| gem | Atalui's Bloodletting | 阿图鲁伊的放血术 |
| gem | Bleed III | 流血 III |
| gem | Poison III | 中毒 III |
| gem | Rapid Attacks II | 快速攻击 II |
| gem | Concentrated Area | 范围集中 |
| gem | Defy II | 顽抗 II |
| gem | Poison Spores | 毒孢迸溅 |
| gem | Brambleslam | 遍地荆棘 |
| gem | Admixture | 混合物 |
| gem | Deadly Poison II | 致命毒素 II |
| gem | Bursting Plague | 迸发之疫 |
| gem | Enraged Warcry II | 燃怒战吼 II |
| gem | Uruk's Smelting | 厄罗克的熔炼术 |
| gem | Armour Break III | 护甲破损 III |
| gem | Lifetap | 赤炼 |
| gem | Magnified Area II | 范围扩大 II |
| gem | Heft | 势大力沉 |
| gem | Heavy Swing | 沉重挥舞 |
| gem | Armour Demolisher II | 护甲破坏者 II |
| gem | Meat Shield II | 肉盾 II |
| gem | Lasting Shock | 持久感电 |
| gem | Overcharge | 过载 |
| gem | Elemental Army | 元素大军 |
| gem | Chaos Mastery | 混沌专精 |
| gem | Armour Demolisher I | 护甲破坏者 I |
| gem | Cooldown Recovery II | 冷却回复 II |
| gem | Virtuous Barrier | 美德壁垒 |
| gem | Eternal Rage | 永恒狂怒 |
| gem | Spear Throw | 战矛飞掷 |
| class | Mercenary | 佣兵 |
| class | Druid | 德鲁伊 |
| class | Monk | 行者 |
| class | Sorceress | 魔巫 |
| class | Warrior | 战士 |
| class | Witch | 女巫 |
| class | Ranger | 游侠 |
| class | Huntress | 女猎手 |
| ascendancy | Gemling Legionnaire | 古灵使徒斗士 |
| ascendancy | Titan | 泰坦 |
| ascendancy | Warbringer | 战争使者 |
| ascendancy | Smith of Kitava | 奇塔弗匠师 |
| ascendancy | Deadeye | 锐眼 |
| ascendancy | Pathfinder | 追猎者 |
| ascendancy | Amazon | 亚马逊 |
| ascendancy | Ritualist | 仪祭师 |
| ascendancy | Witchhunter | 猎巫人 |
| ascendancy | Tactician | 战术家 |
| ascendancy | Blood Mage | 命源法师 |
| ascendancy | Infernalist | 驱炎使 |
| ascendancy | Lich | 巫妖 |
| ascendancy | Stormweaver | 风暴编织者 |
| ascendancy | Chronomancer | 塑时术师 |
| ascendancy | Invoker | 祈求者 |
| ascendancy | Acolyte of Chayula | 夏乌拉追随者 |
| ascendancy | Shaman | 萨满 |
| ascendancy | Oracle | 神谕者 |
| ascendancy | Martial Artist | 武圣 |
| ascendancy | Spirit Walker | 灵魂行者 |
| ascendancy | Disciple of Varashta | 瓦拉煞的门徒 |
| ascendancy | Abyssal Lich | 深渊巫妖 |

## 验证范围

本文件和 JSON 是术语研究交付。产品接入、未知名称回退、前后端一致性和实际 48 颗宝石覆盖由实现任务在云端验证；本研究不声称 Chat/Web 测试通过或用户验收完成。

