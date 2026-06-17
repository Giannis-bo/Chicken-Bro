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

function hasCompleteTranslatedBody(article) {
  const bodyZh = cleanText(article && article.bodyZh)
  const summary = cleanText(article && article.summary)
  const bodyBlocksZh = article && Array.isArray(article.bodyBlocksZh) ? article.bodyBlocksZh : []
  if (bodyBlocksZh.length) {
    const blockText = bodyBlocksZh.map((block) => {
      if (!block || typeof block !== 'object') return ''
      if (block.type === 'list') return Array.isArray(block.items) ? block.items.join(' ') : ''
      return cleanText(block.text)
    }).join(' ')
    if (/[\u4e00-\u9fff]/.test(blockText) && blockText.length >= 30) return true
  }
  if (bodyZh.length < 80) return false
  if (summary && (bodyZh === summary || bodyZh === `中文正文：${summary}`)) return false
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
