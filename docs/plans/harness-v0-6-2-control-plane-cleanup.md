# Harness v0.6.2 任务证据绑定与旧控制面收敛实施计划

> **执行方法：** 在当前任务分支内使用 TDD 逐项实现；每个行为变更先观察目标测试失败，再写最小实现。Harness 是唯一控制面，本计划不创建 `docs/superpowers` 平行规格或账本。

**目标：** 让 Standard / Strict PR 的 CI 验证本任务自己的完整 release packet，明确 runtime、verification、closure 三类 identity 和人工验收汇总，并删除已失去执行权的旧文档与前端证据。

**架构：** `scripts/verify-project.js` 从 PR diff 中解析唯一任务 release 目录，`.github/workflows/project-harness.yml` 不再读取全局 `activeReleaseArtifact`。`scripts/project-harness.js` 校验 packet identity 与 manual-acceptance 合同；schema、template、Harness 文档和测试共同拥有该合同。旧兼容代码只进入 caller-proof 账本，本任务不删除仍有登记消费者的运行代码。

**技术栈：** Node.js 22+、`node:test`、JSON Schema、GitHub Actions、Markdown/JSON 控制面。

## 全局约束

- 分类为 `Strict`，release trigger 为 `docs_tooling_only`；不修改产品运行时、API、数据库、部署或用户可见行为。
- PR diff 必须解析出唯一完整任务 packet；零个、多个或缺少 requirement/evidence/manifest 都 fail closed。
- `runtimeIdentity`、`verificationIdentity`、`closureIdentity` 不得互相冒充；不适用或尚未发生必须显式标记状态与原因。
- 需要人工验收时，逐项状态只能进入显式矩阵；`accepted`、`not_run_user_waived`、`pending` 的 rollup 必须与条目精确一致。
- 不补造 PR #91/#92 的缺失历史证据，不把旧 packet 或旧截图晋级为当前证明。
- 根 `app.json`、`pages/`、PVE/WCL 和 backend compatibility seam 只有在 caller proof 证明无活跃调用者后才能另任务删除。
- 不增加第二次 full profile、额外独立评审或任何候选部署。

---

### Task 1：建立任务 release packet 和 CI 选择合同

**文件：**

- 修改：`scripts/verify-project.js`
- 修改：`.github/workflows/project-harness.yml`
- 测试：`tests/verify-project.test.js`

**接口：**

- 输入：`--release-from-changes --base <git-ref>`。
- 输出：从 `<base>...HEAD` 变更中解析出的唯一 `artifacts/releases/<slug>`。
- 失败：`task_release_missing`、`task_release_ambiguous`、`task_release_incomplete`。

- [x] RED：新增测试，证明 CI 不再读取 `docs/project-state.json.activeReleaseArtifact`，并覆盖唯一、零个、多个和不完整 packet。
- [x] RED 验证：运行 `node --test tests/verify-project.test.js`，确认失败原因来自缺少 task-scoped resolver。
- [x] GREEN：实现 `--release-from-changes`，保留显式 `--release` 供本地/历史审计使用，并校验 manifest 与同任务 requirement/evidence/Harness 绑定。
- [x] GREEN 验证：重跑 `node --test tests/verify-project.test.js`。

### Task 2：实现 identity 与人工验收 fail-closed 合同

**文件：**

- 修改：`docs/schemas/harness-evidence.schema.json`
- 修改：`docs/templates/harness-evidence.json`
- 修改：`scripts/project-harness.js`
- 测试：`tests/project-harness.test.js`

**接口：**

- `identities.runtime|verification|closure`：每项含允许状态，并在 `bound` 时要求 identity，在 `not_applicable|pending` 时要求原因。
- `manualAcceptance`：包含 `required`、`status`、`items` 和 `rollup`。
- `manualAcceptanceContract.requiredItemIds`：requirement 先冻结完整必验集合，evidence items 必须精确相等。
- `rollup`：`total`、`accepted`、`notRunUserWaived`、`pending` 必须与 items 精确相等。

- [x] RED：新增缺 identity、绑定身份为空、closure 冒充完成、人工汇总不一致和合法 waiver 的测试。
- [x] RED 验证：运行 `node --test tests/project-harness.test.js`，确认新测试按目标 reason code 失败。
- [x] GREEN：实现最小验证逻辑并同步 schema/template。
- [x] GREEN 验证：重跑 `node --test tests/project-harness.test.js`。

### Task 3：升级 Harness 文档与当前状态

**文件：**

- 修改：`docs/harness.md`
- 修改：`docs/verification-matrix.md`
- 修改：`docs/project-state.json`
- 修改：`docs/roadmap.md`
- 修改：`tests/project-state.test.js`

- [x] 更新 Harness 版本、task-scoped packet、identity 和人工验收规则。
- [x] 删除 `activeReleaseArtifact`，改用无 CI 权限的 `defaultLocalReleaseArtifact`，CI 只认任务 diff。
- [x] 把已批准 rule candidate 晋级为活动规则，并登记本任务 release packet。
- [x] 运行 project-state、Harness、owner map 定向测试。

### Task 4：收敛旧文档和前端历史证据

**文件：**

- 删除：`docs/superpowers/**`
- 修改：`docs/gear-simulation-full-chain-runbook.md`
- 修改：`docs/plans/ui-reconstruction.md`
- 修改：`docs/design/current-ui/runtime-review-status.json`
- 删除：`artifacts/ui-runtime-reviews/**`

- [x] 删除 7 份未进入计划白名单的 Superpowers 历史计划/规格。
- [x] 修复装备 runbook 的 Phase 5 过期状态和两条失效计划引用。
- [x] 将 UI 计划中的候选流水压缩为当前状态、当前缺口和当前验收边界。
- [x] 移除 `current:false` 的 superseded runtime artifact 引用和实体；历史保留在 Git。
- [x] 运行 Markdown 路径审计、JSON 解析和 UI 架构审计。

### Task 5：建立兼容代码 caller-proof 退役门禁

**文件：**

- 创建：`docs/compatibility-retirement.json`
- 修改：`docs/project-owner-map.json`
- 修改：`tests/project-owner-map.test.js`

**接口：**

- 每个 compatibility group 登记 `status`、`owners`、`knownCallers`、`tests`、`retirementDecision` 和 `deletionRequirements`。
- 本任务仅允许 `retain_pending_caller_proof` 或 `dormant_product_decision`，不得伪造 `safe_to_delete`。

- [x] RED：新增 owner-map 测试，要求根 14 路由、PVE、WCL 和兼容 backend seam 都有明确生命周期和删除条件。
- [x] GREEN：写入 machine-readable 退役清单并从 owner map 链接。
- [x] GREEN 验证：重跑 owner-map 和 PVE/Simulator 定向测试。

### Task 6：最终验证与证据封装

**文件：**

- 更新：`artifacts/releases/2026-07-19-harness-v0-6-2-control-plane-cleanup/evidence.json`
- 生成：`artifacts/releases/2026-07-19-harness-v0-6-2-control-plane-cleanup/manifest.json`

- [x] 运行 `node scripts/verify-project.js --profile harness --release artifacts/releases/2026-07-19-harness-v0-6-2-control-plane-cleanup --base origin/main`。
- [x] 运行 scoped UI architecture、PVE/WCL、JSON/Markdown 链接审计和 `git diff --check`。
- [x] 执行 whole-diff local CR，修复有效 finding 后复测。
- [x] evidence 只晋级到当前新鲜证据支持的等级；本任务无 runtime/live 声明。
