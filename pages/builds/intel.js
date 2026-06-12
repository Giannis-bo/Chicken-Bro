const { fallbackBuildsIntel, requestBuildsIntel } = require('./builds-api')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')

Page({
  data: {
    ...fallbackBuildsIntel(),
    loading: false,
    fromFallback: true,
    requestError: ''
  },

  onLoad() {
    this.analyticsStartedAt = Date.now()
    trackPageView('pages/builds/intel', { source: 'builds' })
    this.loadIntel()
  },

  onUnload() {
    trackPageLeave('pages/builds/intel', this.analyticsStartedAt)
  },

  openSpecDetail(event) {
    const specId = event.currentTarget.dataset.id
    if (!specId) return
    trackEvent('builds_query_open', { queryKey: 'talents', specId, source: 'intel' }, { page: 'pages/builds/intel' })
    wx.navigateTo({
      url: `/pages/builds/detail?query=talents&spec=${encodeURIComponent(specId)}`
    })
  },

  loadIntel() {
    this.setData({ loading: true })
    requestBuildsIntel().then(({ payload, fromFallback, error }) => {
      this.setData({
        ...payload,
        fromFallback,
        requestError: error || ''
      })
    }).catch((error) => {
      this.setData({
        requestError: error.message || String(error),
        fromFallback: true
      })
    }).finally(() => {
      this.setData({ loading: false })
    })
  }
})
