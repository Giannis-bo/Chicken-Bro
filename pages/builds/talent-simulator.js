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
  communityTemplateApplyMode,
  communityTemplateStatusText,
  initialTalentRanks,
  maxRankFor,
  parseTalentExportCode,
  rankFor,
  tapTalentNode,
  templatesForScenario
} = require('./talent-simulator-core')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')
const { saveBuildTemplate } = require('../common/build-template-storage')

const SIMC_BUILD_CONTEXT_STORAGE_KEY = 'wow_simc_build_context'
const PAGE_ROUTE = 'pages/builds/talent-simulator'
const defaultSpecId = '法师-冰霜'
const fallbackPayload = fallbackBuildsHome()
const defaultScenarios = [
  { key: 'mythic_plus', title: '大秘境', fightStyle: 'DungeonSlice', targets: 5, durationSeconds: 360 },
  { key: 'single', title: '单体', fightStyle: 'Patchwerk', targets: 1, durationSeconds: 300 },
  { key: 'cleave', title: '顺劈', fightStyle: 'HecticAddCleave', targets: 3, durationSeconds: 300 }
]
const TREE_ORDER = ['class', 'hero', 'spec']
const TREE_LABELS = {
  class: '通用',
  hero: '英雄',
  spec: '专精'
}
const TREE_DEFAULT_TITLES = {
  class: '通用天赋',
  hero: '英雄天赋',
  spec: '专精天赋'
}

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

function treeLabel(key) {
  return TREE_LABELS[key] || '天赋'
}

function treeTitle(key, section) {
  if (key === 'class') return '通用天赋树'
  if (key === 'hero') return section.title ? `${section.title} · 英雄天赋树` : '英雄天赋树'
  if (key === 'spec') return section.title ? `${section.title} · 专精天赋树` : '专精天赋树'
  return section.title || '天赋树'
}

function treeSubtitle(key, section) {
  const title = section && section.title
  if (!title || title === TREE_DEFAULT_TITLES[key]) return TREE_DEFAULT_TITLES[key] || ''
  return title
}

function sectionProgressStyle(section) {
  const pointCap = Number(section && section.pointCap) || 0
  const pointCount = Number(section && section.pointCount) || 0
  const progress = pointCap > 0 ? Math.max(0, Math.min(100, (pointCount / pointCap) * 100)) : 0
  return `width:${progress.toFixed(2)}%;`
}

function sectionPanelClass(key) {
  return `active-tree-${key || 'class'}`
}

function sectionGridClass(key) {
  return ['talent-grid', 'active-tree-grid', `active-tree-grid-${key || 'class'}`, key === 'hero' ? 'hero-grid' : ''].filter(Boolean).join(' ')
}

function decorateActiveSection(section) {
  const next = decorateSection(section || { key: 'class', title: TREE_DEFAULT_TITLES.class })
  const key = next.key || 'class'
  return {
    ...next,
    displayLabel: treeLabel(key),
    displayTitle: treeTitle(key, next),
    subtitle: treeSubtitle(key, next),
    progressStyle: sectionProgressStyle(next),
    panelClass: sectionPanelClass(key),
    gridClass: sectionGridClass(key)
  }
}

function buildTreeNavItems(sectionsByKey, activeTreeKey, searchTerm) {
  const hasSearch = Boolean(String(searchTerm || '').trim())
  return TREE_ORDER.map((key) => {
    const section = decorateSection((sectionsByKey && sectionsByKey[key]) || { key, title: TREE_DEFAULT_TITLES[key] })
    const matchCount = Number(section.searchMatchCount) || 0
    const hasMatch = hasSearch && matchCount > 0
    return {
      key,
      label: treeLabel(key),
      subtitle: treeSubtitle(key, section),
      pointLabel: section.pointLabel,
      matchLabel: hasMatch ? `${matchCount} 命中` : '',
      tabClass: ['tree-tab', activeTreeKey === key ? 'active' : '', hasMatch ? 'has-match' : ''].filter(Boolean).join(' ')
    }
  })
}

function exportStatusText(code) {
  return code ? '导出码已生成，复制或带去 SimC 时会重新校验。' : '导出码待生成，请先加载天赋树。'
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

function talentTemplateTitle(className, specName, scenarioTitle) {
  const specLabel = `${specName || ''}${className || ''}`.trim() || '天赋模板'
  return scenarioTitle ? `${specLabel} · ${scenarioTitle}` : specLabel
}

function shortDate(value) {
  const text = String(value || '').trim()
  if (!text) return ''
  return text.includes('T') ? text.split('T')[0] : text.slice(0, 10)
}

function decorateCommunityTemplate(template) {
  const mode = communityTemplateApplyMode(template)
  const sampleCount = Number(template && template.sampleCount) || 0
  const maxKeyLevel = Number(template && template.maxKeyLevel) || 0
  return {
    ...(template || {}),
    applyMode: mode,
    sampleLabel: sampleCount > 0 ? `样本 ${sampleCount}` : '样本待补',
    keyLabel: maxKeyLevel > 0 ? `最高 +${maxKeyLevel}` : '',
    updatedLabel: shortDate((template && template.updatedAt) || ''),
    actionLabel: mode === 'visual' ? '应用' : '带去 SimC',
    cardClass: ['community-template-card', mode === 'simc_only' ? 'external' : '', mode === 'blocked' ? 'blocked' : ''].filter(Boolean).join(' ')
  }
}

function communityTemplateContext(template) {
  if (!template) return null
  return {
    id: template.id || '',
    name: template.name || '',
    flowLabel: template.flowLabel || '',
    scenarioKey: template.scenarioKey || '',
    sourceKey: template.sourceKey || '',
    sourceName: template.sourceName || '',
    sourceUrl: template.sourceUrl || '',
    sampleCount: template.sampleCount || 0,
    maxKeyLevel: template.maxKeyLevel || 0,
    analysisWindow: template.analysisWindow || '',
    updatedAt: template.updatedAt || '',
    rawImportCode: template.rawImportCode || '',
    websimExportCode: template.websimExportCode || '',
    canApplyVisual: !!template.canApplyVisual,
    canUseInSimc: !!template.canUseInSimc
  }
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
    communityTemplates: [],
    communityTemplateSync: {
      sourceStatus: 'missing_credentials',
      sources: {},
      templates: { total: 0, verified: 0, blocked: 0 }
    },
    activeCommunityTemplates: [],
    communityTemplateStatusText: '缺少社区模板 API 凭据',
    communityTemplateSheet: { visible: false },
    selectedCommunityTemplate: null,
    talentStatus: 'loading',
    nodes: [],
    treeSections: [],
    talentRanks: {},
    baseTalentRanks: {},
    pointCaps: {},
    classSection: decorateSection({ key: 'class', title: '职业天赋' }),
    specSection: decorateSection({ key: 'spec', title: '专精天赋' }),
    heroSection: decorateSection({ key: 'hero', title: '英雄天赋' }),
    activeTreeKey: 'class',
    treeNavItems: [],
    activeSection: decorateActiveSection({ key: 'class', title: '职业天赋' }),
    selectedNodes: [],
    searchTerm: '',
    searchCountText: '',
    websimExportCode: '',
    exportStatusText: exportStatusText(''),
    statusText: '正在读取 WebSim 天赋树',
    loading: false,
    fromFallback: true,
    requestError: '',
    choiceSheet: { visible: false, title: '', options: [] },
    nodeDetailSheet: { visible: false, node: null },
    importSheet: { visible: false, code: '' },
    simcSubmitting: false,
    templateSaving: false
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
      statusText: '正在加载天赋树'
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
        communityTemplates: payload.communityTemplates || [],
        communityTemplateSync: payload.communityTemplateSync || {
          sourceStatus: 'missing_credentials',
          sources: {},
          templates: { total: 0, verified: 0, blocked: 0 }
        },
        selectedCommunityTemplate: null,
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
    const classSection = byKey.class || decorateSection({ key: 'class', title: '职业天赋' })
    const specSection = byKey.spec || decorateSection({ key: 'spec', title: '专精天赋' })
    const heroSection = byKey.hero || decorateSection({ key: 'hero', title: '英雄天赋' })
    const sectionsByKey = { class: classSection, spec: specSection, hero: heroSection }
    const activeTreeKey = sectionsByKey[this.data.activeTreeKey] ? this.data.activeTreeKey : 'class'
    const activeSection = decorateActiveSection(sectionsByKey[activeTreeKey])
    const scenario = this.data.scenarioOptions[this.data.selectedScenarioIndex] || this.data.scenarioOptions[0]
    const sourceStatus = (this.data.communityTemplateSync && this.data.communityTemplateSync.sourceStatus) || 'missing_credentials'
    const canShowTemplates = sourceStatus === 'synced' || sourceStatus === 'partial'
    const activeCommunityTemplates = canShowTemplates
      ? templatesForScenario(this.data.communityTemplates, this.data.scenarioKey).map(decorateCommunityTemplate)
      : []
    this.setData({
      classSection,
      specSection,
      heroSection,
      activeTreeKey,
      treeNavItems: buildTreeNavItems(sectionsByKey, activeTreeKey, this.data.searchTerm),
      activeSection,
      selectedNodes: viewModel.selectedNodes,
      websimExportCode: viewModel.websimExportCode,
      exportStatusText: exportStatusText(viewModel.websimExportCode),
      activeCommunityTemplates,
      communityTemplateStatusText: communityTemplateStatusText(this.data.communityTemplateSync),
      searchCountText: this.data.searchTerm ? `${viewModel.searchMatches.length} 个匹配` : '',
      statusText: talentSummary(viewModel.selectedNodes, scenario)
    })
  },

  selectClass(event) {
    const selection = selectedState(Number(event.detail.value), 0, this.data.classOptions)
    this.setData({ ...selection, heroKey: '', activeTreeKey: 'class' }, () => this.loadTalentsForSelection())
  },

  selectSpec(event) {
    const selection = selectedState(this.data.selectedClassIndex, Number(event.detail.value), this.data.classOptions)
    this.setData({ ...selection, heroKey: '', activeTreeKey: 'class' }, () => this.loadTalentsForSelection())
  },

  selectHero(event) {
    const index = Number(event.detail.value) || 0
    const hero = this.data.heroOptions[index] || {}
    this.setData({
      selectedHeroIndex: index,
      selectedHeroLabel: hero.label || hero.title || hero.key || '默认',
      heroKey: hero.key || '',
      activeTreeKey: 'hero'
    }, () => this.loadTalentsForSelection())
  },

  selectScenario(event) {
    const index = Number(event.detail.value) || 0
    const scenario = this.data.scenarioOptions[index] || this.data.scenarioOptions[0]
    this.setData({
      selectedScenarioIndex: index,
      scenarioKey: scenario.key || 'mythic_plus',
      selectedScenarioTitle: scenario.title || '大秘境',
      selectedCommunityTemplate: null
    }, () => this.renderTalentView())
  },

  updateTalentSearch(event) {
    this.setData({ searchTerm: event.detail.value || '' }, () => this.renderTalentView())
  },

  clearTalentSearch() {
    this.setData({ searchTerm: '' }, () => this.renderTalentView())
  },

  selectTalentTree(event) {
    const key = event.currentTarget.dataset.key || 'class'
    const nextKey = TREE_ORDER.includes(key) ? key : 'class'
    this.setData({ activeTreeKey: nextKey }, () => this.renderTalentView())
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
      selectedCommunityTemplate: null,
      importSheet: { visible: false, code: '' }
    }, () => this.renderTalentView())
  },

  openCommunityTemplates() {
    this.setData({ communityTemplateSheet: { visible: true } }, () => this.renderTalentView())
  },

  closeCommunityTemplates() {
    this.setData({ communityTemplateSheet: { visible: false } })
  },

  applyCommunityTemplate(event) {
    const id = event.currentTarget.dataset.id || ''
    const template = (this.data.activeCommunityTemplates || []).find((item) => item.id === id)
    if (!template) return
    const mode = communityTemplateApplyMode(template)
    if (mode === 'simc_only') {
      this.setData({
        selectedCommunityTemplate: template,
        communityTemplateSheet: { visible: false },
        statusText: `已选择社区模板：${template.name}，可带去 SimC。`
      })
      safeToast('此模板可带去 SimC')
      return
    }
    if (mode !== 'visual') {
      safeToast('模板暂不可用')
      return
    }
    const parsed = parseTalentExportCode(template.websimExportCode || '')
    if (!parsed) {
      safeToast('模板导入码不可用')
      return
    }
    const rankState = initialTalentRanks(this.data.nodes, { pointCaps: this.data.pointCaps })
    const allowedIds = new Set(this.data.nodes.map((node) => node.id))
    Object.keys(parsed.talentRanks).forEach((nodeId) => {
      if (allowedIds.has(nodeId)) rankState.talentRanks[nodeId] = parsed.talentRanks[nodeId]
    })
    this.setData({
      talentRanks: rankState.talentRanks,
      baseTalentRanks: rankState.baseTalentRanks,
      selectedCommunityTemplate: template,
      communityTemplateSheet: { visible: false },
      statusText: `已应用社区模板：${template.name}`
    }, () => this.renderTalentView())
  },

  copyTalentExport() {
    const code = this.data.websimExportCode || ''
    if (!code) return
    if (typeof wx !== 'undefined' && typeof wx.setClipboardData === 'function') {
      wx.setClipboardData({ data: code })
    }
  },

  saveTalentTemplate() {
    const code = this.data.websimExportCode || ''
    if (!code) {
      safeToast('暂无可保存的天赋导出码')
      return
    }
    if (this.data.templateSaving) return
    const scenario = this.data.scenarioOptions[this.data.selectedScenarioIndex] || {}
    const selectedDetail = this.data.selectedDetail || {}
    const selectedSpec = this.data.selectedSpec || {}
    const selectedCommunityTemplate = communityTemplateContext(this.data.selectedCommunityTemplate)
    const payload = {
      classKey: this.data.classKey,
      specKey: this.data.specKey,
      heroKey: this.data.heroKey,
      scenarioKey: this.data.scenarioKey,
      talents: code,
      talentState: {
        selectedNodes: this.data.selectedNodes,
        websimExportCode: code,
        communityTemplate: selectedCommunityTemplate,
        heroKey: this.data.heroKey,
        scenarioKey: this.data.scenarioKey
      }
    }
    this.setData({ templateSaving: true, statusText: '正在保存天赋模板' })
    requestWebsimProfile(payload).then(({ payload: profilePayload }) => {
      const talentEncoding = (profilePayload && profilePayload.talentEncoding) || { status: 'failed', lines: [] }
      const simcLines = Array.isArray(talentEncoding.lines) ? talentEncoding.lines : []
      const encodingStatus = talentEncoding.status || 'failed'
      const saved = saveBuildTemplate({
        type: 'talent',
        title: talentTemplateTitle(
          selectedDetail.className || selectedSpec.className || '',
          selectedDetail.specName || selectedSpec.title || selectedSpec.specName || '',
          scenario.title || this.data.selectedScenarioTitle || ''
        ),
        classKey: this.data.classKey,
        className: selectedDetail.className || selectedSpec.className || '',
        specKey: this.data.specKey,
        specName: selectedDetail.specName || selectedSpec.title || selectedSpec.specName || '',
        heroKey: this.data.heroKey || '',
        heroLabel: this.data.selectedHeroLabel || '',
        scenarioKey: this.data.scenarioKey || '',
        scenarioTitle: scenario.title || this.data.selectedScenarioTitle || '',
        rawString: code,
        simcLines,
        status: encodingStatus === 'encoded' ? 'encoded' : 'blocked',
        statusLabel: encodingStatus === 'encoded' ? '已编码' : '不可计算',
        source: selectedCommunityTemplate && selectedCommunityTemplate.sourceName ? selectedCommunityTemplate.sourceName : 'WebSim 天赋模拟器',
        metadata: {
          selectedNodes: this.data.selectedNodes || [],
          selectedNodeCount: (this.data.selectedNodes || []).length,
          communityTemplate: selectedCommunityTemplate,
          encodingStatus,
          encodingErrors: talentEncoding.errors || [],
          summary: talentSummary(this.data.selectedNodes || [], scenario)
        }
      })
      safeToast(saved ? '天赋模板已保存' : '天赋模板保存失败')
    }).catch((error) => {
      safeToast((error && error.message) || '天赋模板保存失败')
    }).finally(() => {
      this.setData({ templateSaving: false })
      this.renderTalentView()
    })
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
    const selectedCommunityTemplate = communityTemplateContext(this.data.selectedCommunityTemplate)
    const communityImportCode = selectedCommunityTemplate && selectedCommunityTemplate.rawImportCode ? selectedCommunityTemplate.rawImportCode : ''
    return {
      specId: selectedDetail.id || selectedSpec.id || '',
      className: selectedDetail.className || selectedSpec.className || '',
      specName: selectedDetail.specName || selectedSpec.specName || '',
      role: selectedDetail.role || selectedSpec.role || '',
      activeQueryKey: 'talents',
      activeQueryTitle: '天赋构筑',
      sourceName: (selectedCommunityTemplate && selectedCommunityTemplate.sourceName) || talents.sourceName || selectedDetail.sourceName || 'WebSim',
      publishedAt: talents.publishedAt || selectedDetail.publishedAt || '',
      analysisWindow: talents.analysisWindow || selectedDetail.analysisWindow || '',
      sourceNote: talents.sourceNote || selectedDetail.sourceNote || '',
      details: {
        ...details,
        talents: {
          ...talents,
          importCode: communityImportCode || talents.importCode || '',
          communityTemplate: selectedCommunityTemplate,
          websimExportCode: this.data.websimExportCode || '',
          simcLines,
          encodingStatus
        }
      },
      simulatorState: {
        talent: {
          selectedNodes: this.data.selectedNodes || [],
          websimExportCode: this.data.websimExportCode || '',
          communityTemplate: selectedCommunityTemplate,
          heroKey: this.data.heroKey || '',
          scenarioKey: this.data.scenarioKey || '',
          scenarioTitle: scenario.title || '',
          encodingStatus,
          simcLines,
          importCode: communityImportCode || talents.importCode || '',
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
        communityTemplate: communityTemplateContext(this.data.selectedCommunityTemplate),
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
