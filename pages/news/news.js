const {
  fallbackPayload,
  rememberRefreshTime,
  requestManualRefresh,
  requestNewsHome,
  shouldRefreshToday
} = require('./news-api')

Page({
  data: {
    navTitle: '最新资讯',
    heroNews: [],
    metrics: [],
    channels: [],
    highlights: [],
    lastRefreshedAt: '',
    refreshMode: '',
    requestError: '',
    loading: false,
    fromFallback: false
  },

  onLoad() {
    this.applyPayload(fallbackPayload('bootstrap'), true)
    this.loadNews(shouldRefreshToday() ? 'scheduled' : 'cached')
  },

  onPullDownRefresh() {
    this.handleRefresh()
  },

  openArticle(event) {
    const { id } = event.currentTarget.dataset
    if (!id) return
    wx.navigateTo({
      url: `/pages/news/detail?id=${encodeURIComponent(id)}`
    })
  },

  openMetric(event) {
    const { key } = event.currentTarget.dataset
    wx.navigateTo({
      url: `/pages/news/list?type=metric&key=${encodeURIComponent(key || 'today')}`
    })
  },

  openChannel(event) {
    const { value } = event.currentTarget.dataset
    wx.navigateTo({
      url: `/pages/news/list?type=channel&value=${encodeURIComponent(value || '')}`
    })
  },

  loadNews(refreshMode) {
    this.setData({ loading: true })
    requestNewsHome(refreshMode).then(({ payload, fromFallback, error }) => {
      this.applyPayload(payload, fromFallback, error)
    }).finally(() => {
      this.setData({ loading: false })
      wx.stopPullDownRefresh()
    })
  },

  handleRefresh() {
    if (this.data.loading) return
    this.setData({ loading: true })
    requestManualRefresh().then(({ payload, fromFallback, error }) => {
      this.applyPayload(payload, fromFallback, error)
      wx.showToast({
        title: fromFallback ? '已显示本地缓存' : '刷新完成',
        icon: 'none'
      })
    }).finally(() => {
      this.setData({ loading: false })
      wx.stopPullDownRefresh()
    })
  },

  applyPayload(payload, fromFallback, error) {
    rememberRefreshTime(payload.lastRefreshedAt)
    this.setData({
      navTitle: payload.navTitle,
      heroNews: payload.heroNews,
      metrics: payload.metrics,
      channels: payload.channels,
      highlights: payload.highlights,
      lastRefreshedAt: payload.lastRefreshedAt,
      refreshMode: payload.refreshMode,
      requestError: error || '',
      fromFallback
    })
  }
})
