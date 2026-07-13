const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const projectStatePath = 'docs/project-state.json'
const phase4HistoryPath = 'docs/roadmap/history/2026-07-phase4-pg-read-model.md'
const controlPlaneRelease = 'artifacts/releases/2026-07-10-harness-control-plane'
const executableHarnessRelease = 'artifacts/releases/2026-07-10-executable-project-harness'
const characterizationRelease = 'artifacts/releases/2026-07-10-critical-contract-characterization'
const archivedPhase5Release = 'artifacts/releases/2026-07-11-equipment-simulator-phase5c-frontend-cutover'
const activeTalentLkgRelease = 'artifacts/releases/2026-07-13-talent-link-lkg-sync-guard'

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'))
}

function assertPathExists(relativePath) {
  assert.ok(fs.existsSync(relativePath), `${relativePath} should exist`)
}

function assertUniqueById(entries, label) {
  const ids = entries.map((entry) => entry.id)
  assert.equal(new Set(ids).size, ids.length, `${label} ids should be unique`)
}

test('project-state is the single machine-readable current truth entry', () => {
  assertPathExists(projectStatePath)
  const state = readJson(projectStatePath)

  assert.equal(state.schemaVersion, 1)
  assert.equal(state.updatedAt, '2026-07-13')
  assert.equal(state.activeMilestone, 'none')
  assert.equal(state.featureIteration, 'allowed_under_harness')
  assert.equal(state.activeReleaseArtifact, activeTalentLkgRelease)

  assert.ok(Array.isArray(state.activeContracts), 'activeContracts should be an array')
  assert.ok(Array.isArray(state.completedBaselines), 'completedBaselines should be an array')
  assert.ok(Array.isArray(state.historicalContracts), 'historicalContracts should be an array')
  assert.ok(Array.isArray(state.controlPlaneConclusions), 'controlPlaneConclusions should be an array')

  assertUniqueById(state.activeContracts, 'activeContracts')
  assertUniqueById(state.completedBaselines, 'completedBaselines')
  assertUniqueById(state.historicalContracts, 'historicalContracts')

  const activeContractIds = new Set(state.activeContracts.map((entry) => entry.id))
  assert.ok(activeContractIds.has('talent_link_lkg_sync_guard'))
  assert.ok(!activeContractIds.has('equipment_simulator_capability_architecture'))
  assert.ok(!activeContractIds.has('equipment_simulator_phase5_async_stat_snapshot_plan'))
  assert.ok(!activeContractIds.has('equipment_simulator_phase3_resolve_profile_workbench_plan'))
  assert.ok(!activeContractIds.has('equipment_simulator_phase1_contracts_plan'))

  const historicalContractIds = new Set(state.historicalContracts.map((entry) => entry.id))
  assert.ok(historicalContractIds.has('equipment_simulator_phase0_safety'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase1_contracts_plan'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase2a_pure_resolver'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase2b_pg_loader_facade_parity'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase2_canonical_resolver_plan'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase3a_resolve_profile_api'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase3b_structured_transport_state'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase3c_workbench_cutover'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase3_resolve_profile_workbench_plan'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase4a_release_contracts'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase4b_pg_registry_legacy_import'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase4c_release_shadow_readers'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase4d_atomic_manifest_cutover'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase4e_scheduled_refresh'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase4_release_train_plan'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase5a_stat_snapshot_store'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase5b_stat_snapshot_worker_api'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase5c_frontend_cutover'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase5_async_stat_snapshot_plan'))
  assert.ok(historicalContractIds.has('equipment_simulator_capability_architecture'))

  for (const entry of state.activeContracts) {
    assert.notEqual(entry.lifecycle, 'historical', `${entry.id} should not be historical and active`)
    assertPathExists(entry.path)
  }
  for (const entry of state.historicalContracts) {
    assert.equal(entry.lifecycle, 'historical', `${entry.id} should be explicitly historical`)
    assertPathExists(entry.path)
  }

  const activePaths = new Set(state.activeContracts.map((entry) => entry.path))
  for (const entry of state.historicalContracts) {
    assert.ok(!activePaths.has(entry.path), `${entry.path} should not be both active and historical`)
  }

  for (const releasePath of [activeTalentLkgRelease, archivedPhase5Release, characterizationRelease, executableHarnessRelease, controlPlaneRelease]) {
    assertPathExists(path.join(releasePath, 'requirement.json'))
    assertPathExists(path.join(releasePath, 'evidence.json'))
    assertPathExists(path.join(releasePath, 'manifest.json'))
  }

  assert.ok(
    state.completedBaselines.some((entry) => entry.id === 'project_harness_normalization_20260710'),
    'Project Harness normalization should be recorded as a completed baseline'
  )
  assert.ok(
    state.completedBaselines.some((entry) => entry.id === 'equipment_simulator_phase1_20260710'),
    'Equipment simulator Phase 1 should be recorded as a completed baseline'
  )
  assert.ok(
    state.completedBaselines.some((entry) => entry.id === 'equipment_simulator_phase2a_20260710'),
    'Equipment simulator Phase 2A should be recorded as a completed baseline'
  )
  assert.ok(
    state.completedBaselines.some((entry) => entry.id === 'equipment_simulator_phase2_20260711'),
    'Equipment simulator Phase 2 should be recorded as a completed baseline'
  )
  assert.ok(
    state.completedBaselines.some((entry) => entry.id === 'equipment_simulator_phase3a_20260711'),
    'Equipment simulator Phase 3A should be recorded as a completed baseline'
  )
  assert.ok(
    state.completedBaselines.some((entry) => entry.id === 'equipment_simulator_phase3b_20260711'),
    'Equipment simulator Phase 3B should be recorded as a completed baseline'
  )
  assert.ok(
    state.completedBaselines.some((entry) => entry.id === 'equipment_simulator_phase3_20260711'),
    'Equipment simulator Phase 3 should be recorded as a completed baseline'
  )
  assert.ok(
    state.completedBaselines.some((entry) => entry.id === 'equipment_simulator_phase4a_20260711'),
    'Equipment simulator Phase 4A should be recorded as a completed baseline'
  )
  assert.ok(
    state.completedBaselines.some((entry) => entry.id === 'equipment_simulator_phase4b_20260711'),
    'Equipment simulator Phase 4B should be recorded as a completed baseline'
  )
  assert.ok(
    state.completedBaselines.some((entry) => entry.id === 'equipment_simulator_phase4c_20260711'),
    'Equipment simulator Phase 4C should be recorded as a completed baseline'
  )
  assert.ok(
    state.completedBaselines.some((entry) => entry.id === 'equipment_simulator_phase5_20260712'),
    'Equipment simulator Phase 0-5 should be recorded as a completed live baseline'
  )

  const gearStat = state.runtimeBaseline.gearStatSnapshot
  assert.equal(gearStat.status, 'phase5_complete_live_verified')
  assert.equal(gearStat.frontendCutover, true)
  assert.equal(gearStat.verifiedSpecCount, 32)
  assert.equal(gearStat.explicitNonReadySpecCount, 8)

  const phase5Evidence = readJson(path.join(archivedPhase5Release, 'evidence.json'))
  const phase5Closure = readJson(path.join(archivedPhase5Release, 'closure-audit.json'))
  const phase5Requirement = readJson(path.join(archivedPhase5Release, 'requirement.json'))
  const phase5Plan = fs.readFileSync('docs/plans/2026-07-11-equipment-simulator-phase5-async-stat-snapshot-plan.md', 'utf8')
  const gearRunbook = fs.readFileSync('docs/gear-simulation-full-chain-runbook.md', 'utf8')
  const buildsArchitecture = fs.readFileSync('docs/builds-architecture.md', 'utf8')
  const simulatorContract = fs.readFileSync('docs/simulator-simc-end-to-end.md', 'utf8')
  assert.equal(phase5Evidence.status, 'archived')
  assert.equal(phase5Evidence.highestEvidenceLevel, 'live_verified')
  assert.equal(phase5Closure.status, 'completed_live_verified_archived')
  assert.equal(phase5Closure.phase6Catalyst.status, 'external_dependency_todo_fail_closed')
  assert.deepEqual(phase5Closure.phase5dMatrix.contractDecision, {
    approvedAt: '2026-07-12',
    approvedBy: 'user',
    decision: 'split_profile_readiness_from_stat_execution_outcome',
    profileReadinessScope: 'canonical_resolver_and_profile_serializer_readiness',
    acceptedStatExecutionOutcomes: ['verified_immutable_snapshot', 'explicit_fail_closed_problem_without_snapshot'],
    verifiedSnapshotCount: 32,
    explicitFailClosedCount: 8,
    runtimeScopeExpanded: false
  })
  assert.ok(
    phase5Requirement.decisionLog.some((entry) => entry.decision === 'Phase 5D separates profileReadiness from stat execution outcome and accepts 32 verified snapshots plus 8 explicit fail-closed outcomes as honest closure evidence.'),
    'Phase 5C requirement should record the approved Phase 5D closure decision'
  )
  assert.doesNotMatch(phase5Plan, /Every combination that claims `profileReadiness=ready` must execute through the worker and produce parseable verified JSON/)
  assert.match(phase5Plan, /`profileReadiness=ready` authorizes canonical serialization and worker execution; it does not predeclare the stat execution result/)
  assert.doesNotMatch(gearRunbook, /`pages\/simulator\/simc\.js`[^\n]*请求 `\/api\/websim\/gear\/stats`/)
  assert.match(buildsArchitecture, /`POST \/api\/websim\/gear\/stat-snapshots`/)
  assert.match(buildsArchitecture, /旧 `POST \/api\/websim\/gear\/stats`[^\n]*兼容/)
  assert.match(simulatorContract, /async stat-snapshot API/)
  assert.match(simulatorContract, /Profile readiness and stat execution outcome are separate contracts/)
})

test('current truth has one conclusion for UI, PG read-model, Harness normalization and equipment simulator Phase 0-5', () => {
  const state = readJson(projectStatePath)
  const conclusions = state.controlPlaneConclusions
  const domains = conclusions.map((entry) => entry.domain)

  assert.equal(new Set(domains).size, domains.length, 'control-plane conclusion domains should be unique')

  const byDomain = new Map(conclusions.map((entry) => [entry.domain, entry]))
  assert.equal(byDomain.get('ui_delivery').status, 'accepted_baseline')
  assert.equal(byDomain.get('pg_read_model_phase4').status, 'completed')
  assert.equal(byDomain.get('project_harness_normalization').status, 'completed')
  assert.equal(byDomain.get('equipment_simulator_phase0_5').status, 'completed_live_verified')

  assert.equal(byDomain.get('ui_delivery').activeContract, null)
  assert.equal(byDomain.get('pg_read_model_phase4').activeContract, null)
  assert.equal(byDomain.get('project_harness_normalization').activeContract, null)
  assert.equal(byDomain.get('equipment_simulator_phase0_5').activeContract, null)
})

test('roadmap top is concise and phase 4 PR-level detail is archived', () => {
  assertPathExists(phase4HistoryPath)
  const roadmapTop = fs.readFileSync('docs/roadmap.md', 'utf8')
    .split(/\r?\n/)
    .slice(0, 40)
    .join('\n')
  const history = fs.readFileSync(phase4HistoryPath, 'utf8')

  assert.match(roadmapTop, /Project Harness 工程规范化（已完成/)
  assert.match(roadmapTop, /装备模拟 Phase 0–5（已完成/)
  assert.match(roadmapTop, /Phase 6.*fail-closed/)
  assert.doesNotMatch(roadmapTop, /Phase 4 第[一二三四五六七八九十]+刀/)
  assert.match(history, /Phase 4 第四十刀/)
  assert.match(history, /公开 observed-only gear 入口、baseline 默认空/)
})
