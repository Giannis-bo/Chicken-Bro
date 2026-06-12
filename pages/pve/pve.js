const { fallbackPveHome, requestPveHome } = require('./pve-api')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')

Page({
  data: {
    ...fallbackPveHome(),
    loading: false,
    fromFallback: true,
    requestError: ''
  },

  onLoad() {
    this.analyticsStartedAt = Date.now()
    this.analyticsVisible = true
    trackPageView('pages/pve/pve', { source: 'tab' })
    trackEvent('pve_home_view', { source: 'tab' }, { page: 'pages/pve/pve' })
    this.loadPveHome()
  },

  onShow() {
    if (this.analyticsVisible === false) {
      this.analyticsStartedAt = Date.now()
      this.analyticsVisible = true
      trackPageView('pages/pve/pve', { source: 'tab_resume' })
      trackEvent('pve_home_view', { source: 'tab_resume' }, { page: 'pages/pve/pve' })
    }
  },

  onHide() {
    if (this.analyticsVisible !== false) {
      trackPageLeave('pages/pve/pve', this.analyticsStartedAt)
      this.analyticsVisible = false
    }
  },

  onUnload() {
    if (this.analyticsVisible !== false) {
      trackPageLeave('pages/pve/pve', this.analyticsStartedAt)
      this.analyticsVisible = false
    }
  },

  openPveModule(event) {
    const moduleKey = event.currentTarget.dataset.key
    trackEvent('pve_module_open', { moduleKey: moduleKey || '' }, { page: 'pages/pve/pve' })
    wx.navigateTo({
      url: `/pages/pve/detail?module=${moduleKey}`
    })
  },

  loadPveHome() {
    this.setData({ loading: true })
    requestPveHome().then(({ payload, fromFallback, error }) => {
      this.setData({
        ...payload,
        fromFallback,
        requestError: error || ''
      })
    }).catch((error) => {
      this.setData({
        fromFallback: true,
        requestError: error && error.message ? error.message : 'request failed'
      })
    }).finally(() => {
      this.setData({ loading: false })
    })
  }
})
