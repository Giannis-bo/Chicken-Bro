const { currentAuth } = require('./pages/common/auth-client')

App({
  globalData: {
    auth: null
  },

  onLaunch() {
    this.globalData.auth = currentAuth()
  }
})
