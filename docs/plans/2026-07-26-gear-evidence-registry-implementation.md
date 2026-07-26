# Gear Evidence Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将装备静态事实（精确变体、静态属性、宝石槽、附魔、美化、套装与静态 option 适用性）收敛为一套由 Evidence Registry 和唯一 Fact Compiler 产生、并由现有 Gear Release 发布的 Canonical Facts；消除同一事实在 catalog、payload、Resolver 和 Taro 中被独立维护的情况。

**Architecture:** Source collector 只提交不可变 Artifact；版本化 parser 从 Artifact 产生 Observation；纯 Fact Compiler 按 `factType` policy 产生 `verified` / `unresolved_missing` / `unresolved_conflict` Canonical Fact。现有 immutable Gear Release 封存发布事实，Authority Loader、Resolver、browse serializer、health 和 Taro 只消费该发布版本。Evidence Gap Queue 是受围栏保护的自动追溯队列，不能直接写事实或切换 Manifest。

**Tech Stack:** Python 3、PostgreSQL、现有 Gear Release / Active Season Manifest、SimulationCraft probe、Battle.net season cache、Taro/TypeScript、Node test runner、Harness Strict candidate deployment。

## Global Constraints

- Harness classification is **Strict**. 任何可用户见的 runtime 改动均先走 candidate Gear Release 与 candidate deployment；只有显式用户验收才可切换 active Manifest。
- 不新增 Fact Release、第二个 Manifest 或第二个 active pointer；复用 `server/gear_release_store.py` 的 release、candidate、CAS 与 rollback。
- Artifact、Observation、Fact 都是 append-only；修正通过新 revision、supersede 或 invalidation 表达，不能更新原 payload 或删除历史。
- Compiler 必须纯函数：不得读取网络、当前时间、前端 state、active Manifest 或 mutable staging 以外的输入。相同输入、parser revision 与 policy revision 必须产生相同 Fact/Release 内容 hash。
- `verified + false/0` 表示确认不支持；缺证据和冲突只能分别为 `unresolved_missing`、`unresolved_conflict`。消费者不得以缺字段推断 `false/0`。
- Resolver 保留动态选择合法性（容量使用、unique gem、spec、双持、全局美化限制）；Fact Compiler 只负责静态事实和静态 option 适用性。
- 兼容字段可短期保留，但只能由 Canonical Fact serializer 单向投影；`hasSocket`、`canEnchant`、`canEmbellish` 不得再作为独立 truth。
- Evidence Gap Worker 只能写入 Artifact/Observation，并要求重编译 candidate Release；它不能直接写 `verified`、改 compiler policy、改代码或改 active Manifest。
- 发布前必须先完成 old/new shadow 对账；每项差异只能分类为 `exact_parity`、`intended_correction`、`newly_exposed_gap` 或 `regression`。`regression` 阻止 candidate 晋升。
- 不把 root code、Artifact、Observation、hash、worker 状态或“申请核验”暴露给玩家。用户只看“可用 / 不可用 / 待核验”。

---

## Task 1: Freeze the canonical fact contract with executable characterization tests

**Files:**

- Create: `tests/gear_evidence_registry_test.py`
- Create: `server/gear_evidence_registry.py`
- Modify: `docs/plans/2026-07-26-gear-evidence-registry-design.md`

- [ ] **Step 1: Add failing contract tests for identity, hash separation, and three-state facts**

  Cover `item:250033/variant:void_upgrade-298` and assert that:

  - `factKey` binds only `seasonRevision + subjectKey + factType`;
  - a value/provenance change does not change that key;
  - `factValueHash` changes for a `1 -> 0` or `verified -> unresolved_missing` change;
  - `provenanceHash` changes only for the selected Observation set/policy revision;
  - `verified, value=0` and `verified, value=false` remain verified;
  - `unresolved_missing` and `unresolved_conflict` cannot carry a trusted default value;
  - Artifact identity is idempotent by source identity/revision/season/payload hash and rejects secret-shaped keys recursively.

- [ ] **Step 2: Run the focused test and verify it fails because the contract owner does not exist**

  Run: `python -m unittest tests.gear_evidence_registry_test`

  Expected: import or missing-symbol failure, not a skipped test.

- [ ] **Step 3: Implement the pure contract owner**

  In `server/gear_evidence_registry.py`, add canonical JSON/hash helpers plus public constructors/validators:

  - `build_evidence_artifact(...)`
  - `build_evidence_observation(...)`
  - `build_canonical_fact(...)`
  - `canonical_fact_key(...)`
  - `fact_value_hash(...)`
  - `provenance_hash(...)`

  Require schema revisions `gear-evidence-artifact-v1`, `gear-evidence-observation-v1`, and `gear-canonical-fact-v1`; accept only the three approved fact statuses. Keep all returned mappings JSON-canonical and immutable by convention.

- [ ] **Step 4: Re-run the focused contract suite**

  Run: `python -m unittest tests.gear_evidence_registry_test`

  Expected: pass, including deterministic repeated construction.

- [ ] **Step 5: Record the implementation names in the approved design without changing its semantics**

  Add a short implementation-anchor paragraph to the design that names the module and hash contracts; do not change approved product behavior.

- [ ] **Step 6: Commit the isolated contract slice**

  ```powershell
  git add server/gear_evidence_registry.py tests/gear_evidence_registry_test.py docs/plans/2026-07-26-gear-evidence-registry-design.md
  git commit -m "feat(gear): add canonical evidence fact contracts"
  ```

## Task 2: Add the append-only PostgreSQL registry and fenced Evidence Gap queue

**Files:**

- Create: `server/migrations/postgres/0019_gear_evidence_registry.sql`
- Create: `server/gear_evidence_store.py`
- Create: `server/gear_evidence_gap_store.py`
- Create: `tests/gear_evidence_store_test.py`
- Modify: `tests/postgres_schema_test.py`
- Modify: `docs/database-architecture.md`

- [ ] **Step 1: Add failing store/schema tests**

  Test duplicate Artifact/Observation insertion reuses the original immutable row; assert Observation cannot reference a missing Artifact; assert Facts are versioned append-only by `(fact_key, fact_value_hash, provenance_hash)`; assert a Gap is idempotent by `gap_key` and fenced by `lock_token`; assert runtime role grants no `UPDATE`/`DELETE` to Artifact, Observation, or Fact rows.

- [ ] **Step 2: Run the focused tests to establish failure**

  Run: `python -m unittest tests.gear_evidence_store_test tests.postgres_schema_test`

  Expected: missing migration/store behavior.

- [ ] **Step 3: Add migration `0019_gear_evidence_registry`**

  Create `cache.websim_gear_evidence_artifacts`, `cache.websim_gear_evidence_observations`, `cache.websim_gear_canonical_facts`, `cache.websim_gear_evidence_invalidations`, and `ops.websim_gear_evidence_gaps`.

  Enforce canonical identities, JSONB payloads, artifact/observation foreign keys, append-only permissions, and indexes for `(season_revision, subject_key, fact_type)`. Make the queue operational only: `status`, `attempt`, `locked_by`, `lock_token`, `lease_until`, `next_attempt_at`, `problem_code`, and structured `missing_requirement_json`; do not put Fact values in queue result fields. Register the migration in `ops.schema_migrations` and update `docs/database-architecture.md`.

- [ ] **Step 4: Implement the two SQL owners**

  `GearEvidenceStore` owns only Artifact, Observation, invalidation, and Fact persistence/query methods. `GearEvidenceGapStore` owns only `enqueue_gaps`, `claim_next`, `finish`, and `health_summary`, copying the lease/CAS discipline of `AttributeRuleAuditStore` but using the approved Gear gap statuses and root codes.

- [ ] **Step 5: Re-run focused storage and schema tests**

  Run: `python -m unittest tests.gear_evidence_store_test tests.postgres_schema_test`

  Expected: all storage invariants and role assertions pass.

- [ ] **Step 6: Commit the registry persistence slice**

  ```powershell
  git add server/migrations/postgres/0019_gear_evidence_registry.sql server/gear_evidence_store.py server/gear_evidence_gap_store.py tests/gear_evidence_store_test.py tests/postgres_schema_test.py docs/database-architecture.md
  git commit -m "feat(gear): persist immutable evidence registry"
  ```

## Task 3: Implement versioned parsers and the declarative Fact Compiler

**Files:**

- Create: `server/gear_evidence_observers.py`
- Create: `server/gear_fact_compiler.py`
- Create: `tests/gear_evidence_observers_test.py`
- Create: `tests/gear_fact_compiler_test.py`
- Modify: `server/gear_socket_authority.py`
- Modify: `server/gear_rule_matrix.py`

- [ ] **Step 1: Write failing observer tests**

  Cover parser replay from a stored Battle.net item Artifact, SimC exact-item/bonus probe Artifact, and season-rule Artifact. Assert parser revisions become part of Observation identity; a malformed source becomes a structured parser result rather than a default Observation; no observer reads the clock or network.

- [ ] **Step 2: Write failing compiler-policy tests**

  Use small fixtures to cover each first-stage policy: `item_identity`, `slot_compatibility`, `variant_track`, `static_stats`, `socket_count`, `enchant_capability`, `embellishment_capability`, `enhancement_option`, `allowed_enhancement_options`, `item_set_membership`.

  Explicitly test `socket_count=1` for `250033/void_upgrade-298`, verified zero sockets, absence-not-zero, conflicting exact observations, policy revision invalidation, and byte-for-byte deterministic recompilation.

- [ ] **Step 3: Run the focused observer/compiler tests and verify failure**

  Run: `python -m unittest tests.gear_evidence_observers_test tests.gear_fact_compiler_test`

- [ ] **Step 4: Implement observers and compiler**

  In `server/gear_evidence_observers.py`, expose deterministic `observe_*` functions returning accepted observations or structured non-observation diagnostics. In `server/gear_fact_compiler.py`, expose `FACT_POLICIES`, `compile_facts(...)`, `compile_subject_facts(...)`, and `evidence_gaps_from_facts(...)`.

  Every policy declares allowed sources, source scope, combination mode, closed-world condition for false/zero, conflict policy, impact scope, and rule revision. Adapt `gear_socket_authority.py` to emit source observations/input facts only; remove its authority to decide the final consumer payload. Keep dynamic legality in `gear_rule_matrix.py` untouched except for accepting canonical static inputs.

- [ ] **Step 5: Re-run focused tests and ensure the legacy socket fixture still passes**

  Run: `python -m unittest tests.gear_evidence_observers_test tests.gear_fact_compiler_test tests.gear_socket_authority_test tests.gear_rule_matrix_test`

  Expected: the exact `250033` conflict is represented as one verified compiled socket fact, not two competing source booleans.

- [ ] **Step 6: Commit the pure compilation slice**

  ```powershell
  git add server/gear_evidence_observers.py server/gear_fact_compiler.py server/gear_socket_authority.py server/gear_rule_matrix.py tests/gear_evidence_observers_test.py tests/gear_fact_compiler_test.py
  git commit -m "feat(gear): compile canonical static facts"
  ```

## Task 4: Seal compiled facts into existing Gear Releases with shadow comparison

**Files:**

- Modify: `server/gear_release_tool.py`
- Modify: `server/gear_release_refresh.py`
- Modify: `server/gear_release_store.py`
- Create: `server/gear_fact_shadow.py`
- Create: `tests/gear_fact_shadow_test.py`
- Modify: `tests/gear_release_tool_test.py`
- Modify: `tests/gear_release_refresh_test.py`

- [ ] **Step 1: Add failing release tests**

  Assert a prepared snapshot materializes `canonicalFacts` and bounded fact/provenance references in item, variant, and option payloads without copying raw Artifact payloads. Assert source evidence includes a deterministic compiler policy/fact digest. Assert a no-op recompilation creates neither a new content hash nor a new candidate release.

- [ ] **Step 2: Add failing shadow-classification tests**

  `compare_legacy_and_canonical(...)` must classify every difference exclusively as `exact_parity`, `intended_correction`, `newly_exposed_gap`, or `regression`; unclassified differences must fail release preparation. Include the known browse/Resolve `250033` `hasSocket=false` vs `socketCount=1` case as `intended_correction`.

- [ ] **Step 3: Run the release/shadow tests to establish failure**

  Run: `python -m unittest tests.gear_release_tool_test tests.gear_release_refresh_test tests.gear_fact_shadow_test`

- [ ] **Step 4: Integrate the compiler into the sole release-preparation path**

  Replace the direct terminal authority of `_project_socket_facts_into_release_payloads(...)` and `_materialize_enhancement_management(...)` with an adapter that:

  1. imports accepted legacy source records into Artifact/Observation form;
  2. compiles Facts using the declared policy revision;
  3. projects only release-safe fact values/statuses/references into the immutable snapshot;
  4. enqueues unresolved Facts idempotently; and
  5. runs shadow classification before `seal_gear_release`.

  Preserve current Gear Release integrity checks, parent release behavior, and candidate-first publication. Do not alter active Manifest selection here.

- [ ] **Step 5: Re-run release tests**

  Run: `python -m unittest tests.gear_release_tool_test tests.gear_release_refresh_test tests.gear_fact_shadow_test`

  Expected: a repeat preparation with unchanged inputs is a no-op and regressions block a candidate.

- [ ] **Step 6: Commit the release integration slice**

  ```powershell
  git add server/gear_release_tool.py server/gear_release_refresh.py server/gear_release_store.py server/gear_fact_shadow.py tests/gear_release_tool_test.py tests/gear_release_refresh_test.py tests/gear_fact_shadow_test.py
  git commit -m "feat(gear): seal canonical facts in gear releases"
  ```

## Task 5: Move Authority Loader, Resolver, and API projection to released facts

**Files:**

- Modify: `server/pg_gear_authority_loader.py`
- Modify: `server/gear_resolver.py`
- Modify: `server/gear_evidence_ledger.py`
- Modify: `server/websim_payload.py`
- Modify: `tests/pg_gear_authority_loader_test.py`
- Modify: `tests/gear_resolver_test.py`
- Modify: `tests/websim_payload_test.py`
- Modify: `docs/design/current-ui/routes/gear-detail/truth-adaptation.json`

- [ ] **Step 1: Write failing loader/resolver tests**

  Assert loader reads Canonical Facts only from the selected Gear Release and rejects mutable staging/source payload as a fallback. Assert Resolver projects fact refs into the existing evidence ledger as a Resolution Proof, while dynamic selection checks continue to run separately.

- [ ] **Step 2: Write failing public-contract tests**

  Assert a browse payload and exact Resolve result report the same canonical capability state for the same item/variant. Test `250033/void_upgrade-298` as one socket; test verified zero as unavailable; test unresolved capability as `pending` and disabled only in that category.

- [ ] **Step 3: Run focused loader/resolver/serializer tests to establish failure**

  Run: `python -m unittest tests.pg_gear_authority_loader_test tests.gear_resolver_test tests.websim_payload_test`

- [ ] **Step 4: Implement the one-way consumer projection**

  `pg_gear_authority_loader.py` reads `canonicalFacts` as the sole static authority. `gear_resolver.py` consumes those facts and attaches fact references to `gear-evidence-ledger-v1` without recomputing source truth. `websim_payload.py` emits capability views with state/value/options derived solely from released facts. If legacy booleans remain, derive them only in this serializer from verified capability facts.

- [ ] **Step 5: Update the route truth contract and re-run focused tests**

  Document that compact browse and exact Resolve share the same published fact projection; keep all internal provenance out of the public route contract.

  Run: `python -m unittest tests.pg_gear_authority_loader_test tests.gear_resolver_test tests.websim_payload_test`

- [ ] **Step 6: Commit the consumer authority slice**

  ```powershell
  git add server/pg_gear_authority_loader.py server/gear_resolver.py server/gear_evidence_ledger.py server/websim_payload.py tests/pg_gear_authority_loader_test.py tests/gear_resolver_test.py tests/websim_payload_test.py docs/design/current-ui/routes/gear-detail/truth-adaptation.json
  git commit -m "feat(gear): consume released canonical facts"
  ```

## Task 6: Make Taro render verified, unavailable, and pending capabilities consistently

**Files:**

- Modify: `packages/domain/src/entities.ts`
- Modify: `apps/mini-taro/src/pages/builds/gear-detail-model.ts`
- Modify: `apps/mini-taro/src/pages/builds/detail.tsx`
- Modify: `apps/mini-taro/src/pages/builds/gear-detail-model.test.ts`
- Modify: `apps/mini-taro/src/pages/builds/detail.test.tsx`

- [ ] **Step 1: Add failing model tests for the three visible states**

  Verify: (1) socket count one is selectable even if a legacy `hasSocket=false` field appears; (2) verified `socket_count=0` is displayed as “不可用”; (3) unresolved socket/enchant/embellishment shows only that category as “待核验” and disables its controls; (4) verified categories remain usable; (5) artifact, hash, root code, and worker status never become UI text.

- [ ] **Step 2: Run the focused Taro tests and verify failure**

  Run:

  ```powershell
  & 'C:\Users\blizz\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' --test apps/mini-taro/src/pages/builds/gear-detail-model.test.ts apps/mini-taro/src/pages/builds/detail.test.tsx
  ```

- [ ] **Step 3: Add typed public capability views and remove independent boolean interpretation**

  Define `GearCapabilityFactView` in `packages/domain/src/entities.ts` with `status`, `value`, and safe option references. In `gear-detail-model.ts`, make `gearEnhancementSocketCount` consume the canonical state/value first and treat legacy boolean fields only as serializer compatibility output, never as a precedence rule. Update `detail.tsx` to show the approved three labels without a diagnostic affordance.

- [ ] **Step 4: Re-run targeted Taro tests**

  Run the same bundled-Node command.

  Expected: item `250033`, variant `void_upgrade-298`, reaches the gem selector with one slot.

- [ ] **Step 5: Commit the UI consumer slice**

  ```powershell
  git add packages/domain/src/entities.ts apps/mini-taro/src/pages/builds/gear-detail-model.ts apps/mini-taro/src/pages/builds/detail.tsx apps/mini-taro/src/pages/builds/gear-detail-model.test.ts apps/mini-taro/src/pages/builds/detail.test.tsx
  git commit -m "fix(gear): render canonical enhancement states"
  ```

## Task 7: Close unresolved-fact automation through a bounded internal worker and health

**Files:**

- Create: `server/gear_evidence_gap_worker.py`
- Create: `tests/gear_evidence_gap_worker_test.py`
- Create: `server/wow-gear-evidence-gap-worker.service`
- Modify: `server/news_backend.py`
- Modify: `server/data_health_followup.py`
- Modify: `tests/news_backend_test.py`
- Modify: `tests/data_health_followup_test.py`
- Modify: `scripts/deploy-vps.sh`

- [ ] **Step 1: Write failing worker and health tests**

  Assert claim/retry/lease loss/terminal behavior. Assert a worker only invokes approved collectors/parsers and requests candidate recompilation; it cannot update a Fact, call Manifest activation, or overwrite conflict state. Assert `/api/data/health` exposes aggregate queue state/revision only and `data_health_followup.py` triggers the service only for a changed explicit queue revision.

- [ ] **Step 2: Run focused worker/health tests to establish failure**

  Run: `python -m unittest tests.gear_evidence_gap_worker_test tests.news_backend_test tests.data_health_followup_test`

- [ ] **Step 3: Implement the bounded worker and operational health component**

  Add `run_gear_evidence_gap_worker(...)` with a fixed maximum job count, lease fencing, idempotent collector inputs, and structured outcomes. Add `gear_evidence_gap_health_component(...)` in `news_backend.py`. Add the `gear_evidence_gap_worker` systemd action to `data_health_followup.py`, gated by queue input revision rather than human-readable blockers. Install a oneshot service through `scripts/deploy-vps.sh`; the existing health-followup timer remains the scheduler.

- [ ] **Step 4: Re-run worker/health tests**

  Run: `python -m unittest tests.gear_evidence_gap_worker_test tests.news_backend_test tests.data_health_followup_test`

- [ ] **Step 5: Commit the automatic-closure slice**

  ```powershell
  git add server/gear_evidence_gap_worker.py server/wow-gear-evidence-gap-worker.service server/news_backend.py server/data_health_followup.py scripts/deploy-vps.sh tests/gear_evidence_gap_worker_test.py tests/news_backend_test.py tests/data_health_followup_test.py
  git commit -m "feat(gear): automate evidence gap recovery"
  ```

## Task 8: Candidate rollout, active cutover, and legacy authority removal

**Files:**

- Create: `docs/runbooks/gear-evidence-registry-cutover.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/roadmap/ideas.md`
- Modify: `docs/plans/README.md`
- Modify: `docs/project-owner-map.json`
- Modify: `docs/backend-owner-map.json`
- Modify: legacy modules named by caller-proof search in `server/gear_socket_authority.py`, `server/gear_release_tool.py`, `server/pg_gear_authority_loader.py`, `server/websim_payload.py`, and `apps/mini-taro/src/pages/builds/gear-detail-model.ts`

- [ ] **Step 1: Add failing end-to-end characterization tests**

  Build a candidate snapshot with the canonical compiler and assert: no partial/needs-variant duplicate leaks as an exact selection; browse/Resolve/Taro agree for 250033; a missing capability affects only its own controls; and no-op refresh leaves the active/candidate release identity unchanged.

- [ ] **Step 2: Run the scoped backend and frontend suite before cutover changes**

  Run:

  ```powershell
  python -m unittest tests.gear_evidence_registry_test tests.gear_evidence_store_test tests.gear_evidence_observers_test tests.gear_fact_compiler_test tests.gear_fact_shadow_test tests.gear_release_tool_test tests.gear_release_refresh_test tests.pg_gear_authority_loader_test tests.gear_resolver_test tests.websim_payload_test tests.gear_evidence_gap_worker_test
  & 'C:\Users\blizz\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' --test apps/mini-taro/src/pages/builds/gear-detail-model.test.ts apps/mini-taro/src/pages/builds/detail.test.tsx
  ```

- [ ] **Step 3: Write the candidate deployment and rollback runbook**

  Document exact sequence: schema migration backup/check, Artifact import, Observation replay, shadow report review, candidate Gear Release identity, candidate deploy parity, health/API/Resolve smoke, Taro route manual acceptance, explicit active Manifest CAS, and rollback to the previous existing Manifest revision. State that registry rows survive rollback and no active pointer changes without explicit user authorization.

- [ ] **Step 4: Execute candidate-only deployment verification**

  Deploy the branch/commit to the approved candidate path with `WOW_DEPLOY_START_ASYNC_SYNCS=0`; record release/manifest identities, runtime file parity, health component state, worker state, exact API payloads, and the fallback Manifest revision. Do not merge or activate production here.

- [ ] **Step 5: Obtain explicit user acceptance for the real Taro route and active cutover**

  Manual acceptance must verify the equipment-detail route shows one gem slot for `250033/void_upgrade-298`, shows “不可用” for confirmed unsupported capability, and shows “待核验” only for unresolved categories. Until this acceptance, retain old active Manifest and classify the work as candidate-verified only.

- [ ] **Step 6: Cut over atomically and prove rollback remains available**

  On explicit acceptance only, activate the candidate through the existing Manifest CAS, run fresh API/Resolve/Taro smoke, and prove previous Manifest rollback. Then remove compatibility writers/readers found by caller-proof search so no `hasSocket` or enhancement capability truth remains outside Canonical Fact projection.

- [ ] **Step 7: Run final Harness verification and commit documentation/caller-proof cleanup**

  Run:

  ```powershell
  git diff --check
  python -m unittest tests.gear_evidence_registry_test tests.gear_evidence_store_test tests.gear_evidence_observers_test tests.gear_fact_compiler_test tests.gear_fact_shadow_test tests.gear_release_tool_test tests.gear_release_refresh_test tests.pg_gear_authority_loader_test tests.gear_resolver_test tests.websim_payload_test tests.gear_evidence_gap_worker_test
  & 'C:\Users\blizz\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' --test apps/mini-taro/src/pages/builds/gear-detail-model.test.ts apps/mini-taro/src/pages/builds/detail.test.tsx
  & 'C:\Users\blizz\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' scripts/audit-ui-architecture.js
  ```

  Commit only after every scoped test and candidate evidence succeeds. Update the roadmap state and the linked idea with evidence paths rather than placing an execution timeline in `docs/roadmap.md`.

## Harness Completion Criteria

1. One exact published Fact is the sole authority for each released static gear fact, and its fact/provenance identity is deterministic.
2. Browse, exact Resolve, and Taro agree for the same item/variant. The known `250033/void_upgrade-298` case yields `socket_count=1` end-to-end.
3. Confirmed false/zero is unavailable; missing/conflicting evidence is pending and category-scoped; no technical evidence detail is shown to players.
4. Resolver dynamic legality still rejects illegal selections without inventing static facts.
5. Artifact/Observation/Fact are append-only, queue work is fenced, and the worker cannot directly change facts or active publication.
6. Unchanged artifacts/parser/policy produce a no-op release refresh.
7. Candidate deployment, candidate Gear Release, API/Resolve smoke, health, bounded worker state, manual Taro acceptance, active Manifest CAS, and rollback proof are recorded as fresh evidence.
8. Caller-proof search after cutover shows no remaining independent writer/reader of socket/enchant/embellishment truth.

