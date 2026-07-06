# 12.1 Season Cutover Master Checklist

## 背景

2026-07-06 讨论确认：12.1 / Season 2 切换不能只看装备、天赋、套装转化或 SimC runtime 任意单点。正式小程序需要一个更高层的 season cutover 控制面，把所有会影响用户可见数据、模板保存、SimC 结果和 AI 结论的版本轴绑定到同一次切换。

本清单串联以下子设计：

- [12.1 PTR Season Catalog Isolation Design](2026-07-06-12-1-ptr-season-catalog-design.md)
- [12.1 Catalyst Inherited Stats and SimC Design](2026-07-06-12-1-catalyst-inherited-stats-simc-design.md)
- [12.1 PTR Talent Catalog Isolation Design](2026-07-06-12-1-ptr-talent-catalog-design.md)
- [12.1 SimC Runtime Revision and Cutover Design](2026-07-06-12-1-simc-runtime-cutover-design.md)

外部证据：

- [Blizzard 12.1 PTR Development Notes](https://us.forums.blizzard.com/en/wow/t/midnight-curse-of-ulatek-ptr-development-notes/2317811) 已包含大量职业、天赋、套装和物品变更。
- [Season 2 PTR update](https://us.forums.blizzard.com/en/wow/t/midnight-curse-of-ulatek-ptr-development-notes/2317811/10) 已开始披露 Season 2 M+ 测试副本。
- [Curse of Ula'tek Endgame Reward Changes](https://us.forums.blizzard.com/en/wow/t/curse-of-ulatek-endgame-reward-changes/2317450) 涉及 Season 2 升级货币、项链升级、来源和 Great Vault 奖励规则。
- [PTR API namespace discussion](https://us.forums.blizzard.com/en/blizzard/t/ptr-patch-related-namespaces/55366) 表明 Battle.net Game Data API 不应被当成稳定 PTR/future patch 数据源。

本设计只记录总控清单和门禁，不执行代码实现、不采集数据、不写库、不切换线上 pointer。

## 2026-07-06 Implementation Evidence

首个实现阶段已完成只读控制面骨架，不采集 12.1 PTR 数据、不写入 S2 catalog、不切换 active pointer。

- `/api/data/health` 新增 `season_cutover_readiness` component，聚合 active retail manifest、staging/PTR manifests、gear/talent/SimC/community/stat weight/Chickenbro/terminology revision bindings、正式读策略、历史资产策略和 top blockers。
- 正式读策略固定为 `active_retail_manifest`，`allowClientSeasonOverride=false`；PTR/staging manifest 只作为 `internal_only` readiness 状态暴露。
- SimC runtime manifest 扩展 `simcRuntimeRevision`、`sourceCommit`、`artifactHash`、`binaryPath`、`channel`、`status`，用于后续 active/staging runtime pointer 审计。
- 12.1 Catalyst 专项字段 `redirected_base_stats` 已进入后端 SimC gear option allowlist；未知 gear option 仍不会进入 `simcOptions`。
- 术语最小门禁先以后端 fixture 记录 `spellslinger -> 疾咒师`，并将“法术投射者”保留为历史 alias，不作为 canonical display。

实现与测试证据：`server/news_backend.py`、`server/simulator_payload.py`、`server/websim_payload.py`、`tests/news_backend_test.py`。

## 核心目标

12.1 cutover 的目标是保证正式小程序在任意时刻只处于两种可信状态之一：

- S1 active：正式用户只看到 Season 1 数据、模板和模拟结果。
- S2 active：Season 2 的装备、天赋、SimC runtime、来源池、升级规则、社区模板和派生结论已经通过同一套门禁。

不允许出现混态，例如：

- S2 装备搭配 S1 天赋被标记为正式 ready。
- S2 天赋搭配旧 SimC runtime 提交真实模拟。
- S1 社区模板继续作为 S2 当前推荐。
- S2 副本池未切，但装备来源和 PVE 页面已经展示 S2。
- 旧属性权重、职业排行或 Chickenbro allowedNumbers 被继续用于 S2 强结论。

## Season Manifest

新增或抽象一个总控 `seasonRevision`，作为正式小程序读取季节数据的唯一入口。它不替代各子 catalog，而是把各子版本绑定成一个可审计组合。

建议字段：

- `seasonRevision`：例如 `retail-12.1-s2-2026xxxx`。
- `expansion`、`patch`、`season`、`channel`。
- `active`：正式小程序只能读取一个 active retail season。
- `gameBuild` / `liveBuild` / `checkedAt`。
- `gearCatalogRevision`。
- `talentCatalogRevision`。
- `simcRuntimeRevision`。
- `dungeonPoolRevision`。
- `raidLootRevision`。
- `delveRewardRevision`。
- `preyHuntRewardRevision`。
- `upgradeTrackRevision`。
- `vaultRuleRevision`。
- `communityTemplateRevision`。
- `statWeightRevision`。
- `pveRankingRevision`。
- `chickenbroEvidenceRevision`。
- `terminologyRevision`。
- `frontendCopyRevision`。
- `previousSeasonRevision` / `rollbackSeasonRevision`。
- `status`：`candidate`、`staging`、`preflight`、`verified`、`active`、`partial`、`blocked`、`rolled_back`。
- `blockers`：跨系统阻断项。

正式读接口不直接接受用户传入的 `seasonRevision=ptr-*`。内部测试可以通过后台配置或测试环境读取 staging/PTR manifest，但 response 必须显式标记 `channel` 和 `seasonRevision`。

## 数据源分层

PTR 阶段：

- Official PTR notes、Wowhead PTR、SimC PTR/nightly、Wago PTR 只用于候选发现和内部联调。
- PTR `ptr_executable` 只说明内部可运行，不等于正式 `verified`。
- PTR 数据不能进入正式小程序 active manifest。

Live 复核阶段：

- Battle.net live metadata / journal / item-set 是正式物品和来源静态事实的核心证据。
- 稳定 SimC runtime / generated data 是 profile 执行和天赋编码的核心证据。
- Wago DB2 / curated evidence 用于补充附魔、TraitEdge、spell text、可读标签和规则对账。
- Raider.IO / WCL / Archon 只能作为真实玩家样本、排行、日志或参考来源，不能单独把装备属性、天赋规则或强度结论晋升为正式事实。

## Cutover 阶段

### 1. PTR Candidate

- 建立 `ptr-12.1-s2-*` season manifest。
- 采集候选装备、附魔、宝石、制造业、美化、套装、天赋、M+ 副本池、团本、Delves、Prey Hunt 和奖励规则。
- 所有数据默认 `candidate` / `partial` / `blocked`。
- 后台输出 diff、coverage、blocker 和缺口，不影响正式小程序。

### 2. Staging Executable

- 安装 PTR/nightly SimC runtime 到 inactive slot。
- Gear / talent catalog 在 staging 中跑 serializer、profile、stat snapshot 和 SimC smoke。
- Catalyst `redirected_base_stats` 进入专项 fixture。
- M+ / raid / delve / prey reward source 只用于 staging 来源筛选和测试。
- 产物可以晋升为 `ptr_executable`，但不能进入正式 `verified`。

### 3. Inactive Retail Preflight

- 准备 inactive `retail-12.1-s2-*` season manifest。
- 正式 API 仍读取 S1 active。
- 后台预跑全量或分批 catalog rebuild。
- 社区模板、属性权重、PVE ranking 和 Chickenbro 证据先标记 `stale` / `pending_collection`。
- 定义 launch-day job profile，避免所有同步任务同时全量运行。

### 4. Live Revalidation

12.1 live 后必须重新复核：

- Battle.net live item / journal / item-set / spell / media。
- SimC stable runtime 和 source commit。
- Wago DB2 / TraitEdge / enchant evidence。
- M+ dungeon pool、raid loot、Delves、Prey Hunt、upgrade tracks、vault rules。
- Raider.IO / WCL / Archon 新赛季 source availability。
- 40 spec / 80 hero tree matrix。
- 40 spec gear compact traversal。
- `/api/websim/profile` 和 `/api/websim/simulate` 代表样本。

PTR 阶段通过的状态不能直接复制成 live `verified`。

### 5. Active Pointer Switch

只有当 season manifest 的核心 gate 通过时，才允许切换 active：

- `gearCatalogRevision` verified 或明确 partial 且不会暴露为 sim-ready。
- `talentCatalogRevision` verified 或明确 partial 且不会保存为 executable template。
- `simcRuntimeRevision` verified。
- source pool 和 reward rule verified。
- community template 当前赛季矩阵有明确状态。
- stat weights / PVE ranking / Chickenbro evidence 已 stale-closed 或已重建。
- `/api/data/health` 没有 unknown 混态。
- 前端 smoke 通过。

切换动作是 active manifest pointer 切换，不删除 S1 数据。

### 6. Canary and Rollback

- 切换后 24-48 小时保留 S1 rollback manifest。
- 重点观察 `/health`、`/api/data/health`、SimC task success rate、profile serializer blockers、community template coverage、admin gates。
- 如果发现系统性错误，回滚 active manifest 到 S1 或上一个 verified S2 revision。
- 回滚不删除 S2 staging / failed revision，保留用于排查。

## Gate Matrix

| Gate | 必须确认 | 阻断条件 |
| --- | --- | --- |
| Season manifest | 所有 active revision 指向同一 patch/season/channel | 任意子 revision 缺失、错季或混态 |
| Gear catalog | 装备、来源、variant、bonus、gem/enchant/embellishment、crafted_stats、Catalyst overlay | 无 verified variant、缺 SimC option、错季来源进入正式候选 |
| Talent catalog | tree、hero tree、rules、import/export、encoding、community template revision | 旧 import code 被静默重解释、节点/edge/entry mismatch |
| SimC runtime | binary、commit、manifest、real SimC smoke、rollback | binary missing、profile parse failure、12.1 字段不支持 |
| Source pools | M+、raid、Delves、Prey Hunt、world source | S1 source pool 仍作为 S2 当前来源 |
| Reward rules | upgrade track、currency、vault、very rare、crafted max quality | 装等/货币/可升级条件无法解释 |
| Community templates | talent 80 hero slots、gear 40 specs、source status、winner freshness | S1 winner 被当成 S2 推荐、fallback 冒充真实样本 |
| Stat weights | scale factors、sample count、SimC build、translation status | S1 权重继续输出 S2 强建议 |
| PVE ranking | Archon/WCL/Raider.IO season/source timestamp | 旧排行继续显示为当前赛季 |
| Chickenbro evidence | allowedNumbers、profile baseline、WCL/SimC evidence refs | 使用 stale 数字生成强结论 |
| Terminology | zh_CN 术语 canonical name、alias、source、termRevision | LLM 或前端猜译进入正式展示 |
| User templates | gear/talent/simc runtime revision 绑定、migration state | 历史模板被静默重解释 |
| Frontend | season state、empty/partial/blocker UI、no PTR query bypass | 空列表、旧内容、错误 ready 状态 |
| Ops | backup、job budget、locks、restart、smoke、rollback | 同步任务互相踩锁、无回滚路径 |

## 用户资产迁移

所有用户资产需要显式绑定保存时 revision：

- 装备模板：`seasonRevision`、`gearCatalogRevision`、`simcRuntimeRevision`、gear signature。
- 天赋模板：`seasonRevision`、`talentCatalogRevision`、`schemaRevision`、`simcBuild`。
- SimC 任务：`seasonRevision`、`gearCatalogRevision`、`talentCatalogRevision`、`simcRuntimeRevision`、scenario、profile signature。
- Chickenbro / AI 报告：evidence revision、allowedNumbers revision、source timestamps。

S2 active 后，S1 资产状态建议：

- `historical`：可查看原结果。
- `needs_migration`：可引导用户重建或重新导入。
- `simc_only_external`：旧官方 import code 仍可由 SimC 接受，但不能可视化成当前 WebSim tree。
- `blocked`：缺装备、缺天赋、缺 SimC 字段或旧来源已失效。

不允许把旧资产静默升级为 S2 verified。

## Health and Admin Surface

`/api/data/health` 和后台 gates 需要新增或聚合：

- active `seasonRevision`。
- staging/PTR `seasonRevision`。
- 各子 revision 的 status、checkedAt、sourceRefs。
- cross-revision compatibility status。
- top blockers，按 gear / talent / SimC / source pool / reward rule / community / stat weights / frontend 分类。
- cutover readiness：`ready`、`partial`、`blocked`、`staging_only`。
- rollback target 和上一版 active manifest。

正式小程序只消费 active retail health。后台可以显示 PTR/staging health，但不能让正式用户绕过 active pointer。

## Launch-Day Job Profile

大版本当天不要把所有任务都切成 full sync。建议分层：

- 必跑：live metadata revalidation、SimC runtime smoke、gear/talent serializer matrix、`/api/data/health`。
- 分批跑：gear variant probe、community gear templates、stat weights、PVE ranking。
- targeted 跑：Raider.IO / WCL 只针对缺口 spec/hero/slot。
- 延后跑：非核心新闻、低优先级图标/描述润色、深层历史归档。

所有任务要记录 run id、source count、duration、lock wait、blocker summary。共享锁任务必须确认串行顺序，避免全量同步互相阻塞。

## Frontend Cutover States

前端至少需要表达：

- S1 正常 active。
- S2 数据准备中。
- S2 已切换但部分模块 pending。
- 某模板为历史赛季模板。
- 某模块因装备、天赋、SimC、社区样本或 API 缺口不可模拟。
- 当前结果基于历史 SimC runtime，不代表当前赛季。

前端不判断赛季规则，不硬编码 itemId / talentId / dungeon name 过滤。所有状态来自后端 manifest 和 health。

## Final Go / No-Go Checklist

切 active 前必须逐项确认：

- [ ] active S1 manifest 可回滚。
- [ ] inactive S2 manifest 完整。
- [ ] Battle.net live metadata / journal / item-set 完成复核。
- [ ] Gear catalog verified / partial / blocked 状态清楚。
- [ ] Talent catalog verified / partial / blocked 状态清楚。
- [ ] SimC runtime verified，记录 source commit 和 binary path。
- [ ] Catalyst `redirected_base_stats` fixture 通过。
- [ ] M+ / raid / Delves / Prey Hunt source pool 对齐 S2。
- [ ] Upgrade / currency / vault rule 对齐 S2。
- [ ] Community templates 不复用 S1 winner 作为 S2 verified。
- [ ] Stat weights / PVE ranking / Chickenbro 数字证据已 stale-closed 或重建。
- [ ] 术语 catalog 已绑定 `terminologyRevision`，高影响中文名缺口进入 health / admin。
- [ ] 历史用户模板不会被静默重解释。
- [ ] `/api/data/health` 没有 unknown 混态。
- [ ] `/health`、核心 WebSim API、SimC submit smoke 通过。
- [ ] 前端可见状态明确，不展示错季内容。
- [ ] Rollback pointer 和备份路径已记录。

任意一项失败时，不切 active。可以继续保留 S2 staging / inactive revision 供内部测试。

## 后续实施提示

后续实现时应先补测试和只读检查：

1. S1 active + S2 inactive 并存，正式 API 只读取 S1 manifest。
2. S2 manifest 中 gear/talent/SimC 任意一项错季时，health 标记 blocked。
3. S1 社区模板在 S2 active 下进入 historical / stale，不可应用为 current verified。
4. S1 SimC 任务回放保留旧 runtime，rerun 生成新任务。
5. Frontend bootstrap 能拿到 season state，并展示准备中 / 历史模板 / blocker 状态。
6. Rollback manifest 切回后，核心 API 和 health 恢复上一版 active 组合。
