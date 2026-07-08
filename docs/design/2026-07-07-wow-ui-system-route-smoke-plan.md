# WOW 小程序 UI 系统 Route Smoke And Runtime Verification Plan

Status: `route_smoke_plan_draft`

This document defines the route smoke and runtime verification ladder for the WOW mini-program UI system rebuild. It is not `runtime_verified`, not `final_accepted`, and not permission to touch WeChat Developer Tools with high-disturbance actions.

## Linked Control Plane

- [WOW 小程序 UI 系统重建完整 Goal](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Phase 1/2 Inventory](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-phase1-inventory.md)
- [Target Lock Proposal](2026-07-07-wow-ui-system-target-lock-proposal.md)
- [Foundation Component Contracts](2026-07-07-wow-ui-system-foundation-component-contracts.md)
- [Asset Manifest Draft](2026-07-07-wow-ui-system-asset-manifest-draft.md)
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-route-smoke-plan/manifest.json`

## Route Inventory

Current registered pages from `app.json`:

| Surface | Route | Entry Type |
| --- | --- | --- |
| News home | `/pages/news/news` | tab |
| News list | `/pages/news/list` | stack |
| News detail | `/pages/news/detail` | stack |
| Builds tab | `/pages/builds/builds` | tab |
| Current spec workbench | `/pages/builds/workbench` | stack |
| Builds intel | `/pages/builds/intel` | stack |
| Talent simulator | `/pages/builds/talent-simulator` | stack |
| Gear/detail | `/pages/builds/detail` | stack |
| Smart analysis tab | `/pages/simulator/simulator` | tab |
| SimC | `/pages/simulator/simc` | stack |
| Chickenbro | `/pages/simulator/chickenbro` | stack |
| Tasks | `/pages/simulator/tasks` | stack |
| Task detail | `/pages/simulator/task-detail` | stack |
| Profile/templates | `/pages/profile/profile` | tab |

`pages/pve/*` exists in the repository but is not registered in `app.json`; it is excluded from this UI system runtime acceptance until product scope changes.

## Verification Ladder

| Layer | Status It Can Prove | What It Checks | What It Cannot Prove |
| --- | --- | --- | --- |
| `source_route_inventory` | route plan exists | `app.json`, route handlers, registered pages. | Layout, runtime, screenshots. |
| `browser_component_precheck` | component precheck candidate | Component owners, fixture rects, overflow, fake chrome, forbidden text. | WeChat runtime, tabBar, native nav, real device rendering. |
| `browser_scene_matrix` | scene matrix precheck candidate | Core scenes across compact/standard/large browser harness. | Real mini-program screenshot acceptance. |
| `miniprogram_runtime_capture` | runtime screenshot evidence | Real WeChat page render, tab navigation, stack navigation, screenshots. | Final visual pass without overlay/scorecard. |
| `comparison_and_scorecard` | visual acceptance evidence | Current/target/implementation comparison, component crops, overlay, red-zone, route manifest. | Product target lock if user has not confirmed it. |

No layer may promote itself above its evidence. Browser evidence cannot be called runtime verified.

## DevTools Low-Disturbance Policy

Default forbidden actions:

- `cli open`
- `cli close`
- forced restart
- clear cache
- switch project
- switch appid
- delete or replace user data directory
- login/logout operations
- screenshot/navigation before `captureSafe=true`

Allowed actions only after explicit runner gate:

- Read current DevTools process and port state.
- Read-only health probe.
- Browser/component harness generation outside DevTools.
- Real screenshot capture only when `captureSafe=true`.
- Route navigation only inside the capture runner that writes an action ledger.

Every runtime run must write an action ledger with:

- `captureSafe`
- DevTools app path and port
- appid state
- forbidden action check
- scene list
- failed scenes
- screenshot path list
- route action list
- login-state incident note if any

## Core Scene Matrix

| ID | Surface | Route | Required State | Primary Assertions |
| --- | --- | --- | --- | --- |
| `news_home_top` | News home | `/pages/news/news` | loaded or fallback loaded | tabBar visible, no fake chrome, command header, channel dock, ranked feed preview. |
| `news_home_scrolled` | News home | `/pages/news/news` | scrolled | ranked feed rows visible, 5 priority rows, no all-black list, source state visible. |
| `news_channel_official` | News list | `/pages/news/list?type=channel&value=official` | list | channel filter title, list rows, open detail affordance. |
| `news_detail_first` | News detail | `/pages/news/detail?id=<articleId>` | detail | title, original/source/date, content, source proof. |
| `builds_tab_top` | Builds tab | `/pages/builds/builds` | loaded | current spec console, workbench primary entry, old entries reachable. |
| `builds_spec_switch` | Builds tab | `/pages/builds/builds` | changed spec | class/spec/hero controls update without layout shift. |
| `workbench_ready` | Workbench | `/pages/builds/workbench?spec=<spec>` | `ready_to_simulate` fixture or real state | readiness verdict, main action to SimC, four modules, evidence summary. |
| `workbench_blocked_gear` | Workbench | `/pages/builds/workbench?spec=<spec>` | `blocked` gear gap | blocker and gear action, no DPS/score/tier, unified `StatusVisual`. |
| `workbench_partial_talent` | Workbench | `/pages/builds/workbench?spec=<spec>` | `partial` talent coverage | partial state, evidence expansion path, no strong conclusion. |
| `workbench_stale` | Workbench | `/pages/builds/workbench?spec=<spec>` | `stale` | freshness text and refresh/source action. |
| `workbench_evidence_expanded` | Workbench | `/pages/builds/workbench?spec=<spec>` | expanded | coverage, checkedAt, catalogStatus, statSnapshot, blockers. |
| `talent_simulator_load` | Talent | `/pages/builds/talent-simulator?spec=<spec>` | loaded | real talent icons, tree visible, save/import/apply actions. |
| `talent_simulator_missing` | Talent | `/pages/builds/talent-simulator?spec=<spec>` | source_reference/partial | fallback text and source state, no fake icon. |
| `gear_detail_load` | Gear | `/pages/builds/detail?query=gear&spec=<spec>` | loaded | 16 slots or blocker, real item icons, candidate detail path. |
| `gear_missing_slot` | Gear | `/pages/builds/detail?query=gear&spec=<spec>` | missing slot | blocked save, slot action, no fake SimC-ready claim. |
| `simc_from_workbench` | SimC | `/pages/simulator/simc?from=workbench&spec=<spec>` | handoff | context strip, template selection, submit gate. |
| `simc_blocked_templates` | SimC | `/pages/simulator/simc?from=workbench&spec=<spec>` | missing templates | blocked state and next action. |
| `smart_analysis_tab` | Smart analysis | `/pages/simulator/simulator` | tab | Chickenbro-first entry, no dead card grid. |
| `chickenbro_empty` | Chickenbro | `/pages/simulator/chickenbro` | empty | ChatShell empty state, input safe-area. |
| `chickenbro_workbench_context` | Chickenbro | `/pages/simulator/chickenbro?from=workbench&spec=<spec>` | context | bounded context summary, evidence chips, no raw backend fields. |
| `chickenbro_generating` | Chickenbro | `/pages/simulator/chickenbro` | submitting | generating row, input disabled/loading. |
| `chickenbro_done` | Chickenbro | `/pages/simulator/chickenbro` | completed | answer, evidence rows, next questions. |
| `chickenbro_failed` | Chickenbro | `/pages/simulator/chickenbro` | failed/fallback | recoverable failure, fallback clarity. |
| `tasks_list` | Tasks | `/pages/simulator/tasks?from=builds` | list or empty | task rows/empty state, detail navigation. |
| `task_detail` | Task detail | `/pages/simulator/task-detail?id=<taskId>` | detail or missing | status, report/evidence or missing task state. |
| `profile_guest` | Profile | `/pages/profile/profile` | guest/formal boundary | login boundary, local templates, remote sync status. |
| `profile_templates` | Profile | `/pages/profile/profile` | templates | local/remote template rows, delete/jump actions. |

## Route Smoke Assertions

Every scene must assert:

- no fake time, battery, Wi-Fi, phone frame or WeChat capsule;
- no horizontal overflow on compact/standard/large;
- no visible `DPS`, `综合评分`, `S 级`, `A级`, `提升优先级` without the required evidence policy;
- no production reference to quarantine assets;
- bottom tab / safe-area is not covered by content;
- long Chinese and long English text do not escape their owner slot;
- image material is clipped by `MaterialImage`, real object icon by `GameObjectIcon`, state by `StatusVisual`.

## Required Artifacts Per Runtime Run

- `manifest.json`
- `devtools-action-ledger.json`
- `screenshots/*.png`
- `component-crops/*.png`
- `comparisons/*.png`
- `overlays/*.png`
- `red-zones/*.png`
- `scorecard.json`
- `route-smoke-report.md`

## Status Boundary

This plan is `route_smoke_plan_draft`. It does not prove any scene is runtime verified. Runtime verification starts only when the target is locked, implementation permit exists, component precheck passes, DevTools `captureSafe=true`, and screenshots are captured from the real mini-program.
