# 至暗之夜 S2 数据仓库与候选发布链设计

日期：2026-08-12
状态：设计稿，待用户确认后进入实施计划
范围：装备库、装备美化（embellishment）、附魔、宝石、套装、装等轨道

## 1. 目标与用户场景

12.1/S2 切换时，用户希望在装备工作台中选择真实的 S2 装备，并看到与该装备绑定的装等轨道、套装身份、附魔、宝石和美化选项。用户不应看到 S1 的旧来源被伪装成 S2，也不应因为数据尚未核验而得到一个看似完整但无法执行的 SimC 配置。

本任务建立一套独立的 S2 数据仓库和候选发布包：

- S1 数据保持不可变，只作为 last-known-good 基线；
- S2 使用新的 `seasonId`、`seasonRevision`、来源证据和依赖 revision；
- 数据采集、归一化、候选 Catalog、Exact Registry、Release 和 Manifest 依次绑定；
- `verified`、`partial`、`blocked`、`pending` 和 `UNVERIFIED` 保持原义；
- 候选包完成全部门禁前不切换活动 Manifest，不覆盖生产读模型。

本设计中的“美化”指战斗装备的 embellishment，不把外观收藏、幻化外观或房屋装饰混入战斗装备 Catalog。外观类奖励可以保留为独立的来源证据，但不能成为装备属性或 SimC 选择项。

## 2. 事实边界

### 2.1 官方来源负责的事实

Battle.net Game Data API 和已保存的官方客户端证据负责：

- item identity、名称、图标、槽位、护甲/武器类型、handedness；
- Journal、实例、首领、难度和掉落关系；
- 物品与套装的结构化关系、set identity 和 class membership；
- 宝石物品身份和官方静态属性描述；
- 配方、专业、工艺品输出物和可用的工艺修饰槽；
- S2 来源的官方引用、数据版本和公告时间证据。

官方来源不能单独证明完整的当前实例属性或 SimC 可执行性。

### 2.2 SimC 12.1 负责的事实

SimulationCraft Midnight/12.1 runtime 负责：

- item variant 的 `bonus_id`、`ilevel`、升级轨道和可执行 profile 语法；
- 变体的静态属性、socket、可执行附魔和美化 token；
- set bonus 在 SimC profile 中的可编译性；
- 对每个候选 item/variant 的执行结果和 runtime revision。

SimC 不能单独决定官方掉落来源、赛季 membership、职业合法性或套装身份。普通社区 profile 和观察样本只能作为发现输入，不得升级为 S2 权威。

### 2.3 仓库治理规则负责的事实

现有 `gear_track_authority.py`、`gear_rule_matrix.py`、`crafted_pve_membership.py` 和 release/catalog 合同继续作为治理 owner。S2 只能通过新的 season/rule binding 使用这些规则；不得在前端或请求处理时复制 S1 规则并推导 S2 结论。

## 3. S2 身份与 End Game 数据范围

固定逻辑 ID 为 `midnight-season-2`。最终 `seasonRevision` 不手写日期或版本号，而由规范化的 S2 season metadata、source policy、官方证据摘要和客户端 build 生成内容 hash，例如：

```text
season-midnight-season-2:<sha256-prefix>
```

每个 source、item pool、set、option 和 track record 都必须携带：

```json
{
  "seasonId": "midnight-season-2",
  "seasonRevision": "season-midnight-season-2:<hash>",
  "captureContext": {
    "capturedAt": "<timestamp>",
    "officialAnnouncementRefs": [],
    "clientBuild": "<build>"
  },
  "dataStatus": "verified|partial|blocked|pending",
  "sourceRefs": []
}
```

本任务不实现 S2 分阶段开放，也不由 Catalog 按官方解锁日期过滤数据。仓库一次性准备完整的 S2 End Game 装备池，官方公告中的日期只作为 `captureContext` 和审计证据保留，不改变候选是否进入 Catalog。

End Game 数据范围包括：

- Venomous Abyss 的所有可核验难度和 Raid Finder wing；
- S2 Mythic+ 轮换、Mythic 0、Great Vault 奖励池及其对应装等轨道；
- S2 Delves、Prey、Lair/World Boss 和其他当前治理范围内的高等级奖励池；
- S2 crafted 输出、工艺质量、工艺副属性和可用美化；
- S2 tier set membership、set bonus、宝石、附魔、美化和完整装等轨道；
- 其他能被官方来源和 SimC 12.1 共同绑定的 End Game equipment source。

外观收藏、幻化外观和房屋装饰仍不进入战斗装备 Catalog；若官方来源同时返回这些奖励，单独记录为排除证据。

## 4. 数据仓库布局

新增版本化 S2 数据根目录；S1 文件不改名、不复用、不原地覆盖：

```text
server/data/midnight-season-2/
  season.json
  source-policy.json
  official-membership/
  crafted-membership.json
  set-membership.json
  enhancement-options.json
  track-authority-input.json
  README.md

artifacts/releases/2026-08-12-midnight-season-2-data-foundation/
  requirement.json
  manifest.json
  evidence.json
  raw/
    blizzard/
    client-db2/
    simc/
  normalized/
  audits/
  candidate/
```

`raw/` 只保存带 checksum、来源 URL、请求 namespace、region/locale、抓取时间和 client build 的原始证据。`server/data/midnight-season-2/` 只保存可审阅、可复现的规范化输入和小型治理 allowlist；大体量原始响应留在候选证据包，不进入请求时读取路径。

## 5. 构建流水线

### 阶段 A：采集与封存

1. 读取完整 S2 End Game 范围的官方公告、Battle.net API、官方客户端/DB2 证据和 SimC 12.1 runtime identity。
2. 将每个响应写入隔离 staging，生成 SHA-256、请求参数、来源引用和 capture manifest。
3. 检查官方 client build、SimC runtime revision 和 API namespace 是否一致；不一致时保留证据但将候选标为 `partial/blocked`。
4. 不从 S1 membership、S1 item variant 或旧 SimC profile 自动推导 S2 membership。

### 阶段 B：构建来源与装备 Universe

1. 用 S2 source policy 建立 raid、dungeon、mythic_plus、delve、prey、lair/world boss、great vault、crafted、world content、vendor 等 source owner。
2. 以官方 Journal/Item/Recipe/Set 关系建立 source membership；每个来源保留 raw membership、verified membership、缺口和 exclusion reason。
3. 单独构建 S2 item identity 和 equipment eligibility；缺少护甲/武器类型、槽位或 class context 的不可进入 Browse membership。
4. 以官方 identity 加 SimC variant probe 形成 `item -> variant -> progressionState`，exact instance 仍不能扩展 BrowseVariant。

### 阶段 C：构建强化选项

所有强化项都是独立 option record，不把字符串塞回 item：

| 类型 | 权威事实 | 必须绑定 |
| --- | --- | --- |
| 宝石 | 官方 gem item metadata + SimC `gem_id/gem_bonus_id/gem_ilevel` | item identity、socket category、stat display、unique policy |
| 附魔 | 官方 spell/item enchant metadata + SimC `enchant_id` | 可附魔槽位、职业/专精适用性、来源 revision |
| 美化 | 官方配方/修饰槽或已证明的 built-in source + SimC token | 可美化槽位、source-only/editor-managed 分类、全身数量限制 |
| 工艺副属性 | 官方 recipe/customization + governed rule | recipe/output item、secondary-stat schema、quality/track |

只有 `metadataStatus=verified` 且 option 与 S2 revision 一致的选项才进入候选 Release。原始 SimC token 没有官方或既有权威绑定时只能进入诊断 evidence，不能进入默认选择。

### 阶段 D：构建套装

1. 从官方 tier/set identity 建立每个职业的 S2 set membership，至少包含头、肩、胸、手、腿等可用部位。
2. 将 set ID、class keys、source、难度/掉落关系和 item variant 分开保存；同一 item 关联多个冲突 set ID 时阻断该 item authority。
3. 由 SimC 验证 set bonus 的 profile 编译和效果入口，但不得用 SimC 名称猜测官方 set identity。
4. set bonus 统计只由 Resolver/Canonical Kernel 计算，前端不从名称或槽位数量自行拼接。

### 阶段 E：构建装等轨道

S2 使用新的 Track Authority binding：

```text
(seasonRevision, gearRuleRevision, trackAuthorityRevision)
```

每条轨道记录至少包含：`trackKey`、`progressionKind`、`rank/maxRank`、`itemLevel`、可用 source/slot、bonus evidence、官方引用、SimC probe identity 和 evidence status。

- 不复制 S1 的 263/276/289/298 数值；
- 不从通用 `trackRank`、名称或当前玩家选择反推 S2 轨道；
- 普通 Browse 只保留 governed maximum rank；
- 非标准轨道（工艺质量、Ascendant、赛季特殊升级）必须有独立来源和 slot/source eligibility；
- 任何 `itemLevel`、bonus ID 或 rank 冲突都生成 blocked record，而不是选择一个“看起来最合理”的形状。

### 阶段 F：候选 Catalog/Release

按现有候选链生成：

```text
official/SimC captures
  -> S2 normalized warehouse
  -> S2 Gear Release candidate
  -> S2 Catalog v3 candidate + Exact Registry
  -> 40 spec shadow/evidence
  -> candidate WebSim/WeChat smoke
  -> explicit acceptance
  -> controlled Manifest cutover
```

候选的 dependency vector 必须同时绑定：

- `seasonRevision`；
- `gearReleaseId`、`gearCatalogRevision`、`gearExactRegistryRevision`；
- `trackAuthorityRevision`、`gearRuleRevision`；
- `enhancementOptionRevision`、`setMembershipRevision`；
- `simcRuntimeRevision`；
- talent/catalog/serializer 等现有 release dependencies。

任何字段为空、跨 S1/S2、或来自不同 capture build 的组合均阻断候选 seal。

## 6. 用户可见状态与安全边界

- verified：可浏览、可进入 Resolve；
- pending：数据采集或 authority 绑定尚未完成，不可选择；它不表示“未来阶段暂不可用”，而表示当前证据链尚未闭合；
- partial：来源或属性覆盖不完整，只展示受限事实，不生成完整 SimC 结论；
- blocked：隐藏于默认选择，并保留可解释 blocker 给数据健康/管理端；
- stale：旧 S1/旧 capture 不得悄悄回流为 S2。

Candidate API 可以提供 S2 的 `seasonRevision` 和 readiness summary，但在 Active Manifest 仍为 S1 时不能让正式读路径混用两个 revision。

## 7. 验证与完成标准

### 数据完整性

- S2 所有 raw capture 有 checksum、sourceRef、capture time、build/namespace；
- source membership 的 verified/partial/blocked 差集可解释；
- 40 个专精的装备候选 traversal 完成，缺失项列出 source 和 blocker；
- verified variant 的 item level、bonus、stats、slot/type、source provenance 不缺失；
- verified gem/enchant/embellishment option 的 metadata 和适用槽位不缺失；
- tier set 无未绑定 class/set identity，无多 set 冲突；
- S2 Track Authority 的每个 public record 都有独立 evidence，未知轨道保持 blocked。

### 工程与发布

- 现有 S1 单元测试保持通过；
- 新增 S2 schema/normalization/track/enhancement/set/candidate gate 测试，先 RED 后 GREEN；
- Catalog/Exact Registry revision 可重复生成；
- shadow 过程中无写 SQL、无 active pointer 变化、无异步回流；
- candidate API、Resolve、community import、stat readiness 和 serializer 使用同一 dependency vector；
- S1 active Manifest generation、release identity 和生产读路径保持不变；
- `git diff --check`、Harness requirement/evidence 检查通过；
- 只有在用户明确验收后，才进入受控 Manifest cutover。

## 8. 回滚与失败策略

数据采集或候选构建失败时，保留 raw evidence 和 blocked audit，停止在当前构建步骤，不删除 S1 数据。候选 Release 未 seal 或 seal 后未 promote 都不影响线上；需要回滚时只回到 S1 last-known-good Manifest，不拼接 S1/S2 表或 option。

若 S2 某个 source、套装、强化项或轨道证据不完整，则只阻断相应 membership/option/track，不把整个仓库伪装成完整；但 candidate promotion 必须按 release gate 的要求处理整体缺口。

## 9. 主要实现 owner

- S2 season/source capture：`server/game-season.js`、`server/season_pve_official_evidence.py`、`scripts/capture-season-pve-official-snapshot.py`；
- membership/universe：`server/season_pve_universe.py`、`server/crafted_pve_membership.py`；
- track：`server/gear_track_authority.py`；
- enhancement：`server/gear_enhancement_management.py`、`server/gear_release_tool.py`、`server/gear_rule_matrix.py`；
- set/authority/read model：`server/gear_catalog_revision.py`、`server/pg_gear_authority_loader.py`、`server/websim_payload.py`；
- candidate/release/evidence：`server/gear_release*.py`、`scripts/gear-catalog-revision.py`、`scripts/catalog-candidate-evidence.py`。

实施时优先增加 S2 输入契约和构建器，再接入候选 release；不先修改活动前端，也不通过请求时计算补齐数据。

## 10. 外部依据

- Blizzard：<https://news.blizzard.com/en-us/article/24294369/the-shadows-deepen-midnight-season-2-begins-august-18>
- SimulationCraft Midnight branch：<https://github.com/simulationcraft/simc/tree/midnight>
- SimulationCraft Expansion Options：<https://github.com/simulationcraft/simc/wiki/ExpansionOptions>
- SimulationCraft Equipment：<https://github.com/simulationcraft/simc/wiki/Equipment>
