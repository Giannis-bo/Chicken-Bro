# WOW UI System Route Smoke Execution Manifest Template

Status: `route_smoke_execution_template_only`

Date: 2026-07-07

This template defines the required JSON contract for a future real route-smoke execution run. It does not run WeChat Developer Tools, does not create screenshots, and does not prove `runtime_verified` or `final_accepted`.

## Linked Control Plane

- [WOW 小程序 UI 系统重建完整 Goal](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Route Smoke And Runtime Verification Plan](2026-07-07-wow-ui-system-route-smoke-plan.md)
- [DevTools Action Ledger Template](2026-07-07-wow-ui-system-devtools-action-ledger-template.md)
- [Production Asset Manifest Template](2026-07-07-wow-ui-system-production-asset-manifest-template.md)
- Preflight: `scripts/ui-system-route-smoke-execution-preflight.js`
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-route-smoke-execution-template/manifest.json`

## Command

```sh
node scripts/ui-system-route-smoke-execution-preflight.js --require-execution --json
```

Current expected exit code without a real runtime execution manifest: `11`.

Default runtime manifest path:

```text
artifacts/ui-system-rebuild/runtime/route-smoke-execution-manifest.json
```

## Required Runtime Manifest Shape

```json
{
  "status": "route_smoke_execution_ready",
  "schemaVersion": 1,
  "targetLockDecision": "docs/design/2026-07-07-wow-ui-system-target-locked-decision.md",
  "activePermit": "docs/plans/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit.md",
  "devtoolsActionLedgerPath": "artifacts/ui-system-rebuild/runtime/devtools-action-ledger.json",
  "productionAssetManifestPath": "artifacts/ui-system-rebuild/runtime/production-asset-manifest.json",
  "checkedAt": "2026-07-07T00:00:00.000Z",
  "captureSafe": true,
  "viewportMatrix": ["compact", "standard", "large"],
  "artifactPaths": {
    "manifest": "artifacts/ui-system-rebuild/runtime/route-smoke-execution-manifest.json",
    "devtoolsActionLedger": "artifacts/ui-system-rebuild/runtime/devtools-action-ledger.json",
    "screenshotsDir": "artifacts/ui-system-rebuild/runtime/screenshots",
    "componentCropsDir": "artifacts/ui-system-rebuild/runtime/component-crops",
    "comparisonsDir": "artifacts/ui-system-rebuild/runtime/comparisons",
    "overlaysDir": "artifacts/ui-system-rebuild/runtime/overlays",
    "redZonesDir": "artifacts/ui-system-rebuild/runtime/red-zones",
    "scorecardJson": "artifacts/ui-system-rebuild/runtime/scorecard.json",
    "routeSmokeReport": "artifacts/ui-system-rebuild/runtime/route-smoke-report.md"
  },
  "scorecard": {
    "status": "pass",
    "sceneCount": 27,
    "failedScenes": []
  },
  "sceneResults": [
    {
      "id": "news_home_top",
      "surface": "news_home",
      "route": "/pages/news/news",
      "status": "pass",
      "viewports": ["compact", "standard", "large"],
      "assertions": {
        "noFakeChrome": true,
        "noHorizontalOverflow": true,
        "noForbiddenStrongClaims": true,
        "noQuarantineAssets": true,
        "safeAreaClear": true,
        "longTextFits": true,
        "ownerFitRespected": true
      },
      "screenshotPath": "artifacts/ui-system-rebuild/runtime/screenshots/news_home_top.png",
      "componentCropPaths": [
        "artifacts/ui-system-rebuild/runtime/component-crops/news_home_top-feed.png"
      ],
      "comparisonPath": "artifacts/ui-system-rebuild/runtime/comparisons/news_home_top.png",
      "overlayPath": "artifacts/ui-system-rebuild/runtime/overlays/news_home_top.png",
      "redZonePath": "artifacts/ui-system-rebuild/runtime/red-zones/news_home_top.png",
      "routeActions": [
        {
          "action": "switchTab",
          "route": "/pages/news/news"
        }
      ],
      "visibleStrongClaims": [],
      "quarantineAssetReferences": []
    }
  ]
}
```

The real execution manifest must include all 27 scenes from the route smoke plan:

- `news_home_top`
- `news_home_scrolled`
- `news_channel_official`
- `news_detail_first`
- `builds_tab_top`
- `builds_spec_switch`
- `workbench_ready`
- `workbench_blocked_gear`
- `workbench_partial_talent`
- `workbench_stale`
- `workbench_evidence_expanded`
- `talent_simulator_load`
- `talent_simulator_missing`
- `gear_detail_load`
- `gear_missing_slot`
- `simc_from_workbench`
- `simc_blocked_templates`
- `smart_analysis_tab`
- `chickenbro_empty`
- `chickenbro_workbench_context`
- `chickenbro_generating`
- `chickenbro_done`
- `chickenbro_failed`
- `tasks_list`
- `task_detail`
- `profile_guest`
- `profile_templates`

## Required Per-Scene Assertions

Every scene must pass:

- `noFakeChrome`
- `noHorizontalOverflow`
- `noForbiddenStrongClaims`
- `noQuarantineAssets`
- `safeAreaClear`
- `longTextFits`
- `ownerFitRespected`

Every scene must also provide a real screenshot, at least one component crop, one current/target/implementation comparison, one overlay, one red-zone image, and route actions.

## Forbidden Runtime Shortcuts

The execution manifest fails if:

- `captureSafe` is not true;
- the target lock decision, active permit, DevTools action ledger, or production asset manifest path is missing;
- any required scene is absent;
- any scene lacks compact / standard / large viewport evidence;
- any scene status is not `pass`;
- any scene includes visible `DPS`, `综合评分`, `S 级`, `A级`, or `提升优先级` without the policy gate;
- any scene references quarantine assets;
- any route action records `cli open`, `cli close`, forced restart, clear cache, project/appid switch, user-data replacement, login, or logout.

## Non-Promotion Boundary

This template can only prove `route_smoke_execution_template_only`. It cannot prove target lock, active permit, page integration, runtime verification, visual acceptance, or final acceptance.
