# WOW UI System Target Lock Decision And News List Detail Activation Packet

Status: `activation_packet_draft`
Created: 2026-07-07

This packet defines the exact work that may happen after the user confirms or revises the target lock. It is not `target_locked`, not an active implementation permit, not page integration, and not runtime verification.

## Linked Evidence

- [WOW 小程序 UI 系统重建完整 Goal](2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Target Lock Proposal](../design/2026-07-07-wow-ui-system-target-lock-proposal.md)
- [Target Lock Readiness Review](../design/2026-07-07-wow-ui-system-target-lock-readiness-review.md)
- [News List Detail Permit Draft](2026-07-07-wow-ui-system-news-list-detail-implementation-permit-draft.md)
- [News List Detail Owner Skeleton Source Precheck](../design/2026-07-07-wow-ui-system-news-list-detail-owner-skeleton-precheck.md)
- [News List Detail Component Precheck](../design/2026-07-07-wow-ui-system-news-list-detail-component-precheck.md)
- [Implementation Permit Coverage Matrix](../design/2026-07-07-wow-ui-system-implementation-permit-coverage-matrix.md)
- [Route Smoke And Runtime Verification Plan](../design/2026-07-07-wow-ui-system-route-smoke-plan.md)
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-target-lock-decision-and-news-list-detail-activation-packet/manifest.json`

## Purpose

The project is ready to ask for a target-lock decision, but it must not jump straight from readiness review to page edits. This packet gives the post-confirmation execution path:

1. Record the user's target-lock decision.
2. Convert exactly one draft permit into an active permit.
3. Integrate only that surface under the active permit.
4. Verify with source tests, browser/component evidence, real mini-program screenshots and route smoke.

## Trigger

This packet may be used only after one of these explicit user decisions:

- "确认 `A-Cockpit + B-Ledger + C-Captain` 为 target lock"
- "按 readiness review 的推荐方向锁定"
- a written modification that clearly replaces or amends the recommended target

Ambiguous approval, silence, test pass, browser screenshot pass, or Codex confidence is not enough.

## Step 1: Target-Locked Decision Record

After explicit user confirmation, create a new decision record:

- Planned file: `docs/design/2026-07-07-wow-ui-system-target-locked-decision.md`
- Planned artifact: `artifacts/ui-system-rebuild/20260707-target-locked-decision/manifest.json`
- Planned status: `target_locked`

The decision record must contain:

- confirmed target name or the user's written modification;
- source link to the exact user-confirmed turn or quoted decision text;
- surfaces included in the lock;
- foundation and surface owner rules;
- asset production/quarantine/source-map rules;
- route smoke rules;
- explicit non-promotion boundary: target lock is not implementation, runtime verification or final acceptance.

## Step 2: First Active Permit

Recommended first active permit:

`news_list_detail`

Planned active permit file:

- `docs/plans/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit.md`

Planned active permit artifact:

- `artifacts/ui-system-rebuild/20260707-news-list-detail-active-permit/manifest.json`

Template and preflight:

- [News List Detail Active Implementation Permit Template](2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit-template.md)
- `node scripts/ui-system-active-permit-preflight.js --surface news_list_detail --require-active-permit --json`

Why this surface first:

- `ArticleListBoard` and `ArticleReader` already exist as owner skeletons.
- Their fixture matrix exists.
- Their surface component precheck exists.
- The component precheck has 3 viewport screenshots, 7 crops, failures `0`, warnings `0`, horizontal overflow `0`.
- The surface is bounded and has strict source-translation, fallback and source-copy rules.

## Active Permit Scope

The active permit may allow only these files:

- `pages/news/list.wxml`
- `pages/news/list.wxss`
- `pages/news/list.js`
- `pages/news/list.json`
- `pages/news/detail.wxml`
- `pages/news/detail.wxss`
- `pages/news/detail.js`
- `pages/news/detail.json`
- `pages/news/news-api.js` only for stricter UI-facing read-model shaping or stricter validation
- `components/article-list-board/*`
- `components/article-reader/*`
- targeted foundation component fixes only if they preserve owner contracts
- targeted tests for news list/detail and UI-system evidence
- `artifacts/ui-system-rebuild/*news-list-detail*` runtime evidence

The active permit must continue to forbid:

- `app.json`, tabBar, `project.config.json`, appid or route registration changes;
- backend API, collector, translator, moderation gate or database schema changes;
- unrelated surfaces such as news home, builds, workbench, talent, gear, SimC, Chickenbro, tasks or profile;
- page-private article row, body block, source proof, status, button, warning or material geometry after component integration;
- fake read counts, fake source logo, fake official badge, fake publication date, fake hotness, fake manual refresh success;
- hidden fallback/incomplete state;
- raw backend payload, raw collector metadata, raw translator JSON, raw LLM prompt/output, admin fields, token, database id or internal job id.

## Implementation Contract

The page layer may:

- pass validated list/detail data to `ArticleListBoard` and `ArticleReader`;
- bind route/query state;
- handle `openarticle` and `copysource` events;
- call existing `requestArticleList()` and `requestArticleDetail()`;
- call existing analytics and clipboard APIs.

The page layer may not:

- restyle component internals to fix geometry;
- split source proof or fallback visuals across page-private classes;
- convert fallback payloads into verified article states;
- invent article visuals, official marks or source icons;
- weaken `news-api.js` readiness gates.

## Required Pre-Integration Checks

Before page integration under the active permit:

- confirm `target_locked` decision record exists;
- confirm active `news_list_detail` permit exists;
- confirm `ArticleListBoard` and `ArticleReader` source files parse;
- rerun the `news_list_detail` component precheck;
- confirm `devtoolsTouched=false` for pre-integration evidence.

## Required Post-Integration Evidence

After page integration:

- Node tests for news page style and UI-system evidence;
- browser/component precheck for `ArticleListBoard` and `ArticleReader`;
- real WeChat mini-program screenshots after `captureSafe=true`;
- screenshots for official list, metric list, list fallback, ready detail, missing-id detail, not-found detail, fallback detail, copy-source action and back-to-list;
- component crops for list header, article row, source proof, body blocks, source footer and copy action;
- target vs implementation overlay/red-zone comparison;
- scorecard that fails on fake source, hidden fallback, raw payload exposure, body overflow, source URL overflow and page-private article geometry;
- route smoke manifest for all `news_list_detail` scenes;
- DevTools action ledger.

Required `news_list_detail` route smoke scene ids:

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

## Stop Conditions

Stop before page edits if:

- the target lock is absent or contested;
- the active permit does not exist;
- the design requires fake article imagery or fake official/source marks;
- a backend/article/translator contract change is required;
- component owner geometry is insufficient and would require page-private layout fixes;
- DevTools is not capture-safe and runtime evidence is required.

## Non-Promotion Rule

This packet can only prove `activation_packet_draft`. It cannot prove:

- `target_locked`;
- `active_implementation_permit`;
- `page_integration`;
- `runtime_verified`;
- `final_accepted`.
