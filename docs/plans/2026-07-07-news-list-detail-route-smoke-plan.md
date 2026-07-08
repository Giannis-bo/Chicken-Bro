# News List Detail Route Smoke Plan

Status: `route_smoke_plan_ready`

Date: 2026-07-07

This plan scopes route smoke to the active `news_list_detail` permit. It does not run WeChat Developer Tools and does not claim runtime verification.

## Scope

Routes:

- `/pages/news/list`
- `/pages/news/detail`

Active permit:

- `docs/plans/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit.md`

## Scenes

| Scene | Route | Required Check |
| --- | --- | --- |
| `news_list_metric_updates` | `/pages/news/list?type=metric&key=updates` | list loads through `ArticleListBoard`; no page-private geometry |
| `news_list_loading` | `/pages/news/list` | skeleton state visible |
| `news_list_empty` | `/pages/news/list` | empty state visible without fake content |
| `news_list_fallback` | `/pages/news/list` | fallback/source_reference state visible |
| `news_list_open_detail` | `/pages/news/list` -> `/pages/news/detail?id=...` | article id preserved |
| `news_detail_first` | `/pages/news/detail?id=...` | `ArticleReader` renders headline/body/source |
| `news_detail_missing_id` | `/pages/news/detail` | missing id blocked state visible |
| `news_detail_not_found` | `/pages/news/detail?id=missing` | not-found state visible |
| `news_detail_fallback` | `/pages/news/detail?id=...` | fallback/source_reference evidence visible |
| `news_detail_copy_source` | `/pages/news/detail?id=...` | copy action uses `article.sourceUrl` |
| `news_detail_back_to_list` | detail -> list | route return works without tab/app reset |

## Screenshot Requirement

When DevTools capture is safe, collect compact / standard / large screenshots for:

- list ready;
- list fallback;
- detail ready;
- detail missing id;
- detail fallback;
- copy-source interaction after tap.

Each screenshot set should include:

- full-page screenshot;
- `ArticleListBoard` or `ArticleReader` component crop;
- overflow check;
- route action log;
- DevTools action ledger.

## Current State

- `target_locked=true`
- `activeImplementationPermit=true`
- `pageAdoptionReady=true` for `news_list_detail`
- low-disturbance DevTools health check has run without `open`, `close`, `login`, `clear cache`, project switch, navigation, or screenshot RPC
- `captureSafe=false`
- blocker: current visible WeChat DevTools instance does not expose a usable miniprogram-automator runtime endpoint
- `runtimeVerified=false`
- `finalAccepted=false`

Screenshots remain pending. The next safe step is to confirm or enable the active project's automator runtime endpoint and rerun capture with an explicit `WECHAT_AUTOMATOR_PORT`; do not restart, clear cache, switch appid/project, or run login/logout automation to force capture.

Evidence:

- `artifacts/ui-system-rebuild/runtime-health/devtools-health-1783439727658.json`
- `artifacts/ui-system-rebuild/20260707-news-list-detail-runtime-verification-status/manifest.json`

Runtime preflights remain intentionally failing:

- `node scripts/ui-system-route-smoke-execution-preflight.js --require-execution --json` -> `route_smoke_execution_missing`, exit `11`
- `node scripts/ui-system-devtools-action-ledger-preflight.js --require-ledger --json` -> `devtools_action_ledger_missing`, exit `9`
- `node scripts/ui-system-visual-acceptance-preflight.js --require-scorecard --json` -> `visual_acceptance_scorecard_missing`, exit `13`
