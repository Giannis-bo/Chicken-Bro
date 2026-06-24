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
const GEAR_ENHANCEMENT_SNAPSHOT_REVISION = 'websim-gear-enhancement-snapshot-v1'
const gearEnhancementMax = 2
const enchantableGearSlots = new Set(['back', 'chest', 'wrist', 'legs', 'feet', 'finger1', 'finger2', 'main_hand', 'off_hand'])
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

function selectedEnhancementRowCount(rows) {
  return (Array.isArray(rows) ? rows : []).filter((row) => {
    return Array.isArray(row.options) && row.options.some((option) => option.selected)
  }).length
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
  return text
    .split(/[；;，,\n]+/)
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => {
      const match = part.match(/[+-]?\d[\d,]*(?:\.\d+)?/)
      if (!match) return null
      const value = gearNumericValue(match[0])
      if (value === null) return null
      const label = part.replace(match[0], '').replace(/[+：:]/g, ' ').trim()
      const key = gearStatKeyForLabel(label || part, primaryKey)
      return key ? { key, value } : null
    })
    .filter(Boolean)
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
    primaryStat: gearAttributeMetric('intellect', '智力', null, '待补'),
    enhancementRows: [
      gearEnhancementMetric('embellishment', '美化', 0, gearEnhancementMax),
      gearEnhancementMetric('gem', '宝石', 0, 0),
      gearEnhancementMetric('enchant', '附魔', 0, 0)
    ],
    statRows: [
      gearAttributeMetric('stamina', '耐力', null, '待补'),
      gearAttributeMetric('haste', '急速', 0, '0'),
      gearAttributeMetric('crit', '暴击', 0, '0'),
      gearAttributeMetric('mastery', '精通', 0, '0'),
      gearAttributeMetric('versatility', '全能', 0, '0')
    ]
  }
}

function buildGearAttributePanel(gearPayload, selectedGearBySlot, selectedSpec, enhancementBySlot) {
  const requiredSlotsForPanel = requiredGearTemplateSlots(gearPayload || {})
  const indexedSelection = selectedGearByCanonicalSlot(selectedGearBySlot || {})
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
  const itemLevelAverage = itemLevels.length
    ? itemLevels.reduce((sum, value) => sum + value, 0) / itemLevels.length
    : null
  const payloadPrimary = payloadGearStatValue(gearPayload, primaryKey)
  const payloadStamina = payloadGearStatValue(gearPayload, 'stamina')
  const primaryValue = totals[primaryKey] > 0 ? totals[primaryKey] : payloadPrimary
  const staminaValue = totals.stamina > 0 ? totals.stamina : payloadStamina
  const enhancementSheet = buildGearEnhancementSheet(gearPayload, selectedGearBySlot, enhancementBySlot || {}, false)
  return {
    visible: true,
    summary: `已选 ${selectedItems.length}/${requiredSlotsForPanel.length} 槽`,
    itemLevel: gearAttributeMetric('itemLevel', '装备等级', itemLevelAverage, '待补'),
    primaryStat: gearAttributeMetric(primaryKey, gearPrimaryStatLabels[primaryKey] || '主属性', primaryValue, '待补'),
    enhancementRows: [
      gearEnhancementMetric('embellishment', '美化', enhancementSheet.embellishmentUsed, enhancementSheet.embellishmentMax),
      gearEnhancementMetric('gem', '宝石', selectedEnhancementRowCount(enhancementSheet.gemRows), enhancementSheet.gemRows.length),
      gearEnhancementMetric('enchant', '附魔', selectedEnhancementRowCount(enhancementSheet.enchantRows), enhancementSheet.enchantRows.length)
    ],
    statRows: [
      gearAttributeMetric('stamina', '耐力', staminaValue, '待补'),
      gearAttributeMetric('haste', '急速', totals.haste, '0'),
      gearAttributeMetric('crit', '暴击', totals.crit, '0'),
      gearAttributeMetric('mastery', '精通', totals.mastery, '0'),
      gearAttributeMetric('versatility', '全能', totals.versatility, '0')
    ]
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
  if (normalized.includes('crafted_stats') || normalized === 'crafted stats') return '缺少制造属性搭配'
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

function normalizedEnhancementBySlot(enhancementBySlot) {
  const result = {}
  Object.keys(enhancementBySlot || {}).sort().forEach((slot) => {
    const record = enhancementBySlot[slot]
    if (!record || typeof record !== 'object') return
    const next = {}
    ;['socketOptionId', 'enchantOptionId', 'embellishmentOptionId', 'gem_id', 'gem_bonus_id', 'gem_ilevel', 'enchant_id', 'embellishment'].forEach((key) => {
      const value = cleanGearString(record[key])
      if (value) next[key] = value
    })
    if (Object.keys(next).length) result[slot] = next
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

function enhancementOptionsForSlot(gearPayload, item, optionKey) {
  const slot = item && (item.slot || item.simcSlot)
  return uniqueEnhancementOptions([
    ...((item && Array.isArray(item[optionKey])) ? item[optionKey] : []),
    ...gearGroupOptionsForSlot(gearPayload, slot, optionKey)
  ])
}

function itemSupportsEnhancement(item, type, options) {
  const caps = item && item.modCapabilities ? item.modCapabilities : {}
  const slot = item && (item.slot || item.simcSlot)
  const hasItemOptions = (key) => !!(item && Array.isArray(item[key]) && item[key].length)
  if (type === 'gem') return !!(caps.hasSocket || item.supportsSocket || item.gem_id || item.gem_bonus_id || hasItemOptions('socketOptions'))
  if (type === 'enchant') return !!(caps.canEnchant || enchantableGearSlots.has(slot) || hasItemOptions('enchantOptions'))
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
      item.builtInEmbellishment ||
      item.intrinsicEmbellishment ||
      item.inherentEmbellishment ||
      (['built_in', 'builtin', 'intrinsic', 'item'].includes(cleanGearString(item.embellishmentSource).toLowerCase()) ? item.embellishment : '') ||
      item.embellishment
    )
  )
}

function enhancementOptionSelected(option, selected, type) {
  const simcOptions = option && option.simcOptions && typeof option.simcOptions === 'object' ? option.simcOptions : {}
  if (type === 'gem') {
    return !!(
      (selected.socketOptionId && option.id === selected.socketOptionId) ||
      (selected.gem_id && cleanGearString(simcOptions.gem_id) === selected.gem_id)
    )
  }
  if (type === 'enchant') {
    return !!(
      (selected.enchantOptionId && option.id === selected.enchantOptionId) ||
      (selected.enchant_id && cleanGearString(simcOptions.enchant_id) === selected.enchant_id)
    )
  }
  if (type === 'embellishment') {
    return !!(
      (selected.embellishmentOptionId && option.id === selected.embellishmentOptionId) ||
      (selected.embellishment && cleanGearString(simcOptions.embellishment) === selected.embellishment)
    )
  }
  return false
}

function enhancementOptionForData(option, selected, type, disabled) {
  const simcOptions = option && option.simcOptions && typeof option.simcOptions === 'object' ? option.simcOptions : {}
  const isSelected = enhancementOptionSelected(option, selected || {}, type)
  return {
    id: cleanGearString(option.id || option.key || option.label || option.name),
    label: cleanGearString(option.label || option.name || option.id || '强化选项'),
    selected: isSelected,
    disabled: !!(disabled && !isSelected),
    simcOptions
  }
}

function enhancementRow(slot, item, options, selected, type, disabled) {
  return {
    slot,
    label: gearSlotDisplayLabels[slot] || slot,
    itemName: itemDisplayName(item),
    selectedLabel: (options.find((option) => enhancementOptionSelected(option, selected || {}, type)) || {}).label || '',
    options: options.map((option) => enhancementOptionForData(option, selected || {}, type, disabled))
  }
}

function emptyGearEnhancementSheet() {
  return {
    visible: false,
    gemRows: [],
    enchantRows: [],
    embellishmentRows: [],
    embellishmentUsed: 0,
    embellishmentMax: gearEnhancementMax,
    blockers: [],
    emptyText: ''
  }
}

function buildGearEnhancementSheet(gearPayload, selectedGearBySlot, enhancementBySlot, visible) {
  const indexed = selectedGearByCanonicalSlot(selectedGearBySlot || {})
  const enhancement = normalizedEnhancementBySlot(enhancementBySlot || {})
  const builtInCount = Object.keys(indexed).filter((slot) => builtInEmbellishmentValue(indexed[slot])).length
  const selectedEmbellishmentCount = Object.keys(enhancement).filter((slot) => cleanGearString(enhancement[slot].embellishment)).length
  const embellishmentUsed = builtInCount + selectedEmbellishmentCount
  const gemRows = []
  const enchantRows = []
  const embellishmentRows = []
  const blockers = []
  if (embellishmentUsed > gearEnhancementMax) {
    blockers.push(`美化已超过上限 ${embellishmentUsed}/${gearEnhancementMax}`)
  }
  requiredGearTemplateSlots(gearPayload || {}).forEach((slot) => {
    const item = indexed[slot]
    if (!item) return
    const selected = enhancement[slot] || {}
    const socketOptions = enhancementOptionsForSlot(gearPayload, item, 'socketOptions')
    const enchantOptions = enhancementOptionsForSlot(gearPayload, item, 'enchantOptions')
    const embellishmentOptions = enhancementOptionsForSlot(gearPayload, item, 'embellishmentOptions')
    if (socketOptions.length && itemSupportsEnhancement(item, 'gem', socketOptions)) {
      gemRows.push(enhancementRow(slot, item, socketOptions, selected, 'gem', false))
    } else if (selected.gem_id) {
      blockers.push(`${gearSlotDisplay(slot)} 宝石已不兼容`)
    }
    if (enchantOptions.length && itemSupportsEnhancement(item, 'enchant', enchantOptions)) {
      enchantRows.push(enhancementRow(slot, item, enchantOptions, selected, 'enchant', false))
    } else if (selected.enchant_id) {
      blockers.push(`${gearSlotDisplay(slot)} 附魔已不兼容`)
    }
    if (embellishmentOptions.length && itemSupportsEnhancement(item, 'embellishment', embellishmentOptions) && !builtInEmbellishmentValue(item)) {
      embellishmentRows.push(enhancementRow(slot, item, embellishmentOptions, selected, 'embellishment', embellishmentUsed >= gearEnhancementMax))
    } else if (selected.embellishment) {
      blockers.push(`${gearSlotDisplay(slot)} 美化已不兼容`)
    }
  })
  const emptyText = gemRows.length || enchantRows.length || embellishmentRows.length
    ? ''
    : '当前已选装备没有可配置的宝石、附魔或美化。'
  return {
    visible: !!visible,
    gemRows,
    enchantRows,
    embellishmentRows,
    embellishmentUsed,
    embellishmentMax: gearEnhancementMax,
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
  const rowKeepsSelection = (type, slot) => {
    const row = rowsByType[type].get(slot)
    return !!(row && Array.isArray(row.options) && row.options.some((option) => option.selected))
  }
  const normalized = normalizedEnhancementBySlot(enhancementBySlot)
  Object.keys(normalized).forEach((slot) => {
    if (!rowKeepsSelection('gem', slot)) {
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

function enhancementSelectionFromOption(type, option) {
  const simcOptions = option && option.simcOptions && typeof option.simcOptions === 'object' ? option.simcOptions : {}
  if (type === 'gem') {
    return {
      socketOptionId: cleanGearString(option.id),
      gem_id: cleanGearString(simcOptions.gem_id),
      gem_bonus_id: cleanGearString(simcOptions.gem_bonus_id),
      gem_ilevel: cleanGearString(simcOptions.gem_ilevel)
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

function removeEnhancementType(record, type) {
  const next = { ...(record || {}) }
  if (type === 'gem') {
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
    'builtInEmbellishment',
    'intrinsicEmbellishment',
    'inherentEmbellishment',
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
        detailRows: gearCandidateDetailRows(displayCandidate),
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
      variantLabel: candidate.variantLabel || '',
      modSummary: gearModSummary(candidate),
      statusLabel: gearStatusLabel(trust.status),
      statusClass: gearStatusClass(trust.status),
      detailRows: gearCandidateDetailRows(candidate, trust),
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
    const item = enrichedGearItemFromCandidates(payload, slot, selection[slot] || ((payload.equippedSet || {})[slot]) || {})
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
  const gearDataFallback = !!(currentState.gearDataFallback || (gearPayload && gearPayload.dataStatus === 'blocked'))
  const selectedGearBySlot = currentState.selectedGearBySlot || {}
  const gearReadiness = currentState.gearReadiness || (gearPayload && gearPayload.readiness) || {}
  const gearSlotRows = buildGearSlotRows(gearPayload, selectedGearBySlot)
  const gearAttributePanel = buildGearAttributePanel(gearPayload, selectedGearBySlot, currentState.selectedSpec, currentState.enhancementBySlot)
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
    enhancementBySlot: {},
    gearSlotSheet: emptyGearSlotSheet(),
    gearEnhancementSheet: emptyGearEnhancementSheet(),
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
    const existingEnhancement = this.data.gearSelectionKey === selectionKey ? (this.data.enhancementBySlot || {}) : {}
    const hasExistingRows = Array.isArray(this.data.gearSlotRows) && this.data.gearSlotRows.length > 0
    if (this.data.gearSelectionKey !== selectionKey) {
      this.gearPayloadCache = null
      this.gearSlotCandidateCache = {}
    }
    this.setData({
      gearLoading: true,
      gearInitialLoading: !hasExistingRows,
      gearRequestError: '',
      gearDataFallback: false,
      gearDataWarningText: '',
      gearSelectionKey: selectionKey,
      gearSlotSheet: emptyGearSlotSheet(),
      gearEnhancementSheet: emptyGearEnhancementSheet(),
      gearCommunityTemplateSheet: emptyGearCommunityTemplateSheet()
    })
    requestWebsimGear(keys).then(({ payload, error, fromFallback }) => {
      if (this.data.gearSelectionKey !== selectionKey) return
      this.gearPayloadCache = payload
      this.gearSlotCandidateCache = {}
      const baselineSelection = equippedSetToSelection(payload.equippedSet || {}, payload)
      const selectedGearBySlot = {
        ...baselineSelection,
        ...existingSelection
      }
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
    this.setData(this.gearPayloadCache ? gearDerivedStateForData(nextState) : nextState)
  },

  openGearSlotSheet(event) {
    const slot = event.currentTarget.dataset.slot || ''
    if (!slot) return
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
  },

  closeGearSlotSheet() {
    this.setData({
      gearSlotSheet: emptyGearSlotSheet()
    })
  },

  openGearEnhancementSheet() {
    if (this.data.gearDataFallback) {
      showToast(this.data.gearDataWarningText || '装备接口暂不可用，无法配置强化')
      return
    }
    const gearPayload = fullGearPayloadForPage(this) || this.data.gearPayload || {}
    this.setData({
      gearEnhancementSheet: buildGearEnhancementSheet(
        gearPayload,
        this.data.selectedGearBySlot || {},
        this.data.enhancementBySlot || {},
        true
      ),
      gearSlotSheet: emptyGearSlotSheet(),
      gearCommunityTemplateSheet: emptyGearCommunityTemplateSheet()
    })
  },

  closeGearEnhancementSheet() {
    this.setData({
      gearEnhancementSheet: emptyGearEnhancementSheet()
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
    const current = normalizedEnhancementBySlot(this.data.enhancementBySlot || {})
    const existing = current[slot] || {}
    const nextRecord = option.selected
      ? removeEnhancementType(existing, type)
      : { ...existing, ...enhancementSelectionFromOption(type, option) }
    const compactRecord = compactEnhancementRecord(nextRecord)
    if (compactRecord) current[slot] = compactRecord
    else delete current[slot]
    const gearPayload = fullGearPayloadForPage(this) || this.data.gearPayload || {}
    this.setData({
      enhancementBySlot: current,
      gearAttributePanel: buildGearAttributePanel(gearPayload, this.data.selectedGearBySlot || {}, this.data.selectedSpec, current),
      gearEnhancementSheet: buildGearEnhancementSheet(gearPayload, this.data.selectedGearBySlot || {}, current, true)
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
    const gearPayload = fullGearPayloadForPage(this)
    if (!gearPayload) {
      this.loadWebsimGearForSelection()
      return
    }
    const selectedGearBySlot = equippedSetToSelection(gearPayload.equippedSet || {}, gearPayload)
    const enhancementBySlot = {}
    const derivedState = createDetailDerivedState(this.data.selectedDetail, this.data.activeQueryKey, {
      ...this.data,
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
    trackEvent('builds_gear_selection_reset', {
      specId: (this.data.selectedSpec && this.data.selectedSpec.id) || ''
    }, { page: 'pages/builds/detail' })
  },

  applyGearCommunityTemplate(event) {
    const templateId = event.currentTarget.dataset.id || ''
    const templates = this.data.activeGearCommunityTemplates || gearCommunityTemplatesForPayload(fullGearPayloadForPage(this) || {})
    const template = templates.find((item) => item.id === templateId)
    if (!template || !template.canApplyGear) {
      showToast('当前模板暂不可导入')
      return
    }
    const gearPayload = fullGearPayloadForPage(this) || {}
    const baselineSelection = equippedSetToSelection(gearPayload.equippedSet || {}, gearPayload)
    const templateSelection = gearItemsToSelection(template.gearItems || [])
    const selectedGearBySlot = {
      ...baselineSelection,
      ...templateSelection
    }
    const enhancementBySlot = prunedEnhancementBySlot(gearPayload, selectedGearBySlot, this.data.enhancementBySlot || {})
    const derivedState = createDetailDerivedState(this.data.selectedDetail, this.data.activeQueryKey, {
      ...this.data,
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
      readySlotCount: template.readySlotCount || Object.keys(templateSelection).length,
      specId: (this.data.selectedSpec && this.data.selectedSpec.id) || ''
    }, { page: 'pages/builds/detail' })
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
    if (!(candidate.simcReady && gearTemplateLine(candidate))) {
      const trust = gearTrustState(candidate, candidate.statusClass, candidate.reason)
      showToast(trust.blockerLabel || trust.reason || '该装备数据待补，暂不能应用')
      return Promise.resolve()
    }
    const selectedGearBySlot = {
      ...(this.data.selectedGearBySlot || {}),
      [slot]: candidate
    }
    const gearPayload = fullGearPayloadForPage(this) || this.data.gearPayload || {}
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
      selectedGearBySlot,
      enhancementBySlot
    })
    this.setData({
      ...derivedState,
      enhancementBySlot,
      gearSlotSheet: emptyGearSlotSheet(),
      gearEnhancementSheet: emptyGearEnhancementSheet()
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
    const gearPayload = fullGearPayloadForPage(this) || this.data.gearPayload || {}
    const configLines = canonicalGearTemplateLines(this.data.selectedGearBySlot || {}, gearPayload)
    const status = gearTemplateStatus(this.data.selectedGearBySlot || {}, gearPayload)
    const requiredCount = (status.requiredSlots || requiredGearSlots).length
    if (status.missingSlots.length || configLines.length !== requiredCount) {
      showToast(gearTemplateValidationMessage(status.issues, requiredCount) || `请补齐 ${requiredCount} 个装备槽位后再保存`)
      return
    }
    const scenario = gearScenarioAt(this.data.selectedGearTemplateScenarioIndex)
    const selectedDetail = this.data.selectedDetail || {}
    const selectedSpec = this.data.selectedSpec || {}
    const keys = specWebsimKeys(selectedSpec)
    const enhancementBySlot = prunedEnhancementBySlot(gearPayload, this.data.selectedGearBySlot || {}, this.data.enhancementBySlot || {})
    const enhancementSheet = buildGearEnhancementSheet(gearPayload, this.data.selectedGearBySlot || {}, enhancementBySlot, false)
    if ((enhancementSheet.blockers || []).length || enhancementSheet.embellishmentUsed > enhancementSheet.embellishmentMax) {
      showToast((enhancementSheet.blockers || [])[0] || `美化已超过上限 ${enhancementSheet.embellishmentUsed}/${enhancementSheet.embellishmentMax}`)
      this.setData({
        enhancementBySlot,
        gearEnhancementSheet: {
          ...enhancementSheet,
          visible: this.data.gearEnhancementSheet && this.data.gearEnhancementSheet.visible
        }
      })
      return
    }
    const snapshot = gearTemplateSnapshot(this.data.selectedGearBySlot || {}, enhancementBySlot, gearPayload)
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
      rawString: JSON.stringify(snapshot),
      simcLines: [],
      status: status.status,
      statusLabel: status.statusLabel,
      source: '装备模拟器',
      metadata: {
        gearSnapshot: snapshot,
        gearBySlot: snapshot.gearBySlot,
        enhancementBySlot,
        selectedGearSnapshot: this.data.selectedGearBySlot || {},
        selectedItems,
        configLineCount: configLines.length,
        missingSlots: [],
        statPendingSlots: status.statPendingSlots || [],
        sourcePendingSlots: status.sourcePendingSlots || [],
        craftedStatSelections: craftedStatSelections(this.data.selectedGearBySlot || {}),
        warningSummary: status.warningSummary || '',
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
