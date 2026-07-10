const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const projectStatePath = 'docs/project-state.json'
const phase4HistoryPath = 'docs/roadmap/history/2026-07-phase4-pg-read-model.md'
const controlPlaneRelease = 'artifacts/releases/2026-07-10-harness-control-plane'
const executableHarnessRelease = 'artifacts/releases/2026-07-10-executable-project-harness'
const characterizationRelease = 'artifacts/releases/2026-07-10-critical-contract-characterization'
const activeRelease = 'artifacts/releases/2026-07-10-equipment-simulator-phase1-contracts-rule-authority'

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
  assert.equal(state.updatedAt, '2026-07-10')
  assert.equal(state.activeMilestone, 'equipment_simulator_phase2')
  assert.equal(state.featureIteration, 'allowed_under_harness')
  assert.equal(state.activeReleaseArtifact, activeRelease)

  assert.ok(Array.isArray(state.activeContracts), 'activeContracts should be an array')
  assert.ok(Array.isArray(state.completedBaselines), 'completedBaselines should be an array')
  assert.ok(Array.isArray(state.historicalContracts), 'historicalContracts should be an array')
  assert.ok(Array.isArray(state.controlPlaneConclusions), 'controlPlaneConclusions should be an array')

  assertUniqueById(state.activeContracts, 'activeContracts')
  assertUniqueById(state.completedBaselines, 'completedBaselines')
  assertUniqueById(state.historicalContracts, 'historicalContracts')

  const activeContractIds = new Set(state.activeContracts.map((entry) => entry.id))
  assert.ok(activeContractIds.has('equipment_simulator_capability_architecture'))
  assert.ok(activeContractIds.has('equipment_simulator_phase2_canonical_resolver_plan'))
  assert.ok(!activeContractIds.has('equipment_simulator_phase1_contracts_plan'))

  const historicalContractIds = new Set(state.historicalContracts.map((entry) => entry.id))
  assert.ok(historicalContractIds.has('equipment_simulator_phase0_safety'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase1_contracts_plan'))

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

  for (const releasePath of [activeRelease, characterizationRelease, executableHarnessRelease, controlPlaneRelease]) {
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
})

test('current truth has one conclusion for UI, PG read-model and Harness normalization', () => {
  const state = readJson(projectStatePath)
  const conclusions = state.controlPlaneConclusions
  const domains = conclusions.map((entry) => entry.domain)

  assert.equal(new Set(domains).size, domains.length, 'control-plane conclusion domains should be unique')

  const byDomain = new Map(conclusions.map((entry) => [entry.domain, entry]))
  assert.equal(byDomain.get('ui_delivery').status, 'accepted_baseline')
  assert.equal(byDomain.get('pg_read_model_phase4').status, 'completed')
  assert.equal(byDomain.get('project_harness_normalization').status, 'completed')

  assert.equal(byDomain.get('ui_delivery').activeContract, null)
  assert.equal(byDomain.get('pg_read_model_phase4').activeContract, null)
  assert.equal(byDomain.get('project_harness_normalization').activeContract, null)
})

test('roadmap top is concise and phase 4 PR-level detail is archived', () => {
  assertPathExists(phase4HistoryPath)
  const roadmapTop = fs.readFileSync('docs/roadmap.md', 'utf8')
    .split(/\r?\n/)
    .slice(0, 40)
    .join('\n')
  const history = fs.readFileSync(phase4HistoryPath, 'utf8')

  assert.match(roadmapTop, /Project Harness 工程规范化（已完成/)
  assert.doesNotMatch(roadmapTop, /Phase 4 第[一二三四五六七八九十]+刀/)
  assert.match(history, /Phase 4 第四十刀/)
  assert.match(history, /公开 observed-only gear 入口、baseline 默认空/)
})
