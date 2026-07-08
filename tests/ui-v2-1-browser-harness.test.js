const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const {
  buildBrowserHarness,
  writeBrowserHarness,
  renderActualCssComponentHarness
} = require('../artifacts/ui-v2-1-strict-restoration/create-pass36-browser-harness')
const {
  buildBrowserLayoutAuditPlan
} = require('../artifacts/ui-v2-1-strict-restoration/audit-pass36-browser-layout')
const {
  buildBrowserSceneMatrixPlan,
  renderBrowserSceneMatrixHtml
} = require('../artifacts/ui-v2-1-strict-restoration/audit-pass36-browser-scene-matrix')

test('pass36 browser harness is a staging-only visual aid and not final runtime evidence', () => {
  const harness = buildBrowserHarness({ render: false })

  assert.equal(harness.devtoolsTouched, false)
  assert.equal(harness.runtimeScreenshot, false)
  assert.equal(harness.browserHarness, true)
  assert.equal(harness.strictGateEligible, false)
  assert.match(harness.html.board, /wow-pass36-browser-harness/)
  assert.match(harness.html.actualCssComponents, /pass36q-browser-actual-css-components\.html/)
  assert.deepEqual(harness.sourceEvidence.realWxssInputs, [
    'app.wxss',
    'pages/news/news.wxss',
    'pages/news/news.wxml',
    'components/channel-dock/channel-dock.wxss',
    'components/channel-dock/channel-dock.wxml',
    'components/ranked-feed/ranked-feed.wxss',
    'components/ranked-feed/ranked-feed.wxml',
    'pages/builds/builds.wxss',
    'pages/builds/builds.wxml',
    'pages/builds/workbench.wxss',
    'pages/builds/workbench.wxml',
    'components/status-badge/status-badge.wxss',
    'components/status-badge/status-badge.wxml'
  ])
  assert.deepEqual(Object.keys(harness.sourceEvidence.componentTargetImages), [
    'buildsSpecConsole',
    'buildsWorkbenchPanel',
    'buildsWorkflowTimeline',
    'workbenchIdentityPanel',
    'workbenchVerdictSlab',
    'workbenchModuleDock',
    'workbenchEvidenceLedger'
  ])
  assert.match(harness.note, /does not launch, close, log into, probe, or capture WeChat DevTools/)
})

test('pass36 browser harness visible HTML avoids duplicated system chrome and strong false pass claims', () => {
  const harness = buildBrowserHarness({ render: false })
  const html = `${harness.documents.boardHtml}\n${harness.documents.componentHtml}\n${harness.documents.actualCssComponentHtml}`

  assert.doesNotMatch(html, /battery|wifi|wi-fi|wifo|电量|9:41|22:43|模拟状态栏|假状态栏/i)
  assert.doesNotMatch(html, /class="phone"|class="nav"|actual-phone/)
  assert.doesNotMatch(html, /comparison-main-target-current-pass36l/)
  assert.doesNotMatch(html, /strictGateEligible:\s*true|严格门禁通过|最终验收通过/)
  assert.doesNotMatch(html, /\d+(?:\.\d+)?万阅读|87\s*\/\s*100/)
  assert.match(html, /浏览器快速视觉事实/)
  assert.match(html, /不替代微信开发者工具最终验收/)
  assert.match(html, /captureSafe=false/)
  assert.match(html, /频道 dock/)
  assert.match(html, /今日重点/)
})

test('pass36 actual CSS component harness consumes real news WXSS classes', () => {
  const html = renderActualCssComponentHarness()
  const source = fs.readFileSync('artifacts/ui-v2-1-strict-restoration/create-pass36-browser-harness.js', 'utf8')

  assert.match(source, /readFileSync\(path\.join\(repoRoot, 'app\.wxss'\)/)
  assert.match(source, /readFileSync\(path\.join\(repoRoot, 'pages\/news\/news\.wxss'\)/)
  assert.match(source, /readFileSync\(path\.join\(repoRoot, 'components\/channel-dock\/channel-dock\.wxss'\)/)
  assert.match(source, /readFileSync\(path\.join\(repoRoot, 'components\/ranked-feed\/ranked-feed\.wxss'\)/)
  assert.match(source, /readFileSync\(path\.join\(repoRoot, 'pages\/builds\/builds\.wxss'\)/)
  assert.match(source, /readFileSync\(path\.join\(repoRoot, 'pages\/builds\/workbench\.wxss'\)/)
  assert.match(source, /convertRpxToPx/)
  assert.match(html, /真实 WXSS 组件预检/)
  assert.match(html, /chrome-free target crops/)
  assert.match(html, /builds-target-spec_console\.png/)
  assert.match(html, /builds-target-workbench_panel\.png/)
  assert.match(html, /builds-target-workflow_timeline\.png/)
  assert.match(html, /workbench-target-identity_panel\.png/)
  assert.match(html, /workbench-target-verdict_slab\.png/)
  assert.match(html, /workbench-target-module_dock\.png/)
  assert.match(html, /workbench-target-evidence_ledger\.png/)
  assert.doesNotMatch(html, /comparison-main-target-current-pass36l/)
  assert.match(html, /news-tab-dock/)
  assert.match(html, /surface-material channel-dock-material/)
  assert.match(html, /news-tab-item pass37-module-card is-active visual-tone-official/)
  assert.match(html, /ranked-feed-root/)
  assert.match(html, /focus-row pass37-module-card visual-tone-update state-published thumb-fallback_thumb/)
  assert.match(html, /focus-thumb-fallback-image/)
  assert.doesNotMatch(html, /visual-source-badge|BN<\/text>|WH<\/text>|SRC<\/text>/)
  assert.match(html, /builds-spec-console/)
  assert.match(html, /workbench-entry/)
  assert.match(html, /workbench-cockpit/)
  assert.match(html, /verdict-slab/)
  assert.match(html, /module-card-grid/)
  assert.match(html, /evidence-row/)
  assert.match(html, /不触碰微信开发者工具/)
  assert.doesNotMatch(html, /wx:for|wx:if|bindtap|catchtap/)
})

test('pass36 browser harness can write manifest without rendering Chrome', () => {
  const root = fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'pass36-browser-harness-test-'))
  const previousMode = process.env.WOW_PASS36_BROWSER_HARNESS_OUTPUT_MODE
  const previousRoot = process.env.WOW_PASS36_BROWSER_HARNESS_OUTPUT_ROOT
  process.env.WOW_PASS36_BROWSER_HARNESS_OUTPUT_MODE = 'staging'
  process.env.WOW_PASS36_BROWSER_HARNESS_OUTPUT_ROOT = root

  try {
    const result = writeBrowserHarness({ render: false })
    assert.equal(result.manifest.devtoolsTouched, false)
    assert.equal(result.manifest.runtimeScreenshot, false)
    assert.equal(result.manifest.strictGateEligible, false)
    assert.equal(result.manifest.screenshots.board.status, 'skipped')
    assert.equal(result.manifest.screenshots.actualCssComponents.status, 'skipped')
    assert.ok(fs.existsSync(result.manifestPath))
    assert.ok(fs.existsSync(path.join(path.dirname(result.manifestPath), 'pass36q-browser-harness.html')))
    assert.ok(fs.existsSync(path.join(path.dirname(result.manifestPath), 'pass36q-browser-components.html')))
    assert.ok(fs.existsSync(path.join(path.dirname(result.manifestPath), 'pass36q-browser-actual-css-components.html')))
  } finally {
    if (previousMode === undefined) delete process.env.WOW_PASS36_BROWSER_HARNESS_OUTPUT_MODE
    else process.env.WOW_PASS36_BROWSER_HARNESS_OUTPUT_MODE = previousMode
    if (previousRoot === undefined) delete process.env.WOW_PASS36_BROWSER_HARNESS_OUTPUT_ROOT
    else process.env.WOW_PASS36_BROWSER_HARNESS_OUTPUT_ROOT = previousRoot
    fs.rmSync(root, { recursive: true, force: true })
  }
})

test('pass36 browser harness treats a written PNG as browser evidence even if Chrome cleanup stalls', () => {
  const source = fs.readFileSync('artifacts/ui-v2-1-strict-restoration/create-pass36-browser-harness.js', 'utf8')

  assert.match(source, /captured_after_timeout/)
  assert.match(source, /fs\.existsSync\(pngPath\) && fs\.statSync\(pngPath\)\.size > 0/)
  assert.match(source, /not strict mini-program evidence/)
  assert.match(source, /--disable-background-networking/)
  assert.match(source, /--disable-component-update/)
})

test('pass36 browser layout audit checks DOM rects without becoming runtime evidence', () => {
  const plan = buildBrowserLayoutAuditPlan()
  const source = fs.readFileSync('artifacts/ui-v2-1-strict-restoration/audit-pass36-browser-layout.js', 'utf8')

  assert.equal(plan.devtoolsTouched, false)
  assert.equal(plan.runtimeScreenshot, false)
  assert.equal(plan.browserHarness, true)
  assert.equal(plan.strictGateEligible, false)
  assert.match(plan.forbiddenVisibleChromePattern, /battery/)
  assert.match(plan.forbiddenVisibleChromePattern, /假状态栏/)
  assert.match(source, /getBoundingClientRect/)
  assert.match(source, /scrollWidth - element\.clientWidth/)
  assert.match(source, /childrenWithin/)
  assert.match(source, /Final pass36 scorecard still requires fresh WeChat mini-program screenshots/)

  const ruleIds = plan.rules.map((rule) => rule.id)
  assert.deepEqual(ruleIds, [
    'mini_program_frames_keep_390px_width',
    'news_channel_dock_has_six_safe_tabs',
    'news_ranked_focus_list_has_five_safe_rows',
    'news_ranked_focus_rows_keep_target_density',
    'builds_components_stay_inside_mobile_frame',
    'workbench_components_stay_inside_mobile_frame',
    'workbench_control_strip_children_do_not_escape'
  ])
  assert.equal(
    plan.rules.find((rule) => rule.id === 'mini_program_frames_keep_390px_width').minCount,
    4
  )
  assert.deepEqual(
    plan.rules.find((rule) => rule.id === 'news_channel_dock_has_six_safe_tabs').childCounts,
    [{ selector: '.news-tab-item', count: 6 }]
  )
  assert.deepEqual(
    plan.rules.find((rule) => rule.id === 'news_ranked_focus_list_has_five_safe_rows').childCounts,
    [{ selector: '.focus-row', count: 5 }]
  )
  assert.ok(
    plan.rules.find((rule) => rule.id === 'workbench_components_stay_inside_mobile_frame').childCounts
      .some((item) => item.selector === '.module-card' && item.count === 4)
  )
})

test('pass36 browser scene matrix preflights every runtime scene without becoming acceptance evidence', () => {
  const plan = buildBrowserSceneMatrixPlan()
  const html = renderBrowserSceneMatrixHtml(plan, 'compact')
  const source = fs.readFileSync('artifacts/ui-v2-1-strict-restoration/audit-pass36-browser-scene-matrix.js', 'utf8')

  assert.equal(plan.devtoolsTouched, false)
  assert.equal(plan.runtimeScreenshot, false)
  assert.equal(plan.browserHarness, true)
  assert.equal(plan.strictGateEligible, false)
  assert.equal(plan.sceneCount, 27)
  assert.equal(plan.scenes.length, 27)
  assert.equal(plan.scenes.filter((scene) => scene.viewportId === 'compact').length, 9)
  assert.equal(plan.scenes.filter((scene) => scene.viewportId === 'standard').length, 9)
  assert.equal(plan.scenes.filter((scene) => scene.viewportId === 'large').length, 9)
  assert.deepEqual(Array.from(new Set(plan.scenes.map((scene) => scene.screen))), [
    'news_home_top',
    'news_home_scrolled',
    'builds_tab',
    'workbench_first_screen',
    'workbench_evidence_expanded',
    'workbench_blocked',
    'workbench_partial',
    'workbench_stale',
    'workbench_ready'
  ])
  assert.match(html, /pass36v 浏览器全场景预检矩阵/)
  assert.match(html, /data-scene="news_home_top"/)
  assert.match(html, /data-scene="workbench_ready"/)
  assert.match(html, /news-command/)
  assert.match(html, /news-tab-dock/)
  assert.match(html, /focus-row/)
  assert.match(html, /builds-spec-console/)
  assert.match(html, /workbench-cockpit/)
  assert.match(html, /readiness-panel/)
  assert.match(html, /不是最终验收/)
  assert.doesNotMatch(html, /battery|wifi|wi-fi|wifo|电量|9:41|22:43|模拟状态栏|假状态栏/i)
  assert.doesNotMatch(html, /综合评分|S 级|A级|提升优先级/)

  assert.match(source, /buildRuntimeCaptureContract/)
  assert.match(source, /renderActualNewsCss\(width\)/)
  assert.match(source, /viewport\.innerText/)
  assert.match(source, /sceneCount: scenes\.length/)
  assert.match(source, /pass36v-browser-scene-matrix-\$\{viewportId\}\.html/)
  assert.match(source, /fullPage: true/)
  assert.match(source, /Final pass36 acceptance still requires fresh WeChat DevTools screenshots/)
})
