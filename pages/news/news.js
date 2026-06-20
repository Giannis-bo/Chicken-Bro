const {
  fallbackPayload,
  rememberRefreshTime,
  requestNewsHome,
  shouldRefreshToday
} = require('./news-api')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')

Page({
  data: {
    navTitle: '最新资讯',
    heroNews: [],
    channels: [],
    highlights: [],
    lastRefreshedAt: '',
    refreshMode: '',
    requestError: '',
    loading: false,
    fromFallback: false
  },

  onLoad() {
    this.analyticsStartedAt = Date.now()
    this.analyticsVisible = true
    trackPageView('pages/news/news', { source: 'tab' })
    trackEvent('news_home_view', { source: 'tab' }, { page: 'pages/news/news' })
    this.applyPayload(fallbackPayload('bootstrap'), true)
    this.loadNews(shouldRefreshToday() ? 'scheduled' : 'cached')
  },

  onShow() {
    if (this.analyticsVisible === false) {
      this.analyticsStartedAt = Date.now()
      this.analyticsVisible = true
      trackPageView('pages/news/news', { source: 'tab_resume' })
      trackEvent('news_home_view', { source: 'tab_resume' }, { page: 'pages/news/news' })
    }
  },

  onHide() {
    if (this.analyticsVisible !== false) {
      trackPageLeave('pages/news/news', this.analyticsStartedAt)
      this.analyticsVisible = false
    }
  },

  onUnload() {
    if (this.analyticsVisible !== false) {
      trackPageLeave('pages/news/news', this.analyticsStartedAt)
      this.analyticsVisible = false
    }
  },

  openArticle(event) {
    const { id } = event.currentTarget.dataset
    if (!id) return
    trackEvent('news_article_open', { articleId: id, source: 'home' }, { page: 'pages/news/news' })
    wx.navigateTo({
      url: `/pages/news/detail?id=${encodeURIComponent(id)}`
    })
  },

  openChannel(event) {
    const { value } = event.currentTarget.dataset
    trackEvent('news_list_view', { type: 'channel', value: value || '', source: 'channel_item' }, { page: 'pages/news/news' })
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
    })
  },

  applyPayload(payload, fromFallback, error) {
    rememberRefreshTime(payload.lastRefreshedAt)
    this.setData({
      navTitle: payload.navTitle,
      heroNews: payload.heroNews,
      channels: payload.channels,
      highlights: payload.highlights,
      lastRefreshedAt: payload.lastRefreshedAt,
      refreshMode: payload.refreshMode,
      requestError: error || '',
      fromFallback
    })
  }
})
