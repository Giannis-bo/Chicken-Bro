const test = require('node:test')
const assert = require('node:assert/strict')

function loadStorageModule(initialStorage) {
  const storage = { ...(initialStorage || {}) }
  global.wx = {
    getStorageSync(key) {
      return storage[key] || ''
    },
    setStorageSync(key, value) {
      storage[key] = value
    }
  }
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
