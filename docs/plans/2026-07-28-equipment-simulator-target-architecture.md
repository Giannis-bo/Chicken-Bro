# 装备模拟目标架构

状态：`已批准；Phase 0-2 已完整归档；Phase 3 ResolvedLoadout + SimulationSnapshot 正在推进`

批准日期：`2026-07-28`

## 1. 用户目标

玩家在微信小程序中选择职业和专精后，可以手动组合当前赛季、当前 PVE
实际可获得的装备，也可以导入社区高端玩家模板。系统必须保留具体装备实例，
准确展示轨道、等级、属性和强化；保存模板后，再由后端生成合法且可复现的
SimulationCraft 输入。

当前产品主链保持不变：

```text
选择职业 / 专精
-> 手动配装或导入社区模板
-> 调整装备与强化
-> 保存结构化模板
-> 发起 SimC
-> 查看任务结果
```

装备模拟负责配装和保存；SimC 页面负责执行已保存模板。两者不合并成新的入口。

## 2. 产品范围

“全部装备”固定指：

> 当前赛季、当前 PVE 内容中实际可获得，并且对 40 个专精可装备或有意义的全部装备。

能力边界：

- 40/40 专精支持装备浏览、具体变体、属性、宝石、附魔、美化、制造属性、
  合法性校验和模板保存。
- 26 个常规输出专精支持可信的 SimC 性能模拟。
- 6 个坦克、7 个治疗和增辉唤魔师可以完成配装和模板保存，但不提供性能模拟。
  这些专精必须显示明确的 `unsupported`，不能产生伪成功或误导性数值。
- 社区模板中不属于当前赛季可选目录的实际装备可以按原始身份只读展示，但不能
  伪装成当前赛季候选。

本设计不负责：

- BiS、推荐排序、属性权重或职业强弱排名。
- 为坦克、治疗或增辉自行建立战斗模型。
- 在前端建立第二套装备、变体、属性或强化规则。
- 把 Wowhead、Raider.IO、Warcraft Logs 或 Archon 的公开展示推断成其内部架构。
- 恢复旧 Gear Evidence Registry、逐标量 Fact/Observation/Artifact DAG、
  r14/r22/r23 或已删除计划的执行权。
- 微服务拆分、事件溯源、通用规则 DSL 或通用 Claim DAG。

## 3. 已确认的设计原则

1. 保留现有可靠内核，只重做装备目录、变体和属性证据层。
2. 列表浏览不运行 SimC，也不在线查询第三方装备数据库。
3. 前端只提交选择意图；合法性、属性和 SimC readiness 由后端拥有。
4. 缺少精确证据时可以保存草稿，但不能保存为可模拟模板或提交 SimC。
5. 候选目录离线构建，完整验证后通过单一 Manifest 指针原子发布。
6. 同一 canonical 输入必须得到相同内容哈希，不能因时间戳或构建序号制造新版本。
7. `profileReadiness=ready` 只表示可生成并执行 canonical profile，不等于已经完成
   SimC，也不等于 DPS 可信。

## 4. 目标实体

### 4.1 `CatalogRevision`

职责：封存一个赛季装备目录及其依赖版本。

主键：

```text
catalogRevision = gear-catalog:sha256:<canonical-content-hash>
```

内容包括赛季、PVE 来源范围、规则版本、ItemDefinition membership、
BrowseVariant membership、构建器版本和来源摘要。构建时间、任务 ID、日志路径
等非业务字段不得进入内容哈希。

`CatalogRevision` 不可变。内容相同的重复构建必须复用同一主键，不产生新的 rXX。

### 4.2 `ItemDefinition`

职责：表示一件装备在指定目录中的稳定定义。

主键：

```text
(catalogRevision, itemId)
```

拥有：

- 名称、图标、槽位、护甲或武器类型。
- 职业、专精、双持、唯一装备等基础限制。
- 当前赛季 PVE 获取来源。
- 可用轨道集合。
- 来源、解析方式、版本和可信状态。

不拥有具体玩家的轨道等级、宝石、附魔或制造选择。

### 4.3 `BrowseVariant`

职责：服务手动候选浏览。

身份：

```text
browseVariantKey =
  sha256(canonical(catalogRevision, itemId, progressionState))
```

每件装备每个合法 progression state 只发布一个代表项。勇士、英雄和神话使用
`upgrade_track` progression，BrowseVariant 必须发布最高合法 rank；虚空晋升使用
独立 `ascendant` progression，不增加前端开关，也不得伪造为普通 `6/6` 轨道；
最高品质制造装备使用 `crafted_quality` progression，制造副属性属于
EnhancementSelection，不参与 BrowseVariant 身份。每个 BrowseVariant 必须包含
canonical `variantKey`、`progressionState`、ilevel、bonus IDs、可验证静态事实和
证据状态。精确定义见
[Track Authority 阻塞修正](2026-07-28-equipment-simulator-track-authority-correction.md)。

BrowseVariant 不是精确玩家实例，不能用其最高级属性替代社区玩家实际穿戴的
英雄 3/6 等中间等级。

### 4.4 `ExactItemInstance`

职责：表示社区导入、个人模板或已穿戴状态中的具体装备实例。

主键：

```text
exactItemInstanceKey =
  sha256(canonical(itemId, bonusIds, context, progressionState, ilevel,
                   gemIds, enchantId, craftedStats, embellishmentIds))
```

所有数组必须按 SimC 语义 canonicalize；无业务意义的采集时间和展示文案不参与哈希。
精确实例首次出现时可异步解析并缓存。解析完成前状态为 `pending` 或 `blocked`，
不得使用 BrowseVariant、默认轨道或同 itemId 的其他实例补值。

为避免重复计算，内部缓存可以额外使用不含强化的 `exactVariantSignature`，但对外保存
和 SimC 输入仍绑定完整 `exactItemInstanceKey`。

### 4.5 `EnhancementSelection`

职责：表示宝石、附魔、美化和制造属性的 canonical 选择。

它不是独立发布目录，而是 ItemDefinition/ExactItemInstance 上的合法选择输入。
后端 Enhancement Resolver 按装备部位、类型、插槽、赛季、职业和整套装备约束返回：

- `available`
- `unavailable`
- `pending`
- `blocked`

前端只展示后端返回的兼容候选；全局数量、互斥、唯一装备和跨物品限制仍由后端
对完整套装做最终校验。不再兼容的已选强化必须明确提示，不能静默删除。

### 4.6 `ResolvedLoadout`

职责：Canonical Loadout Resolver 对一个完整装备组合的不可变解析结果。

主键：

```text
resolvedLoadoutKey =
  sha256(classKey, specKey, orderedSlotExactInstanceKeys,
         enhancementSelections, ruleRevision, catalogRevision)
```

输出包括 ordered slots、合法性结果、静态属性、约束、serializer input 和明确
problem 列表。只有 `ready` 的 ResolvedLoadout 才能成为可模拟模板。

### 4.7 `SimulationSnapshot`

职责：封存一次实际 SimC 提交。

主键：

```text
simulationSnapshotKey =
  sha256(resolvedLoadoutKey, talentProfileKey, characterContext,
         scenarioOptions, compilerRevision, simcRuntimeRevision)
```

快照保存实际提交的 canonical SimC 输入、模板版本、Catalog/Rule/Compiler/Runtime
revision 和结果身份。已保存模板可以继续编辑；已执行任务的快照不得随新目录或规则
变化。

## 5. 真值和来源归属

| 事实 | Owner | 可用输入 | 禁止替代 |
| --- | --- | --- | --- |
| 当前赛季与 PVE 来源范围 | Catalog Builder / PostgreSQL catalog | Blizzard Game Data、当前稳定规则 | 社区玩家是否穿戴 |
| 物品定义与可用轨道 | Catalog Builder | 结构化物品 metadata、受治理规则 | 前端文案、名称猜测 |
| 精确玩家实例身份 | Exact Instance Resolver | Battle.net/插件/observed profile 中的完整实例字段 | BrowseVariant 最高级 |
| 具体变体静态属性 | Backend Resolver | verified variant、SimC DBC/受治理规则、已验证 exact snapshot | Wowhead tooltip、默认装等 |
| 强化兼容性 | Enhancement Resolver | versioned rule matrix、canonical option identity | 前端筛选结果 |
| 整套合法性 | Loadout Resolver | 完整 Selection Intent | 单槽候选可见性 |
| SimC 输入 | SimC Profile Compiler | ready ResolvedLoadout + profile context | 前端拼接文本 |
| DPS 与报告数字 | SimC Runner / result parser | 最终执行输出 | 生成预览、LLM 或参考站数值 |

Raider.IO、Warcraft Logs、Archon 和 Wowhead 可以作为 observed evidence 或
reference-only 来源；除非进入受治理的 verified 规则，否则不得拥有生产属性真值。

## 6. 运行链路

```text
受治理数据源
-> Catalog Builder
-> immutable CatalogRevision
-> ItemDefinition + canonical BrowseVariant per progression state
-> candidate validation
-> Active Season Manifest
-> 微信装备浏览
-> 手动选择或社区 ExactItemInstance 导入
-> Enhancement Resolver
-> Loadout Resolver
-> ResolvedLoadout
-> 保存结构化模板
-> SimulationSnapshot
-> SimC Profile Compiler
-> SimC Runner
-> 任务结果与前端展示
```

手动选择流程：

1. 候选列表按 ItemDefinition 分组；普通升级轨道只展示最高 rank，制造品质和虚空
   晋升各按自身 progression state 展示一个 BrowseVariant。
2. 玩家选择装备和轨道后，后端返回该候选真实存在的合法配置。
3. 前端显式应用 Selection Intent。
4. 后端重新 Resolve，成功后才更新 confirmed loadout。

社区导入流程：

1. 保留玩家实际 itemId、bonus IDs、track/rank/ilevel 和全部强化。
2. 命中 ExactItemInstance 缓存则复用；未命中时进入有界解析。
3. 精确实例未完成前允许只读显示和草稿保存，不允许冒充 ready。
4. 导入内容必须按当前 Catalog/Rule revision 重新校验，不能因来源是高端玩家而跳过。

SimC 流程：

1. 只从已保存的结构化模板发起。
2. 后端按当前活动 Catalog/Rule revision 重新 Resolve。
3. 通过后生成不可变 SimulationSnapshot。
4. Profile Compiler 按固定 slot order 和字段顺序输出原生 `id`、`bonus_id`、
   `ilevel`、`gem_id`、`enchant_id`、`crafted_stats`、`embellishment` 及必要的
   profile/precombat/temporary-enchant 层。
5. 相同快照和 SimC runtime 必须生成字节一致的 canonical 输入。
6. 14 个不支持性能模拟的专精在创建 Runner task 前确定性阻断。

## 7. 玩家可见状态

| 状态 | 含义 | 允许动作 |
| --- | --- | --- |
| `available` | 当前目录存在且可选择 | 加入草稿 |
| `verified` | 具体变体和静态属性已确认 | 显示真实属性 |
| `pending` | 已知身份正在解析 | 只读展示、保存草稿 |
| `partial` | 部分字段可信但未满足完整合同 | 只读展示、保存草稿 |
| `stale` | 来源或 revision 过期 | 展示旧身份和过期原因 |
| `blocked` | 缺证据或违反规则 | 不得成为可模拟模板 |
| `unsupported` | 产品不提供该专精的性能模拟 | 可配装和保存，禁止提交 SimC |

错误必须定位到具体对象和字段，例如“缺少英雄 4/6 的 verified 属性”，不能只返回
“数据异常”。任何 unresolved、partial、stale、blocked 或 unsupported 状态都不能被
序列化为成功任务。

## 8. 构建、发布与回滚

Catalog Builder 只写 staging/candidate，不直接改活动消费者：

1. 收集并归一当前赛季 PVE ItemDefinition。
2. 按每件装备的合法 progression state 批量生成 BrowseVariant；只有普通升级轨道
   批量生成最高 rank。
3. 验证 bonus ID、progression kind、条件式 rank、ilevel、属性和来源闭包。
4. 验证 40 专精浏览覆盖、强化规则和社区模板重放。
5. 对 canonical 内容计算 CatalogRevision hash。
6. 内容未变化时复用现有 revision，记录 `no_change`。
7. 验证全部通过后，生成与 Gear/Community/Rule revisions 交叉绑定的 Manifest。
8. 通过一个 compare-and-swap 指针原子切换。

候选失败不改变活动指针。回滚只切回上一稳定 Manifest，不逐表改写。线上读请求始终只
消费一个活动版本；禁止在一个响应内混用活动目录、旧社区模板或不同 rule revision。

## 9. 资源与保留合同

Builder 启动前必须具备显式的环境预算；没有预算配置时任务直接 `blocked`：

- `maxRssBytes`
- `maxTemporaryBytes`
- `minFreeBytes`
- `minFreePercent`
- `maxCandidateDuration`
- `maxDiagnosticBytes`

默认安全线要求构建期间文件系统预测峰值不超过已用容量的 `80%`；如果环境设定更低，
以更严格值为准。预检至少保留：

```text
active hot payload
+ one rollback hot payload
+ estimated candidate payload
+ estimated temporary working set
+ configured free-space reserve
```

实现必须采用按来源/物品分块的流式构建和有界批次，不把全目录、全证据和全量诊断同时
复制到内存。进程 RSS、临时字节、耗时任一达到硬上限时立即停止 promotion，活动版本
保持不变。

保留策略：

- 热存储只保留 active、一个 rollback 和一个 in-progress candidate 的完整物化。
- 被历史 SimulationSnapshot 引用的 revision 保留 identity、canonical SimC input 和
  最小 provenance，不为每次任务复制完整 catalog。
- 未被活动/回滚/快照引用的旧完整物化进入有界回收。
- failed candidate 的构建目录在任务退出、异常和信号处理后统一清理。
- 诊断文件同时受数量、年龄和 `maxDiagnosticBytes` 限制；超限先删除最旧的未引用诊断。
- 清理失败必须进入 health，后续构建在空间恢复前保持 `blocked`。

## 10. 与现有系统的关系

保留：

- `GET /api/websim/gear` 的 initial/slot 浏览职责。
- `POST /api/websim/gear/resolve` 的 canonical Selection Intent。
- `POST /api/websim/profile` 的后端重新 Resolve 与 serializer 边界。
- 社区模板导入、个人模板保存、异步 stat snapshot 和 SimC task/result 链路。
- 现有 Gear/Community Release、Active Manifest、CAS pointer、PostgreSQL-only
  runtime 和 Taro typed API。

需要演进：

- Gear Release 的 catalog payload 收敛为 ItemDefinition + BrowseVariant membership。
- ExactItemInstance 由社区导入和模板按需解析、去重和缓存。
- Enhancement options 绑定 canonical identity，消除展示值直传。
- 模板到 SimC 之间增加明确的 SimulationSnapshot identity。
- Release Builder 改为确定性、流式、有资源硬门禁和统一清理的 Catalog Builder。

需要删除或降级：

- 逐静态标量重复建立 Artifact/Observation/Fact/Release 的 Evidence Registry。
- 因修正一个标量就重新物化全量数据库或制造无意义 rXX 的流程。
- 浏览请求触发 SimC、同步、外部请求或写库。
- 前端默认 variant、属性推断和兼容 option 补全。

## 11. 迁移策略

迁移必须保持一套长期事实系统：

1. 只读盘点当前活动 Gear/Community Release、Manifest、API 调用方和表 ownership。
2. 将当前活动 Gear Release canonicalize 为首个 CatalogRevision；内容不变时不重新
   解析全目录。
3. 在现有 PostgreSQL release registry 中增加新 membership/identity，不创建长期
   candidate 数据库副本。
4. 将现有社区模板和个人模板映射为 ExactItemInstance；无法证明精确身份的模板保持
   partial/blocked。
5. 新 Catalog reader 对 40 专精运行 shadow read，对比候选集合、progression、
   条件式 rank、属性、
   社区导入和 canonical SimC 行。
6. 只在完整 shadow matrix 通过后切换单一活动 Manifest。
7. 切换后旧 reader 只保留短期兼容调用；caller inventory 为零后删除，禁止长期双写。
8. 回滚只恢复旧 Manifest pointer；模板和历史任务继续按自己的 revision/snapshot
   解释。

迁移不得改变当前 UI 入口、owner 隔离、模板 ID 或历史 SimC 结果。

## 12. 影响图

| 分类 | 范围 |
| --- | --- |
| `must_change` | catalog builder、目录 membership、variant identity、exact instance cache、enhancement canonical option、SimulationSnapshot、发布验证和资源门禁 |
| `must_not_change` | 四个职业入口、装备模拟到保存模板的主路径、owner 隔离、任务结果访问控制、现有历史任务结果、Taro 视觉目标 |
| `risk_unknown` | 当前活动 Release 到 CatalogRevision 的无损映射率、所有社区模板 exact instance 完整率、现网 builder 峰值资源、旧 API caller 数量 |
| `evidence_required` | 40 专精 shadow、26 专精真实 SimC、14 专精阻断、模板/任务兼容、资源压测、pointer rollback、本地/远端/云端 identity parity |

## 13. 验收矩阵

| 用例 | 必须结果 |
| --- | --- |
| 40 专精浏览 | 40/40 返回当前赛季合法候选；source blocker 必须阻止验收而不是算作通过 |
| 当前 PVE 完整性 | 已纳入范围的来源、难度、槽位和物品都有 verified membership 或显式排除理由，不能静默缺失 |
| 手动列表 | 普通轨道只出现最高 rank；制造品质和虚空晋升各出现一个 canonical BrowseVariant |
| 中间等级导入 | 英雄 3/6 等实例保留真实 rank、ilevel、属性和强化 |
| 虚空晋升 | 作为独立 ascendant 状态出现，无额外开关且不伪造普通轨道 rank |
| 制造装备 | 同一装等状态只出现一次，制造副属性进入 EnhancementSelection |
| 具体属性 | 所有公开可模拟实例具有 verified variant 和静态属性 |
| 强化 | 宝石、附魔、美化、制造属性兼容性和整套限制正确 |
| Fail closed | 缺证据只允许草稿，不生成 ready 模板或 SimC task |
| SimC | 26/26 常规输出专精至少一套完整模板真实执行成功 |
| 不支持专精 | 6 坦克、7 治疗和增辉在 Runner 前明确 `unsupported` |
| 确定性输入 | 同一 SimulationSnapshot + runtime 生成相同输入 hash |
| 确定性构建 | 同一 catalog 输入重复构建得到同一 CatalogRevision |
| 单一活动版本 | 所有线上消费者读取同一个 Manifest dependency vector |
| 候选隔离 | 构建/验证失败不改变活动版本 |
| 回滚 | CAS 切回上一 Manifest 后 API、模板和 SimC smoke 恢复 |
| 资源上限 | RSS、临时磁盘、耗时均有硬门禁，失败后无无界残留 |
| 三方身份 | 本地、origin 和云端可核对代码、Manifest 与 runtime identity |
| 微信验收 | 手动配装、社区导入、强化、保存和 SimC 主路径在真实微信通过 |

以下证据不能单独宣布完成：

- 单元测试通过但未运行真实 SimC。
- 40 专精接口返回 200，但候选或属性仍为 partial。
- `/health=200`，但 catalog、template 或 SimC component 为 partial/blocked。
- 本地 Git 与 origin 一致，但云端 Manifest/runtime identity 不一致。
- 微信构建成功，但 DevTools 未加载最新源码哈希产物或用户未完成主路径验收。

## 14. 设计批准后的下一步

本文件定义长期目标；当前执行仍受 Harness 任务 packet 控制。
[Phase 0 归档证据](../../artifacts/releases/2026-07-28-equipment-simulator-phase0-unblock/evidence.json)
记录：

- 活动 Manifest 为 generation 32，绑定一个 immutable Gear Release 和一个
  80 槽 Community Release；
- 排除非战斗 Cosmetic 后，1,674 条 legacy Browse 归并为 1,309 个 canonical
  BrowseVariant，1,309/1,309 均有精确映射和静态属性；
- 438 条制造属性组合仍作为 EnhancementSelection 关联，折叠 365 个重复 Browse
  身份；
- 40/40 专精浏览与 80/80 社区 ExactItemInstance 导入通过；
- 26/26 支持专精真实执行 SimC 并产生 DPS，14/14 不支持专精在 Runner 前确定性阻断；
- Community Builder 在 1,467,432,960 bytes 峰值 RSS、24,622 ms、0 临时字节、
  0 写入下通过硬门禁；
- Manifest 回滚到上一稳定版本及恢复 generation 32 均通过真实 API/SimC smoke。

全局 `/api/data/health` 仍为 `partial`：活动 Manifest 和 stat worker 已 verified，
但旧 staging catalog、旧 template chain、上一轮 release refresh 失败和
manual-override legality health 仍由旧 owner 报告。这些状态不推翻独立活动 Release
验收，也不能被包装成全局健康成功；它们必须进入后续 Catalog/authority 迁移。

Phase 0 的两项真实微信验收、PR CI、合入、最新 `main` 微信刷新和
本地/`origin/main`/云端身份收口已完成。Phase 1 随后完成前两项切片：
`CatalogRevision + ItemDefinition + BrowseVariant` dormant schema，以及活动
Gear Release 到首个 CatalogRevision 的确定性迁移与 40 专精 shadow。当前从
第 3 项继续：

1. `ExactItemInstance + EnhancementSelection` 缓存和社区/个人模板迁移。
2. `ResolvedLoadout + SimulationSnapshot` 身份、canonical compiler 和任务兼容。
3. 单一 Manifest 切换、旧 reader/caller 淘汰、健康 owner 迁移、回滚和真实微信验收。
