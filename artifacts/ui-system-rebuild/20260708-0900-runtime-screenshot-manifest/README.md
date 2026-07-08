# 09:00 Runtime Screenshot Manifest

Status: `runtime_recapture_blocked_after_source_changes`

This manifest is the 09:00 delivery evidence control point. It intentionally does not promote browser demos, static tests, old pass scorecards, or component prechecks to UI correctness.

## Rules

- Every `app.json` page needs a real WeChat mini-program screenshot or an explicit `fail/risk` record.
- P0 pages need first-screen evidence and route smoke evidence.
- DevTools validation must be low-disruption: no close, restart, cache clear, appid switch, project switch, user-directory deletion, or repeated open/close/compile loops.
- User-reported real simulator failures override local assumptions until a new real screenshot disproves them.

## Current State

- Runtime verified: `false` for the current worktree.
- Final accepted: `false`.
- DevTools touched by the latest probe: existing listening ports only; no navigation, screenshot, close, restart, cache clear, appid switch, project switch, or user-directory deletion.
- `page-captures/` contains historical real WeChat screenshots for all 14 pages, but they are not current proof after later source changes.
- Latest read-only automator endpoint probe returned `automator_endpoint_probe_no_ready_endpoint`; do not run batch route smoke or screenshots until DevTools exposes a ready automator endpoint again.
- The current source-side fix after those historical screenshots removes the workbench verdict shield/atomic-image path. `StatusVisual` now uses state-enumerated basic shapes, so `builds_workbench.png` is useful as visual reference only, not as proof of the latest component state.

## Static Rescue Precheck

- `git diff --check`: passed.
- JS/JSON parse checks: passed for touched rescue files and the 09:00 manifest.
- 14 registered pages have `js/json/wxml/wxss` files.
- P0 pages have a navigation layer and a scroll/frame layer.
- `ChannelDock` has been downgraded to stable text orbs instead of generated PNG glyphs.
- `simulator` and `chickenbro` chat pages have prompt/evidence content and no enhanced chat scroll.

## DevTools State

- Latest endpoint probe: `artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/automator-endpoint-probe.json`.
- Action ledger: `artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/devtools-action-ledger.json`.
- Current usable endpoint: none detected by the latest read-only probe.
- Previous endpoint `ws://127.0.0.1:9854` is not currently accepting automator connections.
- Result: current screenshot recapture is blocked. The next validation step is a single-page endpoint/route probe after the user manually recompiles or restores DevTools.
- No login/open/close/cache/project-switch action was used in the latest rescue probe.

## Historical Screenshot Coverage

Historical P0 screenshots exist:

- `pages/news/news`
- `pages/builds/builds`
- `pages/builds/workbench`
- `pages/builds/talent-simulator`
- `pages/builds/detail`
- `pages/simulator/simulator`
- `pages/simulator/simc`
- `pages/profile/profile`

Historical P1/P2 screenshots exist:

- `pages/news/list`
- `pages/news/detail`
- `pages/simulator/chickenbro`
- `pages/simulator/tasks`
- `pages/simulator/task-detail`
- `pages/builds/intel`

## Current Validation Rule

- Use single-page capture for final evidence only after an endpoint probe finds a ready automator endpoint.
- Do not treat historical screenshots as current worktree proof.
- Treat `navigateTo callback not returned within short window` as a route warning when route matches, loading is false, and screenshot is valid.
- Treat `currentState timed out` plus a tiny screenshot as invalid evidence; immediately recapture that page by itself.
- Do not use multi-page serial capture as final proof.
- `capture-0900-pages.js` now refuses full 14-page serial capture by default. Use `WOW_0900_CAPTURE_PAGES=<page>` for normal validation. `WOW_0900_ALLOW_BATCH=1` is only for explicit user-approved risky batch capture.

## Rebuild The Evidence Summary

After refreshing any single-page screenshot, rebuild the non-DevTools summary with:

```sh
node artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/summarize-0900-screenshots.js
```

This script only reads `app.json` and existing files under `page-captures/`. It does not connect to WeChat DevTools, does not navigate, and does not affect login state.

Safe single-page capture command:

```sh
NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost WECHAT_AUTOMATOR_PORT=9854 WOW_0900_CAPTURE_PAGES=pages/news/news node artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/capture-0900-pages.js
```

Low-disruption P0 route smoke command:

```sh
NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost WECHAT_AUTOMATOR_PORT=9854 WOW_0900_RUN_P0_ROUTE_SMOKE=1 node artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/p0-route-smoke.js
```

The route smoke does not capture screenshots and does not run unless `WOW_0900_RUN_P0_ROUTE_SMOKE=1` is set.

Read-only automator endpoint probe:

```sh
node artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/automator-endpoint-probe.js
```

The endpoint probe only calls `Tool.getInfo` against existing WeChat DevTools listening ports. It does not navigate, capture screenshots, run `cli auto`, close, restart, clear cache, switch appid, or switch project.
