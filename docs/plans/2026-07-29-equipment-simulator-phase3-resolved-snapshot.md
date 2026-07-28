# 装备模拟 Phase 3：ResolvedLoadout 与 SimulationSnapshot

状态：`正在推进`

日期：`2026-07-29`

## 1. 用户价值

玩家保存的装备模板必须对应一套明确、合法且可重放的具体装备，而不是一组会随目录、
规则或 SimC 版本变化的松散字段。发起模拟时，系统必须封存实际执行的装备、天赋、
角色、场景、编译器和 SimC runtime 身份；同一输入重复提交必须得到字节一致的 profile。

本阶段完成后：

- 只有 canonical 槽位都绑定 Phase 2 `verified` ExactItemInstance、且当前 Resolver
  整套合法性通过的组合能成为 `ready` ResolvedLoadout；
- partial、stale、blocked、revision conflict 或不完整组合仍可作为草稿存在，但不能
  生成 SimulationSnapshot；
- 26 个支持专精由后端生成不可变 canonical SimC 输入；14 个不支持专精在 Runner
  task 创建前确定性阻断；
- 已执行任务保存的 snapshot 不随模板、Catalog、Rule、Compiler 或 Runtime 更新而变。

入口和用户旅程保持不变：装备模拟负责配装、导入和保存；SimC 页面只执行已保存模板。

## 2. 当前事实

- Phase 1 已归档
  `gear-catalog:sha256:2addca2ff52fdcc2d23c369572c88fba9919332927f07f10350d700654e5aa34`，
  包含 613 个 ItemDefinition 和 1,309 个 BrowseVariant。
- Phase 2 已归档
  `gear-exact-registry:sha256:ef910dd82d402f035959e628295e7d2b05dd74aca02463163c452da2d5eeb88a`：
  1,242 条模板装备引用全部分类，1,187 verified，55 explicit partial，零 silent drop。
- 现有 `gear_resolver` 已拥有整套合法性、静态属性、约束和 serializer input；现有
  canonical profile/task 链已能重新 Resolve 并在 Runner 前执行专精支持门禁。
- 旧 `gear-resolved-snapshot-v1` 仍绑定 Gear Release/variant 身份，尚未绑定正式
  CatalogRevision、ExactItemInstance、compiler revision 和不可变任务 snapshot。
- 全局 `/api/data/health` 仍为 `partial`；本阶段不得将局部合同通过包装成全局健康。

## 3. 范围

### 3.1 必须实现

1. 纯确定性 `ResolvedLoadout` builder：
   - 输入职业/专精、当前 verified Resolver snapshot、Phase 2 exact registry 引用和
     Catalog/Rule revision；
   - 按 `CANONICAL_GEAR_SLOTS` 固定顺序绑定 exact key 与 enhancement selection；
   - 精确核对 itemId、ilevel、bonus/gem/enchant/crafted/embellishment serializer
     字段和 Catalog-bound static facts；
   - 复用 Resolver 的整套合法性、约束、静态属性和 evidence 结论，不建立第二套规则；
   - 任何 partial reference、缺槽、重复槽、key/serializer/revision 不一致均阻断。
2. 纯确定性 `SimulationSnapshot` 与 canonical compiler：
   - identity 绑定 ResolvedLoadout、talentProfileKey、characterContext、
     scenarioOptions、compilerRevision、simcRuntimeRevision；
   - 固定 actor、talent、gear、preparation、scenario 与执行参数的行/字段顺序；
   - 保存 canonical input、输入 hash、所有 revision 和结果 identity；
   - 26 个支持专精可创建 ready snapshot，14 个不支持专精返回 `unsupported`，未知专精
     返回 `blocked`。
3. append-only PostgreSQL owner：
   - 封存/load/verify ResolvedLoadout 与 SimulationSnapshot；
   - executed snapshot 只允许追加结果绑定，不允许重写 canonical input 或 revision；
   - 运行角色最小权限，UPDATE/DELETE/TRUNCATE 默认禁止。
4. 有界 shadow 与任务兼容：
   - 对活动 80 个 Community 模板逐一构建 loadout；含 55 条 partial 引用的模板明确
     blocked，其他模板不得 silent drop；
   - 对可执行模板生成两次 snapshot，证明 identity/input hash/bytes 一致；
   - 新任务 request 保存 snapshot identity 和 canonical input；runner 只执行该
     immutable input，dedupe fingerprint 绑定 snapshot key；
   - 旧任务读取和历史结果保持兼容。
5. Harness、owner map、migration、tests、候选部署、真实 SimC、PR/main/cloud parity、
   rollback 与归档证据完整。

### 3.2 明确不做

- 不切换活动 Catalog/Community/Season Manifest pointer。
- 不修改 Phase 1/2 已封存行，不把 55 条 partial 引用猜成 exact key。
- 不在前端生成或修补 SimC profile。
- 不改变装备模拟、模板保存、SimC 和任务列表的页面入口。
- 不在本阶段删除旧 Resolver；旧 reader 淘汰与单一 Manifest cutover 属于下一阶段。
- 不下载第三方数据或安装新依赖。

## 4. Canonical 合同

```text
resolvedLoadoutKey =
  sha256(classKey, specKey, orderedSlotExactInstanceKeys,
         orderedEnhancementSelectionKeys, ruleRevision, catalogRevision)

simulationSnapshotKey =
  sha256(resolvedLoadoutKey, talentProfileKey, characterContext,
         scenarioOptions, compilerRevision, simcRuntimeRevision)
```

`ResolvedLoadout` 的公开状态仅为 `ready` 或 `blocked`。ordered slots 必须使用
`CANONICAL_GEAR_SLOTS`；单件双手武器可由既有 Resolver readiness 明确省略 off_hand，
不得由新 builder 自行猜测。

compiler 只消费 `ready` loadout 的 `serializerInput`。允许字段顺序固定为：
`id, ilevel, bonus_id, gem_id, gem_bonus_id, gem_ilevel, enchant_id,
crafted_stats, embellishment, redirected_base_stats`。所有 profile 使用 LF，去除尾随空格，
并以单个末尾换行结束。

## 5. 实施顺序

1. RED：loadout identity、slot order、exact/serializer parity、partial/missing/revision
   fail-closed、static totals 测试。
2. GREEN：纯 ResolvedLoadout builder 与 verified exact registry adapter。
3. RED/GREEN：canonical compiler、snapshot identity、26/14 support matrix 和字节确定性。
4. RED/GREEN：append-only store/migration、任务 request/fingerprint/runner snapshot 绑定。
5. 本地 focused/full verification，绑定最终 immutable candidate HEAD。
6. 云端 migration、80 模板 shadow、26 真实 SimC/14 阻断、runtime/API/health/timer、
   rollback和 file SHA parity。
7. CR、PR CI、合入、post-merge 验证、清理和归档；自动进入单一 Manifest cutover。

## 6. 验收矩阵

| 门禁 | 通过标准 |
| --- | --- |
| Loadout identity | 同一 ordered exact 组合两次得到相同 key/row hash |
| Exact-only | 只消费 Phase 2 verified reference；partial/blocked 无 key 且不能 ready |
| 合法性 | Resolver 非 verified、aggregate legality blocked 或 profile readiness 非 ready 必须阻断 |
| Serializer parity | 每槽 itemId 与所有 canonical SimC 字段逐字匹配 exact validation |
| 属性 | 整套静态属性来自 verified exact validation，且与 Resolver verified totals 一致 |
| Snapshot identity | talent/character/scenario/compiler/runtime 任一变化都会改变 snapshot key |
| Canonical bytes | 相同 snapshot 的 profile bytes 和 hash 完全一致 |
| 支持矩阵 | 26 supported 可进入 runner；14 unsupported 在 task insert/runner 前阻断 |
| 任务兼容 | 新任务持久化 snapshot；旧任务读取/结果不变；dedupe 绑定 snapshot key |
| Community shadow | 80/80 模板分类，ready/blocked 数量闭合，零 silent drop |
| 发布 | migration、候选、真实 SimC、PR/main/cloud、回滚和 cleanup 证据完整 |

## 7. 回滚

- 新 Loadout/Snapshot 表和 request 字段为 additive；切回旧代码后旧任务仍按原字段读取。
- 活动 Manifest pointer 不变；候选失败不影响 Catalog、Community 或现有模板。
- snapshot/input append-only；错误候选通过代码回滚和停止新写入处理，不更新历史行。
- 任一 identity、serializer、support-policy、真实 SimC 或 pointer parity 失败立即阻断。
