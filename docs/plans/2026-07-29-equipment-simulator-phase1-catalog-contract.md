# 装备模拟 Phase 1：Catalog 合同与确定性迁移

状态：`正在推进`

日期：`2026-07-29`

## 1. 用户价值

玩家看到的仍是原有“选择职业/专精 → 配装或导入社区模板 → 保存 → SimC”主路径，
但装备目录底层从兼容命名的 Gear Release 收敛为明确的
`CatalogRevision + ItemDefinition + BrowseVariant membership`。本阶段先建立 dormant
合同并用活动 generation 32 做无损 shadow，不切换微信或公共 API reader。

完成后必须证明：

- 当前赛季 PVE 目录可以由同一活动 Gear Release 确定性重建；
- 1,309 个 canonical BrowseVariant 不因制造副属性组合重复出现；
- 普通升级轨道、制造品质和虚空晋升使用不同的 canonical progression state；
- 缺少精确静态事实、来源、轨道或完整成员关系时整次构建 fail closed；
- dormant Catalog 的写入不会改变活动 Manifest、generation 32 或现有用户链路。

## 2. 当前事实

- Phase 0 已完整归档，活动 Manifest generation 32、Gear Release
  `gear-release:sha256:9299fe1f...` 和 Community Release
  `community-release:sha256:686708be...` 已通过 40/40 浏览、80/80 导入、
  26/14 SimC、真实微信和回滚矩阵。
- Phase 0 只证明现有 Gear Release 可以无损映射；当前尚无独立
  `gear-catalog:sha256:*` 实体或 dormant Catalog membership 表。
- Phase 0 的 `mappedItemCount=1,310` 是槽位元数据分类总量，不等于正式目录成员。
  首次候选构建据此 fail closed 后，生产快照复核确认：正式 ItemDefinition 只能由
  canonical BrowseVariant 或 verified ExactItemInstance 建立成员关系。当前快照对应
  613 个正式 ItemDefinition；其余 697 条孤立或仅来源历史元数据继续留在旧快照中，
  不得伪装成玩家可浏览或可导入的装备。
- 第二次候选验证进一步确认两个确定性边界：Catalog 内容身份必须对数据库成员回读顺序
  不敏感；Phase 0 Track Authority 已验证的 298 ExactItemInstance 必须继续作为普通
  Ascendant BrowseVariant 的资格证据。两项均由 RED/GREEN 测试固定，避免回读误判和
  11 个合法 Ascendant 成员丢失。
- 第三次候选生成了完整 613/1,309 成员，但暴露 store 的 seal 后语义比较仍按 SQL
  返回顺序比较数组；事务再次完整回滚。store 现按成员稳定键比较集合，同时继续对每行
  内容哈希和完整 CatalogRevision 做严格验证。
- 第四次候选已成功 seal 并回读 613/1,309 Catalog，pointer generation 32 保持不变；
  40 专精 shadow 随后因误读 `mode=initial` 的模板预览而全部报告空候选。生产探针证明
  full catalog payload 正常返回候选，shadow reader 现固定读取 full catalog，不再把
  首屏模板预览当作完整装备目录。
- 第五次候选改读 full catalog 后，40 个完整 payload 被进程级 LRU 同时保留，实时
  cgroup 峰值达到 2,220,298,240 bytes，超过既定 2,000,000,000 bytes 硬上限，因此
  主动终止且不产出通过报告。shadow reader 现会立即压缩为候选身份对、清空仅属于候选
  进程的 payload cache 并回收对象；下一候选同时由 MemoryMax/RuntimeMaxSec 硬限制。
- 第六次候选证明仅清 LRU 仍不够：单次 public payload 深拷贝触及
  2,000,039,936 bytes 并产生 307 MiB swap，再次主动终止。最终方案不再调用 public
  payload builder；它只读取一次同一活动 Gear Release snapshot，复用当前 PG selector
  的来源/变体/选项索引，对 40 专精逐一生成最小候选身份集合。
- 第七次候选以 881,748 KiB、235.18 秒和零 swap 通过资源/pointer/seal 门禁，但
  selector 输入错误地包含了 48,555 条 ExactItemInstance，造成 40,306 个非 Browse
  身份被报告未映射。投影入口现只接收已由 Phase 0 审核为 `rowFamily=browse` 的 1,674
  条 legacy 行；ExactItemInstance 保留给后续阶段，不混入 Phase 1 Browse parity。
- 第八次候选在 871,936 KiB、169.40 秒、零 swap 内把差异收敛到 926 个制造 compact
  synthetic key。当前 PG selector 会把同一制造轨道的六种副属性组合显示为
  `crafted-{trackKey}-{itemLevel}`；Catalog 已折叠为同一 BrowseVariant，shadow 现为
  该 synthetic key 建立确定性 alias，而不把制造副属性重新写回 Browse 身份。
- 全局 `/api/data/health` 仍为 `partial`。本阶段不把旧 staging/refresh owner
  冒充成新的 Catalog 健康成功，也不在完成 shadow 前迁移 health owner。

## 3. 范围

### 3.1 必须实现

1. 新增纯确定性 Catalog builder：
   - 输入一个已绑定活动 Manifest 的完整只读 Gear Release snapshot；
   - 输出不可变 `CatalogRevision`、`ItemDefinition` 和 `BrowseVariant` membership；
   - 内容哈希排除构建时间、任务 ID、日志路径和展示文案；
   - 相同 canonical 输入重复构建得到同一个 `gear-catalog:sha256:*`。
2. 新增 dormant PostgreSQL schema：
   - Catalog revision、item definition、browse variant 三组 append-only 表；
   - 行级内容哈希、外键、唯一 membership、不可变 trigger 和最小权限；
   - 不新增活动 Catalog 指针，不修改 Season Manifest。
3. 新增唯一 SQL owner/store：
   - 原子 seal，冲突时逐字节核验；
   - load/verify 只读取指定 CatalogRevision；
   - 不允许 update/delete sealed rows。
4. 新增有界迁移与 shadow 工具：
   - 在同一只读快照中读取活动 Gear Release；
   - 构建并 seal dormant Catalog；
   - 再读取验证内容哈希、数量和 40 专精旧/新目录可见性；
   - 前后核对活动 Manifest pointer 完全不变。
5. 将新表、owner、调用方和验证命令纳入 project owner、backend owner、迁移测试、
   caller audit 和当前控制面。

### 3.2 明确不做

- 不切换 `cache.websim_active_manifest_pointer`，不发布新的 Season Manifest。
- 不修改微信装备入口、候选 UI、TemplateSet、社区模板或 SimC task 行为。
- 不在本阶段引入 ExactItemInstance 缓存、EnhancementSelection 表、
  ResolvedLoadout 或 SimulationSnapshot。
- 不把制造 `crafted_stats` 写入 BrowseVariant 身份或静态事实。
- 不在线查询 Wowhead、Raider.IO、Warcraft Logs、Archon 或新的第三方数据。

## 4. Canonical 合同

### 4.1 CatalogRevision

Catalog 内容身份由以下 canonical 数据计算：

```text
schemaRevision
seasonRevision
builderRevision
dependencyVector
sourceSummary(content hash and governed source revisions)
ordered ItemDefinition membership
ordered BrowseVariant membership seeds
```

`sourceGearReleaseId`、构建时间和运行日志只作 provenance，不进入内容哈希。
Gear Release 本身已是内容寻址；同内容的重复来源不得制造新 CatalogRevision。

### 4.2 ItemDefinition

每个成员以 `(catalogRevision, itemId)` 唯一，保留稳定名称、图标、槽位、装备类型、
限制、当前 PVE 来源和可信状态。成员必须至少拥有一个 canonical BrowseVariant 或一个
verified ExactItemInstance，并且拥有可治理的当前 PVE 来源；仅有历史元数据、仅有来源、
没有 canonical 槽位或没有 verified 使用关系的记录不能成为 ItemDefinition。legacy
item 行的 `sourceStatus` 只作 provenance；当成员来源行已由治理链验证时，以来源行的
verified 状态作为 Catalog 的有效来源状态，不回写旧行。

### 4.3 BrowseVariant

CatalogRevision 先根据 `itemId + progressionState + canonical variant facts` 的 membership
seed 计算；随后派生：

```text
browseVariantKey =
  sha256(catalogRevision, itemId, progressionState)
```

这样保持目标身份合同，同时避免把派生 key 反向放进 Catalog hash 形成循环。

- 普通 `upgrade_track` 只保留最高合法 rank。
- `crafted_quality` 与 `ascendant` 不得伪造普通 rank。
- 同一制造装备的不同 `crafted_stats` 归属于后续 EnhancementSelection，不产生多个
  BrowseVariant；builder 只保留与选择无关且在所有组合中一致的静态事实。
- 非制造候选同一 progression state 必须恰好对应一条 verified legacy browse row。
- 任一成员缺少正装等、bonus IDs、verified 静态事实或 Track Authority 时，整次
  Catalog 构建阻断。

## 5. 实施顺序

1. RED：为 canonical identity、制造折叠、循环身份规避、异常阻断和 SQL
   不可变合同添加失败测试。
2. GREEN：实现纯 builder 与行级验证。
3. RED/GREEN：实现 migration 和唯一 store 的 seal/load/verify。
4. RED/GREEN：实现有界 active Gear Release snapshot → dormant Catalog 工具与
   pointer fence。
5. 本地 full 验证后部署候选代码和 repository-owned migration；异步同步保持关闭。
6. 在云端 seal 首个 dormant Catalog，运行两次确定性构建、40 专精 shadow、
   资源和零 pointer-change 检查。
7. 完成 CR、PR CI、合并、main/云端代码与 dormant Catalog 身份收口。

## 6. 验收矩阵

| 门禁 | 通过标准 |
| --- | --- |
| 确定性 | 同一活动 snapshot 重建两次得到同一 CatalogRevision 和逐行 hash |
| ItemDefinition | 当前生产快照精确生成 613 个正式成员（canonical Browse 或 verified Exact 使用关系）；697 条 dormant 历史/仅来源元数据被排除；无重复、无孤儿、无空 canonical slot |
| BrowseVariant | 1,309/1,309 verified membership；普通、制造、Ascendant progression 分离 |
| 制造折叠 | 438 个制造属性组合仍折叠为 73 个 BrowseVariant membership；选择属性不进入身份 |
| 40 专精 shadow | 40/40 专精旧 Gear Release 与 dormant Catalog 的可见候选集合一致 |
| 写入安全 | 只新增 dormant append-only Catalog 行；活动 Manifest generation 32 前后不变 |
| 资源 | 构建和 seal 在既定内存/时间/临时文件上限内，失败时不留下半成品 |
| 公共兼容 | 当前微信/API/Resolver/SimC 聚焦回归通过，未读取 dormant Catalog |
| 发布 | migration、代码、CatalogRevision、PR/main/cloud 身份和回滚证据完整 |

## 7. 回滚

- Phase 1 不创建活动指针，旧 reader 始终继续读取 generation 32 Gear Release。
- 候选失败时回滚代码/服务；已 seal dormant 行保持不可变但无人读取。
- migration 只新增表、索引、trigger 和权限，不通过破坏性 down migration 删除数据。
- 任何 pointer 漂移、40 专精差异或资源超限立即阻断，不进入下一切片。
