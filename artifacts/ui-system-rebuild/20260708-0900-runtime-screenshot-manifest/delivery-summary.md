# 09:00 UI Rescue Runtime Status

Status: `runtime_recapture_complete_auto_14_screenshots_14_pass_final_accepted`

Current truth:

- Latest read-only endpoint probe after explicit hidden `--auto-port 9854` returned `automator_endpoint_probe_found_ready_endpoint`; current usable endpoint is `ws://127.0.0.1:9854`.
- `pages/news/news` automated proof passed: `switchTab:ok`, `App.getCurrentPage.path=pages/news/news`, and `App.captureScreenshot` wrote `page-captures/news_news_auto_20260709T031806Z.png` (`860x1864`).
- `pages/news/list` automated proof passed: `navigateTo:ok`, `App.getCurrentPage.path=pages/news/list`, and `App.captureScreenshot` wrote `page-captures/news_list_auto_20260709T053302Z.png` (`860x1864`).
- `pages/news/detail` automated proof passed: `navigateTo:ok`, `App.getCurrentPage.path=pages/news/detail`, and `App.captureScreenshot` wrote `page-captures/news_detail_auto_20260709T053334Z.png` (`860x1864`).
- `pages/builds/builds` automated proof passed: `switchTab:ok`, `App.getCurrentPage.path=pages/builds/builds`, and `App.captureScreenshot` wrote `page-captures/builds_builds_auto_20260709T051856Z.png` (`860x1864`).
- `pages/builds/intel` automated proof passed: `navigateTo:ok`, `App.getCurrentPage.path=pages/builds/intel`, and `App.captureScreenshot` wrote `page-captures/builds_intel_auto_20260709T053348Z.png` (`860x1864`).
- `pages/builds/workbench` automated proof passed: `navigateTo:ok`, `App.getCurrentPage.path=pages/builds/workbench`, and `App.captureScreenshot` wrote `page-captures/builds_workbench_auto_20260709T051629Z.png` (`860x1864`).
- `pages/builds/talent-simulator` automated proof passed: `navigateTo:ok`, `App.getCurrentPage.path=pages/builds/talent-simulator`, and `App.captureScreenshot` wrote `page-captures/builds_talent-simulator_auto_20260709T052151Z.png` (`860x1864`).
- `pages/builds/detail` automated proof passed after replacing the sticky action bar with non-overlapping document-flow controls: `navigateTo:ok`, `App.getCurrentPage.path=pages/builds/detail`, and `App.captureScreenshot` wrote `page-captures/builds_detail_auto_20260709T060642Z.png` (`860x1864`).
- `pages/simulator/simulator` automated proof passed: `switchTab:ok`, `App.getCurrentPage.path=pages/simulator/simulator`, and `App.captureScreenshot` wrote `page-captures/simulator_simulator_auto_20260709T052530Z.png` (`860x1864`).
- `pages/simulator/simc` automated proof passed: `navigateTo:ok`, `App.getCurrentPage.path=pages/simulator/simc`, and `App.captureScreenshot` wrote `page-captures/simulator_simc_auto_20260709T052916Z.png` (`860x1864`).
- `pages/simulator/chickenbro` automated proof passed: `navigateTo:ok`, `App.getCurrentPage.path=pages/simulator/chickenbro`, and `App.captureScreenshot` wrote `page-captures/simulator_chickenbro_auto_20260709T053404Z.png` (`860x1864`).
- `pages/simulator/tasks` automated proof passed: `navigateTo:ok`, `App.getCurrentPage.path=pages/simulator/tasks`, and `App.captureScreenshot` wrote `page-captures/simulator_tasks_auto_20260709T053422Z.png` (`860x1864`).
- `pages/simulator/task-detail` automated proof passed: `navigateTo:ok`, `App.getCurrentPage.path=pages/simulator/task-detail`, and `App.captureScreenshot` wrote `page-captures/simulator_task-detail_auto_20260709T060703Z.png` (`860x1864`), showing the expected direct-open empty state.
- `pages/profile/profile` automated proof passed: `switchTab:ok`, `App.getCurrentPage.path=pages/profile/profile`, and `App.captureScreenshot` wrote `page-captures/profile_profile_auto_20260709T053114Z.png` (`860x1864`).
- Static route/design guardrails pass.
- Historical real WeChat screenshots exist for all 14 pages, but they are not current proof after later source changes.
- All 14 registered routes have current route evidence. All 14 pages have current screenshots and all 14 visually pass. Runtime proof is complete and accepted as the current baseline; future UI adjustments are separate requests.
- No forbidden DevTools lifecycle actions were used.
- Existing screenshot files are historical only after source changes.

Latest source-side rescue changes:

- News home channel dock no longer carries pass36 generated tab icon URLs. `综合 / 官方 / 更新 / 活动 / 社区 / 攻略` now render as stable text marks, and ranked fallback no longer has a `visual-glyph-thumb` image branch, so tab switching cannot swap back to offset PNG glyphs.
- Custom tabBar now owns an image failure fallback: if a tab icon PNG fails or selected icon rendering breaks, that item falls back to a centered fixed-size glyph while keeping the label visible.
- Talent simulator root layout now uses a flex full-height shell with a `flex: 1 / height: 0` scroll region instead of putting a `100vh` scroll region below the custom navigation bar.
- Workbench status visual abandoned the shield/atomic-image path after user rejection. It now uses `StatusVisual` layered `shape="auto"`: blocked/error -> triangle with exclamation, ready/source/stale -> circle, partial/loading -> diamond. `workbench-state` no longer emits `statusAtomicUrl`.
- The earlier shield fallback attempt is superseded and must not be restored for the workbench verdict. Current workbench verdict status uses state-enumerated basic shapes instead of shield assets.
- `tests/builds-page.test.js` locks the status fallback contract.
- `tests/news-page-style.test.js` now forbids the old pass36 channel PNG path and protects the current `178rpx` tabBar avoidance rhythm instead of pulling the page back to the older oversized `218rpx` spacing.
- `tests/navigation-bar.test.js` now protects the custom tabBar `binderror -> iconFailures -> glyph fallback` path.

Latest static verification:

- `node --test tests/builds-page.test.js tests/navigation-bar.test.js tests/news-page-style.test.js tests/simulator-page.test.js tests/ui-style-guide-implementation.test.js` -> `178/178` pass.
- `node --test tests/navigation-bar.test.js` -> `11/11` pass.
- `node --test tests/navigation-bar.test.js tests/news-page-style.test.js tests/builds-page.test.js tests/talent-simulator-core.test.js tests/simulator-page.test.js tests/ui-style-guide-implementation.test.js` -> `193/193` pass.
- JSON parse check passed for `devtools-action-ledger.json`, `manifest.json`, `final-delivery-audit.json`, and `automator-endpoint-probe.json`.
- `git diff --check` passed for the current touched rescue files.

## 14 Page Matrix

| Tier | Page | Current Status | Required Next Evidence |
| --- | --- | --- | --- |
| P0 | `pages/news/news` | pass: automated route+screenshot proof exists | optional repeat on another device size |
| P1 | `pages/news/list` | pass: automated route+screenshot proof exists; visual first viewport passes | optional repeat on another device size |
| P1 | `pages/news/detail` | pass: automated route+screenshot proof exists; visual first viewport passes | optional repeat on another device size |
| P0 | `pages/builds/builds` | pass: automated route+screenshot proof exists; visual first viewport passes | optional repeat on another device size |
| P0 | `pages/builds/workbench` | pass: automated route+screenshot proof exists; visual first viewport passes | optional repeat on another device size |
| P2 | `pages/builds/intel` | pass: automated route+screenshot proof exists; visual first viewport passes | optional repeat on another device size |
| P0 | `pages/builds/talent-simulator` | pass: automated route+screenshot proof exists; visual first viewport passes | optional repeat on another device size |
| P0 | `pages/builds/detail` | pass: automated route+screenshot proof exists; visual first viewport passes after non-overlapping action layout fix | optional repeat on another device size |
| P0 | `pages/simulator/simulator` | pass: automated route+screenshot proof exists; visual first viewport passes | optional repeat on another device size |
| P0 | `pages/simulator/simc` | pass: automated route+screenshot proof exists; visual first viewport passes | optional repeat on another device size |
| P1 | `pages/simulator/chickenbro` | pass: automated route+screenshot proof exists; visual first viewport passes | optional repeat on another device size |
| P1 | `pages/simulator/tasks` | pass: automated route+screenshot proof exists; visual first viewport passes | optional repeat on another device size |
| P1 | `pages/simulator/task-detail` | pass: automated route+screenshot proof exists; direct-open empty state is readable | optional valid task-id detail proof |
| P0 | `pages/profile/profile` | pass: automated route+screenshot proof exists; visual first viewport passes | optional repeat on another device size |

## Safe Next Step

1. Keep this accepted 14-page runtime evidence as the baseline for future UI requests.
2. Treat future UI changes as separate requirements with their own plan, screenshot matrix, and verification gate.
3. Prepare commit or handoff package for the current accepted baseline if requested.
