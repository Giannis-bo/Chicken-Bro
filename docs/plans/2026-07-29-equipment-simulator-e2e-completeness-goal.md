# 装备模拟端到端完整性验证 Goal

**状态：** 正在推进

**Harness 分级：** Strict，多阶段 Goal；每个会改变数据、Catalog、运行时或发布状态的切片必须使用自己的唯一 task-scoped release packet。
**用户目标：** 玩家在真实微信小程序中浏览、导入、编辑、保存并模拟当前赛季 PVE 装备时，看到的是完整、合法、可追溯且可执行的后端事实；不能漏装备，不能把 `partial` / `blocked` 包装成通过，也不能靠视图绕过上游问题。

## 1. 当前事实

- generation 35 和 Phase 0-4 是已归档 v1 基线，不是本 Goal 的当前验收证据。
- 当前 `manifest-catalog-detail-contract` 仍是 Catalog Browse 纠偏切片；其旧候选、微信包和 evidence 绑定 `da051891`，不能证明后续 `d1006712` 及其之后的源码。
- 现有 40 专精 shadow 从同一 Catalog 投影 public candidates，只能证明集合内部映射自洽，不能证明官方当前赛季 PVE 来源宇宙没有漏 instance、encounter、difficulty 或 item。
- Journal 摄取存在 instance、raid、encounter、item 容量上限；当前没有逐项记录所有因容量、失败或 fallback 未进入 staging 的关系。
- 云服务器根盘曾达到 92%，违反目标架构 `<= 80%` 的候选硬门槛。日志输出上游修复、受控轮转/压缩、journal vacuum 和精确保留清理后已复核为 79%；历史 PostgreSQL/SQLite 备份保留。新候选仍须在每次启动前重新通过同一门槛。
- 当前候选链的自动化回归可作为诊断和修复证据，但真实微信验收必须重新绑定最终同一不可变候选。

## 2. 用户可见完成标准

1. 玩家选择任意一个 40 专精，合法槽位都能看到本赛季实际可获得且适配该专精的完整 PVE 候选。
2. 每件候选的名称、图标、来源、难度、装备类型、进度状态、装等、静态属性和可强化能力都来自匹配的后端 Catalog / Exact / Enhancement 证据。
3. 普通 Browse 只显示 governed maximum-rank progression；制造品质和虚空晋升保持独立 canonical progression；低 rank 玩家实装只能保留在 Exact。
4. 社区或个人 Exact 导入保留真实 bonus、宝石、附魔、制造副属性和美化，不会为了进入 Browse 而改写身份；缺证据时明确阻断。
5. Apply 后必须经过 canonical Resolve；ready ResolvedLoadout 才能编译和提交 SimC。26 个支持专精产生真实终态结果，14 个不支持专精在执行前按策略阻断。
6. 微信 DevTools / Computer Use 中的真实操作覆盖完整交叉矩阵，不以法师或一两个样本外推全量结论。

## 3. 当前赛季 PVE 宇宙合同

建立不可变 `SeasonPveUniverseRevision`，其 identity 至少绑定：

- `seasonRevision` 与 source-policy revision；
- 每个 `sourceType + instanceId`；
- 每个 `instanceId + encounterId + difficultyKey`；
- 每个来源关系下的 `itemId`；
- authority、抓取时间、原始 evidence reference、fetch/cap/fallback 状态；
- universe 内容 hash 与生成器 revision。

每个 universe member 必须且只能落入以下一个终态：

- `included`：可追到 staging item/source/variant、Catalog ItemDefinition/BrowseVariant、专精 eligibility 与 Resolve；
- `excluded`：逐项记录稳定 `reasonCode`、事实 owner、evidenceRef、时间和治理决定；
- `blocked`：上游证据缺失或冲突，明确阻断候选和发布。

聚合计数、HTTP 200、40/40 spec 数量、zero-unmapped 或“至少一个候选”都不能代替这个一对一 partition。

## 4. 执行切片

### Slice A — 收敛当前 Catalog correction

- 修正 current-HEAD 与 requirement/evidence/微信包身份漂移。
- 让 public verified-detail 与 replacement visibility 同时校验真实 Catalog Browse provenance。
- 用真实代码回归覆盖 exact-only import → Exact authority → Resolve → ResolvedLoadout → canonical SimC compiler，且不创建 Browse membership。
- 运行本地相邻回归和 CR；服务器资源门槛已恢复，但 dormant/read-only 证据仍不能代替当前不可变候选和 Universe 闭包。

### Slice B — Universe authority 与只读差集

- 从官方当前赛季 PVE 来源策略建立 universe revision。
- 把摄取 caps、分页、fetch failure、fallback 和未映射关系变成 machine-readable omission ledger。
- 输出 universe → Journal → staging → Gear Release → Catalog 的逐项差集；本切片不因发现缺口而静默过滤。
- 若需要下载数据文件、安装依赖或改变外部数据源，先遵守仓库 Network / Download Approval。

### Slice C — 上游修复与 dormant Catalog

- 按实际 owner 修复 source discovery、ingestion、staging、静态事实、类型、progression 或 authority mapping。
- 每个修复先有失败回归，再做最小实现；不得在 Taro 中推断或补写装备事实。
- universe 差集归零或每条获得治理性 exclusion 后，才构建 dormant Catalog / Exact / Manifest dependency vector。

### Slice D — 资源受控不可变候选

- [x] 候选前根盘恢复为 79%，保留 active + rollback、当前/上一版 SimC 和数据库备份；每个新 candidate/temp workset 仍须重新预测并满足 `<= 80%` 与显式 reserve。
- 启动时 `MemAvailable >= 2 GiB`，运行中不得低于 512 MiB。
- 同时只运行一个资源密集型候选操作；生产 backend 保持在线；sync/backfill/collector 和非必要 SimC job 关闭。
- 候选使用 `MemoryHigh=1G`、`MemoryMax=1280M` 的声明预算；持续超过 1 GiB 或瞬时超过 1152 MiB 时停止并保留诊断。
- 始终使用 `WOW_DEPLOY_START_ASYNC_SYNCS=0`；记录 commit/tree/file parity、active pointer 前后、PG rollback、timer/backflow 与 cgroup current/peak。
- 历史数据库在没有 checksum backup + 独立 restore/read-back 之前只保留，不执行 drop、truncate、vacuum full 或文件删除。

### Slice E — 自动化全矩阵

自动化证据必须覆盖并持久化每一行结果：

- 40 专精 × 合法槽位 × universe item × progression eligibility；
- 每个 expected relation 的 visible / rule-excluded / governance-excluded / blocked 终态；
- Catalog / Exact / Enhancement / ResolvedLoadout revision parity；
- 普通、制造、虚空、套装、饰品、武器/副手、双戒/双饰品和合法空副手边界；
- 跨职业 armor/weapon proficiency、主属性、unique-equipped、插槽、附魔、美化和制造副属性；
- 26 支持专精真实 SimC 终态与 14 不支持专精前置阻断；
- 任一错误沿 `UI → public payload → PG read model → Catalog/Exact → staging → source universe` 追到 owner 和根因。

### Slice F — 真实微信全矩阵

- 构建产物的 source hash、Git commit/tree、后端 API base 和 Manifest dependency vector 必须绑定同一不可变候选。
- 使用现有微信 DevTools 进程、`miniprogram-automator` 和必要的 Computer Use；不自动安装 DevTools，不把截图或接口 smoke 冒充人工验收。
- 全部 40 专精逐一进入装备模拟，遍历每个合法槽位和返回候选；对每个 expected item/progression relation 实际打开详情并核对显示/可选状态。
- 每个专精至少完成一次跨槽换装、Apply、Resolve、保存、重载和异常恢复；Exact/强化使用跨职业、跨护甲、跨武器类型的完整类别矩阵。
- 26/14 SimC 路径逐项验证任务提交或前置阻断、任务列表、详情终态、重试/返回路径。
- 自动化可执行的 DevTools 操作全量执行；Computer Use 负责真实点击、输入、回退、滚动、选中态和异常状态复核。任何 route crash、空列表、旧包、请求失败或状态不一致都回到上游根因。
- 结果 ledger 至少记录 class/spec/slot/item/progression/action/assertion/status/runtime identity；少量样本不能获得全量通过结论。

## 5. 停止线

- universe 未形成一对一 inclusion/exclusion/blocked 闭包；
- 任何来源、难度、物品因 cap/fetch/fallback 静默丢失；
- Catalog/Exact/Manifest/微信包 revision 不一致；
- 云盘、内存、cgroup 或生产健康超过预算；
- 真实微信未覆盖完整 40 专精交叉矩阵；
- 只得到 API/test/build 通过，没有同一候选的 DevTools 实际操作证据；
- `partial`、`blocked`、`stale` 被改写成成功；
- 需要破坏性清理、外部下载或依赖安装但尚未获得对应授权。

## 6. Harness 关闭

每个改变运行态的切片必须经过当前 requirement、targeted tests、local CR、唯一 task packet、不可变候选、回滚证据和 CI。最终 Goal 只有在：

1. universe completeness closure 通过；
2. 自动化全矩阵通过；
3. 同一最终候选的真实微信全矩阵通过；
4. 用户给出明确的 post-test acceptance；
5. merge、production、local/origin/cloud parity 与清理完成；

之后才能标记完成。
