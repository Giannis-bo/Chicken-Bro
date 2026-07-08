# Gear Detail Owner Skeleton Source Precheck

Status: `owner_skeleton_source_precheck`

Surface: `gear_detail`

This document records source-level owner evidence for the gear detail / gear simulator surface. It does not authorize page WXML/WXSS edits and does not promote the surface to `target_locked`, active implementation permit or runtime verified.

## Owner Components

| Owner | Responsibility |
| --- | --- |
| `GearLoadoutBoard` | Owns 16-slot board geometry, slot card dimensions, icon sockets, readiness rows, stat summary rows, selected/missing/source-reference states, save/import/reset action rail and evidence rows. |
| `GearConfigSheet` | Owns source filters, candidate rows, item icon/title/source/status alignment, variant tracks, crafted stat chips, socket/enchant/embellishment groups, community import rows, blockers and fixed apply action geometry. |

## Source Evidence

- `components/gear-loadout-board/gear-loadout-board.json`
- `components/gear-loadout-board/gear-loadout-board.js`
- `components/gear-loadout-board/gear-loadout-board.wxml`
- `components/gear-loadout-board/gear-loadout-board.wxss`
- `components/gear-config-sheet/gear-config-sheet.json`
- `components/gear-config-sheet/gear-config-sheet.js`
- `components/gear-config-sheet/gear-config-sheet.wxml`
- `components/gear-config-sheet/gear-config-sheet.wxss`
- `artifacts/ui-system-rebuild/20260707-gear-detail-owner-skeleton/fixtures.json`
- `artifacts/ui-system-rebuild/20260707-gear-detail-owner-skeleton/manifest.json`

## Fixture Coverage

`GearLoadoutBoard` fixtures:

- `gear_loadout_loading`
- `gear_loadout_ready`
- `gear_loadout_blocked_slots`
- `gear_loadout_source_reference`

`GearConfigSheet` fixtures:

- `gear_config_candidate_list`
- `gear_config_variant_choice`
- `gear_config_enhancement_blocked`
- `gear_config_community_import`

The fixtures cover loading, complete slots, missing slots, source-reference items, candidate selection, variant-required blocker, enhancement cap blocker and community import source-reference state. They use payload-shaped `iconSrc` fields or text fallback only. They are not production item claims, BiS recommendations, DPS previews, rankings, scores or official source claims.

## Data Trust Boundaries

- No visible `DPS`, `BiS`, `综合评分`, `S/A 级`, `提升优先级`, ranking or percentile claim is introduced.
- Real item icons are component inputs only. Production icons must come from payload, Battle.net/WebSim mapping, repository verified assets or user-provided source.
- Missing icons use text fallback through `GameObjectIcon`.
- `GearLoadoutBoard` and `GearConfigSheet` own slot card, icon socket, candidate row, chip, blocker, action rail and evidence-row geometry. The page must not recreate these shapes after the permit is activated.
- Raw backend blocker keys, raw `bonus_id`, `gem_id`, `enchant_id`, `crafted_stats`, token, openid, user id and database id remain forbidden in visible UI.

## Non-Promotion

This evidence is intentionally below implementation:

- `targetLocked=false`
- `activePermit=false`
- `pageIntegration=false`
- `runtimeVerified=false`
- `devtoolsTouched=false`
- `routeSmoke=false`
- `finalAccepted=false`

Next required evidence:

1. Gear detail component/browser precheck with viewport screenshots and owner crops.
2. User target lock decision.
3. Conversion of `gear_detail` draft into a single active implementation permit.
4. Page integration using owner components only.
5. Real WeChat mini-program screenshots, overlay/red-zone/scorecard, route smoke and DevTools action ledger.
