# WOW UI System Visual Acceptance Scorecard Template

Status: `visual_acceptance_scorecard_template_only`

Date: 2026-07-07

This template defines the scorecard contract for future visual acceptance of the WOW mini-program UI system rebuild. It does not create screenshots, does not compare pixels by itself, and does not prove `runtime_verified` or `final_accepted`.

## Linked Control Plane

- [WOW 小程序 UI 系统重建完整 Goal](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Route Smoke And Runtime Verification Plan](2026-07-07-wow-ui-system-route-smoke-plan.md)
- [Route Smoke Execution Manifest Template](2026-07-07-wow-ui-system-route-smoke-execution-template.md)
- [Page Adoption Preflight Template](2026-07-07-wow-ui-system-page-adoption-preflight-template.md)
- Preflight: `scripts/ui-system-visual-acceptance-preflight.js`
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-visual-acceptance-scorecard-template/manifest.json`

## Command

```sh
node scripts/ui-system-visual-acceptance-preflight.js --require-scorecard --json
```

Current expected exit code without a real runtime scorecard: `13`.

Default runtime scorecard path:

```text
artifacts/ui-system-rebuild/runtime/visual-acceptance-scorecard.json
```

## Required Runtime Scorecard Shape

```json
{
  "status": "visual_acceptance_scorecard_ready",
  "schemaVersion": 1,
  "targetLockDecision": "docs/design/2026-07-07-wow-ui-system-target-locked-decision.md",
  "activePermit": "docs/plans/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit.md",
  "routeSmokeExecutionManifest": "artifacts/ui-system-rebuild/runtime/route-smoke-execution-manifest.json",
  "productionAssetManifestPath": "artifacts/ui-system-rebuild/runtime/production-asset-manifest.json",
  "checkedAt": "2026-07-07T00:00:00.000Z",
  "source": "real_miniprogram_runtime",
  "captureSafe": true,
  "minSurfaceScore": 90,
  "minComponentScore": 90,
  "requiredViewports": ["compact", "standard", "large"],
  "failedSurfaces": [],
  "blockingRedZones": [],
  "surfaces": [
    {
      "id": "news_home",
      "status": "pass",
      "score": 92,
      "viewports": ["compact", "standard", "large"],
      "currentScreenshotPath": "artifacts/ui-system-rebuild/runtime/current/news_home.png",
      "targetImagePath": "artifacts/ui-system-rebuild/runtime/target/news_home.png",
      "implementationScreenshotPath": "artifacts/ui-system-rebuild/runtime/screenshots/news_home_top.png",
      "comparisonPath": "artifacts/ui-system-rebuild/runtime/comparisons/news_home.png",
      "overlayPath": "artifacts/ui-system-rebuild/runtime/overlays/news_home.png",
      "redZonePath": "artifacts/ui-system-rebuild/runtime/red-zones/news_home.png",
      "componentCrops": [
        {
          "component": "RankedFeed",
          "owner": "RankedFeed",
          "status": "pass",
          "score": 93,
          "currentCropPath": "artifacts/ui-system-rebuild/runtime/component-crops/news_home_ranked_feed_current.png",
          "targetCropPath": "artifacts/ui-system-rebuild/runtime/component-crops/news_home_ranked_feed_target.png",
          "implementationCropPath": "artifacts/ui-system-rebuild/runtime/component-crops/news_home_ranked_feed_implementation.png",
          "overlayPath": "artifacts/ui-system-rebuild/runtime/overlays/news_home_ranked_feed.png",
          "redZonePath": "artifacts/ui-system-rebuild/runtime/red-zones/news_home_ranked_feed.png",
          "redZones": []
        }
      ],
      "metrics": {
        "gutterDeltaPxMax": 2,
        "slotDeltaPxMax": 2,
        "glyphCenterDeltaPxMax": 1,
        "textOverflowCount": 0,
        "horizontalOverflowCount": 0,
        "fakeChromeCount": 0,
        "blockingRedZoneCount": 0
      }
    }
  ]
}
```

The real scorecard must include all 10 core runtime surfaces:

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

## Pass Rules

Every surface must provide:

- current screenshot;
- target image;
- implementation screenshot from the real mini-program runtime;
- current / target / implementation comparison;
- overlay image;
- red-zone image;
- at least one component crop with current crop, target crop, implementation crop, overlay and red-zone;
- compact / standard / large viewport coverage;
- score at least `90`.

Every component crop must score at least `90`, have `status=pass`, and have no blocking red-zone entries.

Every surface metric must satisfy:

- `gutterDeltaPxMax <= 2`
- `slotDeltaPxMax <= 2`
- `glyphCenterDeltaPxMax <= 1`
- `textOverflowCount = 0`
- `horizontalOverflowCount = 0`
- `fakeChromeCount = 0`
- `blockingRedZoneCount = 0`

## Forbidden Shortcuts

The scorecard fails if:

- it is not based on `real_miniprogram_runtime`;
- `captureSafe` is not true;
- target lock, active permit, route smoke execution manifest or production asset manifest is missing;
- any required surface is missing;
- current, target or implementation image evidence is missing;
- component crops, overlays or red-zones are missing;
- a surface or component scores below `90`;
- any blocking red-zone, horizontal overflow, text overflow, fake chrome or oversized geometry delta remains.

## Non-Promotion Boundary

This template can only prove `visual_acceptance_scorecard_template_only`. It cannot prove target lock, active permit, page integration, route smoke execution, runtime verification or final acceptance.
