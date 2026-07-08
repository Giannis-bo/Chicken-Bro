# WOW UI System Target-Locked Decision Template

Status: `target_locked_template_only`

Date: 2026-07-07

This template defines the required shape of the future target-locked decision record. It is not `target_locked`, not an active implementation permit, not page integration, and not runtime verification.

Do not rename this file into the real decision record automatically. The real decision record may be created only after explicit user confirmation or written modification.

## Future File

- Planned real decision file: `docs/design/2026-07-07-wow-ui-system-target-locked-decision.md`
- Planned real artifact: `artifacts/ui-system-rebuild/20260707-target-locked-decision/manifest.json`
- Required real status: `target_locked`

## Sufficient User Decision Text

Any of these may unlock the real decision record:

- `确认 A-Cockpit + B-Ledger + C-Captain 为 target lock`
- `按 readiness review 的推荐方向锁定`
- `锁定，但做这些修改：...`

These do not unlock it:

- `继续`
- continuation turn
- passing tests
- Codex confidence
- browser/component precheck
- silence or ambiguous approval

## Required Real Decision Sections

The real `target_locked` decision record must include these sections:

- `Status: target_locked`
- `User Decision Source`
- `Confirmed Target`
- `Decision Brief Boundary`
- `First-Class Surfaces`
- `Foundation Owner Rules`
- `Surface Owner Rules`
- `Asset Production And Quarantine Rules`
- `Material Asset Seed Boundary`
- `Real WoW Object Source Rules`
- `Route Smoke Rules`
- `Implementation Permit Rule`
- `Non-Promotion Boundary`
- `Next Allowed Action`

## Required Target

The recommended target name is:

`A-Cockpit + B-Ledger + C-Captain`

If the user modifies the target, the real decision record must quote the modification and explain what changed before any active permit is created.

## Required Decision Brief Boundary

The real decision record must reference:

- `artifacts/ui-system-rebuild/20260707-target-lock-decision-brief/manifest.json`
- expected status: `target_lock_decision_brief`
- expected preflight status: `target_lock_decision_brief_ready`

The brief must remain non-promoting before the real record is written:

- `targetLocked=false`
- `activeImplementationPermit=false`
- `pageIntegration=false`
- `runtimeVerified=false`
- `finalAccepted=false`

The real record must preserve the brief's runtime gates:

- `production_asset_manifest_preflight`
- `real_wow_source_map_preflight`
- `page_adoption_preflight`
- `visual_acceptance_preflight`
- `route_smoke_execution_preflight`
- `devtools_action_ledger_preflight`

## Required Surfaces

The lock must cover all core surfaces from the goal:

- `news_home`
- `news_list_detail`
- `builds_tab`
- `current_spec_workbench`
- `talent_simulator`
- `gear_detail`
- `simc`
- `chickenbro`
- `tasks`
- `profile_templates`

## Required Non-Negotiables

- Real WoW class/spec/talent/item/source icons cannot come from imagegen.
- Imagegen can only provide low-semantic material through the asset manifest and component owners.
- The real decision record must reference the target-lock decision brief and preserve its production asset manifest, real WoW source map, page adoption, visual acceptance, route smoke and DevTools ledger gates.
- The real decision record must reference `artifacts/ui-system-rebuild/20260707-material-asset-seed/manifest.json` with status `material_asset_seed_ready`; the seed is not a production manifest and must remain `pageDirectUseAllowed=false` and `productionUseAllowed=false`.
- Pages compose owner components, bind data and handle routes; pages do not fix component internals with private geometry.
- Chickenbro remains a first-class surface.
- Fake system chrome remains forbidden.
- No unproven DPS, comprehensive score, S/A grade, upgrade priority or fake source claim.
- Runtime verification requires real WeChat mini-program screenshots, component crops, overlay/red-zone, scorecard, route smoke and DevTools action ledger.
- Exactly one draft permit may become active after target lock.

## Preflight

Run this before converting any draft permit to active:

```sh
node scripts/ui-system-target-lock-decision-preflight.js --require-decision --json
```

While the real decision record is absent or incomplete, the command exits non-zero.
