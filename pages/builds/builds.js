const { fallbackBuildsHome, requestBuildsHome } = require('./builds-api')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')

Page({
  data: {
    ...fallbackBuildsHome(),
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
  },

  onShow() {
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
      wx.navigateTo({
        url: '/pages/simulator/tasks?from=builds'
      })
      return
    }
    wx.navigateTo({
      url: `/pages/builds/detail?query=${encodeURIComponent(queryKey || '')}`
    })
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
  }
})
