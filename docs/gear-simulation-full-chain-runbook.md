# 装备模拟全链路 Runbook

## 适用范围

覆盖装备 catalog、canonical resolver、release train、社区模板导入、异步属性快照、SimC serializer、PostgreSQL 同步、health、发布和回滚。

稳定数据规则见 [装备数据库治理](gear-database-governance.md)，产品与路由关系见 [职业专精架构](builds-architecture.md)。

## 不变规则

- Runtime 是 PostgreSQL-only；SQLite 只允许作为显式离线迁移源或备份输入。
- 装备事实先在后端归一，前端只消费 typed payload，不实现第二套职业、槽位、强化或来源规则。
- `verified` 必须有可追溯 source、当前赛季归属、结构化变体和可执行字段。
- 缺 metadata、变体、属性、来源或兼容证据时返回 `partial` / `blocked` 与明确 problem。
- Read API、health 和页面加载不得触发同步、写库或外部下载。
- Resolver、serializer、import 和 snapshot worker 都 fail closed；展示可用不等于 SimC-ready。
- 生产写库前备份实际 PostgreSQL target；代码与 DB 回滚分别处理。

## 权威链路

```text
Battle.net + SimulationCraft + governed rules + observed evidence
  -> PostgreSQL catalog / release manifest
  -> GET /api/websim/gear
  -> POST /api/websim/gear/resolve
  -> canonical selection + profile readiness
  -> POST /api/websim/gear/stat-snapshots
  -> immutable verified snapshot or explicit fail-closed outcome
  -> /api/websim/profile -> SimC task
```

- `selection-intent-v1` 只接受选择意图；客户端提交的 `itemSetId`、属性、SimC 选项、合法性、readiness、证据或 claims 一律拒绝。
- winner attribute audit 是 Release 后的只读后台证据链：仅封存 candidate winner 的 `profileHash` / `gearHash` 变化、完整身份和 canonical 装备/强化输入可写去重 intent；它不属于 `selection-intent-v1`、Resolver 或小程序交互请求。
- `wow-gear-release-refresh.service` 成功后通过 `OnSuccess=wow-attribute-rule-audit.service` 触发一轮有界 PG worker。worker 至多领取少量 fenced intent、只读 Battle.net Profile，先对齐种族/等级/装备实例/装等/bonus/gem/enchant，再调用确定性属性解释器；不调用 SimC，不改 catalog/template/Release/Manifest。
- `blocked_missing_evidence`、`blocked_source_unavailable` 与 `inconclusive_input_mismatch` 都是审计终态，不阻断 winner election、模板公开、导入或切装。只有相同完整输入下的 `confirmed_mismatch` 形成内部 health finding，并阻止该 revision 的未来规则 promotion；已有发布规则需新的 rule revision 或明确 feature-hide 才能改变。
- `selectionSignature`、`resolvedGearSignature` 和 `profileSignature` 分别绑定选择、解析 authority、角色/天赋/serializer/SimC/stat policy 依赖，不允许用一个模糊 hash 替代三层失效边界。
- `gear-result-envelope-v1` 的 HTTP 语义已在 Phase 3A `POST /api/websim/gear/resolve` 与 canonical Profile mode 生效；旧 Profile body 仍保持原 shape。
- `gear-rule-matrix-v1` 固定按 10 条显式纯函数规则执行，只返回 ordered legality results，不生成 Resolved Snapshot、属性、套装归属、Evidence Claims、SimC lines 或 readiness。
- Phase 2A 新增 `server/gear_resolver.py` 与 `server/gear_evidence_ledger.py`：固定执行 base item → verified variant → verified overlay → effective capabilities → legal enhancements，并输出结构化静态属性、canonical `itemSetId`、constraints、serializer input 和五组 Evidence Claims。它们不接受连接、store、route 或文件系统参数，也不生成完整 profile 字符串或 DPS。
- verified variant 缺少 `resolvedStats`、overlay 缺少 immutable source ref、overlay 与 base 的 canonical set identity 冲突、option 非法或 evidence record 缺失时必须 fail-closed；非法 enhancement 不得污染静态属性或 SimC options，dynamic effects 不得折算为静态 stats。
- Phase 2B 新增 `server/pg_gear_authority_loader.py`：在一个 PostgreSQL read-only transaction 中，用三条 static domain query 批量读取 Authority Context；1 槽与 16 槽的 cold budget 都是 3，warm cache hit 只执行 revision query，不允许 per-slot SQL。
- `AuthorityContextCache` 同时受 entry count 与 canonical serialized bytes 限制，cache key 绑定完整 Dependency Vector 与 Selection Signature；missing/unavailable/incomplete authority 不缓存。loader 只消费结构化 `itemStats`，不解析展示用 `statSummary`；source 的 `status` 或 `sourceStatus` 至少一项必须显式为 `verified`，`sourceStatus=source_reference` 作为来源类别单独保留，不能遮蔽另一字段的 verified 证据，缺失状态按 `unknown` 阻断。每件 item 最多投影 8 条显式 verified source，优先与所选 variant 同源且最近，避免历史 source 无界膨胀；非法数值类型不得静默清洗为空属性后放行。
- 公共 observed template 的 `variantKey` 是 PG 原始 key 经既有 `normalize_option_value` 得到的 public alias。loader 必须在同一条静态数组 SQL 中同时接受 exact raw key 与该 alias，仍以 itemId 绑定匹配；任何 alias 碰撞、wrong-item 记录或缺失 authority 都 fail-closed，重复 `(itemId, variantKey)` pair 在查询前去重且不增加 SQL 往返。
- item 的装备类型、护甲/武器类型、handedness 与等价槽必须复用现有 Battle.net structured payload helper，不能从名称或当前玩家选择反推。`finger1/finger2`、`trinket1/trinket2` 共用等价槽 authority；one-hand weapon 的 item authority 可进入主手/副手，最终是否允许双持仍由 Rule Matrix 的 class/spec rule 决定；two-hand weapon 必须让 profile readiness 正确免除空副手。
- canonical tier membership 只接受显式 verified tier source，或 `source_type=tier_set` 且 `authority=Battle.net Game Data API`、`setId` 非空的结构化 membership。loader 在同一 item/variant SQL 中聚合所有可信 setId；0 个表示无套装证据，1 个进入 canonical `itemSetId`，多个冲突必须把 item authority 整体阻断。source evidence 每个 source type 只保留最新一条，总数仍最多 8。
- Phase 2B 的 `PostgresCacheStore.get_gear_authority_context`、`gear_resolver_runtime_authority` 和 `build_websim_profile_response_from_resolved_snapshot` 已由 Phase 3A `server/gear_runtime.py` 统一编排。resolved-snapshot facade 仍只消费后端 Resolver 生成的 `serializerInput.gearItems`，委托现有 serializer，并以 golden parity 锁住兼容输出；不得出现第二套规则或客户端 snapshot 快捷路径。
- loader 返回的 `compatibility-pg-live-v1` 明确是当前 PG live state 的过渡兼容视图，`formalActiveManifest=false`；不可冒充 Phase 4 才拥有的 immutable Active Season Manifest。
- 既有 `server/websim_payload.py`、PostgreSQL selectors 和 observed-only public read model 继续提供 browse 事实；Phase 3A 只增加 backend-owned `resolverContext`、`/resolve` 和带 `selectionIntent` 的 canonical Profile strangler mode。旧 `/profile` body、`/gear/stats`、frontend page、Worker、migration/write、job、sync/backfill、cleanup 和公开模板合同均未改变。
- Catalyst 继续要求 verified capability 与 revision；当前保持 fail-closed，Phase 6 的 12.1 保留绿字转换仍是外部依赖型 TODO。
- 2026-07-11 PR #63 候选硬门禁：cold 1/16 槽都执行 `SET TRANSACTION READ ONLY + revision/items/options`，warm 16 槽只执行 `SET TRANSACTION READ ONLY + revision`；真实 Mage/Arcane 15 槽与 DK/Frost 16 槽 authority 都是 `missingFields=[]`。Mage Resolver/五组 Ledger/Facade 全绿，cold 30 次 `p95=201.275ms`、warm 100 次 `p95=105.726ms` 且 cache hit `100/100`，低于 `500ms/200ms` 阈值；四类 fail-closed、`/profile=200`、`/resolve=404`、40/40 observed-only/baseline=0、slot payload、单线程 backend 和零 backend error 都通过。
- 候选 timer/backflow 证据必须区分代码部署与自然外部任务：本次 `WOW_DEPLOY_START_ASYNC_SYNCS=0` 没有启动任何装备 sync/write/backflow；自然 `data-health-followup` 在候选 backend 激活前 1 秒完成，随后独立 SimC updater 因既有 GitHub proxy TLS EOF 失败。恢复探针未切换 binary，`/opt/wow-simc/.commit` 仍为可用的 `1e357922af363f3d87cc0758863c2bb6d7701b72`；该外部下载链路异常要单独记录，不能删掉失败事实，也不能把它解释成 Phase 2B Resolver/loader 回归或借机开启 Catalyst。

## Phase 3 Resolve/Profile 与前端工作台切换边界

- Phase 3 按 3A backend API、3B structured transport + pure state、3C active page cutover 三个 Strict Slice 推进，不允许把 route、transport 和 UI 一次性混成不可回滚大改。
- 3A 在 gear browse payload 增加 backend-owned `resolverContext`，其 `authoredAgainst` 与 Dependency Revisions 必须来自 Phase 2 loader 的同一 revision authority；它仍是 `formalActiveManifest=false` 的过渡身份，不替代 Phase 4 Manifest。
- `POST /api/websim/gear/resolve` 只接受 Selection Intent，返回 `gear-result-envelope-v1`：合法或业务阻断为 200，结构错误 400，revision 冲突 409，authority 不可用 503。它不运行 SimC、不返回 DPS、不推荐装备。
- `/api/websim/profile` 仅在 body 带 `selectionIntent` 时进入 canonical mode，服务端重新加载 Authority、重新 Resolve，再把 server snapshot 交给 serializer facade；旧 body 保留原 200 shape。客户端提交的 snapshot、serializer input、合法性、属性、套装或 Evidence 一律不能复用。
- 3B 的 `requestJson(..., {responseMode: 'structured-problem'})` 只作为 opt-in；有效 409/503/202 envelope 不进入 generic fallback，网络/超时/非法 body 才标 offline。`gear-workbench-state.js` 必须无 `wx`、storage、network、clock 依赖，并按 serial + intentVersion 丢弃旧响应。
- 3C 页面对 confirmed Intent 与 draft 分层；409 只更新 revisions 并最多自动重试一次，503 与 offline 分开显示。last verified snapshot 可只读展示，但 dirty/stale/blocked/read-only 状态不得保存为 verified、生成 profile 或进入 SimC。
- 前端可保留 candidate/source/variant 的浏览与格式化，但最终合法性、Tier identity、set count、确定性总属性、constraints 与 profile readiness 只能来自匹配当前 Intent 的 Resolved Snapshot。legacy stat snapshot 在 Phase 5 前保持独立，不能覆盖 Resolver readiness。
- Phase 3 不新增 migration/write/sync/backfill/cleanup/job/Worker，不改变 public observed-only/baseline-empty，不创建正式 release registry，不开放 Catalyst。
- 2026-07-11 Phase 3A live acceptance：PR #65 合入 `1b87bd6`，merge/candidate tree 同为 `c323141a`，clean-main 等价树已重部署。40/40 public Intent Resolve，11 个 verified talent import Profile resolved、29 个缺导入 Profile truthful blocked；负向 HTTP 为 malformed 400、stale 409、wrong-slot 200 blocked、missing authority 503、unknown Catalyst 503。on-host production Nginx warm 100 为 `p50=97.470ms / p95=112.334ms / p99=115.604ms`，cold→warm statement budget 为 `4→2`（含 `SET TRANSACTION READ ONLY`），cache 为 `1 entry / 73,917 bytes / limit 32 entries + 4 MiB`。公网 client path warm p95 `367.412ms` 要单独报告为 RTT 路径事实；额外 5 并发大 slot payload 压测造成的 Python RSS 保留已通过 backend restart 恢复，不能归因于 Authority cache，也不能冒充通过项。candidate 与 post-merge deploy 都使用 `WOW_DEPLOY_START_ASYNC_SYNCS=0`；11:14 的 observed/WebSim/stat sync 是既有 health-followup timer 自然触发，不是 deploy backflow。
- 2026-07-11 Slice 3B merge acceptance：PR #67 最终头 `7642ad0` 通过 GitHub Harness 并合入 `8afebbf`。opt-in structured-problem mode 保留有效 200/202/409/503 envelope；malformed/network/timeout 才 fallback，默认 transport/auth/analytics headers 不变。canonical wrappers 固定 Resolve raw Intent 与 Profile `{selectionIntent, profileContext}`；纯状态覆盖 confirmed/draft、serial/version、一次 409 rebase、503/offline、current/last verified 与 stat snapshot 分离。targeted `45/45`、frontend `377 tests / 123 commands`、full `129 commands` 通过；active import=0，因此没有 deployment 或真实微信证据，最高证据保持 local/CI。
- 2026-07-11 Slice 3C live acceptance：PR #69 exact evidence head `b9f568e` 通过 GitHub Harness 并 squash 合入 `869372d`。initial/candidate/variant/enhancement/community/saved/reset 七条确认流已统一到 serial+intentVersion Resolve；最终属性、Tier/set、legality、constraints 与 readiness 只来自匹配 snapshot，save/Profile/SimC 绑定 current verified signature。真实微信 captured pending→verified、15/15 effective slots 与 signature change；候选与 clean-main post-merge 40/40 Resolve、400/409/200-blocked/503 负向、旧接口、PG-only、timer/log/rollback 通过。候选 QA 发现并修复 eager 16-slot detail fan-out 与 UUID/`optionKey` authority mismatch；现在 drawer 只 lazy-load selected slot，提交稳定 optionKey，并由 Resolver constraints 隐藏无权威能力的强化选项。七个 runtime 文件 main/remote hash 一致；恢复重启后 `/health` ok、约 49 MiB、单任务、`NRestarts=0`、无 fatal 日志。Phase 3 已归档，Catalyst 仍 disabled/fail-closed。

## Phase 4 Release Train 与 Community Migration 边界

- Phase 4 按 4A pure release contracts、4B immutable PG registry + `legacy-import-r0`、4C shadow readers、4D atomic Active Manifest cutover、4E scheduled candidate refresh 五个 Strict Slice 推进；不得把 migration、reader、pointer cutover 与 timer 混成一个不可回滚 PR。
- 当前 `cache.websim_items`、gear source/variant/mod option 和 community template 表继续是 mutable staging。Phase 4D 已把 public reader 切到正式 active Manifest generation 9，精确绑定一个 immutable Gear Release 与 Community Release；staging 仍只供 sync 和后续 candidate build 使用，不得绕过 Release/Manifest pointer 进入正式读取。
- 不可变 Gear/Community Release 必须以 canonical content hash 生成 release ID；sealed content 不 update/delete。Active Retail Season Manifest 原子绑定 Gear Release、可空 Community Release 与 Dependency Revisions；promotion/rollback 只 compare-and-swap 一个 pointer，不逐表回写。
- 第一轮 Community Release 标记 `legacy-import-r0`，但每个模板必须重新生成 exact Selection Intent，并对目标 Gear Release 运行 current Resolver。legacy 只表示来源，不能 grandfather 合法性、freshness、source evidence 或 signature。
- 每专精选举最多一个 public winner；合法低排名项仅为 internal standby，非法/stale/source-invalid/binding mismatch 为 rejected。缺合法 winner 时该 spec 公开为空并标 degraded，禁止用 `season_recommendation`、default、SimC preset 或 baseline 补齐。
- Shadow compare 必须覆盖 40 专精的 winner presence、Intent、resolved signature、legality、provenance、baseline=0、browse identity 与 Profile Dependency Vector。任何 illegal winner、mixed release、baseline leak、integrity error 或非 observed public source 都阻断 promotion。
- Existing sync 只写 staging；Phase 4E release refresh 必须 candidate-first。相同 Gear Release 的 community winner 更新在完整 gate 后可自动发布；新赛季、rule、serializer、schema、capability 和高风险 gear 变化必须 controlled cutover。deploy 继续 `WOW_DEPLOY_START_ASYNC_SYNCS=0`，不得触发 refresh。
- Phase 4 release train 已完成 immutable Gear/Community Release、shadow reader、原子 Active Manifest pointer 和 scheduled candidate refresh；当前状态与历史证据索引统一由 `docs/project-state.json` 拥有。
- Phase 5 已完成 revision-complete stat signature、fenced PostgreSQL snapshot/job store、单 worker/canonical async API 和活动前端 cutover。当前公开矩阵保持 32 个 verified immutable snapshot 与 8 个 explicit fail-closed outcome；Profile readiness 与 stat execution outcome 是独立合同。
- Phase 0-5 已归档。Phase 6 或 Catalyst 启用必须另开 Harness contract；当前不得启用 Catalyst、前端属性合成或 legacy synchronous stats 回流。
- Scheduled refresh 只消费 staging；相同 Gear Release 的低风险 Community winner 更新也必须通过完整 gate。新赛季、rule、serializer、schema、capability 或高风险 gear 变化继续 controlled cutover。

### Slice 4D 原子首切与回滚操作

Slice 4D 使用 `server/migrations/postgres/0014_websim_active_manifest_pointer_state.sql` 增加显式 `active / transitional` pointer mode。`retail` 行一旦创建就不能删除：首次 promote 从 generation 0 写入 generation 1；首切回滚把同一行更新为 transitional generation 2；重新 promote 更新为 active generation 3。禁止删除 pointer、重置 generation 或重新开放 `expectedGeneration=0`。

候选部署前必须备份目标 PostgreSQL、记录候选 commit/tree 和 0014 前的 Manifest/Pointer 行数，然后以 migration owner 在一个失败即终止的事务中应用 0014。部署仍固定 `WOW_DEPLOY_START_ASYNC_SYNCS=0`。应用后检查：`pointer_mode` 约束存在、active 必须有 Manifest FK、transitional 必须没有 Manifest、`wow_app` 只有 pointer 的 `SELECT/INSERT/UPDATE` 且没有 `DELETE`。

首次 promote 命令必须显式携带当前已封存的 Gear/Community Release、season、talent、SimC 和 expected generation；tool 会重新验证 release/dependency 组合，在一个事务中 seal/reuse Manifest 并 CAS pointer：

```bash
python3 -m server.gear_release_tool promote \
  --season-revision "$SEASON_REVISION" \
  --simc-runtime-revision "$SIMC_RUNTIME_REVISION" \
  --gear-release-id "$GEAR_RELEASE_ID" \
  --community-release-id "$COMMUNITY_RELEASE_ID" \
  --talent-catalog-revision "$TALENT_CATALOG_REVISION" \
  --expected-generation 0 \
  --updated-by "$CUTOVER_ACTOR"
```

社区模板通过 `POST /api/websim/gear/community-import` 原子转换为同一种 selection intent，再交给 resolver；不得在前端逐槽猜测或拼接。

## 可信来源

| 来源 | 可以决定 | 不能决定 |
| --- | --- | --- |
| Battle.net Game Data | 物品身份、来源、inventory type、Journal 与套装关系 | 当前实例完整属性、SimC 可执行性 |
| SimulationCraft | 变体属性探测、profile 语法和可执行性 | 官方掉落来源、玩家热度 |
| Raider.IO / WCL observed evidence | 玩家样本和候选发现 | 规则合法性、BiS、物品属性真值 |
| 仓库 governed mapping | 可审计的职业、槽位、制造业和例外规则 | 未登记的外部事实 |

社区截图、攻略和 UI target 只用于发现问题或表达界面，不得写成装备事实。

## 核心 owner

- `server/gear_contracts.py`、`gear_rule_matrix.py`：请求、结果和规则合同。
- `server/gear_resolver.py`、`pg_gear_authority_loader.py`：纯 resolver 与 PostgreSQL authority facade。
- `server/gear_result_envelope.py`、`gear_runtime.py`：revision-aware transport 与 runtime 组合。
- `server/gear_release*.py`、`gear_release_store.py`：manifest、shadow、refresh 与原子切换。
- `server/community_template_import.py`：社区模板原子导入与 fidelity 门禁。
- `server/gear_stat_snapshot*.py`：异步快照 API、store 和 worker。
- `server/websim_payload.py`：兼容 read model 与最终 serializer。
- `packages/domain`、`packages/api-client`：Taro typed contract。
- `apps/mini-taro`：活动消费者 UI；`pages/` 是迁移期兼容消费者。

## Catalog 与 release 合同

- Source 包含类型、赛季、状态、provenance 和更新时间；inactive、错季或诊断-only source 不进入选择。
- Verified variant 包含 item level/track、结构化属性、生成来源、SimC 实例字段和一致 revision。
- Socket、enchant、embellishment、crafted stats 是独立结构化 option；blocked option 不进入默认选择。
- 后端统一裁决护甲、武器、槽位、主属性、unique、套装、美化和专精规则。
- 活动 release manifest 是一次原子可读版本；读者不能混用不同 revision 的 catalog、rules 和 templates。
- Refresh 先构建候选 release、运行门禁与 shadow 对比，再切换活动指针；失败保持 last-known-good。

## Resolver 合同

`POST /api/websim/gear/resolve` 接收 `selectionIntent + profileContext`，返回 canonical result envelope：

- 每个槽位的 canonical selection、可应用 enhancement 和结构化 blocker；
- `revision` / signature，供客户端丢弃过期响应；
- profile readiness 与 serializer 所需结构化 payload；
- 不可执行状态不补默认值、不复用 stale option、不返回伪 verified。

客户端必须用递增请求序号和返回 signature 防止旧请求覆盖新选择。保存模板只保存 canonical snapshot、revision 和仍匹配的 verified stat snapshot。

## 社区模板导入

`POST /api/websim/gear/community-import` 必须原子处理整份模板：

- 保留可信 item/variant/enhancement 证据，输出逐项 adoption/problem；
- 任何被采用内容都再次经过当前 release/rule authority；
- fidelity 不足时返回可解释 blocker，不静默删槽、猜 option 或部分成功伪装完整成功；
- 导入结果进入 resolver，不形成独立模板事实源。

## 异步属性快照

`POST /api/websim/gear/stat-snapshots` 以 canonical selection signature 幂等创建或查询任务：

- `pending` 允许有界轮询；只有 signature 匹配的 verified snapshot 可写入模板 metadata。
- 换职业、专精、种族、场景、天赋或装备后，旧快照只读 stale；旧请求不得覆盖新状态。
- Worker 终态只能是 immutable verified snapshot，或带 problem/blocker 且无 snapshot 的 fail-closed outcome。
- 旧 `/api/websim/gear/stats` 只保留兼容职责，不是活动 Taro 路径。

## Taro 前端合同

- 通过 `packages/api-client` 调用 gear read、resolve、community import 和 stat snapshots。
- 页面不自行构造 canonical enhancement、合法性或属性快照。
- 换装备后用 resolver 返回值裁剪 stale draft；两个等价槽位仍保持独立 key。
- 请求竞态由 revision/signature 处理；loading、problem、partial 和 stale 都是显式 UI 状态。
- 提交前重新经过 resolver/profile readiness；前端不拼 SimC profile 字符串。

## 只读审计与更新顺序

更新前检查 data health、release manifest、source/item/variant/mod-option 分布、40 专精规则覆盖和重点武器样本。然后：

1. 明确版本、赛季、实例、套装、制造业和规则范围。
2. 运行本地测试与只读审计，列出 blockers。
3. 备份实际 PostgreSQL target。
4. 对写入脚本先 dry-run。
5. 按 source -> metadata -> variant -> mod option -> rules -> candidate release 顺序写入。
6. 运行 release gate、shadow 对比并原子切换。
7. 抽样 gear read、resolve、community import、stat snapshot 和 serializer。
8. 运行 40 专精 traversal、Taro 核心交互和远端 smoke。

## 验证

```bash
python3 -m unittest \
  tests.gear_contracts_test \
  tests.gear_rule_matrix_test \
  tests.gear_resolver_test \
  tests.gear_result_envelope_test \
  tests.gear_release_test \
  tests.gear_stat_snapshot_api_test \
  tests.community_template_import_test
node --test tests/gear-workbench-state.test.js tests/builds-page.test.js
npm run audit:ui-architecture
npm run typecheck
npm run test:taro
git diff --check
```

远端 smoke 至少检查 `/health`、`/api/data/health`、关键专精的 compact gear、resolve、community import dry sample 和 snapshot 状态流。HTTP 200 或单元测试只证明工程基础，仍需核对 revision、状态、blocker、来源和内容。

## 回滚

- 代码问题：回退代码并重新部署，不修改可信 DB；复核 health、manifest、resolve 和 serializer。
- 数据污染：停止写入任务，备份异常状态，恢复写入前 PostgreSQL 备份，重启后复核 release 与 40 专精 coverage。
- Release 问题：原子切回 last-known-good manifest，不拼接旧新 revision。
- 少量规则错误：先备份，再做最小修正；规则错误同时补代码和测试。

## 发布清单

- [ ] 活动 release manifest、revision 和 rollback target 已记录。
- [ ] Verified variant 缺属性和 provenance 为 0。
- [ ] Source、variant、option、compatibility blockers 可解释。
- [ ] 40 专精 traversal 与重点武器/护甲/美化样本通过。
- [ ] Resolver 对 stale/incompatible 输入 fail closed，竞态测试通过。
- [ ] 社区模板导入 fidelity 与原子性通过。
- [ ] 属性快照 verified/fail-closed 状态流与 signature 隔离通过。
- [ ] Taro 使用 typed canonical API，未保留第二套本地装备事实。
- [ ] PostgreSQL 备份路径、写入范围、health 与远端 smoke 已记录。
