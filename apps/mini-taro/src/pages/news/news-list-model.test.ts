import { describe, expect, it } from 'vitest'

import type { NewsArticle, NewsListPayload } from '@wow-mini/domain'

import {
  articleMatchesNewsCategory,
  buildNewsListModel,
  formatNewsListDate,
  type NewsListCategoryId,
} from './news-list-model'

function article(id: string, overrides: Partial<NewsArticle> = {}): NewsArticle {
  return {
    id,
    title: `资讯 ${id}`,
    summary: `摘要 ${id}`,
    channel: '正式服动态',
    category: '正式服',
    sourceName: 'Blizzard News',
    sourceUrl: `https://worldofwarcraft.blizzard.com/news/${id}`,
    publishedAt: `2026-07-${String(Number(id.replace(/\D/gu, '')) || 1).padStart(2, '0')}`,
    contentStatus: 'ready',
    verificationStatus: 'official_verified',
    sourceTier: 'official',
    sourceBadges: ['官方已核验'],
    ...overrides,
  }
}

function payload(articles: readonly NewsArticle[]): NewsListPayload {
  return {
    title: '今日更新',
    type: 'metric',
    key: 'today',
    value: '',
    count: articles.length,
    articles,
  }
}

function build(overrides: Partial<Parameters<typeof buildNewsListModel>[0]> = {}) {
  return buildNewsListModel({
    payload: payload(Array.from({ length: 8 }, (_, index) => article(`a${index + 1}`))),
    routeState: 'ready',
    activeCategory: 'all',
    sortDirection: 'newest',
    visibleCount: 6,
    ...overrides,
  })
}

describe('news list target model', () => {
  it('locks the six target categories and initial visible window', () => {
    const model = build()

    expect(model.categories.map((category) => category.label)).toEqual(['全部', '官方', '蓝贴', '更新', '活动', '社区'])
    expect(model.visibleRowSlotCount).toBe(6)
    expect(model.items).toHaveLength(6)
    expect(model.countLabel).toBe('共 8 条')
    expect(model.terminal).toMatchObject({ mode: 'more', title: '还有 2 条资讯', action: 'load_more' })
  })

  it('classifies categories only from explicit article fields', () => {
    const samples: Readonly<Record<NewsListCategoryId, NewsArticle>> = {
      all: article('1'),
      official: article('2', { verificationStatus: 'unknown', sourceTier: 'community', sourceBadges: ['官方已核验'] }),
      blue_post: article('3', { sourceName: 'Blizzard Forums' }),
      updates: article('4', { tags: ['hotfix'], verificationStatus: 'unknown', sourceTier: 'unknown', sourceBadges: [] }),
      events: article('5', { tagItems: [{ id: 'weekly', label: '周报' }], verificationStatus: 'unknown', sourceTier: 'unknown', sourceBadges: [] }),
      community: article('6', { sourceName: 'Wowhead', sourceTier: 'community', verificationStatus: 'unknown', sourceBadges: [] }),
    }

    for (const [category, candidate] of Object.entries(samples)) {
      expect(articleMatchesNewsCategory(candidate, category as NewsListCategoryId)).toBe(true)
    }
    expect(articleMatchesNewsCategory(article('7'), 'blue_post')).toBe(false)
    expect(articleMatchesNewsCategory(article('8'), 'community')).toBe(false)
  })

  it('labels LLM translation honestly and never turns it into human translation', () => {
    const model = build({
      payload: payload([article('1', { translationStatus: 'llm' })]),
    })

    expect(model.items[0]).toMatchObject({ status: 'source_reference', statusLabel: '机器翻译' })
    expect(model.items[0]?.statusLabel).not.toBe('已翻译')
  })

  it('blocks only the source affordance when sourceUrl is absent', () => {
    const model = build({
      payload: payload([article('1', { sourceUrl: '' })]),
    })

    expect(model.items[0]).toMatchObject({ sourceAvailable: false, sourceLabel: '来源不可用', status: 'blocked' })
  })

  it('uses absolute source dates and stable chronological sorting', () => {
    const data = payload([
      article('1', { publishedAt: '2026-07-02T12:00:00Z' }),
      article('2', { publishedAt: '2026-07-14T12:00:00Z' }),
    ])
    const newest = build({ payload: data })
    const oldest = build({ payload: data, sortDirection: 'oldest' })

    expect(newest.items.map((item) => item.id)).toEqual(['2', '1'])
    expect(oldest.items.map((item) => item.id)).toEqual(['1', '2'])
    expect(newest.items[0]?.dateLabel).toBe('07月14日')
    expect(formatNewsListDate('刚刚')).toBe('日期待核验')
  })

  it('keeps all regions honest during the first load', () => {
    const model = buildNewsListModel({
      routeState: 'loading',
      activeCategory: 'all',
      sortDirection: 'newest',
      visibleCount: 6,
    })

    expect(model.initialLoading).toBe(true)
    expect(model.categories).toHaveLength(6)
    expect(model.items).toEqual([])
    expect(model.countLabel).toBe('共 -- 条')
    expect(model.terminal).toMatchObject({ mode: 'loading', action: 'none' })
  })

  it('uses the terminal panel for complete, empty and filtered-empty states', () => {
    const complete = build({ payload: payload([article('1')]) })
    const empty = build({ payload: payload([]) })
    const filteredEmpty = build({ activeCategory: 'community' })

    expect(complete.terminal).toMatchObject({ mode: 'complete', action: 'refresh' })
    expect(empty.terminal).toMatchObject({ mode: 'empty', action: 'refresh' })
    expect(filteredEmpty.terminal).toMatchObject({ mode: 'empty', action: 'reset_filter' })
  })

  it('preserves previous rows while reporting refresh failure', () => {
    const model = build({ routeState: 'error', routeReason: 'network down' })

    expect(model.items).toHaveLength(6)
    expect(model.items.every((item) => item.statusLabel === '缓存可用')).toBe(true)
    expect(model.terminal).toMatchObject({ mode: 'error', detail: 'network down', action: 'retry' })
  })
})
