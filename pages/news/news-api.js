const { buildNewsHomePayload, createRefreshState, shouldAutoRefresh } = require('../../server/news/home-payload')
const seedArticles = require('../../server/news/articles.seed')
const { apiUrl } = require('../common/api-client')

const STORAGE_KEY = 'wow_news_last_refreshed_at'

function fallbackPayload(refreshMode) {
  return buildNewsHomePayload(seedArticles, createRefreshState(refreshMode || 'fallback'))
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
        if (res.statusCode >= 200 && res.statusCode < 300 && res.data && res.data.heroNews) {
          resolve({ payload: res.data, fromFallback: false, error: '' })
          return
        }
        resolve({ payload: fallbackPayload(refreshMode), fromFallback: true, error: `HTTP ${res.statusCode}` })
      },
      fail: (error) => {
        resolve({ payload: fallbackPayload(refreshMode), fromFallback: true, error: error.errMsg || 'request failed' })
      }
    })
  })
}

function requestManualRefresh() {
  return new Promise((resolve) => {
    const url = apiUrl('/api/news/refresh?mode=manual')
    if (!url) {
      resolve({ payload: fallbackPayload('manual-fallback'), fromFallback: true, error: 'missing api base url' })
      return
    }
    wx.request({
      url,
      method: 'POST',
      timeout: 8000,
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300 && res.data && res.data.heroNews) {
          resolve({ payload: res.data, fromFallback: false, error: '' })
          return
        }
        resolve({ payload: fallbackPayload('manual-fallback'), fromFallback: true, error: `HTTP ${res.statusCode}` })
      },
      fail: (error) => {
        resolve({ payload: fallbackPayload('manual-fallback'), fromFallback: true, error: error.errMsg || 'request failed' })
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

function fallbackArticleList(query) {
  query = normalizeListQuery(query)
  const payload = fallbackPayload('list-fallback')
  let articles = [...payload.highlights]
  if (query.type === 'channel') {
    articles = articles.filter((article) => article.channel === query.value)
  } else if (query.key === 'class-change') {
    articles = articles.filter((article) => (article.tags || []).indexOf('class-change') >= 0)
  } else if (query.key === 'ptr') {
    articles = articles.filter((article) => article.channel === '测试服前瞻')
  }
  const title = query.type === 'channel'
    ? query.value
    : query.key === 'class-change'
      ? '职业变动'
      : query.key === 'ptr'
        ? '测试服重点'
        : '今日更新'
  return {
    title,
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
        if (res.statusCode >= 200 && res.statusCode < 300 && res.data && res.data.articles) {
          resolve({ payload: res.data, fromFallback: false, error: '' })
          return
        }
        resolve({ payload: fallbackArticleList(query), fromFallback: true, error: `HTTP ${res.statusCode}` })
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
        if (res.statusCode >= 200 && res.statusCode < 300 && res.data && res.data.id) {
          resolve({ article: res.data, fromFallback: false, error: '' })
          return
        }
        resolve({ article: findFallbackArticle(articleId), fromFallback: true, error: `HTTP ${res.statusCode}` })
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
  requestManualRefresh,
  requestNewsHome,
  shouldRefreshToday
}
