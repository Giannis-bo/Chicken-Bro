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

test('current UI delivery contract replaces historical pass artifacts with committed 09:00 evidence', () => {
  const roadmap = read('docs/roadmap.md')
  const handoff = read('docs/plans/2026-07-08-codex-goal-mode-ui-delivery-handoff.md')
  const entryContract = read('docs/plans/2026-07-08-ui-goal-mode-entry-contract.md')
  const sourceOfTruth = read('docs/plans/2026-07-08-current-ui-delivery-source-of-truth.md')
  const manifest = readJson(`${artifactRoot}/manifest.json`)

  assert.match(roadmap, /09:00 UI delivery rescue/)
  assert.match(handoff, /not a pass36\/pass37 continuation|不是.*pass36\/pass37/)
  assert.match(entryContract, /pass36\/pass37 patching|旧 UI 系统重建、pass36\/pass37/)
  assert.match(sourceOfTruth, /pass36\/pass37 continuation|不是继续旧 UI 系统重建、pass36\/pass37/)
  assert.equal(manifest.scope, 'all_app_json_pages')
  assert.equal(manifest.runtimeVerified, true)
  assert.equal(manifest.finalAccepted, true)
})

test('current final delivery audit preserves complete accepted runtime proof', () => {
  const audit = readJson(`${artifactRoot}/final-delivery-audit.json`)

  assert.equal(audit.rescueDeliveryReady, true)
  assert.equal(audit.finalAccepted, true)
  assert.match(audit.finalAcceptanceSource, /future_ui_adjustments_as_separate_requests/)
  assert.equal(audit.currentRuntimeBlocker.type, 'none_runtime_evidence_complete')
  assert.deepEqual(audit.devtoolsDiscipline.prohibitedActionsUsed, [])
  assert.equal(audit.totals.currentRuntimeScreenshotCount, 14)
  assert.equal(audit.totals.currentRuntimePassCount, 14)
  assert.equal(audit.totals.riskCount, 0)
  assert.match(audit.staticEvidence.meaning, /does not prove UI correctness/)
  const screenshotsByPage = Object.fromEntries(audit.automatedRuntimeEvidence.items.map((item) => [item.path, item.screenshot]))
  assert.match(screenshotsByPage['pages/news/news'], /news_news_auto_20260709T031806Z\.png/)
  assert.match(screenshotsByPage['pages/news/list'], /news_list_auto_20260709T053302Z\.png/)
  assert.match(screenshotsByPage['pages/news/detail'], /news_detail_auto_20260709T053334Z\.png/)
  assert.match(screenshotsByPage['pages/builds/workbench'], /builds_workbench_auto_20260709T051629Z\.png/)
  assert.match(screenshotsByPage['pages/builds/builds'], /builds_builds_auto_20260709T051856Z\.png/)
  assert.match(screenshotsByPage['pages/builds/intel'], /builds_intel_auto_20260709T053348Z\.png/)
  assert.match(screenshotsByPage['pages/builds/talent-simulator'], /builds_talent-simulator_auto_20260709T052151Z\.png/)
  assert.match(screenshotsByPage['pages/builds/detail'], /builds_detail_auto_20260709T060642Z\.png/)
  assert.match(screenshotsByPage['pages/simulator/simulator'], /simulator_simulator_auto_20260709T052530Z\.png/)
  assert.match(screenshotsByPage['pages/simulator/simc'], /simulator_simc_auto_20260709T052916Z\.png/)
  assert.match(screenshotsByPage['pages/simulator/chickenbro'], /simulator_chickenbro_auto_20260709T053404Z\.png/)
  assert.match(screenshotsByPage['pages/simulator/tasks'], /simulator_tasks_auto_20260709T053422Z\.png/)
  assert.match(screenshotsByPage['pages/simulator/task-detail'], /simulator_task-detail_auto_20260709T060703Z\.png/)
  assert.match(screenshotsByPage['pages/profile/profile'], /profile_profile_auto_20260709T053114Z\.png/)
  assert.equal(audit.pages.find((page) => page.path === 'pages/builds/detail').status, 'auto_route_and_screenshot_passed_visual_pass')
  assert.equal(audit.pages.find((page) => page.path === 'pages/simulator/simulator').status, 'auto_route_and_screenshot_passed_visual_pass')
  assert.equal(audit.pages.find((page) => page.path === 'pages/simulator/simc').status, 'auto_route_and_screenshot_passed_visual_pass')
  assert.equal(audit.pages.find((page) => page.path === 'pages/profile/profile').status, 'auto_route_and_screenshot_passed_visual_pass')
  assert.equal(audit.pages.find((page) => page.path === 'pages/simulator/task-detail').status, 'auto_route_and_screenshot_passed_visual_pass')
  assert.deepEqual(audit.runtimeRiskEvidence, [])
})

test('static route and package-size evidence are committed under the current manifest', () => {
  const manifest = readJson(`${artifactRoot}/manifest.json`)
  const audit = readJson(`${artifactRoot}/final-delivery-audit.json`)
  const routeAudit = readJson(`${artifactRoot}/static-route-contract-audit.json`)

  assert.equal(routeAudit.status, 'static_route_contract_passed')
  assert.match(manifest.staticEvidence.staticRouteContract, /static-route-contract-audit\.json status=static_route_contract_passed/)
  assert.equal(audit.staticEvidence.packageSize.errorBefore, 'source size 4647KB exceed max limit 2MB')
  assert.ok(audit.staticEvidence.packageSize.estimatedAfterKb < 2048)
  assert.match(audit.staticEvidence.packageSize.strategy, /exclude assets\/generated\/\*\*/)
})

test('runtime source no longer depends on generated tab icon slices or historical pass class names', () => {
  const runtimeSources = [
    'app.wxss',
    'pages/news/news.wxml',
    'pages/news/news.js',
    'components/channel-dock/channel-dock.wxml',
    'components/ranked-feed/ranked-feed.wxml',
    'custom-tab-bar/index.wxml',
    'custom-tab-bar/index.js'
  ].map(read).join('\n')

  assert.doesNotMatch(runtimeSources, /news_tab_icon_(?:all|official|update|event|community|guide)_pass36/)
  assert.doesNotMatch(runtimeSources, /NEWS_TAB_ICON_BY_KEY/)
  assert.doesNotMatch(runtimeSources, /pass3[0-9]|pass36|pass37/)
  assert.match(runtimeSources, /assets\/tabbar\/news-selected\.png/)
  assert.match(runtimeSources, /assets\/user\/intel-command-icon\.png/)
})
