# 职业专精 Tab Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将原 BD tab 重构为“职业专精”，主页面聚焦四个查询入口；每个入口点击后进入独立详情页，并在详情页中通过下拉框选择职业和专精后展示真实数据详情。

**Architecture:** 小程序 `pages/builds` 继续承载第二个 tab，但页面语义改为职业专精。后端新增 `server/builds/home-payload.js` 作为职业专精数据契约层，先用可信来源种子数据表达 API payload，后续可替换为定时采集和分析任务。前端主页面只展示 banner、四个查询入口和热门专精资讯；详情在 `pages/builds/detail` 页面中展示，职业和专精通过 picker 下拉选择。

**Tech Stack:** 微信小程序 WXML/WXSS/JS，Node.js `node:test`，现有轻量 server 目录。

### Task 1: 数据契约测试

**Files:**
- Create: `tests/builds-home-payload.test.js`

**Steps:**
1. 写 failing test，约束 `navTitle` 为“职业专精”、不再返回 `metrics`、四个入口为 `talents/gear/statWeights/rotation`。
2. 约束热门专精和详情每条信息都包含 `sourceName/sourceUrl/publishedAt/sourceNote/analysisWindow`。
3. 约束可信来源包含 Raider.IO、Warcraft Logs、Archon、Subcreation。
4. 约束 `classOptions` 覆盖 13 个职业和 39 个专精，用于子窗口下拉选择。
5. 运行 `node --test tests/builds-home-payload.test.js`，预期因模块不存在失败。

### Task 2: 数据模块实现

**Files:**
- Create: `server/builds/home-payload.js`

**Steps:**
1. 实现 `queryTypes`、`trustedBuildSources`、`classOptions`、`buildSpecializationHomePayload()`、`getSpecializationDetail(id)`。
2. 用覆盖坦克、治疗、近战、远程的种子专精表达页面展示。
3. 每个专精详情必须覆盖天赋构筑、装备获取、属性权重、输出循环。
4. 运行 `node --test tests/builds-home-payload.test.js`，预期通过。

### Task 3: 小程序页面重构

**Files:**
- Modify: `app.json`
- Modify: `pages/builds/builds.js`
- Modify: `pages/builds/builds.wxml`
- Modify: `pages/builds/builds.wxss`

**Steps:**
1. 将 tabBar 文案从 `BD` 改为 `职业专精`。
2. 保留顶部 banner，删除第二行 metrics。
3. 查询入口改为天赋构筑、装备获取、属性权重、输出循环，点击后 `wx.navigateTo` 到详情页。
4. 详情页中用职业 picker 和专精 picker 做选择，再展示该入口对应的详情。
5. 天赋、装备、属性、循环分别使用导入代码卡、装备来源列表、属性权重条、循环时间线。
6. 热门专精作为资讯模块，展示来源、时间、分析窗口和摘要。
7. 视觉风格改为联盟蓝、金、白银体系。

### Task 4: 文档同步

**Files:**
- Modify: `README.md`
- Create: `docs/builds-architecture.md`

**Steps:**
1. README 将 `BD` 改为 `职业专精`。
2. 新增职业专精前后端方案，说明数据源、定时分析、API payload、来源校验和覆盖所有职业专精的扩展方式。

### Task 5: 验证

**Commands:**
- `node --test tests/builds-home-payload.test.js tests/navigation-bar.test.js tests/news-home-payload.test.js tests/news-api-client.test.js tests/news-detail-view.test.js`
- `python3 -m unittest tests.news_backend_test tests.news_collector_test`

**Expected:** 所有测试通过。若本机缺少网络或依赖，不触发下载，记录阻塞原因。
