# WOW UI System SimC Implementation Permit Draft

Status: `implementation_permit_draft`

This is the single-surface permit draft for rebuilding the SimC template-submission page as the verified handoff cockpit after the current spec workbench. It is not `target_locked`, not an active implementation permit, and does not authorize page WXML/WXSS edits.

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
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-simc-permit-draft/manifest.json`

## Surface

Surface: `simc`

Route:

- `/pages/simulator/simc`

Reason to draft this now:

- It receives `ready_to_simulate` workbench handoff and owns the real submit gate.
- It is the first page where a user can turn saved talent and gear templates into a SimC task, so unsupported DPS preview or fake readiness would be especially damaging.
- Current source already has useful deterministic gates: template selection, gear stat snapshot validation, confirm-only analysis, active task limit and final task submission.

## Current Source Findings

These findings are diagnostic evidence, not permission to patch:

- `pages/simulator/simc.wxml` composes `template-hero`, `template-selector`, `confirm-summary`, `blocked-panel`, `result-panel`, `preparation-panel`, fixed `action-bar` and `selector-sheet` directly with page-private classes.
- `pages/simulator/simc.wxss` owns page background, panel geometry, selector sheet geometry, bottom action-bar layout, disabled/loading button states and compact selector tracks.
- `pages/simulator/simc.wxml` references generated `ui-redesign/20260701` material directly from page WXML.
- `pages/simulator/simc.js` uses `mode: 'simcraft_template'`, `confirmTemplateSimulation()` for validation and `submitConfirmedTask()` for final save/submit.
- `pages/simulator/simc.js` enforces an active SimC template task limit of 2 and translates `taskLock.reason=active_simc_task_limit` into user-facing Chinese copy.
- `pages/simulator/simc.js` already localizes common raw SimC diagnostics and crash text; the UI permit must preserve this and forbid raw traceback, raw command, raw profile or secret-like values.
- Current summary-stat UI can show verified gear stat snapshot values, but it must not be treated as DPS, ranking, percentile, grade or upgrade-priority output.

## Target Dependency

This draft assumes the target proposal direction `A-Cockpit + B-Ledger + C-Captain`, but it cannot activate until the user confirms or edits the target lock.

Required before activation:

- `target_locked` design for SimC workbench handoff, blocked templates, ready submit gate and task-created states.
- Accepted or revised asset manifest with production / quarantine / real source-map sections.
- Clean production component precheck.
- Clean browser component precheck.
- Explicit user or owner approval to convert this draft into an active implementation permit.

## Intended Component Owners

| Owner | Role On SimC |
| --- | --- |
| `PageFrame` | Stack route gutters, scroll bounds, safe-area and fixed-action clearance. |
| `WowPanel` | Handoff header, template selectors, confirm summary, blocked state and task-state shells. |
| `StatusVisual` | Missing templates, validation blocked, ready, submitting, submitted, task-limit and failed states. |
| `ActionButton` | Confirm, submit, retry, go-to-template and view-task actions. |
| `EvidenceLedger` | Template pair evidence, gear stat snapshot status, validation blockers, active task limit and run policy rows. |
| `ModuleCard` | Talent template, gear template, scenario, combat preparation and task lock compact modules. |
| `GameObjectIcon` | Real class/spec/talent/gear icons only when sourced from payload, mapping, repository asset or text fallback. |
| `MaterialImage` | Low-semantic panel/background/socket material through component-owned fit and opacity. |

Pages may bind selected class/race/templates/scenario, confirmation result and submit state, but may not own panel geometry, selector geometry, fixed button geometry, status visuals or evidence-row tracks.

## Proposed Allowed Files After Activation

These files would be allowed only after this draft becomes an active permit:

- `pages/simulator/simc.wxml`
- `pages/simulator/simc.wxss`
- `pages/simulator/simc.js`
- `pages/simulator/simc.json`
- `pages/simulator/simulator-api.js` only if existing client shape needs UI-facing normalization and no backend contract changes are introduced
- `components/page-frame/*`
- `components/wow-panel/*`
- `components/status-visual/*`
- `components/action-button/*`
- `components/evidence-ledger/*`
- `components/module-card/*`
- `components/game-object-icon/*`
- `components/material-image/*`
- narrowly scoped simulator and UI system tests
- SimC-specific browser/runtime evidence under `artifacts/ui-system-rebuild/`

Any change outside this list requires a revised permit.

## Forbidden Files And Actions

- No `app.json` route or tabBar changes.
- No `project.config.json` / appid / DevTools shadow changes.
- No backend API contract changes.
- No unrelated workbench, builds tab, talent simulator, gear detail, Chickenbro, task detail, profile or news page edits.
- No page-private template selector, panel, status, action button, selector sheet, fixed action-bar, evidence row or material geometry.
- No direct page reference to quarantine assets, whole-page target images or pass-named generated glyphs.
- No generated class/spec/talent/item/source icon pretending to be real WoW evidence.
- No DPS preview before a real final SimC task result exists.
- No visible `综合评分`, `S 级`, `A级`, `提升优先级`, ranking, percentile or fake upgrade conclusion.
- No raw SimC profile, raw command, raw traceback, raw log payload, token, openid, user id or database id.
- No WeChat DevTools open/close/restart/cache-clear/login/logout actions.

## Data Boundary

Allowed data sources:

- Existing `fallbackBuildsHome()` and `requestBuildsHome()` class/spec payload.
- Existing local and remote build templates through `listBuildTemplates()`, `fetchBuildTemplates()` and `syncBuildTemplate()`.
- Existing gear stat snapshot path through `requestWebsimGearStats()`.
- Existing simulator API client through `requestSimulatorAnalysis()` and `requestSimulatorTasks()`.
- Existing `mode: 'simcraft_template'` request path.
- Existing active task limit handling for queued/running SimC template tasks.

Required UI mapping:

- `from=workbench`: show bounded class/spec/scenario context and return/back-link language, not raw profile data.
- `missing_templates`: show which template type is missing and route to talent/gear/profile without enabling submit.
- `gear_stat_blocked`: show localized gear stat blocker and keep confirm/submit disabled.
- `confirm_ready`: enable confirm only when class, talent template and gear template are selected and stat validation is not blocked.
- `template_ready`: show that the combination passed validation and enable submit only if active task limit is not reached.
- `task_limit`: show active task limit language and keep submit disabled.
- `submitting`: disable confirm/submit and keep fixed action layout stable.
- `task_created`: show submitted state and route to task list/detail when available.
- `failed`: show localized retry guidance without raw SimC diagnostics.

Forbidden product claims:

- No DPS or damage preview during selection or confirm-only state.
- No comprehensive score.
- No S/A grade.
- No upgrade priority.
- No fake official, verified or source logo.
- No real WoW icon unless it comes from payload, Battle.net/WebSim mapping, repository verified asset or user-provided source.
- No raw profile, raw command, raw traceback, raw task payload or secret-like value.

## Asset Boundary

Allowed:

- Low-semantic panel, border, texture, socket and decorative material after manifest approval.
- Real class/spec/talent/gear icons through verified source map and `GameObjectIcon`.
- Text fallback for missing real object icons.
- Status material only through `StatusVisual`.

Forbidden:

- Imagegen class/spec/talent/item/source icons.
- Imagegen numbers, DPS, scores, labels or business conclusions.
- Whole-page target images or contact sheets in production WXML/WXSS.
- Fake time, battery, Wi-Fi, phone frame or WeChat capsule.
- Direct `ui-redesign` or `ui-v2-1-slices` page references outside active permit production manifest entries.

## Route Smoke Scope

Required scenes after implementation:

- `simc_from_workbench`: `/pages/simulator/simc?from=workbench&spec=<spec>` shows context strip, template selection and submit gate.
- `simc_blocked_templates`: missing talent or gear templates keep confirm/submit disabled and show next action.
- `simc_gear_stat_blocked`: gear stat blocker appears in player language and no submit path opens.
- `simc_confirm_ready`: valid template pair enables confirm, not submit.
- `simc_template_ready`: confirm-only pass enables submit and shows validation evidence.
- `simc_task_limit`: active task limit disables submit with user-facing explanation.
- `simc_submitting`: submitting state keeps fixed action area stable.
- `simc_task_created`: final submit creates or records task state and offers task route.

Required assertions:

- No horizontal overflow on compact / standard / large.
- No fake host chrome.
- Fixed action bar does not cover content, bottom tab or safe-area.
- No DPS preview, score, tier or upgrade-priority claim before final task result.
- Selector sheet stays inside viewport and handles long template names.
- Confirm and submit states are visually distinct and disabled/loading states are component-owned.
- Raw SimC diagnostics are not visible.
- No quarantine asset reference.

## Evidence Required Before Runtime Acceptance

- Browser scene precheck for all SimC states listed above.
- Real WeChat mini-program screenshots after `captureSafe=true`.
- Component crops for `PageFrame`, `WowPanel`, `StatusVisual`, `ActionButton`, `EvidenceLedger`, `ModuleCard` and selector sheet.
- Current / target / implementation comparison.
- Overlay and red-zone output for route context strip, selector rows, confirm summary, blocked panel, fixed action bar, selector sheet and bottom safe-area.
- Scorecard that explicitly rejects fake DPS preview, removed submit gate, raw SimC diagnostics, fixed-button overlap, page-private material geometry and hidden task-limit state.
- Route smoke report and DevTools action ledger.

## Rollback And Stop Conditions

Stop implementation and return to permit revision if any of these occur:

- The target is still not locked.
- A required component owner needs page-private WXML/WXSS geometry to look acceptable.
- The page needs new backend fields or fake front-end fields to express readiness.
- The UI needs DPS preview before final task result.
- Raw SimC diagnostics, raw profile or secret-like values are needed to explain failure.
- Browser precheck passes but real mini-program screenshot shows fixed action bar, tab/safe-area or selector-sheet overlap.
- DevTools capture is not safe or would require high-disturbance actions.

## Current Status

This draft is ready for target-lock review. It does not activate implementation.
