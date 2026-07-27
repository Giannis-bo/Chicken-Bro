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

## Delivery Checkpoints

2026-07-26 用户确认把原先单次全量实施拆成四个可独立评审和交付的阶段，避免把事实底座、运行时消费、后台自动化与零售切换放进一个巨型合入：

1. **Foundation / shadow（Tasks 1–4）：** Registry、Observation、Fact Compiler、现有 Gear Release 封存与 shadow；不得改变活动运行时消费或 Manifest。
2. **Consumer cutover（Tasks 5–6）：** Authority Loader、Resolver、API 与 Taro 统一消费 released facts。Task 5 必须先完成 targeted GREEN、独立复审和本地 CR，提交并推送远端任务分支、核对本地/远端 SHA，形成可跨电脑恢复的受跟踪检查点后停止；不得自动进入 Task 6。
3. **Automatic closure（Task 7）：** Evidence Gap Worker 与 health 单独评审和交付；不得与用户可见消费切换共用一个未审查的运行时切片。
4. **Candidate and retail closure（Task 8）：** 候选部署、真实 Taro 验收、显式 Manifest CAS、回滚证明与最终 Harness 收口。

每一阶段必须能独立验证、独立拒绝或回滚，并拥有自己的 task-scoped Harness 证据。不得用一个 PR、一个 release packet 或一个 candidate window 覆盖四个阶段。现有提交可以通过后续分支/提交边界重组，但不得重写 `origin/main`、丢弃已完成工作或越过显式用户验收。

---

## Task 1: Freeze the canonical fact contract with executable characterization tests

**Files:**

- Create: `tests/gear_evidence_registry_test.py`
- Create: `server/gear_evidence_registry.py`
- Modify: `docs/plans/2026-07-26-gear-evidence-registry-design.md`

- [x] **Step 1: Add failing contract tests for identity, hash separation, and three-state facts**

  Cover `item:250033/variant:void_upgrade-298` and assert that:

  - `factKey` binds only `seasonRevision + subjectKey + factType`;
  - a value/provenance change does not change that key;
  - `factValueHash` changes for a `1 -> 0` or `verified -> unresolved_missing` change;
  - `provenanceHash` changes only for the selected Observation set/policy revision;
  - `verified, value=0` and `verified, value=false` remain verified;
  - `unresolved_missing` and `unresolved_conflict` cannot carry a trusted default value;
  - Artifact identity is idempotent by source identity/revision/season/payload hash and rejects secret-shaped keys recursively.

- [x] **Step 2: Run the focused test and verify it fails because the contract owner does not exist**

  Run: `python -m unittest tests.gear_evidence_registry_test`

  Expected: import or missing-symbol failure, not a skipped test.

- [x] **Step 3: Implement the pure contract owner**

  In `server/gear_evidence_registry.py`, add canonical JSON/hash helpers plus public constructors/validators:

  - `build_evidence_artifact(...)`
  - `build_evidence_observation(...)`
  - `build_canonical_fact(...)`
  - `canonical_fact_key(...)`
  - `fact_value_hash(...)`
  - `provenance_hash(...)`

  Require schema revisions `gear-evidence-artifact-v1`, `gear-evidence-observation-v1`, and `gear-canonical-fact-v1`; accept only the three approved fact statuses. Keep all returned mappings JSON-canonical and immutable by convention.

- [x] **Step 4: Re-run the focused contract suite**

  Run: `python -m unittest tests.gear_evidence_registry_test`

  Expected: pass, including deterministic repeated construction.

- [x] **Step 5: Record the implementation names in the approved design without changing its semantics**

  Add a short implementation-anchor paragraph to the design that names the module and hash contracts; do not change approved product behavior.

- [x] **Step 6: Commit the isolated contract slice**

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

- [x] **Step 1: Add failing store/schema tests**

  Test duplicate Artifact/Observation insertion reuses the original immutable row; assert Observation cannot reference a missing Artifact; assert Facts are versioned append-only by `(fact_key, fact_value_hash, provenance_hash)`; assert a Gap is idempotent by `gap_key` and fenced by `lock_token`; assert runtime role grants no `UPDATE`/`DELETE` to Artifact, Observation, or Fact rows.

- [x] **Step 2: Run the focused tests to establish failure**

  Run: `python -m unittest tests.gear_evidence_store_test tests.postgres_schema_test`

  Expected: missing migration/store behavior.

- [x] **Step 3: Add migration `0019_gear_evidence_registry`**

  Create `cache.websim_gear_evidence_artifacts`, `cache.websim_gear_evidence_observations`, `cache.websim_gear_canonical_facts`, `cache.websim_gear_evidence_invalidations`, and `ops.websim_gear_evidence_gaps`.

  Enforce canonical identities, JSONB payloads, artifact/observation foreign keys, append-only permissions, and indexes for `(season_revision, subject_key, fact_type)`. Make the queue operational only: `status`, `attempt`, `locked_by`, `lock_token`, `lease_until`, `next_attempt_at`, `problem_code`, and structured `missing_requirement_json`; do not put Fact values in queue result fields. Register the migration in `ops.schema_migrations` and update `docs/database-architecture.md`.

- [x] **Step 4: Implement the two SQL owners**

  `GearEvidenceStore` owns only Artifact, Observation, invalidation, and Fact persistence/query methods. `GearEvidenceGapStore` owns only `enqueue_gaps`, `claim_next`, `finish`, and `health_summary`, copying the lease/CAS discipline of `AttributeRuleAuditStore` but using the approved Gear gap statuses and root codes.

- [x] **Step 5: Re-run focused storage and schema tests**

  Run: `python -m unittest tests.gear_evidence_store_test tests.postgres_schema_test`

  Expected: all storage invariants and role assertions pass.

- [x] **Step 6: Commit the registry persistence slice**

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

- [x] **Step 1: Write failing observer tests**

  Cover parser replay from a stored Battle.net item Artifact, SimC exact-item/bonus probe Artifact, and season-rule Artifact. Assert parser revisions become part of Observation identity; a malformed source becomes a structured parser result rather than a default Observation; no observer reads the clock or network.

- [x] **Step 2: Write failing compiler-policy tests**

  Use small fixtures to cover each first-stage policy: `item_identity`, `slot_compatibility`, `variant_track`, `static_stats`, `socket_count`, `enchant_capability`, `embellishment_capability`, `enhancement_option`, `allowed_enhancement_options`, `item_set_membership`.

  Explicitly test `socket_count=1` for `250033/void_upgrade-298`, verified zero sockets, absence-not-zero, conflicting exact observations, policy revision invalidation, and byte-for-byte deterministic recompilation.

- [x] **Step 3: Run the focused observer/compiler tests and verify failure**

  Run: `python -m unittest tests.gear_evidence_observers_test tests.gear_fact_compiler_test`

- [x] **Step 4: Implement observers and compiler**

  In `server/gear_evidence_observers.py`, expose deterministic `observe_*` functions returning accepted observations or structured non-observation diagnostics. In `server/gear_fact_compiler.py`, expose `FACT_POLICIES`, `compile_facts(...)`, `compile_subject_facts(...)`, and `evidence_gaps_from_facts(...)`.

  Every policy declares allowed sources, source scope, combination mode, closed-world condition for false/zero, conflict policy, impact scope, and rule revision. Adapt `gear_socket_authority.py` to emit source observations/input facts only; remove its authority to decide the final consumer payload. Keep dynamic legality in `gear_rule_matrix.py` untouched except for accepting canonical static inputs.

- [x] **Step 5: Re-run focused tests and ensure the legacy socket fixture still passes**

  Run: `python -m unittest tests.gear_evidence_observers_test tests.gear_fact_compiler_test tests.gear_socket_authority_test tests.gear_rule_matrix_test`

  Expected: the exact `250033` conflict is represented as one verified compiled socket fact, not two competing source booleans.

- [x] **Step 6: Commit the pure compilation slice**

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

- [x] **Step 1: Add failing release tests**

  Assert a prepared snapshot materializes `canonicalFacts` and bounded fact/provenance references in item, variant, and option payloads without copying raw Artifact payloads. Assert source evidence includes a deterministic compiler policy/fact digest. Assert a no-op recompilation creates neither a new content hash nor a new candidate release.

- [x] **Step 2: Add failing shadow-classification tests**

  `compare_legacy_and_canonical(...)` must classify every difference exclusively as `exact_parity`, `intended_correction`, `newly_exposed_gap`, or `regression`; unclassified differences must fail release preparation. Include the known browse/Resolve `250033` `hasSocket=false` vs `socketCount=1` case as `intended_correction`.

- [x] **Step 3: Run the release/shadow tests to establish failure**

  Run: `python -m unittest tests.gear_release_tool_test tests.gear_release_refresh_test tests.gear_fact_shadow_test`

- [x] **Step 4: Integrate the compiler into the sole release-preparation path**

  Replace the direct terminal authority of `_project_socket_facts_into_release_payloads(...)` and `_materialize_enhancement_management(...)` with an adapter that:

  1. imports accepted legacy source records into Artifact/Observation form;
  2. compiles Facts using the declared policy revision;
  3. projects only release-safe fact values/statuses/references into the immutable snapshot;
  4. enqueues unresolved Facts idempotently; and
  5. runs shadow classification before `seal_gear_release`.

  Preserve current Gear Release integrity checks, parent release behavior, and candidate-first publication. Do not alter active Manifest selection here.

- [x] **Step 5: Re-run release tests**

  Run: `python -m unittest tests.gear_release_tool_test tests.gear_release_refresh_test tests.gear_fact_shadow_test`

  Expected: a repeat preparation with unchanged inputs is a no-op and regressions block a candidate.

- [x] **Step 6: Commit the release integration slice**

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

- [x] **Step 1: Write failing loader/resolver tests**

  Assert loader reads Canonical Facts only from the selected Gear Release and rejects mutable staging/source payload as a fallback. Assert Resolver projects fact refs into the existing evidence ledger as a Resolution Proof, while dynamic selection checks continue to run separately.

- [x] **Step 2: Write failing public-contract tests**

  Assert a browse payload and exact Resolve result report the same canonical capability state for the same item/variant. Test `250033/void_upgrade-298` as one socket; test verified zero as unavailable; test unresolved capability as `pending` and disabled only in that category.

- [x] **Step 3: Run focused loader/resolver/serializer tests to establish failure**

  Run: `python -m unittest tests.pg_gear_authority_loader_test tests.gear_resolver_test tests.websim_payload_test`

- [x] **Step 4: Implement the one-way consumer projection**

  `pg_gear_authority_loader.py` reads `canonicalFacts` as the sole static authority. `gear_resolver.py` consumes those facts and attaches fact references to `gear-evidence-ledger-v1` without recomputing source truth. `websim_payload.py` emits capability views with state/value/options derived solely from released facts. If legacy booleans remain, derive them only in this serializer from verified capability facts.

- [x] **Step 5: Update the route truth contract and re-run focused tests**

  Document that compact browse and exact Resolve share the same published fact projection; keep all internal provenance out of the public route contract.

  Run: `python -m unittest tests.pg_gear_authority_loader_test tests.gear_resolver_test tests.websim_payload_test`

- [x] **Step 6: Commit the consumer authority slice**

  ```powershell
  git add server/pg_gear_authority_loader.py server/gear_resolver.py server/gear_evidence_ledger.py server/websim_payload.py tests/pg_gear_authority_loader_test.py tests/gear_resolver_test.py tests/websim_payload_test.py docs/design/current-ui/routes/gear-detail/truth-adaptation.json
  git commit -m "feat(gear): consume released canonical facts"
  ```

- [x] **Step 7: Publish the reviewed Task 5 cross-device checkpoint**

  After every Task 5 targeted test is GREEN, the independent review is clean, and local CR confirms the complete Task 5 diff:

  ```powershell
  git diff --check
  git status --short --branch
  git add docs/plans/2026-07-26-gear-evidence-registry-implementation.md docs/roadmap.md docs/roadmap/ideas.md server/gear_fact_compiler.py server/gear_fact_shadow.py server/gear_release_store.py server/gear_release_tool.py server/gear_resolver.py server/gear_rule_matrix.py server/gear_runtime.py server/pg_gear_authority_loader.py server/websim_payload.py tests/gear_fact_compiler_test.py tests/gear_release_store_test.py tests/gear_release_tool_test.py tests/gear_resolver_test.py tests/gear_runtime_test.py tests/pg_gear_authority_loader_test.py tests/websim_payload_test.py
  git commit -m "fix(gear): close released fact consumer review"
  git push -u origin codex/gear-evidence-registry
  git rev-parse HEAD
  git rev-parse origin/codex/gear-evidence-registry
  ```

  The two SHAs must match. Record the exact branch, SHA, focused-test result, review status, remaining untracked/unstaged state, and the next unchecked plan step in the thread handoff. Do not merge `main`, create a retail candidate, activate a Manifest, or start Task 6 at this checkpoint.

## Task 6: Make Taro render verified, unavailable, and pending capabilities consistently

**Files:**

- Modify: `packages/domain/src/entities.ts`
- Modify: `apps/mini-taro/src/pages/builds/gear-detail-model.ts`
- Modify: `apps/mini-taro/src/pages/builds/detail.tsx`
- Modify: `apps/mini-taro/src/pages/builds/gear-detail-model.test.ts`
- Modify: `apps/mini-taro/src/pages/builds/detail.test.tsx`

- [x] **Step 1: Add failing model tests for the three visible states**

  Verify: (1) socket count one is selectable even if a legacy `hasSocket=false` field appears; (2) verified `socket_count=0` is displayed as “不可用”; (3) unresolved socket/enchant/embellishment shows only that category as “待核验” and disables its controls; (4) verified categories remain usable; (5) artifact, hash, root code, and worker status never become UI text.

- [x] **Step 2: Run the focused Taro tests and verify failure**

  Run:

  ```powershell
  & 'C:\Users\blizz\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' --test apps/mini-taro/src/pages/builds/gear-detail-model.test.ts apps/mini-taro/src/pages/builds/detail.test.tsx
  ```

- [x] **Step 3: Add typed public capability views and remove independent boolean interpretation**

  Define `GearCapabilityFactView` in `packages/domain/src/entities.ts` with `status`, `value`, and safe option references. In `gear-detail-model.ts`, make `gearEnhancementSocketCount` consume the canonical state/value first and treat legacy boolean fields only as serializer compatibility output, never as a precedence rule. Update `detail.tsx` to show the approved three labels without a diagnostic affordance.

- [x] **Step 4: Re-run targeted Taro tests**

  Run the same bundled-Node command.

  Expected: item `250033`, variant `void_upgrade-298`, reaches the gem selector with one slot.

- [x] **Step 5: Commit the UI consumer slice**

  ```powershell
  git add packages/domain/src/entities.ts apps/mini-taro/src/pages/builds/gear-detail-model.ts apps/mini-taro/src/pages/builds/detail.tsx apps/mini-taro/src/pages/builds/gear-detail-model.test.ts apps/mini-taro/src/pages/builds/detail.test.tsx
  git commit -m "fix(gear): render canonical enhancement states"
  ```

- [x] **Step 6: Publish the reviewed Task 6 cross-device checkpoint**

  After the focused Taro tests are GREEN, independent review is clean, and local CR confirms the Task 6 diff, record the completed steps in this tracked implementation plan, push `codex/gear-evidence-registry`, and verify local `HEAD` equals `origin/codex/gear-evidence-registry`. Stop after the checkpoint. Do not merge `main`, create a candidate, switch a Manifest, deploy retail, or start Task 7/8.

## Task 7: Close unresolved-fact automation through a bounded internal worker and health

> 2026-07-27 scope extension approved by the user: in addition to fenced
> collection, this task includes a source-specific trusted collector and a
> separate consumer that can seal an inactive candidate Gear Release from its
> immutable Artifact/Observation inputs. It cannot call refresh/promotion,
> switch a Manifest, deploy a candidate, or change retail. Those remain Task 8.

**Files:**

- Create: `server/gear_evidence_gap_worker.py`
- Create: `server/gear_evidence_candidate_request_store.py`
- Create: `server/gear_evidence_candidate_recompiler.py`
- Create: `server/migrations/postgres/0020_gear_evidence_candidate_recompile.sql`
- Create: `tests/gear_evidence_gap_worker_test.py`
- Create: `tests/gear_evidence_candidate_recompiler_test.py`
- Create: `server/wow-gear-evidence-gap-worker.service`
- Create: `server/wow-gear-evidence-candidate-recompiler.service`
- Modify: `server/news_backend.py`
- Modify: `server/data_health_followup.py`
- Modify: `server/gear_evidence_store.py`
- Modify: `server/gear_release_tool.py`
- Modify: `server/gear_release_refresh.py`
- Modify: `tests/news_backend_test.py`
- Modify: `tests/data_health_followup_test.py`
- Modify: `server/deploy_lighthouse.sh`

- [x] **Step 1: Write failing worker and health tests**

  Assert claim/retry/lease loss/terminal behavior. Assert a worker only invokes approved collectors/parsers and requests candidate recompilation; it cannot update a Fact, call Manifest activation, or overwrite conflict state. Assert `/api/data/health` exposes aggregate queue state/revision only and `data_health_followup.py` triggers the service only for a changed explicit queue revision. For the approved extension, assert the strict `simc_bonus_probe` collector observes one socket for `250033/void_upgrade-298`, the durable candidate handoff is fenced/retryable, and the candidate-only recompiler seals before it completes its matching gap.

- [x] **Step 2: Run focused worker/health tests to establish failure**

  Run: `python -m unittest tests.gear_evidence_gap_worker_test tests.news_backend_test tests.data_health_followup_test`

- [x] **Step 3: Implement the bounded worker and operational health component**

  Add `run_gear_evidence_gap_worker(...)` with a fixed maximum job count, lease fencing, idempotent collector inputs, and structured outcomes. Add `gear_evidence_gap_health_component(...)` in `news_backend.py`. Add the `gear_evidence_gap_worker` systemd action to `data_health_followup.py`, gated by queue input revision rather than human-readable blockers. Install a oneshot service through `server/deploy_lighthouse.sh`; the existing health-followup timer remains the scheduler. The worker writes only immutable Artifact/Observation, hands recovered work to a fenced `candidate_pending` request, and never finishes that gap itself.

  The `simc_bonus_probe` collector accepts only `socket_count` + `exact_variant` routes with a strict positive trailing bonus id. The candidate recompiler reads only the request's fenced identities, supplies them explicitly to candidate release preparation, and can only seal the inactive candidate pair. It must not invoke `run_release_refresh`, any Manifest writer/CAS, or deployment.

- [x] **Step 4: Re-run worker/health tests**

  Run: `python -m unittest tests.gear_evidence_gap_worker_test tests.news_backend_test tests.data_health_followup_test`

- [x] **Step 5: Commit the automatic-closure slice**

  ```powershell
  git add docs/plans/2026-07-26-gear-evidence-registry-implementation.md server/gear_evidence_gap_worker.py server/gear_evidence_candidate_request_store.py server/gear_evidence_candidate_recompiler.py server/migrations/postgres/0020_gear_evidence_candidate_recompile.sql server/wow-gear-evidence-gap-worker.service server/wow-gear-evidence-candidate-recompiler.service server/gear_evidence_gap_store.py server/gear_evidence_store.py server/gear_fact_compiler.py server/gear_release_tool.py server/gear_release_refresh.py server/news_backend.py server/data_health_followup.py server/deploy_lighthouse.sh tests/gear_evidence_gap_worker_test.py tests/gear_evidence_candidate_recompiler_test.py tests/gear_evidence_store_test.py tests/gear_fact_compiler_test.py tests/gear_release_tool_test.py tests/news_backend_test.py tests/data_health_followup_test.py tests/postgres_schema_test.py
  git commit -m "feat(gear): automate evidence gap recovery"
  ```

  The checkpoint follows fresh focused verification (including candidate-only
  recompile and schema coverage), an independent review, and local CR. It does
  not deploy the new services or candidates, change a Manifest, or start Task 8.

## Task 8: Candidate rollout, active cutover, and legacy authority removal

**Files:**

- Create: `docs/runbooks/gear-evidence-registry-cutover.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/roadmap/ideas.md`
- Modify: `docs/plans/README.md`
- Modify: `docs/project-owner-map.json`
- Modify: `docs/backend-owner-map.json`
- Modify: legacy modules named by caller-proof search in `server/gear_socket_authority.py`, `server/gear_release_tool.py`, `server/pg_gear_authority_loader.py`, `server/websim_payload.py`, and `apps/mini-taro/src/pages/builds/gear-detail-model.ts`

- [x] **Step 1: Add failing end-to-end characterization tests**

  Build a candidate snapshot with the canonical compiler and assert: no partial/needs-variant duplicate leaks as an exact selection; browse/Resolve/Taro agree for 250033; a missing capability affects only its own controls; and no-op refresh leaves the active/candidate release identity unchanged.

  Completed before candidate work. The characterization coverage remains local-only; it creates no candidate release, does not deploy a service, and does not change a Manifest.

- [x] **Step 2: Run the scoped backend and frontend suite before cutover changes**

  Run:

  ```powershell
  python -m unittest tests.gear_evidence_registry_test tests.gear_evidence_store_test tests.gear_evidence_observers_test tests.gear_fact_compiler_test tests.gear_fact_shadow_test tests.gear_release_tool_test tests.gear_release_refresh_test tests.pg_gear_authority_loader_test tests.gear_resolver_test tests.websim_payload_test tests.gear_evidence_gap_worker_test
  & 'C:\Users\blizz\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' --test apps/mini-taro/src/pages/builds/gear-detail-model.test.ts apps/mini-taro/src/pages/builds/detail.test.tsx
  ```

  Fresh local result on 2026-07-27: `python3 -m unittest` passed **722 tests** in 21.149s. The exact two-file Taro Vitest invocation passed **34 tests**. The Python process emitted pre-existing non-failing unclosed SQLite `ResourceWarning` messages; neither result is candidate, deployment, real-WeChat, user-acceptance, Manifest-CAS, or closure evidence.

- [x] **Step 3: Write the candidate deployment and rollback runbook**

  Document exact sequence: schema migration backup/check, Artifact import, Observation replay, shadow report review, candidate Gear Release identity, candidate deploy parity, health/API/Resolve smoke, Taro route manual acceptance, explicit active Manifest CAS, and rollback to the previous existing Manifest revision. State that registry rows survive rollback and no active pointer changes without explicit user authorization.

  The fail-closed procedure is recorded in [gear-evidence-registry-cutover.md](../runbooks/gear-evidence-registry-cutover.md). It requires a separately identified candidate PostgreSQL target, tree/root/service/port, a backup before the sequential `0019` then `0020` migrations, and an explicit retail authorization boundary. It does not create a candidate or Active Season Manifest merely by existing.

- [x] **Step 3.5: Bind an immutable pre-candidate runtime checkpoint**

  After the runbook and packet are final, perform final local CR, commit and push the complete runtime slice, require a clean task branch, re-run the scoped backend/frontend suites, and bind the exact committed `HEAD` and tree hash in the evidence packet. Candidate deployment may use only that committed tree. Later evidence-only changes may append evidence but must not modify runtime source, build inputs, or the bound candidate identity; any such modification requires a new checkpoint and candidate window.

  Completed on 2026-07-27 at runtime commit `9d6a0772c6493b69d5fb366fd1728c447439f9f2` and tree `7b3c058454f5b0b621103ec1c7595c36d7d7bcc8`. The pushed branch matched that commit; the clean checkpoint re-ran 722 scoped Python tests, 34 scoped Taro tests, and the 283-check UI architecture audit. This records local verification only and creates no candidate root, database, service, pointer, or retail change.

- [x] **Step 3.6: Rebind the candidate checkpoint after full-catalog capacity correction**

  The first isolated candidate build never persisted an Artifact, Observation, Fact, Gap, or release, but it exhausted the small candidate host while repeatedly rescanning the full evidence universe for each fact and again during seal replay. Treat that as a failed candidate attempt, not a candidate result. The repair introduces a single indexed batch compiler for the complete requested subject/fact universe and uses it for both candidate preparation and complete-store replay; it preserves the existing pure per-subject compiler for narrow callers. New candidate writes must run in a named cgroup with recorded CPU, memory, niceness, and runtime limits so a failed verification cannot starve the retail service.

  Completed on 2026-07-27 at runtime commit `dd0489b9a020f94377d291b15acc7c47981027b5` and tree `e7108a507a047a341e9adbb1ad8696570754b297`. The pushed branch matches the runtime commit. The fresh scoped Python suite passed 725 tests in 22.838s, the two-file Taro suite passed 34 tests, and the UI architecture audit passed 283 checks. This remains local verification only; a new isolated root/database, bounded build, release seal, service smoke, and real-WeChat acceptance remain Step 4/5 work.

- [ ] **Step 3.7: Replace the full-catalog peak-memory path with a bounded streaming release build**

  The r5 failure is a release-build implementation defect, not a reason to relax
  the candidate resource envelope: preparation retained a full raw snapshot,
  full Artifact/Observation/Fact collections, a full legacy/canonical shadow,
  and later re-created the same full evidence universe during seal. On a 4GB
  shared host that can exhaust retail headroom even when the candidate remains
  inside its own `MemoryMax`. The correction must retain the same fail-closed
  release semantics while bounding transient work to one deterministic subject
  batch plus the returned release snapshot.

  1. Add failing focused tests that run the release preparation with a tiny
     batch size and prove it produces the same projected snapshot, release
     identity/content hash, gap set, and `250033/void_upgrade-298` socket fact
     as the current deterministic compiler. Include an allowed-option rule
     whose referenced option belongs to a different batch, a regression that
     must still block shadow, and a receipt-tamper case that must still block
     seal. The tests must exercise real compiler/store behavior, not assert
     internal call counts.
  2. Compile and persist immutable Evidence in deterministic batches. Option
     evidence required by an item/variant allowed-option rule is a read-only
     compiler context, never a duplicate persistence write. Project each
     completed batch into the one release snapshot in place; do not retain a
     second canonical snapshot or a whole-catalog Fact list. Preserve the
     existing monolithic helper only for narrow callers and explicitly supplied
     gap-recovery inputs until that path receives its own bounded treatment.
  3. Replace full comparison arrays and identity arrays in the streaming gate
     with a versioned, deterministic compact receipt (counts plus a
     digest). The compact shadow must still classify every fact and fail closed
     on any regression or unclassified difference. Legacy v1 receipts/shadows
     remain verifiable so existing releases are not reinterpreted.
  4. Make `GearReleaseStore` replay the expected evidence and validate receipt,
     Fact, gap, and shadow semantics in the same deterministic batches. It may
     never trust a compact digest without re-reading immutable Store rows; it
     must reject missing, duplicated, tampered, or cross-batch observations.
  5. Re-run the focused tool/store/shadow/compiler suites, then the complete
     scoped backend and Taro matrix. Run independent review and local CR,
     create a new immutable runtime checkpoint, and use a new isolated
     candidate root/database only after its capacity preflight. Do not retry r5,
     merge `main`, switch a Manifest, or touch retail in this step.

  Implementation/local verification progress on 2026-07-27: the release path
  now persists and projects one deterministic batch at a time, writes a compact
  v2 shadow/receipt, and seals by independently replaying the same bounded
  schedule from Store rows. The schedule is sealed with its batch size and
  order revision; later item/variant batches reuse one compact option-Fact map
  rather than raw option Artifacts/Observations. TDD covers a cross-batch
  option rule, no duplicate option persistence, a deliberately unordered
  multi-row prepare/seal replay, receipt tampering, and the Store's independent
  `allowed_enhancement_options` replay. The focused suite passed 146 tests;
  the complete scoped Python suite passed 727 tests in 22.235s; the two-file
  Taro suite passed 34 tests; and the UI architecture audit passed 283 checks.
  The non-failing pre-existing SQLite `ResourceWarning` messages remain. A
  second independent local CR found no remaining P1/P2 after the added Store
  replay coverage. This step remains unchecked until a newly committed and
  pushed immutable checkpoint is deployed to a new isolated candidate root and
  its bounded full-catalog build is observed.

- [ ] **Step 4: Execute candidate-only deployment verification**

  Deploy the branch/commit to the approved candidate path with `WOW_DEPLOY_START_ASYNC_SYNCS=0`; record release/manifest identities, runtime file parity, health component state, worker state, exact API payloads, and the fallback Manifest revision. Do not merge or activate production here.

  The candidate public API service is read-only with collectors disabled and must bind its inactive candidate Gear/Community Release through the dedicated candidate-release configuration, not a candidate Manifest CAS. Migration, Artifact/Observation replay, and bounded worker/recompiler execution run only as separately named writable one-off processes against the isolated candidate database.

  Current candidate state on 2026-07-27: the isolated `gear-evidence-registry-dd0489b9-r4` source root and verified pre-0019 backup were created with the required resource envelope, but its PostgreSQL restore stopped before 0019 while restoring `websim_gear_release_variants` because the shared host had insufficient disk capacity for another full database copy. The backup and stopped partial candidate database are retained for diagnosis. No candidate public process, release, Manifest, retail database, or retail pointer changed. With explicit user authority, three unreferenced July 15–17 historical candidate archive directories were removed after service-reference checks, restoring approximately 9.46GiB while retaining r3/r4. Fresh `r5` capacity, backup, sequential migration, candidate binding, and async-sync guard checks then passed. Its full-catalog build stayed below the 45% CPU quota but reached the 2.2GB candidate memory ceiling while the shared 4GB host retained only approximately 180MB; it was stopped before persistence. The r5 registry/release rows remain zero. Do not retry until candidate capacity can leave retail headroom or a separately reviewed streaming-memory correction is bound to a new immutable checkpoint.

- [ ] **Step 5: Obtain explicit user acceptance for the real Taro route and active cutover**

  Manual acceptance must verify the equipment-detail route shows one gem slot for `250033/void_upgrade-298`, shows “不可用” for confirmed unsupported capability, and shows “待核验” only for unresolved categories. Until this acceptance, retain old active Manifest and classify the work as candidate-verified only.

- [ ] **Step 6: Cut over atomically and prove rollback remains available**

  On explicit acceptance only, first complete final CR and evidence, commit/push the task branch, merge/push `main`, prove local/remote SHA parity, and re-run scoped verification on the merge result. Back up retail and deploy compatible code/schema; deterministically replay the same immutable Artifact/Observation inputs and revisions into retail, materialize retail releases, and prove their IDs/content hashes/digests equal the accepted candidate releases. Only then re-read a fresh retail pointer generation, execute the existing Manifest CAS, run fresh API/Resolve/Taro smoke, and prove previous Manifest rollback. Then remove compatibility writers/readers found by caller-proof search so no `hasSocket` or enhancement capability truth remains outside Canonical Fact projection.

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
