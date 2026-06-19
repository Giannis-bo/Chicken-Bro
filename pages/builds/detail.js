const {
  fallbackBuildsDetail,
  fallbackBuildsHome,
  requestBuildsDetail,
  requestBuildsHome
} = require('./builds-api')
const {
  requestWebsimGear,
  requestWebsimGearStats
} = require('./websim-api')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')
const { syncBuildTemplate } = require('../common/build-template-storage')
const { attachGameAsset } = require('../common/game-asset')

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
const gearTemplateScenarios = [
  { key: 'single', title: '单体' },
  { key: 'mythic_plus', title: '大秘境' },
  { key: 'raid', title: '团本' }
]
const gearCandidateFilters = [
  { key: 'recommended', label: '推荐' },
  { key: 'all', label: '全部' },
  { key: 'dungeon', label: '地下城' },
  { key: 'raid', label: '团本' },
  { key: 'crafted', label: '制造' }
]

function showToast(title) {
  if (typeof wx !== 'undefined' && typeof wx.showToast === 'function') {
    wx.showToast({ title, icon: 'none' })
  }
}

function findQuery(queryKey) {
  const actions = Array.isArray(payload.quickActions) ? payload.quickActions : []
  return actions.find((item) => item.key === queryKey) || actions[0] || { key: 'talents', title: '天赋构筑', desc: '' }
}

function detailForQuery(selectedDetail, queryKey) {
  const details = selectedDetail && selectedDetail.details ? selectedDetail.details : {}
  return details[queryKey] || null
}

function defaultGearStatSnapshot(message) {
  return {
    statStatus: 'blocked',
    blockers: [message || '等待装备模拟数据'],
    primary: null,
    stamina: null,
    secondary: [],
    armor: null,
    weaponDps: null,
    itemLevel: { key: 'itemLevel', label: '装备等级', value: '0', rawValue: 0 },
    maxLevel: 0,
    checkedAt: ''
  }
}

function specWebsimKeys(selectedSpec) {
  const websimClassKey = (selectedSpec && (selectedSpec.websimClassKey || selectedSpec.classKey)) || 'mage'
  const websimSpecKey = (selectedSpec && (selectedSpec.websimSpecKey || selectedSpec.specKey)) || 'frost'
  return {
    classKey: websimClassKey,
    specKey: websimSpecKey
  }
}

function itemDisplayName(item) {
  return (item && (item.displayName || item.localizedName || item.englishName || item.name)) || '待选择装备'
}

function attachGearGameAsset(row, contextKey) {
  const slot = row && (row.slot || row.simcSlot || '')
  const displayName = itemDisplayName(row)
  return attachGameAsset(row || {}, {
    entityType: 'item',
    entityId: (row && String(row.itemId || row.id || displayName)) || displayName,
    contextKey,
    source: (row && (row.metadataSource || row.sourceType || row.source)) || 'game_asset_fallback',
    status: row && (row.simcReady || row.metadataStatus === 'verified') ? 'verified' : ((row && row.iconUrl) ? 'partial' : 'missing'),
    semanticTags: ['game', 'gear', 'item', slot],
    usage: ['builds_detail', contextKey],
    fallbackText: displayName
  })
}

function gearStatusLabel(status) {
  if (status === 'verified') return 'SimC-ready'
  if (status === 'partial') return '缺字段'
  return '不可计算'
}

function gearStatusClass(status) {
  if (status === 'verified') return 'verified'
  if (status === 'partial') return 'partial'
  return 'blocked'
}

function statWeightStatusLabel(status) {
  if (status === 'verified') return '已验证'
  if (status === 'partial') return '部分可用'
  if (status === 'stale') return '缓存过期'
  return '暂不可用'
}

function statWeightScenarios(activeDetail) {
  const scenarios = activeDetail && Array.isArray(activeDetail.scenarioWeights) ? activeDetail.scenarioWeights : []
  if (scenarios.length) return scenarios
  const stats = activeDetail && Array.isArray(activeDetail.stats) ? activeDetail.stats : []
  if (!stats.length) return []
  return [{
    scenarioKey: 'legacy',
    scenarioTitle: activeDetail.title || '属性权重',
    scenarioLabel: '默认',
    sourceStatus: activeDetail.sourceStatus || 'source_reference',
    weights: stats,
    validation: activeDetail.validation || {},
    recommendationsZh: activeDetail.recommendationsZh || [],
    warningsZh: activeDetail.warningsZh || [],
    blockers: activeDetail.blockers || [],
    analysisWindow: activeDetail.analysisWindow || '',
    sourceNote: activeDetail.sourceNote || ''
  }]
}

function scenarioKeyOf(scenario) {
  return (scenario && (scenario.scenarioKey || scenario.key)) || ''
}

function selectedStatWeightScenario(activeDetail, scenarioKey) {
  const scenarios = statWeightScenarios(activeDetail)
  if (!scenarios.length) return null
  const defaultKey = scenarioKey || (activeDetail && activeDetail.defaultScenarioKey) || scenarioKeyOf(scenarios[0])
  return scenarios.find((item) => scenarioKeyOf(item) === defaultKey) || scenarios[0]
}

function listFromScenario(scenario, key) {
  const values = scenario && Array.isArray(scenario[key]) ? scenario[key] : []
  return values.filter((item) => item)
}

function selectedGearItems(selectedGearBySlot) {
  return Object.keys(selectedGearBySlot || {})
    .sort()
    .map((slot) => selectedGearBySlot[slot])
    .filter((item) => item && item.slot)
}

function selectedSimcItems(selectedGearBySlot) {
  return selectedGearItems(selectedGearBySlot).filter((item) => item.simcReady)
}

function gearTemplateLine(item) {
  const slot = item && (item.simcSlot || item.slot)
  const itemId = item && (item.itemId || item.id)
  if (!slot || !itemId) return ''
  const fields = [
    `${slot}=`,
    `id=${itemId}`,
    item.ilevel ? `ilevel=${item.ilevel}` : '',
    item.bonus_id ? `bonus_id=${item.bonus_id}` : '',
    item.gem_id ? `gem_id=${item.gem_id}` : '',
    item.gem_bonus_id ? `gem_bonus_id=${item.gem_bonus_id}` : '',
    item.gem_ilevel ? `gem_ilevel=${item.gem_ilevel}` : '',
    item.enchant_id ? `enchant_id=${item.enchant_id}` : '',
    item.crafted_stats ? `crafted_stats=${item.crafted_stats}` : ''
  ].filter(Boolean)
  return fields.join(',')
}

function canonicalGearTemplateLines(selectedGearBySlot) {
  return selectedSimcItems(selectedGearBySlot).map(gearTemplateLine).filter(Boolean)
}

function gearTemplateStatus(selectedItems, simcLines) {
  if (!selectedItems.length || !simcLines.length) {
    return { status: 'blocked', statusLabel: '不可计算' }
  }
  if (simcLines.length === selectedItems.length) {
    return { status: 'simc_ready', statusLabel: 'SimC-ready' }
  }
  return { status: 'partial', statusLabel: '缺字段' }
}

function gearTemplateTitle(className, specName, scenarioTitle) {
  const specLabel = `${specName || ''}${className || ''}`.trim() || '装备模板'
  return scenarioTitle ? `${specLabel} · ${scenarioTitle}` : specLabel
}

function gearScenarioAt(index) {
  return gearTemplateScenarios[Math.max(0, Math.min(Number(index) || 0, gearTemplateScenarios.length - 1))] || gearTemplateScenarios[0]
}

function equippedSetToSelection(equippedSet) {
  const selection = {}
  Object.keys(equippedSet || {}).forEach((slot) => {
    if (equippedSet[slot]) selection[slot] = equippedSet[slot]
  })
  return selection
}

function gearGroupsBySlot(payload) {
  const groups = {}
  const sourceGroups = (payload && (payload.replacementCandidates || payload.slotGroups)) || []
  sourceGroups.forEach((group) => {
    const slot = group.slot || group.simcSlot
    if (slot) groups[slot] = group
  })
  return groups
}

function gearCandidateKey(item, slot, index) {
  const itemId = item.itemId || item.id || item.name || index
  return [
    item.slot || slot,
    itemId,
    item.variantKey || item.defaultVariantKey || '',
    item.ilevel || '',
    item.bonus_id || '',
    item.gem_id || '',
    item.gem_bonus_id || '',
    item.gem_ilevel || '',
    item.enchant_id || '',
    item.crafted_stats || ''
  ].join('-')
}

function gearCandidateSources(item) {
  return item && Array.isArray(item.sources) ? item.sources : []
}

function gearCandidateSourceLabel(item) {
  const sources = gearCandidateSources(item)
  if (sources.length) return sources[0].label || sources[0].sourceLabel || ''
  return (item && (item.source || item.sourceName || item.encounterName || item.instanceName)) || ''
}

function gearCandidateSourceType(item) {
  const sources = gearCandidateSources(item)
  const sourceType = (sources[0] && sources[0].sourceType) || (item && item.sourceType) || ''
  const normalized = String(sourceType || '').toLowerCase()
  if (normalized.includes('raid')) return 'raid'
  if (normalized.includes('craft')) return 'crafted'
  if (normalized.includes('dungeon') || normalized.includes('loot')) return 'dungeon'
  return normalized || 'other'
}

function gearCandidateMatchesFilter(item, filterKey) {
  if (!filterKey || filterKey === 'all') return true
  if (filterKey === 'recommended') {
    return Number(item.recommendationScore || 0) > 0 || !!item.selected || !!item.simcReady
  }
  return gearCandidateSourceType(item) === filterKey
}

function gearOptionKey(option, index) {
  return (option && (option.id || option.key || option.name)) || `option-${index}`
}

function decorateVariantOptions(candidate, selectedKey) {
  const variants = Array.isArray(candidate && candidate.variants) ? candidate.variants : []
  return variants.map((variant, index) => {
    const key = variant.key || variant.variantKey || `variant-${index}`
    return {
      ...variant,
      key,
      selected: key === selectedKey,
      statusClass: gearStatusClass(variant.status || 'partial')
    }
  })
}

function decorateModOptions(options, selectedId) {
  return (Array.isArray(options) ? options : []).map((option, index) => {
    const id = gearOptionKey(option, index)
    return {
      ...option,
      id,
      selected: id === selectedId,
      statusClass: gearStatusClass(option.status || 'partial')
    }
  })
}

function candidateVariant(candidate, variantKey) {
  const variants = Array.isArray(candidate && candidate.variants) ? candidate.variants : []
  if (!variants.length) return null
  const defaultKey = variantKey || candidate.defaultVariantKey || candidate.variantKey || variants[0].key || variants[0].variantKey
  return variants.find((variant) => (variant.key || variant.variantKey) === defaultKey) || variants[0]
}

function selectedGearModOption(options, selectedId) {
  const normalized = Array.isArray(options) ? options : []
  if (!normalized.length || !selectedId) return null
  return normalized.find((option, index) => gearOptionKey(option, index) === selectedId) || null
}

function applySimcOptions(target, options) {
  Object.keys(options || {}).forEach((key) => {
    const value = options[key]
    if (value !== undefined && value !== null && value !== '') {
      target[key] = value
    }
  })
}

function appliedGearCandidate(candidate, variantKey, socketOptionId, enchantOptionId) {
  if (!candidate) return null
  const variant = candidateVariant(candidate, variantKey)
  const socket = selectedGearModOption(candidate.socketOptions, socketOptionId)
  const enchant = selectedGearModOption(candidate.enchantOptions, enchantOptionId)
  const selected = {
    ...candidate,
    selected: undefined,
    statusClass: undefined,
    statusLabel: undefined,
    reason: undefined
  }
  if (variant) {
    selected.variantKey = variant.key || variant.variantKey || ''
    selected.variantLabel = variant.label || ''
    selected.difficultyKey = variant.difficultyKey || selected.difficultyKey || ''
    selected.sourceType = variant.sourceType || selected.sourceType || ''
    if (variant.itemLevel || variant.ilevel) selected.ilevel = variant.itemLevel || variant.ilevel
    applySimcOptions(selected, variant.simcOptions)
  }
  if (socket) {
    selected.socketOptionId = socket.id
    selected.socketOptionLabel = socket.name || socket.label || ''
    applySimcOptions(selected, socket.simcOptions)
  }
  if (enchant) {
    selected.enchantOptionId = enchant.id
    selected.enchantOptionLabel = enchant.name || enchant.label || ''
    applySimcOptions(selected, enchant.simcOptions)
  }
  const hasSimcMod = !!(selected.bonus_id || selected.gem_id || selected.enchant_id || selected.crafted_stats)
  selected.simcReady = !!(selected.slot && (selected.itemId || selected.id) && selected.ilevel && hasSimcMod)
  selected.missingFields = selected.simcReady ? [] : [
    !selected.ilevel ? 'ilevel' : '',
    !hasSimcMod ? 'bonus_id/gem_id/enchant_id' : ''
  ].filter(Boolean)
  return selected
}

function gearModSummary(item) {
  const parts = []
  if (item && item.socketOptionLabel) parts.push(item.socketOptionLabel)
  if (item && item.enchantOptionLabel) parts.push(item.enchantOptionLabel)
  return parts.join(' / ')
}

function emptyGearSlotSheet() {
  return {
    visible: false,
    slot: '',
    label: '',
    item: null,
    filterKey: 'recommended',
    filters: gearCandidateFilters,
    candidates: [],
    allCandidates: [],
    selectedCandidateIndex: 0,
    activeCandidate: null,
    appliedCandidate: null,
    variantKey: '',
    socketOptionId: '',
    enchantOptionId: '',
    variantOptions: [],
    socketOptions: [],
    enchantOptions: []
  }
}

function buildGearSlotSheet(slot, row, allCandidates, options) {
  const config = options || {}
  const filterKey = config.filterKey || 'recommended'
  const filtered = allCandidates.filter((item) => gearCandidateMatchesFilter(item, filterKey))
  const candidates = filtered.length || filterKey === 'all' ? filtered : allCandidates
  const selectedCandidateIndex = Math.max(0, Math.min(Number(config.candidateIndex) || 0, Math.max(candidates.length - 1, 0)))
  const activeCandidate = candidates[selectedCandidateIndex] || null
  const defaultVariant = candidateVariant(activeCandidate, config.variantKey)
  const variantKey = (defaultVariant && (defaultVariant.key || defaultVariant.variantKey)) || ''
  const socketOptionId = config.socketOptionId || ''
  const enchantOptionId = config.enchantOptionId || ''
  const appliedCandidate = appliedGearCandidate(activeCandidate, variantKey, socketOptionId, enchantOptionId)
  return {
    visible: true,
    slot,
    label: (row && row.label) || slot,
    item: row,
    filterKey,
    filters: gearCandidateFilters.map((filter) => ({
      ...filter,
      active: filter.key === filterKey,
      count: filter.key === 'all'
        ? allCandidates.length
        : allCandidates.filter((item) => gearCandidateMatchesFilter(item, filter.key)).length
    })),
    candidates: candidates.map((candidate, index) => ({
      ...candidate,
      selected: index === selectedCandidateIndex
    })),
    allCandidates,
    selectedCandidateIndex,
    activeCandidate,
    appliedCandidate,
    variantKey,
    socketOptionId,
    enchantOptionId,
    variantOptions: decorateVariantOptions(activeCandidate, variantKey),
    socketOptions: decorateModOptions(activeCandidate && activeCandidate.socketOptions, socketOptionId),
    enchantOptions: decorateModOptions(activeCandidate && activeCandidate.enchantOptions, enchantOptionId)
  }
}

function buildGearCandidateRows(slot, payload, selectedGearBySlot) {
  const groups = gearGroupsBySlot(payload)
  const group = groups[slot] || { items: [] }
  const selected = (selectedGearBySlot || {})[slot]
  const rawItems = Array.isArray(group.items) ? group.items.slice(0) : []
  if (selected && !rawItems.some((item) => String(item.itemId || item.id || '') === String(selected.itemId || selected.id || ''))) {
    rawItems.unshift(selected)
  }
  const seen = new Set()
  return rawItems.map((item, index) => {
    const key = gearCandidateKey(item, slot, index)
    if (seen.has(key)) return null
    seen.add(key)
    const isSelected = selected && String(selected.itemId || selected.id || '') === String(item.itemId || item.id || '')
    const missingFields = Array.isArray(item.missingFields) ? item.missingFields : []
    return attachGearGameAsset({
      ...item,
      key,
      slot: item.slot || slot,
      displayName: itemDisplayName(item),
      iconUrl: item.iconUrl || '',
      source: gearCandidateSourceLabel(item),
      sourceType: gearCandidateSourceType(item),
      variantLabel: item.variantLabel || '',
      modSummary: gearModSummary(item),
      statusLabel: gearStatusLabel(item.simcReady ? 'verified' : (missingFields.length ? 'partial' : 'blocked')),
      statusClass: gearStatusClass(item.simcReady ? 'verified' : (missingFields.length ? 'partial' : 'blocked')),
      reason: item.simcReady ? '可写入 SimC profile' : (missingFields.length ? `缺 ${missingFields.join(' / ')}` : '缺 SimC 字段'),
      selected: !!isSelected
    }, 'gear-candidate')
  }).filter(Boolean)
}

function buildGearSlotRows(payload, selectedGearBySlot) {
  const slots = payload && Array.isArray(payload.slots) ? payload.slots : []
  const readiness = (payload && payload.slotReadiness) || {}
  const groups = gearGroupsBySlot(payload)
  const selection = selectedGearBySlot || {}
  return slots.map((slotMeta) => {
    const slot = slotMeta.slot || slotMeta.simcSlot || slotMeta.key
    const item = selection[slot] || ((payload.equippedSet || {})[slot]) || {}
    const slotState = readiness[slot] || {}
    const status = item.simcReady ? 'verified' : (slotState.status || 'blocked')
    return attachGearGameAsset({
      slot,
      label: slotMeta.label || slot,
      displayName: itemDisplayName(item),
      iconUrl: item.iconUrl || '',
      itemId: item.itemId || item.id || '',
      ilevel: item.ilevel || '',
      source: gearCandidateSourceLabel(item),
      sourceType: item.sourceType || '',
      variantLabel: item.variantLabel || '',
      modSummary: gearModSummary(item),
      status,
      statusLabel: gearStatusLabel(status),
      statusClass: gearStatusClass(status),
      reason: slotState.reason || (item.simcReady ? '可写入 SimC profile' : '等待 SimC 字段'),
      candidateCount: buildGearCandidateRows(slot, payload, selection).length
    }, 'gear-slot')
  })
}

function buildGearStatBlockers(snapshot, readiness) {
  const blockers = snapshot && Array.isArray(snapshot.blockers) ? snapshot.blockers : []
  if (blockers.length) return blockers
  const warnings = readiness && Array.isArray(readiness.warnings) ? readiness.warnings : []
  return warnings
}

function gearStatStatusText(snapshot) {
  if (snapshot && snapshot.statStatus === 'verified') return `已验证满级属性 · ${snapshot.maxLevel || ''}`
  return '属性快照 blocked'
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
  const currentState = state || {}
  const baseTalents = talentDetail && Array.isArray(talentDetail.coreTalents) ? talentDetail.coreTalents : []
  const activeTalentScenarioKey = currentState.activeTalentScenarioKey || talentScenarios[0].key
  const selectedTalentNodes = Array.isArray(currentState.selectedTalentNodes)
    ? currentState.selectedTalentNodes.filter((name) => baseTalents.includes(name))
    : baseTalents.slice(0, 4)
  const talentNodeRows = buildTalentNodeRows(talentDetail, selectedTalentNodes)
  const talentScenario = talentScenarios.find((item) => item.key === activeTalentScenarioKey) || talentScenarios[0]
  const talentSimulationSummary = buildTalentSimulationSummary(talentDetail, talentScenario.key, selectedTalentNodes)
  const gearPayload = currentState.gearPayload || null
  const selectedGearBySlot = currentState.selectedGearBySlot || {}
  const gearStatSnapshot = currentState.gearStatSnapshot || (gearPayload && gearPayload.statSnapshot) || defaultGearStatSnapshot()
  const gearReadiness = currentState.gearReadiness || (gearPayload && gearPayload.readiness) || {}
  const gearSlotRows = buildGearSlotRows(gearPayload, selectedGearBySlot)
  const statWeightScenario = selectedStatWeightScenario(activeDetail, currentState.activeStatWeightScenarioKey)
  const activeStatRows = statWeightScenario && Array.isArray(statWeightScenario.weights)
    ? statWeightScenario.weights
    : ((activeDetail && Array.isArray(activeDetail.stats)) ? activeDetail.stats : [])
  const statWeightValidation = (statWeightScenario && statWeightScenario.validation) || {}
  const statWeightBlockers = [
    ...listFromScenario(statWeightScenario, 'blockers'),
    ...listFromScenario(statWeightValidation, 'blockers')
  ].filter((item, index, list) => list.indexOf(item) === index)

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
    gearPayload,
    selectedGearBySlot,
    gearSlotRows,
    gearReadiness,
    gearStatSnapshot,
    gearStatBlockers: buildGearStatBlockers(gearStatSnapshot, gearReadiness),
    gearStatStatusText: gearStatStatusText(gearStatSnapshot),
    gearSimcItems: selectedSimcItems(selectedGearBySlot),
    statWeightScenarios: statWeightScenarios(activeDetail),
    activeStatWeightScenario: statWeightScenario,
    activeStatWeightScenarioKey: scenarioKeyOf(statWeightScenario),
    activeStatRows,
    statWeightStatusLabel: statWeightStatusLabel(statWeightScenario && statWeightScenario.sourceStatus),
    statWeightValidation,
    statWeightBlockers,
    statWeightRecommendations: listFromScenario(statWeightScenario, 'recommendationsZh'),
    statWeightWarnings: listFromScenario(statWeightScenario, 'warningsZh')
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
    gearTemplateScenarios,
    selectedGearTemplateScenarioIndex: 0,
    ...createSelectionState(defaultSelection.classIndex, defaultSelection.specIndex, 'talents'),
    loading: false,
    gearLoading: false,
    gearStatsLoading: false,
    gearTemplateSaving: false,
    gearRequestError: '',
    gearSelectionKey: '',
    gearSlotSheet: emptyGearSlotSheet(),
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
    if (queryKey === 'talents' && typeof wx !== 'undefined' && typeof wx.redirectTo === 'function') {
      wx.redirectTo({
        url: `/pages/builds/talent-simulator?spec=${encodeURIComponent(specId)}`
      })
      return
    }
    const selection = findSpecSelection(specId)
    const selectionState = createSelectionState(selection.classIndex, selection.specIndex, queryKey)
    this.setData({
      activeQueryKey: queryKey,
      activeQuery: findQuery(queryKey),
      ...selectionState
    })
    this.loadRemoteHome()
    this.loadSelectedDetail(selectionState.selectedSpec && selectionState.selectedSpec.id)
    if (queryKey === 'gear') {
      this.loadWebsimGearForSelection(selectionState)
    }
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
    if (this.data.activeQueryKey === 'gear') {
      this.loadWebsimGearForSelection(selectionState)
    }
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
    if (this.data.activeQueryKey === 'gear') {
      this.loadWebsimGearForSelection(selectionState)
    }
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

  loadWebsimGearForSelection(selectionState) {
    const selectedSpec = (selectionState && selectionState.selectedSpec) || this.data.selectedSpec || {}
    const keys = specWebsimKeys(selectedSpec)
    const selectionKey = `${keys.classKey}:${keys.specKey}`
    const existingSelection = this.data.gearSelectionKey === selectionKey ? (this.data.selectedGearBySlot || {}) : {}
    this.setData({
      gearLoading: true,
      gearRequestError: '',
      gearSelectionKey: selectionKey,
      gearSlotSheet: emptyGearSlotSheet()
    })
    requestWebsimGear(keys).then(({ payload, error }) => {
      if (this.data.gearSelectionKey !== selectionKey) return
      const baselineSelection = equippedSetToSelection(payload.equippedSet || {})
      const selectedGearBySlot = {
        ...baselineSelection,
        ...existingSelection
      }
      const gearStatSnapshot = payload.statSnapshot || defaultGearStatSnapshot()
      const gearReadiness = payload.readiness || {}
      const derivedState = createDetailDerivedState(this.data.selectedDetail, this.data.activeQueryKey, {
        ...this.data,
        gearPayload: payload,
        selectedGearBySlot,
        gearReadiness,
        gearStatSnapshot
      })
      this.setData({
        ...derivedState,
        gearLoading: false,
        gearRequestError: error || ''
      })
      this.refreshGearStats()
    }).catch((error) => {
      this.setData({
        gearLoading: false,
        gearRequestError: error.message || String(error)
      })
    })
  },

  refreshGearStats() {
    const keys = specWebsimKeys(this.data.selectedSpec || {})
    const gearItems = selectedGearItems(this.data.selectedGearBySlot || {})
    const talentState = this.data.websimTalentState || {}
    const talentImport = (this.data.talentSimulatorState && this.data.talentSimulatorState.importCode) || ''
    const scenario = gearScenarioAt(this.data.selectedGearTemplateScenarioIndex)
    this.setData({ gearStatsLoading: true })
    return requestWebsimGearStats({
      classKey: keys.classKey,
      specKey: keys.specKey,
      talents: talentImport,
      talentState,
      scenarioKey: scenario.key,
      level: (this.data.gearPayload && this.data.gearPayload.maxLevel) || undefined,
      gearSelection: {
        items: gearItems
      }
    }).then(({ payload, error }) => {
      const gearReadiness = payload.gearReadiness || this.data.gearReadiness || {}
      const derivedState = createDetailDerivedState(this.data.selectedDetail, this.data.activeQueryKey, {
        ...this.data,
        gearStatSnapshot: payload,
        gearReadiness
      })
      this.setData({
        ...derivedState,
        gearStatsLoading: false,
        gearRequestError: error || this.data.gearRequestError || ''
      })
    }).catch((error) => {
      const gearStatSnapshot = defaultGearStatSnapshot(error.message || String(error))
      const derivedState = createDetailDerivedState(this.data.selectedDetail, this.data.activeQueryKey, {
        ...this.data,
        gearStatSnapshot
      })
      this.setData({
        ...derivedState,
        gearStatsLoading: false,
        gearRequestError: error.message || String(error)
      })
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
          selectedGearBySlot: this.data.selectedGearBySlot || {},
          selectedItems: selectedGearItems(this.data.selectedGearBySlot || {}),
          simcItems: this.data.gearSimcItems || [],
          readiness: this.data.gearReadiness || {},
          statSnapshot: this.data.gearStatSnapshot || defaultGearStatSnapshot()
        },
        statWeights: {
          scenarioKey: this.data.activeStatWeightScenarioKey || '',
          scenarioTitle: (this.data.activeStatWeightScenario && this.data.activeStatWeightScenario.scenarioTitle) || '',
          sourceStatus: (this.data.activeStatWeightScenario && this.data.activeStatWeightScenario.sourceStatus) || '',
          validation: this.data.statWeightValidation || {},
          weights: this.data.activeStatRows || [],
          recommendationsZh: this.data.statWeightRecommendations || [],
          warningsZh: this.data.statWeightWarnings || []
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

  openGearSlotSheet(event) {
    const slot = event.currentTarget.dataset.slot || ''
    if (!slot) return
    const row = (this.data.gearSlotRows || []).find((item) => item.slot === slot) || {}
    const candidates = buildGearCandidateRows(slot, this.data.gearPayload || {}, this.data.selectedGearBySlot || {})
    this.setData({
      gearSlotSheet: buildGearSlotSheet(slot, row, candidates, { filterKey: 'recommended' })
    })
  },

  closeGearSlotSheet() {
    this.setData({
      gearSlotSheet: emptyGearSlotSheet()
    })
  },

  setGearCandidateFilter(event) {
    const filterKey = event.currentTarget.dataset.key || 'all'
    const sheet = this.data.gearSlotSheet || {}
    if (!sheet.slot) return
    this.setData({
      gearSlotSheet: buildGearSlotSheet(sheet.slot, sheet.item || {}, sheet.allCandidates || sheet.candidates || [], {
        filterKey,
        candidateIndex: 0
      })
    })
  },

  selectGearCandidate(event) {
    const index = Number(event.currentTarget.dataset.index || 0)
    const sheet = this.data.gearSlotSheet || {}
    if (!sheet.slot) return
    this.setData({
      gearSlotSheet: buildGearSlotSheet(sheet.slot, sheet.item || {}, sheet.allCandidates || sheet.candidates || [], {
        filterKey: sheet.filterKey || 'all',
        candidateIndex: index
      })
    })
  },

  selectGearVariant(event) {
    const key = event.currentTarget.dataset.key || ''
    const sheet = this.data.gearSlotSheet || {}
    if (!sheet.slot) return
    this.setData({
      gearSlotSheet: buildGearSlotSheet(sheet.slot, sheet.item || {}, sheet.allCandidates || sheet.candidates || [], {
        filterKey: sheet.filterKey || 'all',
        candidateIndex: sheet.selectedCandidateIndex || 0,
        variantKey: key,
        socketOptionId: sheet.socketOptionId || '',
        enchantOptionId: sheet.enchantOptionId || ''
      })
    })
  },

  selectGearSocketOption(event) {
    const id = event.currentTarget.dataset.id || ''
    const sheet = this.data.gearSlotSheet || {}
    if (!sheet.slot) return
    this.setData({
      gearSlotSheet: buildGearSlotSheet(sheet.slot, sheet.item || {}, sheet.allCandidates || sheet.candidates || [], {
        filterKey: sheet.filterKey || 'all',
        candidateIndex: sheet.selectedCandidateIndex || 0,
        variantKey: sheet.variantKey || '',
        socketOptionId: id,
        enchantOptionId: sheet.enchantOptionId || ''
      })
    })
  },

  selectGearEnchantOption(event) {
    const id = event.currentTarget.dataset.id || ''
    const sheet = this.data.gearSlotSheet || {}
    if (!sheet.slot) return
    this.setData({
      gearSlotSheet: buildGearSlotSheet(sheet.slot, sheet.item || {}, sheet.allCandidates || sheet.candidates || [], {
        filterKey: sheet.filterKey || 'all',
        candidateIndex: sheet.selectedCandidateIndex || 0,
        variantKey: sheet.variantKey || '',
        socketOptionId: sheet.socketOptionId || '',
        enchantOptionId: id
      })
    })
  },

  applyGearCandidate() {
    const sheet = this.data.gearSlotSheet || {}
    const slot = sheet.slot || ''
    const candidate = sheet.appliedCandidate || appliedGearCandidate(sheet.activeCandidate, sheet.variantKey, sheet.socketOptionId, sheet.enchantOptionId)
    if (!slot || !candidate) return Promise.resolve()
    const selectedGearBySlot = {
      ...(this.data.selectedGearBySlot || {}),
      [slot]: candidate
    }
    trackEvent('builds_gear_candidate_select', {
      gearSlot: slot,
      itemId: candidate.itemId || candidate.id || '',
      variantKey: candidate.variantKey || '',
      simcReady: !!candidate.simcReady,
      specId: (this.data.selectedSpec && this.data.selectedSpec.id) || ''
    }, { page: 'pages/builds/detail' })
    const derivedState = createDetailDerivedState(this.data.selectedDetail, this.data.activeQueryKey, {
      ...this.data,
      selectedGearBySlot
    })
    this.setData({
      ...derivedState,
      gearSlotSheet: emptyGearSlotSheet()
    })
    return this.refreshGearStats() || Promise.resolve()
  },

  selectGearTemplateScenario(event) {
    const index = Number(event.detail.value) || 0
    this.setData({
      selectedGearTemplateScenarioIndex: Math.max(0, Math.min(index, gearTemplateScenarios.length - 1))
    }, () => {
      this.refreshGearStats()
    })
  },

  saveGearTemplate() {
    const selectedItems = selectedGearItems(this.data.selectedGearBySlot || {})
    const simcLines = canonicalGearTemplateLines(this.data.selectedGearBySlot || {})
    const status = gearTemplateStatus(selectedItems, simcLines)
    if (!selectedItems.length) {
      showToast('暂无可保存的装备')
      return
    }
    if (!simcLines.length) {
      showToast('缺少 SimC-ready 装备')
      return
    }
    const scenario = gearScenarioAt(this.data.selectedGearTemplateScenarioIndex)
    const selectedDetail = this.data.selectedDetail || {}
    const selectedSpec = this.data.selectedSpec || {}
    const keys = specWebsimKeys(selectedSpec)
    syncBuildTemplate({
      type: 'gear',
      title: gearTemplateTitle(
        selectedDetail.className || selectedSpec.className || '',
        selectedDetail.specName || selectedSpec.title || selectedSpec.specName || '',
        scenario.title
      ),
      classKey: keys.classKey,
      className: selectedDetail.className || selectedSpec.className || '',
      specKey: keys.specKey,
      specName: selectedDetail.specName || selectedSpec.title || selectedSpec.specName || '',
      scenarioKey: scenario.key,
      scenarioTitle: scenario.title,
      rawString: simcLines.join('\n'),
      simcLines,
      status: status.status,
      statusLabel: status.statusLabel,
      source: '装备模拟器',
      metadata: {
        selectedGearSnapshot: this.data.selectedGearBySlot || {},
        selectedItems,
        simcReadyCount: simcLines.length,
        selectedItemCount: selectedItems.length,
        readiness: this.data.gearReadiness || {},
        statSnapshot: this.data.gearStatSnapshot || defaultGearStatSnapshot(),
        gearSchemaRevision: this.data.gearPayload && this.data.gearPayload.gearSchemaRevision,
        maxLevel: this.data.gearPayload && this.data.gearPayload.maxLevel
      }
    }).then(({ payload }) => {
      showToast(payload && payload.template ? '装备模板已保存' : '装备模板保存失败')
    }).catch(() => {
      showToast('装备模板保存失败')
    })
  },

  setTalentScenario(event) {
    const key = event.currentTarget.dataset.key || talentScenarios[0].key
    trackEvent('builds_talent_scenario_select', {
      scenarioKey: key,
      specId: (this.data.selectedSpec && this.data.selectedSpec.id) || ''
    }, { page: 'pages/builds/detail' })
    this.refreshDerivedState({ activeTalentScenarioKey: key })
  },

  setStatWeightScenario(event) {
    const key = event.currentTarget.dataset.key || ''
    if (!key) return
    trackEvent('builds_stat_weight_scenario_select', {
      scenarioKey: key,
      specId: (this.data.selectedSpec && this.data.selectedSpec.id) || ''
    }, { page: 'pages/builds/detail' })
    this.refreshDerivedState({ activeStatWeightScenarioKey: key })
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
