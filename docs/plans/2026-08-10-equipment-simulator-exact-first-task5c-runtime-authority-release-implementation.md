# Exact-first Task 5C Runtime Authority Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax. This task has one sequential database/runtime owner; do not dispatch parallel implementers.

**Goal:** Publish a bounded server-owned Runtime Authority Release so the existing Exact SimC API creates v3 loadouts, snapshots and jobs only when the saved source, effect occurrences and eight runtime revisions all rehydrate exactly.

**Architecture:** A pure owner seals/reloads resolver-context, runtime-release and occurrence-index documents. A PostgreSQL-only store persists one source-binding membership and release-scoped occurrence rows. The existing materializer reads that release after 0033 source replay, creates v3 identities, and the worker rehydrates the same release/context/snapshot/job triple; no UI-visible surface or mutable pointer participates.

**Tech Stack:** Python 3 stdlib, canonical document owners, PostgreSQL migration/functions/roles, `unittest`, repository Harness; existing Taro source unchanged.

## Global Constraints

- Base is the current Task 5A foundation branch; do not edit root-worktree WIP.
- Do not use local PostgreSQL, download/install dependencies, modify Catalog/Manifest/generation 35, start observation/backfill, or change current UI route/JSX/SCSS/copy/navigation.
- `0030`--`0034`, v1/v2 canonical bytes/key/hash and archived Task 3A/3B/4W evidence are immutable. `0035` is forward-only and adds v3 only.
- Runtime reads no active/latest pointer, Cache compatibility context, client authority, Catalog membership, latest row or process default. Zero/multiple/drift returns literal blocked/unsupported.
- No raw profile/player/realm/server/user UUID enters release/context/index, loadout/snapshot/job/result/log/public envelope. Release/context keys stay server-internal.
- Candidate is one low-priority, capacity-preflighted cloud-only disposable PostgreSQL fresh/upgrade run after local TDD, independent CR and exact final head. Production only follows candidate, CI, Harness and user acceptance gates.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `server/exact_runtime_authority_release.py` | Canonical schemas plus seal/reload/verify of release/context/index documents and release-bound effect-record lookup contract. |
| `server/exact_runtime_authority_release_store.py` | PostgreSQL-only admission/read owner; never builds a release from runtime state. |
| `server/migrations/postgres/0035_websim_exact_runtime_authority_release.sql` | Append-only release/index tables, v3 constraint compatibility and least-privilege functions. |
| `server/gear_resolved_loadout.py`, `server/simulation_snapshot.py` | V3 builders/verifiers that bind release/context/vector without modifying v2. |
| `server/simulation_snapshot_store.py`, `server/gear_exact_import_job_store.py`, `server/gear_exact_authority_worker.py` | V3 persistence, request rehydration and execution only for the sealed triple. |
| `server/exact_simc_api.py`, `server/news_backend.py` | Server-only release provider composition and narrow Exact route enablement. |

## Task 1: Canonical Runtime Authority Release Owner

**Files:**
- Create: `server/exact_runtime_authority_release.py`, `tests/exact_runtime_authority_release_test.py`
- Modify: `server/gear_loadout_effect_authority.py`, `tests/gear_loadout_effect_authority_test.py`, `docs/project-owner-map.json`, `docs/backend-owner-map.json`, `tests/gear_canonical_owner_gate_test.py`

**Interfaces:**
- Consumes: `SealedCanonicalDocument`, `reload_effect_record`, Task 4L `loadout_effect_subject_signatures` and `resolve_loadout_effect_authority`, eight-key `DEPENDENCY_VECTOR_KEYS`.
- Produces: `seal_runtime_resolver_context`, `reload_runtime_resolver_context`, `seal_runtime_authority_release`, `reload_runtime_authority_release`, `seal_runtime_occurrence_index_entry`, `reload_runtime_occurrence_index_entry`, `resolve_release_effect_records`.

- [x] **Step 1: Write the failing pure-contract tests**

```python
def test_release_rejects_missing_or_extra_dependency_vector_keys(self):
    result = seal_runtime_authority_release({"seasonRevision": "s1"}, context)
    self.assertEqual(result.status, "blocked")

def test_occurrence_entry_reloads_only_same_release_subject_record_and_hash(self):
    entry = sealed_occurrence_entry(release, subject, record)
    self.assertEqual(reload_runtime_occurrence_index_entry(entry.canonical_bytes, entry.content_key).content_key, entry.content_key)

def test_task4l_exports_ordered_subject_variant_signatures(self):
    self.assertEqual(
        loadout_effect_subject_signatures(first_pass_snapshot),
        tuple(record.subject_variant_signature for record in expected_records),
    )
```

- [x] **Step 2: Run RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.exact_runtime_authority_release_test`

Expected: FAIL because the module does not exist.

- [x] **Step 3: Implement the minimal pure owner**

```python
def resolve_release_effect_records(release, snapshot, index_rows, record_loader):
    required_variants = tuple(descriptor.subject_variant_signature for descriptor in snapshot.effect_descriptors)
    indexed = {}
    for row in index_rows:
        if row.runtime_authority_release_key != release.content_key:
            raise RuntimeAuthorityReleaseIntegrityError("release drift")
        if row.subject_variant_signature in indexed:
            raise RuntimeAuthorityReleaseIntegrityError("multiple rows for descriptor")
        indexed[row.subject_variant_signature] = row
    if set(indexed) != set(required_variants):
        raise RuntimeAuthorityReleaseIntegrityError("index does not exactly cover descriptors")
    records = []
    for signature in required_variants:
        row = indexed[signature]
        record = record_loader(row.effect_record_key)
        if record.content_key != row.effect_record_key or sha256(record.canonical_bytes).hexdigest() != row.effect_record_sha256:
            raise RuntimeAuthorityReleaseIntegrityError("effect record substitution")
        records.append(record)
    return tuple(records)
```

The actual owner must also typed-reload each row/record and compare its runtime/vector fields before returning. It calls the public Task 4L ordered-signature witness rather than importing private descriptor helpers or recomputing signatures. Unknown is unsealable, duplicate ordinals remain, and release/context keys never enter public data.

- [x] **Step 4: Run GREEN and owner gate**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.exact_runtime_authority_release_test tests.gear_loadout_effect_authority_test tests.gear_canonical_owner_gate_test`

Expected: PASS; v1/v2 owners retain original imports/bytes.

- [x] **Step 5: Commit**

```bash
git add server/exact_runtime_authority_release.py server/gear_loadout_effect_authority.py tests/exact_runtime_authority_release_test.py tests/gear_loadout_effect_authority_test.py docs/project-owner-map.json docs/backend-owner-map.json tests/gear_canonical_owner_gate_test.py
git commit -m "feat(exact): seal runtime authority releases"
```

## Task 2: Append-only 0035 Release and Index Persistence

**Files:**
- Create: `server/migrations/postgres/0035_websim_exact_runtime_authority_release.sql`, `server/exact_runtime_authority_release_store.py`, `tests/exact_runtime_authority_release_store_test.py`
- Modify: `server/gear_exact_authority_store.py`, `tests/gear_exact_authority_store_test.py`, `tests/postgres_schema_test.py`, `tests/postgres_integration_test.py`

**Interfaces:**
- Consumes: Task 1 documents, 0030 effect record rows, 0033 binding key and owner scope.
- Produces: `RuntimeAuthorityReleaseStore.admit`, `read_unique_for_binding`, `read_occurrences`, `load_effect_records`.

- [x] **Step 1: Write failing store and schema tests**

```python
def test_read_unique_for_binding_blocks_zero_or_multiple_release_memberships(self):
    with self.assertRaises(RuntimeAuthorityReleaseIntegrityError):
        self.store.read_unique_for_binding(OWNER, BINDING)

def test_0035_gives_app_and_worker_no_release_table_dml(self):
    self.assert_schema_has_no_direct_dml("wow_app", "ops.websim_exact_runtime_authority_releases")
```

- [x] **Step 2: Run RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.exact_runtime_authority_release_store_test tests.postgres_schema_test`

Expected: FAIL because 0035/store functions do not exist.

- [x] **Step 3: Implement 0035 and store**

`0035` adds append-only release/context/index tables, FKs to 0030 records and 0033 bindings, reject-update/delete/truncate triggers, and `wow_migrator`-owned admission/read functions. Python typed-reloads all inputs before one transaction/readback; it does not query Catalog, `latest`, or compatibility context.

- [x] **Step 4: Run GREEN**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.exact_runtime_authority_release_store_test tests.gear_exact_authority_store_test tests.postgres_schema_test tests.postgres_integration_test`

Expected: PASS locally; PostgreSQL fresh/upgrade remains candidate-only.

- [x] **Step 5: Commit**

```bash
git add server/migrations/postgres/0035_websim_exact_runtime_authority_release.sql server/exact_runtime_authority_release_store.py server/gear_exact_authority_store.py tests/exact_runtime_authority_release_store_test.py tests/gear_exact_authority_store_test.py tests/postgres_schema_test.py tests/postgres_integration_test.py
git commit -m "feat(exact): persist runtime authority releases"
```

## Task 3: Forward-only v3 Loadout, Snapshot and Request Identity

**Files:**
- Modify: `server/gear_resolved_loadout.py`, `tests/gear_resolved_loadout_test.py`
- Modify: `server/simulation_snapshot.py`, `tests/simulation_snapshot_test.py`, `tests/simulation_snapshot_compat_test.py`
- Modify: `server/simulation_snapshot_store.py`, `tests/simulation_snapshot_store_test.py`
- Modify: `server/gear_exact_import_job_store.py`, `tests/gear_exact_import_job_store_test.py`
- Modify: `server/migrations/postgres/0035_websim_exact_runtime_authority_release.sql`, `tests/postgres_schema_test.py`, `tests/postgres_integration_test.py`

**Interfaces:**
- Consumes: Task 1 release/context and Task 4L verified aggregate.
- Produces: `build_resolved_loadout_v3`, `verify_resolved_loadout_v3`, `build_simulation_snapshot_v3`, `verify_simulation_snapshot_v3`, `exact-import-job-request-v3` with a typed release reference.

- [x] **Step 1: Add RED identity cases**

```python
def test_v3_snapshot_key_changes_when_only_runtime_release_key_changes(self):
    self.assertNotEqual(build_v3("release-a")["simulationSnapshotKey"], build_v3("release-b")["simulationSnapshotKey"])

def test_v1_and_v2_request_bytes_are_unchanged_when_v3_is_added(self):
    self.assertEqual(build_v2_request(), FROZEN_V2_REQUEST)
```

- [x] **Step 2: Run RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.gear_resolved_loadout_test tests.simulation_snapshot_test tests.simulation_snapshot_store_test tests.gear_exact_import_job_store_test`

Expected: FAIL only on missing v3 builders/schema acceptance.

- [x] **Step 3: Add v3 beside v1/v2**

V3 loadout/snapshot/request bytes and row hashes contain `runtimeAuthorityReleaseKey`, `resolverContextKey`, and exactly eight dependency vector fields. 0035 extends 0031/0034 validators forward-only for v1/v2/v3; v3 rejects v2 prefixes. Snapshot store runs v3 verifier before returning a row.

- [x] **Step 4: Run GREEN compatibility matrix**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.gear_resolved_loadout_test tests.simulation_snapshot_test tests.simulation_snapshot_compat_test tests.simulation_snapshot_store_test tests.gear_exact_import_job_store_test tests.postgres_schema_test`

Expected: PASS; v1/v2 fixtures retain original key/bytes.

- [x] **Step 5: Commit**

```bash
git add server/gear_resolved_loadout.py server/simulation_snapshot.py server/simulation_snapshot_store.py server/gear_exact_import_job_store.py server/migrations/postgres/0035_websim_exact_runtime_authority_release.sql tests/gear_resolved_loadout_test.py tests/simulation_snapshot_test.py tests/simulation_snapshot_compat_test.py tests/simulation_snapshot_store_test.py tests/gear_exact_import_job_store_test.py tests/postgres_schema_test.py tests/postgres_integration_test.py
git commit -m "feat(exact): bind v3 snapshots to runtime releases"
```

## Task 4: Materializer, Worker and HTTP Enablement

**Files:**
- Modify: `server/exact_simc_api.py`, `tests/exact_simc_api_test.py`
- Modify: `server/gear_exact_authority_worker.py`, `tests/gear_exact_authority_worker_test.py`
- Modify: `server/news_backend.py`, `tests/news_backend_test.py`

**Interfaces:**
- Consumes: unique release reader, v3 builders, server source/profile readers and 0032 job store.
- Produces: enabled `exact_simc_api_for_authenticated_user()` only under sealed release composition; v3-only worker execution.

- [x] **Step 1: Write failing runtime tests**

```python
def test_materializer_rejects_release_vector_context_or_occurrence_drift_before_enqueue(self):
    self.assertEqual(materializer(request, OWNER_HASH)["status"], "blocked")

def test_worker_marks_v2_job_unsupported_and_executes_only_v3_release_bound_snapshot(self):
    self.assertEqual(process(v2_claim)["classification"], "unsupported")
```

- [x] **Step 2: Run RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.exact_simc_api_test tests.gear_exact_authority_worker_test tests.news_backend_test`

Expected: FAIL because provider composition and v3 execution do not exist.

- [x] **Step 3: Implement server-only composition**

Materializer order is source-replay → unique-release-read → first-pass resolve → release-index record reload → Task 4L aggregate → final resolve → v3 loadout/snapshot/job. Backend instantiates only explicit server stores; any unavailable component returns existing fail-closed envelope. Worker reloads v3 request release/context/snapshot, compares every key/vector, and never runs v1/v2 or arbitrary profile.

- [x] **Step 4: Run GREEN**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.exact_simc_api_test tests.gear_exact_authority_worker_test tests.news_backend_test tests.gear_exact_import_job_store_test tests.simulation_snapshot_store_test`

Expected: PASS with ready only for injected complete-release fixtures; incomplete/live-unavailable cases remain blocked.

- [ ] **Step 5: Commit**

```bash
git add server/exact_simc_api.py server/gear_exact_authority_worker.py server/news_backend.py tests/exact_simc_api_test.py tests/gear_exact_authority_worker_test.py tests/news_backend_test.py
git commit -m "feat(exact): execute release-bound v3 simulations"
```

## Task 5: Whole-branch Evidence, Candidate and Production Handoff

**Files:**
- Modify: `tests/postgres_integration_test.py`
- Modify: `docs/postgres-identity-migration-runbook.md`, `docs/verification-matrix.md`, `docs/plans/README.md`, `docs/roadmap.md`, `docs/plans/2026-08-04-equipment-simulator-exact-first-persistence-resequence.md`, `docs/plans/2026-08-07-equipment-simulator-exact-first-task5a-api-runtime.md`, `docs/plans/2026-08-07-equipment-simulator-exact-first-task5b-active-authority-source.md`, this plan
- Create/Modify: `artifacts/releases/2026-08-10-equipment-simulator-exact-first-task5c-runtime-authority-release/evidence.json`, `artifacts/releases/2026-08-10-equipment-simulator-exact-first-task5c-runtime-authority-release/manifest.json`

- [x] **Step 1: Run whole local verification and CR**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p '*_test.py'`

Run: `node scripts/project-harness.js --check --requirement-file artifacts/releases/2026-08-10-equipment-simulator-exact-first-task5c-runtime-authority-release/requirement.json --evidence-file artifacts/releases/2026-08-10-equipment-simulator-exact-first-task5c-runtime-authority-release/evidence.json --manifest-file artifacts/releases/2026-08-10-equipment-simulator-exact-first-task5c-runtime-authority-release/manifest.json --base origin/main`

Expected: local evidence cannot claim candidate/production/manual acceptance.

- [x] **Step 1a: Add the cloud-only candidate harness with RED/GREEN evidence**

The existing `Task5CV3MigrationBoundaryTest` is static only and cannot prove the
candidate gate.  Add one opt-in `0035` runner in
`tests/postgres_integration_test.py` which accepts only a new lowercase run id,
two distinct pre-provisioned disposable fresh/upgrade DSNs and distinct
migrator/app/worker DSNs.  It must first prove both databases are empty and
correctly commented, apply `0001..0035` versus `0001..0034 -> 0035`, and use
only the repository's sealed-document stores/functions to prove one release
admission/readback, zero/multiple membership fail-closed, exact occurrence
readback, V3 request/snapshot worker checks, v1/v2 non-execution, function ACLs,
provider-disable rollback and no asynchronous backflow.  It must never create,
drop or reset databases/roles, and must emit one redacted commit/tree/0035-hash
attestation only after rechecking the clean source identity and both database
identities.

Run RED: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.postgres_integration_test.Task5CCandidateHarnessTest`

Expected: FAIL because the Task 5C explicit candidate configuration and real
candidate class do not yet exist.

Run GREEN: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.postgres_integration_test.Task5CCandidateHarnessTest tests.postgres_integration_test.Task5CV3MigrationBoundaryTest`

Expected: PASS locally with the real candidate class skipped while no Task 5C
cloud DSNs are configured; the harness-contract test must pass and no local
PostgreSQL connection is attempted.

Completed locally: the RED path failed first on the missing Task 5C attestation
and runner; the GREEN contract suite passes with the cloud runner skipped when
no Task 5C DSNs are present. The runner itself remains candidate-only and does
not constitute a cloud, production, provider, worker, or player-loop result.

- [ ] **Step 2: Run one final-head cloud candidate**

Preflight remote disk/CPU/memory. Use fresh named disposable PostgreSQL fresh `0001..0035` and upgrade `0001..0034 -> 0035` databases with distinct redacted roles. Prove release admission/reload, zero/multiple relation block, v3 job/worker, v1/v2 stability, route ready/blocked/unsupported, no async backflow and provider-disable rollback. Archive exact commit/tree before deleting only those named resources.

The first candidate `t5c260810033244` on `3afb3660` / tree
`74e70769613772e4c75e2a7e80e7593b2ea22c72` reached `0035` in both
disposable databases but failed before attestation because frozen `0033` used
the ambiguous `ON CONFLICT (binding_key)` inside a `RETURNS TABLE(binding_key
...)` PL/pgSQL function. Its log SHA-256 is
`59a2e26a52fc2a3ac3f8448b24590456d810a3c01ab068db80a2ac65cf1da20a`.
The forward-only `0035` repair at `71a83b7c` replaces that function with the
named primary-key conflict target while preserving `0030--0034` bytes. The
failed databases, role and temporary remote material were identity-checked and
discarded; they are non-reusable. This checkbox remains open: one new run-id
on the repaired final runtime head is still required and must not treat the
failed run as candidate evidence.

The second candidate `t5c2608101217a9` bound the repaired final head
`d426fbc6` / tree `5af4b178421f2295cfaaa6336d9cb2c669b40254`. Its initial
runner log-open was refused before Python started (the preserved empty log has
SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`);
both exact-commented databases were then independently proven empty before the
sole actual candidate execution. Fresh and upgrade both reached 35 migrations,
but the binding admission transaction failed before attestation because frozen
`0033`'s `verify_websim_exact_template_authority_binding_relations` trigger
directly reads the protected binding table as `wow_app`. The actual candidate
log SHA-256 is
`d887db68c4019f3b29fd86fbc6fa62b659878d65d58a07fdf6c1eb6ca4c64224`.
This is a distinct forward-only compatibility defect, not a candidate success
or retry authorization. After this identity archive, its two databases,
candidate role, remote source, bundle, logs and 0600 credential material were
discarded and independently rechecked absent; the inactive worker and production
state were not changed. A new final-head candidate remains required after any
forward repair; this checkbox remains open.

The follow-on forward-only repair `0ca0619b` keeps `0030--0034` verbatim and
changes only `0035`: it converts the frozen binding-relation validator to
`SECURITY DEFINER`, explicitly assigns it to `wow_migrator`, preserves the
frozen fixed search path, and revokes direct execution from public/app/worker
principals. Its 0035 SHA-256 is
`6aef914d618433913314711388d4093d6905c61ea9ea445d33267f2e579e7064`.
The RED/GREEN schema regression, focused 58-test schema/candidate contract, and
the full local suite (`2964` tests, `OK`, 5 expected cloud-only skips) pass.
This proves only local repair; it changes runtime migration bytes, so one brand
new final-head candidate remains mandatory and the prior runs remain unusable.

The third candidate `t5c2608101210d3` bound final head `80f484f8` / tree
`ab83d4e495c25cc5f207fb4b23de0a7a7ed760f7`, reached 35 migrations on both
paths, and then failed before attestation because the candidate test passed
`seal_runtime_occurrence_index_entry(...).document` to a store that correctly
requires the sealed entry. Its log SHA-256 is
`36129af925c05b64377498279c18d05ffc370ff58edb2d37205b48bd9b1135cf`.
This candidate harness fixture error must be repaired with TDD; it invalidates
this run and requires another new final-head candidate. Its exact disposable
resources were identity-archived, discarded and rechecked absent before that
repair; production state and the inactive worker were not changed.

The candidate-harness repair `a14f6c47` follows RED/GREEN: it keeps the sealed
occurrence entry returned by `seal_runtime_occurrence_index_entry` instead of
unwrapping `.document`, and adds a runner-source regression assertion. It has
no migration or UI change. The full local suite passes with `2965` tests and 5
expected cloud-only skips, but the candidate test source changed; a brand-new
final-head candidate remains mandatory and all three prior run ids stay unusable.

- [ ] **Step 3: Review, CI and production only after candidate PASS**

Run final CR/Harness at exact candidate head, publish one implementation PR, require exact-head CI, then apply reviewed `0030..0035` and provider/worker enablement per runbook. Record main/origin/cloud parity, no timer/backflow, API/readback and rollback. Never create a CI-only PR.

- [ ] **Step 4: Existing-page user acceptance and closure**

On unchanged `simc_submit`, record complete release-bound ready/result, missing-authority blocked/no task, unsupported blocked/no task, and v3 task/result readback. Only explicit post-test user acceptance permits closure and post-merge WeChat refresh/cleanup.

## Plan Self-Review

- Tasks 1--2 implement immutable release/context/index and ACL; Task 3 propagates identity; Task 4 composes provider/worker/HTTP; Task 5 owns candidate/production/real-WeChat gates.
- Every task has exact files, interfaces, RED/GREEN command and commit boundary. Candidate resources remain unnamed until final head for disposal safety.
- `runtimeAuthorityReleaseKey`, `resolverContextKey` and the eight-field vector are the same server-only v3 relation in Tasks 1--4; public envelopes remain unchanged.
