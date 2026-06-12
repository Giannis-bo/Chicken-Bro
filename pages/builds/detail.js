const {
  fallbackBuildsDetail,
  fallbackBuildsHome,
  requestBuildsDetail,
  requestBuildsHome
} = require('./builds-api')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')

const SIMC_BUILD_CONTEXT_STORAGE_KEY = 'wow_simc_build_context'
const fallbackPayload = fallbackBuildsHome()
const payload = fallbackPayload && Array.isArray(fallbackPayload.quickActions) ? fallbackPayload : {
  quickActions: [],
  classOptions: [],
  trustedSources: []
}
const defaultSpecId = '法师-冰霜'
const simulatorDefaults = {
  talentScenarios: [
    { key: 'mythicPlus', title: '大秘境', label: '多目标', simcHint: '大秘境多目标' },
    { key: 'singleTarget', title: '单体', label: '5 分钟', simcHint: '单体 5 分钟' },
    { key: 'raid', title: '团本', label: 'Boss', simcHint: '团本 Boss' }
  ]
}
const talentScenarios = simulatorDefaults.talentScenarios

function findQuery(queryKey) {
  const actions = Array.isArray(payload.quickActions) ? payload.quickActions : []
  return actions.find((item) => item.key === queryKey) || actions[0] || { key: 'talents', title: '天赋构筑', desc: '' }
}

function detailForQuery(selectedDetail, queryKey) {
  const details = selectedDetail && selectedDetail.details ? selectedDetail.details : {}
  return details[queryKey] || null
}

function gearKey(row, index) {
  return `${row.slot || '装备'}-${row.name || index}-${index}`
}

function inferGearSourceType(source) {
  const text = String(source || '').toLowerCase()
  if (text.includes('dropped') || text.includes('drop') || text.includes('boss')) return '副本掉落'
  if (text.includes('tier') || text.includes('set')) return '套装'
  if (text.includes('crafted') || text.includes('craft')) return '制造'
  if (text.includes('trinket')) return '饰品来源'
  if (text.includes('archon') || text.includes('mythicstats')) return '样本热度'
  if (text.includes('wowhead')) return '物品库'
  return '来源待核'
}

function buildGearAcquisitionRows(activeDetail, acquiredKeys) {
  const acquiredSet = new Set(Array.isArray(acquiredKeys) ? acquiredKeys : [])
  const gearRows = activeDetail && Array.isArray(activeDetail.gear) ? activeDetail.gear : []
  return gearRows.map((row, index) => {
    const key = gearKey(row, index)
    return {
      ...row,
      key,
      priorityLabel: `优先级 ${index + 1}`,
      sourceType: inferGearSourceType(row.source),
      acquired: acquiredSet.has(key)
    }
  })
}

function buildGearProgressText(rows) {
  if (!rows.length) return '暂无装备候选'
  const acquiredCount = rows.filter((row) => row.acquired).length
  return `已获取 ${acquiredCount}/${rows.length} 件`
}

function buildGearNextAction(rows) {
  const nextRow = rows.find((row) => !row.acquired)
  if (!nextRow) return rows.length ? '当前候选已全部标记获取，下一步进入 SimC 做真实收益校验。' : '等待装备数据刷新后再规划获取顺序。'
  return `下一件：${nextRow.slot || '装备'} ${nextRow.name || '候选装备'} · ${nextRow.sourceType}`
}

function buildTalentNodeRows(activeDetail, selectedNodes) {
  const selectedSet = new Set(Array.isArray(selectedNodes) ? selectedNodes : [])
  const coreTalents = activeDetail && Array.isArray(activeDetail.coreTalents) ? activeDetail.coreTalents : []
  return coreTalents.map((name, index) => ({
    key: `${name}-${index}`,
    name,
    badge: index + 1,
    selected: selectedSet.has(name)
  }))
}

function buildTalentSimulationSummary(activeDetail, scenarioKey, selectedNodes) {
  const scenario = talentScenarios.find((item) => item.key === scenarioKey) || talentScenarios[0]
  const selectedList = Array.isArray(selectedNodes) ? selectedNodes : []
  const selectedText = selectedList.length ? selectedList.join('、') : '未选择核心节点'
  const codeText = activeDetail && activeDetail.importCode ? '已带入导入代码' : '缺少导入代码，仅作方向校验'
  return `${scenario.title}${scenario.label}：${selectedText}；${codeText}。`
}

function createDetailDerivedState(selectedDetail, queryKey, state) {
  const activeDetail = detailForQuery(selectedDetail, queryKey)
  const talentDetail = detailForQuery(selectedDetail, 'talents')
  const gearDetail = detailForQuery(selectedDetail, 'gear')
  const currentState = state || {}
  const baseTalents = talentDetail && Array.isArray(talentDetail.coreTalents) ? talentDetail.coreTalents : []
  const activeTalentScenarioKey = currentState.activeTalentScenarioKey || talentScenarios[0].key
  const selectedTalentNodes = Array.isArray(currentState.selectedTalentNodes)
    ? currentState.selectedTalentNodes.filter((name) => baseTalents.includes(name))
    : baseTalents.slice(0, 4)
  const gearAcquiredKeys = Array.isArray(currentState.gearAcquiredKeys) ? currentState.gearAcquiredKeys : []
  const talentNodeRows = buildTalentNodeRows(talentDetail, selectedTalentNodes)
  const talentScenario = talentScenarios.find((item) => item.key === activeTalentScenarioKey) || talentScenarios[0]
  const talentSimulationSummary = buildTalentSimulationSummary(talentDetail, talentScenario.key, selectedTalentNodes)
  const gearAcquisitionRows = buildGearAcquisitionRows(gearDetail, gearAcquiredKeys)

  return {
    activeDetail,
    activeTalentScenarioKey: talentScenario.key,
    selectedTalentNodes,
    talentNodeRows,
    talentSimulationSummary,
    talentSimulatorState: {
      scenarioKey: talentScenario.key,
      scenarioTitle: talentScenario.title,
      simcHint: talentScenario.simcHint,
      selectedNodes: selectedTalentNodes,
      importCode: (talentDetail && talentDetail.importCode) || '',
      summary: talentSimulationSummary
    },
    gearAcquiredKeys,
    gearAcquisitionRows,
    gearProgressText: buildGearProgressText(gearAcquisitionRows),
    gearNextAction: buildGearNextAction(gearAcquisitionRows)
  }
}

function createSelectionState(classIndex, specIndex, queryKey) {
  const classOptions = Array.isArray(payload.classOptions) ? payload.classOptions : []
  const selectedClassIndex = classOptions.length ? Math.max(0, Math.min(Number(classIndex) || 0, classOptions.length - 1)) : 0
  const selectedClass = classOptions[selectedClassIndex] || null
  const specOptions = selectedClass && Array.isArray(selectedClass.specializations) ? selectedClass.specializations : []
  const selectedSpecIndex = specOptions.length ? Math.max(0, Math.min(Number(specIndex) || 0, specOptions.length - 1)) : 0
  const selectedSpec = specOptions[selectedSpecIndex] || null
  const detail = selectedSpec && selectedSpec.id ? fallbackBuildsDetail(selectedSpec.id) : null

  return {
    selectedClassIndex,
    selectedSpecIndex,
    selectedClass,
    specOptions,
    selectedSpec,
    selectedDetail: detail,
    ...createDetailDerivedState(detail, queryKey)
  }
}

function findSpecSelection(specId) {
  for (let classIndex = 0; classIndex < payload.classOptions.length; classIndex += 1) {
    const specIndex = payload.classOptions[classIndex].specializations.findIndex((item) => item.id === specId)
    if (specIndex >= 0) {
      return { classIndex, specIndex }
    }
  }
  return { classIndex: 0, specIndex: 0 }
}

const defaultSelection = findSpecSelection(defaultSpecId)

Page({
  data: {
    ...payload,
    navTitle: '职业专精查询',
    activeQueryKey: 'talents',
    activeQuery: findQuery('talents'),
    talentScenarios,
    ...createSelectionState(defaultSelection.classIndex, defaultSelection.specIndex, 'talents'),
    loading: false,
    fromFallback: true,
    requestError: ''
  },

  onLoad(options) {
    const queryKey = options.query || 'talents'
    const specId = options.spec ? decodeURIComponent(options.spec) : defaultSpecId
    this.analyticsStartedAt = Date.now()
    this.analyticsQueryKey = queryKey
    this.analyticsSpecId = specId
    trackPageView('pages/builds/detail', { queryKey, specId })
    trackEvent('builds_detail_view', { queryKey, specId }, { page: 'pages/builds/detail' })
    const selection = findSpecSelection(specId)
    const selectionState = createSelectionState(selection.classIndex, selection.specIndex, queryKey)
    this.setData({
      activeQueryKey: queryKey,
      activeQuery: findQuery(queryKey),
      ...selectionState
    })
    this.loadRemoteHome()
    this.loadSelectedDetail(selectionState.selectedSpec && selectionState.selectedSpec.id)
  },

  onUnload() {
    trackPageLeave('pages/builds/detail', this.analyticsStartedAt, {
      queryKey: this.data.activeQueryKey || this.analyticsQueryKey || '',
      specId: (this.data.selectedSpec && this.data.selectedSpec.id) || this.analyticsSpecId || ''
    })
  },

  selectClass(event) {
    const classIndex = Number(event.detail.value)
    const selectionState = createSelectionState(classIndex, 0, this.data.activeQueryKey)
    trackEvent('builds_class_select', {
      queryKey: this.data.activeQueryKey,
      className: (selectionState.selectedClass && selectionState.selectedClass.name) || '',
      specId: (selectionState.selectedSpec && selectionState.selectedSpec.id) || ''
    }, { page: 'pages/builds/detail' })
    this.setData(selectionState)
    this.loadSelectedDetail(selectionState.selectedSpec && selectionState.selectedSpec.id)
  },

  selectSpec(event) {
    const specIndex = Number(event.detail.value)
    const selectionState = createSelectionState(this.data.selectedClassIndex, specIndex, this.data.activeQueryKey)
    trackEvent('builds_spec_select', {
      queryKey: this.data.activeQueryKey,
      className: (selectionState.selectedClass && selectionState.selectedClass.name) || '',
      specName: (selectionState.selectedSpec && selectionState.selectedSpec.title) || '',
      specId: (selectionState.selectedSpec && selectionState.selectedSpec.id) || ''
    }, { page: 'pages/builds/detail' })
    this.setData(selectionState)
    this.loadSelectedDetail(selectionState.selectedSpec && selectionState.selectedSpec.id)
  },

  loadRemoteHome() {
    requestBuildsHome().then(({ payload: remotePayload }) => {
      if (!remotePayload || !remotePayload.classOptions) return
      this.setData({
        quickActions: remotePayload.quickActions,
        classOptions: remotePayload.classOptions,
        trustedSources: remotePayload.trustedSources,
        lastAnalyzedAt: remotePayload.lastAnalyzedAt,
        analysisWindow: remotePayload.analysisWindow
      })
    }).catch((error) => {
      this.setData({
        requestError: error.message || String(error),
        fromFallback: true
      })
    })
  },

  loadSelectedDetail(specId) {
    if (!specId) return
    this.setData({ loading: true })
    requestBuildsDetail(specId).then(({ payload, fromFallback, error }) => {
      this.setData({
        selectedDetail: payload,
        ...createDetailDerivedState(payload, this.data.activeQueryKey, this.data),
        fromFallback,
        requestError: error || ''
      })
    }).finally(() => {
      this.setData({ loading: false })
    })
  },

  buildSimcContext() {
    const selectedDetail = this.data.selectedDetail || {}
    const selectedSpec = this.data.selectedSpec || {}
    const activeDetail = this.data.activeDetail || {}
    const activeQuery = this.data.activeQuery || {}
    return {
      specId: selectedDetail.id || selectedSpec.id || '',
      className: selectedDetail.className || selectedSpec.className || '',
      specName: selectedDetail.specName || selectedSpec.specName || '',
      role: selectedDetail.role || selectedSpec.role || '',
      activeQueryKey: this.data.activeQueryKey,
      activeQueryTitle: activeQuery.title || '',
      sourceName: activeDetail.sourceName || selectedDetail.sourceName || '',
      publishedAt: activeDetail.publishedAt || selectedDetail.publishedAt || '',
      analysisWindow: activeDetail.analysisWindow || selectedDetail.analysisWindow || '',
      sourceNote: activeDetail.sourceNote || selectedDetail.sourceNote || '',
      details: selectedDetail.details || {},
      simulatorState: {
        talent: this.data.talentSimulatorState || {},
        gear: {
          progressText: this.data.gearProgressText || '',
          nextAction: this.data.gearNextAction || '',
          acquiredKeys: this.data.gearAcquiredKeys || []
        }
      }
    }
  },

  refreshDerivedState(overrides) {
    const nextState = createDetailDerivedState(
      this.data.selectedDetail,
      this.data.activeQueryKey,
      {
        ...this.data,
        ...(overrides || {})
      }
    )
    this.setData(nextState)
  },

  setTalentScenario(event) {
    const key = event.currentTarget.dataset.key || talentScenarios[0].key
    trackEvent('builds_talent_scenario_select', {
      scenarioKey: key,
      specId: (this.data.selectedSpec && this.data.selectedSpec.id) || ''
    }, { page: 'pages/builds/detail' })
    this.refreshDerivedState({ activeTalentScenarioKey: key })
  },

  toggleTalentNode(event) {
    const node = event.currentTarget.dataset.node || ''
    if (!node) return
    const selectedSet = new Set(this.data.selectedTalentNodes || [])
    if (selectedSet.has(node)) {
      selectedSet.delete(node)
    } else {
      selectedSet.add(node)
    }
    trackEvent('builds_talent_node_toggle', {
      node,
      selected: selectedSet.has(node),
      scenarioKey: this.data.activeTalentScenarioKey,
      specId: (this.data.selectedSpec && this.data.selectedSpec.id) || ''
    }, { page: 'pages/builds/detail' })
    this.refreshDerivedState({ selectedTalentNodes: Array.from(selectedSet) })
  },

  toggleGearAcquired(event) {
    const key = event.currentTarget.dataset.key || ''
    if (!key) return
    const acquiredSet = new Set(this.data.gearAcquiredKeys || [])
    if (acquiredSet.has(key)) {
      acquiredSet.delete(key)
    } else {
      acquiredSet.add(key)
    }
    const gearRow = (this.data.gearAcquisitionRows || []).find((row) => row.key === key) || {}
    trackEvent('builds_gear_toggle', {
      gearSlot: gearRow.slot || '',
      selected: acquiredSet.has(key),
      specId: (this.data.selectedSpec && this.data.selectedSpec.id) || ''
    }, { page: 'pages/builds/detail' })
    this.refreshDerivedState({ gearAcquiredKeys: Array.from(acquiredSet) })
  },

  openTalentSimc() {
    this.openSimcWithBuildContext()
  },

  openSimcWithBuildContext() {
    if (!this.data.selectedDetail || !this.data.activeDetail) return
    const context = this.buildSimcContext()
    trackEvent('builds_simc_entry_click', {
      queryKey: context.activeQueryKey || '',
      specId: context.specId || '',
      className: context.className || '',
      specName: context.specName || '',
      scenarioKey: (context.simulatorState && context.simulatorState.talent && context.simulatorState.talent.scenarioKey) || ''
    }, { page: 'pages/builds/detail' })
    try {
      wx.setStorageSync(SIMC_BUILD_CONTEXT_STORAGE_KEY, context)
    } catch (error) {
      console.error('Failed to store SimC build context', error)
      wx.showToast({ title: '构筑上下文保存失败', icon: 'none' })
      return
    }
    wx.navigateTo({
      url: `/pages/simulator/simc?from=builds&spec=${encodeURIComponent(context.specId || '')}`,
      fail: (error) => {
        console.error('Failed to open SimC page', error)
        wx.showToast({ title: '无法打开 SimC 页面', icon: 'none' })
      }
    })
  }
})
