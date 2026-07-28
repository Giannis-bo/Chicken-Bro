# 装备模拟 Phase 2：ExactItemInstance 与 EnhancementSelection

状态：`正在推进`

日期：`2026-07-29`

## 1. 用户价值

社区高端玩家或个人已保存模板中的装备必须继续代表玩家实际穿戴的具体实例。
例如英雄 3/6 不能被目录中的英雄最高级 BrowseVariant 替换；宝石、附魔、美化和
制造副属性也必须作为该实例的 canonical 强化选择保留。

本阶段完成后，系统底层能够：

- 从 sealed Community/个人装备模板中确定性重建具体装备实例；
- 对同一具体实例生成稳定 `exactItemInstanceKey`，不受采集时间或展示文案影响；
- 将装备固有变体与可编辑强化分层，避免把制造副属性重新写回 BrowseVariant；
- 对缺少 bonus ID、轨道、装等、属性或强化证据的实例明确返回
  `partial` / `blocked`，不使用同 itemId 的其他变体补值。

当前微信入口、活动 Manifest 和公共 reader 在本阶段保持不变。

## 2. 当前事实

- Phase 1 已归档：
  `gear-catalog:sha256:2addca2ff52fdcc2d23c369572c88fba9919332927f07f10350d700654e5aa34`
  精确封存 613 个 ItemDefinition 与 1,309 个 BrowseVariant；40/40 shadow、
  资源、不可变、PR、合入和三方身份均通过。
- 活动 Gear Release 仍包含 48,555 条 `rowFamily=exact_instance` 历史/observed
  变体。Phase 2 只物化被 sealed Community 或个人模板实际引用的实例，不把全部
  observed 历史行复制成新的长期快照。
- Phase 0 已有 `project_template_exact_instances` 与 `audit_template_exactness`
  纯审计，可验证 itemId、variantKey、bonus IDs、progression、ilevel 和强化字段；
  它们是迁移输入，不是正式 ExactItemInstance identity/store。
- 当前 Selection Intent 只携带 itemId、variantKey 与 canonical option key。
  现有 Resolver/Track Authority/Enhancement 管理仍是规则 owner；新缓存不能建立
  第二套合法性规则。
- 个人装备模板属于账号 owner；本阶段只读解析其结构化 gear snapshot，并以内容哈希
  参与 shadow。不得把用户 ID、昵称、令牌或原始 owner 字段写入全局 Exact 缓存。
- 全局 `/api/data/health` 仍为 `partial`。本阶段只为 dormant Exact cache 生成独立
  证据，不接管旧 health owner。

## 3. 范围

### 3.1 必须实现

1. 新增纯确定性 Exact builder：
   - 从一个 Catalog-bound Gear Release snapshot、模板 Intent 和 option authority
     解析具体实例；
   - 复用 Track Authority，保留中间 rank、ilevel、bonus IDs 和 verified 静态属性；
   - canonicalize bonus、gem、enchant、crafted stats、embellishment 和 context；
   - 相同业务输入生成相同 identity、逐行 hash 和迁移报告。
2. 正式化 `EnhancementSelection`：
   - gem 顺序按插槽语义保留；
   - bonus IDs、crafted stats 与 embellishment IDs 按各自 SimC 集合语义归一；
   - enchant 为单值；
   - option key 只作 release-bound provenance，不进入跨 revision 的具体实例 identity；
   - gem/enchant/embellishment/crafted stats 的实际 SimC 值必须由 verified option 或
     sealed exact source 提供，不能由前端文本反推。
3. 新增 dormant append-only PostgreSQL cache：
   - canonical EnhancementSelection；
   - canonical ExactItemInstance identity；
   - Catalog/Rule-bound exact validation 与 verified static facts；
   - template scope/content identity/slot 到 ExactItemInstance 的无 owner 信息引用；
   - seal/load/verify、不可变 trigger、最小权限和有界 JSON。
4. 新增有界迁移与 shadow：
   - Community winner 必须全部分类；任一 silent drop 阻断；
   - 个人装备模板可以为零；若存在则每个结构化模板必须分类；
   - verified 模板的 slot/item/variant/ilevel/progression/enhancement 与旧链一致；
   - 缺证据模板保留 `partial` / `blocked`，不得被计为 exact；
   - 重复实例去重，未引用的 48,555 历史 exact 行不物化。
5. 将新 owner、migration、tests、CLI 和 evidence packet 纳入 Harness 控制面。

### 3.2 明确不做

- 不切换活动 Manifest、Catalog reader、Community reader 或个人模板读写路径。
- 不更新或重写 sealed Gear/Community Release 和现有 `app.build_templates`。
- 不实现 ResolvedLoadout、SimulationSnapshot、完整 SimC compiler 或任务迁移。
- 不把 BrowseVariant 最高级属性用于 ExactItemInstance。
- 不把 EnhancementSelection 作为可公开浏览的独立装备目录。
- 不查询或下载新的第三方数据。

## 4. Canonical 合同

### 4.1 EnhancementSelection

```text
enhancementSelectionKey =
  sha256(gemIdsInSocketOrder, gemBonusIdsInSocketOrder,
         gemItemLevelsInSocketOrder, enchantId,
         sortedUniqueCraftedStats, sortedUniqueEmbellishmentIds)
```

空选择也是一个合法的 canonical selection。数组长度不一致、非法 token、option key
与实际 SimC 值不一致时阻断。sealed source 中同一 `enchant_id` 出现多个值时，现有
source 已明确标记为 `source_only` / `unresolved_drop`，因此保留为
`ENHANCEMENT_SINGLE_VALUE_MALFORMED` 的 `partial` reference，不选择其中任一值，
也不物化 ExactItemInstance。

### 4.2 ExactItemInstance

```text
exactVariantSignature =
  sha256(itemId, sortedUniqueBonusIds, context,
         progressionState, ilevel)

exactItemInstanceKey =
  sha256(itemId, sortedUniqueBonusIds, context,
         progressionState, ilevel, enhancementSelection)
```

`catalogRevision`、rule revision、source URL、template ID、采集时间、名称和 UI 文案
不进入跨 revision 的实例 identity；它们进入 validation/provenance。

静态属性不进入实例 identity。具体属性由 `(exactItemInstanceKey, catalogRevision,
gearRuleRevision)` validation 封存，因此规则或证据修正不会伪造另一件玩家装备，
也不会 update 已封存的旧 validation。

`sourceVariantKey` 与 `finger1/finger2`、`trinket1/trinket2` 等穿戴位置是模板引用
provenance，只存在于 Template reference，不进入上述 validation。多个 source alias
或左右槽位指向同一 exact identity 时，共享同一 validation，不得因引用位置不同产生
validation conflict；真正不同的静态属性或 serializer input 仍然阻断。

### 4.3 Template reference

模板只用以下无 owner 信息的 canonical reference 参与 shadow：

```text
(catalogRevision, templateScope, templateContentHash, slot)
  -> exactItemInstanceKey + validationStatus
```

`templateScope` 仅为 `community` 或 `personal`。个人账号 ID、昵称、原始 template ID
和访问令牌不得写入全局 cache 或证据。

`verified` reference 必须带有 ExactItemInstance key；允许的 source evidence gap 使用
无 key 的 `partial` reference。candidate shadow 只有在所有模板/装备均分类、无
silent drop、只剩上述允许的 evidence gap 且 seal/load 精确回读时才可通过；报告必须
同时公开 `registryStatus=partial` 与 `evidenceGapCodes`，后续 loadout 只能消费
`verified` reference。

## 5. 实施顺序

1. RED：identity、SimC 语义 canonicalization、非业务字段排除、中间 rank、
   option/value mismatch、缺静态事实和 silent-drop 测试。
2. GREEN：实现纯 EnhancementSelection/ExactItemInstance builder。
3. RED/GREEN：实现四组 append-only cache 表与唯一 store 的 seal/load/verify。
4. RED/GREEN：实现 Community/个人模板只读 projector、引用去重和迁移报告。
5. 本地 focused/full 验证后绑定 immutable candidate HEAD。
6. 云端应用 repository-owned migration，读取同一 generation-32 snapshot，seal dormant
   Exact cache，并运行 Community/个人模板 shadow、资源、pointer fence 和精确回读。
7. 完成 CR、PR CI、合入、post-merge parity、清理和归档，再进入
   ResolvedLoadout + SimulationSnapshot。

## 6. 验收矩阵

| 门禁 | 通过标准 |
| --- | --- |
| 确定性 | 相同模板/snapshot 重建两次得到相同 selection、instance、validation、reference hash |
| 中间等级 | 英雄 3/6 等实例保留真实 progression、ilevel、bonus IDs 和静态属性 |
| 强化 | gem 顺序、enchant、crafted stats、embellishment 与 sealed source/option authority 一致 |
| Community | 活动 sealed Community 装备模板 100% 分类；verified 模板无 silent drop |
| 个人模板 | 允许零条；存在的结构化装备模板全部分类且不泄露 owner 信息 |
| Fail closed | 缺 identity、Track Authority、static facts 或 enhancement evidence 只产生 partial/blocked |
| 去重 | 相同 exact identity 只物化一次；未引用历史 exact 行不复制 |
| 写入安全 | 只新增 dormant append-only 行；旧 Release、模板与 generation-32 pointer 不变 |
| 资源 | 在既定 2,000,000,000-byte / 300-second 候选硬上限内，零无界临时残留 |
| 发布 | migration、代码、报告、PR/main/cloud identity 和 rollback 证据完整 |

## 7. 回滚

- 新表没有活动 pointer，当前 API/Resolver/模板继续读取 generation 32 旧链。
- 候选失败回滚代码/服务；已 sealed dormant row 保持不可变但无人消费。
- migration 只新增表、索引、trigger 和权限，不执行破坏性 down migration。
- 任一模板 silent drop、owner 泄漏、identity 不确定、资源超限或 pointer 漂移立即阻断。
