# 装备模拟重复 Effect Subject 语义纠偏计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` and `superpowers:test-driven-development`. This is a bounded semantic correction after the Canonical foundation whole-branch review failed; it is not an owner-gate patch and does not relax the existing Stop Gate.

状态：`正在推进（whole-branch review FAIL / 1 Important；实现与 scoped review 待完成；原 Task 3 blocked）`

## Goal

让合法 Exact v2 装备中按位置重复出现的同变体 effect subject（首先是相同宝石）仍能按 Exact 派生顺序完成 effect-support aggregate，并进入 pure `ready` authority envelope；同时继续拒绝缺失、额外、错序、错 runtime 或非 sealed records。

## Root cause

`gemIds`、`gemBonusIds`、`gemItemLevels` 是位置相关的 ordered arrays，合同没有禁止两个位置使用相同值。`derive_exact_effect_subjects()` 因而可以合法地产生两个相同 identity 的 gem subjects；但 `resolve_exact_effect_support()` 使用 `identity -> position` 与 `identity -> record` 字典，把第二个位置折叠为重复记录并返回 `DUPLICATE_EFFECT_RECORD`。

这不是 Catalog、SimC runtime 或 source change-control 问题，而是 pure semantic consumer 的 ordered-multiset 错误。2026-08-04 fresh whole-branch review 因此为 `FAIL / CHANGES_REQUIRED`。

## Fixed semantics

- Exact 派生 subjects 是有序、可重复的序列；不得去重，也不得改变 Exact v2 identity/schema。
- 输入 records 必须与 expected subjects 逐位置匹配。相同 sealed record 可以在两个相同 subject 位置重复出现，但不是强制要求；同 identity 的两个位置也可以各自使用不同 bytes/key 的有效 sealed record。
- aggregate 的 `subjects` 与 `supportRecords` 必须保留相同数量、顺序和重复项；相同 record 的 content key 可以重复。
- 同 identity 的不同有效 records 若 status/verifiedAt 不同，按各位置原样保留；任一位置为 `unsupported`，aggregate 必须为 `unsupported`，authority envelope 必须 fail closed 而不是 `ready`。
- 不把位置写入 effect-record identity，不要求对相同效果重复探测，也不修改 record schema/key。

### Reason-code decision table

在 exact/runtime/sequence type 与 record seal/reload 验证通过后，按输入 index 依次判定，前一条命中后不再尝试后续分类：

1. `index >= len(expected_subjects)`：identity 属于任一 expected subject 时为 `DUPLICATE_EFFECT_RECORD`，否则为 `UNEXPECTED_EFFECT_RECORD`。
2. identity 等于 `expected_subjects[index]`：接受该位置。
3. identity 不属于完整 expected subject 序列：`UNEXPECTED_EFFECT_RECORD`。
4. identity 出现在 `expected_subjects[index + 1:]`：`NON_CANONICAL_EFFECT_RECORD_ORDER`，即后续位置被提前提交。
5. 其余情况表示该 identity 的 expected occurrence 已在前面耗尽：`DUPLICATE_EFFECT_RECORD`。
6. 所有已提交 records 均逐位置接受、但数量小于 expected 时：`EFFECT_RECORD_MISSING`，指向第一个未满足位置。

Examples for expected `[item, A, B]`:

- `[item, A]` -> `EFFECT_RECORD_MISSING`
- `[item, B]` -> `NON_CANONICAL_EFFECT_RECORD_ORDER`
- `[item, X]` -> `UNEXPECTED_EFFECT_RECORD`
- `[item, A, A]` or `[item, A, B, A]` -> `DUPLICATE_EFFECT_RECORD`
- `[item, A, B, X]` -> `UNEXPECTED_EFFECT_RECORD`

## Scope

**Production:**

- Modify: `server/simc_item_effect_support.py`

**Tests:**

- Modify: `tests/simc_item_effect_support_test.py`
- Modify: `tests/gear_exact_authority_test.py`

**Control plane:**

- Modify: `artifacts/releases/2026-08-04-equipment-simulator-exact-first/requirement.json`
- Modify: `docs/project-owner-map.json`
- Modify: `docs/backend-owner-map.json`
- Modify: `docs/plans/README.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/plans/2026-08-04-equipment-simulator-canonical-kernel-redesign.md`
- Modify: `docs/plans/2026-08-04-equipment-simulator-canonical-owner-change-control.md`
- Modify: `docs/plans/2026-08-04-equipment-simulator-canonical-kernel-implementation.md` only to keep its stopped status current
- Modify: `docs/plans/2026-08-04-equipment-simulator-exact-first-implementation.md`
- Modify: `docs/plans/2026-08-04-equipment-simulator-duplicate-effect-subject-correction.md`
- Modify: `tests/gear_canonical_owner_gate_test.py` only for current-truth status assertions; gate/analyzer/registry/mutations must not change.

## Must not change

- Canonical Kernel, Exact v2 schema/key, effect-record schema/key, Track Authority, CLI/probe behavior and source-change-control registry.
- generation 35, Catalog/Manifest pointers, persistence/store/worker, Resolver/API/UI, SimC runtime or deployment.
- frozen v1 identities, raw plugin privacy, `proofClaim=source_change_control_only`, `runtimeConsumers=[]`, `originalTask3Activated=false`.

## Task 1: TDD ordered-multiset correction

- [ ] Add a RED aggregate test with two identical gem positions and records `[item, gem, gem]`; require `verified`, three aggregate subjects and three support records in exact order.
- [ ] Add RED boundaries for one missing occurrence, one extra duplicate, distinct-subject wrong order and an unrelated record, asserting the decision table reason codes exactly.
- [ ] Add a non-adjacent repeated-subject RED using gem order `A/B/A`; require positional aggregate order and no identity-keyed collapse.
- [ ] Add a repeated-subject RED whose two valid records have different keys/status (`verified` and `unsupported`); require both records to remain and aggregate `unsupported`.
- [ ] Add authority-envelope regressions proving all-verified duplicate-gem Exact reaches pure `ready`, while the mixed verified/unsupported duplicate remains blocked.
- [ ] Replace identity-keyed aggregation with bounded positional matching; do not add a second schema, occurrence key or deduplication pass.
- [ ] Keep all existing effect, Exact, Track Authority, CLI, owner-gate and frozen identity regressions green.
- [ ] Commit only after focused RED becomes GREEN and the full matrix passes.

## Task 2: Independent scoped review

- [ ] Fresh reviewer must replay the original duplicate-gem failure and adjacent missing/extra/order cases.
- [ ] Reviewer must confirm the production diff is limited to ordered matching and does not change schema/key/runtime behavior.
- [ ] Spec must be `PASS` and Code Quality `APPROVED` with no Critical/Important findings before re-running whole-branch review.

## Task 3: Fresh whole-branch re-review

- [ ] From `7cf5c37bb1612ca703cbfbdef21ef31024d7e1e0`, re-run the full independent whole-branch review on a committed clean HEAD.
- [ ] Re-run Python/Vitest/Node/Harness/JSON/pycompile/diff, hostile owner-gate replays and both frozen keys.
- [ ] Only simultaneous scoped `PASS/APPROVED` and whole-branch `PASS/APPROVED` allow controller status closure. This still does not activate original Task 3 or authorize runtime/release/deploy.

## Stop Gate

Stop and redesign if the fix requires any of the following:

- changing Exact v2 or effect-record schema/content keys;
- deduplicating position-sensitive Exact arrays or inventing a Catalog/runtime dependency;
- modifying the owner-gate analyzer/registry or expanding `proofClaim`;
- touching persistence, worker, Resolver/API/UI, generation 35 or SimC runtime;
- making missing, extra, unordered or unsealed evidence pass as verified.
