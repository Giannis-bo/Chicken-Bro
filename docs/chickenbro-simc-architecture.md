# Chickenbro 架构

本文描述仓库实现与边界，不作为部署状态证明。当前产品仅含 Web Chat 与云端 SimC，使用 QQ 登录；各项交付状态见[项目状态](project-state.json)，职责与测试归属见[项目 owners](project-owner-map.json)和[后端 owners](backend-owner-map.json)。

## 客户端、身份与数据

Taro H5 的 `apps/mini-taro/src/app.tsx` 挂载 React WebApp，单一 `pages/web/index` 入口承载 `/` 对话、`/simc` 模拟、`/admin` 运营页与 `/?view=faq`。

依赖方向为 UI → typed API client → HTTP route → application → domain/port → repository/adapter。Domain 不依赖 FastAPI、Taro 或外部 provider；客户端显式使用 `web` 或受限 `public` context，普通请求使用 Taro H5 request，SSE 使用浏览器 fetch。

QQ 登录通过浏览器绑定、短时、一次性 state 和固定 callback 校验 provider/appid/openid，再映射到内部 `identity.users.id`。服务端签发 Secure、HttpOnly、SameSite=Lax Session；写请求检查 Origin/Host 与 CSRF，Bearer 不作为生产认证。授权码、AppKey 和 provider token 不进入日志、业务记录或公开响应；昵称和头像有界清理，头像限受信 HTTPS QQ 域名。

PostgreSQL 使用 `identity`、`chat`、`simc`、`ops` schema。业务查询由服务端 Principal 注入 owner，请求体不能选择所有权；队列与审计也纳入相应数据生命周期。历史迁移保留追溯，不作为重新迁移或删除的授权。

## Chat 与研究

`server/app/chickenbro` 拥有会话、消息、运行、图片及工具结果，执行账号级单回复和请求幂等。`chat.executions` 持久化调度，独立 Worker 使用 lease、阶段和工具结果处理故障；断开 API 连接不主动取消生成，不盲重放副作用。图片和历史读取均 owner-scoped。

研究由服务端在消息入场时关联，正常追问继续当前研究，显式新研究切开旧对象、消息与图片范围。模型先判断目标与规模，明确无界查询先拒绝；陌生术语结合职业、赛季和配置检索，先复用证据，再补能改变结论的缺口。

| 约束 | 范围与含义 |
| --- | --- |
| 10 名玩家、3 场战斗、3 个比较组 | 同研究跨轮累计的范围边界 |
| SimC 任务次数 | 单轮及跨轮均不限次数；保留提交记录与幂等复用，状态上限和剩余 null 表示不限次数 |
| 48 次来源子查询、20,000 事件请求单位、360 秒 | 单 run 执行保护；同 run 重建不刷新，正常追问不永久耗尽研究资格 |
| 历史成本 | 失败与跨轮消耗保留；缺失模型 usage 记 unknown，子查询数不等于全部 HTTP 往返 |
| 未覆盖范围 | 不承诺跨独立研究账号总配额，原生网页不冒充后备网页五来源硬计量 |

WCL 参数在预留上游工作前校验；统计保留窗口、过滤、层级及完整性。治疗视图配对有效/含过量表，保留负数调整与父子边界，按战斗时长归一；只有必要窗口补事件。日志频次、样本或同步事件不直接证明按键习惯、完整时序或动作缺席。

历史证据按账号、对话和研究投影，区分报告、战斗、角色、视图、窗口及过滤条件；未知过滤不冒充精确同查询。各视图保持自身完整性，partial 不升级为 verified，裁剪明确标记。已完成战斗的成功 overview/healing 可在同账号同对话 6 小时内复用，TTL 取原记录且仍检查范围，跨账号不共享。

通用证据投影最多 12 条、每条约 3.8KB，优先属性并跨视图保留；研究上下文最多 24KB，保留用户原目标、修正及必要相邻助手选项的身份、顺序和遗漏。助手建议与外部资料不成为用户授权。0010 迁移增量保存工作量、模型 usage 和请求元信息，primary/repair 阶段分别记账。

模拟声明检查只使用本 run 当前 owner 实际返回的任务与对照证据，对可识别的完成、DPS/HPS 和百分比声明进行有限核对，错误进入既有一次无工具修复。假设、条件及无法对应的自然语言不冒充已验证；固定语义评测区分真实 trace、人工 rubric 与未运行项，离线合同检查不产生语义通过。

## SimC 与 Worker

`server/app/simulation` 拥有 Raider.IO 快照、预检、compiler、任务、attempt 和结果；`server/app/worker` 负责 PostgreSQL 队列 claim、lease、心跳和 dispatch。引擎仅在云端运行，成功须有正业务指标与完整来源。输出/坦克支持由运行配置和 readiness 控制，治疗拒绝；WCL 用于研究和历史天赋恢复，不用于新角色导入。

任务及对照保留原始快照。`preview_simulation` 执行只读编译预检，`query_simulation_options` 提供引擎绑定选项，`compare_simulation_jobs` 核对同快照、引擎/compiler 与控制参数后计算差异及保守误差。天赋覆盖校验节点、点数门槛和英雄树；连续编辑保留已有有效配置，未覆盖资料拒绝执行。候选装备的假设版本须明示，制造/特殊版本不能从装等推定。

`scenario.actionLists` 为完整自定义 APL：default 必填，子列表有界；省略沿用，提供则整组替换。拒绝换行、路径/顶层选项注入及缺失/递归引用。预检仅证明可编译，云端校验实际语义；结果核对有效装备、天赋，并以 profile hash 绑定最多 512 条动作样本。APL 是优先级，样本与包装动作不能证明内部施放顺序。Web 通过 scenarioVersion=4 接收新字段，旧请求保留既有合同；实际 compiler 版本按运行核对。

## 运营后台

`server/app/admin` 提供只读 QQ 用户、Chat/SimC 聚合。`WOW_ADMIN_USER_ID` 只接受一个经真实 QQ 会话核验的内部 UUID，空值拒绝所有访问，测试身份不得成为管理员；每请求检查会话与权限并审计，响应不缓存。`/admin/access` 只返回当前账号自己的核验标识和权限。

统计使用北京时间区间与只读快照事务：活跃用户按提问/模拟提交去重，成功率排除进行中与取消，缺有效指标或来源的 SimC 成功状态计作异常失败；排除已知验收模拟身份，不推算页面访问或费用。

[验证矩阵](verification-matrix.md) · [开发指南](development.md)

## 按需研究流程（2026-09-12，已发布）

核心 `agent/AGENTS.md` 保留身份、目标/约束理解、事实、权限、研究范围及流程索引。第16个 MCP 工具 `read_chickenbro_skill` 只接受 mechanics、wcl-analysis、rankings、simc-experiment 四个名称，从同一 release 的固定文件读取不超过16KiB的UTF-8流程。返回正文与SHA-256版本；不接受路径或网络地址，不访问业务数据、不消耗来源/模拟预算。无匹配流程的简单问题不加载，相关复杂问题按需组合；读取失败不臆造流程。

核心规则授权内置流程作为下级操作指导；用户、网页及普通工具结果仍是不可信数据。既有15个工具、服务端身份和预算合同保持不变。安全观察记录仅保存技能名称与摘要，不把流程当成游戏事实。核心实际LF/CRLF加载与10KiB余量纳入后端测试，防止32KiB加载上限回归。语义效果以本批前后真实模型对照及线上记录为准，不能用文件缩短推算收益。

流程观察通过仅含规范化run UUID的run-identity.json绑定当前请求，验收先匹配run再读取，避免并发用户观察混入。运行源码2294cb95，证据见[本批记录](../artifacts/verification/2026-09-12-agent-skills/README.md)。

### 指定阶段状态

阶段场景通过 `initialState`、`measurement` 和 `assertions` 编译为 v7；默认开怪场景沿用现有编译版本。云端解析资源上限并校验每次迭代 t=0 快照，使用完整显式 APL，20–120 秒固定窗口、最多128次且共享任务时间预算。资源、Buff层数/时长及单充能冷却不符或断言失败时，任务不产生成功结果。统计包括总伤害（含宠物/守护者）、动作/Buff携带次数与资源溢出；聚合报告与中文身份重新绑定。Buff携带不等同实际增伤，隐藏触发历史、宠物/DoT起始状态和首领专属易伤未由此接口恢复。
