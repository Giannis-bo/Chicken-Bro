# WOW Mini Program Roadmap

> 这份文档是项目的长期推进控制台：先统一目标，再拆行动，再把讨论中的想法持续收敛到可执行路线中。

## 项目愿景

面向 WoW 玩家，构建一套一体化辅助工具：用可信数据追踪资讯、职业构筑、PVE 内容与赛季变化，并通过 WebSim、SimC 和 AI 分析把“看数据”推进到“做决策”。

第一阶段的核心判断是：项目不只是一个资讯小程序，而是一个围绕玩家构筑、战斗表现和版本变化的分析工作台。资讯、职业专精、PVE 数据和模拟器都应服务于同一个目标：帮助玩家更快理解当前版本、选择构筑、验证收益并复盘问题。

## 当前产品能力

| 能力 | 当前状态 | 说明 | 关联文档 / 区域 |
| --- | --- | --- | --- |
| 资讯追踪 | 已完成基础版 | 后端提供新闻首页、列表、详情、刷新任务和来源记录。 | [news-architecture.md](news-architecture.md), `pages/news/`, `server/news_backend.py` |
| 职业专精 | 已完成基础版 | 职业、专精、天赋、装备、属性权重和循环的结构化展示已建立。 | [builds-architecture.md](builds-architecture.md), `pages/builds/` |
| PVE 专区 | 已完成基础版 | 当前赛季大秘境、团队 raid、boss 攻略入口和分析窗口已接入统一后端。 | `pages/pve/`, `server/news_backend.py` |
| 智能分析 / SimC | 正在深化 | 已有 SimCraft agent、任务保存、真实执行、阶段输出和防误导策略。 | [simulator-simc-end-to-end.md](simulator-simc-end-to-end.md), [2026-06-11-simc-flow-risk-avoidance.md](plans/2026-06-11-simc-flow-risk-avoidance.md) |
| WebSim 工作台 | 正在推进 | 已开始把天赋、装备候选、SimC-ready 校验和 WebSim profile 生成连成闭环。 | `websim/`, `server/websim_payload.py` |
| 后端与部署 | 已完成基础版 | 统一 Python 后端、SQLite、Lighthouse 部署脚本、systemd 服务和同步任务已建立。 | [remote-debugging.md](remote-debugging.md), [2026-06-09-unified-backend-cloud-deploy.md](plans/2026-06-09-unified-backend-cloud-deploy.md) |
| 个人化工作台 | 规划中 | README 已预留“我的”tab，WebSim 也已有角色载入占位，后续需要角色绑定、收藏、订阅和数据源设置。 | `pages/profile/`, `websim/app.js` |

## 路线主题

| 主题 | 方向 |
| --- | --- |
| 数据可信与新鲜度 | 所有玩家可见结论都应带来源、时间窗口、验证状态和 fallback 边界；赛季未验证时宁可阻断，也不展示可能过期数据。 |
| 构筑到模拟闭环 | 职业专精、WebSim、SimC 和任务详情要形成一条链：选择构筑、补齐可执行输入、提交模拟、保存和复盘结果。 |
| 证据化 AI 报告 | LLM 只做解释和表达，数字事实必须来自 SimC runner、日志解析或可信参考源；未来报告应逐步 schema 化。 |
| 个人化角色体验 | 从通用查询推进到角色档案、收藏专精、订阅提醒、任务历史和个人数据源配置。 |
| 运维与可观测 | 正式域名、HTTPS、合法域名、刷新记录、health check、smoke 和部署状态要成为稳定发布链路的一部分。 |

## 里程碑

| 状态 | 里程碑 | 目标 | 用户价值 | 关键动作 | 完成标准 | 关联 |
| --- | --- | --- | --- | --- | --- | --- |
| 已完成 | 统一后端与云部署 | 用一个轻量后端承载新闻、职业、PVE、模拟器和 AI 分析。 | 小程序不再依赖纯本地 payload，后续能力可以稳定接入服务端。 | 建立统一 API；接入 SQLite；部署到 Lighthouse；补齐服务文档。 | `/health` 与核心 API 可用；部署脚本和远程调试文档存在；相关测试通过。 | [统一后端计划](plans/2026-06-09-unified-backend-cloud-deploy.md) |
| 已完成 | 职业专精基础体验 | 将原 BD tab 重构为职业专精查询入口。 | 玩家能从职业/专精维度查看天赋、装备、属性和循环。 | 重构 tab；建立职业专精数据契约；新增详情页和架构文档。 | 入口与详情页可用；职业专精覆盖完整；文档记录数据源和扩展方式。 | [职业专精计划](plans/2026-06-09-specializations-tab.md) |
| 已完成 | SimC 风险边界收敛 | 防止空 profile、模板 profile 和 LLM 误导性 DPS 输出。 | 玩家不会把模板、空输入或模型猜测误认为真实模拟结论。 | 区分 explicit / prompt / generated；限制真实执行；补齐阶段输出和防护文档。 | SimC 执行前校验清晰；generated 只作为预览；文档列出已知风险和规避原则。 | [SimC 风险规避](plans/2026-06-11-simc-flow-risk-avoidance.md) |
| 正在推进 | WebSim 到 SimC 的可提交闭环 | 让 WebSim 选择的天赋和装备能安全生成 SimC profile 并提交模拟。 | 玩家可以从可视化构筑直接进入可信模拟，而不是手动拼 profile。 | 天赋节点编码；装备 SimC-ready 校验；候选装备提示；阻断不可提交状态。 | 有天赋编码结果、装备 readiness、阻断原因和成功执行测试；候选装备不会误写入 SimC。 | `websim/`, `server/websim_payload.py`, `tests/websim_payload_test.py` |
| 下一步 | Roadmap 与想法池常态化 | 把项目目标、已完成动作、下一步和讨论想法放到同一套文档体系。 | 后续迭代有稳定上下文，减少反复解释和方向漂移。 | 维护本文件；新增想法池；定期把完成项和新想法同步进 roadmap。 | `docs/roadmap.md` 能回答目标、现状和下一步；`docs/roadmap/ideas.md` 能收纳待确认想法。 | [ideas.md](roadmap/ideas.md) |
| 下一步 | 数据可信度与赛季同步完善 | 明确哪些数据来自官方、SimC、Wago、日志站或本地 fallback。 | 玩家能知道数据是否新鲜、可信，避免看到过期赛季内容。 | 完善同步状态；暴露数据来源；区分 verified / blocked / fallback。 | 关键页面展示数据状态；过期或未验证数据不会伪装成当前赛季。 | `server/websim_payload.py`, `server/news_backend.py` |
| 下一步 | SimC 输入契约产品化 | 把可执行 `/simc`、confirm-only、submit、gear readiness 和 profileSource 规则固化成用户可理解的流程。 | 玩家知道什么时候只是预览、什么时候可以真实模拟，以及缺哪些输入。 | 强化 `/simc` 导入；确认与提交复用 payload；规范 SimC slot；区分展示 gear 与可执行 gear。 | 任意模拟提交前都能说明输入来源、是否可执行、缺失字段和是否保存任务。 | [simulator-simc-end-to-end.md](simulator-simc-end-to-end.md), [ideas.md](roadmap/ideas.md) |
| 下一步 | 正式发布与刷新可观测 | 补齐 HTTPS、微信合法域名、443、刷新 run 管理和 health check。 | 体验版/正式版能稳定访问，刷新失败和环境问题可被定位。 | 配置正式域名；限制手动刷新；记录刷新错误；拆分网络、SimC、LLM、参考数据探测。 | 正式环境不依赖 HTTP IP；刷新记录可查；部署后 smoke 有明确步骤。 | [news-architecture.md](news-architecture.md), [remote-debugging.md](remote-debugging.md) |
| 后续 | 职业 / PVE 数据采集自动化 | 将当前结构化 payload 逐步替换为定时采集、校验和数据库化数据。 | 构筑、PVE 和资讯能跟随版本、热修、赛季和日志样本更新。 | 接入 Raider.IO、Warcraft Logs、Archon、Subcreation 等可信源；保留样本窗口和低样本状态。 | 人工种子不再承担“最新结论”；每条结论都有来源和分析窗口。 | [builds-architecture.md](builds-architecture.md), `server/pve/` |
| 后续 | 角色绑定与个人化工作台 | 从通用查询推进到玩家自己的角色、收藏、订阅和任务记录。 | 玩家能围绕自己的角色持续分析，而不是每次从零开始。 | 设计角色资料、订阅、收藏、历史任务和权限边界。 | 角色数据模型和隐私边界明确；至少一个个人化场景可用。 | `pages/profile/`, `simulator_tasks` |
| 后续 | WCL / 日志复盘链路 | 将战斗日志分析纳入 SimC 与 AI 报告链路。 | 玩家能把“理论收益”和“实战问题”放在同一份报告里看。 | 定义日志输入；抽取关键战斗证据；连接 SimC 差距解释。 | 能从日志生成可解释问题列表，并和 SimC / 参考数据分清来源。 | `pages/simulator/`, `server/simulator_payload.py` |
| 后续 | LLM 报告 schema 化 | 从自由文本 prompt/report 逐步转为 evidence JSON、允许数字列表和结构化输出。 | AI 报告更稳定，不会编造或误读数字。 | 定义 report schema；校验 allowedNumbers；不合格时回退 deterministic recommendations。 | LLM 输出每个数字都有后端证据；失败时仍有可读报告。 | [SimC 风险规避](plans/2026-06-11-simc-flow-risk-avoidance.md) |
| 暂缓 | 深度 Codex Agent 工作流 | 将 Codex worker 用于低频复杂任务，如 profile 修复和跨文件证据复核。 | 复杂问题可由 agent 深挖，但不会拖慢高频普通分析。 | 保持普通 LLM、SimC runner、Codex worker 职责分离。 | 有明确触发条件、任务隔离、超时和结果展示后再扩大使用。 | [SimC 风险规避](plans/2026-06-11-simc-flow-risk-avoidance.md) |
| 待决策 | 产品定位命名 | 明确项目对外是“资讯小程序”“构筑模拟器”还是“玩家分析工作台”。 | 对外表达更清晰，后续 UI、文案和优先级更统一。 | 补录本地讨论想法；确定核心用户和主场景。 | Roadmap 中有一句稳定的产品定位，并同步到 README。 | [ideas.md](roadmap/ideas.md) |
| 待决策 | 首页与 tab 权重 | 明确资讯、职业专精、PVE、WebSim/SimC、我的五条线的主次关系。 | 后续产品体验不会每条线平均用力，而是围绕主场景组织。 | 结合用户场景决定首页入口、默认工作流和导航文案。 | Roadmap 中确定“第一主线”和“辅助能力”。 | [ideas.md](roadmap/ideas.md) |

## 维护规则

- 本文件只维护长期方向、阶段状态和高层动作；具体执行步骤继续放在 `docs/plans/`。
- 新想法先进入 [roadmap/ideas.md](roadmap/ideas.md)，不要直接塞进里程碑。
- 当一个想法被采纳，移动到本文件的相应里程碑，并补上完成标准。
- 当一项工作完成，只更新状态和证据链接；不要改写历史计划文档。
- 无法从仓库或当前对话确认的历史想法，统一标记为“待补录”或“待确认”。
- 每次讨论后，如果用户明确说“OK”“认可”“就按这个”或等价确认，Codex 应主动把该想法纳入 [roadmap/ideas.md](roadmap/ideas.md) 或本文件；如果当轮不适合直接编辑，应明确提醒用户是否纳入 roadmap。
