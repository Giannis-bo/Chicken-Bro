# TalentTreeCanvas Owner Skeleton Source Precheck

Status: `owner_skeleton_source_precheck`
Created: 2026-07-07

## Scope

This source precheck adds `TalentTreeCanvas` as the surface owner for `talent_simulator`. It does not activate the talent simulator implementation permit and does not authorize edits to `pages/builds/talent-simulator.*`.

## Design Read

Reading this as: native WeChat mini-program product UI for WoW players, with a high-density Azeroth evidence-cockpit language, leaning toward existing WOW foundation owners rather than a generic dashboard or landing-page system. Dial reading for this owner: `DESIGN_VARIANCE=5`, `MOTION_INTENSITY=2`, `VISUAL_DENSITY=9`.

## Added Owner

- `components/talent-tree-canvas/talent-tree-canvas.js`
- `components/talent-tree-canvas/talent-tree-canvas.json`
- `components/talent-tree-canvas/talent-tree-canvas.wxml`
- `components/talent-tree-canvas/talent-tree-canvas.wxss`

`TalentTreeCanvas` owns tree viewport dimensions, node positions, link geometry, passive/active/choice shape semantics, choice affordance, rank badge placement, tree action rail and talent evidence ledger placement.

## Foundation Dependencies

- `WowPanel` for the surface shell.
- `GameObjectIcon` for real talent icons and text fallback.
- `StatusVisual` for loading, blocked, partial, source reference and save readiness states.
- `ActionButton` for save, import and reset actions.
- `EvidenceLedger` for authority, readiness and save blocker rows.
- `MaterialImage` only for low-semantic tree material.

## Fixture Matrix

Fixture source: `artifacts/ui-system-rebuild/20260707-talent-tree-canvas-owner-skeleton/fixtures.json`

Covered fixtures:

- `talent_tree_loading`
- `talent_tree_ready`
- `talent_tree_missing_icon`
- `talent_tree_locked_path`
- `talent_tree_choice_node`
- `talent_save_blocked`
- `talent_save_ready`

## Non-Promotion

This evidence is not:

- `target_locked`
- `active_implementation_permit`
- page integration
- component/browser precheck
- real WeChat mini-program runtime verification
- route smoke
- final acceptance

## Boundaries

- No `pages/builds/talent-simulator.*` page file was edited.
- No DevTools action was performed.
- No generated talent icon was introduced.
- No DPS, comprehensive score, S/A grade, ranking or upgrade-priority claim was added.
- No raw backend blocker, token, openid, user id or database id is exposed by the owner.

## Next Evidence

Run a surface component precheck for `TalentTreeCanvas`, produce browser viewport screenshots, component crops and a contact sheet, then update the permit coverage matrix without promoting the page to runtime verified.
