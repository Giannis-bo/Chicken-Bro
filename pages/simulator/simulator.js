const {
  fallbackSimulatorHome,
  requestSimulatorHome,
  requestSimulatorTasks
} = require('./simulator-api')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')

Page({
  data: {
    ...fallbackSimulatorHome(),
    tasks: [],
    scrollTarget: '',
    loading: false,
    fromFallback: true,
    requestError: ''
  },

  onLoad() {
    this.analyticsStartedAt = Date.now()
    this.analyticsVisible = true
    trackPageView('pages/simulator/simulator', { source: 'tab' })
    trackEvent('simulator_home_view', { source: 'tab' }, { page: 'pages/simulator/simulator' })
    this.loadSimulatorHome()
    this.loadSimulatorTasks()
  },

  onUnload() {
    if (this.analyticsVisible !== false) {
      trackPageLeave('pages/simulator/simulator', this.analyticsStartedAt)
      this.analyticsVisible = false
    }
  },

  onShow() {
    this.loadSimulatorTasks()
    if (this.analyticsVisible === false) {
      this.analyticsStartedAt = Date.now()
      this.analyticsVisible = true
      trackPageView('pages/simulator/simulator', { source: 'tab_resume' })
      trackEvent('simulator_home_view', { source: 'tab_resume' }, { page: 'pages/simulator/simulator' })
    }
  },

  onHide() {
    if (this.analyticsVisible !== false) {
      trackPageLeave('pages/simulator/simulator', this.analyticsStartedAt)
      this.analyticsVisible = false
    }
  },

  openAnalysisModule(event) {
    const mode = event.currentTarget.dataset.key || 'simcraft'
    trackEvent('simulator_module_open', { mode }, { page: 'pages/simulator/simulator' })
    if (mode === 'simc') {
      wx.navigateTo({ url: '/pages/simulator/simc' })
      return
    }
    if (mode === 'wcl') {
      wx.navigateTo({ url: '/pages/simulator/wcl' })
      return
    }
    if (mode === 'tasks') {
      this.setData({ scrollTarget: '' }, () => {
        this.setData({ scrollTarget: 'task-section' })
      })
    }
  },

  openTaskDetail(event) {
    const taskId = event.currentTarget.dataset.taskId || ''
    if (!taskId) return
    trackEvent('task_detail_view', { taskId, source: 'simulator_home' }, { page: 'pages/simulator/simulator' })
    wx.navigateTo({ url: `/pages/simulator/task-detail?id=${encodeURIComponent(taskId)}` })
  },

  loadSimulatorHome() {
    this.setData({ loading: true })
    requestSimulatorHome().then(({ payload, fromFallback, error }) => {
      this.setData({
        ...payload,
        fromFallback,
        requestError: error || ''
      })
    }).finally(() => {
      this.setData({ loading: false })
    })
  },

  loadSimulatorTasks() {
    requestSimulatorTasks().then(({ payload, fromFallback }) => {
      const tasks = payload && Array.isArray(payload.tasks) ? payload.tasks : []
      if (fromFallback || !tasks.length) {
        this.setData({ tasks: [] })
        return
      }
      this.setData({
        tasks: tasks.map((task) => ({
          taskId: task.taskId,
          title: task.question || `${task.mode} 分析`,
          status: task.status || 'ready',
          desc: (task.recommendations && task.recommendations[0]) || '已保存到当前微信用户的模拟器任务。'
        }))
      })
    })
  }
})
