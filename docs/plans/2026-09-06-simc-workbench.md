# SimC 模拟工作台

状态：正在推进。2026-09-06 用户确认设计并授权实施。使用 writing-plans、TDD、subagent-driven-development 方法；本文件是唯一任务计划与进度记录。

## 已确认设计

Web 提供新建模拟、独立任务列表、完整结果报告。配置按角色来源、战斗、精度与增益分组；报告突出真实 DPS/HPS、误差、迭代、战斗时长，再展示技能贡献、Buff、资源、属性、装备天赋。页头显示当前云端引擎版本，报告保存任务运行版本。历史摘要如实降级；缺项、排队、运行、失败明确展示。保持 Mini/Web 共享 owner 和独立认证。先隔离测试环境，不合入 main 或生产切流。

## 实现合同

- 不新增依赖，不在本地安装或运行 SimC。复用当前测试分支和已安装云端 runtime。
- 参数：fightStyle 白名单 Patchwerk / HecticAddCleave / LightMovement / HeavyMovement；desiredTargets 1..20；iterations 1..10000；maxTime 30..600 秒；varyCombatLength 0..0.5；targetError 0..5%；raidBuffs 与 bloodlust 为 boolean。新增参数省略时保留旧规范化哈希和编译行为；显式提交时全部写入 profile 和 scenario hash。
- 新版 UI 使用 `view=workbench` 选择扩展 snapshot/job/list payload；省略时保持旧客户端精确字段合同。
- 扩展 snapshot 增加 character；扩展 job 增加 character、scenario、metric，详情 result 增加 report（旧记录为 null）。只有归属验证后的 application 数据可公开。
- Character: `{name:string,className:string,specialization:string,level:number|null,race:string}`。
- Scenario 为上述参数对象，旧任务无法恢复时 null。Metric 为 `{name:'dps'|'hps',value:number}` 或 null。
- `GET /api/v2/simc/runtime` 需已认证，返回 `{status:'available'|'unavailable',version:string|null,gameVersion:string|null,build:string|null,sourceCommit:string|null,runtimeRevision:string|null}`。版本来自校验后的实际二进制，禁止把 revision/hash 当版本。
- Report: `{schemaVersion:1,engine:{version:string|null,gameVersion:string|null,build:string|null},actor:Character & {talents:string|null},metric:{name:'dps'|'hps',value:number,error:number|null},statistics:{iterations:number|null,fightLengthSeconds:number|null,elapsedSeconds:number|null},abilities:Array<{name:string,amount:number,portion:number|null,executions:number|null,critPercent:number|null}>,buffs:Array<{name:string,uptime:number}>,resources:Array<{name:string,gained:number|null,lost:number|null}>,attributes:Array<{name:string,value:number}>,gear:Array<{slot:string,itemId:number,itemLevel:number|null}>}`。
- JSON 仅在 worker 私有临时目录输出，限制体积、字段/数组长度与有限数值，验证 actor、主指标正值及运行身份；归一报告写入现有 result_json.report，不增加数据库。

## 实施与验证

- [x] 1. 参数与 API：先写编译参数/拒绝非法类型/哈希差异测试；扩展 compiler、application 和 route；旧端字段保持不变；domain guards、API client、model 同步。主要文件 server/app/simulation/compiler.py、application.py、api/routes/simc.py、packages/domain/src/simc*.ts、packages/api-client/src/simc.ts。
- [x] 2. 报告与版本：先写 JSON 语义、非有限值、actor 不匹配、旧文本兼容、临时输出和版本读取测试；实现 report.py、runtime.py、worker.py；使用真实云端 JSON 核对字段。
- [x] 3. Web 工作台：拆分 WebSimcView、WebSimcReport 和专用 SCSS；新增配置控件、任务筛选、报告、版本和异常路径；DOM 测试验证提交参数、视图导航和报告降级；真实桌面与 390px 截图检查。
- [x] 4. 集成：定向后端、全前端、控制面、typecheck、lint、H5/Mini 构建、git diff --check；本地 CR；隔离测试发布和云端语义模拟；记录 commit/build/runtime/数据库身份与回滚。用户体验验收单独等待。

## 验收与回滚

手工必验：独立任务入口、扩展配置真实生效、结构化报告、当前/历史版本、缺项与历史摘要、390px 布局、Mini/Web 同 owner 同一任务及 B 隔离。测试 release 原子切换，保留旧 release；回滚仅切回原测试链接并重启测试 API/Worker。无 schema 变更，无数据清理。

## 进度与决策

- 基线 3be4e6cb，隔离目录 `.worktrees/simc-workbench`，分支 `codex/simc-workbench`；原工作区干净且保留。
- 接口采用 opt-in 扩展，避免已发布 Mini 严格 response guard 拒绝新增字段。

- 合并当前测试运行基线 5e4e7322，保留鸡哥研究与 SimC 工具更新；本轮扩展使用 compiler-v3，旧 v1/v2 队列可按原编译身份重放。
- 本地 CR 修正：时长整数校验、引擎信息失败重试、百分比统一单位与中文标签；审查复核通过。
- 测试站已更新至 `18b6597e`：365 后端、182 前端、62 控制面通过，typecheck/lint/H5/Mini 构建通过；保留原测试 release 与生产服务。
- 真实浏览器完成新建、列表、报告和旧任务误差回退检查；390px 无页面横向溢出，技能表独立横向滚动。
- 两次云端真实任务成功：`b5ec0ee3-8ed1-4569-bcba-e1eadf399778`（站桩）与 `602a14d1-fed5-48f2-9b7d-3e71bf63e112`（少量移动、3 目标、关闭团队增益和嗜血）。SimC 1210-01，游戏 12.1.0.69299，源码 f50a2121。
- Candidate 实测修正百分比浮点边界、compound 技能占比口径和历史 metricError 展示；不修改历史持久化数据。
- 下一步：用户测试验收，特别是真实 Mini/Web 同任务及第二用户隔离。本轮不代表用户验收、main 合入或生产切流。

- 2026-09-06 用户要求：游戏术语全部使用国服译名，不显示英文。沿用本任务测试发布范围；共享中文术语层覆盖网页和小程序，技能/增益名称按当前引擎法术编号与国服数据核对。未核实名称显示带序号的中文待收录提示，不猜译、不把内部英文标识当名称。保留真实角色名、导入代码和审计标识。
- 国服术语版 `98cdb259` 已发布测试站；193 前端、62 控制面、类型/lint、双端构建通过。两份现有报告译名覆盖为零缺项；实际浏览器技能/增益无英文且数值保持一致，390px 无页面溢出。后端仍为 `18b6597e`，105 个原有非网页文件逐字节保持。

- 2026-09-06 用户要求在角色来源下展示两条合法链接示例。角色评分使用用户提供的 Giannis－白银之手链接；战斗日志通过真实角色接口核实报告 `CPGWvnJ2t9QMRrA1`、战斗 `1`、角色 `4`。本次仅增加明确可打开的示例文案，不改变来源解析或模拟行为。
- 合法链接示例版 `84ccd5d3` 已更新测试站；两条链接通过当前来源解析，22 项工作台测试、类型检查、lint 和网页构建通过；桌面及 390px 实测完整显示，窄屏自动换行。后端及生产服务保持原有身份。

- 2026-09-06 用户导入反馈：客户端遗漏国服战斗日志域名，已用查询参数和片段参数两条回归测试复现；修复共享客户端白名单。云端真实读取确认角色评分缺等级，当前战斗日志适配器返回缺等级、种族、装备、天赋；链接示例补充完整性说明，不把链接有效等同可模拟，不编造字段。

- 2026-09-06 用户明确要求以 Giannis 的角色评分和战斗日志链接完成实际导入、云端模拟；遇到阻塞明确反馈。实施：详细角色接口验证地区/服务器/角色/职业后补齐等级和种族；战斗日志读取指定战斗/角色的战斗员事件，保留当场装备附魔宝石，天赋与同角色导出代码逐节点核对一致才采用；不一致保持阻塞。来源和补齐字段写入 provenance，测试站分别从页面运行两个真实任务。
- 最终导入修复：后端 `c78761b8`、网页 `e4a4326e`；372 后端、199 前端、类型/lint、双端构建通过。实际页面分别提交 Giannis 角色评分任务 `b1807708-ad52-48f7-adcd-4d501f5d2f20`（每秒伤害 225950.24）和战斗日志任务 `7e2c4903-6de4-4049-a0f6-ea7f36118af3`（每秒伤害 227723.91），报告语义有效，配置哈希一致，两个完成任务在任务入口可见。完整日志导入曾触发客户端默认 6 秒超时，已将仅来源读取的等待上限调整为 60 秒并用原始片段链接复测通过。其他日志若与同角色当前天赋导出不一致，继续如实阻塞；不使用当前天赋代替当场配置。

- 2026-09-06 用户要求：识别到非法链接时明确标记非法，并引导参考示例。网页非法链接提示明确区分格式/来源不支持，并指向输入框下方两条示例；不改变合法但资料缺失、权限受限或网络错误的分类。

- 2026-09-06 用户要求移除截图红框小字：网页品牌下方的英文副标题，以及历史对话下方的“服务端同步”。同步移除登录页相同品牌副标题；其余内容保持原有行为。

- 2026-09-06 用户明确指定来源输入提示为“仅接收 Raider.IO 或者 WCL 的合法链接，请参考示例”，并移除示例区域前的资料完整性说明；保留两条示例和实际错误提示。

- 2026-09-06 用户反馈回答过程中切到模拟页会中断回答。根因是主标签条件渲染卸载对话组件，触发 ChatModel.dispose 取消请求。改为已访问页面保持挂载、仅切换可见性；模拟页首次访问才加载。验证等待首字、输出中反复切换、隐藏时完成、模拟草稿保留，以及退出整个登录工作区时仍取消请求。沿用隔离测试网页发布范围。
