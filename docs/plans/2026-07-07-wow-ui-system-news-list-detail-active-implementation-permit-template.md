# News List Detail Active Implementation Permit Template

Status: `active_implementation_permit_template_only`

Date: 2026-07-07

This template defines the required shape of the future active implementation permit for `news_list_detail`. It is not an active permit, not page integration, not runtime verification, and not final acceptance.

Do not rename this file into the real active permit automatically. The real active permit may be created only after the real `target_locked` decision record passes preflight.

## Future File

- Planned real active permit file: `docs/plans/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit.md`
- Planned real artifact: `artifacts/ui-system-rebuild/20260707-news-list-detail-active-permit/manifest.json`
- Required real status: `active_implementation_permit`
- Surface: `news_list_detail`
- Primary routes: `/pages/news/list`, `/pages/news/detail`
- Required two-part goal sync: `artifacts/ui-system-rebuild/20260707-two-part-goal-sync/manifest.json`
- Required target decision: `docs/design/2026-07-07-wow-ui-system-target-locked-decision.md`
- Required decision brief: `artifacts/ui-system-rebuild/20260707-target-lock-decision-brief/manifest.json`

## Required Real Permit Sections

The real active permit must include:

- `Status: active_implementation_permit`
- `Surface`
- `Two-Part Goal Boundary`
- `Target Lock Decision`
- `Decision Brief Boundary`
- `Allowed Files`
- `Forbidden Files And Actions`
- `Owner Components`
- `Material Asset Boundary`
- `Production Asset Manifest Gate`
- `Real WoW Source Map Gate`
- `Data Boundary`
- `Protected Behaviors`
- `Route Smoke Scenes`
- `Pre-Integration Checks`
- `Post-Integration Evidence`
- `Stop Conditions`
- `Non-Promotion Boundary`

## Allowed Files

The active permit may allow only:

- `pages/news/list.wxml`
- `pages/news/list.wxss`
- `pages/news/list.js`
- `pages/news/list.json`
- `pages/news/detail.wxml`
- `pages/news/detail.wxss`
- `pages/news/detail.js`
- `pages/news/detail.json`
- `pages/news/news-api.js`
- `components/article-list-board/*`
- `components/article-reader/*`
- targeted foundation component fixes only if they preserve owner contracts
- targeted tests for news list/detail and UI-system evidence
- `artifacts/ui-system-rebuild/*news-list-detail*`

## Forbidden Files And Actions

The active permit must forbid:

- `app.json`
- tabBar changes
- `project.config.json`
- appid changes
- route registration changes
- backend API, collector, translator, moderation gate or database schema changes
- unrelated surfaces: news home, builds, workbench, talent, gear, SimC, Chickenbro, tasks or profile
- page-private article row, body block, source proof, status, button, warning or material geometry
- fake read counts, fake source logo, fake official badge, fake publication date, fake hotness or fake manual refresh success
- hidden fallback or incomplete state
- raw backend payload, collector metadata, translator JSON, LLM prompt/output, admin fields, token, database id or internal job id

## Two-Part Goal Boundary

- The active permit must reference `artifacts/ui-system-rebuild/20260707-two-part-goal-sync/manifest.json`.
- The required status is `two_part_goal_sync`.
- The two-part goal sync must keep `targetLocked=false`, `activeImplementationPermit=false`, `pageIntegrationAllowed=false`, `runtimeVerified=false` and `finalAccepted=false` at the template stage.
- The real permit may only implement the single surface named by the permit; it may not turn the two-part goal sync into a broad page rewrite permission.

## Decision Brief Boundary

- The active permit must reference `artifacts/ui-system-rebuild/20260707-target-lock-decision-brief/manifest.json`.
- The decision brief must remain `target_lock_decision_brief` with ready status `target_lock_decision_brief_ready`.
- The active permit must inherit the brief's production asset manifest, real WoW source map, page adoption, visual acceptance, route smoke execution and DevTools action ledger gates.
- The decision brief is not itself target lock, active permit, page integration or runtime evidence.

## Required Owner Components

- `ArticleListBoard`
- `ArticleReader`
- `PageFrame`
- `WowPanel`
- `RankedFeed`
- `EvidenceLedger`
- `ActionButton`
- `MaterialImage`
- `GameObjectIcon`

## Material Asset Boundary

- The active permit must reference `artifacts/ui-system-rebuild/20260707-material-asset-seed/manifest.json`.
- The required seed status is `material_asset_seed_ready`.
- The seed remains seed-only: `productionManifest=false`, `pageDirectUseAllowed=false` and `productionUseAllowed=false`.
- The permit may not authorize page-direct use of imagegen material or any generated WoW object/fact.

## Production Asset Manifest Gate

Before page integration, the active permit must require:

```sh
node scripts/ui-system-production-asset-manifest-preflight.js --require-production-manifest --json
```

The production manifest must be derived from the material seed, declare exact file paths, dimensions, owners, fit strategy, allowed surfaces and package budget, and must not contain text, fake chrome, real WoW objects, source logos or business conclusions.

## Real WoW Source Map Gate

Before page integration, the active permit must require:

```sh
node scripts/ui-system-real-wow-source-map-preflight.js --require-source-map --json
```

Real WoW objects in the page must come from the runtime source map, not from imagegen material or target screenshots.

## Protected Behaviors

- Article ready gates require `contentStatus=ready`.
- Article ready gates require `translationFidelity=source_translation`.
- Article ready gates require `verificationStatus=official_verified`.
- Article ready gates require `licenseStatus=approved`.
- Article ready gates require `sourceTier=official`.
- Complete translated body is required before live display.
- Fallback list/detail state remains visible.
- Missing id and not-found states remain explicit.
- `bodyBlocksZh` paragraph, heading, list and quote blocks are preserved.
- Copy source action uses `article.sourceUrl`.
- List row navigation preserves article id.

## Route Smoke Scenes

- `news_channel_official`
- `news_list_metric_updates`
- `news_list_loading`
- `news_list_empty`
- `news_list_fallback`
- `news_list_open_detail`
- `news_detail_first`
- `news_detail_missing_id`
- `news_detail_not_found`
- `news_detail_fallback`
- `news_detail_copy_source`
- `news_detail_back_to_list`

## Pre-Integration Checks

The active permit must require these commands before touching page WXML/WXSS:

```sh
node scripts/ui-system-target-lock-decision-brief-preflight.js --require-ready --json
node scripts/ui-system-target-lock-decision-preflight.js --require-decision --json
node scripts/ui-system-active-permit-preflight.js --surface news_list_detail --require-active-permit --json
node scripts/ui-system-production-asset-manifest-preflight.js --require-production-manifest --json
node scripts/ui-system-real-wow-source-map-preflight.js --require-source-map --json
node scripts/ui-system-page-adoption-preflight.js --require-adoption --json
```

## Preflight

Run before page implementation:

```sh
node scripts/ui-system-active-permit-preflight.js --surface news_list_detail --require-active-permit --json
```

While the target-locked decision or real active permit is absent/incomplete, the command exits non-zero.
