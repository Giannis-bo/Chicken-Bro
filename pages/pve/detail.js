const { fallbackPveModule, requestPveModule } = require('./pve-api')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')

Page({
  data: {
    activeModule: fallbackPveModule('teamLadder'),
    loading: false,
    fromFallback: true,
    requestError: ''
  },

  onLoad(options) {
    const moduleKey = options.module || 'teamLadder'
    this.analyticsStartedAt = Date.now()
    this.analyticsModuleKey = moduleKey
    trackPageView('pages/pve/detail', { moduleKey })
    trackEvent('pve_module_view', { moduleKey }, { page: 'pages/pve/detail' })
    this.setData({
      activeModule: fallbackPveModule(moduleKey)
    })
    this.loadModule(moduleKey)
  },

  onUnload() {
    trackPageLeave('pages/pve/detail', this.analyticsStartedAt, { moduleKey: this.analyticsModuleKey || '' })
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
