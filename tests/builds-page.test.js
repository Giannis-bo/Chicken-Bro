const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const { buildSpecializationHomePayload } = require('../server/builds/home-payload')

test('builds tab is renamed to specialization and removes legacy metrics row', () => {
  const app = JSON.parse(fs.readFileSync('app.json', 'utf8'))
  const tab = app.tabBar.list.find((item) => item.pagePath === 'pages/builds/builds')
  const wxml = fs.readFileSync('pages/builds/builds.wxml', 'utf8')

  assert.equal(tab.text, '职业专精')
  assert.doesNotMatch(wxml, /class="metrics"/)
  assert.doesNotMatch(wxml, /metric-card/)
})

test('builds page focuses on four query entries that navigate to detail pages', () => {
  const js = fs.readFileSync('pages/builds/builds.js', 'utf8')
  const wxml = fs.readFileSync('pages/builds/builds.wxml', 'utf8')
  const payload = buildSpecializationHomePayload()

  assert.deepEqual(
    payload.quickActions.map((item) => item.title),
    ['天赋构筑', '装备获取', '属性权重', '输出循环']
  )
  assert.match(wxml, /bindtap="openQueryPage"/)
  assert.match(js, /openQueryPage\(event\)/)
  assert.match(js, /wx\.navigateTo/)
  assert.match(js, /encodeURIComponent\(queryKey \|\| ''\)/)
  assert.doesNotMatch(wxml, /query-window/)
  assert.doesNotMatch(wxml, /queryWindowVisible/)
  assert.doesNotMatch(wxml, /section-title">选择专精/)
  assert.doesNotMatch(wxml, /class="spec-grid"/)
  assert.doesNotMatch(wxml, /class="detail-panel"/)
})

test('query detail page is registered and uses dropdown pickers', () => {
  const app = JSON.parse(fs.readFileSync('app.json', 'utf8'))
  const js = fs.readFileSync('pages/builds/detail.js', 'utf8')
  const wxml = fs.readFileSync('pages/builds/detail.wxml', 'utf8')

  assert.ok(app.pages.includes('pages/builds/detail'))
  assert.match(wxml, /picker[\s\S]*range="\{\{classOptions\}\}"/)
  assert.match(wxml, /picker[\s\S]*range="\{\{specOptions\}\}"/)
  assert.match(wxml, /bindchange="selectClass"/)
  assert.match(wxml, /bindchange="selectSpec"/)
  assert.match(js, /onLoad\(options\)/)
  assert.match(js, /selectClass\(event\)/)
  assert.match(js, /selectSpec\(event\)/)
  assert.match(js, /defaultSpecId = '法师-冰霜'/)
})

test('query detail page has module-specific UI sections', () => {
  const wxml = fs.readFileSync('pages/builds/detail.wxml', 'utf8')

  assert.match(wxml, /wx:if="\{\{activeQueryKey == 'talents'\}\}"/)
  assert.match(wxml, /class="talent-code-card"/)
  assert.match(wxml, /wx:if="\{\{activeDetail\.importCode\}\}"/)
  assert.match(wxml, /class="talent-chip-list"/)
  assert.match(wxml, /activeDetail\.coreTalents/)
  assert.match(wxml, /wx:if="\{\{activeQueryKey == 'gear'\}\}"/)
  assert.match(wxml, /class="gear-list"/)
  assert.match(wxml, /wx:if="\{\{activeQueryKey == 'statWeights'\}\}"/)
  assert.match(wxml, /class="stat-bars"/)
  assert.match(wxml, /wx:if="\{\{activeQueryKey == 'rotation'\}\}"/)
  assert.match(wxml, /class="rotation-timeline"/)
})

test('builds page uses an Archon-style specialization meta palette', () => {
  const wxml = fs.readFileSync('pages/builds/builds.wxml', 'utf8')
  const css = fs.readFileSync('pages/builds/builds.wxss', 'utf8')

  assert.match(wxml, /background="#111111"/)
  assert.match(wxml, /color="#FFFFFF"/)
  assert.match(css, /\.builds-shell[\s\S]*background:\s*#060606;/)
  assert.match(css, /\.builds-hero[\s\S]*#8b3ff5/i)
  assert.match(css, /\.builds-hero[\s\S]*#f8b700/i)
  assert.match(css, /\.query-card[\s\S]*border-radius:\s*16rpx;/)
  assert.match(css, /\.query-card[\s\S]*background:\s*#151515;/)
  assert.doesNotMatch(css, /#edf3ff/i)
})

test('featured specialization cards show source evidence', () => {
  const wxml = fs.readFileSync('pages/builds/builds.wxml', 'utf8')

  assert.match(wxml, /item\.sourceName/)
  assert.match(wxml, /item\.publishedAt/)
  assert.match(wxml, /item\.analysisWindow/)
})

test('featured specialization section is a three-dot swiper preview with view-all navigation', () => {
  const js = fs.readFileSync('pages/builds/builds.js', 'utf8')
  const wxml = fs.readFileSync('pages/builds/builds.wxml', 'utf8')
  const css = fs.readFileSync('pages/builds/builds.wxss', 'utf8')
  const payload = buildSpecializationHomePayload()

  assert.equal(payload.featuredSpecializations.length, 3)
  assert.match(wxml, /swiper[\s\S]*class="intel-swiper"[\s\S]*indicator-dots/)
  assert.match(wxml, /swiper-item[\s\S]*wx:for="\{\{featuredSpecializations\}\}"/)
  assert.doesNotMatch(wxml, /class="intel-scroll"/)
  assert.match(wxml, /bindtap="openIntelPage"/)
  assert.match(wxml, />查看全部</)
  assert.match(js, /openIntelPage\(\)/)
  assert.match(js, /pages\/builds\/intel/)
  assert.match(css, /\.intel-swiper[\s\S]*height:\s*300rpx;/)
  assert.match(css, /\.intel-swiper\s+\.wx-swiper-dots[\s\S]*bottom:\s*10rpx;/)
  assert.match(css, /\.intel-card[\s\S]*height:\s*260rpx;/)
})

test('specialization intel page is registered and renders all retrieved content', () => {
  const app = JSON.parse(fs.readFileSync('app.json', 'utf8'))
  const js = fs.readFileSync('pages/builds/intel.js', 'utf8')
  const wxml = fs.readFileSync('pages/builds/intel.wxml', 'utf8')
  const css = fs.readFileSync('pages/builds/intel.wxss', 'utf8')

  assert.ok(app.pages.includes('pages/builds/intel'))
  assert.match(js, /requestBuildsIntel/)
  assert.match(js, /fallbackBuildsIntel/)
  assert.match(wxml, /wx:for="\{\{items\}\}"/)
  assert.match(wxml, /item\.sourceName/)
  assert.match(wxml, /item\.analysisWindow/)
  assert.match(wxml, /bindtap="openSpecDetail"/)
  assert.match(js, /pages\/builds\/detail\?query=talents&spec=/)
  assert.match(css, /\.intel-list/)
})

test('query detail page can open on a specialization selected from intel cards', () => {
  const js = fs.readFileSync('pages/builds/detail.js', 'utf8')

  assert.match(js, /options\.spec/)
  assert.match(js, /decodeURIComponent\(options\.spec\)/)
  assert.match(js, /findSpecSelection\(specId\)/)
})

test('query detail page can pass current talent and gear context to simc', () => {
  const js = fs.readFileSync('pages/builds/detail.js', 'utf8')
  const wxml = fs.readFileSync('pages/builds/detail.wxml', 'utf8')
  const css = fs.readFileSync('pages/builds/detail.wxss', 'utf8')

  assert.match(wxml, /bindtap="openSimcWithBuildContext"/)
  assert.match(wxml, /带当前构筑去 SimC/)
  assert.match(js, /SIMC_BUILD_CONTEXT_STORAGE_KEY/)
  assert.match(js, /buildSimcContext\(\)/)
  assert.match(js, /details:\s*selectedDetail\.details \|\| \{\}/)
  assert.match(js, /wx\.setStorageSync\(SIMC_BUILD_CONTEXT_STORAGE_KEY/)
  assert.match(js, /\/pages\/simulator\/simc\?from=builds/)
  assert.match(js, /fail:\s*\(error\) =>/)
  assert.match(css, /\.simc-link-panel/)
  assert.match(css, /\.simc-link-button/)
})

test('talent detail page exposes a front-end talent simulator', () => {
  const js = fs.readFileSync('pages/builds/detail.js', 'utf8')
  const wxml = fs.readFileSync('pages/builds/detail.wxml', 'utf8')
  const css = fs.readFileSync('pages/builds/detail.wxss', 'utf8')

  assert.match(js, /talentScenarios:\s*\[/)
  assert.match(js, /selectedTalentNodes/)
  assert.match(js, /setTalentScenario\(event\)/)
  assert.match(js, /toggleTalentNode\(event\)/)
  assert.match(js, /openTalentSimc\(\)/)
  assert.match(js, /talentSimulationSummary/)
  assert.match(js, /talentSimulatorState/)
  assert.match(wxml, /class="talent-simulator"/)
  assert.match(wxml, /wx:for="\{\{talentScenarios\}\}"/)
  assert.match(wxml, /bindtap="setTalentScenario"/)
  assert.match(wxml, /bindtap="toggleTalentNode"/)
  assert.match(wxml, /模拟这套天赋/)
  assert.match(css, /\.talent-scenario-tabs/)
  assert.match(css, /\.talent-node-chip\.selected/)
  assert.match(css, /\.talent-simc-button/)
})

test('gear detail page exposes acquisition progress and next item actions', () => {
  const js = fs.readFileSync('pages/builds/detail.js', 'utf8')
  const wxml = fs.readFileSync('pages/builds/detail.wxml', 'utf8')
  const css = fs.readFileSync('pages/builds/detail.wxss', 'utf8')

  assert.match(js, /gearAcquisitionRows/)
  assert.match(js, /gearProgressText/)
  assert.match(js, /gearNextAction/)
  assert.match(js, /toggleGearAcquired\(event\)/)
  assert.match(js, /buildGearAcquisitionRows/)
  assert.match(wxml, /class="gear-progress-panel"/)
  assert.match(wxml, /gearProgressText/)
  assert.match(wxml, /gearNextAction/)
  assert.match(wxml, /wx:for="\{\{gearAcquisitionRows\}\}"/)
  assert.match(wxml, /bindtap="toggleGearAcquired"/)
  assert.match(wxml, /item\.priorityLabel/)
  assert.match(wxml, /item\.sourceType/)
  assert.match(css, /\.gear-progress-panel/)
  assert.match(css, /\.gear-acquisition-row\.acquired/)
  assert.match(css, /\.gear-check/)
})

test('simc linkage derives talent and gear state from full specialization details', () => {
  const js = fs.readFileSync('pages/builds/detail.js', 'utf8')

  assert.match(js, /const talentDetail = detailForQuery\(selectedDetail,\s*'talents'\)/)
  assert.match(js, /const gearDetail = detailForQuery\(selectedDetail,\s*'gear'\)/)
  assert.match(js, /buildTalentNodeRows\(talentDetail/)
  assert.match(js, /buildGearAcquisitionRows\(gearDetail/)
})
