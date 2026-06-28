const { requestSimulatorTaskDetail } = require('./simulator-api')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')

const DETAIL_SECONDARY_STATS = [
  { key: 'crit', label: '暴击' },
  { key: 'haste', label: '急速' },
  { key: 'mastery', label: '精通' },
  { key: 'versatility', label: '全能' }
]

function cleanDetailText(value) {
  return String(value === undefined || value === null ? '' : value).trim()
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
      this.setData({ loading: false, requestError: 'missing task id' })
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
    const briefConclusion = simcReport.summary || (isPreviewSimc
      ? '已生成可执行 SimC 模板；未执行正式 SimC DPS 模拟。请提供完整 /simc 导出后再给出可用于对比的输出。'
      : (simcDps
          ? `SimC 已跑通，当前模板约 ${simcDps} DPS（${simcUnitText}）。`
          : (recommendations[0] || (simulation.error ? `SimC 未产出可用 DPS：${simulation.error}` : '任务已记录，等待可用结果。'))))
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
      preparationSummary: simcReportPreparation.summary || '',
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
