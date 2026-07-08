const { buildNewsHomePayload, createRefreshState, shouldAutoRefresh } = require('../../server/news/home-payload')
const seedArticles = require('../../server/news/articles.seed')
const { apiUrl } = require('../common/api-client')

const STORAGE_KEY = 'wow_news_last_refreshed_at'

function fallbackPayload(refreshMode) {
  return buildNewsHomePayload(seedArticles, createRefreshState(refreshMode || 'fallback'))
}

function cleanText(value) {
  return typeof value === 'string' ? value.trim() : ''
}

function endsWithEllipsis(value) {
  return /(?:…|\.{3}|．．．)$/.test(cleanText(value))
}

function stripBodyLabel(value) {
  return cleanText(value).replace(/^中文正文\s*[:：]\s*/, '')
}

function bodyBlocksText(blocks) {
  return (Array.isArray(blocks) ? blocks : []).map((block) => {
    if (!block || typeof block !== 'object') return ''
    if (block.type === 'list') return Array.isArray(block.items) ? block.items.map(stripBodyLabel).join(' ') : ''
    return stripBodyLabel(block.text)
  }).filter(Boolean).join(' ')
}

function textLooksLikeSummary(bodyText, summary) {
  const body = stripBodyLabel(bodyText)
  const summaryText = stripBodyLabel(summary)
  if (!body || !summaryText) return false
  if (body === summaryText) return true
  return body.startsWith(summaryText) && body.length <= summaryText.length + 20
}

function hasCompleteTranslatedBody(article) {
  const bodyZh = stripBodyLabel(article && article.bodyZh)
  const summary = cleanText(article && article.summary)
  const bodyBlocksZh = article && Array.isArray(article.bodyBlocksZh) ? article.bodyBlocksZh : []
  if (bodyBlocksZh.length) {
    const blockText = bodyBlocksText(bodyBlocksZh)
    if (!/[\u4e00-\u9fff]/.test(blockText) || blockText.length < 30) return false
    if (summary && textLooksLikeSummary(blockText, summary)) return false
    if (summary && bodyBlocksZh.length === 1 && blockText.length <= summary.length + 20) return false
    if (endsWithEllipsis(blockText)) return false
    return true
  }
  if (bodyZh.length < 80) return false
  if (summary && textLooksLikeSummary(bodyZh, summary)) return false
  if (summary && bodyZh.length <= summary.length + 20) return false
  if (endsWithEllipsis(bodyZh)) return false
  return true
}

function isReadyArticlePayload(article) {
  if (!article || typeof article !== 'object') return false
  if (article.contentStatus !== 'ready') return false
  if (article.translationStatus !== 'llm') return false
  if (article.translationFidelity !== 'source_translation') return false
  if (article.verificationStatus !== 'official_verified') return false
  if (article.licenseStatus !== 'approved') return false
  if (article.sourceTier !== 'official') return false
  if (!cleanText(article.id) || !cleanText(article.title) || !cleanText(article.summary)) return false
  if (!cleanText(article.originalTitle) || !hasCompleteTranslatedBody(article)) return false
  if (!cleanText(article.sourceName) || !cleanText(article.sourceUrl) || !cleanText(article.publishedAt)) return false
  if (!Array.isArray(article.sourceBadges) || !article.sourceBadges.some((badge) => cleanText(badge))) return false
  return Array.isArray(article.tagItems) && article.tagItems.some((item) => cleanText(item && item.label))
}

function articleListIsReady(articles) {
  return Array.isArray(articles) && articles.every(isReadyArticlePayload)
}

function homePayloadIsReady(payload) {
  if (!payload || !Array.isArray(payload.heroNews) || !Array.isArray(payload.highlights)) return false
  const visibleArticles = [...payload.heroNews, ...payload.highlights]
  return visibleArticles.length > 0 && visibleArticles.every(isReadyArticlePayload)
}

function requestNewsHome(refreshMode) {
  return new Promise((resolve) => {
    const url = apiUrl('/api/news/home')
    if (!url) {
      resolve({ payload: fallbackPayload(refreshMode), fromFallback: true, error: 'missing api base url' })
      return
    }
    wx.request({
      url,
      method: 'GET',
      timeout: 6000,
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300 && homePayloadIsReady(res.data)) {
          resolve({ payload: res.data, fromFallback: false, error: '' })
          return
        }
        const error = res.statusCode >= 200 && res.statusCode < 300 ? 'incomplete article payload' : `HTTP ${res.statusCode}`
        resolve({ payload: fallbackPayload(refreshMode), fromFallback: true, error })
      },
      fail: (error) => {
        resolve({ payload: fallbackPayload(refreshMode), fromFallback: true, error: error.errMsg || 'request failed' })
      }
    })
  })
}

function findFallbackArticle(articleId) {
  const payload = fallbackPayload('detail-fallback')
  return [...payload.heroNews, ...payload.highlights].find((article) => article.id === articleId) || null
}

function normalizeListQuery(query) {
  const source = query && typeof query === 'object' ? query : {}
  return {
    type: source.type || 'metric',
    key: source.key || 'today',
    value: source.value || ''
  }
}

function articleSearchText(article) {
  const item = article || {}
  const tagItems = Array.isArray(item.tagItems) ? item.tagItems : []
  return [
    item.title,
    item.summary,
    item.channel,
    item.category,
    item.sourceName,
    item.sourceTier,
    item.verificationStatus,
    ...(item.tags || []),
    ...tagItems.map((tag) => `${tag && tag.id || ''} ${tag && tag.label || ''}`)
  ].join(' ').toLowerCase()
}

function filterFallbackByMetricKey(articles, key) {
  if (key === 'class-change') {
    return articles.filter((article) => (article.tags || []).indexOf('class-change') >= 0)
  }
  if (key === 'ptr') {
    return articles.filter((article) => article.channel === '测试服前瞻')
  }
  if (key === 'official') {
    return articles.filter((article) => /blizzard|官方|official|official_verified/.test(articleSearchText(article)))
  }
  if (key === 'updates') {
    return articles.filter((article) => /content-update|hotfix|patch|ptr|beta|class-change|更新|热修|测试服|职业调整/.test(articleSearchText(article)))
  }
  if (key === 'events') {
    return articles.filter((article) => /event|trading-post|weekly|rewards|活动|商栈|周报|奖励|timeways/.test(articleSearchText(article)))
  }
  if (key === 'community') {
    return articles.filter((article) => /community|社区|wowhead|icy veins|icy-veins/.test(articleSearchText(article)))
  }
  if (key === 'guides') {
    return articles.filter((article) => /guide|攻略|指南|how to|玩法|build|rotation|simc|wcl/.test(articleSearchText(article)))
  }
  return articles
}

function fallbackArticleListTitle(query) {
  if (query.type === 'channel') return query.value
  if (query.key === 'class-change') return '职业变动'
  if (query.key === 'ptr') return '测试服重点'
  if (query.key === 'official') return '官方'
  if (query.key === 'updates') return '更新'
  if (query.key === 'events') return '活动'
  if (query.key === 'community') return '社区'
  if (query.key === 'guides') return '攻略'
  return '今日更新'
}

function fallbackArticleList(query) {
  query = normalizeListQuery(query)
  const payload = fallbackPayload('list-fallback')
  let articles = [...payload.highlights]
  if (query.type === 'channel') {
    articles = articles.filter((article) => article.channel === query.value)
  } else {
    articles = filterFallbackByMetricKey(articles, query.key)
  }
  return {
    title: fallbackArticleListTitle(query),
    type: query.type || 'metric',
    key: query.key || 'today',
    value: query.value || '',
    count: articles.length,
    articles
  }
}

function requestArticleList(query) {
  query = normalizeListQuery(query)
  const params = [
    `type=${encodeURIComponent(query.type)}`,
    `key=${encodeURIComponent(query.key)}`,
    `value=${encodeURIComponent(query.value)}`
  ].join('&')
  return new Promise((resolve) => {
    const url = apiUrl(`/api/news/list?${params}`)
    if (!url) {
      resolve({ payload: fallbackArticleList(query), fromFallback: true, error: 'missing api base url' })
      return
    }
    wx.request({
      url,
      method: 'GET',
      timeout: 6000,
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300 && res.data && articleListIsReady(res.data.articles)) {
          resolve({ payload: res.data, fromFallback: false, error: '' })
          return
        }
        const error = res.statusCode >= 200 && res.statusCode < 300 ? 'incomplete article payload' : `HTTP ${res.statusCode}`
        resolve({ payload: fallbackArticleList(query), fromFallback: true, error })
      },
      fail: (error) => {
        resolve({ payload: fallbackArticleList(query), fromFallback: true, error: error.errMsg || 'request failed' })
      }
    })
  })
}

function requestArticleDetail(articleId) {
  return new Promise((resolve) => {
    const url = apiUrl(`/api/news/article?id=${encodeURIComponent(articleId || '')}`)
    if (!url) {
      resolve({ article: findFallbackArticle(articleId), fromFallback: true, error: 'missing api base url' })
      return
    }
    wx.request({
      url,
      method: 'GET',
      timeout: 6000,
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300 && isReadyArticlePayload(res.data)) {
          resolve({ article: res.data, fromFallback: false, error: '' })
          return
        }
        const error = res.statusCode >= 200 && res.statusCode < 300 ? 'incomplete article payload' : `HTTP ${res.statusCode}`
        resolve({ article: findFallbackArticle(articleId), fromFallback: true, error })
      },
      fail: (error) => {
        resolve({ article: findFallbackArticle(articleId), fromFallback: true, error: error.errMsg || 'request failed' })
      }
    })
  })
}

function rememberRefreshTime(value) {
  if (value) {
    wx.setStorageSync(STORAGE_KEY, value)
  }
}

function shouldRefreshToday(now) {
  const lastRefreshedAt = wx.getStorageSync(STORAGE_KEY)
  return shouldAutoRefresh(lastRefreshedAt, now || new Date().toISOString())
}

module.exports = {
  fallbackPayload,
  rememberRefreshTime,
  requestArticleDetail,
  requestArticleList,
  requestNewsHome,
  shouldRefreshToday
}
