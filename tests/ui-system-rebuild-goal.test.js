const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

const goalPath = 'docs/plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md'
const twoPartGoalSyncPath = 'docs/plans/2026-07-07-wow-ui-system-two-part-goal-sync.md'
const twoPartGoalSyncManifestPath = 'artifacts/ui-system-rebuild/20260707-two-part-goal-sync/manifest.json'
const twoPartGoalSyncReadmePath = 'artifacts/ui-system-rebuild/20260707-two-part-goal-sync/README.md'
const activationGuardPath = 'docs/design/2026-07-07-wow-ui-system-activation-guard.md'
const activationGuardManifestPath = 'artifacts/ui-system-rebuild/20260707-activation-guard/manifest.json'
const activationGuardReadmePath = 'artifacts/ui-system-rebuild/20260707-activation-guard/README.md'
const inventoryPath = 'docs/plans/2026-07-07-wow-mini-program-ui-system-rebuild-phase1-inventory.md'
const phase1ClosureAuditPath = 'docs/plans/2026-07-07-wow-mini-program-ui-system-rebuild-phase1-2-closure-audit.md'
const phase1ClosureAuditManifestPath = 'artifacts/ui-system-rebuild/20260707-phase1-2-closure-audit/manifest.json'
const phase1ClosureAuditReadmePath = 'artifacts/ui-system-rebuild/20260707-phase1-2-closure-audit/README.md'
const phase3Path = 'docs/design/2026-07-07-wow-ui-system-phase3-design-candidates.md'
const phase3ArtifactManifestPath = 'artifacts/ui-system-rebuild/20260707-phase3-target-candidates/manifest.json'
const phase3ArtifactReadmePath = 'artifacts/ui-system-rebuild/20260707-phase3-target-candidates/README.md'
const targetLockProposalPath = 'docs/design/2026-07-07-wow-ui-system-target-lock-proposal.md'
const targetLockProposalManifestPath = 'artifacts/ui-system-rebuild/20260707-target-lock-proposal/manifest.json'
const targetLockReadinessReviewPath = 'docs/design/2026-07-07-wow-ui-system-target-lock-readiness-review.md'
const targetLockReadinessReviewManifestPath = 'artifacts/ui-system-rebuild/20260707-target-lock-readiness-review/manifest.json'
const targetLockReadinessReviewReadmePath = 'artifacts/ui-system-rebuild/20260707-target-lock-readiness-review/README.md'
const targetLockDecisionRequestPath = 'docs/design/2026-07-07-wow-ui-system-target-lock-decision-request.md'
const targetLockDecisionRequestManifestPath = 'artifacts/ui-system-rebuild/20260707-target-lock-decision-request/manifest.json'
const targetLockDecisionRequestReadmePath = 'artifacts/ui-system-rebuild/20260707-target-lock-decision-request/README.md'
const activationPacketPath = 'docs/plans/2026-07-07-wow-ui-system-target-lock-decision-and-news-list-detail-activation-packet.md'
const activationPacketManifestPath = 'artifacts/ui-system-rebuild/20260707-target-lock-decision-and-news-list-detail-activation-packet/manifest.json'
const activationPacketReadmePath = 'artifacts/ui-system-rebuild/20260707-target-lock-decision-and-news-list-detail-activation-packet/README.md'
const componentContractsPath = 'docs/design/2026-07-07-wow-ui-system-foundation-component-contracts.md'
const componentContractsManifestPath = 'artifacts/ui-system-rebuild/20260707-foundation-component-contracts/manifest.json'
const surfaceOwnerContractsPath = 'docs/design/2026-07-07-wow-ui-system-surface-owner-contracts.md'
const surfaceOwnerContractsManifestPath = 'artifacts/ui-system-rebuild/20260707-surface-owner-contracts/manifest.json'
const surfaceOwnerContractsReadmePath = 'artifacts/ui-system-rebuild/20260707-surface-owner-contracts/README.md'
const newsListDetailOwnerSkeletonPrecheckPath = 'docs/design/2026-07-07-wow-ui-system-news-list-detail-owner-skeleton-precheck.md'
const newsListDetailOwnerSkeletonManifestPath = 'artifacts/ui-system-rebuild/20260707-news-list-detail-owner-skeleton/manifest.json'
const newsListDetailOwnerSkeletonFixturesPath = 'artifacts/ui-system-rebuild/20260707-news-list-detail-owner-skeleton/fixtures.json'
const newsListDetailOwnerSkeletonReadmePath = 'artifacts/ui-system-rebuild/20260707-news-list-detail-owner-skeleton/README.md'
const newsListDetailComponentPrecheckPath = 'docs/design/2026-07-07-wow-ui-system-news-list-detail-component-precheck.md'
const newsListDetailComponentPrecheckManifestPath = 'artifacts/ui-system-rebuild/20260707-news-list-detail-component-precheck/manifest.json'
const newsListDetailComponentPrecheckReadmePath = 'artifacts/ui-system-rebuild/20260707-news-list-detail-component-precheck/README.md'
const chickenbroOwnerSkeletonPrecheckPath = 'docs/design/2026-07-07-wow-ui-system-chickenbro-owner-skeleton-precheck.md'
const chickenbroOwnerSkeletonManifestPath = 'artifacts/ui-system-rebuild/20260707-chickenbro-owner-skeleton/manifest.json'
const chickenbroOwnerSkeletonFixturesPath = 'artifacts/ui-system-rebuild/20260707-chickenbro-owner-skeleton/fixtures.json'
const chickenbroOwnerSkeletonReadmePath = 'artifacts/ui-system-rebuild/20260707-chickenbro-owner-skeleton/README.md'
const chickenbroComponentPrecheckPath = 'docs/design/2026-07-07-wow-ui-system-chickenbro-component-precheck.md'
const chickenbroComponentPrecheckManifestPath = 'artifacts/ui-system-rebuild/20260707-chickenbro-component-precheck/manifest.json'
const chickenbroComponentPrecheckReadmePath = 'artifacts/ui-system-rebuild/20260707-chickenbro-component-precheck/README.md'
const assetManifestDraftPath = 'docs/design/2026-07-07-wow-ui-system-asset-manifest-draft.md'
const assetManifestDraftManifestPath = 'artifacts/ui-system-rebuild/20260707-asset-manifest-draft/manifest.json'
const assetManifestDraftReadmePath = 'artifacts/ui-system-rebuild/20260707-asset-manifest-draft/README.md'
const routeSmokePlanPath = 'docs/design/2026-07-07-wow-ui-system-route-smoke-plan.md'
const routeSmokePlanManifestPath = 'artifacts/ui-system-rebuild/20260707-route-smoke-plan/manifest.json'
const routeSmokePlanReadmePath = 'artifacts/ui-system-rebuild/20260707-route-smoke-plan/README.md'
const foundationHarnessDraftPath = 'docs/design/2026-07-07-wow-ui-system-foundation-harness-draft.md'
const foundationHarnessDraftManifestPath = 'artifacts/ui-system-rebuild/20260707-foundation-harness/manifest.json'
const foundationHarnessDraftReadmePath = 'artifacts/ui-system-rebuild/20260707-foundation-harness/README.md'
const productionComponentPrecheckPath = 'docs/design/2026-07-07-wow-ui-system-production-component-precheck.md'
const productionComponentPrecheckManifestPath = 'artifacts/ui-system-rebuild/20260707-production-component-precheck/manifest.json'
const productionComponentPrecheckReadmePath = 'artifacts/ui-system-rebuild/20260707-production-component-precheck/README.md'
const browserComponentPrecheckPath = 'docs/design/2026-07-07-wow-ui-system-browser-component-precheck.md'
const browserComponentPrecheckManifestPath = 'artifacts/ui-system-rebuild/20260707-browser-component-precheck/manifest.json'
const browserComponentPrecheckReadmePath = 'artifacts/ui-system-rebuild/20260707-browser-component-precheck/README.md'
const newsHomePermitDraftPath = 'docs/plans/2026-07-07-wow-ui-system-news-home-implementation-permit-draft.md'
const newsHomePermitDraftManifestPath = 'artifacts/ui-system-rebuild/20260707-news-home-permit-draft/manifest.json'
const newsHomePermitDraftReadmePath = 'artifacts/ui-system-rebuild/20260707-news-home-permit-draft/README.md'
const newsListDetailPermitDraftPath = 'docs/plans/2026-07-07-wow-ui-system-news-list-detail-implementation-permit-draft.md'
const newsListDetailPermitDraftManifestPath = 'artifacts/ui-system-rebuild/20260707-news-list-detail-permit-draft/manifest.json'
const newsListDetailPermitDraftReadmePath = 'artifacts/ui-system-rebuild/20260707-news-list-detail-permit-draft/README.md'
const buildsTabPermitDraftPath = 'docs/plans/2026-07-07-wow-ui-system-builds-tab-implementation-permit-draft.md'
const buildsTabPermitDraftManifestPath = 'artifacts/ui-system-rebuild/20260707-builds-tab-permit-draft/manifest.json'
const buildsTabPermitDraftReadmePath = 'artifacts/ui-system-rebuild/20260707-builds-tab-permit-draft/README.md'
const buildsTabOwnerSkeletonPrecheckPath = 'docs/design/2026-07-07-wow-ui-system-builds-tab-owner-skeleton-precheck.md'
const buildsTabOwnerSkeletonManifestPath = 'artifacts/ui-system-rebuild/20260707-builds-tab-owner-skeleton/manifest.json'
const buildsTabOwnerSkeletonFixturesPath = 'artifacts/ui-system-rebuild/20260707-builds-tab-owner-skeleton/fixtures.json'
const buildsTabOwnerSkeletonReadmePath = 'artifacts/ui-system-rebuild/20260707-builds-tab-owner-skeleton/README.md'
const buildsTabComponentPrecheckPath = 'docs/design/2026-07-07-wow-ui-system-builds-tab-component-precheck.md'
const buildsTabComponentPrecheckManifestPath = 'artifacts/ui-system-rebuild/20260707-builds-tab-component-precheck/manifest.json'
const buildsTabComponentPrecheckReadmePath = 'artifacts/ui-system-rebuild/20260707-builds-tab-component-precheck/README.md'
const chickenbroPermitDraftPath = 'docs/plans/2026-07-07-wow-ui-system-chickenbro-implementation-permit-draft.md'
const chickenbroPermitDraftManifestPath = 'artifacts/ui-system-rebuild/20260707-chickenbro-permit-draft/manifest.json'
const chickenbroPermitDraftReadmePath = 'artifacts/ui-system-rebuild/20260707-chickenbro-permit-draft/README.md'
const workbenchPermitDraftPath = 'docs/plans/2026-07-07-wow-ui-system-workbench-implementation-permit-draft.md'
const workbenchPermitDraftManifestPath = 'artifacts/ui-system-rebuild/20260707-workbench-permit-draft/manifest.json'
const workbenchPermitDraftReadmePath = 'artifacts/ui-system-rebuild/20260707-workbench-permit-draft/README.md'
const workbenchOwnerSkeletonPrecheckPath = 'docs/design/2026-07-07-wow-ui-system-workbench-owner-skeleton-precheck.md'
const workbenchOwnerSkeletonManifestPath = 'artifacts/ui-system-rebuild/20260707-workbench-owner-skeleton/manifest.json'
const workbenchOwnerSkeletonFixturesPath = 'artifacts/ui-system-rebuild/20260707-workbench-owner-skeleton/fixtures.json'
const workbenchOwnerSkeletonReadmePath = 'artifacts/ui-system-rebuild/20260707-workbench-owner-skeleton/README.md'
const workbenchComponentPrecheckPath = 'docs/design/2026-07-07-wow-ui-system-workbench-component-precheck.md'
const workbenchComponentPrecheckManifestPath = 'artifacts/ui-system-rebuild/20260707-workbench-component-precheck/manifest.json'
const workbenchComponentPrecheckReadmePath = 'artifacts/ui-system-rebuild/20260707-workbench-component-precheck/README.md'
const talentTreeCanvasOwnerSkeletonPrecheckPath = 'docs/design/2026-07-07-wow-ui-system-talent-tree-canvas-owner-skeleton-precheck.md'
const talentTreeCanvasOwnerSkeletonManifestPath = 'artifacts/ui-system-rebuild/20260707-talent-tree-canvas-owner-skeleton/manifest.json'
const talentTreeCanvasOwnerSkeletonFixturesPath = 'artifacts/ui-system-rebuild/20260707-talent-tree-canvas-owner-skeleton/fixtures.json'
const talentTreeCanvasOwnerSkeletonReadmePath = 'artifacts/ui-system-rebuild/20260707-talent-tree-canvas-owner-skeleton/README.md'
const talentTreeCanvasComponentPrecheckPath = 'docs/design/2026-07-07-wow-ui-system-talent-tree-canvas-component-precheck.md'
const talentTreeCanvasComponentPrecheckManifestPath = 'artifacts/ui-system-rebuild/20260707-talent-tree-canvas-component-precheck/manifest.json'
const talentTreeCanvasComponentPrecheckReadmePath = 'artifacts/ui-system-rebuild/20260707-talent-tree-canvas-component-precheck/README.md'
const talentSimulatorPermitDraftPath = 'docs/plans/2026-07-07-wow-ui-system-talent-simulator-implementation-permit-draft.md'
const talentSimulatorPermitDraftManifestPath = 'artifacts/ui-system-rebuild/20260707-talent-simulator-permit-draft/manifest.json'
const talentSimulatorPermitDraftReadmePath = 'artifacts/ui-system-rebuild/20260707-talent-simulator-permit-draft/README.md'
const gearDetailPermitDraftPath = 'docs/plans/2026-07-07-wow-ui-system-gear-detail-implementation-permit-draft.md'
const gearDetailPermitDraftManifestPath = 'artifacts/ui-system-rebuild/20260707-gear-detail-permit-draft/manifest.json'
const gearDetailPermitDraftReadmePath = 'artifacts/ui-system-rebuild/20260707-gear-detail-permit-draft/README.md'
const gearDetailOwnerSkeletonPrecheckPath = 'docs/design/2026-07-07-wow-ui-system-gear-detail-owner-skeleton-precheck.md'
const gearDetailOwnerSkeletonManifestPath = 'artifacts/ui-system-rebuild/20260707-gear-detail-owner-skeleton/manifest.json'
const gearDetailOwnerSkeletonFixturesPath = 'artifacts/ui-system-rebuild/20260707-gear-detail-owner-skeleton/fixtures.json'
const gearDetailOwnerSkeletonReadmePath = 'artifacts/ui-system-rebuild/20260707-gear-detail-owner-skeleton/README.md'
const gearDetailComponentPrecheckPath = 'docs/design/2026-07-07-wow-ui-system-gear-detail-component-precheck.md'
const gearDetailComponentPrecheckManifestPath = 'artifacts/ui-system-rebuild/20260707-gear-detail-component-precheck/manifest.json'
const gearDetailComponentPrecheckReadmePath = 'artifacts/ui-system-rebuild/20260707-gear-detail-component-precheck/README.md'
const tasksPermitDraftPath = 'docs/plans/2026-07-07-wow-ui-system-tasks-implementation-permit-draft.md'
const tasksPermitDraftManifestPath = 'artifacts/ui-system-rebuild/20260707-tasks-permit-draft/manifest.json'
const tasksPermitDraftReadmePath = 'artifacts/ui-system-rebuild/20260707-tasks-permit-draft/README.md'
const tasksOwnerSkeletonPrecheckPath = 'docs/design/2026-07-07-wow-ui-system-tasks-owner-skeleton-precheck.md'
const tasksOwnerSkeletonManifestPath = 'artifacts/ui-system-rebuild/20260707-tasks-owner-skeleton/manifest.json'
const tasksOwnerSkeletonFixturesPath = 'artifacts/ui-system-rebuild/20260707-tasks-owner-skeleton/fixtures.json'
const tasksOwnerSkeletonReadmePath = 'artifacts/ui-system-rebuild/20260707-tasks-owner-skeleton/README.md'
const tasksComponentPrecheckPath = 'docs/design/2026-07-07-wow-ui-system-tasks-component-precheck.md'
const tasksComponentPrecheckManifestPath = 'artifacts/ui-system-rebuild/20260707-tasks-component-precheck/manifest.json'
const tasksComponentPrecheckReadmePath = 'artifacts/ui-system-rebuild/20260707-tasks-component-precheck/README.md'
const profileTemplatesPermitDraftPath = 'docs/plans/2026-07-07-wow-ui-system-profile-templates-implementation-permit-draft.md'
const profileTemplatesPermitDraftManifestPath = 'artifacts/ui-system-rebuild/20260707-profile-templates-permit-draft/manifest.json'
const profileTemplatesPermitDraftReadmePath = 'artifacts/ui-system-rebuild/20260707-profile-templates-permit-draft/README.md'
const profileTemplatesOwnerSkeletonPrecheckPath = 'docs/design/2026-07-07-wow-ui-system-profile-templates-owner-skeleton-precheck.md'
const profileTemplatesOwnerSkeletonManifestPath = 'artifacts/ui-system-rebuild/20260707-profile-templates-owner-skeleton/manifest.json'
const profileTemplatesOwnerSkeletonFixturesPath = 'artifacts/ui-system-rebuild/20260707-profile-templates-owner-skeleton/fixtures.json'
const profileTemplatesOwnerSkeletonReadmePath = 'artifacts/ui-system-rebuild/20260707-profile-templates-owner-skeleton/README.md'
const profileTemplatesComponentPrecheckPath = 'docs/design/2026-07-07-wow-ui-system-profile-templates-component-precheck.md'
const profileTemplatesComponentPrecheckManifestPath = 'artifacts/ui-system-rebuild/20260707-profile-templates-component-precheck/manifest.json'
const profileTemplatesComponentPrecheckReadmePath = 'artifacts/ui-system-rebuild/20260707-profile-templates-component-precheck/README.md'
const simcPermitDraftPath = 'docs/plans/2026-07-07-wow-ui-system-simc-implementation-permit-draft.md'
const simcPermitDraftManifestPath = 'artifacts/ui-system-rebuild/20260707-simc-permit-draft/manifest.json'
const simcPermitDraftReadmePath = 'artifacts/ui-system-rebuild/20260707-simc-permit-draft/README.md'
const permitCoverageMatrixPath = 'docs/design/2026-07-07-wow-ui-system-implementation-permit-coverage-matrix.md'
const permitCoverageMatrixManifestPath = 'artifacts/ui-system-rebuild/20260707-permit-coverage-matrix/manifest.json'
const permitCoverageMatrixReadmePath = 'artifacts/ui-system-rebuild/20260707-permit-coverage-matrix/README.md'
const roadmapPath = 'docs/roadmap.md'
const ideasPath = 'docs/roadmap/ideas.md'

function read(path) {
  return fs.readFileSync(path, 'utf8')
}

function readJson(path) {
  return JSON.parse(read(path))
}

function readPngSize(path) {
  const buffer = fs.readFileSync(path)
  assert.equal(buffer.toString('ascii', 1, 4), 'PNG')
  return {
    width: buffer.readUInt32BE(16),
    height: buffer.readUInt32BE(20)
  }
}

test('UI system rebuild goal supersedes pass36 local repair and includes first-class Chickenbro', () => {
  const source = read(goalPath)

  assert.match(source, /WOW 小程序 UI 系统重建/)
  assert.match(source, /停止“继续修 pass36”的旧目标/)
  assert.match(source, /AppShell \/ PageFrame \/ WowPanel \/ MaterialImage \/ GameObjectIcon \/ StatusVisual \/ ActionButton \/ ModuleCard \/ ChannelDock \/ RankedFeed \/ EvidenceLedger \/ ChatShell/)
  assert.match(source, /队长页升为一等 surface/)
  assert.match(source, /## Active Two-Part Goal/)
  assert.match(source, /### Part 1: Codex Goal/)
  assert.match(source, /### Part 2: Project Documentation Goal/)
  assert.match(source, /Codex 当前执行 goal：停止以 pass36\/pass37 局部修补、像素调参、单页 scorecard 或主观“变好看”为推进方式/)
  assert.match(source, /执行顺序固定为：问题登记 -> 组件 owner -> imagegen 低语义素材 manifest -> 真实 WoW 素材 source map -> target lock -> 单 surface implementation permit -> component\/browser precheck -> 真实微信小程序截图 -> overlay\/red-zone\/scorecard -> route smoke -> DevTools action ledger/)
  assert.match(source, /项目文档 goal：把上述 UI 系统重建作为长期产品与工程控制面写进 `docs\/roadmap\.md`、`docs\/roadmap\/ideas\.md`、`docs\/plans\/`、`docs\/design\/` 和测试/)
  assert.match(source, /任何 `runtime_verified \/ final_accepted` 都必须能回链到真实微信小程序截图、目标图、实现图、组件 crop、overlay、red-zone、scorecard、route smoke 和 DevTools action ledger/)
  assert.match(source, /## Current Two-Part Contract/)
  assert.match(source, /Codex execution goal: 当前线程只按 `UI system rebuild` 方法推进/)
  assert.match(source, /Project documentation goal: 项目文档只记录长期方向和证据状态/)
  assert.match(source, /没有 active permit 时不得继续页面级拼形状或像素补丁/)
  assert.match(source, /不能把 Codex 自信、imagegen 整页图、浏览器预检、旧 pass scorecard、单页截图或主观评分写成真实小程序验收/)
  assert.match(source, /## Design Read/)
  assert.match(source, /redesign-overhaul of a dense consumer mini program/)
  assert.match(source, /DESIGN_VARIANCE=7/)
  assert.match(source, /MOTION_INTENSITY=4/)
  assert.match(source, /VISUAL_DENSITY=9/)
  assert.match(source, /## Goal Sync Snapshot/)
  assert.match(source, /Current Codex tool goal: `active`/)
  assert.match(source, /Required split: `Codex Active Goal` defines how Codex executes the work in this thread/)
  assert.match(source, /2026-07-07 two-part sync/)
  assert.match(source, /2026-07-07-wow-ui-system-two-part-goal-sync\.md/)
  assert.match(source, /2026-07-07 activation guard/)
  assert.match(source, /2026-07-07-wow-ui-system-activation-guard\.md/)
  assert.match(source, /## Codex Active Goal/)
  assert.match(source, /### Copyable Goal/)
  assert.match(source, /### Short Version/)
  assert.match(source, /### Execution Contract/)
  assert.match(source, /## Project Documentation Goal/)
  assert.match(source, /## Two-Part Goal Contract/)
  assert.match(source, /Codex 当前执行目标：停止 pass36\/pass37 局部修补、像素调参和单页 scorecard 路线/)
  assert.match(source, /页面实现只能在单 surface active permit 下进行/)
  assert.match(source, /每一步按“组件 owner -> 素材 manifest -> target lock -> 单 surface permit -> component\/browser precheck -> 真实小程序截图 -> route smoke”推进/)
  assert.match(source, /Codex 执行目标只负责“怎么推进这次工作”：先建立可验证 UI 生产系统，再进入页面实现/)
  assert.match(source, /项目文档目标：把 UI 系统重建写进 `docs\/roadmap\.md`、`docs\/roadmap\/ideas\.md`、`docs\/plans\/`、`docs\/design\/` 和测试证据/)
  assert.match(source, /不能把 Codex 自信、浏览器预检、旧 pass scorecard、单页截图、主观评分或 imagegen 整页图当成真实小程序验收/)
  assert.match(source, /Tool status: Codex thread goal is currently `active`/)
  assert.match(source, /does not support rewriting the objective while an active goal is unfinished/)
  assert.match(source, /this file is the precise copyable goal contract for subsequent work/)
  assert.match(source, /Codex 执行 goal：控制当前工作方法/)
  assert.match(source, /项目文档 goal：控制长期方向和证据晋级/)
  assert.match(source, /禁止把草稿、浏览器预检、旧 scorecard、单页截图、主观评分或 imagegen 整页图写成 runtime verified \/ final accepted/)
  assert.match(source, /线程执行目标和项目文档控制面的共同口径/)
  assert.match(source, /draft \/ design_locked \/ component_precheck \/ source evidence/)
  assert.match(source, /旧 pass36\/pass37 目标只作为失败证据、诊断证据和历史上下文/)
  assert.doesNotMatch(source, /Codex Active Execution Goal/)
  assert.doesNotMatch(source, /Project Documentation Control Plane/)
  assert.doesNotMatch(source, /直到外部 active goal 被用户或宿主系统替换/)
  assert.doesNotMatch(source, /## Codex Goal To Use Now/)
  assert.doesNotMatch(source, /### Copyable Codex Goal/)
  assert.doesNotMatch(source, /### Short Codex Goal/)
  assert.doesNotMatch(source, /### Part 1: Codex Active Execution Goal/)
  assert.doesNotMatch(source, /### Part 2: Project Documentation Control Plane/)
})

test('two-part goal sync records Codex goal first and project documentation goal second', () => {
  const source = read(twoPartGoalSyncPath)
  const manifest = readJson(twoPartGoalSyncManifestPath)
  const readme = read(twoPartGoalSyncReadmePath)

  assert.match(source, /^Status: `two_part_goal_sync`$/m)
  assert.match(source, /## Latest Request Handling/)
  assert.match(source, /The user asked to split the update into two visible steps: first provide the Codex goal, then update the project documentation/)
  assert.match(source, /the active tool goal remains open/)
  assert.match(source, /## Step 1: Codex Goal To Use Now/)
  assert.match(source, /先建立可复用、可验证、可解释的 App 级 UI 生产系统/)
  assert.match(source, /没有 active implementation permit 不改核心页面 WXML\/WXSS/)
  assert.match(source, /## Step 2: Project Documentation Update Contract/)
  assert.match(source, /文档只记录方向、边界、证据、状态和下一步/)
  assert.match(source, /当前只能记录 `source evidence` 与 blocked gates/)
  assert.match(source, /## Codex Execution Rules/)
  assert.match(source, /Codex 负责推进当前工作方法/)
  assert.match(source, /Codex 不能把 pass36\/pass37 旧 scorecard、主观评分、单张截图、浏览器预检或 imagegen 整页图当成最终验收/)
  assert.match(source, /## Documentation Control Rules/)
  assert.match(source, /`docs\/roadmap\.md` 记录正式路线、当前状态、证据链接和后续门禁/)
  assert.match(source, /Tests 必须守住状态晋级/)
  assert.doesNotMatch(source, /## Immediate Codex Goal/)
  assert.doesNotMatch(source, /## Part 1: Codex Goal/)
  assert.doesNotMatch(source, /## Part 2: Project Documentation Goal/)
  assert.match(source, /Target lock: `false`/)
  assert.match(source, /Active implementation permit: `false`/)
  assert.match(source, /Page integration allowed: `false`/)
  assert.match(source, /Runtime verified: `false`/)
  assert.match(source, /The next valid transition is explicit user confirmation or written modification of the target lock/)

  assert.equal(manifest.status, 'two_part_goal_sync')
  assert.equal(manifest.codexToolGoalStatus, 'active')
  assert.equal(manifest.codexToolObjectiveRewriteSupportedWhileActive, false)
  assert.equal(manifest.latestUserRequestHandled, 'codex_goal_first_then_project_docs')
  assert.equal(manifest.visibleTwoStepGoalSynced, true)
  assert.equal(manifest.step1CodexGoalToUseNow, true)
  assert.equal(manifest.step2ProjectDocumentationUpdateContract, true)
  assert.equal(manifest.codexGoalPresentedFirst, true)
  assert.equal(manifest.projectDocumentationUpdatedSecond, true)
  assert.equal(manifest.deduplicatedTwoPartDocument, true)
  assert.equal(manifest.activeGoalKeptOpen, true)
  assert.equal(Object.hasOwn(manifest, 'immediateCodexGoal'), false)
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activeImplementationPermit, false)
  assert.equal(manifest.pageIntegrationAllowed, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.finalAccepted, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.match(manifest.step1CodexGoalSummary, /没有 active permit 不改核心页面 WXML\/WXSS/)
  assert.match(manifest.step2ProjectDocumentationGoalSummary, /不能把 Codex 自信、旧 pass 产物、imagegen 整页图/)
  assert.ok(manifest.executionOrder.includes('imagegen low-semantic asset manifest'))
  assert.ok(manifest.executionOrder.includes('real WeChat mini-program screenshots'))
  assert.ok(manifest.forbiddenPromotion.includes('page_integration_without_active_permit'))
  assert.equal(manifest.nextValidTransition, 'explicit user target-lock confirmation or written modification')

  assert.match(readme, /two_part_goal_sync/)
  assert.match(readme, /visibleTwoStepGoalSynced: `true`/)
  assert.match(readme, /step1CodexGoalToUseNow: `true`/)
  assert.match(readme, /step2ProjectDocumentationUpdateContract: `true`/)
  assert.match(readme, /deduplicatedTwoPartDocument: `true`/)
  assert.match(readme, /latestUserRequestHandled: `codex_goal_first_then_project_docs`/)
  assert.match(readme, /targetLocked: `false`/)
  assert.match(readme, /activeImplementationPermit: `false`/)
})

test('activation guard blocks page implementation until explicit target lock and active permit exist', () => {
  const source = read(activationGuardPath)
  const manifest = readJson(activationGuardManifestPath)
  const readme = read(activationGuardReadmePath)

  assert.match(source, /^Status: `activation_guard_blocked_waiting_for_target_lock`$/m)
  assert.match(source, /activationAllowed=false/)
  assert.match(source, /pageIntegrationAllowed=false/)
  assert.match(source, /missing_target_locked_decision_record/)
  assert.match(source, /missing_active_implementation_permit/)
  assert.match(source, /continuation_turn_is_not_confirmation/)
  assert.match(source, /No page WXML\/WXSS implementation is allowed/)
  assert.match(source, /node scripts\/ui-system-activation-preflight\.js --require-activation --json/)
  assert.match(source, /This guard can only prove `activation_guard_blocked_waiting_for_target_lock`/)

  assert.equal(manifest.status, 'activation_guard_blocked_waiting_for_target_lock')
  assert.equal(manifest.preflightScript, 'scripts/ui-system-activation-preflight.js')
  assert.equal(manifest.activationAllowed, false)
  assert.equal(manifest.pageIntegrationAllowed, false)
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activePermit, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.finalAccepted, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.targetLockedDecisionRecordExists, false)
  assert.equal(manifest.firstActivePermitExists, false)
  assert.ok(manifest.blockingReasons.includes('missing_target_locked_decision_record'))
  assert.ok(manifest.blockingReasons.includes('missing_active_implementation_permit'))
  assert.ok(manifest.blockingReasons.includes('continuation_turn_is_not_confirmation'))
  assert.ok(manifest.guardRules.includes('continuation turns do not unlock target lock'))
  assert.ok(manifest.nextValidTransitions.includes('explicit user target-lock confirmation or written modification'))

  assert.match(readme, /activationAllowed=false/)
})

test('Phase 1 inventory records current component owner gaps and evidence limits', () => {
  const source = read(inventoryPath)

  assert.match(source, /scopedSourceEditsAllowed=false/)
  assert.match(source, /`action-button`\s+\|\s+0 page usage/)
  assert.match(source, /`page-frame`\s+\|\s+0 page usage/)
  assert.match(source, /`ChatShell`\s+\|\s+missing/)
  assert.match(source, /`pages\/simulator\/chickenbro`/)
  assert.match(source, /pass36l/)
  assert.match(source, /`strictGateEligible=false`/)
  assert.match(source, /Route Smoke Gap Matrix/)
})

test('Phase 1/2 closure audit proves source gate only and keeps implementation frozen', () => {
  const source = read(phase1ClosureAuditPath)
  const manifest = readJson(phase1ClosureAuditManifestPath)
  const readme = read(phase1ClosureAuditReadmePath)

  assert.match(source, /^Status: `phase1_2_closure_source_evidence`$/m)
  assert.match(source, /Phase 1\/2 is closed as `source_evidence_ready`/)
  assert.match(source, /Core page WXML\/WXSS remains frozen until that permit exists/)
  assert.match(source, /Registered App Pages/)
  assert.match(source, /Asset Manifest Draft/)
  assert.match(source, /DevTools action ledger/)
  assert.match(source, /exactly one active implementation permit/)
  assert.match(source, /This document can only prove `phase1_2_closure_source_evidence`/)
  assert.match(source, /It cannot prove `target_locked`, `active_implementation_permit`, `runtime_verified`, `final_accepted`/)

  assert.equal(manifest.status, 'phase1_2_closure_source_evidence')
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activeImplementationPermit, false)
  assert.equal(manifest.pageIntegrationAuthorized, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.finalAccepted, false)
  assert.ok(manifest.phase1Requirements.some((item) => item.id === 'registered_pages_inventory' && item.status === 'complete_source_evidence'))
  assert.ok(manifest.phase1Requirements.some((item) => item.id === 'core_page_freeze' && item.status === 'complete_source_rule'))
  assert.ok(manifest.phase2Requirements.some((item) => item.id === 'current_problem_register' && item.status === 'complete_source_evidence'))
  assert.ok(manifest.phase2Requirements.some((item) => item.id === 'route_smoke_gap_matrix' && item.status === 'complete_plan'))
  assert.ok(manifest.ownerSystemEvidence.includes('StatusVisual'))
  assert.ok(manifest.ownerSystemEvidence.includes('ChickenbroCoachSurface'))
  assert.ok(manifest.nonPromotionRule.includes('page_integration'))
  assert.ok(manifest.nonPromotionRule.includes('route_smoke_completed'))
  assert.ok(manifest.nextRequiredEvidence.includes('target lock decision or revision'))
  assert.ok(manifest.nextRequiredEvidence.includes('DevTools action ledger'))

  assert.match(readme, /DevTools remains untouched by this artifact/)
  assert.match(readme, /Next gate: target-lock decision or revision/)
})

test('roadmap ideas points to the new UI system rebuild direction', () => {
  const source = read(ideasPath)

  assert.match(source, /UI 系统 two-part goal sync/)
  assert.match(source, /同日再次指出 Codex goal 仍需分两部分并先显式给出/)
  assert.match(source, /Step 1 `Codex Goal To Use Now`/)
  assert.match(source, /Step 2 `Project Documentation Update Contract`/)
  assert.match(source, /WOW 小程序 UI 系统重建目标/)
  assert.match(source, /2026-07-07 用户确认 active Codex goal 重置/)
  assert.match(source, /Codex 执行 goal 和项目文档 goal 两层/)
  assert.match(source, /同日再次要求先给 Codex goal，再更新项目文档/)
  assert.match(source, /同日查询 Codex 工具层 active goal，并补充 `Active Two-Part Goal` \/ `Design Read` \/ `Goal Sync Snapshot`/)
  assert.match(source, /active 未完成时不能重写 objective/)
  assert.match(source, /以 goal 文档的 `Active Two-Part Goal`、`Design Read`、`Goal Sync Snapshot`、`Codex Active Goal` 和 `Project Documentation Goal` 作为后续精确执行口径/)
  assert.match(source, /2026-07-07-wow-mini-program-ui-system-rebuild-goal\.md/)
  assert.match(source, /2026-07-07-wow-mini-program-ui-system-rebuild-phase1-inventory\.md/)
  assert.match(source, /2026-07-07-wow-mini-program-ui-system-rebuild-phase1-2-closure-audit\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-phase3-design-candidates\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-target-lock-proposal\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-target-lock-readiness-review\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-target-lock-decision-request\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-target-lock-decision-and-news-list-detail-activation-packet\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-chickenbro-owner-skeleton-precheck\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-chickenbro-component-precheck\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-builds-tab-owner-skeleton-precheck\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-builds-tab-component-precheck\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-workbench-owner-skeleton-precheck\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-workbench-component-precheck\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-talent-tree-canvas-owner-skeleton-precheck\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-talent-tree-canvas-component-precheck\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-foundation-component-contracts\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-surface-owner-contracts\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-news-list-detail-owner-skeleton-precheck\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-news-list-detail-component-precheck\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-asset-manifest-draft\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-route-smoke-plan\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-foundation-harness-draft\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-production-component-precheck\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-browser-component-precheck\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-news-home-implementation-permit-draft\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-news-list-detail-implementation-permit-draft\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-builds-tab-implementation-permit-draft\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-chickenbro-implementation-permit-draft\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-workbench-implementation-permit-draft\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-talent-simulator-implementation-permit-draft\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-gear-detail-implementation-permit-draft\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-tasks-implementation-permit-draft\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-profile-templates-implementation-permit-draft\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-profile-templates-owner-skeleton-precheck\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-profile-templates-component-precheck\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-simc-implementation-permit-draft\.md/)
  assert.match(source, /2026-07-07-wow-ui-system-implementation-permit-coverage-matrix\.md/)
  assert.match(source, /Phase 3 当前已有 design_candidate_brief、target_candidate_reference、target_lock_proposal、component_contract_draft、asset_manifest_draft、route_smoke_plan_draft、component_harness_draft、component_precheck、browser_component_precheck 和 implementation_permit_draft/)
  assert.match(source, /Part 1 Codex 执行 goal 负责当前工作方法，Part 2 项目文档 goal 负责长期方向、证据链接和状态升级规则/)
  assert.match(source, /imagegen 素材必须先经过 asset manifest draft 的低语义分类、quarantine 和真实 WoW source map 边界/)
  assert.match(source, /浏览器预检、真实小程序截图、overlay\/scorecard 和 route smoke 必须作为分层证据，不能互相替代/)
  assert.match(source, /foundation harness 先暴露 12 个 owner，当前已补齐 AppShell、MaterialImage、StatusVisual、ChatShell 组件骨架，并新增 production component precheck 和 browser component precheck，源码失败项为 0、生成素材 blocker 为 0、三视口浏览器 rect\/crop 失败项为 0/)
  assert.match(source, /`ChannelDock` \/ `RankedFeed` 已移除旧 `ui-v2-1-slices` 硬编码引用/)
  assert.match(source, /首个 `news_home` implementation permit draft 已锁定 allowed files、forbidden actions、data boundary、asset boundary 和 route smoke scenes/)
  assert.match(source, /`news_list_detail` implementation permit draft 已锁定 owner components、当前 source findings、`requestArticleList` \/ `requestArticleDetail` \/ `news-api\.js` ready gates、source_translation、official_verified、approved、official source tier、bodyBlocksZh、source proof、copy source、missing-id\/not-found、无假来源\/假刷新\/隐藏 fallback 和 route smoke scenes/)
  assert.match(source, /新增 `ArticleListBoard`、`ArticleReader`、`BuildsTabSurface`、`TalentTreeCanvas`、`GearLoadoutBoard`、`GearConfigSheet`、`TaskQueueBoard`、`TaskResultReport`、`ProfileIdentityPanel`、`TemplateLibraryBoard` 合同/)
  assert.match(source, /多个 surface 已经单独推进到 source skeleton、fixture matrix 和 surface component precheck/)
  assert.match(source, /仍缺页面 permit 激活、真实小程序截图和 route smoke/)
  assert.match(source, /`news_list_detail`、`builds_tab`、`current_spec_workbench`、`talent_simulator`、`gear_detail`、`tasks`、`profile_templates` 和 `chickenbro` 已推进到对应 owner skeleton \/ fixture matrix \/ surface component precheck/)
  assert.match(source, /真正页面实现仍需单 surface active permit、页面接入、真实小程序截图、overlay\/red-zone、scorecard 和 route smoke/)
  assert.match(source, /资讯列表 \/ 资讯详情 owner skeleton source precheck/)
  assert.match(source, /`ArticleListBoard` 和 `ArticleReader` 组件骨架/)
  assert.match(source, /这只是 `owner_skeleton_source_precheck`/)
  assert.match(source, /资讯列表 \/ 资讯详情 component precheck/)
  assert.match(source, /生成 3 张 viewport screenshot、7 张组件 crop 和 contact sheet/)
  assert.match(source, /这只是 `surface_component_precheck`/)
  assert.match(source, /UI 系统 target lock readiness review/)
  assert.match(source, /UI 系统 target lock decision request/)
  assert.match(source, /审查结论为 `ready_for_user_decision`/)
  assert.match(source, /建议第一个 active permit 选择 `news_list_detail`/)
  assert.match(source, /这只是 `target_lock_readiness_review`/)
  assert.match(source, /UI 系统 target lock \/ news_list_detail activation packet draft/)
  assert.match(source, /先写 target_locked decision record，再只把 `news_list_detail` 转成第一个 active permit/)
  assert.match(source, /planned files、allowed files、forbidden actions、page layer may\/may-not、pre-integration checks、post-integration screenshots\/crops\/overlay\/route smoke\/ledger 和 stop conditions/)
  assert.match(source, /这只是 `activation_packet_draft`/)
  assert.match(source, /炸鸡队长 owner skeleton source precheck/)
  assert.match(source, /新增 `ChickenbroCoachSurface` 组件骨架/)
  assert.match(source, /fixture matrix 覆盖 tab 空态、工作台上下文、生成中、完成证据、失败、话题抽屉、输入聚焦和长消息滚动/)
  assert.match(source, /这只是 `owner_skeleton_source_precheck`/)
  assert.match(source, /当前 `pages\/simulator\/chickenbro` 与 `pages\/simulator\/simulator` 仍未接入/)
  assert.match(source, /炸鸡队长 component precheck/)
  assert.match(source, /生成 3 张 viewport screenshot、8 张组件 crop 和 contact sheet/)
  assert.match(source, /修复 `ChatShell` scroll lane 把输入条推出 owner 边界的问题/)
  assert.match(source, /这只是 `surface_component_precheck`/)
  assert.match(source, /职业专精 tab owner skeleton source precheck/)
  assert.match(source, /新增 `BuildsTabSurface` 组件骨架/)
  assert.match(source, /fixture matrix 覆盖 ready、loading、source_reference、blocked、长文案和缺真实图标/)
  assert.match(source, /职业专精 tab component precheck/)
  assert.match(source, /old_four_entries_preserved=pass/)
  assert.match(source, /不能授权 `pages\/builds\/builds` 接入/)
  assert.match(source, /当前专精工作台 owner skeleton source precheck/)
  assert.match(source, /新增 `WorkbenchCockpitSurface` 组件骨架/)
  assert.match(source, /fixture matrix 覆盖 ready、blocked gear、partial talent、stale、source_reference 和 evidence-expanded/)
  assert.match(source, /当前页面仍未接入/)
  assert.match(source, /当前专精工作台 component precheck/)
  assert.match(source, /使用 production WXSS class names 渲染 workbench fixture matrix/)
  assert.match(source, /生成 3 张 viewport screenshot、8 张组件 crop 和 contact sheet/)
  assert.match(source, /不能授权 `pages\/builds\/workbench` 或 `pages\/builds\/builds` 接入/)
  assert.match(source, /天赋模拟器 TalentTreeCanvas owner skeleton \/ component precheck/)
  assert.match(source, /fixture matrix 覆盖 loading、ready、缺真实图标 fallback、locked path、choice node、save blocked 和 save ready/)
  assert.match(source, /failures=0、warnings=0、horizontalOverflow=0/)
  assert.match(source, /pageIntegration=false、devtoolsTouched=false/)
  assert.match(source, /这只是 `surface_component_precheck`/)
  assert.match(source, /`chickenbro` implementation permit draft 已记录当前 raw 字段暴露、双路由覆盖、ChatShell owner 和证据语言映射边界/)
  assert.match(source, /`current_spec_workbench` implementation permit draft 已锁定 readiness states、owner components、data boundary、asset boundary、forbidden claims 和 route smoke scenes/)
  assert.match(source, /`builds_tab` implementation permit draft 已锁定 owner components、当前 source findings、旧四入口保留、数据边界、真实职业\/专精图标来源、asset boundary 和 `builds_tab_top \/ builds_spec_switch \/ builds_\*_entry` route smoke scenes/)
  assert.match(source, /`talent_simulator` implementation permit draft 已锁定 owner components、当前 source findings、`requestWebsimTalents` \/ `talent-simulator-core` 数据边界、真实天赋图标规则、save-readiness blockers、community import、cross-spec switch、无 DPS\/评分强结论和 route smoke scenes/)
  assert.match(source, /`TalentTreeCanvas`/)
  assert.match(source, /`gear_detail` implementation permit draft 已锁定 owner components、当前 source findings、`requestWebsimGear` \/ `requestWebsimGearStats` 数据边界、真实物品图标规则、16 槽状态、candidate\/variant\/crafted\/enhancement gates、community import、stat snapshot、无 DPS\/BiS\/评分强结论和 route smoke scenes/)
  assert.match(source, /后续 owner skeleton 与 component precheck 已作为单独证据补齐/)
  assert.match(source, /装备详情 \/ 装备模拟 GearLoadoutBoard 与 GearConfigSheet owner skeleton \/ component precheck/)
  assert.match(source, /fixture matrix 覆盖 loading、完整 16 槽、缺核心槽、source_reference、候选列表、variant required、强化上限阻断和社区导入参考态/)
  assert.match(source, /生成 3 张 viewport screenshot、10 张组件 crop 和 contact sheet/)
  assert.match(source, /当前 failures=0、warnings=0、horizontalOverflow=0、pageIntegration=false、devtoolsTouched=false/)
  assert.match(source, /激活前必须重新跑 gear detail component precheck/)
  assert.match(source, /`tasks` implementation permit draft 已锁定 owner components、当前 source findings、`requestSimulatorTasks` \/ `requestSimulatorTaskDetail` 数据边界、guest query 边界、任务状态语义、final non-preview SimC result gate、失败本地化、combat buff 行、无 preview DPS\/假排名\/原始诊断泄漏和 route smoke scenes/)
  assert.match(source, /后续已补 `TaskQueueBoard` \/ `TaskResultReport` owner skeleton、fixture matrix 和 component precheck/)
  assert.match(source, /任务列表 \/ 任务详情 TaskQueueBoard 与 TaskResultReport owner skeleton \/ component precheck/)
  assert.match(source, /fixture matrix 覆盖 loading、empty、error、list ready、queued\/running\/completed\/failed 卡片、guest read、missing id、not found、preview no metric、final result、timeout failure、raw diagnostic guard、context 和 combat buffs/)
  assert.match(source, /生成 3 张 viewport screenshot、10 张组件 crop 和 contact sheet/)
  assert.match(source, /`simc` implementation permit draft 已锁定 owner components、当前 source findings、`simcraft_template` 数据边界、confirm\/submit 双 gate、active task limit、raw SimC 诊断本地化、无 DPS preview 和 route smoke scenes/)
  assert.match(source, /`profile_templates` implementation permit draft 已锁定 owner components、当前 source findings、`currentProfile` \/ `saveProfileDraft` \/ `buildTemplateSummary` \/ `fetchBuildTemplates` \/ `deleteBuildTemplateRemote` 数据边界、本地\/远端同步状态、删除安全、raw token\/openid\/rawString\/simcLines 泄漏禁区/)
  assert.match(source, /后续已补 `ProfileIdentityPanel` \/ `TemplateLibraryBoard` owner skeleton、fixture matrix 和 surface component precheck/)
  assert.match(source, /我的模板 \/ 个人资料 ProfileIdentityPanel 与 TemplateLibraryBoard owner skeleton \/ component precheck/)
  assert.match(source, /fixture matrix 覆盖 guest local-only、formal synced、remote sync loading\/fallback、dirty draft、save failed、long nickname、missing avatar、empty library、loaded library、long title、missing metadata、delete confirm\/cancel\/success\/remote fallback、talent\/gear entry/)
  assert.match(source, /coverage matrix 明确当前 `news_home`、`news_list_detail`、`builds_tab`、`current_spec_workbench`、`talent_simulator`、`gear_detail`、`simc`、`chickenbro`、`tasks`、`profile_templates` 均有 draft permit/)
  assert.match(source, /`missingPermitQueue=\[\]`/)
  assert.match(source, /component_precheck、browser_component_precheck 和 implementation_permit_draft/)
  assert.match(source, /\| WOW 小程序 UI 系统重建目标 \|[^\n]*\| 已采纳 \|/)
  assert.match(source, /\| UI 系统 Phase 1\/2 closure audit \|[^\n]*\| 已采纳 \|/)
  assert.match(source, /\| 当前专精工作台 implementation permit draft \|[^\n]*\| 已采纳 \|/)
  assert.match(source, /\| UI 系统 implementation permit 覆盖矩阵 \|[^\n]*\| 已采纳 \|/)
  assert.match(source, /\| UI 系统 surface-specific owner contracts draft \|[^\n]*\| 已采纳 \|/)
  assert.match(source, /\| 资讯列表 \/ 资讯详情 implementation permit draft \|[^\n]*\| 已采纳 \|/)
  assert.match(source, /\| 资讯列表 \/ 资讯详情 owner skeleton source precheck \|[^\n]*\| 已采纳 \|/)
  assert.match(source, /\| 资讯列表 \/ 资讯详情 component precheck \|[^\n]*\| 已采纳 \|/)
  assert.match(source, /\| UI 系统 target lock readiness review \|[^\n]*\| 已采纳 \|/)
  assert.match(source, /\| UI 系统 target lock decision request \|[^\n]*\| 已采纳 \|/)
  assert.match(source, /\| UI 系统 target lock \/ news_list_detail activation packet draft \|[^\n]*\| 已采纳 \|/)
  assert.match(source, /\| 炸鸡队长 owner skeleton source precheck \|[^\n]*\| 已采纳 \|/)
  assert.match(source, /\| 职业专精 tab owner skeleton source precheck \|[^\n]*\| 已采纳 \|/)
  assert.match(source, /\| 职业专精 tab component precheck \|[^\n]*\| 已采纳 \|/)
  assert.match(source, /\| 当前专精工作台 owner skeleton source precheck \|[^\n]*\| 已采纳 \|/)
  assert.match(source, /\| 当前专精工作台 component precheck \|[^\n]*\| 已采纳 \|/)
  assert.match(source, /\| 天赋模拟器 TalentTreeCanvas owner skeleton \/ component precheck \|[^\n]*\| 已采纳 \|/)
  assert.match(source, /\| 职业专精 tab implementation permit draft \|[^\n]*\| 已采纳 \|/)
  assert.match(source, /\| SimC implementation permit draft \|[^\n]*\| 已采纳 \|/)
  assert.match(source, /\| 天赋模拟器 implementation permit draft \|[^\n]*\| 已采纳 \|/)
  assert.match(source, /\| 装备详情 \/ 装备模拟 implementation permit draft \|[^\n]*\| 已采纳 \|/)
  assert.match(source, /\| 任务列表 \/ 任务详情 implementation permit draft \|[^\n]*\| 已采纳 \|/)
  assert.match(source, /\| 任务列表 \/ 任务详情 TaskQueueBoard 与 TaskResultReport owner skeleton \/ component precheck \|[^\n]*\| 已采纳 \|/)
  assert.match(source, /\| 我的模板 \/ 个人资料 implementation permit draft \|[^\n]*\| 已采纳 \|/)
  assert.match(source, /\| 我的模板 \/ 个人资料 ProfileIdentityPanel 与 TemplateLibraryBoard owner skeleton \/ component precheck \|[^\n]*\| 已采纳 \|/)
})

test('roadmap promotes UI system rebuild into an active milestone with two-part control', () => {
  const source = read(roadmapPath)

  assert.match(source, /2026-07-07 Two-step goal wording sync/)
  assert.match(source, /用户再次指出 Codex goal 需要先给出、再更新项目文档/)
  assert.match(source, /Step 1 是 `Codex Goal To Use Now`/)
  assert.match(source, /Step 2 是 `Project Documentation Update Contract`/)
  assert.match(source, /2026-07-07 WOW UI system rebuild/)
  assert.match(source, /Codex 工具层 active goal 已指向该方向/)
  assert.match(source, /active goal 未完成时不能重写 objective/)
  assert.match(source, /`Active Two-Part Goal`、`Current Two-Part Contract`、`Design Read`、`Goal Sync Snapshot`、`Codex Active Goal` 和 `Project Documentation Goal` 作为后续两段式执行口径/)
  assert.match(source, /Part 1 是 Codex 执行 goal/)
  assert.match(source, /Part 2 是项目文档 goal/)
  assert.match(source, /imagegen 低语义素材 manifest/)
  assert.match(source, /真实 WoW 素材 source map/)
  assert.match(source, /WOW 小程序 UI 系统重建完整 Goal/)
  assert.match(source, /UI 重建必须先通过组件 owner、素材 manifest、target lock、implementation permit、浏览器预检和真实小程序验收/)
  assert.match(source, /移动端 UI 风格与密度 \| 后续小程序 UI 统一遵守“移动端艾泽拉斯分析控制台”规范，并升级为组件 owner 驱动的 UI 系统/)
  assert.match(source, /\| 正在推进 \| WOW 小程序 UI 系统重建 \|/)
  assert.match(source, /不再以 pass36\/pass37 scorecard 或主观“看起来更好”作为通过依据/)
  assert.match(source, /没有这些证据时只能标记 draft \/ design_candidate \/ component_precheck \/ source evidence/)
  assert.match(source, /News Home Permit Draft/)
  assert.match(source, /News List Detail Permit Draft/)
  assert.match(source, /Surface Owner Contracts/)
  assert.match(source, /Chickenbro Permit Draft/)
  assert.match(source, /Workbench Permit Draft/)
  assert.match(source, /Builds Tab Permit Draft/)
  assert.match(source, /Talent Simulator Permit Draft/)
  assert.match(source, /Gear Detail Permit Draft/)
  assert.match(source, /SimC Permit Draft/)
  assert.match(source, /Tasks Permit Draft/)
  assert.match(source, /Profile Templates Permit Draft/)
  assert.match(source, /current_spec_workbench/)
  assert.match(source, /仍不是 active permit，也不是 runtime verified/)
  assert.match(source, /2026-07-07 Builds tab component precheck/)
  assert.match(source, /`builds_tab` 已补充 `BuildsTabSurface` source-level owner skeleton 和 surface-level production\/browser component precheck/)
  assert.match(source, /旧四入口 `talents \/ gear \/ simc \/ tasks` 保留/)
  assert.match(source, /输出 3 张 viewport screenshot、8 张组件 crop 和 contact sheet/)
  assert.match(source, /Builds Tab Owner Skeleton Source Precheck/)
  assert.match(source, /Builds Tab Component Precheck/)
  assert.match(source, /2026-07-07 Workbench component precheck/)
  assert.match(source, /`current_spec_workbench` 已补充 `WorkbenchCockpitSurface` source-level owner skeleton 和 surface-level production\/browser component precheck/)
  assert.match(source, /failures=0、warnings=0、horizontalOverflow=0/)
  assert.match(source, /Workbench Owner Skeleton Source Precheck/)
  assert.match(source, /Workbench Component Precheck/)
  assert.match(source, /2026-07-07 TalentTreeCanvas component precheck/)
  assert.match(source, /`talent_simulator` 已补充 `TalentTreeCanvas` source-level owner skeleton 和 surface-level production\/browser component precheck/)
  assert.match(source, /passive\/active\/choice 节点形状、choice affordance、rank badge、动作轨和证据轨/)
  assert.match(source, /缺真实图标 fallback、locked path、choice node、save blocked 和 save ready/)
  assert.match(source, /TalentTreeCanvas Owner Skeleton Source Precheck/)
  assert.match(source, /TalentTreeCanvas Component Precheck/)
  assert.match(source, /2026-07-07 Tasks component precheck/)
  assert.match(source, /`tasks` 已补充 `TaskQueueBoard` \/ `TaskResultReport` source-level owner skeleton 和 surface-level production\/browser component precheck/)
  assert.match(source, /最终结果 gate、上下文行、战斗准备行、本地化失败说明和 handoff actions/)
  assert.match(source, /preview no metric、final result、timeout failure、raw diagnostic guard、context 和 combat buffs/)
  assert.match(source, /输出 3 张 viewport screenshot、10 张组件 crop 和 contact sheet/)
  assert.match(source, /Tasks Owner Skeleton Source Precheck/)
  assert.match(source, /Tasks Component Precheck/)
  assert.match(source, /2026-07-07 Profile templates component precheck/)
  assert.match(source, /`profile_templates` 已补充 `ProfileIdentityPanel` \/ `TemplateLibraryBoard` source-level owner skeleton 和 surface-level production\/browser component precheck/)
  assert.match(source, /头像 socket、昵称草稿、本地\/正式档案状态、同步受限说明、模板模块、模板卡片、安全 meta chips、空态、删除确认 hooks/)
  assert.match(source, /delete confirm\/cancel\/success\/remote fallback、talent\/gear entry/)
  assert.match(source, /Profile Templates Owner Skeleton Source Precheck/)
  assert.match(source, /Profile Templates Component Precheck/)
  assert.match(source, /2026-07-07 Permit coverage matrix/)
  assert.match(source, /当前 `news_home`、`news_list_detail`、`builds_tab`、`current_spec_workbench`、`talent_simulator`、`gear_detail`、`simc`、`chickenbro`、`tasks`、`profile_templates` 均拥有 draft permit/)
  assert.match(source, /当前核心 runtime surface permit 覆盖已完整/)
  assert.match(source, /2026-07-07 Surface owner contracts/)
  assert.match(source, /`ArticleListBoard`、`ArticleReader`、`TalentTreeCanvas`、`GearLoadoutBoard`、`GearConfigSheet`、`TaskQueueBoard`、`TaskResultReport`、`ProfileIdentityPanel`、`TemplateLibraryBoard`/)
  assert.match(source, /只证明复杂几何已有 owner 合同，不证明 owner skeleton、fixture matrix、component precheck/)
  assert.match(source, /2026-07-07 News list\/detail owner skeleton/)
  assert.match(source, /`news_list_detail` 已从 owner contract draft 推进到 source-level owner skeleton/)
  assert.match(source, /新增 `ArticleListBoard` 与 `ArticleReader` 组件骨架和 fixture matrix/)
  assert.match(source, /不是 target lock、active permit、component\/browser precheck 或 runtime verified/)
  assert.match(source, /News List Detail Owner Skeleton Source Precheck/)
  assert.match(source, /2026-07-07 News list\/detail component precheck/)
  assert.match(source, /surface-level production\/browser component precheck/)
  assert.match(source, /failures=0、warnings=0、horizontalOverflow=0/)
  assert.match(source, /News List Detail Component Precheck/)
  assert.match(source, /2026-07-07 Target lock readiness review/)
  assert.match(source, /ready_for_user_decision/)
  assert.match(source, /A-Cockpit \+ B-Ledger \+ C-Captain/)
  assert.match(source, /建议第一个 active permit 选择 `news_list_detail`/)
  assert.match(source, /Target Lock Readiness Review/)
  assert.match(source, /2026-07-07 Target lock decision request/)
  assert.match(source, /三种明确选择：确认 `A-Cockpit \+ B-Ledger \+ C-Captain`、带书面修改确认、或退回重修 target/)
  assert.match(source, /只有用户明确确认后才允许写 `target_locked` decision record/)
  assert.match(source, /Target Lock Decision Request/)
  assert.match(source, /2026-07-07 Activation packet draft/)
  assert.match(source, /先写 `target_locked` decision record，再只把 `news_list_detail` 转成第一个 active implementation permit/)
  assert.match(source, /只证明 `activation_packet_draft`/)
  assert.match(source, /Target Lock Decision And News List Detail Activation Packet/)
  assert.match(source, /2026-07-07 Chickenbro owner skeleton/)
  assert.match(source, /新增 `ChickenbroCoachSurface` 组件骨架和 fixture matrix/)
  assert.match(source, /将 `answerSource`、`confidence`、`job\.status` 的可见表达收束为玩家语言映射/)
  assert.match(source, /当前 `pages\/simulator\/chickenbro` 与 `pages\/simulator\/simulator` 仍未接入/)
  assert.match(source, /Chickenbro Owner Skeleton Source Precheck/)
  assert.match(source, /Permit Coverage Matrix/)
})

test('Phase 3 design candidates are broad, comparable, and not target locked', () => {
  const source = read(phase3Path)

  assert.match(source, /^Status: `design_candidate_brief`$/m)
  assert.match(source, /does not lock a final target, does not authorize implementation/)
  assert.match(source, /Candidate A: Evidence Cockpit/)
  assert.match(source, /Candidate B: Evidence Ledger/)
  assert.match(source, /Candidate C: Party Operations/)
  assert.match(source, /News home/)
  assert.match(source, /Builds tab/)
  assert.match(source, /Workbench/)
  assert.match(source, /Chickenbro/)
  assert.match(source, /SimC/)
  assert.match(source, /imagegen may not invent class\/spec\/talent\/equipment\/source icons/)
  assert.match(source, /No complete SimC-ready talents plus core gear means no DPS/)
  assert.match(source, /This is not a target lock/)
  assert.match(source, /phase3-target-candidate-contact-sheet\.png/)
  assert.match(source, /Status remains `target_candidate_reference`/)
  assert.doesNotMatch(source, /^Status: `target_locked`$/m)
})

test('Phase 3 target candidate artifact exists and cannot be promoted as runtime evidence', () => {
  const manifest = readJson(phase3ArtifactManifestPath)
  const readme = read(phase3ArtifactReadmePath)

  assert.equal(manifest.status, 'target_candidate_reference')
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.implementationPermit, false)
  assert.deepEqual(manifest.surfaces, ['news', 'builds', 'workbench', 'chickenbro'])
  assert.deepEqual(manifest.candidates.map((candidate) => candidate.id), ['A', 'B', 'C'])
  assert.ok(manifest.factBoundary.some((item) => /No candidate is a runtime screenshot/.test(item)))
  assert.ok(manifest.factBoundary.some((item) => /Real WoW class\/spec\/talent\/equipment\/source icons must come from verified sources/.test(item)))
  assert.ok(manifest.forbiddenPromotion.includes('runtime_verified'))
  assert.ok(manifest.forbiddenPromotion.includes('final_accepted'))
  assert.ok(manifest.nextRequiredEvidence.some((item) => /Component decomposition/.test(item)))

  const sheetPath = manifest.contactSheet
  assert.ok(fs.existsSync(sheetPath), `${sheetPath} should exist`)
  const size = readPngSize(sheetPath)
  assert.ok(size.width >= 1200, `contact sheet width should be reviewable, got ${size.width}`)
  assert.ok(size.height >= 2400, `contact sheet height should include all surfaces, got ${size.height}`)

  assert.match(readme, /Status: `target_candidate_reference`/)
  assert.match(readme, /This is not `target_locked`/)
  assert.match(readme, /The current column uses archived screenshot evidence and is not a new DevTools capture/)
})

test('target lock proposal covers all core surfaces and remains unconfirmed', () => {
  const source = read(targetLockProposalPath)
  const manifest = readJson(targetLockProposalManifestPath)

  assert.match(source, /^Status: `target_lock_proposal`$/m)
  assert.match(source, /This proposal is not `target_locked` until the user confirms it/)
  assert.match(source, /Asset Manifest Draft/)
  assert.match(source, /Route Smoke And Runtime Verification Plan/)
  assert.match(source, /Foundation Harness Draft/)
  assert.match(source, /Production Component Precheck/)
  assert.match(source, /A-Cockpit \+ B-Ledger \+ C-Captain/)
  for (const section of [
    'News Home',
    'News List And Detail',
    'Builds Tab',
    'Current Spec Workbench',
    'Talent Simulator',
    'Gear Simulator / Detail',
    'SimC',
    'Chickenbro',
    'Tasks',
    'Profile / My Templates'
  ]) {
    assert.match(source, new RegExp(`### \\d+\\. ${section.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`))
  }
  for (const owner of [
    'AppShell',
    'PageFrame',
    'WowPanel',
    'MaterialImage',
    'GameObjectIcon',
    'StatusVisual',
    'ActionButton',
    'ModuleCard',
    'ChannelDock',
    'RankedFeed',
    'EvidenceLedger',
    'ChatShell'
  ]) {
    assert.match(source, new RegExp(`\\| \`${owner}\` \\|`))
  }
  assert.match(source, /After target lock, implementation still requires a separate implementation permit/)
  assert.doesNotMatch(source, /^Status: `target_locked`$/m)

  assert.equal(manifest.status, 'target_lock_proposal')
  assert.equal(manifest.sourceAssetManifestDraft, assetManifestDraftPath)
  assert.equal(manifest.assetManifestDraftArtifact, assetManifestDraftManifestPath)
  assert.equal(manifest.sourceRouteSmokePlan, routeSmokePlanPath)
  assert.equal(manifest.routeSmokePlanArtifact, routeSmokePlanManifestPath)
  assert.equal(manifest.sourceFoundationHarnessDraft, foundationHarnessDraftPath)
  assert.equal(manifest.foundationHarnessDraftArtifact, foundationHarnessDraftManifestPath)
  assert.equal(manifest.sourceProductionComponentPrecheck, productionComponentPrecheckPath)
  assert.equal(manifest.productionComponentPrecheckArtifact, productionComponentPrecheckManifestPath)
  assert.equal(manifest.sourceBrowserComponentPrecheck, browserComponentPrecheckPath)
  assert.equal(manifest.browserComponentPrecheckArtifact, browserComponentPrecheckManifestPath)
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.implementationPermit, false)
  assert.equal(manifest.hybrid.name, 'A-Cockpit + B-Ledger + C-Captain')
  assert.deepEqual(manifest.coveredSurfaces, [
    'news_home',
    'news_list',
    'news_detail',
    'builds_tab',
    'current_spec_workbench',
    'talent_simulator',
    'gear_simulator',
    'simc',
    'chickenbro',
    'tasks',
    'profile_templates'
  ])
  assert.deepEqual(manifest.foundationOwners, [
    'AppShell',
    'PageFrame',
    'WowPanel',
    'MaterialImage',
    'GameObjectIcon',
    'StatusVisual',
    'ActionButton',
    'ModuleCard',
    'ChannelDock',
    'RankedFeed',
    'EvidenceLedger',
    'ChatShell'
  ])
  assert.ok(manifest.assetBoundary.quarantineClasses.includes('whole-page target image'))
  assert.ok(manifest.assetBoundary.requiresRealSourceMap.includes('class/spec/hero icons'))
  assert.ok(manifest.routeSmokeSurfaces.includes('chickenbro'))
  assert.ok(manifest.forbiddenPromotion.includes('target_locked_without_user_confirmation'))
  assert.ok(manifest.nextRequiredEvidence.includes('asset manifest draft accepted or revised into production/quarantine/source-map manifest'))
  assert.ok(manifest.nextRequiredEvidence.includes('route smoke plan accepted or revised'))
  assert.ok(manifest.nextRequiredEvidence.includes('separate implementation permit before WXML/WXSS edits'))
})

test('target lock readiness review is ready for user decision but does not promote implementation', () => {
  const source = read(targetLockReadinessReviewPath)
  const manifest = readJson(targetLockReadinessReviewManifestPath)
  const readme = read(targetLockReadinessReviewReadmePath)

  assert.match(source, /^Status: `target_lock_readiness_review`$/m)
  assert.match(source, /ready for a user target-lock decision/)
  assert.match(source, /not `target_locked`, not an active implementation permit, not page integration/)
  assert.match(source, /DESIGN_VARIANCE=6/)
  assert.match(source, /MOTION_INTENSITY=3/)
  assert.match(source, /VISUAL_DENSITY=9/)
  assert.match(source, /A-Cockpit \+ B-Ledger \+ C-Captain/)
  assert.match(source, /Technical readiness for a user decision is now `ready_for_user_decision`/)
  assert.match(source, /Missing external decision/)
  assert.match(source, /Phase 3 target candidate contact sheet covers `news`, `builds`, `workbench`, `chickenbro`/)
  assert.match(source, /Foundation and Surface Owner Contracts exist/)
  assert.match(source, /Route Smoke Plan exists and covers all registered core runtime surfaces/)
  assert.match(source, /The safest first active permit candidate is `news_list_detail`/)
  assert.match(source, /surface-level production\/browser component precheck with 3 viewport screenshots, 7 component crops, failures `0`, warnings `0`, horizontal overflow `0`/)
  assert.match(source, /This document can only prove `target_lock_readiness_review`/)
  assert.match(source, /`active_implementation_permit`/)
  assert.match(source, /`runtime_verified`/)

  assert.equal(manifest.status, 'target_lock_readiness_review')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activePermit, false)
  assert.equal(manifest.pageIntegration, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.finalAccepted, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.sourceReview, targetLockReadinessReviewPath)
  assert.equal(manifest.sourceTargetLockProposal, targetLockProposalPath)
  assert.equal(manifest.sourcePhase3Candidates, phase3Path)
  assert.equal(manifest.sourceFoundationContracts, componentContractsPath)
  assert.equal(manifest.sourceSurfaceOwnerContracts, surfaceOwnerContractsPath)
  assert.equal(manifest.sourceAssetManifestDraft, assetManifestDraftPath)
  assert.equal(manifest.sourceRouteSmokePlan, routeSmokePlanPath)
  assert.equal(manifest.sourcePermitCoverageMatrix, permitCoverageMatrixPath)
  assert.equal(manifest.sourceProductionComponentPrecheck, productionComponentPrecheckPath)
  assert.equal(manifest.sourceBrowserComponentPrecheck, browserComponentPrecheckPath)
  assert.equal(manifest.sourceNewsListDetailComponentPrecheck, newsListDetailComponentPrecheckPath)
  assert.equal(manifest.recommendedTargetName, 'A-Cockpit + B-Ledger + C-Captain')
  assert.equal(manifest.decisionReadiness, 'ready_for_user_decision')
  assert.deepEqual(manifest.designRead, {
    pageKind: 'native WeChat mini-program product UI',
    audience: 'WoW players',
    language: 'dense dark Azeroth evidence cockpit',
    designVariance: 6,
    motionIntensity: 3,
    visualDensity: 9
  })

  const readinessByItem = Object.fromEntries(manifest.checklistReview.map((item) => [item.item, item.readiness]))
  assert.equal(readinessByItem['user confirmation of hybrid or written modification'], 'missing_user_decision')
  assert.equal(readinessByItem['target visual set for news builds workbench Chickenbro'], 'ready_for_decision')
  assert.equal(readinessByItem['surface notes for talent gear SimC tasks profile'], 'ready_for_decision')
  assert.equal(readinessByItem['component decomposition for foundation and surface owners'], 'needs_user_acceptance')
  assert.equal(readinessByItem['asset manifest draft accepted or revised'], 'needs_user_acceptance')
  assert.equal(readinessByItem['route smoke checklist accepted or revised'], 'needs_user_acceptance')
  assert.equal(readinessByItem['implementation permit coverage'], 'ready_for_decision')
  assert.equal(readinessByItem['component precheck baseline'], 'partial_component_precheck')

  assert.ok(manifest.canLockIfUserConfirms.includes('target_locked status for A-Cockpit + B-Ledger + C-Captain'))
  assert.ok(manifest.canLockIfUserConfirms.includes('one active implementation permit at a time'))
  assert.ok(manifest.cannotLockFromThisReview.includes('page WXML/WXSS edits'))
  assert.ok(manifest.cannotLockFromThisReview.includes('active implementation permit'))
  assert.ok(manifest.cannotLockFromThisReview.includes('runtime verification from browser screenshots or component crops'))
  assert.equal(manifest.recommendedFirstActivePermitAfterTargetLock.surface, 'news_list_detail')
  assert.ok(manifest.recommendedFirstActivePermitAfterTargetLock.reason.includes('surface component precheck exists with failures 0 warnings 0 horizontalOverflow 0'))
  for (const forbidden of [
    'target_locked_without_user_confirmation',
    'active_implementation_permit_without_target_lock',
    'page_integration_without_active_permit',
    'runtime_verified_without_real_miniprogram_screenshots',
    'final_accepted_without_full_runtime_evidence'
  ]) {
    assert.ok(manifest.forbiddenPromotion.includes(forbidden), `${forbidden} should be forbidden`)
  }
  for (const nextEvidence of [
    'user confirms or revises target lock',
    'write target_locked decision record only after confirmation',
    'convert exactly one draft into active implementation permit',
    'page integration only under active permit',
    'real mini-program screenshots and route smoke after integration'
  ]) {
    assert.ok(manifest.nextRequiredEvidence.includes(nextEvidence), `${nextEvidence} should be required`)
  }

  assert.match(readme, /Status: `target_lock_readiness_review`/)
  assert.match(readme, /Decision readiness: `ready_for_user_decision`/)
  assert.match(readme, /Recommended target: `A-Cockpit \+ B-Ledger \+ C-Captain`/)
  assert.match(readme, /Target locked: `false`/)
  assert.match(readme, /Active permit: `false`/)
  assert.match(readme, /Runtime verified: `false`/)
  assert.match(readme, /`news_list_detail`, because it already has owner skeletons, fixture matrix and surface component precheck/)
  assert.match(readme, /cannot promote anything to `target_locked`, `active_implementation_permit`, `runtime_verified` or `final_accepted`/)
})

test('target lock decision request exposes explicit user choices without locking target', () => {
  const source = read(targetLockDecisionRequestPath)
  const manifest = readJson(targetLockDecisionRequestManifestPath)
  const readme = read(targetLockDecisionRequestReadmePath)

  assert.match(source, /^Status: `target_lock_decision_request`$/m)
  assert.match(source, /not `target_locked`, not an active implementation permit, not page integration/)
  assert.match(source, /Choose one of these outcomes/)
  assert.match(source, /Confirm recommended target/)
  assert.match(source, /Confirm with modifications/)
  assert.match(source, /Reject \/ revise target/)
  assert.match(source, /Recommended lock:/)
  assert.match(source, /`A-Cockpit \+ B-Ledger \+ C-Captain`/)
  assert.match(source, /Ambiguous approval, silence, "继续", passing tests, or a continuation turn is not sufficient/)
  assert.match(source, /This document can only prove `target_lock_decision_request`/)

  assert.equal(manifest.status, 'target_lock_decision_request')
  assert.equal(manifest.linkedPhase1Closure, phase1ClosureAuditPath)
  assert.equal(manifest.linkedTargetLockProposal, targetLockProposalPath)
  assert.equal(manifest.linkedTargetLockReadinessReview, targetLockReadinessReviewPath)
  assert.equal(manifest.linkedActivationPacket, activationPacketPath)
  assert.equal(manifest.recommendedTargetName, 'A-Cockpit + B-Ledger + C-Captain')
  assert.equal(manifest.decisionReadiness, 'ready_for_user_decision')
  assert.equal(manifest.requiresExplicitUserDecision, true)
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activePermit, false)
  assert.equal(manifest.pageIntegration, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.finalAccepted, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.deepEqual(manifest.decisionOptions.map((item) => item.id), [
    'confirm_recommended_target',
    'confirm_with_modifications',
    'reject_or_revise_target'
  ])
  assert.ok(manifest.sufficientConfirmationTexts.includes('按 readiness review 的推荐方向锁定'))
  assert.ok(manifest.insufficientSignals.includes('继续'))
  assert.ok(manifest.insufficientSignals.includes('browser precheck'))
  assert.ok(manifest.nonNegotiableConstraints.includes('real WoW objects cannot come from imagegen'))
  assert.equal(manifest.recommendedFirstActivePermitIfConfirmed.surface, 'news_list_detail')
  assert.ok(manifest.forbiddenPromotion.includes('target_locked_without_explicit_user_decision'))
  assert.ok(manifest.nextRequiredEvidence.includes('explicit user target-lock confirmation or written modification'))

  assert.match(readme, /It does not prove `target_locked`/)
})

test('activation packet drafts the post-target-lock path without activating implementation', () => {
  const source = read(activationPacketPath)
  const manifest = readJson(activationPacketManifestPath)
  const readme = read(activationPacketReadmePath)

  assert.match(source, /^Status: `activation_packet_draft`$/m)
  assert.match(source, /not `target_locked`, not an active implementation permit, not page integration/)
  assert.match(source, /Record the user's target-lock decision/)
  assert.match(source, /Convert exactly one draft permit into an active permit/)
  assert.match(source, /Ambiguous approval, silence, test pass, browser screenshot pass, or Codex confidence is not enough/)
  assert.match(source, /Planned file: `docs\/design\/2026-07-07-wow-ui-system-target-locked-decision\.md`/)
  assert.match(source, /Planned active permit file:/)
  assert.match(source, /2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit\.md/)
  assert.match(source, /`news_list_detail`/)
  assert.match(source, /The page layer may:/)
  assert.match(source, /The page layer may not:/)
  assert.match(source, /Required Pre-Integration Checks/)
  assert.match(source, /Required Post-Integration Evidence/)
  assert.match(source, /Stop Conditions/)
  assert.match(source, /This packet can only prove `activation_packet_draft`/)
  assert.match(source, /`runtime_verified`/)

  assert.equal(manifest.status, 'activation_packet_draft')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activePermit, false)
  assert.equal(manifest.pageIntegration, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.finalAccepted, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.sourcePacket, activationPacketPath)
  assert.equal(manifest.sourceTargetLockProposal, targetLockProposalPath)
  assert.equal(manifest.sourceTargetLockReadinessReview, targetLockReadinessReviewPath)
  assert.equal(manifest.sourceNewsListDetailPermitDraft, newsListDetailPermitDraftPath)
  assert.equal(manifest.sourceNewsListDetailOwnerSkeleton, newsListDetailOwnerSkeletonPrecheckPath)
  assert.equal(manifest.sourceNewsListDetailComponentPrecheck, newsListDetailComponentPrecheckPath)
  assert.equal(manifest.sourcePermitCoverageMatrix, permitCoverageMatrixPath)
  assert.equal(manifest.sourceRouteSmokePlan, routeSmokePlanPath)
  assert.equal(manifest.triggerRequiresExplicitUserDecision, true)
  assert.ok(manifest.acceptedTriggerExamples.some((item) => /A-Cockpit \+ B-Ledger \+ C-Captain/.test(item)))
  assert.equal(manifest.plannedTargetLockedDecision.file, 'docs/design/2026-07-07-wow-ui-system-target-locked-decision.md')
  assert.equal(manifest.plannedTargetLockedDecision.plannedStatus, 'target_locked')
  assert.equal(manifest.plannedFirstActivePermit.surface, 'news_list_detail')
  assert.equal(manifest.plannedFirstActivePermit.file, 'docs/plans/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit.md')
  assert.equal(manifest.plannedFirstActivePermit.plannedStatus, 'active_implementation_permit')
  assert.ok(manifest.plannedFirstActivePermit.reason.includes('component precheck has 3 viewport screenshots 7 crops failures 0 warnings 0 horizontalOverflow 0'))

  for (const allowed of [
    'pages/news/list.wxml',
    'pages/news/detail.wxml',
    'pages/news/news-api.js',
    'components/article-list-board/*',
    'components/article-reader/*'
  ]) {
    assert.ok(manifest.allowedFilesAfterActivePermit.includes(allowed), `${allowed} should be allowed after active permit`)
  }
  for (const forbidden of [
    'app.json tabBar route registration changes',
    'project.config.json appid DevTools settings changes',
    'backend API collector translator moderation gate database schema changes',
    'unrelated surface edits',
    'page-private article row body block source proof status button warning or material geometry',
    'hidden fallback or incomplete state'
  ]) {
    assert.ok(manifest.forbiddenFilesAndActions.includes(forbidden), `${forbidden} should be forbidden`)
  }
  assert.ok(manifest.pageLayerMay.includes('pass validated list/detail data to ArticleListBoard and ArticleReader'))
  assert.ok(manifest.pageLayerMay.includes('handle openarticle and copysource events'))
  assert.ok(manifest.pageLayerMayNot.includes('restyle component internals to fix geometry'))
  assert.ok(manifest.pageLayerMayNot.includes('weaken news-api readiness gates'))
  assert.ok(manifest.requiredPreIntegrationChecks.includes('target_locked decision record exists'))
  assert.ok(manifest.requiredPreIntegrationChecks.includes('active news_list_detail permit exists'))
  assert.ok(manifest.requiredPreIntegrationChecks.includes('news_list_detail component precheck rerun'))
  assert.ok(manifest.requiredPostIntegrationEvidence.includes('real WeChat mini-program screenshots after captureSafe=true'))
  assert.ok(manifest.requiredPostIntegrationEvidence.includes('route smoke manifest for news_list_detail scenes'))
  assert.ok(manifest.requiredPostIntegrationEvidence.includes('DevTools action ledger'))
  assert.ok(manifest.stopConditions.includes('target lock absent or contested'))
  assert.ok(manifest.stopConditions.includes('active permit absent'))
  assert.ok(manifest.stopConditions.includes('DevTools not capture-safe while runtime evidence is required'))
  for (const forbiddenPromotion of [
    'target_locked',
    'active_implementation_permit',
    'page_integration',
    'runtime_verified',
    'final_accepted'
  ]) {
    assert.ok(manifest.forbiddenPromotion.includes(forbiddenPromotion), `${forbiddenPromotion} should not be promoted`)
  }
  for (const nextEvidence of [
    'explicit user target-lock confirmation or written modification',
    'target_locked decision record',
    'active news_list_detail implementation permit',
    'page integration under active permit',
    'runtime evidence after captureSafe=true'
  ]) {
    assert.ok(manifest.nextRequiredEvidence.includes(nextEvidence), `${nextEvidence} should be required`)
  }

  assert.match(readme, /Status: `activation_packet_draft`/)
  assert.match(readme, /Target locked: `false`/)
  assert.match(readme, /Active permit: `false`/)
  assert.match(readme, /Page integration: `false`/)
  assert.match(readme, /Runtime verified: `false`/)
  assert.match(readme, /Create `docs\/design\/2026-07-07-wow-ui-system-target-locked-decision\.md`/)
  assert.match(readme, /Create `docs\/plans\/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit\.md`/)
  assert.match(readme, /cannot promote anything to `target_locked`, `active_implementation_permit`, `page_integration`, `runtime_verified` or `final_accepted`/)
})

test('foundation component contracts define all owners and remain draft only', () => {
  const source = read(componentContractsPath)
  const manifest = readJson(componentContractsManifestPath)

  assert.match(source, /^Status: `component_contract_draft`$/m)
  assert.match(source, /This document is a component decomposition draft/)
  assert.match(source, /Asset Manifest Draft/)
  assert.match(source, /Route Smoke And Runtime Verification Plan/)
  assert.match(source, /Foundation Harness Draft/)
  assert.match(source, /Production Component Precheck/)
  assert.match(source, /Browser Component Precheck/)
  assert.match(source, /Surface Owner Contracts/)
  assert.match(source, /Pages compose components, bind data and handle route events only/)
  assert.match(source, /No page may split base and glyph/)
  assert.match(source, /Legacy pass aliases and legacy `status-badge` references may remain only as historical evidence/)
  assert.match(source, /This contract is `component_contract_draft`/)
  assert.doesNotMatch(source, /^Status: `component_precheck`$/m)

  for (const owner of [
    'AppShell',
    'PageFrame',
    'WowPanel',
    'MaterialImage',
    'GameObjectIcon',
    'StatusVisual',
    'ActionButton',
    'ModuleCard',
    'ChannelDock',
    'RankedFeed',
    'EvidenceLedger',
    'ChatShell'
  ]) {
    assert.match(source, new RegExp(`### ${owner}`))
  }

  for (const state of [
    'ready_to_simulate',
    'blocked',
    'partial',
    'stale',
    'source_reference',
    'unknown',
    'loading',
    'empty',
    'error'
  ]) {
    assert.match(source, new RegExp(`\\| \`${state}\` \\|`))
  }

  assert.match(source, /compact, standard, large/)
  assert.match(source, /page WXML\/WXSS/)
  assert.match(source, /chat input outside ChatShell/i)

  assert.equal(manifest.status, 'component_contract_draft')
  assert.equal(manifest.sourceAssetManifestDraft, assetManifestDraftPath)
  assert.equal(manifest.assetManifestDraftArtifact, assetManifestDraftManifestPath)
  assert.equal(manifest.sourceRouteSmokePlan, routeSmokePlanPath)
  assert.equal(manifest.routeSmokePlanArtifact, routeSmokePlanManifestPath)
  assert.equal(manifest.sourceFoundationHarnessDraft, foundationHarnessDraftPath)
  assert.equal(manifest.foundationHarnessDraftArtifact, foundationHarnessDraftManifestPath)
  assert.equal(manifest.sourceProductionComponentPrecheck, productionComponentPrecheckPath)
  assert.equal(manifest.productionComponentPrecheckArtifact, productionComponentPrecheckManifestPath)
  assert.equal(manifest.sourceBrowserComponentPrecheck, browserComponentPrecheckPath)
  assert.equal(manifest.browserComponentPrecheckArtifact, browserComponentPrecheckManifestPath)
  assert.equal(manifest.sourceSurfaceOwnerContracts, surfaceOwnerContractsPath)
  assert.equal(manifest.surfaceOwnerContractsArtifact, surfaceOwnerContractsManifestPath)
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.componentPrecheck, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.implementationPermit, false)
  assert.deepEqual(manifest.foundationOwners, [
    'AppShell',
    'PageFrame',
    'WowPanel',
    'MaterialImage',
    'GameObjectIcon',
    'StatusVisual',
    'ActionButton',
    'ModuleCard',
    'ChannelDock',
    'RankedFeed',
    'EvidenceLedger',
    'ChatShell'
  ])
  assert.deepEqual(manifest.sharedStates, [
    'ready_to_simulate',
    'blocked',
    'partial',
    'stale',
    'source_reference',
    'unknown',
    'loading',
    'empty',
    'error'
  ])
  assert.deepEqual(manifest.fixtureMatrix.viewports, ['compact', 'standard', 'large'])
  assert.ok(manifest.forbiddenPageOverrides.includes('split status base and glyph'))
  assert.ok(manifest.forbiddenPageOverrides.includes('chat input outside ChatShell'))
  assert.ok(manifest.preIntegrationGates.includes('surface-specific owner contracts exist for complex geometry before activating a surface permit'))
  assert.ok(manifest.preIntegrationGates.includes('component harness draft renders all owners and states'))
  assert.ok(manifest.preIntegrationGates.includes('production component precheck has zero failures and no unresolved asset blockers'))
  assert.ok(manifest.preIntegrationGates.includes('browser component precheck has zero failures across compact standard large viewports'))
  assert.ok(manifest.preIntegrationGates.includes('production-code browser harness renders all owners and states'))
  assert.ok(manifest.preIntegrationGates.includes('asset manifest draft accepted or revised into production/quarantine/source-map manifest'))
  assert.ok(manifest.preIntegrationGates.includes('route smoke plan ready for target surface with action ledger'))
  assert.ok(manifest.forbiddenPromotion.includes('component_precheck'))
  assert.ok(manifest.forbiddenPromotion.includes('implementation_permission_for_page_wxml_wxss'))
})

test('surface owner contracts assign complex geometry without runtime promotion', () => {
  const source = read(surfaceOwnerContractsPath)
  const manifest = readJson(surfaceOwnerContractsManifestPath)
  const readme = read(surfaceOwnerContractsReadmePath)

  assert.match(source, /^Status: `surface_owner_contract_draft`$/m)
  assert.match(source, /dense native WeChat mini-program product UI for WoW players/)
  assert.match(source, /DESIGN_VARIANCE: 6/)
  assert.match(source, /MOTION_INTENSITY: 3/)
  assert.match(source, /VISUAL_DENSITY: 9/)
  assert.match(source, /Foundation Component Contracts/)
  assert.match(source, /Implementation Permit Coverage Matrix/)
  assert.match(source, /Pages may compose these owners, pass read-model props and handle route events/)
  assert.match(source, /Pages may not patch owner internals/)
  assert.match(source, /Real WoW object imagery must flow through `GameObjectIcon`/)
  assert.match(source, /Low-semantic generated materials must flow through `MaterialImage`/)
  assert.match(source, /Status base, glyph, label and state color must flow through `StatusVisual`/)
  assert.match(source, /Buttons must flow through `ActionButton`/)
  assert.match(source, /Evidence rows, blockers, source references and checkedAt must flow through `EvidenceLedger`/)

  for (const owner of [
    'ArticleListBoard',
    'ArticleReader',
    'BuildsTabSurface',
    'ChickenbroCoachSurface',
    'TalentTreeCanvas',
    'GearLoadoutBoard',
    'GearConfigSheet',
    'TaskQueueBoard',
    'TaskResultReport',
    'ProfileIdentityPanel',
    'TemplateLibraryBoard'
  ]) {
    assert.match(source, new RegExp(`## ${owner}`))
    assert.ok(manifest.surfaceOwners.some((item) => item.owner === owner), `${owner} should be in manifest`)
  }

  for (const fixture of [
    'news_list_fallback',
    'news_detail_body_quote',
    'builds_tab_long_labels',
    'chickenbro_topic_drawer',
    'talent_tree_choice_node',
    'gear_slots_16_complete',
    'gear_sheet_apply_blocked',
    'task_card_failed',
    'task_detail_preview_no_dps',
    'profile_remote_sync_fallback',
    'template_delete_confirm'
  ]) {
    assert.match(source, new RegExp(fixture))
    assert.ok(manifest.surfaceOwners.some((item) => item.requiredFixtures.includes(fixture)), `${fixture} should be required`)
  }

  assert.match(source, /status shield and exclamation split apart/)
  assert.match(source, /page gutters hit screen edge/)
  assert.match(source, /compressed gold CTA button/)
  assert.match(source, /task result shows preview DPS/)
  assert.match(source, /coach conversation route shell, topic drawer and evidence explanation/)
  assert.match(source, /Visible raw `answerSource`, `confidence` or `job\.status`/)
  assert.match(source, /Input bar stays inside `ChatShell`/)
  assert.match(source, /This document can only prove `surface_owner_contract_draft`/)

  assert.equal(manifest.status, 'surface_owner_contract_draft')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.componentPrecheck, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.implementationPermit, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.sourceContract, surfaceOwnerContractsPath)
  assert.equal(manifest.sourceFoundationContracts, componentContractsPath)
  assert.equal(manifest.sourcePermitCoverageMatrix, permitCoverageMatrixPath)
  assert.equal(manifest.sourceTargetLockProposal, targetLockProposalPath)
  assert.equal(manifest.sourceAssetManifestDraft, assetManifestDraftPath)
  assert.equal(manifest.sourceRouteSmokePlan, routeSmokePlanPath)
  assert.deepEqual(manifest.dialSettings, {
    DESIGN_VARIANCE: 6,
    MOTION_INTENSITY: 3,
    VISUAL_DENSITY: 9
  })
  assert.deepEqual(manifest.surfaceOwners.map((item) => item.owner), [
    'ArticleListBoard',
    'ArticleReader',
    'BuildsTabSurface',
    'ChickenbroCoachSurface',
    'TalentTreeCanvas',
    'GearLoadoutBoard',
    'GearConfigSheet',
    'TaskQueueBoard',
    'TaskResultReport',
    'ProfileIdentityPanel',
    'TemplateLibraryBoard'
  ])
  assert.ok(manifest.globalRules.includes('pages compose owners, bind data and handle route actions only'))
  assert.ok(manifest.globalRules.includes('real WoW object imagery flows through GameObjectIcon'))
  assert.ok(manifest.globalRules.includes('low-semantic generated materials flow through MaterialImage'))
  assert.ok(manifest.globalRules.includes('status base glyph label and color flow through StatusVisual'))
  assert.ok(manifest.antiRegressionMapping.includes('status shield and exclamation split apart'))
  assert.ok(manifest.antiRegressionMapping.includes('task result shows preview DPS'))
  assert.ok(manifest.antiRegressionMapping.includes('Chickenbro exposes answerSource confidence or job.status'))
  assert.ok(manifest.antiRegressionMapping.includes('Chickenbro page-private chat bubbles input bar or topic drawer'))
  for (const forbidden of ['target_locked', 'active_implementation_permit', 'component_precheck', 'runtime_verified', 'final_accepted']) {
    assert.ok(manifest.forbiddenPromotion.includes(forbidden), `${forbidden} should not be promoted`)
  }
  assert.ok(manifest.nextRequiredEvidence.includes('component skeletons for new surface owners when activating a surface'))
  assert.ok(manifest.nextRequiredEvidence.includes('ChickenbroCoachSurface owner skeleton source precheck before Chickenbro page integration'))
  assert.ok(manifest.nextRequiredEvidence.includes('fixture matrix for each activated owner'))
  assert.ok(manifest.nextRequiredEvidence.includes('single-surface active implementation permit'))
  assert.ok(manifest.nextRequiredEvidence.includes('real mini-program screenshots'))

  assert.match(readme, /Status: `surface_owner_contract_draft`/)
  assert.match(readme, /ArticleListBoard/)
  assert.match(readme, /ChickenbroCoachSurface/)
  assert.match(readme, /TemplateLibraryBoard/)
  assert.match(readme, /not component prechecked/)
  assert.match(readme, /No WeChat DevTools action was taken/)
})

test('news list/detail owner skeletons exist without page integration or claim leakage', () => {
  const owners = [
    {
      dir: 'article-list-board',
      componentName: 'ArticleListBoard',
      requiredTags: ['wow-panel', 'status-visual', 'evidence-ledger', 'material-image'],
      requiredEvents: ['openarticle', 'evidencetoggle']
    },
    {
      dir: 'article-reader',
      componentName: 'ArticleReader',
      requiredTags: ['wow-panel', 'status-visual', 'evidence-ledger', 'action-button'],
      requiredEvents: ['copysource', 'evidencetoggle']
    }
  ]

  for (const owner of owners) {
    const base = `components/${owner.dir}/${owner.dir}`
    for (const ext of ['js', 'json', 'wxml', 'wxss']) {
      assert.ok(fs.existsSync(`${base}.${ext}`), `${owner.dir}.${ext} should exist`)
    }

    const js = read(`${base}.js`)
    const json = readJson(`${base}.json`)
    const wxml = read(`${base}.wxml`)
    const wxss = read(`${base}.wxss`)

    assert.doesNotThrow(() => new Function('Component', js)(() => {}), `${owner.componentName} JS should parse`)
    assert.equal(json.component, true)
    for (const tag of owner.requiredTags) {
      assert.ok(json.usingComponents[tag], `${owner.componentName} should declare ${tag}`)
      assert.match(wxml, new RegExp(`<${tag}\\b`), `${owner.componentName} should render ${tag}`)
    }
    for (const eventName of owner.requiredEvents) {
      assert.match(js, new RegExp(`triggerEvent\\('${eventName}'`), `${owner.componentName} should emit ${eventName}`)
    }
    assert.match(wxss, new RegExp(`\\.wow-${owner.dir}`), `${owner.componentName} should own its root geometry`)

    const combined = `${js}\n${json}\n${wxml}\n${wxss}`
    assert.doesNotMatch(combined, /DPS|综合评分|S\s*级|A\s*级|提升优先级|BiS/)
    assert.doesNotMatch(combined, /answerSource|confidence|job\.status|raw profile|raw SimC|collector metadata|translator JSON/)
    assert.doesNotMatch(combined, /battery|wifi|Wi-Fi|胶囊|状态栏|系统状态栏|电量/i)
  }

  const listJs = read('components/article-list-board/article-list-board.js')
  const readerJs = read('components/article-reader/article-reader.js')
  const readerWxml = read('components/article-reader/article-reader.wxml')
  assert.match(listJs, /query: this\.data\.query \|\| null/)
  assert.match(readerJs, /sourceUrl: sourceUrl/)
  assert.match(readerWxml, /bodyBlocks/)
  assert.match(readerWxml, /复制来源/)

  assert.doesNotMatch(read('pages/news/list.wxml'), /article-list-board/)
  assert.doesNotMatch(read('pages/news/detail.wxml'), /article-reader/)
})

test('news list/detail owner skeleton precheck records fixtures and non-promotion gates', () => {
  const source = read(newsListDetailOwnerSkeletonPrecheckPath)
  const manifest = readJson(newsListDetailOwnerSkeletonManifestPath)
  const fixtures = readJson(newsListDetailOwnerSkeletonFixturesPath)
  const readme = read(newsListDetailOwnerSkeletonReadmePath)

  assert.match(source, /^Status: `owner_skeleton_source_precheck`$/m)
  assert.match(source, /Added `components\/article-list-board\/\*`/)
  assert.match(source, /Added `components\/article-reader\/\*`/)
  assert.match(source, /No page WXML\/WXSS integration was performed/)
  assert.match(source, /No route registration, tabBar, appid, DevTools or backend contract changes were performed/)
  assert.match(source, /Emits `openarticle` with article id and query context/)
  assert.match(source, /Emits `copysource` with `article\.sourceUrl` only/)
  assert.match(source, /Production\/browser component precheck and component crops are now recorded in \[News List Detail Component Precheck\]/)
  assert.match(source, /This document can only prove `owner_skeleton_source_precheck`/)

  assert.equal(manifest.status, 'owner_skeleton_source_precheck')
  assert.equal(manifest.surface, 'news_list_detail')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activePermit, false)
  assert.equal(manifest.componentPrecheck, false)
  assert.equal(manifest.browserPrecheck, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.pageIntegration, false)
  assert.equal(manifest.sourceSurfaceOwnerContracts, surfaceOwnerContractsPath)
  assert.equal(manifest.sourcePermitDraft, newsListDetailPermitDraftPath)
  assert.equal(manifest.sourcePermitCoverageMatrix, permitCoverageMatrixPath)
  assert.equal(manifest.sourceNewsListDetailComponentPrecheck, newsListDetailComponentPrecheckPath)
  assert.equal(manifest.newsListDetailComponentPrecheckArtifact, newsListDetailComponentPrecheckManifestPath)
  assert.equal(manifest.fixtureMatrix, newsListDetailOwnerSkeletonFixturesPath)
  assert.deepEqual(manifest.ownerComponents.map((item) => item.owner), ['ArticleListBoard', 'ArticleReader'])
  assert.ok(manifest.ownerComponents.every((item) => item.sourcePrecheck === 'pass'))
  for (const dependency of ['WowPanel', 'StatusVisual', 'EvidenceLedger', 'ActionButton', 'MaterialImage']) {
    assert.ok(manifest.foundationDependencies.includes(dependency), `${dependency} should be recorded`)
  }
  for (const behavior of [
    'list loading empty fallback and ready states are represented',
    'fallback and requestError remain visible',
    'article row open emits only article id and query context',
    'reader missing id and not found states are explicit',
    'reader bodyBlocksZh heading paragraph list quote rendering is owned by ArticleReader',
    'copy source action emits article.sourceUrl only'
  ]) {
    assert.ok(manifest.protectedBehaviors.includes(behavior), `${behavior} should be protected`)
  }
  for (const forbidden of ['fake read counts', 'fake source logo', 'LLM commentary replacing source translation', 'hidden fallback state']) {
    assert.ok(manifest.forbiddenClaims.includes(forbidden), `${forbidden} should be forbidden`)
  }
  for (const exposure of ['raw backend payload', 'raw collector metadata', 'raw translator JSON', 'raw LLM prompt or output']) {
    assert.ok(manifest.forbiddenExposures.includes(exposure), `${exposure} should be forbidden`)
  }
  for (const fixtureId of [
    'news_list_loading',
    'news_list_ready',
    'news_list_empty',
    'news_list_fallback',
    'news_list_long_source_url',
    'news_detail_loading',
    'news_detail_ready',
    'news_detail_missing_id',
    'news_detail_not_found',
    'news_detail_fallback',
    'news_detail_long_source_url'
  ]) {
    assert.ok(manifest.fixtureIds.includes(fixtureId), `${fixtureId} should be in manifest`)
  }
  for (const nextEvidence of [
    'surface component precheck recorded in artifacts/ui-system-rebuild/20260707-news-list-detail-component-precheck/manifest.json',
    'target lock confirmation or revision',
    'convert news_list_detail draft into active implementation permit before page integration'
  ]) {
    assert.ok(manifest.nextRequiredEvidence.includes(nextEvidence), `${nextEvidence} should be required`)
  }
  for (const forbidden of ['target_locked', 'active_implementation_permit', 'component_precheck', 'browser_precheck', 'runtime_verified', 'final_accepted']) {
    assert.ok(manifest.nonPromotionRule.includes(forbidden), `${forbidden} should not be promoted`)
  }

  assert.equal(fixtures.status, 'owner_fixture_matrix_draft')
  assert.deepEqual(fixtures.owners, ['ArticleListBoard', 'ArticleReader'])
  assert.deepEqual(fixtures.listFixtures.map((item) => item.id), [
    'news_list_loading',
    'news_list_ready',
    'news_list_empty',
    'news_list_fallback',
    'news_list_long_source_url'
  ])
  assert.deepEqual(fixtures.readerFixtures.map((item) => item.id), [
    'news_detail_loading',
    'news_detail_ready',
    'news_detail_missing_id',
    'news_detail_not_found',
    'news_detail_fallback',
    'news_detail_long_source_url'
  ])
  assert.ok(fixtures.readerFixtures.some((fixture) => fixture.id === 'news_detail_ready' && fixture.props.article.bodyBlocksZh.some((block) => block.type === 'quote')))

  assert.match(readme, /Status: `owner_skeleton_source_precheck`/)
  assert.match(readme, /The owner component directories and `js\/json\/wxml\/wxss` files exist/)
  assert.match(readme, /production\/browser evidence is recorded in `artifacts\/ui-system-rebuild\/20260707-news-list-detail-component-precheck\/`/)
  assert.match(readme, /It is not connected to `pages\/news\/list` or `pages\/news\/detail`/)
  assert.match(readme, /No WeChat DevTools action was taken/)
})

test('chickenbro owner skeleton source precheck separates coach UI from page geometry', () => {
  const source = read(chickenbroOwnerSkeletonPrecheckPath)
  const manifest = readJson(chickenbroOwnerSkeletonManifestPath)
  const fixtures = readJson(chickenbroOwnerSkeletonFixturesPath)
  const readme = read(chickenbroOwnerSkeletonReadmePath)

  assert.match(source, /^Status: `owner_skeleton_source_precheck`$/m)
  assert.match(source, /Added `components\/chickenbro-coach-surface\/\*`/)
  assert.match(source, /Tightened `components\/chat-shell\/\*` defaults/)
  assert.match(source, /No `pages\/simulator\/chickenbro\.\*` or `pages\/simulator\/simulator\.\*` page integration was performed/)
  assert.match(source, /No route registration, tabBar, appid, DevTools or backend contract changes were performed/)
  assert.match(source, /native WeChat mini-program product UI for WoW players/)
  assert.match(source, /`DESIGN_VARIANCE: 6`/)
  assert.match(source, /`VISUAL_DENSITY: 9`/)
  assert.match(source, /### ChickenbroCoachSurface/)
  assert.match(source, /Translates backend-facing evidence fields into player-facing labels/)
  assert.match(source, /### ChatShell/)
  assert.match(source, /Current Source Findings Still Unfixed/)
  assert.match(source, /`pages\/simulator\/chickenbro\.wxml` still displays `assistantPayload\.answerSource` and `assistantPayload\.confidence`/)
  assert.match(source, /This skeleton does not patch those routes/)
  assert.match(source, /`chickenbro_done_with_evidence`/)
  assert.match(source, /No visible `answerSource`, `confidence` or `job\.status` text/)
  assert.match(source, /`answerSource` -> `通用回答` \/ `本地证据` \/ `降级回复` \/ `来源参考` \/ `证据不足`/)
  assert.match(source, /Production\/browser component precheck for `ChickenbroCoachSurface` and `ChatShell`/)
  assert.match(source, /This document can only prove `owner_skeleton_source_precheck`/)

  assert.equal(manifest.status, 'owner_skeleton_source_precheck')
  assert.equal(manifest.surface, 'chickenbro')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activePermit, false)
  assert.equal(manifest.componentPrecheck, false)
  assert.equal(manifest.browserPrecheck, false)
  assert.equal(manifest.pageIntegration, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.finalAccepted, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.sourceGoal, goalPath)
  assert.equal(manifest.sourceSurfaceOwnerContracts, surfaceOwnerContractsPath)
  assert.equal(manifest.sourcePermitDraft, chickenbroPermitDraftPath)
  assert.equal(manifest.sourcePermitCoverageMatrix, permitCoverageMatrixPath)
  assert.equal(manifest.sourceRouteSmokePlan, routeSmokePlanPath)
  assert.equal(manifest.sourceOwnerSkeletonPrecheck, chickenbroOwnerSkeletonPrecheckPath)
  assert.equal(manifest.fixtureMatrix, chickenbroOwnerSkeletonFixturesPath)
  assert.deepEqual(manifest.ownerComponents.map((item) => item.owner), ['ChickenbroCoachSurface', 'ChatShell'])
  assert.ok(manifest.ownerComponents.every((item) => item.sourcePrecheck === 'pass'))
  for (const dependency of ['ChatShell', 'EvidenceLedger', 'StatusVisual', 'ActionButton', 'MaterialImage']) {
    assert.ok(manifest.foundationDependencies.includes(dependency), `${dependency} should be recorded`)
  }
  for (const behavior of [
    'ChickenbroCoachSurface owns route-level chat header context suggested prompts evidence summary request-error slab topic drawer and retry action',
    'ChatShell owns message list scroll input safe-area empty state context strip and chat actions',
    'EvidenceLedger owns player-facing answer evidence rows',
    'backend-facing answerSource confidence and job.status are mapped before visible UI'
  ]) {
    assert.ok(manifest.protectedBehaviors.includes(behavior), `${behavior} should be protected`)
  }
  assert.deepEqual(manifest.mappingRules.answerSource, ['通用回答', '本地证据', '降级回复', '来源参考', '证据不足'])
  assert.deepEqual(manifest.mappingRules.confidence, ['可解释', '部分可用', '证据不足', '阻断'])
  assert.deepEqual(manifest.mappingRules['job.status'], ['等待整理', '整理中', '已完成', '暂时失败'])
  for (const fixtureId of [
    'chickenbro_tab_empty',
    'chickenbro_workbench_context',
    'chickenbro_generating',
    'chickenbro_done_with_evidence',
    'chickenbro_failed',
    'chickenbro_topic_drawer',
    'chickenbro_input_focus',
    'chickenbro_long_message_scroll'
  ]) {
    assert.ok(manifest.fixtureIds.includes(fixtureId), `${fixtureId} should be in manifest`)
  }
  for (const forbidden of ['answerSource', 'confidence', 'job.status']) {
    assert.ok(manifest.forbiddenVisibleText.includes(forbidden), `${forbidden} should be forbidden visibly`)
  }
  for (const nextEvidence of [
    'ChickenbroCoachSurface and ChatShell component precheck rerun before activation',
    'convert chickenbro draft into active implementation permit before page integration'
  ]) {
    assert.ok(manifest.nextRequiredEvidence.includes(nextEvidence), `${nextEvidence} should be required`)
  }
  for (const forbidden of ['target_locked', 'active_implementation_permit', 'component_precheck', 'browser_precheck', 'page_integration', 'runtime_verified', 'final_accepted']) {
    assert.ok(manifest.nonPromotionRule.includes(forbidden), `${forbidden} should not be promoted`)
  }

  assert.equal(fixtures.status, 'owner_skeleton_fixture_matrix')
  assert.equal(fixtures.surface, 'chickenbro')
  assert.equal(fixtures.owner, 'ChickenbroCoachSurface')
  assert.deepEqual(fixtures.fixtures.map((item) => item.id), manifest.fixtureIds)
  assert.ok(fixtures.fixtures.some((fixture) => fixture.id === 'chickenbro_workbench_context' && fixture.contextMeta.includes('不包含原始档案')))
  assert.ok(fixtures.fixtures.some((fixture) => fixture.id === 'chickenbro_done_with_evidence' && fixture.assistantPayload.answerSource === 'codex'))
  assert.ok(fixtures.fixtures.some((fixture) => fixture.id === 'chickenbro_long_message_scroll' && fixture.assertions.includes('no horizontal overflow')))

  const ownerBase = 'components/chickenbro-coach-surface/chickenbro-coach-surface'
  for (const ext of ['js', 'json', 'wxml', 'wxss']) {
    assert.ok(fs.existsSync(`${ownerBase}.${ext}`), `chickenbro-coach-surface.${ext} should exist`)
  }
  const ownerJs = read(`${ownerBase}.js`)
  const ownerJson = readJson(`${ownerBase}.json`)
  const ownerWxml = read(`${ownerBase}.wxml`)
  const ownerWxss = read(`${ownerBase}.wxss`)
  assert.doesNotThrow(() => new Function('Component', ownerJs)(() => {}), 'ChickenbroCoachSurface JS should parse')
  assert.equal(ownerJson.component, true)
  for (const tag of ['chat-shell', 'evidence-ledger', 'status-visual', 'action-button', 'material-image']) {
    assert.ok(ownerJson.usingComponents[tag], `ChickenbroCoachSurface should declare ${tag}`)
    assert.match(ownerWxml, new RegExp(`<${tag}\\b`), `ChickenbroCoachSurface should render ${tag}`)
  }
  for (const eventName of ['send', 'inputchange', 'newtopic', 'opendrawer', 'closedrawer', 'suggestedprompt', 'retry', 'evidencetoggle']) {
    assert.match(ownerJs, new RegExp(`triggerEvent\\('${eventName}'`), `ChickenbroCoachSurface should emit ${eventName}`)
  }
  assert.match(ownerJs, /mapAnswerSource/)
  assert.match(ownerJs, /mapEvidenceStrength/)
  assert.match(ownerJs, /mapJobStatus/)
  assert.match(ownerWxss, /\.wow-chickenbro-surface/)
  assert.match(ownerWxss, /safe-area|ChatShell|chat-stage|drawer/i)
  assert.doesNotMatch(ownerWxml, /answerSource|confidence|job\.status|raw profile|raw SimC|DPS|综合评分|S\s*级|提升优先级/)
  assert.doesNotMatch(ownerWxml, /battery|wifi|Wi-Fi|胶囊|状态栏|系统状态栏|电量/i)

  const chatWxml = read('components/chat-shell/chat-shell.wxml')
  const chatJs = read('components/chat-shell/chat-shell.js')
  assert.match(chatWxml, /contextActionLabel/)
  assert.match(chatWxml, /newTopicLabel/)
  assert.match(chatWxml, /sendLabel/)
  assert.match(chatWxml, /sendingLabel/)
  for (const labelProp of ['contextActionLabel', 'newTopicLabel', 'sendLabel', 'sendingLabel']) {
    assert.match(chatJs, new RegExp(labelProp))
  }

  assert.doesNotMatch(read('pages/simulator/chickenbro.wxml'), /chickenbro-coach-surface/)
  assert.doesNotMatch(read('pages/simulator/simulator.wxml'), /chickenbro-coach-surface/)

  assert.match(readme, /Status: `owner_skeleton_source_precheck`/)
  assert.match(readme, /`ChickenbroCoachSurface`: route-level coach composition/)
  assert.match(readme, /Current raw-field and page-private geometry findings remain until a future active permit/)
  assert.match(readme, /20260707-chickenbro-component-precheck\/manifest\.json/)
  assert.match(readme, /Real mini-program screenshots, route smoke manifest and DevTools action ledger/)
})

test('chickenbro component precheck records browser crops without page or runtime promotion', () => {
  const source = read(chickenbroComponentPrecheckPath)
  const manifest = readJson(chickenbroComponentPrecheckManifestPath)
  const readme = read(chickenbroComponentPrecheckReadmePath)

  assert.match(source, /^Status: `surface_component_precheck`$/m)
  assert.match(source, /production\/browser component precheck for the `chickenbro` surface owners/)
  assert.match(source, /not `target_locked`, not an active implementation permit, not page integration/)
  assert.match(source, /local headless Chrome precheck runner/)
  assert.match(source, /production WXSS class names/)
  assert.match(source, /compact \/ standard \/ large browser viewport screenshots/)
  assert.match(source, /eight standard-viewport component crops/)
  assert.match(source, /Fixed `ChatShell` owner CSS so the scroll lane no longer pushes the input bar outside the component boundary/)
  assert.match(source, /No `pages\/simulator\/chickenbro\.\*` or `pages\/simulator\/simulator\.\*` page integration was performed/)
  assert.match(source, /No WeChat DevTools action was performed/)
  assert.match(source, /Failures: `0`/)
  assert.match(source, /Warnings: `0`/)
  assert.match(source, /Horizontal overflow: `0`/)
  assert.match(source, /Forbidden visible text: `0`/)
  assert.match(source, /input bar remains inside `ChatShell`/)
  assert.match(source, /This document can only prove `surface_component_precheck`/)

  assert.equal(manifest.status, 'surface_component_precheck')
  assert.equal(manifest.surface, 'chickenbro')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activePermit, false)
  assert.equal(manifest.componentPrecheck, true)
  assert.equal(manifest.browserPrecheck, true)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.pageIntegration, false)
  assert.equal(manifest.sourceComponentPrecheckDoc, chickenbroComponentPrecheckPath)
  assert.equal(manifest.sourceOwnerSkeletonPrecheck, chickenbroOwnerSkeletonPrecheckPath)
  assert.equal(manifest.sourceOwnerSkeletonArtifact, chickenbroOwnerSkeletonManifestPath)
  assert.equal(manifest.sourceFixtures, chickenbroOwnerSkeletonFixturesPath)
  assert.equal(manifest.fixtureHtml, 'artifacts/ui-system-rebuild/20260707-chickenbro-component-precheck/component-fixture.html')
  assert.deepEqual(manifest.viewports.map((item) => item.id), ['compact', 'standard', 'large'])
  assert.equal(manifest.measurements.length, 3)
  assert.equal(manifest.crops.length, 8)
  assert.equal(manifest.viewportScreenshots.length, 3)
  assert.equal(manifest.failures.length, 0)
  assert.equal(manifest.warnings.length, 0)
  for (const report of manifest.ownerReports) {
    assert.equal(report.status, 'pass')
    assert.equal(report.forbiddenVisibleStatus, 'pass')
  }
  for (const measurement of manifest.measurements) {
    assert.equal(measurement.document.horizontalOverflow, 0)
    assert.equal(measurement.forbiddenVisibleText.length, 0)
    assert.ok(measurement.ownerRects.some((rect) => rect.owner === 'ChickenbroCoachSurface' && rect.found))
    assert.ok(measurement.ownerRects.some((rect) => rect.owner === 'ChatShell' && rect.found))
  }
  for (const cropId of [
    'chickenbro-surface-empty',
    'chickenbro-context-suggestions',
    'chickenbro-chat-shell',
    'chickenbro-evidence-ledger',
    'chickenbro-error-slab',
    'chickenbro-topic-drawer',
    'chickenbro-inputbar-focus',
    'chickenbro-long-message-bubble'
  ]) {
    assert.ok(manifest.crops.some((crop) => crop.id === cropId), `${cropId} should be cropped`)
  }
  const contactSize = readPngSize('artifacts/ui-system-rebuild/20260707-chickenbro-component-precheck/component-crop-contact-sheet.png')
  assert.ok(contactSize.width >= 1000)
  assert.ok(contactSize.height >= 1000)
  for (const screenshotPath of manifest.viewportScreenshots) {
    const size = readPngSize(screenshotPath)
    assert.ok(size.width >= 360)
    assert.ok(size.height >= 780)
  }
  const chatShellWxss = read('components/chat-shell/chat-shell.wxss')
  assert.doesNotMatch(chatShellWxss, /\.wow-chat-shell__scroll\s*{[^}]*height:\s*100%/s)
  for (const forbidden of ['target_locked', 'active_implementation_permit', 'runtime_verified', 'final_accepted']) {
    assert.ok(manifest.forbiddenPromotion.includes(forbidden), `${forbidden} should not be promoted`)
  }
  assert.ok(manifest.nextRequiredEvidence.includes('convert chickenbro draft into active implementation permit before page integration'))
  assert.ok(manifest.nextRequiredEvidence.includes('route smoke and DevTools action ledger after page integration'))

  assert.match(readme, /Status: `surface_component_precheck`/)
  assert.match(readme, /Failures: `0`/)
  assert.match(readme, /Warnings: `0`/)
  assert.match(readme, /standard_surface_crops_written: `pass` \(8\)/)
  assert.match(readme, /does not connect these owners to `pages\/simulator\/chickenbro` or `pages\/simulator\/simulator`/)
})

test('builds tab owner skeleton source precheck separates tab UI from page geometry', () => {
  const source = read(buildsTabOwnerSkeletonPrecheckPath)
  const manifest = readJson(buildsTabOwnerSkeletonManifestPath)
  const fixtures = readJson(buildsTabOwnerSkeletonFixturesPath)
  const readme = read(buildsTabOwnerSkeletonReadmePath)

  assert.match(source, /^Status: `owner_skeleton_source_precheck`$/m)
  assert.match(source, /Added `components\/builds-tab-surface\/\*`/)
  assert.match(source, /No `pages\/builds\/builds\.\*` page integration was performed/)
  assert.match(source, /Uses `StatusVisual` for readiness and workbench state/)
  assert.match(source, /Uses `ActionButton` for workbench and route actions/)
  assert.match(source, /Uses `ModuleCard` for talents, gear, SimC, tasks and Chickenbro workflow entries/)
  assert.match(source, /Uses `EvidenceLedger` for entry evidence/)
  assert.match(source, /The matrix explicitly preserves the old four entry keys: `talents`, `gear`, `simc`, `tasks`/)
  assert.match(source, /Production\/browser component precheck for `BuildsTabSurface` now exists/)

  assert.equal(manifest.status, 'owner_skeleton_source_precheck')
  assert.equal(manifest.surface, 'builds_tab')
  assert.equal(manifest.owner, 'BuildsTabSurface')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activePermit, false)
  assert.equal(manifest.pageIntegration, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.sourceFixtures, buildsTabOwnerSkeletonFixturesPath)
  assert.deepEqual(manifest.fixtureIds, [
    'builds_tab_ready',
    'builds_tab_loading',
    'builds_tab_source_reference',
    'builds_tab_blocked_workbench',
    'builds_tab_long_labels',
    'builds_tab_missing_icons'
  ])
  assert.deepEqual(manifest.preservedEntryKeys, ['talents', 'gear', 'simc', 'tasks'])
  for (const dependency of ['WowPanel', 'StatusVisual', 'ActionButton', 'ModuleCard', 'EvidenceLedger', 'GameObjectIcon', 'MaterialImage']) {
    assert.ok(manifest.foundationDependencies.includes(dependency), `${dependency} should be recorded`)
  }
  for (const forbidden of ['target_locked', 'active_implementation_permit', 'page_integration', 'runtime_verified', 'final_accepted']) {
    assert.ok(manifest.forbiddenPromotion.includes(forbidden), `${forbidden} should not be promoted`)
  }
  assert.ok(manifest.nextRequiredEvidence.includes('production/browser component precheck for BuildsTabSurface'))
  assert.ok(manifest.nextRequiredEvidence.includes('convert builds_tab draft into active implementation permit before page integration'))

  assert.equal(fixtures.status, 'owner_skeleton_fixture_matrix')
  assert.equal(fixtures.surface, 'builds_tab')
  assert.deepEqual(fixtures.fixtures.map((item) => item.id), manifest.fixtureIds)
  assert.ok(fixtures.fixtures.some((fixture) => fixture.id === 'builds_tab_ready' && fixture.state === 'ready_to_simulate'))
  assert.ok(fixtures.fixtures.some((fixture) => fixture.id === 'builds_tab_blocked_workbench' && fixture.workflowCards.some((card) => card.key === 'gear' && card.status === 'blocked')))
  assert.ok(fixtures.fixtures.some((fixture) => fixture.id === 'builds_tab_missing_icons' && !fixture.specIconUrl && fixture.specFallbackText === '未'))
  for (const fixture of fixtures.fixtures) {
    const keys = (fixture.workflowCards || []).map((card) => card.key)
    for (const key of ['talents', 'gear', 'simc', 'tasks']) {
      assert.ok(keys.includes(key), `${fixture.id} should preserve ${key}`)
    }
  }

  const ownerBase = 'components/builds-tab-surface/builds-tab-surface'
  for (const ext of ['js', 'json', 'wxml', 'wxss']) {
    assert.ok(fs.existsSync(`${ownerBase}.${ext}`), `builds-tab-surface.${ext} should exist`)
  }
  const ownerJs = read(`${ownerBase}.js`)
  const ownerJson = readJson(`${ownerBase}.json`)
  const ownerWxml = read(`${ownerBase}.wxml`)
  const ownerWxss = read(`${ownerBase}.wxss`)
  assert.doesNotThrow(() => new Function('Component', ownerJs)(() => {}), 'BuildsTabSurface JS should parse')
  assert.equal(ownerJson.component, true)
  for (const tag of ['wow-panel', 'status-visual', 'action-button', 'module-card', 'evidence-ledger', 'game-object-icon', 'material-image']) {
    assert.ok(ownerJson.usingComponents[tag], `BuildsTabSurface should declare ${tag}`)
    assert.match(ownerWxml, new RegExp(`<${tag}\\b`), `BuildsTabSurface should render ${tag}`)
  }
  for (const eventName of ['workbenchtap', 'classchange', 'specchange', 'herochange', 'entrytap', 'evidencetoggle', 'refresh']) {
    assert.match(ownerJs, new RegExp(`triggerEvent\\('${eventName}'`), `BuildsTabSurface should emit ${eventName}`)
  }
  assert.match(ownerJs, /normalizeStatus/)
  assert.match(ownerJs, /ready_to_simulate/)
  assert.match(ownerWxss, /\.wow-builds-tab-surface/)
  assert.doesNotMatch(ownerWxml, /DPS|综合评分|S\s*级|A\s*级|提升优先级|BiS|raw profile|raw SimC/)
  assert.doesNotMatch(ownerWxml, /battery|wifi|Wi-Fi|胶囊|状态栏|系统状态栏|电量/i)
  assert.doesNotMatch(read('pages/builds/builds.wxml'), /builds-tab-surface/)

  assert.match(readme, /Status: `owner_skeleton_source_precheck`/)
  assert.match(readme, /does not connect to `pages\/builds\/builds`/)
  assert.match(readme, /Runtime verified: `false`/)
})

test('builds tab component precheck records browser crops and old entry preservation', () => {
  const source = read(buildsTabComponentPrecheckPath)
  const manifest = readJson(buildsTabComponentPrecheckManifestPath)
  const readme = read(buildsTabComponentPrecheckReadmePath)

  assert.match(source, /^Status: `surface_component_precheck`$/m)
  assert.match(source, /production\/browser component precheck for `BuildsTabSurface`/)
  assert.match(source, /not `target_locked`, not an active implementation permit, not page integration/)
  assert.match(source, /Fixture HTML rendered with production WXSS class names/)
  assert.match(source, /Compact \/ standard \/ large local headless Chrome viewports/)
  assert.match(source, /Eight standard-viewport component crops/)
  assert.match(source, /Old talent, gear, SimC and task entries must remain visible in every fixture/)
  assert.match(source, /Failures: `0`/)
  assert.match(source, /Warnings: `0`/)
  assert.match(source, /Horizontal overflow: `0`/)
  assert.match(source, /Forbidden visible text: `0`/)
  assert.match(source, /This document can only prove `surface_component_precheck`/)

  assert.equal(manifest.status, 'surface_component_precheck')
  assert.equal(manifest.surface, 'builds_tab')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activePermit, false)
  assert.equal(manifest.componentPrecheck, true)
  assert.equal(manifest.browserPrecheck, true)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.pageIntegration, false)
  assert.equal(manifest.browserEngine, 'chrome_headless_cdp')
  assert.equal(manifest.sourceComponentPrecheckDoc, buildsTabComponentPrecheckPath)
  assert.equal(manifest.sourceOwnerSkeletonPrecheck, buildsTabOwnerSkeletonPrecheckPath)
  assert.equal(manifest.sourceOwnerSkeletonArtifact, buildsTabOwnerSkeletonManifestPath)
  assert.equal(manifest.sourceFixtures, buildsTabOwnerSkeletonFixturesPath)
  assert.equal(manifest.fixtureHtml, 'artifacts/ui-system-rebuild/20260707-builds-tab-component-precheck/component-fixture.html')
  assert.deepEqual(manifest.ownerReports.map((item) => item.owner), ['BuildsTabSurface'])
  for (const ownerReport of manifest.ownerReports) {
    assert.equal(ownerReport.status, 'pass')
    assert.equal(ownerReport.jsSyntax, 'pass')
    assert.equal(ownerReport.dependencyStatus, 'pass')
    assert.equal(ownerReport.eventStatus, 'pass')
    assert.equal(ownerReport.forbiddenVisibleStatus, 'pass')
    assert.deepEqual(ownerReport.missingFiles, [])
    assert.deepEqual(ownerReport.missingDependencies, [])
    assert.deepEqual(ownerReport.missingEvents, [])
    assert.deepEqual(ownerReport.forbiddenVisibleMatches, [])
  }
  assert.deepEqual(manifest.viewports.map((viewport) => viewport.id), ['compact', 'standard', 'large'])
  assert.equal(manifest.measurements.length, 3)
  assert.equal(manifest.crops.length, 8)
  assert.equal(manifest.viewportScreenshots.length, 3)
  assert.equal(manifest.failures.length, 0)
  assert.equal(manifest.warnings.length, 0)
  assert.deepEqual(manifest.preservedEntryKeys, ['talents', 'gear', 'simc', 'tasks'])
  for (const measurement of manifest.measurements) {
    assert.equal(measurement.document.horizontalOverflow, 0)
    assert.equal(measurement.forbiddenVisibleText.length, 0)
    assert.equal(measurement.ownerRects.length, 6)
    assert.ok(measurement.ownerRects.every((rect) => rect.owner === 'BuildsTabSurface' && rect.found))
    assert.ok(measurement.fixtureEntryKeys.every((item) => item.missingPreservedKeys.length === 0))
  }
  for (const cropId of [
    'builds-ready-surface',
    'builds-current-spec-console',
    'builds-class-spec-hero-switchers',
    'builds-workbench-entry-blocked',
    'builds-status-visual',
    'builds-workflow-grid',
    'builds-preserved-task-card',
    'builds-long-labels'
  ]) {
    assert.ok(manifest.crops.some((crop) => crop.id === cropId), `${cropId} should be cropped`)
  }
  for (const checkId of ['owner_source_precheck_pass', 'all_viewports_measured', 'no_document_horizontal_overflow', 'old_four_entries_preserved', 'no_forbidden_visible_text', 'standard_surface_crops_written', 'devtools_not_touched', 'page_integration_not_performed']) {
    assert.ok(manifest.checks.some((check) => check.id === checkId && check.status === 'pass'), `${checkId} should pass`)
  }
  const contactSize = readPngSize('artifacts/ui-system-rebuild/20260707-builds-tab-component-precheck/component-crop-contact-sheet.png')
  assert.ok(contactSize.width >= 1000)
  assert.ok(contactSize.height >= 1000)
  for (const screenshotPath of manifest.viewportScreenshots) {
    const size = readPngSize(screenshotPath)
    assert.ok(size.width >= 360)
    assert.ok(size.height >= 780)
  }
  for (const forbidden of ['target_locked', 'active_implementation_permit', 'runtime_verified', 'final_accepted']) {
    assert.ok(manifest.forbiddenPromotion.includes(forbidden), `${forbidden} should not be promoted`)
  }
  assert.ok(manifest.nextRequiredEvidence.includes('convert builds_tab draft into active implementation permit before page integration'))
  assert.ok(manifest.nextRequiredEvidence.includes('real mini-program screenshots after captureSafe=true'))

  assert.match(readme, /Status: `surface_component_precheck`/)
  assert.match(readme, /Failures: `0`/)
  assert.match(readme, /Warnings: `0`/)
  assert.match(readme, /standard_surface_crops_written: `pass` \(8\)/)
  assert.match(readme, /does not connect `BuildsTabSurface` to `pages\/builds\/builds`/)
})

test('workbench owner skeleton source precheck separates cockpit UI from page geometry', () => {
  const source = read(workbenchOwnerSkeletonPrecheckPath)
  const manifest = readJson(workbenchOwnerSkeletonManifestPath)
  const fixtures = readJson(workbenchOwnerSkeletonFixturesPath)
  const readme = read(workbenchOwnerSkeletonReadmePath)

  assert.match(source, /^Status: `owner_skeleton_source_precheck`$/m)
  assert.match(source, /Added `components\/workbench-cockpit-surface\/\*`/)
  assert.match(source, /No `pages\/builds\/workbench\.\*` or `pages\/builds\/builds\.\*` page integration was performed/)
  assert.match(source, /Uses `StatusVisual` for the verdict state/)
  assert.match(source, /Uses `ActionButton` for primary and blocker actions/)
  assert.match(source, /Uses `ModuleCard` for talents, gear, SimC and Chickenbro status cards/)
  assert.match(source, /Uses `EvidenceLedger` for coverage, checkedAt, catalogStatus, statSnapshot, template count and blockers/)
  assert.match(source, /Production\/browser component precheck for `WorkbenchCockpitSurface` now exists/)
  assert.match(source, /This document can only prove `owner_skeleton_source_precheck`/)

  assert.equal(manifest.status, 'owner_skeleton_source_precheck')
  assert.equal(manifest.surface, 'current_spec_workbench')
  assert.equal(manifest.owner, 'WorkbenchCockpitSurface')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activePermit, false)
  assert.equal(manifest.pageIntegration, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.sourceFixtures, workbenchOwnerSkeletonFixturesPath)
  assert.deepEqual(manifest.fixtureIds, [
    'workbench_ready',
    'workbench_blocked_gear',
    'workbench_partial_talent',
    'workbench_stale',
    'workbench_source_reference',
    'workbench_evidence_expanded'
  ])
  for (const dependency of ['WowPanel', 'StatusVisual', 'ActionButton', 'ModuleCard', 'EvidenceLedger', 'GameObjectIcon', 'MaterialImage']) {
    assert.ok(manifest.foundationDependencies.includes(dependency), `${dependency} should be recorded`)
  }
  for (const forbidden of ['target_locked', 'active_implementation_permit', 'page_integration', 'runtime_verified', 'final_accepted']) {
    assert.ok(manifest.forbiddenPromotion.includes(forbidden), `${forbidden} should not be promoted`)
  }
  assert.ok(manifest.nextRequiredEvidence.includes('production/browser component precheck for WorkbenchCockpitSurface'))
  assert.ok(manifest.nextRequiredEvidence.includes('convert workbench draft into active implementation permit before page integration'))
  assert.ok(manifest.nextRequiredEvidence.includes('route smoke and DevTools action ledger after page integration'))

  assert.equal(fixtures.status, 'owner_skeleton_fixture_matrix')
  assert.equal(fixtures.surface, 'current_spec_workbench')
  assert.deepEqual(fixtures.fixtures.map((item) => item.id), manifest.fixtureIds)
  assert.deepEqual(fixtures.sharedScenarioOptions.map((item) => item.key), ['single', 'aoe_5', 'mythic_plus'])
  assert.ok(fixtures.fixtures.some((fixture) => fixture.id === 'workbench_ready' && fixture.state === 'ready_to_simulate'))
  assert.ok(fixtures.fixtures.some((fixture) => fixture.id === 'workbench_blocked_gear' && fixture.primaryAction.key === 'open_gear'))
  assert.ok(fixtures.fixtures.some((fixture) => fixture.id === 'workbench_evidence_expanded' && fixture.evidenceRows.some((row) => row.value === 'statSnapshot=blocked')))

  const ownerBase = 'components/workbench-cockpit-surface/workbench-cockpit-surface'
  for (const ext of ['js', 'json', 'wxml', 'wxss']) {
    assert.ok(fs.existsSync(`${ownerBase}.${ext}`), `workbench-cockpit-surface.${ext} should exist`)
  }
  const ownerJs = read(`${ownerBase}.js`)
  const ownerJson = readJson(`${ownerBase}.json`)
  const ownerWxml = read(`${ownerBase}.wxml`)
  const ownerWxss = read(`${ownerBase}.wxss`)
  assert.doesNotThrow(() => new Function('Component', ownerJs)(() => {}), 'WorkbenchCockpitSurface JS should parse')
  assert.equal(ownerJson.component, true)
  for (const tag of ['wow-panel', 'status-visual', 'action-button', 'module-card', 'evidence-ledger', 'game-object-icon']) {
    assert.ok(ownerJson.usingComponents[tag], `WorkbenchCockpitSurface should declare ${tag}`)
    assert.match(ownerWxml, new RegExp(`<${tag}\\b`), `WorkbenchCockpitSurface should render ${tag}`)
  }
  assert.ok(ownerJson.usingComponents['material-image'], 'WorkbenchCockpitSurface should declare MaterialImage for material ownership')
  for (const eventName of ['primaryaction', 'blockeraction', 'moduletap', 'evidencetoggle', 'scenariochange', 'classchange', 'specchange']) {
    assert.match(ownerJs, new RegExp(`triggerEvent\\('${eventName}'`), `WorkbenchCockpitSurface should emit ${eventName}`)
  }
  assert.match(ownerJs, /normalizeStatus/)
  assert.match(ownerJs, /ready_to_simulate/)
  assert.match(ownerWxss, /\.wow-workbench-surface/)
  assert.doesNotMatch(ownerWxml, /DPS|综合评分|S\s*级|A\s*级|提升优先级|BiS|raw profile|raw SimC/)
  assert.doesNotMatch(ownerWxml, /battery|wifi|Wi-Fi|胶囊|状态栏|系统状态栏|电量/i)

  assert.doesNotMatch(read('pages/builds/workbench.wxml'), /workbench-cockpit-surface/)
  assert.doesNotMatch(read('pages/builds/builds.wxml'), /workbench-cockpit-surface/)

  assert.match(readme, /Status: `owner_skeleton_source_precheck`/)
  assert.match(readme, /does not connect to `pages\/builds\/workbench` or `pages\/builds\/builds`/)
  assert.match(readme, /Runtime verified: `false`/)
})

test('workbench component precheck records browser crops without page or runtime promotion', () => {
  const source = read(workbenchComponentPrecheckPath)
  const manifest = readJson(workbenchComponentPrecheckManifestPath)
  const readme = read(workbenchComponentPrecheckReadmePath)

  assert.match(source, /^Status: `surface_component_precheck`$/m)
  assert.match(source, /production\/browser component precheck for `WorkbenchCockpitSurface`/)
  assert.match(source, /not `target_locked`, not an active implementation permit, not page integration/)
  assert.match(source, /Fixture HTML rendered with production WXSS class names/)
  assert.match(source, /Compact \/ standard \/ large local headless Chrome viewports/)
  assert.match(source, /Eight standard-viewport component crops/)
  assert.match(source, /Failures: `0`/)
  assert.match(source, /Warnings: `0`/)
  assert.match(source, /Horizontal overflow: `0`/)
  assert.match(source, /Forbidden visible text: `0`/)
  assert.match(source, /`StatusVisual` can own the verdict base\/glyph as one component/)
  assert.match(source, /This document can only prove `surface_component_precheck`/)

  assert.equal(manifest.status, 'surface_component_precheck')
  assert.equal(manifest.surface, 'current_spec_workbench')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activePermit, false)
  assert.equal(manifest.componentPrecheck, true)
  assert.equal(manifest.browserPrecheck, true)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.pageIntegration, false)
  assert.equal(manifest.browserEngine, 'chrome_headless_cdp')
  assert.equal(manifest.sourceComponentPrecheckDoc, workbenchComponentPrecheckPath)
  assert.equal(manifest.sourceOwnerSkeletonPrecheck, workbenchOwnerSkeletonPrecheckPath)
  assert.equal(manifest.sourceOwnerSkeletonArtifact, workbenchOwnerSkeletonManifestPath)
  assert.equal(manifest.sourceFixtures, workbenchOwnerSkeletonFixturesPath)
  assert.equal(manifest.fixtureHtml, 'artifacts/ui-system-rebuild/20260707-workbench-component-precheck/component-fixture.html')
  assert.deepEqual(manifest.ownerReports.map((item) => item.owner), ['WorkbenchCockpitSurface'])
  for (const ownerReport of manifest.ownerReports) {
    assert.equal(ownerReport.status, 'pass')
    assert.equal(ownerReport.jsSyntax, 'pass')
    assert.equal(ownerReport.dependencyStatus, 'pass')
    assert.equal(ownerReport.eventStatus, 'pass')
    assert.equal(ownerReport.forbiddenVisibleStatus, 'pass')
    assert.deepEqual(ownerReport.missingFiles, [])
    assert.deepEqual(ownerReport.missingDependencies, [])
    assert.deepEqual(ownerReport.missingEvents, [])
    assert.deepEqual(ownerReport.forbiddenVisibleMatches, [])
  }
  assert.deepEqual(manifest.viewports.map((viewport) => viewport.id), ['compact', 'standard', 'large'])
  assert.equal(manifest.measurements.length, 3)
  assert.equal(manifest.crops.length, 8)
  assert.equal(manifest.viewportScreenshots.length, 3)
  assert.equal(manifest.failures.length, 0)
  assert.equal(manifest.warnings.length, 0)
  for (const measurement of manifest.measurements) {
    assert.equal(measurement.document.horizontalOverflow, 0)
    assert.equal(measurement.forbiddenVisibleText.length, 0)
    assert.equal(measurement.ownerRects.length, 6)
    assert.ok(measurement.ownerRects.every((rect) => rect.owner === 'WorkbenchCockpitSurface' && rect.found))
  }
  for (const cropId of [
    'workbench-ready-surface',
    'workbench-hero-identity',
    'workbench-blocked-verdict',
    'workbench-status-visual',
    'workbench-primary-action',
    'workbench-module-band',
    'workbench-partial-module-card',
    'workbench-evidence-ledger-expanded'
  ]) {
    assert.ok(manifest.crops.some((crop) => crop.id === cropId), `${cropId} should be cropped`)
  }
  for (const checkId of ['owner_source_precheck_pass', 'all_viewports_measured', 'no_document_horizontal_overflow', 'no_forbidden_visible_text', 'standard_surface_crops_written', 'devtools_not_touched', 'page_integration_not_performed']) {
    assert.ok(manifest.checks.some((check) => check.id === checkId && check.status === 'pass'), `${checkId} should pass`)
  }
  const contactSize = readPngSize('artifacts/ui-system-rebuild/20260707-workbench-component-precheck/component-crop-contact-sheet.png')
  assert.ok(contactSize.width >= 1000)
  assert.ok(contactSize.height >= 1000)
  for (const screenshotPath of manifest.viewportScreenshots) {
    const size = readPngSize(screenshotPath)
    assert.ok(size.width >= 360)
    assert.ok(size.height >= 780)
  }
  for (const forbidden of ['target_locked', 'active_implementation_permit', 'runtime_verified', 'final_accepted']) {
    assert.ok(manifest.forbiddenPromotion.includes(forbidden), `${forbidden} should not be promoted`)
  }
  assert.ok(manifest.nextRequiredEvidence.includes('convert workbench draft into active implementation permit before page integration'))
  assert.ok(manifest.nextRequiredEvidence.includes('real mini-program screenshots after captureSafe=true'))

  assert.match(readme, /Status: `surface_component_precheck`/)
  assert.match(readme, /Failures: `0`/)
  assert.match(readme, /Warnings: `0`/)
  assert.match(readme, /standard_surface_crops_written: `pass` \(8\)/)
  assert.match(readme, /does not connect `WorkbenchCockpitSurface` to `pages\/builds\/workbench` or `pages\/builds\/builds`/)
})

test('talent tree canvas owner skeleton separates tree UI from page geometry', () => {
  const source = read(talentTreeCanvasOwnerSkeletonPrecheckPath)
  const manifest = readJson(talentTreeCanvasOwnerSkeletonManifestPath)
  const fixtures = readJson(talentTreeCanvasOwnerSkeletonFixturesPath)
  const readme = read(talentTreeCanvasOwnerSkeletonReadmePath)
  const ownerJson = readJson('components/talent-tree-canvas/talent-tree-canvas.json')
  const ownerJs = read('components/talent-tree-canvas/talent-tree-canvas.js')
  const ownerWxml = read('components/talent-tree-canvas/talent-tree-canvas.wxml')
  const ownerWxss = read('components/talent-tree-canvas/talent-tree-canvas.wxss')

  assert.match(source, /^Status: `owner_skeleton_source_precheck`$/m)
  assert.match(source, /adds `TalentTreeCanvas` as the surface owner for `talent_simulator`/)
  assert.match(source, /does not authorize edits to `pages\/builds\/talent-simulator\.\*`/)
  assert.match(source, /tree viewport dimensions, node positions, link geometry/)
  assert.match(source, /choice affordance, rank badge placement, tree action rail and talent evidence ledger placement/)
  assert.match(source, /No `pages\/builds\/talent-simulator\.\*` page file was edited/)

  assert.equal(manifest.surface, 'talent_simulator')
  assert.equal(manifest.owner, 'TalentTreeCanvas')
  assert.equal(manifest.status, 'owner_skeleton_source_precheck')
  assert.equal(manifest.pageIntegration, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.sourceFixtures, talentTreeCanvasOwnerSkeletonFixturesPath)
  assert.equal(manifest.sourcePermitDraft, talentSimulatorPermitDraftPath)
  assert.equal(manifest.sourceOwnerSkeletonPrecheckDoc, talentTreeCanvasOwnerSkeletonPrecheckPath)
  assert.deepEqual(manifest.fixtureIds, [
    'talent_tree_loading',
    'talent_tree_ready',
    'talent_tree_missing_icon',
    'talent_tree_locked_path',
    'talent_tree_choice_node',
    'talent_save_blocked',
    'talent_save_ready'
  ])
  assert.ok(manifest.ownerResponsibilities.includes('tree viewport dimensions'))
  assert.ok(manifest.ownerResponsibilities.includes('choice affordance'))
  assert.ok(manifest.forbidden.includes('generated talent icons'))
  assert.ok(manifest.nextRequiredEvidence.includes('run TalentTreeCanvas surface component precheck with browser crops'))

  assert.equal(fixtures.surface, 'talent_simulator')
  assert.equal(fixtures.owner, 'TalentTreeCanvas')
  assert.equal(fixtures.devtoolsTouched, false)
  assert.equal(fixtures.pageIntegration, false)
  assert.match(fixtures.realWowAssetRule, /explicit WoW render icon URLs or text fallback/)
  assert.deepEqual(fixtures.fixtures.map((fixture) => fixture.id), manifest.fixtureIds)
  assert.ok(fixtures.fixtures.some((fixture) => JSON.stringify(fixture).includes('https://render.worldofwarcraft.com')))
  assert.ok(fixtures.fixtures.some((fixture) => fixture.id === 'talent_tree_missing_icon' && JSON.stringify(fixture).includes('fallback')))

  for (const file of manifest.componentFiles) {
    assert.ok(fs.existsSync(file), `${file} should exist`)
  }
  for (const tag of ['wow-panel', 'game-object-icon', 'status-visual', 'action-button', 'evidence-ledger', 'material-image']) {
    assert.ok(ownerJson.usingComponents[tag], `TalentTreeCanvas should declare ${tag}`)
    assert.match(ownerWxml, new RegExp(`<${tag}\\b`), `TalentTreeCanvas should render ${tag}`)
  }
  for (const eventName of ['nodetap', 'choicetap', 'savetap', 'importtap', 'resettap', 'treeswitch', 'evidencetoggle', 'viewportchange']) {
    assert.match(ownerJs, new RegExp(`triggerEvent\\('${eventName}'`), `TalentTreeCanvas should emit ${eventName}`)
  }
  assert.match(ownerJs, /normalizeShape/)
  assert.match(ownerJs, /normalizeLink/)
  assert.match(ownerJs, /ready_to_simulate/)
  assert.match(ownerWxss, /\.wow-talent-tree-canvas/)
  assert.doesNotMatch(ownerWxml, /DPS|综合评分|S\s*级|A\s*级|提升优先级|BiS|raw profile|raw SimC/)
  assert.doesNotMatch(read('pages/builds/talent-simulator.wxml'), /talent-tree-canvas/)

  assert.match(readme, /Status: `owner_skeleton_source_precheck`/)
  assert.match(readme, /Runtime verified: `false`/)
})

test('talent tree canvas component precheck records browser crops without page or runtime promotion', () => {
  const source = read(talentTreeCanvasComponentPrecheckPath)
  const manifest = readJson(talentTreeCanvasComponentPrecheckManifestPath)
  const readme = read(talentTreeCanvasComponentPrecheckReadmePath)

  assert.match(source, /^Status: `surface_component_precheck`$/m)
  assert.match(source, /renders `TalentTreeCanvas` fixture states with production WXSS class names/)
  assert.match(source, /does not touch WeChat DevTools and does not connect the owner to `pages\/builds\/talent-simulator`/)
  assert.match(source, /Crops: `8`/)
  assert.match(source, /Failures: `0`/)
  assert.match(source, /Warnings: `0`/)
  assert.match(source, /Choice node affordance, rank badge, icon socket and node base are cropped as one owner component/)
  assert.match(source, /This evidence is only `surface_component_precheck`/)

  assert.equal(manifest.status, 'surface_component_precheck')
  assert.equal(manifest.surface, 'talent_simulator')
  assert.equal(manifest.owner, 'TalentTreeCanvas')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activePermit, false)
  assert.equal(manifest.componentPrecheck, true)
  assert.equal(manifest.browserPrecheck, true)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.pageIntegration, false)
  assert.equal(manifest.browserEngine, 'chrome_headless_cdp')
  assert.equal(manifest.sourceComponentPrecheckDoc, talentTreeCanvasComponentPrecheckPath)
  assert.equal(manifest.sourceOwnerSkeletonPrecheck, talentTreeCanvasOwnerSkeletonPrecheckPath)
  assert.equal(manifest.sourceOwnerSkeletonArtifact, talentTreeCanvasOwnerSkeletonManifestPath)
  assert.equal(manifest.sourceFixtures, talentTreeCanvasOwnerSkeletonFixturesPath)
  assert.equal(manifest.fixtureHtml, 'artifacts/ui-system-rebuild/20260707-talent-tree-canvas-component-precheck/component-fixture.html')
  assert.deepEqual(manifest.ownerReports.map((item) => item.owner), ['TalentTreeCanvas'])
  for (const ownerReport of manifest.ownerReports) {
    assert.equal(ownerReport.status, 'pass')
    assert.equal(ownerReport.jsSyntax, 'pass')
    assert.equal(ownerReport.dependencyStatus, 'pass')
    assert.equal(ownerReport.eventStatus, 'pass')
    assert.equal(ownerReport.forbiddenVisibleStatus, 'pass')
    assert.deepEqual(ownerReport.missingFiles, [])
    assert.deepEqual(ownerReport.missingDependencies, [])
    assert.deepEqual(ownerReport.missingEvents, [])
    assert.deepEqual(ownerReport.forbiddenVisibleMatches, [])
  }
  assert.deepEqual(manifest.viewports.map((viewport) => viewport.id), ['compact', 'standard', 'large'])
  assert.equal(manifest.measurements.length, 3)
  assert.equal(manifest.crops.length, 8)
  assert.equal(manifest.viewportScreenshots.length, 3)
  assert.equal(manifest.failures.length, 0)
  assert.equal(manifest.warnings.length, 0)
  for (const measurement of manifest.measurements) {
    assert.equal(measurement.document.horizontalOverflow, 0)
    assert.equal(measurement.forbiddenVisibleText.length, 0)
    assert.ok(measurement.ownerRects.every((rect) => rect.found))
    assert.ok(measurement.treeChecks.every((check) => check.shellFound && check.nodesInside))
  }
  for (const cropId of [
    'talent-tree-ready-surface',
    'talent-tree-header',
    'talent-tree-viewport',
    'talent-tree-choice-node',
    'talent-tree-locked-path',
    'talent-tree-action-rail',
    'talent-tree-evidence',
    'talent-tree-missing-icon'
  ]) {
    assert.ok(manifest.crops.some((crop) => crop.id === cropId), `${cropId} should be cropped`)
  }
  for (const checkId of ['owner_source_precheck_pass', 'all_viewports_measured', 'no_document_horizontal_overflow', 'no_forbidden_visible_text', 'nodes_inside_tree_shell', 'standard_surface_crops_written', 'devtools_not_touched', 'page_integration_not_performed']) {
    assert.ok(manifest.checks.some((check) => check.id === checkId && check.status === 'pass'), `${checkId} should pass`)
  }
  const contactSize = readPngSize('artifacts/ui-system-rebuild/20260707-talent-tree-canvas-component-precheck/component-crop-contact-sheet.png')
  assert.ok(contactSize.width >= 1000)
  assert.ok(contactSize.height >= 1000)
  for (const screenshotPath of manifest.viewportScreenshots) {
    const size = readPngSize(screenshotPath)
    assert.ok(size.width >= 360)
    assert.ok(size.height >= 780)
  }
  for (const forbidden of ['target_locked', 'active_implementation_permit', 'runtime_verified', 'final_accepted']) {
    assert.ok(manifest.forbiddenPromotion.includes(forbidden), `${forbidden} should not be promoted`)
  }
  assert.ok(manifest.nextRequiredEvidence.includes('convert talent simulator draft into active implementation permit before page integration'))
  assert.ok(manifest.nextRequiredEvidence.includes('connect TalentTreeCanvas to pages/builds/talent-simulator only under active permit'))
  assert.ok(manifest.nextRequiredEvidence.includes('real mini-program screenshots after captureSafe=true'))

  assert.match(readme, /Status: `surface_component_precheck`/)
  assert.match(readme, /Failures: `0`/)
  assert.match(readme, /Warnings: `0`/)
  assert.match(readme, /standard_surface_crops_written: `pass` \(8\)/)
  assert.match(readme, /does not connect `TalentTreeCanvas` to `pages\/builds\/talent-simulator`/)
})

test('news list/detail component precheck records browser crops without page or runtime promotion', () => {
  const source = read(newsListDetailComponentPrecheckPath)
  const manifest = readJson(newsListDetailComponentPrecheckManifestPath)
  const readme = read(newsListDetailComponentPrecheckReadmePath)

  assert.match(source, /^Status: `surface_component_precheck`$/m)
  assert.match(source, /production\/browser component precheck for the `news_list_detail` surface owners/)
  assert.match(source, /not `target_locked`, not an active implementation permit, not page integration/)
  assert.match(source, /local headless Chrome precheck runner/)
  assert.match(source, /production WXSS class names/)
  assert.match(source, /compact \/ standard \/ large browser viewport screenshots/)
  assert.match(source, /seven standard-viewport component crops/)
  assert.match(source, /No page WXML\/WXSS integration was performed/)
  assert.match(source, /No WeChat DevTools action was performed/)
  assert.match(source, /Failures: `0`/)
  assert.match(source, /Warnings: `0`/)
  assert.match(source, /Horizontal overflow: `0`/)
  assert.match(source, /Standard crops written: `7`/)
  assert.match(source, /This precheck does not prove/)
  assert.match(source, /real WeChat mini-program runtime rendering/)
  assert.match(source, /active implementation permission for `pages\/news\/list` or `pages\/news\/detail`/)
  assert.match(source, /This document can only prove `surface_component_precheck`/)

  assert.equal(manifest.status, 'surface_component_precheck')
  assert.equal(manifest.surface, 'news_list_detail')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activePermit, false)
  assert.equal(manifest.componentPrecheck, true)
  assert.equal(manifest.browserPrecheck, true)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.pageIntegration, false)
  assert.equal(manifest.browserEngine, 'chrome_headless_cdp')
  assert.equal(manifest.sourceComponentPrecheckDoc, newsListDetailComponentPrecheckPath)
  assert.equal(manifest.sourceOwnerSkeletonPrecheck, newsListDetailOwnerSkeletonPrecheckPath)
  assert.equal(manifest.sourceOwnerSkeletonArtifact, newsListDetailOwnerSkeletonManifestPath)
  assert.equal(manifest.sourceFixtures, newsListDetailOwnerSkeletonFixturesPath)
  assert.equal(manifest.fixtureHtml, 'artifacts/ui-system-rebuild/20260707-news-list-detail-component-precheck/component-fixture.html')

  assert.deepEqual(manifest.ownerReports.map((item) => item.owner), ['ArticleListBoard', 'ArticleReader'])
  for (const ownerReport of manifest.ownerReports) {
    assert.equal(ownerReport.status, 'pass')
    assert.equal(ownerReport.jsSyntax, 'pass')
    assert.equal(ownerReport.dependencyStatus, 'pass')
    assert.equal(ownerReport.eventStatus, 'pass')
    assert.equal(ownerReport.forbiddenClaimStatus, 'pass')
    assert.deepEqual(ownerReport.missingFiles, [])
    assert.deepEqual(ownerReport.missingDependencies, [])
    assert.deepEqual(ownerReport.missingEvents, [])
    assert.deepEqual(ownerReport.forbiddenMatches, [])
  }

  assert.deepEqual(manifest.viewports.map((viewport) => viewport.id), ['compact', 'standard', 'large'])
  assert.equal(manifest.measurements.length, 3)
  for (const measurement of manifest.measurements) {
    assert.ok(measurement.document.horizontalOverflow <= 2)
    assert.equal(measurement.ownerRects.length, 11)
    assert.ok(measurement.ownerRects.every((rect) => rect.found))
  }
  assert.deepEqual(manifest.failures, [])
  assert.deepEqual(manifest.warnings, [])
  assert.ok(manifest.checks.some((check) => check.id === 'owner_source_precheck_pass' && check.status === 'pass' && check.count === 2))
  assert.ok(manifest.checks.some((check) => check.id === 'fixture_html_written' && check.status === 'pass'))
  assert.ok(manifest.checks.some((check) => check.id === 'all_viewports_measured' && check.status === 'pass' && check.count === 3))
  assert.ok(manifest.checks.some((check) => check.id === 'no_document_horizontal_overflow' && check.status === 'pass'))
  assert.ok(manifest.checks.some((check) => check.id === 'owner_min_rects_pass' && check.status === 'pass'))
  assert.ok(manifest.checks.some((check) => check.id === 'standard_surface_crops_written' && check.status === 'pass' && check.count === 7))
  assert.ok(manifest.checks.some((check) => check.id === 'devtools_not_touched' && check.status === 'pass'))
  assert.ok(manifest.checks.some((check) => check.id === 'page_integration_not_performed' && check.status === 'pass'))

  assert.deepEqual(manifest.crops.map((crop) => crop.id), [
    'article-list-ready',
    'article-list-row',
    'article-list-fallback-evidence',
    'article-reader-ready',
    'article-reader-body',
    'article-reader-source-footer',
    'article-reader-blocked'
  ])
  assert.equal(manifest.crops.length, 7)
  for (const crop of manifest.crops) {
    assert.ok(fs.existsSync(crop.path), `${crop.path} should exist`)
    const size = readPngSize(crop.path)
    assert.ok(size.width >= 24, `${crop.path} should have measurable width`)
    assert.ok(size.height >= 24, `${crop.path} should have measurable height`)
  }
  for (const viewportScreenshot of manifest.viewportScreenshots) {
    assert.ok(fs.existsSync(viewportScreenshot), `${viewportScreenshot} should exist`)
    const size = readPngSize(viewportScreenshot)
    assert.ok(size.width >= 360)
    assert.ok(size.height >= 700)
  }
  assert.ok(fs.existsSync(manifest.contactSheet), `${manifest.contactSheet} should exist`)
  const contactSize = readPngSize(manifest.contactSheet)
  assert.ok(contactSize.width >= 1000)
  assert.ok(contactSize.height >= 1000)
  assert.ok(fs.existsSync(manifest.fixtureHtml), `${manifest.fixtureHtml} should exist`)
  assert.ok(fs.statSync(manifest.fixtureHtml).size > 10000, 'fixture html should include owner fixtures and production WXSS')

  for (const forbidden of ['target_locked', 'active_implementation_permit', 'runtime_verified', 'final_accepted']) {
    assert.ok(manifest.forbiddenPromotion.includes(forbidden), `${forbidden} should not be promoted`)
  }
  for (const nextEvidence of [
    'user confirmation or revision of target lock',
    'convert news_list_detail draft into active implementation permit before page integration',
    'connect ArticleListBoard and ArticleReader to pages/news only under active permit',
    'real mini-program screenshots after captureSafe=true',
    'route smoke and DevTools action ledger after page integration'
  ]) {
    assert.ok(manifest.nextRequiredEvidence.includes(nextEvidence), `${nextEvidence} should be required`)
  }

  assert.match(readme, /Status: `surface_component_precheck`/)
  assert.match(readme, /not a WeChat runtime screenshot/)
  assert.match(readme, /Failures: `0`/)
  assert.match(readme, /Warnings: `0`/)
  assert.match(readme, /no horizontal document overflow/)
  assert.match(readme, /does not connect these owners to `pages\/news\/list` or `pages\/news\/detail`/)
  assert.match(readme, /does not provide route smoke, overlay, red-zone or DevTools action ledger/)
})

test('asset manifest draft separates generated material, quarantine, and real WoW source maps', () => {
  const source = read(assetManifestDraftPath)
  const manifest = readJson(assetManifestDraftManifestPath)
  const readme = read(assetManifestDraftReadmePath)

  assert.match(source, /^Status: `asset_manifest_draft`$/m)
  assert.match(source, /not `target_locked`, not `runtime_verified`, and not an implementation permit/)
  assert.match(source, /Imagegen output may become low-semantic material only after manifest review/)
  assert.match(source, /State visuals must be owned by `StatusVisual`, including base, glyph, center point, size and transparent boundary/)
  assert.match(source, /Page WXML\/WXSS must not reference new material until a later implementation permit/)

  for (const assetClass of ['panel', 'border', 'texture', 'socket', 'state-base', 'state-atomic', 'decorative']) {
    assert.match(source, new RegExp('\\| `' + assetClass + '` \\|'))
    assert.ok(manifest.allowedProductionMaterialClasses.includes(assetClass))
  }

  for (const quarantineClass of [
    'whole-page target image',
    'image with visible text',
    'fact-bearing generated icon',
    'fake chrome',
    'pass-named asset pending recut',
    'legacy surface material',
    'reference source image'
  ]) {
    assert.match(source, new RegExp(quarantineClass.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
    assert.ok(manifest.quarantineClasses.includes(quarantineClass))
  }

  assert.ok(manifest.candidateInputs.some((item) => item.policy === 'candidate_low_semantic_input'))
  assert.ok(manifest.candidateInputs.some((item) => item.policy === 'candidate_socket_input'))
  assert.ok(manifest.candidateInputs.some((item) => item.policy === 'candidate_status_input'))
  assert.ok(manifest.quarantineInputs.some((item) => item.policy === 'quarantine_legacy_surface_material'))
  assert.ok(manifest.quarantineInputs.some((item) => item.policy === 'quarantine_pass_named_asset'))
  assert.ok(manifest.quarantineInputs.some((item) => item.policy === 'quarantine_rejected_direction'))

  assert.deepEqual(manifest.realSourceMap.allowedSourceClasses, [
    'api',
    'battlenet',
    'websim',
    'repo_verified',
    'user_provided'
  ])
  assert.ok(manifest.realSourceMap.forbiddenSourceClasses.includes('imagegen'))
  assert.ok(manifest.realSourceMap.forbiddenSourceClasses.includes('target_screenshot_crop'))
  assert.deepEqual(manifest.realSourceMap.entityTypes, [
    'class',
    'spec',
    'hero',
    'talent',
    'spell',
    'item',
    'source',
    'dungeon',
    'raid',
    'affix'
  ])
  assert.ok(manifest.realSourceMap.currentEvidence.includes('pages/common/game-asset.js'))
  assert.ok(manifest.realSourceMap.currentEvidence.includes('server/news_backend.py /api/websim/assets'))

  assert.deepEqual(manifest.componentOwners.MaterialImage, ['panel', 'border', 'texture', 'decorative'])
  assert.deepEqual(manifest.componentOwners.GameObjectIcon, ['socket', 'real_wow_object_icon', 'text_fallback'])
  assert.deepEqual(manifest.componentOwners.StatusVisual, ['state-base', 'state-atomic', 'state_glyph_contract'])
  assert.match(manifest.fitStrategy['state-atomic'], /no page-owned glyph overlay/)
  assert.equal(manifest.sizeBudget.mobileMaterialKbMax, 350)
  assert.equal(manifest.packageBudgetPending, true)

  assert.equal(manifest.status, 'asset_manifest_draft')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.componentPrecheck, false)
  assert.equal(manifest.implementationPermit, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.ok(manifest.promotionGates.includes('implementation_permit_names_owner_component_and_surface'))
  assert.ok(manifest.forbiddenPromotion.includes('production_use_without_implementation_permit'))
  assert.ok(manifest.nextRequiredEvidence.includes('component harness fixtures for MaterialImage GameObjectIcon StatusVisual'))

  assert.match(readme, /Status: `asset_manifest_draft`/)
  assert.match(readme, /Real WoW object icons must come from `gameAsset\.iconUrl`/)
})

test('route smoke plan covers registered app routes and keeps browser/runtime evidence separated', () => {
  const source = read(routeSmokePlanPath)
  const manifest = readJson(routeSmokePlanManifestPath)
  const readme = read(routeSmokePlanReadmePath)
  const appConfig = readJson('app.json')

  assert.match(source, /^Status: `route_smoke_plan_draft`$/m)
  assert.match(source, /not `runtime_verified`, not `final_accepted`/)
  assert.match(source, /No layer may promote itself above its evidence/)
  assert.match(source, /Browser evidence cannot be called runtime verified/)
  assert.match(source, /Default forbidden actions/)
  assert.match(source, /Every runtime run must write an action ledger/)
  assert.match(source, /`pages\/pve\/\*` exists in the repository but is not registered in `app\.json`/)

  assert.equal(manifest.status, 'route_smoke_plan_draft')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.componentPrecheck, false)
  assert.equal(manifest.implementationPermit, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.finalAccepted, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.deepEqual(manifest.registeredPages, appConfig.pages)
  assert.deepEqual(
    manifest.tabPages,
    appConfig.tabBar.list.map((item) => item.pagePath)
  )
  assert.ok(manifest.excludedDormantRoutes.includes('pages/pve/pve'))
  assert.ok(manifest.excludedDormantRoutes.includes('pages/pve/detail'))

  assert.deepEqual(manifest.verificationLadder, [
    'source_route_inventory',
    'browser_component_precheck',
    'browser_scene_matrix',
    'miniprogram_runtime_capture',
    'comparison_and_scorecard'
  ])
  assert.equal(manifest.devtoolsPolicy.requiresCaptureSafe, true)
  for (const forbidden of [
    'cli open',
    'cli close',
    'forced restart',
    'clear cache',
    'switch appid',
    'delete user data directory',
    'screenshot before captureSafe=true'
  ]) {
    assert.ok(manifest.devtoolsPolicy.forbiddenActions.includes(forbidden))
  }
  for (const ledgerField of ['captureSafe', 'sceneList', 'failedScenes', 'routeActions', 'loginStateIncidentNote']) {
    assert.ok(manifest.devtoolsPolicy.requiredLedgerFields.includes(ledgerField))
  }

  assert.equal(manifest.scenes.length, 27)
  for (const sceneId of [
    'news_home_top',
    'news_home_scrolled',
    'builds_tab_top',
    'workbench_ready',
    'workbench_blocked_gear',
    'workbench_partial_talent',
    'workbench_stale',
    'workbench_evidence_expanded',
    'talent_simulator_load',
    'gear_detail_load',
    'simc_from_workbench',
    'smart_analysis_tab',
    'chickenbro_workbench_context',
    'tasks_list',
    'profile_templates'
  ]) {
    assert.ok(manifest.scenes.some((scene) => scene.id === sceneId), `missing ${sceneId}`)
  }
  for (const scene of manifest.scenes) {
    const routePath = scene.route.replace(/^\//, '').split('?')[0]
    assert.ok(appConfig.pages.includes(routePath), `${scene.id} uses unregistered route ${routePath}`)
  }

  assert.ok(manifest.commonAssertions.includes('no_fake_time_battery_wifi_phone_frame_or_wechat_capsule'))
  assert.ok(manifest.commonAssertions.includes('no_quarantine_asset_reference'))
  assert.ok(manifest.commonAssertions.includes('StatusVisual_owns_state_visuals'))
  assert.ok(manifest.requiredRuntimeArtifacts.includes('devtools-action-ledger.json'))
  assert.ok(manifest.requiredRuntimeArtifacts.includes('overlays/*.png'))
  assert.ok(manifest.requiredRuntimeArtifacts.includes('red-zones/*.png'))
  assert.ok(manifest.requiredRuntimeArtifacts.includes('route-smoke-report.md'))
  assert.ok(manifest.forbiddenPromotion.includes('browser_precheck_promoted_to_runtime_verified'))
  assert.ok(manifest.nextRequiredEvidence.includes('captureSafe=true runtime gate'))
  assert.ok(manifest.nextRequiredEvidence.includes('real mini-program screenshots for all required scenes'))

  assert.match(readme, /Status: `route_smoke_plan_draft`/)
  assert.match(readme, /Browser evidence cannot be promoted to runtime verification/)
})

test('foundation harness draft exposes all target owners and remains below component precheck', () => {
  const source = read(foundationHarnessDraftPath)
  const manifest = readJson(foundationHarnessDraftManifestPath)
  const readme = read(foundationHarnessDraftReadmePath)

  assert.match(source, /^Status: `component_harness_draft`$/m)
  assert.match(source, /not `component_precheck`, not `runtime_verified`, and not an implementation permit/)
  assert.match(source, /covered only nine legacy owners and still used `StatusBadge`/)
  assert.match(source, /component directories for all 12 target owners/)
  assert.match(source, /legacy `status-badge` also exists but cannot be promoted automatically/)
  assert.match(source, /It renders a static Pillow board, not real WXML\/WXSS/)
  assert.match(source, /It does not authorize page WXML\/WXSS edits/)

  assert.equal(manifest.status, 'component_harness_draft')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.componentPrecheck, false)
  assert.equal(manifest.implementationPermit, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.renderMode, 'static_pillow_component_harness')

  assert.deepEqual(manifest.foundationOwners, [
    'AppShell',
    'PageFrame',
    'WowPanel',
    'MaterialImage',
    'GameObjectIcon',
    'StatusVisual',
    'ActionButton',
    'ModuleCard',
    'ChannelDock',
    'RankedFeed',
    'EvidenceLedger',
    'ChatShell'
  ])
  assert.deepEqual(manifest.missingTargetOwners, [])
  assert.deepEqual(manifest.legacyAliases, [
    {
      targetOwner: 'StatusVisual',
      legacyComponent: 'status-badge'
    }
  ])
  assert.equal(manifest.crops.length, 12)
  assert.ok(manifest.existingComponentDirs.includes('app-shell'))
  assert.ok(manifest.existingComponentDirs.includes('material-image'))
  assert.ok(manifest.existingComponentDirs.includes('status-visual'))
  assert.ok(manifest.existingComponentDirs.includes('chat-shell'))
  assert.ok(manifest.existingComponentDirs.includes('status-badge'))
  assert.ok(manifest.existingComponentDirs.includes('game-object-icon'))
  assert.ok(manifest.checks.some((check) => check.id === 'all_target_owners_rendered' && check.count === 12))
  assert.ok(manifest.checks.some((check) => check.id === 'all_target_owner_dirs_present'))
  assert.ok(manifest.checks.some((check) => check.id === 'legacy_status_badge_not_promoted_to_status_visual'))
  assert.ok(manifest.forbiddenPromotion.includes('component_precheck'))
  assert.ok(manifest.forbiddenPromotion.includes('runtime_verified'))
  assert.ok(manifest.nextRequiredEvidence.includes('real component harness using production component code'))
  assert.ok(manifest.nextRequiredEvidence.includes('StatusVisual production-code fixture measurement'))
  assert.ok(manifest.nextRequiredEvidence.includes('ChatShell production-code fixture measurement'))

  const size = readPngSize(manifest.contactSheet)
  assert.ok(size.width >= 1200, `contact sheet width should be reviewable, got ${size.width}`)
  assert.ok(size.height >= 1600, `contact sheet height should include all owners, got ${size.height}`)
  for (const crop of manifest.crops) {
    assert.ok(fs.existsSync(crop.path), `${crop.path} should exist`)
    assert.ok(crop.width >= 360)
    assert.ok(crop.height >= 300)
  }

  assert.match(readme, /Status: `component_harness_draft`/)
  assert.match(readme, /Missing Target Owners/)
  assert.match(readme, /- none/)
  assert.match(readme, /status-badge` exists, but the target owner is `StatusVisual`/)
  assert.match(readme, /StatusVisual production-code fixture measurement/)
  assert.match(readme, /ChatShell production-code fixture measurement/)
})

test('production component precheck uses source components and remains below runtime verification', () => {
  const source = read(productionComponentPrecheckPath)
  const manifest = readJson(productionComponentPrecheckManifestPath)
  const readme = read(productionComponentPrecheckReadmePath)

  assert.match(source, /^Status: `component_precheck`$/m)
  assert.match(source, /not `runtime_verified`, not `target_locked`, and not an implementation permit/)
  assert.match(source, /All 12 foundation owner component directories/)
  assert.match(source, /`ModuleCard` now routes status rendering through `StatusVisual`, not legacy `status-badge`/)
  assert.match(source, /Generated asset blockers: `0`/)
  assert.match(source, /`ChannelDock` and `RankedFeed` no longer hardcode old generated `ui-v2-1-slices` material/)
  assert.match(source, /Browser rect measurement and component crops are now recorded/)
  assert.match(source, /must not expose raw backend vocabulary/)
  assert.match(source, /no longer contains raw backend evidence field names/)
  assert.match(source, /does not itself include `ArticleListBoard` and `ArticleReader`/)
  assert.match(source, /separate \[News List Detail Component Precheck\]/)

  assert.equal(manifest.status, 'component_precheck')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.implementationPermit, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.renderMode, 'html_fixture_using_production_wxss_and_owner_class_names')
  assert.equal(manifest.sourceGoal, goalPath)
  assert.equal(manifest.sourceContracts, componentContractsPath)
  assert.equal(manifest.sourceSurfaceOwnerContracts, surfaceOwnerContractsPath)
  assert.equal(manifest.sourceNewsListDetailOwnerSkeletonPrecheck, newsListDetailOwnerSkeletonPrecheckPath)
  assert.equal(manifest.newsListDetailOwnerSkeletonArtifact, newsListDetailOwnerSkeletonManifestPath)
  assert.equal(manifest.sourceNewsListDetailComponentPrecheck, newsListDetailComponentPrecheckPath)
  assert.equal(manifest.newsListDetailComponentPrecheckArtifact, newsListDetailComponentPrecheckManifestPath)
  assert.equal(manifest.sourceHarnessDraft, foundationHarnessDraftPath)
  assert.deepEqual(manifest.surfaceOwnerSourceSkeletons, ['ArticleListBoard', 'ArticleReader'])
  assert.equal(manifest.surfaceOwnerPrecheckStatus.ArticleListBoard, 'surface_component_precheck')
  assert.equal(manifest.surfaceOwnerPrecheckStatus.ArticleReader, 'surface_component_precheck')
  assert.deepEqual(manifest.foundationOwners, [
    'AppShell',
    'PageFrame',
    'WowPanel',
    'MaterialImage',
    'GameObjectIcon',
    'StatusVisual',
    'ActionButton',
    'ModuleCard',
    'ChannelDock',
    'RankedFeed',
    'EvidenceLedger',
    'ChatShell'
  ])
  assert.deepEqual(manifest.sharedStates, [
    'ready_to_simulate',
    'blocked',
    'partial',
    'stale',
    'source_reference',
    'unknown',
    'loading',
    'empty',
    'error'
  ])
  assert.equal(manifest.ownerReports.length, 12)
  assert.deepEqual(manifest.failures, [])
  assert.deepEqual(manifest.blockers, [])
  assert.ok(manifest.checks.some((check) => check.id === 'all_foundation_component_files_present' && check.status === 'pass' && check.count === 12))
  assert.ok(manifest.checks.some((check) => check.id === 'all_component_js_compiles' && check.status === 'pass' && check.count === 12))
  assert.ok(manifest.checks.some((check) => check.id === 'no_legacy_pass_classes_in_foundation_components' && check.status === 'pass'))
  assert.ok(manifest.checks.some((check) => check.id === 'module_card_uses_status_visual' && check.status === 'pass'))
  assert.ok(manifest.checks.some((check) => check.id === 'status_visual_shared_state_vocabulary' && check.status === 'pass' && check.count === 9))
  assert.ok(manifest.checks.some((check) => check.id === 'generated_assets_need_manifest_resolution' && check.status === 'pass' && check.count === 0))
  assert.ok(manifest.nextRequiredEvidence.includes('browser rect measurement for compact standard large fixture viewports'))
  assert.ok(manifest.nextRequiredEvidence.includes('implementation permit for one surface only after browser component precheck'))
  assert.ok(manifest.forbiddenPromotion.includes('implementation_permit'))
  assert.ok(manifest.forbiddenPromotion.includes('runtime_verified'))

  assert.ok(fs.existsSync(manifest.fixtureHtml), `${manifest.fixtureHtml} should exist`)
  assert.ok(fs.statSync(manifest.fixtureHtml).size > 10000, 'fixture html should contain production WXSS and owner fixtures')
  const fixtureHtml = read(manifest.fixtureHtml)
  assert.match(fixtureHtml, /WOW UI System Production Component Precheck/)
  assert.match(fixtureHtml, /wow-status-visual/)
  assert.match(fixtureHtml, /wow-chat-shell/)
  assert.match(fixtureHtml, /证据状态/)
  assert.match(fixtureHtml, /部分可用/)
  assert.doesNotMatch(fixtureHtml, /answerSource|confidence|job\.status|raw profile|raw SimC/)

  assert.match(readme, /Status: `component_precheck`/)
  assert.match(readme, /ArticleListBoard` and `ArticleReader` now exist as source-level skeletons/)
  assert.match(readme, /production\/browser evidence lives in the separate `20260707-news-list-detail-component-precheck` artifact/)
  assert.match(readme, /foundation artifact still covers only the 12 foundation owners/)
  assert.match(readme, /Failures: `0`/)
  assert.match(readme, /Blockers: `0`/)
  assert.match(readme, /browser rect measurement for compact standard large fixture viewports/)
})

test('browser component precheck measures all owner rects and crops without runtime promotion', () => {
  const source = read(browserComponentPrecheckPath)
  const manifest = readJson(browserComponentPrecheckManifestPath)
  const readme = read(browserComponentPrecheckReadmePath)

  assert.match(source, /^Status: `browser_component_precheck`$/m)
  assert.match(source, /not `runtime_verified`, not `target_locked`, and not an implementation permit/)
  assert.match(source, /Compact, standard and large viewport rect measurements are recorded/)
  assert.match(source, /All 12 foundation owner roots are found and measurable/)
  assert.match(source, /The run does not touch WeChat DevTools/)
  assert.match(source, /player-facing evidence copy rather than raw backend field names/)

  assert.equal(manifest.status, 'browser_component_precheck')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.implementationPermit, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.browserEngine, 'chrome_headless_cdp')
  assert.equal(manifest.sourceProductionComponentPrecheck, productionComponentPrecheckManifestPath)
  assert.equal(manifest.fixtureHtml, 'artifacts/ui-system-rebuild/20260707-production-component-precheck/component-fixture.html')
  assert.deepEqual(manifest.viewports.map((viewport) => viewport.id), ['compact', 'standard', 'large'])
  assert.deepEqual(manifest.foundationOwners, [
    'AppShell',
    'PageFrame',
    'WowPanel',
    'MaterialImage',
    'GameObjectIcon',
    'StatusVisual',
    'ActionButton',
    'ModuleCard',
    'ChannelDock',
    'RankedFeed',
    'EvidenceLedger',
    'ChatShell'
  ])
  assert.equal(manifest.measurements.length, 3)
  assert.ok(manifest.measurements.every((measurement) => measurement.ownerRects.length === 12))
  assert.ok(manifest.measurements.every((measurement) => measurement.document.horizontalOverflow <= 2))
  assert.equal(manifest.crops.length, 12)
  assert.deepEqual(manifest.failures, [])
  assert.deepEqual(manifest.warnings, [])
  assert.ok(manifest.checks.some((check) => check.id === 'production_component_precheck_is_clean' && check.status === 'pass'))
  assert.ok(manifest.checks.some((check) => check.id === 'all_viewports_measured' && check.status === 'pass' && check.count === 3))
  assert.ok(manifest.checks.some((check) => check.id === 'all_owner_rects_measured' && check.status === 'pass' && check.count === 12))
  assert.ok(manifest.checks.some((check) => check.id === 'standard_owner_crops_written' && check.status === 'pass' && check.count === 12))
  assert.ok(manifest.checks.some((check) => check.id === 'devtools_not_touched' && check.status === 'pass'))
  assert.ok(manifest.forbiddenPromotion.includes('implementation_permit'))
  assert.ok(manifest.forbiddenPromotion.includes('runtime_verified'))
  assert.ok(manifest.nextRequiredEvidence.includes('one-surface implementation permit'))
  assert.ok(manifest.nextRequiredEvidence.includes('real mini-program screenshots after captureSafe=true'))

  const fixtureHtml = read(manifest.fixtureHtml)
  assert.match(fixtureHtml, /回答依据会翻译成玩家能读懂的证据说明/)
  assert.match(fixtureHtml, /证据状态/)
  assert.match(fixtureHtml, /部分可用/)
  assert.doesNotMatch(fixtureHtml, /answerSource|confidence|job\.status|raw profile|raw SimC/)

  assert.ok(fs.existsSync(manifest.contactSheet), `${manifest.contactSheet} should exist`)
  const contactSize = readPngSize(manifest.contactSheet)
  assert.ok(contactSize.width >= 1000)
  assert.ok(contactSize.height >= 1000)
  for (const viewportScreenshot of manifest.viewportScreenshots) {
    assert.ok(fs.existsSync(viewportScreenshot), `${viewportScreenshot} should exist`)
    const size = readPngSize(viewportScreenshot)
    assert.ok(size.width >= 360)
    assert.ok(size.height >= 700)
  }
  for (const crop of manifest.crops) {
    assert.ok(fs.existsSync(crop.path), `${crop.path} should exist`)
    const size = readPngSize(crop.path)
    assert.ok(size.width >= 24)
    assert.ok(size.height >= 24)
  }

  assert.match(readme, /Status: `browser_component_precheck`/)
  assert.match(readme, /Failures: `0`/)
  assert.match(readme, /Warnings: `0`/)
  assert.match(readme, /devtools_not_touched: `pass`/)
})

test('news home implementation permit draft is scoped and not active', () => {
  const source = read(newsHomePermitDraftPath)
  const manifest = readJson(newsHomePermitDraftManifestPath)
  const readme = read(newsHomePermitDraftReadmePath)
  const appConfig = readJson('app.json')

  assert.match(source, /^Status: `implementation_permit_draft`$/m)
  assert.match(source, /not `target_locked`, not an active implementation permit/)
  assert.match(source, /does not authorize page WXML\/WXSS edits/)
  assert.match(source, /Surface: `news_home`/)
  assert.match(source, /Route: `\/pages\/news\/news`/)
  assert.match(source, /all-black/)
  assert.match(source, /No `app\.json` route or tabBar changes/)
  assert.match(source, /No WeChat DevTools open\/close\/restart\/cache-clear\/login\/logout actions/)
  assert.match(source, /No backend API contract changes/)
  assert.match(source, /No edits to unrelated surfaces/)
  assert.match(source, /No page-private status badge, card, button, icon socket, fake chrome or material geometry/)
  assert.match(source, /Fake read counts/)
  assert.match(source, /Imagegen story thumbnails/)
  assert.match(source, /Real WeChat mini-program screenshots after `captureSafe=true`/)
  assert.match(source, /This draft is ready for target-lock review\. It does not activate implementation\./)

  assert.equal(manifest.status, 'implementation_permit_draft')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.implementationPermit, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.surface, 'news_home')
  assert.equal(manifest.route, '/pages/news/news')
  assert.ok(appConfig.pages.includes(manifest.route.replace(/^\//, '')))
  assert.equal(manifest.sourceGoal, goalPath)
  assert.equal(manifest.sourcePermitDraft, newsHomePermitDraftPath)
  assert.equal(manifest.sourceTargetLockProposal, targetLockProposalPath)
  assert.equal(manifest.sourceAssetManifestDraft, assetManifestDraftPath)
  assert.equal(manifest.sourceRouteSmokePlan, routeSmokePlanPath)
  assert.equal(manifest.sourceProductionComponentPrecheck, productionComponentPrecheckManifestPath)
  assert.equal(manifest.sourceBrowserComponentPrecheck, browserComponentPrecheckManifestPath)
  assert.deepEqual(manifest.requiredBeforeActivation, [
    'user_confirmed_or_modified_target_lock',
    'accepted_or_revised_asset_manifest',
    'clean_production_component_precheck',
    'clean_browser_component_precheck',
    'explicit_conversion_from_draft_to_active_permit'
  ])
  assert.deepEqual(manifest.ownerComponents, [
    'AppShell',
    'PageFrame',
    'ChannelDock',
    'RankedFeed',
    'MaterialImage',
    'GameObjectIcon'
  ])
  assert.ok(manifest.proposedAllowedFilesAfterActivation.includes('pages/news/news.wxml'))
  assert.ok(manifest.proposedAllowedFilesAfterActivation.includes('components/channel-dock/*'))
  assert.ok(manifest.proposedAllowedFilesAfterActivation.includes('components/ranked-feed/*'))
  assert.ok(manifest.forbiddenFilesAndActions.includes('app.json route or tabBar changes'))
  assert.ok(manifest.forbiddenFilesAndActions.includes('project.config.json / appid / DevTools shadow changes'))
  assert.ok(manifest.forbiddenFilesAndActions.includes('backend API contract changes'))
  assert.ok(manifest.dataBoundary.allowed.includes('existing news home/list payload from pages/news/news-api.js'))
  assert.ok(manifest.dataBoundary.forbiddenClaims.includes('fake read counts'))
  assert.ok(manifest.dataBoundary.forbiddenClaims.includes('generated article thumbnails that imply real article imagery'))
  assert.ok(manifest.assetBoundary.forbidden.includes('imagegen story thumbnails'))
  assert.ok(manifest.assetBoundary.forbidden.includes('whole-page target images or contact sheets in production WXML/WXSS'))
  assert.deepEqual(manifest.routeSmokeScenes, [
    'news_home_top',
    'news_home_scrolled',
    'news_channel_official',
    'news_detail_first'
  ])
  assert.ok(manifest.requiredRuntimeArtifactsAfterImplementation.includes('real WeChat mini-program screenshots after captureSafe=true'))
  assert.ok(manifest.stopConditions.includes('target not locked'))
  assert.ok(manifest.stopConditions.includes('required component owner needs page-private geometry'))
  assert.ok(manifest.forbiddenPromotion.includes('active_implementation_permit'))
  assert.ok(manifest.forbiddenPromotion.includes('runtime_verified'))
  assert.ok(manifest.nextRequiredEvidence.includes('user confirmation or modification of target lock proposal'))

  assert.match(readme, /Status: `implementation_permit_draft`/)
  assert.match(readme, /not target locked, not an active implementation permit/)
  assert.match(readme, /Activation Gate/)
})

test('news list detail implementation permit draft protects source translation and is not active', () => {
  const source = read(newsListDetailPermitDraftPath)
  const manifest = readJson(newsListDetailPermitDraftManifestPath)
  const readme = read(newsListDetailPermitDraftReadmePath)
  const appConfig = readJson('app.json')

  assert.match(source, /^Status: `implementation_permit_draft`$/m)
  assert.match(source, /Surface: `news_list_detail`/)
  assert.match(source, /Primary routes: `\/pages\/news\/list`, `\/pages\/news\/detail`/)
  assert.match(source, /not `target_locked`, not an active implementation permit/)
  assert.match(source, /does not authorize page WXML\/WXSS edits/)
  assert.match(source, /final missing permit in the implementation permit coverage matrix after `profile_templates`/)
  assert.match(source, /News list owns channel\/metric query state, loading, empty, fallback and article-row navigation/)
  assert.match(source, /News detail owns title, original title, Chinese body blocks, source proof, badges, tags, copy-source action and not-found\/fallback states/)
  assert.match(source, /source_translation/)
  assert.match(source, /official_verified/)
  assert.match(source, /approved/)
  assert.match(source, /sourceTier=official/)
  assert.match(source, /complete translated bodies/)
  assert.match(source, /UI must not weaken those gates by hiding fallback\/incomplete states/)
  assert.match(source, /Current Source Findings/)
  assert.match(source, /pages\/news\/list\.wxml/)
  assert.match(source, /pages\/news\/detail\.wxml/)
  assert.match(source, /pages\/news\/news-api\.js/)
  assert.match(source, /contentStatus=ready/)
  assert.match(source, /translationFidelity=source_translation/)
  assert.match(source, /verificationStatus=official_verified/)
  assert.match(source, /licenseStatus=approved/)
  assert.match(source, /requestArticleList\(\)/)
  assert.match(source, /requestArticleDetail\(\)/)
  assert.match(source, /ArticleListBoard/)
  assert.match(source, /ArticleReader/)
  assert.match(source, /No manual refresh controls may be added/)
  assert.match(source, /Do not weaken `contentStatus`, `translationStatus`, `translationFidelity`, `verificationStatus`, `licenseStatus`, `sourceTier`/)
  assert.match(source, /Do not expose raw collector\/translator\/admin\/backend payloads or LLM commentary as article content/)
  assert.match(source, /This draft proves only that `news_list_detail` now has a scoped implementation permit draft/)

  assert.equal(manifest.status, 'implementation_permit_draft')
  assert.equal(manifest.surface, 'news_list_detail')
  assert.deepEqual(manifest.routes, ['/pages/news/list', '/pages/news/detail'])
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activePermit, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.sourcePermit, newsListDetailPermitDraftPath)
  assert.equal(manifest.sourceCoverageMatrix, permitCoverageMatrixPath)
  assert.equal(manifest.sourceOwnerSkeletonPrecheck, newsListDetailOwnerSkeletonPrecheckPath)
  assert.equal(manifest.ownerSkeletonArtifact, newsListDetailOwnerSkeletonManifestPath)
  assert.equal(manifest.sourceComponentPrecheck, newsListDetailComponentPrecheckPath)
  assert.equal(manifest.componentPrecheckArtifact, newsListDetailComponentPrecheckManifestPath)
  assert.deepEqual(manifest.requiredOwnerContracts, ['ArticleListBoard', 'ArticleReader'])
  for (const owner of ['PageFrame', 'WowPanel', 'RankedFeed', 'EvidenceLedger', 'ActionButton', 'MaterialImage', 'GameObjectIcon']) {
    assert.ok(manifest.foundationOwners.includes(owner), `${owner} should be a foundation owner`)
  }
  for (const protectedBehavior of [
    'article ready gates require contentStatus ready',
    'article ready gates require translationFidelity source_translation',
    'article ready gates require verificationStatus official_verified',
    'article ready gates require licenseStatus approved',
    'article ready gates require sourceTier official',
    'complete translated body required before live display',
    'fallback list/detail state remains visible',
    'bodyBlocksZh paragraph heading list quote preservation',
    'copy source action uses article.sourceUrl',
    'list row navigation preserves article id'
  ]) {
    assert.ok(manifest.protectedBehaviors.includes(protectedBehavior), `${protectedBehavior} should be protected`)
  }
  for (const forbiddenClaim of ['fake read counts', 'fake source logo', 'LLM commentary replacing source translation', 'manual refresh success', 'hidden fallback state']) {
    assert.ok(manifest.forbiddenClaims.includes(forbiddenClaim), `${forbiddenClaim} should be forbidden`)
  }
  for (const exposure of ['raw backend payload', 'raw collector metadata', 'raw translator JSON', 'raw LLM prompt or output']) {
    assert.ok(manifest.forbiddenExposures.includes(exposure), `${exposure} should be forbidden`)
  }
  assert.deepEqual(manifest.routeSmokeScenes, [
    'news_channel_official',
    'news_list_metric_updates',
    'news_list_loading',
    'news_list_empty',
    'news_list_fallback',
    'news_list_open_detail',
    'news_detail_first',
    'news_detail_missing_id',
    'news_detail_not_found',
    'news_detail_fallback',
    'news_detail_copy_source',
    'news_detail_back_to_list'
  ])
  for (const forbidden of ['target_locked', 'active_implementation_permit', 'component_precheck', 'runtime_verified', 'final_accepted']) {
    assert.ok(manifest.nonPromotionRule.includes(forbidden), `${forbidden} should not be promoted`)
  }
  assert.ok(manifest.nextRequiredEvidence.includes('accepted news list/detail material asset manifest entries'))
  assert.ok(manifest.nextRequiredEvidence.includes('convert news_list_detail draft into active implementation permit before page integration'))
  assert.ok(manifest.nextRequiredEvidence.includes('connect ArticleListBoard and ArticleReader to pages/news only under active permit'))
  assert.ok(manifest.nextRequiredEvidence.includes('real mini-program screenshots'))
  for (const route of manifest.routes) {
    assert.ok(appConfig.pages.includes(route.replace(/^\//, '')), `${route} should be registered`)
  }

  assert.match(readme, /Status: `implementation_permit_draft`/)
  assert.match(readme, /`news_list_detail` now has a dedicated implementation permit draft/)
  assert.match(readme, /ArticleListBoard/)
  assert.match(readme, /ArticleReader/)
  assert.match(readme, /not an active implementation permit/)
  assert.match(readme, /component evidence lives in `artifacts\/ui-system-rebuild\/20260707-news-list-detail-component-precheck\/`/)
  assert.match(readme, /No WeChat DevTools action was taken/)
})

test('builds tab implementation permit draft preserves upstream routes and is not active', () => {
  const source = read(buildsTabPermitDraftPath)
  const manifest = readJson(buildsTabPermitDraftManifestPath)
  const readme = read(buildsTabPermitDraftReadmePath)
  const appConfig = readJson('app.json')

  assert.match(source, /^Status: `implementation_permit_draft`$/m)
  assert.match(source, /rebuilding the `职业专精` tab as the upstream entry/)
  assert.match(source, /not `target_locked`, not an active implementation permit/)
  assert.match(source, /does not authorize page WXML\/WXSS edits/)
  assert.match(source, /Surface: `builds_tab`/)
  assert.match(source, /\/pages\/builds\/builds/)
  assert.match(source, /Current Source Findings/)
  assert.match(source, /`pages\/builds\/builds\.wxml` composes `builds-spec-console`, `workbench-entry` and `query-section` directly/)
  assert.match(source, /`pages\/builds\/builds\.wxss` owns shell gutters, hero grid, medallion geometry, workbench entry frame, workflow rail, quick action card geometry/)
  assert.match(source, /references `ui-v2-1-slices` generated materials directly/)
  assert.match(source, /keeps old quick routes through `openQueryPage\(\)`/)
  assert.match(source, /does not expose a full compact class\/spec\/hero switch contract/)
  assert.match(source, /Quick entries for talents, gear, SimC and tasks are still reachable and must remain reachable/)
  assert.match(source, /No backend API contract changes/)
  assert.match(source, /No deleting or hiding old talent, gear, SimC and task entrances/)
  assert.match(source, /No page-private hero, workbench entry, module card, status, action button, icon socket, workflow rail or material geometry/)
  assert.match(source, /Allowed data sources/)
  assert.match(source, /Existing `fallbackBuildsHome\(\)` and `requestBuildsHome\(\)` payload/)
  assert.match(source, /Existing `classIconUrlFor\(\)` and `specIconUrlFor\(\)` repository mappings/)
  assert.match(source, /Required UI mapping/)
  assert.match(source, /Current spec console must show selected class\/spec\/hero or conservative fallback/)
  assert.match(source, /Old four entries remain reachable and visibly downranked/)
  assert.match(source, /No DPS, damage preview or simulated result on the tab/)
  assert.match(source, /No real WoW icon unless it comes from payload, Battle\.net\/WebSim mapping, repository verified asset or user-provided source/)
  assert.match(source, /builds_tab_top/)
  assert.match(source, /builds_spec_switch/)
  assert.match(source, /builds_workbench_entry/)
  assert.match(source, /builds_talent_entry/)
  assert.match(source, /builds_gear_entry/)
  assert.match(source, /builds_simc_entry/)
  assert.match(source, /builds_tasks_entry/)
  assert.match(source, /`BuildsTabSurface` now has source-level owner skeleton evidence and a production\/browser component precheck/)
  assert.match(source, /It still does not activate implementation, and the component precheck must be rerun before any active permit conversion\./)

  assert.equal(manifest.status, 'implementation_permit_draft')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.implementationPermit, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.surface, 'builds_tab')
  assert.deepEqual(manifest.routes, ['/pages/builds/builds'])
  for (const route of manifest.routes) {
    assert.ok(appConfig.pages.includes(route.replace(/^\//, '')), `${route} should be registered`)
  }
  assert.equal(manifest.sourceGoal, goalPath)
  assert.equal(manifest.sourcePermitDraft, buildsTabPermitDraftPath)
  assert.equal(manifest.sourceTargetLockProposal, targetLockProposalPath)
  assert.equal(manifest.sourceAssetManifestDraft, assetManifestDraftPath)
  assert.equal(manifest.sourcePermitCoverageMatrix, permitCoverageMatrixPath)
  assert.equal(manifest.sourceRouteSmokePlan, routeSmokePlanPath)
  assert.equal(manifest.sourceProductionComponentPrecheck, productionComponentPrecheckManifestPath)
  assert.equal(manifest.sourceBrowserComponentPrecheck, browserComponentPrecheckManifestPath)
  assert.equal(manifest.sourceBuildsTabOwnerSkeletonPrecheck, buildsTabOwnerSkeletonPrecheckPath)
  assert.equal(manifest.buildsTabOwnerSkeletonArtifact, buildsTabOwnerSkeletonManifestPath)
  assert.equal(manifest.sourceBuildsTabComponentPrecheck, buildsTabComponentPrecheckPath)
  assert.equal(manifest.buildsTabComponentPrecheckArtifact, buildsTabComponentPrecheckManifestPath)
  assert.ok(manifest.currentSourceFindings.includes('pages/builds/builds.wxml composes builds-spec-console workbench-entry and query-section with page-private classes'))
  assert.ok(manifest.currentSourceFindings.includes('quick entries for talents gear SimC and tasks are still reachable and must remain reachable after rebuild'))
  assert.deepEqual(manifest.requiredBeforeActivation, [
    'user_confirmed_or_modified_target_lock',
    'accepted_or_revised_asset_manifest',
    'clean_builds_tab_surface_component_precheck_rerun_before_activation',
    'clean_browser_component_precheck',
    'explicit_conversion_from_draft_to_active_permit'
  ])
  assert.deepEqual(manifest.ownerComponents, [
    'BuildsTabSurface',
    'AppShell',
    'PageFrame',
    'WowPanel',
    'GameObjectIcon',
    'StatusVisual',
    'ActionButton',
    'ModuleCard',
    'MaterialImage'
  ])
  assert.ok(manifest.proposedAllowedFilesAfterActivation.includes('pages/builds/builds.wxml'))
  assert.ok(manifest.proposedAllowedFilesAfterActivation.includes('pages/builds/builds-api.js'))
  assert.ok(manifest.proposedAllowedFilesAfterActivation.includes('components/module-card/*'))
  assert.ok(manifest.proposedAllowedFilesAfterActivation.includes('components/builds-tab-surface/*'))
  assert.ok(manifest.forbiddenFilesAndActions.includes('app.json route or tabBar changes'))
  assert.ok(manifest.forbiddenFilesAndActions.includes('project.config.json / appid / DevTools shadow changes'))
  assert.ok(manifest.forbiddenFilesAndActions.includes('backend API contract changes'))
  assert.ok(manifest.forbiddenFilesAndActions.includes('deleting or hiding old talent gear SimC and task entrances'))
  assert.ok(manifest.dataBoundary.allowed.includes('existing fallbackBuildsHome and requestBuildsHome payload'))
  assert.match(manifest.dataBoundary.requiredUiMapping.current_spec_console, /class\/spec\/hero/)
  assert.match(manifest.dataBoundary.requiredUiMapping.compact_switchers, /without layout jump/)
  assert.match(manifest.dataBoundary.requiredUiMapping.old_entries, /remain reachable/)
  assert.ok(manifest.dataBoundary.forbiddenClaims.includes('DPS damage preview or simulated result'))
  assert.ok(manifest.assetBoundary.forbidden.includes('imagegen class/spec/hero/talent/item/source icons'))
  assert.deepEqual(manifest.routeSmokeScenes, [
    'builds_tab_top',
    'builds_spec_switch',
    'builds_workbench_entry',
    'builds_talent_entry',
    'builds_gear_entry',
    'builds_simc_entry',
    'builds_tasks_entry'
  ])
  assert.ok(manifest.requiredRuntimeArtifactsAfterImplementation.includes('real WeChat mini-program screenshots after captureSafe=true'))
  assert.ok(manifest.stopConditions.includes('design requires deleting or hiding old talent gear SimC or task entrances'))
  assert.ok(manifest.forbiddenPromotion.includes('active_implementation_permit'))
  assert.ok(manifest.forbiddenPromotion.includes('runtime_verified'))
  assert.ok(manifest.nextRequiredEvidence.includes('rerun BuildsTabSurface production/browser component precheck before activation'))
  assert.ok(manifest.nextRequiredEvidence.includes('convert this draft into an active builds_tab implementation permit'))

  assert.match(readme, /Status: `implementation_permit_draft`/)
  assert.match(readme, /not target locked, not an active implementation permit/)
  assert.match(readme, /`BuildsTabSurface` now has owner skeleton evidence and a production\/browser component precheck with 8 crops/)
  assert.match(readme, /Old talent, gear, SimC and task entrances must remain reachable/)
  assert.match(readme, /Activation Gate/)
})

test('chickenbro implementation permit draft is first-class and not active', () => {
  const source = read(chickenbroPermitDraftPath)
  const manifest = readJson(chickenbroPermitDraftManifestPath)
  const readme = read(chickenbroPermitDraftReadmePath)
  const appConfig = readJson('app.json')

  assert.match(source, /^Status: `implementation_permit_draft`$/m)
  assert.match(source, /making Chickenbro a first-class WOW mini-program surface/)
  assert.match(source, /not `target_locked`, not an active implementation permit/)
  assert.match(source, /does not authorize page WXML\/WXSS edits/)
  assert.match(source, /Surface: `chickenbro`/)
  assert.match(source, /\/pages\/simulator\/simulator/)
  assert.match(source, /\/pages\/simulator\/chickenbro/)
  assert.match(source, /Current Source Findings/)
  assert.match(source, /displays `assistantPayload\.answerSource` and `assistantPayload\.confidence`/)
  assert.match(source, /displays `job\.status`/)
  assert.match(source, /same visible raw field pattern/)
  assert.match(source, /instead of the target `ChatShell` owner contract/)
  assert.match(source, /No backend API contract changes/)
  assert.match(source, /No direct database \/ token \/ raw log \/ raw SimC exposure/)
  assert.match(source, /No page-private chat bubble, evidence row, status badge, input bar, drawer or material geometry/)
  assert.match(source, /Backend `answerSource` must be translated into user-language source labels/)
  assert.match(source, /Backend `confidence` must be translated into evidence strength language/)
  assert.match(source, /Backend `job\.status` must be translated into player-facing task states/)
  assert.match(source, /Forbidden visible text/)
  assert.match(source, /raw SimC profile/)
  assert.match(source, /unsupported DPS, ranking, percentile, S\/A grade or upgrade-priority claims/)
  assert.match(source, /smart_analysis_tab/)
  assert.match(source, /chickenbro_workbench_context/)
  assert.match(source, /input_focus/)
  assert.match(source, /long_message_scroll/)
  assert.match(source, /Clean Chickenbro surface component precheck with production WXSS class names/)
  assert.match(source, /Clean browser component precheck rerun before activation/)
  assert.match(source, /3 viewport screenshots, 8 component crops, failures=0, warnings=0 and horizontalOverflow=0/)
  assert.match(source, /This still does not activate implementation/)

  assert.equal(manifest.status, 'implementation_permit_draft')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.implementationPermit, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.surface, 'chickenbro')
  assert.deepEqual(manifest.routes, ['/pages/simulator/simulator', '/pages/simulator/chickenbro'])
  for (const route of manifest.routes) {
    assert.ok(appConfig.pages.includes(route.replace(/^\//, '')), `${route} should be registered`)
  }
  assert.equal(manifest.sourceGoal, goalPath)
  assert.equal(manifest.sourcePermitDraft, chickenbroPermitDraftPath)
  assert.equal(manifest.sourceTargetLockProposal, targetLockProposalPath)
  assert.equal(manifest.sourceAssetManifestDraft, assetManifestDraftPath)
  assert.equal(manifest.sourceRouteSmokePlan, routeSmokePlanPath)
  assert.equal(manifest.sourceProductionComponentPrecheck, productionComponentPrecheckManifestPath)
  assert.equal(manifest.sourceBrowserComponentPrecheck, browserComponentPrecheckManifestPath)
  assert.equal(manifest.sourceChickenbroOwnerSkeletonPrecheck, chickenbroOwnerSkeletonPrecheckPath)
  assert.equal(manifest.chickenbroOwnerSkeletonArtifact, chickenbroOwnerSkeletonManifestPath)
  assert.equal(manifest.sourceChickenbroComponentPrecheck, chickenbroComponentPrecheckPath)
  assert.equal(manifest.chickenbroComponentPrecheckArtifact, chickenbroComponentPrecheckManifestPath)
  assert.equal(manifest.surfaceComponentPrecheck, true)
  assert.ok(manifest.currentSourceFindings.includes('pages/simulator/chickenbro.wxml displays assistantPayload.answerSource and assistantPayload.confidence'))
  assert.ok(manifest.currentSourceFindings.includes('pages/simulator/simulator.wxml has the same visible raw field pattern'))
  assert.deepEqual(manifest.requiredBeforeActivation, [
    'user_confirmed_or_modified_target_lock',
    'accepted_or_revised_asset_manifest',
    'clean_chickenbro_surface_component_precheck_rerun_before_activation',
    'accepted_chickenbro_owner_skeleton',
    'explicit_conversion_from_draft_to_active_permit'
  ])
  assert.deepEqual(manifest.ownerComponents, [
    'ChickenbroCoachSurface',
    'ChatShell',
    'PageFrame',
    'EvidenceLedger',
    'StatusVisual',
    'ActionButton',
    'MaterialImage'
  ])
  assert.ok(manifest.proposedAllowedFilesAfterActivation.includes('pages/simulator/chickenbro.wxml'))
  assert.ok(manifest.proposedAllowedFilesAfterActivation.includes('pages/simulator/simulator.wxml'))
  assert.ok(manifest.proposedAllowedFilesAfterActivation.includes('pages/simulator/chickenbro-chat.js'))
  assert.ok(manifest.proposedAllowedFilesAfterActivation.includes('components/chat-shell/*'))
  assert.ok(manifest.forbiddenFilesAndActions.includes('backend API contract changes'))
  assert.ok(manifest.forbiddenFilesAndActions.includes('direct database token raw log raw SimC exposure'))
  assert.ok(manifest.dataBoundary.allowed.includes('existing /api/chickenbro/messages session and job client calls'))
  assert.ok(manifest.dataBoundary.requiredUiMapping.answerSource.includes('证据不足'))
  assert.ok(manifest.dataBoundary.requiredUiMapping.confidence.includes('部分可用'))
  assert.ok(manifest.dataBoundary.requiredUiMapping['job.status'].includes('整理中'))
  assert.ok(manifest.dataBoundary.forbiddenVisibleText.includes('answerSource'))
  assert.ok(manifest.dataBoundary.forbiddenVisibleText.includes('confidence'))
  assert.ok(manifest.dataBoundary.forbiddenVisibleText.includes('job.status'))
  assert.ok(manifest.assetBoundary.forbidden.includes('imagegen portraits pretending to be Chickenbro evidence'))
  assert.deepEqual(manifest.routeSmokeScenes, [
    'smart_analysis_tab',
    'chickenbro_empty',
    'chickenbro_workbench_context',
    'chickenbro_generating',
    'chickenbro_done',
    'chickenbro_failed',
    'topic_drawer',
    'input_focus',
    'long_message_scroll'
  ])
  assert.ok(manifest.requiredRuntimeArtifactsAfterImplementation.includes('real WeChat mini-program screenshots after captureSafe=true'))
  assert.ok(manifest.stopConditions.includes('visible UI needs raw backend fields to explain evidence'))
  assert.ok(manifest.stopConditions.includes('page requires direct WXML/WXSS geometry for chat bubbles evidence rows drawer or input bar'))
  assert.ok(manifest.forbiddenPromotion.includes('active_implementation_permit'))
  assert.ok(manifest.forbiddenPromotion.includes('runtime_verified'))
  assert.ok(manifest.nextRequiredEvidence.includes('user confirmation or modification of target lock proposal'))
  assert.ok(manifest.nextRequiredEvidence.includes('accepted ChickenbroCoachSurface owner skeleton and fixture matrix'))
  assert.ok(manifest.nextRequiredEvidence.includes('rerun Chickenbro surface component precheck before activation'))

  assert.match(readme, /Status: `implementation_permit_draft`/)
  assert.match(readme, /not target locked, not an active implementation permit/)
  assert.match(readme, /Current WXML exposes backend-facing evidence fields/)
  assert.match(readme, /ChickenbroCoachSurface/)
  assert.match(readme, /20260707-chickenbro-component-precheck\/manifest\.json/)
  assert.match(readme, /failures=0 and warnings=0/)
  assert.match(readme, /Activation Gate/)
})

test('workbench implementation permit draft is readiness-gated and not active', () => {
  const source = read(workbenchPermitDraftPath)
  const manifest = readJson(workbenchPermitDraftManifestPath)
  const readme = read(workbenchPermitDraftReadmePath)
  const appConfig = readJson('app.json')

  assert.match(source, /^Status: `implementation_permit_draft`$/m)
  assert.match(source, /current spec workbench as the central evidence cockpit/)
  assert.match(source, /not `target_locked`, not an active implementation permit/)
  assert.match(source, /does not authorize page WXML\/WXSS edits/)
  assert.match(source, /Surface: `current_spec_workbench`/)
  assert.match(source, /\/pages\/builds\/workbench\?spec=<spec>/)
  assert.match(source, /\/pages\/builds\/builds/)
  assert.match(source, /Current Source Findings/)
  assert.match(source, /page-private classes such as `workbench-hero`, `verdict-slab`, `module-card`, `evidence-row` and `primary-action`/)
  assert.match(source, /`pages\/builds\/workbench\.wxss` owns gutters, panel borders, module geometry, evidence row tracks, button sizing and state tone classes/)
  assert.match(source, /still references `ui-v2-1-slices` material assets directly/)
  assert.match(source, /legacy `status-badge` path and page-level `verdict-status-badge` geometry/)
  assert.match(source, /target owner is `StatusVisual`/)
  assert.match(source, /`pages\/builds\/workbench-state\.js` correctly keeps `canShowStrongResult: false`/)
  assert.match(source, /No backend API contract changes/)
  assert.match(source, /No page-private shield\/glyph\/status, panel, card, button, socket, evidence row or material geometry/)
  assert.match(source, /Allowed data sources/)
  assert.match(source, /Existing `\/api\/websim\/talents` through `requestWebsimTalents\(\)`/)
  assert.match(source, /Existing `\/api\/websim\/gear` through `requestWebsimGear\(\)`/)
  assert.match(source, /Required UI mapping/)
  assert.match(source, /`ready_to_simulate`: show input completeness and route to existing SimC page/)
  assert.match(source, /`blocked`: show what is missing, what it affects and the next route to fix it/)
  assert.match(source, /`partial`: show usable evidence and missing coverage without a strong result/)
  assert.match(source, /`stale`: show freshness problem and refresh\/source action/)
  assert.match(source, /`source_reference`: show source-reference language and evidence expansion/)
  assert.match(source, /Forbidden product claims/)
  assert.match(source, /No DPS or damage preview/)
  assert.match(source, /No comprehensive score/)
  assert.match(source, /No S\/A grade/)
  assert.match(source, /No upgrade priority/)
  assert.match(source, /No real WoW object icon unless it comes from API payload, Battle\.net\/WebSim mapping, repository verified asset or user-provided source/)
  assert.match(source, /Status base\/glyph material only through `StatusVisual`/)
  assert.match(source, /workbench_blocked_gear/)
  assert.match(source, /workbench_source_reference/)
  assert.match(source, /talent_simulator_load/)
  assert.match(source, /gear_detail_load/)
  assert.match(source, /simc_from_workbench/)
  assert.match(source, /chickenbro_workbench_context/)
  assert.match(source, /State visuals are a single component, not split shield\/background\/glyph pieces/)
  assert.match(source, /This draft is ready for target-lock review\. `WorkbenchCockpitSurface` now has source-level owner skeleton evidence/)
  assert.match(source, /It still does not activate implementation, and the component precheck must be rerun before any active permit conversion\./)

  assert.equal(manifest.status, 'implementation_permit_draft')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.implementationPermit, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.surface, 'current_spec_workbench')
  assert.deepEqual(manifest.routes, ['/pages/builds/workbench', '/pages/builds/builds'])
  for (const route of manifest.routes) {
    assert.ok(appConfig.pages.includes(route.replace(/^\//, '')), `${route} should be registered`)
  }
  assert.equal(manifest.sourceGoal, goalPath)
  assert.equal(manifest.sourcePermitDraft, workbenchPermitDraftPath)
  assert.equal(manifest.sourceTargetLockProposal, targetLockProposalPath)
  assert.equal(manifest.sourceAssetManifestDraft, assetManifestDraftPath)
  assert.equal(manifest.sourceRouteSmokePlan, routeSmokePlanPath)
  assert.equal(manifest.sourceProductionComponentPrecheck, productionComponentPrecheckManifestPath)
  assert.equal(manifest.sourceBrowserComponentPrecheck, browserComponentPrecheckManifestPath)
  assert.equal(manifest.sourceWorkbenchOwnerSkeletonPrecheck, workbenchOwnerSkeletonPrecheckPath)
  assert.equal(manifest.workbenchOwnerSkeletonArtifact, workbenchOwnerSkeletonManifestPath)
  assert.equal(manifest.sourceWorkbenchComponentPrecheck, workbenchComponentPrecheckPath)
  assert.equal(manifest.workbenchComponentPrecheckArtifact, workbenchComponentPrecheckManifestPath)
  assert.equal(manifest.surfaceComponentPrecheck, true)
  assert.ok(manifest.currentSourceFindings.includes('pages/builds/workbench.wxml composes hero readiness slab module band and evidence rows with page-private classes'))
  assert.ok(manifest.currentSourceFindings.includes('verdict status uses legacy status-badge path and page-level verdict-status-badge geometry while the target owner is StatusVisual'))
  assert.ok(manifest.currentSourceFindings.includes('pages/builds/workbench-state.js keeps canShowStrongResult false and no DPS score S/A grade or upgrade-priority claims'))
  assert.deepEqual(manifest.requiredBeforeActivation, [
    'user_confirmed_or_modified_target_lock',
    'accepted_or_revised_asset_manifest',
    'clean_workbench_surface_component_precheck_rerun_before_activation',
    'clean_production_component_precheck',
    'clean_browser_component_precheck',
    'explicit_conversion_from_draft_to_active_permit'
  ])
  assert.deepEqual(manifest.ownerComponents, [
    'PageFrame',
    'WowPanel',
    'StatusVisual',
    'ActionButton',
    'ModuleCard',
    'EvidenceLedger',
    'GameObjectIcon',
    'MaterialImage'
  ])
  assert.ok(manifest.proposedAllowedFilesAfterActivation.includes('pages/builds/workbench.wxml'))
  assert.ok(manifest.proposedAllowedFilesAfterActivation.includes('pages/builds/workbench-state.js'))
  assert.ok(manifest.proposedAllowedFilesAfterActivation.includes('pages/builds/builds.wxml'))
  assert.ok(manifest.proposedAllowedFilesAfterActivation.includes('components/status-visual/*'))
  assert.ok(manifest.proposedAllowedFilesAfterActivation.includes('components/evidence-ledger/*'))
  assert.ok(manifest.forbiddenFilesAndActions.includes('app.json route or tabBar changes'))
  assert.ok(manifest.forbiddenFilesAndActions.includes('project.config.json / appid / DevTools shadow changes'))
  assert.ok(manifest.forbiddenFilesAndActions.includes('backend API contract changes'))
  assert.ok(manifest.forbiddenFilesAndActions.includes('page-private shield glyph status panel card button socket evidence row or material geometry'))
  assert.ok(manifest.dataBoundary.allowed.includes('existing /api/websim/talents through requestWebsimTalents'))
  assert.ok(manifest.dataBoundary.allowed.includes('existing pure aggregation in pages/builds/workbench-state.js'))
  assert.match(manifest.dataBoundary.requiredUiMapping.ready_to_simulate, /existing SimC page/)
  assert.match(manifest.dataBoundary.requiredUiMapping.blocked, /what is missing/)
  assert.match(manifest.dataBoundary.requiredUiMapping.partial, /without a strong result/)
  assert.match(manifest.dataBoundary.requiredUiMapping.stale, /freshness/)
  assert.match(manifest.dataBoundary.requiredUiMapping.source_reference, /not recommendation/)
  assert.ok(manifest.dataBoundary.forbiddenClaims.includes('DPS or damage preview'))
  assert.ok(manifest.dataBoundary.forbiddenClaims.includes('comprehensive score'))
  assert.ok(manifest.dataBoundary.forbiddenClaims.includes('S/A grade'))
  assert.ok(manifest.dataBoundary.forbiddenClaims.includes('upgrade priority'))
  assert.ok(manifest.assetBoundary.forbidden.includes('imagegen class/spec/talent/item/source icons'))
  assert.ok(manifest.assetBoundary.forbidden.includes('direct ui-v2-1-slices page references outside active permit production manifest entries'))
  assert.deepEqual(manifest.routeSmokeScenes, [
    'builds_tab_top',
    'workbench_ready',
    'workbench_blocked_gear',
    'workbench_partial_talent',
    'workbench_stale',
    'workbench_source_reference',
    'workbench_evidence_expanded',
    'talent_simulator_load',
    'gear_detail_load',
    'simc_from_workbench',
    'chickenbro_workbench_context'
  ])
  assert.ok(manifest.requiredRuntimeArtifactsAfterImplementation.includes('real WeChat mini-program screenshots after captureSafe=true'))
  assert.ok(manifest.stopConditions.includes('StatusVisual cannot own state base and glyph without split ownership'))
  assert.ok(manifest.forbiddenPromotion.includes('active_implementation_permit'))
  assert.ok(manifest.forbiddenPromotion.includes('runtime_verified'))
  assert.ok(manifest.nextRequiredEvidence.includes('rerun WorkbenchCockpitSurface production/browser component precheck before activation'))
  assert.ok(manifest.nextRequiredEvidence.includes('convert this draft into an active current_spec_workbench implementation permit'))

  assert.match(readme, /Status: `implementation_permit_draft`/)
  assert.match(readme, /not target locked, not an active implementation permit/)
  assert.match(readme, /Current source inspection shows the page still owns panel, button, module, evidence and status geometry locally/)
  assert.match(readme, /`WorkbenchCockpitSurface` now has source-level owner skeleton evidence and a production\/browser component precheck/)
  assert.match(readme, /failures=0 and warnings=0/)
  assert.match(readme, /Activation Gate/)
})

test('talent simulator implementation permit draft preserves WebSim tree rules and is not active', () => {
  const source = read(talentSimulatorPermitDraftPath)
  const manifest = readJson(talentSimulatorPermitDraftManifestPath)
  const readme = read(talentSimulatorPermitDraftReadmePath)

  assert.match(source, /^Status: `implementation_permit_draft`$/m)
  assert.match(source, /rebuilding the native WebSim talent simulator page/)
  assert.match(source, /not `target_locked`, not an active implementation permit/)
  assert.match(source, /Surface: `talent_simulator`/)
  assert.match(source, /`\/pages\/builds\/talent-simulator`/)
  assert.match(source, /first missing permit in the current implementation permit coverage matrix/)
  assert.match(source, /real WebSim talent-tree interaction, point gates, choice nodes/)
  assert.match(source, /`talent-header`, `talent-toolbar`, `tree-tabs`, `active-tree-panel`, `talent-grid`, `talent-node`, fixed `mobile-action-bar`/)
  assert.match(source, /`pages\/builds\/talent-simulator\.wxss` owns page background, panel borders, picker geometry, tree-tab geometry, active tree panel, node shape, choice frame, arrows, link lines, rank badge/)
  assert.match(source, /`requestWebsimBootstrap\(\)` and `requestWebsimTalents\(\)`/)
  assert.match(source, /`buildTalentViewModel\(\)`, `initialTalentRanks\(\)`, `tapTalentNode\(\)`, `adjustTalentRank\(\)`, `choiceGroupNodes\(\)`, `parseTalentExportCode\(\)`/)
  assert.match(source, /point caps, granted ranks, parent requirements, choice mutual exclusion, shape normalization, link geometry/)
  assert.match(source, /blocks saving when the WebSim talent payload is fallback/)
  assert.match(source, /`rawString` as a WebSim export code and keeps `simcLines: \[\]`/)
  assert.match(source, /Real talent icons are attached through `attachGameAsset\(\)` as `entityType: 'talent'`/)
  assert.match(source, /`TalentTreeCanvas` owner skeleton and fixture matrix remain aligned with the target lock/)
  assert.match(source, /TalentTreeCanvas Owner Skeleton Source Precheck/)
  assert.match(source, /TalentTreeCanvas Component Precheck/)
  assert.match(source, /Current Owner Evidence/)
  assert.match(source, /Current precheck result: `surface_component_precheck`, failures `0`, warnings `0`, crops `8`/)
  assert.match(source, /Surface-specific owner for tree grid dimensions, node positions, link lines, choice node frame, rank badge and touch target geometry/)
  assert.match(source, /No backend API contract changes/)
  assert.match(source, /No page-private tree node, link line, choice frame, rank badge, panel, status, action button, fixed action-bar, evidence row, sheet or material geometry/)
  assert.match(source, /No weakening parent requirement, point cap, granted rank, choice mutual exclusion, cross-spec template, fallback-block or save-readiness rules/)
  assert.match(source, /Existing `requestWebsimTalents\(\)` payload/)
  assert.match(source, /Existing `talent-simulator-core` rule helpers/)
  assert.match(source, /`tree_ready`: show real class\/spec\/hero tree tabs, point caps and export-code readiness/)
  assert.match(source, /`choice_sheet`: show mutually exclusive choices with real talent icons or text fallback/)
  assert.match(source, /`save_ready`: show save action only after class\/spec\/hero trees are capped and WebSim export code is available/)
  assert.match(source, /`community_visual_import`: apply visual community templates and preserve cross-spec switch behavior/)
  assert.match(source, /No DPS, damage, ranking, percentile, tier, S\/A grade, comprehensive score or upgrade priority/)
  assert.match(source, /`talent_tree_ready`/)
  assert.match(source, /`talent_community_missing_credentials`/)
  assert.match(source, /This draft is ready for target-lock review and active-permit decision after `TalentTreeCanvas` owner evidence/)
  assert.match(source, /rerun the component precheck against the locked target and convert this draft into an active permit/)

  assert.equal(manifest.status, 'implementation_permit_draft')
  assert.equal(manifest.surface, 'talent_simulator')
  assert.deepEqual(manifest.routes, ['/pages/builds/talent-simulator'])
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.implementationPermit, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.sourcePermitDraft, talentSimulatorPermitDraftPath)
  assert.equal(manifest.sourcePermitCoverageMatrix, permitCoverageMatrixPath)
  assert.deepEqual(manifest.requiredBeforeActivation, [
    'user_confirmed_or_modified_target_lock',
    'accepted_or_revised_asset_manifest',
    'TalentTreeCanvas_owner_skeleton_and_fixture_matrix',
    'clean_TalentTreeCanvas_component_precheck_rerun_before_activation',
    'explicit_conversion_from_draft_to_active_permit'
  ])
  assert.equal(manifest.sourceTalentTreeCanvasOwnerSkeletonPrecheck, talentTreeCanvasOwnerSkeletonPrecheckPath)
  assert.equal(manifest.talentTreeCanvasOwnerSkeletonArtifact, talentTreeCanvasOwnerSkeletonManifestPath)
  assert.equal(manifest.sourceTalentTreeCanvasComponentPrecheck, talentTreeCanvasComponentPrecheckPath)
  assert.equal(manifest.talentTreeCanvasComponentPrecheckArtifact, talentTreeCanvasComponentPrecheckManifestPath)
  assert.deepEqual(manifest.ownerComponents, [
    'PageFrame',
    'WowPanel',
    'TalentTreeCanvas',
    'GameObjectIcon',
    'StatusVisual',
    'ActionButton',
    'EvidenceLedger',
    'ModuleCard',
    'MaterialImage'
  ])
  assert.ok(manifest.currentSourceFindings.some((item) => item.includes('talent-header talent-toolbar tree-tabs active-tree-panel talent-grid talent-node')))
  assert.ok(manifest.currentSourceFindings.some((item) => item.includes('point caps granted ranks parent requirements choice mutual exclusion shape normalization link geometry')))
  assert.ok(manifest.currentSourceFindings.some((item) => item.includes('blocks saving on fallback talent payload')))
  assert.ok(manifest.proposedAllowedFilesAfterActivation.includes('components/talent-tree-canvas/*'))
  assert.ok(manifest.forbiddenFilesAndActions.includes('backend API contract changes'))
  assert.ok(manifest.forbiddenFilesAndActions.includes('weakening parent requirement point cap granted rank choice mutual exclusion cross-spec template fallback-block or save-readiness rules'))
  assert.ok(manifest.dataBoundary.allowed.includes('existing requestWebsimTalents payload for nodes tree sections hero key talent authority readiness and community templates'))
  assert.ok(manifest.dataBoundary.allowed.includes('existing talent-simulator-core rule helpers for point gates choice groups node shape export code community template filtering and cross-spec application'))
  assert.equal(manifest.dataBoundary.requiredUiMapping.tree_ready, 'show real class/spec/hero tree tabs point caps and export-code readiness')
  assert.equal(manifest.dataBoundary.requiredUiMapping.save_ready, 'show save action only after class/spec/hero trees are capped and WebSim export code is available')
  assert.equal(manifest.dataBoundary.requiredUiMapping.community_simc_only, 'refuse simc-only external code in the visual editor with user-facing copy')
  assert.ok(manifest.dataBoundary.forbiddenClaims.includes('DPS damage ranking percentile tier S/A grade comprehensive score or upgrade priority'))
  assert.ok(manifest.assetBoundary.forbidden.includes('imagegen class/spec/hero/talent/source icons'))
  assert.deepEqual(manifest.routeSmokeScenes, [
    'talent_simulator_from_builds',
    'talent_simulator_from_workbench',
    'talent_loading_bootstrap',
    'talent_loading_tree',
    'talent_tree_ready',
    'talent_switch_class_spec',
    'talent_switch_hero',
    'talent_tree_tab_switch',
    'talent_node_locked',
    'talent_choice_sheet',
    'talent_detail_sheet',
    'talent_save_blocked',
    'talent_save_ready',
    'talent_personal_import',
    'talent_community_visual_import',
    'talent_community_simc_only',
    'talent_community_missing_credentials'
  ])
  assert.ok(manifest.requiredRuntimeArtifactsAfterImplementation.includes('real WeChat mini-program screenshots after captureSafe=true'))
  assert.ok(manifest.stopConditions.includes('TalentTreeCanvas or equivalent tree owner is not defined before page integration'))
  assert.ok(manifest.stopConditions.includes('talent-rule tests fail or visual changes require weakening point caps parent gates choice exclusivity or save-readiness gates'))
  assert.ok(manifest.forbiddenPromotion.includes('active_implementation_permit'))
  assert.ok(manifest.forbiddenPromotion.includes('runtime_verified'))
  assert.ok(manifest.nextRequiredEvidence.includes('rerun TalentTreeCanvas surface component precheck before activation'))
  assert.ok(manifest.nextRequiredEvidence.includes('convert this draft into an active talent_simulator implementation permit'))
  assert.ok(manifest.nextRequiredEvidence.includes('then implement using owner components only'))

  assert.match(readme, /Status: `implementation_permit_draft`/)
  assert.match(readme, /not target locked, not an active implementation permit, and not runtime verified/)
  assert.match(readme, /existing WebSim rule path, point caps, parent gates, granted ranks, choice mutual exclusion, cross-spec import, save-readiness blockers and template persistence must be preserved/)
  assert.match(readme, /`TalentTreeCanvas` now has an owner skeleton, fixture matrix and surface component precheck/)
  assert.match(readme, /clean `TalentTreeCanvas` surface component precheck rerun before activation/)
})

test('gear detail owner skeleton source precheck separates loadout and config sheet UI from page geometry', () => {
  const source = read(gearDetailOwnerSkeletonPrecheckPath)
  const manifest = readJson(gearDetailOwnerSkeletonManifestPath)
  const fixtures = readJson(gearDetailOwnerSkeletonFixturesPath)
  const readme = read(gearDetailOwnerSkeletonReadmePath)

  assert.match(source, /Status: `owner_skeleton_source_precheck`/)
  assert.match(source, /Surface: `gear_detail`/)
  assert.match(source, /`GearLoadoutBoard`/)
  assert.match(source, /`GearConfigSheet`/)
  assert.match(source, /16-slot board geometry/)
  assert.match(source, /candidate rows, item icon\/title\/source\/status alignment/)
  assert.match(source, /No visible `DPS`, `BiS`, `综合评分`, `S\/A 级`, `提升优先级`/)
  assert.match(source, /targetLocked=false/)
  assert.match(source, /pageIntegration=false/)
  assert.match(source, /runtimeVerified=false/)
  assert.match(source, /devtoolsTouched=false/)

  assert.equal(manifest.status, 'owner_skeleton_source_precheck')
  assert.equal(manifest.surface, 'gear_detail')
  assert.deepEqual(manifest.ownerComponents, ['GearLoadoutBoard', 'GearConfigSheet'])
  assert.equal(manifest.pageIntegration, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activePermit, false)
  assert.ok(manifest.sourceFiles.includes('components/gear-loadout-board/gear-loadout-board.js'))
  assert.ok(manifest.sourceFiles.includes('components/gear-config-sheet/gear-config-sheet.js'))
  assert.ok(manifest.nonPromotionGates.includes('not_runtime_verified'))
  assert.ok(manifest.dataTrustRules.includes('no DPS'))
  assert.ok(manifest.dataTrustRules.includes('no generated WoW item icons'))
  assert.ok(manifest.nextRequiredEvidence.includes('gear_detail component/browser precheck crops'))

  assert.deepEqual(fixtures.ownerComponents, ['GearLoadoutBoard', 'GearConfigSheet'])
  assert.ok(fixtures.gearLoadoutBoard.some((item) => item.fixtureId === 'gear_loadout_ready'))
  assert.ok(fixtures.gearLoadoutBoard.some((item) => item.fixtureId === 'gear_loadout_blocked_slots'))
  assert.ok(fixtures.gearConfigSheet.some((item) => item.fixtureId === 'gear_config_variant_choice'))
  assert.ok(fixtures.gearConfigSheet.some((item) => item.fixtureId === 'gear_config_enhancement_blocked'))
  assert.doesNotMatch(JSON.stringify({
    gearLoadoutBoard: fixtures.gearLoadoutBoard,
    gearConfigSheet: fixtures.gearConfigSheet
  }), /DPS|BiS|综合评分|S\s*级|A\s*级|提升优先级/)

  for (const filePath of manifest.sourceFiles) {
    assert.ok(fs.existsSync(filePath), `${filePath} exists`)
  }
  assert.match(readme, /Status: `owner_skeleton_source_precheck`/)
  assert.match(readme, /not `target_locked`, not an active permit, not page integration/)
})

test('gear detail component precheck records browser crops without page or runtime promotion', () => {
  const source = read(gearDetailComponentPrecheckPath)
  const manifest = readJson(gearDetailComponentPrecheckManifestPath)
  const readme = read(gearDetailComponentPrecheckReadmePath)

  assert.match(source, /Status: `surface_component_precheck`/)
  assert.match(source, /Surface: `gear_detail`/)
  assert.match(source, /`GearLoadoutBoard`/)
  assert.match(source, /`GearConfigSheet`/)
  assert.match(source, /failures=0/)
  assert.match(source, /10 owner crops/)
  assert.match(source, /devtoolsTouched=false/)
  assert.match(source, /does not connect `GearLoadoutBoard` or `GearConfigSheet` to `pages\/builds\/detail`/)

  assert.equal(manifest.status, 'surface_component_precheck')
  assert.equal(manifest.surface, 'gear_detail')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activePermit, false)
  assert.equal(manifest.componentPrecheck, true)
  assert.equal(manifest.browserPrecheck, true)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.pageIntegration, false)
  assert.equal(manifest.browserEngine, 'chrome_headless_cdp')
  assert.equal(manifest.sourceOwnerSkeletonPrecheck, gearDetailOwnerSkeletonPrecheckPath)
  assert.equal(manifest.sourceOwnerSkeletonArtifact, gearDetailOwnerSkeletonManifestPath)
  assert.equal(manifest.sourceComponentPrecheckDoc, gearDetailComponentPrecheckPath)
  assert.equal(manifest.failures.length, 0)
  assert.equal(manifest.warnings.length, 0)
  assert.equal(manifest.viewports.length, 3)
  assert.equal(manifest.viewportScreenshots.length, 3)
  assert.equal(manifest.crops.length, 10)
  assert.ok(manifest.ownerReports.every((report) => report.status === 'pass'))
  assert.ok(manifest.checks.every((check) => check.status === 'pass'))
  assert.ok(manifest.forbiddenPromotion.includes('runtime_verified'))
  assert.ok(manifest.nextRequiredEvidence.includes('connect GearLoadoutBoard and GearConfigSheet to pages/builds/detail only under active permit'))
  assert.ok(fs.existsSync(manifest.fixtureHtml))
  assert.ok(fs.existsSync(manifest.contactSheet))
  for (const screenshot of manifest.viewportScreenshots) {
    const size = readPngSize(screenshot)
    assert.ok(size.width > 0)
    assert.ok(size.height > 0)
  }
  for (const crop of manifest.crops) {
    const size = readPngSize(crop.path)
    assert.ok(size.width > 0)
    assert.ok(size.height > 0)
  }

  assert.match(readme, /Status: `surface_component_precheck`/)
  assert.match(readme, /Failures: `0`/)
  assert.match(readme, /Warnings: `0`/)
  assert.match(readme, /gear-loadout-slot-grid/)
  assert.match(readme, /gear-config-enhancement-group/)
})

test('gear detail implementation permit draft protects real item readiness and is not active', () => {
  const source = read(gearDetailPermitDraftPath)
  const manifest = readJson(gearDetailPermitDraftManifestPath)
  const readme = read(gearDetailPermitDraftReadmePath)
  const appConfig = readJson('app.json')

  assert.match(source, /^Status: `implementation_permit_draft`$/m)
  assert.match(source, /rebuilding the gear detail \/ gear simulator page/)
  assert.match(source, /not `target_locked`, not an active implementation permit/)
  assert.match(source, /Surface: `gear_detail`/)
  assert.match(source, /`\/pages\/builds\/detail\?query=gear`/)
  assert.match(source, /next missing permit in the current implementation permit coverage matrix after the talent simulator draft/)
  assert.match(source, /16-slot readiness, real replacement candidates, item-level variants, crafted stat choices, sockets, enchants, embellishments/)
  assert.match(source, /`gear-panel`, `gear-request-alert`, `gear-attribute-panel`, `gear-attribute-grid`, `gear-slot-grid`, `gear-slot-card`/)
  assert.match(source, /`requestWebsimGear\(\)` and `requestWebsimGearStats\(\)`/)
  assert.match(source, /`gearPayloadCache`, `gearSlotCandidateCache`, `gearInitialLoading`, `gearDataFallback`, `gearStatSnapshot`/)
  assert.match(source, /`buildGearSlotRows\(\)`, `buildGearAttributePanel\(\)`, `buildGearSlotSheet\(\)`, `buildGearEnhancementSheet\(\)`/)
  assert.match(source, /source-reference gear, missing\/untrusted slots, heavy candidate cache behavior, catalog fallback, stat snapshot request gates/)
  assert.match(source, /blocks saving or applying when required gear slots are missing/)
  assert.match(source, /structured `gearBySlot` and `enhancementBySlot` snapshot/)
  assert.match(source, /Real item icons are attached through `attachGameAsset\(\)`/)
  assert.match(source, /`GearLoadoutBoard` owner skeleton and fixture matrix remain valid after target lock/)
  assert.match(source, /`GearConfigSheet` owner skeleton and fixture matrix remain valid after target lock/)
  assert.match(source, /Surface-specific owner for 16-slot grid, slot dimensions, slot status, icon sockets/)
  assert.match(source, /Surface-specific owner for candidate list, item detail, filters, variant tracks, crafted stat chips, enhancement groups/)
  assert.match(source, /No backend API contract changes/)
  assert.match(source, /No page-private 16-slot grid, slot card, icon socket, candidate row, variant chip, crafted stat chip, enhancement group/)
  assert.match(source, /No weakening SimC-ready slot validation, apply-candidate trust gates, crafted stat gates, variant gates, enhancement caps/)
  assert.match(source, /Existing `requestWebsimGear\(\)` payload/)
  assert.match(source, /Existing `requestWebsimGearStats\(\)` payload/)
  assert.match(source, /`slot_grid_ready`: show 16-slot board or the canonical slot set returned by the payload with stable card dimensions/)
  assert.match(source, /`enhancement_sheet_ready`: show socket, enchant and embellishment groups from backend readable display evidence/)
  assert.match(source, /`stat_snapshot_verified`: show verified attribute metadata and checkedAt\/source without presenting it as performance score/)
  assert.match(source, /No DPS, damage, ranking, percentile, tier, S\/A grade, comprehensive score, BiS, popularity or upgrade priority/)
  assert.match(source, /`gear_slot_grid_ready`/)
  assert.match(source, /`gear_enhancement_over_cap`/)
  assert.match(source, /`gear_simc_handoff`/)
  assert.match(source, /GearLoadoutBoard` and `GearConfigSheet` now have source-level owner skeletons, fixture matrix and browser\/component precheck evidence/)
  assert.match(source, /failures=0`, `warnings=0`, 3 viewport screenshots, 10 component crops/)
  assert.match(source, /This draft is ready for target-lock review and now has `GearLoadoutBoard` \/ `GearConfigSheet` owner skeleton plus component precheck evidence\. It does not activate implementation\./)

  assert.equal(manifest.status, 'implementation_permit_draft')
  assert.equal(manifest.surface, 'gear_detail')
  assert.deepEqual(manifest.routes, ['/pages/builds/detail?query=gear'])
  assert.ok(appConfig.pages.includes(manifest.routes[0].replace(/^\//, '').split('?')[0]))
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.implementationPermit, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.sourcePermitDraft, gearDetailPermitDraftPath)
  assert.equal(manifest.sourcePermitCoverageMatrix, permitCoverageMatrixPath)
  assert.equal(manifest.sourceGearDetailOwnerSkeletonPrecheck, gearDetailOwnerSkeletonPrecheckPath)
  assert.equal(manifest.gearDetailOwnerSkeletonArtifact, gearDetailOwnerSkeletonManifestPath)
  assert.equal(manifest.sourceGearDetailComponentPrecheck, gearDetailComponentPrecheckPath)
  assert.equal(manifest.gearDetailComponentPrecheckArtifact, gearDetailComponentPrecheckManifestPath)
  assert.deepEqual(manifest.requiredBeforeActivation, [
    'user_confirmed_or_modified_target_lock',
    'accepted_or_revised_asset_manifest',
    'GearLoadoutBoard_owner_skeleton_and_fixture_matrix_still_valid_after_target_lock',
    'GearConfigSheet_owner_skeleton_and_fixture_matrix_still_valid_after_target_lock',
    'clean_gear_detail_surface_component_precheck_rerun_before_activation',
    'explicit_conversion_from_draft_to_active_permit'
  ])
  assert.deepEqual(manifest.ownerComponents, [
    'PageFrame',
    'WowPanel',
    'GearLoadoutBoard',
    'GearConfigSheet',
    'GameObjectIcon',
    'StatusVisual',
    'ActionButton',
    'EvidenceLedger',
    'ModuleCard',
    'MaterialImage'
  ])
  assert.ok(manifest.currentSourceFindings.some((item) => item.includes('gear-panel gear-request-alert gear-attribute-panel gear-slot-grid gear-slot-card')))
  assert.ok(manifest.currentSourceFindings.some((item) => item.includes('requestWebsimGear and requestWebsimGearStats')))
  assert.ok(manifest.currentSourceFindings.some((item) => item.includes('source-reference gear missing/untrusted slots heavy candidate cache')))
  assert.ok(manifest.currentSourceFindings.some((item) => item.includes('blocks saving or applying when required gear slots are missing')))
  assert.ok(manifest.proposedAllowedFilesAfterActivation.includes('components/gear-loadout-board/*'))
  assert.ok(manifest.proposedAllowedFilesAfterActivation.includes('components/gear-config-sheet/*'))
  assert.ok(manifest.forbiddenFilesAndActions.includes('backend API contract changes'))
  assert.ok(manifest.forbiddenFilesAndActions.includes('fake DPS damage preview BiS label comprehensive score S/A grade percentile ranking popularity official badge or upgrade-priority claim'))
  assert.ok(manifest.forbiddenFilesAndActions.includes('weakening SimC-ready slot validation apply-candidate trust gates crafted stat gates variant gates enhancement caps source-reference blockers save-readiness rules stat snapshot request gates or community import safety'))
  assert.ok(manifest.dataBoundary.allowed.includes('existing requestWebsimGear payload for slots slot groups equipped set replacement candidates community templates community sync state readiness catalog status checkedAt blockers item database revision and variant revision'))
  assert.ok(manifest.dataBoundary.allowed.includes('existing requestWebsimGearStats payload for verified SimC stat snapshot only'))
  assert.equal(manifest.dataBoundary.requiredUiMapping.slot_grid_ready, 'show 16-slot board or canonical slot set returned by payload with stable card dimensions')
  assert.equal(manifest.dataBoundary.requiredUiMapping.enhancement_sheet_ready, 'show socket enchant and embellishment groups from backend readable display evidence')
  assert.equal(manifest.dataBoundary.requiredUiMapping.stat_snapshot_verified, 'show verified attribute metadata and checkedAt/source without presenting it as performance score')
  assert.ok(manifest.dataBoundary.forbiddenClaims.includes('DPS damage ranking percentile tier S/A grade comprehensive score BiS popularity or upgrade priority'))
  assert.ok(manifest.assetBoundary.forbidden.includes('imagegen item/source/dungeon/raid/class/spec/hero icons'))
  assert.deepEqual(manifest.routeSmokeScenes, [
    'gear_detail_from_builds',
    'gear_detail_from_workbench',
    'gear_initial_loading',
    'gear_payload_fallback',
    'gear_catalog_blocked_or_partial',
    'gear_slot_grid_ready',
    'gear_slot_missing',
    'gear_slot_source_reference',
    'gear_slot_sheet_empty',
    'gear_candidate_detail',
    'gear_variant_required',
    'gear_crafted_stat_required',
    'gear_candidate_apply_blocked',
    'gear_candidate_apply_ready',
    'gear_enhancement_sheet',
    'gear_enhancement_over_cap',
    'gear_enhancement_stale_pruned',
    'gear_community_missing_credentials',
    'gear_community_source_reference_blocked',
    'gear_personal_template_import',
    'gear_community_template_import',
    'gear_stat_snapshot_loading',
    'gear_stat_snapshot_verified',
    'gear_stat_snapshot_blocked',
    'gear_save_blocked',
    'gear_save_ready',
    'gear_template_saved',
    'gear_simc_handoff'
  ])
  assert.ok(manifest.requiredRuntimeArtifactsAfterImplementation.includes('real WeChat mini-program screenshots after captureSafe=true'))
  assert.ok(manifest.stopConditions.includes('GearLoadoutBoard / GearConfigSheet owner skeleton or clean component precheck is missing stale or contradicted before page integration'))
  assert.ok(manifest.forbiddenPromotion.includes('active_implementation_permit'))
  assert.ok(manifest.forbiddenPromotion.includes('runtime_verified'))
  assert.ok(manifest.nextRequiredEvidence.includes('rerun GearLoadoutBoard and GearConfigSheet surface component precheck before activation'))
  assert.ok(manifest.nextRequiredEvidence.includes('convert this draft into an active gear_detail implementation permit'))

  assert.match(readme, /Status: `implementation_permit_draft`/)
  assert.match(readme, /not target locked, not an active implementation permit, and not runtime verified/)
  assert.match(readme, /`GearLoadoutBoard` owner skeleton and fixture matrix still valid after target lock/)
  assert.match(readme, /`GearConfigSheet` owner skeleton and fixture matrix still valid after target lock/)
  assert.match(readme, /failures=0`, `warnings=0`, 3 viewport screenshots, 10 component crops/)
  assert.match(readme, /existing 16-slot readiness, real item candidates, variant selection, crafted stat selection, socket\/enchant\/embellishment gates/)
})

test('tasks owner skeleton source precheck separates queue and result report UI from page geometry', () => {
  const source = read(tasksOwnerSkeletonPrecheckPath)
  const manifest = readJson(tasksOwnerSkeletonManifestPath)
  const fixtures = readJson(tasksOwnerSkeletonFixturesPath)
  const readme = read(tasksOwnerSkeletonReadmePath)

  assert.match(source, /^Status: `owner_skeleton_source_precheck`$/m)
  assert.match(source, /TaskQueueBoard/)
  assert.match(source, /TaskResultReport/)
  assert.match(source, /task list hero, status rail, task cards/)
  assert.match(source, /detail hero, final result gate, context rows/)
  assert.match(source, /List cards do not show preview strong metrics/)
  assert.match(source, /Raw command\/profile\/diagnostic text is localized before visible output/)
  assert.match(source, /not:\n\n- `target_locked`/)
  assert.match(source, /component precheck with crops/)

  assert.equal(manifest.status, 'owner_skeleton_source_precheck')
  assert.equal(manifest.surface, 'tasks')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activePermit, false)
  assert.equal(manifest.componentPrecheck, false)
  assert.equal(manifest.browserPrecheck, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.pageIntegration, false)
  assert.equal(manifest.sourceOwnerContract, surfaceOwnerContractsPath)
  assert.equal(manifest.sourcePermitDraft, tasksPermitDraftPath)
  assert.equal(manifest.sourceFixtures, tasksOwnerSkeletonFixturesPath)
  assert.equal(manifest.sourceOwnerSkeletonPrecheckDoc, tasksOwnerSkeletonPrecheckPath)
  assert.deepEqual(manifest.owners.map((owner) => owner.id), ['TaskQueueBoard', 'TaskResultReport'])
  assert.ok(manifest.owners[0].events.includes('tasktap'))
  assert.ok(manifest.owners[0].events.includes('gosimc'))
  assert.ok(manifest.owners[0].events.includes('goworkbench'))
  assert.ok(manifest.owners[1].events.includes('askchickenbro'))
  assert.ok(manifest.fixtureMatrix.TaskQueueBoard.includes('tasks_list_ready'))
  assert.ok(manifest.fixtureMatrix.TaskQueueBoard.includes('tasks_empty_to_workbench'))
  assert.ok(manifest.fixtureMatrix.TaskResultReport.includes('task_detail_preview_no_dps'))
  assert.ok(manifest.fixtureMatrix.TaskResultReport.includes('task_detail_failed_raw_diagnostic'))
  assert.ok(manifest.checks.find((check) => check.id === 'owner_components_exist' && check.status === 'pass'))
  assert.ok(manifest.checks.find((check) => check.id === 'page_integration_not_performed' && check.status === 'pass'))
  assert.ok(manifest.forbiddenPromotion.includes('runtime_verified'))
  assert.ok(manifest.nextRequiredEvidence.includes('run TaskQueueBoard and TaskResultReport component precheck with crops'))

  assert.equal(fixtures.status, 'owner_skeleton_source_precheck')
  assert.equal(fixtures.surface, 'tasks')
  assert.equal(fixtures.pageIntegration, false)
  assert.equal(fixtures.devtoolsTouched, false)
  assert.ok(fixtures.taskQueueBoard.some((fixture) => fixture.fixtureId === 'tasks_list_ready'))
  assert.ok(fixtures.taskResultReport.some((fixture) => fixture.fixtureId === 'task_detail_failed_raw_diagnostic'))
  assert.ok(fixtures.requiredFixtures.TaskQueueBoard.includes('task_card_failed'))
  assert.ok(fixtures.requiredFixtures.TaskResultReport.includes('task_detail_combat_buffs'))

  for (const owner of ['task-queue-board', 'task-result-report']) {
    for (const ext of ['json', 'js', 'wxml', 'wxss']) {
      assert.ok(fs.existsSync(`components/${owner}/${owner}.${ext}`), `${owner}.${ext} should exist`)
    }
  }
  assert.match(readme, /`TaskQueueBoard`/)
  assert.match(readme, /`TaskResultReport`/)
  assert.match(readme, /Runtime verified: `false`/)
})

test('tasks component precheck records browser crops without page or runtime promotion', () => {
  const source = read(tasksComponentPrecheckPath)
  const manifest = readJson(tasksComponentPrecheckManifestPath)
  const readme = read(tasksComponentPrecheckReadmePath)

  assert.match(source, /^Status: `surface_component_precheck`$/m)
  assert.match(source, /TaskQueueBoard/)
  assert.match(source, /TaskResultReport/)
  assert.match(source, /Failures: `0`/)
  assert.match(source, /Warnings: `0`/)
  assert.match(source, /Crops: `10`/)
  assert.match(source, /`pages\/simulator\/tasks\.\*` and `pages\/simulator\/task-detail\.\*` remain untouched/)

  assert.equal(manifest.status, 'surface_component_precheck')
  assert.equal(manifest.surface, 'tasks')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activePermit, false)
  assert.equal(manifest.componentPrecheck, true)
  assert.equal(manifest.browserPrecheck, true)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.pageIntegration, false)
  assert.equal(manifest.browserEngine, 'chrome_headless_cdp')
  assert.equal(manifest.sourceComponentPrecheckDoc, tasksComponentPrecheckPath)
  assert.equal(manifest.sourceOwnerSkeletonPrecheck, tasksOwnerSkeletonPrecheckPath)
  assert.equal(manifest.sourceOwnerSkeletonArtifact, tasksOwnerSkeletonManifestPath)
  assert.equal(manifest.sourceFixtures, tasksOwnerSkeletonFixturesPath)
  assert.equal(manifest.failures.length, 0)
  assert.equal(manifest.warnings.length, 0)
  assert.equal(manifest.crops.length, 10)
  assert.equal(manifest.viewportScreenshots.length, 3)
  assert.ok(manifest.ownerReports.every((report) => report.status === 'pass'))
  assert.ok(manifest.measurements.every((measurement) => measurement.document.horizontalOverflow === 0))
  assert.ok(manifest.measurements.every((measurement) => measurement.forbiddenVisibleText.length === 0))
  assert.ok(manifest.checks.find((check) => check.id === 'standard_surface_crops_written' && check.status === 'pass' && check.count === 10))
  assert.ok(manifest.checks.find((check) => check.id === 'devtools_not_touched' && check.status === 'pass'))
  assert.ok(manifest.checks.find((check) => check.id === 'page_integration_not_performed' && check.status === 'pass'))
  for (const cropId of [
    'tasks-queue-ready-surface',
    'tasks-queue-status-rail',
    'tasks-queue-task-card',
    'tasks-queue-empty-state',
    'tasks-queue-action-rail',
    'task-result-final-surface',
    'task-result-metric-grid',
    'task-result-context-section',
    'task-result-failure-section',
    'task-result-action-rail'
  ]) {
    const crop = manifest.crops.find((item) => item.id === cropId)
    assert.ok(crop, `${cropId} crop should exist`)
    assert.ok(fs.existsSync(crop.path), `${crop.path} should exist`)
  }
  for (const screenshot of manifest.viewportScreenshots) {
    assert.ok(fs.existsSync(screenshot), `${screenshot} should exist`)
    const size = readPngSize(screenshot)
    assert.ok(size.width >= 360)
    assert.ok(size.height >= 780)
  }
  assert.ok(fs.existsSync(manifest.contactSheet))
  assert.ok(manifest.forbiddenPromotion.includes('final_accepted'))
  assert.ok(manifest.nextRequiredEvidence.includes('convert tasks draft into active implementation permit before page integration'))

  assert.match(readme, /Status: `surface_component_precheck`/)
  assert.match(readme, /Failures: `0`/)
  assert.match(readme, /Warnings: `0`/)
  assert.match(readme, /tasks-queue-ready-surface/)
  assert.match(readme, /task-result-failure-section/)
  assert.match(readme, /cannot prove `target_locked`, `active_implementation_permit`, `runtime_verified` or `final_accepted`/)
})

test('tasks implementation permit draft protects task history and result gates and is not active', () => {
  const source = read(tasksPermitDraftPath)
  const manifest = readJson(tasksPermitDraftManifestPath)
  const readme = read(tasksPermitDraftReadmePath)
  const appConfig = readJson('app.json')

  assert.match(source, /^Status: `implementation_permit_draft`$/m)
  assert.match(source, /rebuilding the SimC task list and task detail pages/)
  assert.match(source, /not `target_locked`, not an active implementation permit/)
  assert.match(source, /Surface: `tasks`/)
  assert.match(source, /`\/pages\/simulator\/tasks`/)
  assert.match(source, /`\/pages\/simulator\/task-detail`/)
  assert.match(source, /next missing permit in the current implementation permit coverage matrix after the gear detail draft/)
  assert.match(source, /guest task reads, list-to-detail navigation, loading, empty, queued\/running\/completed\/failed states/)
  assert.match(source, /`task-shell-bg`, `task-command`, `task-command-count`, `task-list-section`, `task-list-card`, `task-status`/)
  assert.match(source, /`requestSimulatorTasks\(\)`/)
  assert.match(source, /`requestSimulatorTaskDetail\(\)`/)
  assert.match(source, /hides generated preview DPS/)
  assert.match(source, /raw SimC crash diagnostics/)
  assert.match(source, /guest task list\/detail reads over insecure development HTTP without bearer token/)
  assert.match(source, /Source-level `TaskQueueBoard` owner skeleton and fixture matrix/)
  assert.match(source, /Source-level `TaskResultReport` owner skeleton and fixture matrix/)
  assert.match(source, /Clean production\/browser component precheck for `TaskQueueBoard` and `TaskResultReport`/)
  assert.match(source, /status `surface_component_precheck`, failures `0`, warnings `0`, crops `10`/)
  assert.match(source, /Surface-specific owner for list hero, status rail, task cards, status chips, tags, terminal time/)
  assert.match(source, /Surface-specific owner for detail hero, final result metric, run context, stat rows, combat buffs/)
  assert.match(source, /No backend API contract changes/)
  assert.match(source, /No page-private task card, task status, tag chip, queue rail, empty step, result strip, metric cell, combat buff row/)
  assert.match(source, /No preview\/confirm-only\/generated profile DPS display/)
  assert.match(source, /No raw SimC command, raw profile, traceback, `sim_signal_handler`, segmentation fault text/)
  assert.match(source, /Existing `requestSimulatorTasks\(\)` payload/)
  assert.match(source, /Existing `requestSimulatorTaskDetail\(taskId\)` payload/)
  assert.match(source, /`task_detail_preview_no_dps`: show generated\/preview result as not executed and suppress preview DPS/)
  assert.match(source, /`task_detail_final_result`: show final SimC metric only when the result actually ran and is not preview\/generated/)
  assert.match(source, /`task_detail_failed_raw_diagnostic`: localize raw SimC diagnostics and hide raw command\/profile strings/)
  assert.match(source, /No DPS, damage, ranking, percentile, tier, S\/A grade, comprehensive score or upgrade priority unless it is a final, non-preview SimC task result/)
  assert.match(source, /`tasks_list_ready`/)
  assert.match(source, /`task_detail_combat_buffs`/)
  assert.match(source, /`tasks_empty_to_workbench`/)
  assert.match(source, /This draft now has `TaskQueueBoard` \/ `TaskResultReport` owner skeleton evidence and a clean surface component precheck/)
  assert.match(source, /it remains blocked from page integration until target lock is confirmed/)

  assert.equal(manifest.status, 'implementation_permit_draft')
  assert.equal(manifest.surface, 'tasks')
  assert.deepEqual(manifest.routes, ['/pages/simulator/tasks', '/pages/simulator/task-detail'])
  for (const route of manifest.routes) {
    assert.ok(appConfig.pages.includes(route.replace(/^\//, '').split('?')[0]), `${route} should be registered`)
  }
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.implementationPermit, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.sourcePermitDraft, tasksPermitDraftPath)
  assert.equal(manifest.sourcePermitCoverageMatrix, permitCoverageMatrixPath)
  assert.equal(manifest.sourceTasksOwnerSkeletonPrecheck, tasksOwnerSkeletonPrecheckPath)
  assert.equal(manifest.tasksOwnerSkeletonArtifact, tasksOwnerSkeletonManifestPath)
  assert.equal(manifest.sourceTasksComponentPrecheck, tasksComponentPrecheckPath)
  assert.equal(manifest.tasksComponentPrecheckArtifact, tasksComponentPrecheckManifestPath)
  assert.deepEqual(manifest.requiredBeforeActivation, [
    'user_confirmed_or_modified_target_lock',
    'accepted_or_revised_asset_manifest',
    'TaskQueueBoard_owner_skeleton_and_fixture_matrix',
    'TaskResultReport_owner_skeleton_and_fixture_matrix',
    'clean_production_component_precheck',
    'clean_browser_component_precheck',
    'explicit_conversion_from_draft_to_active_permit'
  ])
  assert.deepEqual(manifest.ownerComponents, [
    'PageFrame',
    'WowPanel',
    'TaskQueueBoard',
    'TaskResultReport',
    'StatusVisual',
    'ActionButton',
    'EvidenceLedger',
    'ModuleCard',
    'MaterialImage',
    'GameObjectIcon'
  ])
  assert.ok(manifest.currentSourceFindings.some((item) => item.includes('task-shell-bg task-command task-command-count task-list-section task-list-card')))
  assert.ok(manifest.currentSourceFindings.some((item) => item.includes('requestSimulatorTasks')))
  assert.ok(manifest.currentSourceFindings.some((item) => item.includes('requestSimulatorTaskDetail')))
  assert.ok(manifest.currentSourceFindings.some((item) => item.includes('guest task list/detail reads')))
  assert.ok(manifest.proposedAllowedFilesAfterActivation.includes('components/task-queue-board/*'))
  assert.ok(manifest.proposedAllowedFilesAfterActivation.includes('components/task-result-report/*'))
  assert.ok(manifest.forbiddenFilesAndActions.includes('backend API contract changes'))
  assert.ok(manifest.forbiddenFilesAndActions.includes('preview confirm-only or generated profile DPS display'))
  assert.ok(manifest.forbiddenFilesAndActions.includes('weakening guest task query boundary list-to-detail route preview-DPS suppression localized failure mapping final-result gate active task status semantics or task detail error handling'))
  assert.ok(manifest.dataBoundary.allowed.includes('existing requestSimulatorTasks payload and simcReportSummary list read model'))
  assert.ok(manifest.dataBoundary.allowed.includes('existing requestSimulatorTaskDetail taskId payload and analysis.simcReport detail read model'))
  assert.equal(manifest.dataBoundary.requiredUiMapping.task_detail_preview_no_dps, 'show generated/preview result as not executed and suppress preview DPS')
  assert.equal(manifest.dataBoundary.requiredUiMapping.task_detail_final_result, 'show final SimC metric only when result actually ran and is not preview/generated')
  assert.equal(manifest.dataBoundary.requiredUiMapping.task_detail_failed_raw_diagnostic, 'localize raw SimC diagnostics and hide raw command/profile strings')
  assert.ok(manifest.dataBoundary.forbiddenClaims.includes('generated preview DPS confirm-only DPS or generated-profile DPS'))
  assert.ok(manifest.assetBoundary.forbidden.includes('imagegen task ids DPS values rankings source names status labels or business conclusions'))
  assert.deepEqual(manifest.routeSmokeScenes, [
    'tasks_from_simc',
    'tasks_from_workbench',
    'tasks_loading',
    'tasks_empty',
    'tasks_fallback_error',
    'tasks_list_ready',
    'task_card_completed',
    'task_card_running',
    'task_card_failed',
    'task_open_detail',
    'task_detail_loading',
    'task_detail_missing_id',
    'task_detail_not_found',
    'task_detail_preview_no_dps',
    'task_detail_final_result',
    'task_detail_failed_timeout',
    'task_detail_failed_raw_diagnostic',
    'task_detail_context',
    'task_detail_combat_buffs',
    'task_detail_guest_read',
    'tasks_empty_to_simc',
    'tasks_empty_to_workbench'
  ])
  assert.ok(manifest.requiredRuntimeArtifactsAfterImplementation.includes('real WeChat mini-program screenshots after captureSafe=true'))
  assert.ok(manifest.stopConditions.includes('TaskQueueBoard or equivalent list owner is not defined before page integration'))
  assert.ok(manifest.stopConditions.includes('TaskResultReport or equivalent detail owner is not defined before page integration'))
  assert.ok(manifest.stopConditions.includes('simulator task tests fail or visual changes require weakening guest task read list-to-detail navigation preview-DPS suppression final-result gate localized failure mapping or raw diagnostic hiding'))
  assert.ok(manifest.forbiddenPromotion.includes('active_implementation_permit'))
  assert.ok(manifest.forbiddenPromotion.includes('runtime_verified'))
  assert.ok(manifest.nextRequiredEvidence.includes('keep TaskQueueBoard and TaskResultReport component precheck green before active permit conversion'))

  assert.match(readme, /Status: `implementation_permit_draft`/)
  assert.match(readme, /not target locked, not an active implementation permit, and not runtime verified/)
  assert.match(readme, /`TaskQueueBoard` owner skeleton and fixture matrix, currently present/)
  assert.match(readme, /`TaskResultReport` owner skeleton and fixture matrix, currently present/)
  assert.match(readme, /clean production\/browser component precheck, currently present with `0` failures, `0` warnings and `10` crops/)
  assert.match(readme, /existing task list\/detail routes, guest task reads, status localization, empty-state navigation, preview-DPS suppression/)
})

test('profile templates owner skeleton source precheck separates identity and library UI from page geometry', () => {
  const source = read(profileTemplatesOwnerSkeletonPrecheckPath)
  const manifest = readJson(profileTemplatesOwnerSkeletonManifestPath)
  const fixtures = readJson(profileTemplatesOwnerSkeletonFixturesPath)
  const readme = read(profileTemplatesOwnerSkeletonReadmePath)

  assert.match(source, /^Status: `owner_skeleton_source_precheck`$/m)
  assert.match(source, /profile_templates/)
  assert.match(source, /ProfileIdentityPanel/)
  assert.match(source, /TemplateLibraryBoard/)
  assert.match(source, /avatar socket, nickname draft input, guest\/formal status/)
  assert.match(source, /talent\/gear modules, recent template cards, meta chips/)
  assert.match(source, /Template cards do not expose `rawString`, `simcLines`/)
  assert.match(source, /Deletion remains a confirmation flow/)
  assert.match(source, /not:\n\n- `target_locked`/)

  assert.equal(manifest.status, 'owner_skeleton_source_precheck')
  assert.equal(manifest.surface, 'profile_templates')
  assert.deepEqual(manifest.routes, ['/pages/profile/profile'])
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activePermit, false)
  assert.equal(manifest.componentPrecheck, false)
  assert.equal(manifest.browserPrecheck, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.pageIntegration, false)
  assert.equal(manifest.sourceOwnerContract, surfaceOwnerContractsPath)
  assert.equal(manifest.sourcePermitDraft, profileTemplatesPermitDraftPath)
  assert.equal(manifest.sourceFixtures, profileTemplatesOwnerSkeletonFixturesPath)
  assert.equal(manifest.sourceOwnerSkeletonPrecheckDoc, profileTemplatesOwnerSkeletonPrecheckPath)
  assert.deepEqual(manifest.owners.map((owner) => owner.id), ['ProfileIdentityPanel', 'TemplateLibraryBoard'])
  assert.ok(manifest.owners[0].events.includes('chooseavatar'))
  assert.ok(manifest.owners[0].events.includes('updatenickname'))
  assert.ok(manifest.owners[0].events.includes('saveprofile'))
  assert.ok(manifest.owners[1].events.includes('confirmdelete'))
  assert.ok(manifest.owners[1].events.includes('deletetemplate'))
  assert.ok(manifest.fixtureMatrix.ProfileIdentityPanel.includes('profile_guest_local_only'))
  assert.ok(manifest.fixtureMatrix.ProfileIdentityPanel.includes('profile_remote_sync_fallback'))
  assert.ok(manifest.fixtureMatrix.TemplateLibraryBoard.includes('template_delete_confirm'))
  assert.ok(manifest.fixtureMatrix.TemplateLibraryBoard.includes('template_delete_remote_fallback'))
  assert.ok(manifest.fixtureMatrix.TemplateLibraryBoard.includes('template_entry_gear'))
  assert.ok(manifest.checks.find((check) => check.id === 'owner_components_exist' && check.status === 'pass'))
  assert.ok(manifest.checks.find((check) => check.id === 'page_integration_not_performed' && check.status === 'pass'))
  assert.ok(manifest.forbiddenPromotion.includes('runtime_verified'))
  assert.ok(manifest.nextRequiredEvidence.includes('run ProfileIdentityPanel and TemplateLibraryBoard component precheck with crops'))

  assert.ok(fixtures.profileIdentityPanel.some((fixture) => fixture.fixtureId === 'profile_long_nickname'))
  assert.ok(fixtures.profileIdentityPanel.some((fixture) => fixture.fixtureId === 'profile_save_failed'))
  assert.ok(fixtures.templateLibraryBoard.some((fixture) => fixture.fixtureId === 'template_missing_meta'))
  assert.ok(fixtures.templateLibraryBoard.some((fixture) => fixture.fixtureId === 'template_delete_cancel'))
  assert.ok(fixtures.templateLibraryBoard.some((fixture) => fixture.fixtureId === 'template_entry_talent'))
  assert.doesNotMatch(JSON.stringify(fixtures), /raw profile|raw SimC|token|openid|unionid|云端验证|官方推荐|DPS|综合评分|提升优先级/i)

  for (const owner of ['profile-identity-panel', 'template-library-board']) {
    for (const ext of ['json', 'js', 'wxml', 'wxss']) {
      assert.ok(fs.existsSync(`components/${owner}/${owner}.${ext}`), `${owner}.${ext} should exist`)
    }
  }
  assert.match(readme, /ProfileIdentityPanel/)
  assert.match(readme, /TemplateLibraryBoard/)
  assert.match(readme, /Page integration: `false`/)
})

test('profile templates component precheck records browser crops without page or runtime promotion', () => {
  const source = read(profileTemplatesComponentPrecheckPath)
  const manifest = readJson(profileTemplatesComponentPrecheckManifestPath)
  const readme = read(profileTemplatesComponentPrecheckReadmePath)

  assert.match(source, /^Status: `surface_component_precheck`$/m)
  assert.match(source, /ProfileIdentityPanel/)
  assert.match(source, /TemplateLibraryBoard/)
  assert.match(source, /Failures: `0`/)
  assert.match(source, /Warnings: `0`/)
  assert.match(source, /Crops: `10`/)
  assert.match(source, /`pages\/profile\/profile\.\*` remains untouched/)

  assert.equal(manifest.status, 'surface_component_precheck')
  assert.equal(manifest.surface, 'profile_templates')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activePermit, false)
  assert.equal(manifest.componentPrecheck, true)
  assert.equal(manifest.browserPrecheck, true)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.pageIntegration, false)
  assert.equal(manifest.browserEngine, 'chrome_headless_cdp')
  assert.equal(manifest.sourceComponentPrecheckDoc, profileTemplatesComponentPrecheckPath)
  assert.equal(manifest.sourceOwnerSkeletonPrecheck, profileTemplatesOwnerSkeletonPrecheckPath)
  assert.equal(manifest.sourceOwnerSkeletonArtifact, profileTemplatesOwnerSkeletonManifestPath)
  assert.equal(manifest.sourceFixtures, profileTemplatesOwnerSkeletonFixturesPath)
  assert.equal(manifest.failures.length, 0)
  assert.equal(manifest.warnings.length, 0)
  assert.equal(manifest.crops.length, 10)
  assert.equal(manifest.viewportScreenshots.length, 3)
  assert.ok(manifest.ownerReports.every((report) => report.status === 'pass'))
  assert.ok(manifest.measurements.every((measurement) => measurement.document.horizontalOverflow === 0))
  assert.ok(manifest.measurements.every((measurement) => measurement.forbiddenVisibleText.length === 0))
  assert.ok(manifest.checks.find((check) => check.id === 'standard_surface_crops_written' && check.status === 'pass' && check.count === 10))
  assert.ok(manifest.checks.find((check) => check.id === 'devtools_not_touched' && check.status === 'pass'))
  assert.ok(manifest.checks.find((check) => check.id === 'page_integration_not_performed' && check.status === 'pass'))
  for (const cropId of [
    'profile-identity-local-surface',
    'profile-identity-avatar-nickname',
    'profile-identity-metrics',
    'profile-identity-remote-fallback',
    'template-library-loaded-surface',
    'template-library-module-row',
    'template-library-template-card',
    'template-library-empty-state',
    'template-library-delete-confirm',
    'template-library-remote-fallback'
  ]) {
    const crop = manifest.crops.find((item) => item.id === cropId)
    assert.ok(crop, `${cropId} crop should exist`)
    assert.ok(fs.existsSync(crop.path), `${crop.path} should exist`)
  }
  for (const screenshot of manifest.viewportScreenshots) {
    assert.ok(fs.existsSync(screenshot), `${screenshot} should exist`)
    const size = readPngSize(screenshot)
    assert.ok(size.width >= 360)
    assert.ok(size.height >= 780)
  }
  assert.ok(fs.existsSync(manifest.contactSheet))
  assert.ok(manifest.forbiddenPromotion.includes('final_accepted'))
  assert.ok(manifest.nextRequiredEvidence.includes('convert profile_templates draft into active implementation permit before page integration'))

  assert.match(readme, /Status: `surface_component_precheck`/)
  assert.match(readme, /Failures: `0`/)
  assert.match(readme, /Warnings: `0`/)
  assert.match(readme, /profile-identity-avatar-nickname/)
  assert.match(readme, /template-library-delete-confirm/)
  assert.match(readme, /cannot prove `target_locked`, `active_implementation_permit`, `runtime_verified` or `final_accepted`/)
})

test('profile templates implementation permit draft protects user assets and is not active', () => {
  const source = read(profileTemplatesPermitDraftPath)
  const manifest = readJson(profileTemplatesPermitDraftManifestPath)
  const readme = read(profileTemplatesPermitDraftReadmePath)
  const appConfig = readJson('app.json')

  assert.match(source, /^Status: `implementation_permit_draft`$/m)
  assert.match(source, /Surface: `profile_templates`/)
  assert.match(source, /Primary route: `\/pages\/profile\/profile`/)
  assert.match(source, /not `target_locked`, not an active implementation permit/)
  assert.match(source, /does not authorize page WXML\/WXSS edits/)
  assert.match(source, /next missing permit after `tasks`/)
  assert.match(source, /WeChat avatar and nickname draft state/)
  assert.match(source, /Local-first profile persistence/)
  assert.match(source, /Remote template fetch, merge, sync and delete fallback/)
  assert.match(source, /Guest\/formal boundary and authenticated request safety/)
  assert.match(source, /Destructive template deletion confirmation/)
  assert.match(source, /`pages\/profile\/profile\.wxml` directly composes `profile-shell`/)
  assert.match(source, /`pages\/profile\/profile\.wxss` owns shell, cockpit, avatar, metric, template module/)
  assert.match(source, /`pages\/profile\/profile\.js` imports `currentProfile` \/ `saveProfileDraft`/)
  assert.match(source, /`hydrateTemplates\(\)` renders local `buildTemplateSummary\(\)` first/)
  assert.match(source, /`saveProfileDraft\(\)`, which persists local profile state before attempting remote auth\/profile save/)
  assert.match(source, /`deleteTemplate\(\)` requires `wx\.showModal` confirmation/)
  assert.match(source, /`wow_build_templates_v1`/)
  assert.match(source, /insecure HTTP bearer blocking/)
  assert.match(source, /ProfileIdentityPanel/)
  assert.match(source, /TemplateLibraryBoard/)
  assert.match(source, /Do not modify backend API contracts or database schema/)
  assert.match(source, /Do not edit `app\.json`, tabBar, `project\.config\.json`, appid, DevTools settings or route registration/)
  assert.match(source, /Do not close, restart, clear cache, switch project, switch appid/)
  assert.match(source, /Do not weaken local-first save, remote merge, insecure HTTP bearer blocking, guest\/formal boundary/)
  assert.match(source, /Forbidden UI exposure/)
  assert.match(source, /Auth token, refresh token, raw openid, unionid, internal user id or database row id/)
  assert.match(source, /Full `rawString`, full `simcLines`, raw imported talent code or raw gear profile/)
  assert.match(source, /Remote fallback must be visible as local-only or sync-limited state/)
  assert.match(source, /Deleting a template is destructive and must keep a confirmation path/)
  assert.match(source, /Template counts must come from `buildTemplateSummary\(\)`/)
  assert.match(source, /No DPS, ranking, S\/A grade, "提升优先级", "云端验证" or "官方推荐"/)
  assert.match(source, /profile_guest_local_only/)
  assert.match(source, /profile_formal_synced/)
  assert.match(source, /template_delete_remote_fallback/)
  assert.match(source, /template_entry_talent/)
  assert.match(source, /profile_delete_cancel/)
  assert.match(source, /Scorecard that fails on fake sync, raw token\/openid leakage, raw template leakage/)
  assert.match(source, /DevTools action ledger proving low-disturbance capture/)
  assert.match(source, /Owner contracts for `ProfileIdentityPanel` and `TemplateLibraryBoard`, now supported by source-level owner skeleton and component precheck evidence/)
  assert.match(source, /Current supporting evidence:/)
  assert.match(source, /Profile Templates Owner Skeleton Source Precheck/)
  assert.match(source, /Profile Templates Component Precheck/)
  assert.match(source, /This draft plus the current owner skeleton and browser\/component precheck prove only `implementation_permit_draft` and `surface_component_precheck` evidence for `profile_templates`/)

  assert.equal(manifest.status, 'implementation_permit_draft')
  assert.equal(manifest.surface, 'profile_templates')
  assert.deepEqual(manifest.routes, ['/pages/profile/profile'])
  assert.ok(appConfig.pages.includes('pages/profile/profile'))
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activePermit, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.sourcePermit, profileTemplatesPermitDraftPath)
  assert.equal(manifest.sourceCoverageMatrix, permitCoverageMatrixPath)
  assert.equal(manifest.sourceProfileTemplatesOwnerSkeletonPrecheck, profileTemplatesOwnerSkeletonPrecheckPath)
  assert.equal(manifest.profileTemplatesOwnerSkeletonArtifact, profileTemplatesOwnerSkeletonManifestPath)
  assert.equal(manifest.sourceProfileTemplatesComponentPrecheck, profileTemplatesComponentPrecheckPath)
  assert.equal(manifest.profileTemplatesComponentPrecheckArtifact, profileTemplatesComponentPrecheckManifestPath)
  assert.ok(manifest.sourceFilesInspected.includes('pages/profile/profile.wxml'))
  assert.ok(manifest.sourceFilesInspected.includes('pages/common/auth-client.js'))
  assert.ok(manifest.sourceFilesInspected.includes('pages/common/build-template-storage.js'))
  assert.deepEqual(manifest.requiredOwnerContracts, [
    'ProfileIdentityPanel',
    'TemplateLibraryBoard'
  ])
  assert.ok(manifest.foundationOwners.includes('PageFrame'))
  assert.ok(manifest.foundationOwners.includes('StatusVisual'))
  assert.ok(manifest.foundationOwners.includes('EvidenceLedger'))
  assert.ok(manifest.protectedBehaviors.includes('local-first profile draft save'))
  assert.ok(manifest.protectedBehaviors.includes('local template summary renders before remote fetch'))
  assert.ok(manifest.protectedBehaviors.includes('remote template merge without losing local templates'))
  assert.ok(manifest.protectedBehaviors.includes('insecure HTTP bearer blocking'))
  assert.ok(manifest.protectedBehaviors.includes('delete confirmation before destructive removal'))
  assert.ok(manifest.protectedBehaviors.includes('rawString preservation'))
  assert.ok(manifest.protectedBehaviors.includes('simcLines preservation'))
  assert.ok(manifest.forbiddenExposures.includes('auth token'))
  assert.ok(manifest.forbiddenExposures.includes('raw openid'))
  assert.ok(manifest.forbiddenExposures.includes('full rawString'))
  assert.ok(manifest.forbiddenExposures.includes('full simcLines'))
  assert.deepEqual(manifest.routeSmokeScenes, [
    'profile_tab_top',
    'profile_local_draft',
    'profile_formal_user',
    'profile_remote_sync_loading',
    'profile_remote_sync_fallback',
    'profile_template_empty',
    'profile_template_library_loaded',
    'profile_template_long_title',
    'profile_template_missing_meta',
    'profile_delete_confirm',
    'profile_delete_cancel',
    'profile_delete_success',
    'profile_delete_remote_fallback',
    'profile_template_entry_talent',
    'profile_template_entry_gear'
  ])
  for (const forbidden of ['target_locked', 'active_implementation_permit', 'runtime_verified', 'final_accepted']) {
    assert.ok(manifest.nonPromotionRule.includes(forbidden))
  }
  assert.ok(!manifest.nonPromotionRule.includes('component_precheck'))
  assert.ok(manifest.nextRequiredEvidence.includes('keep ProfileIdentityPanel and TemplateLibraryBoard component precheck green before active permit conversion'))
  assert.ok(manifest.nextRequiredEvidence.includes('accepted profile material asset manifest entries'))
  assert.ok(manifest.nextRequiredEvidence.includes('real mini-program screenshots'))
  assert.ok(manifest.nextRequiredEvidence.includes('DevTools action ledger'))

  assert.match(readme, /Status: `implementation_permit_draft`/)
  assert.match(readme, /`profile_templates` now has a dedicated implementation permit draft/)
  assert.match(readme, /`ProfileIdentityPanel` and `TemplateLibraryBoard` as required owners/)
  assert.match(readme, /owner skeletons, fixture matrix and component precheck/)
  assert.match(readme, /not an active implementation permit/)
  assert.match(readme, /No WeChat DevTools action was taken/)
})

test('simc implementation permit draft protects the real submit gate and is not active', () => {
  const source = read(simcPermitDraftPath)
  const manifest = readJson(simcPermitDraftManifestPath)
  const readme = read(simcPermitDraftReadmePath)

  assert.match(source, /^Status: `implementation_permit_draft`$/m)
  assert.match(source, /rebuilding the SimC template-submission page as the verified handoff cockpit/)
  assert.match(source, /not `target_locked`, not an active implementation permit/)
  assert.match(source, /Surface: `simc`/)
  assert.match(source, /`\/pages\/simulator\/simc`/)
  assert.match(source, /receives `ready_to_simulate` workbench handoff and owns the real submit gate/)
  assert.match(source, /`template-hero`, `template-selector`, `confirm-summary`, `blocked-panel`, `result-panel`, `preparation-panel`, fixed `action-bar` and `selector-sheet`/)
  assert.match(source, /`pages\/simulator\/simc\.wxss` owns page background, panel geometry, selector sheet geometry/)
  assert.match(source, /generated `ui-redesign\/20260701` material directly from page WXML/)
  assert.match(source, /`mode: 'simcraft_template'`, `confirmTemplateSimulation\(\)`/)
  assert.match(source, /`submitConfirmedTask\(\)` for final save\/submit/)
  assert.match(source, /active SimC template task limit of 2/)
  assert.match(source, /localizes common raw SimC diagnostics/)
  assert.match(source, /must not be treated as DPS, ranking, percentile, grade or upgrade-priority output/)
  assert.match(source, /Target Dependency/)
  assert.match(source, /`PageFrame`/)
  assert.match(source, /`WowPanel`/)
  assert.match(source, /`StatusVisual`/)
  assert.match(source, /`ActionButton`/)
  assert.match(source, /`EvidenceLedger`/)
  assert.match(source, /`ModuleCard`/)
  assert.match(source, /No backend API contract changes/)
  assert.match(source, /No page-private template selector, panel, status, action button, selector sheet, fixed action-bar, evidence row or material geometry/)
  assert.match(source, /No DPS preview before a real final SimC task result exists/)
  assert.match(source, /No raw SimC profile, raw command, raw traceback, raw log payload, token, openid, user id or database id/)
  assert.match(source, /Existing `fallbackBuildsHome\(\)` and `requestBuildsHome\(\)`/)
  assert.match(source, /Existing gear stat snapshot path through `requestWebsimGearStats\(\)`/)
  assert.match(source, /Existing simulator API client through `requestSimulatorAnalysis\(\)` and `requestSimulatorTasks\(\)`/)
  assert.match(source, /Existing `mode: 'simcraft_template'` request path/)
  assert.match(source, /`confirm_ready`: enable confirm only when class, talent template and gear template are selected/)
  assert.match(source, /`template_ready`: show that the combination passed validation/)
  assert.match(source, /`task_limit`: show active task limit language and keep submit disabled/)
  assert.match(source, /`simc_from_workbench`/)
  assert.match(source, /`simc_task_created`/)
  assert.match(source, /This draft is ready for target-lock review\. It does not activate implementation\./)

  assert.equal(manifest.status, 'implementation_permit_draft')
  assert.equal(manifest.surface, 'simc')
  assert.deepEqual(manifest.routes, ['/pages/simulator/simc'])
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.implementationPermit, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.sourcePermitDraft, simcPermitDraftPath)
  assert.equal(manifest.sourcePermitCoverageMatrix, permitCoverageMatrixPath)
  assert.deepEqual(manifest.requiredBeforeActivation, [
    'user_confirmed_or_modified_target_lock',
    'accepted_or_revised_asset_manifest',
    'clean_production_component_precheck',
    'clean_browser_component_precheck',
    'explicit_conversion_from_draft_to_active_permit'
  ])
  assert.deepEqual(manifest.ownerComponents, [
    'PageFrame',
    'WowPanel',
    'StatusVisual',
    'ActionButton',
    'EvidenceLedger',
    'ModuleCard',
    'GameObjectIcon',
    'MaterialImage'
  ])
  assert.ok(manifest.currentSourceFindings.some((item) => item.includes('template-hero template-selector confirm-summary')))
  assert.ok(manifest.currentSourceFindings.some((item) => item.includes('mode simcraft_template confirmTemplateSimulation')))
  assert.ok(manifest.currentSourceFindings.some((item) => item.includes('active SimC template task limit of 2')))
  assert.ok(manifest.currentSourceFindings.some((item) => item.includes('must not be treated as DPS ranking percentile grade or upgrade-priority output')))
  assert.ok(manifest.proposedAllowedFilesAfterActivation.includes('pages/simulator/simc.wxml'))
  assert.ok(manifest.proposedAllowedFilesAfterActivation.includes('components/evidence-ledger/*'))
  assert.ok(manifest.forbiddenFilesAndActions.includes('backend API contract changes'))
  assert.ok(manifest.forbiddenFilesAndActions.includes('DPS preview before a real final SimC task result exists'))
  assert.ok(manifest.forbiddenFilesAndActions.includes('raw SimC profile raw command raw traceback raw log payload token openid user id or database id'))
  assert.ok(manifest.dataBoundary.allowed.includes('existing mode simcraft_template request path'))
  assert.equal(manifest.dataBoundary.requiredUiMapping.confirm_ready, 'enable confirm only when class talent template and gear template are selected and stat validation is not blocked')
  assert.equal(manifest.dataBoundary.requiredUiMapping.template_ready, 'show combination passed validation and enable submit only if active task limit is not reached')
  assert.equal(manifest.dataBoundary.requiredUiMapping.task_limit, 'show active task limit language and keep submit disabled')
  assert.ok(manifest.dataBoundary.forbiddenClaims.includes('DPS or damage preview during selection or confirm-only state'))
  assert.ok(manifest.assetBoundary.forbidden.includes('imagegen numbers DPS scores labels or business conclusions'))
  assert.deepEqual(manifest.routeSmokeScenes, [
    'simc_from_workbench',
    'simc_blocked_templates',
    'simc_gear_stat_blocked',
    'simc_confirm_ready',
    'simc_template_ready',
    'simc_task_limit',
    'simc_submitting',
    'simc_task_created'
  ])
  assert.ok(manifest.requiredRuntimeArtifactsAfterImplementation.includes('real WeChat mini-program screenshots after captureSafe=true'))
  assert.ok(manifest.stopConditions.includes('UI needs DPS preview before final task result'))
  assert.ok(manifest.forbiddenPromotion.includes('active_implementation_permit'))
  assert.ok(manifest.forbiddenPromotion.includes('runtime_verified'))
  assert.ok(manifest.nextRequiredEvidence.includes('convert this draft into an active simc implementation permit'))

  assert.match(readme, /Status: `implementation_permit_draft`/)
  assert.match(readme, /not target locked, not an active implementation permit, and not runtime verified/)
  assert.match(readme, /existing `simcraft_template` flow, confirm gate, final submit gate, active task limit and localized SimC error mapping must be preserved/)
  assert.match(readme, /Runtime Evidence Still Missing/)
})

test('implementation permit coverage matrix exposes complete draft coverage without promotion', () => {
  const source = read(permitCoverageMatrixPath)
  const manifest = readJson(permitCoverageMatrixManifestPath)
  const readme = read(permitCoverageMatrixReadmePath)
  const appConfig = readJson('app.json')

  assert.match(source, /^Status: `permit_coverage_matrix_draft`$/m)
  assert.match(source, /not `target_locked`, not an active implementation permit/)
  assert.match(source, /does not authorize page WXML\/WXSS edits/)
  assert.match(source, /A core surface is not implementation-ready until it has:/)
  assert.match(source, /Existing page code, old pass artifacts, component skeletons, browser precheck or a passing page test cannot substitute for an implementation permit/)
  assert.match(source, /\| `news_home` \| `\/pages\/news\/news` \| `implementation_permit_draft`/)
  assert.match(source, /\| `news_list_detail` \| `\/pages\/news\/list`, `\/pages\/news\/detail` \| `surface_component_precheck`/)
  assert.match(source, /\| `builds_tab` \| `\/pages\/builds\/builds` \| `surface_component_precheck`/)
  assert.match(source, /\| `current_spec_workbench` \| `\/pages\/builds\/workbench`, `\/pages\/builds\/builds` entry \| `surface_component_precheck`/)
  assert.match(source, /\| `talent_simulator` \| `\/pages\/builds\/talent-simulator` \| `surface_component_precheck`/)
  assert.match(source, /\| `gear_detail` \| `\/pages\/builds\/detail\?query=gear` \| `surface_component_precheck`/)
  assert.match(source, /\| `simc` \| `\/pages\/simulator\/simc` \| `implementation_permit_draft`/)
  assert.match(source, /\| `chickenbro` \| `\/pages\/simulator\/simulator`, `\/pages\/simulator\/chickenbro` \| `surface_component_precheck`/)
  assert.match(source, /\| `tasks` \| `\/pages\/simulator\/tasks`, `\/pages\/simulator\/task-detail` \| `surface_component_precheck`/)
  assert.match(source, /\| `profile_templates` \| `\/pages\/profile\/profile` \| `surface_component_precheck`/)
  assert.match(source, /Surface Owner Contracts/)
  assert.match(source, /News List Detail Owner Skeleton Source Precheck/)
  assert.match(source, /News List Detail Component Precheck/)
  assert.match(source, /Builds Tab Owner Skeleton Source Precheck/)
  assert.match(source, /Builds Tab Component Precheck/)
  assert.match(source, /Workbench Owner Skeleton Source Precheck/)
  assert.match(source, /Workbench Component Precheck/)
  assert.match(source, /TalentTreeCanvas Owner Skeleton Source Precheck/)
  assert.match(source, /TalentTreeCanvas Component Precheck/)
  assert.match(source, /Tasks Owner Skeleton Source Precheck/)
  assert.match(source, /Tasks Component Precheck/)
  assert.match(source, /Profile Templates Owner Skeleton Source Precheck/)
  assert.match(source, /Profile Templates Component Precheck/)
  assert.match(source, /Chickenbro Owner Skeleton Source Precheck/)
  assert.match(source, /Chickenbro Component Precheck/)
  assert.match(source, /target lock, active permit conversion, page integration under permit/)
  assert.match(source, /\| `pve_dormant` \| `pages\/pve\/\*` not registered \| `out_of_scope_for_runtime_acceptance`/)
  assert.match(source, /All core runtime surfaces now have implementation permit drafts/)
  assert.match(source, /No surface is implementation-ready until its draft is explicitly converted to an active permit/)
  assert.match(source, /Decide which single surface becomes the first active implementation permit/)
  assert.match(source, /Run any missing surface-specific fixture strategy before activating that chosen permit/)
  assert.match(source, /Convert exactly one draft into an active implementation permit before page edits/)
  assert.match(source, /This matrix can only prove `permit_coverage_matrix_draft`/)
  assert.match(source, /surface owner contracts now exist as drafts/)
  assert.match(source, /`builds_tab` now has a source-level `BuildsTabSurface` owner skeleton, fixture matrix and surface component precheck with browser crops/)
  assert.match(source, /`current_spec_workbench` now has a source-level `WorkbenchCockpitSurface` owner skeleton, fixture matrix and surface component precheck with browser crops/)
  assert.match(source, /`talent_simulator` now has a source-level `TalentTreeCanvas` owner skeleton, fixture matrix and surface component precheck with browser crops/)
  assert.match(source, /`tasks` now has source-level `TaskQueueBoard` \/ `TaskResultReport` owner skeletons, fixture matrix and surface component precheck with browser crops/)
  assert.match(source, /`profile_templates` now has source-level `ProfileIdentityPanel` \/ `TemplateLibraryBoard` owner skeletons, fixture matrix and surface component precheck with browser crops/)
  assert.match(source, /`chickenbro` also has a source-level `ChickenbroCoachSurface` owner skeleton, fixture matrix and surface component precheck with browser crops/)

  assert.equal(manifest.status, 'permit_coverage_matrix_draft')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.implementationPermit, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.sourceMatrix, permitCoverageMatrixPath)
  assert.equal(manifest.sourceGoal, goalPath)
  assert.equal(manifest.sourceTargetLockProposal, targetLockProposalPath)
  assert.equal(manifest.sourceSurfaceOwnerContracts, surfaceOwnerContractsPath)
  assert.equal(manifest.surfaceOwnerContractsArtifact, surfaceOwnerContractsManifestPath)
  assert.equal(manifest.sourceNewsListDetailOwnerSkeletonPrecheck, newsListDetailOwnerSkeletonPrecheckPath)
  assert.equal(manifest.newsListDetailOwnerSkeletonArtifact, newsListDetailOwnerSkeletonManifestPath)
  assert.equal(manifest.sourceNewsListDetailComponentPrecheck, newsListDetailComponentPrecheckPath)
  assert.equal(manifest.newsListDetailComponentPrecheckArtifact, newsListDetailComponentPrecheckManifestPath)
  assert.equal(manifest.sourceBuildsTabOwnerSkeletonPrecheck, buildsTabOwnerSkeletonPrecheckPath)
  assert.equal(manifest.buildsTabOwnerSkeletonArtifact, buildsTabOwnerSkeletonManifestPath)
  assert.equal(manifest.sourceBuildsTabComponentPrecheck, buildsTabComponentPrecheckPath)
  assert.equal(manifest.buildsTabComponentPrecheckArtifact, buildsTabComponentPrecheckManifestPath)
  assert.equal(manifest.sourceWorkbenchOwnerSkeletonPrecheck, workbenchOwnerSkeletonPrecheckPath)
  assert.equal(manifest.workbenchOwnerSkeletonArtifact, workbenchOwnerSkeletonManifestPath)
  assert.equal(manifest.sourceWorkbenchComponentPrecheck, workbenchComponentPrecheckPath)
  assert.equal(manifest.workbenchComponentPrecheckArtifact, workbenchComponentPrecheckManifestPath)
  assert.equal(manifest.sourceTalentTreeCanvasOwnerSkeletonPrecheck, talentTreeCanvasOwnerSkeletonPrecheckPath)
  assert.equal(manifest.talentTreeCanvasOwnerSkeletonArtifact, talentTreeCanvasOwnerSkeletonManifestPath)
  assert.equal(manifest.sourceTalentTreeCanvasComponentPrecheck, talentTreeCanvasComponentPrecheckPath)
  assert.equal(manifest.talentTreeCanvasComponentPrecheckArtifact, talentTreeCanvasComponentPrecheckManifestPath)
  assert.equal(manifest.sourceGearDetailOwnerSkeletonPrecheck, gearDetailOwnerSkeletonPrecheckPath)
  assert.equal(manifest.gearDetailOwnerSkeletonArtifact, gearDetailOwnerSkeletonManifestPath)
  assert.equal(manifest.sourceGearDetailComponentPrecheck, gearDetailComponentPrecheckPath)
  assert.equal(manifest.gearDetailComponentPrecheckArtifact, gearDetailComponentPrecheckManifestPath)
  assert.equal(manifest.sourceTasksOwnerSkeletonPrecheck, tasksOwnerSkeletonPrecheckPath)
  assert.equal(manifest.tasksOwnerSkeletonArtifact, tasksOwnerSkeletonManifestPath)
  assert.equal(manifest.sourceTasksComponentPrecheck, tasksComponentPrecheckPath)
  assert.equal(manifest.tasksComponentPrecheckArtifact, tasksComponentPrecheckManifestPath)
  assert.equal(manifest.sourceProfileTemplatesOwnerSkeletonPrecheck, profileTemplatesOwnerSkeletonPrecheckPath)
  assert.equal(manifest.profileTemplatesOwnerSkeletonArtifact, profileTemplatesOwnerSkeletonManifestPath)
  assert.equal(manifest.sourceProfileTemplatesComponentPrecheck, profileTemplatesComponentPrecheckPath)
  assert.equal(manifest.profileTemplatesComponentPrecheckArtifact, profileTemplatesComponentPrecheckManifestPath)
  assert.equal(manifest.sourceChickenbroOwnerSkeletonPrecheck, chickenbroOwnerSkeletonPrecheckPath)
  assert.equal(manifest.chickenbroOwnerSkeletonArtifact, chickenbroOwnerSkeletonManifestPath)
  assert.equal(manifest.sourceChickenbroComponentPrecheck, chickenbroComponentPrecheckPath)
  assert.equal(manifest.chickenbroComponentPrecheckArtifact, chickenbroComponentPrecheckManifestPath)
  assert.equal(manifest.sourceRouteSmokePlan, routeSmokePlanPath)
  assert.deepEqual(manifest.knownPermitDrafts.map((item) => item.surface), [
    'news_home',
    'news_list_detail',
    'builds_tab',
    'current_spec_workbench',
    'talent_simulator',
    'gear_detail',
    'simc',
    'chickenbro',
    'tasks',
    'profile_templates'
  ])
  assert.deepEqual(manifest.knownPermitDrafts.map((item) => item.active), [false, false, false, false, false, false, false, false, false, false])
  assert.equal(manifest.knownPermitDrafts.find((item) => item.surface === 'news_list_detail').status, 'implementation_permit_draft')
  assert.deepEqual(manifest.missingPermitQueue, [])
  for (const forbidden of ['target_locked', 'active_implementation_permit', 'component_precheck', 'runtime_verified', 'final_accepted']) {
    assert.ok(manifest.nonPromotionRule.includes(forbidden))
  }
  const statusBySurface = Object.fromEntries(manifest.coreSurfaceCoverage.map((item) => [item.surface, item.permitStatus]))
  assert.equal(statusBySurface.news_home, 'implementation_permit_draft')
  assert.equal(statusBySurface.news_list_detail, 'surface_component_precheck')
  assert.equal(statusBySurface.builds_tab, 'surface_component_precheck')
  assert.equal(statusBySurface.current_spec_workbench, 'surface_component_precheck')
  assert.equal(statusBySurface.talent_simulator, 'surface_component_precheck')
  assert.equal(statusBySurface.gear_detail, 'surface_component_precheck')
  assert.equal(statusBySurface.simc, 'implementation_permit_draft')
  assert.equal(statusBySurface.chickenbro, 'surface_component_precheck')
  assert.equal(statusBySurface.tasks, 'surface_component_precheck')
  assert.equal(statusBySurface.profile_templates, 'surface_component_precheck')
  assert.equal(statusBySurface.pve_dormant, 'out_of_scope_for_runtime_acceptance')
  const newsListCoverage = manifest.coreSurfaceCoverage.find((item) => item.surface === 'news_list_detail')
  assert.ok(newsListCoverage.missingBeforeImplementation.includes('target lock'))
  assert.ok(newsListCoverage.missingBeforeImplementation.includes('active permit conversion'))
  assert.ok(newsListCoverage.missingBeforeImplementation.includes('page integration under active permit'))
  assert.ok(newsListCoverage.missingBeforeImplementation.includes('runtime screenshots and route smoke'))
  const buildsCoverage = manifest.coreSurfaceCoverage.find((item) => item.surface === 'builds_tab')
  assert.ok(buildsCoverage.missingBeforeImplementation.includes('target lock'))
  assert.ok(buildsCoverage.missingBeforeImplementation.includes('active permit conversion'))
  assert.ok(buildsCoverage.missingBeforeImplementation.includes('page integration under active permit'))
  assert.ok(buildsCoverage.missingBeforeImplementation.includes('runtime screenshots and route smoke'))
  const workbenchCoverage = manifest.coreSurfaceCoverage.find((item) => item.surface === 'current_spec_workbench')
  assert.ok(workbenchCoverage.missingBeforeImplementation.includes('target lock'))
  assert.ok(workbenchCoverage.missingBeforeImplementation.includes('active permit conversion'))
  assert.ok(workbenchCoverage.missingBeforeImplementation.includes('page integration under active permit'))
  assert.ok(workbenchCoverage.missingBeforeImplementation.includes('runtime screenshots and route smoke'))
  const talentCoverage = manifest.coreSurfaceCoverage.find((item) => item.surface === 'talent_simulator')
  assert.ok(talentCoverage.missingBeforeImplementation.includes('target lock'))
  assert.ok(talentCoverage.missingBeforeImplementation.includes('active permit conversion'))
  assert.ok(talentCoverage.missingBeforeImplementation.includes('page integration under active permit'))
  assert.ok(talentCoverage.missingBeforeImplementation.includes('runtime screenshots and route smoke'))
  assert.ok(!talentCoverage.missingBeforeImplementation.includes('TalentTreeCanvas skeleton fixtures precheck crops'))
  const gearCoverage = manifest.coreSurfaceCoverage.find((item) => item.surface === 'gear_detail')
  assert.ok(gearCoverage.missingBeforeImplementation.includes('target lock'))
  assert.ok(gearCoverage.missingBeforeImplementation.includes('active permit conversion'))
  assert.ok(gearCoverage.missingBeforeImplementation.includes('page integration under active permit'))
  assert.ok(gearCoverage.missingBeforeImplementation.includes('runtime screenshots and route smoke'))
  assert.ok(!gearCoverage.missingBeforeImplementation.includes('GearLoadoutBoard skeleton fixtures precheck crops'))
  assert.ok(!gearCoverage.missingBeforeImplementation.includes('GearConfigSheet skeleton fixtures precheck crops'))
  const chickenbroCoverage = manifest.coreSurfaceCoverage.find((item) => item.surface === 'chickenbro')
  assert.ok(!chickenbroCoverage.missingBeforeImplementation.includes('ChickenbroCoachSurface component precheck crops'))
  assert.ok(chickenbroCoverage.missingBeforeImplementation.includes('page integration under active permit'))
  const tasksCoverage = manifest.coreSurfaceCoverage.find((item) => item.surface === 'tasks')
  assert.ok(tasksCoverage.missingBeforeImplementation.includes('target lock'))
  assert.ok(tasksCoverage.missingBeforeImplementation.includes('active permit conversion'))
  assert.ok(tasksCoverage.missingBeforeImplementation.includes('page integration under active permit'))
  assert.ok(tasksCoverage.missingBeforeImplementation.includes('runtime screenshots and route smoke'))
  assert.ok(!tasksCoverage.missingBeforeImplementation.includes('TaskQueueBoard skeleton fixtures precheck crops'))
  assert.ok(!tasksCoverage.missingBeforeImplementation.includes('TaskResultReport skeleton fixtures precheck crops'))
  const profileCoverage = manifest.coreSurfaceCoverage.find((item) => item.surface === 'profile_templates')
  assert.ok(profileCoverage.missingBeforeImplementation.includes('target lock'))
  assert.ok(profileCoverage.missingBeforeImplementation.includes('active permit conversion'))
  assert.ok(profileCoverage.missingBeforeImplementation.includes('page integration under active permit'))
  assert.ok(profileCoverage.missingBeforeImplementation.includes('runtime screenshots and route smoke'))
  assert.ok(!profileCoverage.missingBeforeImplementation.includes('ProfileIdentityPanel skeleton fixtures precheck crops'))
  assert.ok(!profileCoverage.missingBeforeImplementation.includes('TemplateLibraryBoard skeleton fixtures precheck crops'))
  assert.ok(manifest.nextRequiredEvidence.includes('decide which single surface becomes the first active implementation permit'))
  assert.ok(manifest.nextRequiredEvidence.includes('run any missing surface-specific fixture strategy before activating that chosen permit'))

  for (const item of manifest.coreSurfaceCoverage) {
    for (const route of item.routes) {
      if (route.includes('?') || route.includes('*')) continue
      assert.ok(appConfig.pages.includes(route.replace(/^\//, '')), `${route} should be registered`)
    }
  }

  assert.match(readme, /Status: `permit_coverage_matrix_draft`/)
  assert.match(readme, /`talent_simulator` has advanced to surface component precheck/)
  assert.match(readme, /`TalentTreeCanvas` now has a fixture matrix/)
  assert.match(readme, /`tasks` has advanced to surface component precheck/)
  assert.match(readme, /`TaskQueueBoard` and `TaskResultReport` now have a fixture matrix/)
  assert.match(readme, /`profile_templates` has advanced to surface component precheck/)
  assert.match(readme, /`ProfileIdentityPanel` and `TemplateLibraryBoard` now have a fixture matrix/)
  assert.match(readme, /Draft permits exist for:/)
  assert.match(readme, /`news_home`/)
  assert.match(readme, /`news_list_detail`/)
  assert.match(readme, /`builds_tab`/)
  assert.match(readme, /`talent_simulator`/)
  assert.match(readme, /`gear_detail`/)
  assert.match(readme, /`simc`/)
  assert.match(readme, /`tasks`/)
  assert.match(readme, /`profile_templates`/)
  assert.match(readme, /Missing or partial permit coverage:/)
  assert.match(readme, /Missing or partial permit coverage:\n\n- none for the current core runtime surface set/)
  assert.match(readme, /Surface-specific owner contracts now exist as drafts/)
  assert.match(readme, /Source-level skeletons exist for:/)
  assert.match(readme, /ArticleListBoard/)
  assert.match(readme, /ArticleReader/)
  assert.match(readme, /WorkbenchCockpitSurface/)
  assert.match(readme, /TaskQueueBoard/)
  assert.match(readme, /TaskResultReport/)
  assert.match(readme, /ProfileIdentityPanel/)
  assert.match(readme, /TemplateLibraryBoard/)
  assert.match(readme, /ChickenbroCoachSurface/)
  assert.match(readme, /production\/browser component precheck and component crops/)
  assert.match(readme, /Surface component precheck exists for:/)
  assert.match(readme, /`BuildsTabSurface`/)
  assert.match(readme, /TaskQueueBoard/)
  assert.match(readme, /TaskResultReport/)
  assert.match(readme, /ProfileIdentityPanel/)
  assert.match(readme, /TemplateLibraryBoard/)
  assert.match(readme, /ChickenbroCoachSurface/)
  assert.match(readme, /ChatShell/)
  assert.match(readme, /Surface Owner Contract Status/)
  assert.match(readme, /`TaskResultReport`/)
  assert.match(readme, /cannot promote any surface to `active_implementation_permit`, `runtime_verified` or `final_accepted`/)
})

test('new foundation owner component skeletons exist with bounded responsibilities', () => {
  for (const owner of ['app-shell', 'material-image', 'status-visual', 'chat-shell']) {
    for (const ext of ['json', 'js', 'wxml', 'wxss']) {
      assert.ok(fs.existsSync(`components/${owner}/${owner}.${ext}`), `${owner}.${ext} should exist`)
    }
  }

  const appShellWxml = read('components/app-shell/app-shell.wxml')
  const appShellJs = read('components/app-shell/app-shell.js')
  const appShellWxss = read('components/app-shell/app-shell.wxss')
  assert.doesNotMatch(appShellWxml, /time|battery|wifi|Wi-Fi|胶囊|状态栏/i)
  assert.match(appShellJs, /tabSafe/)
  assert.match(appShellJs, /navSafe/)
  assert.match(appShellWxss, /env\(safe-area-inset-bottom\)/)

  const materialWxml = read('components/material-image/material-image.wxml')
  const materialJs = read('components/material-image/material-image.js')
  assert.match(materialWxml, /mode="{{imageMode}}"/)
  assert.match(materialJs, /normalizeFit/)
  assert.match(materialJs, /normalizeTone/)
  assert.match(materialJs, /materialload/)
  assert.match(materialJs, /materialerror/)

  const statusWxml = read('components/status-visual/status-visual.wxml')
  const statusJs = read('components/status-visual/status-visual.js')
  const statusWxss = read('components/status-visual/status-visual.wxss')
  assert.match(statusWxml, /wow-status-visual__atomic/)
  assert.match(statusWxml, /wow-status-visual__base-image/)
  assert.match(statusWxml, /wow-status-visual__glyph-stage/)
  assert.match(statusJs, /GLYPH_BY_STATE/)
  for (const state of ['ready_to_simulate', 'blocked', 'partial', 'stale', 'source_reference', 'unknown']) {
    assert.match(statusJs, new RegExp(state))
  }
  assert.doesNotMatch(statusWxss, /color-mix/)
  assert.match(statusWxss, /currentColor/)

  const chatWxml = read('components/chat-shell/chat-shell.wxml')
  const chatJs = read('components/chat-shell/chat-shell.js')
  const chatWxss = read('components/chat-shell/chat-shell.wxss')
  assert.match(chatWxml, /scroll-view/)
  assert.match(chatWxml, /textarea/)
  assert.match(chatWxml, /evidenceRows/)
  assert.match(chatWxml, /nextQuestions/)
  for (const eventName of ['send', 'inputchange', 'newtopic', 'opendrawer']) {
    assert.match(chatJs, new RegExp(eventName))
  }
  assert.match(chatWxss, /--chat-safe-bottom/)

  const allFoundationComponentSource = [
    'components/app-shell/app-shell.wxml',
    'components/page-frame/page-frame.wxml',
    'components/wow-panel/wow-panel.wxml',
    'components/material-image/material-image.wxml',
    'components/game-object-icon/game-object-icon.wxml',
    'components/status-visual/status-visual.wxml',
    'components/action-button/action-button.wxml',
    'components/module-card/module-card.wxml',
    'components/channel-dock/channel-dock.wxml',
    'components/ranked-feed/ranked-feed.wxml',
    'components/evidence-ledger/evidence-ledger.wxml',
    'components/chat-shell/chat-shell.wxml'
  ].map(read).join('\n')
  assert.doesNotMatch(allFoundationComponentSource, /pass3[0-9]|pass36|pass37/)
  assert.doesNotMatch(read('components/module-card/module-card.wxml'), /status-badge/)
  assert.match(read('components/module-card/module-card.wxml'), /status-visual/)
})
