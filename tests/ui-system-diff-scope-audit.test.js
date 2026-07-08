const test = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')

const auditScript = 'scripts/ui-system-diff-scope-audit.js'
const auditDocPath = 'docs/design/2026-07-07-wow-ui-system-diff-scope-audit.md'
const auditManifestPath = 'artifacts/ui-system-rebuild/20260707-diff-scope-audit/manifest.json'
const auditReadmePath = 'artifacts/ui-system-rebuild/20260707-diff-scope-audit/README.md'

function runAudit(args = []) {
  return spawnSync(process.execPath, [auditScript, ...args], {
    encoding: 'utf8'
  })
}

function read(path) {
  return fs.readFileSync(path, 'utf8')
}

function readJson(path) {
  return JSON.parse(read(path))
}

test('diff scope audit allows evidence and owner work while activation is blocked', () => {
  const result = runAudit([
    '--json',
    '--changed-file', 'docs/design/example.md',
    '--changed-file', 'tests/example.test.js',
    '--changed-file', 'components/status-visual/status-visual.wxml',
    '--changed-file', 'assets/ui-system/example.png'
  ])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'diff_scope_clean_for_current_gate')
  assert.equal(report.activationAllowed, false)
  assert.equal(report.pageIntegrationAllowed, false)
  assert.equal(report.pageScopeBlocked, false)
  assert.deepEqual(report.blockedPageIntegrationFiles, [])
  assert.ok(report.categories.evidenceOrTooling.includes('docs/design/example.md'))
  assert.ok(report.categories.componentOwnerWork.includes('components/status-visual/status-visual.wxml'))
  assert.ok(report.categories.assetWork.includes('assets/ui-system/example.png'))
})

test('diff scope audit blocks page and app-shell edits until active permit exists', () => {
  const result = runAudit([
    '--require-no-page-integration',
    '--json',
    '--changed-file', 'pages/news/news.wxml',
    '--changed-file', 'pages/builds/workbench.wxss',
    '--changed-file', 'app.wxss',
    '--changed-file', 'components/navigation-bar/navigation-bar.wxml',
    '--changed-file', 'project.config.json'
  ])

  assert.equal(result.status, 3)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'diff_scope_blocked_page_integration_present')
  assert.equal(report.pageScopeBlocked, true)
  assert.equal(report.devtoolsScopeRisk, true)
  assert.ok(report.blockedPageIntegrationFiles.includes('pages/news/news.wxml'))
  assert.ok(report.blockedPageIntegrationFiles.includes('pages/builds/workbench.wxss'))
  assert.ok(report.blockedPageIntegrationFiles.includes('app.wxss'))
  assert.ok(report.blockedPageIntegrationFiles.includes('components/navigation-bar/navigation-bar.wxml'))
  assert.ok(report.devtoolsTouchRiskFiles.includes('project.config.json'))
  assert.match(report.requiredAction, /quarantine page\/app\/navigation changes/)
})

test('diff scope audit summary keeps category counts without dumping every file', () => {
  const result = runAudit([
    '--summary-json',
    '--changed-file', 'pages/news/news.wxml',
    '--changed-file', 'docs/design/example.md'
  ])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'diff_scope_blocked_page_integration_present')
  assert.equal(report.categoryCounts.pageIntegration, 1)
  assert.equal(report.categoryCounts.evidenceOrTooling, 1)
  assert.equal(report.blockedPageIntegrationFileCount, 1)
  assert.equal(report.categories, undefined)
  assert.ok(report.blockedPageIntegrationFiles.includes('pages/news/news.wxml'))
})

test('diff scope audit artifact records current quarantined page scope', () => {
  const source = read(auditDocPath)
  const manifest = readJson(auditManifestPath)
  const readme = read(auditReadmePath)

  assert.match(source, /^Status: `diff_scope_blocked_page_integration_present`$/m)
  assert.match(source, /blockedPageIntegrationFileCount=44/)
  assert.match(source, /pageScopeBlocked=true/)
  assert.match(source, /`pages\/builds\/workbench\.wxml`/)
  assert.match(source, /`project\.config\.json`/)
  assert.match(source, /quarantine page\/app\/navigation changes/)

  assert.equal(manifest.status, 'diff_scope_blocked_page_integration_present')
  assert.equal(manifest.auditScript, 'scripts/ui-system-diff-scope-audit.js')
  assert.equal(manifest.activationAllowed, false)
  assert.equal(manifest.pageIntegrationAllowed, false)
  assert.equal(manifest.blockedPageIntegrationFileCount, 44)
  assert.equal(manifest.pageScopeBlocked, true)
  assert.equal(manifest.devtoolsScopeRisk, true)
  assert.equal(manifest.categoryCounts.pageIntegration, 39)
  assert.equal(manifest.categoryCounts.componentOwnerWork, 108)
  assert.ok(manifest.blockedPageIntegrationFiles.includes('pages/news/news.wxml'))
  assert.ok(manifest.blockedPageIntegrationFiles.includes('pages/builds/workbench.wxml'))
  assert.ok(manifest.devtoolsTouchRiskFiles.includes('project.config.json'))
  assert.ok(manifest.nonPromotion.includes('not active_implementation_permit'))

  assert.match(readme, /pageScopeBlocked: true/)
})
