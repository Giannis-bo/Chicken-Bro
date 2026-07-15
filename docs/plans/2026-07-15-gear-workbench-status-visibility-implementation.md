# 装备模拟校验状态卡移除 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 移除装备模拟页的全局校验状态卡，不改变内部 Resolve 校验或用户操作保护。

**Architecture:** 只收敛 `pages/builds/detail.wxml` 的展示层，删除整个 `gear-workbench-status` 节点。JavaScript 继续持有 workbench 状态并驱动保存、强化编辑和 SimC 入口的现有禁用条件；测试把该展示契约改为“状态卡不存在”，同时继续验证这些操作保护的 WXML 绑定仍在。

**Tech Stack:** 微信小程序 WXML、Node.js 内置 `node:test`、`assert`。

## Global Constraints

- 不修改 API、服务端 Resolve、workbench 状态机、数据库、health/admin、定时任务或部署脚本。
- `gearDataWarningText` 的装备数据接口可用性提示不属于本次被移除的状态卡，必须保留。
- 必须保留保存模板与进入 SimC 的现有禁用绑定，校验失败仍 fail-closed。
- 本次仅做本地实现和验证；不推送、不开 PR、不部署。

---

### Task 1: 隐藏全局状态卡并锁定页面展示契约

**Files:**
- Modify: `tests/builds-page.test.js:1511-1670`
- Modify: `pages/builds/detail.wxml:60-71`

**Interfaces:**
- Consumes: `gearWorkbenchView` 继续为保存和 SimC 按钮提供 `canUseVerifiedSnapshot` 与 `canRunProfile`。
- Produces: 装备页 WXML 不再绑定 `gearWorkbenchStatusText`、`gearWorkbenchSignatureLabel` 或 `gearWorkbenchProblemRows`，但仍绑定 `gearDataWarningText` 和现有操作禁用条件。

- [ ] **Step 1: 先将页面结构测试改为“状态卡不可见”**

  在 `gear detail page exposes inline equipment simulator state and replacement sheet` 测试中，用以下断言替换当前对 `gearWorkbenchStatusText` 和 `gearWorkbenchProblemRows` 的 `assert.match` 断言：

  ```js
  assert.doesNotMatch(wxml, /class="gear-workbench-status/)
  assert.doesNotMatch(wxml, /gearWorkbenchStatusText/)
  assert.doesNotMatch(wxml, /gearWorkbenchSignatureLabel/)
  assert.doesNotMatch(wxml, /gearWorkbenchProblemRows/)
  ```

  保留紧邻的断言：

  ```js
  assert.match(wxml, /gearDataWarningText/)
  assert.match(wxml, /disabled="\{\{gearDataFallback \|\| gearTemplateSaving \|\| !gearWorkbenchView\.canUseVerifiedSnapshot\}\}"/)
  assert.match(wxml, /disabled="\{\{!gearWorkbenchView\.canRunProfile\}\}"/)
  ```

- [ ] **Step 2: 运行该测试并确认其因旧状态卡而失败**

  Run:

  ```bash
  node --test --test-name-pattern='gear detail page exposes inline equipment simulator state and replacement sheet' tests/builds-page.test.js
  ```

  Expected: FAIL，错误来自 `assert.doesNotMatch` 仍在 WXML 中找到 `gear-workbench-status` 或其展示字段，而不是测试加载或语法错误。

- [ ] **Step 3: 最小化删除状态卡 WXML 节点**

  从 `pages/builds/detail.wxml` 的 `<view class="module-panel gear-panel" ...>` 内删除以下完整节点，不添加替代占位元素：

  ```xml
  <view class="gear-workbench-status {{gearWorkbenchView.resolveStatus}}">
    <text class="gear-workbench-status-title">{{gearWorkbenchStatusText}}</text>
    <text class="gear-workbench-status-meta" wx:if="{{gearWorkbenchSignatureLabel}}">配置签名 {{gearWorkbenchSignatureLabel}}</text>
    <text class="gear-workbench-problem" wx:for="{{gearWorkbenchProblemRows}}" wx:key="key">{{item.text}}</text>
  </view>
  ```

  保留 `gear-request-alert` 和紧随其后的 `gear-attribute-panel`。

- [ ] **Step 4: 重新运行聚焦测试并确认通过**

  Run:

  ```bash
  node --test --test-name-pattern='gear detail page exposes inline equipment simulator state and replacement sheet' tests/builds-page.test.js
  ```

  Expected: PASS，且该测试仍确认装备数据告警和保存/SimC 禁用条件存在。

- [ ] **Step 5: 运行页面回归与静态检查**

  Run:

  ```bash
  node --test tests/builds-page.test.js
  node --check pages/builds/detail.js
  git diff --check
  ```

  Expected: 三条命令均以退出码 0 完成；不出现 WXML 断言失败、JavaScript 语法错误或空白错误。

- [ ] **Step 6: 审查并提交实现**

  检查仅修改 `tests/builds-page.test.js`、`pages/builds/detail.wxml` 和本计划文件；确认没有改动 `pages/builds/detail.js` 的内部状态或任何后端文件。随后执行：

  ```bash
  git add pages/builds/detail.wxml tests/builds-page.test.js docs/plans/2026-07-15-gear-workbench-status-visibility-implementation.md
  git commit -m "fix: hide gear workbench status card"
  ```

  Expected: 单个实现提交只包含展示层收敛、对应回归测试和实施计划。
