const { fallbackBuildsHome, requestBuildsHome } = require('./builds-api')

Page({
  data: {
    ...fallbackBuildsHome(),
    loading: false,
    fromFallback: true,
    requestError: ''
  },

  onLoad() {
    this.loadBuildsHome()
  },

  openQueryPage(event) {
    const queryKey = event.currentTarget.dataset.key
    wx.navigateTo({
      url: `/pages/builds/detail?query=${encodeURIComponent(queryKey || '')}`
    })
  },

  openIntelPage() {
    wx.navigateTo({
      url: '/pages/builds/intel'
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
