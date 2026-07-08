# 2026-07-08 09:00 UI Rescue Context Lock

## Purpose

This document is the current handoff guardrail for the WOW mini program UI rescue before the 09:00 delivery.

Future Codex sessions and agents must read this file before acting on old UI system rebuild plans, pass scorecards, owner registries, implementation permits, or imagegen reference artifacts. The immediate goal is not to prove the previous architecture correct. The goal is to ship a usable, stable, visually acceptable mini program under time pressure without hiding broken UI behind static tests.

## Current Source Of Truth

Read in this order:

1. `docs/roadmap.md` top entry for `2026-07-08 09:00 UI delivery rescue`.
2. `docs/plans/2026-07-08-wow-mini-program-0900-ui-delivery-goal.md`.
3. This context lock.
4. Only then consult older design/system docs as historical evidence.

Older documents are not deleted because they contain useful evidence, but they must not override this rescue context.

## Current Delivery Objective

Before 09:00, deliver a demonstrable mini program where:

- All 14 `app.json` pages can open or have an explicit fail/risk record.
- P0 pages have real WeChat mini program screenshots with no obvious broken layout.
- The bottom tabBar is stable: visible icons, visible labels, correct safe-area spacing, no fake system chrome.
- Core flows can be demonstrated: news home, builds tab, current spec workbench, talent simulator, gear detail, SimC, chickenbro/intelligent analysis, profile.
- DevTools validation does not destroy login state, close/restart tools, clear cache, switch appid/project, or run long repeated automation loops.

## Current P0 Visual Failures To Fix First

These are not isolated pixel problems. Treat them as layout/system failures:

- Bottom tabBar: labels missing, icons stretched or too low, bar glued to screen bottom, safe-area mismatch.
- News channel dock: `综合 / 官方 / 更新 / 活动 / 社区 / 攻略` icon/text alignment remains visibly off after many fixes.
- Current spec workbench: blocked shield visual was repeatedly split/misaligned; it must be one stable component or one complete asset with fixed box and centered glyph.
- Workbench module cards: content stacks and micro badges are too cramped; use readable fixed card structure instead of tiny nested labels.
- Chickenbro/intelligent analysis: header/buttons/input are clipped or overlaid by capsule/safe area; input must sit above tabBar and remain dynamic, not frozen in the middle of the page.
- Profile: top identity area has visible left/right split from background/material layering.
- Several pages still risk fixed bottom actions being covered by custom tabBar.
- WeChat DevTools has repeatedly shown page unresponsive; validation must be short and logged.

## Work Style Reset

Do:

- Use real rendered evidence whenever possible.
- Prefer simple, robust page-level layout when failed component abstraction blocks delivery.
- Keep core information visible; do not make empty shells to pass screenshots.
- Replace unstable image/icon compositions with stable simplified components when time is short.
- Record screenshots, route, pass/fail/risk, and DevTools action ledger.
- Treat static tests as guardrails only; real mini program screenshots are the acceptance signal.

Do not:

- Continue old pass36/pass37 pixel patching.
- Claim a page is fixed without a real screenshot or explicit risk note.
- Restore wrong structures only to satisfy outdated tests.
- Re-enter broad UI system rebuild, skill comparison, or 90% imagegen recreation work.
- Use page-private overlays that fake status bar/time/battery/Wi-Fi.
- Split a single semantic status visual into loose background + floating glyph.
- Let fixed bottom controls overlap the custom tabBar.
- Run DevTools close/restart/cache clear/project switch/appid switch/delete-user-data operations.

## Evidence Rules

`runtime_verified` or `final_accepted` requires real WeChat mini program evidence.

Allowed proof:

- Real screenshot path.
- Page route.
- Viewport/device.
- Short route smoke result.
- Pass/fail/risk label.
- DevTools action ledger showing no forbidden lifecycle action.

Not enough proof:

- `git diff --check`.
- Static unit tests only.
- Browser-only preview.
- Old scorecard.
- Subjective score.
- "Looks fixed from CSS."

## Test Interpretation

Some old tests encode pre-rescue structure. If they fail because they expect an old wrong layout, do not roll back the rescue fix. Instead, record the mismatch and update the test only after the UI is stable.

Still run lightweight checks for syntax, JSON validity, missing page files, and obvious static regressions.

## DevTools Rule

Default stance: preserve the user's logged-in DevTools session.

Allowed low-disturbance actions:

- Health probe.
- Foreground/activate existing DevTools once.
- Connect to an already available automator endpoint.
- Navigate one short path and screenshot.

Forbidden by default:

- Close/reopen DevTools.
- Clear cache or storage.
- Switch appid.
- Switch project.
- Delete user directories.
- Repeated compile/open/close loops.

If screenshot automation is not safe, mark `captureSafe=false`, explain why, and continue with code-side fixes plus explicit risk. Do not pretend runtime verification happened.

## 09:00 Codex Goal Text

Use this as the Codex goal for target/goal mode:

```text
在 2026-07-08 09:00 前交付 WOW 小程序 UI 救火版。严格以 docs/roadmap.md 顶部 09:00 UI delivery rescue、docs/plans/2026-07-08-wow-mini-program-0900-ui-delivery-goal.md、docs/plans/2026-07-08-0900-ui-rescue-context-lock.md 为当前控制面；旧 UI 系统重建、pass36/pass37、旧 scorecard、旧 owner registry、旧 implementation permit 和 imagegen 整页图只作为历史证据，不驱动本轮验收。

核心目标：14 个 app.json 页面全部可打开或有明确 fail/risk 记录；P0 页面真实微信小程序截图无明显崩坏；底部 tabBar 稳定；首页、职业专精、当前专精工作台、天赋模拟、装备详情、SimC、炸鸡队长/智能分析、我的页面可演示；DevTools 登录态和稳定性不被验证流程破坏。

工作流要求：先修全局壳、safe area、底部 tabBar、页面 gutter、滚动区、输入栏和 fixed bottom 避让；再逐个 P0 页面用真实截图验证。禁止继续旧局部像素修补、禁止主观宣布通过、禁止为了旧测试恢复错误结构、禁止删核心信息做空壳。没有真实小程序截图只能标 risk，不能标 runtime_verified/final_accepted。

DevTools 要求：默认使用用户已登录已打开的开发者工具；禁止自动关闭/重启/清缓存/切 appid/切项目/删除用户目录/反复 open-close-compile；每次真实验证只跑短路径并记录页面、截图、pass/fail/risk、是否卡死和 action ledger。
```
