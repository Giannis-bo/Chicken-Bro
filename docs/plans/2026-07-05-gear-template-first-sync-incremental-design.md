# 社区装备模板首次增量采集方案

> 日期：2026-07-05
> 状态：方案草案，待拆实施计划
> 范围：社区装备模板、首次同步、增量续跑、SimC variant probe、Raider.IO observed gear、health/admin 验收。

## 背景

社区天赋模板补齐 80 个槽位后，采集路径已经从“全局高分榜反复全量”演进为“目标矩阵 + 缺口队列 + 证据排序”。装备模板也需要同样的思路，但装备的目标不是 hero 槽位，而是每个职业专精的一套 16 个 canonical 装备槽，以及每件装备背后的 variant / gem / enchant / crafted stats / SimC 可执行字段。

装备模板和天赋模板的展示模型不同：天赋模板需要每个专精同时展示 2 个英雄天赋槽位；装备模板只按 `class/spec` 选出 1 个最优真实社区角色装备模板，不强制关联或区分英雄天赋。同时，小程序端还要为“基线装备”保留 1 个独立位置。也就是说，邪 DK 的装备页不需要拆成天启邪装备和萨莱茵邪装备，而是展示“邪 DK 最优社区装备模板”以及“邪 DK 基线装备”。

当前装备链路已有基础：

- `/api/websim/gear` 已输出 `communityTemplates`。
- PG-only 运行时已经写入 `cache.websim_community_gear_templates`、`cache.websim_items`、`cache.websim_gear_sources`、`cache.websim_gear_variants`。
- observed gear backfill 已有 cursor/state 思路，可独立补 Raider.IO 观测装备变体。
- `build_community_gear_templates` 当前主要从 `cache.websim_profile_presets` 派生模板，还缺少面向 40 个专精、16 个槽位和 variant 缺口的 target queue。

因此，装备模板首次同步不应该走“全量 catalog + 全量 profile + 全量 SimC probe + 全量模板重建，失败后再重跑”的模式。首轮也应该从第一分钟就可恢复、可跳过已完成目标、可解释缺口。

## 目标

- 首次同步就按 target queue 运行，避免反复全量同步。
- 为 40 个专精构建真实社区装备模板覆盖，每个 spec 最多晋级 1 个真实社区 best winner，每个模板必须能表达 16 个 canonical 槽位的完整性。
- 为每个 spec 预留 1 个 baseline gear 槽位；baseline 不计入真实社区覆盖，也不参与社区 best winner 竞争。
- 将“采集真实玩家装备样本”和“验证装备实例属性可执行”拆开，Raider.IO/WCL 只做观测证据，生产装备属性仍来自 SimC JSON gear output 或 Battle.net Game Data。
- 对每个 spec、slot、variant 输出当前状态、阻断原因、下一步动作和续跑 cursor。
- 保留旧 complete winner：新数据如果只是 partial、stale 或缺 variant evidence，不能覆盖当前可用模板。
- 让 `/api/data/health` 和 `/admin/gates` 能回答：哪些专精完整、哪些槽缺样本、哪些 variant 缺 SimC 证明、下一轮只需要补什么。

## 非目标

- 不把 `default_template` 包装成真实社区样本。
- 不宣称“绝对 BiS”或“权威毕业装备”。首版语义应是“证据排序推荐装备模板”。
- 不直接用 Raider.IO/WCL profile API 的装备属性作为生产属性。
- 不像天赋模板一样按 hero 拆装备模板槽位；hero 只可作为来源角色的上下文证据，不作为装备模板 target key 或展示分组。
- 不因单件装等更高自动替换整套模板。
- 不让 partial / source_reference / stale / wrong-season / fallback 数据进入可执行 SimC 模板。
- 不在读接口中补造缺失 variant；补齐必须发生在同步、回填或审计任务中。

## 目标矩阵

装备首轮同步拆成三层目标，而不是一个全量任务。对外展示再收敛为每个 spec 的两个位置：1 个 community best，1 个 baseline。

### Public Display Slots

小程序端按 `class/spec` 展示装备模板，不按 hero 展示。

每个 spec 目标展示位：

- `community_best`: 最优真实社区角色装备模板，来源可以是 Raider.IO observed profile，后续可被 WCL evidence 加权；最多 1 条 active winner。
- `baseline`: 基线装备模板，现有实现可继续使用 `sourceKey=default_template` 或后续重命名为 `baseline_template`；该槽位不算真实社区覆盖，不冒充玩家样本，不参与 community best 排名。

当 `community_best` 还没有完整真实样本时，该位置应显示 `pending_collection` 或 `blocked` 语义；baseline 若可用，仍只能表达“基线起点”，不能替代真实社区模板。

### Spec Template Target

每个职业专精至少一个目标：

```text
gear-template:<classKey>:<specKey>:<templateSlot>:<scenarioKey>
```

`templateSlot` 首版固定为：

- `community_best`
- `baseline`

内部 candidate 仍保留真实 `sourceKey`，例如：

- `raiderio_observed_profile`
- `simc_preset`
- `default_template` / `baseline_template`

目标状态：

- `complete`: 16 个 canonical 槽位都有 SimC-ready 装备行，且 serializer 可执行。
- `partial`: 有真实装备样本，但缺一个或多个 canonical 槽位或 variant 证明。
- `pending_collection`: 还没有足够真实玩家样本。
- `blocked`: 有样本但被确定性门禁阻断，例如 class/spec 不匹配、variant 无法解析、slot 不兼容、SimC probe 失败。
- `stale`: 当前 winner 或关键 variant 已过新鲜度窗口。

### Slot Target

每个 spec 有 16 个 canonical slot 目标：

```text
gear-slot:<classKey>:<specKey>:<slot>
```

Slot target 用于查漏补缺。首轮同步如果一个 spec 已经有 13/16 槽，不应重跑整套 profile 扫描，而是只把缺失槽位加入高优先级队列。

### Variant Target

每个待验证装备实例变体有独立目标：

```text
gear-variant:<itemId>:<slot>:<itemLevel>:<optionDigest>
```

`optionDigest` 来自 normalized SimC gear line 的关键字段，例如：

- `bonus_id`
- `gem_id`
- `gem_bonus_id`
- `gem_ilevel`
- `enchant_id`
- `crafted_stats`
- `crafting_quality`
- `drop_level`
- `suffix`
- `titan_disc_id`

同一 variant target 已 probe 成功后，后续模板装配只能复用结果，不应再次消耗 SimC 预算。

## 首次同步流程

### Phase 0：只读预检

输入：

- 当前 PG gear catalog。
- 当前 `websim_community_gear_templates`。
- 当前 `websim_profile_presets`。
- 当前 observed gear sources / variants。
- 当前 stat weight / mod option readiness。
- 当前 `/api/data/health` 的 gear 与 community template 状态。

输出：

- 40 个 `community_best` spec template target。
- 40 个 `baseline` spec template target。
- 640 个 spec-slot target。
- 已有 complete winner 列表。
- partial template 缺口。
- missing / partial / stale variant target。
- 本轮首次同步预算建议。

预检不得访问外部 API，不写库，只生成计划和摘要。

### Phase 1：队列初始化

按优先级生成首轮队列：

1. 没有 complete `community_best` 装备模板的 spec。
2. 已有 partial 模板但缺槽少的 spec。
3. 已有完整 16 槽但 variant evidence stale 的 spec。
4. 只有 baseline / `default_template` 的 spec。
5. 已有 complete 且新鲜的 spec 只进入低优先级巡检。

队列字段建议：

- `targetKey`
- `targetType`
- `status`
- `priority`
- `currentWinnerId`
- `currentWinnerSignature`
- `missingSlots`
- `pendingVariantCount`
- `cursor`
- `budget`
- `stopReason`
- `nextAction`

### Phase 2：Raider.IO observed profile 采集

Raider.IO 负责发现真实玩家装备样本，但不负责证明装备属性。

采集策略：

- 按 `class/spec` 拉对应高分段角色池，不从全局 Top 自然覆盖开始，也不按 hero 强制拆池。
- 优先消费已有 Raider.IO cache 和已知 target profile。
- 只对 `pending_collection`、缺 slot 或 stale 的 spec 扩大 page/region/profile 窗口。
- 每个 profile 写入 normalized observed evidence，至少保留 region、realm、character、profile URL、run source、checkedAt、class/spec、itemId、slot、itemLevel 和观测到的 option 字段。
- 如果 profile 当前专精污染、slot 不兼容或样本字段不足，只写 reject reason 或 blocker，不晋级模板。

关键约束：

- Raider.IO 观测到的是玩家装备配置，不是生产属性来源。
- observed profile 可以产生 candidate 和 source refs，不能绕过 SimC-ready variant gate。
- 不为填满 16 槽跨职业、跨专精或跨 slot 借装备。
- 来源角色的英雄天赋可保留为 evidence context，但不能要求同一 spec 产出多个 hero 装备 winner。

### Phase 3：SimC Variant Probe

只有新发现、缺失、partial 或 stale 的 variant 进入 probe。

Probe 输入：

- normalized gear line。
- class/spec/race/scenario 的最小可执行上下文。
- itemId、slot、itemLevel、optionDigest。

Probe 输出：

- `verified`: SimC JSON gear output 可解析，且字段与目标 variant 匹配。
- `partial`: 有部分字段，但缺关键 option 或存在 warning。
- `blocked`: SimC resolution failure、slot mismatch、unsupported option、item not found、wrong season 等。
- `cached`: 与既有 normalized gear-line signature 完全一致，复用缓存。

预算策略：

- 首轮每个 spec 有固定 probe 上限，优先缺槽与当前 winner 所需 variant。
- 同一 `gear-variant` 成功后全局复用。
- 连续失败的 variant 写入 reject cache 和 TTL，后续只在 SimC build、season revision 或 source evidence 改变时重试。

### Phase 4：模板装配

模板装配只读取已经验证的 candidate items 和 variant 结果。

硬门禁：

- class/spec 匹配。
- 16 个 canonical slot 完整。
- 每个 item 有 canonical slot、itemId 和 SimC-ready option。
- 所有必要 variant stat evidence 为 verified。
- serializer 能生成 16 行 canonical gear raw string。
- gem / enchant / crafted stats 不使用假 seed，不把缺失字段补造成真实值。
- `source_reference`、partial、blocked、wrong-season、fallback 不进入 complete 模板。

装配输出：

- `rawString`
- `gearItems`
- `readySlotCount`
- `missingSlots`
- `templateEvidence`
- `sourceRefs`
- `inputDigest`
- `variantDigest`
- `qualityScore`
- `promotionReason`

### Phase 5：晋级与发布

同一 `class/spec/templateSlot/scenario` 内只允许一个 active winner；其中 `community_best` 只能有 1 个真实社区 winner，`baseline` 只能有 1 个基线 winner。二者独立展示、独立审计、独立计数。

晋级顺序：

1. complete 优于 partial。
2. 16 槽完整且所有 variant verified。
3. 真实 observed evidence 数量更多。
4. 来源更新且未过期。
5. role/spec 兼容性更明确。
6. normalized quality score 更高。
7. 稳定 id tie-breaker。

自动替换限制：

- community best winner 不被 baseline 覆盖，baseline 也不参与 community best 排名。
- complete winner 不被 partial candidate 覆盖。
- WCL/高质量 evidence 支撑的 winner 不被普通 Raider.IO-only 小幅变化覆盖。
- 单件装等提升不触发整套替换，除非整套模板仍完整且通过所有 hard gate。
- 新模板只在质量明显提升、旧 winner stale/blocked，或当前没有 complete winner 时晋级。
- 不确定的变化进入 `candidate_only` 或 `needs_review`。

## 增量状态模型

首版可以继续使用 PG sync state JSON；当 admin 需要高频过滤和对账时，再拆正式表。

### Gear Template Target State

```json
{
  "schemaVersion": 1,
  "targetKey": "gear-template:mage:frost:community_best:mplus_mixed_route",
  "targetType": "gear_template",
  "templateSlot": "community_best",
  "status": "partial",
  "currentWinnerId": "observed-profile-mage-frost",
  "currentWinnerSignature": "sha256:...",
  "inputDigest": "sha256:...",
  "variantDigest": "sha256:...",
  "readySlotCount": 13,
  "missingSlots": ["neck", "finger2", "trinket2"],
  "pendingVariantCount": 4,
  "cursor": {
    "provider": "raiderio",
    "region": "cn",
    "page": 1,
    "profileOffset": 40,
    "lastProfileId": "..."
  },
  "budget": {
    "profileLimit": 40,
    "variantProbeLimit": 24
  },
  "stopReason": "variant_probe_budget_exhausted",
  "nextAction": "probe_missing_variants"
}
```

### Gear Variant Probe State

```json
{
  "targetKey": "gear-variant:12345:finger1:684:sha256...",
  "status": "blocked",
  "lastProbeSignature": "sha256...",
  "lastProbeAt": "2026-07-05T00:00:00Z",
  "simcBuild": "16b061b2d928",
  "seasonRevision": "midnight-s1",
  "failureCount": 2,
  "blocker": {
    "stage": "simc_variant_probe",
    "reason": "simc_resolution_warning",
    "detail": "missing enchant_id"
  },
  "retryAfter": "2026-07-08T00:00:00Z"
}
```

### Candidate Ledger

候选先进入 ledger，不直接发布。

建议状态：

- `candidate`
- `promoted`
- `candidate_only`
- `needs_review`
- `rejected_regression`
- `rejected_blocked`
- `expired`

记录字段：

- `candidateId`
- `targetKey`
- `sourceKey`
- `sourceUrl`
- `signature`
- `inputDigest`
- `variantDigest`
- `status`
- `readySlotCount`
- `missingSlots`
- `qualityScore`
- `hardGateStatus`
- `promotionReason`
- `rejectionReason`
- `firstSeenAt`
- `lastSeenAt`

## 如何避免首轮反复全量

### Digest 跳过

每个 spec template 计算三个 digest：

- `sourceDigest`: 参与装配的 profile preset / observed source refs。
- `variantDigest`: 16 槽 candidate 的 variant signatures。
- `outputDigest`: 最终 rawString + enhancement snapshot。

如果 `sourceDigest` 和 `variantDigest` 都没变，首轮续跑也不重建模板，只刷新 progress。

### 已完成目标跳过

首轮任务被中断后，下一次从 PG sync state 读取：

- complete 且新鲜的 spec 不进入高优先级队列。
- 已 probe 成功的 variant 不再 probe。
- 已知 blocked 且 TTL 未过的 variant 不再重复 probe。
- 已知 rejected profile 不再重复拉取，除非 checkedAt 过期或 profile signature 改变。

### 缺口优先

首轮每个批次都按缺口排序：

1. `readySlotCount=15` 且只缺 1 槽。
2. 缺 slot 但已有足够 observed evidence。
3. variant probe pending 多于 source pending 的 spec。
4. 完全没有 observed profile 的 spec。
5. 已有 complete 的 freshness 巡检。

这样可以先快速把大量接近 complete 的 spec 推上来，而不是平均扫完所有 class/spec/page。

### 分层预算

首轮同步不再只有一个总预算，而是分层预算：

- profile discovery budget
- source normalization budget
- variant probe budget
- template assembly budget
- admin/health reporting budget

每层耗尽时写 `stopReason`，下一轮只恢复该层之后的工作。

## Health 与 Admin 展示

`/api/data/health` 建议增加：

- `gearTemplates.totalSpecCount`
- `gearTemplates.completeSpecCount`
- `gearTemplates.partialSpecCount`
- `gearTemplates.pendingCollectionSpecCount`
- `gearTemplates.blockedSpecCount`
- `gearTemplates.realCommunityCoveredSpecCount`
- `gearTemplates.defaultOnlySpecCount`
- `gearTemplates.missingSlotCount`
- `gearTemplates.pendingVariantProbeCount`
- `gearTemplates.cachedProbeHitCount`
- `gearTemplates.rejectedRegressionCount`
- `gearTemplates.lastRunMode`
- `gearTemplates.lastRunStopReason`
- `gearTemplates.nextAction`

`/admin/gates` 的 `gear_templates` domain 建议按 spec 展开：

- active winner。
- 当前 source。
- 16 槽覆盖矩阵。
- 每个缺 slot 的候选数量。
- 每个 blocked variant 的 stage/reason。
- last cursor。
- last promotion / rejection。
- next action。

owner 首屏应能看到：

- 哪些 spec 只有 default，不算真实社区覆盖。
- 哪些 spec 的 `community_best` 缺失，但 `baseline` 可用。
- 哪些 spec 缺样本。
- 哪些 spec 有样本但缺 SimC variant 证明。
- 哪些 spec 已 complete 但 stale。
- 哪些 candidate 被拒绝，拒绝是回退还是证据不足。

## Run Modes

### `gear_template_preflight`

只读模式。生成目标队列、缺口矩阵、预算建议，不访问外部 API，不写库。

### `gear_template_first_sync`

首次同步模式。允许较大预算，但仍按 target queue 断点续跑。

建议默认：

- 每批处理有限 spec 数。
- 每 spec 有 profile/profile-page 上限。
- variant probe 有全局 CPU 上限。
- 每批结束写 progress report。

### `gear_template_targeted_refresh`

日常补缺模式。只处理：

- pending collection。
- stale winner。
- partial template。
- missing slot。
- stale/blocked 但 TTL 到期的 variant。

### `gear_template_full_rebuild`

显式全量重建，只用于：

- 赛季切换。
- SimC build 变化。
- gear catalog schema/revision 变化。
- slot/serializer 规则变化。
- 生产事故后 owner 明确要求重建。

## 验收标准

首轮实现后至少满足：

- 首次同步可中断、可恢复，第二次不会重跑已完成 spec 和已 verified variant。
- 40 个 spec 的展示槽位矩阵完整：`community_best` 与 `baseline` 分开计数，complete / partial / pending_collection / blocked / default_only 都有明确语义。
- 任何 real community gear 覆盖都不能由 `default_template` 填平。
- 装备模板不按 hero 拆槽；选择邪 DK 时只展示 1 个邪 DK community best 装备模板和 1 个 baseline 预留位。
- complete 模板必须是 16 个 canonical slot。
- partial candidate 不能覆盖 complete winner。
- Raider.IO/WCL profile API 属性不能作为生产属性写入 verified variant。
- SimC probe 缓存能避免同一 normalized gear line 反复计算。
- `/api/websim/gear` 能继续只读返回 schema，不触发补齐写入。
- `/api/data/health` 和 `/admin/gates` 能展示 missing slots、pending variants、blocked reasons 和 next action。
- 文档、run summary 和 admin records 能解释每个未 complete spec 为什么还没有补齐。

## 实施拆分建议

1. 补只读 preflight：输出 40 spec 的 `community_best` / `baseline` 展示槽位、640 slot 和 variant 缺口矩阵。
2. 把 observed backfill cursor 升级为 spec/slot target queue。
3. 增加 variant probe cache 和 TTL reject cache。
4. 增加 gear template candidate ledger 和 winner history。
5. 改造 `build_community_gear_templates`：从全量 preset 派生改为 digest + target 驱动。
6. 增强 health/admin `gear_templates` 视图。
7. 加自动验收脚本：40 spec coverage、default-only 隔离、complete winner 保护、variant probe 去重、read endpoint no-write。

## 风险与待决策

- 首轮每个 spec 允许采多少 Raider.IO profile 才标记为 `pending_collection`。
- SimC variant probe 的每日 CPU 预算和超时上限。
- 是否需要 WCL gear evidence 作为装备模板排序加权，首版可先只记录 `wcl_missing`。
- “最优”是否只做 M+ mixed route，还是区分 raid / single target / aoe pack。
- 坦克和治疗的 `qualityScore` 不能复用纯 DPS 排序，需要角色专属指标。
- default template 是否继续作为可导入起点展示，还是在真实社区装备覆盖完成前只作为诊断兜底。

## 阶段 1 本地实施计划

> 更新时间：2026-07-05 00:30 CST
> 状态：正在推进。第一步先补齐只读 preflight / health 表达，再进入线上全量采集与 sync 证据记录。

### Step 1：只读 preflight 与 health 对账

- 目标：`sync_community_template_cache_postgres()` 每次写入 `community_template_sync_latest` 时，同时输出 `gear.preflight`。
- 输出口径：
  - `40 spec x community_best`：只统计真实社区来源，`default_template` / `baseline_template` / `simc_preset` 不得填平。
  - `40 spec x baseline`：单独统计 baseline 展示位可用 / blocked，不参与 community best 排名。
  - `40 x 16 canonical slots`：只针对 `community_best` 输出 ready / missing slot matrix。
  - `targetQueue`：输出 `gear-template:*` 与 `gear-slot:*` 下一步目标，供首轮续跑和 admin 对账使用。
- 已完成本地代码：
  - `server/postgres_cache_sync.py` 新增 `community-gear-template-preflight-v1` builder。
  - `server/postgres_cache_store.py` 新增 PG 持久化模板覆盖读取方法。
  - `server/news_backend.py` 在 `/api/data/health` 的 `community_templates.details` 透出 `gearTemplatePreflight` 与 `baselineGearTemplates`。
- 本地测试：
  - `python -m unittest tests.postgres_cache_sync_test tests.postgres_cache_store_test tests.news_backend_test`
  - 结果：`Ran 269 tests in 129.487s - OK`。

### Step 2：线上 Phase 1 首轮采集

- 部署前：
  - 本地 CR 检查 diff 是否只改变 preflight / health / tests / docs。
  - 使用现有脚本部署，保持 `WOW_DEPLOY_SKIP_BOOTSTRAP=1 WOW_DEPLOY_START_ASYNC_SYNCS=0 ./server/deploy_lighthouse.sh`。
  - 部署前备份 PostgreSQL，记录 backup path 与 size。
- 线上执行：
  - 启动一次 `wow-community-template-sync.service` 或等价 transient service。
  - 如需要，先跑 `wow-gear-observed-backfill` 以刷新 Raider.IO observed evidence；Raider.IO 只作为 observed evidence。
  - 记录 syncRunId / runId、systemd start/end timestamp、wall time、CPU time、Result、ExecMainStatus。
- 线上验收：
  - `/health`
  - `/api/data/health`
  - `/admin/gates`（使用 GET）
  - `/api/websim/talents` 全 40 spec / 80 hero slots。
  - `/api/websim/gear` 全 40 spec，确认每个 spec 有 community_best 状态和 baseline 状态，community_best complete 或明确 pending/blocker。
  - 核对 `gearTemplatePreflight.canonicalSlotMatrix.totalSlotCount = 640`，并记录 missing slot 汇总。

### Step 3：Phase 1 验收门禁

- 通过条件：
  - 40 个 spec 的 `community_best` 均为 complete，或每个未 complete spec 都有明确 pending/blocker、missingSlots、nextAction。
  - 40 个 spec 的 baseline display slot 均 available 或有明确 blocked 根因。
  - complete community gear template 必须有 16 canonical slots。
  - 没有 `source_reference` / `partial` / `stale` / `wrong-season` / `fallback` / `default_template` 冒充真实社区 complete。
  - 没有按 hero 强拆装备 winner。
- 若 Phase 1 未通过：只记录 blocker 和 nextAction，不进入 Phase 2 日常增量上线。

### Step 4：Phase 2 日常增量

- 仅在 Phase 1 验收通过后实施。
- 目标模式：
  - 天赋：`daily_light` / `daily_targeted` / `weekly_deep` / `season_reset_full`。
  - 装备：只处理 pending / stale / blocked / missing slot / stale variant，不默认全量。
  - change report 区分 `unchanged` / `metadata_refreshed` / `promoted` / `candidate_only` / `needs_review` / `rejected_regression` / `blocked` / `stale_winner`。
## 2026-07-05 Phase 1 implementation/deploy status

Status: Phase 1 is blocked, not accepted. Phase 2 daily incremental refresh has not started.

Implemented in this slice:

- Added `community-gear-template-preflight-v1` to the Postgres community-template sync payload.
- Health now exposes `gearTemplatePreflight`, `realCommunityGearTemplates`, and `baselineGearTemplates`.
- Public gear read models now split real `community_best` from baseline templates:
  - `communityTemplates`: one real/pending community slot per spec.
  - `baselineTemplates`: `simc_preset` / `default_template` display candidates.
  - Baseline/default rows no longer count as real community coverage.

Verification:

- `python -m unittest tests.postgres_cache_sync_test tests.postgres_cache_store_test tests.news_backend_test tests.websim_payload_test`
- Result: `Ran 616 tests in 241.895s - OK`.
- `python -m compileall server/postgres_cache_sync.py server/postgres_cache_store.py server/news_backend.py server/websim_payload.py` exited 0.
- `git diff --check` exited 0 with only CRLF replacement warnings.

Deployment and live evidence:

- Backup: `/opt/wow-mini-program/backups/community-gear-preflight-before-20260704T163953Z/wow_test.dump`, `9542055` bytes.
- Final backend restart: `Sun 2026-07-05 01:10:31 CST`, active/running, `ExecMainStatus=0`.
- Preflight sync run: `pg-community-template-2026-07-04T164047z0000`.
- Talent coverage: `80 total / 80 verified / 0 partial / 0 blocked`.
- Gear preflight: `40 specs`, `80 display slots`, `640 canonical slot checks`.
- `community_best`: `0 complete / 26 partial / 14 pending / 0 blocked`.
- `baseline`: `32 available / 8 blocked`.
- Slot matrix: `162 ready / 478 missing`.
- `targetQueueCount`: `526`.

Blockers:

- Scheduled full/deep sync failed with `Result=oom-kill`, `ExecMainStatus=137`, memory peak `3.0G`, swap peak `241.4M`.
- Real community gear completion is `0/40`, so Phase 1 cannot be accepted.
- All-spec live gear endpoint sweep was not accepted as a pass gate in this turn: sequential sweep stalled on slow gear responses, and a curl-based sweep hit Windows GBK decoding errors. A representative live sample verified the PG route split: sampled `/api/websim/gear?compact=1` specs returned one community slot, with `simc_preset` only under `baselineTemplates`.

Next action:

- Split first-sync into bounded target-queue batches.
- Reduce Raider.IO/profile/run-detail budgets before another deep run.
- Continue observed gear plus SimC/Battle.net variant evidence backfill until every `community_best` slot is complete or has a stable blocker/next action.
- Keep Phase 2 gated until Phase 1 acceptance passes.

## 2026-07-05 bounded first-sync implementation/deploy status

Status: Phase 1 is still blocked, not accepted. Phase 2 daily incremental talent/gear refresh has not started.

Implemented in this slice:

- Added `gear_template_first_sync` / `gear_template_targeted_refresh` mode handling to the PostgreSQL community-template sync.
- `gear_template_first_sync` is gear-only for template writes: existing verified talent rows are read for coverage but are not rewritten.
- Added bounded Raider.IO collection for gear first-sync: run pages `0`, run-detail limits `0`, target specs from the gear preflight queue, and capped profile/backfill budgets.
- Wired observed gear backfill into the sync pipeline and payload as `gear.observedBackfill`.
- Updated `gear_observed_backfill.py` so PostgreSQL runtime honors `--target-limit`, `--profile-limit`, `--timeout-seconds`, `--simc-stats`, and `--full-profile-gear`.
- Community gear completion remains fail-closed: observed Raider.IO profile attributes are not trusted as complete gear unless backed by SimulationCraft stat evidence.

Verification:

- Focused tests: `Ran 5 tests in 0.073s - OK`.
- Sync/store tests: `Ran 60 tests in 0.094s - OK`.
- Four-module regression suite: `Ran 619 tests in 272.082s - OK`.
- `compileall` for the touched server modules exited 0.
- `git diff --check` exited 0 with only CRLF replacement warnings.

Deployment and backup:

- Deployed `server/postgres_cache_sync.py`, `server/postgres_cache_store.py`, and `server/gear_observed_backfill.py` by narrow `scp` plus remote `install`.
- Backend restart after deploy: `Sun 2026-07-05 01:30:01 CST`, active/running, `ExecMainStatus=0`.
- Valid PostgreSQL backup before bounded gear first-sync runs: `/opt/wow-mini-program/backups/community-gear-first-sync-before-20260704T173051Z/wow_test.dump`, size `9560573` bytes.

Live bounded sync evidence:

- First transient run `wow-community-template-sync-gear-first-0131.service`: success, runtime `1min 9.582s`, CPU `4.311s`, `ExecMainStatus=0`.
- First run observed backfill: `targetLimit=320`, `profileLimit=80`, `processedProfileCount=21`, `variantCount=86`, `stopReason=target_limit_reached`.
- Broader transient run `wow-community-template-sync-gear-first-0139.service`: success, runtime `4min 2.623s`, CPU `11.254s`, `ExecMainStatus=0`.
- Final `syncRunId`: `pg-community-template-2026-07-04T174214z0000`.
- Broader run observed backfill: `targetLimit=2000`, `profileLimit=240`, `processedProfileCount=125`, `variantCount=360`, `stopReason=target_limit_reached`.

Final live coverage:

- `/health`: HTTP 200.
- `/admin/gates`: HTTP 200 via GET.
- Authenticated `/api/admin/gates/summary`: HTTP 200, `overallStatus=partial`, `queueSummary.count=1707`, `gear_templates=55`.
- Top admin blockers include `missing SimulationCraft item stats`, `missing deterministic SimC variant preset`, and `SimC JSON did not include target item stats`.
- `/api/data/health`: `overallStatus=partial`, `community_templates.status=partial`.
- Talent coverage: `80 hero slots / 80 verified / 0 pending_collection / 0 blocked`.
- Gear coverage: `40 specs`, `80 display slots`, `640 canonical slot checks`.
- Final `community_best`: `0 complete / 36 partial / 4 pending / 0 blocked`.
- Final `baseline`: `32 available / 8 blocked`.
- Final canonical slot matrix: `640 total / 158 ready / 482 missing`.
- Final `targetQueueCount`: `530`.
- Public `/api/websim/talents` all-spec sweep: `40 specs`, `80 templates`, `80 verified`, `0 pending`, `0 blocked`.
- Public `/api/websim/gear?compact=1` all-spec sweep at lower concurrency: `40 specs`, `40 community slots`, `32 baseline slots`, `0 complete / 36 partial / 4 pending / 0 blocked`, with no default/baseline/simc-preset leakage into `communityTemplates`.

Blocker and next action:

- Phase 1 cannot be accepted because real community gear completion is still `0/40`.
- The bounded path avoids the previous scheduled deep-sync OOM and improves coverage from `26 partial / 14 pending` to `36 partial / 4 pending`.
- Remaining completion is blocked by missing trusted SimulationCraft/Battle.net variant evidence, not by Raider.IO profile discovery alone.
- Next implementation work must add a PostgreSQL-native SimC variant probe/cache or Battle.net-backed item-instance proof path for observed variants.
- Do not relax the complete gate to use Raider.IO/WCL profile API attributes as production gear attributes.
- Keep Phase 2 gated until Phase 1 acceptance passes.

## 2026-07-05 blocked baseline display-slot read-model status

Status: Phase 1 is improved but still not accepted. Phase 2 daily incremental talent/gear refresh has not started.

Implemented in this slice:

- Added a `baseline_blocked` read-model placeholder for specs with no baseline template.
- The placeholder is only a baseline display slot: `status=blocked`, `sourceStatus=blocked`, `canApplyGear=false`, `readySlotCount=0`, all `16` canonical slots missing, and compact-safe top-level `blockers` / `nextAction`.
- The PG and legacy gear read models add it only when baseline selection finds no real baseline candidate. It is not written to PostgreSQL and does not count as real community gear.

Verification:

- Focused RED/GREEN test: `tests.postgres_cache_store_test.PostgresCacheStoreTest.test_websim_gear_keeps_cached_read_model_when_pg_season_is_stale`.
- `python -m unittest tests.postgres_cache_store_test`: `Ran 39 tests in 0.055s - OK`.
- `python -m unittest tests.postgres_cache_sync_test`: `Ran 27 tests in 0.076s - OK`.
- `python -m unittest tests.websim_payload_test`: `Ran 348 tests in 125.181s - OK`.
- `python -m compileall server/postgres_cache_store.py server/websim_payload.py` exited 0.
- `git diff --check` exited 0 with only CRLF replacement warnings.

Deployment and live evidence:

- Hot deploy used `WOW_DEPLOY_SKIP_BOOTSTRAP=1` and `WOW_DEPLOY_START_ASYNC_SYNCS=0`; no sync/backfill run was started.
- Backend after deploy: `Sun 2026-07-05 03:21:05 CST`, active/running, `Result=success`, `ExecMainStatus=0`.
- Latest data sync remains `syncRunId=pg-community-template-2026-07-04T184617z0000`.
- Public `/api/websim/talents` all-spec sweep: `40 specs / 80 templates / 80 verified`.
- Public `/api/websim/gear?compact=1&mode=initial` all-spec sweep: `40 community slots / 40 baseline slots / bad=[]`.
- Gear `community_best`: `12 complete / 28 partial / 0 pending / 0 blocked`, `203` missing community slots.
- Gear baseline display slots: `18 complete / 14 partial / 8 blocked`, with `32 simc_preset` and `8 baseline_blocked` sources.
- Health/admin still correctly report source coverage as partial: real community gear `12 covered / 28 missing+partial`, baseline source templates `32 available / 8 blocked`, admin summary `overallStatus=partial`.

Blocker and next action:

- This closes the public baseline display-slot omission, but it does not complete Phase 1.
- Phase 1 remains blocked by `12/40` real community gear completion, `203` missing canonical community gear slots, and the `8` baseline source templates still needing real construction behind their blocked placeholders.
- Continue targeted variant proof and Battle.net item-instance proof before revisiting Phase 2.

## 2026-07-05 two-hand/ranged off-hand occupancy read-model status

Status: Phase 1 is improved but still not accepted. Phase 2 daily incremental talent/gear refresh has not started.

Implemented in this slice:

- Counted `off_hand` as occupied, not missing, when a SimC-ready `main_hand` proves it through concrete `weaponType` or through a mandatory spec equipment mode (`two_hand`, `two_hand_agi`, `ranged`).
- Kept hybrid/selectable and shield/off-hand specs fail-closed; they still require real off-hand evidence.
- Normalized persisted non-baseline community gear rows at read time so old `partial + missing off_hand` rows can become complete without a database write.
- Preserved persisted PostgreSQL template IDs and skipped baseline rows during this normalization.

Verification:

- Focused RED/GREEN builder test: `tests.websim_payload_test.WebSimPayloadTest.test_community_gear_template_counts_two_hand_main_hand_as_offhand_occupied`.
- Focused RED/GREEN PG read-model test: `tests.postgres_cache_store_test.PostgresCacheStoreTest.test_gear_read_model_counts_two_hand_main_hand_as_offhand_occupied`.
- `python -m unittest tests.websim_payload_test`: `Ran 349 tests in 102.662s - OK`.
- `python -m unittest tests.postgres_cache_store_test`: `Ran 40 tests in 0.059s - OK`.
- `python -m compileall server/websim_payload.py server/postgres_cache_store.py` exited 0.
- `git diff --check` exited 0 with only CRLF replacement warnings.

Deployment and live evidence:

- Hot deploy used `WOW_DEPLOY_SKIP_BOOTSTRAP=1` and `WOW_DEPLOY_START_ASYNC_SYNCS=0`; no sync/backfill run was started.
- Backend after deploy: `Sun 2026-07-05 03:53:11 CST`, active/running, `Result=success`, `ExecMainStatus=0`.
- Latest data sync remains `syncRunId=pg-community-template-2026-07-04T184617z0000`.
- `/health`, `/api/data/health`, and `/admin/gates` returned HTTP 200.
- Public `deathknight:blood` gear changed from `partial, ready=15, missing=off_hand` to `complete, ready=16, missing=[]`, with `occupiedSlots.off_hand.reason=spec_two_hand_main_hand` and no emitted `off_hand=` SimC line.
- Public `/api/websim/gear?compact=1&mode=initial` curl-based all-spec sweep: `40` specs checked, `bad=[]`, `errors=[]`.
- Gear `community_best`: `16 complete / 24 partial / 0 pending / 0 blocked`.
- Gear baseline display slots: `32 available / 8 blocked`.
- Gear canonical slot matrix: `640 total / 442 ready / 198 missing`.

Blocker and next action:

- This removes the false off-hand gap for mandatory two-hand/ranged specs, but it does not complete Phase 1.
- Remaining partial specs still need real evidence for missing slots; hybrid/off-hand specs remain fail-closed.
- Continue targeted variant proof and Battle.net item-instance proof before starting Phase 2.

## 2026-07-05 Battle.net weapon metadata off-hand occupancy status

Status: Phase 1 is improved but still not accepted. Phase 2 daily incremental talent/gear refresh has not started.

Implemented in this slice:

- Added PostgreSQL read-model enrichment from official `cache.websim_items` metadata before community gear slot coverage is recomputed.
- Required `_metadata.source = Battle.net Game Data API` before metadata can provide weapon proof.
- Backfilled three bounded official metadata rows: `193723=Staff`, `245770=Staff`, `258218=One-Handed Sword`.

Verification:

- Focused RED/GREEN PG metadata test: `tests.postgres_cache_store_test.PostgresCacheStoreTest.test_gear_read_model_uses_official_item_metadata_for_offhand_occupancy`.
- `python -m unittest tests.postgres_cache_store_test`: `Ran 41 tests in 0.071s - OK`.
- `python -m compileall server/postgres_cache_store.py` exited 0.
- `git diff --check` exited 0 with only CRLF replacement warnings.

Deployment and live evidence:

- Hot deploy used `WOW_DEPLOY_SKIP_BOOTSTRAP=1` and `WOW_DEPLOY_START_ASYNC_SYNCS=0`; no sync/backfill service was started.
- Backup before metadata writes: `/opt/wow-mini-program/backups/community-gear-offhand-metadata-before-20260704T201043Z/wow_test.dump`, `17063366` bytes.
- Final backend state after manual restart: `Sun 2026-07-05 04:18:17 CST`, active/running, `Result=success`, `ExecMainStatus=0`.
- `/health`, `/api/data/health`, and `/admin/gates` returned HTTP 200.
- Targeted smoke confirmed `druid:restoration`, `monk:brewmaster`, and `monk:windwalker` are now complete through official `Staff` metadata.
- Targeted smoke confirmed `warlock:destruction` stays partial because official `Skybreaker's Blade` metadata is `One-Handed Sword` and chest is still missing.
- Public `/api/websim/gear?compact=1&mode=initial` lower-concurrency all-spec sweep: `40` specs checked, `bad=[]`, `errors=[]`.
- Gear `community_best`: `19 complete / 21 partial / 0 pending / 0 blocked`.
- Gear baseline display slots: `32 available / 8 blocked`.
- Gear canonical slot matrix: `640 total / 445 ready / 195 missing`.

Blocker and next action:

- This removes three additional false off-hand gaps, but it does not complete Phase 1.
- Continue targeted slot evidence collection for the remaining `21` partial community specs and real baseline construction for the `8` blocked baseline specs.

## 2026-07-05 duplicate-slot and persisted slot-coverage reconciliation status

Status: Phase 1 is more consistent and fail-closed, but still not accepted. Phase 2 daily incremental talent/gear refresh has not started.

Implemented in this slice:

- Community gear coverage now assigns distinct equivalent-slot items into open canonical slots, covering real cases such as two observed trinkets both entering as `trinket1`.
- The duplicate assignment refuses to reuse the same item ID for both equivalent slots.
- Persisted community gear replacement now audits observed rows with the current slot-coverage model and official Battle.net item metadata before returning coverage counts.
- The audit can promote stale partial rows, demote stale complete rows, and keep real complete winners protected from weaker partial candidates.
- Baseline, `simc_preset`, `source_reference`, manual fixture, fallback, and stale rows still do not count as real community coverage.

Verification:

- Focused websim duplicate/off-hand tests: `Ran 2 tests in 0.538s - OK`.
- Focused replacement guard/reconcile tests: `Ran 5 tests in 0.068s - OK`.
- `python -m unittest tests.postgres_cache_store_test`: `Ran 44 tests in 0.076s - OK`.
- `python -m compileall server/postgres_cache_store.py server/websim_payload.py` exited 0.

Deployment and live write evidence:

- Hot deploy used `WOW_DEPLOY_SKIP_BOOTSTRAP=1` and `WOW_DEPLOY_START_ASYNC_SYNCS=0`.
- Backup before final recompute write: `/opt/wow-mini-program/backups/community-gear-recompute-predicate-fix-before-20260704T204908Z/wow_test.dump`, `17064705` bytes.
- Final recompute `runId`: `pg-community-template-recompute-predicate-fix-20260704T204925Z`.
- Backend after final deploy: `Sun 2026-07-05 04:48:57 CST`, active/running, `Result=success`, `ExecMainStatus=0`, `NRestarts=0`.
- Persisted observed community status now matches public observed coverage: `14 complete / 26 partial`.
- Admin gate observed subset now matches public coverage: `raiderio_observed_profile = 14 verified / 26 blocked`.

Live acceptance evidence:

- `/health`: HTTP 200.
- `/api/data/health`: HTTP 200, `overallStatus=partial`.
- `/admin/gates`: HTTP 200 via GET.
- Authenticated `/api/admin/gates/summary`: HTTP 200, `overallStatus=partial`, `gear_templates=45` in queue summary.
- Authenticated `/api/admin/gates/records?domain=talents`: `80` records, `80 verified`.
- Authenticated `/api/admin/gates/records?domain=gear_templates`: `79` records, `34 verified / 45 blocked`; source breakdown `raiderio_observed_profile=14 verified / 26 blocked`, `simc_preset=20 verified / 19 blocked`.
- Public `/api/websim/talents` all-spec sweep: `40 specs / 80 hero slots / 80 verified`.
- Public `/api/websim/gear?compact=1&mode=initial` all-spec sweep: `40 specs`, `40 baseline display slots`, `40 observed community rows`, `14 complete / 26 partial`, `errors=[]`.
- Gear canonical slot matrix from public community templates: `640 total / 419 ready / 221 missing`.
- Missing slot totals: `trinket2=22`, `off_hand=18`, `main_hand=17`, `feet=15`, `finger2=15`, `neck=15`, `trinket1=15`, `wrist=15`, `back=14`, `waist=13`, `head=12`, `chest=11`, `finger1=11`, `shoulder=10`, `hands=9`, `legs=9`.

Blocker and next action:

- Phase 1 remains blocked because real community gear completion is only `14/40`; the 640-slot matrix still has `221` missing slots.
- The prior `19 complete` read-model number was reduced intentionally after stale persisted complete labels were reconciled against current slot coverage.
- Next lane should target real missing trinket/ring/off-hand evidence and healer/support profile proof, then rerun observed-only replacement/reconciliation.
- Phase 2 daily incremental update remains gated until Phase 1 acceptance passes.

## 2026-07-05 untruncated observed variants and health freshness status

Status: Phase 1 is improved but still not accepted. Phase 2 daily incremental talent/gear refresh has not started.

Implemented in this slice:

- Removed the global `LIMIT 4000` from observed-variant template construction. Production currently has `7815` current observed variants, so the old cap silently hid trusted older rows from the community gear builder.
- Added `PostgresCacheStore.community_gear_template_live_health_summary()` and wired PostgreSQL-only `/api/data/health` to overlay the current gear-template table instead of stale sync-state gear counts after guarded replacement writes.
- Kept real community coverage separated from baseline `simc_preset` coverage; baseline/default/source-reference/manual-fixture/fallback rows still cannot fill real community gear.
- Fixed the helper to normalize the real `expected_spec_pairs()` return shape (`class:spec` strings), after live smoke exposed that tuple-only test data was too narrow.

Verification:

- Focused no-global-truncation regression: `test_build_community_gear_templates_does_not_globally_truncate_observed_variants`.
- Focused live-health regressions: `test_community_gear_template_live_health_summary_reads_current_rows` and `test_pg_only_data_health_uses_postgres_state_without_sqlite`.
- `python -m unittest tests.postgres_cache_store_test`: `Ran 46 tests in 0.065s - OK`.
- `python -m unittest tests.news_backend_test`: `Ran 212 tests in 111.101s - OK`.
- `python -m compileall server/postgres_cache_store.py server/news_backend.py` exited 0.

Deployment and live write evidence:

- Hot deploys used `WOW_DEPLOY_SKIP_BOOTSTRAP=1` and `WOW_DEPLOY_START_ASYNC_SYNCS=0`.
- Backup before the untruncated observed write: `/opt/wow-mini-program/backups/community-gear-untruncated-observed-before-20260704T210026Z/wow_test.dump`, `17065480` bytes.
- Dry run `pg-community-template-untruncated-observed-dry-run-20260704T210015Z`: `38` observed rows, `18 complete / 20 partial`.
- Write run `pg-community-template-untruncated-observed-write-20260704T210046Z`: persisted observed rows ended at `23 complete / 17 partial`.
- Backend after final deploy: `Sun 2026-07-05 05:35:52 CST`, active/running, `Result=success`, `ExecMainStatus=0`, `NRestarts=0`.

Live acceptance evidence:

- `/health`, `/api/data/health`, `/admin/gates`, `/api/admin/gates/summary`, `/api/admin/gates/records?domain=talents&limit=200`, and `/api/admin/gates/records?domain=gear_templates&limit=200` all returned HTTP 200.
- `/api/data/health` now reports current active gear-template state: `gearTemplates.total=77 / verified=43 / partial=34 / blocked=0`, `lastSyncRun=pg-community-template-untruncated-observed-write-20260704T210046Z`.
- Health real community gear: `23 covered / 17 partial+missing / 0 pending / 0 blocked`.
- Health canonical slot matrix: `640 total / 550 ready / 90 missing`.
- Admin records: talents `80 verified`; gear templates `43 verified / 34 blocked`.
- Direct DB source split: `raiderio_observed_profile=23 complete / 17 partial`, `simc_preset=20 complete / 17 partial`; two expired `simc_preset` partial rows are excluded from health/admin active counts.
- Public `/api/websim/talents` all-spec sweep: `40 specs / 80 templates / 80 verified`, `errors=[]`.
- Public `/api/websim/gear?compact=1&mode=initial` single-flight all-spec sweep: `40 specs`, `40 observed community rows`, all `raiderio_observed_profile`, `23 complete / 17 partial`, `90` missing slots, `errors=[]`, `bad=[]`.
- A 4-way public gear sweep attempt timed out after three specs and was discarded as invalid evidence; the accepted sweep was single-flight from server localhost.

Blocker and next action:

- Phase 1 remains blocked because real community gear completion is `23/40`; the 640-slot matrix still has `90` missing slots.
- Highest-count remaining slot gaps: `trinket2=12`, `trinket1=8`, `off_hand=7`, `back=6`, `feet=6`.
- Next lane should target those high-impact missing slots with real observed variant proof, then rerun guarded replacement and the same health/admin/public sweeps.
- Phase 2 daily incremental update remains gated until Phase 1 acceptance passes.

## 2026-07-05 missing-slot backfill status

Status: Phase 1 is improved but still not accepted. Phase 2 daily incremental talent/gear refresh has not started.

Implemented in this slice:

- Ran a bounded production `gear_template_first_sync` backfill against the current missing-slot set.
- Kept the production trust rule unchanged: Raider.IO observed profile data is source evidence only; complete community gear still requires trusted SimulationCraft JSON gear stats or Battle.net-backed item proof.
- Investigated an item-table-stat fallback and left it disabled because the strict safe match did not improve coverage, while looser matching would risk cross-spec, wrong-slot, or stale stat leakage.
- No local code patch was made in this slice; the progress came from live evidence collection and guarded rebuild.

Backup and live run evidence:

- Backup before write: `/opt/wow-mini-program/backups/community-gear-missing-slot-backfill-20260704T214139Z/wow_test.dump`, `17086607` bytes.
- Transient unit: `wow-community-gear-first-sync-20260704T214249Z.service`.
- Result: `success`, `code=exited/status=0`, runtime `7min 41.291s`, CPU `2min 51.204s`, memory peak `1.1G`.
- Final `syncRunId`: `pg-community-template-2026-07-04T214249z0000`.
- Observed backfill checked at `2026-07-04T21:48:21+00:00`: `processedProfileCount=752`, `variantCount=3974`, `verifiedCount=3138`, `partialCount=836`, `blockedCount=412`, `simcProfileCount=752`, `simcResolvedProfileCount=628`, `simcResolvedSlotCount=9656`, `stopReason=target_limit_reached`.

Live acceptance evidence:

- `/health`, `/api/data/health`, `/admin/gates`, `/api/admin/gates/summary`, `/api/admin/gates/records?domain=talents`, `/api/admin/gates/records?domain=gear_templates`, and `/api/admin/gates/queue?domain=gear_templates` all returned HTTP 200.
- `/api/data/health` remains `overallStatus=partial`.
- Public `/api/websim/talents` all-spec sweep: `40 specs / 80 templates / 80 verified`, `bad=[]`, `badApply=[]`.
- Corrected public `/api/websim/gear?compact=1&mode=initial` all-spec sweep: `40 specs`, `bad=[]`, `errors=[]`, all `40` community rows from `raiderio_observed_profile`.
- Gear `community_best`: `27 complete / 13 partial / 0 pending / 0 public blocked`.
- Gear baseline display slots: `27 complete / 5 partial / 8 blocked`, with sources `32 simc_preset / 8 baseline_blocked`.
- Gear community canonical slot matrix: `640 total / 577 ready / 63 missing`.
- Missing slot totals: `trinket2=9`, `off_hand=6`, `trinket1=5`, `neck=4`, `hands=4`, `waist=4`, `feet=4`, `finger2=4`, `main_hand=4`, `chest=3`, `shoulder=3`, `back=3`, `wrist=3`, `finger1=3`, `head=2`, `legs=2`.

Remaining blocker classification:

- The previous `90` missing community slots classified as `75` missing trusted SimC stats, `8` paired equivalent-slot distinct-item gaps, `7` no observed variant rows, and `0` possible builder gaps.
- The current `63` missing community slots classify as `54` missing trusted SimC stats, `7` paired equivalent-slot distinct-item gaps, `2` no observed variant rows, and `0` possible builder gaps.
- The largest remaining stat-proof blockers are healer/support profiles that current SimC resolution does not fully cover: `holy`/`discipline` Priest, `holy` Paladin, `mistweaver` Monk, and `preservation` Evoker.
- Warlock `affliction` and `destruction` still need real off-hand evidence; one-handed main-hand metadata is not enough to occupy `off_hand`.

Blocker and next action:

- Phase 1 remains blocked because real community gear completion is `27/40`; the 640-slot matrix still has `63` missing slots.
- Next lane should target Battle.net Game Data item-instance proof or another verified stat source for the `54` statless observed rows, distinct second trinket/finger evidence for paired-slot gaps, and real off-hand rows for the two Warlock specs.
- Phase 2 daily incremental update remains gated until Phase 1 acceptance passes.

## 2026-07-05 preflight parity fix and targeted 13-spec sync status

Status: Phase 1 is improved but still not accepted. Phase 2 daily incremental talent/gear refresh has not started.

Implemented in this slice:

- Fixed the PG gear preflight to reuse current class/spec-aware slot coverage semantics instead of trusting stale persisted `missingSlots`.
- The scheduler now treats mandatory two-hand/ranged off-hand occupancy and equivalent-slot reconciliation the same way the public read model does.
- The read-only production preflight target set now matches public health: `13` partial community specs and `63` missing slots before the targeted run.

Verification:

- Focused RED/GREEN scheduler regression: `tests.postgres_cache_sync_test.PostgresCacheSyncTest.test_gear_preflight_treats_mandatory_two_hand_offhand_as_covered`.
- Focused pair: `Ran 2 tests in 0.050s - OK`.
- `python -m unittest tests.postgres_cache_sync_test`: `Ran 28 tests in 0.093s - OK`.
- `python -m compileall server/postgres_cache_sync.py` exited 0.

Deployment and targeted sync evidence:

- Deployed `server/postgres_cache_sync.py` by narrow remote install.
- Backend after restart: `Sun 2026-07-05 06:10:23 CST`, active/running, `Result=success`, `ExecMainStatus=0`, `NRestarts=0`.
- Backup before write: `/opt/wow-mini-program/backups/community-gear-targeted-13spec-before-20260704T221128Z/wow_test.dump`, `17329236` bytes.
- Transient unit: `wow-community-gear-targeted-13spec-20260704T221203Z.service`.
- Result: success, runtime `7min 49.822s`, CPU `3min 7.567s`, memory peak `1.1G`, swap peak `0B`.
- Final `syncRunId`: `pg-community-template-2026-07-04T221203z0000`.
- Observed backfill processed `900` profiles, `14560` observed items, and `4355` variants; `2249` verified, `2106` partial, `514` blocked; `528` SimC profiles resolved `8243` slots.

Live acceptance evidence:

- `/health`, `/api/data/health`, `/admin/gates`, `/api/admin/gates/summary`, `/api/admin/gates/records?domain=talents`, `/api/admin/gates/records?domain=gear_templates`, and `/api/admin/gates/queue?domain=gear_templates` all returned HTTP 200.
- `/api/data/health` remains `overallStatus=partial`; gear templates are `77 total / 63 verified / 14 partial-or-admin-blocked`.
- Talent public sweep: `40 specs / 80 templates / 80 verified`, `bad=[]`, `badApply=[]`.
- Gear public sweep: `40 specs`, `bad=[]`, `errors=[]`; all `40` community rows are `raiderio_observed_profile`.
- Gear `community_best`: `32 complete / 8 partial / 0 pending / 0 public blocked`.
- Gear baseline display slots: `27 complete / 5 partial / 8 blocked`, with sources `32 simc_preset / 8 baseline_blocked`.
- Gear community canonical matrix: `640 total / 592 ready / 48 missing`.
- Remaining partial specs: `evoker:preservation`, `monk:brewmaster`, `monk:mistweaver`, `paladin:holy`, `priest:discipline`, `priest:holy`, `warlock:affliction`, `warlock:destruction`.

Remaining blocker classification:

- Current `48` missing community slots classify as `43` observed rows missing trusted SimC stats, `3` observed off-hand rows missing trusted SimC stats while main-hand occupancy remains unproven, `2` off-hand slots with no observed row and unproven main-hand occupancy, and `0` possible builder gaps.
- The remaining gaps are therefore provenance/data gaps, not known builder gaps.
- The next lane should target verified stat proof for healer/support rows and real/proven off-hand evidence for the remaining caster/hybrid gaps.

Blocker and next action:

- Phase 1 remains blocked because real community gear completion is `32/40`; the 640-slot matrix still has `48` missing slots.
- Do not relax production completion by using Raider.IO/WCL profile API attributes, stale persisted missing-slot data, or cross-spec item-table stats.
- Phase 2 daily incremental update remains gated until Phase 1 acceptance passes.
