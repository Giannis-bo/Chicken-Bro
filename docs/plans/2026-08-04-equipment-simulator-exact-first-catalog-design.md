# 装备模拟 Exact-first 与来源受限 Catalog 设计

状态：`下一步`

性质：已确认的目标设计；不授予实施、候选发布、生产切换或恢复 Universe Goal 的权限。

## 1. 用户目标

玩家导入一套来自 SimulationCraft 插件或其他受支持输入的精确装备后，只要装备字段
完整、整套组合合法、关键效果得到当前 SimC runtime 的明确支持，就应能够保存、重载、
生成不可变快照并得到可复现的模拟结果。装备尚未进入公开换装目录，不能单独成为阻断
原因。

玩家浏览和更换装备时，只能看到已完成来源、赛季、变体、规则和 SimC 门禁的候选。
目录缺失、目录刷新失败或新装备尚在验证，不得污染已经可执行的 Exact 主链。

## 2. 决策与非目标

采用以下组合，而不是 Catalog 白名单优先或纯 Exact：

1. Exact-first 是模拟资格主链。
2. Catalog 是独立、有限、来源受限的可浏览候选集合。
3. 首期 Catalog 只承诺大秘境、团本和制造三个来源子集。
4. 未收录的精确装备允许被观察，但用户请求不得直接写入正式 Catalog。
5. 新目录内容只能通过候选构建、门禁、不可变 CatalogRevision 和原子切换发布。

本设计不承诺：

- 当前赛季全部 PVE 装备 Universe 已闭包。
- 插件导出能够证明玩家真实拥有对应装备。
- 一次成功的 SimC 解析或运行足以证明所有特殊效果均被准确建模。
- 通过收集玩家出现频率可以替代官方来源、结构化 metadata 或受治理规则。
- 通过追加装备定义可以修复非法组合、字段缺失或 SimC runtime 能力缺口。

## 3. 两个集合而不是两个对称装备库

### 3.1 Exact 可执行能力域

Exact 侧不是需要预先枚举完整 membership 的装备库，而是对任意输入执行确定性判定：

```text
canonical ExactItemInstance
-> Exact Authority Resolution
-> full-loadout Rule Resolution
-> SimC effect-support preflight
-> immutable ResolvedLoadout
-> immutable SimulationSnapshot
-> pinned SimC runtime execution
```

同一 canonical 输入与依赖向量必须得到相同身份。插件导出是“用户要求模拟什么”的输入
权威，不是“玩家真实拥有什么”的不可伪造证明。

### 3.2 Catalog 可换装集合

Catalog 是提前枚举并发布的有限集合，拥有 ItemDefinition、来源 membership、合法
progression state 和可浏览 BrowseVariant。它不拥有具体玩家的宝石、附魔、制造副属性、
装饰或中间轨道实例。

必须满足：

```text
materialize(模拟器可换装 BrowseVariant) ⊆ SimC-ready ExactItemInstance
```

这里的 `materialize` 不允许填充隐式默认值。对于制造属性等必选项，用户必须显式完成
选择；Catalog 必须至少存在一条完整合法的选择路径，且每条被后端接受的完整路径都能
形成 SimC-ready ExactItemInstance。

纯资料展示但不可准确模拟的物品可以留在其他展示域，但不得进入模拟器的可换装
BrowseVariant membership。

## 4. 信任与依赖边界

### 4.1 模拟资格

`simulationStatus=ready` 依赖：

- 完整且 canonical 的 ExactItemInstance 字段；
- 当前 RuleRevision 对槽位、职业、唯一装备、套装、装饰和跨装备约束的裁决；
- 对应 ExactAuthorityEnvelope 对静态属性与实例语义的确认；
- 当前 SimC runtime 对 profile 语法和关键动态效果的明确支持；
- 固定 compiler 与 runtime 身份。

`ExactAuthorityEnvelope` 是按实例内容寻址、不可变的 authority envelope，绑定完整
ExactItemInstance、结构化静态事实、效果支持引用、resolver 版本和来源版本。它可以在
有界解析后按实例追加和缓存，不要求该实例先进入一个全局 Catalog 或 Exact Registry
membership；SimulationSnapshot 直接绑定所消费的 envelope identities。

CatalogRevision 只能在 canonical SimulationSnapshot 之外作为非权威的
`originCatalogRevision` provenance 记录，不进入快照内容身份或模拟依赖向量。若一次
换装最初消费了 Catalog 事实，后端必须先把完整结果物化并验证为 ExactItemInstance，再由
ExactAuthorityEnvelope 接管。Catalog membership 缺失不是单独的模拟阻断条件。实现前
必须审计并修正现有“Exact 导入必须命中当前 Catalog”或
“SimC 提交必须重新取得 Catalog membership”的残留耦合，同时保留 RuleRevision 的
完整校验。

### 4.2 目录资格

`catalogStatus=listed` 额外依赖：

- 当前赛季 membership；
- 大秘境、团本或制造来源之一的可追溯证据；
- 完整 ItemDefinition；
- 所有发布 progression state 的 bonus ID、ilevel 和静态事实；
- 可完成的强化与制造选择规则；
- Catalog 候选门禁和原子发布。

玩家导入次数只能决定候选调查优先级，不能决定目录资格。

### 4.3 组件职责

| 组件 | 唯一职责 | 不能做 |
| --- | --- | --- |
| Exact Import Adapter | 解析插件、Battle.net 或 observed profile 输入并 canonicalize | 补默认装备事实、决定 Catalog membership |
| Exact Authority Resolver | 验证实例字段和静态事实，生成不可变 ExactAuthorityEnvelope | 用 BrowseVariant 或同 itemId 的其他实例补值 |
| Loadout Resolver | 按 RuleRevision 裁决整套合法性 | 把单槽可见性冒充整套合法性 |
| SimC Support Preflight | 按固定 runtime 验证语法与关键效果支持 | 把进程退出码零当作效果正确 |
| Observation Recorder | 去身份化、去重并有界记录新 Exact 观察 | 写 staging、candidate 或 active Catalog |
| Catalog Admission Worker | 验证来源、赛季、变体和规则证据并生成候选输入 | 直接切换生产指针 |
| Catalog Builder/Publisher | 构建不可变 revision、运行门禁并 CAS 发布 | 在失败时修改 last-known-good |
| Snapshot Compiler/Runner | 从 ready ResolvedLoadout 生成和执行不可变快照 | 读取前端拼接 profile 或未绑定 runtime |

关键效果支持采用三态 `verified | unknown | unsupported`。静态装备只有在权威数据确认不含
动态效果时才可直接为 `verified`；动态效果必须绑定当前 runtime 的受治理支持记录或确定性
专项探测。`unknown` 和 `unsupported` 都不能创建正式 SimC 任务。

### 4.4 三条数据流

```text
导入模拟：Exact input -> Exact Authority -> Loadout Resolver
          -> SimC Support Preflight -> Snapshot -> Runner

浏览换装：Active Catalog -> BrowseVariant -> 玩家显式选择完整 option
          -> Exact materialization -> 与导入模拟相同的后半链

动态发现：ready/unlisted Exact -> Observation Recorder -> Admission Worker
          -> Catalog candidate -> gates -> immutable revision -> CAS publish
```

动态发现链与当前用户模拟链异步隔离；Catalog 发布成功不会回写或替换已经存在的
ExactItemInstance 和 SimulationSnapshot。

## 5. 首期来源范围

### 5.1 大秘境

只纳入当前赛季明确属于活动地下城池、且能验证掉落 membership 与发布 progression
state 的物品。地下城活动、宝库奖励或升级规则之间的关系必须分别建模；没有明确映射时
保持 `partial`，不得从相似装等或历史赛季推导。

### 5.2 团本

只纳入当前赛季明确关联的副本、首领、难度或受治理奖励关系。套装 membership、普通
掉落、稀有掉落和转化关系分别拥有证据；不能因物品出现在玩家身上就反推官方掉落来源。

### 5.3 制造

Catalog 收录稳定产品身份和合法品质/progression state，不枚举制造副属性、装饰和其他
可选材料的笛卡尔积。这些内容由 EnhancementSelection 和整套 Resolver 在用户显式选择
后生成 ExactItemInstance。

三个来源以外的完整 Exact 装备仍可模拟；其 Catalog 状态为 `out_of_scope`，除非后续
产品决策明确扩展来源范围。

## 6. Observation Queue

Observation Queue 负责发现，不拥有生产事实。它保存去身份化的 canonical 装备观察、
首次/最近观察时间、去重计数、解析版本和分类结果，不保存角色名、服务器名或能够证明
玩家身份的原始导出全文。

观察身份至少绑定赛季、游戏 build、itemId 和 canonical exact variant signature。同一
身份重复出现只增加有界计数和最近观察时间，不制造无限记录。

### 6.1 分流

| 输入结果 | 当前模拟 | Queue 路由 | Catalog 行为 |
| --- | --- | --- | --- |
| Exact 完整、SimC 支持、Catalog 未收录 | 允许 | `observed_unlisted` | 可进入来源调查 |
| Exact 字段不完整 | 阻断 | 解析诊断 | 不成为 Catalog 候选 |
| SimC 关键效果未确认 | 阻断 | `runtime_gap` | 不靠补 Catalog 修复 |
| 整套组合非法 | 阻断 | 规则诊断 | 不追加装备定义 |
| 来源超出首期范围 | 允许，前提是 Exact ready | `out_of_scope` | 不进入首期 Catalog |
| 当前赛季三来源内的新装备 | 允许，前提是 Exact ready | `evidence_pending` | 可进入候选构建 |

Observation 状态不得覆盖 simulationStatus，也不得把单个玩家输入提升为官方来源事实。

### 6.2 有界运行

- Queue 按 canonical identity 幂等写入。
- 原始诊断 payload 有保留期限和字节上限；正式候选只消费结构化字段。
- 同一 itemId 的相互冲突证据进入冲突状态，不能以多数票自动胜出。
- 队列不可用只影响新观察收集，不阻断 Exact 模拟。
- 请求路径只允许写 observation 事件，不允许写 staging、candidate 或 active Catalog。

## 7. Catalog 晋升

一个观察项只有完成以下门禁，才能进入新 CatalogRevision：

1. 确认属于当前赛季和三个首期来源之一。
2. 确认 itemId、槽位、护甲/武器类型、职业与基础限制。
3. 建立所有拟发布 progression state 的 bonus ID、ilevel 和静态事实。
4. 建立宝石、附魔、制造属性、装饰及跨装备兼容规则。
5. 至少构造一个无隐式默认值的合法 Exact 样本。
6. SimC profile compiler 通过；带关键动态效果的装备还必须具备明确 effect-support
   evidence，单纯“任务成功退出”不算充分证据。
7. 重放已有 Exact 模板、可换装候选和负向规则样本。
8. 验证资源预算、内容哈希、依赖版本和无混合 revision 读取。
9. 生成不可变 CatalogRevision 与交叉绑定 Manifest。
10. 通过 compare-and-swap 原子切换；任一失败保持 last-known-good。

已建立、schema 未变化的来源适配器可以自动生成 candidate；新来源、新规则类型、来源
冲突或 effect-support 缺口必须进入人工产品/工程决策，不允许自动扩大承诺。

## 8. 玩家可见状态

内部保留两个正交状态：

```text
simulationStatus = ready | pending | blocked | unsupported
catalogStatus = listed | unlisted | candidate | out_of_scope
```

典型展示合同：

| 状态 | 玩家结果 | 允许动作 |
| --- | --- | --- |
| `ready + listed` | 可以模拟、可以换装 | 保存、换装、提交 |
| `ready + unlisted` | 可以模拟，暂未进入换装目录 | 保存、提交 |
| `ready + out_of_scope` | 可以模拟，不属于当前目录范围 | 保存、提交 |
| `pending + any` | 正在验证具体装备 | 只读、保存草稿、重试 |
| `blocked + any` | 展示具体缺失字段或非法规则 | 修改或重新导出 |
| `unsupported + any` | 展示具体装备和 runtime 能力缺口 | 禁止创建 SimC 任务 |

不得向玩家显示没有对象、字段和恢复动作的笼统“数据异常”。全局 Catalog 更新失败时，
目录继续使用上一稳定版；已有 Exact 模板的加载和模拟不受影响。

## 9. 快照、结果与回滚

- ResolvedLoadout 和 SimulationSnapshot 绑定完整 Exact identity、所消费的
  ExactAuthorityEnvelope identities、RuleRevision、compiler 和 SimC runtime。
- CatalogRevision 只在 canonical 快照之外作为 `originCatalogRevision` provenance 保存，
  不参与快照内容哈希，也不能把 unlisted 的 ready Exact 变成失败。
- 已执行快照不被后续 Catalog 晋升、降级或来源变化原地重写。
- 相同快照与相同 runtime 复用同一 append-only 终态结果。
- Catalog 候选失败不改变活动指针；回滚只切换 Manifest，不逐表回写。
- runtime 更新不能把历史结果冒充为新 runtime 的复现结果；需要重新模拟时生成新快照或
  明确的新执行身份。

## 10. 验收门禁

### 10.1 Exact 主链

1. 导入 Catalog 外但完整且受支持的 Exact 装备，成功保存、重载和模拟。
2. 上述请求只产生 observation 事件，active Catalog/staging/candidate 均无请求时写入。
3. 缺字段时定位具体 item/field，不使用默认装等、相似 bonus 或最高 BrowseVariant 补值。
4. 非法组合定位具体约束，不误报为 Catalog 缺失。
5. SimC 关键效果未确认时在任务创建前阻断，不返回伪准确 DPS。
6. 相同 canonical 输入和依赖向量生成相同身份与字节一致 profile。

### 10.2 Catalog 主链

1. 每个模拟器可换装 BrowseVariant 至少存在一条完整合法的 Exact materialization 路径。
2. 必选强化没有隐式默认，所有已接受完整选择都能生成 SimC-ready Exact。
3. 新装备只在候选门禁通过后进入新 CatalogRevision。
4. 候选失败、Queue 故障或来源冲突均不改变 last-known-good。
5. 晋升后旧 SimulationSnapshot 身份和历史结果保持不变。
6. 重复观察幂等去重，资源使用保持在配置的记录数和字节预算内。

### 10.3 真实体验

真实微信主链必须覆盖导入、保存、重载、换装、Resolve、提交、结果查看，以及 unlisted、
字段缺失、非法组合、runtime unsupported 和 Catalog candidate 失败。HTTP 200、单元测试、
队列入库或 SimC 进程退出都不能单独证明玩家闭环完成。

硬门禁为：

```text
catalog_non_simulatable_count = 0
silent_default_fill_count = 0
request_time_catalog_write_count = 0
historical_snapshot_identity_drift = 0
mixed_revision_read_count = 0
```

## 11. 覆盖率与承诺

分别报告：

- `exact_sim_success_rate`：语法有效的真实导入中最终 simulationStatus=ready 的比例，并按
  incomplete、illegal、runtime gap 和内部错误拆分失败原因。
- `catalog_coverage`：三个首期来源内 verified item/progression membership 占可枚举权威
  denominator 的比例；denominator 不可获得时直接报告 `blocked`，不估算百分比。
- `unlisted_but_simulatable_rate`：ready Exact 导入中 catalogStatus 不是 listed 的比例。
- `catalog_non_simulatable_count`：必须持续为零。

在积累真实导入分布前，不宣称三个来源覆盖了固定百分比的玩家场景。真实导入指标只说明
已观察用户样本，不能证明整个赛季 Universe 完整。

## 12. 与当前基线的关系

- generation 35、Phase 0-4 证据和 26/14 SimC 能力矩阵保持历史已完成基线，不因本设计
  被改写为新完成状态。
- 当前 Catalog Browse 纠偏、14 路由 UI 验收与阻塞的 E2E Universe Goal 保持独立。
- 本设计不恢复 19 类 Universe 闭包，不把三来源子集包装成全 PVE 完整性。
- 后续实施计划必须先审计 Exact/Resolver/Profile Compiler 对 Catalog membership 的所有
  当前调用和测试，再按 Harness 选择迁移、候选、验证和回滚范围。
- 未形成并批准实施计划前，不修改 runtime、数据库 schema、worker、API、微信前端或活动
  Manifest。

## 13. 主要剩余风险

1. SimC 能解析装备但未准确实现特殊效果，是最严重的静默错误风险；必须把 effect-support
   evidence 与进程成功分开。
2. 插件导出可被编辑，只能作为模拟意图，不能用于资产拥有证明、排行榜真实性或账号审计。
3. 制造选择空间不能靠预生成组合穷举；错误建模会重新制造目录爆炸。
4. 三来源是否覆盖大部分真实玩家只能由后续真实导入分布验证，不能由直觉关闭。
5. Observation Queue 若没有去身份化、去重和资源上限，会演变为新的不受控 staging。
