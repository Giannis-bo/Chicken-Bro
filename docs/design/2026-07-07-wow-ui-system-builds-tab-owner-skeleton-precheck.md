# WOW UI System Builds Tab Owner Skeleton Source Precheck

Status: `owner_skeleton_source_precheck`
Created: 2026-07-07

This document records the source-level owner skeleton for `builds_tab`. It is not `target_locked`, not an active implementation permit, not page integration and not runtime verification.

## Scope

Added `components/builds-tab-surface/*` as the owner skeleton for the职业专精 tab.

No `pages/builds/builds.*` page integration was performed. The existing page still owns old page-private geometry and direct generated material references until a future active permit allows replacement.

## Owner Responsibilities

- Owns current spec console geometry, including real icon slot, class/spec/hero text, readiness state and overview chips.
- Owns compact class/spec/hero switcher rows and long-label behavior.
- Owns the promoted current spec workbench entry while keeping it below the owner boundary.
- Owns the workflow module grid for old talent, gear, SimC and task entrances, with Chickenbro allowed as an extra entry.
- Uses `StatusVisual` for readiness and workbench state.
- Uses `ActionButton` for workbench and route actions.
- Uses `ModuleCard` for talents, gear, SimC, tasks and Chickenbro workflow entries.
- Uses `EvidenceLedger` for entry evidence, icon source, route preservation and fallback state.
- Uses `GameObjectIcon` for real class/spec icon mapping or text fallback.
- Uses `MaterialImage` only for low-semantic material slots.

## Fixture Matrix

The fixture matrix is in `artifacts/ui-system-rebuild/20260707-builds-tab-owner-skeleton/fixtures.json`.

Fixtures:

- `builds_tab_ready`
- `builds_tab_loading`
- `builds_tab_source_reference`
- `builds_tab_blocked_workbench`
- `builds_tab_long_labels`
- `builds_tab_missing_icons`

The matrix explicitly preserves the old four entry keys: `talents`, `gear`, `simc`, `tasks`.

## Current Source Finding Reconfirmed

The current page is still diagnostic-only evidence:

- `pages/builds/builds.wxml` composes `builds-spec-console`, `workbench-entry` and `query-section` directly with page-private classes.
- `pages/builds/builds.wxss` owns shell gutters, hero grid, medallion geometry, workbench entry frame, workflow rail, quick action card geometry and material fit.
- Direct page references to generated `ui-v2-1-slices` remain in the current page until an active permit replaces them.

## Non-Promotion Rule

This document can only prove `owner_skeleton_source_precheck`.

It cannot prove:

- `target_locked`
- `active_implementation_permit`
- page integration
- route smoke
- real WeChat mini-program screenshot
- runtime verification
- final acceptance

## Next Evidence

Production/browser component precheck for `BuildsTabSurface` now exists as a separate evidence layer. After that, the surface still needs target lock, active permit conversion, page integration under permit, real mini-program screenshots, overlay/red-zone/scorecard and route smoke.
