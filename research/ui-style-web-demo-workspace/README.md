# Chickenbro Web workspace demo

这是从独立 projectless 原型接回 `codex/ui-style-research` 的候选视觉版本，保留为独立目录，未覆盖同级的 `research/ui-style-web-demo/` 旧稿。

## 交接记录

- 来源线程：`codex://threads/01a065e7-add3-7fb3-98ad-822fe05b8eeb`
- 来源候选：`/Users/boyuan/Documents/Codex/2026-09-03/hand-drawn-mascot-logo/web-header-prototype`
- 本次纳入：源码、方案文档、素材、测试、Sites 配置和构建输出；旧稿继续原样保留。
- 运行边界：这是分支内的已确认视觉候选包，不替换 `apps/mini-taro` 入口，不改变生产 WebSim 或 Active 版本。

## 当前方案

- 顶部 banner 固定，不参与页面滚动。
- 左侧栏承载历史对话列表；咕咕从 logo 掉落后只在左侧栏活动。
- 右侧为对话区域，背景插画只放在右侧，并保留低饱和、低对比的阅读层级。
- “为了部落！”皮肤可逆切换；萨尔位于插画左侧，奥格瑞玛城门位于右侧，云层使用轻微漂移动效。
- 咕咕面向右侧背景，形成“宠物在前景、插画在远景”的画中画透视关系。

## 目录

- `src/App.jsx`：工作区结构、模式切换、皮肤切换、咕咕掉落/重播。
- `src/appState.js`：文案、历史会话、皮肤和插画可见性参数。
- `src/styles.css`：固定 banner、左栏/右栏布局、透视层和响应式样式。
- `public/assets/`：咕咕、萨尔/奥格瑞玛和云层素材。
- `design-qa.md`：最近一次桌面端与移动端验收记录。

## 验证状态

该版本在接回前已完成：

- `node --test tests/*.test.mjs`：10 passed
- `npm run test:sites`：4 passed
- `npm run build`：通过
- 桌面端 1440×1024、移动端 390×844：无横向溢出，插画位于右侧主区域，咕咕位于左侧栏。

纳入当前分支后的环境复核（2026-09-04）：

- `node --test tests/*.test.mjs`：10 passed
- `npm run test:sites`：4 passed
- `vite build` + `node scripts/prepare-sites-build.mjs`：通过，复用原始候选目录中已存在的同版本依赖，本次未安装依赖。
- `dist/` 已按当前源码刷新；候选目录自身仍未安装 `node_modules`，直接执行 `npm run build` 仍需先补齐依赖。

这是视觉候选 demo，不等同于生产 WebSim 或 Active 版本；后续若确认方向，再把布局和状态逐项移植到原项目的正式前端入口。
