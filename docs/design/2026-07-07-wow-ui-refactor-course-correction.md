# WOW UI Refactor Course Correction

Status: `ui_refactor_course_correction_blocked`
Date: 2026-07-07

This records the current course correction for the in-progress mini-program UI refactor. It is not `target_locked`, not an active implementation permit, not page integration and not runtime verification.

## Source

User feedback in the current Codex thread:

- The home fixed bottom tab icons have not been implemented.
- Page margins and restoration are poor, and the work does not appear componentized or governed by a design spec.

## Findings

1. `app.json` has a native `tabBar.list`, but its items only define `pagePath` and `text`; they do not define `iconPath` or `selectedIconPath`. A better UI cannot rely on page-level fake fixed tabs.
2. The repository has source-level owners such as `AppShell`, `PageFrame`, `ChannelDock`, `RankedFeed`, `StatusVisual`, `ActionButton` and surface owners, but current page diffs still contain page-private gutters, legacy `page-shell/page-content` classes, direct generated material references and many primitive WXML nodes.
3. The implementation gate remains blocked: there is no target-locked decision record, no active implementation permit, and the current diff still contains quarantined page/app/navigation changes.

## Required Correction

- Fixed bottom navigation icons must be native WeChat `tabBar` icons: every tab requires `iconPath` and `selectedIconPath`, with real local assets under `assets/tabbar/`.
- Page integration must compose `AppShell`, `PageFrame` and the surface owner components. Pages may bind data and handle route events only.
- Horizontal gutters, section rhythm, panel geometry, status visuals, action buttons, evidence rows and chat layout must stay inside owner components.
- Until target lock and exactly one active implementation permit exist, page WXML/WXSS, `app.json`, navigation chrome and `project.config.json` changes remain quarantined and cannot count as runtime evidence.

## Preflight

```sh
node scripts/ui-system-refactor-course-correction-preflight.js --require-ready --json
```

Current expected exit code: `19`.

Current expected status: `ui_refactor_course_correction_blocked`.

## Evidence Links

- Script: `scripts/ui-system-refactor-course-correction-preflight.js`
- Test: `tests/ui-system-refactor-course-correction-preflight.test.js`
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-refactor-course-correction/manifest.json`
- Implementation gate: [WOW UI System Implementation Gate](2026-07-07-wow-ui-system-implementation-gate.md)
