# WOW Mini Program Roadmap

Active frontend ownership is explicit: `apps/mini-taro` owns the active 14-route runtime and `packages/api-client/src` owns typed transport. The root `app.json` and `pages/` tree remain compatibility consumers only, preserving the 14-route surface without receiving new first-level ownership. The machine-readable route matrix is `docs/project-owner-map.json`.

状态：`active`
更新时间：`2026-07-19`

## 本文职责

本文件只回答三个问题：产品要解决什么、当前主线是什么、下一阶段按什么顺序推进。

执行步骤只进入 `docs/plans/README.md` 白名单；设计事实只进入 `DESIGN.md` 与 `docs/design/current-ui/`；接口、运行和部署细节留在稳定架构或 runbook。历史过程、否定式约定、截图账本和阶段证据由 Git 与 release packet 保存。

## 产品方向

面向 WoW 玩家构建一体化分析工作台，把资讯、职业构筑、装备、SimC、任务结果和证据受限的 AI 建议连接成一条可复用路径：

`理解版本 -> 选择构筑 -> 保存模板 -> 执行模拟 -> 解释结果 -> 继续优化`

产品以四个一级入口组织：资讯、职业专精、智能分析、我的。PVE、WCL 和 WebSim 历史能力保留，但在真实数据源、用户价值和发布门禁明确前不恢复为一级入口。

## 当前能力边界

| 能力 | 当前判断 | 下一步边界 |
| --- | --- | --- |
| 资讯 | 已有首页、列表、中文详情、来源与发布状态 | 保持来源、翻译和内容状态可追踪 |
| 职业构筑 | canonical resolver、release train、社区模板原子导入、异步属性快照和 Taro typed API 接合已完成 | 在真实微信候选中验证构筑主路径；不能引入第二套本地装备事实 |
| SimC 与任务 | 已有确定性转换、执行、任务保存和结构化报告基础 | 输入可执行、数字有证据、失败可解释 |
| 炸鸡队长 | 已有证据受限对话和确定性降级 | 通用建议与本地证据严格分层 |
| 个人模板 | 已有微信账号、天赋/装备模板汇总与同步基础 | 数据保持 owner 隔离，再扩展收藏、角色和订阅 |
| 数据与发布 | PostgreSQL-only、read-model selector、Harness、验证矩阵、Taro/兼容 owner、CI 与 caller-proof 淘汰合同已建立 | 按 compatibility retirement 合同逐项证明无调用方后再淘汰兼容面 |
| PVE / WCL | 历史实现保留，当前不是首版主入口 | 授权数据、样本窗口、可信状态和恢复验收同时明确后再启用 |

## 当前优先级

| 优先级 | 里程碑 | 完成标准 | 权威入口 |
| --- | --- | --- | --- |
| 已完成 | 主干架构接合 | Taro 已接入 resolver、community import、stat snapshot；Harness 已把 Taro 定义为活动 UI owner，旧 `pages/` 只保留兼容职责 | [装备 runbook](gear-simulation-full-chain-runbook.md)、[owner map](project-owner-map.json)、[验证矩阵](verification-matrix.md) |
| P0 | 14 路由 UI 系统重建 | 共享 chrome、控件和素材槽先在微信三基线成立，再按固定批次传播；14 路由各完成一次真实运行态复核和核心交互验证 | [DESIGN.md](../DESIGN.md)、[current-ui](design/current-ui/README.md)、[当前计划](plans/ui-reconstruction.md) |
| 已完成 | 文档控制面收敛 | roadmap 无执行流水；plans 只有活动入口；Harness 状态、稳定合同和 release evidence 各有唯一 owner | 本文件、[plans/README.md](plans/README.md)、[project-state.json](project-state.json) |
| 已完成 | Harness v0.6.2 证据绑定 | PR #93 已让 CI 绑定任务自己的 requirement/evidence/manifest；runtime、verification 与 closure identity 分离，人工验收和 `not_run_user_waived` 进入可校验矩阵，且没有增加重复 full、额外评审或运行时改动 | [Harness](harness.md)、[验证矩阵](verification-matrix.md)、[归档证据](../artifacts/releases/2026-07-19-harness-v0-6-2-control-plane-cleanup/evidence.json) |
| 已完成 | Harness v0.6.3 当前事实与 DX 收口 | 当前事实顺序、Taro 开发入口、活动文档可达性、本地假失败和 CLI fail-fast 规则保持一致；不增加新流程或重复验证 | [Harness](harness.md)、[文档地图](README.md)、[release packet](../artifacts/releases/2026-07-20-harness-v0-6-3-docs-dx/evidence.json) |
| P1 | 构筑到模拟闭环稳定 | 天赋/装备模板可确定性加载、转换、校验、提交和复盘；不可执行状态 fail closed | [builds-architecture.md](builds-architecture.md)、[simulator-simc-end-to-end.md](simulator-simc-end-to-end.md) |
| P1 | 证据化报告 | 玩家可见数字来自 runner、日志或明确参考源；模型只负责解释 | `server/simulator_payload.py` |
| P1 | 发布与可观测 | 核心 API、刷新任务、SimC 和数据健康有可重复 smoke、超时与故障定位 | [remote-debugging.md](remote-debugging.md)、[verification-matrix.md](verification-matrix.md) |
| P2 | 个人化工作台 | 角色、收藏、模板和任务历史围绕微信账号 owner 组织 | `apps/mini-taro/src/pages/profile/`、`server/news_backend.py` |
| P2 | PVE / WCL 恢复决策 | 明确数据授权、样本窗口、入口价值和失败边界 | `pages/pve/`、`pages/simulator/wcl.*` |
| 待决策 | 产品命名与首页权重 | 确定一句对外定位和第一主线，并同步 README 与导航文案 | [ideas.md](roadmap/ideas.md) |

## UI 交付路径

1. 用 canonical target 固化全量目标与设计语言；目标图决定可见结构和几何，真实 API/domain 决定内容与行为。
2. 从全量目标提取共享 owner 合同，由 `audit:ui-architecture` 阻断 route-private chrome、安全区和原生控件回流。
3. 在真实微信运行态验证 `news_home`、`simulator_home`、`news_detail`；结构预检后再做 target/runtime 像素复核。
4. 三基线成立后，按 news、builds、simulation/profile 固定批次传播。
5. 每个路由只做一次最终视觉复核和一个核心交互验证；单元测试不授予视觉通过。

## 维护规则

- roadmap 控制在 150 行以内，只保留方向、优先级、能力边界和完成标准。
- 当前执行计划只允许出现在计划白名单；被替代后删除，Git 即历史。
- 稳定事实写肯定式合同；临时踩坑和否定式过程不进入长期控制面。
- 证据只指向当前存在且有 owner 的文件，不链接已删除计划或一次性截图目录。
- 新想法先进入 [ideas.md](roadmap/ideas.md)，确认优先级后再进入里程碑。
