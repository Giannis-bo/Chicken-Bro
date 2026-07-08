# WOW UI System Tasks Implementation Permit Draft

Status: `implementation_permit_draft`

This is the single-surface permit draft for rebuilding the SimC task list and task detail pages inside the WOW mini-program UI system. It is not `target_locked`, not an active implementation permit, and does not authorize page WXML/WXSS edits.

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
- [Tasks Owner Skeleton Source Precheck](../design/2026-07-07-wow-ui-system-tasks-owner-skeleton-precheck.md)
- [Tasks Component Precheck](../design/2026-07-07-wow-ui-system-tasks-component-precheck.md)
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-tasks-permit-draft/manifest.json`

## Surface

Surface: `tasks`

Routes:

- `/pages/simulator/tasks`
- `/pages/simulator/task-detail`

Reason to draft this now:

- It is the next missing permit in the current implementation permit coverage matrix after the gear detail draft.
- It owns the task-history and result-review surface for SimC submissions, including guest task reads, list-to-detail navigation, loading, empty, queued/running/completed/failed states, localized failure summaries, final SimC result display and preview-result suppression.
- It closes the route smoke loop from workbench and SimC to saved task history; without this permit, UI rebuild can still break the downstream proof that a submitted task can be found and reviewed.

## Current Source Findings

These findings are diagnostic evidence, not permission to patch:

- `pages/simulator/tasks.wxml` directly composes `task-shell-bg`, `task-command`, `task-command-count`, `task-list-section`, `task-list-card`, `task-status`, tag rows, empty-step rows and empty actions.
- `pages/simulator/tasks.wxss` owns page background, command hero, task count module, task list card, status chip, tag chip, empty state, step index and action geometry with page-private classes.
- `pages/simulator/tasks.js` uses `requestSimulatorTasks()`, normalizes `simcReportSummary`, localizes task status, tags class/spec/hero/scenario, formats terminal times and navigates to `/pages/simulator/task-detail?id=...`.
- `pages/simulator/task-detail.wxml` directly composes `task-detail-hero`, `result-strip`, `result-cell`, SimC context rows, stat context grid and combat buff rows.
- `pages/simulator/task-detail.wxss` owns detail hero, result strip, metric cells, context cards, stat cells and combat buff row geometry with page-private classes.
- `pages/simulator/task-detail.js` uses `requestSimulatorTaskDetail()`, normalizes final SimC reports, hides generated preview DPS, localizes missing gear slots, item-name mismatches, timeouts and raw SimC crash diagnostics, and maps combat-buff preparation rows into user-facing labels.
- `pages/simulator/simulator-api.js` supports guest task list/detail reads over insecure development HTTP without bearer token by attaching `guest=1&guestId=...`.
- Existing tests protect that the task list opens task detail, localizes completed/running/failed cards, keeps guest task reads token-free when allowed, renders saved task details, hides generated preview DPS, exposes structured final SimC result, maps combat buffs, localizes timeout summaries and blocks raw SimC diagnostic leakage.

## Target Dependency

This draft assumes the target proposal direction `A-Cockpit + B-Ledger + C-Captain`, but it cannot activate until the user confirms or edits the target lock.

Required before activation:

- `target_locked` design for task history, queue status rail, empty state, task cards, status chips, detail hero, final result metric, run context, combat buffs, blocked/error states and return actions.
- Accepted or revised asset manifest with production / quarantine / real source-map sections.
- Source-level `TaskQueueBoard` owner skeleton and fixture matrix for list hero, task status rail, task cards, tags, time rows, empty-state steps and list actions. Current evidence: [Tasks Owner Skeleton Source Precheck](../design/2026-07-07-wow-ui-system-tasks-owner-skeleton-precheck.md).
- Source-level `TaskResultReport` owner skeleton and fixture matrix for detail hero, final result gate, context rows, stat snapshot rows, combat buff rows, localized failure rows and no-result states. Current evidence: [Tasks Owner Skeleton Source Precheck](../design/2026-07-07-wow-ui-system-tasks-owner-skeleton-precheck.md).
- Clean production/browser component precheck for `TaskQueueBoard` and `TaskResultReport`. Current evidence: [Tasks Component Precheck](../design/2026-07-07-wow-ui-system-tasks-component-precheck.md), status `surface_component_precheck`, failures `0`, warnings `0`, crops `10`.
- Explicit user or owner approval to convert this draft into an active implementation permit.

## Intended Component Owners

| Owner | Role On Tasks |
| --- | --- |
| `PageFrame` | Route gutters, scroll bounds, safe-area, tabBar-aware spacing and detail/list page bounds. |
| `WowPanel` | Task list sections, detail sections, empty-state shells and result/context panel structure. |
| `TaskQueueBoard` | Surface-specific owner for list hero, status rail, task cards, status chips, tags, terminal time and empty-state steps/actions. |
| `TaskResultReport` | Surface-specific owner for detail hero, final result metric, run context, stat rows, combat buffs and localized failure/no-result presentation. |
| `StatusVisual` | Loading, queued, running, completed, failed, blocked, empty, fallback and source-reference status labels. |
| `ActionButton` | Empty-state SimC/workbench actions, detail return/continue/retry actions if later enabled, and stable disabled/loading action geometry. |
| `EvidenceLedger` | Task evidence rows, result status, checkedAt/timing, scenario metadata, stat snapshot source and localized blockers. |
| `ModuleCard` | Compact task summary modules where the target design needs scannable metrics. |
| `MaterialImage` | Low-semantic panel/background/rail material through component-owned fit and opacity. |
| `GameObjectIcon` | Real class/spec/item/source icons only if payload/mapping provides verified source; text fallback otherwise. |

Pages may bind task arrays, selected task id, loading/error state, normalized detail data and route events, but may not own task-card geometry, status-chip geometry, result metric geometry, evidence-row tracks, combat-buff row layout, empty-step layout, action sizing or material fit.

## Proposed Allowed Files After Activation

These files would be allowed only after this draft becomes an active permit:

- `pages/simulator/tasks.wxml`
- `pages/simulator/tasks.wxss`
- `pages/simulator/tasks.js`
- `pages/simulator/tasks.json`
- `pages/simulator/task-detail.wxml`
- `pages/simulator/task-detail.wxss`
- `pages/simulator/task-detail.js`
- `pages/simulator/task-detail.json`
- `pages/simulator/simulator-api.js` only if existing client shape needs UI-facing normalization and no backend contract changes are introduced
- `components/page-frame/*`
- `components/wow-panel/*`
- `components/task-queue-board/*`
- `components/task-result-report/*`
- `components/status-visual/*`
- `components/action-button/*`
- `components/evidence-ledger/*`
- `components/module-card/*`
- `components/material-image/*`
- `components/game-object-icon/*`
- narrowly scoped `tests/simulator-page.test.js`, `tests/frontend-api-client.test.js` and UI-system tests
- Tasks-specific browser/runtime evidence under `artifacts/ui-system-rebuild/`

Any change outside this list requires a revised permit.

## Forbidden Files And Actions

- No `app.json` route or tabBar changes.
- No `project.config.json` / appid / DevTools shadow changes.
- No backend API contract changes.
- No unrelated workbench, builds tab, talent simulator, gear detail, SimC, Chickenbro, profile or news page edits.
- No page-private task card, task status, tag chip, queue rail, empty step, result strip, metric cell, combat buff row, evidence row, action button or material geometry.
- No direct page reference to quarantine assets, whole-page target images or pass-named generated glyphs.
- No generated class/spec/hero/item/source icon pretending to be real WoW evidence.
- No DPS, ranking, percentile, tier, S/A grade, comprehensive score, upgrade priority or performance conclusion except a final SimC task result that the existing `simcReport.result` read model says actually ran and is not preview/generated.
- No preview/confirm-only/generated profile DPS display.
- No raw SimC command, raw profile, traceback, `sim_signal_handler`, segmentation fault text, seed, target health, token, openid, user id, database id or raw internal blocker key in visible UI.
- No weakening guest task query boundary, list-to-detail route, preview-DPS suppression, localized failure mapping, final-result gate, active task status semantics or task detail error handling.
- No WeChat DevTools open/close/restart/cache-clear/login/logout actions.

## Data Boundary

Allowed data sources:

- Existing `requestSimulatorTasks()` payload and `simcReportSummary` list read model.
- Existing `requestSimulatorTaskDetail(taskId)` payload and `analysis.simcReport` detail read model.
- Existing guest task query behavior through `simulatorGuestId()` and `guest=1&guestId=...`.
- Existing `taskStatusView()`, task tag, task title, terminal time and localized failed task summary helpers.
- Existing task-detail normalization for `simcReport.result`, scenario, stat snapshot, combat buffs and localized SimC diagnostics.
- Existing analytics events for page view, task list view, task detail view and empty-state navigation.

Required UI mapping:

- `tasks_from_simc`: show that task history can be reached from SimC without losing route context.
- `tasks_from_workbench`: show task history can be reached from workbench or empty state can return to workbench.
- `tasks_loading`: show stable loading shell without fake task rows.
- `tasks_empty`: show empty task state with clear actions to SimC and workbench.
- `tasks_fallback_error`: show request error/fallback without fake zero-history certainty.
- `tasks_list_ready`: show actual tasks from payload with stable cards.
- `task_card_completed`: show completed status, tags, terminal time and no duplicated DPS summary in the list card.
- `task_card_queued`: show queued state as in-progress without terminal completion time.
- `task_card_running`: show running state as in-progress without terminal completion time.
- `task_card_failed`: show localized failure summary and terminal time without raw command output.
- `task_detail_loading`: show stable loading shell for selected task id.
- `task_detail_missing_id`: show missing-id error without backend request loop.
- `task_detail_not_found`: show not-found state and request error without fake result.
- `task_detail_preview_no_dps`: show generated/preview result as not executed and suppress preview DPS.
- `task_detail_final_result`: show final SimC metric only when the result actually ran and is not preview/generated.
- `task_detail_failed_timeout`: show localized timeout summary.
- `task_detail_failed_raw_diagnostic`: localize raw SimC diagnostics and hide raw command/profile strings.
- `task_detail_context`: show scenario, duration, stat snapshot and bounded build context without raw profile data.
- `task_detail_combat_buffs`: show combat-buff rows from structured preparation items, not backend prose.
- `task_detail_guest_read`: keep guest task detail readable through existing client boundary without leaking bearer token.

Forbidden product claims:

- No DPS, damage, ranking, percentile, tier, S/A grade, comprehensive score or upgrade priority unless it is a final, non-preview SimC task result from the existing detail read model.
- No generated preview DPS, confirm-only DPS or generated-profile DPS.
- No fake official, verified, community or source logo.
- No real WoW icon unless it comes from payload, Battle.net/WebSim mapping, repository verified asset or user-provided source.
- No raw internal blocker keys, raw backend payload fields, raw profile, raw command or secret-like values in user text.

## Asset Boundary

Allowed:

- Low-semantic panel, border, texture, rail, divider and decorative material after manifest approval.
- Real class/spec/source/item icons through verified source map and `GameObjectIcon`.
- Text fallback for missing class/spec/source/item icons.
- Status material only through `StatusVisual`.
- Task rail/card material only through `TaskQueueBoard` or `TaskResultReport`.

Forbidden:

- Imagegen class/spec/hero/item/source icons.
- Imagegen task ids, DPS values, rankings, source names, status labels or business conclusions.
- Whole-page target images or contact sheets in production WXML/WXSS.
- Fake time, battery, Wi-Fi, phone frame or WeChat capsule.
- Direct `ui-redesign` or `ui-v2-1-slices` page references outside active permit production manifest entries.

## Route Smoke Scope

Required scenes after implementation:

- `tasks_from_simc`: `/pages/simulator/tasks?from=simc` loads task history with route context.
- `tasks_from_workbench`: `/pages/simulator/tasks?from=workbench` loads task history with route context.
- `tasks_loading`: list loading state is stable.
- `tasks_empty`: empty task history shows SimC and workbench actions.
- `tasks_fallback_error`: list fallback/error state is stable and honest.
- `tasks_list_ready`: completed, queued/running and failed task cards render from payload.
- `task_card_completed`: completed task card shows status, tags and completion time.
- `task_card_running`: running task card shows in-progress state and no completion time.
- `task_card_failed`: failed task card shows localized failure summary.
- `task_open_detail`: tapping a card opens `/pages/simulator/task-detail?id=...`.
- `task_detail_loading`: detail loading state is stable.
- `task_detail_missing_id`: missing task id state is stable.
- `task_detail_not_found`: not-found/error state is stable.
- `task_detail_preview_no_dps`: generated preview hides preview DPS.
- `task_detail_final_result`: completed final SimC result shows metric from `simcReport.result`.
- `task_detail_failed_timeout`: timeout is localized.
- `task_detail_failed_raw_diagnostic`: raw SimC diagnostic is localized and hidden.
- `task_detail_context`: scenario, stat snapshot and bounded context render without raw profile.
- `task_detail_combat_buffs`: combat buff rows render from structured preparation items.
- `task_detail_guest_read`: guest detail read route remains compatible with existing API client boundary.
- `tasks_empty_to_simc`: empty action navigates to `/pages/simulator/simc?from=tasks`.
- `tasks_empty_to_workbench`: empty action navigates to `/pages/builds/workbench?from=tasks`.

Required assertions:

- No horizontal overflow on compact / standard / large.
- No fake host chrome.
- Task list cards, status chips, tag rows, result metric and combat buff rows stay inside measured bounds.
- Long task titles, long localized failures, long class/spec/hero names and missing icons do not resize the rail or break the cards.
- Empty actions keep stable size in disabled/loading states.
- Preview/generated/confirm-only task details do not show DPS.
- Final completed task details may show DPS only from the final SimC report result.
- No raw SimC command, raw profile, seed, traceback, segmentation fault or secret-like value is visible.
- No quarantine asset reference.

## Evidence Required Before Runtime Acceptance

- Browser scene precheck for all task scenes listed above.
- Real WeChat mini-program screenshots after `captureSafe=true`.
- Component crops for `PageFrame`, `WowPanel`, `TaskQueueBoard`, `TaskResultReport`, `StatusVisual`, `ActionButton`, `EvidenceLedger`, `ModuleCard`, `GameObjectIcon`, `MaterialImage` and fixed/list/detail action areas.
- Current / target / implementation comparison.
- Overlay and red-zone output for task list hero, task card, status chip, tag row, empty state, result metric, context rows, stat rows, combat buff rows, error states and bottom safe-area.
- Scorecard that explicitly rejects fake icons, preview DPS, fake result claims, raw SimC diagnostics, card overflow, detail overflow, lost guest read behavior, lost list-to-detail route and page-private material geometry.
- Route smoke report and DevTools action ledger.

## Rollback And Stop Conditions

Stop implementation and return to permit revision if any of these occur:

- The target is still not locked.
- `TaskQueueBoard` or equivalent list owner is not defined before page integration.
- `TaskResultReport` or equivalent detail owner is not defined before page integration.
- A required owner needs page-private WXML/WXSS geometry to look acceptable.
- The page needs new backend fields or fake front-end fields to express task status.
- The UI needs fake DPS, fake ranking, fake status history, fake official icons or generated task facts to look complete.
- Simulator task tests fail or visual changes require weakening guest task read, list-to-detail navigation, preview-DPS suppression, final-result gate, localized failure mapping or raw diagnostic hiding.
- Browser precheck passes but real mini-program screenshot shows task cards, result metric, combat buff rows, tab/safe-area or keyboard overlap.
- DevTools capture is not safe or would require high-disturbance actions.

## Current Status

This draft now has `TaskQueueBoard` / `TaskResultReport` owner skeleton evidence and a clean surface component precheck. It is still only `implementation_permit_draft`: it remains blocked from page integration until target lock is confirmed and this draft is explicitly converted into an active implementation permit.
