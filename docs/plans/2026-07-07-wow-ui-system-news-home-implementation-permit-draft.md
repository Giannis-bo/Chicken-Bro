# WOW UI System News Home Implementation Permit Draft

Status: `implementation_permit_draft`

This is the first single-surface permit draft for the WOW mini-program UI system rebuild. It is not `target_locked`, not an active implementation permit, and does not authorize page WXML/WXSS edits.

## Linked Control Plane

- [WOW 小程序 UI 系统重建完整 Goal](2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Phase 1/2 Inventory](2026-07-07-wow-mini-program-ui-system-rebuild-phase1-inventory.md)
- [Target Lock Proposal](../design/2026-07-07-wow-ui-system-target-lock-proposal.md)
- [Foundation Component Contracts](../design/2026-07-07-wow-ui-system-foundation-component-contracts.md)
- [Asset Manifest Draft](../design/2026-07-07-wow-ui-system-asset-manifest-draft.md)
- [Route Smoke And Runtime Verification Plan](../design/2026-07-07-wow-ui-system-route-smoke-plan.md)
- [Production Component Precheck](../design/2026-07-07-wow-ui-system-production-component-precheck.md)
- [Browser Component Precheck](../design/2026-07-07-wow-ui-system-browser-component-precheck.md)
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-news-home-permit-draft/manifest.json`

## Surface

Surface: `news_home`

Route: `/pages/news/news`

Reason to start here:

- It directly addresses the earlier failure where the scrolled news priority list became visually flat and near-black.
- It validates foundation owners that should also support later surfaces: `AppShell`, `PageFrame`, `ChannelDock`, `RankedFeed`, `MaterialImage`, and `GameObjectIcon`.
- It is a tab surface, so it exercises bottom tab / safe-area boundaries before the workbench rebuild.

## Target Dependency

This draft assumes the target proposal direction `A-Cockpit + B-Ledger + C-Captain`, but it cannot activate until the user confirms or edits the target lock.

Required before activation:

- `target_locked` design for `news_home`.
- Accepted or revised asset manifest with production / quarantine / real source-map sections.
- Clean production component precheck.
- Clean browser component precheck.
- Explicit user or owner approval to convert this draft into an active implementation permit.

## Intended Component Owners

| Owner | Role On News Home |
| --- | --- |
| `AppShell` | App background, tab-safe floor and no fake host chrome. |
| `PageFrame` | Page gutters, top rhythm, scroll content bounds and bottom tab padding. |
| `ChannelDock` | Six-channel dock geometry, selected state and channel icon sockets. |
| `RankedFeed` | `今日重点` ranked rows, rank column, real thumbnail/fallback, source/date and save affordance. |
| `MaterialImage` | Low-semantic fallback material only; never article facts or source logos. |
| `GameObjectIcon` | Real source/object icon slots where the payload has verified icon evidence; otherwise text fallback. |

Pages may compose these owners and bind data, but may not restyle their internals for local fixes.

## Proposed Allowed Files After Activation

These files would be allowed only after this draft becomes an active permit:

- `pages/news/news.wxml`
- `pages/news/news.wxss`
- `pages/news/news.js`
- `pages/news/news.json`
- `components/channel-dock/*`
- `components/ranked-feed/*`
- narrowly scoped tests for news page and UI system gates
- news-home specific browser/runtime evidence under `artifacts/ui-system-rebuild/`

Any change outside this list requires a revised permit.

## Forbidden Files And Actions

- No `app.json` route or tabBar changes.
- No `project.config.json` / appid / DevTools shadow changes.
- No backend API contract changes.
- No edits to unrelated surfaces such as `pages/builds/*`, `pages/simulator/*`, `pages/profile/*`.
- No page-private status badge, card, button, icon socket, fake chrome or material geometry.
- No direct page reference to quarantine assets, whole-page target images or pass-named generated glyphs.
- No WeChat DevTools open/close/restart/cache-clear/login/logout actions.

## Data Boundary

Allowed data sources:

- Existing news home/list payload from `pages/news/news-api.js`.
- Existing local fallback payload already used by the page.
- Real article visual fields only when the payload already identifies them as article imagery.
- Existing source/channel labels and state already present in the view model.

Forbidden product claims:

- Fake read counts.
- Fake hotness or ranking scores.
- Fake official logos or source verification.
- Generated article thumbnails that imply real article imagery.
- Any hidden source state on source_reference or fallback rows.

## Asset Boundary

Allowed:

- Low-semantic panel, border, texture or socket material after manifest approval.
- Text fallback for missing article/source icons.
- Real article thumbnails only from payload evidence.

Forbidden:

- Imagegen story thumbnails.
- Imagegen official/source marks.
- Any generated class/spec/talent/item/source icon.
- Whole-page target images or contact sheets in production WXML/WXSS.
- Fake time, battery, Wi-Fi, phone frame or WeChat capsule.

## Route Smoke Scope

Required scenes after implementation:

- `news_home_top`: tab enter, channel dock visible, ranked feed preview visible.
- `news_home_scrolled`: `今日重点` list dominant, at least five priority rows visible or valid empty/fallback state.
- `news_channel_official`: channel switch from dock/list path remains usable.
- `news_detail_first`: opening a real row reaches detail and back navigation returns without layout corruption.

Required assertions:

- No horizontal overflow on compact / standard / large.
- No fake host chrome.
- Bottom tab and safe-area are not covered.
- Ranked rows are not all-black; rank, title, metadata and save affordance are visually separable.
- Long Chinese titles and missing thumbnails remain inside `RankedFeed` slots.
- No quarantine asset reference.

## Evidence Required Before Runtime Acceptance

- Browser scene precheck for `news_home_top` and `news_home_scrolled`.
- Real WeChat mini-program screenshots after `captureSafe=true`.
- Component crops for `ChannelDock` and `RankedFeed`.
- Current / target / implementation comparison.
- Overlay and red-zone output for the channel dock and ranked feed.
- Scorecard that explicitly rejects all-black scrolled list, fake chrome and hidden source states.
- Route smoke report and DevTools action ledger.

## Rollback And Stop Conditions

Stop implementation and return to permit revision if any of these occur:

- The target is still not locked.
- A required component owner needs page-private geometry to look acceptable.
- News data requires new backend fields or fake front-end fields to match the design.
- A required image is not real article evidence or an approved low-semantic material.
- Browser precheck passes but real mini-program screenshot shows tab/safe-area overlap.
- DevTools capture is not safe or would require high-disturbance actions.

## Current Status

This draft is ready for target-lock review. It does not activate implementation.
