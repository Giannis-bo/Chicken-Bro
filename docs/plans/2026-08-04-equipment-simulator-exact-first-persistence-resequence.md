# 装备模拟 Exact-first 持久化与运行链重排计划

> **For agentic workers:** REQUIRED SUB-SKILLS: Use `superpowers:subagent-driven-development`, `superpowers:test-driven-development`, and `superpowers:verification-before-completion`. This plan forward-replaces the old implementation plan's Task 3 and later execution order after two independent readiness audits returned `NOT_READY`.

状态：`正在推进（Task 3A implementation_allowed / candidate_pending。第五次 t3a260805125812 的 0030 fresh/upgrade 与原始 attestation-v2 保留为 immutable 历史，但 PR #114 full-profile run 30977816268/job 92215539827 证明其 exact source 在 direct-server startup 回归；因此为 runtime_passed_invalidated_by_direct_runtime_import_regression。当前 runtime/verification identities 均 pending，五个 run 的十库全部 immutable/non-reusable，必须第六次新 run-id/双库在 controller full local profile 后重跑。literal candidate_rerun_required / evidence_promotion_blocked 是当前工程真相；无 production migration/runtime consumer，Task 4P+ 未授权）`

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
- Task 4P 只允许修改 `server/gear_resolver.py`、`server/gear_rule_matrix.py`、`server/gear_resolved_loadout.py`、`server/simulation_snapshot.py`、`server/simulation_snapshot_compat.py`、`tests/gear_resolver_test.py`、`tests/gear_rule_matrix_test.py`、`tests/gear_resolved_loadout_test.py`、`tests/simulation_snapshot_test.py`、`tests/simulation_snapshot_compat_test.py`，再加上述状态控制面文件；不得改 DB、service、deploy、API 或 UI。
- Task 4L 在执行前必须先冻结独立 owner、canonical aggregate schema、完整性证明、文件 allowlist 和 persistence impact，并通过 plan review；当前没有实现授权。
- Task 3B 只允许修改 `server/migrations/postgres/0031_websim_exact_snapshot_v2.sql`、`server/simulation_snapshot_store.py`、`tests/simulation_snapshot_store_test.py`、`tests/postgres_schema_test.py`、`tests/postgres_integration_test.py` 与状态控制面文件；不得引入 job/worker/runtime consumer。
- Task 4W 只允许修改 `server/migrations/postgres/0032_websim_exact_import_jobs.sql`、`server/gear_exact_import_job_store.py`、`server/gear_exact_authority_worker.py`、`server/wow-gear-exact-authority-worker.service`、`server/deploy_lighthouse.sh`、`tests/gear_exact_import_job_store_test.py`、`tests/gear_exact_authority_worker_test.py`、`tests/postgres_schema_test.py`、`tests/postgres_integration_test.py`、数据库 runbook 与状态控制面文件。API/UI 仍不激活。
- Task 5A 和 Task 6C 在执行前必须各自补出 task-scoped allowlist、用户可见验收、candidate/rollback 和独立 review；本计划当前只给顺序和边界，不提前授权其实现。
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

Two real candidates failed before the then-current `0026` authority migration: `t3a2608050955` at `f90a302040f722fec0807bd600f8e2242169801c` because `0001` already creates `UNIQUE (user_id, template_type, config_hash)` under PostgreSQL's legacy generated name while `0003` unconditionally adds `build_templates_user_id_template_type_config_hash_key`; then `t3a260805111623` because `0003` compares catalog `name[]` attributes with a `text[]` literal. A third run, `t3a260805113656`, passed both fresh and upgrade runtime paths at commit `0e0743ca188efbd7cb818bfb8a210fd998379f4d` / tree `3fce81f57dbdc851a9438ae63ea051f666bf1051`, but its active Harness requirement status was `local_verified` instead of `implementation_allowed`. A fourth run, `t3a260805120026`, then genuinely passed both 0026 paths at commit `9ffd57b05ab97be880daf65425d6de9e26609e32`, but origin/main later occupied 0026-0029. Safe integration changed the Task 3A path, ledger, SHA and migration chain to `0030`, so the fourth run is `runtime_passed_superseded_by_main_integration`. The fifth run, `t3a260805125812`, genuinely passed the final integrated 0030 chain from clean commit `a4c0fd04b39577838ad4fb7a0e3c54b8e0205c30` / tree `aa0908eb8214d9572fc604e3399321c5d6eb3754`; its attestation and databases remain immutable historical evidence. GitHub PR #114 full-profile run `30977816268`, job `92215539827`, then exposed `GearRuntimeTest.test_runtime_imports_from_server_directory_for_direct_backend_startup` and `PgGearAuthorityLoaderTest.test_loader_imports_in_direct_server_runtime_mode`: the exact candidate source used only `server.gear_contracts` when direct server startup has no `server` package. The package-relative import plus direct-server fallback, and corresponding contract changes, invalidate fifth-run promotion. Current status is `implementation_allowed / candidate_pending`, engineering truth is `candidate_rerun_required / evidence_promotion_blocked`, and a sixth new run-id with two new databases is mandatory. All five run pairs and all ten databases are immutable evidence and must never be reset or reused; the Node deprecation warning was not the cause.

Historical status continuity: after the fourth run was superseded, Task 3A was literally `candidate_rerun_required / evidence_promotion_blocked`. The fifth clean 0030 candidate temporarily cleared that blocker, but the direct-server import regression invalidated its current promotion; those literals are again the current engineering truth until the sixth candidate passes.

The authorized `0003` correction is locally implemented and independently reviewed: it retains the legacy-name drop; conditionally creates the target unique constraint only when absent; then verifies with `pg_catalog.pg_constraint` and `pg_catalog.pg_attribute` that exactly one target constraint is on `app.build_templates`, has `contype = 'u'`, and ordered columns `user_id, template_type, config_hash`, otherwise raises an explicit exception. It does not swallow `duplicate_object`, drop/recreate an already-correct target, change `0001`, add a retro migration or reconcile ledger state. The fifth candidate used a new run-id and two newly provisioned databases, rejected all four prior run ids before connecting, and proved exactly one correct target constraint, no legacy-name constraint, exactly one `0003_build_template_config_hash_unique` ledger row and one `0030_websim_exact_authority_bundle` ledger row. Evidence promotion remains bounded to the exact attested runtime commit/tree and does not imply production activation or Task 3A delivery closure.

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
- [x] RED PostgreSQL integration uses two operator-provisioned empty disposable databases and never creates/drops a database. `WOW_PG_TEST_RUN_ID_0030` matching `^[a-z0-9]{8,32}$`, `WOW_PG_TEST_DSN_FRESH_0030`, and `WOW_PG_TEST_DSN_UPGRADE_0030` are mandatory. The suite rejects prior run ids `t3a2608050955`, `t3a260805111623`, `t3a260805113656`, `t3a260805120026`, and `t3a260805125812` before importing `psycopg` or connecting. The DSNs must identify distinct exact-commented empty databases. Fresh applies `0001..0030`; upgrade applies `0001..0029`, seeds and snapshots frozen v1 rows, then applies `0030`. Both candidates bind the final runtime-affecting commit, Git tree and 0030 SHA-256 and emit `task3a-candidate-attestation-v2`. Candidate 后只允许 evidence/manifest 与任务状态文档变化；任何 code/test/migration/requirement/owner-contract 变化都使 candidate 失效并要求重跑。The fourth and fifth runs remain immutable historical evidence and are forbidden for reuse.
- [x] Implement minimal reload/store/migration; do not add jobs or snapshot v2.
- [x] Run focused suites, full Canonical matrix, owner gate, existing v1 store/snapshot suites, Node/Harness/JSON/pycompile/diff.
- [x] Freeze both existing v1/v2 Exact keys.
- [x] Independent spec/code review is `PASS/APPROVED` with zero unresolved findings on the final Task 3A code/test state.
- [x] Fourth candidate `t3a260805120026` genuinely passed the former 0026 chain and remains immutable historical evidence, but is `runtime_passed_superseded_by_main_integration` and cannot close the integrated Task 3A.
- [x] origin/main integration, 0030 correction, local verification and independent whole-branch CR passed at merge commit `1619815c`; current evidence is `local_verified / candidate_pending`.
- [x] Fifth candidate `t3a260805125812` genuinely passed from exact clean commit `a4c0fd04` / tree `aa0908eb` using two new explicit-commented databases; its attestation-v2 and post-audit are immutable historical evidence.
- [x] PR #114 full-profile run `30977816268` / job `92215539827` identified the direct-server import regression and focused RED/GREEN correction; the Node deprecation warning is not the cause.
- [ ] Controller full local profile remains pending; current evidence stays `implementation_allowed`, not `local_verified`.
- [ ] Sixth candidate needs a new run-id and two new databases. Fifth history status is `runtime_passed_invalidated_by_direct_runtime_import_regression`; `candidate_rerun_required / evidence_promotion_blocked` remains current engineering truth.

`t3a2608050955` 与 `t3a260805111623` 已在 `0003` 前失败；`t3a260805113656` runtime passed 但 requirement gate 错误使其不可晋升；第四次 `t3a260805120026` 真实通过 former 0026 chain，但 main integration 强制迁移到 0030，故为 `runtime_passed_superseded_by_main_integration`。第五次 `t3a260805125812` 真实通过最终 0030 链，但其 exact source 被 PR #114 直接 server runtime 回归失效，故为 `runtime_passed_invalidated_by_direct_runtime_import_regression`。十座库全部 immutable/non-reusable；第六次新 run-id/双库 mandatory，且 no production migration/runtime consumer。

2026-08-05 首轮独立实现 review 返回 `CHANGES_REQUIRED`；相关 findings 已完成 RED/GREEN correction，第四次真实双 PostgreSQL candidate 与当时 Harness packet 也确曾通过。随后 origin/main migration 漂移使 packet 失效；0030 集成修正与第五次 candidate 也曾通过。PR #114 后发现 direct-server import regression，故第五次不能继续作为当前验证或 promotion；当前只恢复诚实的 `implementation_allowed / candidate_pending` packet，controller 的 full local profile 与第六次 candidate 仍 pending。`implementation_allowed` 不等于 production/live/release-ready。

---

## Task 4P: Pure v2 Resolver / Loadout / Snapshot

This task executes the old Task 5 pure-domain intent before any v2 store changes.

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
