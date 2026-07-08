# News List Detail Owner Skeleton Source Precheck

Status: `owner_skeleton_source_precheck`
Created: 2026-07-07

This document records the first source-level owner skeleton for the `news_list_detail` surface. It is not `target_locked`, not `component_precheck`, not `browser_precheck`, not an active implementation permit, and not runtime verified.

## Linked Control Plane

- [WOW 小程序 UI 系统重建完整 Goal](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Surface Owner Contracts](2026-07-07-wow-ui-system-surface-owner-contracts.md)
- [News List Detail Permit Draft](../plans/2026-07-07-wow-ui-system-news-list-detail-implementation-permit-draft.md)
- [Implementation Permit Coverage Matrix](2026-07-07-wow-ui-system-implementation-permit-coverage-matrix.md)
- [News List Detail Component Precheck](2026-07-07-wow-ui-system-news-list-detail-component-precheck.md)
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-news-list-detail-owner-skeleton/manifest.json`
- Fixture matrix: `artifacts/ui-system-rebuild/20260707-news-list-detail-owner-skeleton/fixtures.json`

## What Changed

- Added `components/article-list-board/*`.
- Added `components/article-reader/*`.
- Added a `news_list_detail` fixture matrix for list and reader states.
- No page WXML/WXSS integration was performed.
- No route registration, tabBar, appid, DevTools or backend contract changes were performed.

## Owner Responsibilities Now In Source

### ArticleListBoard

- Owns list header, count, loading skeletons, empty state, fallback/source_reference slab and article row geometry.
- Emits `openarticle` with article id and query context.
- Keeps `fromFallback` / `requestError` visible through `EvidenceLedger`.
- Uses `StatusVisual` for list and row states.
- Uses `MaterialImage` only for low-semantic or payload-provided row visuals.

### ArticleReader

- Owns title stack, original title, summary, source/date rows, chips, source proof, translated body blocks and source footer.
- Preserves body block types: heading, paragraph, list and quote.
- Emits `copysource` with `article.sourceUrl` only.
- Shows missing-id and not-found as explicit blocked states.
- Uses `EvidenceLedger`, `StatusVisual` and `ActionButton` instead of page-private source proof, status and copy button geometry.

## Fixture Coverage

List fixtures:

- `news_list_loading`
- `news_list_ready`
- `news_list_empty`
- `news_list_fallback`
- `news_list_long_source_url`

Reader fixtures:

- `news_detail_loading`
- `news_detail_ready`
- `news_detail_missing_id`
- `news_detail_not_found`
- `news_detail_fallback`
- `news_detail_long_source_url`

## Protected Boundaries

- No fake read count, heat score, source logo, official badge, publication date or manual refresh success.
- No LLM commentary replacing source translation.
- No raw backend payload, collector metadata, translator JSON, LLM prompt/output, admin field, token, database id or internal job id.
- No page-private article row, reader body block, source footer or copy button geometry in this skeleton.
- No full-page generated target image or generated article thumbnail is referenced.

## Next Required Evidence

- Production/browser component precheck and component crops are now recorded in [News List Detail Component Precheck](2026-07-07-wow-ui-system-news-list-detail-component-precheck.md).
- User confirmation or revision of target lock.
- Explicit conversion of the `news_list_detail` permit draft into an active implementation permit before page integration.
- Real mini-program screenshots, route smoke and DevTools action ledger after page implementation.

## Non-Promotion Rule

This document can only prove `owner_skeleton_source_precheck`. It cannot prove:

- `target_locked`;
- `active_implementation_permit`;
- `component_precheck`;
- `browser_precheck`;
- `runtime_verified`;
- `final_accepted`.
