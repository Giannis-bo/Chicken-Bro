# WoW 小程序 App 级 UI / 交互重设计计划

## 目标

完成一轮真实可用的小程序 UI / 交互重设计，把当前项目从“功能集合”升级为有 C 端 app 感的 WoW 玩家情报与构筑分析工具。

本轮不再继续做横向 skill 比稿，也不把 imagegen 生成图当最终界面。新的设计必须基于真实产品能力、真实魔兽素材、真实接口状态和可验证数据边界落地。

核心覆盖范围：

- 资讯首页
- 职业专精 tab
- 当前专精工作台
- 天赋模拟器承接
- 装备模拟承接
- SimC 承接
- 任务列表承接
- 炸鸡队长承接
- 我的模板 / 已保存模板承接

## 产品方向

产品应被重新组织为“WoW 玩家情报与构筑工作台”。

首页负责让玩家快速感知版本与资讯重点；职业专精 tab 负责让玩家进入当前角色 / 当前专精的构筑判断；当前专精工作台负责把天赋、装备、SimC、队长解释和模板状态收束到一个明确问题：

> 当前是否具备模拟 / 评分条件？如果不能，缺什么？如果可以，下一步去哪？

## 设计语言

整体视觉方向：

- 移动端 WoW 情报 app
- 暗色基底 + 金色重点
- 高密度但可扫读
- 强证据感
- 有真实游戏质感
- 不做普通黑卡片堆叠
- 不做页游皮肤
- 不用大面积无意义装饰图

页面气质：

- 资讯首页：像版本情报控制台，首屏聚焦今日重点和更新节奏。
- 职业专精 tab：像当前角色 / 专精控制中心，不只是入口列表。
- 当前专精工作台：像证据驾驶舱，优先展示 readiness、blocker、下一步行动和四模块状态。
- 承接页面：保持现有功能完整，但视觉入口和状态表达要和新设计一致。

## 用户分层

默认面向新手玩家：

- 首屏给明确结论。
- 明确下一步行动。
- 不要求用户理解数据来源细节才能继续。

同时兼顾资深玩家：

- 展开区提供来源、覆盖率、blocker、checkedAt、catalogStatus、statSnapshot、模板数量等证据。
- 不用综合分掩盖来源差异。
- 允许资深用户判断数据是否可信。

## 真实素材规则

魔兽相关元素不能凭空生成。

真实职业、专精、天赋、装备、来源对象必须优先来自：

- 接口中的 `gameAsset.iconUrl`
- 真实 WoW render icon URL
- 项目已有 WebSim / Gear / Talent 读模型
- 真实装备、天赋、职业、专精数据
- 已确认来源状态和本地模板数据

禁止用 imagegen 生成或替代：

- 职业图标
- 专精图标
- 天赋图标
- 装备图标
- 来源 logo
- 真实物品图
- 真实技能图
- DPS
- S / A 级
- 综合评分
- 提升优先级
- blocker
- readiness 状态
- 业务结论

缺真实图标时使用文字 fallback，不伪装成真实资产。

## Imagegen 工作流

imagegen 继续使用，但必须作为真实 app 设计素材工作流的一部分，而不是直接生成最终 UI。

imagegen 可用于：

- 视觉方向板
- 背景材质
- 面板纹理
- 状态氛围素材
- 空态 / 阻断态背景素材
- 工作台驾驶舱抽象材质
- 资讯首页抽象氛围图

imagegen 产物必须满足：

- 不承载真实业务结论。
- 不承载真实状态。
- 不承载真实魔兽对象。
- 不覆盖接口中的真实图标。
- 不把生成图里的数字、文案、评分带入产品。
- 所有生产使用资产都要登记 manifest。

新增素材 manifest 至少包含：

- 文件路径
- 来源类型：`imagegen` / `api_asset` / `real_wow_asset`
- 用途
- 是否生产使用
- 是否包含真实魔兽对象
- 禁止用途
- 生成时间或来源说明

## 证据边界

必须遵守：

- 没有完整 SimC-ready talents + gear 前，不显示 DPS。
- 不显示 S / A 级。
- 不显示综合评分。
- 不显示提升优先级。
- 不把 imagegen 内容当事实。
- 不把 LLM / 炸鸡队长解释当事实来源。
- 不把临时 demo 数据写成永久产品规则。
- 不把无来源判断包装成强结论。

状态表达统一使用：

- `ready_to_simulate`
- `blocked`
- `partial`
- `stale`
- `source_reference`
- `verified`

评分来源只能来自明确基准：

- 同 profile SimC delta
- 同来源百分位
- 证据完整度

第一版不混合成综合分。

## 资讯首页改造

目标：

- 从普通资讯流升级为 WoW 情报 app 首页。
- 压缩过大的顶部 banner。
- 强化“今日重点”的信息层级。
- 修复滚动后重点列表黑、空、弱的问题。
- 保留真实来源、频道、发布时间和详情入口。
- 不新增假资讯、不新增假来源。

首屏结构：

- 顶部情报摘要：更新状态、重点数量、来源覆盖、最近刷新。
- 今日重点：展示真实 highlight，不做假推荐。
- 频道 / 来源提示：帮助用户理解内容可信度。
- 列表入口：滚动后仍保持信息密度和可读性。

涉及文件：

- `pages/news/news.js`
- `pages/news/news.wxml`
- `pages/news/news.wxss`

## 职业专精 Tab 改造

目标：

- 从“功能查询入口”升级为职业专精控制台。
- 当前专精工作台成为最高优先级入口。
- 旧四入口保留，但下沉为能力矩阵。
- 职业 / 专精选择要更像 app 内工作流，不像临时 demo 面板。

首屏结构：

- 当前专精入口：职业、专精、英雄天赋、状态摘要、主行动。
- 能力矩阵：
  - 天赋构筑
  - 装备模拟
  - 模拟 SimC
  - 任务列表
- 说明和状态要来自真实接口或本地模板状态，不造假。

涉及文件：

- `pages/builds/builds.js`
- `pages/builds/builds.wxml`
- `pages/builds/builds.wxss`

## 当前专精工作台

新增页面：

- `pages/builds/workbench.js`
- `pages/builds/workbench.wxml`
- `pages/builds/workbench.wxss`
- `pages/builds/workbench.json`
- `pages/builds/workbench-state.js`

注册：

- 在 `app.json` 注册 `pages/builds/workbench`。

入口：

- 职业专精 tab 首屏顶部新增“当前专精工作台”主入口。
- 点击进入 `/pages/builds/workbench?spec=<当前默认或已选专精>`。

数据来源：

- `fallbackBuildsHome()`
- `requestBuildsHome()`
- `/api/websim/talents`
- `/api/websim/gear`
- `listBuildTemplates('talent')`
- `listBuildTemplates('gear')`
- 远端模板接口
- 现有 SimC 页面
- 现有炸鸡队长页面

工作台状态聚合：

- 新增 `pages/builds/workbench-state.js`。
- 只做纯函数，不发请求。
- 输入：
  - `selectedSpec`
  - `talentsPayload`
  - `gearPayload`
  - `talentTemplates`
  - `gearTemplates`
  - 当前场景
- 输出：
  - 聚合状态
  - 首屏结论
  - 主 blocker
  - 下一步 action
  - 四模块状态
  - 证据展开行

工作台首屏回答：

- 当前职业 / 专精 / 英雄天赋是什么。
- 当前是否 ready to simulate。
- 如果不能，主要缺什么。
- 下一步应该去哪。
- 天赋、装备、SimC、炸鸡队长四个模块分别是什么状态。

工作台 UI 结构：

- 顶部紧凑驾驶舱 hero：
  - 当前职业
  - 当前专精
  - 英雄天赋
  - 场景
  - readiness
  - 主行动
- 阻断 / 下一步 slab：
  - 最多 2 个主 blocker
  - 明确 action
- 四模块状态带：
  - 天赋
  - 装备
  - SimC
  - 炸鸡队长
- 证据展开区：
  - coverage
  - checkedAt
  - catalogStatus
  - statSnapshot
  - template count
  - blockers

场景切换：

- `single`
- `aoe_5`
- `mythic_plus`

主行动规则：

- `ready_to_simulate`：进入 `/pages/simulator/simc?from=workbench&spec=...`
- `blocked` 且装备缺口：进入装备模拟 / 装备详情承接页
- `blocked` 且天赋缺口：进入天赋模拟器
- `partial`：优先展开证据，并提供继续补齐入口
- `stale`：优先刷新 / 查看来源
- `source_reference`：显示来源参考状态，不输出强结论

炸鸡队长规则：

- 可从工作台进入 `/pages/simulator/chickenbro?from=workbench&spec=...`
- 只传 bounded context。
- 不传 raw profile。
- 只解释证据、blocker 和下一步。
- 不替代 SimC、评分或真实来源判断。

## 关键承接链路

新 UI 必须能进入并保持可用：

- 天赋模拟器
- 装备模拟
- SimC
- 任务列表
- 炸鸡队长
- 我的模板 / 已保存模板

原有页面不能被删除或破坏。新工作台是主体验，旧入口作为下沉能力继续存在。

## 文案规则

禁止使用无证据强结论：

- `DPS`
- `综合评分`
- `S 级`
- `A级`
- `提升优先级`
- `最强`
- `毕业`
- `必选`

允许使用：

- `可模拟`
- `暂不可模拟`
- `缺少核心装备`
- `天赋来源不完整`
- `装备模板未保存`
- `来源参考`
- `数据过期`
- `查看证据`
- `继续补齐`

## 实施步骤

### Step 1：设计资产与素材治理

- 生成或整理 imagegen 背景 / 材质 / 状态氛围素材。
- 建立 `assets/generated/.../manifest.json`。
- 确认真实 WoW 图标只来自接口或真实 render URL。
- 不把生成图中的假数字、假图标、假评分带入代码。

### Step 2：资讯首页 UI 改造

- 重做资讯首页首屏层级。
- 压缩 banner。
- 强化今日重点。
- 优化滚动后重点列表。
- 保留真实来源、频道、日期和详情入口。

### Step 3：职业专精 Tab UI 改造

- 新增当前专精工作台主入口。
- 下沉旧四入口为能力矩阵。
- 保持职业 / 专精选择可用。
- 保持天赋、装备、SimC、任务入口可达。

### Step 4：当前专精工作台实现

- 新增页面和路由。
- 新增纯前端状态聚合函数。
- 接入 talents、gear、本地模板、远端模板。
- 实现 readiness、blocker、下一步 action、四模块状态、证据展开区。
- 接入 SimC、天赋、装备、炸鸡队长、我的模板导航。

### Step 5：证据与文案静态检查

- 检查 WXML 中不出现禁用强结论文案。
- 检查 imagegen 产物没有被当作真实图标或状态。
- 检查状态色和状态文案统一。

### Step 6：测试与截图验收

- 跑 Node 单测。
- 跑静态 diff 检查。
- 用 WeChat DevTools / miniprogram automation 跑真实小程序截图。
- 产出截图 manifest。

## 测试计划

Node 测试：

```bash
node --test tests/builds-page.test.js tests/frontend-api-client.test.js tests/builds-workbench-state.test.js
node --test tests/news-page-style.test.js tests/news-home-payload.test.js
node --test tests/simulator-page.test.js
git diff --check
```

静态检查：

- `app.json` 注册 workbench 页面。
- 职业专精 tab 有工作台入口。
- 旧四入口仍存在。
- 工作台状态聚合覆盖 `ready_to_simulate`、`blocked`、`partial`、`stale`、`source_reference`。
- WXML 不出现无证据强结论文案。
- WXSS 符合 `docs/ui-style-guide.md` 的暗色、金色、状态色、高密度和移动端可读性要求。

## 截图验收

必须重新跑真实小程序并截图。

至少覆盖：

- 资讯首页顶部
- 资讯首页滚动后
- 职业专精 tab
- 当前专精工作台首屏
- 工作台证据展开
- 工作台 `blocked` 装备态
- 工作台 `partial` 天赋态
- 天赋模拟器
- 装备模拟
- SimC
- 任务列表
- 炸鸡队长
- 我的模板 / 已保存模板

截图产物放入：

```text
artifacts/miniprogram-screenshots/<timestamp>/workbench-redesign/
```

截图 manifest 至少包含：

- 路由
- 场景
- 是否真实可达
- 数据状态
- 截图文件路径
- 失败原因

如果 WeChat DevTools 未登录或 automation 不可用，必须记录 blocker，不能把未截图状态说成验收完成。

## 完成标准

- 资讯首页信息层级明显提升。
- 职业专精 tab 不再只是功能入口集合。
- 当前专精工作台能真实回答“能否模拟 / 评分，为什么，下一步去哪”。
- 天赋、装备、SimC、任务、炸鸡队长、我的模板链路不断。
- imagegen 资产进入真实素材工作流。
- 魔兽相关元素没有被臆造。
- 证据边界没有被破坏。
- 测试通过。
- 小程序截图完成并有 manifest。

## 非目标

本轮不做：

- 继续横向比较 UI skill。
- 用 imagegen 直接生成最终可上线界面。
- 新增后端接口。
- 改 SimC 提交流程。
- 用假数据补齐 readiness。
- 制造 DPS、排名、S/A 级、综合评分或提升优先级。
- 删除旧功能入口。
