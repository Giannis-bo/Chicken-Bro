# WOW UI Delivery Rescue Parallel Plan

## Summary

当前 UI 交付质量未达标，停止继续做单点 CSS 调参。本轮切换为并行救火交付：用浏览器同构证据锁定真实页面接入问题，再按 surface 拆分修复，最后用同一套 browser audit、组件 crop、静态测试和用户反馈截图对齐验收。

本轮不使用 `computer-use`，不主动关闭、重启、清缓存或切换微信开发者工具。真实小程序验证只在用户明确允许时作为最终截图补证；日常迭代先用浏览器同构 harness。

## Delivery Scope

- 资讯首页：恢复轮播视觉、修复频道 dock icon/文字居中、修复底部 tabBar 图标资源拉伸和文字缺失风险。
- 职业专精 / 工作台入口：修复页面接入边距、判断对象列宽、右侧状态文案截断、工作流卡片信息密度。
- 智能分析 / 炸鸡队长：修复输入区遮挡、状态条与输入条层级、底部 tabBar/safe-area 预留、长消息滚动。
- 验收体系：补齐真实页面接入层 browser audit，避免“组件 fixture 通过但模拟器页面仍坏”的错判。

## Parallel Agents

### Agent 1: News Surface

- Owner: `pages/news/*`、`components/channel-dock/*`、`components/ranked-feed/*`、`assets/tabbar/*`。
- Fixes:
  - banner fallback 在 `visualUrl` 失效或未加载时仍显示低语义背景。
  - `ChannelDock` 宽度、icon socket、glyph center、label baseline 回到合同范围。
  - tabBar PNG 资源符合微信尺寸和透明边界，不造成拉伸或文字消失。
- Evidence:
  - `run-pass37-news-implementation-layout-audit.js`
  - news component crops
  - tabBar asset preview / metadata

### Agent 2: Builds And Workbench

- Owner: `pages/builds/builds.*`、`pages/builds/workbench.*`、`components/builds-tab-surface/*`、`components/workbench-cockpit-surface/*`、共享状态/模块组件的必要样式。
- Fixes:
  - 页面级 gutter 与 panel 内边距统一。
  - “判断对象 / 证据范围 / 输出边界”等列宽不压缩、不异常换行。
  - 天赋/装备/SimC/队长入口保留且可扫读。
  - 工作台模块字体、行高、状态视觉不再过小或错位。
- Evidence:
  - builds tab component precheck
  - 新增 page-integration browser audit 或等价截图

### Agent 3: Chickenbro And Simulator

- Owner: `pages/simulator/simulator.*`、`pages/simulator/chickenbro.*`、`components/chat-shell/*`、`components/chickenbro-coach-surface/*`。
- Fixes:
  - inputbar 不遮挡消息、不遮挡状态条。
  - scroll 区底部留白与 tabBar/safe-area 一致。
  - 空态、生成中、失败态、长消息、工作台上下文承接都能正常排版。
- Evidence:
  - chickenbro component precheck
  - 新增 page-integration browser audit 或等价截图

### Agent 4: Read-only QA

- Owner: 不改代码。
- Checks:
  - 找出组件 fixture 与真实页面模拟器不一致的根因。
  - 列出最快交付闸门和剩余风险。
  - 复核 tabBar、fallback、页面私有布局、fixed input 层级。

## Main Thread Responsibilities

- 维护统一交付闸门。
- 合并并审查各 agent 结果。
- 跑最终命令：
  - `node --test tests/news-page-style.test.js tests/builds-page.test.js tests/simulator-page.test.js tests/ui-style-guide-implementation.test.js tests/navigation-bar.test.js`
  - `git diff --check`
- 输出现状 / 修复后截图路径、失败项、不能标记通过的原因。

## Acceptance Gate

本轮不能再用主观分数通过。交付至少满足：

- 浏览器同构截图覆盖 news、builds/workbench、simulator/chickenbro、tabBar asset preview。
- 每个用户反馈点都有对应证据：修复截图、测量结果或明确 remaining blocker。
- 组件 crop 与真实页面接入层都通过基础布局检查。
- 无明显横向溢出、顶边、压缩按钮、内部文字遮挡、重复系统 chrome。
- 若微信开发者工具不可稳定自动截图，必须明确标记为 `browser_verified_only`，不能写成 `runtime_verified`。
