# Equipment Simulator Capability Architecture Design

> 日期：2026-07-10
>
> 状态：书面规格已批准 / 待实施计划 / 未实施
>
> Harness：Strict
>
> 基线：`main@d65e21e`
>
> 事实入口：`docs/project-state.json`、`docs/roadmap.md`、`docs/harness.md`

## 1. 结论

装备模拟应重构为一个可信的装备配置工作台，而不是 DPS 比较器、优化器或系统 BiS 生成器。

用户选择装备、变体、宝石、附魔、美化、制造选项和套装后，系统立即返回四类结论：

1. 当前配置是否合法。
2. 确定性的原始属性和属性变化。
3. 每个结论的来源、规则和版本证据。
4. 是否可以生成可执行 SimC profile，以及异步属性快照当前处于什么状态。

社区模板不是另一套逻辑。它只是带来源证据的预填 Selection Intent，必须经过与手工配置完全相同的 Authority Context、Resolver、规则矩阵、Evidence Ledger 和 Serializer。当前赛季非法、错季、过期或不可验证的候选必须在选举和发布阶段被拒绝，不能作为公共“待修复模板”出现。

总体方案采用：

- Modular Monolith；
- Versioned Catalog / Release；
- 一个 Canonical Gear Instance Resolver；
- Active Season Manifest 原子组合正式数据；
- PostgreSQL-only Authority Context；
- 后端 Serializer；
- 独立异步 SimC Stat Snapshot Worker；
- 七阶段 Strangler Delivery。

不引入微服务、事件溯源、Redis、Celery、通用规则 DSL、通用 Claim DAG 或第二套前端状态框架。

## 2. 用户承诺与成功标准

### 2.1 用户承诺

- 用户每次修改装备后，可以立即看到服务端确认的合法性和确定性原始属性。
- 非法选择必须指出具体槽位、选项、规则和证据，不使用笼统的“模拟失败”。
- 属性百分比只有来自当前 SimC Runtime 的 verified JSON snapshot 才显示为 verified。
- SimC 暂不可用时，原始 rating 仍可显示；系统不能伪造百分比或沿用不相容的旧结果。
- 导入社区模板后，系统仍按当前赛季和当前 Gear Release 重新解析。
- 公共社区入口宁可对某个专精为空，也不能展示已知非法、错季、过期或系统伪造模板。

### 2.2 业务完成标准

- 手工配置与社区模板共用一个 Resolver。
- 前端不再拥有最终合法性、Tier 身份、套装计数、总属性或 SimC readiness 判断。
- 当前合法 winner 覆盖率以 40/40 为可靠性 SLO；任一公开 winner 都必须合法。
- Gear、Community、Rule、Serializer 和 SimC 变更均可追溯到不可变 release/revision。
- 新 runtime 变更在合入前通过 Candidate Deployment Gate。
- 失败时有明确的 fail-closed、降级和回滚行为。

### 2.3 不能冒充完成的证据

- 40/40 HTTP 200 不能证明模板合法。
- 单元测试通过不能证明云端 Serializer 和 SimC Runtime 可执行。
- `redirected_base_stats` 出现在 allowlist 不能证明 Catalyst 已实现。
- SimC 可以解析 profile 不能替代装备规则权威。
- 前端本地属性求和不能替代当前服务端 Resolved Snapshot。
- 旧 snapshot 存在不能证明它与当前 revision 相容。

## 3. 当前已有能力

| 已有能力 | 当前 Owner | 本设计处理方式 |
| --- | --- | --- |
| `/api/websim/gear` initial/slot 窄读取 | `server/postgres_cache_store.py` + PG read-model selectors | 保留为 Catalog Browse，不承担最终实例解析 |
| 结构化 `gearBySlot` / `enhancementBySlot` 保存 | 后端与前端现有保存链 | 保留并迁移为 Selection Intent；历史 snapshot 仅审计 |
| 后端 SimC gear line Serializer | `server/websim_payload.py` | 通过 compatibility facade 迁移到 Resolver 输出，不下放前端 |
| SimC JSON `buffed_stats` 解析 | `server/websim_payload.py` | 保留为 verified stat source，增加轻量执行模式与异步 Worker |
| 基础装备合法性 | `server/gear_legality.py` | Characterization 后纳入版本化 Rule Matrix |
| 宝石、附魔、美化和制造检查 | 多处 `websim_payload.py` helpers | 收敛到同一 evaluator chain |
| observed-only 公共社区入口 | `server/gear_public_contract.py`、PG selectors | 保留来源边界，替换 provisional/覆盖式发布链 |
| 12.1 Season Manifest 健康骨架 | `server/news_backend.py` + 既有 12.1 设计 | 升级为正式公共读控制面，而不另造平行机制 |
| systemd 定时任务与 SimC Runtime 更新 | `server/*.service`、`server/*.timer` | 复用调度方式，新增独立 stat snapshot worker |
| `scripts/perf_probe.py` | 性能验证脚本 | 扩展 Resolve cold/warm/concurrency 场景 |
| Repo-native Harness v0.5 | `docs/harness.md`、验证脚本与 owner maps | 作为每个 runtime PR 的交付门禁 |

## 4. 已确认的当前风险

1. PostgreSQL-only 路径中，`conn=None` 的 enhancement merge 可以接受客户端伪造的 embellishment；现有 server-catalog precedence 测试主要覆盖 SQLite。
2. 当前 `/api/websim/gear/stats` 在 HTTP 请求线程同步运行 SimC，后端超时 45 秒、前端超时 60 秒，profile 默认 1000 combat iterations。
3. 当前 Catalyst gate 可因 allowlist 中存在 `redirected_base_stats` 而误报 verified，但 Serializer 并未证明能输出或执行该字段。
4. 当前前端仍推断 Tier/套装身份、计数和部分总属性。
5. 当前 community sync 先 replace active rows，再做 preflight。
6. 当前 public predicate 接受 `observed_provisional`；该状态还与旧 `scenarioResults` 耦合，不能代表装备合法。
7. `COMMUNITY_TEMPLATE_REVISION` 和 `GEAR_CATALOG_REVISION` 仍包含 schema 常量语义，不能代表一次真实数据 release。
8. `pages/common/api-client.js` 会丢弃非 2xx 的结构化 body，409/503 无法传递给装备状态机。
9. 当前 40 专精 smoke 主要证明 Catalog/Public Payload 遍历；真实 SimC stat snapshot 只覆盖较小的 fake/core-spec 集合。
10. 核心职责集中在多个热点大文件，继续添加分支会扩大结构债和 review 风险。

## 5. 事实 Owner 与信任边界

### 5.1 Client

Selection Intent 是唯一允许的客户端装备输入结构，但它始终是不可信输入。客户端可以提交 ID 和用户选择，不能提交最终事实。

客户端可以拥有：

- 草稿与确认交互；
- 当前 Intent；
- `intentVersion`；
- 请求 serial、debounce 和竞态取消；
- 服务端 constraints 对应的按钮禁用；
- 已验证事实的展示和排序；
- last verified snapshot 的离线只读展示。

客户端不能拥有：

- 最终合法性；
- Template 修复；
- Tier/Catalyst 身份推断；
- 套装计数；
- 最终属性总计；
- SimC readiness；
- SimC profile 字符串拼装；
- 非 2xx problem 的重新分类。

### 5.2 Backend

- PostgreSQL Store/Adapter 拥有正式 Release、SQL、candidate write、sync/write/backfill 和 Authority Context 加载。
- `gear_resolver.py` 拥有纯解析、规则执行、静态属性与 Evidence Claims。
- 后端 Serializer 拥有标准 SimC profile 和 stat snapshot profile 的生成。
- Release owner 拥有 candidate/preflight/promotion/rollback，不允许定时任务绕过 active Manifest。
- Health/Admin 只投影真实状态，不把 partial、blocked 或 allowlisted 改写为 verified。

### 5.3 SimC

SimC 是 profile executability 和 verified stat snapshot 的执行权威之一，不是装备赛季、来源、unique-equipped、选举资格或公共可见性的唯一合法性权威。

## 6. 总体架构

```text
External sources / current APIs
    |
    v
normalize + evidence capture
    |
    v
immutable candidate releases
    |
    +--> rule/catalog/community preflight
    |          |
    |          +--> rejected / blocked / internal standby
    |
    v
release registry
    |
    v
ACTIVE RETAIL SEASON MANIFEST  <---- pointer rollback
    |                    |
    |                    +--> compatible community winner map
    v
catalog browse (/gear initial + slot)
    |
user creates untrusted Selection Intent
    |
    v
load manifest + bounded Authority Context
    |
    v
CANONICAL GEAR INSTANCE RESOLVER
    |
    +--> Resolved Snapshot + typed Evidence Ledger
    |        |
    |        +--> immediate legality + raw attributes
    |
    +--> backend SimC Serializer
             |
             +--> standard /profile
             |
             +--> stat_snapshot_v1 signature
                         |
                         v
                 PG snapshot job/store
                         |
                         v
                 bounded systemd worker
                         |
                         v
                 verified SimC JSON stats
```

### 6.1 架构选择

- Modular Monolith 保持部署简单。
- Release Registry、Resolver 和 Snapshot Worker 是清晰边界，不是独立微服务。
- 旧大文件先作为 facade/adapter，按 characterization 拆出职责。
- 一次最多引入两个内部边界；超过约 8 个文件的 PR 必须解释，而不是机械禁止。

## 7. Selection Intent、Dependency Vector 与签名

### 7.1 Selection Intent

Selection Intent 至少包含：

```json
{
  "schemaRevision": "selection-intent-v1",
  "authoredAgainst": {
    "seasonRevision": "...",
    "gearCatalogRevision": "..."
  },
  "eligibilityContext": {
    "classKey": "...",
    "specKey": "...",
    "level": 80
  },
  "slots": {
    "head": {
      "itemId": "...",
      "variantKey": "...",
      "gemOptionIds": [],
      "enchantOptionId": "",
      "embellishmentOptionId": "",
      "craftedOptionId": "",
      "catalystOptionId": ""
    }
  }
}
```

客户端不能提交最终属性、最终 itemSetId、最终合法状态、服务端 evidence、最终 SimC options 或 readiness。

### 7.2 Dependency Vector

每个解析结果必须物化自己的依赖向量：

```text
seasonRevision
gearCatalogReleaseId / gearCatalogRevision
gearRuleRevision
resolverContractRevision
serializerRevision
simcRuntimeRevision
statPolicyRevision
selectionSchemaRevision
```

Community origin evidence 另带：

```text
communityTemplateReleaseId / communityTemplateRevision
templateOriginSignature
validatedAgainstGearReleaseId
```

### 7.3 三层签名

1. `selectionSignature`
   - canonical Selection Intent；
   - class/spec/level eligibility context；
   - selection schema revision。
2. `resolvedGearSignature`
   - selection signature；
   - season、gear release、rule、resolver revisions。
3. `profileSignature` / `statSignature`
   - resolved gear signature；
   - character context hash；
   - talent import hash / hero context；
   - serializer、SimC runtime、stat policy revisions。

每个 cache、claim 和 snapshot 必须声明自己使用 Dependency Vector 的哪些字段。不能用一个不透明的总 hash 掩盖依赖，也不能只用 item IDs。

## 8. Authority Context 与版本化规则矩阵

### 8.1 Authority Context

路由/Store 在一个只读事务内，根据 Active Manifest 和 Selection Intent 加载窄 Authority Context。Resolver 签名固定为：

```text
resolve(selection_intent, authority_context) -> resolved_snapshot
```

Resolver 不接受数据库连接，不隐式查询，不在 `conn=None` 时相信客户端 options。

缺少权威字段、release 不相容或 revision mismatch 必须 blocked，不能默认合法。

### 8.2 Rule Matrix

v1 规则矩阵至少覆盖：

1. 赛季、release、物品身份和等级要求；
2. 槽位与 inventory type；
3. 职业、专精、护甲和武器资格；
4. 主副手、双持、双手武器及专精例外；
5. unique-equipped、同类唯一和重复物品；
6. socket 数量、宝石类型和唯一宝石；
7. 附魔适用性、物品类型和符文熔铸；
8. 美化、制造选项和全角色数量限制；
9. Catalyst/Tier Overlay 资格；
10. 跨槽位、跨物品和套装聚合规则。

每条规则拥有：

- `ruleId`；
- `ruleRevision`；
- scope；
- parameters；
- authority source references；
- deterministic blocker code；
- explicit evaluator function。

规则描述可以数据化，但不建设动态规则 DSL。执行顺序固定，Rule Matrix 的 revision 纳入 Dependency Vector。

## 9. Canonical Resolver

### 9.1 Slot Pipeline

```text
Base Item
  -> Variant
  -> Tier/Catalyst Overlay
  -> Effective Capabilities
  -> Gems/Enchants/Embellishments/Crafted Options
  -> Resolved Slot
```

Overlay 必须先于 enhancements，因为 Overlay 可能改变有效属性和能力；enhancement 的最终适用性必须基于 Overlay 后实例判断。

### 9.2 Whole-character Pipeline

```text
Resolved Slots
  -> cross-slot legality
  -> unique/quantity limits
  -> canonical itemSetId aggregation
  -> deterministic static attributes
  -> profile executability readiness
  -> typed Evidence Ledger
  -> backend Serializer input
```

套装身份只使用 canonical `itemSetId` / verified overlay identity，不使用名称或 source type 猜测。动态套装效果只展示为 active effect，不换算为伪属性或 DPS。

### 9.3 Resolved Snapshot

至少包含：

- contract revision；
- evaluated Dependency Vector；
- selection/resolved signatures；
- per-slot resolved instances；
- effective capabilities；
- per-slot and aggregate legality；
- deterministic raw stats and deltas；
- set state and active dynamic effects；
- profile readiness；
- constraints for the next valid user actions；
- typed Evidence Ledger；
- blockers/problems。

保存时同时保留 Intent 和 Resolved Snapshot 审计副本。历史 Snapshot 只能查看，当前执行必须重新 Resolve Intent。

## 10. Evidence Ledger v1

Ledger 是当前 Resolver 响应投影，不是事件日志。

### 10.1 五组 Claims

1. `identity_options`
   - item、variant、gem、enchant、embellishment、crafted、tier overlay。
2. `provenance`
   - catalog/source、community template、采集时间、release、evidence revision。
3. `legality`
   - 每条通过或阻断的 Rule Claim。
4. `static_attributes`
   - 单槽属性、增强属性、套装计数、全角色确定性合计。
5. `profile_executability`
   - serializer capability、SimC runtime 和 profile readiness。

### 10.2 Claim Identity

- `claimKey` 是稳定语义位置，例如 `slot:head:variant`。
- `claimId` 是当前事实实例指纹，包含 claim key、value digest、source IDs、rule revision、resolved signature 和 Dependency Vector。

普通 Claim 不建立任意 DAG。只有总属性、整套合法性和 profile readiness 等聚合 Claim 使用有限 `dependsOn`。

当前 Resolver Claim 只允许 `verified` 或 `blocked`：

- `pending` 属于异步 Job/Envelope；
- `stale` 属于历史 Snapshot 的展示状态；
- 两者都不能伪装成当前确定性事实。

`sourceRefs` 指向不可变 Evidence Record，不保存无法审计的自由文本作为唯一证据。

## 11. Result Envelope 与 HTTP 语义

统一响应：

```json
{
  "contractRevision": "gear-result-envelope-v1",
  "requestId": "...",
  "status": "resolved|blocked|pending|unavailable",
  "releaseContext": {},
  "data": {},
  "problems": []
}
```

Problem kinds：

- `INVALID_INTENT`
- `ILLEGAL_SELECTION`
- `REVISION_CONFLICT`
- `AUTHORITY_UNAVAILABLE`
- `SIMC_UNAVAILABLE`
- `INTERNAL_ERROR`

HTTP：

| HTTP | 语义 |
| --- | --- |
| 200 | 已解析的 domain result，包括合法或 blocked selection |
| 202 | 异步 stat snapshot pending |
| 400 | 请求结构无法解析 |
| 409 | authored/current revision conflict，需要重新 Resolve |
| 503 | Authority 或 SimC 暂不可用 |
| 500 | 未分类内部错误 |

前端 `requestJson` 增加 opt-in `responseMode: structured-problem`：

- 非 2xx 也先解析合法 Result Envelope；
- 409/503 problem 不进入泛化 fallback；
- 202 是正常 pending；
- 只有网络失败、超时或非法响应才标记 offline；
- last verified snapshot 可 stale/read-only 展示，但不能启动新 SimC；
- 409 保留 Intent，按当前 revision 重新 Resolve，不静默重解释并执行 SimC。

## 12. API Contracts

### 12.1 Catalog Browse

`GET /api/websim/gear?mode=initial|slot`

- 保留现有首包与按槽加载；
- 返回可浏览 candidates、capabilities 和 catalog health；
- 不返回客户端可自行组合的最终合法事实。

### 12.2 Resolve

`POST /api/websim/gear/resolve`

- 低成本同步；
- 只接受 Selection Intent；
- 返回 legality、raw stats/deltas、sets、constraints、evidence、profile readiness；
- 不运行 SimC，不比较 DPS，不推荐最佳装备。

### 12.3 Profile

`POST /api/websim/profile`

- 重新 Resolve Intent；
- 使用 canonical Resolved Snapshot 生成标准完整 SimC profile；
- 前端不拼 profile。

### 12.4 New Stat Snapshot API

`POST /api/websim/gear/stat-snapshots`

- 重新 Resolve Intent；
- server-generated stat signature；
- cache hit 返回 200 verified；
- miss/get-or-start 返回 202 pending；
- saturation/runtime unavailable 返回结构化 503；
- 不返回 DPS。

### 12.5 Legacy Compatibility

现有 `POST /api/websim/gear/stats` 在迁移期：

- 保持旧客户端 200 响应 shape；
- 改用 `stat_snapshot_v1`，不再跑 1000 combat iterations；
- 全局并发限制为 1；
- 新前端禁止调用；
- 在客户端遥测满足退役阈值后再废弃。

## 13. SimC Execution

### 13.1 两种 Serializer Execution Flavor

1. `standard_profile`
   - 完整可执行 profile；
   - 保留标准场景参数；
   - 用于导出和显式 SimC 执行能力。
2. `stat_snapshot_v1`
   - 与 standard profile 共用完全相同的 actor、talents、gear 和 preparation facts；
   - `iterations=1`；
   - 不计算 scale factors；
   - 不保存或展示 DPS；
   - 最短 runtime 由 40 专精真实 smoke 校准；
   - 输出 JSON `buffed_stats`。

`profileReadiness` 与 `statSnapshotStatus` 必须分开表达。

`profileReadiness=ready` 的准确含义是：当前 Serializer 能生成 profile，且 active SimC Runtime 已通过保留相同 actor、talents、gear、preparation 和 APL 输入的最小 executability probe。它不表示完整战斗模拟已完成，不证明 APL 的战斗质量，也不产生 DPS 结论。

### 13.2 PG Snapshot Store 与 Worker

- 独立 PostgreSQL snapshot/job 表，不复用用户 `simulator_tasks`。
- unique stat signature 实现跨请求、跨进程 single-flight。
- API 不在 HTTP request thread 启动 SimC。
- `wow-gear-stat-snapshot-worker.service` 使用 lease、heartbeat 和 expired-job reclaim。
- 默认一个 SimC child；候选机压测通过后才允许配置为两个。
- 设置 global queue 和 per-client active limit。
- timeout 进入短期 cooldown；确定性 blocker 持续到相关 revision 变化。
- Health 暴露 queue depth、oldest age、running、timeouts、cache hit rate 和 worker revision。

## 14. Community Template Election 与 Release

### 14.1 Community Template 是什么

- 真实玩家 observed profile 的来源证据；
- 预填 Selection Intent；
- 不等同于系统 BiS；
- 不因存在 `scenarioResults` 自动合法；
- 不因缺少 DPS 结果自动非法。

### 14.2 Candidate Eligibility

每个 candidate 必须：

- 当前赛季；
- 真实来源证据有效；
- 变体和必要选项完整；
- 通过当前 Gear Release 的 canonical Resolver；
- 无 legality blocker；
- 记录 `validatedAgainstGearReleaseId`；
- freshness 合格。

`observed_provisional` 只允许保留在内部候选池，不能成为 public winner。

### 14.3 Release Status

- `verified`：40/40 专精都有合法 current winner。
- `degraded`：部分专精为空，但所有公开 winner 都合法。
- `blocked`：出现非法 winner、release integrity 问题、错 gear binding 或系统性 authority failure。

40/40 是必须持续追求的 SLO，不是诱导系统展示非法 fallback 的理由。

旧 winner 只有在 freshness、当前 Resolver、当前 gear release 和来源证据全部重新通过时才能 carry-forward。缺少合法 winner 的专精公共入口为空；其他专精不因单点缺失被冻结。

## 15. Release Registry 与 Active Season Manifest

### 15.1 不可变 Releases

Gear 和 Community 独立生成 candidate release，每次真实数据构建都有不可变 `releaseId`。现有 `gearCatalogRevision` / `communityTemplateRevision` 名称继续作为兼容 label，但不能再用 schema 常量代表数据 release。

### 15.2 正式读组合

正式小程序只读取一个 active retail Season Manifest：

```text
seasonRevision
gearCatalogReleaseId
communityTemplateReleaseId | null
talentCatalogRevision
simcRuntimeRevision
rule/serializer/capability revisions
rollbackSeasonRevision
```

Gear G2 可以先激活为：

```text
{ gear: G2, community: null }
```

兼容 Community C2 完成后再原子切换为：

```text
{ gear: G2, community: C2, C2.validatedAgainst: G2 }
```

每个请求只读取一次 Manifest，并用 release ID 约束后续查询。回滚只切 Manifest pointer，不逐个回滚子表。

### 15.3 Community Migration

1. 新 Candidate Release 在 inactive/shadow 表生成。
2. 先 Resolve/preflight，再成为可发布 release；绝不先覆盖 active。
3. 当前合法数据重新验证并导入为 `legacy-import-r0`。
4. 新旧 reader shadow compare 40 专精 winner、gear signature、legality 和 provenance。
5. Candidate deployment 通过后切 Active Manifest。
6. 切换后不允许静默 fallback 旧表；需要恢复时回滚 Manifest。
7. 旧表稳定两个 release 周期后才进入退役计划。

## 16. Scheduled Refresh 与自动发布

### 16.1 节奏

- Daily：增量采集、community election、candidate validation。
- Weekly：全量证据、规则和 catalog 深审。
- Revision-triggered：Gear/Rule/Serializer/SimC 变化触发 40 专精全量重验。

### 16.2 Risk-classified Promotion

- 所有采集自动写 Candidate，不直接写 active。
- 同 Gear Release 的 community winner 更新在完整 gate 通过后可自动发布。
- 已知非法或过期的 active winner 必须自动下线，对应专精置空并告警。
- 旧 winner 仍合法但新 candidate 覆盖下降时，保留旧 winner、阻止 candidate promotion 并主动重选。
- 同赛季、同 schema、低风险 additive gear 更新可在完整回归后自动发布。
- 新赛季、rule、serializer、Catalyst capability、schema migration 和高风险属性变化必须受控 cutover。
- SimC Runtime 可由既有自动化构建 candidate，但 readiness/promotion 必须通过真实 smoke 和 Manifest compatibility gate。
- 每次 promotion 记录 reason、diff、gate result 和 rollback target。

## 17. Catalyst 与 Tier

### 17.1 当前赛季

使用 `direct_tier_item` capability：用户直接选择固定套装，不显示转换 UI。

### 17.2 12.1

`preserve_base_secondary_stats` 保持 disabled/candidate，直到以下证明全部 verified：

1. Catalog 中存在带来源的 Overlay Policy；
2. Resolver 生成预期最终属性和 Claims；
3. Serializer 实际输出支持的 SimC 表达；
4. Active SimC Runtime 可解析并输出预期 JSON；
5. 真实 Catalyst fixture smoke 通过；
6. 前端能解释 base stats retained 与 tier identity overlay；
7. Active Season Manifest 绑定 capability revision。

Allowlist 只允许研究，不是 verified 证据。现有虚假 Catalyst 绿灯必须在 Phase 0 改为 fail closed。12.1 实现已记录在根目录 `TODOS.md`。

## 18. Frontend Workbench State

新增无依赖纯模块 `pages/builds/gear-workbench-state.js`，管理：

- confirmed Intent；
- draft edits；
- `intentVersion`；
- latest Resolve serial；
- stat snapshot signature/status；
- last verified snapshot；
- structured problems；
- offline/read-only 状态。

状态流：

```text
confirmed
  -> editing draft
  -> confirm intentVersion+1
  -> resolving
       -> resolved legal / resolved blocked / revision conflict / offline
  -> optional stat snapshot get-or-start
       -> pending / verified / unavailable
```

旧请求返回时必须比较 request serial 和 intentVersion；过期响应不能覆盖新 Intent。

## 19. 性能合同

### 19.1 Resolve Query Budget

每次 cold Resolve：

- 一个 read-only transaction；
- 查询数不随槽位数量增长；
- 最多三个有界批量查询：
  1. Active Manifest / Dependency Vector；
  2. selected items、variants、overlays、capabilities；
  3. selected enhancements、rules、evidence。

Resolver 内部零数据库调用。

### 19.2 Cache

- bounded in-process LRU；
- key 使用对应完整 Dependency Vector；
- deterministic illegal result 可短期缓存；
- authority/runtime transient failure 不缓存；
- 同时设置 entries 和 memory budget；
- revision change 自然失效。

### 19.3 SLO

- warm server p95：不高于 200ms；
- cold server p95：不高于 500ms；
- Candidate Harness 记录 p50/p95/p99、查询数、cache hit rate、内存和 before/after。

性能 fixture 覆盖 16 槽、完整 enhancements、set、Catalyst candidate、community import、cold/warm、并发 1/5/20、合法/非法/blocked。

## 20. Test Strategy

继续使用 Python `unittest` 和 Node `node:test`，不增加测试框架依赖。

### 20.1 Coverage Map

```text
Selection Intent
  +-- malformed ------------------------------> 400 INVALID_INTENT
  +-- authored revision mismatch ------------> 409 REVISION_CONFLICT
  +-- authority missing ----------------------> 503 AUTHORITY_UNAVAILABLE
  +-- valid authority context
        +-- illegal slot/option/cross-slot ---> 200 blocked + rule claims
        +-- legal
              +-- raw attrs/set/evidence -----> 200 resolved
              +-- standard profile
              |     +-- serializer blocked ---> profileReadiness blocked
              |     +-- executable -----------> profileReady
              +-- stat snapshot
                    +-- cache hit -------------> 200 verified
                    +-- cache miss ------------> 202 pending
                    +-- worker timeout --------> 503/unavailable + raw attrs retained
                    +-- runtime mismatch ------> new signature / no stale reuse

Community candidate
  +-- wrong season/stale/source invalid ------> rejected internal
  +-- resolver illegal ------------------------> rejected internal
  +-- legal -----------------------------------> eligible winner/standby
  +-- spec missing ----------------------------> degraded release, public spec empty
  +-- release binding mismatch ----------------> blocked; active unchanged
```

### 20.2 Planned Test Files

- `tests/gear_resolver_test.py`
- `tests/gear_release_test.py`
- extensions to `tests/postgres_cache_store_test.py`
- extensions to `tests/news_backend_test.py`
- `tests/gear-workbench-state.test.js`
- extensions to `tests/frontend-api-client.test.js`
- small page integration cases in `tests/builds-page.test.js`
- compatibility characterization in `tests/websim_payload_test.py`

New Resolver/Release/State modules target 100% behavioral branch coverage。大文件不追求虚假的 100% line coverage，但所有新增/迁移分支和 error path 必须有测试。

### 20.3 Mandatory Regressions

- PG-only forged client enhancement is rejected。
- Missing Authority Context never falls back to client options。
- Non-2xx Result Envelope body survives frontend transport。
- Old response serial cannot overwrite a newer Intent。
- Community sync does not mutate active before preflight。
- Provisional/illegal/stale templates cannot become public winners。
- Cache never crosses incompatible Dependency Vector。
- Catalyst allowlist alone cannot produce verified。
- Legacy `/gear/stats` remains backward-compatible during migration。

### 20.4 Real SimC Candidate Gate

对 40 个专精的 active community intent：

- 40 个都必须经过 current Resolver；
- 所有声称 `profileReadiness=ready` 的标准 profile 必须真实执行最小 executability probe；probe 只覆盖执行预算，不得替换 actor、talents、gear、preparation 或 APL facts；
- `stat_snapshot_v1` 必须另外证明可解析 verified JSON `buffed_stats`；允许同一次最小 SimC 进程同时提供两类证据，但证据声明必须分开；
- non-ready 必须有允许的明确 blocker，不能误报 ready；
- 不运行或比较 DPS；
- Resolver、Serializer、Gear Rule、Gear Release、Community Release 或 SimC Runtime 变化时触发完整矩阵；
- 纯 UI 改动且 backend contract 未变时可跳过真实 SimC 全矩阵。

## 21. Failure Modes 与恢复

| Failure | Public behavior | Recovery |
| --- | --- | --- |
| Manifest 缺失或混态 | 503 Authority unavailable，不使用旧组合 | 修复/回滚 active Manifest |
| Authority Context 缺字段 | Selection blocked，不相信客户端 | 重建 release 或补权威证据 |
| authored revision 过期 | 409，保留 Intent | 使用当前 revision 重新 Resolve |
| Resolver rule missing | blocked claim | 补 Rule Matrix/source，发布新 rule revision |
| Community candidate 无合法 winner | 该专精为空，release degraded | standby/re-election/daily refresh |
| Community candidate 系统性错误 | active 不变 | 修 candidate，重新 preflight |
| Gear Release 先激活 | community binding 置 null | 等兼容 community release 后再切 Manifest |
| LRU stale risk | signature 不匹配即 miss | 新 Dependency Vector 自然失效 |
| SimC worker down | raw attrs 可见，snapshot unavailable | systemd restart、lease reclaim |
| Queue saturated | 503 SimC unavailable，不伪造结果 | backpressure、限流、扩容前压测 |
| SimC runtime 更新 | 旧 stat signature 不复用 | 新 runtime signature 重新计算 |
| Client offline | last verified stale/read-only | 联网后重新 Resolve，不自动执行 SimC |
| Catalyst capability 未闭环 | conversion UI hidden | Capability Proof Matrix 全通过后启用 |
| Candidate deploy failure | 不合入、不切 pointer | code/config rollback，保留 active release |

## 22. Impact Map

### must_change

- Gear Instance Resolver 与 Rule Matrix；
- PostgreSQL Authority Context loader；
- `/resolve`、`/profile`、new stat snapshot API；
- frontend structured problem mode 与 workbench state；
- community candidate/preflight/release/pointer；
- Season Manifest 正式读；
- SimC stat execution 与 Worker；
- health/admin/timer/deploy smoke；
- tests、runbook、owner map 和 roadmap evidence。

### must_not_change

- 公共模板仍只来自真实玩家 observed source；
- baseline/recommended/system templates 不回流公共入口；
- PG-only runtime；
- 前端不拼 SimC profile；
- 个人模板 owner/auth isolation；
- 新闻、天赋和其他无关产品语义；
- async sync/backfill 默认不由 deploy 自动启动。

### risk_unknown

- 12.1 retained-secondary-stat 的正式字段与精确语义；
- 当前云机同时运行两个 stat snapshot SimC child 的 CPU/内存影响；
- 旧小程序 `/gear/stats` 调用版本分布；
- catalog 中 unique/gem/enchant authority 字段完整度。

### evidence_required

- Rule Matrix source coverage；
- PG query plans 与 perf probe；
- 40-spec Resolver/Serializer/SimC matrix；
- shadow release diff；
- candidate deploy identity/runtime parity；
- live health/API/systemd/log smoke；
- rollback Manifest 和旧客户端兼容证据。

## 23. 七阶段 Strangler Delivery

### Phase 0: Production safety corrections

- PG forged enhancement fail closed；
- Catalyst false-green fail closed；
- legacy stats 使用 lightweight mode + concurrency 1；
- 不改变旧客户端 response shape。

### Phase 1: Contracts and rule authority

- Dependency Vector/signatures；
- Rule Matrix；
- Result Envelope；
- Authority Context contract；
- characterization/red tests。

### Phase 2: Canonical Resolver

- `gear_resolver.py`；
- PG context loader；
- complete slot/whole-character pipeline；
- Evidence Ledger v1；
- old facade parity。

### Phase 3: Resolve/Profile and frontend workbench

- `/gear/resolve`；
- `/profile` reuse；
- structured-problem client；
- pure frontend state；
- remove frontend final-fact inference；
- candidate deploy before cutover。

### Phase 4: Release train and community migration

- immutable Release Registry；
- Active Season Manifest；
- candidate/standby/per-spec election；
- `legacy-import-r0`；
- shadow compare；
- atomic cutover；
- scheduled refresh。

### Phase 5: Async SimC snapshot

- PG job/store；
- systemd Worker；
- new endpoint；
- single-flight/lease/recovery/health；
- frontend cutover；
- legacy telemetry and later retirement。

### Phase 6: 12.1 Catalyst capability

外部规则与 SimC 支持成熟后才开始；完成 Resolver/Serializer/Evidence/real fixture proof 后开放 UI。

每个 runtime PR：

- 最多两个新内部边界；
- 约 8 files 为 review smell threshold；
- red/characterization first；
- local CR；
- targeted + profile verification；
- candidate deployment before merge；
- active timers/backflow/log/runtime parity smoke；
- explicit rollback evidence。

## 24. What Is Not In Scope

- 装备 DPS 比较。
- 自动生成最佳装备。
- 系统 BiS 或 optimizer。
- 战斗场景推荐。
- 把动态套装效果换算成伪 DPS/静态属性。
- 前端 SimC profile assembly。
- 用 SimC 替代所有装备规则权威。
- 微服务、事件总线、事件溯源、Redis 或 Celery。
- 通用规则 DSL。
- 完整任意 Claim DAG。
- 立即退役旧 `/gear/stats`。
- 在正式 12.1 规则和 runtime support 不足时实现 Catalyst 保留绿字转换。
- 重写无关 PG sync/write/backfill、新闻、天赋或个人资产链路。

## 25. Deferred Work

根目录 `TODOS.md` 已记录：

1. 12.1 Catalyst retained-secondary-stat overlay activation。
2. 新客户端完成迁移后退役 legacy synchronous gear-stats endpoint。

## 26. Acceptance Evidence

设计进入实施前：

- 用户书面复核本设计；
- 根据本设计生成分阶段 implementation plan；
- 为当前 Phase 建立 Harness requirement/evidence packet；
- 更新 owner maps 与 verification profile 影响范围；
- 明确 candidate deploy 和 rollback 命令。

每阶段完成时：

- 需求合同和 Impact Map 已满足；
- 测试覆盖新增/迁移行为与 failure paths；
- diff 没有跨越本阶段非目标；
- candidate runtime identity 明确；
- health/API/PG/UI/systemd/log smoke 与 rollback evidence 已归档；
- roadmap、runbook、owner map 和 project state 按实际证据更新；
- 不以测试通过或 HTTP 200 单独声明 live verified。

## 27. Review Record

本设计经过：

- 逐项产品对齐；
- Architecture Review；
- Code Quality Review；
- Test Review 与独立 QA test-plan artifact；
- Performance Review；
- 独立反方审查。

独立 Codex CLI 因本机 CLI/model compatibility 未产生结果；按 review fallback 使用全新上下文只读审查，提出五个 blocker。它们已分别通过以下设计修正关闭：

1. Dependency Vector 与三层签名；
2. Active Season Manifest 原子组合；
3. Shadow Community Release migration；
4. Structured Problem transport；
5. Legacy/new SimC endpoint compatibility sequence。

其余 concerns 通过 Rule Matrix、per-spec degraded release、Catalyst proof matrix、typed shallow Evidence Ledger、bounded query budget 和七阶段 delivery 处理。

### GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
| --- | --- | --- | ---: | --- | --- |
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | skipped | User chose direct engineering review; no CEO expansion requested |
| Codex Review | independent outside voice | Structural challenge | 1 | issues resolved in design | 5 blockers, 5 concerns, 3 simplifications |
| Eng Review | `/plan-eng-review` | Architecture, code, tests, performance | 1 | design decisions approved | Architecture, rule, release, API, test and performance contracts locked |
| Design Review | `/plan-design-review` | Visual design | 0 | not applicable | This document defines capability architecture, not a new visual delivery contract |

## 28. Final Design Status

所有关键产品和工程决策均已确认，书面规格已由用户批准。当前没有未决实现语义；只有外部依赖型 deferred work。下一步是在新 Session 中创建持续 Goal，按 phase 分别使用 `superpowers:writing-plans` 生成可执行计划，并以 `superpowers:executing-plans` 在没有真实阻塞或待决策项时持续推进。Phase 6 的 12.1 Catalyst 外部依赖不属于当前 Goal 的完成条件。
