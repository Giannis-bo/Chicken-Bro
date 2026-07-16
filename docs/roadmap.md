# WOW Mini Program Roadmap

状态：`active`
更新时间：`2026-07-17`

## 本文职责

本文件只回答三个问题：产品要解决什么、当前主线是什么、下一阶段按什么顺序推进。

执行步骤只进入 `docs/plans/README.md` 白名单中的当前计划；设计事实只进入 `DESIGN.md` 与 `docs/design/current-ui/`；接口、运行和部署细节留在各自稳定文档。历史执行过程、尝试、否定式约定、截图账本和阶段性证据由 Git 保存，不在 roadmap 重复归档。

## 产品方向

面向 WoW 玩家构建一体化分析工作台，把资讯、职业构筑、装备、SimC、任务结果和证据受限的 AI 建议连接成一条可复用路径：

`理解版本 -> 选择构筑 -> 保存模板 -> 执行模拟 -> 解释结果 -> 继续优化`

产品对外暂以四个一级入口组织：资讯、职业专精、智能分析、我的。PVE、WCL 和 WebSim 的历史能力保留，但在真实数据源、用户价值和发布门禁明确前不恢复为一级入口。

## 当前能力边界

| 能力 | 当前判断 | 下一步边界 |
| --- | --- | --- |
| 资讯 | 已有首页、列表、中文详情、来源与发布状态 | 保持来源、翻译和内容状态可追踪；不以 UI 重建改写内容事实 |
| 职业构筑 | 已有职业/专精入口、天赋模拟、16 槽装备、模板保存 | 收敛共享交互和组件，不继续以页面补丁修复相同问题 |
| SimC 与任务 | 已有固定输入、确定性转换、执行、任务保存和结构化报告基础 | 继续保证输入可执行、数字有证据、失败可解释 |
| 炸鸡队长 | 已有证据受限对话和确定性降级 | 通用建议与本地证据严格分层，不编造排名、日志或数值 |
| 个人模板 | 已有微信账号、天赋/装备模板汇总与同步基础 | 所有个人数据保持 owner 隔离，再扩展收藏、角色和订阅 |
| 数据与部署 | 已有统一后端、SQLite、部署与健康检查基础 | 优先补迁移、可观测和发布 smoke，不在 UI 周期混入大规模后端重构 |
| PVE / WCL | 历史实现保留，当前不是首版主入口 | 只有授权数据、样本窗口、可信状态和恢复验收同时明确后再启用 |

## 当前优先级

| 优先级 | 里程碑 | 完成标准 | 权威入口 |
| --- | --- | --- | --- |
| P0 | 14 路由 UI 系统重建 | 共享 chrome、控件和素材槽先在微信三基线成立，再按固定批次传播；14 路由各自完成一次最终真实运行态复核和核心交互验证 | [DESIGN.md](../DESIGN.md)、[current-ui](design/current-ui/README.md)、[当前执行计划](plans/2026-07-14-target-first-14-route-rebuild.md) |
| P0 | 文档控制面收敛 | roadmap 不含执行流水；plans 只有一个活动入口；设计事实、执行计划和最终证据各有唯一 owner；仓库内不再引用已删除的 UI 计划 | 本文件、[plans/README.md](plans/README.md) |
| P1 | 构筑到模拟闭环稳定 | 天赋/装备模板可确定性加载、转换、校验、提交和复盘；不可执行状态 fail closed | [builds-architecture.md](builds-architecture.md)、[simulator-simc-end-to-end.md](simulator-simc-end-to-end.md) |
| P1 | 证据化报告 | 玩家可见数字来自 runner、日志或明确参考源；模型只负责解释；缺证据时输出确定性降级 | `server/simulator_payload.py`、`tests/news_backend_test.py` |
| P1 | 发布与可观测 | 核心 API、刷新任务、SimC 执行和数据健康有可重复 smoke、超时和故障定位路径 | [remote-debugging.md](remote-debugging.md)、`server/` |
| P2 | 个人化工作台 | 角色、收藏、模板和任务历史围绕微信账号 owner 组织，跨账号不可访问 | `pages/profile/`、`server/news_backend.py` |
| P2 | PVE / WCL 恢复决策 | 明确数据授权、样本窗口、入口价值和失败边界后，决定恢复或继续 dormant | `pages/pve/`、`pages/simulator/wcl.*` |
| 待决策 | 产品命名与首页权重 | 确定一句对外定位和第一主线，并同步 README 与导航文案 | [ideas.md](roadmap/ideas.md) |

## UI 交付路径

UI 主线不再按页面逐个修补，而按以下不可倒置的顺序推进：

1. 用 canonical target 固化全量目标与设计语言；目标图决定可见结构和几何，真实 API/domain 决定内容与行为。
2. 从全量目标提取共享 owner 合同，并由 `audit:ui-architecture` 阻断 route-private chrome、安全区和原生控件回流。
3. 在真实微信运行态同时验证 `news_home`、`simulator_home`、`news_detail`；结构几何预检通过后再做 target/runtime 像素复核。
4. 三基线成立后，按 news、builds、simulation/profile 三个固定批次传播。
5. 每个路由只做一次最终 target/runtime 视觉复核和一个核心交互验证；单元测试只证明逻辑，不授予视觉通过。

详细合同由 [DESIGN.md](../DESIGN.md) 和 [current-ui/README.md](design/current-ui/README.md) 维护，执行步骤只由 [当前计划](plans/2026-07-14-target-first-14-route-rebuild.md) 维护。

## 维护规则

- roadmap 只保留方向、优先级、能力边界和完成标准；建议控制在 150 行以内。
- 当前执行计划只允许出现在 `docs/plans/README.md` 白名单；被替代后删除，Git 即历史。
- 稳定事实写肯定式合同；临时禁令、踩坑记录和“不要再做什么”只在仍能阻断当前错误时保留。
- 证据链接只指向当前存在且仍有 owner 的文件；不链接已删除计划或一次性截图目录。
- 完成一项工作只更新状态、完成标准和稳定入口，不追加按日期排列的执行日志。
- 新想法先进入 [ideas.md](roadmap/ideas.md)，确认优先级后再进入里程碑。
