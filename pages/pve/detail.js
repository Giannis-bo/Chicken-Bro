const { fallbackPveModule, requestPveModule } = require('./pve-api')

Page({
  data: {
    activeModule: fallbackPveModule('teamLadder'),
    loading: false,
    fromFallback: true,
    requestError: ''
  },

  onLoad(options) {
    const moduleKey = options.module || 'teamLadder'
    this.setData({
      activeModule: fallbackPveModule(moduleKey)
    })
    this.loadModule(moduleKey)
  },

  loadModule(moduleKey) {
    this.setData({ loading: true })
    requestPveModule(moduleKey).then(({ payload, fromFallback, error }) => {
      this.setData({
        activeModule: payload,
        fromFallback,
        requestError: error || ''
      })
    }).catch((error) => {
      this.setData({
        fromFallback: true,
        requestError: error && error.message ? error.message : 'request failed'
      })
    }).finally(() => {
      this.setData({ loading: false })
    })
  }
})
