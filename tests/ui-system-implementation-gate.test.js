const test = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')

const gateScript = 'scripts/ui-system-implementation-gate.js'
const gateDocPath = 'docs/design/2026-07-07-wow-ui-system-implementation-gate.md'
const gateManifestPath = 'artifacts/ui-system-rebuild/20260707-implementation-gate/manifest.json'
const gateReadmePath = 'artifacts/ui-system-rebuild/20260707-implementation-gate/README.md'

function runGate(args = []) {
  return spawnSync(process.execPath, [gateScript, ...args], {
    encoding: 'utf8'
  })
}

function read(filePath) {
  return fs.readFileSync(filePath, 'utf8')
}

function readJson(filePath) {
  return JSON.parse(read(filePath))
}

test('implementation gate passes the confirmed news_list_detail implementation entrypoint', () => {
  const result = runGate(['--require-implementation', '--json'])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'ui_system_implementation_gate_passed')
  assert.equal(report.implementationAllowed, true)
  assert.equal(report.checkedSurface, 'news_list_detail')
  assert.deepEqual(report.blockingChecks, [])
  assert.deepEqual(report.blockingReasons, [])
  assert.ok(report.checks.find((check) => check.id === 'activation').exitCode === 0)
  assert.ok(report.checks.find((check) => check.id === 'target_lock_decision').exitCode === 0)
  assert.ok(report.checks.find((check) => check.id === 'first_surface_readiness').exitCode === 0)
  assert.equal(report.checks.find((check) => check.id === 'first_surface_readiness').passed, true)
  assert.ok(report.checks.find((check) => check.id === 'course_correction').exitCode === 0)
  assert.ok(report.checks.find((check) => check.id === 'active_permit').exitCode === 0)
  assert.ok(report.checks.find((check) => check.id === 'diff_scope').exitCode === 0)
})

test('implementation gate artifact records passed single-surface status without runtime promotion', () => {
  const source = read(gateDocPath)
  const manifest = readJson(gateManifestPath)
  const readme = read(gateReadmePath)

  assert.match(source, /^Status: `ui_system_implementation_gate_passed`$/m)
  assert.match(source, /implementationAllowed=true/)
  assert.match(source, /activation_preflight_passed/)
  assert.match(source, /target_lock_decision_ready/)
  assert.match(source, /first_surface_activation_readiness_ready/)
  assert.match(source, /ui_refactor_course_correction_ready/)
  assert.match(source, /active_permit_ready/)
  assert.match(source, /diff_scope_clean_for_current_gate/)

  assert.equal(manifest.status, 'ui_system_implementation_gate_passed')
  assert.equal(manifest.gateScript, gateScript)
  assert.equal(manifest.implementationAllowed, true)
  assert.equal(manifest.expectedRequireImplementationExitCode, 0)
  assert.ok(manifest.aggregatedChecks.some((check) => check.id === 'first_surface_readiness' && check.expectedStatus === 'first_surface_activation_readiness_ready'))
  assert.ok(manifest.aggregatedChecks.some((check) => check.id === 'course_correction' && check.expectedStatus === 'ui_refactor_course_correction_ready'))
  assert.deepEqual(manifest.blockingChecks, [])
  assert.ok(manifest.passingChecks.includes('diff_scope'))
  assert.ok(manifest.nonPromotion.includes('not runtime_verified'))

  assert.match(readme, /implementationAllowed: true/)
})
