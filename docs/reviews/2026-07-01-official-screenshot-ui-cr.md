# 2026-07-01 Official Screenshot UI CR

## Summary

- Baseline: official WeChat DevTools mini-program screenshots in `artifacts/miniprogram-screenshots/20260630-workbench-redesign/`.
- Capture status: current `manifest.json` is `complete` again after recapturing 14/14 required scenes through the logged-in official WeChat DevTools project.
- Design review adapter: [WoW Mini Program Design Review Adapter](../design/wow-mini-program-design-review-adapter.md).
- Main verdict: the direction is now real-product usable and much better than the earlier imagegen/demo rounds, but the next pass must fix workflow continuity, scene-proof screenshots, and evidence hierarchy before doing more visual polish.

## 2026-07-01 Continuation Status

- Fixed in code: SimC now inherits workbench class/spec/scenario, workbench gear readiness uses one canonical count/blocker model, Chickenbro carries bounded workbench context, raw `scheduled` and long timestamps are localized in the core UI, and the profile page no longer shows fixed `4 / 2 / 12` placeholder account metrics.
- Visual propagation added: tasks and profile now use the same generated non-factual shell/material assets as workbench, news, builds, SimC, and Chickenbro.
- Verification passed: `node --test tests/builds-workbench-state.test.js tests/builds-page.test.js tests/frontend-api-client.test.js`, `node --test tests/simulator-page.test.js tests/news-page-style.test.js tests/ui-style-guide-implementation.test.js tests/profile-auth.test.js`, and `git diff --check`.
- Screenshot acceptance passed: `artifacts/miniprogram-screenshots/20260630-workbench-redesign/manifest.json` reports `complete`, `missingScenes=[]`, and 14 captured records. The recapture used the existing logged-in DevTools instance with `WOW_REUSE_IDE_AUTO=1` and `WOW_CAPTURE_CHILDREN=0`, avoiding per-scene IDE relaunch.

## P0

| Scene | Finding | Evidence | Impact | Fix |
| --- | --- | --- | --- | --- |
| 010 SimC | Workbench context is not inherited by SimC. | [010_simc.png](../../artifacts/miniprogram-screenshots/20260630-workbench-redesign/screenshots/010_simc.png) shows `职业 请选择职业` even though the route is `from=workbench&spec=法师-冰霜`. | Breaks the main path: `ready_to_simulate -> 去 SimC 校验` should land with the same class/spec context, not restart the user at an empty selector. | Parse workbench `spec`/class/spec query in `pages/simulator/simc`, preselect class/spec, filter templates, and keep empty template blockers scoped to that spec. |
| 004/006 Workbench | Gear readiness copy/counts are inconsistent across live and fixture states. | [004_workbench_first_screen.png](../../artifacts/miniprogram-screenshots/20260630-workbench-redesign/screenshots/004_workbench_first_screen.png) says `装备 15/15 槽` while also saying `缺少副手`; [006_workbench_blocked_gear.png](../../artifacts/miniprogram-screenshots/20260630-workbench-redesign/screenshots/006_workbench_blocked_gear.png) says `15/16 槽`. | Weakens the core trust promise. Users cannot tell whether off-hand is optional, missing, or counted differently by two modules. | Make `workbench-state` output one canonical gear count model: selected count, required count, optional off-hand rule, and blocker label must derive from the same source. |
| 002 News Scrolled | The "scrolled" screenshot does not visibly show a scrolled state. | [002_news_home_scrolled.png](../../artifacts/miniprogram-screenshots/20260630-workbench-redesign/screenshots/002_news_home_scrolled.png) is visually the same top-of-page composition as [001_news_home_top.png](../../artifacts/miniprogram-screenshots/20260630-workbench-redesign/screenshots/001_news_home_top.png). | We cannot use this screenshot to evaluate the original concern about down-scroll list hierarchy. | Fix `capture-official.js` to scroll the actual `scroll-view`/content container, then recapture the post-scroll state. |
| 005 Workbench Evidence Expanded | The named evidence-expanded scene does not visibly prove evidence expansion. | [005_workbench_evidence_expanded.png](../../artifacts/miniprogram-screenshots/20260630-workbench-redesign/screenshots/005_workbench_evidence_expanded.png) shows the same first-screen slab as the normal workbench; evidence rows are below the fold. | The acceptance set says evidence was captured, but the image does not let reviewers evaluate coverage, checkedAt, catalogStatus, statSnapshot, or blockers. | For the evidence scene, scroll to the evidence section or move the first expanded evidence rows into the visible capture area. |

## P1

| Scene | Finding | Evidence | Impact | Fix |
| --- | --- | --- | --- | --- |
| 004/005 Workbench | Blocked state is repeated too many times. | Badge says `阻断`, slab says cannot submit, next-step card says missing off-hand, module cards repeat blocked/partial. | The user sees alarm repetition instead of one clear verdict and one clear next action. | Make a single verdict slab own the blocker. Convert the module area into compact status chips or a progress rail. |
| 004/005/007 Workbench | The "ability matrix" still feels like four equal cards, not a workflow. | Talent, gear, SimC, and captain cards use similar card weight and repeated CTA shape. | The product goal is a cockpit; equal cards pull it back toward a feature-entry grid. | Reframe modules as `Inputs -> Validation -> Explain` with one primary action and smaller evidence affordances. |
| 001/002 News | The hero, featured card, and list repeat the same content shape. | News top shows `今日情报台`, a large featured article, then `今日重点` with the same article style. | The page is readable, but not yet an editorial/app-like news product. | Split roles: hero = status summary, featured = one story, list = denser feed with clear source/time/status. |
| 001/002 News | Raw operational language leaks into user UI. | `scheduled` and full timezone timestamps are visible. | Makes the app feel like an internal dashboard rather than a polished player product. | Replace with Chinese user-facing freshness labels such as `定时更新` and short date/time. |
| 003 Builds Tab | The top hero and module grid still carry scaffolding language. | `能力 02`, `深入模块`, repeated `进入查询`, and `旧入口保留` feel implementation-oriented. | The tab is functional but not yet a strong C-end app surface. | Rename around user jobs: `当前专精`, `构筑输入`, `模拟验证`, `队长解释`; remove internal counter labels. |
| 008 Talent Simulator | Selection state is hard to reconcile. | Hero says selected 3 talent nodes, while the visible tree tab says `通用 0/34`; some nodes show selected state. | Advanced users may distrust whether counts represent global selection, current tree, or imported state. | Show total selected and current-tree selected separately, or change the hero copy to avoid contradicting per-tree tabs. |
| 008 Talent Simulator | Fixed bottom action bar covers the lower tree. | The bottom action bar sits on top of tree content. | Tree manipulation can feel cramped and partly obscured. | Add bottom padding equal to action bar height and ensure the last tree row can scroll above it. |
| 012 Chickenbro | Chat entry is honest but too empty and does not carry workbench context. | [012_chickenbro.png](../../artifacts/miniprogram-screenshots/20260630-workbench-redesign/screenshots/012_chickenbro.png) shows a single intro bubble and large blank middle space. | The captain feels disconnected from the workbench state it is supposed to explain. | Pass bounded context from workbench and render small context chips plus 2-3 suggested prompts. |
| 013 Profile | Profile counts look like fixed product counters rather than explained user data. | `4 收藏职业`, `2 关注角色`, `12 订阅词条` appear without source or empty-state explanation. | If these are placeholders/fallbacks, they can reduce data trust. | Tie counts to real local/remote data or mark them as setup shortcuts; avoid unbacked account-like metrics. |

## P2

| Scene | Finding | Evidence | Fix |
| --- | --- | --- | --- |
| 009 Gear Simulator | Page title still says `职业专精查询` while the page is an equipment simulator. | [009_gear_simulator.png](../../artifacts/miniprogram-screenshots/20260630-workbench-redesign/screenshots/009_gear_simulator.png). | Rename nav/hero so the object and task match: `装备模拟` / `冰霜法师装备`. |
| 010 SimC | Some empty-state labels are technically correct but low-emotion. | `尚未保存天赋模板`, `尚未保存装备模板`. | Add concise next action hints after P0 inheritance is fixed. |
| 011 Tasks | Empty state is much better, but the lower half remains mostly dark. | [011_tasks.png](../../artifacts/miniprogram-screenshots/20260630-workbench-redesign/screenshots/011_tasks.png). | Add a compact recent-task policy note or keep the container shorter. |
| 004/005 Workbench | English implementation labels leak into UI. | `checkedAt`, `SimC-ready`, and lower-case `simc` appear in player-facing areas. | Localize or reserve English only for established player terms. |
| 001 News | Article timestamps are too raw. | Full `YYYY-MM-DD 00:00:00+08:00` takes visual weight from headlines. | Show short date and move exact timestamp into details/evidence. |

## Strengths To Keep

- The gear simulator is the strongest visual proof of "real WoW assets + dense mobile utility"; it should be a reference for future tool surfaces.
- Talent simulator uses real talent icons and tree affordances; do not replace this with generated or decorative assets.
- Workbench readiness states are directionally right: blocked, partial, and ready are visible and action-oriented.
- Task empty state is now a real product state instead of an almost-black blank page.
- Chickenbro copy correctly refuses to fabricate DPS, rankings, and log conclusions.

## Next Implementation Pass

1. Fix P0 product path: SimC inherits workbench class/spec and workbench gear readiness uses one canonical count/blocker model.
2. Fix screenshot acceptance: recapture actual news scrolled state and actual evidence-expanded state.
3. Recompose workbench first screen: one verdict, one primary action, one compact module/status rail, evidence lower but reachable.
4. Clean player-facing copy: remove `scheduled`, raw `checkedAt`, raw timezone timestamps, and scaffolding labels.
5. Use imagegen only for material assets after layout is stable: dark iron panel texture, subtle state backgrounds, and empty-state atmosphere; do not generate WoW icons or factual UI content.
6. Rerun official mini-program screenshots and compare against this CR before declaring the next UI pass complete.

## Verification Notes

- This review used the final official screenshot contact sheet and individual PNGs under `artifacts/miniprogram-screenshots/20260630-workbench-redesign/screenshots/`.
- `manifest.json` being complete remains useful for route reachability, but visual proof must still be checked manually for scene correctness.
