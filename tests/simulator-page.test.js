const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

function flushPromises() {
  return new Promise((resolve) => setTimeout(resolve, 0))
}

function expectedLocalMinute(value) {
  const date = new Date(value)
  const pad = (part) => String(part).padStart(2, '0')
  return [
    date.getFullYear(),
    pad(date.getMonth() + 1),
    pad(date.getDate())
  ].join('-') + ` ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function loadPageModule(modulePath, stubs) {
  let pageDefinition = null
  const originalPage = global.Page
  global.Page = (definition) => {
    pageDefinition = definition
  }
  const stubbedPaths = Object.keys(stubs || {})
  const previousCache = new Map()
  for (const stubPath of stubbedPaths) {
    const resolved = require.resolve(stubPath)
    previousCache.set(resolved, require.cache[resolved])
    require.cache[resolved] = {
      id: resolved,
      filename: resolved,
      loaded: true,
      exports: stubs[stubPath]
    }
  }
  try {
    delete require.cache[require.resolve(modulePath)]
    require(modulePath)
  } finally {
    global.Page = originalPage
    for (const stubPath of stubbedPaths) {
      const resolved = require.resolve(stubPath)
      const previous = previousCache.get(resolved)
      if (previous) {
        require.cache[resolved] = previous
      } else {
        delete require.cache[resolved]
      }
    }
  }
  return pageDefinition
}

function createPageInstance(pageDefinition) {
  return {
    ...pageDefinition,
    data: { ...(pageDefinition.data || {}) },
    setData(update) {
      this.data = { ...this.data, ...(update || {}) }
    }
  }
}

const sampleTalentTemplate = {
  id: 'talent-1',
  type: 'talent',
  title: '奥法 WebSim 天赋',
  rawString: 'websim:mage:arcane:spellslinger:n1:1',
  classKey: 'mage',
  className: '法师',
  specKey: 'arcane',
  specName: '奥术',
  status: 'saved',
  updatedAt: '2026-06-19T08:00:00Z'
}

const sampleGearTemplate = {
  id: 'gear-1',
  type: 'gear',
  title: '奥法 16 槽装备',
  rawString: 'head=hat,id=1\nneck=amulet,id=2',
  classKey: 'mage',
  className: '法师',
  specKey: 'arcane',
  specName: '奥术',
  status: 'complete',
  updatedAt: '2026-06-19T09:00:00Z'
}

const sampleGearStatSnapshot = {
  statStatus: 'verified',
  primary: { key: 'intellect', label: 'Intellect', value: '12,345', rawValue: 12345 },
  secondary: [
    { key: 'crit', label: 'Crit', value: '994', rawValue: 994, convertedValue: '28.6%' },
    { key: 'haste', label: 'Haste', value: '884', rawValue: 884, convertedValue: '18.3%' },
    { key: 'mastery', label: 'Mastery', value: '773', rawValue: 773, convertedValue: '42.1%' },
    { key: 'versatility', label: 'Versatility', value: '662', rawValue: 662, convertedValue: '8.2%' }
  ]
}

const sampleGearTemplateWithStatSnapshot = {
  ...sampleGearTemplate,
  metadata: { statSnapshot: sampleGearStatSnapshot }
}

const warriorTalentTemplate = {
  ...sampleTalentTemplate,
  id: 'talent-warrior',
  title: 'Warrior Talent',
  rawString: 'websim:warrior:arms:slayer:n1:1',
  classKey: 'warrior',
  className: 'Warrior',
  specKey: 'arms',
  specName: 'Arms',
  updatedAt: '2026-06-20T10:00:00Z'
}

const warriorGearTemplate = {
  ...sampleGearTemplate,
  id: 'gear-warrior',
  title: 'Warrior Gear',
  rawString: 'head=helm,id=11\nneck=amulet,id=12',
  classKey: 'warrior',
  className: 'Warrior',
  specKey: 'arms',
  specName: 'Arms',
  updatedAt: '2026-06-20T09:00:00Z'
}

const shamanTalentTemplate = {
  ...sampleTalentTemplate,
  id: 'talent-shaman',
  title: '元素萨满 Talent',
  rawString: 'websim:shaman:elemental:stormbringer:n1:1',
  classKey: 'shaman',
  className: '萨满祭司',
  specKey: 'elemental',
  specName: '元素',
  updatedAt: '2026-06-22T10:00:00Z'
}

const shamanGearTemplate = {
  ...sampleGearTemplate,
  id: 'gear-shaman',
  title: '元素萨满 Gear',
  rawString: 'head=helm,id=21\nneck=amulet,id=22',
  classKey: 'shaman',
  className: '萨满祭司',
  specKey: 'elemental',
  specName: '元素',
  updatedAt: '2026-06-22T09:00:00Z'
}

const simcClassOptions = [
  { name: 'Mage', key: 'mage', specializations: [{ title: 'Arcane', websimClassKey: 'mage', websimSpecKey: 'arcane' }] },
  { name: 'Warrior', key: 'warrior', specializations: [{ title: 'Arms', websimClassKey: 'warrior', websimSpecKey: 'arms' }] },
  { name: 'Priest', key: 'priest', specializations: [{ title: 'Discipline', websimClassKey: 'priest', websimSpecKey: 'discipline' }] }
]

const simcClassOptionsWithShaman = [
  ...simcClassOptions,
  { name: '萨满祭司', key: 'shaman', specializations: [{ title: '元素', websimClassKey: 'shaman', websimSpecKey: 'elemental' }] }
]

test('simc page exposes single aoe5 and approximate mythic plus scenarios', () => {
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/builds/builds-api.js': {
      fallbackBuildsHome: () => ({ classOptions: simcClassOptionsWithShaman }),
      requestBuildsHome: () => Promise.resolve({ payload: { classOptions: simcClassOptionsWithShaman }, fromFallback: true, error: '' })
    },
    '../pages/builds/websim-api.js': {
      requestWebsimGearStats: () => Promise.resolve({ payload: {}, fromFallback: true, error: '' })
    },
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: () => Promise.resolve({ payload: { templates: [] }, fromFallback: true, error: '' }),
      listBuildTemplates: () => [],
      syncBuildTemplate: () => Promise.resolve({ payload: {}, fromFallback: true, error: '' })
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorAnalysis: () => Promise.resolve({ payload: {}, fromFallback: false, error: '' })
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const wxml = fs.readFileSync('pages/simulator/simc.wxml', 'utf8')
  const page = createPageInstance(pageDefinition)

  assert.deepEqual(pageDefinition.data.scenarioOptions.map((item) => item.key), ['single', 'aoe_5', 'mythic_plus'])
  assert.deepEqual(pageDefinition.data.scenarioOptions.map((item) => item.desc), [
    '固定单目标，5分钟',
    '固定5目标，5分钟',
    '平均4目标，6分钟'
  ])
  assert.match(wxml, /selectedScenarioTitle/)
  assert.equal(page.data.selectedScenarioTitle, '单体')
  page.selectScenario({ currentTarget: { dataset: { key: 'mythic_plus' } } })
  assert.equal(page.data.selectedScenarioKey, 'mythic_plus')
  assert.equal(page.data.selectedScenarioTitle, '近似大秘境')
})

test('simc page keeps submission setup compact and scrollable', () => {
  const wxml = fs.readFileSync('pages/simulator/simc.wxml', 'utf8')
  const css = fs.readFileSync('pages/simulator/simc.wxss', 'utf8')

  assert.match(wxml, /<scroll-view class="page-scroll simc-scroll" scroll-y type="list">/)
  assert.match(wxml, /identity-selector-row/)
  assert.match(wxml, /class="template-selector compact-selector class-selector identity-selector-card"/)
  assert.match(wxml, /class="template-selector compact-selector race-selector identity-selector-card"/)
  assert.match(wxml, /class="template-selector scenario-selector"/)
  assert.match(css, /\.simc-scroll\s*\{[\s\S]*min-height:\s*0/)
  assert.match(css, /\.simc-page\s*\{[\s\S]*padding:[^;]*calc\(150rpx \+ env\(safe-area-inset-bottom\)\)/)
  assert.match(css, /\.identity-selector-row\s*\{[\s\S]*grid-template-columns:\s*repeat\(2, minmax\(0, 1fr\)\)/)
  assert.match(css, /\.segmented-row\s*\{[\s\S]*grid-template-columns:\s*repeat\(3, minmax\(0, 1fr\)\)/)
})

test('simc page exposes combat preparation policy and temporary buff toggles before validation', () => {
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/builds/builds-api.js': {
      fallbackBuildsHome: () => ({ classOptions: simcClassOptionsWithShaman }),
      requestBuildsHome: () => Promise.resolve({ payload: { classOptions: simcClassOptionsWithShaman }, fromFallback: true, error: '' })
    },
    '../pages/builds/websim-api.js': {
      requestWebsimGearStats: () => Promise.resolve({ payload: {}, fromFallback: true, error: '' })
    },
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: () => Promise.resolve({ payload: { templates: [] }, fromFallback: true, error: '' }),
      listBuildTemplates: () => [],
      syncBuildTemplate: () => Promise.resolve({ payload: {}, fromFallback: true, error: '' })
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorAnalysis: () => Promise.resolve({ payload: {}, fromFallback: false, error: '' })
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const wxml = fs.readFileSync('pages/simulator/simc.wxml', 'utf8')
  const page = createPageInstance(pageDefinition)

  assert.match(wxml, /combat-preparation-panel/)
  assert.match(wxml, /combatPreparationRows/)
  assert.doesNotMatch(wxml, /后端校验/)
  assert.doesNotMatch(wxml, /preparation-policy-desc/)
  assert.match(wxml, /temporaryBuffOptions/)
  assert.match(wxml, /toggleTemporaryBuff/)
  assert.deepEqual(page.data.temporaryBuffOptions.map((item) => item.key), ['bloodlust', 'combatPotion', 'weaponOil'])
  assert.equal(page.data.temporaryBuffOptions.some((item) => item.enabled), false)
})

test('simc page names the selected class combat buffs before validation', async () => {
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/builds/builds-api.js': {
      fallbackBuildsHome: () => ({ classOptions: simcClassOptionsWithShaman }),
      requestBuildsHome: () => Promise.resolve({ payload: { classOptions: simcClassOptionsWithShaman }, fromFallback: true, error: '' })
    },
    '../pages/builds/websim-api.js': {
      requestWebsimGearStats: () => Promise.resolve({ payload: {}, fromFallback: true, error: '' })
    },
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: (type) => Promise.resolve({
        payload: { templates: type === 'talent' ? [sampleTalentTemplate, shamanTalentTemplate] : [sampleGearTemplate, shamanGearTemplate] },
        fromFallback: true,
        error: ''
      }),
      listBuildTemplates: () => [],
      syncBuildTemplate: () => Promise.resolve({ payload: {}, fromFallback: true, error: '' })
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorAnalysis: () => Promise.resolve({ payload: {}, fromFallback: false, error: '' })
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const page = createPageInstance(pageDefinition)
  await page.loadTemplateLists()
  await flushPromises()

  assert.equal(page.data.selectedClassKey, 'shaman')
  assert.equal(page.data.selectedTalentTemplate.specKey, 'elemental')
  assert.equal(page.data.combatPreparationRows[0].label, '团队增益')
  assert.equal(page.data.combatPreparationRows[0].value, '天怒')
  assert.equal(page.data.combatPreparationRows[1].label, '职业准备')
  assert.equal(page.data.combatPreparationRows[1].value, '无增益')
})

test('simc page uses a fixed saved-template workflow without chat composer', () => {
  const js = fs.readFileSync('pages/simulator/simc.js', 'utf8')
  const wxml = fs.readFileSync('pages/simulator/simc.wxml', 'utf8')
  const css = fs.readFileSync('pages/simulator/simc.wxss', 'utf8')

  assert.match(wxml, /data-selector="class"[\s\S]*bindtap="openSelectorSheet"/)
  assert.match(wxml, /data-selector="race"[\s\S]*bindtap="openSelectorSheet"/)
  assert.match(wxml, /data-selector="talent"[\s\S]*bindtap="openSelectorSheet"/)
  assert.match(wxml, /data-selector="gear"[\s\S]*bindtap="openSelectorSheet"/)
  assert.match(wxml, /selectorSheet\.visible/)
  assert.match(wxml, /selectSelectorOption/)
  assert.doesNotMatch(wxml, /<picker\b/)
  assert.match(wxml, /class="template-selector compact-selector class-selector identity-selector-card"/)
  assert.match(wxml, /class="template-selector compact-selector"/)
  assert.match(wxml, /selector-row/)
  assert.match(wxml, /toolbar-picker/)
  assert.doesNotMatch(wxml, /picker-label/)
  assert.match(wxml, /picker-value/)
  assert.match(wxml, /template-selector/)
  assert.doesNotMatch(wxml, /template-workspace/)
  assert.match(wxml, /talentTemplates/)
  assert.match(wxml, /gearTemplates/)
  assert.match(wxml, /scenarioOptions/)
  assert.match(wxml, /\{\{talentTemplates\.length\}\} 个配置/)
  assert.match(wxml, /\{\{gearTemplates\.length\}\} 个配置/)
  assert.doesNotMatch(wxml, /\{\{classOptions\.length\}\}/)
  assert.doesNotMatch(wxml, /analysisTypeOptions/)
  assert.doesNotMatch(wxml, /selectAnalysisType/)
  assert.doesNotMatch(js, /ANALYSIS_TYPE_OPTIONS/)
  assert.doesNotMatch(js, /selectAnalysisType/)
  assert.match(wxml, /bindtap="confirmTemplateSimulation"/)
  assert.match(wxml, /bindtap="submitConfirmedTask"/)
  assert.match(wxml, /blockedReasons/)
  assert.match(wxml, /summary-layout/)
  assert.match(wxml, /summary-left/)
  assert.match(wxml, /summary-stat-panel/)
  assert.match(wxml, /summaryStatPanel\.primary/)
  assert.match(wxml, /summaryStatPanel\.secondaryRows/)
  assert.match(wxml, /item\.percentText/)
  assert.match(wxml, /确认摘要/)
  assert.match(wxml, /种族/)
  assert.doesNotMatch(wxml, /chat-messages|chat-composer|textarea|chatInput|quickReplies/)
  assert.match(js, /fetchBuildTemplates/)
  assert.match(js, /selectedClassKey/)
  assert.match(js, /selectedRaceKey/)
  assert.match(js, /summaryStatPanelFromSnapshot/)
  assert.match(js, /selectRace\(/)
  assert.match(js, /raceKey:\s*this\.data\.selectedRaceKey/)
  assert.match(js, /selectClass\(/)
  assert.match(js, /selectedClassIndex/)
  assert.match(js, /selectedRaceIndex/)
  assert.match(js, /selectedTalentTemplateIndex/)
  assert.match(js, /selectedGearTemplateIndex/)
  assert.match(js, /buildTemplatePayload\(/)
  assert.match(js, /openSelectorSheet\(/)
  assert.match(js, /selectSelectorOption\(/)
  assert.match(js, /mode:\s*'simcraft_template'/)
  assert.match(js, /buildTemplatePayload\(true,\s*false\)/)
  assert.match(js, /confirmOnly:\s*false/)
  assert.match(js, /saveTask:\s*true/)
  assert.match(js, /allowInsecureGuestRequest:\s*true/)
  assert.doesNotMatch(js, /mode:\s*'simcraft_agent'|sendChatMessage|sendChatContent|useQuickReply|buildPromptFromContext/)
  assert.match(css, /\.template-selector/)
  assert.doesNotMatch(css, /\.template-workspace/)
  assert.match(css, /\.template-hero \+ \.identity-selector-row/)
  assert.match(css, /\.compact-selector/)
  assert.match(css, /\.selector-row/)
  assert.match(css, /\.toolbar-picker/)
  assert.match(css, /\.selector-sheet-mask/)
  assert.match(css, /\.selector-sheet/)
  assert.match(css, /\.selector-sheet-option/)
  assert.doesNotMatch(css, /\.picker-label/)
  assert.match(css, /\.picker-value/)
  assert.match(css, /\.confirm-summary/)
  assert.match(css, /\.summary-layout/)
  assert.match(css, /\.summary-left/)
  assert.match(css, /\.summary-stat-panel/)
  assert.match(css, /\.summary-left \.summary-value[\s\S]*white-space:\s*nowrap/)
  assert.match(css, /\.summary-left \.summary-value[\s\S]*text-overflow:\s*ellipsis/)
  assert.match(css, /\.summary-secondary-percent/)
  assert.match(css, /\.blocked-panel/)
  assert.doesNotMatch(css, /\.class-option|\.template-option/)
  assert.doesNotMatch(css, /\.chat-composer|\.chat-row-user|\.quick-reply/)
})

test('simc action buttons avoid native loading overlay flicker', () => {
  const wxml = fs.readFileSync('pages/simulator/simc.wxml', 'utf8')
  const css = fs.readFileSync('pages/simulator/simc.wxss', 'utf8')
  const pageBlock = (css.match(/\.simc-page\s*\{[^}]*\}/) || [''])[0]
  const scrollBlock = (css.match(/\.simc-scroll\s*\{[^}]*\}/) || [''])[0]
  const actionBarBlock = (css.match(/\.action-bar\s*\{[^}]*\}/) || [''])[0]

  assert.doesNotMatch(wxml, /<picker\b/)
  assert.match(wxml, /<scroll-view class="page-scroll simc-scroll" scroll-y type="list">/)
  assert.doesNotMatch(wxml, /<button\b/)
  assert.doesNotMatch(wxml, /\sloading="\{\{(?:confirming|submittingTask)\}\}"/)
  assert.doesNotMatch(wxml, /template-workspace/)
  assert.match(wxml, /button-spinner/)
  assert.match(wxml, /校验中/)
  assert.match(wxml, /提交中/)
  assert.match(css, /(?:^|\n)page\s*\{[^}]*background:\s*#060606/)
  assert.doesNotMatch(css, /\.template-workspace/)
  assert.match(pageBlock, /min-height:\s*100%/)
  assert.match(scrollBlock, /min-height:\s*0/)
  assert.match(scrollBlock, /height:\s*0/)
  assert.match(css, /\.template-hero \+ \.identity-selector-row\s*\{[\s\S]*margin-top:\s*14rpx/)
  assert.match(actionBarBlock, /position:\s*fixed/)
  assert.match(actionBarBlock, /background:\s*#060606/)
  assert.match(css, /\.button-spinner/)
  assert.match(css, /@keyframes\s+button-spin/)
})

test('simc custom selector sheet applies race choices without native picker events', async () => {
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/builds/builds-api.js': {
      fallbackBuildsHome: () => ({ classOptions: simcClassOptions }),
      requestBuildsHome: () => Promise.resolve({ payload: { classOptions: simcClassOptions }, fromFallback: true, error: '' })
    },
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: (type) => Promise.resolve({
        payload: {
          templates: type === 'talent'
            ? [sampleTalentTemplate, warriorTalentTemplate]
            : [sampleGearTemplate, warriorGearTemplate]
        },
        fromFallback: true,
        error: ''
      }),
      listBuildTemplates: () => [],
      buildTemplateSummary: () => []
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorAnalysis: () => Promise.resolve({ payload: {}, fromFallback: false, error: '' })
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const wxml = fs.readFileSync('pages/simulator/simc.wxml', 'utf8')
  const page = createPageInstance(pageDefinition)
  await page.loadTemplateLists()
  await flushPromises()

  page.openSelectorSheet({ currentTarget: { dataset: { selector: 'race' } } })
  assert.equal(page.data.selectorSheet.visible, true)
  assert.equal(page.data.selectorSheet.type, 'race')
  assert.equal(page.data.selectorSheet.title, '选择种族')
  assert.equal(page.data.selectorSheet.options[0].label, '人类')
  assert.equal(page.data.selectorSheet.options.some((item) => item.selected && item.key === page.data.selectedRaceKey), true)

  page.setData({
    canSubmitTask: true,
    taskSubmitted: true,
    latestAnalysis: { agent: { status: 'template_ready' } }
  })
  page.selectSelectorOption({ currentTarget: { dataset: { index: 1 } } })

  assert.equal(page.data.selectorSheet.visible, false)
  assert.equal(page.data.selectedRaceKey, 'dwarf')
  assert.equal(page.data.selectedRaceName, '矮人')
  assert.equal(page.data.canSubmitTask, false)
  assert.equal(page.data.taskSubmitted, false)
  assert.equal(page.data.latestAnalysis, null)
})

test('simc page does not duplicate template loading on initial show', async () => {
  let buildsHomeRequests = 0
  let fetchTalentRequests = 0
  let fetchGearRequests = 0
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/builds/builds-api.js': {
      fallbackBuildsHome: () => ({ classOptions: simcClassOptions }),
      requestBuildsHome: () => {
        buildsHomeRequests += 1
        return Promise.resolve({ payload: { classOptions: simcClassOptions }, fromFallback: false, error: '' })
      }
    },
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: (type) => {
        if (type === 'talent') fetchTalentRequests += 1
        if (type === 'gear') fetchGearRequests += 1
        return Promise.resolve({
          payload: {
            templates: type === 'talent' ? [sampleTalentTemplate] : [sampleGearTemplate]
          },
          fromFallback: false,
          error: ''
        })
      },
      listBuildTemplates: () => [],
      buildTemplateSummary: () => []
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorAnalysis: () => Promise.resolve({ payload: {}, fromFallback: false, error: '' })
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const wxml = fs.readFileSync('pages/simulator/simc.wxml', 'utf8')
  const page = createPageInstance(pageDefinition)

  page.onLoad({})
  page.onShow()
  await flushPromises()
  await flushPromises()

  assert.equal(buildsHomeRequests, 1)
  assert.equal(fetchTalentRequests, 1)
  assert.equal(fetchGearRequests, 1)
})

test('simc page keeps local template state when remote template loading fails', async () => {
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/builds/builds-api.js': {
      fallbackBuildsHome: () => ({ classOptions: simcClassOptions }),
      requestBuildsHome: () => Promise.reject(new Error('home timeout'))
    },
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: () => Promise.reject(new Error('template timeout')),
      listBuildTemplates: (type) => (type === 'talent' ? [sampleTalentTemplate] : [sampleGearTemplate]),
      buildTemplateSummary: () => []
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorAnalysis: () => Promise.resolve({ payload: {}, fromFallback: false, error: '' })
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const page = createPageInstance(pageDefinition)

  await page.loadTemplateLists()
  await flushPromises()

  assert.equal(page.data.loadingTemplates, false)
  assert.equal(page.data.fromFallback, true)
  assert.match(page.data.requestError, /home timeout|template timeout/)
  assert.equal(page.data.selectedClassKey, 'mage')
  assert.equal(page.data.selectedTalentTemplate.id, 'talent-1')
  assert.equal(page.data.selectedGearTemplate.id, 'gear-1')
  assert.equal(page.data.canConfirm, true)
})

test('simc page ignores stale template responses after a newer selection', async () => {
  let resolveHome
  let resolveTalent
  let resolveGear
  const remoteHome = new Promise((resolve) => { resolveHome = resolve })
  const remoteTalent = new Promise((resolve) => { resolveTalent = resolve })
  const remoteGear = new Promise((resolve) => { resolveGear = resolve })
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/builds/builds-api.js': {
      fallbackBuildsHome: () => ({ classOptions: simcClassOptions }),
      requestBuildsHome: () => remoteHome
    },
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: (type) => (type === 'talent' ? remoteTalent : remoteGear),
      listBuildTemplates: (type) => (type === 'talent'
        ? [sampleTalentTemplate, warriorTalentTemplate]
        : [sampleGearTemplate, warriorGearTemplate]),
      buildTemplateSummary: () => []
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorAnalysis: () => Promise.resolve({ payload: {}, fromFallback: false, error: '' })
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const page = createPageInstance(pageDefinition)
  const loading = page.loadTemplateLists()
  assert.equal(page.data.selectedClassKey, 'warrior')

  page.selectClass({ detail: { value: 0 } })
  assert.equal(page.data.selectedClassKey, 'mage')

  resolveHome({ payload: { classOptions: simcClassOptions }, fromFallback: false, error: '' })
  resolveTalent({ payload: { templates: [warriorTalentTemplate] }, fromFallback: false, error: '' })
  resolveGear({ payload: { templates: [warriorGearTemplate] }, fromFallback: false, error: '' })
  await loading
  await flushPromises()

  assert.equal(page.data.selectedClassKey, 'mage')
  assert.equal(page.data.selectedTalentTemplate && page.data.selectedTalentTemplate.id, 'talent-1')
  assert.equal(page.data.selectedGearTemplate && page.data.selectedGearTemplate.id, 'gear-1')
  assert.equal(page.data.canConfirm, true)
})

test('simc page defaults to the most recent template class and filters picker templates', async () => {
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/builds/builds-api.js': {
      fallbackBuildsHome: () => ({ classOptions: simcClassOptions }),
      requestBuildsHome: () => Promise.resolve({ payload: { classOptions: simcClassOptions }, fromFallback: true, error: '' })
    },
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: (type) => Promise.resolve({
        payload: {
          templates: type === 'talent'
            ? [sampleTalentTemplate, warriorTalentTemplate]
            : [sampleGearTemplate, warriorGearTemplate]
        },
        fromFallback: true,
        error: ''
      }),
      listBuildTemplates: () => [],
      buildTemplateSummary: () => []
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorAnalysis: () => Promise.resolve({ payload: {}, fromFallback: false, error: '' })
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const page = createPageInstance(pageDefinition)
  await page.loadTemplateLists()
  await flushPromises()

  assert.deepEqual(page.data.classOptions.map((item) => item.key), ['mage', 'warrior', 'priest'])
  assert.equal(page.data.selectedClassKey, 'warrior')
  assert.equal(page.data.selectedClassIndex, 1)
  assert.deepEqual(page.data.talentTemplates.map((item) => item.id), ['talent-warrior'])
  assert.deepEqual(page.data.gearTemplates.map((item) => item.id), ['gear-warrior'])
  assert.equal(page.data.selectedTalentTemplate.id, 'talent-warrior')
  assert.equal(page.data.selectedGearTemplate.id, 'gear-warrior')
  assert.equal(page.data.canConfirm, true)

  page.selectClass({ detail: { value: 0 } })
  assert.equal(page.data.selectedClassKey, 'mage')
  assert.deepEqual(page.data.talentTemplates.map((item) => item.id), ['talent-1'])
  assert.deepEqual(page.data.gearTemplates.map((item) => item.id), ['gear-1'])
  assert.equal(page.data.selectedTalentTemplate.id, 'talent-1')
  assert.equal(page.data.selectedGearTemplate.id, 'gear-1')
  assert.equal(page.data.canConfirm, true)

  page.selectClass({ detail: { value: 2 } })
  assert.equal(page.data.selectedClassKey, 'priest')
  assert.deepEqual(page.data.talentTemplates, [])
  assert.deepEqual(page.data.gearTemplates, [])
  assert.equal(page.data.selectedTalentTemplate, null)
  assert.equal(page.data.selectedGearTemplate, null)
  assert.equal(page.data.emptyState.talent, '尚未保存天赋模板')
  assert.equal(page.data.emptyState.gear, '尚未保存装备模板')
  assert.equal(page.data.canConfirm, false)
})

test('simc page loads saved talent and gear templates with empty states', async () => {
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/builds/builds-api.js': {
      fallbackBuildsHome: () => ({ classOptions: simcClassOptions }),
      requestBuildsHome: () => Promise.resolve({ payload: { classOptions: simcClassOptions }, fromFallback: true, error: '' })
    },
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: (type) => Promise.resolve({
        payload: { templates: type === 'talent' ? [sampleTalentTemplate] : [] },
        fromFallback: true,
        error: ''
      }),
      listBuildTemplates: (type) => (type === 'talent' ? [sampleTalentTemplate] : []),
      buildTemplateSummary: () => []
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorAnalysis: () => Promise.resolve({ payload: {}, fromFallback: false, error: '' })
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const page = createPageInstance(pageDefinition)
  await page.loadTemplateLists()
  await flushPromises()

  assert.deepEqual(page.data.allTalentTemplates, [sampleTalentTemplate])
  assert.deepEqual(page.data.classOptions.map((item) => item.key), ['mage', 'warrior', 'priest'])
  assert.equal(page.data.selectedClassKey, 'mage')
  assert.deepEqual(page.data.talentTemplates, [sampleTalentTemplate])
  assert.deepEqual(page.data.gearTemplates, [])
  assert.equal(page.data.selectedTalentTemplate.id, 'talent-1')
  assert.equal(page.data.selectedGearTemplate, null)
  assert.equal(page.data.emptyState.gear, '尚未保存装备模板')
  assert.equal(page.data.emptyState.talent, '')
  assert.deepEqual(page.data.summaryStatPanel.secondaryRows.map((row) => row.percentText), ['缺装备', '缺装备', '缺装备', '缺装备'])
  assert.equal(page.data.canConfirm, false)
})

test('simc page keeps empty talent and gear template selectors compact', () => {
  const wxml = fs.readFileSync('pages/simulator/simc.wxml', 'utf8')

  assert.match(wxml, /data-selector="talent"[\s\S]*emptyState\.talent/)
  assert.match(wxml, /data-selector="gear"[\s\S]*emptyState\.gear/)
  assert.doesNotMatch(wxml, /<view class="empty-state" wx:if="\{\{emptyState\.talent\}\}">/)
  assert.doesNotMatch(wxml, /<view class="empty-state" wx:if="\{\{emptyState\.gear\}\}">/)
})

test('simc page derives the summary stat panel from verified gear stat snapshots', async () => {
  const gearWithStats = {
    ...sampleGearTemplate,
    title: 'Very long Arcane gear template title that should stay single line in summary',
    metadata: { statSnapshot: sampleGearStatSnapshot }
  }
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/builds/builds-api.js': {
      fallbackBuildsHome: () => ({ classOptions: simcClassOptions }),
      requestBuildsHome: () => Promise.resolve({ payload: { classOptions: simcClassOptions }, fromFallback: true, error: '' })
    },
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: (type) => Promise.resolve({
        payload: { templates: type === 'talent' ? [sampleTalentTemplate] : [gearWithStats] },
        fromFallback: true,
        error: ''
      }),
      listBuildTemplates: () => [],
      buildTemplateSummary: () => []
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorAnalysis: () => Promise.resolve({ payload: {}, fromFallback: false, error: '' })
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const page = createPageInstance(pageDefinition)
  await page.loadTemplateLists()
  await flushPromises()

  assert.equal(page.data.summaryStatPanel.primary.valueText, '12,345')
  assert.deepEqual(page.data.summaryStatPanel.secondaryRows.map((row) => row.key), ['crit', 'haste', 'mastery', 'versatility'])
  assert.deepEqual(page.data.summaryStatPanel.secondaryRows.map((row) => row.percentText), ['28.6%', '18.3%', '42.1%', '8.2%'])

  page.applyAnalysisResult({
    request: {
      buildContext: {
        details: {
          statWeights: {
            statSnapshot: {
              ...sampleGearStatSnapshot,
              primary: { key: 'intellect', label: 'Intellect', value: '13,000', rawValue: 13000 },
              secondary: [
                { key: 'crit', label: 'Crit', value: '1010', rawValue: 1010, convertedValue: '29.1%' },
                ...sampleGearStatSnapshot.secondary.slice(1)
              ]
            }
          }
        }
      }
    },
    agent: { status: 'template_ready', canSubmitTask: true, validation: { passed: true, errors: [] } },
    simulation: { ran: false, error: '', metrics: {} },
    recommendations: []
  }, false, '')

  assert.equal(page.data.summaryStatPanel.primary.valueText, '13,000')
  assert.equal(page.data.summaryStatPanel.secondaryRows[0].percentText, '29.1%')
})

test('simc page refreshes summary stats for structured gear templates without cached snapshots', async () => {
  const requests = []
  const syncedTemplates = []
  let resolveStats
  const statsResponse = new Promise((resolve) => {
    resolveStats = resolve
  })
  const structuredGearTemplate = {
    ...sampleGearTemplate,
    rawString: JSON.stringify({
      schemaRevision: 'websim-gear-enhancement-snapshot-v1',
      gearBySlot: { head: { slot: 'head', itemId: '1', id: '1', ilevel: 707, bonus_id: '12345' } },
      enhancementBySlot: {}
    }),
    metadata: { maxLevel: 90 }
  }
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/builds/builds-api.js': {
      fallbackBuildsHome: () => ({ classOptions: simcClassOptions }),
      requestBuildsHome: () => Promise.resolve({ payload: { classOptions: simcClassOptions }, fromFallback: true, error: '' })
    },
    '../pages/builds/websim-api.js': {
      requestWebsimGearStats: (request) => {
        requests.push(request)
        return statsResponse
      }
    },
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: (type) => Promise.resolve({
        payload: { templates: type === 'talent' ? [sampleTalentTemplate] : [structuredGearTemplate] },
        fromFallback: true,
        error: ''
      }),
      listBuildTemplates: () => [],
      buildTemplateSummary: () => [],
      syncBuildTemplate: (template) => {
        syncedTemplates.push(template)
        return Promise.resolve({ payload: { template, templates: [template] }, fromFallback: false, error: '' })
      }
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorAnalysis: () => Promise.resolve({ payload: {}, fromFallback: false, error: '' })
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const page = createPageInstance(pageDefinition)

  const loadPromise = page.loadTemplateLists()
  await flushPromises()

  assert.equal(requests.length, 1)
  assert.equal(requests[0].classKey, 'mage')
  assert.equal(requests[0].specKey, 'arcane')
  assert.equal(requests[0].talents, sampleTalentTemplate.rawString)
  assert.ok(requests[0].rawString.startsWith('{'))
  assert.deepEqual(page.data.summaryStatPanel.secondaryRows.map((row) => row.percentText), ['计算中', '计算中', '计算中', '计算中'])

  resolveStats({ payload: { ...sampleGearStatSnapshot, blockers: [] }, fromFallback: false, error: '' })
  await loadPromise
  await flushPromises()
  await flushPromises()

  assert.equal(page.data.summaryStatPanel.primary.valueText, '12,345')
  assert.equal(page.data.summaryStatPanel.secondaryRows[0].percentText, '28.6%')
  assert.equal(syncedTemplates.length, 1)
  assert.equal(syncedTemplates[0].metadata.statSnapshot.statStatus, 'verified')
  assert.equal(page.data.selectedGearTemplate.metadata.statSnapshot, undefined)
  assert.equal(page.buildTemplatePayload(true, false).templateContext.gear.metadata.statSnapshot.statStatus, 'verified')
})

test('simc page does not rewrite large gear template objects when summary stats refresh completes', async () => {
  const updates = []
  const syncedTemplates = []
  let resolveStats
  const statsResponse = new Promise((resolve) => {
    resolveStats = resolve
  })
  const gearSnapshot = {
    schemaRevision: 'websim-gear-enhancement-snapshot-v1',
    gearBySlot: {
      head: {
        slot: 'head',
        itemId: '1',
        id: '1',
        ilevel: 707,
        bonus_id: '12345',
        debugPayload: 'x'.repeat(1024 * 256)
      }
    },
    enhancementBySlot: {}
  }
  const structuredGearTemplate = {
    ...sampleGearTemplate,
    rawString: 'legacy metadata snapshot',
    metadata: { maxLevel: 90, gearSnapshot }
  }
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/builds/builds-api.js': {
      fallbackBuildsHome: () => ({ classOptions: simcClassOptions }),
      requestBuildsHome: () => Promise.resolve({ payload: { classOptions: simcClassOptions }, fromFallback: true, error: '' })
    },
    '../pages/builds/websim-api.js': {
      requestWebsimGearStats: () => statsResponse
    },
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: (type) => Promise.resolve({
        payload: { templates: type === 'talent' ? [sampleTalentTemplate] : [structuredGearTemplate] },
        fromFallback: true,
        error: ''
      }),
      listBuildTemplates: () => [],
      buildTemplateSummary: () => [],
      syncBuildTemplate: (template) => {
        syncedTemplates.push(template)
        return Promise.resolve({ payload: { template, templates: [template] }, fromFallback: false, error: '' })
      }
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorAnalysis: () => Promise.resolve({ payload: {}, fromFallback: false, error: '' })
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const page = createPageInstance(pageDefinition)
  const originalSetData = page.setData
  page.setData = function setData(update) {
    updates.push(update || {})
    return originalSetData.call(this, update)
  }

  const loadPromise = page.loadTemplateLists()
  await flushPromises()
  updates.length = 0

  resolveStats({ payload: { ...sampleGearStatSnapshot, blockers: [] }, fromFallback: false, error: '' })
  await loadPromise
  await flushPromises()
  await flushPromises()

  const templateRewriteUpdates = updates.filter((update) => (
    Object.prototype.hasOwnProperty.call(update, 'selectedGearTemplate') ||
    Object.prototype.hasOwnProperty.call(update, 'gearTemplates') ||
    Object.prototype.hasOwnProperty.call(update, 'allGearTemplates')
  ))
  assert.deepEqual(templateRewriteUpdates, [])
  assert.equal(page.data.summaryStatPanel.primary.valueText, '12,345')
  assert.equal(syncedTemplates[0].metadata.statSnapshot.statStatus, 'verified')
})

test('simc page clears pending summary stat refresh when selection no longer has a stats request', async () => {
  const requests = []
  let resolveStats
  const statsResponse = new Promise((resolve) => {
    resolveStats = resolve
  })
  const structuredGearTemplate = {
    ...sampleGearTemplate,
    rawString: JSON.stringify({
      schemaRevision: 'websim-gear-enhancement-snapshot-v1',
      gearBySlot: { head: { slot: 'head', itemId: '1', id: '1', ilevel: 707, bonus_id: '12345' } },
      enhancementBySlot: {}
    }),
    metadata: { maxLevel: 90 }
  }
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/builds/builds-api.js': {
      fallbackBuildsHome: () => ({ classOptions: simcClassOptions }),
      requestBuildsHome: () => Promise.resolve({ payload: { classOptions: simcClassOptions }, fromFallback: true, error: '' })
    },
    '../pages/builds/websim-api.js': {
      requestWebsimGearStats: (request) => {
        requests.push(request)
        return statsResponse
      }
    },
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: (type) => Promise.resolve({
        payload: { templates: type === 'talent' ? [sampleTalentTemplate] : [structuredGearTemplate] },
        fromFallback: true,
        error: ''
      }),
      listBuildTemplates: () => [],
      buildTemplateSummary: () => [],
      syncBuildTemplate: () => Promise.resolve({ payload: {}, fromFallback: true, error: '' })
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorAnalysis: () => Promise.resolve({ payload: {}, fromFallback: false, error: '' })
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const page = createPageInstance(pageDefinition)

  await page.loadTemplateLists()
  await flushPromises()

  assert.equal(requests.length, 1)
  assert.equal(page.data.summaryStatsLoading, true)

  page.selectClass({ detail: { value: 2 } })

  assert.equal(page.data.selectedClassKey, 'priest')
  assert.equal(page.data.selectedGearTemplate, null)
  assert.equal(page.data.summaryStatsRequestSignature, '')
  assert.equal(page.data.summaryStatsLoading, false)

  resolveStats({ payload: { ...sampleGearStatSnapshot, blockers: [] }, fromFallback: false, error: '' })
  await flushPromises()
  await flushPromises()

  assert.equal(page.data.selectedClassKey, 'priest')
  assert.equal(page.data.selectedGearTemplate, null)
  assert.equal(page.data.summaryStatPanel.primary.valueText, '缺装备')
})

test('simc page explains blocked summary stat snapshots', async () => {
  const structuredGearTemplate = {
    ...sampleGearTemplate,
    rawString: JSON.stringify({
      schemaRevision: 'websim-gear-enhancement-snapshot-v1',
      gearBySlot: { waist: { slot: 'waist', itemId: '244611', id: '244611', bonus_id: '1808/8960/12214' } },
      enhancementBySlot: {}
    }),
    metadata: { maxLevel: 90 }
  }
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/builds/builds-api.js': {
      fallbackBuildsHome: () => ({ classOptions: simcClassOptions }),
      requestBuildsHome: () => Promise.resolve({ payload: { classOptions: simcClassOptions }, fromFallback: true, error: '' })
    },
    '../pages/builds/websim-api.js': {
      requestWebsimGearStats: () => Promise.resolve({
        payload: {
          statStatus: 'blocked',
          blockers: ['Missing core SimC gear slots: waist, feet.']
        },
        fromFallback: false,
        error: ''
      })
    },
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: (type) => Promise.resolve({
        payload: { templates: type === 'talent' ? [sampleTalentTemplate] : [structuredGearTemplate] },
        fromFallback: true,
        error: ''
      }),
      listBuildTemplates: () => [],
      buildTemplateSummary: () => [],
      syncBuildTemplate: () => Promise.resolve({ payload: {}, fromFallback: true, error: '' })
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorAnalysis: () => Promise.resolve({ payload: {}, fromFallback: false, error: '' })
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const page = createPageInstance(pageDefinition)

  await page.loadTemplateLists()
  await flushPromises()

  assert.equal(page.data.summaryStatPanel.noteText, '缺少可执行装备槽位：腰带、脚部')
  assert.deepEqual(page.data.summaryStatPanel.secondaryRows.map((row) => row.percentText), ['不可用', '不可用', '不可用', '不可用'])
})

test('simc page does not leak raw simc diagnostics in blocked summary stat notes', async () => {
  const rawDiagnostic = "Trivial: Player 'websim_unholy' at slot hands has inconsistency between name 'item_249971' and 'relentless_riders_bonegrasps' for id 249971"
  const structuredGearTemplate = {
    ...sampleGearTemplate,
    title: '邪 DK 装备',
    rawString: JSON.stringify({
      schemaRevision: 'websim-gear-enhancement-snapshot-v1',
      gearBySlot: { hands: { slot: 'hands', itemId: '249971', id: '249971', bonus_id: '13534' } },
      enhancementBySlot: {}
    }),
    metadata: { maxLevel: 90 }
  }
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/builds/builds-api.js': {
      fallbackBuildsHome: () => ({ classOptions: simcClassOptions }),
      requestBuildsHome: () => Promise.resolve({ payload: { classOptions: simcClassOptions }, fromFallback: true, error: '' })
    },
    '../pages/builds/websim-api.js': {
      requestWebsimGearStats: () => Promise.resolve({
        payload: {
          statStatus: 'blocked',
          blockers: [rawDiagnostic]
        },
        fromFallback: false,
        error: ''
      })
    },
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: (type) => Promise.resolve({
        payload: { templates: type === 'talent' ? [sampleTalentTemplate] : [structuredGearTemplate] },
        fromFallback: true,
        error: ''
      }),
      listBuildTemplates: () => [],
      buildTemplateSummary: () => [],
      syncBuildTemplate: () => Promise.resolve({ payload: {}, fromFallback: true, error: '' })
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorAnalysis: () => Promise.resolve({ payload: {}, fromFallback: false, error: '' })
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const page = createPageInstance(pageDefinition)

  await page.loadTemplateLists()
  await flushPromises()

  assert.equal(page.data.summaryStatPanel.noteText, '手套装备数据不一致：装备名称和物品 ID 对不上，请重新选择或保存手套。')
  assert.doesNotMatch(page.data.summaryStatPanel.noteText, /Trivial|websim_unholy|item_249971|inconsistency/)
  assert.deepEqual(page.data.summaryStatPanel.secondaryRows.map((row) => row.percentText), ['不可用', '不可用', '不可用', '不可用'])
})

test('simc page does not leak raw simc crashes in blocked summary stat notes', async () => {
  const rawDiagnostic = [
    'sim_signal_handler: Segmentation fault! Iteration=0 Seed=-6016506965595101173 TargetHealth=0',
    'sim_signal_handler: Segmentation fault! Thread=1 Iteration=-1 Seed=15740702310078284102 (15740702310078284103) TargetHealth=0'
  ].join('\n\n')
  const structuredGearTemplate = {
    ...sampleGearTemplate,
    rawString: JSON.stringify({
      schemaRevision: 'websim-gear-enhancement-snapshot-v1',
      gearBySlot: { hands: { slot: 'hands', itemId: '249971', id: '249971', bonus_id: '13534' } },
      enhancementBySlot: {}
    }),
    metadata: { maxLevel: 90 }
  }
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/builds/builds-api.js': {
      fallbackBuildsHome: () => ({ classOptions: simcClassOptions }),
      requestBuildsHome: () => Promise.resolve({ payload: { classOptions: simcClassOptions }, fromFallback: true, error: '' })
    },
    '../pages/builds/websim-api.js': {
      requestWebsimGearStats: () => Promise.resolve({
        payload: {
          statStatus: 'blocked',
          blockers: [rawDiagnostic]
        },
        fromFallback: false,
        error: ''
      })
    },
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: (type) => Promise.resolve({
        payload: { templates: type === 'talent' ? [sampleTalentTemplate] : [structuredGearTemplate] },
        fromFallback: true,
        error: ''
      }),
      listBuildTemplates: () => [],
      buildTemplateSummary: () => [],
      syncBuildTemplate: () => Promise.resolve({ payload: {}, fromFallback: true, error: '' })
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorAnalysis: () => Promise.resolve({ payload: {}, fromFallback: false, error: '' })
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const page = createPageInstance(pageDefinition)

  await page.loadTemplateLists()
  await flushPromises()

  assert.match(page.data.summaryStatPanel.noteText, /SimC/)
  assert.doesNotMatch(page.data.summaryStatPanel.noteText, /sim_signal_handler|Segmentation fault|Seed=|TargetHealth/)
  assert.deepEqual(page.data.summaryStatPanel.secondaryRows.map((row) => row.percentText), ['不可用', '不可用', '不可用', '不可用'])
})

test('simc page localizes raw simc diagnostics in blocked validation reasons', async () => {
  const rawDiagnostic = "Trivial: Player 'websim_unholy' at slot hands has inconsistency between name 'item_249971' and 'relentless_riders_bonegrasps' for id 249971"
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/builds/builds-api.js': {
      fallbackBuildsHome: () => ({ classOptions: simcClassOptions }),
      requestBuildsHome: () => Promise.resolve({ payload: { classOptions: simcClassOptions }, fromFallback: true, error: '' })
    },
    '../pages/builds/websim-api.js': {
      requestWebsimGearStats: () => Promise.resolve({ payload: sampleGearStatSnapshot, fromFallback: false, error: '' })
    },
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: () => Promise.resolve({ payload: { templates: [] }, fromFallback: true, error: '' }),
      listBuildTemplates: () => [],
      buildTemplateSummary: () => [],
      syncBuildTemplate: () => Promise.resolve({ payload: {}, fromFallback: true, error: '' })
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorAnalysis: () => Promise.resolve({ payload: {}, fromFallback: false, error: '' }),
      requestSimulatorTasks: () => Promise.resolve({ payload: { tasks: [] }, fromFallback: false, error: '' })
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const page = createPageInstance(pageDefinition)

  page.applyAnalysisResult({
    agent: { status: 'blocked', canSubmitTask: false, validation: { errors: [] } },
    simulation: { error: rawDiagnostic },
    evidenceState: { blockers: [] }
  }, false, '')

  assert.deepEqual(page.data.blockedReasons, ['手套装备数据不一致：装备名称和物品 ID 对不上，请重新选择或保存手套。'])
  assert.doesNotMatch(page.data.blockedReasons.join(' '), /Trivial|websim_unholy|item_249971|inconsistency/)
})

test('simc page blocks confirm when gear stat snapshot is unavailable', async () => {
  let analysisCalls = 0
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: () => Promise.resolve({ payload: { templates: [] }, fromFallback: true, error: '' }),
      listBuildTemplates: () => [],
      buildTemplateSummary: () => []
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorAnalysis: () => {
        analysisCalls += 1
        return Promise.resolve({ payload: {}, fromFallback: false, error: '' })
      }
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const page = createPageInstance(pageDefinition)
  const blockedGearTemplate = {
    ...sampleGearTemplate,
    metadata: {
      statSnapshot: {
        statStatus: 'blocked',
        blockers: ['missing item id for gear slot: hands', 'bonus_id/gem_id/enchant_id']
      }
    }
  }
  page.setData({
    selectedClassKey: 'mage',
    selectedRaceKey: 'troll',
    selectedScenarioKey: 'single',
    selectedAnalysisType: 'baseline',
    selectedTalentTemplate: sampleTalentTemplate,
    selectedGearTemplate: blockedGearTemplate,
    canConfirm: true,
    summaryStatPanel: {
      statStatus: 'pending',
      noteText: '装备属性暂不可用：部分装备数据需要重新校验',
      primary: { label: '主属性', valueText: '不可用' },
      secondaryRows: []
    }
  })

  const result = await page.confirmTemplateSimulation()

  assert.equal(result, null)
  assert.equal(analysisCalls, 0)
  assert.equal(page.data.confirming, false)
  assert.equal(page.data.canSubmitTask, false)
  assert.equal(page.data.validatedCanSubmitTask, false)
  assert.deepEqual(page.data.blockedReasons, ['装备属性未通过校验：手套缺少物品 ID；缺少 bonus/宝石/附魔字段'])
})

test('simc page invalidates cached summary stats when the race changes', async () => {
  const requests = []
  let resolveStats
  const statsResponse = new Promise((resolve) => {
    resolveStats = resolve
  })
  const rawString = JSON.stringify({
    schemaRevision: 'websim-gear-enhancement-snapshot-v1',
    gearBySlot: { head: { slot: 'head', itemId: '1', id: '1', ilevel: 707, bonus_id: '12345' } },
    enhancementBySlot: {}
  })
  const cachedRequest = {
    classKey: 'mage',
    specKey: 'arcane',
    raceKey: 'troll',
    level: 90,
    scenarioKey: 'single',
    talents: sampleTalentTemplate.rawString,
    rawString,
    metadata: {}
  }
  const structuredGearTemplate = {
    ...sampleGearTemplate,
    rawString,
    metadata: {
      maxLevel: 90,
      statSnapshot: sampleGearStatSnapshot,
      statSnapshotSignature: JSON.stringify(cachedRequest)
    }
  }
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/builds/builds-api.js': {
      fallbackBuildsHome: () => ({ classOptions: simcClassOptions }),
      requestBuildsHome: () => Promise.resolve({ payload: { classOptions: simcClassOptions }, fromFallback: true, error: '' })
    },
    '../pages/builds/websim-api.js': {
      requestWebsimGearStats: (request) => {
        requests.push(request)
        return statsResponse
      }
    },
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: (type) => Promise.resolve({
        payload: { templates: type === 'talent' ? [sampleTalentTemplate] : [structuredGearTemplate] },
        fromFallback: true,
        error: ''
      }),
      listBuildTemplates: () => [],
      buildTemplateSummary: () => [],
      syncBuildTemplate: () => Promise.resolve({ payload: {}, fromFallback: true, error: '' })
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorAnalysis: () => Promise.resolve({ payload: {}, fromFallback: false, error: '' })
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const page = createPageInstance(pageDefinition)
  await page.loadTemplateLists()
  await flushPromises()

  assert.equal(requests.length, 0)
  assert.equal(page.data.summaryStatPanel.secondaryRows[0].percentText, '28.6%')

  page.selectRace({ detail: { value: 0 } })
  await flushPromises()

  assert.equal(requests.length, 1)
  assert.equal(requests[0].raceKey, 'human')
  assert.deepEqual(page.data.summaryStatPanel.secondaryRows.map((row) => row.percentText), ['计算中', '计算中', '计算中', '计算中'])
  assert.equal(((page.buildTemplatePayload(true, false).templateContext.gear.metadata || {}).statSnapshot), undefined)

  resolveStats({ payload: { ...sampleGearStatSnapshot, blockers: [] }, fromFallback: false, error: '' })
  await flushPromises()
})

test('simc page reuses the same template payload for confirm and final submit', async () => {
  const requests = []
  const gearSnapshot = {
    schemaRevision: 'websim-gear-enhancement-snapshot-v1',
    gearBySlot: { head: { slot: 'head', itemId: '250001', simcReady: true } },
    enhancementBySlot: {}
  }
  const gearTemplateWithSnapshot = {
    ...sampleGearTemplate,
    rawString: 'gear snapshot stored in metadata',
    metadata: { gearSnapshot, statSnapshot: sampleGearStatSnapshot }
  }
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/builds/builds-api.js': {
      fallbackBuildsHome: () => ({ classOptions: simcClassOptions }),
      requestBuildsHome: () => Promise.resolve({ payload: { classOptions: simcClassOptions }, fromFallback: true, error: '' })
    },
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: (type) => Promise.resolve({
        payload: { templates: type === 'talent' ? [sampleTalentTemplate] : [gearTemplateWithSnapshot] },
        fromFallback: true,
        error: ''
      }),
      listBuildTemplates: () => [],
      buildTemplateSummary: () => []
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorAnalysis: (request, options) => {
        requests.push({ request, options })
        return Promise.resolve({
          payload: {
            mode: 'simcraft_template',
            status: request.saveTask ? 'queued' : 'ready',
            taskId: request.saveTask ? 'task-1' : '',
            request,
            agent: request.saveTask
              ? { status: 'simc_queued', canSubmitTask: false, validation: { passed: true, errors: [] } }
              : { status: 'template_ready', canSubmitTask: true, validation: { passed: true, errors: [] } },
            simulation: { ran: false, error: '', metrics: {} },
            recommendations: ['模板组合已确认，可以提交执行 SimC。']
          },
          fromFallback: false,
          error: ''
        })
      }
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const originalWx = global.wx
  global.wx = { showToast() {} }
  let page
  try {
    page = createPageInstance(pageDefinition)
    await page.loadTemplateLists()
    await flushPromises()
    const raceIndex = page.data.raceOptions.findIndex((item) => item.key === 'void_elf')
    assert.ok(raceIndex >= 0)
    page.selectRace({ detail: { value: raceIndex } })
    page.selectScenario({ currentTarget: { dataset: { key: 'mythic_plus' } } })
    await page.confirmTemplateSimulation()
    await flushPromises()
    await page.submitConfirmedTask()
    await flushPromises()
  } finally {
    global.wx = originalWx
  }

  assert.equal(requests.length, 2)
  assert.equal(requests[0].request.mode, 'simcraft_template')
  assert.equal(requests[0].request.confirmOnly, true)
  assert.equal(requests[0].request.saveTask, false)
  assert.equal(requests[0].request.classKey, 'mage')
  assert.equal(requests[0].request.raceKey, 'void_elf')
  assert.equal(requests[0].request.scenarioKey, 'mythic_plus')
  assert.equal(requests[0].request.analysisType, 'baseline')
  assert.deepEqual(requests[0].request.temporaryBuffs, {})
  assert.equal(requests[0].request.templateContext.talent.id, 'talent-1')
  assert.equal(requests[0].request.templateContext.gear.id, 'gear-1')
  assert.deepEqual(requests[0].request.templateContext.gear.metadata, { gearSnapshot, statSnapshot: sampleGearStatSnapshot })
  assert.equal(requests[1].request.confirmOnly, false)
  assert.equal(requests[1].request.saveTask, true)
  assert.deepEqual(requests[1].request.templateContext, requests[0].request.templateContext)
  assert.equal(requests[1].request.classKey, requests[0].request.classKey)
  assert.equal(requests[1].request.raceKey, requests[0].request.raceKey)
  assert.equal(requests[1].request.scenarioKey, requests[0].request.scenarioKey)
  assert.deepEqual(requests[1].request.temporaryBuffs, requests[0].request.temporaryBuffs)
  assert.deepEqual(requests[1].options, { auth: true, allowInsecureGuestRequest: true })
  assert.equal(page.data.taskSubmitted, true)
  assert.equal(page.data.submittedTaskId, 'task-1')
  assert.equal(page.data.canSubmitTask, false)
  assert.equal((page.data.latestAnalysis && page.data.latestAnalysis.agent) || null, null)
  assert.equal(page.data.resultSummary, '')
})

test('simc page sends selected temporary combat buffs with confirm and submit payloads', async () => {
  const requests = []
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/builds/builds-api.js': {
      fallbackBuildsHome: () => ({ classOptions: simcClassOptions }),
      requestBuildsHome: () => Promise.resolve({ payload: { classOptions: simcClassOptions }, fromFallback: true, error: '' })
    },
    '../pages/builds/websim-api.js': {
      requestWebsimGearStats: () => Promise.resolve({ payload: sampleGearStatSnapshot, fromFallback: false, error: '' })
    },
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: (type) => Promise.resolve({
        payload: { templates: type === 'talent' ? [sampleTalentTemplate] : [sampleGearTemplateWithStatSnapshot] },
        fromFallback: false,
        error: ''
      }),
      listBuildTemplates: () => [],
      syncBuildTemplate: () => Promise.resolve({ payload: {}, fromFallback: false, error: '' })
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorAnalysis: (request, options) => {
        requests.push({ request, options })
        return Promise.resolve({
          payload: {
            taskId: request.saveTask ? 'task-temp-buffs' : '',
            agent: { status: 'template_ready', canSubmitTask: true, validation: { passed: true, errors: [] } },
            simcReport: {
              schemaRevision: 'simc-report-v2',
              state: 'ready',
              summary: 'Template payload validated; submit to run SimC.',
              result: { ran: false, hasDps: false, dps: '', dpsDisplay: '' }
            }
          },
          fromFallback: false,
          error: ''
        })
      }
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const originalWx = global.wx
  global.wx = { showToast() {} }
  try {
    const page = createPageInstance(pageDefinition)
    await page.loadTemplateLists()
    await flushPromises()
    page.toggleTemporaryBuff({ currentTarget: { dataset: { key: 'bloodlust' } } })
    page.toggleTemporaryBuff({ currentTarget: { dataset: { key: 'combatPotion' } } })
    await page.confirmTemplateSimulation()
    await flushPromises()
    await page.submitConfirmedTask()
    await flushPromises()
  } finally {
    global.wx = originalWx
  }

  assert.equal(requests.length, 2)
  assert.deepEqual(requests[0].request.temporaryBuffs, { bloodlust: true, combatPotion: true })
  assert.deepEqual(requests[1].request.temporaryBuffs, { bloodlust: true, combatPotion: true })
})

test('simc page surfaces confirm request failures without leaving loading stuck', async () => {
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/builds/builds-api.js': {
      fallbackBuildsHome: () => ({ classOptions: simcClassOptions }),
      requestBuildsHome: () => Promise.resolve({ payload: { classOptions: simcClassOptions }, fromFallback: true, error: '' })
    },
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: (type) => Promise.resolve({
        payload: { templates: type === 'talent' ? [sampleTalentTemplate] : [sampleGearTemplateWithStatSnapshot] },
        fromFallback: true,
        error: ''
      }),
      listBuildTemplates: () => [],
      buildTemplateSummary: () => []
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorAnalysis: () => Promise.reject(new Error('confirm timeout'))
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const page = createPageInstance(pageDefinition)
  await page.loadTemplateLists()
  await flushPromises()

  const result = await page.confirmTemplateSimulation()

  assert.equal(result, null)
  assert.equal(page.data.confirming, false)
  assert.equal(page.data.canSubmitTask, false)
  assert.equal(page.data.taskSubmitted, false)
  assert.match(page.data.requestError, /confirm timeout/)
  assert.deepEqual(page.data.blockedReasons, ['confirm timeout'])
})

test('simc page surfaces submit request failures while keeping retry available', async () => {
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/builds/builds-api.js': {
      fallbackBuildsHome: () => ({ classOptions: simcClassOptions }),
      requestBuildsHome: () => Promise.resolve({ payload: { classOptions: simcClassOptions }, fromFallback: true, error: '' })
    },
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: (type) => Promise.resolve({
        payload: { templates: type === 'talent' ? [sampleTalentTemplate] : [sampleGearTemplateWithStatSnapshot] },
        fromFallback: true,
        error: ''
      }),
      listBuildTemplates: () => [],
      buildTemplateSummary: () => []
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorAnalysis: () => Promise.reject(new Error('submit timeout'))
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const originalWx = global.wx
  global.wx = { showToast() {} }
  try {
    const page = createPageInstance(pageDefinition)
    await page.loadTemplateLists()
    await flushPromises()
    const confirmedPayload = page.buildTemplatePayload(true, false)
    page.setData({
      canSubmitTask: true,
      confirmedPayload
    })

    const result = await page.submitConfirmedTask()

    assert.equal(result, null)
    assert.equal(page.data.submittingTask, false)
    assert.equal(page.data.canSubmitTask, true)
    assert.equal(page.data.taskSubmitted, false)
    assert.equal(page.data.submittedTaskId, '')
    assert.match(page.data.requestError, /submit timeout/)
    assert.deepEqual(page.data.blockedReasons, ['submit timeout'])
  } finally {
    global.wx = originalWx
  }
})

test('simc page blocks submit when two active template tasks already exist', async () => {
  let analysisCalls = 0
  const activeTasks = [
    { taskId: 'task-active-1', mode: 'simcraft_template', status: 'queued' },
    { taskId: 'task-active-2', mode: 'simcraft_template', status: 'running' },
    { taskId: 'task-done', mode: 'simcraft_template', status: 'completed' }
  ]
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/builds/builds-api.js': {
      fallbackBuildsHome: () => ({ classOptions: simcClassOptions }),
      requestBuildsHome: () => Promise.resolve({ payload: { classOptions: simcClassOptions }, fromFallback: true, error: '' })
    },
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: () => Promise.resolve({ payload: { templates: [] }, fromFallback: true, error: '' }),
      listBuildTemplates: () => [],
      buildTemplateSummary: () => []
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorTasks: () => Promise.resolve({ payload: { tasks: activeTasks }, fromFallback: false, error: '' }),
      requestSimulatorAnalysis: () => {
        analysisCalls += 1
        return Promise.resolve({ payload: {}, fromFallback: false, error: '' })
      }
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const page = createPageInstance(pageDefinition)
  page.setData({
    canSubmitTask: true,
    confirmedPayload: {
      mode: 'simcraft_template',
      confirmOnly: true,
      saveTask: false,
      classKey: 'mage',
      raceKey: 'troll',
      scenarioKey: 'single',
      analysisType: 'baseline',
      templateContext: { talent: sampleTalentTemplate, gear: sampleGearTemplate }
    }
  })

  await page.refreshActiveTaskGate()
  const result = await page.submitConfirmedTask()

  assert.equal(result, null)
  assert.equal(analysisCalls, 0)
  assert.equal(page.data.activeTaskCount, 2)
  assert.equal(page.data.activeTaskLimitReached, true)
  assert.equal(page.data.canSubmitTask, false)
  assert.match(page.data.activeTaskLimitMessage, /2/)
})

test('simc page keeps submit blocked when backend reports active task limit', async () => {
  let analysisCalls = 0
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/builds/builds-api.js': {
      fallbackBuildsHome: () => ({ classOptions: simcClassOptions }),
      requestBuildsHome: () => Promise.resolve({ payload: { classOptions: simcClassOptions }, fromFallback: true, error: '' })
    },
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: () => Promise.resolve({ payload: { templates: [] }, fromFallback: true, error: '' }),
      listBuildTemplates: () => [],
      buildTemplateSummary: () => []
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorTasks: () => Promise.resolve({ payload: { tasks: [] }, fromFallback: false, error: '' }),
      requestSimulatorAnalysis: () => {
        analysisCalls += 1
        return Promise.resolve({
          payload: {
            mode: 'simcraft_template',
            status: 'blocked',
            taskLock: {
              active: true,
              reason: 'active_simc_task_limit',
              activeCount: 2,
              limit: 2
            },
            agent: {
              status: 'task_limit_reached',
              canSubmitTask: false,
              validation: { passed: false, errors: ['已有 2 个模拟任务正在排队或运行，请等待前面的任务完成后再提交。'] }
            },
            simulation: {
              ran: false,
              error: '已有 2 个模拟任务正在排队或运行，请等待前面的任务完成后再提交。',
              metrics: {}
            },
            recommendations: ['已有 2 个模拟任务正在排队或运行，请等待前面的任务完成后再提交。']
          },
          fromFallback: false,
          error: ''
        })
      }
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const originalWx = global.wx
  global.wx = { showToast() {} }
  try {
    const page = createPageInstance(pageDefinition)
    page.setData({
      canSubmitTask: true,
      confirmedPayload: {
        mode: 'simcraft_template',
        confirmOnly: true,
        saveTask: false,
        classKey: 'mage',
        raceKey: 'troll',
        scenarioKey: 'single',
        analysisType: 'baseline',
        templateContext: { talent: sampleTalentTemplate, gear: sampleGearTemplate }
      }
    })

    const result = await page.submitConfirmedTask()

    assert.equal(result.status, 'blocked')
    assert.equal(analysisCalls, 1)
    assert.equal(page.data.activeTaskLimitReached, true)
    assert.equal(page.data.activeTaskCount, 2)
    assert.equal(page.data.canSubmitTask, false)
    assert.match(page.data.activeTaskLimitMessage, /2/)
    assert.deepEqual(page.data.blockedReasons, ['已有 2 个模拟任务正在排队或运行，请等待前面的任务完成后再提交。'])
  } finally {
    global.wx = originalWx
  }
})

test('simc page exposes deterministic blocked reasons from template validation', () => {
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: () => Promise.resolve({ payload: { templates: [] }, fromFallback: true, error: '' }),
      listBuildTemplates: () => [],
      buildTemplateSummary: () => []
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorAnalysis: () => Promise.resolve({ payload: {}, fromFallback: false, error: '' })
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const page = createPageInstance(pageDefinition)
  page.applyAnalysisResult({
    agent: { status: 'template_blocked', validation: { errors: ['template class/spec mismatch', 'missing gear slots: off_hand'] } },
    simulation: { error: 'template class/spec mismatch; missing gear slots: off_hand' },
    recommendations: []
  }, false, '')

  assert.deepEqual(page.data.blockedReasons, ['template class/spec mismatch', '缺少可执行装备槽位：副手'])
  assert.equal(page.data.canSubmitTask, false)
})

test('simc page surfaces confirm preview report finding', () => {
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: () => Promise.resolve({ payload: { templates: [] }, fromFallback: true, error: '' }),
      listBuildTemplates: () => [],
      buildTemplateSummary: () => []
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorAnalysis: () => Promise.resolve({ payload: {}, fromFallback: false, error: '' })
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const wxml = fs.readFileSync('pages/simulator/simc.wxml', 'utf8')
  const page = createPageInstance(pageDefinition)
  page.applyAnalysisResult({
    agent: { status: 'template_ready', canSubmitTask: true, validation: { passed: true, errors: [] } },
    report: {
      topFindings: [{ text: 'Template payload validated; confirmOnly did not execute SimC.' }]
    },
    recommendations: ['Generic ready message.']
  }, false, '')

  assert.equal(page.data.resultSummary, '当前天赋、装备和场景已通过校验，可以提交任务开始运行 SimC。')
  assert.match(wxml, /resultSummary/)
})

test('simc page stores only compact analysis state after validation', () => {
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: () => Promise.resolve({ payload: { templates: [] }, fromFallback: true, error: '' }),
      listBuildTemplates: () => [],
      buildTemplateSummary: () => []
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorAnalysis: () => Promise.resolve({ payload: {}, fromFallback: false, error: '' })
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const wxml = fs.readFileSync('pages/simulator/simc.wxml', 'utf8')
  const page = createPageInstance(pageDefinition)
  page.applyAnalysisResult({
    agent: { status: 'template_ready', canSubmitTask: true, validation: { passed: true, errors: [] } },
    request: {
      buildContext: {
        details: {
          gear: { simcItems: Array.from({ length: 16 }, (_, index) => `slot_${index}=item,id=${index}`) },
          talents: { importCode: 'websim:very-large-talent-code' }
        }
      }
    },
    profile: 'head=item,id=1\n'.repeat(800),
    simcReport: {
      schemaRevision: 'simc-report-v2',
      state: 'ready',
      summary: 'Template payload validated; submit to run SimC.',
      preparation: {
        schemaRevision: 'simc-preparation-v1',
        summary: 'SimC buffs: optimal_raid=0; self-class raid buff enabled: Skyfury; selected temporary combat buffs: Bloodlust/Heroism, Combat potion, Weapon oil or sharpening stone.',
        evidenceState: 'partial',
        items: [
          {
            key: 'optimal_raid',
            category: 'raid_buff_baseline',
            label: 'Full raid buff package',
            state: 'disabled',
            summary: 'SimulationCraft optimal_raid is disabled; only backend-verified self-class buffs may be added.',
            evidenceState: 'verified'
          },
          {
            key: 'skyfury',
            category: 'self_class_raid_buff',
            label: 'Skyfury',
            state: 'enabled',
            summary: "Only the player's own class raid buff is enabled: Skyfury.",
            evidenceState: 'verified'
          },
          {
            key: 'temporary_combat_buffs',
            category: 'temporary_combat_buffs',
            label: 'Temporary combat buffs',
            state: 'enabled',
            summary: 'Bloodlust/Heroism, Combat potion, Weapon oil or sharpening stone',
            evidenceState: 'partial'
          }
        ]
      },
      result: { ran: false, hasDps: false, dps: '', dpsDisplay: '' }
    },
    report: {
      topFindings: [{ text: 'Template payload validated; confirmOnly did not execute SimC.' }]
    }
  }, false, '')

  assert.deepEqual(page.data.latestAnalysis, {
    agent: {
      status: 'template_ready',
      statusText: '组合校验通过'
    },
    simcReport: {
      schemaRevision: 'simc-report-v2',
      state: 'ready',
      result: { ran: false, hasDps: false, dps: '', dpsDisplay: '' }
    },
    preparation: {
      hasRows: true,
      rows: [
        { key: 'skyfury', label: '团队增益', valueText: '天怒', stateText: '已开启' },
        { key: 'temporary_combat_buffs', label: '临时增益', valueText: '嗜血 / 英勇、爆发药水、武器涂油', stateText: '已选择' }
      ]
    }
  })
  assert.equal(page.data.latestAnalysis.request, undefined)
  assert.equal(page.data.latestAnalysis.profile, undefined)
  assert.equal(page.data.canSubmitTask, true)
  assert.equal(page.data.resultSummary, '当前天赋、装备和场景已通过校验，可以提交任务开始运行 SimC。')
  assert.doesNotMatch(wxml, /latestAnalysis\.simcReport\.preparation\.summary/)
  assert.doesNotMatch(wxml, /latestAnalysis\.simcReport\.preparation\.evidenceState/)
  assert.doesNotMatch(wxml, /latestAnalysis\.simcReport\.preparation\.items/)
  assert.doesNotMatch(wxml, /模拟增益/)
  assert.match(wxml, /latestAnalysis\.preparation\.rows/)
  assert.match(wxml, /statusText/)
  assert.match(wxml, /战斗增益/)
})

test('smart analysis tab only keeps the chickenbro coach entry', () => {
  const app = JSON.parse(fs.readFileSync('app.json', 'utf8'))
  const js = fs.readFileSync('pages/simulator/simulator.js', 'utf8')
  const wxml = fs.readFileSync('pages/simulator/simulator.wxml', 'utf8')
  const css = fs.readFileSync('pages/simulator/simulator.wxss', 'utf8')
  const api = fs.readFileSync('pages/simulator/simulator-api.js', 'utf8')
  const chickenbroJs = fs.readFileSync('pages/simulator/chickenbro.js', 'utf8')
  const chickenbroWxml = fs.readFileSync('pages/simulator/chickenbro.wxml', 'utf8')
  const chickenbroCss = fs.readFileSync('pages/simulator/chickenbro.wxss', 'utf8')

  assert.ok(app.pages.includes('pages/simulator/simc'))
  assert.ok(!app.pages.includes('pages/simulator/wcl'))
  assert.ok(app.pages.includes('pages/simulator/chickenbro'))
  assert.ok(app.pages.includes('pages/simulator/tasks'))
  assert.ok(app.pages.includes('pages/simulator/task-detail'))
  assert.match(wxml, /<view class="hero simulator-hero">/)
  assert.doesNotMatch(wxml, /class="metrics"/)
  assert.doesNotMatch(wxml, /metric-card/)
  assert.match(wxml, /analysis-modules/)
  assert.match(wxml, /wx:for="\{\{analysisModules\}\}"/)
  assert.doesNotMatch(wxml, /scroll-into-view="\{\{scrollTarget\}\}"/)
  assert.doesNotMatch(wxml, /id="task-section"/)
  assert.doesNotMatch(wxml, /任务列表/)
  assert.doesNotMatch(wxml, /data-task-id="\{\{item\.taskId\}\}"/)
  assert.doesNotMatch(wxml, /bindtap="openTaskDetail"/)
  assert.match(js, /openAnalysisModule\(event\)/)
  assert.doesNotMatch(js, /openTaskDetail\(event\)/)
  assert.doesNotMatch(js, /loadSimulatorTasks/)
  assert.doesNotMatch(js, /scrollTarget/)
  assert.doesNotMatch(js, /tasks:\s*\[\]/)
  assert.doesNotMatch(js, /taskId:\s*task\.taskId/)
  assert.doesNotMatch(js, /wx\.navigateTo\(\{[\s\S]*\/pages\/simulator\/simc/)
  assert.doesNotMatch(js, /\/pages\/simulator\/wcl/)
  assert.match(js, /wx\.navigateTo\(\{[\s\S]*\/pages\/simulator\/chickenbro/)
  assert.doesNotMatch(js, /\/pages\/simulator\/task-detail\?id=/)
  assert.match(api, /navTitle:\s*'智能分析'/)
  assert.match(api, /analysisModules:\s*\[/)
  assert.match(api, /homeWithoutLegacyMetrics/)
  assert.doesNotMatch(api, /metrics:\s*undefined/)
  assert.doesNotMatch(api, /title:\s*'模拟 SimC'/)
  assert.doesNotMatch(api, /title:\s*'分析 WCL'/)
  assert.match(api, /key:\s*'chickenbro'/)
  assert.match(api, /title:\s*'炸鸡队长'/)
  assert.doesNotMatch(api, /title:\s*'任务列表'/)
  assert.match(css, /\.analysis-modules/)
  assert.match(css, /\.analysis-module-card/)
  assert.match(css, /\.module-chickenbro/)
  assert.match(chickenbroJs, /requestChickenbroMessage/)
  assert.doesNotMatch(chickenbroJs, /requestSimulatorAnalysis/)
  assert.match(chickenbroWxml, /chatMessages/)
  assert.match(chickenbroWxml, /wx:key="messageId"/)
  assert.match(chickenbroWxml, /session && session\.sessionId/)
  assert.match(chickenbroWxml, /job \? job\.status : ''/)
  assert.match(chickenbroWxml, /assistantPayload\.priorityActions/)
  assert.match(chickenbroWxml, /assistantPayload\.evidenceRefs && assistantPayload\.evidenceRefs\.length/)
  assert.match(chickenbroWxml, /assistantPayload\.limitations && assistantPayload\.limitations\.length/)
  assert.match(chickenbroWxml, /job\.status/)
  assert.match(chickenbroCss, /\.chickenbro-hero/)
})

test('simulator task list has a dedicated page and opens task details', () => {
  const app = JSON.parse(fs.readFileSync('app.json', 'utf8'))
  const js = fs.readFileSync('pages/simulator/tasks.js', 'utf8')
  const wxml = fs.readFileSync('pages/simulator/tasks.wxml', 'utf8')
  const css = fs.readFileSync('pages/simulator/tasks.wxss', 'utf8')

  assert.ok(app.pages.includes('pages/simulator/tasks'))
  assert.match(js, /requestSimulatorTasks/)
  assert.match(js, /loadSimulatorTasks/)
  assert.match(js, /openTaskDetail\(event\)/)
  assert.match(js, /\/pages\/simulator\/task-detail\?id=/)
  assert.match(wxml, /wx:for="\{\{tasks\}\}"/)
  assert.match(wxml, /data-task-id="\{\{item\.taskId\}\}"/)
  assert.match(wxml, /bindtap="openTaskDetail"/)
  assert.match(wxml, /任务列表/)
  assert.match(css, /\.task-list-page/)
  assert.match(css, /\.task-list-card/)
})

test('simulator task list localizes SimC task cards with tags and finish time', () => {
  const pageDefinition = loadPageModule('../pages/simulator/tasks.js', {
    '../pages/simulator/simulator-api.js': {
      requestSimulatorTasks: () => Promise.resolve({ payload: { tasks: [] }, fromFallback: false, error: '' })
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const wxml = fs.readFileSync('pages/simulator/tasks.wxml', 'utf8')
  const css = fs.readFileSync('pages/simulator/tasks.wxss', 'utf8')

  const completed = pageDefinition.normalizeTask({
    taskId: 'task-shaman-completed',
    mode: 'simcraft_template',
    status: 'completed',
    createdAt: '2026-06-27T04:20:00+00:00',
    updatedAt: '2026-06-27T04:21:17+00:00',
    simcReportSummary: {
      state: 'completed',
      title: 'Elemental Shaman SimC',
      summary: 'SimC completed with 73680.202 DPS.',
      statusText: 'completed',
      dpsDisplay: '73680.202 DPS',
      scenario: { key: 'mythic_plus', label: '大秘境基准', targets: 5 },
      build: {
        raceName: '巨魔',
        className: '萨满祭祀',
        specName: '元素',
        heroLabel: '风暴使者'
      },
      preparation: {
        summary: 'SimC buffs: optimal_raid=0; self-class raid buff enabled: Skyfury.'
      },
      timing: { finishedAt: '2026-06-27T04:21:17+00:00' },
      updatedAt: '2026-06-27T04:21:17+00:00'
    }
  })
  const completedSameInstant = pageDefinition.normalizeTask({
    taskId: 'task-shaman-completed-local',
    mode: 'simcraft_template',
    status: 'completed',
    updatedAt: '2026-06-27T12:21:17+08:00',
    simcReportSummary: {
      state: 'completed',
      scenario: { key: 'single', targets: 1 },
      build: { className: '萨满祭祀', specName: '元素' },
      timing: { finishedAt: '2026-06-27T12:21:17+08:00' }
    }
  })
  const failed = pageDefinition.normalizeTask({
    taskId: 'task-shaman-failed',
    mode: 'simcraft_template',
    status: 'failed',
    updatedAt: '2026-06-27T04:22:17+00:00',
    simcReportSummary: {
      state: 'failed',
      summary: "Command '['/opt/wow-simc/current/simc', '-']' timed out after 45 seconds",
      scenario: { key: 'single', targets: 1 },
      build: { raceName: '兽人', className: '萨满祭祀', specName: '元素', heroKey: 'stormbringer' },
      preparation: {
        summary: 'SimC buffs: optimal_raid=0; self-class raid buff enabled: Skyfury; selected temporary combat buffs: Bloodlust/Heroism, Combat potion, Weapon oil or sharpening stone.'
      },
      timing: { finishedAt: '2026-06-27T04:22:17+00:00' }
    }
  })
  const running = pageDefinition.normalizeTask({
    taskId: 'task-shaman-running',
    mode: 'simcraft_template',
    status: 'running',
    updatedAt: '2026-06-27T04:23:17+00:00',
    simcReportSummary: {
      state: 'running',
      summary: 'SimC task is running; results will appear in the task list.',
      scenario: { key: 'mythic_plus', targets: 5 },
      build: { className: '萨满祭祀', specName: '元素' },
      timing: {}
    }
  })
  const aoe = pageDefinition.normalizeTask({
    taskId: 'task-shaman-aoe',
    mode: 'simcraft_template',
    status: 'running',
    updatedAt: '2026-06-27T04:24:17+00:00',
    simcReportSummary: {
      state: 'running',
      summary: 'SimC task is running; results will appear in the task list.',
      scenario: { key: 'aoe_5', targets: 5 },
      build: { className: '萨满祭祀', specName: '元素' },
      timing: {}
    }
  })

  assert.equal(completed.title, `元素萨满祭祀_${expectedLocalMinute('2026-06-27T04:21:17+00:00')}`)
  assert.equal(completedSameInstant.title, completed.title)
  assert.equal(completedSameInstant.completionTimeText, completed.completionTimeText)
  assert.equal(completed.statusText, '已完成')
  assert.equal(completed.statusClass, 'status-completed')
  assert.equal(completed.desc, '')
  assert.equal(completed.preparationSummary, undefined)
  assert.equal(completed.dpsDisplay, undefined)
  assert.deepEqual(completed.tags.map((item) => item.text), [
    '巨魔',
    '萨满祭祀',
    '元素',
    '风暴使者',
    '近似大秘境'
  ])
  assert.ok(completed.tags.every((item) => !item.text.includes('：')))
  assert.equal(completed.completionTimeText, `完成时间：${expectedLocalMinute('2026-06-27T04:21:17+00:00')}`)

  assert.equal(failed.statusText, '失败')
  assert.equal(failed.statusClass, 'status-failed')
  assert.equal(failed.desc, 'SimC 执行超时：当前组合已经入队并开始运行，但本次模拟超过 45 秒未完成。可以稍后重试，或等待前面的任务完成后再提交。')
  assert.equal(failed.preparationSummary, undefined)
  assert.ok(failed.tags.some((item) => item.text === '单体'))
  assert.equal(failed.completionTimeText, `完成时间：${expectedLocalMinute('2026-06-27T04:22:17+00:00')}`)

  assert.equal(running.statusText, '进行中')
  assert.equal(running.statusClass, 'status-running')
  assert.deepEqual(running.tags.map((item) => item.text), [
    '萨满祭祀',
    '元素',
    '近似大秘境'
  ])
  assert.ok(running.tags.every((item) => item.text !== '待补'))
  assert.equal(running.completionTimeText, '完成时间：未完成')
  assert.deepEqual(aoe.tags.map((item) => item.text), [
    '萨满祭祀',
    '元素',
    'AOE5目标'
  ])

  assert.match(wxml, /item\.statusText/)
  assert.match(wxml, /item\.statusClass/)
  assert.match(wxml, /item\.tags/)
  assert.doesNotMatch(wxml, /item\.preparationSummary/)
  assert.match(wxml, /item\.completionTimeText/)
  assert.doesNotMatch(wxml, /dpsDisplay/)
  assert.doesNotMatch(wxml, /大秘境基准/)
  assert.doesNotMatch(wxml, /task-preparation/)
  assert.match(css, /\.status-completed/)
  assert.match(css, /\.status-failed/)
  assert.match(css, /\.status-running/)
  assert.match(css, /\.task-tag/)
  assert.match(css, /\.task-finished-at/)
})

test('chickenbro page submits messages through independent chat API', async () => {
  let capturedRequest = null
  const pageDefinition = loadPageModule('../pages/simulator/chickenbro.js', {
    '../pages/simulator/simulator-api.js': {
      requestChickenbroMessage: (request) => {
        capturedRequest = request
        return Promise.resolve({
          payload: {
            mode: 'chickenbro',
            session: { sessionId: 'session-1' },
            job: { jobId: 'job-1', status: 'succeeded' },
            userMessage: { messageId: 'message-user-1', role: 'user', content: '奥法强韧怎么打？' },
            assistantMessage: {
              messageId: 'message-assistant-1',
              role: 'assistant',
              content: '先围绕大波次规划爆发。',
              payload: {
                answerSource: 'codex',
                confidence: 'medium',
                priorityActions: [
                  { title: '确认大波次爆发窗口', evidenceRefs: ['profile.summary'] }
                ],
                evidenceRefs: ['profile.summary'],
                limitations: ['partial_profiles_background_only']
              }
            }
          },
          fromFallback: false,
          error: ''
        })
      }
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const originalWx = global.wx
  global.wx = { showToast() {} }
  try {
    const page = createPageInstance(pageDefinition)
    page.setData({
      chickenbroPrompt: '奥法强韧怎么打？',
      contextDraft: 'class=mage spec=arcane scenario=mplus_fortified'
    })
    page.submitChickenbroMessage()
    await flushPromises()
    await flushPromises()

    assert.equal(capturedRequest.message, '奥法强韧怎么打？')
    assert.equal(capturedRequest.context.classKey, 'mage')
    assert.equal(capturedRequest.context.specKey, 'arcane')
    assert.equal(capturedRequest.context.scenarioKey, 'mplus_fortified')
    assert.equal(page.data.session.sessionId, 'session-1')
    assert.equal(page.data.job.status, 'succeeded')
    assert.equal(page.data.chatMessages.length, 2)
    assert.equal(page.data.assistantPayload.priorityActions[0].title, '确认大波次爆发窗口')
    assert.equal(page.data.assistantPayload.evidenceRefs[0], 'profile.summary')
    assert.equal(page.data.assistantPayload.limitations[0], 'partial_profiles_background_only')
  } finally {
    global.wx = originalWx
  }
})

test('chickenbro page surfaces request failures without leaving loading stuck', async () => {
  const pageDefinition = loadPageModule('../pages/simulator/chickenbro.js', {
    '../pages/simulator/simulator-api.js': {
      requestChickenbroMessage: () => Promise.reject(new Error('network timeout'))
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const originalWx = global.wx
  global.wx = { showToast() {} }
  try {
    const page = createPageInstance(pageDefinition)
    page.setData({
      chickenbroPrompt: '奥法强韧怎么打？',
      contextDraft: 'class=mage spec=arcane scenario=mplus_fortified',
      session: { sessionId: 'session-before-failure' },
      job: { jobId: 'old-job', status: 'succeeded' },
      chatMessages: [{ messageId: 'old-message', role: 'assistant', content: '旧回复' }],
      assistantPayload: {
        answerSource: 'old',
        confidence: 'high',
        priorityActions: [{ title: '旧行动' }],
        evidenceRefs: ['old.ref'],
        limitations: ['old-limit']
      }
    })
    page.submitChickenbroMessage()
    await flushPromises()
    await flushPromises()

    assert.equal(page.data.loading, false)
    assert.equal(page.data.fromFallback, true)
    assert.equal(page.data.session.sessionId, 'session-before-failure')
    assert.equal(page.data.job, null)
    assert.deepEqual(page.data.chatMessages, [])
    assert.deepEqual(page.data.assistantPayload.priorityActions, [])
    assert.deepEqual(page.data.assistantPayload.evidenceRefs, [])
    assert.deepEqual(page.data.assistantPayload.limitations, [])
    assert.match(page.data.requestError, /network timeout/)
  } finally {
    global.wx = originalWx
  }
})

test('simulator task detail page renders saved task analysis', () => {
  const js = fs.readFileSync('pages/simulator/task-detail.js', 'utf8')
  const wxml = fs.readFileSync('pages/simulator/task-detail.wxml', 'utf8')
  const css = fs.readFileSync('pages/simulator/task-detail.wxss', 'utf8')
  const api = fs.readFileSync('pages/simulator/simulator-api.js', 'utf8')

  assert.match(js, /requestSimulatorTaskDetail/)
  assert.match(js, /loadTaskDetail\(options\.id/)
  assert.match(js, /normalizeTaskDetail\(task\)/)
  assert.match(wxml, /任务详情/)
  assert.doesNotMatch(wxml, /玩家问题/)
  assert.doesNotMatch(wxml, /构筑上下文/)
  assert.doesNotMatch(wxml, /报告解释/)
  assert.doesNotMatch(wxml, /Evidence/)
  assert.doesNotMatch(wxml, /下一步/)
  assert.doesNotMatch(wxml, /AI/)
  assert.doesNotMatch(wxml, /真实大秘境对标/)
  assert.doesNotMatch(wxml, /执行阶段/)
  assert.doesNotMatch(wxml, /Pipeline/)
  assert.doesNotMatch(wxml, /生成的 SimC 模板/)
  assert.doesNotMatch(wxml, /SimC 执行摘要/)
  assert.doesNotMatch(wxml, /detail\.recommendations/)
  assert.doesNotMatch(wxml, /detail\.mythicPlusReference/)
  assert.doesNotMatch(wxml, /detail\.mythicPlusReferenceText/)
  assert.doesNotMatch(wxml, /detail\.buildContextText/)
  assert.doesNotMatch(wxml, /detail\.stages/)
  assert.doesNotMatch(wxml, /detail\.draftProfile/)
  assert.doesNotMatch(wxml, /detail\.simulationSummary/)
  assert.doesNotMatch(wxml, /detail\.llmContent/)
  assert.doesNotMatch(wxml, /AI 解读/)
  assert.match(wxml, /detail\.heroTitle/)
  assert.doesNotMatch(wxml, /detail\.questionSummary/)
  assert.doesNotMatch(wxml, /class="detail-title">\{\{detail\.question\}\}/)
  assert.match(js, /heroTitle/)
  assert.doesNotMatch(js, /questionSummary/)
  assert.doesNotMatch(js, /mythicPlusReference/)
  assert.match(js, /simcMetricLabel/)
  assert.match(js, /simcUnitText/)
  assert.match(js, /simcDisplayValue/)
  assert.match(wxml, /detail\.simcDisplayValue/)
  assert.match(wxml, /detail\.simcMetricLabel/)
  assert.match(wxml, /detail\.simcUnitText/)
  assert.match(wxml, /detail\.scenarioDisplayText/)
  assert.match(wxml, /detail\.scenarioMetaText/)
  assert.match(wxml, /detail\.statRows/)
  assert.doesNotMatch(wxml, /detail\.reportFindings/)
  assert.doesNotMatch(wxml, /detail\.reportActions/)
  assert.doesNotMatch(wxml, /detail\.reportLimitations/)
  assert.match(wxml, /detail\.briefConclusion/)
  assert.match(api, /requestSimulatorTaskDetail\(taskId\)/)
  assert.match(css, /\.task-detail-hero/)
  assert.match(css, /word-break:\s*break-all/)
  assert.match(css, /white-space:\s*pre-wrap/)
  assert.doesNotMatch(css, /\.detail-code/)
})

test('task detail normalizes long build prompts into a compact report header', () => {
  let pageDefinition = null
  const originalPage = global.Page
  global.Page = (definition) => {
    pageDefinition = definition
  }
  delete require.cache[require.resolve('../pages/simulator/task-detail.js')]
  require('../pages/simulator/task-detail.js')
  global.Page = originalPage

  const longTalentCode = `CAE${'A'.repeat(96)}`
  const normalized = pageDefinition.normalizeTaskDetail({
    taskId: 'task-long',
    mode: 'simcraft_agent',
    question: [
      '第1轮玩家：我从职业专精页带入了冰霜法师的天赋构筑。',
      '请按大秘境多目标场景，先确认这个方案能否生成 SimC 任务。',
      `天赋导入代码：${longTalentCode}`,
      '装备候选：武器：Umbral Spire of Zuraal；饰品：Gaze of the Alnseer'
    ].join('\n'),
    request: {},
    analysis: {
      request: {
        buildContext: {
          className: '法师',
          specName: '冰霜',
          activeQueryTitle: '天赋构筑',
          details: {
            talents: { importCode: longTalentCode },
            gear: { gear: [{ slot: '武器', name: 'Umbral Spire of Zuraal' }] }
          }
        }
      },
      simulation: { ran: false, error: '' },
      recommendations: []
    }
  })

  assert.equal(normalized.heroTitle, 'SimC 任务 · 冰霜法师')
  assert.equal(normalized.question, undefined)
  assert.equal(normalized.questionSummary, undefined)
  assert.equal(normalized.buildContext, undefined)
  assert.equal(normalized.buildContextText, undefined)
})

test('task detail hides generated SimC preview DPS values from the report', () => {
  let pageDefinition = null
  const originalPage = global.Page
  global.Page = (definition) => {
    pageDefinition = definition
  }
  delete require.cache[require.resolve('../pages/simulator/task-detail.js')]
  require('../pages/simulator/task-detail.js')
  global.Page = originalPage
  const wxml = fs.readFileSync('pages/simulator/task-detail.wxml', 'utf8')

  const normalized = pageDefinition.normalizeTaskDetail({
    taskId: 'task-preview',
    mode: 'simcraft_agent',
    question: '我是700装等冰法，想看大秘境 AOE DPS 是否合格',
    request: {},
    analysis: {
      request: { profileSource: 'generated' },
      simulation: {
        quality: 'preview',
        metricLabel: '正式 SimC DPS',
        metricUnit: '需要完整 /simc 导出',
        metrics: { dps: '26.129' },
        error: ''
      },
      recommendations: ['已生成可执行 SimC 模板；未执行正式 SimC DPS 模拟。']
    }
  })

  assert.equal(normalized.simcStatusText, '需完整 /simc')
  assert.equal(normalized.simcMetricLabel, '正式 SimC DPS')
  assert.equal(normalized.simcUnitText, '需要完整 /simc 导出')
  assert.equal(normalized.simcDps, '')
  assert.equal(normalized.simcDisplayValue, '未执行正式模拟')
  assert.match(normalized.briefConclusion, /未执行正式 SimC DPS 模拟/)
  assert.doesNotMatch(normalized.briefConclusion, /26\.129/)
})

test('task detail exposes structured SimC result without report explanation', () => {
  let pageDefinition = null
  const originalPage = global.Page
  global.Page = (definition) => {
    pageDefinition = definition
  }
  delete require.cache[require.resolve('../pages/simulator/task-detail.js')]
  require('../pages/simulator/task-detail.js')
  global.Page = originalPage
  const wxml = fs.readFileSync('pages/simulator/task-detail.wxml', 'utf8')

  const normalized = pageDefinition.normalizeTaskDetail({
    taskId: 'task-report',
    mode: 'simcraft_template',
    question: 'Run fixed template',
    request: {},
    analysis: {
      request: {
        buildContext: {
          className: 'Mage',
          specName: 'Arcane',
          details: { talents: {}, gear: { gear: [] } }
        }
      },
      simulation: { ran: false, error: '', metrics: {} },
      recommendations: ['Submit the confirmed task to run full SimC.'],
      simcReport: {
        schemaRevision: 'simc-report-v2',
        state: 'completed',
        title: 'Arcane Mage SimC',
        summary: 'SimC completed with 654321 DPS.',
        statusText: 'completed',
        scenario: { key: 'mythic_plus', label: '大秘境基准', fightStyle: 'DungeonSlice', targets: 5, durationSeconds: 360 },
        preparation: {
          summary: 'SimC buffs: optimal_raid=0; self-class raid buff enabled: Skyfury; selected temporary combat buffs: Bloodlust/Heroism, Combat potion.',
          items: [
            {
              key: 'optimal_raid',
              category: 'raid_buff_baseline',
              label: 'Full raid buff package',
              state: 'disabled',
              summary: 'SimulationCraft optimal_raid is disabled; only backend-verified self-class buffs may be added.',
              evidenceState: 'verified'
            },
            {
              key: 'skyfury',
              category: 'self_class_raid_buff',
              label: 'Skyfury',
              state: 'enabled',
              summary: "Only the player's own class raid buff is enabled: Skyfury.",
              evidenceState: 'verified'
            },
            {
              key: 'enhancement_weapon_imbues',
              category: 'spec_combat_preparation',
              label: 'Enhancement weapon imbues',
              state: 'pending_evidence',
              summary: 'Windfury Weapon and Flametongue Weapon are pending current-profile SimC smoke before default injection.',
              evidenceState: 'partial'
            },
            {
              key: 'temporary_combat_buffs',
              category: 'temporary_combat_buffs',
              label: 'Temporary combat buffs',
              state: 'enabled',
              summary: 'Bloodlust/Heroism, Combat potion, Weapon oil or sharpening stone',
              evidenceState: 'partial'
            }
          ]
        },
        build: {
          statSnapshot: {
            statStatus: 'verified',
            primary: { key: 'intellect', label: '智力', value: '2,624', rawValue: 2624 },
            secondary: [
              { key: 'crit', label: '暴击', value: '8,100', convertedValue: '25%' },
              { key: 'haste', label: '急速', value: '3,497', convertedValue: '10.8%' },
              { key: 'mastery', label: '精通', value: '12,440', convertedValue: '78.7%' },
              { key: 'versatility', label: '全能', value: '300', convertedValue: '1%' }
            ]
          }
        },
        result: {
          ran: true,
          hasDps: true,
          dps: '654321',
          dpsDisplay: '654321 DPS',
          metricLabel: 'DPS',
          metricUnit: '伤害/秒'
        },
        messages: {
          blockers: [],
          warnings: [],
          nextActions: ['Use this as the baseline.'],
          evidenceRefs: ['simc.dps']
        }
      },
      report: {
        source: 'deterministic_confirm_preview',
        topFindings: [
          {
            text: 'Template payload validated; confirmOnly did not execute SimC.',
            evidenceRefs: ['simc.confirmOnly', 'simc.template']
          }
        ],
        nextActions: ['Submit the task when ready.'],
        limitations: ['No DPS is available until final submit runs SimC.']
      }
    }
  })

  assert.equal(normalized.reportFindings, undefined)
  assert.equal(normalized.reportActions, undefined)
  assert.equal(normalized.reportLimitations, undefined)
  assert.equal(normalized.hasReportExplanation, undefined)
  assert.equal(normalized.briefConclusion, 'SimC completed with 654321 DPS.')
  assert.equal(normalized.simcDps, '654321')
  assert.equal(normalized.simcDisplayValue, '654321 DPS')
  assert.equal(normalized.preparationSummary, undefined)
  assert.equal(normalized.hasCombatBuffRows, true)
  assert.deepEqual(normalized.combatBuffRows, [
    { key: 'skyfury', label: '团队增益', valueText: '天怒', stateText: '已开启' },
    { key: 'enhancement_weapon_imbues', label: '职业准备', valueText: '风怒武器、火舌武器', stateText: '待验证' },
    { key: 'temporary_combat_buffs', label: '临时增益', valueText: '嗜血 / 英勇、爆发药水、武器涂油', stateText: '已选择' }
  ])
  assert.doesNotMatch(wxml, /detail\.preparationSummary/)
  assert.doesNotMatch(wxml, /模拟增益/)
  assert.match(wxml, /detail\.combatBuffRows/)
  assert.match(wxml, /战斗增益/)
  assert.equal(normalized.scenarioDisplayText, '近似大秘境')
  assert.equal(normalized.scenarioMetaText, 'DungeonSlice · 6分钟')
  assert.deepEqual(normalized.statRows.map((item) => [item.label, item.valueText]), [
    ['智力', '2,624'],
    ['暴击', '25%'],
    ['急速', '10.8%'],
    ['精通', '78.7%'],
    ['全能', '1%']
  ])
})

test('task detail shows unselected temporary combat buffs without backend prose', () => {
  let pageDefinition = null
  const originalPage = global.Page
  global.Page = (definition) => {
    pageDefinition = definition
  }
  delete require.cache[require.resolve('../pages/simulator/task-detail.js')]
  require('../pages/simulator/task-detail.js')
  global.Page = originalPage

  const normalized = pageDefinition.normalizeTaskDetail({
    taskId: 'task-temp-disabled',
    mode: 'simcraft_template',
    request: {},
    analysis: {
      simcReport: {
        schemaRevision: 'simc-report-v2',
        state: 'completed',
        title: 'Elemental Shaman SimC',
        summary: 'SimC completed with 73450.168 DPS.',
        statusText: 'completed',
        preparation: {
          summary: 'SimC buffs: optimal_raid=0; self-class raid buff enabled: Skyfury; temporary combat buffs are off by default.',
          items: [
            {
              key: 'temporary_combat_buffs',
              category: 'temporary_combat_buffs',
              label: 'Temporary combat buffs',
              state: 'disabled',
              summary: 'Bloodlust/Heroism, combat potion, and temporary weapon buffs are off by default.',
              evidenceState: 'verified'
            }
          ]
        },
        result: {
          ran: true,
          hasDps: true,
          dps: '73450.168',
          dpsDisplay: '73450.168 DPS'
        }
      }
    }
  })

  assert.deepEqual(normalized.combatBuffRows, [
    { key: 'temporary_combat_buffs', label: '临时增益', valueText: '未选择', stateText: '未选择' }
  ])
})

test('task detail localizes failed SimC timeout summaries', () => {
  let pageDefinition = null
  const originalPage = global.Page
  global.Page = (definition) => {
    pageDefinition = definition
  }
  delete require.cache[require.resolve('../pages/simulator/task-detail.js')]
  require('../pages/simulator/task-detail.js')
  global.Page = originalPage

  const normalized = pageDefinition.normalizeTaskDetail({
    taskId: 'task-timeout',
    mode: 'simcraft_template',
    status: 'failed',
    request: {},
    analysis: {
      simulation: {
        ran: false,
        error: "Command '['/opt/wow-simc/current/simc', '-']' timed out after 45 seconds",
        metrics: {}
      },
      simcReport: {
        schemaRevision: 'simc-report-v2',
        state: 'failed',
        title: 'Elemental Shaman SimC',
        summary: "Command '['/opt/wow-simc/current/simc', '-']' timed out after 45 seconds",
        statusText: 'failed',
        result: { ran: false, hasDps: false, dps: '', dpsDisplay: '' }
      }
    }
  })

  assert.equal(normalized.statusText, 'failed')
  assert.equal(normalized.briefConclusion, 'SimC 执行超时：当前组合已经开始运行，但本次模拟超过 45 秒未完成。可以稍后重试，或等待前面的任务完成后再提交。')
  assert.doesNotMatch(normalized.briefConclusion, /Command|\[|timed out/i)
})

test('task detail does not leak raw simc diagnostics from legacy simulation errors', () => {
  let pageDefinition = null
  const originalPage = global.Page
  global.Page = (definition) => {
    pageDefinition = definition
  }
  delete require.cache[require.resolve('../pages/simulator/task-detail.js')]
  require('../pages/simulator/task-detail.js')
  global.Page = originalPage

  const normalized = pageDefinition.normalizeTaskDetail({
    taskId: 'task-raw-diagnostic',
    mode: 'simcraft_template',
    status: 'ready',
    request: {},
    analysis: {
      simulation: {
        ran: false,
        error: "Trivial: Player 'websim_unholy' at slot hands has inconsistency between name 'item_249971' and 'relentless_riders_bonegrasps' for id 249971",
        metrics: {}
      },
      simcReport: {
        schemaRevision: 'simc-report-v2',
        state: '',
        title: 'Unholy Death Knight SimC',
        summary: '',
        statusText: '',
        result: { ran: false, hasDps: false, dps: '', dpsDisplay: '' }
      }
    }
  })

  assert.equal(normalized.briefConclusion, '手套装备数据不一致：装备名称和物品 ID 对不上，请重新选择或保存手套。')
  assert.doesNotMatch(normalized.briefConclusion, /Trivial|websim_unholy|item_249971|inconsistency/)
})

test('task detail does not leak raw simc crashes from legacy simulation errors', () => {
  let pageDefinition = null
  const originalPage = global.Page
  global.Page = (definition) => {
    pageDefinition = definition
  }
  delete require.cache[require.resolve('../pages/simulator/task-detail.js')]
  require('../pages/simulator/task-detail.js')
  global.Page = originalPage

  const normalized = pageDefinition.normalizeTaskDetail({
    taskId: 'task-raw-crash',
    mode: 'simcraft_template',
    status: 'ready',
    request: {},
    analysis: {
      simulation: {
        ran: false,
        error: [
          'sim_signal_handler: Segmentation fault! Iteration=0 Seed=-6016506965595101173 TargetHealth=0',
          'sim_signal_handler: Segmentation fault! Thread=1 Iteration=-1 Seed=15740702310078284102 (15740702310078284103) TargetHealth=0'
        ].join('\n\n'),
        metrics: {}
      },
      simcReport: {
        schemaRevision: 'simc-report-v2',
        state: '',
        title: 'Unholy Death Knight SimC',
        summary: '',
        statusText: '',
        result: { ran: false, hasDps: false, dps: '', dpsDisplay: '' }
      }
    }
  })

  assert.match(normalized.briefConclusion, /SimC/)
  assert.doesNotMatch(normalized.briefConclusion, /sim_signal_handler|Segmentation fault|Seed=|TargetHealth/)
})

test('task detail hides legacy LLM report fields for SimC template tasks', () => {
  let pageDefinition = null
  const originalPage = global.Page
  global.Page = (definition) => {
    pageDefinition = definition
  }
  delete require.cache[require.resolve('../pages/simulator/task-detail.js')]
  require('../pages/simulator/task-detail.js')
  global.Page = originalPage

  const normalized = pageDefinition.normalizeTaskDetail({
    taskId: 'task-legacy-template',
    mode: 'simcraft_template',
    question: 'Run saved template',
    request: {
      mode: 'simcraft_template'
    },
    analysis: {
      mode: 'simcraft_template',
      request: { mode: 'simcraft_template' },
      simulation: {
        ran: true,
        error: '',
        metricLabel: 'DPS',
        metricUnit: '伤害/秒',
        metrics: { dps: '73680.202' }
      },
      recommendations: ['请选择同职业专精的完整天赋模板和 16 槽装备模板后再提交。'],
      report: {
        topFindings: [
          { text: 'SimC completed with DPS 73680.202.', evidenceRefs: ['simc.dps'] },
          { text: 'SimC DPS falls within a broad sanity window around the attached external Mythic+ reference.', evidenceRefs: ['simc.benchmark'] }
        ],
        nextActions: ['请选择同职业专精的完整天赋模板和 16 槽装备模板后再提交。'],
        limitations: [
          'Only numbers listed in allowedNumbers are treated as evidence.',
          'LLM prose is explanatory and cannot create new numeric facts.'
        ]
      },
      allowedNumbers: [{ key: 'simc.dps', value: '73680.202' }],
      llm: { called: false, content: '' },
      codex: { worker: 'unused' }
    }
  })

  assert.equal(normalized.modeText, 'SimC 模板')
  assert.equal(normalized.simcDps, '73680.202')
  assert.equal(normalized.simcDisplayValue, '73680.202')
  assert.equal(normalized.recommendations, undefined)
  assert.equal(normalized.reportFindings, undefined)
  assert.equal(normalized.reportActions, undefined)
  assert.equal(normalized.reportLimitations, undefined)
  assert.equal(normalized.hasReportExplanation, undefined)
  assert.equal(normalized.analysis, undefined)
  assert.equal(normalized.request, undefined)
})

test('dormant wcl analysis page is not registered in the first-version app', () => {
  const app = JSON.parse(fs.readFileSync('app.json', 'utf8'))
  const js = fs.readFileSync('pages/simulator/wcl.js', 'utf8')
  const wxml = fs.readFileSync('pages/simulator/wcl.wxml', 'utf8')

  assert.ok(!app.pages.includes('pages/simulator/wcl'))
  assert.match(js, /navTitle:\s*'分析 WCL'/)
  assert.match(wxml, /textarea[\s\S]*value="\{\{wclPrompt\}\}"/)
  assert.match(wxml, /bindtap="submitWclAnalysis"/)
  assert.match(js, /submitWclAnalysis\(\)/)
  assert.match(js, /mode:\s*'wcl'/)
  assert.match(js, /prompt:\s*this\.data\.wclPrompt/)
  assert.match(js, /saveTask:\s*true/)
  assert.match(js, /auth:\s*true/)
  assert.match(js, /allowInsecureGuestRequest:\s*true/)
})

test('wcl result page renders deterministic log evidence and report findings', () => {
  const wxml = fs.readFileSync('pages/simulator/wcl.wxml', 'utf8')
  const css = fs.readFileSync('pages/simulator/wcl.wxss', 'utf8')

  assert.match(wxml, /latestAnalysis\.logEvidence/)
  assert.match(wxml, /latestAnalysis\.logEvidence\.sourceStatus/)
  assert.match(wxml, /latestAnalysis\.logEvidence\.reportCode/)
  assert.match(wxml, /latestAnalysis\.report\.topFindings/)
  assert.match(wxml, /item\.evidenceRefs/)
  assert.match(css, /\.wcl-evidence-card/)
  assert.match(css, /\.wcl-report-finding/)
})

test('guest simulator submissions skip wechat login preflight', async () => {
  let loginCalls = 0
  let analysisOptions = null
  const pageDefinition = loadPageModule('../pages/simulator/wcl.js', {
    '../pages/common/auth-client.js': {
      loginWithWechat: () => {
        loginCalls += 1
        return Promise.resolve(null)
      }
    },
    '../pages/simulator/simulator-api.js': {
      requestSimulatorAnalysis: (request, options) => {
        analysisOptions = options
        return Promise.resolve({
          payload: { status: 'blocked', recommendations: [], report: { topFindings: [] } },
          fromFallback: false,
          error: ''
        })
      }
    },
    '../pages/common/analytics-client.js': {
      trackEvent: () => Promise.resolve(false),
      trackPageLeave: () => Promise.resolve(false),
      trackPageView: () => Promise.resolve(false)
    }
  })
  const originalWx = global.wx
  global.wx = { showToast() {} }
  try {
    const page = createPageInstance(pageDefinition)
    page.submitWclAnalysis()
    await flushPromises()
    await flushPromises()
  } finally {
    global.wx = originalWx
  }

  assert.equal(loginCalls, 0)
  assert.deepEqual(analysisOptions, { auth: true, allowInsecureGuestRequest: true })

  const simcJs = fs.readFileSync('pages/simulator/simc.js', 'utf8')
  const wclJs = fs.readFileSync('pages/simulator/wcl.js', 'utf8')
  assert.doesNotMatch(simcJs, /loginWithWechat\(\)/)
  assert.doesNotMatch(wclJs, /loginWithWechat\(\)/)
})
