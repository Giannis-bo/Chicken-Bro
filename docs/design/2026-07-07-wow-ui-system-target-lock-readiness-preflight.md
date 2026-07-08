# WOW UI System Target-Lock Readiness Preflight

Status: `target_lock_readiness_preflight`

Date: 2026-07-07

This document records the machine-checkable preflight for target-lock readiness. It is not `target_locked`, not an active implementation permit, not page integration, and not runtime verification.

## Purpose

`node scripts/ui-system-target-lock-readiness-preflight.js --require-ready --json` checks whether the current target-lock packet is complete enough to ask the user for a decision.

The passing status is `target_lock_readiness_ready`. It means the proposal, decision brief, candidates, component owner contracts, asset boundary, route smoke plan, permit coverage and browser component baseline are present and internally consistent.

It does not mean:

- target lock has happened;
- any draft permit may become active;
- page WXML/WXSS can be edited;
- browser/component precheck can be promoted to runtime evidence;
- the UI is `runtime_verified` or `final_accepted`.

## Checked Evidence

- Target-lock readiness review.
- Target-lock decision brief.
- Target-lock proposal.
- Phase 3 A/B/C candidate manifest and contact sheet.
- Foundation and surface owner contracts.
- Asset manifest draft, material asset seed, and real WoW object source boundary.
- Material asset seed safety: 7 required material classes, all 10 core surfaces, package budget, no text, no fake chrome, no real WoW object, no page direct use and no production direct use.
- Decision brief safety: recommended target, three decision options, first surface, material seed, production asset manifest gate, real WoW source map gate, page adoption, runtime evidence and non-promotion boundary.
- Route smoke plan with capture-safe DevTools policy.
- Permit coverage matrix for all 10 core surfaces.
- Browser component precheck for compact, standard and large viewports.

## Current Expected Result

The current packet should pass readiness:

```bash
node scripts/ui-system-target-lock-readiness-preflight.js --require-ready --json
```

Expected:

- `status=target_lock_readiness_ready`
- `readyForUserDecision=true`
- `targetLocked=false`
- `activePermit=false`
- `pageIntegration=false`
- `runtimeVerified=false`
- `finalAccepted=false`
- next required evidence: explicit user target-lock confirmation or written modification.

## Fail-Closed Behavior

The preflight exits with code `14` when readiness evidence is incomplete or any manifest accidentally promotes target lock, active permit, page integration, runtime verification or final acceptance.

Examples:

- Missing A/B/C candidate manifest.
- Missing contact sheet.
- Missing owner component coverage.
- Missing decision brief or missing runtime gates in the brief.
- Missing low-semantic material classes.
- Missing or unsafe material asset seed.
- Material seed marked as production manifest or page-direct usable.
- Route smoke plan below required scene coverage.
- Permit coverage missing any core surface.
- Browser precheck has failures or horizontal overflow.
- Any checked manifest sets `targetLocked=true`, `activePermit=true`, `pageIntegration=true`, `runtimeVerified=true`, `finalAccepted=true`, `strictGateEligible=true` or `devtoolsTouched=true`.

## Non-Promotion Boundary

This preflight is a decision-readiness gate only. The next legal step after a pass is still user confirmation or written modification of the target. The real target-locked record remains:

`docs/design/2026-07-07-wow-ui-system-target-locked-decision.md`

That record must be validated by:

```bash
node scripts/ui-system-target-lock-decision-preflight.js --require-decision --json
```

Only after a valid target-locked decision record may exactly one implementation permit be converted from draft to active.
