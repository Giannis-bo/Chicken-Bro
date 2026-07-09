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

test('roadmap and current UI handoff make 09:00 rescue the active control surface', () => {
  const roadmap = read('docs/roadmap.md')
  const handoff = read('docs/plans/2026-07-08-codex-goal-mode-ui-delivery-handoff.md')
  const entryContract = read('docs/plans/2026-07-08-ui-goal-mode-entry-contract.md')
  const sourceOfTruth = read('docs/plans/2026-07-08-current-ui-delivery-source-of-truth.md')

  assert.match(roadmap, /Codex goal-mode UI delivery handoff/)
  assert.match(roadmap, /UI goal-mode entry contract/)
  assert.match(roadmap, /current UI delivery source of truth/)
  assert.match(roadmap, /09:00 UI delivery rescue/)
  assert.match(handoff, /every page currently registered in `app\.json`/)
  assert.match(entryContract, /current real WeChat evidence|real WeChat screenshot evidence|route\/action record/)
  assert.match(sourceOfTruth, /14 页 proof matrix/)
  assert.match(`${handoff}\n${entryContract}\n${sourceOfTruth}`, /pass36\/pass37/)
  assert.match(`${handoff}\n${entryContract}\n${sourceOfTruth}`, /not a pass36\/pass37 continuation|pass36\/pass37 patching|不是.*pass36\/pass37/)
})

test('current delivery manifest covers exactly the registered app pages', () => {
  const appConfig = readJson('app.json')
  const audit = readJson(`${artifactRoot}/final-delivery-audit.json`)
  const pagePaths = audit.pages.map((page) => page.path)

  assert.equal(audit.scope, 'all_app_json_pages')
  assert.equal(audit.totals.pageCount, 14)
  assert.equal(audit.totals.p0Count, 8)
  assert.equal(audit.totals.p1Count, 5)
  assert.equal(audit.totals.p2Count, 1)
  assert.deepEqual(pagePaths, appConfig.pages)
})

test('current delivery evidence marks runtime proof complete and user accepted as baseline', () => {
  const manifest = readJson(`${artifactRoot}/manifest.json`)
  const audit = readJson(`${artifactRoot}/final-delivery-audit.json`)
  const ledger = readJson(`${artifactRoot}/devtools-action-ledger.json`)

  assert.equal(manifest.runtimeVerified, true)
  assert.equal(manifest.finalAccepted, true)
  assert.equal(audit.runtimeVerified, true)
  assert.equal(audit.finalAccepted, true)
  assert.match(audit.finalAcceptanceSource, /future_ui_adjustments_as_separate_requests/)
  assert.equal(audit.rescueDeliveryReady, true)
  assert.equal(audit.currentRuntimeBlocker.type, 'none_runtime_evidence_complete')
  assert.deepEqual(audit.currentRuntimeBlocker.forbiddenActionsUsed, [])
  assert.equal(ledger.captureSafe, true)
  assert.deepEqual(ledger.forbiddenActionCheck.prohibitedActionsUsed, [])
  assert.ok(Array.isArray(ledger.routeActionList))
  assert.equal(audit.totals.currentRuntimeScreenshotCount, 14)
  assert.equal(audit.totals.currentRuntimePassCount, 14)
  assert.equal(audit.totals.riskCount, 0)
  assert.equal(audit.automatedRuntimeEvidence.count, 14)
  assert.equal(audit.pages.find((page) => page.path === 'pages/news/news').status, 'auto_route_and_screenshot_passed_visual_pass')
  assert.equal(audit.pages.find((page) => page.path === 'pages/news/list').status, 'auto_route_and_screenshot_passed_visual_pass')
  assert.equal(audit.pages.find((page) => page.path === 'pages/news/detail').status, 'auto_route_and_screenshot_passed_visual_pass')
  assert.equal(audit.pages.find((page) => page.path === 'pages/builds/builds').status, 'auto_route_and_screenshot_passed_visual_pass')
  assert.equal(audit.pages.find((page) => page.path === 'pages/builds/workbench').status, 'auto_route_and_screenshot_passed_visual_pass')
  assert.equal(audit.pages.find((page) => page.path === 'pages/builds/intel').status, 'auto_route_and_screenshot_passed_visual_pass')
  assert.equal(audit.pages.find((page) => page.path === 'pages/builds/talent-simulator').status, 'auto_route_and_screenshot_passed_visual_pass')
  assert.equal(audit.pages.find((page) => page.path === 'pages/builds/detail').status, 'auto_route_and_screenshot_passed_visual_pass')
  assert.equal(audit.pages.find((page) => page.path === 'pages/simulator/simulator').status, 'auto_route_and_screenshot_passed_visual_pass')
  assert.equal(audit.pages.find((page) => page.path === 'pages/simulator/simc').status, 'auto_route_and_screenshot_passed_visual_pass')
  assert.equal(audit.pages.find((page) => page.path === 'pages/simulator/chickenbro').status, 'auto_route_and_screenshot_passed_visual_pass')
  assert.equal(audit.pages.find((page) => page.path === 'pages/simulator/tasks').status, 'auto_route_and_screenshot_passed_visual_pass')
  assert.equal(audit.pages.find((page) => page.path === 'pages/simulator/task-detail').status, 'auto_route_and_screenshot_passed_visual_pass')
  assert.equal(audit.pages.find((page) => page.path === 'pages/profile/profile').status, 'auto_route_and_screenshot_passed_visual_pass')
  const screenshotsByPage = Object.fromEntries(audit.automatedRuntimeEvidence.items.map((item) => [item.path, item.screenshot]))
  assert.match(screenshotsByPage['pages/builds/detail'], /builds_detail_auto_20260709T060642Z\.png/)
  assert.match(screenshotsByPage['pages/simulator/task-detail'], /simulator_task-detail_auto_20260709T060703Z\.png/)
  assert.deepEqual(audit.runtimeRiskEvidence, [])
})

test('foundation and current rescue source files do not carry historical pass class names', () => {
  const sourceFiles = [
    'app.wxss',
    'components/app-shell/app-shell.wxml',
    'components/page-frame/page-frame.wxml',
    'components/wow-panel/wow-panel.wxml',
    'components/material-image/material-image.wxml',
    'components/game-object-icon/game-object-icon.wxml',
    'components/status-visual/status-visual.wxml',
    'components/action-button/action-button.wxml',
    'components/module-card/module-card.wxml',
    'components/channel-dock/channel-dock.wxml',
    'components/ranked-feed/ranked-feed.wxml',
    'components/evidence-ledger/evidence-ledger.wxml',
    'components/chat-shell/chat-shell.wxml',
    'pages/news/news.wxml',
    'custom-tab-bar/index.wxml'
  ].map(read).join('\n')

  assert.doesNotMatch(sourceFiles, /pass3[0-9]|pass36|pass37/)
  assert.match(sourceFiles, /news-page-frame/)
  assert.match(sourceFiles, /news-module-dock/)
  assert.match(sourceFiles, /news-module-card/)
  assert.match(sourceFiles, /news-panel/)
})

test('current package-size fix keeps runtime assets committed and generated assets excluded', () => {
  const projectConfig = readJson('project.config.json')
  const ignored = new Set((projectConfig.packOptions?.ignore || []).map((entry) => `${entry.type}:${entry.value}`))
  const audit = readJson(`${artifactRoot}/final-delivery-audit.json`)

  assert.ok(ignored.has('glob:assets/generated/**'))
  assert.ok(ignored.has('glob:artifacts/**'))
  assert.ok(ignored.has('glob:scripts/**'))
  assert.ok(audit.staticEvidence.packageSize.estimatedAfterKb < 2048)

  for (const runtimeAsset of [
    'assets/tabbar/news.png',
    'assets/tabbar/news-selected.png',
    'assets/tabbar/builds.png',
    'assets/tabbar/builds-selected.png',
    'assets/tabbar/simulator.png',
    'assets/tabbar/simulator-selected.png',
    'assets/tabbar/profile.png',
    'assets/tabbar/profile-selected.png',
    'assets/user/intel-command-icon.png'
  ]) {
    assert.ok(fs.existsSync(runtimeAsset), `${runtimeAsset} should remain committed runtime source`)
  }
})
