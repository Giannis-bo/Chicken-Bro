# Chickenbro-SimC Rebuild Phase 2 Identity and Clean Data Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bootstrap a clean `chickenbro_prod` schema and make Mini Bearer and Web HttpOnly sessions resolve safely to the same formal internal user.

**Architecture:** A new product-only migration lineage creates exactly `identity`, `chat`, `simc`, and `ops`; it never replays legacy migrations. Authentication remains in the existing modular application, adds `app_context` to the WeChat identity key, rejects mixed credentials, and applies exact-origin plus double-submit CSRF protection to Cookie-authenticated writes.

**Tech Stack:** PostgreSQL 14+, Python 3, FastAPI/Pydantic, psycopg-compatible repository layer, Node test harness, Bash deployment guards.

**Spec:** `docs/superpowers/specs/2026-09-02-chickenbro-simc-total-rebuild-design.md`

## Global Constraints

- `identity.users.id` is the only business owner.
- Formal WeChat identity uniqueness is `(provider='wechat_mini', app_context, provider_subject)`; UnionID is optional metadata and never required or guessed.
- Raw OpenID, `session_key`, Mini Bearer, Web Cookie, scene ticket, verifier, CSRF token, provider secret, and DSN never enter logs or audit payloads.
- Web and Mini credentials are independently issued/revoked; business APIs receive only `Principal(user_id, session_kind)`.
- Cookie-authenticated mutations require exact allowed origin and matching CSRF header/cookie; Mini mutations use Bearer and do not send Cookie credentials.
- The clean database contains no `app`, `content`, `cache`, `knowledge`, `analytics`, `websim`, prototype, gear, talent, or old auth-token objects.
- Provisioning is fail-closed while the capacity gate is blocked or an independent recovery target is absent.
- No dependency installation is allowed.

---

## File Structure

- Create `server/migrations/product/0001_chickenbro_simc_core.sql`: complete clean product schema.
- Create `server/migrations/product/apply.py`: ordered, transactional product migration runner.
- Create `tests/product_schema_test.py`: exact schema/table/privilege/forbidden-owner tests.
- Create `server/app/platform/csrf.py`: origin-bound double-submit CSRF checks.
- Modify `server/app/platform/{config,cookies,origin}.py`: formal allowed origin and Web/CSRF Cookie settings.
- Modify `server/app/identity/{domain,ports,repository,application}.py`: app-context identity and independent sessions.
- Modify `server/app/api/{dependencies,routes/auth}.py` and `server/app/main.py`: unambiguous Principal and audit wiring.
- Create `tests/app_identity_application_test.py`, `tests/app_identity_api_test.py`, `tests/app_csrf_test.py`: formal dual-session behavior and security tests.
- Create `server/provision_chickenbro_database_lighthouse.sh`: capacity/backup guarded database bootstrap.
- Create `tests/provision-chickenbro-database.test.js`: dry-run and fail-closed shell contract tests.
- Create `artifacts/releases/2026-09-02-chickenbro-simc-identity-data/{requirement,evidence,manifest}.json`.

### Task 0: Open the Strict Phase 2 requirement

**Files:**
- Create: `artifacts/releases/2026-09-02-chickenbro-simc-identity-data/requirement.json`
- Modify: `README.md`
- Modify: `docs/project-state.json`
- Modify: `docs/project-owner-map.json`
- Modify: `docs/backend-owner-map.json`
- Modify: `docs/roadmap.md`
- Modify: `docs/plans/README.md`
- Modify: `docs/verification-matrix.md`
- Modify: `docs/chickenbro-simc-production-runbook.md`
- Modify: `tests/project-state.test.js`

**Interfaces:**
- Consumes: sealed Phase 1 evidence, current capacity blocker and the approved Phase 2 plan.
- Produces: one `implementation_allowed` Strict requirement for local schema/Identity/API-security/dry-run work; candidate mutation remains separately false until capacity and independent recovery are proven.

- [x] **Step 1: Write a failing Phase 2 current-state test**

Assert Phase 1 evidence is sealed, Phase 2 is active, the task-scoped requirement exists, and `candidateDatabaseProvisioningAuthorized` remains false.

- [x] **Step 2: Update the control plane and write the requirement**

Mark Phase 1 `已完成`, Phase 2 `正在推进`, bind the requirement and retain the literal capacity/recovery blocker in state, roadmap, owner maps and verification matrix.

- [x] **Step 3: Verify and commit before product implementation**

```bash
node --test tests/project-state.test.js tests/project-owner-map.test.js tests/backend-owner-map.test.js
node scripts/project-harness.js --check-requirement \
  --requirement-file artifacts/releases/2026-09-02-chickenbro-simc-identity-data/requirement.json
git add artifacts/releases/2026-09-02-chickenbro-simc-identity-data/requirement.json \
  README.md docs tests/project-state.test.js
git commit -m "chore: open dual-client identity data requirement"
```

### Task 1: Product-only PostgreSQL migration lineage

**Files:**
- Create: `server/migrations/product/0001_chickenbro_simc_core.sql`
- Create: `server/migrations/product/apply.py`
- Create: `tests/product_schema_test.py`

**Interfaces:**
- Consumes: a management DSN and runtime role name `wow_app`.
- Produces: `apply_product_migrations(connection, migration_dir) -> tuple[str, ...]` and exactly the target tables named in the approved spec.

- [x] **Step 1: Write a failing exact-owner schema test**

```python
EXPECTED = {
    "identity": {"users", "user_identities", "auth_sessions", "web_login_sessions"},
    "chat": {"conversations", "messages", "agent_runs"},
    "simc": {"source_snapshots", "simulation_jobs", "simulation_attempts", "simulation_results"},
    "ops": {"schema_migrations", "job_queue", "audit_events", "usage_counters"},
}
FORBIDDEN_SCHEMAS = {"app", "content", "cache", "knowledge", "analytics", "websim"}

def test_clean_product_sql_declares_only_target_owners(self):
    sql = Path("server/migrations/product/0001_chickenbro_simc_core.sql").read_text()
    for schema, tables in EXPECTED.items():
        for table in tables:
            self.assertIn(f"CREATE TABLE {schema}.{table}", sql)
    for schema in FORBIDDEN_SCHEMAS:
        self.assertNotIn(f"CREATE SCHEMA {schema}", sql)
```

- [x] **Step 2: Run the test and verify the missing migration failure**

Run: `python3 -m unittest tests.product_schema_test -v`

Expected: FAIL because the product migration does not exist.

- [x] **Step 3: Write the clean schema with explicit identity uniqueness**

```sql
CREATE TABLE identity.user_identities (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    provider text NOT NULL CHECK (provider = 'wechat_mini'),
    app_context text NOT NULL CHECK (length(app_context) BETWEEN 1 AND 128),
    provider_subject text NOT NULL CHECK (length(provider_subject) BETWEEN 1 AND 256),
    union_id text,
    profile_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider, app_context, provider_subject)
);
```

Copy the already verified Chat, SimC result immutability, and job-lease constraints from migrations `0038` and `0039`, then add bounded `ops.audit_events` and `ops.usage_counters`. `ops.audit_events` must include `event_type`, `subject_key`, bounded `payload_json`, `created_at`, and `UNIQUE (event_type, subject_key)` so Phase 5 can record idempotent migration mappings without another permanent table. Do not copy `0040`, `account_kind`, `prototype_sessions`, or any legacy schema.

- [x] **Step 4: Implement ordered transactional application**

```python
def apply_product_migrations(connection, migration_dir: Path) -> tuple[str, ...]:
    applied = []
    for path in sorted(migration_dir.glob("[0-9][0-9][0-9][0-9]_*.sql")):
        migration_id = path.stem
        if migration_is_applied(connection, migration_id):
            continue
        with connection.transaction():
            connection.execute(path.read_text(encoding="utf-8"))
            record_migration(connection, migration_id)
        applied.append(migration_id)
    return tuple(applied)
```

- [x] **Step 5: Verify SQL text and optional isolated PostgreSQL integration**

Run:

```bash
python3 -m unittest tests.product_schema_test -v
WOW_PG_TEST_DSN_V2="$WOW_PG_TEST_DSN_V2" python3 -m unittest tests.product_schema_test.ProductSchemaIntegrationTest -v
```

Expected: static tests PASS; integration runs only when the dedicated test DSN is already configured, otherwise reports SKIP rather than success.

- [x] **Step 6: Commit**

```bash
git add server/migrations/product tests/product_schema_test.py
git commit -m "feat: add clean Chickenbro SimC schema"
```

### Task 2: Formal WeChat identity and independent session resolution

**Files:**
- Modify: `server/app/identity/domain.py`
- Modify: `server/app/identity/ports.py`
- Modify: `server/app/identity/repository.py`
- Modify: `server/app/identity/application.py`
- Create: `tests/app_identity_application_test.py`
- Modify: `tests/app_identity_repository_test.py`

**Interfaces:**
- Consumes: `WechatIdentity(openid, unionid)` and `AppSettings.wechat_app_id` as `app_context`.
- Produces: `upsert_wechat_mini_identity(app_context: str, provider_subject: str, union_id: str | None, now: datetime) -> UUID`; `resolve_principal(credential, kind) -> Principal | None`.

- [ ] **Step 1: Write failing same-user and conflict tests**

```python
def test_mini_exchange_and_confirmed_web_exchange_share_one_user(self):
    mini = app.exchange_mini_code("wx-code")
    created = app.create_web_login(verifier, idempotency_key="login-request")
    app.confirm_mini_web_login(scene_ticket, mini.principal)
    web = app.exchange_web_login(created.session.id, verifier)
    self.assertEqual(mini.principal.user_id, web.principal.user_id)
    self.assertEqual(mini.principal.session_kind, "mini_bearer")
    self.assertEqual(web.principal.session_kind, "web_cookie")

def test_same_openid_in_different_app_contexts_is_not_guessed_as_one_user(self):
    first = repository.upsert_wechat_mini_identity("app-a", "openid", None, now)
    second = repository.upsert_wechat_mini_identity("app-b", "openid", None, now)
    self.assertNotEqual(first, second)
```

- [ ] **Step 2: Run focused identity tests and verify failure**

Run: `python3 -m unittest tests.app_identity_application_test tests.app_identity_repository_test -v`

Expected: FAIL on the new `app_context` signature and same-user flow.

- [ ] **Step 3: Implement exact identity upsert and conflict handling**

Use `INSERT ... ON CONFLICT (provider, app_context, provider_subject) DO UPDATE SET updated_at = EXCLUDED.updated_at RETURNING user_id`. If one provider identity is already attached to a different user, raise `IDENTITY_CONFLICT`; never merge on display name or UnionID. Continue storing only auth/session token hashes.

- [ ] **Step 4: Verify independent revocation**

Add tests proving Web logout revokes only `web_cookie`, Mini logout revokes only the presented `mini_bearer`, and either logout leaves Chat/SimC owner rows untouched.

- [ ] **Step 5: Run and commit**

```bash
python3 -m unittest tests.app_identity_application_test tests.app_identity_repository_test -v
git add server/app/identity tests/app_identity_application_test.py tests/app_identity_repository_test.py
git commit -m "feat: bind Mini and Web sessions to one formal user"
```

### Task 3: Unambiguous Principal plus exact-origin and CSRF protection

**Files:**
- Create: `server/app/platform/csrf.py`
- Modify: `server/app/platform/config.py`
- Modify: `server/app/platform/cookies.py`
- Modify: `server/app/platform/origin.py`
- Modify: `server/app/api/dependencies.py`
- Modify: `server/app/api/routes/auth.py`
- Modify: `server/app/main.py`
- Create: `tests/app_csrf_test.py`
- Create: `tests/app_identity_api_test.py`

**Interfaces:**
- Produces: `require_principal(request) -> Principal`, `require_mutating_principal(request) -> Principal`, `issue_csrf_token() -> str`, and `require_web_csrf(request, settings) -> None`.
- Cookie names: `__Host-chickenbro-session` HttpOnly and `__Host-chickenbro-csrf` JavaScript-readable; both Secure, SameSite=Lax, Path=/, no Domain.

- [ ] **Step 1: Write failing mixed-credential and CSRF tests**

```python
def test_bearer_and_cookie_together_are_rejected(self):
    response = client.get("/api/v2/me", headers={"Authorization": "Bearer mini"}, cookies={SESSION: "web"})
    self.assertEqual(response.status_code, 400)
    self.assertEqual(response.json()["error"]["code"], "AMBIGUOUS_AUTH")

def test_cookie_write_requires_matching_origin_header_and_csrf_cookie(self):
    response = client.post("/api/v2/auth/logout", headers={"Origin": allowed_origin, "X-CSRF-Token": "wrong"}, cookies={SESSION: "web", CSRF: "right"})
    self.assertEqual(response.status_code, 403)
    self.assertEqual(response.json()["error"]["code"], "CSRF_REJECTED")
```

- [ ] **Step 2: Run focused API tests and verify failure**

Run: `python3 -m unittest tests.app_csrf_test tests.app_identity_api_test -v`

Expected: FAIL because mixed-auth and CSRF dependencies do not exist.

- [ ] **Step 3: Implement constant-time double-submit verification**

```python
def require_web_csrf(request: Request, settings: AppSettings) -> None:
    require_web_origin(request, settings.web_origin)
    cookie = request.cookies.get(settings.web_csrf_cookie_name, "")
    header = request.headers.get("X-CSRF-Token", "")
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise CsrfRejectedError("CSRF_REJECTED")
```

`require_principal` must reject multiple credential transports, malformed Bearer syntax, a Mini token used as Cookie, and a Web token used as Bearer. `require_mutating_principal` calls CSRF only for `web_cookie` Principals.

- [ ] **Step 4: Add redacted auth audit events**

Audit payloads contain only event type, request ID, internal user ID when already authenticated, session kind, status code, timestamp, and coarse reason code. Tests must reject keys matching `token|cookie|openid|session_key|verifier|ticket|secret`.

- [ ] **Step 5: Run and commit**

```bash
python3 -m unittest tests.app_csrf_test tests.app_identity_api_test tests.app_identity_application_test tests.app_identity_repository_test -v
git add server/app/platform server/app/api server/app/main.py tests/app_csrf_test.py tests/app_identity_api_test.py
git commit -m "feat: secure formal dual-client authentication"
```

### Task 4: Capacity-guarded clean database provisioning

**Files:**
- Create: `server/provision_chickenbro_database_lighthouse.sh`
- Create: `tests/provision-chickenbro-database.test.js`
- Modify: `docs/chickenbro-simc-production-runbook.md`

**Interfaces:**
- Consumes: exact target `chickenbro_prod`, existing management role, `WOW_REBUILD_BACKUP_ROOT`, and `docs/refactor/chickenbro-simc-cloud-inventory.json`.
- Produces: dry-run JSON by default; mutation only with `--apply --inventory-sha <sha256> --backup-device <absolute-path>`.

- [ ] **Step 1: Write failing shell-contract tests**

```js
test('provisioning is dry-run by default and never drops wow_test', () => {
  const script = readFileSync('server/provision_chickenbro_database_lighthouse.sh', 'utf8')
  assert.match(script, /MODE="dry-run"/)
  assert.match(script, /TARGET_DATABASE="chickenbro_prod"/)
  assert.doesNotMatch(script, /DROP DATABASE[\s\S]*wow_test/i)
  assert.match(script, /blocked_until_independent_legacy_cleanup_or_storage_expansion/)
})
```

- [ ] **Step 2: Run and verify failure**

Run: `node --test tests/provision-chickenbro-database.test.js`

Expected: FAIL because the provisioning script does not exist.

- [ ] **Step 3: Implement preflight and apply gates**

The script must compare the reviewed inventory hash, check `df`/`pg_database_size` again, require the backup root to have a different device ID from PostgreSQL data, create a management-role dump and `pg_restore --list` validation, then create only `chickenbro_prod` and apply `server/migrations/product`. It must abort when the database already exists with an unexpected migration identity.

- [ ] **Step 4: Run dry-run and tests**

```bash
node --test tests/provision-chickenbro-database.test.js
bash server/provision_chickenbro_database_lighthouse.sh --dry-run
```

Expected: tests PASS; dry run emits no secret and makes no remote or local PostgreSQL mutation.

- [ ] **Step 5: Commit**

```bash
git add server/provision_chickenbro_database_lighthouse.sh \
  tests/provision-chickenbro-database.test.js docs/chickenbro-simc-production-runbook.md
git commit -m "ops: guard clean Chickenbro database provisioning"
```

### Task 5: Candidate verification and Strict phase packet

**Files:**
- Create: `artifacts/releases/2026-09-02-chickenbro-simc-identity-data/requirement.json`
- Create: `artifacts/releases/2026-09-02-chickenbro-simc-identity-data/evidence.json`
- Create: `artifacts/releases/2026-09-02-chickenbro-simc-identity-data/manifest.json`
- Modify: `docs/project-state.json`

**Interfaces:**
- Produces: candidate evidence for clean schema and dual-session identity; it does not authorize production DSN cutover.

- [ ] **Step 1: Revalidate the already-open Strict requirement**

Require clean-schema integration, identity conflict tests, session independence, mixed-credential rejection, Origin/CSRF tests, provisioning dry run, candidate DB identity, rollback path, and zero forbidden schemas.

- [ ] **Step 2: Run local verification**

```bash
python3 -m unittest tests.product_schema_test tests.app_identity_application_test \
  tests.app_identity_repository_test tests.app_identity_api_test tests.app_csrf_test -v
node --test tests/provision-chickenbro-database.test.js
node scripts/verify-project.js --profile backend \
  --release artifacts/releases/2026-09-02-chickenbro-simc-identity-data
```

- [ ] **Step 3: Provision and smoke the candidate only when preflight is green**

If capacity or independent backup remains blocked, record literal `blocked` and stop before `--apply`. Otherwise apply the product migration to the isolated candidate database, verify forbidden schemas are absent, issue Mini and Web sessions through a fake/provider-approved test identity, and prove both resolve to one user without printing identifiers.

- [ ] **Step 4: Local CR and evidence sealing**

Review SQL privileges, credential transport, Cookie attributes, CSRF, audit redaction, exact DB target, restore path, and candidate isolation. Then write/check the Harness packet and commit it.

```bash
git add artifacts/releases/2026-09-02-chickenbro-simc-identity-data docs/project-state.json
git commit -m "test: seal dual-client identity data evidence"
```

Phase 2 is complete only when the clean schema and dual-session identity are verified in an isolated candidate. Production continues using its previous DSN.
