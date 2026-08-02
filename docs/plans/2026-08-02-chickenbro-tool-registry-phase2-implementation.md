# Chickenbro Tool Registry Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Subagent dispatch is not authorized for this session.

**Goal:** Replace Chickenbro's fixed Raider.IO/Warcraft Logs Tool selection with a PostgreSQL-backed immutable Tool Registry Release while preserving current answers, evidence, owner and source boundaries.

**Architecture:** Pure Registry validation and discovery live in `server/chickenbro_registry.py`; PostgreSQL `ops` tables own immutable manifests and one active release; a bounded runtime adapter maps only two approved implementation refs to existing Tool builders. `news_backend.py` orchestrates the snapshot and existing answer chain, while Trace v2 records Registry identity and discovered-versus-selected capabilities without rewriting Trace v1.

**Tech Stack:** Python 3 standard library, `unittest`, PostgreSQL/psycopg, existing `wow-backend`, existing Raider.IO and Warcraft Logs adapters, Project Harness, systemd.

状态：`正在推进`
分类：`Strict`
确认日期：2026-08-02

设计入口：[Phase 2 Tool Registry 设计](2026-08-02-chickenbro-tool-registry-phase2-design.md)

## Global Constraints

- Initial Registry Release contains exactly `source:raiderio:v1` and `source:warcraftlogs:v1`.
- Personal templates and SimC remain context evidence and are not registered as Tools.
- Registry drives discovery only; execution remains bound to repository-owned approved adapters.
- No dynamic import, arbitrary Python, SQL, Shell, URL, credential or owner value may come from a manifest, model or client.
- No CapabilityGap, Toolsmith, candidate generation, shadow, canary, promotion, frontend or answer-policy change is allowed.
- Runtime role has read-only Registry privileges; only migration/release ownership writes Registry rows.
- Registry unavailable or invalid never falls back to the old fixed allowlist.
- P1 Trace v1 remains readable; new Registry-backed requests write Trace v2 only.
- No dependencies, third-party downloads or new services are introduced.

## File and owner map

| File | Responsibility |
| --- | --- |
| `server/chickenbro_registry.py` | Pure Manifest/Release canonicalization, hash validation and deterministic discovery |
| `server/chickenbro_tool_runtime.py` | 60-second verified snapshot cache and approved adapter dispatch |
| `server/migrations/postgres/0025_chickenbro_tool_registry.sql` | Immutable Manifest/Release tables, initial release and least-privilege grants |
| `server/postgres_ops_store.py` | Transactional active Registry Release read |
| `server/news_backend.py` | RequestIntent orchestration, Registry loading, ToolResult wiring and health projection |
| `server/chickenbro_observability.py` | Trace v1 compatibility and Registry Trace v2/projection |
| `tests/chickenbro_registry_test.py` | Pure schema, hash and discovery contracts |
| `tests/chickenbro_tool_runtime_test.py` | Cache, binding and execution contracts |
| `tests/postgres_ops_store_test.py` | Active release query/row projection |
| `tests/postgres_schema_test.py` | 0025 constraints, seed and privileges |
| `tests/chickenbro_agent_test.py` | Old/new ToolResult parity and backend selection behavior |
| `tests/chickenbro_observability_test.py` | Trace v1 compatibility and v2 Registry facts |
| `tests/chickenbro_eval_test.py` | v2 offline projection behavior |
| `tests/news_backend_test.py` | End-to-end Registry-backed session, failure and health behavior |

---

### Task 1: Add pure immutable Manifest and Registry Release contracts

**Files:**
- Create: `server/chickenbro_registry.py`
- Create: `tests/chickenbro_registry_test.py`

**Interfaces:**
- Produces: `canonical_json(value) -> str`, `manifest_content_hash(manifest) -> str`, `registry_release_hash(manifest_refs) -> str`, `validate_chickenbro_tool_manifest(manifest) -> dict`, `validate_chickenbro_registry_release(release) -> dict`, and `discover_chickenbro_capabilities(release, request_intent, request_context) -> dict`.
- Consumers: Tasks 2-5.

- [ ] **Step 1: Write failing Manifest and Release validation tests**

Create two valid manifest fixtures in the test module. The Raider.IO fixture must use:

```python
{
    "toolId": "source:raiderio:v1",
    "version": "1.0.0",
    "kind": "tool",
    "namespace": "source",
    "purpose": "Load bounded Raider.IO specialization evidence.",
    "inputSchema": {"required": ["classKey", "specKey"]},
    "outputSchema": {"schemaRevision": "chickenbro-tool-result-v1"},
    "discoveryPolicy": {
        "requestKinds": ["community_build"],
        "requiredContextFields": ["classKey", "specKey"],
        "productPhases": ["retail", "ptr"],
        "regions": ["cn", "global", "us", "eu", "kr", "tw"],
        "priority": 100,
    },
    "riskClass": "read_only",
    "sideEffects": [],
    "ownerPolicy": "public_source",
    "sourcePolicy": {"sourceKey": "raiderio", "requiredStatuses": ["synced", "partial"]},
    "freshnessPolicy": {"maxAgeSeconds": 86400, "staleBehavior": "limitation_only"},
    "timeoutBudgetMs": 3000,
    "costBudget": {"status": "bounded_existing_runtime"},
    "implementationRef": "chickenbro.source.raiderio.v1",
    "evalRefs": ["chickenbro-eval:verified_source_success"],
    "status": "active",
    "provenance": {"kind": "repository_migration", "revision": "0025"},
    "createdAt": "2026-08-02T00:00:00+00:00",
}
```

The WCL fixture differs only in identity, `requestKinds=["personal_wcl"]`, `requiredContextFields=["wclReport"]`, `ownerPolicy="owner_bound_report"`, source key, freshness policy, implementation ref and Eval ref. Tests must assert:

```python
validated = validate_chickenbro_tool_manifest(with_hash(RAIDERIO_MANIFEST))
self.assertEqual("source:raiderio:v1", validated["toolId"])
self.assertRaisesRegex(ValueError, "unknown manifest keys", validate_chickenbro_tool_manifest, {**validated, "python": "evil"})
self.assertRaisesRegex(ValueError, "implementationRef", validate_chickenbro_tool_manifest, {**validated, "implementationRef": "python:os.system"})
self.assertRaisesRegex(ValueError, "contentHash", validate_chickenbro_tool_manifest, {**validated, "purpose": "mutated"})
```

Build one release with ordered refs and assert duplicate IDs, missing hash, unknown status and changed `releaseHash` fail closed.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
python -m unittest tests.chickenbro_registry_test -v
```

Expected: `ModuleNotFoundError: No module named 'server.chickenbro_registry'`.

- [ ] **Step 3: Implement exact-key validation and canonical hashes**

Use `json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))` and SHA-256. `contentHash` is calculated from the manifest without `contentHash`; `releaseHash` is calculated only from ordered `manifestRefs`. Enforce the two approved Tool IDs and implementation refs, exact manifest keys, exact release keys, non-empty semantic version, ISO timezone timestamps, positive timeout, `kind=tool`, `namespace=source`, `riskClass=read_only`, empty side effects, and `status in {active, disabled}`.

- [ ] **Step 4: Write failing deterministic discovery tests**

Cover this exact matrix:

```text
personal_wcl + wclReport -> discover/select WCL only
community_build + classKey + specKey -> discover/select Raider.IO only
community_build missing specKey -> no selection, missingContextFields=[specKey]
general -> no selection
unknown productPhase or region -> no selection
disabled manifest -> entire referenced release invalid
```

The result contract is:

```python
{
    "registryVersion": "chickenbro-tools-1",
    "registryReleaseHash": "sha256:...",
    "discoveredCapabilityIds": [],
    "selectedCapabilityIds": [],
    "selectedManifests": [],
    "missingContextFields": [],
}
```

- [ ] **Step 5: Implement deterministic discovery and verify GREEN**

Discovery must sort by numeric `priority` descending, then `toolId`; selected manifests are defensive copies. Run:

```powershell
python -m unittest tests.chickenbro_registry_test -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit the pure Registry contract**

```powershell
git add server/chickenbro_registry.py tests/chickenbro_registry_test.py
git commit -m "feat(chickenbro): define immutable tool registry contracts"
```

---

### Task 2: Persist the immutable initial Registry Release in PostgreSQL

**Files:**
- Create: `server/migrations/postgres/0025_chickenbro_tool_registry.sql`
- Modify: `server/postgres_ops_store.py`
- Modify: `tests/postgres_schema_test.py`
- Modify: `tests/postgres_ops_store_test.py`

**Interfaces:**
- Consumes: Task 1 manifest/release validators.
- Produces: `PostgresOpsStore.load_active_chickenbro_registry_release() -> dict`.

- [ ] **Step 1: Write failing schema tests**

Add `CHICKENBRO_TOOL_REGISTRY = ROOT / "server" / "migrations" / "postgres" / "0025_chickenbro_tool_registry.sql"`. Assert normalized SQL contains:

```text
CREATE TABLE IF NOT EXISTS ops.chickenbro_tool_manifests
PRIMARY KEY (tool_id, version)
CREATE TABLE IF NOT EXISTS ops.chickenbro_tool_registry_releases
CREATE UNIQUE INDEX IF NOT EXISTS chickenbro_tool_registry_one_active
WHERE status = 'active'
REFERENCES ops.chickenbro_tool_manifests (tool_id, version)
GRANT SELECT ON ops.chickenbro_tool_manifests TO wow_app
GRANT SELECT ON ops.chickenbro_tool_registry_releases TO wow_app
REVOKE INSERT, UPDATE, DELETE
0025_chickenbro_tool_registry
source:raiderio:v1
source:warcraftlogs:v1
```

Also assert the seed includes deterministic content/release hashes and exactly two manifest rows.

- [ ] **Step 2: Run schema test and verify RED**

```powershell
python -m unittest tests.postgres_schema_test.PostgresSchemaTest.test_chickenbro_tool_registry_migration_is_immutable_and_read_only -v
```

Expected: missing 0025 file or constant.

- [ ] **Step 3: Create migration 0025**

Store each complete manifest as JSONB plus indexed identity/hash columns. Store `manifest_refs_json` and `release_hash` on the release row. Use CHECK constraints for hash prefix, statuses and non-empty IDs; use one partial unique active index. Seed exact canonical JSON produced by Task 1 and insert the migration ledger row idempotently. Revoke write privileges from `wow_app` after granting SELECT.

- [ ] **Step 4: Write failing Ops store projection test**

Use the existing fake cursor/connection style and return one release row followed by two manifest rows. Assert one transaction, ordered refs and validation:

```python
release = store.load_active_chickenbro_registry_release()
self.assertEqual("chickenbro-tools-1", release["registryVersion"])
self.assertEqual(
    ["source:raiderio:v1", "source:warcraftlogs:v1"],
    [item["toolId"] for item in release["manifests"]],
)
self.assertNotIn("credential", json.dumps(release).lower())
```

- [ ] **Step 5: Implement one transactional active-release read**

`load_active_chickenbro_registry_release` must query the single active row, then fetch exact `(tool_id, version)` pairs. It returns raw JSON projections to Task 1 validation and raises `KeyError("active chickenbro registry release not found")` for zero rows or `RuntimeError("multiple active chickenbro registry releases")` for multiple rows. It must not write, lock for update or activate a release.

- [ ] **Step 6: Run PostgreSQL contract tests and commit**

```powershell
python -m unittest tests.postgres_schema_test tests.postgres_ops_store_test tests.chickenbro_registry_test -v
git add server/migrations/postgres/0025_chickenbro_tool_registry.sql server/postgres_ops_store.py tests/postgres_schema_test.py tests/postgres_ops_store_test.py
git commit -m "feat(chickenbro): persist initial tool registry release"
```

Expected: all tests pass.

---

### Task 3: Add bounded cache and approved adapter execution

**Files:**
- Create: `server/chickenbro_tool_runtime.py`
- Create: `tests/chickenbro_tool_runtime_test.py`

**Interfaces:**
- Consumes: `validate_chickenbro_registry_release`, `discover_chickenbro_capabilities`.
- Produces: `ChickenbroRegistryRuntime(cache_ttl_seconds=60)`, `.resolve(loader, request_intent, request_context, now=None) -> dict`, and `execute_chickenbro_selected_tools(resolution, adapter_bindings, request) -> list[dict]`.

- [ ] **Step 1: Write failing cache tests**

Use an injected loader and timezone-aware clock. Cover:

```text
fresh database release -> registrySource=postgres and cache stored
loader failure at age 30s -> verified cache used
loader failure at age 61s -> RegistryUnavailable raised
cold-start loader failure -> RegistryUnavailable raised
invalid database release -> RegistryInvalid raised and prior cache is not silently substituted
```

Invalid Registry data is a security/configuration failure, not a transient read failure; cached fallback is allowed only when the loader itself raises an availability error before returning data.

- [ ] **Step 2: Run and verify RED**

```powershell
python -m unittest tests.chickenbro_tool_runtime_test -v
```

Expected: missing runtime module.

- [ ] **Step 3: Implement thread-safe verified cache resolution**

Use a lock around snapshot replacement. Store defensive copies, verified-at monotonic/UTC timestamp, Registry identity and no user request data. Return resolution with:

```python
{
    **discover_chickenbro_capabilities(...),
    "registrySource": "postgres" | "verified_cache",
    "registryStatus": "verified",
}
```

- [ ] **Step 4: Write failing adapter security and execution tests**

Bindings are explicit callables keyed only by approved implementation refs. Tests must assert unknown refs fail before any callable runs; the request object passed to adapters contains only `message`, `intent` and sanitized `context`; one adapter failure returns a bounded ToolResult with `status=failed`, no exception text longer than 160 characters and no fallback adapter call.

- [ ] **Step 5: Implement adapter dispatch and verify GREEN**

Execute only `selectedManifests`, once each, in discovery order. The adapter result must be a dict with `sourceKey`, `status`, `facts`, `evidence`, `evidenceRefs`, `limitations` and `nextActions`; otherwise return `status=failed` for that capability. Run:

```powershell
python -m unittest tests.chickenbro_registry_test tests.chickenbro_tool_runtime_test -v
```

- [ ] **Step 6: Commit runtime isolation**

```powershell
git add server/chickenbro_tool_runtime.py tests/chickenbro_tool_runtime_test.py
git commit -m "feat(chickenbro): add verified registry runtime"
```

---

### Task 4: Cut the backend from fixed selection to Registry discovery

**Files:**
- Modify: `server/news_backend.py`
- Modify: `tests/chickenbro_agent_test.py`
- Modify: `tests/news_backend_test.py`

**Interfaces:**
- Consumes: Tasks 1-3 and existing `classify_chickenbro_request`, Raider.IO builder and WCL builder.
- Produces: Registry-backed `load_chickenbro_source_tool_results` and bounded `registryContext` in each new Agent request.

- [ ] **Step 1: Write failing parity and no-fallback tests**

Capture the current ToolResult for:

```text
WCL URL with verified evidence
WCL URL with missing credentials
retail protection-warrior build with synced Raider.IO
PTR frost-deathknight build with partial Raider.IO
general WoW question
community build missing spec
```

Inject an active Registry loader and assert exact ToolResult parity for supported paths. Then make the Registry loader unavailable/invalid and assert `load_chickenbro_source_tool_results` does not call either old direct branch, returns no fabricated evidence and adds `registry_unavailable`/`registry_invalid` to bounded limitations.

- [ ] **Step 2: Run focused backend tests and verify RED**

```powershell
python -m unittest tests.chickenbro_agent_test tests.news_backend_test.NewsBackendTest.test_chickenbro_registry_unavailable_never_uses_fixed_allowlist -v
```

Expected: no Registry injection/context exists or fixed branch still runs.

- [ ] **Step 3: Wire Ops store, cache and explicit adapters**

Create one process-level `ChickenbroRegistryRuntime(60)`. The loader calls `ops_data_store().load_active_chickenbro_registry_release()` and fails when the Ops store is missing. Bind:

```python
{
    "chickenbro.source.raiderio.v1": lambda request: build_raiderio_chickenbro_tool_result(
        chickenbro_cached_raiderio_payload(), request["intent"]
    ),
    "chickenbro.source.warcraftlogs.v1": lambda request: build_wcl_chickenbro_tool_result(
        build_wcl_log_evidence({"prompt": request["message"]})
    ),
}
```

Do not accept adapter keys from the HTTP payload. Delete the intent-based direct Tool dispatch in `load_chickenbro_source_tool_results`.

- [ ] **Step 4: Attach bounded Registry context before model execution**

`build_chickenbro_bounded_context` must include:

```python
"registryContext": {
    "status": "verified" | "unavailable" | "invalid",
    "registryVersion": "",
    "registryReleaseHash": "",
    "registrySource": "postgres" | "verified_cache" | "",
    "discoveredCapabilityIds": [],
    "selectedCapabilityIds": [],
}
```

Do not include manifests, purpose, implementation refs or exception text. Registry failure limitations feed the existing answer/evidence path but do not change the public response schema.

- [ ] **Step 5: Add a read-only health component**

`build_data_health_payload` adds `chickenbro_tool_registry` with status `verified`, `partial` or `blocked`, checked time, Registry version/hash prefix, active Tool IDs, cache source and blockers. It must not refresh sources, execute Tool adapters or expose manifests.

- [ ] **Step 6: Run backend regression and commit**

```powershell
python -m unittest tests.chickenbro_registry_test tests.chickenbro_tool_runtime_test tests.chickenbro_agent_test tests.news_backend_test -v
git add server/news_backend.py tests/chickenbro_agent_test.py tests/news_backend_test.py
git commit -m "feat(chickenbro): discover tools from active registry"
```

Expected: all tests pass and supported ToolResults are unchanged.

---

### Task 5: Upgrade new traces to Registry v2 without rewriting v1

**Files:**
- Modify: `server/chickenbro_observability.py`
- Modify: `server/chickenbro_eval.py`
- Modify: `tests/chickenbro_observability_test.py`
- Modify: `tests/chickenbro_eval_test.py`
- Modify: `tests/fixtures/chickenbro_trace_eval_cases.json`

**Interfaces:**
- Consumes: Task 4 `registryContext`.
- Produces: `chickenbro-agent-trace-v2` and `chickenbro-trace-projection-v2`; preserves v1 validators/projection for historical records.

- [ ] **Step 1: Write failing Trace v2 tests**

Add verified Registry context and assert:

```python
self.assertEqual("chickenbro-agent-trace-v2", trace["schemaRevision"])
self.assertEqual("chickenbro-registry-runtime-v1", trace["runtimeVersion"])
self.assertEqual("registry", trace["selectionMode"])
self.assertEqual("chickenbro-tools-1", trace["registryVersion"])
self.assertEqual("postgres", trace["registrySource"])
self.assertEqual(["source:raiderio:v1"], trace["discoveredCapabilityIds"])
self.assertEqual(["source:raiderio:v1"], trace["selectedCapabilityIds"])
```

Also assert a literal P1 v1 fixture still validates and projects unchanged; unknown Registry source/hash/capability and selected-not-discovered fail.

- [ ] **Step 2: Run focused tests and verify RED**

```powershell
python -m unittest tests.chickenbro_observability_test tests.chickenbro_eval_test -v
```

Expected: current builder emits v1/fixed_allowlist and lacks Registry keys.

- [ ] **Step 3: Implement version-dispatched validation**

Keep frozen v1 constants and validation path. New runtime context emits v2. v2 capability IDs come from the validated Registry context rather than a global fixed set, but must match `source:[a-z0-9_.-]+:v[0-9]+`, be unique and have a matching selected Tool status. `registryReleaseHash` must be `sha256:` plus 64 lowercase hex chars. Projection v2 includes version/hash, source, discovered/selected IDs and existing bounded status fields only.

- [ ] **Step 4: Update the offline Eval corpus**

Every P2 case adds the deterministic initial Registry context. Retain one explicit `historical_trace_v1_is_readable` unit fixture outside the JSON corpus. Eval continues without DB, model, network or Tool execution and validates expected Registry version/selection.

- [ ] **Step 5: Run Trace/Eval and backend terminal-path tests**

```powershell
python -m unittest tests.chickenbro_observability_test tests.chickenbro_eval_test tests.news_backend_test tests.postgres_personal_store_test -v
python scripts/evaluate_chickenbro_traces.py
```

Expected: all tests pass; Eval summary reports all cases passed; one successful/failed terminal request writes one v2 Trace while old v1 reads remain valid.

- [ ] **Step 6: Commit observability cutover**

```powershell
git add server/chickenbro_observability.py server/chickenbro_eval.py tests/chickenbro_observability_test.py tests/chickenbro_eval_test.py tests/fixtures/chickenbro_trace_eval_cases.json
git commit -m "feat(chickenbro): trace registry discovery identity"
```

---

### Task 6: Bind control plane, release evidence and candidate deployment

**Files:**
- Modify: `docs/backend-owner-map.json`
- Modify: `docs/project-owner-map.json`
- Modify: `docs/plans/README.md`
- Modify: `docs/plans/2026-08-02-chickenbro-capability-evolution-design.md`
- Modify: `docs/plans/2026-08-02-chickenbro-tool-registry-phase2-design.md`
- Modify: `docs/plans/2026-08-02-chickenbro-tool-registry-phase2-implementation.md`
- Create: `artifacts/releases/2026-08-02-chickenbro-tool-registry-phase2/requirement.json`
- Create: `artifacts/releases/2026-08-02-chickenbro-tool-registry-phase2/manifest.json`
- Create: `artifacts/releases/2026-08-02-chickenbro-tool-registry-phase2/evidence.json`

**Interfaces:**
- Consumes: Tasks 1-5 and Harness schema v2.
- Produces: one task-scoped release packet, candidate/live evidence, merge/closure identity and archived control-plane status.

- [ ] **Step 1: Update owner maps**

Make `server/chickenbro_registry.py` the Manifest/Release/discovery fact owner, `server/chickenbro_tool_runtime.py` the runtime adapter/cache owner, `postgres_ops_store.py` the read-store owner and `news_backend.py` an orchestrator. Add must-not-change rules for arbitrary implementation refs, owner/credential override, fixed-allowlist fallback and Phase 3-5 scope.

- [ ] **Step 2: Create the Strict requirement packet**

Use slug `chickenbro-tool-registry-phase2`. The requirement scope is exactly:

```json
[
  "immutable PostgreSQL Tool manifests and active Registry Release",
  "deterministic Registry discovery for existing Raider.IO and Warcraft Logs Tools",
  "repository-bound adapter execution with no arbitrary implementation loading",
  "Registry Trace v2 with P1 Trace v1 read compatibility",
  "read-only Registry health and bounded verified-cache degradation"
]
```

Out of scope is exactly:

```json
[
  "new Tools or wrapping personal template and SimC context as Tools",
  "CapabilityGap persistence or clustering",
  "Cloud Codex Toolsmith or candidate generation",
  "shadow, canary, promotion or model training",
  "frontend, public response schema or answer-policy changes"
]
```

Set classification `Strict`, release trigger `backend_api`, manual acceptance not required, and evidence requirements for migration, full Harness, candidate three-path smoke and rollback.

- [ ] **Step 3: Run focused verification and local CR**

```powershell
python -m unittest tests.chickenbro_registry_test tests.chickenbro_tool_runtime_test tests.postgres_schema_test tests.postgres_ops_store_test -v
python -m unittest tests.chickenbro_observability_test tests.chickenbro_eval_test tests.chickenbro_agent_test -v
python -m unittest tests.news_backend_test tests.postgres_personal_store_test -v
python scripts/evaluate_chickenbro_traces.py
node --test tests/project-owner-map.test.js tests/backend-owner-map.test.js
git diff --check
```

CR must explicitly confirm: exactly two Tools; no new external call or credential; no manifest-provided executable code; no fixed fallback in P2 code; ToolResult and public response parity; v1 read compatibility; Registry failure fail closed; no frontend diff.

- [ ] **Step 4: Create manifest/evidence and run exact full Harness**

Generate `manifest.json` through the repository Harness identity flow. On an exact clean HEAD run:

```powershell
$node = 'C:\Users\blizz\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
& $node scripts/verify-project.js --profile full --release artifacts/releases/2026-08-02-chickenbro-tool-registry-phase2
```

Expected: one complete packet selected, full profile passes, verification identity binds exact HEAD, and no P1 packet is reused.

- [ ] **Step 5: Deploy one immutable candidate**

Before writes, record candidate SHA, remote service/health, current P1 runtime hashes, PostgreSQL migration ledger, current timer state and a PostgreSQL backup. Keep `WOW_DEPLOY_START_ASYNC_SYNCS=0`. Deploy only affected server files plus migration 0025, apply it through the existing repository migration path, restart `wow-backend`, and verify exact file hashes and migration identity.

- [ ] **Step 6: Run live three-path and failure smoke**

Using isolated guest sessions, verify:

```text
community build question -> Raider.IO selected only, response schema unchanged, Trace v2 registrySource=postgres
public WCL report URL -> Warcraft Logs selected only, response schema unchanged, Trace v2
general WoW question -> no Tool selected, normal answer
wrong-owner Trace read -> not found
Registry table read privilege -> wow_app SELECT succeeds; INSERT/UPDATE/DELETE fail
temporarily unavailable Registry read with verified cache <=60s -> verified_cache Trace source
invalid or cache-expired Registry path in isolated probe -> no fixed allowlist call and explicit blocker
health -> chickenbro_tool_registry reports initial release and exactly two active IDs
```

Do not mutate the active release to simulate failure on the shared candidate. Use injected isolated process/probe or a transactionally rolled-back test connection.

- [ ] **Step 7: Prove code rollback**

Restore the recorded P1 backend/runtime files, restart and verify health plus the same WCL/build/general smoke under fixed allowlist, leaving additive 0025 tables intact. Restore the exact P2 candidate and repeat health plus one Registry-backed request. Record hashes and Trace schema differences.

- [ ] **Step 8: Final CR, commit, merge and archive**

Update evidence to `candidate_verified`, run final local CR and targeted tests, commit all task files, push the task branch and open/update its PR. After CI is green, merge without history rewrite, verify merged `main` with scoped tests, push, verify local `main == origin/main`, verify cloud files/runtime identity match the approved candidate or deploy exact merged tree if required, then update evidence/control-plane status to archived and remove only this task worktree/local/published branch. No WeChat refresh is required because active frontend files do not change.

## Final acceptance matrix

| Boundary | Required proof |
| --- | --- |
| User journey | Existing build, WCL and general questions preserve response schema and evidence behavior |
| Registry | One immutable active release, exactly two approved manifests, deterministic hashes |
| Execution | Repository adapter binding only; no arbitrary code/URL/owner/credential from data |
| Selection | discovered and selected sets are deterministic and correctly separated |
| Failure | Invalid/unavailable Registry never invokes fixed allowlist or unregistered Tool |
| Privacy | Manifest/Trace contain no prompt, answer, credentials or owner data |
| Trace | New requests use v2; historical v1 remains readable |
| Scope | No new Tool, Gap, Toolsmith, shadow/canary/promotion or frontend change |
| Runtime | Exact candidate, PostgreSQL migration, health, three-path smoke and rollback pass |
| Closure | CI, merged main, origin and cloud identity agree; task resources are cleaned |

## Execution notes

- Execute inline; do not dispatch subagents.
- Create an isolated worktree before Task 1 and do not move or commit the main checkout's unrelated UI changes.
- Stop only for destructive data action, scope expansion, inability to prove Registry read-only privileges, failed owner/evidence boundary, non-fast-forward remote conflict or a candidate regression that cannot be safely rolled back.
