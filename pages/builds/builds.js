const { fallbackBuildsHome, requestBuildsHome } = require('./builds-api')
const { requestSimulatorTasks } = require('../simulator/simulator-api')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')

Page({
  data: {
    ...fallbackBuildsHome(),
    tasks: [],
    scrollTarget: '',
    loading: false,
    fromFallback: true,
    requestError: ''
  },

  onLoad() {
    this.analyticsStartedAt = Date.now()
    this.analyticsVisible = true
    trackPageView('pages/builds/builds', { source: 'tab' })
    trackEvent('builds_home_view', { source: 'tab' }, { page: 'pages/builds/builds' })
    this.loadBuildsHome()
    this.loadSimulatorTasks()
  },

  onShow() {
    this.loadSimulatorTasks()
    if (this.analyticsVisible === false) {
      this.analyticsStartedAt = Date.now()
      this.analyticsVisible = true
      trackPageView('pages/builds/builds', { source: 'tab_resume' })
      trackEvent('builds_home_view', { source: 'tab_resume' }, { page: 'pages/builds/builds' })
    }
  },

  onHide() {
    if (this.analyticsVisible !== false) {
      trackPageLeave('pages/builds/builds', this.analyticsStartedAt)
      this.analyticsVisible = false
    }
  },

  onUnload() {
    if (this.analyticsVisible !== false) {
      trackPageLeave('pages/builds/builds', this.analyticsStartedAt)
      this.analyticsVisible = false
    }
  },

  openQueryPage(event) {
    const queryKey = event.currentTarget.dataset.key
    trackEvent('builds_query_open', { queryKey: queryKey || '' }, { page: 'pages/builds/builds' })
    if (queryKey === 'talents') {
      wx.navigateTo({
        url: '/pages/builds/talent-simulator'
      })
      return
    }
    if (queryKey === 'simc') {
      wx.navigateTo({
        url: '/pages/simulator/simc?from=builds'
      })
      return
    }
    if (queryKey === 'tasks') {
      this.setData({ scrollTarget: '' }, () => {
        this.setData({ scrollTarget: 'task-section' })
      })
      return
    }
    wx.navigateTo({
      url: `/pages/builds/detail?query=${encodeURIComponent(queryKey || '')}`
    })
  },

  openTaskDetail(event) {
    const taskId = event.currentTarget.dataset.taskId || ''
    if (!taskId) return
    trackEvent('task_detail_view', { taskId, source: 'builds_home' }, { page: 'pages/builds/builds' })
    wx.navigateTo({ url: `/pages/simulator/task-detail?id=${encodeURIComponent(taskId)}` })
  },

  loadBuildsHome() {
    this.setData({ loading: true })
    requestBuildsHome().then(({ payload, fromFallback, error }) => {
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
