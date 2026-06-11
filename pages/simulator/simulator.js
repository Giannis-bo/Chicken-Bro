const {
  fallbackSimulatorHome,
  requestSimulatorHome,
  requestSimulatorTasks
} = require('./simulator-api')

Page({
  data: {
    ...fallbackSimulatorHome(),
    loading: false,
    fromFallback: true,
    requestError: ''
  },

  onLoad() {
    this.loadSimulatorHome()
    this.loadSimulatorTasks()
  },

  openAnalysisModule(event) {
    const mode = event.currentTarget.dataset.key || 'simcraft'
    if (mode === 'simc') {
      wx.navigateTo({ url: '/pages/simulator/simc' })
      return
    }
    if (mode === 'wcl') {
      wx.navigateTo({ url: '/pages/simulator/wcl' })
      return
    }
    if (mode === 'tasks') {
      wx.pageScrollTo && wx.pageScrollTo({ selector: '.task-section', duration: 240 })
    }
  },

  openTaskDetail(event) {
    const taskId = event.currentTarget.dataset.taskId || ''
    if (!taskId) return
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
      if (fromFallback || !payload.tasks || !payload.tasks.length) return
      this.setData({
        tasks: payload.tasks.map((task) => ({
          taskId: task.taskId,
          title: task.question || `${task.mode} 分析`,
          status: task.status || 'ready',
          desc: (task.recommendations && task.recommendations[0]) || '已保存到当前微信用户的模拟器任务。'
        }))
      })
    })
  }
})
