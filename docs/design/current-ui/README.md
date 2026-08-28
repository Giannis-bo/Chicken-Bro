# Current UI Control Plane

本目录只保存当前 14 路由重建所需的设计事实、route 合同和最终验收合同。

## 权威映射

| 问题 | 唯一入口 |
| --- | --- |
| 14 路由分别对应哪张目标图 | `target-registry.json` |
| 目标图的可见结构与几何是什么 | route 下的 `target-inventory.json`、`target-geometry.json` |
| 目标内容如何映射真实业务 | route 下的 `truth-adaptation.json` |
| 哪个共享组件或素材槽负责实现 | route 下的 `component-contract.json`、`asset-contract.json` |
| 当前按什么顺序执行 | `docs/plans/ui-reconstruction.md` |
| 共享架构是否仍满足 14 路由合同 | `npm run audit:ui-architecture` |
| 微信三基线的结构几何是否稳定 | `npm run verify:ui-baselines` |
| 最终微信验收必须记录什么 | `runtime-review-contract.json` |
| 每条路由必须验证哪个核心交互 | `core-interaction-contract.json` |
| 哪些按钮组必须保证唯一激活材质 | `selected-control-contract.json`、`npm run verify:ui-selected-states`、`npm run promote:ui-selected-states` |
| 14 路由和原生按钮是否越出微信视口 | `route-geometry-contract.json`、`npm run verify:ui-route-geometry` |
| 如何按语义区域比较 target/runtime 几何 | `runtime-region-mapping-contract.json`、`npm run compare:ui-runtime-regions` |
| 如何晋级结构化区域差异证据 | `REGION_COMPARISON_PATH=<absolute path> npm run promote:ui-region-comparison` |
| 可见运行素材槽是否回到路由合同 | `runtime-asset-slot-mapping-contract.json`、`npm run verify:ui-asset-slots` |
| 如何合并并晋级全量素材槽证据 | `ASSET_SLOT_DETAIL_PATHS=<batch-a,batch-b> npm run promote:ui-asset-slots` |
| 如何把隔离缓存晋级为不可变运行态 artifact | `npm run promote:ui-review-cache` |

## 14 路由实现映射

`apps/mini-taro/src/app.config.ts` 是活动路由配置；根目录 `app.json` 只承担兼容消费。两者当前 14 条
path 完全同序。`target-registry.json` 中带 `/` 的 route id（如 `specialization_home/builds_home`、
`profile/templates`）以及历史大小写 `SimC_submit` 是稳定设计合同 id，不是额外页面或待修正路径。

| 设计合同 id | 微信 path | 活动 Taro owner |
| --- | --- | --- |
| `news_home` | `pages/news/news` | `apps/mini-taro/src/pages/news/news.tsx` |
| `news_list` | `pages/news/list` | `apps/mini-taro/src/pages/news/list.tsx` |
| `news_detail` | `pages/news/detail` | `apps/mini-taro/src/pages/news/detail.tsx` |
| `specialization_home/builds_home` | `pages/builds/builds` | `apps/mini-taro/src/pages/builds/builds.tsx` |
| `current_spec_workbench` | `pages/builds/workbench` | `apps/mini-taro/src/pages/builds/workbench.tsx` |
| `build_intel` | `pages/builds/intel` | `apps/mini-taro/src/pages/builds/intel.tsx` |
| `talent_simulator` | `pages/builds/talent-simulator` | `apps/mini-taro/src/pages/builds/talent-simulator.tsx` |
| `gear_detail` | `pages/builds/detail?query=gear` | `apps/mini-taro/src/pages/builds/detail.tsx` |
| `simulator_home` | `pages/simulator/simulator` | `apps/mini-taro/src/pages/simulator/simulator.tsx` |
| `SimC_submit` | `pages/simulator/simc` | `apps/mini-taro/src/pages/simulator/simc.tsx` |
| `chickenbro_chat` | `pages/simulator/chickenbro` | `apps/mini-taro/src/pages/simulator/chickenbro.tsx` |
| `tasks_list` | `pages/simulator/tasks` | `apps/mini-taro/src/pages/simulator/tasks.tsx` |
| `task_detail` | `pages/simulator/task-detail` | `apps/mini-taro/src/pages/simulator/task-detail.tsx` |
| `profile/templates` | `pages/profile/profile` | `apps/mini-taro/src/pages/profile/profile.tsx` |

活动 Taro tab 文案是“资讯、专精、队长、我的”。`app.json` 的“最新资讯、职业专精、智能分析、
我的”是兼容文案，不拥有当前 UI 决策。源码路径一致只证明配置事实；当前视觉/交互总状态仍是
`active_unverified`，14 条 route ledger 均保持 `UNVERIFIED`。

`artifacts/ui-visual-targets/current/` 保存 canonical target 本体。目录存在、源码可编译、DOM/AX 元素存在和单元测试通过只证明对应工程事实；视觉状态由 target/runtime 微信复核决定。

交付顺序、批次边界和验证节奏统一由 `docs/plans/ui-reconstruction.md` 维护，本目录不重复叙述执行流程。

目标图载荷只进入一次性隔离上下文；主项目会话只接收路径、尺寸、hash、结构化边界、差异和状态。

真实微信截图先由 `UI_REVIEW_ROUTES=<route,...> npm run capture:ui-review-cache` 写入仓库外缓存。捕获复用已存在的 DevTools 进程，但在小程序内部使用 `reLaunch(route)` 切换待审路由；manifest 必须分别记录 `captureMethod=reused_existing_wechat_devtools_process` 与 `routeNavigationMethod=mini_program_relaunch`，不得把“未重启 DevTools 进程”误写成“未 reLaunch 路由”。捕获按路由重试并在每张成功后原子更新 manifest；中途失败会保留已核验 PNG 和 pending 路由，后续同一 commit/viewport 从 checkpoint 续跑，不重启 DevTools 或重做整批。只有显式提供 `UI_REVIEW_MANIFEST=<absolute manifest path>` 和 `UI_REVIEW_ROUTES=<route,...>` 后，`npm run promote:ui-review-cache` 才会重新核验 PNG 尺寸、字节数和 SHA-256，并复制到 `artifacts/ui-runtime-reviews/<commit>/<viewport>/<sha256>/`。晋级使用不可覆盖写入并生成内容寻址 receipt；它只建立可审计 artifact，不会自动把路由标为 `PASS`。

架构审计与几何预检不是视觉通过。缺少 target/runtime 像素复核时，路由状态仍为 `UNVERIFIED`。

14 路由的当前结论只记录在 `runtime-review-status.json`。该文件必须与 target registry、核心交互合同和 route contract 根目录一致；没有路径包含自身完整 SHA-256 的微信运行态 artifact、全部通过且字段完整的区域与素材语义差异、零 P0/P1/碰撞/裁切/重叠指标、真实核心交互结果和带 UTC 时间的具名人工确认时，不得把任何路由标为 `PASS`。

`core-interaction-contract.json` 的总状态由 14 条逐路由结果推导：存在未验证项时为 `active_unverified`，任一失败时为 `active_failed`，全部真实通过后才可为 `verified`。路由视觉状态不得在对应核心交互仍未通过时晋级 `PASS`。

## 运行素材根

默认微信构建把登记素材复制到 `/assets/ui-v2`，用于本地开发和未配置远端资源的候选构建。只有显式设置合法 HTTPS 根路径时，构建才切换到远端素材并停止复制本地素材：

```bash
WOW_ASSET_RUNTIME_ROOT=https://cdn.example.com/wow-assets/releases/2026-07-18-ui-v2 npm run build:weapp
```

远端根目录必须保持 `packages/design-system/assets/` 下的相对目录结构，并以 `/releases/<release-id>` 结尾；`release-id` 至少 8 个字符且只能使用字母、数字、点、下划线和连字符。未版本化根、`latest`、查询参数、HTTP 或其他协议会在构建阶段失败。该开关只建立可验证的交付路径，不代表 CDN 已获准上线；在真实候选构建启用前，仍须确认完整资产上传与 hash、HTTPS 可用性、微信 request/download 合法域名和恢复默认本地素材构建的方式。
