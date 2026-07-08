# WOW 小程序 UI 系统 Production Component Precheck

Status: `component_precheck`

This document records the first source-driven production component precheck for the WOW mini-program UI system rebuild. It is not `runtime_verified`, not `target_locked`, and not an implementation permit.

## Linked Control Plane

- [WOW 小程序 UI 系统重建完整 Goal](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Foundation Component Contracts](2026-07-07-wow-ui-system-foundation-component-contracts.md)
- [Surface Owner Contracts](2026-07-07-wow-ui-system-surface-owner-contracts.md)
- [News List Detail Owner Skeleton Source Precheck](2026-07-07-wow-ui-system-news-list-detail-owner-skeleton-precheck.md)
- [News List Detail Component Precheck](2026-07-07-wow-ui-system-news-list-detail-component-precheck.md)
- [Foundation Harness Draft](2026-07-07-wow-ui-system-foundation-harness-draft.md)
- [Asset Manifest Draft](2026-07-07-wow-ui-system-asset-manifest-draft.md)
- [Browser Component Precheck](2026-07-07-wow-ui-system-browser-component-precheck.md)
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-production-component-precheck/manifest.json`
- Fixture HTML: `artifacts/ui-system-rebuild/20260707-production-component-precheck/component-fixture.html`

## What This Proves

- All 12 foundation owner component directories have WXML, JS, WXSS and JSON files.
- Component JS sources compile.
- Foundation WXML no longer carries `pass36` / `pass37` class aliases.
- `ModuleCard` now routes status rendering through `StatusVisual`, not legacy `status-badge`.
- `StatusVisual` owns the shared state vocabulary and the base/glyph/atomic structure.
- `ChatShell` owns the chat scroll, context, evidence rows, next-question chips and input safe-area.
- `ChatShell` fixture copy uses player-facing evidence language (`证据状态` / `部分可用`) and must not expose raw backend vocabulary such as `answerSource`, `confidence`, `job.status`, raw profile, or raw SimC.

## What This Does Not Prove

- It does not prove real WeChat runtime rendering.
- It does not itself include `ArticleListBoard` and `ArticleReader`; those surface owners now have a separate [News List Detail Component Precheck](2026-07-07-wow-ui-system-news-list-detail-component-precheck.md).
- It does not itself replace browser rect measurement; that evidence now lives in [Browser Component Precheck](2026-07-07-wow-ui-system-browser-component-precheck.md).
- It does not prove page integration quality.
- It does not authorize page WXML/WXSS changes.
- It does not promote any target candidate to `target_locked`.

## Current Result

- Source failures: `0`.
- Generated asset blockers: `0`.
- `ChannelDock` and `RankedFeed` no longer hardcode old generated `ui-v2-1-slices` material.
- `ChatShell` fixture has been regenerated from source and no longer contains raw backend evidence field names.
- The fixture is still source/browser-adjacent evidence, not WeChat runtime evidence.

## Next Required Evidence

- Browser rect measurement and component crops are now recorded in [Browser Component Precheck](2026-07-07-wow-ui-system-browser-component-precheck.md).
- `ArticleListBoard` and `ArticleReader` surface component precheck is now recorded separately; page integration still requires target lock and an active `news_list_detail` permit.
- Next step is user confirmation or modification of the target lock proposal.
- After target lock, write a one-surface implementation permit before page integration.
