# WOW 小程序 UI 重建

> Active frontend ownership: `apps/mini-taro` owns the active 14-route mini-program runtime, and `packages/api-client/src` owns the active typed frontend transport contract. Root `app.json` and matching `pages/` clients are compatibility consumers only. Delete an individual legacy item only after `docs/compatibility-retirement.json` proves that it has no active callers.

状态：`正在推进`

## 用户目标

用户在微信中通过资讯、专精、队长和个人四个入口完成信息阅读、构筑准备、确定性模拟和记录复盘。页面必须可编译、可交互、安全区稳定，并且只展示 canonical API 和证据合同允许的事实。

## 当前真值

| 领域 | 当前状态 | 权威入口 |
| --- | --- | --- |
| 活动实现 | Taro 拥有 14 路由；typed API 拥有传输合同；根 `pages/` 不接收新一级职责 | `docs/project-owner-map.json` |
| 设计目标 | 14 个 canonical target、route geometry、truth adaptation、component/asset contract 已登记 | `docs/design/current-ui/target-registry.json` |
| 自动架构 | 14 路由共享 owner、窄屏几何、素材槽、选中态和 route contract 由架构审计阻断回归 | `scripts/audit-ui-architecture.js` |
| 生产包 | API 和素材使用已批准 HTTPS 命名域；release package、domain audit 和包体机械门禁已有可重复入口 | `docs/project-state.json` |
| 人工验收 | 当前真实汇总为 6 路由 accepted、8 路由 `not_run_user_waived`，不得表述为 14/14 | `docs/project-state.json` |
| 当前运行证据 | 当前合同仍为 `active_unverified`；旧 commit 的截图、几何和交互 artifact 已从工作树删除，只保留在 Git 历史 | `docs/design/current-ui/runtime-review-status.json` |
| 产品命名 | 活动 Taro 导航使用“资讯 / 专精 / 队长 / 我的”；对外产品定位和首页权重仍待 roadmap 决策 | `docs/roadmap/ideas.md` |

当前 `gear_detail` 的候选装备与强化编辑恢复遵循 [Taro 装备编辑器恢复设计](2026-07-24-taro-gear-editor-recovery-design.md)：候选选择、合法等级/变体配置和显式应用分离；宝石、附魔、美化使用可取消的本地草稿，只有确认后才提交 canonical Resolve。

## 权威输入

1. `docs/design/current-ui/target-registry.json` 和对应 route contract。
2. `DESIGN.md` 与 `docs/design/current-ui/README.md`。
3. 当前 Taro、typed API/domain 和后端 canonical owner。
4. `docs/project-state.json` 的当前证据与人工验收边界。

历史计划、过程截图、旧 commit 证据和未进入 `docs/plans/README.md` 白名单的文档没有执行权。

## 固定顺序和批次

`目标合同 -> 共享 owner -> 微信三基线 -> news -> builds -> simulation/profile -> 最终验收`

1. 三基线：`news_home`、`simulator_home`、`news_detail`。
2. news：`news_home`、`news_list`、`news_detail`。
3. builds：`builds_home`、`current_spec_workbench`、`build_intel`、`talent_simulator`、`gear_detail`。
4. simulation/profile：`simulator_home`、`simc_submit`、`chickenbro_chat`、`tasks_list`、`task_detail`、`profile_templates`。

## builds_home 已确认方向

`builds_home` 收敛为“职业命令卡组”：首页只选择职业，首屏平级展示天赋、装备、SimC 和任务四个紧凑入口；下方展示 owner-scoped 的最近三次 SimC 任务，不随职业筛选，并与四入口共同铺满正文可用高度。首页不展示具体专精、英雄天赋、模板准备状态、进度或重复工作台。天赋、装备和 SimC 使用当前职业最近有效的专精作为启动上下文，任务保持独立。

实施前必须先制作并登记新的 canonical target，以 target-only measurement 更新该路由的 inventory、geometry、truth adaptation、component/asset contract 和核心交互合同；讨论期概念稿、当前 runtime 或旧 CSS 都不能写入目标 bounds。完整设计与验收边界见 [Builds Home 职业命令卡组设计](../design/current-ui/routes/builds-home/product-design.md)。

## 共享 owner 边界

| Owner | 职责 |
| --- | --- |
| `AppShell` | safe area、设计舞台、背景、正文视口和根页 TabBar 占位 |
| `PageFrame` | root/pushed/chat 头部、返回与胶囊避让 |
| `RouteStage` / `RouteFlow` / `RouteColumn` / `RouteGrid` / `RouteRegion` | 舞台、状态、column/grid composition 和语义区域 |
| `ActionButton` / `ControlButton` | 微信原生按钮尺寸、状态和默认样式归一 |
| `ProductTabBar` | 四入口导航、唯一激活态和底部安全区 |
| `Surface/Frame`、`Glyph/Medallion` | 材质、边框、图标 fit、裁切、亮度和可信 fallback |

共享缺陷只在共享 owner 修复。Route 样式仅表达 target 独有的坐标、网格行、滚动窗口和内容 composition；不得恢复 `reconstruction.module.scss` 中已移除的 route-private 平行 owner。

## 批次与验证协议

1. 开始前建立 route 合同与当前运行态的差异矩阵，先确定共享 owner。
2. 开发期只跑变更面的 targeted tests；批次候选再跑一次类型、Taro 测试、构建和架构审计。
3. 微信在线入口必须显式给出最多 2 个路由，拒绝 `all`，复用一个 watch 和一个现有 Automator 会话，不自动 launch/reload/退出 DevTools。
4. 空 renderer、超时、旧 contract hash、缺证据或工具失败都保持 `UNVERIFIED`，不得用重启或 fallback 伪造 PASS。
5. 截图、几何、核心交互、选中态、素材槽和人工确认各自证明不同维度，不能互相替代。
6. 新 runtime evidence 只对精确 commit/viewport/contract 有效；被替代的 artifact 从工作树删除，Git 历史承担追溯。

## 当前缺口

- 8 个 `not_run_user_waived` 路由没有当前微信视觉和核心交互 acceptance；waiver 只允许合入，不等于通过。
- 当前 14 路由状态账本仍为 `UNVERIFIED`，需要未来新候选按当前 contract 重新采集，不复用旧 artifact。
- 102 个候选素材仍需按语义、裁切、清晰度、真机表现和人工确认逐项晋级。
- 产品命名和首页权重仍待 roadmap 决策；确认后必须同步活动 Taro、兼容配置、README 和 route contract。

## 完成标准

14 路由各自具备当前候选的微信可编译证据、safe area/头部/正文/TabBar/固定操作区无覆盖、目标结构和材质成立、合同要求状态稳定、核心交互可用、真实数据与可信边界不变。最终 evidence 的人工验收矩阵必须精确区分 `accepted`、`not_run_user_waived` 和 `pending`，只有 14 个路由全部 `accepted` 才能声明完整微信验收。
