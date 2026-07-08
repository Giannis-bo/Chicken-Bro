const { requestSimulatorTaskDetail } = require('./simulator-api')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')

const DETAIL_SECONDARY_STATS = [
  { key: 'crit', label: '暴击' },
  { key: 'haste', label: '急速' },
  { key: 'mastery', label: '精通' },
  { key: 'versatility', label: '全能' }
]

const DETAIL_PREPARATION_CATEGORY_LABELS = {
  self_class_raid_buff: '团队增益',
  spec_combat_preparation: '职业准备',
  temporary_combat_buffs: '临时增益'
}

const DETAIL_PREPARATION_STATE_LABELS = {
  enabled: '已开启',
  disabled: '未开启',
  pending_evidence: '待验证',
  not_applicable: '无增益'
}

const DETAIL_PREPARATION_VALUE_LABELS = {
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

const DETAIL_PREPARATION_VALUE_ALIASES = {
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

const DETAIL_SIMC_SLOT_LABELS = {
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

function cleanDetailText(value) {
  return String(value === undefined || value === null ? '' : value).trim()
}

const DETAIL_SIMC_CRASH_TEXT = 'SimC 执行失败：当前组合运行时崩溃，后端未能产出可用结果。请稍后重试，或检查天赋、装备和场景。'

function isRawDetailSimcCrashDiagnostic(text) {
  return /sim_signal_handler|segmentation fault|\bsigsegv\b|\bsignal\s*11\b/i.test(cleanDetailText(text))
}

function detailSimcSlotLabel(value) {
  const key = cleanDetailText(value).replace(/\.$/, '')
  return DETAIL_SIMC_SLOT_LABELS[key] || key
}

function localizedDetailSimcSlotList(value) {
  return cleanDetailText(value)
    .replace(/\.$/, '')
    .split(',')
    .map((item) => detailSimcSlotLabel(item.trim()))
    .filter(Boolean)
    .join('、')
}

function localizedDetailMissingGearSlotsText(value) {
  const text = cleanDetailText(value)
  const match = text.match(/^(?:Missing core SimC gear slots|missing gear slots):\s*(.+?)\.?$/i)
  if (!match) return ''
  const slots = localizedDetailSimcSlotList(match[1])
  return slots ? `缺少可执行装备槽位：${slots}` : '缺少可执行装备槽位'
}

function localizedDetailItemNameDiagnosticText(value) {
  const text = cleanDetailText(value)
  const match = text.match(/^Trivial:\s*Player\b.*?\bat slot\s+([a-z0-9_]+)\b.*?has inconsistency between name\b/i)
  if (!match) return ''
  const slot = detailSimcSlotLabel(match[1])
  return `${slot}装备数据不一致：装备名称和物品 ID 对不上，请重新选择或保存${slot}。`
}

function detailPreparationValueLabel(value) {
  const text = cleanDetailText(value)
  const normalized = text.replace(/\.$/, '').replace(/^and\s+/i, '').trim().toLowerCase()
  return DETAIL_PREPARATION_VALUE_LABELS[text] || DETAIL_PREPARATION_VALUE_ALIASES[normalized] || text
}

function detailTemporaryBuffText(summary, state) {
  if (state === 'disabled') return '未选择'
  const text = cleanDetailText(summary)
  if (!text) return state === 'enabled' ? '已选择' : ''
  return text
    .split(',')
    .map((item) => detailPreparationValueLabel(item))
    .filter(Boolean)
    .join('、') || text
}

function detailCombatBuffValue(item) {
  const category = cleanDetailText(item && item.category)
  const state = cleanDetailText(item && item.state)
  if (category === 'temporary_combat_buffs') {
    return detailTemporaryBuffText(item && item.summary, state)
  }
  if (category === 'self_class_raid_buff' && state === 'not_applicable') return '无增益'
  return detailPreparationValueLabel(item && item.label) || cleanDetailText(item && item.summary)
}

function detailCombatBuffStateText(item, category) {
  const state = cleanDetailText(item && item.state)
  if (category === 'temporary_combat_buffs' && state === 'enabled') return '已选择'
  if (category === 'temporary_combat_buffs' && state === 'disabled') return '未选择'
  return DETAIL_PREPARATION_STATE_LABELS[state] || state || cleanDetailText(item && item.evidenceState)
}

function detailCombatBuffRows(preparation) {
  const source = preparation && typeof preparation === 'object' ? preparation : {}
  const items = Array.isArray(source.items) ? source.items : []
  return items
    .map((item) => {
      const category = cleanDetailText(item && item.category)
      const categoryLabel = DETAIL_PREPARATION_CATEGORY_LABELS[category]
      if (!categoryLabel) return null
      const valueText = detailCombatBuffValue(item)
      if (!valueText) return null
      return {
        key: cleanDetailText(item && item.key) || category,
        label: categoryLabel,
        valueText,
        stateText: detailCombatBuffStateText(item, category)
      }
    })
    .filter(Boolean)
}

function localizedFailedDetailSummary(summary) {
  const text = cleanDetailText(summary)
  const missingGearSlots = localizedDetailMissingGearSlotsText(text)
  if (missingGearSlots) return `SimC 执行失败：${missingGearSlots}。请检查装备模板后再试。`
  const itemNameDiagnostic = localizedDetailItemNameDiagnosticText(text)
  if (itemNameDiagnostic) return `SimC 执行失败：${itemNameDiagnostic}`
  if (isRawDetailSimcCrashDiagnostic(text)) return DETAIL_SIMC_CRASH_TEXT
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
  return 'SimC 执行失败：当前组合已提交，但后端模拟没有产出可用结果。请稍后重试，或检查天赋、装备和场景。'
}

function localizedDetailSimcText(summary) {
  const text = cleanDetailText(summary)
  if (!text) return ''
  const missingGearSlots = localizedDetailMissingGearSlotsText(text)
  if (missingGearSlots) return missingGearSlots
  const itemNameDiagnostic = localizedDetailItemNameDiagnosticText(text)
  if (itemNameDiagnostic) return itemNameDiagnostic
  if (isRawDetailSimcCrashDiagnostic(text)) return DETAIL_SIMC_CRASH_TEXT
  const timeout = text.match(/timed out after\s+(\d+)\s+seconds?/i)
  if (timeout || /Invalid 'class_talents'|no parseable dps/i.test(text)) {
    return localizedFailedDetailSummary(text)
  }
  if (/traceback|^command\b|\bitem_\d+\b|\bwebsim_[a-z0-9_]+\b|\bsimulationcraft\b|seed=|targethealth=/i.test(text)) {
    return 'SimC 执行失败：后端未能完成当前组合模拟。请稍后重试，或检查天赋、装备和场景。'
  }
  if (/simc/i.test(text) && /(failed|error|invalid|unable|missing|could not|timeout|timed out|parseable)/i.test(text)) {
    return 'SimC 执行失败：后端未能完成当前组合模拟。请稍后重试，或检查天赋、装备和场景。'
  }
  return text
}

function detailBriefConclusion(summary, isFailed) {
  const text = cleanDetailText(summary)
  if (isFailed) return localizedFailedDetailSummary(text)
  return localizedDetailSimcText(text)
}

function verifiedDetailStatSnapshot(snapshot) {
  return snapshot && typeof snapshot === 'object' && snapshot.statStatus === 'verified' ? snapshot : null
}

function detailMetricValue(row) {
  const value = cleanDetailText(row && row.value)
  if (value) return value
  const raw = row && row.rawValue
  if (raw !== undefined && raw !== null && raw !== '') return cleanDetailText(raw)
  return ''
}

function detailMetricPercent(row) {
  const converted = cleanDetailText(row && row.convertedValue)
  if (converted) return converted
  const raw = Number(row && row.convertedRawValue)
  if (Number.isFinite(raw)) {
    const rounded = Math.round(raw * 10) / 10
    return `${Number.isInteger(rounded) ? rounded : rounded.toFixed(1)}%`
  }
  return detailMetricValue(row)
}

function detailStatRows(snapshot) {
  const source = verifiedDetailStatSnapshot(snapshot)
  if (!source) return []
  const rows = []
  const primary = source.primary && typeof source.primary === 'object' ? source.primary : null
  const primaryValue = detailMetricValue(primary)
  if (primaryValue) {
    rows.push({
      key: cleanDetailText(primary && primary.key) || 'primary',
      label: cleanDetailText(primary && primary.label) || '主属性',
      valueText: primaryValue
    })
  }
  const secondary = Array.isArray(source.secondary) ? source.secondary : []
  DETAIL_SECONDARY_STATS.forEach((definition) => {
    const row = secondary.find((item) => item && item.key === definition.key) || null
    const valueText = detailMetricPercent(row)
    if (valueText) {
      rows.push({
        key: definition.key,
        label: cleanDetailText(row && row.label) || definition.label,
        valueText
      })
    }
  })
  return rows
}

function firstVerifiedDetailStatSnapshot(...values) {
  for (const value of values) {
    const snapshot = verifiedDetailStatSnapshot(value)
    if (snapshot) return snapshot
  }
  return null
}

function durationText(seconds) {
  const value = Number(seconds || 0)
  if (!Number.isFinite(value) || value <= 0) return ''
  const minutes = Math.round(value / 60)
  return minutes > 0 ? `${minutes}分钟` : `${value}秒`
}

function scenarioDisplayText(scenario) {
  const source = scenario && typeof scenario === 'object' ? scenario : {}
  const key = cleanDetailText(source.key)
  const label = cleanDetailText(source.label)
  const targets = Number(source.targets || 0)
  if (key === 'mythic_plus') return '近似大秘境'
  if (key === 'aoe_5' || targets > 1) return `AOE ${targets || 5}目标`
  if (key === 'single' || targets === 1) return `单体 ${targets || 1}目标`
  return label || key
}

function scenarioMetaText(scenario) {
  const source = scenario && typeof scenario === 'object' ? scenario : {}
  return [
    cleanDetailText(source.fightStyle),
    durationText(source.durationSeconds)
  ].filter(Boolean).join(' · ')
}

Page({
  data: {
    navTitle: '任务详情',
    detail: null,
    loading: true,
    fromFallback: false,
    requestError: ''
  },

  onLoad(options) {
    const taskId = options.id || ''
    this.analyticsStartedAt = Date.now()
    this.analyticsTaskId = taskId
    trackPageView('pages/simulator/task-detail', { taskId })
    trackEvent('task_detail_view', { taskId, source: 'detail_page' }, { page: 'pages/simulator/task-detail' })
    this.loadTaskDetail(options.id || '')
  },

  onUnload() {
    trackPageLeave('pages/simulator/task-detail', this.analyticsStartedAt, { taskId: this.analyticsTaskId || '' })
  },

  loadTaskDetail(taskId) {
    if (!taskId) {
      this.setData({ loading: false, requestError: '请从任务列表进入任务详情；当前直开路径没有携带任务 ID。' })
      return
    }
    requestSimulatorTaskDetail(taskId)
      .then(({ payload, fromFallback, error }) => {
        this.setData({
          detail: this.normalizeTaskDetail(payload.task),
          fromFallback,
          requestError: error || ''
        })
      })
      .catch((error) => {
        this.setData({
          detail: null,
          fromFallback: true,
          requestError: error && error.message ? error.message : 'request failed'
        })
      })
      .finally(() => {
        this.setData({ loading: false })
      })
  },

  normalizeTaskDetail(task) {
    if (!task) return null
    const analysis = task.analysis || {}
    const request = task.request || {}
    const analysisRequest = analysis.request || {}
    const agent = analysis.agent || {}
    const simulation = analysis.simulation || {}
    const metrics = simulation.metrics || {}
    const simcReport = analysis.simcReport || {}
    const simcReportResult = simcReport.result || {}
    const simcReportBuild = simcReport.build || {}
    const simcReportScenario = simcReport.scenario || {}
    const simcReportPreparation = simcReport.preparation || {}
    const mode = task.mode || request.mode || analysisRequest.mode || analysis.mode || ''
    const modeText = this.modeText(mode)
    const isSimcraftTemplateMode = mode === 'simcraft_template' || analysis.mode === 'simcraft_template'
    const recommendations = isSimcraftTemplateMode
      ? []
      : (analysis.recommendations || task.recommendations || []).slice(0, 3)
    const buildContext = analysisRequest.buildContext || request.buildContext || null
    const isPreviewSimc = this.isPreviewSimc(task, request, analysisRequest, simulation)
    const simcDps = isPreviewSimc ? '' : (simcReportResult.dps || metrics.dps || '')
    const simcMetricLabel = simcReportResult.metricLabel || simulation.metricLabel || (isPreviewSimc ? '正式 SimC DPS' : 'DPS')
    const simcUnitText = simcReportResult.metricUnit || simulation.metricUnit || (isPreviewSimc ? '需要完整 /simc 导出' : '伤害/秒')
    const simcDisplayValue = (isPreviewSimc ? '' : simcReportResult.dpsDisplay) || simcDps || (isPreviewSimc ? '未执行正式模拟' : '未解析')
    const statSnapshot = firstVerifiedDetailStatSnapshot(
      simcReportBuild.statSnapshot,
      request.statSnapshot,
      analysisRequest.statSnapshot,
      (((buildContext || {}).details || {}).gear || {}).statSnapshot,
      (((request.templateContext || {}).gear || {}).metadata || {}).statSnapshot,
      (((analysisRequest.templateContext || {}).gear || {}).metadata || {}).statSnapshot
    )
    const statRows = detailStatRows(statSnapshot)
    const scenarioSource = Object.keys(simcReportScenario).length
      ? simcReportScenario
      : { key: request.scenarioKey || analysisRequest.scenarioKey || '', targets: 0 }
    const scenarioDisplay = scenarioDisplayText(scenarioSource)
    const combatBuffRows = detailCombatBuffRows(simcReportPreparation)
    const reportState = cleanDetailText(simcReport.state || simcReport.statusText || task.status || analysis.status).toLowerCase()
    const failedSummary = simcReport.summary || simulation.error || ''
    const briefConclusion = detailBriefConclusion(failedSummary, reportState === 'failed') || (isPreviewSimc
      ? '已生成可执行 SimC 模板；未执行正式 SimC DPS 模拟。请提供完整 /simc 导出后再给出可用于对比的输出。'
      : (simcDps
          ? `SimC 已跑通，当前模板约 ${simcDps} DPS（${simcUnitText}）。`
          : (recommendations[0] || (simulation.error ? localizedDetailSimcText(simulation.error) : '任务已记录，等待可用结果。'))))
    return {
      taskId: task.taskId || task.id || '',
      id: task.id || task.taskId || '',
      mode,
      createdAt: task.createdAt || '',
      updatedAt: task.updatedAt || '',
      heroTitle: simcReport.title || this.heroTitle(modeText, buildContext),
      modeText,
      statusText: simcReport.statusText || task.status || analysis.status || 'ready',
      briefConclusion,
      simcDps,
      simcDisplayValue,
      simcMetricLabel,
      simcUnitText,
      simcStatusText: simcReport.statusText || (isPreviewSimc ? '需完整 /simc' : (simulation.ran ? '已跑通' : (simulation.error ? '未跑通' : '待执行'))),
      hasRunContext: !!(scenarioDisplay || statRows.length),
      scenarioDisplayText: scenarioDisplay,
      scenarioMetaText: scenarioMetaText(scenarioSource),
      hasCombatBuffRows: combatBuffRows.length > 0,
      combatBuffRows,
      statRows,
      createdAtText: task.createdAt || ''
    }
  },

  isPreviewSimc(task, request, analysisRequest, simulation) {
    if (simulation && simulation.quality === 'preview') return true
    return (analysisRequest && analysisRequest.profileSource === 'generated') ||
      (request && request.profileSource === 'generated') ||
      (task && task.profileSource === 'generated')
  },

  modeText(mode) {
    if (mode === 'simcraft_template') return 'SimC 模板'
    if (mode === 'simcraft_agent') return 'SimC 任务'
    if (mode === 'simcraft') return 'SimC 分析'
    if (mode === 'wcl') return 'WCL 分析'
    return mode || '分析任务'
  },

  heroTitle(modeText, buildContext) {
    const context = buildContext || {}
    const specTitle = `${context.specName || ''}${context.className || ''}`.trim()
    return specTitle ? `${modeText} · ${specTitle}` : modeText
  }
})
