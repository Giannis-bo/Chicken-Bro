const test = require('node:test')
const assert = require('node:assert/strict')

function loadNewsApiWithWx(wxMock) {
  global.wx = wxMock
  delete require.cache[require.resolve('../pages/news/news-api')]
  return require('../pages/news/news-api')
}

test('requestArticleList tolerates missing query input', async () => {
  let requestedUrl = ''
  const api = loadNewsApiWithWx({
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: () => '',
    request: ({ url, success }) => {
      requestedUrl = url
      success({ statusCode: 200, data: { articles: [] } })
    }
  })

  const result = await api.requestArticleList()

  assert.equal(result.fromFallback, false)
  assert.match(requestedUrl, /type=metric/)
  assert.match(requestedUrl, /key=today/)
})

test('release builds fall back when no HTTPS API base URL is configured', async () => {
  const api = loadNewsApiWithWx({
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'release' } }),
    getStorageSync: () => '',
    request: () => {
      throw new Error('request should not run without release API base URL')
    }
  })

  const result = await api.requestNewsHome()

  assert.equal(result.fromFallback, true)
  assert.match(result.error, /missing api base url/)
})
