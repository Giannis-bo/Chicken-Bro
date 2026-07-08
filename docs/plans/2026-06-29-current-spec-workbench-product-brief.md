# 当前专精工作台产品设计简报

> 本文是后续 UI 设计的产品输入，不是视觉稿、实现计划或 imagegen 结果说明。所有页面原型、视觉探索和交互文案都应先从本文派生，再回到真实接口与 `docs/ui-style-guide.md` 校验。

## 1. 背景与边界

当前小程序已经具备天赋构筑、装备模拟、SimC 提交、任务列表和炸鸡队长能力，但玩家视角仍容易感受到“功能入口集合”，而不是围绕当前角色/专精的一条决策路径。

`当前专精工作台` 的目标不是再新增一个大而全页面，而是把职业专精入口收束成一个明确问题：

**当前这个专精构筑能否模拟/评分，为什么，下一步该做什么。**

本轮只定义产品结构和证据规则：

- 不实现代码。
- 不改页面。
- 不继续生成 UI 图。
- 不用 imagegen 输出作为事实、图标、状态或文案来源。
- OpenAI workbench 方向只作为结构参考，不作为最终 UI 方案。

## 2. 产品目标

把天赋、装备、SimC、炸鸡队长从并列入口收束为一个当前专精工作台：

- 对新手：默认直接告诉他当前能不能继续、缺什么、点哪里。
- 对资深玩家：展开后能看到来源、覆盖率、blockers、checkedAt 和判断依据。
- 对系统：所有强结论都由读模型、SimC 结果或明确来源支撑，LLM 只负责解释和追问，不负责制造事实。

默认用户模式采用“双层模式”：

- 第一层是结论层：readiness、阻断原因、下一步行动。
- 第二层是证据层：模块状态、来源、覆盖率、blockers、时间戳、可追问解释。

## 3. 核心用户任务

### 3.1 新手任务

新手进入当前专精工作台时，主要任务不是理解所有模块，而是完成下一步：

1. 确认当前专精和场景是否正确。
2. 知道当前是否可以提交模拟。
3. 如果不能提交，知道缺哪个输入，以及去哪里补。
4. 如果可以提交，知道提交后会得到什么，不会被虚假的 DPS、S 级或综合分误导。

### 3.2 资深玩家任务

资深玩家需要能验证系统判断是否可信：

1. 查看天赋、装备、SimC、队长上下文分别处于什么状态。
2. 展开 blockers、coverage、source、checkedAt。
3. 区分 `verified`、`partial`、`source_reference`、`blocked`、`stale`。
4. 判断当前数据是可执行输入、参考来源，还是仅用于诊断。
5. 在证据不足时继续补齐，而不是被迫相信一个无来源评分。

## 4. 主路径

工作台主路径固定为：

1. 选择或继承当前专精。
2. 读取天赋与装备。
3. 合并 readiness 判断。
4. 进入阻断修复或提交模拟。
5. 由炸鸡队长解释证据、阻断和下一步。

对应现有能力：

- 天赋读取：`GET /api/websim/talents?class=...&spec=...&hero=...`
- 装备读取：`GET /api/websim/gear?class=...&spec=...&compact=1`
- Profile 确认：`POST /api/websim/profile`
- 模拟提交：`POST /api/websim/simulate`
- SimC 任务链路：`pages/simulator/simc`、`pages/simulator/tasks`
- 队长解释：`/api/chickenbro/*` 与 simulator 现有聊天形态

## 5. 状态模型

工作台使用 `docs/ui-style-guide.md` 和现有读模型的可信状态，不新增一套视觉上好看但语义不清的状态。

| 状态 | 含义 | UI 权限 |
| --- | --- | --- |
| `ready_to_simulate` | 天赋编码成功，核心装备槽位 SimC-ready，当前场景没有阻断。 | 可以展示“提交模拟”主动作；只有最终 SimC 结果存在后才显示 DPS。 |
| `blocked` | 存在确定性缺口，当前不能执行目标动作或不能输出强结论。 | 必须显示缺什么、影响什么、下一步去哪；不是错误页。 |
| `partial` | 有一部分可信数据，但不足以形成强结论。 | 可以预览、编辑、补齐或查看参考；不能显示评分、提升等级或强推荐。 |
| `stale` | 数据过期、赛季漂移或 checkedAt 超出可信窗口。 | 允许查看历史/参考；强结论和提交动作需要刷新或重新确认。 |
| `source_reference` | 来源参考，不是已验证可执行输入。 | 可展示来源和跳转；不得表现为 verified 或可直接模拟。 |

`ready_to_simulate` 是工作台聚合态，不替代后端已有 `verified/partial/source_reference/blocked/stale`。模块内仍使用原状态，首屏只把它们合并成一句可理解结论。

## 6. 首屏信息优先级

首屏优先级必须服务于“当前能否模拟/评分，为什么”：

1. 当前专精身份：职业、专精、英雄天赋、场景、赛季。
2. readiness 结论：可提交、需补齐、仅参考、已过期。
3. 阻断原因：最多先展示 1-2 个最影响下一步的 blocker。
4. 下一步行动：补天赋、补装备、刷新数据、提交模拟、查看任务。
5. 四个模块状态：天赋、装备、SimC、炸鸡队长。
6. 证据展开区：来源、覆盖率、blockers、checkedAt、profile/任务状态。

首屏不应该把四个模块做成平均权重的大卡片墙。模块是支撑结论的证据，不是并列导航广告。

## 7. 模块职责

### 7.1 天赋

天赋模块回答：

- 当前天赋是否来自可编码来源。
- 是否能生成 SimC talent 字段。
- 法术描述、图标、规则覆盖是否完整。
- 缺口会影响“显示解释”还是“模拟提交”。

如果 `talentReadiness.simcReady=true` 但 `spellReady=false`，UI 可以允许进入模拟前置链路，但必须在证据层说明法术解释/图标仍是 `partial`。

### 7.2 装备

装备模块回答：

- 是否补齐当前场景需要的核心槽位。
- 已选装备有多少是 SimC-ready。
- 缺失槽位、宝石、附魔、美化或变体字段会阻断什么。
- 候选装备是 verified、partial 还是 source_reference。

展示型装备和可执行 SimC gear 必须分离。缺少 `bonus_id/gem_id/enchant_id/crafted_stats` 等字段时，不能把候选写成可执行 profile。

### 7.3 SimC

SimC 模块回答：

- 当前能否 confirm profile。
- 当前能否 final submit。
- 是否已有任务，任务状态是什么。
- 是否已有最终 SimC 结果和可展示 DPS。

确认阶段不运行 SimC、不调用 LLM、不生成最终 DPS。最终 DPS 只能来自实际 SimC 输出解析，不能来自预估、imagegen、LLM 或 UI 文案。

### 7.4 炸鸡队长

炸鸡队长模块回答：

- 为什么当前被阻断。
- 证据分别来自哪里。
- 下一步该补哪个输入。
- 用户追问时如何把天赋、装备、SimC 状态解释清楚。

队长不是评分引擎。它不能替代 SimC、WCL、Raider.IO、属性权重或本地读模型输出结论。

## 8. 评分与强结论规则

没有完整 SimC-ready gear + talents 前，不显示：

- DPS。
- 提升优先级。
- S 级 / A 级。
- 综合评分。
- “毕业”“最优”“高收益”等强结论。

评分第一版只能来自单一明确基准：

- 同 profile 的 SimC delta。
- 同一来源、同一窗口、同一场景的百分位。
- 证据完整度。

第一版不把多个来源混合成综合分。若没有明确基准，UI 只能显示状态和下一步，不能用视觉强弱暗示真实收益。

## 9. 队长介入规则

炸鸡队长可以介入这些场景：

- 解释 `blocked`：缺什么、影响什么、怎么补。
- 解释 `partial`：哪些能参考，哪些不能当结论。
- 解释 `stale`：为什么需要刷新，过期会影响哪些判断。
- 解释 `source_reference`：来源只能参考，不能直接提交或评分。
- 引导追问：围绕当前职业、专精、场景和已知模块状态继续问。

炸鸡队长不能做这些事：

- 在没有 SimC 结果时输出 DPS。
- 在没有同源基准时输出提升等级或综合评分。
- 把通用魔兽知识包装成本地证据。
- 把 imagegen 文案、视觉元素或模型推理当作事实。
- 绕过后端 readiness，直接建议“已经可以提交”。

## 10. UI 设计输入

后续视觉稿必须从本文派生，不直接从 imagegen 图派生。

必须遵守：

- `docs/ui-style-guide.md` 的暗色 + 金色 + 真实游戏图标 + 高密度数据方向。
- `verified/partial/source_reference/blocked/stale` 的颜色和语义一致性。
- 首屏移动端密度：核心信息和关键动作必须在首屏可见。
- 真实图标只表示对象和状态，不作为装饰素材堆叠。
- 文案先说对象和状态，不解释 UI 怎么用。

imagegen 后续只能用于视觉语言探索：

- 可以探索面板材质、布局气质、图像氛围。
- 不能生成生产图标。
- 不能生成真实装备/天赋状态。
- 不能生成中文结论文案。
- 不能决定 readiness、评分、优先级或 blocker。

## 11. 关键场景清单

后续 UI 原型至少覆盖这些真实场景：

1. `ready_to_simulate`：天赋和核心装备都可执行，首屏主动作是提交模拟。
2. `blocked`：缺核心输入，例如副手、必需装备字段或 profile 无法确认，首屏主动作是补齐阻断项。
3. `partial`：天赋可编码但 spell detail 不完整，允许模拟路径继续，但证据层标注解释能力不足。
4. `stale`：来源或赛季状态过期，允许查看历史/参考，强结论和提交前需刷新。
5. `source_reference`：社区、攻略或第三方参考存在，但不能保存为 verified 模板或直接提交。
6. SimC 确认通过但未提交：只能显示 confirm 结果和提交动作，不显示最终 DPS。
7. SimC 任务运行中：展示 `queued/running` 与任务入口，不输出结果。
8. SimC 失败或未解析 DPS：展示后端失败原因，不生成模拟结论。
9. 队长无本地证据：可以回答通用范围问题，但必须标注不代表本地 SimC/WCL/排名证据。

## 12. 当前接口证据快照

以下是 2026-06-30 对线上接口的产品设计快照，只用于证明当前 UI 必须能表达这些状态，不是永久产品规则。

### 12.1 天赋快照

请求：

```text
GET http://124.223.51.33/api/websim/talents?class=mage&spec=frost&hero=spellslinger
```

观察到：

- `talentStatus=simc`
- `dataStatus=blocked`
- `nodes=110`
- `presetCount=2`
- `communityTemplateCount=3`
- `talentReadiness.treeReady=true`
- `talentReadiness.ruleReady=true`
- `talentReadiness.encodingReady=true`
- `talentReadiness.simcReady=true`
- `talentReadiness.spellReady=false`
- `spellCoverage=72/110`
- blocker 包括法术描述/图标不完整，以及 38 个天赋节点仍有 unresolved formula text。
- `talentAuthority.diffStatus=pending_official_audit`
- `checkedAt=2026-06-29T03:14:49+00:00`

产品含义：

- 模拟编码路径可继续。
- 法术解释和图标证据仍是 `partial/blocked` 风险。
- UI 不应把天赋模块表现成“全量已验证”。

### 12.2 装备快照

请求：

```text
GET http://124.223.51.33/api/websim/gear?class=mage&spec=frost&compact=1
```

观察到：

- `dataStatus=blocked`
- `catalogStatus=partial`
- `selectedCount=15`
- `simcReadyCount=15`
- `missingRequiredSlots=["off_hand"]`
- `statSnapshot.statStatus=blocked`
- `statSnapshot.checkedAt=2026-06-29T16:06:27+00:00`
- `statSnapshot.blockers=["Select complete SimC-ready gear and talents to calculate a verified stat snapshot."]`
- `catalogBlockers` 包括缺 deterministic SimC variant preset、SimC JSON 没有目标物品属性、active season dungeon list missing。

产品含义：

- 工作台首屏应优先显示“当前不可输出属性快照/评分”的原因。
- 缺失副手、catalog partial 和 statSnapshot blocked 都是主路径信息，不应折叠进深层详情。
- 不能显示综合评分、DPS 或提升优先级。

## 13. 验收检查

### 13.1 文档自检

逐条对照 `docs/ui-style-guide.md`：

- 数据可信 UI：所有强结论都有状态和来源约束。
- 真实图标：只表达对象和状态，不承担装饰。
- 移动端密度：首屏优先结论、阻断和动作。
- 文案规则：AI 区分证据事实和解释建议。

### 13.2 产品一致性检查

- 简报不输出无来源强结论。
- 简报不把 imagegen 内容当事实。
- 简报不把某次接口临时数据写成永久规则。
- 简报保留 `blocked/partial/stale/source_reference` 的可用产品状态。

### 13.3 实施可用性检查

另一个工程师应能根据本文直接继续做：

- 当前专精工作台信息架构。
- 首屏状态聚合逻辑。
- 新手/资深双层展示。
- 阻断态和证据展开交互。
- 后续 UI 原型验收清单。

不应需要重新判断主路径、评分规则或 imagegen 边界。

### 13.4 回归上下文检查

后续实现时至少回归这些文档：

- `docs/ui-style-guide.md`
- `docs/builds-architecture.md`
- `docs/simulator-simc-end-to-end.md`
- `artifacts/ui-skill-comparison/README.md`

并重新读取当前接口状态：

- `/api/websim/talents`
- `/api/websim/gear`
- `/api/websim/profile`
- `/api/websim/simulate`

## 14. 后续交付输入

下一步 UI 设计应以本文作为唯一产品结构输入：

1. 先画信息架构和状态聚合，不先画炫酷界面。
2. 再做高保真移动端视觉探索。
3. 如使用 imagegen，只探索视觉语言，不继承其图标、文案和数据。
4. 最后用真实接口快照、Playwright 截图和小程序渲染检查验证。
