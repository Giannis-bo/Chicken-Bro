# WOW UI System Target Lock Decision Request

Status: `target_lock_decision_request`
Created: 2026-07-07

Artifact manifest: `artifacts/ui-system-rebuild/20260707-target-lock-decision-request/manifest.json`

## Purpose

This document turns the target-lock readiness review into a concrete user decision request. It is not `target_locked`, not an active implementation permit, not page integration, and not runtime verification.

The current evidence is ready for a decision, but Codex must not infer that decision from tests, continuation turns, browser precheck, old pass artifacts, or its own confidence.

## Decision Needed

Choose one of these outcomes:

| Option | Meaning | Next Allowed Action |
| --- | --- | --- |
| Confirm recommended target | Lock `A-Cockpit + B-Ledger + C-Captain` as the product and UI direction. | Write `target_locked` decision record, then convert exactly one draft permit to active. |
| Confirm with modifications | Lock the direction with explicit written changes, such as visual density, material strength, first active permit surface, Chickenbro emphasis, or route-smoke scope. | Write the modified `target_locked` decision record, then update the activation packet before any page edit. |
| Reject / revise target | Keep target unlocked and return to design candidates or target proposal revision. | No page implementation; revise candidate or proposal evidence first. |

## Recommended Decision

Recommended lock:

`A-Cockpit + B-Ledger + C-Captain`

Why:

- Candidate A preserves fast-scanning cockpit hierarchy for news, builds and workbench.
- Candidate B keeps source state, blockers, checkedAt, coverage and veteran details visible.
- Candidate C makes Chickenbro, tasks and novice next-action language first-class surfaces.
- This hybrid matches the user's repeated feedback: keep app feeling and material presence, but stop page-level shape patching, fake facts and lost first-screen information.

## Non-Negotiable Constraints

These remain true whichever option is chosen:

- Real WoW class/spec/talent/item/source icons cannot come from imagegen.
- Imagegen may provide only low-semantic material through the asset manifest and component owners.
- Pages may compose owner components, bind data and route events, but may not fix component geometry with page-private classes.
- Chickenbro remains a first-class surface, not a leftover chat shell.
- Bottom tab, safe-area and real WeChat chrome must be preserved; fake time, battery, Wi-Fi, capsule or phone frame remain forbidden.
- No `DPS`, comprehensive score, S/A grade, upgrade priority or fake source claims without evidence rules.
- No `runtime_verified` or `final_accepted` without real WeChat mini-program screenshots, component crops, overlay/red-zone, scorecard, route smoke and DevTools action ledger.

## If Confirmed

If the user confirms the recommended target or provides written modifications, create:

- `docs/design/2026-07-07-wow-ui-system-target-locked-decision.md`
- `artifacts/ui-system-rebuild/20260707-target-locked-decision/manifest.json`

Use [WOW UI System Target-Locked Decision Template](2026-07-07-wow-ui-system-target-locked-decision-template.md) and `node scripts/ui-system-target-lock-decision-preflight.js --require-decision --json` to validate the record before any draft permit becomes active.

Then convert exactly one draft permit to active. The current recommendation remains:

- first active surface: `news_list_detail`
- active permit file: `docs/plans/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit.md`
- active permit artifact: `artifacts/ui-system-rebuild/20260707-news-list-detail-active-permit/manifest.json`

## Confirmation Text That Is Sufficient

Any of these are sufficient:

- `确认 A-Cockpit + B-Ledger + C-Captain 为 target lock`
- `按 readiness review 的推荐方向锁定`
- `锁定，但做这些修改：...`

Ambiguous approval, silence, "继续", passing tests, or a continuation turn is not sufficient.

## Non-Promotion Rule

This document can only prove `target_lock_decision_request`. It cannot prove:

- `target_locked`
- `active_implementation_permit`
- page integration
- runtime verification
- final acceptance
