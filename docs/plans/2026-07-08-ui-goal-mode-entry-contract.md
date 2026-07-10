# 2026-07-08 UI Goal Mode Entry Contract

> Archived current-state note (2026-07-10): this contract is no longer the active UI entry by default. `docs/project-state.json` records UI delivery as an accepted baseline; use this file as historical rescue evidence unless a new UI Harness contract explicitly reactivates UI delivery work.

## Purpose

This is the first-read contract for the current WOW mini program UI delivery goal mode.

It exists to stop future Codex sessions from drifting back into old UI-system rebuild work, pass36/pass37 patching, stale scorecards, browser-only validation, static-test confidence, or memory-based visual edits.

Until the user explicitly replaces this file, UI delivery work must start here after `AGENTS.md` and the top of `docs/roadmap.md`.

## Current Delivery Goal

Deliver the current WOW mini program UI rescue build for handoff.

This is a real WeChat mini program delivery task, not a design exploration task.

The target is:

- all 14 `app.json` pages are accounted for;
- P0 pages are visibly usable in real WeChat screenshots;
- P1 pages open and remain readable;
- P2 pages do not white-screen or hang;
- bottom tabBar icons and labels are visible and stable;
- core product information is not removed to make layouts easier;
- WeChat DevTools login state and stability are protected.

## Read Order

Read in this order before making UI decisions or editing files:

1. `AGENTS.md`
2. `docs/roadmap.md` top current-control entries
3. `docs/plans/2026-07-08-ui-goal-mode-entry-contract.md`
4. `docs/plans/2026-07-08-current-ui-delivery-source-of-truth.md`
5. current `app.json`
6. current real WeChat evidence under `artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/`
7. current page/component source
8. older rescue locks and UI-system rebuild docs only as historical evidence

If an older document, scorecard, test, imagegen target, or implementation permit conflicts with this file, this file wins.

## Page Scope

All registered pages are in scope:

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

P0 pages must have fresh real-screenshot evidence before they can be called usable:

- `pages/news/news`
- `pages/builds/builds`
- `pages/builds/workbench`
- `pages/builds/talent-simulator`
- `pages/builds/detail`
- `pages/simulator/simulator`
- `pages/simulator/simc`
- `pages/profile/profile`

P1 pages must open and be readable:

- `pages/news/list`
- `pages/news/detail`
- `pages/simulator/chickenbro`
- `pages/simulator/tasks`
- `pages/simulator/task-detail`

P2 pages must not white-screen or hang:

- `pages/builds/intel`

## Non-Negotiable Corrections

Do not claim a fix without current real WeChat evidence for the same route.

Do not continue a failed component chain just because it exists in the repo. If a component repeatedly produces broken real screenshots, replace or bypass it for this rescue build.

Do not solve layout by deleting required product content. Homepage carousel/channel/ranked feed, bottom tabBar labels, workbench conclusion/details, Chickenbro welcome/input, and profile identity must remain visible where relevant.

Do not satisfy stale tests by restoring broken UI. Update tests only when they were protecting a structure that real screenshots proved wrong.

Do not use browser preview, static tests, CSS reasoning, old screenshots, or old scorecards as proof of UI correctness.

Do not fake WeChat chrome. Do not render duplicate time, battery, Wi-Fi, or capsule elements inside page content.

Do not use imagegen assets as fake real WoW objects, fake facts, fake statuses, or text-bearing UI truth. Imagegen can only provide low-semantic visual material after it is sliced, named, and fitted.

## Required Workflow

Before editing:

- identify the exact route;
- identify the latest screenshot or mark evidence as missing;
- write the visible failure in one sentence;
- decide the owner layer: app shell/tabBar/safe area, route layout, or one component owner;
- choose the smallest fix that can be recaptured.

After editing:

- run syntax/static checks only as guardrails;
- recapture the same route in real WeChat if DevTools is safe;
- if DevTools is unsafe, mark the page `risk`;
- update the proof matrix, screenshot manifest, or delivery ledger with current status.

## DevTools Safety

The user's logged-in WeChat DevTools session is delivery infrastructure.

Forbidden unless the user explicitly asks in the same turn:

- close DevTools;
- restart DevTools;
- clear cache or storage;
- switch appid;
- switch project;
- delete DevTools user data;
- run repeated open/close/compile loops;
- continue long route batches after timeout, unresponsive warning, or login-state change.

Allowed:

- use an existing healthy automator endpoint;
- capture one route at a time;
- run short direct route smoke checks;
- record every DevTools action in a ledger;
- stop immediately on unresponsive warning or login-state instability.

If DevTools hangs, the next step is diagnosis, not another visual patch. Check for heavy synchronous render, repeated large `setData`, recursive route automation, oversized image nodes, runaway timers, and deep scroll/custom-component height propagation.

## Proof Matrix Requirement

The delivery report must include one row per page:

- route;
- priority;
- latest screenshot path or `missing`;
- visual status `pass / risk / fail`;
- route status `pass / risk / fail`;
- main visible issue;
- DevTools action used or `none`;
- whether evidence was captured after the latest relevant source change.

No page may be marked `runtime_verified` without current real WeChat screenshot evidence and a route/action record.

## Current Known High-Risk Issues

Treat these as open until fresh runtime evidence proves otherwise:

- bottom tabBar text missing, icons stretched, or unsafe bottom spacing;
- homepage `综合 / 官方 / 更新 / 活动 / 社区 / 攻略` channel icons off-center;
- homepage carousel or ranked feed removed or degraded;
- workbench blocked-state shield and glyph split, floating, or overlapping content;
- workbench cards cramped, clipped, or lacking hierarchy;
- talent simulator overflowing or visually unfinished;
- Chickenbro/intelligent-analysis input clipped, floating too high, or page reduced to an empty shell;
- profile identity area split or unreadable;
- fixed action/input covered by tabBar or safe area;
- DevTools page-unresponsive warnings or login-state loss after automation.

## Codex Goal Text

Use this goal text when starting Codex Goal Mode:

```text
交付 WOW 小程序当前 UI 救火版，并用真实微信小程序证据证明可交付。当前是 09:00 前救火交付，不是继续旧 UI 系统重建，不是凭想象继续修图，也不是用静态测试或旧 scorecard 宣布完成。

启动后必须先读取：AGENTS.md、docs/roadmap.md 顶部、docs/plans/2026-07-08-ui-goal-mode-entry-contract.md、docs/plans/2026-07-08-current-ui-delivery-source-of-truth.md、当前 app.json、当前真实微信小程序证据和 artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/ 下的 manifest/ledger/audit。旧 UI 系统重建、pass36/pass37、旧 owner registry、旧 implementation permit、browser-only demo、imagegen 整页目标图和旧静态测试期望只能作为历史证据，不能驱动本轮验收。

目标覆盖 app.json 注册的全部 14 个页面：news/news、news/list、news/detail、builds/builds、builds/workbench、builds/intel、builds/talent-simulator、builds/detail、simulator/simulator、simulator/simc、simulator/chickenbro、simulator/tasks、simulator/task-detail、profile/profile。P0 页面必须真实截图无明显崩坏；P1 页面必须可打开可读；P2 页面不能白屏或卡死。底部 tabBar 图标和文字必须稳定；首页轮播/频道/重点列表、职业专精、当前专精工作台、天赋模拟、装备详情、SimC、炸鸡队长/智能分析、任务、我的页面都必须保留核心信息和可演示入口。

工作流必须从 14 页 proof matrix 开始。每次改动前先锁定真实 route、最新截图、可见问题和 owner 层；每次只改最小必要层，优先修 app shell/tabBar/safe area、channel/icon owner、status visual owner、chat shell/input owner 这类系统问题。改完必须 recapture 同一路由；如果 DevTools 不安全，只能标 risk，不能标 runtime_verified 或 final_accepted。

禁止继续凭 CSS 推理、浏览器预览、旧截图、旧 scorecard 或静态测试宣布修好；禁止继续旧局部像素修补；禁止为了旧测试恢复错误结构；禁止删核心信息做空壳；禁止伪造微信状态栏/胶囊；禁止把一个状态视觉拆成会错位的多层；禁止用 imagegen 伪造真实 WoW 对象、事实、文字或状态；禁止在 P0 页面仍明显失败时扩大范围做装饰。

DevTools 必须低扰动：默认使用用户已登录、已打开的微信开发者工具；禁止自动关闭、重启、清缓存、切 appid、切项目、删除用户目录或反复 open-close-compile；出现页面无响应、currentState timeout 或登录态异常时立即停止长批量自动化，记录 blocker，排查重 setData、同步循环、过大渲染、自动化循环，再用单页面短路径验证或标记风险。

交付输出必须包含：14 页 proof matrix、真实截图 manifest、每页 pass/risk/fail、P0 route smoke 或明确 route 风险、DevTools action ledger、剩余风险清单。只有 14 个页面均有当前证据或明确风险、P0 主线无明显崩坏、tabBar/首页/workbench/Chickenbro/profile 不再出现用户已指出的崩坏、DevTools 未被禁用动作扰动时，才允许声明完成。
```
