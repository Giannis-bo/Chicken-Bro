# News List Detail Active Implementation Permit

Status: `active_implementation_permit`

Date: 2026-07-07

Surface: `news_list_detail`

## Two-Part Goal Boundary

This permit inherits the current two-part goal sync at `artifacts/ui-system-rebuild/20260707-two-part-goal-sync/manifest.json`.

Required status: `two_part_goal_sync`.

The current delivery convergence goal is narrower than the long-term system rebuild: exactly one surface is permitted for page integration in this pass, and all other surfaces remain backlog, risk, or next permit candidates.

## Target Lock Decision

Required target decision record:

- `docs/design/2026-07-07-wow-ui-system-target-locked-decision.md`

Required target status: `target_locked`.

Confirmed target: `A-Cockpit + B-Ledger + C-Captain`.

Confirmed surface: `news_list_detail`.

Preflight:

```sh
node scripts/ui-system-target-lock-decision-preflight.js --require-decision --json
```

## Decision Brief Boundary

This permit references `artifacts/ui-system-rebuild/20260707-target-lock-decision-brief/manifest.json`.

Expected brief status: `target_lock_decision_brief`.

Expected ready status: `target_lock_decision_brief_ready`.

The permit preserves the brief's runtime gates:

- `production_asset_manifest_preflight`
- `real_wow_source_map_preflight`
- `page_adoption_preflight`
- `visual_acceptance_preflight`
- `route_smoke_execution_preflight`
- `devtools_action_ledger_preflight`

## Allowed Files

The active surface may edit:

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

Delivery convergence tabBar exception:

- `app.json` may be edited only to add native tabBar `iconPath` and `selectedIconPath`.
- `assets/tabbar/*` may be added only for local runtime tabBar icons.

## Forbidden Files And Actions

- `app.json` changes are forbidden except the tabBar icon exception above.
- `project.config.json` is forbidden.
- Appid changes, DevTools project switching, broad cache clearing and route registration changes are forbidden.
- Unrelated surfaces are forbidden: builds, workbench, Chickenbro, tasks, profile, SimC, talent, gear and news home.
- Page-private article row, body block, source proof, status, button, warning or material geometry is forbidden.
- Fake read counts, fake source logo, fake official badge, fake publication date, fake hotness and fake manual refresh success are forbidden.
- Hidden fallback or incomplete state is forbidden.
- Raw backend payload, collector metadata, translator JSON, LLM prompt/output, admin fields, token, database id or internal job id are forbidden.

## Owner Components

Required owner components:

- `ArticleListBoard`
- `ArticleReader`
- `PageFrame`
- `WowPanel`
- `RankedFeed`
- `EvidenceLedger`
- `ActionButton`
- `MaterialImage`
- `GameObjectIcon`

Page files may compose these owners and pass data/events. They must not rewrite owner geometry in page classes.

## Material Asset Boundary

This permit references `artifacts/ui-system-rebuild/20260707-material-asset-seed/manifest.json`.

Required status: `material_asset_seed_ready`.

The seed remains seed-only: `productionManifest=false`.

No page direct use and no production direct use: `pageDirectUseAllowed=false` and `productionUseAllowed=false`.

Imagegen material cannot provide real WoW objects, source logos, text, business conclusions or fake chrome.

## Production Asset Manifest Gate

Before promoting imagegen material into production for this surface, run:

```sh
node scripts/ui-system-production-asset-manifest-preflight.js --require-production-manifest --json
```

The manifest must declare paths, dimensions, owners, fit strategy, allowed surfaces and package budget. This permit does not require imagegen material for `news_list_detail` if the surface can pass with owner components and real data.

## Real WoW Source Map Gate

Before real WoW object assets are introduced into this surface, run:

```sh
node scripts/ui-system-real-wow-source-map-preflight.js --require-source-map --json
```

The news list/detail surface may render article source state and fallback visuals, but real WoW object icons must come from the source map, not imagegen or target screenshots.

## Data Boundary

- Data comes from existing `pages/news/news-api.js` article list/detail requests.
- The permit does not alter backend API shape, collector logic, translation pipeline, moderation gates or database schema.
- Article list rows may use title, summary, channel, publishedAt, sourceName and sourceUrl.
- Detail view may use title, originalTitle, summary, channel, publishedAt, sourceBadges, metaChips, tagItems, bodyBlocksZh and article.sourceUrl.

## Protected Behaviors

- Article ready gates require `contentStatus=ready` when present.
- Article ready gates require `translationFidelity=source_translation` when present.
- Article ready gates require `verificationStatus=official_verified` when present.
- Article ready gates require `licenseStatus=approved` when present.
- Article ready gates require `sourceTier=official` when present.
- Complete translated body remains visible when available.
- Fallback list/detail state remains visible.
- Missing id and not-found states remain explicit.
- `bodyBlocksZh` paragraph, heading, list and quote blocks are preserved.
- Copy source action uses `article.sourceUrl`.
- List row navigation preserves article id.
- Visible fallback state must remain visible and understandable.

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

Run these before claiming the surface is implementation-ready:

```sh
node scripts/ui-system-target-lock-decision-brief-preflight.js --require-ready --json
node scripts/ui-system-target-lock-decision-preflight.js --require-decision --json
node scripts/ui-system-active-permit-preflight.js --surface news_list_detail --require-active-permit --json
```

Runtime-oriented gates remain required before runtime promotion:

```sh
node scripts/ui-system-production-asset-manifest-preflight.js --require-production-manifest --json
node scripts/ui-system-real-wow-source-map-preflight.js --require-source-map --json
node scripts/ui-system-page-adoption-preflight.js --surface news_list_detail --require-adoption --json
```

## Post-Integration Evidence

Required evidence after implementation:

- target-lock decision preflight.
- active permit preflight.
- course-correction preflight.
- `news_list_detail` page adoption preflight.
- relevant unit tests.
- route smoke plan or execution evidence.
- screenshots when DevTools capture is safe.

## Stop Conditions

Stop and do not widen scope if:

- a second surface needs page WXML/WXSS changes;
- app route registration changes are needed;
- backend/API contract changes are needed;
- generated or reference-only material is needed directly in a page;
- DevTools login state becomes unstable;
- page adoption requires page-private geometry.

## Non-Promotion Boundary

This permit allows exactly one page integration slice. It is not:

- all-surface implementation;
- `runtime_verified`;
- `final_accepted`;
- all-surface visual acceptance;
- proof that non-selected pages are done.
