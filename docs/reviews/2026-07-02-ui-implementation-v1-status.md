# UI Implementation v1 Status

## Scope

本轮目标是把三张已确认的 imagegen 高质量目标图拆成真实小程序组件语言, 并落到以下关键场景:

- 资讯首页首屏与下滚重点列表。
- 职业专精 tab 的工作台入口与旧四入口下沉。
- 当前专精工作台首屏、四模块状态带和证据下滚区。

## Implemented

- `pages/news/news.*`
  - 新增 `今日情报台` 控制台头部。
  - hero、频道和重点列表新增真实图片槽与文字 fallback。
  - 当前资讯 payload 没有真实图片字段时, 不使用 generated 图或假新闻配图。
  - 今日重点列表保留 rank、频道、来源、日期、摘要和动作, 不回退到纯黑文本卡片。

- `pages/builds/workbench.*`
  - 移除旧 `assets/generated/ui-redesign/20260701/*` 整图背景。
  - 用 CSS 金属面板、状态边、专精 medallion 和 2x2 模块卡片承接 `workbench-target.png` 的视觉语言。
  - 四模块卡片保留图标槽、状态、指标、说明和动作。
  - 证据区继续展示来源、覆盖、模板、检查时间和 blocker。

- `pages/builds/workbench-state.js`
  - SimC fallback 从 `S` 改为 `Sim`, 避免被误读成评级。
  - 继续保持 `canShowStrongResult: false`, 不在工作台输出 DPS、综合评分、S/A 级或提升优先级。

- `docs/design/2026-07-02-imagegen-to-miniprogram-layout-decomposition.md`
  - 补齐 news/builds/workbench 三页的目标图拆组件规则。
  - 明确 imagegen 只作为结构、材质、布局语言来源, 不作为真实图标、状态、评分或业务事实来源。

## Verification

- `node --test tests/news-page-style.test.js tests/builds-workbench-state.test.js tests/builds-page.test.js tests/ui-style-guide-implementation.test.js`
- `node --test tests/builds-page.test.js tests/news-page-style.test.js tests/frontend-api-client.test.js tests/ui-style-guide-implementation.test.js tests/simulator-page.test.js`
- `git diff --check`
- 静态扫描范围: `pages/news`, `pages/builds/workbench.*`, `pages/builds/builds.*`
  - 未发现 `assets/generated`, `ui-redesign`, `iconFallback: 'S'`, `DPS`, `综合评分`, `S 级`, `A级`, `提升优先级`。

## Screenshot Status

官方小程序截图已完成。过程保持当前微信开发者工具实例不关闭、不重启:

- 当前 DevTools HTTP server 端口为 `46952`。
- 原有 automator 端口 `9852` 可读页面状态, 但 `app.screenshot` 后续超时。
- `cli islogin --port 46952` 返回 `{"login":true}`。
- 在不关闭或重启 DevTools 的前提下, 通过 `cli auto --project ... --port 46952 --auto-port 9853` 新开 automation 端口, 并用 `ws://127.0.0.1:9853` 完成截图。
- `manifest.json` 状态为 `complete`, 覆盖 14 个真实小程序场景, 且每张截图通过非黑图视觉检查。

证据:

- `artifacts/miniprogram-screenshots/20260702-ui-implementation-v1/manifest.json`
- `artifacts/miniprogram-screenshots/20260702-ui-implementation-v1/screenshots/*.png`
- `artifacts/miniprogram-screenshots/20260702-ui-implementation-v1/comparison-main-current-target-implemented.png`
- `artifacts/miniprogram-screenshots/20260702-ui-implementation-v1/comparison-all-scenes-current-implemented.png`

完成场景:

- 资讯首页首屏与下滚重点列表。
- 职业专精 tab。
- 当前专精工作台首屏、证据展开、blocked 装备态、partial 天赋态、ready 态。
- 天赋模拟器、装备模拟、SimC、任务列表、炸鸡队长、我的模板。

## Comparison Artifacts

- 主三列对比: `artifacts/miniprogram-screenshots/20260702-ui-implementation-v1/comparison-main-current-target-implemented.png`
- 全场景 before/after: `artifacts/miniprogram-screenshots/20260702-ui-implementation-v1/comparison-all-scenes-current-implemented.png`
- 现状来源: `artifacts/miniprogram-screenshots/20260630-workbench-redesign/screenshots/*.png`
- 目标来源: `artifacts/ui-visual-targets/20260702-pretty-direction/*.png`
- 实现来源: `artifacts/miniprogram-screenshots/20260702-ui-implementation-v1/screenshots/*.png`
