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
4. 微信复核复用单一 watch 与单一 Automator 连接；连接、单路由和总流程均有硬超时。
5. 工具链失败时保留 `UNVERIFIED` 和诊断结果，下一轮先恢复环境；不在实现任务中扩建监督器、端口发现器或第二套验证框架。
6. 单元测试、构建和 DOM 几何用于阻断回归；视觉通过只来自 target/runtime 对比和用户确认。

## 收口审计

当前工作流控制面完整：14 个路由均已登记 canonical target，并具有目标结构、目标几何、事实适配、组件 owner 与素材槽合同；共享架构审计、微信三基线、固定批次和最终逐路由验收各有唯一入口。新执行者可以从本计划进入，不需要阅读历史计划、过程截图或会话记录。

“工作流完整”表示每个页面都有同一条可执行、可阻断、可验收的交付路径，不表示 14 个页面已获得视觉通过。`docs/project-state.json` 在最终微信证据齐备前保持 `active_unverified`。

| 系统问题 | 当前事实 | 关闭条件 |
| --- | --- | --- |
| 全量视觉闭环 | 架构合同覆盖 14 路由，最终 target/runtime 微信复核尚未覆盖 14 路由 | 每路由按 `runtime-review-contract.json` 提交完整结论，并由人工确认 |
| 素材生产链 | `news_home` 素材族已进入微信生产状态；builds、workbench、build-intel、talent-simulator 等仍包含生成待审、复用待验或未晋级槽位 | 素材进入统一 manifest，完成裁切、语义、清晰度和真机复核后晋级；COS/CDN 迁移作为独立工作包执行 |
| 包体与远端资源 | 默认本地素材构建约 5.4 MB；显式 HTTPS 素材根构建约 1.9 MB 且不复制本地素材。路由按 owner 文件导入后，生产 `common.js` / `common.wxss` 已由约 608/603 KB 降至约 373/345 KB；生产资产上传、不可变 URL 与微信 request/download 合法域名审批尚未形成可验证记录 | COS/CDN、不可变 URL、域名审批、分包策略和包体预算在同一资源交付工作包内关闭 |
| 一级页面一致性 | 四个 root route 已共享 `PageFrame` 与 `ProductTabBar` owner，最终头部与底栏尺寸调整后需要同一真机窗口复核 | 四个一级页面在相同 viewport 下通过安全区、头部、正文起点和 TabBar 对比 |
| 页面状态稳定性 | ready 主路径已有实现，loading、empty、error、stale 的完整几何证据仍不齐 | 每路由至少覆盖合同要求的可达状态，确认状态切换不改变共享 chrome 和关键布局 |
| 核心交互 | 装备选择已改为本地草稿先落地、选择面板先关闭，再异步校验；其余路由仍需按合同完成一个核心交互 | 微信运行态记录动作、预期、实际与结果 |
| 业务事实边界 | Taro 通过 typed API 消费 resolver、community import 和 stat snapshot；装备主属性、兼容性与徽标由后端拥有 | 架构审计持续阻断前端重建职业/装备规则，前端只负责展示映射 |
| 产品命名 | roadmap 定义“智能分析”，当前运行导航仍使用“队长” | 产品决策后一次同步导航、标题、README 与 route 合同 |

上述条目是当前长期缺口，不记录某次执行过程。临时截图、一次性脚本和旧计划不进入仓库；Git 历史承担追溯职责。

## 当前工作包

- 主干接合：Taro typed API 对齐 resolver、community import 与 stat snapshot；后端只读审计，改动边界保持在前端。
- UI 治理：先修共享 chrome、TabBar、medallion 与素材 fit，再处理 route composition。
- 当前批次：builds，优先 `builds_home` 和 `gear_detail` 的尺度、图标裁切与装备选择交互。

## 完成标准

14 个路由均满足：微信可编译；安全区、头部、正文、TabBar 和固定输入区互不覆盖；目标结构、材质、图标层级与信息密度成立；ready/loading/empty/error 几何稳定；核心交互可用；真实数据与可信边界不变。
