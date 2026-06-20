const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')
const { buildSpecializationHomePayload } = require('../server/builds/home-payload')

function loadBuildsDetailPageConfig(options = {}) {
  const source = fs.readFileSync('pages/builds/detail.js', 'utf8')
  const sandbox = {
    console,
    Page(config) {
      sandbox.pageConfig = config
    },
    wx: {
      navigateTo() {},
      redirectTo() {},
      setStorageSync() {},
      showToast(toast) {
        if (Array.isArray(options.toasts)) options.toasts.push(toast || {})
      }
    },
    require(modulePath) {
      if (modulePath === './builds-api') {
        return {
          fallbackBuildsHome: () => ({
            quickActions: [{ key: 'gear', title: '装备模拟', desc: '' }],
            classOptions: [],
            trustedSources: []
          }),
          fallbackBuildsDetail: () => ({
            details: {
              talents: { coreTalents: [], importCode: '' },
              gear: {}
            }
          }),
          requestBuildsDetail: () => Promise.resolve({ payload: null }),
          requestBuildsHome: () => Promise.resolve({ payload: null })
        }
      }
      if (modulePath === './websim-api') {
        return {
          requestWebsimGear: options.requestWebsimGear || (() => Promise.resolve({ payload: {} })),
          requestWebsimGearStats: options.requestWebsimGearStats || (() => Promise.resolve({ payload: {} }))
        }
      }
      if (modulePath === '../common/analytics-client') {
        return {
          trackEvent() {},
          trackPageLeave() {},
          trackPageView() {}
        }
      }
      if (modulePath === '../common/build-template-storage') {
        return {
          syncBuildTemplate(record) {
            if (Array.isArray(options.savedTemplates)) options.savedTemplates.push(record)
            return Promise.resolve({ payload: { template: record || {} } })
          }
        }
      }
      if (modulePath === '../common/game-asset') {
        return require('../pages/common/game-asset')
      }
      throw new Error(`Unexpected require: ${modulePath}`)
    }
  }
  vm.runInNewContext(source, sandbox, { filename: 'pages/builds/detail.js' })
  return sandbox.pageConfig
}

const canonicalGearSlots = [
  'head', 'neck', 'shoulder', 'back', 'chest', 'wrist', 'hands', 'waist',
  'legs', 'feet', 'finger1', 'finger2', 'trinket1', 'trinket2', 'main_hand', 'off_hand'
]

function completeGearSelection(slots = canonicalGearSlots) {
  return slots.reduce((selection, slot, index) => {
    selection[slot] = {
      slot,
      simcSlot: slot,
      itemId: String(250000 + index),
      id: String(250000 + index),
      displayName: `Item ${slot}`,
      ilevel: 707,
      bonus_id: '12345',
      simcReady: true
    }
    return selection
  }, {})
}

function loadTalentSimulatorPageConfig(options = {}) {
  const source = fs.readFileSync('pages/builds/talent-simulator.js', 'utf8')
  const mocks = {
    profilePayload: null,
    savedTemplate: null,
    talentRequests: [],
    toasts: []
  }
  const sandbox = {
    console,
    Page(config) {
      sandbox.pageConfig = config
    },
    wx: {
      showToast(options) {
        mocks.toasts.push(options || {})
      }
    },
    require(modulePath) {
      if (modulePath === './builds-api') {
        return {
          fallbackBuildsHome: () => ({
            quickActions: [],
            classOptions: [{
              name: '法师',
              key: 'mage',
              specializations: [{
                id: '法师-冰霜',
                title: '冰霜',
                className: '法师',
                specName: '冰霜',
                websimClassKey: 'mage',
                websimSpecKey: 'frost'
              }]
            }],
            trustedSources: []
          }),
          fallbackBuildsDetail: () => ({
            className: '法师',
            specName: '冰霜',
            details: {
              talents: { coreTalents: [], importCode: '' },
              gear: {}
            }
          }),
          requestBuildsHome: () => Promise.resolve({ payload: null })
        }
      }
      if (modulePath === './websim-api') {
        return {
          requestWebsimBootstrap: () => Promise.resolve({ payload: options.bootstrapPayload || {} }),
          requestWebsimTalents: (params = {}) => {
            mocks.talentRequests.push(params)
            const key = `${params.classKey || ''}:${params.specKey || ''}:${params.heroKey || ''}`
            const payload = (options.talentPayloads && options.talentPayloads[key]) || options.defaultTalentPayload || {}
            return Promise.resolve({ payload })
          },
          requestWebsimProfile: (payload) => {
            mocks.profilePayload = payload
            return Promise.resolve({
              payload: {
                talentEncoding: {
                  status: 'encoded',
                  lines: ['talents=websim-code'],
                  errors: []
                }
              }
            })
          }
        }
      }
      if (modulePath === './talent-simulator-core') {
        const core = require('../pages/builds/talent-simulator-core')
        if (options.omitTemplatesForClass) {
          const { templatesForClass, ...rest } = core
          return rest
        }
        return core
      }
      if (modulePath === '../common/analytics-client') {
        return {
          trackEvent() {},
          trackPageLeave() {},
          trackPageView() {}
        }
      }
      if (modulePath === '../common/build-template-storage') {
        return {
          syncBuildTemplate(record) {
            mocks.savedTemplate = record
            return Promise.resolve({ payload: { template: record } })
          }
        }
      }
      if (modulePath === '../common/game-asset') {
        return require('../pages/common/game-asset')
      }
      throw new Error(`Unexpected require: ${modulePath}`)
    }
  }
  vm.runInNewContext(source, sandbox, { filename: 'pages/builds/talent-simulator.js' })
  return { pageConfig: sandbox.pageConfig, mocks }
}

test('builds tab is renamed to specialization and removes legacy metrics row', () => {
  const app = JSON.parse(fs.readFileSync('app.json', 'utf8'))
  const tab = app.tabBar.list.find((item) => item.pagePath === 'pages/builds/builds')
  const wxml = fs.readFileSync('pages/builds/builds.wxml', 'utf8')

  assert.equal(tab.text, '职业专精')
  assert.doesNotMatch(wxml, /class="metrics"/)
  assert.doesNotMatch(wxml, /metric-card/)
})

test('builds page focuses on four query entries and opens talents in the native simulator', () => {
  const js = fs.readFileSync('pages/builds/builds.js', 'utf8')
  const wxml = fs.readFileSync('pages/builds/builds.wxml', 'utf8')
  const payload = buildSpecializationHomePayload()

  assert.deepEqual(
    payload.quickActions.map((item) => item.title),
    ['天赋构筑', '装备模拟', '属性权重', '输出循环']
  )
  assert.match(wxml, /bindtap="openQueryPage"/)
  assert.match(js, /openQueryPage\(event\)/)
  assert.match(js, /wx\.navigateTo/)
  assert.match(js, /queryKey === 'talents'/)
  assert.match(js, /pages\/builds\/talent-simulator/)
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
  assert.doesNotMatch(app.pages.join('\n'), /gear-simulator/)
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
  assert.doesNotMatch(wxml, /class="gear-stat-panel"/)
  assert.match(wxml, /class="gear-slot-grid"/)
  assert.match(wxml, /wx:if="\{\{activeQueryKey == 'statWeights'\}\}"/)
  assert.match(wxml, /class="stat-bars"/)
  assert.match(wxml, /class="stat-scenario-tabs"/)
  assert.match(wxml, /activeStatRows/)
  assert.match(wxml, /statWeightValidation\.simcSuccessCount/)
  assert.match(wxml, /statWeightRecommendations/)
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
  assert.match(js, /pages\/builds\/talent-simulator\?spec=/)
  assert.match(css, /\.intel-list/)
})

test('talent simulator page can open on a specialization selected from intel cards', () => {
  const js = fs.readFileSync('pages/builds/talent-simulator.js', 'utf8')

  assert.match(js, /options\.spec/)
  assert.match(js, /decodeURIComponent\(options\.spec\)/)
  assert.match(js, /findSpecSelection\(specId,/)
})

test('query detail page removes talent and gear simc entrances while keeping stat weights entry', () => {
  const js = fs.readFileSync('pages/builds/detail.js', 'utf8')
  const wxml = fs.readFileSync('pages/builds/detail.wxml', 'utf8')
  const css = fs.readFileSync('pages/builds/detail.wxss', 'utf8')

  assert.doesNotMatch(wxml, /bindtap="openTalentSimc"/)
  assert.doesNotMatch(wxml, /模拟这套天赋/)
  assert.match(js, /SIMC_BUILD_CONTEXT_STORAGE_KEY/)
  assert.match(js, /buildSimcContext\(\)/)
  assert.match(js, /statWeights:\s*\{/)
  assert.match(js, /weights:\s*this\.data\.activeStatRows/)
  assert.match(js, /wx\.setStorageSync\(SIMC_BUILD_CONTEXT_STORAGE_KEY/)
  assert.match(js, /\/pages\/simulator\/simc\?from=builds/)
  assert.match(js, /fail:\s*\(error\) =>/)
  assert.doesNotMatch(wxml, /class="simc-link-panel"/)
  assert.doesNotMatch(css, /\.simc-link-panel/)
})

test('stat weights detail page exposes scenario state without strong claim copy', () => {
  const js = fs.readFileSync('pages/builds/detail.js', 'utf8')
  const wxml = fs.readFileSync('pages/builds/detail.wxml', 'utf8')
  const css = fs.readFileSync('pages/builds/detail.wxss', 'utf8')

  assert.match(js, /statWeightScenarios\(activeDetail\)/)
  assert.match(js, /selectedStatWeightScenario/)
  assert.match(js, /setStatWeightScenario\(event\)/)
  assert.match(js, /builds_stat_weight_scenario_select/)
  assert.match(wxml, /wx:for="\{\{statWeightScenarios\}\}"/)
  assert.match(wxml, /bindtap="setStatWeightScenario"/)
  assert.match(wxml, /class="stat-source-state/)
  assert.match(wxml, /样本 \{\{statWeightValidation\.sampleCount/)
  assert.match(wxml, /Profile \{\{statWeightValidation\.profileCount/)
  assert.match(wxml, /SimC \{\{statWeightValidation\.simcSuccessCount/)
  assert.match(wxml, /当前不输出强结论/)
  assert.doesNotMatch(wxml, /最优|毕业|必堆/)
  assert.match(css, /\.stat-scenario-tab\.active/)
  assert.match(css, /\.stat-source-state\.verified/)
  assert.match(css, /\.stat-blocked-list/)
  assert.match(css, /\.stat-simc-button/)
})

test('native talent simulator page exposes WebSim tree controls and template persistence', () => {
  const app = JSON.parse(fs.readFileSync('app.json', 'utf8'))
  const js = fs.readFileSync('pages/builds/talent-simulator.js', 'utf8')
  const wxml = fs.readFileSync('pages/builds/talent-simulator.wxml', 'utf8')
  const css = fs.readFileSync('pages/builds/talent-simulator.wxss', 'utf8')

  assert.ok(app.pages.includes('pages/builds/talent-simulator'))
  assert.match(js, /game-asset/)
  assert.match(js, /requestWebsimBootstrap/)
  assert.match(js, /requestWebsimTalents/)
  assert.doesNotMatch(js, /requestWebsimProfile/)
  assert.match(js, /buildTalentViewModel/)
  assert.match(js, /tapTalentNode\(event\)/)
  assert.match(js, /selectChoiceTalent\(event\)/)
  assert.match(js, /resetTalents\(\)/)
  assert.match(js, /saveTalentTemplate\(\)/)
  assert.match(js, /confirmSaveTalentTemplate\(\)/)
  assert.match(js, /saveTemplateSheet/)
  assert.match(js, /defaultTalentTemplateTitle/)
  assert.match(js, /syncBuildTemplate/)
  assert.doesNotMatch(js, /openTalentImport\(\)/)
  assert.doesNotMatch(js, /applyTalentImport\(\)/)
  assert.doesNotMatch(js, /importSheet/)
  assert.doesNotMatch(js, /copyTalentExport\(\)/)
  assert.doesNotMatch(js, /openTalentSimc\(\)/)
  assert.doesNotMatch(js, /buildSimcContext\(\)/)
  assert.doesNotMatch(js, /SIMC_BUILD_CONTEXT_STORAGE_KEY/)
  assert.doesNotMatch(js, /talentEncoding\.lines/)
  assert.match(js, /activeTreeKey:\s*'class'/)
  assert.match(js, /treeNavItems/)
  assert.match(js, /activeSection/)
  assert.match(js, /selectTalentTree\(event\)/)
  assert.match(js, /node\.canSelect \? 'selectable' : ''/)
  assert.match(js, /`shape-\$\{node\.shape \|\| 'square'\}`/)
  assert.match(js, /line && line\.available \? 'available' : ''/)
  assert.doesNotMatch(js, /selectScenario\(event\)/)
  assert.doesNotMatch(js, /updateTalentSearch\(event\)/)
  assert.doesNotMatch(js, /clearTalentSearch\(\)/)
  assert.doesNotMatch(js, /searchTerm:\s*''/)
  assert.doesNotMatch(js, /searchCountText:/)
  assert.match(wxml, /class="talent-simulator-page"/)
  const toolbarMatch = wxml.match(/<view class="talent-toolbar">([\s\S]*?)<\/view>\s*<\/picker>\s*<\/view>/)
  assert.ok(toolbarMatch)
  assert.equal((toolbarMatch[1].match(/<picker/g) || []).length, 3)
  assert.match(toolbarMatch[1], />职业</)
  assert.match(toolbarMatch[1], />专精</)
  assert.match(toolbarMatch[1], />英雄天赋</)
  assert.doesNotMatch(toolbarMatch[1], />场景</)
  assert.doesNotMatch(wxml, /bindchange="selectScenario"/)
  assert.doesNotMatch(wxml, /range="\{\{scenarioOptions\}\}"/)
  assert.doesNotMatch(wxml, /class="talent-search-panel"/)
  assert.doesNotMatch(wxml, /class="talent-search-input"/)
  assert.doesNotMatch(wxml, /placeholder="搜索天赋"/)
  assert.doesNotMatch(wxml, /bindinput="updateTalentSearch"/)
  assert.doesNotMatch(wxml, /bindtap="clearTalentSearch"/)
  assert.match(wxml, /item\.gameAsset\.iconUrl/)
  assert.doesNotMatch(wxml, /item\.iconUrl/)
  assert.match(wxml, /wx:for="\{\{treeNavItems\}\}"/)
  assert.match(wxml, /class="\{\{item\.tabClass\}\}"/)
  assert.match(wxml, /class="active-tree-panel/)
  assert.match(wxml, /activeSection\.nodes/)
  assert.match(wxml, /class="\{\{item\.linkClass\}\}"/)
  assert.match(wxml, /bindtap="tapTalentNode"/)
  assert.match(wxml, /bindtap="resetTalents"/)
  assert.match(wxml, /bindtap="openCommunityTemplates"/)
  assert.match(wxml, /bindtap="saveTalentTemplate"/)
  assert.match(wxml, /saveTemplateSheet\.visible/)
  assert.match(wxml, /bindinput="updateTemplateName"/)
  assert.match(wxml, /bindtap="confirmSaveTalentTemplate"/)
  assert.doesNotMatch(wxml, /bindtap="openTalentImport"/)
  assert.doesNotMatch(wxml, /importSheet\.visible/)
  assert.doesNotMatch(wxml, /bindtap="copyTalentExport"/)
  assert.doesNotMatch(wxml, /bindtap="openTalentSimc"/)
  assert.doesNotMatch(wxml, />复制</)
  assert.doesNotMatch(wxml, /带去 SimC/)
  assert.match(wxml, /choiceSheet/)
  assert.match(wxml, /nodeDetailSheet/)
  assert.match(css, /\.tree-tabs/)
  assert.match(css, /\.talent-toolbar\s*\{[\s\S]*grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\);/)
  assert.match(css, /\.toolbar-picker\s*\{[\s\S]*display:\s*flex;[\s\S]*align-items:\s*center;[\s\S]*min-height:\s*58rpx;[\s\S]*\}/)
  assert.match(css, /\.picker-label\s*\{[\s\S]*flex-shrink:\s*0;[\s\S]*\}/)
  assert.match(css, /\.picker-value\s*\{[\s\S]*margin-top:\s*0;[\s\S]*text-overflow:\s*ellipsis;[\s\S]*\}/)
  assert.match(css, /\.tree-tab\s*\{[\s\S]*display:\s*flex;[\s\S]*align-items:\s*center;[\s\S]*min-height:\s*68rpx;[\s\S]*\}/)
  assert.match(css, /\.tree-tab-subtitle\s*\{[\s\S]*flex:\s*1;[\s\S]*text-overflow:\s*ellipsis;[\s\S]*\}/)
  assert.match(wxml, /class="active-tree-separator"/)
  assert.match(css, /\.active-tree-head\s*\{[\s\S]*align-items:\s*center;[\s\S]*padding:\s*14rpx 22rpx;[\s\S]*\}/)
  assert.match(css, /\.active-tree-title-wrap\s*\{[\s\S]*display:\s*flex;[\s\S]*align-items:\s*center;[\s\S]*overflow:\s*hidden;[\s\S]*\}/)
  assert.match(css, /\.active-tree-title\s*\{[\s\S]*margin-top:\s*0;[\s\S]*white-space:\s*nowrap;[\s\S]*text-overflow:\s*ellipsis;[\s\S]*\}/)
  assert.match(css, /\.active-tree-subtitle\s*\{[\s\S]*margin-top:\s*0;[\s\S]*white-space:\s*nowrap;[\s\S]*text-overflow:\s*ellipsis;[\s\S]*\}/)
  assert.doesNotMatch(css, /\.talent-search-panel/)
  assert.doesNotMatch(css, /\.talent-search-input/)
  assert.doesNotMatch(css, /\.search-clear-button/)
  assert.match(css, /\.active-tree-panel/)
  assert.match(css, /\.mobile-action-bar/)
  assert.match(css, /\.talent-node\.selected/)
  assert.match(css, /\.talent-node\.locked/)
  assert.match(css, /\.talent-page-content\s*\{[\s\S]*padding:\s*24rpx 24rpx 230rpx;[\s\S]*\}/)
  assert.match(css, /\.talent-grid\s*\{[\s\S]*height:\s*1080rpx;[\s\S]*\}/)
  assert.match(css, /\.active-tree-grid-hero\s*\{[\s\S]*height:\s*820rpx;[\s\S]*\}/)
  assert.match(css, /\.active-tree-grid-spec\s*\{[\s\S]*height:\s*1080rpx;[\s\S]*\}/)
  assert.match(css, /\.talent-link::after\s*\{[\s\S]*border-left:\s*12rpx solid rgba\(150,\s*150,\s*150,\s*0\.62\);[\s\S]*\}/)
  assert.match(css, /\.talent-link\.active\s*\{[\s\S]*background:\s*#f8b700;[\s\S]*\}/)
  assert.match(css, /\.talent-link\.active::after\s*\{[\s\S]*border-left-color:\s*#f8b700;[\s\S]*\}/)
  assert.match(css, /\.talent-link\.available\s*\{[\s\S]*background:\s*rgba\(248,\s*183,\s*0,\s*0\.72\);[\s\S]*\}/)
  assert.match(css, /\.talent-node\s*\{[\s\S]*width:\s*64rpx;[\s\S]*height:\s*64rpx;[\s\S]*margin-left:\s*-32rpx;[\s\S]*margin-top:\s*-32rpx;[\s\S]*box-sizing:\s*border-box;[\s\S]*border:\s*5rpx solid rgba\(255,\s*255,\s*255,\s*0\.16\);[\s\S]*\}/)
  assert.match(css, /\.talent-node\.shape-circle\s*\{[\s\S]*border-radius:\s*50%;[\s\S]*\}/)
  assert.match(css, /\.talent-node\.shape-square\s*\{[\s\S]*border-radius:\s*14rpx;[\s\S]*\}/)
  assert.match(wxml, /class="talent-choice-frame" wx:if="\{\{item\.shape === 'choice'\}\}"/)
  assert.match(css, /\.talent-node\.shape-choice\s*\{[\s\S]*border:\s*0;[\s\S]*overflow:\s*visible;[\s\S]*\}/)
  assert.match(css, /\.talent-node\.shape-choice \.talent-choice-frame\s*\{[\s\S]*left:\s*-3rpx;[\s\S]*width:\s*70rpx;[\s\S]*clip-path:\s*polygon\(20% 0,\s*80% 0,\s*100% 20%,\s*100% 80%,\s*80% 100%,\s*20% 100%,\s*0 80%,\s*0 20%\);[\s\S]*\}/)
  assert.match(css, /\.talent-node\.shape-choice \.talent-choice-frame::after\s*\{[\s\S]*inset:\s*5rpx;[\s\S]*clip-path:\s*polygon\(20% 0,\s*80% 0,\s*100% 20%,\s*100% 80%,\s*80% 100%,\s*20% 100%,\s*0 80%,\s*0 20%\);[\s\S]*\}/)
  assert.match(css, /\.talent-node\.shape-choice \.talent-icon,[\s\S]*\.talent-node\.shape-choice \.talent-icon-fallback\s*\{[\s\S]*left:\s*6rpx;[\s\S]*width:\s*52rpx;[\s\S]*clip-path:\s*polygon\(18% 0,\s*82% 0,\s*100% 18%,\s*100% 82%,\s*82% 100%,\s*18% 100%,\s*0 82%,\s*0 18%\);[\s\S]*\}/)
  assert.match(css, /\.talent-node\.shape-choice::before\s*\{[\s\S]*left:\s*-13rpx;[\s\S]*border-right:\s*16rpx solid rgba\(150,\s*150,\s*150,\s*0\.72\);[\s\S]*\}/)
  assert.match(css, /\.talent-node\.shape-choice::after\s*\{[\s\S]*right:\s*-13rpx;[\s\S]*border-left:\s*16rpx solid rgba\(150,\s*150,\s*150,\s*0\.72\);[\s\S]*\}/)
  assert.match(css, /\.talent-node\.shape-choice\.available::before,[\s\S]*\.talent-node\.shape-choice\.selected::before,[\s\S]*\.talent-node\.shape-choice\.granted::before\s*\{[\s\S]*border-right-color:\s*#f8b700;[\s\S]*\}/)
  assert.match(css, /\.talent-node\.granted\s*\{[\s\S]*border-color:\s*#f8b700;[\s\S]*\}/)
  assert.match(css, /\.talent-node\.selectable:not\(\.selected\)\s*\{[\s\S]*border-color:\s*#24f05a;[\s\S]*\}/)
  assert.doesNotMatch(css, /\.talent-node\.selectable:not\(\.selected\):not\(\.shape-choice\)::after/)
  assert.match(css, /\.rank-button\s*\{[\s\S]*width:\s*72rpx;[\s\S]*min-width:\s*72rpx;[\s\S]*max-width:\s*72rpx;[\s\S]*padding:\s*0;[\s\S]*margin:\s*0;[\s\S]*box-sizing:\s*border-box;[\s\S]*display:\s*flex;[\s\S]*align-items:\s*center;[\s\S]*justify-content:\s*center;[\s\S]*line-height:\s*1;[\s\S]*\}/)
  assert.match(css, /\.rank-button::after\s*\{\s*border:\s*0;\s*\}/)
  assert.match(css, /\.talent-choice-sheet/)
  assert.match(css, /\.talent-detail-sheet/)
  assert.match(css, /\.template-save-sheet/)
  assert.doesNotMatch(wxml, /talent-board-scroll/)
  assert.doesNotMatch(wxml, /talent-column class/)
  assert.doesNotMatch(wxml, /talent-column spec/)
  assert.doesNotMatch(wxml, /talent-column hero/)
  assert.doesNotMatch(css, /min-width:\s*1500rpx/)
  assert.doesNotMatch(wxml, /class="talent-chip-list"/)
})

test('native talent simulator save flow names talent templates for the profile library', async () => {
  const { pageConfig, mocks } = loadTalentSimulatorPageConfig()
  const selectedNodes = [{ id: 'root', rank: 1 }]
  const page = {
    ...pageConfig,
    data: {
      ...pageConfig.data,
      websimExportCode: 'websim:mage:frost:frostfire:root:1',
      classKey: 'mage',
      specKey: 'frost',
      heroKey: 'frostfire',
      scenarioKey: 'mythic_plus',
      selectedHeroLabel: '霜火',
      selectedScenarioIndex: 0,
      scenarioOptions: [{ key: 'mythic_plus', title: '大秘境' }],
      selectedDetail: { className: '法师', specName: '冰霜' },
      selectedSpec: { className: '法师', title: '冰霜', specName: '冰霜' },
      selectedNodes,
      classSection: { key: 'class', pointCount: 34, pointCap: 34 },
      heroSection: { key: 'hero', pointCount: 13, pointCap: 13 },
      specSection: { key: 'spec', pointCount: 34, pointCap: 34 },
      canSaveTalentTemplate: true,
      selectedCommunityTemplate: null,
      saveTemplateSheet: { visible: false, name: '', defaultName: '' },
      templateSaving: false
    },
    setData(update, callback) {
      this.data = { ...this.data, ...update }
      if (callback) callback()
    },
    renderTalentView() {}
  }

  pageConfig.saveTalentTemplate.call(page)

  assert.equal(page.data.saveTemplateSheet.visible, true)
  assert.match(page.data.saveTemplateSheet.name, /^法师-冰霜-霜火-\d{4} \d{4}$/)
  assert.ok(page.data.saveTemplateSheet.name.length <= 28)

  pageConfig.updateTemplateName.call(page, { detail: { value: '我的AOE模板' } })
  await pageConfig.confirmSaveTalentTemplate.call(page)

  assert.equal(page.data.saveTemplateSheet.visible, false)
  assert.equal(mocks.profilePayload, null)
  assert.equal(mocks.savedTemplate.type, 'talent')
  assert.equal(mocks.savedTemplate.title, '我的AOE模板')
  assert.equal(mocks.savedTemplate.rawString, 'websim:mage:frost:frostfire:root:1')
  assert.equal(Array.isArray(mocks.savedTemplate.simcLines), true)
  assert.equal(mocks.savedTemplate.simcLines.length, 0)
  assert.equal(mocks.savedTemplate.status, 'saved')
  assert.equal(mocks.savedTemplate.statusLabel, '已保存')
  assert.deepEqual(mocks.savedTemplate.metadata.selectedNodes, selectedNodes)
})

test('native talent simulator blocks template save until talent points are filled', () => {
  const { pageConfig, mocks } = loadTalentSimulatorPageConfig()
  const page = {
    ...pageConfig,
    data: {
      ...pageConfig.data,
      websimExportCode: 'websim:mage:frost:frostfire:root:1',
      classSection: { key: 'class', pointCount: 33, pointCap: 34 },
      heroSection: { key: 'hero', pointCount: 13, pointCap: 13 },
      specSection: { key: 'spec', pointCount: 34, pointCap: 34 },
      canSaveTalentTemplate: false,
      saveBlockReason: '请先点满天赋点：通用 33/34',
      saveTemplateSheet: { visible: false, name: '', defaultName: '' },
      templateSaving: false
    },
    setData(update, callback) {
      this.data = { ...this.data, ...update }
      if (callback) callback()
    },
    renderTalentView() {}
  }

  pageConfig.saveTalentTemplate.call(page)
  pageConfig.confirmSaveTalentTemplate.call(page)

  assert.equal(page.data.saveTemplateSheet.visible, false)
  assert.equal(mocks.profilePayload, null)
  assert.equal(mocks.savedTemplate, null)
  assert.equal(mocks.toasts.at(-1).title, '请先点满天赋点：通用 33/34')
})

test('native talent simulator action bar keeps three clear actions on one row', () => {
  const wxml = fs.readFileSync('pages/builds/talent-simulator.wxml', 'utf8')
  const css = fs.readFileSync('pages/builds/talent-simulator.wxss', 'utf8')

  const actionBarMatch = wxml.match(/<view class="mobile-action-bar">([\s\S]*?)<\/view>/)
  assert.ok(actionBarMatch)
  assert.equal((actionBarMatch[1].match(/<button/g) || []).length, 3)
  assert.match(actionBarMatch[1], /保存模板/)
  assert.match(actionBarMatch[1], /导入社区推荐/)
  assert.match(actionBarMatch[1], /重置/)
  assert.doesNotMatch(actionBarMatch[1], /openTalentImport/)
  assert.match(css, /grid-template-columns:\s*minmax\(220rpx,\s*1\.15fr\) minmax\(220rpx,\s*1fr\) 132rpx;/)
  assert.match(css, /\.mobile-action-bar button\s*\{[\s\S]*width:\s*100%;[\s\S]*margin:\s*0;[\s\S]*box-sizing:\s*border-box;[\s\S]*white-space:\s*nowrap;[\s\S]*\}/)
  assert.match(css, /\.action-primary-button/)
  assert.match(css, /\.action-secondary-button/)
  assert.match(css, /\.mobile-action-bar button::after\s*\{\s*border:\s*0;\s*\}/)
})

test('native talent simulator save sheet keeps cancel and save on the same row', () => {
  const wxml = fs.readFileSync('pages/builds/talent-simulator.wxml', 'utf8')
  const css = fs.readFileSync('pages/builds/talent-simulator.wxss', 'utf8')

  const saveSheetMatch = wxml.match(/<view class="save-sheet-actions">([\s\S]*?)<\/view>/)
  assert.ok(saveSheetMatch)
  assert.equal((saveSheetMatch[1].match(/<button/g) || []).length, 2)
  assert.match(saveSheetMatch[1], /save-sheet-secondary[\s\S]*取消/)
  assert.match(saveSheetMatch[1], /save-sheet-primary[\s\S]*保存/)
  assert.match(wxml, /disabled="\{\{!canSaveTalentTemplate \|\| templateSaving\}\}"/)
  assert.match(css, /\.template-save-sheet\s*\{[\s\S]*padding:\s*18rpx 24rpx calc\(42rpx \+ env\(safe-area-inset-bottom\)\);[\s\S]*box-sizing:\s*border-box;[\s\S]*\}/)
  assert.match(css, /\.save-sheet-actions\s*\{[\s\S]*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\);[\s\S]*align-items:\s*center;[\s\S]*\}/)
  assert.match(css, /\.save-sheet-actions button\s*\{[\s\S]*width:\s*100%;[\s\S]*min-width:\s*0;[\s\S]*margin:\s*0;[\s\S]*box-sizing:\s*border-box;[\s\S]*display:\s*flex;[\s\S]*align-items:\s*center;[\s\S]*justify-content:\s*center;[\s\S]*line-height:\s*1;[\s\S]*white-space:\s*nowrap;[\s\S]*\}/)
})

test('native talent simulator page exposes community template import sheet', () => {
  const js = fs.readFileSync('pages/builds/talent-simulator.js', 'utf8')
  const wxml = fs.readFileSync('pages/builds/talent-simulator.wxml', 'utf8')
  const css = fs.readFileSync('pages/builds/talent-simulator.wxss', 'utf8')
  const api = fs.readFileSync('pages/builds/websim-api.js', 'utf8')

  assert.match(api, /communityTemplates:\s*\[\]/)
  assert.match(api, /communityTemplateSync/)
  assert.match(js, /communityTemplates:\s*\[\]/)
  assert.match(js, /communityTemplateSync/)
  assert.match(js, /activeCommunityTemplates/)
  assert.match(js, /communityTemplateSheet/)
  assert.match(js, /selectedCommunityTemplate/)
  assert.match(js, /openCommunityTemplates\(\)/)
  assert.match(js, /closeCommunityTemplates\(\)/)
  assert.match(js, /applyCommunityTemplate\(event\)/)
  assert.match(js, /communityTemplateStatusText/)
  assert.match(js, /communityTemplateApplyMode/)
  assert.match(wxml, /bindtap="openCommunityTemplates"/)
  assert.match(wxml, />导入社区推荐</)
  assert.match(wxml, /communityTemplateSheet\.visible/)
  assert.match(wxml, /wx:for="\{\{activeCommunityTemplates\}\}"/)
  assert.match(wxml, /item\.name/)
  assert.match(wxml, /item\.sourceName/)
  assert.match(wxml, /item\.sampleLabel/)
  assert.match(wxml, /item\.keyLabel/)
  assert.match(wxml, /item\.updatedLabel/)
  assert.match(wxml, /item\.canApplyVisual/)
  assert.match(wxml, /class="template-apply-row"/)
  assert.match(wxml, /bindtap="applyCommunityTemplate"/)
  assert.match(css, /\.community-template-sheet/)
  assert.match(css, /\.community-template-card/)
  assert.match(css, /\.community-template-card\.external/)
  assert.match(css, /\.template-apply-row\s*\{[\s\S]*display:\s*flex;[\s\S]*justify-content:\s*center;[\s\S]*\}/)
  assert.match(css, /\.template-apply-button\s*\{[\s\S]*width:\s*300rpx;[\s\S]*max-width:\s*100%;[\s\S]*margin:\s*0;[\s\S]*display:\s*flex;[\s\S]*align-items:\s*center;[\s\S]*justify-content:\s*center;[\s\S]*line-height:\s*1;[\s\S]*\}/)
})

test('native talent simulator keeps rendering if the class template helper is not exported yet', () => {
  const { pageConfig } = loadTalentSimulatorPageConfig({ omitTemplatesForClass: true })
  const mageTemplate = {
    id: 'mage-template',
    classKey: 'mage',
    name: 'Mage Template',
    canApplyVisual: true,
    websimExportCode: 'websim:mage:frost:frostfire:root:1'
  }
  const warriorTemplate = {
    id: 'warrior-template',
    classKey: 'warrior',
    name: 'Warrior Template',
    canApplyVisual: true,
    websimExportCode: 'websim:warrior:protection:mountain_thane:root:1'
  }
  const page = {
    ...pageConfig,
    data: {
      ...pageConfig.data,
      activeTreeKey: 'class',
      classKey: 'mage',
      specKey: 'frost',
      heroKey: 'frostfire',
      nodes: [{ id: 'root', treeType: 'class', row: 1, col: 1, maxRank: 1, granted: true }],
      treeSections: [{ key: 'class', title: 'Class', tree: 'class', pointCap: 1 }],
      talentRanks: { root: 1 },
      baseTalentRanks: { root: 1 },
      pointCaps: { class: 1 },
      communityTemplates: [mageTemplate, warriorTemplate],
      communityTemplateSync: { sourceStatus: 'synced', sources: {}, templates: { total: 2, verified: 2, blocked: 0 } },
      scenarioOptions: [{ key: 'mythic_plus', title: 'Mythic+' }],
      selectedScenarioIndex: 0
    },
    setData(update, callback) {
      this.data = { ...this.data, ...update }
      if (callback) callback()
    }
  }

  assert.doesNotThrow(() => pageConfig.renderTalentView.call(page))
  assert.deepEqual(page.data.activeCommunityTemplates.map((item) => item.id), ['mage-template'])
})

test('native talent simulator filters duplicate community talent trees', () => {
  const { pageConfig } = loadTalentSimulatorPageConfig()
  const lowerTemplate = {
    id: 'rio-frost-low',
    classKey: 'mage',
    specKey: 'frost',
    heroKey: 'frostfire',
    name: 'Same build +18',
    canApplyVisual: true,
    websimExportCode: 'websim:mage:frost:frostfire:root:1,ice:2',
    talentState: {
      selectedNodes: [
        { id: 'ice', rank: 2 },
        { id: 'root', rank: 1 }
      ]
    },
    sampleCount: 60,
    maxKeyLevel: 18
  }
  const strongerTemplate = {
    ...lowerTemplate,
    id: 'rio-frost-high',
    name: 'Same build +24',
    sampleCount: 42,
    maxKeyLevel: 24
  }
  const distinctTemplate = {
    id: 'rio-frost-other',
    classKey: 'mage',
    specKey: 'frost',
    heroKey: 'frostfire',
    name: 'Different build',
    canApplyVisual: true,
    websimExportCode: 'websim:mage:frost:frostfire:root:1,bolt:1',
    talentState: {
      selectedNodes: [
        { id: 'bolt', rank: 1 },
        { id: 'root', rank: 1 }
      ]
    },
    sampleCount: 20,
    maxKeyLevel: 20
  }
  const page = {
    ...pageConfig,
    data: {
      ...pageConfig.data,
      activeTreeKey: 'class',
      classKey: 'mage',
      specKey: 'frost',
      heroKey: 'frostfire',
      nodes: [{ id: 'root', treeType: 'class', row: 1, col: 1, maxRank: 1, granted: true }],
      treeSections: [{ key: 'class', title: 'Class', tree: 'class', pointCap: 1 }],
      talentRanks: { root: 1 },
      baseTalentRanks: { root: 1 },
      pointCaps: { class: 1 },
      communityTemplates: [lowerTemplate, distinctTemplate, strongerTemplate],
      communityTemplateSync: { sourceStatus: 'synced', sources: {}, templates: { total: 3, verified: 3, blocked: 0 } },
      scenarioOptions: [{ key: 'mythic_plus', title: 'Mythic+' }],
      selectedScenarioIndex: 0
    },
    setData(update, callback) {
      this.data = { ...this.data, ...update }
      if (callback) callback()
    }
  }

  pageConfig.renderTalentView.call(page)

  assert.deepEqual(page.data.activeCommunityTemplates.map((item) => item.id), ['rio-frost-high', 'rio-frost-other'])
})

test('native talent simulator applies cross-spec community templates after switching target tree', async () => {
  const classOptions = [{
    name: 'Mage',
    key: 'mage',
    specializations: [
      { id: 'mage-frost', title: 'Frost', className: 'Mage', specName: 'Frost', websimClassKey: 'mage', websimSpecKey: 'frost' },
      { id: 'mage-arcane', title: 'Arcane', className: 'Mage', specName: 'Arcane', websimClassKey: 'mage', websimSpecKey: 'arcane' }
    ]
  }]
  const websimClasses = [{
    key: 'mage',
    specs: [
      { key: 'frost', heroTrees: [{ key: 'frostfire', label: 'Frostfire' }] },
      { key: 'arcane', heroTrees: [{ key: 'spellslinger', label: 'Spellslinger' }] }
    ]
  }]
  const template = {
    id: 'rio-arcane',
    classKey: 'mage',
    specKey: 'arcane',
    heroKey: 'spellslinger',
    name: 'Rioone-Mage-Spellslinger-Arcane-Mythic+',
    canApplyVisual: true,
    websimExportCode: 'websim:mage:arcane:spellslinger:arcane-root:1'
  }
  const { pageConfig, mocks } = loadTalentSimulatorPageConfig({
    talentPayloads: {
      'mage:arcane:spellslinger': {
        heroKey: 'spellslinger',
        nodes: [{ id: 'arcane-root', treeType: 'class', rank: 1, maxRank: 1 }],
        treeSections: [{ key: 'class', pointCap: 34 }],
        communityTemplates: [template],
        communityTemplateSync: { sourceStatus: 'synced', sources: {}, templates: { total: 1, verified: 1, blocked: 0 } },
        talentStatus: 'verified'
      }
    }
  })
  const page = {
    ...pageConfig,
    data: {
      ...pageConfig.data,
      classOptions,
      websimClasses,
      selectedClassIndex: 0,
      selectedSpecIndex: 0,
      selectedClass: classOptions[0],
      specOptions: classOptions[0].specializations,
      selectedSpec: classOptions[0].specializations[0],
      classKey: 'mage',
      specKey: 'frost',
      heroKey: 'frostfire',
      heroOptions: websimClasses[0].specs[0].heroTrees,
      selectedHeroIndex: 0,
      activeCommunityTemplates: [template],
      nodes: [{ id: 'frost-root', treeType: 'class', rank: 1, maxRank: 1 }],
      pointCaps: {}
    },
    setData(update, callback) {
      this.data = { ...this.data, ...update }
      if (callback) callback()
    },
    renderTalentView() {}
  }

  await pageConfig.applyCommunityTemplate.call(page, { currentTarget: { dataset: { id: 'rio-arcane' } } })

  assert.equal(mocks.talentRequests.at(-1).classKey, 'mage')
  assert.equal(mocks.talentRequests.at(-1).specKey, 'arcane')
  assert.equal(mocks.talentRequests.at(-1).heroKey, 'spellslinger')
  assert.equal(page.data.selectedSpecIndex, 1)
  assert.equal(page.data.specKey, 'arcane')
  assert.equal(page.data.heroKey, 'spellslinger')
  assert.equal(page.data.talentRanks['arcane-root'], 1)
  assert.equal(page.data.selectedCommunityTemplate.id, 'rio-arcane')
  assert.equal(page.data.communityTemplateSheet.visible, false)
})

test('gear detail page exposes inline equipment simulator state and replacement sheet', () => {
  const js = fs.readFileSync('pages/builds/detail.js', 'utf8')
  const wxml = fs.readFileSync('pages/builds/detail.wxml', 'utf8')
  const css = fs.readFileSync('pages/builds/detail.wxss', 'utf8')

  assert.match(js, /game-asset/)
  assert.match(js, /requestWebsimGear/)
  assert.doesNotMatch(js, /requestWebsimGearStats/)
  assert.match(js, /selectedGearBySlot/)
  assert.match(js, /gearSlotRows/)
  assert.match(js, /gearInitialLoading/)
  assert.doesNotMatch(js, /gearStatSnapshot/)
  assert.doesNotMatch(js, /gearStatBlockers/)
  assert.match(js, /loadWebsimGearForSelection/)
  assert.doesNotMatch(js, /refreshGearStats/)
  assert.match(js, /openGearSlotSheet\(event\)/)
  assert.match(js, /selectGearCandidate\(event\)/)
  assert.match(js, /setGearCandidateFilter\(event\)/)
  assert.match(js, /selectGearVariant\(event\)/)
  assert.match(js, /selectGearSocketOption\(event\)/)
  assert.match(js, /selectGearEnchantOption\(event\)/)
  assert.match(js, /applyGearCandidate\(\)/)
  assert.match(js, /gearTemplateScenarios/)
  assert.match(js, /selectGearTemplateScenario\(event\)/)
  assert.match(js, /openGearCommunityTemplates\(\)/)
  assert.match(js, /applyGearCommunityTemplate\(event\)/)
  assert.match(js, /resetGearSelection\(\)/)
  assert.doesNotMatch(js, /scenarioKey:\s*'single'/)
  assert.match(js, /selectedGearTemplateScenarioIndex/)
  assert.doesNotMatch(js, /this\.refreshGearStats\(\)/)
  assert.match(js, /saveGearTemplate\(\)/)
  assert.match(js, /canonicalGearTemplateLines/)
  assert.match(js, /syncBuildTemplate/)
  assert.doesNotMatch(wxml, /class="gear-status-strip"/)
  assert.doesNotMatch(wxml, /class="gear-template-picker"/)
  assert.doesNotMatch(wxml, /class="gear-stat-panel"/)
  assert.doesNotMatch(wxml, /gearStatSnapshot\.statStatus/)
  assert.doesNotMatch(wxml, /gearStatBlockers/)
  assert.match(wxml, /class="gear-slot-grid"/)
  assert.match(wxml, /wx:for="\{\{gearSlotRows\}\}"/)
  assert.doesNotMatch(wxml, /source-strip/)
  assert.match(wxml, /class="gear-loading-state" wx:if="\{\{gearInitialLoading\}\}"/)
  assert.match(wxml, /class="gear-icon"/)
  assert.match(wxml, /item\.gameAsset\.iconUrl/)
  assert.doesNotMatch(wxml, /item\.iconUrl/)
  assert.match(wxml, /item\.displayName/)
  assert.match(wxml, /item\.statusLabel/)
  assert.doesNotMatch(wxml, /item\.reason/)
  assert.doesNotMatch(wxml, /item\.source\s*(\|\||\}\})/)
  assert.doesNotMatch(wxml, /item\.itemId/)
  assert.doesNotMatch(wxml, /gearStatSnapshot\.itemLevel\.value/)
  assert.match(wxml, /bindtap="openGearSlotSheet"/)
  assert.match(wxml, /gearSlotSheet\.visible/)
  assert.match(wxml, /gearSlotSheet\.filters/)
  assert.match(wxml, /wx:for="\{\{gearSlotSheet\.candidates\}\}"/)
  assert.match(wxml, /bindtap="selectGearCandidate"/)
  assert.match(wxml, /gearSlotSheet\.variantOptions/)
  assert.match(wxml, /gearSlotSheet\.socketOptions/)
  assert.match(wxml, /gearSlotSheet\.enchantOptions/)
  assert.match(wxml, /bindtap="selectGearVariant"/)
  assert.match(wxml, /bindtap="selectGearSocketOption"/)
  assert.match(wxml, /bindtap="selectGearEnchantOption"/)
  assert.match(wxml, /bindtap="applyGearCandidate"/)
  assert.match(wxml, /bindtap="saveGearTemplate"/)
  assert.match(wxml, /bindtap="openGearCommunityTemplates"/)
  assert.match(wxml, /bindtap="resetGearSelection"/)
  assert.match(wxml, /gearCommunityTemplateSheet\.visible/)
  assert.match(wxml, /wx:for="\{\{activeGearCommunityTemplates\}\}"/)
  assert.match(wxml, /bindtap="applyGearCommunityTemplate"/)
  const gearPanelMarkup = wxml.match(/<view class="module-panel gear-panel"[\s\S]*?<view class="module-panel stats-panel"/)
  assert.ok(gearPanelMarkup)
  assert.doesNotMatch(gearPanelMarkup[0], /class="insight-list"/)
  assert.match(wxml, /class="gear-template-actions" wx:if="\{\{!gearInitialLoading\}\}"/)
  assert.match(wxml, /class="source-box" wx:if="\{\{activeDetail && activeQueryKey != 'gear'\}\}"/)
  assert.ok(wxml.indexOf('bindtap="saveGearTemplate"') > wxml.indexOf('class="gear-slot-grid"'))
  assert.doesNotMatch(css, /\.gear-stat-panel/)
  assert.match(css, /\.gear-slot-grid/)
  assert.match(css, /\.gear-slot-card\s*\{[\s\S]*min-height:\s*176rpx;[\s\S]*padding:\s*12rpx;/)
  assert.match(css, /\.gear-loading-state/)
  assert.match(css, /\.gear-slot-sheet/)
  assert.match(css, /\.gear-sheet-filter/)
  assert.match(css, /\.gear-variant-chip/)
  assert.match(css, /\.gear-mod-option/)
  assert.match(css, /\.gear-template-actions\s*\{[\s\S]*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\);/)
  assert.match(css, /\.gear-community-template-sheet/)
  assert.match(css, /\.gear-template-action-button\.primary\s*\{[\s\S]*grid-column:\s*1\s*\/\s*-1;/)
})

test('gear detail hides fallback insight while first gear payload is loading', () => {
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGear: () => new Promise(() => {})
  })
  const page = {
    data: {
      selectedDetail: {
        details: {
          talents: { coreTalents: [], importCode: '' },
          gear: {
            sourceName: 'Mythicstats + Wowhead',
            publishedAt: '2026-06-09',
            items: ['old fallback gear insight']
          }
        }
      },
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: {},
      gearSlotRows: [],
      gearSelectionKey: '',
      gearSlotSheet: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.loadWebsimGearForSelection.call(page, {
    selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' }
  })

  assert.equal(page.data.gearLoading, true)
  assert.equal(page.data.gearInitialLoading, true)
})

test('gear slot candidate count matches selectable deduped equipment rows', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const item = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '250060',
    id: '250060',
    displayName: '虚空粉碎者的面纱',
    iconUrl: 'https://render.worldofwarcraft.com/us/icons/56/inv_helm_cloth_raidmage_j_01.jpg',
    ilevel: '289',
    bonus_id: '1808/13575',
    simcReady: true
  }
  const gearPayload = {
    slots: [{ slot: 'head', simcSlot: 'head', label: '头部' }],
    replacementCandidates: [{
      slot: 'head',
      simcSlot: 'head',
      label: '头部',
      items: [
        { ...item, source: 'MID1_Mage_Frost_Frostfire' },
        { ...item, source: 'MID1_Mage_Frost_Spellslinger' },
        { ...item, source: 'MID1_Mage_Frost_Frostfire_Copy' }
      ]
    }],
    equippedSet: { head: item },
    slotReadiness: { head: { status: 'verified', reason: '可写入 SimC profile' } },
    readiness: {},
    statSnapshot: { statStatus: 'blocked', blockers: [] }
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedGearBySlot: { head: item }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'head' } } })

  assert.equal(page.data.gearSlotSheet.candidates.length, 1)
  assert.equal(page.data.gearSlotRows[0].candidateCount, page.data.gearSlotSheet.candidates.length)
  assert.equal(page.data.gearSlotRows[0].gameAsset.iconUrl, item.iconUrl)
  assert.equal(page.data.gearSlotSheet.candidates[0].gameAsset.iconUrl, item.iconUrl)
})

test('gear slot sheet applies variant socket and enchant fields into selected gear', async () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const item = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '250777',
    id: '250777',
    displayName: 'Catalog Hood',
    sourceType: 'raid',
    sources: [{ label: 'Vault Mage - Arcane Vault', sourceType: 'raid' }],
    defaultVariantKey: 'heroic-707',
    variants: [
      {
        key: 'heroic-707',
        label: 'Heroic 707',
        itemLevel: 707,
        simcOptions: { bonus_id: '12345' },
        status: 'verified'
      },
      {
        key: 'mythic-710',
        label: 'Mythic 710',
        itemLevel: 710,
        simcOptions: { bonus_id: '67890' },
        status: 'verified'
      }
    ],
    socketOptions: [{
      id: 'socket-gem-240983',
      name: 'Quick Gem',
      simcOptions: { gem_id: '240983', gem_ilevel: '710' },
      status: 'verified'
    }],
    enchantOptions: [{
      id: 'enchant-8017',
      name: 'Radiant Enchant',
      simcOptions: { enchant_id: '8017' },
      status: 'verified'
    }],
    simcReady: true
  }
  const gearPayload = {
    slots: [{ slot: 'head', simcSlot: 'head', label: 'Head' }],
    replacementCandidates: [{
      slot: 'head',
      simcSlot: 'head',
      label: 'Head',
      items: [item]
    }],
    equippedSet: {},
    slotReadiness: {},
    readiness: {},
    statSnapshot: { statStatus: 'blocked', blockers: [] }
  }
  let refreshCalls = 0
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    },
    refreshGearStats() {
      refreshCalls += 1
      return Promise.resolve()
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'head' } } })
  pageConfig.selectGearVariant.call(page, { currentTarget: { dataset: { key: 'mythic-710' } } })
  pageConfig.selectGearSocketOption.call(page, { currentTarget: { dataset: { id: 'socket-gem-240983' } } })
  pageConfig.selectGearEnchantOption.call(page, { currentTarget: { dataset: { id: 'enchant-8017' } } })
  await pageConfig.applyGearCandidate.call(page)

  const selected = page.data.selectedGearBySlot.head
  assert.equal(selected.variantKey, 'mythic-710')
  assert.equal(selected.ilevel, 710)
  assert.equal(selected.bonus_id, '67890')
  assert.equal(selected.gem_id, '240983')
  assert.equal(selected.gem_ilevel, '710')
  assert.equal(selected.enchant_id, '8017')
  assert.equal(page.data.gearSlotSheet.visible, false)
  assert.equal(refreshCalls, 0)
})

test('gear detail does not request stat snapshot when gear payload loads', async () => {
  let refreshCalls = 0
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGear: () => Promise.resolve({
      payload: {
        classKey: 'mage',
        specKey: 'frost',
        slots: canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot })),
        replacementCandidates: [],
        equippedSet: completeGearSelection(),
        slotReadiness: {},
        readiness: {
          fullReady: true,
          warnings: [],
          itemLevel: { key: 'itemLevel', label: '装备等级', value: '0', rawValue: 0 }
        },
        statSnapshot: {
          statStatus: 'blocked',
          blockers: ['装备模拟数据暂不可用，等待后端返回槽位结构。'],
          itemLevel: { key: 'itemLevel', label: '装备等级', value: '0', rawValue: 0 }
        }
      }
    })
  })
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: {},
      gearSelectionKey: '',
      gearSlotSheet: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    },
    refreshGearStats() {
      refreshCalls += 1
      return Promise.resolve()
    }
  }

  pageConfig.loadWebsimGearForSelection.call(page, {
    selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' }
  })
  await new Promise((resolve) => setImmediate(resolve))

  assert.equal(refreshCalls, 0)
  assert.equal(page.data.gearSlotRows.length, canonicalGearSlots.length)
})

test('gear template save requires all canonical slots and stores neutral complete status', () => {
  const savedTemplates = []
  const toasts = []
  const pageConfig = loadBuildsDetailPageConfig({ savedTemplates, toasts })
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const incompleteSelection = completeGearSelection(canonicalGearSlots.slice(0, -1))
  const completeSelection = completeGearSelection()
  const page = {
    data: {
      selectedDetail: { className: '法师', specName: '冰霜', details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      selectedSpec: { className: '法师', title: '冰霜', specName: '冰霜', websimClassKey: 'mage', websimSpecKey: 'frost' },
      activeQueryKey: 'gear',
      gearPayload: {
        slots,
        maxLevel: 90,
        gearSchemaRevision: 'websim-gear-simulator-v1'
      },
      selectedGearBySlot: incompleteSelection,
      selectedGearTemplateScenarioIndex: 0
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.saveGearTemplate.call(page)

  assert.equal(savedTemplates.length, 0)
  assert.match(toasts.at(-1).title, /请补齐 16 个装备槽位/)

  page.data.selectedGearBySlot = completeSelection
  pageConfig.saveGearTemplate.call(page)

  assert.equal(savedTemplates.length, 1)
  assert.equal(savedTemplates[0].status, 'complete')
  assert.equal(savedTemplates[0].statusLabel, '完整配置')
  assert.equal(Array.isArray(savedTemplates[0].simcLines), true)
  assert.equal(savedTemplates[0].simcLines.length, 0)
  assert.equal(savedTemplates[0].rawString.split('\n').length, canonicalGearSlots.length)
})

test('gear reset restores the backend equipped baseline', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const baseline = completeGearSelection(['head', 'neck'])
  const modifiedHead = { ...baseline.head, itemId: '299999', id: '299999', displayName: 'Modified Head' }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: ['head', 'neck'].map((slot) => ({ slot, simcSlot: slot, label: slot })),
        equippedSet: baseline,
        replacementCandidates: [],
        slotReadiness: {},
        readiness: {}
      },
      selectedGearBySlot: {
        ...baseline,
        head: modifiedHead
      },
      gearSlotSheet: { visible: true },
      gearCommunityTemplateSheet: { visible: true }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.resetGearSelection.call(page)

  assert.equal(page.data.selectedGearBySlot.head.itemId, baseline.head.itemId)
  assert.equal(page.data.selectedGearBySlot.neck.itemId, baseline.neck.itemId)
  assert.equal(page.data.gearSlotSheet.visible, false)
  assert.equal(page.data.gearCommunityTemplateSheet.visible, false)
})

test('gear community template overlays template slots onto baseline only', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const baseline = completeGearSelection(['head', 'neck'])
  const previousNeck = { ...baseline.neck, itemId: '288888', id: '288888', displayName: 'Previous Neck' }
  const templateHead = { ...baseline.head, itemId: '277777', id: '277777', displayName: 'Community Head' }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: ['head', 'neck'].map((slot) => ({ slot, simcSlot: slot, label: slot })),
        equippedSet: baseline,
        replacementCandidates: [],
        slotReadiness: {},
        readiness: {}
      },
      selectedGearBySlot: {
        ...baseline,
        neck: previousNeck
      },
      activeGearCommunityTemplates: [{
        id: 'community-head',
        name: 'Community Head Template',
        canApplyGear: true,
        gearItems: [templateHead]
      }],
      gearCommunityTemplateSheet: { visible: true },
      gearSlotSheet: { visible: true }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.applyGearCommunityTemplate.call(page, { currentTarget: { dataset: { id: 'community-head' } } })

  assert.equal(page.data.selectedGearBySlot.head.itemId, templateHead.itemId)
  assert.equal(page.data.selectedGearBySlot.neck.itemId, baseline.neck.itemId)
  assert.equal(page.data.gearCommunityTemplateSheet.visible, false)
  assert.equal(page.data.gearSlotSheet.visible, false)
})

test('simc linkage derives talent and gear state from full specialization details', () => {
  const js = fs.readFileSync('pages/builds/detail.js', 'utf8')

  assert.match(js, /const talentDetail = detailForQuery\(selectedDetail,\s*'talents'\)/)
  assert.match(js, /buildTalentNodeRows\(talentDetail/)
  assert.match(js, /buildGearSlotRows/)
  assert.match(js, /websimClassKey/)
  assert.match(js, /websimSpecKey/)
})
