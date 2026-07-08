const test = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const auditScript = 'scripts/ui-system-evidence-promotion-audit.js'
const auditDocPath = 'docs/design/2026-07-07-wow-ui-system-evidence-promotion-audit.md'
const manifestPath = 'artifacts/ui-system-rebuild/20260707-evidence-promotion-audit/manifest.json'
const readmePath = 'artifacts/ui-system-rebuild/20260707-evidence-promotion-audit/README.md'

function runAudit(args = []) {
  return spawnSync(process.execPath, [auditScript, ...args], {
    encoding: 'utf8'
  })
}

function read(filePath) {
  return fs.readFileSync(filePath, 'utf8')
}

function readJson(filePath) {
  return JSON.parse(read(filePath))
}

test('evidence promotion audit is clean for current source evidence', () => {
  const result = runAudit(['--require-clean', '--json'])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'ui_system_evidence_promotion_clean')
  assert.equal(report.promotionAllowed, false)
  assert.equal(report.violationCount, 0)
  assert.ok(report.scannedFileCount > 0)
  assert.ok(report.forbiddenStatuses.includes('runtime_verified'))
  assert.ok(report.allowedStatusFiles.target_locked.includes('docs/design/2026-07-07-wow-ui-system-target-locked-decision.md'))
  assert.ok(report.allowedStatusFiles.active_implementation_permit.includes('docs/plans/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit.md'))
  assert.ok(report.forbiddenTrueFields.includes('goalComplete'))
})

test('evidence promotion audit fails on forbidden status and true promotion fields', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-promotion-audit-'))
  fs.mkdirSync(path.join(directory, 'nested'), { recursive: true })
  fs.writeFileSync(path.join(directory, 'bad.md'), '# Bad\n\nStatus: `runtime_verified`\n')
  fs.writeFileSync(path.join(directory, 'nested', 'bad.json'), JSON.stringify({
    status: 'final_accepted',
    runtimeVerified: true,
    nested: {
      goalComplete: true
    }
  }))

  const result = runAudit(['--scan-dir', directory, '--require-clean', '--json'])

  assert.equal(result.status, 8)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'ui_system_evidence_promotion_violation')
  assert.equal(report.violationCount, 4)
  assert.ok(report.violations.some((violation) => violation.type === 'forbidden_status_line'))
  assert.ok(report.violations.some((violation) => violation.type === 'forbidden_manifest_status'))
  assert.ok(report.violations.some((violation) => violation.field === '/runtimeVerified'))
  assert.ok(report.violations.some((violation) => violation.field === '/nested/goalComplete'))
})

test('evidence promotion audit artifact records clean non-promotion status', () => {
  const source = read(auditDocPath)
  const manifest = readJson(manifestPath)
  const readme = read(readmePath)

  assert.match(source, /^Status: `ui_system_evidence_promotion_clean`$/m)
  assert.match(source, /promotionAllowed=false/)
  assert.match(source, /target_locked and active_implementation_permit are allowed only in their explicit decision and permit files/)
  assert.match(source, /forbidden status claims remain: `runtime_verified`, `final_accepted`/)
  assert.match(source, /Sentences such as "not `runtime_verified`" remain legal guard language/)

  assert.equal(manifest.status, 'ui_system_evidence_promotion_clean')
  assert.equal(manifest.auditScript, auditScript)
  assert.equal(manifest.promotionAllowed, false)
  assert.equal(manifest.expectedRequireCleanExitCode, 0)
  assert.ok(manifest.forbiddenStatuses.includes('final_accepted'))
  assert.ok(manifest.forbiddenTrueFields.includes('implementationAllowed'))
  assert.ok(manifest.allowedStatusFiles.target_locked.includes('docs/design/2026-07-07-wow-ui-system-target-locked-decision.md'))

  assert.match(readme, /promotionAllowed: false/)
})
