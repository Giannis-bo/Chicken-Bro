# Chickenbro 当前架构

依据 2026-09-09 仓库实现整理。当前只提供 Web Chat 与 SimC，QQ 网站登录已上线；本轮移除残余小程序源码的部署状态另见[清理计划](plans/2026-09-09-mini-retirement.md)。

## 客户端与传输

`apps/mini-taro/src/app.tsx` 挂载 React WebApp，Taro H5 使用单一 `pages/web/index` 入口。`/` 是对话，`/simc` 是模拟，`/?view=faq` 是 FAQ；旧短路径仅作为 Web URL 兼容入口，不挂载小程序页面。

依赖方向为 UI → typed API client → HTTP route → application → domain / port → repository / adapter。Domain 不依赖 FastAPI、Taro 或具体外部 provider。客户端使用显式 `web` 或受限 `public` auth context，普通请求使用 Taro H5 request，SSE 使用浏览器 fetch；不再提供 Mini Bearer、微信运行环境或原生分块请求分支。

## 身份

QQ 登录由 `identity.qq_application` 与 `integrations.qq_connect` 实现：同源 POST 创建随机 state 和 HttpOnly 浏览器绑定，浏览器跳转 QQ 官方授权，固定 callback 校验 state、绑定、时效和 AppID，再由数据库原子消费尝试。provider/appid/openid 映射到 `identity.users.id`，签发 Web Session 和 CSRF Cookie。

授权码、AppKey 和 QQ token 只在服务器 provider 边界短暂使用，不写日志、业务表或公开响应。QQ 昵称与头像经过有界清理；头像只允许受信 HTTPS QQ 域名。默认 Cookie 使用 Secure、HttpOnly（Session）、SameSite=Lax 和 Path=/；写请求检查精确 Origin/Host 与 CSRF。Bearer 请求拒绝，QQ 登录不会自动关联旧微信账号。

## Chat

`server/app/chickenbro` 拥有会话、消息、运行、图片和工具结果。路由从 Principal 注入 owner；账号级单回复与请求幂等在服务端执行。Web 可读取历史、流式进展、耗时、回答反馈以及归档会话。

生成使用 `chat.executions` 持久化调度和独立 Worker；API 断开不主动取消生成。Worker 通过租约、阶段和工具结果记录处理故障，不盲目重放副作用。图片存储与读取 owner-scoped，归档和保留策略由服务端执行。

## SimC 与 Worker

`server/app/simulation` 拥有 Raider.IO 来源快照、校验、compiler、任务、attempt 和结果。`server/app/worker` 负责 PostgreSQL 队列 claim、lease、心跳和 handler dispatch。SimulationCraft 仅在云端运行；结果必须有正业务指标与来源信息，不能用进程退出码代替成功。

WCL 适配器用于战斗研究及历史天赋恢复，不恢复 WCL 新角色导入。输出和坦克专精受运行配置与 readiness 控制，治疗明确拒绝。新任务和装备对照保留原快照与结果。

### 场景实验（已发布，compiler v5）

任务工具返回 owner-scoped 原来源、角色、有效装备与天赋。`preview_simulation` 复用 application 的只读编译预检，`query_simulation_options` 查询引擎绑定的节点选项/物品名称，`compare_simulation_jobs` 校验同快照、同引擎/compiler、同控制参数后计算差异与保守误差判断。

compiler v5 增加 `talentOverrides`，不改原始快照；`baseJobId` 连续修改保留之前的有效配置。版本绑定的连线资料校验跨节点分配、点数门槛和英雄树；资料无法覆盖的配置拒绝执行。装备查询可从已观察到的升级 bonus 生成同进度饰品候选，并明确它是假设版本；未覆盖的制造/特殊物品版本仍需可靠资料。v5 Worker 要求真实报告核对天赋、装备 ID 和覆盖装等；历史编译版本保留原行为。Web 通过 `scenarioVersion=3` 读取天赋场景，旧客户端保持旧字段合同。实施与剩余资料缺口见[场景实验计划](plans/2026-09-09-simc-scenario-experiments.md)。

## 数据与所有权

PostgreSQL 当前 schema 为 `identity`、`chat`、`simc`、`ops`。所有用户业务查询从内部 `user_id` 限定所有权；请求体不能选择 owner。`ops.job_queue` 包含任务引用，`ops.audit_events` 保留操作审计；清理不能只删除用户而遗漏队列、运行及图片。

历史 migration 不改写，旧微信 schema 只作为已应用迁移与恢复兼容结构保留；本轮数据清理以精确清单及新恢复证据执行，不与 QQ 数据合并。

当前职责与检查入口见[项目 owners](project-owner-map.json)、[后端 owners](backend-owner-map.json)和[验证矩阵](verification-matrix.md)。[旧双端架构](chickenbro-simc-architecture-pre-mini-retirement.md)仅供追溯。

## 运营统计后台

`/admin` 是只读运营页面；`server/app/admin/application.py` 管理唯一管理员和北京时间查询范围，`repository.py` 在只读快照事务中聚合当前 QQ 用户的 Chat/SimC。`WOW_ADMIN_USER_ID` 只能配置一个经真实 QQ 会话核验的内部 UUID，空值拒绝所有人，固定测试账号及已知模拟身份不得成为管理员。每次统计请求检查 Web session 和服务端权限并记录审计，响应禁止缓存。`/admin/access` 只返回当前账号自己的核验标识和权限。

累计用户截至所选结束日，活跃用户以提问/模拟提交去重；成功率不含进行中或取消，SimC 缺少有效指标/来源的成功状态单列异常并计入失败分母；反馈和任务状态是查询时的当前值。统计排除已知验收模拟身份，不包含页面访问量或推算费用。

### 自定义施法（compiler v6，已发布）

`scenario.actionLists` 表示完整的自定义 APL：default 必填，可含 precombat 和有界子列表；省略字段沿用原配置，提供字段则整组替换，不与旧列表部分合并。预检只证明结构可编译；云端引擎负责技能/表达式语义校验，未知技能不能成为成功结果。拒绝换行、路径/顶层选项注入、缺失或递归列表引用，保留角色快照和其他参数。

v6 结果继续核对有效装备/天赋，并保存带 profile hash 的 `actionEvidence`，仅投影报告采样迭代中最多 512 个条目的技能名、ID 和相对时间；不公开原始报告路径或目标数据。APL 是优先级，不能仅凭列表顺序推断施放顺序；strict_sequence 在当前引擎 JSON 中可能只显示包装动作，应使用可核对的条件式动作或明确缺少内部时间证据。Web 通过 scenarioVersion=4 接收新场景字段，旧客户端不接收该字段。

Chat 对陌生玩家术语先结合职业、赛季和配置检索；无关搜索结果须在现有预算内换词/来源，只有仍无法消歧时才追问。不固化俗称映射或套装效果。验证与未覆盖范围见[本轮记录](../artifacts/verification/2026-09-10-custom-apl/README.md)。生产 API/Worker 已同时启用 v6，发布源码与公网验收见[发布记录](../artifacts/verification/2026-09-10-custom-apl/release/README.md)。

## 有限研究的执行与证据（2026-09-11）

研究范围由服务端在消息入场时关联：10名玩家、3场战斗、3个比较组及4个新模拟跨轮累计。48次来源子查询、20,000事件请求单位和360秒是单个服务端run的执行保护；同run重建不刷新，正常用户追问可继续同一有限范围，历史累计成本不清零。没有新增按账号每日研究配额。原生搜索仍保留现有检索合同，不冒充已纳入后备网页五来源硬计量。

模型先判断目标与规模，明确无界Top100/全量采样先拒绝；有限问题先复用已有证据，再补能改变结论的缺口。WCL参数本地校验发生在预留上游工作前，非法参数返回可纠正错误。`healing`视图配对读取有效/含过量治疗表，保留负数调整项、父子项边界及完整性，按战斗时长归一；只对必要窗口补事件。

历史证据按账号、对话和当前研究投影，首个研究兼容旧持久化建立前的记录；显式新研究不自动继承旧对象。属性、装备优先于治疗汇总有界投影，嵌套命中细节不挤占属性；内容作为不可信资料。已完成战斗的成功overview/healing可在同账号同对话6小时内按规范化报告/战斗/角色/视图/窗口复用，原记录固定TTL，复用仍检查范围，记录0次新增上游。跨账号不共享。

0010迁移增量保存research_runs.work、agent_runs.model_usage和tool_results.request_json。模型usage保留input/output/cached/reasoning/total及primary/repair阶段；缺失为unknown，不推算历史token费用。来源次数是受控子查询计数，不等于全部HTTP往返数。

## 通用研究证据与上下文（2026-09-11）

历史投影复用现有WCL视图，按报告/战斗/角色/视图/窗口/过滤条件区分来源；整场casts/damage/gear的范围与事件窗口独立。治疗、伤害、施法、资源统计及有界事件样本保留各自完整性；partial不升级为verified，样本不证明完整时序或缺席。最多12条约3.8KB记录，优先属性并跨视图保留，超量与历史49条探测明确标记遗漏。旧记录缺少事件过滤信息时不合并为精确同查询。

`researchContext`从持久用户消息投影原目标与修正，并保留相邻助手选项用于指代；最多24KB，返回身份、顺序和遗漏标记，不把助手建议当用户授权。显式新研究切开旧消息和图片范围；正常追问保留当前研究。服务端状态同时给出跨轮范围已用/剩余与单run执行额度。

SimC网关只收集本run当前账号实际返回的任务与对照证据；最终回答对明确模拟完成、DPS/HPS和对照百分比的可识别声明进行有限检查，错误进入原有一次无工具修复。假设、条件说明、日志指标与无明确对应关系的自然语言不冒充已验证；这不是完整因果/语义验证。固定20题评测把真实trace、人工rubric与未运行项分别记录，默认离线检查不调用模型，也不能产生语义通过。
