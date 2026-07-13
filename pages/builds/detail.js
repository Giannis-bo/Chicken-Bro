const {
  fallbackBuildsDetail,
  fallbackBuildsHome,
  requestBuildsDetail,
  requestBuildsHome
} = require('./builds-api')
const {
  requestWebsimGear,
  requestWebsimGearResolve,
  requestWebsimGearStatSnapshot,
  requestWebsimTalentImport
} = require('./websim-api')
const {
  applyGearResolveResult,
  applyGearStatSnapshotResult,
  beginGearStatSnapshot,
  beginGearResolve,
  confirmGearIntent,
  createGearWorkbenchState,
  createGearStatSnapshotState,
  editGearIntent,
  gearWorkbenchCanRunProfile,
  gearWorkbenchCanUseVerifiedSnapshot,
  gearWorkbenchView,
  gearStatRequestTimeoutMs,
  invalidateGearStatSnapshot,
  rebaseGearIntentRevisions
} = require('./gear-workbench-state')
const { completeResolverContext, serializeGearSelectionIntent } = require('./gear-selection-intent')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')
const { listBuildTemplates, syncBuildTemplate } = require('../common/build-template-storage')
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
    { key: 'single', title: '单体', label: '1目标', simcHint: '单体 5 分钟' },
    { key: 'aoe_5', title: '5目标AOE', label: '5目标', simcHint: '5目标 AOE' },
    { key: 'mythic_plus', title: '近似大秘境', label: 'DungeonSlice', simcHint: '近似大秘境' }
  ]
}
const talentScenarios = simulatorDefaults.talentScenarios
const gearTemplateScenarios = [
  { key: 'single', title: '单体' },
  { key: 'aoe_5', title: '5目标AOE' },
  { key: 'mythic_plus', title: '近似大秘境' },
  { key: 'raid', title: '团本' }
]
const GEAR_ENHANCEMENT_SNAPSHOT_REVISION = 'websim-gear-enhancement-snapshot-v1'
const gearEnhancementMax = 2
const gearTierSetMax = 5
const primaryStatGemUniqueGroup = 'primary_stat_gem'
const primaryStatGemUniqueLimit = 1
const primaryStatGemIds = new Set(['240967', '240969', '240971', '240983'])
const enchantableGearSlots = new Set(['back', 'chest', 'wrist', 'legs', 'feet', 'finger1', 'finger2', 'main_hand', 'off_hand'])
const governedEnchantFallbackSlots = new Set(['back', 'chest', 'legs', 'feet', 'finger1', 'finger2', 'main_hand', 'off_hand'])
const gearConfigEnchantExcludedCategories = new Set([
  'class_only_precombat',
  'class_only_weapon_enchant',
  'combat_preparation',
  'runeforge',
  'temporary_enchant'
])
const offhandWeaponEnchantTypes = new Set([
  'dagger',
  'fist weapon',
  'one-handed axe',
  'one-handed mace',
  'one-handed sword',
  'warglaive'
])
const twoHandWeaponTypes = new Set([
  'polearm',
  'staff',
  'two-handed axe',
  'two-handed mace',
  'two-handed sword'
])
const gearEmbellishmentArmorSlots = new Set(['head', 'shoulder', 'back', 'chest', 'wrist', 'hands', 'waist', 'legs', 'feet'])
const gearEmbellishmentJewelrySlots = new Set(['neck', 'finger1', 'finger2'])
const gearEmbellishmentEquipmentSlots = new Set([
  ...gearEmbellishmentArmorSlots,
  ...gearEmbellishmentJewelrySlots,
  'main_hand',
  'off_hand'
])
const gearEnhancementSlotOrder = ['neck', 'finger1', 'finger2', 'main_hand', 'off_hand']
const gearCandidateFilters = [
  { key: 'all', label: '全部' },
  { key: 'dungeon', label: '大秘境' },
  { key: 'raid', label: '团本' },
  { key: 'tier_set', label: '套装' },
  { key: 'crafted', label: '制造业' }
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
  devourer: '噬灭',
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
  raiderio: 'Raider.IO 观测',
  default_template: '默认模板'
}
const gearPrimaryStatLabels = {
  strength: '力量',
  agility: '敏捷',
  intellect: '智力'
}
const gearTrackedAttributeKeys = [
  'strength',
  'agility',
  'intellect',
  'stamina',
  'haste',
  'crit',
  'mastery',
  'versatility',
  'armor'
]

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

function normalizedGearKey(value) {
  return cleanGearString(value).replace(/-/g, '_').toLowerCase()
}

function primaryStatKeyForSpec(selectedSpec) {
  const keys = specWebsimKeys(selectedSpec || {})
  const classKey = normalizedGearKey(keys.classKey)
  const specKey = normalizedGearKey(keys.specKey)
  if (classKey === 'deathknight' || classKey === 'warrior') return 'strength'
  if (classKey === 'demonhunter' || classKey === 'hunter' || classKey === 'rogue') return 'agility'
  if (classKey === 'evoker' || classKey === 'mage' || classKey === 'priest' || classKey === 'warlock') return 'intellect'
  if (classKey === 'paladin') return specKey === 'holy' ? 'intellect' : 'strength'
  if (classKey === 'shaman') return specKey === 'enhancement' ? 'agility' : 'intellect'
  if (classKey === 'druid') return specKey === 'feral' || specKey === 'guardian' ? 'agility' : 'intellect'
  if (classKey === 'monk') return specKey === 'mistweaver' ? 'intellect' : 'agility'
  return 'intellect'
}

function gearNumericValue(value) {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  const text = cleanGearString(value).replace(/,/g, '')
  const match = text.match(/[+-]?\d+(?:\.\d+)?/)
  return match ? Number(match[0]) : null
}

function formatGearAttributeValue(value, fallback) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return fallback
  const rounded = Math.round(Number(value) * 10) / 10
  const text = Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1).replace(/\.0$/, '')
  return text.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

function gearAttributeMetric(key, label, value, fallback) {
  const rawValue = value === null || value === undefined ? null : Number(value)
  const displayValue = formatGearAttributeValue(rawValue, fallback)
  return {
    key,
    label,
    value: displayValue,
    rawValue,
    pending: displayValue === '待补'
  }
}

function verifiedGearStatSnapshot(snapshot) {
  if (!snapshot || typeof snapshot !== 'object') return null
  return snapshot.statStatus === 'verified' ? snapshot : null
}

function compactGearStatSnapshotMetric(row) {
  if (!row || typeof row !== 'object') return null
  const metric = {
    key: cleanGearString(row.key),
    label: cleanGearString(row.label),
    value: cleanGearString(row.value)
  }
  ;['rawValue', 'convertedValue', 'convertedRawValue', 'convertedSourceValue', 'convertedSourceUnit'].forEach((key) => {
    if (row[key] !== undefined && row[key] !== null && row[key] !== '') metric[key] = row[key]
  })
  return metric.value ? metric : null
}

function compactVerifiedGearStatSnapshot(snapshot) {
  const source = verifiedGearStatSnapshot(snapshot)
  if (!source) return null
  const secondary = Array.isArray(source.secondary)
    ? source.secondary.map(compactGearStatSnapshotMetric).filter(Boolean)
    : []
  return {
    statStatus: 'verified',
    statSource: cleanGearString(source.statSource),
    simcVersion: cleanGearString(source.simcVersion),
    checkedAt: cleanGearString(source.checkedAt),
    classKey: cleanGearString(source.classKey),
    specKey: cleanGearString(source.specKey),
    maxLevel: source.maxLevel || 0,
    primary: compactGearStatSnapshotMetric(source.primary),
    secondary,
    itemLevel: compactGearStatSnapshotMetric(source.itemLevel)
  }
}

function gearStatSnapshotMetric(snapshot, key) {
  const source = verifiedGearStatSnapshot(snapshot)
  if (!source) return null
  if (key === 'primary') return source.primary || null
  if (key === 'stamina') return source.stamina || null
  if (key === 'itemLevel') return source.itemLevel || null
  if (key === 'armor') return source.armor || null
  const secondary = Array.isArray(source.secondary) ? source.secondary : []
  return secondary.find((row) => row && row.key === key) || null
}

function gearAttributeMetricFromSnapshot(row, fallbackKey, fallbackLabel) {
  if (!row || typeof row !== 'object') return null
  const value = cleanGearString(row.value)
  if (!value) return null
  const metric = {
    key: row.key || fallbackKey,
    label: row.label || fallbackLabel,
    value,
    rawValue: row.rawValue === undefined ? gearNumericValue(value) : row.rawValue,
    pending: false
  }
  if (row.convertedValue) {
    metric.convertedValue = row.convertedValue
    metric.convertedRawValue = row.convertedRawValue
    metric.convertedSourceValue = row.convertedSourceValue
    metric.convertedSourceUnit = row.convertedSourceUnit
  }
  return metric
}

function gearAttributeMetricWithSnapshot(key, label, value, fallback, gearStatSnapshot) {
  const snapshotMetric = gearAttributeMetricFromSnapshot(gearStatSnapshotMetric(gearStatSnapshot, key), key, label)
  return snapshotMetric || gearAttributeMetric(key, label, value, fallback)
}

function gearEnhancementMetric(key, label, used, max) {
  const safeUsed = Math.max(0, Number(used) || 0)
  const safeMax = Math.max(0, Number(max) || 0)
  return {
    key,
    label,
    value: `${safeUsed}/${safeMax}`,
    used: safeUsed,
    max: safeMax,
    pending: false
  }
}

function emptyCommunityEnhancementImportState() {
  return {
    templateId: '',
    serial: 0,
    resolvedGearSignature: '',
    unresolvedBySlot: {},
    warnings: []
  }
}

function clearCommunityEnhancementImportState(page) {
  if (!page) return
  page.communityEnhancementImportState = emptyCommunityEnhancementImportState()
}

function eligibleCommunityEnhancementImportState(state, snapshot) {
  const current = state && typeof state === 'object' ? state : emptyCommunityEnhancementImportState()
  const snapshotSignature = cleanGearString(snapshot && snapshot.resolvedGearSignature)
  return !!(
    snapshotSignature &&
    cleanGearString(current.resolvedGearSignature) === snapshotSignature
  ) ? current : emptyCommunityEnhancementImportState()
}

function eligibleCommunityEnhancementImportStateForPage(page, snapshot) {
  const resolveStatus = cleanGearString(page && page.gearWorkbenchState && page.gearWorkbenchState.resolveStatus)
  if (['dirty', 'resolving', 'pending', 'revision_conflict'].includes(resolveStatus)) {
    return emptyCommunityEnhancementImportState()
  }
  return eligibleCommunityEnhancementImportState(
    page && page.communityEnhancementImportState,
    snapshot
  )
}

function inheritedEnhancementCountByType(state) {
  const counts = { gem: 0, enchant: 0, embellishment: 0 }
  Object.keys((state && state.unresolvedBySlot) || {}).forEach((slot) => {
    const record = state.unresolvedBySlot[slot] || {}
    counts.gem += Array.isArray(record.gemIds) ? record.gemIds.length : 0
    counts.enchant += Array.isArray(record.enchantIds) ? record.enchantIds.length : 0
    counts.embellishment += Array.isArray(record.embellishments) ? record.embellishments.length : 0
  })
  return counts
}

function withInheritedEnhancementCount(metric, inheritedCount) {
  const count = Math.max(0, Number(inheritedCount) || 0)
  if (!count) return metric
  return {
    ...metric,
    inheritedCount: count,
    inheritedLabel: `另有 ${count} 个已继承事实不可编辑`
  }
}

function gearItemIsTierSet(item) {
  if (!item || typeof item !== 'object') return false
  if (cleanGearString(item.itemSetName || item.setName || item.tierSetName)) return true
  const sourceValues = [
    item.sourceType,
    item.variantSource,
    ...(Array.isArray(item.sourceTypes) ? item.sourceTypes : []),
    ...(Array.isArray(item.sources) ? item.sources.map((source) => source && (source.sourceType || source.type)) : [])
  ].map((value) => cleanGearString(value).toLowerCase()).filter(Boolean)
  return sourceValues.some((value) => value.includes('tier') || value.includes('item_set'))
}

function gearTierSetIdentity(item) {
  return cleanGearString(item && (item.itemSetName || item.setName || item.tierSetName))
}

function gearTierSetCountForPanel(items) {
  const tierItems = (Array.isArray(items) ? items : []).filter((item) => gearItemIsTierSet(item))
  if (!tierItems.length) return 0
  const countsBySet = tierItems.reduce((memo, item) => {
    const setName = gearTierSetIdentity(item)
    if (setName) memo[setName] = (memo[setName] || 0) + 1
    return memo
  }, {})
  const namedCounts = Object.keys(countsBySet).map((key) => countsBySet[key])
  const count = namedCounts.length ? Math.max(...namedCounts) : tierItems.length
  return Math.min(count, gearTierSetMax)
}

function explicitGearCapabilityValue(caps, key) {
  if (!caps || typeof caps !== 'object' || !Object.prototype.hasOwnProperty.call(caps, key)) return null
  const value = caps[key]
  if (value === true || value === 1) return true
  if (value === false || value === 0) return false
  const text = cleanGearString(value).toLowerCase()
  if (['true', '1', 'yes'].includes(text)) return true
  if (['false', '0', 'no'].includes(text)) return false
  return value ? true : false
}

function gearItemIsHeldOffHand(item) {
  if (!item || typeof item !== 'object') return false
  const values = [
    item.weaponType,
    item.weaponSubType,
    item.inventoryType,
    item.inventory_type,
    item.inventorySlot,
    item.equipLocation,
    item.itemSubClass,
    item.itemSubclass,
    item.subclassName
  ].map((value) => cleanGearString(value).toLowerCase()).filter(Boolean)
  return values.some((value) => (
    value.includes('held in off-hand') ||
    value.includes('held in off hand') ||
    value.includes('held off-hand') ||
    value.includes('held off hand')
  ))
}

function gearItemSocketCapacity(item) {
  if (!item || typeof item !== 'object') return 0
  const capacity = gearSocketCapacityValue(item)
  if (capacity > 0) return capacity
  if (gearSocketCapacityHasExplicitValue(item)) return 0
  const caps = item.modCapabilities && typeof item.modCapabilities === 'object' ? item.modCapabilities : {}
  const explicit = explicitGearCapabilityValue(caps, 'hasSocket')
  return explicit === true || item.supportsSocket ? 1 : 0
}

function gearItemEnchantCapacity(item) {
  if (!item || typeof item !== 'object') return 0
  const { slot, armorType, weaponType } = gearItemTypeContext(item)
  if (!enchantableGearSlots.has(slot)) return 0
  if (slot !== 'off_hand') return 1
  if (!weaponType && !armorType) return 0
  if (weaponType === 'held in off-hand' || weaponType === 'shield' || armorType === 'shield') return 0
  if (weaponType && !offhandWeaponEnchantTypes.has(weaponType)) return 0
  return 1
}

function itemSupportsEnhancementMetric(gearPayload, item, type, optionKey) {
  if (!item || typeof item !== 'object') return false
  const caps = item.modCapabilities && typeof item.modCapabilities === 'object' ? item.modCapabilities : {}
  const capabilityKey = {
    gem: 'hasSocket',
    enchant: 'canEnchant',
    embellishment: 'canEmbellish'
  }[type]
  const explicitCapability = explicitGearCapabilityValue(caps, capabilityKey)
  const itemOptions = item && Array.isArray(item[optionKey]) ? item[optionKey] : []
  const payloadOptions = enhancementOptionsForSlot(gearPayload, item, optionKey)
  if (type === 'gem') {
    if (gearItemSocketCapacity(item) <= 0) return false
    if (explicitCapability !== null) return explicitCapability
    return !!(item.supportsSocket || itemOptions.length || payloadOptions.length)
  }
  if (type === 'enchant') {
    if (gearItemEnchantCapacity(item) <= 0) return false
    if (explicitCapability === false) return false
    if (itemOptions.length || payloadOptions.length) return true
    if (gearPayloadHasEnhancementOptions(gearPayload, optionKey)) return false
    const slot = cleanGearString(item.slot || item.simcSlot)
    return explicitCapability === true && governedEnchantFallbackSlots.has(slot)
  }
  if (explicitCapability !== null) return explicitCapability
  if (type === 'embellishment') {
    const sourceType = cleanGearString(item.sourceType).toLowerCase()
    const variantSource = cleanGearString(item.variantSource).toLowerCase()
    return !!(item.crafted_stats || item.embellishment || sourceType === 'crafted' || variantSource === 'crafted' || itemOptions.length || payloadOptions.length)
  }
  return false
}

function itemSupportsConfiguredEnhancementFallback(item, type) {
  if (!item || typeof item !== 'object') return false
  const caps = item.modCapabilities && typeof item.modCapabilities === 'object' ? item.modCapabilities : {}
  if (type === 'gem') {
    const explicit = explicitGearCapabilityValue(caps, 'hasSocket')
    if (explicit === false) return false
    return gearItemSocketCapacity(item) > 0 && !!(explicit || item.supportsSocket)
  }
  if (type === 'enchant') {
    const explicit = explicitGearCapabilityValue(caps, 'canEnchant')
    if (explicit === false) return false
    return gearItemEnchantCapacity(item) > 0 && !!(explicit || cleanGearString(item.enchant_id))
  }
  if (type === 'embellishment') {
    const explicit = explicitGearCapabilityValue(caps, 'canEmbellish')
    if (explicit === false) return false
    return !!(explicit || item.crafted_stats || item.embellishment || builtInEmbellishmentValue(item))
  }
  return false
}

function enhancementRecordHasSelectedType(record, type) {
  return enhancementRecordSelectedCount(record, type) > 0
}

function simcOptionValueCount(value) {
  const text = cleanGearString(value)
  if (!text) return 0
  return text.split(/[\/,;|\s]+/).map((part) => part.trim()).filter(Boolean).length
}

function numericCapacityValue(value) {
  if (Array.isArray(value)) return value.length
  if (value && typeof value === 'object') return Object.keys(value).length
  const number = Number(value)
  return Number.isFinite(number) && number > 0 ? number : 0
}

function gearSocketCapacityCandidates(item) {
  const caps = item && item.modCapabilities && typeof item.modCapabilities === 'object' ? item.modCapabilities : {}
  return [
    caps.socketCount,
    caps.socket_count,
    caps.gemSocketCount,
    caps.gem_socket_count,
    item && item.socketCount,
    item && item.socket_count,
    item && item.gemSocketCount,
    item && item.gem_socket_count,
    item && item.sockets,
    item && item.gemSockets
  ]
}

function gearSocketCapacityHasExplicitValue(item) {
  return gearSocketCapacityCandidates(item).some((value) => {
    if (Array.isArray(value)) return true
    if (value && typeof value === 'object') return true
    if (typeof value === 'number') return Number.isFinite(value)
    return cleanGearString(value) !== ''
  })
}

function gearSocketCapacityValue(item) {
  return gearSocketCapacityCandidates(item).reduce((max, value) => Math.max(max, numericCapacityValue(value)), 0)
}

function enhancementRecordSelectedCount(record, type) {
  if (!record || typeof record !== 'object') return 0
  if (type === 'gem') {
    return Math.max(
      normalizedOptionIdentityList(record.gemOptionIds).length,
      simcOptionValueCount(record.gem_id),
      cleanGearString(record.socketOptionId) ? 1 : 0,
      cleanGearString(record.gem_bonus_id) ? 1 : 0
    )
  }
  if (type === 'enchant') return cleanGearString(record.enchantOptionId) || cleanGearString(record.enchant_id) ? 1 : 0
  if (type === 'embellishment') return cleanGearString(record.embellishmentOptionId) || cleanGearString(record.embellishment) ? 1 : 0
  return 0
}

function itemEmbeddedEnhancementCount(item, type) {
  if (!item || typeof item !== 'object') return 0
  if (type === 'gem') {
    return Math.max(
      simcOptionValueCount(item.gem_id),
      simcOptionValueCount(item.gem_bonus_id),
      simcOptionValueCount(item.gem_ilevel)
    )
  }
  if (type === 'enchant') return cleanGearString(item.enchant_id) ? 1 : 0
  if (type === 'embellishment') return builtInEmbellishmentValue(item) || cleanGearString(item.embellishment) ? 1 : 0
  return 0
}

function gearEnhancementMetricCapacity(gearPayload, item, type, optionKey) {
  if (!item || typeof item !== 'object') return 0
  const embeddedCount = itemEmbeddedEnhancementCount(item, type)
  if (type === 'gem') {
    return itemSupportsEnhancementMetric(gearPayload, item, type, optionKey) ? gearItemSocketCapacity(item) : 0
  }
  if (type === 'enchant') {
    return itemSupportsEnhancementMetric(gearPayload, item, type, optionKey) ? gearItemEnchantCapacity(item) : 0
  }
  if (type === 'embellishment') {
    return Math.max(embeddedCount, itemSupportsEnhancementMetric(gearPayload, item, type, optionKey) ? 1 : 0)
  }
  return 0
}

function gearEnhancementMetricUsage(gearPayload, slots, indexed, enhancement, type, optionKey) {
  return (Array.isArray(slots) ? slots : []).reduce((memo, slot) => {
    const item = indexed && indexed[slot]
    let capacity = gearEnhancementMetricCapacity(gearPayload, item, type, optionKey)
    const selectedRecord = enhancement && enhancement[slot]
    const selectedCount = enhancementRecordMatchesCurrentItem(gearPayload, item, selectedRecord, optionKey, type)
      ? enhancementRecordSelectedCount(selectedRecord, type)
      : 0
    const embeddedCount = type === 'embellishment' ? itemEmbeddedEnhancementCount(item, type) : 0
    if (!capacity && selectedCount) capacity = selectedCount
    if (!capacity) return memo
    memo.max += capacity
    memo.used += Math.min(capacity, Math.max(
      embeddedCount,
      selectedCount
    ))
    return memo
  }, { used: 0, max: 0 })
}

function gearStatKeyForLabel(label, primaryKey) {
  const text = cleanGearString(label).toLowerCase()
  const compact = text.replace(/[\s/_-]+/g, '')
  if (!text) return ''
  if (text.includes('护甲') || text.includes('armor')) return 'armor'
  if (text.includes('耐力') || text.includes('stamina')) return 'stamina'
  if (text.includes('急速') || text.includes('haste')) return 'haste'
  if (text.includes('暴击') || text.includes('爆击') || text.includes('critical') || text.includes('crit')) return 'crit'
  if (text.includes('精通') || text.includes('mastery')) return 'mastery'
  if (text.includes('全能') || text.includes('versatility')) return 'versatility'
  if (text.includes('主属性') || text.includes('primary stat') || compact.includes('primarystat')) return primaryKey
  if ((text.includes('力量') && text.includes('敏捷') && text.includes('智力')) || compact.includes('stragiint')) return primaryKey
  if ((text.includes('strength') && text.includes('agility') && text.includes('intellect')) || compact.includes('strintagi')) return primaryKey
  if ((text.includes('力量') && text.includes('敏捷')) || compact.includes('stragi') || compact.includes('agistr')) return primaryKey === 'strength' || primaryKey === 'agility' ? primaryKey : ''
  if ((text.includes('力量') && text.includes('智力')) || compact.includes('strint') || compact.includes('intstr')) return primaryKey === 'strength' || primaryKey === 'intellect' ? primaryKey : ''
  if ((text.includes('敏捷') && text.includes('智力')) || compact.includes('agiint') || compact.includes('intagi')) return primaryKey === 'agility' || primaryKey === 'intellect' ? primaryKey : ''
  if (text.includes('agility') && text.includes('intellect')) return primaryKey === 'agility' || primaryKey === 'intellect' ? primaryKey : ''
  if (text.includes('力量') || text.includes('strength')) return 'strength'
  if (text.includes('敏捷') || text.includes('agility')) return 'agility'
  if (text.includes('智力') || text.includes('intellect')) return 'intellect'
  return ''
}

function gearStatEntriesFromSummary(summary, primaryKey) {
  const text = cleanGearString(summary)
  if (!text) return []
  return text.split(/[；;，,\n]+/).reduce((entries, rawPart) => {
    const part = rawPart.trim()
    if (!part) return entries
    const numberLeadingEntries = []
    const numberLeadingPattern = /([+-]?\d[\d,]*(?:\.\d+)?)\s*([^+\-\d；;,，\n]+)/g
    let tokenMatch = numberLeadingPattern.exec(part)
    while (tokenMatch) {
      const value = gearNumericValue(tokenMatch[1])
      const label = cleanGearString(tokenMatch[2]).replace(/[+：:]/g, ' ').trim()
      const key = gearStatKeyForLabel(label, primaryKey)
      if (key && value !== null) numberLeadingEntries.push({ key, value })
      tokenMatch = numberLeadingPattern.exec(part)
    }
    if (numberLeadingEntries.length) return entries.concat(numberLeadingEntries)
    const match = part.match(/[+-]?\d[\d,]*(?:\.\d+)?/)
    if (!match) return entries
    const value = gearNumericValue(match[0])
    if (value === null) return entries
    const label = part.replace(match[0], '').replace(/[+：:]/g, ' ').trim()
    const key = gearStatKeyForLabel(label || part, primaryKey)
    return key ? entries.concat({ key, value }) : entries
  }, [])
}

function gearStatEntriesFromStructuredValue(value, primaryKey) {
  if (!value) return []
  if (Array.isArray(value)) {
    return value.map((row) => {
      if (!row || typeof row !== 'object') return null
      const label = row.label || row.name || row.displayName || row.stat || row.statName || row.key || row.type
      const key = gearStatKeyForLabel(label, primaryKey)
      const amount = [row.value, row.amount, row.rating, row.rawValue, row.baseValue].reduce((matched, candidate) => {
        if (matched !== null) return matched
        return gearNumericValue(candidate)
      }, null)
      return key && amount !== null ? { key, value: amount } : null
    }).filter(Boolean)
  }
  if (typeof value === 'object') {
    const label = value.label || value.name || value.displayName || value.stat || value.statName || value.key || value.type
    const key = gearStatKeyForLabel(label, primaryKey)
    const amount = [value.value, value.amount, value.rating, value.rawValue, value.baseValue].reduce((matched, candidate) => {
      if (matched !== null) return matched
      return gearNumericValue(candidate)
    }, null)
    if (key && amount !== null) return [{ key, value: amount }]
    return Object.keys(value).map((keyName) => {
      const key = gearStatKeyForLabel(keyName, primaryKey)
      const amount = gearNumericValue(value[keyName])
      return key && amount !== null ? { key, value: amount } : null
    }).filter(Boolean)
  }
  return []
}

function gearStatEntriesForItem(item, primaryKey) {
  const structured = [
    ...gearStatEntriesFromStructuredValue(item && item.stats, primaryKey),
    ...gearStatEntriesFromStructuredValue(item && item.itemStats, primaryKey),
    ...gearStatEntriesFromStructuredValue(item && item.attributes, primaryKey),
    ...gearStatEntriesFromStructuredValue(item && item.secondaryStats, primaryKey)
  ]
  if (structured.length) return structured
  return gearStatEntriesFromSummary(item && (item.statSummary || item.stat_summary || item.statsSummary), primaryKey)
}

function gearStatEntriesForEnhancementOption(option, primaryKey) {
  if (!option || typeof option !== 'object') return []
  const payload = optionPayload(option)
  const structured = [
    ...gearStatEntriesFromStructuredValue(option.stats, primaryKey),
    ...gearStatEntriesFromStructuredValue(option.itemStats, primaryKey),
    ...gearStatEntriesFromStructuredValue(payload.stats, primaryKey),
    ...gearStatEntriesFromStructuredValue(payload.itemStats, primaryKey)
  ]
  if (structured.length) return structured
  return gearStatEntriesFromSummary(
    option.statSummary ||
    option.stat_summary ||
    option.displayLabel ||
    option.display_label ||
    option.summary ||
    option.valueSummary ||
    payload.statSummary ||
    payload.stat_summary ||
    payload.displayLabel ||
    payload.display_label ||
    payload.summary ||
    payload.valueSummary,
    primaryKey
  )
}

function directGearStatValue(source, statKey) {
  const aliases = {
    strength: ['strength', 'str', '力量'],
    agility: ['agility', 'agi', '敏捷'],
    intellect: ['intellect', 'intelligence', 'int', '智力'],
    stamina: ['stamina', 'sta', '耐力'],
    haste: ['haste', 'hasteRating', 'haste_rating', '急速'],
    crit: ['crit', 'criticalStrike', 'critical_strike', 'criticalStrikeRating', 'critRating', '暴击', '爆击'],
    mastery: ['mastery', 'masteryRating', 'mastery_rating', '精通'],
    versatility: ['versatility', 'versatilityRating', 'versatility_rating', 'vers', '全能'],
    armor: ['armor', 'armorValue', 'armor_value', '护甲'],
    health: ['health', 'hp', 'maxHealth', 'max_health', '生命值'],
    mana: ['mana', 'mp', 'maxMana', 'max_mana', '法力值']
  }[statKey] || []
  for (let index = 0; index < aliases.length; index += 1) {
    const key = aliases[index]
    if (source && Object.prototype.hasOwnProperty.call(source, key)) {
      const value = gearNumericValue(source[key])
      if (value !== null) return value
    }
  }
  return null
}

function payloadGearStatValue(payload, statKey) {
  const sources = [
    payload && payload.characterStats,
    payload && payload.character_stats,
    payload && payload.statSnapshot,
    payload && payload.stats,
    payload && payload.resources,
    payload && payload.attributes,
    payload
  ]
  for (let index = 0; index < sources.length; index += 1) {
    const source = sources[index]
    if (!source) continue
    const direct = directGearStatValue(source, statKey)
    if (direct !== null) return direct
    const structured = gearStatEntriesFromStructuredValue(source, 'intellect')
    const matched = structured.find((item) => item.key === statKey)
    if (matched) return matched.value
  }
  return null
}

function emptyGearAttributePanel() {
  return {
    visible: false,
    summary: '已选 0/16 槽',
    itemLevel: gearAttributeMetric('itemLevel', '装备等级', null, '待补'),
    enhancementRows: [
      gearEnhancementMetric('embellishment', '美化', 0, gearEnhancementMax),
      gearEnhancementMetric('gem', '宝石', 0, 0),
      gearEnhancementMetric('enchant', '附魔', 0, 0),
      gearEnhancementMetric('tierSet', '套装', 0, gearTierSetMax)
    ],
    statRows: [
      gearAttributeMetric('intellect', '智力', null, '待补'),
      gearAttributeMetric('stamina', '耐力', null, '待补'),
      gearAttributeMetric('haste', '急速', 0, '0'),
      gearAttributeMetric('crit', '暴击', 0, '0'),
      gearAttributeMetric('mastery', '精通', 0, '0'),
      gearAttributeMetric('versatility', '全能', 0, '0')
    ]
  }
}

function buildGearAttributePanel(gearPayload, selectedGearBySlot, selectedSpec, enhancementBySlot, gearStatSnapshot) {
  const requiredSlotsForPanel = requiredGearTemplateSlots(gearPayload || {})
  const indexedSelection = enrichedSelectedGearByCanonicalSlot(gearPayload, selectedGearBySlot || {})
  const selectedItems = requiredSlotsForPanel.map((slot) => indexedSelection[slot]).filter(Boolean)
  if (!selectedItems.length) return emptyGearAttributePanel()
  const specKeys = specWebsimKeys({
    websimClassKey: (selectedSpec && (selectedSpec.websimClassKey || selectedSpec.classKey)) || (gearPayload && gearPayload.classKey),
    websimSpecKey: (selectedSpec && (selectedSpec.websimSpecKey || selectedSpec.specKey)) || (gearPayload && gearPayload.specKey)
  })
  const primaryKey = primaryStatKeyForSpec(specKeys)
  const totals = gearTrackedAttributeKeys.reduce((memo, key) => {
    memo[key] = 0
    return memo
  }, {})
  const itemLevels = []
  selectedItems.forEach((item) => {
    const itemLevel = gearNumericValue(item && (item.ilevel || item.itemLevel || item.item_level))
    if (itemLevel !== null) itemLevels.push(itemLevel)
    const itemTotals = {}
    gearStatEntriesForItem(item, primaryKey).forEach((entry) => {
      itemTotals[entry.key] = (itemTotals[entry.key] || 0) + entry.value
    })
    gearTrackedAttributeKeys.forEach((key) => {
      if (itemTotals[key] === undefined) {
        const direct = directGearStatValue(item, key)
        if (direct !== null) itemTotals[key] = direct
      }
      if (itemTotals[key] !== undefined) totals[key] += itemTotals[key]
    })
  })
  const enhancement = normalizedEnhancementBySlot(enhancementBySlot || {})
  requiredSlotsForPanel.forEach((slot) => {
    const item = indexedSelection[slot]
    const selected = enhancement[slot]
    if (!item || !selected) return
    ;[
      ['socketOptions', 'gem'],
      ['enchantOptions', 'enchant'],
      ['embellishmentOptions', 'embellishment']
    ].forEach(([optionKey, type]) => {
      const selectedOption = enhancementOptionsForSlot(gearPayload, item, optionKey)
        .find((option) => enhancementOptionSelected(option, selected, type))
      if (!selectedOption) return
      gearStatEntriesForEnhancementOption(selectedOption, primaryKey).forEach((entry) => {
        totals[entry.key] = (totals[entry.key] || 0) + entry.value
      })
    })
  })
  const itemLevelAverage = itemLevels.length
    ? itemLevels.reduce((sum, value) => sum + value, 0) / itemLevels.length
    : null
  const payloadPrimary = payloadGearStatValue(gearPayload, primaryKey)
  const payloadStamina = payloadGearStatValue(gearPayload, 'stamina')
  const primaryValue = totals[primaryKey] > 0 ? totals[primaryKey] : payloadPrimary
  const staminaValue = totals.stamina > 0 ? totals.stamina : payloadStamina
  const verifiedSnapshot = verifiedGearStatSnapshot(gearStatSnapshot)
  const snapshotPrimary = gearAttributeMetricFromSnapshot(gearStatSnapshotMetric(verifiedSnapshot, 'primary'), primaryKey, gearPrimaryStatLabels[primaryKey] || '主属性')
  const snapshotStamina = gearAttributeMetricFromSnapshot(gearStatSnapshotMetric(verifiedSnapshot, 'stamina'), 'stamina', '耐力')
  const snapshotItemLevel = gearAttributeMetricFromSnapshot(gearStatSnapshotMetric(verifiedSnapshot, 'itemLevel'), 'itemLevel', '装备等级')
  const enhancementSheet = buildGearEnhancementSheet(gearPayload, selectedGearBySlot, enhancementBySlot || {}, false)
  const gemUsage = gearEnhancementMetricUsage(gearPayload, requiredSlotsForPanel, indexedSelection, enhancement, 'gem', 'socketOptions')
  const enchantUsage = gearEnhancementMetricUsage(gearPayload, requiredSlotsForPanel, indexedSelection, enhancement, 'enchant', 'enchantOptions')
  const tierSetCount = gearTierSetCountForPanel(selectedItems)
  return {
    visible: true,
    summary: `已选 ${selectedItems.length}/${requiredSlotsForPanel.length} 槽`,
    itemLevel: snapshotItemLevel || gearAttributeMetric('itemLevel', '装备等级', itemLevelAverage, '待补'),
    enhancementRows: [
      gearEnhancementMetric('embellishment', '美化', enhancementSheet.embellishmentUsed, enhancementSheet.embellishmentMax),
      gearEnhancementMetric('gem', '宝石', gemUsage.used, gemUsage.max),
      gearEnhancementMetric('enchant', '附魔', enchantUsage.used, enchantUsage.max),
      gearEnhancementMetric('tierSet', '套装', tierSetCount, gearTierSetMax)
    ],
    statRows: [
      snapshotPrimary || gearAttributeMetric(primaryKey, gearPrimaryStatLabels[primaryKey] || '主属性', primaryValue, '待补'),
      snapshotStamina || gearAttributeMetric('stamina', '耐力', staminaValue, '待补'),
      gearAttributeMetricWithSnapshot('haste', '急速', totals.haste, '0', verifiedSnapshot),
      gearAttributeMetricWithSnapshot('crit', '暴击', totals.crit, '0', verifiedSnapshot),
      gearAttributeMetricWithSnapshot('mastery', '精通', totals.mastery, '0', verifiedSnapshot),
      gearAttributeMetricWithSnapshot('versatility', '全能', totals.versatility, '0', verifiedSnapshot)
    ]
  }
}

const canonicalGearAttributeLabels = {
  intellect: '智力',
  agility: '敏捷',
  strength: '力量',
  stamina: '耐力',
  haste: '急速',
  crit: '暴击',
  critical_strike: '暴击',
  mastery: '精通',
  versatility: '全能',
  armor: '护甲'
}

function canonicalGearAttributePanel(snapshot, statSnapshot, communityImportState) {
  if (!snapshot || typeof snapshot !== 'object') return emptyGearAttributePanel()
  const totals = snapshot.staticAttributes && typeof snapshot.staticAttributes === 'object'
    ? (snapshot.staticAttributes.totals || snapshot.staticAttributes)
    : {}
  const resolvedSlots = snapshot.resolvedSlots && typeof snapshot.resolvedSlots === 'object'
    ? snapshot.resolvedSlots
    : {}
  const itemLevels = Object.keys(resolvedSlots).map((slot) => Number(resolvedSlots[slot] && resolvedSlots[slot].itemLevel)).filter(Number.isFinite)
  const itemLevel = itemLevels.length ? itemLevels.reduce((sum, value) => sum + value, 0) / itemLevels.length : null
  const readiness = snapshot.profileReadiness && typeof snapshot.profileReadiness === 'object'
    ? snapshot.profileReadiness
    : {}
  const requiredSlots = Array.isArray(readiness.requiredSlots) ? readiness.requiredSlots : Object.keys(resolvedSlots)
  const readySlots = Array.isArray(readiness.readySlots) ? readiness.readySlots : Object.keys(resolvedSlots)
  const constraints = snapshot.constraints && snapshot.constraints.slots && typeof snapshot.constraints.slots === 'object'
    ? snapshot.constraints.slots
    : {}
  const selectedOptions = Object.keys(resolvedSlots).map((slot) => (resolvedSlots[slot] && resolvedSlots[slot].selectedOptions) || {})
  const gemUsed = selectedOptions.reduce((count, options) => count + (Array.isArray(options.gemOptionIds) ? options.gemOptionIds.length : 0), 0)
  const enchantUsed = selectedOptions.filter((options) => options.enchantOptionId).length
  const embellishmentUsed = selectedOptions.filter((options) => options.embellishmentOptionId).length
  const gemMax = Object.keys(constraints).reduce((count, slot) => count + (Number(constraints[slot] && constraints[slot].socketCount) || 0), 0)
  const enchantMax = Object.keys(constraints).filter((slot) => constraints[slot] && constraints[slot].canEnchant).length
  const embellishmentMaxValue = Number(snapshot.constraints && snapshot.constraints.embellishmentMax)
  const embellishmentMax = Number.isFinite(embellishmentMaxValue) && embellishmentMaxValue >= 0
    ? embellishmentMaxValue
    : 0
  const setCounts = snapshot.setState && snapshot.setState.itemSetCounts && typeof snapshot.setState.itemSetCounts === 'object'
    ? snapshot.setState.itemSetCounts
    : {}
  const tierCount = Object.keys(setCounts).reduce((maximum, key) => Math.max(maximum, Number(setCounts[key]) || 0), 0)
  const inheritedCounts = inheritedEnhancementCountByType(
    eligibleCommunityEnhancementImportState(communityImportState, snapshot)
  )
  const preferredOrder = ['intellect', 'agility', 'strength', 'stamina', 'haste', 'crit', 'critical_strike', 'mastery', 'versatility', 'armor']
  const verifiedStatSnapshot = verifiedGearStatSnapshot(statSnapshot)
  const snapshotSecondaryKeys = Array.isArray(verifiedStatSnapshot && verifiedStatSnapshot.secondary)
    ? verifiedStatSnapshot.secondary.map((row) => cleanGearString(row && row.key)).filter(Boolean)
    : []
  const orderedKeys = [
    ...preferredOrder.filter((key) => Object.prototype.hasOwnProperty.call(totals, key)),
    ...Object.keys(totals).sort().filter((key) => !preferredOrder.includes(key)),
    ...snapshotSecondaryKeys.filter((key) => !Object.prototype.hasOwnProperty.call(totals, key))
  ]
  return {
    visible: orderedKeys.length > 0 || Object.keys(resolvedSlots).length > 0,
    summary: `已校验 ${readySlots.length}/${requiredSlots.length} 槽`,
    itemLevel: gearAttributeMetric('itemLevel', '装备等级', itemLevel, '待补'),
    enhancementRows: [
      withInheritedEnhancementCount(
        gearEnhancementMetric('embellishment', '美化', embellishmentUsed, embellishmentMax),
        inheritedCounts.embellishment
      ),
      withInheritedEnhancementCount(gearEnhancementMetric('gem', '宝石', gemUsed, gemMax), inheritedCounts.gem),
      withInheritedEnhancementCount(gearEnhancementMetric('enchant', '附魔', enchantUsed, enchantMax), inheritedCounts.enchant),
      { ...gearEnhancementMetric('tierSet', '套装', tierCount, tierCount), value: String(tierCount) }
    ],
    statRows: orderedKeys.map((key) => {
      const snapshotMetric = gearAttributeMetricFromSnapshot(
        gearStatSnapshotMetric(verifiedStatSnapshot, key),
        key,
        canonicalGearAttributeLabels[key] || key
      )
      if (!Object.prototype.hasOwnProperty.call(totals, key)) return snapshotMetric || gearAttributeMetric(key, canonicalGearAttributeLabels[key] || key, 0, '0')
      const canonicalMetric = gearAttributeMetric(key, canonicalGearAttributeLabels[key] || key, totals[key], '0')
      return snapshotMetric && snapshotMetric.convertedValue
        ? { ...canonicalMetric, convertedValue: snapshotMetric.convertedValue, convertedRawValue: snapshotMetric.convertedRawValue }
        : canonicalMetric
    })
  }
}

function workbenchProblemRows(problems) {
  const labels = {
    RESOLVER_CONTEXT_UNAVAILABLE: '缺少当前赛季校验上下文，请稍后重试',
    AUTHORITY_UNAVAILABLE: '装备权威数据暂不可用，请稍后重试',
    REVISION_CONFLICT: '装备数据版本已更新，请重新校验',
    GEAR_REQUIRED_SLOTS_INCOMPLETE: '请补齐服务端标记的必需装备槽位',
    GEAR_TRANSPORT_UNAVAILABLE: '网络连接异常，当前配置未完成校验'
  }
  return (Array.isArray(problems) ? problems : []).slice(0, 5).map((problem, index) => ({
    key: `${String(problem && problem.code || 'GEAR_PROBLEM')}-${index}`,
    code: String(problem && problem.code || ''),
    text: String(labels[problem && problem.code] || '当前装备配置存在待处理问题').slice(0, 80)
  }))
}

function canonicalGearSlotRows(rows, state) {
  const sourceRows = Array.isArray(rows) ? rows : []
  const snapshot = state && (state.currentSnapshot || state.lastVerifiedSnapshot)
  const resolvedSlots = snapshot && snapshot.resolvedSlots && typeof snapshot.resolvedSlots === 'object'
    ? snapshot.resolvedSlots
    : {}
  return sourceRows.map((row) => {
    if (state && ['resolving', 'pending', 'dirty'].includes(state.resolveStatus)) {
      return { ...row, status: 'partial', statusLabel: '校验中', statusClass: 'partial' }
    }
    const resolved = resolvedSlots[row.slot]
    const verified = !!(resolved && resolved.legality && resolved.legality.status === 'verified')
    return {
      ...row,
      status: verified ? 'verified' : 'blocked',
      statusLabel: verified ? '已校验' : '未通过校验',
      statusClass: verified ? 'verified' : 'blocked'
    }
  })
}

function gearWorkbenchDataState(state, data, communityImportState) {
  const view = gearWorkbenchView(state)
  const displaySnapshot = acceptedGearDisplaySnapshot(state)
  const displayCommunityImportState = ['dirty', 'resolving', 'pending', 'revision_conflict'].includes(cleanGearString(state && state.resolveStatus))
    ? emptyCommunityEnhancementImportState()
    : communityImportState
  const statusText = {
    idle: '等待校验当前装备配置',
    dirty: '装备配置已修改，等待校验',
    resolving: '正在校验当前装备配置',
    pending: '服务端仍在校验当前装备配置',
    blocked: '当前装备配置未通过校验',
    revision_conflict: state && state.revisionRetryCount >= 1 ? '装备数据再次更新，已切换为只读' : '装备数据已更新，正在重新校验',
    unavailable: '装备校验服务暂不可用',
    offline: '网络连接异常，显示最近一次已校验结果',
    verified: '当前装备配置已通过服务端校验'
  }
  return {
    gearWorkbenchView: view,
    gearWorkbenchStatusText: statusText[view.resolveStatus] || '等待校验当前装备配置',
    gearWorkbenchSignatureLabel: view.resolvedGearSignature ? view.resolvedGearSignature.slice(0, 20) : '',
    gearWorkbenchProblemRows: workbenchProblemRows(state && state.problems),
    gearAttributePanel: canonicalGearAttributePanel(displaySnapshot, data && data.gearStatSnapshot, displayCommunityImportState),
    ...((data && Array.isArray(data.gearSlotRows)) ? { gearSlotRows: canonicalGearSlotRows(data.gearSlotRows, state) } : {})
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

function cleanGearString(value) {
  return String(value === undefined || value === null ? '' : value).trim()
}

function gearIssueSlotLabel(value) {
  const key = cleanGearString(value).replace(/\.$/, '')
  return gearSlotDisplayLabels[key] || key
}

function localizedGearIssueSlotList(value) {
  return cleanGearString(value)
    .replace(/\.$/, '')
    .split(',')
    .map((item) => gearIssueSlotLabel(item.trim()))
    .filter(Boolean)
    .join('、')
}

function localizedGearMissingSlotsIssue(value) {
  const text = cleanGearString(value)
  const match = text.match(/^(?:Missing core SimC gear slots|missing gear slots):\s*(.+?)\.?$/i)
  if (!match) return ''
  const slots = localizedGearIssueSlotList(match[1])
  return slots ? `缺少可执行装备槽位：${slots}` : '缺少可执行装备槽位'
}

function localizedGearItemNameDiagnostic(value) {
  const text = cleanGearString(value)
  const match = text.match(/^Trivial:\s*Player\b.*?\bat slot\s+([a-z0-9_]+)\b.*?has inconsistency between name\b/i)
  if (!match) return ''
  const slot = gearIssueSlotLabel(match[1])
  return `${slot}装备数据不一致：装备名称和物品 ID 对不上，请重新选择或保存${slot}。`
}

function localizedGearFieldIssue(value) {
  const text = cleanGearString(value)
  const missingItemId = text.match(/^missing item id for gear slot:\s*([a-z0-9_]+)\.?$/i)
  if (missingItemId) return `${gearIssueSlotLabel(missingItemId[1])}缺少物品 ID`
  return ''
}

function localizedGearIssue(value) {
  const text = String(value || '').trim()
  const normalized = text.toLowerCase()
  if (!text) return ''
  const missingSlots = localizedGearMissingSlotsIssue(text)
  if (missingSlots) return missingSlots
  const itemNameDiagnostic = localizedGearItemNameDiagnostic(text)
  if (itemNameDiagnostic) return itemNameDiagnostic
  const fieldIssue = localizedGearFieldIssue(text)
  if (fieldIssue) return fieldIssue
  if (normalized.includes('deterministic simc variant')) return '缺少确定 SimC 变体'
  if (normalized.includes('simc json did not include target item stats') || normalized.includes('simulationcraft item stats')) return 'SimC 属性待回填'
  if (normalized.includes('bonus_id/gem_id/enchant_id')) return '缺少 bonus/宝石/附魔'
  if (normalized.includes('missing item id') || normalized === 'itemid' || normalized === 'item id') return '缺少物品 ID'
  if (normalized.includes('item level') || normalized === 'ilevel' || normalized === 'itemlevel') return '缺少装等'
  if (normalized.includes('variantkey') || normalized === 'variant key') return '缺少变体'
  if (normalized === 'slot') return '缺少槽位'
  if (normalized.includes('crafted_stats') || normalized === 'crafted stats') return '缺少制造属性搭配'
  if (normalized.includes('observed gear source is not verified')) return '观测来源未验证'
  if (normalized.includes('crafted variant missing deterministic simc options')) return '制造变体缺少确定 SimC 字段'
  if (normalized.includes('missing item')) return '缺少装备'
  if (/traceback|^command\b|\bitem_\d+\b|\bwebsim_[a-z0-9_]+\b|\bsimulationcraft\b/.test(normalized)) return '装备模拟数据暂不可用'
  if (normalized.includes('simc') && /(failed|error|invalid|unable|missing|could not|timeout|timed out|parseable)/.test(normalized)) return '装备模拟数据暂不可用'
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

function gearCandidateHasDisplayStats(item) {
  return !!(
    item && (
      item.statSummary ||
      (Array.isArray(item.stats) && item.stats.length) ||
      (Array.isArray(item.itemStats) && item.itemStats.length) ||
      (Array.isArray(item.attributes) && item.attributes.length) ||
      (Array.isArray(item.secondaryStats) && item.secondaryStats.length)
    )
  )
}

function gearCandidateStatsPending(item) {
  if (!item || gearCandidateHasDisplayStats(item)) return false
  const statDisplayStatus = String(item.statDisplayStatus || '').toLowerCase()
  if (statDisplayStatus.includes('pending')) return true
  if (String(item.simcStatStatus || '').toLowerCase() === 'failed') return true
  const blockers = stringList([
    ...((item && item.blockers) || []),
    ...((item && item.variantBlockers) || []),
    ...((item && item.missingFields) || [])
  ]).join(' ').toLowerCase()
  return blockers.includes('simulationcraft item stats')
}

function gearCandidateDropSourcePending(item) {
  if (!item) return false
  return gearDropSourceText(item) === '来源待补充'
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
  } else if (item && item.simcReady && gearCandidateStatsPending(item)) {
    status = 'stat-pending'
  } else if (item && item.simcReady && gearCandidateDropSourcePending(item)) {
    status = 'source-pending'
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
  if (status === 'stat-pending') {
    const details = gearPendingStatReason(item) || '装备属性待补充'
    return {
      status,
      label: '属性待补',
      reason: `可保存为 SimC 配置，但${details}，装备属性未验证。`,
      blockerLabel: details
    }
  }
  if (status === 'source-pending') {
    return {
      status,
      label: '来源待补',
      reason: '可保存为 SimC 配置，但掉落来源待补充，来源未验证。',
      blockerLabel: '掉落来源待补充'
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
  if (status === 'stat-pending') return '属性待补'
  if (status === 'source-pending') return '来源待补'
  if (status === 'source-reference') return '来源参考'
  if (status === 'partial') return '缺字段'
  return '不可计算'
}

function gearStatusClass(status) {
  if (status === 'verified') return 'verified'
  if (status === 'stat-pending') return 'partial'
  if (status === 'source-pending') return 'partial'
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

function craftedStatSelections(selectedGearBySlot) {
  return selectedGearItems(selectedGearBySlot).filter((item) => item.selectedCraftedStatKey || item.crafted_stats).map((item) => ({
    slot: item.slot || item.simcSlot || '',
    itemId: normalizedGearItemId(item),
    variantKey: item.variantKey || '',
    selectedCraftedStatKey: item.selectedCraftedStatKey || '',
    crafted_stats: item.crafted_stats || '',
    statSummary: item.statSummary || ''
  }))
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
    item.crafted_stats ? `crafted_stats=${item.crafted_stats}` : '',
    item.embellishment ? `embellishment=${item.embellishment}` : ''
  ].filter(Boolean)
  return fields.join(',')
}

function orderedGearBySlot(selectedGearBySlot, gearPayload) {
  const indexed = selectedGearByCanonicalSlot(selectedGearBySlot)
  const snapshot = {}
  requiredGearTemplateSlots(gearPayload).forEach((slot) => {
    if (!indexed[slot]) return
    snapshot[slot] = gearObjectForSnapshot(indexed[slot])
  })
  return snapshot
}

function normalizedOptionIdentityList(value) {
  return (Array.isArray(value) ? value : [])
    .map(cleanGearString)
    .filter((id, index, values) => id && values.indexOf(id) === index)
}

function normalizedEnhancementBySlot(enhancementBySlot) {
  const result = {}
  Object.keys(enhancementBySlot || {}).sort().forEach((slot) => {
    const record = enhancementBySlot[slot]
    if (!record || typeof record !== 'object') return
    const next = {}
    const gemOptionIds = normalizedOptionIdentityList(record.gemOptionIds)
    if (gemOptionIds.length) next.gemOptionIds = gemOptionIds
    ;['socketOptionId', 'enchantOptionId', 'embellishmentOptionId', 'gem_id', 'gem_bonus_id', 'gem_ilevel', 'enchant_id', 'embellishment'].forEach((key) => {
      const value = cleanGearString(record[key])
      if (value) next[key] = value
    })
    if (Object.keys(next).length) result[slot] = next
  })
  return result
}

function optionIdentityEnhancementBySlot(enhancementBySlot) {
  const normalized = normalizedEnhancementBySlot(enhancementBySlot)
  const result = {}
  Object.keys(normalized).forEach((slot) => {
    const next = {}
    const gemOptionIds = normalizedOptionIdentityList(normalized[slot] && normalized[slot].gemOptionIds)
    if (gemOptionIds.length) next.gemOptionIds = gemOptionIds
    ;['socketOptionId', 'enchantOptionId', 'embellishmentOptionId'].forEach((key) => {
      const value = cleanGearString(normalized[slot] && normalized[slot][key])
      if (value) next[key] = value
    })
    if (Object.keys(next).length) result[slot] = next
  })
  return result
}

function gearSelectionWithoutEmbeddedSimcEnhancements(selectedGearBySlot) {
  const result = {}
  Object.keys(selectedGearBySlot || {}).forEach((slot) => {
    const item = selectedGearBySlot[slot]
    if (!item || typeof item !== 'object') return
    const next = { ...item }
    ;['gem_id', 'gem_bonus_id', 'gem_ilevel', 'enchant_id', 'embellishment', 'embellishmentSource'].forEach((key) => {
      delete next[key]
    })
    result[slot] = next
  })
  return result
}

function canonicalWorkbenchSnapshot(page) {
  return acceptedGearDisplaySnapshot(page && page.gearWorkbenchState)
}

function acceptedGearDisplaySnapshot(state) {
  if (gearWorkbenchCanUseVerifiedSnapshot(state)) return state.currentSnapshot
  return (state && state.lastVerifiedSnapshot) || null
}

function canonicalEnhancementTypeIdentity(record, type) {
  const source = record && typeof record === 'object' ? record : {}
  if (type === 'gem') {
    const gemOptionIds = normalizedOptionIdentityList(source.gemOptionIds)
    const legacyOptionId = cleanGearString(source.socketOptionId)
    return gemOptionIds.length ? gemOptionIds : (legacyOptionId ? [legacyOptionId] : [])
  }
  if (type === 'enchant') return cleanGearString(source.enchantOptionId)
  if (type === 'embellishment') return cleanGearString(source.embellishmentOptionId)
  return ''
}

function changedCanonicalEnhancementTargets(beforeEnhancementBySlot, afterEnhancementBySlot) {
  const before = optionIdentityEnhancementBySlot(beforeEnhancementBySlot)
  const after = optionIdentityEnhancementBySlot(afterEnhancementBySlot)
  const slots = Array.from(new Set([...Object.keys(before), ...Object.keys(after)])).sort()
  const targets = []
  slots.forEach((slot) => {
    ;['gem', 'enchant', 'embellishment'].forEach((type) => {
      const beforeIdentity = canonicalEnhancementTypeIdentity(before[slot], type)
      const afterIdentity = canonicalEnhancementTypeIdentity(after[slot], type)
      if (JSON.stringify(beforeIdentity) !== JSON.stringify(afterIdentity)) targets.push({ slot, type })
    })
  })
  return targets
}

function normalizedEnhancementReplacementTargets(targets) {
  const seen = new Set()
  return (Array.isArray(targets) ? targets : []).reduce((result, target) => {
    const slot = cleanGearString(target && target.slot)
    const type = cleanGearString(target && target.type)
    const key = `${slot}:${type}`
    if (!slot || !['gem', 'enchant', 'embellishment'].includes(type) || seen.has(key)) return result
    seen.add(key)
    result.push({ slot, type })
    return result
  }, [])
}

function gearSelectionWithCanonicalEnhancementConstraints(selectedGearBySlot, snapshot) {
  const result = gearSelectionWithoutEmbeddedSimcEnhancements(selectedGearBySlot)
  const constraints = snapshot && snapshot.constraints && snapshot.constraints.slots && typeof snapshot.constraints.slots === 'object'
    ? snapshot.constraints.slots
    : {}
  Object.keys(result).forEach((slot) => {
    const item = result[slot]
    const slotConstraints = constraints[slot] && typeof constraints[slot] === 'object' ? constraints[slot] : {}
    const socketCount = Math.max(0, Number(slotConstraints.socketCount) || 0)
    result[slot] = {
      ...item,
      socketCount,
      supportsSocket: socketCount > 0,
      modCapabilities: {
        hasSocket: socketCount > 0,
        socketCount,
        canEnchant: slotConstraints.canEnchant === true,
        canEmbellish: slotConstraints.canEmbellish === true
      }
    }
  })
  return result
}

function gearTemplateSnapshot(selectedGearBySlot, enhancementBySlot, gearPayload) {
  return {
    schemaRevision: GEAR_ENHANCEMENT_SNAPSHOT_REVISION,
    gearBySlot: orderedGearBySlot(selectedGearBySlot, gearPayload),
    enhancementBySlot: normalizedEnhancementBySlot(enhancementBySlot)
  }
}

function simcTalentImportCandidate(value) {
  const text = cleanGearString(value)
  if (!text) return ''
  const normalized = text.startsWith('talents=') ? text.split('=', 2)[1].trim() : text
  return normalized.startsWith('websim:') ? '' : text
}

function gearTalentImportForStats(data) {
  const talentDetail = detailForQuery((data && data.selectedDetail) || {}, 'talents') || {}
  const candidates = [
    talentDetail.importCode,
    talentDetail.talentImport,
    talentDetail.rawString,
    data && data.talentImport,
    data && data.gearStatsTalentImport,
    talentDetail.websimExportCode,
    data && data.websimExportCode
  ]
  return candidates.map(simcTalentImportCandidate).find(Boolean) || ''
}

function gearStatsRequestForPage(page) {
  const data = (page && page.data) || {}
  const gearPayload = fullGearPayloadForPage(page) || data.gearPayload || {}
  const blockers = []
  if (data.activeQueryKey !== 'gear') blockers.push('当前不在装备模拟页')
  if (!gearPayload || !Array.isArray(gearPayload.slots)) blockers.push('等待装备数据')
  if (data.gearDataFallback) blockers.push(data.gearDataWarningText || '装备接口暂不可用')
  const canonicalState = page && page.gearWorkbenchState
  const canonicalSnapshot = canonicalState && canonicalState.currentSnapshot
  if (!canonicalState || !gearWorkbenchCanUseVerifiedSnapshot(canonicalState)) blockers.push('等待当前装备配置完成服务端校验')
  const selectedGearBySlot = prunedGearSelectionByWeaponRule(gearPayload, data.selectedGearBySlot || {})
  const requiredSlots = requiredGearTemplateSlots(gearPayload)
  const indexed = selectedGearByCanonicalSlot(selectedGearBySlot)
  if (!canonicalState) {
    const missingSlots = requiredSlots.filter((slot) => !gearTemplateLine(indexed[slot]))
    if (missingSlots.length) blockers.push(`请补齐 ${requiredSlots.length} 个装备槽位`)
  }
  const talents = gearTalentImportForStats(data)
  if (!talents) blockers.push('缺少天赋导入代码')
  if (blockers.length) {
    return { ready: false, blockers: blockers.filter(Boolean) }
  }
  const profileContext = {
    name: cleanGearString(data.selectedCharacterName || data.characterName || ''),
    race: cleanGearString(data.selectedRaceKey || data.raceKey || ''),
    scenarioKey: gearScenarioAt(data.selectedGearTemplateScenarioIndex).key,
    heroKey: cleanGearString(data.selectedHeroKey || ''),
    talents
  }
  Object.keys(profileContext).forEach((key) => {
    if (!profileContext[key]) delete profileContext[key]
  })
  const selectionIntent = JSON.parse(JSON.stringify(canonicalState.confirmedIntent))
  const payload = { selectionIntent, profileContext }
  return {
    ready: true,
    payload,
    signature: JSON.stringify([
      canonicalState.intentVersion,
      canonicalSnapshot && canonicalSnapshot.resolvedGearSignature || '',
      payload
    ])
  }
}

function maybeRefreshGearStatsForPage(page) {
  const request = gearStatsRequestForPage(page)
  if (!request.ready) {
    if ((request.blockers || []).includes('当前不在装备模拟页')) return Promise.resolve(null)
    if (page && typeof page.clearGearStatsSnapshot === 'function') {
      return page.clearGearStatsSnapshot(request.blockers)
    }
    return Promise.resolve(null)
  }
  if (page && typeof page.refreshGearStats === 'function') {
    return page.refreshGearStats(request.payload, request.signature)
  }
  return Promise.resolve(null)
}

function resolveOrRefreshGearForPage(page, selectedGearBySlot, enhancementBySlot, resolveContext) {
  const gearPayload = fullGearPayloadForPage(page) || (page && page.data && page.data.gearPayload) || {}
  if (completeResolverContext(gearPayload.resolverContext) && page && typeof page.confirmAndResolveGearIntent === 'function') {
    return page.confirmAndResolveGearIntent(selectedGearBySlot, enhancementBySlot, resolveContext)
      .then(() => maybeRefreshGearStatsForPage(page))
  }
  return maybeRefreshGearStatsForPage(page)
}

function optionQualityRank(option) {
  const payload = option && typeof option.payload === 'object' ? option.payload : {}
  const value = option && (option.qualityRank || option.rank || payload.qualityRank || payload.rank || payload.craftingQuality || payload.qualityTier)
  if (value === undefined || value === null || value === '') return 2
  const text = String(value).trim().toLowerCase()
  if (['2', 'r2', 'rank2', 'rank_2', 'two-star', 'two_star', '2-star', '2星', '二星'].includes(text)) return 2
  if (['1', 'r1', 'rank1', 'rank_1', 'one-star', 'one_star', '1-star', '1星', '一星'].includes(text)) return 1
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : 0
}

function verifiedRankTwoOption(option) {
  if (!option || typeof option !== 'object') return false
  const status = cleanGearString(option.status || 'verified').toLowerCase()
  return status === 'verified' && optionQualityRank(option) === 2
}

function gearGroupOptionsForSlot(gearPayload, slot, key) {
  const groups = gearGroupsBySlot(gearPayload)
  const group = groups[slot] || {}
  return Array.isArray(group[key]) ? group[key] : []
}

function gearPayloadHasEnhancementOptions(gearPayload, key) {
  const groups = (gearPayload && (gearPayload.replacementCandidates || gearPayload.slotGroups)) || []
  return (Array.isArray(groups) ? groups : []).some((group) => {
    const options = group && Array.isArray(group[key]) ? group[key] : []
    return options.some((option) => verifiedRankTwoOption(option))
  })
}

function uniqueEnhancementOptions(options) {
  const seen = new Set()
  return (options || []).filter((option) => {
    if (!verifiedRankTwoOption(option)) return false
    const simcOptions = option.simcOptions && typeof option.simcOptions === 'object' ? option.simcOptions : {}
    const key = JSON.stringify([option.id || option.label || option.name || '', simcOptions])
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function enhancementOptionSlotGroup(option) {
  const payload = option && option.payload && typeof option.payload === 'object' ? option.payload : {}
  return cleanGearString((option && option.slotGroup) || payload.slotGroup || payload.slot_group).toLowerCase()
}

function normalizedConfigKey(value) {
  return cleanGearString(value).replace(/[^a-zA-Z0-9_]+/g, '_').replace(/^_+|_+$/g, '').toLowerCase()
}

function enchantOptionConfigCategory(option) {
  const payload = option && option.payload && typeof option.payload === 'object' ? option.payload : {}
  return normalizedConfigKey(
    (option && (option.configCategory || option.config_category || option.enchantCategory || option.enchant_category)) ||
    payload.configCategory ||
    payload.config_category ||
    payload.enchantCategory ||
    payload.enchant_category ||
    payload.category
  )
}

function enchantOptionExcludedFromGearConfig(option) {
  const payload = option && option.payload && typeof option.payload === 'object' ? option.payload : {}
  const category = enchantOptionConfigCategory(option)
  return !!(
    gearConfigEnchantExcludedCategories.has(category) ||
    (option && (option.excludeFromGearConfig || option.exclude_from_gear_config || option.blocked)) ||
    payload.excludeFromGearConfig ||
    payload.exclude_from_gear_config ||
    payload.blocked
  )
}

function enchantOptionItemTypeRule(option) {
  const payload = option && option.payload && typeof option.payload === 'object' ? option.payload : {}
  return normalizedConfigKey(
    (option && (option.itemTypeRule || option.item_type_rule)) ||
    payload.itemTypeRule ||
    payload.item_type_rule
  )
}

function gearItemTypeContext(item) {
  return {
    slot: cleanGearString(item && (item.slot || item.simcSlot)),
    armorType: cleanGearString(item && item.armorType).toLowerCase(),
    weaponType: cleanGearString(item && item.weaponType).toLowerCase()
  }
}

function normalizedWeaponRule(gearPayload) {
  const rule = gearPayload && gearPayload.weaponRule && typeof gearPayload.weaponRule === 'object'
    ? gearPayload.weaponRule
    : {}
  const normalizeList = (values) => new Set(
    (Array.isArray(values) ? values : [])
      .map((value) => cleanGearString(value).toLowerCase())
      .filter(Boolean)
  )
  const mode = cleanGearString(rule.mode).toLowerCase()
  const mainHandTypes = normalizeList(rule.mainHandTypes)
  const offHandTypes = normalizeList(rule.offHandTypes)
  return {
    mode,
    mainHandTypes,
    offHandTypes,
    available: !!(mode || mainHandTypes.size || offHandTypes.size)
  }
}

function weaponRuleAllowsItem(rule, item) {
  if (!rule || !rule.available || !item) return true
  const { slot, weaponType } = gearItemTypeContext(item)
  if (slot !== 'main_hand' && slot !== 'off_hand') return true
  if (!weaponType) return true
  const allowedTypes = slot === 'main_hand' ? rule.mainHandTypes : rule.offHandTypes
  return allowedTypes.has(weaponType)
}

function backendGearLegalityBlocksItem(item) {
  if (!item || typeof item !== 'object') return false
  const compatibility = item.compatibility && typeof item.compatibility === 'object' ? item.compatibility : {}
  return item.legalityStatus === 'blocked' || compatibility.legalityStatus === 'blocked'
}

function backendGearLegalityBlocksSlot(gearPayload, slot, item) {
  if (!gearPayload || !slot || !item) return false
  const backendItem = ((gearPayload.equippedSet || {})[slot]) || null
  if (!backendGearLegalityBlocksItem(backendItem)) return false
  const backendItemId = normalizedGearItemId(backendItem)
  const selectedItemId = normalizedGearItemId(item)
  return !!(backendItemId && selectedItemId && backendItemId === selectedItemId)
}

function prunedGearSelectionByWeaponRule(gearPayload, selectedGearBySlot) {
  const rule = normalizedWeaponRule(gearPayload || {})
  const selected = { ...(selectedGearBySlot || {}) }
  Object.keys(selected).forEach((slot) => {
    if (backendGearLegalityBlocksItem(selected[slot]) || backendGearLegalityBlocksSlot(gearPayload, slot, selected[slot])) delete selected[slot]
  })
  if (!rule.available) return selected
  Object.keys(selected).forEach((slot) => {
    if (!weaponRuleAllowsItem(rule, selected[slot])) delete selected[slot]
  })
  const mainType = gearItemTypeContext(selected.main_hand).weaponType
  if (
    selected.off_hand &&
    twoHandWeaponTypes.has(mainType) &&
    rule.mode !== 'dual_wield_2h'
  ) {
    delete selected.off_hand
  }
  return selected
}

function offHandOccupyingMainHandItem(gearPayload, selectedGearBySlot) {
  const rule = normalizedWeaponRule(gearPayload || {})
  if (rule.available && rule.mode === 'dual_wield_2h') return null
  const equippedSet = (gearPayload && gearPayload.equippedSet) || {}
  const mainHand = (selectedGearBySlot && selectedGearBySlot.main_hand) || equippedSet.main_hand
  const mainType = gearItemTypeContext(mainHand).weaponType
  return twoHandWeaponTypes.has(mainType) ? mainHand : null
}

function occupiedOffHandGearItem(gearPayload, selectedGearBySlot) {
  const mainHand = offHandOccupyingMainHandItem(gearPayload, selectedGearBySlot)
  if (!mainHand) return null
  return {
    slot: 'off_hand',
    simcSlot: 'off_hand',
    displayName: '双手武器已占用',
    localizedName: '双手武器已占用',
    source: '主手双手武器',
    sourceType: 'weapon_rule',
    simcReady: true,
    metadataStatus: 'verified',
    reason: '主手双手武器占用副手槽位',
    blockerLabel: ''
  }
}

function embellishmentOptionAppliesToItem(option, item) {
  const group = enhancementOptionSlotGroup(option)
  if (!group) return true
  const { slot, armorType, weaponType } = gearItemTypeContext(item)
  const isShield = slot === 'off_hand' && (weaponType === 'shield' || armorType === 'shield')
  const isHeldOffhand = slot === 'off_hand' && weaponType === 'held in off-hand'
  if (group === 'equipment') return gearEmbellishmentEquipmentSlots.has(slot)
  if (group === 'jewelry') return gearEmbellishmentJewelrySlots.has(slot)
  if (group === 'armor') return gearEmbellishmentArmorSlots.has(slot) || isShield
  if (group === 'weapon' || group === 'weapon_offhand') return slot === 'main_hand' || isHeldOffhand
  if (group === 'weapon_armor') {
    return gearEmbellishmentArmorSlots.has(slot) || slot === 'main_hand' || isShield || isHeldOffhand
  }
  return true
}

function enchantOptionAppliesToItem(option, item) {
  if (enchantOptionExcludedFromGearConfig(option)) return false
  const { slot, armorType, weaponType } = gearItemTypeContext(item)
  if (slot !== 'off_hand') return true
  const isShield = weaponType === 'shield' || armorType === 'shield'
  const isHeldOffhand = weaponType === 'held in off-hand'
  const rule = enchantOptionItemTypeRule(option)
  if (['any', 'any_equipment', 'equipment', 'gear', 'gear_slot'].includes(rule)) return true
  if (['shield', 'offhand_shield', 'off_hand_shield'].includes(rule)) return isShield
  if (['held_offhand', 'held_off_hand', 'holdable', 'invtype_holdable'].includes(rule)) return isHeldOffhand
  return offhandWeaponEnchantTypes.has(weaponType)
}

function rawEnhancementOptionsForSlot(gearPayload, item, optionKey) {
  const slot = item && (item.slot || item.simcSlot)
  return uniqueEnhancementOptions([
    ...((item && Array.isArray(item[optionKey])) ? item[optionKey] : []),
    ...gearGroupOptionsForSlot(gearPayload, slot, optionKey)
  ])
}

function isDeathKnightGearPayload(gearPayload) {
  const key = cleanGearString(gearPayload && (gearPayload.classKey || gearPayload.websimClassKey)).toLowerCase().replace(/[^a-z0-9]+/g, '')
  return key === 'deathknight' || key === 'dk'
}

function isWeaponEnchantSlot(slot) {
  return slot === 'main_hand' || slot === 'off_hand'
}

function deathKnightRuneforgeWarningForItem(gearPayload, item) {
  if (!isDeathKnightGearPayload(gearPayload)) return ''
  const { slot } = gearItemTypeContext(item)
  if (!isWeaponEnchantSlot(slot)) return ''
  const options = rawEnhancementOptionsForSlot(gearPayload, item, 'enchantOptions')
    .filter((option) => enchantOptionAppliesToItem(option, item))
  if (!options.length || gearItemEnchantCapacity(item) <= 0) return ''
  return 'DK runeforge: 死亡骑士默认使用符文熔铸；普通武器附魔会覆盖符文熔铸，当前默认隐藏。'
}

function enhancementOptionsForSlot(gearPayload, item, optionKey) {
  const options = rawEnhancementOptionsForSlot(gearPayload, item, optionKey)
  if (optionKey === 'enchantOptions') {
    const { slot } = gearItemTypeContext(item)
    if (isDeathKnightGearPayload(gearPayload) && isWeaponEnchantSlot(slot)) return []
    return options.filter((option) => enchantOptionAppliesToItem(option, item))
  }
  if (optionKey === 'embellishmentOptions') {
    return options.filter((option) => embellishmentOptionAppliesToItem(option, item))
  }
  return options
}

function itemSupportsEnhancement(item, type, options) {
  const caps = item && item.modCapabilities ? item.modCapabilities : {}
  const slot = item && (item.slot || item.simcSlot)
  const hasItemOptions = (key) => !!(item && Array.isArray(item[key]) && item[key].length)
  if (type === 'gem') {
    const explicit = explicitGearCapabilityValue(caps, 'hasSocket')
    if (explicit === false) return false
    return gearItemSocketCapacity(item) > 0 && !!(explicit || (options && options.length) || hasItemOptions('socketOptions') || item.supportsSocket)
  }
  if (type === 'enchant') {
    const explicit = explicitGearCapabilityValue(caps, 'canEnchant')
    if (explicit === false) return false
    return gearItemEnchantCapacity(item) > 0 && !!((options && options.length) || hasItemOptions('enchantOptions'))
  }
  if (type === 'embellishment') {
    const sourceType = cleanGearString(item && item.sourceType).toLowerCase()
    const variantSource = cleanGearString(item && item.variantSource).toLowerCase()
    return !!(caps.canEmbellish || item.crafted_stats || item.embellishment || sourceType === 'crafted' || variantSource === 'crafted' || hasItemOptions('embellishmentOptions'))
  }
  return false
}

function builtInEmbellishmentValue(item) {
  return cleanGearString(
    item && (
      (item.hasBuiltInEmbellishment ? item.builtInEmbellishment || 'built_in' : '') ||
      item.builtInEmbellishment ||
      item.intrinsicEmbellishment ||
      item.inherentEmbellishment ||
      (['built_in', 'builtin', 'intrinsic', 'item'].includes(cleanGearString(item.embellishmentSource).toLowerCase()) ? item.embellishment : '') ||
      item.embellishment
    )
  )
}

function gearBuiltInEmbellishmentBadgeLabel(item) {
  if (!item || typeof item !== 'object') return ''
  const source = cleanGearString(item.embellishmentSource).toLowerCase()
  const appliedEmbellishment = cleanGearString(item.embellishment)
  const hasExplicitBuiltIn = !!(
    item.hasBuiltInEmbellishment ||
    item.builtInEmbellishment ||
    item.intrinsicEmbellishment ||
    item.inherentEmbellishment ||
    ['built_in', 'builtin', 'intrinsic', 'item'].includes(source)
  )
  if (!hasExplicitBuiltIn && !appliedEmbellishment) return ''
  return cleanGearString(item.builtInEmbellishmentLabel) || '美化'
}

function gearHandednessBadgeLabel(item) {
  const direct = cleanGearString(item && item.handednessLabel)
  if (direct) return direct
  const weaponType = cleanGearString(item && item.weaponType).toLowerCase()
  if (!weaponType) return ''
  if (weaponType.includes('two-handed') || weaponType.includes('polearm') || weaponType.includes('staff')) return '双手'
  if (weaponType.includes('bow') || weaponType.includes('crossbow') || weaponType.includes('gun')) return '远程'
  if (
    weaponType.includes('one-handed') ||
    weaponType.includes('dagger') ||
    weaponType.includes('fist') ||
    weaponType.includes('warglaive') ||
    weaponType.includes('wand')
  ) return '单手'
  if (weaponType.includes('shield')) return '盾牌'
  if (weaponType.includes('held in off-hand')) return '副手'
  return ''
}

function truthyGearFlag(value) {
  if (typeof value === 'boolean') return value
  const text = cleanGearString(value).toLowerCase()
  if (!text) return false
  return !['0', 'false', 'no', 'none', 'null'].includes(text)
}

function gearUniqueBadgeLabel(item) {
  if (!item || typeof item !== 'object') return ''
  if (!truthyGearFlag(item.uniqueEquipped || item.unique_equipped)) return ''
  return cleanGearString(item.uniqueEquippedLabel || item.uniqueLabel) || '唯一'
}

function gearEquipmentBadgeLabels(item) {
  if (!item || typeof item !== 'object') return []
  const labels = []
  const addLabel = (label) => {
    const text = cleanGearString(label)
    if (text && !labels.includes(text)) labels.push(text)
  }
  const backendBadges = Array.isArray(item.equipmentBadges) ? item.equipmentBadges : []
  backendBadges.forEach((badge) => {
    if (typeof badge === 'string') addLabel(badge)
    else if (badge && typeof badge === 'object') addLabel(badge.label || badge.name || badge.displayLabel)
  })
  addLabel(gearHandednessBadgeLabel(item))
  addLabel(gearUniqueBadgeLabel(item))
  const embellishmentLabel = gearBuiltInEmbellishmentBadgeLabel(item)
  return labels.filter((label) => label !== embellishmentLabel)
}

function enhancementRecordMatchesCurrentItem(gearPayload, item, enhancementRecord, optionKey, type) {
  if (!enhancementRecordHasSelectedType(enhancementRecord, type)) return false
  if (enhancementRecordMatchesEmbeddedItem(item, enhancementRecord, type)) return true
  const options = enhancementOptionsForSlot(gearPayload, item, optionKey)
  if (!options.length) return itemSupportsConfiguredEnhancementFallback(item, type)
  if (!itemSupportsEnhancement(item, type, options)) return false
  return options.some((option) => enhancementOptionSelected(option, enhancementRecord, type))
}

function enhancementRecordMatchesEmbeddedItem(item, enhancementRecord, type) {
  if (!item || !enhancementRecord || typeof item !== 'object' || typeof enhancementRecord !== 'object') return false
  if (type === 'gem') {
    return !!(
      (cleanGearString(enhancementRecord.gem_id) && cleanGearString(enhancementRecord.gem_id) === cleanGearString(item.gem_id)) ||
      (cleanGearString(enhancementRecord.gem_bonus_id) && cleanGearString(enhancementRecord.gem_bonus_id) === cleanGearString(item.gem_bonus_id)) ||
      (cleanGearString(enhancementRecord.gem_ilevel) && cleanGearString(enhancementRecord.gem_ilevel) === cleanGearString(item.gem_ilevel))
    )
  }
  if (type === 'enchant') {
    return !!(
      cleanGearString(enhancementRecord.enchant_id) &&
      cleanGearString(enhancementRecord.enchant_id) === cleanGearString(item.enchant_id)
    )
  }
  if (type === 'embellishment') {
    const embedded = cleanGearString(item.embellishment || builtInEmbellishmentValue(item))
    return !!(cleanGearString(enhancementRecord.embellishment) && cleanGearString(enhancementRecord.embellishment) === embedded)
  }
  return false
}

function gearSlotEnhancementBadgeLabels(gearPayload, item, enhancementRecord) {
  const labels = []
  const addLabel = (label) => {
    if (!labels.includes(label)) labels.push(label)
  }
  if (enhancementRecordMatchesCurrentItem(gearPayload, item, enhancementRecord, 'socketOptions', 'gem')) addLabel('宝石')
  if (enhancementRecordMatchesCurrentItem(gearPayload, item, enhancementRecord, 'enchantOptions', 'enchant')) addLabel('附魔')
  if (enhancementRecordMatchesCurrentItem(gearPayload, item, enhancementRecord, 'embellishmentOptions', 'embellishment')) addLabel('美化')
  if (gearBuiltInEmbellishmentBadgeLabel(item)) addLabel('美化')
  return labels
}

function enhancementOptionIdentity(option) {
  return cleanGearString(option && (option.optionKey || option.option_key || option.id || option.key))
}

function enhancementOptionSelected(option, selected, type) {
  const simcOptions = option && option.simcOptions && typeof option.simcOptions === 'object' ? option.simcOptions : {}
  const optionId = enhancementOptionIdentity(option)
  if (type === 'gem') {
    const gemOptionIds = normalizedOptionIdentityList(selected.gemOptionIds)
    if (gemOptionIds.length) return gemOptionIds.includes(optionId)
    return !!(
      (selected.socketOptionId && optionId === selected.socketOptionId) ||
      (selected.gem_id && cleanGearString(simcOptions.gem_id) === selected.gem_id)
    )
  }
  if (type === 'enchant') {
    return !!(
      (selected.enchantOptionId && optionId === selected.enchantOptionId) ||
      (selected.enchant_id && cleanGearString(simcOptions.enchant_id) === selected.enchant_id)
    )
  }
  if (type === 'embellishment') {
    return !!(
      (selected.embellishmentOptionId && optionId === selected.embellishmentOptionId) ||
      (selected.embellishment && cleanGearString(simcOptions.embellishment) === selected.embellishment)
    )
  }
  return false
}

function textContainsCjk(value) {
  return /[\u3400-\u9fff]/.test(String(value || ''))
}

function optionItemStatSummary(option) {
  const stats = Array.isArray(option.itemStats) ? option.itemStats : (Array.isArray(option.stats) ? option.stats : [])
  const parts = []
  const seen = new Set()
  stats.forEach((stat) => {
    if (!stat || typeof stat !== 'object') return
    const label = cleanGearString(stat.label || (stat.type && stat.type.name) || stat.name || stat.stat).replace(/爆击/g, '暴击')
    const value = cleanGearString(stat.value || stat.amount)
    const displayValue = value && /^\d+(\.\d+)?$/.test(value) ? `+${value}` : value
    const part = label && displayValue ? `${displayValue}${label}` : (label || cleanGearString(stat.display))
    if (!part || seen.has(part)) return
    seen.add(part)
    parts.push(part)
  })
  return parts.join(' ')
}

function optionPayload(option) {
  return option && option.payload && typeof option.payload === 'object' ? option.payload : {}
}

function optionFirstValue(option, keys) {
  const payload = optionPayload(option)
  const keyList = Array.isArray(keys) ? keys : [keys]
  for (const source of [option || {}, payload]) {
    for (const key of keyList) {
      const value = source[key]
      if (value !== undefined && value !== null && value !== '') return value
    }
  }
  return ''
}

function optionGemIds(option) {
  const simcOptions = option && option.simcOptions && typeof option.simcOptions === 'object' ? option.simcOptions : {}
  const gemIdText = cleanGearString(simcOptions.gem_id || optionFirstValue(option, ['gemItemId', 'gem_item_id']))
  return gemIdText ? gemIdText.split('/').map((value) => cleanGearString(value)).filter(Boolean) : []
}

function enhancementOptionUniqueGroup(option, type) {
  const explicitGroup = cleanGearString(optionFirstValue(option, ['uniqueGroup', 'unique_group', 'uniqueKey', 'unique_key']))
  if (explicitGroup) return explicitGroup
  if (type === 'gem' && optionGemIds(option).some((gemId) => primaryStatGemIds.has(gemId))) {
    return primaryStatGemUniqueGroup
  }
  return ''
}

function enhancementOptionUniqueLimit(option, type) {
  const rawLimit = optionFirstValue(option, ['uniqueLimit', 'unique_limit', 'uniqueEquippedLimit', 'unique_equipped_limit'])
  const parsed = Number.parseInt(rawLimit, 10)
  if (Number.isFinite(parsed) && parsed > 0) return parsed
  return enhancementOptionUniqueGroup(option, type) ? primaryStatGemUniqueLimit : 0
}

function enhancementUniqueGroupLabel(group, type) {
  if (type === 'gem' && group === primaryStatGemUniqueGroup) return '主属性宝石'
  return group || '唯一强化'
}

function optionDisplayStatus(option) {
  const payload = optionPayload(option)
  return cleanGearString(option.displayStatus || option.display_status || payload.displayStatus || payload.display_status).toLowerCase()
}

function optionEvidenceSource(option) {
  const payload = optionPayload(option)
  return cleanGearString(option.evidenceSource || option.evidence_source || option.displaySource || option.display_source || payload.evidenceSource || payload.evidence_source || payload.displaySource || payload.display_source || payload.metadataSource)
}

function optionDisplayLabel(option) {
  const payload = optionPayload(option)
  return cleanGearString(
    option.displayLabel ||
    option.display_label ||
    payload.displayLabel ||
    payload.display_label ||
    option.displayName ||
    payload.displayName ||
    option.label ||
    option.name
  )
}

function enhancementLabelLooksLikeFallback(label, type) {
  const value = cleanGearString(label)
  if (!value) return true
  if (/^(gem|enchant|embellishment|observed|server seed)\b/i.test(value)) return true
  if (/\$/.test(value) || /\|[A-Za-z]:/.test(value)) return true
  if (type === 'enchant' && /^(附魔|武器附魔|戒指附魔|披风附魔|胸甲附魔|护腕附魔|靴子附魔|腿部强化)\s*[\d/]*$/i.test(value)) return true
  if (type === 'gem' && /^(宝石|gem)\s*[\d/]+$/i.test(value)) return true
  return false
}

function enhancementOptionRecordVerified(option) {
  const displayStatus = optionDisplayStatus(option || {})
  if (displayStatus && displayStatus !== 'verified') return false
  const status = cleanGearString(optionFirstValue(option || {}, 'status') || 'verified').toLowerCase()
  return !status || status === 'verified'
}

function enhancementOptionHasAuthoritativeLabelField(option) {
  const payload = optionPayload(option || {})
  return !!cleanGearString(
    (option && (option.label || option.displayLabel || option.display_label)) ||
    payload.label ||
    payload.displayLabel ||
    payload.display_label
  )
}

function verifiedGenericEnhancementOptionLabel(option, type) {
  if (!enhancementOptionRecordVerified(option || {})) return ''
  if (!enhancementOptionHasAuthoritativeLabelField(option || {})) return ''
  const simcOptions = option && option.simcOptions && typeof option.simcOptions === 'object' ? option.simcOptions : {}
  if (type === 'gem') {
    const gemIds = optionGemIds(option || {})
    return gemIds.length ? `\u5b9d\u77f3 ${gemIds.join('/')}` : ''
  }
  if (type === 'enchant') {
    const enchantId = cleanGearString(simcOptions.enchant_id || optionFirstValue(option || {}, ['enchantId', 'enchant_id']))
    return enchantId ? `\u9644\u9b54 ${enchantId}` : ''
  }
  if (type === 'embellishment') {
    const embellishment = cleanGearString(simcOptions.embellishment || optionFirstValue(option || {}, ['embellishment', 'embellishmentId', 'embellishment_id']))
    return embellishment ? embellishment.replace(/[_-]+/g, ' ') : ''
  }
  return ''
}

function readableEnhancementOptionLabel(option, type) {
  const record = option || {}
  const explicitLabel = optionDisplayLabel(record)
  const fallbackLabel = verifiedGenericEnhancementOptionLabel(record, type)
  if (type === 'gem') {
    const payload = optionPayload(record)
    const explicitGemLabel = cleanGearString(record.label || payload.label)
    const readableExplicitLabel = explicitGemLabel && !enhancementLabelLooksLikeFallback(explicitGemLabel, type) ? explicitGemLabel : ''
    return cleanGearString(
      record.displayLabel ||
      record.display_label ||
      payload.displayLabel ||
      payload.display_label ||
      record.statSummary ||
      record.stat_summary ||
      record.summary ||
      record.valueSummary ||
      payload.statSummary ||
      payload.summary ||
      readableExplicitLabel
    ) || optionItemStatSummary(record) || fallbackLabel
  }
  const payload = optionPayload(record)
  const hasExplicitDisplayLabel = !!cleanGearString(record.displayLabel || record.display_label || payload.displayLabel || payload.display_label)
  const evidenceSource = optionEvidenceSource(record)
  if (!enhancementOptionRecordVerified(record)) return ''
  if (enhancementLabelLooksLikeFallback(explicitLabel, type)) return fallbackLabel
  if (!textContainsCjk(explicitLabel) && !hasExplicitDisplayLabel && !evidenceSource) return fallbackLabel
  return explicitLabel || fallbackLabel
}

function enhancementOptionForData(option, selected, type, disabled, slot) {
  const simcOptions = option && option.simcOptions && typeof option.simcOptions === 'object' ? option.simcOptions : {}
  const isSelected = enhancementOptionSelected(option, selected || {}, type)
  const displayLabel = readableEnhancementOptionLabel(option || {}, type)
  if (!displayLabel) return null
  const uniqueGroup = enhancementOptionUniqueGroup(option || {}, type)
  const uniqueLimit = enhancementOptionUniqueLimit(option || {}, type)
  const isDisabled = typeof disabled === 'function' ? disabled(option || {}, isSelected, slot) : disabled
  return {
    id: enhancementOptionIdentity(option) || cleanGearString(option.label || option.name),
    label: displayLabel,
    selected: isSelected,
    disabled: !!(isDisabled && !isSelected),
    simcOptions,
    uniqueGroup,
    uniqueLimit
  }
}

function enhancementRow(slot, item, options, selected, type, disabled) {
  const displayOptions = options
    .map((option) => enhancementOptionForData(option, selected || {}, type, disabled, slot))
    .filter(Boolean)
  return {
    slot,
    label: gearSlotDisplayLabels[slot] || slot,
    itemName: itemDisplayName(item),
    selectedLabel: (displayOptions.find((option) => option.selected) || {}).label || '',
    options: displayOptions
  }
}

function emptyGearEnhancementSheet() {
  return {
    visible: false,
    equipmentRows: [],
    activeSlot: '',
    activeTitle: '',
    activeItemName: '',
    activeGemRows: [],
    activeEnchantRows: [],
    activeEmbellishmentRows: [],
    activeInheritedRows: [],
    gemRows: [],
    enchantRows: [],
    embellishmentRows: [],
    confirmedEnhancementBySlot: {},
    inheritedCount: 0,
    embellishmentUsed: 0,
    embellishmentMax: gearEnhancementMax,
    warnings: [],
    blockers: [],
    emptyText: ''
  }
}

function gearEnhancementSlotSortKey(slot, fallbackIndex) {
  const priorityIndex = gearEnhancementSlotOrder.indexOf(slot)
  return [
    priorityIndex >= 0 ? priorityIndex : gearEnhancementSlotOrder.length,
    fallbackIndex
  ]
}

function buildGearEnhancementEquipmentRows(slots, indexed, gemRows, enchantRows, embellishmentRows, activeSlot, pendingSlots) {
  const rowMaps = {
    gem: new Map(gemRows.map((row) => [row.slot, row])),
    enchant: new Map(enchantRows.map((row) => [row.slot, row])),
    embellishment: new Map(embellishmentRows.map((row) => [row.slot, row]))
  }
  return (slots || []).map((slot) => {
    const typeLabels = []
    if (rowMaps.gem.has(slot)) typeLabels.push('宝石')
    if (rowMaps.enchant.has(slot)) typeLabels.push('附魔')
    if (rowMaps.embellishment.has(slot)) typeLabels.push('美化')
    if (!typeLabels.length && pendingSlots && pendingSlots.has(slot)) typeLabels.push('加载选项')
    if (!typeLabels.length) return null
    const item = indexed[slot] || {}
    return {
      slot,
      label: gearSlotDisplayLabels[slot] || slot,
      itemName: itemDisplayName(item),
      typeSummary: typeLabels.join(' / '),
      active: slot === activeSlot
    }
  }).filter(Boolean)
}

function selectedEnhancementUniqueGroups(gearPayload, indexed, enhancement, type) {
  const state = {}
  if (type !== 'gem') return state
  requiredGearTemplateSlots(gearPayload || {}).forEach((slot) => {
    const item = indexed[slot]
    const selected = enhancement[slot] || {}
    if (!item || !enhancementRecordHasSelectedType(selected, type)) return
    const options = enhancementOptionsForSlot(gearPayload, item, 'socketOptions')
    options.filter((option) => enhancementOptionSelected(option, selected, type)).forEach((selectedOption) => {
      const group = enhancementOptionUniqueGroup(selectedOption, type)
      if (!group) return
      const limit = enhancementOptionUniqueLimit(selectedOption, type) || 1
      if (!state[group]) state[group] = { limit, slots: [] }
      state[group].limit = Math.min(state[group].limit || limit, limit)
      state[group].slots.push(slot)
    })
  })
  return state
}

function gemOptionIdentityBlockers(gearPayload, indexed, enhancement) {
  const blockers = []
  Object.keys(enhancement || {}).forEach((slot) => {
    const gemOptionIds = normalizedOptionIdentityList(enhancement[slot] && enhancement[slot].gemOptionIds)
    if (!gemOptionIds.length) return
    const item = indexed && indexed[slot]
    if (!item) {
      blockers.push(`${gearSlotDisplay(slot)} 宝石选项当前不可用：${gemOptionIds.join('、')}`)
      return
    }
    const socketCapacity = gearItemSocketCapacity(item)
    if (gemOptionIds.length > socketCapacity) {
      blockers.push(`${gearSlotDisplay(slot)} 宝石已超过插槽上限 ${gemOptionIds.length}/${socketCapacity}`)
    }
    const availableOptionIds = new Set(
      enhancementOptionsForSlot(gearPayload, item, 'socketOptions')
        .map(enhancementOptionIdentity)
        .filter(Boolean)
    )
    const unmatchedOptionIds = gemOptionIds.filter((id) => !availableOptionIds.has(id))
    if (unmatchedOptionIds.length) {
      blockers.push(`${gearSlotDisplay(slot)} 宝石选项当前不可用：${unmatchedOptionIds.join('、')}`)
    }
  })
  return blockers
}

function buildGearEnhancementSheet(gearPayload, selectedGearBySlot, enhancementBySlot, visible, requestedActiveSlot) {
  const indexed = enrichedSelectedGearByCanonicalSlot(gearPayload, selectedGearBySlot || {})
  const enhancement = normalizedEnhancementBySlot(enhancementBySlot || {})
  const builtInCount = Object.keys(indexed).filter((slot) => builtInEmbellishmentValue(indexed[slot])).length
  const selectedEmbellishmentCount = Object.keys(enhancement).filter((slot) => (
    cleanGearString(enhancement[slot].embellishmentOptionId) || cleanGearString(enhancement[slot].embellishment)
  )).length
  const embellishmentUsed = builtInCount + selectedEmbellishmentCount
  const gemUniqueGroups = selectedEnhancementUniqueGroups(gearPayload, indexed, enhancement, 'gem')
  const gemRows = []
  const enchantRows = []
  const embellishmentRows = []
  const warnings = []
  const blockers = stringList(gearPayload && gearPayload.gearLegalityBlockers)
  blockers.push(...gemOptionIdentityBlockers(gearPayload, indexed, enhancement))
  if (embellishmentUsed > gearEnhancementMax) {
    blockers.push(`美化已超过上限 ${embellishmentUsed}/${gearEnhancementMax}`)
  }
  Object.keys(gemUniqueGroups).forEach((group) => {
    const state = gemUniqueGroups[group]
    const limit = state.limit || 1
    const count = (state.slots || []).length
    if (count > limit) {
      blockers.push(`${enhancementUniqueGroupLabel(group, 'gem')}已超过上限 ${count}/${limit}`)
    }
  })
  requiredGearTemplateSlots(gearPayload || {}).forEach((slot) => {
    const item = indexed[slot]
    if (!item) return
    const selected = enhancement[slot] || {}
    const socketOptions = enhancementOptionsForSlot(gearPayload, item, 'socketOptions')
    const enchantOptions = enhancementOptionsForSlot(gearPayload, item, 'enchantOptions')
    const embellishmentOptions = enhancementOptionsForSlot(gearPayload, item, 'embellishmentOptions')
    const runeforgeWarning = deathKnightRuneforgeWarningForItem(gearPayload, item)
    if (runeforgeWarning && !warnings.includes(runeforgeWarning)) warnings.push(runeforgeWarning)
    const selectedGemCount = enhancementRecordSelectedCount(selected, 'gem')
    const socketCapacity = gearItemSocketCapacity(item)
    if (selectedGemCount > socketCapacity) {
      const blocker = `${gearSlotDisplay(slot)} 宝石已超过插槽上限 ${selectedGemCount}/${socketCapacity}`
      if (!blockers.includes(blocker)) blockers.push(blocker)
    }
    if (socketOptions.length && itemSupportsEnhancement(item, 'gem', socketOptions)) {
      const row = enhancementRow(slot, item, socketOptions, selected, 'gem', (option, isSelected) => {
        if (isSelected) return false
        if (selectedGemCount >= socketCapacity) return true
        const group = enhancementOptionUniqueGroup(option, 'gem')
        if (!group) return false
        const limit = enhancementOptionUniqueLimit(option, 'gem') || 1
        const state = gemUniqueGroups[group] || { slots: [] }
        return (state.slots || []).length >= limit
      })
      if (row.options.length) gemRows.push(row)
    } else if (selected.gem_id) {
      blockers.push(`${gearSlotDisplay(slot)} 宝石已不兼容`)
    }
    if (enchantOptions.length && itemSupportsEnhancement(item, 'enchant', enchantOptions)) {
      const row = enhancementRow(slot, item, enchantOptions, selected, 'enchant', false)
      if (row.options.length) enchantRows.push(row)
    } else if (selected.enchant_id) {
      blockers.push(`${gearSlotDisplay(slot)} 附魔已不兼容`)
    }
    if (embellishmentOptions.length && itemSupportsEnhancement(item, 'embellishment', embellishmentOptions) && !builtInEmbellishmentValue(item)) {
      const row = enhancementRow(slot, item, embellishmentOptions, selected, 'embellishment', embellishmentUsed >= gearEnhancementMax)
      if (row.options.length) embellishmentRows.push(row)
    } else if (selected.embellishment) {
      blockers.push(`${gearSlotDisplay(slot)} 美化已不兼容`)
    }
  })
  const emptyText = gemRows.length || enchantRows.length || embellishmentRows.length
    ? ''
    : '当前已选装备没有可配置的宝石、附魔或美化。'
  const configurableSlots = requiredGearTemplateSlots(gearPayload || {}).filter((slot) => {
    return gemRows.some((row) => row.slot === slot) ||
      enchantRows.some((row) => row.slot === slot) ||
      embellishmentRows.some((row) => row.slot === slot)
  }).sort((left, right) => {
    const allSlots = requiredGearTemplateSlots(gearPayload || {})
    const leftKey = gearEnhancementSlotSortKey(left, allSlots.indexOf(left))
    const rightKey = gearEnhancementSlotSortKey(right, allSlots.indexOf(right))
    return leftKey[0] - rightKey[0] || leftKey[1] - rightKey[1]
  })
  const activeSlot = configurableSlots.includes(requestedActiveSlot) ? requestedActiveSlot : (configurableSlots[0] || '')
  const equipmentRows = buildGearEnhancementEquipmentRows(configurableSlots, indexed, gemRows, enchantRows, embellishmentRows, activeSlot)
  const activeGemRows = activeSlot ? gemRows.filter((row) => row.slot === activeSlot) : []
  const activeEnchantRows = activeSlot ? enchantRows.filter((row) => row.slot === activeSlot) : []
  const activeEmbellishmentRows = activeSlot ? embellishmentRows.filter((row) => row.slot === activeSlot) : []
  return {
    visible: !!visible,
    loading: false,
    draftEnhancementBySlot: enhancement,
    equipmentRows,
    activeSlot,
    activeTitle: activeSlot ? (gearSlotDisplayLabels[activeSlot] || activeSlot) : '',
    activeItemName: activeSlot ? itemDisplayName(indexed[activeSlot]) : '',
    activeGemRows,
    activeEnchantRows,
    activeEmbellishmentRows,
    gemRows,
    enchantRows,
    embellishmentRows,
    embellishmentUsed,
    embellishmentMax: gearEnhancementMax,
    warnings,
    blockers,
    emptyText
  }
}

function prunedEnhancementBySlot(gearPayload, selectedGearBySlot, enhancementBySlot) {
  const sheet = buildGearEnhancementSheet(gearPayload, selectedGearBySlot, enhancementBySlot, true)
  const rowsByType = {
    gem: new Map(sheet.gemRows.map((row) => [row.slot, row])),
    enchant: new Map(sheet.enchantRows.map((row) => [row.slot, row])),
    embellishment: new Map(sheet.embellishmentRows.map((row) => [row.slot, row]))
  }
  const normalized = normalizedEnhancementBySlot(enhancementBySlot)
  const indexed = enrichedSelectedGearByCanonicalSlot(gearPayload, selectedGearBySlot || {})
  const rowKeepsSelection = (type, slot) => {
    const row = rowsByType[type].get(slot)
    return !!(
      (row && Array.isArray(row.options) && row.options.some((option) => option.selected)) ||
      enhancementRecordMatchesEmbeddedItem(indexed[slot], normalized[slot], type)
    )
  }
  Object.keys(normalized).forEach((slot) => {
    const gemOptionIds = normalizedOptionIdentityList(normalized[slot].gemOptionIds)
    if (gemOptionIds.length) {
      const row = rowsByType.gem.get(slot)
      const selectedOptionIds = new Set(
        row && Array.isArray(row.options)
          ? row.options.filter((option) => option.selected).map((option) => cleanGearString(option.id)).filter(Boolean)
          : []
      )
      const retainedGemOptionIds = gemOptionIds.filter((id) => selectedOptionIds.has(id))
      if (retainedGemOptionIds.length) normalized[slot].gemOptionIds = retainedGemOptionIds
      else delete normalized[slot].gemOptionIds
      delete normalized[slot].socketOptionId
      delete normalized[slot].gem_id
      delete normalized[slot].gem_bonus_id
      delete normalized[slot].gem_ilevel
    } else if (!rowKeepsSelection('gem', slot)) {
      delete normalized[slot].socketOptionId
      delete normalized[slot].gem_id
      delete normalized[slot].gem_bonus_id
      delete normalized[slot].gem_ilevel
    }
    if (!rowKeepsSelection('enchant', slot)) {
      delete normalized[slot].enchantOptionId
      delete normalized[slot].enchant_id
    }
    if (!rowKeepsSelection('embellishment', slot)) {
      delete normalized[slot].embellishmentOptionId
      delete normalized[slot].embellishment
    }
    if (!Object.keys(normalized[slot]).length) delete normalized[slot]
  })
  return normalized
}

function enhancementSelectionFromOption(type, option, record) {
  const simcOptions = option && option.simcOptions && typeof option.simcOptions === 'object' ? option.simcOptions : {}
  if (type === 'gem') {
    const currentGemOptionIds = normalizedOptionIdentityList(record && record.gemOptionIds)
    const legacyOptionId = cleanGearString(record && record.socketOptionId)
    const optionId = cleanGearString(option.id)
    return {
      gemOptionIds: normalizedOptionIdentityList([
        ...(currentGemOptionIds.length ? currentGemOptionIds : (legacyOptionId ? [legacyOptionId] : [])),
        optionId
      ]),
      socketOptionId: '',
      gem_id: '',
      gem_bonus_id: '',
      gem_ilevel: ''
    }
  }
  if (type === 'enchant') {
    return {
      enchantOptionId: cleanGearString(option.id),
      enchant_id: cleanGearString(simcOptions.enchant_id)
    }
  }
  if (type === 'embellishment') {
    return {
      embellishmentOptionId: cleanGearString(option.id),
      embellishment: cleanGearString(simcOptions.embellishment)
    }
  }
  return {}
}

function removeEnhancementType(record, type, optionId) {
  const next = { ...(record || {}) }
  if (type === 'gem') {
    const gemOptionIds = normalizedOptionIdentityList(next.gemOptionIds)
    const removedOptionId = cleanGearString(optionId)
    const remainingGemOptionIds = removedOptionId
      ? gemOptionIds.filter((id) => id !== removedOptionId)
      : []
    if (remainingGemOptionIds.length) next.gemOptionIds = remainingGemOptionIds
    else delete next.gemOptionIds
    delete next.socketOptionId
    delete next.gem_id
    delete next.gem_bonus_id
    delete next.gem_ilevel
  } else if (type === 'enchant') {
    delete next.enchantOptionId
    delete next.enchant_id
  } else if (type === 'embellishment') {
    delete next.embellishmentOptionId
    delete next.embellishment
  }
  return next
}

function compactEnhancementRecord(record) {
  const next = {}
  const gemOptionIds = normalizedOptionIdentityList(record && record.gemOptionIds)
  if (gemOptionIds.length) next.gemOptionIds = gemOptionIds
  ;['socketOptionId', 'enchantOptionId', 'embellishmentOptionId', 'gem_id', 'gem_bonus_id', 'gem_ilevel', 'enchant_id', 'embellishment'].forEach((key) => {
    const value = cleanGearString(record && record[key])
    if (value) next[key] = value
  })
  return Object.keys(next).length ? next : null
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

function optionalGearSlotsForPayload(gearPayload) {
  const readiness = gearPayload && gearPayload.readiness ? gearPayload.readiness : {}
  if (!readiness.fullReady) return []
  const missingRequired = new Set(Array.isArray(readiness.missingRequiredSlots) ? readiness.missingRequiredSlots : [])
  const missingCore = new Set(Array.isArray(readiness.missingCoreSlots) ? readiness.missingCoreSlots : [])
  return requiredGearSlots.filter((slot) => slot === 'off_hand' && missingRequired.has(slot) && !missingCore.has(slot))
}

function requiredGearTemplateSlots(gearPayload) {
  const optionalSlots = new Set(optionalGearSlotsForPayload(gearPayload))
  return requiredGearSlots.filter((slot) => !optionalSlots.has(slot))
}

function canonicalGearTemplateLines(selectedGearBySlot, gearPayload) {
  const indexed = selectedGearByCanonicalSlot(selectedGearBySlot)
  return requiredGearTemplateSlots(gearPayload).map((slot) => gearTemplateLine(indexed[slot])).filter(Boolean)
}

function missingGearConfigSlots(selectedGearBySlot, gearPayload) {
  const indexed = selectedGearByCanonicalSlot(selectedGearBySlot)
  return requiredGearTemplateSlots(gearPayload).filter((slot) => !gearTemplateLine(indexed[slot]))
}

function gearTemplateValidationIssues(selectedGearBySlot, gearPayload) {
  const indexed = selectedGearByCanonicalSlot(selectedGearBySlot)
  return requiredGearTemplateSlots(gearPayload).map((slot) => {
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

function gearTemplateValidationMessage(issues, requiredCount) {
  const list = Array.isArray(issues) ? issues : []
  if (!list.length) return ''
  const details = list.slice(0, 3).map((item) => item.message).join('；')
  const more = list.length > 3 ? `；另有 ${list.length - 3} 个槽位` : ''
  const hasMissingSlot = list.some((item) => /缺少装备/.test(item.message))
  const slotCount = Number(requiredCount) || requiredGearSlots.length
  return `${hasMissingSlot ? `请补齐 ${slotCount} 个装备槽位` : '请先修正装备槽位'}：${details}${more}`
}

function gearTemplateWarningSummary(statPendingSlots, sourcePendingSlots) {
  const parts = []
  if (statPendingSlots.length) parts.push(`属性待补 ${statPendingSlots.length} 槽`)
  if (sourcePendingSlots.length) parts.push(`来源待补 ${sourcePendingSlots.length} 槽`)
  return parts.join('；')
}

function gearTemplateWarningStatusLabel(statPendingSlots, sourcePendingSlots) {
  if (statPendingSlots.length && sourcePendingSlots.length) return '完整配置 · 属性/来源待补'
  if (statPendingSlots.length) return '完整配置 · 属性待补'
  if (sourcePendingSlots.length) return '完整配置 · 来源待补'
  return '完整配置'
}

function gearTemplateStatus(selectedGearBySlot, gearPayload) {
  const requiredSlots = requiredGearTemplateSlots(gearPayload)
  const issues = gearTemplateValidationIssues(selectedGearBySlot, gearPayload)
  if (issues.length) {
    return { status: 'partial', statusLabel: '缺字段', missingSlots: issues.map((item) => item.slot), issues, requiredSlots, statPendingSlots: [], sourcePendingSlots: [], warningSummary: '' }
  }
  const indexed = selectedGearByCanonicalSlot(selectedGearBySlot)
  const statPendingSlots = requiredSlots.filter((slot) => {
    const item = indexed[slot]
    return !!(item && item.simcReady && gearCandidateStatsPending(item))
  })
  const sourcePendingSlots = requiredSlots.filter((slot) => {
    const item = indexed[slot]
    return !!(item && item.simcReady && !gearCandidateStatsPending(item) && gearCandidateDropSourcePending(item))
  })
  if (statPendingSlots.length || sourcePendingSlots.length) {
    return {
      status: 'complete_with_warnings',
      statusLabel: gearTemplateWarningStatusLabel(statPendingSlots, sourcePendingSlots),
      missingSlots: [],
      issues: [],
      requiredSlots,
      statPendingSlots,
      sourcePendingSlots,
      warningSummary: gearTemplateWarningSummary(statPendingSlots, sourcePendingSlots)
    }
  }
  return { status: 'complete', statusLabel: '完整配置', missingSlots: [], issues: [], requiredSlots, statPendingSlots: [], sourcePendingSlots: [], warningSummary: '' }
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

function trimGearTemplateTitle(title) {
  const text = String(title || '').replace(/\s+/g, ' ').trim()
  if (!text) return ''
  return text.length > maxGearTemplateTitleLength ? text.slice(0, maxGearTemplateTitleLength) : text
}

function gearTemplateTitleOrDefault(value, fallback) {
  return trimGearTemplateTitle(value) || trimGearTemplateTitle(fallback) || '装备模板'
}

function emptyGearSaveTemplateSheet() {
  return { visible: false, name: '', defaultName: '' }
}

function gearTemplateSaveDraft(page, templateTitle) {
  const data = page.data || {}
  if (data.gearDataFallback) {
    return { blockMessage: data.gearDataWarningText || '装备接口暂不可用，无法保存装备模板' }
  }
  const workbenchState = page.gearWorkbenchState
  if (workbenchState && !gearWorkbenchCanUseVerifiedSnapshot(workbenchState)) {
    return { blockMessage: '当前装备配置尚未通过服务端校验，暂不能保存' }
  }
  const gearPayload = fullGearPayloadForPage(page) || data.gearPayload || {}
  const selectedGearBySlot = prunedGearSelectionByWeaponRule(gearPayload, data.selectedGearBySlot || {})
  const selectedItems = selectedGearItems(selectedGearBySlot)
  const configLines = canonicalGearTemplateLines(selectedGearBySlot, gearPayload)
  const resolvedSnapshot = workbenchState && workbenchState.currentSnapshot
  const canonicalReadiness = resolvedSnapshot && resolvedSnapshot.profileReadiness
  const status = workbenchState
    ? {
        status: 'complete',
        statusLabel: '已校验配置',
        missingSlots: [],
        issues: [],
        requiredSlots: Array.isArray(canonicalReadiness && canonicalReadiness.requiredSlots) ? canonicalReadiness.requiredSlots : [],
        statPendingSlots: [],
        sourcePendingSlots: [],
        warningSummary: ''
      }
    : gearTemplateStatus(selectedGearBySlot, gearPayload)
  const requiredCount = (status.requiredSlots || requiredGearSlots).length
  if (!workbenchState && (status.missingSlots.length || configLines.length !== requiredCount)) {
    return {
      blockMessage: gearTemplateValidationMessage(status.issues, requiredCount) || `请补齐 ${requiredCount} 个装备槽位后再保存`,
      state: { selectedGearBySlot }
    }
  }
  const scenario = gearScenarioAt(data.selectedGearTemplateScenarioIndex)
  const selectedDetail = data.selectedDetail || {}
  const selectedSpec = data.selectedSpec || {}
  const keys = specWebsimKeys(selectedSpec)
  const enhancementBySlot = prunedEnhancementBySlot(gearPayload, selectedGearBySlot, data.enhancementBySlot || {})
  const enhancementSheet = buildGearEnhancementSheet(gearPayload, selectedGearBySlot, enhancementBySlot, false)
  if (!workbenchState && ((enhancementSheet.blockers || []).length || enhancementSheet.embellishmentUsed > enhancementSheet.embellishmentMax)) {
    return {
      blockMessage: (enhancementSheet.blockers || [])[0] || `美化已超过上限 ${enhancementSheet.embellishmentUsed}/${enhancementSheet.embellishmentMax}`,
      state: {
        selectedGearBySlot,
        enhancementBySlot,
        gearEnhancementSheet: {
          ...enhancementSheet,
          visible: data.gearEnhancementSheet && data.gearEnhancementSheet.visible
        }
      }
    }
  }
  const snapshot = gearTemplateSnapshot(selectedGearBySlot, enhancementBySlot, gearPayload)
  const statState = page && page.gearStatSnapshotState
  const statSnapshot = statState && statState.statSnapshotStatus === 'verified'
    ? compactVerifiedGearStatSnapshot(statState.currentStatSnapshot)
    : null
  const defaultName = gearTemplateTitle(
    selectedDetail.className || selectedSpec.className || '',
    selectedDetail.specName || selectedSpec.title || selectedSpec.specName || '',
    scenario.title
  )
  return {
    defaultName,
    selectedGearBySlot,
    enhancementBySlot,
    record: {
      type: 'gear',
      title: gearTemplateTitleOrDefault(templateTitle, defaultName),
      classKey: keys.classKey,
      className: selectedDetail.className || selectedSpec.className || '',
      specKey: keys.specKey,
      specName: selectedDetail.specName || selectedSpec.title || selectedSpec.specName || '',
      scenarioKey: scenario.key,
      scenarioTitle: scenario.title,
      rawString: JSON.stringify(snapshot),
      simcLines: [],
      status: status.status,
      statusLabel: status.statusLabel,
      source: '装备模拟器',
      metadata: {
        ...(statSnapshot ? {
          statSnapshot,
          statSnapshotRequestSignature: statState.verifiedStatContextKey || '',
          statSnapshotSignature: statState.statSnapshotSignature || '',
          statSnapshotSource: statSnapshot.statSource || 'simulationcraft_json'
        } : {}),
        gearSnapshot: snapshot,
        gearBySlot: snapshot.gearBySlot,
        enhancementBySlot,
        selectedGearSnapshot: selectedGearBySlot,
        selectedItems,
        configLineCount: configLines.length,
        missingSlots: [],
        statPendingSlots: status.statPendingSlots || [],
        sourcePendingSlots: status.sourcePendingSlots || [],
        craftedStatSelections: craftedStatSelections(selectedGearBySlot),
        warningSummary: status.warningSummary || '',
        selectedItemCount: selectedItems.length,
        gearSchemaRevision: data.gearPayload && data.gearPayload.gearSchemaRevision,
        maxLevel: data.gearPayload && data.gearPayload.maxLevel,
        ...(resolvedSnapshot ? {
          selectionIntent: workbenchState.confirmedIntent,
          resolvedGearSignature: resolvedSnapshot.resolvedGearSignature || '',
          dependencyVector: resolvedSnapshot.dependencyVector || {}
        } : {})
      }
    }
  }
}

function persistGearTemplateForPage(page, templateTitle) {
  const draft = gearTemplateSaveDraft(page, templateTitle)
  if (draft.blockMessage) {
    if (draft.state) page.setData(draft.state)
    showToast(draft.blockMessage)
    return Promise.resolve(null)
  }
  page.setData({
    gearTemplateSaving: true,
    selectedGearBySlot: draft.selectedGearBySlot,
    enhancementBySlot: draft.enhancementBySlot
  })
  return syncBuildTemplate(draft.record).then(({ payload }) => {
    const saved = !!(payload && payload.template)
    if (saved) {
      page.setData({ gearSaveTemplateSheet: emptyGearSaveTemplateSheet() })
    }
    showToast(saved ? '装备模板已保存' : '装备模板保存失败')
  }).catch(() => {
    showToast('装备模板保存失败')
  }).finally(() => {
    page.setData({ gearTemplateSaving: false })
  })
}

function gearScenarioAt(index) {
  return gearTemplateScenarios[Math.max(0, Math.min(Number(index) || 0, gearTemplateScenarios.length - 1))] || gearTemplateScenarios[0]
}

function gearSourceValueNeedsEnrichment(value) {
  return !value || gearSimcPresetSourceLabel(value) || gearObservedSourceLabel(value)
}

function gearValueMissing(value) {
  return value === undefined || value === null || value === '' || (Array.isArray(value) && !value.length)
}

function matchingGearCandidateForItem(payload, slot, item) {
  const itemId = normalizedGearItemId(item)
  if (!payload || !slot || !itemId) return null
  const groups = gearGroupsBySlot(payload)
  const group = groups[slot] || {}
  const items = Array.isArray(group.items) ? group.items : []
  return items.find((candidate) => normalizedGearItemId(candidate) === itemId) || null
}

function applySimcReadyCandidateEvidence(enriched, candidate, item) {
  if (!candidate || !candidate.simcReady || (item && item.simcReady)) return enriched
  ;[
    'sourceType',
    'source',
    'sourceName',
    'displaySourceName',
    'name',
    'variantSource',
    'variantDifficultyKey',
    'blockers',
    'variantBlockers',
    'missingFields',
    'simcReady',
    'simcIlevelOnly'
  ].forEach((key) => {
    if (['missingFields', 'blockers', 'variantBlockers'].includes(key)) {
      if (Object.prototype.hasOwnProperty.call(candidate, key)) enriched[key] = candidate[key]
      return
    }
    if (!gearValueMissing(candidate[key])) enriched[key] = candidate[key]
  })
  return enriched
}

function enrichedGearItemFromCandidates(payload, slot, item) {
  if (!item) return item
  const candidate = matchingGearCandidateForItem(payload, slot, item)
  if (!candidate || candidate === item) return item
  const enriched = { ...candidate, ...item }
  ;[
    'sources',
    'observedProfileRefs',
    'statSummary',
    'stats',
    'itemStats',
    'attributes',
    'secondaryStats',
    'statDisplayStatus',
    'simcStatStatus',
    'simcStatFailureKind',
    'metadataStatus',
    'iconUrl',
    'displayName',
    'name',
    'variantSource',
    'variantDifficultyKey',
    'blockers',
    'variantBlockers'
  ].forEach((key) => {
    if (gearValueMissing(item[key]) && !gearValueMissing(candidate[key])) {
      enriched[key] = candidate[key]
    }
  })
  if (gearSourceValueNeedsEnrichment(item.source) && !gearSourceValueNeedsEnrichment(candidate.source)) {
    enriched.source = candidate.source
  }
  if (gearSourceValueNeedsEnrichment(item.sourceName) && !gearSourceValueNeedsEnrichment(candidate.sourceName)) {
    enriched.sourceName = candidate.sourceName
  }
  if (gearSourceValueNeedsEnrichment(item.displaySourceName) && !gearSourceValueNeedsEnrichment(candidate.displaySourceName)) {
    enriched.displaySourceName = candidate.displaySourceName
  }
  if (gearSourceValueNeedsEnrichment(item.sourceType) && !gearSourceValueNeedsEnrichment(candidate.sourceType)) {
    enriched.sourceType = candidate.sourceType
  }
  return applySimcReadyCandidateEvidence(enriched, candidate, item)
}

function enrichedSelectedGearByCanonicalSlot(payload, selectedGearBySlot) {
  const indexed = selectedGearByCanonicalSlot(selectedGearBySlot || {})
  const enriched = {}
  Object.keys(indexed).forEach((slot) => {
    enriched[slot] = enrichedGearItemFromCandidates(payload, slot, indexed[slot])
  })
  return enriched
}

function equippedSetToSelection(equippedSet, payload) {
  const selection = {}
  Object.keys(equippedSet || {}).forEach((slot) => {
    if (equippedSet[slot]) selection[slot] = enrichedGearItemFromCandidates(payload, slot, equippedSet[slot])
  })
  return selection
}

function emptyGearCommunityTemplateSheet() {
  return { visible: false }
}

function gearItemsToSelection(items, payload) {
  const selection = {}
  ;(items || []).forEach((item) => {
    const slot = item && (item.simcSlot || item.slot)
    if (!slot || !requiredGearSlots.includes(slot)) return
    const normalized = {
      ...item,
      slot: item.slot || slot,
      simcSlot: item.simcSlot || slot
    }
    selection[slot] = enrichedGearItemFromCandidates(payload, slot, normalized)
  })
  return selection
}

function templateShortDate(value) {
  const text = cleanGearString(value)
  if (!text) return ''
  return text.includes('T') ? text.split('T')[0] : text.slice(0, 10)
}

function parseSavedGearTemplateSnapshot(template) {
  const metadata = template && template.metadata && typeof template.metadata === 'object' ? template.metadata : {}
  let parsed = {}
  const rawString = cleanGearString(template && template.rawString)
  if (rawString) {
    try {
      const value = JSON.parse(rawString)
      parsed = value && typeof value === 'object' ? value : {}
    } catch (error) {
      parsed = {}
    }
  }
  return {
    gearBySlot: metadata.selectedGearSnapshot || metadata.gearBySlot || parsed.gearBySlot || {},
    enhancementBySlot: metadata.enhancementBySlot || parsed.enhancementBySlot || {}
  }
}

function savedGearTemplatesForImport() {
  let templates = []
  try {
    templates = listBuildTemplates('gear')
  } catch (error) {
    templates = []
  }
  return (Array.isArray(templates) ? templates : []).map((template) => {
    const snapshot = parseSavedGearTemplateSnapshot(template)
    const gearBySlot = selectedGearByCanonicalSlot(snapshot.gearBySlot || {})
    const readySlotCount = requiredGearSlots.filter((slot) => !!gearBySlot[slot]).length
    const canApplyGear = readySlotCount > 0
    const savedAt = templateShortDate((template && (template.updatedAt || template.createdAt)) || '')
    return {
      ...(template || {}),
      displayName: (template && template.title) || '已保存装备模板',
      displaySourceName: (template && template.source) || '我的保存',
      statusLabel: (template && template.statusLabel) || '已保存',
      slotCoverageLabel: `已保存 ${readySlotCount}/${requiredGearSlots.length} 槽`,
      missingSlotLabel: readySlotCount >= requiredGearSlots.length ? '配置完整' : `缺 ${requiredGearSlots.length - readySlotCount} 槽`,
      updatedLabel: savedAt ? `保存 ${savedAt}` : '',
      canApplyGear,
      savedGearBySlot: gearBySlot,
      savedEnhancementBySlot: normalizedEnhancementBySlot(snapshot.enhancementBySlot || {}),
      actionLabel: canApplyGear ? '应用' : '不可导入',
      cardClass: ['saved-template-card', canApplyGear ? (readySlotCount >= requiredGearSlots.length ? 'complete' : 'partial') : 'blocked'].filter(Boolean).join(' ')
    }
  }).slice(0, 8)
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

function gearTemplateHasRecoverableWeaponRepair(template, missingSlots, blockers) {
  const skippedSlots = communityTemplateSkippedWeaponSlots(template)
  if (!skippedSlots.size) return false
  const missing = Array.isArray(missingSlots) ? missingSlots : []
  if (missing.some((slot) => !skippedSlots.has(slot))) return false
  const messages = stringList(blockers)
  if (!messages.length) return true
  return messages.every((message) => {
    const text = cleanGearString(message).toLowerCase()
    return text.includes('weapon rule') ||
      text.includes('selected two-hand main hand') ||
      text.includes('two-hand main hand') ||
      text.includes('main_hand gear incompatible') ||
      text.includes('off_hand gear incompatible')
  })
}

function gearCommunityTemplateIsObservedPartial(template, status, sourceStatus, missingSlots) {
  const sourceKey = normalizeGearTemplateKey(template && template.sourceKey)
  if (sourceKey !== 'raiderio_observed_profile') return false
  if (status === 'complete' || sourceStatus === 'complete' || sourceStatus === 'synced' || sourceStatus === 'verified') {
    return Array.isArray(missingSlots) && missingSlots.length > 0
  }
  return true
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
  const observedPartial = gearCommunityTemplateIsObservedPartial(template, normalizedStatus, normalizedSourceStatus, missingSlots)
  const canApplyGear = !!(template && template.canApplyGear !== false && readySlotCount > 0 && !sourceReference && !observedPartial && normalizedStatus !== 'blocked' && normalizedSourceStatus !== 'blocked')
  const displaySourceName = gearCommunitySourceDisplayName(template)
  const recoverableWeaponRepair = canApplyGear && gearTemplateHasRecoverableWeaponRepair(template, missingSlots, blockers)
  const blockerLabel = recoverableWeaponRepair ? '' : (gearIssueText(blockers) || (sourceReference ? '仅作为来源参考，不可直接导入' : ''))
  const slotCoverageLabel = recoverableWeaponRepair
    ? `已覆盖 ${readySlotCount}/${requiredGearSlots.length} 槽 · 武器自动补齐`
    : `已覆盖 ${readySlotCount}/${requiredGearSlots.length} 槽`
  const missingSlotLabel = recoverableWeaponRepair
    ? '武器自动补齐'
    : (missingSlots.length ? `缺 ${missingSlots.length} 槽` : '16 槽完整')
  const statusLabel = recoverableWeaponRepair ? '可导入' : gearCommunityStatusLabel(normalizedStatus)
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
    statusLabel,
    sourceStatusLabel: gearCommunityStatusLabel(normalizedSourceStatus),
    slotCoverageLabel,
    missingSlotLabel,
    blockerLabel,
    updatedLabel: (template && template.updatedAt) || '',
    actionLabel: canApplyGear ? '应用' : '不可导入',
    cardClass: gearCommunityTemplateCardClass({ status: normalizedStatus, sourceStatus: normalizedSourceStatus })
  }
}

function gearCommunityTemplatesForPayload(payload) {
  const communityTemplates = payload && Array.isArray(payload.communityTemplates) ? payload.communityTemplates : []
  const baselineTemplates = payload && Array.isArray(payload.baselineTemplates) ? payload.baselineTemplates : []
  const seenIds = new Set()
  const templates = []
  ;[...communityTemplates, ...baselineTemplates].forEach((template) => {
    if (!template) return
    const id = String(template.id || '').trim()
    if (id && seenIds.has(id)) return
    if (id) seenIds.add(id)
    templates.push(template)
  })
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
  if (fromFallback) {
    return '装备接口暂不可用，当前只是空槽位兜底。'
  }
  return ''
}

function gearPayloadForData(payload) {
  if (!payload || typeof payload !== 'object') return payload
  const slim = { ...payload }
  delete slim.replacementCandidates
  delete slim.slotGroups
  delete slim.equippedSet
  delete slim.baselineSet
  delete slim.presets
  delete slim.candidateItems
  delete slim.catalogItems
  delete slim.communityTemplates
  return slim
}

function gearDerivedStateForData(state) {
  if (!state || !state.gearPayload) return state
  return {
    ...state,
    gearPayload: gearPayloadForData(state.gearPayload),
    selectedGearBySlot: gearSelectionForData(state.selectedGearBySlot)
  }
}

function fullGearPayloadForPage(page) {
  return (page && page.gearPayloadCache) || (page && page.data && page.data.gearPayload) || null
}

function gearObjectForSnapshot(item) {
  if (!item || typeof item !== 'object') return item
  const allowedKeys = [
    'slot',
    'simcSlot',
    'itemId',
    'id',
    'name',
    'displayName',
    'localizedName',
    'englishName',
    'ilevel',
    'itemLevel',
    'bonus_id',
    'gem_id',
    'gem_bonus_id',
    'gem_ilevel',
    'enchant_id',
    'crafted_stats',
    'embellishment',
    'modCapabilities',
    'supportsSocket',
    'sourceType',
    'variantSource',
    'variantKey',
    'defaultVariantKey',
    'simcIlevelOnly',
    'armorType',
    'weaponType',
    'itemSetName',
    'hasBuiltInEmbellishment',
    'builtInEmbellishment',
    'intrinsicEmbellishment',
    'inherentEmbellishment',
    'builtInEmbellishmentLabel',
    'embellishmentSource',
    'compatibility',
    'missingFields',
    'simcReady'
  ]
  const slim = {}
  allowedKeys.forEach((key) => {
    const value = item[key]
    if (value !== undefined && value !== null && value !== '') slim[key] = value
  })
  return slim
}

function gearObjectForData(item) {
  if (!item || typeof item !== 'object') return item
  const slim = { ...item }
  delete slim.sources
  delete slim.socketOptions
  delete slim.enchantOptions
  delete slim.embellishmentOptions
  delete slim.variants
  delete slim.sourceRefs
  delete slim.observedProfileRefs
  delete slim.sourceReferences
  delete slim.rawItem
  delete slim.candidateItems
  delete slim.replacementCandidates
  delete slim.originalItem
  return slim
}

function gearSelectionForData(selection) {
  const slim = {}
  Object.keys(selection || {}).forEach((slot) => {
    slim[slot] = gearObjectForData(selection[slot])
  })
  return slim
}

function gearOptionForData(option) {
  if (!option || typeof option !== 'object') return option
  const slim = { ...option }
  delete slim.simcOptions
  delete slim.sortValue
  delete slim.originalIndex
  return slim
}

function gearSlotCandidatesForPage(page, slot, fallback) {
  const cache = page && page.gearSlotCandidateCache
  const cached = cache && cache[slot]
  return Array.isArray(cached) ? cached : (Array.isArray(fallback) ? fallback : [])
}

function gearCandidatePoolForSlot(page, gearPayload, slot) {
  const group = gearGroupsBySlot(gearPayload || {})[slot] || {}
  return gearSlotCandidatesForPage(page, slot, group.items || [])
}

function firstApplicableGearCandidate(page, gearPayload, slot, selectedGearBySlot) {
  const rule = normalizedWeaponRule(gearPayload || {})
  const selected = selectedGearBySlot || {}
  const mainType = gearItemTypeContext(selected.main_hand).weaponType
  const candidates = gearCandidatePoolForSlot(page, gearPayload, slot)
  for (const candidate of candidates) {
    const applied = appliedGearCandidate(
      candidate,
      candidate && (candidate.defaultVariantKey || candidate.variantKey || ''),
      candidate && (candidate.selectedCraftedStatKey || candidate.craftedStatOptionKey || '')
    )
    if (!(applied && applied.simcReady && gearTemplateLine(applied))) continue
    if (!weaponRuleAllowsItem(rule, applied)) continue
    if (
      slot === 'off_hand' &&
      twoHandWeaponTypes.has(mainType) &&
      rule.mode !== 'dual_wield_2h'
    ) {
      continue
    }
    return applied
  }
  return null
}

function communityTemplateSkippedWeaponSlots(template) {
  return new Set(
    stringList((template && template.legalitySkippedSlots) || ((template && template.payload) || {}).legalitySkippedSlots)
      .filter((slot) => slot === 'main_hand' || slot === 'off_hand')
  )
}

function repairedGearSelectionForSkippedWeapons(page, gearPayload, selectedGearBySlot, template) {
  const skippedSlots = communityTemplateSkippedWeaponSlots(template)
  if (!skippedSlots.size) return selectedGearBySlot || {}
  let selected = prunedGearSelectionByWeaponRule(gearPayload, selectedGearBySlot || {})
  if (skippedSlots.has('main_hand') && !selected.main_hand) {
    const mainHand = firstApplicableGearCandidate(page, gearPayload, 'main_hand', selected)
    if (mainHand) {
      selected = prunedGearSelectionByWeaponRule(gearPayload, {
        ...selected,
        main_hand: mainHand
      })
    }
  }
  if (skippedSlots.has('off_hand') && !selected.off_hand) {
    const mainType = gearItemTypeContext(selected.main_hand).weaponType
    const rule = normalizedWeaponRule(gearPayload || {})
    if (!(twoHandWeaponTypes.has(mainType) && rule.mode !== 'dual_wield_2h')) {
      const offHand = firstApplicableGearCandidate(page, gearPayload, 'off_hand', selected)
      if (offHand) {
        selected = prunedGearSelectionByWeaponRule(gearPayload, {
          ...selected,
          off_hand: offHand
        })
      }
    }
  }
  return selected
}

function communityTemplateBaseGearSelection(gearPayload, template) {
  const templateSelection = gearItemsToSelection((template && template.gearItems) || [], gearPayload)
  return prunedGearSelectionByWeaponRule(gearPayload, templateSelection)
}

function simcOptionTokens(value) {
  const values = Array.isArray(value) ? value : [value]
  const result = []
  values.forEach((entry) => {
    cleanGearString(entry).split(/[\s/,]+/).forEach((token) => {
      const normalized = cleanGearString(token)
      if (normalized) result.push(normalized)
    })
  })
  return result
}

function communityTemplateRawEnhancementBySlot(template) {
  const result = {}
  const recordForSlot = (slot) => {
    if (!result[slot]) {
      result[slot] = {
        gemIds: [],
        gemIdSequences: [],
        gemConflict: false,
        enchantIds: [],
        embellishments: [],
        gemOptionIds: [],
        enchantOptionIds: [],
        embellishmentOptionIds: []
      }
    }
    return result[slot]
  }
  const addUnique = (target, values) => {
    ;(Array.isArray(values) ? values : []).forEach((value) => {
      const normalized = cleanGearString(value)
      if (normalized && !target.includes(normalized)) target.push(normalized)
    })
  }
  const addGemSequence = (target, values) => {
    const sequence = (Array.isArray(values) ? values : []).map(cleanGearString).filter(Boolean)
    if (!sequence.length) return
    const duplicate = target.gemIdSequences.some((existing) => (
      existing.length === sequence.length && existing.every((value, index) => value === sequence[index])
    ))
    if (!duplicate) target.gemIdSequences.push(sequence)
    target.gemConflict = target.gemIdSequences.length > 1
    target.gemIds = target.gemConflict ? target.gemIdSequences.flat() : [...target.gemIdSequences[0]]
  }
  const mergeRecord = (slot, record, allowOptionIdentities) => {
    if (!slot || !record || typeof record !== 'object') return
    const target = recordForSlot(slot)
    const gemIds = simcOptionTokens(record.gem_id || record.gemId || record.gemIds)
    addGemSequence(target, gemIds)
    addUnique(target.enchantIds, simcOptionTokens(record.enchant_id || record.enchantId || record.enchantIds))
    addUnique(target.embellishments, [record.embellishment || record.embellishmentId || record.embellishment_id])
    if (allowOptionIdentities) {
      addUnique(target.gemOptionIds, [
        ...normalizedOptionIdentityList(record.gemOptionIds),
        cleanGearString(record.socketOptionId || record.socket_option_id)
      ])
      addUnique(target.enchantOptionIds, [record.enchantOptionId || record.enchant_option_id])
      addUnique(target.embellishmentOptionIds, [record.embellishmentOptionId || record.embellishment_option_id])
    }
  }
  const payload = template && template.payload && typeof template.payload === 'object' ? template.payload : {}
  ;[template && template.enhancementBySlot, payload.enhancementBySlot].forEach((enhancementBySlot) => {
    Object.keys(enhancementBySlot || {}).forEach((slot) => mergeRecord(slot, enhancementBySlot[slot], true))
  })
  const gearItems = [
    ...((template && Array.isArray(template.gearItems)) ? template.gearItems : []),
    ...((Array.isArray(payload.gearItems) ? payload.gearItems : []))
  ]
  gearItems.forEach((item) => {
    const slot = cleanGearString(item && (item.simcSlot || item.slot))
    const simcOptions = item && item.simcOptions && typeof item.simcOptions === 'object' ? item.simcOptions : {}
    mergeRecord(slot, { ...simcOptions, ...(item || {}) }, false)
  })
  Object.keys(result).forEach((slot) => {
    const record = result[slot]
    if (!Object.keys(record).some((key) => Array.isArray(record[key]) && record[key].length)) delete result[slot]
  })
  return result
}

function communityEnhancementAffectedSlots(template) {
  return Object.keys(communityTemplateRawEnhancementBySlot(template))
}

function loadCommunityTemplateEnhancementDetails(page, template, requestContext) {
  const affectedSlots = communityEnhancementAffectedSlots(template)
  const incompleteSlots = affectedSlots.filter((slot) => gearPayloadNeedsSlotDetail(page, slot))
  if (!incompleteSlots.length) return null
  return Promise.all(incompleteSlots.map((slot) => (
    loadGearSlotDetailForPage(page, slot, requestContext).catch(() => fullGearPayloadForPage(page))
  ))).then(() => fullGearPayloadForPage(page))
}

function communityEnhancementOptionVisible(option) {
  const payload = optionPayload(option || {})
  return !(
    option && (option.isVisible === false || option.is_visible === false) ||
    payload.isVisible === false ||
    payload.is_visible === false
  )
}

function communityEnhancementOptionAppliesToSlot(option, slot) {
  const payload = optionPayload(option || {})
  const applicableSlots = option && Array.isArray(option.applicableSlots)
    ? option.applicableSlots
    : (Array.isArray(payload.applicableSlots) ? payload.applicableSlots : [])
  if (!applicableSlots.length) return true
  const normalized = applicableSlots.map(cleanGearString).filter(Boolean)
  return normalized.includes('*') || normalized.includes(slot)
}

function communityEnhancementStableOptionIdentity(option) {
  return cleanGearString(option && (option.optionKey || option.option_key))
}

function communityEnhancementOptionHasAffirmativeTrust(option) {
  const record = option || {}
  const status = cleanGearString(optionFirstValue(record, 'status')).toLowerCase()
  if (status !== 'verified' || optionDisplayStatus(record) !== 'verified') return false
  const explicitRank = optionFirstValue(record, [
    'qualityRank', 'rank', 'craftingQuality', 'qualityTier'
  ])
  return explicitRank === '' || optionQualityRank({ qualityRank: String(explicitRank) }) === 2
}

function communityEnhancementAuthoritativeLabel(option, type) {
  const record = option || {}
  const payload = optionPayload(record)
  const label = cleanGearString(
    record.displayLabel ||
    record.display_label ||
    payload.displayLabel ||
    payload.display_label ||
    record.label ||
    payload.label ||
    record.name ||
    payload.name
  )
  if (!label || enhancementLabelLooksLikeFallback(label, type)) return ''
  const normalizedLabel = label.toLowerCase().replace(/[\s_-]+/g, '')
  const simcOptions = record.simcOptions && typeof record.simcOptions === 'object' ? record.simcOptions : {}
  const rawValues = type === 'gem'
    ? optionGemIds(record)
    : (type === 'enchant'
        ? [simcOptions.enchant_id || optionFirstValue(record, ['enchantId', 'enchant_id'])]
        : [simcOptions.embellishment || optionFirstValue(record, ['embellishment', 'embellishmentId', 'embellishment_id'])])
  if (rawValues.some((value) => cleanGearString(value).toLowerCase().replace(/[\s_-]+/g, '') === normalizedLabel)) return ''
  return label
}

function communityEnhancementOptionsForSlot(gearPayload, item, optionKey, type) {
  const slot = cleanGearString(item && (item.simcSlot || item.slot))
  const options = enhancementOptionsForSlot(gearPayload, item, optionKey).filter((option) => (
    !!communityEnhancementStableOptionIdentity(option) &&
    communityEnhancementOptionVisible(option) &&
    communityEnhancementOptionAppliesToSlot(option, slot) &&
    communityEnhancementOptionHasAffirmativeTrust(option) &&
    !!communityEnhancementAuthoritativeLabel(option, type)
  ))
  return itemSupportsEnhancement(item, type, options) ? options : []
}

function communityEnhancementOptionForSimcValue(options, simcKey, rawValue) {
  const expected = cleanGearString(rawValue)
  if (!expected) return null
  const matchesByIdentity = new Map()
  ;(options || []).forEach((option) => {
    const simcOptions = option && option.simcOptions && typeof option.simcOptions === 'object' ? option.simcOptions : {}
    if (cleanGearString(simcOptions[simcKey]) !== expected) return
    const identity = communityEnhancementStableOptionIdentity(option)
    if (identity && !matchesByIdentity.has(identity)) matchesByIdentity.set(identity, option)
  })
  return matchesByIdentity.size === 1 ? Array.from(matchesByIdentity.values())[0] : null
}

function communityEnhancementOptionForIdentity(options, identity) {
  const expected = cleanGearString(identity)
  if (!expected) return null
  return (options || []).find((option) => communityEnhancementStableOptionIdentity(option) === expected) || null
}

function reconcileCommunityTemplateEnhancements(gearPayload, selectedGearBySlot, rawBySlot) {
  const enhancementBySlot = {}
  const unresolvedBySlot = {}
  const indexed = enrichedSelectedGearByCanonicalSlot(gearPayload || {}, selectedGearBySlot || {})
  Object.keys(rawBySlot || {}).forEach((slot) => {
    const raw = rawBySlot[slot] || {}
    const item = indexed[slot]
    const unresolved = { gemIds: [], enchantIds: [], embellishments: [], readOnly: true }
    if (!item) {
      unresolved.gemIds = simcOptionTokens(raw.gemIds)
      unresolved.enchantIds = simcOptionTokens(raw.enchantIds)
      unresolved.embellishments = (raw.embellishments || []).map(cleanGearString).filter(Boolean)
      if (unresolved.gemIds.length || unresolved.enchantIds.length || unresolved.embellishments.length) {
        unresolvedBySlot[slot] = unresolved
      }
      return
    }
    const next = {}
    const gemOptions = communityEnhancementOptionsForSlot(gearPayload, item, 'socketOptions', 'gem')
    const enchantOptions = communityEnhancementOptionsForSlot(gearPayload, item, 'enchantOptions', 'enchant')
    const embellishmentOptions = communityEnhancementOptionsForSlot(gearPayload, item, 'embellishmentOptions', 'embellishment')
    const rawGemIds = simcOptionTokens(raw.gemIds)
    if (raw.gemConflict) {
      unresolved.gemIds = rawGemIds
    } else if (rawGemIds.length > gearItemSocketCapacity(item)) {
      unresolved.gemIds = rawGemIds
    } else if (rawGemIds.length) {
      const matchedGemOptionIds = []
      rawGemIds.forEach((gemId) => {
        const matched = communityEnhancementOptionForSimcValue(gemOptions, 'gem_id', gemId)
        const optionId = communityEnhancementStableOptionIdentity(matched)
        if (optionId) matchedGemOptionIds.push(optionId)
        else unresolved.gemIds.push(gemId)
      })
      if (matchedGemOptionIds.length) next.gemOptionIds = matchedGemOptionIds
    } else {
      const explicitGemOptionIds = normalizedOptionIdentityList(raw.gemOptionIds)
      if (explicitGemOptionIds.length <= gearItemSocketCapacity(item)) {
        const matchedGemOptionIds = explicitGemOptionIds.filter((identity) => (
          !!communityEnhancementOptionForIdentity(gemOptions, identity)
        ))
        if (matchedGemOptionIds.length) next.gemOptionIds = matchedGemOptionIds
      }
    }
    const rawEnchantIds = simcOptionTokens(raw.enchantIds)
    if (rawEnchantIds.length === 1) {
      const matched = communityEnhancementOptionForSimcValue(enchantOptions, 'enchant_id', rawEnchantIds[0])
      const optionId = communityEnhancementStableOptionIdentity(matched)
      if (optionId) next.enchantOptionId = optionId
      else unresolved.enchantIds = rawEnchantIds
    } else if (rawEnchantIds.length > 1) {
      unresolved.enchantIds = rawEnchantIds
    } else {
      const explicitEnchantOptionIds = normalizedOptionIdentityList(raw.enchantOptionIds)
      if (explicitEnchantOptionIds.length === 1 && communityEnhancementOptionForIdentity(enchantOptions, explicitEnchantOptionIds[0])) {
        next.enchantOptionId = explicitEnchantOptionIds[0]
      }
    }
    const rawEmbellishments = (raw.embellishments || []).map(cleanGearString).filter(Boolean)
    if (rawEmbellishments.length === 1) {
      const matched = communityEnhancementOptionForSimcValue(embellishmentOptions, 'embellishment', rawEmbellishments[0])
      const optionId = communityEnhancementStableOptionIdentity(matched)
      if (optionId) next.embellishmentOptionId = optionId
      else unresolved.embellishments = rawEmbellishments
    } else if (rawEmbellishments.length > 1) {
      unresolved.embellishments = rawEmbellishments
    } else {
      const explicitEmbellishmentOptionIds = normalizedOptionIdentityList(raw.embellishmentOptionIds)
      if (
        explicitEmbellishmentOptionIds.length === 1 &&
        communityEnhancementOptionForIdentity(embellishmentOptions, explicitEmbellishmentOptionIds[0])
      ) {
        next.embellishmentOptionId = explicitEmbellishmentOptionIds[0]
      }
    }
    if (Object.keys(next).length) enhancementBySlot[slot] = next
    if (unresolved.gemIds.length || unresolved.enchantIds.length || unresolved.embellishments.length) {
      unresolvedBySlot[slot] = unresolved
    }
  })
  const unresolvedSlotCount = Object.keys(unresolvedBySlot).length
  return {
    enhancementBySlot,
    unresolvedBySlot,
    warnings: unresolvedSlotCount
      ? [`${unresolvedSlotCount} 个槽位的社区强化缺少当前可编辑证据，已按只读事实保留。`]
      : []
  }
}

function communityTemplateNeedsWeaponSlotDetail(page, gearPayload, slot, selectedGearBySlot) {
  if (!gearPayloadNeedsSlotDetail(page, slot)) return false
  return !firstApplicableGearCandidate(page, gearPayload, slot, selectedGearBySlot || {})
}

function loadCommunityTemplateWeaponRepairDetails(page, template, requestContext) {
  const skippedSlots = communityTemplateSkippedWeaponSlots(template)
  if (!skippedSlots.size) return null
  let gearPayload = fullGearPayloadForPage(page) || (page && page.data && page.data.gearPayload) || {}
  let selected = communityTemplateBaseGearSelection(gearPayload, template)
  const loadOffHandIfNeeded = () => {
    if (requestContext && typeof requestContext.shouldApply === 'function' && !requestContext.shouldApply()) return null
    gearPayload = fullGearPayloadForPage(page) || gearPayload
    selected = repairedGearSelectionForSkippedWeapons(page, gearPayload, selected, template)
    const mainType = gearItemTypeContext(selected.main_hand).weaponType
    const rule = normalizedWeaponRule(gearPayload || {})
    const offHandOccupied = twoHandWeaponTypes.has(mainType) && rule.mode !== 'dual_wield_2h'
    const loadOffHand = skippedSlots.has('off_hand') &&
      !selected.off_hand &&
      !offHandOccupied &&
      communityTemplateNeedsWeaponSlotDetail(page, gearPayload, 'off_hand', selected)
    if (!loadOffHand) return null
    return loadGearSlotDetailForPage(page, 'off_hand', requestContext).catch(() => fullGearPayloadForPage(page) || gearPayload)
  }
  const loadMain = skippedSlots.has('main_hand') &&
    !selected.main_hand &&
    communityTemplateNeedsWeaponSlotDetail(page, gearPayload, 'main_hand', selected)
  if (loadMain) {
    return loadGearSlotDetailForPage(page, 'main_hand', requestContext)
      .catch(() => fullGearPayloadForPage(page) || gearPayload)
      .then(() => loadOffHandIfNeeded() || (fullGearPayloadForPage(page) || gearPayload))
  }
  return loadOffHandIfNeeded()
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

function replaceGearSlotGroup(groups, detailGroups, slot) {
  const source = Array.isArray(groups) ? groups : []
  const detail = (Array.isArray(detailGroups) ? detailGroups : []).find((group) => (
    group && (group.slot || group.simcSlot) === slot
  ))
  if (!detail) return source
  let replaced = false
  const next = source.map((group) => {
    if (group && (group.slot || group.simcSlot) === slot) {
      replaced = true
      return detail
    }
    return group
  })
  if (!replaced) next.push(detail)
  return next
}

function mergeGearSlotDetailPayload(basePayload, detailPayload, slot) {
  if (!detailPayload || typeof detailPayload !== 'object') return basePayload || {}
  const merged = { ...(basePayload || {}) }
  if (Array.isArray(detailPayload.replacementCandidates)) {
    merged.replacementCandidates = replaceGearSlotGroup(
      merged.replacementCandidates,
      detailPayload.replacementCandidates,
      slot
    )
  }
  if (Array.isArray(detailPayload.slotGroups)) {
    merged.slotGroups = replaceGearSlotGroup(merged.slotGroups, detailPayload.slotGroups, slot)
  }
  if (detailPayload.equippedSet && typeof detailPayload.equippedSet === 'object') {
    merged.equippedSet = {
      ...((merged.equippedSet && typeof merged.equippedSet === 'object') ? merged.equippedSet : {}),
      [slot]: detailPayload.equippedSet[slot]
    }
    if (!merged.equippedSet[slot]) delete merged.equippedSet[slot]
  }
  if (detailPayload.slotReadiness && typeof detailPayload.slotReadiness === 'object') {
    merged.slotReadiness = {
      ...((merged.slotReadiness && typeof merged.slotReadiness === 'object') ? merged.slotReadiness : {}),
      [slot]: detailPayload.slotReadiness[slot]
    }
    if (!merged.slotReadiness[slot]) delete merged.slotReadiness[slot]
  }
  if (Array.isArray(detailPayload.gearLegalityBlockers)) {
    merged.gearLegalityBlockers = Array.from(new Set([
      ...((Array.isArray(merged.gearLegalityBlockers) ? merged.gearLegalityBlockers : [])),
      ...detailPayload.gearLegalityBlockers
    ].filter(Boolean)))
  }
  return merged
}

function gearPayloadNeedsSlotDetail(page, slot) {
  const payload = fullGearPayloadForPage(page) || {}
  const cached = page && page.gearSlotCandidateCache && page.gearSlotCandidateCache[slot]
  if (Array.isArray(cached) && cached.length && cached.every((item) => item && item.detailMode !== 'summary')) {
    return false
  }
  const group = gearGroupsBySlot(payload)[slot] || {}
  const items = Array.isArray(group.items) ? group.items : []
  if (group.detailMode === 'complete' && !items.some((item) => item && item.detailMode === 'summary')) {
    return false
  }
  return payload.gearPayloadMode === 'initial' || group.detailMode === 'partial' || items.some((item) => item && item.detailMode === 'summary')
}

function gearEnhancementSlotNeedsDetail(gearPayload, item, selectedEnhancement) {
  if (!item || typeof item !== 'object') return false
  const socketOptions = enhancementOptionsForSlot(gearPayload, item, 'socketOptions')
  const enchantOptions = enhancementOptionsForSlot(gearPayload, item, 'enchantOptions')
  const embellishmentOptions = enhancementOptionsForSlot(gearPayload, item, 'embellishmentOptions')
  if (!socketOptions.length && (
    itemSupportsConfiguredEnhancementFallback(item, 'gem') ||
    enhancementRecordHasSelectedType(selectedEnhancement, 'gem')
  )) {
    return true
  }
  if (!enchantOptions.length && (
    itemSupportsConfiguredEnhancementFallback(item, 'enchant') ||
    enhancementRecordHasSelectedType(selectedEnhancement, 'enchant')
  )) {
    return true
  }
  if (!embellishmentOptions.length && !builtInEmbellishmentValue(item) && (
    itemSupportsConfiguredEnhancementFallback(item, 'embellishment') ||
    enhancementRecordHasSelectedType(selectedEnhancement, 'embellishment')
  )) {
    return true
  }
  return false
}

function gearEnhancementDetailSlotsForPage(page) {
  const gearPayload = fullGearPayloadForPage(page) || (page && page.data && page.data.gearPayload) || {}
  const currentSelectedGearBySlot = (page && page.data && page.data.selectedGearBySlot) || {}
  const canonicalSnapshot = canonicalWorkbenchSnapshot(page)
  const selectedGearBySlot = page && page.gearWorkbenchState
    ? gearSelectionWithCanonicalEnhancementConstraints(currentSelectedGearBySlot, canonicalSnapshot)
    : currentSelectedGearBySlot
  const indexed = enrichedSelectedGearByCanonicalSlot(gearPayload, selectedGearBySlot)
  const currentEnhancement = (
    (page && page.data && page.data.gearEnhancementSheet && page.data.gearEnhancementSheet.draftEnhancementBySlot) ||
    (page && page.data && page.data.enhancementBySlot) ||
    {}
  )
  const enhancement = page && page.gearWorkbenchState
    ? optionIdentityEnhancementBySlot(currentEnhancement)
    : normalizedEnhancementBySlot(currentEnhancement)
  return requiredGearTemplateSlots(gearPayload || {}).filter((slot) => {
    const item = indexed[slot]
    return !!(item && gearPayloadNeedsSlotDetail(page, slot) && gearEnhancementSlotNeedsDetail(gearPayload, item, enhancement[slot]))
  })
}

function canonicalEnhancementTypesBySlot(snapshot) {
  const result = {}
  const constraints = snapshot && snapshot.constraints && snapshot.constraints.slots && typeof snapshot.constraints.slots === 'object'
    ? snapshot.constraints.slots
    : {}
  Object.keys(constraints).forEach((slot) => {
    const record = constraints[slot] || {}
    const types = []
    if ((Number(record.socketCount) || 0) > 0) types.push('gem')
    if (record.canEnchant === true) types.push('enchant')
    if (record.canEmbellish === true) types.push('embellishment')
    if (types.length) result[slot] = types
  })
  return result
}

const inheritedEnhancementTypeRows = [
  ['gem', 'gemIds', '宝石'],
  ['enchant', 'enchantIds', '附魔'],
  ['embellishment', 'embellishments', '美化']
]

function inheritedEnhancementRowsBySlot(state) {
  const result = {}
  Object.keys((state && state.unresolvedBySlot) || {}).forEach((slot) => {
    const record = state.unresolvedBySlot[slot] || {}
    const rows = inheritedEnhancementTypeRows.reduce((items, [type, key, label]) => {
      if (!Array.isArray(record[key]) || !record[key].length) return items
      items.push({
        slot,
        type,
        label,
        statusLabel: '已继承，当前目录不可编辑',
        readOnly: true
      })
      return items
    }, [])
    if (rows.length) result[slot] = rows
  })
  return result
}

function enhancementTypeLabel(type) {
  return { gem: '宝石', enchant: '附魔', embellishment: '美化' }[type] || ''
}

function buildGearEnhancementSheetForPage(page, visible, requestedActiveSlot, overrides) {
  const state = overrides || {}
  const currentSheet = page && page.data && page.data.gearEnhancementSheet
  const gearPayload = fullGearPayloadForPage(page) || (page && page.data && page.data.gearPayload) || {}
  const currentSelectedGearBySlot = state.selectedGearBySlot || (page && page.data && page.data.selectedGearBySlot) || {}
  const currentEnhancementBySlot = state.enhancementBySlot || (
    page && page.data && page.data.gearEnhancementSheet && page.data.gearEnhancementSheet.draftEnhancementBySlot
  ) || (page && page.data && page.data.enhancementBySlot) || {}
  const canonicalWorkbench = !!(page && page.gearWorkbenchState)
  const canonicalSnapshot = canonicalWorkbenchSnapshot(page)
  const selectedGearBySlot = canonicalWorkbench
    ? gearSelectionWithCanonicalEnhancementConstraints(currentSelectedGearBySlot, canonicalSnapshot)
    : currentSelectedGearBySlot
  const enhancementBySlot = canonicalWorkbench
    ? optionIdentityEnhancementBySlot(currentEnhancementBySlot)
    : currentEnhancementBySlot
  const confirmedEnhancementBySlot = optionIdentityEnhancementBySlot(
    state.confirmedEnhancementBySlot ||
    (currentSheet && currentSheet.visible && currentSheet.confirmedEnhancementBySlot) ||
    (page && page.data && page.data.enhancementBySlot) ||
    {}
  )
  const sheet = buildGearEnhancementSheet(
    gearPayload,
    selectedGearBySlot,
    enhancementBySlot,
    visible,
    requestedActiveSlot
  )
  if (canonicalSnapshot) {
    const embellishmentMax = Number(canonicalSnapshot.constraints && canonicalSnapshot.constraints.embellishmentMax)
    sheet.embellishmentMax = Number.isFinite(embellishmentMax) && embellishmentMax >= 0
      ? embellishmentMax
      : 0
  }
  sheet.confirmedEnhancementBySlot = confirmedEnhancementBySlot
  const detailSlots = gearEnhancementDetailSlotsForPage(page)
  const communityImportState = eligibleCommunityEnhancementImportStateForPage(page, canonicalSnapshot)
  const inheritedRowsBySlot = inheritedEnhancementRowsBySlot(communityImportState)
  const canonicalTypesBySlot = canonicalEnhancementTypesBySlot(canonicalSnapshot)
  const configurableSlots = (sheet.equipmentRows || []).map((row) => row.slot)
  const allSlots = requiredGearTemplateSlots(gearPayload || {})
  const equipmentSlots = Array.from(new Set([
    ...configurableSlots,
    ...detailSlots,
    ...Object.keys(canonicalTypesBySlot),
    ...Object.keys(inheritedRowsBySlot)
  ])).filter((slot) => !!selectedGearBySlot[slot]).sort((left, right) => {
    const leftKey = gearEnhancementSlotSortKey(left, allSlots.indexOf(left))
    const rightKey = gearEnhancementSlotSortKey(right, allSlots.indexOf(right))
    return leftKey[0] - rightKey[0] || leftKey[1] - rightKey[1]
  })
  if (!equipmentSlots.length) return { ...sheet, activeInheritedRows: [], inheritedCount: 0 }
  if (sheet.emptyText && detailSlots.length) sheet.emptyText = '请选择装备槽位加载可配置选项。'
  else if (sheet.emptyText) sheet.emptyText = ''
  const activeSlot = equipmentSlots.includes(requestedActiveSlot)
    ? requestedActiveSlot
    : (sheet.activeSlot || equipmentSlots[0] || '')
  const indexed = enrichedSelectedGearByCanonicalSlot(gearPayload, selectedGearBySlot)
  const pendingSlots = new Set([
    ...detailSlots,
    ...Object.keys(canonicalTypesBySlot),
    ...Object.keys(inheritedRowsBySlot)
  ])
  const equipmentRows = buildGearEnhancementEquipmentRows(
    equipmentSlots,
    indexed,
    sheet.gemRows || [],
    sheet.enchantRows || [],
    sheet.embellishmentRows || [],
    activeSlot,
    pendingSlots
  ).map((row) => {
    const canonicalTypes = canonicalTypesBySlot[row.slot] || []
    const inheritedTypes = (inheritedRowsBySlot[row.slot] || []).map((item) => item.type)
    const hydratedTypes = []
    if ((sheet.gemRows || []).some((item) => item.slot === row.slot)) hydratedTypes.push('gem')
    if ((sheet.enchantRows || []).some((item) => item.slot === row.slot)) hydratedTypes.push('enchant')
    if ((sheet.embellishmentRows || []).some((item) => item.slot === row.slot)) hydratedTypes.push('embellishment')
    const typeLabels = Array.from(new Set([
      ...canonicalTypes,
      ...hydratedTypes,
      ...inheritedTypes
    ])).map(enhancementTypeLabel).filter(Boolean)
    return {
      ...row,
      typeSummary: typeLabels.length ? typeLabels.join(' / ') : row.typeSummary,
      inherited: inheritedTypes.length > 0
    }
  })
  const activeInheritedRows = activeSlot ? (inheritedRowsBySlot[activeSlot] || []) : []
  const inheritedCount = Object.keys(inheritedRowsBySlot).reduce(
    (count, slot) => count + inheritedRowsBySlot[slot].length,
    0
  )
  return {
    ...sheet,
    equipmentRows,
    activeSlot,
    activeTitle: activeSlot ? (gearSlotDisplayLabels[activeSlot] || activeSlot) : '',
    activeItemName: activeSlot ? itemDisplayName(indexed[activeSlot]) : '',
    activeGemRows: activeSlot ? (sheet.gemRows || []).filter((row) => row.slot === activeSlot) : [],
    activeEnchantRows: activeSlot ? (sheet.enchantRows || []).filter((row) => row.slot === activeSlot) : [],
    activeEmbellishmentRows: activeSlot ? (sheet.embellishmentRows || []).filter((row) => row.slot === activeSlot) : [],
    activeInheritedRows,
    inheritedCount,
    warnings: Array.from(new Set([
      ...(sheet.warnings || []),
      ...((Array.isArray(communityImportState.warnings) ? communityImportState.warnings : []))
    ]))
  }
}

function loadGearSlotDetailForPage(page, slot, requestContext) {
  if (!page || !slot) return Promise.resolve(fullGearPayloadForPage(page))
  if (!gearPayloadNeedsSlotDetail(page, slot)) return Promise.resolve(fullGearPayloadForPage(page))
  const selectedSpec = (page && page.data && page.data.selectedSpec) || {}
  const keys = specWebsimKeys(selectedSpec)
  const selectionKey = `${keys.classKey}:${keys.specKey}`
  const contextKey = cleanGearString(requestContext && requestContext.requestKey)
  const requestKey = [selectionKey, slot, contextKey].filter(Boolean).join(':')
  page.gearSlotDetailRequestCache = page.gearSlotDetailRequestCache || {}
  if (page.gearSlotDetailRequestCache[requestKey]) return page.gearSlotDetailRequestCache[requestKey]
  const requestPromise = requestWebsimGear({ ...keys, mode: 'slot', slot }).then(({ payload, error, fromFallback }) => {
    if (!page || !page.data || page.data.gearSelectionKey !== selectionKey) return fullGearPayloadForPage(page)
    if (requestContext && typeof requestContext.shouldApply === 'function' && !requestContext.shouldApply()) {
      return fullGearPayloadForPage(page)
    }
    if (fromFallback || error) return fullGearPayloadForPage(page)
    const merged = mergeGearSlotDetailPayload(fullGearPayloadForPage(page) || {}, payload, slot)
    page.gearPayloadCache = merged
    return merged
  }).finally(() => {
    if (page.gearSlotDetailRequestCache && page.gearSlotDetailRequestCache[requestKey] === requestPromise) {
      delete page.gearSlotDetailRequestCache[requestKey]
    }
  })
  page.gearSlotDetailRequestCache[requestKey] = requestPromise
  return requestPromise
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
    item.crafted_stats || '',
    item.embellishment || ''
  ].join('-')
}

function gearCandidateSources(item) {
  return item && Array.isArray(item.sources) ? item.sources : []
}

function gearObservedSourceLabel(value) {
  return /raider\.io.*observed|raider\.io.*观测|实装观测/i.test(String(value || ''))
}

function gearSimcPresetSourceLabel(value) {
  return /^simulationcraft preset\b/i.test(String(value || '').trim())
}

function gearSourceIsSimcPreset(source) {
  if (!source) return false
  const sourceType = String(source.sourceType || source.type || '').toLowerCase()
  const label = source.label || source.sourceLabel || source.source || ''
  return sourceType === 'simc_preset' || sourceType === 'simcpreset' || gearSimcPresetSourceLabel(label)
}

function gearSourceIsObservedEvidence(source) {
  if (!source) return false
  const sourceType = String(source.sourceType || source.type || '').toLowerCase()
  const label = source.label || source.sourceLabel || source.source || ''
  return sourceType === 'observed_profile' || gearObservedSourceLabel(label)
}

function gearDropSources(item) {
  return gearCandidateSources(item).filter((source) => !gearSourceIsObservedEvidence(source) && !gearSourceIsSimcPreset(source))
}

function gearCandidateSourceLabel(item) {
  const sources = gearDropSources(item)
  if (sources.length) return sources[0].label || sources[0].sourceLabel || ''
  const fallback = item && (item.source || item.sourceName || item.encounterName || item.instanceName)
  if (gearObservedSourceLabel(fallback)) return '来源待补充'
  if (gearSimcPresetSourceLabel(fallback)) return '来源待补充'
  if (fallback) return fallback
  return '来源待补充'
}

function gearCandidateSourceType(item) {
  const sources = gearDropSources(item)
  const sourceType = (sources[0] && sources[0].sourceType) || (item && item.sourceType) || ''
  const normalized = String(sourceType || '').toLowerCase()
  if (normalized.includes('tier') || normalized.includes('item_set')) return 'tier_set'
  if (normalized.includes('raid')) return 'raid'
  if (normalized.includes('craft')) return 'crafted'
  if (normalized.includes('dungeon') || normalized.includes('loot')) return 'dungeon'
  return normalized || 'other'
}

function gearCandidateMatchesFilter(item, filterKey) {
  if (!filterKey || filterKey === 'all') return true
  return gearCandidateSourceType(item) === filterKey
}

function gearCandidateFilterOptions(allCandidates, activeKey) {
  const baseFilters = gearCandidateFilters.slice(0)
  return baseFilters.map((filter) => ({
    ...filter,
    active: filter.key === activeKey,
    count: filter.key === 'all'
      ? allCandidates.length
      : allCandidates.filter((item) => gearCandidateMatchesFilter(item, filter.key)).length
  }))
}

function gearOptionKey(option, index) {
  return (option && (option.id || option.key || option.name)) || `option-${index}`
}

function gearVariantDifficultyLabel(variant) {
  const trackLabel = gearVariantUpgradeTrackLabel(variant)
  if (trackLabel) return trackLabel
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
    tier_set: '套装',
    crafted: '制造装备',
    source_pending: '来源待补',
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

function gearVariantUpgradeTrackLabel(variant) {
  const rawLevel = variant && (variant.itemLevel || variant.ilevel)
  const level = Number(rawLevel || 0)
  const labels = {
    263: '勇士',
    276: '英雄',
    289: '神话',
    298: '虚空晋升'
  }
  return labels[level] || ''
}

function gearVariantLevelLabel(variant) {
  const rawLevel = variant && (variant.itemLevel || variant.ilevel)
  const level = Number(rawLevel || 0)
  return level > 0 ? `装等 ${level}` : ''
}

function gearVariantSortValue(variant, index) {
  const rawLevel = variant && (variant.itemLevel || variant.ilevel)
  const level = Number(rawLevel || 0)
  if (level > 0) return level
  const key = String((variant && (variant.difficultyKey || variant.sourceType || variant.key || variant.variantKey)) || '').toLowerCase()
  const label = String((variant && (variant.difficultyLabel || variant.difficultyName || variant.label)) || '')
  if (/champion/.test(key) || /勇士/.test(label)) return 263
  if (/hero/.test(key) || /英雄/.test(label)) return 276
  if (/void/.test(key) || /虚空/.test(label)) return 298
  if (/myth/.test(key) || /神话|史诗/.test(label)) return 289
  return 10000 + index
}

function gearCandidateVariants(candidate) {
  const variants = Array.isArray(candidate && candidate.variants) ? candidate.variants.slice(0) : []
  const hasItemLevelTrack = variants.some((variant) => Number((variant && (variant.itemLevel || variant.ilevel)) || 0) > 0)
  if (!hasItemLevelTrack) return variants
  return variants.filter((variant) => !gearVariantIsPendingPlaceholder(variant))
}

function gearVariantIsPendingPlaceholder(variant) {
  if (!variant) return false
  const level = Number((variant.itemLevel || variant.ilevel) || 0)
  if (level > 0) return false
  const key = String(variant.key || variant.variantKey || '').toLowerCase().replace(/_/g, '-')
  const difficultyKey = String(variant.difficultyKey || '').toLowerCase().replace(/_/g, '-')
  return key === 'needs-variant' || difficultyKey === 'needs-variant'
}

function gearVariantOptionVisibleKey(option) {
  if (!option || !option.levelLabel) return `${option && option.key || 'variant'}-${option && option.originalIndex || 0}`
  return `${option.displayLabel || ''}|${option.levelLabel || ''}`
}

function gearVariantOptionScore(option, selectedKey) {
  const statusRank = {
    verified: 4,
    complete: 4,
    synced: 3,
    partial: 2,
    blocked: 0
  }
  const simcOptions = option && typeof option.simcOptions === 'object' ? option.simcOptions : {}
  const simcOptionCount = Object.keys(simcOptions).filter((key) => simcOptions[key] !== undefined && simcOptions[key] !== null && simcOptions[key] !== '').length
  const hasExplicitSimcMod = !!(simcOptions.bonus_id || simcOptions.gem_id || simcOptions.enchant_id || simcOptions.crafted_stats)
  return [
    option && option.key === selectedKey ? 1 : 0,
    statusRank[String(option && option.status || '').toLowerCase()] || 0,
    hasExplicitSimcMod ? 1 : 0,
    option && option.simcIlevelOnly ? 0 : 1,
    simcOptionCount,
    -Number(option && option.originalIndex || 0)
  ]
}

function gearVariantOptionIsBetter(candidate, current, selectedKey) {
  const left = gearVariantOptionScore(candidate, selectedKey)
  const right = gearVariantOptionScore(current, selectedKey)
  for (let index = 0; index < left.length; index += 1) {
    if (left[index] !== right[index]) return left[index] > right[index]
  }
  return false
}

function collapseDuplicateVariantOptions(options, selectedKey) {
  const collapsed = []
  const byVisibleKey = {}
  ;(options || []).forEach((option) => {
    const visibleKey = gearVariantOptionVisibleKey(option)
    const existingIndex = byVisibleKey[visibleKey]
    if (existingIndex === undefined) {
      byVisibleKey[visibleKey] = collapsed.length
      collapsed.push(option)
      return
    }
    if (gearVariantOptionIsBetter(option, collapsed[existingIndex], selectedKey)) {
      collapsed[existingIndex] = option
    }
  })
  return collapsed
}

function decorateVariantOptions(candidate, selectedKey) {
  const variants = gearCandidateVariants(candidate)
  const options = variants.map((variant, index) => {
    const key = variant.key || variant.variantKey || `variant-${index}`
    return {
      ...variant,
      key,
      displayLabel: gearVariantDifficultyLabel(variant),
      levelLabel: gearVariantLevelLabel(variant),
      selected: key === selectedKey,
      statusClass: gearStatusClass(variant.status || 'partial'),
      sortValue: gearVariantSortValue(variant, index),
      originalIndex: index
    }
  }).sort((left, right) => {
    if (left.sortValue !== right.sortValue) return left.sortValue - right.sortValue
    return left.originalIndex - right.originalIndex
  })
  return collapseDuplicateVariantOptions(options, selectedKey)
}

function candidateVariant(candidate, variantKey) {
  const variants = gearCandidateVariants(candidate)
  if (!variants.length) return null
  const fallbackVariant = variants.find((variant) => {
    const variantLevel = Number((variant && (variant.itemLevel || variant.ilevel)) || 0)
    const candidateLevel = Number((candidate && (candidate.ilevel || candidate.itemLevel)) || 0)
    return candidateLevel > 0 && variantLevel === candidateLevel
  }) || variants[0]
  const defaultKey = variantKey || candidate.defaultVariantKey || candidate.variantKey || fallbackVariant.key || fallbackVariant.variantKey
  return variants.find((variant) => (variant.key || variant.variantKey) === defaultKey) || fallbackVariant
}

function craftedStatOptionsForVariant(variant) {
  return Array.isArray(variant && variant.craftedStatOptions) ? variant.craftedStatOptions : []
}

function selectedCraftedStatOption(variant, selectedKey) {
  const options = craftedStatOptionsForVariant(variant)
  if (!options.length || !selectedKey) return null
  return options.find((option, index) => gearOptionKey(option, index) === selectedKey) || null
}

function decorateCraftedStatOptions(variant, selectedKey) {
  return craftedStatOptionsForVariant(variant).map((option, index) => {
    const key = gearOptionKey(option, index)
    return {
      ...option,
      key,
      selected: key === selectedKey,
      statusClass: gearStatusClass(option.status || 'partial')
    }
  })
}

function applySimcOptions(target, options) {
  Object.keys(options || {}).forEach((key) => {
    const value = options[key]
    if (value !== undefined && value !== null && value !== '') {
      target[key] = value
    }
  })
}

function applyVariantDisplayFields(target, variant) {
  if (!target || !variant) return
  const statKeys = ['statSummary', 'statDisplayStatus', 'statSource', 'simcStatStatus', 'simcStatFailureKind', 'simcStatCheckedAt']
  const statArrayKeys = ['itemStats', 'stats', 'attributes', 'secondaryStats']
  let hasVariantStats = false
  statArrayKeys.forEach((key) => {
    if (Array.isArray(variant[key]) && variant[key].length) {
      target[key] = variant[key]
      hasVariantStats = true
    } else {
      delete target[key]
    }
  })
  statKeys.forEach((key) => {
    if (variant[key] !== undefined && variant[key] !== null && variant[key] !== '') {
      target[key] = variant[key]
      if (key === 'statSummary') hasVariantStats = true
    } else if (!hasVariantStats || key === 'statSummary') {
      delete target[key]
    }
  })
  if (!hasVariantStats && (variant.itemLevel || variant.ilevel)) {
    target.statDisplayStatus = variant.statDisplayStatus || 'pending_current_variant'
  }
  if (Array.isArray(variant.blockers)) {
    target.variantBlockers = variant.blockers
  }
}

function appliedGearCandidate(candidate, variantKey, craftedStatOptionKey) {
  if (!candidate) return null
  const variant = candidateVariant(candidate, variantKey)
  const craftedOptions = craftedStatOptionsForVariant(variant)
  const craftedOption = selectedCraftedStatOption(variant, craftedStatOptionKey)
  const selected = {
    ...candidate
  }
  delete selected.selected
  delete selected.statusClass
  delete selected.statusLabel
  delete selected.reason
  if (variant) {
    selected.variantKey = variant.key || variant.variantKey || ''
    selected.variantLabel = gearVariantDifficultyLabel(variant) || variant.label || ''
    selected.variantDifficultyLabel = gearVariantDifficultyLabel(variant)
    selected.difficultyKey = variant.difficultyKey || selected.difficultyKey || ''
    selected.sourceType = variant.sourceType || selected.sourceType || ''
    if (variant.itemLevel || variant.ilevel) selected.ilevel = variant.itemLevel || variant.ilevel
    applySimcOptions(selected, variant.simcOptions)
    if (variant.itemLevel || variant.ilevel) selected.ilevel = Number(variant.itemLevel || variant.ilevel) || (variant.itemLevel || variant.ilevel)
    applyVariantDisplayFields(selected, variant)
  }
  if (craftedOptions.length) {
    delete selected.crafted_stats
    selected.selectedCraftedStatKey = craftedOption ? (craftedStatOptionKey || gearOptionKey(craftedOption, 0)) : ''
    selected.selectedCraftedStatLabel = craftedOption ? (craftedOption.label || craftedOption.name || '') : ''
    if (craftedOption) {
      applySimcOptions(selected, craftedOption.simcOptions)
      applyVariantDisplayFields(selected, craftedOption)
      if (Array.isArray(craftedOption.blockers)) {
        selected.variantBlockers = craftedOption.blockers
      }
      if (String(craftedOption.status || '').toLowerCase() !== 'verified') {
        selected.blockers = stringList([
          ...((selected.blockers) || []),
          ...((craftedOption.blockers) || []),
          craftedOption.reason || craftedOption.blocker || craftedOption.statusReason || 'SimC crafted item stats pending'
        ])
      }
    }
  }
  const hasSimcMod = !!(selected.bonus_id || selected.gem_id || selected.enchant_id || selected.crafted_stats)
  const hasExecutableVariant = !!(selected.ilevel || hasSimcMod)
  selected.simcReady = !!(selected.slot && (selected.itemId || selected.id) && hasExecutableVariant)
  selected.missingFields = selected.simcReady ? [] : [
    !selected.ilevel ? 'ilevel' : '',
    !hasSimcMod ? 'bonus_id/gem_id/enchant_id' : ''
  ].filter(Boolean)
  if (craftedOptions.length && !craftedOption) {
    selected.simcReady = false
    selected.missingFields = stringList([...(selected.missingFields || []), 'crafted_stats'])
  }
  if (craftedOption && String(craftedOption.status || '').toLowerCase() !== 'verified') {
    selected.simcReady = false
  }
  return selected
}

function gearModSummary(item) {
  const parts = []
  if (item && item.socketOptionLabel) parts.push(item.socketOptionLabel)
  if (item && item.enchantOptionLabel) parts.push(item.enchantOptionLabel)
  return parts.join(' / ')
}

function gearDropSourceText(item) {
  const sourceType = String(gearCandidateSourceType(item) || item && item.sourceType || '').toLowerCase()
  const setName = String((item && (item.itemSetName || item.setName || item.tierSetName)) || '').trim()
  if (sourceType === 'tier_set' && setName) return `${setName}-套装`
  const labels = gearDropSources(item)
    .map((source) => source && (source.label || source.sourceLabel || source.encounterName || source.instanceName))
    .filter(Boolean)
  const fallback = item && (item.source || item.sourceName || [item.instanceName, item.encounterName].filter(Boolean).join(' · '))
  const values = stringList(labels.length ? labels : [
    (gearObservedSourceLabel(fallback) || gearSimcPresetSourceLabel(fallback)) ? '' : fallback
  ])
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

function displayLabelForGearStatKey(key) {
  const labels = {
    strength: '力量',
    agility: '敏捷',
    intellect: '智力',
    stamina: '耐力',
    haste: '急速',
    crit: '暴击',
    mastery: '精通',
    versatility: '全能',
    armor: '护甲'
  }
  return labels[key] || key
}

function gearStatEntriesForDisplay(item, primaryKey) {
  const resolvedPrimary = cleanGearString(primaryKey || (item && item.primaryStatKey))
  const entries = gearStatEntriesForItem(item, resolvedPrimary)
  if (!entries.length) return []
  const primaryKeys = ['strength', 'agility', 'intellect']
  const seen = new Set()
  return entries.filter((entry) => {
    if (!entry || !entry.key) return false
    if (primaryKeys.includes(entry.key) && resolvedPrimary && entry.key !== resolvedPrimary) return false
    const key = `${entry.key}:${entry.value}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function gearStatDisplaySummary(item, primaryKey) {
  const entries = gearStatEntriesForDisplay(item, primaryKey)
  if (!entries.length) return ''
  return entries.map((entry) => `${displayLabelForGearStatKey(entry.key)} ${entry.value}`).join('；')
}

function gearPendingStatReason(item) {
  const simcStatus = String((item && item.simcStatStatus) || '').toLowerCase()
  const failureKind = String((item && item.simcStatFailureKind) || '').toLowerCase()
  if (simcStatus === 'failed') {
    if (failureKind === 'item_resolution') return 'SimC 物品解析失败'
    if (failureKind === 'unsupported_profile') return 'SimC 暂不支持该配置'
    return 'SimC 属性解析失败'
  }
  const blockers = stringList([
    ...((item && item.blockers) || []),
    ...((item && item.variantBlockers) || []),
    ...((item && item.missingFields) || [])
  ]).join(' ').toLowerCase()
  if (blockers.includes('simulationcraft item stats')) return 'SimC 属性待回填'
  return ''
}

function gearAttributeText(item, primaryKey) {
  const resolvedPrimary = cleanGearString(primaryKey || (item && item.primaryStatKey))
  if (item && item.statSummary && !resolvedPrimary) return String(item.statSummary).trim()
  const statSummary = gearStatDisplaySummary(item, resolvedPrimary)
  if (statSummary) return statSummary
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
  const statDisplayStatus = String((item && item.statDisplayStatus) || '').toLowerCase()
  if (!parts.length && statDisplayStatus.includes('pending')) {
    const details = [
      item && item.ilevel ? `装等 ${item.ilevel}` : '',
      gearPendingStatReason(item)
    ].filter(Boolean)
    return `属性待补充${details.length ? `（${details.join('，')}）` : ''}`
  }
  if (!parts.length && item && item.ilevel) parts.push(`装等 ${item.ilevel}`)
  const seen = new Set()
  return parts.filter((value) => {
    if (!value || seen.has(value)) return false
    seen.add(value)
    return true
  }).join('；') || '属性待补充'
}

function gearCandidateDetailRows(item, primaryKey) {
  const rows = []
  rows.push({ label: '掉落来源', value: gearDropSourceText(item) })
  const badgeLabels = gearEquipmentBadgeLabels(item)
  if (badgeLabels.length) rows.push({ label: '装备标签', value: badgeLabels.join(' / ') })
  rows.push({ label: '装备属性', value: gearAttributeText(item, primaryKey) })
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
    selectedCandidateIndex: 0,
    detailKey: '',
    emptyText: '',
    activeCandidate: null,
    appliedCandidate: null,
    variantKey: '',
    craftedStatOptionKey: '',
    socketOptionId: '',
    enchantOptionId: '',
    variantOptions: [],
    craftedStatOptions: [],
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
  const requestedVariantKey = config.variantKey || ''
  const defaultVariant = candidateVariant(activeCandidate, requestedVariantKey)
  const variantKey = (defaultVariant && (defaultVariant.key || defaultVariant.variantKey)) || requestedVariantKey
  const craftedStatOptionKey = config.craftedStatOptionKey || config.selectedCraftedStatKey || ''
  const appliedCandidate = appliedGearCandidate(activeCandidate, variantKey, craftedStatOptionKey)
  const activeTrust = gearTrustState(appliedCandidate || activeCandidate, activeCandidate && activeCandidate.statusClass, activeCandidate && activeCandidate.reason)
  const canApplyCandidate = !!(appliedCandidate && appliedCandidate.simcReady && gearTemplateLine(appliedCandidate))
  const detailKey = candidates.some((item) => item.key === config.detailKey) ? config.detailKey : ''
  return {
    visible: true,
    slot,
    label: (row && row.label) || slot,
    item: row,
    filterKey,
    filters: gearCandidateFilterOptions(allCandidates, filterKey),
    candidates: candidates.map((candidate, index) => {
      const isSelected = index === selectedCandidateIndex
      let displayCandidate = candidate
      if (isSelected && appliedCandidate) {
        const trust = gearTrustState(
          appliedCandidate,
          appliedCandidate.status || appliedCandidate.variantStatus || appliedCandidate.statusClass,
          appliedCandidate.reason
        )
        displayCandidate = {
          ...appliedCandidate,
          key: candidate.key,
          statusLabel: gearStatusLabel(trust.status),
          statusClass: gearStatusClass(trust.status),
          trustLabel: trust.label,
          trustReason: trust.reason,
          blockerLabel: trust.blockerLabel,
          reason: trust.reason
        }
      }
      return {
        ...gearObjectForData(displayCandidate),
        equipmentBadgeLabels: gearEquipmentBadgeLabels(displayCandidate),
        detailRows: gearCandidateDetailRows(displayCandidate, displayCandidate.primaryStatKey),
        embellishmentBadgeLabel: gearBuiltInEmbellishmentBadgeLabel(displayCandidate),
        selected: isSelected,
        detailOpen: candidate.key === detailKey
      }
    }),
    selectedCandidateIndex,
    detailKey,
    emptyText: candidates.length ? '' : '该来源暂无候选装备',
    activeCandidate: gearObjectForData(activeCandidate),
    appliedCandidate: gearObjectForData(appliedCandidate),
    variantKey,
    craftedStatOptionKey,
    socketOptionId: '',
    enchantOptionId: '',
    variantOptions: decorateVariantOptions(activeCandidate, variantKey).map(gearOptionForData),
    craftedStatOptions: decorateCraftedStatOptions(defaultVariant, craftedStatOptionKey).map(gearOptionForData),
    socketOptions: [],
    enchantOptions: [],
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
    const candidate = item
    const key = gearCandidateKey(candidate, slot, index)
    if (seen.has(key)) return null
    seen.add(key)
    const isSelected = selected && String(selected.itemId || selected.id || '') === String(candidate.itemId || candidate.id || '')
    const missingFields = Array.isArray(candidate.missingFields) ? candidate.missingFields : []
    const trust = gearTrustState(candidate, candidate.simcReady ? 'verified' : (missingFields.length ? 'partial' : 'blocked'), candidate.reason)
    return attachGearGameAsset({
      ...candidate,
      key,
      slot: candidate.slot || slot,
      displayName: itemDisplayName(candidate),
      iconUrl: candidate.iconUrl || '',
      source: gearCandidateSourceLabel(candidate),
      sourceType: gearCandidateSourceType(candidate),
      equipmentBadgeLabels: gearEquipmentBadgeLabels(candidate),
      embellishmentBadgeLabel: gearBuiltInEmbellishmentBadgeLabel(candidate),
      variantLabel: candidate.variantLabel || '',
      modSummary: gearModSummary(candidate),
      statusLabel: gearStatusLabel(trust.status),
      statusClass: gearStatusClass(trust.status),
      detailRows: gearCandidateDetailRows(candidate, candidate.primaryStatKey),
      trustLabel: trust.label,
      trustReason: trust.reason,
      blockerLabel: trust.blockerLabel,
      reason: trust.reason,
      selected: !!isSelected
    }, 'gear-candidate')
  }).filter(Boolean)
}

function buildGearSlotRows(payload, selectedGearBySlot, enhancementBySlot) {
  const slots = payload && Array.isArray(payload.slots) && payload.slots.length
    ? payload.slots
    : requiredGearSlots.map((slot) => ({
      slot,
      simcSlot: slot,
      key: slot,
      label: gearSlotDisplayLabels[slot] || slot
    }))
  const readiness = (payload && payload.slotReadiness) || {}
  const groups = gearGroupsBySlot(payload)
  const selection = selectedGearBySlot || {}
  const enhancement = normalizedEnhancementBySlot(enhancementBySlot || {})
  const equippedSet = (payload && payload.equippedSet) || {}
  return slots.map((slotMeta) => {
    const slot = slotMeta.slot || slotMeta.simcSlot || slotMeta.key
    const occupiedOffHand = slot === 'off_hand' && !selection[slot]
      ? occupiedOffHandGearItem(payload, selection)
      : null
    const item = occupiedOffHand || enrichedGearItemFromCandidates(payload, slot, selection[slot] || equippedSet[slot] || {})
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
      equipmentBadgeLabels: gearEquipmentBadgeLabels(item),
      embellishmentBadgeLabel: gearBuiltInEmbellishmentBadgeLabel(item),
      enhancementBadgeLabels: gearSlotEnhancementBadgeLabels(payload, item, enhancement[slot]),
      variantLabel: item.variantLabel || '',
      variantKey: item.variantKey || '',
      selectedCraftedStatKey: item.selectedCraftedStatKey || '',
      craftedStatOptionKey: item.craftedStatOptionKey || item.selectedCraftedStatKey || '',
      modSummary: gearModSummary(item),
      status: trust.status,
      statusLabel: gearStatusLabel(trust.status),
      statusClass: gearStatusClass(trust.status),
      trustLabel: trust.label,
      trustReason: trust.reason,
      blockerLabel: trust.blockerLabel,
      reason: trust.reason
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
  const gearDataFallback = !!currentState.gearDataFallback
  const selectedGearBySlot = prunedGearSelectionByWeaponRule(gearPayload, currentState.selectedGearBySlot || {})
  const gearReadiness = currentState.gearReadiness || (gearPayload && gearPayload.readiness) || {}
  const gearSlotRows = buildGearSlotRows(gearPayload, selectedGearBySlot, currentState.enhancementBySlot)
  const gearStatSnapshot = currentState.gearStatSnapshot || (gearPayload && gearPayload.statSnapshot) || defaultGearStatSnapshot()
  const gearAttributePanel = buildGearAttributePanel(
    gearPayload,
    selectedGearBySlot,
    currentState.selectedSpec,
    currentState.enhancementBySlot,
    gearStatSnapshot
  )
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
    selectedGearBySlot,
    gearSlotRows,
    gearAttributePanel,
    gearStatSnapshot,
    gearStatBlockers: Array.isArray(gearStatSnapshot.blockers) ? gearStatSnapshot.blockers : [],
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

function acceptedVerifiedGearResolve(state, request, snapshot) {
  return !!(
    state &&
    request &&
    snapshot &&
    state.resolveStatus === 'verified' &&
    Number(state.latestResolveSerial) === Number(request.serial) &&
    Number(state.intentVersion) === Number(request.intentVersion) &&
    state.currentSnapshot === snapshot &&
    cleanGearString(snapshot.resolvedGearSignature)
  )
}

function communityReplacementBindingForPage(page) {
  const snapshot = canonicalWorkbenchSnapshot(page)
  const current = page && page.communityEnhancementImportState
  const eligible = eligibleCommunityEnhancementImportState(current, snapshot)
  if (!cleanGearString(eligible.resolvedGearSignature)) return null
  return {
    templateId: cleanGearString(eligible.templateId),
    serial: Number(eligible.serial) || 0,
    resolvedGearSignature: cleanGearString(eligible.resolvedGearSignature)
  }
}

function unresolvedEvidenceAfterVerifiedReplacement(unresolvedBySlot, snapshot, targets) {
  const resolvedSlots = snapshot && snapshot.resolvedSlots && typeof snapshot.resolvedSlots === 'object'
    ? snapshot.resolvedSlots
    : {}
  const replacementTargets = new Set(normalizedEnhancementReplacementTargets(targets).map((target) => `${target.slot}:${target.type}`))
  const result = {}
  Object.keys(unresolvedBySlot || {}).forEach((slot) => {
    const record = unresolvedBySlot[slot] || {}
    const selected = resolvedSlots[slot] && resolvedSlots[slot].selectedOptions || {}
    const next = {
      gemIds: Array.isArray(record.gemIds) ? [...record.gemIds] : [],
      enchantIds: Array.isArray(record.enchantIds) ? [...record.enchantIds] : [],
      embellishments: Array.isArray(record.embellishments) ? [...record.embellishments] : [],
      readOnly: true
    }
    if (replacementTargets.has(`${slot}:gem`) && Array.isArray(selected.gemOptionIds) && selected.gemOptionIds.length) next.gemIds = []
    if (replacementTargets.has(`${slot}:enchant`) && cleanGearString(selected.enchantOptionId)) next.enchantIds = []
    if (replacementTargets.has(`${slot}:embellishment`) && cleanGearString(selected.embellishmentOptionId)) next.embellishments = []
    if (next.gemIds.length || next.enchantIds.length || next.embellishments.length) result[slot] = next
  })
  return result
}

function communityEvidenceWarnings(unresolvedBySlot) {
  const unresolvedSlotCount = Object.keys(unresolvedBySlot || {}).length
  return unresolvedSlotCount
    ? [`${unresolvedSlotCount} 个槽位的社区强化缺少当前可编辑证据，已按只读事实保留。`]
    : []
}

function bindCommunityImportToResolvedSnapshot(page, request, snapshot, resolveContext) {
  if (!acceptedVerifiedGearResolve(page && page.gearWorkbenchState, request, snapshot)) return false
  const binding = resolveContext && resolveContext.communityImport
  const current = page.communityEnhancementImportState || emptyCommunityEnhancementImportState()
  if (binding && typeof binding === 'object') {
    if (
      cleanGearString(current.templateId) !== cleanGearString(binding.templateId) ||
      Number(current.serial) !== Number(binding.serial)
    ) return false
    page.communityEnhancementImportState = {
      ...current,
      resolvedGearSignature: cleanGearString(snapshot.resolvedGearSignature)
    }
    return true
  }
  const replacement = resolveContext && resolveContext.communityReplacement
  if (!replacement || typeof replacement !== 'object') return false
  if (
    cleanGearString(current.templateId) !== cleanGearString(replacement.templateId) ||
    Number(current.serial) !== Number(replacement.serial) ||
    cleanGearString(current.resolvedGearSignature) !== cleanGearString(replacement.resolvedGearSignature)
  ) return false
  const unresolvedBySlot = unresolvedEvidenceAfterVerifiedReplacement(current.unresolvedBySlot, snapshot, replacement.targets)
  page.communityEnhancementImportState = {
    ...current,
    resolvedGearSignature: cleanGearString(snapshot.resolvedGearSignature),
    unresolvedBySlot,
    warnings: communityEvidenceWarnings(unresolvedBySlot)
  }
  return true
}

const defaultSelection = findSpecSelection(defaultSpecId)

Page({
  communityEnhancementImportSerial: 0,
  communityEnhancementImportState: emptyCommunityEnhancementImportState(),

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
    gearStatSnapshot: defaultGearStatSnapshot(),
    gearStatBlockers: [],
    gearStatsRequestError: '',
    enhancementBySlot: {},
    gearSlotSheet: emptyGearSlotSheet(),
    gearEnhancementSheet: emptyGearEnhancementSheet(),
    gearSaveTemplateSheet: emptyGearSaveTemplateSheet(),
    gearCommunityTemplateSheet: emptyGearCommunityTemplateSheet(),
    gearWorkbenchView: {
      resolveStatus: 'idle',
      resolving: false,
      readOnly: true,
      canUseVerifiedSnapshot: false,
      canRunProfile: false,
      resolvedGearSignature: ''
    },
    gearWorkbenchStatusText: '等待校验当前装备配置',
    gearWorkbenchSignatureLabel: '',
    gearWorkbenchProblemRows: [],
    savedGearTemplates: [],
    fromFallback: true,
    requestError: ''
  },

  onLoad(options) {
    clearCommunityEnhancementImportState(this)
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
    clearCommunityEnhancementImportState(this)
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
    clearCommunityEnhancementImportState(this)
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
      const gearPayload = fullGearPayloadForPage(this)
      this.setData({
        selectedDetail: payload,
        ...createDetailDerivedState(payload, this.data.activeQueryKey, {
          ...this.data,
          gearPayload
        }),
        fromFallback,
        requestError: error || ''
      })
      maybeRefreshGearStatsForPage(this)
    }).finally(() => {
      this.setData({ loading: false })
    })
  },

  loadWebsimGearForSelection(selectionState) {
    const selectedSpec = (selectionState && selectionState.selectedSpec) || this.data.selectedSpec || {}
    const keys = specWebsimKeys(selectedSpec)
    const selectionKey = `${keys.classKey}:${keys.specKey}`
    const existingSelection = this.data.gearSelectionKey === selectionKey ? (this.data.selectedGearBySlot || {}) : {}
    const existingEnhancement = this.data.gearSelectionKey === selectionKey ? (this.data.enhancementBySlot || {}) : {}
    const existingStatsTalentImport = this.data.gearSelectionKey === selectionKey ? (this.data.gearStatsTalentImport || '') : ''
    const hasExistingRows = Array.isArray(this.data.gearSlotRows) && this.data.gearSlotRows.length > 0
    if (this.data.gearSelectionKey !== selectionKey) {
      this.gearPayloadCache = null
      this.gearSlotCandidateCache = {}
      this.gearSlotDetailRequestCache = {}
      this.gearStatsTalentImportKey = ''
    }
    this.setData({
      gearLoading: true,
      gearInitialLoading: !hasExistingRows,
      gearRequestError: '',
      gearDataFallback: false,
      gearDataWarningText: '',
      gearSelectionKey: selectionKey,
      gearStatsTalentImport: existingStatsTalentImport,
      gearStatsTalentImportError: '',
      gearSlotSheet: emptyGearSlotSheet(),
      gearEnhancementSheet: emptyGearEnhancementSheet(),
      gearCommunityTemplateSheet: emptyGearCommunityTemplateSheet()
    })
    this.gearInitialRequestCache = this.gearInitialRequestCache || {}
    const requestKey = `${selectionKey}:initial`
    if (this.gearInitialRequestCache[requestKey]) return this.gearInitialRequestCache[requestKey]
    const requestPromise = requestWebsimGear({ ...keys, mode: 'initial' }).then(({ payload, error, fromFallback }) => {
      if (this.data.gearSelectionKey !== selectionKey) return
      this.gearPayloadCache = payload
      this.gearSlotCandidateCache = {}
      const baselineSelection = equippedSetToSelection(payload.equippedSet || {}, payload)
      const selectedGearBySlot = prunedGearSelectionByWeaponRule(payload, {
        ...baselineSelection,
        ...existingSelection
      })
      const enhancementBySlot = prunedEnhancementBySlot(payload, selectedGearBySlot, existingEnhancement)
      const gearDataFallback = !!fromFallback
      const gearReadiness = payload.readiness || {}
      const derivedState = createDetailDerivedState(this.data.selectedDetail, this.data.activeQueryKey, {
        ...this.data,
        gearPayload: payload,
        selectedGearBySlot,
        enhancementBySlot,
        gearReadiness,
        gearDataFallback,
        gearRequestError: error || ''
      })
      this.setData({
        ...gearDerivedStateForData(derivedState),
        gearLoading: false,
        gearInitialLoading: false,
        gearRequestError: error || '',
        gearDataFallback,
        gearDataWarningText: gearDataWarningText(error || '', payload, gearDataFallback),
        enhancementBySlot
      })
      const resolution = resolveOrRefreshGearForPage(this, selectedGearBySlot, enhancementBySlot)
      if (typeof this.loadGearStatsTalentImport === 'function') {
        this.loadGearStatsTalentImport(keys, selectionKey)
      }
      return Promise.resolve(resolution).then(() => payload)
    }).catch((error) => {
      this.gearPayloadCache = null
      this.gearSlotCandidateCache = {}
      this.setData({
        gearLoading: false,
        gearInitialLoading: false,
        gearRequestError: error.message || String(error),
        gearDataFallback: true,
        gearDataWarningText: gearDataWarningText(error.message || String(error), null, true)
      })
      maybeRefreshGearStatsForPage(this)
      return null
    }).finally(() => {
      if (this.gearInitialRequestCache && this.gearInitialRequestCache[requestKey] === requestPromise) {
        delete this.gearInitialRequestCache[requestKey]
      }
    })
    this.gearInitialRequestCache[requestKey] = requestPromise
    return requestPromise
  },

  loadGearStatsTalentImport(keys, selectionKey) {
    if (gearTalentImportForStats(this.data)) return Promise.resolve('')
    if (this.gearStatsTalentImportKey === selectionKey) return Promise.resolve(this.data.gearStatsTalentImport || '')
    this.gearStatsTalentImportKey = selectionKey
    return requestWebsimTalentImport(keys).then(({ payload, error }) => {
      if (this.data.gearSelectionKey !== selectionKey) return ''
      const importCode = cleanGearString(payload && payload.importCode)
      if (!importCode) {
        const blockers = payload && Array.isArray(payload.blockers) ? payload.blockers.join(' / ') : ''
        this.setData({ gearStatsTalentImportError: error || blockers || 'no SimC-ready community talent import' })
        return ''
      }
      this.setData({
        gearStatsTalentImport: importCode,
        gearStatsTalentImportError: ''
      })
      return maybeRefreshGearStatsForPage(this)
    }).catch((error) => {
      if (this.data.gearSelectionKey !== selectionKey) return ''
      this.gearStatsTalentImportKey = ''
      this.setData({ gearStatsTalentImportError: error && error.message ? error.message : String(error || 'talent import request failed') })
      return ''
    })
  },

  buildSimcContext() {
    const selectedDetail = this.data.selectedDetail || {}
    const selectedSpec = this.data.selectedSpec || {}
    const activeDetail = this.data.activeDetail || {}
    const activeQuery = this.data.activeQuery || {}
    const context = {
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
    if (this.data.activeQueryKey === 'gear' && this.gearWorkbenchState && gearWorkbenchCanRunProfile(this.gearWorkbenchState)) {
      const snapshot = this.gearWorkbenchState.currentSnapshot || {}
      context.simulatorState.gear = {
        selectionIntent: this.gearWorkbenchState.confirmedIntent,
        resolvedGearSignature: snapshot.resolvedGearSignature || '',
        dependencyVector: snapshot.dependencyVector || {}
      }
    }
    return context
  },

  confirmAndResolveGearIntent(selectedGearBySlot, enhancementBySlot, resolveContext) {
    const replacementBinding = resolveContext && resolveContext.replaceInheritedEvidence
      ? communityReplacementBindingForPage(this)
      : null
    const completionContext = {
      ...((resolveContext && typeof resolveContext === 'object') ? resolveContext : {}),
      ...(replacementBinding
        ? {
            communityReplacement: {
              ...replacementBinding,
              targets: normalizedEnhancementReplacementTargets(resolveContext.inheritedReplacementTargets)
            }
          }
        : {})
    }
    const gearPayload = fullGearPayloadForPage(this) || this.data.gearPayload || {}
    const selectedSpec = this.data.selectedSpec || {}
    const keys = specWebsimKeys({
      websimClassKey: selectedSpec.websimClassKey || selectedSpec.classKey || gearPayload.classKey,
      websimSpecKey: selectedSpec.websimSpecKey || selectedSpec.specKey || gearPayload.specKey
    })
    const selection = selectedGearBySlot || {}
    const enhancements = enhancementBySlot || {}
    const selectionIntent = serializeGearSelectionIntent({
      resolverContext: gearPayload.resolverContext,
      eligibilityContext: {
        classKey: keys.classKey,
        specKey: keys.specKey,
        level: Number(gearPayload.maxLevel) || 90
      },
      selectedGearBySlot: selection,
      enhancementBySlot: enhancements
    })
    if (!selectionIntent) {
      this.gearWorkbenchState = {
        ...createGearWorkbenchState({}, {}),
        resolveStatus: 'unavailable',
        readOnly: true,
        problems: [{ code: 'RESOLVER_CONTEXT_UNAVAILABLE', title: '缺少服务端装备校验上下文' }]
      }
      this.setData({
        selectedGearBySlot: selection,
        enhancementBySlot: enhancements,
        ...gearWorkbenchDataState(this.gearWorkbenchState, this.data, this.communityEnhancementImportState)
      })
      return Promise.resolve(null)
    }

    if (!this.gearWorkbenchState || !completeResolverContext(gearPayload.resolverContext)) {
      this.gearWorkbenchState = createGearWorkbenchState(gearPayload.resolverContext, selectionIntent)
    } else {
      this.gearWorkbenchState = editGearIntent(this.gearWorkbenchState, selectionIntent)
      this.gearWorkbenchState = confirmGearIntent(this.gearWorkbenchState)
    }
    const pending = beginGearResolve(this.gearWorkbenchState)
    this.gearWorkbenchState = pending.state
    this.setData({
      selectedGearBySlot: selection,
      enhancementBySlot: enhancements,
      ...gearWorkbenchDataState(this.gearWorkbenchState, this.data, this.communityEnhancementImportState)
    })

    const applyResult = (request, transportResult) => {
      this.gearWorkbenchState = applyGearResolveResult(this.gearWorkbenchState, request, transportResult)
      const envelope = transportResult && transportResult.payload
      if (this.gearWorkbenchState.resolveStatus === 'revision_conflict') {
        const rebased = rebaseGearIntentRevisions(this.gearWorkbenchState, envelope && envelope.releaseContext)
        if (rebased !== this.gearWorkbenchState) {
          this.gearWorkbenchState = rebased
          const retry = beginGearResolve(this.gearWorkbenchState)
          this.gearWorkbenchState = retry.state
          this.setData(gearWorkbenchDataState(this.gearWorkbenchState, this.data, this.communityEnhancementImportState))
          return requestWebsimGearResolve(retry.request.selectionIntent).then((retryResult) => applyResult(retry.request, retryResult))
        }
      }
      const currentSnapshot = this.gearWorkbenchState.currentSnapshot
      bindCommunityImportToResolvedSnapshot(this, request, currentSnapshot, completionContext)
      this.setData(gearWorkbenchDataState(
        this.gearWorkbenchState,
        this.data,
        this.communityEnhancementImportState
      ))
      return currentSnapshot
    }

    return requestWebsimGearResolve(pending.request.selectionIntent)
      .then((result) => applyResult(pending.request, result))
      .catch((error) => applyResult(pending.request, {
        fromFallback: true,
        transportError: error && error.message ? error.message : String(error || 'gear resolve failed'),
        offline: true
      }))
  },

  refreshDerivedState(overrides) {
    const gearPayload = fullGearPayloadForPage(this)
    const nextState = createDetailDerivedState(
      this.data.selectedDetail,
      this.data.activeQueryKey,
      {
        ...this.data,
        gearPayload,
        ...(overrides || {})
      }
    )
    this.setData({
      ...(this.gearPayloadCache ? gearDerivedStateForData(nextState) : nextState),
      ...(this.gearWorkbenchState ? gearWorkbenchDataState(this.gearWorkbenchState, this.data, this.communityEnhancementImportState) : {})
    })
  },

  clearGearStatsSnapshot(blockers) {
    if (this.gearStatSnapshotState) {
      this.gearStatSnapshotState = invalidateGearStatSnapshot(this.gearStatSnapshotState)
      if (this.gearWorkbenchState) {
        this.gearWorkbenchState.statSnapshotStatus = this.gearStatSnapshotState.statSnapshotStatus
        this.gearWorkbenchState.statSnapshotSignature = this.gearStatSnapshotState.statSnapshotSignature
      }
    }
    const messages = Array.isArray(blockers) && blockers.length ? blockers : ['等待完整装备和天赋后计算属性百分比']
    const lastVerified = this.gearStatSnapshotState && this.gearStatSnapshotState.lastVerifiedStatSnapshot
    const snapshot = lastVerified
      ? { ...lastVerified, stale: true, readOnly: true }
      : defaultGearStatSnapshot(messages[0])
    snapshot.blockers = messages
    this.gearStatsRequestKey = ''
    const nextState = createDetailDerivedState(this.data.selectedDetail, this.data.activeQueryKey, {
      ...this.data,
      gearPayload: fullGearPayloadForPage(this),
      gearStatSnapshot: snapshot
    })
    this.setData({
      ...(this.gearPayloadCache ? gearDerivedStateForData(nextState) : nextState),
      gearStatSnapshot: snapshot,
      gearStatBlockers: messages,
      gearStatsLoading: false,
      gearStatsRequestError: '',
      ...(this.gearWorkbenchState ? gearWorkbenchDataState(this.gearWorkbenchState, this.data, this.communityEnhancementImportState) : {})
    })
    return Promise.resolve(null)
  },

  refreshGearStats(requestPayload, requestSignature) {
    const request = requestPayload
      ? { ready: true, payload: requestPayload, signature: requestSignature || JSON.stringify(requestPayload) }
      : gearStatsRequestForPage(this)
    if (!request.ready) return this.clearGearStatsSnapshot(request.blockers)
    const currentSnapshot = this.data.gearStatSnapshot
    const existingState = this.gearStatSnapshotState || createGearStatSnapshotState(
      currentSnapshot && currentSnapshot.statStatus === 'verified' ? currentSnapshot : null,
      this.gearWorkbenchState && this.gearWorkbenchState.statSnapshotSignature
    )
    if (existingState.activeStatRequest && existingState.activeStatRequest.contextKey === request.signature) {
      return Promise.resolve(existingState.lastVerifiedStatSnapshot || null)
    }
    if (existingState.statSnapshotStatus === 'verified' && existingState.verifiedStatContextKey === request.signature) {
      return Promise.resolve(existingState.currentStatSnapshot)
    }
    this.gearStatsRequestKey = request.signature
    const begun = beginGearStatSnapshot(existingState, {
      contextKey: request.signature,
      selectionIntent: request.payload.selectionIntent,
      profileContext: request.payload.profileContext
    }, Date.now())
    this.gearStatSnapshotState = begun.state

    const renderStatState = () => {
      const statState = this.gearStatSnapshotState
      const staleSnapshot = statState.lastVerifiedStatSnapshot
        ? { ...statState.lastVerifiedStatSnapshot, stale: statState.statSnapshotStatus !== 'verified', readOnly: statState.statSnapshotStatus !== 'verified' }
        : null
      const snapshot = statState.currentStatSnapshot || staleSnapshot || defaultGearStatSnapshot(
        statState.statSnapshotStatus === 'timed_out' ? '属性快照等待超时' : 'SimC 属性快照计算中'
      )
      const problemMessages = (statState.statProblems || []).map((problem) => cleanGearString(problem && (problem.title || problem.code))).filter(Boolean)
      const nextState = createDetailDerivedState(this.data.selectedDetail, this.data.activeQueryKey, {
        ...this.data,
        gearPayload: fullGearPayloadForPage(this),
        gearStatSnapshot: snapshot
      })
      if (this.gearWorkbenchState) {
        this.gearWorkbenchState.statSnapshotStatus = statState.statSnapshotStatus
        this.gearWorkbenchState.statSnapshotSignature = statState.statSnapshotSignature
      }
      this.setData({
        ...(this.gearPayloadCache ? gearDerivedStateForData(nextState) : nextState),
        gearStatSnapshot: snapshot,
        gearStatBlockers: problemMessages.length ? problemMessages : (snapshot.blockers || []),
        gearStatsLoading: !!statState.activeStatRequest,
        gearStatsRequestError: ['offline', 'unavailable', 'revision_conflict', 'timed_out', 'blocked'].includes(statState.statSnapshotStatus)
          ? (problemMessages.join('；') || '装备属性暂不可用')
          : '',
        ...(this.gearWorkbenchState ? gearWorkbenchDataState(
          this.gearWorkbenchState,
          { ...this.data, gearStatSnapshot: snapshot },
          this.communityEnhancementImportState
        ) : {})
      })
      return snapshot
    }

    renderStatState()
    const poll = (statRequest) => requestWebsimGearStatSnapshot(
      statRequest.selectionIntent,
      statRequest.profileContext,
      { timeoutMs: gearStatRequestTimeoutMs(statRequest, Date.now()) }
    ).then((result) => {
      const next = applyGearStatSnapshotResult(this.gearStatSnapshotState, statRequest, result, Date.now())
      if (next === this.gearStatSnapshotState) return null
      this.gearStatSnapshotState = next
      const displayed = renderStatState()
      const following = next.activeStatRequest
      if (!following) {
        if (next.statSnapshotStatus !== 'verified') this.gearStatsRequestKey = ''
        return next.currentStatSnapshot || displayed
      }
      const wait = typeof this.waitForGearStatSnapshotRetry === 'function'
        ? this.waitForGearStatSnapshotRetry(following.retryAfterMs)
        : new Promise((resolve) => setTimeout(resolve, following.retryAfterMs))
      return Promise.resolve(wait).then(() => {
        const active = this.gearStatSnapshotState && this.gearStatSnapshotState.activeStatRequest
        if (!active || active.serial !== following.serial || active.contextKey !== following.contextKey) return null
        return poll(active)
      })
    }).catch((error) => {
      const offlineResult = {
        payload: null,
        fromFallback: true,
        error: error && error.message ? error.message : String(error || '属性快照请求失败'),
        offline: true
      }
      this.gearStatSnapshotState = applyGearStatSnapshotResult(this.gearStatSnapshotState, statRequest, offlineResult, Date.now())
      this.gearStatsRequestKey = ''
      renderStatState()
      return null
    })
    return poll(begun.request)
  },

  loadGearSlotDetail(slot) {
    return loadGearSlotDetailForPage(this, slot)
  },

  openGearSlotSheet(event) {
    const slot = event.currentTarget.dataset.slot || ''
    if (!slot) return Promise.resolve()
    const openWithCurrentPayload = () => {
      const row = (this.data.gearSlotRows || []).find((item) => item.slot === slot) || {}
      const candidates = buildGearCandidateRows(slot, fullGearPayloadForPage(this) || {}, this.data.selectedGearBySlot || {})
      const selectedGear = ((this.data.selectedGearBySlot || {})[slot]) || {}
      const selectedItemId = String(selectedGear.itemId || selectedGear.id || row.itemId || '')
      const selectedCandidateIndex = Math.max(0, candidates.findIndex((item) => {
        if (item.selected) return true
        return selectedItemId && String(item.itemId || item.id || '') === selectedItemId
      }))
      this.gearSlotCandidateCache = {
        ...(this.gearSlotCandidateCache || {}),
        [slot]: candidates
      }
      this.setData({
        gearSlotSheet: buildGearSlotSheet(slot, row, candidates, {
          filterKey: 'all',
          candidateIndex: selectedCandidateIndex,
          variantKey: selectedGear.variantKey || row.variantKey || '',
          craftedStatOptionKey: selectedGear.selectedCraftedStatKey || selectedGear.craftedStatOptionKey || row.selectedCraftedStatKey || row.craftedStatOptionKey || ''
        })
      })
    }
    if (gearPayloadNeedsSlotDetail(this, slot)) {
      return loadGearSlotDetailForPage(this, slot)
        .catch(() => fullGearPayloadForPage(this))
        .then(openWithCurrentPayload)
    }
    openWithCurrentPayload()
    return Promise.resolve()
  },

  closeGearSlotSheet() {
    this.setData({
      gearSlotSheet: emptyGearSlotSheet()
    })
  },

  openGearEnhancementSheet() {
    if (this.data.gearDataFallback) {
      showToast(this.data.gearDataWarningText || '装备接口暂不可用，无法配置强化')
      return Promise.resolve()
    }
    const openWithCurrentPayload = () => {
      const gearPayload = fullGearPayloadForPage(this) || this.data.gearPayload || {}
      const currentSelectedGearBySlot = this.data.selectedGearBySlot || {}
      const currentEnhancementBySlot = this.data.enhancementBySlot || {}
      const selectedGearBySlot = prunedGearSelectionByWeaponRule(gearPayload, currentSelectedGearBySlot)
      const enhancementBySlot = prunedEnhancementBySlot(gearPayload, selectedGearBySlot, currentEnhancementBySlot)
      const selectionChanged = JSON.stringify(selectedGearBySlot) !== JSON.stringify(currentSelectedGearBySlot)
      const enhancementChanged = JSON.stringify(enhancementBySlot) !== JSON.stringify(currentEnhancementBySlot)
      if (selectionChanged || enhancementChanged) this.setData({
        ...(selectionChanged ? { selectedGearBySlot } : {}),
        ...(enhancementChanged ? { enhancementBySlot } : {}),
        gearSlotRows: buildGearSlotRows(gearPayload, selectedGearBySlot, enhancementBySlot),
        gearAttributePanel: this.gearWorkbenchState
          ? canonicalGearAttributePanel(
              acceptedGearDisplaySnapshot(this.gearWorkbenchState),
              this.data.gearStatSnapshot,
              this.communityEnhancementImportState
            )
          : buildGearAttributePanel(gearPayload, selectedGearBySlot, this.data.selectedSpec, enhancementBySlot, this.data.gearStatSnapshot)
      })
      this.setData({
        gearEnhancementSheet: buildGearEnhancementSheetForPage(this, true),
        gearSlotSheet: emptyGearSlotSheet(),
        gearCommunityTemplateSheet: emptyGearCommunityTemplateSheet()
      })
    }
    openWithCurrentPayload()
    return Promise.resolve()
  },

  closeGearEnhancementSheet() {
    this.setData({
      gearEnhancementSheet: emptyGearEnhancementSheet()
    })
  },

  selectGearEnhancementSlot(event) {
    const slot = event.currentTarget.dataset.slot || ''
    if (!slot) return Promise.resolve()
    const gearPayload = fullGearPayloadForPage(this) || this.data.gearPayload || {}
    const selectedGearBySlot = this.data.selectedGearBySlot || {}
    const currentSheet = this.data.gearEnhancementSheet || emptyGearEnhancementSheet()
    const enhancementBySlot = currentSheet.draftEnhancementBySlot || this.data.enhancementBySlot || {}
    const selectedItem = enrichedSelectedGearByCanonicalSlot(gearPayload, selectedGearBySlot)[slot]
    const needsDetail = gearPayloadNeedsSlotDetail(this, slot) &&
      gearEnhancementSlotNeedsDetail(gearPayload, selectedItem, normalizedEnhancementBySlot(enhancementBySlot)[slot])
    const nextSheet = buildGearEnhancementSheetForPage(this, true, slot)
    if (!needsDetail) {
      this.setData({ gearEnhancementSheet: nextSheet })
      return Promise.resolve()
    }
    nextSheet.loading = true
    if (nextSheet.emptyText) nextSheet.emptyText = '正在加载当前槽位的可配置选项...'
    this.setData({ gearEnhancementSheet: nextSheet })
    return loadGearSlotDetailForPage(this, slot)
      .catch(() => fullGearPayloadForPage(this) || gearPayload)
      .then(() => {
        const activeSheet = this.data.gearEnhancementSheet || {}
        if (!activeSheet.visible || activeSheet.activeSlot !== slot) return
        const refreshedPayload = fullGearPayloadForPage(this) || gearPayload
        const currentSelectedGearBySlot = this.data.selectedGearBySlot || selectedGearBySlot
        const refreshedSelectedGearBySlot = prunedGearSelectionByWeaponRule(refreshedPayload, currentSelectedGearBySlot)
        const refreshedEnhancementBySlot = prunedEnhancementBySlot(
          refreshedPayload,
          refreshedSelectedGearBySlot,
          activeSheet.draftEnhancementBySlot || enhancementBySlot
        )
        const selectionChanged = JSON.stringify(refreshedSelectedGearBySlot) !== JSON.stringify(currentSelectedGearBySlot)
        const enhancementChanged = JSON.stringify(refreshedEnhancementBySlot) !== JSON.stringify(activeSheet.draftEnhancementBySlot || enhancementBySlot)
        if (selectionChanged || enhancementChanged) this.setData({
          ...(selectionChanged ? { selectedGearBySlot: refreshedSelectedGearBySlot } : {}),
          ...(enhancementChanged ? { enhancementBySlot: refreshedEnhancementBySlot } : {}),
          gearSlotRows: buildGearSlotRows(refreshedPayload, refreshedSelectedGearBySlot, refreshedEnhancementBySlot),
          gearAttributePanel: this.gearWorkbenchState
            ? canonicalGearAttributePanel(
                acceptedGearDisplaySnapshot(this.gearWorkbenchState),
                this.data.gearStatSnapshot,
                this.communityEnhancementImportState
              )
            : buildGearAttributePanel(
              refreshedPayload,
              refreshedSelectedGearBySlot,
              this.data.selectedSpec,
              refreshedEnhancementBySlot,
              this.data.gearStatSnapshot
            )
        })
        this.setData({
          gearEnhancementSheet: buildGearEnhancementSheetForPage(this, true, slot)
        })
      })
  },

  selectGearEnhancementOption(event) {
    const slot = event.currentTarget.dataset.slot || ''
    const type = event.currentTarget.dataset.type || ''
    const optionId = event.currentTarget.dataset.id || ''
    if (!slot || !type || !optionId) return
    const sheet = this.data.gearEnhancementSheet || emptyGearEnhancementSheet()
    const rowsByType = {
      gem: sheet.gemRows || [],
      enchant: sheet.enchantRows || [],
      embellishment: sheet.embellishmentRows || []
    }
    const row = (rowsByType[type] || []).find((item) => item.slot === slot)
    const option = row && (row.options || []).find((item) => item.id === optionId)
    if (!row || !option || option.disabled) return
    const current = normalizedEnhancementBySlot(sheet.draftEnhancementBySlot || this.data.enhancementBySlot || {})
    const existing = current[slot] || {}
    const nextRecord = option.selected
      ? removeEnhancementType(existing, type, optionId)
      : { ...existing, ...enhancementSelectionFromOption(type, option, existing) }
    const compactRecord = compactEnhancementRecord(nextRecord)
    if (compactRecord) current[slot] = compactRecord
    else delete current[slot]
    this.setData({
      gearEnhancementSheet: buildGearEnhancementSheetForPage(this, true, sheet.activeSlot || slot, {
        selectedGearBySlot: this.data.selectedGearBySlot || {},
        enhancementBySlot: current
      })
    })
  },

  confirmGearEnhancementSheet() {
    const sheet = this.data.gearEnhancementSheet || emptyGearEnhancementSheet()
    const gearPayload = fullGearPayloadForPage(this) || this.data.gearPayload || {}
    const selectedGearBySlot = prunedGearSelectionByWeaponRule(gearPayload, this.data.selectedGearBySlot || {})
    const editorSelectedGearBySlot = this.gearWorkbenchState
      ? gearSelectionWithCanonicalEnhancementConstraints(selectedGearBySlot, canonicalWorkbenchSnapshot(this))
      : selectedGearBySlot
    const draftEnhancementBySlot = normalizedEnhancementBySlot(
      sheet.draftEnhancementBySlot || this.data.enhancementBySlot || {}
    )
    const draftGemBlockers = gemOptionIdentityBlockers(
      gearPayload,
      enrichedSelectedGearByCanonicalSlot(gearPayload, editorSelectedGearBySlot),
      draftEnhancementBySlot
    )
    if (draftGemBlockers.length) {
      const draftValidationSheet = buildGearEnhancementSheetForPage(this, true, sheet.activeSlot, {
        selectedGearBySlot,
        enhancementBySlot: draftEnhancementBySlot
      })
      draftValidationSheet.blockers = Array.from(new Set([
        ...draftGemBlockers,
        ...(draftValidationSheet.blockers || [])
      ]))
      showToast(draftGemBlockers[0])
      this.setData({
        selectedGearBySlot,
        gearEnhancementSheet: draftValidationSheet
      })
      return
    }
    const enhancementBySlot = prunedEnhancementBySlot(
      gearPayload,
      editorSelectedGearBySlot,
      draftEnhancementBySlot
    )
    const inheritedReplacementTargets = changedCanonicalEnhancementTargets(
      sheet.confirmedEnhancementBySlot || this.data.enhancementBySlot || {},
      enhancementBySlot
    )
    const validationSheet = buildGearEnhancementSheetForPage(this, true, sheet.activeSlot, {
      selectedGearBySlot,
      enhancementBySlot
    })
    if ((validationSheet.blockers || []).length || validationSheet.embellishmentUsed > validationSheet.embellishmentMax) {
      showToast((validationSheet.blockers || [])[0] || `美化已超过上限 ${validationSheet.embellishmentUsed}/${validationSheet.embellishmentMax}`)
      this.setData({
        selectedGearBySlot,
        gearEnhancementSheet: validationSheet
      })
      return
    }
    this.setData({
      selectedGearBySlot,
      enhancementBySlot,
      gearAttributePanel: this.gearWorkbenchState
        ? canonicalGearAttributePanel(
            acceptedGearDisplaySnapshot(this.gearWorkbenchState),
            this.data.gearStatSnapshot,
            this.communityEnhancementImportState
          )
        : buildGearAttributePanel(gearPayload, selectedGearBySlot, this.data.selectedSpec, enhancementBySlot, this.data.gearStatSnapshot),
      gearSlotRows: buildGearSlotRows(gearPayload, selectedGearBySlot, enhancementBySlot),
      gearEnhancementSheet: emptyGearEnhancementSheet()
    })
    return resolveOrRefreshGearForPage(this, selectedGearBySlot, enhancementBySlot, {
      replaceInheritedEvidence: true,
      inheritedReplacementTargets
    })
  },

  openGearCommunityTemplates() {
    if (this.data.gearDataFallback) {
      showToast(this.data.gearDataWarningText || '装备接口暂不可用，无法导入社区模板')
      return
    }
    this.refreshDerivedState()
    this.setData({
      savedGearTemplates: savedGearTemplatesForImport(),
      gearCommunityTemplateSheet: { visible: true },
      gearSlotSheet: emptyGearSlotSheet(),
      gearEnhancementSheet: emptyGearEnhancementSheet()
    })
  },

  closeGearCommunityTemplates() {
    this.setData({
      gearCommunityTemplateSheet: emptyGearCommunityTemplateSheet()
    })
  },

  resetGearSelection() {
    clearCommunityEnhancementImportState(this)
    const gearPayload = fullGearPayloadForPage(this)
    if (!gearPayload) {
      this.loadWebsimGearForSelection()
      return
    }
    const selectedGearBySlot = prunedGearSelectionByWeaponRule(
      gearPayload,
      equippedSetToSelection(gearPayload.equippedSet || {}, gearPayload)
    )
    const enhancementBySlot = {}
    const derivedState = createDetailDerivedState(this.data.selectedDetail, this.data.activeQueryKey, {
      ...this.data,
      gearPayload,
      selectedGearBySlot,
      enhancementBySlot
    })
    this.setData({
      ...derivedState,
      enhancementBySlot,
      gearSlotSheet: emptyGearSlotSheet(),
      gearEnhancementSheet: emptyGearEnhancementSheet(),
      gearCommunityTemplateSheet: emptyGearCommunityTemplateSheet()
    })
    const resolution = resolveOrRefreshGearForPage(this, selectedGearBySlot, enhancementBySlot)
    trackEvent('builds_gear_selection_reset', {
      specId: (this.data.selectedSpec && this.data.selectedSpec.id) || ''
    }, { page: 'pages/builds/detail' })
    return resolution
  },

  applySavedGearTemplate(event) {
    const templateId = event.currentTarget.dataset.id || ''
    const template = (this.data.savedGearTemplates || []).find((item) => item.id === templateId)
    if (!template || !template.canApplyGear) {
      showToast('保存模板暂不可导入')
      return
    }
    const gearPayload = fullGearPayloadForPage(this) || {}
    const baselineSelection = equippedSetToSelection(gearPayload.equippedSet || {}, gearPayload)
    const templateSelection = selectedGearByCanonicalSlot(template.savedGearBySlot || {})
    if (!Object.keys(templateSelection).length) {
      showToast('保存模板缺少装备配置')
      return
    }
    clearCommunityEnhancementImportState(this)
    const selectedGearBySlot = prunedGearSelectionByWeaponRule(gearPayload, {
      ...baselineSelection,
      ...templateSelection
    })
    const enhancementBySlot = prunedEnhancementBySlot(gearPayload, selectedGearBySlot, template.savedEnhancementBySlot || {})
    const derivedState = createDetailDerivedState(this.data.selectedDetail, this.data.activeQueryKey, {
      ...this.data,
      gearPayload,
      selectedGearBySlot,
      enhancementBySlot
    })
    this.setData({
      ...derivedState,
      enhancementBySlot,
      gearSlotSheet: emptyGearSlotSheet(),
      gearEnhancementSheet: emptyGearEnhancementSheet(),
      gearCommunityTemplateSheet: emptyGearCommunityTemplateSheet()
    })
    const resolution = resolveOrRefreshGearForPage(this, selectedGearBySlot, enhancementBySlot)
    trackEvent('builds_gear_saved_template_apply', {
      templateId,
      readySlotCount: Object.keys(templateSelection).length,
      specId: (this.data.selectedSpec && this.data.selectedSpec.id) || ''
    }, { page: 'pages/builds/detail' })
    return resolution
  },

  applyGearCommunityTemplate(event) {
    const templateId = event.currentTarget.dataset.id || ''
    const templates = this.data.activeGearCommunityTemplates || gearCommunityTemplatesForPayload(fullGearPayloadForPage(this) || {})
    const template = templates.find((item) => item.id === templateId)
    if (!template || !template.canApplyGear) {
      showToast('当前模板暂不可导入')
      return Promise.resolve()
    }
    const importSerial = Number(this.communityEnhancementImportSerial || 0) + 1
    const importSelectionKey = this.data.gearSelectionKey || (() => {
      const keys = specWebsimKeys(this.data.selectedSpec || {})
      return `${keys.classKey}:${keys.specKey}`
    })()
    this.communityEnhancementImportSerial = importSerial
    this.communityEnhancementImportState = {
      templateId,
      serial: importSerial,
      resolvedGearSignature: '',
      unresolvedBySlot: {},
      warnings: []
    }
    const importIsCurrent = () => {
      const state = this.communityEnhancementImportState || {}
      const currentKeys = specWebsimKeys(this.data.selectedSpec || {})
      const currentSelectionKey = this.data.gearSelectionKey || `${currentKeys.classKey}:${currentKeys.specKey}`
      return state.templateId === templateId && state.serial === importSerial && currentSelectionKey === importSelectionKey
    }
    const detailRequestContext = {
      requestKey: `community:${templateId}:${importSerial}`,
      shouldApply: importIsCurrent
    }
    const applyWithCurrentPayload = () => {
      if (!importIsCurrent()) return null
      const gearPayload = fullGearPayloadForPage(this) || {}
      const selectedGearBySlot = gearSelectionWithoutEmbeddedSimcEnhancements(repairedGearSelectionForSkippedWeapons(
        this,
        gearPayload,
        communityTemplateBaseGearSelection(gearPayload, template),
        template
      ))
      const reconciliation = reconcileCommunityTemplateEnhancements(
        gearPayload,
        selectedGearBySlot,
        communityTemplateRawEnhancementBySlot(template)
      )
      const enhancementBySlot = reconciliation.enhancementBySlot
      this.communityEnhancementImportState = {
        templateId,
        serial: importSerial,
        resolvedGearSignature: '',
        unresolvedBySlot: reconciliation.unresolvedBySlot,
        warnings: reconciliation.warnings
      }
      const derivedState = createDetailDerivedState(this.data.selectedDetail, this.data.activeQueryKey, {
        ...this.data,
        gearPayload,
        selectedGearBySlot,
        enhancementBySlot
      })
      this.setData({
        ...derivedState,
        enhancementBySlot,
        gearSlotSheet: emptyGearSlotSheet(),
        gearEnhancementSheet: emptyGearEnhancementSheet(),
        gearCommunityTemplateSheet: emptyGearCommunityTemplateSheet()
      })
      trackEvent('builds_gear_community_template_apply', {
        templateId,
        readySlotCount: template.readySlotCount || Object.keys(selectedGearBySlot || {}).length,
        specId: (this.data.selectedSpec && this.data.selectedSpec.id) || ''
      }, { page: 'pages/builds/detail' })
      return resolveOrRefreshGearForPage(this, selectedGearBySlot, enhancementBySlot, {
        communityImport: { templateId, serial: importSerial }
      })
    }
    const detailPromise = loadCommunityTemplateWeaponRepairDetails(this, template, detailRequestContext)
    return Promise.resolve(detailPromise)
      .then(() => importIsCurrent() ? loadCommunityTemplateEnhancementDetails(this, template, detailRequestContext) : null)
      .then(applyWithCurrentPayload)
  },

  setGearCandidateFilter(event) {
    const filterKey = event.currentTarget.dataset.key || 'all'
    const sheet = this.data.gearSlotSheet || {}
    if (!sheet.slot) return
    const candidates = gearSlotCandidatesForPage(this, sheet.slot, sheet.candidates)
    this.setData({
      gearSlotSheet: buildGearSlotSheet(sheet.slot, sheet.item || {}, candidates, {
        filterKey,
        candidateIndex: 0
      })
    })
  },

  selectGearCandidate(event) {
    const index = Number(event.currentTarget.dataset.index || 0)
    const sheet = this.data.gearSlotSheet || {}
    if (!sheet.slot) return
    const candidates = gearSlotCandidatesForPage(this, sheet.slot, sheet.candidates)
    this.setData({
      gearSlotSheet: buildGearSlotSheet(sheet.slot, sheet.item || {}, candidates, {
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
    const allCandidates = gearSlotCandidatesForPage(this, sheet.slot, candidates)
    this.setData({
      gearSlotSheet: buildGearSlotSheet(sheet.slot, sheet.item || {}, allCandidates, {
        filterKey: sheet.filterKey || 'all',
        candidateIndex: sheet.selectedCandidateIndex || 0,
        variantKey: sheet.variantKey || '',
        craftedStatOptionKey: sheet.craftedStatOptionKey || '',
        detailKey
      })
    })
  },

  selectGearVariant(event) {
    const key = event.currentTarget.dataset.key || ''
    const sheet = this.data.gearSlotSheet || {}
    if (!sheet.slot) return
    const candidates = gearSlotCandidatesForPage(this, sheet.slot, sheet.candidates)
    this.setData({
      gearSlotSheet: buildGearSlotSheet(sheet.slot, sheet.item || {}, candidates, {
        filterKey: sheet.filterKey || 'all',
        candidateIndex: sheet.selectedCandidateIndex || 0,
        variantKey: key,
        craftedStatOptionKey: '',
        detailKey: sheet.detailKey || ''
      })
    })
  },

  selectCraftedStatOption(event) {
    const key = event.currentTarget.dataset.key || ''
    const sheet = this.data.gearSlotSheet || {}
    if (!sheet.slot) return
    const candidates = gearSlotCandidatesForPage(this, sheet.slot, sheet.candidates)
    this.setData({
      gearSlotSheet: buildGearSlotSheet(sheet.slot, sheet.item || {}, candidates, {
        filterKey: sheet.filterKey || 'all',
        candidateIndex: sheet.selectedCandidateIndex || 0,
        variantKey: sheet.variantKey || '',
        craftedStatOptionKey: key,
        detailKey: sheet.detailKey || ''
      })
    })
  },

  applyGearCandidate() {
    const sheet = this.data.gearSlotSheet || {}
    const slot = sheet.slot || ''
    const candidate = sheet.appliedCandidate || appliedGearCandidate(sheet.activeCandidate, sheet.variantKey, sheet.craftedStatOptionKey)
    if (!slot || !candidate) return Promise.resolve()
    const gearPayload = fullGearPayloadForPage(this) || this.data.gearPayload || {}
    const canonicalResolverAvailable = completeResolverContext(gearPayload.resolverContext)
    const candidateCanEnterResolver = !!normalizedGearItemId(candidate)
    if (!(canonicalResolverAvailable ? candidateCanEnterResolver : (candidate.simcReady && gearTemplateLine(candidate)))) {
      const trust = gearTrustState(candidate, candidate.statusClass, candidate.reason)
      showToast(trust.blockerLabel || trust.reason || '该装备数据待补，暂不能应用')
      return Promise.resolve()
    }
    const selectedGearBySlot = prunedGearSelectionByWeaponRule(gearPayload, {
      ...(this.data.selectedGearBySlot || {}),
      [slot]: candidate
    })
    const enhancementBySlot = prunedEnhancementBySlot(gearPayload, selectedGearBySlot, this.data.enhancementBySlot || {})
    trackEvent('builds_gear_candidate_select', {
      gearSlot: slot,
      itemId: candidate.itemId || candidate.id || '',
      variantKey: candidate.variantKey || '',
      configReady: !!gearTemplateLine(candidate),
      specId: (this.data.selectedSpec && this.data.selectedSpec.id) || ''
    }, { page: 'pages/builds/detail' })
    const derivedState = createDetailDerivedState(this.data.selectedDetail, this.data.activeQueryKey, {
      ...this.data,
      gearPayload,
      selectedGearBySlot,
      enhancementBySlot
    })
    this.setData({
      ...derivedState,
      enhancementBySlot,
      gearSlotSheet: emptyGearSlotSheet(),
      gearEnhancementSheet: emptyGearEnhancementSheet()
    })
    return resolveOrRefreshGearForPage(this, selectedGearBySlot, enhancementBySlot)
  },

  selectGearTemplateScenario(event) {
    const index = Number(event.detail.value) || 0
    this.setData({
      selectedGearTemplateScenarioIndex: Math.max(0, Math.min(index, gearTemplateScenarios.length - 1))
    })
    maybeRefreshGearStatsForPage(this)
  },

  saveGearTemplate() {
    if (this.data.gearTemplateSaving) return
    const draft = gearTemplateSaveDraft(this)
    if (draft.blockMessage) {
      if (draft.state) this.setData(draft.state)
      showToast(draft.blockMessage)
      return
    }
    this.setData({
      selectedGearBySlot: draft.selectedGearBySlot,
      enhancementBySlot: draft.enhancementBySlot,
      gearSaveTemplateSheet: {
        visible: true,
        name: draft.defaultName,
        defaultName: draft.defaultName
      }
    })
  },

  closeGearSaveTemplateSheet() {
    if (this.data.gearTemplateSaving) return
    this.setData({ gearSaveTemplateSheet: emptyGearSaveTemplateSheet() })
  },

  updateGearTemplateName(event) {
    const name = trimGearTemplateTitle(event && event.detail ? event.detail.value : '')
    this.setData({
      gearSaveTemplateSheet: {
        ...(this.data.gearSaveTemplateSheet || emptyGearSaveTemplateSheet()),
        name
      }
    })
  },

  confirmSaveGearTemplate() {
    if (this.data.gearTemplateSaving) return Promise.resolve(null)
    const sheet = this.data.gearSaveTemplateSheet || {}
    const templateTitle = gearTemplateTitleOrDefault(sheet.name, sheet.defaultName)
    this.setData({
      gearSaveTemplateSheet: {
        ...sheet,
        name: templateTitle
      }
    })
    return persistGearTemplateForPage(this, templateTitle)
  },

  persistGearTemplate(templateTitle) {
    return persistGearTemplateForPage(this, templateTitle)
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
    if (this.data.activeQueryKey === 'gear' && !gearWorkbenchCanRunProfile(this.gearWorkbenchState)) {
      showToast('当前装备配置尚未通过服务端校验，暂不能进入 SimC')
      return
    }
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
