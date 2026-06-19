const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')
const { buildSpecializationHomePayload } = require('../server/builds/home-payload')

function loadBuildsDetailPageConfig() {
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
      showToast() {}
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
          requestWebsimGear: () => Promise.resolve({ payload: {} }),
          requestWebsimGearStats: () => Promise.resolve({ payload: {} })
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
          syncBuildTemplate() {
            return Promise.resolve({ payload: { template: {} } })
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
  assert.match(wxml, /class="gear-stat-panel"/)
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

test('query detail page can pass current talent and gear context to simc', () => {
  const js = fs.readFileSync('pages/builds/detail.js', 'utf8')
  const wxml = fs.readFileSync('pages/builds/detail.wxml', 'utf8')
  const css = fs.readFileSync('pages/builds/detail.wxss', 'utf8')

  assert.match(wxml, /bindtap="openSimcWithBuildContext"/)
  assert.match(wxml, /带当前构筑去 SimC/)
  assert.match(js, /SIMC_BUILD_CONTEXT_STORAGE_KEY/)
  assert.match(js, /buildSimcContext\(\)/)
  assert.match(js, /details:\s*selectedDetail\.details \|\| \{\}/)
  assert.match(js, /selectedGearBySlot:\s*this\.data\.selectedGearBySlot/)
  assert.match(js, /statSnapshot:\s*this\.data\.gearStatSnapshot/)
  assert.match(js, /simcItems:\s*this\.data\.gearSimcItems/)
  assert.match(js, /statWeights:\s*\{/)
  assert.match(js, /weights:\s*this\.data\.activeStatRows/)
  assert.match(js, /wx\.setStorageSync\(SIMC_BUILD_CONTEXT_STORAGE_KEY/)
  assert.match(js, /\/pages\/simulator\/simc\?from=builds/)
  assert.match(js, /fail:\s*\(error\) =>/)
  assert.match(css, /\.simc-link-panel/)
  assert.match(css, /\.simc-link-button/)
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

test('native talent simulator page exposes WebSim tree controls and SimC handoff', () => {
  const app = JSON.parse(fs.readFileSync('app.json', 'utf8'))
  const js = fs.readFileSync('pages/builds/talent-simulator.js', 'utf8')
  const wxml = fs.readFileSync('pages/builds/talent-simulator.wxml', 'utf8')
  const css = fs.readFileSync('pages/builds/talent-simulator.wxss', 'utf8')

  assert.ok(app.pages.includes('pages/builds/talent-simulator'))
  assert.match(js, /game-asset/)
  assert.match(js, /requestWebsimBootstrap/)
  assert.match(js, /requestWebsimTalents/)
  assert.match(js, /requestWebsimProfile/)
  assert.match(js, /buildTalentViewModel/)
  assert.match(js, /tapTalentNode\(event\)/)
  assert.match(js, /selectChoiceTalent\(event\)/)
  assert.match(js, /resetTalents\(\)/)
  assert.match(js, /applyTalentImport\(\)/)
  assert.match(js, /copyTalentExport\(\)/)
  assert.match(js, /openTalentSimc\(\)/)
  assert.match(js, /saveTalentTemplate\(\)/)
  assert.match(js, /syncBuildTemplate/)
  assert.match(js, /SIMC_BUILD_CONTEXT_STORAGE_KEY/)
  assert.match(js, /talentEncoding\.lines/)
  assert.match(js, /activeTreeKey:\s*'class'/)
  assert.match(js, /treeNavItems/)
  assert.match(js, /activeSection/)
  assert.match(js, /selectTalentTree\(event\)/)
  assert.match(wxml, /class="talent-simulator-page"/)
  assert.match(wxml, /item\.gameAsset\.iconUrl/)
  assert.doesNotMatch(wxml, /item\.iconUrl/)
  assert.match(wxml, /wx:for="\{\{treeNavItems\}\}"/)
  assert.match(wxml, /class="\{\{item\.tabClass\}\}"/)
  assert.match(wxml, /class="active-tree-panel/)
  assert.match(wxml, /activeSection\.nodes/)
  assert.match(wxml, /bindtap="tapTalentNode"/)
  assert.match(wxml, /bindinput="updateTalentSearch"/)
  assert.match(wxml, /bindtap="resetTalents"/)
  assert.match(wxml, /bindtap="openTalentImport"/)
  assert.match(wxml, /bindtap="saveTalentTemplate"/)
  assert.match(wxml, /bindtap="copyTalentExport"/)
  assert.match(wxml, /bindtap="openTalentSimc"/)
  assert.match(wxml, /choiceSheet/)
  assert.match(wxml, /nodeDetailSheet/)
  assert.match(css, /\.tree-tabs/)
  assert.match(css, /\.active-tree-panel/)
  assert.match(css, /\.mobile-action-bar/)
  assert.match(css, /\.talent-node\.selected/)
  assert.match(css, /\.talent-node\.locked/)
  assert.match(css, /\.talent-choice-sheet/)
  assert.match(css, /\.talent-detail-sheet/)
  assert.doesNotMatch(wxml, /talent-board-scroll/)
  assert.doesNotMatch(wxml, /talent-column class/)
  assert.doesNotMatch(wxml, /talent-column spec/)
  assert.doesNotMatch(wxml, /talent-column hero/)
  assert.doesNotMatch(css, /min-width:\s*1500rpx/)
  assert.doesNotMatch(wxml, /class="talent-chip-list"/)
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
  assert.match(wxml, />社区模板</)
  assert.match(wxml, /communityTemplateSheet\.visible/)
  assert.match(wxml, /wx:for="\{\{activeCommunityTemplates\}\}"/)
  assert.match(wxml, /item\.name/)
  assert.match(wxml, /item\.sourceName/)
  assert.match(wxml, /item\.sampleLabel/)
  assert.match(wxml, /item\.keyLabel/)
  assert.match(wxml, /item\.updatedLabel/)
  assert.match(wxml, /item\.canApplyVisual/)
  assert.match(wxml, /bindtap="applyCommunityTemplate"/)
  assert.match(css, /\.community-template-sheet/)
  assert.match(css, /\.community-template-card/)
  assert.match(css, /\.community-template-card\.external/)
})

test('gear detail page exposes inline equipment simulator state and replacement sheet', () => {
  const js = fs.readFileSync('pages/builds/detail.js', 'utf8')
  const wxml = fs.readFileSync('pages/builds/detail.wxml', 'utf8')
  const css = fs.readFileSync('pages/builds/detail.wxss', 'utf8')

  assert.match(js, /game-asset/)
  assert.match(js, /requestWebsimGear/)
  assert.match(js, /requestWebsimGearStats/)
  assert.match(js, /selectedGearBySlot/)
  assert.match(js, /gearSlotRows/)
  assert.match(js, /gearStatSnapshot/)
  assert.match(js, /gearStatBlockers/)
  assert.match(js, /loadWebsimGearForSelection/)
  assert.match(js, /refreshGearStats/)
  assert.match(js, /openGearSlotSheet\(event\)/)
  assert.match(js, /selectGearCandidate\(event\)/)
  assert.match(js, /gearTemplateScenarios/)
  assert.match(js, /selectGearTemplateScenario\(event\)/)
  assert.doesNotMatch(js, /scenarioKey:\s*'single'/)
  assert.match(js, /selectedGearTemplateScenarioIndex/)
  assert.match(js, /this\.refreshGearStats\(\)/)
  assert.match(js, /saveGearTemplate\(\)/)
  assert.match(js, /canonicalGearTemplateLines/)
  assert.match(js, /syncBuildTemplate/)
  assert.match(wxml, />装备模拟</)
  assert.match(wxml, /查看满级属性、替换装备并校验 SimC-ready 状态/)
  assert.match(wxml, /class="gear-stat-panel"/)
  assert.match(wxml, /gearStatSnapshot\.statStatus/)
  assert.match(wxml, /gearStatBlockers/)
  assert.match(wxml, /class="gear-slot-grid"/)
  assert.match(wxml, /wx:for="\{\{gearSlotRows\}\}"/)
  assert.match(wxml, /class="gear-icon"/)
  assert.match(wxml, /item\.gameAsset\.iconUrl/)
  assert.doesNotMatch(wxml, /item\.iconUrl/)
  assert.match(wxml, /item\.displayName/)
  assert.match(wxml, /item\.statusLabel/)
  assert.match(wxml, /bindtap="openGearSlotSheet"/)
  assert.match(wxml, /gearSlotSheet\.visible/)
  assert.match(wxml, /wx:for="\{\{gearSlotSheet\.candidates\}\}"/)
  assert.match(wxml, /bindtap="selectGearCandidate"/)
  assert.match(wxml, /range="\{\{gearTemplateScenarios\}\}"/)
  assert.match(wxml, /bindchange="selectGearTemplateScenario"/)
  assert.match(wxml, /bindtap="saveGearTemplate"/)
  assert.match(css, /\.gear-stat-panel/)
  assert.match(css, /\.gear-slot-grid/)
  assert.match(css, /\.gear-slot-card/)
  assert.match(css, /\.gear-slot-sheet/)
  assert.match(css, /\.gear-template-actions/)
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

test('simc linkage derives talent and gear state from full specialization details', () => {
  const js = fs.readFileSync('pages/builds/detail.js', 'utf8')

  assert.match(js, /const talentDetail = detailForQuery\(selectedDetail,\s*'talents'\)/)
  assert.match(js, /buildTalentNodeRows\(talentDetail/)
  assert.match(js, /buildGearSlotRows/)
  assert.match(js, /websimClassKey/)
  assert.match(js, /websimSpecKey/)
})
