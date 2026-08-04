# 装备模拟 Canonical Kernel 重设计

状态：`已完成（仅 pure Canonical foundation 与 source change-control final whole-branch PASS/APPROVED；原 Task 3 readiness NOT_READY，须按持久化重排计划通过复审后才可启动）`

**当前 replacement:** [Canonical Ownership Change-Control Plan](2026-08-04-equipment-simulator-canonical-owner-change-control.md) 与 [重复 Effect Subject 语义纠偏](2026-08-04-equipment-simulator-duplicate-effect-subject-correction.md) 已完成。Task 1 的 gate 只声明 `source_change_control_only`；final whole-branch re-review 为 PASS/APPROVED、0 findings。原 Task 3 readiness 已判定 `NOT_READY`，由 [Exact-first 持久化与运行链重排计划](2026-08-04-equipment-simulator-exact-first-persistence-resequence.md) forward-replace；其独立复审通过前不得启动。

**目标：** 在不改变 v1 identity、generation 35、Task 1 `exact-loadout-intent-v2` 字段结构和 Exact-first/Catalog 解耦方向的前提下，替换未发布的 Task 2 内部实现，让 Exact、Progression、Effect、Probe、CLI 和 Authority Envelope 只消费同一个 canonical 语言与同一类封存对象。

**用户结果：** 同一合法装备及依赖向量始终得到相同 identity；任意真实差异都改变 identity；非 canonical、未经 authority 验证或 runtime 不匹配的输入不能被静默修正或包装为 `ready`。

## 1. 为什么需要重设计

Task 1 已冻结 v1 兼容基线并建立 Catalog-independent 的 Exact v2 输入合同。Task 2 的实验实现随后通过五轮测试先行修复，把原有 16 条行为测试扩展到 66 条，并保持 23 条 v1/Track Authority 回归通过。但每轮独立审查仍能从另一个消费模块找到同类缺口：

- slot 有的路径使用 `CANONICAL_GEAR_SLOTS`，有的只验证非空 token；
- 有的路径拒绝 CR/LF，有的仍接受 Unicode line separator 或 control；
- 有的路径按原始字节验证，有的先 `strip`、`str`、排序或去重；
- 有的 owner 重建真实 Track Authority，有的只重算调用者自带 payload 的 hash；
- 任意 `dict` 可以跨越 Exact、Effect 和 Envelope 边界，迫使每个消费者重新解释一遍 schema。

剩余两个审查反例只是症状：非法 slot alias 仍可生成 progression，Unicode control/line separator 仍可穿过 Exact、Effect、Probe 和 CLI。根因是 canonical 语言和封存边界没有唯一 owner。

因此不得继续第六轮局部补丁。Task 2 内部代码尚未合并、部署或持久化，可以替换；Git 历史保留为失败证据，不做历史改写。

## 2. 固定边界

以下边界不因本次重设计改变：

- `selection-intent-v1`、v1 ExactItemInstance、ResolvedLoadout、SimulationSnapshot 的 canonical bytes/key 保持不变。
- generation 35、Phase 0-4 归档证据和活动 Manifest 指针保持不变。
- Task 1 `exact-loadout-intent-v2` 的 schema revision、字段集合、15 个核心槽和可选 off-hand 顺序保持不变。
- 合法 Task 1 fixture 的 canonical bytes/key 保持不变；原先可被 parser 接受、但包含非 canonical Unicode/control 的输入改为明确 `blocked`，这属于收紧非法输入语言，不是合法 identity 漂移。
- Exact 可模拟性不依赖 Catalog membership；Catalog、owner、observation 和 provenance 不进入 canonical identity。
- Import Adapter 可以解析外部文本；进入 canonical core 后禁止自动 trim、大小写转换、类型转换、排序、去重或默认补值。
- 原始 SimulationCraft 插件文本不持久化、不写日志、不进入 job、响应、诊断或 canonical payload。
- Task 3 persistence、migration、worker、API、Catalog admission 和 UI 在新版 Task 2 完成独立复审前不启动。

## 3. 方案比较与决策

### 方案 A：只抽取公共 helper

把 token、slot 和 Unicode 检查抽成几个函数，保留当前模块继续接收任意 `dict`。

优点是 diff 小。缺点是 Exact、Progression、Effect 和 Envelope 仍各自拥有 schema 解释权，调用者仍可绕过 factory 构造形状正确但语义错误的 payload。五轮复审已经证明这个边界不稳定，因此不采用。

### 方案 B：Canonical Kernel + sealed value objects

建立唯一 primitive/serialization kernel；每个 domain owner 只能通过 factory 把 raw payload 转为不可变、可重新验证的 sealed document。跨模块接口不再接收任意字典。

改动比 helper retrofit 大，但不需要新依赖、代码生成或数据库迁移，能直接消除重复解释和调用者自签 payload。采用此方案。

### 方案 C：JSON Schema/codegen

用 schema/codegen 同时生成 Python 和 TypeScript validator。

形式最完整，但会引入生成工具、生成物治理和更大的跨仓库变更；当前问题不需要这个复杂度，暂不采用。若未来需要第三种 runtime 消费同一合同，可重新评估。

## 4. 架构

```text
外部插件/Battle.net/observed input
              |
              v
       Exact Import Adapter
  （只在这里解析外部表达）
              |
              v
 exact-loadout-intent-v2 / Task 1
              |
              v
       Canonical Kernel
   primitive + bytes + seal
      /        |         \
     v         v          v
 ExactItem  Progression  EffectRecord/Aggregate
      \        |          /
       \       |         /
        ExactAuthorityEnvelope
                 |
                 v
        Task 3 Store（后续）
```

Canonical Kernel 是唯一 primitive、canonical JSON 和封存规则 owner；Exact、Track Authority adapter 和 Effect owner 仍分别拥有自己的业务 schema，但不能重新定义 token、slot、Unicode、整数、数组或 hash 规则。

## 5. Canonical Kernel

新增 `server/gear_canonical_kernel.py`，只负责纯函数和不可变文档，不读取数据库、Catalog、runtime process 或环境变量。

### 5.1 Primitive 规则

Kernel 提供以下唯一入口：

```python
canonical_identity_token(value, *, path, allow_empty=False, max_bytes=256)
canonical_report_token(value, *, path, allow_empty=False, max_bytes=256)
canonical_slot(value, *, path)
canonical_int(value, *, path, minimum, maximum)
canonical_ordered_list(value, *, path, item_rule, max_items)
canonical_set_list(value, *, path, item_rule, max_items)
canonical_mapping(value, *, path, exact_keys)
canonical_json_bytes(value)
content_key(prefix, canonical_bytes)
```

共同规则：

- 类型必须精确匹配；`bool` 不能冒充 `int`，整数不能被转成字符串。
- 检查原始字符串和原始 UTF-8 bytes，禁止先 `strip` 或 normalize。
- 输入必须等于自身 trim 结果；不允许首尾空白。
- 身份 token 使用显式 ASCII grammar。报告 token 只允许受控 ASCII 空格和标点；玩家名、显示名称等自由文本不得进入 Exact authority identity。
- 拒绝所有 C0/C1 control、DEL、Unicode `Cc/Cf/Cs`、`Zl/Zp` 以及 CR/LF。即使上层 pattern 将来放宽，control predicate 仍独立成立。
- 如合同允许非 ASCII bounded text，输入必须已经是 NFC；Kernel 只验证，不执行 normalize。
- ordered list 保持位置，不排序或去重。
- set list 必须在输入时已经按 canonical bytes 排序且唯一；否则 blocked。
- mapping 必须使用完全相同的 key set；未知和缺失字段都 blocked。
- canonical JSON 固定 `ensure_ascii=False`、`sort_keys=True`、紧凑 separators、`allow_nan=False`；禁止 `default=str`。

`CANONICAL_GEAR_SLOTS` 继续由 `server/gear_contracts.py` 拥有，Kernel 直接引用该常量。任何其他模块不得复制槽位集合或只用 token 替代 slot 校验。

### 5.2 Sealed document

Kernel 提供不可变的内部文档类型：

```python
@dataclass(frozen=True)
class SealedCanonicalDocument:
    schema_revision: str
    canonical_bytes: bytes
    content_key: str
```

构造器不作为普通 public API 暴露。每个 domain factory 返回：

```python
CanonicalResult[SealedCanonicalDocument]
```

`CanonicalResult` 只能是：

- `verified + document`；或
- `blocked + issues`。

不存在部分 document。Issue 固定为 `{code, path, recoveryAction}`，不得回显原始值。

加载已序列化文档时必须走 `verify_sealed_document`：严格 JSON decode、schema validator、byte-for-byte reserialize、prefix/hash 重算全部通过后，才恢复 sealed document。内容寻址证明内容一致，不证明来源可信；Task 3 store 以后仍负责 provenance、append-only 和读取授权。

消费者需要读取字段时，只能调用 Kernel 的 `verified_payload_copy(document, expected_schema)`；该函数再次检查 schema、bytes 和 key，并返回新建的 JSON copy。Sealed document 不暴露可变的内部 mapping，也不允许消费者缓存并修改解析结果。

## 6. Domain owners

### 6.1 Exact item

`server/gear_exact_item_instance.py` 保留 v1 public wrapper。v2 改为：

```python
seal_exact_item(exact_slot_payload) -> CanonicalResult[CanonicalExactItem]
```

规则：

- 直接消费 Task 1 slot 字段，不读取 `variantKey`、Catalog row、status、rowFamily 或 `simcOptions`。
- `gemIds/gemBonusIds/gemItemLevels` 是位置相关数组；长度和错位由 Task 1/Exact schema明确验证。
- `bonusIds/craftedStats/embellishmentIds/redirectedBaseStats` 是 set-like 字段，必须预先 sorted + unique。
- serializer input 只能由 sealed Exact 派生，不再作为 Envelope 的独立调用者输入。
- Task 1 没有 `craftedEffectIds` 字段。出现该字段在第一边界以具体 path blocked；合法 `craftedStats` 后续生成 governed `crafted_effect` subject。
- 任何字段变化都改变 exact bytes/key；listed/unlisted、Catalog 和 provenance 不改变 key。

### 6.2 Progression binding

`server/gear_exact_authority.py` 中的 progression factory 改为只接受 sealed Exact 和 strict Track Authority input：

```python
seal_exact_progression(
    exact: CanonicalExactItem,
    *,
    season_revision: str,
    gear_rule_revision: str,
    slot: str,
    has_crafted_source: bool,
) -> CanonicalResult[CanonicalProgressionBinding]
```

- slot 必须来自 `CANONICAL_GEAR_SLOTS`，大小写或 alias 不接受。
- factory 调用现有 `resolve_exact_instance_progression` pure owner，不复制 ladder、rank、crafted quality 或 Ascendant 规则。
- 绑定 production Track Authority rule revision、record key、完整 canonical input 和输出 progression state。
- Envelope 只接受 sealed progression；重载时通过同一个 factory/verification path 证明字节一致。

### 6.3 Static facts 与 serializer

静态事实由单独 factory 封存，fact key 使用 identity token，数值只允许有限整数或有限浮点且禁止 bool。serializer bytes 完全由 sealed Exact 派生，不允许调用者提交第二份 id/ilevel/options。

### 6.4 Effect records、probe 与 aggregate

`server/simc_item_effect_support.py` 拥有 effect schema，但全部 primitive 和 seal 调用 Kernel：

- subject kind 固定 `item|gem|enchant|embellishment|crafted_effect|set_bonus`。
- subject key/signature 只能从 sealed Exact 或整套 Resolver 的 sealed loadout 派生，不接受调用者自由构造。
- `craftedStats` 按 deterministic schema 生成 `crafted_effect` subject；每个 subject 独立要求 sealed support record。
- static、dynamic、unsupported record 都绑定 subject、variant、runtime、verifiedAt 和完整内容 key。
- runtime mismatch 一律 `unknown`；unsupported 的决定证据必须进入 aggregate key。
- `server/simc_item_effect_probe.py` 只负责差分判定；verified 前必须调用同一个 effect record factory。
- CLI 只有取得 sealed verified record 才输出 stdout/exit 0；其余状态非零且 stdout 为空。

### 6.5 Authority Envelope

Envelope 新接口不再接收任意 payload：

```python
seal_exact_authority_envelope(
    *,
    exact: CanonicalExactItem,
    static_facts: CanonicalStaticFacts,
    progression: CanonicalProgressionBinding,
    effect_support: CanonicalEffectAggregate,
    resolver_revision: str,
) -> CanonicalResult[CanonicalExactAuthorityEnvelope]
```

Envelope 只检查 sealed 文档之间的 key/revision 关系：

- exact key 完全相同；
- progression/static/effect 都绑定同一 exact；
- effect runtime、rule revision 和 resolver revision 完整；
- effect status 必须 verified；
- canonical payload 不含 owner、Catalog、observation 或 provenance。

Envelope 不再重复解释 itemId、slot、serializer、Unicode 或数组规则。

## 7. 数据流和信任边界

1. Import Adapter 接收原始插件文本，执行 65,536-byte 上限、已知行解析和 path-aware diagnostics。
2. Task 1 parser 产生结构化 Exact v2 intent；它不证明装备合法、静态事实完整或 effect supported。
3. 每个 slot 进入 `seal_exact_item`。非 canonical 输入在此停止。
4. Track Authority、static facts 和 effect owners 分别从 sealed Exact 建立 sealed dependency documents。
5. Envelope 只组合 sealed documents。
6. Task 3 以后只持久化验证通过的 canonical bytes/key；raw dict 进入 store 前必须恢复为 sealed document。

任何阶段失败都不产生 ready envelope，不使用相似 item、最高 variant、默认装等、Catalog metadata 或旧 runtime record 补值。

## 8. 错误和恢复

- `blocked`：输入本身非法、非 canonical、规则不相容或 authority binding 冲突。返回具体 path 和重新导入/修改选择动作。
- `unknown`：缺 effect authority 或 runtime revision 不匹配。不得转为 verified。
- `unsupported`：当前 runtime 明确不实现该 effect。证据必须封存并进入 aggregate key。
- Probe timeout/crash 属于执行失败，不产生 effect record。

Diagnostics 只包含代码、路径、subject kind 和恢复动作；不得包含原始插件行、玩家身份或自由文本 payload。

## 9. 验证策略

### 9.1 共享 mutation corpus

建立一份 Python/Vitest 可共同消费的 fixture，按字段类型枚举：

- string：首尾空格、CR/LF、C0/C1、`U+0085/U+0090`、`U+2028/U+2029`、format control、non-NFC、超长 bytes；
- slot：合法值、大小写、别名、旧 spelling、不存在值；
- int：bool、float、负数、0、上界外；
- ordered list：tuple、错位、错误类型；
- set list：乱序、重复、错误类型；
- mapping：未知 key、缺 key、非字符串 key；
- seal：改 payload 不改 key、改 key 不改 payload、错误 prefix/schema/revision。

对于消费同一种 primitive 的路径，同一 mutation 必须在 Task 1 Python/TypeScript、Exact、Progression、Effect、Probe、CLI 和 Envelope 的适用子集中得到预先声明的一致结果。不适用的 domain 字段不为凑矩阵而复制。

### 9.2 Identity properties

- 相同合法输入和依赖向量产生 byte-identical payload/key。
- 任一 identity-owning 字段变化都改变对应 key。
- Catalog/listed/unlisted/owner/observation/provenance 变化不改变 Exact key。
- 非 canonical payload 不与 canonical payload共享 key，因为前者不能被 sealed。
- v1 fixtures 和合法 Task 1 v2 fixtures零漂移。

### 9.3 Owner/static gate

增加 AST/owner-map 测试：

- 在本次新增或修改的 Task 2 consumer 范围内，只有 Kernel 能定义 primitive canonical validators 和 v2 canonical JSON/hash helper；既有 v1 owner 保持原样并由冻结测试保护；
- Task 2 consumer 不得对 identity 字段调用 `strip`、`str`、`sorted(set(...))` 或 `default=str`；
- 只有 `gear_contracts.py` 拥有 canonical slot 枚举；
- Probe、CLI 和 Envelope 不接受 raw effect/exact dict。

不引入 Hypothesis 或其他新依赖；使用确定性 mutation matrix，便于 CI 和审查重放。

## 10. 实施切片

新版 Task 2 拆成五个可独立审查的内部切片：

1. Kernel：primitive、canonical bytes、sealed document、mutation corpus；不迁移消费者。
2. Exact + Progression：v2 Exact factory、Track Authority binding、v1/Task 1 freeze。
3. Effect + Probe + CLI：subject derivation、record/aggregate seal 和差分证据。
4. Static facts + Envelope：只组合 sealed documents，删除独立 serializer input。
5. Consolidation gate：删除/禁止 module-local validator，运行全 mutation matrix、owner/static gate 和独立最终审查。

每个切片都使用 fresh implementer、spec review 和 code-quality review。一个切片未 clean，不进入下一个。Task 2 完成后才重新编号并启动原计划 Task 3。

## 11. 完成标准

- 原最终复审中的非法 slot alias 和 Unicode control/line-separator 反例全部在第一 owning boundary blocked。
- 所有历史 Task 2 对抗用例和共享 mutation corpus通过。
- 合法 Task 1 v2 bytes/key 和全部 v1 bytes/key 零漂移。
- Task 2 模块不存在第二套 primitive/slot/Unicode/canonical JSON owner。
- Envelope public API 不接受 raw dict 或独立 serializer payload。
- crafted-effect-bearing Exact 通过 governed `craftedStats` subject 完整到达 ready envelope；合同外 `craftedEffectIds` 明确 blocked。
- no Catalog dependency、no raw-profile persistence、no Task 3 store/migration/API/UI changes。
- 独立最终审查同时给出 Spec `PASS` 和 Code Quality `APPROVED`。

只有以上条件全部成立，roadmap 才能从 `待决策` 恢复为 `正在推进（Task 3）`。
