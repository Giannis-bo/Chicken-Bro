# Chickenbro Web 登录候选环境隔离实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不切换现有公网 `/api/v2/`、不触碰 `codex/ui-style-research` 和不复用公网 v2 数据的前提下，让体验版小程序能够真实验证 Web 微信扫码、明确确认、Cookie 会话和 `/me` 闭环。

**Architecture:** 候选 API 使用独立 systemd 进程和 `127.0.0.1:8791`，候选数据库从空的 `wow_dev` 克隆为独立 `wow_v2_candidate` 数据库并只应用 0038--0040；`www.chickenbro.cloud` 只增加浏览器所需的 `/api/v2-candidate/` 反向代理和 `/web-candidate/` 静态路径，已获微信 request 域名批准的 `api.chickenbro.cloud` 同样只增加 `/api/v2-candidate/` 反向代理，生产 `/api/v2/` 与旧 API 保持原样。Web 与小程序通过编译期候选 API 前缀进入候选 API，Cookie 使用独立名称。体验版二维码使用候选专用 `WOW_WECHAT_CHECK_PATH=0`，正式默认仍为 `1`。

**Scope:** 候选登录链路、微信图片响应兼容、候选服务/数据库/Nginx 脚本、H5/小程序候选构建和证据记录。暂不正式发布小程序，不合入 `main`，不切正式服务，不启动候选 Worker，不迁移既有账户数据。

## Verified constraints

- 当前公网 v2 服务使用 `wow_test`、8790 和 `/api/v2/`；没有候选服务、候选域名或候选证书。
- `wow_dev` 仅有基础 identity/ops 结构且无现有用户，适合作为候选数据库模板；候选库需单独命名，避免其他开发进程共用。
- 微信服务端对目标页面在 `check_path=true` 下返回 41030；同一 AppID 在 `check_path=false` 下返回真实 JPEG，因此候选需显式记录该边界并接受 PNG/JPEG。
- 现有 `www.chickenbro.cloud` 与 `api.chickenbro.cloud` 证书和 Nginx 入口均已存在，候选只使用同域路径，不新建 DNS/证书；小程序 API 指向已批准的 `api.chickenbro.cloud`，浏览器 Web 仍从 `www.chickenbro.cloud` 同源访问。

## Tasks

### 1. Add failing contracts first

- Add tests for `WOW_WECHAT_CHECK_PATH`, PNG/JPEG QR validation and MIME-preserving data URLs.
- Add tests for the candidate Web auth prefix and H5 public path configuration.
- Add static deployment tests requiring 8791, candidate service/env/database/static paths, additive Nginx locations, no `wow-v2-api` stop/restart, no legacy service changes, and backup-first behavior.
- Run only the focused suites and confirm they fail for the missing behavior.

### 2. Implement shared contracts and backend behavior

- Add `__WOW_WEB_AUTH_API_PREFIX__` and `WOW_H5_PUBLIC_PATH` build constants with strict path validation.
- Make Web auth client paths use the configured prefix while preserving the default `/api/v2` behavior.
- Extend WeChat settings with a boolean `WOW_WECHAT_CHECK_PATH` defaulting to true.
- Accept only real PNG/JPEG magic bytes and matching/empty image MIME types; preserve the actual MIME in the QR data URL; reject placeholders and non-image payloads.
- Keep secrets, provider tokens, OpenID/UnionID and raw QR bytes out of logs/evidence.

### 3. Implement candidate runtime assets

- Add a candidate-only systemd unit using `/opt/wow-mini-program-candidate`, existing compatible v2 virtualenv, `WOW_APP_ENV=candidate`, port 8791, candidate cookie name, candidate DB env file and `WOW_WECHAT_ENV_VERSION=trial`/`WOW_WECHAT_CHECK_PATH=0`.
- Add a candidate deployment script that packages the candidate source, creates a backup before mutation, clones `wow_dev` into a new candidate database, applies 0038--0040 transactionally as `wow_migrator`, writes a mode-0600 candidate env file without printing values, installs a separate source tree and static release, and adds/removes only marked candidate Nginx locations.
- Verify rollback restores the candidate unit/env/Nginx/static pointer and never stops or rewrites the existing v2 or legacy service.

### 4. Run local verification and build candidate artifacts

- Run focused Python/TypeScript/Node tests, typecheck, lint, H5 build, WeChat build and the route/architecture audits.
- Build H5 with `/web-candidate/`, candidate prefix and verified immutable remote assets.
- Build the WeChat package with the approved `https://api.chickenbro.cloud` plus candidate prefix, keep the package below the 2 MB upload limit, and record branch/commit/source hash.

### 5. Deploy candidate and perform user-controlled acceptance

- Deploy only the candidate script to the known server after local verification; check candidate loopback health, both public candidate API paths, Web static path, old `/api/v2` parity, old API parity, Nginx syntax and secret-free logs.
- Upload the new experience-version package through the existing logged-in WeChat DevTools CLI; do not alter the protected `codex/ui-style-research` DevTools project.
- User scans the candidate QR, opens `pages/auth/web-login-confirm`, clicks explicit confirmation, verifies Web pending → confirmed → authenticated, refreshes `/me`, logs out, and checks replay/expiry/cancel/wrong-verifier recovery.
- Keep evidence `candidate_pending`/`user_acceptance_pending` until the user explicitly reports the real flow passed.

## Rollback

Stop only the candidate service, restore the candidate service/env/both Nginx marked blocks/static symlink and preserve the candidate database backup. Never change `/api/v2/` production routing, `wow-v2-api`, `wow-backend`, legacy API, `wow_test`, Active Manifest or the protected UI worktree.

## Verification commands

```sh
python3 -m unittest tests.app_config_test tests.app_wechat_mini_test tests.app_identity_repository_test tests.app_auth_application_test tests.app_api_test tests.app_schema_test
npm exec vitest run packages/domain/src packages/api-client/src apps/mini-taro/src/web apps/mini-taro/src/pages/auth
npm run typecheck
npm run lint
npm --workspace @wow-mini/mini-taro run build:h5
npm run build:weapp
node --test tests/deploy-web-v2-candidate.test.js
bash -n server/deploy_web_v2_candidate_lighthouse.sh
git diff --check
```
