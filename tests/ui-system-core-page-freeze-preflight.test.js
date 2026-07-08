const test = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')

const freezeScript = 'scripts/ui-system-core-page-freeze-preflight.js'

function runFreeze(args = []) {
  return spawnSync(process.execPath, [freezeScript, ...args], {
    encoding: 'utf8'
  })
}

test('core page freeze preflight allows evidence and owner component work without page changes', () => {
  const result = runFreeze([
    '--require-frozen',
    '--json',
    '--changed-file', 'docs/design/example.md',
    '--changed-file', 'tests/example.test.js',
    '--changed-file', 'scripts/example.js',
    '--changed-file', 'components/status-visual/status-visual.wxml',
    '--changed-file', 'assets/ui-system/example.png'
  ])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'core_page_freeze_clean')
  assert.equal(report.freezeSatisfied, true)
  assert.equal(report.frozenCoreFileCount, 0)
  assert.deepEqual(report.frozenCoreFiles, [])
})

test('core page freeze preflight blocks page app navigation and project config changes without target lock and active permit', () => {
  const result = runFreeze([
    '--require-frozen',
    '--json',
    '--changed-file', 'pages/news/news.wxml',
    '--changed-file', 'pages/builds/workbench.wxss',
    '--changed-file', 'pages/simulator/chickenbro.js',
    '--changed-file', 'app.json',
    '--changed-file', 'components/navigation-bar/navigation-bar.wxml',
    '--changed-file', 'project.config.json'
  ])

  assert.equal(result.status, 16)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'core_page_freeze_blocked')
  assert.equal(report.freezeSatisfied, false)
  assert.equal(report.blockedByMissingGate, true)
  assert.equal(report.targetDecisionExists, false)
  assert.equal(report.activePermitExists, false)
  assert.equal(report.frozenCoreFileCount, 6)
  assert.equal(report.groupedFrozenFileCounts.core_surface_page, 3)
  assert.equal(report.groupedFrozenFileCounts.app_shell, 1)
  assert.equal(report.groupedFrozenFileCounts.navigation_chrome, 1)
  assert.equal(report.groupedFrozenFileCounts.devtools_project_config, 1)
  assert.ok(report.frozenCoreFiles.includes('pages/news/news.wxml'))
  assert.ok(report.frozenCoreFiles.includes('pages/builds/workbench.wxss'))
  assert.ok(report.frozenCoreFiles.includes('project.config.json'))
  assert.ok(report.missingRequirements.includes('target_locked_decision_record'))
  assert.ok(report.missingRequirements.includes('active_implementation_permit'))
  assert.match(report.requiredAction, /freeze or quarantine core page\/app\/navigation changes/)
  assert.ok(report.nonPromotion.includes('not_runtime_verified'))
})

test('core page freeze preflight summary keeps the blocked file list and grouped counts', () => {
  const result = runFreeze([
    '--summary-json',
    '--changed-file', 'pages/profile/profile.wxml',
    '--changed-file', 'docs/design/example.md'
  ])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'core_page_freeze_blocked')
  assert.equal(report.freezeSatisfied, false)
  assert.equal(report.frozenCoreFileCount, 1)
  assert.equal(report.groupedFrozenFileCounts.core_surface_page, 1)
  assert.ok(report.frozenCoreFiles.includes('pages/profile/profile.wxml'))
})
