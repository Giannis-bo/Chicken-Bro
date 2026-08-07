# Exact-first Task 5A API / Runtime 接合设计

状态：`implementation_allowed，local foundation 正在推进（2026-08-07：用户确认现有 simc_submit 的后端接合范围、final candidate 后的生产 migration/worker activation，及完成该链路所必需的 owner-scoped source-binding 子切片。allowlist、TDD、candidate 与回滚门槛已冻结。Exact API generic confirm/submit/read、0033 source binding/admission/replay、0034 v2 job→snapshot binding、injected v2 worker processor、strict Exact HTTP confirm/submit/read facade、strict typed Exact client contract，以及不改视觉的当前 simc_submit local request binding 均已完成；但尚无 save-route、active authority/profile provider、enabled runtime owner、candidate、生产操作或用户验收。用户已确认 profile source amendment：只有 remote saved talent template 可经 server reload/compile 进入 Exact，client raw profile、local 与 handoff 保持 blocked。完整 active loadout/effect materialization 完成前，ready-path 仍 literal blocked。）`

本文件是 Task 5A 的当前设计入口。它补足重排计划对 Task 5A 要求的用户体验、授权边界、候选/回滚与独立评审；已确认的设计已冻结为下方 allowlisted implementation plan。它只授权本地 TDD 实现，不授权 candidate、生产操作或用户闭环声明。本文件不重开 Task 3A、4P、4L、3B 或 4W，也不授予 Task 6C 的 observation/Catalog admission 权限。

## 用户目标与当前摩擦

用户已在现有 `simc_submit` 页面选择职业、天赋、装备来源和场景；点击确认与提交时，页面现在仍经由 v1 `selectionIntent`、属性快照和旧 `simulator.analyze` 路径。该输入只表达用户想模拟什么，不能被前端升级为 Exact fact。

Task 5A 的体验目标是保持这个页面、入口、视觉和操作顺序不变：用户仍从既有装备详情或保存模板带入装备、确认组合并提交 SimC；后台改为服务器把意图物化为 Exact authority、v2 ResolvedLoadout 和 immutable SimulationSnapshot，再以绑定 SimC runtime 执行。若 authority、全套规则或 effect occurrence 不完整，用户在同一页面看到现有的阻断状态并且不会创建任务。没有前端猜测、没有旧路径回退、没有“HTTP 200 即完成”的承诺。

## 已确认设计

### 1. 保留页面，替换可信执行链

- 继续使用既有 `apps/mini-taro/src/pages/simulator/simc.tsx` 的装备来源、确认、提交和任务记录入口；不得新增路由、控件、文案布局、SCSS 或 canonical target。
- `packages/api-client` 提供 Exact-first confirm、submit 和 owner-scoped job read 的 typed contract；页面只替换调用绑定与状态映射，继续使用已有 `ready`、`partial`、`blocked`、`error` 状态区域。
- 前端发送既有 `selection-intent-v1`、不含装备事实的 gear `exact-simc-source-ref-v1`、不含 raw talent 的 `exact-simc-profile-ref-v1`，以及仅含 `raceKey` / `scenarioKey` 的 `exact-simc-execution-intent-v1`；它们全是 *untrusted intent*，不是 Exact input。前端不得调用 `canonicalExactLoadoutIntent` 将 v1 item/variant 值拼成 v2，也不得补 bonus、装等、gem、enchant、crafted、effect、天赋行或 Catalog 事实。
- gear source ref 只保留当前既有装备 source 的 kind / bounded id / remote-state，供服务端以该 owner 的保存记录或 active sealed source 重找 authority。它不是 authority，也不能让 local-only template 或 handoff 变成 Exact；来源缺失、非 remote、重找不唯一或重找后的 v1 intent 不等时，返回 literal `blocked / EXACT_SOURCE_AUTHORITY_REQUIRED`。
- profile ref 只保留当前选中 remote talent template 的 bounded id / remote-state；服务端只在该 authenticated owner scope 重读对应 `app.build_templates` talent row，校验 class/spec/hero 与 sealed loadout，再以当前服务器可用的 talent encoder 产生 canonical talent lines 与 `talentProfileKey`。execution intent 的 race/scenario 也只在服务端当前 SimC options/preparation authority 中重读和规范化。profile ref 缺失、非 remote、row 不存在、template/raw/encoder 不可用、class/spec/hero/race/scenario/preparation 不匹配，或任一 output 不能通过 SimulationSnapshot verifier 时，返回 literal `blocked / EXACT_PROFILE_AUTHORITY_REQUIRED`；local talent、handoff 和 client `profileContext` 永不进入 Exact。
- remote template 的 Exact 资格不是 source ref 本身，而是一条 server-owned、append-only 的 admission binding：服务器先 owner-scope 重读已保存的 `app.build_templates` 行，重新规范化 v1 intent，并只在该 intent 唯一匹配一个 sealed template group、该 group 的每个 slot 都有当前 revision 下唯一且 typed-reload 成功的 Authority Bundle 时写入 canonical binding bytes/key/hash。绑定同时钉住 owner hash、template id、template config/payload/selection signature、registry/rule/resolver/runtime revision、template identity/content hash 和 slot-bound envelope keys；binding JSON 不包含 raw profile、角色/realm/server 或 user UUID。
- 保存后没有 binding、binding 与重读 source hash 不同、group/bundle 不唯一、任一 typed reload/revision 失配，或 loadout effect authority 尚未完整，均只让后续 Exact confirm 返回 literal `blocked`；不得在 confirm、worker 或 registry reader 中重新做无 source-binding 的 discovery。既有 remote 模板只有在当前保存路径重新保存并完成 admission 后才能进入 Exact；这不改变其既有保存/展示能力，也不把 legacy 模板误报为 ready。
- 认证层保有的 canonical user UUID 只在单次后端调用内用于 owner-scoped source reload 与 binding 函数；route 以 `exact-simc-job-owner-v1:` 域隔离 hash 作为 0032 API/job/read identity。该 job hash 与 binding 的 `exact-template-owner-v1:` hash 目的不同且不可互换；UUID 不进入 request bytes、job、binding、日志、公开 envelope 或 result。
- 后端从这项意图经受控 Resolver 物化完整 Exact；只有完整、authority-bound 的 `exact-loadout-intent-v2` 与其 sealed `resolvedLoadoutKey`、`simulationSnapshotKey`、`snapshotRowHash` 可进入新的 `exact-import-job-request-v2` canonical bytes/key/hash。0032 既有 `exact-import-job-request-v1` rows/bytes 永远不重写；worker 对 v1 只返回 literal `unsupported`，绝不反向选取 snapshot。Catalog 仅能作为初始 materialization 来源，不能作为 ready 的最终依据；unlisted 的 ready Exact 不得因未列入 Catalog 被阻断。

### 2. Exact API 与任务语义

- 新的 owner-scoped Exact SimC API 分为确认、提交与读取三个动作。确认不创建可执行 SimC 任务；提交只接受同一 canonical request/dependency vector 已确认的 ready snapshot；读取只能访问当前 owner 的 job/result。
- 每个响应有固定 envelope、operation status、structured problem codes、request/job/snapshot identity 和必要的 retry/cooldown 信息。它不返回 raw plugin profile、角色名、realm、server、未密封 authority document 或能让前端重建事实的内部 payload。
- 服务端处理顺序固定为：gear/profile/execution intent 解析与 owner-scoped reload -> Exact Authority Bundle typed reload -> `resolve_v2` -> loadout-level effect authority 校验 -> server-only talent/options materialization -> `build_simulation_snapshot_v2` 与 store reload -> SimC execution。任一阶段的 `unknown`、`unsupported`、缺字段、非法组合、bytes/key/hash drift 或 runtime mismatch 立即进入 literal `blocked`/`unsupported`，不调用旧 `analyze`、不复用 v1 snapshot、更不把部分结果写为 resolved。
- `0034_websim_exact_job_snapshot_binding.sql` 只以 forward migration 放宽 0032 request JSON constraint/function verification，使其并行接受既有 v1 与新的 v2 request schema；v2 snapshot reference 进入 request canonical bytes，不能依赖 job id、最新行、进程内缓存或 side table。worker 以 v2 reference reload snapshot，并逐项核对 snapshot/loadout key、snapshot row hash、runtime revision 与 sealed v2 verifier；任一缺失、drift、v1 request 或不 ready 状态均 terminalize 为 typed non-ready，绝不执行 runner。
- 现有 Task 4W worker 的 `unavailable_processor` 只在本 Task 的授权实现中替换为上述 typed processor。它仍通过独立 login DSN、`SET ROLE wow_exact_worker`、database-clock lease/token CAS 和 0032 function boundary 工作；公开 app role 不获得 authority 或 job-table DML。

### 3. 发布、回滚与用户边界

- 最终 runtime head 先在云端做一次低优先级、资源预检通过的 disposable PostgreSQL fresh/upgrade candidate；禁止本机 PostgreSQL，候选数据库、candidate login、目录和 bundle 都必须是新的、精确标识且可清理资源。
- 该 candidate 必须验证 0030--0034 的连续 migration、app/worker least-privilege boundary、v1 bytes/key/hash 不变、v2 job/snapshot canonical relation、Exact ready/unlisted 成功、缺 authority/illegal/runtime unsupported 的 fail-closed 行为、SimC task/result identity、现有 `simc_submit` typed call 和 rollback。
- 只有 candidate、独立 CR、final-head CI 和 Harness 允许后，才可将 0030--0034 应用于生产、启用受限 worker 并切换当前 `simc_submit` 的 backend binding；部署保持 `WOW_DEPLOY_START_ASYNC_SYNCS=0`，不启动 observation/backfill，不改 Catalog/Manifest pointer 或 generation 35。
- 回滚先停止 Exact worker、禁用 Exact API binding 并将页面置为明确不可用状态；不得静默回退旧 `simulator.analyze`。数据库只按已验证的 migration/备份 runbook 处理；已产生的 immutable snapshot/result 不重写。

## 需求质疑、方案比较与影响边界

### 反方质疑

- **“只要现有 API 返回成功即可”不成立。** 旧 `analyze` 可以处理 intent 或 v1 属性快照，但无法证明 tier、set、cross-slot、loadout-scoped occurrence、snapshot 与 SimC runtime 的同一身份；它不能承载 Exact-first 用户承诺。
- **“前端把 v1 补成 v2”不成立。** 前端没有 authority document、完整 occurrence 规则或 sealed canonical bytes；在那里拼 bonus、gem、enchant 或 Catalog 值会把猜测升级成事实。
- **“先换页面再补后端”不成立。** 当前页面已是既有用户入口；重做视觉不能解决 truth boundary，反而会扩大验证与手工验收面。

### 方案比较

| 方案 | 结论 | 原因 |
| --- | --- | --- |
| A. 前端 v1 -> v2 转换后继续调旧 `analyze` | 拒绝 | 把未可信 intent 伪造成 Exact，且无法 fail closed。 |
| B. 保留旧 `analyze` 作为 Exact API 失败时的 fallback | 拒绝 | 会把 `blocked` 静默降级为貌似成功的旧结果，破坏用户可追溯性。 |
| C. 后端物化 Exact，队列/worker 消费 v2 snapshot；页面只替换 typed binding | 采用 | 最小化 UI 变更，同时把 authority、canonical identity 与执行责任留在唯一后端 owner。 |

### 联动影响

`现有 simc_submit v1 intent` -> `typed Exact confirm/submit/read` -> `server materialization + authority reload` -> `resolve_v2 + SimulationSnapshot v2` -> `0032 owner-scoped job` -> `restricted Exact worker` -> `pinned SimC result`。

页面绝不跨越到 authority、resolver、snapshot 或 runner；Catalog 只可位于 server materialization 的输入侧。任一箭头不能证明完整 authority 时，响应是结构化 `blocked`/`unsupported`，不是旧链路。

### 工程健康判断

`server/news_backend.py` 是热点路由文件，Task 5A 只能增加窄的 route wiring，并将 materialization/API orchestration 放在新 owner 模块；不得继续向通用 `analyze` 分支堆叠 Exact 判断。worker 继续通过既有 0032 函数和角色边界访问数据库。前端只可改 typed client 与当前页面的调用映射，因此不触碰 target geometry 或视觉回归面。implementation plan 已给出每一个新 owner、每一个热点接点和每个测试文件的精确 allowlist。

当前源代码审查额外确认：`buildCanonicalSimcContext(...)` 会把选择的 template/handoff 压缩为 v1 `selectionIntent`，现有 API 无法从该值反向确定原 source。因而 Task 5A 必须显式传递上述 opaque source ref；把当前 local-only template 或 handoff 当作可重放 Exact source 都是不成立的推断。它们会保持 blocked，直到后续有单独授权的 server-owned authority source。

2026-08-07 的 profile audit 同样确认：当前页面将 `talentTemplate.rawString`、race 与 scenario 直接组成 `profileContext`；`ExactSimcMaterializer` 的 injected profile seam 因而尚无 active owner。用户确认采用 remote saved talent source 后，本 Task 仅把 client source ID 和 choice intent 送往后端：`PostgresPersonalStore` 以 authenticated owner reload talent row，现有 server talent encoder 在请求内存中产生 canonical lines，active server options 规范化 race/scenario/preparation，`SimulationSnapshot` 自行 content-address talent lines。它不新增 talent persistence/migration、不把 raw profile 复制到 0030--0034 或公开 envelope、不允许 client lines 成为 fallback，也不把当前未建模的 loadout effect authority 推断为 ready。

当前还没有证据表明 remote template 记录能提供与现有 selection 完整匹配的 `ExactAuthorityBundle` / envelope key closure。`build_resolved_loadout_from_registry(...)` 也要求 server-bound template identity，不能把 registry 当作无界候选搜索。因此 Task 5A 不得先接 HTTP/UI，再以 Catalog 或 slot 相似性补足；在一个可重放 source-to-bundle reader 得到当前 task 的独立 allowlist、TDD 和 authority evidence 前，真实 ready 分支必须继续 literal `blocked`。这一 gap 不是 4W failure，也不是 Task 6C 已获授权。

2026-08-07 的当前源码复核进一步限定了这个 gap：`app.build_templates` 只保存 owner-scoped 的 v1 draft、`selectionIntent`、前端 `resolvedGearSignature` 与任意 metadata；其中没有服务器写入、可 byte-verified reload 的 Authority Bundle/envelope relation。sealed Exact registry 刻意不保存 personal owner/source-template identity，且 `build_resolved_loadout_from_registry(...)` 明确拒绝无 server-bound content hash/authority identity 的 registry-wide discovery。故不能把 remote template ID、其 client metadata 或相似 slot 当作 mapping。用户随后明确授权了本 Task 5A 的独立 source-binding 子切片：新增 0033 只保存上述受限 admission relation，并且它不改变 active Manifest/Catalog pointer、不触发 observation/backfill，也不使尚未完成的 loadout/effect materialization 变成 ready。该 relation 与 local injected v2 materializer foundation 完成并经过其 TDD/CR 后，仍须完成 active authority/profile composition、worker、route/client/current-page binding 和最终 candidate，才可进入用户路径。

2026-08-07 的 Step 2 source audit 发现 `exact-import-job-request-v1` 与 0032 job table 只封存 `exactLoadoutIntent` 和 dependency vector，不含 `SimulationSnapshotKey`、talent/profile/scenario identity 或一个 durable job-to-snapshot relation；0031 的 v2 snapshot 本身则绑定这些 identity。多个 snapshot 可以共享同一装备 intent/revisions，故 worker 不能通过反向搜索、最新行或重新 materialize 来猜出唯一 snapshot。用户已批准本计划的 0034 amendment：以 forward-only SQL 增加 `exact-import-job-request-v2` acceptance，v2 canonical bytes 内必须同时保存 `resolvedLoadoutKey`、`simulationSnapshotKey` 和 `snapshotRowHash`。它不改写 v1/0032 历史 rows、表 owner、role/function signature 或 direct-DML boundary；它只让 app 在被重验的 v2 snapshot 已 sealed 后 enqueue v2，且让 worker 唯一 reload 该 reference。

2026-08-07 的 active-runtime audit 还确认：当前 `PostgresCacheStore` 的 read-only resolver context 能给出 selection-intent 的兼容 dependency vector，但不能证明 `exact-import-job-request-v2` 所需的完整八项 `gameBuild` / `compilerRevision` / `workerRevision` / `effectAuthorityRevision` 等 canonical identity；同时没有一个按 sealed loadout key 重读并验证 loadout-effect aggregate 的 API owner。0033 binding 仅钉住 registry/rule/resolver/runtime 四项，不能推导其余项。故路由可以先完成 authenticated owner scope、严格 request/envelope 和 literal blocked contract，但不得把这些缺失值写成默认值或由 slot/Catalog/最新 aggregate 补推；在有独立 exact authority provider 的 allowlisted TDD/evidence 前，runtime ready 分支仍不可启用。

Exact HTTP contract 固定为：`POST /api/simulator/exact/confirm` 接收唯一的 Exact intent envelope；`POST /api/simulator/exact/submit` 接收 `{request, confirmation}`；`GET /api/simulator/exact/job?id=<positive-integer>` 只读取当前 authenticated owner 的 job。未认证返回 `401`；结构安全但 `blocked` / `unsupported` 的 Exact envelope 返回 `409`；排队/运行读取可返回 `202`；任何 runtime owner 不可用、私有字段或 envelope drift 返回不泄露细节的 `503`。这些 route 只调用 Task 5A API owner，绝不调用 legacy `/api/simulator/analyze`。

## 明确非目标

- 不改变现有前端视觉、route geometry、Design target、SCSS、页面入口或导航。
- 不让 v1 `selectionIntent`、BrowseVariant、Catalog membership、HTTP 200、worker active 或 SimC exit code 充当 Exact authority 或用户闭环证明。
- 不实现 Task 6C observation、candidate/admission、Catalog revision 发布或 Manifest CAS；0033 仅限本计划的 remote-template Exact authority admission binding，不是 Catalog 或 Manifest admission。
- 不重跑、重建或清理已归档的 Task 3A/3B/4W candidate；不修改其 formal evidence identity。
- 不保存或输出 raw plugin profile、玩家姓名、realm、server 或其他身份化输入。

## 用户可见验收与停止条件

在 candidate 和真实微信中，既有 `simc_submit` 页面至少证明：

1. 一个服务器可物化、完整且 effect authority 完整的当前装备来源可确认、提交、生成 Exact-bound task，并在既有任务查看体验中得到其绑定结果；
2. 任何缺 tier/set/cross-slot/loadout-scoped authority 的组合显示 literal `blocked` / `LOADOUT_EFFECT_AUTHORITY_REQUIRED`，不会创建任务；
3. `unknown` 或 `unsupported` SimC effect 在任务创建前被阻断；
4. 当前页面的视觉、入口、选择和记录导航没有被本 Task 改写；
5. 生产 migration、worker activation、API smoke、timer/backflow 状态与 rollback 均有精确 commit/tree/build identity 证据。

若服务器无法从现有 v1 选装意图物化完整 Exact，或必须在前端补值、改变 Catalog/Manifest pointer、使用未授权 migration、重用候选资源、绕过 worker role、或把运行错误伪装为 legacy 成功，立即停止并保持 literal `blocked`。

## 已确认决策

- 2026-08-07：用户明确要求新后端接入当前前端 UI；接入限于既有 `simc_submit` 调用绑定，UI 视觉与入口不重做。
- 2026-08-07：用户明确授权 Task 5A 在 final candidate 通过后执行生产 0030--0032 migration 并激活 dormant Exact worker；授权不扩展至 Catalog/Manifest、generation 35、Task 6C 或其它异步同步。
- 2026-08-07：用户确认 Task 5A 只允许远端已保存、且服务端能重找并完整匹配 sealed Authority Bundle 的装备模板进入 Exact 路径；handoff、本地模板、缺失或不唯一映射全部 literal `blocked`。
- 2026-08-07：用户明确批准继续完成该独立 owner-scoped source-binding/persistence 子切片及其必需的受限 0033 migration 设计与本地实现；这不放宽现有 UI 入口/视觉、Catalog/Manifest/generation 35、Task 6C、异步同步或 candidate/production gate。生产 0033 与 0030--0032 一样只能在本 Task final candidate、CR、CI、Harness 和既有页面验收之后执行。
- 2026-08-07：用户批准 0034 forward-only job→snapshot binding amendment。它保留所有 0032/v1 canonical request bytes 和 job rows；新 v2 request 必须在 canonical bytes 中绑定 `resolvedLoadoutKey`、`simulationSnapshotKey`、`snapshotRowHash`。不得以 side table、latest-row lookup、重新 materialize 或进程内缓存补足关联；worker 只执行 reloaded v2 snapshot，v1/缺失/drift 一律 typed non-ready。该批准不扩展至 UI visual、Catalog/Manifest/generation 35、Task 6C、candidate 或生产 gate。
- 2026-08-07：用户确认 Task 5A profile source amendment：Exact request 只可 reference authenticated owner 的 remote saved talent template，并由 server reload/compile；race/scenario 仍仅是经 server options revalidation 的 choice intent。local/handoff template、client raw talent/profileContext、缺失/非 remote/不一致 profile source 与不可验证 options 均 literal `blocked / EXACT_PROFILE_AUTHORITY_REQUIRED`。该 amendment 不增加 UI entry/visual、talent persistence migration、Catalog/Manifest/generation 35、Task 6C、candidate 或生产 gate。

## 冻结实施计划与文件 allowlist

下列计划按小步 TDD 执行。每一步仅在该步的 RED 用例存在且失败原因符合预期后写生产代码；任一新文件、迁移、路由、UI visual owner、Catalog/Manifest pointer 或异步任务需求都属于 scope expansion，必须停止。

### 允许文件

- Create: `server/exact_simc_api.py`、`tests/exact_simc_api_test.py`。该 module 是唯一的 request materialization / confirm / submit / read owner；其 public surface 接收 v1 intent 但只产生 typed Exact v2 outcome，依赖由 route/worker 显式注入。
- Create: `server/exact_template_authority_binding.py`、`server/exact_template_authority_binding_store.py`、`server/exact_template_authority_admission.py`、`server/exact_template_authority_source_reader.py`、`tests/exact_template_authority_binding_test.py`、`tests/exact_template_authority_binding_store_test.py`、`tests/exact_template_authority_admission_test.py`、`tests/exact_template_authority_source_reader_test.py`、`server/migrations/postgres/0033_websim_exact_template_authority_binding.sql`。它们是唯一的 remote saved-template admission、persistence 与 later-source-read owner：source 必须由 server owner-scope reload；admission 只在保存后用唯一 template group 和每槽 typed-reload 的 Bundle closure 生成 binding；later read 只可重算 source signature、要求唯一 matching binding 并逐槽回读被记录的 bundle，绝不重做 registry matching；binding 必须是 canonical bytes/key/hash、append-only、owner/template/config/payload/selection scoped，并通过 slot-bound Authority Bundle closure 读回验证。它们不得写 Exact registry、Catalog/Manifest pointer、snapshot/job/result 或公开 payload。
- Modify: `server/gear_exact_authority_store.py`、`tests/gear_exact_authority_store_test.py`，仅增加按 already-sealed exact item instance key + pinned revisions 查找并 typed-reload **唯一** Authority Bundle 的 read seam；零个或多个结果一律 integrity failure，不能选择最新/第一个。
- Modify: `server/postgres_personal_store.py`、`tests/postgres_personal_store_test.py`，仅增加 server-only、owner-scoped gear 与 talent template reload projection；不得把 config hash、source digest、binding、authority key 或 private reload projection 加入 public template response。
- Create: `server/migrations/postgres/0034_websim_exact_job_snapshot_binding.sql`。仅以 forward migration 令 0032 job table/function boundary 并行接受 v1 与 v2 canonical request schema；v2 必须恰有 `schemaRevision`、`exactLoadoutIntent`、`dependencyVector`、`resolvedLoadoutKey`、`simulationSnapshotKey`、`snapshotRowHash`，并保留原 request byte/key hash、sensitive-field、owner/role/function ACL、lease/CAS/retention 约束。禁止新 side table、direct DML、role/function signature 改动、v1 row rewrite、Catalog/Manifest 写入。
- Modify: `server/gear_exact_import_job_store.py`、`tests/gear_exact_import_job_store_test.py`，只增加 `exact-import-job-request-v2` 的 canonical build/reload 及 snapshot reference validator；v1 build/reload bytes/key 必须不变，v2 不得省略或替换任一 sealed reference。
- Modify: `tests/postgres_schema_test.py`、`tests/postgres_integration_test.py`，仅增加 0033/0034 的 canonical bytes/hash, FK/relation closure、v1/v2 compatibility、function ACL、least-privilege、fresh/upgrade candidate contract；不改既有 0030--0032 assertions/evidence。
- Modify: `server/news_backend.py`，仅加入窄的 Exact confirm、submit、owner-scoped read route wiring、当前 runtime revision / authenticated owner hash 注入和固定 JSON envelope。不得改 `/api/simulator/analyze` 的语义或复用它作为 fallback。
- Modify: `tests/news_backend_test.py`，仅增加 Exact route auth、strict gear/profile/execution request schema、owner isolation、blocked-no-task 与 private-field rejection 的行为测试；不得修改 legacy analyze expectations。
- Modify: `server/gear_exact_authority_worker.py`、`tests/gear_exact_authority_worker_test.py`，以注入的 v2 snapshot executor 替换 `unavailable_processor`，保留 0032 role/lease/CAS boundary，且只写 bounded result/problem identity。
- Modify: `server/postgres_cache_store.py`、`server/simulation_snapshot_store.py`、`tests/simulation_snapshot_store_test.py`，只增加 Exact API 所需的 typed authority/snapshot rehydration seam；不得更改已 sealed v1/v2 bytes/key/hash 或迁移 SQL。
- Modify: `packages/api-client/src/simulator.ts`、`packages/api-client/src/simulator.test.ts`、`packages/api-client/src/index.ts`、`packages/api-client/src/clients.ts`，加入 typed Exact confirm/submit/read methods、严格 envelope validator 和无 fallback-to-legacy 行为。
- Modify: `apps/mini-taro/src/pages/simulator/simc.tsx`、`apps/mini-taro/src/pages/simulator/simc-submit-model.ts`、`apps/mini-taro/src/pages/simulator/simc-submit-model.test.ts`、`apps/mini-taro/src/pages/simulator/simc-page-contract.test.ts`，只替换请求编排和状态映射；不得改变 route、JSX hierarchy、用户文案、样式、target 或导航行为。
- Modify only if focused RED test proves deployment wiring cannot safely reuse the dormant contract: `server/wow-gear-exact-authority-worker.service`、`server/deploy_lighthouse.sh`、`docs/postgres-identity-migration-runbook.md` 及其已有 focused tests/runbook checks。此例外只可实现 feature-disable / worker-stop / no-async-backflow 回滚，不能在本机或未经 candidate 的生产环境启动服务。
- Control plane only: this plan, `docs/plans/README.md`, `docs/roadmap.md`, the resequence plan, this task's requirement/evidence/manifest, and only the Task 5A sections of current owner/verification maps if source changes make them stale. Existing Task 3A/3B/4W evidence files、`docs/project-state.json`、generation 35、Catalog/Manifest pointer 和 `0030`--`0032` SQL 均禁止改动。

### Step 0 — server-owned remote-template admission / persistence

1. First add RED pure-contract tests for a remote source projection and canonical binding. They must prove that local/handoff/no-owner sources, client metadata identity, changed source payload or selection signature, ambiguous template identity/content group, missing bundle, duplicated bundle, revision drift and byte/key/hash reload failure never produce a binding. A binding must contain only bounded canonical identities and be reproducible byte-for-byte from the same server reload.
2. Add RED store/schema tests for 0033: the source row is reloaded owner-scoped from `app.build_templates`; the binding and its ordered slot relations are append-only except user/template cascade deletion; every relation has an FK to an existing sealed Authority Bundle; writer/read functions are `wow_migrator` owned and app execution is limited to owner-scoped admission/read functions; `wow_app` and `wow_exact_worker` receive no direct table DML. Fresh/upgrade integration remains cloud-candidate-only and must not run locally.
3. Implement the pure owner and store. Admission may be invoked only immediately after server save/reload of a remote `gear` template; an unsuccessful admission preserves the ordinary saved template but creates no Exact binding. On a later Exact source read, recompute the stored source hash/signature from the owner-scoped template row, require exactly one matching binding, reload every stored Authority Bundle at the pinned revisions, and return a structured literal blocked result on any failure. It must never rerun registry matching as a runtime fallback.
4. Add the narrow `PostgresPersonalStore` source reload and `GearExactAuthorityStore` unique lookup seams. Do not wire confirm/submit, worker, HTTP endpoints, typed clients or the current page until the admission contract is independently reviewed and its complete materializer test has a red case.
5. Run the focused pure/store/personal/authority/schema tests, Python compilation, `git diff --check` and the Task 5A requirement validation. Record only local evidence; do not create a candidate, apply 0033, modify UI or generate an evidence-only PR.

### Step 1 — Exact API owner RED contract

1. In `tests/exact_simc_api_test.py`, create typed fake dependencies for authority materialization, `resolve_v2`, snapshot store, 0032 job store and pinned runner. Cover complete ready/unlisted Exact, missing/forged authority, missing/non-remote/ambiguous source ref, tier/set/cross-slot/loadout authority absence, illegal v2 result, bytes/key/hash drift, runtime mismatch, owner isolation and no raw identity persistence.
2. The RED API contract must prove: confirm never enqueues, submit accepts only the exact confirmed dependency vector/snapshot identity, read is owner-scoped, every non-ready path returns literal `blocked`/`unsupported`, and no path calls legacy `analyze`.
3. Add `server/exact_simc_api.py` using injected dependencies. It binds server-owned authority, rehydrates it before and after `resolve_v2`, seals/reloads v2 loadout + snapshot, and maps only verified canonical identities into the `exact-import-job-request-v1` dependency vector.
4. Run `python3 -m unittest tests.exact_simc_api_test` before and after implementation; add direct-import and `py_compile` checks for the new module.

### Step 2 — 0034 snapshot-bound request / queue processor RED contract

1. First extend `tests/gear_exact_import_job_store_test.py` and `tests/postgres_schema_test.py` with RED cases for `exact-import-job-request-v2`: all three snapshot references must be present, canonical, bounded and included in exact request bytes/key; one-field drift must change/reject the request; v1 build/reload bytes/key remain unchanged; 0034 only accepts the exact v1/v2 field sets and preserves 0032 ACL/function signatures. Extend `tests/simulation_snapshot_store_test.py` only with a typed v2 reload seam if existing `load_snapshot(..., include_result=False)` cannot prove key/loadout/row-hash/runtime identity.
2. Create 0034 and implement the bounded v2 request builder/reloader. `ExactSimcMaterializer` may emit a job request only after its sealed snapshot has the matching `resolvedLoadoutKey`, `simulationSnapshotKey` and `rowHash`; failed persistence/reload remains blocked and creates no job.
3. Extend `tests/gear_exact_authority_worker_test.py` with RED cases for a claimed v1 request, missing/not-ready v2 snapshot, key/loadout/row-hash/runtime drift, typed blocked/unsupported, pinned-runner completion, lease loss and sensitive exception text. No case may pass a raw profile or permit snapshot discovery.
4. Implement the worker's injected processor boundary in `server/gear_exact_authority_worker.py`. It rejects v1, reloads only the snapshot named by the typed v2 request, verifies the exact three references plus runtime before running, binds the bounded result through `SimulationSnapshotStore`, then token-terminalizes once. It must never run arbitrary profile text, infer an authority document, select latest state or alter Catalog state.
5. Run `python3 -m unittest tests.gear_exact_authority_worker_test tests.gear_exact_import_job_store_test tests.simulation_snapshot_store_test tests.postgres_schema_test` and Python compilation for every changed server module.

### Step 3 — Hot-route and typed-client contract

1. Add focused RED HTTP tests in `tests/news_backend_test.py` for the three Exact endpoints: route-level auth/owner hashing, strict gear/profile/execution request schema, status-to-HTTP mapping, no private response fields, blocked no-task and owner-isolated read. Missing/non-remote/local profile ref or client raw `profileContext` must be blocked. Existing `/api/simulator/analyze` tests stay unchanged.
2. Extend `tests/exact_simc_api_test.py` and `tests/postgres_personal_store_test.py` with RED cases for owner-scoped remote talent reload, profile/execution ref validation, canonical server-only talent/options materialization and rejection of raw/client/local/handoff input. Then wire exactly these endpoints in `server/news_backend.py`; it creates dependencies from the active read model without modifying its pointer, passes the pinned runtime revision, and has no implicit sync/backfill/start behavior.
3. Add RED validator tests in `packages/api-client/src/simulator.test.ts`; each malformed or legacy-shaped response must become client fallback/error rather than ready. Implement only `exactSimcConfirm`, `exactSimcSubmit`, `exactSimcRead` in the existing `SimulatorClient`/client aggregation.
4. Run `python3 -m unittest tests.exact_simc_api_test tests.gear_exact_authority_worker_test tests.news_backend_test` and the focused package-client test command documented by its workspace scripts; do not install dependencies.

### Step 4 — Existing-page binding, no visual change

1. First extend `simc-submit-model.test.ts` and `simc-page-contract.test.ts` with RED behavior checks: v1 stays intent-only; opaque gear/profile refs never contain equipment facts or raw talent; local/handoff gear or talent remains blocked when it lacks server authority; execution intent contains only bounded choice keys; confirm/submit/read consume Exact envelopes; ready/pending/blocked/unsupported mapping is explicit; `LOADOUT_EFFECT_AUTHORITY_REQUIRED` and `EXACT_PROFILE_AUTHORITY_REQUIRED` remain literal; no `simulator.analyze` is used for this path; and the existing page contract/route/visible content stays unchanged.
2. In `simc.tsx`, replace the current stat-snapshot / legacy analyze polling with Exact confirm/submit/read polling while retaining the same cancellation session, preparation gate, active-task guard and task-record navigation. `simc-submit-model.ts` may add typed state mapping only; it must not add or remove UI controls or strings.
3. Run the focused Taro page/model tests with the already-present workspace runtime. If dependencies are not locally available, stop and report the missing pre-approved runtime rather than install anything.

### Step 5 — Whole-branch evidence, candidate and production sequence

1. Perform local CR against this plan, require all TDD evidence, run `git diff --check`, requirement/packet JSON validation and the Harness-selected verification. Produce this Task's evidence and manifest only after their sources are final; do not create an evidence-only PR/CI cycle.
2. After final review and exact final head, run exactly one low-priority cloud candidate with distinct, new disposable PostgreSQL fresh `0001..0034` and upgrade `0001..0032 -> 0033 -> 0034` databases. Preflight disk/CPU/memory, use separate redacted migrator/app/worker logins, keep async sync off, capture source-admission/v1 compatibility/v2 snapshot binding/route/worker/rollback proof, then dispose only these named resources after archive identity checks.
3. Only if the candidate, fresh final-head CI and Harness gates pass, follow the existing runbook to back up and apply production `0030`--`0034`, activate the dormant dedicated worker, deploy the exact binding, smoke exact ready/blocked/unsupported/readback and prove no timer/backflow. If any gate fails, disable the binding/worker and leave the current page explicitly unavailable; never fall back to legacy `analyze`.
4. Obtain the four named real-WeChat acceptance items on the unchanged `simc_submit` page before any Task 5A delivery-closure claim. Task 6C remains unstarted.
