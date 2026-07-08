# 2026-07-08 Current UI Delivery Source Of Truth

## Purpose

This is the current first-read document for WOW mini program UI delivery.

It exists to prevent future Codex sessions and agents from continuing the wrong workflow: broad UI-system rebuild, old pass/scorecard chasing, browser-only validation, static-test confidence, component patching without runtime evidence, or imaginary fixes that do not match the WeChat simulator.

Until the user explicitly replaces this document, every agent entering this repository for UI work must use this as the active execution contract.

## Latest User Correction

The current user correction is stronger than the earlier rescue notes:

- do not keep editing from memory, imagination, CSS reasoning, or stale screenshots;
- do not claim a page is fixed until the same real WeChat route has been recaptured or explicitly marked `risk`;
- do not continue a broken component chain if it has already failed repeatedly in simulator screenshots;
- do not remove product content, bottom navigation, carousel, channel dock, ranked feed, workbench details, or Chickenbro input just to make layout easier;
- do not treat "fast delivery" as permission to ship incorrect layout;
- do not keep broadening scope while P0 pages still visibly fail;
- do not let older goals, pass artifacts, stale scorecards, or old static tests override fresh user screenshots.

The immediate delivery question is:

> Can every `app.json` page be opened, seen, and explained with current real WeChat evidence, and are the P0 user journeys visibly usable without DevTools being destabilized?

If the answer is not proven, the status is `risk` or `fail`, not `done`.

## Read Order

Read in this order before planning or editing UI:

1. `AGENTS.md`
2. `docs/roadmap.md` top entries
3. `docs/plans/2026-07-08-current-ui-delivery-source-of-truth.md`
4. Current `app.json`
5. Current real WeChat mini program screenshots and manifests under `artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/`
6. Current page/component source
7. Older 2026-07-08 rescue locks only for historical context
8. Older UI-system rebuild docs, pass artifacts, owner registries, implementation permits, browser demos, imagegen target images, stale tests, and scorecards only as historical evidence

If any older document conflicts with this file, this file wins.

Do not spend the rescue window reading every older UI-system document. Older documents are for context only after the current screenshot, route, and source facts are understood.

## Current Goal

Deliver a usable, demonstrable WOW mini program UI rescue build for the current handoff window.

This is not:

- a full UI-system rebuild;
- a 90% imagegen target recreation project;
- a pass36/pass37 continuation;
- a scorecard-only task;
- a component-registry completion task;
- a browser HTML demo task;
- a static-test cleanup task;
- an excuse to hide broken content behind empty shells.

This is:

- all `app.json` pages accounted for;
- P0 pages visibly usable in real WeChat mini program screenshots;
- P1 pages open and readable;
- P2 pages not white-screening or hanging;
- bottom tabBar icons and labels visible and stable;
- homepage, builds/spec, workbench, talent simulator, gear detail, SimC, Chickenbro/intelligent-analysis, tasks, and profile demonstrable;
- DevTools login state and stability protected.

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

## Known Runtime Failures

Treat these as current system risks until fresh runtime evidence proves otherwise:

- bottom tabBar labels missing, icons stretched, or bottom spacing unsafe;
- homepage channel dock icons such as `综合 / 官方` off-center;
- homepage carousel, channel dock, and ranked feed accidentally removed or degraded;
- workbench blocked-state shield/glyph split, overlaid, or positioned from page-private offsets;
- workbench cards cramped, clipped, unreadable, or stacked without visual hierarchy;
- talent simulator visually unfinished or overflowing;
- Chickenbro/intelligent-analysis input clipped, floating too high, hidden behind tabBar, or page body reduced to an empty shell;
- profile top identity area split by broken material layering;
- fixed bottom actions covered by tabBar or safe area;
- route navigation works in code but times out or fails in real automator/runtime;
- WeChat DevTools page-unresponsive warnings or login-state loss after automation.

These failures are not isolated cosmetic bugs. They indicate workflow and ownership failure until fixed at the right layer:

- tabBar failure belongs to the app shell/custom tabBar contract, not per-page padding hacks;
- repeated icon centering failure belongs to the icon/channel component contract, not individual image offsets;
- repeated shield/glyph failure belongs to one status visual owner, not separate page-private background and glyph layers;
- repeated Chickenbro input failure belongs to the chat shell and bottom-safe-area contract, not fixed empty vertical space;
- repeated DevTools hang means verification must shrink to one short route at a time, with immediate stop on timeout.

## Workflow Contract

Before editing UI:

- start with a current screenshot or runtime capture target for the exact route;
- write down the visible failure in one sentence before touching code;
- identify the exact route and current screenshot that proves the problem;
- decide whether the fix belongs to global shell/tabBar/safe area, page layout, or one component owner;
- avoid broad visual edits without a recapture plan;
- stop using failed abstractions if they repeatedly produce broken simulator screenshots.

After editing UI:

- run the smallest relevant static check only to catch syntax or contract regressions;
- recapture the same route whenever DevTools is safe;
- if DevTools is unsafe, mark the page as `risk`, not `pass`;
- update the relevant manifest or ledger with route, screenshot, pass/risk/fail, and DevTools status.

Do not:

- claim success from CSS reasoning, browser preview, static tests, or `git diff --check`;
- keep repairing the same broken layout one pixel at a time;
- satisfy stale tests by restoring a broken UI structure;
- delete core product information to make a page look clean;
- fake WeChat status bar, time, battery, Wi-Fi, or capsule chrome;
- split one semantic status visual into unmanaged background plus floating glyph;
- use imagegen assets as fake real WoW objects, fake data, fake status, or fake text facts.

When time is short, prefer a stable, honest, lower-risk layout over a more decorative layout that cannot be verified. Do not keep polishing a visibly broken decorative structure.

## Emergency Layout Baseline

Every deliverable page should use the simplest stable structure that preserves the product:

- one page root owns the safe area;
- one scroll region owns vertical scroll;
- bottom tabBar and fixed inputs/actions have reserved space;
- gutters are explicit and consistent;
- buttons have stable height;
- fixed-size icons are centered by their owner component;
- long text wraps or clamps intentionally;
- no horizontal overflow in the real simulator viewport;
- decorative material never pushes or covers business content.

When a complex component chain is unstable, use a stable page-level rescue layout. The rescue layout is acceptable only if the real product information and navigation remain visible.

## DevTools Rules

The user's logged-in WeChat DevTools session is delivery infrastructure.

Forbidden unless the user explicitly asks in the same turn:

- close DevTools;
- restart DevTools;
- clear cache or storage;
- switch appid;
- switch project;
- delete DevTools user data;
- run repeated open/close/compile loops;
- run long serial navigation batches after timeout or unresponsive warnings.

Allowed:

- connect to an existing healthy automator endpoint;
- run one-page or very short route checks;
- capture one route at a time;
- record route, screenshot path, page state, warning, and action ledger;
- stop immediately if DevTools becomes unresponsive.

If DevTools is unsafe, set `captureSafe=false` and continue with code inspection or browser/component precheck only. Do not mark runtime verification complete.

If DevTools shows page-unresponsive warnings:

1. stop long automation immediately;
2. record the route, action, time, and whether login state changed;
3. do not retry by closing, reopening, clearing cache, or switching appid;
4. inspect recent source changes for heavy synchronous loops, oversized rendering, recursive `setData`, repeated timers, or runaway route automation;
5. resume only with a single direct route capture after the user confirms DevTools is healthy, or leave the page as `risk`.

## Evidence Required

A page can be called `runtime_verified` only when there is:

- a real WeChat mini program screenshot path;
- route and viewport/device context;
- pass/risk/fail label;
- route smoke or direct-open result;
- DevTools action record with no forbidden lifecycle actions.

For this delivery window, every page review must check:

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

If proof is missing, write `risk`. Do not write `pass`.

## Proof Matrix

Every delivery report must include a compact matrix with one row per `app.json` page:

- route;
- priority `P0 / P1 / P2`;
- latest screenshot path or `missing`;
- visual status `pass / risk / fail`;
- route status `pass / risk / fail`;
- main visible issue, if any;
- DevTools action used, or `none`;
- whether the evidence was captured after the latest relevant code change.

Static tests, browser previews, and old artifacts may be listed as supporting notes, but they cannot fill the screenshot or route-status columns.

## Current Evidence Locations

Use these current evidence files before making claims:

- `artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/page-captures/`
- `artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/aggregate-page-visual-manifest.json`
- `artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/single-page-screenshot-summary.json`
- `artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/visual-review-ledger.md`
- `artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/visual-review-ledger.json`
- `artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/final-delivery-audit.md`
- `artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/final-delivery-audit.json`
- `artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/p0-route-smoke-manifest.json`
- `artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/devtools-action-ledger.json`
- `artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/static-route-contract-audit.json`
- `artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/automator-endpoint-probe.json`

Static route contracts can reduce uncertainty, but they do not replace runtime route smoke.

## Stop Conditions

Stop implementation and fix the workflow first if:

- the user reports the same visual bug still exists after a claimed fix;
- screenshot evidence contradicts the code-level assumption;
- DevTools becomes unresponsive;
- login state is lost after an automation action;
- a fix only moves a problem between pages;
- a page is stable only because core content was removed;
- more than one page is being changed without a fresh route/screenshot target.

If any stop condition happens, the next action is not another visual tweak. The next action is a short written correction: route, failed assumption, owner layer, safer fix, and verification path.

## Codex Goal Text

Use this exact text when starting Codex Goal Mode:

```text
交付 WOW 小程序当前 UI 救火版，并用真实微信小程序证据证明可交付。当前是 09:00 前救火交付，不是继续旧 UI 系统重建，也不是凭想象继续修图。

当前控制面只认：AGENTS.md、docs/roadmap.md 顶部、docs/plans/2026-07-08-current-ui-delivery-source-of-truth.md、当前 app.json、当前真实微信小程序截图和 artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/ 下的 manifest/ledger/audit。旧 UI 系统重建、pass36/pass37、旧 scorecard、旧 owner registry、旧 implementation permit、browser-only demo、imagegen 整页目标图和旧静态测试期望只能作为历史证据，不能驱动本轮验收。

目标：覆盖 app.json 注册的全部 14 个页面；P0 页面真实截图无明显崩坏；P1 页面可打开可读；P2 页面不白屏不卡死；底部 tabBar 图标和文字稳定；首页轮播/频道/重点列表、职业专精、当前专精工作台、天赋模拟、装备详情、SimC、炸鸡队长/智能分析、任务、我的页面可演示；DevTools 登录态和稳定性不被验证流程破坏。

工作流：先建立 14 页 proof matrix，再按当前真实截图定位 P0 问题；每次只改最小 owner 层，优先 app shell/tabBar/safe area、channel/icon owner、status visual owner、chat shell/input owner 这类系统问题；改完必须 recapture 同一路由，或明确标 risk。没有真实小程序截图只能标 risk，不能标 runtime_verified 或 final_accepted。

禁止：继续凭 CSS 推理、浏览器预览、旧 scorecard 或静态测试宣布修好；继续旧局部像素修补；为了旧测试恢复错误结构；删核心信息做空壳；伪造微信状态栏/胶囊；把一个状态视觉拆成会错位的多层；用 imagegen 伪造真实 WoW 对象、事实、文字或状态；在 P0 页面仍明显失败时扩大范围做装饰。

DevTools：默认使用用户已登录、已打开的微信开发者工具；禁止自动关闭、重启、清缓存、切 appid、切项目、删除用户目录或反复 open-close-compile；出现 currentState timeout、页面无响应或登录态异常时立即停止长批量自动化，记录 blocker，排查重 setData/同步循环/过大渲染/自动化循环，改用单页面短路径验证或标记风险。

交付输出：14 页 proof matrix、真实截图 manifest、每页 pass/risk/fail、P0 route smoke 或明确 route 风险、DevTools action ledger、剩余风险清单。只有 14 个页面均有当前证据或明确风险、P0 主线无明显崩坏、tabBar/首页/workbench/Chickenbro/profile 不再出现用户已指出的崩坏、DevTools 未被禁用动作扰动时，才允许声明完成。
```
