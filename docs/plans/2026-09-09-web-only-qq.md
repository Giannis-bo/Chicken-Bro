# Web-only QQ Login Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development; do not create nested agents. Follow the approved user decisions below.

**Goal:** Retire the Mini product and make QQ the only production Web sign-in provider.

**Architecture:** Keep the existing Taro H5, internal user_id, HttpOnly Web session and owner-scoped Chat/SimC. Replace Mini QR confirmation with a browser-bound, one-use QQ OAuth authorization-code flow. QQ creates separate accounts; retained WeChat data is never merged or deleted.

**Tech Stack:** Existing React/Taro H5, FastAPI, httpx and PostgreSQL. No new dependencies.

**Spec:** This document records the user's approved Web-only/QQ scope and explicit no-migration decision on 2026-09-09.

## Global Constraints

- Existing main has unrelated dirty WIP; work only in `.worktrees/qq-web` on `codex/qq-web-only`.
- Preserve Chat and SimC ownership, account concurrency guard, idempotency and cloud-only SimulationCraft.
- AppID is 1905584243. Secret is stored separately on the cloud, never in source, commands, reports or logs.
- Production callback is `https://www.chickenbro.cloud/api/v2/auth/qq/callback`.
- No new dependencies, downloads, destructive database migrations, source-history rewrites, push, production cutover or WeChat submission.
- The user authorized saving the QQ credentials on the cloud. Store a root-owned 0600 environment file; do not restart production just to save it.
- QQ accounts start with no old WeChat history. Preserve all old records. Existing WeChat-created sessions must not become QQ sessions implicitly.
- Mini is retired from active routes/build/UI; historical source and evidence may remain recoverable but must not ship as executable product pages or authentication entry points.
- Configuration presence and local fake-provider tests do not prove QQ review approval or a real QQ login.

## Task 1: Backend QQ identity and browser login

**Files:** `server/app/identity/qq_application.py`, `server/app/integrations/qq_connect.py`, `server/app/identity/{ports,repository}.py`, `server/app/api/routes/auth.py`, `server/app/main.py`, `server/app/platform/{config,health}.py`, new product migration and corresponding identity/API/provider/PG tests.

**Interfaces:**
- POST `/api/v2/auth/qq/login`, JSON `{}`; require configured Web Origin/Host. Return `{authorizationUrl, requestId}` and a Secure/HttpOnly/SameSite=Lax browser-binding cookie.
- GET `/api/v2/auth/qq/callback`, query `code`, `state` (or provider error). Validate browser binding, exact state and expiry before using QQ; atomically consume attempt once across workers. Exchange code server-side, verify returned client_id equals configured appid, map `(qq, appid, openid)` to internal user_id, issue existing Web session + CSRF cookies, redirect to configured Web origin. Failure redirects to fixed same-origin `/?loginError=CODE`; never expose provider raw errors or secrets. No arbitrary return URL.
- Configuration `WOW_QQ_APPID`, `WOW_QQ_APP_KEY` (repr hidden), `WOW_QQ_REDIRECT_URI`; exact HTTPS same-origin callback validation with environment-specific fixed paths: production `/api/v2/auth/qq/callback`, test `/test/api/v2/auth/qq/callback`, candidate `/api/v2-candidate/auth/qq/callback`. Fixed landing pages `/`, `/test/`, `/web-candidate/` respectively; browser-binding cookies use environment-isolated names. No WeChat config needed for readiness or composition.
- Retain `/api/v2/me`, `/api/v2/me/avatar`, `/api/v2/auth/logout` semantics used by Web. Retrieve QQ get_user_info for sanitized nickname and allowlisted HTTPS avatar URL; extend me with optional avatarUrl. Profile unavailable may fall back without blocking sign-in; do not require Mini upload.
- Old WeChat login/confirmation and Mini test-login HTTP routes are unavailable. Production auth resolves only Web sessions for QQ-linked users; test accounts remain restricted to explicit test environments.

- [x] Write tests first: success creates separate QQ owner, second QQ sees no first owner's state, state/cookie mismatch and expiry reject before provider access, replay/concurrent consumption fail, provider token/client_id/openid malformed or mismatched fail closed, cancelled consent returns recoverable fixed error, cookies/CSRF/Origin enforced, old WeChat/Bearer cannot authenticate.
- [x] Observe expected RED with `/tmp/chickenbro-merge-check-venv-20260907/bin/python -m unittest tests.app_qq_login_test -v`.
- [x] Implement provider calls with bounded timeouts, no token persistence/logging, no redirects to arbitrary hosts; implement Postgres attempt consume and QQ identity upsert with proper unique/concurrency constraints. Migration is additive and grant-limited; preserve old tables/data.
- [x] Run targeted tests plus relevant backend regression. Update superseded login expectations; retain actual Chat/SimC behavior tests.
- [x] Self-review, commit only task paths and report tests/limitations.

## Task 2: Web QQ sign-in and Mini build retirement

**Files:** `apps/mini-taro/src/web/{WebApp,WebLoginHome,web-auth-model}*`, `packages/{api-client,domain}/src/web-auth*`, `apps/mini-taro/src/{app.tsx,app.config.ts}`, H5 entry page, config, package scripts, active help/welcome/account copy and tests.

**Interfaces:** Consume Task 1 POST login response, then navigate to QQ authorizationUrl only after validating HTTPS official `graph.qq.com` host. Existing me/logout/CSRF remains; me may include optional allowlisted HTTPS QQ avatarUrl. Display that avatar when present. On return, load account and translate fixed loginError enum into recoverable text; clear only that query parameter without discarding app route. No auto login loop.

- [x] Test no QR creation/polling, explicit QQ login redirect, failed/cancelled authorization retry, me/401/logout, account isolation resets and retained test login in nonproduction.
- [x] Replace QR panel with QQ sign-in action, preserve existing site visual layout. Use the official 16x16 QQ asset URL verified in the official UI spec: `https://wiki.connect.qq.com/wp-content/uploads/2016/12/Connect_logo_1.png`, alongside QQ登录 text, without altering the image or downloading a file.
- [x] H5 entry must not mount/import any Mini product page. Disable WeApp build/dev/refresh commands with clear retired message; remove active Mini marketing, confirmation UI, dependency on Mini avatar selection and FAQ instructions. Keep Taro H5.
- [x] Run affected tests, full front-end suite, typecheck, lint, production H5 build and browser preview.
- [x] Self-review, commit only task paths and report.

## Task 3: Control documents, cloud secret and final integration

**Files:** `AGENTS.md`, `docs/{project-state.json,roadmap.md,plans/README.md,chickenbro-simc-architecture.md,verification-matrix.md,project-owner-map.json,backend-owner-map.json}`, release/setup docs and sanitized `artifacts/verification/2026-09-09-qq-web/`.

- [x] Save QQ env on verified cloud host, root-owned 0600, with metadata-only receipt and no service restart; preserve existing settings and rollbacks.
- [x] Update current product boundaries and checks to Web-only/QQ; preserve historical release evidence as historical. Match active owners and API contracts.
- [x] Run relevant control/ops checks, fresh backend/frontend/PG tests and diff check; fix integration failures and record limitations.
- [x] Independently review complete change for OAuth/CSRF/replay/account isolation and Mini runtime retirement. Address valid findings and reverify changed paths.
- [x] Report local code status, cloud secret status, QQ application review and deployment separately. Production release awaits concrete tested user acceptance.
