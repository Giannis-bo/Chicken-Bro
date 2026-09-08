# Chickenbro-SimC Rebuild Phase 1 Control Plane Implementation Plan

> 当前结论（2026-09-08）：本计划已交付的 1.0 实现范围获用户整体验收，状态为 `已完成`。下面保留各阶段当时的状态与证据；旧“待验收/未合入/阻塞”描述不代表当前结论，也不授权重放迁移、发布或清理。未实现设想及微信公开发布不自动完成。详见 [1.0 说明](../../releases/1.0.md)。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish one machine-readable keep/delete/migrate inventory, current architecture, production runbook, and Harness packet before any product code or remote state is changed.

**Architecture:** A deterministic local classifier inventories every tracked path and records its disposition without deleting it. A separate redacted cloud-audit parser records exact database, service, timer, port, directory, and capacity facts; current documentation and Harness evidence consume those two artifacts as the only cleanup control plane.

**Tech Stack:** Node.js 20, Python 3 standard library, Git, JSON, Project Harness.

**Spec:** `docs/superpowers/specs/2026-09-02-chickenbro-simc-total-rebuild-design.md`

## Global Constraints

- The target product contains only Chickenbro Chat and SimC business domains on WeChat Mini Program and Web.
- Mini Bearer and Web HttpOnly Cookie sessions remain independent and resolve to one `identity.users.id`.
- This phase performs no code deletion, database mutation, deployment, service restart, cutover, dependency install, or network download.
- Every inventory entry is exact, content-addressed, and one of `keep`, `migrate`, `delete`, or `review`; unresolved `review` entries block later deletion.
- Current legacy production remains `Active / last-known-good` until candidate, rollback, and real user acceptance close.
- The 8.1GB free-space snapshot is stale after any remote change and must be refreshed before mutation.
- Candidate, HTTP 200, tests, systemd active, or a cleanup dry run is not completion.

---

## File Structure

- Create `docs/refactor/chickenbro-simc-disposition-rules.json`: human-reviewed path classification rules.
- Create `scripts/build-chickenbro-simc-refactor-inventory.js`: deterministic tracked-file inventory generator.
- Create `tests/chickenbro-simc-refactor-inventory.test.js`: classifier, hash, unresolved, and determinism tests.
- Generate `docs/refactor/chickenbro-simc-refactor-inventory.json`: exact local inventory bound to a Git commit.
- Create `server/chickenbro_simc_cloud_inventory.py`: redacted parser and live read-only audit command builder.
- Create `tests/chickenbro_simc_cloud_inventory_test.py`: secret-redaction and capacity-gate tests.
- Create `docs/refactor/chickenbro-simc-cloud-inventory.json`: read-only cloud snapshot with observed timestamp.
- Create `docs/chickenbro-simc-architecture.md`: single current architecture authority.
- Create `docs/chickenbro-simc-production-runbook.md`: capacity, backup, migration, cutover, rollback, and retirement gates.
- Modify `README.md`, `docs/README.md`, `docs/project-state.json`, `docs/project-owner-map.json`, `docs/backend-owner-map.json`, `docs/verification-matrix.md`, `docs/plans/README.md`: point current control-plane readers at the new artifacts.
- Create `artifacts/releases/2026-09-02-chickenbro-simc-control-plane/{requirement,evidence,manifest}.json`: one Strict phase packet.

### Task 0: Open the Strict Phase 1 requirement

**Files:**
- Create: `artifacts/releases/2026-09-02-chickenbro-simc-control-plane/requirement.json`

**Interfaces:**
- Consumes: approved design, six implementation plans, current state, roadmap, and Harness schema.
- Produces: one `implementation_allowed` Strict requirement that permits only Phase 1 read-only/local control-plane work.

- [ ] **Step 1: Write the exact requirement before implementation**

Set `manualAcceptanceContract.required` to `false`, `releaseTrigger` to `docs_tooling_only`, rollback to `code_rollback`, and protected surfaces to application runtime, production ingress, database state, services/timers, credentials, and Active Manifest. Evidence requirements are deterministic inventory, redacted read-only cloud audit, current-authority tests, link/plan coverage, and local CR.

- [ ] **Step 2: Validate the requirement**

Run:

```bash
node scripts/project-harness.js --check-requirement \
  --requirement-file artifacts/releases/2026-09-02-chickenbro-simc-control-plane/requirement.json
```

Expected: exit 0 and a valid Strict requirement.

- [ ] **Step 3: Commit the requirement before Task 1**

```bash
git add artifacts/releases/2026-09-02-chickenbro-simc-control-plane/requirement.json \
  docs/superpowers/plans/2026-09-02-chickenbro-simc-rebuild-01-control-plane.md
git commit -m "chore: open rebuild control plane requirement"
```

### Task 1: Deterministic local keep/delete/migrate inventory

**Files:**
- Create: `docs/refactor/chickenbro-simc-disposition-rules.json`
- Create: `scripts/build-chickenbro-simc-refactor-inventory.js`
- Create: `tests/chickenbro-simc-refactor-inventory.test.js`
- Generate: `docs/refactor/chickenbro-simc-refactor-inventory.json`

**Interfaces:**
- Consumes: `git ls-files -z` from a clean tracked `HEAD`, the repository root, and ordered rules from `chickenbro-simc-disposition-rules.json`.
- Produces: `classifyPath(relativePath, rules) -> { disposition, category, owner, reason, matchedRule }` and `buildInventory({ root, commit, paths, rules }) -> RefactorInventory`.
- Self-reference rule: the generated inventory file records `excludedSelfPath` and is not included in its own entry list because a file cannot contain its own stable content hash.

- [x] **Step 1: Write failing classifier and determinism tests**

```js
test('target owners are kept while prototype and legacy product surfaces are deleted', () => {
  assert.equal(classifyPath('server/app/chickenbro/domain.py', rules).disposition, 'keep')
  assert.equal(classifyPath('server/app/api/routes/prototype.py', rules).disposition, 'delete')
  assert.equal(classifyPath('apps/mini-taro/src/pages/news/news.tsx', rules).disposition, 'delete')
  assert.equal(classifyPath('server/news_backend.py', rules).disposition, 'delete')
  assert.equal(classifyPath('server/migrations/postgres/0038_chickenbro_simc_platform_foundation.sql', rules).disposition, 'migrate')
})

test('inventory ordering and sha256 are deterministic', () => {
  const first = buildInventory({ root, commit: 'a'.repeat(40), paths: ['b', 'a'], rules })
  const second = buildInventory({ root, commit: 'a'.repeat(40), paths: ['a', 'b'], rules })
  assert.deepEqual(first, second)
  assert.match(first.inventorySha256, /^[0-9a-f]{64}$/)
})
```

- [x] **Step 2: Run the focused test and verify the missing module failure**

Run: `node --test tests/chickenbro-simc-refactor-inventory.test.js`

Expected: FAIL because `scripts/build-chickenbro-simc-refactor-inventory.js` does not exist.

- [x] **Step 3: Implement ordered, fail-closed classification**

```js
function classifyPath(relativePath, rules) {
  const match = rules.rules.find((rule) =>
    rule.paths?.includes(relativePath) || rule.prefixes?.some((prefix) => relativePath.startsWith(prefix)),
  )
  if (!match) {
    return { disposition: 'review', category: 'unresolved', owner: '', reason: 'NO_RULE_MATCH', matchedRule: '' }
  }
  return { disposition: match.disposition, category: match.category, owner: match.owner, reason: match.reason, matchedRule: match.id }
}
```

Rules are evaluated from most-specific exception to broader known-tree disposition. The rules file must explicitly keep the new spec, Harness, `server/app/{identity,chickenbro,simulation,worker,platform,integrations}`, the target client owners, and tests for those owners; it must mark prototype, news, builds, gear, talent, WebSim, legacy 14-route, legacy migrations, deployment units, and historical docs as `delete` or `migrate`. A repository-wide catch-all is forbidden: an unknown top-level path must resolve to `review`, so a newly introduced product tree cannot silently inherit a deletion decision.

- [x] **Step 4: Run focused tests and commit the inventory owner**

Run: `node --test tests/chickenbro-simc-refactor-inventory.test.js`

Expected: PASS.

```bash
git add docs/refactor/chickenbro-simc-disposition-rules.json \
  scripts/build-chickenbro-simc-refactor-inventory.js \
  tests/chickenbro-simc-refactor-inventory.test.js \
  docs/superpowers/plans/2026-09-02-chickenbro-simc-rebuild-01-control-plane.md
git commit -m "chore: define Chickenbro SimC inventory owners"
```

- [x] **Step 5: Generate and validate the exact inventory from clean HEAD**

Run:

```bash
test -z "$(git status --short --untracked-files=no)"
node scripts/build-chickenbro-simc-refactor-inventory.js \
  --rules docs/refactor/chickenbro-simc-disposition-rules.json \
  --output docs/refactor/chickenbro-simc-refactor-inventory.json
node --test tests/chickenbro-simc-refactor-inventory.test.js
```

Expected: tests PASS; the generated JSON has `unresolvedCount: 0`, a full 40-character `generatedFromCommit`, per-entry SHA-256 for files, stable sorted entries, and `excludedSelfPath: "docs/refactor/chickenbro-simc-refactor-inventory.json"`.

- [x] **Step 6: Commit the generated inventory**

```bash
git add docs/refactor/chickenbro-simc-refactor-inventory.json
git commit -m "chore: inventory Chickenbro SimC rebuild files"
```

### Task 2: Redacted cloud inventory and capacity gate

**Files:**
- Create: `server/chickenbro_simc_cloud_inventory.py`
- Create: `tests/chickenbro_simc_cloud_inventory_test.py`
- Create: `docs/refactor/chickenbro-simc-cloud-inventory.json`

**Interfaces:**
- Consumes: tab-separated rows from read-only `psql`, `systemctl`, `ss`, `du`, and `df` probes; no environment values or command lines containing secrets.
- Produces: `build_inventory(snapshot: Mapping[str, object]) -> dict`, `capacity_gate(inventory) -> str`, and a JSON document with exact resource names and `observedAt`.

- [x] **Step 1: Write failing redaction and capacity tests**

```python
def test_capacity_is_blocked_when_free_space_is_smaller_than_current_database():
    inventory = build_inventory({"rootFreeBytes": 8_100_000_000, "currentDatabaseBytes": 15_000_000_000})
    assert inventory["capacityGate"] == "blocked_until_independent_legacy_cleanup_or_storage_expansion"

def test_output_rejects_secret_shaped_fields(self):
    with self.assertRaisesRegex(ValueError, "secret-bearing field"):
        build_inventory({"databaseUrl": "postgresql://" + "user:password@" + "host/db"})
```

- [x] **Step 2: Run the focused test and verify it fails**

Run: `python3 -m unittest tests.chickenbro_simc_cloud_inventory_test -v`

Expected: FAIL because `server.chickenbro_simc_cloud_inventory` does not exist.

- [x] **Step 3: Implement a strict redacted schema**

```python
SECRET_KEYS = frozenset({"password", "secret", "token", "databaseUrl", "pgpass", "cookie"})

def capacity_gate(inventory: Mapping[str, object]) -> str:
    if int(inventory["rootFreeBytes"]) <= int(inventory["currentDatabaseBytes"]):
        return "blocked_until_independent_legacy_cleanup_or_storage_expansion"
    return "capacity_preflight_required"
```

The live command builder may emit only database name/size/connection count, unit name/load/active/enabled state, listening address/port/process name, directory path/size, filesystem size/used/free, and SHA/version identities. It must never print `Environment=`, DSNs, PGPASS contents, WeChat credentials, Codex configuration, or source-provider credentials.

- [x] **Step 4: Refresh the read-only cloud snapshot**

Run the script through the existing authorized SSH path with `--read-only --output -`, review stdout for the allowed schema, then write the reviewed JSON to `docs/refactor/chickenbro-simc-cloud-inventory.json`. If SSH is unavailable, record `status: unreachable` and retain the 2026-09-02 observation; do not fabricate freshness.

- [x] **Step 5: Run tests and commit**

```bash
python3 -m unittest tests.chickenbro_simc_cloud_inventory_test -v
git add server/chickenbro_simc_cloud_inventory.py \
  tests/chickenbro_simc_cloud_inventory_test.py \
  docs/refactor/chickenbro-simc-cloud-inventory.json
git commit -m "chore: add redacted rebuild cloud inventory"
```

### Task 3: Make the new architecture the only execution authority

**Files:**
- Create: `docs/chickenbro-simc-architecture.md`
- Create: `docs/chickenbro-simc-production-runbook.md`
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/project-state.json`
- Modify: `docs/project-owner-map.json`
- Modify: `docs/backend-owner-map.json`
- Modify: `docs/verification-matrix.md`
- Modify: `docs/plans/README.md`
- Modify: `tests/project-state.test.js`

**Interfaces:**
- Consumes: the approved spec plus the two machine inventories from Tasks 1-2.
- Produces: one active architecture, one active production runbook, and machine-readable owner/verification references with no legacy execution authority.

- [x] **Step 1: Add failing current-authority assertions**

```js
assert.equal(state.activeMilestone, 'chickenbro_simc_total_rebuild_phase_1')
assert.equal(state.targetProduct.implementationAuthorized, true)
assert.equal(state.targetProduct.productionCutoverAuthorized, false)
assert.equal(state.targetProduct.destructiveCleanupAuthorized, false)
assert.equal(state.refactorInventory.localManifest, 'docs/refactor/chickenbro-simc-refactor-inventory.json')
assert.equal(state.refactorInventory.cloudSnapshot, 'docs/refactor/chickenbro-simc-cloud-inventory.json')
```

- [x] **Step 2: Run the state test and observe the expected failure**

Run: `node --test tests/project-state.test.js`

Expected: FAIL on the new phase and manifest fields.

- [x] **Step 3: Write the current architecture and runbook**

The architecture must define the exact dependency direction, Principal boundary, Chat/SimC owners, public API surface, worker lease semantics, and target five routes. The runbook must define preflight capacity, independent backup device verification, clean database bootstrap, full/delta migration, write fence, candidate, cutover, post-write rollback restriction, and exact retirement gates. Neither document may retain an implementation link to old S2, gear, talent, WebSim, prototype, or 14-route plans.

- [x] **Step 4: Update owner maps and verification matrix**

Set only `identity`, `chat`, `simc`, `worker`, `dual_client`, `migration`, `deployment`, and `legacy_retirement` as target product owners. Mark old owners `legacy_runtime_baseline_pending_retirement`; do not delete their factual evidence yet. Define focused commands for each phase and a final full profile that includes Python application tests, Node/Taro tests, build, candidate smoke, migration reconciliation, and remote parity.

- [x] **Step 5: Verify current authority and commit**

```bash
node --test tests/project-state.test.js
node scripts/project-harness.js --check-requirement \
  --requirement-file artifacts/releases/2026-09-02-chickenbro-simc-control-plane/requirement.json
git add README.md docs/README.md \
  docs/chickenbro-simc-architecture.md docs/chickenbro-simc-production-runbook.md \
  docs/project-state.json docs/project-owner-map.json docs/backend-owner-map.json \
  docs/verification-matrix.md docs/plans/README.md tests/project-state.test.js
git commit -m "docs: activate Chickenbro SimC rebuild control plane"
```

### Task 4: Seal the Strict phase evidence packet

**Files:**
- Create: `artifacts/releases/2026-09-02-chickenbro-simc-control-plane/requirement.json`
- Create: `artifacts/releases/2026-09-02-chickenbro-simc-control-plane/evidence.json`
- Create: `artifacts/releases/2026-09-02-chickenbro-simc-control-plane/manifest.json`

**Interfaces:**
- Consumes: committed inventory, documentation, tests, and exact Git identities from Tasks 1-3.
- Produces: one complete Harness packet whose evidence status is no stronger than local verification and read-only cloud reachability.

- [x] **Step 1: Revalidate the already-open Strict requirement**

Confirm it still permits only Phase 1 control-plane work and does not include deployment, cutover, migration, or cleanup claims.

- [x] **Step 2: Run the full phase verification**

```bash
node --test tests/chickenbro-simc-refactor-inventory.test.js tests/project-state.test.js
python3 -m unittest tests.chickenbro_simc_cloud_inventory_test -v
node scripts/verify-project.js --profile harness \
  --release artifacts/releases/2026-09-02-chickenbro-simc-control-plane
```

Expected: all selected checks exit 0 with zero failures.

- [x] **Step 3: Perform local CR**

Review `git diff origin/main...HEAD` against the approved spec. Reject any write command, secret-bearing output, broad delete target, legacy execution authority, unresolved inventory entry, or unverified cloud freshness claim.

- [x] **Step 4: Bind evidence and manifest to the verified commit**

Run:

```bash
node scripts/project-harness.js --write \
  --date 2026-09-02 \
  --slug chickenbro-simc-control-plane \
  --requirement-file artifacts/releases/2026-09-02-chickenbro-simc-control-plane/requirement.json \
  --evidence-file artifacts/releases/2026-09-02-chickenbro-simc-control-plane/evidence.json
node scripts/project-harness.js --check \
  --requirement-file artifacts/releases/2026-09-02-chickenbro-simc-control-plane/requirement.json \
  --evidence-file artifacts/releases/2026-09-02-chickenbro-simc-control-plane/evidence.json \
  --manifest-file artifacts/releases/2026-09-02-chickenbro-simc-control-plane/manifest.json
```

- [x] **Step 5: Commit the packet**

```bash
git add artifacts/releases/2026-09-02-chickenbro-simc-control-plane
git commit -m "test: seal rebuild control plane evidence"
```

Phase 1 is complete only when the branch has one complete packet, all local entries are classified, the cloud snapshot is explicitly fresh or unreachable, and no product/runtime mutation occurred.
