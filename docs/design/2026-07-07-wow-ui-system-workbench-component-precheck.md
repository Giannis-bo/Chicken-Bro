# Workbench Component Precheck

Status: `surface_component_precheck`
Created: 2026-07-07

This document records the production/browser component precheck for `WorkbenchCockpitSurface`. It is not `target_locked`, not an active implementation permit, not page integration, not route smoke and not runtime verified.

## Linked Control Plane

- [WOW 小程序 UI 系统重建完整 Goal](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Workbench Owner Skeleton Source Precheck](2026-07-07-wow-ui-system-workbench-owner-skeleton-precheck.md)
- [Workbench Permit Draft](../plans/2026-07-07-wow-ui-system-workbench-implementation-permit-draft.md)
- [Implementation Permit Coverage Matrix](2026-07-07-wow-ui-system-implementation-permit-coverage-matrix.md)
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-workbench-component-precheck/manifest.json`
- Contact sheet: `artifacts/ui-system-rebuild/20260707-workbench-component-precheck/component-crop-contact-sheet.png`

## What Was Measured

- Source precheck for `components/workbench-cockpit-surface/*`.
- Fixture HTML rendered with production WXSS class names.
- Compact / standard / large local headless Chrome viewports.
- Six workbench states from the fixture matrix.
- Eight standard-viewport component crops:
  - workbench ready surface;
  - hero identity;
  - blocked verdict;
  - unified status visual;
  - primary action;
  - module band;
  - partial module card;
  - evidence ledger expanded.

## Result

- Status: `surface_component_precheck`
- Failures: `0`
- Warnings: `0`
- Viewport screenshots: `3`
- Component crops: `8`
- Horizontal overflow: `0` on compact / standard / large.
- Forbidden visible text: `0` matches for strong claims, raw profile text or fake host chrome.
- DevTools touched: `false`
- Page integration: `false`

## What This Proves

- The workbench now has a source-level owner skeleton with fixture coverage.
- The owner can render the core workbench states without document horizontal overflow in a browser precheck.
- `StatusVisual` can own the verdict base/glyph as one component in the owner fixture.
- `ActionButton`, `ModuleCard`, `EvidenceLedger`, `GameObjectIcon`, `WowPanel` and `MaterialImage` are the intended foundation dependencies.

## What This Does Not Prove

- It does not prove target lock.
- It does not authorize page WXML/WXSS edits.
- It does not prove the current mini-program page has been fixed.
- It does not prove WeChat runtime behavior, route smoke, overlay/red-zone, scorecard or final acceptance.

This document can only prove `surface_component_precheck`.

## Next Required Evidence

- Rerun this component precheck before any active workbench implementation permit.
- User confirmation or revision of the target lock.
- Convert exactly one draft permit into an active implementation permit before page integration.
- Real mini-program screenshots, crops, overlay, red-zone, scorecard, route smoke and DevTools action ledger after page integration.
