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
      source: '测试首领 - 测试副本',
      sources: [{ label: '测试首领 - 测试副本', sourceType: 'dungeon' }],
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

test('builds page uses the shared WoW specialization meta palette', () => {
  const wxml = fs.readFileSync('pages/builds/builds.wxml', 'utf8')
  const css = fs.readFileSync('pages/builds/builds.wxss', 'utf8')

  assert.match(wxml, /background="#111111"/)
  assert.match(wxml, /color="#FFFFFF"/)
  assert.match(css, /\.builds-shell[\s\S]*background:\s*#060606;/)
  assert.match(css, /\.builds-hero[\s\S]*#17120d/i)
  assert.match(css, /\.builds-hero[\s\S]*#f8b700/i)
  assert.match(css, /\.builds-hero[\s\S]*rgba\(139,\s*63,\s*245,\s*0\.16\)/i)
  assert.match(css, /\.query-card[\s\S]*border-radius:\s*12rpx;/)
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
  assert.match(css, /\.intel-swiper[\s\S]*height:\s*252rpx;/)
  assert.match(css, /\.intel-swiper\s+\.wx-swiper-dots[\s\S]*bottom:\s*10rpx;/)
  assert.match(css, /\.intel-card[\s\S]*height:\s*220rpx;/)
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
  assert.match(css, /\.toolbar-picker\s*\{[\s\S]*display:\s*flex;[\s\S]*align-items:\s*center;[\s\S]*min-height:\s*54rpx;[\s\S]*\}/)
  assert.match(css, /\.picker-label\s*\{[\s\S]*flex-shrink:\s*0;[\s\S]*\}/)
  assert.match(css, /\.picker-value\s*\{[\s\S]*margin-top:\s*0;[\s\S]*text-overflow:\s*ellipsis;[\s\S]*\}/)
  assert.match(css, /\.tree-tab\s*\{[\s\S]*display:\s*flex;[\s\S]*align-items:\s*center;[\s\S]*min-height:\s*64rpx;[\s\S]*\}/)
  assert.match(css, /\.tree-tab-subtitle\s*\{[\s\S]*flex:\s*1;[\s\S]*text-overflow:\s*ellipsis;[\s\S]*\}/)
  assert.match(wxml, /class="active-tree-separator"/)
  assert.match(css, /\.active-tree-head\s*\{[\s\S]*align-items:\s*center;[\s\S]*padding:\s*12rpx 18rpx;[\s\S]*\}/)
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
  assert.match(css, /\.talent-page-content\s*\{[\s\S]*padding:\s*20rpx 22rpx 208rpx;[\s\S]*\}/)
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
  assert.match(css, /\.template-save-sheet\s*\{[\s\S]*padding:\s*16rpx 22rpx calc\(36rpx \+ env\(safe-area-inset-bottom\)\);[\s\S]*box-sizing:\s*border-box;[\s\S]*\}/)
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
  assert.match(js, /buildGearAttributePanel/)
  assert.match(js, /gearInitialLoading/)
  assert.doesNotMatch(js, /gearStatSnapshot/)
  assert.doesNotMatch(js, /gearStatBlockers/)
  assert.match(js, /loadWebsimGearForSelection/)
  assert.doesNotMatch(js, /refreshGearStats/)
  assert.match(js, /openGearSlotSheet\(event\)/)
  assert.match(js, /selectGearCandidate\(event\)/)
  assert.match(js, /setGearCandidateFilter\(event\)/)
  assert.match(js, /selectGearVariant\(event\)/)
  assert.doesNotMatch(js, /selectGearSocketOption\(event\)/)
  assert.doesNotMatch(js, /selectGearEnchantOption\(event\)/)
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
  assert.match(js, /openGearEnhancementSheet\(\)/)
  assert.match(js, /selectGearEnhancementOption\(event\)/)
  assert.match(js, /enhancementBySlot/)
  assert.match(js, /gearEnhancementSheet/)
  assert.match(js, /canonicalGearTemplateLines/)
  assert.match(js, /syncBuildTemplate/)
  assert.doesNotMatch(wxml, /class="gear-status-strip"/)
  assert.doesNotMatch(wxml, /class="gear-template-picker"/)
  assert.doesNotMatch(wxml, /class="gear-stat-panel"/)
  assert.doesNotMatch(wxml, /gearStatSnapshot\.statStatus/)
  assert.doesNotMatch(wxml, /gearStatBlockers/)
  assert.match(wxml, /class="gear-attribute-panel"/)
  assert.match(wxml, /gearAttributePanel\.primaryStat/)
  assert.match(wxml, /gearAttributePanel\.enhancementRows/)
  assert.doesNotMatch(wxml, /gearAttributePanel\.resourceRows/)
  assert.match(wxml, /class="gear-slot-grid"/)
  assert.match(wxml, /wx:for="\{\{gearSlotRows\}\}"/)
  assert.ok(wxml.indexOf('class="gear-attribute-panel"') < wxml.indexOf('class="gear-slot-grid"'))
  assert.ok(wxml.indexOf('class="gear-attribute-action"') > wxml.indexOf('class="gear-attribute-panel"'))
  assert.ok(wxml.indexOf('class="gear-attribute-action"') < wxml.indexOf('class="gear-slot-grid"'))
  const gearSlotGridMarkup = wxml.match(/<view class="gear-slot-grid">[\s\S]*?<view class="gear-loading-state"/)
  assert.ok(gearSlotGridMarkup)
  assert.doesNotMatch(gearSlotGridMarkup[0], /gear-slot-status/)
  assert.doesNotMatch(gearSlotGridMarkup[0], /gear-slot-footer/)
  assert.doesNotMatch(gearSlotGridMarkup[0], /item\.statusLabel/)
  assert.doesNotMatch(gearSlotGridMarkup[0], /item\.trustLabel/)
  assert.doesNotMatch(wxml, /source-strip/)
  assert.match(wxml, /class="gear-loading-state" wx:if="\{\{gearInitialLoading\}\}"/)
  assert.match(wxml, /class="detail-desc" wx:if="\{\{activeQuery\.desc && activeQueryKey != 'gear'\}\}"/)
  assert.match(wxml, /class="gear-icon"/)
  assert.match(wxml, /item\.gameAsset\.iconUrl/)
  assert.doesNotMatch(wxml, /item\.iconUrl/)
  assert.match(wxml, /item\.displayName/)
  assert.doesNotMatch(wxml, /gearTrustSummaryText/)
  assert.doesNotMatch(wxml, /class="gear-trust-summary"/)
  assert.doesNotMatch(wxml, /candidateCount/)
  assert.doesNotMatch(wxml, /个候选/)
  assert.match(wxml, /class="gear-apply-message"/)
  assert.match(wxml, /gearSlotSheet\.activeTrustText/)
  assert.match(wxml, /class="gear-config-stack"/)
  assert.match(wxml, /class="gear-variant-track-grid"/)
  assert.match(wxml, /class="gear-variant-track-card /)
  assert.match(wxml, /class="gear-variant-track-name"/)
  assert.match(wxml, /class="gear-variant-track-level"/)
  assert.doesNotMatch(wxml, /class="gear-section-optional"/)
  assert.doesNotMatch(wxml, /class="gear-mod-section"/)
  assert.doesNotMatch(wxml, /宝石插槽/)
  assert.doesNotMatch(wxml, /gearSlotSheet\.activeTrustLabel/)
  assert.doesNotMatch(wxml, /class="gear-sheet-active"/)
  assert.match(wxml, /item\.blockerLabel/)
  assert.doesNotMatch(wxml, /item\.source\s*(\|\||\}\})/)
  assert.doesNotMatch(wxml, /item\.itemId/)
  assert.doesNotMatch(wxml, /gearStatSnapshot\.itemLevel\.value/)
  assert.match(wxml, /bindtap="openGearSlotSheet"/)
  assert.match(wxml, /gearSlotSheet\.visible/)
  assert.match(wxml, /gearSlotSheet\.filters/)
  assert.match(wxml, /wx:for="\{\{gearSlotSheet\.candidates\}\}"/)
  assert.match(wxml, /bindtap="selectGearCandidate"/)
  assert.match(wxml, /gearSlotSheet\.variantOptions/)
  assert.match(wxml, /gearSlotSheet\.variantOptions\.length/)
  assert.doesNotMatch(wxml, /gearSlotSheet\.variantOptions\.length > 1/)
  assert.doesNotMatch(wxml, /配置来源/)
  assert.doesNotMatch(wxml, /实装观测/)
  assert.doesNotMatch(wxml, /gearSlotSheet\.socketOptions/)
  assert.doesNotMatch(wxml, /gearSlotSheet\.enchantOptions/)
  assert.match(wxml, /bindtap="selectGearVariant"/)
  assert.doesNotMatch(wxml, /bindtap="selectGearSocketOption"/)
  assert.doesNotMatch(wxml, /bindtap="selectGearEnchantOption"/)
  assert.match(wxml, /bindtap="applyGearCandidate"/)
  assert.match(wxml, /bindtap="saveGearTemplate"/)
  assert.doesNotMatch(wxml, /class="gear-template-action-button enhance"/)
  assert.match(wxml, /bindtap="openGearEnhancementSheet"/)
  assert.match(wxml, /gearEnhancementSheet\.visible/)
  assert.match(wxml, /gearEnhancementSheet\.gemRows/)
  assert.match(wxml, /gearEnhancementSheet\.enchantRows/)
  assert.match(wxml, /gearEnhancementSheet\.embellishmentRows/)
  assert.match(wxml, /bindtap="openGearCommunityTemplates"/)
  assert.match(wxml, /bindtap="resetGearSelection"/)
  assert.match(wxml, /gearDataWarningText/)
  assert.match(wxml, /disabled="\{\{gearDataFallback \|\| gearTemplateSaving\}\}"/)
  assert.match(wxml, /class="gear-template-action-button import"/)
  assert.match(wxml, /disabled="\{\{gearDataFallback\}\}"/)
  assert.match(wxml, /gearCommunityTemplateSheet\.visible/)
  assert.match(wxml, /wx:for="\{\{activeGearCommunityTemplates\}\}"/)
  assert.match(wxml, /gear-community-template-title">\{\{item\.displayName \|\| item\.name\}\}/)
  assert.match(wxml, /\{\{item\.displaySourceName \|\| item\.sourceName\}\} · \{\{item\.slotCoverageLabel\}\}/)
  assert.match(wxml, /bindtap="applyGearCommunityTemplate"/)
  const gearPanelMarkup = wxml.match(/<view class="module-panel gear-panel"[\s\S]*?<view class="module-panel stats-panel"/)
  assert.ok(gearPanelMarkup)
  assert.doesNotMatch(gearPanelMarkup[0], /class="insight-list"/)
  assert.match(wxml, /class="gear-template-actions" wx:if="\{\{!gearInitialLoading\}\}"/)
  assert.match(wxml, /class="source-box" wx:if="\{\{activeDetail && activeQueryKey != 'gear'\}\}"/)
  assert.ok(wxml.indexOf('bindtap="saveGearTemplate"') > wxml.indexOf('class="gear-slot-grid"'))
  assert.doesNotMatch(css, /\.gear-stat-panel/)
  assert.match(css, /\.gear-attribute-panel/)
  assert.match(css, /\.gear-attribute-action/)
  assert.match(css, /\.gear-attribute-enhancement-row/)
  assert.match(css, /\.gear-attribute-grid\s*\{[\s\S]*grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\);/)
  assert.match(css, /\.gear-slot-grid/)
  assert.match(css, /\.gear-slot-grid\s*\{[\s\S]*gap:\s*8rpx;[\s\S]*margin-top:\s*12rpx;/)
  assert.match(css, /\.gear-slot-card\s*\{[\s\S]*min-height:\s*118rpx;[\s\S]*padding:\s*10rpx;/)
  assert.match(css, /\.gear-slot-card \.gear-name\s*\{[\s\S]*font-size:\s*22rpx;[\s\S]*line-height:\s*1\.28;/)
  assert.match(css, /\.gear-request-alert/)
  assert.doesNotMatch(css, /\.gear-trust-summary/)
  assert.match(css, /\.gear-loading-state/)
  assert.match(css, /\.gear-slot-sheet/)
  assert.match(css, /\.gear-sheet-filter/)
  assert.match(css, /\.gear-sheet-filter-row\s*\{[\s\S]*grid-template-columns:\s*repeat\(5,\s*minmax\(0,\s*1fr\)\);/)
  assert.match(css, /\.gear-config-stack/)
  assert.match(css, /\.gear-variant-track-grid\s*\{[\s\S]*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\);/)
  assert.match(css, /\.gear-variant-track-card/)
  assert.match(css, /\.gear-apply-message/)
  assert.doesNotMatch(css, /\.gear-config-column-side/)
  assert.doesNotMatch(css, /\.gear-mod-option/)
  assert.doesNotMatch(css, /\.gear-section-optional/)
  assert.doesNotMatch(css, /\.gear-mod-list/)
  assert.match(css, /\.gear-template-actions\s*\{[\s\S]*display:\s*flex;[\s\S]*align-items:\s*center;[\s\S]*gap:\s*8rpx;/)
  assert.match(css, /\.gear-template-action-button\s*\{[\s\S]*width:\s*0;[\s\S]*box-sizing:\s*border-box;[\s\S]*display:\s*flex;[\s\S]*white-space:\s*nowrap;[\s\S]*overflow:\s*hidden;/)
  assert.match(css, /\.gear-template-action-button\.import\s*\{[\s\S]*flex-grow:\s*1\.35;[\s\S]*\}/)
  assert.match(css, /\.gear-template-action-button\[disabled\]/)
  assert.match(css, /\.gear-enhancement-sheet/)
  assert.match(css, /\.gear-enhancement-option\.disabled/)
  const gearActionsCss = css.match(/\.gear-template-actions\s*\{[^}]*\}/)
  assert.ok(gearActionsCss)
  assert.doesNotMatch(gearActionsCss[0], /grid-template-columns/)
  assert.match(css, /\.gear-community-template-sheet/)
  assert.match(css, /\.gear-community-template-card\.source-reference/)
  const gearCommunityCardCss = css.match(/\.gear-community-template-card\s*\{[^}]*\}/)
  assert.ok(gearCommunityCardCss)
  assert.match(gearCommunityCardCss[0], /display:\s*flex;/)
  assert.match(gearCommunityCardCss[0], /flex-direction:\s*column;/)
  assert.match(gearCommunityCardCss[0], /gap:\s*14rpx;/)
  assert.doesNotMatch(gearCommunityCardCss[0], /grid-template-columns:/)
  const gearCommunitySideCss = css.match(/\.gear-community-template-side\s*\{[^}]*\}/)
  assert.ok(gearCommunitySideCss)
  assert.match(gearCommunitySideCss[0], /min-width:\s*0;/)
  assert.match(gearCommunitySideCss[0], /display:\s*flex;/)
  assert.match(gearCommunitySideCss[0], /flex-direction:\s*column;/)
  assert.match(gearCommunitySideCss[0], /gap:\s*10rpx;/)
  assert.match(gearCommunitySideCss[0], /align-items:\s*stretch;/)
  const gearCommunityApplyCss = css.match(/\.gear-community-template-apply\s*\{[^}]*\}/)
  assert.ok(gearCommunityApplyCss)
  assert.match(gearCommunityApplyCss[0], /width:\s*100%;/)
  assert.match(gearCommunityApplyCss[0], /max-width:\s*100%;/)
  assert.match(gearCommunityApplyCss[0], /box-sizing:\s*border-box;/)
  assert.match(gearCommunityApplyCss[0], /display:\s*flex;/)
  assert.match(gearCommunityApplyCss[0], /white-space:\s*nowrap;/)
  assert.match(gearCommunityApplyCss[0], /overflow:\s*hidden;/)
  const primaryGearActionCss = css.match(/\.gear-template-action-button\.primary\s*\{[^}]*\}/)
  assert.ok(primaryGearActionCss)
  assert.doesNotMatch(primaryGearActionCss[0], /grid-column/)
})

test('gear detail summarizes selected equipment attributes above the slot grid', async () => {
  const selectedGear = completeGearSelection(['head', 'chest', 'finger1'])
  selectedGear.head = {
    ...selectedGear.head,
    ilevel: 298,
    statSummary: '智力 120；耐力 240；急速 30；暴击 20；精通 10；全能 5；护甲 100'
  }
  selectedGear.chest = {
    ...selectedGear.chest,
    ilevel: 289,
    statSummary: '敏捷 or 智力 80；耐力 160；急速 15；精通 7；护甲 80'
  }
  selectedGear.finger1 = {
    ...selectedGear.finger1,
    ilevel: 286,
    statSummary: '力量/敏捷/智力 50；耐力 90；暴击 12；全能 6',
    modCapabilities: { hasSocket: true, canEnchant: true, canEmbellish: false }
  }
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGear: () => Promise.resolve({
      payload: {
        classKey: 'mage',
        specKey: 'frost',
        slots: canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot })),
        replacementCandidates: canonicalGearSlots.map((slot) => ({
          slot,
          simcSlot: slot,
          label: slot,
          items: [],
          socketOptions: slot === 'finger1'
            ? [{ id: 'gem-rank-two', label: '迅捷宝石', status: 'verified', simcOptions: { gem_id: '240983' }, payload: { qualityRank: 2 } }]
            : [],
          enchantOptions: slot === 'finger1'
            ? [{ id: 'enchant-rank-two', label: '戒指附魔', status: 'verified', simcOptions: { enchant_id: '7334' }, payload: { qualityRank: 2 } }]
            : []
        })),
        equippedSet: selectedGear,
        slotReadiness: {},
        readiness: { fullReady: false },
        communityTemplates: []
      }
    })
  })
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: {},
      enhancementBySlot: {},
      gearSelectionKey: '',
      gearSlotRows: [],
      gearSlotSheet: {},
      gearEnhancementSheet: { visible: false },
      gearCommunityTemplateSheet: { visible: false }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.loadWebsimGearForSelection.call(page, {
    selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' }
  })
  await new Promise((resolve) => setImmediate(resolve))

  const panel = page.data.gearAttributePanel
  assert.equal(panel.visible, true)
  assert.equal(panel.summary, '已选 3/16 槽')
  assert.equal(panel.itemLevel.value, '291')
  assert.equal(panel.primaryStat.label, '智力')
  assert.equal(panel.primaryStat.value, '250')
  assert.equal(panel.resourceRows, undefined)
  assert.equal(panel.enhancementRows.find((row) => row.key === 'embellishment').value, '0/2')
  assert.equal(panel.enhancementRows.find((row) => row.key === 'gem').value, '0/1')
  assert.equal(panel.enhancementRows.find((row) => row.key === 'enchant').value, '0/1')
  assert.equal(panel.statRows.find((row) => row.key === 'stamina').value, '490')
  assert.equal(panel.statRows.find((row) => row.key === 'haste').value, '45')
  assert.equal(panel.statRows.find((row) => row.key === 'crit').value, '32')
  assert.equal(panel.statRows.find((row) => row.key === 'mastery').value, '17')
  assert.equal(panel.statRows.find((row) => row.key === 'versatility').value, '11')
})

test('gear attribute panel maps hybrid primary stat labels to the active spec', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const page = {
    gearPayloadCache: {
      slots,
      replacementCandidates: [],
      equippedSet: {},
      slotReadiness: {},
      readiness: { fullReady: false }
    },
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots,
        replacementCandidates: [],
        equippedSet: {},
        slotReadiness: {},
        readiness: { fullReady: false }
      },
      selectedSpec: { websimClassKey: 'paladin', websimSpecKey: 'holy' },
      selectedGearBySlot: {
        head: {
          slot: 'head',
          simcSlot: 'head',
          itemId: '250101',
          displayName: 'Hybrid Helm',
          ilevel: 289,
          statSummary: '力量 or 智力 120；耐力 240'
        }
      },
      enhancementBySlot: {},
      gearEnhancementSheet: { visible: false },
      gearCommunityTemplateSheet: { visible: false },
      gearSlotSheet: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  assert.equal(page.data.gearAttributePanel.primaryStat.label, '智力')
  assert.equal(page.data.gearAttributePanel.primaryStat.value, '120')

  page.data.selectedSpec = { websimClassKey: 'rogue', websimSpecKey: 'subtlety' }
  page.data.selectedGearBySlot = {
    head: {
      slot: 'head',
      simcSlot: 'head',
      itemId: '250102',
      displayName: 'Hybrid Hood',
      ilevel: 289,
      statSummary: 'stragi 80；耐力 160'
    }
  }
  pageConfig.refreshDerivedState.call(page)
  assert.equal(page.data.gearAttributePanel.primaryStat.label, '敏捷')
  assert.equal(page.data.gearAttributePanel.primaryStat.value, '80')
})

test('gear enhancement sheet filters configurable slots and disables extra embellishments at the cap', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection()
  selection.finger1 = {
    ...selection.finger1,
    modCapabilities: { hasSocket: true, canEnchant: true, canEmbellish: false }
  }
  selection.finger2 = {
    ...selection.finger2,
    modCapabilities: { hasSocket: false, canEnchant: true, canEmbellish: false }
  }
  selection.wrist = {
    ...selection.wrist,
    sourceType: 'crafted',
    modCapabilities: { hasSocket: false, canEnchant: true, canEmbellish: true }
  }
  selection.back = {
    ...selection.back,
    embellishment: 'dawnthread_lining'
  }
  selection.chest = {
    ...selection.chest,
    intrinsicEmbellishment: 'duskthread_lining'
  }
  selection.hands = {
    ...selection.hands,
    sourceType: 'dungeon',
    modCapabilities: { hasSocket: false, canEnchant: false, canEmbellish: false }
  }
  const gearPayload = {
    slots,
    replacementCandidates: [
      {
        slot: 'finger1',
        simcSlot: 'finger1',
        label: 'finger1',
        items: [],
        socketOptions: [
          {
            id: 'gem-rank-two',
            label: '迅捷宝石',
            status: 'verified',
            simcOptions: { gem_id: '240983', gem_ilevel: '707' },
            payload: { qualityRank: 2 }
          }
        ],
        enchantOptions: [
          {
            id: 'enchant-rank-two',
            label: '戒指附魔',
            status: 'verified',
            simcOptions: { enchant_id: '7334' },
            payload: { qualityRank: 2 }
          }
        ]
      },
      {
        slot: 'finger2',
        simcSlot: 'finger2',
        label: 'finger2',
        items: [],
        socketOptions: [
          {
            id: 'gem-rank-two-finger2',
            label: '迅捷宝石',
            status: 'verified',
            simcOptions: { gem_id: '240983', gem_ilevel: '707' },
            payload: { qualityRank: 2 }
          }
        ]
      },
      {
        slot: 'wrist',
        simcSlot: 'wrist',
        label: 'wrist',
        items: [],
        embellishmentOptions: [
          {
            id: 'embellishment-blue-silken-lining',
            label: '蓝色丝质内衬',
            status: 'verified',
            simcOptions: { embellishment: 'blue_silken_lining' },
            payload: { qualityRank: 2, simcKey: 'blue_silken_lining' }
          }
        ]
      },
      {
        slot: 'hands',
        simcSlot: 'hands',
        label: 'hands',
        items: [],
        embellishmentOptions: [
          {
            id: 'embellishment-hands',
            label: '蓝色丝质内衬',
            status: 'verified',
            simcOptions: { embellishment: 'blue_silken_lining' },
            payload: { qualityRank: 2, simcKey: 'blue_silken_lining' }
          }
        ]
      }
    ],
    equippedSet: {},
    slotReadiness: {},
    readiness: { fullReady: true }
  }
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: selection,
      enhancementBySlot: {},
      gearEnhancementSheet: { visible: false }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  assert.equal(page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'gem').value, '0/1')
  pageConfig.openGearEnhancementSheet.call(page)

  assert.equal(page.data.gearEnhancementSheet.visible, true)
  assert.equal(JSON.stringify(page.data.gearEnhancementSheet.gemRows.map((row) => row.slot)), JSON.stringify(['finger1']))
  assert.equal(JSON.stringify(page.data.gearEnhancementSheet.enchantRows.map((row) => row.slot)), JSON.stringify(['finger1']))
  assert.equal(JSON.stringify(page.data.gearEnhancementSheet.embellishmentRows.map((row) => row.slot)), JSON.stringify(['wrist']))
  assert.equal(page.data.gearEnhancementSheet.embellishmentUsed, 2)
  assert.equal(page.data.gearEnhancementSheet.embellishmentMax, 2)
  assert.equal(page.data.gearEnhancementSheet.embellishmentRows[0].options[0].disabled, true)

  pageConfig.selectGearEnhancementOption.call(page, {
    currentTarget: { dataset: { slot: 'finger1', type: 'gem', id: 'gem-rank-two' } }
  })
  assert.equal(page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'gem').value, '1/1')
})

test('gear community templates derive readable names from class spec hero and source', async () => {
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGear: () => Promise.resolve({
      payload: {
        classKey: 'mage',
        specKey: 'frost',
        slots: canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot })),
        replacementCandidates: canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot, items: [] })),
        equippedSet: {},
        slotReadiness: {},
        readiness: { fullReady: false },
        communityTemplates: [{
          id: 'simc-preset',
          classKey: 'mage',
          specKey: 'frost',
          name: 'MID1_Mage_Frost_Spellslinger',
          sourceKey: 'simc_preset',
          sourceName: 'SimC preset',
          status: 'complete',
          readySlotCount: 16,
          missingSlots: [],
          canApplyGear: true,
          gearItems: Object.values(completeGearSelection())
        }, {
          id: 'rio-observed',
          classLabel: '法师',
          specLabel: '冰霜',
          name: 'Raider.IO 观测装备 · 法师冰霜',
          sourceKey: 'observed_profile',
          sourceName: 'Raider.IO observed gear',
          status: 'partial',
          readySlotCount: 6,
          missingSlots: canonicalGearSlots.slice(6),
          canApplyGear: true,
          gearItems: Object.values(completeGearSelection(canonicalGearSlots.slice(0, 6)))
        }],
        communityTemplateSync: {
          sourceStatus: 'partial',
          sources: {},
          templates: { total: 2, verified: 1, partial: 1, blocked: 0 }
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
      gearSlotRows: [],
      gearSlotSheet: {},
      gearCommunityTemplateSheet: { visible: false }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.loadWebsimGearForSelection.call(page, {
    selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' }
  })
  await new Promise((resolve) => setImmediate(resolve))

  assert.equal(page.data.activeGearCommunityTemplates[0].displayName, '法师-冰霜-法术投射者 · SimC 预设')
  assert.equal(page.data.activeGearCommunityTemplates[0].displaySourceName, 'SimC 预设')
  assert.equal(page.data.activeGearCommunityTemplates[1].displayName, '法师-冰霜 · Raider.IO 观测')
  assert.equal(page.data.activeGearCommunityTemplates[1].displaySourceName, 'Raider.IO 观测')
})

test('gear detail marks backend fallback and blocks empty community imports', async () => {
  const toasts = []
  const pageConfig = loadBuildsDetailPageConfig({
    toasts,
    requestWebsimGear: () => Promise.resolve({
      fromFallback: true,
      error: 'missing api base url',
      payload: {
        classKey: 'mage',
        specKey: 'frost',
        slots: canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot })),
        replacementCandidates: canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot, items: [] })),
        equippedSet: {},
        slotReadiness: {},
        readiness: { fullReady: false },
        communityTemplates: [],
        communityTemplateSync: {
          sourceStatus: 'missing_credentials',
          sources: {},
          templates: { total: 0, verified: 0, partial: 0, blocked: 0 }
        },
        dataStatus: 'blocked'
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
      gearSlotRows: [],
      gearSlotSheet: {},
      gearCommunityTemplateSheet: { visible: false }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.loadWebsimGearForSelection.call(page, {
    selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' }
  })
  await new Promise((resolve) => setImmediate(resolve))
  pageConfig.openGearCommunityTemplates.call(page)

  assert.equal(page.data.gearDataFallback, true)
  assert.equal(page.data.gearSlotRows.length, canonicalGearSlots.length)
  assert.match(page.data.gearDataWarningText, /未连接后端 API/)
  assert.equal(page.data.gearCommunityTemplateSheet.visible, false)
  assert.match(toasts.at(-1).title, /未连接后端 API/)
})

test('gear detail keeps heavy candidate payload out of setData while preserving slot sheet candidates', async () => {
  const heavyCandidate = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '250060',
    id: '250060',
    displayName: '虚空粉碎者的面纱',
    iconUrl: 'https://render.worldofwarcraft.com/us/icons/56/inv_helm_cloth_raidmage_j_01.jpg',
    simcReady: true,
    source: '诸界吞噬者迪门修斯 - 法力熔炉：欧米伽',
    sources: Array.from({ length: 20 }, (_, index) => ({
      id: `source-${index}`,
      sourceType: index % 2 ? 'observed_profile' : 'raid',
      sourceLabel: `重型来源 ${index} ${'x'.repeat(120)}`
    })),
    socketOptions: Array.from({ length: 30 }, (_, index) => ({
      id: `socket-${index}`,
      name: `宝石 ${index} ${'y'.repeat(120)}`,
      simcOptions: { gem_id: String(240900 + index) },
      status: 'verified'
    })),
    variants: Array.from({ length: 8 }, (_, index) => ({
      key: `variant-${index}`,
      label: `变体 ${index}`,
      simcOptions: { bonus_id: String(12000 + index) }
    })),
    sourceRefs: Array.from({ length: 8 }, (_, index) => ({ id: `ref-${index}`, label: `引用 ${index}` })),
    observedProfileRefs: Array.from({ length: 8 }, (_, index) => ({ sourceName: `样本 ${index}` })),
    sourceReferences: Array.from({ length: 8 }, (_, index) => ({ id: `source-reference-${index}` })),
    rawItem: { payload: 'x'.repeat(2000) }
  }
  const gearPayload = {
    classKey: 'mage',
    specKey: 'frost',
    slots: [{ slot: 'head', simcSlot: 'head', label: '头部' }],
    replacementCandidates: [{
      slot: 'head',
      simcSlot: 'head',
      label: '头部',
      items: [heavyCandidate]
    }],
    equippedSet: { head: heavyCandidate },
    slotReadiness: {},
    readiness: { fullReady: false },
    communityTemplates: [],
    communityTemplateSync: {
      sourceStatus: 'partial',
      sources: {},
      templates: { total: 0, verified: 0, partial: 0, blocked: 0 }
    },
    catalogStatus: 'partial'
  }
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGear: () => Promise.resolve({ payload: gearPayload, fromFallback: false, error: '' })
  })
  const setDataUpdates = []
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: {},
      gearSelectionKey: '',
      gearSlotRows: [],
      gearSlotSheet: {},
      gearCommunityTemplateSheet: { visible: false }
    },
    setData(update) {
      setDataUpdates.push(update)
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.loadWebsimGearForSelection.call(page, {
    selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' }
  })
  await new Promise((resolve) => setImmediate(resolve))

  assert.ok(page.gearPayloadCache)
  assert.equal(page.gearPayloadCache.replacementCandidates[0].items[0].itemId, '250060')
  assert.equal(page.data.gearPayload.replacementCandidates, undefined)
  assert.equal(page.data.gearPayload.slotGroups, undefined)
  assert.equal(page.data.gearPayload.equippedSet, undefined)
  assert.equal(page.data.gearPayload.communityTemplates, undefined)
  assert.equal(page.data.selectedGearBySlot.head.sources, undefined)
  assert.equal(page.data.selectedGearBySlot.head.socketOptions, undefined)
  assert.equal(page.data.selectedGearBySlot.head.variants, undefined)
  assert.equal(page.data.selectedGearBySlot.head.sourceRefs, undefined)
  assert.equal(page.data.selectedGearBySlot.head.observedProfileRefs, undefined)
  assert.equal(page.data.selectedGearBySlot.head.sourceReferences, undefined)
  assert.equal(page.data.selectedGearBySlot.head.rawItem, undefined)
  assert.ok(setDataUpdates.every((update) => !update.gearPayload || !update.gearPayload.replacementCandidates))
  assert.ok(setDataUpdates.every((update) => !update.selectedGearBySlot || !update.selectedGearBySlot.head.sources))
  assert.ok(setDataUpdates.every((update) => !update.selectedGearBySlot || !update.selectedGearBySlot.head.variants))

  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'head' } } })
  assert.equal(page.data.gearSlotSheet.candidates.length, 1)
  assert.equal(page.data.gearSlotSheet.candidates[0].displayName, '虚空粉碎者的面纱')
  assert.equal(page.data.gearSlotSheet.candidates[0].sources, undefined)
  assert.equal(page.data.gearSlotSheet.candidates[0].socketOptions, undefined)
  assert.equal(page.data.gearSlotSheet.candidates[0].variants, undefined)
  assert.equal(page.data.gearSlotSheet.candidates[0].sourceRefs, undefined)
  assert.equal(page.data.gearSlotSheet.candidates[0].observedProfileRefs, undefined)
  assert.equal(page.data.gearSlotSheet.candidates[0].sourceReferences, undefined)
  assert.equal(page.data.gearSlotSheet.candidates[0].rawItem, undefined)
  assert.equal(page.data.gearSlotSheet.activeCandidate.sources, undefined)
  assert.equal(page.data.gearSlotSheet.activeCandidate.variants, undefined)
  assert.equal(page.data.gearSlotSheet.appliedCandidate.socketOptions, undefined)
  assert.equal(page.data.gearSlotSheet.appliedCandidate.variants, undefined)
  assert.equal(page.data.gearSlotSheet.allCandidates, undefined)
  assert.equal(page.gearSlotCandidateCache.head[0].sources.length, 20)
  assert.equal(page.gearSlotCandidateCache.head[0].socketOptions.length, 30)
  assert.equal(page.gearSlotCandidateCache.head[0].variants.length, 8)
})

test('gear detail keeps catalog health gaps out of the top summary', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots,
        replacementCandidates: [],
        equippedSet: {},
        slotReadiness: {},
        readiness: { fullReady: true },
        catalogStatus: 'partial',
        catalogHealthSummary: {
          sourcePendingItemCount: 131,
          missingStatObservedVariantCount: 303,
          socketMissingMetadataCount: 39,
          partialVariantCount: 519,
          sourcePendingExamples: [
            {
              itemId: '250777',
              displayName: '缺来源披风',
              slots: ['back'],
              sourceTypes: ['observed_profile']
            }
          ],
          partialVariantExamples: [
            {
              itemId: '250888',
              slot: 'head',
              sourceType: 'raid',
              sourceLabel: 'Void Captain - Voidspire',
              variantId: 'loot-partial-250888-head',
              blockers: ['missing deterministic SimC variant preset']
            }
          ]
        }
      },
      selectedGearBySlot: completeGearSelection()
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)

  assert.equal(Object.hasOwn(page.data, 'gearTrustSummaryText'), false)
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

test('gear slot rows keep selectable equipment rows out of card copy', () => {
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
  assert.equal(Object.hasOwn(page.data.gearSlotRows[0], 'candidateCount'), false)
  assert.equal(page.data.gearSlotRows[0].gameAsset.iconUrl, item.iconUrl)
  assert.equal(page.data.gearSlotSheet.candidates[0].gameAsset.iconUrl, item.iconUrl)
})

test('gear candidate detail treats observed profiles as evidence not drop source', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const observedOnly = {
    slot: 'finger1',
    simcSlot: 'finger1',
    itemId: '249920',
    id: '249920',
    displayName: '至暗之夜的眼眸',
    simcReady: true,
    ilevel: 289,
    bonus_id: '13440/6652/13577/12699/12806',
    source: 'Raider.IO CN observed mage frost',
    observedProfileRefs: [
      { sourceName: 'Raider.IO CN profile gear', classKey: 'mage', specKey: 'frost', itemLevel: 289 }
    ],
    sources: [
      { sourceType: 'observed_profile', sourceLabel: 'Raider.IO CN observed mage frost' }
    ]
  }
  const officialWithObserved = {
    slot: 'finger1',
    simcSlot: 'finger1',
    itemId: '251115',
    id: '251115',
    displayName: '分叉指环',
    simcReady: true,
    source: 'Raider.IO CN observed priest holy',
    sources: [
      { sourceType: 'observed_profile', sourceLabel: 'Raider.IO CN observed priest holy' },
      { sourceType: 'raid', sourceLabel: '无眠之心 - 法力熔炉：欧米伽' }
    ]
  }
  const gearPayload = {
    slots: [{ slot: 'finger1', simcSlot: 'finger1', label: '戒指' }],
    replacementCandidates: [{
      slot: 'finger1',
      simcSlot: 'finger1',
      label: '戒指',
      items: [observedOnly, officialWithObserved]
    }],
    equippedSet: {},
    slotReadiness: {},
    readiness: {},
    statSnapshot: { statStatus: 'blocked', blockers: [] }
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'finger1' } } })

  const firstSource = page.data.gearSlotSheet.candidates[0].detailRows.find((row) => row.label === '掉落来源')
  const secondSource = page.data.gearSlotSheet.candidates[1].detailRows.find((row) => row.label === '掉落来源')
  assert.equal(page.data.gearSlotSheet.candidates[0].source, '来源待补充')
  assert.equal(page.data.gearSlotSheet.candidates[0].statusLabel, '来源待补')
  assert.equal(page.data.gearSlotSheet.candidates[0].trustLabel, '来源待补')
  assert.equal(page.data.gearSlotSheet.activeTrustLabel, '来源待补')
  assert.match(page.data.gearSlotSheet.activeTrustText, /掉落来源待补充/)
  assert.equal(firstSource.value, '来源待补充')
  assert.equal(page.data.gearSlotSheet.candidates[0].detailRows.some((row) => row.label === '实装观测'), false)
  assert.equal(secondSource.value, '无眠之心 - 法力熔炉：欧米伽')
})

test('gear slot rows enrich sparse equipped items from matching candidates', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const sparseEquipped = {
    slot: 'back',
    simcSlot: 'back',
    itemId: '258575',
    id: '258575',
    displayName: '刚鳞大氅',
    simcReady: true,
    ilevel: 289,
    bonus_id: '6652/13335',
    source: 'SimulationCraft preset: MID1_Mage_Frost_Frostfire',
    sourceType: 'simc_preset',
    sources: [
      { sourceType: 'simc_preset', sourceLabel: 'SimulationCraft preset: MID1_Mage_Frost_Frostfire' }
    ],
    statDisplayStatus: 'pending_current_variant'
  }
  const enrichedCandidate = {
    ...sparseEquipped,
    source: '兰吉特 - 通天峰',
    sourceType: 'dungeon',
    sources: [
      { sourceType: 'dungeon', label: '兰吉特 - 通天峰' },
      { sourceType: 'simc_preset', sourceLabel: 'SimulationCraft preset: MID1_Mage_Frost_Frostfire' }
    ],
    statSummary: '力量/敏捷/智力 70；耐力 995；暴击 50；精通 42',
    statDisplayStatus: 'verified_variant'
  }
  const gearPayload = {
    slots: [{ slot: 'back', simcSlot: 'back', label: '背部' }],
    replacementCandidates: [{
      slot: 'back',
      simcSlot: 'back',
      label: '背部',
      items: [enrichedCandidate]
    }],
    equippedSet: { back: sparseEquipped },
    slotReadiness: {},
    readiness: {},
    statSnapshot: { statStatus: 'blocked', blockers: [] }
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedGearBySlot: { back: sparseEquipped }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)

  const row = page.data.gearSlotRows[0]
  assert.equal(row.source, '兰吉特 - 通天峰')
  assert.equal(row.statusLabel, '已配置')
  assert.equal(row.trustLabel, '可保存')
  assert.doesNotMatch(row.reason, /来源待补/)
})

test('gear candidate detail separates SimulationCraft preset from drop source', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const simcPresetOnly = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '268283',
    id: '268283',
    displayName: '溃烂之花冠冕',
    simcReady: true,
    ilevel: 298,
    bonus_id: '6652/12667/13577/13335/13786',
    source: 'SimulationCraft preset: MID1_Rogue_Outlaw_Fatebound',
    sourceType: 'simc_preset',
    sources: [
      { sourceType: 'simc_preset', sourceLabel: 'SimulationCraft preset: MID1_Rogue_Outlaw_Fatebound' }
    ],
    statSummary: '敏捷 or 智力 124；耐力 1768'
  }
  const gearPayload = {
    slots: [{ slot: 'head', simcSlot: 'head', label: '头部' }],
    replacementCandidates: [{
      slot: 'head',
      simcSlot: 'head',
      label: '头部',
      items: [simcPresetOnly]
    }],
    equippedSet: {},
    slotReadiness: {},
    readiness: {}
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'head' } } })

  assert.equal(page.data.gearSlotSheet.candidates[0].statusLabel, '来源待补')
  assert.equal(page.data.gearSlotSheet.candidates[0].trustLabel, '来源待补')
  assert.equal(page.data.gearSlotSheet.activeTrustLabel, '来源待补')
  assert.equal(page.data.gearSlotSheet.canApplyCandidate, true)
  assert.equal(page.data.gearSlotSheet.candidates[0].source, '来源待补充')
  const detailRows = page.data.gearSlotSheet.candidates[0].detailRows
  assert.equal(detailRows.find((row) => row.label === '掉落来源').value, '来源待补充')
  assert.equal(detailRows.some((row) => row.label === '配置来源'), false)
})

test('gear candidate detail shows crafted source even when compact candidate source type is a SimC preset', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const craftedPreset = {
    slot: 'off_hand',
    simcSlot: 'off_hand',
    itemId: '237850',
    id: '237850',
    displayName: '远行者的劈斧',
    simcReady: true,
    bonus_id: '8793/8960',
    crafted_stats: '40/32',
    source: '制造装备',
    sourceType: 'simcPreset',
    statSummary: '力量 124；耐力 1768'
  }
  const gearPayload = {
    slots: [{ slot: 'off_hand', simcSlot: 'off_hand', label: '副手' }],
    replacementCandidates: [{
      slot: 'off_hand',
      simcSlot: 'off_hand',
      label: '副手',
      items: [craftedPreset]
    }],
    equippedSet: {},
    slotReadiness: {},
    readiness: {}
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'off_hand' } } })

  const candidate = page.data.gearSlotSheet.candidates[0]
  const detailRows = candidate.detailRows
  assert.equal(candidate.source, '制造装备')
  assert.equal(detailRows.find((row) => row.label === '掉落来源').value, '制造装备')
})

test('gear slot sheet exposes source reference and blocker trust states', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const sourceReferenceItem = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '250888',
    id: '250888',
    displayName: 'Guide Only Hood',
    sourceType: 'source_reference',
    source: '虚空粉碎者掉落',
    sources: [{ label: '虚空粉碎者掉落', sourceType: 'dungeon' }],
    stats: [
      { label: '智力', value: '1234' },
      { name: '急速', value: '567' }
    ],
    metadataStatus: 'source_reference',
    missingFields: ['deterministic SimC variant'],
    blockers: ['missing deterministic SimC variant preset'],
    simcReady: false
  }
  const blockedItem = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '250999',
    id: '250999',
    displayName: 'Broken Hood',
    sourceType: 'raid',
    blockers: ['missing item id'],
    simcReady: false
  }
  const gearPayload = {
    slots: [{ slot: 'head', simcSlot: 'head', label: '头部' }],
    replacementCandidates: [{
      slot: 'head',
      simcSlot: 'head',
      label: '头部',
      items: [sourceReferenceItem, blockedItem]
    }],
    equippedSet: {},
    slotReadiness: { head: { status: 'blocked', reason: 'missing item' } },
    readiness: {}
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'head' } } })

  assert.deepEqual(Array.from(page.data.gearSlotSheet.filters, (item) => item.key), ['all', 'dungeon', 'raid', 'tier_set', 'crafted'])
  assert.deepEqual(Array.from(page.data.gearSlotSheet.filters, (item) => item.label), ['全部', '大秘境', '团本', '套装', '制造业'])
  assert.equal(page.data.gearSlotSheet.filterKey, 'all')
  assert.equal(page.data.gearSlotSheet.candidates[0].statusClass, 'source-reference')
  assert.equal(page.data.gearSlotSheet.candidates[0].trustLabel, '来源参考')
  assert.match(page.data.gearSlotSheet.candidates[0].trustReason, /不可直接保存/)
  assert.equal(page.data.gearSlotSheet.activeTrustLabel, '来源参考')
  assert.match(page.data.gearSlotSheet.activeTrustText, /缺少确定 SimC 变体/)

  pageConfig.toggleGearCandidateDetail.call(page, { currentTarget: { dataset: { index: 0 } } })

  assert.equal(page.data.gearSlotSheet.candidates[0].detailOpen, true)
  assert.equal(page.data.gearSlotSheet.candidates[1].detailOpen, false)
  assert.ok(page.data.gearSlotSheet.candidates[0].detailRows.some((row) => row.label === '掉落来源' && row.value === '虚空粉碎者掉落'))
  assert.ok(page.data.gearSlotSheet.candidates[0].detailRows.some((row) => row.label === '装备属性' && /智力 1234/.test(row.value) && /急速 567/.test(row.value)))
  assert.equal(page.data.gearSlotSheet.candidates[0].detailRows.some((row) => /物品 ID|SimC|缺失字段|阻断原因|变体|观测样本/.test(row.label)), false)

  pageConfig.selectGearCandidate.call(page, { currentTarget: { dataset: { index: 1 } } })

  assert.equal(page.data.gearSlotSheet.activeTrustLabel, '阻断')
  assert.match(page.data.gearSlotSheet.activeTrustText, /缺少物品 ID/)
})

test('gear candidate detail prefers stat summary without duplicating stat arrays', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const item = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '250777',
    id: '250777',
    displayName: 'Catalog Hood',
    sourceType: 'catalog',
    source: 'Catalog Dungeon',
    stats: [{ label: 'Intellect', value: 7 }],
    itemStats: [{ label: 'Intellect', value: 7 }],
    statSummary: 'Intellect 7; Haste 9',
    missingFields: ['ilevel'],
    simcReady: false
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: [{ slot: 'head', simcSlot: 'head', label: 'Head' }],
        replacementCandidates: [{ slot: 'head', simcSlot: 'head', label: 'Head', items: [item] }],
        equippedSet: {},
        slotReadiness: { head: { status: 'blocked', reason: 'missing item' } },
        readiness: {}
      },
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'head' } } })
  pageConfig.toggleGearCandidateDetail.call(page, { currentTarget: { dataset: { index: 0 } } })

  const attributes = page.data.gearSlotSheet.candidates[0].detailRows.find((row) => /Intellect|Haste/.test(row.value))
  assert.equal(attributes.value, 'Intellect 7; Haste 9')
})

test('gear candidate detail marks pending current variant stats instead of showing item level as attributes', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const item = {
    slot: 'back',
    simcSlot: 'back',
    itemId: '193712',
    id: '193712',
    displayName: '药渍披风',
    source: '茂林古树 - 艾杰斯亚学院',
    ilevel: 289,
    simcReady: true,
    statDisplayStatus: 'pending_current_variant'
  }
  const gearPayload = {
    slots: [{ slot: 'back', simcSlot: 'back', label: '披风' }],
    replacementCandidates: [{
      slot: 'back',
      simcSlot: 'back',
      label: '披风',
      items: [item]
    }],
    equippedSet: {},
    slotReadiness: {},
    readiness: {},
    statSnapshot: { statStatus: 'blocked', blockers: [] }
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'back' } } })

  const attributes = page.data.gearSlotSheet.candidates[0].detailRows.find((row) => row.label === '装备属性')
  assert.equal(attributes.value, '属性待补充（装等 289）')
})

test('gear candidate detail explains simc item resolution failure for observed variants', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const item = {
    slot: 'neck',
    simcSlot: 'neck',
    itemId: '268291',
    id: '268291',
    displayName: '腐沼的孢子之心',
    ilevel: 298,
    simcReady: true,
    statDisplayStatus: 'pending_current_variant',
    simcStatStatus: 'failed',
    simcStatFailureKind: 'item_resolution',
    observedProfileRefs: [{ sourceName: 'Raider.IO', classKey: 'mage', specKey: 'frost' }]
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: [{ slot: 'neck', simcSlot: 'neck', label: '项链' }],
        replacementCandidates: [{ slot: 'neck', simcSlot: 'neck', label: '项链', items: [item] }],
        equippedSet: {},
        slotReadiness: {},
        readiness: {}
      },
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'neck' } } })

  const candidate = page.data.gearSlotSheet.candidates[0]
  assert.equal(candidate.statusLabel, '属性待补')
  assert.equal(candidate.trustLabel, '属性待补')
  assert.match(candidate.trustReason, /装备属性/)
  const attributes = page.data.gearSlotSheet.candidates[0].detailRows.find((row) => row.label === '装备属性')
  assert.equal(attributes.value, '属性待补充（装等 298，SimC 物品解析失败）')
})

test('gear slot sheet blocks applying candidates that still need item level or simc options', async () => {
  const wxml = fs.readFileSync('pages/builds/detail.wxml', 'utf8')
  assert.match(wxml, /class="gear-apply-button" disabled="\{\{!gearSlotSheet\.canApplyCandidate\}\}"/)

  const toasts = []
  const pageConfig = loadBuildsDetailPageConfig({ toasts })
  const partialItem = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '251109',
    id: '251109',
    displayName: '断法暗影面具',
    sourceType: 'catalog',
    source: '瑟拉奈尔·日鞭 - 魔导师平台',
    sources: [{ label: '瑟拉奈尔·日鞭 - 魔导师平台', sourceType: 'dungeon' }],
    stats: [
      { label: '智力', value: 7 },
      { label: '精通', value: 9 }
    ],
    missingFields: ['ilevel', 'bonus_id/gem_id/enchant_id'],
    blockers: ['missing deterministic SimC variant preset'],
    variants: [{
      key: 'needs-variant',
      variantKey: 'needs-variant',
      difficultyLabel: '难度待补',
      itemLevel: 0,
      simcOptions: {},
      status: 'partial'
    }],
    defaultVariantKey: 'needs-variant',
    simcReady: false
  }
  const gearPayload = {
    slots: [{ slot: 'head', simcSlot: 'head', label: '头部' }],
    replacementCandidates: [{
      slot: 'head',
      simcSlot: 'head',
      label: '头部',
      items: [partialItem]
    }],
    equippedSet: {},
    slotReadiness: { head: { status: 'blocked', reason: 'missing item' } },
    readiness: {}
  }
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
      throw new Error('partial candidates must not refresh gear stats')
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'head' } } })

  assert.equal(page.data.gearSlotSheet.candidates.length, 1)
  assert.equal(page.data.gearSlotSheet.canApplyCandidate, false)
  assert.match(page.data.gearSlotSheet.activeTrustText, /缺少装等/)

  await pageConfig.applyGearCandidate.call(page)

  assert.equal(page.data.selectedGearBySlot.head, undefined)
  assert.equal(page.data.gearSlotSheet.visible, true)
  assert.match(toasts.at(-1).title, /缺少装等/)
})

test('gear slot sheet does not treat embellishment-only candidates as simc-ready', async () => {
  const toasts = []
  const pageConfig = loadBuildsDetailPageConfig({ toasts })
  const item = {
    slot: 'wrist',
    simcSlot: 'wrist',
    itemId: '260333',
    id: '260333',
    displayName: 'Only Embellished Cuffs',
    sourceType: 'crafted',
    source: '制造业',
    embellishment: 'dawnthread_lining',
    missingFields: ['ilevel', 'bonus_id/gem_id/enchant_id'],
    simcReady: false
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: [{ slot: 'wrist', simcSlot: 'wrist', label: '腕部' }],
        replacementCandidates: [{
          slot: 'wrist',
          simcSlot: 'wrist',
          label: '腕部',
          items: [item]
        }],
        equippedSet: {},
        slotReadiness: { wrist: { status: 'blocked', reason: 'missing base SimC fields' } },
        readiness: {}
      },
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    },
    refreshGearStats() {
      throw new Error('embellishment-only candidates must not refresh gear stats')
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'wrist' } } })

  assert.equal(page.data.gearSlotSheet.canApplyCandidate, false)
  assert.equal(page.data.gearSlotSheet.appliedCandidate.simcReady, false)
  assert.ok(page.data.gearSlotSheet.appliedCandidate.missingFields.includes('ilevel'))
  assert.ok(page.data.gearSlotSheet.appliedCandidate.missingFields.includes('bonus_id/gem_id/enchant_id'))

  await pageConfig.applyGearCandidate.call(page)

  assert.equal(page.data.selectedGearBySlot.wrist, undefined)
  assert.equal(page.data.gearSlotSheet.visible, true)
  assert.match(toasts.at(-1).title, /缺少装等/)
})

test('gear slot sheet applies simc-ready candidates with simc options when item level is absent', async () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const item = {
    slot: 'off_hand',
    simcSlot: 'off_hand',
    itemId: '251175',
    id: '251175',
    displayName: '灵魂枯萎劈刀',
    source: '测试首领 - 测试副本',
    sources: [{ label: '测试首领 - 测试副本', sourceType: 'dungeon' }],
    bonus_id: '4786/12806',
    enchant_id: '8039',
    statSummary: '敏捷 62；耐力 884',
    simcReady: true
  }
  const gearPayload = {
    slots: [{ slot: 'off_hand', simcSlot: 'off_hand', label: '副手' }],
    replacementCandidates: [{
      slot: 'off_hand',
      simcSlot: 'off_hand',
      label: '副手',
      items: [item]
    }],
    equippedSet: {},
    slotReadiness: {},
    readiness: {}
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'off_hand' } } })

  assert.equal(page.data.gearSlotSheet.canApplyCandidate, true)

  await pageConfig.applyGearCandidate.call(page)

  assert.equal(page.data.selectedGearBySlot.off_hand.itemId, '251175')
  assert.equal(page.data.selectedGearBySlot.off_hand.ilevel, undefined)
  assert.equal(page.data.selectedGearBySlot.off_hand.bonus_id, '4786/12806')
})

test('gear slot sheet keeps candidates that differ only by embellishment', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const baseItem = {
    slot: 'wrist',
    simcSlot: 'wrist',
    itemId: '260444',
    id: '260444',
    displayName: 'Crafted Cuffs',
    sourceType: 'crafted',
    ilevel: 289,
    bonus_id: '12345',
    simcReady: true
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: [{ slot: 'wrist', simcSlot: 'wrist', label: '腕部' }],
        replacementCandidates: [{
          slot: 'wrist',
          simcSlot: 'wrist',
          label: '腕部',
          items: [
            { ...baseItem, embellishment: 'dawnthread_lining' },
            { ...baseItem, embellishment: 'duskthread_lining' }
          ]
        }],
        equippedSet: {},
        slotReadiness: {},
        readiness: {}
      },
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'wrist' } } })

  assert.equal(page.data.gearSlotSheet.candidates.length, 2)
  assert.deepEqual(
    Array.from(page.data.gearSlotSheet.candidates, (candidate) => candidate.embellishment),
    ['dawnthread_lining', 'duskthread_lining']
  )
})

test('gear slot sheet source filters include tier set and crafted buckets while omitting recommendations', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const dungeonItem = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '250777',
    id: '250777',
    displayName: 'Catalog Hood',
    sourceType: 'dungeon',
    sources: [{ label: 'Maisara Caverns', sourceType: 'dungeon' }],
    ilevel: 707,
    bonus_id: '12345',
    simcReady: true
  }
  const tierSetItem = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '250778',
    id: '250778',
    displayName: 'Catalyst Hood',
    sourceType: 'tier_set',
    sources: [{ label: '套装转化', sourceType: 'tier_set' }],
    ilevel: 707,
    bonus_id: '12345',
    simcReady: true
  }
  const gearPayload = {
    slots: [{ slot: 'head', simcSlot: 'head', label: 'Head' }],
    replacementCandidates: [{
      slot: 'head',
      simcSlot: 'head',
      label: 'Head',
      items: [dungeonItem, tierSetItem]
    }],
    equippedSet: {},
    slotReadiness: {},
    readiness: {}
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'head' } } })

  assert.deepEqual(Array.from(page.data.gearSlotSheet.filters, (filter) => filter.key), ['all', 'dungeon', 'raid', 'tier_set', 'crafted'])
  assert.deepEqual(Array.from(page.data.gearSlotSheet.filters, (filter) => filter.label), ['全部', '大秘境', '团本', '套装', '制造业'])
  assert.equal(page.data.gearSlotSheet.filters.find((filter) => filter.key === 'crafted').count, 0)
  assert.equal(page.data.gearSlotSheet.filters.some((filter) => /推荐/.test(filter.label)), false)
  assert.equal(page.data.gearSlotSheet.candidates.length, 2)

  pageConfig.setGearCandidateFilter.call(page, { currentTarget: { dataset: { key: 'raid' } } })

  assert.equal(page.data.gearSlotSheet.filterKey, 'raid')
  assert.equal(page.data.gearSlotSheet.candidates.length, 0)
  assert.equal(page.data.gearSlotSheet.emptyText, '该来源暂无候选装备')

  pageConfig.setGearCandidateFilter.call(page, { currentTarget: { dataset: { key: 'tier_set' } } })

  assert.equal(page.data.gearSlotSheet.filterKey, 'tier_set')
  assert.equal(page.data.gearSlotSheet.candidates.length, 1)
  assert.equal(page.data.gearSlotSheet.candidates[0].displayName, 'Catalyst Hood')

  pageConfig.setGearCandidateFilter.call(page, { currentTarget: { dataset: { key: 'crafted' } } })

  assert.equal(page.data.gearSlotSheet.filterKey, 'crafted')
  assert.equal(page.data.gearSlotSheet.candidates.length, 0)
  assert.equal(page.data.gearSlotSheet.emptyText, '该来源暂无候选装备')
})

test('gear candidate detail toggle does not change the selected candidate', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const gearPayload = {
    slots: [{ slot: 'head', simcSlot: 'head', label: 'Head' }],
    replacementCandidates: [{
      slot: 'head',
      simcSlot: 'head',
      label: 'Head',
      items: [
        {
          slot: 'head',
          simcSlot: 'head',
          itemId: '250101',
          id: '250101',
          displayName: 'Selected Hood',
          sourceType: 'dungeon',
          ilevel: 707,
          bonus_id: '12345',
          simcReady: true
        },
        {
          slot: 'head',
          simcSlot: 'head',
          itemId: '250202',
          id: '250202',
          displayName: 'Inspect Only Hood',
          sourceType: 'raid',
          ilevel: 710,
          bonus_id: '67890',
          simcReady: true
        }
      ]
    }],
    equippedSet: {},
    slotReadiness: {},
    readiness: {}
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'head' } } })

  assert.equal(page.data.gearSlotSheet.selectedCandidateIndex, 0)
  assert.equal(page.data.gearSlotSheet.activeCandidate.itemId, '250101')

  pageConfig.toggleGearCandidateDetail.call(page, { currentTarget: { dataset: { index: 1 } } })

  assert.equal(page.data.gearSlotSheet.selectedCandidateIndex, 0)
  assert.equal(page.data.gearSlotSheet.activeCandidate.itemId, '250101')
  assert.equal(page.data.gearSlotSheet.candidates[0].detailOpen, false)
  assert.equal(page.data.gearSlotSheet.candidates[1].detailOpen, true)
})

test('gear candidate rows render only a compact detail action on the right side', () => {
  const wxml = fs.readFileSync('pages/builds/detail.wxml', 'utf8')
  assert.match(wxml, /class="gear-candidate-action"/)
  assert.match(wxml, /class="gear-candidate-detail-button"/)
  assert.doesNotMatch(wxml, /item\.shortStatusLabel/)
  assert.doesNotMatch(wxml, /item\.issueSummary/)
  assert.doesNotMatch(wxml, /class="gear-candidate-meta"/)
})

test('gear slot sheet keeps socket options out of equipment detail controls', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const item = {
    slot: 'neck',
    simcSlot: 'neck',
    itemId: '268291',
    id: '268291',
    displayName: '悲恸吊坠',
    sourceType: 'dungeon',
    ilevel: 289,
    bonus_id: '67890',
    simcReady: true
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: [{ slot: 'neck', simcSlot: 'neck', label: '颈部' }],
        replacementCandidates: [{
          slot: 'neck',
          simcSlot: 'neck',
          label: '颈部',
          socketOptions: [{
            id: 'socket-gem-213743',
            name: '迅捷宝石',
            simcOptions: { gem_id: '213743' },
            status: 'verified'
          }],
          items: [item]
        }],
        equippedSet: {},
        slotReadiness: {},
        readiness: {}
      },
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'neck' } } })

  assert.deepEqual(Array.from(page.data.gearSlotSheet.socketOptions), [])
  assert.equal(page.data.gearSlotSheet.activeCandidate.socketOptions, undefined)
  assert.equal(page.data.gearSlotSheet.canApplyCandidate, true)
})

test('gear slot sheet keeps enchant options out of equipment detail controls', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const item = {
    slot: 'main_hand',
    simcSlot: 'main_hand',
    itemId: '249293',
    id: '249293',
    displayName: '仪式妖术之刃',
    sourceType: 'raid',
    ilevel: 298,
    bonus_id: '13786',
    simcReady: true
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: [{ slot: 'main_hand', simcSlot: 'main_hand', label: '主手' }],
        replacementCandidates: [{
          slot: 'main_hand',
          simcSlot: 'main_hand',
          label: '主手',
          enchantOptions: [{
            id: 'enchant-3368',
            name: '武器附魔',
            simcOptions: { enchant_id: '3368' },
            status: 'verified'
          }],
          items: [item]
        }],
        equippedSet: {},
        slotReadiness: {},
        readiness: {}
      },
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'main_hand' } } })

  assert.deepEqual(Array.from(page.data.gearSlotSheet.enchantOptions), [])
  assert.equal(page.data.gearSlotSheet.activeCandidate.enchantOptions, undefined)
  assert.equal(page.data.gearSlotSheet.canApplyCandidate, true)
})

test('gear slot sheet sorts upgrade tracks as champion hero myth and void ascension', async () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const item = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '250777',
    id: '250777',
    displayName: 'Catalog Hood',
    sourceType: 'raid',
    sources: [{ label: 'Vault Mage - Arcane Vault', sourceType: 'raid' }],
    modCapabilities: { hasSocket: true, canEnchant: true },
    defaultVariantKey: 'champion-263',
    variants: [
      {
        key: 'myth-289',
        label: 'Myth 289',
        difficultyLabel: '史诗',
        itemLevel: 289,
        simcOptions: { bonus_id: '67890' },
        status: 'verified'
      },
      {
        key: 'void-298',
        label: 'Void 298',
        difficultyLabel: '史诗',
        itemLevel: 298,
        simcOptions: { bonus_id: '13786' },
        status: 'verified'
      },
      {
        key: 'champion-263',
        label: 'Champion 263',
        difficultyLabel: '大秘境',
        itemLevel: 263,
        simcOptions: { bonus_id: '12345' },
        status: 'verified'
      },
      {
        key: 'hero-276',
        label: 'Hero 276',
        difficultyLabel: '英雄',
        itemLevel: 276,
        simcOptions: { bonus_id: '23456' },
        status: 'verified'
      },
      {
        key: 'needs-variant',
        label: '难度 / 装等待补',
        difficultyKey: 'needs-variant',
        itemLevel: 0,
        status: 'partial',
        blockers: ['missing deterministic SimC variant preset']
      }
    ],
    simcReady: true
  }
  const gearPayload = {
    slots: [{ slot: 'head', simcSlot: 'head', label: 'Head' }],
    replacementCandidates: [{
      slot: 'head',
      simcSlot: 'head',
      label: 'Head',
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
  assert.deepEqual(Array.from(page.data.gearSlotSheet.variantOptions, (variant) => variant.displayLabel), ['勇士', '英雄', '神话', '虚空晋升'])
  assert.deepEqual(Array.from(page.data.gearSlotSheet.variantOptions, (variant) => variant.levelLabel), ['装等 263', '装等 276', '装等 289', '装等 298'])
  assert.equal(page.data.gearSlotSheet.variantOptions.some((variant) => variant.displayLabel === '难度待补'), false)
  assert.deepEqual(Array.from(page.data.gearSlotSheet.socketOptions), [])
  assert.deepEqual(Array.from(page.data.gearSlotSheet.enchantOptions), [])
  assert.equal(page.data.gearSlotSheet.canApplyCandidate, true)
  pageConfig.selectGearVariant.call(page, { currentTarget: { dataset: { key: 'myth-289' } } })
  assert.equal(page.data.gearSlotSheet.canApplyCandidate, true)
  assert.equal(page.data.gearSlotSheet.appliedCandidate.gem_id, undefined)
  assert.equal(page.data.gearSlotSheet.appliedCandidate.enchant_id, undefined)
  await pageConfig.applyGearCandidate.call(page)

  const selected = page.data.selectedGearBySlot.head
  assert.equal(selected.variantKey, 'myth-289')
  assert.equal(selected.ilevel, 289)
  assert.equal(selected.bonus_id, '67890')
  assert.equal(selected.gem_id, undefined)
  assert.equal(selected.gem_ilevel, undefined)
  assert.equal(selected.enchant_id, undefined)
  assert.equal(page.data.gearSlotSheet.visible, false)
  assert.equal(refreshCalls, 0)
})

test('gear slot sheet only renders DB-provided item level tracks for catalog candidates', async () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const item = {
    slot: 'shoulder',
    simcSlot: 'shoulder',
    itemId: '250888',
    id: '250888',
    displayName: 'Duplicate Shoulder',
    sourceType: 'raid',
    sources: [{ label: 'Void Captain - Voidspire', sourceType: 'raid' }],
    defaultVariantKey: 'observed-289-current',
    variants: [
      {
        key: 'observed-289-current',
        label: 'Observed 289',
        difficultyLabel: '团本',
        difficultyKey: 'raid',
        itemLevel: 289,
        simcOptions: { bonus_id: '24680' },
        status: 'verified'
      }
    ],
    simcReady: true
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: [{ slot: 'shoulder', simcSlot: 'shoulder', label: 'Shoulder' }],
        replacementCandidates: [{
          slot: 'shoulder',
          simcSlot: 'shoulder',
          label: 'Shoulder',
          items: [item]
        }],
        equippedSet: {},
        slotReadiness: {},
        readiness: {},
        statSnapshot: { statStatus: 'blocked', blockers: [] }
      },
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'shoulder' } } })

  assert.deepEqual(Array.from(page.data.gearSlotSheet.variantOptions, (variant) => variant.displayLabel), ['神话'])
  assert.deepEqual(Array.from(page.data.gearSlotSheet.variantOptions, (variant) => variant.levelLabel), ['装等 289'])
  assert.equal(page.data.gearSlotSheet.variantOptions[0].key, 'observed-289-current')
})

test('gear slot sheet updates visible item level and attributes when variant changes', async () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const item = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '250999',
    id: '250999',
    displayName: 'Variant Hood',
    sourceType: 'raid',
    sources: [{ label: 'Void Captain - Voidspire', sourceType: 'raid' }],
    defaultVariantKey: 'champion-263',
    statSummary: '智力 999；耐力 999',
    itemStats: [
      { key: 'intellect', label: '智力', value: 999 },
      { key: 'stamina', label: '耐力', value: 999 }
    ],
    statDisplayStatus: 'verified_variant',
    variants: [
      {
        key: 'champion-263',
        label: 'Champion 263',
        difficultyKey: 'champion',
        itemLevel: 263,
        simcOptions: { ilevel: '263' },
        statSummary: '智力 100；耐力 200',
        statDisplayStatus: 'verified_variant',
        status: 'verified'
      },
      {
        key: 'hero-276',
        label: 'Hero 276',
        difficultyKey: 'hero',
        itemLevel: 276,
        simcOptions: { ilevel: '276' },
        statSummary: '智力 120；耐力 240',
        statDisplayStatus: 'verified_variant',
        status: 'verified'
      },
      {
        key: 'myth-289',
        label: 'Myth 289',
        difficultyKey: 'myth',
        itemLevel: 289,
        simcOptions: { ilevel: '289' },
        statSummary: '智力 140；耐力 280',
        statDisplayStatus: 'verified_variant',
        status: 'verified'
      }
    ],
    simcReady: true
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
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
      },
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'head' } } })
  pageConfig.selectGearVariant.call(page, { currentTarget: { dataset: { key: 'hero-276' } } })

  const selectedCandidate = page.data.gearSlotSheet.candidates[0]
  assert.equal(selectedCandidate.ilevel, 276)
  assert.equal(selectedCandidate.statSummary, '智力 120；耐力 240')
  assert.ok(selectedCandidate.detailRows.some((row) => row.label === '装备属性' && row.value === '智力 120；耐力 240'))
  assert.equal(selectedCandidate.detailRows.some((row) => /智力 999/.test(row.value)), false)
  assert.equal(page.data.gearSlotSheet.appliedCandidate.ilevel, 276)
})

test('gear slot sheet counts crafted filter when crafted candidates exist', async () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const craftedItem = {
    slot: 'wrist',
    simcSlot: 'wrist',
    itemId: '260200',
    id: '260200',
    displayName: 'Crafted Bracers',
    sourceType: 'crafted',
    sources: [{ label: '制造装备', sourceType: 'crafted' }],
    variants: [{
      key: 'crafted-myth-285',
      label: '神话 285',
      difficultyKey: 'myth',
      itemLevel: 285,
      simcOptions: { ilevel: '285', bonus_id: '8793/8960' },
      craftedStatOptions: [{
        key: 'haste_mastery',
        label: '急速 + 精通',
        simcOptions: { crafted_stats: '40/32' },
        status: 'verified',
        statSummary: '智力 285；急速 40；精通 32'
      }],
      status: 'verified'
    }],
    simcReady: true
  }
  const dungeonItem = {
    slot: 'wrist',
    simcSlot: 'wrist',
    itemId: '260201',
    id: '260201',
    displayName: 'Dungeon Bracers',
    sourceType: 'dungeon',
    sources: [{ label: '测试副本', sourceType: 'dungeon' }],
    variants: [{ key: 'myth-289', difficultyKey: 'myth', itemLevel: 289, simcOptions: { ilevel: '289', bonus_id: '12345' }, status: 'verified' }],
    simcReady: true
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: [{ slot: 'wrist', simcSlot: 'wrist', label: 'Wrist' }],
        replacementCandidates: [{
          slot: 'wrist',
          simcSlot: 'wrist',
          label: 'Wrist',
          items: [craftedItem, dungeonItem]
        }],
        equippedSet: {},
        slotReadiness: {},
        readiness: {},
        statSnapshot: { statStatus: 'blocked', blockers: [] }
      },
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'wrist' } } })

  const craftedFilter = page.data.gearSlotSheet.filters.find((filter) => filter.key === 'crafted')
  assert.equal(craftedFilter.label, '制造业')
  assert.equal(craftedFilter.count, 1)

  pageConfig.setGearCandidateFilter.call(page, { currentTarget: { dataset: { key: 'dungeon' } } })
  assert.equal(page.data.gearSlotSheet.filters.some((filter) => filter.key === 'crafted'), true)
  assert.equal(page.data.gearSlotSheet.candidates.length, 1)
  assert.equal(page.data.gearSlotSheet.candidates[0].sourceType, 'dungeon')
})

test('crafted gear requires selecting a stat option before apply and serializes crafted_stats', async () => {
  const pageConfig = loadBuildsDetailPageConfig()
  assert.equal(typeof pageConfig.selectCraftedStatOption, 'function')
  const craftedItem = {
    slot: 'wrist',
    simcSlot: 'wrist',
    itemId: '260200',
    id: '260200',
    displayName: 'Crafted Bracers',
    sourceType: 'crafted',
    sources: [{ label: '制造装备', sourceType: 'crafted' }],
    variants: [{
      key: 'crafted-myth-285',
      label: '神话 285',
      difficultyKey: 'myth',
      itemLevel: 285,
      simcOptions: { ilevel: '285', bonus_id: '8793/8960' },
      craftedStatOptions: [
        {
          key: 'haste_mastery',
          label: '急速 + 精通',
          simcOptions: { crafted_stats: '40/32' },
          status: 'verified',
          statSummary: '智力 285；急速 40；精通 32',
          statDisplayStatus: 'verified_variant'
        },
        {
          key: 'crit_vers',
          label: '暴击 + 全能',
          simcOptions: { crafted_stats: '36/36' },
          status: 'partial',
          blockers: ['SimC crafted item probe missing item stats']
        }
      ],
      status: 'verified'
    }],
    simcReady: true
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      selectedSpec: { id: '法师-冰霜', title: '冰霜' },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: [{ slot: 'wrist', simcSlot: 'wrist', label: 'Wrist' }],
        replacementCandidates: [{
          slot: 'wrist',
          simcSlot: 'wrist',
          label: 'Wrist',
          items: [craftedItem]
        }],
        equippedSet: {},
        slotReadiness: {},
        readiness: { fullReady: false },
        statSnapshot: { statStatus: 'blocked', blockers: [] }
      },
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'wrist' } } })

  assert.equal(page.data.gearSlotSheet.craftedStatOptions.length, 2)
  assert.equal(page.data.gearSlotSheet.canApplyCandidate, false)
  assert.match(page.data.gearSlotSheet.activeTrustText, /缺少制造属性搭配/)

  pageConfig.selectCraftedStatOption.call(page, { currentTarget: { dataset: { key: 'crit_vers' } } })
  assert.equal(page.data.gearSlotSheet.canApplyCandidate, false)
  assert.match(page.data.gearSlotSheet.activeTrustText, /SimC/)

  pageConfig.selectCraftedStatOption.call(page, { currentTarget: { dataset: { key: 'haste_mastery' } } })
  assert.equal(page.data.gearSlotSheet.canApplyCandidate, true)
  assert.equal(page.data.gearSlotSheet.appliedCandidate.crafted_stats, '40/32')
  assert.equal(page.data.gearSlotSheet.appliedCandidate.selectedCraftedStatKey, 'haste_mastery')
  assert.equal(page.data.gearSlotSheet.candidates[0].statSummary, '智力 285；急速 40；精通 32')

  await pageConfig.applyGearCandidate.call(page)

  const selected = page.data.selectedGearBySlot.wrist
  assert.equal(selected.crafted_stats, '40/32')
  assert.equal(selected.selectedCraftedStatKey, 'haste_mastery')
  assert.match(selected.statSummary, /急速 40/)

  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'wrist' } } })
  assert.equal(page.data.gearSlotSheet.craftedStatOptionKey, 'haste_mastery')
  assert.equal(page.data.gearSlotSheet.canApplyCandidate, true)
  assert.equal(page.data.gearSlotSheet.appliedCandidate.crafted_stats, '40/32')
})

test('gear slot sheet clears stale candidate attributes when selected track has pending stats', async () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const item = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '251111',
    id: '251111',
    displayName: 'Pending Hood',
    sourceType: 'raid',
    sources: [{ label: 'Void Captain - Voidspire', sourceType: 'raid' }],
    defaultVariantKey: 'myth-289',
    statSummary: '智力 140；耐力 280',
    itemStats: [
      { key: 'intellect', label: '智力', value: 140 },
      { key: 'stamina', label: '耐力', value: 280 }
    ],
    statDisplayStatus: 'verified_variant',
    variants: [
      {
        key: 'myth-289',
        label: 'Myth 289',
        difficultyKey: 'myth',
        itemLevel: 289,
        simcOptions: { ilevel: '289' },
        statSummary: '智力 140；耐力 280',
        statDisplayStatus: 'verified_variant',
        status: 'verified'
      },
      {
        key: 'hero-276',
        label: 'Hero 276',
        difficultyKey: 'hero',
        itemLevel: 276,
        simcOptions: { ilevel: '276' },
        statDisplayStatus: 'pending_current_variant',
        status: 'partial',
        blockers: ['SimulationCraft item stats']
      }
    ],
    simcReady: true
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
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
      },
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'head' } } })
  pageConfig.selectGearVariant.call(page, { currentTarget: { dataset: { key: 'hero-276' } } })

  const attributes = page.data.gearSlotSheet.candidates[0].detailRows.find((row) => row.label === '装备属性')
  assert.match(attributes.value, /属性待补充/)
  assert.match(attributes.value, /装等 276/)
  assert.equal(/智力 140|耐力 280/.test(attributes.value), false)
})

test('gear candidate detail uses set name for tier source and hides backend evidence rows', async () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const item = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '252222',
    id: '252222',
    displayName: 'Set Hood',
    sourceType: 'tier_set',
    source: 'SimulationCraft preset: MID1_Mage_Frost',
    itemSetName: '虚空粉碎者协律',
    sources: [
      { label: 'SimulationCraft preset: MID1_Mage_Frost', sourceType: 'simc_preset' },
      { label: 'Raider.IO CN observed mage frost', sourceType: 'observed_profile' },
      { label: 'Catalyst', sourceType: 'tier_set' }
    ],
    observedProfileRefs: [{ sourceName: 'Raider.IO', classKey: 'mage', specKey: 'frost' }],
    variants: [{
      key: 'myth-289',
      difficultyKey: 'myth',
      itemLevel: 289,
      simcOptions: { ilevel: '289' },
      statSummary: '智力 140；耐力 280',
      statDisplayStatus: 'verified_variant',
      status: 'verified'
    }],
    simcReady: true
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
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
      },
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'head' } } })

  const rows = page.data.gearSlotSheet.candidates[0].detailRows
  assert.equal(rows.find((row) => row.label === '掉落来源').value, '虚空粉碎者协律-套装')
  assert.equal(rows.some((row) => row.label === '配置来源'), false)
  assert.equal(rows.some((row) => row.label === '实装观测'), false)
})

test('gear community template import blocks source reference templates and surfaces blockers', () => {
  const toasts = []
  const pageConfig = loadBuildsDetailPageConfig({ toasts })
  const baseline = completeGearSelection(['head'])
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: ['head', 'neck'].map((slot) => ({ slot, simcSlot: slot, label: slot })),
        equippedSet: {},
        replacementCandidates: [],
        slotReadiness: {},
        readiness: {},
        communityTemplates: [{
          id: 'guide-reference',
          name: 'Guide Reference',
          sourceKey: 'wowhead_guide',
          sourceName: 'Wowhead guide',
          sourceStatus: 'source_reference',
          status: 'partial',
          readySlotCount: 1,
          missingSlots: canonicalGearSlots.slice(1),
          canApplyGear: true,
          blockers: ['missing deterministic SimC variant preset'],
          gearItems: [baseline.head]
        }]
      },
      selectedGearBySlot: {},
      gearCommunityTemplateSheet: { visible: true },
      gearSlotSheet: { visible: true }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  const template = page.data.activeGearCommunityTemplates[0]

  assert.equal(template.cardClass, 'source-reference')
  assert.equal(template.statusLabel, '来源参考')
  assert.equal(template.canApplyGear, false)
  assert.match(template.missingSlotLabel, /缺 15 槽/)
  assert.match(template.blockerLabel, /missing deterministic SimC variant preset/)

  pageConfig.applyGearCommunityTemplate.call(page, { currentTarget: { dataset: { id: 'guide-reference' } } })

  assert.equal(page.data.selectedGearBySlot.head, undefined)
  assert.match(toasts.at(-1).title, /暂不可导入/)
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
  assert.match(savedTemplates[0].title, /^法师-冰霜-单体-\d{4} \d{4}$/)
  assert.equal(Array.isArray(savedTemplates[0].simcLines), true)
  assert.equal(savedTemplates[0].simcLines.length, 0)
  const snapshot = JSON.parse(savedTemplates[0].rawString)
  assert.equal(Object.keys(snapshot.gearBySlot).length, canonicalGearSlots.length)
  assert.deepEqual(snapshot.enhancementBySlot, {})
  assert.equal(snapshot.schemaRevision, 'websim-gear-enhancement-snapshot-v1')
})

test('gear template save stores structured enhancement snapshot for backend serialization', () => {
  const savedTemplates = []
  const pageConfig = loadBuildsDetailPageConfig({ savedTemplates })
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection()
  selection.head = {
    ...selection.head,
    key: 'head-heavy-ui',
    detailRows: [{ label: '装备属性', value: '智力 120' }],
    gameAsset: { iconUrl: 'https://example.invalid/icon.png' },
    statusLabel: '已验证',
    trustLabel: '可信'
  }
  selection.finger1 = {
    ...selection.finger1,
    modCapabilities: { hasSocket: true, canEnchant: true, canEmbellish: false }
  }
  selection.wrist = {
    ...selection.wrist,
    sourceType: 'crafted',
    modCapabilities: { hasSocket: false, canEnchant: true, canEmbellish: true },
    embellishmentOptions: [
      {
        id: 'client-only-embellishment',
        status: 'verified',
        payload: { qualityRank: 2 },
        simcOptions: { embellishment: 'client_only_lining' }
      }
    ]
  }
  const enhancementBySlot = {
    finger1: {
      socketOptionId: 'gem-rank-two',
      enchantOptionId: 'enchant-rank-two',
      gem_id: '240983',
      gem_ilevel: '707',
      enchant_id: '7334'
    },
    wrist: {
      embellishmentOptionId: 'embellishment-blue-silken-lining',
      embellishment: 'blue_silken_lining'
    }
  }
  const page = {
    data: {
      selectedDetail: { className: '法师', specName: '冰霜', details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      selectedSpec: { className: '法师', title: '冰霜', specName: '冰霜', websimClassKey: 'mage', websimSpecKey: 'frost' },
      activeQueryKey: 'gear',
      gearPayload: {
        slots,
        maxLevel: 90,
        gearSchemaRevision: 'websim-gear-simulator-v1',
        replacementCandidates: [
          {
            slot: 'finger1',
            simcSlot: 'finger1',
            label: 'finger1',
            items: [],
            socketOptions: [
              {
                id: 'gem-rank-two',
                label: '迅捷宝石',
                status: 'verified',
                simcOptions: { gem_id: '240983', gem_ilevel: '707' },
                payload: { qualityRank: 2 }
              }
            ],
            enchantOptions: [
              {
                id: 'enchant-rank-two',
                label: '戒指附魔',
                status: 'verified',
                simcOptions: { enchant_id: '7334' },
                payload: { qualityRank: 2 }
              }
            ]
          },
          {
            slot: 'wrist',
            simcSlot: 'wrist',
            label: 'wrist',
            items: [],
            embellishmentOptions: [
              {
                id: 'embellishment-blue-silken-lining',
                label: '蓝色丝质内衬',
                status: 'verified',
                simcOptions: { embellishment: 'blue_silken_lining' },
                payload: { qualityRank: 2, simcKey: 'blue_silken_lining' }
              }
            ]
          }
        ]
      },
      selectedGearBySlot: selection,
      enhancementBySlot,
      selectedGearTemplateScenarioIndex: 0
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.saveGearTemplate.call(page)

  assert.equal(savedTemplates.length, 1)
  const snapshot = JSON.parse(savedTemplates[0].rawString)
  assert.equal(snapshot.schemaRevision, 'websim-gear-enhancement-snapshot-v1')
  assert.equal(snapshot.gearBySlot.head.itemId, '250000')
  assert.equal(snapshot.gearBySlot.head.key, undefined)
  assert.equal(snapshot.gearBySlot.head.detailRows, undefined)
  assert.equal(snapshot.gearBySlot.head.gameAsset, undefined)
  assert.equal(snapshot.gearBySlot.head.statusLabel, undefined)
  assert.equal(snapshot.gearBySlot.head.trustLabel, undefined)
  assert.equal(snapshot.gearBySlot.wrist.embellishmentOptions, undefined)
  assert.equal(JSON.stringify(snapshot.enhancementBySlot), JSON.stringify(enhancementBySlot))
  assert.equal(JSON.stringify(savedTemplates[0].metadata.enhancementBySlot), JSON.stringify(enhancementBySlot))
  assert.doesNotMatch(savedTemplates[0].rawString, /^head=/m)
})

test('gear template save prunes invalid enhancement fields by type', () => {
  const savedTemplates = []
  const pageConfig = loadBuildsDetailPageConfig({ savedTemplates })
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection()
  selection.finger1 = {
    ...selection.finger1,
    modCapabilities: { hasSocket: false, canEnchant: true, canEmbellish: false }
  }
  const page = {
    data: {
      selectedDetail: { className: '法师', specName: '冰霜', details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      selectedSpec: { className: '法师', title: '冰霜', specName: '冰霜', websimClassKey: 'mage', websimSpecKey: 'frost' },
      activeQueryKey: 'gear',
      gearPayload: {
        slots,
        maxLevel: 90,
        gearSchemaRevision: 'websim-gear-simulator-v1',
        replacementCandidates: [
          {
            slot: 'finger1',
            simcSlot: 'finger1',
            label: 'finger1',
            items: [],
            enchantOptions: [
              {
                id: 'enchant-rank-two',
                label: '戒指附魔',
                status: 'verified',
                simcOptions: { enchant_id: '7334' },
                payload: { qualityRank: 2 }
              }
            ]
          }
        ]
      },
      selectedGearBySlot: selection,
      enhancementBySlot: {
        finger1: {
          socketOptionId: 'gem-rank-two',
          gem_id: '240983',
          gem_ilevel: '707',
          enchantOptionId: 'enchant-rank-two',
          enchant_id: '7334'
        }
      },
      selectedGearTemplateScenarioIndex: 0
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.saveGearTemplate.call(page)

  assert.equal(savedTemplates.length, 1)
  const snapshot = JSON.parse(savedTemplates[0].rawString)
  assert.deepEqual(snapshot.enhancementBySlot, {
    finger1: {
      enchantOptionId: 'enchant-rank-two',
      enchant_id: '7334'
    }
  })
})

test('gear template save blocks over-cap embellishments', () => {
  const savedTemplates = []
  const toasts = []
  const pageConfig = loadBuildsDetailPageConfig({ savedTemplates, toasts })
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection()
  selection.back = {
    ...selection.back,
    embellishment: 'dawnthread_lining'
  }
  selection.chest = {
    ...selection.chest,
    intrinsicEmbellishment: 'duskthread_lining'
  }
  selection.wrist = {
    ...selection.wrist,
    sourceType: 'crafted',
    modCapabilities: { hasSocket: false, canEnchant: true, canEmbellish: true }
  }
  const page = {
    data: {
      selectedDetail: { className: '法师', specName: '冰霜', details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      selectedSpec: { className: '法师', title: '冰霜', specName: '冰霜', websimClassKey: 'mage', websimSpecKey: 'frost' },
      activeQueryKey: 'gear',
      gearPayload: {
        slots,
        maxLevel: 90,
        gearSchemaRevision: 'websim-gear-simulator-v1',
        replacementCandidates: [
          {
            slot: 'wrist',
            simcSlot: 'wrist',
            label: 'wrist',
            items: [],
            embellishmentOptions: [
              {
                id: 'embellishment-blue-silken-lining',
                label: '蓝色丝质内衬',
                status: 'verified',
                simcOptions: { embellishment: 'blue_silken_lining' },
                payload: { qualityRank: 2, simcKey: 'blue_silken_lining' }
              }
            ]
          }
        ]
      },
      selectedGearBySlot: selection,
      enhancementBySlot: {
        wrist: {
          embellishmentOptionId: 'embellishment-blue-silken-lining',
          embellishment: 'blue_silken_lining'
        }
      },
      gearEnhancementSheet: { visible: false },
      selectedGearTemplateScenarioIndex: 0
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.saveGearTemplate.call(page)

  assert.equal(savedTemplates.length, 0)
  assert.match(toasts.at(-1).title, /美化已超过上限 3\/2/)
  assert.ok(page.data.gearEnhancementSheet.blockers.includes('美化已超过上限 3/2'))
})

test('gear template save allows backend-ready two-handed setups without off hand', () => {
  const savedTemplates = []
  const toasts = []
  const pageConfig = loadBuildsDetailPageConfig({ savedTemplates, toasts })
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const twoHandSelection = completeGearSelection(canonicalGearSlots.filter((slot) => slot !== 'off_hand'))
  const page = {
    data: {
      selectedDetail: { className: '死亡骑士', specName: '鲜血', details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      selectedSpec: { className: '死亡骑士', title: '鲜血', specName: '鲜血', websimClassKey: 'deathknight', websimSpecKey: 'blood' },
      activeQueryKey: 'gear',
      gearPayload: {
        slots,
        maxLevel: 90,
        gearSchemaRevision: 'websim-gear-simulator-v1',
        readiness: {
          fullReady: true,
          missingRequiredSlots: ['off_hand'],
          missingCoreSlots: [],
          requiredReadyCount: 15
        }
      },
      selectedGearBySlot: twoHandSelection,
      selectedGearTemplateScenarioIndex: 0
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.saveGearTemplate.call(page)

  assert.equal(toasts.length, 0)
  assert.equal(savedTemplates.length, 1)
  assert.equal(savedTemplates[0].status, 'complete')
  const snapshot = JSON.parse(savedTemplates[0].rawString)
  assert.equal(Object.keys(snapshot.gearBySlot).length, canonicalGearSlots.length - 1)
  assert.equal(snapshot.gearBySlot.off_hand, undefined)
})

test('gear template save keeps source pending evidence in metadata', () => {
  const savedTemplates = []
  const pageConfig = loadBuildsDetailPageConfig({ savedTemplates })
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection()
  selection.waist = {
    ...selection.waist,
    source: 'SimulationCraft preset: MID1_Mage_Frost_Frostfire',
    sourceType: 'simc_preset',
    sources: [{ sourceType: 'simc_preset', sourceLabel: 'SimulationCraft preset: MID1_Mage_Frost_Frostfire' }],
    statSummary: '智力 70；耐力 995',
    simcReady: true
  }
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
      selectedGearBySlot: selection,
      selectedGearTemplateScenarioIndex: 0
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.saveGearTemplate.call(page)

  assert.equal(savedTemplates.length, 1)
  assert.equal(savedTemplates[0].status, 'complete_with_warnings')
  assert.equal(savedTemplates[0].statusLabel, '完整配置 · 来源待补')
  assert.deepEqual(Array.from(savedTemplates[0].metadata.sourcePendingSlots), ['waist'])
  assert.deepEqual(Array.from(savedTemplates[0].metadata.statPendingSlots), [])
  assert.match(savedTemplates[0].metadata.warningSummary, /来源待补/)
})

test('gear template save validation names missing and untrusted slots', () => {
  const savedTemplates = []
  const toasts = []
  const pageConfig = loadBuildsDetailPageConfig({ savedTemplates, toasts })
  const page = {
    data: {
      selectedDetail: { className: '法师', specName: '冰霜', details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      selectedSpec: { className: '法师', title: '冰霜', specName: '冰霜', websimClassKey: 'mage', websimSpecKey: 'frost' },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot })),
        maxLevel: 90,
        gearSchemaRevision: 'websim-gear-simulator-v1'
      },
      selectedGearBySlot: completeGearSelection(canonicalGearSlots.slice(0, -1)),
      selectedGearTemplateScenarioIndex: 0
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.saveGearTemplate.call(page)

  assert.equal(savedTemplates.length, 0)
  assert.match(toasts.at(-1).title, /off_hand/)

  page.data.selectedGearBySlot = {
    ...completeGearSelection(canonicalGearSlots.slice(0, -1)),
    off_hand: {
      slot: 'off_hand',
      simcSlot: 'off_hand',
      id: 'guide-only-offhand',
      displayName: 'Guide Only Offhand',
      ilevel: 707,
      bonus_id: '12345',
      metadataStatus: 'source_reference',
      sourceType: 'source_reference',
      simcReady: false
    }
  }

  pageConfig.saveGearTemplate.call(page)

  assert.equal(savedTemplates.length, 0)
  assert.match(toasts.at(-1).title, /off_hand/)
  assert.match(toasts.at(-1).title, /物品 ID|来源参考/)
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
