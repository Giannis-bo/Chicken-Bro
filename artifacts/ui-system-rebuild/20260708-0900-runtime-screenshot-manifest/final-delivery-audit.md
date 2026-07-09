# 09:00 UI Rescue Runtime Status

Status: `runtime_recapture_complete_auto_14_screenshots_14_pass_final_accepted`

Current truth:

- Static route/design guardrails pass.
- Latest read-only endpoint probe returned `automator_endpoint_probe_found_ready_endpoint`.
- Current usable automator endpoint is `ws://127.0.0.1:9854`.
- 2026-07-09 follow-up: plain current-project `cli auto --project /Users/boyuan/Documents/wow_mini_program --port 30412` succeeded but did not expose a ready endpoint. After discovering the hidden local DevTools CLI option, `cli auto --project /Users/boyuan/Documents/wow_mini_program --port 30412 --auto-port 9854 --trust-project --lang zh` exposed a ready endpoint and the probe recommended `9854`.
- After the user manually clicked Compile, the supplied `pages/news/news` screenshot was saved as `page-captures/news_news_manual_20260709_after_compile.png` (`682x1458`).
- Manual visual assessment for that one screenshot: title, command card, channel dock, ranked feed, and custom tabBar are visible; no obvious white screen, capsule overlap, horizontal overflow, or bottom tabBar text loss.
- Automated `pages/news/news` proof passed: `switchTab('/pages/news/news')` returned `switchTab:ok`, `App.getCurrentPage.path` matched `pages/news/news`, and `App.captureScreenshot` wrote `page-captures/news_news_auto_20260709T031806Z.png` (`860x1864`).
- Automated `pages/news/list` proof passed: `navigateTo('/pages/news/list')` returned `navigateTo:ok`, `App.getCurrentPage.path` matched `pages/news/list`, and `App.captureScreenshot` wrote `page-captures/news_list_auto_20260709T053302Z.png` (`860x1864`).
- Automated `pages/news/detail` proof passed: `navigateTo('/pages/news/detail?id=...')` returned `navigateTo:ok`, `App.getCurrentPage.path` matched `pages/news/detail`, and `App.captureScreenshot` wrote `page-captures/news_detail_auto_20260709T053334Z.png` (`860x1864`).
- Automated `pages/builds/builds` proof passed: `switchTab('/pages/builds/builds')` returned `switchTab:ok`, `App.getCurrentPage.path` matched `pages/builds/builds`, and `App.captureScreenshot` wrote `page-captures/builds_builds_auto_20260709T051856Z.png` (`860x1864`).
- Automated `pages/builds/intel` proof passed: `navigateTo('/pages/builds/intel')` returned `navigateTo:ok`, `App.getCurrentPage.path` matched `pages/builds/intel`, and `App.captureScreenshot` wrote `page-captures/builds_intel_auto_20260709T053348Z.png` (`860x1864`).
- Automated `pages/builds/workbench` proof passed: `navigateTo('/pages/builds/workbench?spec=...')` returned `navigateTo:ok`, `App.getCurrentPage.path` matched `pages/builds/workbench`, and `App.captureScreenshot` wrote `page-captures/builds_workbench_auto_20260709T051629Z.png` (`860x1864`).
- Automated `pages/builds/talent-simulator` proof passed: `navigateTo('/pages/builds/talent-simulator')` returned `navigateTo:ok`, `App.getCurrentPage.path` matched `pages/builds/talent-simulator`, and `App.captureScreenshot` wrote `page-captures/builds_talent-simulator_auto_20260709T052151Z.png` (`860x1864`).
- `pages/builds/detail` automated proof passed after replacing the sticky action bar with non-overlapping document-flow controls: `navigateTo:ok`, `App.getCurrentPage.path=pages/builds/detail`, and `App.captureScreenshot` wrote `page-captures/builds_detail_auto_20260709T060642Z.png` (`860x1864`).
- Automated `pages/simulator/simulator` proof passed: `switchTab('/pages/simulator/simulator')` returned `switchTab:ok`, `App.getCurrentPage.path` matched `pages/simulator/simulator`, and `App.captureScreenshot` wrote `page-captures/simulator_simulator_auto_20260709T052530Z.png` (`860x1864`).
- Automated `pages/simulator/simc` proof passed: `navigateTo('/pages/simulator/simc')` returned `navigateTo:ok`, `App.getCurrentPage.path` matched `pages/simulator/simc`, and `App.captureScreenshot` wrote `page-captures/simulator_simc_auto_20260709T052916Z.png` (`860x1864`).
- Automated `pages/simulator/chickenbro` proof passed: `navigateTo('/pages/simulator/chickenbro')` returned `navigateTo:ok`, `App.getCurrentPage.path` matched `pages/simulator/chickenbro`, and `App.captureScreenshot` wrote `page-captures/simulator_chickenbro_auto_20260709T053404Z.png` (`860x1864`).
- Automated `pages/simulator/tasks` proof passed: `navigateTo('/pages/simulator/tasks')` returned `navigateTo:ok`, `App.getCurrentPage.path` matched `pages/simulator/tasks`, and `App.captureScreenshot` wrote `page-captures/simulator_tasks_auto_20260709T053422Z.png` (`860x1864`).
- `pages/simulator/task-detail` automated proof passed: `navigateTo:ok`, `App.getCurrentPage.path=pages/simulator/task-detail`, and `App.captureScreenshot` wrote `page-captures/simulator_task-detail_auto_20260709T060703Z.png` (`860x1864`), showing the expected direct-open empty state.
- Automated `pages/profile/profile` proof passed: `switchTab('/pages/profile/profile')` returned `switchTab:ok`, `App.getCurrentPage.path` matched `pages/profile/profile`, and `App.captureScreenshot` wrote `page-captures/profile_profile_auto_20260709T053114Z.png` (`860x1864`).
- All 14 registered routes have current route evidence. All 14 pages have current screenshots and all 14 visually pass. Runtime proof is complete and accepted as the current baseline; future UI adjustments are separate requests.
- News channel dock source no longer carries pass36 generated tab icon URLs; custom tabBar now has centered glyph fallback when icon PNGs fail; talent simulator no longer puts a 100vh scroll region below the custom navigation bar; Workbench verdict no longer uses shield/atomic fallback.
- No forbidden DevTools lifecycle actions were used.
- Existing screenshot files are historical only after source changes.

## 14 Page Matrix

| Tier | Page | Current Status | Required Next Evidence |
| --- | --- | --- | --- |
| P0 | `pages/news/news` | pass: automated route + screenshot proof, visual first viewport passes | optional repeat on another device size for future UI iteration |
| P1 | `pages/news/list` | pass: automated route + screenshot proof, visual first viewport passes | optional repeat on another device size for future UI iteration |
| P1 | `pages/news/detail` | pass: automated route + screenshot proof, visual first viewport passes | optional repeat on another device size for future UI iteration |
| P0 | `pages/builds/builds` | pass: automated route + screenshot proof, visual first viewport passes | optional repeat on another device size for future UI iteration |
| P0 | `pages/builds/workbench` | pass: automated route + screenshot proof, visual first viewport passes | optional repeat on another device size for future UI iteration |
| P2 | `pages/builds/intel` | pass: automated route + screenshot proof, visual first viewport passes | optional repeat on another device size for future UI iteration |
| P0 | `pages/builds/talent-simulator` | pass: automated route + screenshot proof, visual first viewport passes | optional repeat on another device size for future UI iteration |
| P0 | `pages/builds/detail` | pass: automated route+screenshot proof exists; visual first viewport passes after non-overlapping action layout fix | optional repeat on another device size |
| P0 | `pages/simulator/simulator` | pass: automated route + screenshot proof, visual first viewport passes | optional repeat on another device size for future UI iteration |
| P0 | `pages/simulator/simc` | pass: automated route + screenshot proof, visual first viewport passes | optional repeat on another device size for future UI iteration |
| P1 | `pages/simulator/chickenbro` | pass: automated route + screenshot proof, visual first viewport passes | optional repeat on another device size for future UI iteration |
| P1 | `pages/simulator/tasks` | pass: automated route + screenshot proof, visual first viewport passes | optional repeat on another device size for future UI iteration |
| P1 | `pages/simulator/task-detail` | pass: automated route+screenshot proof exists; direct-open empty state is readable | optional valid task-id detail proof |
| P0 | `pages/profile/profile` | pass: automated route + screenshot proof, visual first viewport passes | optional repeat on another device size for future UI iteration |

## Safe Next Step

1. Keep this accepted 14-page runtime evidence as the baseline for future UI requests.
2. Treat future UI changes as separate requirements with their own plan, screenshot matrix, and verification gate.
3. Prepare commit or handoff package for the current accepted baseline if requested.
