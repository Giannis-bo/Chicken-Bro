# 2026-07-08 09:00 UI Delivery Handoff Lock

## Purpose

This is the shortest current-control document for the 09:00 WOW mini program UI delivery.

Every Codex session, subagent, or reviewer entering this repository before the 09:00 delivery must read this file before older UI plans, scorecards, component registries, implementation permits, design references, or test expectations.

## Current Codex Goal

Use this exact goal text when starting Codex target/goal mode:

```text
在 2026-07-08 09:00 前交付 WOW 小程序 UI 救火版。

当前控制面只认：
1. docs/roadmap.md 顶部 2026-07-08 09:00 相关条目；
2. docs/plans/2026-07-08-0900-ui-delivery-handoff-lock.md；
3. docs/plans/2026-07-08-0900-ui-delivery-execution-guard.md；
4. docs/plans/2026-07-08-wow-mini-program-0900-ui-delivery-goal.md；
5. docs/plans/2026-07-08-0900-ui-rescue-context-lock.md；
6. app.json 当前注册页面和真实微信小程序截图。

旧 UI 系统重建、pass36/pass37、旧 scorecard、旧 owner registry、旧 implementation permit、browser-only demo、imagegen 整页参考图、旧静态测试期望，只能作为历史证据，不能驱动本轮验收。

核心目标：覆盖 app.json 注册的 14 个页面；P0 页面真实微信小程序截图无明显崩坏；P1 页面可打开可读；P2 页面不白屏不卡死；底部 tabBar 图标和文字稳定；首页、职业专精、当前专精工作台、天赋模拟、装备详情、SimC、炸鸡队长/智能分析、我的页面可演示；微信开发者工具登录态和稳定性不被验证流程破坏。

工作流：先修全局壳、safe area、底部 tabBar、页面 gutter、滚动区、输入栏和 fixed bottom 避让；再逐个 P0/P1/P2 页面用真实截图验证。禁止继续旧局部像素修补，禁止主观宣布通过，禁止为了旧测试恢复错误结构，禁止删核心信息做空壳。没有真实微信小程序截图只能标 risk，不能标 runtime_verified 或 final_accepted。

DevTools：默认使用用户已登录、已打开的微信开发者工具。禁止自动关闭、重启、清缓存、切 appid、切项目、删除用户目录、反复 open-close-compile。每次真实验证只跑短路径，并记录页面、截图、pass/fail/risk、是否卡死和 action ledger。
```

## App Page Scope

`app.json` currently registers 14 pages. All are in delivery scope:

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

P0 must be visually demonstrable from real mini program screenshots:

- `pages/news/news`
- `pages/builds/builds`
- `pages/builds/workbench`
- `pages/builds/talent-simulator`
- `pages/builds/detail`
- `pages/simulator/simulator`
- `pages/simulator/simc`
- `pages/profile/profile`

P1 must open and remain readable:

- `pages/news/list`
- `pages/news/detail`
- `pages/simulator/chickenbro`
- `pages/simulator/tasks`
- `pages/simulator/task-detail`

P2 must not white-screen or hang:

- `pages/builds/intel`

## Known Failures That Must Not Be Hidden

Treat these as system failures, not isolated pixels:

- bottom tabBar missing labels, stretched icons, unsafe bottom spacing, or fake chrome;
- news channel dock icon/text misalignment;
- workbench blocked shield split into unmanaged background plus glyph;
- workbench cards cramped, overlaid, or unreadable;
- Chickenbro/intelligent-analysis header, buttons, message area, or input clipped by capsule/tabBar;
- profile top identity area visually split by broken material layering;
- fixed bottom actions covered by tabBar;
- DevTools page unresponsive or login state destabilized by validation workflow.

## Current Work Rules

Do:

- fix global shell, safe area, tabBar, gutters, scroll regions, and input/fixed-bottom avoidance first;
- prefer a stable page-level rescue layout over a failed abstraction when time is short;
- keep core product information and actions visible;
- simplify unstable visual assets when needed instead of repeatedly patching misaligned material;
- use real WeChat mini program screenshots as acceptance evidence;
- update stale tests only after the runtime UI is stable.

Do not:

- continue old pass36/pass37 pixel patching;
- claim success from CSS reasoning, browser preview, or static tests alone;
- restore broken UI to satisfy stale tests;
- create empty shells by deleting important information;
- split one semantic status visual into separate unmanaged layers;
- fake WeChat status bar, time, battery, Wi-Fi, or capsule chrome;
- disturb DevTools login state with lifecycle automation.

## Evidence Required

A page can be called `runtime_verified` only when there is:

- a real WeChat mini program screenshot path;
- the page route and viewport/device context;
- pass/fail/risk status;
- short route smoke or direct-open result;
- DevTools action record proving no forbidden lifecycle action.

If any item is missing, the page remains `risk` or `draft`.

## Stop Conditions

Stop implementation and fix the workflow first if:

- DevTools becomes unresponsive again;
- login state is lost after an automation action;
- screenshots do not match what the code change claimed;
- a fix only moves a problem between pages;
- a page looks stable only by deleting core content or hiding broken sections.
