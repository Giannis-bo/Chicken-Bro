# 炸鸡队长统一 ChatBot 与受控分析架构设计

状态：`下一步`
分类：`Strict（分阶段实施）`
确认日期：2026-07-24

实施入口：尚未创建。本设计完成书面审阅后，只为阶段 0 建立首份实施计划；后续阶段分别规划、验证和发布，不做一次性整体切换。

当前事实：[project-state.json](../project-state.json)、[roadmap.md](../roadmap.md)、[Harness](../harness.md)、[SimC 全链路](../simulator-simc-end-to-end.md)、[验证矩阵](../verification-matrix.md)

## 设计结论

炸鸡队长对玩家只呈现为一个 ChatBot，专注于魔兽世界正式服当前版本和测试服的构筑、SimC、WCL 与社区信息分析。玩家不需要选择“即时问答”“证据模式”或“诊断模式”；系统根据问题、当前上下文、授权范围和证据强度自动选择受控 Tool，必要时把重分析转为可追踪任务，再回到同一段对话给出结论。

实现采用现有 Python/PostgreSQL 体系下的模块化单体：

- 一个 `wow-backend` 拥有聊天 API、身份与权限、轻量 Tool、外部来源适配、证据校验和回复组织；
- 一个通用 `analysis-worker` 执行 WCL 深度分析和 SimC 对比等耗时任务；
- 现有 PostgreSQL 保存 owner 隔离的个人数据、对话与任务状态、紧凑证据和结果，并以任务表承担首版轻量队列；
- Chat Orchestrator、Personal Context、WoW Source Gateway、Analysis Engine 和 Evidence Ledger 是代码职责边界，不是五个服务。

首版不引入 Redis、RabbitMQ、Kafka、微服务、通用插件平台、向量数据库或任意网页代理。只有真实负载、资源竞争或运维证据证明现有边界不足时，才考虑拆分。

## 用户目标与完成体验

### 核心用户结果

玩家应当能够在同一个对话入口中：

1. 询问正式服当前版本或测试服的职业、专精、天赋、装备、打法和版本变化；
2. 查询自己已经保存的天赋模板、装备模板和 SimC 任务记录；
3. 获取 WCL、Raider.IO、Wowhead、Archon.gg 及其他受支持来源的信息；
4. 请求 WCL 复盘、SimC 对比、天赋与装备收益分析；
5. 获得结论优先、轻松但专业、具有高端玩家判断力的中文建议。

### 主路径

普通问题直接返回快速回答。需要个人数据时，后端先在当前账号范围内寻找候选：只有一个明确对象时直接使用，存在多个模板或任务时返回选择卡片。需要私有 WCL、明确消耗资源的 SimC 对比或可能改变分析对象时，先让玩家确认。

轻量 Tool 在当前请求内完成，并显示简短查询状态；WCL 深度分析和 SimC 对比创建任务卡片，持续显示排队、运行、部分完成、失败或完成状态。任务完成后，结论追加到原话题，不要求玩家重新描述上下文。

### 异常路径

- 未登录玩家仍可进行不依赖个人数据的普通问答；“我的模板”和“我的任务”要求登录。
- 来源超时或不可用时，回答明确说明缺失来源、数据时间和可继续执行的动作。
- 证据不足时可以给出通用排查方向，但不得生成日志事实、DPS、排名、收益百分比或个人结论。
- 当前话题存在多个可能对象时只追问一个最关键问题，避免把 Tool 参数表暴露给玩家。

## 非目标

首版不承诺：

- 自动爬取任意网站、绕过来源限制或把社区页面批量沉淀为本地知识库；
- 通过模型直接访问 SQL、Shell、文件系统、凭证或任意 URL；
- 自动生成无限候选并运行大规模 SimC 搜索；
- 把社区热度、单份 WCL、一次 SimC 或模型知识描述成绝对 BiS；
- 让模型结论自动覆盖个人模板、公共模板或后端 authority；
- 建立团队级 WCL 工作台、完整 RAG 平台、通用 Agent 插件市场或独立计费系统。

## 目标架构

```text
Taro Chat UI
  -> wow-backend
       -> Chat Orchestrator
       -> Personal Context tools -> PostgreSQL
       -> WoW Source tools -> approved external sources/cache
       -> Evidence and response validation
       -> heavy analysis request -> PostgreSQL job
                                      -> analysis-worker
                                           -> WCL analysis
                                           -> SimC comparison
                                      -> evidence/result -> PostgreSQL
  <- answer / choice card / task card / completed analysis
```

部署单元始终保持为后端、通用 Worker 和 PostgreSQL 三部分。后端内部的逻辑模块通过固定接口通信；它们可以独立测试和替换，但不形成网络服务边界。

### Chat Orchestrator

每轮对话按固定顺序执行：

1. 识别用户意图、正式服或测试服版本、职业专精、场景和当前对象；
2. 判断是否可以直接回答、需要轻量 Tool、需要玩家选择，或需要创建重任务；
3. 调用受控 Tool，并接收结构化结果；
4. 校验 Tool 状态、来源版本、时间、owner、数字和证据引用；
5. 组织结论、依据、限制和下一步；
6. 在返回前执行数字白名单、`evidenceRefs`、权限和失败状态校验。

模型可以选择 Tool、归纳事实和解释取舍，但不能直接访问 PostgreSQL、外部 API、密钥或执行器，也不能自行计算 WCL 事件和 SimC 结果。生产主链采用可替换的常规模型执行器，不与 Codex CLI 绑定；Codex 只保留为开发、复核或明确的低频特殊任务选项。

### Personal Context

Personal Context 只读取当前登录账号授权的数据，并为模型返回必要摘要：

- 稳定角色、常用职业专精和场景偏好；
- 已保存天赋/装备模板的名称、revision、版本、场景和紧凑摘要；
- SimC 任务的状态、输入快照、运行版本和结果摘要；
- 当前话题选中的模板、任务、WCL 报告和仍在运行的分析任务。

短期对话上下文保存最近消息、当前职业专精、场景、已选对象和 Tool 引用。新话题清除话题绑定。长期记忆只保存明确、稳定、可编辑的结构化偏好，不保存完整日志、完整角色档案、无限对话摘要或模型推断的人格标签。

### WoW Source Gateway

每个外部来源使用独立 adapter，负责参数校验、请求预算、缓存、新鲜度、来源版本、错误映射和引用生成：

- Warcraft Logs 使用官方授权与 API。公开报告和私有报告分开处理，私有数据只在用户明确授权后读取；
- Raider.IO 使用受支持的公开 API、缓存和归因规则；
- Blizzard 或本地 canonical catalog 提供游戏实体和后端已确认事实；
- Wowhead 首版只使用受支持的实体信息、tooltip、公开引用或链接，不假定存在通用攻略 API；
- Archon.gg 首版只作为允许访问的参考来源或外链，不建设未经授权的抓取器；
- 新社区来源必须单独进入 allowlist，定义访问方式、缓存、新鲜度、版权和降级边界。

来源结果必须携带 game track、补丁或赛季、采集时间、新鲜度和限制。来源之间发生冲突时不由模型偷偷合并，而是保留差异并说明各自代表什么。

### Analysis Engine

确定性程序负责抓取、解析、指标计算和模拟执行；模型只在这些结果之上选择主要问题、解释影响并给出有序建议。

WCL 和 SimC 首版共用一个通用 Worker。只有后续出现真实 CPU/内存竞争、队列互相阻塞或不同扩缩容要求时，才拆为独立 Worker。

### Evidence Ledger

Evidence Ledger 首版是 Tool 和任务共享的结构化证据合同，不是独立服务或通用 Claim 平台。每项可见结论至少绑定：

- 来源类型和引用；
- 查询或任务参数摘要；
- owner 和授权范围；
- game track、版本、赛季或运行时 revision；
- 采集、执行和完成时间；
- `verified`、`partial`、`stale`、`blocked` 或 `failed` 状态；
- 可用于回答的数字白名单；
- 限制和建议下一步。

证据可随消息或任务结果以 JSONB 保存。只有查询、复用和保留策略证明需要独立表时才进一步拆分。

## Tool 合同

首版维护少量明确 Tool，不建设通用插件系统。

### 个人数据 Tool

- `find_saved_templates`：按当前账号、类型、职业专精和场景寻找模板；
- `get_saved_template`：读取一个已授权模板的紧凑快照；
- `find_simc_tasks`：查询当前账号的 SimC 任务；
- `get_simc_task_result`：读取任务输入版本、状态、结构化结果和证据。

### 来源 Tool

- `query_raiderio`：读取允许的公开角色或大秘境数据；
- `lookup_wow_entity`：查询后端 canonical catalog、Blizzard 或受支持实体资料；
- `search_current_wow_sources`：在已允许来源中查询当前版本参考信息，不接受任意域名。

### 分析 Tool

- `inspect_wcl_report`：验证报告、战斗、角色、可见性和可分析范围；
- `analyze_wcl`：创建或复用 WCL 深度分析任务；
- `compare_simc`：创建或复用受控 SimC 对比任务。

所有 Tool 返回统一 `ToolResult`：

```text
status
facts[]
evidence[]
limitations[]
nextActions[]
```

Tool 不接收由模型提供的 `userId`。owner 始终由后端登录态注入。模型不能获得跨用户查询、任意 URL、SQL、Shell、密钥、自动覆盖模板、批量 SimC 或把输出直接发布为公共事实的 Tool。

## PostgreSQL 职责

PostgreSQL 继续作为唯一运行时持久层，负责：

- owner 隔离的模板、角色、任务、会话和消息；
- 结构化长期偏好；
- 分析任务的状态、优先级、fingerprint、lease、heartbeat、attempt、取消和结果；
- Tool 查询摘要、紧凑证据、来源缓存与新鲜度；
- 任务完成后供同一话题恢复的上下文引用。

它不负责模型推理、SimC 执行、网页抓取、完整 WCL 事件仓库、完整 SimC stdout、模型 chain-of-thought 或明文密钥保存。首版由 PostgreSQL 任务表承担轻量队列，避免引入第二套消息基础设施。

## WCL 分析设计

### 输入确认

分析必须确定报告 code、fight、actor、专精、game track 和用户问题。缺少关键对象时先返回候选或要求一次确认；不得默认把报告中第一个角色当作用户。

### 确定性流水线

1. 通过官方 API 验证报告可见性、战斗和角色；
2. 按 actor、fight 和所需数据类型分页拉取事件，不能依赖当前有限事件样本；
3. 计算技能次数、资源使用、Buff/DoT 覆盖、爆发窗口、停手、死亡、打断和机制事件等确定性指标；
4. 只有 boss、难度、专精、版本和样本窗口可比时，才生成对照；
5. 模型从已验证指标中选择 2 至 4 个主要问题，按影响和可行动性排序。

事件量过大时允许保存短期临时数据或分段聚合，但长期只保留输入身份、聚合指标、证据引用和结论。原始事件在任务结束或保留窗口到期后清理。

### 强结论边界

单份日志能够说明该次战斗发生了什么，不能单独证明通用最优打法。排名、百分位、技能差值或死亡结论必须来自明确字段或匹配样本；无法取到对应数据时标为 `partial`，不能由模型补全。

## SimC 对比设计

每个任务保存不可变输入快照，至少绑定模板及 revision、canonical profile、SimC runtime revision、fight style、目标数、时长、迭代数和临时 Buff。

对比流程：

1. 先运行或复用基准；
2. 候选只来自玩家明确指定、已保存模板，或模型提出并通过 canonical Resolver 校验的少量高层变更；
3. 所有候选使用相同 runtime、场景、时长、目标数和迭代设置；
4. 只有成功且可比较的结果才展示绝对值、差值和百分比；
5. 模型解释收益来自哪个改动、适用什么场景及牺牲了什么，不把单场景收益写成全局最优。

同一 owner、输入快照、版本、分析类型和场景生成 fingerprint。已有运行中任务直接复用；已完成且仍满足版本与新鲜度要求的结果直接返回。

## 任务状态与 Worker

任务状态固定为：

```text
queued -> running -> succeeded | partial | failed | timed_out | cancelled
```

Worker 领取任务时写入有期限的 lease，并周期性 heartbeat。Worker 崩溃后，过期 lease 可被重新领取；旧 Worker 的迟到结果受 fencing 约束，不能覆盖新 attempt。临时网络错误允许有限重试和退避，输入无效、权限失败和确定性校验失败不重试。用户可以取消尚未完成的任务。

Worker 初期默认单并发，并配置单任务 CPU、内存和运行时间上限。队列深度、最老任务年龄、失败类型和运行时版本进入健康检查。

## 回复与人格

炸鸡队长默认采用以下表达顺序：

1. 先给判断或建议；
2. 再给 2 至 4 个最关键依据；
3. 明确版本、场景、来源和不确定性；
4. 给出按优先级排序的下一步；
5. 只有确实影响结论时才追问一个关键问题。

语气应当像轻松、专业、有实战经验的高端玩家：使用玩家熟悉的术语，但不过度玩梗；能够明确说“证据不够”“这只是单体木桩收益”或“这次日志不能证明该结论”。不堆砌原始指标，也不以权威口吻掩盖来源限制。

## 安全、隐私与资源预算

### 权限和数据最小化

- owner 只能由后端身份系统确定；
- OAuth Token 和 API 密钥留在服务端，不进入模型上下文、ToolResult 或日志；
- Tool 使用固定 Schema、来源 allowlist、超时和返回大小上限，阻断 SSRF 和任意执行；
- 管理健康页只展示任务状态和脱敏摘要，不展示私人模板、完整聊天或私有 WCL 内容；
- 长期只保留复现和解释所需的紧凑数据，原始临时输入按明确保留周期清理；
- 后续提供删除话题、历史、个人结构化记忆和来源授权的用户入口。

### 成本预算

- 每轮对话限制 Tool 次数、总等待时间和模型上下文长度；
- 每个用户限制重任务并发，重复任务按 fingerprint 复用；
- SimC 只允许一个基准和少量候选；
- 每个来源具有速率预算、缓存和新鲜度策略，禁止无限重试；
- 缓存和模型上下文不因完整 WCL 事件或完整 SimC 输出无限增长。

首版阈值由后端配置管理，不建立复杂配额、计费或优先级平台。

## 故障隔离与回滚

- 单个来源异常只关闭对应 Tool；可用缓存必须标注采集时间和 `stale` 状态；
- WCL 或 SimC 证据不完整时强结论 fail closed；
- 模型异常时保留任务状态、结构化结果和确定性降级；
- Worker 异常通过 lease、heartbeat 和 fencing 恢复；
- PostgreSQL 异常时，个人数据和任务操作 fail closed，绝不回退到不具备 owner 隔离的本地存储；
- 每个 Tool、来源 adapter、模型执行器和 Worker 路径具有独立 feature flag；
- 关闭重分析后，普通聊天、模板查询和任务历史仍可独立保留。

首版复用现有认证、PostgreSQL、服务日志、systemd 和健康检查，不增加完整 IAM、独立 Secrets Vault 或分布式追踪平台。

## 分阶段交付

### 阶段 0：现状特征化与合同

固化 Chat、Tool、Job 和 Evidence 合同；为现有模板查询、SimC 任务、Raider.IO、WCL bootstrap、数字白名单和确定性降级建立特征测试；统一正式服、测试服、版本和数据时间表达。本阶段不改变玩家体验。

### 阶段 1：统一 ChatBot 与轻量 Tool

交付普通当前版本问答、个人模板和 SimC 任务查询、Raider.IO、游戏实体与受支持社区信息查询，以及同一话题中的选择卡片和证据化回答。前端只有一个聊天入口，不暴露内部模式。

### 阶段 2：通用 Worker 与 SimC 对比

建立 PostgreSQL 任务领取、lease、heartbeat、取消、恢复和 fingerprint 复用；优先复用现有 SimC 能力，交付基准加少量候选的可复现对比和任务卡片。

### 阶段 3：WCL 深度分析

补齐 report/fight/actor 识别、分页事件、确定性指标、可比样本和证据受限解释。WCL 的复杂性不提前进入普通 Chat 主链。

### 阶段 4：验证后扩展

根据真实使用数据决定是否增加更多社区来源、职业知识索引、团队分析、多方案搜索、主动提醒或周期任务。这些能力不阻塞核心 ChatBot。

每个阶段单独建立 implementation plan 和 Harness release packet。涉及后端、PG、Worker 或用户可见运行时的阶段必须先做候选部署 smoke，再按当前 Harness 规则进入合并和上线。

## 验收与验证

### 用户可见验收

- 普通问题明确绑定正式服或测试服、版本、来源和数据时间；
- “我的模板/任务”严格 owner 隔离，多候选时可选择；
- SimC 结论可追溯到不可变输入、runtime、场景和结果；
- WCL 结论绑定报告、战斗和角色，且不把猜测写成日志事实；
- 来源、模型或 Worker 异常时给出诚实、可继续行动的降级；
- 回复保持结论优先、轻松专业、证据边界清楚。

### 自动化验证

- Tool Schema、数字白名单、证据引用和 owner 隔离合同测试；
- WCL 固定 fixture 的分页、actor 过滤和确定性指标测试；
- SimC 相同场景比较、不可比结果拒绝和 fingerprint 复用测试；
- Job 状态机、lease 过期、heartbeat、取消、重试和 fencing 测试；
- 来源 adapter 的超时、限流、缓存、stale 和错误映射测试；
- 模型失败、来源失败、Worker 失败和 PostgreSQL fail-closed 测试；
- 选择性真实来源 smoke、候选部署 smoke、健康检查和回滚演练。

人格与回答质量使用固定问题集做人工复核，至少覆盖普通版本问题、个人模板、多候选、SimC 成功/失败、WCL 完整/部分证据和来源不可用。模型表达评估不能替代确定性合同测试。

## 已确认决策与暂缓项

已确认：

- 对外只有一个 ChatBot，不向玩家暴露内部模式；
- 采用模块化单体后端、一个通用 Worker 和现有 PostgreSQL；
- Tool 是后端内部受控能力，不是独立服务或通用插件；
- PostgreSQL 首版兼任轻量任务队列，不新增消息中间件；
- 模型负责理解和解释，确定性程序负责事实、指标与执行；
- WCL 与 SimC 重分析异步化，SimC 先于 WCL 深度分析落地；
- 严格保留 owner、证据、版本、新鲜度和 fail-closed 边界。

暂缓：

- 微信原生 AI 供应商适配；
- WCL/SimC 独立 Worker；
- 向量数据库和完整知识库；
- Archon 或其他社区的未经授权抓取；
- 团队级分析、无限候选搜索和主动周期分析。
