# 炸鸡队长能力演化控制面设计

状态：`已确认设计`
分类：`Strict（分阶段实施）`
确认日期：2026-08-02

本设计扩展[炸鸡队长统一 ChatBot 与受控分析架构](2026-07-24-chickenbro-chatbot-design.md)和[来源驱动 Agent 实施计划](2026-08-01-chickenbro-source-agent-implementation.md)。它定义长期能力演化边界，但不把现有来源 Agent 描述成已经具备 Toolsmith、动态 Tool Registry 或自动晋级能力。Phase 1 已归档；Phase 2 Tool Registry 已获得单独设计与实施授权；Phase 3–5 仍必须分别规划、审阅、验证和发布，不能从本次授权推导。

实施入口：[Phase 1：Trace、Outcome 与 Eval 基础实施计划](2026-08-02-chickenbro-observability-phase1-implementation.md) · [Phase 2：Tool Registry 专项设计](2026-08-02-chickenbro-tool-registry-phase2-design.md)

当前事实入口：[project-state.json](../project-state.json)、[roadmap.md](../roadmap.md)、[Harness](../harness.md)、[验证矩阵](../verification-matrix.md)

## 设计结论

炸鸡队长不建立由聊天原文堆积而成的静态公共知识库，也不把“自我进化”定义成在线模型自行改权重、改代码或发布代码。目标是建立一个**能力演化控制面**：在线 Agent 按需发现和使用已经发布的 Tool、Workflow 与 Skill；异步系统从 owner-bound 会话结果和结构化 Agent Trace 中识别重复能力缺口；隔离的云端 Codex Toolsmith 生成或修复候选能力；独立 Evaluator 以保留样本、确定性门禁、shadow 和 canary 证据决定是否允许晋级。

在线执行面与离线演化面必须分离：

- 在线 Captain Runtime Agent 只消费已发布能力，不能编辑 Registry、代码或发布状态；
- Gap Miner 只抽象、去标识和聚类问题，不执行任意 Tool；
- Cloud Codex Toolsmith 只在隔离环境生成候选包，不能自行发布；
- Independent Evaluator / Promoter 独立验证并按风险策略晋级或回退；
- 只读、无副作用且完全由已批准原语组成的声明式 Workflow，可在通过评估后自动进入 shadow/canary；新执行代码、外部写入、新凭据范围和生产部署始终保留人工批准。

## 用户目标与完成体验

玩家只需要自然提问，不需要理解 Tool、来源适配器或演化流程。系统完成后的可见体验是：

1. 版本、开放日期、职业环境等时效事实能够按产品、地区、阶段和查询时间自动调用合适来源；
2. 已验证事实直接、自然地回答，不再用泛化免责声明掩盖已经确定的结论；
3. 证据不足时准确说明缺失来源或冲突，不编造结论，也不暴露内部错误码和执行器术语；
4. 回答正文保持简洁，来源、适用地区、截至时间和验证状态按需展开；
5. 同类问题反复失败后，后台能够形成可验证的能力改进候选，而不是依赖人工不断追加固定回答；
6. 新能力出错时能够自动降级或回退，不影响原有可用能力。

例如“当前版本和下个版本国服开放时间”不能沉淀为一个固定答案。系统应沉淀通用能力：“按游戏产品、地区、正式服/PTR/Beta 阶段和 as-of 时间查询当前发布状态，并仅使用满足来源与新鲜度策略的证据回答。”

## 非目标

本设计不建设：

- 把所有聊天原文、用户纠正或模型回答合并成公共知识库；
- 在线 Agent 自行编辑生产代码、数据库 Schema、Registry 状态或系统提示词；
- 由同一个 Codex 生成、评估并批准自己的能力；
- 任意网页抓取、任意 URL、任意 SQL、Shell、文件系统或凭据访问；
- 仅凭点赞、点踩或一次用户纠正自动生成公共事实；
- 以 Tool 数量、候选数量或 LLM 自评分代表能力进化；
- 首阶段引入通用插件市场、向量数据库、独立微服务集群或模型权重训练。

## 方案选择

| 方案 | 收益 | 主要风险 | 结论 |
| --- | --- | --- | --- |
| 同一个 Codex 在线回答、制造 Tool 并发布 | 迁移最少，早期演示快 | 在线延迟和故障面放大；上下文与权限混杂；同一主体自测、自批、自发布 | 只适合隔离原型，不进入生产目标 |
| 在线执行面与离线演化面分离 | 在线稳定；候选可追踪、独立评估和回退；Codex 可在请求路径外做深度代码工作 | 需要分阶段建立 Trace、Registry、Eval 和发布身份 | 采用 |
| 全自动多 Agent 自修改闭环 | 理论自动化程度最高 | 错误累积、目标投机、成本、隐私和供应链风险难以界定 | 当前不采用 |

用户提出的 `tools_box` 是正确的运行时入口，但只对应 Registry 中已发布能力的可发现清单。缺少 Trace、Gap、Toolsmith、独立 Eval 和发布控制时，`tools_box` 只是动态菜单，不能构成可靠的自我进化机制。

## 目标架构

```text
Taro Chat UI
  -> wow-backend / Captain Runtime Agent
       -> Tool Discovery -> active Tool / Workflow / Skill
       -> Evidence Validation -> natural answer
       -> owner-bound message + structured Agent Trace

Agent Trace + outcome signals
  -> Gap Miner / Experience Distiller
       -> de-identified CapabilityGap cluster
       -> qualified gap + redacted fixtures + Eval Cases
  -> isolated Cloud Codex Toolsmith
       -> candidate Eval / Skill / Workflow / executable Tool package
  -> Independent Evaluator / Promoter
       -> evaluated -> shadow -> canary -> active
       -> degraded / retired / rollback
  -> Tool Registry consumed by Captain Runtime Agent
```

控制面首版继续依托现有 Python、PostgreSQL、Worker、Harness 和部署边界。逻辑职责可以先在模块化单体内实现；只有负载、权限隔离或运维证据证明需要拆分时，才形成新的网络服务。

现有代码承接关系保持明确：`server/news_backend.py` 继续拥有 HTTP、身份、owner、会话和消息边界；`server/chickenbro_agent.py` 从当前固定 allowlist 调度逐步演化为 Registry 消费者；`server/codex_worker.py` 继续只是可替换执行器适配，不因运行 Codex CLI 自动取得 Toolsmith 或发布权限；现有 Chickenbro session、message 和 agent job 是 owner-bound 原始证据引用，不直接充当跨用户经验库。

## 组件职责

### Captain Runtime Agent

在线请求按以下顺序处理：

1. 从后端身份和消息中形成受控 `RequestContext`，包含 owner、产品、地区、game track、版本阶段、场景和 as-of 时间；
2. 只从 Registry 中发现 `active` 且满足 owner、风险、来源和新鲜度策略的能力；
3. 由后端验证 Tool 参数并执行，模型不能提供或覆盖 owner、凭据和任意资源地址；
4. 校验 Tool 状态、证据、数字白名单、适用范围与冲突；
5. 生成直接回答以及可展开的证据摘要；
6. 保存结构化 Trace 和结果信号。

Runtime Agent 不能修改 Tool Manifest、实现引用、评估结果或发布状态。能力不存在时必须记录 `tool_missing` 或其他明确失败，不允许静默切换成固定回复。

### Gap Miner / Experience Distiller

Gap Miner 异步读取 owner-bound Trace 引用和允许的结果信号，将重复问题抽象成去标识化 `CapabilityGap`。它负责：

- 区分产品缺陷、单次服务故障、提示或表达问题、数据源缺口和真正能力缺口；
- 对相同 problem signature 去重、聚类并计算重复性；
- 保留可验证的期望结果、必需输入、证据类型、风险等级和已观察失败；
- 生成脱敏 fixture 与 Eval Case；
- 在证据不足或来源互相冲突时保持 `observed` 或 `quarantined`，不得交给发布链路。

Gap Miner 不拥有任意 Tool 执行权，不把聊天内容改写成公共事实，也不保存跨 owner 可反查的原文片段。

### Cloud Codex Toolsmith

Toolsmith 位于在线请求路径之外，在隔离工作区中接收合格 Gap、脱敏 fixture、现有 Tool 接口、代码范围和验收合同。它按固定顺序选择最小改进：

1. 新增或修正 Eval Case；
2. 调整 Skill；
3. 用已批准 Tool 组合声明式 Workflow；
4. 前三项不足时才生成新的可执行 Tool adapter。

候选包必须同时包含 manifest、实现或声明、契约测试、保留 fixture 之外的生成测试、来源和新鲜度策略、权限与副作用声明、超时与成本预算、迁移和回滚说明。Toolsmith 可以根据评估失败继续修复候选，但不能写生产 Registry、取得生产凭据、部署或批准候选。

### Independent Evaluator / Promoter

Evaluator 使用与 Toolsmith 隔离的测试输入和权限，执行确定性契约、保留样本回放、Trace grading、安全和性能测试。Promoter 只读取已签名或不可变的候选身份与评估结果，按策略改变生命周期状态。LLM Judge 可用于评价自然度和可行动性，但不能替代事实、Schema、owner、来源、权限和副作用的确定性门禁。

## Registry 与核心数据合同

### Tool Manifest

每个可消费能力至少记录：

```text
toolId
version
kind                  # tool | workflow | skill
namespace
purpose
inputSchema
outputSchema
riskClass
sideEffects
ownerPolicy
sourcePolicy
freshnessPolicy
timeoutBudget
costBudget
implementationRef
evalRefs
status
provenance
```

动态选择同时使用结构化范围、状态、风险、历史成功率、延迟和成本，不只依赖自然语言描述。Registry 保存版本化 manifest 和发布身份，不保存模型 chain-of-thought、密钥或任意可执行文本。实现通过不可变引用绑定，发布状态变化必须可审计、可回退。

### Agent Trace

Trace 是可观测事实，不是完整思维过程。至少包含：

```text
traceId / ownerRef / sessionRef / messageRef
runtimeVersion / registryVersion
requestScope
discoveredCapabilityIds
selectedCapabilityIds
validatedArguments
toolStatuses / evidenceRefs / freshnessStates
answerStatus
latency / boundedCost
outcomeSignals
createdAt
```

敏感参数、原始 WCL 事件、完整 prompt、密钥和自由文本 chain-of-thought 不进入 Trace。跨用户分析只读取脱敏投影；原始 Trace 仍遵守 owner 和保留期。

### CapabilityGap

Gap 是问题能力的抽象，不是固定答案：

```text
gapId
problemSignature
desiredOutcome
requiredInputs
requiredEvidence
expectedOutputContract
riskClass
observedFailureKinds
sampleCount / ownerCount
verificationState
redactedFixtureRefs
evalCaseRefs
lifecycleStatus
```

硬信号包括 `tool_missing`、`tool_failed`、`evidence_missing`、`schema_invalid`、`explicit_correction` 和 `verification_conflict`。软信号包括立即改写、重复追问、无效 Tool 游走、异常延迟/成本和无法归因的不满意。软信号只能提高审核优先级，不能单独创建公共事实或发布候选。

### Eval Case

Eval Case 绑定输入范围、预期事实或行为、证据来源、允许的变化、禁止行为和 as-of 规则。用户事实纠正只能产生待验证 Claim 和 Eval Case；正确答案必须由获准来源重新核验。表达偏好可以影响 owner-bound 或产品级回答策略，但不能覆盖事实合同。

## 在线与异步数据流

### 在线回答链路

```text
问题
-> 补全 scope 与 as-of
-> Registry 发现
-> Tool 执行
-> 证据校验
-> 自然回答
-> Trace + outcome
```

证据已满足时直接回答，不添加无意义免责声明。证据不足时说明实际缺失来源、时间或冲突；内部标识只进入 Trace，不原样展示给玩家。

### 异步演化链路

```text
Trace / outcome
-> observation
-> de-identification
-> clustering
-> qualification
-> Eval Case
-> minimal candidate kind
-> isolated generation
-> independent evaluation
-> shadow
-> canary
-> active or rollback
```

候选生命周期固定为：

```text
observed -> clustered -> qualified -> candidate -> evaluated
         -> quarantined                    |
                                             v
                         shadow -> canary -> active
                                      |         |
                                      v         v
                                  degraded -> retired
```

同一个生成主体不得把自己创建的候选标记为 `evaluated` 或 `active`。

## 防止错误学习

- 原始聊天不是事实来源；模型答案也不是事实来源；
- 用户事实纠正只触发核验、回归测试和能力修复，不直接成为公共事实；
- 产品缺陷进入工程缺陷流程，不进入 CapabilityGap；
- 事实必须绑定产品、地区、game track、版本/赛季、查询时间、来源和新鲜度；
- 来源冲突保留各自 provenance，未经规则或人工裁决不得合并为单一结论；
- 时效事实按 freshness policy 重新验证，过期结论不得继续作为 `verified`；
- 候选和生产能力均保留版本、评估和使用 lineage，禁止用自身失败答案继续生成“正确答案”；
- 生产指标恶化时回退到上一不可变 Champion，并把失败作为新的 observation，而不是直接修改当前生产实现。

## Champion / Candidate 评估

“生成更多 Tool”不代表进化。Candidate 必须在未提供给 Toolsmith 的保留样本上稳定优于当前 Champion，并通过以下四层评估：

1. **确定性契约：** Schema、参数验证、owner、权限、来源、新鲜度、超时、副作用和失败映射；
2. **事实与任务结果：** 版本、日期、地区、职业、模板、WCL 或 SimC 结论的可验证正确性；
3. **Agent Trace：** Tool 发现与选择、无效调用、过期证据、来源冲突和停止条件；
4. **用户体验：** 结论优先、必要具体性、自然中文、无无意义免责声明、无内部术语泄露、证据不足时准确说明缺口。

安全、owner 隔离、外部写入和凭据范围是零容忍硬门槛。质量、延迟和成本必须相对 Champion 达到该阶段实施计划预先声明的阈值；阈值不得由 Candidate 的同一生成过程事后调整。

线上观察至少记录：

- 可验证正确率与无依据断言率；
- 用户事实纠正率、重问率和立即改写率；
- Tool 发现、选择和执行成功率；
- 来源过期与冲突处理正确率；
- owner、权限和隐私事件；
- 请求延迟、Tool 延迟和有界成本。

## 发布、自主权限与回退

| 能力类型 | 允许的自动化 | 必须人工批准 |
| --- | --- | --- |
| Eval Case | 去标识和确定性校验后加入回归候选集 | 改变公共事实 authority 或隐私范围 |
| Skill | 生成、测试、shadow | 进入生产默认回答策略 |
| 只读声明式 Workflow | 评估通过后自动进入 shadow/canary；策略允许时自动 active | 新来源、新 owner 范围或策略外风险 |
| 可执行 Tool | 生成、隔离测试、评估、shadow | 代码发布、生产部署、外部写入、新凭据范围 |

shadow 不影响用户回答；canary 只接收策略允许的少量真实请求，并保留 Champion 回放。硬门禁失败立即停止；质量或成本恶化进入 `degraded` 并回退；被替代且无调用方的版本按 Harness 兼容淘汰规则进入 `retired`。

## 故障与降级

- Registry 不可用：使用进程内最后一次已验证只读快照；无法验证快照身份时停止 Tool 调用，不切换成任意工具；
- Tool 超时：记录明确 Tool 状态，允许按 manifest 的有界策略重试；不得由模型伪造结果；
- 来源过期或冲突：可回答不依赖该事实的部分，时效结论保持 `partial`、`stale` 或 `blocked`；
- Trace 写入失败：回答可在不影响 owner 安全时完成，但本次结果不得进入学习和晋级样本；
- Gap Miner 或 Toolsmith 失败：不影响在线回答，候选可重试但不得绕过 Evaluator；
- Evaluator 不可用：候选停留在原状态，不能以 Toolsmith 自测代替；
- canary 指标恶化：原子回退到上一 Champion，并保留候选身份、失败证据和影响窗口；
- 生产写入或隐私边界异常：立即禁用对应能力，不能仅降权继续运行。

## 分阶段实施

本设计必须拆成五个可独立审阅、验证和回退的实施计划：

### Phase 1：Trace、Outcome 与 Eval 基础

在不改变用户回答路径和 Tool 选择方式的前提下，引入最小结构化 Trace、结果信号、脱敏投影和回归运行器。先证明当前系统的成功与失败可观测，且不会记录 chain-of-thought、密钥或跨 owner 原文。

### Phase 2：Tool Registry 与在线动态调用

将现有固定 allowlist 迁移为版本化 manifest 和 Registry 驱动发现，保留后端参数、owner、来源和副作用校验。首批只注册现有、已验证 Tool；不在本阶段制造新 Tool。

已确认专项边界见[Phase 2：Tool Registry 专项设计](2026-08-02-chickenbro-tool-registry-phase2-design.md)：初始 Registry 只包含 Raider.IO 与 Warcraft Logs；个人模板和 SimC 继续作为 context evidence；Registry 只驱动发现，执行仍绑定仓库内获准 adapter。

### Phase 3：CapabilityGap 聚类与审核

从结构化信号产生 observation，建立去标识、聚类、验证、隔离和 Eval Case 流程。该阶段只产生合格 Gap，不执行代码生成或自动发布。

### Phase 4：隔离 Toolsmith 候选生成

云端 Codex 在隔离工作区中按 Eval -> Skill -> Workflow -> Tool 顺序生成候选包，并接受独立测试反馈。所有候选保持非生产状态。

### Phase 5：Shadow、Canary、Promotion 与自动回退

建立不可变 Candidate/Champion 身份、保留样本、shadow、canary、策略化晋级、运行指标和原子回退。只有本阶段完成后，策略允许的只读声明式 Workflow 才能获得有限自动晋级能力。

阶段不得合并成一次性切换。Phase 1 是下一份实施计划的唯一默认范围；后续阶段必须使用前一阶段的新鲜证据重新决策。

## 用户可见验收

完整目标的用户验收至少证明：

1. 已验证的时效事实能够直接回答，并可展开查看适用地区、截至时间、来源和状态；
2. 来源失败时给出具体、真实的限制，不输出固定兜底模板；
3. 同类能力缺口能够形成去标识 Gap 和独立 Eval，而聊天原文保持 owner-bound；
4. Toolsmith 生成的候选不能直接进入生产；
5. Candidate 在保留样本、shadow 和 canary 中优于 Champion 后才晋级；
6. 生产指标恶化能够回退，且回退后在线 Agent 不再发现已降级版本；
7. 产品缺陷、用户偏好、用户事实纠正、数据源故障和能力缺口被分流到正确系统。

任何单元测试、Toolsmith 自评、历史截图或少量成功回答，都不能替代对应阶段的 Harness、候选运行时和真实微信验收。

## 研究依据

- [OpenAI Tool Search](https://developers.openai.com/api/docs/guides/tools-tool-search)：按需加载 Tool 与 namespace，而不是把所有工具一次性放入模型上下文；
- [OpenAI Programmatic Tool Calling](https://developers.openai.com/api/docs/guides/tools-programmatic-tool-calling)：模型可组合受注册 Tool 约束的程序化流程，但隔离运行时不因此获得任意网络、文件或子进程权限；
- [OpenAI MCP / Connectors 安全指南](https://developers.openai.com/api/docs/guides/tools-connectors-mcp)：外部 Tool 必须处理审批、敏感数据和 prompt injection 风险；
- [OpenAI Agent Evals / Trace Grading](https://developers.openai.com/api/docs/guides/agent-evals)：评估完整 Agent 轨迹、Tool、guardrail 与 handoff，而不是只看最终文字；
- [Agent Workflow Memory](https://arxiv.org/abs/2409.07429)、[TroVE](https://arxiv.org/abs/2401.12869)、[SkillWeaver](https://arxiv.org/abs/2504.07079)与[Tool-Genesis](https://arxiv.org/abs/2603.05578)：工作流、技能和工具可以从经验中抽象并复用，但生成数量不等于可靠性；
- [Tool Preferences Are Unreliable](https://aclanthology.org/2025.emnlp-main.1060/)：模型对 Tool 的自然语言偏好不足以替代结构化路由、状态和实测表现；
- [Reflexion](https://arxiv.org/abs/2303.11366)：反馈记忆可以改善后续推理，但不提供事实 authority 或生产发布证明。

这些研究支持“动态工具发现＋工作流记忆＋候选生成＋独立评估”的方向，不支持让一个在线模型自行生成、验证并发布生产代码。
