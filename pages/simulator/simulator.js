const {
  fallbackSimulatorHome,
  requestSimulatorHome
} = require('./simulator-api')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')

Page({
  data: {
    ...fallbackSimulatorHome(),
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
  },

  onUnload() {
    if (this.analyticsVisible !== false) {
      trackPageLeave('pages/simulator/simulator', this.analyticsStartedAt)
      this.analyticsVisible = false
    }
  },

  onShow() {
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
    if (mode === 'chickenbro') {
      wx.navigateTo({ url: '/pages/simulator/chickenbro' })
    }
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
  }
})
