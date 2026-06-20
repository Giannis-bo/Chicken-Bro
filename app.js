const { currentAuth } = require('./pages/common/auth-client')
const { DEV_API_BASE_URL } = require('./pages/common/api-client')

App({
  globalData: {
    auth: null,
    backendApiBaseUrl: DEV_API_BASE_URL
  },

  onLaunch() {
    this.globalData.auth = currentAuth()
  }
})
