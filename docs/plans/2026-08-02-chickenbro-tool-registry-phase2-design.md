# 炸鸡队长能力演化 Phase 2：Tool Registry 设计

状态：`正在推进（本地实现完成，等待候选验证）`
分类：`Strict`
确认日期：2026-08-02

本设计落实[能力演化控制面总设计](2026-08-02-chickenbro-capability-evolution-design.md)的 Phase 2。Phase 1 的 Trace、Outcome 与离线 Eval 已归档；本阶段只把现有 Raider.IO 与 Warcraft Logs 来源 Tool 从固定分支迁移到版本化 Registry，不制造新 Tool，不授权后续 Gap、Toolsmith、shadow、canary 或自动 promotion。

当前事实入口：[project-state.json](../project-state.json)、[roadmap.md](../roadmap.md)、[plans/README.md](README.md)、[Phase 1 证据](../../artifacts/releases/2026-08-02-chickenbro-observability-phase1/evidence.json)、[Phase 2 证据](../../artifacts/releases/2026-08-02-chickenbro-tool-registry-phase2/evidence.json)、[Harness](../harness.md)、[验证矩阵](../verification-matrix.md)

## 需求合同

玩家继续用自然语言提问，不需要选择工具或理解 Registry。对于职业构筑问题，队长仍只在有明确职业/专精时读取 Raider.IO；对于包含公开 WCL 报告链接的问题，仍只调用 Warcraft Logs。回答结构、证据校验、数字白名单、owner 隔离和失败提示保持不变。

P2 的用户价值不在于立刻增加知识面，而在于让“可使用哪些能力、使用哪个版本、为什么被发现、实际调用了什么”成为可验证事实。完成后，部署方可以通过不可变 Registry Release 控制已发布能力，Runtime 不再依赖 `if/else` 固定 Tool 列表，后续阶段才能安全地产生和评估候选能力。

## 当前问题

- `server/news_backend.py::load_chickenbro_source_tool_results` 直接按 intent 分支调用两个 Tool；
- `server/chickenbro_observability.py` 把 capability ID 和 `fixed_allowlist` 写死在 Trace validator；
- Tool 的输入、输出、owner、来源、新鲜度、超时和副作用合同没有统一 manifest；
- 当前代码无法表达一组原子发布的 Tool 版本，也无法区分“发现”与“实际执行”；
- 直接把自然语言描述或数据库中的任意 implementation reference 变成可执行代码，会扩大到任意代码执行和自发布风险。

## 反方质疑

当前只有两个 Tool，建立 Registry 会增加 Schema、store、缓存和迁移复杂度，却不会自动提高回答正确率。若 Registry 仍由代码常量决定，它只是换了位置的 allowlist；若让数据库保存任意 Python 引用并动态加载，又会把配置面升级成远程代码执行面。

因此 P2 只有在以下条件同时成立时才值得实施：

1. Manifest 和 Release 是可审计、不可变、原子读取的生产事实；
2. 发现由数据驱动，但执行仍绑定仓库内已批准 adapter；
3. 旧固定分支被真正删除，Trace 能证明 Registry 版本、发现集合和实际调用集合；
4. Registry 失效不会静默回退或扩大 Tool 权限；
5. 首批范围严格限制为已经存在并通过 P1 证据链验证的两个 Tool。

## 方案比较

| 方案 | 收益 | 风险 | 结论 |
| --- | --- | --- | --- |
| 仓库 JSON/YAML Manifest | 实现最小、Git 可审计 | 运行时仍随代码发布，不能形成原子 Registry Release，也不能为后续 promoter 提供控制面 | 不采用 |
| PostgreSQL 不可变 Manifest + Registry Release，执行绑定仓库 adapter | 发现、版本、状态和发布身份可审计；不开放任意代码；可为后续阶段复用 | 需要 migration、Ops store、缓存和兼容 Trace | 采用 |
| 独立 Registry 服务或数据库动态加载任意 implementationRef | 远程扩展最灵活 | 新服务、凭据、网络故障面和远程代码执行风险远超当前收益 | 不采用 |

## 目标架构

```text
message + owner-bound context + history
  -> classify RequestIntent
  -> load verified active Registry Release
  -> deterministic discovery
       -> discovered capability refs
       -> selected capability refs
  -> backend argument validation
  -> repository-owned adapter execution
  -> existing ToolResult / evidence validation
  -> unchanged model answer schema
  -> Trace v2(registry release + discovered + selected + status)
```

### 组件职责

| 组件 | 职责 | 禁止事项 |
| --- | --- | --- |
| `server/chickenbro_registry.py` | 纯函数校验 Manifest/Release、内容哈希和结构化 discovery | 不连数据库、不执行 Tool、不读取用户原文 |
| `server/postgres_ops_store.py` | 原子读取 active Registry Release 与引用的 manifests | 不解释自然语言、不决定 Tool 参数 |
| `server/chickenbro_tool_runtime.py` | 把已选择 manifest 绑定到仓库内 adapter，校验参数并执行 | 不动态 import 数据库提供的模块、不接受任意 URL/SQL/Shell |
| `server/news_backend.py` | 形成 RequestIntent、加载 Registry、编排 ToolResult 与现有回答链 | 不再保留固定 Tool 选择分支 |
| `server/chickenbro_observability.py` | 验证并生成兼容旧记录的 Trace v1 和 Registry Trace v2 | 不保存 manifest 正文、用户原文或 Tool payload |

## Registry 数据合同

### Tool Manifest

每个 manifest 是不可变记录，主键为 `tool_id + version`，包含：

```text
toolId
version
kind                  # phase 2 固定为 tool
namespace             # source
purpose
inputSchema
outputSchema
discoveryPolicy
riskClass
sideEffects
ownerPolicy
sourcePolicy
freshnessPolicy
timeoutBudgetMs
costBudget
implementationRef
evalRefs
status                # active | disabled
provenance
contentHash
createdAt
```

`discoveryPolicy` 只能包含结构化字段：允许的 `requestKinds`、必需 context 字段、支持的 product phase、region 和固定 priority。它不能包含 prompt、正则代码、SQL、Python 或任意表达式。

`implementationRef` 只是稳定标识，不是可执行路径。P2 只允许：

```text
chickenbro.source.raiderio.v1
chickenbro.source.warcraftlogs.v1
```

Runtime adapter map 在仓库源码中把这两个标识绑定到现有 builder/loader。未知 implementationRef 必须让整个 Registry Release 校验失败，不能跳过后继续运行。

### Registry Release

Release 是一组 manifest 引用的不可变快照，当前生效身份由独立单行 pointer 指向：

```text
registryVersion
manifestRefs          # ordered toolId + version + contentHash
releaseHash
provenance
createdAt
```

`ops.chickenbro_tool_registry_active` 只保留一行 `singleton_id=1`、当前 `registry_version`、激活时间和 provenance；切换只更新 pointer，不修改历史 Release。Runtime 必须在一次事务读取 pointer、Release 和全部引用 manifest，重新计算 content/release hash，并验证引用完整、ID 唯一、manifest 状态 active、implementationRef 获准。部分读取、重复 ID、hash 冲突或未知字段均视为整个快照无效。

Phase 2 初始 release 只包含：

- `source:raiderio:v1` → `chickenbro.source.raiderio.v1`
- `source:warcraftlogs:v1` → `chickenbro.source.warcraftlogs.v1`

本阶段不提供公共写 API、前端管理界面或模型可调用的 Registry 修改 Tool。初始 release 由 PostgreSQL migration 以确定性内容写入；后续发布身份仍需独立阶段和 Harness 证据。

## 发现与执行规则

1. 后端沿用现有确定性 classifier 形成 `RequestIntent`；模型不参与发现。
2. discovery 只在 active release 中筛选满足 `requestKinds` 和 required context 的 manifest。
3. `personal_wcl` 只发现并选择 Warcraft Logs；`community_build + classKey + specKey` 只发现并选择 Raider.IO；`general` 不选择 Tool。
4. discovered 表示满足 scope 的已发布能力；selected 表示通过 owner、参数、来源和风险校验并准备执行的能力。
5. adapter 重新构建参数，忽略模型或客户端提供的 capability ID、owner、凭据、source URL 和 implementationRef。
6. ToolResult 继续经过现有 evidenceRefs、allowedNumbers、freshness 和模型输出校验；Registry 不能提升来源状态。
7. 单个 Tool 失败保留明确状态和 limitation，不调用未发现能力替代，也不生成固定答案。

## 缓存、故障与降级

- Runtime 缓存最近一次已完整验证的不可变 release，缓存身份包含 `registryVersion + releaseHash`；
- 每次缓存刷新都从 PostgreSQL active pointer 重新读取并验证；缓存最大可用期固定为 60 秒；
- PostgreSQL Registry 临时读取失败时，可在 60 秒内使用进程内已验证快照并在 Trace 标记缓存来源；超过 60 秒或进程冷启动无快照时停止 Tool 调用；
- Registry 不可用不等于整个对话必须失败：普通无 Tool 对话可继续，需要来源的回答只能提供不依赖该来源的部分并明确缺口；
- manifest、release hash、引用或 adapter 绑定失败是 `registry_invalid`，不得降级成旧固定 allowlist；
- runtime code 回滚可恢复 P1 固定 allowlist 版本，但 P2 代码内部不保留隐藏兼容开关。

## Trace v2 与兼容读取

P2 新 Trace 使用 `chickenbro-agent-trace-v2`，至少新增：

```text
runtimeVersion = chickenbro-registry-runtime-v1
selectionMode = registry
registryVersion
registryReleaseHash
registrySource = postgres | verified_cache
discoveredCapabilityIds
selectedCapabilityIds
```

`toolStatuses` 只对应 selected Tool。Trace validator 必须继续只读支持历史 v1，不能重写旧 Trace；新写入只产生 v2。去标识 projection 保留 Registry 版本、选择集合和状态，但不保留 release provenance、manifest purpose、owner、参数、原始证据或自由文本。

## 权限与数据边界

- Registry 表属于 `ops` schema；Runtime role 只有读取权限，不能 INSERT/UPDATE/DELETE；
- migration/发布角色负责写入不可变 manifest 和 release；
- manifest 不保存 token、凭据值、用户数据、prompt、聊天内容或来源 payload；
- owner policy 是后端校验合同，Registry 记录不能授予更大 owner 范围；
- 两个来源 adapter 沿用现有凭据和来源边界，不新增外部写入或第三方下载。

## 联动影响图

```text
0025 PostgreSQL migration
  -> PostgresOpsStore active release read
  -> chickenbro_registry validation/discovery
  -> chickenbro_tool_runtime adapter execution
  -> news_backend bounded context
  -> chickenbro_observability Trace v2
  -> offline Eval + health + release evidence
```

不改变 Taro/legacy 前端、消息 API response schema、个人模板 API、SimC 任务、WCL/Raider.IO 数据 owner 或模型输出 schema。

## 工程健康判断

`news_backend.py` 是现有热点，本阶段只保留编排：Registry 校验/discovery 与 adapter dispatch 必须分别进入小型纯模块。不得把 manifest schema、hash、缓存或执行映射继续堆入 `news_backend.py`。`PostgresOpsStore` 只增加 Registry 读取方法，不能成为 discovery 规则 owner。

## 验收证据

### 确定性合同

- Manifest/Release 拒绝未知字段、重复 ID、hash 冲突、未知 implementationRef 和非 active 引用；
- discovery 矩阵覆盖 WCL、职业构筑、一般问题、缺失 class/spec、PTR/retail 和未知 scope；
- 客户端、模型和 manifest 均不能覆盖 owner、凭据或任意资源地址；
- P1 Trace v1 可继续读取，新请求只写 v2。

### 行为等价

- 对同一组输入，P1 fixed allowlist 与 P2 Registry 在两个已支持 Tool 上产生相同 ToolResult、evidenceRefs、allowedNumbers、answer schema 和失败状态；
- 一般问题仍不调用 Tool；WCL 问题不调用 Raider.IO；职业构筑问题不调用 WCL；
- Registry unavailable/invalid 不触发旧 allowlist 或未发布 Tool。

### PostgreSQL 与运行时

- migration 0025 的不可变表、唯一 active pointer、hash、FK/约束、只读 runtime 权限和 ledger 通过；
- clean exact HEAD full Harness 通过；
- 已知云服务器候选部署验证 migration、active release、两个真实 Tool 路径、一般无 Tool 路径、invalid/unavailable 降级、Trace v2、health、timer/backflow 和代码回滚；
- candidate、local、origin/main 和 cloud runtime identity 在收尾时精确对齐。

## 非目标

- 不新增官方版本查询、个人模板、SimC、WCL 对比或其他 Tool；
- 不把现有 context evidence 包装成 Tool；
- 不做 CapabilityGap、跨用户聚类、Toolsmith、候选生成、shadow、canary 或 promotion；
- 不允许运行时生成、编辑或发布 manifest；
- 不改变前端、回答文案策略、模型供应商或长期记忆合同；
- 不用 Tool 数量或 Registry 存在本身宣称系统已经自我进化。

## 回滚

候选失败时恢复 P1 已验证代码身份并重启 `wow-backend`；0025 表和初始 release 为加法数据，可保留，不删除 P1 Trace、消息、会话或 Agent job。恢复后以同一组三路径 smoke 证明 fixed allowlist 行为恢复。P2 最终合入后，Registry release 回退和自动 promotion 仍属于后续阶段，不能在本阶段伪装完成。

## 决策记录

- 2026-08-02：用户批准继续能力演化 P2 并要求推进到完成收尾。
- 2026-08-02：首批 Registry 只包含 Raider.IO 与 Warcraft Logs；个人模板和 SimC 保持 context evidence。
- 2026-08-02：采用 PostgreSQL 不可变 Manifest/Release + 仓库内 adapter 绑定；拒绝静态文件 Registry 和数据库任意代码加载。
