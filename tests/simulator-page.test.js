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

  assert.match(wxml, /picker[\s\S]*range="\{\{classOptions\}\}"[\s\S]*bindchange="selectClass"/)
  assert.match(wxml, /picker[\s\S]*range="\{\{talentTemplates\}\}"[\s\S]*bindchange="selectTalentTemplate"/)
  assert.match(wxml, /picker[\s\S]*range="\{\{gearTemplates\}\}"[\s\S]*bindchange="selectGearTemplate"/)
  assert.match(wxml, /toolbar-picker/)
  assert.match(wxml, /picker-label/)
  assert.match(wxml, /picker-value/)
  assert.match(wxml, /template-selector/)
  assert.match(wxml, /talentTemplates/)
  assert.match(wxml, /gearTemplates/)
  assert.match(wxml, /scenarioOptions/)
  assert.match(wxml, /analysisTypeOptions/)
  assert.match(wxml, /bindtap="confirmTemplateSimulation"/)
  assert.match(wxml, /bindtap="submitConfirmedTask"/)
  assert.match(wxml, /blockedReasons/)
  assert.match(wxml, /确认摘要/)
  assert.doesNotMatch(wxml, /chat-messages|chat-composer|textarea|chatInput|quickReplies/)
  assert.match(js, /fetchBuildTemplates/)
  assert.match(js, /selectedClassKey/)
  assert.match(js, /selectClass\(/)
  assert.match(js, /selectedClassIndex/)
  assert.match(js, /selectedTalentTemplateIndex/)
  assert.match(js, /selectedGearTemplateIndex/)
  assert.match(js, /buildTemplatePayload\(/)
  assert.match(js, /mode:\s*'simcraft_template'/)
  assert.match(js, /buildTemplatePayload\(true,\s*false\)/)
  assert.match(js, /confirmOnly:\s*false/)
  assert.match(js, /saveTask:\s*true/)
  assert.match(js, /allowInsecureGuestRequest:\s*true/)
  assert.doesNotMatch(js, /mode:\s*'simcraft_agent'|sendChatMessage|sendChatContent|useQuickReply|buildPromptFromContext/)
  assert.match(css, /\.template-selector/)
  assert.match(css, /\.toolbar-picker/)
  assert.match(css, /\.picker-label/)
  assert.match(css, /\.picker-value/)
  assert.match(css, /\.confirm-summary/)
  assert.match(css, /\.blocked-panel/)
  assert.doesNotMatch(css, /\.class-option|\.template-option/)
  assert.doesNotMatch(css, /\.chat-composer|\.chat-row-user|\.quick-reply/)
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
  assert.equal(page.data.canConfirm, false)
})

test('simc page reuses the same template payload for confirm and final submit', async () => {
  const requests = []
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
      requestSimulatorAnalysis: (request, options) => {
        requests.push({ request, options })
        return Promise.resolve({
          payload: {
            mode: 'simcraft_template',
            status: 'ready',
            taskId: request.saveTask ? 'task-1' : '',
            request,
            agent: { status: 'template_ready', canSubmitTask: true, validation: { passed: true, errors: [] } },
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
  try {
    const page = createPageInstance(pageDefinition)
    await page.loadTemplateLists()
    await flushPromises()
    page.selectScenario({ currentTarget: { dataset: { key: 'mythic_plus' } } })
    page.selectAnalysisType({ currentTarget: { dataset: { key: 'stat_weights' } } })
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
  assert.equal(requests[0].request.scenarioKey, 'mythic_plus')
  assert.equal(requests[0].request.analysisType, 'stat_weights')
  assert.equal(requests[0].request.templateContext.talent.id, 'talent-1')
  assert.equal(requests[0].request.templateContext.gear.id, 'gear-1')
  assert.equal(requests[1].request.confirmOnly, false)
  assert.equal(requests[1].request.saveTask, true)
  assert.deepEqual(requests[1].request.templateContext, requests[0].request.templateContext)
  assert.equal(requests[1].request.classKey, requests[0].request.classKey)
  assert.equal(requests[1].request.scenarioKey, requests[0].request.scenarioKey)
  assert.deepEqual(requests[1].options, { auth: true, allowInsecureGuestRequest: true })
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

test('smart analysis tab is a three-module entry hub without metrics', () => {
  const app = JSON.parse(fs.readFileSync('app.json', 'utf8'))
  const js = fs.readFileSync('pages/simulator/simulator.js', 'utf8')
  const wxml = fs.readFileSync('pages/simulator/simulator.wxml', 'utf8')
  const css = fs.readFileSync('pages/simulator/simulator.wxss', 'utf8')
  const api = fs.readFileSync('pages/simulator/simulator-api.js', 'utf8')

  assert.ok(app.pages.includes('pages/simulator/simc'))
  assert.ok(app.pages.includes('pages/simulator/wcl'))
  assert.ok(app.pages.includes('pages/simulator/task-detail'))
  assert.match(wxml, /<view class="hero simulator-hero">/)
  assert.doesNotMatch(wxml, /class="metrics"/)
  assert.doesNotMatch(wxml, /metric-card/)
  assert.match(wxml, /analysis-modules/)
  assert.match(wxml, /wx:for="\{\{analysisModules\}\}"/)
  assert.match(wxml, /scroll-into-view="\{\{scrollTarget\}\}"/)
  assert.match(wxml, /id="task-section"/)
  assert.match(wxml, /任务列表/)
  assert.match(wxml, /data-task-id="\{\{item\.taskId\}\}"/)
  assert.match(wxml, /bindtap="openTaskDetail"/)
  assert.match(js, /openAnalysisModule\(event\)/)
  assert.match(js, /openTaskDetail\(event\)/)
  assert.match(js, /onShow\(\)\s*\{\s*this\.loadSimulatorTasks\(\)/)
  assert.match(js, /scrollTarget:\s*''/)
  assert.match(js, /scrollTarget:\s*'task-section'/)
  assert.match(js, /tasks:\s*\[\]/)
  assert.match(js, /taskId:\s*task\.taskId/)
  assert.match(js, /wx\.navigateTo\(\{[\s\S]*\/pages\/simulator\/simc/)
  assert.match(js, /wx\.navigateTo\(\{[\s\S]*\/pages\/simulator\/wcl/)
  assert.match(js, /\/pages\/simulator\/task-detail\?id=/)
  assert.match(api, /navTitle:\s*'智能分析'/)
  assert.match(api, /analysisModules:\s*\[/)
  assert.match(api, /homeWithoutLegacyMetrics/)
  assert.doesNotMatch(api, /metrics:\s*undefined/)
  assert.match(api, /title:\s*'模拟 SimC'/)
  assert.match(api, /title:\s*'分析 WCL'/)
  assert.match(api, /title:\s*'任务列表'/)
  assert.match(css, /\.analysis-modules/)
  assert.match(css, /\.analysis-module-card/)
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
  assert.match(wxml, /玩家问题/)
  assert.match(wxml, /AI 结论/)
  assert.match(wxml, /真实大秘境对标/)
  assert.match(wxml, /执行阶段/)
  assert.doesNotMatch(wxml, /生成的 SimC 模板/)
  assert.doesNotMatch(wxml, /SimC 执行摘要/)
  assert.match(wxml, /detail\.recommendations/)
  assert.match(wxml, /detail\.mythicPlusReference/)
  assert.match(wxml, /detail\.mythicPlusReferenceText/)
  assert.match(wxml, /detail\.buildContextText/)
  assert.match(wxml, /detail\.stages/)
  assert.doesNotMatch(wxml, /detail\.draftProfile/)
  assert.doesNotMatch(wxml, /detail\.simulationSummary/)
  assert.doesNotMatch(wxml, /detail\.llmContent/)
  assert.doesNotMatch(wxml, /AI 解读/)
  assert.match(wxml, /detail\.heroTitle/)
  assert.match(wxml, /detail\.questionSummary/)
  assert.doesNotMatch(wxml, /class="detail-title">\{\{detail\.question\}\}/)
  assert.match(js, /summarizeTaskQuestion\(question\)/)
  assert.match(js, /heroTitle/)
  assert.match(js, /questionSummary/)
  assert.match(js, /simcMetricLabel/)
  assert.match(js, /simcUnitText/)
  assert.match(js, /simcDisplayValue/)
  assert.match(wxml, /detail\.simcDisplayValue/)
  assert.match(wxml, /detail\.simcMetricLabel/)
  assert.match(wxml, /detail\.simcUnitText/)
  assert.match(wxml, /detail\.briefConclusion/)
  assert.match(api, /requestSimulatorTaskDetail\(taskId\)/)
  assert.match(css, /\.task-detail-hero/)
  assert.match(css, /word-break:\s*break-all/)
  assert.match(css, /white-space:\s*pre-wrap/)
  assert.match(css, /\.build-context-box/)
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
  assert.match(normalized.questionSummary, /冰霜法师的天赋构筑/)
  assert.doesNotMatch(normalized.questionSummary, new RegExp(longTalentCode))
  assert.ok(normalized.questionSummary.length < normalized.question.length)
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

test('wcl analysis page submits WCL questions through the simulator analyzer', () => {
  const app = JSON.parse(fs.readFileSync('app.json', 'utf8'))
  const js = fs.readFileSync('pages/simulator/wcl.js', 'utf8')
  const wxml = fs.readFileSync('pages/simulator/wcl.wxml', 'utf8')

  assert.ok(app.pages.includes('pages/simulator/wcl'))
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
