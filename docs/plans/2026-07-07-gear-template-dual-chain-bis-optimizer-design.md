# 装备模板双链路与毕业级 SimC Optimizer 设计

> 日期：2026-07-07
> 状态：方案确认，待拆实施计划
> 范围：`community_best_v2` 真实角色快照链、`recommended_bis_v1` 毕业目标推荐链、SimC optimizer、真实玩家 anchor 校验、12.1 赛季初状态门禁。

## 背景

当前装备导入已经能达到 `communityImportTemplates=80/80`，但 2026-07-07 的元素萨回归暴露出两个架构问题。

第一，真实社区装备模板不应是来源不明的 rawString。线上 `observed_profile_shaman_elemental` 曾返回 `sourceUrl=""`、`sampleCount=0`，且 rawString 中出现和当前高分角色页面不一致的武器组合。这说明现有 `community_best` 语义还不够像“真实角色快照”，更像同步链路中拼出的观测模板。

第二，`season_recommendation` 不能承担毕业推荐。以 Mandur 的 Blizzard Armory 当前真实角色为 anchor，在同一 Mandur profile、同一天赋、同一 APL、同一场景 `HecticAddCleave / 5 targets / 180s / 10000 iterations` 下，Mandur 当前装备约 `237956 DPS`，线上 baseline 模板约 `211177 DPS`，baseline 低约 `12.68%`。这说明基于静态绿字权重和单件评分的 baseline 即使可导入，也不能被理解为推荐或毕业目标。

因此装备模板需要拆成两条语义独立的链路：

- `community_best_v2`：真实玩家当前装备快照，随赛季进度更新。
- `recommended_bis_v1`：面向毕业目标的 SimC optimizer 推荐，不受当前玩家获取进度拖低。

## 设计原则

- 事实样本和推荐结论分离。真实玩家穿什么是一条事实链，系统推荐什么是另一条优化链。
- 绿字权重只用于召回和候选压缩，不能作为最终裁判。
- 最终 winner 必须由 SimC gear compare 决定，并通过真实高分玩家 observed anchor 反证。
- 任何推荐若低于 top observed anchor 超过误差带，不能升级为 `verified`。
- 赛季初可以给 `projected_bis`，但不能把预测包装成 `verified_bis`。
- 旧 `season_recommendation` 降级为 legacy/starter baseline，只能作为可导入起点或诊断 fallback，不再承担毕业推荐主语义。

## 非目标

- 不在首版实现无限制全组合暴力搜索。
- 不把 Wowhead、Method、Murlok、U.GG 等页面结论直接写成 verified 装备模板；这些来源只能提供候选发现、优先级 prior 或人工交叉校验。
- 不用单一 stat weight、单件 item score 或装等排序决定毕业推荐。
- 不要求赛季初就产出 `verified_bis`。
- 不让前端拼 SimC profile；profile serialization、enhancement merge、legality gate 和 SimC run 都继续由后端承担。

## Public Template Contract

小程序装备导入应展示两个清晰类别。

### 高分玩家当前装备

`templateType=community_observed`，来源是一个具体角色的当前装备快照。

用户理解：高分玩家现在穿什么。

允许特性：

- 随赛季进度变化。
- 赛季初可能不是毕业装。
- 可以按 Raider.IO 分数、WCL 表现或 SimC replay DPS 选择 winner。
- 可以被新鲜真实快照替换。

禁止特性：

- 不能叫 BiS、毕业、最优推荐。
- 不能没有具体角色来源。
- 不能把系统拼装模板伪装成真实角色。

### 毕业目标推荐

`templateType=recommended_bis`，来源是系统 optimizer 生成的目标装备组合。

用户理解：当前赛季最终目标配装。

允许特性：

- 赛季初可显示为 `projected_bis`。
- 候选池可包含当前还没人穿齐的装备。
- 可使用最高可达装等、Catalyst、crafted、embellishment、宝石、附魔和套装转化建模。

禁止特性：

- 不能低于真实高分玩家 anchor 很多还继续展示为推荐。
- 不能用 community winner 当作毕业推荐替代品。
- 不能在 SimC 或关键候选缺证据时标记 `verified_bis`。

## community_best_v2

### 数据来源

候选来源优先级：

1. Blizzard Armory / SimC `armory=` 当前角色导出。
2. Raider.IO profile 当前装备，必须可映射到具体角色和 Armory 链接。
3. WCL combatantinfo 装备快照，后续用于战斗场景佐证。
4. Murlok / U.GG 等聚合页只作为发现角色，不作为最终装备 rawString 来源。

每条快照必须绑定：

- `characterName`
- `region`
- `realm`
- `sourceUrl`
- `sourceProvider`
- `fetchedAt`
- `profileHash`
- `simcRuntimeRevision`
- `talentImportCode`
- `heroKey`
- `mplusScore` / `rank` / `sampleWindow`
- 16 槽装备 raw lines
- 场景 SimC replay 结果

如果没有具体角色 URL 或 profile hash，不能进入 `community_best_v2` active winner。

### Winner 选择

每个 class/spec 维护一个 candidate ledger。候选进入 ledger 后先验证：

- 当前赛季和当前专精一致。
- SimC/Armory profile 导入成功。
- 16 个 canonical 槽位可识别。
- serializer replay 不丢槽、不改写非法组合。
- 关键装备有可追踪 item id、bonus、gem、enchant、crafted stats。

首版 winner 策略建议：

1. 取 top N 高分玩家，例如 Raider.IO 每 spec 前 20-50。
2. 用统一场景跑 SimC replay。
3. 选择 `simcDps` 最高的真实角色作为 `community_best_v2`。
4. 同时记录分数最高角色、DPS 最高角色、当前 active winner 是否一致。

如果 SimC replay 不稳定或外部 API 不可用，可以短期退回“分数最高真实角色”，但状态必须是 `observed_provisional`。

### 状态

- `observed_verified`：真实角色来源明确，profile 导入成功，16 槽完整，SimC replay 成功。
- `observed_provisional`：真实角色明确，但 SimC replay 或部分 enhancement evidence 不完整。
- `observed_stale`：超过新鲜度窗口，例如 24-48 小时。
- `observed_partial`：角色可识别，但装备槽、variant 或 serializer replay 不完整。
- `observed_blocked`：无具体角色来源、profile 无法导入、装备不可复现或规则冲突无法解释。

## recommended_bis_v1

### 输入

`recommended_bis_v1` 使用完整赛季装备池，而不是社区 winner。

输入必须绑定 revision：

- `seasonManifestRevision`
- `gearCatalogRevision`
- `talentCatalogRevision`
- `simcRuntimeRevision`
- `terminologyRevision`
- `scenarioKey`
- `optimizerVersion`

装备池包括：

- 当前 M+ 地城掉落。
- 当前团本掉落。
- 套装和 Catalyst 转化。
- 制造装备、crafted stats、embellishment。
- 宝石、附魔、临时武器强化和职业 prep policy。
- 武器、饰品、戒指、unique-equipped 和装等轨道。
- 当前可达到最高装等与赛季终局装等假设。

每个候选必须能生成后端 SimC-ready line。只有 source 但缺可执行 variant 的装备不能进入最终 winner。

### 状态

- `projected_bis`：基于当前已知赛季池和 SimC runtime 的预测毕业目标。允许赛季初展示，但必须标注预测/待验证。
- `candidate_bis`：候选池完整，optimizer 可跑通，关键组合已低迭代筛选，但 observed anchor 或关键 pairwise compare 尚未完全通过。
- `verified_bis`：高迭代 SimC、pairwise compare、真实 observed anchor 校验均通过。
- `optimizer_blocked`：缺装备池、缺 variant、SimC crash、关键装备不可建模或搜索空间无法收敛。
- `optimizer_failed`：生成的推荐显著低于 top observed anchor，或稳定性检查失败。

旧 `season_recommendation` 可以作为 `starter_baseline` 继续存在，但不再填充 `recommended_bis_v1` 的 verified 语义。

## Optimizer Search

### 绿字权重的角色

绿字权重只用于候选召回，不用于最终决策。

原因：

- 绿字收益是局部边际收益，受当前装备分布、天赋、套装、饰品、武器和场景影响。
- 同一专精不同 seed profile 可能得到不同 scale factors。
- 单件权重分数无法表达饰品触发、套装阈值、crafted/embellishment 组合和属性递减。

因此 optimizer 使用多 prior 保守召回：

- `mastery_heavy`
- `crit_heavy`
- `haste_heavy`
- `balanced`
- `observed_scale_factor`
- `guide_prior`
- `community_distribution_prior`

只要一件装备在任一 prior 下进入同槽候选前列，就应保留。只有被另一件同槽装备在装等、主属性、特效、插槽、套装关系和副属性上全面支配时，才可 Pareto 淘汰。

### 候选压缩

普通槽位保留 Top K，例如 8-12。

特殊部位放宽：

- 武器组合池。
- 饰品组合池。
- 戒指组合池。
- 套装 4/5 与散件替代池。
- crafted / embellishment 池。
- 带特殊效果或 unique-equipped 装备池。

候选压缩的成功标准不是“选出最优”，而是“不剪掉可能最优的装备”。每次压缩必须输出 `prunedReason` 和 `keptByPrior`，便于审计。

### 组合搜索

推荐搜索分三层。

第一层：seed profiles。

- 当前 `community_best_v2` winner。
- 分数最高真实角色。
- 最高装等粗配装。
- mastery-heavy / crit-heavy / haste-heavy / balanced 粗配装。
- 套装 4 件 + 不同散件组合。
- 不同武器和饰品组合。

第二层：低迭代粗筛。

- 每个组合块先局部比较。
- 保留前 N 个组合，例如 20-50。
- 记录每个组合的 DPS、误差、差距和 blockers。

第三层：高迭代精筛。

- 对前 N 套完整 profile 跑高迭代 SimC。
- 对前 3-5 套做 pairwise compare。
- 对关键冲突做 targeted gear compare：武器、饰品、套装 4/5、crafted/embellishment、低收益属性高装等替代。

最终 winner 必须来自高迭代精筛，而不是规则评分。

## Anchor Validation

`recommended_bis_v1` 必须和真实玩家 anchor 对比。

Anchor 来源：

- 当前 `community_best_v2` active winner。
- DPS 最高 observed candidate。
- 分数最高 observed candidate。
- 可选：WCL combatantinfo 高表现样本。

校验规则：

- 如果 recommended DPS >= best observed DPS，且误差带不冲突，可继续升级。
- 如果 recommended DPS 低于 best observed 但在 1-2% 误差/模型差异带内，保持 `candidate_bis`，记录原因。
- 如果 recommended DPS 低于 best observed 超过阈值，例如 2%，标记 `optimizer_failed` 或扩大候选池重跑。
- 如果低 5% 以上，必须阻断，不允许展示为推荐。

Mandur case 应作为固定回归样本：元素萨真实 Mandur profile 在 5 目标场景显著高于旧 baseline 时，旧 baseline 不得标记为 recommended。

## Daily Update Strategy

这次改动会影响日常刷新链路，但两条链的刷新目标不同，不能用同一个“每天全量重建”任务处理。

### community_best_v2 daily refresh

`community_best_v2` 是日更原生链路。它表达的是当前赛季真实玩家观测事实，因此允许随赛季进度逐步变好。

日常任务分四档：

- `daily_light`：每天拉取每个专精 top N 真实角色，比较 `profileHash` / `gearHash` / `talentHash`。未变化的角色不重跑 SimC；发生变化或新进榜的角色进入 replay queue。
- `daily_targeted`：只补 `stale` / `partial` / `blocked` / `low_confidence` 专精，重试失败 API、缺 profile、缺 slot、缺 SimC replay 的候选。
- `weekly_deep`：扩大榜单窗口、region、样本数和可选 WCL combatantinfo anchor，用于发现慢变化或新流派。
- `season_reset_full`：赛季、版本、装备池或 SimC runtime 大变更时重建 observed ledger，不沿用旧赛季 winner 作为 current truth。

替换 active winner 必须满足：

- 来源是可追溯真实角色快照，有角色、region、realm、sourceUrl、fetchedAt 和 raw profile hash。
- 通过装备合法性 gate、16 槽完整性和 SimC profile 可运行性检查。
- 相同场景 SimC replay 高于当前 winner，且误差带不冲突；否则进入 candidate ledger，不自动替换。
- 如果当天外部 API 失败或新样本 partial，保留旧 verified observed winner，并把专精标记为 `stale` / `refresh_blocked`，不能用 partial candidate 覆盖。

### recommended_bis_v1 daily guard

`recommended_bis_v1` 不是每天全量 optimizer 重跑。它表达毕业目标，应该由赛季装备池、最高可达装等、规则建模和 SimC optimizer 决定；每日任务只做守卫和触发判断。

每日 guard 检查：

- `seasonManifestRevision` 是否变化。
- `gearCatalogRevision`、variant、gem、enchant、crafted、embellishment、tier set metadata 是否变化。
- `simcRuntimeRevision` 是否变化，或 SimC health 是否从 blocked 恢复。
- `community_best_v2` observed anchor 是否更新，并且是否反证当前 recommended winner。
- 旧 optimizer 是否处于 `optimizer_blocked` / `optimizer_failed` / `anchor_failed`，且满足重试窗口。

触发 full optimizer 的事件：

- 赛季或版本 cutover。
- 装备池、最高装等、升级轨道、套装、饰品、武器、crafted / embellishment 规则变化。
- SimC runtime 更新，且影响 profile 可运行性或装备效果建模。
- 新 observed anchor 稳定高于当前 recommended winner，例如超过 2% block threshold。
- 管理员手动触发某 spec / scenario 重算。

如果 daily guard 发现 observed anchor 反证 recommended：

- `verified_bis` 立即降级为 `anchor_failed` 或 `candidate_bis`。
- 前端不能继续把它展示成毕业推荐，只能展示为待复核/历史结果/暂不可验证。
- optimizer queue 只入队受影响 spec / scenario，不触发 40 specs 无差别全量风暴。

### Cost and stability controls

- 先 hash diff，再决定是否调用 SimC。
- observed 日更只 replay 变化角色，不重跑所有 retained candidates。
- recommended 日更只做 guard，不做 full optimizer；full optimizer 是事件触发和预算受控任务。
- 每条链保留 winner history、candidate ledger 和 reject/blocker reason，避免每天因为小误差或榜单波动反复 churn。
- health 必须区分 `daily checked`、`queued`、`stale`、`blocked`、`anchor_failed` 和 `optimizer_required`，不能只报 `80/80`。

## Evidence Payload

### community_best_v2

```json
{
  "templateType": "community_observed",
  "schemaRevision": "community-best-v2",
  "character": {
    "name": "Mandur",
    "region": "eu",
    "realm": "hyjal",
    "sourceUrl": "https://worldofwarcraft.com/en-gb/character/hyjal/mandur"
  },
  "sourceProvider": "blizzard_armory",
  "fetchedAt": "2026-07-07T00:00:00Z",
  "profileHash": "sha256:...",
  "simcRuntimeRevision": "1205-01-12.0.7.68453",
  "scenarioResults": {
    "mplus_5target_hac": {
      "dps": 237956,
      "errorPct": 0.12,
      "iterations": 10000
    }
  },
  "confidence": "observed_verified"
}
```

### recommended_bis_v1

```json
{
  "templateType": "recommended_bis",
  "schemaRevision": "recommended-bis-v1",
  "optimizerVersion": "gear-bis-optimizer-v1",
  "status": "candidate_bis",
  "scenarioKey": "mplus_5target_hac",
  "candidatePool": {
    "gearCatalogRevision": "gear-catalog-revision",
    "candidateCount": 1234,
    "keptCandidateCount": 168,
    "prunedCandidateCount": 1066
  },
  "statPriorPolicy": {
    "role": "candidate_recall_only",
    "priors": ["mastery_heavy", "crit_heavy", "haste_heavy", "balanced", "observed_scale_factor"],
    "finalDecision": "simc_gear_compare"
  },
  "simc": {
    "lowIterationRuns": 240,
    "highIterationRuns": 12,
    "pairwiseCompares": 8,
    "winnerDps": 242000,
    "winnerErrorPct": 0.15
  },
  "anchorValidation": {
    "bestObservedCharacter": "Mandur",
    "bestObservedDps": 237956,
    "deltaPctVsBestObserved": 1.7,
    "status": "passed"
  },
  "confidence": "verified_bis"
}
```

## Health And Admin Gates

Health should stop treating `80/80` as the full success condition.

New counters:

- `communityObserved.coveredSpecCount`
- `communityObserved.verifiedSpecCount`
- `communityObserved.staleSpecCount`
- `communityObserved.dailyCheckedAt`
- `communityObserved.changedWinnerCount`
- `communityObserved.simcReplayQueuedCount`
- `communityObserved.simcReplayFailedCount`
- `recommendedBis.projectedSpecCount`
- `recommendedBis.candidateSpecCount`
- `recommendedBis.verifiedSpecCount`
- `recommendedBis.blockedSpecCount`
- `recommendedBis.optimizerFailedSpecCount`
- `recommendedBis.anchorFailedSpecCount`
- `recommendedBis.lastGuardCheckAt`
- `recommendedBis.revisionStaleSpecCount`
- `recommendedBis.optimizerQueuedSpecCount`
- `recommendedBis.fullOptimizerRunRequiredSpecCount`

Admin gate must show:

- Which real character is active observed winner.
- Which observed anchors were compared.
- Recommended winner DPS vs observed winner DPS.
- Search budget used.
- Top blockers.
- Why a template is not verified.
- Which candidates were pruned and why.
- Whether the latest daily guard only refreshed observed data or queued a recommended optimizer rerun.

## Rollout Plan

### Phase 0: Read-Only Audit

- For 3-5 representative specs, import top real characters through SimC Armory.
- Store no new active templates.
- Compare current baseline against observed anchor.
- Confirm how often current baseline fails anchor validation.

### Phase 1: community_best_v2

- Build real-character snapshot ledger.
- Require source URL and profile hash.
- Stop accepting source-less observed templates as active winners.
- Keep current `community_best` as legacy fallback until v2 coverage reaches 40/40.

### Phase 2: recommended_bis_v1 Prototype

- Implement one DPS spec first, using Elemental Shaman as regression.
- Build conservative candidate recall.
- Run low/high iteration SimC locally or in a controlled worker.
- Add anchor validation against Mandur-style observed profiles.

### Phase 3: Multi-Spec Expansion

- Expand to all DPS specs.
- Tanks/healers/support remain `projected` or `candidate` until role-specific objectives exist.
- Add health/admin matrix and budget controls.

### Phase 4: 12.1 Cutover Integration

- Bind optimizer to Season Manifest.
- Permit `projected_bis` as soon as 12.1 live gear catalog and SimC runtime are compatible.
- Upgrade to `candidate_bis` after candidate pool and critical special effects are modeled.
- Upgrade to `verified_bis` only after observed anchors and pairwise compares pass.

## Test And Verification Requirements

- `community_best_v2` rejects source-less templates.
- SimC Armory import stores profile hash and source URL.
- Legality gate cannot silently overrule a successful real Armory profile without evidence.
- Candidate recall keeps true observed anchor items even if static stat weights dislike them.
- Pareto pruning never removes special-effect gear, tier pieces, crafted/embellishment, weapons, rings or trinkets without explicit reason.
- Recommended winner lower than observed anchor by more than threshold cannot become `verified_bis`.
- Elemental Shaman Mandur regression: old baseline lower by about 12.68% must be blocked from recommended status.
- `season_recommendation` remains visible only as starter/legacy baseline and never claims `verified_bis`.

## Open Questions

- Exact observed anchor threshold: start with 2% block threshold and 1% warning threshold, then tune after 10-20 specs.
- SimC budget per spec: decide maximum low-iteration and high-iteration runs before implementation.
- Whether WCL combatantinfo should enter Phase 1 or wait until Phase 3.
- How to present `projected_bis` in UI without making it look like final truth.
- Whether non-DPS specs should get separate `recommended_role_v1` instead of sharing `recommended_bis_v1`.
