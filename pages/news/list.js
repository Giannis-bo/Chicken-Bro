const { requestArticleList } = require('./news-api')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')

Page({
  data: {
    navTitle: '资讯列表',
    title: '',
    count: 0,
    articles: [],
    loading: true,
    fromFallback: false,
    requestError: ''
  },

  onLoad(options) {
    this.analyticsStartedAt = Date.now()
    const query = {
      type: options.type || 'metric',
      key: options.key || 'today',
      value: options.value ? decodeURIComponent(options.value) : ''
    }
    this.analyticsQuery = query
    trackPageView('pages/news/list', query)
    trackEvent('news_list_view', query, { page: 'pages/news/list' })
    this.loadArticles(query)
  },

  onUnload() {
    trackPageLeave('pages/news/list', this.analyticsStartedAt, this.analyticsQuery || {})
  },

  loadArticles(query) {
    requestArticleList(query).then(({ payload, fromFallback, error }) => {
      this.setData({
        navTitle: payload.title || '资讯列表',
        title: payload.title || '资讯列表',
        count: payload.count || 0,
        articles: payload.articles || [],
        loading: false,
        fromFallback,
        requestError: error || ''
      })
    })
  },

  openArticle(event) {
    const { id } = event.currentTarget.dataset
    if (!id) return
    trackEvent('news_article_open', { articleId: id, source: 'list' }, { page: 'pages/news/list' })
    wx.navigateTo({
      url: `/pages/news/detail?id=${encodeURIComponent(id)}`
    })
  }
})
