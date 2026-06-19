const test = require('node:test')
const assert = require('node:assert/strict')

function loadStorageModule(initialStorage) {
  const storage = { ...(initialStorage || {}) }
  delete global.getApp
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync(key) {
      return storage[key] || ''
    },
    setStorageSync(key, value) {
      storage[key] = value
    },
    request() {
      throw new Error('wx.request not mocked')
    }
  }
  delete require.cache[require.resolve('../pages/common/api-client')]
  delete require.cache[require.resolve('../pages/common/build-template-storage')]
  const api = require('../pages/common/build-template-storage')
  return { api, storage }
}

test('build template storage returns empty lists for missing or bad storage', () => {
  const { api, storage } = loadStorageModule()

  assert.deepEqual(api.listBuildTemplates(), [])
  storage[api.BUILD_TEMPLATE_STORAGE_KEY] = '{bad-json'
  assert.deepEqual(api.listBuildTemplates('talent'), [])
})

test('build template storage saves sorts dedupes and deletes local templates', () => {
  const { api } = loadStorageModule()

  const first = api.saveBuildTemplate({
    type: 'talent',
    title: '冰霜法师 · 大秘境',
    className: '法师',
    specName: '冰霜',
    scenarioTitle: '大秘境',
    rawString: 'websim:mage:frost:first',
    updatedAt: '2026-06-16T00:00:00.000Z'
  })
  const second = api.saveBuildTemplate({
    type: 'gear',
    title: '冰霜法师 · 单体',
    className: '法师',
    specName: '冰霜',
    scenarioTitle: '单体',
    rawString: 'head=,id=250060',
    updatedAt: '2026-06-17T00:00:00.000Z'
  })
  const duplicate = api.saveBuildTemplate({
    type: 'talent',
    title: '冰霜法师 · 团本',
    className: '法师',
    specName: '冰霜',
    scenarioTitle: '团本',
    rawString: 'websim:mage:frost:first',
    updatedAt: '2026-06-18T00:00:00.000Z'
  })

  assert.equal(duplicate.id, first.id)
  assert.equal(api.listBuildTemplates('talent').length, 1)
  assert.equal(api.listBuildTemplates('talent')[0].scenarioTitle, '团本')
  assert.deepEqual(api.listBuildTemplates().map((item) => item.id), [first.id, second.id])
  assert.deepEqual(api.buildTemplateSummary().map((item) => item.type), ['talent', 'gear'])
  assert.equal(api.buildTemplateSummary()[0].count, 1)

  assert.equal(api.deleteBuildTemplate(first.id), true)
  assert.deepEqual(api.listBuildTemplates('talent'), [])
  assert.equal(api.deleteBuildTemplate('missing'), false)
})

test('build template sync saves locally and falls back before sending auth over insecure http', async () => {
  const { api, storage } = loadStorageModule({
    wow_backend_api_base_url: 'http://example.test',
    wow_backend_auth_token: 'secret-token'
  })
  global.wx.request = () => {
    throw new Error('auth request should be blocked on insecure http')
  }

  const result = await api.syncBuildTemplate({
    type: 'talent',
    title: 'Local Frost',
    rawString: 'websim:mage:frost:local',
    status: 'encoded'
  })

  assert.equal(result.fromFallback, true)
  assert.match(result.error, /insecure api base url/)
  assert.equal(result.payload.template.title, 'Local Frost')
  assert.equal(api.listBuildTemplates('talent').length, 1)
  assert.ok(storage[api.BUILD_TEMPLATE_STORAGE_KEY])
})

test('build template sync merges remote template payloads over authenticated https', async () => {
  const { api } = loadStorageModule({
    wow_backend_api_base_url: 'https://api.example.test',
    wow_backend_auth_token: 'secret-token'
  })
  let requested = null
  global.wx.request = ({ url, method, data, header, success }) => {
    requested = { url, method, data, header }
    success({
      statusCode: 200,
      data: {
        template: {
          id: 'remote-template-1',
          clientId: data.template.id,
          type: 'gear',
          title: 'Remote Gear',
          rawString: 'head=,id=250777',
          status: 'simc_ready',
          updatedAt: '2026-06-19T01:00:00+00:00'
        },
        templates: []
      }
    })
  }

  const result = await api.syncBuildTemplate({
    type: 'gear',
    title: 'Local Gear',
    rawString: 'head=,id=250777',
    status: 'simc_ready'
  })

  assert.equal(result.fromFallback, false)
  assert.match(requested.url, /\/api\/me\/build-templates$/)
  assert.equal(requested.method, 'POST')
  assert.equal(requested.header.Authorization, 'Bearer secret-token')
  assert.equal(result.payload.template.id, 'remote-template-1')
  assert.deepEqual(api.listBuildTemplates('gear').map((item) => item.id), ['remote-template-1'])
  assert.equal(api.listBuildTemplates('gear')[0].title, 'Remote Gear')
})
