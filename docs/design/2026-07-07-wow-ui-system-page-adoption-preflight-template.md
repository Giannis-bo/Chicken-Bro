# WOW UI System Page Adoption Preflight Template

Status: `page_adoption_preflight_template_only`

Date: 2026-07-07

This template defines the static page-adoption gate for the WOW mini-program UI system rebuild. It checks whether core pages compose owner components instead of rebuilding geometry in page WXML/WXSS. It does not authorize page implementation and does not prove runtime verification.

## Linked Control Plane

- [WOW 小程序 UI 系统重建完整 Goal](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Foundation Component Contracts](2026-07-07-wow-ui-system-foundation-component-contracts.md)
- [Surface Owner Contracts](2026-07-07-wow-ui-system-surface-owner-contracts.md)
- [Implementation Gate](2026-07-07-wow-ui-system-implementation-gate.md)
- [Route Smoke Execution Manifest Template](2026-07-07-wow-ui-system-route-smoke-execution-template.md)
- Preflight: `scripts/ui-system-page-adoption-preflight.js`
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-page-adoption-preflight-template/manifest.json`

## Command

```sh
node scripts/ui-system-page-adoption-preflight.js --require-adoption --json
```

Current expected exit code before permitted page integration: `12`.

## What It Checks

Every core page must:

- register required owner components in `usingComponents`;
- render the required owner component tags in WXML;
- keep page WXML to composition, props, slots and route event binding;
- avoid direct page `<image>` material usage;
- avoid generated/reference/pass36/pass37 assets in page WXML/WXSS;
- avoid old page-private geometry classes such as `page-shell`, `page-scroll`, `surface-material`, `verdict-slab`, `workbench-*`, `chat-bubble`, `topic-drawer`, `profile-cockpit`, `template-card` and pass36/pass37 aliases;
- avoid legacy `status-badge`; state visuals must flow through `StatusVisual`.

## Required Page Ownership

| Page | Required Owner Components |
| --- | --- |
| `pages/news/news` | `app-shell`, `page-frame`, `channel-dock`, `ranked-feed` |
| `pages/news/list` | `app-shell`, `page-frame`, `article-list-board` |
| `pages/news/detail` | `app-shell`, `page-frame`, `article-reader` |
| `pages/builds/builds` | `app-shell`, `page-frame`, `builds-tab-surface` |
| `pages/builds/workbench` | `app-shell`, `page-frame`, `workbench-cockpit-surface` |
| `pages/builds/talent-simulator` | `app-shell`, `page-frame`, `talent-tree-canvas` |
| `pages/builds/detail` | `app-shell`, `page-frame`, `gear-loadout-board`, `gear-config-sheet` |
| `pages/simulator/simc` | `app-shell`, `page-frame`, `wow-panel`, `evidence-ledger`, `action-button`, `module-card` |
| `pages/simulator/simulator` | `app-shell`, `page-frame`, `chickenbro-coach-surface`, `chat-shell` |
| `pages/simulator/chickenbro` | `app-shell`, `page-frame`, `chickenbro-coach-surface`, `chat-shell` |
| `pages/simulator/tasks` | `app-shell`, `page-frame`, `task-queue-board` |
| `pages/simulator/task-detail` | `app-shell`, `page-frame`, `task-result-report` |
| `pages/profile/profile` | `app-shell`, `page-frame`, `profile-identity-panel`, `template-library-board` |

## Current Boundary

The current source tree is expected to fail this preflight because page WXML/WXSS still contains historical page-private geometry and direct generated material references. That failure is useful: it prevents current page files from being mistaken for the vNext page-adoption state.

## Non-Promotion Boundary

This template can only prove `page_adoption_preflight_template_only`. Even a future passing page-adoption preflight would still be below real mini-program screenshots, component crops, overlay, red-zone, scorecard, route smoke execution and DevTools action ledger.
