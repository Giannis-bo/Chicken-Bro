# 2026-07-08 09:00 UI Delivery Execution Guard

## Purpose

This is the short current-control document for the 09:00 WOW mini program UI delivery. It exists to stop future Codex sessions and agents from drifting back into old UI-system rebuild work, old pass scorecards, or screenshot-free claims.

Read this file immediately after `docs/roadmap.md` and before acting on older plans.

## Current Goal

Ship a demonstrable, stable rescue version of the mini program UI before 09:00.

This is not the same goal as:

- full UI system rebuild;
- pass36/pass37 repair;
- 90% imagegen recreation;
- old owner registry completion;
- old implementation-permit completion;
- static test green-only completion.

## Source Of Truth Order

1. `docs/roadmap.md` top entries for `2026-07-08`.
2. `docs/plans/2026-07-08-0900-ui-delivery-execution-guard.md`.
3. `docs/plans/2026-07-08-wow-mini-program-0900-ui-delivery-goal.md`.
4. `docs/plans/2026-07-08-0900-ui-rescue-context-lock.md`.
5. Current `app.json` registered pages and real mini program runtime screenshots.
6. Older plans only as historical evidence.

If these conflict, the newest roadmap entry and this execution guard win.

## Non-Negotiable Scope

All pages registered in `app.json` are in scope. A page may be `pass`, `risk`, or `fail`, but it must not disappear from the delivery record.

P0 pages must be demonstrable with real mini program screenshots and no obvious broken layout:

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

P2 page must not white-screen or hang:

- `pages/builds/intel`

## Known System Failures To Correct

Treat these as system problems, not isolated pixels:

- bottom tabBar labels missing, icons stretched, bar glued to the bottom, or safe-area spacing wrong;
- news channel icons/text still visually off after repeated edits;
- current spec workbench status shield split into loose background plus floating glyph;
- workbench module cards cramped or unreadable;
- Chickenbro/intelligent-analysis input/header/buttons clipped, floating, or hidden behind capsule/tabBar;
- profile top panel visually split by broken material layering;
- fixed bottom controls covered by tabBar;
- DevTools page unresponsive or login state destabilized by validation workflow.

## Work Rules

Do:

- fix global layout first: nav safe area, page gutter, scroll region, bottom tabBar, fixed action/input avoidance;
- prefer stable page-level rescue layout over failed abstractions when time is short;
- keep real product information and key actions visible;
- use simplified stable icons/components if current visual assets keep failing;
- record real screenshot path, page route, pass/risk/fail, and DevTools action state;
- update tests only after the runtime UI is stable, and only when tests protect the new correct behavior.

Do not:

- continue old pass36/pass37 pixel patching;
- claim fixed without a real mini program screenshot or explicit risk note;
- restore a broken layout only to satisfy stale tests;
- use browser-only previews as final UI evidence;
- create empty shells by deleting core information;
- fake WeChat status bar, time, battery, Wi-Fi, or capsule chrome;
- split one semantic status visual into separate unmanaged layers;
- run broad DevTools open/close/compile/cache-clear loops.

## DevTools Safety

The user's logged-in WeChat DevTools session is an asset.

Forbidden by default:

- close DevTools;
- restart DevTools;
- clear cache or storage;
- switch appid;
- switch project;
- delete DevTools user data;
- run repeated lifecycle automation.

Allowed low-disturbance checks:

- connect to an already available automator endpoint;
- run one short route or one small batch;
- capture screenshot;
- log page, action, screenshot, pass/risk/fail, and whether the page became unresponsive.

If DevTools is not safe, mark `captureSafe=false` and continue only with code-side risk notes. Do not mark runtime verification complete.

## Evidence Rules

`runtime_verified` requires:

- real WeChat mini program screenshot;
- route and viewport/device context;
- short route smoke or direct open result;
- pass/risk/fail label;
- DevTools action ledger with no forbidden lifecycle action.

Not sufficient:

- static tests only;
- `git diff --check` only;
- browser harness only;
- old scorecard;
- subjective score;
- CSS reasoning without runtime evidence.

## Completion Bar

Do not mark the goal complete until:

- all `app.json` pages have screenshot evidence or explicit fail/risk entries;
- all P0 pages have no obvious broken layout in real screenshots;
- bottom tabBar has visible icons and labels on real tab pages;
- workbench blocked/ready state visual is not split or overlaid incorrectly;
- Chickenbro/intelligent-analysis input and action area are stable above tabBar;
- DevTools was not disturbed by forbidden lifecycle actions;
- remaining issues are listed as risks rather than hidden.

## Codex Goal Text

Use this text when starting target/goal mode:

```text
在 2026-07-08 09:00 前交付 WOW 小程序 UI 救火版。以 docs/roadmap.md 顶部 2026-07-08 条目、docs/plans/2026-07-08-0900-ui-delivery-execution-guard.md、docs/plans/2026-07-08-wow-mini-program-0900-ui-delivery-goal.md、docs/plans/2026-07-08-0900-ui-rescue-context-lock.md 为当前控制面；旧 UI 系统重建、pass36/pass37、旧 scorecard、旧 owner registry、旧 implementation permit 和 imagegen 整页图只作为历史证据，不驱动本轮验收。

核心目标：覆盖 app.json 注册的全部页面；P0 页面真实微信小程序截图无明显崩坏；P1 页面可打开可读；P2 不白屏不卡死；底部 tabBar 图标和文字稳定；首页、职业专精、当前专精工作台、天赋模拟、装备详情、SimC、炸鸡队长/智能分析、我的页面可演示；DevTools 登录态和稳定性不被验证流程破坏。

工作流：先修全局壳、safe area、底部 tabBar、页面 gutter、滚动区、输入栏和 fixed bottom 避让；再逐个 P0/P1 页面用真实截图验证。禁止继续旧局部像素修补、禁止主观宣布通过、禁止为了旧测试恢复错误结构、禁止删核心信息做空壳。没有真实小程序截图只能标 risk，不能标 runtime_verified/final_accepted。

DevTools：默认使用用户已登录已打开的开发者工具；禁止自动关闭、重启、清缓存、切 appid、切项目、删除用户目录或反复 open-close-compile；每次真实验证只跑短路径，并记录页面、截图、pass/fail/risk、是否卡死和 action ledger。
```
