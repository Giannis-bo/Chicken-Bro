# 炸鸡队长 Smart Question Chain 设计

状态：`正在推进`

分类：`Strict`

确认日期：2026-08-03

实施入口：[实施计划](2026-08-03-chickenbro-smart-question-chain-implementation.md)。本切片落实[统一 ChatBot 架构](2026-07-24-chickenbro-chatbot-design.md)和[能力演化控制面](2026-08-02-chickenbro-capability-evolution-design.md)的在线问题理解、受控能力规划与可观测缺口；不授权 Toolsmith、shadow、canary 或自动 promotion。

## 用户场景与承诺

玩家会用自然语言、社区简称和带时效的版本问题提问，例如“奶骑在 12.1 PTR 强度如何”或“不是测试服，元素萨现在版本大秘境强度如何”。玩家不应理解 Tool、来源 API 或版本化 Registry，也不应因用词不是 canonical 英文专精名、显式纠正上一轮游戏阶段，或来源未被调度而收到“没有抓取能力”的泛化回答。

本切片的承诺是：

1. 后端把自然语言解析为通用 `QuestionFrame`，分别表达实体、游戏阶段、版本、问题类型、场景、证据需求与仍有歧义的字段；简称是实体解析输入，不是回答模板。
2. 对时效或 PTR 问题，后端按证据需求发现受控能力，而不是仅凭 `general/community_build/personal_wcl` 这一层分类静默放弃。显式正式服纠正优先于历史 PTR 上下文，且不会继承无关补丁号。
3. 命中允许的当前来源能力时，先在有界预算内读取匹配来源：PTR/改动使用官方当前来源；正式服大秘境强度使用新鲜 Raider.IO 高层样本。WCL 只有在运维显式配置了当前 M+ encounter、partition 与赛季标签时，才读取一页公共样本作为辅助覆盖证据；否则返回 literal `partial`，不猜测目标。来源、版本/适用范围、查询时间与限制进入可引用 `ToolResult`。
4. 回答必须区分“已确认改动”“社区高层趋势”“当前公共日志样本”和“尚无足够比较样本的强度结论”。Raider.IO 才能满足本切片的同职责高层横向信号；WCL 单专精单页不得冒充 Tier。无样本时状态为 `partial`，而不是冒充排名，也不是谎称系统无检索能力。
5. 未能满足的证据需求进入 owner-bound Trace 的脱敏字段，供后续 CapabilityGap 聚类使用；不把玩家原话、模型回答或一次纠正写成公共事实。

## 非目标

- 不按单个提问、职业或补丁写死回答。
- 不允许模型访问任意 URL、SQL、Shell、文件、密钥或客户端提交的 Tool ID。
- 不抓取未批准的 Wowhead、Icy Veins、Archon 或社区站点。Archon 目前只有 reference URL，不是可用于结论的当前数据源；只有获得授权 API/合作数据或另行批准的受控采集方案后才能加入比较链路。
- 不写入来源缓存、不触发全量资讯同步、不修改个人模板、SimC、会话 owner、前端消息 API 或已有 Tool 的语义。已有的 WCL v2 OAuth 只允许读取一个公开、非 owner-bound 的大秘境排行页；个人报告复盘仍走原有 Tool。
- 不在本切片实现跨 owner CapabilityGap 表、Toolsmith、候选代码生成、shadow/canary、自动 promotion 或自动回滚。

## 方案对比

| 方案 | 结果 | 风险 | 结论 |
| --- | --- | --- | --- |
| 为 NQ/PTR 增加固定回复和更多 `if/else` | 修复单句 | 每个新说法继续漏路由，无法证明证据范围 | 不采用 |
| 让在线 Codex 自行联网、选择任意 tool_box | 表面通用 | 来源、prompt injection、时效、成本与可复现实验失控 | 不采用 |
| QuestionFrame + capability plan + 已批准来源 workflow + Trace observation | 可推广至版本、职业、构筑、任务类问题；来源边界可测 | 需扩展 Registry 合同与受控 Tool | 采用 |

## 目标在线链路

```text
raw message + same-session history
  -> QuestionFrame
       subject: class/spec candidates and resolution
       scope: retail|ptr, patch, region, scenario, as-of
       questionType: current_research | community_build | personal_wcl | general
       evidenceNeeds and unresolvedFields
  -> Capability Planner
       -> active Registry manifests matching evidenceNeeds and scope
       -> selected capabilities + unmet evidence needs
  -> backend-owned adapter execution
       -> existing fresh Raider.IO cache / configured bounded public WCL adapter
       -> official current-source adapter (bounded live read)
  -> ToolResult validation + evidence/freshness gate
  -> bounded context + natural answer
  -> owner-bound Trace v3 projection
       -> semantic request + selected capability + unmet evidence kind
```

`QuestionFrame` 是结构化查询合同，不包含完整聊天或模型推理。最小形态如下：

```json
{
  "schemaRevision": "chickenbro-question-frame-v1",
  "questionType": "current_research",
  "subject": {"classKey": "paladin", "specKey": "holy", "resolution": "resolved"},
  "scope": {"productPhase": "ptr", "patchVersion": "12.1", "region": "cn", "scenarioKey": ""},
  "evidenceNeeds": ["official_current_changes", "comparative_strength_signal"],
  "unresolvedFields": ["scenarioKey"]
}
```

The planner is deterministic and consumes only this frame plus the active immutable Registry Release. It never accepts a model-selected implementation reference. `current_research` may select the official source Tool for a PTR/patch/change evidence need, and selects the two public community-strength Tools only for resolved retail **Mythic+** comparative-strength research. `scenarioKey` is a Registry discovery constraint, so raid/PvP questions never receive M+ evidence. `community_build` and `personal_wcl` retain their existing Tool selection semantics.

## 官方当前来源 Tool

`source:current-wow-sources:v1` is a repository-owned, read-only adapter. It has a 10-second total budget, receives only sanitized QuestionFrame fields, and reads the two approved official sources already registered by the news subsystem:

- Blizzard News;
- Blizzard Forums / In Development.

It first uses supplied fresh eligible facts only when they have a matching product phase and source capture time. Otherwise it performs a bounded in-memory collection with one article per approved source and a per-request timeout; it neither persists articles nor starts scheduled syncs. The adapter matches the frame subject and patch scope against the returned source record, emits at most three compact evidence rows, and returns:

- `source_reference` when it has a matching official fact;
- `partial` when it has phase-level current facts but no direct subject or comparison evidence;
- `failed` when no source can be read inside budget.

An official patch note validates an ability change, not a cross-spec strength ranking. The Tool must include `comparative_strength_signal_missing` until a separately approved comparative source or simulation evidence is present. This is a trust boundary, not a fallback template.

## 正式服社区强度来源

`source:raiderio-strength:v1` reuses the existing fresh, backend-owned Raider.IO cache. It emits only the queried specialization's de-identified, same-role high-key signal: `aggregate_runs` 的 documented `bestScore`/key/sample fields and placement among same-role cache entries. It cannot assert representation, completion rate, DPS, a universal Tier, or an individual character conclusion.

`source:warcraftlogs-public-rankings:v1` uses existing WCL v2 OAuth credentials only with the explicit `WOW_CHICKENBRO_WCL_PUBLIC_MPLUS_ENCOUNTER_ID` / `...PARTITION` / `...SEASON_LABEL` target contract. It never reuses the generic template-sync target or heuristically selects a zone. It reads exactly one matching public page with an eight-second network timeout, 60-second in-process TTL, identical-request singleflight and a 12 request/minute process budget. It retains no player names or combat-event payload, and emits only metric type, row count, configured encounter/partition/season window, source URL, query time and limitation. A WCL per-encounter metric is supplementary coverage evidence, not a cross-spec Tier table.

For a retail M+ strength question, the answer layer synthesizes only what returned sources support: a current Raider.IO high-key trend, optionally complemented by a configured WCL public sample. A returned Raider.IO strength result creates a deterministic postcondition: the model must cite it and cannot answer “没有数据/自己去 WCL、Raider.IO 或 SimC 查”. It must state each source's limitation and leave source disagreement, stale cache, empty rankings, absent target contract or credential failure as literal `partial`/`failed` evidence. `source:archon:*` is deliberately absent: an Archon navigation link or legacy compatibility field is not a live source result.

## Answer and Trace rules

The bounded context adds `questionFrame` and `capabilityPlan`. The model receives source facts and allowed evidence references, but may not present a numeric rank, DPS, percentile or superiority claim without authorised numeric evidence. When a community strength source returned evidence, the `source_reference` prompt must answer the requested topic first, compare/summarize the returned signals, list their limitations specifically, and must not ask the player to manually search WCL, Raider.IO or SimC. Post-validation rejects an answer that omits the returned comparative evidence reference or uses the no-data/manual-lookup fallback; a rejected normal or streamed model reply instead produces the same generic, source-derived fallback (and guarded streams buffer text until validation). It asks for scenario only when it materially changes the conclusion.

Trace v3 adds only de-identified fields: `questionType`, subject resolution status, requested evidence kinds, selected capability IDs and unmet evidence kinds. The Trace never stores raw entity text, message text, source body, user identity, full prompt or model chain-of-thought. A missing expected capability produces `tool_missing`; an unsatisfied required evidence kind produces `evidence_missing`. These are observations only, not automatic product facts or release requests.

## Impact, risks and rollback

| Classification | Surfaces |
| --- | --- |
| must change | question parsing, Registry schema/active release, community-source adapter binding, bounded context, trace/eval, PostgreSQL migration and candidate deployment |
| must not change | owner isolation, chat request/response schema, personal templates, SimC, owner-bound WCL report execution, scheduled refresh behavior, disabled third-party sources |
| risk unknown | official feed/WCL response latency, explicit public target availability and high-key signal interpretation; resolve with bounded candidate smoke and fixture coverage |
| evidence required | semantic routing matrix, source/freshness/timeout matrix, model-output guard, migration/Registry identity, candidate API smoke, service/health/logs and user WeChat acceptance |

The database migration only appends an immutable manifest/release and moves the active Registry pointer after backup. Candidate failure rolls back code and the recorded pre-deploy active pointer (currently `chickenbro-tools-2`), never an assumed historical version; it does not delete historical manifests, traces or user messages. Network failure remains a literal source failure/partial evidence state and never starts asynchronous refresh services.

## User acceptance

The candidate must demonstrate, in the real chat entry:

1. “NQ/奶骑在 12.1 PTR 强度如何” is framed as holy paladin + PTR + current research and selects the official source capability.
2. “不是测试服，元素萨现在版本大秘境强度如何” is framed as elemental shaman + retail + Mythic+, clears inherited PTR/patch scope, and selects both community-strength capabilities. “12.1 PTR 当前版本…” still resolves PTR; a subsequent “那天赋呢” does not inherit the prior strength intent.
3. A formal raid/PvP strength question does not select either M+ capability; it keeps its own scenario and reports the actual missing comparable evidence.
4. The retail answer cites returned Raider.IO evidence, compares/summarizes its bounded signal, and post-validation rejects a no-data/manual-lookup fallback. WCL can supplement only when its explicit current-M+ target contract is configured.
5. A source timeout, stale cache, absent WCL target contract, empty rankings or missing credentials reports the actual missing evidence and still does not manufacture Tier/DPS/ranking numbers.
6. A normal WCL report or Raider.IO build path remains unchanged, and no unapproved host is contacted.
