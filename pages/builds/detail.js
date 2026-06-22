const {
  fallbackBuildsDetail,
  fallbackBuildsHome,
  requestBuildsDetail,
  requestBuildsHome
} = require('./builds-api')
const {
  requestWebsimGear
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
  { key: 'all', label: '全部' },
  { key: 'dungeon', label: '大秘境' },
  { key: 'raid', label: '团本' }
]
const maxGearTemplateTitleLength = 28
const gearClassLabels = {
  deathknight: '死亡骑士',
  demonhunter: '恶魔猎手',
  druid: '德鲁伊',
  evoker: '唤魔师',
  hunter: '猎人',
  mage: '法师',
  monk: '武僧',
  paladin: '圣骑士',
  priest: '牧师',
  rogue: '潜行者',
  shaman: '萨满祭司',
  warlock: '术士',
  warrior: '战士'
}
const gearSpecLabels = {
  arcane: '奥术',
  fire: '火焰',
  frost: '冰霜',
  holy: '神圣',
  protection: '防护',
  retribution: '惩戒',
  elemental: '元素',
  enhancement: '增强',
  restoration: '恢复',
  arms: '武器',
  fury: '狂怒',
  blood: '鲜血',
  unholy: '邪恶',
  havoc: '浩劫',
  vengeance: '复仇',
  balance: '平衡',
  feral: '野性',
  guardian: '守护',
  devastation: '湮灭',
  preservation: '恩护',
  augmentation: '增辉',
  beast_mastery: '野兽控制',
  marksmanship: '射击',
  survival: '生存',
  brewmaster: '酒仙',
  mistweaver: '织雾',
  windwalker: '踏风',
  discipline: '戒律',
  shadow: '暗影',
  assassination: '奇袭',
  outlaw: '狂徒',
  subtlety: '敏锐',
  affliction: '痛苦',
  demonology: '恶魔学识',
  destruction: '毁灭'
}
const gearHeroLabels = {
  deathbringer: '死亡使者',
  rider_of_the_apocalypse: '天启骑士',
  sanlayn: '萨莱茵',
  aldrachi_reaver: '奥达奇掠夺者',
  fel_scarred: '邪痕者',
  annihilator: '歼灭者',
  void_scarred: '虚痕者',
  keeper_of_the_grove: '丛林守护者',
  wildstalker: '野性追猎者',
  elunes_chosen: '艾露恩钦选者',
  druid_of_the_claw: '利爪德鲁伊',
  flameshaper: '塑焰者',
  scalecommander: '鳞长',
  chronowarden: '时空守卫',
  dark_ranger: '黑暗游侠',
  pack_leader: '兽群领袖',
  sentinel: '哨兵',
  spellslinger: '法术投射者',
  sunfury: '日怒',
  frostfire: '霜火',
  conduit_of_the_celestials: '天神御师',
  master_of_harmony: '和谐宗师',
  shado_pan: '影踪派',
  herald_of_the_sun: '旭日使者',
  lightsmith: '铸光者',
  templar: '圣殿骑士',
  oracle: '神谕者',
  voidweaver: '虚空编织者',
  archon: '执政官',
  deathstalker: '死亡猎手',
  fatebound: '命缚者',
  trickster: '欺诈者',
  farseer: '先知',
  stormbringer: '风暴使者',
  totemic: '图腾祭司',
  hellcaller: '地狱召唤者',
  soul_harvester: '灵魂收割者',
  diabolist: '恶魔学家',
  colossus: '巨像',
  mountain_thane: '山丘领主',
  slayer: '屠戮者'
}
const gearCommunitySourceLabels = {
  simc_preset: 'SimC 预设',
  observed_profile: 'Raider.IO 观测',
  raiderio_observed: 'Raider.IO 观测',
  raiderio: 'Raider.IO 观测'
}

const requiredGearSlots = [
  'head', 'neck', 'shoulder', 'back', 'chest', 'wrist', 'hands', 'waist',
  'legs', 'feet', 'finger1', 'finger2', 'trinket1', 'trinket2', 'main_hand', 'off_hand'
]
const gearSlotDisplayLabels = {
  head: '头部',
  neck: '项链',
  shoulder: '肩部',
  back: '披风',
  chest: '胸部',
  wrist: '护腕',
  hands: '手套',
  waist: '腰带',
  legs: '腿部',
  feet: '脚部',
  finger1: '戒指 1',
  finger2: '戒指 2',
  trinket1: '饰品 1',
  trinket2: '饰品 2',
  main_hand: '主手',
  off_hand: '副手'
}

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

function gearSlotDisplay(slot) {
  return `${gearSlotDisplayLabels[slot] || slot}(${slot})`
}

function normalizedGearItemId(item) {
  const rawId = item && (item.itemId || item.item_id || item.id)
  const itemId = String(rawId || '').trim()
  return /^\d+$/.test(itemId) ? itemId : ''
}

function stringList(values) {
  return (Array.isArray(values) ? values : [])
    .map((value) => String(value || '').trim())
    .filter(Boolean)
}

function localizedGearIssue(value) {
  const text = String(value || '').trim()
  const normalized = text.toLowerCase()
  if (!text) return ''
  if (normalized.includes('deterministic simc variant')) return '缺少确定 SimC 变体'
  if (normalized.includes('bonus_id/gem_id/enchant_id')) return '缺少 bonus/宝石/附魔'
  if (normalized.includes('missing item id') || normalized === 'itemid' || normalized === 'item id') return '缺少物品 ID'
  if (normalized.includes('item level') || normalized === 'ilevel' || normalized === 'itemlevel') return '缺少装等'
  if (normalized.includes('variantkey') || normalized === 'variant key') return '缺少变体'
  if (normalized === 'slot') return '缺少槽位'
  if (normalized.includes('observed gear source is not verified')) return '观测来源未验证'
  if (normalized.includes('crafted variant missing deterministic simc options')) return '制造变体缺少确定 SimC 字段'
  if (normalized.includes('missing item')) return '缺少装备'
  return text
}

function localizedGearIssues(values) {
  const seen = new Set()
  return stringList(values)
    .map(localizedGearIssue)
    .filter((item) => {
      if (!item || seen.has(item)) return false
      seen.add(item)
      return true
    })
}

function gearIssueText(values, fallback) {
  const issues = localizedGearIssues(values)
  if (issues.length) return issues.join('；')
  return localizedGearIssue(fallback || '')
}

function isSourceReferenceGear(item) {
  const statusValues = [
    item && item.status,
    item && item.sourceStatus,
    item && item.metadataStatus,
    item && item.sourceType,
    item && item.variantSource
  ].map((value) => String(value || '').toLowerCase())
  return !!(item && (item.isReference || statusValues.includes('source_reference') || statusValues.includes('source-reference')))
}

function gearTrustState(item, fallbackStatus, fallbackReason) {
  const blockers = stringList((item && item.blockers) || [])
  const missingFields = stringList((item && item.missingFields) || [])
  const sourceReference = isSourceReferenceGear(item)
  let status = fallbackStatus || ''
  if (sourceReference) {
    status = 'source-reference'
  } else if (item && item.simcReady) {
    status = 'verified'
  } else if (status === 'blocked') {
    status = 'blocked'
  } else if (missingFields.length || status === 'partial') {
    status = 'partial'
  } else if (blockers.length) {
    status = 'blocked'
  } else {
    status = 'blocked'
  }

  if (status === 'verified') {
    return {
      status,
      label: '可保存',
      reason: '具备 canonical 槽位、物品 ID 和可执行字段。',
      blockerLabel: ''
    }
  }
  if (status === 'source-reference') {
    const details = gearIssueText(blockers.length ? blockers : missingFields, fallbackReason)
    return {
      status,
      label: '来源参考',
      reason: ['仅作为来源参考，不可直接保存为装备模板。', details].filter(Boolean).join(' '),
      blockerLabel: details || '来源参考不可直接导入'
    }
  }
  if (status === 'partial') {
    const details = gearIssueText(missingFields, fallbackReason || '缺少可执行装备字段')
    return {
      status,
      label: '缺字段',
      reason: `${details}，保存前需补齐。`,
      blockerLabel: details
    }
  }
  const details = gearIssueText(blockers, fallbackReason || '缺少可执行装备字段')
  return {
    status: 'blocked',
    label: '阻断',
    reason: details,
    blockerLabel: details
  }
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
  if (status === 'verified') return '已配置'
  if (status === 'source-reference') return '来源参考'
  if (status === 'partial') return '缺字段'
  return '不可计算'
}

function gearStatusClass(status) {
  if (status === 'verified') return 'verified'
  if (status === 'source-reference') return 'source-reference'
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

function gearTemplateLine(item) {
  const slot = item && (item.simcSlot || item.slot)
  const itemId = normalizedGearItemId(item)
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

function selectedGearByCanonicalSlot(selectedGearBySlot) {
  const indexed = {}
  Object.keys(selectedGearBySlot || {}).forEach((slotKey) => {
    const item = selectedGearBySlot[slotKey]
    const slot = item && (item.simcSlot || item.slot || slotKey)
    if (!slot || !item) return
    indexed[slot] = {
      ...item,
      slot: item.slot || slot,
      simcSlot: item.simcSlot || slot
    }
  })
  return indexed
}

function canonicalGearTemplateLines(selectedGearBySlot) {
  const indexed = selectedGearByCanonicalSlot(selectedGearBySlot)
  return requiredGearSlots.map((slot) => gearTemplateLine(indexed[slot])).filter(Boolean)
}

function missingGearConfigSlots(selectedGearBySlot) {
  const indexed = selectedGearByCanonicalSlot(selectedGearBySlot)
  return requiredGearSlots.filter((slot) => !gearTemplateLine(indexed[slot]))
}

function gearTemplateValidationIssues(selectedGearBySlot) {
  const indexed = selectedGearByCanonicalSlot(selectedGearBySlot)
  return requiredGearSlots.map((slot) => {
    const item = indexed[slot]
    if (!item) {
      return { slot, message: `${gearSlotDisplay(slot)} 缺少装备` }
    }
    if (isSourceReferenceGear(item)) {
      return { slot, message: `${gearSlotDisplay(slot)} 是来源参考，不能保存为可执行模板` }
    }
    if (!normalizedGearItemId(item)) {
      return { slot, message: `${gearSlotDisplay(slot)} 缺少可执行物品 ID` }
    }
    if (!gearTemplateLine(item)) {
      return { slot, message: `${gearSlotDisplay(slot)} 缺少可保存字段` }
    }
    return null
  }).filter(Boolean)
}

function gearTemplateValidationMessage(issues) {
  const list = Array.isArray(issues) ? issues : []
  if (!list.length) return ''
  const details = list.slice(0, 3).map((item) => item.message).join('；')
  const more = list.length > 3 ? `；另有 ${list.length - 3} 个槽位` : ''
  const hasMissingSlot = list.some((item) => /缺少装备/.test(item.message))
  return `${hasMissingSlot ? '请补齐 16 个装备槽位' : '请先修正装备槽位'}：${details}${more}`
}

function gearTemplateStatus(selectedGearBySlot) {
  const issues = gearTemplateValidationIssues(selectedGearBySlot)
  if (issues.length) {
    return { status: 'partial', statusLabel: '缺字段', missingSlots: issues.map((item) => item.slot), issues }
  }
  return { status: 'complete', statusLabel: '完整配置', missingSlots: [], issues: [] }
}

function cleanGearTemplateTitlePart(value, fallback, maxLength) {
  const text = String(value || fallback || '')
    .replace(/\s+/g, '')
    .replace(/[·|｜]/g, '-')
    .replace(/^-+|-+$/g, '')
    .trim()
  if (!text) return ''
  return text.length > maxLength ? text.slice(0, maxLength) : text
}

function compactGearTemplateTime(date) {
  const current = date instanceof Date && !Number.isNaN(date.getTime()) ? date : new Date()
  const month = String(current.getMonth() + 1).padStart(2, '0')
  const day = String(current.getDate()).padStart(2, '0')
  const hour = String(current.getHours()).padStart(2, '0')
  const minute = String(current.getMinutes()).padStart(2, '0')
  return `${month}${day} ${hour}${minute}`
}

function gearTemplateTitle(className, specName, scenarioTitle) {
  const time = compactGearTemplateTime()
  const prefix = [
    cleanGearTemplateTitlePart(className, '职业', 6),
    cleanGearTemplateTitlePart(specName, '专精', 6),
    cleanGearTemplateTitlePart(scenarioTitle, '场景', 8)
  ].filter(Boolean).join('-') || '装备'
  const maxPrefixLength = Math.max(4, maxGearTemplateTitleLength - time.length - 1)
  const shortPrefix = prefix.length > maxPrefixLength ? prefix.slice(0, maxPrefixLength) : prefix
  return `${shortPrefix}-${time}`
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

function emptyGearCommunityTemplateSheet() {
  return { visible: false }
}

function gearItemsToSelection(items) {
  const selection = {}
  ;(items || []).forEach((item) => {
    const slot = item && (item.simcSlot || item.slot)
    if (!slot || !requiredGearSlots.includes(slot)) return
    selection[slot] = {
      ...item,
      slot: item.slot || slot,
      simcSlot: item.simcSlot || slot
    }
  })
  return selection
}

function gearCommunityStatusLabel(status) {
  if (status === 'source-reference' || status === 'source_reference') return '来源参考'
  if (status === 'complete') return '完整配置'
  if (status === 'synced' || status === 'verified') return '已验证'
  if (status === 'partial') return '部分可用'
  if (status === 'blocked' || status === 'missing_credentials') return '暂不可用'
  return '待同步'
}

function gearCommunityTemplateCardClass(template) {
  const status = template && (template.status || template.sourceStatus)
  const sourceStatus = template && template.sourceStatus
  if (status === 'source-reference' || status === 'source_reference' || sourceStatus === 'source_reference' || sourceStatus === 'source-reference') return 'source-reference'
  if (status === 'complete' || status === 'synced' || status === 'verified') return 'complete'
  if (status === 'partial') return 'partial'
  return 'blocked'
}

function normalizeGearTemplateKey(value) {
  return String(value || '')
    .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
    .replace(/[^a-zA-Z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .toLowerCase()
}

function matchedGearLabel(template, labels, explicitKey) {
  const key = normalizeGearTemplateKey(explicitKey)
  if (key && labels[key]) return labels[key]
  const haystack = normalizeGearTemplateKey([
    template && template.id,
    template && template.name,
    template && template.sourceName
  ].filter(Boolean).join('_'))
  const matchedKey = Object.keys(labels)
    .sort((left, right) => right.length - left.length)
    .find((item) => haystack.includes(item))
  return matchedKey ? labels[matchedKey] : ''
}

function gearCommunitySourceDisplayName(template) {
  const sourceKey = normalizeGearTemplateKey(template && (template.sourceKey || template.sourceType || template.provider))
  if (sourceKey && gearCommunitySourceLabels[sourceKey]) return gearCommunitySourceLabels[sourceKey]
  const rawName = String((template && template.sourceName) || '').trim()
  const normalizedName = rawName.toLowerCase()
  if (normalizedName.includes('simc') && normalizedName.includes('preset')) return 'SimC 预设'
  if (/raider\.?io/.test(normalizedName) && (normalizedName.includes('observed') || normalizedName.includes('gear'))) {
    return 'Raider.IO 观测'
  }
  return rawName || '社区装备'
}

function gearCommunityTemplateDisplayName(template) {
  const classLabel = (template && template.classLabel) || matchedGearLabel(template, gearClassLabels, template && template.classKey)
  const specLabel = (template && template.specLabel) || matchedGearLabel(template, gearSpecLabels, template && template.specKey)
  const heroLabel = (template && template.heroLabel) || matchedGearLabel(template, gearHeroLabels, template && template.heroKey)
  const sourceName = gearCommunitySourceDisplayName(template)
  const profileLabel = [classLabel, specLabel, heroLabel].filter(Boolean).join('-')
  const rawName = String((template && template.name) || '').trim()
  return [profileLabel || rawName || '社区装备模板', sourceName].filter(Boolean).join(' · ')
}

function decorateGearCommunityTemplate(template) {
  const gearSelection = gearItemsToSelection((template && template.gearItems) || [])
  const gearItems = requiredGearSlots.map((slot) => gearSelection[slot]).filter(Boolean)
  const readySlotCount = Number((template && template.readySlotCount) || gearItems.length || 0)
  const missingSlots = Array.isArray(template && template.missingSlots)
    ? template.missingSlots
    : requiredGearSlots.filter((slot) => !gearSelection[slot])
  const status = (template && template.status) || (missingSlots.length ? 'partial' : 'complete')
  const sourceStatus = (template && template.sourceStatus) || status
  const sourceReference = status === 'source_reference' || status === 'source-reference' || sourceStatus === 'source_reference' || sourceStatus === 'source-reference'
  const normalizedStatus = sourceReference ? 'source-reference' : status
  const normalizedSourceStatus = sourceReference ? 'source-reference' : sourceStatus
  const blockers = stringList((template && template.blockers) || ((template && template.payload) || {}).blockers)
  const canApplyGear = !!(template && template.canApplyGear !== false && readySlotCount > 0 && !sourceReference && normalizedStatus !== 'blocked' && normalizedSourceStatus !== 'blocked')
  const displaySourceName = gearCommunitySourceDisplayName(template)
  const blockerLabel = blockers[0] || (sourceReference ? '仅作为来源参考，不可直接导入' : '')
  return {
    ...(template || {}),
    status: normalizedStatus,
    sourceStatus: normalizedSourceStatus,
    gearItems,
    readySlotCount,
    missingSlots,
    canApplyGear,
    displayName: gearCommunityTemplateDisplayName(template),
    displaySourceName,
    statusLabel: gearCommunityStatusLabel(normalizedStatus),
    sourceStatusLabel: gearCommunityStatusLabel(normalizedSourceStatus),
    slotCoverageLabel: `已覆盖 ${readySlotCount}/${requiredGearSlots.length} 槽`,
    missingSlotLabel: missingSlots.length ? `缺 ${missingSlots.length} 槽` : '16 槽完整',
    blockerLabel,
    updatedLabel: (template && template.updatedAt) || '',
    actionLabel: canApplyGear ? '应用' : '不可导入',
    cardClass: gearCommunityTemplateCardClass({ status: normalizedStatus, sourceStatus: normalizedSourceStatus })
  }
}

function gearCommunityTemplatesForPayload(payload) {
  const templates = payload && Array.isArray(payload.communityTemplates) ? payload.communityTemplates : []
  return templates.map(decorateGearCommunityTemplate)
}

function gearCommunitySyncSummary(syncState, templates) {
  const status = syncState && syncState.sourceStatus
  if (Array.isArray(templates) && templates.length) {
    return `社区模板 ${templates.length} 个 · ${gearCommunityStatusLabel(status)}`
  }
  return '暂无可导入装备模板'
}

function gearDataWarningText(error, payload, fromFallback) {
  if (error === 'missing api base url') {
    return '未连接后端 API，当前只是空槽位兜底，无法读取真实装备和社区模板。'
  }
  if (error) {
    return `装备接口请求失败：${error}。当前只是空槽位兜底。`
  }
  if (fromFallback || (payload && payload.dataStatus === 'blocked')) {
    return '装备接口暂不可用，当前只是空槽位兜底。'
  }
  return ''
}

function gearTrustSummaryText(payload, selectedGearBySlot) {
  if (!payload) return ''
  const status = gearTemplateStatus(selectedGearBySlot || {})
  const readyCount = requiredGearSlots.length - status.missingSlots.length
  const catalogStatus = gearCommunityStatusLabel((payload.catalogStatus || payload.dataStatus || '').replace('_', '-'))
  if (status.issues.length) {
    return `当前配置 ${readyCount}/${requiredGearSlots.length} 槽可保存；${gearTemplateValidationMessage(status.issues)}。装备库：${catalogStatus}`
  }
  return `当前配置 16/16 槽完整；装备库：${catalogStatus}`
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
  return gearCandidateSourceType(item) === filterKey
}

function gearOptionKey(option, index) {
  return (option && (option.id || option.key || option.name)) || `option-${index}`
}

function gearVariantDifficultyLabel(variant) {
  const explicit = variant && (variant.difficultyLabel || variant.difficultyName)
  if (explicit) return explicit
  const key = String((variant && (variant.difficultyKey || variant.sourceType)) || '').toLowerCase().replace(/[-\s]+/g, '_')
  const labels = {
    normal: '普通',
    heroic: '英雄',
    mythic: '史诗',
    lfr: '随机',
    raid_finder: '随机',
    mythic_plus: '大秘境',
    dungeon: '大秘境',
    raid: '团本',
    observed_profile: '实装观测',
    needs_variant: '难度待补'
  }
  if (labels[key]) return labels[key]
  const label = String((variant && variant.label) || '')
  if (/heroic|英雄/i.test(label)) return '英雄'
  if (/mythic\+|mythic plus|大秘境/i.test(label)) return '大秘境'
  if (/mythic|史诗|神话/i.test(label)) return '史诗'
  if (/normal|普通/i.test(label)) return '普通'
  if (/raid finder|lfr|随机/i.test(label)) return '随机'
  if (/select difficulty|待补/i.test(label)) return '难度待补'
  return label || '难度待补'
}

function gearVariantLevelLabel(variant) {
  const rawLevel = variant && (variant.itemLevel || variant.ilevel)
  const level = Number(rawLevel || 0)
  return level > 0 ? `装等 ${level}` : ''
}

function decorateVariantOptions(candidate, selectedKey) {
  const variants = Array.isArray(candidate && candidate.variants) ? candidate.variants : []
  return variants.map((variant, index) => {
    const key = variant.key || variant.variantKey || `variant-${index}`
    return {
      ...variant,
      key,
      displayLabel: gearVariantDifficultyLabel(variant),
      levelLabel: gearVariantLevelLabel(variant),
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
    selected.variantLabel = gearVariantDifficultyLabel(variant) || variant.label || ''
    selected.variantDifficultyLabel = gearVariantDifficultyLabel(variant)
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

function gearDropSourceText(item) {
  const labels = gearCandidateSources(item)
    .map((source) => source && (source.label || source.sourceLabel || source.encounterName || source.instanceName))
    .filter(Boolean)
  const fallback = item && (item.source || item.sourceName || [item.instanceName, item.encounterName].filter(Boolean).join(' · '))
  const values = stringList(labels.length ? labels : [fallback])
  const seen = new Set()
  return values.filter((value) => {
    if (seen.has(value)) return false
    seen.add(value)
    return true
  }).slice(0, 3).join('；') || '来源待补充'
}

function gearStatLabel(label) {
  const normalized = String(label || '').trim().toLowerCase()
  const labels = {
    intellect: '智力',
    int: '智力',
    agility: '敏捷',
    agi: '敏捷',
    strength: '力量',
    str: '力量',
    stamina: '耐力',
    sta: '耐力',
    crit: '暴击',
    critical_strike: '暴击',
    haste: '急速',
    mastery: '精通',
    versatility: '全能',
    armor: '护甲',
    avoidance: '闪避',
    leech: '吸血',
    speed: '速度'
  }
  return labels[normalized] || String(label || '').trim()
}

function gearStatText(stat) {
  if (!stat) return ''
  if (typeof stat === 'string') return stat.trim()
  if (typeof stat !== 'object') return ''
  const label = gearStatLabel(stat.label || stat.name || stat.stat || stat.key || stat.type)
  const value = stat.value !== undefined && stat.value !== null && stat.value !== ''
    ? stat.value
    : (stat.amount || stat.rating || stat.displayValue || stat.text || '')
  if (label && value) return `${label} ${value}`
  return label || String(value || '').trim()
}

function gearAttributeText(item) {
  if (item && item.statSummary) return String(item.statSummary).trim()
  const statSources = [
    item && item.stats,
    item && item.itemStats,
    item && item.attributes,
    item && item.secondaryStats
  ]
  const parts = []
  statSources.forEach((stats) => {
    if (Array.isArray(stats)) {
      stats.map(gearStatText).filter(Boolean).forEach((text) => parts.push(text))
    }
  })
  if (!parts.length && item && item.ilevel) parts.push(`装等 ${item.ilevel}`)
  const seen = new Set()
  return parts.filter((value) => {
    if (!value || seen.has(value)) return false
    seen.add(value)
    return true
  }).join('；') || '属性待补充'
}

function gearCandidateDetailRows(item) {
  const rows = []
  rows.push({ label: '掉落来源', value: gearDropSourceText(item) })
  rows.push({ label: '装备属性', value: gearAttributeText(item) })
  return rows
}

function emptyGearSlotSheet() {
  return {
    visible: false,
    slot: '',
    label: '',
    item: null,
    filterKey: 'all',
    filters: gearCandidateFilters,
    candidates: [],
    allCandidates: [],
    selectedCandidateIndex: 0,
    detailKey: '',
    emptyText: '',
    activeCandidate: null,
    appliedCandidate: null,
    variantKey: '',
    socketOptionId: '',
    enchantOptionId: '',
    variantOptions: [],
    socketOptions: [],
    enchantOptions: [],
    activeTrustLabel: '',
    activeTrustText: '',
    canApplyCandidate: false
  }
}

function buildGearSlotSheet(slot, row, allCandidates, options) {
  const config = options || {}
  const filterKey = config.filterKey || 'all'
  const filtered = allCandidates.filter((item) => gearCandidateMatchesFilter(item, filterKey))
  const candidates = filtered
  const selectedCandidateIndex = Math.max(0, Math.min(Number(config.candidateIndex) || 0, Math.max(candidates.length - 1, 0)))
  const activeCandidate = candidates[selectedCandidateIndex] || null
  const defaultVariant = candidateVariant(activeCandidate, config.variantKey)
  const variantKey = (defaultVariant && (defaultVariant.key || defaultVariant.variantKey)) || ''
  const socketOptionId = config.socketOptionId || ''
  const enchantOptionId = config.enchantOptionId || ''
  const appliedCandidate = appliedGearCandidate(activeCandidate, variantKey, socketOptionId, enchantOptionId)
  const activeTrust = gearTrustState(appliedCandidate || activeCandidate, activeCandidate && activeCandidate.statusClass, activeCandidate && activeCandidate.reason)
  const canApplyCandidate = !!(appliedCandidate && appliedCandidate.simcReady && gearTemplateLine(appliedCandidate))
  const detailKey = candidates.some((item) => item.key === config.detailKey) ? config.detailKey : ''
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
      selected: index === selectedCandidateIndex,
      detailOpen: candidate.key === detailKey
    })),
    allCandidates,
    selectedCandidateIndex,
    detailKey,
    emptyText: candidates.length ? '' : '该来源暂无候选装备',
    activeCandidate,
    appliedCandidate,
    variantKey,
    socketOptionId,
    enchantOptionId,
    variantOptions: decorateVariantOptions(activeCandidate, variantKey),
    socketOptions: decorateModOptions(activeCandidate && activeCandidate.socketOptions, socketOptionId),
    enchantOptions: decorateModOptions(activeCandidate && activeCandidate.enchantOptions, enchantOptionId),
    activeTrustLabel: activeTrust.label,
    activeTrustText: activeTrust.reason,
    canApplyCandidate
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
    const trust = gearTrustState(item, item.simcReady ? 'verified' : (missingFields.length ? 'partial' : 'blocked'), item.reason)
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
      statusLabel: gearStatusLabel(trust.status),
      statusClass: gearStatusClass(trust.status),
      detailRows: gearCandidateDetailRows(item, trust),
      trustLabel: trust.label,
      trustReason: trust.reason,
      blockerLabel: trust.blockerLabel,
      reason: trust.reason,
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
    const trust = gearTrustState(item, status, slotState.reason || (item.simcReady ? '可保存为配置' : '等待装备配置字段'))
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
      status: trust.status,
      statusLabel: gearStatusLabel(trust.status),
      statusClass: gearStatusClass(trust.status),
      trustLabel: trust.label,
      trustReason: trust.reason,
      blockerLabel: trust.blockerLabel,
      reason: trust.reason,
      candidateCount: buildGearCandidateRows(slot, payload, selection).length
    }, 'gear-slot')
  })
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
  const gearDataFallback = !!(currentState.gearDataFallback || (gearPayload && gearPayload.dataStatus === 'blocked'))
  const selectedGearBySlot = currentState.selectedGearBySlot || {}
  const gearReadiness = currentState.gearReadiness || (gearPayload && gearPayload.readiness) || {}
  const gearSlotRows = buildGearSlotRows(gearPayload, selectedGearBySlot)
  const gearInitialLoading = !!(currentState.gearLoading && !gearSlotRows.length)
  const activeGearCommunityTemplates = gearCommunityTemplatesForPayload(gearPayload)
  const gearCommunityTemplateSync = (gearPayload && gearPayload.communityTemplateSync) || {}
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
    gearDataFallback,
    gearDataWarningText: gearDataWarningText(currentState.gearRequestError || '', gearPayload, gearDataFallback),
    gearTrustSummaryText: gearTrustSummaryText(gearPayload, selectedGearBySlot),
    selectedGearBySlot,
    gearSlotRows,
    gearInitialLoading,
    gearReadiness,
    activeGearCommunityTemplates,
    gearCommunityTemplateSync,
    gearCommunityTemplateStatusText: gearCommunitySyncSummary(gearCommunityTemplateSync, activeGearCommunityTemplates),
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
    gearInitialLoading: false,
    gearStatsLoading: false,
    gearTemplateSaving: false,
    gearRequestError: '',
    gearDataFallback: false,
    gearDataWarningText: '',
    gearSelectionKey: '',
    gearSlotSheet: emptyGearSlotSheet(),
    gearCommunityTemplateSheet: emptyGearCommunityTemplateSheet(),
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
    const hasExistingRows = Array.isArray(this.data.gearSlotRows) && this.data.gearSlotRows.length > 0
    this.setData({
      gearLoading: true,
      gearInitialLoading: !hasExistingRows,
      gearRequestError: '',
      gearDataFallback: false,
      gearDataWarningText: '',
      gearSelectionKey: selectionKey,
      gearSlotSheet: emptyGearSlotSheet(),
      gearCommunityTemplateSheet: emptyGearCommunityTemplateSheet()
    })
    requestWebsimGear(keys).then(({ payload, error, fromFallback }) => {
      if (this.data.gearSelectionKey !== selectionKey) return
      const baselineSelection = equippedSetToSelection(payload.equippedSet || {})
      const selectedGearBySlot = {
        ...baselineSelection,
        ...existingSelection
      }
      const gearDataFallback = !!fromFallback
      const gearReadiness = payload.readiness || {}
      const derivedState = createDetailDerivedState(this.data.selectedDetail, this.data.activeQueryKey, {
        ...this.data,
        gearPayload: payload,
        selectedGearBySlot,
        gearReadiness,
        gearDataFallback,
        gearRequestError: error || ''
      })
      this.setData({
        ...derivedState,
        gearLoading: false,
        gearInitialLoading: false,
        gearRequestError: error || '',
        gearDataFallback,
        gearDataWarningText: gearDataWarningText(error || '', payload, gearDataFallback)
      })
    }).catch((error) => {
      this.setData({
        gearLoading: false,
        gearInitialLoading: false,
        gearRequestError: error.message || String(error),
        gearDataFallback: true,
        gearDataWarningText: gearDataWarningText(error.message || String(error), null, true)
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
      simulatorState: {
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
      gearSlotSheet: buildGearSlotSheet(slot, row, candidates, { filterKey: 'all' })
    })
  },

  closeGearSlotSheet() {
    this.setData({
      gearSlotSheet: emptyGearSlotSheet()
    })
  },

  openGearCommunityTemplates() {
    if (this.data.gearDataFallback) {
      showToast(this.data.gearDataWarningText || '装备接口暂不可用，无法导入社区模板')
      return
    }
    this.refreshDerivedState()
    this.setData({
      gearCommunityTemplateSheet: { visible: true },
      gearSlotSheet: emptyGearSlotSheet()
    })
  },

  closeGearCommunityTemplates() {
    this.setData({
      gearCommunityTemplateSheet: emptyGearCommunityTemplateSheet()
    })
  },

  resetGearSelection() {
    const gearPayload = this.data.gearPayload
    if (!gearPayload) {
      this.loadWebsimGearForSelection()
      return
    }
    const selectedGearBySlot = equippedSetToSelection(gearPayload.equippedSet || {})
    const derivedState = createDetailDerivedState(this.data.selectedDetail, this.data.activeQueryKey, {
      ...this.data,
      selectedGearBySlot
    })
    this.setData({
      ...derivedState,
      gearSlotSheet: emptyGearSlotSheet(),
      gearCommunityTemplateSheet: emptyGearCommunityTemplateSheet()
    })
    trackEvent('builds_gear_selection_reset', {
      specId: (this.data.selectedSpec && this.data.selectedSpec.id) || ''
    }, { page: 'pages/builds/detail' })
  },

  applyGearCommunityTemplate(event) {
    const templateId = event.currentTarget.dataset.id || ''
    const templates = this.data.activeGearCommunityTemplates || gearCommunityTemplatesForPayload(this.data.gearPayload || {})
    const template = templates.find((item) => item.id === templateId)
    if (!template || !template.canApplyGear) {
      showToast('当前模板暂不可导入')
      return
    }
    const baselineSelection = equippedSetToSelection((this.data.gearPayload && this.data.gearPayload.equippedSet) || {})
    const templateSelection = gearItemsToSelection(template.gearItems || [])
    const selectedGearBySlot = {
      ...baselineSelection,
      ...templateSelection
    }
    const derivedState = createDetailDerivedState(this.data.selectedDetail, this.data.activeQueryKey, {
      ...this.data,
      selectedGearBySlot
    })
    this.setData({
      ...derivedState,
      gearSlotSheet: emptyGearSlotSheet(),
      gearCommunityTemplateSheet: emptyGearCommunityTemplateSheet()
    })
    trackEvent('builds_gear_community_template_apply', {
      templateId,
      readySlotCount: template.readySlotCount || Object.keys(templateSelection).length,
      specId: (this.data.selectedSpec && this.data.selectedSpec.id) || ''
    }, { page: 'pages/builds/detail' })
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
        candidateIndex: index,
        detailKey: sheet.detailKey || ''
      })
    })
  },

  toggleGearCandidateDetail(event) {
    const index = Number(event.currentTarget.dataset.index || 0)
    const sheet = this.data.gearSlotSheet || {}
    const candidates = sheet.candidates || []
    const candidate = candidates[index]
    if (!sheet.slot || !candidate) return
    const key = candidate.key || ''
    const detailKey = sheet.detailKey === key ? '' : key
    this.setData({
      gearSlotSheet: buildGearSlotSheet(sheet.slot, sheet.item || {}, sheet.allCandidates || candidates, {
        filterKey: sheet.filterKey || 'all',
        candidateIndex: sheet.selectedCandidateIndex || 0,
        variantKey: sheet.variantKey || '',
        socketOptionId: sheet.socketOptionId || '',
        enchantOptionId: sheet.enchantOptionId || '',
        detailKey
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
        enchantOptionId: sheet.enchantOptionId || '',
        detailKey: sheet.detailKey || ''
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
        enchantOptionId: sheet.enchantOptionId || '',
        detailKey: sheet.detailKey || ''
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
        enchantOptionId: id,
        detailKey: sheet.detailKey || ''
      })
    })
  },

  applyGearCandidate() {
    const sheet = this.data.gearSlotSheet || {}
    const slot = sheet.slot || ''
    const candidate = sheet.appliedCandidate || appliedGearCandidate(sheet.activeCandidate, sheet.variantKey, sheet.socketOptionId, sheet.enchantOptionId)
    if (!slot || !candidate) return Promise.resolve()
    if (!(candidate.simcReady && gearTemplateLine(candidate))) {
      const trust = gearTrustState(candidate, candidate.statusClass, candidate.reason)
      showToast(trust.blockerLabel || trust.reason || '该装备数据待补，暂不能应用')
      return Promise.resolve()
    }
    const selectedGearBySlot = {
      ...(this.data.selectedGearBySlot || {}),
      [slot]: candidate
    }
    trackEvent('builds_gear_candidate_select', {
      gearSlot: slot,
      itemId: candidate.itemId || candidate.id || '',
      variantKey: candidate.variantKey || '',
      configReady: !!gearTemplateLine(candidate),
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
    return Promise.resolve()
  },

  selectGearTemplateScenario(event) {
    const index = Number(event.detail.value) || 0
    this.setData({
      selectedGearTemplateScenarioIndex: Math.max(0, Math.min(index, gearTemplateScenarios.length - 1))
    })
  },

  saveGearTemplate() {
    if (this.data.gearDataFallback) {
      showToast(this.data.gearDataWarningText || '装备接口暂不可用，无法保存装备模板')
      return
    }
    const selectedItems = selectedGearItems(this.data.selectedGearBySlot || {})
    const configLines = canonicalGearTemplateLines(this.data.selectedGearBySlot || {})
    const status = gearTemplateStatus(this.data.selectedGearBySlot || {})
    if (status.missingSlots.length || configLines.length !== requiredGearSlots.length) {
      showToast(gearTemplateValidationMessage(status.issues) || '请补齐 16 个装备槽位后再保存')
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
      rawString: configLines.join('\n'),
      simcLines: [],
      status: status.status,
      statusLabel: status.statusLabel,
      source: '装备模拟器',
      metadata: {
        selectedGearSnapshot: this.data.selectedGearBySlot || {},
        selectedItems,
        configLineCount: configLines.length,
        missingSlots: [],
        selectedItemCount: selectedItems.length,
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

  openSimcWithBuildContext() {
    if (!this.data.selectedDetail || !this.data.activeDetail) return
    const context = this.buildSimcContext()
    trackEvent('builds_simc_entry_click', {
      queryKey: context.activeQueryKey || '',
      specId: context.specId || '',
      className: context.className || '',
      specName: context.specName || '',
      scenarioKey: (context.simulatorState && context.simulatorState.statWeights && context.simulatorState.statWeights.scenarioKey) || ''
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
