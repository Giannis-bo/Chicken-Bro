const test = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')

const preflightScript = 'scripts/ui-system-activation-preflight.js'

function runPreflight(args = []) {
  return spawnSync(process.execPath, [preflightScript, ...args], {
    encoding: 'utf8'
  })
}

test('activation preflight reports current target-lock gate as blocked', () => {
  const result = runPreflight(['--json'])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'activation_preflight_blocked')
  assert.equal(report.activationAllowed, false)
  assert.equal(report.pageIntegrationAllowed, false)
  assert.equal(report.targetLockedDecisionRecordPath, 'docs/design/2026-07-07-wow-ui-system-target-locked-decision.md')
  assert.equal(report.targetLockedDecisionRecordExists, false)
  assert.equal(report.firstActivePermitPath, 'docs/plans/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit.md')
  assert.equal(report.firstActivePermitExists, false)
  assert.ok(report.blockingReasons.includes('missing_target_locked_decision_record'))
  assert.ok(report.blockingReasons.includes('missing_active_implementation_permit'))
  assert.ok(report.blockingReasons.includes('continuation_turn_is_not_confirmation'))
  assert.ok(report.forbiddenWhileBlocked.includes('page WXML/WXSS implementation'))
})

test('activation preflight can fail implementation entrypoints while blocked', () => {
  const result = runPreflight(['--require-activation', '--json'])

  assert.equal(result.status, 2)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'activation_preflight_blocked')
  assert.equal(report.activationAllowed, false)
  assert.ok(report.nextValidTransitions.includes('explicit user target-lock confirmation or written modification'))
})
