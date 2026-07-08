# WOW UI System Real WoW Source Map Seed

Status: `real_wow_source_map_seed_ready`

Date: 2026-07-07

This document records the pre-runtime source-map seed for real WoW object imagery. It exists so future UI implementation can use imagegen for low-semantic materials while keeping class, spec, hero, talent, spell, item, source, dungeon, raid and affix facts tied to real interfaces or verified repository mappings.

It is not a runtime source map, not a target lock, not an active implementation permit, not page integration and not runtime verification.

## Command

```sh
node scripts/ui-system-real-wow-source-map-seed-preflight.js --require-seed --json
```

Current expected exit code: `0`.

## Seed Sources

| Entity | Source | Owner | Runtime Rule |
| --- | --- | --- | --- |
| Class | `pages/common/wow-spec-assets.js` `CLASS_ASSET_MAP` plus `pages/common/game-asset.js` render URL normalization. | `GameObjectIcon` | Use verified mapping or localized initials fallback. |
| Spec | `pages/common/wow-spec-assets.js` `SPEC_ASSET_MAP` plus `pages/common/game-asset.js`. | `GameObjectIcon` | Use verified mapping or localized initials fallback; do not draw spec icons with imagegen. |
| Hero | `server/websim_payload.py` `hero_tree_payload`. | `GameObjectIcon` | Use key/label context and text fallback unless a verified icon field exists later. |
| Talent | `/api/websim/talents` payload built by `server/websim_payload.py`. | `GameObjectIcon` | Use `gameAsset.iconUrl` / `iconUrl` / spell id evidence; fallback is text. |
| Spell | Battle.net spell media imported by WebSim payload code. | `GameObjectIcon` | Use Battle.net/WebSim `gameAsset.iconUrl`; fallback is text. |
| Item | `/api/websim/gear` payload built by `server/websim_payload.py`. | `GameObjectIcon` | Use item `gameAsset.iconUrl`; fallback is text. |
| Source | Backend source checks and evidence rows. | `GameObjectIcon` | Use source reference row; do not invent official logos. |
| Dungeon | Battle.net journal cache and Raider.IO observed run context. | `GameObjectIcon` | Use verified source labels or text fallback. |
| Raid | Battle.net journal raid cache. | `GameObjectIcon` | Use verified source labels or text fallback. |
| Affix | Scenario/affix context from backend and Raider.IO. | `GameObjectIcon` | Use verified labels or text fallback. |

## Runtime Promotion Boundary

The seed only proves that the source categories and code contracts are known. Runtime source-map readiness still requires:

- a user-confirmed `target_locked` decision record;
- exactly one active implementation permit;
- page integration that actually binds the fields;
- `artifacts/ui-system-rebuild/runtime/real-wow-source-map.json`;
- observed runtime payload fields for the integrated surface;
- no `sourceClass=imagegen` or generated object flags for real WoW objects.

Frontend request reuse is anchored through `pages/builds/websim-api.js`, so page owners consume the existing WebSim client instead of inventing new image or data contracts.

## Non-Promotion Rule

This seed can only prove `real_wow_source_map_seed_ready`. It cannot prove `target_locked`, `active_implementation_permit`, `page_integration`, `runtime_verified`, `final_accepted` or visual acceptance.
