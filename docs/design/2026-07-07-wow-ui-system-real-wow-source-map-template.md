# WOW UI System Real WoW Source Map Template

Status: `real_wow_source_map_template_only`

Date: 2026-07-07

This template defines the runtime source-map contract for real WoW object imagery. It is not a production source map, not page integration, not runtime verification and not final acceptance.

## Command

```sh
node scripts/ui-system-real-wow-source-map-preflight.js --require-source-map --json
```

Current expected exit code without a real source map: `15`.

## Purpose

The UI system uses imagegen only for low-semantic material such as panel, border, texture, socket and decorative surfaces. Real WoW objects must never be invented by imagegen or cropped from target screenshots.

This source map makes every real object image traceable before page integration:

- class icons;
- spec icons;
- hero talent icons;
- talent node and spell icons;
- item and equipment icons;
- source icons and source labels;
- dungeon, raid and affix icons when surfaced.

## Required Runtime Shape

The real runtime file must live at:

`artifacts/ui-system-rebuild/runtime/real-wow-source-map.json`

The status must be:

`real_wow_source_map_ready`

Required top-level fields:

- `schemaVersion: 1`
- `targetLockDecision`
- `activePermit`
- `checkedAt`
- `sourceMaps`

Each `sourceMaps[]` entry must include:

```json
{
  "id": "frost-mage-spec-icon",
  "entityType": "spec",
  "sourceClass": "websim",
  "owner": "GameObjectIcon",
  "allowedSurfaces": ["builds_tab", "current_spec_workbench", "simc", "chickenbro"],
  "payloadField": "payload.currentSpec.gameAsset.iconUrl",
  "contractReference": "server/builds/home-payload.js class/spec gameAsset mapping",
  "requiredFields": ["entityType", "entityId", "iconUrl", "source", "status"],
  "fallback": "localized_initials",
  "status": "source_map_ready",
  "generatedByImagegen": false,
  "containsGeneratedObject": false
}
```

Allowed `sourceClass` values:

- `api`
- `battlenet`
- `websim`
- `repo_verified`
- `user_provided`

Forbidden source classes:

- `imagegen`
- `target_screenshot_crop`
- `random_cdn_without_mapping`
- `generated_product_glyph`
- `page_private_fallback_art`

`repo_verified` and `user_provided` entries must also provide:

- `assetPath`
- `verifiedBy`

`api`, `battlenet` and `websim` entries must provide:

- `payloadField`
- `contractReference`

## Required Coverage

The complete source map must cover these entity types:

- `class`
- `spec`
- `hero`
- `talent`
- `spell`
- `item`
- `source`
- `dungeon`
- `raid`
- `affix`

The complete source map must cover these core surfaces:

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

## Fail-Closed Rules

The preflight rejects:

- missing source map file;
- `sourceClass=imagegen`;
- generated object flags;
- page-private owners;
- target screenshot crops;
- generated/pass36/pass37/reference paths for file-backed sources;
- payload sources that pretend to be local assets;
- file-backed sources without a real file and verification owner;
- missing entity-type or surface coverage.

## Non-Promotion Boundary

This template can only prove `real_wow_source_map_template_only`.

It cannot prove:

- `target_locked`;
- `active_implementation_permit`;
- `page_integration`;
- `runtime_verified`;
- `final_accepted`.
