# WoW 小程序真实页面前端 CR

## 结论

前几轮概念图不再作为依据。当前优化应从真实小程序页面出发, 先做能被截图和测试证明的小步改版。

本轮最高价值第一刀: 资讯首页滚动后的「今日重点」列表。

原因:

- 用户最早明确指出该区域“全黑”, 问题真实存在。
- 只涉及 `pages/news/news.*`, 不改后端契约。
- 可在前后截图里直接判断信息层级、列表密度和题材感是否改善。
- 风险小于工作台和 SimC, 不会误伤证据状态模型。

## 审计依据

- 真实截图: `artifacts/miniprogram-screenshots/20260630-workbench-redesign/screenshots/`
- UI 规范: `docs/ui-style-guide.md`
- 代码页面:
  - `pages/news/news.wxml`
  - `pages/news/news.wxss`
  - `pages/builds/builds.wxml`
  - `pages/builds/workbench.wxml`
  - `pages/simulator/simc.wxml`
  - `pages/simulator/chickenbro.wxml`
  - `pages/profile/profile.wxml`

## 共性问题

| 问题 | 影响 | 证据 |
| --- | --- | --- |
| imagegen 背景和局部材质被多页面重复使用, 信息层经常和材质层争抢注意力 | 页面看似更有题材感, 但扫读效率下降 | `pages/news/news.wxml:2-12`, `pages/builds/workbench.wxml:2-12`, `pages/simulator/simc.wxml:2-10`, `pages/profile/profile.wxml:2-12` |
| 多数页面首屏都在 hero、材质、卡片之间堆层级, 但关键行动没有稳定落在首屏最清晰位置 | 用户要先识别页面装饰, 再找下一步 | `pages/news/news.wxml:10-50`, `pages/builds/builds.wxml:8-31`, `pages/builds/workbench.wxml:10-79` |
| 状态色和模块强调色过多, source、warning、CTA、装饰金边混在一起 | 数据可信 UI 的语义被稀释 | `pages/news/news.wxss:224-240`, `pages/simulator/chickenbro.wxss` 中绿色同时承担 AI/上下文强调 |
| 多个列表行没有统一的标题行、meta 行、来源行结构 | 滚动列表读起来像黑卡堆叠, 不是可扫读信息流 | `pages/news/news.wxml:75-88`, `pages/profile/profile.wxml:43-64` |

## 页面级 CR

### 资讯首页

主要问题:

- `news-command`、swiper、频道、重点列表都使用强卡片, 首屏层级重, 但滚动后列表仍像普通黑卡。
- 「今日重点」卡片只有频道、日期、标题、摘要、来源, 没有列表序号、来源可信感、阅读动作或重点类型。
- 频道色固定偏红, 所有重点都像同一种告警, 不是资讯优先级。
- `highlight-summary` 没有行数封顶, 极端摘要可能拉高卡片。

证据:

- `pages/news/news.wxml:70-90`
- `pages/news/news.wxss:389-453`
- 截图: `002_news_home_scrolled.png`

建议:

- 保持现有接口字段, 只重排「今日重点」列表。
- 卡片改为左侧序号 + 中部正文 + 右侧日期/动作的扫读行。
- 保留频道、标题、摘要、来源, 增加“查看”动作但不新增数据。
- 对标题、摘要、来源做行数封顶和省略。
- 降低卡片背景黑块感, 用暗铁面板、左侧金色 rail 和来源 meta 拉开层级。

### 职业专精 tab

主要问题:

- 顶部 hero 和工作台入口都用了大材质, 两者在首屏抢主叙事。
- 工作台入口文案是对的, 但没有直接暴露当前 readiness 或 blocker, 入口像广告卡。
- 旧入口下沉后成为“构筑流程”, 信息顺序合理, 但每个 query card 的右侧 action 与标题之间没有明确优先级。

证据:

- `pages/builds/builds.wxml:8-47`
- `pages/builds/builds.wxss` 的 `.builds-hero`, `.workbench-entry`, `.query-card`
- 截图: `003_builds_tab.png`

建议:

- 后续把 hero 压缩成一行导航摘要。
- 工作台入口直接展示当前专精、状态、主 blocker。
- query card 保持紧凑列表, 不再增加视觉材质。

### 当前专精工作台

主要问题:

- 信息是完整的, 但首屏模块太多: cockpit、readiness、blocker、workflow、template、evidence 争夺垂直空间。
- `workbench-hero` 背景材质 opacity 较高,真实图标、标题、状态 badge 都压在复杂底图上。
- readiness panel 的主行动在右侧, 但 blocker slab 又重复出现下一步, 对新手来说“点哪里”有重复。

证据:

- `pages/builds/workbench.wxml:10-153`
- 截图: `004_workbench_first_screen.png`, `005_workbench_evidence_expanded.png`

建议:

- 后续第一屏只保留对象、readiness、主 blocker、主 action、四模块状态。
- evidence 和模板进入二级区或折叠区。
- 保留真实 icon, 但不要把 icon 放在强底图上。

### SimC

主要问题:

- 表单流程完整, 但首屏从职业、种族、天赋、装备、场景、战斗增益一路堆叠, 用户很晚才看到 blocked/confirm summary。
- fixed action bar 是对的, 但 blocked reason 不在首屏主路径附近。
- 场景预设卡每个都带说明, 高度偏大。

证据:

- `pages/simulator/simc.wxml:18-170`
- 截图: `010_simc.png`

建议:

- 后续把 readiness/blocked 摘要提到模板选择上方。
- 场景预设改成一行 segmented control, 说明进入 secondary text。
- 缺模板时把“去保存模板”作为明确动作。

### 炸鸡队长

主要问题:

- 聊天主体结构正确, 但 header 仍偏大, 抢走消息区高度。
- 工作台 context 和 suggested prompts 有价值, 但和 header 分成两块, 首屏稍碎。
- 绿色被用于上下文、assistant bubble、证据来源, 语义过宽。

证据:

- `pages/simulator/chickenbro.wxml:8-97`
- 截图: `012_chickenbro.png`

建议:

- 后续把 header 和 context 合并为紧凑上下文条。
- 保留左右气泡和 fixed composer。
- evidence 面板只在回答后出现, 默认不抢首屏。

### 我的页面

主要问题:

- 个人 cockpit 有题材感, 但头像、昵称、说明和指标区分割较弱。
- 模板列表结构可用, 但删除按钮视觉过弱, 容易误触或看漏。
- 设置与管理目前是占位列表, 没有状态说明, 会显得未完成。

证据:

- `pages/profile/profile.wxml:10-82`
- 截图: `013_profile_templates.png`

建议:

- 后续保留模板库, 先减少顶部材质干扰。
- 设置项增加 disabled/coming soon 语义或隐藏未实现项。
- 删除按钮改为更明确的危险操作样式, 并保持 modal 二次确认。

## 第一刀改版范围

只修改资讯首页「今日重点」列表:

- `pages/news/news.wxml`
- `pages/news/news.wxss`

不修改:

- 接口字段。
- 新闻详情路由。
- 刷新逻辑。
- 频道数据。
- 强结论或模拟相关文案。

验收:

- 资讯滚动列表不再是同质黑卡。
- 标题、摘要、来源、日期、动作各有稳定位置。
- 长标题、长摘要、长来源不撑破卡片。
- 仍通过 `tests/news-page-style.test.js` 和 `git diff --check`。

## 第一刀实施记录

已修改:

- `pages/news/news.wxml`
- `pages/news/news.wxss`
- `pages/news/news.js`
- `tests/news-page-style.test.js`

关键取舍:

- 保留真实资讯 payload, 不新增强结论。
- 移除资讯页整页 imagegen 背景和局部素材覆盖, 避免继续把概念图当 UI 壳。
- 保留暗色、金色、暗铁面板和紧凑信息条, 用真实字段组合成 `今日情报台`、频道、来源、重点数量、刷新状态。
- 「今日重点」改为左序号、中正文、右日期/动作的高密度列表, 并对标题、摘要、来源做固定行数和省略。

已验证:

- `node --test tests/news-page-style.test.js tests/frontend-api-client.test.js tests/ui-style-guide-implementation.test.js`
- `git diff --check`
- 静态搜索确认本轮资讯页不出现 `DPS`、`综合评分`、`S 级`、`A 级`、`提升优先级` 等无证据强结论。

未完成:

- 真实小程序 after 截图暂未产出。微信开发者工具当前显示 `未登录`, 模拟器显示 `模拟器启动失败 / Error: 需要重新登录`; automator 能连接, 但 `switchTab('/pages/news/news')` 超时。
- 阻塞证据记录在 `artifacts/miniprogram-screenshots/20260702-real-ui-first-pass/manifest.json` 和 `artifacts/miniprogram-screenshots/20260702-real-ui-first-pass/screenshots/devtools-login-blocker-fullscreen.png`。

登录恢复后下一步:

- 复跑 `NODE_PATH=/tmp/wow-miniprogram-automator/node_modules node artifacts/miniprogram-screenshots/20260702-real-ui-first-pass/capture-news-scrolled.js`。
- 补齐 `news-home-scrolled-after.png`。
- 和历史 `002_news_home_scrolled.png` 做前后对比, 再决定是否进入职业专精 tab。

## 下一页改版建议

建议第二刀选择 `职业专精 tab`, 而不是直接改工作台。

原因:

- 它是工作台、天赋、装备、SimC、任务列表的总入口, 对整体主路径影响更大。
- 当前截图 `artifacts/miniprogram-screenshots/20260630-workbench-redesign/screenshots/003_builds_tab.png` 已经能证明问题: 顶部 hero 和工作台入口都使用大面积素材, 首屏两块都在讲“职业专精”, 但用户真正需要的当前专精状态、是否可模拟、缺什么没有露出。
- 当前代码 `pages/builds/builds.wxml` 仍有 `builds-shell-bg`、`builds-hero-material`、`workbench-entry-material`, 和本轮资讯页刚修掉的问题同源。
- 这页改动可以继续保持低风险: 不动后端接口, 不改旧入口路由, 只重排首页入口的信息层级。

建议范围:

- 移除整页 imagegen 背景和工作台入口大材质, 保留暗色金色控制台底盘。
- 顶部 hero 压缩为一行页面摘要, 只说明对象是 `职业专精`。
- 工作台入口改成真实任务卡:
  - 左侧显示当前职业/专精/英雄天赋。
  - 中间显示 readiness 文案, 例如 `等待天赋和装备证据`、`可进入校验`。
  - 右侧只保留一个主动作 `进入`。
  - 下方用 4 个短状态格展示 `天赋`、`装备`、`SimC`、`队长`, 不再用装饰 tag。
- `构筑流程` 保留旧四入口, 但改成更像流程列表:
  - 每行固定 `阶段`、`对象`、`当前状态/用途`、`动作`。
  - 阶段标签保留 `输入`、`验证`、`追踪`, 但不作为大按钮。
  - 长说明压成 1 到 2 行, 防止卡片高度过大。

验收重点:

- 首屏同时看到当前专精工作台入口和至少 2 个旧流程入口。
- 不出现整页素材背景, 不用 imagegen 图冒充真实游戏资产。
- 工作台入口必须回答“当前要不要进工作台, 进去看什么”, 而不是只说“当前专精工作台”。
- 旧入口仍可用, 路由和埋点不变。
- 截图验证至少包含 `职业专精 tab 首屏`、`滚动后构筑流程列表`、`点击工作台入口后的页面跳转`。

## 第二刀实施记录

已修改:

- `pages/builds/builds.js`
- `pages/builds/builds.wxml`
- `pages/builds/builds.wxss`
- `tests/builds-page.test.js`
- `tests/ui-style-guide-implementation.test.js`
- `docs/design/2026-07-02-imagegen-to-miniprogram-layout-decomposition.md`
- `docs/roadmap/ideas.md`

关键取舍:

- 以 `artifacts/ui-visual-targets/20260702-pretty-direction/builds-target.png` 作为视觉目标, 但不照搬静态图。
- 移除 `builds-shell-bg`、`builds-hero-material`、`workbench-entry-material`, 不再用整页 imagegen 背景。
- 新增 `buildHomeOverview()` 和 `workbenchEntry.modules`, 把目标图拆成页面摘要、专精 socket、状态 badge、工作台主行动、四模块状态带、流程列表。
- builds tab 不直接计算 readiness, 只显示 `等待证据`; 真实天赋/装备/SimC 判断仍进入工作台后读取接口。
- 四个旧入口仍保留, 路由和埋点不变。

已验证:

- `node --test tests/builds-page.test.js tests/news-page-style.test.js tests/frontend-api-client.test.js tests/ui-style-guide-implementation.test.js tests/simulator-page.test.js`
- `git diff --check`

未完成:

- 官方小程序 after 截图仍受微信开发者工具登录/runtime 阻塞影响, 需要登录恢复后补拍。
