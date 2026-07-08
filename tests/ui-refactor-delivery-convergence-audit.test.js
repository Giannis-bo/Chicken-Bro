const test = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const auditScript = 'scripts/ui-refactor-delivery-convergence-audit.js'

function runAudit(args = []) {
  return spawnSync(process.execPath, [auditScript, ...args], {
    encoding: 'utf8'
  })
}

function copyFixture(sourceRoot, targetRoot, filePath) {
  const source = path.join(sourceRoot, filePath)
  const target = path.join(targetRoot, filePath)
  fs.mkdirSync(path.dirname(target), { recursive: true })
  fs.copyFileSync(source, target)
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'))
}

function writeJson(filePath, value) {
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`)
}

test('delivery convergence audit passes the narrowed handoff package without runtime promotion', () => {
  const result = runAudit(['--require-ready', '--json'])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'ui_refactor_delivery_convergence_ready')
  assert.equal(report.deliveryConvergenceReady, true)
  assert.equal(report.surface, 'news_list_detail')
  assert.equal(report.runtimeEvidenceMode, 'blocked_explained')
  assert.deepEqual(report.missingRequirements, [])
  assert.equal(report.commandResults.courseCorrection.status, 'ui_refactor_course_correction_ready')
  assert.equal(report.commandResults.implementationGate.status, 'ui_system_implementation_gate_passed')
  assert.equal(report.commandResults.pageAdoption.status, 'page_adoption_ready')
  assert.equal(report.commandResults.evidencePromotion.status, 'ui_system_evidence_promotion_clean')
  assert.equal(report.nonPromotion.runtimeVerified, false)
  assert.equal(report.nonPromotion.finalAccepted, false)
  assert.equal(report.nonPromotion.allSurfaceAccepted, false)
})

test('delivery convergence audit fails when runtime blocker is not backed by health evidence', () => {
  const sourceRoot = process.cwd()
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-delivery-audit-'))
  const requiredFiles = [
    'artifacts/ui-system-rebuild/20260707-delivery-convergence/manifest.json',
    'artifacts/ui-system-rebuild/20260707-delivery-backlog/manifest.json',
    'artifacts/ui-system-rebuild/20260707-news-list-detail-route-smoke-plan/manifest.json',
    'artifacts/ui-system-rebuild/20260707-news-list-detail-runtime-verification-status/manifest.json',
    'artifacts/ui-system-rebuild/20260707-news-list-detail-active-permit/manifest.json'
  ]
  requiredFiles.forEach((filePath) => copyFixture(sourceRoot, directory, filePath))

  const runtimePath = path.join(
    directory,
    'artifacts/ui-system-rebuild/20260707-news-list-detail-runtime-verification-status/manifest.json'
  )
  const runtimeStatus = readJson(runtimePath)
  runtimeStatus.devtoolsHealthCheck.path = 'artifacts/ui-system-rebuild/runtime-health/missing.json'
  writeJson(runtimePath, runtimeStatus)

  const result = runAudit(['--root', directory, '--json'])
  assert.equal(result.status, 0)

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'ui_refactor_delivery_convergence_incomplete')
  assert.equal(report.deliveryConvergenceReady, false)
  assert.ok(report.missingRequirements.includes('runtime.devtoolsHealthCheck.path_exists'))
})
