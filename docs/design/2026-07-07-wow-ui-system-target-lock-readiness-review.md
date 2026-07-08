# WOW UI System Target Lock Readiness Review

Status: `target_lock_readiness_review`
Created: 2026-07-07

This document reviews whether the current UI system rebuild evidence is ready for a user target-lock decision. It is not `target_locked`, not an active implementation permit, not page integration, and not real WeChat mini-program runtime verification.

## Design Read

Reading this as native WeChat mini-program product UI for WoW players, with a dense dark Azeroth evidence-cockpit language. This is not a marketing page or portfolio redesign. The useful taste-skill calibration is:

- `DESIGN_VARIANCE=6`: enough asymmetry and material hierarchy to avoid a plain list app, but not freeform layout chaos.
- `MOTION_INTENSITY=3`: mostly static native app UI, with pressed/loading/state transitions only.
- `VISUAL_DENSITY=9`: cockpit density, compact scanning and evidence-first layout.

## Linked Evidence

- [WOW 小程序 UI 系统重建完整 Goal](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Target Lock Proposal](2026-07-07-wow-ui-system-target-lock-proposal.md)
- [Phase 3 Design Candidates](2026-07-07-wow-ui-system-phase3-design-candidates.md)
- [Foundation Component Contracts](2026-07-07-wow-ui-system-foundation-component-contracts.md)
- [Surface Owner Contracts](2026-07-07-wow-ui-system-surface-owner-contracts.md)
- [Asset Manifest Draft](2026-07-07-wow-ui-system-asset-manifest-draft.md)
- [Route Smoke And Runtime Verification Plan](2026-07-07-wow-ui-system-route-smoke-plan.md)
- [Implementation Permit Coverage Matrix](2026-07-07-wow-ui-system-implementation-permit-coverage-matrix.md)
- [Production Component Precheck](2026-07-07-wow-ui-system-production-component-precheck.md)
- [Browser Component Precheck](2026-07-07-wow-ui-system-browser-component-precheck.md)
- [News List Detail Component Precheck](2026-07-07-wow-ui-system-news-list-detail-component-precheck.md)
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-target-lock-readiness-review/manifest.json`

## Decision Readiness

Recommended target-lock decision:

`A-Cockpit + B-Ledger + C-Captain`

Meaning:

- use Candidate A as the app shell and fast-scan first-screen structure;
- use Candidate B for evidence rows, source freshness, coverage, blockers and veteran detail;
- use Candidate C for Chickenbro, task flow, context handoff and novice next-action language.

Technical readiness for a user decision is now `ready_for_user_decision`: the proposal has enough documented structure to ask the user to confirm, reject, or revise the target direction. The project is not implementation-ready until that decision is explicitly recorded.

## Target Lock Checklist Review

| Checklist Item | Current Evidence | Readiness |
| --- | --- | --- |
| User confirmation of the hybrid or written modification | Missing external decision | `missing_user_decision` |
| Target visual set for news, builds, workbench and Chickenbro | Phase 3 target candidate contact sheet covers `news`, `builds`, `workbench`, `chickenbro` | `ready_for_decision` |
| Surface notes for talent, gear, SimC, tasks and profile | Target Lock Proposal includes all five surfaces | `ready_for_decision` |
| Component decomposition accepted for all foundation owners | Foundation and Surface Owner Contracts exist | `needs_user_acceptance` |
| Asset manifest draft accepted or revised | Asset Manifest Draft exists with production, quarantine and source-map boundaries | `needs_user_acceptance` |
| Route smoke checklist accepted or revised | Route Smoke Plan exists and covers all registered core runtime surfaces | `needs_user_acceptance` |
| Implementation permit coverage | Coverage matrix shows all core runtime surfaces have draft permits | `ready_for_decision` |
| Component precheck baseline | Foundation production/browser precheck exists; `news_list_detail` has surface component precheck | `partial_component_precheck` |

## What Can Be Locked

If the user confirms the direction without modification, the lock should be written as:

- Status: `target_locked`
- Target name: `A-Cockpit + B-Ledger + C-Captain`
- Product stance: dense evidence cockpit, real WoW objects, low-semantic generated material only, no fake strong claims.
- First-class surfaces: news home/list/detail, builds tab, current spec workbench, talent, gear, SimC, Chickenbro, tasks, profile/templates.
- Implementation rule: exactly one surface may be converted from draft to active permit at a time.

## What Cannot Be Locked Yet

This review does not authorize:

- page WXML/WXSS edits;
- converting any draft permit to active without explicit target lock;
- production use of reference-only or quarantine imagegen assets;
- claiming runtime verification from browser screenshots or component crops;
- marking any surface as `final_accepted`;
- skipping real WeChat mini-program screenshots, route smoke, overlay, red-zone or DevTools action ledger.

## Recommended First Active Permit After Target Lock

The safest first active permit candidate is `news_list_detail`.

Reason:

- it has a dedicated implementation permit draft;
- it has `ArticleListBoard` and `ArticleReader` owner skeletons;
- it has a fixture matrix;
- it has a surface-level production/browser component precheck with 3 viewport screenshots, 7 component crops, failures `0`, warnings `0`, horizontal overflow `0`;
- it is a bounded reading flow with strict source translation and fallback rules.

The first active permit should still stop before runtime acceptance until real WeChat mini-program screenshots, route smoke, overlay/red-zone comparison and DevTools action ledger exist.

## Non-Promotion Rule

This document can only prove `target_lock_readiness_review`. It cannot prove:

- `target_locked`;
- `active_implementation_permit`;
- `page_integration`;
- `runtime_verified`;
- `final_accepted`.
