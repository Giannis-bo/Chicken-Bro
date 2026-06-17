# WOW Mini Program Roadmap

> 这份文档是项目的长期推进控制台：先统一目标，再拆行动，再把讨论中的想法持续收敛到可执行路线中。

## 项目愿景

面向 WoW 玩家，构建一套一体化辅助工具：用可信数据追踪资讯、职业构筑、PVE 内容与赛季变化，并通过 WebSim、SimC 和 AI 分析把“看数据”推进到“做决策”。

第一阶段的核心判断是：项目不只是一个资讯小程序，而是一个围绕玩家构筑、战斗表现和版本变化的分析工作台。资讯、职业专精、PVE 数据和模拟器都应服务于同一个目标：帮助玩家更快理解当前版本、选择构筑、验证收益并复盘问题。

## 当前产品能力

| 能力 | 当前状态 | 说明 | 关联文档 / 区域 |
| --- | --- | --- | --- |
| 资讯追踪 | 已完成基础版 | 后端提供新闻首页、列表、详情、刷新任务和来源记录。 | [news-architecture.md](news-architecture.md), `pages/news/`, `server/news_backend.py` |
| 职业专精 | 已完成基础版 | 职业、专精、装备、属性权重和循环的结构化展示已建立；天赋构筑已接入小程序原生 WebSim 天赋模拟器，可从职业专精入口和热门专精卡片进入。 | [builds-architecture.md](builds-architecture.md), `pages/builds/` |
| PVE 专区 | 已完成基础版 | 当前赛季大秘境、团队 raid、boss 攻略入口和分析窗口已接入统一后端。 | `pages/pve/`, `server/news_backend.py` |
| 智能分析 / SimC | 已完成 | SimC 输入框架已阶段性完成：已有 SimCraft agent、confirm-only、任务保存、真实执行、阶段输出和防误导策略，并能保留 WebSim 天赋节点、导出码和 SimC talent lines。 | [simulator-simc-end-to-end.md](simulator-simc-end-to-end.md), [2026-06-11-simc-flow-risk-avoidance.md](plans/2026-06-11-simc-flow-risk-avoidance.md) |
| WebSim 工作台 | 已完成 | 已把天赋编码、完整核心装备 SimC-ready 校验、canonical WebSim profile、任务保存、真实 SimC 执行、装备中文名/图标和掉落查询体验连成基础闭环。 | `websim/`, `server/websim_payload.py` |
| 后端与部署 | 已完成基础版 | 统一 Python 后端、SQLite、Lighthouse 部署脚本、systemd 服务和同步任务已建立。 | [remote-debugging.md](remote-debugging.md), [2026-06-09-unified-backend-cloud-deploy.md](plans/2026-06-09-unified-backend-cloud-deploy.md) |
| 个人化工作台 | 规划中 | README 已预留“我的”tab，WebSim 也已有角色载入占位，后续需要角色绑定、构筑模板库、收藏、订阅和数据源设置。 | `pages/profile/`, `websim/app.js` |

## 路线主题

| 主题 | 方向 |
| --- | --- |
| 数据可信与新鲜度 | 所有玩家可见结论都应带来源、时间窗口、验证状态和 fallback 边界；赛季未验证时宁可阻断，也不展示可能过期数据。 |
| 构筑到模拟闭环 | 职业专精、WebSim、SimC 和任务详情要形成一条链：选择构筑、保存/加载模板、补齐可执行输入、提交模拟、保存和复盘结果。 |
| 证据化 AI 报告 | LLM 只做解释和表达，数字事实必须来自 SimC runner、日志解析或可信参考源；未来报告应逐步 schema 化。 |
| 个人化角色体验 | 从通用查询推进到角色档案、收藏专精、订阅提醒、任务历史和个人数据源配置。 |
| 运维与可观测 | 正式域名、HTTPS、合法域名、刷新记录、SimC / 游戏数据 / 模板健康检测、smoke 和部署状态要成为稳定发布链路的一部分。 |

## 里程碑

| 状态 | 里程碑 | 目标 | 用户价值 | 关键动作 | 完成标准 | 关联 |
| --- | --- | --- | --- | --- | --- | --- |
| 已完成 | 统一后端与云部署 | 用一个轻量后端承载新闻、职业、PVE、模拟器和 AI 分析。 | 小程序不再依赖纯本地 payload，后续能力可以稳定接入服务端。 | 建立统一 API；接入 SQLite；部署到 Lighthouse；补齐服务文档。 | `/health` 与核心 API 可用；部署脚本和远程调试文档存在；相关测试通过。 | [统一后端计划](plans/2026-06-09-unified-backend-cloud-deploy.md) |
| 已完成 | 职业专精基础体验 | 将原 BD tab 重构为职业专精查询入口。 | 玩家能从职业/专精维度查看天赋、装备、属性和循环。 | 重构 tab；建立职业专精数据契约；新增详情页和架构文档。 | 入口与详情页可用；职业专精覆盖完整；文档记录数据源和扩展方式。 | [职业专精计划](plans/2026-06-09-specializations-tab.md) |
| 已完成 | SimC 风险边界收敛 | 防止空 profile、模板 profile 和 LLM 误导性 DPS 输出。 | 玩家不会把模板、空输入或模型猜测误认为真实模拟结论。 | 区分 explicit / prompt / generated；限制真实执行；补齐阶段输出和防护文档。 | SimC 执行前校验清晰；generated 只作为预览；文档列出已知风险和规避原则。 | [SimC 风险规避](plans/2026-06-11-simc-flow-risk-avoidance.md) |
| 已完成 | WebSim 到 SimC 的可提交闭环 | 让 WebSim 选择的天赋和装备能安全生成 SimC profile 并提交模拟。 | 玩家可以从可视化构筑直接进入可信模拟，而不是手动拼 profile。 | 天赋节点编码；完整核心装备 SimC-ready 校验；canonical WebSim profile；候选装备提示；阻断不可提交状态。 | 预览、提交、保存任务和 SimC 执行复用同一份 profile；核心装备栏位完整；有天赋编码结果、装备 readiness、阻断原因、成功执行测试和 benchmark 状态；候选装备不会误写入 SimC；无外部参考窗口时明确标为 unverified。 | `websim/`, `server/websim_payload.py`, `tests/websim_payload_test.py`, `tests/news_backend_test.py`, [SimC 端到端](simulator-simc-end-to-end.md) |
| 已完成 | 小程序原生天赋模拟器 | 将 WebSim 天赋树移植到职业专精 tab 的“天赋构筑”入口。 | 玩家可以在小程序内直接点选职业、专精和英雄天赋，并把编码后的构筑带入 SimC 确认流程。 | 新增天赋模拟器页；接入 WebSim bootstrap/talents/profile；暴露职业/专精 WebSim key；实现点数、前置、choice、搜索、导入导出、移动端分树标签展示和 SimC 上下文保留。 | `pages/builds/talent-simulator` 可从天赋构筑和热门专精进入；移动端以通用/英雄/专精标签切换单树渲染；payload 暴露 WebSim class/spec key；SimC build context 保留 selectedNodes、websimExportCode、hero/scenario、encodingStatus 和 simcLines；无完整装备时仍要求补装备；相关前后端契约测试覆盖。 | `app.json`, `pages/builds/talent-simulator.*`, `pages/builds/talent-simulator-core.js`, `pages/builds/websim-api.js`, `server/builds/home-payload.js`, `server/simulator_payload.py`, `tests/talent-simulator-core.test.js`, `tests/builds-page.test.js`, `tests/frontend-api-client.test.js`, `tests/news_backend_test.py`, `tests/simulator-page.test.js` |
| 已完成 | SimC 输入契约产品化 | 把可执行 `/simc`、WebSim profile、confirm-only、submit、gear readiness、profileSource 和外部 benchmark 规则固化成用户可理解的流程。 | 玩家知道什么时候只是预览、什么时候可以真实模拟、缺哪些输入，以及模拟结果是否落在外部数据的合理区间。 | 强化 `/simc` 导入；确认与提交复用 payload；规范 SimC slot；区分展示 gear 与可执行 gear；标注 reasonable / outlier / unverified；补齐更多场景的外部参考窗口。 | 任意模拟提交前都能说明输入来源、是否可执行、缺失字段、是否保存任务和横向合理性状态；外部数据缺席时不得把 DPS 称为已横向验证。 | `websim/app.js`, `server/news_backend.py`, `server/websim_payload.py`, `tests/websim-page.test.js`, `tests/websim_payload_test.py`, [simulator-simc-end-to-end.md](simulator-simc-end-to-end.md) |
| 已完成 | 装备元数据与查询体验补全 | 用官方物品数据补齐装备中文名、图标、来源状态和掉落查询默认视图。 | 玩家在装备模拟器、职业装备页和装备查询里看到真实中文装备与图标，不再被英文名、空白掉落或展示型参考误导。 | 接入 Battle.net Game Data API 缓存；补齐别名映射、官方英文名精确检索、复合装备行拆分；区分 verified item、source_reference 和 fallback；装备查询优先定位有掉落的首领。 | WebSim 装备候选、地下城掉落和职业装备页均显示中文名/图标；Archon/Wowhead 参考行标记为 source_reference；空掉落首领不会作为默认空白结果；相关测试和远端 smoke 通过。 | `server/websim_payload.py`, `server/builds/home-payload.js`, `server/news_backend.py`, `pages/builds/detail.*`, `websim/app.js`, `websim/app.css`, `tests/websim_payload_test.py`, `tests/builds-page.test.js`, `tests/websim-page.test.js` |
| 正在推进 | 模板化构筑与固定 SimC 输入 | 将天赋字符串、装备字符串和角色/职业选择沉淀为可保存、可加载、可验证的构筑模板，并把 SimC 入口从 LLM 对话引导转为固定表单。 | 玩家可以保存自己的天赋/装备模板，也能加载社区经典模板，后续快速组合并提交可信 SimC，不必每次从聊天或手动拼接开始。 | 已完成社区大秘模板 v1：独立社区模板模型、manual fixture 同步、Raider.IO / Warcraft Logs adapter 骨架、缺凭据状态、天赋模拟器社区模板 sheet、WebSim 可视化应用和 SimC-only 外部导入码上下文保留；正在补全全职业天赋规则权威层，统一前端可选性、后端编码校验和 SimC handoff。 | 模板记录包含类型、职业/专精/英雄天赋、场景、版本、来源、raw string、解析状态和验证状态；天赋规则包含 parentMode、choice、默认赠送点、购买点数、门槛、schemaRevision 和确定性阻断原因；SimC 提交不依赖对话补槽；缺少角色、天赋或装备时有确定性阻断原因；社区模板标注来源和适用赛季；保存模板能进入后续快速导入。 | `server/websim_payload.py`, `server/community_talent_sources/`, `pages/builds/talent-simulator.*`, `pages/builds/talent-simulator-core.js`, `pages/builds/websim-api.js`, `pages/simulator/simc.js`, `tests/websim_payload_test.py`, `tests/talent-simulator-core.test.js`, `tests/builds-page.test.js`, `tests/simulator-page.test.js`, [ideas.md](roadmap/ideas.md) |
| 下一步 | 职业专精内嵌装备模拟 | 将职业专精详情页里的“装备获取”模块升级为“装备模拟”，不新增独立小程序页。 | 玩家在当前职业/专精上下文里直接查看满级穿戴属性、替换各部位装备并理解是否可用于真实 SimC。 | 模块改名；新增装备摘要、满级属性快照、槽位网格/列表和槽位替换面板；后端返回 equippedSet、statSnapshot、slotReadiness 和 replacementCandidates；缺关键字段时展示确定性原因。 | 当前详情页可展示全职业专精装备模拟状态；每个槽位能查看和替换候选装备；只有 verified 属性快照才标为可信；partial/blocked 状态不会伪装成正确满级属性；移动端小屏无遮挡、不卡片嵌套、可继续带入 SimC。 | [内嵌装备模拟设计](plans/2026-06-17-builds-inline-gear-simulator-design.md), `pages/builds/detail.*`, `server/websim_payload.py`, `server/builds/home-payload.js`, `tests/builds-page.test.js`, `tests/websim_payload_test.py` |
| 下一步 | Roadmap 与想法池常态化 | 把项目目标、已完成动作、下一步和讨论想法放到同一套文档体系。 | 后续迭代有稳定上下文，减少反复解释和方向漂移。 | 维护本文件；新增想法池；定期把完成项和新想法同步进 roadmap。 | `docs/roadmap.md` 能回答目标、现状和下一步；`docs/roadmap/ideas.md` 能收纳待确认想法。 | [ideas.md](roadmap/ideas.md) |
| 正在推进 | 数据可信度与赛季同步完善 | 明确哪些数据来自官方、SimC、Wago、日志站或本地 fallback。 | 玩家能知道数据是否新鲜、可信，避免看到过期赛季内容。 | 已完成装备物品官方元数据和 source_reference 分层；天赋规则采用 SimC/Wago 可运行图，Blizzard Game Data API 真实对账在 API 凭据申请完成后再开启，当前保持 `not_configured` / `pending_official_audit`，差异后续进入健康哨兵而非静默通过；下一步继续完善赛季同步、刷新记录和更多外部数据源状态。 | 关键页面展示数据状态；过期或未验证数据不会伪装成当前赛季；官方/SimC/Wago 对账不一致时标记 blocked / stale / incompatible，并阻断真实 SimC 提交。 | `server/websim_payload.py`, `server/news_backend.py`, `docs/roadmap/ideas.md` |
| 后续 | 数据与模拟健康哨兵 | 把 SimC 程序版本、Battle.net 赛季/天赋/装备数据、社区模板和端到端 SimC 兼容性纳入统一巡检。 | 玩家和维护者能知道当前模拟结果是否建立在最新且兼容的数据面上，避免 SimC 版本、天赋树、装备字段或模板过期时继续给出可信结论。 | 复用现有 `wow-simc-version-check`；新增游戏数据 revision 检测；对核心职业/专精跑兼容性 smoke；模板在赛季或天赋树变更后重新解析；在 health/admin surface 展示 blocked / stale / verified / incompatible。 | 每次巡检记录 checkedAt、SimC local/latest commit、seasonRevision、talentSchemaRevision、itemMetadataRevision、templateRevision 和 compatibility status；不兼容或过期时阻断真实 SimC 提交并给出确定性原因。 | `server/deploy_lighthouse.sh`, `server/websim_payload.py`, `server/game-season.js`, `pages/simulator/simc.*`, `docs/roadmap/ideas.md` |
| 下一步 | 全职业天赋规则校验与追踪机制 | 为“全职业天赋规则权威层”建立持续验证、漂移追踪和失败归因机制。 | 玩家不会因为底层规则漂移遇到错误的不可选 / 可选状态；维护者能快速定位是缺树、缺边、缺 entry、点数门槛、choice 冲突还是官方对账差异。 | 建立 authority matrix runner 和规则回归样本库，固定冰法暴风雪、急咒师左链、多父 OR、choice 互斥、默认赠送点、降点裁剪等核心样本；记录 `talentSchemaRevision`、`simcBuild`、`traitEdgeSource`、`officialRevision`、`diffStatus`、`checkedAt`、失败节点和阻断原因；输出 CI / health / admin 可读报告；Blizzard API 凭据到位后再接入官方对账。 | 每次规则或数据更新都能跑全量 13 职业 / 40 专精 / 英雄树矩阵 smoke；失败项带 class/spec/hero/node/reason；任何缺树、缺边、缺 entry 或对账差异都不会被标为 verified；真实 SimC 提交复用同一阻断原因。 | `server/websim_payload.py`, `server/news_backend.py`, `tests/websim_payload_test.py`, `tests/talent-simulator-core.test.js`, `docs/roadmap/ideas.md` |
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
