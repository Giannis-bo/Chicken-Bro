# WOW UI System Material Asset Seed

Status: `material_asset_seed_ready`

Date: 2026-07-07

This document records the first machine-checked low-semantic material seed for the WOW mini-program UI system rebuild. It is a bridge between the earlier asset manifest draft and the future production asset manifest. It is not a production manifest, not target lock, not an active permit, not page integration and not runtime verification.

## Command

```sh
node scripts/ui-system-material-asset-seed-preflight.js --require-seed --json
```

Expected current exit code: `0`.

## Purpose

The prior UI attempts failed partly because assets were treated as page decoration instead of component-owned material. This seed narrows the next step:

- keep imagegen useful as low-semantic material,
- prevent generated images from becoming real WoW objects or factual UI,
- give `MaterialImage`, `WowPanel`, `GameObjectIcon`, `StatusVisual` and `ActionButton` owned inputs,
- keep page WXML/WXSS blocked until target lock and active permit exist.

## Seed Contract

The seed manifest is:

```text
artifacts/ui-system-rebuild/20260707-material-asset-seed/manifest.json
```

It currently records 9 candidate material seeds under a 512KB package budget:

| Class | Owner | Seed Count | Production Status |
| --- | --- | ---: | --- |
| `panel` | `WowPanel` | 2 | candidate only |
| `border` | `WowPanel`, `ActionButton` | 2 | candidate only |
| `texture` | `MaterialImage` | 1 | candidate only |
| `socket` | `GameObjectIcon` | 1 | candidate only |
| `state-base` | `StatusVisual` | 1 | candidate only |
| `state-atomic` | `StatusVisual` | 1 | candidate only |
| `decorative` | `PageFrame` | 1 | candidate only |

Every seed declares:

- real file path,
- dimensions,
- file size,
- owner,
- fit strategy,
- allowed surfaces,
- source evidence,
- safety flags for text, fake chrome, real WoW objects, source logos, business conclusions and generated object icons.

All `pageDirectUseAllowed` and `productionUseAllowed` flags are `false`. All seeds require re-cut/review before production.

## Why State Visual Has Two Paths

The seed intentionally includes both:

- `state-base`: a shield/base material owned by `StatusVisual`,
- `state-atomic`: a complete blocked emblem owned by `StatusVisual`.

This supports either layered or atomic implementation later, but it forbids the failed pattern where a page places the shield and exclamation mark independently. Center point, transparent bounds, size and glyph composition remain component-owned.

## Quarantine

The seed keeps these classes out of future production until explicitly reclassified:

- pass36/pass37 named glyphs and fallback thumbnails,
- whole-page target images,
- generated fake chrome,
- legacy restoration assets,
- rejected heavy-shell direction assets.

## Current Judgment

This closes one gap in the goal audit: `imagegen_asset_boundary` is no longer just a prose draft. It now has a concrete seed manifest and a preflight. It is still weak evidence because the future production manifest, page adoption, runtime screenshots and visual acceptance are missing.

## Non-Promotion Rule

This seed can only prove `material_asset_seed_ready`. It cannot prove `production_asset_manifest_ready`, `target_locked`, `active_implementation_permit`, `page_integration`, `runtime_verified` or `final_accepted`.
