# WOW UI System Builds Tab Component Precheck

Status: `surface_component_precheck`
Created: 2026-07-07

This document records production/browser component precheck for `BuildsTabSurface`. It is not `target_locked`, not an active implementation permit, not page integration and not runtime verification.

## Evidence

- Fixture HTML rendered with production WXSS class names.
- Compact / standard / large local headless Chrome viewports.
- Eight standard-viewport component crops.
- Old talent, gear, SimC and task entries must remain visible in every fixture.
- No `pages/builds/builds.*` page integration was performed.
- DevTools touched: `false`.

## Result

- Failures: `0`
- Warnings: `0`
- Horizontal overflow: `0`
- Forbidden visible text: `0`
- Component crops: `8`

## Owner Notes

`BuildsTabSurface` owns the current spec console, class/spec/hero switchers, workbench primary entry, workflow module grid and entry evidence. The component keeps the old four entry keys `talents`, `gear`, `simc`, `tasks` visible in all fixtures, while allowing Chickenbro as an additional route.

This document can only prove `surface_component_precheck`. It cannot authorize edits to `pages/builds/builds`, cannot replace real mini-program screenshots, and cannot prove final acceptance.
