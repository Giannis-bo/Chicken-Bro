# WOW UI System Core Page Freeze Preflight

Status: `core_page_freeze_blocked`

Date: 2026-07-07

This document records the dedicated freeze gate for core page, App shell, existing navigation chrome, and DevTools project config changes. It exists because the UI rebuild goal explicitly stops page-level patching and pass36/pass37-style pixel repairs until a target-locked decision and exactly one active implementation permit exist.

This is source evidence only. It does not create a target lock, does not activate a permit, does not approve page integration, and does not claim runtime verification.

## Command

```bash
node scripts/ui-system-core-page-freeze-preflight.js --require-frozen --summary-json
```

Expected current exit code: `16`.

## Current Result

- Status: `core_page_freeze_blocked`
- freezeSatisfied: `false`
- blockedByMissingGate: `true`
- targetDecisionExists: `false`
- activePermitExists: `false`
- changedFileCount: `2858`
- frozenCoreFileCount: `44`
- app_shell: `2`
- navigation_chrome: `3`
- core_surface_page: `38`
- devtools_project_config: `1`

## Frozen Scope

The frozen scope includes:

- `app.js / app.json / app.wxss`
- `project.config.json`
- `components/navigation-bar/*`
- `pages/news/*`
- `pages/builds/*`
- `pages/simulator/*`
- `pages/profile/*`
- `pages/pve/*`

These files are not deleted or reverted by this preflight. They are treated as quarantined implementation work until a valid target lock and active implementation permit exist.

## Current Frozen Files

- `app.json`
- `app.wxss`
- `components/navigation-bar/navigation-bar.js`
- `components/navigation-bar/navigation-bar.wxml`
- `components/navigation-bar/navigation-bar.wxss`
- `pages/builds/builds-api.js`
- `pages/builds/builds.js`
- `pages/builds/builds.wxml`
- `pages/builds/builds.wxss`
- `pages/builds/detail.wxml`
- `pages/builds/intel.wxml`
- `pages/builds/talent-simulator-core.js`
- `pages/builds/talent-simulator.wxml`
- `pages/builds/workbench-state.js`
- `pages/builds/workbench.js`
- `pages/builds/workbench.json`
- `pages/builds/workbench.wxml`
- `pages/builds/workbench.wxss`
- `pages/news/detail.wxml`
- `pages/news/list.wxml`
- `pages/news/news-api.js`
- `pages/news/news.js`
- `pages/news/news.json`
- `pages/news/news.wxml`
- `pages/news/news.wxss`
- `pages/profile/profile.js`
- `pages/profile/profile.wxml`
- `pages/profile/profile.wxss`
- `pages/pve/detail.wxml`
- `pages/pve/pve.wxml`
- `pages/simulator/chickenbro-chat.js`
- `pages/simulator/chickenbro.wxml`
- `pages/simulator/chickenbro.wxss`
- `pages/simulator/simc.js`
- `pages/simulator/simc.wxml`
- `pages/simulator/simc.wxss`
- `pages/simulator/simulator.wxml`
- `pages/simulator/simulator.wxss`
- `pages/simulator/task-detail.wxml`
- `pages/simulator/tasks.js`
- `pages/simulator/tasks.wxml`
- `pages/simulator/tasks.wxss`
- `pages/simulator/wcl.wxml`
- `project.config.json`

## Required Action

Freeze or quarantine core page/App/navigation changes until both of these exist:

- `docs/design/2026-07-07-wow-ui-system-target-locked-decision.md`
- `docs/plans/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit.md` or the single active permit selected by the target lock

Until then, valid work is limited to evidence, design docs, component owner contracts, source-level owner skeletons, asset manifests, preflight scripts, tests, and browser/component prechecks.

## Non-Promotion Boundary

This preflight is not:

- `target_locked`
- `active_implementation_permit`
- page integration evidence
- `runtime_verified`
- `final_accepted`
