import { storageKey, type NewsArticle, type NewsHomePayload, type NewsListParams, type NewsListPayload } from '@wow-mini/domain'

import { cleanString, encodeQuery, isRecord } from './guards'
import { taroStorage, type StorageAdapter } from './storage'
import type { ApiResult, ApiTransport } from './transport'

function bodyBlocksText(value: unknown): string {
  if (!Array.isArray(value)) return ''
  return value.map((block) => {
    if (!isRecord(block)) return ''
    if (block['type'] === 'list' && Array.isArray(block['items'])) {
      return block['items'].map(cleanString).filter(Boolean).join(' ')
    }
    return cleanString(block['text'])
  }).filter(Boolean).join(' ')
}

function hasCompleteTranslatedBody(article: Record<string, unknown>): boolean {
  const summary = cleanString(article['summary'])
  const body = cleanString(article['bodyZh']).replace(/^中文正文\s*[:：]\s*/, '')
  const blockText = bodyBlocksText(article['bodyBlocksZh']).replace(/^中文正文\s*[:：]\s*/, '')
  const text = blockText || body
  if (!/[\u4e00-\u9fff]/.test(text) || text.length < 30) return false
  if (summary && (text === summary || (text.startsWith(summary) && text.length <= summary.length + 20))) return false
  return !/(?:…|\.{3}|．．．)$/.test(text)
}

export function isReadyNewsArticle(value: unknown): value is NewsArticle {
  if (!isRecord(value)) return false
  if (value['contentStatus'] !== 'ready') return false
  if (value['translationStatus'] !== 'llm') return false
  if (value['translationFidelity'] !== 'source_translation') return false
  if (value['verificationStatus'] !== 'official_verified') return false
  if (value['licenseStatus'] !== 'approved') return false
  if (value['sourceTier'] !== 'official') return false
  const required = ['id', 'title', 'summary', 'originalTitle', 'sourceName', 'sourceUrl', 'publishedAt']
  if (required.some((key) => !cleanString(value[key]))) return false
  if (!Array.isArray(value['sourceBadges']) || !value['sourceBadges'].some((badge) => cleanString(badge))) return false
  if (!Array.isArray(value['tagItems']) || !value['tagItems'].some((tag) => isRecord(tag) && cleanString(tag['label']))) return false
  return hasCompleteTranslatedBody(value)
}

function isNewsMetric(value: unknown): boolean {
  if (!isRecord(value) || !cleanString(value['key']) || !cleanString(value['label'])) return false
  const metricValue = value['value']
  return (typeof metricValue === 'string' && metricValue.trim().length > 0)
    || (typeof metricValue === 'number' && Number.isFinite(metricValue))
}

function isNewsChannel(value: unknown): boolean {
  if (!isRecord(value) || !cleanString(value['id']) || !cleanString(value['title'])) return false
  const updateCount = value['updateCount']
  return updateCount === undefined || (typeof updateCount === 'number' && Number.isFinite(updateCount) && updateCount >= 0)
}

export function isReadyNewsHomePayload(value: unknown): value is NewsHomePayload {
  if (!isRecord(value)
    || !cleanString(value['navTitle'])
    || !cleanString(value['lastRefreshedAt'])
    || !cleanString(value['refreshMode'])
    || !Array.isArray(value['heroNews'])
    || !Array.isArray(value['highlights'])
    || !Array.isArray(value['metrics'])
    || !Array.isArray(value['channels'])
    || !value['metrics'].every(isNewsMetric)
    || !value['channels'].every(isNewsChannel)) return false
  const visible = [...value['heroNews'], ...value['highlights']]
  return visible.length > 0 && visible.every(isReadyNewsArticle)
}

function isReadyNewsList(value: unknown): value is NewsListPayload {
  return isRecord(value)
    && Array.isArray(value['articles'])
    && value['articles'].every(isReadyNewsArticle)
}

function fallbackHome(refreshMode: string): NewsHomePayload {
  return {
    navTitle: '',
    heroNews: [],
    metrics: [],
    channels: [],
    highlights: [],
    lastRefreshedAt: '',
    refreshMode,
  }
}

const supplementalHomeMetrics = [
  { key: 'updates', label: '更新' },
  { key: 'events', label: '活动' },
] as const

async function supplementLiveHomeMetrics(
  transport: ApiTransport,
  result: ApiResult<NewsHomePayload>,
): Promise<ApiResult<NewsHomePayload>> {
  if (result.fromFallback) return result
  const existing = new Set(result.payload.metrics.map((metric) => metric.key))
  const missing = supplementalHomeMetrics.filter((metric) => !existing.has(metric.key))
  if (!missing.length) return result

  const responses = await Promise.all(missing.map(async (metric) => ({
    metric,
    result: await transport.requestEndpoint('news.list', `/api/news/list?${encodeQuery({
      type: 'metric',
      key: metric.key,
      value: '',
    })}`, {
      attachAnalyticsHeaders: false,
      fallback: () => fallbackList({ type: 'metric', key: metric.key, value: '' }),
      validate: isReadyNewsList,
    }),
  })))
  const additions = responses.flatMap(({ metric, result: listResult }) => (
    listResult.fromFallback
      ? []
      : [{ key: metric.key, label: metric.label, value: String(listResult.payload.count) }]
  ))
  if (!additions.length) return result
  return {
    ...result,
    payload: {
      ...result.payload,
      metrics: [...result.payload.metrics, ...additions],
    },
  }
}

function distinctHomeHighlights(payload: NewsHomePayload): readonly NewsArticle[] {
  const heroIds = new Set(payload.heroNews.map((article) => article.id).filter(Boolean))
  const seen = new Set<string>()
  return payload.highlights.filter((article) => {
    if (!article.id || heroIds.has(article.id) || seen.has(article.id)) return false
    seen.add(article.id)
    return true
  })
}

async function supplementLiveHomeHighlights(
  transport: ApiTransport,
  result: ApiResult<NewsHomePayload>,
): Promise<ApiResult<NewsHomePayload>> {
  const distinct = [...distinctHomeHighlights(result.payload)]
  if (!result.fromFallback && distinct.length < 4) {
    const listResult = await transport.requestEndpoint('news.list', `/api/news/list?${encodeQuery({
      type: 'metric',
      key: 'today',
      value: '',
    })}`, {
      attachAnalyticsHeaders: false,
      fallback: () => fallbackList({ type: 'metric', key: 'today', value: '' }),
      validate: isReadyNewsList,
    })
    if (!listResult.fromFallback) {
      const heroIds = new Set(result.payload.heroNews.map((article) => article.id).filter(Boolean))
      const seen = new Set(distinct.map((article) => article.id))
      for (const article of listResult.payload.articles) {
        if (!article.id || heroIds.has(article.id) || seen.has(article.id)) continue
        seen.add(article.id)
        distinct.push(article)
        if (distinct.length >= 6) break
      }
    }
  }
  return {
    ...result,
    payload: {
      ...result.payload,
      highlights: distinct.slice(0, 6),
    },
  }
}

function articleSearchText(article: NewsArticle): string {
  return [
    article.title,
    article.summary,
    article.channel,
    article.category,
    article.sourceName,
    article.sourceTier,
    article.verificationStatus,
    ...(article.tags ?? []),
    ...(article.tagItems ?? []).map((tag) => `${tag.id ?? ''} ${tag.label}`),
  ].join(' ').toLowerCase()
}

function fallbackListTitle(query: Required<NewsListParams>): string {
  if (query.type === 'channel') return query.value
  const titles: Readonly<Record<string, string>> = {
    'class-change': '职业变动',
    ptr: '测试服重点',
    official: '官方',
    updates: '更新',
    events: '活动',
    community: '社区',
    guides: '攻略',
    'mythic-plus': '大秘境',
    gear: '装备',
    system: '系统',
  }
  return titles[query.key] ?? '今日更新'
}

function fallbackList(params: NewsListParams): NewsListPayload {
  const query: Required<NewsListParams> = {
    type: params.type ?? 'metric',
    key: params.key ?? 'today',
    value: params.value ?? '',
  }
  let articles: NewsArticle[] = []
  if (query.type === 'channel') {
    articles = articles.filter((article) => article.channel === query.value)
  } else if (query.key === 'class-change') {
    articles = articles.filter((article) => article.tags?.includes('class-change'))
  } else if (query.key === 'ptr') {
    articles = articles.filter((article) => article.channel === '测试服前瞻')
  } else {
    const patterns: Readonly<Record<string, RegExp>> = {
      official: /blizzard|官方|official|official_verified/,
      updates: /content-update|hotfix|patch|ptr|beta|class-change|更新|热修|测试服|职业调整/,
      events: /event|trading-post|weekly|rewards|活动|商栈|周报|奖励|timeways/,
      community: /community|社区|wowhead|icy veins|icy-veins/,
      guides: /guide|攻略|指南|how to|玩法|build|rotation|simc|wcl/,
      'mythic-plus': /mythic[- ]?plus|mythic\+|keystone|m\+|大秘|史诗钥石|秘境/,
      gear: /gear|item|loot|trinket|weapon|armor|tier[- ]?set|equipment|装备|物品|战利品|饰品|武器|护甲|套装/,
      system: /system|feature|interface|warband|delve|housing|profession|collection|account|系统|功能|界面|战团|地下堡|住房|专业|收藏|账号/,
    }
    const pattern = patterns[query.key]
    if (pattern) articles = articles.filter((article) => pattern.test(articleSearchText(article)))
  }
  return {
    title: fallbackListTitle(query),
    type: query.type,
    key: query.key,
    value: query.value,
    count: articles.length,
    articles,
  }
}

export interface NewsClient {
  home(refreshMode?: string): Promise<ApiResult<NewsHomePayload>>
  list(params?: NewsListParams): Promise<ApiResult<NewsListPayload>>
  article(id: string): Promise<ApiResult<NewsArticle | null>>
  rememberRefreshTime(at?: number): void
  shouldRefreshToday(now?: number): boolean
  isHomeFavorite(): boolean
  setHomeFavorite(selected: boolean): void
  savedArticleIds(): readonly string[]
  setArticleSaved(articleId: string, selected: boolean): readonly string[]
}

function storedBoolean(value: unknown): boolean {
  return value === true || value === 'true' || value === 1 || value === '1'
}

function storedStringList(value: unknown): readonly string[] {
  let candidate = value
  if (typeof value === 'string') {
    try {
      candidate = JSON.parse(value)
    } catch {
      return []
    }
  }
  if (!Array.isArray(candidate)) return []
  return [...new Set(candidate.map(cleanString).filter(Boolean))]
}

export function createNewsClient(
  transport: ApiTransport,
  storage: StorageAdapter = taroStorage,
): NewsClient {
  return {
    async home(refreshMode = 'manual') {
      const result = await transport.requestEndpoint('news.home', '/api/news/home', {
        attachAnalyticsHeaders: false,
        fallback: () => fallbackHome(refreshMode),
        validate: isReadyNewsHomePayload,
      })
      const withMetrics = await supplementLiveHomeMetrics(transport, result)
      return supplementLiveHomeHighlights(transport, withMetrics)
    },
    list(params = {}) {
      const query: Required<NewsListParams> = {
        type: params.type ?? 'metric',
        key: params.key ?? 'today',
        value: params.value ?? '',
      }
      const encoded = encodeQuery(query)
      return transport.requestEndpoint('news.list', `/api/news/list?${encoded}`, {
        attachAnalyticsHeaders: false,
        fallback: () => fallbackList(query),
        validate: isReadyNewsList,
      })
    },
    article(id) {
      return transport.requestEndpoint('news.article', `/api/news/article?id=${encodeURIComponent(id)}`, {
        attachAnalyticsHeaders: false,
        fallback: () => null,
        validate: (value) => isRecord(value) && isReadyNewsArticle(value['article'] ?? value),
      }).then((result) => {
        if (!result.fromFallback && isRecord(result.payload) && 'article' in result.payload) {
          return { ...result, payload: result.payload['article'] as NewsArticle }
        }
        return result as ApiResult<NewsArticle | null>
      })
    },
    rememberRefreshTime(at = Date.now()) {
      storage.set(storageKey('news.lastRefreshedAt'), String(at))
    },
    shouldRefreshToday(now = Date.now()) {
      const last = Number(storage.get<string | number>(storageKey('news.lastRefreshedAt')) ?? 0)
      if (!last) return true
      return new Date(last).toDateString() !== new Date(now).toDateString()
    },
    isHomeFavorite() {
      return storedBoolean(storage.get(storageKey('news.homeFavorite')))
    },
    setHomeFavorite(selected) {
      storage.set(storageKey('news.homeFavorite'), selected)
    },
    savedArticleIds() {
      return storedStringList(storage.get(storageKey('news.savedArticleIds')))
    },
    setArticleSaved(articleId, selected) {
      const cleanId = cleanString(articleId)
      const current = new Set(storedStringList(storage.get(storageKey('news.savedArticleIds'))))
      if (cleanId) {
        if (selected) current.add(cleanId)
        else current.delete(cleanId)
      }
      const next = [...current]
      storage.set(storageKey('news.savedArticleIds'), JSON.stringify(next))
      return next
    },
  }
}
