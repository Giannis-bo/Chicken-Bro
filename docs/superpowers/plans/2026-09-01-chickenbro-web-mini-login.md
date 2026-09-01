# Chickenbro Public Web and Mini Login Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 在 https://www.chickenbro.cloud 交付一个可访问的 Web 原型，并用炸鸡队长微信小程序真实扫码、明确确认后为 Web 建立独立登录会话。

**Architecture:** 保留旧 server/news_backend.py、旧 API、14 条 Taro 业务路由和现有生产服务作为 LKG；新增模块化 v2 ASGI API、PostgreSQL identity session 表、微信小程序服务端 adapter、独立 H5 Web shell 和隐藏的小程序确认页。Web 通过同源 /api/v2 使用 HttpOnly Cookie，小程序通过 wx.login 换取独立短期 Bearer；两者只映射到同一个内部 user_id。

**Tech Stack:** Python 3.13-compatible FastAPI/Pydantic/Uvicorn/psycopg/httpx；Taro 4.2 + React 18 + TypeScript 5.9；Vitest 4；PostgreSQL；Nginx/systemd；现有 npm lockfile 和部署 runbook。

**Spec:** docs/superpowers/specs/2026-09-01-chickenbro-web-mini-login-design.md

## Global Constraints

- 公网入口固定为 https://www.chickenbro.cloud；Web 主路径是桌面优先的二维码登录原型。
- 二维码必须由服务端调用微信小程序码接口生成；凭据、access token、OpenID、UnionID、session_key、Cookie 和 DSN 不得进入客户端日志、业务 evidence 或仓库。
- Web 登录使用浏览器 verifier + 服务端 verifier hash + 短期一次性 scene ticket；scene ticket 不携带 user_id、OpenID、UnionID、token 或个人字段。
- Web Cookie 和小程序 Bearer 独立签发、独立撤销；共享的是内部 user_id 和业务数据，不是 Cookie、session_key 或微信 access token。
- 不实现微信网站应用 OAuth、snsapi_login、网站 AppID/AppSecret 或把 UnionID 作为必要前置条件。
- identity.users.id 是业务 owner；provider subject 只做服务端精确身份解析，不作为客户端 owner 字段。
- 现有 14 条 Taro 业务路由、四个 tab 顺序、Active Manifest、server/news_backend.py、server/wow-backend.service、旧 API 和现有生产 PostgreSQL 不被本功能切换或删除。
- pages/auth/web-login-confirm 是无 TabBar 的 auxiliary_auth 路由，不计入当前 14 条产品路由、视觉目标、activeRouteOwners 或一级导航。
- /api/v2 只由新的 v2 API 服务提供；不得把新路由追加到旧 wow-backend 或 server/news_backend.py。
- Web API 的浏览器状态写请求只接受精确的 https://www.chickenbro.cloud Origin；小程序 Bearer 调用不依赖 Web Origin。
- 生产默认 Web login session TTL 为 300 秒，Web auth session TTL 为 604800 秒；两项都由服务配置覆盖且有上下限校验。
- 生产 Cookie 使用 HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age，默认名称为 __Host-wow_v2，不设置 Domain。
- 本地/候选缺少 PG 或微信配置时只能显示 blocked/unconfigured；页面可达、HTTP 200、构建成功、systemd active 或假二维码都不能证明登录完成。
- PostgreSQL migration 必须是 additive、单事务、备份后执行；SQLite 不得成为 Web 登录运行时 fallback。
- 候选部署先于合入/正式切流；候选证据必须记录 branch/commit、文件 parity、migration、service/Nginx、API/UI smoke、回滚路径和真实扫码状态。
- 本任务不接入 Codex、Raider.IO、WCL、SimC 执行、付费、旧路由删除或业务数据迁移。

## File Structure and Ownership

### Shared contracts and clients

- Create packages/domain/src/web-auth.ts and its test — DTO/status/verifier validator。
- Modify packages/domain/src/index.ts — 导出 Web auth 类型和 validator。
- Create packages/api-client/src/web-auth.ts and its test — WebAuthClient、Cookie credentials 和显式 mini Bearer。
- Modify packages/api-client/src/transport.ts and its test — credentials 选项和 Web same-origin base resolver；旧 /wow-api 行为保持不变。
- Modify packages/api-client/src/clients.ts and index.ts — 暴露 wowApi.webAuth。

### Backend identity and API

- Modify server/app/platform/config.py — Web origin、Cookie、TTL、微信配置及安全校验；secret 使用 repr=False。
- Create server/app/platform/cookies.py and origin.py — Cookie 和精确 Origin 边界。
- Modify server/app/identity/domain.py and ports.py — digest、auth session、Web login ports；保留已有纯状态机。
- Create server/app/identity/application.py and repository.py — use case 与 psycopg identity repository。
- Create server/app/integrations/wechat_mini.py — jscode2session、app access token 缓存、小程序码 HTTP adapter。
- Modify server/app/api/errors.py; create dependencies.py and routes/auth.py; modify routes/__init__.py and main.py。
- Create server/migrations/postgres/0039_wechat_web_login_sessions.sql。
- Create tests/app_auth_domain_test.py, app_identity_repository_test.py, app_wechat_mini_test.py, app_auth_application_test.py；modify app_config_test.py, app_api_test.py, app_schema_test.py。

### H5 and mini-program surfaces

- Create apps/mini-taro/src/web/web-auth-model.ts and test — verifier/sessionStorage/UI state reducer。
- Create apps/mini-taro/src/web/WebApp.tsx, WebApp.module.scss and web-app-contract.test.ts。
- Create apps/mini-taro/src/pages/auth/web-login-confirm.tsx, config, style and test。
- Modify apps/mini-taro/src/app.tsx, src/app.config.ts and config/index.ts。
- Modify route-contract.test.ts, tests/project-owner-map.test.js and scripts/audit-ui-architecture.js to distinguish auxiliary auth from the 14 product routes。

### Deployment and control plane

- Create server/wow-v2-api.service, server/wow-v2-web.nginx and server/deploy_web_v2_lighthouse.sh。
- Create tests/deploy-web-v2.test.js。
- Modify docs/remote-debugging.md, docs/project-owner-map.json, docs/backend-owner-map.json, docs/plans/README.md and docs/roadmap.md。
- Create during verification artifacts/releases/2026-09-01-chickenbro-web-mini-login/requirement.json, evidence.json and manifest.json；evidence 只写公开状态、hash、request id 和脱敏环境结论。

## Implementation Tasks

### Task 0: Register the approved scope and preserve the 14-route boundary

**Files:**

- Modify docs/roadmap.md, docs/plans/README.md
- Modify docs/project-owner-map.json, docs/backend-owner-map.json
- Modify scripts/audit-ui-architecture.js
- Modify tests/project-owner-map.test.js
- Modify apps/mini-taro/src/pages/_shared/route-contract.test.ts

**Interfaces:**

- Consumes: approved spec at docs/superpowers/specs/2026-09-01-chickenbro-web-mini-login-design.md.
- Produces: owner map entry web_v2_auth, auxiliary route constant pages/auth/web-login-confirm, and an audit contract that still counts exactly 14 product routes.

- [ ] Step 1: Write the failing contract tests

Add this test:

~~~
const auxiliaryAuthRoute = 'pages/auth/web-login-confirm'

it('registers Web login confirmation as auxiliary, not as a product route', () => {
  const appConfig = fs.readFileSync(
    path.join(process.cwd(), 'apps/mini-taro/src/app.config.ts'),
    'utf8',
  )
  expect(appConfig).toContain(auxiliaryAuthRoute)
  expect(routePolicy.registeredRouteCount).toBe(14)
  expect(routeContracts.map((route) => route.targetPage)).not.toContain(auxiliaryAuthRoute)
})
~~~

For the JavaScript owner/audit checks, derive the product list with:

~~~
const auxiliaryAppRoutes = new Set(['pages/auth/web-login-confirm'])
const productRoutes = appConfig.pages.filter((route) => !auxiliaryAppRoutes.has(route))
~~~

- [ ] Step 2: Run the focused tests to verify the boundary fails

~~~
npm exec vitest run apps/mini-taro/src/pages/_shared/route-contract.test.ts
node --test tests/project-owner-map.test.js
~~~

Expected: the auxiliary route assertion fails because the route and filtering contract do not exist yet.

- [ ] Step 3: Add owner records and exact filtering

Change the roadmap Identity row to 正在推进 and link the spec and plan. Add web_v2_auth with fact owner server/app/identity/application.py, write owner server/app/identity/repository.py, user_visible_runtime release trigger, backend/frontend/full verification profiles, v2 runtime surfaces, rollback code_rollback plus data_restore, and mustNotChange entries for the legacy service, old API, 14 routes and Active Manifest. The architecture audit must run existing geometry/semantic checks on productRoutes and add a separate auxiliary route existence/no-tabbar check. WebApp.tsx is not part of the 14-route visual registry.

- [ ] Step 4: Run the focused tests to verify the boundary passes

~~~
npm exec vitest run apps/mini-taro/src/pages/_shared/route-contract.test.ts
node --test tests/project-owner-map.test.js
node scripts/audit-ui-architecture.js
~~~

Expected: product route count remains 14, auxiliary route is explicit, and old route owners remain unchanged.

- [ ] Step 5: Commit

~~~
git add docs/roadmap.md docs/plans/README.md docs/project-owner-map.json docs/backend-owner-map.json scripts/audit-ui-architecture.js tests/project-owner-map.test.js apps/mini-taro/src/pages/_shared/route-contract.test.ts
git commit -m "docs: register web login ownership boundary"
~~~

### Task 1: Define shared Web auth contracts and credential-aware transport

**Files:**

- Create packages/domain/src/web-auth.ts and web-auth.test.ts
- Modify packages/domain/src/index.ts
- Modify packages/api-client/src/transport.ts and transport.test.ts
- Create packages/api-client/src/web-auth.ts and web-auth.test.ts
- Modify packages/api-client/src/clients.ts and index.ts

**Interfaces:**

~~~
export interface WebAuthClient {
  createWebLoginSession(browserVerifier: string, idempotencyKey: string): Promise<ApiResult<WebLoginCreated>>
  statusWebLoginSession(sessionId: string, browserVerifier: string): Promise<ApiResult<WebLoginStatusResponse>>
  exchangeWebLoginSession(sessionId: string, browserVerifier: string): Promise<ApiResult<WebLoginExchangeResponse>>
  cancelWebLoginSession(sessionId: string, browserVerifier: string): Promise<ApiResult<WebLoginStatusResponse>>
  exchangeMiniCode(code: string): Promise<ApiResult<MiniExchangeResponse>>
  confirmMiniWebLogin(sceneTicket: string, accessToken: string): Promise<ApiResult<ConfirmResponse>>
  me(): Promise<ApiResult<MeResponse>>
  logout(): Promise<ApiResult<LogoutResponse>>
}
~~~

WebLoginCreated is sessionId + expiresAt + qrDataUrl and never scene ticket. Status is one of pending, confirmed, expired, cancelled or exchanged. MeResponse contains only safe display name/connected state.

- [ ] Step 1: Write failing contract tests

~~~
it('rejects a Web response that exposes a scene ticket or non-PNG QR', () => {
  expect(isWebLoginCreated({
    sessionId: validUuid,
    expiresAt: validDate,
    qrDataUrl: 'data:image/png;base64,AA==',
  })).toBe(true)
  expect(isWebLoginCreated({
    sessionId: validUuid,
    expiresAt: validDate,
    sceneTicket: 'raw',
  })).toBe(false)
  expect(isWebLoginCreated({
    sessionId: validUuid,
    expiresAt: validDate,
    qrDataUrl: 'placeholder',
  })).toBe(false)
})
~~~

The client test records the transport call and asserts auth is false, credentials is include, Authorization is absent for me/status/create/exchange/cancel/logout, and create forwards Idempotency-Key. The mini confirm test asserts explicit Bearer and credentials omit.

- [ ] Step 2: Run tests to verify they fail

~~~
npm exec vitest run packages/domain/src/web-auth.test.ts packages/api-client/src/web-auth.test.ts packages/api-client/src/transport.test.ts
~~~

Expected: missing validator/client/credentials behavior fails.

- [ ] Step 3: Implement validators, client and transport option

Extend RequestOptions with credentials values omit, same-origin and include; pass it to Taro.request with omit as the default. Add a Web auth base resolver returning window.location.origin in H5 and the configured HTTPS API origin in WeApp; leave old h5ApiBaseUrl and /wow-api behavior unchanged. All Web client methods use auth false. Only mini confirm sets an explicit Authorization header and uses credentials omit. Use structured-problem mode so 401/409/410 remain observable to the Web state machine.

- [ ] Step 4: Run tests and typecheck

~~~
npm exec vitest run packages/domain/src/web-auth.test.ts packages/api-client/src/web-auth.test.ts packages/api-client/src/transport.test.ts
npm run typecheck
~~~

Expected: focused tests and existing auth transport tests pass.

- [ ] Step 5: Commit

~~~
git add packages/domain/src packages/api-client/src
git commit -m "feat: add typed web login client contract"
~~~

### Task 2: Add v2 identity persistence and the real WeChat mini adapter

**Files:**

- Create server/migrations/postgres/0039_wechat_web_login_sessions.sql
- Modify server/app/platform/config.py, identity/domain.py and identity/ports.py
- Create server/app/platform/cookies.py, platform/origin.py, identity/repository.py and integrations/wechat_mini.py
- Create tests/app_auth_domain_test.py, tests/app_identity_repository_test.py, tests/app_wechat_mini_test.py
- Modify tests/app_config_test.py and tests/app_schema_test.py

**Interfaces:**

~~~
@dataclass(frozen=True)
class PublicUser:
    user_id: UUID
    display_name: str

@dataclass(frozen=True)
class WechatIdentity:
    openid: str
    unionid: str | None = None

@dataclass(frozen=True)
class IssuedSession:
    token: str
    expires_at: datetime
    principal: Principal

@dataclass(frozen=True)
class WebLoginCreated:
    session: WebLoginSession
    qr_data_url: str

@dataclass(frozen=True)
class WebLoginStatusView:
    status: WebLoginSessionStatus
    expires_at: datetime

@dataclass(frozen=True)
class MeView:
    connected: bool
    display_name: str

class IdentityRepository(Protocol):
    def upsert_wechat_mini_identity(self, *, provider_subject: str, now: datetime) -> UUID: ...
    def issue_auth_session(self, *, token_hash: str, user_id: UUID, kind: SessionKind, expires_at: datetime) -> None: ...
    def resolve_auth_session(self, *, token_hash: str, kind: SessionKind, now: datetime) -> Principal | None: ...
    def revoke_auth_session(self, *, token_hash: str, kind: SessionKind, now: datetime) -> None: ...
    def insert_web_login_session(self, session: WebLoginSession, *, now: datetime) -> None: ...
    def get_web_login_session(self, *, session_id: UUID, for_update: bool = False) -> WebLoginSession | None: ...
    def save_web_login_session(self, session: WebLoginSession, *, now: datetime) -> None: ...
    def get_public_user(self, user_id: UUID) -> PublicUser | None: ...

class WechatMiniGateway(Protocol):
    def exchange_code(self, code: str) -> WechatIdentity: ...
    def create_mini_code(self, *, scene: str, page: str, env_version: str) -> bytes: ...
~~~

- [ ] Step 1: Write failing migration/domain/adapter tests

Require the migration to contain:

~~~
CREATE TABLE IF NOT EXISTS identity.auth_sessions
CREATE TABLE IF NOT EXISTS identity.web_login_sessions
kind IN ('mini_bearer', 'web_cookie')
status IN ('pending', 'confirmed', 'exchanged', 'cancelled', 'expired')
scene_ticket_sha256
browser_verifier_sha256
0039_wechat_web_login_sessions
~~~

Adapter tests inject a fake HTTP client and assert AppID use, no Secret in logs, JSON errors are not accepted as PNG, and missing config maps to WECHAT_NOT_CONFIGURED.

- [ ] Step 2: Run tests to verify they fail

~~~
python3 -m unittest tests.app_auth_domain_test tests.app_identity_repository_test tests.app_wechat_mini_test tests.app_config_test tests.app_schema_test
~~~

Expected: new modules and migration clauses are absent.

- [ ] Step 3: Implement additive schema and configuration

Create identity.auth_sessions with token hash primary key, user_id foreign key, kind, issue/expiry/revocation timestamps and metadata. Create identity.web_login_sessions with UUID id, unique lowercase SHA-256 scene digest, browser verifier digest, nullable idempotency-key digest, nullable user, status, expiry, exchange and update timestamps. Scope the idempotency uniqueness to the verifier digest and never persist the raw key. Grant only required CRUD to wow_app and register the migration in ops.schema_migrations; do not alter identity.auth_tokens or old tables.

Add these environment fields: WOW_WEB_ORIGIN, WOW_WEB_COOKIE_NAME, WOW_WEB_LOGIN_TTL_SECONDS, WOW_WEB_SESSION_TTL_SECONDS, WOW_WECHAT_APPID, WOW_WECHAT_SECRET, WOW_WECHAT_PAGE and WOW_WECHAT_ENV_VERSION. Validate production HTTPS origin, loopback API binding, TTL bounds 60..900 and 300..2592000, page path without a leading slash and cookie name beginning with __Host-. Keep database_url and wechat_secret hidden from repr.

- [ ] Step 4: Implement digest, repository, security helpers and adapter

Use:

~~~
def digest(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()

def new_opaque_token(byte_length: int = 32) -> str:
    return secrets.token_urlsafe(byte_length)
~~~

upsert_wechat_mini_identity queries only provider wechat_openid and exact provider_subject, creates a fresh UUID user when absent, handles the unique conflict transactionally and ignores optional UnionID for identity merging. Repository status changes use SELECT FOR UPDATE and map rows to digest-only domain objects. WechatMiniClient uses injected httpx.Client, caches the app access token in process memory until expiry minus 60 seconds, calls cgi-bin/token and wxa/getwxacodeunlimit, validates image/png and returns only PNG bytes.

- [ ] Step 5: Run focused tests and static checks

~~~
python3 -m unittest tests.app_auth_domain_test tests.app_identity_repository_test tests.app_wechat_mini_test tests.app_config_test tests.app_schema_test
python3 -m unittest tests.app_domain_test
git diff --check
~~~

Expected: digest-only state, owner-scoped SQL, secret redaction, additive migration and no legacy table mutation all pass.

- [ ] Step 6: Commit

~~~
git add server/app server/migrations/postgres/0039_wechat_web_login_sessions.sql tests/app_auth_domain_test.py tests/app_identity_repository_test.py tests/app_wechat_mini_test.py tests/app_config_test.py tests/app_schema_test.py
git commit -m "feat: add v2 identity sessions and WeChat adapter"
~~~

### Task 3: Implement v2 auth routes, Cookie exchange and app composition

**Files:**

- Create server/app/identity/application.py
- Modify server/app/api/errors.py
- Create server/app/api/dependencies.py and server/app/api/routes/auth.py
- Modify server/app/api/routes/__init__.py, server/app/main.py and server/app/platform/health.py
- Create tests/app_auth_application_test.py
- Modify tests/app_api_test.py

**Interfaces:**

~~~
class WebAuthApplication:
    def create_web_login(self, browser_verifier: str) -> WebLoginCreated: ...
    def get_web_login_status(self, session_id: UUID, browser_verifier: str) -> WebLoginStatusView: ...
    def confirm_mini_web_login(self, scene_ticket: str, principal: Principal) -> None: ...
    def exchange_web_login(self, session_id: UUID, browser_verifier: str) -> IssuedSession: ...
    def cancel_web_login(self, session_id: UUID, browser_verifier: str) -> WebLoginStatusView: ...
    def exchange_mini_code(self, code: str) -> IssuedSession: ...
    def me(self, principal: Principal) -> MeView: ...
    def logout(self, principal: Principal, raw_cookie: str | None) -> None: ...
~~~

Routes are exactly:

~~~
POST /api/v2/auth/wechat/mini/exchange
POST /api/v2/auth/wechat/web/login-sessions
GET  /api/v2/auth/wechat/web/login-sessions/{id}
POST /api/v2/auth/wechat/web/login-sessions/{id}/exchange
POST /api/v2/auth/wechat/web/login-sessions/{id}/cancel
POST /api/v2/auth/wechat/mini/web-login-confirm
POST /api/v2/auth/logout
GET  /api/v2/me
~~~

- [ ] Step 1: Write failing application and API tests

~~~
def test_web_exchange_sets_only_secure_http_only_cookie(self):
    client = self.build_client()
    created = client.post('/api/v2/auth/wechat/web/login-sessions', json={
        'browserVerifier': 'A' * 43,
    })
    self.assertEqual(created.status_code, 201)
    session_id = created.json()['sessionId']
    self.confirm_with_fake_mini(session_id)
    response = client.post(
        f'/api/v2/auth/wechat/web/login-sessions/{session_id}/exchange',
        headers={
            'X-Web-Login-Verifier': 'A' * 43,
            'Origin': 'https://www.chickenbro.cloud',
        },
    )
    self.assertEqual(response.status_code, 200)
    cookie = response.headers['set-cookie']
    self.assertIn('HttpOnly', cookie)
    self.assertIn('Secure', cookie)
    self.assertIn('SameSite=Lax', cookie)
    self.assertNotIn('openid', response.text.lower())
~~~

Add tests for missing/short verifier, wrong verifier, status hiding user, unconfigured WeChat returning WECHAT_NOT_CONFIGURED, mini confirm without Web Origin, exchange replay returning WEB_LOGIN_ALREADY_EXCHANGED, exact Origin rejection, unauthenticated /me, authenticated /me and independent mini/Web session kinds.

- [ ] Step 2: Run focused tests to verify they fail

~~~
python3 -m unittest tests.app_auth_application_test tests.app_api_test
~~~

Expected: missing application/routes/dependencies cause failure while /health tests still describe the existing liveness contract.

- [ ] Step 3: Implement application state machine and token ownership

For create, validate a 43--128 character base64url verifier, generate a 16-byte URL-safe scene ticket, call the gateway with pages/auth/web-login-confirm, then persist only both SHA-256 digests. Return sessionId, expiresAt and data:image/png;base64,...; never return raw scene.

For confirm/exchange/cancel, lock the row, compare digests with hmac.compare_digest, apply the existing domain transition and commit once. Exchange generates a fresh Web cookie token, inserts kind=web_cookie, then returns it to the route for set_cookie; it never returns the token in JSON. Mini exchange maps the exact mini OpenID to the internal user and returns a fresh kind=mini_bearer token only to the mini caller. Optional UnionID is not used to merge identities.

- [ ] Step 4: Implement public error and security dependencies

Add an ApiProblem exception with status_code, code and public message; register its handler before the generic handler. Preserve the existing request-id middleware so every success and error response includes the canonical requestId and X-Request-Id. Use these public codes:

~~~
AUTH_REQUIRED
ORIGIN_REJECTED
VALIDATION_ERROR
WEB_LOGIN_NOT_FOUND
WEB_LOGIN_EXPIRED
WEB_LOGIN_CANCELLED
WEB_LOGIN_VERIFIER_MISMATCH
WEB_LOGIN_ALREADY_EXCHANGED
WEB_LOGIN_NOT_CONFIRMED
WECHAT_NOT_CONFIGURED
WECHAT_PROVIDER_UNAVAILABLE
INTERNAL_ERROR
~~~

require_mini_principal reads only Authorization: Bearer; require_web_principal reads only the configured Cookie; neither accepts the other kind. Mutating browser routes call require_web_origin; mini routes do not. The create route requires a bounded Idempotency-Key, hashes it with the verifier digest, and returns the same still-valid session for an exact retry; transition routes rely on row locks and stable replay codes. Error payloads contain only error.code, error.message and requestId.

- [ ] Step 5: Wire the app and run API tests

create_app gains an optional web_auth_application injection parameter; when absent it composes the configured v2 repository and gateway without making a network call during app construction. Existing /health, readiness and generic 404 behavior remain unchanged. Add a readiness component wechat_mini that reports unconfigured when credentials are absent but never calls WeChat during a health probe.

~~~
python3 -m unittest tests.app_auth_application_test tests.app_api_test tests.app_config_test tests.app_domain_test
npm exec vitest run packages/api-client/src/web-auth.test.ts
~~~

Expected: v2 route tests pass, old health tests pass, and no API response contains provider identity or secret material.

- [ ] Step 6: Commit

~~~
git add server/app tests/app_auth_application_test.py tests/app_api_test.py
git commit -m "feat: expose v2 Web and mini auth routes"
~~~

### Task 4: Build the desktop-first Web/H5 prototype

**Files:**

- Create apps/mini-taro/src/web/web-auth-model.ts and web-auth-model.test.ts
- Create apps/mini-taro/src/web/WebApp.tsx, WebApp.module.scss and web-app-contract.test.ts
- Modify apps/mini-taro/src/app.tsx and apps/mini-taro/config/index.ts

**Interfaces:**

- Consumes: wowApi.webAuth, WebLoginStatusResponse, WebLoginCreated, MeResponse and WebAuthClient.
- Produces: H5 / with idle -> pending -> confirmed -> authenticated and honest blocked/expired/cancelled states; no legacy tab navigation or fake identity.

- [ ] Step 1: Write failing state and source contract tests

~~~
it('transitions only from a real QR response to pending', () => {
  expect(reduceWebAuthState(initialWebAuthState, { type: 'created', payload: validQr }))
    .toMatchObject({ phase: 'pending' })
  expect(reduceWebAuthState(initialWebAuthState, { type: 'created', payload: blockedQr }))
    .toMatchObject({ phase: 'blocked' })
})

it('keeps verifier in sessionStorage and never places it in the URL', () => {
  expect(source).toContain('sessionStorage')
  expect(source).toContain('crypto.getRandomValues')
  expect(source).not.toContain('browserVerifier=')
})
~~~

- [ ] Step 2: Run focused tests to verify they fail

~~~
npm exec vitest run apps/mini-taro/src/web/web-auth-model.test.ts apps/mini-taro/src/web/web-app-contract.test.ts
~~~

Expected: files and state reducer are absent.

- [ ] Step 3: Implement the pure browser state model

Use 32 random bytes encoded as base64url for the verifier. Reuse only the current tab's sessionStorage key chickenbro.web.login.verifier; never use localStorage, URL parameters, analytics fields or DOM text for it. Reducer events are created, status, authenticated, blocked and logout. created accepts only a valid PNG data URL; failed transport and invalid payload become blocked. Terminal phases clear polling state.

- [ ] Step 4: Implement WebApp.tsx and the intentional visual shell

The first viewport contains brand mark text, one sentence describing the two-domain product, a single “使用微信小程序登录” card, QR image after a real create response, remaining-time label, cancel/refresh actions and a clear “使用小程序确认” instruction. Authenticated state shows the connected account card plus two disabled-but-honest “队长” and “SimC” next-stage cards. Mobile layout states “请使用电脑或另一台设备展示二维码”，never claims that same-device scanning happened.

On mount call webAuth.me() with credentials include; 401 becomes idle, other transport failure becomes blocked. Create generates/stores verifier then calls the client. Poll status every 1500 ms only while pending/confirmed; after confirmed call exchange once. On exchange success call /me; on expired/cancelled/replay show the matching recovery action. Logout calls the client and returns to idle. Do not use wowApi.auth or legacy /api/auth/wechat-login.

- [ ] Step 5: Keep H5 routing isolated and run preview build

In app.tsx branch only on Taro.ENV_TYPE.WEB: H5 returns WebApp; WeApp returns the existing children and AppTabBar. In config/index.ts add a development proxy for /api to http://127.0.0.1:8790 and retain /wow-api unchanged. Use existing design-system tokens without modifying the 14 route styles.

~~~
npm exec vitest run apps/mini-taro/src/web apps/mini-taro/src/pages/_shared/route-contract.test.ts
npm run typecheck
npm --workspace @wow-mini/mini-taro run build:h5
~~~

Expected: H5 production build emits a real Web shell, no build error, and no old tab bar in H5 source composition; existing WeApp route contracts remain intact.

- [ ] Step 6: Commit

~~~
git add apps/mini-taro/src/web apps/mini-taro/src/app.tsx apps/mini-taro/config/index.ts
git commit -m "feat: add Chickenbro Web login prototype"
~~~

### Task 5: Add the real mini-program confirmation page without changing product navigation

**Files:**

- Create apps/mini-taro/src/pages/auth/web-login-confirm.tsx, web-login-confirm.config.ts, web-login-confirm.module.scss and web-login-confirm.test.ts
- Modify apps/mini-taro/src/app.config.ts
- Modify apps/mini-taro/src/pages/_shared/route-contract.test.ts, tests/project-owner-map.test.js and scripts/audit-ui-architecture.js

**Interfaces:**

- Consumes: Taro.useLoad route scene parameter, Taro.login(), wowApi.webAuth.exchangeMiniCode and wowApi.webAuth.confirmMiniWebLogin.
- Produces: one registered auxiliary_auth page with explicit confirmation and no TabBar, no database access and no provider data display.

- [ ] Step 1: Write failing page contract tests

~~~
it('uses Taro login and requires an explicit confirmation action', () => {
  expect(source).toContain('Taro.login')
  expect(source).toContain('confirmMiniWebLogin')
  expect(source).toContain('确认登录')
  expect(source).not.toContain('wx.getStorage')
  expect(source).not.toContain('WOW_WECHAT_SECRET')
})

it('is not a tab route or active visual target', () => {
  expect(tabBarItems.map((item) => item.pagePath))
    .not.toContain('pages/auth/web-login-confirm')
})
~~~

- [ ] Step 2: Run the test to verify it fails

~~~
npm exec vitest run apps/mini-taro/src/pages/auth/web-login-confirm.test.ts apps/mini-taro/src/pages/_shared/route-contract.test.ts
~~~

Expected: page and route are absent.

- [ ] Step 3: Implement the page flow

Read only the scene parameter supplied by WeChat. If absent, render WEB_LOGIN_SCENE_MISSING recovery. On load call Taro.login(), pass its short-lived code to exchangeMiniCode, retain the returned mini Bearer only in component memory and show the account confirmation copy. The button calls confirmMiniWebLogin(scene, accessToken) once; disable it while pending and replace the button with success or a public error/retry state. Never display OpenID, UnionID, nickname, access token or session_key.

- [ ] Step 4: Register only the auxiliary route and preserve contracts

Append this exact entry to pages without changing any existing route or tab list:

~~~
pages: [
  // existing 14 routes remain byte-for-byte ordered
  'pages/auth/web-login-confirm',
]
~~~

The route tests and architecture audit filter this path from 14 product route checks and assert that it has no tabBar membership and no target-registry entry.

- [ ] Step 5: Build WeApp and run contracts

~~~
npm exec vitest run apps/mini-taro/src/pages/auth/web-login-confirm.test.ts apps/mini-taro/src/pages/_shared/route-contract.test.ts
npm run typecheck
npm --workspace @wow-mini/mini-taro run build:weapp
~~~

Expected: generated app.json contains the auxiliary page and all page JS/JSON/WXML/WXSS files; current 14 product route checks stay exact.

- [ ] Step 6: Commit

~~~
git add apps/mini-taro/src/pages/auth apps/mini-taro/src/app.config.ts apps/mini-taro/src/pages/_shared/route-contract.test.ts tests/project-owner-map.test.js scripts/audit-ui-architecture.js
git commit -m "feat: add mini program Web login confirmation page"
~~~

### Task 6: Prepare isolated v2 candidate deployment and rollback assets

**Files:**

- Create server/wow-v2-api.service, server/wow-v2-web.nginx and server/deploy_web_v2_lighthouse.sh
- Create tests/deploy-web-v2.test.js
- Modify docs/remote-debugging.md

**Interfaces:**

- Consumes: built apps/mini-taro/dist/h5, tracked source tree, 0039 migration, existing remote wow-lighthouse alias and existing certificate paths discovered read-only.
- Produces: candidate deployment command that changes only v2 API/H5/static/migration; legacy API/service remains untouched.

- [ ] Step 1: Write failing deployment contract tests

~~~
test('v2 deployment is isolated from the legacy service', () => {
  const script = fs.readFileSync('server/deploy_web_v2_lighthouse.sh', 'utf8')
  assert.match(script, /wow-v2-api/)
  assert.match(script, /127\\.0\\.0\\.1:8790/)
  assert.doesNotMatch(script, /systemctl\\s+(?:restart|stop|disable).*wow-backend/)
  assert.doesNotMatch(script, /news_backend\\.py/)
})

test('Nginx template proxies only v2 API and serves the H5 root', () => {
  const nginx = fs.readFileSync('server/wow-v2-web.nginx', 'utf8')
  assert.match(nginx, /server_name\\s+www\\.chickenbro\\.cloud/)
  assert.match(nginx, /location\\s+\\^~\\s+\\/api\\/v2\\//)
  assert.match(nginx, /proxy_pass\\s+http:\\/\\/127\\.0\\.0\\.1:8790/)
  assert.match(nginx, /try_files\\s+\\$uri\\s+\\$uri\\//)
})
~~~

- [ ] Step 2: Run deployment tests to verify they fail

~~~
node --test tests/deploy-web-v2.test.js
~~~

Expected: new deployment assets are absent.

- [ ] Step 3: Implement the isolated service and Nginx template

wow-v2-api.service must use /opt/wow-mini-program/.venv-v2/bin/python -m uvicorn server.app.main:app, WOW_APP_ENV=production, WOW_API_V2_HOST=127.0.0.1, WOW_API_V2_PORT=8790 and EnvironmentFile=-/etc/wow-v2-api.env. It must not read /etc/wow-backend.env or start a worker. The Nginx template must redirect port 80 to HTTPS, use existing certificate paths found on the server, serve /var/www/chickenbro-web, add security headers, proxy /api/v2/ with Host/X-Forwarded headers and avoid Access-Control-Allow-Origin: *.

- [ ] Step 4: Implement backup-first candidate script

The script must validate remote host/user/paths and known host checking; package only the tracked source needed by v2; create/update .venv-v2 from server/requirements-v2.txt without changing the legacy environment; require /etc/wow-v2-api.env mode 0600 without echoing values; back up the v2 service, env, Nginx site and target database into a run-id directory; apply 0039 with psql --single-transaction --set ON_ERROR_STOP=1; install assets; run nginx -t; reload only the v2 service/Nginx; and verify loopback /health, /api/v2/health/readiness, the www static root and unauthenticated /api/v2/me. On failure restore only the named v2 service/Nginx/env assets and preserve the database backup. Do not delete unrelated LKG files or restore SQLite.

- [ ] Step 5: Add candidate evidence fields and run static deployment tests

~~~
bash -n server/deploy_web_v2_lighthouse.sh
node --test tests/deploy-web-v2.test.js tests/deploy_lighthouse.test.js tests/deploy-script.test.js
git diff --check
~~~

Expected: v2 script passes shell/static tests and existing legacy deployment tests remain unchanged.

- [ ] Step 6: Commit

~~~
git add server/wow-v2-api.service server/wow-v2-web.nginx server/deploy_web_v2_lighthouse.sh tests/deploy-web-v2.test.js docs/remote-debugging.md
git commit -m "ops: prepare isolated Web v2 candidate deployment"
~~~

### Task 7: Complete local verification, candidate smoke and delivery evidence

**Files:**

- Modify docs/verification-matrix.md
- Modify docs/project-owner-map.json and docs/backend-owner-map.json
- Create artifacts/releases/2026-09-01-chickenbro-web-mini-login/requirement.json, evidence.json and manifest.json

**Interfaces:**

- Consumes: all previous task outputs, H5/WeApp builds, candidate deployment and user-controlled real mini-program scan.
- Produces: evidence packet whose status distinguishes local_verified, candidate_pending, live_verified, blocked and user_acceptance_pending; no live success claim without real QR scan and click confirmation.

- [ ] Step 1: Run the complete local verification ladder

~~~
python3 -m unittest \
  tests.app_auth_domain_test \
  tests.app_identity_repository_test \
  tests.app_wechat_mini_test \
  tests.app_auth_application_test \
  tests.app_api_test \
  tests.app_config_test \
  tests.app_schema_test \
  tests.app_domain_test

npm run typecheck
npm run lint
npm exec vitest run packages/domain/src packages/api-client/src apps/mini-taro/src/web apps/mini-taro/src/pages/auth apps/mini-taro/src/pages/_shared/route-contract.test.ts
npm --workspace @wow-mini/mini-taro run build:h5
npm --workspace @wow-mini/mini-taro run build:weapp
node scripts/audit-ui-architecture.js
git diff --check
~~~

Expected: local code/build contracts pass; if PostgreSQL/WeChat is absent, evidence explicitly records blocked/unconfigured integration rather than success.

- [ ] Step 2: Create the local evidence packet

requirement.json names the exact spec and public acceptance criteria. manifest.json contains branch, HEAD, changed tracked file hashes and build output hashes. evidence.json records each check with status, evidenceLevel, command, result, requestId where applicable and sensitiveValuesLogged=false; it contains no DSN, token, QR payload, OpenID or UnionID.

- [ ] Step 3: Deploy a candidate with the isolated script

Before deployment, record git status --short --branch, diff review, exact remote target, PostgreSQL backup path and v2 env backup path. Run the v2 script with async legacy syncs disabled. Verify:

~~~
curl -fsS https://www.chickenbro.cloud/
curl -fsS https://www.chickenbro.cloud/api/v2/health/readiness
curl -i -fsS https://www.chickenbro.cloud/api/v2/me
ssh wow-lighthouse 'sudo systemctl status wow-v2-api --no-pager'
ssh wow-lighthouse 'sudo nginx -t'
ssh wow-lighthouse 'curl -fsS http://127.0.0.1:8790/health'
~~~

Expected: page/static/health are reachable; unauthenticated /me is a public 401; old api.chickenbro.cloud health retains its prior conclusion.

- [ ] Step 4: Perform real Web-to-mini login smoke

Use the public Web page on a computer/one device and a published WeChat mini program on another device:

1. Click generate QR and verify the response contains a non-placeholder PNG data URL.
2. Scan with the mini program; verify pages/auth/web-login-confirm opens.
3. Verify the page requires the user to click “确认登录”.
4. Click confirmation and observe Web pending -> confirmed -> authenticated.
5. Verify refresh remains authenticated through the HttpOnly Cookie and /api/v2/me returns only safe user view.
6. Verify logout, QR expiry, cancel, wrong verifier, repeated exchange and missing scene each recover with a public error.
7. Check v2 and Nginx logs for absence of Secret, access token, OpenID, UnionID, Cookie value and complete QR payload.

This step requires the user's physical scan/click. Until the user explicitly reports “我已测试通过” or “可以收尾”, evidence remains user_acceptance_pending and no final live completion claim is made.

- [ ] Step 5: Update final evidence and current docs

Promote only checks that actually pass. A missing WeChat credential, unpublished mini page, certificate or user scan is recorded as blocked/candidate_pending; page reachability and HTTP 200 remain reachability evidence only. Add the new route/service/schema to the verification matrix and owner maps without changing the 14-route visual target registry.

- [ ] Step 6: Commit evidence and docs, then pause for user acceptance

~~~
git add docs/verification-matrix.md docs/project-owner-map.json docs/backend-owner-map.json artifacts/releases/2026-09-01-chickenbro-web-mini-login
git commit -m "docs: record Web login candidate evidence"
~~~

After this commit, report the public URL and exact remaining acceptance state. Do not merge, delete the worktree, remove rollback material or call the result live_verified until the user has completed the real login smoke and explicitly authorizes closure.

## Verification Summary and Rollback

The minimum local proof is the focused Python/TypeScript test set plus both Taro production builds and the existing 14-route audit. The minimum candidate proof is static Web reachability, v2 loopback/API/readiness, additive migration registration, old API parity, real non-placeholder QR, real mini-program confirmation, Cookie /me refresh, logout/replay/expiry behavior and secret-free logs. Each claim is recorded separately; no aggregate green status is inferred from one binary or HTTP response.

Rollback order is: stop only wow-v2-api, restore the named v2 service/env/Nginx backups, reload Nginx/systemd, verify old api.chickenbro.cloud health and preserve the PostgreSQL backup/0039 audit record. If the migration itself caused an issue before any user flow, restore the reviewed pre-migration PostgreSQL backup according to docs/postgres-identity-migration-runbook.md; never enable SQLite fallback and never mutate legacy identity tables or wow-backend service as a shortcut.
