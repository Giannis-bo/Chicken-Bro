# WOW UI System Workbench Implementation Permit Draft

Status: `implementation_permit_draft`

This is the single-surface permit draft for rebuilding the current spec workbench as the central evidence cockpit. It is not `target_locked`, not an active implementation permit, and does not authorize page WXML/WXSS edits.

## Linked Control Plane

- [WOW 小程序 UI 系统重建完整 Goal](2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Phase 1/2 Inventory](2026-07-07-wow-mini-program-ui-system-rebuild-phase1-inventory.md)
- [Target Lock Proposal](../design/2026-07-07-wow-ui-system-target-lock-proposal.md)
- [Foundation Component Contracts](../design/2026-07-07-wow-ui-system-foundation-component-contracts.md)
- [Asset Manifest Draft](../design/2026-07-07-wow-ui-system-asset-manifest-draft.md)
- [Route Smoke And Runtime Verification Plan](../design/2026-07-07-wow-ui-system-route-smoke-plan.md)
- [Workbench Owner Skeleton Source Precheck](../design/2026-07-07-wow-ui-system-workbench-owner-skeleton-precheck.md)
- [Workbench Component Precheck](../design/2026-07-07-wow-ui-system-workbench-component-precheck.md)
- [Production Component Precheck](../design/2026-07-07-wow-ui-system-production-component-precheck.md)
- [Browser Component Precheck](../design/2026-07-07-wow-ui-system-browser-component-precheck.md)
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-workbench-permit-draft/manifest.json`

## Surface

Surface: `current_spec_workbench`

Routes:

- `/pages/builds/workbench?spec=<spec>` as the stack route.
- `/pages/builds/builds` as the tab entry surface that promotes the workbench.

Reason to draft this now:

- The workbench is the page where the previous failures were most visible: edge-to-edge panels, misaligned spec picker text, split shield/glyph status visuals, compressed action button, vertically piled module cards, tiny type and lost bottom-tab context.
- It is the central product surface for the new direction: "can the current spec be simulated, why, and where should the player go next".
- Current source already has a useful pure aggregation model in `pages/builds/workbench-state.js`; the rebuild should preserve that data trust boundary while replacing page-private geometry with owner components.

## Current Source Findings

These findings are diagnostic evidence, not permission to patch:

- `pages/builds/workbench.wxml` composes hero, readiness slab, module band and evidence rows directly with page-private classes such as `workbench-hero`, `verdict-slab`, `module-card`, `evidence-row` and `primary-action`.
- `pages/builds/workbench.wxss` owns gutters, panel borders, module geometry, evidence row tracks, button sizing and state tone classes that should belong to `PageFrame`, `WowPanel`, `ModuleCard`, `EvidenceLedger`, `ActionButton` and `StatusVisual`.
- `pages/builds/workbench.wxml` still references `ui-v2-1-slices` material assets directly through page WXML; future production references must flow through approved manifest entries and owner components.
- The verdict status uses a legacy `status-badge` path and page-level `verdict-status-badge` geometry; the target owner is `StatusVisual`, including base, glyph, center point, size and transparent boundary.
- `pages/builds/builds.wxml` promotes the workbench entry but also owns the entry panel/material/module geometry locally; the active workbench permit must explicitly decide whether this tab-entry portion is in scope.
- `pages/builds/workbench-state.js` correctly keeps `canShowStrongResult: false`, exposes readiness states, maps primary actions and preserves evidence rows without DPS, score, S/A grade or upgrade-priority claims. This pure aggregation boundary should be retained.

## Target Dependency

This draft assumes the target proposal direction `A-Cockpit + B-Ledger + C-Captain`, but it cannot activate until the user confirms or edits the target lock.

Required before activation:

- `target_locked` design for the workbench first screen, evidence-expanded state and builds-tab workbench entry.
- Accepted or revised asset manifest with production / quarantine / real source-map sections.
- Clean `WorkbenchCockpitSurface` production/browser component precheck rerun before activation.
- Clean broader production component precheck and browser component precheck.
- Explicit user or owner approval to convert this draft into an active implementation permit.

## Intended Component Owners

| Owner | Role On Workbench |
| --- | --- |
| `PageFrame` | Route gutters, scroll bounds, tab-safe bottom spacing and top rhythm. |
| `WowPanel` | Workbench hero, readiness slab, module band and evidence section shell. |
| `StatusVisual` | `ready_to_simulate / blocked / partial / stale / source_reference / unknown` state base, glyph, center point, size and transparent boundary. |
| `ActionButton` | Primary action, blocker action and evidence toggle sizing/state. |
| `ModuleCard` | Four-module status band for talents, gear, SimC and Chickenbro. |
| `EvidenceLedger` | Preview and expanded evidence rows, coverage, checkedAt, blockers, template count and source language. |
| `GameObjectIcon` | Real class/spec/talent/gear icons from verified source map or payload; text fallback otherwise. |
| `MaterialImage` | Low-semantic background, panel, border, socket and decorative material through component-owned fit. |

Pages may bind selected spec, scenario, aggregate state and route actions, but may not own panel geometry, status geometry, button geometry, module-card layout or evidence-row tracks.

## Proposed Allowed Files After Activation

These files would be allowed only after this draft becomes an active permit:

- `pages/builds/workbench.wxml`
- `pages/builds/workbench.wxss`
- `pages/builds/workbench.js`
- `pages/builds/workbench.json`
- `pages/builds/workbench-state.js`
- `pages/builds/builds.wxml` for the workbench entry only
- `pages/builds/builds.wxss` for the workbench entry only
- `pages/builds/builds.js` for route/query handoff only
- `components/page-frame/*`
- `components/wow-panel/*`
- `components/status-visual/*`
- `components/action-button/*`
- `components/module-card/*`
- `components/evidence-ledger/*`
- `components/game-object-icon/*`
- `components/material-image/*`
- narrowly scoped builds/workbench and UI system tests
- workbench-specific browser/runtime evidence under `artifacts/ui-system-rebuild/`

Any change outside this list requires a revised permit.

## Forbidden Files And Actions

- No `app.json` route or tabBar changes.
- No `project.config.json` / appid / DevTools shadow changes.
- No backend API contract changes.
- No unrelated news, simulator, Chickenbro chat, profile, task or talent/gear detail page edits.
- No page-private shield/glyph/status, panel, card, button, socket, evidence row or material geometry.
- No direct page reference to quarantine assets, whole-page target images or pass-named generated glyphs.
- No generated class/spec/talent/item/source icon pretending to be real WoW evidence.
- No visible `DPS`, `综合评分`, `S 级`, `A级`, `提升优先级`, ranking, percentile or fake upgrade conclusion.
- No WeChat DevTools open/close/restart/cache-clear/login/logout actions.

## Data Boundary

Allowed data sources:

- Existing `/api/websim/talents` through `requestWebsimTalents()`.
- Existing `/api/websim/gear` through `requestWebsimGear()`.
- Existing `fallbackBuildsHome()` and `requestBuildsHome()` for class/spec matrix and default selection.
- Existing local and remote template reads through `listBuildTemplates()`, `fetchBuildTemplates()` and current template summary helpers.
- Existing pure aggregation in `pages/builds/workbench-state.js`.

Required UI mapping:

- `ready_to_simulate`: show input completeness and route to existing SimC page; do not run SimC inside the workbench.
- `blocked`: show what is missing, what it affects and the next route to fix it.
- `partial`: show usable evidence and missing coverage without a strong result.
- `stale`: show freshness problem and refresh/source action.
- `source_reference`: show source-reference language and evidence expansion, not a recommendation.
- `unknown`: use fallback state language and keep actions conservative.

Forbidden product claims:

- No DPS or damage preview.
- No comprehensive score.
- No S/A grade.
- No upgrade priority.
- No "official" or "verified" icon unless it comes from verified data state.
- No real WoW object icon unless it comes from API payload, Battle.net/WebSim mapping, repository verified asset or user-provided source.
- No raw SimC profile, raw log payload, token, openid, user id or database id.

## Asset Boundary

Allowed:

- Low-semantic panel, border, texture, socket, state-base, state-atomic and decorative material after manifest approval.
- Real class/spec/talent/item icons through verified source map and `GameObjectIcon`.
- Text fallback for missing real object icons.
- Status base/glyph material only through `StatusVisual`.

Forbidden:

- Imagegen class/spec/talent/item/source icons.
- Imagegen numbers, scores, labels, DPS or business conclusions.
- Whole-page target images or contact sheets in production WXML/WXSS.
- Fake time, battery, Wi-Fi, phone frame or WeChat capsule.
- Direct `ui-v2-1-slices` page references unless the active permit lists the exact production manifest entry and owner component.

## Route Smoke Scope

Required scenes after implementation:

- `builds_tab_top`: builds tab enters, workbench entry is primary and old four entries remain reachable.
- `workbench_ready`: readiness conclusion, primary action to SimC, four modules and evidence summary.
- `workbench_blocked_gear`: gear blocker, gear action, no DPS/score/tier, unified `StatusVisual`.
- `workbench_partial_talent`: partial talent state, evidence expansion path and no strong conclusion.
- `workbench_stale`: freshness text and refresh/source action.
- `workbench_source_reference`: only source-reference evidence, no recommendation language.
- `workbench_evidence_expanded`: coverage, checkedAt, catalogStatus, statSnapshot, template count and blockers.
- `talent_simulator_load`: workbench talent action reaches the existing talent simulator route.
- `gear_detail_load`: workbench gear action reaches the existing gear detail route.
- `simc_from_workbench`: ready action reaches `/pages/simulator/simc?from=workbench&spec=<spec>`.
- `chickenbro_workbench_context`: Chickenbro route receives bounded context without raw profile data.

Required assertions:

- No horizontal overflow on compact / standard / large.
- No fake host chrome.
- Bottom tab, safe-area and navigation boundaries are preserved.
- State visuals are a single component, not split shield/background/glyph pieces.
- Primary action keeps stable height and text containment.
- Module cards expose a clear hierarchy and do not vertically pile all content without emphasis.
- Evidence ledger rows keep readable type size and do not collapse into tiny labels.
- Real icons only represent objects/status they actually own.
- No quarantine asset reference.

## Evidence Required Before Runtime Acceptance

- Browser scene precheck for all workbench states listed above.
- Real WeChat mini-program screenshots after `captureSafe=true`.
- Component crops for `StatusVisual`, `ActionButton`, `ModuleCard`, `EvidenceLedger`, `GameObjectIcon` and workbench entry.
- Current / target / implementation comparison.
- Overlay and red-zone output for page gutters, hero/spec row, verdict slab, status visual, primary action, module band and evidence ledger.
- Scorecard that explicitly rejects edge-to-edge panels, split shield/glyph state visuals, compressed buttons, tiny type, lost first-screen information and fake strong claims.
- Route smoke report and DevTools action ledger.

## Rollback And Stop Conditions

Stop implementation and return to permit revision if any of these occur:

- The target is still not locked.
- A required component owner needs page-private WXML/WXSS geometry to look acceptable.
- State visuals cannot be expressed by `StatusVisual` without splitting base and glyph ownership.
- The page needs fake front-end facts to match the design.
- A required image implies a real class/spec/talent/item/source that is not verified.
- Browser precheck passes but real mini-program screenshot shows tab/safe-area/navigation overlap.
- DevTools capture is not safe or would require high-disturbance actions.

## Current Status

This draft is ready for target-lock review. `WorkbenchCockpitSurface` now has source-level owner skeleton evidence and a production/browser component precheck with compact / standard / large viewport screenshots, eight component crops, `failures=0`, `warnings=0` and `horizontalOverflow=0`. It still does not activate implementation, and the component precheck must be rerun before any active permit conversion.
