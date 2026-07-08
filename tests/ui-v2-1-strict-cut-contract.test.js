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
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.finalAccepted, false)
})

test('current final delivery audit preserves risk status instead of promoting static proof', () => {
  const audit = readJson(`${artifactRoot}/final-delivery-audit.json`)

  assert.equal(audit.rescueDeliveryReady, false)
  assert.equal(audit.currentRuntimeBlocker.type, 'wechat_devtools_no_ready_automator_endpoint')
  assert.deepEqual(audit.devtoolsDiscipline.prohibitedActionsUsed, [])
  assert.equal(audit.totals.currentRuntimeScreenshotCount, 0)
  assert.equal(audit.totals.currentRuntimePassCount, 0)
  assert.equal(audit.totals.riskCount, audit.totals.pageCount)
  assert.match(audit.staticEvidence.meaning, /does not prove UI correctness/)
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
