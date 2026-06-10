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
    simPrompt: '我是冰法，想跑单体 5 分钟并解释属性收益\n```simc\nmage="冰法样例"\ntalents=CAE\ngear_ilvl=700\n```',
    agentRound: 1,
    latestAnalysis: null
  },

  onLoad() {
    this.loadSimulatorHome()
    this.loadSimulatorTasks()
  },

  openTool(event) {
    const mode = event.currentTarget.dataset.key || 'simcraft'
    if (mode === 'simcraft') {
      this.submitSimulation()
      return
    }
    this.setData({ loading: true })
    loginWithWechat().catch(() => null).then(() => {
      return requestSimulatorAnalysis({
        mode,
        prompt: this.data.simPrompt
      })
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

  updateSimPrompt(event) {
    this.setData({ simPrompt: event.detail.value || '' })
  },

  useQuickReply(event) {
    const reply = event.currentTarget.dataset.reply || ''
    if (!reply) return
    const prompt = (this.data.simPrompt || '').trim()
    this.setData({
      simPrompt: prompt ? `${prompt}\n${reply}` : reply
    })
  },

  submitSimulation() {
    const prompt = (this.data.simPrompt || '').trim()
    this.setData({ loading: true })
    loginWithWechat().catch(() => null).then(() => {
      return requestSimulatorAnalysis({
        mode: 'simcraft_agent',
        prompt: this.data.simPrompt,
        message: this.data.simPrompt,
        round: this.data.agentRound,
        runSimulation: true
      })
    }).then(({ payload, fromFallback, error }) => {
      const nextRound = payload && payload.agent && payload.agent.status === 'needs_clarification'
        ? Math.min((payload.agent.round || this.data.agentRound) + 1, 3)
        : 1
      this.setData({
        latestAnalysis: payload,
        fromFallback,
        requestError: error || '',
        agentRound: nextRound
      })
      wx.showToast({
        title: prompt ? (fromFallback ? '已生成本地建议' : 'Agent 已返回') : '已提交模拟',
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
