const { requestArticleDetail } = require('./news-api')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')

Page({
  data: {
    navTitle: '资讯详情',
    article: null,
    loading: true,
    homeButton: false,
    fromFallback: false,
    requestError: ''
  },

  onLoad(options) {
    const articleId = options.id || ''
    this.analyticsStartedAt = Date.now()
    this.analyticsArticleId = articleId
    trackPageView('pages/news/detail', { articleId })
    trackEvent('news_article_view', { articleId }, { page: 'pages/news/detail' })
    this.loadArticle(articleId)
  },

  onUnload() {
    trackPageLeave('pages/news/detail', this.analyticsStartedAt, { articleId: this.analyticsArticleId || '' })
  },

  onShow() {
    const pages = typeof getCurrentPages === 'function' ? getCurrentPages() : []
    this.setData({
      homeButton: pages.length > 2
    })
  },

  loadArticle(articleId) {
    if (!articleId) {
      this.setData({ loading: false, requestError: 'missing article id' })
      return
    }
    requestArticleDetail(articleId)
      .then(({ article, fromFallback, error }) => {
        this.setData({
          article: this.normalizeArticle(article),
          fromFallback,
          requestError: error || ''
        })
      })
      .catch((error) => {
        this.setData({
          article: null,
          fromFallback: true,
          requestError: error && error.message ? error.message : 'request failed'
        })
      })
      .finally(() => {
        this.setData({ loading: false })
      })
  },

  normalizeArticle(article) {
    if (!article) return null
    const tags = article.tags || []
    const tagsText = tags.length ? tags.join(' / ') : '无'
    const bodyZh = article.bodyZh || article.summary || ''
    const originalTitle = article.originalTitle || article.title || ''
    const originalBody = article.originalBody || article.originalSummary || article.summary || ''
    return {
      ...article,
      tagsText,
      bodyZh,
      originalTitle,
      originalBody,
      metaChips: [
        { label: '分类', value: article.category || '未分类' },
        { label: '频道', value: article.channel || '资讯' },
        { label: '标签', value: tagsText }
      ]
    }
  },

  copySourceUrl() {
    if (!this.data.article || !this.data.article.sourceUrl) return
    trackEvent('news_source_copy', { articleId: this.data.article.id || this.analyticsArticleId || '' }, { page: 'pages/news/detail' })
    wx.setClipboardData({
      data: this.data.article.sourceUrl
    })
  }
})
