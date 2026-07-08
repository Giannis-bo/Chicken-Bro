# WOW UI System Builds Tab Implementation Permit Draft

Status: `implementation_permit_draft`

This is the single-surface permit draft for rebuilding the `职业专精` tab as the upstream entry to the current spec workbench, talent simulator, gear detail, SimC and task history. It is not `target_locked`, not an active implementation permit, and does not authorize page WXML/WXSS edits.

## Linked Control Plane

- [WOW 小程序 UI 系统重建完整 Goal](2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Phase 1/2 Inventory](2026-07-07-wow-mini-program-ui-system-rebuild-phase1-inventory.md)
- [Target Lock Proposal](../design/2026-07-07-wow-ui-system-target-lock-proposal.md)
- [Foundation Component Contracts](../design/2026-07-07-wow-ui-system-foundation-component-contracts.md)
- [Builds Tab Owner Skeleton Source Precheck](../design/2026-07-07-wow-ui-system-builds-tab-owner-skeleton-precheck.md)
- [Builds Tab Component Precheck](../design/2026-07-07-wow-ui-system-builds-tab-component-precheck.md)
- [Asset Manifest Draft](../design/2026-07-07-wow-ui-system-asset-manifest-draft.md)
- [Implementation Permit Coverage Matrix](../design/2026-07-07-wow-ui-system-implementation-permit-coverage-matrix.md)
- [Route Smoke And Runtime Verification Plan](../design/2026-07-07-wow-ui-system-route-smoke-plan.md)
- [Production Component Precheck](../design/2026-07-07-wow-ui-system-production-component-precheck.md)
- [Browser Component Precheck](../design/2026-07-07-wow-ui-system-browser-component-precheck.md)
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-builds-tab-permit-draft/manifest.json`

## Surface

Surface: `builds_tab`

Route:

- `/pages/builds/builds`

Reason to draft this now:

- It is the tab entry for the entire build workflow and the upstream route into workbench, talent simulator, gear detail, SimC and tasks.
- The target explicitly requires current spec console, primary workbench entry, compact class/spec/hero controls and old entries still reachable.
- Current source inspection shows the tab still owns hero, workbench-entry, module row, query card and material geometry directly in page WXML/WXSS.

## Current Source Findings

These findings are diagnostic evidence, not permission to patch:

- `pages/builds/builds.wxml` composes `builds-spec-console`, `workbench-entry` and `query-section` directly with page-private classes.
- `pages/builds/builds.wxss` owns shell gutters, hero grid, medallion geometry, workbench entry frame, workflow rail, quick action card geometry and compact media rules.
- `pages/builds/builds.wxml` references `ui-v2-1-slices` generated materials directly from page WXML.
- `pages/builds/builds.js` builds a default workbench entry from `fallbackBuildsHome()` / `requestBuildsHome()` and keeps old quick routes through `openQueryPage()`.
- Current tab does not expose a full compact class/spec/hero switch contract in the page itself; the active permit must decide the exact switcher UI and route handoff before implementation.
- Quick entries for talents, gear, SimC and tasks are still reachable and must remain reachable after rebuild.

## Target Dependency

This draft assumes the target proposal direction `A-Cockpit + B-Ledger + C-Captain`, but it cannot activate until the user confirms or edits the target lock.

Required before activation:

- `target_locked` design for the builds tab first screen and scrolled workflow area.
- Accepted or revised asset manifest with production / quarantine / real source-map sections.
- Clean BuildsTabSurface production/browser component precheck rerun.
- Clean browser component precheck.
- Explicit user or owner approval to convert this draft into an active implementation permit.

## Intended Component Owners

| Owner | Role On Builds Tab |
| --- | --- |
| `BuildsTabSurface` | Current spec console, compact class/spec/hero switchers, promoted workbench entry, preserved old entry grid and entry evidence. |
| `AppShell` | App background, tab-safe floor and no fake host chrome. |
| `PageFrame` | Tab route gutters, scroll bounds, bottom tab padding and top rhythm. |
| `WowPanel` | Current spec console, workbench entry shell and workflow section shell. |
| `GameObjectIcon` | Real class/spec/hero icons from payload, Battle.net/WebSim mapping, repo verified asset or text fallback. |
| `StatusVisual` | Workbench readiness and module state tone, including state base/glyph ownership. |
| `ActionButton` | Workbench entry action and old entry route actions. |
| `ModuleCard` | Talent, gear, SimC and task/Chickenbro compact workflow entries. |
| `MaterialImage` | Low-semantic material fit, opacity and quarantine boundary. |

Pages may bind `classOptions`, selected class/spec/hero, workbench entry state and route actions, but may not own card, status, icon socket, button, workflow rail or material geometry.

## Proposed Allowed Files After Activation

These files would be allowed only after this draft becomes an active permit:

- `pages/builds/builds.wxml`
- `pages/builds/builds.wxss`
- `pages/builds/builds.js`
- `pages/builds/builds.json`
- `pages/builds/builds-api.js` only if view-model fields are needed and no backend contract changes are introduced
- `components/app-shell/*`
- `components/page-frame/*`
- `components/wow-panel/*`
- `components/game-object-icon/*`
- `components/status-visual/*`
- `components/action-button/*`
- `components/module-card/*`
- `components/material-image/*`
- `components/builds-tab-surface/*`
- narrowly scoped builds tab and UI system tests
- builds-tab-specific browser/runtime evidence under `artifacts/ui-system-rebuild/`

Any change outside this list requires a revised permit.

## Forbidden Files And Actions

- No `app.json` route or tabBar changes.
- No `project.config.json` / appid / DevTools shadow changes.
- No backend API contract changes.
- No unrelated workbench, talent simulator, gear detail, SimC, Chickenbro, task, profile or news page edits.
- No deleting or hiding old talent, gear, SimC and task entrances.
- No page-private hero, workbench entry, module card, status, action button, icon socket, workflow rail or material geometry.
- No direct page reference to quarantine assets, whole-page target images or pass-named generated glyphs.
- No generated class/spec/hero/talent/item/source icons pretending to be real WoW evidence.
- No visible `DPS`, `综合评分`, `S 级`, `A级`, `提升优先级`, ranking, percentile or fake upgrade conclusion.
- No WeChat DevTools open/close/restart/cache-clear/login/logout actions.

## Data Boundary

Allowed data sources:

- Existing `fallbackBuildsHome()` and `requestBuildsHome()` payload.
- Existing `classOptions`, `quickActions` and local fallback view model.
- Existing `buildHomeOverview()` and `buildWorkbenchEntry()` logic if kept pure and display-only.
- Existing `classIconUrlFor()` and `specIconUrlFor()` repository mappings as fallback for real class/spec icons.
- Existing route actions to workbench, talent simulator, gear detail, SimC and tasks.

Required UI mapping:

- Current spec console must show selected class/spec/hero or conservative fallback.
- Compact class/spec/hero switchers must update selected context without layout jump.
- Workbench entry remains the highest-priority route but cannot consume the entire tab.
- Old four entries remain reachable and visibly downranked, not removed.
- Template or evidence counts may only show when present in payload or verified local state.
- Missing data must show source-reference or loading language, not fake readiness.

Forbidden product claims:

- No DPS, damage preview or simulated result on the tab.
- No comprehensive score.
- No S/A grade.
- No upgrade priority.
- No fake official, verified or source logo.
- No real WoW icon unless it comes from payload, Battle.net/WebSim mapping, repository verified asset or user-provided source.
- No raw SimC profile, raw log payload, token, openid, user id or database id.

## Asset Boundary

Allowed:

- Low-semantic panel, border, texture, socket and decorative material after manifest approval.
- Real class/spec/hero icons through verified source map and `GameObjectIcon`.
- Text fallback for missing real object icons.
- Status material only through `StatusVisual`.

Forbidden:

- Imagegen class/spec/hero/talent/item/source icons.
- Imagegen numbers, scores, labels, DPS or business conclusions.
- Whole-page target images or contact sheets in production WXML/WXSS.
- Fake time, battery, Wi-Fi, phone frame or WeChat capsule.
- Direct `ui-v2-1-slices` page references outside active permit production manifest entries.

## Route Smoke Scope

Required scenes after implementation:

- `builds_tab_top`: tab enter, current spec console, workbench primary entry and old entries reachable.
- `builds_spec_switch`: class/spec/hero control update without layout shift, fake icons or route context loss.
- `builds_workbench_entry`: tapping workbench entry reaches `/pages/builds/workbench?spec=<spec>`.
- `builds_talent_entry`: tapping talent entry reaches `/pages/builds/talent-simulator`.
- `builds_gear_entry`: tapping gear entry reaches `/pages/builds/detail?query=gear`.
- `builds_simc_entry`: tapping SimC entry reaches `/pages/simulator/simc?from=builds`.
- `builds_tasks_entry`: tapping tasks entry reaches `/pages/simulator/tasks?from=builds`.

Required assertions:

- No horizontal overflow on compact / standard / large.
- No fake host chrome.
- Bottom tab and safe-area are not covered.
- Current spec icon is real or text fallback, not imagegen.
- Old entries remain reachable after the workbench is promoted.
- Long class/spec/hero labels do not escape their owner slots.
- No quarantine asset reference.

## Evidence Required Before Runtime Acceptance

- Browser scene precheck for `builds_tab_top`, `builds_spec_switch` and each entry route.
- Real WeChat mini-program screenshots after `captureSafe=true`.
- Component crops for `PageFrame`, `WowPanel`, `GameObjectIcon`, `StatusVisual`, `ActionButton` and `ModuleCard`.
- Current / target / implementation comparison.
- Overlay and red-zone output for tab gutters, current spec console, workbench entry, old entry row/grid and bottom tab boundary.
- Scorecard that explicitly rejects removed old entries, fake class/spec icons, page-private material geometry, hidden template/evidence state and fake strong claims.
- Route smoke report and DevTools action ledger.

## Rollback And Stop Conditions

Stop implementation and return to permit revision if any of these occur:

- The target is still not locked.
- A required component owner needs page-private WXML/WXSS geometry to look acceptable.
- The class/spec/hero switcher requires new backend fields.
- The design requires deleting or hiding old talent, gear, SimC or task entrances.
- A generated image implies a real class/spec/hero/talent/item/source that is not verified.
- Browser precheck passes but real mini-program screenshot shows tab/safe-area/navigation overlap.
- DevTools capture is not safe or would require high-disturbance actions.

## Current Status

This draft is ready for target-lock review. `BuildsTabSurface` now has source-level owner skeleton evidence and a production/browser component precheck. It still does not activate implementation, and the component precheck must be rerun before any active permit conversion.
