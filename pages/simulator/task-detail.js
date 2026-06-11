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
