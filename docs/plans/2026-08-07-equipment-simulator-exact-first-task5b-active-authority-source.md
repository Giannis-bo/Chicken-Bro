# Exact-first Task 5B Active Authority Source Contract

状态：`requirement_challenged（2026-08-07：Task 5A 的 local foundation 已完成，但 active ready-path 缺少一个可证明、不可推断的 authority source。本 Task 只冻结缺口和升级条件；不授权 provider、migration、candidate、生产或 UI 变更。）`

## 用户目标与当前阻断

玩家继续使用既有 `simc_submit` 页面时，后端只能在能重放同一套装备、强化、effect occurrence、profile 与 SimC runtime 的完整 canonical identity 时创建任务。当前页面已具备严格 Exact request binding；当事实不全时，它必须继续显示既有阻断状态，而不能换回旧 `analyze` 或看似成功的部分结果。

已验证的当前事实是：Task 5A 已能通过 owner-scoped 0033 binding 重读 remote gear template 与 slot-bound `ExactAuthorityBundle`，并在显式注入的 authority 下完成 v2 Resolve、loadout/snapshot seal 和 v2 job binding。HTTP facade 因此可安全返回固定 `EXACT_AUTHORITY_UNAVAILABLE`。它不能安全返回 `ready`，因为活跃读模型尚没有以下两个事实 owner：

1. 一个封存、可 typed-reload 的八项 `dependencyVector`（`seasonRevision`、`gameBuild`、`gearRuleRevision`、`resolverRevision`、`compilerRevision`、`workerRevision`、`simcRuntimeRevision`、`effectAuthorityRevision`）；0033 只钉住其中 registry/rule/resolver/runtime 的 source-admission 维度。
2. 一个针对 first-pass `resolve_v2` 所产生的每个 loadout-scoped subject/occurrence，能唯一返回同 runtime、同 subject signature 的 sealed effect record 的 authority relation。0031 只保存已经构建完成的 aggregate；它不能从 `resolvedLoadoutKey`、Catalog、slot bundle、最新行或缓存反推出一个尚未构建的 aggregate。

这不是 Task 3A、3B、4L、4W 或 Task 5A local foundation 的失败。它是 active runtime input 尚未存在，且依现有 Exact-first 规则不得由 client、Catalog pointer、兼容 `PostgresCacheStore` vector、process constant 或“最新 support record”补齐。

## 已否决的捷径

| 方案 | 结论 | 原因 |
| --- | --- | --- |
| 从 active Catalog/Manifest 或 `PostgresCacheStore` 兼容 context 补齐 vector | 拒绝 | 该 context 无完整八项 immutable identity，且 mutable pointer 不能证明 source/occurrence closure。 |
| 从 slot bundle 或相同 itemId 推断 set/cross-slot support record | 拒绝 | 动态 subject 的 signature 含完整 resolved gear state；slot facts 不唯一决定它。 |
| 以最新 snapshot、latest effect row 或内存缓存寻找 aggregate | 拒绝 | 多个 snapshot/record 可同时有效；“最新”不是 canonical authority。 |
| 将 Task 5A 的 injected fake/provider 直接接入 runtime | 拒绝 | 这只证明接口可组合，不能提供生产数据事实。 |

## Task 5B 必须先得到的 authority contract

在任何代码、migration 或 candidate 开始前，必须由一个独立、明确授权的 authority-source contract 指定以下全部内容：

1. **runtime release identity**：一个 immutable canonical document 的 bytes/key/hash，包含且只包含八项 vector、其 schema/revision、producer identity 与 source revision；不得从环境默认值或运行进程自动拼装。
2. **resolver context identity**：该 release 如何按其自身 key 重读并验证完整 Resolver authority context，而不是读取随后变化的 Catalog/Manifest pointer。
3. **occurrence index**：对 first-pass `resolve_v2` 的每一项 subject signature，如何在同一 release 内得到唯一 sealed `simc-item-effect-record` key；零个、多个、unsupported、unknown、bytes/key/hash/runtime drift 均为 literal non-ready。
4. **publication owner 与权限**：谁能以何种受控 admission 写入该 release/index、如何校验 canonical relation、app/worker 的最小读取权限，以及为何该路径不属于隐式 Catalog/Manifest/generation 35 mutation。
5. **lifecycle/rollback**：release selection 的 explicit identity、candidate-only activation procedure、停止/disable 顺序与历史 authority/snapshot/job 的不可变性。

在这五项未共同存在前，`exact_simc_api_for_authenticated_user()` 必须继续返回 `None`，Exact HTTP 继续 fail closed，当前 UI 不作任何改动。

## 影响图

```text
remote saved template + 0033 binding
        │
        ├── unique slot bundles ──> first-pass resolve_v2 ──> subject signatures
        │                                                        │
        │                                                        ├── missing unique occurrence index ──> blocked
        │                                                        └── governed effect record keys ──> sealed aggregate
        │
        └── missing immutable eight-field runtime release ──> blocked

only after both exact owners exist
        └── ExactSimcMaterializer -> v2 loadout/snapshot -> 0034 job reference -> restricted worker
```

## Frozen boundary and allowlist

本 Task 当前只允许 control-plane 变更：

- `docs/plans/2026-08-07-equipment-simulator-exact-first-task5b-active-authority-source.md`
- `docs/plans/README.md`
- `docs/roadmap.md`
- `docs/plans/2026-08-04-equipment-simulator-exact-first-persistence-resequence.md`
- `artifacts/releases/2026-08-07-equipment-simulator-exact-first-task5b-active-authority-source/requirement.json`

明确禁止：任何 server/client/UI source、0035+ migration、existing migration edit、Catalog/Manifest/generation 35 pointer、Task 6C observation/admission、candidate、cloud DB、production migration、worker activation/service action、CI-only evidence PR 或现有 Task 3A/3B/4W/5A packet 改写。

## 重新进入 implementation 的门槛

若一个独立 Strict plan 同时给出上述五项的 concrete schema、owner、read/write ACL、exact file allowlist、RED/GREEN tests、fresh/upgrade candidate、rollback 与 user-visible acceptance，才能将其 requirement 从 `requirement_challenged` 提升为 `implementation_allowed`。该计划会是新的 runtime/data-authority task；不得通过修改本文件的状态绕过独立 review。

届时必须分别验证：

- 同一 release/vector 与同一 source bytes 重放得到相同 canonical request/loadout/snapshot identities；
- 每个 tier/set/cross-slot/loadout occurrence 都有唯一同-release effect relation，否则任务未创建；
- release、record、bundle、profile 或 runtime 任一 drift 均保持 `blocked`/`unsupported`；
- current `simc_submit` 的 route、JSX hierarchy、SCSS、copy、入口与导航不变，且无 legacy fallback；
- cloud-only disposable candidate、production rollout 和四项 real-WeChat acceptance 仍是后续独立 evidence，不能由本 Task 声明完成。

## 当前精确 blocker

目前没有可引用的 active authority release/occurrence-index contract。要继续进入实现，必须先由用户/产品明确授权一个新的 authority data-admission scope（它会与 Task 6C 的 data-source discipline 相邻，但不能借用或暗中启动 Task 6C），或者指定一个已经存在且能逐项满足本文件五项条件的 immutable source。二者在当前 control plane 都不存在。
