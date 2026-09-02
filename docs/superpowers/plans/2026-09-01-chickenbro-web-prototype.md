# Chickenbro Web Prototype Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with review checkpoints.

**Goal:** 在既有 v2 平台与正式 Web 登录基础上，交付一个不强制正式登录、但具备隔离 prototype owner 的 H5 Web Chickenbro + 真实角色 SimC 原型，并完成候选及公网 smoke。

**Architecture:** 继续使用 `apps/mini-taro` 的 H5 root mount；WebApp 默认进入 prototype shell，正式二维码登录保留为次级入口。新增 `/api/v2/prototype/*`，通过服务端生成的短期 prototype capability 映射到 `identity.users(account_kind=prototype)`，复用 v2 chat/simc/ops 表和 owner 条件，拒绝正式 `/api/v2/me`/Cookie 依赖。Chickenbro 走原生 Codex adapter，SimC 走链接 Router → `CharacterSnapshot` → readiness → compiler → Worker → 云端 runtime。

**Tech Stack:** FastAPI、Pydantic、PostgreSQL、Python Worker、原生 Codex CLI、HTTPX、React/Taro H5、TypeScript typed client、Vitest、Python unittest、现有 Nginx/systemd candidate deploy。

**Spec:** `docs/superpowers/specs/2026-09-01-chickenbro-web-prototype-design.md`

## Global Constraints

- Prototype bypass 不是正式登录；Web 不强制 `/api/v2/me` 或 Web Cookie，正式二维码登录接口和确认页继续保留。
- Prototype token 只存在当前 tab `sessionStorage`；服务端只存 token hash，客户端永远不提交或接收内部 `user_id`。
- 所有 prototype chat、snapshot、job、result 必须绑定 prototype owner；正式用户历史不得包含 prototype 数据。
- Chickenbro 只允许原生 Codex；Codex 不可用、超时或输出非法时必须显式失败，禁止普通 LLM、模板或静默 fallback。
- SimC 只接受真实来源快照；`generated`、`preview`、HTTP 200、进程 exit code 0 或 Candidate 都不能单独构成成功。
- 不修改旧 14 路由业务合同、旧 `/api/*`、旧 `/websim`、Active Manifest、正式登录协议或 TLS 证书配置。
- 不安装依赖、下载第三方文件或触发外部网络写入，直到用户明确授权；远程上线只使用仓库已有部署路径。
- 保留当前 worktree 外的 `codex/chickenbro-simc-platform-foundation` worktree 和原分支；不 reset、clean、force push 或删除。

---

### Task 1: Register the approved Web prototype scope

**Files:**
- Modify: `docs/plans/README.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/project-owner-map.json`
- Modify: `docs/backend-owner-map.json`
- Create: `docs/superpowers/specs/2026-09-01-chickenbro-web-prototype-design.md`
- Create: `docs/superpowers/plans/2026-09-01-chickenbro-web-prototype.md`
- Test: `tests/project-owner-map.test.js`

**Interfaces:**
- Produces the scoped Web prototype spec and a whitelisted current execution plan.
- Keeps the previous Web login design as a preserved formal-login capability rather than the prototype entry gate.

- [x] **Step 1: Record the approved scope and boundaries**

  Add the prototype spec with the user journey, principal isolation, Chat/SimC API contracts, acceptance criteria, compatibility rules, and rollback plan. Link it from the current-plan index and roadmap without rewriting historical evidence.

- [ ] **Step 2: Run the documentation/owner-map contract test**

  Run: `node --test tests/project-owner-map.test.js`

  Expected: PASS, with the new plan/spec reachable from the current execution index.

- [ ] **Step 3: Check the documentation diff**

  Run: `git diff --check -- docs/plans/README.md docs/roadmap.md docs/superpowers/specs/2026-09-01-chickenbro-web-prototype-design.md docs/superpowers/plans/2026-09-01-chickenbro-web-prototype.md`

  Expected: exit 0 and no whitespace errors.

---

### Task 2: Add isolated prototype identity and request dependencies

**Files:**
- Create: `server/migrations/postgres/0040_web_prototype_sessions.sql`
- Modify: `server/app/identity/domain.py`
- Modify: `server/app/identity/ports.py`
- Modify: `server/app/identity/repository.py`
- Create: `server/app/identity/prototype.py`
- Modify: `server/app/api/dependencies.py`
- Create: `server/app/api/routes/prototype.py`
- Modify: `server/app/api/routes/__init__.py`
- Modify: `server/app/main.py`
- Test: `tests/app_prototype_identity_domain_test.py`
- Test: `tests/app_prototype_identity_application_test.py`
- Test: `tests/app_prototype_api_test.py`
- Test: `tests/app_schema_test.py`

**Interfaces:**
- `PrototypePrincipal(user_id: UUID, session_id: UUID, session_kind: Literal['prototype'])`.
- `PrototypeIdentityApplication.create_session(now) -> PrototypeSessionIssued`.
- `PrototypeIdentityApplication.resolve(token, now) -> PrototypePrincipal | None`.
- `PrototypeIdentityApplication.revoke(principal, now) -> None`.
- `require_prototype_principal(request) -> PrototypePrincipal`.
- `POST /api/v2/prototype/sessions -> {sessionToken, expiresAt, requestId, mode:'prototype'}`.
- `POST /api/v2/prototype/sessions/revoke -> {revoked:true, requestId}`.

- [ ] **Step 1: Write failing domain tests**

  Add tests proving that a prototype token is hashed, expiry and revocation are enforced, the raw token is not stored in the domain object, and a prototype principal is distinct from `mini_bearer` and `web_cookie`.

- [ ] **Step 2: Run the domain tests to verify RED**

  Run: `python3 -m unittest tests.app_prototype_identity_domain_test -v`

  Expected: FAIL because the prototype domain types and transitions do not exist.

- [ ] **Step 3: Add the additive PostgreSQL schema**

  Add `identity.users.account_kind` with `formal|prototype`, default `formal`; add `identity.prototype_sessions` with token hash, internal user id, expiry, revoke time, and timestamps; add indexes and `wow_app` grants. Register migration `0040_web_prototype_sessions` in `ops.schema_migrations`. Do not alter the legacy identity tables or migration 0039 semantics.

- [ ] **Step 4: Implement the identity application and repository**

  Create server-generated owner/user/session ids, issue a high-entropy token once, store only SHA-256, resolve only active non-expired non-revoked prototype rows, and reject formal sessions at the prototype dependency. Do not expose `user_id` in the HTTP payload.

- [ ] **Step 5: Add the prototype session API**

  Register the session routes under `/api/v2/prototype`, return a public `mode:'prototype'` marker, and map invalid/expired/revoked tokens to stable 401 errors. The create route is the only unauthenticated write; all business routes require the resulting capability.

- [ ] **Step 6: Run the identity tests to verify GREEN**

  Run: `python3 -m unittest tests.app_prototype_identity_domain_test tests.app_prototype_identity_application_test tests.app_prototype_api_test tests.app_schema_test -v`

  Expected: PASS with no raw token or internal owner id in response fixtures.

---

### Task 3: Implement the v2 Chickenbro Codex-only stream

**Files:**
- Create: `server/app/chickenbro/repository.py`
- Create: `server/app/chickenbro/application.py`
- Create: `server/app/chickenbro/codex_adapter.py`
- Create: `server/app/chickenbro/stream.py`
- Modify: `server/app/api/routes/prototype.py`
- Modify: `server/app/chickenbro/ports.py`
- Modify: `server/app/chickenbro/domain.py`
- Test: `tests/app_chickenbro_domain_test.py`
- Test: `tests/app_chickenbro_application_test.py`
- Test: `tests/app_chickenbro_stream_test.py`
- Test: `tests/app_chickenbro_owner_isolation_test.py`
- Test: `tests/codex_worker_test.py`

**Interfaces:**
- `PrototypeChatApplication.create_conversation(principal, title) -> ConversationView`.
- `PrototypeChatApplication.load_conversation(principal, conversation_id) -> ConversationView`.
- `PrototypeChatApplication.stream_message(principal, conversation_id, content, client_message_id, idempotency_key) -> Iterator[ChatEvent]`.
- `CodexChatPort.stream(prompt, timeout_seconds) -> Iterator[CodexStreamEvent]`.
- `ChatEvent` values: `started`, `delta`, `completed`, `failed`, each with `sequence`, `requestId`, and `conversationId`.
- `POST /api/v2/prototype/conversations/{id}/messages/stream` returns `text/event-stream`.

- [ ] **Step 1: Write failing stream and failure tests**

  Cover sequence monotonicity, assistant persistence only after `completed`, Codex unavailable/timeout/invalid output producing visible `failed`, and cross-owner conversation access returning 404/403 without leaking existence.

- [ ] **Step 2: Run the tests to verify RED**

  Run: `python3 -m unittest tests.app_chickenbro_domain_test tests.app_chickenbro_application_test tests.app_chickenbro_stream_test tests.app_chickenbro_owner_isolation_test -v`

  Expected: FAIL because the v2 chat application and repository do not exist.

- [ ] **Step 3: Add the Codex stream adapter**

  Wrap the existing native Codex command construction/runner boundary. The production adapter must refuse to start when the native Codex feature flag, binary, or profile is unavailable; parse JSONL agent-message deltas; bound prompt/history/output sizes; redact credentials; and map timeout/non-zero/empty output to stable public errors. It must never call `run_chickenbro_agent`, `call_chat_completion`, or any ordinary LLM fallback.

- [ ] **Step 4: Add owner-bound chat persistence**

  Implement repository methods for conversations, messages, and agent runs using `(user_id, aggregate_id)` constraints; preserve idempotent client messages; write user message and streaming run before invoking Codex; write assistant only on success; keep failed run diagnostics private and bounded.

- [ ] **Step 5: Add SSE serialization and prototype routes**

  Serialize only allowlisted public fields as SSE frames, start sequence at 1 for deltas, and close the stream after completed/failed. Conversation creation and reads use the prototype dependency and never accept a client owner id.

- [ ] **Step 6: Run the focused chat tests to verify GREEN**

  Run: `python3 -m unittest tests.app_chickenbro_domain_test tests.app_chickenbro_application_test tests.app_chickenbro_stream_test tests.app_chickenbro_owner_isolation_test tests.codex_worker_test -v`

  Expected: PASS; specifically assert that a Codex failure produces no assistant message and no fallback-model marker.

---

### Task 4: Implement source adapters, CharacterSnapshot readiness, compiler, and SimC application

**Files:**
- Create: `server/app/simulation/sources.py`
- Create: `server/app/simulation/snapshots.py`
- Create: `server/app/simulation/readiness.py`
- Create: `server/app/simulation/compiler.py`
- Create: `server/app/simulation/repository.py`
- Create: `server/app/simulation/application.py`
- Modify: `server/app/simulation/domain.py`
- Modify: `server/app/simulation/ports.py`
- Modify: `server/app/api/routes/prototype.py`
- Create: `tests/fixtures/character_sources/raiderio_ready.json`
- Create: `tests/fixtures/character_sources/wcl_incomplete.json`
- Create: `tests/app_simulation_sources_test.py`
- Create: `tests/app_simulation_readiness_test.py`
- Create: `tests/app_simulation_compiler_test.py`
- Create: `tests/app_simulation_application_test.py`

**Interfaces:**
- `CharacterSourceRouter.resolve(url, http_client) -> SourceSnapshot`.
- `RaiderIOCharacterAdapter.resolve(parsed_url) -> CharacterSnapshotCandidate`.
- `WclCharacterAdapter.resolve(parsed_url) -> CharacterSnapshotCandidate`.
- `SimcReadinessValidator.validate(snapshot, runtime_capabilities) -> ReadinessReport`.
- `SimcProfileCompiler.compile(snapshot, scenario) -> CompiledSimcInput`.
- `PrototypeSimulationApplication.resolve_source(principal, source_url) -> SourceSnapshotView`.
- `PrototypeSimulationApplication.submit(principal, snapshot_id, scenario, idempotency_key) -> SimulationJobView`.
- `PrototypeSimulationApplication.read_job(principal, job_id) -> SimulationJobView`.
- `POST /api/v2/prototype/source-snapshots`, `GET /api/v2/prototype/source-snapshots/{id}`, `POST /api/v2/prototype/simulations`, `GET /api/v2/prototype/simulations/{id}`.

- [ ] **Step 1: Write failing fixture tests**

  Assert allowed Raider.IO/WCL URLs route correctly, non-HTTPS/non-allowlisted URLs become `INVALID_LINK` without network access, ready fixture has provenance and raw hash, and incomplete WCL fixture exposes missing fields without being submit-ready.

- [ ] **Step 2: Run the source/readiness tests to verify RED**

  Run: `python3 -m unittest tests.app_simulation_sources_test tests.app_simulation_readiness_test tests.app_simulation_compiler_test -v`

  Expected: FAIL because the v2 source adapters, validator, and compiler are not implemented.

- [ ] **Step 3: Implement URL parsing and provider adapters**

  Use HTTPX through an injected read-only gateway. Reject redirects outside the allowlist, preserve provider/source URL/revision/fetched-at provenance, normalize provider fields into one source-independent candidate, and return `ACCESS_RESTRICTED`, `CHARACTER_NOT_FOUND`, or `SNAPSHOT_UNAVAILABLE` without exposing provider response bodies or credentials.

- [ ] **Step 4: Implement immutable snapshot and readiness validation**

  Persist one candidate revision with raw SHA-256 and provenance. Validate identity, class/spec/race, the Web prototype max-level policy (effective level 90), required gear semantics, talents, compiler support, and current runtime support. `generated` or `preview` inputs must result in `INCOMPLETE_FOR_SIMC` or `SNAPSHOT_UNAVAILABLE`, never `READY_FOR_SIMC`.

- [ ] **Step 5: Implement backend-owned compiler and submit application**

  Compile only from a persisted ready snapshot and scenario; store compiler/runtime revisions and scenario hash; enforce prototype owner and idempotency; enqueue a `simc` job with a snapshot reference rather than a client profile string. Re-read and validate readiness at submit time.

- [ ] **Step 6: Run the simulation application tests to verify GREEN**

  Run: `python3 -m unittest tests.app_simulation_sources_test tests.app_simulation_readiness_test tests.app_simulation_compiler_test tests.app_simulation_application_test -v`

  Expected: PASS, including blocked-link, incomplete-snapshot, generated-profile, owner-isolation, and ready-submit cases.

---

### Task 5: Connect the SimC Worker to the configured cloud runtime

**Files:**
- Create: `server/app/simulation/worker.py`
- Modify: `server/app/worker/handlers.py`
- Modify: `server/app/worker/main.py`
- Modify: `server/app/platform/config.py`
- Create: `tests/app_simulation_worker_test.py`
- Modify: `tests/app_worker_runtime_test.py`

**Interfaces:**
- `SimulationWorker.handle(job_id, worker_id) -> SimulationJobStatus`.
- `SimulationCraftPort.run(compiled_input, runtime_revision) -> RawSimulationExecution`.
- `SimulationResultParser.parse(execution) -> SemanticSimulationMetric | PublicSimulationFailure`.

- [ ] **Step 1: Write failing worker semantic tests**

  Cover queued-to-running lease ownership, timeout/failure, valid metric publication, missing metric rejection, profile hash/provenance, retry bounds, and no result publication for a process with exit code 0 but invalid output.

- [ ] **Step 2: Run the worker tests to verify RED**

  Run: `python3 -m unittest tests.app_simulation_worker_test tests.app_worker_runtime_test -v`

  Expected: FAIL because the SimC execution handler and semantic parser do not exist.

- [ ] **Step 3: Implement the cloud SimC port**

  Invoke the existing configured cloud/runtime boundary through an injected command or HTTP port; do not install or run SimC locally. Capture runtime identity, profile hash, bounded diagnostics, and parse a real primary metric. Respect the current Active runtime identity; do not switch Active Manifest or auto-promote Candidate.

- [ ] **Step 4: Implement lease-safe job handling**

  Claim only owned queued jobs, transition through the existing `ops.job_queue` lease contract, write attempts and immutable results under the prototype owner, and map parser/runtime errors to public `FAILED` codes without raw stdout.

- [ ] **Step 5: Run the worker tests to verify GREEN**

  Run: `python3 -m unittest tests.app_simulation_worker_test tests.app_worker_runtime_test -v`

  Expected: PASS with semantic-result assertions and no success on exit-code-only fixtures.

---

### Task 6: Add shared domain/client contracts and wire the Web shell

**Files:**
- Create: `packages/domain/src/web-prototype.ts`
- Modify: `packages/domain/src/index.ts`
- Create: `packages/api-client/src/web-prototype.ts`
- Modify: `packages/api-client/src/clients.ts`
- Modify: `packages/api-client/src/index.ts`
- Create: `apps/mini-taro/src/web/web-prototype-model.ts`
- Create: `apps/mini-taro/src/web/WebPrototypeApp.tsx`
- Create: `apps/mini-taro/src/web/WebPrototypeApp.module.scss`
- Modify: `apps/mini-taro/src/web/WebApp.tsx`
- Modify: `apps/mini-taro/src/web/WebApp.module.scss`
- Create: `packages/domain/src/web-prototype.test.ts`
- Create: `packages/api-client/src/web-prototype.test.ts`
- Create: `apps/mini-taro/src/web/web-prototype-model.test.ts`
- Modify: `apps/mini-taro/src/web/web-app-contract.test.ts`

**Interfaces:**
- `WebPrototypeClient.createSession() -> ApiResult<PrototypeSession>`.
- `WebPrototypeClient.createConversation() -> ApiResult<ConversationView>`.
- `WebPrototypeClient.streamMessage(...) -> AsyncGenerator<ChatStreamEvent>`.
- `WebPrototypeClient.resolveSource(url) -> ApiResult<SourceSnapshotView>`.
- `WebPrototypeClient.submitSimulation(...) -> ApiResult<SimulationJobView>`.
- `reducePrototypeState(state, event) -> PrototypeState`.

- [ ] **Step 1: Write failing contract/model tests**

  Assert the typed client never uses formal auth storage, sends only `X-Prototype-Session`, treats `READY_FOR_SIMC` as the sole submit-ready state, renders explicit Codex failures, and reduces refresh/reset/expired session states correctly.

- [ ] **Step 2: Run the TypeScript tests to verify RED**

  Run: `npx vitest run packages/domain/src/web-prototype.test.ts packages/api-client/src/web-prototype.test.ts apps/mini-taro/src/web/web-prototype-model.test.ts`

  Expected: FAIL because the contracts, client, and reducer do not exist.

- [ ] **Step 3: Implement domain and typed transport contracts**

  Add response guards for prototype session, conversation, SSE events, snapshot readiness, job status, and semantic result. Store the opaque session only in a dedicated session-storage key; never call `webAuth.me()` as an entry gate and never send formal Cookie/Bearer credentials to prototype routes.

- [ ] **Step 4: Implement the Web prototype UI**

  Make the existing H5 `WebApp` default to `WebPrototypeApp`. Keep the formal QR login panel reachable through a secondary action. Render the persistent bypass banner, isolation copy, reset action, chat bubbles/composer/stream error, source input, readiness blockers, job progress, and semantic result. Use no old 14-route UI or fake data.

- [ ] **Step 5: Run the client/UI tests to verify GREEN**

  Run: `npx vitest run packages/domain/src/web-prototype.test.ts packages/api-client/src/web-prototype.test.ts apps/mini-taro/src/web/web-prototype-model.test.ts apps/mini-taro/src/web/web-app-contract.test.ts`

  Expected: PASS with no formal login preflight and no generated SimC result path.

---

### Task 7: Candidate build, deploy, smoke, and evidence

**Files:**
- Modify: `server/deploy_web_v2_lighthouse.sh`
- Modify: `server/wow-v2-api.service`
- Create: `server/wow-v2-worker.service`
- Modify: `docs/remote-debugging.md`
- Create: `tests/deploy-web-v2-prototype.test.js`
- Create: `artifacts/releases/2026-09-01-chickenbro-web-prototype/requirement.json`
- Create: `artifacts/releases/2026-09-01-chickenbro-web-prototype/manifest.json`
- Create: `artifacts/releases/2026-09-01-chickenbro-web-prototype/evidence.json`

**Interfaces:**
- Candidate package includes the v2 API, additive migrations, Worker code, and `apps/mini-taro/dist/h5`.
- Deployment preserves the existing backup/rollback contract, starts the isolated SimC Worker separately from the API, and starts prototype capability only through an explicit environment flag.
- Evidence records commit identity, deployed tree/package hash, API/Worker/UI smoke results, known blocked states, and rollback target.

- [ ] **Step 1: Write failing deploy guard tests**

  Assert the deploy script requires the H5 build, 0038/0039/0040 migrations, v2 service, prototype flag, additive backup, checksum verification, and post-deploy checks for prototype session creation, unauthenticated `/api/v2/me` rejection, and legacy health.

- [ ] **Step 2: Run the deploy guard tests to verify RED**

  Run: `node --test tests/deploy-web-v2-prototype.test.js`

  Expected: FAIL until the deployment guard and smoke commands are wired.

- [ ] **Step 3: Add candidate packaging and rollback guards**

  Extend the existing script without changing its TLS certificate paths or legacy service. Keep PostgreSQL backup, static release symlink, service/Nginx restore, checksum validation, and explicit `WOW_WEB_PROTOTYPE_ENABLED` environment handling. Do not auto-run async data syncs or switch Active Manifest.

- [ ] **Step 4: Run local verification**

  Run after explicit dependency-install approval: `npm run typecheck`, `npm run test:taro`, `npm run audit:ui-architecture`, `npm run build:h5`, and the focused Python/Node suites from Tasks 2–6.

  Expected: all commands exit 0; any external provider/Codex/PG absence remains an explicit `blocked` or `UNVERIFIED` evidence state.

- [ ] **Step 5: Deploy the candidate through the existing path**

  Run the repository-owned candidate deployment only after the H5 build and local focused verification are green. The remote script must create a named backup, apply only additive migrations, install the candidate package, restart the isolated v2 service, and smoke `/`, `/health`, `/api/v2/health/readiness`, `/api/v2/prototype/sessions`, `/api/v2/me`, and legacy API health.

- [ ] **Step 6: Run post-deploy Web smoke**

  Verify via HTTPS that the page opens without a formal Cookie, the bypass banner is visible, prototype session reset isolates data, Codex failure is explicit when unavailable, initial SimC is blocked at “待输入”, and no legacy route/health regression is present. Verify live SimC only if a real ready snapshot and configured runtime are available; otherwise record the honest blocker.

- [ ] **Step 7: Review and record evidence**

  Run: `git diff --check`; local CR against the task spec and owner map; `node scripts/verify-project.js --profile full --release artifacts/releases/2026-09-01-chickenbro-web-prototype` using the complete task packet; then write evidence with runtime identity, candidate identity, rollback path, and unresolved blockers. Do not call a blocked/partial/unverified state “上线成功”。

---

## Completion Checklist

- [ ] Prototype bypass is visible and does not invoke formal `/api/v2/me` as a gate.
- [ ] Prototype owner isolation is tested at domain, API, repository, and UI storage levels.
- [ ] Chickenbro uses only native Codex and explicit failure semantics.
- [ ] Raider.IO/WCL adapters produce immutable source candidates and provenance.
- [ ] Only ready real snapshots reach the compiler and Worker.
- [ ] SimC success requires semantic metric plus runtime/compiler provenance.
- [ ] Existing 14 routes, old APIs/WebSim, Active Manifest, formal login, and TLS remain compatible.
- [ ] Local tests, H5 build, candidate smoke, HTTPS smoke, CR, rollback target, and release evidence are fresh.
