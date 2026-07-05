# 社区模板增量刷新与变化评估方案

> 日期：2026-07-04
> 状态：方案草案，待拆实施计划
> 范围：社区天赋模板、社区装备模板、日更差异同步、变化好坏判定、后台/health 验收。

## 背景

首次补齐 80 个社区天赋槽位时，系统经历了多轮全量扫描、跨区扩样本、run-detail 深挖、`missing_slots` 窄刷新和 import-code selector 收尾。这种方式适合首次建库和抢救长尾缺口，但不适合作为每天运行的常态。

日更机制不能默认把全部 Raider.IO ranking、run-detail、profile、WCL 证据和 SimC gear probe 全部重跑一遍。后续应该把“首次补齐”和“持续刷新”拆开：

- 首次建库可以使用较大预算，目标是建立完整覆盖。
- 日常刷新应该浅层、增量、差异化，目标是发现变化和保持新鲜度。
- 深度刷新应该只给 pending、stale、blocked 或低置信目标。
- 全量重建只在赛季切换、SimC / 天赋 authority / 装备 catalog 重大变更时显式触发。

装备模板也面临同样问题。装备的目标维度不同，但同样不能每天重建全部 profile、variant、SimC probe 和模板。

## 目标

- 首次全量补齐后，日常刷新不再默认全量重跑。
- 保持 fail-closed：不得把 baseline、manual fixture、fallback、stale、expired、跨 hero 借码或错误来源晋级为真实社区 verified。
- 每次刷新输出可审计 diff：不变、元数据刷新、晋级、仅候选、需复核、拒绝、阻断。
- 复用当前天赋的 target matrix、active winner、`missing_slots` 和 WebSim authority 校验。
- 为装备模板补齐等价的增量 digest、target queue 和 winner 保护。
- 让 admin gates 能回答：今天哪些槽变了，为什么变，变化是好还是坏。

## 非目标

- 不放松 WebSim authority、SimC gear stat、source honesty 或完整装备门禁。
- 不要求必须有 WCL 才能展示 Raider.IO verified 模板。
- 不用裸 DPS/HPS/key level 作为自动替换依据。
- 不允许 partial 装备模板覆盖 complete winner。
- 首版不引入大型分布式任务系统，优先沿用当前 PG sync state 和 systemd job 模式。

## 当前基础

### 天赋已有能力

- 固定目标矩阵：`40 specs x 2 hero slots = 80 slots`。
- `missing_slots` 模式：只针对未 verified 的 `class/spec/hero` 槽位。
- Raider.IO per-spec ranking：按职业专精定向拉榜。
- Raider.IO `talentLoadoutText` import-code 解码：先从榜单行识别 hero selector。
- WebSim authority：解析和编码是 verified 硬门禁。
- WCL evidence tier：`wcl_exact_template`、`wcl_character_supported`、`wcl_missing`、`wcl_conflict`、`wcl_blocked`。
- active-slot housekeeping：每个 `class/spec/hero` 只保留一个 active winner。

### 装备已有能力

- 社区装备模板从 PG profile presets、observed gear 和 catalog 证据派生。
- 装备模板记录包含 status、signature、raw string、ready slot count、missing slots。
- observed gear variants 已有独立 backfill/state 思路。
- 社区装备模板本身还缺少类似天赋 80 槽矩阵的 target queue 和 digest-based rebuild。

## 刷新模式

### `daily_light`

用途：低成本新鲜度巡检和变化发现。

天赋行为：

- 每个 spec 只扫 Raider.IO per-spec ranking 的浅层窗口，例如前 1-2 页。
- 优先解 `talentLoadoutText`，不默认抓 run-detail / profile。
- 将解码出的 `class/spec/hero/signature` 与当前 active winner 比较。
- 如果 signature 不变，只更新 freshness / evidence 元数据。
- 如果发现新 signature，才进入 candidate validation。
- WCL 只给当前 winner 或高质量 candidate 补 evidence，不阻断 Raider.IO verified。

装备行为：

- 为每个 `class/spec/sourceKey` 计算 `inputDigest`。
- digest 不变则不重建该 spec 的装备模板。
- 只 probe missing、partial、stale gear variants。
- 同 normalized gear-line signature 的 SimC JSON gear-stat 结果复用缓存。

### `daily_targeted`

用途：只处理已知缺口，不全量重跑。

天赋行为：

- 读取当前 coverage matrix。
- 只把 `pending_collection`、`blocked`、`stale`、低置信 slot 放入 target queue。
- 每个 target 从自己的 cursor 继续：region、page、rank、source window。
- 只有目标仍有找到候选的概率时才增加深度预算。

装备行为：

- 只处理 partial community gear template、stale winner、缺 canonical slot、stale/partial variant。
- 优先补齐 missing slot 和 stale variant。
- 新 candidate 未达到 complete 前，不 expire 旧 complete winner。

### `weekly_deep`

用途：受控扩样本。

- 扩大 Raider.IO pages / regions，主要服务长尾 hero slot。
- raw import code 缺失或冲突时，才抓 run-detail / profile。
- 给 promoted candidate 做 WCL exact/support 证据刷新。
- 在 CPU/API 预算内扩大 observed gear profile 与 SimC gear-stat probe。

### `season_reset_full`

用途：显式全量重建。

触发条件包括：

- 新赛季或赛季池变更。
- SimC build 变化。
- talent schema / WebSim authority 变化。
- gear catalog revision 变化。
- 外部来源 contract 发生明显漂移。

这是唯一可以常规采用“类似全量”的模式。

## 增量状态模型

首版可以先落在 PG sync state JSON；如果体积和查询需求增长，再升为正式 PG 表。

### Refresh Target

表示一个可续跑目标。

天赋 target key：

```text
talent:<classKey>:<specKey>:<heroKey>
```

装备 target key：

```text
gear:<classKey>:<specKey>:<sourceKey>
gear-variant:<itemId>:<slot>:<sourceType>:<itemLevel>:<optionDigest>
```

建议字段：

- `targetKey`
- `targetType`: `talent_slot`、`gear_template`、`gear_variant`
- `status`: `healthy`、`pending_collection`、`stale`、`blocked`、`needs_review`
- `priority`
- `currentWinnerId`
- `currentWinnerSignature`
- `currentEvidenceTier`
- `lastCheckedAt`
- `nextRunAt`
- `cursor`
- `budget`
- `stopReason`
- `lastChangeSummary`

### Cursor

天赋 cursor：

- `sourceKey`
- `region`
- `page`
- `rank`
- `lastObservedHeroKey`
- `lastCandidateId`
- `lastRunId`

装备 cursor：

- `provider`
- `profileOffset`
- `targetItemIds`
- `variantOffset`
- `lastProbeSignature`
- `failedProbeCount`

### Candidate Ledger

候选先入 ledger，不直接发布。

建议状态：

- `candidate`
- `promoted`
- `candidate_only`
- `needs_review`
- `rejected_regression`
- `rejected_blocked`
- `expired`

建议字段：

- `candidateId`
- `targetKey`
- `sourceKey`
- `sourceUrl`
- `signature`
- `status`
- `evidenceTier`
- `qualityScore`
- `hardGateStatus`
- `promotionReason`
- `rejectionReason`
- `firstSeenAt`
- `lastSeenAt`

### Winner History

记录 active winner 变化。

建议字段：

- `targetKey`
- `previousWinnerId`
- `nextWinnerId`
- `changeType`
- `reason`
- `checkedAt`
- `operatorMode`
- `sourceSummary`

## 如何判断变化是好还是坏

新数据不能默认代表更好。每个 candidate 先过两层判断：

1. hard gate：能不能被消费。
2. promotion gate：是否明显优于当前 winner。

### 硬回退

出现以下情况，一律视为坏变化，不能自动晋级：

- `class/spec/hero` 不匹配。
- WebSim authority 解析失败。
- WebSim talent encoding 失败。
- 天赋 `canApplyVisual` 从 true 变 false。
- 天赋状态从 `verified` 降为 `partial`、`blocked` 或 `pending_collection`。
- WCL evidence 变为 `wcl_conflict` 或 `wcl_blocked`。
- 来源变成 stale、expired、manual fixture、baseline、fallback 或错误 source family。
- Raider.IO profile-current 专精污染。
- run-detail 与 import-code selector 冲突。
- 跨 hero 借码。
- 装备模板从 `complete` 变 `partial`。
- 装备模板丢失 canonical slot。
- 装备 variant 丢失 verified stat evidence。
- 之前 verified 的装备 variant 新增 SimC resolution warning 或 probe failure。

### 天赋晋级规则

只比较通过 hard gate 的候选。

推荐顺序：

1. `wcl_exact_template`
2. `wcl_character_supported`
3. Raider.IO-only / `wcl_missing`
4. 更高 normalized quality score
5. 更高 key level
6. 更多 source refs / samples
7. 更新 evidence
8. 稳定 id tie-breaker

替换要有滞后阈值，避免每天抖动：

- 很小的 quality 变化不替换。
- WCL-backed winner 不被普通 Raider.IO-only candidate 替换，除非当前 winner stale 或 invalid。
- signature 不同但证据没有更强时，只进入 `candidate_only` 或 `needs_review`。
- winner 失效、过期、来源不可信时，允许同等级候选接管。

### 装备晋级规则

推荐顺序：

1. `complete` 优于 `partial`。
2. 16 个 canonical slots 完整。
3. 所有装备 variant 都有 verified stat evidence。
4. gem / enchant / crafted_stats blocker 更少。
5. 有更多真实 observed evidence。
6. 来源更新。
7. 稳定 id tie-breaker。

装备避免单字段过拟合：

- 不能因为单件装等更高就替换整套模板。
- 不能用更不可执行的整套模板替换当前 complete winner。
- Raider.IO / WCL profile API 的装备属性不能当生产装备属性。

## Change Report

每次刷新必须输出差异摘要，而不是只输出 total / verified。

建议桶：

- `unchanged`: active winner 没变。
- `metadata_refreshed`: winner/signature 没变，只刷新 freshness 或 evidence 元数据。
- `promoted`: winner 替换。
- `candidate_only`: 发现新候选，但当前 winner 仍更好。
- `needs_review`: 候选可能更好，但自动替换依据不足。
- `rejected_regression`: 候选触发质量或来源回退。
- `blocked`: 候选未通过 authority / SimC / source gate。
- `stale_winner`: 当前 winner 接近过期或来源 stale。

每条 promotion / rejection 需要说明：

- previous winner
- next candidate
- evidence tier 对比
- quality score 对比
- hard gate 结果
- source URLs
- promotion 或 rejection reason

## 天赋增量流程

```text
读取 coverage matrix
  -> 构造 target queue
  -> daily_light 浅扫 Raider.IO per-spec ranking
  -> 优先解 import code selector
  -> 与当前 winner signature 对比
  -> 仅校验 changed candidate
  -> 必要时刷新 WCL evidence
  -> promotion gate
  -> 更新 winner / candidate ledger
  -> 发布每槽 1 个 active winner read model
  -> 输出 change report
```

关键约束：

- import-code 解码优先于 run-detail / profile。
- run-detail / profile 预算归属于 target slot，而不是全局扫描。
- `missing_slots` 应升级为 cursor queue，而不只是 target-spec filter。
- `pending_collection` 继续是正常公开状态，不是系统错误。

## 装备增量流程

```text
读取 gear catalog / variant 状态
  -> 计算 profile preset / observed variant inputDigest
  -> 只 target changed 或 stale specs
  -> 只 probe missing / partial / stale variants
  -> 只重建 digest changed 的 gear template
  -> 比较 complete winner 与 candidate
  -> 新数据 partial 时保留旧 complete winner
  -> 输出 change report
```

关键约束：

- 用 `inputDigest` 决定是否重建装备模板。
- 用 normalized gear-line signature 缓存 SimC JSON gear-stat probe。
- gear catalog variant health 和 community gear template health 分开表达。
- default template、partial source reference 不填平真实社区覆盖。

## Admin 和 Health 展示

`/api/data/health` 应补充：

- refresh mode
- target counts by status
- stale target count
- promoted count
- candidate-only count
- rejected regression count
- blocked count
- last full audit time
- next scheduled deep refresh

`/admin/gates` 应增加 slot/spec 视角：

- active winner
- candidate count
- last change
- rejection reasons
- cursor position
- next action
- freshness status

owner 首屏应能回答：“今天哪些槽变了，这些变化是提升、候选、需复核，还是回退？”

## 建议落地阶段

### Phase 1：天赋 daily incremental

- 新增 `daily_light` 模式。
- 将 refresh target state 写入现有 sync state JSON。
- Raider.IO per-spec ranking 只浅扫。
- 优先解 import code。
- 只校验变化候选。
- 输出 change report。

### Phase 2：cursor-based targeted gaps

- 将 `missing_slots` 升级为 cursor queue。
- 记录每个 target 的 page / region / rank。
- 增加带 TTL 的 reject cache。
- 避免重复扫描已确认耗尽的长尾窗口。

### Phase 3：gear template digesting

- 为社区装备模板新增 `inputDigest`。
- 只重建 digest changed specs。
- 新数据 partial 时保留 complete winner。
- 增加 variant 级 stale/missing target queue。

### Phase 4：统一后台 diff

- admin gates 增加 target queue、candidate、winner history 视图。
- 固化 post-sync 只读验收命令：
  - `/api/data/health`
  - 40 个 `/api/websim/talents`
  - 代表性 `/api/websim/gear`
  - admin gates records
  - duplicate active target check
  - bad source check
  - canApply / canUseInSimc check

## 验收标准

- 日常天赋刷新不再默认运行旧的 all-slot deep scan。
- 无变化时，daily refresh 不重写 active winners。
- hard gate 失败的 candidate 永不替换 winner。
- WCL-backed winner 不被较弱 Raider.IO-only candidate 替换，除非 stale 或 invalid。
- 装备 complete winner 不被 partial candidate 替换。
- 重复 daily run 不重复扫描同一批已耗尽长尾窗口。
- health 和 admin gates 展示 change buckets 和 promotion reasons。
- full rebuild 仍可执行，但必须显式触发。

## 待决策问题

- still-valid winner 的 stale 窗口应该是 7、14 还是 30 天？
- WCL exact evidence 是否应该延长 winner TTL？
- 每个 slot/spec 保留多少 candidate-only 记录再 compact？
- gear template digesting 放在 community template sync 内，还是拆独立 gear-template refresh job？
- 生产环境每日 SimC gear probe 的最大 CPU 预算是多少？
