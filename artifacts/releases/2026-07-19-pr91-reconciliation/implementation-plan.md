# PR #91 Mainline Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconcile current `main` into PR #91 without rewriting history, preserve #92 contracts, retain only the still-useful WeChat/runtime improvements, and make PR #91 safely mergeable.

**Architecture:** Work directly on the existing `codex/cdn-api-publishing` PR branch inside the isolated worktree. Merge `origin/main` into the branch with current-main conflict authority, then audit the remaining PR diff by behavior and adapt each retained capability to current owners. Keep the current production API/asset root; alternative CDN tooling remains dormant and cannot influence production constants.

**Tech Stack:** Git, Node.js 20+, Taro 4.2, React 18, strict TypeScript, Vitest, Node test runner, Python unittest, Project Harness v0.6.1.

## Global Constraints

- Current truth is `docs/project-state.json`, then `docs/roadmap.md`, `docs/plans/ui-reconstruction.md`, `DESIGN.md`, and `docs/design/current-ui/README.md` from `origin/main`.
- `apps/mini-taro` owns the 14 active routes; `packages/api-client/src` owns typed transport; root `pages/` remains a compatibility consumer only.
- Production remains on `https://api.chickenbro.cloud` and `https://api.chickenbro.cloud/wow-assets/releases/2026-07-19-taro-full-integration`.
- Do not activate `static.chickenbro.cloud/wow-media`, claim its 404 release is published, disable URL checks, or trigger async sync/backfill.
- Do not rebase or force push the published PR branch.
- Current-main behavior wins every conflict unless a retained #91 behavior is reintroduced through the current owner with a focused test.
- Real WeChat evidence is manual, uses at most two routes per batch, and cannot be replaced by unit tests, API 200, or historical screenshots.
- The final runtime head receives one Harness `full`/CI pass and at most one candidate deployment window.

---

### Task 1: Reconcile branch ancestry without rewriting history

**Files:**
- Modify through merge: all files changed by `origin/main` since `2f8222f6df96e3cd0936ed07386a0e06def32079`
- Preserve: `artifacts/releases/2026-07-19-pr91-reconciliation/design.md`
- Preserve: `artifacts/releases/2026-07-19-pr91-reconciliation/implementation-plan.md`

**Interfaces:**
- Consumes: `origin/main` at or beyond `65be719204d4e398cede2dd1a947821cbd00c3d4`
- Produces: a two-parent merge commit on `codex/cdn-api-publishing`, with current-main content selected for overlapping hunks

- [x] **Step 1: Verify both worktrees are clean and refresh remote refs**

```powershell
git -C G:\Codex\wow status --short --branch
git status --short --branch
git fetch --prune origin
git rev-parse origin/main
```

Expected: both worktrees have no uncommitted files; `origin/main` is `65be719204d4e398cede2dd1a947821cbd00c3d4` or a verified fast-forward descendant.

- [x] **Step 2: Merge current main with main-side conflict preference**

```powershell
git merge --no-ff -X theirs --no-commit origin/main
git restore --source=origin/main --staged --worktree -- docs/project-state.json docs/roadmap.md docs/plans/ui-reconstruction.md DESIGN.md docs/design/current-ui/README.md
git diff --name-only --diff-filter=U
git commit -m "merge: reconcile PR91 with current main"
```

Expected: the unresolved-path command prints nothing and a normal merge commit is created without history rewrite. If unresolved paths remain, inspect each path and reconstruct it against the current owner; do not choose the #91 version merely to make the merge finish.

- [x] **Step 3: Verify current control-plane files match merged main**

```powershell
git diff --exit-code origin/main -- docs/project-state.json docs/roadmap.md docs/plans/ui-reconstruction.md DESIGN.md docs/design/current-ui/README.md
git diff --check
```

Expected: no control-plane diff and no whitespace errors.

### Task 2: Record the 13-commit disposition matrix

**Files:**
- Create: `artifacts/releases/2026-07-19-pr91-reconciliation/commit-disposition.json`
- Modify: `artifacts/releases/2026-07-19-pr91-reconciliation/implementation-plan.md`

**Interfaces:**
- Consumes: commits `5954508`, `e359234`, `896db33`, `e7ae334`, `2248be4`, `f8683ac`, `074b7c2`, `c31e602`, `b6fef07`, `d268601`, `7ca75e1`, `f7d3721`, `600f09b`
- Produces: schema version 1 JSON containing `commit`, `subject`, `disposition`, `retainedBehaviors`, `excludedBehaviors`, and `evidence`

- [x] **Step 1: Capture the post-merge net diff and commit history**

```powershell
git log --reverse --format="%H%x09%s" 2f8222f6df96e3cd0936ed07386a0e06def32079..600f09bc91dca8236627e6001bd1160dd75c4821
git diff --name-status origin/main...HEAD
git diff --stat origin/main...HEAD
```

Expected: the 13 original commits are present and the final diff is measured against current main.

- [x] **Step 2: Write the disposition matrix**

Use these exact dispositions as the starting contract and narrow retained behavior when current main already has a stronger equivalent:

```json
{
  "5954508": "retain_dormant_tooling_only",
  "e359234": "adapt_to_current_geometry_gate",
  "896db33": "adapt_to_current_release_gate",
  "e7ae334": "superseded_by_current_production_origin",
  "2248be4": "retain_atomic_build_promotion",
  "f8683ac": "retain_build_cleanup_boundary",
  "074b7c2": "superseded_by_current_domain_contract",
  "c31e602": "adapt_startup_and_audit_guards",
  "b6fef07": "retain_devtools_session_protection",
  "d268601": "adapt_remote_asset_build_without_root_switch",
  "7ca75e1": "retain_tab_identity_and_current_owner_header_fix",
  "f7d3721": "retain_initial_payload_contract_test",
  "600f09b": "adapt_to_current_appshell_pageframe_owners"
}
```

Every entry must identify the final test or diff proving the decision. It must explicitly exclude alternate-CDN activation and old control-plane wording.

- [x] **Step 3: Validate JSON and commit the audit artifact**

```powershell
node -e "JSON.parse(require('node:fs').readFileSync('artifacts/releases/2026-07-19-pr91-reconciliation/commit-disposition.json','utf8'))"
git diff --check
git add artifacts/releases/2026-07-19-pr91-reconciliation
git commit -m "docs: audit PR91 reconciliation scope"
```

Expected: JSON parses, diff check passes, and the audit commit contains only the release-packet files.

### Task 3: Restore authoritative TabBar identity with TDD

**Files:**
- Create or preserve: `apps/mini-taro/src/tab-bar-items.test.ts`
- Create or preserve: `apps/mini-taro/src/tab-bar-state.ts`
- Create or preserve: `apps/mini-taro/src/tab-bar-state.test.ts`
- Create or preserve: `apps/mini-taro/src/use-tab-root-identity.ts`
- Modify: `apps/mini-taro/src/tab-bar-items.ts`
- Modify: `apps/mini-taro/src/custom-tab-bar/index.tsx`
- Modify: `apps/mini-taro/src/pages/news/news.tsx`
- Modify: `apps/mini-taro/src/pages/builds/builds.tsx`
- Modify: `apps/mini-taro/src/pages/simulator/simulator.tsx`
- Modify: `apps/mini-taro/src/pages/profile/profile.tsx`

**Interfaces:**
- Produces: `resolveActiveTabRoute(candidates, fallback?)`, `createActiveTabRouteStore()`, `activeTabRouteStore`, and `useTabRootIdentity(pagePath)`
- Preserves: current #92 page actions, canonical empty/blocked behavior, typed route models, and all shared owner contracts

- [x] **Step 1: Run the focused tests before implementation**

```powershell
npx vitest run apps/mini-taro/src/tab-bar-items.test.ts apps/mini-taro/src/tab-bar-state.test.ts apps/mini-taro/src/pages/_shared/route-contract.test.ts
```

Expected before restoration: at least one test fails because current-main conflict resolution removed the #91 store/hook or root-page wiring.

- [x] **Step 2: Implement only the TabBar identity contract**

`resolveActiveTabRoute` must normalize candidates, prefer the actual page stack route, accept only registered Tab roots, and use the news root as the final fallback. `activeTabRouteStore.set` must ignore non-Tab routes and notify subscribers only after a real state change. Each of the four root pages must call `useTabRootIdentity` without changing its existing route state, actions, or JSX.

- [x] **Step 3: Make `switchTab` failure recover from real route state**

`custom-tab-bar/index.tsx` must subscribe once with `useEffect`, optimistically publish the selected Tab, call `Taro.switchTab`, and on rejection resolve the actual page stack/router route before restoring the previous state.

- [x] **Step 4: Run focused and route-contract tests**

```powershell
npx vitest run apps/mini-taro/src/tab-bar-items.test.ts apps/mini-taro/src/tab-bar-state.test.ts apps/mini-taro/src/pages/_shared/route-contract.test.ts
```

Expected: all selected files pass with zero failures.

- [x] **Step 5: Commit the TabBar behavior**

```powershell
git add apps/mini-taro/src/tab-bar-items.ts apps/mini-taro/src/tab-bar-items.test.ts apps/mini-taro/src/tab-bar-state.ts apps/mini-taro/src/tab-bar-state.test.ts apps/mini-taro/src/use-tab-root-identity.ts apps/mini-taro/src/custom-tab-bar/index.tsx apps/mini-taro/src/pages/news/news.tsx apps/mini-taro/src/pages/builds/builds.tsx apps/mini-taro/src/pages/simulator/simulator.tsx apps/mini-taro/src/pages/profile/profile.tsx
git commit -m "fix(taro): keep TabBar identity synchronized"
```

Expected: the commit does not remove or rewrite unrelated page behavior.

### Task 4: Integrate safe WeChat build promotion and session protection

**Files:**
- Create or preserve: `scripts/build-weapp-safely.js`
- Create or preserve: `scripts/finalize-weapp-build.js`
- Create or preserve: `tests/build-weapp-safely.test.js`
- Create or preserve: `tests/finalize-weapp-build.test.js`
- Create or preserve: `tests/wechat-automator.test.js`
- Modify: `apps/mini-taro/config/index.ts`
- Modify: `apps/mini-taro/package.json`
- Modify: `package.json`
- Modify: `scripts/wechat-automator.js`
- Modify: `scripts/capture-ui-review-cache.js`

**Interfaces:**
- Produces: `validateBuild(root)`, `promoteWeappBuild(stagingRoot, destinationRoot, options)`, `resolveIsolatedOutputRoot(root)`, and `finalizeWeappBuild(root)`
- Preserves: current production cache disablement, one existing DevTools process, explicit route batches of at most two, and no automatic launch/reload

- [x] **Step 1: Run build-promotion and automator regression tests**

```powershell
node --test tests/build-weapp-safely.test.js tests/finalize-weapp-build.test.js tests/wechat-automator.test.js tests/taro-production-build.test.js
```

Expected: retained #91 tests reveal any mainline-conflict regression; existing production-cache tests remain green.

- [x] **Step 2: Adapt the safe build wrapper to current config**

The wrapper must build to an OS temp directory with `WOW_TARO_ISOLATED_BUILD=1` and `WOW_TARO_OUTPUT_ROOT=<temp>`, reject symlinks and invalid/missing page entries, copy dependencies before `app.json`, write `app.js` last as the commit marker, and leave the active output untouched on failure. `apps/mini-taro/config/index.ts` must retain `cache.enable = !productionBuild && !isolatedBuild`.

- [x] **Step 3: Preserve the current DevTools session boundary**

The automator/capture path may attach to an existing endpoint but must not close, reload, or replace the user's logged-in DevTools process. It must retain the current explicit route-batch limit and fail closed when no usable renderer exists.

- [x] **Step 4: Run focused build and automator tests**

```powershell
node --test tests/build-weapp-safely.test.js tests/finalize-weapp-build.test.js tests/wechat-automator.test.js tests/taro-production-build.test.js tests/capture-ui-review-cache.test.js
```

Expected: all selected tests pass, including incomplete-tree, symlink, unchanged-package, app-entry-last, production-cache, and session-ownership cases.

- [x] **Step 5: Commit build/session safety**

```powershell
git add package.json apps/mini-taro/package.json apps/mini-taro/config/index.ts scripts/build-weapp-safely.js scripts/finalize-weapp-build.js scripts/wechat-automator.js scripts/capture-ui-review-cache.js tests/build-weapp-safely.test.js tests/finalize-weapp-build.test.js tests/wechat-automator.test.js
git commit -m "fix(weapp): promote complete builds safely"
```

Expected: no generated `dist/weapp` files are staged.

### Task 5: Preserve the mini-program initial gear payload contract

**Files:**
- Modify: `server/news_backend.py`
- Modify only if required by the current owner: `server/websim_payload.py`
- Modify only if required by typed transport: `packages/api-client/src/transport.ts`
- Modify: `tests/websim_payload_test.py`
- Modify: `tests/frontend-api-client.test.js`

**Interfaces:**
- Consumes: `X-Wow-Platform: miniprogram`, query `mode`, query `slot`
- Produces: mini-program `/api/websim/gear` defaults to `mode=initial` only when the caller did not provide a mode; explicit modes and non-mini-program callers remain unchanged

- [x] **Step 1: Run the exact initial-mode regression test**

```powershell
python -m unittest tests.websim_payload_test.WebSimPayloadTest.test_http_websim_gear_miniprogram_header_uses_compact_payload
```

Expected before restoration: FAIL because `gearPayloadMode`/candidate limit do not reflect `initial`, or PASS if current main already has an equivalent contract.

- [x] **Step 2: Apply the minimal backend default when the test is red**

Inside the `/api/websim/gear` handler, after reading the caller-supplied mode:

```python
if platform == "miniprogram" and not str(mode or "").strip():
    mode = "initial"
```

Do not alter explicit `mode`, `slot`, compact semantics, resolver ownership, public source keys, or fallback truth.

- [x] **Step 3: Run focused API and transport tests**

```powershell
python -m unittest tests.websim_payload_test.WebSimPayloadTest.test_http_websim_gear_miniprogram_header_uses_compact_payload tests.websim_payload_test.WebSimPayloadTest.test_websim_gear_initial_mode_slims_candidate_details
node --test tests/frontend-api-client.test.js
```

Expected: all selected tests pass; the initial response retains four candidates per slot and omits heavy per-item collections while explicit slot detail remains available.

- [x] **Step 4: Commit the payload contract only if it changes current main**

```powershell
git add server/news_backend.py server/websim_payload.py packages/api-client/src/transport.ts tests/websim_payload_test.py tests/frontend-api-client.test.js
git commit -m "perf(api): slim mini-program initial gear payload"
```

Expected: skipped if the post-merge main already satisfies the exact tests with no diff.

### Task 6: Retain useful PNG/runtime-media support without switching CDN roots

**Files:**
- Create or preserve: `packages/design-system/assets/vector-runtime/**`
- Create or preserve: `packages/design-system/src/components/useTrustedMediaLoadState.ts`
- Create or preserve: `packages/design-system/src/components/useTrustedMediaLoadState.test.ts`
- Create or preserve: `packages/design-system/src/runtime-media-path.cjs`
- Create or preserve: `packages/design-system/src/runtime-media-path.d.cts`
- Modify: `packages/assets-manifest/src/index.ts`
- Modify: `packages/assets-manifest/src/current-manifest.test.ts`
- Modify: `packages/design-system/src/runtime-media.ts`
- Modify: `packages/design-system/src/runtime-media.test.ts`
- Modify only through shared owners: `packages/design-system/src/components/MaterialImage.tsx`, `GameObjectIcon.tsx`, `SystemGlyph.tsx`, `ProductionAssetGlyph.tsx`
- Create or preserve: `scripts/generate-weapp-vector-runtime.js`
- Create or preserve: `scripts/publish-runtime-media.js`
- Create or preserve: `tests/publish-runtime-media.test.js`
- Modify: `docs/cdn-asset-publishing.md`

**Interfaces:**
- Produces: deterministic local PNG runtime fallbacks, trusted-media state shared by media components, and an explicit dormant publisher
- Preserves: `__WOW_ASSET_RUNTIME_ROOT__` current production value and current `api.chickenbro.cloud` immutable release

- [x] **Step 1: Run manifest/media regression tests**

```powershell
npx vitest run packages/assets-manifest/src/current-manifest.test.ts packages/design-system/src/runtime-media.test.ts packages/design-system/src/components/useTrustedMediaLoadState.test.ts
node --test tests/publish-runtime-media.test.js
```

Expected: any missing current-main adaptation is exposed before source changes.

- [x] **Step 2: Keep only registered PNG fallbacks and trusted URL behavior**

Every retained PNG must have a unique manifest asset ID/slot, deterministic relative path, and test coverage. Shared media components must use one trusted-load-state owner; they may show a registered local fallback on missing/untrusted remote media but may not upgrade fallback content to verified.

- [x] **Step 3: Keep publisher tooling dormant**

The publisher must require an explicit release ID and output target, validate host allowlists, byte size, and SHA-256, and have no package script that runs during build, test, deploy, or release verification. Documentation must state that the historical `static.chickenbro.cloud/wow-media/releases/2026-07-19-wow-icons-v1` path is unpublished and must not be configured.

- [x] **Step 4: Run integrity, package, and focused media tests**

```powershell
npx vitest run packages/assets-manifest/src/current-manifest.test.ts packages/design-system/src/runtime-media.test.ts packages/design-system/src/components/useTrustedMediaLoadState.test.ts
node --test tests/publish-runtime-media.test.js
npm run verify:ui-asset-integrity
npm run verify:ui-package
```

Expected: zero hash/path mismatch; package mechanics pass; current root is unchanged; no alternative CDN root appears in production constants.

- [x] **Step 5: Commit media support**

```powershell
git add packages/assets-manifest packages/design-system scripts/generate-weapp-vector-runtime.js scripts/publish-runtime-media.js tests/publish-runtime-media.test.js docs/cdn-asset-publishing.md
git commit -m "feat(weapp): add deterministic runtime icon fallbacks"
```

Expected: only registered runtime assets, shared media code, dormant tooling, tests, and its runbook are included.

### Task 7: Reconcile shared chrome and verification contracts

**Files:**
- Modify only if net-new behavior remains: `packages/design-system/src/components/PageFrame.tsx`
- Modify only if net-new behavior remains: `packages/design-system/src/components/owners.module.scss`
- Modify only if net-new behavior remains: `packages/design-system/src/components/TabBar.module.scss`
- Modify: `scripts/audit-ui-architecture.js`
- Modify: `scripts/verify-ui-route-geometry.js`
- Modify: `scripts/verify-ui-package.js`
- Modify: `docs/plans/ui-reconstruction.md`
- Modify: `docs/project-state.json`
- Modify: `artifacts/releases/2026-07-19-pr91-reconciliation/commit-disposition.json`

**Interfaces:**
- Consumes: current `AppShell`, `PageFrame`, `ProductTabBar`, route geometry, selected-state, package, and evidence contracts
- Produces: one shared-owner implementation and a current-truth record that does not promote unverified routes

- [x] **Step 1: Compare #91 shared-chrome changes against current owners**

```powershell
git diff origin/main...HEAD -- packages/design-system/src/components/PageFrame.tsx packages/design-system/src/components/owners.module.scss packages/design-system/src/components/TabBar.module.scss
npm run audit:ui-architecture
```

Expected: route-private ownership regressions are identified; any already-equivalent #91 rule is classified as superseded instead of duplicated.

- [x] **Step 2: Keep only current-owner fixes**

Header/capsule spacing remains owned by `PageFrame`; top/bottom safe area remains owned by `AppShell`; Tab geometry and active material remain owned by `ProductTabBar`. Remove stale duplicate selectors, fixed-width route patches, old control-plane wording, and any rule that weakens the current geometry/selection contracts.

- [x] **Step 3: Update current state without overclaiming**

Record the PR #91 reconciliation status and evidence path. Preserve `active_unverified` and the existing 5 accepted / 9 `not_run_user_waived` manual boundary until new manual evidence exists. Do not claim 14/14 visual acceptance.

- [x] **Step 4: Run architecture, geometry-source, and project-state tests**

```powershell
npm run audit:ui-architecture
node --test tests/project-state.test.js tests/wechat-viewport.test.js tests/release-domain-policy.test.js
git diff --check
```

Expected: 14-route architecture audit reports zero findings; project-state and release-domain tests pass.

- [x] **Step 5: Commit current contracts**

```powershell
git add packages/design-system/src/components scripts/audit-ui-architecture.js scripts/verify-ui-route-geometry.js scripts/verify-ui-package.js docs/plans/ui-reconstruction.md docs/project-state.json artifacts/releases/2026-07-19-pr91-reconciliation/commit-disposition.json
git commit -m "docs: align PR91 with current UI contracts"
```

Expected: the commit contains only shared-owner adaptations, gates, and truthful control-plane updates.

### Task 8: Final local verification and whole-branch CR

**Files:**
- Create: `artifacts/releases/2026-07-19-pr91-reconciliation/evidence.json`
- Modify: `artifacts/releases/2026-07-19-pr91-reconciliation/commit-disposition.json`

**Interfaces:**
- Consumes: final branch diff against `origin/main`
- Produces: final verification results, risks, rollback, candidate identity, and CR findings

- [x] **Step 1: Run targeted frontend/backend checks**

```powershell
npm run typecheck
npm run lint
npm run test:taro
npm run audit:ui-architecture
node --test tests/build-weapp-safely.test.js tests/finalize-weapp-build.test.js tests/wechat-automator.test.js tests/frontend-api-client.test.js tests/project-state.test.js tests/publish-runtime-media.test.js tests/release-domain-policy.test.js
python -m unittest tests.websim_payload_test
```

Expected: every command exits 0. Python runs sequentially on Windows.

- [x] **Step 2: Run current release package gates**

```powershell
$env:WOW_BACKEND_API_BASE_URL='https://api.chickenbro.cloud'
$env:WOW_ASSET_RUNTIME_ROOT='https://api.chickenbro.cloud/wow-assets/releases/2026-07-19-taro-full-integration'
$env:WOW_WECHAT_REQUEST_DOMAIN_APPROVED='yes'
npm run audit:taro-domain
npm run build:weapp
npm run verify:ui-package:release
```

Expected: domain audit reports `productionReady=true`; release package reports `releaseReady=true`; the build contains the current root and not the unpublished alternative root.

- [x] **Step 3: Run one final Harness full profile**

```powershell
node scripts/verify-project.js --profile full
```

Expected: the final head full profile exits 0; do not repeat frontend/backend/full profiles serially.

- [x] **Step 4: Perform whole-branch local CR**

```powershell
git diff --check origin/main...HEAD
git diff --stat origin/main...HEAD
git log --oneline --decorate origin/main..HEAD
```

Review the full diff against the design, disposition matrix, current owner map, fail-closed semantics, package/root constants, performance, and rollback. Fix every valid Critical or Important finding and rerun its affected checks.

- [x] **Step 5: Write and validate the evidence packet**

`evidence.json` must include `status`, `highestEvidenceLevel`, `scope`, `verification`, `risks`, `rollback`, `candidate`, `manualAcceptance`, and `wholeBranchReview`. Before manual WeChat acceptance, set `highestEvidenceLevel` no higher than `local_verified` or `deployable` according to actual candidate evidence.

```powershell
node scripts/project-harness.js --json --slug pr91-reconciliation --evidence-file artifacts/releases/2026-07-19-pr91-reconciliation/evidence.json
git diff --check
```

Expected: Harness parses the evidence packet and preserves the manual acceptance gap.

### Task 9: Candidate, manual acceptance, merge, and cleanup

**Files:**
- Modify after evidence exists: `artifacts/releases/2026-07-19-pr91-reconciliation/evidence.json`
- Modify after closure: `docs/project-state.json`
- Modify after closure: `docs/plans/ui-reconstruction.md`

**Interfaces:**
- Consumes: final PR head, passing local checks/CI, explicit user acceptance on the new candidate
- Produces: merged PR #91, synchronized `main`, truthful evidence, and cleanup of this task's worktree/branch

- [x] **Step 1: Push the reconciled PR branch and verify GitHub CI**

```powershell
git push origin codex/cdn-api-publishing
gh pr checks 91 --repo boyuan19910222-ui/wow_mini_program --watch
```

Expected: the remote branch advances without force and the latest Project Harness check passes.

- [x] **Step 2: Run one final candidate window when runtime files remain**

Deploy only the final PR head through the existing candidate path, keep `WOW_DEPLOY_START_ASYNC_SYNCS=0`, record branch/commit, runtime file parity, `/health`, `/api/data/health`, affected API smoke, service/timer/log state, backup, and rollback. If the final diff is frontend-only, use the production weapp candidate and skip backend hot deploy.

- [x] **Step 3: Request two-route manual WeChat acceptance**

Ask the user to verify no more than these two routes in one batch:

1. `pages/news/news`: switch across all four Tab items and confirm the active item follows the visible root without a dead tap.
2. `pages/builds/detail`: scroll, use the back entry, and confirm title/back control do not overlap the system capsule or scroll away incorrectly.

Expected: explicit post-test acceptance such as `我已测试通过，可以合入`.

- [x] **Step 4: Complete Harness closure after explicit acceptance**

Run final local CR, commit closure evidence, merge PR #91 without history rewrite, update local `main` by fast-forward, rerun scoped merge-result verification, and push `main`.

```powershell
gh pr merge 91 --repo boyuan19910222-ui/wow_mini_program --merge --delete-branch=false
git -C G:\Codex\wow fetch origin
git -C G:\Codex\wow pull --ff-only origin main
git -C G:\Codex\wow rev-parse HEAD
git -C G:\Codex\wow rev-parse origin/main
git ls-remote origin refs/heads/main
```

Expected: the three main SHAs match the PR merge commit and scoped verification passes on the merge result.

- [x] **Step 5: Remove only this task's worktree and branches**

After confirming the worktree is clean and PR #91 is merged, remove `G:\Codex\wow\.worktrees\cdn-api-publishing`, delete local `codex/cdn-api-publishing`, and delete the merged remote branch. Do not touch other branches or worktrees.
