# S2 官方 API 事实快照（第一阶段）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

状态：`阶段 1 raw capture 已完成并校验 1370 responses；用户授权的有限 DB2 字段扩展已完成配方、双物品变体/转换、current season 和 recipe 52446 min6 四个 bounded probe；min6 已验证 recipe output 与五档 crafting quality，并绑定固定 SimC 序列化证据，但副属性/美化语义、SimC build 对齐和来源兼容性仍未闭合；normalized snapshot 因全量 recipe output、item variant/static stats、tier conversion、Mythic+ cap/track 官方字段仍未闭合保持 blocked；候选发布和指针切换保持阻断`

**Goal:** 先冻结用户确认的 S2 产品内容选择，再只使用暴雪 World of Warcraft Game Data API 建立一个
可复算、可审计、有限范围的 `OfficialApiFactSnapshot`。它封存团本（包括巢穴）、大秘境、制造业和套装
四类范围内“可达神话终点”候选的官方事实与显式排除账本，为第二阶段提供唯一游戏事实输入。

**Architecture:** `S2ProductContentScopeV1` 只记录用户确认的官方对象选择与产品标签，不携带游戏
事实；原始 API 响应由 capture manifest 逐请求固定；纯本地的 normalizer 只读取该 manifest、选择策略
和原始响应，生成带内容身份的事实快照。任何 API 没有提供或无法唯一关联的事实都写成 `UNVERIFIED`，
不会向 SimC、Raider.IO、客户端数据、旧 S1/S2 候选或前端推断查询。

**Tech Stack:** Python 3 标准库（JSON、SHA-256、`unittest`）、仓库既有 Blizzard OAuth/Game Data
读取辅助函数的窄适配层、Node Harness packet 校验器。

## 玩家结果与阶段边界

玩家最终需要的是“可以信任为什么一件装备会出现在可选列表中”，而不是一个把不同来源互相佐证出来的
伪全量库。本阶段不会让玩家看到新装备、替换列表或模拟按钮；它只让后续阶段拥有一个能回答“官方 API
到底确认了什么、没有确认什么、为何排除”的唯一底座。

本阶段成功不等于 List A、装备解析、社区导入、SimC 任务、Manifest、候选部署或真实微信验收成功。
它的唯一交付是一个独立、不可变、可读但未发布的事实快照及其证据包。

## 全局约束

- S2 的来源范围、item membership、套装 membership 和官方 API 可见事实仍由 Blizzard Game Data API
  捕获响应裁决。对于 API 明确缺失且命中白名单的配方输出、品质/变体、强化兼容或 cap/track 字段，
  允许读取固定 Blizzard retail client DB2 字段；该 DB2 证据必须由
  `server/data/midnight-season-2/db2-field-allowlist-v1.json` 约束，Wago 只能作为 transport-only mirror，
  不得把第三方 schema 当作 authority，也不得接收 SimC、Raider.IO、Wowhead、新闻或现有 Catalog 作为事实输入。
- 产品只选择以下四类范围：8 个大秘境 Journal Instance（`1030`、`1041`、`1202`、`1304`、`1309`、
  `1311`、`1313`、`1322`）；团本范围内的潮缚石窟 Journal Instance `1317` 的 Encounter `2849` 和
  烈毒之渊 Journal Instance `1320` 的全部 Encounter；由官方专业/配方/产物关系发现的 `crafted`；
  以及 S2 官方 Item Set、职业归属、部位与效果关系组成的 `tier_set`。大秘境必须由官方回包确认
  `DUNGEON + MYTHIC_KEYSTONE`；潮缚石窟和烈毒之渊必须确认 `RAID + MYTHIC`，潮缚石窟产品层归入
  `raid` 但原始来源类型保留为 `lair`。任何不匹配都为
  `UNVERIFIED`，而不是按名称或旧样本修正。
- 其他当前赛季 Journal 内容一律记为 `OUT_OF_SCOPE_PRODUCT_CONTENT`，即使其原始类别是 `RAID` 或
  可达史诗难度。地下堡、狩猎、世界 Boss、普通地下城、Great Vault 和世界内容也必须记录为显式排除；
  Great Vault 不是独立装备来源，不能成为第五个 membership kind。`tier_set` 是独立 membership
  维度，可以与原始获取来源并存。
- 实例的 `MYTHIC`/`MYTHIC_KEYSTONE` 只验证来源归属。每个 item 仍须由独立的官方轨道/变体关系证明
  `mythicCapable=true`；不得用副本难度、Great Vault、SimC 成功或社区观察替代该 item-level 证明。
- “S2”只是任务标签；具体赛季、实例、物品、配方、套装、轨道和强化关系必须能追溯到官方响应中的
  reference。若 API 没有提供足以识别或关联它们的字段，结论为 `UNVERIFIED`。
- 不能给权威抓取设置会被静默接受的 item/page/sample 上限。遇到分页未闭合、扩展队列上限或响应不完整时
  必须 fail closed，状态为 `blocked`，不能把截断样本称为完整快照。
- 只允许在用户明确授权本次联网下载和本地写入原始响应后运行 live capture。离线 fixture、单元测试和
  `--dry-run-request-plan` 不联网；它们只能证明实现，不证明 S2 事实闭包。
- 不启动旧的 End Game capture chain，也不修改其候选、证据、runtime 或 Active Manifest；
  `server/data/midnight-season-2/source-policy.json` 只作为本次四类装备库范围的 pending scope record，
  不代表已经完成 live capture 或 promotion。不得修改
  `server/season_pve_official_capture.py`、`server/season_pve_official_evidence.py`、
  `scripts/capture-season-pve-official-snapshot.py`、`scripts/build-season-2-endgame-foundation.py` 或
  `server/season_endgame_candidate.py`。它们属于已 `blocked` 的旧多源候选链，不能被重命名、续跑或作为
  新阶段输入。
- 不改动 `server/websim_payload.py`，更不能在其中添加 S2 自动抓取、SimC、Catalog 或 health 行为。新
  live CLI 只能通过一个可注入的窄 adapter 调用其中既有的 OAuth/API helper，测试使用假 reader。
- 不创建 `SelectableCatalogCandidate`、`SelectableCatalogRelease`、`BrowseVariant`、Exact Registry、
  数据库迁移、SimC profile/probe/task、Active Manifest、现网 API 或前端改动。

## 唯一来源合同

| 结论 | 唯一 owner | 允许输入 | API 无法确认时 |
| --- | --- | --- | --- |
| S2 source、item、variant、轨道、套装、制造输出、强化关系 | `OfficialApiFactSnapshot` | 已固定的官方 raw response；仅对 API 缺失字段追加白名单内的官方 client DB2 投影 | `UNVERIFIED`，不进入下一阶段输入 |
| 产品选择哪些内容 | `S2ProductContentScopeV1` | 用户确认的官方对象 ID 与产品标签 | 未选择内容为 `OUT_OF_SCOPE_PRODUCT_CONTENT`；选择与官方回包不匹配为 `UNVERIFIED` |
| 选择内容是否存在、属于何类、有哪些 Boss/难度、是否达神话终点 | `OfficialApiFactSnapshot` | 已固定的官方 raw response | `UNVERIFIED`，不进入下一阶段输入 |
| 地下堡、狩猎、世界 Boss 排除 | `OfficialFactScopeV1` | 官方发现的 source relation | `OUT_OF_SCOPE_*` ledger row |
| SimC 能否执行、社区角色曾否穿戴 | 后续独立 owner | 本阶段禁止读取 | 本阶段没有结论 |

“同一 itemId 能被 SimC 或社区模板解析”不是官方范围、来源、轨道或变体事实。第一阶段不得因为它能运行
而提升任何记录；反过来，未来社区实例的 execution-ready 也不会反写本快照。

## 输入、输出和身份

### 1. 产品内容选择与范围策略：`S2ProductContentScopeV1` + `OfficialFactScopeV1`

新增 `server/data/midnight-season-2/s2-product-content-scope-v1.json` 与
`server/data/midnight-season-2/official-fact-scope-v1.json`。前者只存已确认的内容 selector 与产品
标签；后者只存通用排除与神话终点门禁。二者合在一起只定义“抓什么、如何归组和何时排除”，不定义
任何游戏事实：

```json
{
  "schemaVersion": 1,
  "productContentScopeRevision": "midnight-season-2-product-content-scope-v1",
  "seasonKey": "midnight-season-2",
  "journalInstanceSelections": {
    "mythic_plus": [1030, 1041, 1202, 1304, 1309, 1311, 1313, 1322],
    "lair": [{ "journalInstanceId": 1317, "journalEncounterIds": [2849] }],
    "raid": [{ "journalInstanceId": 1320, "journalEncounterSelection": "all" }]
  },
  "craftedSelection": { "kind": "official_recipe_output_relations" },
  "expectedOfficialConstraints": {
    "mythic_plus": { "journalCategory": "DUNGEON", "mode": "MYTHIC_KEYSTONE" },
    "lair": { "journalCategory": "RAID", "mode": "MYTHIC" },
    "raid": { "journalCategory": "RAID", "mode": "MYTHIC" }
  }
}
```

```json
{
  "schemaVersion": 1,
  "scopePolicyRevision": "midnight-season-2-official-fact-scope-v1",
  "seasonKey": "midnight-season-2",
  "authority": { "kind": "blizzard_game_data_api" },
  "excludedSourceKinds": {
    "delve": "OUT_OF_SCOPE_DELVE",
    "prey": "OUT_OF_SCOPE_PREY",
    "world_boss": "OUT_OF_SCOPE_WORLD_BOSS"
  },
  "nonMembershipKinds": ["great_vault"],
  "requiresOfficialMythicCap": true
}
```

内容策略可以列出上述数值 selector，因为它们表达用户的产品范围；不得列出副本/Boss 显示名、item、
掉落、轨道、属性、新闻链接、SimC hash 或社区样本。每个 selector 的实际名称、原始类别、Encounter、
难度和装备关系都必须由 capture 中的官方 relation 决定。每种来源的发现状态必须是
`verified_nonempty`、`verified_empty` 或 `UNVERIFIED`；`verified_empty` 只能由官方索引/关系明确证实，
不能以“暂时没有抓到”代替。

### 2. 原始捕获：`OfficialApiCaptureManifest`

live capture 已写入 1370 个原始 JSON，并生成通过 hash/bytes 校验的
[`official-api-capture-v8/capture-manifest.json`](https://api.chickenbro.cloud/wow-evidence/releases/2026-08-24-s2-equipment-library-evidence-v2/artifacts/releases/2026-08-17-s2-official-api-fact-snapshot/official-api-capture-v8/capture-manifest.json)。
v3/v7 的失败侧车作为过程证据保留；v8 只跟随当前 S2 season、8 个 Midnight skill-tier、13 个 S2 item
set 和当前 period，不扩展历史 season/skill-tier。每个 manifest entry 固定：

```text
requestKey = sha256(canonical(path, query, namespace, region, locale))
entry = {
  requestKey, path, query, namespace, region, locale,
  responsePath, responseSha256, responseBytes, capturedAt,
  paginationParentRequestKey | null, apiBuild | null
}
```

OAuth token、Authorization header、client secret、完整 request URL 中的敏感 query 均不得写入磁盘或
日志。capture 采用 bootstrap -> 官方 response 引用扩展 -> 分页闭合的 request plan；每个扩展请求必须
来自先前官方 response 中的 canonical reference。未知路径、重复 request key、遗漏分页、额外 raw file、
hash 不符或 namespace/locale 漂移都使 manifest 无效。

### 3. 规范化输出：`OfficialApiFactSnapshot`

`server/s2_official_api_fact_snapshot.py` 生成的 snapshot 至少有：

```json
{
  "schemaRevision": "s2-official-api-fact-snapshot-v1",
  "status": "verified | partial | blocked",
  "seasonKey": "midnight-season-2",
  "productContentScopeRevision": "midnight-season-2-product-content-scope-v1",
  "scopePolicyRevision": "midnight-season-2-official-fact-scope-v1",
  "officialApiFactSnapshotRevision": "s2-official-api-fact-snapshot:sha256:...",
  "captureIdentity": {
    "captureManifestSha256": "sha256:...",
    "region": "...",
    "locale": "...",
    "namespaces": ["..."],
    "parserRevision": "s2-official-api-fact-snapshot-v1",
    "capturedAtRange": { "first": "...", "last": "..." },
    "apiBuild": "... | null"
  },
  "sourceFacts": [],
  "itemFacts": [],
  "exclusionLedger": [],
  "unresolvedFacts": [],
  "counts": {}
}
```

每个 `itemFact` 必须包含 `itemId`、官方 variant/source/track/set/crafted/enhancement fields、
`factStatus`、`officialEvidenceRefs` 和逐字段 problem code。任一可选字段不应被伪造为空的“已验证”；
官方缺口使用 `UNVERIFIED`。`exclusionLedger` 必须可定位到官方 relation，并记录 `subjectKey`、
`sourceKind`、`reasonCode`、`officialEvidenceRefs`。

snapshot revision 只哈希 canonical scope、manifest 内容 hash、parser revision 和 canonical normalized
facts；`capturedAt`、文件名和输出路径不参与身份。相同内容重复构建必须得到相同 revision。仅当所有
范围内候选的必需游戏事实都 `verified` 且 raw capture 完整时，snapshot 才能是 `verified`；否则为
`partial`，而 capture 结构错误、截断或未经授权则为 `blocked`。第二阶段只接受 `verified` snapshot。

## 当前阶段切片记录

- 已完成：四类产品范围 selector、三类内容排除与 Great Vault 非 membership 合同。
- 已完成：官方 relation 分类、Lair 原始来源保留、tier_set 独立 membership、官方轨道 fail-closed 门禁。
- 已完成：本地 capture manifest 元数据/分页/hash 校验、确定性 snapshot revision、partial/blocked/UNVERIFIED 状态和无 SimC-ready 升级。
- 已完成：只读离线 CLI；它只消费本地 capture root，没有 `--live`，partial snapshot 保留输出但返回非零。
- 未完成：从真实 Blizzard API/有限 DB2 证据扩展并生成完整四类事实快照、完整 raw/DB2 fixture corpus、
  全量字段覆盖审计和阶段移交。

### 2026-08-19 有限 DB2 字段扩展

用户已授权在官方 API 字段缺口处进行有限 DB2 查询。新增的
`server/data/midnight-season-2/db2-field-allowlist-v1.json` 固定 Blizzard
retail client build `12.1.0.68914`、`exact` 过滤、允许的表/字段和官方 API
根事实派生的外键图；Wago `db2-find` 只作为 transport-only mirror，不能成为
事实 authority。适配器只保存字段投影、来源 body hash/bytes、查询身份和
field coverage，不保存原始 DB2 行，也不允许全表 CSV 或无界搜索。

已完成 recipe `52446`（Quel'dorei Softsteppers）的 min3 24-request 最小 probe，
并在同一 allowlist 下建立 min6 138-request exact probe：
`SkillLineAbility -> SpellEffect -> CraftingData -> crafted item`、五档
crafting quality、reagents、modified crafting slots 及有限 bonus-tree 图均有
字段级证据。min6 的 recipe output 和五档 quality 为 `verified`；
`Amplify Secondary Stat` 与 `Add Embellishment` 只记录为 observed capability，
不生成 semantic options，二者分别保持 `SECONDARY_OPTION_SEMANTICS_UNVERIFIED`
和 `EMBELLISHMENT_EFFECT_UNVERIFIED`。六条固定 SimC probe 能回读精确 item、装等和
静态属性，但运行时 `12.1.0.69299` 与 DB2 capture `12.1.0.68914` 不一致，且有
item-resolution warning，因此只证明序列化技术路径，不证明合法选项或 release readiness。
证据位于
[`recipe-52446-min6/capture-manifest.json`](https://api.chickenbro.cloud/wow-evidence/releases/2026-08-24-s2-equipment-library-evidence-v2/artifacts/releases/2026-08-19-s2-limited-db2-field-expansion/recipe-52446-min6/capture-manifest.json)，
汇总见
[`summary.json`](https://api.chickenbro.cloud/wow-evidence/releases/2026-08-24-s2-equipment-library-evidence-v2/artifacts/releases/2026-08-19-s2-limited-db2-field-expansion/summary.json)。

同一 v8 capture 现已生成只读 source inventory：观察到 442 个官方 item
identity（大秘境 247、团本含巢穴 130、tier_set 65），377 条去重后的来源
membership edge，以及 65 条 tier_set membership。制造业只能确认 793 个
recipe root，因 API 缺少 output item identity，不能把它们计入装备身份分母；
因此 `fourSourceCandidateTotal=null`、`finalVariantVerifiedCount=0`、
`simcReadyCount=0`，并保留 `OFFICIAL_API_RECIPE_OUTPUT_MISSING`。报告位于
[`official-capture-inventory-v1/inventory.json`](https://api.chickenbro.cloud/wow-evidence/releases/2026-08-24-s2-equipment-library-evidence-v2/artifacts/releases/2026-08-19-s2-official-api-fact-snapshot/official-capture-inventory-v1/inventory.json)，
不是 Catalog、Exact、Candidate 或 release 输入。

随后对官方 API 已引用的 Mythic+ item `159317` 与 S2 tier-set item `271481`
进行了 227-page/217-query 的 bonus-tree、level-selector、base static 和
conversion bounded probe；结果为 `partial`，变体 materialization 与转换保留仍未闭合。
对官方 current Mythic+ season `18` 进行了四表 exact probe，但四张 DB2 表均返回
零行，未推断 season-id remapping，`mythicPlusCapTrack` 继续为 `UNVERIFIED`。
三组证据位于
[`item-159317-271481/capture-manifest.json`](https://api.chickenbro.cloud/wow-evidence/releases/2026-08-24-s2-equipment-library-evidence-v2/artifacts/releases/2026-08-19-s2-limited-db2-field-expansion/item-159317-271481/capture-manifest.json)、
[`recipe-52446-min6/capture-manifest.json`](https://api.chickenbro.cloud/wow-evidence/releases/2026-08-24-s2-equipment-library-evidence-v2/artifacts/releases/2026-08-19-s2-limited-db2-field-expansion/recipe-52446-min6/capture-manifest.json) 和
[`summary.json`](https://api.chickenbro.cloud/wow-evidence/releases/2026-08-24-s2-equipment-library-evidence-v2/artifacts/releases/2026-08-19-s2-limited-db2-field-expansion/summary.json)。
这些 probe 都不是 release、Catalog、Exact、Candidate 或 Active Manifest 输入。

运行时与 CI/Harness 的边界保持不变：生产 runtime 读取 PostgreSQL/API 状态，永远不会去打开这些发布证据
URL；CI/Harness 仍可在 checkout 内消费本地 task packet、`artifacts/releases/...` 输出和
`scripts/project-harness.js` 的既有本地合同。

## 实施任务

- [x] **Task 0：冻结第一阶段任务合同与停止条件**

  **Files:**
  - Create: `artifacts/releases/2026-08-13-s2-official-api-fact-snapshot/requirement.json`
  - Create: `artifacts/releases/2026-08-13-s2-official-api-fact-snapshot/manifest.json`
  - Create: `artifacts/releases/2026-08-13-s2-official-api-fact-snapshot/evidence.json`
  - Modify: `docs/project-state.json`, `docs/roadmap.md`, `docs/plans/README.md`

  **Interfaces:** requirement 记录 `manualAcceptance.required=false`、无用户可见 runtime、无候选部署，
  并冻结本阶段的输入/输出/停止码；evidence 分开记录 fixture-local、live capture 和 phase-2 eligibility，
  不把前者升级为后者。

  **Steps:**
  1. 用 Harness 模板创建任务三件套，填写单一 slug、当前 Harness version、`manualAcceptance` 空集合，
     以及明确的 `not_applicable` 原因：本阶段没有新用户入口或运行时部署。
  2. requirement 的 acceptance items 必须包括：官方-only 输入审计、capture manifest 完整性、四类范围
     分类、三类显式排除、`UNVERIFIED` fail-closed、snapshot revision 可复算、无 Manifest/Catalog/SimC
     写入。不得把“真实 S2 已闭合”预填为 accepted。
  3. 在实施开始和每个输出生成后运行：

     ```bash
     node scripts/project-harness.js --check-requirement \
       --requirement-file artifacts/releases/2026-08-13-s2-official-api-fact-snapshot/requirement.json
     ```

  4. 在 evidence 中把未执行的 live capture 写成 `pending` 或 `not_applicable` 的准确原因；没有用户明确
     联网授权时，绝不产生“verified official capture”结论。
  5. 在完成前运行完整 packet check：

     ```bash
     node scripts/project-harness.js --check \
       --requirement-file artifacts/releases/2026-08-13-s2-official-api-fact-snapshot/requirement.json \
       --evidence-file artifacts/releases/2026-08-13-s2-official-api-fact-snapshot/evidence.json \
       --manifest-file artifacts/releases/2026-08-13-s2-official-api-fact-snapshot/manifest.json
     ```

- [x] **Task 1：先实现 S2 内容选择验证，再实现通用范围分类合同**

  **Files:**
  - Create: `server/data/midnight-season-2/s2-product-content-scope-v1.json`
  - Create: `server/data/midnight-season-2/official-fact-scope-v1.json`
  - Create: `server/s2_official_fact_scope.py`
  - Create: `tests/s2_official_fact_scope_test.py`
  - Create: `tests/fixtures/s2_official_api_fact_snapshot/product-content-scope-v1.json`
  - Create: `tests/fixtures/s2_official_api_fact_snapshot/scope-v1.json`

  **Interfaces:**

  ```python
  class S2OfficialFactScopeError(ValueError): ...

  def load_product_content_scope(path: str | Path) -> dict: ...
  def load_official_fact_scope(path: str | Path) -> dict: ...
  def classify_official_source(*, official_relation: dict, product_scope: dict, scope: dict) -> dict: ...
  def require_official_mythic_cap(*, official_track: dict | None) -> dict: ...
  ```

  `classify_official_source` 只返回 `verified_nonempty`、`verified_empty`、`UNVERIFIED` 或一条明确的
  exclusion；它只能用内容策略的数值 selector 与官方 relation 分类，不得接受自由文本名称、item list、
  SimC/社区字段作为分类依据。

  **Steps:**
  1. 先写 `tests/s2_official_fact_scope_test.py`：验证仅 8 个已确认的大秘境 selector、潮缚石窟的
     `1317/2849`、烈毒之渊 `1320/all` 能被纳入；验证潮缚石窟原始 `RAID` 只会因产品策略成为 `lair`，
     绝不改写其官方类别。
  2. 测试并实现约束验证：8 个大秘境必须是 `DUNGEON + MYTHIC_KEYSTONE`，潮缚石窟和烈毒之渊必须有
     `RAID + MYTHIC`；selector 缺失、Encounter 不匹配、难度缺失或类别漂移均为 `UNVERIFIED`，不按名称猜测。
  3. 验证任意其他当前赛季 Journal content 输出 `OUT_OF_SCOPE_PRODUCT_CONTENT`；地下堡、狩猎、世界 Boss
     分别输出既有 `OUT_OF_SCOPE_*`；`great_vault` 不生成 membership。
  4. 写两个 scope JSON 与 loader，拒绝未知 kind、重复 selector、selector 的显示名/item/掉落/轨道字段、
     allowed/excluded 重叠、`requiresOfficialMythicCap` 缺失、任何非 `blizzard_game_data_api` authority 和
     SimC/社区字段。
  5. 实现轨道门禁：官方字段确认可达神话终点才返回 `verified`；明确不能达到则写
     `EXCLUDED_NOT_MYTHIC_CAPABLE`；字段不存在或多义时写 `S2_OFFICIAL_TRACK_UNAVAILABLE`。
  6. 运行并预期全绿：

     ```bash
     python3 -m unittest tests.s2_official_fact_scope_test
     ```

- [ ] **Task 2：实现 raw capture manifest 校验与纯官方事实规范化器**

  **当前切片：** `[x]` 已完成离线 manifest 校验、规范化事实输入的快照构建和独立 snapshot validator；`[ ]` 仍需实现从官方 raw response/reference graph 到 `sourceFacts`、`itemFacts`、recipe/set/track/enhancement relations 的完整 normalizer。

  **Files:**
  - Create: `server/s2_official_api_fact_snapshot.py`
  - Create: `tests/s2_official_api_fact_snapshot_test.py`
  - Create: `tests/fixtures/s2_official_api_fact_snapshot/raw/`
  - Create: `tests/fixtures/s2_official_api_fact_snapshot/capture-manifest.complete.json`
  - Create: `tests/fixtures/s2_official_api_fact_snapshot/capture-manifest.incomplete.json`

  **Interfaces:**

  ```python
  class S2OfficialApiFactSnapshotError(ValueError): ...

  def canonical_json_sha256(value: object) -> str: ...
  def validate_capture_manifest(*, capture_root: Path, manifest: dict, scope: dict) -> dict: ...
  def build_official_api_fact_snapshot(*, capture_root: Path, manifest: dict, scope: dict) -> dict: ...
  def validate_official_api_fact_snapshot(snapshot: dict, *, scope: dict) -> None: ...
  ```

  **Steps:**
  1. 先写失败优先测试：hash mismatch、重复 `requestKey`、额外 raw file、缺失分页 continuation、
     namespace/locale 不一致、非官方 request path、缺少 source reference 都必须确定性拒绝。
  2. 写 canonical JSON/hash helper；它使用 UTF-8、稳定键排序和无空白编码。测试同内容不同 key order
     得到相同 hash，而 `capturedAt` 改变不改变 snapshot revision。
  3. 写 manifest verifier：完整性检查只能依据 manifest/文件/官方 response reference；不得读取任何
     `simc*`、`raiderio*`、`catalog*`、`client*` payload，也不得接受它们作为函数参数。
  4. 写 normalizer：先从官方 journal response 建立 8 个大秘境、潮缚石窟 `1317/2849`、烈毒之渊
     `1320/all` 的 `sourceFacts`，再从这些 verified source facts 扩展 item、recipe/set/track/enhancement
     relation；每一字段存 evidence reference。缺少 recipe 输出、套装、轨道、变体或强化关系时附加对应
     `UNVERIFIED` row，而不是创建默认值。
  5. 写 ledger：当前赛季 Journal 中未被产品内容选择命中的内容输出
     `OUT_OF_SCOPE_PRODUCT_CONTENT`；官方发现的地下堡、狩猎、世界 Boss row 分别输出
     `OUT_OF_SCOPE_DELVE`、`OUT_OF_SCOPE_PREY`、`OUT_OF_SCOPE_WORLD_BOSS`；已选择内容无法证明神话终点
     不是 exclusion 成功，而是 `UNVERIFIED`。
  6. 覆盖 verified、partial、blocked 三种 snapshot：只有 fixture 中每个必需 relation 完整时可以
     `verified`；任何官方事实缺口为 `partial`，capture 结构损坏为 `blocked`。运行：

     ```bash
     python3 -m unittest tests.s2_official_api_fact_snapshot_test
     ```

- [ ] **Task 3：提供离线构建 CLI、可复算输出与候选输入门禁**

  **当前切片：** `[x]` 已完成无 live 参数的本地 CLI、raw 文件 parity 校验、partial 非零退出和非官方输入拒绝；`[ ]` 仍需接入完整 raw fixture corpus 与第二阶段只接受 `verified` snapshot 的正式门禁。

  **Files:**
  - Create: `scripts/build-s2-official-api-fact-snapshot.py`
  - Create: `tests/s2_official_api_fact_snapshot_cli_test.py`
  - Create: `tests/fixtures/s2_official_api_fact_snapshot/expected-snapshot.verified.json`
  - Create: `tests/fixtures/s2_official_api_fact_snapshot/expected-snapshot.partial.json`

  **Interfaces:**

  ```text
  python3 scripts/build-s2-official-api-fact-snapshot.py \
    --scope server/data/midnight-season-2/official-fact-scope-v1.json \
    --capture-root <local-capture-root> \
    --output <snapshot.json>
  ```

  CLI 只读本地 capture root；没有 `--live`，也没有 SimC/Raider.IO/Catalog 参数。stdout 输出简短 JSON
  summary，stderr 输出无敏感 diagnostic，非 `verified` snapshot 返回非零退出码并保留可审计的 partial
  snapshot（结构性 manifest failure 则不写 snapshot）。

  **Steps:**
  1. 先写 CLI 测试：`--help`、未知参数、缺少参数、fixture verified、fixture partial、损坏 manifest、
     重跑相同 capture 的 revision 一致，以及无网络副作用。
  2. 实现路径边界：拒绝 scope/capture/output 逃逸、拒绝 output 覆盖 input raw、用原子临时文件 rename
     写 snapshot；不删除或修改 raw capture。
  3. 输出 counts：`candidateCountByKind`、`verifiedCountByKind`、`unverifiedCountByKind`、
     `excludedCountByReason`、`status`、`officialApiFactSnapshotRevision`。不要输出 List A count、
     `publicSimcReadyRate` 或任何模拟 readiness。
  4. 实现 `--require-verified`：默认允许生成 `partial` 诊断，指定后只要 status 不是 `verified` 就退出
     非零；下一阶段入口必须调用该门禁，不能自己检查一个松散 boolean。
  5. 运行：

     ```bash
     python3 -m unittest tests.s2_official_api_fact_snapshot_cli_test
     python3 scripts/build-s2-official-api-fact-snapshot.py \
       --scope tests/fixtures/s2_official_api_fact_snapshot/scope-v1.json \
       --capture-root tests/fixtures/s2_official_api_fact_snapshot/raw \
       --output /tmp/s2-official-api-fact-snapshot.json --require-verified
     ```

- [x] **Task 4：实现并执行受控 live capture adapter；raw capture captured，官方字段缺口保持 blocked**

  **Files:**
  - Create: `scripts/capture-s2-official-api-fact-snapshot.py`
  - Create: `tests/s2_official_api_fact_capture_cli_test.py`
  - Modify: `artifacts/releases/2026-08-13-s2-official-api-fact-snapshot/requirement.json`

  **Interfaces:**

  ```python
  class BlizzardGameDataReader(Protocol):
      def get(self, path: str, *, namespace: str, region: str, locale: str, query: dict) -> dict: ...

  def build_official_request_plan(*, scope: dict, reader: BlizzardGameDataReader) -> list[dict]: ...
  def capture_official_request_plan(*, plan: list[dict], output_root: Path, reader: BlizzardGameDataReader) -> dict: ...
  ```

  **Steps:**
  1. 写 reader-injection 测试，不产生网络请求：bootstrap -> 官方 reference 扩展 -> pagination 闭合；
     只允许 scope 定义的官方 Game Data namespace 和从 response 发现的 canonical reference。
  2. live CLI 默认只支持 `--dry-run-request-plan`；真正抓取必须同时传入 `--live`、显式 output root，且
     既有 Blizzard credentials 未配置时以 `S2_OFFICIAL_CAPTURE_CREDENTIALS_UNAVAILABLE` 失败，不写 raw。
  3. 通过一个仅在该 CLI 内的 adapter 调用既有 `blizzard_credentials_configured`、token 和 `blizzard_get`
     helper；不改 `server/websim_payload.py`，不让 app runtime 自动触发 capture。
  4. 拒绝 `--max-items`、`--max-pages`、`--sample`、自定义 URL、非官方路径和断点续抓后未重新校验的
     manifest。任何资源保护触发都为 `S2_OFFICIAL_CAPTURE_INCOMPLETE_LIMIT`，不是 success。
  5. **STOP / 已完成授权检查点：** 在实际执行 `--live` 或向本地写入任何网络响应之前，报告将要请求的
     官方 path 数、预计 raw 输出目录、凭据是否存在和回滚方式，并等待用户批准本次下载。没有该批准，
     用户已于 2026-08-17 明确授权下载并持久化官方 API 响应。
  6. 授权后 v8 capture 完成并写入 1370 个 raw 与 `capture-manifest.json`；manifest、hash、bytes 和范围
     audit 全部通过。793 个 recipe 没有显式 output item，486 个 item 没有 static stats/bonus/track，
     当前 Mythic+ period 只有 id/start/end，因此 snapshot normalizer 保持 blocked，不开始 Catalog/SimC 工作。

- [x] **Task 5：完成证据、局部审阅与阶段移交判定（raw captured / snapshot blocked）**

  **Files:**
  - Modify: `artifacts/releases/2026-08-17-s2-official-api-fact-snapshot/evidence.json`
  - Modify: `artifacts/releases/2026-08-17-s2-official-api-fact-snapshot/manifest.json`
  - Create: `artifacts/releases/2026-08-17-s2-official-api-fact-snapshot/snapshot-summary.json`
  - Modify: `docs/project-state.json`, `docs/roadmap.md`, `docs/plans/README.md`

  **Steps:**
  1. 把 snapshot identity、scope revision、capture manifest hash、candidate/verified/unverified/excluded counts
     和每个 blocker 写入 evidence；不将 `partial` 书写为 `verified`、`ready` 或 List A 可用。
  2. 在 project state 中明确区分 `implementation_local_verified`、`official_snapshot_partial`、
     `official_snapshot_verified` 和 `blocked`。只有 `official_snapshot_verified` 才能新增第二阶段
     requirement；旧 2026-08-12 candidate 继续保持历史 `blocked`。
  3. 运行本阶段完整的本地验证：

     ```bash
     python3 -m unittest \
       tests.s2_official_fact_scope_test \
       tests.s2_official_api_fact_snapshot_test \
       tests.s2_official_api_fact_snapshot_cli_test \
       tests.s2_official_api_fact_capture_cli_test
     node --test tests/project-state.test.js
     git diff --check
     ```

  4. 做一次 local CR：确认 diff 不修改旧 S2 candidate、generation 35、Catalog/Manifest/Exact registry、
     SimC、Raider.IO、WebSim runtime、数据库、部署和 Taro；确认所有 new input 都能落到一个官方 manifest
     entry hash。
  5. **移交规则：** 本阶段只完成 raw capture 与 evidence handoff；`snapshot.status` 尚未生成，因官方
     output/variant/cap 字段缺口保持 blocked。未创建第二阶段输入，不自动创建或执行 Catalog/Exact、SimC
     或候选发布；用户可看到 raw 计数、字段级 blocker 和排除边界，但没有 fallback 和 promotion。

## 验收矩阵

| 场景 | 期望结果 | 不能误报为 |
| --- | --- | --- |
| 官方 fixture 闭合 | deterministic `verified` snapshot 与稳定 revision | 真实 S2 capture 已完成 |
| API 缺少轨道/来源/配方/variant 关系 | `partial` + `UNVERIFIED` + evidence ref | SimC 或社区数据可补齐 |
| 官方发现地下堡、狩猎、世界 Boss | 对应 `OUT_OF_SCOPE_*` ledger row | 范围内候选或静默丢弃 |
| 抓取分页/manifest/hash 失败 | `blocked`，不产生可移交 snapshot | “样本覆盖完成” |
| 无授权或无凭据 | 无网络、无 raw 写入、`pending`/`blocked` 证据 | API 不可用的永久结论 |
| snapshot `verified` | 仅可作为第二阶段的输入资格 | List A、SimC、玩家模拟或 Active Manifest 已可用 |

## 回滚与保留

- 该阶段不碰活动指针，因此失败回滚就是不写新 snapshot、不生成第二阶段 packet、不发布任何目录。
- raw captures、capture manifest、partial ledger 和 evidence 均追加保留；不得覆盖同一 revision 的旧文件，
  也不得删除 2026-08-12 历史 blocked evidence。
- 若 parser/schema 修复，创建新的 parser revision 与 snapshot revision；历史快照和其未验证结论不可
  原地改写。
- 本次 live capture 已获得用户明确的网络下载/落盘授权，v8 raw manifest 已完成；用户随后批准了最小
  DB2 字段范围，当前完成 recipe、双物品变体/转换和 current season 三个 bounded probe。后续必须闭合全量 recipe output、item variant/static stats、
  tier conversion preservation 与 Mythic+ cap/track 字段，并分别建立 SimC evidence，才能考虑 normalizer
  或第二阶段输入。DB2 partial probe 不改变四类产品范围，也不授予 Catalog、Exact、Candidate、Active
  Manifest 或生产写入权限。
