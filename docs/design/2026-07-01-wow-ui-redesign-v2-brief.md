# WoW 小程序真实 UI 二轮设计 Brief

## 目标

基于官方小程序截图和 UI CR，把当前小程序继续推进为“移动端艾泽拉斯分析控制台”。本轮只改真实小程序页面与真实截图流程，不再新增 HTML demo，不继续横评 skill，不把 imagegen 输出当作事实 UI。

输入证据：

- 官方截图：`artifacts/miniprogram-screenshots/20260630-workbench-redesign/`
- 设计评审规则：`docs/design/wow-mini-program-design-review-adapter.md`
- UI CR：`docs/reviews/2026-07-01-official-screenshot-ui-cr.md`
- 风格规范：`docs/ui-style-guide.md`
- 产品简报：`docs/plans/2026-06-29-current-spec-workbench-product-brief.md`

## P0 产品链路

必须先修产品链路，再做视觉强化。

- SimC 从工作台进入时必须继承职业、专精和场景上下文。
- SimC 缺模板时必须在当前专精上下文内解释缺什么，不回到“请选择职业”。
- 工作台装备 readiness 的槽位计数、缺口和 blocker 必须来自同一套模型。
- 官方 `news scrolled` 截图必须真实滚动到资讯列表中段。
- 官方 `workbench evidence expanded` 截图必须肉眼可见证据明细。

## 页面方向

### 资讯首页

- 顶部是情报摘要，不重复当作第一篇文章。
- 轮播只承担精选故事，不承担状态说明。
- 滚动后列表要保留清晰来源、频道、短时间和标题层级。
- 不露出 `scheduled`、原始 timezone 时间戳或内部刷新模式。

### 职业专精 Tab

- 工作台入口保持最高优先级。
- 旧入口下沉为工作流能力：构筑输入、模拟验证、任务追踪、队长解释。
- 移除“能力 02”“深入模块”“旧入口保留”“进入查询”等脚手架文案。

### 当前专精工作台

- 首屏只保留一个主 verdict。
- 一个主 blocker 对应一个主 action。
- 四模块从等权卡片改成工作流状态带：天赋输入、装备输入、SimC 校验、队长解释。
- 证据区服务资深玩家，默认不抢首屏，但官方 evidence 截图必须滚动到该区。
- 不显示 DPS、综合评分、S/A 级、提升优先级或无来源强结论。

### SimC

- 从工作台进入后，页面标题和选择器显示当前职业/专精。
- 空模板态解释“当前专精缺少天赋模板 / 装备模板”。
- 保留既有保存模板、校验组合和提交任务流程。

### 炸鸡队长

- 从工作台进入时带 bounded context：职业、专精、场景、来源。
- 首屏展示当前解释对象和建议问题。
- 队长只解释证据和阻断，不替代 SimC 评分，不编 DPS、排名或日志结论。

## Imagegen 素材工作流

imagegen 只提供抽象视觉素材，不提供事实内容。

允许：

- 暗铁 / 奥术 / 档案面板材质。
- blocked / partial / ready / source_reference 的状态氛围背景。
- 空态氛围素材。
- 小程序局部视觉参考。

禁止：

- 职业、专精、天赋、装备、来源 logo 等真实对象图标。
- DPS、评分、排名、提升优先级、blocker 或 readiness 结论。
- 带文字的假 UI 截图。
- 会被当作接口数据或游戏事实的内容。

当前可用素材登记在 `assets/generated/ui-redesign/20260630/manifest.json`。生产 UI 只能使用其中标记 `productionUse: true` 且 `sourceType: imagegen` 的抽象材质；真实 WoW 图标必须来自 API/read model 的 `gameAsset.iconUrl` 或受控真实资产索引。

## 实施范围

重点文件：

- `pages/news/news.*`
- `pages/builds/builds.*`
- `pages/builds/workbench*`
- `pages/simulator/simc.*`
- `pages/simulator/chickenbro*`
- `artifacts/miniprogram-screenshots/20260630-workbench-redesign/capture-official.js`
- 对应测试文件

## 验收

截图必须来自官方微信开发者工具项目，不接受 Web Preview 替代。

必须覆盖：

- 资讯首页首屏
- 资讯滚动后列表
- 职业专精 tab
- 工作台首屏 blocked
- 工作台 evidence 展开
- 工作台 blocked 装备态
- 工作台 partial 天赋态
- 工作台 ready 态
- 天赋模拟器
- 装备模拟
- SimC 从工作台承接态
- 任务列表
- Chickenbro 从工作台承接态
- 我的模板

通过条件：

- `manifest.json` 为 `complete`。
- 所有截图非黑屏。
- `news scrolled` 和 `workbench evidence expanded` 肉眼证明场景成立。
- SimC 截图显示已继承工作台专精上下文。
- 工作台装备计数和 blocker 不矛盾。
- 无 `scheduled`、裸 `checkedAt`、长 timezone 时间戳等内部文案泄漏。
- 无无证据 DPS、综合评分、S/A 级、提升优先级。

## 回归命令

```bash
node --test tests/builds-workbench-state.test.js tests/builds-page.test.js tests/frontend-api-client.test.js
node --test tests/simulator-page.test.js tests/news-page-style.test.js tests/ui-style-guide-implementation.test.js
git diff --check
```
