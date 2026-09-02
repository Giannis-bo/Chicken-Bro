# Chickenbro-SimC Rebuild Phase 4 Formal SimC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose one trustworthy owner-scoped SimC snapshot, job, attempt, and result history shared by Mini and Web.

**Architecture:** Raider.IO and WCL remain source adapters that can only emit immutable snapshot candidates. A single readiness validator and compiler determine eligibility; PostgreSQL owns job state and leases, the independent Worker owns SimulationCraft execution, and a formal API exposes only semantically validated results and bounded provenance.

**Tech Stack:** Python 3, FastAPI, PostgreSQL queue/leases, cloud SimulationCraft runtime, TypeScript domain guards and API client.

**Spec:** `docs/superpowers/specs/2026-09-02-chickenbro-simc-total-rebuild-design.md`

## Global Constraints

- SimC runs only in the configured cloud runtime; do not install or execute SimulationCraft locally.
- Raider.IO/WCL HTTP 200, parsed JSON, or a generated profile is not readiness.
- Missing actor level, class, spec, race, talents, gear, runtime support, or source authority fails explicitly; no prototype level-90/default race/gear/talent values survive.
- Jobs/results are owner-scoped, inputs/results are immutable, and retry attempts do not create multiple results.
- A successful result requires return code 0, a valid actor, an accepted primary metric, matching input/compiler/runtime identity, and no fatal diagnostic.
- Raw third-party payloads, credentials, raw stdout/stderr, profiles, internal owners, and leases are not returned to clients.
- Formal clients do not call `/api/v2/prototype/**`.

---

## File Structure

- Modify `server/app/simulation/{ports,application,repository,sources,snapshots,readiness,compiler,worker}.py`: formal Principal flow, lists, strict source semantics, result provenance.
- Modify `server/app/worker/{leases,handlers,main}.py`: terminal idempotency and lease recovery.
- Create `server/app/api/routes/simc.py`: formal snapshot/job API.
- Modify `server/app/api/routes/__init__.py`, `server/app/api/dependencies.py`, `server/app/main.py`: register formal SimC application.
- Create `tests/app_simc_api_test.py`, `tests/app_simc_cross_client_test.py`, `tests/app_simc_result_semantics_test.py`.
- Modify existing `tests/app_simulation_{application,sources,readiness,compiler,worker}_test.py` and `tests/app_worker_{lease,runtime}_test.py`.
- Create `packages/domain/src/simc.ts`, `packages/domain/src/simc.test.ts`.
- Create `packages/api-client/src/simc.ts`, `packages/api-client/src/simc.test.ts`.
- Modify package indexes/clients.
- Create `artifacts/releases/2026-09-02-chickenbro-simc-simc/{requirement,evidence,manifest}.json`.

### Task 1: Formal owner-scoped Simulation application and history

**Files:**
- Modify: `server/app/simulation/ports.py`
- Modify: `server/app/simulation/application.py`
- Modify: `server/app/simulation/repository.py`
- Modify: `tests/app_simulation_application_test.py`

**Interfaces:**
- Produces: `SimulationApplication.resolve_source(principal, source_url)`, `submit(principal, snapshot_id, scenario, idempotency_key)`, `list_jobs(principal, cursor, limit) -> SimulationJobPage`, `read_job(principal, job_id) -> SimulationJobView`, and `read_snapshot(principal, snapshot_id)`.
- Cursor: base64url `{"updatedAt":"<UTC ISO>","id":"<UUID>"}`; default 20, maximum 50.

- [ ] **Step 1: Write failing Principal, pagination, and retry tests**

```python
def test_same_owner_job_history_is_stable_across_pages(self):
    first = app.list_jobs(principal, cursor=None, limit=2)
    second = app.list_jobs(principal, cursor=first.next_cursor, limit=2)
    self.assertEqual([job.id for job in first.items + second.items], expected_ids)

def test_submit_retry_returns_same_job_and_one_queue_command(self):
    first = app.submit(principal, snapshot.id, scenario, "job-request-1")
    second = app.submit(principal, snapshot.id, scenario, "job-request-1")
    self.assertEqual(first.id, second.id)
    self.assertEqual(len(queue.commands), 1)
```

- [ ] **Step 2: Run and verify failure**

Run: `python3 -m unittest tests.app_simulation_application_test -v`

Expected: FAIL because only `PrototypeSimulationApplication` exists and there is no list API.

- [ ] **Step 3: Generalize to formal Principal and keyset list**

```python
@dataclass(frozen=True)
class SimulationJobPage:
    items: tuple[SimulationJobView, ...]
    next_cursor: str | None

class SimulationApplication:
    def list_jobs(self, principal: Principal, cursor: str | None, limit: int = 20) -> SimulationJobPage:
        boundary = decode_job_cursor(cursor) if cursor else None
        bounded = min(max(int(limit), 1), 50)
        rows = self._repository.list_jobs(principal.user_id, boundary, bounded + 1)
        views = tuple(SimulationJobView(job=row, result=self._repository.get_result(principal.user_id, row.id)) for row in rows[:bounded])
        return SimulationJobPage(views, encode_job_cursor(rows[bounded - 1]) if len(rows) > bounded else None)
```

Keep a temporary `PrototypeSimulationApplication = SimulationApplication` alias only until Phase 6.

- [ ] **Step 4: Add owner-first SQL methods**

Every list/read query starts with `WHERE user_id = %s`; jobs order by `updated_at DESC, id DESC`; attempts are returned by `job_id` only after the owner-scoped job has been resolved.

- [ ] **Step 5: Run and commit**

```bash
python3 -m unittest tests.app_simulation_application_test tests.app_identity_repository_test -v
git add server/app/simulation/ports.py server/app/simulation/application.py \
  server/app/simulation/repository.py tests/app_simulation_application_test.py
git commit -m "feat: formalize owner-scoped SimC application"
```

### Task 2: Remove prototype defaults and enforce source/readiness truth

**Files:**
- Modify: `server/app/simulation/sources.py`
- Modify: `server/app/simulation/snapshots.py`
- Modify: `server/app/simulation/readiness.py`
- Modify: `server/app/simulation/compiler.py`
- Modify: `tests/app_simulation_sources_test.py`
- Modify: `tests/app_simulation_readiness_test.py`
- Modify: `tests/app_simulation_compiler_test.py`

**Interfaces:**
- Produces: `CharacterSnapshotCandidate` with explicit `missing_fields`, source provenance, raw SHA-256, and no guessed character fields; `ReadinessReport.ready` only for `READY_FOR_SIMC`.

- [ ] **Step 1: Write failing no-default tests**

```python
def test_missing_level_is_incomplete_not_default_90(self):
    candidate = adapter.resolve(source_without_level)
    self.assertEqual(candidate.readiness, SourceReadiness.INCOMPLETE_FOR_SIMC)
    self.assertIn("character.level", candidate.missing_fields)
    self.assertNotEqual(candidate.snapshot.get("level"), 90)

def test_missing_race_never_compiles_race_none(self):
    with self.assertRaisesRegex(SimcCompileError, "MISSING_RACE"):
        compiler.compile(snapshot_without_race, scenario)
```

- [ ] **Step 2: Run and verify the existing prototype-default behavior fails**

Run: `python3 -m unittest tests.app_simulation_sources_test tests.app_simulation_readiness_test tests.app_simulation_compiler_test -v`

- [ ] **Step 3: Delete `_prototype_character_level` and centralize required fields**

```python
REQUIRED_CHARACTER_PATHS = (
    "character.name", "character.region", "character.realm", "character.level",
    "character.class", "character.spec", "character.race", "talents.loadout", "gear.items",
)
```

Adapters normalize only source-present data. The readiness validator owns missing-field classification; the compiler accepts only a snapshot already marked `READY_FOR_SIMC` and rechecks actor and runtime identity.

- [ ] **Step 4: Verify WCL/Raider.IO failure distinctions**

Tests cover `INVALID_LINK`, `CHARACTER_NOT_FOUND`, `ACCESS_RESTRICTED`, `SNAPSHOT_UNAVAILABLE`, `INCOMPLETE_FOR_SIMC`, and `READY_FOR_SIMC` without collapsing them into one provider error.

- [ ] **Step 5: Run and commit**

```bash
python3 -m unittest tests.app_simulation_sources_test tests.app_simulation_readiness_test tests.app_simulation_compiler_test -v
git add server/app/simulation/sources.py server/app/simulation/snapshots.py \
  server/app/simulation/readiness.py server/app/simulation/compiler.py \
  tests/app_simulation_sources_test.py tests/app_simulation_readiness_test.py tests/app_simulation_compiler_test.py
git commit -m "fix: remove guessed SimC source defaults"
```

### Task 3: Lease-safe Worker and semantic result publication

**Files:**
- Modify: `server/app/simulation/worker.py`
- Modify: `server/app/worker/leases.py`
- Modify: `server/app/worker/handlers.py`
- Modify: `server/app/worker/main.py`
- Modify: `tests/app_simulation_worker_test.py`
- Modify: `tests/app_worker_lease_test.py`
- Modify: `tests/app_worker_runtime_test.py`
- Create: `tests/app_simc_result_semantics_test.py`

**Interfaces:**
- Produces: exactly one immutable `SimulationResult` per job; attempts remain append-only; terminal queue acknowledgment occurs only after job/result transaction commits.

- [ ] **Step 1: Write failing semantic and duplicate-delivery tests**

```python
def test_exit_zero_race_none_is_failed_without_result(self):
    status = worker.handle(lease, execution="Player: Test race=none\nDPS=12345")
    self.assertEqual(status, SimulationJobStatus.FAILED)
    self.assertEqual(repository.job.public_error_code, "SIMC_ACTOR_INVALID")
    self.assertEqual(repository.results, [])

def test_duplicate_queue_delivery_keeps_one_result(self):
    worker.handle(lease)
    worker.handle(lease)
    self.assertEqual(len(repository.results), 1)
    self.assertEqual(repository.attempts[-1].diagnostic, "ALREADY_TERMINAL")
```

- [ ] **Step 2: Run and verify failure**

Run: `python3 -m unittest tests.app_simulation_worker_test tests.app_worker_lease_test tests.app_worker_runtime_test tests.app_simc_result_semantics_test -v`

- [ ] **Step 3: Enforce semantic result gates**

The parser requires a non-placeholder actor, supported race/class/spec, finite positive metric, expected scenario, matching profile SHA, compiler revision, runtime revision, and no fatal diagnostics. Persist only normalized metric/provenance; truncate bounded public diagnostic and discard stdout/stderr.

- [ ] **Step 4: Make terminal handling idempotent**

Lock the job row, return `ALREADY_TERMINAL` for succeeded/failed/cancelled, create attempt N once, and commit result plus succeeded job state before acknowledging the queue lease. Lost lease before commit produces retryable failure; lost lease after terminal commit reads the terminal job and does not rerun SimC.

- [ ] **Step 5: Run and commit**

```bash
python3 -m unittest tests.app_simulation_worker_test tests.app_worker_lease_test \
  tests.app_worker_runtime_test tests.app_simc_result_semantics_test -v
git add server/app/simulation/worker.py server/app/worker \
  tests/app_simulation_worker_test.py tests/app_worker_lease_test.py \
  tests/app_worker_runtime_test.py tests/app_simc_result_semantics_test.py
git commit -m "feat: publish only semantic SimC results"
```

### Task 4: Formal SimC API and typed shared client

**Files:**
- Create: `server/app/api/routes/simc.py`
- Modify: `server/app/api/routes/__init__.py`
- Modify: `server/app/api/dependencies.py`
- Modify: `server/app/main.py`
- Create: `tests/app_simc_api_test.py`
- Create: `tests/app_simc_cross_client_test.py`
- Create: `packages/domain/src/simc.ts`
- Create: `packages/domain/src/simc.test.ts`
- Create: `packages/api-client/src/simc.ts`
- Create: `packages/api-client/src/simc.test.ts`
- Modify: package indexes/clients.

**Interfaces:**
- Routes:
  - `POST /api/v2/simc/snapshots`
  - `GET /api/v2/simc/snapshots/{snapshot_id}`
  - `GET /api/v2/simc/jobs?cursor=&limit=`
  - `POST /api/v2/simc/jobs`
  - `GET /api/v2/simc/jobs/{job_id}`
- Produces TypeScript `SourceSnapshotView`, `SimulationJobSummary`, `SimulationJobDetail`, `SimulationResultView`, and `SimcClient`; all methods consume the Phase-3 `ClientAuthContext` unchanged.

- [ ] **Step 1: Write failing cross-client route and guard tests**

```python
def test_job_created_by_web_is_visible_to_mini_same_user(self):
    created = client.post("/api/v2/simc/jobs", cookies=web_cookies, headers=web_write_headers, json=payload)
    listed = client.get("/api/v2/simc/jobs", headers=mini_headers)
    self.assertIn(created.json()["id"], [row["id"] for row in listed.json()["items"]])

def test_other_user_cannot_read_job(self):
    self.assertEqual(client.get(f"/api/v2/simc/jobs/{job_id}", headers=other_headers).status_code, 404)
```

```ts
expect(isSimulationJobDetail({ ...validJob, userId: crypto.randomUUID() })).toBe(false)
```

- [ ] **Step 2: Run and verify missing routes/modules**

```bash
python3 -m unittest tests.app_simc_api_test tests.app_simc_cross_client_test -v
npm run test:taro -- packages/domain/src/simc.test.ts packages/api-client/src/simc.test.ts
```

- [ ] **Step 3: Implement bounded public payloads**

Snapshot responses expose source provider/key, readiness, bounded missing/blocker codes, fetched time, and safe provenance; job responses expose job/status/revisions/timestamps/public error, bounded attempts, and semantic result. They never expose owner, raw payload, source credentials, profile, stdout/stderr, worker ID, lease, or internal queue payload.

- [ ] **Step 4: Implement auth-neutral typed transport**

Mini supplies Bearer/credentials omit; Web supplies Cookie/credentials include and CSRF on POST. Validators reject internal fields and non-finite metrics.

- [ ] **Step 5: Run and commit**

```bash
python3 -m unittest tests.app_simc_api_test tests.app_simc_cross_client_test \
  tests.app_simulation_application_test tests.app_simulation_worker_test \
  tests.app_simc_result_semantics_test -v
npm run test:taro -- packages/domain/src/simc.test.ts packages/api-client/src/simc.test.ts
npm run typecheck
git add server/app/api server/app/main.py tests/app_simc_api_test.py tests/app_simc_cross_client_test.py \
  packages/domain/src/simc.ts packages/domain/src/simc.test.ts packages/domain/src/index.ts \
  packages/api-client/src/simc.ts packages/api-client/src/simc.test.ts \
  packages/api-client/src/index.ts packages/api-client/src/clients.ts
git commit -m "feat: expose formal cross-client SimC API"
```

### Task 5: Cloud candidate and Strict SimC evidence

**Files:**
- Create: `artifacts/releases/2026-09-02-chickenbro-simc-simc/requirement.json`
- Create: `artifacts/releases/2026-09-02-chickenbro-simc-simc/evidence.json`
- Create: `artifacts/releases/2026-09-02-chickenbro-simc-simc/manifest.json`
- Modify: `docs/project-state.json`

- [ ] **Step 1: Create a Strict requirement**

Require source failure distinctions, no guessed defaults, readiness/compiler gates, owner isolation, idempotent queue/worker/result, two-session shared history, typed client, candidate SimC runtime identity, rollback, and semantic result evidence.

- [ ] **Step 2: Run the full local matrix without local SimC execution**

```bash
python3 -m unittest tests.app_simulation_application_test tests.app_simulation_sources_test \
  tests.app_simulation_readiness_test tests.app_simulation_compiler_test \
  tests.app_simulation_worker_test tests.app_worker_lease_test tests.app_worker_runtime_test \
  tests.app_simc_result_semantics_test tests.app_simc_api_test tests.app_simc_cross_client_test -v
npm run test:taro -- packages/domain/src/simc.test.ts packages/api-client/src/simc.test.ts
npm run typecheck
```

- [ ] **Step 3: Deploy candidate and run one controlled cloud SimulationCraft job**

Record commit/deployed hashes, source snapshot/hash/provenance, readiness, compiled profile hash without profile content, Worker/lease identity, actual cloud runtime revision, semantic metric, result identity, same-user cross-client read, second-user denial, and rollback. A return code by itself is not evidence.

- [ ] **Step 4: Local CR and evidence sealing**

Reject guessed fields, legacy Catalog/Manifest/Resolver imports, raw provider/profile/output leakage, unscoped reads, duplicate results, or runtime identity mismatch. Write/check the Harness packet and commit.

```bash
git add artifacts/releases/2026-09-02-chickenbro-simc-simc docs/project-state.json
git commit -m "test: seal formal SimC evidence"
```

Phase 4 is complete when a real controlled cloud candidate run passes semantic gates and is visible through both session transports; production is still not cut over.
