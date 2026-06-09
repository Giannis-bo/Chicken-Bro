const { requestArticleList } = require('./news-api')

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
    this.loadArticles({
      type: options.type || 'metric',
      key: options.key || 'today',
      value: options.value ? decodeURIComponent(options.value) : ''
    })
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
    wx.navigateTo({
      url: `/pages/news/detail?id=${encodeURIComponent(id)}`
    })
  }
})
