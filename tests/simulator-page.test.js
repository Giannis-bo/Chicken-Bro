const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

function flushPromises() {
  return new Promise((resolve) => setTimeout(resolve, 0))
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

const simcClassOptions = [
  { name: 'Mage', key: 'mage', specializations: [{ title: 'Arcane', websimClassKey: 'mage', websimSpecKey: 'arcane' }] },
  { name: 'Warrior', key: 'warrior', specializations: [{ title: 'Arms', websimClassKey: 'warrior', websimSpecKey: 'arms' }] },
  { name: 'Priest', key: 'priest', specializations: [{ title: 'Discipline', websimClassKey: 'priest', websimSpecKey: 'discipline' }] }
]

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
  assert.match(wxml, /class="template-selector compact-selector class-selector"/)
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
  assert.match(css, /\.template-hero \+ \.template-selector/)
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
  const actionBarBlock = (css.match(/\.action-bar\s*\{[^}]*\}/) || [''])[0]

  assert.doesNotMatch(wxml, /<picker\b/)
  assert.doesNotMatch(wxml, /<scroll-view\b/)
  assert.doesNotMatch(wxml, /<button\b/)
  assert.doesNotMatch(wxml, /\sloading="\{\{(?:confirming|submittingTask)\}\}"/)
  assert.doesNotMatch(wxml, /type="list"/)
  assert.doesNotMatch(wxml, /template-workspace/)
  assert.match(wxml, /button-spinner/)
  assert.match(wxml, /校验中/)
  assert.match(wxml, /提交中/)
  assert.match(css, /(?:^|\n)page\s*\{[^}]*background:\s*#060606/)
  assert.doesNotMatch(css, /\.template-workspace/)
  assert.match(pageBlock, /min-height:\s*100vh/)
  assert.match(css, /\.template-hero \+ \.template-selector\s*\{[\s\S]*margin-top:\s*14rpx/)
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

  assert.equal(page.data.summaryStatPanel.noteText, '缺少可执行装备槽位：waist, feet')
  assert.deepEqual(page.data.summaryStatPanel.secondaryRows.map((row) => row.percentText), ['不可用', '不可用', '不可用', '不可用'])
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
  assert.equal(requests[0].request.templateContext.talent.id, 'talent-1')
  assert.equal(requests[0].request.templateContext.gear.id, 'gear-1')
  assert.deepEqual(requests[0].request.templateContext.gear.metadata, { gearSnapshot })
  assert.equal(requests[1].request.confirmOnly, false)
  assert.equal(requests[1].request.saveTask, true)
  assert.deepEqual(requests[1].request.templateContext, requests[0].request.templateContext)
  assert.equal(requests[1].request.classKey, requests[0].request.classKey)
  assert.equal(requests[1].request.raceKey, requests[0].request.raceKey)
  assert.equal(requests[1].request.scenarioKey, requests[0].request.scenarioKey)
  assert.deepEqual(requests[1].options, { auth: true, allowInsecureGuestRequest: true })
  assert.equal(page.data.taskSubmitted, true)
  assert.equal(page.data.submittedTaskId, 'task-1')
  assert.equal(page.data.canSubmitTask, false)
})

test('simc page surfaces confirm request failures without leaving loading stuck', async () => {
  const pageDefinition = loadPageModule('../pages/simulator/simc.js', {
    '../pages/builds/builds-api.js': {
      fallbackBuildsHome: () => ({ classOptions: simcClassOptions }),
      requestBuildsHome: () => Promise.resolve({ payload: { classOptions: simcClassOptions }, fromFallback: true, error: '' })
    },
    '../pages/common/build-template-storage.js': {
      fetchBuildTemplates: (type) => Promise.resolve({
        payload: { templates: type === 'talent' ? [sampleTalentTemplate] : [sampleGearTemplate] },
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
        payload: { templates: type === 'talent' ? [sampleTalentTemplate] : [sampleGearTemplate] },
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

  assert.deepEqual(page.data.blockedReasons, ['template class/spec mismatch', 'missing gear slots: off_hand'])
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

  assert.equal(page.data.resultSummary, 'Template payload validated; confirmOnly did not execute SimC.')
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
      result: { ran: false, hasDps: false, dps: '', dpsDisplay: '' }
    },
    report: {
      topFindings: [{ text: 'Template payload validated; confirmOnly did not execute SimC.' }]
    }
  }, false, '')

  assert.deepEqual(page.data.latestAnalysis, {
    agent: {
      status: 'template_ready'
    },
    simcReport: {
      schemaRevision: 'simc-report-v2',
      state: 'ready',
      summary: 'Template payload validated; submit to run SimC.',
      result: { ran: false, hasDps: false, dps: '', dpsDisplay: '' }
    }
  })
  assert.equal(page.data.latestAnalysis.request, undefined)
  assert.equal(page.data.latestAnalysis.profile, undefined)
  assert.equal(page.data.canSubmitTask, true)
  assert.equal(page.data.resultSummary, 'Template payload validated; submit to run SimC.')
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
  assert.equal(normalized.scenarioDisplayText, '大秘境 AOE 5目标')
  assert.equal(normalized.scenarioMetaText, 'DungeonSlice · 6分钟')
  assert.deepEqual(normalized.statRows.map((item) => [item.label, item.valueText]), [
    ['智力', '2,624'],
    ['暴击', '25%'],
    ['急速', '10.8%'],
    ['精通', '78.7%'],
    ['全能', '1%']
  ])
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
