# 装备模拟 Exact-first 持久化与运行链重排计划

> **For agentic workers:** REQUIRED SUB-SKILLS: Use `superpowers:subagent-driven-development`, `superpowers:test-driven-development`, and `superpowers:verification-before-completion`. This plan forward-replaces the old implementation plan's Task 3 and later execution order after two independent readiness audits returned `NOT_READY`.

状态：`正在推进（Task 3A delivery closure 已完成：PR #114 合并、scoped Harness、main/origin parity 与严格限定的候选资源清理均已完成；其正式 packet 仍为 runtime_verified / candidate_verified 且 closure identity 为 pending，因为现行 lifecycle test 不建模 archived。Task 4P 已在 Harness User Acceptance Closure 下完成 pure-domain 归档，合并为 d5a1f813；Task 4L 也已完成 pure-domain 归档，合并为 d4eac363。Task 3B delivery closure 已完成：final-head `t3b260806203541` fresh/upgrade PostgreSQL candidate、独立 CR、PR #117 CI `31102912308`、merge `61eddf45`、merge-result scoped Harness、main/origin parity 和严格限定的候选资源清理均已完成；正式 packet 保持 runtime_verified / candidate_verified 与 closure identity pending。Task 4W 的 final-head `t4w260807000500` cloud-only fresh/upgrade PostgreSQL candidate、独立 CR、PR #118 exact-head CI `31119305966`、merge `14f47437`、merge-result scoped Harness、main/origin parity、归档与严格限定的候选资源清理均已完成；正式 packet 保持 runtime_verified / candidate_verified 与 closure identity pending，因为 lifecycle contract 不建模 archived。Task 5A 的 local source/profile/job/API/client foundation 已完成，仍未接入 active runtime ready-path。Task 5B 已冻结为 `requirement_challenged`：当前不存在 immutable eight-field runtime release 或动态 loadout occurrence→sealed effect-record authority relation；因此 provider、0035+ migration、candidate、production activation 与 Task 6C 均未授权，ready-path 保持 literal blocked。）`

## Goal

在已完成的 pure Canonical foundation 上，先建立可完整重验的 append-only authority bundle，再建立纯函数 v2 Resolver/ResolvedLoadout/SimulationSnapshot，之后才修改 v1/v2 snapshot persistence，最后引入 owner-scoped jobs、独立 worker 权限、lease/retention、API 和运行时消费。

本计划不把“foundation 已通过”扩张为“持久化/worker/runtime 已就绪”。

## Why the old order is stopped

旧 Task 3 不可直接执行：

- effect record 已冻结为 `simc-item-effect-record-v1` / `simc-item-effect-record:sha256:`；旧 SQL 仍使用过期身份；
- `ExactAuthorityEnvelope` 实际只保存 Exact、Static、Progression、Effect Aggregate 的 keys 与 resolver revision；旧 SQL 没有保存完整 dependency closure；
- canonical identity 来自精确 bytes，JSONB 不能成为唯一身份载体；
- 旧 Task 3 要求 store round-trip v2 loadout/snapshot，但对应 v2 builder/verifier 在旧 Task 5 才存在；
- job schema 没有 `finished_at` / `cooldown_until`，不能表达 terminal+7d retention 或 failed cooldown；
- 当前 app/worker 共用 `wow_app`，不能兑现 worker-only claim/prune/authority writes。

因此旧实施计划 Task 3-8 只保留历史，不再授予执行权。本计划是唯一活动 replacement。

## Immutable boundaries

- generation 35、Catalog/Manifest pointers、Phase 0-4 证据和所有 v1 canonical bytes/key 不变。
- `proofClaim=source_change_control_only`；不得把 registry 当 runtime authority。
- raw plugin text 不入 DB、job、result、log、artifact 或公开 payload。
- Catalog membership 不决定 simulation readiness；`originCatalogRevision` 只做 canonical document 之外的 provenance。
- 每个阶段 scoped review 未同时 `PASS/APPROVED`，不得进入下一阶段。
- 任何 migration/runtime slice 在真实 PostgreSQL candidate evidence 前不得标记 release-ready。

## Revised execution order

1. **Task 3A:** Canonical authority bundle rehydration + append-only persistence (`0030`)，无 runtime consumer。
2. **Task 4P:** 提前完成纯函数 v2 Resolver、ResolvedLoadout、SimulationSnapshot（替代旧 Task 5 的 pure domain 部分），无 DB/runtime；遇到 loadout-scoped effect 先显式阻断。
3. **Task 4L:** 单独设计并 review loadout-scoped effect subject/aggregate authority；未完成前不得把 tier/set/cross-slot effect 配置标成 ready。
4. **Task 3B:** v1/v2 conditional loadout/snapshot persistence (`0031`)，只消费 Task 4P/4L 的 verifier。
5. **Task 4W:** owner-scoped jobs、独立 worker DB role、lease/retention/metrics 与 worker service (`0032`)。
6. **Task 5A:** Exact import API、正式 SimC submit 接合与 UI typed contract。
7. **Task 6C:** observation/candidate/admission 从 `0033` 开始，保持独立 candidate/release gate。

## Execution authority and changed-file boundaries

- 每一阶段开始前重新读取 `docs/project-state.json`、`docs/roadmap.md`、本计划、原实施计划顶部的 stopped/replacement 状态和 Harness requirement；只以本计划中该阶段的 allowlist 为执行权。目录存在、旧 checkbox 或 Git 历史都不授予执行权。
- Task 3A 的完整 allowlist 就是下方 Scope 列出的代码/测试/迁移，加 `docs/plans/README.md`、`docs/roadmap.md`、原 Exact-first 实施计划及四份 Canonical foundation/correction 计划的顶部状态、本计划、Harness `requirement.json`/`evidence.json`/`manifest.json`、两个 owner map 和 `docs/postgres-identity-migration-runbook.md` 的任务状态/候选数据库说明。2026-08-05 授权的 migration-chain correction 额外且仅允许 `server/migrations/postgres/0003_build_template_config_hash_unique.sql`，以及已经允许的两份 PostgreSQL 测试和上述状态控制面；最后这些控制面文件不得借机改变产品承诺。
- **2026-08-05 merge-scope exception:** 用户在最终独立 CR 识别到 PR #114 将已完成的 Pure Canonical foundation/source-change-control 与 Task 3A 放在同一不可变 branch diff 后，明确授权将 reviewed implementation HEAD `32495d951f61a7ee0328030c84211dd724cc846c` 所代表的已审核前置 foundation 与 Task 3A 一并合并。此例外只解决该既有 PR 的 integration scope：不允许新增任何代码/测试/迁移，也不放宽未来 Task 3A 或 Task 4P 的 allowlist；它不改变第八次 runtime candidate `9f230f2e` / tree `89e7e5e`、不授权 production/runtime/API/UI/worker 或 generation 35 变更。
- Task 4P 只允许修改 `server/gear_resolver.py`、`server/gear_rule_matrix.py`、`server/gear_resolved_loadout.py`、`server/simulation_snapshot.py`、`server/simulation_snapshot_compat.py`、`tests/gear_resolver_test.py`、`tests/gear_rule_matrix_test.py`、`tests/gear_resolved_loadout_test.py`、`tests/simulation_snapshot_test.py`、`tests/simulation_snapshot_compat_test.py`，再加上述状态控制面文件；不得改 DB、service、deploy、API 或 UI。2026-08-06 用户仅授权一项已完成 Task 3A 的 lifecycle-control reconciliation：额外且仅可修改 `tests/gear_canonical_owner_gate_test.py` 与 `tests/postgres_schema_test.py`，使历史 promotion window 锚定已记录的 Task 3A SHA parity、并按 current-summary 与 detailed-history 文档职责验证状态；不得改 Task 3A packet、candidate/runtime identity、资源、产品行为或本 Task 4P 的 pure-domain 语义。
- Task 4L 的独立 owner、canonical aggregate schema、完整性证明、文件 allowlist 与 0031 persistence impact 由 `2026-08-06-equipment-simulator-exact-first-task4l-loadout-effect-authority.md` 冻结。其 Strict pure-domain slice 已归档；随后用户明确授权 Task 3B，且其独立 requirement/replay-context review 已将执行严格限定在下述 0031 persistence allowlist。该授权不扩展至 4W、5A、6C 或任何 production/runtime/user-visible action。
- Task 3B 只允许修改 `server/migrations/postgres/0031_websim_exact_snapshot_v2.sql`、`server/simulation_snapshot_store.py`、`tests/simulation_snapshot_store_test.py`、`tests/postgres_schema_test.py`、`tests/postgres_integration_test.py` 与状态控制面文件；不得引入 job/worker/runtime consumer。
- Task 4W 只允许修改 `server/migrations/postgres/0032_websim_exact_import_jobs.sql`、`server/gear_exact_import_job_store.py`、`server/gear_exact_authority_worker.py`、`server/wow-gear-exact-authority-worker.service`、`server/deploy_lighthouse.sh`、`tests/gear_exact_import_job_store_test.py`、`tests/gear_exact_authority_worker_test.py`、`tests/postgres_schema_test.py`、`tests/postgres_integration_test.py`、数据库 runbook 与状态控制面文件。API/UI 仍不激活。
- Task 5A 的用户确认设计和 `requirement.json` 位于 `2026-08-07-equipment-simulator-exact-first-task5a-api-runtime.md` 与 `artifacts/releases/2026-08-07-equipment-simulator-exact-first-task5a/requirement.json`；其 local TDD foundation 已完成，但 ready-path 仍不得推进。后续 [Task 5B authority-source contract](2026-08-07-equipment-simulator-exact-first-task5b-active-authority-source.md) 已冻结 source gap，用户确认并授权 local implementation 的 [Task 5C Runtime Authority Release](2026-08-10-equipment-simulator-exact-first-task5c-runtime-authority-release-design.md) / [implementation plan](2026-08-10-equipment-simulator-exact-first-task5c-runtime-authority-release-implementation.md) 规定 project-owned、仅覆盖闭合模板的 immutable release 与 forward-only v3 identity；0033 仍只能重放 source-to-slot-bundle closure，0031 仍只保存已完成 aggregate。Task 5C 的 candidate、deployment 或生产状态仍只能在其独立 Harness gates 后发生；Task 6C 仍须自行补出全部 task-scoped allowlist、用户可见验收、candidate/rollback 和独立 review；本计划当前只给顺序和边界，不提前声明其完成。
- 任一阶段 diff 越出 allowlist、迁移编号碰撞、当前真相改变或需要触碰 generation 35/Catalog pointers 时立即停止并更新计划，不通过临时 exemption 扩权。

---

## Task 3A：完整 Canonical Authority Bundle 持久化

### Scope

**Canonical reload boundary**

- Modify: `server/gear_canonical_kernel.py`
- Modify: `tests/gear_canonical_kernel_test.py`
- Modify: `server/gear_exact_item_instance.py`
- Modify: `tests/gear_exact_item_instance_test.py`
- Modify: `server/gear_exact_authority.py`
- Modify: `tests/gear_exact_authority_test.py`
- Modify: `server/simc_item_effect_support.py`
- Modify: `tests/simc_item_effect_support_test.py`

**Persistence**

- Modify: `server/migrations/postgres/0003_build_template_config_hash_unique.sql` only for the authorized fail-closed semantic-idempotence migration-chain correction
- Create: `server/migrations/postgres/0030_websim_exact_authority_bundle.sql`
- Create: `server/gear_exact_authority_store.py`
- Create: `tests/gear_exact_authority_store_test.py`
- Create: `tests/gear_exact_authority_store_import_boundary_test.py`
- Modify: `tests/postgres_schema_test.py`
- Modify: `tests/postgres_integration_test.py`

**Source change-control and control plane**

- Modify: `tests/fixtures/gear_canonical_owner_registry.json`
- Modify: `tests/gear_canonical_owner_gate_test.py`
- Modify: `tests/simc_gear_import_test.py` only to bind the Harness packet to the active Task 3A slice/resequence heading instead of the stopped four-slice plan
- Modify: `artifacts/releases/2026-08-04-equipment-simulator-exact-first/requirement.json`
- Modify: `docs/project-owner-map.json`
- Modify: `docs/backend-owner-map.json`
- Modify: `docs/plans/README.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/plans/2026-08-04-equipment-simulator-exact-first-implementation.md` only for stopped/replacement status
- Modify: `docs/plans/2026-08-04-equipment-simulator-canonical-kernel-redesign.md` only to remove the stale “original Task 3 may start” claim
- Modify: `docs/plans/2026-08-04-equipment-simulator-canonical-kernel-implementation.md`, `docs/plans/2026-08-04-equipment-simulator-canonical-owner-change-control.md`, and `docs/plans/2026-08-04-equipment-simulator-duplicate-effect-subject-correction.md` only for the same superseded top-level status
- Modify: `docs/postgres-identity-migration-runbook.md` only for the two-database candidate procedure
- Create/Modify: `artifacts/releases/2026-08-04-equipment-simulator-exact-first/evidence.json` and `manifest.json` only after real candidate evidence exists
- Modify: this plan only for checklist/status

Task 3A must not modify `simulation_snapshot_store.py`, `postgres_cache_store.py`, jobs, worker, API, Resolver, loadout/snapshot domain schemas, deployment, Catalog or runtime.

### 2026-08-05 authorized migration-chain correction

Two real candidates failed before the then-current `0026` authority migration: `t3a2608050955` at `f90a302040f722fec0807bd600f8e2242169801c` because `0001` already creates `UNIQUE (user_id, template_type, config_hash)` while `0003` unconditionally added the target; then `t3a260805111623` because `0003` compared catalog `name[]` with `text[]`. Third run `t3a260805113656` passed but its requirement gate was wrong. Fourth run `t3a260805120026` passed 0026 but was superseded by main migrations 0026-0029. Fifth run `t3a260805125812` passed 0030 but its exact source failed direct-server runtime. Sixth run `t3a260805142130` passed final 0030 and audit but its exact source failed an owner lifecycle test. Seventh run `t3a260805160003` genuinely passed final 0030 from exact frozen commit `8c9490cdc074001ca58c03a6e67bacf2806b33fa` / tree `f71aad198ab66e4ff22b6f893b004bccfd3e35b4` and independent read-only audit; however, that frozen HEAD's full profile failed because `docs/plans/README.md` and `docs/roadmap.md` omitted literal `0030`, while the schema current-truth test hard-coded `implementation_allowed` despite a legitimate `local_verified` packet. PostgreSQL was not the cause. Correcting the lifecycle test, owner contracts and status docs invalidated seventh-run promotion. Eighth run `t3a260805163536` used a distinct run id and two new databases and passed at exact runtime commit `9f230f2e0c44a0157fb58870f10197e5525c227a` / tree `89e7e5e70ca16cfba20f4140df7995a463b7ce31`; owner/lifecycle verification commit `1714f376d40e21112b13f537572932a1f5bd38f0` / tree `7ba9ff1863822a90ffd081d3de70c0f7af3dfbc2` later passed the unique full profile, Harness and exact two-path candidate→verification gate. Current formal status is `runtime_verified / candidate_verified`; runtime/verification identities are separately bound. Delivery closure completed through PR #114 merge, scoped Harness, main/origin parity and exact eighth-candidate cleanup; closure identity remains pending because the lifecycle contract does not model `archived`. All prior seven run pairs and fourteen databases are immutable/non-reusable.

Historical status continuity: the fifth clean 0030 candidate was invalidated by direct-server import; the sixth and seventh clean 0030 candidates passed PostgreSQL but are unpromotable after separate current-truth lifecycle-test regressions. Historical literal `candidate_rerun_required / evidence_promotion_blocked` was cleared only after the distinct eighth candidate passed and the separately bound owner/lifecycle verification HEAD satisfied both executable diff windows.

The authorized `0003` correction is locally implemented and independently reviewed: it retains the legacy-name drop; conditionally creates the target unique constraint only when absent; then verifies with `pg_catalog.pg_constraint` and `pg_catalog.pg_attribute` that exactly one target constraint is on `app.build_templates`, has `contype = 'u'`, and ordered columns `user_id, template_type, config_hash`, otherwise raises an explicit exception. It does not swallow `duplicate_object`, drop/recreate an already-correct target, change `0001`, add a retro migration or reconcile ledger state. The seventh candidate used a new run-id and two newly provisioned databases and proved the exact constraint/ledger invariants, but remains historical-only. Eighth-candidate pre-connect validation rejected all seven historical run ids, and `t3a260805163536` independently proved the runtime source. Candidate→verification diff contains only the owner test and this plan; verification→promotion diff is restricted to the six declared Task 3A evidence/status files. Runtime evidence promotion does not imply production activation or delivery closure.

### Canonical reload contract

Storage reload is a new explicit raw-bytes boundary, not a generic caller-authored payload API.

- Kernel owns one bounded private rehydration primitive that accepts exact `bytes + content_key + kind + schema + prefix + domain validator`, reruns byte/depth/node/UTF-8/duplicate-key/canonical-byte/hash checks, and returns `SealedCanonicalDocument` only on exact equality.
- The primitive is not exported through Kernel `__all__`; only registered domain owners may import it, and the source-change-control registry must record the exact import.
- Domain modules expose typed reload functions for:
  - Exact v2 item;
  - Exact Static Facts bound to Exact;
  - Progression bound to Exact and production Track Authority;
  - Effect Record bound to runtime;
  - Effect Aggregate bound to Exact, runtime and ordered records;
  - Exact Authority Envelope bound to all four documents.
- The only public reload signatures are frozen as follows; each raises `CanonicalValueError` on any mismatch and returns an exact `SealedCanonicalDocument`, never `CanonicalResult`, raw dict or normalized fallback:
  - `reload_exact_item(canonical_bytes: bytes, content_key: str) -> SealedCanonicalDocument`;
  - `reload_exact_static_facts(canonical_bytes: bytes, content_key: str, *, exact: SealedCanonicalDocument) -> SealedCanonicalDocument`;
  - `reload_exact_progression(canonical_bytes: bytes, content_key: str, *, exact: SealedCanonicalDocument) -> SealedCanonicalDocument`; it replays production Track Authority from the sealed payload's season/rule/slot/crafted inputs;
  - `reload_effect_record(canonical_bytes: bytes, content_key: str, *, runtime_revision: str) -> SealedCanonicalDocument`;
  - `reload_effect_aggregate(canonical_bytes: bytes, content_key: str, *, exact: SealedCanonicalDocument, runtime_revision: str, records: tuple[SealedCanonicalDocument, ...]) -> SealedCanonicalDocument`;
  - `reload_exact_authority_envelope(canonical_bytes: bytes, content_key: str, *, exact: SealedCanonicalDocument, static_facts: SealedCanonicalDocument, progression: SealedCanonicalDocument, effect_support: SealedCanonicalDocument, resolver_revision: str) -> SealedCanonicalDocument`.
- Store code imports only those typed domain reload functions. It must not import private validators, parse/normalize domain fields, instantiate sealed documents, or invent a second serializer.
- `tests/gear_exact_authority_store_import_boundary_test.py` is an independent AST/import gate for the store: it allowlists only the typed reload functions, sealed-document/dataclass typing and DB adapter imports; direct imports of Kernel private names, domain validators, canonical serializers or Catalog owners fail. This store gate does **not** add a sixth registry target: the source-change-control registry stays exactly five targets/nine exemptions and its claim stays `source_change_control_only`.

Each reload function receives stored canonical bytes/key, rebuilds the sealed domain document, and rejects any bytes/key/schema/binding drift. No `strip`, coercion, normalization, JSONB round-trip or Catalog lookup is allowed.

### PostgreSQL schema

`0030` is rechecked as free immediately before creation and creates only three append-only cache tables. The migration-number prefix is globally unique across `0001..0030`; origin/main's `0026..0029` remain unchanged.

#### `cache.websim_canonical_documents`

- `content_key text PRIMARY KEY`
- `document_kind text NOT NULL`
- `schema_revision text NOT NULL`
- `canonical_bytes bytea NOT NULL CHECK (octet_length(canonical_bytes) BETWEEN 2 AND 1048576)`
- `canonical_json jsonb NOT NULL CHECK (jsonb_typeof(canonical_json) = 'object')` as a query/constraint projection only
- `canonical_sha256 text NOT NULL CHECK (canonical_sha256 ~ '^[0-9a-f]{64}$')`
- `sealed_at timestamptz NOT NULL DEFAULT clock_timestamp()`
- migration preflight requires the PostgreSQL core function `pg_catalog.sha256(bytea)`; absence is a hard blocker and does not authorize `pgcrypto` or an application-only hash check;
- `canonical_sha256 = pg_catalog.encode(pg_catalog.sha256(canonical_bytes), 'hex')`;
- `canonical_json = pg_catalog.convert_from(canonical_bytes, 'UTF8')::jsonb`;
- the closed matrix requires `content_key = <kind-specific prefix> || canonical_sha256`, not only a matching suffix.
- a closed kind/schema/prefix matrix for exactly:
  - `exact_item` / `gear-exact-item-instance-v2` / `exact-item-instance:sha256:`
  - `exact_static_facts` / `exact-static-facts-v1` / `exact-static-facts:sha256:`
  - `exact_progression` / `exact-progression-binding-v1` / `exact-progression:sha256:`
  - `effect_record` / `simc-item-effect-record-v1` / `simc-item-effect-record:sha256:`
  - `effect_aggregate` / `simc-item-effect-support-v1` / `simc-item-effect-support:sha256:`
  - `exact_authority` / `exact-authority-envelope-v1` / `exact-authority:sha256:`

`canonical_bytes` is the identity source. The database independently hashes those bytes and verifies their JSONB projection; `canonical_json` never generates the key and never replaces byte verification. Typed reload remains responsible for strict duplicate-key, NFC, canonical lexical bytes and domain bindings that JSONB cannot prove.

#### `cache.websim_effect_aggregate_records`

- `(effect_support_key, ordinal)` primary key;
- `effect_support_key` foreign key to canonical documents;
- `effect_record_key` foreign key to canonical documents;
- ordinal bounded `0..127`;
- repeated `effect_record_key` at different ordinals is allowed;
- insert-time trigger verifies aggregate/record document kinds and the aggregate JSON binding at that ordinal. Application reload verifies exact ordered equality with aggregate `supportRecords`.

#### `cache.websim_exact_authority_bundles`

- `exact_authority_envelope_key` primary/foreign key;
- foreign keys for `exact_item_instance_key`, `static_facts_key`, `progression_binding_key`, `effect_support_key`;
- derived query projections: `gear_rule_revision`, `simc_runtime_revision`, `resolver_revision`;
- insert-time trigger verifies all component kinds and exact JSON key bindings, including envelope keys and projection equality;
- no owner, Catalog membership or provenance fields.

Every trigger/function in `0030` is schema-qualified, `SECURITY INVOKER`, and declares `SET search_path = pg_catalog, pg_temp` with the temporary schema last; it never resolves an unqualified table/function. Foreign keys provide committed-row existence under concurrency, while the binding triggers lock/reference the exact keyed rows in the same statement. The store inserts documents first, then ordered relations/bundle, and performs exact readback before commit; a concurrent same-key/different-value write fails the insert/readback transaction rather than winning by last-write.

All three tables receive immutable triggers. Explicitly `REVOKE INSERT, UPDATE, DELETE, TRUNCATE FROM wow_app` and grant only `SELECT` in 0030. Task 3A has no runtime writer; Task 4W later grants an independent worker role. Migration/migrator and tests may write during candidate verification.

### Store contract

The store return type is frozen as:

```python
@dataclass(frozen=True)
class ExactAuthorityBundle:
    exact_item: SealedCanonicalDocument
    static_facts: SealedCanonicalDocument
    progression: SealedCanonicalDocument
    effect_records: tuple[SealedCanonicalDocument, ...]
    effect_support: SealedCanonicalDocument
    envelope: SealedCanonicalDocument
```

`GearExactAuthorityStore` provides no “latest”, Exact-key search or partial-success authority:

- `seal_authority_bundle(bundle: ExactAuthorityBundle) -> ExactAuthorityBundle`
- `load_verified_bundle(envelope_key, *, gear_rule_revision, simc_runtime_revision, resolver_revision) -> ExactAuthorityBundle`
- `load_verified_bundles(envelope_keys, *, gear_rule_revision, simc_runtime_revision, resolver_revision) -> tuple[ExactAuthorityBundle, ...]`
- `load_effect_records(record_keys, *, simc_runtime_revision) -> tuple[SealedCanonicalDocument, ...]`

Batch loads preserve caller input order and multiplicity exactly: `A, B, A` returns bundles/records in `A, B, A` order. They reject empty/invalid keys and any missing or revision-mismatched occurrence. A progression is season/track-authority bound, so an Exact item key is never an authoritative lookup key; callers must provide the exact envelope key selected for that slot.

Write path:

1. reverify every live sealed document through the typed reload path;
2. require envelope/component keys and ordered aggregate record keys to match exactly;
3. insert the entire closure in one transaction;
4. use insert-if-absent then exact readback comparison; identical writes are idempotent, same key/different bytes or projections are integrity errors;
5. never accept raw dicts or individual unbound documents as a successful bundle.

Read path loads exact canonical bytes, reconstructs Exact -> Static/Progression -> ordered Effect Records -> Effect Aggregate -> Envelope, and returns only a fully reverified immutable bundle. Any missing row, wrong kind/schema/key/runtime/rule/resolver, reordered duplicate record or byte drift fails closed.

### TDD and verification

- [x] Preflight found origin/main occupying `0026..0029`; stop, integrate main and move Task 3A atomically to globally unique `0030`.
- [x] RED Kernel/domain reload: exact bytes/key pass; whitespace, duplicate key, non-NFC, over-bound, wrong kind/schema/prefix/key and cross-document binding fail.
- [x] RED store: full frozen-dataclass round-trip, `A/B/A` batch order, identical idempotency, collision, missing component, wrong runtime/rule/resolver, duplicate/gapped/extra/missing effect-record ordinal, repeated same record at two ordinals, reordered non-adjacent duplicate, concurrent same-key writes, tampered canonical bytes/hash/JSON projection, distinct `1`/`1.0`/exponent lexical bytes and partial transaction rollback.
- [x] RED store import boundary: direct Kernel-private/domain-validator/serializer/Catalog imports fail while typed reload imports pass; registry remains five targets/nine exemptions and `source_change_control_only`.
- [x] RED SQL/static: exact kind/schema/prefix/hash/bytes-to-JSON matrix, both aggregate FKs, component FKs/binding trigger, fixed search path, immutable triggers, wow_app SELECT-only and unique migration identity.
- [x] RED migration-chain correction: old `0003` lacks strict `app.build_templates`/`contype = 'u'`/ordered-column verification, explicit semantic-drift failure and fail-closed handling; focused test fails against the unconditional target add.
- [x] RED PostgreSQL integration uses two operator-provisioned empty disposable databases and never creates/drops a database. `WOW_PG_TEST_RUN_ID_0030` matching `^[a-z0-9]{8,32}$`, `WOW_PG_TEST_DSN_FRESH_0030`, and `WOW_PG_TEST_DSN_UPGRADE_0030` are mandatory. The suite rejects prior run ids `t3a2608050955`, `t3a260805111623`, `t3a260805113656`, `t3a260805120026`, `t3a260805125812`, `t3a260805142130`, and `t3a260805160003` before importing `psycopg` or connecting. The DSNs must identify distinct exact-commented empty databases. Fresh applies `0001..0030`; upgrade applies `0001..0029`, seeds and snapshots frozen v1 rows, then applies `0030`. Both candidates bind the final runtime-affecting commit, Git tree and 0030 SHA-256 and emit `task3a-candidate-attestation-v2`. Candidate 后若修改 runtime/product code、migration、PostgreSQL candidate integration test、requirement 或 owner contract，runtime candidate 即失效并要求重跑；纯 lifecycle fixture/control-plane correction 仅在 candidate commit 到 verification HEAD 的 runtime-affecting production/migration/PG-candidate/requirement/owner path diff 为空、路径差异无重复且精确只有 `tests/gear_canonical_owner_gate_test.py` 与本 active resequence plan，并且 final clean verification HEAD 通过 full profile 与 Harness 时，才允许保留原 candidate runtime identity。随后 verification HEAD 必须是实际 Git `HEAD` 的祖先，且 verification HEAD 到实际 `HEAD` 的 promotion window 差异无重复并精确只有 Task 3A 的 `evidence.json`、`manifest.json`、本 active resequence plan、`docs/plans/README.md`、`docs/postgres-identity-migration-runbook.md` 与 `docs/roadmap.md`；该窗口由实际 `git rev-parse HEAD`、`git merge-base --is-ancestor` 和 `git diff --name-only` 重算，混入任何 production、migration、PG candidate test、requirement 或 owner-map 路径都失败。The fourth, fifth, sixth and seventh runs remain immutable historical evidence and are forbidden for reuse.
- [x] PR CI run `30993690037` exposed a Python 3.11/3.13 representation drift: Python 3.11 includes empty optional AST fields that Python 3.13 `ast.dump(show_empty=False)` omits, producing 29 false owner-gate failures against unchanged registry digests. `_ast_digest` now uses one recursive, version-stable canonical serializer with the Python 3.13 default semantics; existing registry and assignment SHA values remain unchanged. This correction changes no runtime/product code, migration, PostgreSQL candidate integration test, requirement, owner contract or candidate identity and is not a runtime candidate failure; only the later clean `1714f376` full-profile verification authorizes promotion.
- [x] Implement minimal reload/store/migration; do not add jobs or snapshot v2.
- [x] Run focused suites, full Canonical matrix, owner gate, existing v1 store/snapshot suites, Node/Harness/JSON/pycompile/diff.
- [x] Freeze both existing v1/v2 Exact keys.
- [x] Independent spec/code review is `PASS/APPROVED` with zero unresolved findings on the historical clean candidate code/test state; it cannot promote the corrected tree.
- [x] Fourth candidate `t3a260805120026` genuinely passed the former 0026 chain and remains immutable historical evidence, but is `runtime_passed_superseded_by_main_integration` and cannot close the integrated Task 3A.
- [x] As of historical merge commit `1619815c`, origin/main integration, the 0030 correction, local verification and independent whole-branch CR had passed before the direct-server correction; that pre-correction packet was not current `local_verified` evidence and cannot override the later clean-HEAD promotion recorded below.
- [x] Fifth candidate `t3a260805125812` genuinely passed from exact clean commit `a4c0fd04` / tree `aa0908eb` using two new explicit-commented databases; its attestation-v2 and post-audit are immutable historical evidence.
- [x] PR #114 full-profile run `30977816268` / job `92215539827` identified the direct-server import regression and focused RED/GREEN correction; the Node deprecation warning is not the cause.
- [x] Historical controller full local profile passed at clean tested HEAD `87ba835f20bc0ca9eb762419a08b9be4ee54057a`, but the later lifecycle test/control-plane correction invalidated that verification identity; it remains historical only.
- [x] Sixth candidate `t3a260805142130` genuinely passed PostgreSQL and independent read-only audit, but the frozen HEAD owner current-truth test failed; history status is `runtime_passed_unpromotable_evidence_lifecycle_test_regression` and PostgreSQL is not the cause.
- [x] Correct the evidence lifecycle gate, reject all historical candidate/evidence identity reuse, complete scoped independent re-review at `d31279d19ac6ae5eedf381665678c3bf6d869377`, and remove the redundant top-level transitional status lock at `7a4390c9794dd46b5e95aa142409bfcc6952bf74`.
- [x] Exact full local profile passed at clean tested HEAD `7a4390c9794dd46b5e95aa142409bfcc6952bf74` / tree `606a17509aa5294cc1de8ceb129f0046bc2cd5a9`: exit 0, `status=project_verification_passed`, 173 commands, Node 747/747, Python 2716/2716 with two expected real-PG candidate-environment skips, Vitest 437/437 and all remaining checks/Harness pass; current evidence is `local_verified / candidate_pending`.
- [x] Seventh candidate `t3a260805160003` genuinely passed migration `0030` PostgreSQL and independent read-only audit, but its exact frozen source failed three full-profile current-truth assertions; history status is `runtime_passed_unpromotable_current_truth_lifecycle_test_regression` and PostgreSQL is not the cause.
- [x] Eighth candidate `t3a260805163536` passed from exact runtime commit `9f230f2e0c44a0157fb58870f10197e5525c227a` / tree `89e7e5e70ca16cfba20f4140df7995a463b7ce31`; owner/lifecycle verification commit `1714f376d40e21112b13f537572932a1f5bd38f0` / tree `7ba9ff1863822a90ffd081d3de70c0f7af3dfbc2` passed the unique 173-command full profile (Node 747/747, Python 2718/2718 with two expected real-PG candidate-environment skips, Vitest 437/437), Harness and exact owner-test plus active-plan candidate→verification gate. Current evidence is `runtime_verified / candidate_verified`, identities are separately bound, and `nextCandidate=null`.
- [x] Delivery closure completed: corrected PR CI `31002327763` passed, PR #114 merged as `97fca062`, post-merge and final-archive scoped Harness verification passed, main/origin parity was confirmed before cleanup, and only the exact eighth disposable databases were discarded after identity checks. Remote artifacts remain in recoverable quarantine and the local bundle remains in Trash; the merged Task 3A implementation worktree and local feature branch were removed, while the remote feature ref was already absent after PR merge. Historical fourteen databases were not touched. Formal packet status remains `runtime_verified / candidate_verified` and closure identity `pending` because the current lifecycle test does not model an archived stage. Production migration/runtime consumer remain unauthorized; Task 4P is separately user-authorized but not part of Task 3A.

`t3a2608050955` 与 `t3a260805111623` 已在 `0003` 前失败；`t3a260805113656` 因 requirement gate 不可晋升；第四次 `t3a260805120026` 为 `runtime_passed_superseded_by_main_integration`；第五次 `t3a260805125812` 为 `runtime_passed_invalidated_by_direct_runtime_import_regression`；第六次 `t3a260805142130` 为 `runtime_passed_unpromotable_evidence_lifecycle_test_regression`；第七次 `t3a260805160003` 为 `runtime_passed_unpromotable_current_truth_lifecycle_test_regression`。前七次十四座库全部 immutable/non-reusable；第八次 `t3a260805163536` 是当前 `candidate_verified` 双库，且 migration `0030` 无 production migration/runtime consumer。

2026-08-05 第七次 candidate 真实通过 0030 与独立只读审计，但 frozen HEAD `8c9490cd` 的 exact full profile RED 证明其 current-truth source 不是 full-profile green；其 `runtime_passed_unpromotable_current_truth_lifecycle_test_regression` 状态永久保留。随后第八次 `t3a260805163536` 在 exact runtime source 上通过 0030、attestation 与两层只读审计，verification HEAD `1714f376` 通过 unique full profile、Harness 与 executable split-identity diff gates。PR CI `30993690037` 的 Python 3.11 AST 空字段兼容性失败属于 verification serializer 缺陷，已由同一 clean HEAD 纠正，不是 runtime candidate 失败。PR #114 合并后，合并结果与最终归档记录通过 scoped Harness、main/origin parity 确认后，仅当前第八次双库被处置，候选产物可恢复隔离；前七次十四库未触碰。证据保持 `runtime_verified / candidate_verified`；closure identity 仍 pending 是现行 lifecycle test 的明确约束，不是 production 或用户体验完成声明。

---

## Task 4P: Pure v2 Resolver / Loadout / Snapshot

This task executes the old Task 5 pure-domain intent before any v2 store changes.

**状态（2026-08-06）：已完成纯函数归档（`archived`）。** `2e60fb5e` 的 pure-domain source 经 `238028f1` 的 Task 3A lifecycle-control reconciliation、exact-head PR CI run `31064766939` full profile 成功和独立最终 CR 后，合并为 `d5a1f813` 并通过 post-merge scoped Harness。它保持 pure-domain 合同：无 runtime identity、candidate、production、API/UI/SimC 用户路径或 release 完成声明；Task 4L/3B 仍不激活。

- Add v2 builders/verifiers in Resolver, ResolvedLoadout, SimulationSnapshot and compatibility modules.
- Exact Authority Envelope and item effect records use the frozen prefixes:
  - `exact-authority:sha256:`
  - `simc-item-effect-record:sha256:`
- v2 loadout identity binds `exactAuthorityBySlot`, an ordered non-empty list of `{slot, exactAuthorityEnvelopeKey}`. Entries include occupied slots only and must follow `CANONICAL_GEAR_SLOTS`; a slot appears at most once. The same Exact item may legally occur in two slots, but progression binds slot, so each pair must load a bundle whose `progression.trackAuthorityInput.slot` equals the pair's slot; two different slots therefore cannot reuse one Envelope key. Verifiers reject input/key sorting, duplicate slot/key, slot/progression mismatch or a pair list that differs from the resolved loadout.
- Task 4P's initial `effectEvidenceByOccurrence` is an ordered multiset of slot-scoped `{scope='slot', slot, exactAuthorityEnvelopeKey, recordOrdinal, subjectKind, subjectKey, subjectVariantSignature, supportRecordKey}`. Entries follow `CANONICAL_GEAR_SLOTS`, then each Envelope aggregate's record ordinal; array position and full occurrence fields preserve repeated item/record occurrences, and neither key sorting nor set/dict deduplication is allowed.
- Task 4P does not invent an incomplete loadout-level record list. If Rule Matrix derives any tier/set/cross-slot/loadout-scoped effect subject, Resolver returns literal `blocked` / `LOADOUT_EFFECT_AUTHORITY_REQUIRED`. Task 4L must later introduce one reviewed subject owner and completeness aggregate before such a loadout can become ready.
- v2 identity also binds Rule/Resolver/compiler/SimC runtime revisions. It never binds Catalog membership or provenance.
- `originCatalogRevision` stays outside canonical payload/hash.
- v1 builder/verifier remains a separate strict branch and all historical bytes/key stay unchanged.
- No DB, job, worker, API, UI or deployment changes.

Task 4P RED cases must include main/off-hand legality, same Exact with distinct slot-bound Envelopes in finger1/finger2 and trinket1/trinket2, rejection of one Envelope reused across slots, repeated identical effect record occurrences, non-adjacent duplicate records, reordered slot input, reordered evidence input, and fail-closed tier/set subjects. Canonical-equivalent caller order produces the same builder output; verifier input that is not already canonical fails closed.

Task 4P requires a separately reviewed implementation slice before Task 3B.

## Task 3B: v1/v2 conditional snapshot persistence (`0031`)

Only after Task 4P and a separately reviewed Task 4L completeness contract exist; this section does not itself authorize `0031`:

- alter loadout/snapshot tables with schema-conditioned Catalog/registry/envelope-key checks;
- add `exact_authority_by_slot_json` as the exact Task 4P slot-bound ordered pairs for v2 and exact `[]` for v1; do not store a unique key-only array that loses slot or multiplicity;
- add `effect_evidence_by_occurrence_json` with the exact Task 4P ordered multiset for v2 and exact `[]` for v1;
- add a separate append-only `cache.websim_loadout_effect_authorities` table rather than extending Task 3A's closed `cache.websim_canonical_documents` kind matrix. Its exact columns are `loadout_effect_authority_key text PRIMARY KEY`, `schema_revision text NOT NULL`, `canonical_bytes bytea NOT NULL`, `canonical_json jsonb NOT NULL`, `canonical_sha256 text NOT NULL`, and `sealed_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp()`; it requires `schema_revision = 'loadout-effect-authority-v1'`, canonical bytes length `2..1048576`, object JSON, `canonical_json ? 'schemaRevision' AND canonical_json->>'schemaRevision' = schema_revision`, `canonical_sha256 = encode(sha256(canonical_bytes),'hex')`, JSON equal to decoded bytes, and key exactly `loadout-effect-authority:sha256:` plus that hash. The table itself is the `loadout_effect_authority` document-kind discriminator, so no other kind/schema payload can occupy it.
- add append-only `cache.websim_loadout_effect_authority_records(loadout_effect_authority_key, ordinal, effect_record_key, sealed_at)`: primary key `(loadout_effect_authority_key, ordinal)`, `ordinal 0..127`, a `DEFERRABLE INITIALLY DEFERRED` foreign key from authority key to the new table, and foreign key from effect record key to `cache.websim_canonical_documents(content_key)`. It must not impose a unique `effect_record_key`, because repeated occurrence is semantically required. `0031` defines one shared checker invoked by two `AFTER INSERT DEFERRABLE INITIALLY DEFERRED FOR EACH ROW` constraint triggers: one on authority-parent insertion and one on relation-row insertion. Parent and all relation rows may be inserted in either order within one transaction; at transaction end the checker must prove the relation ordinals are exactly contiguous `0..jsonb_array_length(supportRecords)-1`, each `effect_record_key` equals that authority payload's `supportRecords[ordinal].supportRecordKey`, each referenced canonical document is `effect_record`, and cardinality exactly equals the payload array length. Thus missing tail, extra, duplicate, gapped, reordered or substituted relation rows fail at commit, rather than observing a transient incomplete parent. Both new tables receive the existing append-only update/delete/truncate rejection and the same no-direct-write privilege boundary as Task 3A records.
- add nullable `loadout_effect_authority_key` foreign-key columns to both persisted ResolvedLoadout and SimulationSnapshot rows. Every v1 row must have this column `NULL` and exact `effect_evidence_by_occurrence_json = []`. A v2 row with no active loadout effect also has `NULL`, no `scope='loadout'` occurrence and its Task 4P identity unchanged. A v2 row with an active loadout effect must have one matching `loadout-effect-authority:sha256:` key, a JSON `loadoutEffectAuthorityKey` equal to that column, and an exact ordered `scope='loadout'` suffix whose every occurrence names that key and whose ordinal/record key matches the authority relation.
- add nullable `resolver_replay_context_json` only to persisted ResolvedLoadout rows. It is a bounded noncanonical `exact-resolver-replay-context-v1` projection that preserves exactly the Task 4P/4L verifier inputs: `status=verified`; dependency revisions; resolved gear signature; class/spec eligibility; verified profile readiness and required/ready slots; minimal occupied resolved-slot `{slot,itemId,legality.status}` values; `setState`; ordered `loadoutEffectSubjects`; and the matching verified `v2EffectBoundary`. The projection has no raw plugin text, player/realm identity, Catalog revision or source payload, is not included in `loadout_json`, `snapshot_json`, any canonical key or row hash, and has a fixed 1 MiB JSON-object bound. v1 rows require it to be `NULL`; every v2 row requires it to be non-NULL. For an active effect the saved verified boundary carries the same aggregate key; for owner reload only, the store clones this projection, changes both statuses to literal `blocked` and removes that one boundary key before calling `reload_loadout_effect_authority`. This is a status-only replay adaptation, not a Rule Matrix derivation: the store must never reconstruct descriptors from slots, infer an aggregate or validate a second JSON shape. SimulationSnapshot rows do not duplicate this context; they load their referenced ResolvedLoadout and reuse its exact saved projection.
- `SimulationSnapshotStore` must reload the authority through `reload_loadout_effect_authority`, rehydrate every relation entry through `reload_effect_record`, and reuse the Task 4L ResolvedLoadout/SimulationSnapshot verifiers for the complete v2 row. It must not duplicate JSON-shape validation or rederive the aggregate from slots. Its migration triggers must reject a mismatched aggregate key, missing/extra/reordered relation row, v1 non-NULL key/non-empty effect evidence, and any v2 active occurrence whose stored aggregate/key/relation does not match its canonical bytes.
- v2 `SimulationSnapshotStore.seal_loadout` accepts the full resolved v2 verifier context only as an explicit keyword argument, persists the minimal replay projection, reads every Exact Authority Bundle through the Task 3A store, and reloads an active aggregate from `0031` before accepting the row. v1 callers keep the current signature and behavior. On every v2 load or snapshot load, a missing, oversized, non-object, mixed v1/v2, revision/signature/boundary/slot mismatch, or failed typed reload is an integrity error; no fallback to stored JSON or Catalog occurs.
- keep `originCatalogRevision` in separate provenance columns/wrappers, outside stored canonical documents and row hashes;
- reuse Task 4P verifiers in `SimulationSnapshotStore`; no duplicated v2 validator;
- preserve every historical v1 row/key/hash and append-only trigger;
- require fresh and 0030->0031 real PostgreSQL migration evidence.

## Task 4W: Owner-scoped jobs and worker (`0032`)

Task 4W uses two principals and never grants role-management power to migrations or services:

- `wow_exact_worker` is a pre-provisioned `NOLOGIN` group role. `0032` starts with a fail-closed existence/`rolcanlogin=false` assertion; it never executes `CREATE ROLE` and neither `wow_migrator`, `wow_app` nor the service receives `CREATEROLE`.
- an operator-created `LOGIN INHERIT` principal is granted membership in `wow_exact_worker` outside the migration, with credentials held only in `/etc/wow-exact-worker.env` as `WOW_EXACT_WORKER_DATABASE_URL`; every worker connection immediately executes `SET ROLE wow_exact_worker` and verifies `session_user` membership plus `current_user='wow_exact_worker'`. The worker refuses `WOW_DATABASE_URL`.
- `server/wow-gear-exact-authority-worker.service` reads only the worker env file. Candidate/deploy preflight verifies the NOLOGIN group role, LOGIN membership, redacted distinct DSNs and rollback to the prior service/env; `docs/postgres-identity-migration-runbook.md` owns the provisioning/check/rollback procedure.
- migration/runtime preflight also requires PostgreSQL core `pg_catalog.gen_random_uuid()`; absence is a hard compatibility blocker and does not authorize an implicit extension install.

`0032` creates exactly:

- `ops.websim_exact_import_jobs` with `job_id bigserial`, `owner_key_hash text CHECK '^sha256:[0-9a-f]{64}$'`, `request_key text CHECK '^exact-import-request:sha256:[0-9a-f]{64}$'`, `request_bytes bytea` bounded to 131,072 bytes, matching object `request_json jsonb` bounded to 131,072 bytes, `status pending|running|resolved|blocked|unsupported|failed`, `terminal_classification NULL|resolved|incomplete|illegal|runtime_gap|internal_error`, `attempt 0..3`, `locked_by text` bounded to 160 characters, DB-generated `lock_token uuid`, `lease_until`, `queued_at`, `started_at`, `heartbeat_at`, `finished_at`, `cooldown_until`, object `result_json` bounded to 131,072 bytes, object `problem_json` bounded to 16,384 bytes, `created_at`, `updated_at` and the exact row-state checks below;
- `uq_ops_websim_exact_jobs_deterministic` as a partial unique index on `(owner_key_hash, request_key)` for `pending|running|resolved|blocked|unsupported`, `idx_ops_websim_exact_jobs_failed_cooldown` on `(owner_key_hash, request_key, cooldown_until DESC, job_id DESC)` for failed rows, `idx_ops_websim_exact_jobs_claim` on `(status, lease_until, queued_at, job_id)`, and `idx_ops_websim_exact_jobs_retention` on `(finished_at, job_id)` for terminal rows;
- `ops.websim_exact_worker_state` keyed by `worker_id`, with runtime/worker revisions, current job, status, heartbeat and object `last_outcome_json` bounded to 16,384 bytes;
- `ops.websim_exact_import_metrics_daily` keyed by `(metric_day, terminal_classification, catalog_status)`, with only aggregate count and timestamps.

Job row checks are not implementation-defined:

- `pending`: `attempt=0`; lock/token/lease/start/heartbeat/finish/cooldown/classification are NULL or empty as appropriate;
- `running`: `attempt BETWEEN 1 AND 3`; non-empty `locked_by`, non-NULL UUID token/lease/start/heartbeat; finish/cooldown/classification NULL;
- `resolved|blocked|unsupported`: cleared lock/token/lease, non-NULL start/finish/classification, NULL cooldown; classification must map respectively to `resolved`, `incomplete|illegal`, or `runtime_gap`;
- `failed`: cleared lock/token/lease, non-NULL start/finish, classification `internal_error`, and `cooldown_until = finished_at + interval '15 minutes'`;
- every terminal row has `finished_at >= started_at`; pending/running rows never have a terminal classification. Retry policy identity is frozen as `exact-import-retry-policy-v1` with three total claims, 30-second leases and a 15-minute failed cooldown.

The only accepted request schema is canonical `exact-import-job-request-v1` with exact top-level keys `schemaRevision`, `exactLoadoutIntent`, and `dependencyVector`. The dependency vector has exact keys `seasonRevision`, `gameBuild`, `gearRuleRevision`, `resolverRevision`, `compilerRevision`, `workerRevision`, `simcRuntimeRevision`, and `effectAuthorityRevision`. A typed domain builder verifies the canonical Exact intent, rejects recursively any `rawProfile|rawString|playerName|characterName|realm|server` field, emits canonical bytes, and computes the expected request key. PostgreSQL independently requires `request_json = convert_from(request_bytes,'UTF8')::jsonb` and computes `request_key = 'exact-import-request:sha256:' || encode(sha256(request_bytes),'hex')`. Enqueue compares exact bytes on every reuse; worker claim reloads the same typed request and recomputes the key before doing work.

The callable surface is frozen as:

- `ops.websim_exact_enqueue(p_owner_key_hash text, p_request_bytes bytea, p_request_json jsonb) RETURNS TABLE(job_id bigint, request_key text, status text, reused boolean, cooldown_until timestamptz)`;
- `ops.websim_exact_read(p_owner_key_hash text, p_job_id bigint) RETURNS TABLE(job_id bigint, request_key text, status text, result_json jsonb, problem_json jsonb, queued_at timestamptz, started_at timestamptz, finished_at timestamptz, cooldown_until timestamptz)`;
- `ops.websim_exact_claim(p_worker_id text, p_worker_revision text, p_simc_runtime_revision text) RETURNS TABLE(job_id bigint, request_key text, request_bytes bytea, request_json jsonb, lock_token uuid, lease_until timestamptz)`;
- `ops.websim_exact_heartbeat(p_job_id bigint, p_lock_token uuid) RETURNS TABLE(job_id bigint, lease_until timestamptz)`;
- `ops.websim_exact_terminalize(p_job_id bigint, p_lock_token uuid, p_terminal_status text, p_terminal_classification text, p_result_json jsonb, p_problem_json jsonb, p_catalog_status text) RETURNS TABLE(job_id bigint, status text, finished_at timestamptz, cooldown_until timestamptz)`;
- `ops.websim_exact_update_worker_state(p_worker_id text, p_status text, p_worker_revision text, p_simc_runtime_revision text, p_current_job_id bigint, p_last_outcome_json jsonb) RETURNS void`;
- `ops.websim_exact_prune_jobs(p_limit_rows integer) RETURNS integer` and `ops.websim_exact_prune_metrics(p_limit_rows integer) RETURNS integer`.

These functions use concrete scalar/bytea/jsonb arguments and typed results, never dynamic SQL. All eight functions, including owner-scoped read, are `SECURITY DEFINER`, owned by `wow_migrator`, fully qualify all objects, declare `SET search_path = pg_catalog, pg_temp`, and are followed in the same migration transaction by signature-specific `REVOKE ALL ... FROM PUBLIC`. No caller-provided predicate is composed dynamically.

Before runtime activation:

- revoke authority INSERT and all job/metrics table writes from `wow_app`;
- explicitly `GRANT USAGE ON SCHEMA cache, ops` to `wow_exact_worker`; revoke all direct privileges on the three ops tables and `ops.websim_exact_import_jobs_job_id_seq` from `PUBLIC`, `wow_app` and `wow_exact_worker` before the function grants, overriding migration `0002` default privileges;
- grant worker only SELECT/INSERT on authority documents and EXECUTE on claim/heartbeat/terminal/worker-state/bounded-prune functions;
- app gets `EXECUTE` only on owner-scoped enqueue/read and zero table DML or full-table SELECT on the three ops tables;
- worker gets `EXECUTE` only on claim/heartbeat/terminalize/worker-state/prune functions plus SELECT/INSERT on the three `0030` authority tables; it gets zero direct UPDATE/DELETE on authority or ops tables and no owner-scoped app function;
- every other function EXECUTE ACL, including PUBLIC defaults and cross-role app/worker calls, is absent.

Job schema includes `started_at`, `finished_at`, `cooldown_until`; terminal retention is `finished_at + 7 days`, metrics retention is 90 days. All time and lease decisions use PostgreSQL `clock_timestamp()`.

Real PostgreSQL permission tests use distinct `WOW_PG_TEST_DSN_MIGRATOR_0032`, `WOW_PG_TEST_DSN_APP_0032`, and actual worker-login `WOW_PG_TEST_DSN_WORKER_0032`. They additionally exercise admin-side `SET ROLE wow_app` / `SET ROLE wow_exact_worker`, but that is not a substitute for the real login DSNs. Tests prove schema usage, allowed functions, zero PUBLIC EXECUTE, cross-owner reads returning no row, table/sequence scans or DML and wrong-role functions failing, worker `SET ROLE`, expired-token CAS updating zero rows, and prune respecting requested `1..100`; static SQL assertions alone are insufficient.

### Lease decision table

| Current condition | Operation | Required result |
| --- | --- | --- |
| no active/deterministic terminal | enqueue | new pending, attempt 0 |
| same owner+request pending/running/resolved/blocked/unsupported | enqueue | reuse existing job |
| different owner | enqueue | separate job; authority content may be shared |
| pending, attempt < 3 | claim | atomic running, attempt+1, new token/30s lease |
| running lease expired, attempt < 3 | claim | atomic reclaim with new token |
| valid token and `lease_until > clock_timestamp()` | heartbeat | extend lease |
| wrong token or expired lease | heartbeat/terminalize | zero rows; worker abandons |
| valid running lease | terminalize | one CAS + metrics in same transaction |
| attempt exhausted | reclaim | terminal failed |
| failed before cooldown | enqueue | return unavailable/existing failure |
| failed after cooldown | enqueue | new pending job allowed |
| terminal older than 7d | prune | delete at most requested 1..100 |
| pending/running | prune | never delete |

Request identity binds sanitized intent, season/game build, Rule, Resolver, worker, SimC runtime and explicit effect-authority revision. Catalog status is live/noncanonical projection, never a frozen deterministic terminal fact.

`websim_exact_enqueue` obtains a transaction-scoped PostgreSQL advisory lock derived from the validated `(owner_key_hash, request_key)` before inspecting active/terminal/failed rows. This serializes the no-row and failed-cooldown boundaries; after the 15-minute boundary exactly one concurrent call may create the next pending row and the rest reuse it. Claim uses `FOR UPDATE SKIP LOCKED`; DB generates `lock_token` with `pg_catalog.gen_random_uuid()`. When an expired running row already has `attempt=3`, claim atomically terminalizes it as `failed/internal_error`, writes bounded `ATTEMPT_EXHAUSTED` problem data and increments the daily metric in the same transaction before considering another job. Enqueue and claim both fail closed on request bytes/key/schema drift.

## Stop Gate

Stop and redesign if any task requires:

- translating current canonical keys into legacy aliases;
- storing JSONB without exact canonical bytes;
- accepting dangling or partially verified authority documents;
- adding v2 store validation before the v2 domain verifier exists;
- using `wow_app` as both public API and privileged authority worker at activation;
- creating/login-enabling roles inside application migrations or reusing `WOW_DATABASE_URL` in the exact worker;
- application-provided lease/retention time;
- changing generation 35, Catalog/Manifest pointers, v1 bytes/key or runtime before its task-scoped review.
