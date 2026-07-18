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

Review 窗口同时覆盖共享组件、页面 JSX 中的非组件 wrapper、route SCSS 和跨路由相似布局。完全同构的舞台、状态边界、column/grid composition 或区域子视图填充必须归共享 owner；只有 target 高度、区域坐标、网格行、滚动窗口或交互覆盖范围确实不同的布局才保留 route 特化。`audit:ui-architecture` 阻断页面直接拥有 route-state/target-region-count、重复实现 stage foundation，或在 route SCSS 重建共享 column/grid/region composition；窄屏 media override 必须实际改变布局，禁止用与基础规则完全相同的声明伪装适配。RouteRegion 不得由 route SCSS 设置 `overflow:visible` 绕过内容边界；需要外溢的徽章或阴影只能在组件内部由明确 owner 控制。

## 收口审计

当前工作流控制面完整：14 个路由均已登记 canonical target，并具有目标结构、目标几何、事实适配、组件 owner 与素材槽合同；共享架构审计、微信三基线、固定批次和最终逐路由验收各有唯一入口。新执行者可以从本计划进入，不需要阅读历史计划、过程截图或会话记录。

“工作流完整”表示每个页面都有同一条可执行、可阻断、可验收的交付路径，不表示 14 个页面已获得视觉通过。`docs/project-state.json` 在最终微信证据齐备前保持 `active_unverified`。

| 系统问题 | 当前事实 | 关闭条件 |
| --- | --- | --- |
| 全量视觉闭环 | `runtime-review-status.json` 已逐路由绑定 path、canonical target、合同根与当前状态；核心交互已有不可变证据，几何和选中态则因 review 窗口扩大而把旧产物降为历史，当前契约证据重新待采。截图链路已分为仓库外 commit/viewport 缓存和显式不可变晋级：`9bb2f3c69a45` 的 390×844 DPR3 实例曾为 05、06、任务列表和任务详情晋级 4 份内容寻址 artifact 与 receipt，`93f0cbd6d065` 的四路由 26 区域比较曾作为 SHA-256 `859ba24b…39ff` 晋级。在线截图入口现拒绝 `all` 并强制每次最多 2 路由，保留按 commit/viewport 的 manifest 续跑；14 路由闭包只在不连接微信的离线晋级阶段合并，避免长批 relaunch、截图重试和图片 I/O 再次卡死 session。离线 `npm run build:ui-review-index` 会对选定 capture 与 canonical target 重新执行有界字节、尺寸和 SHA-256 校验，再原子生成最多 1 MiB 的本地 HTML 并排 review 索引；HTML 只引用 `file:` PNG，不内嵌图片、不连接 DevTools，主会话只接收 routeCount/bytes/indexPath 摘要。缓存续跑、晋级和索引都要求 PNG 是 manifest 同目录下按 route 命名的普通文件，拒绝 `../`、跨缓存引用和符号链接；底层所有有界证据读取还使用 `O_NOFOLLOW` 打开文件，关闭检查后替换成链接的竞态窗口。commit `f139a50c6877` 上仅对 05 做一次有界缓存续跑探针，8.5 秒内 0 capture，manifest 明确记录 `fail to capture screenshot` 并保留 news_detail pending；随后 renderer 为空 DOM，因此停止截图重试且未重启/刷新 DevTools。几何、交互、选中态和素材槽验证器现只向 stdout 输出计数、最多 10 个失败键和 detailPath，完整逐路由结果统一经过同一个结构化 detail owner：在线写入使用带 UUID 的唯一临时文件再原子替换，崩溃残留不会阻断下次写入；离线读取通过固定 1 MiB+1 字节缓冲执行硬上限，而不是 `stat` 后无界 `readFile`，避免文件竞争、半写文件或大型 JSON 再次压垮主 session。截图缓存和晋级现复用同一有界二进制读取基元，PNG 在 SHA-256 或尺寸解析前最多进入 8 MiB+1 字节，manifest 复用 1 MiB 有界 JSON owner；目标/运行时几何比较输出也原子写入，证据链不再保留独立无界入口。四类结构化晋级最多接收 14 个 detail；截图 artifact、receipt 和结构化 evidence 均先写唯一临时文件，再以原子硬链接建立不可变目标，重复晋级逐字节校验，截图只晋级已经过尺寸与 SHA-256 验证的 buffer，不再重新复制可能变化的源路径。旧四路由目标/运行时区域比较晋级器也已接入 1 MiB 有界读取和同一原子不可变 owner，并要求精确覆盖 mapping contract，partial comparison 不再能冒充闭包。四路由仍缺当前 commit 素材质感和人工确认，其余路由还缺不可变截图 artifact，14/14 继续保持 `UNVERIFIED` | 截图接口恢复后从 pending manifest 续跑；按当前契约重新采集几何和选中态证据，每路由按 `runtime-review-contract.json` 提交完整结论，并由人工确认后单独晋级 |
| 素材生产链 | 14 个路由素材合同均已登记：`news_home` 1 个已进入微信生产状态，其余保持 candidate/partial/no-promotion。14/14 路由现均有运行子槽到概念合同槽/共享非事实槽的显式映射；`16e4da777937` 的 390×844 DPR3 微信实例分批扫描 506 个可见素材元素、路由内累计 145 个唯一槽，未登记槽、`undefined` 槽和 `asset-missing=true` 均为 0，并已合并为 SHA-256 `e75fb966…fc16` 的内容寻址历史证据。跨路由同名运行槽必须映射到唯一 canonical shared role；反向 assetId→slot 审计现覆盖普通、frame 和 fallback 三类共 193 个字面量绑定并 deny-by-default，未登记跨语义复用直接失败。News Detail 的 6 个 CSS-only 面板已删除不会渲染却仍发布 `news-frame.*` 身份的假绑定，`ForgedPanel` 在 `frameMode=none` 时不再输出 frame asset 元数据。06 的三张 imagegen 候选已注册并绑定，productionPromoted/productionPromotionAuthorized 仍为 false；真实微信历史扫描 62 元素 / 9 槽、missing 0，只证明接线。后续 builds-home 定向扫描在截图 API 失败后遇到 renderer 空 DOM：两个路由均为 0 元素 / 0 槽，旧验证器曾错误 PASS；当前验证器和晋级器均拒绝空路由，该批明确排除且未通过重启掩盖。离线集成审计现覆盖整个 mini app 与 design-system 源码，并精确记录 builds-home `complete_23_of_23`（未独立审查、未生产晋级）、news-home `partial_27_of_33`（已生产家族含 6 个当前未引用 fallback/control 变体）、shared-chrome `partial_1_of_5`（仅 back medallion 接线）；这些计数与 registry、源码引用不一致即失败 | 素材进入统一 manifest，完成裁切、语义、清晰度和真机复核后晋级；renderer 恢复后从小批素材槽扫描续跑，COS/CDN 迁移作为独立工作包执行 |
| 包体与远端资源 | `npm run verify:ui-package` 在当前 HEAD 的隔离临时目录复跑两种 production 构建：本地素材包 5,038,167 bytes / 214 个文件 / 137 个素材文件，逐路径闭包为 expected 137 / missing 0 / unexpected 0；切换到占位远端根后为 1,772,579 bytes / 77 个文件 / 0 个本地素材文件，`common.js` 383,166 bytes、`common.wxss` 343,856 bytes，机械预算通过。包体检查最多遍历 4,096 个文件，单文本文件最多读取 1 MiB，JS/JSON/WXML/WXSS 总读取量最多 4 MiB，异常构建不会先于预算判定压垮任务。但远端根仍是 `.invalid` 占位域名，因此报告必须是 `status: partial`、`packageMechanicsPass: true`、`releaseReady: false`，不能再把理论远端包误报为可发布；`npm run verify:ui-package:release` 会在未提供获批 `WOW_ASSET_RUNTIME_ROOT` 时失败。`npm run verify:ui-asset-integrity` 另对 6 个 raster collection、69 个 asset ID、138 个 1x/2x runtime 文件以 64 KiB 分块逐一复算 3,807,528 bytes 与 SHA-256，byte/hash mismatch 均为 0；单素材上限 8 MiB、单 manifest 上限 1 MiB，不整图加载、解码或输出图片。生产资产上传/hash 与微信 download 合法域名审批尚未形成可验证记录 | 配置并审批版本化 HTTPS `WOW_ASSET_RUNTIME_ROOT`，上传后逐文件复核 hash，再以 `npm run verify:ui-package:release` 得到 `releaseReady: true`；路径闭包、字节哈希和机械预算由隔离门禁持续阻断回归 |
| 微信 API 请求域名 | `npm run audit:taro-domain` 为 report-only：开发 origin 与 H5 proxy 均为显式 HTTP IP，认证请求在非 HTTPS 下 fail-closed，仓库未提交域名校验绕过；生产 `WOW_BACKEND_API_BASE_URL` 尚未配置为 HTTPS 命名 origin，`WOW_WECHAT_REQUEST_DOMAIN_APPROVED=yes` 审批记录缺失 | 配置生产 HTTPS 命名后端，在微信后台批准 request 合法域名，并以两项生产环境变量复跑审计为 `productionReady: true` |
| 一级页面一致性 | 四个 root route 已共享 `PageFrame` 与 `ProductTabBar` owner。真实微信曾显示 shellBody 为 0–844、固定 TabBar 为 747–844，profile 末端设置区 649.95–843.95，证明旧 padding 方案允许正文绘制在底栏后方。共享 AppShell 现把 root shellBody 高度限定为 `100vh - tabbar-safe-height`；四路由复核均为 shellBody.bottom 747 = TabBar.top 747、零重叠，长内容保持可滚，新闻与模拟首页末端内容留在可视区。TabBar 仍为 4 项、1 active / 3 inactive、材质 mismatch 0 | 四个一级页面在相同 viewport 下持续通过安全区、头部、正文起点、滚动裁切和 TabBar 唯一激活态对比 |
| 页面状态稳定性 | ready 主路径已有实现，loading、empty、error、stale 的完整几何证据仍不齐 | 每路由至少覆盖合同要求的可达状态，确认状态切换不改变共享 chrome 和关键布局 |
| 真实微信视口与安全区 | `route-geometry-contract.json` 与 `npm run verify:ui-route-geometry` 已把 14 路由共享 shell、顶层 RouteRegion、原生 Button 与 `View role=button` 的横纵边界、根页 TabBar、设备 safe area 以及 06/SimC/12 的首屏终端区域纳入 1px 容差门禁；非 unavailable 路由若没有语义区域会以 `missing-route-regions` 失败。真实微信为 390×844 DPR3、safeAreaBottom 810、safeBottomInset 34；固定 dock 控件必须直接结束在安全底边之上。旧验证器只查询原生 `button`，导致 Simulator dock 的三个 View 控件形成空集合 PASS；当前查询会合并并去重两类交互节点，Simulator 上传/链接/发送和 Chickenbro 新话题/发送共 5 个具名 dock 控件必须存在，否则以 `missing-fixed-dock-control` 失败。Chickenbro composer、12 底部动作与 SimC footer 已完成样式修复。06 已移除 `824px` 页面最小高度与 `498.75px` 卡片区固定高度的冲突，改由 `route-safe-viewport-height` 分配可收缩的内部卡片滚动区，终端免责声明不再被固定总高推出安全视口。12 列表与详情页也统一使用 `route-safe-viewport-height - space-12`，与 `shellBody` 内容盒完全一致，避免百分比高度或重复底部留白把终端按钮推出首屏。SimC 已移除 818px 固定舞台，八个纵向区域按原基线换算为受审计的百分比坐标，footer 与提交动作随同一安全内容视口缩放；SimC 与 Chickenbro 的 17 个绝对区域横向坐标也已从 390px 固定宽度换算为百分比，审计保证 `left + width ≤ 100%`，避免 320/360px 微信窗口横向崩坏。后续全路由审计又发现 `gear_detail` 双选择器和 `simulator_home` 三个绝对区域仍使用 164–368px 固定宽度：这些区域现按原设计比例或左右锚点缩放，架构门禁禁止任何 `*Region` 再引入固定 px 宽度。历史 commit `b67be415751e` 曾采集 14/14 pass、零 violation，但它早于 `initialSafeAreaRegionIds` 和 role-button dock 规则，现已降为历史而非当前证明。新 detail 和晋级产物必须携带当前几何契约 SHA-256，旧规则产物无法晋级；06 内部滚动卡片和具名横向内容仍仅使用精确角色例外，失败明细硬限制前 10 条 | renderer 恢复后在既有 Automator endpoint 上按路由小批复跑当前契约；固定 dock、首屏终端区域、根页 TabBar 与可滚正文使用不同安全区规则，不能用全局 overflow 豁免 |
| 选中态唯一性 | `selected-control-contract.json` v3 已登记 11 个高风险控件组，限制最多一个激活状态，并要求 `data-selection-material` 与 selected/active 状态一一对应；连续分段与独立按钮现在显式分类，连续组逐项发布 `data-leading-boundary=active/suppressed/inactive`。运行时 detail v3 按控件顺序推导期望边界并统计 mismatch，晋级器拒绝任何边界不匹配，补上旧 v2 无法读取 `::before` 普通分隔线的证据盲区。05 翻译栏、产品 TabBar、新闻频道、两套天赋页签和任务筛选已统一关闭激活项自身及紧邻右侧的普通分隔层；任务筛选另已删除与 `data-selected` 重复绘制材质的本地 `filterSelected` class，状态材质只保留一个 owner。进一步反向扫描发现 TabBar、频道、新闻分类、05 翻译、天赋、装备和 SimC 场景等 8 个组件仍同时用条件 active class 与合同 attribute 驱动同一状态；这些 class/selector marker 已全部删除，CSS 统一响应控件自身 `data-selected=true` 或 `data-active=true`，子图标只继承父状态。静态审计现在从所有 `data-selection-material` JSX 发布点反向提取 role、唯一 state attribute 和 boundary，要求发布 role 与 11 组合同双向闭包；当前为 12 个发布点、11 个唯一 role，news-list 的两个共享实现均受同一合同约束。历史 commit `cee4032427a8` 曾得到 10 组 pass + `talent` unavailable/stale，但早于双边界和单 attribute owner 策略，现已降为历史。新 detail 和晋级产物必须携带当前 selected-control 契约 SHA-256，旧规则产物无法晋级；所有原生 Button 继续只能通过共享 owner，门禁验证其清除微信默认尺寸、间距与 `::after` 边框。Gear Detail 的主操作按钮已移除 347px 三重宽度锁定，改由左右锚点和 `max-width:100%` 共同约束；共享审计禁止大型 Action/Button/Control 再引入固定像素宽度 | renderer 与生产请求域名恢复后补跑当前 11 组 v3 契约；新增 `data-selected`/`data-active` 组必须登记稳定 role、唯一激活上限、连续/独立边界模式和唯一材质 owner，并通过同 commit 的不可变全量 artifact |
| 核心交互 | `core-interaction-contract.json` 已为 14 路由各登记一个源码 owner、稳定选择器、前置条件、动作与预期。验证器支持按小批原子写入携带 commit/viewport 的结构化 detail；晋级器只接受同 commit/viewport、精确 14 路由、零 FAIL/零重复的闭包，并仅允许合同具名状态成为 `UNAVAILABLE`。历史 commit `b8d01d20a1ab` 曾由 7 个双路由小批合并出 13 条 PASS + `talent` UNAVAILABLE/stale 的 SHA-256 `abf32769…408f0` 不可变证据；之后运行时 UI 的按钮身份、区域闭包和素材绑定已变化，因此该产物已降为历史，不再关闭当前交互缺口。talent 在同 commit 几何批次曾正常渲染 8 区域，交互批次随后进入 stale 且树 Tab 为 0，证明外部数据前置会波动，不能伪造 PASS | renderer 与生产请求域名恢复后按当前源码重新采集 14 路由；继续使用小批 detail 合并，不运行易退化的单次长批，不 launch/重载 DevTools |
| 业务事实边界 | Taro 通过 typed API 消费 resolver、community import 和 stat snapshot；装备主属性、兼容性与徽标由后端拥有 | 架构审计持续阻断前端重建职业/装备规则，前端只负责展示映射 |
| 产品命名 | roadmap 定义“智能分析”，当前运行导航仍使用“队长” | 产品决策后一次同步导航、标题、README 与 route 合同 |

稳定性执行约束：所有微信在线入口仍要求显式路由小批且每批最多 2 路由，禁止 `all`、禁止 launch/reload DevTools。单页几何读取最多 32 个 RouteRegion、128 个按钮、64 个控制单元和 32 个 dock 按钮；素材槽与 material owner 各最多 128 个，单组选中态和核心交互候选各最多 32 个。超限必须保留真实查询数量并结构化 FAIL，不能截断后伪造 PASS。14 路由语义区域合同与源码 `RouteRegion` 发布集合双向闭包，运行时同时拒绝缺失、重复、匿名和未登记区域；8 个 RouteStage 的 `targetRegionCount` 必须匹配组件合同 `stableRegionCount`。安全区/固定 dock 的 9 个关键 control role 必须各有唯一源码发布者；合同声明首屏终端区域或按钮的 4 条路线必须从自身 CSS Module 消费共享 `--route-safe-viewport-height`，route SCSS 禁止重新引入 `100vh/dvh/svh` 或直接读取 `env(safe-area-*)`。所有原生 Button 必须经共享 owner 清除微信默认宽度、最小尺寸、间距、圆角、背景、字体/行高/对齐和 `::after` 边框，组件规则不得用非零横向 margin 把按钮推出直接布局单元。窄屏硬控件宽度、刚性网格及最小网格 footprint 同时审计 design-system 和 route SCSS；每个已锚定 RouteRegion 都必须在 320×568 最小视口获得可计算的横纵几何，解析器覆盖无单位零、百分比、px、像素变量和简单 `calc`，并要求正宽正高、固定像素底边留在所属舞台内；同一舞台禁止混用像素与百分比纵向坐标，全部区域矩形还要通过 1px 容差的全 pairwise 二维碰撞检查。目标/运行时比较的目标 geometry 与 runtime detail 均使用 1 MiB 有界 JSON owner。任何超限、空 renderer 或旧契约 SHA 均保留为未验证状态，不触发自动重启来掩盖失败。

素材状态证据约束：所有发布 `data-asset-id` 的五类渲染 owner 必须同时从统一 manifest 发布 `data-promotion-status=production_promoted/candidate_pending_review/missing`。当前完整队列覆盖 1 个 vector manifest 与 6 个 raster collection，共 135 个资产：33 个已生产晋级、102 个待审；vector 的 66 个 `untrusted_candidate` 不得再被 raster-only 统计漏掉。素材槽 detail v3 记录逐路由生产、候选、缺失和可见 material owner 计数；缺少合法状态的可见素材、非法 owner 或 owner 计数不闭合均不能晋级。素材槽与几何、交互、选中态 detail 共用同一个有界原子 JSON owner，异常中断或超大文件不得破坏续跑。任何内部包含 ProductionAsset/NineSliceFrame 的交互 owner 都必须显式声明 `data-material-owner=asset/css`，范围包括 ControlButton 和非组件 `View role=button` wrapper：完整底板只能由 asset 绘制，徽章、节点或 glyph 则由 css 拥有按钮材质，禁止两套底板语义同时存在。反向 AST 审计已覆盖 9 个以上实际交互素材节点；共享 shell 还会对任何 `data-material-owner=asset` 的原生 button 或 `View role=button` 统一清除 CSS border/background/box-shadow，当前 3 条完整底板 owner 均受此兜底。共享 ActionButton 仅在 `assetRuntimePath` 真实可用时切换为 asset owner并渲染 NineSliceFrame，素材缺失或远端根不可用时保持 css fallback，避免从双底板退化为无底板。Build Workspace 同样根据 frame 可用性动态切换 owner，TabBar、模拟任务台与 Profile 分类等图标型交互明确由 css 拥有底板。该证据只区分生产与候选，不会把“已接线”冒充“已完成真机与人工复核”。

上述条目是当前长期缺口，不记录某次执行过程。临时截图、一次性脚本和旧计划不进入仓库；Git 历史承担追溯职责。

## 当前工作包

- 主干接合：Taro typed API 对齐 resolver、community import 与 stat snapshot；后端只读审计，改动边界保持在前端。
- UI 治理：先修共享 chrome、TabBar、medallion 与素材 fit，再处理 route composition。
- 当前批次：builds，优先 `builds_home` 和 `gear_detail` 的尺度、图标裁切与装备选择交互。Gear Detail 三列强化控件现跟随 `minmax(0, 1fr)` 轨道收缩；Workbench readiness 操作从固定 `min-width:164px` 改为父栏宽度与 164px 上限共同约束。继续扩大到非组件 wrapper 后发现 Workbench Evidence Ledger 在 320px 微信宽度下，内部约 286px 内容盒小于旧三列最小宽度、gap 与 padding 的 292px 总需求；标题和行列现改为 92/74/42px 可伸缩下限并为行体补 `min-width:0`。架构审计禁止大型控件固定宽度、禁止 Action/Button/Control 使用 96px 以上固定最小宽度，并禁止一个组件网格同时堆叠两个 100px 以上刚性最小列；通用 footprint 门禁还会解析固定列、`minmax()` 下限、`repeat()`、列间距和显式水平 padding，任何组件网格的最小总占用不得超过 286px 窄屏内容盒，同时保留明确位于横向 ScrollView 内的职业选项宽度。

## 微信验收与恢复链路

1. 保持一个 `taro build --type weapp --watch`，不得为单次验收再启动第二个 watch。
2. 验证入口默认复用 `9420-9460` 范围内已监听的 automation 端口，或连接明确提供的 `WECHAT_AUTOMATOR_ENDPOINT`；默认不得调用 DevTools CLI `auto`，因为它可能导致窗口重载。
3. 只有确认当前没有可复用 endpoint、且允许一次性建立 automation 会话时，才显式设置 `WECHAT_AUTOMATOR_LAUNCH=1`。同一会话后续验证必须连接既有端口，不得重复 launch、退出或重启开发者工具。
4. 连接恢复后依次执行结构几何预检、当前批次核心交互、14 路由 target/runtime 复核；三者证据不可互相替代。截图、几何、核心交互、选中态和素材槽五类在线入口统一要求显式路由、拒绝 `all` 且每次最多 2 路由；空环境变量不得默认为全量执行。各小批 detail 仅由对应离线晋级器合并为精确 14 路由闭包。
5. 结构预检输出 `visualPixelReview: UNVERIFIED` 是预期边界。只有按 `runtime-review-contract.json` 齐备运行态 artifact、target 映射、区域差异、素材语义、碰撞和交互结果，并经人工确认，路由才可标记 `PASS`。
6. 最终候选再执行一次 Harness `full` 和 GitHub CI；工具恢复过程不生成第二套监督器、临时截图档案或会话记录。
7. 若仓库已有 `.git/gc.log` 且包含大量不可达 loose objects，长期任务只允许用仓库本地 `gc.auto=0` 停止每次 commit 的重复自动整理尝试；不得在验收过程中删除 `gc.log`、运行 `prune` 或手动 `gc`，以免制造长时间停顿或破坏恢复对象。
8. GitHub Project Harness 以 PR 编号建立 concurrency group，并启用 `cancel-in-progress`；连续 push 时只保留最新 HEAD，旧 HEAD 不得继续并发占用完整 Harness 容量。

## 完成标准

14 个路由均满足：微信可编译；安全区、头部、正文、TabBar 和固定输入区互不覆盖；目标结构、材质、图标层级与信息密度成立；ready/loading/empty/error 几何稳定；核心交互可用；真实数据与可信边界不变。
