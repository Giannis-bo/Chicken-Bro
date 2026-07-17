# WOW 小程序 UI 重建

状态：`正在推进`

## 目标

以 `artifacts/ui-visual-targets/current/` 的 14 张 canonical target 为视觉事实，以当前 Taro、typed API/domain 和真实路由状态为业务事实，交付可编译、可交互、布局稳定的微信小程序。

## 权威输入

1. `docs/design/current-ui/target-registry.json`
2. 当前 route 的 `target-inventory.json` 与 `target-geometry.json`
3. 当前 route 的 `truth-adaptation.json`、`component-contract.json` 与 `asset-contract.json`
4. `DESIGN.md`、当前 API/domain 与源码

## 交付顺序

`全量目标 -> 设计语言 -> 共享 owner -> 微信三基线 -> 固定路由批次 -> 最终验收`

| 阶段 | 产物 | 完成标准 |
| --- | --- | --- |
| 目标固化 | registry、inventory、target geometry | 14 路由的结构、几何和素材角色完整 |
| 事实适配 | truth adaptation | 可见槽位均有真实字段、状态、动作和 fallback |
| 共享实现 | AppShell、PageFrame、ProductTabBar、控件与素材 owner | 共享几何由共享 owner 负责 |
| 三基线 | `news_home`、`simulator_home`、`news_detail` | 根页、深路由、安全区、滚动与原生控件稳定 |
| 批次传播 | news、builds、simulation/profile | 每批集中修复后进入一次运行态复核 |
| 最终验收 | 14 路由 review | 每路由一份最终结论和一个核心交互结果 |

## 共享 owner

| Owner | 职责 |
| --- | --- |
| `AppShell` | 安全区、390px 设计舞台、背景和纵向滚动 |
| `PageFrame` | root / pushed / pushed-action / chat 头部与胶囊避让 |
| `RouteStage` / `RouteFlow` / `RouteColumn` / `RouteGrid` / `RouteRegion` | 固定舞台、流式状态边界、纵向 composition、首页 grid 与区域子视图填充基础；route 只保留 target 高度、区域坐标、网格行、滚动和内容特化 |
| `ActionButton` / `ControlButton` | 微信原生控件的尺寸与状态归一 |
| `ProductTabBar` | 四个一级页面的四等分导航、底部安全区和正文占位 |
| `Surface/Frame` | 边框、纹理、阴影和 fallback |
| `Glyph/Medallion` | 图标 fit、裁切、尺寸、亮度、状态和 fallback |

共享缺陷在共享 owner 修复；route 样式只表达目标中独有的内容 composition。

## 固定批次

1. news：`news_home`、`news_list`、`news_detail`
2. builds：`builds_home`、`current_spec_workbench`、`build_intel`、`talent_simulator`、`gear_detail`
3. simulation/profile：`simulator_home`、`simc_submit`、`chickenbro_chat`、`tasks_list`、`task_detail`、`profile_templates`

## 批次协议

1. 开始前用 route 合同和运行态几何建立一张差异矩阵，并一次确定共享 owner。
2. 在同一批次内集中实现；编辑阶段只运行快速静态检查，不启动微信全量巡检。
3. 批次实现完成后只执行一次目标测试、一次构建和一次真实微信复核。
4. 微信复核复用单一 watch 与单一 Automator 连接；自动扫描到的候选端口握手最多 2 秒，显式 endpoint/launch、单路由和总流程均有硬超时。
5. 工具链失败时保留 `UNVERIFIED` 和诊断结果，下一轮先恢复环境；不在实现任务中扩建监督器、端口发现器或第二套验证框架。
6. 单元测试、构建和 DOM 几何用于阻断回归；视觉通过只来自 target/runtime 对比和用户确认。

Review 窗口同时覆盖共享组件、页面 JSX 中的非组件 wrapper、route SCSS 和跨路由相似布局。完全同构的舞台、状态边界、column/grid composition 或区域子视图填充必须归共享 owner；只有 target 高度、区域坐标、网格行、滚动窗口或交互覆盖范围确实不同的布局才保留 route 特化。`audit:ui-architecture` 阻断页面直接拥有 route-state/target-region-count、重复实现 stage foundation，或在 route SCSS 重建共享 column/grid/region composition。

## 收口审计

当前工作流控制面完整：14 个路由均已登记 canonical target，并具有目标结构、目标几何、事实适配、组件 owner 与素材槽合同；共享架构审计、微信三基线、固定批次和最终逐路由验收各有唯一入口。新执行者可以从本计划进入，不需要阅读历史计划、过程截图或会话记录。

“工作流完整”表示每个页面都有同一条可执行、可阻断、可验收的交付路径，不表示 14 个页面已获得视觉通过。`docs/project-state.json` 在最终微信证据齐备前保持 `active_unverified`。

| 系统问题 | 当前事实 | 关闭条件 |
| --- | --- | --- |
| 全量视觉闭环 | `runtime-review-status.json` 已逐路由绑定 path、canonical target、合同根与当前状态；真实微信已完成 14 路由结构/几何与核心交互证据闭环。截图链路已分为仓库外 commit/viewport 缓存和显式不可变晋级：`9bb2f3c69a45` 的 390×844 DPR3 实例已为 05、06、任务列表和任务详情晋级 4 份内容寻址 artifact 与 receipt，`93f0cbd6d065` 的四路由 26 区域比较已作为 SHA-256 `859ba24b…39ff` 晋级。commit `273f14ed2ed0` 上再次只对 05 做单路由三次有界探测，6.3 秒内 0 capture、明确留下 pending manifest 后停止；未重启/刷新 DevTools，结构接口继续正常。四路由仍缺当前 commit 素材质感和人工确认，其余路由还缺不可变截图 artifact，因此 14/14 继续保持 `UNVERIFIED` | 截图接口恢复后从 pending manifest 续跑；每路由按 `runtime-review-contract.json` 提交完整结论，并由人工确认后单独晋级 |
| 素材生产链 | 14 个路由素材合同均已登记：`news_home` 1 个已进入微信生产状态，其余保持 candidate/partial/no-promotion。14/14 路由现均有运行子槽到概念合同槽/共享非事实槽的显式映射；`16e4da777937` 的 390×844 DPR3 微信实例分批扫描 506 个可见素材元素、路由内累计 145 个唯一槽，未登记槽、`undefined` 槽和 `asset-missing=true` 均为 0，并已合并为 SHA-256 `e75fb966…fc16` 的内容寻址全量证据。跨路由同名运行槽必须映射到唯一 canonical shared role；反向 assetId→slot 审计对 154 个字面量绑定 deny-by-default，未登记 raster/材质复用直接失败。news detail 的证据标题误用已修复并在微信扫描 17 元素 / 8 槽、missing 0、旧槽 0。06 的三张 imagegen 候选此前 manifest 错写为未注册/未接线；当前事实是 registry 已导入且组件已绑定，元数据现改为 candidate bound、runtime composition review pending，productionPromoted/productionPromotionAuthorized 仍为 false。真实微信 06 定向扫描 62 元素 / 9 槽、missing 0，summary medallion、card shell、primary action 三个候选槽全部出现；这只证明接线，不替代清晰度、组合和人工验收。审计同时要求 raster manifest 的 registered/wired 声明与 registry import、源码引用一致 | 素材进入统一 manifest，完成裁切、语义、清晰度和真机复核后晋级；COS/CDN 迁移作为独立工作包执行 |
| 包体与远端资源 | `npm run verify:ui-package` 在隔离临时目录复跑两种 production 构建：本地素材包 5,046,338 bytes / 137 个素材文件，且与 6 个 raster runtime 家族及 vector 源目录逐路径闭包一致（expected 137 / missing 0 / unexpected 0）；显式版本化 HTTPS 素材根包 1,780,750 bytes / 0 个本地素材文件，已确认编译产物包含配置根且只保留一处未执行的默认 fallback 定义；`common.js` 384,138 bytes，`common.wxss` 351,728 bytes，均通过当前预算且不覆盖唯一 watch 输出。全部已登记 production/candidate asset 在切换根后均解析到 HTTPS 前缀，构建配置与运行时清单复用同一不可变根校验器，未版本化根会在构建阶段失败；生产资产上传/hash 与微信 request/download 合法域名审批尚未形成可验证记录 | COS/CDN 上传/hash、域名审批和生产 URL 在资源交付工作包内关闭；不可变路径、运行根切换、路径闭包与包体预算由隔离门禁持续阻断回归 |
| 微信 API 请求域名 | `npm run audit:taro-domain` 为 report-only：开发 origin 与 H5 proxy 均为显式 HTTP IP，认证请求在非 HTTPS 下 fail-closed，仓库未提交域名校验绕过；生产 `WOW_BACKEND_API_BASE_URL` 尚未配置为 HTTPS 命名 origin，`WOW_WECHAT_REQUEST_DOMAIN_APPROVED=yes` 审批记录缺失 | 配置生产 HTTPS 命名后端，在微信后台批准 request 合法域名，并以两项生产环境变量复跑审计为 `productionReady: true` |
| 一级页面一致性 | 四个 root route 已共享 `PageFrame` 与 `ProductTabBar` owner。真实微信曾显示 shellBody 为 0–844、固定 TabBar 为 747–844，profile 末端设置区 649.95–843.95，证明旧 padding 方案允许正文绘制在底栏后方。共享 AppShell 现把 root shellBody 高度限定为 `100vh - tabbar-safe-height`；四路由复核均为 shellBody.bottom 747 = TabBar.top 747、零重叠，长内容保持可滚，新闻与模拟首页末端内容留在可视区。TabBar 仍为 4 项、1 active / 3 inactive、材质 mismatch 0 | 四个一级页面在相同 viewport 下持续通过安全区、头部、正文起点、滚动裁切和 TabBar 唯一激活态对比 |
| 页面状态稳定性 | ready 主路径已有实现，loading、empty、error、stale 的完整几何证据仍不齐 | 每路由至少覆盖合同要求的可达状态，确认状态切换不改变共享 chrome 和关键布局 |
| 真实微信视口与安全区 | `route-geometry-contract.json` 与 `npm run verify:ui-route-geometry` 已把 14 路由共享 shell、顶层 RouteRegion、原生 Button 横纵边界、根页 TabBar 边界和设备 safe area 纳入 1px 容差门禁；非 unavailable 路由若没有语义区域会以 `missing-route-regions` 失败。真实微信为 390×844 DPR3、safeAreaBottom 810、safeBottomInset 34；固定 dock 控件必须直接结束在安全底边之上，Chickenbro composer 原先按钮 bottom 831，现由共享 AppShell owner 统一加底部安全区并降到 797。12 曾因 route frame 只扣顶部安全区，底部“查看详情”到 830.23；当前 frame 消费共享 `--route-safe-viewport-height`，按钮降到 782.72。SimC footer 与“任务规则”按钮也从 844 降到 808。合同的 `initialSafeAreaButtonRoles` 要求两路由指定终端动作首屏就结束在 810 安全底边之上，不能再用滚动 padding 豁免；横向专精按钮仍仅通过精确 role 获取横向滚动例外。commit `b67be415751e` 已按 4 个小批复用既有微信实例采集 14/14 pass、零 unavailable、零 violation 的当前完整 detail，并晋级为 SHA-256 `afb8df11…7eed6` 的内容寻址不可变证据；四个根页均为 shellBody.bottom 747 = TabBar.top 747，06 最大区域右边界 380.5，12 最大区域底边 794.72。晋级器继续要求同 commit/viewport/safeArea、精确路由闭包且拒绝任何假绿；06 内部滚动卡片和具名横向内容仍使用精确角色例外，失败明细硬限制前 10 条 | CI 持续运行静态合同门禁；涉及几何的变更在既有 Automator endpoint 上按路由小批复跑，固定 dock、首屏终端动作、根页 TabBar 与可滚正文使用不同安全区规则，不能用全局 overflow 豁免 |
| 选中态唯一性 | `selected-control-contract.json` v2 已登记 11 个高风险控件组，统一限制最多一个激活状态，并要求每个可用控件的 `data-selection-material` owner 与 selected/active 状态一一对应。验证器现可按小批原子写入 commit/viewport/detail，离线晋级器要求精确 11 组闭包、零重复、零 fail、合同允许的 unavailable 和所有 pass 组 `materialMismatches=0`。commit `cee4032427a8` 的 390×844 DPR3 实例已由 3 个小批合并，10 组 pass + `talent` unavailable/stale 作为 SHA-256 `78a24209…291c8` 的内容寻址不可变证据晋级。可用组覆盖产品 TabBar、新闻频道/分类、05 翻译状态、装备职业/槽位/增强项、SimC 专精/场景和任务筛选，全部材质错配 0；05 为 1 active / 2 inactive，SimC 专精为 1 / 39，场景为 1 / 2。05 已移除相邻普通项直接持有的 `border-left`，改由独立分隔层绘制并在选中项两侧关闭；所有原生 Button 继续只能通过共享 owner，门禁验证其清除微信默认尺寸、间距与 `::after` 边框 | 生产请求域名恢复后补跑 `talent`；新增 `data-selected`/`data-active` 交互组必须登记稳定 role、唯一激活上限和独占材质 owner，并通过同 commit 的不可变全量 artifact |
| 核心交互 | `core-interaction-contract.json` 已为 14 路由各登记一个源码 owner、稳定选择器、前置条件、动作与预期。验证器支持按小批原子写入携带 commit/viewport 的结构化 detail；晋级器只接受同 commit/viewport、精确 14 路由、零 FAIL/零重复的闭包，并仅允许合同具名状态成为 `UNAVAILABLE`。commit `b8d01d20a1ab` 的 390×844 DPR3 实例已由 7 个双路由小批合并，13 条 PASS + `talent` UNAVAILABLE/stale 作为 SHA-256 `abf32769…408f0` 的当前内容寻址不可变证据晋级。talent 在同 commit 几何批次曾正常渲染 8 区域，交互批次随后进入 stale 且树 Tab 为 0，证明是外部数据前置波动而非可伪造的 PASS；其余导航、折叠、排序、草稿、刷新和重置均按合同通过。装备选择保持本地草稿先落地、选择面板先关闭，再异步校验 | 生产请求域名批准后补跑 `talent`；交互变化继续使用小批 detail 合并，不运行易退化的单次 14 路由长批，不 launch/重载 DevTools |
| 业务事实边界 | Taro 通过 typed API 消费 resolver、community import 和 stat snapshot；装备主属性、兼容性与徽标由后端拥有 | 架构审计持续阻断前端重建职业/装备规则，前端只负责展示映射 |
| 产品命名 | roadmap 定义“智能分析”，当前运行导航仍使用“队长” | 产品决策后一次同步导航、标题、README 与 route 合同 |

上述条目是当前长期缺口，不记录某次执行过程。临时截图、一次性脚本和旧计划不进入仓库；Git 历史承担追溯职责。

## 当前工作包

- 主干接合：Taro typed API 对齐 resolver、community import 与 stat snapshot；后端只读审计，改动边界保持在前端。
- UI 治理：先修共享 chrome、TabBar、medallion 与素材 fit，再处理 route composition。
- 当前批次：builds，优先 `builds_home` 和 `gear_detail` 的尺度、图标裁切与装备选择交互。

## 微信验收与恢复链路

1. 保持一个 `taro build --type weapp --watch`，不得为单次验收再启动第二个 watch。
2. 验证入口默认复用 `9420-9460` 范围内已监听的 automation 端口，或连接明确提供的 `WECHAT_AUTOMATOR_ENDPOINT`；默认不得调用 DevTools CLI `auto`，因为它可能导致窗口重载。
3. 只有确认当前没有可复用 endpoint、且允许一次性建立 automation 会话时，才显式设置 `WECHAT_AUTOMATOR_LAUNCH=1`。同一会话后续验证必须连接既有端口，不得重复 launch、退出或重启开发者工具。
4. 连接恢复后依次执行结构几何预检、当前批次核心交互、14 路由 target/runtime 复核；三者证据不可互相替代。
5. 结构预检输出 `visualPixelReview: UNVERIFIED` 是预期边界。只有按 `runtime-review-contract.json` 齐备运行态 artifact、target 映射、区域差异、素材语义、碰撞和交互结果，并经人工确认，路由才可标记 `PASS`。
6. 最终候选再执行一次 Harness `full` 和 GitHub CI；工具恢复过程不生成第二套监督器、临时截图档案或会话记录。

## 完成标准

14 个路由均满足：微信可编译；安全区、头部、正文、TabBar 和固定输入区互不覆盖；目标结构、材质、图标层级与信息密度成立；ready/loading/empty/error 几何稳定；核心交互可用；真实数据与可信边界不变。
