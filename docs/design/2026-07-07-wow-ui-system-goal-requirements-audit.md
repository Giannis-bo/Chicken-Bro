# WOW UI System Goal Requirements Audit

Status: `ui_system_goal_requirements_incomplete`

Date: 2026-07-07

This audit maps the active UI system rebuild goal to current evidence. It is deliberately stricter than the existing implementation gate: the gate answers "may we implement now?", while this audit answers "is the full goal actually complete?".

Current answer: no. The project has strong source evidence for Phase 1/2, component owner direction and first-surface activation readiness, but it still lacks target lock, active permit, permitted page integration, real mini-program runtime screenshots, overlay/red-zone/scorecard, route smoke execution and DevTools action ledger.

## Command

```sh
node scripts/ui-system-goal-requirements-audit.js --require-complete --json
```

Current expected exit code: `7`.

## Summary

- status: `ui_system_goal_requirements_incomplete`
- goalComplete=false
- completionClaimAllowed=false
- runtimeVerifiedAllowed=false
- finalAcceptedAllowed=false
- implementationGateStatus=`ui_system_implementation_gate_blocked`
- implementationAllowed=false

## Requirement Matrix

| Requirement | Current Evidence | Judgment |
| --- | --- | --- |
| Goal reset from pass36/pass37 local repair to UI system rebuild. | [Goal](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md), [Two-Part Goal Sync](../plans/2026-07-07-wow-ui-system-two-part-goal-sync.md), roadmap entries. | Complete as control-plane alignment. |
| Phase 1 inventory of pages, components, assets, screenshots, scorecards and DevTools action state. | [Phase 1 Inventory](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-phase1-inventory.md), [Phase 1/2 Closure Audit](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-phase1-2-closure-audit.md). | Complete at source-evidence level. |
| Phase 2 current problem register and freeze against page-level pixel patching. | Phase 1/2 inventory, closure audit and [Diff Scope Audit](2026-07-07-wow-ui-system-diff-scope-audit.md). | Complete at source-evidence level. |
| Core page WXML/WXSS, app shell and navigation chrome freeze. | [Activation Guard](2026-07-07-wow-ui-system-activation-guard.md), [Implementation Gate](2026-07-07-wow-ui-system-implementation-gate.md), [Core Page Freeze Preflight](2026-07-07-wow-ui-system-core-page-freeze-preflight.md) and diff-scope audit. | Blocked gate active; `node scripts/ui-system-core-page-freeze-preflight.js --require-frozen --summary-json` exits `16` while 44 page/App/navigation/project files remain quarantined and target lock / active permit are absent. |
| Foundation and surface owner system. | Foundation contracts, surface contracts, [Owner Registry Preflight](2026-07-07-wow-ui-system-owner-registry-preflight.md), owner skeletons, browser/component prechecks and [Page Adoption Preflight Template](2026-07-07-wow-ui-system-page-adoption-preflight-template.md). | Owner registry is source-ready: `node scripts/ui-system-owner-registry-preflight.js --require-ready --json` exits `0` with 26 owners across 10 surfaces. This is still not page adoption; current source pages fail `node scripts/ui-system-page-adoption-preflight.js --require-adoption --json` with exit code `12`. |
| Imagegen low-semantic asset boundary. | [Asset Manifest Draft](2026-07-07-wow-ui-system-asset-manifest-draft.md), [Material Asset Seed](2026-07-07-wow-ui-system-material-asset-seed.md), [Production Asset Manifest Template](2026-07-07-wow-ui-system-production-asset-manifest-template.md), `scripts/ui-system-material-asset-seed-preflight.js` and `scripts/ui-system-production-asset-manifest-preflight.js`. | Material seed is ready: `node scripts/ui-system-material-asset-seed-preflight.js --require-seed --json` exits `0` with 9 low-semantic candidate seeds, 7 material classes, 10 surface coverage and package budget `444.84KB / 512KB`. This is still not a production manifest, page integration or runtime evidence. |
| Real WoW object source boundary. | Asset manifest draft, production asset manifest template, [Real WoW Source Map Template](2026-07-07-wow-ui-system-real-wow-source-map-template.md), [Real WoW Source Map Seed](2026-07-07-wow-ui-system-real-wow-source-map-seed.md), target proposal and goal doc. | Source-map seed is ready: `node scripts/ui-system-real-wow-source-map-seed-preflight.js --require-seed --json` exits `0` and covers 10 entity types across 10 surfaces. Runtime source map still missing; `node scripts/ui-system-real-wow-source-map-preflight.js --require-source-map --json` exits `15` until target lock, active permit and integrated runtime fields exist. |
| Chickenbro first-class surface. | Chickenbro owner skeleton, component precheck and permit draft. | Component evidence only; runtime surface not verified. |
| User-confirmed `target_locked` design covering all core surfaces. | Target lock request, [Target Lock Decision Brief](2026-07-07-wow-ui-system-target-lock-decision-brief.md), target-locked decision template and [Target-Lock Readiness Preflight](2026-07-07-wow-ui-system-target-lock-readiness-preflight.md). | Readiness packet and compact decision brief are machine-checked as decision-ready, but the real decision record and explicit user confirmation are still missing. |
| First bounded surface activation readiness. | [First Surface Activation Readiness Preflight](2026-07-07-wow-ui-system-first-surface-activation-readiness-preflight.md), activation packet and news list/detail owner/component evidence. | Source evidence complete: `node scripts/ui-system-first-surface-activation-readiness-preflight.js --require-ready --json` exits `0` for `news_list_detail`, with 79 checks, 0 failures, 12 stable route scene ids and non-promotion fields all false. This is still not target lock, not active permit and not page integration. |
| Exactly one active implementation permit. | News list/detail active permit template and preflight. | Missing active permit. |
| Page integration under permit. | Implementation gate and page adoption preflight. | Blocked; implementation gate now also checks `first_surface_readiness` as a passing precondition, but target lock, active permit and clean page scope are still missing. Post-integration page adoption must pass before runtime evidence can count. |
| Real WeChat mini-program screenshots for all core surfaces, states and viewports. | Route smoke plan plus [Route Smoke Execution Manifest Template](2026-07-07-wow-ui-system-route-smoke-execution-template.md). | Missing runtime evidence; `node scripts/ui-system-route-smoke-execution-preflight.js --require-execution --json` exits `11` until a real execution manifest exists. |
| Component crops, overlay, red-zone and scorecard from runtime implementation. | Goal, route smoke plan, route smoke execution template and [Visual Acceptance Scorecard Template](2026-07-07-wow-ui-system-visual-acceptance-scorecard-template.md). | Missing runtime evidence; `node scripts/ui-system-visual-acceptance-preflight.js --require-scorecard --json` exits `13` until a real runtime scorecard exists. |
| Route smoke execution. | Route smoke plan, route smoke execution template and `scripts/ui-system-route-smoke-execution-preflight.js`. | Missing valid execution manifest, route logs, screenshots, crops, overlays, red-zones and scorecard. |
| DevTools low-disturbance action ledger. | Activation guard, route smoke plan, [DevTools Action Ledger Template](2026-07-07-wow-ui-system-devtools-action-ledger-template.md) and `scripts/ui-system-devtools-action-ledger-preflight.js`. | Missing capture-safe runtime ledger. |
| Non-promotion guard. | Goal, activation guard, implementation gate and closure audit. | Complete as a guard; it does not complete the UI rebuild. |

## Missing Completion Evidence

- `docs/design/2026-07-07-wow-ui-system-target-locked-decision.md`
- explicit user target-lock confirmation or written modification; current `node scripts/ui-system-target-lock-decision-brief-preflight.js --require-ready --json` only proves `target_lock_decision_brief_ready`, and current `node scripts/ui-system-target-lock-readiness-preflight.js --require-ready --json` only proves `target_lock_readiness_ready`, not `target_locked`.
- `docs/plans/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit.md`
- first-surface activation readiness exists for `news_list_detail`, but it only proves `first_surface_activation_readiness_ready`; current `node scripts/ui-system-first-surface-activation-readiness-preflight.js --require-ready --json` exits `0` without creating `target_locked`, active permit or page integration.
- passing core page freeze preflight; current `node scripts/ui-system-core-page-freeze-preflight.js --require-frozen --summary-json` exits `16` because 44 page/App/navigation/project files are quarantined without target lock and active permit.
- owner registry source-ready preflight exists, but page adoption and runtime component crops are still missing; current `node scripts/ui-system-owner-registry-preflight.js --require-ready --json` only proves source owner coverage.
- clean page/app/navigation diff scope before implementation
- passing page adoption preflight after permitted page integration; current `node scripts/ui-system-page-adoption-preflight.js --require-adoption --json` exits `12` because the real pages still contain page-private geometry and direct generated material references.
- material asset seed exists, but production asset manifest with exact post-recut files, dimensions, owners, fit strategy and package budget is still missing; current `node scripts/ui-system-material-asset-seed-preflight.js --require-seed --json` exits `0`, while `node scripts/ui-system-production-asset-manifest-preflight.js --require-production-manifest --json` exits `10` because the real runtime production manifest is intentionally absent.
- real WoW source-map seed exists, but runtime source map for class, spec, hero, talent, spell, item, source, dungeon, raid and affix imagery is still missing; current `node scripts/ui-system-real-wow-source-map-seed-preflight.js --require-seed --json` exits `0`, while `node scripts/ui-system-real-wow-source-map-preflight.js --require-source-map --json` exits `15` because the real runtime source map is intentionally absent.
- real mini-program screenshots for `news_home`, `news_list_detail`, `builds_tab`, `current_spec_workbench`, `talent_simulator`, `gear_detail`, `simc`, `chickenbro`, `tasks` and `profile_templates`
- compact / standard / large viewport evidence
- target/current/implementation comparison set
- component crop set
- overlay metrics
- red-zone report
- scorecard for each core surface; current `node scripts/ui-system-visual-acceptance-preflight.js --require-scorecard --json` exits `13` because the real runtime visual acceptance scorecard is intentionally absent.
- route smoke execution manifest; current `node scripts/ui-system-route-smoke-execution-preflight.js --require-execution --json` exits `11` because the real runtime execution manifest is intentionally absent.
- DevTools action ledger with `captureSafe=true`; current `node scripts/ui-system-devtools-action-ledger-preflight.js --require-ledger --json` exits `9` because the real runtime ledger is intentionally absent.

## Next Valid Movement

Continue source-level work only, or obtain explicit target-lock confirmation/written modification. After target lock exists, create exactly one active permit, then integrate one surface and collect runtime evidence. Until then, any `runtime_verified`, `final_accepted` or completion claim is false.

## Non-Promotion Rule

This audit can only prove `ui_system_goal_requirements_incomplete`. It cannot prove `target_locked`, `active_implementation_permit`, `page_integration`, `runtime_verified`, `final_accepted` or visual acceptance.
