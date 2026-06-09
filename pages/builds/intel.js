const { fallbackBuildsIntel, requestBuildsIntel } = require('./builds-api')

Page({
  data: {
    ...fallbackBuildsIntel(),
    loading: false,
    fromFallback: true,
    requestError: ''
  },

  onLoad() {
    this.loadIntel()
  },

  openSpecDetail(event) {
    const specId = event.currentTarget.dataset.id
    if (!specId) return
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
