# Workbench Owner Skeleton Source Precheck

Status: `owner_skeleton_source_precheck`
Created: 2026-07-07

This document records the first source-level owner skeleton for the `current_spec_workbench` surface. It is not `target_locked`, not `component_precheck`, not an active implementation permit, not page integration and not runtime verified.

## Linked Control Plane

- [WOW 小程序 UI 系统重建完整 Goal](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Workbench Permit Draft](../plans/2026-07-07-wow-ui-system-workbench-implementation-permit-draft.md)
- [Surface Owner Contracts](2026-07-07-wow-ui-system-surface-owner-contracts.md)
- [Workbench Component Precheck](2026-07-07-wow-ui-system-workbench-component-precheck.md)
- [Implementation Permit Coverage Matrix](2026-07-07-wow-ui-system-implementation-permit-coverage-matrix.md)
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-workbench-owner-skeleton/manifest.json`
- Fixture matrix: `artifacts/ui-system-rebuild/20260707-workbench-owner-skeleton/fixtures.json`

## What Changed

- Added `components/workbench-cockpit-surface/*`.
- Added a `current_spec_workbench` fixture matrix for ready, blocked gear, partial talent, stale, source-reference and evidence-expanded states.
- No `pages/builds/workbench.*` or `pages/builds/builds.*` page integration was performed.
- No route registration, tabBar, appid, DevTools or backend contract changes were performed.

## Design Read

Reading this as: native WeChat mini-program product UI for WoW players, with a dense evidence cockpit language and a workbench that answers whether the current spec can be simulated, why and where to go next.

Dial settings:

- `DESIGN_VARIANCE: 6`
- `MOTION_INTENSITY: 2`
- `VISUAL_DENSITY: 9`

## Owner Responsibilities Now In Source

### WorkbenchCockpitSurface

- Owns workbench route-level composition below the page frame.
- Owns current spec identity, scenario strip, readiness verdict, blocker rows, primary action, four-module status band and evidence ledger placement.
- Uses `StatusVisual` for the verdict state so the state base, glyph, center point and transparent boundary are not split.
- Uses `ActionButton` for primary and blocker actions so button height and text containment are component-owned.
- Uses `ModuleCard` for talents, gear, SimC and Chickenbro status cards.
- Uses `EvidenceLedger` for coverage, checkedAt, catalogStatus, statSnapshot, template count and blockers.
- Uses `GameObjectIcon` for real class/spec icons and text fallback when no verified object icon exists.
- Uses `MaterialImage` and `WowPanel` only for low-semantic material and panel shells.

## Current Source Findings Still Unfixed

These findings remain in the current routes until a future active implementation permit:

- `pages/builds/workbench.wxml` still composes hero, verdict slab, module band and evidence rows with page-private classes.
- `pages/builds/workbench.wxss` still owns panel gutters, button geometry, module geometry, evidence-row tracks and state tone classes.
- `pages/builds/workbench.wxml` still references generated material directly through page WXML.
- `pages/builds/builds.wxml` still owns the workbench entry panel and quick-entry geometry locally.

This skeleton does not patch those routes. It gives the future active permit a component owner that can replace them without page-private geometry.

## Fixture Coverage

- `workbench_ready`
- `workbench_blocked_gear`
- `workbench_partial_talent`
- `workbench_stale`
- `workbench_source_reference`
- `workbench_evidence_expanded`

## Protected Boundaries

- No visible `DPS`, `综合评分`, `S 级`, `A级`, `提升优先级`, ranking or percentile claims.
- No fake official source, fake verified icon or fake WoW class/spec/talent/item icon.
- No raw SimC profile, raw log payload, token, openid, user id or database id.
- No fake phone chrome, time, battery, Wi-Fi or WeChat capsule.
- No page-private panel, status, action, module, evidence row or material geometry.

## Next Required Evidence

- Production/browser component precheck for `WorkbenchCockpitSurface` now exists; rerun it before activation.
- User confirmation or revision of target lock.
- Explicit conversion of the `current_spec_workbench` permit draft into an active implementation permit before page integration.
- Page integration that replaces current route shells with owner components only.
- Real mini-program screenshots after `captureSafe=true`.
- Route smoke manifest and DevTools action ledger.

## Non-Promotion Rule

This document can only prove `owner_skeleton_source_precheck`. It cannot prove:

- `target_locked`;
- `active_implementation_permit`;
- `page_integration`;
- `runtime_verified`;
- `final_accepted`.
