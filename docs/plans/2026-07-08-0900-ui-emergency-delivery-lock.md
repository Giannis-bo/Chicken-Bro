# 2026-07-08 09:00 UI Emergency Delivery Lock

> Superseded for current execution by [2026-07-08 Current UI Delivery Source Of Truth](2026-07-08-current-ui-delivery-source-of-truth.md). Keep this file as historical rescue context; do not treat it as newer than the current source-of-truth document.

## Purpose

This is the first document to read for the 2026-07-08 09:00 WOW mini program UI delivery.

It exists because the previous workflow repeatedly produced code changes that looked plausible in source but failed in the real WeChat mini program: broken bottom tab labels, misaligned channel icons, split status shield/glyph, clipped chat input, unstable page chrome, and DevTools unresponsive/login-state incidents.

The next agent must not continue from imagination, stale scorecards, browser-only evidence, or old component aspirations. The delivery must be driven by real mini program screenshots, route smoke, and a short risk ledger.

## Source Of Truth Order

Read in this order:

1. `docs/roadmap.md` top 2026-07-08 entries.
2. `docs/plans/2026-07-08-0900-ui-emergency-delivery-lock.md`.
3. `docs/plans/2026-07-08-0900-ui-delivery-handoff-lock.md`.
4. `docs/plans/2026-07-08-0900-ui-delivery-execution-guard.md`.
5. `docs/plans/2026-07-08-wow-mini-program-0900-ui-delivery-goal.md`.
6. `docs/plans/2026-07-08-0900-ui-rescue-context-lock.md`.
7. Current `app.json`, current WXML/WXSS/JS, and real WeChat mini program screenshots.
8. Older UI-system rebuild docs, pass artifacts, owner registry, implementation permits, browser demos, target images, and tests only as historical evidence.

If these sources conflict, this emergency lock wins until the 09:00 delivery is either shipped or explicitly replaced by the user.

## Current Reality

Do not claim these are solved without fresh evidence:

- Bottom tabBar has repeatedly lost labels, stretched icons, or glued itself to the bottom.
- News channel dock icons such as `综合 / 官方` have repeatedly remained off-center after many edits.
- Current spec workbench blocked-state shield has repeatedly been split or overlaid incorrectly.
- Workbench cards and evidence rows have repeatedly become cramped, clipped, or hard to read.
- Chickenbro/intelligent-analysis has repeatedly had the input area clipped, floated too high, or blocked by page chrome/tabBar.
- Profile top identity area has shown broken material layering and visual splits.
- WeChat DevTools has repeatedly shown page-unresponsive behavior during validation.
- Static tests and code reasoning have not matched what the user saw in the simulator.

Treat these as workflow failures first, not individual pixels.

## Emergency Goal

Ship a demonstrable rescue UI before 09:00.

The target is not:

- full UI system rebuild;
- 90% imagegen target recreation;
- pass36/pass37 completion;
- old scorecard completion;
- owner registry completion;
- static-test-only completion;
- empty shell pages that hide broken content.

The target is:

- every `app.json` page is accounted for;
- P0 pages are usable and visually not broken in real mini program screenshots;
- P1 pages open and remain readable;
- P2 pages do not white-screen or hang;
- bottom tabBar has visible icons and labels;
- homepage, builds/spec, current spec workbench, talent simulator, gear detail, SimC, Chickenbro/intelligent-analysis, tasks, and profile can be demonstrated;
- DevTools validation does not destroy login state or make the project unusable.

## Page Scope

All current `app.json` pages are in scope:

- `pages/news/news`
- `pages/news/list`
- `pages/news/detail`
- `pages/builds/builds`
- `pages/builds/workbench`
- `pages/builds/intel`
- `pages/builds/talent-simulator`
- `pages/builds/detail`
- `pages/simulator/simulator`
- `pages/simulator/simc`
- `pages/simulator/chickenbro`
- `pages/simulator/tasks`
- `pages/simulator/task-detail`
- `pages/profile/profile`

## Priority

P0 real-screenshot pass required:

- `pages/news/news`
- `pages/builds/builds`
- `pages/builds/workbench`
- `pages/builds/talent-simulator`
- `pages/builds/detail`
- `pages/simulator/simulator`
- `pages/simulator/simc`
- `pages/profile/profile`

P1 readable/open required:

- `pages/news/list`
- `pages/news/detail`
- `pages/simulator/chickenbro`
- `pages/simulator/tasks`
- `pages/simulator/task-detail`

P2 no-white-screen/no-hang required:

- `pages/builds/intel`

## Workflow Rules

### Evidence First

Before another UI patch:

- identify the exact route and screenshot that proves the problem;
- compare the visible failure to the intended layout;
- change the smallest owner of the layout problem;
- recapture the same route;
- mark pass/risk/fail.

Do not make broad visual edits without a screenshot-backed failure and a recapture plan.

### Stop Repeating Failed Abstractions

If a component or custom shell has repeatedly produced broken runtime screenshots, do not keep repairing it one pixel at a time.

Allowed emergency fallback:

- replace unstable nested composition with a stable page-level block layout;
- replace fragile image layering with one complete atomic image or a pure CSS/text fallback;
- replace offset-prone generated icon art with centered text/glyph inside a fixed-size owner;
- simplify decorative material when it competes with content.

Forbidden:

- hiding core product content to make a screenshot look cleaner;
- restoring broken layouts only to satisfy stale tests;
- splitting one semantic status visual into unmanaged background plus floating glyph;
- faking WeChat status bar, time, battery, Wi-Fi, or capsule chrome;
- calling browser HTML preview final evidence.

### Layout Baseline

Every core page must obey:

- one page root controls safe area and bottom spacing;
- one scroll region owns vertical scroll;
- fixed bottom actions and chat input reserve space for tabBar/safe area;
- page gutters are explicit and consistent;
- icons are centered by a fixed-size component owner, not by per-page nudges;
- long text must wrap or clamp intentionally, never push controls out of bounds;
- buttons have stable height and cannot be compressed by flex children;
- no horizontal overflow in the real simulator viewport.

## DevTools Stability Rules

The user's logged-in WeChat DevTools session is production evidence infrastructure.

Forbidden unless the user explicitly asks in that turn:

- close DevTools;
- restart DevTools;
- clear cache/storage;
- switch appid;
- switch project;
- delete DevTools user data;
- run repeated open/close/compile loops;
- run long serial navigation batches after `currentState` timeouts or page-unresponsive warnings.

Allowed:

- connect to an existing automator endpoint;
- capture one route or a very small batch;
- record the route, screenshot path, page state, warning, and action ledger;
- stop immediately if DevTools becomes unresponsive.

If DevTools is unsafe:

- mark `captureSafe=false`;
- continue only with code inspection and browser/component precheck;
- do not mark runtime verification complete.

## UI Correctness Proof

A page can be called runtime-verified only with:

- real WeChat mini program screenshot path;
- route and viewport/device context;
- pass/risk/fail label;
- short route smoke or direct-open result;
- DevTools action ledger with no forbidden lifecycle actions.

For 09:00 rescue, every screenshot review must at least check:

- no white screen;
- no obvious horizontal overflow;
- no obvious edge-to-edge content crash;
- no capsule/nav overlap;
- bottom tabBar icon and text visible where applicable;
- input or fixed action not covered by tabBar;
- core title and primary action readable;
- homepage carousel/channel/ranked feed retained;
- workbench conclusion/status/action retained;
- Chickenbro welcome/input/action retained;
- profile identity area readable.

If proof is missing, write `risk`; do not write `pass`.

## Implementation Order

1. Freeze broad refactors and old scorecard-driven edits.
2. Re-establish the real screenshot manifest for all 14 pages.
3. Fix global shell/tabBar/safe-area/scroll/input bottom spacing first.
4. Fix P0 pages from screenshot evidence only.
5. Fix P1 readability and route smoke.
6. Confirm P2 is not white-screen or hanging.
7. Produce a final delivery ledger with screenshots, remaining risks, and DevTools safety notes.

## Codex Goal Text

Use this exact goal text for Codex Goal Mode:

```text
在 2026-07-08 09:00 前交付 WOW 小程序 UI 救火版，并以真实微信小程序截图证明可交付。

当前控制面只认：docs/roadmap.md 顶部 2026-07-08 条目、docs/plans/2026-07-08-0900-ui-emergency-delivery-lock.md、docs/plans/2026-07-08-0900-ui-delivery-handoff-lock.md、docs/plans/2026-07-08-0900-ui-delivery-execution-guard.md、docs/plans/2026-07-08-wow-mini-program-0900-ui-delivery-goal.md、docs/plans/2026-07-08-0900-ui-rescue-context-lock.md、当前 app.json、当前真实微信小程序截图。旧 UI 系统重建、pass36/pass37、旧 scorecard、旧 owner registry、旧 implementation permit、browser-only demo、imagegen 整页目标图、旧静态测试期望只能作为历史证据，不能驱动本轮验收。

核心目标：覆盖 app.json 注册的全部 14 个页面；P0 页面真实截图无明显崩坏；P1 页面可打开可读；P2 页面不白屏不卡死；底部 tabBar 图标和文字稳定；首页轮播/频道/重点列表、职业专精、当前专精工作台、天赋模拟、装备详情、SimC、炸鸡队长/智能分析、任务、我的页面可演示；DevTools 登录态和稳定性不被验证流程破坏。

工作流必须纠偏：先用真实截图定位问题，再改最小 owner，再 recapture 同一路由。禁止继续凭 CSS 推理或浏览器预览宣布修好；禁止继续旧局部像素修补；禁止为了旧测试恢复错误结构；禁止删核心信息做空壳；禁止把一个状态视觉拆成会错位的多层；禁止伪造微信状态栏/胶囊；没有真实小程序截图只能标 risk，不能标 runtime_verified 或 final_accepted。

DevTools 规则：默认使用用户已登录、已打开的微信开发者工具；禁止自动关闭、重启、清缓存、切 appid、切项目、删除用户目录或反复 open-close-compile；出现 currentState timeout、页面无响应或登录态异常时，立即停止长批量自动化，记录 blocker，改用单页面短路径验证。

交付输出：真实截图 manifest、每页 pass/risk/fail、P0 route smoke、DevTools action ledger、剩余风险清单。只有 14 个页面均有证据或明确风险、P0 主线无明显崩坏、DevTools 未被禁用动作扰动时，才允许声明完成。
```
