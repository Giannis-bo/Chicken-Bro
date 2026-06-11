const { requestSimulatorTaskDetail } = require('./simulator-api')

Page({
  data: {
    navTitle: '任务详情',
    detail: null,
    loading: true,
    fromFallback: false,
    requestError: ''
  },

  onLoad(options) {
    this.loadTaskDetail(options.id || '')
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
    const simcDps = metrics.dps || ''
    const mythicPlusReference = analysis.mythicPlusReference || null
    const buildContext = analysisRequest.buildContext || request.buildContext || null
    const mythicPlusReferenceText = mythicPlusReference
      ? (mythicPlusReference.comparisonText || `${mythicPlusReference.avgDps || ''} / ${mythicPlusReference.maxDps || ''}`)
      : ''
    const briefConclusion = simcDps
      ? `SimC 已跑通，当前模板约 ${simcDps} DPS。`
      : (recommendations[0] || (simulation.error ? `SimC 未产出可用 DPS：${simulation.error}` : '任务已记录，等待可用结果。'))
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
      simcStatusText: simulation.ran ? '已跑通' : (simulation.error ? '未跑通' : '待执行'),
      createdAtText: task.createdAt || ''
    }
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
