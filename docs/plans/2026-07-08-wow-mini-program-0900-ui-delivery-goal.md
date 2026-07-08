# WOW 小程序 09:00 UI 交付救火 Goal

## Summary

当前目标切换为 `09:00 可交付 UI 救火`。这不是继续完整 UI 系统重建，也不是继续旧 pass / 旧 scorecard / 旧组件链局部修补。

交付定义：14 个 `app.json` 注册页面可打开，P0 页面真实微信小程序截图无明显崩坏，底部菜单稳定，核心路径能演示，微信开发者工具不再因打开项目或进入核心页面稳定卡死。

紧急交付不是错误交付。本轮必须快速纠正工作流：抛弃拖后腿的旧限制、旧测试保护的错误结构、失败组件链和主观验收；但不允许用“紧急”作为乱改、删核心信息、做空壳页面或糊弄视觉的理由。

## Active Scope

`app.json` 当前注册页面全部纳入交付范围：

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

## Priority Tiers

### P0 Must Not Break

这些页面必须能作为 09:00 演示主线，真实截图不能有明显遮挡、贴边、横向溢出、底部菜单错误、胶囊遮挡、输入栏漂移、核心操作不可见：

- `pages/news/news`
- `pages/builds/builds`
- `pages/builds/workbench`
- `pages/builds/talent-simulator`
- `pages/builds/detail`
- `pages/simulator/simulator`
- `pages/simulator/simc`
- `pages/profile/profile`

### P1 Must Open And Read

这些页面必须可打开、可读、可返回；视觉可以不精修，但不能白屏、卡死、布局明显崩：

- `pages/news/list`
- `pages/news/detail`
- `pages/simulator/chickenbro`
- `pages/simulator/tasks`
- `pages/simulator/task-detail`

### P2 No White Screen

这些页面不作为主演示重点，但不能白屏、卡死或破坏导航：

- `pages/builds/intel`

## Current Failure Diagnosis

- 静态测试曾多次通过，但真实微信小程序截图仍然错误；测试不能替代真实 UI。
- 旧组件化路线在微信自定义组件宿主、slot、safe area、`scroll-view` 高度、底部 tab 避让上反复失控。
- 旧 pass / scorecard / owner registry / implementation permit 文档现在只能作为历史证据或参考，不能驱动 09:00 交付。
- 失败组件链不能继续作为默认选择，包括但不限于导致真实截图明显崩坏的 shell、surface、chat 嵌套。
- imagegen 目标图仍是视觉方向参考，但不能直接当实现，也不能让实现退化为空壳或素材乱堆。
- DevTools 登录态和卡死问题是交付 blocker，不是旁枝问题。

## Delivery Principles

- 真实小程序截图优先级高于静态测试。
- 交付可见质量优先级高于架构洁癖。
- 稳定页面级布局可以优先于失败组件复用。
- 不为了旧测试恢复错误结构。
- 不为了“稳定”删除核心信息或做空页面。
- 不继续在用户已指出失败的方向上反复 patch。
- 不新增大规模设计探索、不新增大组件体系、不做全套 90% 还原承诺。
- 保留已确认的暗黑魔兽、黑金、厚重游戏 UI、App 感方向。
- 能用稳定块级布局解决的问题，不赌复杂 flex / nested scroll / custom component height propagation。

## UI Correctness Evidence

09:00 前不要求完整 overlay / red-zone / 90% 还原，但必须提交真实证据：

- 每个注册页面至少 1 张真实微信小程序截图。
- P0 页面至少包含首屏截图；有关键交互态的页面需补关键态截图。
- 截图 manifest 必须标记 `pass / fail / risk`。
- P0 route smoke 至少覆盖：进入、返回、tab 切换、关键主按钮不跳错、不卡死。
- 验收 checklist：
  - 无白屏。
  - 无明显横向溢出。
  - 无明显遮挡。
  - 无明显贴边。
  - 微信胶囊不压内容。
  - 底部 tabBar 图标和文字可见。
  - 输入栏在合理位置。
  - 核心操作可见。
  - 文字可读。
  - 真实功能入口没有被删掉。

禁止把以下内容当作 UI 正确证明：

- 仅静态测试通过。
- 仅 `git diff --check` 通过。
- 仅浏览器 HTML demo。
- 仅主观评分。
- 旧 pass scorecard。
- 没有真实小程序截图的“看起来应该好了”。

## DevTools Stability Plan

微信开发者工具卡死和登录态失效必须作为 P0 blocker 处理。

### 2026-07-08 07:26 Runtime Incident Addendum

当前事实状态：

- `node --test tests/navigation-bar.test.js tests/news-page-style.test.js tests/simulator-page.test.js tests/builds-page.test.js` 已通过，覆盖底部 tabBar、首页频道 dock、工作台状态槽、智能分析输入栏等救火守门。
- `node --check` 和 `git diff --check` 已通过本轮核心改动。
- 真实微信开发者工具自动化 endpoint 仍可连接，`Tool.getInfo` 成功，推荐 automator 端口为 `9854`。
- 但最新单页真实截图 `pages/news/news` 在 `App.captureScreenshot` 阶段 10 秒超时；随后只读 `evaluate(getCurrentPages())` 也超时。
- 因此当前不能把任何截图缺失页面标记为 `runtime_verified` 或 `final_accepted`。
- 本次自动化没有执行关闭、重启、清缓存、切 appid、切项目、删除用户目录；`forbiddenActionsUsed` 为空。

当前判断：

- 这不是单个像素或单页 UI 问题，运行时已经进入冻结态。
- 直接继续反复截图或批量 route smoke 会放大 DevTools 卡死和登录态风险。
- 已发现并修复一个全局低风险问题：custom tabBar 与页面 `syncTabBarSelected` 改为幂等，避免 `onShow / attached` 重复 `setData`。
- 仓库已有 DevTools shadow 机制，目的就是避免源码目录被频繁写入触发 hot-compile storm；但当前 goal 禁止自动切项目，不能私自切到 shadow 当作通过证据。

后续执行纪律：

- 用户或交付负责人重新编译/恢复 DevTools 后，必须先跑单页 route probe，再跑单页截图，不允许直接跑 14 页批量。
- 如果现有 DevTools 仍冻结，优先方案是用户确认后打开已同步的干净 shadow 运行目录；这属于“切项目”，需要显式记录，不得静默执行。
- 在真实截图恢复前，只能声明 `static/browser precheck passed` 和 `runtime blocked/risk`，不能声明 UI 已覆盖全部页面或交付完成。

### 禁止动作

- 禁止自动关闭 DevTools。
- 禁止自动重启 DevTools。
- 禁止清缓存。
- 禁止切 appid。
- 禁止切项目。
- 禁止删除用户目录。
- 禁止粗暴自动化反复 open / close / compile。

### 低扰动验证

- 默认使用用户已登录、已打开的 DevTools。
- 每次只验证一个目标页面或一条短路径。
- 每次真实验证记录当前页面、操作、截图、是否卡死。
- 如果卡死，立即停止 UI patch，记录最近改动文件和当前页面，把卡死当 blocker 修。

### 代码侧降载

优先排查和修复：

- 页面级大图过多或未懒加载。
- `setData` 高频写入大对象。
- 重复 `onLoad/onShow` 请求。
- 自定义组件深度嵌套。
- `scroll-view` 与 flex/grid 高度互相赌行为。
- 长列表一次性渲染过多节点。
- 未使用组件仍在 page json 注册。
- 装饰素材压过业务内容。

## Page Delivery Requirements

### 首页资讯

- 顶部资讯首屏完整。
- 轮播和今日重点保留。
- 频道 dock 六入口稳定：`综合 / 官方 / 更新 / 活动 / 社区 / 攻略`。
- 若 PNG 图标持续偏移，允许降级为稳定简化图标或文字版，不再继续微调错误素材。
- 底部 tabBar 清晰可用。

### 职业专精

- 保留职业专精主入口。
- 当前专精工作台入口清晰。
- 旧入口可下沉但不能丢失。
- 不允许卡片内容过度截断到不可读。

### 当前专精工作台

- 首屏回答“当前能否模拟，为什么”。
- `暂不可模拟 / 可提交模拟 / 部分可用 / 来源参考` 等状态必须真实、可读。
- 盾牌/叹号必须作为完整状态视觉或完整图片，不再拆成会错位的底图 + glyph。
- 工作流状态卡不能堆叠混乱。
- 如果复杂驾驶舱继续坏，降级为稳定三段：当前专精、模拟结论、工作流状态。

### 天赋模拟

- 页面可打开、不溢出。
- 职业/专精/天赋信息不乱造。
- 保存、导入、重置等关键入口可见。
- 不追求炫酷天赋树 90% 还原，优先可演示不坏。

### 装备详情

- 装备读取、槽位、模板、SimC readiness 信息可读。
- 不显示无证据的 DPS、S/A 级、综合评分、提升优先级。
- 主操作可见，不被底部菜单遮挡。

### SimC

- 可从工作台或 tab 进入。
- 输入准备、模板选择、提交/校验入口可见。
- 不直接输出无证据结论。
- 页面不因长内容或底部按钮卡死。

### 炸鸡队长 / 智能分析

- 不是空壳。
- 首屏至少包括队长身份、证据边界说明、一条欢迎消息、输入栏、新话题、发送。
- 输入栏稳定在底部 tabBar 上方。
- 微信胶囊不遮挡标题或按钮。
- 不暴露 raw `answerSource / confidence / job.status`。
- 如果复杂证据抽屉不稳，先降级为稳定聊天界面。

### 任务与任务详情

- 可打开、可返回。
- 任务列表和任务结果可读。
- 不遮挡底部菜单。
- 不泄漏 raw SimC 崩溃日志。

### 我的

- 登录/用户状态区域不能左右割裂。
- 模板、身份、同步入口可读。
- 不触发 DevTools 登录态破坏动作。

## Execution Order

1. 冻结错误方向：停止旧组件链和旧 scorecard 驱动。
2. 建立真实页面清单和截图 manifest。
3. 先修全局壳：导航安全区、底部 tabBar、页面 gutter、滚动区、输入栏。
4. P0 页面逐个真实截图修复。
5. P1 页面打开和可读性修复。
6. P2 页面白屏/卡死检查。
7. 输出 09:00 交付清单和已知风险。

## Explicit Non-Goals

- 不完成完整 UI 系统重建。
- 不承诺所有页面 90% imagegen 还原。
- 不做完整 overlay / red-zone 工作流。
- 不做大规模新 imagegen 探索。
- 不重构后端接口。
- 不追求所有旧测试恢复绿色。
- 不把旧目标文档改写成当前事实。

## Acceptance Criteria

- 14 个注册页面均有真实小程序截图或明确 fail/risk 记录。
- P0 页面真实截图无明显崩坏。
- 底部 tabBar 在至少 2 个 tab 页面真实截图中正常。
- `pages/simulator/simulator` 不再是空壳，输入栏位置合理。
- 首页频道 dock 不再明显歪或挤；如降级，降级方案稳定可解释。
- 工作台 `暂不可模拟` 态可读，状态图不分裂。
- DevTools 未因本轮验证流程被主动关闭、清缓存、切项目或破坏登录态。
- 所有未完成项在最终交付清单中标为 risk，不伪装完成。
