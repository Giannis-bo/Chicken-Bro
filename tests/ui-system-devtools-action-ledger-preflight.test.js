const test = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const preflightScript = 'scripts/ui-system-devtools-action-ledger-preflight.js'
const templatePath = 'docs/design/2026-07-07-wow-ui-system-devtools-action-ledger-template.md'
const manifestPath = 'artifacts/ui-system-rebuild/20260707-devtools-action-ledger-template/manifest.json'
const readmePath = 'artifacts/ui-system-rebuild/20260707-devtools-action-ledger-template/README.md'

function runPreflight(args = []) {
  return spawnSync(process.execPath, [preflightScript, ...args], {
    encoding: 'utf8'
  })
}

function read(filePath) {
  return fs.readFileSync(filePath, 'utf8')
}

function readJson(filePath) {
  return JSON.parse(read(filePath))
}

function makeLedger(source) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-devtools-ledger-'))
  const file = path.join(directory, 'devtools-action-ledger.json')
  fs.writeFileSync(file, JSON.stringify(source, null, 2))
  return file
}

function validLedger() {
  return {
    status: 'devtools_action_ledger_capture_safe',
    captureSafe: true,
    checkedAt: '2026-07-07T00:00:00.000Z',
    captureRunner: 'artifacts/ui-system-rebuild/runtime/capture-runner.js',
    devtools: {
      appPath: '/Applications/wechatwebdevtools.app',
      port: 12345,
      appidState: 'existing_authorized_project'
    },
    forbiddenActionCheck: {
      status: 'pass',
      prohibitedActionsUsed: []
    },
    sceneList: ['news_home_top'],
    failedScenes: [],
    screenshotPathList: ['screenshots/news_home_top.png'],
    routeActionList: [
      {
        scene: 'news_home_top',
        action: 'switchTab',
        route: '/pages/news/news'
      }
    ],
    loginStateIncidentNote: 'none'
  }
}

test('DevTools action ledger preflight reports missing runtime ledger by default', () => {
  const result = runPreflight(['--require-ledger', '--json'])

  assert.equal(result.status, 9)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'devtools_action_ledger_missing')
  assert.equal(report.ledgerExists, false)
  assert.equal(report.runtimeCaptureEvidenceReady, false)
  assert.ok(report.missingRequirements.includes('devtools_action_ledger_file'))
  assert.ok(report.requiredFields.includes('loginStateIncidentNote'))
})

test('DevTools action ledger preflight accepts a capture-safe candidate ledger', () => {
  const ledgerPath = makeLedger(validLedger())
  const result = runPreflight(['--ledger-file', ledgerPath, '--require-ledger', '--json'])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'devtools_action_ledger_ready')
  assert.equal(report.ledgerExists, true)
  assert.equal(report.runtimeCaptureEvidenceReady, true)
  assert.equal(report.captureSafe, true)
  assert.equal(report.sceneCount, 1)
  assert.equal(report.screenshotCount, 1)
  assert.equal(report.routeActionCount, 1)
  assert.deepEqual(report.missingRequirements, [])
})

test('DevTools action ledger preflight rejects forbidden actions and unsafe capture', () => {
  const ledger = validLedger()
  ledger.captureSafe = false
  ledger.forbiddenActionCheck.prohibitedActionsUsed = ['cli close']
  ledger.routeActionList.push({
    scene: 'bad',
    action: 'cli open',
    route: '/pages/news/news'
  })
  const ledgerPath = makeLedger(ledger)
  const result = runPreflight(['--ledger-file', ledgerPath, '--require-ledger', '--json'])

  assert.equal(result.status, 9)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'devtools_action_ledger_invalid')
  assert.equal(report.runtimeCaptureEvidenceReady, false)
  assert.ok(report.missingRequirements.includes('captureSafe_true'))
  assert.ok(report.missingRequirements.includes('forbiddenActionCheck.prohibitedActionsUsed_empty'))
  assert.ok(report.missingRequirements.includes('forbidden_actions_detected'))
  assert.ok(report.forbiddenActionsDetected.includes('cli close'))
})

test('DevTools action ledger template remains template-only and non-runtime', () => {
  const source = read(templatePath)
  const manifest = readJson(manifestPath)
  const readme = read(readmePath)

  assert.match(source, /^Status: `devtools_action_ledger_template_only`$/m)
  assert.match(source, /node scripts\/ui-system-devtools-action-ledger-preflight\.js --require-ledger --json/)
  assert.match(source, /Current expected exit code without a real runtime ledger: `9`/)
  assert.match(source, /"captureSafe": true/)
  assert.match(source, /loginStateIncidentNote/)
  assert.match(source, /DevTools touched by this template: false/)
  assert.match(source, /It cannot prove `runtime_verified`, `final_accepted`, visual acceptance, target lock, active permit, or page integration/)

  assert.equal(manifest.status, 'devtools_action_ledger_template_only')
  assert.equal(manifest.preflightScript, preflightScript)
  assert.equal(manifest.runtimeLedgerExists, false)
  assert.equal(manifest.captureSafeProven, false)
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.expectedRequireLedgerExitCode, 9)
  assert.ok(manifest.requiredFields.includes('routeActionList'))
  assert.ok(manifest.forbiddenActions.includes('cli close'))
  assert.ok(manifest.nonPromotion.includes('not runtime_verified'))

  assert.match(readme, /captureSafeProven: false/)
})
