# Gear Detail Component Precheck

Status: `surface_component_precheck`

Surface: `gear_detail`

Owners:

- `GearLoadoutBoard`
- `GearConfigSheet`

This document records browser/component precheck evidence for the gear detail owner components. It uses production WXSS class names in local headless Chrome and does not touch WeChat DevTools.

## Evidence

- Runner: `artifacts/ui-system-rebuild/20260707-gear-detail-component-precheck/run-gear-detail-component-precheck.js`
- Manifest: `artifacts/ui-system-rebuild/20260707-gear-detail-component-precheck/manifest.json`
- Fixture HTML: `artifacts/ui-system-rebuild/20260707-gear-detail-component-precheck/component-fixture.html`
- Viewport screenshots: `artifacts/ui-system-rebuild/20260707-gear-detail-component-precheck/viewport-screenshots/`
- Component crops: `artifacts/ui-system-rebuild/20260707-gear-detail-component-precheck/component-crops/`
- Contact sheet: `artifacts/ui-system-rebuild/20260707-gear-detail-component-precheck/component-crop-contact-sheet.png`

## Required Checks

The runner must record:

- `surface=gear_detail`
- `status=surface_component_precheck`
- `targetLocked=false`
- `activePermit=false`
- `pageIntegration=false`
- `runtimeVerified=false`
- `devtoolsTouched=false`
- `failures=0`
- no document horizontal overflow
- no visible `DPS`, `BiS`, `综合评分`, `S/A 级`, `提升优先级`, ranking, percentile, raw profile, raw SimC, token, openid, system chrome, time, battery or Wi-Fi text
- 3 viewport screenshots: compact, standard and large
- 10 owner crops covering loadout surface, slot grid, missing slot, stat summary, action rail, sheet surface, candidate row, variant track, enhancement group and sheet action rail

## Non-Promotion

This evidence is intentionally below implementation:

- It does not connect `GearLoadoutBoard` or `GearConfigSheet` to `pages/builds/detail`.
- It does not prove real WeChat mini-program runtime behavior.
- It does not prove route smoke, overlay, red-zone, scorecard or final acceptance.
- It cannot convert the `gear_detail` draft permit into an active permit by itself.

Next required evidence:

1. User target lock confirmation or revision.
2. Convert the `gear_detail` draft into a single active implementation permit.
3. Integrate `pages/builds/detail` through `GearLoadoutBoard` and `GearConfigSheet` only.
4. Capture real mini-program screenshots with DevTools action ledger and route smoke.
