# Project Harness Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Track each deliverable and PR as an explicit checklist item.

**Goal:** 在不改变现有产品语义和公开入口的前提下，建立可执行、可失败、可归档的项目级 Harness 工程基线。

**Architecture:** 先收口 current truth，再把 requirement/evidence、owner map 和 verification profiles 变成机器可校验门禁，最后只在 owner 缺口阻碍收口时执行有上限的等价结构修复。Harness 本地工具保持只读，runtime 发布继续由独立 Candidate Deployment Gate 控制。

**Tech Stack:** Node.js 标准库、`node:test`、Python 3 标准库、`unittest`、JSON、Git/GitHub Actions、现有 Lighthouse deploy/smoke 脚本。

## Status

`方案已批准 / 等待新 Goal Session 实施`

用户已选择 B 路线：先完成阶段性的工程规范化，再恢复需求和功能迭代。

本计划是 `docs/harness.md` v0.5 的下一阶段执行合同。它不把“规范化”解释为无限拆文件，也不以大文件行数下降作为完成标准。目标是让 current truth、owner、contract、verification、evidence 和 release gate 真正可执行、可失败、可归档。

## Architecture Detail

本轮分成三个交付面：

1. **Control plane**：收口当前事实，解决 roadmap、active contract 和历史计划互相冲突的问题。
2. **Executable Harness**：把现有“模板提示”升级为会返回非零退出码的 requirement/evidence/owner/verification 门禁。
3. **Engineering baseline**：补齐全项目 owner/contract map 和关键链路 characterization；只在 owner 边界确实无法落地时做少量结构修复。

Harness 脚本默认只读，不 SSH、不部署、不下载、不安装依赖、不写生产。部署仍由明确的候选部署步骤执行，不能被本地验证脚本隐式触发。

## Approach Decision

本轮已对比并由用户选择以下路线：

| 路线 | 范围 | 取舍 | 结论 |
| --- | --- | --- | --- |
| A：流程规范化 | current truth、模板、evidence、验证命令 | 最快，但 owner/contract 和工程热点仍主要依赖人工判断 | 不采用 |
| B：工程规范化 | A + 全项目 owner map、关键 characterization、自动门禁和少量必要边界修复 | 能形成可执行基线，同时有明确终点 | **已批准** |
| C：深度结构重构 | B + 持续拆分所有热点文件和 write/sync repositories | 结构收益可能更高，但会把功能迭代无限后移并扩大 runtime 风险 | 不采用 |

B 路线的核心约束是“以 owner/contract 缺口决定是否拆分”，不是“看到大文件就继续拆分”。

## Global Constraints

- 本里程碑期间冻结新需求、新功能和产品语义调整；只允许规范化、characterization、门禁、文档收口和必要的等价结构修复。
- 不改变公开装备入口：`communityTemplates` 仍只允许 active `raiderio_observed_profile`，`baselineTemplates` 公开默认仍为空。
- `recommended_bis`、`season_recommendation`、`default_template`、`simc_preset`、`baseline_blocked` 不得回流公开装备入口。
- 后端 read model 继续拥有结构化事实；前端只消费结构化结果，不自行推断 source、quality、verified 或 public readiness。
- 不重构 sync/write/backfill/cleanup 数据写入路径；本轮只允许建立 owner map、characterization 和 guardrail。
- 不做 UI 视觉重设计，不改变路由、主流程、文案承诺或用户数据模型。
- 不新增第三方运行时依赖。任何安装、下载、clone、submodule 或 remote 修改仍需显式授权。
- 结构修复默认最多 3 个独立 runtime slice；超过上限必须作为新决策回到用户确认。
- 每个 runtime slice 必须独立 TDD、独立 PR，并通过 Harness v0.5 Candidate Deployment Gate 后才能合入。
- 如果 owner/contract 审计没有发现阻碍规范化完成的结构问题，允许 0 个 runtime slice 完成里程碑。

---

## Non-Goals

- 不追求把 `server/websim_payload.py`、`server/news_backend.py` 或前端大页面拆到某个行数阈值。
- 不以测试数量增长、40/40 覆盖、API 200 或 health 绿灯替代用户语义和证据等级判断。
- 不处理新的推荐算法、BiS、赛季内容、Chickenbro 能力、UI 改版或正式发布需求。
- 不切换数据库、不执行 migration、不主动触发 sync/backfill、不清理生产数据。
- 不把 GitHub CI、候选部署或线上 smoke 变成产品事实 owner。

## Deliverable 1: Current Truth Control Plane

### Design

新增 `docs/project-state.json` 作为机器可读的当前状态索引。`docs/roadmap.md` 继续拥有产品方向和里程碑，但不再承担逐 PR 运行日志；详细发布证据进入历史文档或 release artifact。

`docs/project-state.json` 至少包含：

```json
{
  "schemaVersion": 1,
  "updatedAt": "2026-07-10",
  "activeMilestone": "project_harness_normalization",
  "featureIteration": "frozen_until_milestone_exit",
  "activeReleaseArtifact": "artifacts/releases/2026-07-10-harness-control-plane",
  "activeContracts": [],
  "completedBaselines": [],
  "historicalContracts": [],
  "runtimeBaseline": {},
  "knownRisks": []
}
```

执行要求：

- 把 Phase 4 逐刀长记录从 roadmap 顶部收敛为一条完成摘要，原文完整迁入 `docs/roadmap/history/2026-07-phase4-pg-read-model.md` 或等价历史入口。
- 对账并修正旧 UI handoff 的 active/complete 状态；不能让 roadmap 已验收而 AGENTS/active contract 仍要求继续救火。
- 更新 `docs/README.md`、`docs/plans/README.md` 和 AGENTS 当前读取顺序。
- 新增 contract test，确保 active contract 文件存在、状态不冲突、历史文档不能被列为 active。

### Acceptance

- 新 Session 读取 `AGENTS.md -> docs/project-state.json -> docs/roadmap.md -> domain contract` 即可回答当前里程碑、冻结状态和有效合同。
- roadmap 不再包含逐 PR 级别的顶部长段日志。
- UI、PG read-model 和 Harness 状态各自只有一个 active conclusion。
- 历史文字完整保留，有明确链接，不删除证据。

## Deliverable 2: Executable Requirement And Evidence Contracts

### Design

为 Standard / Strict 工作建立版本化 JSON contract：

- `docs/schemas/harness-requirement.schema.json`
- `docs/schemas/harness-evidence.schema.json`
- `docs/templates/harness-requirement.json`
- `docs/templates/harness-evidence.json`

Requirement packet 最少表达：classification、goal、user value、non-goals、current truth、impact map、ownership、engineering health、acceptance evidence、release trigger、rollback 和 decision log。

Evidence packet 最少表达：requirement slug、branch/commit、scope、verification、highest evidence level、runtime evidence、risks、rollback、cleanup 和 archived references。

扩展 `scripts/project-harness.js`：

```text
node scripts/project-harness.js --check \
  --requirement-file artifacts/releases/2026-07-10-executable-project-harness/requirement.json \
  --evidence-file artifacts/releases/2026-07-10-executable-project-harness/evidence.json \
  --base origin/main
```

每个 PR 在开始实现前必须从下方 registry 选择固定 release directory，并把相对路径写入 `docs/project-state.json.activeReleaseArtifact`。每个目录固定包含：

```text
requirement.json
evidence.json
manifest.json
```

`scripts/verify-project.js --release <release-directory>` 负责把 requirement/evidence 路径透传给 Harness；未显式传 `--release` 时，只允许从 `docs/project-state.json.activeReleaseArtifact` 解析，缺失或存在多个 active release 时必须失败。CI 使用同一解析规则。

Control plane PR 是唯一 bootstrap 例外：它负责首次创建 `project-state.json` 和自己的 requirement/evidence packet，因此只能使用当前 v0.5 manifest + 人工 local CR，最高声明 `local_verified`。Executable Harness PR 必须先用新 validator 追溯验证 bootstrap packet，之后不再允许 bootstrap 例外。

本里程碑的 release directory registry 固定如下，同一时刻只有当前 PR 对应目录可以出现在 `activeReleaseArtifact`：

1. `artifacts/releases/2026-07-10-harness-control-plane`
2. `artifacts/releases/2026-07-10-executable-project-harness`
3. `artifacts/releases/2026-07-10-critical-contract-characterization`
4. `artifacts/releases/2026-07-10-harness-runtime-slice-01`
5. `artifacts/releases/2026-07-10-harness-runtime-slice-02`
6. `artifacts/releases/2026-07-10-harness-runtime-slice-03`
7. `artifacts/releases/2026-07-10-project-harness-normalization`

未执行的 runtime slice directory 不创建。不得为同一 PR 临时生成第二个 active packet。

`--check` 必须在以下情况返回非零：

- JSON 结构或枚举非法。
- Standard / Strict 缺 current truth、impact map、owner、验收或 rollback。
- 需求还未 `implementation_allowed` 就声明实现证据。
- evidence level 高于实际证据能够证明的等级。
- runtime surface 改动声明 `live_verified`，但缺 candidate identity、smoke、timer backflow 或 rollback。
- artifact 引用不存在，或 requirement/evidence slug 不一致。
- critical changed file 没有 owner map 命中。

### Acceptance

- 先写 invalid fixture 红测，再实现 validator。
- 正常 packet 返回 0；每类违规 fixture 返回非零和稳定 reason code。
- 脚本不执行 packet 内命令，不部署，不联网，不写生产。
- schema 和 validator 一致，不能出现 schema 允许而脚本拒绝的无解释分叉。

## Deliverable 3: Project Owner And Contract Map

### Design

新增 `docs/project-owner-map.json`，作为全项目一级 owner map；现有 `docs/backend-owner-map.json` 保留为三个后端热点的二级细节。

一级 map 的 critical-domain baseline 在开始实现前冻结为以下 **16 个 ID**；子项可以细化，但不能新增、删除或改名后继续用零计数结束里程碑。确需改变清单时必须回到用户决策：

1. `app_shell_route_runtime`
2. `frontend_api_auth_transport`
3. `personal_build_template_assets`
4. `news_content_public_api`
5. `websim_gear_public_read_model`
6. `websim_talent_public_read_model`
7. `websim_loot_assets_bootstrap`
8. `simc_template_task_pipeline`
9. `chickenbro_session_evidence_pipeline`
10. `external_source_provenance`
11. `postgres_runtime_schema_boundary`
12. `cache_sync_state_repository`
13. `scheduled_sync_backfill_cleanup`
14. `health_admin_observability`
15. `deploy_runtime_services`
16. `ui_runtime_evidence`

每个 critical domain 至少记录：

```json
{
  "id": "websim_gear_public_read_model",
  "factOwner": "server/gear_public_contract.py",
  "writeOwner": null,
  "consumers": [],
  "publicContracts": [],
  "mustNotChange": [],
  "characterization": [],
  "runtimeSurfaces": [],
  "runbooks": [],
  "rollback": []
}
```

新增 `tests/project-owner-map.test.js`，验证：

- id 唯一，owner/consumer/test/runbook 路径存在。
- critical domain 不允许没有 fact owner。
- 有写入行为的 domain 必须声明 write owner。
- 前端不能成为 backend source/status/verified 判断的 fact owner。
- health/admin 和 deploy 只能是 consumer/orchestrator，不能成为产品事实 owner。
- `project-owner-map` 与 `backend-owner-map` 的重叠 owner 不冲突。

### Acceptance

- 上述 16 个 critical domain 全部能从 changed path 映射到 owner、tests、verification profile 和 release trigger；`ui_runtime_evidence` 必须显式覆盖当前 `app.json` 的 14 个 route。
- `unownedCriticalDomains=0`、`conflictingFactOwners=0`。
- 未准备拆分的 write/sync owner 可以标 `health_watch`，但不能保持未定义。

## Deliverable 4: Verification Profiles And CI Baseline

### Design

新增 `scripts/verify-project.js` 和 `docs/verification-matrix.md`，统一以下 profile：

| Profile | 用途 | 最低命令 |
| --- | --- | --- |
| `harness` | docs/schema/owner/tooling | harness tests、owner/state contract tests、JSON validation、`node --check`、`git diff --check` |
| `backend` | Python backend/data/read model | 目标测试、Python 全量、`compileall`、Harness check |
| `frontend` | 小程序 JS/WXML/WXSS contract | Node 全量、JS syntax、Harness check；UI 运行证据另行收集 |
| `full` | 里程碑/PR 收口 | Python 全量 + Node 全量 + syntax/JSON/diff + Harness check |

示例：

```text
node scripts/verify-project.js --profile full --release artifacts/releases/2026-07-10-executable-project-harness
```

该脚本只编排本地验证，不自动部署。实际 runtime/UI/PG evidence 仍由对应 Gate 收集。

新增 `.github/workflows/project-harness.yml`，在 PR 上从 `docs/project-state.json.activeReleaseArtifact` 解析当前 packet，并运行 `harness` 和 `full` profile。不得通过跳过测试、吞掉退出码或把失败标为 allow-failure 来制造绿灯。若 clean GitHub runner 缺少仓库未声明的依赖，里程碑保持 `health_blocked`、feature freeze 不解除；先如实记录 blocker，再由用户单独决定依赖治理，不在本任务中静默安装。

### Acceptance

- 本地一个命令可重复跑完整基线。
- CI 和本地使用同一入口及同一个 active release packet，不维护两套命令或 packet 发现逻辑。
- targeted test 失败、schema 无效、owner 冲突或完整测试失败时，profile 返回非零。
- runtime candidate deploy 不会被 CI 或本地 full profile隐式触发。

## Deliverable 5: Critical Contract Characterization Baseline

### Design

使用 owner map 审计冻结的 16 个 critical domain，优先引用现有 tests/fixtures；只有缺口才新增 characterization：

1. `app_shell_route_runtime`：app.json routes、tab bar、safe area 和 route open contract。
2. `frontend_api_auth_transport`：API base URL、Bearer 安全边界、错误/空态 transport。
3. `personal_build_template_assets`：模板 CRUD、owner isolation、本地/账号资产边界。
4. `news_content_public_api`：source fidelity、translation status 和 content API envelope。
5. `websim_gear_public_read_model`：observed-only、baseline-empty、legality 和 structured payload。
6. `websim_talent_public_read_model`：talent readiness、authority、community template applicability。
7. `websim_loot_assets_bootstrap`：loot/assets/bootstrap envelope、season gate 和 blocker 传播。
8. `simc_template_task_pipeline`：serializer、task snapshot、owner isolation、deterministic fallback。
9. `chickenbro_session_evidence_pipeline`：session/job owner、evidence/allowed-number、fallback。
10. `external_source_provenance`：Battle.net/Raider.IO/WCL/SimC source key、freshness 和 fail-closed。
11. `postgres_runtime_schema_boundary`：PG-only、schema owner、no SQLite fallback。
12. `cache_sync_state_repository`：sync-state read/write owner 和 health partial semantics。
13. `scheduled_sync_backfill_cleanup`：timer ownership、idempotency、backflow 和 async-sync-off。
14. `health_admin_observability`：只消费权威状态，不升级 partial/blocked。
15. `deploy_runtime_services`：deploy、systemd、rollback 和 runtime hash parity。
16. `ui_runtime_evidence`：当前 14-route proof matrix 和 DevTools evidence rule。

每条链路必须得到一个结论：

- `characterized`：现有测试足够并有 owner-map 引用。
- `gap_closed`：新增 characterization 后关闭。
- `health_watch`：当前可接受，但明确风险和后续触发条件。
- `blocked`：阻止规范化里程碑结束。

### Acceptance

- critical contract 没有 `unknown`。
- `blocked=0` 才允许结束里程碑。
- 现有 accepted UI evidence 如果相关源码未变，可通过 hash/manifest parity 继续引用；源码已变、证据缺失或状态冲突时才安全地重采集对应 route，不能用旧截图越权。

## Deliverable 6: Bounded Structural Remediation

### Entry Rule

只有同时满足以下条件才允许进入结构修复：

- owner map 证明同一 critical fact 被多个模块判断，或没有稳定 owner。
- characterization 已固定当前行为。
- 可以通过一个小 helper/selector/adapter/repository facade 解决。
- 不触达产品语义，不重构 sync/write/backfill/cleanup。
- 单个 slice 可独立测试、review、rollback 和候选部署。

### Execution Rule

- 最多 3 个 runtime slice；每个单独 branch/PR。
- 先红测，再最小实现，再等价/contract 验证。
- 不按行数目标连续机械拆分。
- runtime slice 必须走 Candidate Deployment Gate。
- UI slice 必须走真实 WeChat route evidence；backend slice 必须走 API/PG/systemd/log/hash parity smoke。

### Acceptance

- 允许 `sliceCount=0`。
- 每个执行过的 slice 都有独立 release artifact 和 rollback。
- 超过 3 个或需要 write/sync 结构重构时停止，并形成下一阶段提案，不继续自动扩大范围。

## Deliverable 7: Milestone Closure

完成时生成：

- `artifacts/releases/2026-07-10-project-harness-normalization/requirement.json`
- `artifacts/releases/2026-07-10-project-harness-normalization/evidence.json`
- `artifacts/releases/2026-07-10-project-harness-normalization/manifest.json`
- Harness normalization closure audit。

退出条件必须全部满足：

1. `docs/project-state.json` 是唯一机器可读当前状态入口，文档无 active-state 冲突。
2. Standard / Strict requirement 与 evidence packet 可被 `--check` 机器拒绝或接受。
3. 冻结的 16 个 critical domain 全部存在，`unownedCriticalDomains=0`、`conflictingFactOwners=0`、critical contract `unknown=0`、`blocked=0`。
4. `node scripts/verify-project.js --profile full --release artifacts/releases/2026-07-10-project-harness-normalization` 通过。
5. Python 全量、Node 全量、syntax、JSON、diff check 通过。
6. CI 使用同一验证入口并至少有一次实际绿色 PR 证据；CI/platform blocker 不允许作为里程碑退出例外。
7. 所有 runtime 改动均有候选部署证据；若没有 runtime 改动，明确记录 `candidateDeployment=not_applicable`。
8. roadmap、docs index、owner map 和 artifact 已归档。
9. PR 已合入，工作树 clean，`HEAD == origin/main`。
10. 若触达云端 runtime，线上代码 hash/parity、health/API/systemd/log smoke 通过；未触达则不为文档/工具改动做无意义部署。

全部满足后，`featureIteration` 才能从 `frozen_until_milestone_exit` 改为 `allowed_under_harness`。

## Execution Checklist

### Task 1: Current Truth Contract

**Files:**

- Create: `docs/project-state.json`
- Create: `docs/roadmap/history/2026-07-phase4-pg-read-model.md`
- Create: `tests/project-state.test.js`
- Create: `artifacts/releases/2026-07-10-harness-control-plane/requirement.json`
- Create: `artifacts/releases/2026-07-10-harness-control-plane/evidence.json`
- Create: `artifacts/releases/2026-07-10-harness-control-plane/manifest.json`
- Modify: `AGENTS.md`, `docs/roadmap.md`, `docs/README.md`, `docs/plans/README.md`
- Modify only after evidence reconciliation: the three 2026-07-08 UI current-delivery contracts

- [ ] Write failing tests for missing project state, conflicting active contracts and historical documents listed as active.
- [ ] Run `node --test tests/project-state.test.js` and confirm the intended failures.
- [ ] Add the minimal project-state/index/history changes without altering product contracts.
- [ ] Set exactly one `activeReleaseArtifact`; use current v0.5 manifest + local CR for the documented bootstrap exception.
- [ ] Re-run the target test and `git diff --check`.
- [ ] Local CR the current-truth read order and open the Control plane PR.

### Task 2: Requirement And Evidence Validator

**Files:**

- Create: `docs/schemas/harness-requirement.schema.json`
- Create: `docs/schemas/harness-evidence.schema.json`
- Create: `docs/templates/harness-requirement.json`
- Create: `docs/templates/harness-evidence.json`
- Modify: `scripts/project-harness.js`
- Modify: `tests/project-harness.test.js`

- [ ] Add invalid fixtures/tests for every nonzero failure class described in Deliverable 2.
- [ ] Run `node --test tests/project-harness.test.js` and confirm red behavior.
- [ ] Implement only local JSON/contract validation and stable reason codes.
- [ ] Prove packet commands are never executed and paths cannot escape the repository.
- [ ] Retroactively validate the Control plane bootstrap packet, then remove any code path that could create a second bootstrap exception.
- [ ] Run target tests, JSON validation and `node --check scripts/project-harness.js`.

### Task 3: Project Owner Map

**Files:**

- Create: `docs/project-owner-map.json`
- Create: `tests/project-owner-map.test.js`
- Modify: `docs/backend-owner-map.json` only to add a non-conflicting cross-reference if needed
- Modify: `scripts/project-harness.js`

- [ ] Write red tests for duplicate/unowned critical domains, missing write owners, invalid paths and owner-role violations.
- [ ] Populate the project map from current code/tests/runbooks; do not invent future ownership as current fact.
- [ ] Integrate changed-path owner lookup into Harness check.
- [ ] Run both owner-map test suites and project-harness tests.
- [ ] Review every `health_watch` and record its trigger, not a vague follow-up.

### Task 4: Verification Profiles And CI

**Files:**

- Create: `scripts/verify-project.js`
- Create: `tests/verify-project.test.js`
- Create: `docs/verification-matrix.md`
- Create: `.github/workflows/project-harness.yml`

- [ ] Write red tests proving profile command selection and exit-code propagation.
- [ ] Implement `harness`, `backend`, `frontend` and `full` profiles without deploy side effects.
- [ ] Make CI invoke the same script and no duplicate command list.
- [ ] Run each local profile with its fixed `--release` directory, then open/update the Executable Harness PR.
- [ ] Inspect the real PR check result; do not declare CI green from workflow syntax alone.

### Task 5: Critical Contract Matrix

**Files:**

- Modify: `docs/project-owner-map.json`
- Modify: existing tests/fixtures only where Deliverable 5 identifies an actual gap
- Create: release evidence for the characterization audit

- [ ] Map each of the frozen 16 critical domains to existing characterization and runtime evidence.
- [ ] Add one failing characterization at a time only for genuine gaps.
- [ ] Run the narrow target test, then the relevant backend/frontend profile.
- [ ] Resolve every chain to `characterized`, `gap_closed`, `health_watch` or `blocked`.
- [ ] Stop if `blocked` requires product, write-path or dependency decisions.

### Task 6: Conditional Runtime Slices

**Files:** Determined by the owner-map finding; each slice must declare its own exact write set before editing.

- [ ] If no entry-rule finding exists, record `sliceCount=0` and skip this task.
- [ ] For each accepted finding, write a characterization/red test before the helper/adapter change.
- [ ] Implement the smallest behavior-preserving delegation and run target/full verification.
- [ ] Open a separate PR, candidate deploy the exact branch, and record smoke/hash/timer evidence.
- [ ] Stop at 3 slices even if additional opportunities remain.

### Task 7: Closure And Feature-Unfreeze

**Files:**

- Create: normalization `requirement.json`, `evidence.json`, `manifest.json` and closure audit
- Modify: `docs/project-state.json`, `docs/roadmap.md`, `docs/README.md`, `docs/plans/README.md`

- [ ] Run `node scripts/project-harness.js --check` against the final packet.
- [ ] Run `node scripts/verify-project.js --profile full` and inspect real CI status.
- [ ] Confirm all ten milestone exit conditions and record any accepted `health_watch`.
- [ ] Merge the Closure PR and sync local `main` with `origin/main`.
- [ ] Only then set `featureIteration=allowed_under_harness` and report the exact final commit.

## Pull Request Strategy

建议按以下 PR 边界执行：

1. **Control plane PR**：project state、roadmap/history、docs indexes、active contract 对账。
2. **Executable Harness PR**：schemas、templates、validator、owner map、verification profiles、CI。
3. **Characterization PR**：只补关键合同缺口，不改变 runtime 行为。
4. **Runtime slice PR 0-3 个**：仅在满足 entry rule 时创建，每个独立候选部署。
5. **Closure PR**：最终 evidence、roadmap 状态、feature freeze 解除。

Docs/tooling-only PR 不触发云部署。任何包含 backend/API/PG read model/public payload/health/admin/job/deploy/UI runtime 的 PR 都按对应 Gate 验证。

## Required Verification

每个相关阶段至少运行：

```bash
node --test tests/project-harness.test.js tests/project-owner-map.test.js tests/project-state.test.js tests/verify-project.test.js
python3 -m unittest discover -s tests -p '*_test.py'
node --test tests/*.test.js
python3 -m compileall -q server tests
node --check scripts/project-harness.js
node --check scripts/verify-project.js
find docs artifacts -name '*.json' -print0 | xargs -0 -n1 python3 -m json.tool >/dev/null
git diff --check
```

目标测试文件尚未创建时，只运行当前已存在的测试；新增文件必须按 TDD 先红后绿。

## Candidate Deployment Contract

如果任一 PR 触达 backend/API/PG read model/runtime，默认命令：

```bash
WOW_DEPLOY_SKIP_BOOTSTRAP=1 WOW_DEPLOY_START_ASYNC_SYNCS=0 ./server/deploy_lighthouse.sh
```

smoke 至少覆盖：

- `/health`
- `/api/data/health`
- `/api/websim/bootstrap`
- `/api/websim/assets`
- `/api/websim/talents`
- `/api/websim/gear` initial + slot
- 40-spec observed-only gear sweep
- 变更相关 endpoint
- backend/nginx/sync/backfill service/timer 状态
- 近期日志无 Traceback/ERROR/SQLite fallback
- 关键 runtime 文件 hash parity

候选部署必须先于合入。部署命令不得启动 async sync；既有 timer backflow 必须单独记录。

## Stop Conditions

仅在以下情况停止并回到用户：

- current truth 冲突无法从代码、roadmap、runbook 或 live evidence 判定。
- full verification、CI 或候选 smoke 失败，且存在多个修复/降级选择。
- 需要改变产品承诺、公开入口、数据可信边界或 feature freeze 范围。
- 需要超过 3 个 runtime slice，或必须进入 sync/write/backfill/cleanup 重构。
- 需要依赖安装、第三方下载、remote 修改、force push、生产数据写入或破坏性操作。
- 工作树、PR 或远端发生冲突，继续可能覆盖其他改动。

除此之外，新 Goal Session 应按 Autonomous Progression Gate 持续推进到里程碑收口。

## Goal Session Prompt

```text
你在 /Users/boyuan/Documents/wow_mini_program 继续推进项目。

本次 Goal：完成“Project Harness Engineering Normalization”里程碑。用户已确认 B 路线：先阶段性完成项目 Harness 工程规范化，再恢复需求和功能迭代。不要实现新需求，不要做产品功能迭代，不要把任务扩成无边界的大重构。

启动顺序：
1. 按 AGENTS.md 执行，检查当前 Superpowers skills。
2. 先执行 git status --short --branch；如果工作树不 clean，保护现有改动并停止，不得携带未知 diff 开始本 Goal。
3. 确认 clean 后执行 git switch main，再执行 git pull --ff-only origin main，并确认 git rev-parse HEAD == git rev-parse origin/main。
4. 读取：
   - docs/roadmap.md 顶部
   - docs/harness.md
   - docs/README.md
   - docs/backend-owner-map.json
   - docs/plans/2026-07-10-project-harness-normalization-goal-plan.md
   - docs/plans/2026-07-09-harness-guided-project-optimization-plan.md
5. 只有完成以上检查后才新建 codex/ 开头分支，从 Control plane PR 开始。

严格范围：
- 冻结新需求、新功能、推荐逻辑、UI 重设计和产品语义调整，直到本里程碑退出条件全部满足。
- 不改变公开装备入口：communityTemplates 只允许 active raiderio_observed_profile；baselineTemplates 公开默认为空；recommended_bis、season_recommendation、default_template、simc_preset、baseline_blocked 不得回流。
- 后端继续拥有结构化事实，前端只消费结果。
- 不重构 sync/write/backfill/cleanup，不执行 migration，不主动触发数据写入任务。
- 不新增第三方运行时依赖；下载、安装、clone、submodule、改 remote、force push 或生产数据写入仍需明确授权。
- 结构修复最多 3 个 runtime slice；只有 owner map + characterization 证明必须修复时才进入。允许 0 个 runtime slice 完成里程碑。

按计划依次完成：
A. Current Truth Control Plane
- 新增 docs/project-state.json。
- 把 roadmap 顶部逐 PR 长日志收敛为完成摘要，原文完整归档到历史入口。
- 对账 UI active/complete 状态，更新 AGENTS.md、docs/README.md、docs/plans/README.md，消除 active-state 冲突。
- 先写 current-state contract 红测，再最小实现。

B. Executable Harness
- 新增 versioned requirement/evidence schemas 和 templates。
- 扩展 scripts/project-harness.js：支持 --requirement-file、--evidence-file、--check、--base。
- invalid packet、非法 evidence promotion、runtime 缺 candidate evidence、critical changed file 无 owner 时必须非零退出并给稳定 reason code。
- Harness 只读取本地内容，不执行 packet 中命令，不部署、不 SSH、不联网、不写生产。

C. Project Owner Map
- 新增 docs/project-owner-map.json，覆盖 frontend、backend、read model、repository、jobs/timers、health/admin、deploy/runtime、external adapters。
- critical domain 清单严格冻结为计划中的 16 个 ID；不得通过漏登记或临时扩张清单来满足/阻塞零计数退出条件。
- 保留 docs/backend-owner-map.json 作为三个后端热点的二级细节。
- 新增 contract tests：unownedCriticalDomains=0、conflictingFactOwners=0；有写行为必须有 writeOwner；frontend/health/admin/deploy 不能越权成为 backend 产品事实 owner。

D. Verification Profiles
- 新增 scripts/verify-project.js 和 docs/verification-matrix.md。
- 支持 harness/backend/frontend/full profile；本地与 CI 使用同一入口。
- 每个 PR 必须使用计划 registry 中的固定 release packet，并通过 `--release` 显式传入；CI 从 docs/project-state.json.activeReleaseArtifact 解析同一 packet。
- 只有第一个 Control plane PR 允许计划中定义的 bootstrap 例外；Executable Harness PR 必须追溯验证它，之后禁止例外。
- 新增 .github/workflows/project-harness.yml；不得吞失败、跳过测试或 allow-failure。
- CI/platform blocker 保持 health_blocked 和 feature freeze，不允许降级为里程碑完成。
- 验证脚本绝不能隐式候选部署。

E. Critical Contract Characterization
- 审计并引用/补齐：public gear、talent authority、SimC、Chickenbro、news、auth/personal templates、PG-only/no SQLite fallback、sync-state/health、14-route UI proof、deploy/timer/hash parity。
- 每条只能是 characterized、gap_closed、health_watch 或 blocked；unknown 必须清零，blocked 必须清零才能结束。
- 先复用现有测试；只有真实缺口才新增 characterization。

F. Bounded Structural Remediation
- 仅当 critical fact 多 owner/无 owner 且小 helper/selector/adapter 能关闭问题时执行。
- 每刀 characterization/red test -> 最小实现 -> 目标/全量验证 -> local CR -> 独立 PR。
- 最多 3 刀；不按行数机械拆文件，不进入 sync/write/backfill/cleanup。
- runtime 刀必须先候选部署 smoke，再合入。

G. Closure
- 生成 requirement/evidence/manifest 和 closure audit。
- 更新 project-state、roadmap、owner map、docs indexes。
- 全部退出条件满足后才把 featureIteration 改为 allowed_under_harness。
- 合入全部 PR，同步 main，确认工作树 clean 且 HEAD == origin/main。

本地验证至少运行：
- 目标 tests
- ACTIVE_RELEASE=$(jq -r '.activeReleaseArtifact' docs/project-state.json) && node scripts/verify-project.js --profile full --release "$ACTIVE_RELEASE"
- python3 -m unittest discover -s tests -p '*_test.py'
- node --test tests/*.test.js
- python3 -m compileall -q server tests
- node --check scripts/project-harness.js
- node --check scripts/verify-project.js
- 全部 JSON validation
- git diff --check

如果触达 backend/API/PG read model/runtime，必须按 Harness v0.5 Candidate Deployment Gate，在 PR branch 合入前执行：
WOW_DEPLOY_SKIP_BOOTSTRAP=1 WOW_DEPLOY_START_ASYNC_SYNCS=0 ./server/deploy_lighthouse.sh

候选 smoke 至少覆盖 /health、/api/data/health、WebSim bootstrap/assets/talents/gear initial+slot、40-spec observed-only gear sweep、变更 endpoint、systemd service/timer、近期日志和 runtime hash parity。部署不得启动 async sync，既有 timer backflow 单独记录。

若只改 docs/Harness tooling/tests/CI，不做无意义云端部署，记录 candidateDeployment=not_applicable。

除 current truth 无法判定、验证失败需要权衡、需要改变产品语义、超过 3 个 runtime slice、进入 sync/write 边界、依赖/下载/破坏性操作、生产数据写入或 git 冲突外，不要反复问用户；按 Autonomous Progression Gate 持续推进到 Harness normalization 里程碑完成。
```
