const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

function read(file) {
  return fs.readFileSync(file, 'utf8')
}

function readJson(file) {
  return JSON.parse(read(file))
}

const artifactRoot = 'artifacts/ui-system-rebuild/20260708-0900-runtime-screenshot-manifest'

test('current endpoint probe is read-only and does not mutate WeChat DevTools state', () => {
  const source = read(`${artifactRoot}/automator-endpoint-probe.js`)
  const manifest = readJson(`${artifactRoot}/automator-endpoint-probe.json`)

  assert.match(source, /listeningWechatPorts/)
  assert.match(source, /probePort/)
  assert.match(source, /Tool\.getInfo/)
  assert.match(source, /does not close, restart, clear cache, switch appid, switch project, navigate, or capture screenshots/)
  assert.deepEqual(manifest.forbiddenActionsUsed, [])
  assert.equal(manifest.captureScreenshotUsed, false)
  assert.equal(manifest.navigationUsed, false)
  assert.equal(manifest.cliAutoUsed, false)
})

test('current page capture harness refuses risky batch capture by default', () => {
  const source = read(`${artifactRoot}/capture-0900-pages.js`)

  assert.match(source, /WOW_0900_CAPTURE_PAGES/)
  assert.match(source, /WOW_0900_ALLOW_BATCH/)
  assert.match(source, /Refusing to run a full 14-page serial capture by default/)
  assert.match(source, /Use WOW_0900_CAPTURE_PAGES=<page> for a safe single-page capture/)
  assert.match(source, /switchTab/)
  assert.match(source, /navigateTo/)
  assert.match(source, /redirectTo/)
  assert.match(source, /currentState/)
  assert.match(source, /waitForPageReady/)
})

test('P0 route smoke requires explicit opt-in and stays route-only', () => {
  const source = read(`${artifactRoot}/p0-route-smoke.js`)

  assert.match(source, /WOW_0900_RUN_P0_ROUTE_SMOKE/)
  assert.match(source, /Refusing to run P0 route smoke without explicit opt-in/)
  assert.match(source, /does not close, restart, clear cache, switch appid, or capture screenshots/)
  assert.match(source, /const p0Routes = \[/)
  assert.match(source, /const primaryActions = \[/)
  assert.doesNotMatch(source, /\.screenshot\(/)
})

test('current runtime manifest tracks all app routes with accepted final baseline', () => {
  const appConfig = readJson('app.json')
  const manifest = readJson(`${artifactRoot}/manifest.json`)
  const finalAudit = readJson(`${artifactRoot}/final-delivery-audit.json`)
  const manifestPaths = finalAudit.pages.map((page) => page.path)

  assert.equal(manifest.runtimeVerified, true)
  assert.equal(manifest.finalAccepted, true)
  assert.equal(finalAudit.runtimeVerified, true)
  assert.equal(finalAudit.finalAccepted, true)
  assert.match(finalAudit.finalAcceptanceSource, /future_ui_adjustments_as_separate_requests/)
  assert.equal(finalAudit.totals.currentRuntimeScreenshotCount, appConfig.pages.length)
  assert.equal(finalAudit.totals.riskCount, 0)
  assert.equal(finalAudit.totals.pageCount, appConfig.pages.length)
  assert.deepEqual(manifestPaths, appConfig.pages)
})
