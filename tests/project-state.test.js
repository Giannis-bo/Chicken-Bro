const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')

const { classifyPath, loadRules } = require('../scripts/build-chickenbro-simc-refactor-inventory')

const repositoryRoot = path.resolve(__dirname, '..')
const readJson = (relativePath) => JSON.parse(fs.readFileSync(path.join(repositoryRoot, relativePath), 'utf8'))
const exists = (relativePath) => fs.existsSync(path.join(repositoryRoot, relativePath))

const activePlans = [
  'docs/superpowers/plans/2026-09-02-chickenbro-simc-rebuild-01-control-plane.md',
  'docs/superpowers/plans/2026-09-02-chickenbro-simc-rebuild-02-identity-data.md',
  'docs/superpowers/plans/2026-09-02-chickenbro-simc-rebuild-03-chat.md',
  'docs/superpowers/plans/2026-09-02-chickenbro-simc-rebuild-04-simc.md',
  'docs/superpowers/plans/2026-09-02-chickenbro-simc-rebuild-05-dual-client-migration-cutover.md',
  'docs/superpowers/plans/2026-09-02-chickenbro-simc-rebuild-06-legacy-retirement.md',
]

test('project state names only the approved dual-client Chat and SimC product', () => {
  const state = readJson('docs/project-state.json')

  assert.equal(state.schemaVersion, 2)
  assert.equal(state.activeMilestone, 'chickenbro_simc_total_rebuild_phase_6')
  assert.deepEqual(state.targetProduct.businessDomains, ['chickenbro_chat', 'simc'])
  assert.deepEqual(state.targetProduct.clients, ['wechat_mini_program', 'web'])
  assert.equal(state.targetProduct.identityOwner, 'identity.users.id')
  assert.match(state.targetProduct.crossClientContract, /same internal user_id/)
  assert.deepEqual(state.targetProduct.implementationPlans, activePlans)
  assert.ok(activePlans.every(exists))

  const serialized = JSON.stringify(state)
  for (const removedDomain of ['news_content', 'equipment_catalog', 'talent_graph', 'websim_sync']) {
    assert.equal(serialized.includes(removedDomain), false, removedDomain)
  }
})
test('project state preserves the live safety boundary instead of claiming completion', () => {
  const state = readJson('docs/project-state.json')

  assert.equal(state.delivery.phase1, 'local_verified')
  assert.equal(state.delivery.phase2, 'local_verified_candidate_apply_blocked')
  assert.equal(state.delivery.phase3, 'local_verified')
  assert.equal(state.delivery.phase4, 'local_verified')
  assert.equal(state.delivery.phase5, 'local_verified_live_acceptance_blocked')
  assert.equal(state.delivery.phase6, 'local_and_cloud_cleanup_controls_verified_apply_blocked')
  assert.deepEqual(state.refactorEvidence.localCleanupDryRun, {
    deletable: 2588,
    retained: 267,
    blocked: 0,
    review: 0,
    phase5Accepted: false,
  })
  assert.deepEqual(state.refactorEvidence.cloudCleanupDryRun, {
    total: 80,
    ready: 0,
    blocked: 80,
    unresolvedRequiredTargets: 2,
  })
  assert.equal(state.gates.productionCutoverReady, false)
  assert.equal(state.gates.destructiveCleanupReady, false)
  assert.equal(state.gates.finalUserAcceptance, 'not_run')
  assert.deepEqual(state.gates.cleanupPrerequisites, [
    'independent_restore_verified_backup',
    'candidate_capacity_gate_passed',
    'real_mini_web_acceptance_passed',
    'first_new_write_reconciled',
    'stable_production_health',
  ])
})

test('all execution authorities and refactor evidence are explicit existing files', () => {
  const state = readJson('docs/project-state.json')
  const authorities = Object.values(state.executionAuthority)
  const evidence = Object.values(state.refactorEvidence).filter((value) => typeof value === 'string' && value.includes('/'))

  for (const relativePath of [...authorities, ...evidence]) {
    assert.equal(exists(relativePath), true, relativePath)
  }
  assert.equal(state.refactorEvidence.capacityGate, 'blocked_until_independent_recovery_or_storage_expansion')
  assert.equal(state.refactorEvidence.localCleanupApplyAllowed, false)
  assert.equal(state.refactorEvidence.cloudCleanupApplyAllowed, false)
})

test('every local link in retained Markdown resolves to another retained path', () => {
  const rules = loadRules(path.join(repositoryRoot, 'docs/refactor/chickenbro-simc-disposition-rules.json'))
  const retainedMarkdown = [
    'README.md',
    'docs/README.md',
    'docs/harness.md',
    'docs/roadmap.md',
    'docs/roadmap/ideas.md',
    'docs/verification-matrix.md',
    'docs/chickenbro-simc-architecture.md',
    'docs/chickenbro-simc-production-runbook.md',
    'docs/plans/README.md',
    ...activePlans,
    'docs/superpowers/specs/2026-09-02-chickenbro-simc-total-rebuild-design.md',
  ]

  for (const sourcePath of retainedMarkdown) {
    assert.equal(exists(sourcePath), true, sourcePath)
    const source = fs.readFileSync(path.join(repositoryRoot, sourcePath), 'utf8')
    for (const match of source.matchAll(/\[[^\]]+\]\(([^)]+)\)/g)) {
      const target = match[1].trim().split('#', 1)[0]
      if (!target || /^(?:https?:|mailto:)/.test(target)) continue
      const resolved = path.posix.normalize(path.posix.join(path.posix.dirname(sourcePath), target))
      assert.equal(exists(resolved), true, `${sourcePath} -> ${target}`)
      assert.equal(classifyPath(resolved, rules).disposition, 'keep', `${sourcePath} -> ${target}`)
    }
  }
})
