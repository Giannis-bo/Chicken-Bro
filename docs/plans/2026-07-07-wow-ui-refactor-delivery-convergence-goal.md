# WOW UI Refactor Delivery Convergence Goal

Status: `delivery_convergence_implemented_runtime_blocked`

Date: 2026-07-07

This document narrows the current UI rebuild into a delivery-first convergence package. It does not replace the long-term WOW UI system rebuild direction. It changes the current acceptance line from "rebuild and verify every core surface" to "fix the drift, deliver one bounded vertical slice, and backlog the rest."

## Current Sync State

- `origin/main` was fetched on 2026-07-07.
- Local `main` is still `21` commits behind `origin/main`.
- Fast-forward merge is blocked by local dirty overlapping files. Do not use `reset`, destructive checkout, broad stash, DevTools project switching, or cache clearing to force the sync.
- Overlapping files include roadmap docs, talent simulator files, Chickenbro files, SimC files, `server/news_backend.py`, and related tests.

Current overlapping file list:

- `docs/roadmap.md`
- `docs/roadmap/ideas.md`
- `pages/builds/talent-simulator-core.js`
- `pages/builds/talent-simulator.wxml`
- `pages/simulator/chickenbro-chat.js`
- `pages/simulator/chickenbro.wxml`
- `pages/simulator/chickenbro.wxss`
- `pages/simulator/simulator.wxml`
- `pages/simulator/simulator.wxss`
- `server/news_backend.py`
- `tests/builds-page.test.js`
- `tests/simulator-page.test.js`
- `tests/talent-simulator-core.test.js`

## Active Delivery Scope

- Correct the drift called out by the user:
  - Native bottom tab icons are missing.
  - Page-private gutters and geometry are still too dominant.
  - Pages are not yet truly owned by `AppShell`, `PageFrame`, and surface owner components.
- Deliver exactly one minimum acceptable vertical slice.
- Recommended active surface: `news_list_detail`.
- Recommended target direction remains the existing target-lock recommendation: `A-Cockpit + B-Ledger + C-Captain`.
- Remaining pages become backlog, risk list, and next permit candidates.

## Required Gate Results

Commands run:

```sh
node scripts/ui-system-refactor-course-correction-preflight.js --require-ready --json
node scripts/ui-system-implementation-gate.js --require-implementation --json
```

Observed status:

- `ui_refactor_course_correction_ready`, exit code `0`.
- `ui_system_implementation_gate_passed`, exit code `0`.

Passing checks:

- `activation`
- `target_lock_decision`
- `first_surface_readiness`
- `course_correction`
- `active_permit`
- `diff_scope`

Resolved blockers in this pass:

- Target-locked decision record exists.
- Active `news_list_detail` permit exists.
- Native `app.json` tabBar items now have `iconPath` and `selectedIconPath`.
- `pages/news/list` and `pages/news/detail` pass owner adoption.

Remaining blockers:

- Runtime screenshots are not captured because `captureSafe=false`.
- Route smoke is planned but not executed because the current visible WeChat DevTools instance does not expose a usable miniprogram-automator runtime endpoint.
- All non-selected pages remain backlog/risk/next permit items.
- Local `main` still cannot be safely fast-forwarded over dirty overlapping files.

Low-disturbance DevTools health check:

- Evidence file: `artifacts/ui-system-rebuild/runtime-health/devtools-health-1783439727658.json`
- Visible DevTools window: yes.
- Multiple DevTools instance risk: no.
- Login-affecting probe used: no.
- Runtime/navigation/screenshot probe used: no.
- Forbidden lifecycle actions used: none.
- Health category: `candidate_ports_not_miniprogram_automator`.
- Safe next action: confirm or enable the active project's miniprogram-automator runtime endpoint and rerun capture with explicit `WECHAT_AUTOMATOR_PORT`; do not restart, clear cache, switch appid/project, login, or logout through automation.

## Must Fix For This Delivery

- Get explicit confirmation for:
  - target lock direction;
  - exactly one active surface;
  - permission to add native `app.json` tabBar icons and `assets/tabbar/` runtime resources.
- Add native tabBar icon assets under `assets/tabbar/` and wire every `app.json` tab item with `iconPath` and `selectedIconPath`.
- Convert only the confirmed surface into a real vertical slice:
  - `AppShell`
  - `PageFrame`
  - surface owner component(s)
  - page data binding and route handling only
- Produce verification for that one surface:
  - static gate;
  - component/browser precheck where applicable;
  - route smoke manifest;
  - screenshot plan or actual capture when DevTools is safe.
- Resolve or quarantine the dirty-worktree sync conflict before commit, handoff, or final acceptance.

Current delivery evidence:

- `node scripts/ui-system-target-lock-decision-preflight.js --require-decision --json`
- `node scripts/ui-system-active-permit-preflight.js --surface news_list_detail --require-active-permit --json`
- `node scripts/ui-system-page-adoption-preflight.js --surface news_list_detail --require-adoption --json`
- `node scripts/ui-system-refactor-course-correction-preflight.js --require-ready --json`
- `node scripts/ui-system-implementation-gate.js --require-implementation --json`
- `node scripts/ui-refactor-delivery-convergence-audit.js --require-ready --json`

## Can Wait

- Full rebuild of builds tab, workbench, talent simulator, gear detail, SimC, Chickenbro, tasks, and profile templates.
- All-surface visual scorecard.
- All-surface real WeChat screenshot matrix.
- Full DevTools route smoke across every page.
- Production source map and asset manifest for surfaces outside the selected vertical slice.
- Any further page-level patching outside the active permit.

## Recommended Permit

Use `news_list_detail` as the first single-surface delivery slice because existing evidence already has:

- `ArticleListBoard` and `ArticleReader` owner skeletons.
- First-surface activation readiness passing.
- Route smoke scene ids already defined.
- Less dependency on SimC, WebSim, login state, or complex generated chat output than workbench or Chickenbro.

## Non-Promotion Boundary

Until the user confirms the target and permit, this package is not:

- `target_locked`
- `active_implementation_permit`
- `page_integration_allowed`
- `runtime_verified`
- `final_accepted`

## Backlog Output Contract

Every non-selected page must be listed as one of:

- `next_permit_candidate`
- `risk_requires_design_lock`
- `blocked_by_runtime_verification`
- `backlog`

No non-selected page may be claimed as accepted by the selected surface's evidence.

## Evidence

- [Course Correction](../design/2026-07-07-wow-ui-refactor-course-correction.md)
- [Implementation Gate](../design/2026-07-07-wow-ui-system-implementation-gate.md)
- [News List Detail Active Permit Template](2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit-template.md)
- [News List Detail Active Permit](2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit.md)
- [Delivery Backlog](2026-07-07-wow-ui-refactor-delivery-backlog.md)
- [News List Detail Route Smoke Plan](2026-07-07-news-list-detail-route-smoke-plan.md)
- `artifacts/ui-system-rebuild/20260707-delivery-convergence/manifest.json`
- `artifacts/ui-system-rebuild/20260707-news-list-detail-runtime-verification-status/manifest.json`
- `artifacts/ui-system-rebuild/20260707-delivery-convergence-audit/manifest.json`
