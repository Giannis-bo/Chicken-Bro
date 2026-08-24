# S2 有限可选目录与社区 Exact 模拟设计

状态：`Candidate v73 已验证并发布到 Active Manifest generation 41；用户已确认最新微信预览可收尾；closure packet 对未单独录证的路径保留显式 waiver`

确认日期：`2026-08-13`

当前事实入口：[project-state.json](../project-state.json)、[roadmap.md](../roadmap.md)、
[Harness](../harness.md)、[装备模拟目标架构](2026-07-28-equipment-simulator-target-architecture.md)、
[Observed Build Registry](2026-07-23-observed-build-registry-design.md)、
[v73 live smoke](../../artifacts/releases/2026-08-21-s2-equipment-library-candidate-v73/live-smoke-v1.json)。

## 1. 用户目标与现实约束

本设计接受一个明确前提：当前无法建立并持续证明“完整 S2 装备 Universe”。产品不再以
全量覆盖作为玩家可用模拟的前置条件，而是提供两个严格隔离的能力面：

1. **有限可选目录（List A）**：只发布能够选择、编辑并在固定 SimulationCraft runtime
   下执行的装备、轨道和强化选项。List A 的公开 SimC readiness 必须为 `100%`，但不宣称
   覆盖全部 S2 装备。
2. **社区导入 Exact 实例**：Raider.IO 模板中不属于 List A 的真实观察装备可以按原始实例
   展示、计算属性并参与 SimC；它保持只读，不进入替换列表，也不得扩张 List A。

玩家应能完成以下路径：导入含非 List A 武器的社区模板，看到该武器及整套属性，直接模拟；
也可以用 List A 武器替换它、撤销替换、恢复原社区模板，并把修改后的配装保存为派生模板。

## 2. 已确认的产品边界

- 至暗之夜 S2 装备库的有限事实范围固定为四个逻辑来源：团本（包括巢穴）、大秘境、制造业和
  套装。地下堡、狩猎、世界 Boss、普通地下城、Great Vault 和世界内容明确排除。每个候选必须有
  来自官方 API 快照的范围归属或显式排除 reason，不能因 SimC 可执行或社区观察而越过该边界。
- 产品范围由版本化的 `S2ProductContentScopeV1` 决定，官方 API 只负责验证该选择对应的游戏事实。
  这份策略可以选择官方对象 ID 和产品来源标签，但绝不能提供副本名、Boss、难度、掉落、轨道或 item
  等游戏事实；这些字段一律从同一次官方快照解析。选择与事实必须分层，不能把“产品只纳入什么”误写成
  “官方 API 只存在什么”。

  | 产品来源 | 已确认的 S2 内容选择 | 官方验证条件 | 玩家可见归类 |
  | --- | --- | --- | --- |
  | 大秘境 | 8 个 Journal Instance：`1030`、`1041`、`1202`、`1304`、`1309`、`1311`、`1313`、`1322` | 原始类别为 `DUNGEON`，且存在 `MYTHIC_KEYSTONE` 难度 | 塞塔里斯神庙、诸王之眠、红玉新生法池、密谋小径、夺目谷、纳洛拉克的洞穴、虚空之痕竞技场、毒牙祭坛 |
  | 团本（包括巢穴） | Journal Instance `1317` 的 Encounter `2849`，以及 Journal Instance `1320` 的全部官方 Encounter | 巢穴与团本都必须由官方回包确认 `RAID` 与 `MYTHIC`；巢穴原始来源类型仍保留为 `lair` | 潮缚石窟巢穴、烈毒之渊；产品层统一归入团本 |
  | 制造业 | 官方专业/配方/产物关系中满足神话终点条件的记录 | 每个配方、产物与轨道关系均须由官方 API 闭合 | 制造业 |
  | 套装 | S2 官方 Item Set、职业归属、套装部位和套装效果关系 | 每个 set membership、部位和效果必须由官方 API/固定事实快照闭合 | S2 套装；作为独立 membership 来源，可与团本/巢穴/大秘境/制造业来源并存 |

  因而，S2 团本侧纳入的副本只有**潮缚石窟**和**烈毒之渊**：前者在产品上属于团本范围内的巢穴，
  但底层仍保留 `lair` 原始来源。官方 Journal 若还列出其他原始 `RAID` 内容，它们是可审计的官方目录行，
  但一律记为 `OUT_OF_SCOPE_PRODUCT_CONTENT`，不会因可达史诗难度而自动进入 List A。套装不是另一个
  掉落副本，而是独立的装备库 membership 维度；套装转换必须保留原始装备身份、绿字和特效。

  副本的 `MYTHIC` 或 `MYTHIC_KEYSTONE` 难度只验证来源归属；每件具体装备仍必须由官方 item/轨道
  关系单独证明最终可达神话终点。不能把副本难度、Great Vault、SimC 成功或社区观察当作这项 item-level
  轨道证明。
- List A 是**有限但可信的可选目录**，不是完整装备数据库，也不是官方 S2 Universe 声明。
- List A 只能从 `OfficialApiFactSnapshot` 中 `verified` 的 Item、BrowseVariant、轨道和强化
  事实派生；产品准入策略只能筛选，不得补全或发明游戏事实。
- List A 中所有最终公开 Item、BrowseVariant、轨道和强化兼容关系必须可生成确定的 SimC 输入。
- 社区导入装备不要求属于 List A；整套模板是否可模拟取决于每个槽位能否解析为
  `exact-ready`，而不是取决于 Catalog membership。
- 非 List A 社区装备是只读封存实例：可查看、计算、模拟和整槽替换；不可修改轨道、宝石、
  附魔、美化或制造属性。
- 社区实例被替换后不会出现在候选列表中。玩家只能撤销当前替换或恢复/重新导入原社区模板。
- SimC runtime 只证明固定版本下的属性、效果、序列化与可执行性，不证明官方来源、获取关系
  或完整赛季覆盖。
- Raider.IO 只证明某个角色在某个观察时间点暴露了该装备配置，不授予可浏览目录 membership。
- “社区观察实例可执行”与“官方 API 验证的 List A 成员”是两个不同承诺：前者不得升级为后者，
  即使它的 SimC 运行成功。
- 不使用相似装备、同 itemId 的最高轨道、默认 bonus、S1 数据或前端推断补齐 Exact 实例。
- 保持现有 Taro 路由、页面结构、导航和视觉合同；实现只在现有装备卡片、详情、替换和模板
  流程中表达已确认的只读状态与错误，不另开入口或重做布局。

## 3. 方案比较与选择

| 方案 | 做法 | 结论 |
| --- | --- | --- |
| 导入即扩张 List A | 社区装备解析成功后自动加入替换目录 | 拒绝；会让目录随观察样本漂移，并把“能执行”误写成“可公开选择” |
| 严格双池隔离 | List A 负责浏览与编辑；社区实例进入独立 Exact Registry | **采用**；边界清晰，复用现有 BrowseVariant / ExactItemInstance 架构 |
| 全局社区观察池 | 另建一个可搜索但不可直接选择的社区装备目录 | 后续；第一版没有必要增加第二套浏览产品 |

## 4. 核心实体与身份

### 4.1 `OfficialApiFactSnapshot`

职责：封存唯一可裁决的 S2 游戏事实输入，而不是生成玩家可用模拟。

每个不可变快照至少记录官方 API endpoint、namespace、region/locale、capture 时间、响应内容 hash、
解析器 revision 与 API-build/版本标识；其事实闭包包括 ItemDefinition、范围归属、来源/副本关系、
progression/轨道、套装、制造输出和强化选项中 API 已能确认的字段。它先以
`S2ProductContentScopeV1` 选择四类范围内的 8 个大秘境、潮缚石窟的唯一巢穴 Boss、烈毒之渊、制造业
和 S2 套装 membership，再由
官方 API 验证每个选择的来源、Encounter、难度与神话终点关系；地下堡、狩猎、世界 Boss 及未选择的
当前赛季内容必须进入显式排除账本。

官方 API 缺少、冲突或无法唯一解析的游戏事实保持 `UNVERIFIED`，不得由 SimC、Raider.IO、
相似 item、旧赛季数据或前端推断补齐；此类记录不能进入 List A。该约束不阻止社区快照以
`community_observed` 身份被保存和尝试执行，但不会把观察事实改写成官方事实。

### 4.2 `SelectableCatalogRelease`（List A）

职责：封存一个有限、可浏览、可编辑且全部 SimC-ready 的公开目录。第二阶段只能生成同构但不可公开的
`SelectableCatalogCandidate`；只有第三阶段的逐变体 SimC probe 全部通过后，才可提升为
`SelectableCatalogRelease`。

内容至少包括：

- `ItemDefinition` membership；
- 每件装备的公开 `BrowseVariant` 与明确 progression state；
- itemId、slot、ilevel、bonus IDs、静态属性和 serializer input；
- 宝石、附魔、美化、制造属性等 `EnhancementOption`；
- 每条公开 `(browseVariantKey, enhancementOptionKey)` 兼容边；
- 被排除候选的数量与具体 reason code；
- `officialApiFactSnapshotRevision`、Catalog builder 与规则 revision；
- 最终发布所绑定的 Profile Compiler 和固定 SimC runtime identity。

List A 的 membership 由版本化产品准入策略和候选构建器拥有，但它们只能选择
`OfficialApiFactSnapshot` 中已验证、且在范围策略内的事实。固定 SimC runtime 只负责
materialization 与执行门禁，不能补上官方来源、赛季获取关系、轨道或目录 membership。
缺少官方游戏事实的记录即使 SimC 能运行，也只能作为 `community_observed` Exact 实例保留，
不得作为“可模拟但来源未知”的 List A 条目发布。

### 4.3 `CommunityTemplateSnapshot`

职责：不可变保存 Raider.IO 模板的来源身份、角色/专精上下文、观察时间、原始装备字段和内容
哈希。解析、替换或保存派生模板均不得修改原始快照；访问仍受现有 owner/public-template
授权边界约束，公共 payload 不暴露不必要的角色身份字段。

### 4.4 `ImportedExactItemInstance`

职责：保存社区模板或个人模板中的具体装备实例。

```text
exactItemInstanceKey = sha256(canonical(
  itemId, bonusIds, itemContext, progressionState, ilevel,
  gemIds, enchantId, craftedStats, embellishmentIds
))
```

每条记录还必须绑定：

- `communityTemplateSnapshotId` 与槽位；
- `truthScope=community_observed` 与原始 observation hash；
- 本次解析所用 `officialApiFactSnapshotRevision` 和 `officialFactStatus=verified|UNVERIFIED`；
- `exactResolverRevision`；
- `simcRuntimeRevision`；
- `membershipKind=imported_exact`；
- `editable=false`；
- 原始观察字段、规范化字段、属性结果、serializer input 与 problems。

相同 canonical 实例可以跨模板去重；原始模板 provenance 仍按引用逐条保留。Exact Registry 是
追加式注册表，不是 Browse Catalog。任何 exact row 都不能创建或扩张 `ItemDefinition` 或
`BrowseVariant` membership。这里的 `itemContext` 是导入载荷中的装备实例上下文字段；角色、专精、
等级和战斗配置属于 CommunityTemplate、ResolvedLoadout 或 SimulationSnapshot 上下文，不进入装备
实例主键。角色上下文会影响计算时，其结果缓存必须另行绑定对应的 profile context identity。

`exactItemInstanceKey` 只标识 canonical 装备配置；解析/属性/执行结论必须另行绑定
`truthScope`、官方快照、Resolver、规则、Profile Context 与 runtime revision。社区实例可得到
`simcReadiness=ready`，但这绝不把其 `officialFactStatus=UNVERIFIED` 升级为官方目录事实。

### 4.5 `MixedSelectionIntent`

完整配装的每个槽位只能引用以下联合类型之一：

```text
{ kind: "browse", browseVariantKey, enhancementSelection }
{ kind: "imported_exact", exactItemInstanceKey, readonly: true }
```

`browse` 槽位允许使用后端返回的合法强化选择；`imported_exact` 槽位必须完整重放原始精确实例，
不接受字段级编辑。替换 imported slot 时只能整槽切换为一个 List A `browse` intent。

### 4.6 `ResolvedLoadout` 与 `SimulationSnapshot`

`MixedLoadoutResolver` 不要求所有槽位属于 List A，只要求所有槽位最终解析为 exact-ready，
并通过槽位、职业、唯一装备、双持、套装强化数量和整套规则。只有 ready 的
`ResolvedLoadout` 才能生成不可变 `SimulationSnapshot`。

Snapshot 永久绑定实际 canonical SimC 输入、List A/规则/Resolver/Compiler/runtime revisions 和
结果身份；后续 Catalog 或 runtime 更新不得重写历史结果。

## 5. 事实归属与有界承诺

| 问题 | Owner | 允许声明 | 禁止升级 |
| --- | --- | --- | --- |
| S2 item/variant/轨道/来源/套装/制造/强化的游戏事实 | `OfficialApiFactSnapshot` | 已捕获且 `verified` 的官方事实 | SimC、Raider.IO、旧赛季或前端补齐 |
| 哪些官方事实可在替换列表选择 | 范围策略 + `SelectableCatalogRelease` | 当前 List A membership | 社区样本或 SimC 成功自动扩张 List A |
| List A 装备如何序列化和执行 | 固定 SimC runtime + Profile Compiler | 当前 manifest 下 `simc-ready` | 推导官方来源或全 S2 覆盖 |
| 哪些强化可编辑 | versioned Enhancement/Loadout rules | 已发布兼容边与整套约束 | 依赖 SimC 宽松语法自动放开任意组合 |
| 社区玩家实际穿戴什么 | `CommunityTemplateSnapshot` | 指定时间点的观察配置 | 推导 List A membership 或当前官方合法性 |
| 社区装备能否重放 | Exact Resolver + 固定 SimC runtime | 指定观察实例的 `executionStatus` | 用 BrowseVariant 或相似装备补值，或升级为官方事实 |
| DPS 与报告数字 | SimC Runner/result parser | 指定 Snapshot 与 runtime 的结果 | 把 profile-ready 表述为 DPS 已验证 |

为避免 SimC 内部隐藏多来源，正式候选与 Exact 解析必须关闭默认外部 item fallback，绑定固定
本地 SimC binary、数据 bundle 和配置 hash 所组成的 runtime identity。需要外部字段时必须经过独立、
显式、版本化输入，不得由一次 SimC 运行临时联网补入并写回 Catalog。

## 6. 用户路径

### 6.1 List A 手动配装

1. 替换列表只返回当前 `SelectableCatalogRelease` 的 BrowseVariant。
2. 玩家选择装备后，后端返回该装备可编辑的 progression 与强化兼容项。
3. 前端提交选择意图；后端重新 Resolve，成功后更新当前 confirmed loadout。
4. 保存后生成结构化用户模板；只有整套 ready 才可进入 SimC。

### 6.2 导入社区模板

1. 保存不可变 `CommunityTemplateSnapshot`。
2. 逐槽命中或创建 `ImportedExactItemInstance`；未完成时保留原始展示字段和状态。
3. 模板页面始终显示原始观察装备与强化，并标记“社区观察 · 只读”；只有
   `attributeStatus=ready` 时才显示派生属性。`simcReadiness=ready` 不得展示为“官方已验证”。
4. 整套属性计算包含 ready 的 imported exact；不得用 List A 代表项覆盖其实际 rank 或属性。
5. 所有槽位 exact-ready 且整套规则通过后，允许生成 Snapshot 并模拟。

### 6.3 替换、撤销、恢复与保存

- 打开一个 imported exact 槽位时，顶部显示当前只读装备；下方候选仅来自 List A。
- 玩家选择 List A 装备后，该槽位变为 `browse` intent；原始 Snapshot 不变。
- 玩家可以撤销本次替换，或整套恢复/重新导入原社区模板。
- 保存修改结果时创建用户派生模板并记录 `derivedFromCommunityTemplateId`。
- 未被替换的 imported slots 继续引用只读 exact keys；被替换的原装备不进入 List A，也不留在
  当前派生 loadout 中。

### 6.4 失败修复

解析失败的模板仍可查看并保存草稿。页面必须定位具体槽位和问题；玩家可以用 List A 装备
整槽替换来解除该 blocker。整套 ready 前禁止提交 SimC。

## 7. 正交状态与错误合同

每件装备分别记录：

- `truthScope`: `official_catalog | community_observed`；
- `officialFactStatus`: `verified | UNVERIFIED`；
- `membershipKind`: `selectable_catalog | imported_exact`；
- `editable`: `true | false`；
- `resolutionStatus`: `ready | pending | partial | blocked | stale`；
- `attributeStatus`: `ready | pending | partial | blocked | stale`；
- `simcReadiness`: `ready | pending | partial | blocked | stale`。

状态含义：

- `ready`：精确字段、静态属性、效果、serializer 与固定 runtime 执行合同完整；
- `pending`：已接收并异步解析，只展示原始观察信息；
- `partial`：可识别和部分展示，但缺 exact 字段或效果支持；
- `blocked`：确定性失败，不得参与模拟；
- `stale`：绑定旧 runtime/Resolver，需要重新解析后才能再次模拟。

`ready` 只描述其所属维度的完成状态，不能覆盖其他事实维度：例如社区实例可以
`simcReadiness=ready`，但其 `truthScope=community_observed` 和 `officialFactStatus=UNVERIFIED`
仍必须原样返回并在用户界面可见。

至少使用以下具体问题码：

- `EXACT_VARIANT_FIELDS_INCOMPLETE`；
- `SIMC_ITEM_UNAVAILABLE`；
- `SIMC_EFFECT_UNSUPPORTED`；
- `IMPORTED_ENHANCEMENT_INVALID`；
- `SIMC_RUNTIME_REVISION_STALE`；
- `LOADOUT_LEGALITY_BLOCKED`。

接口必须同时返回问题槽位、字段、原始来源和可恢复动作。不得只返回“数据异常”，也不得把
一个槽位的失败提升为其他槽位的来源或属性结论。

## 8. 发布验证矩阵

### 8.1 List A 强门禁

候选发布必须满足：

1. 每个公开 BrowseVariant 都能生成确定的 Exact 实例。
2. 对每个适用的职业、专精、槽位、item 和 BrowseVariant 完成 Profile 编译与固定 SimC smoke。
3. 每条公开 `(BrowseVariant, EnhancementOption)` 兼容边至少完成一次真实组合验证。
4. 美化数量、唯一装备、双持、插槽和互斥等全局限制使用边界与 pairwise 组合测试；不穷举无
   新语义的全量笛卡尔积。
5. 每个产品支持 SimC 的专精至少完成一套完整 Loadout 模拟；产品不支持的专精必须在创建任务
   前确定性返回 `unsupported`。
6. 公开 List A membership 中不得出现 `pending/partial/blocked/stale`。

发布报告必须记录：

```text
itemCount
browseVariantCount
enhancementOptionCount
compatibilityEdgeCount
officialScopeCandidateCountByKind
officialScopeAdmittedCountByKind
excludedItemCountByReason
publicSimcReadyRate = 100%
```

`publicSimcReadyRate=100%` 只描述 List A 的公开合同，不得与 S2 Universe coverage 混为一个指标；
官方范围候选、纳入和排除指标共同构成有限范围内的覆盖解释，不能用一个“100%”掩盖任意缩小的 List A。

### 8.2 社区模板门禁

- 已进入公开社区模板列表的每个模板必须逐槽 exact-ready、整套 Resolver 通过，并在同一
  SimulationManifest 下真实执行成功。
- 任意新导入模板允许 `pending/partial/blocked`，不承诺必然成功；只在完整解析后开放模拟。
- 任意 imported exact 的成功率、公开社区模板 ready 率和 List A ready 率必须独立报告。

### 8.3 真实用户验收

候选至少覆盖四条真实微信路径：

1. 从 List A 选择装备、编辑强化、保存并模拟；
2. 导入含非 List A 武器的社区模板，展示属性并成功模拟；
3. 用 List A 武器替换只读装备，撤销、恢复原模板、保存派生模板并重新模拟；
4. 导入无法解析的外部装备，准确显示问题槽位，允许草稿保存和整槽替换，但禁止 SimC。

历史验收、HTTP 200、单一代表项 smoke 或候选构建成功均不能替代本轮用户验收。

当前 v73 的后端验证已经覆盖正式 Active Manifest 下的装备库展示数据、社区模板导入和 16 槽混合
替换 Resolve；小程序 typecheck、Taro 测试、装备模板/替换 Node 测试和 `build:weapp` 也已通过。
用户已确认最新微信开发者预览“OK，可以先收尾”，因此本轮 closure 记录装备展示、应用替换和属性概览
路径为用户接受；社区模板导入与登录态命名模板保存没有在本轮单独形成逐路径记录，分别以用户明确收尾授权
记为 `not_run_user_waived`，不冒充已执行。

## 9. 统一发布身份与回滚

活动发布使用一个不可变身份：

```text
SimulationManifest = hash(
  officialApiFactSnapshotRevision,
  selectableCatalogRevision,
  gearRuleRevision,
  enhancementOptionRevision,
  exactResolverRevision,
  profileCompilerRevision,
  simcRuntimeRevision
)
```

社区 Snapshot 与 Imported Exact Registry 不扩张 Manifest 内容；每条记录分别绑定其来源 hash、观察时间、
官方快照、Resolver、Profile Context 和 SimC runtime。它们位于独立的 S2 追加式池，当前 v73 通过
`gearExactRegistryRevision` 与 Active Manifest generation 41 一起绑定发布。后续 SimC 或事实更新必须
构建并验证新的 List A candidate，再原子提升完整依赖向量；不得只替换二进制或原地改写已发布实例。

回滚规则：

- 候选失败不修改活动指针；
- 上线异常通过 CAS 将完整 SimulationManifest 回滚到上一组 Catalog/规则/Compiler/runtime；
- 保留上一 runtime 及其可复核身份，确保历史 Snapshot 和报告仍可解释；
- Exact Registry 追加新 runtime 下的解析记录，不覆盖旧实例；
- 已执行 SimulationSnapshot 永不重写；
- 回滚不删除社区原始快照、用户模板或历史报告。

## 10. 可观测性、安全和资源边界

`/api/data/health`、候选 evidence 与运维日志必须独立暴露：

- List A counts、排除原因与 `publicSimcReadyRate`；
- 官方范围候选、纳入、排除及 `UNVERIFIED` 数量（按团本/大秘境/制造业/套装分类）；
- 公开社区模板 ready/blocked 数量；
- 任意新导入 Exact 的 ready/pending/partial/blocked/stale 数量与 top blockers；
- 当前 Catalog/Rule/Resolver/Compiler/SimC revisions；
- 最近构建、解析和 runtime 漂移时间。

Raider.IO 与客户端输入均视为不可信结构化输入：限制模板大小、槽位数、数组长度和字段类型；
只由后端 Profile Compiler 输出 SimC 文本，不接受外部任意 profile 片段。日志和公共 payload 不得
泄露凭据或不必要的角色隐私字段。

Exact 缓存按 canonical key 去重。被用户模板或 SimulationSnapshot 引用的记录必须保留；未引用
缓存只能按独立、可审计的保留策略清理，不得影响原始社区 Snapshot 或历史结果。

## 11. 分阶段交付

本设计拆为三个顺序明确的子项目，每个子项目单独拥有 Harness packet、验证和回滚合同：

1. **S2 官方事实快照**：先冻结 `S2ProductContentScopeV1`，再只由官方 API 建立四类范围内 8 个大秘境、
   潮缚石窟唯一巢穴 Boss、烈毒之渊、制造业和套装 membership 的 Item/variant/轨道/来源/套装/制造/强化事实、范围候选
   与排除账本；不创建公开 List A、不运行 SimC probe、不切 Active Manifest，也不开放玩家模拟。
2. **S2 装备解析与候选目录**：以第一阶段快照构建不可公开的 List A candidate、兼容边、
   独立 S2 Imported Exact Registry、Mixed Resolver 与替换/撤销/恢复/派生保存；不运行玩家 SimC
   任务，不切 Active Manifest。
3. **S2 SimC 联动与用户验收**：绑定固定本地 runtime、逐变体 probe、Profile Compiler 与任务执行；
   只有此阶段完成 `publicSimcReadyRate=100%` 后才可形成完整 SimulationManifest、候选部署、四条
   真实微信路径、原子切换和回滚。

后续实现计划必须按三个子项目拆分，不能恢复为一个大而全的切换任务；v73 已完成三阶段的数据封存、
release gate、Active Manifest 发布和后端 smoke，用户已确认本轮最新预览可收尾，未单独录证的路径仍受
closure packet waiver 边界约束。候选输出在完成对应门禁前仍不能被当作玩家可用模拟或 Active Manifest。

## 12. 与旧 S2 candidate 的关系

2026-08-12 的 S2 End Game candidate、设计和 evidence 继续作为 `blocked` 历史事实：官方 capture
capped，未修改 Active Manifest、生产数据库或 runtime 指针。它不再定义新方案的完成口径，
也不得被直接 promotion、续跑或改名为 List A。

新工作必须从本设计建立独立 task-scoped 计划与候选身份。generation 35 仍是 v1 历史基线，S1
活动链与 provider/worker disabled 状态保持独立；S2 当前正式指针为 generation 41。全局
`/api/data/health` 仍为 `partial`；用户已确认最新预览可收尾，但社区导入与 authenticated 保存的逐路径
记录分别保持 `not_run_user_waived`，不能升级为独立 accepted 证据。

任何后续 S2 导入池、数据库迁移或 CAS 回滚都必须在新的独立 Harness packet 中绑定候选身份和
回滚证据，不得修改 generation 41 的不可变 release 内容或绕过 Active Manifest owner。
