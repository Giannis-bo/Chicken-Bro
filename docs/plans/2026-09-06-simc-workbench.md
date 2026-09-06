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

- [ ] 1. 参数与 API：先写编译参数/拒绝非法类型/哈希差异测试；扩展 compiler、application 和 route；旧端字段保持不变；domain guards、API client、model 同步。主要文件 server/app/simulation/compiler.py、application.py、api/routes/simc.py、packages/domain/src/simc*.ts、packages/api-client/src/simc.ts。
- [ ] 2. 报告与版本：先写 JSON 语义、非有限值、actor 不匹配、旧文本兼容、临时输出和版本读取测试；实现 report.py、runtime.py、worker.py；使用真实云端 JSON 核对字段。
- [ ] 3. Web 工作台：拆分 WebSimcView、WebSimcReport 和专用 SCSS；新增配置控件、任务筛选、报告、版本和异常路径；DOM 测试验证提交参数、视图导航和报告降级；真实桌面与 390px 截图检查。
- [ ] 4. 集成：定向后端、全前端、控制面、typecheck、lint、H5/Mini 构建、git diff --check；本地 CR；隔离测试发布和云端语义模拟；记录 commit/build/runtime/数据库身份与回滚。用户体验验收单独等待。

## 验收与回滚

手工必验：独立任务入口、扩展配置真实生效、结构化报告、当前/历史版本、缺项与历史摘要、390px 布局、Mini/Web 同 owner 同一任务及 B 隔离。测试 release 原子切换，保留旧 release；回滚仅切回原测试链接并重启测试 API/Worker。无 schema 变更，无数据清理。

## 进度与决策

- 基线 3be4e6cb，隔离目录 `.worktrees/simc-workbench`，分支 `codex/simc-workbench`；原工作区干净且保留。
- 接口采用 opt-in 扩展，避免已发布 Mini 严格 response guard 拒绝新增字段。
