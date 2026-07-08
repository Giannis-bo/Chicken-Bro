# News List Detail Implementation Permit Draft

Status: `implementation_permit_draft`
Surface: `news_list_detail`
Primary routes: `/pages/news/list`, `/pages/news/detail`
Created: 2026-07-07

This document is not `target_locked`, not an active implementation permit, and does not authorize page WXML/WXSS edits. It records the constraints required before rebuilding the news list and article detail reading flow in the WOW mini-program UI system rebuild.

## Why This Permit Exists

`news_list_detail` is the final missing permit in the implementation permit coverage matrix after `profile_templates`. It completes the news flow after `news_home`:

- `news_home` can surface ranked rows and channel docks, but list/detail owns the actual reading path.
- News list owns channel/metric query state, loading, empty, fallback and article-row navigation.
- News detail owns title, original title, Chinese body blocks, source proof, badges, tags, copy-source action and not-found/fallback states.
- The news API client has strict ready gates for `source_translation`, `official_verified`, `approved`, `official` and complete translated bodies; UI must not weaken those gates by hiding fallback/incomplete states.

This surface must not be treated as a simple article-card restyle. If the UI rebuild replaces source translation with LLM commentary, hides fallback state, invents source logos/thumbnails, or lets detail pages show incomplete article payload as verified content, it breaks the product trust contract.

## Current Source Findings

- `pages/news/list.wxml` directly composes `list-shell`, `list-header`, `list-card`, `article-card`, `article-head`, source URL text and empty/loading states with page-private classes.
- `pages/news/list.wxss` owns list gutters, card borders, channel chips, title/summary/source typography and empty-card geometry as page-private CSS.
- `pages/news/list.js` imports `requestArticleList()`, tracks `news_list_view`, stores `type/key/value` query context, renders `fromFallback` / `requestError`, and opens `/pages/news/detail?id=...`.
- `pages/news/detail.wxml` directly composes `detail-card`, meta row, source badges, original title, summary, tag chips, `bodyBlocksZh`, source footer, copy-source button and fallback/not-found warnings.
- `pages/news/detail.wxss` owns detail panel, source badges, body block, list, quote, chip, source footer, source button and warning geometry as page-private CSS.
- `pages/news/detail.js` imports `requestArticleDetail()`, tracks article view/copy events, sets `homeButton` based on stack depth, normalizes article tags/body blocks/source badges and calls `wx.setClipboardData()`.
- `pages/news/news-api.js` only accepts ready article payloads when `contentStatus=ready`, `translationStatus=llm`, `translationFidelity=source_translation`, `verificationStatus=official_verified`, `licenseStatus=approved`, `sourceTier=official`, complete translated body, source name/url/date, source badges and tags are present.
- `requestArticleList()` and `requestArticleDetail()` fall back to local seed-derived payloads with `fromFallback=true` and explicit error strings when the API base is missing, requests fail, or payloads are incomplete.
- `docs/design/2026-07-07-wow-ui-system-target-lock-proposal.md` defines this surface as a ledger-first reading flow: list with channel filter/source freshness/loading/empty/source_reference rows; detail with title/original/source/date/content/source proof/related action; no LLM commentary replacing source translation.
- `docs/design/2026-07-07-wow-ui-system-route-smoke-plan.md` already includes `news_channel_official` and `news_detail_first` route smoke scenes.

## Target Dependency

Before this draft can become active, the following must exist:

- A user-confirmed `target_locked` direction for the ledger-first reading flow.
- Owner contracts for `ArticleListBoard` and `ArticleReader`, or explicit revisions to existing `RankedFeed` / `EvidenceLedger` contracts that cover equivalent responsibilities.
- Accepted asset manifest entries for article list panels, reader panel, source-proof rows and low-semantic fallback materials.
- Fixture coverage for ready list, empty list, fallback list, official channel list, article ready detail, missing id, not found, fallback detail, long title, long source URL, list body blocks, quote blocks and source-copy success.
- Route smoke plan entries for list query, list row open, detail back/home behavior and copy-source action.

## Owner Components

Future implementation must compose existing foundation owners and add news-specific owners instead of rebuilding geometry in page classes.

- `PageFrame`: owns route frame, safe area, reading gutters, scroll bounds and back/home navigation spacing.
- `WowPanel`: owns list header, reader shell, section framing and dense article surface spacing.
- `RankedFeed`: may own list-row/card geometry when rows are rank/feed-like, including title/source/date/thumbnail/fallback layout.
- `EvidenceLedger`: owns source proof, source freshness, fallback warning, source_reference and translation/verification rows.
- `ActionButton`: owns open-detail, copy-source, retry/source actions and disabled states.
- `MaterialImage`: owns low-semantic background/panel materials and must not become article facts.
- `GameObjectIcon`: owns real source/object icon sockets when source maps exist; source logos cannot be generated.
- `ArticleListBoard`: new or revised owner for query title, count, loading/empty/fallback states, article rows, row actions and list density.
- `ArticleReader`: new or revised owner for detail title stack, original title, summary, body blocks, list/quote rendering, tag chips, source footer and not-found/fallback detail states.

## Data Boundary

Allowed data sources:

- `requestArticleList(query)`
- `requestArticleDetail(articleId)`
- Existing fallback payloads derived from `server/news/articles.seed` through `buildNewsHomePayload()`.
- Existing article payload fields already validated by `pages/news/news-api.js`.
- Existing `trackPageView`, `trackEvent`, `trackPageLeave` analytics calls.
- Existing `wx.navigateTo()` from list to detail and `wx.setClipboardData()` for source copying.

Allowed UI-facing fields:

- List fields: `title`, `count`, `articles[]`, `fromFallback`, `requestError`, query `type/key/value`.
- Article row fields: `id`, `channel`, `publishedAt`, `title`, `summary`, `sourceName`, `sourceUrl`.
- Detail fields: `title`, `originalTitle`, `summary`, `channel`, `category`, `publishedAt`, `sourceName`, `sourceUrl`, `sourceBadges`, `metaChips`, `tagItems`, `bodyBlocksZh`, `fromFallback`, `requestError`.
- Article evidence fields only through player-facing language: content ready, source translation, official verification, approved source and fallback/cache state.

Forbidden UI exposure:

- Raw backend payload dumps, raw collector metadata, admin review fields, database ids, tokens or internal job ids.
- Raw LLM prompt/output, raw translator JSON, source scraper payload or moderation diagnostics.
- Hidden fallback/incomplete state on list or detail pages.
- Generated source logos, generated article screenshots, generated official badges or generated thumbnails that imply real article imagery.
- Fake read counts, hotness scores, rankings, manual refresh success, official verification, source freshness or publication dates.

## Product Rules

- Article list/detail may show verified article content only when `news-api.js` ready gates accept the payload.
- Incomplete API payloads must fall back with visible `fromFallback` / `requestError` language; they cannot be silently displayed as live verified content.
- `source_translation` means translated source content, not freeform LLM commentary or a synthetic summary.
- `official_verified`, `approved`, `official` and source badges may not be invented by UI code.
- Source URL copying must copy the actual `article.sourceUrl`; no generated or shortened source can replace it unless a separate source contract is added.
- `bodyBlocksZh` types must be preserved: paragraph, heading, list and quote require distinct but component-owned rendering.
- Missing article id and not-found states must be explicit, not blank pages.
- List query state must be preserved when opening detail and returning.
- No manual refresh controls may be added to user-facing list/detail pages under this permit.
- News article visuals must come from payload evidence; low-semantic materials may support panels but cannot imply story imagery.

## Allowed Files After Active Conversion

Only after this draft is explicitly converted to an active permit:

- `pages/news/list.wxml`
- `pages/news/list.wxss`
- `pages/news/list.js`
- `pages/news/list.json`
- `pages/news/detail.wxml`
- `pages/news/detail.wxss`
- `pages/news/detail.js`
- `pages/news/detail.json`
- `pages/news/news-api.js` only for UI-facing read-model fields or stricter validation; no backend contract relaxation.
- New or revised foundation/news components: `ArticleListBoard`, `ArticleReader`, `PageFrame`, `WowPanel`, `RankedFeed`, `EvidenceLedger`, `ActionButton`, `MaterialImage`, `GameObjectIcon`.
- Targeted tests for news list/detail, news API gates, UI system goal, component precheck and route smoke artifacts.
- `artifacts/ui-system-rebuild/*news-list-detail*` evidence.

## Forbidden Actions

- Do not edit `app.json`, tabBar, `project.config.json`, appid, DevTools settings or route registration from this permit.
- Do not close, restart, clear cache, switch project, switch appid, delete DevTools user directories or run broad DevTools automation from this permit.
- Do not modify backend API contracts, collector contracts, translator contracts, moderation gates or database schema.
- Do not change unrelated surfaces such as news home, builds, workbench, talent, gear, SimC, chickenbro, tasks or profile.
- Do not keep list row, detail card, body block, source badge, tag chip, source button, warning or material geometry as page-private one-off CSS after active implementation.
- Do not weaken `contentStatus`, `translationStatus`, `translationFidelity`, `verificationStatus`, `licenseStatus`, `sourceTier`, complete translated body, source badge or tag readiness gates.
- Do not add manual refresh controls, fake source logos, fake thumbnails, fake read counts, fake official badges, fake publication dates, fake hotness/ranking or hidden fallback state.
- Do not expose raw collector/translator/admin/backend payloads or LLM commentary as article content.

## Required State Mapping

The future page and fixture matrix must cover:

- `news_list_loading`
- `news_list_ready`
- `news_list_empty`
- `news_list_fallback`
- `news_list_incomplete_payload_fallback`
- `news_list_official_channel`
- `news_list_long_title`
- `news_list_long_source_url`
- `news_list_open_detail`
- `news_detail_loading`
- `news_detail_ready`
- `news_detail_missing_id`
- `news_detail_not_found`
- `news_detail_fallback`
- `news_detail_original_title`
- `news_detail_source_badges`
- `news_detail_body_paragraph`
- `news_detail_body_heading`
- `news_detail_body_list`
- `news_detail_body_quote`
- `news_detail_long_title`
- `news_detail_long_source_url`
- `news_detail_copy_source`
- `news_detail_home_button`

## Route Smoke Scenes

- `news_channel_official`: open `/pages/news/list?type=channel&value=official`, show channel/list title, count, rows or explicit empty/fallback state.
- `news_list_metric_updates`: open `/pages/news/list?type=metric&key=updates`, show query title and rows from the current read model.
- `news_list_loading`: bounded loading state does not collapse page frame.
- `news_list_empty`: empty state keeps source/fallback language and no fake rows.
- `news_list_fallback`: request failure or missing API base shows fallback state and error.
- `news_list_open_detail`: tapping a real row navigates to `/pages/news/detail?id=<articleId>`.
- `news_detail_first`: detail shows title, original/source/date, content blocks and source proof.
- `news_detail_missing_id`: missing id shows explicit missing-id state.
- `news_detail_not_found`: unknown id shows not-found/error state.
- `news_detail_fallback`: fallback detail shows cache/fallback warning.
- `news_detail_copy_source`: copy action writes `article.sourceUrl`.
- `news_detail_back_to_list`: back navigation returns without layout corruption.

## Required Evidence Before Runtime Acceptance

- Browser/component precheck for `ArticleListBoard`, `ArticleReader`, `EvidenceLedger`, `ActionButton`, `RankedFeed` and `WowPanel`.
- Real WeChat mini-program screenshots for official list, metric list, list fallback, ready detail, missing/not-found detail, fallback detail and copy-source action.
- Component crops for list header, article row, source proof ledger, body block rendering, source footer and copy button.
- Target vs implementation overlay/red-zone comparisons for page gutter, row density, body typography, source badge layout, source footer and bottom safe area.
- Scorecard that fails on hidden fallback, fake source badge/logo, generated story image, raw backend payload, LLM commentary replacing source translation, manual refresh control, body block overflow and page-private article geometry.
- Route smoke manifest for all scenes above.
- DevTools action ledger proving low-disturbance capture; if `captureSafe=false`, only browser/component evidence may be recorded.

## Stop Conditions

Stop and do not implement this surface if:

- `target_locked` is absent or still contested.
- `ArticleListBoard` / `ArticleReader` owner contracts are missing and existing foundation owners do not explicitly cover their responsibilities.
- The design requires page-private geometry to align rows, body blocks, source badges, source button or warnings.
- The design needs fake article imagery, fake source marks, fake official verification, fake freshness or hidden fallback to look complete.
- A backend/article/translator contract change is needed to express required source state.
- Tests would need to weaken article ready gates, fallback visibility, source translation fidelity, source URL copy behavior, missing-id/not-found handling, body block preservation or route navigation.
- Real mini-program screenshot shows duplicate chrome, bottom tab collision, text overflow, source URL overflow, body block overflow or missing fallback state.
- DevTools is not capture-safe and the required evidence cannot be gathered through browser/component precheck.

## Non-Promotion Rule

This draft proves only that `news_list_detail` now has a scoped implementation permit draft. It cannot prove:

- `target_locked`;
- `active_implementation_permit`;
- `component_precheck`;
- `runtime_verified`;
- `final_accepted`.
