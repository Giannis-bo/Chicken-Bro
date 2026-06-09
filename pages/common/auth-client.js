const { AUTH_TOKEN_STORAGE_KEY, requestJson } = require('./api-client')

const AUTH_USER_STORAGE_KEY = 'wow_backend_auth_user'
const AUTH_EXPIRES_AT_STORAGE_KEY = 'wow_backend_auth_expires_at'
const AUTH_PROFILE_STORAGE_KEY = 'wow_backend_profile'
const DEFAULT_AUTH_TTL_MS = 7 * 24 * 60 * 60 * 1000

function storageGet(key) {
  if (typeof wx === 'undefined' || typeof wx.getStorageSync !== 'function') return ''
  return wx.getStorageSync(key) || ''
}

function storageSet(key, value) {
  if (typeof wx !== 'undefined' && typeof wx.setStorageSync === 'function') {
    wx.setStorageSync(key, value)
  }
}

function parseStoredUser(value) {
  if (!value) return null
  if (typeof value === 'object') return value
  try {
    return JSON.parse(value)
  } catch (error) {
    return null
  }
}

function currentAuth() {
  const accessToken = storageGet(AUTH_TOKEN_STORAGE_KEY)
  let expiresAt = Number(storageGet(AUTH_EXPIRES_AT_STORAGE_KEY) || 0)
  if (accessToken && !expiresAt) {
    expiresAt = Date.now() + DEFAULT_AUTH_TTL_MS
    storageSet(AUTH_EXPIRES_AT_STORAGE_KEY, String(expiresAt))
  }
  if (accessToken && expiresAt <= Date.now()) {
    clearAuth()
    return { accessToken: '', user: null, expiresAt: 0 }
  }
  return {
    accessToken,
    user: parseStoredUser(storageGet(AUTH_USER_STORAGE_KEY)),
    expiresAt
  }
}

function currentProfile() {
  return parseStoredUser(storageGet(AUTH_PROFILE_STORAGE_KEY)) || (currentAuth().user || {})
}

function saveLocalProfile(profile) {
  const current = currentProfile()
  const next = {
    ...current,
    ...profile,
    nickname: typeof profile.nickname === 'string' ? profile.nickname.trim() : current.nickname || '',
    avatarUrl: profile.avatarUrl || current.avatarUrl || ''
  }
  storageSet(AUTH_PROFILE_STORAGE_KEY, JSON.stringify(next))
  return next
}

function persistAuth(payload) {
  if (!payload || !payload.accessToken) return payload
  const expiresAt = Number(payload.expiresAt || payload.expires_at || 0) || Date.now() + DEFAULT_AUTH_TTL_MS
  storageSet(AUTH_TOKEN_STORAGE_KEY, payload.accessToken)
  storageSet(AUTH_USER_STORAGE_KEY, JSON.stringify(payload.user || null))
  storageSet(AUTH_EXPIRES_AT_STORAGE_KEY, String(expiresAt))
  if (payload.user) saveLocalProfile(payload.user)
  return payload
}

function clearAuth() {
  storageSet(AUTH_TOKEN_STORAGE_KEY, '')
  storageSet(AUTH_USER_STORAGE_KEY, '')
  storageSet(AUTH_EXPIRES_AT_STORAGE_KEY, '')
}

function wxLoginCode() {
  return new Promise((resolve, reject) => {
    if (typeof wx === 'undefined' || typeof wx.login !== 'function') {
      reject(new Error('wx.login is unavailable'))
      return
    }
    wx.login({
      success: (res) => {
        if (res && res.code) {
          resolve(res.code)
        } else {
          reject(new Error('wx.login did not return code'))
        }
      },
      fail: (error) => reject(new Error((error && error.errMsg) || 'wx.login failed'))
    })
  })
}

async function loginWithWechat() {
  const existing = currentAuth()
  if (existing.accessToken && existing.user) return existing

  const code = await wxLoginCode()
  const result = await requestJson('/api/auth/wechat-login', {
    method: 'POST',
    data: { code },
    timeout: 10000,
    fallback: () => ({ accessToken: '', user: null }),
    validate: (data) => data && data.accessToken && data.user
  })
  if (result.fromFallback || !result.payload.accessToken) {
    throw new Error(result.error || 'wechat login failed')
  }
  return persistAuth(result.payload)
}

async function saveProfile(profile) {
  const auth = await loginWithWechat()
  const result = await requestJson('/api/me/profile', {
    method: 'POST',
    auth: true,
    data: profile || {},
    fallback: () => auth.user,
    validate: (data) => data && data.openid
  })
  if (!result.fromFallback) {
    persistAuth({ accessToken: auth.accessToken, user: result.payload })
  }
  return result
}

async function saveProfileDraft(profile) {
  const localProfile = saveLocalProfile(profile || {})
  try {
    const result = await saveProfile(localProfile)
    return result.fromFallback ? { ...result, payload: localProfile } : result
  } catch (error) {
    return {
      payload: localProfile,
      fromFallback: true,
      error: error.message || 'profile saved locally'
    }
  }
}

module.exports = {
  AUTH_TOKEN_STORAGE_KEY,
  AUTH_EXPIRES_AT_STORAGE_KEY,
  AUTH_PROFILE_STORAGE_KEY,
  AUTH_USER_STORAGE_KEY,
  clearAuth,
  currentAuth,
  currentProfile,
  loginWithWechat,
  persistAuth,
  saveLocalProfile,
  saveProfile,
  saveProfileDraft,
  wxLoginCode
}
