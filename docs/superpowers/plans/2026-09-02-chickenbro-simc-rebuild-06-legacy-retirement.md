# Chickenbro-SimC Rebuild Phase 6 Legacy Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove every superseded local and cloud owner after the new Chat/SimC production path is accepted, while retaining one restore-verified rollback package for a bounded window.

**Architecture:** Cleanup is driven exclusively by the reviewed local and cloud manifests, exact resource names, and pre-delete content hashes. Local caller/link/build proofs precede file deletion; remote service/database/directory retirement uses a dry-run-first state machine with backup/restore/reference/connection gates and can never target a wildcard, unresolved variable, filesystem root, home directory, or active `chickenbro_prod` owner.

**Tech Stack:** Node.js 20, Python 3, Git, PostgreSQL, systemd, Nginx, Bash, Project Harness.

**Spec:** `docs/superpowers/specs/2026-09-02-chickenbro-simc-total-rebuild-design.md`

## Global Constraints

- Phase 6 cannot start before Phase 5 records real Mini/Web acceptance, first-new-write state, migration reconciliation, and stable production health.
- `chickenbro_prod`, `chickenbro-api`, `chickenbro-worker`, current Web assets, current Mini build identity, `/opt/wow-simc/current`, Nginx/TLS, and the bounded rollback package are protected keep targets.
- Every deletion target is an exact file, database, service, timer, env file, or directory from a reviewed manifest; globs and recursive broad roots are forbidden.
- A database requires zero active connections, zero current config references, an independent restore-verified backup, and an explicit target-name allowlist.
- A service/timer requires zero current dependency/caller references and a replacement or explicit removal decision.
- Cleanup evidence distinguishes deleted, retained, skipped, failed, recoverable, and permanently retired resources.
- Git history is the archive for removed repository docs/code; the independent backup is the recovery authority for removed cloud data.
- Overall completion requires final real Mini/Web acceptance after cleanup, not merely disk reclamation.

---

## File Structure

- Create `scripts/apply-chickenbro-simc-local-cleanup.js`: exact local cleanup verifier/executor.
- Create `tests/chickenbro-simc-local-cleanup.test.js`: no-glob/hash/caller/link/build gates.
- Update `docs/refactor/chickenbro-simc-refactor-inventory.json`: final exact local disposition set.
- Create `server/retire_chickenbro_legacy_lighthouse.sh`: exact remote retirement state machine.
- Create `tests/retire-chickenbro-legacy.test.js`: protected targets, dry-run, backup, DB, service, and directory gates.
- Create `docs/refactor/chickenbro-simc-cloud-cleanup-manifest.json`: exact reviewed cloud resources and recovery identities.
- Delete all manifest-classified legacy docs/code/tests/assets/scripts/services/migrations after caller proof.
- Rewrite `README.md`, `docs/README.md`, `docs/plans/README.md`, owner maps, state, verification matrix, architecture, and production runbook as the complete retained documentation set.
- Create `artifacts/releases/2026-09-02-chickenbro-simc-legacy-retirement/{requirement,evidence,manifest}.json`.

### Task 1: Freeze exact local deletion manifest and caller proof

**Files:**
- Create: `scripts/apply-chickenbro-simc-local-cleanup.js`
- Create: `tests/chickenbro-simc-local-cleanup.test.js`
- Modify: `docs/refactor/chickenbro-simc-refactor-inventory.json`

**Interfaces:**
- Consumes: inventory bound to current commit, exact file SHA-256, retained-file link/import/config/build graphs.
- Produces: `verifyCleanup(inventory, repository) -> { deletable, blocked, retained }`; `--dry-run` default; `--apply --inventory-sha <sha256> --commit <40-char-sha>`.

- [ ] **Step 1: Write failing destructive-safety tests**

```js
test('cleanup rejects directories globs and changed files', () => {
  assert.throws(() => validateTarget('docs/**'), /exact file/)
  assert.throws(() => validateTarget('server/'), /exact file/)
  assert.throws(() => verifyHash('server/news_backend.py', 'wrong'), /hash mismatch/)
})

test('retained caller blocks deletion', () => {
  const result = verifyCleanup(inventoryWithDelete('legacy.py'), repositoryImporting('legacy.py'))
  assert.equal(result.blocked[0].reason, 'RETAINED_CALLER')
})
```

- [ ] **Step 2: Run and verify missing executor failure**

Run: `node --test tests/chickenbro-simc-local-cleanup.test.js`

- [ ] **Step 3: Implement exact graph gates**

Scan tracked source imports, package exports, app route config, build entries, deploy source lists, service `ExecStart`, documentation links, Harness packets, runbooks, and tests. A delete entry with any retained incoming edge becomes `blocked`; a changed SHA becomes `blocked`; an unclassified file becomes `review`. No tool call deletes anything while any count is nonzero.

- [ ] **Step 4: Generate and review final dry run**

```bash
node scripts/build-chickenbro-simc-refactor-inventory.js \
  --rules docs/refactor/chickenbro-simc-disposition-rules.json \
  --output docs/refactor/chickenbro-simc-refactor-inventory.json
node scripts/apply-chickenbro-simc-local-cleanup.js \
  --inventory docs/refactor/chickenbro-simc-refactor-inventory.json --dry-run
```

Expected: zero `review`, zero `blocked`, and every delete target printed as an exact tracked file with SHA-256.

- [ ] **Step 5: Commit the reviewed manifest/executor before deletion**

```bash
git add scripts/apply-chickenbro-simc-local-cleanup.js tests/chickenbro-simc-local-cleanup.test.js \
  docs/refactor/chickenbro-simc-refactor-inventory.json
git commit -m "chore: freeze exact legacy file cleanup"
```

### Task 2: Remove legacy repository code and product surfaces

**Files:**
- Delete: every exact file with `disposition: delete` and `category: code|test|asset|migration|deploy` in `docs/refactor/chickenbro-simc-refactor-inventory.json`.
- Modify: `package.json`, workspace package indexes/configs, Python module exports, deployment source lists.
- Test: retained Chat/SimC/backend/frontend/build suites.

**Interfaces:**
- Retained runtime imports only `server.app` formal Identity/Chat/SimC/Worker owners and target Mini/Web packages.
- Retained build registers exactly five Mini routes/two tabs and no prototype, news, builds, profile, gear, talent, WebSim, Catalog, Manifest, stat-weight, observed-build, or legacy sync owner.

- [ ] **Step 1: Execute only the reviewed local manifest**

Run the cleanup executor with the exact inventory SHA and current commit. Review the resulting Git diff before any further edit. If any target hash/caller differs, stop and regenerate/review rather than forcing deletion.

- [ ] **Step 2: Remove now-unused exports and dependencies**

Delete package exports/imports/config entries only when `rg` proves zero retained callers. Remove a dependency from `package.json` only if it has zero retained imports and is not required by build/test tooling; do not run an install or regenerate a lockfile via network.

- [ ] **Step 3: Run retained backend tests**

```bash
python3 -m unittest tests.app_identity_application_test tests.app_identity_repository_test \
  tests.app_identity_api_test tests.app_csrf_test tests.app_chat_api_test \
  tests.app_chat_cross_client_test tests.app_chickenbro_application_test \
  tests.app_chickenbro_owner_isolation_test tests.app_chickenbro_stream_test \
  tests.app_chickenbro_codex_adapter_test tests.app_simulation_application_test \
  tests.app_simulation_sources_test tests.app_simulation_readiness_test \
  tests.app_simulation_compiler_test tests.app_simulation_worker_test \
  tests.app_worker_lease_test tests.app_worker_runtime_test tests.app_simc_result_semantics_test \
  tests.app_simc_api_test tests.app_simc_cross_client_test -v
```

- [ ] **Step 4: Run retained frontend/build tests**

```bash
npm run test:taro -- apps/mini-taro/src/features apps/mini-taro/src/pages/chickenbro \
  apps/mini-taro/src/pages/simc apps/mini-taro/src/pages/auth apps/mini-taro/src/web \
  packages/domain/src/chat.test.ts packages/domain/src/simc.test.ts \
  packages/api-client/src/chat.test.ts packages/api-client/src/simc.test.ts \
  packages/api-client/src/web-auth.test.ts packages/api-client/src/transport.test.ts
npm run typecheck
npm run lint
npm run build:weapp
npm --workspace @wow-mini/mini-taro run build:h5
```

- [ ] **Step 5: Prove forbidden callers/routes are absent and commit**

```bash
rg -n "api/v2/prototype|news_backend|websim|gear_catalog|talent|observed_build|stat_weight" \
  server/app apps/mini-taro/src packages/api-client/src packages/domain/src
```

Expected: no runtime matches; test fixtures may contain only explicit forbidden-contract assertions. Commit the reviewed deletion diff:

```bash
git add -A
git commit -m "refactor: remove legacy product code"
```

### Task 3: Remove superseded documentation and evidence from the working tree

**Files:**
- Delete: every exact file with `disposition: delete` and `category: documentation|evidence` in the local inventory.
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/plans/README.md`
- Modify: `docs/project-state.json`
- Modify: `docs/project-owner-map.json`
- Modify: `docs/backend-owner-map.json`
- Modify: `docs/verification-matrix.md`
- Modify: `docs/chickenbro-simc-architecture.md`
- Modify: `docs/chickenbro-simc-production-runbook.md`
- Modify: `tests/project-state.test.js`

**Interfaces:**
- Retained documentation entrypoints are exactly README/AGENTS, state, roadmap, Harness/verification, owner maps, current architecture, identity/API/schema documentation, SimC semantics, production/restore runbook, current plans, and current release/cleanup evidence.

- [ ] **Step 1: Apply the reviewed documentation/evidence subset**

Delete only exact inventory paths. Git history remains the archive; do not copy deleted timelines into retained docs.

- [ ] **Step 2: Rewrite entrypoint documentation around the final product**

README documents only Chat/SimC local commands and builds. `docs/README.md` links only retained authorities. `plans/README.md` marks completed phase plans historical and leaves no executable legacy plan. Owner maps contain no legacy owners. Project state sets the final milestone but keeps rollback-package expiry explicitly pending until Task 5.

- [ ] **Step 3: Verify zero broken local links and zero missing plan entries**

Use the repository link checker or the Phase-1 link traversal; require every retained local link to resolve and every retained plan to appear in the plan index. Reject links to Git-deleted paths.

- [ ] **Step 4: Run current-state/Harness tests and commit**

```bash
node --test tests/project-state.test.js tests/chickenbro-simc-refactor-inventory.test.js \
  tests/chickenbro-simc-local-cleanup.test.js
git add -A
git commit -m "docs: remove superseded project history"
```

### Task 4: Exact cloud service, database, env, and directory retirement

**Files:**
- Create: `docs/refactor/chickenbro-simc-cloud-cleanup-manifest.json`
- Create: `server/retire_chickenbro_legacy_lighthouse.sh`
- Create: `tests/retire-chickenbro-legacy.test.js`
- Modify: `docs/chickenbro-simc-production-runbook.md`

**Interfaces:**
- Consumes: refreshed cloud inventory, production acceptance evidence, independent restore manifest, and exact cleanup manifest SHA.
- Produces: one result per exact resource with `deleted|retained|skipped|failed`, before/after identity, recovery reference, and timestamp.

- [ ] **Step 1: Write failing protected-target and exact-name tests**

```js
for (const protectedName of ['chickenbro_prod', 'chickenbro-api.service', 'chickenbro-worker.service', '/opt/wow-simc/current']) {
  assert.throws(() => validateDeletionTarget(protectedName), /protected target/)
}
for (const invalid of ['wow_*', '/opt', '/var/lib', '/', '~', '$HOME']) {
  assert.throws(() => validateDeletionTarget(invalid), /exact target/)
}
```

- [ ] **Step 2: Run and verify missing retirement script failure**

Run: `node --test tests/retire-chickenbro-legacy.test.js`

- [ ] **Step 3: Build the exact cloud manifest from the refreshed inventory**

The manifest lists every retired legacy `wow-*` service/timer, old v2 candidate/formal unit replaced by `chickenbro-*`, exact unused database name, exact env/pgpass/nginx file, and exact deployment/data/static/backup directory. Each entry includes current references, active connections, backup ID/hash, restore-check result, replacement, and delete-after timestamp. Entries failing any gate are `blocked`, not silently omitted.

- [ ] **Step 4: Implement dry-run-first retirement**

For systemd: stop, verify no active request dependency, disable, remove exact unit, daemon-reload, and confirm absent. For databases: revoke connect, terminate only target DB sessions, verify no config reference, run final restore check, then `DROP DATABASE` using a quoted exact identifier. For files/directories: verify path, device, realpath, content hash/manifest, and allowed parent before moving to an exact quarantine; permanent deletion waits for Task 5.

- [ ] **Step 5: Run dry run, review, and apply**

```bash
node --test tests/retire-chickenbro-legacy.test.js
bash server/retire_chickenbro_legacy_lighthouse.sh \
  --manifest docs/refactor/chickenbro-simc-cloud-cleanup-manifest.json --dry-run
```

After review, run with `--apply --manifest-sha <reviewed-sha> --backup-manifest-sha <restore-verified-sha>`. Stop immediately on any changed reference, connection, hash, active target, or missing recovery proof.

- [ ] **Step 6: Verify cloud parity and commit**

Verify only target services/ports/DB/schema owners remain; Nginx/TLS and current SimC runtime work; legacy unit files/envs/DBs/directories are absent or explicitly quarantined; root disk and PostgreSQL sizes are recorded as facts, not success. Commit script, tests, manifest, and redacted results.

```bash
git add server/retire_chickenbro_legacy_lighthouse.sh tests/retire-chickenbro-legacy.test.js \
  docs/refactor/chickenbro-simc-cloud-cleanup-manifest.json docs/chickenbro-simc-production-runbook.md
git commit -m "ops: retire legacy Chickenbro cloud owners"
```

### Task 5: Final recovery drill, post-cleanup acceptance, and closure packet

**Files:**
- Create: `artifacts/releases/2026-09-02-chickenbro-simc-legacy-retirement/requirement.json`
- Create: `artifacts/releases/2026-09-02-chickenbro-simc-legacy-retirement/evidence.json`
- Create: `artifacts/releases/2026-09-02-chickenbro-simc-legacy-retirement/manifest.json`
- Modify: `docs/project-state.json`
- Modify: `docs/roadmap.md`
- Modify: `docs/chickenbro-simc-production-runbook.md`

- [ ] **Step 1: Run an isolated recovery drill**

Restore the retained rollback package into an isolated database/directory that cannot receive public traffic. Verify manifest hashes, schema/listing, required Chat/SimC rows, configuration bundle, Nginx syntax, service unit syntax, and SimC identity. Destroy only the exact drill resources after recording success.

- [ ] **Step 2: Run final local and production verification**

Run the retained full backend/frontend/build suite, Harness full profile, Git/local/origin SHA parity, deployed-file parity, DB migration identity, Worker queue smoke, Nginx/TLS/public API smoke, and one semantic cloud SimC task.

- [ ] **Step 3: Obtain final real Mini/Web acceptance after cleanup**

The user verifies: Mini login, Web QR/explicit Mini confirmation, same conversation list/messages/continued Chat in both directions, same SimC task/history/result in both directions, independent logout, and no old routes/product entries. This post-cleanup acceptance is mandatory even if Phase 5 acceptance passed.

- [ ] **Step 4: Seal the Strict closure packet**

Evidence records exact deleted/retained/skipped resources, recovery drill, final acceptance, Git/origin/deployment/database identities, business smokes, and remaining rollback-package expiry. It must not summarize partial/skipped resources as complete.

- [ ] **Step 5: Retire the bounded rollback package at its reviewed expiry**

After the documented rollback window and stable new-system writes, refresh references and backups, delete only the exact rollback package from the cloud manifest, and record whether it is still recoverable from independent backup. If the window has not elapsed, project status remains `已上线，回滚包待到期退役`, not `已完成`.

- [ ] **Step 6: Mark the overall goal complete only after all gates close**

Set roadmap/state to `已完成`, write/check the Harness packet, run final local CR, integrate/push `main`, verify local/origin/production parity, refresh official WeChat DevTools from latest `main`, and clean task worktrees/branches. Only then may the persistent goal be marked complete.

Phase 6 and the overall rebuild are complete only when no manifest blocker remains, final post-cleanup real-user acceptance passes, the rollback window closes, and all code/data/runtime identities agree.
