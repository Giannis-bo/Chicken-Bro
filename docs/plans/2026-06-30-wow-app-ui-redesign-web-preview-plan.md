# WoW App UI Redesign Web Preview Plan

## 目标

在不获得正式小程序 AppID 开发者授权的前提下，建立一条 Web Preview 验证路径，用于继续推进 `2026-06-30-wow-app-ui-redesign-plan.md` 的 UI 设计评审、场景截图和交互检查。

这份计划不替代正式小程序验收。它的目标是避免今天的 UI 评审被 AppID 权限卡住，同时保留正式 AppID 截图作为后续发布前验收项。

## 适用范围

Web Preview 用于验证：

- 资讯首页信息层级
- 职业专精 tab 信息架构
- 当前专精工作台首屏结构
- 工作台证据展开
- `blocked` 装备态
- `partial` 天赋态
- 天赋模拟器承接
- 装备模拟承接
- SimC 承接
- 任务列表承接
- 炸鸡队长承接
- 我的模板 / 已保存模板承接
- 视觉语言、密度、状态色、文案边界和素材使用规则

Web Preview 不用于验证：

- 正式 AppID 权限
- 微信登录 / openid
- 合法域名 request 校验
- Skyline / 微信原生组件真实渲染差异
- 真机调试
- 上传 / 发布 / 体验版能力
- 正式小程序截图验收

## 产物位置

新增独立 Web Preview 目录：

```text
artifacts/web-preview/20260630-workbench-redesign/
  README.md
  index.html
  preview.css
  preview.js
  serve-preview.js
  capture-preview.js
  manifest.json
  screenshots/
```

正式小程序截图目录继续保留：

```text
artifacts/miniprogram-screenshots/20260630-workbench-redesign/
```

两个目录语义必须分开。Web Preview 产物不能写入正式小程序截图 manifest。

## 验证场景

Web Preview 必须覆盖当前 UI 目标中的 13 个场景。

| ID | Scene | Preview Route | 验证重点 |
| --- | --- | --- | --- |
| 001 | 资讯首页顶部 | `/#news-top` | 情报摘要、今日重点、真实来源信息 |
| 002 | 资讯首页滚动后 | `/#news-scrolled` | 滚动后重点列表不再纯黑、信息可扫读 |
| 003 | 职业专精 tab | `/#builds-tab` | 工作台最高优先级入口、旧四入口保留 |
| 004 | 当前专精工作台首屏 | `/#workbench` | 当前专精、场景、readiness、主行动、四模块状态 |
| 005 | 工作台证据展开 | `/#workbench-evidence` | coverage、checkedAt、catalogStatus、statSnapshot、template count、blockers |
| 006 | 工作台 blocked 装备态 | `/#workbench-blocked-gear` | 缺什么、影响什么、下一步去哪 |
| 007 | 工作台 partial 天赋态 | `/#workbench-partial-talent` | 只展示部分可用和证据，不输出强结论 |
| 008 | 天赋模拟器 | `/#talent-simulator` | 真实天赋图标 / 节点语义 / 导入保存承接 |
| 009 | 装备模拟 | `/#gear-simulator` | 真实装备图标 / 槽位 / 候选状态 |
| 010 | SimC | `/#simc` | 保存模板组合流程、缺模板阻断 |
| 011 | 任务列表 | `/#tasks` | SimC 任务承接 |
| 012 | 炸鸡队长 | `/#chickenbro` | 证据解释入口，不替代评分 |
| 013 | 我的模板 / 已保存模板 | `/#profile-templates` | 天赋 / 装备模板承接 |

## 数据规则

Web Preview 数据必须尽量贴近真实读模型。

允许使用：

- 现有 fallback payload
- 当前仓库里的纯函数状态聚合
- `pages/builds/workbench-state.js`
- 真实 WoW render icon URL
- 项目已有 `gameAsset.iconUrl` 结构
- 明确标注的 preview fixture

禁止使用：

- imagegen 生成的职业 / 专精 / 天赋 / 装备图标
- imagegen 生成的业务状态
- 未标注来源的 DPS、排名、S/A 级、综合评分、提升优先级
- 临时 AppID 截图作为正式验收
- 小程序 DevTools 截图失败时生成的黑图

`blocked` 和 `partial` 场景可使用 fixture，但 manifest 必须标注：

```json
{
  "dataStatus": "web_preview_controlled_fixture"
}
```

## 真实素材规则

Web Preview 必须沿用主计划的真实素材边界：

- 职业、专精、天赋、装备图标来自真实 URL 或文字 fallback。
- imagegen 只可用于抽象材质和背景。
- 缺真实图标时用文字 fallback，不伪装真实资产。
- 不从 imagegen 图里提取数字、状态、评分或业务结论。

## 文案边界

Web Preview 页面中禁止出现无证据强结论：

- `DPS`
- `综合评分`
- `S 级`
- `A级`
- `提升优先级`
- `最强`
- `毕业`
- `必选`

允许出现：

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

### Step 1：建立 Web Preview 骨架

- 新增 `artifacts/web-preview/20260630-workbench-redesign/`。
- 建立 HTML / CSS / JS / README / manifest。
- 页面尺寸按移动端预览，优先模拟小程序 iPhone 宽度。

### Step 2：复刻 13 个场景

- 用 Web 结构复刻当前小程序关键页面。
- 每个场景有独立 hash route。
- 每个场景可以被 Playwright 直接打开和截图。

### Step 3：接入真实状态聚合

- 在 Web Preview 中复用或镜像 `pages/builds/workbench-state.js` 的输出。
- `ready_to_simulate`、`blocked`、`partial`、`stale`、`source_reference` 状态表现必须和小程序一致。

### Step 4：截图生成

- 启动本地 Web server。
- 使用 Playwright 截取 13 个场景。
- 输出到：

```text
artifacts/web-preview/20260630-workbench-redesign/screenshots/
```

### Step 5：生成 manifest

`manifest.json` 必须包含：

- `acceptanceType: "web_preview_only"`
- `officialMiniProgramAcceptance: false`
- 每个场景的 route、scene、dataStatus、reachable、screenshot path
- 使用的 fixture 说明
- 不替代正式 AppID 验收的声明

### Step 6：验证

运行：

```bash
node artifacts/web-preview/20260630-workbench-redesign/capture-preview.js
node --test tests/builds-workbench-state.test.js tests/builds-page.test.js tests/news-page-style.test.js
git diff --check
```

可选检查：

```bash
rg -n "DPS|综合评分|S 级|A级|提升优先级|最强|毕业|必选" artifacts/web-preview/20260630-workbench-redesign pages/builds/workbench.* pages/news/news.*
```

## 完成标准

今天的 Web Preview 目标完成，需要满足：

- 13 个 Web Preview 场景全部可打开。
- 13 张 Web Preview 截图全部存在且非黑屏。
- `manifest.json` 标注 `web_preview_only`。
- 正式小程序截图 manifest 不被覆盖。
- Web Preview 不使用临时 AppID 或 DevTools 截图冒充正式验收。
- 禁用强结论文案不出现。
- 关键 Node 测试通过。

## 与正式小程序验收的关系

Web Preview 完成后，可以推进 UI 设计评审和下一轮视觉 / 交互优化。

正式小程序验收仍需后续补齐：

- 使用正式 AppID。
- 使用有开发者权限的微信账号。
- 跑真实小程序截图。
- 覆盖同样 13 个场景。
- 更新 `artifacts/miniprogram-screenshots/20260630-workbench-redesign/manifest.json`。

Web Preview 不能把正式验收状态从 `blocked_by_appid_permission` 改成 `complete`。
