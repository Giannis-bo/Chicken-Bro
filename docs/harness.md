# Repo-native Harness

> Harness version：v0.6。
> 最后更新：2026-07-15。
> 适用范围：本仓库所有需求讨论、方案设计、实现、验证、部署和交付声明。

本文定义项目内置的轻量交付 Harness。它不是外部平台替代品，也不替代现有 roadmap、runbook、测试或部署脚本。它的作用是把“能不能开始实现”和“能不能声明完成”变成明确的合同和证据状态。

## 核心原则

- 先挑战需求，再实现。Agent 不能从模糊目标直接跳到代码改动。
- 小改动允许 agent 自审通过；大需求必须先和用户对齐方案。
- 没有证据就不能升级状态。`pass`、`verified`、`done`、`live` 必须有对应证据。
- 覆盖率不是质量证明。类似 `40/40`、`80/80`、测试通过、接口 200 只能证明对应维度，不自动证明用户预期。
- 公开入口优先保守。内部 evidence、prototype、legacy fallback、diagnostic 不能自动进入用户可见入口。
- 当前事实优先。`docs/roadmap.md` 顶部、`docs/README.md`、当前 runbook 和 active contract 胜过旧计划、旧截图、旧 manifest。
- 证据只能声明它能证明的等级。静态检查、本地测试、真实运行、线上 smoke、用户验收不能互相冒充。
- 事实判断必须有 owner。前端、health/admin、定时任务和脚本不能各自创造事实结论。
- 需求不能按单点实现。Standard 以上需求必须先评估它属于哪条业务链路，以及会传播到哪些后端、前端、数据、定时任务和运维面。
- 工程健康也是交付边界。触达热点文件、核心 API、PG read model、定时任务、health/admin 或部署脚本时，必须说明结构、性能和可用性影响。
- 运行时改动先候选验证再合入。触达 backend/API、PG read model、公开 payload、health/admin、定时任务、部署脚本或用户可见运行链路时，默认在 PR 最终候选阶段完成一次部署或预览 smoke，通过后再合入。
- Harness 必须由真实问题迭代。返工、事故、证据误判、联动漏评和旧文档误导应先记录 finding，再按规则升级为 Harness 改动。
- 本仓库与已配置项目远端之间的常规同步是协作基础设施，不再作为下载/网络授权阻塞项；但它不能扩展为依赖安装、第三方下载、任意 clone、改 remote 或破坏性历史改写。
- 用户批准计划、授权继续或要求直接推进后，agent 默认自动推进后续范围内步骤；只有明确阻塞、验证失败需权衡、范围变化、待决策点或越界高风险操作才回到用户确认。
- 不确定时按更高风险处理。Agent 如果无法判断需求大小，默认进入大需求流程。

## 用户体验优先讨论门禁

功能、Bug 和需求讨论的默认入口是用户体验，而不是文件、接口、字段或实现步骤。该门禁适用于 Light、Standard 与 Strict；它不阻止只读排查，但会约束后续建议和交付声明的表达顺序。

每次讨论至少应先说明：

1. 用户是谁、处于什么场景、想完成什么任务。
2. 用户目前在哪一步受阻、误解、失去信任或无法继续。
3. 变更后用户应看到/完成什么，以及正常、空态、失败或证据不足时如何被诚实地告知。
4. 用户可观察的完成信号与验收条件。
5. 哪些内容是已验证事实，哪些仍是产品假设或技术假设。

默认输出顺序为“用户目标与场景 → 当前摩擦/伤害 → 目标体验与主路径/例外路径 → 用户侧验收和可信边界 → 技术方案、约束、风险与实施”。

- Bug 必须先描述用户侧症状、影响和预期恢复，再描述怀疑的根因或改动点。
- 技术细节并非省略：只要它会改变用户承诺、数据真实度、隐私、时延、可用性、降级或回滚，就必须明确说明；用户明确要求技术方案/实施时，技术层可成为主叙述。
- 不得把内部证据、实现便利、未验证数据或暂时 fallback 包装成用户承诺。无法证实的体验结论应标为假设、降级、阻断或待验证。
- 进入实施前，用户侧验收和 Harness 的证据/回滚要求必须同时成立；测试通过、接口 200 或实现完成不能单独证明体验已交付。

## 需求分级

### Light

适用于文案、小样式、明确 bug、测试补充、无业务语义变化的小修。

Agent 可自审通过，但必须在动手前简短说明：

- 改什么。
- 为什么风险低。
- 是否改变用户承诺、数据来源、公开入口或部署行为。
- 准备跑什么验证。

### Standard

适用于普通功能、接口、数据展示、局部前后端合同变化。

进入实现前必须形成简短需求合同，至少包含：

- 用户场景。
- 用户侧承诺。
- 非目标。
- 关键假设。
- 验收证据。
- 联动影响面。
- 风险和降级方式。

如果合同里出现无法自证的业务语义，升级为 `Strict`。

### Strict

只要满足任一条件，必须先讨论方案并等用户确认后才能实现：

- 改产品承诺或用户可见主流程。
- 改数据来源、推荐逻辑、SimC、装备 / 天赋可信边界。
- 改公开入口、health 状态、admin 判断、部署、迁移或生产数据。
- 涉及多个模块或前后端合同。
- 改 owner 边界、事实判断归属、发布路径或回滚路径。
- 触达热点文件或核心运行链路，且无法简短说明结构、性能、可用性影响。
- 用户目标包含“推荐、智能、最佳、自动、全职业、上线、日更、生产”等容易放大的词。
- Agent 无法用一句话说明验收证据。

Strict 需求必须先输出：

1. 需求合同。
2. 反方质疑。
3. 2-3 个方案对比。
4. 推荐方案。
5. 非目标。
6. 验收证据。
7. 风险、降级和回滚。
8. 联动影响图。
9. 需要用户明确拍板的问题。

只有用户确认后，才允许进入实施计划。

Strict 只表示产品、可信边界或发布判断需要先对齐；它不自动等于“每一步都走最高成本验证”。验证强度由下方的运行面风险分层决定。

## v0.6 验证风险分层

| 改动面 | 开发中 | 最终本地 | CI | 候选 / live |
| --- | --- | --- | --- | --- |
| 文档、evidence、Harness packet、CI 配置 | 相关 schema / Harness 测试 | `harness` profile | 一次 `full`（CI 统一入口） | 不适用 |
| 纯前端用户交互 | 受影响 Node 测试 | 必要时 frontend profile | 一次 `full` | 一次真实 DevTools 关键路径 |
| 后端只读 / API / public payload | 受影响 Python 测试 | 可省略 full | 一次 `full` | 一次最终 PR head 的候选 smoke |
| sync、写路径、migration、timer、生产数据 | 受影响测试 | 一次 `full` | 一次 `full` | 备份、一次受控候选、定向 smoke、回滚证明 |

- 开发期默认只跑受影响测试；不得把 `frontend`、`backend`、`full` 三个 profile 串行当作常规门禁。
- `full` 是最终 head 的完整验证。普通 runtime 改动由 CI 执行一次即可；只有写路径、migration 或数据修复在候选前额外本地跑一次。
- 纯文档、evidence、归档变更只跑 `harness` profile；若 runtime tree 未变，不得重跑业务 full。
- 每个发布默认一次独立 whole-branch CR。只有发现 Critical / Important、或触达安全、migration、生产写路径时才追加复审。

## Requirement Challenge Gate

实现前的需求挑战必须回答这些问题：

| 问题 | 目的 |
| --- | --- |
| 用户真正要达成的场景是什么？ | 防止只实现字面功能。 |
| 用户侧承诺是什么？ | 明确最终对用户说了什么。 |
| 哪些相似东西不是本需求？ | 防止 scope 偷偷扩大。 |
| 哪些假设可能是错的？ | 提前暴露返工风险。 |
| 有没有更小、更稳、更诚实的首版？ | 防止一上来滚成大雪球。 |
| 最容易让用户不满意的 3 个反例是什么？ | 用失败案例校准方案。 |
| 验收证据是什么？ | 防止用错误指标宣布完成。 |
| 哪些指标不能算验收？ | 防止覆盖率、静态测试或旧截图越权。 |
| 证据不足时怎么处理？ | 明确阻断、降级、隐藏或标 risk。 |
| 哪些决策必须用户确认？ | 防止 agent 代替产品决策。 |

## Current Truth Gate

任何 Standard 以上需求进入方案或实现前，必须先确认当前事实入口。目标是防止 agent 从旧计划、旧证据或历史口径继续执行。

当前事实读取顺序：

1. `docs/roadmap.md` 顶部最新状态。
2. `docs/README.md` 指向的当前文档入口。
3. 相关领域 runbook / architecture doc。
4. 当前 active contract、handoff、implementation permit 或 source-of-truth 文档。
5. 历史 `docs/plans/`、`docs/design/` 和 artifacts，只能作为证据背景，除非被当前入口明确引用。

当前事实门禁必须回答：

| 问题 | 目的 |
| --- | --- |
| 本次需求使用哪个 current source-of-truth？ | 防止从历史计划直接开工。 |
| 有没有旧文档和当前事实冲突？ | 防止旧口径回流。 |
| 本次是否替代旧合同、旧入口或旧证据？ | 防止新增孤立文档。 |
| 哪些历史证据仍可引用，哪些只能归档？ | 防止旧截图、旧 manifest、旧 scorecard 越权。 |
| 完成后要回写哪个当前入口？ | 防止只新增 plan，不更新长期控制台。 |

如果当前事实不清，需求状态只能停在 `requirement_challenged`，不能进入实现。

## Impact Map Gate

Standard 以上需求进入实现前，必须生成影响图。目标不是让每次改动都全量重构，而是明确哪些面必须一起改，哪些面必须证明未受影响。

影响图至少包含四类结果：

| 分类 | 含义 |
| --- | --- |
| `must_change` | 这次必须一起修改，否则需求不成立。 |
| `must_not_change` | 这次明确不应改变，需要 diff、测试或 smoke 证明没有误伤。 |
| `risk_unknown` | 当前无法判断是否受影响，必须先查代码、数据、任务或线上状态。 |
| `evidence_required` | 需要什么证据才能声明该联动面安全。 |

常见联动面：

| 联动面 | 必问问题 |
| --- | --- |
| 数据来源 | source key、抓取源、可信等级、fallback 是否变化？ |
| 业务语义 | 这是事实样本、起步模板、推荐结论、诊断数据，还是内部 evidence？ |
| 合法性规则 | 装备、天赋、饰品、套装、美化、附魔、宝石、制造、职业限制是否被影响？ |
| 后端读模型 | PG read model、public cache、snapshot、baseline fallback 是否需要重建或迁移？ |
| API 合同 | 字段、状态、排序、空态、错误语义、版本兼容是否变化？ |
| 前端展示 | 标签、文案、风险提示、导入按钮、排序、空态、隐藏规则是否仍然诚实？ |
| 用户动作 | 导入、模拟、刷新、分享、收藏、跳转等动作是否仍能闭环？ |
| 定时任务 | daily refresh、sync、cleanup、health follow-up、deploy 后触发是否会回写旧状态？ |
| Health / Admin | 绿灯含义是否变化？后台判断是否和用户可见 read model 一致？ |
| 部署和回滚 | 是否需要迁移、重建缓存、触发任务、回滚脚本或线上 smoke？ |

如果需求触达装备 / 天赋 / SimC / 推荐链路，默认按下面的传播链检查：

```text
source ingestion
-> normalization / legality
-> recommendation semantics
-> cache / read model
-> API contract
-> frontend presentation
-> user action
-> scheduled refresh
-> health / deploy smoke
```

Agent 不能只声明“改了后端逻辑”。必须明确前端、定时任务、缓存、health、部署 smoke 是否属于本次 `must_change`、`must_not_change` 或 `risk_unknown`。

## Ownership / Contract Gate

Standard 以上需求如果触达核心链路，必须明确事实判断归属。目标是避免后端、前端、health/admin、定时任务和脚本各自补一套判断，最后互相覆盖。

Owner 合同必须回答：

| 问题 | 目的 |
| --- | --- |
| 哪个模块拥有事实判断？ | 明确 source key、status、confidence、blocker、public visibility 的权威来源。 |
| 哪些模块只是消费结果？ | 防止前端、health/admin 或脚本二次推断事实。 |
| 哪些字段是 public contract？ | 防止内部 evidence、diagnostic、prototype 字段被误当成用户入口。 |
| 哪些写入路径允许改状态？ | 防止 sync、cleanup、migration 或 fallback 回写不属于自己的状态。 |
| 跨 owner 改动如何验证？ | 要求走 Impact Map、contract test 和对应 owner smoke。 |

默认 owner 原则：

- 后端 serializer / read model owner 负责对前端公开的结构化事实。
- 前端只消费 read model、展示文案和用户动作，不自行推断 source、quality、verified、public readiness。
- health/admin 只展示权威事实和诊断，不把 `partial`、`blocked` 或 internal evidence 改写成 `verified`。
- 定时任务只写自己拥有的 sync state、cache state 或 evidence，不顺手改变公开入口。
- cleanup 只能删除或规范化合同允许的 residue，不能扩大产品语义。
- 部署脚本只负责交付动作和 smoke，不创造产品判断。

如果 owner 不清，需求状态只能停在 `requirement_challenged` 或 `health_risk`，不能进入实现。

## Engineering Health Gate

Standard 以上需求如果触达热点文件、核心 API、PG read model、定时任务、health/admin、部署脚本或高频用户路径，必须通过工程健康门禁。

这个门禁不是重构计划，也不要求每次都抽代码。它只判断本次改动是否会继续扩大结构债、性能风险或可用性风险。

当前已知热点文件包括但不限于：

- `server/websim_payload.py`
- `server/news_backend.py`
- `server/postgres_cache_store.py`

以后凡是单文件过大、近期频繁改动、承载多个领域职责，或位于核心运行链路，也应按热点处理。

工程健康门禁必须回答：

| 维度 | 必问问题 |
| --- | --- |
| 结构边界 | 是否给热点文件增加新业务职责？是否已有更合适的 owner module？本次是 adapter / delegation，还是继续堆分支？ |
| 行为边界 | 是否顺手改变了产品语义、公开入口、source key、fallback、health 判断或错误语义？ |
| 测试安全网 | 是否有 characterization test、contract test、snapshot、golden payload 或 smoke 证明旧行为未被误伤？ |
| 性能 | 是否影响接口耗时、payload size、PG 查询次数、缓存重建、同步任务耗时或前端渲染成本？是否有基线或对比证据？ |
| 可用性 | 出错时是 fail-closed、partial、fallback、retry、blocked，还是静默成功？是否幂等、可重跑、可降级？ |
| 数据安全 | 是否可能污染公开 read model、写入错误缓存、触发旧数据回流、破坏 cleanup 或迁移边界？ |
| 可观测性 | health/admin/log/audit 是否能暴露真实状态，而不是只显示任务跑完或接口 200？ |
| 回滚 | 是否能通过配置、数据回滚、脚本回滚、重新同步或隐藏入口恢复？ |

工程健康结论必须落到四类之一：

| 结论 | 含义 |
| --- | --- |
| `health_safe` | 改动不增加新职责，性能/可用性影响可忽略，验证足够。 |
| `health_watch` | 可接受但需要补充测试、smoke、日志或后续拆分记录。 |
| `health_risk` | 允许继续设计，但实施前必须明确降级、回滚和额外验证。 |
| `health_blocked` | 结构、性能或可用性风险无法解释，不能进入实现。 |

Agent 不能用“只是小改一下大文件”跳过该门禁。若确实只做兼容层或 delegation，必须在方案里说明没有新增领域职责，并给出等价验证。

## Release / Rollback Gate

Standard 以上需求如果触达部署、生产数据、PG read model、cache、定时任务、公开入口、health/admin 或用户可见主流程，必须明确发布和回滚合同。

发布前必须回答：

| 问题 | 目的 |
| --- | --- |
| 是否需要备份？ | 明确代码、PG、cache、配置或线上文件是否需要可恢复点。 |
| 是否需要 migration / cache rebuild / sync trigger？ | 防止代码已发但 read model 或定时任务仍是旧状态。 |
| 发布前 smoke 是什么？ | 明确本地或 staging 证据，不把测试通过当线上可用。 |
| 发布后 smoke 是什么？ | 明确线上 API、UI、PG、timer、health/admin 检查项。 |
| 定时任务是否会回写旧状态？ | 防止 deploy 后 sync、cleanup、follow-up 把旧逻辑带回来。 |
| 回滚路径是什么？ | 区分代码回滚、数据回滚、配置关闭、隐藏入口、重新同步或任务禁用。 |

回滚策略必须选择至少一种：

| 策略 | 适用场景 |
| --- | --- |
| `code_rollback` | 代码行为错误，数据未污染或可兼容。 |
| `data_restore` | PG/cache/read model 被错误写入，需要备份恢复或修正 SQL。 |
| `feature_hide` | 公开入口或 UI 文案有风险，先隐藏或降级。 |
| `config_disable` | 定时任务、runner、策略开关或同步入口需要暂时关闭。 |
| `resync_repair` | 代码已修复，但线上 read model 需要重新生成。 |

只有部署动作完成不能声明 `live_verified`。`live_verified` 必须有当前线上证据，并说明 smoke 覆盖了哪些入口、哪些仍是 risk。

## Candidate Deployment Gate

Standard 以上需求如果触达 backend/API、PG read model、公开 payload、health/admin、定时任务、部署脚本或用户可见运行链路，默认必须在合入前完成 PR 候选部署或等价预览 smoke。目标是避免“合入后才发现部署/runtime 问题”的发布顺序。

适用面：

- backend route、API contract、serializer、public payload。
- PG read model、cache selector、repository selector、cache rebuild 入口。
- health/admin 汇总、门禁状态、后台诊断面。
- systemd timer、sync/backfill/cleanup/follow-up job。
- deploy script、runtime env、服务重启或 smoke 清单。
- 小程序或 WebSim 真实运行入口。

合入前最低证据：

| 证据 | 要求 |
| --- | --- |
| 候选身份 | 明确部署的是 PR branch、preview build 或等价候选版本；记录 commit/hash、文件 parity 或 build identity。 |
| smoke 范围 | 覆盖被改动 runtime surface 的 health、关键 endpoint、read model 或 UI 入口。 |
| 防回流 | 检查 timer/sync/backfill/cleanup 是否会把旧状态写回来；必要时保持 async sync 关闭。 |
| 回滚 | 明确 `code_rollback`、`config_disable`、`feature_hide`、`data_restore` 或 `resync_repair` 至少一种。 |
| 证据归档 | evidence packet、roadmap、runbook 或 PR comment 记录命令、时间和结果摘要。 |

执行规则：

- 候选 smoke 通过后再合入 PR。候选必须是最终 runtime head；同一最终 head 最多部署一次。
- 最终 CI / 候选前先对齐 `main`。同一时间只允许一个 runtime PR 占用候选窗口；窗口内不合入重叠 runtime PR。若等待人工验收超过一个工作窗口，释放窗口并延后最终候选部署，避免证据被新的 `main` 失效。
- 兼容性读取、v1/v2 双读等验证默认在同一个最终 binary 上完成；只有实际滚动升级或 schema 兼容风险证明必须时，才允许部署中间 commit，并在 requirement 中说明原因。
- 如果平台没有 preview，允许把 PR branch 热部署到既有目标环境，但必须记录 branch/commit 与 runtime 文件 parity。
- 如果因平台限制只能合入后验证，必须把它标为例外或纠偏，不能当作常规发布路径；合入后立即执行 live smoke 并记录风险。
- 本 gate 不替代用户对产品方案的确认，也不扩大依赖安装、第三方下载、改 remote、force push 或破坏性操作权限。

## Repository Remote Sync Gate

本仓库与已配置项目远端之间的常规同步不需要额外授权。该规则只用于保持本地 checkout、项目分支和 GitHub PR 状态一致，不改变生产、依赖或第三方数据边界。

默认允许：

- `git fetch`、`git pull --ff-only`、`git push`。
- 发布本项目分支。
- 创建、更新、读取和合入本项目 PR。
- 读取本项目 PR、commit、status/check 信息。

执行要求：

- 本地同步前先看 `git status --short --branch`。
- `main` 默认使用 fast-forward-only 更新。
- 遇到本地未提交改动、非 fast-forward、冲突或远端状态不一致时，先保护当前工作树并说明情况。

仍需明确用户确认：

- force push、rebase 公开分支或其他历史改写。
- 新增或修改 remote。
- `git clone` 其他仓库、submodule update、依赖安装、第三方下载或写入网络获取内容。
- 任何会部署、触发生产任务、下载外部数据或改变生产配置的操作，除非当前请求已明确授权。

## Autonomous Progression Gate

一旦用户确认方案、说“继续”或授权直接推进，agent 不再为每个常规步骤单独请求同意。该规则用于减少流程摩擦，不取消 Strict 需求开始前的方案确认，也不扩大生产、依赖、下载或破坏性操作边界。

默认继续推进：

- 已确认范围内的本地实现、文档更新、测试、静态检查和 artifact 生成。
- 已授权计划中的 branch、commit、push、PR 创建/更新、PR 状态读取和合入。
- 验证通过后的下一步收口，例如 roadmap/runbook/evidence 回写或进入下一阶段准备。
- 无新增产品判断、无破坏性操作、无本地/远端冲突的常规同步和整理。

必须停止并向用户确认：

- 出现测试、smoke、lint、构建、runtime、部署或数据验证失败，且存在多个修复/降级/回滚选择。
- 发现需求需要改变产品承诺、公开入口、数据可信边界、部署方式、成本模型或用户可见主流程。
- 当前事实和旧文档冲突，且无法从 roadmap、runbook、代码或 live evidence 判定应以哪一个为准。
- 需要 force push、公开历史改写、改 remote、clone 其他仓库、submodule、依赖安装、第三方下载、破坏性命令或未授权生产操作。
- 工作树或远端状态存在冲突，继续执行可能覆盖用户改动或扩大 diff 范围。

执行要求：

- 中间更新应只报告关键状态、风险或验证结论，不为明显下一步制造审批点。
- 如果没有 blocker 或 decision point，继续执行到当前阶段自然收口。
- 收口时说明已经执行的同步、验证、PR/合入、未做的 live/deploy smoke，以及下一阶段最高证据等级。

## Evidence Promotion Gate

所有交付声明必须经过证据晋级门禁。证据只能声明它实际证明的状态，不能因为“看起来差不多”跨级。

证据等级：

| 证据 | 最高可声明状态 |
| --- | --- |
| 需求讨论、方案文档、design draft | `requirement_challenged` |
| 用户确认的需求合同 / active permit | `requirement_contract_approved` / `implementation_allowed` |
| 静态检查、单元测试、fixture、mock、golden payload | `local_verified` |
| 本地真实 API、真实 PG read model、本地任务 dry-run、真实小程序 DevTools 截图 | `runtime_verified` |
| 部署前 CR、回滚计划、目标 smoke 清单 | `deployable` |
| 线上 HTTP/API/PG/systemd timer/health/admin smoke，且有当前时间证据 | `live_verified` |
| roadmap / runbook / evidence manifest / cleanup 状态已回写 | `archived` |

不同证据类型的最低要求：

| 领域 | `runtime_verified` 最低要求 |
| --- | --- |
| UI | 真实小程序运行证据；截图、页面路径、操作 ledger 或等价 DevTools 记录齐备。 |
| API | 实际 endpoint 请求和响应摘要；不能只用 mock、fixture 或静态 payload。 |
| PG read model | 实际数据库读模型、source key、状态和关键计数；不能只用生成器测试。 |
| 定时任务 | 实际任务 run id、输入、输出、退出状态、日志摘要；dry-run 只能声明本地运行。 |
| 部署 | 线上服务、health、关键 API 和必要后台任务 smoke；不能只说文件已同步。 |
| 数据 / 推荐 | 证据必须区分事实样本、内部 evidence、prototype、projected、verified 和 public entry。 |

禁止晋级：

- 旧截图、旧 manifest、旧 scorecard 不能证明当前状态。
- 一个页面通过不能证明全页面矩阵通过。
- API 200 不能证明 UI 可用。
- health 绿灯不能证明推荐质量。
- 测试全绿不能证明线上 live。
- 内部 evidence 不能证明公开入口可展示。

如果证据不足，必须降级声明、标 risk、隐藏入口或停止交付声明。

`merge_ready` 与 `archived` 是两个不同收口动作：runtime PR 在候选、CI、必要的真实 UI 和 scoped live smoke 通过后可以合并；roadmap、runbook、evidence 的归档可以随后完成。归档本身不能要求重跑业务 full，除非它改动了运行时代码或测试。

## Harness Feedback Loop

Harness 本身也必须被治理。不能因为一次讨论临时扩写规则，也不能让真实返工和事故只停留在对话里。

每次出现以下情况，必须记录 Harness finding：

- 需求执行后出现明显返工。
- 真实运行结果和本地验证结论不一致。
- 旧文档、旧截图、旧 manifest 误导了执行。
- 影响面漏评，导致前端、后端、数据、定时任务、health/admin 或部署 smoke 出现遗漏。
- 证据等级被误用，例如把本地测试当成 `runtime_verified` 或把部署完成当成 `live_verified`。
- 工程健康风险被低估，例如热点文件继续增加职责、定时任务不可重跑、错误状态不可观测。
- 用户明确指出“以后不要再这样”。

finding 至少记录：

| 字段 | 含义 |
| --- | --- |
| 发生了什么 | 简述事实，不写成泛泛反省。 |
| 没拦住的 gate | Requirement / Current Truth / Impact Map / Engineering Health / Evidence Promotion / Release 等。 |
| 影响 | 返工、线上风险、用户可见问题、数据污染、证据误判或流程成本。 |
| 建议动作 | 不处理、补文档、补脚本、补模板、补测试、调整 gate 或降级规则。 |
| 是否升级 | `finding_only`、`rule_candidate`、`rule_promoted`、`script_candidate`。 |

不是每条 finding 都能修改 Harness。满足任一条件才允许升级为规则或脚本：

- 同类问题出现 2 次以上。
- 造成线上风险、用户可见错误、数据污染或大量返工。
- 当前 gate 明显没有覆盖。
- agent 多次误读同一类证据、文档或状态。
- 用户明确确认需要成为以后规则。

Harness 复盘节奏：

- 每个大需求或发布收口后，检查是否产生 finding。
- 每次回滚、严重返工、证据误判后，立即复盘对应 gate。
- 每 5-10 个 Standard / Strict 需求，归并一次 finding backlog。
- 每次修改 Harness，更新版本、日期和 policy change log。

## Policy Change Log

| Version | Date | Change |
| --- | --- | --- |
| v0.5 | 2026-07-09 | 增加 Candidate Deployment Gate：backend/API、PG read model、公开 payload、health/admin、定时任务、部署脚本和用户可见运行链路默认在 PR 候选阶段先部署或预览 smoke，通过后再合入；无法预合入验证时必须记录例外并补 post-merge live smoke。 |
| v0.6 | 2026-07-15 | 按运行面风险分层验证：开发期默认 targeted，普通 runtime 由最终 CI full 覆盖，高风险写路径才额外本地 full；CI 不再重复 harness + full；同一最终 runtime head 仅一次候选部署；候选窗口串行化；归档不再阻塞合入或重跑业务 full。 |
| v0.4 | 2026-07-09 | 增加 Autonomous Progression Gate：用户确认方案、授权继续或直接推进后，agent 默认自动执行范围内后续步骤；只有明确 blocker、验证失败需权衡、范围变化、待决策点、工作树/远端冲突或越界高风险操作才回到用户确认。 |
| v0.3 | 2026-07-09 | 增加 Repository Remote Sync Gate：本仓库与已配置项目远端之间的常规 fetch / pull --ff-only / push / PR 状态读取、更新和合入不再需要额外授权，同时保留 force push、改 remote、clone、submodule、依赖安装、第三方下载和生产操作的确认边界。 |
| v0.2 | 2026-07-09 | 增加 Ownership / Contract Gate 与 Release / Rollback Gate，明确事实判断归属、发布前后 smoke、回滚策略和定时任务防回流。 |
| v0.1 | 2026-07-09 | 初始 Repo-native Harness：需求分级、Requirement Challenge、Current Truth、Impact Map、Engineering Health、Evidence Promotion、状态机和 Feedback Loop。 |

## 常见质疑清单

Agent 必须主动挑战这些混淆：

- 是否把“覆盖率”和“质量”混在一起？
- 是否把“事实样本”和“推荐结论”混在一起？
- 是否把“能运行”和“用户认可”混在一起？
- 是否把“本地测试通过”和“真实运行时通过”混在一起？
- 是否把“内部 evidence”和“公开入口”混在一起？
- 是否把旧文档、旧截图或旧 manifest 当成当前事实？
- 是否把低等级证据晋级成 `runtime_verified`、`live_verified` 或 `done`？
- 是否让多个模块各自创造事实判断，而没有 owner contract？
- 是否为了 health 变绿而降低 fail-closed 标准？
- 是否存在旧 plan、旧截图、旧 scorecard 覆盖当前真实证据？
- 是否把“改后端逻辑”误当成不会影响前端、缓存、定时任务或运维判断？
- 是否为了赶需求继续向热点文件增加职责？
- 是否只看功能通过，忽略性能、幂等、回滚和可观测性？
- 是否只说“已部署”，没有发布前后 smoke、回滚路径和定时任务防回流检查？
- 是否把真实返工、事故或漏评只当个案处理，没有记录 Harness finding？
- 是否有 timer、sync、cleanup 或 deploy 会把旧状态重新引回来？

## 状态机

所有大需求默认按以下状态推进：

```text
idea
-> requirement_challenged
-> requirement_contract_approved
-> implementation_allowed
-> local_verified
-> runtime_verified
-> deployable
-> live_verified
-> archived
```

状态晋级规则：

- `requirement_challenged`：已确认当前事实入口，并完成反方质疑、方案拆分、影响图、owner 判断和必要的工程健康判断。
- `requirement_contract_approved`：Strict 需求已获用户确认；Light/Standard 可由 agent 自审确认。
- `implementation_allowed`：实施计划、边界、影响面、工程健康结论和验证路径已明确。
- `local_verified`：本地目标测试、静态检查、diff scope 通过。
- `runtime_verified`：当前真实运行环境证据通过，例如真实微信截图、实际 API、实际 PG read model。
- `deployable`：部署前 CR、发布步骤、回滚路径、定时任务防回流检查和 smoke 计划齐备。
- `live_verified`：线上服务、数据、UI 或定时任务有当前证据。
- `archived`：roadmap / runbook / evidence / cleanup 状态已回写，旧证据边界已说明。

## 社区装备模拟反例

“社区装备模拟”不能直接实现成“生成 40/40 或 80/80 模板”。需求挑战必须先拆清：

- `community_best_v2`：真实玩家当前装备事实样本。
- `season_recommendation`：可导入起步模板或 legacy baseline，不是毕业推荐。
- `recommended_bis_v1`：系统 optimizer 推荐，必须经过 SimC、pairwise、observed anchor validation。
- 公开入口：只能展示当前合同允许的 source key。
- 内部 evidence：可以保留，但不能自动回流到用户可见模板。

这个案例的教训是：`complete` 只代表 16 槽可执行，`80/80` 只代表覆盖率，二者都不能证明推荐质量。

## Agent 默认行为

- 用户只给出目标时，先判断需求等级。
- Light 可简短自审后执行。
- Standard 先确认当前事实，再给合同摘要、影响图和必要的工程健康判断；若用户没有异议且风险清楚，可继续。
- Strict 必须等用户确认，不得直接实现。
- 一个任务只处理一个产品或运行目标。认证、工具升级、外部调研、全仓库历史 worktree 清理不属于当前发布门禁，除非它们直接阻断该目标；全局清理由独立 repo-hygiene 任务完成。
- 合并阶段只清理本任务 branch/worktree；历史分支与其他 worktree 的盘点、保留或删除不得阻塞已满足发布门禁的 PR。
- 用户说“先讨论、先规划、先不急实现”时，只能停留在合同、方案、roadmap 或 runbook 层。
- 用户确认“可以、认可、就按这个”后，应把已确认方向记录到 roadmap 系统或当前合同文档。

## Project Harness Script

当前已有第一版只读聚合脚本：`scripts/project-harness.js`。

常用命令：

```bash
node scripts/project-harness.js --json --slug <slug>
node scripts/project-harness.js --json --write --date YYYY-MM-DD --slug <slug>
node scripts/project-harness.js --json --slug <slug> --evidence-file artifacts/releases/<release>/evidence.json
```

带 `--write` 时会写入本地 `artifacts/releases/<date>-<slug>/manifest.json`。不带 `--write` 时只输出 JSON 到 stdout。

带 `--evidence-file` 时只读取仓库内本地 JSON evidence packet，不执行其中的命令。Evidence packet 至少应包含：

- `status`
- `highestEvidenceLevel`
- `scope`
- `verification`
- `risks`
- `rollback`

第一版聚合：

- harness version。
- requirement gate 状态。
- current truth gate。
- impact map。
- ownership / contract gate。
- engineering health gate。
- evidence promotion gate。
- release / rollback gate。
- feedback findings。
- repository remote sync boundary。
- roadmap / active contract 入口。
- diff scope。
- 本地测试。
- UI runtime evidence。
- data health。
- deploy smoke。
- risk matrix。
- v0.6 verification-efficiency、single-candidate-window 与 merge/archive separation 规则。

脚本默认不 SSH、不部署、不联网、不下载、不安装依赖、不写生产；只读取本地文档、热点文件行数和 git 状态，可选写入本地 artifacts。
