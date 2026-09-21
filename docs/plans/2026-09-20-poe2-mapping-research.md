# POE2 国服角色数据到 PoB 的映射来源调研

日期：2026-09-20。范围仅限 2–4 个可复核来源和现有样本抽查；未实现映射、未批量抓取、未接入登录或额外私有接口。

## 结论

当前可行的首版不是建立一份来源不明的“全量中英翻译表”，而是使用 WeGame 公开分享页本次自然加载的数据中已有的版本化联接线索，联接到固定版本 PoB 的英文标识：

- 技能优先使用 `BtGetBase.base_list[].id`（例如 `ActiveSkills.explosive_spear`），再映射到 PoB `Gems.lua` 的 `gameId` / `variantId` / `grantedEffectId`；其跨版本稳定性仍需由 `sourceVersion` 约束。
- 装备优先使用图标 URL 内的游戏资源路径（例如 `.../OneHandSpears/1HSpear10`、`.../Basetypes/AmethystRing`、`.../Uniques/ArmsLength`），再用物品类别、需求和基础数值复核 PoB base/unique。
- PoB 固定提交作为英文目标及计算能力的事实源；不要把第三方中文词典当计算规则源。

这条链已能在当前样本与固定 PoB 提交之间确定性覆盖武器、戒指和主技能。词缀对象只有中文 `description`/flags，任务奖励只有汇总文本，均没有可直接联接的 stat/quest ID；两类仍是首版的实质缺口。遇到未确认模板必须标记 `missing` 或 `unsupported`，不能翻译后直接送入 PoB。

## 候选来源

### 1. 固定版本 Path of Building 2 Community（推荐作为英文目标）

- 仓库：https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2
- 本 Candidate 已固定：`7d6f530cbdab20389ff8bc6ba97a37ac27f74e41`。
- 相关数据：`src/Data/Bases/*.lua`、`src/Data/Uniques/*.lua`、`src/Data/Gems.lua`、`src/Data/Skills/*.lua`、`src/Data/StatDescriptions/*.lua`、`src/Data/QuestRewards.lua`。
- 覆盖：英文基底、暗金、宝石名称与阶级、PoB gem ID、PoB 可解析词缀文本、任务奖励配置。
- 许可：仓库 README 标注 MIT；`LICENSE.md` 的 Path of Building Community 首段是 MIT 授权，并要求复制或实质部分保留版权和许可文本。仓库也包含第三方组件的独立许可证，若复制代码或数据文件，需保留完整 notices：https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/blob/dev/LICENSE.md 。
- 限制：这是英文目标和 PoB 支持范围，不提供国服简中对照；其数据版本必须和 `mappingVersion/gameDataVersion/engineCommit` 一起固定。

### 2. WeGame 指定公开分享页的自然加载响应（推荐作为每次输入的中文侧事实）

- 当前证据：云端 Candidate 的 `evidence/link-research/wegame.json`；仅来自用户指定公开分享页的一次无登录页面观察。
- 有用字段：`GetEquipments` 的 `baseType`、`typeLine`、图标资源路径、类别、需求、基础数值和 flags；`GetSkills` 的技能/辅助名称、阶级、图标资源路径；`BtGetBase` 的 `ActiveSkills.*` 英文式稳定 ID；`GetTalentTree.quest_stats` 的任务奖励汇总。
- 覆盖：样本内简中名称和实际角色数值；装备与技能已有可验证的联接线索。
- 许可/使用边界：响应未携带可复用或再分发许可证；WeGame 也没有在本次调研中提供面向第三方的公开静态数据许可。它只能作为用户主动提交的公开分享页本次输入证据，不能打包成通用数据库、批量枚举或由本结论推导出额外接口抓取权限。正式开放前仍需复核来源使用规范。
- 限制：词缀没有完整 stat ID；`quest_stats` 没有 quest/choice provenance；资源键虽稳定性强，仍要以类别、需求、基础数值做复核并记录来源版本。

### 3. `PathOfBuilding-PoE2-i18n`（可作人工交叉检查，不作为简中主字典）

- 仓库：https://github.com/woolkingx/PathOfBuilding-PoE2-i18n
- 数据：`locale/zh_TW/LC_MESSAGES/*.po` 与生成的 `src/Data/Lang/zh_TW/`，以英文原文为 key 的繁中显示层对照。
- 许可：仓库保留上游 `LICENSE.md`，README 明示 upstream 原始许可为 MIT：https://github.com/woolkingx/PathOfBuilding-PoE2-i18n/blob/release/LICENSE.md 。
- 限制：只有繁体中文，README 明确定位为 display-only；原始 build identity、parser input 和计算内部仍保持英文。它既不是 WeGame 官方简中，也不能证明简繁转换后的词条与国服逐字一致。当前快照基于上游 `b8048682`，与本 Candidate 的 `7d6f530c` 也不是同一提交。
- 结论：只适合检查英文实体是否存在及人工发现歧义；不能作为无需复核的国服映射源。

### 4. `repoe-fork/poe2`（结构化英文辅助源，当前不建议内置）

- 仓库：https://github.com/repoe-fork/poe2
- 示例数据：https://github.com/repoe-fork/poe2/tree/master/data ，包含结构化游戏数据和 `stat_translations/*.json`。
- 覆盖：英文 stat description 等结构化数据，适合研究 stat ID 与模板结构。
- 许可：仓库根目录未找到 LICENSE，GitHub 页面也没有给数据再分发条款。
- 限制：没有国服简中对照，且许可不明确。除非维护者补充明确许可和版本来源，只可用于人工验证公开事实，不应复制/内置其数据。

另外抽查了公开繁中项目 `Orangeeewei/poe-ninja-pob-zh`。它说明其名称与描述来自游戏英文/繁中逐行导出、词缀来自 `stat_descriptions`，但仓库没有 LICENSE，语言也不是国服简中，因此不列为可内置来源。

## 代表性匹配

以下匹配使用既有云端捕获与固定 PoB，不涉及新抓取。

| 类别 | WeGame 样本 | 稳定线索与复核 | 固定 PoB 目标 | 结果 |
| --- | --- | --- | --- | --- |
| 武器 | `阿科扬战矛` | 图标资源 `OneHandSpears/1HSpear10`；需求 78 / 50 力 / 127 敏 / 90 智；基础攻速 1.60 | `itemBases["Akoyan Spear"]`，需求和攻速完全一致 | `mapped`；名称翻译不是唯一依据 |
| 戒指 | `紫晶戒指` | 图标资源 `Basetypes/AmethystRing`；隐式混沌抗性样本值 +13% | `itemBases["Amethyst Ring"]`，隐式范围 +(7–13)% 混沌抗性 | `mapped` |
| 主技能 | `爆破战矛` | `BtGetBase.id = ActiveSkills.explosive_spear`，英文式 key 为 `explosive_spear` | `SkillGemExplosiveSpear`；name `Explosive Spear`；variant `ExplosiveSpear`；granted effect `ExplosiveSpearPlayer` | `mapped`；应保存两侧 ID |
| 辅助阶级 | `处决 II` | `typeLine` 含明确阶级 II，图标为 `ExecuteSupportGem` | `SkillGemExecuteSupportTwo`；name `Execute II`；Tier 4；variant `ExecuteSupportTwo` | 样本可映射；必须把显示阶级和 PoB tier/variant 分开保存 |

暗金也可采用同一路径：样本 `暴政之握 / 符文铁头长矛` 的资源键为 `Uniques/ArmsLength`，固定 PoB 中对应 `Tyranny's Grip / Ironhead Spear`，且六条效果及数值范围一致。资源键 `ArmsLength` 不能直接当显示名称，因为 PoB 中还存在同名辅助宝石 `Arms Length`；必须同时校验类别和 base。

## 词缀与任务奖励缺口

- 词缀：样本行保留 `[Attack|攻击]`、`[Physical|物理]` 等语义标记和 flags，足以辅助模板分类，但不足以唯一确定 stat。可先对“数字归一化后的中文模板 + 语义 markers + mod kind/flags + item domain”做版本化白名单，并要求其英文结果能被固定 PoB parser 接受；歧义或 parser 不支持时停在 `needs_input`。首版不能用通用机器翻译生成英文规则。
- 任务奖励：样本只有 `quest_stats` 汇总，如 `+20 生命上限`、三抗各 +10%、`+100 精魂`、属性选择和咒符栏效果；PoB `QuestRewards.lua` 按区域/事件/选项建模。仅凭汇总不能可靠恢复每个任务选择，尤其重复/组合来源。需要来源侧提供 quest/choice ID，或让用户确认逐项选择；在此之前不得默认全部完成。
- 简中公共字典：本次限量检索未找到同时满足“国服简中、PoE2 当前版本、实体/模板稳定 ID、明确允许再分发”四项条件的公共仓库。这个缺口应写入完整性状态，不宜用繁中、OpenCC 或非许可抓取数据填平。

## 建议的版本与验收边界

字典记录至少保存 `sourceKey`、`sourceVersion`、中文显示值、PoB key/ID、PoB commit、证据字段和状态。优先级为明确 ID > 游戏资源路径并多字段复核 > 经人工审核的模板白名单；纯名称相似或机器翻译不得进入 `mapped`。

首版可以声明样本的武器、戒指、技能及辅助阶级已找到确定性映射路径；不能声明全量词缀、任务奖励或国服角色已完整转换。下一步若要解除阻塞，应先取得带 stat/quest ID 的合法来源或针对有限白名单逐项建立双语证据，并对固定 PoB 重导入与面板做业务核对。

## 补充核验：现成 WeGame → PoB2 转换

### `ackness/pobr`

核验仓库：https://github.com/ackness/pobr ，当前检查提交 `6ab51142e6b56f139a690ddec99d22a7cc0b850d`（2026-09-17）。这是目前最接近本设计的可复用实现：公开分享读取、简中规范化、装备/技能/天赋/珠宝/任务转换和 PoB2 编码均已有代码与合成测试。

关键文件和规则：

- `web/public/_worker.js`：`shareKey()` 严格校验 WeGame HTTPS host/path/fragment；`fetchShare()` 只读取 `GetRoleInfo`、`GetEquipments`、`GetTalentTree`、`GetJewels`、`GetSkills`，不带 cookie，15 秒超时、4 MiB 响应上限、任一端点失败即终止；`itemFields()` 做字段白名单并去掉账号/角色名/URL。它与本设计的访问边界高度一致。
- `apps/pobr-wasm/src/build_api/wegame.rs`：`clean()` 去除 `[EnglishKey|中文]` 显示标记和珠宝 roll range；`canonical()` 用简中模板转英文；`item_text()` 生成 PoB 物品文本并保留 implicit/enchant/rune/explicit/crafted/fractured、品质、防御、需求、腐化和符文；`gem_names()` 用 `zh-CN/base_items.json` 与 stable gem ID 建索引，只接受唯一命中；`gem()` 保留等级/品质并把未知或歧义宝石写入 warnings；`decode()` 保留 `hashes`、`skill_overrides`、两套 `specialisations`、换武器装备，并把实际 `quest_stats` 放入 `questWeGame`，同时关闭默认“全任务完成”。
- 同文件的珠宝分支：解析 `jewel_data`，用 `socket_id` 找 passive node，再用 jewel metadata `id` 找英文 base，翻译 `mod_descriptions`，输出 `socket_node + PoB item text`。未知插槽只告警；装备内 jewel socket 明确告警并跳过，Shaman-only rune bonus 也不无条件应用。
- `apps/pobr-wasm/src/build_api/encode.rs`：`encode_build_json()` 将规范化状态写为 PoB2 XML/分享码，写入武器套装节点、attribute choices、物品、药剂/咒符、树珠宝、技能组及 config。
- `apps/pobr-wasm/tests/wegame.rs`：合成夹具验证中文词缀、宝石、任务、树珠宝、换武器和 encode/decode round trip；未知辅助只进入 notes。真实分享测试被 `#[ignore]` 且要求本地私有 bundle，不把玩家数据提交到仓库。
- `pipeline/gen-zh-cn.mjs` 与 `pipeline/dictionary-source.mjs`：从固定提交的 `addohm/poe2-en-cn-dict` 生成版本化 `base_items.json`、`skills.json`、`stat_lines.json`、classes/words/passives/mods/rare words；使用完整 commit SHA 下载并缓存完整快照。当前 `data/4.5.5.2/i18n/zh-CN/_meta.json` 记录 4,902 bases、854 skills、26,074 stat lines 等，但该旧产物未记录 `source_commit`，若采用必须重新固定来源 SHA，不能只引用生成时间。

许可边界：PoBR 根 `LICENSE` 是 MIT，可复用上述代码/算法，但需保留版权和许可文本。仓库 README 明确说 `data/` 源于 PoE2 客户端资产、版权属于 GGG；MIT 不能解释为覆盖这些游戏数据。它的简中源 `addohm/poe2-en-cn-dict` 没有 LICENSE。因而可优先移植转换代码和合成测试；若要直接内置其字典快照，仍需解决游戏数据/词典的许可与来源条款，或在我们自己的授权数据管线中生成等价版本化映射。

当前样本的珠宝边界与 PoBR 不同：PoBR worker 接受 `jewel_data` 为任意字符串，但 Rust `decode()` 随后要求它可解析成 JSON 数组；空字符串会返回 `invalid WeGame jewel data` 并使整个导入失败。本次样本的 `GetJewels` 正是空字符串。因此不能原样复用这一失败策略；应把空字符串结合 talent tree 中已有 jewel slots 转为明确的 `missing`，保留装备/技能/天赋预览并停在 `needs_input`。这也是采用 PoBR 前必须补的首要行为测试。

### `poe2db.tw/cn/account`

公开入口：https://poe2db.tw/cn/account 。页面只在浏览器侧校验 WeGame share URL 与 64 字符 code，然后调用站内 `/api/requestShareCode?share_code=...`；转换在服务端完成。未向该接口提交用户分享。

只读检查该站已经公开列出的角色页确认：页面能给出 PoB Code、`.build` 下载、技能的 metadata gem IDs、两套武器天赋、装备和按章节拆分的 Quest Stats。它证明“国服公开分享 → PoB Code”已经有人跑通，也提供了人工比较样本。页面同时出现 `Miss`、未鉴定条目和只有 jewel-slot 被动节点的情况，公开页面未说明缺失珠宝如何进入 PoB Code。

该站不能作为可复用实现或运行依赖：页面只暴露站内 API 调用和最终结果，没有公开转换源码、版本化 mapping identity、错误/完整性合同或许可；页脚仅显示站点版权。提交 share code 还会把角色进入公开列表，与本产品的 owner-scoped、最小快照和隐私边界不一致。可把其公开既有角色 PoB 作为有限人工交叉检查，但不能后台代理用户链接或复制其数据。

综合建议：以 PoBR 的 MIT 导入/编码代码结构和测试为实现参考，继续使用自己的 WeGame 采集与 owner-scoped 任务；词典来源、版本固定和完整性状态由本项目控制。首个差异测试应覆盖当前真实形态：`GetJewels == ""`、天赋存在 jewel slots 时必须返回预览 + `missing_jewels`，不得整任务失败或伪造空珠宝。
