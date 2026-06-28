const { requestSimulatorAnalysis, requestSimulatorTasks } = require('./simulator-api')
const { fallbackBuildsHome, requestBuildsHome } = require('../builds/builds-api')
const { requestWebsimGearStats } = require('../builds/websim-api')
const { fetchBuildTemplates, listBuildTemplates, syncBuildTemplate } = require('../common/build-template-storage')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')

const SIMC_PAGE_ROUTE = ['pages', 'simulator', 'simc'].join('/')
const fallbackPayload = fallbackBuildsHome()
const ACTIVE_SIMC_TASK_LIMIT = 2
const ACTIVE_SIMC_TASK_STATUSES = { queued: true, running: true }

const SCENARIO_OPTIONS = [
  { key: 'single', title: '单体', desc: '固定单目标，5分钟' },
  { key: 'aoe_5', title: '5目标AOE', desc: '固定5目标，5分钟' },
  { key: 'mythic_plus', title: '近似大秘境', desc: '平均4目标，6分钟' }
]

function scenarioOptionForKey(key) {
  return SCENARIO_OPTIONS.find((item) => item.key === key) || null
}

function scenarioTitleForKey(key) {
  const option = scenarioOptionForKey(key)
  return option ? option.title : cleanSummaryText(key)
}

function activeTaskLimitMessage(activeCount, limit = ACTIVE_SIMC_TASK_LIMIT) {
  const count = Number(activeCount) || limit
  return `已有 ${count} 个模拟任务正在排队或运行，请等待前面的任务完成后再提交。`
}

function taskActiveState(task) {
  const report = task && task.simcReportSummary ? task.simcReportSummary : {}
  return cleanSummaryText(report.state || task && task.status).toLowerCase()
}

function taskMode(task) {
  const report = task && task.simcReportSummary ? task.simcReportSummary : {}
  return cleanSummaryText(task && task.mode || report.mode || '')
}

function activeSimcTemplateTaskCount(tasks) {
  return (Array.isArray(tasks) ? tasks : []).filter((task) => {
    const mode = taskMode(task)
    if (mode && mode !== 'simcraft_template') return false
    return !!ACTIVE_SIMC_TASK_STATUSES[taskActiveState(task)]
  }).length
}

function taskLimitStateFromPayload(payload, fallbackLimit = ACTIVE_SIMC_TASK_LIMIT) {
  const lock = payload && payload.taskLock
  if (!lock || lock.reason !== 'active_simc_task_limit') return null
  const limit = Number(lock.limit) || fallbackLimit
  const activeCount = Number(lock.activeCount) || limit
  return {
    activeTaskCount: activeCount,
    activeTaskLimit: limit,
    activeTaskLimitReached: true,
    activeTaskLimitMessage: activeTaskLimitMessage(activeCount, limit)
  }
}

const TEMPORARY_BUFF_OPTIONS = [
  {
    key: 'bloodlust',
    title: '嗜血 / 英勇',
    desc: '临时团队爆发，默认关闭'
  },
  {
    key: 'combatPotion',
    title: '爆发药水',
    desc: '通用战斗药水，默认关闭'
  },
  {
    key: 'weaponOil',
    title: '武器涂油',
    desc: '临时武器强化，默认关闭'
  }
]

const SELF_CLASS_RAID_BUFFS = {
  druid: { label: '野性印记' },
  mage: { label: '奥术智慧' },
  priest: { label: '真言术：韧' },
  shaman: { label: '天怒' },
  warrior: { label: '战斗怒吼' }
}

const SPEC_COMBAT_PREPARATION = {
  'shaman:enhancement': {
    label: '风怒武器、火舌武器',
    copy: '增强萨满会识别风怒武器、火舌武器；当前仍待 SimC profile smoke 验证，暂不自动写入。'
  },
  'rogue:assassination': {
    label: '盗贼毒药',
    copy: '刺杀盗贼会识别毒药准备；当前仍待 SimC profile smoke 验证，暂不自动写入。'
  },
  'rogue:outlaw': {
    label: '盗贼毒药',
    copy: '狂徒盗贼会识别毒药准备；当前仍待 SimC profile smoke 验证，暂不自动写入。'
  },
  'rogue:subtlety': {
    label: '盗贼毒药',
    copy: '敏锐盗贼会识别毒药准备；当前仍待 SimC profile smoke 验证，暂不自动写入。'
  }
}

const ANALYSIS_STATUS_TEXT = {
  template_ready: '组合校验通过',
  queued: '任务已提交',
  running: '正在模拟',
  completed: '模拟完成',
  failed: '模拟失败'
}

const PREPARATION_CATEGORY_LABELS = {
  self_class_raid_buff: '团队增益',
  spec_combat_preparation: '职业准备',
  temporary_combat_buffs: '临时增益'
}

const PREPARATION_STATE_LABELS = {
  enabled: '已开启',
  disabled: '未开启',
  pending_evidence: '待验证',
  not_applicable: '无增益'
}

const PREPARATION_VALUE_LABELS = {
  'Mark of the Wild': '野性印记',
  'Arcane Intellect': '奥术智慧',
  'Power Word: Fortitude': '真言术：韧',
  Skyfury: '天怒',
  'Battle Shout': '战斗怒吼',
  'Enhancement weapon imbues': '风怒武器、火舌武器',
  'Rogue poisons': '盗贼毒药',
  'Bloodlust/Heroism': '嗜血 / 英勇',
  'Combat potion': '爆发药水',
  'Weapon oil or sharpening stone': '武器涂油'
}

const PREPARATION_VALUE_ALIASES = {
  'mark of the wild': '野性印记',
  'arcane intellect': '奥术智慧',
  'power word: fortitude': '真言术：韧',
  skyfury: '天怒',
  'battle shout': '战斗怒吼',
  'enhancement weapon imbues': '风怒武器、火舌武器',
  'rogue poisons': '盗贼毒药',
  'bloodlust/heroism': '嗜血 / 英勇',
  'combat potion': '爆发药水',
  'weapon oil or sharpening stone': '武器涂油'
}

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

const SELECTOR_META = {
  class: { title: '选择职业', kicker: '职业' },
  race: { title: '选择种族', kicker: '种族' },
  talent: { title: '选择天赋模板', kicker: '天赋模板' },
  gear: { title: '选择装备模板', kicker: '装备模板' }
}

function emptySelectorSheet() {
  return {
    visible: false,
    type: '',
    title: '',
    kicker: '',
    options: [],
    emptyText: ''
  }
}

function templateSelectorDesc(template) {
  const parts = [
    cleanSummaryText(template && template.specName),
    cleanSummaryText(template && template.heroLabel),
    cleanSummaryText(template && template.status)
  ].filter(Boolean)
  return parts.join(' / ')
}

function selectorOptionsFor(type, data) {
  if (type === 'class') {
    return (data.classOptions || []).map((item, index) => ({
      key: item.key || `class-${index}`,
      label: item.name || item.key || '未命名职业',
      desc: '',
      selected: index === data.selectedClassIndex
    }))
  }
  if (type === 'race') {
    return (data.raceOptions || []).map((item, index) => ({
      key: item.key || `race-${index}`,
      label: item.name || item.key || '未命名种族',
      desc: '',
      selected: index === data.selectedRaceIndex
    }))
  }
  if (type === 'talent') {
    return (data.talentTemplates || []).map((item, index) => ({
      key: item.id || `talent-${index}`,
      label: item.title || item.name || '未命名天赋模板',
      desc: templateSelectorDesc(item),
      selected: index === data.selectedTalentTemplateIndex
    }))
  }
  if (type === 'gear') {
    return (data.gearTemplates || []).map((item, index) => ({
      key: item.id || `gear-${index}`,
      label: item.title || item.name || '未命名装备模板',
      desc: templateSelectorDesc(item),
      selected: index === data.selectedGearTemplateIndex
    }))
  }
  return []
}

function selectorSheetFor(type, data) {
  const meta = SELECTOR_META[type]
  if (!meta) return emptySelectorSheet()
  const options = selectorOptionsFor(type, data || {})
  return {
    visible: true,
    type,
    title: meta.title,
    kicker: meta.kicker,
    options,
    emptyText: options.length ? '' : '暂无可选项'
  }
}

function compactTemplate(template, options = {}) {
  if (!template) return null
  const compact = {
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
  const metadata = template.metadata && typeof template.metadata === 'object' ? template.metadata : {}
  const compactMetadata = {}
  if (metadata.gearSnapshot) {
    compactMetadata.gearSnapshot = metadata.gearSnapshot
  }
  if (options.statSnapshot) compactMetadata.statSnapshot = options.statSnapshot
  if (Object.keys(compactMetadata).length) compact.metadata = compactMetadata
  return compact
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

const SIMC_SLOT_LABELS = {
  head: '头部',
  neck: '项链',
  shoulder: '肩部',
  back: '披风',
  chest: '胸甲',
  wrist: '护腕',
  hands: '手套',
  waist: '腰带',
  legs: '腿部',
  feet: '脚部',
  finger1: '戒指1',
  finger2: '戒指2',
  trinket1: '饰品1',
  trinket2: '饰品2',
  main_hand: '主手',
  off_hand: '副手'
}

const SIMC_FIELD_LABELS = {
  ilevel: '装等',
  itemid: '物品 ID',
  'item id': '物品 ID',
  item_id: '物品 ID',
  bonus_id: 'bonus',
  gem_id: '宝石',
  enchant_id: '附魔',
  crafted_stats: '制造属性',
  'bonus_id/gem_id/enchant_id': 'bonus/宝石/附魔'
}

const SIMC_ENHANCEMENT_LABELS = {
  socket: '宝石',
  enchant: '附魔',
  embellishment: '美化',
  gear: '装备'
}

function cleanSummaryText(value) {
  return String(value === undefined || value === null ? '' : value).trim()
}

function simcSlotLabel(value) {
  const key = cleanSummaryText(value).replace(/\.$/, '')
  return SIMC_SLOT_LABELS[key] || key
}

function localizedSimcSlotList(value) {
  return cleanSummaryText(value)
    .replace(/\.$/, '')
    .split(',')
    .map((item) => simcSlotLabel(item.trim()))
    .filter(Boolean)
    .join('、')
}

function localizedMissingGearSlotsText(value) {
  const text = cleanSummaryText(value)
  const match = text.match(/^(?:Missing core SimC gear slots|missing gear slots):\s*(.+?)\.?$/i)
  if (!match) return ''
  const slots = localizedSimcSlotList(match[1])
  return slots ? `缺少可执行装备槽位：${slots}` : '缺少可执行装备槽位'
}

function localizedItemNameDiagnosticText(value) {
  const text = cleanSummaryText(value)
  const match = text.match(/^Trivial:\s*Player\b.*?\bat slot\s+([a-z0-9_]+)\b.*?has inconsistency between name\b/i)
  if (!match) return ''
  const slot = simcSlotLabel(match[1])
  return `${slot}装备数据不一致：装备名称和物品 ID 对不上，请重新选择或保存${slot}。`
}

function localizedMissingFieldLabel(value) {
  const key = cleanSummaryText(value).toLowerCase()
  return SIMC_FIELD_LABELS[key] || key
}

function localizedMissingFieldList(value) {
  return cleanSummaryText(value)
    .replace(/\.$/, '')
    .split(',')
    .map((item) => localizedMissingFieldLabel(item))
    .filter(Boolean)
    .join('、')
}

function localizedGearFieldDiagnosticText(value) {
  const text = cleanSummaryText(value)
  const missingItemId = text.match(/^missing item id for gear slot:\s*([a-z0-9_]+)\.?$/i)
  if (missingItemId) return `${simcSlotLabel(missingItemId[1])}缺少物品 ID`
  const missingSlotField = text.match(/^([a-z0-9_]+)\s+missing\s+(.+?)\.?$/i)
  if (missingSlotField) {
    const fields = localizedMissingFieldList(missingSlotField[2])
    return `${simcSlotLabel(missingSlotField[1])}缺少${fields || '可执行装备字段'}`
  }
  const normalized = text.toLowerCase()
  if (/^selected candidate item\(s\) are missing simc fields/.test(normalized)) {
    return '部分已选装备缺少 SimC 字段，请回到装备模板检查阻断项。'
  }
  if (SIMC_FIELD_LABELS[normalized]) return `缺少 ${SIMC_FIELD_LABELS[normalized]}字段`
  return ''
}

function localizedEnhancementDiagnosticText(value) {
  const text = cleanSummaryText(value)
  const match = text.match(/^([a-z0-9_]+)\s+(socket|enchant|embellishment|gear)\b/i)
  if (match) {
    const slot = simcSlotLabel(match[1])
    const typeLabel = SIMC_ENHANCEMENT_LABELS[match[2].toLowerCase()] || '增益'
    if (/missing selected gear/i.test(text)) return `${slot}缺少已选装备，无法应用${typeLabel}。`
    if (/not in verified rank-two catalog/i.test(text)) return `${slot}${typeLabel}未通过验证：不在已验证目录中。`
    if (/incompatible/i.test(text)) return `${slot}${typeLabel}与当前装备不兼容。`
  }
  const limit = text.match(/^(primary_stat_gem gem|embellishment) limit exceeded:\s*(\d+)\/(\d+)/i)
  if (limit) {
    const label = limit[1].toLowerCase().startsWith('primary') ? '主属性宝石' : '美化'
    return `${label}已超过上限 ${limit[2]}/${limit[3]}`
  }
  return ''
}

function verifiedSummarySnapshot(snapshot) {
  return snapshot && typeof snapshot === 'object' && snapshot.statStatus === 'verified' ? snapshot : null
}

function stableTextHash(value) {
  const text = String(value === undefined || value === null ? '' : value)
  let hash = 2166136261
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0).toString(36)
}

function summaryStatsRequestSignature(request) {
  const raw = JSON.stringify(request || {})
  if (raw.length <= 4096) return raw
  return JSON.stringify({
    classKey: request && request.classKey,
    specKey: request && request.specKey,
    raceKey: request && request.raceKey,
    level: request && request.level,
    scenarioKey: request && request.scenarioKey,
    talentsHash: stableTextHash(request && request.talents),
    rawStringHash: stableTextHash(request && request.rawString),
    metadataHash: stableTextHash(JSON.stringify((request && request.metadata) || {}))
  })
}

function summaryStatsInvalidationState() {
  return {
    summaryStatsLoading: false,
    summaryStatsRequestSignature: '',
    summaryStatSnapshot: null,
    summaryStatSnapshotSignature: ''
  }
}

function defaultTemporaryBuffOptions() {
  return TEMPORARY_BUFF_OPTIONS.map((item) => ({ ...item, enabled: false }))
}

function selectedTemporaryBuffs(options) {
  const selected = {}
  ;(options || []).forEach((item) => {
    if (item && item.key && item.enabled) selected[item.key] = true
  })
  return selected
}

function selectedSpecKey(data) {
  return cleanSummaryText(
    (data.selectedTalentTemplate && data.selectedTalentTemplate.specKey)
    || (data.selectedGearTemplate && data.selectedGearTemplate.specKey)
    || ''
  )
}

function selectedSpecName(data) {
  return cleanSummaryText(
    (data.selectedTalentTemplate && data.selectedTalentTemplate.specName)
    || (data.selectedGearTemplate && data.selectedGearTemplate.specName)
    || ''
  )
}

function combatPreparationRowsForSelection(data) {
  const source = data || {}
  const classKey = cleanSummaryText(source.selectedClassKey)
  const specKey = selectedSpecKey(source)
  const raidBuff = SELF_CLASS_RAID_BUFFS[classKey] || null
  const specPreparation = SPEC_COMBAT_PREPARATION[`${classKey}:${specKey}`] || null

  return [
    {
      key: 'raid_buff',
      label: '团队增益',
      value: raidBuff ? raidBuff.label : '无增益'
    },
    {
      key: 'spec_preparation',
      label: '职业准备',
      value: specPreparation ? specPreparation.label : '无增益'
    }
  ]
}

function requestFailureMessage(error, fallbackText = 'request failed') {
  return cleanSummaryText(error && error.message) || fallbackText
}

const SIMC_STAT_SNAPSHOT_CRASH_TEXT = 'SimC 属性计算崩溃：当前组合暂时无法完成装备属性校验，请稍后重试，或更换天赋、装备或场景。'
const SIMC_TASK_CRASH_TEXT = 'SimC 执行失败：当前组合运行时崩溃，后端未能产出可用结果。请稍后重试，或检查天赋、装备和场景。'

function isRawSimcCrashDiagnostic(text) {
  return /sim_signal_handler|segmentation fault|\bsigsegv\b|\bsignal\s*11\b/i.test(cleanSummaryText(text))
}

function localizedSimcUserText(value) {
  const text = cleanSummaryText(value)
  if (!text) return ''
  const missingGearSlots = localizedMissingGearSlotsText(text)
  if (missingGearSlots) return missingGearSlots
  const itemNameDiagnostic = localizedItemNameDiagnosticText(text)
  if (itemNameDiagnostic) return itemNameDiagnostic
  const gearFieldDiagnostic = localizedGearFieldDiagnosticText(text)
  if (gearFieldDiagnostic) return gearFieldDiagnostic
  const enhancementDiagnostic = localizedEnhancementDiagnosticText(text)
  if (enhancementDiagnostic) return enhancementDiagnostic
  if (isRawSimcCrashDiagnostic(text)) return SIMC_TASK_CRASH_TEXT
  const timeout = text.match(/timed out after\s+(\d+)\s+seconds?/i)
  if (timeout) {
    return `SimC 执行超时：当前组合已经开始运行，但本次模拟超过 ${timeout[1]} 秒未完成。可以稍后重试，或等待前面的任务完成后再提交。`
  }
  if (/Invalid 'class_talents'/i.test(text)) {
    return 'SimC 执行失败：当前天赋字符串不被 SimC 识别。请重新保存天赋模板，或更换模板后再试。'
  }
  if (/no parseable dps/i.test(text)) {
    return 'SimC 执行失败：本次运行没有解析到可用 DPS 结果。请稍后重试，或检查当前模板。'
  }
  if (/traceback|^command\b|\bitem_\d+\b|\bwebsim_[a-z0-9_]+\b|\bsimulationcraft\b/i.test(text)) {
    return 'SimC 执行失败：后端未能完成当前组合模拟。请稍后重试，或检查天赋、装备和场景。'
  }
  if (/simc/i.test(text) && /(failed|error|invalid|unable|missing|could not|timeout|timed out|parseable)/i.test(text)) {
    return 'SimC 执行失败：后端未能完成当前组合模拟。请稍后重试，或检查天赋、装备和场景。'
  }
  return text
}

function analysisStatusText(status) {
  const key = cleanSummaryText(status)
  return ANALYSIS_STATUS_TEXT[key] || key
}

function preparationValueLabel(value) {
  const text = cleanSummaryText(value)
  const normalized = text.replace(/\.$/, '').replace(/^and\s+/i, '').trim().toLowerCase()
  return PREPARATION_VALUE_LABELS[text] || PREPARATION_VALUE_ALIASES[normalized] || text
}

function temporaryBuffText(summary, state) {
  if (state === 'disabled') return '未选择'
  const text = cleanSummaryText(summary)
  if (!text) return state === 'enabled' ? '已选择' : ''
  return text
    .split(',')
    .map((item) => preparationValueLabel(item))
    .filter(Boolean)
    .join('、') || text
}

function preparationValueText(item) {
  const category = cleanSummaryText(item && item.category)
  const state = cleanSummaryText(item && item.state)
  if (category === 'temporary_combat_buffs') {
    return temporaryBuffText(item && item.summary, state)
  }
  if (category === 'self_class_raid_buff' && state === 'not_applicable') return '无增益'
  return preparationValueLabel(item && item.label) || cleanSummaryText(item && item.summary)
}

function preparationStateText(item, category) {
  const state = cleanSummaryText(item && item.state)
  if (category === 'temporary_combat_buffs' && state === 'enabled') return '已选择'
  if (category === 'temporary_combat_buffs' && state === 'disabled') return '未选择'
  return PREPARATION_STATE_LABELS[state] || state || cleanSummaryText(item && item.evidenceState)
}

function preparationRows(preparation) {
  const source = preparation && typeof preparation === 'object' ? preparation : {}
  const items = Array.isArray(source.items) ? source.items : []
  return items
    .map((item) => {
      const category = cleanSummaryText(item && item.category)
      const label = PREPARATION_CATEGORY_LABELS[category]
      if (!label) return null
      const valueText = preparationValueText(item)
      if (!valueText) return null
      return {
        key: cleanSummaryText(item && item.key) || category,
        label,
        valueText,
        stateText: preparationStateText(item, category)
      }
    })
    .filter(Boolean)
}

function compactAnalysisState(payload) {
  const status = cleanSummaryText(((payload || {}).agent || {}).status)
  if (!status) return null
  const compact = {
    agent: {
      status,
      statusText: analysisStatusText(status)
    }
  }
  const simcReport = payload && payload.simcReport
  if (simcReport) {
    compact.simcReport = {
      schemaRevision: simcReport.schemaRevision,
      state: simcReport.state,
      result: simcReport.result || {}
    }
    const rows = preparationRows(simcReport.preparation)
    if (rows.length) {
      compact.preparation = {
        hasRows: true,
        rows
      }
    }
  }
  return compact
}

function analysisWithoutStatusCard(analysis) {
  if (!analysis || typeof analysis !== 'object') return null
  const compact = { ...analysis }
  delete compact.agent
  return Object.keys(compact).length ? compact : null
}

function statSnapshotFromTemplate(template, expectedSignature = '') {
  const metadata = (template && template.metadata) || {}
  const snapshot = verifiedSummarySnapshot(statSnapshotPayloadFromTemplate(template))
  const storedSignature = cleanSummaryText(metadata.statSnapshotSignature || '')
  if (snapshot && storedSignature && expectedSignature && storedSignature !== expectedSignature) return null
  return snapshot
}

function statSnapshotPayloadFromTemplate(template) {
  const metadata = (template && template.metadata) || {}
  const snapshot = metadata.statSnapshot || metadata.gearStatSnapshot || null
  return snapshot && typeof snapshot === 'object' ? snapshot : null
}

function statSnapshotFromAnalysis(payload) {
  return verifiedSummarySnapshot(statSnapshotPayloadFromAnalysis(payload))
}

function statSnapshotPayloadFromAnalysis(payload) {
  const details = (((payload || {}).request || {}).buildContext || {}).details || {}
  const statWeights = details.statWeights || {}
  const snapshot = (payload && payload.statSnapshot) ||
    statWeights.statSnapshot ||
    ((payload && payload.request) || {}).statSnapshot ||
    null
  return snapshot && typeof snapshot === 'object' ? snapshot : null
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

function summaryStatBlockerText(payload) {
  const blockers = Array.isArray(payload && payload.blockers) ? payload.blockers : []
  const messages = uniqueList(blockers.map(summarySingleStatBlockerText).filter(Boolean))
  return messages.slice(0, 3).join('；')
}

function summarySingleStatBlockerText(value) {
  const text = cleanSummaryText(value)
  if (!text) return ''
  const missingSlots = localizedMissingGearSlotsText(text)
  if (missingSlots) return missingSlots
  const itemNameDiagnostic = localizedItemNameDiagnosticText(text)
  if (itemNameDiagnostic) return itemNameDiagnostic
  const gearFieldDiagnostic = localizedGearFieldDiagnosticText(text)
  if (gearFieldDiagnostic) return gearFieldDiagnostic
  const enhancementDiagnostic = localizedEnhancementDiagnosticText(text)
  if (enhancementDiagnostic) return enhancementDiagnostic
  if (isRawSimcCrashDiagnostic(text)) return SIMC_STAT_SNAPSHOT_CRASH_TEXT
  if (/backend unavailable|missing api base url/i.test(text)) return '属性计算接口暂不可用'
  const localized = localizedSimcUserText(text)
  if (localized !== text) return localized
  if (/traceback|^command\b|\bitem_\d+\b|\bwebsim_[a-z0-9_]+\b|\bsimulationcraft\b|seed=|targethealth=/i.test(text)) {
    return '装备属性暂不可用：后端未能完成当前装备属性计算'
  }
  return localized
}

function summaryStatBlockerTextFromTemplate(template) {
  const snapshot = statSnapshotPayloadFromTemplate(template)
  if (!snapshot || snapshot.statStatus === 'verified') return ''
  return summaryStatBlockerText(snapshot)
}

function summaryStatPanelFromSnapshot(snapshot, pendingText = SUMMARY_STAT_PENDING_TEXT.pending, noteText = '') {
  const source = verifiedSummarySnapshot(snapshot)
  const secondary = Array.isArray(source && source.secondary) ? source.secondary : []
  const primary = source && source.primary ? source.primary : null
  const fallbackText = source ? SUMMARY_STAT_PENDING_TEXT.pending : pendingText
  return {
    statStatus: source ? 'verified' : 'pending',
    noteText: cleanSummaryText(noteText),
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

function summaryStatPanelFromBlockedPayload(payload, pendingText = SUMMARY_STAT_PENDING_TEXT.unavailable) {
  return summaryStatPanelFromSnapshot(null, pendingText, summaryStatBlockerText(payload))
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
  if (snapshot) return summaryStatPanelFromSnapshot(snapshot, SUMMARY_STAT_PENDING_TEXT.pending)
  const blockerText = summaryStatBlockerTextFromTemplate(selection && selection.selectedGearTemplate)
  if (blockerText) return summaryStatPanelFromSnapshot(null, SUMMARY_STAT_PENDING_TEXT.unavailable, blockerText)
  return summaryStatPanelFromSnapshot(null, summaryPendingTextForSelection(selection, fallbackText))
}

function statSnapshotForSelection(data) {
  const request = summaryStatsRequestForSelection(data, { ignoreSnapshot: true })
  const signature = request ? summaryStatsRequestSignature(request) : ''
  const current = verifiedSummarySnapshot(data && data.summaryStatSnapshot)
  if (current && signature && cleanSummaryText(data && data.summaryStatSnapshotSignature) === signature) {
    return current
  }
  return statSnapshotFromTemplate(
    data && data.selectedGearTemplate,
    signature
  )
}

function gearStatValidationMessage(data) {
  if (!data || !data.selectedTalentTemplate || !data.selectedGearTemplate) return ''
  const request = summaryStatsRequestForSelection(data, { ignoreSnapshot: true })
  if (statSnapshotForSelection(data)) return ''
  const panel = data.summaryStatPanel || {}
  const note = cleanSummaryText(panel.noteText)
  if (data.summaryStatsLoading) return '装备属性正在计算：请等待属性计算完成后再校验组合。'
  const templateBlocker = summaryStatBlockerTextFromTemplate(data.selectedGearTemplate)
  if (templateBlocker) return `装备属性未通过校验：${templateBlocker}`
  if (note) {
    const detail = note.replace(/^装备属性(?:暂)?不可用[:：]?/, '').trim()
    return `装备属性未通过校验：${detail || note}`
  }
  if (!request) return '装备属性未完成校验：当前装备模板缺少可计算的装备快照。'
  return '装备属性未完成校验：请等待属性计算完成后再校验组合。'
}

function templateValidationForSelection(data) {
  const errors = []
  const statMessage = gearStatValidationMessage(data)
  if (statMessage) errors.push(statMessage)
  return {
    passed: !errors.length,
    errors,
    warnings: []
  }
}

function summaryStatPanelFromAnalysis(payload, fallbackTemplate, currentPanel) {
  const snapshot = statSnapshotFromAnalysis(payload) || statSnapshotFromTemplate(fallbackTemplate)
  if (snapshot) return summaryStatPanelFromSnapshot(snapshot)
  const payloadSnapshot = statSnapshotPayloadFromAnalysis(payload)
  if (payloadSnapshot && payloadSnapshot.statStatus !== 'verified') {
    const blockerText = summaryStatBlockerText(payloadSnapshot)
    if (blockerText) return summaryStatPanelFromSnapshot(null, SUMMARY_STAT_PENDING_TEXT.unavailable, blockerText)
  }
  const templateBlocker = summaryStatBlockerTextFromTemplate(fallbackTemplate)
  if (templateBlocker) return summaryStatPanelFromSnapshot(null, SUMMARY_STAT_PENDING_TEXT.unavailable, templateBlocker)
  if (currentPanel && currentPanel.noteText) return currentPanel
  return summaryStatPanelFromSnapshot(null)
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
  const selectedScenarioKey = scenarioOptionForKey(previous.selectedScenarioKey)
    ? previous.selectedScenarioKey
    : 'single'
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
    selectedScenarioKey,
    selectedScenarioTitle: scenarioTitleForKey(selectedScenarioKey),
    combatPreparationRows: combatPreparationRowsForSelection({
      selectedClassKey,
      selectedClassName: currentClass ? currentClass.name : '',
      selectedTalentTemplate,
      selectedGearTemplate
    }),
    summaryStatPanel: summaryStatPanelForSelection({
      selectedClassKey,
      selectedRaceKey: raceState.selectedRaceKey,
      selectedScenarioKey,
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
    summaryStatSnapshot: null,
    summaryStatSnapshotSignature: '',
    scenarioOptions: SCENARIO_OPTIONS,
    combatPreparationRows: combatPreparationRowsForSelection({}),
    temporaryBuffOptions: defaultTemporaryBuffOptions(),
    selectedScenarioKey: 'single',
    selectedScenarioTitle: scenarioTitleForKey('single'),
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
    validatedCanSubmitTask: false,
    taskSubmitted: false,
    submittedTaskId: '',
    activeTaskCount: 0,
    activeTaskLimit: ACTIVE_SIMC_TASK_LIMIT,
    activeTaskLimitReached: false,
    activeTaskLimitMessage: '',
    activeTaskLimitLoading: false,
    confirmedPayload: null,
    latestAnalysis: null,
    resultSummary: '',
    blockedReasons: [],
    requestError: '',
    fromFallback: true,
    summaryStatsLoading: false,
    summaryStatsRequestSignature: '',
    selectorSheet: emptySelectorSheet()
  },

  onLoad(options) {
    this.analyticsStartedAt = Date.now()
    this.hasShownOnce = false
    this.templateLoadRequestId = 0
    this.selectionRevision = 0
    trackPageView(SIMC_PAGE_ROUTE, {
      source: options && options.from ? options.from : 'simulator'
    })
    this.loadTemplateLists()
    this.refreshActiveTaskGate()
  },

  onShow() {
    if (!this.analyticsStartedAt) return
    if (!this.hasShownOnce) {
      this.hasShownOnce = true
      return
    }
    this.loadTemplateLists()
    this.refreshActiveTaskGate()
  },

  onUnload() {
    trackPageLeave(SIMC_PAGE_ROUTE, this.analyticsStartedAt, {
      taskSubmitted: this.data.taskSubmitted,
      taskId: this.data.submittedTaskId || ''
    })
  },

  refreshActiveTaskGate() {
    if (typeof requestSimulatorTasks !== 'function') return Promise.resolve(false)
    this.setData({ activeTaskLimitLoading: true })
    return requestSimulatorTasks().then(({ payload }) => {
      const tasks = payload && Array.isArray(payload.tasks) ? payload.tasks : []
      const activeCount = activeSimcTemplateTaskCount(tasks)
      const limit = Number(this.data.activeTaskLimit) || ACTIVE_SIMC_TASK_LIMIT
      const limitReached = activeCount >= limit
      this.setData({
        activeTaskCount: activeCount,
        activeTaskLimitReached: limitReached,
        activeTaskLimitMessage: limitReached ? activeTaskLimitMessage(activeCount, limit) : '',
        canSubmitTask: !!this.data.validatedCanSubmitTask && !limitReached
      })
      return limitReached
    }).catch(() => false).finally(() => {
      this.setData({ activeTaskLimitLoading: false })
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
          summaryStatPanel: summaryStatPanelFromSnapshot(snapshot),
          summaryStatSnapshot: snapshot,
          summaryStatSnapshotSignature: signature
        })
        persistStatSnapshotTemplate(nextGearTemplate)
      } else {
        this.setData({
          summaryStatPanel: summaryStatPanelFromBlockedPayload(payload),
          summaryStatSnapshot: null,
          summaryStatSnapshotSignature: ''
        })
      }
      return payload
    }).catch(() => {
      if (this.data.summaryStatsRequestSignature === signature) {
        this.setData({
          summaryStatPanel: summaryStatPanelFromBlockedPayload({ blockers: ['backend unavailable'] }),
          summaryStatSnapshot: null,
          summaryStatSnapshotSignature: ''
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
    const requestId = (this.templateLoadRequestId || 0) + 1
    this.templateLoadRequestId = requestId
    const loadSelectionRevision = this.selectionRevision || 0
    const isCurrentLoad = () => requestId === this.templateLoadRequestId
    const isCurrentSelection = () => loadSelectionRevision === (this.selectionRevision || 0)
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
        if (!isCurrentLoad() || !isCurrentSelection()) return null
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
        return null
      })
      .catch((error) => {
        if (!isCurrentLoad() || !isCurrentSelection()) return null
        this.setData({
          fromFallback: true,
          requestError: cleanSummaryText(error && error.message) || 'template loading failed'
        })
        return null
      })
      .finally(() => {
        if (isCurrentLoad()) this.setData({ loadingTemplates: false })
      })
  },

  findTemplate(type, id) {
    const templates = type === 'talent' ? this.data.talentTemplates : this.data.gearTemplates
    return templates.find((item) => item.id === id) || null
  },

  markSelectionChanged() {
    this.selectionRevision = (this.selectionRevision || 0) + 1
  },

  refreshSelectionState() {
    this.markSelectionChanged()
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
      validatedCanSubmitTask: false,
      taskSubmitted: false,
      confirmedPayload: null,
      blockedReasons: [],
      latestAnalysis: null,
      ...summaryStatsInvalidationState()
    })
    this.refreshSummaryStatsForSelection()
  },

  openSelectorSheet(event) {
    const type = String(((event.currentTarget || {}).dataset || {}).selector || '').trim()
    const sheet = selectorSheetFor(type, this.data)
    if (!sheet.type || !sheet.options.length) return
    this.setData({ selectorSheet: sheet })
  },

  closeSelectorSheet() {
    this.setData({ selectorSheet: emptySelectorSheet() })
  },

  selectSelectorOption(event) {
    const index = Number(((event.currentTarget || {}).dataset || {}).index)
    const type = this.data.selectorSheet && this.data.selectorSheet.type
    const options = (this.data.selectorSheet && this.data.selectorSheet.options) || []
    if (!Number.isInteger(index) || index < 0 || index >= options.length) return
    this.setData({ selectorSheet: emptySelectorSheet() })
    const pickerEvent = { detail: { value: index } }
    if (type === 'class') return this.selectClass(pickerEvent)
    if (type === 'race') return this.selectRace(pickerEvent)
    if (type === 'talent') return this.selectTalentTemplate(pickerEvent)
    if (type === 'gear') return this.selectGearTemplate(pickerEvent)
    return null
  },

  selectClass(event) {
    const index = Number((event.detail || {}).value)
    if (!Number.isInteger(index) || index < 0 || index >= this.data.classOptions.length) return
    const selectedClass = this.data.classOptions[index] || null
    const classKey = selectedClass ? selectedClass.key : ''
    if (!classKey) return
    this.markSelectionChanged()
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
      validatedCanSubmitTask: false,
      taskSubmitted: false,
      confirmedPayload: null,
      blockedReasons: [],
      latestAnalysis: null,
      ...summaryStatsInvalidationState()
    })
    this.refreshSummaryStatsForSelection()
  },

  selectRace(event) {
    const index = Number((event.detail || {}).value)
    if (!Number.isInteger(index) || index < 0 || index >= this.data.raceOptions.length) return
    const selectedRace = this.data.raceOptions[index] || null
    if (!selectedRace || !selectedRace.key) return
    this.markSelectionChanged()
    this.setData({
      selectedRaceIndex: index,
      selectedRaceKey: selectedRace.key,
      selectedRaceName: selectedRace.name || selectedRace.key,
      canSubmitTask: false,
      validatedCanSubmitTask: false,
      taskSubmitted: false,
      confirmedPayload: null,
      blockedReasons: [],
      latestAnalysis: null,
      ...summaryStatsInvalidationState()
    })
    this.refreshSummaryStatsForSelection()
  },

  selectTalentTemplate(event) {
    if (!this.data.selectedClassKey) return
    const index = Number((event.detail || {}).value)
    if (!Number.isInteger(index) || index < 0 || index >= this.data.talentTemplates.length) return
    const template = this.data.talentTemplates[index] || null
    if (template && templateClassKey(template) !== this.data.selectedClassKey) return
    this.markSelectionChanged()
    this.setData({
      selectedTalentTemplateIndex: index,
      selectedTalentTemplate: template,
      combatPreparationRows: combatPreparationRowsForSelection({ ...this.data, selectedTalentTemplate: template }),
      summaryStatPanel: summaryStatPanelForSelection({ ...this.data, selectedTalentTemplate: template }),
      canConfirm: !!(this.data.selectedClassKey && template && this.data.selectedGearTemplate),
      canSubmitTask: false,
      validatedCanSubmitTask: false,
      taskSubmitted: false,
      confirmedPayload: null,
      blockedReasons: [],
      latestAnalysis: null,
      ...summaryStatsInvalidationState()
    })
    this.refreshSummaryStatsForSelection()
  },

  selectGearTemplate(event) {
    if (!this.data.selectedClassKey) return
    const index = Number((event.detail || {}).value)
    if (!Number.isInteger(index) || index < 0 || index >= this.data.gearTemplates.length) return
    const template = this.data.gearTemplates[index] || null
    if (template && templateClassKey(template) !== this.data.selectedClassKey) return
    this.markSelectionChanged()
    this.setData({
      selectedGearTemplateIndex: index,
      selectedGearTemplate: template,
      combatPreparationRows: combatPreparationRowsForSelection({ ...this.data, selectedGearTemplate: template }),
      summaryStatPanel: summaryStatPanelForSelection({ ...this.data, selectedGearTemplate: template }),
      canConfirm: !!(this.data.selectedClassKey && this.data.selectedTalentTemplate && template),
      canSubmitTask: false,
      validatedCanSubmitTask: false,
      taskSubmitted: false,
      confirmedPayload: null,
      blockedReasons: [],
      latestAnalysis: null,
      ...summaryStatsInvalidationState()
    })
    this.refreshSummaryStatsForSelection()
  },

  selectScenario(event) {
    const key = event.currentTarget.dataset.key || 'single'
    const option = scenarioOptionForKey(key)
    if (!option) return
    this.markSelectionChanged()
    this.setData({
      selectedScenarioKey: key,
      selectedScenarioTitle: option.title,
      canSubmitTask: false,
      validatedCanSubmitTask: false,
      taskSubmitted: false,
      confirmedPayload: null,
      blockedReasons: [],
      latestAnalysis: null,
      ...summaryStatsInvalidationState()
    })
    this.refreshSummaryStatsForSelection()
  },

  toggleTemporaryBuff(event) {
    const key = String((((event || {}).currentTarget || {}).dataset || {}).key || '').trim()
    if (!key) return
    const temporaryBuffOptions = (this.data.temporaryBuffOptions || []).map((item) => (
      item.key === key ? { ...item, enabled: !item.enabled } : item
    ))
    this.markSelectionChanged()
    this.setData({
      temporaryBuffOptions,
      canSubmitTask: false,
      validatedCanSubmitTask: false,
      taskSubmitted: false,
      confirmedPayload: null,
      blockedReasons: [],
      latestAnalysis: null
    })
  },

  buildTemplatePayload(confirmOnly = true, saveTask = false) {
    if (!this.data.selectedClassKey || !this.data.selectedTalentTemplate || !this.data.selectedGearTemplate) return null
    const statSnapshot = statSnapshotForSelection(this.data)
    const templateValidation = templateValidationForSelection(this.data)
    return {
      mode: 'simcraft_template',
      confirmOnly,
      saveTask,
      classKey: this.data.selectedClassKey,
      raceKey: this.data.selectedRaceKey,
      raceName: this.data.selectedRaceName,
      scenarioKey: this.data.selectedScenarioKey,
      analysisType: this.data.selectedAnalysisType,
      temporaryBuffs: selectedTemporaryBuffs(this.data.temporaryBuffOptions),
      templateValidation,
      templateContext: {
        talent: compactTemplate(this.data.selectedTalentTemplate),
        gear: compactTemplate(this.data.selectedGearTemplate, { statSnapshot })
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
    ]).map(localizedSimcUserText).filter(Boolean)
  },

  resultSummaryFromAnalysis(payload) {
    const simcReport = (payload && payload.simcReport) || {}
    const agent = (payload && payload.agent) || {}
    if (agent.status === 'template_ready' || simcReport.state === 'ready') {
      return '当前天赋、装备和场景已通过校验，可以提交任务开始运行 SimC。'
    }
    if (simcReport.summary) return localizedSimcUserText(simcReport.summary)
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
    const limitState = taskLimitStateFromPayload(payload, this.data.activeTaskLimit)
    const activeTaskLimitReached = limitState ? limitState.activeTaskLimitReached : this.data.activeTaskLimitReached
    this.setData({
      latestAnalysis: compactAnalysisState(payload),
      fromFallback: !!fromFallback,
      requestError: error || '',
      blockedReasons,
      resultSummary: this.resultSummaryFromAnalysis(payload),
      summaryStatPanel: summaryStatPanelFromAnalysis(payload, this.data.selectedGearTemplate, this.data.summaryStatPanel),
      validatedCanSubmitTask: ready,
      canSubmitTask: ready && !activeTaskLimitReached,
      taskSubmitted: this.data.taskSubmitted && ready
        && !activeTaskLimitReached,
      ...(limitState || {})
    })
  },

  confirmTemplateSimulation() {
    if (!this.data.canConfirm || this.data.confirming) return Promise.resolve(null)
    const requestPayload = this.buildTemplatePayload(true, false)
    if (!requestPayload) return Promise.resolve(null)
    const validationErrors = ((requestPayload.templateValidation || {}).errors || []).filter(Boolean)
    if (validationErrors.length) {
      this.setData({
        latestAnalysis: null,
        confirmedPayload: null,
        requestError: '',
        blockedReasons: validationErrors,
        resultSummary: '',
        canSubmitTask: false,
        validatedCanSubmitTask: false,
        taskSubmitted: false,
        confirming: false
      })
      return Promise.resolve(null)
    }
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
    }).catch((error) => {
      const message = requestFailureMessage(error, 'confirm failed')
      this.setData({
        latestAnalysis: null,
        fromFallback: true,
        requestError: message,
        blockedReasons: [message],
        resultSummary: '',
        canSubmitTask: false,
        validatedCanSubmitTask: false,
        taskSubmitted: false
      })
      return null
    }).finally(() => {
      this.setData({ confirming: false })
    })
  },

  submitConfirmedTask() {
    if (!this.data.canSubmitTask || this.data.submittingTask || this.data.taskSubmitted) return Promise.resolve(null)
    const basePayload = this.data.confirmedPayload || this.buildTemplatePayload(true, false)
    if (!basePayload) return Promise.resolve(null)
    const validationErrors = ((basePayload.templateValidation || {}).errors || []).filter(Boolean)
    if (validationErrors.length) {
      this.setData({
        latestAnalysis: null,
        requestError: '',
        blockedReasons: validationErrors,
        resultSummary: '',
        canSubmitTask: false,
        validatedCanSubmitTask: false,
        taskSubmitted: false,
        submittedTaskId: ''
      })
      return Promise.resolve(null)
    }
    const requestPayload = {
      ...basePayload,
      confirmOnly: false,
      saveTask: true
    }
    return this.refreshActiveTaskGate().then((limitReached) => {
      if (limitReached) {
        if (typeof wx !== 'undefined' && wx.showToast) {
          wx.showToast({ title: this.data.activeTaskLimitMessage || '已有任务运行中', icon: 'none' })
        }
        return null
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
          canSubmitTask: !saved && this.data.canSubmitTask,
          latestAnalysis: saved ? analysisWithoutStatusCard(this.data.latestAnalysis) : this.data.latestAnalysis,
          resultSummary: saved ? '' : this.data.resultSummary
        })
        if (typeof wx !== 'undefined' && wx.showToast) {
          wx.showToast({ title: saved ? '任务已提交' : '提交失败', icon: 'none' })
        }
        return payload
      })
      .catch((error) => {
        const message = requestFailureMessage(error, 'submit failed')
        this.setData({
          latestAnalysis: null,
          fromFallback: true,
          requestError: message,
          blockedReasons: [message],
          resultSummary: '',
          taskSubmitted: false,
          submittedTaskId: '',
          canSubmitTask: !!this.data.confirmedPayload && !!this.data.canSubmitTask && !this.data.activeTaskLimitReached
        })
        if (typeof wx !== 'undefined' && wx.showToast) {
          wx.showToast({ title: '提交失败', icon: 'none' })
        }
        return null
      })
      .finally(() => {
        this.setData({ submittingTask: false })
      })
    })
  }
})
