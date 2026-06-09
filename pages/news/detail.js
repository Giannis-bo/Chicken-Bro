const { requestArticleDetail } = require('./news-api')

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
    this.loadArticle(options.id || '')
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
    wx.setClipboardData({
      data: this.data.article.sourceUrl
    })
  }
})
