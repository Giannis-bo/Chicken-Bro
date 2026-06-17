# Roadmap Ideas

> 这份文档用于收纳本地讨论、临时灵感和待确认方向。它不是承诺清单；只有被移动到 `docs/roadmap.md` 里程碑的内容，才进入正式推进路线。

## 使用方式

- 新想法先加到“待补录 / 待确认”或“候选想法”。
- 每条想法必须写清楚：想法、来源、解决的问题、潜在收益、风险/疑问、建议归属里程碑、状态。
- 来源如果来自口头或本地聊天，但当前无法核实，写“本地讨论，待补录证据”。
- 定期清理：采纳的移动到 roadmap，放弃的保留结论，重复的合并。
- 每次讨论后，如果用户明确确认某个方向 OK，Codex 应主动更新本文件或 `docs/roadmap.md`；如果暂不编辑，应提醒用户是否要纳入 roadmap。

## 状态定义

| 状态 | 含义 |
| --- | --- |
| 待补录 | 记得讨论过，但还缺具体上下文或证据。 |
| 待确认 | 方向清楚，但需要用户确认优先级或边界。 |
| 候选 | 可以进入后续排序，但暂未纳入正式里程碑。 |
| 已采纳 | 已进入 `docs/roadmap.md` 的某个里程碑。 |
| 已完成 | 已落地，并能链接到代码、文档或测试证据。 |
| 暂缓 | 有价值，但当前不适合推进。 |
| 放弃 | 明确不做，保留原因避免重复讨论。 |

## 待补录 / 待确认

| 想法 | 来源 | 解决的问题 | 潜在收益 | 风险 / 疑问 | 建议归属里程碑 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| 完整梳理本地讨论过的产品方向和功能灵感 | 本地讨论，待补录证据 | 很多想法散落在对话中，后续容易遗失或重复讨论。 | 形成统一上下文，让 roadmap 能持续继承讨论成果。 | 需要逐步补录，不能凭记忆伪造细节。 | Roadmap 与想法池常态化 | 待补录 |
| 明确项目对外定位和一句话表达 | 当前 roadmap 讨论 | README 和产品方向已有多条能力线，但对外主叙事仍需收束。 | 帮助后续决定首页、tab 权重、文案和优先级。 | 需要在“资讯工具”“构筑模拟器”“玩家分析工作台”之间取舍。 | 产品定位命名 | 待确认 |
| 资讯详情完整中文化与发布质检 | 当前对话，2026-06-17 用户确认并要求实现；2026-06-17 追加正式服资讯全文翻译与可信发布方案；2026-06-17 追加纠偏：正文必须是原文直译而非 LLM 改写；2026-06-17 远端验收通过 | 资讯详情只能看到一句话摘要，且原文面板和大块来源模块占据主要阅读空间；全文翻译如果缺少授权、官方校验和冲突隔离，也可能把第三方误传、未授权内容或 LLM 导读改写公开给玩家。 | 用完整中文正文块、原文标题、内容 tag、官方核验 badge 和底部来源按钮提升详情页阅读价值，同时用授权门禁、官方校验、raw/evidence 记录、`translationFidelity=source_translation` 和发布质检避免半成品或不可信内容进入前端。 | 首版自动全文优先覆盖 Blizzard 官方；Wowhead/Icy Veins 默认 reference-only，不公开全文翻译；LLM 失败、正文抓取失败、授权未通过、无官方依据、来源冲突、正文退化为摘要或改写导读时暂不发布，可能造成短期资讯数量更少；本地 fallback seed 也必须服从 source translation fidelity 门禁。 | 资讯详情完整中文化与发布质检 / 正式发布与刷新可观测 / 数据可信度与赛季同步完善 | 已完成 |
| 将 WebSim 作为构筑到模拟的主入口 | 当前代码演进、2026-06-14 阶段验收 | 玩家从天赋/装备选择到 SimC 模拟仍有手动拼接成本。 | 降低模拟门槛，让构筑验证更直观。 | 数据 freshness、天赋编码准确性、装备字段完整度和外部 benchmark 覆盖仍需继续产品化。 | WebSim 到 SimC 的可提交闭环 | 已完成 |
| 小程序原生 WebSim 天赋模拟器 | 当前代码演进，2026-06-15 本地变更 | 职业专精的“天赋构筑”如果只停留在详情展示，玩家仍需要跳转或手动整理天赋上下文。 | 在小程序内完成职业/专精/英雄天赋选择、导入导出和 SimC handoff，让构筑到模拟链路更短。 | WebSim 天赋数据、装备完整性和外部 benchmark 仍要继续维持可信状态；无完整装备时必须阻断真实提交。 | 小程序原生天赋模拟器 | 已完成 |
| 天赋/装备模拟器保存模板 | 当前对话，2026-06-15 用户框架想法；2026-06-17 本地模板库 v1 进展 | 天赋和装备模拟器当前更像一次性编辑状态，字符串如果不能保存，后续快速 SimC 仍要重复导入或重新选择。 | 将天赋字符串和装备字符串保存为个人模板，后续可一键带入 SimC，提高复用效率。 | 本地保存、去重、列表汇总和删除已开始落地；仍需补齐模板加载、账号/服务端同步、角色维度归档和固定 SimC 表单；展示型装备不能伪装成可执行装备。 | 模板化构筑与固定 SimC 输入 / 个人模板库 v1 | 已采纳 |
| 账号化 CRUD 数据边界 | 当前对话，2026-06-17 用户确认 | 小程序已接入微信账号体系，但后续模板、角色、收藏、订阅、任务等增删改查如果继续散在本地或游客态，会造成归属、同步和权限边界不清。 | 以微信账号作为统一 owner，让个人资产可同步、可迁移、可隔离，后续所有写操作都有明确用户归属。 | 需要处理本地模板迁移、游客预览、HTTPS/Bearer 安全、token 过期、跨账号隔离和服务端 owner 字段补齐；读接口可以保留公共/游客态，但写接口必须 fail closed。 | 账号化数据边界与 CRUD 权限 / 个人模板库 v1 / 角色绑定与个人化工作台 | 已采纳 |
| 数据库架构治理与迁移路线 | 当前对话，2026-06-17 用户确认 | 后端已经从新闻服务扩展到账号、SimC 任务、WebSim 缓存、analytics 和后续模板 CRUD；如果继续只靠分散的 `CREATE TABLE IF NOT EXISTS`，后续 owner、迁移、备份和拆库边界会变得不清楚。 | 在不贸然换数据库的前提下，先把 SQLite 单库治理成有 domain map、schema migration、foreign key、owner 规则、备份和拆库标准的架构。 | 不应为了“看起来专业”过早上 Postgres；当前更需要 migration/version、外键强制、用户表 owner、cache 可重建边界、analytics 归档边界和备份 runbook。 | 数据库架构治理与迁移路线 / 账号化数据边界与 CRUD 权限 | 已采纳 |
| SimC 从 LLM 对话引导转为固定输入流程 | 当前对话，2026-06-15 用户框架想法 | 聊天式补槽容易让用户不确定到底缺什么，也容易把 LLM 放在输入契约前面。 | 用职业/角色选择、天赋字符串导入、装备字符串导入和确定性校验替代对话引导，让 SimC 提交流程更稳定。 | LLM 仍可用于结果解释和日志复盘，但不能负责判断输入是否可执行；固定表单要兼容官方 `/simc` 完整 profile 和 WebSim 拆分输入。 | 模板化构筑与固定 SimC 输入 | 已采纳 |
| 天赋模拟器加载个人和社区经典模板 | 当前对话，2026-06-15 用户框架想法 | 新用户不知道如何从零点天赋，老用户也需要快速套用自己常用或社区大神构筑。 | 天赋模拟器能加载个人保存模板和社区经典模板，再按当前角色/场景微调后进入 SimC。 | 社区模板必须标注作者/来源、适用赛季、更新时间、职业/专精/英雄天赋和数据可信状态；需要处理过期版本和天赋树变更导致的不可导入。 | 模板化构筑与固定 SimC 输入 / 数据可信度与赛季同步完善 | 已采纳 |
| 社区大秘天赋模板 v1 | 当前对话，2026-06-16 用户确认并要求实现 | 社区高分玩家模板如果直接依赖外部 API，会在凭据未补齐时阻塞前端能力。 | 先落地独立社区模板模型、fixture/manual 同步、缺凭据状态、天赋模拟器社区模板 sheet、WebSim 可视化应用和 SimC-only 外部导入码上下文保留。 | Raider.IO Developer API 需要后续申请；Warcraft Logs API 需要 client_id/client_secret；Archon 未确认官方 API 前只作为产品参考，不默认抓页面。 | 模板化构筑与固定 SimC 输入 / 职业 / PVE 数据采集自动化 | 已完成 |
| 全职业天赋规则权威层 | 当前对话，2026-06-17 用户确认并要求实现 | 小程序天赋模拟器当前存在多父节点、层级门槛和依赖判断不一致的问题，局部 UI 补丁无法覆盖全职业专精。 | 用 canonical talent schema 和统一规则引擎覆盖 13 职业 / 40 专精 / 英雄树组合，让前端可选性、后端编码校验、导出和 SimC handoff 使用同一事实来源。 | SimC/Wago 作为可运行规则源；Blizzard Game Data API 真实对账等 API 凭据申请完成后再开启，当前保持 `not_configured` / `pending_official_audit`；任何差异都应进入健康哨兵，不得静默标为 verified；不得在未获批准时下载或写入网络数据。 | 模板化构筑与固定 SimC 输入 / 数据可信度与赛季同步完善 / 数据与模拟健康哨兵 | 已采纳 |
| 全职业天赋规则校验与追踪机制 | 当前对话，2026-06-17 用户追加要求 | 即使底层权威层建立，如果没有持续校验和追踪，后续 SimC/Wago/官方数据变更仍可能让节点依赖、choice、默认点或导出编码悄悄漂移。 | 建立 authority matrix、核心样本库、CI/health/admin 报告和失败归因，让每次规则或数据更新都能定位到 class/spec/hero/node/reason。 | Blizzard API 真实对账等凭据到位后再开启；当前先追踪本地 schema、SimC/Wago 可运行图、fallback/blocked 状态和核心样本；巡检不能把未对账数据标为 verified。 | 全职业天赋规则校验与追踪机制 / 数据与模拟健康哨兵 | 已采纳 |
| 职业专精内嵌装备模拟模块 | 当前对话，2026-06-17 用户确认 | 当前职业专精详情里的“装备获取”更偏来源清单，不能直接承担满级穿戴属性、部位替换和 SimC 可执行性判断。 | 在不新增小程序页面的前提下，把现有模块升级为装备模拟，让玩家在当前职业/专精上下文内完成查看属性、替换装备和理解可信状态。 | 属性正确性必须由后端权威层返回；缺 ilvl、bonus、宝石、附魔、制造属性等字段时只能展示 partial/blocked，不能伪装成 verified；UI 需要适配小程序小屏。 | 职业专精内嵌装备模拟 / 模板化构筑与固定 SimC 输入 / 数据可信度与赛季同步完善 | 已采纳 |
| 数据与模拟健康哨兵 | 当前对话，2026-06-15 用户确认 | 只知道后端 alive 或 SimC 有新 commit，不足以判断赛季、天赋、装备、模板和 SimC 是否彼此兼容。 | 形成统一巡检：SimC 版本、Battle.net 赛季/天赋/装备 revision、模板漂移和端到端 profile smoke 都有明确状态。 | 需要控制巡检成本；外部 API 失败时应区分网络错误、凭据错误、数据过期和真实不兼容；巡检结果不能替代真实模拟输出。 | 数据与模拟健康哨兵 / 正式发布与刷新可观测 | 已采纳 |
| 建立数据可信度分层 | 当前代码演进，待补录更多讨论 | 官方、SimC、Wago、日志站和 fallback 数据混用时，用户难判断可信程度。 | 避免展示过期或未经验证的赛季数据。 | 需要统一状态字段和页面表达，避免 UI 噪音。 | 数据可信度与赛季同步完善 | 候选 |
| 装备物品元数据中文化与图标补全 | 当前对话，2026-06-14 已实现 | 装备模拟器和装备查询中存在英文装备名、缺图标、以及展示装备与可执行 SimC 装备来源不清的问题。 | 带 itemId 的装备可通过 Battle.net Game Data API 显示官方中文名、图标和核验状态；职业装备页也能通过别名映射和官方英文名精确检索复用同一份物品元数据。 | 依赖服务器 Battle.net API 凭据；构筑页的 Archon/Wowhead 链接参考必须标记为 `source_reference`，不能伪装成已核验装备。 | 数据可信度与赛季同步完善 / SimC 输入契约产品化 | 已完成 |
| 正式域名、HTTPS 和微信 request 合法域名 | README、news 架构文档 | 当前开发联调用 HTTP/IP，体验版和正式版需要合法域名与 HTTPS。 | 让小程序发布链路稳定，减少环境差异导致的空屏或请求失败。 | 需要域名、证书、Nginx、微信后台配置协同完成。 | 正式发布与刷新可观测 | 候选 |
| 刷新 run 错误记录和管理端查看 | news 架构文档 | 定时刷新失败或源站异常时，当前排查依赖日志和人工检查。 | 运营上能看到何时刷新、是否失败、失败原因和数据新鲜度。 | 管理端鉴权、限流和可见范围需要先定义。 | 正式发布与刷新可观测 | 候选 |
| 移除新闻手动刷新入口和 scheduled 鉴权 | news 架构文档；2026-06-17 用户确认移除手动刷新 | 生产环境不应让用户端直接触发源站抓取。 | 降低源站压力，避免刷新接口被误用，首页只消费 ready payload。 | scheduled 刷新后续仍需要服务端鉴权、来源健康记录和刷新 run 管理。 | 正式发布与刷新可观测 | 已采纳 |
| 职业专精数据定时采集 | builds 架构文档 | 当前职业专精数据先以结构化契约和种子表达，后续需要真实刷新。 | 构筑、装备、属性和循环能跟随版本与热修变化。 | Raider.IO、Warcraft Logs、Archon、Subcreation 等来源的 API 可用性和许可需要确认。 | 职业 / PVE 数据采集自动化 | 候选 |
| 低样本专精不输出强结论 | builds 架构文档 | 样本少的专精容易被误判为“弱”或“最优构筑已确定”。 | 保护冷门专精玩家，提升数据解释可信度。 | UI 需要展示“样本不足”而不是空态或硬结论。 | 数据可信度与赛季同步完善 | 候选 |
| PVE 团本和大秘境日志样本刷新 | README、PVE payload | 当前 PVE 专区已经有队伍、职业、赛季副本、团本战报入口，后续应接入真实样本刷新。 | 玩家能按当前赛季理解副本、首领和队伍趋势。 | 数据源、赛季切换和团队 raid 进度变化都需要 freshness 标记。 | 职业 / PVE 数据采集自动化 | 候选 |
| WebSim 角色档案同步 / 载入角色 | WebSim 前端占位 | 页面已有“载入角色”入口，但账号数据可用前只能提示等待同步。 | 让玩家围绕自己的角色构筑和装备直接模拟。 | 账号授权、角色来源、隐私边界和缓存策略待设计。 | 角色绑定与个人化工作台 | 待确认 |
| 官方 SimulationCraft addon `/simc` 导出作为最高保真输入 | 本地记忆、SimC 文档 | 生成模板和展示型构筑上下文不足以代表玩家真实角色。 | 明确告诉用户最可靠的模拟输入是什么。 | 需要继续降低非 SimC 熟手的导入理解成本。 | SimC 输入契约产品化 | 已完成 |
| confirmOnly 与 final submit 复用同一 payload | 本地记忆、SimC flow | 确认阶段和提交阶段如果字段不一致，可能确认通过但真实提交失败。 | 降低“看起来能跑、提交却不跑”的体验问题。 | 后续新增字段仍必须遵守同一请求 builder。 | SimC 输入契约产品化 | 已完成 |
| 展示型 gear 与可执行 SimC gear 严格分离 | 本地记忆、SimC 文档 | 构筑页装备候选常常缺少 bonus、gem、enchant 等 SimC 字段。 | 避免候选装备被误写入 profile，产生虚假的模拟结论。 | 需要在 UI 中解释为什么某些装备只是候选、不能提交。 | WebSim 到 SimC 的可提交闭环 | 已完成 |
| 规范化 SimC slot keys | 本地记忆、WebSim 改动 | plural/alias slot 名如果进入最终 profile，会造成装备导入不稳定。 | 提高 WebSim、构筑页和 SimC 之间的装备序列化可靠性。 | 前后端都要使用同一套 canonical slot。 | SimC 输入契约产品化 | 已完成 |
| SimC 证据状态机 | SimC 风险规避文档 | 用户需要明确看到确认中、执行中、失败、已跑通、需要 `/simc` 的不同状态。 | 减少“后端做了但前端看不出来”的误解。 | 需要统一后端 stage、前端卡片和任务详情文案。 | SimC 输入契约产品化 | 候选 |
| LLM evidence JSON 与 report schema | SimC 风险规避文档 | 自由文本 prompt/report 容易让模型编数字或误读进度行。 | AI 报告可校验、可回退、可解释。 | Schema、allowedNumbers 和 fallback 策略需要先稳定。 | LLM 报告 schema 化 | 候选 |
| 网络、代理、SimC、LLM、参考数据 health check | SimC 风险规避文档 | 服务器网络、代理、SimC 二进制和 LLM 配置是独立漂移面。 | 部署后能快速定位是哪一层坏了。 | 需要避免 health check 本身过重或依赖不稳定外部调用。 | 正式发布与刷新可观测 | 候选 |
| WCL 完整日志复盘 | README、SimC 风险规避文档 | 只跑理论 SimC 不能解释实战中为什么打不出来。 | 把理论收益和实战问题放在同一份报告里。 | WCL 导出、日志权限、证据抽取和报告边界需要设计。 | WCL / 日志复盘链路 | 候选 |
| Codex Worker 作为异步复杂复核者 | SimC 风险规避文档 | 普通请求不适合每次都调用 Codex，但复杂 profile/WCL 问题需要更深推理。 | 高复杂度问题可深挖，主链路仍保持快速确定。 | 需要任务隔离、超时、可观测和触发条件。 | 深度 Codex Agent 工作流 | 暂缓 |
| 角色绑定、订阅提醒和收藏管理 | README | “我的”tab 已定位为角色偏好、收藏职业、订阅与数据源设置。 | 从一次性查询转为长期个人工作台。 | 用户体系、权限、通知能力和数据源设置需要统一设计。 | 角色绑定与个人化工作台 | 候选 |
| 将 JS payload 迁移到数据库化采集任务 | README | 当前部分结构化数据仍有本地 payload / fallback 成分。 | 数据更新更自动，前端和后端契约更稳定。 | 迁移期间要保留 fallback，避免线上空屏。 | 职业 / PVE 数据采集自动化 | 候选 |
| 首页与 tab 权重重排 | 当前 roadmap 讨论 | 项目能力线增多后，平均分配入口会让主路径不清晰。 | 让用户更快进入最核心工作流。 | 需要先决定产品定位和主场景。 | 首页与 tab 权重 | 待确认 |

## 已采纳索引

| 想法 | 采纳位置 | 证据 |
| --- | --- | --- |
| 用 roadmap 作为长期推进控制台 | [roadmap.md](../roadmap.md) | 当前文档体系 |
| 保留 `docs/plans/` 作为历史执行计划 | [roadmap.md](../roadmap.md) | `docs/plans/*.md` |
| 用户确认 OK 后主动纳入 roadmap 或提醒纳入 | [roadmap.md](../roadmap.md) | 当前维护规则 |
| WebSim 到 SimC 的可提交闭环 | [roadmap.md](../roadmap.md) | `server/websim_payload.py`, `tests/websim_payload_test.py`, `tests/news_backend_test.py`, [simulator-simc-end-to-end.md](../simulator-simc-end-to-end.md) |
| SimC 输入契约产品化 | [roadmap.md](../roadmap.md) | `websim/app.js`, `server/news_backend.py`, `server/websim_payload.py`, `tests/websim-page.test.js`, `tests/websim_payload_test.py`, [simulator-simc-end-to-end.md](../simulator-simc-end-to-end.md) |
| 装备中文名与官方图标补全 | [roadmap.md](../roadmap.md) | `server/websim_payload.py`, `server/builds/home-payload.js`, `server/news_backend.py`, `pages/builds/detail.*`, `websim/app.js`, `websim/app.css`, `tests/websim_payload_test.py`, `tests/builds-home-payload.test.js`, `tests/builds-page.test.js`, `tests/websim-page.test.js` |
| 小程序原生 WebSim 天赋模拟器 | [roadmap.md](../roadmap.md) | `app.json`, `pages/builds/talent-simulator.*`, `pages/builds/websim-api.js`, `server/builds/home-payload.js`, `server/simulator_payload.py`, `tests/talent-simulator-core.test.js`, `tests/builds-page.test.js`, `tests/frontend-api-client.test.js`, `tests/news_backend_test.py`, `tests/simulator-page.test.js` |
| 模板化构筑与固定 SimC 输入 | [roadmap.md](../roadmap.md) | `pages/common/build-template-storage.js`, `pages/profile/profile.*`, `pages/builds/talent-simulator.*`, `pages/builds/detail.*`, `websim/`, `pages/simulator/simc.*`, `server/simulator_payload.py`, `tests/build-template-storage.test.js`, `tests/profile-auth.test.js`, `simulator_tasks` |
| 天赋/装备模拟器保存模板 | [roadmap.md](../roadmap.md) | `pages/common/build-template-storage.js`, `pages/profile/profile.*`, `pages/builds/talent-simulator.*`, `pages/builds/detail.*`, `tests/build-template-storage.test.js`, `tests/profile-auth.test.js`, `tests/builds-page.test.js` |
| 账号化 CRUD 数据边界 | [roadmap.md](../roadmap.md) | `pages/common/auth-client.js`, `pages/common/api-client.js`, `server/news_backend.py`, `tests/frontend-api-client.test.js`, `tests/news_backend_test.py` |
| 数据库架构治理与迁移路线 | [roadmap.md](../roadmap.md) | [2026-06-17-database-architecture-governance.md](../plans/2026-06-17-database-architecture-governance.md), `server/news_backend.py`, `server/websim_payload.py`, `server/analytics.py` |
| 资讯详情完整中文化与发布质检 | [roadmap.md](../roadmap.md) | `server/news_collector.py`, `server/news_translator.py`, `server/news_backend.py`, `server/news/articles.seed.json`, `server/news/home-payload.js`, `pages/news/detail.*`, `tests/news_*` |
| 社区大秘天赋模板 v1 | [roadmap.md](../roadmap.md) | `server/websim_payload.py`, `server/community_talent_sources/`, `pages/builds/talent-simulator.*`, `pages/simulator/simc.js`, `tests/websim_payload_test.py`, `tests/talent-simulator-core.test.js`, `tests/builds-page.test.js`, `tests/simulator-page.test.js` |
| 全职业天赋规则权威层 | [roadmap.md](../roadmap.md) | `server/websim_payload.py`, `pages/builds/talent-simulator-core.js`, `tests/websim_payload_test.py`, `tests/talent-simulator-core.test.js` |
| 全职业天赋规则校验与追踪机制 | [roadmap.md](../roadmap.md) | `server/websim_payload.py`, `server/news_backend.py`, `tests/websim_payload_test.py`, `tests/talent-simulator-core.test.js` |
| 职业专精内嵌装备模拟模块 | [roadmap.md](../roadmap.md) | [2026-06-17-builds-inline-gear-simulator-design.md](../plans/2026-06-17-builds-inline-gear-simulator-design.md), `pages/builds/detail.*`, `server/websim_payload.py`, `tests/builds-page.test.js`, `tests/websim_payload_test.py` |
| 数据与模拟健康哨兵 | [roadmap.md](../roadmap.md) | 当前对话确认；后续围绕 `server/deploy_lighthouse.sh`, `server/websim_payload.py`, `server/game-season.js`, `pages/simulator/simc.*` 设计 |

## 补录模板

```markdown
| 想法 | 来源 | 解决的问题 | 潜在收益 | 风险 / 疑问 | 建议归属里程碑 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
|  | 本地讨论，待补录证据 |  |  |  |  | 待补录 |
```
