# 09:00 UI Rescue Visual Review Ledger

Status: `post_source_change_recapture_required`

> 2026-07-08 update: this visual ledger reviewed screenshots captured before the latest source/test contract changes. It remains useful as historical route evidence, but it cannot prove the current worktree. Any current delivery claim must recapture the affected pages in the real WeChat mini program, or mark them `risk`.

> Latest runtime note: the post-change single-page recapture target was `pages/builds/workbench`. It used the existing automator endpoint, did not use forbidden DevTools lifecycle actions, and failed twice with `capture pages/builds/workbench timed out after 10000ms`, including one retry after deferring non-essential material images. Treat workbench as `risk_capture_timeout` until a fresh screenshot succeeds.

Reviewed evidence:

- `artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/page-captures/*.png`
- `artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/single-page-screenshot-summary.json`
- `artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/aggregate-page-visual-manifest.json`

This ledger is a visual rescue review, not a full UI-system rebuild acceptance. It checks the 09:00 rescue bar: openable pages, no white screen, no obvious P0 layout collapse, visible tabBar labels where applicable, readable content, and stable evidence records.

## P0 Pages

| Page | Screenshot | Rescue status | Notes |
| --- | --- | --- | --- |
| `pages/news/news` | `page-captures/news_news.png` | `pass_for_0900_rescue` | Carousel, channel dock, ranked feed, and custom tabBar are visible. Channel dock now uses centered text glyphs rather than offset generated icon art. |
| `pages/builds/builds` | `page-captures/builds_builds.png` | `pass_for_0900_rescue_with_recapture_risk` | Workbench entry and workflow rows are readable; tabBar labels are visible. After review, page bottom reserve was increased in `pages/builds/builds.wxss` to reduce fixed tabBar overlap; needs single-page recapture when automator is responsive. |
| `pages/builds/workbench` | `page-captures/builds_workbench.png` | `pass_for_0900_rescue_with_polish_risk` | Blocked conclusion, main action, workflow cards, and evidence area are readable. Shield/exclamation no longer overlays text. Density remains high and should be redesigned after rescue. |
| `pages/builds/talent-simulator` | `page-captures/builds_talent-simulator.png` | `pass_for_0900_rescue_with_polish_risk` | Talent tree, tabs, fixed bottom actions, and selected spec are visible. Deep tree is clipped by the fixed action bar by design; richer interaction polish is post-delivery. |
| `pages/builds/detail` | `page-captures/builds_detail.png` | `pass_for_0900_rescue` | Gear slot grid is readable with no white screen, capsule overlap, or horizontal overflow visible in the captured viewport. |
| `pages/simulator/simulator` | `page-captures/simulator_simulator.png` | `pass_for_0900_rescue_with_polish_risk` | Chickenbro/intelligent-analysis identity, welcome message, prompts, evidence boundary, input, send action, and tabBar are visible. Large empty conversation lane is acceptable for rescue but remains product polish. |
| `pages/simulator/simc` | `page-captures/simulator_simc.png` | `pass_for_0900_rescue` | SimC setup, templates, presets, buffs, summary, and fixed actions are visible; actions are not hidden by a custom tabBar on this non-tab page. |
| `pages/profile/profile` | `page-captures/profile_profile.png` | `pass_for_0900_rescue` | Identity panel, template library, settings, and custom tabBar are readable; no split top identity failure visible in the current screenshot. |

## P1/P2 Pages

| Page | Screenshot | Rescue status | Notes |
| --- | --- | --- | --- |
| `pages/news/list` | `page-captures/news_list.png` | `pass_readable_with_route_warning` | List content is readable; route callback warning remains. |
| `pages/news/detail` | `page-captures/news_detail.png` | `pass_readable_with_route_warning` | Article body and source proof are readable; route callback warning remains. |
| `pages/simulator/chickenbro` | `page-captures/simulator_chickenbro.png` | `pass_readable_with_route_warning` | Dedicated Chickenbro page is readable and not an empty shell; route callback warning remains. |
| `pages/simulator/tasks` | `page-captures/simulator_tasks.png` | `pass_readable_with_route_warning` | Empty task state and actions are readable; route callback warning remains. |
| `pages/simulator/task-detail` | `page-captures/simulator_task-detail.png` | `pass_readable_with_route_warning` | Direct-open no-task state is readable; route callback warning remains. |
| `pages/builds/intel` | `page-captures/builds_intel.png` | `pass_no_white_screen_with_route_warning` | P2 page produced a valid screenshot and is not white-screen; route callback warning remains. |

## Remaining Delivery Risks

- Route callback warnings remain on 10 non-tab or secondary routes. They are recorded as route risks when route matches and screenshots are valid.
- Full multi-page serial capture is unsafe and must not be used as final evidence. Use single-page capture only.
- P0 pages are rescue-pass, not full design-system acceptance. Workbench density and talent simulator tree polish need post-09:00 refinement. Builds workflow bottom reserve was increased after screenshot review and should be recaptured when automator is responsive.
- No overlay/red-zone 90% target-image restoration is claimed for this rescue delivery.
- Static tests may still contain stale expectations from older UI architecture and must not be used to roll back runtime-stable rescue UI.

## Historical Delivery Conclusion

For the 09:00 rescue bar, all 14 registered pages have valid screenshot evidence or explicit route-risk notes, P0 pages have no obvious white screen, horizontal overflow, capsule overlap, missing tabBar labels, input drift, or blocked primary action in the reviewed screenshots.

Do not promote this to current final UI-system acceptance. For the current worktree, promote only as `static guardrails pass; real WeChat recapture required`.
