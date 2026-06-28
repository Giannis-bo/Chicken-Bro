const {
  fallbackBuildsDetail,
  fallbackBuildsHome,
  requestBuildsHome
} = require('./builds-api')
const {
  requestWebsimBootstrap,
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
  templatesForClass: coreTemplatesForClass
} = require('./talent-simulator-core')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')
const { listBuildTemplates, syncBuildTemplate } = require('../common/build-template-storage')
const { attachGameAsset } = require('../common/game-asset')

const PAGE_ROUTE = 'pages/builds/talent-simulator'
const defaultSpecId = '法师-冰霜'
const fallbackPayload = fallbackBuildsHome()
const defaultScenarios = [
  { key: 'single', title: '单体', fightStyle: 'Patchwerk', targets: 1, durationSeconds: 300 },
  { key: 'aoe_5', title: '5目标AOE', fightStyle: 'Patchwerk', targets: 5, durationSeconds: 300 },
  { key: 'mythic_plus', title: '近似大秘境', fightStyle: 'DungeonSlice', targets: 5, durationSeconds: 360 }
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
const MAX_TEMPLATE_TITLE_LENGTH = 28

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

function findSpecSelectionByKeys(classOptions, classKey, specKey) {
  const classes = Array.isArray(classOptions) ? classOptions : []
  for (let classIndex = 0; classIndex < classes.length; classIndex += 1) {
    const klass = classes[classIndex] || {}
    const specs = klass.specializations || []
    const specIndex = specs.findIndex((item) => {
      const keys = specKeys(item)
      return keys.classKey === classKey && keys.specKey === specKey
    })
    if (specIndex >= 0) return { classIndex, specIndex }
  }
  return null
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
  if (line && line.x1Rpx != null && line.y1Rpx != null && line.lengthRpx != null) {
    const angle = Number(line.angleDeg) || 0
    return `left:${line.x1Rpx}rpx;top:${line.y1Rpx}rpx;width:${line.lengthRpx}rpx;transform:rotate(${angle}deg);`
  }
  const dx = Number(line.x2 || 0) - Number(line.x1 || 0)
  const dy = Number(line.y2 || 0) - Number(line.y1 || 0)
  const width = Math.sqrt(dx * dx + dy * dy)
  const angle = Math.atan2(dy, dx) * 180 / Math.PI
  return `left:${line.x1}%;top:${line.y1}%;width:${width}%;transform:rotate(${angle}deg);`
}

function linkClass(line) {
  return [
    'talent-link',
    line && line.active ? 'active' : '',
    line && line.available ? 'available' : ''
  ].filter(Boolean).join(' ')
}

function nodeStyle(node) {
  if (node && node.leftRpx != null && node.topRpx != null) {
    return `left:${node.leftRpx}rpx;top:${node.topRpx}rpx;`
  }
  return `left:${node.leftPercent}%;top:${node.topPercent}%;`
}

function nodeClass(node) {
  return [
    'talent-node',
    node.selected ? 'selected' : '',
    node.locked ? 'locked' : 'available',
    node.granted ? 'granted' : '',
    node.canSelect ? 'selectable' : '',
    node.choice ? 'choice' : '',
    `shape-${node.shape || 'square'}`
  ].filter(Boolean).join(' ')
}

function attachTalentGameAsset(item, contextKey) {
  return attachGameAsset(item || {}, {
    entityType: 'talent',
    entityId: (item && String(item.id || item.spellId || item.name || '')) || 'talent',
    contextKey,
    source: (item && (item.source || item.metadataSource)) || 'game_asset_fallback',
    status: item && item.iconUrl ? 'fallback' : 'missing',
    semanticTags: ['game', 'talent', item && item.treeType],
    usage: ['talent_simulator', contextKey],
    fallbackText: (item && (item.name || item.label || item.firstLetter)) || '?'
  })
}

function decorateSection(section) {
  if (!section) return { key: '', title: '', pointCount: 0, pointCap: 0, nodes: [], links: [] }
  return {
    ...section,
    pointLabel: `${section.pointCount || 0}/${section.pointCap || 0}`,
    nodes: (section.nodes || []).map((node) => {
      const next = attachTalentGameAsset(node, 'talent-simulator-node')
      return {
        ...next,
        nodeStyle: nodeStyle(next),
        nodeClass: nodeClass(next),
        rankLabel: `${next.rank || 0}/${next.maxRank || 1}`
      }
    }),
    links: (section.links || []).map((line) => ({
      ...line,
      linkClass: linkClass(line),
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

function buildTreeNavItems(sectionsByKey, activeTreeKey) {
  return TREE_ORDER.map((key) => {
    const section = decorateSection((sectionsByKey && sectionsByKey[key]) || { key, title: TREE_DEFAULT_TITLES[key] })
    return {
      key,
      label: treeLabel(key),
      subtitle: treeSubtitle(key, section),
      pointLabel: section.pointLabel,
      tabClass: ['tree-tab', activeTreeKey === key ? 'active' : ''].filter(Boolean).join(' ')
    }
  })
}

function exportStatusText(code) {
  return code ? '导出码已生成，保存模板时会重新校验。' : '导出码待生成，请先加载天赋树。'
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
  return `${scenarioTitle}：已选择 ${count} 个天赋节点，保存前会由后端重新编码校验。`
}

function backendTalentSaveBlockReason(context = {}) {
  const readiness = context.talentReadiness || {}
  const authority = context.talentAuthority || {}
  const blockers = []
  if (Array.isArray(readiness.blockers)) blockers.push(...readiness.blockers)
  if (Array.isArray(context.blockers)) blockers.push(...context.blockers)
  const detail = blockers.find((item) => String(item || '').trim()) || '请等待 SimulationCraft 天赋目录同步完成'
  if (context.talentStatus === 'fallback') {
    return `后端天赋数据暂不可用于模拟：${detail}`
  }
  if (authority.diffStatus === 'blocked') {
    return `后端天赋数据暂不可用于模拟：${detail}`
  }
  if (readiness && readiness.simcReady === false) {
    return `后端天赋数据暂不可用于模拟：${detail}`
  }
  return ''
}

function talentReadinessContext(data = {}) {
  return {
    talentStatus: data.talentStatus || '',
    talentAuthority: data.talentAuthority || {},
    talentReadiness: data.talentReadiness || {},
    blockers: data.talentBlockers || []
  }
}

function talentSaveReadiness(sectionsByKey, code, readinessContext = {}) {
  const sections = TREE_ORDER
    .map((key) => ({ key, ...((sectionsByKey && sectionsByKey[key]) || {}) }))
    .filter((section) => Number(section.pointCap) > 0)
  if (!String(code || '').trim() || sections.length === 0) {
    return {
      canSaveTalentTemplate: false,
      saveBlockReason: '请先加载并点满天赋树'
    }
  }
  const incomplete = sections.filter((section) => {
    const pointCount = Number(section.pointCount) || 0
    const pointCap = Number(section.pointCap) || 0
    return pointCount < pointCap
  })
  if (incomplete.length) {
    const detail = incomplete
      .map((section) => `${treeLabel(section.key)} ${Number(section.pointCount) || 0}/${Number(section.pointCap) || 0}`)
      .join('，')
    return {
      canSaveTalentTemplate: false,
      saveBlockReason: `请先点满天赋点：${detail}`
    }
  }
  const backendBlockReason = backendTalentSaveBlockReason(readinessContext)
  if (backendBlockReason) {
    return {
      canSaveTalentTemplate: false,
      saveBlockReason: backendBlockReason
    }
  }
  return {
    canSaveTalentTemplate: true,
    saveBlockReason: ''
  }
}

function cleanTemplateTitlePart(value, fallback, maxLength) {
  const text = String(value || fallback || '')
    .replace(/\s+/g, '')
    .replace(/[·|｜]/g, '-')
    .replace(/^-+|-+$/g, '')
    .trim()
  if (!text) return ''
  return text.length > maxLength ? text.slice(0, maxLength) : text
}

function compactTemplateTime(date) {
  const current = date instanceof Date && !Number.isNaN(date.getTime()) ? date : new Date()
  const month = String(current.getMonth() + 1).padStart(2, '0')
  const day = String(current.getDate()).padStart(2, '0')
  const hour = String(current.getHours()).padStart(2, '0')
  const minute = String(current.getMinutes()).padStart(2, '0')
  return `${month}${day} ${hour}${minute}`
}

function trimTemplateTitle(title) {
  const text = String(title || '').replace(/\s+/g, ' ').trim()
  if (!text) return ''
  return text.length > MAX_TEMPLATE_TITLE_LENGTH ? text.slice(0, MAX_TEMPLATE_TITLE_LENGTH) : text
}

function defaultTalentTemplateTitle(className, specName, heroLabel, date) {
  const time = compactTemplateTime(date)
  const prefix = [
    cleanTemplateTitlePart(className, '职业', 6),
    cleanTemplateTitlePart(specName, '专精', 6),
    cleanTemplateTitlePart(heroLabel, '英雄', 8)
  ].filter(Boolean).join('-') || '天赋'
  const maxPrefixLength = Math.max(4, MAX_TEMPLATE_TITLE_LENGTH - time.length - 1)
  const shortPrefix = prefix.length > maxPrefixLength ? prefix.slice(0, maxPrefixLength) : prefix
  return `${shortPrefix}-${time}`
}

function templateTitleOrDefault(value, fallback) {
  return trimTemplateTitle(value) || trimTemplateTitle(fallback) || '天赋模板'
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
  const detailLabel = [
    template && template.specLabel,
    template && template.heroLabel,
    template && template.scenarioTitle
  ].filter(Boolean).join(' · ')
  return {
    ...(template || {}),
    applyMode: mode,
    detailLabel,
    sampleLabel: sampleCount > 0 ? `样本 ${sampleCount}` : '样本待补',
    keyLabel: maxKeyLevel > 0 ? `最高 +${maxKeyLevel}` : '',
    updatedLabel: shortDate((template && template.updatedAt) || ''),
    actionLabel: mode === 'visual' ? '应用' : '不可编辑',
    cardClass: ['community-template-card', mode === 'simc_only' ? 'external' : '', mode === 'blocked' ? 'blocked' : ''].filter(Boolean).join(' ')
  }
}

function templateUpdatedLabel(template) {
  const value = shortDate((template && (template.updatedAt || template.createdAt)) || '')
  return value ? `保存 ${value}` : ''
}

function savedTalentDetailLabel(template) {
  return [
    template && (template.className || template.classKey),
    template && (template.specName || template.specKey),
    template && (template.heroLabel || template.heroKey)
  ].filter(Boolean).join(' · ')
}

function savedTalentTemplatesForImport() {
  let templates = []
  try {
    templates = listBuildTemplates('talent')
  } catch (error) {
    templates = []
  }
  return (Array.isArray(templates) ? templates : []).map((template) => {
    const rawString = String((template && template.rawString) || '').trim()
    const canApply = !!rawString
    return {
      ...(template || {}),
      name: (template && template.title) || '已保存天赋模板',
      sourceName: (template && template.source) || '我的保存',
      detailLabel: savedTalentDetailLabel(template),
      sampleLabel: (template && template.scenarioTitle) || '个人模板',
      keyLabel: (template && template.statusLabel) || '已保存',
      updatedLabel: templateUpdatedLabel(template),
      rawString,
      websimExportCode: rawString,
      canApplyVisual: canApply,
      actionLabel: canApply ? '应用' : '不可导入',
      cardClass: ['community-template-card', 'saved-template-card', canApply ? '' : 'blocked'].filter(Boolean).join(' ')
    }
  }).slice(0, 8)
}

function activeTemplatesForClass(templates, classKey, specKey) {
  if (typeof coreTemplatesForClass === 'function') {
    return coreTemplatesForClass(templates, classKey, specKey)
  }
  const key = String(classKey || '').trim()
  const spec = String(specKey || '').trim()
  return (Array.isArray(templates) ? templates : []).filter((template) => {
    if (!template) return false
    const parsed = parseTalentExportCode(template.websimExportCode)
    const templateClass = String(template.classKey || (parsed && parsed.classKey) || '').trim()
    const templateSpec = String(template.specKey || (parsed && parsed.specKey) || '').trim()
    if (key && templateClass !== key) return false
    if (spec && templateSpec !== spec) return false
    return true
  }).slice(0, 3)
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
    selectedScenarioIndex: 2,
    scenarioKey: 'mythic_plus',
    selectedScenarioTitle: '近似大秘境',
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
    savedTalentTemplates: [],
    communityTemplateStatusText: '缺少社区模板 API 凭据',
    communityTemplateSheet: { visible: false },
    selectedCommunityTemplate: null,
    talentStatus: 'loading',
    talentAuthority: { diffStatus: 'blocked' },
    talentReadiness: { simcReady: false, blockers: [] },
    talentBlockers: [],
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
    websimExportCode: '',
    exportStatusText: exportStatusText(''),
    statusText: '正在读取 WebSim 天赋树',
    loading: false,
    fromFallback: true,
    requestError: '',
    choiceSheet: { visible: false, title: '', options: [] },
    nodeDetailSheet: { visible: false, node: null },
    saveTemplateSheet: { visible: false, name: '', defaultName: '' },
    canSaveTalentTemplate: false,
    saveBlockReason: '请先点满天赋点后保存',
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
      const selectedScenario = scenarios.find((item) => item.key === this.data.scenarioKey) || scenarios[0] || {}
      const selectedScenarioIndex = Math.max(0, scenarios.findIndex((item) => item.key === selectedScenario.key))
      this.setData({
        websimClasses: payload.classes || [],
        scenarioOptions: scenarios,
        selectedScenarioIndex,
        scenarioKey: selectedScenario.key || '',
        selectedScenarioTitle: selectedScenario.title || '',
        currentSeason: payload.currentSeason || payload,
        fromFallback,
        requestError: error || ''
      }, () => {
        this.loadTalentsForSelection()
      })
    })
  },

  loadTalentsForSelection(options = {}) {
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
    return requestWebsimTalents({
      classKey: keys.classKey,
      specKey: keys.specKey,
      heroKey: currentHero.key || ''
    }).then(({ payload, fromFallback, error }) => {
      const pendingTemplate = options.applyTemplate || null
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
        talentAuthority: payload.talentAuthority || { diffStatus: 'blocked' },
        talentReadiness: payload.talentReadiness || { simcReady: false, blockers: payload.blockers || [] },
        talentBlockers: payload.blockers || [],
        currentSeason: payload.currentSeason || this.data.currentSeason,
        heroKey: payload.heroKey || currentHero.key || '',
        pointCaps: rankState.pointCaps,
        talentRanks: rankState.talentRanks,
        baseTalentRanks: rankState.baseTalentRanks,
        fromFallback,
        requestError: error || '',
        statusText: (payload.nodes || []).length ? '天赋树已就绪' : 'WebSim 天赋树不可用，请检查后端数据状态'
      }, () => {
        if (pendingTemplate) {
          this.applyParsedTalentTemplate(pendingTemplate, null, pendingTemplate.applyStatusPrefix || '已应用社区模板：')
          return
        }
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
      pointCaps: this.data.pointCaps
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
      ? activeTemplatesForClass(this.data.communityTemplates, this.data.classKey, this.data.specKey).map(decorateCommunityTemplate)
      : []
    const saveReadiness = talentSaveReadiness(
      sectionsByKey,
      viewModel.websimExportCode,
      talentReadinessContext(this.data)
    )
    this.setData({
      classSection,
      specSection,
      heroSection,
      activeTreeKey,
      treeNavItems: buildTreeNavItems(sectionsByKey, activeTreeKey),
      activeSection,
      selectedNodes: viewModel.selectedNodes,
      websimExportCode: viewModel.websimExportCode,
      exportStatusText: exportStatusText(viewModel.websimExportCode),
      activeCommunityTemplates,
      communityTemplateStatusText: communityTemplateStatusText(this.data.communityTemplateSync),
      canSaveTalentTemplate: saveReadiness.canSaveTalentTemplate,
      saveBlockReason: saveReadiness.saveBlockReason,
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
      return attachTalentGameAsset({
        id: item.id,
        name: item.name,
        description: item.description || '',
        iconUrl: item.iconUrl || '',
        gameAsset: item.gameAsset,
        source: item.source || '',
        treeType: item.treeType || '',
        rank: itemRank,
        rankLabel: `${itemRank}/${maxRankFor(item)}`,
        selected: itemRank > 0
      }, 'talent-choice-sheet')
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

  openCommunityTemplates() {
    this.setData({
      savedTalentTemplates: savedTalentTemplatesForImport(),
      communityTemplateSheet: { visible: true }
    }, () => this.renderTalentView())
  },

  closeCommunityTemplates() {
    this.setData({ communityTemplateSheet: { visible: false } })
  },

  applyParsedTalentTemplate(template, parsedInput, statusPrefix) {
    const parsed = parsedInput || parseTalentExportCode((template && (template.websimExportCode || template.rawString)) || '')
    if (!parsed) {
      safeToast('模板导入码不可用')
      return false
    }
    const rankState = initialTalentRanks(this.data.nodes, { pointCaps: this.data.pointCaps })
    const allowedIds = new Set(this.data.nodes.map((node) => node.id))
    let appliedCount = 0
    Object.keys(parsed.talentRanks).forEach((nodeId) => {
      if (!allowedIds.has(nodeId)) return
      rankState.talentRanks[nodeId] = parsed.talentRanks[nodeId]
      appliedCount += 1
    })
    if (!appliedCount) {
      safeToast('模板与当前天赋树不匹配')
      return false
    }
    this.setData({
      talentRanks: rankState.talentRanks,
      baseTalentRanks: rankState.baseTalentRanks,
      selectedCommunityTemplate: template,
      communityTemplateSheet: { visible: false },
      statusText: `${statusPrefix || '已应用模板：'}${template.name || template.title || ''}`
    }, () => this.renderTalentView())
    return true
  },

  applyParsedCommunityTemplate(template, parsedInput) {
    return this.applyParsedTalentTemplate(template, parsedInput, '已应用社区模板：')
  },

  applyVisualTalentTemplate(template, statusPrefix) {
    const parsed = parseTalentExportCode((template && (template.websimExportCode || template.rawString)) || '')
    if (parsed) {
      const targetClassKey = parsed.classKey || template.classKey || this.data.classKey
      const targetSpecKey = parsed.specKey || template.specKey || this.data.specKey
      const targetHeroKey = parsed.heroKey || template.heroKey || this.data.heroKey
      const sameSelection = targetClassKey === this.data.classKey &&
        targetSpecKey === this.data.specKey &&
        targetHeroKey === this.data.heroKey
      if (sameSelection) {
        return this.applyParsedTalentTemplate(template, parsed, statusPrefix)
      }
      const selection = findSpecSelectionByKeys(this.data.classOptions, targetClassKey, targetSpecKey)
      if (!selection) {
        safeToast('目标专精不可用')
        return
      }
      const nextState = selectedState(selection.classIndex, selection.specIndex, this.data.classOptions)
      const heroes = heroOptionsFor(this.data.websimClasses, targetClassKey, targetSpecKey)
      const heroIndex = heroes.findIndex((item) => item.key === targetHeroKey)
      if (heroIndex < 0) {
        safeToast('目标英雄天赋不可用')
        return
      }
      const hero = heroes[heroIndex] || {}
      return new Promise((resolve) => {
        this.setData({
          ...nextState,
          heroKey: targetHeroKey,
          heroOptions: heroes,
          selectedHeroIndex: heroIndex,
          selectedHeroLabel: hero.label || hero.title || hero.key || '默认',
          activeTreeKey: 'class'
        }, () => {
          resolve(this.loadTalentsForSelection({
            applyTemplate: {
              ...template,
              applyStatusPrefix: statusPrefix
            }
          }))
        })
      })
    }
    if (!parsed) {
      safeToast('模板导入码不可用')
      return
    }
  },

  applySavedTalentTemplate(event) {
    const id = event.currentTarget.dataset.id || ''
    const template = (this.data.savedTalentTemplates || []).find((item) => item.id === id)
    if (!template || !template.rawString) {
      safeToast('保存模板暂不可用')
      return
    }
    return this.applyVisualTalentTemplate(template, '已应用保存模板：')
  },

  applyCommunityTemplate(event) {
    const id = event.currentTarget.dataset.id || ''
    const template = (this.data.activeCommunityTemplates || []).find((item) => item.id === id)
    if (!template) return
    const mode = communityTemplateApplyMode(template)
    if (mode === 'simc_only') {
      safeToast('此模板仅提供外部导入码，当前页不可编辑')
      return
    }
    if (mode !== 'visual') {
      safeToast('模板暂不可用')
      return
    }
    return this.applyVisualTalentTemplate(template, '已应用社区模板：')
  },

  saveTalentTemplate() {
    const saveReadiness = talentSaveReadiness({
      class: this.data.classSection,
      hero: this.data.heroSection,
      spec: this.data.specSection
    }, this.data.websimExportCode, talentReadinessContext(this.data))
    if (!saveReadiness.canSaveTalentTemplate) {
      this.setData(saveReadiness)
      safeToast(saveReadiness.saveBlockReason)
      return
    }
    const code = this.data.websimExportCode || ''
    if (!code) {
      safeToast('暂无可保存的天赋导出码')
      return
    }
    if (this.data.templateSaving) return
    const selectedDetail = this.data.selectedDetail || {}
    const selectedSpec = this.data.selectedSpec || {}
    const defaultName = defaultTalentTemplateTitle(
      selectedDetail.className || selectedSpec.className || '',
      selectedDetail.specName || selectedSpec.title || selectedSpec.specName || '',
      this.data.selectedHeroLabel || ''
    )
    this.setData({
      saveTemplateSheet: {
        visible: true,
        name: defaultName,
        defaultName
      }
    })
  },

  closeSaveTemplateSheet() {
    if (this.data.templateSaving) return
    this.setData({ saveTemplateSheet: { visible: false, name: '', defaultName: '' } })
  },

  updateTemplateName(event) {
    const name = trimTemplateTitle(event && event.detail ? event.detail.value : '')
    this.setData({
      saveTemplateSheet: {
        ...this.data.saveTemplateSheet,
        name
      }
    })
  },

  confirmSaveTalentTemplate() {
    const saveReadiness = talentSaveReadiness({
      class: this.data.classSection,
      hero: this.data.heroSection,
      spec: this.data.specSection
    }, this.data.websimExportCode, talentReadinessContext(this.data))
    if (!saveReadiness.canSaveTalentTemplate) {
      this.setData(saveReadiness)
      safeToast(saveReadiness.saveBlockReason)
      return Promise.resolve(null)
    }
    const sheet = this.data.saveTemplateSheet || {}
    const templateTitle = templateTitleOrDefault(sheet.name, sheet.defaultName)
    this.setData({
      saveTemplateSheet: {
        ...sheet,
        name: templateTitle
      }
    })
    return this.persistTalentTemplate(templateTitle)
  },

  persistTalentTemplate(templateTitle) {
    const saveReadiness = talentSaveReadiness({
      class: this.data.classSection,
      hero: this.data.heroSection,
      spec: this.data.specSection
    }, this.data.websimExportCode, talentReadinessContext(this.data))
    if (!saveReadiness.canSaveTalentTemplate) {
      this.setData(saveReadiness)
      safeToast(saveReadiness.saveBlockReason)
      return Promise.resolve(null)
    }
    const code = this.data.websimExportCode || ''
    if (!code) {
      safeToast('暂无可保存的天赋导出码')
      return Promise.resolve(null)
    }
    if (this.data.templateSaving) return Promise.resolve(null)
    const scenario = this.data.scenarioOptions[this.data.selectedScenarioIndex] || {}
    const selectedDetail = this.data.selectedDetail || {}
    const selectedSpec = this.data.selectedSpec || {}
    const selectedCommunityTemplate = communityTemplateContext(this.data.selectedCommunityTemplate)
    this.setData({ templateSaving: true, statusText: '正在保存天赋模板' })
    return syncBuildTemplate({
        type: 'talent',
        title: templateTitle,
        classKey: this.data.classKey,
        className: selectedDetail.className || selectedSpec.className || '',
        specKey: this.data.specKey,
        specName: selectedDetail.specName || selectedSpec.title || selectedSpec.specName || '',
        heroKey: this.data.heroKey || '',
        heroLabel: this.data.selectedHeroLabel || '',
        scenarioKey: this.data.scenarioKey || '',
        scenarioTitle: scenario.title || this.data.selectedScenarioTitle || '',
        rawString: code,
        simcLines: [],
        status: 'saved',
        statusLabel: '已保存',
        source: selectedCommunityTemplate && selectedCommunityTemplate.sourceName ? selectedCommunityTemplate.sourceName : 'WebSim 天赋模拟器',
        metadata: {
          selectedNodes: this.data.selectedNodes || [],
          selectedNodeCount: (this.data.selectedNodes || []).length,
          communityTemplate: selectedCommunityTemplate,
          templateTitle,
          summary: talentSummary(this.data.selectedNodes || [], scenario)
        }
      }).then(({ payload }) => {
        const saved = !!(payload && payload.template)
        if (saved) {
          this.setData({ saveTemplateSheet: { visible: false, name: '', defaultName: '' } })
        }
        safeToast(saved ? '天赋模板已保存' : '天赋模板保存失败')
    }).catch((error) => {
      safeToast((error && error.message) || '天赋模板保存失败')
    }).finally(() => {
      this.setData({ templateSaving: false })
      this.renderTalentView()
    })
  },
})
