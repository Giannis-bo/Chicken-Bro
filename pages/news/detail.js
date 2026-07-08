const { requestArticleDetail } = require('./news-api')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')

function stripBodyLabel(value) {
  return typeof value === 'string' ? value.replace(/^中文正文\s*[:：]\s*/, '') : value
}

function cleanBodyBlock(block) {
  if (!block || typeof block !== 'object') return block
  if (block.type === 'list') {
    return {
      ...block,
      items: Array.isArray(block.items) ? block.items.map(stripBodyLabel) : []
    }
  }
  return {
    ...block,
    text: stripBodyLabel(block.text || '')
  }
}

Page({
  data: {
    navTitle: '资讯详情',
    article: null,
    loading: true,
    missingId: false,
    notFound: false,
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
      this.setData({ loading: false, missingId: true, notFound: false, requestError: 'missing article id' })
      return
    }
    requestArticleDetail(articleId)
      .then(({ article, fromFallback, error }) => {
        this.setData({
          article: this.normalizeArticle(article),
          missingId: false,
          notFound: !article,
          fromFallback,
          requestError: error || ''
        })
      })
      .catch((error) => {
        this.setData({
          article: null,
          missingId: false,
          notFound: true,
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
    const tagItems = Array.isArray(article.tagItems) && article.tagItems.length
      ? article.tagItems
      : (article.tags || []).map((tag) => ({ id: tag, label: tag }))
    const bodyZh = article.bodyZh || ''
    const bodyBlocksZh = Array.isArray(article.bodyBlocksZh) && article.bodyBlocksZh.length
      ? article.bodyBlocksZh.map(cleanBodyBlock)
      : bodyZh.split(/\n\s*\n/).filter(Boolean).map((text) => ({ type: 'paragraph', text: stripBodyLabel(text) }))
    const originalTitle = article.originalTitle || article.title || ''
    const sourceBadges = Array.isArray(article.sourceBadges) && article.sourceBadges.length
      ? article.sourceBadges
      : ['官方已核验', '全文翻译']
    return {
      ...article,
      tagItems,
      bodyZh,
      bodyBlocksZh,
      originalTitle,
      sourceBadges,
      metaChips: [
        { label: '分类', value: article.category || '未分类' },
        { label: '频道', value: article.channel || '资讯' }
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
