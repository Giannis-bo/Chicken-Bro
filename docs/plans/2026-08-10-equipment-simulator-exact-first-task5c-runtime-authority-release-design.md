# Exact-first Task 5C：有界 Runtime Authority Release 设计

状态：`design_approved / implementation_not_authorized（2026-08-10：用户确认首期只让已有事实完整闭合的远端模板进入 ready；不等待全赛季 PVE Universe，零个、多个、漂移或未建模 relation 继续 literal blocked。本文只冻结后续 Strict task 的设计，不授权任何 provider、migration、candidate、production、worker activation、Catalog/Manifest/generation 35 或 UI 改动。）`

## 用户结果与范围

玩家继续在既有 `simc_submit` 页面提交一个 remote saved template。只有后端能从该模板的 server-owned source binding 重放同一份装备、规则、effect occurrence、profile 和 SimC runtime 时，确认/提交才可变为 ready；否则页面保持现有 blocked 状态，绝不回退 legacy `analyze`。

首期是有界 release，而不是“全赛季装备已齐全”的承诺：一个 release 可以覆盖零个或少量已闭合模板。未进入 release 的模板、local/handoff 来源、缺 tier/set/cross-slot/loadout 事实、unknown/unsupported record 和任一 identity drift 都是正常的 literal non-ready outcome。

本设计承接 Task 5A 的本地 foundation 与 Task 5B 的 source-gap audit；它不修改它们已记录的 local evidence，也不把 Task 3A、3B 或 4W 的 candidate/delivery closure 改写为用户闭环。

## 已验证输入与不得采用的捷径

可作为**发布时输入**的事实只有：

1. 0033 的 append-only remote-template → exact Authority Bundle binding；它重读 owner/template/source signature 并钉住 slot-bound envelope keys。
2. 0030 的 typed-reload Exact Authority Bundle、其 `simc-item-effect-record-v1` canonical bytes/key/hash，以及 bundle 的 rule/resolver/runtime revisions。
3. Task 4L 的纯 `loadout_effect_authority` owner：它从 first-pass Resolver 的 ordered subject descriptors 和 sealed record 序列构造并重验 aggregate。
4. 发布程序在受控 admission 时读取的 Resolver context、game/SimC/compiler/worker identity。它们必须在发布前逐项验证、canonicalize 并写进 immutable document；运行时不得重新读取 mutable pointer。

以下都不能作为 runtime authority：active Catalog/Manifest、`PostgresCacheStore` compatibility context、`latest` row、进程常量、client input、单个 slot 的相似 itemId、worker active、HTTP 200 或 Task 5A 注入 fake。

## Frozen release model

### 1. Immutable documents

Task 5C 的唯一 release owner 应创建三个 append-only canonical document kinds；每个 document 都只从 canonical bytes 得到 key/hash，key 不写回自己的 payload。

| Kind / schema / key prefix | 必须内容 | 运行时用途 |
| --- | --- | --- |
| `exact_runtime_resolver_context` / `exact-runtime-resolver-context-v1` / `exact-runtime-resolver-context:sha256:` | `schemaRevision`、完整 typed Resolver authority context、`seasonRevision`、`gearRuleRevision`、`resolverRevision`、`simcRuntimeRevision`、producer/source revision | 仅以自身 bytes/key/hash 重建 first-pass `resolve_v2` 的 authority context。 |
| `exact_runtime_authority_release` / `exact-runtime-authority-release-v1` / `exact-runtime-authority-release:sha256:` | `schemaRevision`、producer identity/revision、resolver-context key/hash、八项 dependency vector：`seasonRevision`、`gameBuild`、`gearRuleRevision`、`resolverRevision`、`compilerRevision`、`workerRevision`、`simcRuntimeRevision`、`effectAuthorityRevision` | 绑定一次 SimC job 所需的所有运行依赖。 |
| `exact_runtime_occurrence_index_entry` / `exact-runtime-occurrence-index-entry-v1` / `exact-runtime-occurrence-index-entry:sha256:` | `schemaRevision`、release key、full `subjectVariantSignature`、`resolvedGearSignature`、sealed `simc-item-effect-record` key、record canonical SHA-256、producer/source revision | 唯一定位一个动态 occurrence 的 effect record；record bytes 仍只从 0030 canonical-document row typed-reload，不存任何“latest”排序语义。 |

resolver-context document 内的 full authority context 是发布时唯一允许消费 compatibility/read-model 的位置。发布完成后，runtime 只重读 document bytes；之后任何 Catalog/Manifest/compatibility 变化不影响该 release。

八项 vector 必须全为 bounded canonical identity token。release 与 resolver context 必须逐项一致其共同拥有的 season/rule/resolver/runtime identity；0033 binding 和每一个 loaded bundle 则必须一致其实际钉住的 rule/resolver/runtime identity。缺字段、额外字段、boolean、空白、hash drift 或来源不一致都禁止 seal。

### 2. Explicit source-release membership

新的 append-only membership relation 的唯一 key 是 `(exact_template_authority_binding_key, runtime_release_key)`；它保存两端 canonical bytes/key/hash 的验证记录和 admission identity。它不写入 Catalog/Manifest、app template 的公开响应或 source binding 的历史 bytes。

首期规则特意保守：对一个可重放的 0033 binding，membership read **必须恰有一行**。零行或多行都 `EXACT_AUTHORITY_UNAVAILABLE`。因此本 Task 不实现 release rotation、active pointer、latest selection 或自动升级；一个不同 runtime/producer/vector 的 release 必须等待新 source identity 的独立 admission 设计。此限制避免把“当前版本”偷偷降级为可变默认值。

app 可把 server-generated opaque `releaseKey` 连同现有 source ref 发送回来，但它只是不可信 selector。后端必须先按 owner/template 重读 source binding，再核对该 release membership；客户端不能选择无 relation 的 release，也不能凭 key 构造 authority。若当前 UI 需要这项 opaque ref，只允许增加无视觉变化的 prepare/binding 编排，不得修改 route、JSX hierarchy、文案、SCSS、导航或公开 raw authority。

### 3. Dynamic occurrence relation

运行时先用 sealed resolver-context 完成 first-pass `resolve_v2`。其 Task 4L subject descriptor 会产生包含完整 `resolvedGearSignature` 与 revisions 的 `subjectVariantSignature`；index 对每一个此 signature 在同一 release 内必须返回恰好一个 sealed `simc-item-effect-record`。

后端逐项 typed-reload record 后，按 first-pass descriptor 的原始顺序和重复次数调用 `resolve_loadout_effect_authority(...)`。仅当 aggregate 是 `verified`，再将其注入 final `resolve_v2`、ResolvedLoadout v2 与 SimulationSnapshot v2；同一 signature 的重复 occurrence 可以引用同一 record key，但绝不 dedupe occurrence。`unsupported` 保持 `LOADOUT_EFFECT_UNSUPPORTED`；unknown、缺项、额外项、record substitution、ordinal/order drift、不同 release 或 aggregate 重验失败都保持 `LOADOUT_EFFECT_AUTHORITY_REQUIRED`。

没有 loadout-scoped subject 的模板仍必须有完整 release/vector/resolver context，但不需要 occurrence index row；它不会伪造空 effect authority。

## Publication, read and rollback protocol

1. 受控 `wow_migrator` admission 接收一个完整、bounded release input：明确 producer/source revision、八项 vector、typed resolver context、已重读的 0033 binding key 和 ordered occurrence → sealed record keys。它不接受 client JSON，也不在运行时生成 release。
2. admission 先 typed-reload every binding/bundle/record，first-pass resolve，重算 every descriptor variant，再比较整个 ordered multiset。仅在完全相等时，以一个 transaction 写入三个 canonical documents、membership 和 index relations。
3. `wow_app` 仅通过 owner-scoped security-definer read function 读取一个 source binding 的明确 release、resolver context 和 occurrence rows；`wow_exact_worker` 仅可重读 snapshot/job 所引用的 already-sealed release facts。两者均无 release/index table direct DML；`wow_migrator` 是唯一 writer。
4. `ExactSimcMaterializer` 接收明确 release reader。它不能访问 Catalog pointer、compatibility store、latest queries 或 process default；任何 read exception 均映射为现有 unavailable/blocked envelope。
5. 回滚只禁用 provider/worker binding，使 Exact HTTP 返回 `EXACT_AUTHORITY_UNAVAILABLE`。不删除/更新 release、index、snapshot 或 job，也不回退 `/api/simulator/analyze`。

## Success, verification and delivery topology

后续 implementation task 必须明确创建自己的 requirement/evidence/manifest，并作为**唯一 complete runtime delivery packet**验证 Task 5A foundation 加 Task 5C release provider 的组合树。Task 5A packet 保持 `local_verified / candidate_pending`，不能被改写成完成；Harness CI 只应选择新的 complete packet。

RED/GREEN matrix 至少覆盖：

- canonical document bytes/key/hash reload、八项 vector exact key set、resolver-context bytes/hash drift；
- one binding/one release 成功，零/多 membership blocked，owner isolation 与 private-field rejection；
- dynamic descriptor 的 zero/one/multiple index row、record key/bytes/runtime drift、重复 occurrence/order preservation、unsupported/unknown cases；
- no-loadout-effect ready path、Task 5A source/profile ref strictness、no legacy analyze fallback、v1 request bytes/key stability；
- migration freshness/upgrade、table/function ACL、app/worker least privilege、candidate rollback and no async backflow；
- unchanged `simc_submit` route/JSX/SCSS/copy, plus the four real-WeChat acceptance items only after candidate and production gates.

在实现前必须把 exact files、0035+ migration number、release input producer、database role/function signatures、candidate fresh/upgrade chain、rollback runbook 和 UI binding seams 写进独立 Harness requirement。实现之后先做一次新的、低优先级、资源预检通过的 cloud-only disposable PostgreSQL candidate；通过独立 CR、final-head CI、candidate 与 Harness 才能生产 migration、provider/worker activation 和你在既有页面的真实微信验收。

## Explicit non-goals

- 不承诺全赛季 PVE Universe，不下载/导入新的外部装备数据，不启动 Task 6C observation/Catalog admission。
- 不修改当前 UI 的视觉、入口、文案、路由、导航、Catalog/Manifest pointer 或 generation 35。
- 不重跑或重建 Task 3A、3B、4W 的 candidate/CI/cleanup，不把其 internal evidence 写成玩家闭环。
- 不使用本机 PostgreSQL；不在本设计阶段创建 candidate、部署、生产 migration、service enable/start 或云端写入。
