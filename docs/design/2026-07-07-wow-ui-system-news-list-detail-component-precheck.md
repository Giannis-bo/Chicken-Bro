# News List Detail Component Precheck

Status: `surface_component_precheck`
Created: 2026-07-07

This document records the first production/browser component precheck for the `news_list_detail` surface owners. It is not `target_locked`, not an active implementation permit, not page integration, and not real WeChat mini-program runtime verification.

## Linked Control Plane

- [WOW 小程序 UI 系统重建完整 Goal](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [News List Detail Owner Skeleton Source Precheck](2026-07-07-wow-ui-system-news-list-detail-owner-skeleton-precheck.md)
- [Surface Owner Contracts](2026-07-07-wow-ui-system-surface-owner-contracts.md)
- [News List Detail Permit Draft](../plans/2026-07-07-wow-ui-system-news-list-detail-implementation-permit-draft.md)
- [Implementation Permit Coverage Matrix](2026-07-07-wow-ui-system-implementation-permit-coverage-matrix.md)
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-news-list-detail-component-precheck/manifest.json`
- Fixture HTML: `artifacts/ui-system-rebuild/20260707-news-list-detail-component-precheck/component-fixture.html`
- Contact sheet: `artifacts/ui-system-rebuild/20260707-news-list-detail-component-precheck/component-crop-contact-sheet.png`

## What Changed

- Added a local headless Chrome precheck runner for `ArticleListBoard` and `ArticleReader`.
- The runner uses production WXSS class names from the two surface owners and their foundation dependencies.
- The fixture renders list and reader states from the owner skeleton fixture matrix.
- The run captures compact / standard / large browser viewport screenshots.
- The run captures seven standard-viewport component crops:
  - article list board
  - article row
  - fallback evidence
  - article reader
  - reader body
  - source footer
  - blocked reader state
- No page WXML/WXSS integration was performed.
- No WeChat DevTools action was performed.

## Current Result

- Status: `surface_component_precheck`
- Failures: `0`
- Warnings: `0`
- Viewports measured: `compact`, `standard`, `large`
- Horizontal overflow: `0` in every measured viewport
- Standard crops written: `7`
- Owner source precheck: `ArticleListBoard=pass`, `ArticleReader=pass`

## Evidence Boundaries

This precheck proves:

- the two owner components parse and keep their declared foundation dependencies;
- the owner fixture matrix can be rendered through production class names;
- loading, ready, empty, fallback, blocked, not-found and long-source-url states have measurable geometry;
- browser-level component crops exist for the key list and reader slots;
- no page-level integration or DevTools action happened.

This precheck does not prove:

- real WeChat mini-program runtime rendering;
- route smoke;
- overlay, red-zone or scorecard acceptance;
- `target_locked`;
- active implementation permission for `pages/news/list` or `pages/news/detail`;
- final UI acceptance.

## Next Required Evidence

- User confirmation or revision of the target lock.
- Explicit conversion of the `news_list_detail` draft permit into an active implementation permit.
- Page integration only under that active permit.
- Real mini-program screenshots after `captureSafe=true`.
- Route smoke and DevTools action ledger after integration.

## Non-Promotion Rule

This document can only prove `surface_component_precheck`. It cannot prove:

- `target_locked`;
- `active_implementation_permit`;
- `runtime_verified`;
- `final_accepted`.
