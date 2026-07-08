# WOW UI System Production Asset Manifest Template

Status: `production_asset_manifest_template_only`

Date: 2026-07-07

This template defines the production asset manifest required before generated material or real WoW object assets can be treated as runtime UI evidence. It is stricter than the asset manifest draft: every production material must have class, owner, path, dimensions, file size, fit mode, allowed surfaces and semantic safety flags; every real WoW object source must have an explicit source class and `GameObjectIcon` ownership.

This template does not promote any asset to production, does not authorize page integration, and does not replace target lock or active permits.

## Command

```sh
node scripts/ui-system-production-asset-manifest-preflight.js --require-production-manifest --json
```

Current expected exit code without a real production manifest: `10`.

## Default Production Manifest Path

```text
artifacts/ui-system-rebuild/runtime/production-asset-manifest.json
```

The default file is intentionally absent in the current source-evidence phase.

## Required JSON Shape

```json
{
  "status": "production_asset_manifest_ready",
  "schemaVersion": 1,
  "targetLockDecision": "docs/design/2026-07-07-wow-ui-system-target-locked-decision.md",
  "activePermit": "docs/plans/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit.md",
  "checkedAt": "2026-07-07T00:00:00.000Z",
  "packageBudget": {
    "currentKb": 120,
    "maxKb": 2048
  },
  "assets": [
    {
      "id": "news_panel_shell",
      "class": "panel",
      "owner": "WowPanel",
      "path": "assets/generated/ui-system/news_panel_shell.png",
      "width": 320,
      "height": 180,
      "sizeKb": 80,
      "fit": "nine_slice",
      "allowedSurfaces": ["news_home", "news_list_detail"],
      "sourceType": "imagegen_low_semantic",
      "containsText": false,
      "containsFakeChrome": false,
      "containsRealWowObject": false,
      "containsSourceLogo": false,
      "containsBusinessConclusion": false
    }
  ],
  "realObjectSourceMap": [
    {
      "entityType": "spec",
      "sourceClass": "api",
      "owner": "GameObjectIcon",
      "requiredFields": "entityType,entityId,iconUrl,source,status",
      "fallback": "localized initials",
      "status": "source_map_ready"
    }
  ],
  "quarantine": [
    {
      "path": "assets/generated/ui-v2-1-slices/20260703/*pass36*",
      "class": "pass-named asset pending recut",
      "reason": "old pass evidence cannot enter runtime by filename inertia"
    }
  ]
}
```

## Generated Material Rules

- Allowed classes: `panel`, `border`, `texture`, `socket`, `state-base`, `state-atomic`, `decorative`.
- Allowed owners are class-specific and must match `WowPanel`, `PageFrame`, `ActionButton`, `MaterialImage`, `GameObjectIcon`, `ModuleCard`, `ChannelDock`, `StatusVisual` or `AppShell`.
- `sourceType` for generated production material must be `imagegen_low_semantic` or `repo_material`.
- Generated production material must declare all semantic safety flags as `false`: `containsText`, `containsFakeChrome`, `containsRealWowObject`, `containsSourceLogo`, `containsBusinessConclusion`.
- Production paths must not include pass36/pass37 naming, source/reference/atlas suffixes, rejected `ui-v3-1`, old `ui-v2-restoration`, or legacy `ui-redesign/20260701` material.
- Size budgets: `panel/border/texture/decorative <= 350KB`, `socket/state-base/state-atomic <= 96KB`.

## Real WoW Source Map Rules

- Real object icons must be owned by `GameObjectIcon`.
- Allowed source classes: `api`, `battlenet`, `websim`, `repo_verified`, `user_provided`.
- Forbidden source classes: `imagegen`, `target_screenshot_crop`, `random_cdn_without_mapping`, `generated_product_glyph`, `page_private_fallback_art`.
- Entity types must be one of: `class`, `spec`, `hero`, `talent`, `spell`, `item`, `source`, `dungeon`, `raid`, `affix`.

## Non-Promotion Rule

This template can only prove `production_asset_manifest_template_only`. A valid future production asset manifest is still not page integration, not runtime verification and not final acceptance. Runtime claims still require active permit, real mini-program screenshots, component crops, overlay, red-zone, scorecard, route smoke and DevTools ledger.
