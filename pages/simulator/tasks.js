const { requestSimulatorTasks } = require('./simulator-api')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')

function cleanTaskText(value) {
  return String(value === undefined || value === null ? '' : value).trim()
}

function taskSummary(task) {
  const report = task && task.simcReportSummary ? task.simcReportSummary : {}
  return cleanTaskText(report.summary) ||
    cleanTaskText(task && task.summary) ||
    cleanTaskText(task && task.briefConclusion) ||
    cleanTaskText((task && task.recommendations && task.recommendations[0]) || '') ||
    '任务已记录，等待可用结果。'
}

function taskTitle(task) {
  const report = task && task.simcReportSummary ? task.simcReportSummary : {}
  return cleanTaskText(report.title) ||
    cleanTaskText(task && task.question) ||
    `${cleanTaskText(task && task.mode) || 'SimC'} 任务`
}

function taskStatus(task) {
  const report = task && task.simcReportSummary ? task.simcReportSummary : {}
  return cleanTaskText(report.state) ||
    cleanTaskText(report.statusText) ||
    cleanTaskText(task && task.status) ||
    'ready'
}

function normalizeTask(task) {
  const report = task && task.simcReportSummary ? task.simcReportSummary : {}
  const scenario = report.scenario || {}
  return {
    taskId: cleanTaskText((task && (task.taskId || task.id)) || ''),
    title: taskTitle(task),
    status: taskStatus(task),
    desc: taskSummary(task),
    dpsDisplay: cleanTaskText(report.dpsDisplay),
    scenarioText: cleanTaskText(scenario.label) || cleanTaskText(scenario.key),
    updatedAt: cleanTaskText(report.updatedAt || (task && (task.updatedAt || task.createdAt)))
  }
}

Page({
  data: {
    navTitle: '任务列表',
    tasks: [],
    loading: true,
    fromFallback: false,
    requestError: ''
  },

  onLoad(options) {
    this.analyticsStartedAt = Date.now()
    this.analyticsSource = (options && options.from) || 'direct'
    trackPageView('pages/simulator/tasks', { source: this.analyticsSource })
    trackEvent('task_list_view', { source: this.analyticsSource }, { page: 'pages/simulator/tasks' })
    this.loadSimulatorTasks()
  },

  onShow() {
    if (this.loadedOnce) this.loadSimulatorTasks()
  },

  onUnload() {
    trackPageLeave('pages/simulator/tasks', this.analyticsStartedAt, { source: this.analyticsSource || '' })
  },

  loadSimulatorTasks() {
    this.setData({ loading: true })
    requestSimulatorTasks()
      .then(({ payload, fromFallback, error }) => {
        const tasks = payload && Array.isArray(payload.tasks) ? payload.tasks : []
        this.loadedOnce = true
        this.setData({
          tasks: fromFallback ? [] : tasks.map(normalizeTask).filter((task) => task.taskId),
          fromFallback,
          requestError: error || ''
        })
      })
      .catch((error) => {
        this.loadedOnce = true
        this.setData({
          tasks: [],
          fromFallback: true,
          requestError: error && error.message ? error.message : 'request failed'
        })
      })
      .finally(() => {
        this.setData({ loading: false })
      })
  },

  openTaskDetail(event) {
    const taskId = event.currentTarget.dataset.taskId || ''
    if (!taskId) return
    trackEvent('task_detail_view', { taskId, source: 'task_list' }, { page: 'pages/simulator/tasks' })
    wx.navigateTo({ url: `/pages/simulator/task-detail?id=${encodeURIComponent(taskId)}` })
  }
})
