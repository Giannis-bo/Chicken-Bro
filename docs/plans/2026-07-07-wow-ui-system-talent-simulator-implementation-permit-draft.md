# WOW UI System Talent Simulator Implementation Permit Draft

Status: `implementation_permit_draft`

This is the single-surface permit draft for rebuilding the native WebSim talent simulator page inside the WOW mini-program UI system. It is not `target_locked`, not an active implementation permit, and does not authorize page WXML/WXSS edits.

## Linked Control Plane

- [WOW 小程序 UI 系统重建完整 Goal](2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Phase 1/2 Inventory](2026-07-07-wow-mini-program-ui-system-rebuild-phase1-inventory.md)
- [Target Lock Proposal](../design/2026-07-07-wow-ui-system-target-lock-proposal.md)
- [Foundation Component Contracts](../design/2026-07-07-wow-ui-system-foundation-component-contracts.md)
- [Asset Manifest Draft](../design/2026-07-07-wow-ui-system-asset-manifest-draft.md)
- [Implementation Permit Coverage Matrix](../design/2026-07-07-wow-ui-system-implementation-permit-coverage-matrix.md)
- [Route Smoke And Runtime Verification Plan](../design/2026-07-07-wow-ui-system-route-smoke-plan.md)
- [Production Component Precheck](../design/2026-07-07-wow-ui-system-production-component-precheck.md)
- [Browser Component Precheck](../design/2026-07-07-wow-ui-system-browser-component-precheck.md)
- [TalentTreeCanvas Owner Skeleton Source Precheck](../design/2026-07-07-wow-ui-system-talent-tree-canvas-owner-skeleton-precheck.md)
- [TalentTreeCanvas Component Precheck](../design/2026-07-07-wow-ui-system-talent-tree-canvas-component-precheck.md)
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-talent-simulator-permit-draft/manifest.json`

## Surface

Surface: `talent_simulator`

Route:

- `/pages/builds/talent-simulator`

Reason to draft this now:

- It is the first missing permit in the current implementation permit coverage matrix.
- It owns real WebSim talent-tree interaction, point gates, choice nodes, community template import and local/remote talent-template persistence.
- It is the upstream input page for workbench readiness and SimC template submission, so any fake icon, broken tree geometry or lost save gate can corrupt later readiness.

## Current Source Findings

These findings are diagnostic evidence, not permission to patch:

- `pages/builds/talent-simulator.wxml` directly composes `talent-header`, `talent-toolbar`, `tree-tabs`, `active-tree-panel`, `talent-grid`, `talent-node`, fixed `mobile-action-bar`, `talent-choice-sheet`, `talent-detail-sheet`, `template-save-sheet` and `community-template-sheet`.
- `pages/builds/talent-simulator.wxss` owns page background, panel borders, picker geometry, tree-tab geometry, active tree panel, node shape, choice frame, arrows, link lines, rank badge, fixed action bar and sheet geometry with page-private classes.
- `pages/builds/talent-simulator.js` uses `fallbackBuildsHome()`, `requestBuildsHome()`, `requestWebsimBootstrap()` and `requestWebsimTalents()` to build the page state.
- `pages/builds/talent-simulator.js` delegates the actual talent rules to `talent-simulator-core`: `buildTalentViewModel()`, `initialTalentRanks()`, `tapTalentNode()`, `adjustTalentRank()`, `choiceGroupNodes()`, `parseTalentExportCode()` and community template helpers.
- `pages/builds/talent-simulator-core.js` owns point caps, granted ranks, parent requirements, choice mutual exclusion, shape normalization, link geometry, selected-node signatures and WebSim export code generation.
- The page already blocks saving when the WebSim talent payload is fallback, when `talentAuthority.diffStatus` is blocked, when `talentReadiness.simcReady === false`, when the export code is missing, or when class/spec/hero trees are not fully capped.
- The page currently saves `type: 'talent'` templates through `syncBuildTemplate()` with `rawString` as a WebSim export code and keeps `simcLines: []`.
- The page supports personal template import, community template import, cross-spec community template switching, simc-only template refusal and missing credential copy.
- Real talent icons are attached through `attachGameAsset()` as `entityType: 'talent'`; missing icons fall back to text.

## Target Dependency

This draft assumes the target proposal direction `A-Cockpit + B-Ledger + C-Captain`, but it cannot activate until the user confirms or edits the target lock.

Required before activation:

- `target_locked` design for the talent-tree shell, class/spec/hero pickers, tree tabs, node states, choice sheet, detail sheet, save sheet and community import sheet.
- Accepted or revised asset manifest with production / quarantine / real source-map sections.
- `TalentTreeCanvas` owner skeleton and fixture matrix remain aligned with the target lock.
- Clean `TalentTreeCanvas` surface component precheck rerun before activation.
- Explicit user or owner approval to convert this draft into an active implementation permit.

## Current Owner Evidence

`TalentTreeCanvas` has now advanced from owner contract draft to source-level owner skeleton and surface component precheck:

- Owner skeleton: [TalentTreeCanvas Owner Skeleton Source Precheck](../design/2026-07-07-wow-ui-system-talent-tree-canvas-owner-skeleton-precheck.md)
- Component precheck: [TalentTreeCanvas Component Precheck](../design/2026-07-07-wow-ui-system-talent-tree-canvas-component-precheck.md)
- Fixture matrix: `artifacts/ui-system-rebuild/20260707-talent-tree-canvas-owner-skeleton/fixtures.json`
- Component crops and contact sheet: `artifacts/ui-system-rebuild/20260707-talent-tree-canvas-component-precheck/component-crop-contact-sheet.png`

Current precheck result: `surface_component_precheck`, failures `0`, warnings `0`, crops `8`, viewports `compact / standard / large`, `pageIntegration=false`, `devtoolsTouched=false`.

This still does not activate the permit. The page remains unintegrated until target lock and explicit active permit conversion.

## Intended Component Owners

| Owner | Role On Talent Simulator |
| --- | --- |
| `PageFrame` | Stack route gutters, scroll bounds, safe-area and fixed-action clearance. |
| `WowPanel` | Header, toolbar, tree tabs, active tree shell, export summary and sheet shells. |
| `TalentTreeCanvas` | Surface-specific owner for tree grid dimensions, node positions, link lines, choice node frame, rank badge and touch target geometry. |
| `GameObjectIcon` | Real talent icon sockets and text fallback only from payload/mapping/repository/user-provided source. |
| `StatusVisual` | Loading, blocked, fallback, partial, source_reference and save-readiness status labels. |
| `ActionButton` | Save, import, reset, apply, cancel, rank stepper and sheet primary/secondary actions. |
| `EvidenceLedger` | Talent authority, readiness blockers, community source status, checkedAt/source rows and save blockers. |
| `ModuleCard` | Compact class/spec/hero/tree status modules where the target design needs summary cards. |
| `MaterialImage` | Low-semantic panel/background/socket material through component-owned fit and opacity. |

Pages may bind selected class/spec/hero, active tree key, talent ranks, sheet visibility and template actions, but may not own panel geometry, tree geometry, node shape, icon sockets, fixed button geometry, sheet layout or evidence-row tracks.

## Proposed Allowed Files After Activation

These files would be allowed only after this draft becomes an active permit:

- `pages/builds/talent-simulator.wxml`
- `pages/builds/talent-simulator.wxss`
- `pages/builds/talent-simulator.js`
- `pages/builds/talent-simulator.json`
- `pages/builds/talent-simulator-core.js` only for UI-facing view-model fields required by the owner component, not for changing talent game rules without dedicated tests
- `pages/builds/websim-api.js` only if existing client shape needs UI-facing normalization and no backend contract changes are introduced
- `components/page-frame/*`
- `components/wow-panel/*`
- `components/talent-tree-canvas/*`
- `components/game-object-icon/*`
- `components/status-visual/*`
- `components/action-button/*`
- `components/evidence-ledger/*`
- `components/module-card/*`
- `components/material-image/*`
- narrowly scoped `tests/builds-page.test.js`, `tests/talent-simulator-core.test.js`, `tests/frontend-api-client.test.js` and UI-system tests
- Talent-simulator-specific browser/runtime evidence under `artifacts/ui-system-rebuild/`

Any change outside this list requires a revised permit.

## Forbidden Files And Actions

- No `app.json` route or tabBar changes.
- No `project.config.json` / appid / DevTools shadow changes.
- No backend API contract changes.
- No unrelated workbench, builds tab, gear detail, SimC, Chickenbro, task detail, profile or news page edits.
- No page-private tree node, link line, choice frame, rank badge, panel, status, action button, fixed action-bar, evidence row, sheet or material geometry.
- No direct page reference to quarantine assets, whole-page target images or pass-named generated glyphs.
- No generated class/spec/hero/talent/source icon pretending to be real WoW evidence.
- No fake DPS, comprehensive score, S/A grade, percentile, ranking or upgrade-priority claim.
- No weakening parent requirement, point cap, granted rank, choice mutual exclusion, cross-spec template, fallback-block or save-readiness rules to make a visual target easier.
- No raw backend payload, raw internal blocker key, token, openid, user id or database id in visible UI.
- No WeChat DevTools open/close/restart/cache-clear/login/logout actions.

## Data Boundary

Allowed data sources:

- Existing `fallbackBuildsHome()` and `requestBuildsHome()` class/spec payload.
- Existing `requestWebsimBootstrap()` scenario/current-season/class metadata.
- Existing `requestWebsimTalents()` payload for nodes, tree sections, hero key, talent authority, readiness and community templates.
- Existing `talent-simulator-core` rule helpers for point gates, choice groups, node shape, export code, community template filtering and cross-spec application.
- Existing local and remote talent template storage through `listBuildTemplates('talent')` and `syncBuildTemplate()`.
- Existing `attachGameAsset()` / `GameObjectIcon` path for talent icon source and fallback.

Required UI mapping:

- `from_workbench`: show bounded class/spec/hero context and a return/back-link language, not raw profile data.
- `loading_bootstrap`: show bootstrap loading state without hiding safe-area or bottom actions.
- `loading_talents`: show class/spec/hero context and tree skeleton without fake nodes.
- `fallback_blocked`: show backend/WebSim fallback reason and keep save disabled.
- `authority_blocked`: show talent authority or SimulationCraft catalog blocker and keep save disabled.
- `tree_ready`: show real class/spec/hero tree tabs, point caps and export-code readiness.
- `node_locked`: show parent/gate/cap reason in user language.
- `choice_sheet`: show mutually exclusive choices with real talent icons or text fallback.
- `node_detail_sheet`: show rank stepper only for rankable nodes and keep granted-floor protection.
- `save_blocked`: show missing points or backend blocker and keep template save disabled.
- `save_ready`: show save action only after class/spec/hero trees are capped and WebSim export code is available.
- `template_saved`: close save sheet and surface saved status without changing tree ranks.
- `personal_import`: apply local saved WebSim export code only when it matches or can switch to target class/spec/hero.
- `community_visual_import`: apply visual community templates and preserve cross-spec switch behavior.
- `community_simc_only`: refuse simc-only external code in the visual editor with user-facing copy.
- `community_missing_credentials`: show source status without presenting missing data as zero popularity.

Forbidden product claims:

- No DPS, damage, ranking, percentile, tier, S/A grade, comprehensive score or upgrade priority.
- No fake official, verified or source logo.
- No real WoW icon unless it comes from payload, Battle.net/WebSim mapping, repository verified asset or user-provided source.
- No community popularity claim unless payload provides sample count, key level, source and checkedAt/source window.
- No raw internal blocker keys or raw backend payload fields in user text.

## Asset Boundary

Allowed:

- Low-semantic panel, border, texture, socket and decorative material after manifest approval.
- Real talent icons through verified source map and `GameObjectIcon`.
- Text fallback for missing talent icons.
- Node/socket material only through `TalentTreeCanvas` and `GameObjectIcon`.
- Status material only through `StatusVisual`.

Forbidden:

- Imagegen class/spec/hero/talent/source icons.
- Imagegen talent names, node ranks, point counts, DPS, scores, labels or business conclusions.
- Whole-page target images or contact sheets in production WXML/WXSS.
- Fake time, battery, Wi-Fi, phone frame or WeChat capsule.
- Direct `ui-redesign` or `ui-v2-1-slices` page references outside active permit production manifest entries.

## Route Smoke Scope

Required scenes after implementation:

- `talent_simulator_from_builds`: `/pages/builds/talent-simulator?spec=<spec>` loads selected class/spec context.
- `talent_simulator_from_workbench`: `/pages/builds/talent-simulator?from=workbench&spec=<spec>` keeps bounded return context.
- `talent_loading_bootstrap`: bootstrap loading state is stable.
- `talent_loading_tree`: talent tree loading state is stable.
- `talent_tree_ready`: real nodes, links, tree tabs and point caps render.
- `talent_switch_class_spec`: class/spec picker reloads the target tree and resets incompatible hero key safely.
- `talent_switch_hero`: hero picker reloads the hero tree and activates hero tab.
- `talent_tree_tab_switch`: class/hero/spec tabs switch without layout overflow.
- `talent_node_locked`: locked node exposes user-language reason.
- `talent_choice_sheet`: choice-group tap opens stable sheet and selection remains mutually exclusive.
- `talent_detail_sheet`: long press opens node detail and rank stepper respects max/granted floor.
- `talent_save_blocked`: incomplete or backend-blocked tree keeps save disabled and explains blocker.
- `talent_save_ready`: complete tree enables save sheet without fake SimC result.
- `talent_personal_import`: saved template import applies WebSim export code or refuses invalid code.
- `talent_community_visual_import`: community visual template applies or switches target tree.
- `talent_community_simc_only`: external-code-only template is refused in visual editor.
- `talent_community_missing_credentials`: missing source credentials show partial/blocked copy without fake counts.

Required assertions:

- No horizontal overflow on compact / standard / large.
- No fake host chrome.
- Fixed action bar does not cover tree, sheets, bottom tab or safe-area.
- Tree canvas keeps node touch targets, link lines and rank badges inside its measured bounds.
- Choice node base, arrows, icon crop and rank badge are owned by one component and do not split.
- Long talent names, long template names and missing icons do not resize the tree grid.
- Save/import/reset buttons keep stable size in disabled/loading states.
- No DPS preview, score, tier, ranking or upgrade-priority claim.
- No raw backend blockers or secret-like values are visible.
- No quarantine asset reference.

## Evidence Required Before Runtime Acceptance

- Browser scene precheck for all talent scenes listed above.
- Real WeChat mini-program screenshots after `captureSafe=true`.
- Component crops for `PageFrame`, `WowPanel`, `TalentTreeCanvas`, `GameObjectIcon`, `StatusVisual`, `ActionButton`, `EvidenceLedger`, sheet components and fixed action area.
- Current / target / implementation comparison.
- Overlay and red-zone output for header, pickers, tree tabs, tree canvas, choice node, choice sheet, detail sheet, save sheet, community sheet, fixed action bar and bottom safe-area.
- Scorecard that explicitly rejects fake icons, tree overflow, broken choice-node geometry, removed save gate, lost community import behavior, raw blockers, fixed-button overlap and page-private material geometry.
- Route smoke report and DevTools action ledger.

## Rollback And Stop Conditions

Stop implementation and return to permit revision if any of these occur:

- The target is still not locked.
- `TalentTreeCanvas` or equivalent tree owner is not defined before page integration.
- A required owner needs page-private WXML/WXSS geometry to look acceptable.
- The page needs new backend fields or fake front-end fields to express readiness.
- The UI needs fake official talent icons, fake popularity, fake ranking or fake DPS to look complete.
- Talent-rule tests fail or visual changes require weakening point caps, parent gates, choice exclusivity or save-readiness gates.
- Browser precheck passes but real mini-program screenshot shows tree canvas, fixed action bar, tab/safe-area or sheet overlap.
- DevTools capture is not safe or would require high-disturbance actions.

## Current Status

This draft is ready for target-lock review and active-permit decision after `TalentTreeCanvas` owner evidence. It does not activate implementation.

`TalentTreeCanvas` now has source-level owner skeleton, fixture matrix and surface component precheck with browser crops. Before page integration, rerun the component precheck against the locked target and convert this draft into an active permit.
