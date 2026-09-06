# 原题复测

测试运行源码：`db7e1537`，原生 `gpt-6-astra / high`。以下为同一原题在最终提交上的真实输出，没有给模型注入角色、赛季或机制答案。总耗时 143.368 秒，首正文 115.592 秒。

旧回答停在公开页面无数据并要求玩家提供角色链接。新回答自主发现榜单、批量角色并给出机制分析。准确性复核与限制见同目录 `evaluation-review.md`；这是一组有限评测，不代表全面超过通用助手。

---

**高分增强萨重视暴击，核心原因是风暴使者的 Overcharge：暴击同时提高“暴击发生率”和“自然技能的暴击伤害”。配装要结合精通、急速一起看。**[技能原文](https://www.wowhead.com/spell=1251026/overcharge)

我抽查了 IO 当前赛季（至暗之夜第二赛季）世界前十，成功核对 9 人，1 人因角色身份不匹配排除。9 人当前都是增强、选择风暴使者和 Overcharge，并穿着至少四件当季套装。装备快照在 9 月 4—6 日；接口没有返回面板百分比，因此能确认他们的配装选择，无法统计“平均多少暴击”。

具体原因有三层：

1. **Overcharge 让暴击有双重收益。**  
   技能说明是：自然技能的暴击伤害，按你的暴击率的 **40%** 获得加成。因此增加暴击，既让自然技能更常暴击，也让暴击时打得更重。这是这套天赋愿意给暴击分配更多属性的直接机制依据。[Overcharge](https://www.wowhead.com/spell=1251026/overcharge)

2. **当季四件套强化毁灭闪电，使这条收益链更值得关注。**  
   两件套让 Voltaic Blaze 触发火焰新星；四件套让火焰新星减少毁灭闪电冷却，并提高下一次毁灭闪电伤害。由此推断，更多、更强的自然伤害技能，会进一步增加 Overcharge 的价值；具体增加多少，需要看实战伤害构成。[套装原文](https://www.wowhead.com/item=271483/serpent-crown-of-the-ophidian-oracle)

3. **他们在补整套装备缺少的属性，宝石并没有统一全堆暴击。**  
   这批样本的普通宝石选择如下：

   | 宝石倾向 | 人数 | 例子 |
   |---|---:|---|
   | 主要补暴击，搭配精通 | 2 | [Drakthul](https://raider.io/characters/us/sargeras/Drakthul) |
   | 主要补精通，搭配暴击 | 3 | [Lampeao](https://raider.io/characters/us/area-52/Lampeao) |
   | 急速、精通组合 | 4 | [Enhapumper](https://raider.io/characters/eu/draenor/Enhapumper) |

   此外，9 人都用双戒指 **Eyes of the Eagle** 附魔，增加的是暴击效果，进一步强化暴击伤害这一侧。[附魔说明](https://www.wowhead.com/item=243957/enchant-ring-eyes-of-the-eagle)

攻略之间确实存在分歧：同为 12.1，Method 的 8 月 24 日通用排序仍把急速放在暴击前；Wordup 的风暴使者专项说明则把暴击、精通列为接近，并明确解释了第二赛季装备属性变化与 Overcharge 的关系。后者更贴合这批角色的实际天赋，但样本也显示玩家仍会按装备补急速。[Method](https://www.method.gg/guides/enhancement-shaman/stats-races-and-consumables)、[Wordup](https://www.wowhead.com/guide/classes/shaman/enhancement/stat-priority-pve-dps)

**你如果也是这套风暴使者四件套，可以把暴击和精通作为重点配装方向，保留足够急速支撑循环。**具体要不要把某颗急速宝石换成暴击，要比较你当前整套装备的模拟结果；榜单上的暴击百分比本身不是需要追到的固定目标。
