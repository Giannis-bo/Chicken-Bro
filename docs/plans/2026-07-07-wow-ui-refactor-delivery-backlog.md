# WOW UI Refactor Delivery Backlog

Status: `delivery_backlog_defined`

Date: 2026-07-07

This backlog belongs to the delivery convergence goal. It prevents the current `news_list_detail` evidence from being misread as all-surface acceptance.

## Delivered In This Permit

| Surface | Status | Evidence |
| --- | --- | --- |
| `news_list_detail` | `page_adoption_ready` | `node scripts/ui-system-page-adoption-preflight.js --surface news_list_detail --require-adoption --json` |
| native tabBar icons | `implemented` | `app.json` tabBar `iconPath` / `selectedIconPath`, `assets/tabbar/*.png` |
| target lock | `target_locked` | `docs/design/2026-07-07-wow-ui-system-target-locked-decision.md` |
| active permit | `active_implementation_permit` | `docs/plans/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit.md` |

## Remaining Surfaces

| Surface | Classification | Reason | Next Permit Candidate |
| --- | --- | --- | --- |
| `news_home` | `next_permit_candidate` | Still has pass37/page-private geometry and generated material references; not selected in this delivery pass. | Yes |
| `builds_tab` | `risk_requires_design_lock` | Large surface with class/spec switching and current private geometry. | Yes, after news_home or workbench decision |
| `current_spec_workbench` | `risk_requires_design_lock` | Previous failures centered on status shield, layout hierarchy and asset slicing; needs stricter component implementation. | Yes |
| `talent_simulator` | `backlog` | Functional data surface; needs ownerized `TalentTreeCanvas` pass later. | Later |
| `gear_detail` | `backlog` | High data density and configuration sheets; avoid mixing with news delivery. | Later |
| `simc` | `backlog` | Requires evidence and submit-state ownerization. | Later |
| `chickenbro` | `risk_requires_design_lock` | User called out chat UI disorder; must be a separate first-class surface permit. | Yes |
| `tasks` | `backlog` | Needs `TaskQueueBoard` / `TaskResultReport` adoption. | Later |
| `profile_templates` | `backlog` | Needs identity/template owner adoption. | Later |
| `pve` | `backlog` | Not part of active tabBar route and not part of this single-surface permit. | Later |

## Route Smoke Boundary

Only `news_list_detail` scenes are planned in this delivery package:

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

`news_home_top` and `news_home_scrolled` remain outside this permit even though the app's tabBar points to `pages/news/news`.

## Non-Promotion Boundary

This backlog proves scope control only. It does not prove:

- runtime screenshots;
- route smoke execution;
- visual acceptance;
- all-surface page adoption;
- final acceptance.
