# Observed Build Registry Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Every production behavior follows RED → GREEN → REFACTOR; Harness remains the delivery control plane.

**Goal:** 建立一条 dormant、shadow-only 的核心路径，把不可变玩家快照和确定性 projection 组装成完整 80 槽 TemplateSet，并通过 PostgreSQL compare-and-swap 指针证明同槽 LKG、pending 和原子切换语义。

**Architecture:** 新增三个小型领域 owner：`observed_build_registry.py` 只拥有不可变快照，`observed_build_projection.py` 只拥有 projection 结果封装与依赖绑定，`observed_build_template_set.py` 只拥有 80 槽构建和发布分类。`observed_build_store.py` 独占新增 PostgreSQL 表的 SQL；本切片不接管公开 reader、旧 Community Release、定时任务或网络采集。

**Tech Stack:** Python 3 标准库、PostgreSQL additive migration、`unittest`、现有 Project Harness v0.6.4。

## Global Constraints

- 分类为 `Strict`；用户已确认 [Observed Build Registry 设计](2026-07-23-observed-build-registry-design.md)，本计划仍需用户审阅后才进入代码实现。
- 不修改 `server/postgres_cache_sync.py`、`server/postgres_cache_store.py`、`server/websim_payload.py`、`server/gear_release_store.py` 的领域判断。
- 不访问 Raider.IO、Battle.net、WCL 或其他网络来源；不下载、不安装依赖。
- 不修改公开 talents/gear API、活动 Community Release/Manifest、活动前端、health、timer 或 SimC runner。
- 不运行完整战斗 SimC；`profileReadiness=ready` 仅表示 serializer/runtime 可执行。
- 80 槽完整性表示 80 个唯一 entry；`verified`、`stale_lkg`、`pending_collection` 都是合法 entry。
- LKG 只能来自完全相同的 `(classKey, specKey, heroKey, scenarioKey)`。
- dependency vector 变化不得走 observed-only 自动 promotion。
- 新表、repository 和 pointer 在本切片结束时保持 dormant；候选环境只证明 migration、写读、CAS 和 rollback，不切公开生产指针。

## Harness Contract

### 用户场景与承诺

玩家后续看到的天赋和装备社区模板将来自同一份真实玩家快照经过当前 authority 的映射。新 winner 无法映射时，同槽旧模板继续可用并标记 stale；没有旧模板时诚实显示 pending，不影响其他槽更新。

本切片不产生用户可见变化。它交付的是后续接入真实采集、authority adapter 和公开 reader 所需的唯一稳定中间层。

### 非目标

- 不实现 Raider.IO collector、真实 PG 回填或 80 槽网络采集。
- 不把旧 `gearProjectionCandidates` 直接提升为新 production snapshot。
- 不实现 candidate/public API、health/admin、timer 或前端文案。
- 不替换 Gear/Community Release，也不迁移 stat snapshot、SimC task 或个人模板。
- 不设计冷存储、事件总线、微服务、通用 workflow/DSL。

### Impact Map

| 分类 | 内容 |
| --- | --- |
| `must_change` | 新纯领域模块、新 additive migration、新独立 repository、新测试、owner map、Harness packet |
| `must_not_change` | canonical talent authority、gear Resolver、旧 release train、public observed-only、exact import、stat worker、SimC runner、Taro |
| `risk_unknown` | 活动 80 槽与新 slot key 的精确一致性；不可变 row hash/外键是否覆盖脏写；并发 CAS 的 generation 语义 |
| `evidence_required` | deterministic hash、duplicate no-op、A→B、blocked B→A LKG、无 LKG pending、79 槽正常更新、跨槽 LKG 拒绝、dependency drift、CAS/rollback、旧测试不变 |

### Owner 与工程健康

- `server/observed_build_registry.py`：snapshot identity、hash、结构验证。
- `server/observed_build_projection.py`：projection identity、dependency binding、verified/blocked 结果；合法性仍由后续 adapter 调用既有 talent authority 和 gear Resolver。
- `server/observed_build_template_set.py`：期望槽、同槽 LKG、完整性、publication classification。
- `server/observed_build_store.py`：新增表的唯一 SQL owner；不向 `PostgresCacheStore` 或 `GearReleaseStore` 增加新职责。
- 工程健康结论：`health_watch`。原因是新增 migration 和 CAS 写路径，但不修改活动 reader/任务；通过 additive schema、不可变 hash、受控候选和回滚证明约束风险。

### 发布与回滚

- 本地：只应用测试 fake connection，不连接生产。
- 候选：备份实际 PG target，记录 migration 前表/指针不存在或为空；应用 migration，写入隔离测试 scope，证明重复 seal no-op、CAS 冲突 fail closed、rollback generation 单调；删除隔离 scope 仅允许通过候选专用清理 SQL，不授予活动 runtime DELETE。
- 防回流：`WOW_DEPLOY_START_ASYNC_SYNCS=0`；不启动 community/gear refresh、backfill 或 health follow-up。
- 回滚：代码使用 `code_rollback`；未被公开 reader 引用的新增空表可保留。若候选测试数据异常，使用候选备份执行 `data_restore`，不修改旧 Release/Manifest。

---

### Task 1: Freeze the 80-slot and public-contract baseline

**Files:**
- Create: `tests/observed_build_characterization_test.py`
- Read only: `server/websim_payload.py`
- Read only: `server/gear_public_contract.py`

**Interfaces:**
- Consumes: `server.websim_payload.expected_hero_tree_triplets() -> list[str]`
- Produces: a frozen assertion that the current matrix has exactly 80 unique `class:spec:hero` triplets and expands to `scenarioKey="mythic_plus"`.

- [ ] **Step 1: Write the failing characterization test**

```python
import unittest

from server.websim_payload import expected_hero_tree_triplets


class ObservedBuildCharacterizationTest(unittest.TestCase):
    def test_current_hero_matrix_is_exactly_eighty_unique_mythic_plus_slots(self):
        triplets = expected_hero_tree_triplets()
        slots = [f"{triplet}:mythic_plus" for triplet in triplets]

        self.assertEqual(len(triplets), 80)
        self.assertEqual(len(set(triplets)), 80)
        self.assertEqual(len(slots), 80)
        self.assertTrue(all(slot.count(":") == 3 for slot in slots))
```

- [ ] **Step 2: Run the test and record the baseline**

Run:

```bash
python3 -m unittest tests.observed_build_characterization_test -v
```

Expected: PASS with one test. This task characterizes current behavior and intentionally has no production-code RED cycle.

- [ ] **Step 3: Run the existing public/release baseline**

Run:

```bash
python3 -m unittest \
  tests.gear_public_contract_test \
  tests.gear_release_test \
  tests.community_template_import_test
```

Expected: PASS; public observed-only and exact import remain unchanged.

### Task 2: Add immutable ObservedBuildSnapshot contracts

**Files:**
- Create: `server/observed_build_registry.py`
- Create: `tests/observed_build_registry_test.py`

**Interfaces:**
- Produces: `slot_key(slot) -> str`
- Produces: `build_observed_snapshot(*, slot, source, ranking_evidence, talent_observation, gear_observation, source_revision) -> dict`
- Produces: `validate_observed_snapshot(snapshot) -> list[dict]`
- Produces: `snapshot_check(*, run_id, slot, checked_at, status, snapshot_id="", problem=None) -> dict`

- [ ] **Step 1: Write failing tests for canonical identity and unchanged reuse**

```python
def test_same_observed_content_has_same_snapshot_id_despite_check_time():
    first = build_observed_snapshot(**snapshot_input())
    second = build_observed_snapshot(**snapshot_input())
    self.assertEqual(first["snapshotId"], second["snapshotId"])
    self.assertRegex(first["snapshotId"], r"^observed-build:sha256:[0-9a-f]{64}$")

def test_snapshot_rejects_missing_real_source_identity():
    value = snapshot_input()
    value["source"]["sourceIdentity"] = ""
    with self.assertRaisesRegex(ValueError, "sourceIdentity"):
        build_observed_snapshot(**value)

def test_source_check_time_is_not_part_of_immutable_snapshot():
    snapshot = build_observed_snapshot(**snapshot_input())
    check = snapshot_check(
        run_id="run-1",
        slot=snapshot["slot"],
        checked_at="2026-07-23T10:00:00+08:00",
        status="unchanged",
        snapshot_id=snapshot["snapshotId"],
    )
    self.assertNotIn("checkedAt", snapshot)
    self.assertEqual(check["status"], "unchanged")
```

- [ ] **Step 2: Verify RED**

Run:

```bash
python3 -m unittest tests.observed_build_registry_test -v
```

Expected: FAIL because `server.observed_build_registry` does not exist.

- [ ] **Step 3: Implement the minimal immutable contract**

The module must canonicalize dictionaries with sorted JSON keys; snapshot identity must include schema, exact slot, bounded Raider.IO source identity/profile URL, ranking evidence, talent/gear observations, the three source hashes and source revision. It must not include `checkedAt`, process time or database row IDs.

Core return shape:

```python
{
    "schemaRevision": "observed-build-snapshot-v1",
    "snapshotId": "observed-build:sha256:<digest>",
    "slot": {
        "classKey": "...",
        "specKey": "...",
        "heroKey": "...",
        "scenarioKey": "mythic_plus",
    },
    "source": {
        "sourceKey": "raiderio",
        "sourceIdentity": "raiderio:<bounded identity>",
        "profileUrl": "https://raider.io/...",
        "region": "...",
        "realm": "...",
        "character": "...",
    },
    "rankingEvidence": {...},
    "talentObservation": {...},
    "gearObservation": {...},
    "profileHash": "sha256:<digest>",
    "talentHash": "sha256:<digest>",
    "gearHash": "sha256:<digest>",
    "sourceRevision": "...",
}
```

- [ ] **Step 4: Verify GREEN**

Run:

```bash
python3 -m unittest tests.observed_build_registry_test -v
```

Expected: PASS.

### Task 3: Add deterministic BuildProjection contracts

**Files:**
- Create: `server/observed_build_projection.py`
- Create: `tests/observed_build_projection_test.py`

**Interfaces:**
- Consumes: valid `ObservedBuildSnapshot`
- Produces: `build_dependency_vector(...) -> dict`
- Produces: `build_projection(*, snapshot, dependency_vector, talent_projection, gear_projection, profile_readiness, problems=()) -> dict`
- Produces: `validate_projection(projection) -> list[dict]`
- Produces: `publication_change_kind(active_vector, candidate_vector) -> "observed_only" | "dependency_cutover"`

- [ ] **Step 1: Write failing tests**

```python
def test_same_snapshot_and_dependencies_compile_to_same_projection_id():
    first = verified_projection()
    second = verified_projection()
    self.assertEqual(first["projectionId"], second["projectionId"])

def test_blocked_projection_keeps_structured_problems_and_no_importable_payload():
    value = build_projection(
        snapshot=snapshot(),
        dependency_vector=dependencies(),
        talent_projection={"status": "blocked"},
        gear_projection={"status": "verified"},
        profile_readiness={"status": "blocked", "simcReady": False},
        problems=[{"code": "talent_mapping_failed", "stage": "talent"}],
    )
    self.assertEqual(value["status"], "blocked")
    self.assertEqual(value["problems"][0]["code"], "talent_mapping_failed")

def test_dependency_drift_requires_controlled_cutover():
    changed = {**dependencies(), "serializerRevision": "serializer-v2"}
    self.assertEqual(publication_change_kind(dependencies(), changed), "dependency_cutover")
```

- [ ] **Step 2: Verify RED**

Run:

```bash
python3 -m unittest tests.observed_build_projection_test -v
```

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement minimal projection identity**

`projectionId` must be `build-projection:sha256:<digest>` over snapshot ID, exact slot, complete dependency vector, talent result, gear result, readiness and problems. `status=verified` requires both projections verified, `profileReadiness.simcReady=true`, and no problems; all other combinations are `blocked`.

The dependency vector must require:

```python
(
    "seasonRevision",
    "talentCatalogRevision",
    "gearReleaseId",
    "gearRuleRevision",
    "resolverContractRevision",
    "serializerRevision",
    "simcRuntimeRevision",
    "selectionSchemaRevision",
    "projectionSchemaRevision",
)
```

- [ ] **Step 4: Verify GREEN**

Run:

```bash
python3 -m unittest tests.observed_build_projection_test -v
```

Expected: PASS.

### Task 4: Build complete 80-slot TemplateSets with same-slot LKG

**Files:**
- Create: `server/observed_build_template_set.py`
- Create: `tests/observed_build_template_set_test.py`

**Interfaces:**
- Consumes: 80 expected slot dictionaries, new projection results, optional active TemplateSet.
- Produces: `build_template_set(*, expected_slots, candidates_by_slot, active_set, dependency_vector, source_run_id) -> dict`
- Produces: `validate_template_set(template_set, expected_slots) -> list[dict]`
- Produces: `promotion_decision(*, active_set, candidate_set) -> dict`

- [ ] **Step 1: Write failing tests for the agreed failure matrix**

```python
def test_rank_one_b_replaces_a_when_b_is_verified():
    candidate = build_template_set(
        expected_slots=slots(),
        candidates_by_slot={slot_a(): verified_b()},
        active_set=active_with_a(),
        dependency_vector=dependencies(),
        source_run_id="run-b",
    )
    self.assertEqual(entry(candidate, slot_a())["projectionId"], verified_b()["projectionId"])
    self.assertEqual(entry(candidate, slot_a())["status"], "verified")

def test_blocked_b_keeps_same_slot_a_as_stale_lkg():
    candidate = build_template_set(
        expected_slots=slots(),
        candidates_by_slot={slot_a(): blocked_b()},
        active_set=active_with_a(),
        dependency_vector=dependencies(),
        source_run_id="run-b",
    )
    self.assertEqual(entry(candidate, slot_a())["projectionId"], projection_a_id())
    self.assertEqual(entry(candidate, slot_a())["status"], "stale_lkg")
    self.assertEqual(entry(candidate, slot_a())["problem"]["code"], "gear_mapping_failed")

def test_no_lkg_marks_one_pending_and_keeps_other_seventy_nine_entries():
    candidate = build_template_set(
        expected_slots=slots(),
        candidates_by_slot=verified_candidates_except(slot_a()),
        active_set=None,
        dependency_vector=dependencies(),
        source_run_id="run-1",
    )
    self.assertEqual(len(candidate["entries"]), 80)
    self.assertEqual(entry(candidate, slot_a())["status"], "pending_collection")
    self.assertEqual(sum(e["status"] == "verified" for e in candidate["entries"]), 79)

def test_cross_slot_lkg_is_rejected():
    malformed_active = active_with_projection_referenced_from_wrong_hero()
    with self.assertRaisesRegex(ValueError, "same-slot"):
        build_template_set(
            expected_slots=slots(),
            candidates_by_slot={slot_a(): blocked_b()},
            active_set=malformed_active,
            dependency_vector=dependencies(),
            source_run_id="run-b",
        )
```

- [ ] **Step 2: Verify RED**

Run:

```bash
python3 -m unittest tests.observed_build_template_set_test -v
```

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement the minimal builder**

Each entry must have exactly one expected slot and one of:

```python
{"status": "verified", "snapshotId": "...", "projectionId": "...", "problem": {}}
{"status": "stale_lkg", "snapshotId": "...", "projectionId": "...", "problem": {"code": "..."}}
{"status": "pending_collection", "snapshotId": "", "projectionId": "", "problem": {"code": "pending_collection"}}
```

The TemplateSet ID must be `template-set:sha256:<digest>` over schema, dependency vector and sorted entries, excluding creation time and pointer generation. If the new ID equals the active ID, `promotion_decision` returns `no_op`. Observed-only changes with unchanged dependency vector return `auto_promote`; dependency changes return `controlled_cutover`; structural errors return `blocked`.

- [ ] **Step 4: Verify GREEN and the full pure core**

Run:

```bash
python3 -m unittest \
  tests.observed_build_registry_test \
  tests.observed_build_projection_test \
  tests.observed_build_template_set_test -v
```

Expected: PASS.

### Task 5: Add the dormant PostgreSQL registry and CAS pointer

**Files:**
- Create: `server/migrations/postgres/0018_observed_build_registry.sql`
- Create: `server/observed_build_store.py`
- Create: `tests/observed_build_store_test.py`
- Modify: `tests/postgres_schema_test.py`

**Interfaces:**
- Consumes: valid snapshot, projection and TemplateSet dictionaries.
- Produces: `ObservedBuildStore.seal_snapshot(snapshot) -> dict`
- Produces: `ObservedBuildStore.record_snapshot_check(check) -> dict`
- Produces: `ObservedBuildStore.seal_projection(projection) -> dict`
- Produces: `ObservedBuildStore.seal_template_set(template_set) -> dict`
- Produces: `ObservedBuildStore.load_template_set(template_set_id) -> dict`
- Produces: `ObservedBuildStore.compare_and_swap_pointer(scope, expected_generation, template_set_id, actor) -> dict`
- Produces: `ObservedBuildStore.rollback_pointer(scope, expected_generation, actor) -> dict`

- [ ] **Step 1: Write the schema and store tests before SQL/implementation**

Required assertions:

```python
def test_snapshot_seal_is_insert_only_and_hash_conflict_fails():
    # first insert returns sealed row; same content reuses it; same ID/different row hash raises integrity error

def test_template_set_seal_writes_header_and_exactly_eighty_entries_in_one_transaction():
    # assert one header insert, 80 slot inserts, one integrity read and commit

def test_pointer_cas_is_monotonic_and_rejects_stale_generation():
    # UPDATE ... WHERE scope = %s AND generation = %s; rowcount 0 raises CAS conflict

def test_rollback_moves_to_previous_set_without_rewriting_immutable_rows():
    # generation increments, active/rollback IDs swap, no UPDATE on snapshot/projection/template-set tables
```

Migration assertions must require:

```text
cache.observed_build_snapshots
ops.observed_build_snapshot_checks
cache.observed_build_projections
cache.observed_build_template_sets
cache.observed_build_template_set_slots
cache.observed_build_template_set_pointer
```

and `ON DELETE RESTRICT`, status checks, unique slot keys, no runtime `DELETE`, and explicit `wow_app` grants.

- [ ] **Step 2: Verify RED**

Run:

```bash
python3 -m unittest tests.observed_build_store_test tests.postgres_schema_test -v
```

Expected: FAIL because migration/store do not exist.

- [ ] **Step 3: Add the additive migration**

The migration must:

- keep immutable snapshot/projection/set rows insert-only;
- store row hashes and content-addressed IDs;
- use a separate append-only snapshot check table for `checkedAt`;
- enforce projection-to-snapshot and slot-to-projection foreign keys;
- keep one pointer row per bounded scope with `generation >= 0`;
- grant runtime `SELECT, INSERT` on immutable tables and `SELECT, INSERT, UPDATE` only on the pointer;
- revoke `DELETE` on all six new tables from `wow_app`;
- register `0018_observed_build_registry` in `ops.schema_migrations`.

- [ ] **Step 4: Implement the repository**

Repository methods must validate pure contracts before SQL, use one transaction per seal/CAS action, compare stored row hashes before reusing immutable IDs, and raise:

```python
class ObservedBuildIntegrityError(RuntimeError): ...
class ObservedBuildPointerConflict(RuntimeError): ...
```

No repository method may import `websim_payload`, call external services, run SimC or mutate old Release/Manifest tables.

- [ ] **Step 5: Verify GREEN**

Run:

```bash
python3 -m unittest tests.observed_build_store_test tests.postgres_schema_test -v
```

Expected: PASS.

### Task 6: Prove the dormant shadow core end to end

**Files:**
- Create: `tests/observed_build_core_path_test.py`
- Modify: `docs/project-owner-map.json`
- Modify: `docs/backend-owner-map.json`
- Modify: `docs/plans/2026-07-23-observed-build-registry-design.md`
- Modify: `docs/plans/README.md`
- Delete: `docs/superpowers/plans/2026-07-23-mage-candidate-validation-and-elemental-effects.md`
- Create: `artifacts/releases/2026-07-23-observed-build-registry-core/requirement.json`
- Create: `artifacts/releases/2026-07-23-observed-build-registry-core/evidence.json`
- Create: `artifacts/releases/2026-07-23-observed-build-registry-core/manifest.json`

**Interfaces:**
- Consumes: the three pure modules and `ObservedBuildStore`.
- Produces: one test-only 80-slot flow proving snapshot → projection → TemplateSet → seal → CAS → blocked replacement → LKG → rollback.

- [ ] **Step 1: Write the failing core-path test**

The test must use real production modules with a fake DB connection and assert:

```python
self.assertEqual(first_pointer["generation"], 1)
self.assertEqual(first_set_counts, {"verified": 80, "stale_lkg": 0, "pending_collection": 0})
self.assertEqual(second_set_counts, {"verified": 79, "stale_lkg": 1, "pending_collection": 0})
self.assertEqual(second_pointer["generation"], 2)
self.assertEqual(rollback_pointer["generation"], 3)
self.assertEqual(rollback_pointer["activeTemplateSetId"], first_set["templateSetId"])
```

Also assert there are zero imports/calls for network clients, `subprocess`, SimC, `PostgresCacheStore`, `GearReleaseStore`, public readers and old active pointer tables.

- [ ] **Step 2: Verify RED**

Run:

```bash
python3 -m unittest tests.observed_build_core_path_test -v
```

Expected: FAIL until repository integration is complete.

- [ ] **Step 3: Make the core path pass without adding runtime integration**

Only fix the new modules/repository. Do not add adapters to old sync/public modules to satisfy this test.

- [ ] **Step 4: Update current owner/control-plane docs**

Register the new snapshot/projection/TemplateSet owners and changed-path patterns. Mark the design `正在推进`, link this implementation plan, remove the stopped Mage/Elemental plan from the active whitelist, and keep public reader/cutover explicitly outside the slice.

- [ ] **Step 5: Create the task-scoped Harness packet**

Use release slug `2026-07-23-observed-build-registry-core`. The requirement must declare:

- `manualAcceptance.required=false` because there is no user-visible runtime change;
- runtime identity pending until the final candidate commit;
- migration candidate, backup, CAS/rollback and old-reader non-activation evidence;
- rollback strategies `code_rollback` and `data_restore`.

- [ ] **Step 6: Run targeted verification**

Run:

```bash
python3 -m unittest \
  tests.observed_build_characterization_test \
  tests.observed_build_registry_test \
  tests.observed_build_projection_test \
  tests.observed_build_template_set_test \
  tests.observed_build_store_test \
  tests.observed_build_core_path_test \
  tests.postgres_schema_test \
  tests.gear_public_contract_test \
  tests.gear_release_test \
  tests.gear_release_store_test \
  tests.community_template_import_test
node scripts/project-harness.js --check \
  --requirement-file artifacts/releases/2026-07-23-observed-build-registry-core/requirement.json \
  --evidence-file artifacts/releases/2026-07-23-observed-build-registry-core/evidence.json \
  --manifest-file artifacts/releases/2026-07-23-observed-build-registry-core/manifest.json \
  --base origin/main
git diff --check
```

Expected: all tests and Harness checks pass.

- [ ] **Step 7: Run one whole-branch local CR**

Review only the task diff against the approved design, with special attention to immutable identity, same-slot LKG, pointer generation, runtime grants, old reader non-activation and migration rollback.

- [ ] **Step 8: Final verification and candidate preparation**

Run once on final local HEAD:

```bash
node scripts/verify-project.js \
  --profile full \
  --release artifacts/releases/2026-07-23-observed-build-registry-core
```

Expected: PASS. Then follow Harness Candidate Deployment Gate: backup candidate PG, apply `0018`, run isolated seal/CAS/rollback smoke with async sync disabled, record exact commit/tree and evidence. Do not activate public readers or production TemplateSet pointer in this slice.

## Self-Review

- Spec coverage: this slice covers immutable snapshot identity, deterministic projection identity, 80-slot uniqueness, same-slot LKG, pending, dependency drift, content hash, PG persistence and atomic pointer/rollback.
- Deferred by design: network collector, existing-cache backfill, live authority adapters, candidate/public reader, health/admin, timer and controlled first public cutover.
- Placeholder scan: every implementation and error path is explicit; no unresolved placeholder remains.
- Type consistency: snapshot/projection/TemplateSet IDs and store method names are identical across Tasks 2-6.
- Scope guard: no task changes old sync hotspots, public API, frontend, active Release/Manifest or SimC execution.
