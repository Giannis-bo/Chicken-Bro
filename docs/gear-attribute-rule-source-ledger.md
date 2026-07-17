# Gear Attribute Rule Source Ledger

这份账本是装备模拟“非战斗常态属性面板”的生产启用闸门。只有同时具备可审计规则来源、`verified` 黄金样本和跨端 fixture 的 `ruleContext` 才能进入公开 `attributeCalculator`。`fixture_only` 仅可用于本地单元测试，不能发布到小程序。

| ruleContext | attributeRuleRevision | status | sourceRefs | goldenSampleIds | owner | lastVerifiedAt | coverage |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `mage:frost:90:dwarf` | — | `blocked_pending_rule_source` | Armory `https://worldofwarcraft.blizzard.com/en-us/character/kr/azshara/%EC%B9%B4%EB%A5%B4%EA%BD%81%EC%8A%A4` and authorized Battle.net Profile API (2026-07-17T09:12:43Z; active loadout rechecked 2026-07-17T09:24:32Z) | `mage-frost-armory-2026-07-17t091243z` (`candidate`) | 装备模拟 | — | 已确认法师/冰霜/矮人/90 级、Spellslinger 活动配置码、15 件实际装备、bonus IDs、宝石/附魔 IDs、每件官方 typed item stats 与未舍入面板；仍缺可发布的 variant/宝石解析、稳定被动与天赋效果分类/映射和完整 rating 换算 |
| `mage:arcane:90:night_elf` | — | `blocked_pending_rule_source` | Armory `https://worldofwarcraft.blizzard.com/en-gb/character/eu/blackrock/Heated` (2026-07-17 captured); authorized Battle.net Profile API (2026-07-17T04:43:43Z; active loadout rechecked 2026-07-17T09:35:57Z); Raider.IO `https://raider.io/api/v1/characters/profile?region=eu&realm=blackrock&name=Heated&fields=gear%2Ctalents%2Cmythic_plus_scores_by_season%3Acurrent` (2026-07-17 captured) | `mage-arcane-armory-2026-07-17t041853z` (`candidate`) | 装备模拟 | — | 官方 API 已确认种族/专精、15 件实际装备、bonus IDs、宝石/附魔 IDs、每件官方 typed item stats、Spellslinger 活动配置码及未舍入面板；仍无可发布的 variant/宝石解析、全强化数值、全种族/专精基础与 rating 换算、稳定与条件效果分类/映射规则 |

## 2026-07-17 授权候选采集

- 用户已明确授权将英雄榜/官方角色资料写入仓库。原始、可机读的候选记录保存在 `tests/fixtures/gear-attribute-armory-v1.json`。
- `Heated / EU Blackrock / 90 Night Elf Arcane Mage` 的官方页面在 `2026-07-17T04:18:53Z` 可访问：291 装等，面板为智力 `2,462`、耐力 `22,938`、暴击 `19%`、急速 `23%`、精通 `37%`、全能 `7%`，并保存每个可见装备 tooltip 的静态词条和条件效果文本。经用户授权，云端既有 Battle.net OAuth 在 `2026-07-17T04:43:43Z` 只读抓到同一角色的官方 Profile：15 件实际装备（另有不计入装备模拟的衬衣/战袍）、每件 item level/bonus ID/宝石/附魔 ID，以及未舍入的急速 `802 → 23.003637%`、精通 `785 → 37.04609%` 等面板值；在 `2026-07-17T09:35:57Z` 又确认当前为 Arcane Spellslinger 活动配置。全能通过官方 `versatility=385` 和独立的 `versatility_damage_done_bonus=7.1296296` 正确归一为 `385 → 7.1296296%`，与英雄榜截图的 `7%` 一致。Raider.IO profile API 于 `2026-07-17T04:25:50Z` 返回同一角色、种族、当前专精及 15 件相同名称/装等的装备。三者能交叉确认候选输入与输出，但都不构成通用 variant 或非战斗属性公式来源。
- 原候选 `카르공스 / KR Azshara / Frost Mage` 的 URL 在早期抓取时返回 `404`，保留为失败证据。经只读官方 Profile 适配器修复 URL 编码、本地化名称、`rating_normalized` 和 `enchantments` 字段后，`카르꽁스 / KR Azshara / Frost Mage` 于 `2026-07-17T09:12:43Z` 被重新确认：矮人、90 级、15 件实际装备（无副手）、精确 bonus/宝石/附魔 IDs，面板为智力 `2,485`、耐力 `23,001`、暴击 `861 → 25.717392%`、急速 `669 → 21.033895%`、精通 `1,040 → 53.773914%`。这与用户英雄榜截图的智力 `2,485`、耐力 `23,001`、暴击 `26%`、急速 `21%`、精通 `54%` 相符；但它是 2026-07-17 的当前角色快照，不能替换产品中 2026-07-16 的旧 Raider.IO 社区模板面板。
- 三条记录均为 `candidate`。样本注册表校验要求 `candidate` 明示缺口，并阻止它满足 `verified` 规则的 `goldenSampleIds`；没有完整、可复核的换算与输入证据时，公开 `attributeCalculator` 继续返回 `rule_unavailable`。

## 2026-07-17 公式模型修正（仍未发布）

- 已获授权的只读 SimC 源码/DBC 核查仅用于离线公式审计，不参与用户换装请求，也没有运行任何 SimC 模拟。当前生成数据标注为 WoW `12.0.7.68453`：90 级法术暴击为 `46` rating/%、法术急速为 `44`、伤害全能为 `54`、吸血约为 `69.00098495`、速度约为 `11.50016416`、闪避约为 `36.80052531`。
- 这不足以把转换写成固定除法。运行时代码的 `apply_combat_rating_dr` 对二级/三级绿字应用递减曲线；两例官方面板也直接证明了差异：奥法闪避 `127 → 3.4510376%` 仍接近低档线性值，而冰法 `470 → 12.217245%` 已低于 `470 / 36.80052531 = 12.771556%`。因此现有 synthetic `ratingPerPercent` 只可验证解释器骨架，不能作为真实闪避、吸血、速度或其它可能递减属性的发布规则。
- 官方当前活动天赋 tooltip 已提供下一层候选输入：两例均选择 `Inspired Intellect`（Arcane Intellect 额外 `2%` 智力）、`Tome of Rhonin`（`2%` 暴击）、`Tome of Antonidas`（`2%` 急速）、`Charm of Medivh`（`3%` 精通）。奥法还选择 `Arcane Familiar`（最大法力 `10%`）和 `Arcane Tempo`（`2%` 急速）；冰法还选择 `Winter's Blessing`（`3%` 急速及所有急速来源额外 `5%`）。`Brainstorm`、`Overflowing Energy`、`Greater Invisibility` 等明显依赖触发、施法或短时状态的条目保持条件效果，不能并入常态面板。
- 上述 tooltip 是候选证据，不代表已完成分类或运算顺序：例如基础暴击、天赋加算和等级换算的先后、冰法“所有来源急速”对基础/评级/其它加成的作用范围、种族/套装/强化和资源的舍入仍需由版本化规则与逐字段黄金样本复核。任一不明确项继续阻止 promotion。
- 为承载上述两类效果，规则包现明确区分两个有序阶段：`stableModifiers` 在装备绿字合并、进入 `ratingTransform` 前作用于原始属性；每条绿字规则可选的 `postConversionModifiers` 在曲线/基础百分比换算后作用于结果百分比。两端解释器均以规则声明顺序执行，未声明或未识别的效果仍显式标为条件项。该能力只解决“如何精确表达”，不预先判断任何法师天赋应落在哪个阶段；具体映射仍必须由黄金样本逐字段验证后才可写入 `verified` 包。
- 候选解释器现已把曲线本身建模为严格的 `ratingTransform`：`piecewise_linear`、显式 `ratingPerPercent`、有序 `points` 和 `clamp` 越界语义。Python 参考解释器与小程序解释器共享该语义；用 DBC 曲线 `21025` 的源点和冰法 `470` 闪避复核，两端均得到官方未舍入值 `12.217245%`。任何 `verified` rule context 若仍只含旧的 `ratingPerPercent` 线性除法会以 `LEGACY_LINEAR_TRANSFORM_NOT_PROMOTABLE` 被拒绝；两点或共线“伪曲线”也会分别以 `INSUFFICIENT_CURVE_EVIDENCE_FOR_PROMOTION`、`LINEAR_CURVE_NOT_PROMOTABLE` 被拒绝。该能力只证明可以准确表达已证实曲线，**不**代表法师规则、天赋顺序或公开属性面板已发布。
- 每次本地结果的 `inputSignature` 还会绑定实际参与运算的主属性、资源、稳定修正和全部绿字转换规则（包括曲线点），不能只依赖人工递增 `attributeRuleRevision`。因此即使错误地未提升 revision 而改写曲线，结果签名仍会变化并触发保存/审计/fixture 对照。
- 公共 `GET /api/websim/gear` 的 PostgreSQL read-model 路径现与直出路径同构：当存储 payload 缺少 `attributeCalculator` 时，运行时以同一 serializer 补入明确的 `rule_unavailable` 上下文；若存储已提供带 `status` 的规则上下文则原样保留。该修复只消除“字段缺失”与“规则未就绪”的歧义，不会把 candidate、fixture 或 SimC 结果发布为角色属性。

## 2026-07-17 离线实例静态事实探针（仍未发布）

- 已在云端既有 SimulationCraft `12.0.7.68453` 中以 `item_db_source=local`、单次迭代和无网络物品查询，读取官方 Profile 已封存的 item ID、item level、bonus ID、附魔、宝石 ID 与活动天赋；该动作仅用于后台/黄金样本审计，没有参与玩家换装请求、没有写入数据库或刷新 winner。Frost Dwarf 的 15 槽输入可精确复现耐力 `23,001`、生命 `460,020`、智力 `2,485`、精通 rating `1,040` 和吸血 rating `55`。Arcane Night Elf 的同类输入可精确复现耐力 `22,938`、生命 `458,760`、智力 `2,462`、精通 `785`、全能 `385`、吸血 `166` 与速度 `55`。这证明现有 SimC 本地数据足以作为实例静态事实的**审计/交叉验证来源**，但不改变其不在前端实时路径中的边界。
- 同一探针也发现不能把官方 Profile 中的 `bonus_id` 和 `gem_id` 机械相加。Frost 若传入全部记录的 gem ID，得到暴击 `877`、急速 `686`，而官方面板为 `861`、`669`；去掉全部 gem ID 后，急速恰为 `669`，但智力/暴击/精通又分别低为 `2,451`/`813`/`1,005`。Arcane 带全部 gem 时为暴击 `574`、急速 `818`（官方 `558`/`802`）；去掉 gem 后急速仍为 `818`、暴击降为 `539`、全能降为 `305`。因此剩余差异是实例 bonus、强化效果、互斥/条件语义或其序列化约定的组合问题，不能靠截断、常数补偿或前端猜测修正。
- 已获授权的 Battle.net Game Data API 只读探针说明为什么不能直接补洞：`250060` 的通用 item 记录是未按角色实例缩放的 `197` 级基础词条（`+9` 智力、`+14` 耐力、`+12` 急速、`+6` 精通），而 Frost 官方实例为 `289` 级。Gem metadata 可读到 `240892` 为 `+14 Haste/+6 Mastery`、`240908` 为 `+14 Critical Strike/+6 Mastery`、`240983` 为 `+29 Primary Stat`，但前两者没有足以解释角色实例结果的 limit/条件投影。通用 Game Data 因此不能代替按 bonus/装备位置解析的 canonical 静态事实。
- 2026-07-17 的只读生产 PG 核查进一步确认了当前降级的必要性：`7935`、`7963`、`7967`、`7987`、`8041` 等 observed enchant option 虽标记为 `verified`，但 `payload.statDeltas` 均为空，仅保存 `enchant_id`；`8017` 也不在该批可用 option 行中。这里的 `verified` 只表示该选项身份/可用性已观察到，**不**表示它已有可用于属性计算的 canonical 数值，不能把空对象当成零属性。
- 同一版本的离线 SimC DBC 单槽探针能解释部分现象（奥法头部实例闪避 `71`，`8017` 贡献 `37`，鞋子 `7963` 贡献 `19`，合计恰为英雄榜 `127`），但其它同一候选输入仍与已保存候选静态词条相冲突（例如 `258047` 主手在该 DBC 解析为 `465` 智力，而候选记录的辅助静态来源为 `600`）。因此这些探针只能作为待对账证据；未完成角色实例、附魔、宝石和条件效果的一致解析前，绝不从单项差额反推规则或发布数值。
- 结论：下一步必须由后端 Resolver/实例事实 owner 产出已解析物品、宝石、附魔与美化的 canonical 静态属性及其来源/条件标记；实时解释器只消费该 sealed 输入。只有两例官方面板的每个原始字段均能重现后，才可把它们从 `candidate` 提升为 `verified`，并发布对应 `attributeCalculator` rule context。

## 2026-07-17 官方实例词条复核（仍未发布）

- Battle.net Profile `equipment` 的每个实际装备行包含结构化 `stats[].type.type` 与 `stats[].value`；它是按角色实例/bonus 后的数值，不是通用 Game Data 的基础物品词条。审计适配器现只保留这个类型和值：`INTELLECT`、`STAMINA`、四种 rating、`VERSATILITY`、闪避、吸血和速度都会归一成 canonical key；任何未知 type 一律标为 `incomplete`，绝不解析本地化 `display_string` 猜数值。
- 官方结构化词条的两例合计分别为：奥法装备 `1611` 智力、`17991` 耐力、暴击 `523`、急速 `802`、精通 `785`、全能 `305`、闪避 `71`、速度 `55`；冰法装备 `1625` 智力、`18053` 耐力、暴击 `797`、急速 `621`、精通 `1005`、闪避 `303`、吸血 `55`。这已精确解释奥法的装备 raw 急速/精通/速度，以及两例加入官方 gem 后的暴击与部分其它绿字；尚未被 canonical gem/强化规则覆盖的字段继续阻断发布。
- SimC DBC 的同等级缩放预算与官方静态面板差额相互校验：`7935` 为 `+41` 智力及 `+115` 耐力、`7963` 为 `+19` 闪避及 `+232` 耐力、`8017` 为 `+37` 闪避、`8001` 为 `+111` 闪避、`8031` 为 `+166` 吸血、`7987` 为 `+50` 主属性。这里的值来自受控离线 DBC 公式，且 `8031` 已经由单槽 profile 对照显示 `166` 吸血；它们仍须经过 Resolver option/static-fact owner 才能成为公开计算输入。
- 先前将 `258047` 的 `600` 智力描述为辅助来源已被更正：当前官方实例 `equipment.stats` 直接返回 `+600 Intellect`、`+1974 Stamina`、`+90 Haste`、`+82 Mastery`。同一角色输入在 SimC DBC 中得到 `465` 智力是尚未解释的离线 DBC/实例解析差异；官方实例值优先，SimC 不能覆盖它，也不能进入实时路径。
- 先前把两例智力的 `5%` 暂归因于条件天赋 `Brainstorm` 的说法已更正。受控 SimC 源码中，Mage 的 `composite_attribute_multiplier` 会把 Arcane Intellect 的 `3%` 与已选 `Inspired Intellect` 的 `2%` 合并为同一稳定 `5%` 智力乘数；`Brainstorm` 则是独立、可叠层的条件 buff，仍不能计入基础面板。两例官方输入均一致：奥法静态前值 `620 + 1611 + 23 + 41 + 50 = 2345`，乘 `1.05` 后为 `2462.25`，显示 `2462`；冰法静态前值 `619 + 1625 + 32 + 41 + 50 = 2367`，乘 `1.05` 后为 `2485.35`，显示 `2485`。这只完成主属性这一条稳定乘数的证据，不替代其余天赋、条件、资源、variant 或 rating 规则的逐字段 promotion。
- 冰法急速可完整拆为规则顺序：装备/宝石的 `637` 急速 rating，先受 `Winter's Blessing` 的“所有急速来源 +5%”影响并按游戏口径就近取整为 `669`；以 90 级法术急速 `44` rating/百分比换算得到 `15.204545%`；再依次对含基础 `100%` 的总急速应用 `Tome of Antonidas +2%` 与 `Winter's Blessing +3%`，即 `(1 + 15.204545%)*1.02*1.03 - 1 = 21.033895%`，与官方 Profile 一致。受控 SimC DBC 同时给出二级绿字曲线 `21024`、三级绿字曲线 `21025` 及 90 级的 crit/mastery `46`、haste `44`、versatility `54`、avoidance `36.80052531` rating 入口。这证明本地规则引擎必须显式支持“rating 取整”和“含 100% 基线的总量乘法”；尚不等于将任何未封存天赋自动当作常驻。
- 两个官方 `talentLoadoutCode` 已由项目既有的 SimC trait decoder 无损解码：两例都选中 `Inspired Intellect (458437)`、`Tome of Antonidas (382490)` 和 `Tome of Rhonin (382493)`，冰法另选中 `Winter's Blessing (417489)`，奥法另选中 `Arcane Familiar (205022)`。因此发布路径必须从经封存的天赋导入码产生 stable-effect IDs；不能仅按职业/专精默认注入，缺这条事实的模板继续降级。

## 2026-07-17 受控强化静态事实包（仍未发布）

- `server/gear_attribute_static_facts.py` 建立了首个版本化的 option 事实包 `midnight-option-static-facts-r1`。它只接受 option 中结构化的 `simcOptions.gem_id` 或 `simcOptions.enchant_id`；不读取 `statSummary`、本地化名称或 tooltip 文案，因此错误展示文本不能污染 Resolver 的 canonical 输入。
- 已纳入两例法师候选、并由受控离线 DBC 和官方实例面板交叉复核的固定值包括：宝石 `240892`（急速 `16`、精通 `7`）、`240908`（暴击 `16`、精通 `7`）、`240914`（全能 `16`、暴击 `7`）、`240983`（主属性 `32`）；附魔 `7935`（主属性 `41`、耐力 `115`）、`7963`（闪避 `19`、耐力 `232`）、`7987`（主属性 `50`）、`8001`（闪避 `111`）、`8017`（闪避 `37`）、`8031`（吸血 `166`）。主属性只在当前受控的 Mage 输入中投影为智力，其他职业没有猜测式映射。
- `7967`（不改变角色面板 rating 的暴击效果）以及 `4223`、`4897`、`8039`、`8041`（条件/触发效果）会以 `not_applicable` 与明确的效果分类保留；它们不被伪装成零词条，也不因不属于非战斗基础面板而阻塞固定属性计算。
- `240967` 等“按不同至暗之夜宝石颜色”叠加的宝石尚未进入这个包：其固定主属性、颜色集合与暴击效果的完整运算需要一起作为可审计规则输入，不能先投影其中一个数值。任意未知 ID、职业主属性映射或效果类型继续回到 `ATTRIBUTE_STATIC_FACTS_UNAVAILABLE`。
- 此包仅在 Authority Context 投影期补足已有 PostgreSQL option 的读取事实；没有写数据库、没有更新 winner，也没有启用任何 `attributeCalculator` 上下文。两例黄金样本仍为 `candidate`，公开接口继续保持 `rule_unavailable`，直至物品 variant、天赋/条件分类与完整百分比规则逐字段通过。

## 录入要求

- `sourceRefs` 必须能指向具体的规则来源或可复核的官方证据，不能只写“英雄榜截图”或角色名。
- `goldenSampleIds` 必须绑定完整角色身份、抓取时间、等级、种族、专精、天赋、装备/强化快照和英雄榜属性。
- 写入任何网络来源内容前，必须先获得用户对“将网络来源写入仓库”的明确许可；在此之前只能保留本地 synthetic fixture。
- 任一来源、样本或跨端 fixture 失效时，规则状态退回 `blocked_pending_source_capture`，公开接口返回 `ATTRIBUTE_RULE_UNAVAILABLE`。
