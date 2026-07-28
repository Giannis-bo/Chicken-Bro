# Equipment Simulator Track Authority Blocker Resolution

状态：`设计已批准；实现与生产只读重跑完成；Phase 1 仍阻塞`

## 1. 用户场景与问题

玩家在装备模拟中选择一件当前赛季 PVE 装备时，需要看到真实存在且可执行的装备
状态：

- 普通勇士、英雄、神话装备只显示该轨道最高等级；
- 虚空晋升作为独立可选状态出现，但不伪装成普通升级轨道；
- 制造装备先选择合法装等状态，再选择制造副属性；
- 最终选择能够被后端确定性解析为合法 SimulationCraft 输入。

当前活动 Gear Release 的 1,678 条 Browse 行混合了普通升级轨道、虚空晋升状态和
制造属性组合。旧生产器只写 `difficultyKey`、`itemLevelTrack` 和装等，没有专用
轨道 rank。Phase 0 又把所有 Browse 行统一要求为正整数 rank，因此 1,678 条全部
无法映射。

这不是简单的字段漏写。统一补 `rank=6` 会把虚空晋升和制造品质伪装成普通
`6/6` 轨道，也会让同一制造装备的六组副属性成为六个并列“最高 rank”候选。

## 2. 已验证事实

### 2.1 当前生产分布

2026-07-28 对活动 Manifest generation 24 的只读 PostgreSQL 聚合确认：

| 旧行语义 | 行数 | 结构 |
| --- | ---: | --- |
| 普通升级轨道 | 1,116 | `champion`、`hero`、`myth` 各 372 条 |
| 虚空晋升 | 124 | `void_upgrade` |
| 制造神话品质 | 324 | 54 件装备 × 6 组制造副属性 |
| 制造虚空晋升 | 114 | 19 件装备 × 6 组制造副属性 |

全部 1,678 条 Browse 行的 `bonus_id` 都为空，因此不能从 bonus IDs 反推出轨道或
rank。当前 48 条静态属性缺口仍是独立 blocker，不由本设计掩盖。

### 2.2 外部规则事实

- 暴雪 Midnight 更新说明把当前普通升级轨道的满级描述为 `6/6`：
  <https://news.blizzard.com/en-us/article/24244646/midnight-content-update-notes>
- 暴雪 12.0.5 更新说明明确存在 `Myth 1/6`，并把 Ascendant Voidforged 描述为
  fully upgraded Hero、Myth 或最高品质 Radiance Crafted 武器/饰品之后的额外
  晋升：
  <https://news.blizzard.com/en-us/article/24271855/12-0-5-content-update-notes>

上述证据支持普通轨道的 `maxRank=6` 和虚空晋升的“额外转化状态”语义，但不单独
证明仓库硬编码的全部最高装等。精确装等仍必须由版本化规则记录绑定来源和可信状态。

## 3. 方案比较

### 方案 A：所有 Browse 行统一补 `rank=6`

优点是改动最小。缺点是制造品质和虚空晋升不属于普通 6 级轨道，且 438 条制造行
仍会形成并列最高 rank。该方案会把实现假设写成 canonical truth，拒绝采用。

### 方案 B：BrowseVariant 全部取消 rank

优点是能够绕开当前缺字段。缺点是普通勇士、英雄、神话会失去真实升级等级语义，
ExactItemInstance 也无法可靠保留英雄 3/6 等中间实例。该方案削弱用户承诺，拒绝
采用。

### 方案 C：按 progression kind 使用判别联合

普通升级轨道要求 rank；制造品质和虚空晋升使用各自的 canonical 状态，不伪造
rank。制造副属性从 BrowseVariant 中拆回 EnhancementSelection。该方案保留完整
SimC 表达能力，并与游戏规则和现有目标架构的信任边界一致，因此采用。

## 4. 目标合同

### 4.1 `ProgressionState`

BrowseVariant 和 ExactItemInstance 共用以下判别联合：

```text
ProgressionState =
  UpgradeTrackProgression
  | CraftedQualityProgression
  | AscendantProgression
```

#### `UpgradeTrackProgression`

适用于 `champion`、`hero`、`myth`：

```json
{
  "kind": "upgrade_track",
  "trackKey": "hero",
  "rank": 6,
  "maxRank": 6
}
```

- `rank` 和 `maxRank` 必须是正整数；
- BrowseVariant 必须满足 `rank == maxRank`；
- ExactItemInstance 可以保留 `1..maxRank` 的实际中间等级；
- rank 只能来自当前赛季 Track Authority，不能从榜单排名、名称、tooltip 或装等
  反推。

#### `CraftedQualityProgression`

适用于最高品质制造装备：

```json
{
  "kind": "crafted_quality",
  "trackKey": "myth",
  "qualityKey": "radiance_max"
}
```

- 不包含 `rank` 或 `maxRank`；
- 制造副属性不参与 BrowseVariant 身份；
- 玩家选择的 `crafted_stats` 进入 EnhancementSelection；
- 选择完成后由 Resolver 计算该制造实例的完整属性和 SimC options。

#### `AscendantProgression`

适用于普通或制造装备的虚空晋升状态：

```json
{
  "kind": "ascendant",
  "trackKey": "void_upgrade",
  "originKind": "upgrade_track"
}
```

或：

```json
{
  "kind": "ascendant",
  "trackKey": "void_upgrade",
  "originKind": "crafted_quality"
}
```

- 不包含伪造的 `rank=1`、`rank=6` 或 `maxRank`；
- 必须携带当前赛季的 eligible slot/source/origin 证据；
- 前端仍只看到一个独立“虚空晋升”变体，不增加开关。

### 4.2 `TrackAuthorityRecord`

后端新增一个纯、版本化的规则对象，作为 progression 解释的唯一 owner：

```text
TrackAuthorityRecord {
  seasonRevision
  ruleRevision
  progressionKind
  trackKey
  itemLevel
  maxRank?
  eligibleSourceTypes
  eligibleSlots
  eligibleOriginKinds
  sourceRefs
  evidenceStatus
}
```

规则要求：

- `upgrade_track` 必须有 `maxRank`；
- `crafted_quality` 和 `ascendant` 禁止写 rank；
- `itemLevel` 必须是正整数并绑定版本化证据；
- 不满足来源、部位或 origin 条件的虚空晋升保持 `blocked`；
- `evidenceStatus != verified` 的规则不得生成 verified BrowseVariant。

第一步只在现有 Python 领域层建立纯规则合同，不新增数据库表、公开 API、runtime
pointer 或前端事实源。

### 4.3 BrowseVariant 身份

BrowseVariant 从统一的 `(catalogRevision, itemId, trackKey)` 最高-rank 假设修正为：

```text
browseVariantKey =
  sha256(canonical(catalogRevision, itemId, progressionState))
```

约束：

- 普通升级轨道每件装备每条轨道只保留 `rank == maxRank` 的一项；
- 虚空晋升每件 eligible 装备只保留一个 Ascendant 状态；
- 制造神话品质每件装备只保留一个 CraftedQuality 状态；
- 54 件制造装备的 324 行折叠为 54 个 BrowseVariant；
- 19 件可虚空晋升制造装备的 114 行折叠为 19 个 BrowseVariant；
- 六组制造副属性成为 EnhancementSelection 选项，不再制造六个 BrowseVariant。

BrowseVariant 必须继续携带装等、显式 bonus ID 数组、可验证的静态事实、来源和
evidence status。制造副属性导致的动态副属性只在选择后进入 resolved stats，不能
冒充未选择时的静态属性。

### 4.4 ExactItemInstance 身份

ExactItemInstance 的 canonical hash 改为包含完整 `progressionState`：

```text
exactItemInstanceKey =
  sha256(canonical(itemId, bonusIds, context, progressionState, ilevel,
                   gemIds, enchantId, craftedStats, embellishmentIds))
```

社区或个人实例仍必须保留真实 bonus IDs、装等和强化。普通轨道中间 rank 不得被
BrowseVariant 的最高 rank 覆盖；制造与虚空晋升实例也不得被强制补成普通轨道。

## 5. Phase 0 审计修正

Phase 0 纯审计按旧 `difficultyKey` 做结构分类；只有精确 season/rule authority
记录命中时才建立 progression 候选，只有该行的 authority、eligibility 和静态事实
全部有效时才计为 mapped：

| 旧 key | progression kind | rank 规则 |
| --- | --- | --- |
| `champion`、`hero`、`myth` | `upgrade_track` | 使用当前规则的 `maxRank`，Browse 必须为最高 rank |
| `crafted_myth` | `crafted_quality` | 禁止 rank，按装备折叠制造属性组合 |
| `void_upgrade` | `ascendant` | 禁止 rank，要求普通装备 eligibility |
| `crafted_void_upgrade` | `ascendant` | 禁止 rank，要求制造品质 origin 和 eligibility |

审计不得：

- 从 item level 猜轨道或 rank；
- 从通用 `payload.rank` 读取装备 rank；
- 把六组 `crafted_stats` 当作六个 BrowseVariant；
- 因 progression 修正而忽略 48 条缺静态属性；
- 改写 Gear Release、Manifest、Community Release 或生产数据。

修正后的生产只读报告必须分别输出：

- legacy Browse 行数；
- canonical BrowseVariant 候选数；
- 按 progression kind 的 mapped/blocked 数；
- 折叠掉的制造属性组合数；
- 缺 Track Authority、静态属性、eligibility 和 evidence 的具体计数；
- 数据库写入数、pointer generation 前后值和 active release 身份。

## 6. 用户可见结果

本 blocker resolution 不改变现有页面入口。未来 Catalog reader 接入后：

1. 玩家选择普通装备时看到勇士、英雄、神话最高级代表项；
2. eligible 武器、饰品或制造装备额外看到一个虚空晋升状态；
3. 制造装备不会重复出现六次，副属性在制造属性选择中单独选择；
4. 任何规则证据不足、静态属性缺失或 eligibility 不确定的状态保持
   `partial` / `blocked`，不会伪装成可模拟。

## 7. 影响边界

### `must_change`

- 当前目标架构中 BrowseVariant/ExactItemInstance 的 progression 合同；
- 一个独立的纯 Track Authority 领域模块及其单元测试；
- Phase 0 纯审计的 progression 分类、制造折叠和报告计数；
- 当前 Phase 0 报告、Phase 1 决策、project state、roadmap 和 Harness packet。

### `must_not_change`

- 微信小程序入口和已确认的“职业专精装备模拟 → 保存模板 → SimC”路径；
- PostgreSQL schema、Gear Release sealed rows、active Manifest pointer；
- 公开 API、Taro/兼容前端、Resolver、serializer 和 SimC runtime；
- Community Release、40 专精候选、资源峰值和运行时调用方等其他 blocker；
- Phase 1 授权状态；完成本修正后仍按重新审计结果决定，不能预设放行。

## 8. 失败、降级与回滚

- 未知 season/rule revision：Track Authority fail closed，相关 Browse 行为 blocked；
- 官方规则只证明 max rank、未证明精确装等：只认可 max rank，不升级装等证据状态；
- 虚空晋升 eligibility 不足：审计可以记录已识别的 canonical Ascendant 候选，
  但不得把它计为 mapped、verified 或发布态 BrowseVariant；
- 制造行无法无损拆分基础属性与动态副属性：保持 blocked，不选择任一属性组作为默认；
- 48 条缺静态属性：继续单独报告，不因本修正降级为成功。

本切片不写生产库，因此回滚是恢复纯合同、审计代码、文档和 evidence commit；不涉及
数据库恢复或 pointer rollback。

## 9. 验收证据

进入实现后必须按 TDD 证明：

1. 普通升级轨道缺少 verified authority 时 blocked，有 authority 时得到
   `rank=maxRank=6`；
2. crafted/ascendant progression 出现 rank 时被拒绝；
3. 324 条制造神话行折叠为 54 个 BrowseVariant，114 条制造虚空行折叠为 19 个；
4. 六组制造副属性保留为 EnhancementSelection 候选；
5. 48 条缺静态属性仍被准确报告；
6. Phase 0 PostgreSQL 会话继续显式 `BEGIN READ ONLY`，有界 timeout，写入数为 0；
7. 生产重跑前后 active Manifest generation 和 release 身份一致；
8. 当前其他 blocker 和 `allowedNextPlan=none` 不被静默清除；
9. Harness 定向验证和最终 CI full 使用本任务唯一 release packet。

单元测试通过、覆盖率、接口 200、旧截图或硬编码装等都不能单独授予 Catalog
migration readiness。

## 10. 实施顺序与停线

本文件批准后才编写独立实施计划。实施限定为：

1. 纯 Track Authority 合同；
2. Phase 0 纯审计和定向测试；
3. 去标识化生产只读重跑；
4. 当前控制面与本任务 Harness evidence。

如果需要新增 schema、公开 API、修改 staging producer、重封 Gear Release、切换
Manifest、写生产数据或进入 Phase 1，立即停线并另行决策。

## 11. 实施结果

2026-07-28 已完成并归档纯模块、read-only projection、progression-aware audit 和
CLI binding。精确提交
`2c7ff3a268a80a782431f288c3e23fbf2189f928` 在生产临时目录中通过 transient unit
执行，未修改 `/opt/wow-mini-program`，unit 已收集且临时目录已删除。

[生产只读报告](../../artifacts/releases/2026-07-28-equipment-simulator-track-authority-correction/runtime-readonly-audit.json)
记录：

- `legacyBrowseVariantTotal=1678`；
- `canonicalBrowseVariantTotal=1313`；
- `mappedBrowseVariantCount=1265`；
- `craftedEnhancementSelectionRowCount=438`；
- `collapsedCraftedVariantRowCount=365`；
- 唯一 catalog mapping 问题为
  `CATALOG_VARIANT_STATIC_STATS_MISSING=48`；
- Track Authority 精确绑定当前 season/rule 并为 `verified`；
- PostgreSQL source writes 为 `0`，活动 Manifest pointer 前后完全一致。

[机械 Phase 1 决策](../../artifacts/releases/2026-07-28-equipment-simulator-track-authority-correction/phase1-decision.json)
仍为 `blocked`、`allowedNextPlan=none`。Community Release 缺失、40/40 专精初始候选
blocked、资源峰值 unknown 和五个 unresolved runtime references 均未被本修正清除。
纯 Track Authority 仍没有运行时消费者。
