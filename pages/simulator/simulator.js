const { loginWithWechat } = require('../common/auth-client')
const {
  fallbackSimulatorHome,
  requestSimulatorAnalysis,
  requestSimulatorHome,
  requestSimulatorTasks
} = require('./simulator-api')

Page({
  data: {
    ...fallbackSimulatorHome(),
    loading: false,
    fromFallback: true,
    requestError: '',
    latestAnalysis: null
  },

  onLoad() {
    this.loadSimulatorHome()
    this.loadSimulatorTasks()
  },

  openTool(event) {
    const mode = event.currentTarget.dataset.key || 'simcraft'
    this.setData({ loading: true })
    loginWithWechat().catch(() => null).then(() => {
      return requestSimulatorAnalysis({ mode })
    }).then(({ payload, fromFallback, error }) => {
      this.setData({
        latestAnalysis: payload,
        fromFallback,
        requestError: error || ''
      })
      wx.showToast({
        title: fromFallback ? '已生成本地建议' : '分析已提交',
        icon: 'none'
      })
      this.loadSimulatorTasks()
    }).finally(() => {
      this.setData({ loading: false })
    })
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
          title: task.question || `${task.mode} 分析`,
          status: task.status || 'ready',
          desc: (task.recommendations && task.recommendations[0]) || '已保存到当前微信用户的模拟器任务。'
        }))
      })
    })
  }
})
