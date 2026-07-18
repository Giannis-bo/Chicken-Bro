import { describe, expect, it } from 'vitest'

import type { NewsArticle, NewsHomePayload } from '@wow-mini/domain'

import { buildNewsHomeModel, formatNewsHomeDate } from './news-home-model'

function article(id: string, sourceName = 'Blizzard News'): NewsArticle {
  return {
    id,
    title: `资讯 ${id}`,
    summary: `摘要 ${id}`,
    channel: '正式服动态',
    category: '正式服',
    sourceName,
    sourceUrl: `https://worldofwarcraft.blizzard.com/news/${id}`,
    publishedAt: '2026-07-13',
    contentStatus: 'ready',
    verificationStatus: 'official_verified',
    sourceTier: 'official',
  }
}

function payload(): NewsHomePayload {
  const articles = [article('a'), article('b'), article('c'), article('d'), article('e')]
  return {
    navTitle: '最新资讯',
    heroNews: articles.slice(0, 3),
    metrics: [
      { key: 'events', label: '活动', value: 3 },
      { key: 'today', label: '今日更新', value: 33 },
      { key: 'class-change', label: '职业变动', value: 2 },
      { key: 'updates', label: '更新', value: 7 },
    ],
    channels: [],
    highlights: articles,
    lastRefreshedAt: '2026-07-13 08:00:01+08:00',
    refreshMode: 'scheduled',
  }
}

describe('news home target model', () => {
  it('locks the target slot counts and maps metrics by key', () => {
    const model = buildNewsHomeModel({
      payload: payload(),
      routeState: 'ready',
      homeFavorite: false,
      savedArticleIds: ['d'],
    })

    expect(model.daily.metrics.map((metric) => [metric.label, metric.value])).toEqual([
      ['要闻', '33'],
      ['更新', '7'],
      ['平衡', '2'],
      ['活动', '3'],
    ])
    expect(model.channels.map((channel) => channel.label)).toEqual(['综合', '职业', '大秘', '装备', '系统', '更多'])
    expect(model.carousel.visualSlotCount).toBe(5)
    expect(model.carousel.items).toHaveLength(3)
    expect(model.feed).toHaveLength(2)
    expect(model.feed[0]?.id).toBe('d')
    expect(model.feed[0]?.saved).toBe(true)
    expect(model.carousel.items[0]?.sourceLabel).toBe('Blizzard News')
    expect(model.headerStatusLabel).toBe('已更新')
    expect(model.feed.every((item) => !model.carousel.items.some((hero) => hero.id === item.id))).toBe(true)
  })

  it('keeps stale data visible without claiming current official readiness', () => {
    const model = buildNewsHomeModel({
      payload: payload(),
      routeState: 'stale',
      homeFavorite: true,
      savedArticleIds: [],
    })

    expect(model.initialLoading).toBe(false)
    expect(model.headerStatusLabel).toBe('缓存可用')
    expect(model.daily.statusLabel).toBe('缓存可用')
    expect(model.carousel.items.every((item) => item.stateLabel === '缓存可用')).toBe(true)
    expect(model.carousel.items[0]?.sourceLabel).toBe('Blizzard News')
  })

  it('uses one composition when refreshing previous data', () => {
    const model = buildNewsHomeModel({
      payload: payload(),
      routeState: 'loading',
      homeFavorite: false,
      savedArticleIds: [],
    })

    expect(model.initialLoading).toBe(false)
    expect(model.refreshing).toBe(true)
    expect(model.feed).toHaveLength(2)
    expect(model.headerStatusLabel).toBe('更新中')
  })

  it('preserves honest unavailable slots before the first response', () => {
    const model = buildNewsHomeModel({
      routeState: 'loading',
      homeFavorite: false,
      savedArticleIds: [],
    })

    expect(model.initialLoading).toBe(true)
    expect(model.daily.metrics).toHaveLength(4)
    expect(model.daily.metrics.every((metric) => metric.value === '--' && !metric.available)).toBe(true)
    expect(model.carousel.items).toEqual([])
    expect(model.feed).toEqual([])
    expect(model.daily.sourceLabel).toBe('来源参考：暂不可用')
  })

  it('derives one aggregate source count and a stable date label', () => {
    const data = payload()
    data.heroNews = [article('a', 'Blizzard News'), article('b', 'Blizzard Forums')]
    data.highlights = [article('c', 'Blizzard News')]
    const model = buildNewsHomeModel({
      payload: data,
      routeState: 'ready',
      homeFavorite: false,
      savedArticleIds: [],
    })

    expect(model.daily.sourceLabel).toBe('来源参考：2 个官方渠道')
    expect(model.daily.dateLabel).toBe('07月13日')
    expect(formatNewsHomeDate('not-a-date')).toBe('--月--日')
  })

  it('derives aggregate trust only from distinct articles visible in the target slots', () => {
    const data = payload()
    data.heroNews = [article('a'), article('a'), article('b')]
    data.highlights = [
      article('a'),
      article('c'),
      article('d'),
      article('e'),
      article('f'),
      article('hidden', 'Hidden Official Source'),
    ]
    const model = buildNewsHomeModel({
      payload: data,
      routeState: 'ready',
      homeFavorite: false,
      savedArticleIds: [],
    })

    expect(model.carousel.items.map((item) => item.id)).toEqual(['a', 'b'])
    expect(model.feed.map((item) => item.id)).toEqual(['c', 'd', 'e', 'f'])
    expect(model.daily.sourceLabel).toBe('来源参考：1 个官方渠道')
  })

  it('uses a complete first sentence for the fixed carousel summary slot', () => {
    const data = payload()
    data.heroNews = data.heroNews.map((item, index) => index === 0 ? {
      ...item,
      summary: '第一句是可独立阅读的真实摘要。第二句保留在详情页。',
    } : item)
    const model = buildNewsHomeModel({
      payload: data,
      routeState: 'ready',
      homeFavorite: false,
      savedArticleIds: [],
    })

    expect(model.carousel.items[0]?.summary).toBe('第一句是可独立阅读的真实摘要。')
  })

  it('keeps the source title while deriving a truthful compact carousel title', () => {
    const data = payload()
    data.heroNews = data.heroNews.map((item, index) => index === 0 ? {
      ...item,
      title: '反馈：午夜第二赛季地下城测试（7月2日至7月6日）',
    } : item)
    const model = buildNewsHomeModel({
      payload: data,
      routeState: 'ready',
      homeFavorite: false,
      savedArticleIds: [],
    })

    expect(model.carousel.items[0]?.title).toBe('反馈：午夜第二赛季地下城测试（7月2日至7月6日）')
    expect(model.carousel.items[0]?.displayTitle).toBe('午夜第二赛季地下城测试')
  })

  it('fits long mixed-language fallback copy into the fixed carousel text rails', () => {
    const data = payload()
    data.heroNews = data.heroNews.map((item, index) => index === 0 ? {
      ...item,
      title: 'Midnight: Revelations 内容更新将于 6 月 16 日上线',
      summary: '官方公布 Midnight: Revelations 更新：新区域、全能典籍、单 Boss 团本 Sporefall、Turbulent Timeways 和后续故事章节。',
    } : item)
    const model = buildNewsHomeModel({
      payload: data,
      routeState: 'stale',
      homeFavorite: false,
      savedArticleIds: [],
    })

    expect(model.carousel.items[0]?.title).toBe('Midnight: Revelations 内容更新将于 6 月 16 日上线')
    expect(model.carousel.items[0]?.displayTitle).toMatch(/…$/u)
    expect(model.carousel.items[0]?.summary).toMatch(/…$/u)
  })
})
