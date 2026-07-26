# 装备静态事实统一证据登记与编译设计

> 状态：设计已获用户逐段确认，待书面复核与实施计划。
>
> Harness 分类：Strict。
>
> 当前范围：装备静态事实与能力证据。本文不授权实现、部署或活动 Manifest 切换。

## 1. 背景与用户问题

玩家在装备详情中选择精确装备变体后，应看到该变体真实的装等、静态属性、宝石槽、附魔和美化能力。当前链路已经有 PostgreSQL catalog、能力规则、Resolver、Gear Release、API 和 Taro 消费层，但“证据”一词同时指代：

- PostgreSQL 中的 Battle.net、SimulationCraft 和赛季规则来源记录；
- item / variant payload 中的 `socketEvidence` 等能力推导输入；
- Resolver 每次生成的 Evidence Ledger；
- Gear Release 中的 source evidence digest；
- health/admin 中的 blocker 与诊断状态。

这些对象职责不同，却在多个 owner 中重复保存或解释同一事实。2026-07-26 的只读线上核验已确认一个代表性冲突：

- `itemId=250033`、`variantKey=void_upgrade-298`；
- compact browse payload 报告 `hasSocket=false`；
- canonical Resolver 对相同精确变体报告 `socketCount=1`；
- Taro 当前会优先把 `hasSocket=false` 解释为零孔，因此隐藏真实可用的宝石配置。

用户可见伤害不是“缺少更多证据文案”，而是同一个事实被多个组件分别维护后产生不同答案。目标是消除分布式事实所有权，而不是继续增加跨组件一致性补丁。

## 2. 设计目标

1. 为装备静态事实建立唯一的证据登记 owner。
2. 将不可变来源原件、来源解析结果和最终事实明确分层。
3. 由唯一 Fact Compiler 生成 Canonical Facts。
4. 复用现有 immutable Gear Release、Manifest、shadow、原子指针和回滚机制封存并发布事实。
5. Resolver、API、Taro 和 health 只消费已发布事实，不重新解释原始证据。
6. 明确区分已确认的 `false/0`、证据缺失和证据冲突。
7. 让局部能力缺口只阻断对应能力，不无条件阻断整件装备。
8. 让“待核验”可以自动追溯和收敛，但自动 Worker 无权直接修改事实或活动发布。
9. 相同输入必须产生相同 Fact Hash；无内容变化的日常对账不得制造新 Release。
10. 迁移期间允许短期双算，但任何时刻只有一个线上事实权威，并在切换后删除旧 writer/reader。

## 3. 非目标

第一阶段不构建全项目通用 Claim 平台，也不纳入：

- 社区玩家样本和排行榜证据；
- SimC 任务运行结果、DPS 或报告；
- Warcraft Logs 报告与事件；
- 炸鸡队长或其他聊天回答的 `evidenceRefs`；
- 用户个人角色、模板或历史数据；
- 新的 Fact Release 类型、第二套 Manifest 或第二套活动指针；
- 公开用户发起的“申请核验”操作；
- 自动修改 compiler policy、产品代码或活动 Manifest。

SimulationCraft 的精确物品或 bonus 探针输出可以作为装备静态事实的来源 Artifact；这不等于把 SimC 任务结果纳入本设计。

## 4. 术语与唯一职责

| 名称 | 定义 | 唯一 owner |
| --- | --- | --- |
| Evidence Artifact | 一个来源在一个 revision 下的不可变原件，按内容哈希去重 | Evidence Registry |
| Evidence Observation | parser 从一个 Artifact 中提取出的、面向一个装备 subject 和 factType 的标准化陈述 | Observation Parser |
| Canonical Fact | Fact Compiler 根据允许的 Observation 与规则生成的唯一事实 | Fact Compiler |
| Gear Release | 封存一批 Canonical Facts 的现有不可变装备发布 | Gear Release 控制面 |
| Resolution Proof | Resolver 针对一次选择投影出的事实引用与合法性证明 | Resolver |
| Evidence Gap | unresolved Fact 对缺少输入或冲突条件的内部操作记录 | Gap Queue |

现有 `gear-evidence-ledger-v1` 在迁移后只承担 Resolution Proof 视图，不再拥有或维护另一份装备事实。后续可以在兼容窗口结束后评估更名，但本设计不要求立即修改公开合同名称。

## 5. 总体架构

```text
Battle.net / SimC probes / governed season rules
                         |
                         v
                Evidence Artifact
                         |
                 versioned parser
                         v
                Evidence Observation
                         |
              factType compiler policy
                         v
                  Canonical Fact
                         |
              existing immutable Gear Release
                         |
           existing Active Season Manifest pointer
                         |
      +------------------+------------------+
      |                  |                  |
      v                  v                  v
   Resolver         browse/API read model  health/admin
      |                  |
      +---------+--------+
                v
               Taro
```

数据流只能从上游向下游流动。Canonical Fact、Resolver 结果、API 字段、前端状态和 Gap Queue 都不得反向写成 Evidence Artifact 或 Observation。

## 6. 组件边界

### 6.1 Source Collectors

Source Collector 只负责获取来源原件并提交 Artifact：

- 不生成 Canonical Fact；
- 不决定 `verified`；
- 不覆盖既有 Artifact；
- 不把来源字段缺失自动解释成 `false/0`；
- 不读取活动前端状态作为来源。

### 6.2 Evidence Registry

Evidence Registry 是 PostgreSQL 中的逻辑 owner，不要求成为独立网络服务。它负责：

- 以 payload hash 幂等保存 Artifact；
- 保留 source type、source revision、season revision 和采集时间；
- 保留显式撤销或 supersede 关系；
- 保存 parser 产出的 Observation；
- 提供按 subject、factType、revision 查询的有界接口；
- 禁止凭据、access token、Cookie 或其他秘密进入持久化 payload。

### 6.3 Observation Parser

Parser 只把 Artifact 转换为 Observation：

- parser revision 是 Observation 身份的一部分；
- parser 修复通过重放已有 Artifact 生成新 Observation，不要求重新访问外部来源；
- 解析失败产生结构化问题，不写默认 Observation；
- 同一 Artifact 与 parser revision 必须产生确定性结果。

### 6.4 Fact Compiler

Fact Compiler 是 Canonical Fact 的唯一 owner：

- 只消费 Observation 与版本化 compiler policy；
- 不访问网络、当前时间、前端状态或活动请求；
- 不建立全局来源排名；
- 为每个 factType 声明允许来源、组合方式、`false/0` 成立条件、冲突处理和阻断范围；
- 生成确定性 Fact Hash；
- unresolved Fact 产生结构化 Evidence Gap，但不自行采集来源。

### 6.5 Gear Release

现有 Gear Release 正式承担 Canonical Fact Release 的职责：

- 不新增第二种 Release；
- 不新增第二套 Manifest 或指针；
- candidate、shadow、risk classification、compare-and-swap、rollback 继续复用；
- Release row 保存消费所需 Canonical Fact 和有界 provenance 引用；
- 原始 Artifact 不复制进每个 Release row。

### 6.6 Consumers

Resolver、Authority Loader、browse serializer、Taro 和 health/admin：

- 只能消费活动 Gear Release 中的 Canonical Fact；
- 不解析原始 Artifact；
- 不读取 mutable staging payload 作为第二事实源；
- 不根据缺字段推断 `false/0`；
- 不维护 `hasSocket`、`canEnchant`、`canEmbellish` 等独立 truth。

若兼容 API 暂时保留 `hasSocket`，它只能在 serializer 中由已发布 `socketCount > 0` 确定性投影，不能独立存储或参与判断。

### 6.7 静态事实与运行时合法性

Fact Compiler 不取代 Resolver 的构筑级动态规则。

Canonical Fact 负责：

- 精确 item / variant 身份、装等与静态属性；
- 物品可进入的槽位；
- 固有 socket count；
- 物品是否具备附魔或美化能力；
- 内置美化、套装归属和 option 的静态适用范围；
- 可供 Resolver 使用的 canonical option identity 与静态效果。

Resolver 继续负责：

- 当前选择是否超过 socket capacity；
- gem unique group；
- class/spec runeforge 限制；
- 当前构筑的全局美化数量与冲突；
- 双持、双手武器和其他跨槽位组合规则；
- selection intent 与已发布 Fact 是否一致。

Fact Compiler 不接收玩家当前选择，Resolver 不读取原始 Evidence。

## 7. 数据合同

以下字段名是设计合同；实施计划可以在保持语义和身份边界不变的前提下选择具体 PostgreSQL 表名。

实现锚点：纯契约 owner 位于 `server/gear_evidence_registry.py`。`canonical_fact_key(...)` 只散列 season、subject 和 fact type；`fact_value_hash(...)` 独立散列 value/status；`provenance_hash(...)` 独立散列选中的 Observation 引用及 compiler policy revision。`build_evidence_artifact(...)`、`build_evidence_observation(...)` 和 `build_canonical_fact(...)` 仅构造规范化 JSON，不访问网络、时钟或前端状态。

### 7.1 Evidence Artifact

```json
{
  "schemaRevision": "gear-evidence-artifact-v1",
  "artifactId": "gear-artifact:sha256:...",
  "sourceType": "battle_net_item|simc_item_probe|simc_bonus_probe|season_rule",
  "sourceIdentity": "bounded source identity",
  "sourceRevision": "source-specific revision",
  "seasonRevision": "midnight-season-1",
  "capturedAt": "RFC3339 timestamp",
  "payloadHash": "sha256:...",
  "payload": {}
}
```

约束：

- `artifactId` 绑定 source identity、revision 和 payload hash；
- 同一 Artifact 重复写入必须复用；
- Artifact 内容不可更新；
- 更正通过新 Artifact 与 `supersedesArtifactId` 表达；
- 明确撤销通过独立 invalidation 记录表达，不删除原件。

### 7.2 Evidence Observation

```json
{
  "schemaRevision": "gear-evidence-observation-v1",
  "observationId": "gear-observation:sha256:...",
  "artifactId": "gear-artifact:sha256:...",
  "subjectKey": "item:250033/variant:void_upgrade-298",
  "factType": "socket_count",
  "observedValue": 1,
  "parserRevision": "gear-socket-observer-v1",
  "sourceScope": "exact_variant",
  "status": "accepted"
}
```

约束：

- Observation 必须引用存在的 Artifact；
- `subjectKey` 必须是 canonical identity；
- `sourceScope` 必须区分 base item、exact variant、slot rule 等范围；
- malformed、out-of-scope 或被撤销来源不能产生 accepted Observation；
- parser 不决定最终 Fact 状态。

### 7.3 Canonical Fact

```json
{
  "schemaRevision": "gear-canonical-fact-v1",
  "factKey": "gear-fact:sha256:...",
  "subjectKey": "item:250033/variant:void_upgrade-298",
  "seasonRevision": "midnight-season-1",
  "factType": "socket_count",
  "value": 1,
  "status": "verified",
  "observationRefs": ["gear-observation:sha256:..."],
  "compilerRuleRevision": "gear-capability-matrix-v3",
  "factValueHash": "sha256:...",
  "provenanceHash": "sha256:...",
  "impactScope": "socket_only",
  "problemCode": ""
}
```

允许状态只有：

- `verified`；
- `unresolved_missing`；
- `unresolved_conflict`。

已确认的不适用使用 `status=verified` 加 `value=false` 或 `value=0` 表达。不得用 unresolved、空值或缺字段替代已确认的 false。

`factKey` 是稳定语义身份，只绑定 season revision、subjectKey 和 factType，不绑定 value、status、Observation 或 compiler revision。Gap Queue 因此可以在重编译前后持续引用同一事实。

`factValueHash` 绑定 subject、factType、value 和 status；`provenanceHash` 单独绑定被选中的 Observation 集合。compiler rule revision 进入 Gear Release dependency vector。新增一个结果相同且未改变选中 provenance 的重复来源不得制造用户可见能力变化。

### 7.4 Evidence Gap

```json
{
  "schemaRevision": "gear-evidence-gap-v1",
  "gapKey": "gear-gap:sha256:...",
  "factKey": "gear-fact:sha256:...",
  "status": "pending|running|retryable|terminal",
  "problemCode": "artifact_missing",
  "missingRequirement": {},
  "attempt": 0,
  "nextAttemptAt": "RFC3339 timestamp"
}
```

Gap Queue 是操作状态，不是事实或证据来源。消费者不得读取 Gap Queue 来替代 Canonical Fact。

## 8. 第一阶段 factType 策略

| factType | 允许输入 | 编译语义 | unresolved 影响 |
| --- | --- | --- | --- |
| `item_identity` | Battle.net 结构化物品数据 | 精确 identity 必须一致 | 阻断精确变体 |
| `slot_compatibility` | 结构化 inventory/weapon/armor 类型与版本化槽位规则 | 规则计算，不从名称推断 | 阻断精确变体 |
| `variant_track` | 当前赛季轨道规则与精确来源 Observation | item、track、ilvl 必须一致 | 阻断精确变体 |
| `static_stats` | 精确 itemId、variantKey、bonus/crafted identity 的 SimC 探针 | 只接受精确变体属性 | 阻断可执行 SimC；UI 显示属性待核验 |
| `socket_count` | 显式 socket、SimC bonus 映射、适用的当前赛季槽位规则 | 合并已证明的精确容量；缺字段不等于零 | 只阻断宝石 |
| `enchant_capability` | 装备部位规则、职业/专精限制、合法 option catalog | 规则与 option identity 联合计算 | 只阻断附魔 |
| `embellishment_capability` | 制造业元数据、内置美化分类、限额规则 | 区分内置与可选美化 | 只阻断美化 |
| `enhancement_option` | Battle.net / SimC option identity、静态效果和适用范围 | 生成 canonical gem、enchant、embellishment option；不执行玩家当前选择限制 | 只阻断引用该 option 的功能 |
| `allowed_enhancement_options` | 已验证 capability、option facts 与静态槽位适用规则 | 为精确 item/variant 生成允许 option identity 集合 | 只阻断对应强化类别 |
| `item_set_membership` | Battle.net 结构化 set membership | 多个可信不同 setId 为 conflict | 阻断套装结论与相关执行 |

每个策略必须声明：

- allowed source types；
- source scope；
- combination mode；
- closed-world / `false/0` 条件；
- conflict policy；
- impact scope；
- compiler rule revision。

不存在全局 `Battle.net > SimC > rule > observed` 排名。来源是否适用由 factType 决定。

## 9. 稳定性、失效与重编译

装备静态事实没有时间 TTL。已验证事实不会仅因 `checkedAt` 变旧而退回 unresolved。

只允许以下事件触发受影响 factType 重编译：

1. `seasonRevision` 改变；
2. 新 Artifact 的 payload hash 与已有有效输入不同；
3. parser revision 改变；
4. compiler rule revision 改变；
5. Artifact 被显式 supersede 或 invalidated；
6. 原先缺失的 Observation 被补齐。

确定性约束：

```text
same selected Artifacts
+ same parser revisions
+ same compiler policies
+ same season revision
= same Observations, Facts and fact snapshot hash
```

每日 timer 可以运行对账，但当 fact snapshot hash 未变化时：

- 不产生新的有效 Gear Release；
- 不切换 Manifest；
- 不让前端状态变化；
- 只记录 bounded no-op 结果。

## 10. 用户可见合同

用户不接触 Evidence、Observation、Fact Hash、problem code、Gap Queue 或“申请核验”操作。

精确 `itemId + variantKey` 的能力映射固定为：

| Canonical Fact | 用户文案 | 交互 |
| --- | --- | --- |
| `verified` 且支持 | 展示真实选项 | 可选择 |
| `verified` 且不支持 | 不可用 | 不可点击 |
| `unresolved_missing` | 待核验 | 不可点击 |
| `unresolved_conflict` | 待核验 | 不可点击 |

结构事实 unresolved 的精确变体不得进入可选候选。`needs-variant`、partial 占位、原始 blocker 和同装等技术重复变体不得泄漏到玩家候选列表。

## 11. 自动追因与修复闭环

Fact Compiler 生成 unresolved Fact 时，幂等产生 Evidence Gap。根因与允许动作如下：

| problemCode | 含义 | 允许动作 |
| --- | --- | --- |
| `artifact_missing` | 缺少所需来源原件 | 有界重新采集 Artifact |
| `source_unavailable` | 外部来源暂时不可用 | 退避重试 |
| `parser_unhandled_shape` | Artifact 已存在但 parser 无法解析 | 重放新 parser；无新 parser 时进入代码修复 |
| `observation_conflict` | 可信 Observation 冲突 | 停止自动裁决，等待人工规则/来源判断 |
| `compiler_policy_missing` | factType 或 source scope 未被 policy 覆盖 | 需要新 compiler rule revision |
| `projection_contract_regression` | Gear Release、Resolver 或 API 投影不一致 | 阻断候选；代码修复 |

自动 Worker 只能：

- 获取或登记 Artifact；
- 重放 Artifact；
- 生成 Observation；
- 请求 Fact Compiler 重编译；
- 构建候选 Gear Release。

自动 Worker 永远不能：

- 直接把 Canonical Fact 改成 verified；
- 修改活动 Gear Release 或 Manifest；
- 覆盖冲突 Observation；
- 用默认值关闭 Gap；
- 自动修改 compiler policy 或产品代码。

闭环完成条件：

```text
unresolved Fact
-> Evidence Gap
-> new/replayed Artifact and Observation
-> verified Fact
-> Candidate Gear Release
-> Resolver/API/Taro shadow pass
-> existing Manifest promotion policy
```

用户状态只在新的活动 Gear Release 生效后变化。

## 12. 迁移策略

迁移采用“短期双算、单一线上权威、候选验证、原子切换、删除旧路径”。

### 12.1 Slice 0：现状刻画

- 固定当前活动 Gear Release、Manifest、API、Resolver 和 Taro 合同；
- 记录全量 fact coverage；
- 建立已知差异清单，至少包括 `250033 + void_upgrade-298`；
- 区分应保持 parity 的事实和应纠正的旧错误。

### 12.2 Slice 1：Dormant Registry 与纯编译器

- 新增 additive PostgreSQL schema；
- 新增 Artifact、Observation、Fact 和 Gap 纯合同；
- 新增 factType policy 与 fixture；
- 不修改活动读写链路。

### 12.3 Slice 2：单向导入与 shadow facts

- 将当前 accepted PG 来源单向登记为 Artifact；
- 重放 parser 生成 Observation；
- 构建 shadow facts；
- 不把 Canonical Fact 反向写成 Evidence；
- 不构建活动 Release。

### 12.4 Slice 3：全量 old/new shadow

差异必须归为：

- `expected_parity`；
- `intentional_correction`；
- `newly_exposed_gap`；
- `regression`。

不得为了 shadow 全绿复制旧错误或把新暴露缺口默认成 false。

### 12.5 Slice 4：Candidate Gear Release

- 只有新 Fact Compiler 写候选 Gear Release；
- 活动 Manifest 继续指向旧 Release；
- 验证 Authority Loader、Resolver、browse/full API、Taro、health、timer 和 no-op 行为。

### 12.6 Slice 5：Manifest 原子切换

- 按现有 risk classification 与 compare-and-swap 切换；
- 保留旧 Manifest 作为 rollback target；
- Registry append-only 数据不删除；
- 失败时切回旧 Manifest，不修改历史 Artifact。

### 12.7 Slice 6：Caller-proof 淘汰

通过 caller-proof 删除：

- 独立 `hasSocket` truth；
- item/variant 中旧能力证据解释 writer；
- serializer 和 Taro 的本地能力推断；
- 从 Canonical Fact 反向生成 Evidence 的路径；
- 已无调用方的旧 evidence payload。

迁移完成标准包含“没有长期双写”，而不只是新路径可用。

## 13. 错误处理与安全边界

- Registry 写入失败：不得产生 Observation 或 Fact；活动 Release 不变。
- Parser 失败：记录 bounded problem；不得生成默认 Observation。
- Compiler 缺输入：生成 `unresolved_missing`，不得静默 false。
- 可信输入冲突：生成 `unresolved_conflict`，不得 latest-wins 或多数投票。
- 候选投影不一致：`projection_contract_regression` 阻断发布。
- 来源暂时不可用：重试有上限；达到上限保留 terminal root cause。
- Artifact payload 必须在持久化前移除凭据和秘密。
- API、health 和用户 UI 不返回原始 Artifact payload。
- 公共 GET、Resolve、页面刷新和装备点击不执行采集、重放或修复写操作。

## 14. 内部可观测性

`/api/data/health` 保持只读，并以 bounded aggregate 暴露：

- 各 factType 的 verified / unresolved missing / unresolved conflict 数量；
- pending / running / retryable / terminal Gap 数量；
- oldest gap age；
- top problem codes；
- active/candidate Gear Release 与 fact snapshot hash；
- no-op、candidate、blocked 和 promoted 的最近运行状态。

Admin 明细可以显示：

- factKey、subjectKey、factType；
- 受影响 itemId、variantKey；
- compiler rule revision；
- observation refs 和 artifact refs；
- root cause、允许动作和下一次重试时间。

Admin 与 health 都不能成为另一份事实 owner。

## 15. Harness 验证与验收

这是 Strict 任务，因为涉及 PostgreSQL schema/write path、Gear Release、Resolver、public API、Taro、worker/timer、candidate 部署和 Manifest 回滚。

### 15.1 自动验证

1. Artifact 不可变、按 hash 去重、supersede/invalidation 可追溯。
2. Artifact 重放在相同 parser revision 下产生相同 Observation。
3. 每个 factType 覆盖 verified true、verified false/0、missing、conflict 和非法来源。
4. 相同输入产生相同 Fact、fact value hash、provenance hash 和 fact snapshot hash。
5. no-op 对账不生成新有效 Gear Release。
6. Gap Queue 幂等、fenced、重试有上限，Worker 无直接 Fact/Manifest 写权限。
7. 完整活动装备库完成 old/new shadow，所有差异有唯一分类。
8. Authority Loader、Resolver、browse/full API 对相同精确变体消费同一 Fact。
9. Gear Release 中的 enhancement option identity、静态效果和 allowed option refs 与 Resolver 使用值一致。
10. `needs-variant`、partial 占位和同装等技术重复变体不进入用户候选。
11. caller-proof 证明切换后没有旧事实 writer/reader。

### 15.2 Candidate 与运行验证

候选证据至少记录：

- exact branch、commit、tree 和 runtime file parity；
- additive migration 与 rollback；
- Registry/Observation/Fact/Gap counts；
- factType coverage 与 top problem codes；
- old/new shadow 分类；
- candidate Gear Release、Manifest 与活动指针未误切换；
- API、Resolver、health/admin、worker/timer、日志和资源状态；
- no-op 与实际内容变化两条运行；
- rollback 到旧 Manifest；
- `WOW_DEPLOY_START_ASYNC_SYNCS=0` 下无非预期 backflow。

### 15.3 用户可见验收

1. `250033 + void_upgrade-298` 在 browse、Resolve 和 Taro 中统一为 `socketCount=1`。
2. verified true 展示真实选项。
3. verified false/0 展示“不可用”。
4. missing/conflict 展示“待核验”且不可点击。
5. 一个能力 unresolved 不影响其他 verified 能力。
6. 结构事实 unresolved 的变体不进入可选候选。
7. 真实微信装备详情完成候选、变体、宝石、附魔、美化和局部待核验状态验证。

## 16. 回滚

- Schema 只做 additive migration；首次切换前不删除旧表或字段。
- 活动回滚只切回旧 Active Manifest。
- Artifact 与 Observation 为 append-only，不在回滚时删除。
- 若新 compiler 或消费者失败，停止新候选发布并恢复旧 Manifest。
- 旧 writer/reader 仅在新链路稳定、用户验收和 caller-proof 完成后删除。
- 删除旧路径后如需代码回滚，必须使用保留兼容读取窗口的前一已验证版本；不得恢复长期双写。

## 17. 已拒绝方案

### 17.1 分布式证据维护加一致性扫描

拒绝原因：只能发现副本差异，不能消除多个事实 owner。

### 17.2 单一原始证据服务供所有组件自行解释

拒绝原因：统一了存储，但 Resolver、API 和前端仍会形成不同语义。

### 17.3 全局来源优先级

拒绝原因：不同来源只适合证明特定 factType；socket、static stats、set membership 和 enchant 不能共用一个 ranking 算法。

### 17.4 新增独立 Fact Release

拒绝原因：会引入 Gear Release 与 Fact Release 的一致性、双指针和双回滚问题。

### 17.5 用户主动“申请核验”

拒绝原因：普通用户不应理解或操作内部证据治理；公开请求也不得直接触发重型写任务。

## 18. 最终决策摘要

- 第一阶段只覆盖装备静态事实与能力。
- Registry 使用 immutable Artifact + normalized Observation。
- Fact Compiler 是唯一事实 owner，并按 factType 使用版本化策略。
- 现有 Gear Release 是 Canonical Fact Release。
- 静态事实没有时间 TTL。
- 结构事实 unresolved 阻断精确变体；能力事实 unresolved 只阻断对应功能。
- 用户只看到可用、不可用、待核验。
- 自动 Worker 只能补充证据和重编译，不能直接修改 Fact 或活动发布。
- 迁移允许短期双算，但始终只有一个线上权威，并最终删除旧路径。
