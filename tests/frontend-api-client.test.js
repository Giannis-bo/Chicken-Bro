const test = require('node:test')
const assert = require('node:assert/strict')

function resetModule(path) {
  delete require.cache[require.resolve(path)]
  return require(path)
}

test('shared api client uses the Lighthouse backend in develop and no implicit URL in release', () => {
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: () => ''
  }
  let client = resetModule('../pages/common/api-client')
  assert.equal(client.apiUrl('/health'), 'http://124.223.51.33/health')

  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'release' } }),
    getStorageSync: () => ''
  }
  client = resetModule('../pages/common/api-client')
  assert.equal(client.apiUrl('/health'), '')
})

test('builds api returns fallback without an API base and remote payload when request succeeds', async () => {
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'release' } }),
    getStorageSync: () => '',
    request: () => {
      throw new Error('request should not run without an api base url')
    }
  }
  let api = resetModule('../pages/builds/builds-api')
  let result = await api.requestBuildsHome()
  assert.equal(result.fromFallback, true)
  assert.equal(result.payload.navTitle, '职业专精')

  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: () => '',
    request: ({ success }) => success({ statusCode: 200, data: { navTitle: '远端职业专精', quickActions: [] } })
  }
  api = resetModule('../pages/builds/builds-api')
  result = await api.requestBuildsHome()
  assert.equal(result.fromFallback, false)
  assert.equal(result.payload.navTitle, '远端职业专精')
})

test('pve and simulator apis expose fallback payloads', async () => {
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'release' } }),
    getStorageSync: () => '',
    request: () => {
      throw new Error('request should not run without an api base url')
    }
  }
  const pveApi = resetModule('../pages/pve/pve-api')
  const simulatorApi = resetModule('../pages/simulator/simulator-api')

  const pveHome = await pveApi.requestPveHome()
  const simulatorHome = await simulatorApi.requestSimulatorHome()
  const analysis = await simulatorApi.requestSimulatorAnalysis({ mode: 'simcraft' })

  assert.equal(pveHome.fromFallback, true)
  assert.equal(pveHome.payload.navTitle, '副本')
  assert.equal(simulatorHome.fromFallback, true)
  assert.equal(simulatorHome.payload.navTitle, '模拟器')
  assert.equal(analysis.fromFallback, true)
  assert.equal(analysis.payload.mode, 'simcraft')
})

test('auth client exchanges wx.login code and stores backend token', async () => {
  const storage = {}
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: (key) => storage[key] || '',
    setStorageSync: (key, value) => {
      storage[key] = value
    },
    login: ({ success }) => success({ code: 'wx-code-1' }),
    request: ({ url, method, data, success }) => {
      assert.match(url, /\/api\/auth\/wechat-login$/)
      assert.equal(method, 'POST')
      assert.equal(data.code, 'wx-code-1')
      success({
        statusCode: 200,
        data: {
          accessToken: 'token-1',
          tokenType: 'Bearer',
          user: { openid: 'openid-1', nickname: '', avatarUrl: '' }
        }
      })
    }
  }

  const auth = resetModule('../pages/common/auth-client')
  const result = await auth.loginWithWechat()

  assert.equal(result.accessToken, 'token-1')
  assert.equal(auth.currentAuth().accessToken, 'token-1')
  assert.equal(auth.currentAuth().user.openid, 'openid-1')
})

test('authorized requests attach bearer token from storage', async () => {
  const storage = {
    wow_backend_api_base_url: 'https://api.example.test',
    wow_backend_auth_token: 'token-2'
  }
  let authorization = ''
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: (key) => storage[key] || '',
    request: ({ header, success }) => {
      authorization = header.Authorization
      success({ statusCode: 200, data: { ok: true } })
    }
  }

  const client = resetModule('../pages/common/api-client')
  const result = await client.requestJson('/api/private', {
    auth: true,
    fallback: () => ({ ok: false })
  })

  assert.equal(result.fromFallback, false)
  assert.equal(authorization, 'Bearer token-2')
})

test('authorized requests do not send bearer token over insecure http base url', async () => {
  const storage = {
    wow_backend_api_base_url: 'http://api.example.test',
    wow_backend_auth_token: 'token-3'
  }
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: (key) => storage[key] || '',
    request: () => {
      throw new Error('authenticated request should not run over http')
    }
  }

  const client = resetModule('../pages/common/api-client')
  const result = await client.requestJson('/api/private', {
    auth: true,
    fallback: () => ({ ok: false })
  })

  assert.equal(result.fromFallback, true)
  assert.match(result.error, /insecure api base url/)
})

test('profile drafts persist locally even when remote auth endpoint is unavailable', async () => {
  const storage = {}
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: (key) => storage[key] || '',
    setStorageSync: (key, value) => {
      storage[key] = value
    },
    login: ({ success }) => success({ code: 'wx-code-404' }),
    request: ({ success }) => success({ statusCode: 404, data: { error: 'not_found' } })
  }

  const auth = resetModule('../pages/common/auth-client')
  const result = await auth.saveProfileDraft({
    nickname: '微信昵称',
    avatarUrl: 'wxfile://avatar'
  })

  assert.equal(result.fromFallback, true)
  assert.equal(auth.currentProfile().nickname, '微信昵称')
  assert.equal(auth.currentProfile().avatarUrl, 'wxfile://avatar')
})
