const { requestSimulatorTaskDetail } = require('./simulator-api')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')

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
    const question = task.question || request.question || request.prompt || request.message || '未记录玩家问题'
    const modeText = this.modeText(task.mode || request.mode || analysisRequest.mode || '')
    const recommendations = (analysis.recommendations || task.recommendations || []).slice(0, 3)
    const mythicPlusReference = analysis.mythicPlusReference || null
    const buildContext = analysisRequest.buildContext || request.buildContext || null
    const isPreviewSimc = this.isPreviewSimc(task, request, analysisRequest, simulation)
    const simcDps = isPreviewSimc ? '' : (metrics.dps || '')
    const simcMetricLabel = simulation.metricLabel || (isPreviewSimc ? '正式 SimC DPS' : 'DPS')
    const simcUnitText = simulation.metricUnit || (isPreviewSimc ? '需要完整 /simc 导出' : '伤害/秒')
    const simcDisplayValue = simcDps || (isPreviewSimc ? '未执行正式模拟' : '未解析')
    const mythicPlusReferenceText = mythicPlusReference
      ? (mythicPlusReference.comparisonText || `${mythicPlusReference.avgDps || ''} / ${mythicPlusReference.maxDps || ''}`)
      : ''
    const briefConclusion = isPreviewSimc
      ? '已生成可执行 SimC 模板；未执行正式 SimC DPS 模拟。请提供完整 /simc 导出后再给出可用于对比的输出。'
      : (simcDps
          ? `SimC 已跑通，当前模板约 ${simcDps} DPS（${simcUnitText}）。`
          : (recommendations[0] || (simulation.error ? `SimC 未产出可用 DPS：${simulation.error}` : '任务已记录，等待可用结果。')))
    return {
      ...task,
      question,
      questionSummary: this.summarizeTaskQuestion(question),
      heroTitle: this.heroTitle(modeText, buildContext),
      modeText,
      statusText: task.status || analysis.status || 'ready',
      briefConclusion,
      recommendations,
      mythicPlusReference,
      mythicPlusReferenceText,
      buildContext,
      buildContextText: this.buildContextText(buildContext),
      stages: analysis.stages || [],
      simcDps,
      simcDisplayValue,
      simcMetricLabel,
      simcUnitText,
      simcStatusText: isPreviewSimc ? '需完整 /simc' : (simulation.ran ? '已跑通' : (simulation.error ? '未跑通' : '待执行')),
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
    if (mode === 'simcraft_agent') return 'SimC 任务'
    if (mode === 'simcraft') return 'SimC 分析'
    if (mode === 'wcl') return 'WCL 分析'
    return mode || '分析任务'
  },

  heroTitle(modeText, buildContext) {
    const context = buildContext || {}
    const specTitle = `${context.specName || ''}${context.className || ''}`.trim()
    return specTitle ? `${modeText} · ${specTitle}` : modeText
  },

  summarizeTaskQuestion(question) {
    const lines = String(question || '')
      .split(/\n+/)
      .map((line) => line.replace(/^第\d+轮玩家：/, '').trim())
      .filter(Boolean)
    const summaryLines = []
    lines.forEach((line) => {
      if (/^(天赋导入代码|前端天赋模拟器已选择节点|天赋模拟摘要|装备候选|装备获取进度|装备下一步|属性趋势|样本窗口)：/.test(line)) return
      if (/^[A-Za-z0-9+/=]{48,}$/.test(line)) return
      summaryLines.push(line)
    })
    const summary = summaryLines.slice(0, 2).join('\n') || lines.slice(0, 1).join('\n')
    return this.truncateText(summary || question, 120)
  },

  truncateText(text, maxLength) {
    const value = String(text || '').trim()
    if (value.length <= maxLength) return value
    return `${value.slice(0, maxLength - 1)}…`
  },

  buildContextText(context) {
    if (!context) return ''
    const details = context.details || {}
    const talents = details.talents || {}
    const gearRows = (details.gear && details.gear.gear) || []
    const gearNames = gearRows.slice(0, 3).map((item) => item.name).filter(Boolean).join('、')
    const title = `${context.specName || ''}${context.className || ''}`
    const source = context.sourceName || talents.sourceName || ''
    return [
      title ? `专精：${title}` : '',
      context.activeQueryTitle ? `入口：${context.activeQueryTitle}` : '',
      talents.importCode ? '已带入天赋导入代码' : '',
      gearNames ? `装备候选：${gearNames}` : '',
      source ? `来源：${source}` : ''
    ].filter(Boolean).join('；')
  }
})
