# 2026-07-08 Codex Goal Mode UI Delivery Handoff

> Archived current-state note (2026-07-10): this handoff is no longer the active first-read contract by default. `docs/project-state.json` records the UI delivery domain as `accepted_baseline` with 14/14 current mini-program route screenshots accepted on 2026-07-09. Keep this file as historical rescue evidence unless a new UI Harness contract reactivates UI delivery work.

## Status

`历史归档 / accepted baseline`

This is the current goal-mode handoff for the WOW mini program UI delivery.

Read this file before older UI plans, pass artifacts, scorecards, implementation permits, imagegen references, browser demos, or static-test expectations.

## Current Objective

Deliver the WOW mini program current UI rescue build for the handoff window, with real WeChat mini program evidence.

This is not a full UI-system rebuild, not a pass36/pass37 continuation, not a browser-only demo, not a static-test cleanup task, and not a visual guesswork task.

## App Scope

The delivery covers every page currently registered in `app.json`:

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

P0 pages must be visibly usable in fresh real WeChat mini program screenshots:

- `pages/news/news`
- `pages/builds/builds`
- `pages/builds/workbench`
- `pages/builds/talent-simulator`
- `pages/builds/detail`
- `pages/simulator/simulator`
- `pages/simulator/simc`
- `pages/profile/profile`

P1 pages must open and remain readable:

- `pages/news/list`
- `pages/news/detail`
- `pages/simulator/chickenbro`
- `pages/simulator/tasks`
- `pages/simulator/task-detail`

P2 pages must not white-screen or hang:

- `pages/builds/intel`

## Current User-Reported Failures

Treat these as open until fresh real WeChat screenshots prove otherwise:

- bottom tabBar text missing, icons stretched, or unsafe bottom spacing;
- homepage channel icons such as `综合 / 官方` off-center;
- homepage carousel, channel dock, or ranked feed removed or degraded;
- workbench blocked-state shield/glyph split, floating, or overlapping content;
- workbench cards cramped, clipped, or lacking hierarchy;
- talent simulator visually unfinished or overflowing;
- Chickenbro/intelligent-analysis body collapsed, input clipped, input floating too high, or fixed area covered by tabBar;
- profile top identity area split or unreadable;
- fixed bottom actions covered by tabBar or safe area;
- WeChat DevTools page-unresponsive warning, screenshot timeout, or login-state instability.

## Workflow Rules

- Start from the 14-page proof matrix, not from a single component guess.
- Before editing, identify route, latest screenshot, visible failure, and owner layer.
- Owner layers are `app shell/tabBar/safe area`, `route layout`, or one component owner.
- Fix the smallest owner layer that explains the visible failure.
- Do not keep patching a failed component chain if fresh simulator screenshots keep proving it wrong.
- Do not remove core product content to make a page easier to lay out.
- Do not mark a page fixed from CSS reasoning, browser preview, static tests, old screenshots, or old scorecards.
- After editing, recapture the same route in real WeChat if DevTools is safe.
- If DevTools is unsafe, mark the page `risk`; do not mark it `runtime_verified`.

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
- keep running long route batches after timeout, unresponsive warning, or login-state change.

Allowed:

- connect to an existing healthy automator endpoint;
- capture one route at a time;
- run short direct route smoke checks;
- record every DevTools action in a ledger;
- stop immediately on unresponsive warning or login-state instability.

If DevTools hangs, diagnose route render cost, repeated `setData`, large images, runaway timers, automation loops, and custom-component height propagation before any more visual edits.

## Evidence Required

The final delivery report must include one row per app page:

- route;
- priority;
- latest screenshot path or `missing`;
- visual status `pass / risk / fail`;
- route status `pass / risk / fail`;
- main visible issue;
- DevTools action used or `none`;
- whether evidence was captured after the latest relevant source change.

No page may be called `runtime_verified` without current real WeChat screenshot evidence and a route/action record.

## Stop Conditions

Stop and report risk instead of continuing to patch when:

- the same route screenshot capture times out twice;
- DevTools shows page-unresponsive warning;
- login state changes unexpectedly;
- a P0 page remains visibly broken after an owner-layer fix;
- the next proposed change is based on visual imagination rather than current runtime evidence.

## Codex Goal Text

Use this exact goal when entering Codex Goal Mode:

```text
交付 WOW 小程序当前 UI 救火版，并用真实微信小程序证据证明可交付。当前任务是 09:00 前救火交付，不是继续旧 UI 系统重建，不是 pass36/pass37 延续，不是 browser-only demo，不是静态测试 cleanup，也不是凭想象继续修 UI。

启动后必须先读取：AGENTS.md、docs/roadmap.md 顶部、docs/plans/2026-07-08-codex-goal-mode-ui-delivery-handoff.md、docs/plans/2026-07-08-ui-goal-mode-entry-contract.md、docs/plans/2026-07-08-current-ui-delivery-source-of-truth.md、当前 app.json、当前真实微信小程序证据和 artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest/ 下的 manifest/ledger/audit。旧 UI 系统重建、旧 pass/scorecard/owner registry/implementation permit、browser demo、imagegen 整页目标图和旧静态测试期望只能作为历史证据，不能驱动本轮验收。

目标覆盖 app.json 注册的全部 14 个页面：pages/news/news、pages/news/list、pages/news/detail、pages/builds/builds、pages/builds/workbench、pages/builds/intel、pages/builds/talent-simulator、pages/builds/detail、pages/simulator/simulator、pages/simulator/simc、pages/simulator/chickenbro、pages/simulator/tasks、pages/simulator/task-detail、pages/profile/profile。P0 页面必须真实截图无明显崩坏；P1 页面必须可打开可读；P2 页面不能白屏或卡死。底部 tabBar 图标和文字必须稳定；首页轮播/频道/重点列表、职业专精、当前专精工作台、天赋模拟、装备详情、SimC、炸鸡队长/智能分析、任务、我的页面都必须保留核心信息和可演示入口。

工作流必须从 14 页 proof matrix 开始。每次改动前先锁定真实 route、最新截图、可见问题和 owner 层；每次只改最小必要层，优先修 app shell/tabBar/safe area、channel/icon owner、status visual owner、chat shell/input owner 这类系统问题。改完必须 recapture 同一路由；如果 DevTools 不安全，只能标 risk，不能标 runtime_verified 或 final_accepted。

禁止继续凭 CSS 推理、浏览器预览、旧截图、旧 scorecard 或静态测试宣布修好；禁止继续旧局部像素修补；禁止为了旧测试恢复错误结构；禁止删核心信息做空壳；禁止伪造微信状态栏/胶囊；禁止把一个状态视觉拆成会错位的多层；禁止用 imagegen 伪造真实 WoW 对象、事实、文字或状态；禁止在 P0 页面仍明显失败时扩大范围做装饰。

DevTools 必须低扰动：默认使用用户已登录、已打开的微信开发者工具；禁止自动关闭、重启、清缓存、切 appid、切项目、删除用户目录或反复 open-close-compile；出现页面无响应、currentState timeout 或登录态异常时立即停止长批量自动化，记录 blocker，排查重复 setData、同步循环、过大渲染、自动化循环，再用单页面短路径验证或标记风险。

交付输出必须包含：14 页 proof matrix、真实截图 manifest、每页 pass/risk/fail、P0 route smoke 或明确 route 风险、DevTools action ledger、剩余风险清单。只有 14 个页面均有当前证据或明确风险、P0 主线无明显崩坏、tabBar/首页/workbench/Chickenbro/profile 不再出现用户已指出的崩坏、DevTools 未被禁用动作扰动时，才允许声明完成。
```
