const {
  fallbackBuildsDetail,
  fallbackBuildsHome,
  requestBuildsHome
} = require('./builds-api')
const {
  requestWebsimBootstrap,
  requestWebsimProfile,
  requestWebsimTalents
} = require('./websim-api')
const {
  adjustTalentRank,
  buildTalentViewModel,
  choiceGroupNodes,
  initialTalentRanks,
  maxRankFor,
  parseTalentExportCode,
  rankFor,
  tapTalentNode
} = require('./talent-simulator-core')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')

const SIMC_BUILD_CONTEXT_STORAGE_KEY = 'wow_simc_build_context'
const PAGE_ROUTE = 'pages/builds/talent-simulator'
const defaultSpecId = '法师-冰霜'
const fallbackPayload = fallbackBuildsHome()
const defaultScenarios = [
  { key: 'mythic_plus', title: '大秘境', fightStyle: 'DungeonSlice', targets: 5, durationSeconds: 360 },
  { key: 'single', title: '单体', fightStyle: 'Patchwerk', targets: 1, durationSeconds: 300 },
  { key: 'cleave', title: '顺劈', fightStyle: 'HecticAddCleave', targets: 3, durationSeconds: 300 }
]

function safeToast(title) {
  if (typeof wx !== 'undefined' && typeof wx.showToast === 'function') {
    wx.showToast({ title, icon: 'none' })
  }
}

function findSpecSelection(specId, classOptions) {
  const classes = Array.isArray(classOptions) ? classOptions : []
  for (let classIndex = 0; classIndex < classes.length; classIndex += 1) {
    const specs = classes[classIndex].specializations || []
    const specIndex = specs.findIndex((item) => item.id === specId)
    if (specIndex >= 0) return { classIndex, specIndex }
  }
  return { classIndex: 0, specIndex: 0 }
}

function selectedState(classIndex, specIndex, classOptions) {
  const classes = Array.isArray(classOptions) ? classOptions : []
  const selectedClassIndex = Math.max(0, Math.min(Number(classIndex) || 0, Math.max(0, classes.length - 1)))
  const selectedClass = classes[selectedClassIndex] || null
  const specOptions = selectedClass && Array.isArray(selectedClass.specializations) ? selectedClass.specializations : []
  const selectedSpecIndex = Math.max(0, Math.min(Number(specIndex) || 0, Math.max(0, specOptions.length - 1)))
  const selectedSpec = specOptions[selectedSpecIndex] || null
  const selectedDetail = selectedSpec && selectedSpec.id ? fallbackBuildsDetail(selectedSpec.id) : null
  return {
    selectedClassIndex,
    selectedSpecIndex,
    selectedClass,
    specOptions,
    selectedSpec,
    selectedDetail
  }
}

function specKeys(selectedSpec) {
  return {
    classKey: (selectedSpec && (selectedSpec.websimClassKey || selectedSpec.classKey)) || 'mage',
    specKey: (selectedSpec && (selectedSpec.websimSpecKey || selectedSpec.specKey)) || 'frost'
  }
}

function heroOptionsFor(classes, classKey, specKey) {
  const classMeta = (classes || []).find((item) => item.key === classKey) || {}
  const specMeta = (classMeta.specs || []).find((item) => item.key === specKey) || {}
  return Array.isArray(specMeta.heroTrees) && specMeta.heroTrees.length
    ? specMeta.heroTrees
    : (Array.isArray(classMeta.heroTrees) ? classMeta.heroTrees : [])
}

function pointCapsFromSections(sections) {
  return (sections || []).reduce((acc, section) => {
    if (section && section.key && section.pointCap) acc[section.key] = section.pointCap
    return acc
  }, {})
}

function lineStyle(line) {
  const dx = Number(line.x2 || 0) - Number(line.x1 || 0)
  const dy = Number(line.y2 || 0) - Number(line.y1 || 0)
  const width = Math.sqrt(dx * dx + dy * dy)
  const angle = Math.atan2(dy, dx) * 180 / Math.PI
  return `left:${line.x1}%;top:${line.y1}%;width:${width}%;transform:rotate(${angle}deg);`
}

function nodeStyle(node) {
  return `left:${node.leftPercent}%;top:${node.topPercent}%;`
}

function nodeClass(node) {
  return [
    'talent-node',
    node.selected ? 'selected' : '',
    node.locked ? 'locked' : 'available',
    node.granted ? 'granted' : '',
    node.choice ? 'choice' : '',
    node.searchMatch ? 'search-match' : '',
    node.searchDimmed ? 'search-dimmed' : ''
  ].filter(Boolean).join(' ')
}

function decorateSection(section) {
  if (!section) return { key: '', title: '', pointCount: 0, pointCap: 0, nodes: [], links: [] }
  return {
    ...section,
    pointLabel: `${section.pointCount || 0}/${section.pointCap || 0}`,
    nodes: (section.nodes || []).map((node) => ({
      ...node,
      nodeStyle: nodeStyle(node),
      nodeClass: nodeClass(node),
      rankLabel: `${node.rank || 0}/${node.maxRank || 1}`
    })),
    links: (section.links || []).map((line) => ({
      ...line,
      lineStyle: lineStyle(line)
    }))
  }
}

function reasonText(reason) {
  if (reason === 'missing_parent') return '需要先点亮前置节点'
  if (reason === 'point_requirement') return '当前树点数还未达到门槛'
  if (reason === 'point_cap') return '当前树点数已达上限'
  if (reason === 'granted') return '默认赠送天赋不能移除'
  if (reason === 'max_rank') return '已达到最高等级'
  return '暂时不能选择这个节点'
}

function talentSummary(selectedNodes, scenario) {
  const count = (selectedNodes || []).length
  const scenarioTitle = (scenario && scenario.title) || '大秘境'
  return `${scenarioTitle}：已选择 ${count} 个天赋节点，进入 SimC 前会由后端重新编码校验。`
}

Page({
  data: {
    ...fallbackPayload,
    navTitle: '天赋构筑',
    classOptions: fallbackPayload.classOptions || [],
    ...selectedState(findSpecSelection(defaultSpecId, fallbackPayload.classOptions).classIndex, findSpecSelection(defaultSpecId, fallbackPayload.classOptions).specIndex, fallbackPayload.classOptions),
    websimClasses: [],
    scenarioOptions: defaultScenarios,
    selectedScenarioIndex: 0,
    scenarioKey: 'mythic_plus',
    selectedScenarioTitle: '大秘境',
    classKey: 'mage',
    specKey: 'frost',
    heroKey: '',
    heroOptions: [],
    selectedHeroIndex: 0,
    selectedHeroLabel: '默认',
    currentSeason: null,
    talentStatus: 'loading',
    nodes: [],
    treeSections: [],
    talentRanks: {},
    baseTalentRanks: {},
    pointCaps: {},
    classSection: decorateSection({ key: 'class', title: '职业天赋' }),
    specSection: decorateSection({ key: 'spec', title: '专精天赋' }),
    heroSection: decorateSection({ key: 'hero', title: '英雄天赋' }),
    selectedNodes: [],
    searchTerm: '',
    searchCountText: '',
    websimExportCode: '',
    statusText: '正在读取 WebSim 天赋树',
    loading: false,
    fromFallback: true,
    requestError: '',
    choiceSheet: { visible: false, title: '', options: [] },
    nodeDetailSheet: { visible: false, node: null },
    importSheet: { visible: false, code: '' },
    simcSubmitting: false
  },

  onLoad(options) {
    const specId = options && options.spec ? decodeURIComponent(options.spec) : defaultSpecId
    const selection = findSpecSelection(specId, this.data.classOptions)
    const nextSelection = selectedState(selection.classIndex, selection.specIndex, this.data.classOptions)
    this.analyticsStartedAt = Date.now()
    trackPageView(PAGE_ROUTE, { specId })
    trackEvent('builds_talent_simulator_view', { specId }, { page: PAGE_ROUTE })
    this.setData(nextSelection, () => {
      this.loadRemoteHome()
      this.loadBootstrap()
    })
  },

  onUnload() {
    trackPageLeave(PAGE_ROUTE, this.analyticsStartedAt, {
      specId: (this.data.selectedSpec && this.data.selectedSpec.id) || '',
      scenarioKey: this.data.scenarioKey || ''
    })
  },

  loadRemoteHome() {
    requestBuildsHome().then(({ payload, fromFallback, error }) => {
      if (!payload || !Array.isArray(payload.classOptions)) return
      const specId = (this.data.selectedSpec && this.data.selectedSpec.id) || defaultSpecId
      const selection = findSpecSelection(specId, payload.classOptions)
      this.setData({
        classOptions: payload.classOptions,
        quickActions: payload.quickActions,
        fromFallback,
        requestError: error || '',
        ...selectedState(selection.classIndex, selection.specIndex, payload.classOptions)
      })
    })
  },

  loadBootstrap() {
    this.setData({ loading: true, statusText: '正在连接 WebSim 数据' })
    requestWebsimBootstrap().then(({ payload, fromFallback, error }) => {
      const scenarios = Array.isArray(payload.scenarios) && payload.scenarios.length ? payload.scenarios : defaultScenarios
      this.setData({
        websimClasses: payload.classes || [],
        scenarioOptions: scenarios,
        currentSeason: payload.currentSeason || payload,
        fromFallback,
        requestError: error || ''
      }, () => {
        this.loadTalentsForSelection()
      })
    })
  },

  loadTalentsForSelection() {
    const selectedSpec = this.data.selectedSpec || {}
    const keys = specKeys(selectedSpec)
    const heroes = heroOptionsFor(this.data.websimClasses, keys.classKey, keys.specKey)
    const currentHero = heroes.find((item) => item.key === this.data.heroKey) || heroes[0] || { key: '', label: '英雄天赋' }
    const heroIndex = Math.max(0, heroes.findIndex((item) => item.key === currentHero.key))
    this.setData({
      loading: true,
      classKey: keys.classKey,
      specKey: keys.specKey,
      heroKey: currentHero.key || '',
      heroOptions: heroes,
      selectedHeroIndex: heroIndex,
      selectedHeroLabel: currentHero.label || currentHero.title || currentHero.key || '默认',
      statusText: '正在加载三列天赋树'
    })
    requestWebsimTalents({
      classKey: keys.classKey,
      specKey: keys.specKey,
      heroKey: currentHero.key || ''
    }).then(({ payload, fromFallback, error }) => {
      const pointCaps = pointCapsFromSections(payload.treeSections || [])
      const rankState = initialTalentRanks(payload.nodes || [], { pointCaps })
      this.setData({
        nodes: payload.nodes || [],
        treeSections: payload.treeSections || [],
        talentStatus: payload.talentStatus || 'blocked',
        currentSeason: payload.currentSeason || this.data.currentSeason,
        heroKey: payload.heroKey || currentHero.key || '',
        pointCaps: rankState.pointCaps,
        talentRanks: rankState.talentRanks,
        baseTalentRanks: rankState.baseTalentRanks,
        fromFallback,
        requestError: error || '',
        statusText: (payload.nodes || []).length ? '天赋树已就绪' : 'WebSim 天赋树不可用，请检查后端数据状态'
      }, () => {
        this.renderTalentView()
      })
    }).finally(() => {
      this.setData({ loading: false })
    })
  },

  renderTalentView() {
    const viewModel = buildTalentViewModel({
      nodes: this.data.nodes,
      treeSections: this.data.treeSections,
      classKey: this.data.classKey,
      specKey: this.data.specKey,
      heroKey: this.data.heroKey,
      talentRanks: this.data.talentRanks,
      baseTalentRanks: this.data.baseTalentRanks,
      pointCaps: this.data.pointCaps,
      searchTerm: this.data.searchTerm
    })
    const byKey = viewModel.sections.reduce((acc, section) => {
      acc[section.key] = decorateSection(section)
      return acc
    }, {})
    const scenario = this.data.scenarioOptions[this.data.selectedScenarioIndex] || this.data.scenarioOptions[0]
    this.setData({
      classSection: byKey.class || decorateSection({ key: 'class', title: '职业天赋' }),
      specSection: byKey.spec || decorateSection({ key: 'spec', title: '专精天赋' }),
      heroSection: byKey.hero || decorateSection({ key: 'hero', title: '英雄天赋' }),
      selectedNodes: viewModel.selectedNodes,
      websimExportCode: viewModel.websimExportCode,
      searchCountText: this.data.searchTerm ? `${viewModel.searchMatches.length} 个匹配` : '',
      statusText: talentSummary(viewModel.selectedNodes, scenario)
    })
  },

  selectClass(event) {
    const selection = selectedState(Number(event.detail.value), 0, this.data.classOptions)
    this.setData({ ...selection, heroKey: '' }, () => this.loadTalentsForSelection())
  },

  selectSpec(event) {
    const selection = selectedState(this.data.selectedClassIndex, Number(event.detail.value), this.data.classOptions)
    this.setData({ ...selection, heroKey: '' }, () => this.loadTalentsForSelection())
  },

  selectHero(event) {
    const index = Number(event.detail.value) || 0
    const hero = this.data.heroOptions[index] || {}
    this.setData({
      selectedHeroIndex: index,
      selectedHeroLabel: hero.label || hero.title || hero.key || '默认',
      heroKey: hero.key || ''
    }, () => this.loadTalentsForSelection())
  },

  selectScenario(event) {
    const index = Number(event.detail.value) || 0
    const scenario = this.data.scenarioOptions[index] || this.data.scenarioOptions[0]
    this.setData({
      selectedScenarioIndex: index,
      scenarioKey: scenario.key || 'mythic_plus',
      selectedScenarioTitle: scenario.title || '大秘境'
    }, () => this.renderTalentView())
  },

  updateTalentSearch(event) {
    this.setData({ searchTerm: event.detail.value || '' }, () => this.renderTalentView())
  },

  clearTalentSearch() {
    this.setData({ searchTerm: '' }, () => this.renderTalentView())
  },

  tapTalentNode(event) {
    const id = event.currentTarget.dataset.id || ''
    const node = this.data.nodes.find((item) => item.id === id)
    if (!node) return
    const group = choiceGroupNodes(node, this.data.nodes)
    if (node.choiceGroup && group.length > 1) {
      this.openChoiceSheet(node)
      return
    }
    const currentRank = rankFor(node, this.data.talentRanks, this.data.nodes, this.data.baseTalentRanks)
    if (maxRankFor(node) > 1 && currentRank > 0) {
      this.openNodeDetailFor(node)
      return
    }
    const result = tapTalentNode({
      nodes: this.data.nodes,
      talentRanks: this.data.talentRanks,
      baseTalentRanks: this.data.baseTalentRanks,
      pointCaps: this.data.pointCaps
    }, id)
    if (!result.changed) {
      safeToast(reasonText(result.reason))
      this.openNodeDetailFor(node, result.reason)
      return
    }
    this.setData({ talentRanks: result.talentRanks }, () => this.renderTalentView())
  },

  openChoiceSheet(node) {
    const options = choiceGroupNodes(node, this.data.nodes).map((item) => {
      const itemRank = rankFor(item, this.data.talentRanks, this.data.nodes, this.data.baseTalentRanks)
      return {
        id: item.id,
        name: item.name,
        description: item.description || '',
        iconUrl: item.iconUrl || '',
        rank: itemRank,
        rankLabel: `${itemRank}/${maxRankFor(item)}`,
        selected: itemRank > 0
      }
    })
    this.setData({
      choiceSheet: {
        visible: true,
        title: node.name || '选择天赋',
        options
      }
    })
  },

  closeChoiceSheet() {
    this.setData({ choiceSheet: { visible: false, title: '', options: [] } })
  },

  selectChoiceTalent(event) {
    const id = event.currentTarget.dataset.id || ''
    const result = adjustTalentRank({
      nodes: this.data.nodes,
      talentRanks: this.data.talentRanks,
      baseTalentRanks: this.data.baseTalentRanks,
      pointCaps: this.data.pointCaps
    }, id, 1)
    if (!result.changed) {
      safeToast(reasonText(result.reason))
      return
    }
    this.setData({
      talentRanks: result.talentRanks,
      choiceSheet: { visible: false, title: '', options: [] }
    }, () => this.renderTalentView())
  },

  openNodeDetail(event) {
    const id = event.currentTarget.dataset.id || ''
    const node = this.data.nodes.find((item) => item.id === id)
    if (node) this.openNodeDetailFor(node)
  },

  openNodeDetailFor(node, reason) {
    const rank = rankFor(node, this.data.talentRanks, this.data.nodes, this.data.baseTalentRanks)
    this.setData({
      nodeDetailSheet: {
        visible: true,
        reason: reasonText(reason || ''),
        node: {
          ...node,
          rank,
          maxRank: maxRankFor(node),
          rankLabel: `${rank}/${maxRankFor(node)}`
        }
      }
    })
  },

  closeNodeDetail() {
    this.setData({ nodeDetailSheet: { visible: false, node: null } })
  },

  changeDetailRank(event) {
    const id = event.currentTarget.dataset.id || ''
    const delta = Number(event.currentTarget.dataset.delta) || 0
    const result = adjustTalentRank({
      nodes: this.data.nodes,
      talentRanks: this.data.talentRanks,
      baseTalentRanks: this.data.baseTalentRanks,
      pointCaps: this.data.pointCaps
    }, id, delta)
    if (!result.changed) {
      safeToast(reasonText(result.reason))
      return
    }
    const node = this.data.nodes.find((item) => item.id === id)
    this.setData({ talentRanks: result.talentRanks }, () => {
      this.renderTalentView()
      if (node) this.openNodeDetailFor(node)
    })
  },

  resetTalents() {
    const rankState = initialTalentRanks(this.data.nodes, { pointCaps: this.data.pointCaps })
    this.setData({
      talentRanks: rankState.talentRanks,
      baseTalentRanks: rankState.baseTalentRanks
    }, () => this.renderTalentView())
  },

  openTalentImport() {
    this.setData({ importSheet: { visible: true, code: this.data.websimExportCode || '' } })
  },

  closeTalentImport() {
    this.setData({ importSheet: { visible: false, code: '' } })
  },

  updateImportCode(event) {
    this.setData({ importSheet: { ...this.data.importSheet, code: event.detail.value || '' } })
  },

  applyTalentImport() {
    const parsed = parseTalentExportCode(this.data.importSheet.code || '')
    if (!parsed) {
      safeToast('导入码格式不正确')
      return
    }
    const rankState = initialTalentRanks(this.data.nodes, { pointCaps: this.data.pointCaps })
    const allowedIds = new Set(this.data.nodes.map((node) => node.id))
    Object.keys(parsed.talentRanks).forEach((id) => {
      if (allowedIds.has(id)) rankState.talentRanks[id] = parsed.talentRanks[id]
    })
    this.setData({
      talentRanks: rankState.talentRanks,
      baseTalentRanks: rankState.baseTalentRanks,
      importSheet: { visible: false, code: '' }
    }, () => this.renderTalentView())
  },

  copyTalentExport() {
    const code = this.data.websimExportCode || ''
    if (!code) return
    if (typeof wx !== 'undefined' && typeof wx.setClipboardData === 'function') {
      wx.setClipboardData({ data: code })
    }
  },

  buildSimcContext(encoding) {
    const selectedDetail = this.data.selectedDetail || {}
    const selectedSpec = this.data.selectedSpec || {}
    const details = selectedDetail.details || {}
    const talents = details.talents || {}
    const talentEncoding = encoding || {}
    const simcLines = Array.isArray(talentEncoding.lines) ? talentEncoding.lines : []
    const encodingStatus = talentEncoding.status || 'failed'
    const scenario = this.data.scenarioOptions[this.data.selectedScenarioIndex] || {}
    return {
      specId: selectedDetail.id || selectedSpec.id || '',
      className: selectedDetail.className || selectedSpec.className || '',
      specName: selectedDetail.specName || selectedSpec.specName || '',
      role: selectedDetail.role || selectedSpec.role || '',
      activeQueryKey: 'talents',
      activeQueryTitle: '天赋构筑',
      sourceName: talents.sourceName || selectedDetail.sourceName || 'WebSim',
      publishedAt: talents.publishedAt || selectedDetail.publishedAt || '',
      analysisWindow: talents.analysisWindow || selectedDetail.analysisWindow || '',
      sourceNote: talents.sourceNote || selectedDetail.sourceNote || '',
      details: {
        ...details,
        talents: {
          ...talents,
          websimExportCode: this.data.websimExportCode || '',
          simcLines,
          encodingStatus
        }
      },
      simulatorState: {
        talent: {
          selectedNodes: this.data.selectedNodes || [],
          websimExportCode: this.data.websimExportCode || '',
          heroKey: this.data.heroKey || '',
          scenarioKey: this.data.scenarioKey || '',
          scenarioTitle: scenario.title || '',
          encodingStatus,
          simcLines,
          importCode: talents.importCode || '',
          summary: talentSummary(this.data.selectedNodes || [], scenario)
        }
      }
    }
  },

  openTalentSimc() {
    if (this.data.simcSubmitting) return
    this.setData({ simcSubmitting: true, statusText: '正在校验天赋编码' })
    const payload = {
      classKey: this.data.classKey,
      specKey: this.data.specKey,
      heroKey: this.data.heroKey,
      scenarioKey: this.data.scenarioKey,
      talents: this.data.websimExportCode,
      talentState: {
        selectedNodes: this.data.selectedNodes,
        websimExportCode: this.data.websimExportCode,
        heroKey: this.data.heroKey,
        scenarioKey: this.data.scenarioKey
      }
    }
    requestWebsimProfile(payload).then(({ payload: profilePayload }) => {
      const talentEncoding = (profilePayload && profilePayload.talentEncoding) || { status: 'failed', lines: [] }
      const context = this.buildSimcContext(talentEncoding)
      try {
        wx.setStorageSync(SIMC_BUILD_CONTEXT_STORAGE_KEY, context)
      } catch (error) {
        safeToast('构筑上下文保存失败')
        return
      }
      wx.navigateTo({
        url: `/pages/simulator/simc?from=builds&spec=${encodeURIComponent(context.specId || '')}`,
        fail: () => safeToast('无法打开 SimC 页面')
      })
    }).finally(() => {
      this.setData({ simcSubmitting: false })
      this.renderTalentView()
    })
  }
})
