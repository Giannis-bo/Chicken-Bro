# 装备模拟 Exact-first 持久化与运行链重排计划

> **For agentic workers:** REQUIRED SUB-SKILLS: Use `superpowers:subagent-driven-development`, `superpowers:test-driven-development`, and `superpowers:verification-before-completion`. This plan forward-replaces the old implementation plan's Task 3 and later execution order after two independent readiness audits returned `NOT_READY`.

状态：`正在纠正（readiness audit FAIL；计划待独立 review；旧 Task 3 未启动）`

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

1. **Task 3A:** Canonical authority bundle rehydration + append-only persistence (`0026`)，无 runtime consumer。
2. **Task 4P:** 提前完成纯函数 v2 Resolver、ResolvedLoadout、SimulationSnapshot（替代旧 Task 5 的 pure domain 部分），无 DB/runtime。
3. **Task 3B:** v1/v2 conditional loadout/snapshot persistence (`0027`)，只消费 Task 4P 的 verifier。
4. **Task 4W:** owner-scoped jobs、独立 worker DB role、lease/retention/metrics 与 worker service (`0028`)。
5. **Task 5A:** Exact import API、正式 SimC submit 接合与 UI typed contract。
6. **Task 6C:** observation/candidate/admission 从 `0029` 开始，保持独立 candidate/release gate。

---

## Task 3A: 完整 Canonical Authority Bundle 持久化

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

- Create: `server/migrations/postgres/0026_websim_exact_authority_bundle.sql`
- Create: `server/gear_exact_authority_store.py`
- Create: `tests/gear_exact_authority_store_test.py`
- Modify: `tests/postgres_schema_test.py`
- Modify: `tests/postgres_integration_test.py`

**Source change-control and control plane**

- Modify: `tests/fixtures/gear_canonical_owner_registry.json`
- Modify: `tests/gear_canonical_owner_gate_test.py`
- Modify: `artifacts/releases/2026-08-04-equipment-simulator-exact-first/requirement.json`
- Modify: `docs/project-owner-map.json`
- Modify: `docs/backend-owner-map.json`
- Modify: this plan only for checklist/status

Task 3A must not modify `simulation_snapshot_store.py`, `postgres_cache_store.py`, jobs, worker, API, Resolver, loadout/snapshot domain schemas, deployment, Catalog or runtime.

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
- Store code imports only those typed domain reload functions. It must not import private validators, parse/normalize domain fields, instantiate sealed documents, or invent a second serializer.

Each reload function receives stored canonical bytes/key, rebuilds the sealed domain document, and rejects any bytes/key/schema/binding drift. No `strip`, coercion, normalization, JSONB round-trip or Catalog lookup is allowed.

### PostgreSQL schema

`0026` is rechecked as free immediately before creation and creates only three append-only cache tables.

#### `cache.websim_canonical_documents`

- `content_key text PRIMARY KEY`
- `document_kind text NOT NULL`
- `schema_revision text NOT NULL`
- `canonical_bytes bytea NOT NULL CHECK (octet_length(canonical_bytes) BETWEEN 2 AND 1048576)`
- `canonical_json jsonb NOT NULL CHECK (jsonb_typeof(canonical_json) = 'object')` as a query/constraint projection only
- `canonical_sha256 text NOT NULL CHECK (canonical_sha256 ~ '^[0-9a-f]{64}$')`
- `sealed_at timestamptz NOT NULL DEFAULT clock_timestamp()`
- `right(content_key, 64) = canonical_sha256`
- a closed kind/schema/prefix matrix for exactly:
  - `exact_item` / `gear-exact-item-instance-v2` / `exact-item-instance:sha256:`
  - `exact_static_facts` / `exact-static-facts-v1` / `exact-static-facts:sha256:`
  - `exact_progression` / `exact-progression-binding-v1` / `exact-progression:sha256:`
  - `effect_record` / `simc-item-effect-record-v1` / `simc-item-effect-record:sha256:`
  - `effect_aggregate` / `simc-item-effect-support-v1` / `simc-item-effect-support:sha256:`
  - `exact_authority` / `exact-authority-envelope-v1` / `exact-authority:sha256:`

`canonical_bytes` is the identity source. `canonical_json` must equal the decoded JSON value but never generates the key and never replaces byte verification.

#### `cache.websim_effect_aggregate_records`

- `(effect_support_key, ordinal)` primary key;
- `effect_record_key` foreign key to canonical documents;
- ordinal bounded `0..127`;
- repeated `effect_record_key` at different ordinals is allowed;
- insert-time trigger verifies aggregate/record document kinds. Application reload verifies exact ordered equality with aggregate `supportRecords`.

#### `cache.websim_exact_authority_bundles`

- `exact_authority_envelope_key` primary/foreign key;
- foreign keys for `exact_item_instance_key`, `static_facts_key`, `progression_binding_key`, `effect_support_key`;
- derived query projections: `gear_rule_revision`, `simc_runtime_revision`, `resolver_revision`;
- insert-time trigger verifies all component kinds and exact JSON key bindings, including envelope keys and projection equality;
- no owner, Catalog membership or provenance fields.

All three tables receive immutable triggers. Explicitly `REVOKE INSERT, UPDATE, DELETE, TRUNCATE FROM wow_app` and grant only `SELECT` in 0026. Task 3A has no runtime writer; Task 4W later grants an independent worker role. Migration/migrator and tests may write during candidate verification.

### Store contract

`GearExactAuthorityStore` provides no “latest” lookup and no partial-success authority:

- `seal_authority_bundle(exact, static_facts, progression, effect_support, envelope, effect_records)`
- `load_verified_bundle(envelope_key)`
- `load_verified_bundles(exact_keys, *, gear_rule_revision, simc_runtime_revision, resolver_revision)`
- `load_effect_records(record_keys, *, simc_runtime_revision)`

Write path:

1. reverify every live sealed document through the typed reload path;
2. require envelope/component keys and ordered aggregate record keys to match exactly;
3. insert the entire closure in one transaction;
4. use insert-if-absent then exact readback comparison; identical writes are idempotent, same key/different bytes or projections are integrity errors;
5. never accept raw dicts or individual unbound documents as a successful bundle.

Read path loads exact canonical bytes, reconstructs Exact -> Static/Progression -> ordered Effect Records -> Effect Aggregate -> Envelope, and returns only a fully reverified immutable bundle. Any missing row, wrong kind/schema/key/runtime/rule/resolver, reordered duplicate record or byte drift fails closed.

### TDD and verification

- [ ] Preflight `0026` is absent; stop on collision.
- [ ] RED Kernel/domain reload: exact bytes/key pass; whitespace, duplicate key, non-NFC, over-bound, wrong kind/schema/prefix/key and cross-document binding fail.
- [ ] RED store: full bundle round-trip, identical idempotency, collision, missing component, wrong runtime/rule/resolver, duplicate effect-record ordinal, repeated same record at two ordinals, reordered non-adjacent duplicate, tampered canonical bytes/JSON projection and partial transaction rollback.
- [ ] RED SQL/static: exact kind/schema/prefix matrix, component FKs/binding trigger, immutable triggers, wow_app SELECT-only and unique migration identity.
- [ ] RED PostgreSQL integration: apply `0001..0026` fresh and `0025 -> 0026` with existing v1 rows; verify v1 rows/row hashes unchanged, bytea/JSON equality, trigger/grant behavior and bundle transaction.
- [ ] Implement minimal reload/store/migration; do not add jobs or snapshot v2.
- [ ] Run focused suites, full Canonical matrix, owner gate, existing v1 store/snapshot suites, Node/Harness/JSON/pycompile/diff.
- [ ] Freeze both existing v1/v2 Exact keys.
- [ ] Independent spec/code review must be `PASS/APPROVED`.
- [ ] Candidate PostgreSQL evidence is mandatory before Task 3A is `已完成`. If `WOW_PG_TEST_DSN`/`psql` is unavailable locally, report local implementation separately as `candidate_pending`; do not package skipped integration as green.

---

## Task 4P: Pure v2 Resolver / Loadout / Snapshot

This task executes the old Task 5 pure-domain intent before any v2 store changes.

- Add v2 builders/verifiers in Resolver, ResolvedLoadout, SimulationSnapshot and compatibility modules.
- Exact Authority Envelope and loadout-level effect records use the frozen prefixes:
  - `exact-authority:sha256:`
  - `simc-item-effect-record:sha256:`
- v2 identity binds exact envelope keys, Rule/Resolver/compiler/SimC runtime revisions and complete loadout-level verified effect records; it never binds Catalog membership or provenance.
- `originCatalogRevision` stays outside canonical payload/hash.
- v1 builder/verifier remains a separate strict branch and all historical bytes/key stay unchanged.
- No DB, job, worker, API, UI or deployment changes.

Task 4P requires a separately reviewed implementation slice before Task 3B.

## Task 3B: v1/v2 conditional snapshot persistence (`0027`)

Only after Task 4P exists:

- alter loadout/snapshot tables with schema-conditioned Catalog/registry/envelope-key checks;
- add exact authority envelope keys as non-empty, unique, canonical-order JSON arrays for v2 and exact `[]` for v1;
- keep `originCatalogRevision` in separate provenance columns/wrappers, outside stored canonical documents and row hashes;
- reuse Task 4P verifiers in `SimulationSnapshotStore`; no duplicated v2 validator;
- preserve every historical v1 row/key/hash and append-only trigger;
- require fresh and 0026->0027 real PostgreSQL migration evidence.

## Task 4W: Owner-scoped jobs and worker (`0028`)

Task 4W must first establish `wow_exact_worker` as a distinct database principal and separate DSN/config. Before runtime activation:

- revoke authority INSERT and all job/metrics table writes from `wow_app`;
- grant worker only SELECT/INSERT on authority documents, claim/heartbeat/terminal functions, worker state and bounded prune execution;
- app may only owner-scope enqueue/read through explicit functions or narrowly granted operations;
- prune functions are `SECURITY DEFINER`, fixed `search_path`, fully qualified, `REVOKE ALL FROM PUBLIC`, with no bottom-table DELETE grants to app or worker.

Job schema includes `started_at`, `finished_at`, `cooldown_until`; terminal retention is `finished_at + 7 days`, metrics retention is 90 days. All time and lease decisions use PostgreSQL `clock_timestamp()`.

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

## Stop Gate

Stop and redesign if any task requires:

- translating current canonical keys into legacy aliases;
- storing JSONB without exact canonical bytes;
- accepting dangling or partially verified authority documents;
- adding v2 store validation before the v2 domain verifier exists;
- using `wow_app` as both public API and privileged authority worker at activation;
- application-provided lease/retention time;
- changing generation 35, Catalog/Manifest pointers, v1 bytes/key or runtime before its task-scoped review.

