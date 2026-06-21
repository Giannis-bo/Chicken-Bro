const {
  requestSimulatorAnalysis
} = require('./simulator-api')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')

Page({
  data: {
    navTitle: '炸鸡队长',
    kicker: '智能分析 03',
    title: '炸鸡队长',
    desc: '只整理可追踪证据；缺 SimC、WCL、角色上下文或同类样本时，会先列缺失项。',
    loading: false,
    fromFallback: true,
    requestError: '',
    chickenbroPrompt: '角色/专精：\n装等/场景：\n已有 SimC 或 WCL 证据：\n想优先解决的问题：',
    latestAnalysis: null
  },

  onLoad() {
    this.analyticsStartedAt = Date.now()
    trackPageView('pages/simulator/chickenbro', { source: 'simulator' })
  },

  onUnload() {
    trackPageLeave('pages/simulator/chickenbro', this.analyticsStartedAt)
  },

  updateChickenbroPrompt(event) {
    this.setData({ chickenbroPrompt: event.detail.value || '' })
  },

  submitChickenbroCoach() {
    const prompt = (this.data.chickenbroPrompt || '').trim()
    this.setData({ loading: true })
    trackEvent('chickenbro_submit', { hasPrompt: !!prompt }, { page: 'pages/simulator/chickenbro' })
    requestSimulatorAnalysis({
      mode: 'chickenbro',
      prompt,
      question: prompt
    })
      .then(({ payload, fromFallback, error }) => {
        this.setData({
          latestAnalysis: payload,
          fromFallback,
          requestError: error || ''
        })
        wx.showToast({
          title: fromFallback ? '已生成本地检查' : '证据教练已更新',
          icon: 'none'
        })
      }).finally(() => {
        this.setData({ loading: false })
      })
  }
})
