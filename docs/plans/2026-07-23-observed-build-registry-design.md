# Observed Build Registry 与 TemplateSet 架构设计

状态：正在推进
分类：Strict
确认日期：2026-07-23
共享玩家合同确认：2026-07-23

当前实施入口：[Observed Build Registry Core Implementation Plan](2026-07-23-observed-build-registry-core-implementation.md)

当前事实：[project-state.json](../project-state.json)、[roadmap.md](../roadmap.md)、[Harness](../harness.md)、[职业构筑架构](../builds-architecture.md)、[社区模板 Runbook](../community-template-import-full-chain-runbook.md)、[装备模拟 Runbook](../gear-simulation-full-chain-runbook.md)、[天赋模拟 Runbook](../talent-simulation-full-chain-runbook.md)、[SimC 全链路](../simulator-simc-end-to-end.md)

## 设计结论

Raider.IO 玩家数据不再直接推动天赋、装备、Community Release、Manifest 和 SimC 的整条发布链。系统先把真实玩家观测事实保存为不可变、可追溯、可重放的 `ObservedBuildSnapshot`，再由一个后端 `Projection Compiler` 对当前 Talent Catalog、Gear Release、规则和 serializer dependency vector 编译出天赋与装备 canonical projection。公开模板只引用已验证 projection；每日发布物是一份包含 80 个 class/spec/hero/scenario 槽位引用的 `TemplateSet`，通过单一活动指针原子切换。

这 80 个槽位同时是唯一玩家事实集：40 个职业专精各有两个 Hero 槽，每槽绑定一位真实玩家，同一专精的两个槽必须具有不同的 `sourceIdentity`。天赋模拟按 Hero 槽读取一份天赋 projection；装备模拟把同一专精的两个 Hero 槽投影为两份装备模板。天赋和装备不得分别选人，也不得在装备映射失败时改用另一位玩家。

现有 canonical resolver、talent authority、PG-only runtime、observed-only public policy、exact-ID community import、async stat snapshot 和 SimC task runner继续保留。设计不引入微服务、event sourcing、通用 DSL、通用 Claim DAG 或运行时读接口同步。

## 用户结果与可信承诺

玩家在天赋模拟和装备模拟中看到的是同一批真实高端玩家来源经过当前本地 authority 映射后的模板：

- 任意职业专精的装备模拟固定展示两个真实角色模板，严格对应这个专精两个 Hero 槽的两位玩家。
- 任意职业、专精、Hero 组合的天赋模拟固定展示一个真实角色模板。
- 同一 Hero 槽的天赋与装备必须绑定同一个 `snapshotId/sourceIdentity`，并且都可通过现有 exact import 合同导入。
- 模板明确展示玩家、服务器、区域、Hero、场景、来源时间和新鲜度。
- Rank 1 玩家从 A 变为 B，且 B 通过来源、映射、合法性和完整性门禁后，系统可以自动发布 B。
- 新快照的天赋或装备任一 projection 无法映射或校验时，不做半槽切换；同一槽位的天赋和装备共同继续使用最近一次已验证模板，并标记为过期或“新 winner 待验证”。
- 没有历史可用模板时显示 `pending_collection`，不使用 baseline、其他 Hero、其他专精或匿名数据补位。
- 模板可导入、可生成合法 SimC profile，不等于已完成战斗模拟、DPS 验证或 BiS 证明。
- 完整战斗 SimC 只在玩家发起任务时运行；每日模板刷新不批量运行 80 份战斗模拟。

## 当前问题

当前 `sync_community_template_cache_postgres()` 同时编排来源采集、天赋候选、winner promotion、精确角色补抓、observed gear backfill、模板物化、cleanup、coverage 和 sync-state。随后 Community Release 构建又把玩家快照、天赋排序、装备合法性、Gear Release dependency 和候选预览绑定在一起。

这不是某个单独函数的错误。各个安全门禁本身大多合理，问题是它们缺少一个稳定中间对象，导致不同变化频率被迫共用一条发布链：

| 变化时钟 | 正常频率 | 当前应有职责 |
| --- | --- | --- |
| 玩家来源 | 每日或来源变化时 | 采集、去重、保存观测事实 |
| Catalog / 规则 / serializer | 赛季、热修或代码发布时 | 对已有 snapshot 重放 projection |
| SimC 执行 | 玩家请求或明确验证任务时 | 运行战斗模拟并保存任务结果 |

玩家来源失败不应触发 catalog 重发；catalog 补齐也不应要求重新访问 Raider.IO；模板刷新更不应自动运行完整 SimC。

## 方案比较

### 方案 A：只拆分现有同步函数

把现有总编排拆为几个 stage，但继续使用 mutable staging、完整 Community Release 和 Manifest 绑定。

- 优点：迁移最小。
- 缺点：数据生命周期和发布粒度不变；一个来源问题仍会放大为整条发布问题。
- 结论：可改善代码可读性，但不能解决主要运维摩擦，不采用为目标架构。

### 方案 B：Snapshot Registry + Projection Compiler + TemplateSet

保存内容寻址的玩家快照；按 dependency vector 编译 canonical projection；TemplateSet 只保存 80 个槽位引用和状态。

- 优点：可重放、可局部更新、可复用 LKG、来源与 authority 解耦、原子读取和回滚仍然成立。
- 缺点：需要 additive PostgreSQL schema、shadow compiler、双读对比和一次受控切换。
- 结论：采用。

### 方案 C：API 请求时直接转换 Raider.IO payload

- 优点：表面路径最短。
- 缺点：读时计算、无法重放历史、依赖漂移、容易绕过 resolver 和发布门禁。
- 结论：拒绝。

## 目标架构

```text
Raider.IO discovery/profile
  -> ObservedBuildSnapshot Registry
  -> winner election by class/spec/hero/scenario
  -> Projection Compiler
       -> TalentProjection
       -> GearSelectionProjection
       -> profile readiness / structured problems
  -> 80-slot TemplateSet builder
       -> valid new projection
       -> same-slot LKG carry-forward
       -> pending_collection when no LKG
  -> validation
  -> atomic active TemplateSet pointer
  -> talents/gear read models
  -> exact import
  -> canonical profile
  -> on-demand stat snapshot / SimC task
```

实现保持为现有 Python/PostgreSQL modular monolith。网络采集、纯 projection、PG repository、public read model 和 SimC execution 各有一个明确 owner，不新增独立服务边界。

## 核心组件与所有权

### Observed Snapshot Collector

只拥有 Raider.IO discovery/profile 访问、来源身份校验、请求预算、重试、时间窗口和观测事实保存。它不拥有天赋规则、装备属性、winner 公开状态、TemplateSet pointer 或 SimC。

`ObservedBuildSnapshot` 至少绑定：

- `sourceIdentity`、profile URL、region、realm、character；
- class/spec/scenario 与来源 ranking evidence；
- talent loadout/import evidence；
- observed item、bonus、gem、enchant、embellishment 输入；
- `profileHash`、`talentHash`、`gearHash`、`fetchedAt`、source revision。

内容 hash 未变化时复用已有 snapshot，只记录本次来源检查结果，不创建新 projection 或 TemplateSet。任何被活动或 rollback TemplateSet 引用的 snapshot 必须保留；未引用历史的清理周期不是首版切换条件。

### Winner Election 与共享槽位

election 继续拥有 `(classKey, specKey, heroKey, scenarioKey)` 的候选顺序和 winner 身份。一个槽位的发布单元不是独立天赋或独立装备，而是同一个玩家 snapshot 的 `TalentProjection + GearProjection` 组合。装备合法性不得回写或重新排序 winner；如果新 winner 的装备无法投影，不允许装备侧改选其他玩家，也不允许只发布新天赋。

Rank 1 从 A 变为 B 属于 `winnerChanged`。当 dependency vector 未变化且 B 的天赋、装备 projection 全部门禁通过时，它是低风险 observed-only 更新，允许自动进入新 TemplateSet。任一 projection 未通过时记录结构化 problem，并让天赋和装备共同继续引用 A 的同槽 LKG。

### Projection Compiler

输入是一个不可变 snapshot、目标槽位和完整 dependency vector；输出是不可变 projection 或结构化阻断。相同输入必须得到相同结果。

天赋 projection：

- 只复用当前 backend talent authority、节点、choice、edge、point gate 和 encoder；
- raw external code 无法可视化映射时保留 SimC-only 边界，不伪造成可编辑节点；
- 输出 canonical talent state、encoding、readiness、blockers 和 signature。

装备 projection：

- 以 observed `itemId/bonus/gem/enchant/embellishment` 作为选择事实；
- item、variant、属性、槽位、职业限制和 SimC option 全部从当前 Gear Release/Resolver authority 解析；
- Raider.IO 不提供生产属性真值；
- 输出 canonical Selection Intent、resolved signature、readiness、adoption/problems 和 dependency vector。

Projection Compiler 只做确定性映射、合法性和 serializer/profile readiness 检查，不运行完整战斗 SimC。

### TemplateSet Builder

每天扫描完成后构建一个完整的 80 槽候选集合：

1. 新 winner/new snapshot 的 talent 和 gear projection 都 verified：同槽共同引用新 snapshot 与两份新 projection。
2. 任一新 projection blocked 且同槽存在 LKG：天赋和装备共同引用 LKG，槽状态为 `stale_lkg`，保存新 problem 摘要。
3. 任一新 projection blocked 且没有 LKG：槽状态为 `pending_collection`，天赋和装备都不提供可导入模板。
4. 只有 `checkedAt` 变化：复用现有 projection；若 80 个槽的引用、状态和 dependency vector 都未变化，不创建新 TemplateSet。

TemplateSet 保存内容 hash、generation、80 槽引用、每槽状态、dependency vector、source run 和 rollback set。它不复制完整 gear catalog、talent graph 或原始玩家 payload。

内部候选的“80 槽结构完整性”要求每个预期槽都有唯一、结构合法的 entry；`stale_lkg` 和 `pending_collection` 都必须诚实保留，不能用假模板补位。首次公开切换还必须满足更严格的 `80/80 ready`：80 个槽全部具有可导入的 talent 与 gear projection。首次切换后，新的活动 TemplateSet 可以用同槽 `stale_lkg` 承接失败槽并更新其他 79 槽，但任何 `pending_collection`、缺少 entry、重复槽、跨槽 LKG 或无效 projection 引用都会阻断活动指针切换。

公开 read model 由同一份 active TemplateSet 确定性派生：

- 天赋 read model：80 个 Hero 槽各输出一个真实玩家模板。
- 装备 read model：按 class/spec 分组同一份 80 槽，每个专精恰好输出两个带 Hero 身份且 `sourceIdentity` 不同的真实玩家模板。
- 两个 read model 都携带相同的 `templateSetId`、`snapshotId`、`sourceIdentity`、玩家来源与 freshness；前端不参与选人、配对或 LKG 判断。

### Publication Policy

发布分两类：

| 类型 | 条件 | 发布方式 |
| --- | --- | --- |
| 首次公开切换 | 80/80 槽都具有同玩家绑定的可导入 talent 与 gear projection；Catalog、规则、schema、serializer dependency 已冻结；候选和微信 smoke 通过 | 人工批准后 CAS 切换 active TemplateSet pointer |
| observed-only 自动刷新 | 只有玩家 snapshot/winner 变化；Catalog、规则、schema、serializer、SimC revision 均未变化；80 槽全部可导入，失败槽使用同槽 LKG 且没有 pending | 自动 CAS 切换 active TemplateSet pointer |
| dependency cutover | Gear/Talent Catalog、规则、schema、serializer、SimC runtime 任一 revision 变化 | 受控 candidate、shadow compare、人工批准后切换 |

TemplateSet 构建、内容 hash、槽位唯一性、dependency binding 或 rollback target 任一失败时，不切换指针。回滚只切回上一个 TemplateSet，不重写 snapshot、projection 或 catalog。

## 属性与 SimC 边界

每日刷新允许：

- 本地 canonical 静态属性解释；
- talent/gear serializer dry-run；
- profile readiness；
- 已有 immutable stat snapshot 的签名复用。

每日刷新不允许：

- 为 80 个模板运行完整战斗 SimC；
- 根据一次 SimC 数字重新选举社区 winner；
- 把 `profileReadiness=ready` 表述成 DPS 已验证；
- 把 observed 模板表述成 BiS 或推荐最优。

玩家提交模拟时，backend 从 exact projection 重新加载当前 authority，生成 canonical profile，再进入现有 SimC task runner。属性快照只在完整签名变化且缓存未命中时异步生成；旧 snapshot 只读 stale，不能覆盖新请求。

## 失败和降级语义

| 失败 | 公开行为 | 运维行为 |
| --- | --- | --- |
| Raider.IO 整体不可用 | active TemplateSet 不变；现有模板按 freshness 规则变 stale | 记录 source failure，不触发 catalog/release 重建 |
| 新 winner B 抓取失败 | 继续使用 A 的同槽 LKG | `winner_changed_capture_blocked` |
| B 抓取成功但无法映射 | 继续使用 A 的同槽 LKG | 保存 projection problems，可在 catalog 补齐后本地重放 |
| 没有 LKG | 该槽 `pending_collection`，不可导入 | 其他槽继续构建 |
| 单槽异常导致 set 不完整或引用错误 | 不切 active pointer | 候选 set 保留诊断 |
| dependency revision 变化 | 不自动发布 | candidate/shadow/人工 cutover |
| SimC task 失败 | 模板仍可保留为可导入、profile-ready；不得展示 DPS | 任务明确 failed/blocked |

## Health 与 Admin

Health 不再用一个 `80/80` 掩盖不同状态，至少分别暴露：

- source checked / unchanged / changed / failed；
- winner unchanged / changed；
- projection reused / compiled / verified / blocked；
- LKG carried / pending collection；
- candidate TemplateSet created / no-op / blocked；
- active generation、rollback generation 和 dependency vector；
- stale slot count、pending slot count、代表性 problem 和 next action。

Read API 和 health 都只读，不触发采集、projection、SimC 或 pointer 切换。日志只保留 bounded/redacted source identity，公开 payload 不泄露内部诊断或完整原始玩家响应。

## Impact Map

| 分类 | 联动面 |
| --- | --- |
| `must_change` | snapshot/repository schema、community sync orchestration、projection repository/compiler adapter、TemplateSet store/pointer、public template reader、health/admin、release refresh |
| `must_not_change` | talent authority、canonical gear Resolver、PG-only runtime、observed-only public policy、exact community import、个人模板 owner、SimC task runner、前端 consumer-only |
| `risk_unknown` | 现有 Raider.IO payload 对 80 槽的完整 snapshot 输入覆盖；历史 active Community Release 到 snapshot/projection 的可逆回灌；enhancement/variant alias 的 shadow parity |
| `evidence_required` | deterministic replay、80 槽 LKG matrix、old/new API parity、exact import/profile parity、atomic pointer/rollback、source outage、dependency drift、candidate/live smoke |

工程健康目标是停止向 `server/postgres_cache_sync.py`、`server/postgres_cache_store.py`、`server/websim_payload.py` 和 `server/gear_release_store.py` 增加新的跨域判断。热点文件只保留 adapter/delegation；新领域判断进入小型纯模块和有界 repository。

## 迁移策略

迁移采用 strangler，不推倒当前 active Release：

1. **Characterization**：冻结现有 80 槽、exact import、profile readiness、LKG/freshness 和 public observed-only golden。
2. **Additive registry**：增加 snapshot、projection、TemplateSet 和 pointer 表；不改公开 reader。
3. **Backfill without network**：从现有 PG Raider.IO cache、talent winner 和 observed gear rows 回灌 snapshot。
4. **Shadow compile**：先 Mage/Elemental，再扩到 80 槽；逐项比较 source identity、talent state、Selection Intent、enhancements、signatures、readiness 和 problems。
5. **Candidate reader**：候选环境读取 TemplateSet；现有天赋与装备 API 合同保持不变，正式 active Community Release 仍是 LKG。
6. **Controlled 80-slot collection**：使用已获批准的云端项目采集器访问 Raider.IO，把 40 个专精的两个 Hero 槽收敛为 80 个共享玩家 snapshot；只保存真实来源事实，不用 baseline 或跨槽数据填洞。
7. **Controlled first cutover**：只有 80/80 槽同时具备可导入 talent 与 gear projection，并通过完整 Harness evidence、候选 API/import smoke、rollback drill 后，才切 TemplateSet pointer。
8. **WeChat handoff**：从最新主干执行 `npm run refresh:weapp`，确认构建和微信开发者工具实际打开后，交给用户逐页验证。
9. **Compatibility retirement**：证明没有 caller 后，再移除 `gearProjectionCandidates` 跨域承载、重复 observed template 物化和旧 Community Release public reader。

现有装备投影 WIP 可以作为 characterization 和 backfill 输入，但不继续扩大 `sync_community_template_cache_postgres()` 的领域职责。

## 验证与验收

自动验证必须覆盖：

- snapshot hash 去重和 unchanged no-op；
- 相同 snapshot + dependency vector 的 deterministic replay；
- A 同一玩家构筑变化；
- Rank 1 A -> B 自动切换；
- B capture/mapping/legality 失败时 A LKG 保留；
- 无 LKG 时单槽 pending、其他 79 槽正常更新；
- 同槽 talent/gear 必须共享 `snapshotId/sourceIdentity`，任何半槽更新都被拒绝；
- 同一专精两个 Hero 槽的 `sourceIdentity` 必须不同；
- 80 槽唯一性、完整引用、content hash 和 CAS 原子性；
- 首次切换必须 `80/80 ready`，后续失败槽只能使用同槽 LKG；
- 天赋 read model 为 80 个槽各一个模板，装备 read model 为 40 个专精各两个模板；
- dependency drift 禁止自动 promotion；
- catalog 补齐后不访问 Raider.IO 即可重放 blocked snapshot；
- exact talent/gear import、canonical profile 和现有 public contract parity；
- source outage、并发刷新、重复运行、失败重试和 rollback；
- read API/health 零写入、零外部访问、零 SimC；
- 每日扫描不运行完整战斗 SimC。

候选证据至少包含 exact commit/tree、migration/backup、snapshot/projection/TemplateSet counts、80 槽状态矩阵、40 专精装备双模板矩阵、同玩家关联审计、old/new shadow diff、80 个 talent import contract、80 个 gear import contract、代表性 canonical profile、timer/backflow、health/admin、pointer rollback 和真实微信关键路径。

用户侧完成标准：

- 任意专精的装备页都显示两个社区模板，来源、玩家和 Hero 身份清楚，且两个模板都可导入；
- 任意职业、专精、Hero 的天赋页都显示一个对应玩家模板，且可导入；
- 同一个 Hero 槽的天赋与装备可以核对为同一个玩家快照；
- 新 winner 自动更新后可导入；
- 新 winner 失败时旧模板仍可用并显示过期/待验证；
- pending 槽不出现假模板；
- 天赋/装备导入后可进入 SimC 确认；
- 未实际运行 SimC 时不显示 DPS 或“已模拟”承诺。

## 非目标

- 不做 BiS optimizer、推荐评分或自动 DPS 排名。
- 不改变坦克、治疗、增辉目标函数。
- 不让前端参与 winner、LKG、合法性或 freshness 判断。
- 不在首版设计 snapshot 的长期归档/冷存储平台。
- 不借重构开启 Catalyst、全量 stat-weight 重算或新的外部来源。
- 不把本设计文档视为实施授权；实施必须另写 Harness plan 并通过用户审阅。
