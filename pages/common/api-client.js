const DEV_API_BASE_URL = 'http://124.223.51.33'
const API_BASE_STORAGE_KEY = 'wow_backend_api_base_url'
const LEGACY_NEWS_API_BASE_STORAGE_KEY = 'wow_news_api_base_url'
const AUTH_TOKEN_STORAGE_KEY = 'wow_backend_auth_token'
const ANALYTICS_CLIENT_ID_STORAGE_KEY = 'wow_analytics_client_id'
const ANALYTICS_SESSION_ID_STORAGE_KEY = 'wow_analytics_session_id'
const ANALYTICS_SESSION_STARTED_AT_STORAGE_KEY = 'wow_analytics_session_started_at'
const ANALYTICS_SESSION_TTL_MS = 30 * 60 * 1000

let sessionIdCache = ''

function miniProgramEnvVersion() {
  if (typeof wx === 'undefined' || typeof wx.getAccountInfoSync !== 'function') return 'develop'
  const accountInfo = wx.getAccountInfoSync() || {}
  return (accountInfo.miniProgram && accountInfo.miniProgram.envVersion) || 'develop'
}

function configuredApiBaseUrl() {
  const app = typeof getApp === 'function' ? getApp() : null
  const globalData = app && app.globalData
  const globalApiBaseUrl = globalData && (globalData.backendApiBaseUrl || globalData.apiBaseUrl || globalData.newsApiBaseUrl)
  if (globalApiBaseUrl) return globalApiBaseUrl

  if (typeof wx !== 'undefined' && typeof wx.getStorageSync === 'function') {
    const storedApiBaseUrl = wx.getStorageSync(API_BASE_STORAGE_KEY) || wx.getStorageSync(LEGACY_NEWS_API_BASE_STORAGE_KEY)
    if (storedApiBaseUrl) return storedApiBaseUrl
  }

  if (typeof process !== 'undefined' && process.env) {
    return process.env.WOW_BACKEND_API_BASE_URL || process.env.WOW_NEWS_API_BASE_URL || (miniProgramEnvVersion() === 'develop' ? DEV_API_BASE_URL : '')
  }

  return miniProgramEnvVersion() === 'develop' ? DEV_API_BASE_URL : ''
}

function apiUrl(path) {
  const baseUrl = configuredApiBaseUrl()
  return baseUrl ? `${baseUrl}${path}` : ''
}

function isInsecureHttpUrl(url) {
  return /^http:\/\//i.test(url || '')
}

function storageGet(key) {
  if (typeof wx === 'undefined' || typeof wx.getStorageSync !== 'function') return ''
  return wx.getStorageSync(key) || ''
}

function storageSet(key, value) {
  if (typeof wx !== 'undefined' && typeof wx.setStorageSync === 'function') {
    wx.setStorageSync(key, value)
  }
}

function randomAnalyticsId(prefix) {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

function analyticsClientId() {
  const stored = storageGet(ANALYTICS_CLIENT_ID_STORAGE_KEY)
  if (stored) return stored
  const next = randomAnalyticsId('mp')
  storageSet(ANALYTICS_CLIENT_ID_STORAGE_KEY, next)
  return next
}

function analyticsSessionId() {
  if (sessionIdCache) return sessionIdCache
  const stored = storageGet(ANALYTICS_SESSION_ID_STORAGE_KEY)
  const startedAt = Number(storageGet(ANALYTICS_SESSION_STARTED_AT_STORAGE_KEY) || 0)
  if (stored && startedAt && Date.now() - startedAt < ANALYTICS_SESSION_TTL_MS) {
    sessionIdCache = stored
    return sessionIdCache
  }
  sessionIdCache = randomAnalyticsId('session')
  storageSet(ANALYTICS_SESSION_ID_STORAGE_KEY, sessionIdCache)
  storageSet(ANALYTICS_SESSION_STARTED_AT_STORAGE_KEY, String(Date.now()))
  return sessionIdCache
}

function analyticsHeaders(platform) {
  return {
    'X-Wow-Client-Id': analyticsClientId(),
    'X-Wow-Session-Id': analyticsSessionId(),
    'X-Wow-Platform': platform || 'miniprogram'
  }
}

function requestJson(path, options) {
  const requestOptions = options || {}
  return new Promise((resolve) => {
    const url = apiUrl(path)
    if (!url) {
      resolve({ payload: requestOptions.fallback(), fromFallback: true, error: 'missing api base url' })
      return
    }
    if (requestOptions.auth && isInsecureHttpUrl(url) && !requestOptions.allowInsecureGuestRequest) {
      resolve({ payload: requestOptions.fallback(), fromFallback: true, error: 'insecure api base url for authenticated request' })
      return
    }
    const header = Object.assign({}, analyticsHeaders('miniprogram'), requestOptions.header || {})
    if (requestOptions.auth && !isInsecureHttpUrl(url) && typeof wx !== 'undefined' && typeof wx.getStorageSync === 'function') {
      const token = wx.getStorageSync(AUTH_TOKEN_STORAGE_KEY)
      if (token) header.Authorization = `Bearer ${token}`
    }
    wx.request({
      url,
      method: requestOptions.method || 'GET',
      data: requestOptions.data,
      header,
      timeout: requestOptions.timeout || 6000,
      success: (res) => {
        const validate = requestOptions.validate || ((data) => !!data)
        if (res.statusCode >= 200 && res.statusCode < 300 && validate(res.data)) {
          resolve({ payload: res.data, fromFallback: false, error: '' })
          return
        }
        resolve({ payload: requestOptions.fallback(), fromFallback: true, error: `HTTP ${res.statusCode}` })
      },
      fail: (error) => {
        resolve({ payload: requestOptions.fallback(), fromFallback: true, error: error.errMsg || 'request failed' })
      }
    })
  })
}

module.exports = {
  API_BASE_STORAGE_KEY,
  AUTH_TOKEN_STORAGE_KEY,
  ANALYTICS_CLIENT_ID_STORAGE_KEY,
  ANALYTICS_SESSION_ID_STORAGE_KEY,
  ANALYTICS_SESSION_STARTED_AT_STORAGE_KEY,
  DEV_API_BASE_URL,
  analyticsClientId,
  analyticsHeaders,
  analyticsSessionId,
  apiUrl,
  configuredApiBaseUrl,
  isInsecureHttpUrl,
  miniProgramEnvVersion,
  requestJson
}
