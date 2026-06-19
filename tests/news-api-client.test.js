const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

function loadNewsApiWithWx(wxMock) {
  global.wx = wxMock
  delete require.cache[require.resolve('../pages/news/news-api')]
  return require('../pages/news/news-api')
}

test('fallback seed remains plain JavaScript for the mini program packager', () => {
  const source = fs.readFileSync('server/news/articles.seed.js', 'utf8')

  assert.doesNotMatch(source, /require\(['"]\.\/articles\.seed\.json['"]\)/)
  assert.match(source, /module\.exports\s*=\s*\[/)
})

test('fallback seed stays synchronized with backend JSON seed', () => {
  const jsSeed = require('../server/news/articles.seed')
  const jsonSeed = JSON.parse(fs.readFileSync('server/news/articles.seed.json', 'utf8'))

  assert.deepEqual(jsSeed, jsonSeed)
})

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
  assert.ok(result.payload.heroNews.length > 0)
  assert.ok(result.payload.highlights.length > 0)
  assert.equal(result.payload.heroNews[0].translationFidelity, 'source_translation')
})

test('news home falls back when backend returns stale summary-only article payloads', async () => {
  const api = loadNewsApiWithWx({
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: () => '',
    request: ({ success }) => {
      success({
        statusCode: 200,
        data: {
          heroNews: [
            {
              id: 'worldofwarcraft-blizzard-com-76eea49dbd0e',
              title: '前往 Val 和 Naigtal 平息虚空领袖',
              summary: '与伊利达雷恶魔猎手和光铸军团一同冒险，前往两个全新区域——Val…',
              bodyZh: '中文正文：与伊利达雷恶魔猎手和光铸军团一同冒险，前往两个全新区域——Val…',
              sourceName: 'Blizzard News',
              sourceUrl: 'https://worldofwarcraft.blizzard.com/news/24270001/travel-to-val-and-naigtal',
              publishedAt: '2026-06-03',
              originalTitle: 'Travel to Val and Naigtal to Quell Leaders of the Void',
              tagItems: [{ id: 'class-change', label: '职业调整' }]
            }
          ],
          highlights: []
        }
      })
    }
  })

  const result = await api.requestNewsHome()

  assert.equal(result.fromFallback, true)
  assert.match(result.error, /incomplete article payload/)
  assert.ok(result.payload.heroNews.length > 0)
  assert.ok(result.payload.highlights.length > 0)
  assert.ok(
    [...result.payload.heroNews, ...result.payload.highlights]
      .every((article) => article.translationFidelity === 'source_translation')
  )
})

test('article detail request rejects stale summary-only backend payloads', async () => {
  const api = loadNewsApiWithWx({
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: () => '',
    request: ({ success }) => {
      success({
        statusCode: 200,
        data: {
          id: 'worldofwarcraft-blizzard-com-76eea49dbd0e',
          title: '前往 Val 和 Naigtal 平息虚空领袖',
          summary: '与伊利达雷恶魔猎手和光铸军团一同冒险，前往两个全新区域——Val…',
          bodyZh: '中文正文：与伊利达雷恶魔猎手和光铸军团一同冒险，前往两个全新区域——Val…',
          sourceName: 'Blizzard News',
          sourceUrl: 'https://worldofwarcraft.blizzard.com/news/24270001/travel-to-val-and-naigtal',
          publishedAt: '2026-06-03',
          originalTitle: 'Travel to Val and Naigtal to Quell Leaders of the Void',
          tagItems: [{ id: 'class-change', label: '职业调整' }]
        }
      })
    }
  })

  const result = await api.requestArticleDetail('worldofwarcraft-blizzard-com-76eea49dbd0e')

  assert.equal(result.fromFallback, true)
  assert.equal(result.article, null)
  assert.match(result.error, /incomplete article payload/)
})

test('article detail request rejects payloads missing trusted publication gates', async () => {
  const api = loadNewsApiWithWx({
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: () => '',
    request: ({ success }) => {
      success({
        statusCode: 200,
        data: {
          id: 'missing-publication-gates',
          title: '官方热修：2026 年 6 月 3 日',
          summary: '暴雪发布新的《魔兽世界》官方热修说明，覆盖职业问题修正。',
          bodyZh: '中文正文：暴雪发布新的官方热修说明，覆盖正式服近期问题修正。\n\n职业\n\n德鲁伊问题已修正。',
          bodyBlocksZh: [
            { type: 'paragraph', text: '暴雪发布新的官方热修说明，覆盖正式服近期问题修正。' }
          ],
          contentStatus: 'ready',
          translationStatus: 'llm',
          sourceName: 'Blizzard News',
          sourceUrl: 'https://worldofwarcraft.blizzard.com/news/24276957/hotfixes-june-3-2026',
          publishedAt: '2026-06-06',
          originalTitle: 'Hotfixes: June 3, 2026',
          tagItems: [{ id: 'hotfix', label: '热修' }]
        }
      })
    }
  })

  const result = await api.requestArticleDetail('missing-publication-gates')

  assert.equal(result.fromFallback, true)
  assert.equal(result.article, null)
  assert.match(result.error, /incomplete article payload/)
})

test('article detail request accepts verified body block payloads', async () => {
  const api = loadNewsApiWithWx({
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: () => '',
    request: ({ success }) => {
      success({
        statusCode: 200,
        data: {
          id: 'verified-body-blocks',
          title: '官方热修：2026 年 6 月 3 日',
          summary: '暴雪发布新的《魔兽世界》官方热修说明，覆盖职业问题修正。',
          bodyZh: '中文正文：暴雪发布新的官方热修说明，覆盖正式服近期问题修正。\n\n职业\n\n德鲁伊问题已修正。',
          bodyBlocksZh: [
            { type: 'paragraph', text: '暴雪发布新的官方热修说明，覆盖正式服近期问题修正。' },
            { type: 'heading', text: '职业' },
            { type: 'paragraph', text: '德鲁伊问题已修正。' }
          ],
          contentStatus: 'ready',
          translationStatus: 'llm',
          translationFidelity: 'source_translation',
          verificationStatus: 'official_verified',
          licenseStatus: 'approved',
          sourceTier: 'official',
          sourceBadges: ['官方已核验', '全文翻译'],
          sourceName: 'Blizzard News',
          sourceUrl: 'https://worldofwarcraft.blizzard.com/news/24276957/hotfixes-june-3-2026',
          publishedAt: '2026-06-06',
          originalTitle: 'Hotfixes: June 3, 2026',
          tagItems: [{ id: 'hotfix', label: '热修' }]
        }
      })
    }
  })

  const result = await api.requestArticleDetail('verified-body-blocks')

  assert.equal(result.fromFallback, false)
  assert.equal(result.article.bodyBlocksZh[1].type, 'heading')
})

test('article detail fallback exposes trusted seed with source translation fidelity', async () => {
  const api = loadNewsApiWithWx({
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'release' } }),
    getStorageSync: () => '',
    request: () => {
      throw new Error('request should not run without release API base URL')
    }
  })

  const result = await api.requestArticleDetail('blizzard-midnight-revelations-2026-06-03')

  assert.equal(result.fromFallback, true)
  assert.equal(result.article.id, 'blizzard-midnight-revelations-2026-06-03')
  assert.equal(result.article.translationFidelity, 'source_translation')
  assert.equal(result.article.verificationStatus, 'official_verified')
  assert.match(result.error, /missing api base url/)
})
