# 2026-07-09 Docs / Implementation Current Truth Review

## Status

`已完成 / 当前 UI 基线已验收`

本文件记录 2026-07-09 对近期大量 PR 合入后的本地文档/实现对账结果。它不替代 `docs/roadmap.md`，也不重写历史 plan；它的作用是给下一步推进提供一张当前事实表。

2026-07-09 14:29 CST 更新：本轮 UI rescue 已补齐 14 个 `app.json` 页面当前自动 route+screenshot 证据，`manifest.json` / `final-delivery-audit.json` 状态为 `runtime_recapture_complete_auto_14_screenshots_14_pass_final_accepted`，`runtimeVerified=true`、`finalAccepted=true`、`riskCount=0`。用户已确认当前 UI 基线可先收口，后续视觉/布局预期调整另开需求。

本轮只做本地仓库、源码、测试和当前 DevTools 低扰动预检；没有 SSH 云端、没有远端 DB 查询、没有下载、没有安装依赖。

## Read Order Used

1. `docs/roadmap.md`
2. `docs/plans/2026-07-08-codex-goal-mode-ui-delivery-handoff.md`
3. `docs/plans/2026-07-08-ui-goal-mode-entry-contract.md`
4. `docs/plans/2026-07-08-current-ui-delivery-source-of-truth.md`
5. `docs/gear-simulation-full-chain-runbook.md`
6. `app.json`
7. `artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/*`
8. Current source and targeted tests

## Current Truth Matrix

| Area | Current implementation status | Documentation status | Classification | Required next move |
| --- | --- | --- | --- | --- |
| Gear public import templates | All-spec public read model is `public observed-only`: only active `raiderio_observed_profile` can reach public `communityTemplates`; public `baselineTemplates` stays empty. | Roadmap top and newer runbook sections match this; older runbook sections still described `season_recommendation` as public 40/40 baseline. | Implemented, with stale docs now marked superseded in this pass. | Keep public observed-only. Do not reopen `recommended_bis` or `season_recommendation` without new SimC/pairwise/anchor/user acceptance gate. |
| Gear destructive cleanup | Current destructive cleanup code remains pilot-safe for `shaman:elemental`; all-spec hiding is handled by read-model filtering, not by deleting every legacy/recommended row. | Previously implicit; now documented in the runbook current fact table. | Implemented as safe pilot scope; broader cleanup is intentionally not done. | Define per-spec retain/delete policy before any full-table cleanup. |
| Gear legality authority | Source map v1 exists and exposes official/simc/observed/manual_override. Current authority remains `partial`: official/simc missing, manual override active, observed supporting only. | Roadmap/runbook are mostly aligned. | Implemented partial, not verified authority. | Add official/SimC primary source map before increasing `verifiedSpecs`. |
| UI delivery | Current runtime proof is complete for this delivery baseline: 14/14 `app.json` pages have fresh automated route+screenshot records, final audit accepted, risk/fail 0. | Current UI source-of-truth and runtime screenshot manifests are aligned; older pass36/pass37/UI rebuild artifacts are historical. | Runtime verified / accepted baseline. | Freeze this round as accepted. Treat future UI design/visual changes as separate requirements. |
| UI evidence harness | `automator-endpoint-probe.js` is self-contained, `auto-route-screenshot.js` produces route/action/screenshot records, and summary scripts now read the current page manifest before falling back to historical filenames. | Artifact manifests, final audit, delivery summary, DevTools ledger, and tests are synchronized to the accepted baseline. | Evidence harness repaired for current local DevTools flow. | Keep `--auto-port 9854` and current scripts as the evidence path for future UI changes; do not promote stale screenshots. |
| Chickenbro | Frontend chat shell and backend `/api/chickenbro/*` sessions/messages/jobs/profile flow exist with bounded evidence and deterministic fallback. | Roadmap has both completed v0.2 notes and broader ongoing evidence-coach direction. | Core implemented; product depth and online validation still ongoing. | Treat v0 skeleton as shipped, continue evidence quality/UX validation separately. |
| PG-only runtime | Runtime guardrails exist for `WOW_DATABASE_RUNTIME=postgres_only`; local development can still default to SQLite without env. | `docs/database-architecture.md` states PG-only strongly; roadmap still tracks formal production migration/cutover as ongoing. | Runtime boundary implemented; broader migration/launch status wording is mixed. | Split docs into "runtime guardrail implemented" vs "formal production migration/cutover still tracked". |
| Data health follow-up | Code/tests cover follow-up tasks and SimC runtime update orchestration. | Roadmap claims deployed; this pass did not re-SSH or re-smoke cloud. | Locally implemented; live status not refreshed in this pass. | Only claim live-current after fresh server/systemd/API evidence. |
| 12.1 cutover / CN terminology | Design docs and roadmap entries exist. | Docs capture direction but not implementation closure. | Planned / pending implementation. | Keep as next control-plane work, not as already shipped behavior. |

## UI Evidence Precheck

Final current implication: all 14 `app.json` routes now have current automated route+screenshot evidence. The delivery baseline is accepted as of `2026-07-09T06:29:20Z` / `2026-07-09 14:29 CST`; future UI adjustments should start from a new request instead of mutating this accepted rescue round.

This pass restored and reran the read-only endpoint probe. A follow-up current-project automation attempt was also performed after the user asked to close the loop:

- Command: `node artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/automator-endpoint-probe.js`
- Result: `automator_endpoint_probe_no_ready_endpoint`
- Checked ports: `8`
- Recommended endpoint: `null`
- Forbidden DevTools actions used: `[]`
- Navigation used: `false`
- Screenshot used: `false`
- `cli islogin`: `login=true`, IDE server `30412`
- `cli auto --project /Users/boyuan/Documents/wow_mini_program --port 30412`: succeeded with AppID `wx17543b6fc4305479`
- Follow-up endpoint probe after `cli auto`: still `automator_endpoint_probe_no_ready_endpoint`
- User follow-up: manually clicked Compile in the already-open DevTools project and supplied a `pages/news/news` screenshot.
- Manual screenshot saved: `artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/page-captures/news_news_manual_20260709_after_compile.png` (`682x1458`)
- Manual visual result for that single page: title, command card, channel dock, ranked feed, and custom tabBar are visible; no obvious white screen, capsule overlap, horizontal overflow, or bottom tabBar text loss.
- Endpoint probe after manual compile: still `automator_endpoint_probe_no_ready_endpoint`; attempted Tool.getInfo against `9854` plus `7` current listening ports; recommended endpoint `null`.
- Hidden local DevTools CLI option discovered from `/Applications/wechatwebdevtools.app/Contents/Resources/package.nw/js/common/cli/index.js`: `--auto-port`.
- Command: `/Applications/wechatwebdevtools.app/Contents/MacOS/cli auto --project /Users/boyuan/Documents/wow_mini_program --port 30412 --auto-port 9854 --trust-project --lang zh`
- Result: `auto` succeeded with AppID `wx17543b6fc4305479`; `9854` became a listening `wechatweb` port.
- Endpoint probe after explicit `--auto-port 9854`: `automator_endpoint_probe_found_ready_endpoint`; recommended endpoint `9854`.
- Automated `pages/news/news` proof: `WECHAT_AUTOMATOR_PORT=9854 WOW_0900_PROOF_PAGE=pages/news/news node artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/auto-route-screenshot.js`
- Automated proof result: `switchTab:ok`, `App.getCurrentPage.path=pages/news/news`, `App.captureScreenshot` wrote `page-captures/news_news_auto_20260709T031806Z.png` (`860x1864`).
- Follow-up route matrix result: `pages/news/news`, `pages/builds/workbench`, `pages/builds/builds`, `pages/builds/talent-simulator`, `pages/builds/detail`, `pages/simulator/simulator`, `pages/simulator/simc`, `pages/profile/profile`, `pages/news/list`, `pages/news/detail`, `pages/builds/intel`, `pages/simulator/chickenbro`, `pages/simulator/tasks`, and `pages/simulator/task-detail` all have current automated screenshot proof.
- Final accepted proof state: `totalPages=14`, `currentRuntimeScreenshotCount=14`, `currentRuntimePassCount=14`, `riskCount=0`, `failCount=0`, `finalAccepted=true`.

## Current Documentation Corrections Made

- `docs/gear-simulation-full-chain-runbook.md` now states the current public contract near the top: public import is observed-only, while `recommended_bis`, `season_recommendation`, `default_template`, `simc_preset`, and `baseline_blocked` are internal/legacy unless a future gate reopens them.
- The old `season_recommendation` public 40/40 baseline section is now explicitly marked as historical/internal and superseded for public entry.
- The runbook now explicitly separates display-layer all-spec filtering from destructive DB cleanup, which remains pilot-scoped.
- `artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/automator-endpoint-probe.js` no longer requires the missing historical `ui-v2-1-strict-restoration` helper.

## Verification Run

- `git diff --check`: pass.
- `node --check artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/automator-endpoint-probe.js`: pass.
- `node --check artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/auto-route-screenshot.js`: pass.
- `node artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/automator-endpoint-probe.js`: executable and read-only; after explicit `--auto-port 9854`, exited `0` with `automator_endpoint_probe_found_ready_endpoint`.
- `WECHAT_AUTOMATOR_PORT=9854 WOW_0900_PROOF_PAGE=<route> node artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/auto-route-screenshot.js`: produced current proof for all 14 app routes.
- Accepted JSON consistency check: `accepted_json_consistency_ok_14_pages_14_screenshots_0_risk`.
- JSON parse check for `manifest.json`, `page-captures/manifest.json`, `final-delivery-audit.json`, `devtools-action-ledger.json`, and `automator-endpoint-probe.json`: pass.
- `node --test tests/ui-system-rebuild-goal.test.js tests/ui-v2-1-strict-cut-contract.test.js tests/deploy-script.test.js tests/builds-page.test.js`: `137` pass during targeted UI verification.
- `node --test tests/*.test.js`: `340` pass during final full local verification.

Python tests were not rerun in this pass because no Python files changed.

## Next Execution Order

1. Commit this accepted baseline as a local delivery branch; do not push unless explicitly requested.
2. Treat future UI visual/layout changes as a new requirement with a fresh Harness contract and runtime proof matrix.
3. Move the optimization plan to Phase 2: Harness evidence packet standardization.
4. Then prepare Phase 3 backend owner map and characterization tests before any hotspot file split.
5. Separately clean up the PG-only migration wording so docs distinguish implemented runtime guardrails from remaining production cutover/launch work.
6. Keep `recommended_bis_v1` and 12.1 control-plane work separate from UI evidence recovery.
