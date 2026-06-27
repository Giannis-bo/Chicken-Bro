const { requestSimulatorAnalysis } = require('./simulator-api')
const { fallbackBuildsHome, requestBuildsHome } = require('../builds/builds-api')
const { requestWebsimGearStats } = require('../builds/websim-api')
const { fetchBuildTemplates, listBuildTemplates, syncBuildTemplate } = require('../common/build-template-storage')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')

const SIMC_PAGE_ROUTE = ['pages', 'simulator', 'simc'].join('/')
const fallbackPayload = fallbackBuildsHome()

const SCENARIO_OPTIONS = [
  { key: 'single', title: '单体', desc: 'Patchwerk 5 分钟，1 目标' },
  { key: 'mythic_plus', title: '大秘境', desc: 'DungeonSlice 6 分钟，5 目标' }
]

const RACE_OPTIONS = [
  { key: 'human', name: '人类' },
  { key: 'dwarf', name: '矮人' },
  { key: 'night_elf', name: '暗夜精灵' },
  { key: 'gnome', name: '侏儒' },
  { key: 'draenei', name: '德莱尼' },
  { key: 'worgen', name: '狼人' },
  { key: 'pandaren_alliance', name: '联盟熊猫人' },
  { key: 'void_elf', name: '虚空精灵' },
  { key: 'lightforged_draenei', name: '光铸德莱尼' },
  { key: 'dark_iron_dwarf', name: '黑铁矮人' },
  { key: 'kul_tiran', name: '库尔提拉斯人' },
  { key: 'mechagnome', name: '机械侏儒' },
  { key: 'orc', name: '兽人' },
  { key: 'undead', name: '亡灵' },
  { key: 'tauren', name: '牛头人' },
  { key: 'troll', name: '巨魔' },
  { key: 'blood_elf', name: '血精灵' },
  { key: 'goblin', name: '地精' },
  { key: 'pandaren_horde', name: '部落熊猫人' },
  { key: 'nightborne', name: '夜之子' },
  { key: 'highmountain_tauren', name: '至高岭牛头人' },
  { key: 'maghar_orc', name: '玛格汉兽人' },
  { key: 'zandalari_troll', name: '赞达拉巨魔' },
  { key: 'vulpera', name: '狐人' },
  { key: 'pandaren', name: '熊猫人' },
  { key: 'dracthyr', name: '龙希尔' },
  { key: 'earthen', name: '土灵' }
]

const DEFAULT_RACE_BY_CLASS = {
  deathknight: 'orc',
  demonhunter: 'night_elf',
  druid: 'night_elf',
  evoker: 'dracthyr',
  hunter: 'orc',
  mage: 'troll',
  monk: 'pandaren',
  paladin: 'human',
  priest: 'void_elf',
  rogue: 'blood_elf',
  shaman: 'tauren',
  warlock: 'orc',
  warrior: 'orc'
}

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

const SUMMARY_SECONDARY_STATS = [
  { key: 'crit', label: '暴击' },
  { key: 'haste', label: '急速' },
  { key: 'mastery', label: '精通' },
  { key: 'versatility', label: '全能' }
]

const SUMMARY_STAT_PENDING_TEXT = {
  pending: '待计算',
  loading: '计算中',
  missingTalent: '缺天赋',
  missingGear: '缺装备',
  unavailable: '不可用'
}

function cleanSummaryText(value) {
  return String(value === undefined || value === null ? '' : value).trim()
}

function verifiedSummarySnapshot(snapshot) {
  return snapshot && typeof snapshot === 'object' && snapshot.statStatus === 'verified' ? snapshot : null
}

function summaryStatsRequestSignature(request) {
  return JSON.stringify(request || {})
}

function statSnapshotFromTemplate(template, expectedSignature = '') {
  const metadata = (template && template.metadata) || {}
  const snapshot = verifiedSummarySnapshot(metadata.statSnapshot || metadata.gearStatSnapshot || null)
  const storedSignature = cleanSummaryText(metadata.statSnapshotSignature || '')
  if (snapshot && storedSignature && expectedSignature && storedSignature !== expectedSignature) return null
  return snapshot
}

function statSnapshotFromAnalysis(payload) {
  const details = (((payload || {}).request || {}).buildContext || {}).details || {}
  const statWeights = details.statWeights || {}
  return verifiedSummarySnapshot(
    (payload && payload.statSnapshot) ||
    statWeights.statSnapshot ||
    ((payload && payload.request) || {}).statSnapshot ||
    null
  )
}

function summaryMetricValue(row, fallback) {
  const value = cleanSummaryText(row && row.value)
  return value || fallback
}

function summaryMetricPercent(row, fallback) {
  const fallbackText = fallback || SUMMARY_STAT_PENDING_TEXT.pending
  if (!row || typeof row !== 'object') return fallbackText
  const converted = cleanSummaryText(row && row.convertedValue)
  if (converted) return converted
  const raw = Number(row && row.convertedRawValue)
  if (Number.isFinite(raw)) {
    const rounded = Math.round(raw * 10) / 10
    return `${Number.isInteger(rounded) ? rounded : rounded.toFixed(1)}%`
  }
  return fallbackText
}

function summaryStatPanelFromSnapshot(snapshot, pendingText = SUMMARY_STAT_PENDING_TEXT.pending) {
  const source = verifiedSummarySnapshot(snapshot)
  const secondary = Array.isArray(source && source.secondary) ? source.secondary : []
  const primary = source && source.primary ? source.primary : null
  const fallbackText = source ? SUMMARY_STAT_PENDING_TEXT.pending : pendingText
  return {
    statStatus: source ? 'verified' : 'pending',
    primary: {
      key: cleanSummaryText(primary && primary.key) || 'primary',
      label: cleanSummaryText(primary && primary.label) || '主属性',
      valueText: summaryMetricValue(primary, fallbackText)
    },
    secondaryRows: SUMMARY_SECONDARY_STATS.map((definition) => {
      const row = secondary.find((item) => item && item.key === definition.key) || null
      return {
        key: definition.key,
        label: cleanSummaryText(row && row.label) || definition.label,
        valueText: summaryMetricValue(row, ''),
        percentText: summaryMetricPercent(row, fallbackText)
      }
    })
  }
}

function summaryPendingTextForSelection(selection, fallbackText = SUMMARY_STAT_PENDING_TEXT.pending) {
  if (!selection || !selection.selectedGearTemplate) return SUMMARY_STAT_PENDING_TEXT.missingGear
  if (!selection.selectedTalentTemplate) return SUMMARY_STAT_PENDING_TEXT.missingTalent
  return fallbackText
}

function summaryStatPanelForSelection(selection, fallbackText = SUMMARY_STAT_PENDING_TEXT.pending) {
  const request = summaryStatsRequestForSelection(selection, { ignoreSnapshot: true })
  const snapshot = statSnapshotFromTemplate(
    selection && selection.selectedGearTemplate,
    request ? summaryStatsRequestSignature(request) : ''
  )
  return summaryStatPanelFromSnapshot(snapshot, snapshot ? SUMMARY_STAT_PENDING_TEXT.pending : summaryPendingTextForSelection(selection, fallbackText))
}

function summaryStatPanelFromAnalysis(payload, fallbackTemplate) {
  return summaryStatPanelFromSnapshot(statSnapshotFromAnalysis(payload) || statSnapshotFromTemplate(fallbackTemplate))
}

function structuredGearTemplateRaw(template) {
  const rawString = cleanSummaryText(template && template.rawString)
  if (rawString.startsWith('{')) return rawString
  const metadata = (template && template.metadata) || {}
  return metadata.gearSnapshot ? JSON.stringify(metadata.gearSnapshot) : ''
}

function summaryStatsRequestForSelection(data, options = {}) {
  const gearTemplate = data && data.selectedGearTemplate
  const talentTemplate = data && data.selectedTalentTemplate
  if (!gearTemplate || !talentTemplate) return null
  const rawString = structuredGearTemplateRaw(gearTemplate)
  if (!rawString) return null
  const metadata = gearTemplate.metadata && typeof gearTemplate.metadata === 'object' ? gearTemplate.metadata : {}
  const request = {
    classKey: data.selectedClassKey || gearTemplate.classKey || talentTemplate.classKey || 'mage',
    specKey: gearTemplate.specKey || talentTemplate.specKey || 'arcane',
    raceKey: data.selectedRaceKey || '',
    level: Number(metadata.maxLevel) || 90,
    scenarioKey: data.selectedScenarioKey || gearTemplate.scenarioKey || 'single',
    talents: talentTemplate.rawString || '',
    rawString,
    metadata: metadata.gearSnapshot ? { gearSnapshot: metadata.gearSnapshot } : {}
  }
  if (!options.ignoreSnapshot && statSnapshotFromTemplate(gearTemplate, summaryStatsRequestSignature(request))) return null
  return request
}

function templateWithStatSnapshot(template, snapshot, signature = '') {
  const source = verifiedSummarySnapshot(snapshot)
  if (!template || !source) return template || null
  return {
    ...template,
    metadata: {
      ...((template && template.metadata) || {}),
      statSnapshot: source,
      statSnapshotSignature: signature,
      statSnapshotSource: source.statSource || 'simulationcraft_json'
    }
  }
}

function replaceTemplateById(templates, template) {
  if (!template || !template.id) return templates || []
  return (templates || []).map((item) => (item && item.id === template.id ? template : item))
}

function persistStatSnapshotTemplate(template) {
  if (!template || typeof syncBuildTemplate !== 'function') return Promise.resolve(null)
  return syncBuildTemplate(template).catch(() => null)
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

function raceIndexFor(raceOptions, raceKey) {
  const key = String(raceKey || '').trim()
  if (!key) return -1
  return (raceOptions || []).findIndex((item) => item.key === key)
}

function raceStateForClass(classKey, previousRaceKey = '') {
  const defaultRaceKey = DEFAULT_RACE_BY_CLASS[String(classKey || '').trim()] || 'troll'
  const selectedRaceKey = raceIndexFor(RACE_OPTIONS, previousRaceKey) >= 0 ? previousRaceKey : defaultRaceKey
  const selectedRaceIndex = Math.max(0, raceIndexFor(RACE_OPTIONS, selectedRaceKey))
  const selectedRace = RACE_OPTIONS[selectedRaceIndex] || RACE_OPTIONS[0]
  return {
    raceOptions: RACE_OPTIONS,
    selectedRaceIndex,
    selectedRaceKey: selectedRace ? selectedRace.key : '',
    selectedRaceName: selectedRace ? selectedRace.name : ''
  }
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
    selectedRaceKey: data.selectedRaceKey || '',
    selectedScenarioKey: data.selectedScenarioKey || 'single',
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
  const raceState = raceStateForClass(selectedClassKey, previous.selectedRaceKey)
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
    ...raceState,
    talentTemplates: talentList,
    gearTemplates: gearList,
    selectedTalentTemplateIndex,
    selectedGearTemplateIndex,
    selectedTalentTemplate,
    selectedGearTemplate,
    summaryStatPanel: summaryStatPanelForSelection({
      selectedClassKey,
      selectedRaceKey: raceState.selectedRaceKey,
      selectedScenarioKey: previous.selectedScenarioKey || 'single',
      selectedTalentTemplate,
      selectedGearTemplate
    }),
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
    raceOptions: RACE_OPTIONS,
    selectedClassIndex: 0,
    selectedClassKey: '',
    selectedClassName: '',
    selectedRaceIndex: 0,
    selectedRaceKey: 'troll',
    selectedRaceName: '巨魔',
    talentTemplates: [],
    gearTemplates: [],
    selectedTalentTemplateIndex: 0,
    selectedGearTemplateIndex: 0,
    selectedTalentTemplate: null,
    selectedGearTemplate: null,
    summaryStatPanel: summaryStatPanelFromSnapshot(null),
    scenarioOptions: SCENARIO_OPTIONS,
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
    resultSummary: '',
    blockedReasons: [],
    requestError: '',
    fromFallback: true,
    summaryStatsLoading: false,
    summaryStatsRequestSignature: ''
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

  refreshSummaryStatsForSelection() {
    const request = summaryStatsRequestForSelection(this.data)
    if (!request) return Promise.resolve(null)
    const signature = summaryStatsRequestSignature(request)
    if (this.data.summaryStatsLoading || this.data.summaryStatsRequestSignature === signature) {
      return Promise.resolve(null)
    }
    this.setData({
      summaryStatsLoading: true,
      summaryStatsRequestSignature: signature,
      summaryStatPanel: summaryStatPanelForSelection(this.data, SUMMARY_STAT_PENDING_TEXT.loading)
    })
    return requestWebsimGearStats(request).then(({ payload }) => {
      if (this.data.summaryStatsRequestSignature !== signature) return payload
      const snapshot = verifiedSummarySnapshot(payload)
      if (snapshot) {
        const nextGearTemplate = templateWithStatSnapshot(this.data.selectedGearTemplate, snapshot, signature)
        this.setData({
          selectedGearTemplate: nextGearTemplate,
          gearTemplates: replaceTemplateById(this.data.gearTemplates, nextGearTemplate),
          allGearTemplates: replaceTemplateById(this.data.allGearTemplates, nextGearTemplate),
          summaryStatPanel: summaryStatPanelFromSnapshot(snapshot)
        })
        persistStatSnapshotTemplate(nextGearTemplate)
      } else {
        this.setData({
          summaryStatPanel: summaryStatPanelForSelection(this.data, SUMMARY_STAT_PENDING_TEXT.unavailable)
        })
      }
      return payload
    }).catch(() => {
      if (this.data.summaryStatsRequestSignature === signature) {
        this.setData({
          summaryStatPanel: summaryStatPanelForSelection(this.data, SUMMARY_STAT_PENDING_TEXT.unavailable)
        })
      }
      return null
    }).finally(() => {
      if (this.data.summaryStatsRequestSignature === signature) {
        this.setData({ summaryStatsLoading: false })
      }
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
    this.refreshSummaryStatsForSelection()
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
        this.refreshSummaryStatsForSelection()
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
      latestAnalysis: null,
      summaryStatsRequestSignature: ''
    })
    this.refreshSummaryStatsForSelection()
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
      latestAnalysis: null,
      summaryStatsRequestSignature: ''
    })
    this.refreshSummaryStatsForSelection()
  },

  selectRace(event) {
    const index = Number((event.detail || {}).value)
    if (!Number.isInteger(index) || index < 0 || index >= this.data.raceOptions.length) return
    const selectedRace = this.data.raceOptions[index] || null
    if (!selectedRace || !selectedRace.key) return
    this.setData({
      selectedRaceIndex: index,
      selectedRaceKey: selectedRace.key,
      selectedRaceName: selectedRace.name || selectedRace.key,
      canSubmitTask: false,
      taskSubmitted: false,
      confirmedPayload: null,
      blockedReasons: [],
      latestAnalysis: null,
      summaryStatsRequestSignature: ''
    })
    this.refreshSummaryStatsForSelection()
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
      summaryStatPanel: summaryStatPanelForSelection({ ...this.data, selectedTalentTemplate: template }),
      canConfirm: !!(this.data.selectedClassKey && template && this.data.selectedGearTemplate),
      canSubmitTask: false,
      taskSubmitted: false,
      confirmedPayload: null,
      blockedReasons: [],
      latestAnalysis: null,
      summaryStatsRequestSignature: ''
    })
    this.refreshSummaryStatsForSelection()
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
      summaryStatPanel: summaryStatPanelForSelection({ ...this.data, selectedGearTemplate: template }),
      canConfirm: !!(this.data.selectedClassKey && this.data.selectedTalentTemplate && template),
      canSubmitTask: false,
      taskSubmitted: false,
      confirmedPayload: null,
      blockedReasons: [],
      latestAnalysis: null,
      summaryStatsRequestSignature: ''
    })
    this.refreshSummaryStatsForSelection()
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
      latestAnalysis: null,
      summaryStatsRequestSignature: ''
    })
    this.refreshSummaryStatsForSelection()
  },

  buildTemplatePayload(confirmOnly = true, saveTask = false) {
    if (!this.data.selectedClassKey || !this.data.selectedTalentTemplate || !this.data.selectedGearTemplate) return null
    return {
      mode: 'simcraft_template',
      confirmOnly,
      saveTask,
      classKey: this.data.selectedClassKey,
      raceKey: this.data.selectedRaceKey,
      raceName: this.data.selectedRaceName,
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

  resultSummaryFromAnalysis(payload) {
    const report = (payload && payload.report) || {}
    const findings = Array.isArray(report.topFindings) ? report.topFindings : []
    const finding = findings.find((item) => item && String(item.text || '').trim())
    if (finding) return String(finding.text || '').trim()
    const recommendations = Array.isArray(payload && payload.recommendations) ? payload.recommendations : []
    return String(recommendations[0] || '').trim()
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
      resultSummary: this.resultSummaryFromAnalysis(payload),
      summaryStatPanel: summaryStatPanelFromAnalysis(payload, this.data.selectedGearTemplate),
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
      raceKey: requestPayload.raceKey,
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
      raceKey: requestPayload.raceKey,
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
