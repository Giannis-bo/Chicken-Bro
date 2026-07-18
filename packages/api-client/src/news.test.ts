import { describe, expect, it, vi } from 'vitest'

vi.mock('@tarojs/taro', () => ({
  default: {
    getStorageSync: vi.fn(),
    setStorageSync: vi.fn(),
    removeStorageSync: vi.fn(),
  },
}))

import { storageKey, type NewsArticle } from '@wow-mini/domain'

import { createNewsClient, isNewsHomeVisuallyEmpty, isReadyNewsHomePayload } from './news'
import { newsFallbackSnapshot } from './fallback-snapshots'
import type { StorageAdapter } from './storage'
import type { ApiTransport, RequestOptions } from './transport'

class MemoryStorage implements StorageAdapter {
  readonly values = new Map<string, unknown>()

  get<T>(key: string): T | undefined { return this.values.get(key) as T | undefined }
  set<T>(key: string, value: T): void { this.values.set(key, value) }
  remove(key: string): void { this.values.delete(key) }
}

function fallbackTransport(): ApiTransport {
  const respond = async <T>(options: RequestOptions<T>) => ({
    payload: options.fallback(),
    fromFallback: true,
    error: 'offline',
  })
  return {
    request: (_path, options) => respond(options),
    requestEndpoint: (_endpoint, _path, options) => respond(options),
  }
}

function liveArticle(id: string): NewsArticle {
  const seed = newsFallbackSnapshot.heroNews[0]
  if (!seed) throw new Error('news fallback snapshot must include a hero article')
  return {
    ...seed,
    id,
    title: `资讯 ${id}`,
    originalTitle: `News ${id}`,
    sourceUrl: `https://worldofwarcraft.blizzard.com/news/${id}`,
  }
}

describe('news client target contract', () => {
  it('returns empty transport structures instead of packaged news facts when unavailable', async () => {
    const client = createNewsClient(fallbackTransport(), new MemoryStorage())

    const [home, list, article] = await Promise.all([
      client.home(),
      client.list({ type: 'metric', key: 'today' }),
      client.article('missing-article'),
    ])

    expect(home).toMatchObject({ fromFallback: true, payload: {
      heroNews: [], highlights: [], metrics: [], channels: [],
    } })
    expect(list).toMatchObject({ fromFallback: true, payload: { count: 0, articles: [] } })
    expect(article).toMatchObject({ fromFallback: true, payload: null })
  })

  it('rejects structurally incomplete home payloads before route rendering', () => {
    expect(isReadyNewsHomePayload(newsFallbackSnapshot)).toBe(true)
    expect(isReadyNewsHomePayload({ ...newsFallbackSnapshot, metrics: undefined })).toBe(false)
    expect(isReadyNewsHomePayload({ ...newsFallbackSnapshot, lastRefreshedAt: '' })).toBe(false)
    expect(isReadyNewsHomePayload({
      ...newsFallbackSnapshot,
      channels: [{ id: 'official', title: '', updateCount: 1 }],
    })).toBe(false)
  })

  it('accepts a canonical zero-article home payload and classifies its visual emptiness separately', () => {
    const canonicalEmpty = {
      ...newsFallbackSnapshot,
      heroNews: [],
      highlights: [],
    }
    expect(isReadyNewsHomePayload(canonicalEmpty)).toBe(true)
    expect(isNewsHomeVisuallyEmpty(canonicalEmpty)).toBe(true)
    expect(isNewsHomeVisuallyEmpty({
      ...canonicalEmpty,
      heroNews: [liveArticle('visible')],
    })).toBe(false)
    expect(isReadyNewsHomePayload({
      ...canonicalEmpty,
      heroNews: [{ ...liveArticle('invalid-article'), title: '' }],
    })).toBe(false)
    expect(isReadyNewsHomePayload({
      ...canonicalEmpty,
      metrics: [{ key: 'today', label: '', value: '0' }],
    })).toBe(false)
  })

  it('persists the home favorite and a normalized saved-article set', () => {
    const storage = new MemoryStorage()
    const client = createNewsClient(fallbackTransport(), storage)

    expect(client.isHomeFavorite()).toBe(false)
    client.setHomeFavorite(true)
    expect(client.isHomeFavorite()).toBe(true)

    expect(client.setArticleSaved('article-a', true)).toEqual(['article-a'])
    expect(client.setArticleSaved('article-a', true)).toEqual(['article-a'])
    expect(client.setArticleSaved('article-b', true)).toEqual(['article-a', 'article-b'])
    expect(client.setArticleSaved('article-a', false)).toEqual(['article-b'])
    expect(client.savedArticleIds()).toEqual(['article-b'])
  })

  it('recovers safely from malformed saved-article storage', () => {
    const storage = new MemoryStorage()
    storage.set(storageKey('news.savedArticleIds'), '{not json')
    const client = createNewsClient(fallbackTransport(), storage)

    expect(client.savedArticleIds()).toEqual([])
    expect(client.setArticleSaved('article-a', true)).toEqual(['article-a'])
  })

  it('keeps unavailable news lists empty instead of deriving metric facts', async () => {
    const client = createNewsClient(fallbackTransport(), new MemoryStorage())
    const home = await client.home()
    expect(home.payload.metrics).toEqual([])

    for (const key of ['updates', 'events'] as const) {
      const list = await client.list({ type: 'metric', key })
      expect(list.payload).toMatchObject({ key, count: 0, articles: [] })
    }
  })

  it('supports every fixed news-home category without semantic aliasing', async () => {
    const client = createNewsClient(fallbackTransport(), new MemoryStorage())
    const expectedTitles = {
      'mythic-plus': '大秘境',
      gear: '装备',
      system: '系统',
    } as const

    for (const [key, title] of Object.entries(expectedTitles)) {
      const result = await client.list({ type: 'metric', key })
      expect(result.payload.key).toBe(key)
      expect(result.payload.title).toBe(title)
    }
  })

  it('supplements missing live home metrics from the matching live list filters', async () => {
    const transport = {
      request: fallbackTransport().request,
      requestEndpoint: async (endpoint: string, path: string) => {
        if (endpoint === 'news.home') {
          return {
            payload: {
              ...newsFallbackSnapshot,
              metrics: newsFallbackSnapshot.metrics.filter((metric) => metric.key !== 'updates' && metric.key !== 'events'),
            },
            fromFallback: false,
            error: '',
          }
        }
        const key = new URL(`https://example.test${path}`).searchParams.get('key')
        return {
          payload: { title: '', type: 'metric', key: key ?? '', value: '', count: key === 'updates' ? 9 : 4, articles: [] },
          fromFallback: false,
          error: '',
        }
      },
    } as ApiTransport
    const client = createNewsClient(transport, new MemoryStorage())

    const result = await client.home()
    const metrics = Object.fromEntries(result.payload.metrics.map((metric) => [metric.key, Number(metric.value)]))

    expect(metrics['updates']).toBe(9)
    expect(metrics['events']).toBe(4)
  })

  it('keeps live highlights distinct from hero items and fills from the real today list', async () => {
    const articles = ['a', 'b', 'c', 'd', 'e', 'f', 'g'].map(liveArticle)
    const transport = {
      request: fallbackTransport().request,
      requestEndpoint: async (endpoint: string) => {
        if (endpoint === 'news.home') {
          return {
            payload: {
              ...newsFallbackSnapshot,
              heroNews: articles.slice(0, 3),
              highlights: articles.slice(0, 4),
            },
            fromFallback: false,
            error: '',
          }
        }
        return {
          payload: { title: '今日更新', type: 'metric', key: 'today', value: '', count: articles.length, articles },
          fromFallback: false,
          error: '',
        }
      },
    } as ApiTransport
    const client = createNewsClient(transport, new MemoryStorage())

    const result = await client.home()

    expect(result.payload.highlights.map((article) => article.id)).toEqual(['d', 'e', 'f', 'g'])
    expect(result.payload.highlights.some((article) => result.payload.heroNews.some((hero) => hero.id === article.id))).toBe(false)
  })
})
