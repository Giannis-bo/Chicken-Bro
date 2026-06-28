const { requestSimulatorTasks } = require('./simulator-api')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')

function cleanTaskText(value) {
  return String(value === undefined || value === null ? '' : value).trim()
}

const STATUS_VIEW = {
  completed: { text: '已完成', className: 'status-completed' },
  failed: { text: '失败', className: 'status-failed' },
  running: { text: '进行中', className: 'status-running' },
  queued: { text: '进行中', className: 'status-running' },
  blocked: { text: '已阻断', className: 'status-blocked' },
  ready: { text: '待提交', className: 'status-pending' }
}

function formatTaskTime(value) {
  const text = cleanTaskText(value)
  const zonedDate = parseZonedTaskTime(text)
  if (zonedDate) return formatLocalDateMinute(zonedDate)
  const match = text.match(/^(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})/)
  if (match) return `${match[1]}-${match[2]}-${match[3]} ${match[4]}:${match[5]}`
  return text
}

function padTimePart(value) {
  return String(value).padStart(2, '0')
}

function formatLocalDateMinute(date) {
  return [
    date.getFullYear(),
    padTimePart(date.getMonth() + 1),
    padTimePart(date.getDate())
  ].join('-') + ` ${padTimePart(date.getHours())}:${padTimePart(date.getMinutes())}`
}

function parseZonedTaskTime(text) {
  const normalized = text.replace(' ', 'T')
  const zoned = normalized.match(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})$/)
  if (!zoned) return null
  const normalizedOffset = normalized.replace(/([+-]\d{2})(\d{2})$/, '$1:$2')
  const date = new Date(normalizedOffset)
  return isNaN(date.getTime()) ? null : date
}

function taskStatus(task) {
  const report = task && task.simcReportSummary ? task.simcReportSummary : {}
  return cleanTaskText(report.state) ||
    cleanTaskText(report.statusText) ||
    cleanTaskText(task && task.status) ||
    'ready'
}

function taskStatusView(status) {
  const key = cleanTaskText(status).toLowerCase()
  if (STATUS_VIEW[key]) return STATUS_VIEW[key]
  return { text: key || '待处理', className: 'status-pending' }
}

function taskBuild(task) {
  const report = task && task.simcReportSummary ? task.simcReportSummary : {}
  return (report.build && typeof report.build === 'object')
    ? report.build
    : ((task && task.build && typeof task.build === 'object') ? task.build : {})
}

function taskTiming(task) {
  const report = task && task.simcReportSummary ? task.simcReportSummary : {}
  return (report.timing && typeof report.timing === 'object') ? report.timing : {}
}

function terminalTaskTime(task, status) {
  const timing = taskTiming(task)
  const report = task && task.simcReportSummary ? task.simcReportSummary : {}
  const terminalTime = cleanTaskText(timing.finishedAt)
  if (terminalTime) return terminalTime
  const statusKey = cleanTaskText(status).toLowerCase()
  if (statusKey === 'completed' || statusKey === 'failed') {
    return cleanTaskText(report.updatedAt || (task && (task.updatedAt || task.createdAt)))
  }
  return ''
}

function taskDisplayTime(task, status) {
  const timing = taskTiming(task)
  const report = task && task.simcReportSummary ? task.simcReportSummary : {}
  return terminalTaskTime(task, status) ||
    cleanTaskText(timing.startedAt || timing.queuedAt || report.updatedAt || (task && (task.updatedAt || task.createdAt)))
}

function taskScenarioText(scenario) {
  const source = scenario && typeof scenario === 'object' ? scenario : {}
  const key = cleanTaskText(source.key)
  const targets = Number(source.targets || 0)
  if (key === 'mythic_plus') return '近似大秘境'
  if (key === 'aoe_5' || targets > 1) return `AOE${targets || 5}目标`
  if (key === 'single' || targets === 1) return '单体'
  return cleanTaskText(source.label) || key
}

function pushTaskTag(tags, key, value) {
  const text = cleanTaskText(value)
  if (!text) return
  tags.push({ key, text })
}

function localizedFailedTaskSummary(summary) {
  const text = cleanTaskText(summary)
  const timeout = text.match(/timed out after\s+(\d+)\s+seconds?/i)
  if (timeout) {
    return `SimC 执行超时：当前组合已经入队并开始运行，但本次模拟超过 ${timeout[1]} 秒未完成。可以稍后重试，或等待前面的任务完成后再提交。`
  }
  if (/Invalid 'class_talents'/i.test(text)) {
    return 'SimC 执行失败：当前天赋字符串不被 SimC 识别。请重新保存天赋模板，或更换模板后再试。'
  }
  if (/no parseable dps|no parseable DPS/i.test(text)) {
    return 'SimC 执行失败：本次运行没有解析到可用 DPS 结果。请稍后重试，或检查当前模板。'
  }
  return 'SimC 执行失败：当前组合已提交，但后端模拟没有产出可用结果。请稍后重试，或检查天赋、装备和场景。'
}

function taskTags(task) {
  const report = task && task.simcReportSummary ? task.simcReportSummary : {}
  const build = taskBuild(task)
  const tags = []
  pushTaskTag(tags, 'race', build.raceName || build.raceKey)
  pushTaskTag(tags, 'class', build.className || build.classKey)
  pushTaskTag(tags, 'spec', build.specName || build.specKey)
  pushTaskTag(tags, 'hero', build.heroLabel || build.heroName || build.heroKey)
  pushTaskTag(tags, 'scenario', taskScenarioText(report.scenario || task && task.scenario))
  return tags
}

function taskSummary(task, status) {
  const report = task && task.simcReportSummary ? task.simcReportSummary : {}
  const statusKey = cleanTaskText(status).toLowerCase()
  if (statusKey === 'completed') return ''
  if (statusKey === 'queued') return '任务已进入队列，等待后台执行。'
  if (statusKey === 'running') return '任务正在后台执行。'
  if (statusKey === 'failed') {
    return localizedFailedTaskSummary(
      cleanTaskText(report.summary) ||
      cleanTaskText(task && task.summary) ||
      cleanTaskText(task && task.briefConclusion)
    )
  }
  return cleanTaskText(report.summary) ||
    cleanTaskText(task && task.summary) ||
    cleanTaskText(task && task.briefConclusion) ||
    cleanTaskText((task && task.recommendations && task.recommendations[0]) || '') ||
    ''
}

function taskTitle(task, status) {
  const report = task && task.simcReportSummary ? task.simcReportSummary : {}
  const build = taskBuild(task)
  const subject = `${cleanTaskText(build.specName || build.specKey)}${cleanTaskText(build.className || build.classKey)}`.trim() ||
    cleanTaskText(report.title).replace(/\s*SimC\s*$/i, '') ||
    cleanTaskText(task && task.question) ||
    `${cleanTaskText(task && task.mode) || 'SimC'}任务`
  const displayTime = formatTaskTime(taskDisplayTime(task, status)) || '时间待补'
  return `${subject}_${displayTime}`
}

function normalizeTask(task) {
  const report = task && task.simcReportSummary ? task.simcReportSummary : {}
  const status = taskStatus(task)
  const statusView = taskStatusView(status)
  const finishedAt = terminalTaskTime(task, status)
  return {
    taskId: cleanTaskText((task && (task.taskId || task.id)) || ''),
    title: taskTitle(task, status),
    status,
    statusText: statusView.text,
    statusClass: statusView.className,
    desc: taskSummary(task, status),
    tags: taskTags(task),
    completionTimeText: `完成时间：${formatTaskTime(finishedAt) || '未完成'}`,
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
          tasks: fromFallback ? [] : tasks.map((task) => this.normalizeTask(task)).filter((task) => task.taskId),
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
  },

  normalizeTask
})
