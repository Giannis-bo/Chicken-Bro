# 微信 AI 调用小程序能力接入调研

日期：2026-07-03

## 结论

微信开放平台这次“小程序更好地被微信 AI 调用”的方向，本质不是让小程序再内置一个聊天机器人，而是把小程序变成微信 AI 可以发现、理解、调度和操作的服务能力。

对本项目来说，这不是替代“炸鸡队长来啦”，而是让“炸鸡队长来啦”从小程序内部入口，升级为微信 AI 生态里可被自然语言唤起的 WoW 分析能力。用户未来可能不是先打开小程序再点击智能分析，而是在微信 AI 里直接说“帮我看看冰法这版本怎么配装”“这个天赋能不能跑 SimC”，再由微信 AI 调用我们封装好的能力。

因此，适配重点不是重写聊天页，而是给现有 Chickenbro / WebSim / SimC / 数据可信度体系加一层稳定的微信 AI Skill 适配层。

## 公开信息口径

当前公开资料可确认的方向：

- 微信开放平台已面向开发者推进“小程序接入微信 AI 生态”，入口在小程序管理后台的 AI 能力相关配置，公开报道提到支持自动模式和开发模式。
- 自动模式更像由微信 AI 分析和操作现有小程序页面；开发模式则要求开发者把业务能力封装成可调用能力。
- CloudBase 的小程序 AI Skill 文档展示了典型形态：`SKILL.md` 描述能力，`mcp.json` 描述工具接口，`apis/` 承载原子 API，`components/` 承载原子组件，最终让微信 AI 通过自然语言意图调用小程序业务能力。
- 官方 demo 的技能结构也体现了同一思路：不是让 AI 随便读页面，而是把业务行为拆成可声明、可调用、可渲染的能力单元。

信息来源：

- [CloudBase Mini Program Skills 文档](https://docs.cloudbase.net/en/mp-skill)
- [CloudBase Skill 质量检查文档](https://docs.cloudbase.net/en/mp-skill/recipe-9-quality-check)
- [微信小程序 AI Mode Demo](https://github.com/wechat-miniprogram/ai-mode-demo)
- [新京报相关公开报道，搜狐转载](https://m.sohu.com/a/1033893437_114988)
- [IT之家相关公开报道](https://www.ithome.com/0/961/480.htm)

后续真正实施时，仍应以微信开放平台后台可见的最新接入文档、审核要求和内测能力为准。

## 对本项目的影响

### 1. 入口前移

当前产品路径是：

用户打开小程序 -> 进入“炸鸡队长来啦” -> 提问 -> 后端 Chickenbro / Codex / fallback 输出回答。

微信 AI 接入后的潜在路径是：

用户在微信 AI 中提问 -> 微信 AI 判断可调用“炸鸡队长来啦” -> 调用我们的 Skill -> 返回结构化卡片或打开小程序深链。

这会让小程序从“用户主动打开的工具”，变成“微信 AI 可分发的垂直能力”。对 WoW 这种强垂直、强术语、强决策场景，这是明显利好。

### 2. “炸鸡队长”需要被机器理解

用户知道“炸鸡队长来啦”是什么，但微信 AI 不一定知道。Skill 描述里必须明确表达：

- 这是魔兽世界当前版本分析工具。
- 能处理职业专精、天赋模板、装备模拟、SimC 任务、日志复盘等问题。
- 只能在有证据时输出强结论。
- 证据不足时必须返回 `partial` / `stale` / `blocked`，而不是让微信 AI 自己补结论。

这相当于一层新的“AI SEO”：页面标题、能力描述、参数名、返回字段、卡片文案都要能被微信 AI 正确召回。

### 3. 微信 AI 不应绕过项目信任边界

项目现有核心边界仍要保持：

- 通用魔兽建议可以走 Chickenbro direct chat，但不能包装成本地证据。
- DPS、排名、分位、SimC 输出等数字必须来自白名单证据。
- WebSim / Gear / Talent / SimC 的 `verified`、`partial`、`stale`、`blocked` 语义不能被微信 AI 改写。
- 原始 SimC profile、raw log、token、数据库内部字段不能暴露给微信 AI。
- 昂贵任务不能被微信 AI 自动无限触发，必须有确认、限流和任务状态查询。

微信 AI 应该是入口和调度层，炸鸡队长后端仍然是 WoW 事实、证据和回答边界的控制面。

## 推荐能力拆分

首批不要做一个大而全的“问炸鸡队长”接口，而是拆成若干可审计 Skill。

| Skill 能力 | 用户问题示例 | 后端依赖 | 输出形态 | 边界 |
| --- | --- | --- | --- | --- |
| `askChickenbro` | “冰法这版本怎么配装？” | `/api/chickenbro/messages` | 回答摘要 + 证据状态 + 打开聊天 | 继续使用现有 schema、evidenceRefs、allowedNumbers、fallback |
| `getSpecBuildOverview` | “现在惩戒骑大秘境强吗？” | builds / stat weights / data health | 专精概览卡片 | 无真实样本时只能说样本不足 |
| `listTalentTemplates` | “给我一个酒仙天赋模板” | `/api/websim/talents/import` 或 talent templates | 可导入模板列表 | 只返回可视化可导入或明确 partial 的模板 |
| `getGearSimulationSummary` | “这个专精装备模拟现在可用吗？” | `/api/websim/gear?mode=initial` | 装备模拟入口 + 数据状态 | 不把 partial 候选包装成 BiS |
| `createSimcAnalysisTask` | “帮我跑一下这个模板” | `/api/simulator/analyze` | 任务创建确认 | 必须用户确认，限制并发和成本 |
| `getSimcTaskStatus` | “刚才模拟跑完了吗？” | simulator task detail | 任务状态卡片 | 失败原因用产品文案，不泄漏 raw error |

## 技术接入建议

### 架构

建议新增微信 AI 适配层，而不是让 Skill 直接调用现有复杂接口：

```text
微信 AI
  -> Skill 描述 / 原子 API / 原子组件
  -> /api/ai/skills/*
  -> auth / rate limit / input normalization / trust guard
  -> Chickenbro / WebSim / SimC / data health
  -> skill-safe response
```

`/api/ai/skills/*` 的职责：

- 把微信 AI 参数转换成项目内部 class/spec/hero/scenario 等 canonical key。
- 校验用户身份、guest 能力和访问范围。
- 控制昂贵调用，例如 Codex、SimC、WCL。
- 裁剪输出，只返回 Skill 需要展示的安全字段。
- 统一返回 `evidenceState`、`dataStatus`、`nextAction`、`deepLink`。

### 原子组件

Skill 返回不应只有文本，建议准备几类卡片：

- 职业专精概览卡片：职业、专精、场景、数据状态、更新时间。
- 天赋模板卡片：模板名、来源、最高层数、是否可导入。
- 装备模拟入口卡片：当前可用性、缺口、打开模拟器。
- SimC 任务卡片：排队中、运行中、完成、失败、需要补输入。
- 炸鸡队长回答卡片：短回答、证据状态、继续追问入口。

卡片文案必须避免强结论污染，例如不要在 `partial` 时写“最佳装备”，应写“可编辑起点”“样本不足”“等待证据刷新”。

### 深链

微信 AI 返回的主要动作应该是打开明确页面：

- `/pages/simulator/simulator`：进入炸鸡队长聊天。
- `/pages/builds/talent-simulator?spec=...`：打开天赋模拟器。
- `/pages/builds/detail?spec=...&query=gear`：打开装备模拟。
- `/pages/simulator/simc?from=wechat-ai&spec=...`：进入 SimC 模板选择。
- `/pages/simulator/tasks?from=wechat-ai`：查看任务列表。

深链需要携带最少参数，复杂上下文留在服务端 session / task 中，避免在 URL 里塞 raw profile 或敏感数据。

## 产品策略

### 第一优先级：开发模式

自动模式适合让微信 AI 操作已有页面，但本项目的核心是证据判断和安全回答。仅靠自动模式，AI 可能能打开页面，却不一定理解数据状态。

因此首选开发模式：

- 微信 AI 负责意图识别和调用。
- 我们负责参数归一、证据校验、回答生成、成本控制。
- 返回结构化结果和卡片，不让微信 AI 自行拼强结论。

自动模式可以作为补充，用于页面导航和已存在页面理解，但不能作为可信结论来源。

### 第二优先级：只读能力先上线

首批接入应避免自动发起长任务。推荐 MVP：

1. `askChickenbro`
2. `getSpecBuildOverview`
3. `listTalentTemplates`
4. `getGearSimulationSummary`
5. `getSimcTaskStatus`

`createSimcAnalysisTask`、WCL 日志复盘、角色绑定和个性化推荐应放到第二阶段，并要求用户显式确认。

### 第三优先级：评测集

上线前要做固定评测集，覆盖：

- 职业/专精别名：冰法、冰霜法师、frost mage。
- 场景别名：大秘境、M+、单体、AOE、团本。
- 强结论诱导：问“最强职业”“最高 DPS”，证据不足时是否降级。
- 任务成本：用户一句话是否会误触发 SimC。
- 越权输入：raw log、token、后台字段是否被泄漏或引用。
- 数据状态：`stale`、`partial`、`blocked` 是否被卡片保留。

## 建议落地阶段

### Phase 0：接入资格与最新规范确认

- 在小程序管理后台确认 AI 能力入口、内测资格、审核要求。
- 拉取微信开放平台最新开发模式文档。
- 明确是否使用 CloudBase mp-skills 工具链，或使用微信开放平台指定的最终工具链。
- 确认原子组件可用形态、页面跳转限制、登录态传递方式。

### Phase 1：只读 Skill MVP

- 新增 `/api/ai/skills/*` 适配层。
- 只开放只读能力和任务状态查询。
- 返回统一 `skill-safe response`。
- 不改变现有 Chickenbro / WebSim / SimC 内部契约。

验收重点：

- 微信 AI 能正确召回“炸鸡队长来啦”。
- 职业专精参数能归一。
- 不产生未经证据支持的强结论。
- 不触发昂贵任务。

### Phase 2：动作类 Skill

- 增加 SimC 任务创建。
- 增加模板导入 / 保存前确认。
- 增加角色绑定后的个性化入口。
- 加入 rate limit、并发限制、成本观测。

验收重点：

- 用户明确确认后才创建任务。
- 第三个并发任务仍被阻断。
- 失败、blocked、timeout 都能产品化解释。

### Phase 3：观测和发布

- 在 analytics 中标记 `source=wechat_ai`。
- 记录 Skill 调用意图、参数解析结果、命中页面、失败原因。
- 在 admin / health 中单独暴露微信 AI Skill 健康状态。
- 用固定评测集做每次发布前 smoke。

## 风险

- 微信 AI 接入能力仍可能处于内测或快速变化阶段，文档和后台能力需要实施前复核。
- 如果只做自动模式，微信 AI 可能绕过证据状态，输出过强结论。
- 如果把 Skill 暴露得过宽，可能造成 Codex / SimC 成本不可控。
- 如果卡片文案不严谨，`partial` / `blocked` 会被用户误读为推荐结果。
- 如果身份和授权没处理好，可能出现跨 guest 读取任务或会话的问题。

## 当前项目应保持的原则

- 微信 AI 是入口，不是事实源。
- 炸鸡队长是回答边界控制面，不应被绕过。
- Skill 输出必须保留证据状态。
- 长任务必须确认后触发。
- raw SimC、raw log、secret、内部 blocker 原始栈不进入 Skill 响应。
- 首批先做只读和深链，动作类能力后置。

## Roadmap 建议

建议纳入：

- 炸鸡队长证据教练 v0
- 正式发布与刷新可观测
- 数据可信度与赛季同步完善
- 角色绑定与个人化工作台

建议状态：`待规划`。

原因：方向已经清楚，并且与“炸鸡队长来啦”的核心能力强相关，但还需要等待微信开放平台后台能力、Skill 工具链、审核规则和真实接入约束确认后再拆实施计划。
