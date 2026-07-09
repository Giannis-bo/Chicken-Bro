# 09:00 Runtime Screenshot Manifest

Status: `runtime_recapture_complete_auto_14_screenshots_14_pass_final_accepted`

This manifest is the 09:00 delivery evidence control point. It intentionally does not promote browser demos, static tests, old pass scorecards, or component prechecks to UI correctness.

## Rules

- Every `app.json` page needs a real WeChat mini-program screenshot or an explicit `fail/risk` record.
- P0 pages need first-screen evidence and route smoke evidence.
- DevTools validation must be low-disruption: no close, restart, cache clear, appid switch, project switch, user-directory deletion, or repeated open/close/compile loops.
- User-reported real simulator failures override local assumptions until a new real screenshot disproves them.

## Current State

- Runtime verified: `true` for the current worktree.
- Final accepted: `true` by user confirmation on 2026-07-09.
- DevTools touched by the latest proof: current-project `cli auto --auto-port 9854`, `pages/news/news`, `pages/builds/builds`, `pages/simulator/simulator`, and `pages/profile/profile` `switchTab`, `pages/builds/workbench`, `pages/builds/talent-simulator`, `pages/builds/detail`, `pages/simulator/simc`, `pages/news/list`, `pages/news/detail`, `pages/builds/intel`, `pages/simulator/chickenbro`, `pages/simulator/tasks`, and `pages/simulator/task-detail` `navigateTo`, current-page probes, and 14 successful current `App.captureScreenshot` calls; no close, restart, cache clear, appid switch, project switch, user-directory deletion, or 14-page batch.
- `page-captures/` contains historical real WeChat screenshots for all 14 pages, but they are not current proof after later source changes.
- Latest read-only automator endpoint probe returned `automator_endpoint_probe_found_ready_endpoint` with `recommendedAutomatorPort=9854`.
- Current automated proof exists for `pages/news/news`: `page-captures/news_news_auto_20260709T031806Z.png` plus `page-captures/news_news_auto_latest.json`.
- Current automated proof exists for `pages/news/list`: `page-captures/news_list_auto_20260709T053302Z.png` plus `page-captures/news_list_auto_latest.json`.
- Current automated proof exists for `pages/news/detail`: `page-captures/news_detail_auto_20260709T053334Z.png` plus `page-captures/news_detail_auto_latest.json`.
- Current automated proof exists for `pages/builds/builds`: `page-captures/builds_builds_auto_20260709T051856Z.png` plus `page-captures/builds_builds_auto_latest.json`.
- Current automated proof exists for `pages/builds/workbench`: `page-captures/builds_workbench_auto_20260709T051629Z.png` plus `page-captures/builds_workbench_auto_latest.json`.
- Current automated proof exists for `pages/builds/intel`: `page-captures/builds_intel_auto_20260709T053348Z.png` plus `page-captures/builds_intel_auto_latest.json`.
- Current automated proof exists for `pages/builds/talent-simulator`: `page-captures/builds_talent-simulator_auto_20260709T052151Z.png` plus `page-captures/builds_talent-simulator_auto_latest.json`.
- Current automated proof exists for `pages/builds/detail`: `page-captures/builds_detail_auto_20260709T060642Z.png` plus `page-captures/builds_detail_auto_latest.json`.
- Current automated proof exists for `pages/simulator/simulator`: `page-captures/simulator_simulator_auto_20260709T052530Z.png` plus `page-captures/simulator_simulator_auto_latest.json`.
- Current automated proof exists for `pages/simulator/simc`: `page-captures/simulator_simc_auto_20260709T052916Z.png` plus `page-captures/simulator_simc_auto_latest.json`.
- Current automated proof exists for `pages/simulator/chickenbro`: `page-captures/simulator_chickenbro_auto_20260709T053404Z.png` plus `page-captures/simulator_chickenbro_auto_latest.json`.
- Current automated proof exists for `pages/simulator/tasks`: `page-captures/simulator_tasks_auto_20260709T053422Z.png` plus `page-captures/simulator_tasks_auto_latest.json`.
- Current automated proof exists for `pages/simulator/task-detail`: `page-captures/simulator_task-detail_auto_20260709T060703Z.png` plus `page-captures/simulator_task-detail_auto_latest.json`.
- Current automated proof exists for `pages/profile/profile`: `page-captures/profile_profile_auto_20260709T053114Z.png` plus `page-captures/profile_profile_auto_latest.json`.
- All 14 `app.json` routes have current route evidence. All 14 pages have current screenshots and all 14 visually pass. Runtime proof is complete and accepted as the current baseline; future UI adjustments are separate requests.
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
- Current usable endpoint: `ws://127.0.0.1:9854`, restored by hidden DevTools CLI option `--auto-port 9854`.
- Result: all 14 registered pages have current route evidence and current screenshots. All 14 screenshots visually pass. `pages/builds/detail` was recaptured after replacing the sticky action-bar with non-overlapping document-flow controls, and `pages/simulator/task-detail` was recaptured as the expected direct-open empty state.
- No close/cache/project-switch/appid-switch action was used in the latest proof.

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

Current safe single-page route + screenshot command:

```sh
WECHAT_AUTOMATOR_PORT=9854 WOW_0900_PROOF_PAGE=pages/simulator/task-detail node artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/auto-route-screenshot.js
```

If the endpoint disappears after DevTools restarts, restore it first:

```sh
/Applications/wechatwebdevtools.app/Contents/MacOS/cli auto --project /Users/boyuan/Documents/wow_mini_program --port 30412 --auto-port 9854 --trust-project --lang zh
```

The older `capture-0900-pages.js` and `p0-route-smoke.js` still reference the missing historical `ui-v2-1-strict-restoration/connect-miniprogram-automator` helper. Prefer `auto-route-screenshot.js` for the current low-disruption proof path.

Read-only automator endpoint probe:

```sh
node artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/automator-endpoint-probe.js
```

The endpoint probe only calls `Tool.getInfo` against existing WeChat DevTools listening ports. It does not navigate, capture screenshots, run `cli auto`, close, restart, clear cache, switch appid, or switch project.
