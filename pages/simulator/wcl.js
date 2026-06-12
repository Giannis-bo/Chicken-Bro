const { loginWithWechat } = require('../common/auth-client')
const {
  requestSimulatorAnalysis
} = require('./simulator-api')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')

Page({
  data: {
    navTitle: '分析 WCL',
    kicker: '智能分析 02',
    title: '分析 WCL',
    desc: '粘贴 WCL 链接，并说明想解决的问题，例如输出偏低、爆发错位、覆盖率不足或减员原因。',
    loading: false,
    fromFallback: true,
    requestError: '',
    wclPrompt: 'WCL 链接：\n职业/专精：\n想分析的问题：输出为什么低？爆发窗口哪里有问题？',
    latestAnalysis: null
  },

  onLoad() {
    this.analyticsStartedAt = Date.now()
    trackPageView('pages/simulator/wcl', { source: 'simulator' })
  },

  onUnload() {
    trackPageLeave('pages/simulator/wcl', this.analyticsStartedAt)
  },

  updateWclPrompt(event) {
    this.setData({ wclPrompt: event.detail.value || '' })
  },

  submitWclAnalysis() {
    const prompt = (this.data.wclPrompt || '').trim()
    this.setData({ loading: true })
    trackEvent('wcl_submit', { hasPrompt: !!prompt }, { page: 'pages/simulator/wcl' })
    loginWithWechat().catch(() => null).then(() => {
      return requestSimulatorAnalysis({
        mode: 'wcl',
        prompt: this.data.wclPrompt,
        saveTask: true
      }, { auth: true, allowInsecureGuestRequest: true })
    }).then(({ payload, fromFallback, error }) => {
      this.setData({
        latestAnalysis: payload,
        fromFallback,
        requestError: error || ''
      })
      wx.showToast({
        title: prompt ? (fromFallback ? '已生成本地建议' : '分析已提交') : '已提交分析',
        icon: 'none'
      })
    }).finally(() => {
      this.setData({ loading: false })
    })
  }
})
