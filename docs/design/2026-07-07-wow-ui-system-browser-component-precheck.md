# WOW 小程序 UI 系统 Browser Component Precheck

Status: `browser_component_precheck`

This document records the first browser rect measurement for the WOW mini-program foundation components. It is not `runtime_verified`, not `target_locked`, and not an implementation permit.

## Linked Control Plane

- [WOW 小程序 UI 系统重建完整 Goal](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Foundation Component Contracts](2026-07-07-wow-ui-system-foundation-component-contracts.md)
- [Production Component Precheck](2026-07-07-wow-ui-system-production-component-precheck.md)
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-browser-component-precheck/manifest.json`
- Contact sheet: `artifacts/ui-system-rebuild/20260707-browser-component-precheck/component-crop-contact-sheet.png`

## What This Proves

- The production component fixture opens in local headless Chrome.
- Compact, standard and large viewport rect measurements are recorded.
- All 12 foundation owner roots are found and measurable.
- Standard viewport component crops are produced for all 12 owners.
- The `ChatShell` crop reflects player-facing evidence copy rather than raw backend field names.
- The run does not touch WeChat DevTools.

## What This Does Not Prove

- It does not prove WeChat mini-program rendering.
- It does not prove page integration.
- It does not verify final target visual fidelity.
- It does not authorize page WXML/WXSS changes.

## Next Required Evidence

- User confirmation or modification of the target lock proposal.
- A one-surface implementation permit before any core page rebuild.
- Real mini-program screenshots only after `captureSafe=true`.
- Component overlays, red-zone comparison and route smoke after page integration.
