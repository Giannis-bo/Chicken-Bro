const { requestSimulatorAnalysis } = require('./simulator-api')
const { fallbackBuildsHome, requestBuildsHome } = require('../builds/builds-api')
const { fetchBuildTemplates, listBuildTemplates } = require('../common/build-template-storage')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')

const SIMC_PAGE_ROUTE = ['pages', 'simulator', 'simc'].join('/')
const fallbackPayload = fallbackBuildsHome()

const SCENARIO_OPTIONS = [
  { key: 'single', title: '单体', desc: 'Patchwerk 5 分钟，1 目标' },
  { key: 'mythic_plus', title: '大秘境', desc: 'DungeonSlice 6 分钟，5 目标' }
]

const ANALYSIS_TYPE_OPTIONS = [
  { key: 'baseline', title: '基准', desc: '只跑当前组合 DPS' },
  { key: 'stat_weights', title: '属性权重', desc: '追加 scale factors' }
]

function compactTemplate(template) {
  if (!template) return null
  return {
    id: template.id || '',
    type: template.type || '',
    title: template.title || '',
    rawString: template.rawString || '',
    classKey: template.classKey || '',
    className: template.className || '',
    specKey: template.specKey || '',
    specName: template.specName || '',
    heroKey: template.heroKey || '',
    heroLabel: template.heroLabel || '',
    scenarioKey: template.scenarioKey || '',
    scenarioTitle: template.scenarioTitle || '',
    status: template.status || '',
    source: template.source || ''
  }
}

function uniqueList(values) {
  const result = []
  ;(values || []).forEach((value) => {
    const text = String(value || '').trim()
    if (text && !result.includes(text)) result.push(text)
  })
  return result
}

function templateClassKey(template) {
  return String((template && template.classKey) || '').trim()
}

function filterTemplatesByClass(templates, classKey) {
  const key = String(classKey || '').trim()
  if (!key) return []
  return (templates || []).filter((template) => templateClassKey(template) === key)
}

function templateTime(template) {
  const time = new Date((template && (template.updatedAt || template.createdAt)) || 0).getTime()
  return Number.isFinite(time) ? time : 0
}

function normalizeTemplateList(value) {
  return Array.isArray(value)
    ? value
      .filter((item) => item && item.id && item.rawString)
      .slice()
      .sort((a, b) => templateTime(b) - templateTime(a))
    : []
}

function optionClassKey(option) {
  if (!option) return ''
  if (option.key) return String(option.key).trim()
  if (option.websimClassKey) return String(option.websimClassKey).trim()
  const specs = Array.isArray(option.specializations) ? option.specializations : []
  const spec = specs.find((item) => item && (item.websimClassKey || item.classKey || item.classSlug)) || null
  return String((spec && (spec.websimClassKey || spec.classKey || spec.classSlug)) || '').trim()
}

function normalizeClassOptions(value) {
  return Array.isArray(value)
    ? value.map((item) => {
      const key = optionClassKey(item)
      return {
        ...item,
        key,
        name: item.name || item.className || key
      }
    }).filter((item) => item.key)
    : []
}

function mostRecentTemplateClassKey(talentTemplates, gearTemplates) {
  const recent = normalizeTemplateList([...(talentTemplates || []), ...(gearTemplates || [])])
    .find((template) => templateClassKey(template))
  return templateClassKey(recent)
}

function classIndexFor(classOptions, classKey) {
  const key = String(classKey || '').trim()
  if (!key) return -1
  return (classOptions || []).findIndex((item) => item.key === key)
}

function templateIndexFor(templates, template) {
  if (!template || !template.id) return -1
  return (templates || []).findIndex((item) => item.id === template.id)
}

function templateEmptyText(type, filteredTemplates) {
  if ((filteredTemplates || []).length) return ''
  return type === 'talent' ? '尚未保存天赋模板' : '尚未保存装备模板'
}

function snapshotSelection(data) {
  return {
    selectedClassKey: data.selectedClassKey || '',
    selectedTalentTemplate: data.selectedTalentTemplate || null,
    selectedGearTemplate: data.selectedGearTemplate || null
  }
}

function buildTemplateListState(classSource, talentTemplates, gearTemplates, previous = {}) {
  const classOptions = normalizeClassOptions(classSource)
  const allTalentTemplates = normalizeTemplateList(talentTemplates)
  const allGearTemplates = normalizeTemplateList(gearTemplates)
  const previousClassKey = String(previous.selectedClassKey || '').trim()
  const recentClassKey = mostRecentTemplateClassKey(allTalentTemplates, allGearTemplates)
  const selectedClassKey = classIndexFor(classOptions, previousClassKey) >= 0
    ? previousClassKey
    : (classIndexFor(classOptions, recentClassKey) >= 0 ? recentClassKey : '')
  const selectedClassIndex = selectedClassKey ? classIndexFor(classOptions, selectedClassKey) : 0
  const currentClass = selectedClassKey ? classOptions[selectedClassIndex] || null : null
  const talentList = filterTemplatesByClass(allTalentTemplates, selectedClassKey)
  const gearList = filterTemplatesByClass(allGearTemplates, selectedClassKey)
  const previousTalentIndex = templateIndexFor(talentList, previous.selectedTalentTemplate)
  const previousGearIndex = templateIndexFor(gearList, previous.selectedGearTemplate)
  const selectedTalentTemplateIndex = previousTalentIndex >= 0 ? previousTalentIndex : 0
  const selectedGearTemplateIndex = previousGearIndex >= 0 ? previousGearIndex : 0
  const selectedTalentTemplate = talentList[selectedTalentTemplateIndex] || null
  const selectedGearTemplate = gearList[selectedGearTemplateIndex] || null
  return {
    allTalentTemplates,
    allGearTemplates,
    classOptions,
    selectedClassIndex,
    selectedClassKey,
    selectedClassName: currentClass ? currentClass.name : '',
    talentTemplates: talentList,
    gearTemplates: gearList,
    selectedTalentTemplateIndex,
    selectedGearTemplateIndex,
    selectedTalentTemplate,
    selectedGearTemplate,
    emptyState: {
      class: classOptions.length ? '' : '暂无可选择职业',
      talent: templateEmptyText('talent', talentList),
      gear: templateEmptyText('gear', gearList)
    }
  }
}

Page({
  data: {
    navTitle: '模拟 SimC',
    kicker: '智能分析 01',
    title: '模拟 SimC',
    desc: '选择已保存的天赋模板、装备模板和固定场景，提交单组合基准模拟。',
    allTalentTemplates: [],
    allGearTemplates: [],
    classOptions: [],
    selectedClassIndex: 0,
    selectedClassKey: '',
    selectedClassName: '',
    talentTemplates: [],
    gearTemplates: [],
    selectedTalentTemplateIndex: 0,
    selectedGearTemplateIndex: 0,
    selectedTalentTemplate: null,
    selectedGearTemplate: null,
    scenarioOptions: SCENARIO_OPTIONS,
    analysisTypeOptions: ANALYSIS_TYPE_OPTIONS,
    selectedScenarioKey: 'single',
    selectedAnalysisType: 'baseline',
    emptyState: {
      class: '',
      talent: '',
      gear: ''
    },
    loadingTemplates: false,
    confirming: false,
    submittingTask: false,
    canConfirm: false,
    canSubmitTask: false,
    taskSubmitted: false,
    submittedTaskId: '',
    confirmedPayload: null,
    latestAnalysis: null,
    blockedReasons: [],
    requestError: '',
    fromFallback: true
  },

  onLoad(options) {
    this.analyticsStartedAt = Date.now()
    trackPageView(SIMC_PAGE_ROUTE, {
      source: options && options.from ? options.from : 'simulator'
    })
    this.loadTemplateLists()
  },

  onShow() {
    if (this.analyticsStartedAt) this.loadTemplateLists()
  },

  onUnload() {
    trackPageLeave(SIMC_PAGE_ROUTE, this.analyticsStartedAt, {
      taskSubmitted: this.data.taskSubmitted,
      taskId: this.data.submittedTaskId || ''
    })
  },

  loadTemplateLists() {
    const selection = snapshotSelection(this.data)
    const localTalentTemplates = normalizeTemplateList(listBuildTemplates('talent'))
    const localGearTemplates = normalizeTemplateList(listBuildTemplates('gear'))
    const localClassOptions = (fallbackPayload && fallbackPayload.classOptions) || []
    const localState = buildTemplateListState(localClassOptions, localTalentTemplates, localGearTemplates, selection)
    this.setData({
      loadingTemplates: true,
      ...localState,
      canConfirm: !!(localState.selectedClassKey && localState.selectedTalentTemplate && localState.selectedGearTemplate)
    })
    return Promise.all([requestBuildsHome(), fetchBuildTemplates('talent'), fetchBuildTemplates('gear')])
      .then(([homeResult, talentResult, gearResult]) => {
        const homePayload = homeResult.payload || fallbackPayload || {}
        const classOptions = Array.isArray(homePayload.classOptions) ? homePayload.classOptions : localClassOptions
        const talentTemplates = normalizeTemplateList((talentResult.payload || {}).templates || localTalentTemplates)
        const gearTemplates = normalizeTemplateList((gearResult.payload || {}).templates || localGearTemplates)
        const nextState = buildTemplateListState(classOptions, talentTemplates, gearTemplates, selection)
        this.setData({
          ...nextState,
          canConfirm: !!(nextState.selectedClassKey && nextState.selectedTalentTemplate && nextState.selectedGearTemplate),
          fromFallback: !!(homeResult.fromFallback || talentResult.fromFallback || gearResult.fromFallback),
          requestError: homeResult.error || talentResult.error || gearResult.error || ''
        })
      })
      .finally(() => {
        this.setData({ loadingTemplates: false })
      })
  },

  findTemplate(type, id) {
    const templates = type === 'talent' ? this.data.talentTemplates : this.data.gearTemplates
    return templates.find((item) => item.id === id) || null
  },

  refreshSelectionState() {
    const listState = buildTemplateListState(
      this.data.classOptions,
      this.data.allTalentTemplates.length ? this.data.allTalentTemplates : this.data.talentTemplates,
      this.data.allGearTemplates.length ? this.data.allGearTemplates : this.data.gearTemplates,
      snapshotSelection(this.data)
    )
    this.setData({
      ...listState,
      canConfirm: !!(listState.selectedClassKey && listState.selectedTalentTemplate && listState.selectedGearTemplate),
      canSubmitTask: false,
      taskSubmitted: false,
      confirmedPayload: null,
      blockedReasons: [],
      latestAnalysis: null
    })
  },

  selectClass(event) {
    const index = Number((event.detail || {}).value)
    if (!Number.isInteger(index) || index < 0 || index >= this.data.classOptions.length) return
    const selectedClass = this.data.classOptions[index] || null
    const classKey = selectedClass ? selectedClass.key : ''
    if (!classKey) return
    const listState = buildTemplateListState(
      this.data.classOptions,
      this.data.allTalentTemplates,
      this.data.allGearTemplates,
      { selectedClassKey: classKey }
    )
    this.setData({
      ...listState,
      canConfirm: !!(listState.selectedClassKey && listState.selectedTalentTemplate && listState.selectedGearTemplate),
      canSubmitTask: false,
      taskSubmitted: false,
      confirmedPayload: null,
      blockedReasons: [],
      latestAnalysis: null
    })
  },

  selectTalentTemplate(event) {
    if (!this.data.selectedClassKey) return
    const index = Number((event.detail || {}).value)
    if (!Number.isInteger(index) || index < 0 || index >= this.data.talentTemplates.length) return
    const template = this.data.talentTemplates[index] || null
    if (template && templateClassKey(template) !== this.data.selectedClassKey) return
    this.setData({
      selectedTalentTemplateIndex: index,
      selectedTalentTemplate: template,
      canConfirm: !!(this.data.selectedClassKey && template && this.data.selectedGearTemplate),
      canSubmitTask: false,
      taskSubmitted: false,
      confirmedPayload: null,
      blockedReasons: [],
      latestAnalysis: null
    })
  },

  selectGearTemplate(event) {
    if (!this.data.selectedClassKey) return
    const index = Number((event.detail || {}).value)
    if (!Number.isInteger(index) || index < 0 || index >= this.data.gearTemplates.length) return
    const template = this.data.gearTemplates[index] || null
    if (template && templateClassKey(template) !== this.data.selectedClassKey) return
    this.setData({
      selectedGearTemplateIndex: index,
      selectedGearTemplate: template,
      canConfirm: !!(this.data.selectedClassKey && this.data.selectedTalentTemplate && template),
      canSubmitTask: false,
      taskSubmitted: false,
      confirmedPayload: null,
      blockedReasons: [],
      latestAnalysis: null
    })
  },

  selectScenario(event) {
    const key = event.currentTarget.dataset.key || 'single'
    if (!SCENARIO_OPTIONS.some((item) => item.key === key)) return
    this.setData({
      selectedScenarioKey: key,
      canSubmitTask: false,
      taskSubmitted: false,
      confirmedPayload: null,
      blockedReasons: [],
      latestAnalysis: null
    })
  },

  selectAnalysisType(event) {
    const key = event.currentTarget.dataset.key || 'baseline'
    if (!ANALYSIS_TYPE_OPTIONS.some((item) => item.key === key)) return
    this.setData({
      selectedAnalysisType: key,
      canSubmitTask: false,
      taskSubmitted: false,
      confirmedPayload: null,
      blockedReasons: [],
      latestAnalysis: null
    })
  },

  buildTemplatePayload(confirmOnly = true, saveTask = false) {
    if (!this.data.selectedClassKey || !this.data.selectedTalentTemplate || !this.data.selectedGearTemplate) return null
    return {
      mode: 'simcraft_template',
      confirmOnly,
      saveTask,
      classKey: this.data.selectedClassKey,
      scenarioKey: this.data.selectedScenarioKey,
      analysisType: this.data.selectedAnalysisType,
      templateContext: {
        talent: compactTemplate(this.data.selectedTalentTemplate),
        gear: compactTemplate(this.data.selectedGearTemplate)
      }
    }
  },

  blockedReasonsFromAnalysis(payload) {
    const agent = (payload && payload.agent) || {}
    const validation = agent.validation || {}
    const evidenceState = (payload && payload.evidenceState) || {}
    const simulation = (payload && payload.simulation) || {}
    const simulationErrors = String(simulation.error || '')
      .split(';')
      .map((item) => item.trim())
    return uniqueList([
      ...(validation.errors || []),
      ...(evidenceState.blockers || []),
      ...simulationErrors
    ])
  },

  applyAnalysisResult(payload, fromFallback, error) {
    const agent = (payload && payload.agent) || {}
    const blockedReasons = this.blockedReasonsFromAnalysis(payload)
    const ready = !!(agent.canSubmitTask || agent.status === 'template_ready') && !blockedReasons.length
    this.setData({
      latestAnalysis: payload || null,
      fromFallback: !!fromFallback,
      requestError: error || '',
      blockedReasons,
      canSubmitTask: ready,
      taskSubmitted: this.data.taskSubmitted && ready
    })
  },

  confirmTemplateSimulation() {
    if (!this.data.canConfirm || this.data.confirming) return Promise.resolve(null)
    const requestPayload = this.buildTemplatePayload(true, false)
    if (!requestPayload) return Promise.resolve(null)
    this.setData({ confirming: true, confirmedPayload: requestPayload, blockedReasons: [] })
    trackEvent('simc_template_confirm', {
      classKey: requestPayload.classKey,
      scenarioKey: requestPayload.scenarioKey,
      analysisType: requestPayload.analysisType,
      talentTemplateId: requestPayload.templateContext.talent.id,
      gearTemplateId: requestPayload.templateContext.gear.id
    }, { page: SIMC_PAGE_ROUTE })
    return requestSimulatorAnalysis(requestPayload).then(({ payload, fromFallback, error }) => {
      this.applyAnalysisResult(payload, fromFallback, error)
      return payload
    }).finally(() => {
      this.setData({ confirming: false })
    })
  },

  submitConfirmedTask() {
    if (!this.data.canSubmitTask || this.data.submittingTask || this.data.taskSubmitted) return Promise.resolve(null)
    const basePayload = this.data.confirmedPayload || this.buildTemplatePayload(true, false)
    if (!basePayload) return Promise.resolve(null)
    const requestPayload = {
      ...basePayload,
      confirmOnly: false,
      saveTask: true
    }
    this.setData({ submittingTask: true })
    trackEvent('simc_template_submit', {
      classKey: requestPayload.classKey,
      scenarioKey: requestPayload.scenarioKey,
      analysisType: requestPayload.analysisType,
      talentTemplateId: requestPayload.templateContext.talent.id,
      gearTemplateId: requestPayload.templateContext.gear.id
    }, { page: SIMC_PAGE_ROUTE })
    return requestSimulatorAnalysis(requestPayload, { auth: true, allowInsecureGuestRequest: true })
      .then(({ payload, fromFallback, error }) => {
        const saved = !!(payload && payload.taskId)
        this.applyAnalysisResult(payload, fromFallback, error)
        this.setData({
          taskSubmitted: saved,
          submittedTaskId: (payload && payload.taskId) || '',
          canSubmitTask: !saved && this.data.canSubmitTask
        })
        if (typeof wx !== 'undefined' && wx.showToast) {
          wx.showToast({ title: saved ? '任务已提交' : '提交失败', icon: 'none' })
        }
        return payload
      })
      .finally(() => {
        this.setData({ submittingTask: false })
      })
  }
})
