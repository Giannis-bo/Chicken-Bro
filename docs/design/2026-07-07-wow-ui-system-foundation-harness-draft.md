# WOW 小程序 UI 系统 Foundation Harness Draft

Status: `component_harness_draft`

This document records the first UI-system foundation harness for the WOW mini-program rebuild. It is not `component_precheck`, not `runtime_verified`, and not an implementation permit.

## Linked Control Plane

- [WOW 小程序 UI 系统重建完整 Goal](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Foundation Component Contracts](2026-07-07-wow-ui-system-foundation-component-contracts.md)
- [Asset Manifest Draft](2026-07-07-wow-ui-system-asset-manifest-draft.md)
- [Route Smoke And Runtime Verification Plan](2026-07-07-wow-ui-system-route-smoke-plan.md)
- [Production Component Precheck](2026-07-07-wow-ui-system-production-component-precheck.md)
- [Browser Component Precheck](2026-07-07-wow-ui-system-browser-component-precheck.md)
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-foundation-harness/manifest.json`
- Contact sheet: `artifacts/ui-system-rebuild/20260707-foundation-harness/foundation-harness-contact-sheet.png`

## Purpose

The old pass37 harness is useful diagnostic evidence but cannot be the new system gate because it covered only nine legacy owners and still used `StatusBadge` instead of the target `StatusVisual`.

This harness draft covers all target foundation owners and the current repository now has component directories for all 12 target owners:

- `AppShell`
- `PageFrame`
- `WowPanel`
- `MaterialImage`
- `GameObjectIcon`
- `StatusVisual`
- `ActionButton`
- `ModuleCard`
- `ChannelDock`
- `RankedFeed`
- `EvidenceLedger`
- `ChatShell`

## Current Code Reality

| Target Owner | Current Code Status | Meaning |
| --- | --- | --- |
| `AppShell` | `existing_component_dir` | Component directory exists; still needs production-code harness precheck before page integration. |
| `PageFrame` | `existing_component_dir` | Component directory exists; still needs UI-system harness precheck. |
| `WowPanel` | `existing_component_dir` | Component directory exists; still needs UI-system harness precheck. |
| `MaterialImage` | `existing_component_dir` | Low-semantic material owner exists; still needs fit and clipping measurement. |
| `GameObjectIcon` | `existing_component_dir` | Component directory exists; must own real icon fit/fallback. |
| `StatusVisual` | `existing_component_dir_legacy_status_badge_exists` | Target owner now exists; legacy `status-badge` also exists but cannot be promoted automatically. |
| `ActionButton` | `existing_component_dir` | Component directory exists; must own button geometry. |
| `ModuleCard` | `existing_component_dir` | Component directory exists; must own card sizing and hierarchy. |
| `ChannelDock` | `existing_component_dir` | Component directory exists; must own channel dock geometry. |
| `RankedFeed` | `existing_component_dir` | Component directory exists; must own five-row news hierarchy. |
| `EvidenceLedger` | `existing_component_dir` | Component directory exists; must own evidence rows and expansion. |
| `ChatShell` | `existing_component_dir` | Chickenbro shell owner exists; still needs production-code fixture measurement. |

## Evidence Produced

- Static contact sheet with all 12 owners.
- 12 component crop images.
- Manifest listing all target owner directories and legacy alias risk.
- Checks for target owner coverage, state vocabulary coverage, missing owner recording, legacy status badge boundary and no DevTools action.

## Boundaries

This harness is intentionally weaker than component precheck:

- It renders a static Pillow board, not real WXML/WXSS.
- It does not measure production component DOM rects.
- It does not prove compact/standard/large viewport behavior.
- It does not prove route smoke or mini-program runtime rendering.
- It does not authorize page WXML/WXSS edits.

## Next Required Evidence

- Build a real component harness using production component code.
- Run fixture execution for compact, standard and large viewports.
- Add layout containment measurements for material fit, status center point, button height, text overflow and chat input safe-area.
- Measure `StatusVisual` and `ChatShell` with production component fixtures before page integration.
- Browser component precheck is now available; next evidence is a one-surface implementation permit after target lock.
