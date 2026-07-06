# CN Terminology Authority Catalog Design

## 背景

2026-07-06 讨论确认：国服官方游戏术语不能继续依赖 LLM 直译、前端硬编码或临时人工改字。当前项目里已经出现典型问题：`spellslinger` 被硬编码为“法术投射者”，而 [国服官方英雄天赋介绍页](https://wow.blizzard.cn/news/24125213/index.html) 中法师英雄天赋写法为“疾咒师”。用户确认“急咒师”是手误，不作为正式术语。

术语错误不只是 UI 文案问题。它会影响：

- 天赋模拟器 hero tree 展示。
- 装备模板、社区模板和 SimC 任务 tag。
- 新闻翻译和 PTR notes 处理。
- SimC / WCL / Chickenbro 报告里的实体名称。
- 用户搜索、alias 匹配和信任感。

本设计只记录术语权威层方案，不实施代码、不写库、不触碰现有硬编码。

## 核心结论

建立 CN Terminology Authority Catalog，把游戏实体中文名当成可审计数据，而不是散落在代码、LLM prompt 或前端兜底里。

原则：

- 实体 key / id 是稳定事实；中文名是带来源和版本的展示属性。
- LLM 可以翻译普通语句，但不能决定游戏实体名。
- 前端不维护职业、专精、英雄天赋、装备、附魔、词缀等术语兜底表。
- 缺 verified 中文名时，保留英文或显示“名称待校验”，不输出猜译。
- 旧译名、社区译名和错误译名可以作为 alias 用于搜索或迁移，但不能作为 canonical display name。

## 术语对象范围

首批纳入：

- `class`：职业。
- `spec`：专精。
- `hero_talent_tree`：英雄天赋树，例如 `spellslinger -> 疾咒师`。
- `talent`：天赋节点。
- `spell`：技能 / 法术 / buff / debuff。
- `item`：装备、宝石、附魔物品、消耗品。
- `enchant`：附魔。
- `embellishment`：美化。
- `crafted_reagent`：制造业可选材料。
- `dungeon` / `raid` / `encounter`。
- `currency` / `upgrade_track` / `vault_rule`。
- `affix` / `mechanic`。

后续可扩展到 Chickenbro 画像、PVE ranking 标签和新闻 tag。

## 数据模型

建议新增或扩展 `websim_translations` 为通用术语 catalog。字段至少包含：

- `entityType`：例如 `hero_talent_tree`。
- `entityKey`：例如 `spellslinger`。
- `entityId`：如果有官方数字 id，则记录。
- `locale`：首版重点 `zh_CN`。
- `canonicalName`：正式展示名，例如 `疾咒师`。
- `englishName`：例如 `Spellslinger`。
- `aliases`：历史译名、英文名、常见社区译名，例如 `法术投射者`、`射咒师`。
- `rejectedAliases`：确认不能作为正式名的文本。
- `sourceType`：`game_client`、`battle_net_api`、`official_cn_article`、`wago_db2`、`manual_override`、`community_reference`。
- `sourceRef`：URL、DB2 build、API path、manual note。
- `sourceRevision`：官方文章日期、game build、season revision 或 DB2 build。
- `seasonRevision` / `termRevision`。
- `status`：`verified`、`candidate`、`manual_review`、`blocked`、`stale`。
- `checkedAt`。
- `reviewNote`。

示例：

```json
{
  "entityType": "hero_talent_tree",
  "entityKey": "spellslinger",
  "locale": "zh_CN",
  "canonicalName": "疾咒师",
  "englishName": "Spellslinger",
  "aliases": ["Spellslinger", "法术投射者", "射咒师"],
  "rejectedAliases": ["急咒师"],
  "sourceType": "official_cn_article",
  "sourceRef": "https://wow.blizzard.cn/news/24125213/index.html",
  "status": "verified"
}
```

`rejectedAliases` 不一定进入用户搜索；它主要防止人工或 LLM 把已确认错误的文本重新晋升。

## 证据优先级

术语晋升为 `verified` 时按以下优先级：

1. 国服游戏客户端 / zh_CN DB2 / 官方 locale 数据。
2. Battle.net Game Data `zh_CN`，适用于 item、spell、media、journal 等官方 API 覆盖对象。
3. 国服官方站、国服蓝贴、官方新闻。
4. Wago DB2 / Wowhead zhCN / community wiki，仅作为候选或交叉检查。
5. Manual override，必须带 reviewer、sourceRef、reason 和 revision。
6. LLM 输出永远不能作为术语权威来源。

当多个来源冲突时：

- 高优先级来源覆盖低优先级来源。
- 不确定时标记 `manual_review`。
- 不能用 LLM 选择“更自然”的译名。

## 后端消费契约

所有 WebSim / SimC / Chickenbro 相关 payload 应逐步改为后端给出术语状态：

- `displayName`：canonical 中文名或英文 fallback。
- `englishName`。
- `termStatus`：`verified`、`candidate`、`manual_review`、`missing`。
- `termRevision`。
- `termSource`。
- `aliases`：仅后台或搜索需要时输出。

前端看到 `termStatus != verified` 时可以展示轻量提示，但不得自行翻译。

## 前端边界

应逐步移除前端硬编码术语表，例如：

- `pages/builds/detail.js` 里的 `gearHeroLabels`。
- 任何页面里基于 heroKey / itemId / spellId 的中文兜底。

前端允许：

- 展示后端 `displayName`。
- 在搜索中把用户输入传给后端 alias matcher。
- 展示 `名称待校验` / `官方译名待补`。

前端不允许：

- 把 `spellslinger` 翻译成“法术投射者”这类猜译。
- 用 LLM 或本地词典覆盖后端 canonical name。
- 按赛季、职业或 key 自己修补术语。

## LLM 与报告后处理

新闻翻译、SimC 报告、WCL 报告、Chickenbro 输出都需要经过术语后处理：

1. 输入阶段：给 LLM 提供已 verified 的术语表片段。
2. 输出阶段：deterministic term replacer 扫描实体名和 alias。
3. 校验阶段：如果 LLM 使用了 rejected alias 或未验证猜译，报告进入 `translation_blocked` / `term_violation`。
4. 降级阶段：无法确认的实体保留英文或标记待校验。

LLM 仍可负责句子自然度，但实体名必须由 catalog 决定。

## Alias 与搜索

Alias 用于用户体验，不用于正式显示。

允许 alias：

- 英文名：`Spellslinger`。
- 历史错误硬编码：`法术投射者`。
- 社区旧译：`射咒师`。
- 简繁差异或符号差异。

不建议默认收录一次性手误。用户已确认“急咒师”是手误，因此不作为正式 alias；如果后续搜索日志证明大量用户输入该词，可进入 `searchOnlyAliases`，但不能展示。

## Health 与后台门禁

`/api/data/health` 增加 `terminology_catalog`：

- total term count。
- verified / candidate / manual_review / blocked counts。
- high impact missing terms：职业、专精、英雄天赋、装备、附魔、货币、当前赛季副本。
- rejected alias violation count。
- LLM term violation count。
- stale term count after season cutover。
- top blockers。

后台 gates 增加术语审核：

- 按 entity type、status、source、season 过滤。
- 展示候选名、当前 canonical、来源证据和冲突来源。
- 支持 manual override，但必须写 reviewer note。
- 支持把错误译名加入 rejected aliases。

## 12.1 Cutover 关系

术语 catalog 需要绑定 `seasonRevision`，并纳入 12.1 Season Manifest：

- 新天赋、新英雄天赋、新装备、新附魔、新宝石、新制造业材料、新货币、新副本和新奖励轨道都需要术语状态。
- PTR 阶段可以有 `candidate` 术语，但不能包装成国服正式译名。
- 12.1 live 后用 game client / Battle.net `zh_CN` / 国服官方内容复核。
- 术语缺口不一定阻断所有浏览，但会阻断 LLM 报告中的正式中文实体名和强结论。

## 迁移策略

第一阶段：审计和种子

- 扫描 `HERO_TREE_LABELS_ZH`、`gearHeroLabels`、装备/附魔/美化中文 seed、新闻 tag、PVE labels。
- 生成术语候选表。
- 将 `spellslinger -> 疾咒师` 作为首个 confirmed fixture。
- 把 `法术投射者` 作为 alias / rejected display candidate。

第二阶段：后端读模型

- 后端 WebSim talents / gear / profile payload 从术语 catalog 取 display。
- 缺术语时输出 `termStatus=missing`。
- `/api/data/health` 暴露 `terminology_catalog`。

第三阶段：前端收口

- 移除前端硬编码 hero labels。
- 所有页面展示后端 `displayName`。
- 搜索走 alias matcher。

第四阶段：LLM guard

- 新闻翻译、SimC 报告、Chickenbro 输出接术语后处理。
- 术语违规进入 deterministic blocker。

## 验收标准

- `spellslinger` 在所有用户可见 WebSim、装备模板、SimC 任务和 Chickenbro 文案中显示为 `疾咒师`。
- `法术投射者` 不再作为正式展示名，只能作为历史 alias 或 migration signal。
- 前端不能通过本地 hardcoded map 覆盖后端术语。
- LLM 输出实体名时必须遵守 terminology catalog。
- `/api/data/health` 能显示术语缺口和高影响 blocker。
- 12.1 Season Manifest 包含 `terminologyRevision`。

## 后续实施提示

后续实现应 TDD 先行，至少添加：

1. `spellslinger` fixture：官方来源为 `疾咒师`，旧硬编码 `法术投射者` 不能覆盖。
2. 前端 payload fixture：页面只使用后端 `displayName`。
3. LLM violation fixture：输出 rejected alias 时 blocked。
4. Alias search fixture：搜索 `法术投射者` 能找到 `疾咒师`，但展示仍为 canonical。
5. Season cutover fixture：S2 新术语缺 verified 时进入 `manual_review`，不被 LLM 猜译。
