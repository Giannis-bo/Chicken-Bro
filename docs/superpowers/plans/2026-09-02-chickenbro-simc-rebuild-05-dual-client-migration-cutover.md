# Chickenbro-SimC Rebuild Phase 5 Dual Client, Migration, and Cutover Implementation Plan

> 当前结论（2026-09-08）：本计划已交付的 1.0 实现范围获用户整体验收，状态为 `已完成`。下面保留各阶段当时的状态与证据；旧“待验收/未合入/阻塞”描述不代表当前结论，也不授权重放迁移、发布或清理。未实现设想及微信公开发布不自动完成。详见 [1.0 说明](../../releases/1.0.md)。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the two-tab Mini/Web product, migrate all valid owner-bound Chat and SimC history into `chickenbro_prod`, and cut the only public write path to the new platform.

**Architecture:** Mini and H5 reuse typed domain/API clients and focused feature models while keeping their credential transports separate. An idempotent whitelist migrator classifies every legacy candidate, records source-to-target mappings in bounded audit events, reconciles content/owner/order/terminal hashes, and performs one final delta behind a write fence before Nginx and API/Worker DSNs switch atomically.

**Tech Stack:** Taro 4.2, React 18, TypeScript 5.9, Vitest, FastAPI, PostgreSQL, systemd, Nginx, Bash/Python migration tooling.

**Spec:** `docs/superpowers/specs/2026-09-02-chickenbro-simc-total-rebuild-design.md`

## Global Constraints

- Final Mini navigation is exactly `队长 | SimC`; target routes are the five paths in the approved spec.
- Web and Mini show the same server-owned conversations, messages, snapshots, jobs, attempts, and results for one internal user.
- Mini stores only its Bearer session in bounded local storage; Web uses HttpOnly Cookie plus in-memory/double-submit CSRF and never receives the Mini token.
- Prototype/demo owners, sessions, tokens, candidate Web-login sessions, invalid owner/order/terminal records, and all non-Chat/SimC data are rejected.
- Old auth sessions are never migrated; every user signs in again after cutover.
- Migration is idempotent, owner-scoped, hash-reconciled, one full pass plus one fenced delta, with no long-term dual write.
- Before the first new production write, rollback may restore the prior write path; after it, legacy remains read-only and cannot become a second primary.
- Candidate deployment, production cutover, and real user acceptance are separate gates.

---

## File Structure

- Create `apps/mini-taro/src/features/auth/mini-session.ts` and `mini-session.test.ts`: Mini login/session transport.
- Create `apps/mini-taro/src/features/chat/chat-model.ts` and `chat-model.test.ts`: shared Chat view model.
- Create `apps/mini-taro/src/features/simc/simc-model.ts` and `simc-model.test.ts`: shared SimC view model.
- Create `apps/mini-taro/src/pages/chickenbro/index.tsx`, `index.module.scss`, `index.config.ts`, and `index.test.ts`.
- Create `apps/mini-taro/src/pages/simc/index.tsx`, `index.module.scss`, `index.config.ts`, and `index.test.ts`.
- Create `apps/mini-taro/src/pages/simc/tasks.tsx`, `tasks.module.scss`, `tasks.config.ts`, and `tasks.test.ts`.
- Create `apps/mini-taro/src/pages/simc/task-detail.tsx`, `task-detail.module.scss`, `task-detail.config.ts`, and `task-detail.test.ts`.
- Modify `apps/mini-taro/src/app.config.ts`, `app.tsx`, `tab-bar-items.ts`, `tab-bar-state.ts`, and `custom-tab-bar/index.tsx`: exact five routes/two tabs.
- Delete `apps/mini-taro/src/web/PrototypePanel.tsx` and `PrototypePanel.module.scss`; modify `WebApp.tsx`/`WebApp.module.scss`; create `WebShell.tsx`, `WebChatView.tsx`, and `WebSimcView.tsx`.
- Modify `packages/api-client/src/transport.ts`, `clients.ts`, and `web-auth.ts`: Mini/Web auth contexts and CSRF.
- Create `server/migrations/product/migrate_legacy.py` and `reconcile_legacy.py` plus tests/fixtures.
- Create `server/deploy_chickenbro_candidate_lighthouse.sh`, `server/cutover_chickenbro_lighthouse.sh` and tests.
- Create `server/chickenbro-api.service`, `server/chickenbro-worker.service`, `server/chickenbro-api-candidate.service`, and `server/chickenbro-web.nginx`.
- Create `artifacts/releases/2026-09-02-chickenbro-simc-dual-client-cutover/{requirement,evidence,manifest}.json`.

### Task 1: Mini session and Web CSRF transport owners

**Files:**
- Create: `apps/mini-taro/src/features/auth/mini-session.ts`
- Create: `apps/mini-taro/src/features/auth/mini-session.test.ts`
- Modify: `packages/api-client/src/transport.ts`
- Modify: `packages/api-client/src/clients.ts`
- Modify: `packages/api-client/src/web-auth.ts`
- Modify: `packages/api-client/src/transport.test.ts`
- Modify: `packages/api-client/src/web-auth.test.ts`

**Interfaces:**
- Consumes: Phase-3 `ClientAuthContext` for formal business requests.
- Produces: `MiniSessionStore.getValid()`, `login()`, `logout()`, and `createAuthContext() -> { kind: 'mini', accessToken }`; `readWebCsrfCookie() -> string`; transport additionally accepts `{kind:'public'}` only for readiness/login endpoints.

- [ ] **Step 1: Write failing transport separation tests**

```ts
it('mini requests omit cookies and send only bearer', async () => {
  await transport.request('/api/v2/chat/conversations', { auth: { kind: 'mini', accessToken: 'mini-token' } })
  expect(fetchOptions.credentials).toBe('omit')
  expect(fetchOptions.headers.Authorization).toBe('Bearer mini-token')
  expect(fetchOptions.headers['X-CSRF-Token']).toBeUndefined()
})

it('web writes include cookies and csrf without authorization', async () => {
  await transport.request('/api/v2/chat/conversations', { method: 'POST', auth: { kind: 'web', csrfToken: 'csrf' } })
  expect(fetchOptions.credentials).toBe('include')
  expect(fetchOptions.headers['X-CSRF-Token']).toBe('csrf')
  expect(fetchOptions.headers.Authorization).toBeUndefined()
})
```

- [ ] **Step 2: Run and verify failure**

Run: `npm run test:taro -- apps/mini-taro/src/features/auth/mini-session.test.ts packages/api-client/src/transport.test.ts packages/api-client/src/web-auth.test.ts`

- [ ] **Step 3: Implement bounded Mini session lifecycle**

```ts
export interface StoredMiniSession { accessToken: string; expiresAt: string }

export class MiniSessionStore {
  async login(): Promise<StoredMiniSession> {
    const { code } = await Taro.login()
    if (!code) throw new Error('MINI_LOGIN_CODE_MISSING')
    const result = await this.auth.exchangeMiniCode(code)
    if (result.fromFallback || !isMiniExchangeResponse(result.payload)) throw new Error(result.problemCode || 'MINI_LOGIN_FAILED')
    this.storage.set(MINI_SESSION_KEY, result.payload)
    return result.payload
  }
}
```

Reject expired/malformed storage and re-login; never persist Web Cookie, CSRF, OpenID, or `session_key`. Web reads only `__Host-chickenbro-csrf` and keeps the value out of local/session storage.

- [ ] **Step 4: Run and commit**

```bash
npm run test:taro -- apps/mini-taro/src/features/auth/mini-session.test.ts \
  packages/api-client/src/transport.test.ts packages/api-client/src/web-auth.test.ts
npm run typecheck
git add apps/mini-taro/src/features/auth packages/api-client/src
git commit -m "feat: separate Mini and Web auth transports"
```

### Task 2: Two-tab Mini client and exact target routes

**Files:**
- Create: `apps/mini-taro/src/features/chat/chat-model.ts`
- Create: `apps/mini-taro/src/features/chat/chat-model.test.ts`
- Create: `apps/mini-taro/src/features/simc/simc-model.ts`
- Create: `apps/mini-taro/src/features/simc/simc-model.test.ts`
- Create: `apps/mini-taro/src/pages/chickenbro/index.tsx`
- Create: `apps/mini-taro/src/pages/chickenbro/index.module.scss`
- Create: `apps/mini-taro/src/pages/chickenbro/index.config.ts`
- Create: `apps/mini-taro/src/pages/chickenbro/index.test.ts`
- Create: `apps/mini-taro/src/pages/simc/index.tsx`
- Create: `apps/mini-taro/src/pages/simc/index.module.scss`
- Create: `apps/mini-taro/src/pages/simc/index.config.ts`
- Create: `apps/mini-taro/src/pages/simc/index.test.ts`
- Create: `apps/mini-taro/src/pages/simc/tasks.tsx`
- Create: `apps/mini-taro/src/pages/simc/tasks.module.scss`
- Create: `apps/mini-taro/src/pages/simc/tasks.config.ts`
- Create: `apps/mini-taro/src/pages/simc/tasks.test.ts`
- Create: `apps/mini-taro/src/pages/simc/task-detail.tsx`
- Create: `apps/mini-taro/src/pages/simc/task-detail.module.scss`
- Create: `apps/mini-taro/src/pages/simc/task-detail.config.ts`
- Create: `apps/mini-taro/src/pages/simc/task-detail.test.ts`
- Modify: `apps/mini-taro/src/app.config.ts`
- Modify: `apps/mini-taro/src/tab-bar-items.ts`
- Modify: `apps/mini-taro/src/tab-bar-state.ts`
- Modify: `apps/mini-taro/src/custom-tab-bar/index.tsx`
- Modify: `apps/mini-taro/src/tab-bar-items.test.ts`
- Modify: `apps/mini-taro/src/tab-bar-state.test.ts`

**Interfaces:**
- Chat model consumes `ChatClient` and Mini auth context; SimC model consumes `SimcClient` and the same Mini auth context.
- Exact route order: `pages/chickenbro/index`, `pages/simc/index`, `pages/simc/tasks`, `pages/simc/task-detail`, `pages/auth/web-login-confirm`.

- [ ] **Step 1: Write failing exact-route and cross-feature model tests**

```ts
expect(appConfig.pages).toEqual([
  'pages/chickenbro/index',
  'pages/simc/index',
  'pages/simc/tasks',
  'pages/simc/task-detail',
  'pages/auth/web-login-confirm',
])
expect(tabBarItems.map(({ pagePath, label }) => ({ pagePath, label }))).toEqual([
  { pagePath: 'pages/chickenbro/index', label: '队长' },
  { pagePath: 'pages/simc/index', label: 'SimC' },
])
```

- [ ] **Step 2: Run and verify current 15-route/four-tab failure**

Run: `npm run test:taro -- apps/mini-taro/src/tab-bar-items.test.ts apps/mini-taro/src/pages/chickenbro/index.test.ts apps/mini-taro/src/pages/simc/index.test.ts`

- [ ] **Step 3: Implement Chat list/detail/send flow**

The page loads the server conversation page, creates or selects a conversation, loads full ordered messages, streams a send with generated `clientMessageId`/`Idempotency-Key`, appends sequence-checked deltas, then refreshes persisted history on completion/reconnect. Explicit error cards expose retry/re-login without fabricated messages.

- [ ] **Step 4: Implement SimC source/job/history flow**

The SimC home accepts only Raider.IO/WCL URLs, displays readiness/blockers, submits a bounded scenario, navigates to the returned job; task list reads server history; detail polls only queued/running jobs with bounded backoff and renders semantic result/public failure/provenance.

- [ ] **Step 5: Replace route configuration and two-tab shell**

Remove every old page from `app.config.ts`; tab defaults and active-route resolution must use `pages/chickenbro/index`. Keep `web-login-confirm` outside TabBar. Do not leave hidden old route registrations.

- [ ] **Step 6: Verify and commit**

```bash
npm run test:taro -- apps/mini-taro/src/features apps/mini-taro/src/pages/chickenbro \
  apps/mini-taro/src/pages/simc apps/mini-taro/src/tab-bar-items.test.ts apps/mini-taro/src/tab-bar-state.test.ts
npm run typecheck
npm run build:weapp
git add apps/mini-taro/src
git commit -m "feat: rebuild Mini client around Chat and SimC"
```

### Task 3: Formal Web shell without prototype bypass

**Files:**
- Delete: `apps/mini-taro/src/web/PrototypePanel.tsx`
- Delete: `apps/mini-taro/src/web/PrototypePanel.module.scss`
- Modify: `apps/mini-taro/src/web/WebApp.tsx`
- Modify: `apps/mini-taro/src/web/WebApp.module.scss`
- Create: `apps/mini-taro/src/web/WebShell.tsx`
- Create: `apps/mini-taro/src/web/WebChatView.tsx`
- Create: `apps/mini-taro/src/web/WebSimcView.tsx`
- Modify: `apps/mini-taro/src/web/web-app-contract.test.ts`
- Modify: `apps/mini-taro/src/web/web-auth-model.ts` and tests.

**Interfaces:**
- Web states are `checking`, `signed_out`, `qr_pending`, `qr_confirmed`, `authenticated`, `blocked`.
- Authenticated shell has only `队长`, `SimC`, account label, and logout; it uses the same feature models and typed clients as Mini.

- [ ] **Step 1: Write failing no-prototype and two-view tests**

```ts
expect(source).not.toMatch(/PrototypePanel|prototypeClient|返回 Web 原型|demo owner/)
expect(source).toMatch(/WebChatView/)
expect(source).toMatch(/WebSimcView/)
expect(source).toMatch(/队长/)
expect(source).toMatch(/SimC/)
```

- [ ] **Step 2: Run and verify prototype-first failure**

Run: `npm run test:taro -- apps/mini-taro/src/web/web-app-contract.test.ts apps/mini-taro/src/web/web-auth-model.test.ts`

- [ ] **Step 3: Make formal login the only entry**

On load, call `/api/v2/me`; authenticated users enter `WebShell`, 401 users see QR login, and other errors show a truthful retry state. After exchange, read the CSRF cookie and instantiate Web Chat/SimC contexts. Remove every prototype import, control, copy string, and client call.

- [ ] **Step 4: Add shared-history Web views**

Web Chat and SimC use the same server pagination and identifiers as Mini, not local demo state. Reload must reconstruct state from `/me`, conversation/job lists, and details.

- [ ] **Step 5: Verify H5 and commit**

```bash
npm run test:taro -- apps/mini-taro/src/web packages/domain/src/chat.test.ts packages/domain/src/simc.test.ts \
  packages/api-client/src/chat.test.ts packages/api-client/src/simc.test.ts packages/api-client/src/web-auth.test.ts
npm run typecheck
npm --workspace @wow-mini/mini-taro run build:h5
git add apps/mini-taro/src/web packages/api-client/src
git commit -m "feat: make Web login lead to shared Chat and SimC"
```

### Task 4: Idempotent whitelist migration and reconciliation

**Files:**
- Create: `server/migrations/product/migrate_legacy.py`
- Create: `server/migrations/product/reconcile_legacy.py`
- Create: `tests/legacy_product_migration_test.py`
- Create: `tests/fixtures/legacy_product_migration.json`
- Modify: `docs/chickenbro-simc-production-runbook.md`

**Interfaces:**
- Produces: `classify_record(record) -> MigrationDecision`, `migrate_full(source, target, watermark) -> MigrationReport`, `migrate_delta(...)`, and `reconcile(source, target, report) -> ReconciliationReport`.
- Accepted source owners: formal `wechat_mini` identities, valid `chat.*`/`simc.*`, and deterministically owner-bound `app.chickenbro_sessions/messages` plus `app.simulator_tasks`.

- [ ] **Step 1: Write failing acceptance/rejection/idempotency tests**

```python
def test_prototype_and_auth_records_are_rejected(self):
    self.assertEqual(classify_record({"table": "identity.prototype_sessions"}).reason, "PROTOTYPE_NOT_MIGRATED")
    self.assertEqual(classify_record({"table": "identity.auth_sessions"}).reason, "AUTH_SESSION_NOT_MIGRATED")

def test_owner_bound_chat_is_idempotent(self):
    first = migrate_full(source, target, watermark)
    second = migrate_full(source, target, watermark)
    self.assertEqual(first.accepted_hash, second.accepted_hash)
    self.assertEqual(target.message_count, expected_count)
```

- [ ] **Step 2: Run and verify missing migrator failure**

Run: `python3 -m unittest tests.legacy_product_migration_test -v`

- [ ] **Step 3: Implement explicit classifiers**

Every decision has `source_table`, `source_primary_key_hash`, `status` (`accepted` or `rejected`), `reason`, `target_table`, and deterministic target UUIDv5. Store accepted mappings as `ops.audit_events(event_type='legacy_migration.accepted', subject_key='<table>:<pk-hash>')`; unique `(event_type, subject_key)` makes reruns idempotent without retaining raw source keys in public output.

- [ ] **Step 4: Implement ordered migration**

Order is formal users/identities, conversations, messages, agent runs, snapshots, jobs, attempts, results. A row is accepted only if owner, parent, order, required input, terminal state, and content hash all validate. Old auth/session/token rows are never read into target inserts.

- [ ] **Step 5: Implement reconciliation and delta watermark**

Reconciliation compares accepted/rejected counts and reason counts per table, target FK/owner violations, message order hashes, snapshot hashes, job terminal/result hashes, and mapping coverage. The delta uses source `updated_at/id` watermarks captured after the write fence; no ongoing trigger or dual-write path is created.

- [ ] **Step 6: Run and commit**

```bash
python3 -m unittest tests.legacy_product_migration_test -v
git add server/migrations/product/migrate_legacy.py server/migrations/product/reconcile_legacy.py \
  tests/legacy_product_migration_test.py tests/fixtures/legacy_product_migration.json \
  docs/chickenbro-simc-production-runbook.md
git commit -m "feat: add idempotent Chat SimC migration"
```

### Task 5: Clean candidate deployment and real dual-client acceptance

**Files:**
- Create: `server/chickenbro-api.service`
- Create: `server/chickenbro-worker.service`
- Create: `server/chickenbro-api-candidate.service`
- Create: `server/chickenbro-web.nginx`
- Create: `server/deploy_chickenbro_candidate_lighthouse.sh`
- Create: `tests/deploy-chickenbro-candidate.test.js`
- Modify: `docs/chickenbro-simc-production-runbook.md`

**Interfaces:**
- Candidate root `/opt/chickenbro-candidate`, candidate DB `chickenbro_candidate`, candidate API port 8791, public candidate prefix `/api/v2-candidate/`; production target root `/opt/chickenbro`, API 8790.

- [ ] **Step 1: Write failing exact deployment contract tests**

Tests require content-addressed source archive, candidate-only DSN, no `0040` migration, `WOW_DEPLOY_START_ASYNC_SYNCS=0`, rollback trap, file-hash parity, Nginx syntax, systemd readiness, and formal `/me`, Chat, SimC smokes. Tests reject calls to prototype, legacy sync timers, or `wow_test` mutation.

- [ ] **Step 2: Run and verify missing deployment files**

Run: `node --test tests/deploy-chickenbro-candidate.test.js`

- [ ] **Step 3: Implement candidate deployment**

Deploy only the formal application/product migrations/H5 build/services, preserve existing public production routing, run full migration against candidate with a captured read-only watermark, and record branch/commit/deployed hashes, DB migration identity, API/Worker/runtime identity, and rollback path.

- [ ] **Step 4: Run automated candidate acceptance**

Use two session transports for the same test user and a second isolated user. Prove Mini-created/Web-visible and Web-created/Mini-visible conversation/message and SimC job/result paths, logout independence, ticket replay rejection, and owner isolation. Redact identifiers in evidence.

- [ ] **Step 5: Run real user acceptance**

Build/open the official Mini Program candidate, ensure `pages/auth/web-login-confirm` is available in the tested release environment, scan the real Web QR, confirm in Mini, and have the user verify cross-client Chat and SimC history. Record only acceptance status, tested commit/build identity, timestamps, route names, and redacted object hashes.

- [ ] **Step 6: Commit candidate evidence preparation**

```bash
node --test tests/deploy-chickenbro-candidate.test.js
git add server/chickenbro-*.service server/chickenbro-web.nginx \
  server/deploy_chickenbro_candidate_lighthouse.sh tests/deploy-chickenbro-candidate.test.js \
  docs/chickenbro-simc-production-runbook.md
git commit -m "ops: add isolated Chickenbro candidate deployment"
```

### Task 6: Fenced production migration and cutover

**Files:**
- Create: `server/cutover_chickenbro_lighthouse.sh`
- Create: `tests/cutover-chickenbro.test.js`
- Create: `artifacts/releases/2026-09-02-chickenbro-simc-dual-client-cutover/requirement.json`
- Create: `artifacts/releases/2026-09-02-chickenbro-simc-dual-client-cutover/evidence.json`
- Create: `artifacts/releases/2026-09-02-chickenbro-simc-dual-client-cutover/manifest.json`
- Modify: `docs/project-state.json`

**Interfaces:**
- Mutation requires `--apply --candidate-commit <40-char-sha> --inventory-sha <sha256> --backup-manifest-sha <sha256>`.
- Produces exact `writeFenceAt`, full/delta watermarks, first-new-write state, Nginx/service/DSN identities, and rollback classification.

- [ ] **Step 1: Write failing cutover-state-machine tests**

```js
assert.match(script, /preflight -> write_fenced -> delta_migrated -> switched -> accepted_write/)
assert.match(script, /legacy_read_only/)
assert.match(script, /FIRST_NEW_WRITE/)
assert.doesNotMatch(script, /FIRST_NEW_WRITE[\s\S]*legacy_writable/)
```

- [ ] **Step 2: Run and verify failure**

Run: `node --test tests/cutover-chickenbro.test.js`

- [ ] **Step 3: Implement exact cutover and pre-write rollback**

Preflight rechecks capacity, independent restore-verified backup, candidate acceptance, migration reconciliation, Git/deployed parity, WeChat/Web build identity, and rollback files. Stop legacy writers and v2 Worker, capture fence watermarks, run/reconcile delta, switch Nginx/API/Worker to `chickenbro_prod`, then run read-only/auth/owner smokes. Before the first accepted write, any failure restores old Nginx/services and writable legacy DB.

- [ ] **Step 4: Enforce post-write recovery boundary**

After the first new Chat/SimC production write, persist `accepted_write` state. Later failure rolls back code within the new data plane or serves legacy read-only maintenance; the script has no path that makes `wow_test` writable while new writes exist.

- [ ] **Step 5: Execute production cutover only after real acceptance**

Run the reviewed script with exact hashes, then verify `/health`, `/api/v2/health/readiness`, `/api/v2/me`, real Mini login, real Web QR confirmation, shared Chat, shared SimC, owner isolation, Worker/queue, Nginx/TLS, service restarts, database sessions, and deployed hashes. Keep all legacy services/data intact but stopped/read-only for Phase 6 rollback.

- [ ] **Step 6: Seal evidence and commit**

```bash
node --test tests/cutover-chickenbro.test.js
git add server/cutover_chickenbro_lighthouse.sh tests/cutover-chickenbro.test.js \
  artifacts/releases/2026-09-02-chickenbro-simc-dual-client-cutover docs/project-state.json
git commit -m "ops: cut over Chickenbro Chat and SimC"
```

Phase 5 is complete only after real Mini/Web user acceptance, fenced migration reconciliation, production cutover, first-write evidence, and post-cutover shared-history verification. Legacy remains retained but stopped until Phase 6.
