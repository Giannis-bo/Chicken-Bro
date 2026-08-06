# Exact-first Task 4L：Loadout-scoped Effect Authority

状态：`archived（2026-08-06：PR #116 exact-head full CI run 31071444226 通过，合并为 d4eac363，并完成 merge-result scoped Harness；仅 pure-domain 归档，无 runtime/candidate/production/API/UI/SimC 用户路径声明）`

## Goal

为活跃的 loadout-scoped effect 建立一个纯函数、内容寻址且可完整重验的 authority aggregate。它只解除拥有完整、当前 revision 的 authority 的 v2 loadout；缺失、未知、错序、伪造、未建模的 tier/cross-slot/loadout subject 均继续 fail closed。

## 用户与范围边界

玩家最终需要的是“完整装备组合可模拟，缺少 effect authority 时明确说明原因”，而不是前端或 Resolver 猜测 tier/set 效果。本任务只建立后续持久化和运行链可消费的纯领域合同；它不接入数据库、worker、API、UI、SimC 执行、service 或 deploy，也不把 generation 35、Catalog/Manifest pointer、Task 3A candidate 或 v1 事实改写为新状态。

Task 3B 仍保持阻断。它在此合同独立审查和 fresh verification 后，才可按下文已冻结的 document/key relation、ordered occurrence relation 和 rehydration boundary 纳入 `0031`；本任务不得预先修改 migration 或 store。

## Frozen owner and canonical contract

唯一 loadout-scoped schema/rehydration/completeness owner 是新文件 `server/gear_loadout_effect_authority.py`。它消费由正常 Resolver 生成的 v2 boundary snapshot、Rule Matrix 的 explicit canonical subject projection，以及 sealed `simc-item-effect-record-v1` documents。`server/simc_item_effect_support.py` 仍只拥有 Exact-item aggregate；不得把 loadout scope 混入该模块，亦不得修改 Task 3A 的五 target source-change-control registry。Task 3A 的历史 owner maps 和 gate 继续记录其当时的 stage 列表；Task 4L 的独立 permit 不改写那些历史事实。

Aggregate 固定为：

- document kind：`loadout_effect_authority`；schema：`loadout-effect-authority-v1`；key prefix：`loadout-effect-authority:sha256:`。
- exact payload key set：`schemaRevision`、`status`、`resolvedGearSignature`、`gearRuleRevision`、`resolverRevision`、`simcRuntimeRevision`、`subjects`、`supportRecords`。

### Canonical descriptor、subject variant 与 sealed aggregate

Rule Matrix 的 `loadout_effect_subjects(...)` 是唯一 descriptor projection。当前输出只允许 `set_bonus` occurrence，且每个 element 的 exact key set 为 `subjectKind`、`itemSetId`、`pieces`、`subjectKey`：

- `subjectKind` 必须恰为 `set_bonus`；`itemSetId` 与 `subjectKey` 是非空 canonical identity token（最多 256 UTF-8 bytes）；`pieces` 是非 bool integer `1..16`。
- 输入来自 `effective_set_state.activeDynamicEffects` 时，`itemSetId`、`pieces`、`effectId -> subjectKey` 必须逐项保留；fallback aggregation 也必须投影这四项。任何缺字段、空 token、非整数/越界 pieces 或非 set subject 使 projection 不能产生 authority。
- canonical sequence 必须按 `(subjectKind, itemSetId, pieces, subjectKey)` 升序排序，最多 128 个 occurrence；相同 tuple 是合法的不同 occurrence，必须相邻保留。禁止 `set`/dict dedupe、按 record key 排序、缺失、额外、替换或重排。第 129 个或之后的 descriptor 使 owner 返回 `unknown`、不 seal aggregate，Resolver 保持 literal `LOADOUT_EFFECT_AUTHORITY_REQUIRED`。

对于每一个该序列位置，owner 只以如下 canonical payload seal variant；document kind、schema、payload key set 和 prefix 均固定：

```json
{
  "documentKind": "loadout_effect_subject_signature",
  "schemaRevision": "loadout-effect-subject-signature-v1",
  "keyPrefix": "set_bonus-variant:sha256:",
  "payload": {
    "schemaRevision": "loadout-effect-subject-signature-v1",
    "subjectKind": "set_bonus",
    "subjectKey": "<canonical token>",
    "itemSetId": "<canonical token>",
    "pieces": "<canonical non-bool int 1..16>",
    "resolvedGearSignature": "<boundary token>",
    "gearRuleRevision": "<boundary token>",
    "resolverRevision": "<boundary token>",
    "simcRuntimeRevision": "<boundary token>"
  }
}
```

`pieces` above is a JSON number, not a string. The owner validates the exact payload itself; it never trusts a caller-supplied signature. The resulting content key is the only permitted `subjectVariantSignature` for that occurrence.

`subjects` is an ordered multiset of `1..128` elements whose each element has exactly `subjectKind`、`subjectKey`、`subjectVariantSignature`、`status`、`supportRecordKey`; status is exactly `verified` or `unsupported`, and `supportRecordKey` matches `^simc-item-effect-record:sha256:[0-9a-f]{64}$`. `supportRecords` has the same `1..128` length and positions. Every element is an exact revalidated `simc-item-effect-record-v1` payload plus `supportRecordKey`: its key set is exactly one of static verified `{schemaRevision,status,subjectKind,subjectKey,subjectVariantSignature,hasDynamicEffect,simcRuntimeRevision,verifiedAt,supportRecordKey}`, dynamic verified `{schemaRevision,status,subjectKind,subjectKey,subjectVariantSignature,hasDynamicEffect,simcRuntimeRevision,verifiedAt,effectType,expectedActionTokens,expectedBuffTokens,experimentSnapshotKey,controlSnapshotKey,supportRecordKey}`, or unsupported `{schemaRevision,status,subjectKind,subjectKey,subjectVariantSignature,hasDynamicEffect,simcRuntimeRevision,verifiedAt,unsupportedReason,supportRecordKey}`. Each must be reconstructed with existing `reload_effect_record` semantics before comparison.

At every ordinal, descriptor-derived kind/key/variant, subject entry and reloaded record kind/key/variant/status/key must agree exactly. Aggregate `status` is `verified` iff every position is verified; it is `unsupported` iff one or more positions are unsupported; `unknown` never seals a document. Thus a repeated support-record key is legal only when it occupies the corresponding repeated descriptor occurrence; it is never deduplicated.

The public owner surface is frozen as:

```python
def resolve_loadout_effect_authority(
    resolver_snapshot: Any,
    *,
    records: Sequence[SealedCanonicalDocument],
) -> LoadoutEffectAuthorityOutcome: ...

def reload_loadout_effect_authority(
    canonical_bytes: bytes,
    content_key: str,
    *,
    resolver_snapshot: Any,
) -> SealedCanonicalDocument: ...

def verify_loadout_effect_authority(
    document: Any,
    *,
    resolver_snapshot: Any,
) -> bool: ...
```

The first function is the only builder; the latter two recompute the complete boundary and rehydrate the embedded records, not a permissive JSON shape. `LoadoutEffectAuthorityOutcome` follows the existing effect outcome trichotomy: `verified` and `unsupported` each carry one sealed aggregate, while `unknown` carries no document and non-empty canonical issues. Any `tier`、`cross_slot`、other loadout kind or malformed descriptor yields `unknown`, no aggregate, and the literal required block.

### Resolver-bound consumer and occurrence schema

`resolve_v2(selection_intent, authority_context, *, loadout_effect_authority=None)` is the sole resolver injection point. With no active subject, its current Task 4P v2 boundary key set and bytes are untouched. With active subjects and no aggregate, unknown/malformed aggregate, mismatching resolved signature/revisions/descriptors/records, it emits the existing active blocked boundary and literal `blocked / LOADOUT_EFFECT_AUTHORITY_REQUIRED`. A sealed unsupported aggregate emits literal `blocked / LOADOUT_EFFECT_UNSUPPORTED`. Only a verified aggregate permits active v2 readiness and adds exactly `loadoutEffectAuthorityKey` to that active verified boundary; the key must equal the owner document key. Resolver never builds an aggregate or infers a subject.

`build_resolved_loadout_v2(..., loadout_effect_authority=None, ...)` and `verify_resolved_loadout_v2(..., loadout_effect_authority=None)` are the only v2 loadout consumers. `build_simulation_snapshot_v2(..., loadout_effect_authority=None, ...)` and `verify_simulation_snapshot_v2(..., loadout_effect_authority=None, ...)` receive and reverify the same optional sealed document through the resolved-loadout contract. These keyword-only defaults preserve all existing callers and the no-active-effect Task 4P v2 branch unchanged.

For an active verified aggregate only, ResolvedLoadout v2 and SimulationSnapshot v2 each add the exact top-level field `loadoutEffectAuthorityKey` and bind it in their identity/hash. They append loadout occurrences after every existing slot occurrence in this exact form:

```json
{
  "scope": "loadout",
  "loadoutEffectAuthorityKey": "loadout-effect-authority:sha256:<64 lowercase hex>",
  "recordOrdinal": "<non-bool integer from 0>",
  "subjectKind": "set_bonus",
  "subjectKey": "<canonical token>",
  "subjectVariantSignature": "set_bonus-variant:sha256:<64 lowercase hex>",
  "supportRecordKey": "simc-item-effect-record:sha256:<64 lowercase hex>"
}
```

`recordOrdinal` above is a JSON integer, not a string. The loadout sequence is exactly ordinal `0..n-1` for `n in 1..128` from the aggregate `subjects`, with one occurrence per aggregate position; it follows all Task 4P slot occurrences and may repeat every value except its ordinal. The existing `scope='slot'` occurrence schema is untouched. Any unknown scope, count above 128 or a mixed/incorrect key set fails closed. If there is no active loadout subject, `loadoutEffectAuthorityKey` is absent, no `scope='loadout'` occurrence exists, and Task 4P v2 shape/key plus every v1 byte/key/hash/behavior remain exactly unchanged. v1 paths neither accept nor read this field.

## File allowlist

实现只允许：

- Create: `server/gear_loadout_effect_authority.py`、`tests/gear_loadout_effect_authority_test.py`。
- Modify: `server/gear_rule_matrix.py`、`server/gear_resolver.py`、`server/gear_resolved_loadout.py`、`server/simulation_snapshot.py`。
- Modify tests only: `tests/gear_rule_matrix_test.py`、`tests/gear_resolver_test.py`、`tests/gear_resolved_loadout_test.py`、`tests/simulation_snapshot_test.py`、`tests/simulation_snapshot_compat_test.py`。
- Control plane only: this plan, `docs/plans/2026-08-04-equipment-simulator-exact-first-persistence-resequence.md`, `docs/plans/README.md`, `docs/roadmap.md`, and, only after the independent plan review is PASS, exactly the three Task 4L packet files below.
- Create/modify only after plan-review PASS: `artifacts/releases/2026-08-06-equipment-simulator-exact-first-task4l/requirement.json`, `evidence.json`, `manifest.json`.

Do not modify `docs/project-state.json`, either historical owner map or its Task 3A gate test, Task 3A/4P packets, Canonical owner registry/fixture, `server/simc_item_effect_support.py`, `server/gear_exact_authority.py`, any DB/migration/store/worker/service/deploy/API/UI file, or Catalog/Manifest/generation 35 state. Any need to alter this list is a scope expansion and stops the task.

## TDD and review gates

### Task 4L.1: Freeze the owner and aggregate RED matrix

- [x] Add failing tests for a complete verified set aggregate, exact bytes/key reload, missing/extra/reordered/substituted records, repeated same-key occurrence, descriptor/signature/revision/runtime/resolved-signature drift, unsupported evidence, 128/129 occurrence boundary, and unmodelled tier/cross-slot/loadout kinds.
- [x] Run `python3 -m unittest tests.gear_loadout_effect_authority_test tests.gear_rule_matrix_test` and confirm the new cases fail before implementation.
- [x] Implement only the owner, Rule Matrix ordered occurrence projection and direct-server imports.
- [x] Re-run the same matrix and `python3 -m py_compile server/gear_loadout_effect_authority.py server/gear_rule_matrix.py`.
- [x] Obtain an independent scoped CR before moving to Task 4L.2.

### Task 4L.2: Consume authority in Resolver and v2 loadout/snapshot

- [x] Add failing tests proving absent/malformed/mismatched/unknown authority keeps `LOADOUT_EFFECT_AUTHORITY_REQUIRED`; verified aggregate alone permits ready; unsupported aggregate is blocked; v1 plus no-loadout-effect v2 identities are stable; loadout occurrences preserve order/multiplicity and snapshot binds the same aggregate/key/sequence.
- [x] Run the named failing tests before implementation.
- [x] Implement the minimal Resolver, ResolvedLoadout and SimulationSnapshot propagation; do not alter compatibility or runtime consumers unless a failure proves an allowlisted test-only correction is sufficient.
- [x] Run the focused matrix below and direct-server imports.
- [x] Obtain an independent scoped CR before final whole-branch review.

## Fresh verification and evidence ceiling

The required focused command is:

```sh
python3 -m unittest tests.gear_loadout_effect_authority_test tests.gear_rule_matrix_test tests.gear_resolver_test tests.gear_resolved_loadout_test tests.simulation_snapshot_test tests.simulation_snapshot_compat_test
```

An independent plan review has passed against this frozen contract, so the Task 4L Harness packet is now established. Run relevant existing Exact/effect regressions, `py_compile` for every allowlisted Python module, JSON/Harness validation and `git diff --check`. A fresh independent whole-branch CR and exact final-head PR full CI are required. This task can reach only `local_verified` before explicit Harness User Acceptance Closure; runtime identity, candidate deployment, production migration, endpoint/timer smoke and manual UI acceptance are all `not_applicable`.
