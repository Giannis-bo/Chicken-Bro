import type { NewsArticle, NewsHomePayload, ReadinessState } from '@wow-mini/domain'

export interface NewsHomeQuery {
  type: 'metric'
  key: string
}

export interface NewsHomeMetricView {
  id: 'headline' | 'updates' | 'balance' | 'events'
  label: string
  value: string
  glyphAssetId: string
  fallbackGlyphAssetId: string
  query: NewsHomeQuery
  available: boolean
}

export interface NewsHomeChannelView {
  id: string
  label: string
  glyphAssetId: string
  fallbackGlyphAssetId: string
  query: NewsHomeQuery
}

export interface NewsHomeArticleView {
  id: string
  title: string
  displayTitle: string
  summary: string
  sourceLabel: string
  state: ReadinessState
  stateLabel: string
  mediaSource?: string
  saved?: boolean
}

export interface NewsHomeViewModel {
  title: string
  headerSourceLabel: string
  headerStatusLabel: string
  homeFavorite: boolean
  initialLoading: boolean
  refreshing: boolean
  retryAvailable: boolean
  daily: {
    dateLabel: string
    statusLabel: string
    sourceLabel: string
    metrics: readonly NewsHomeMetricView[]
  }
  carousel: {
    items: readonly NewsHomeArticleView[]
    visualSlotCount: 5
  }
  channels: readonly NewsHomeChannelView[]
  feed: readonly NewsHomeArticleView[]
}

export interface BuildNewsHomeModelInput {
  payload?: NewsHomePayload
  routeState: ReadinessState
  homeFavorite: boolean
  savedArticleIds: readonly string[]
}

const metricSlots = [
  { id: 'headline', label: '要闻', key: 'today', glyphAssetId: 'news-metric-glyph.headline', fallbackGlyphAssetId: 'utility-glyph-family.document' },
  { id: 'updates', label: '更新', key: 'updates', glyphAssetId: 'news-metric-glyph.updates', fallbackGlyphAssetId: 'utility-glyph-family.warning' },
  { id: 'balance', label: '平衡', key: 'class-change', glyphAssetId: 'news-metric-glyph.balance', fallbackGlyphAssetId: 'utility-glyph-family.adjust' },
  { id: 'events', label: '活动', key: 'events', glyphAssetId: 'news-metric-glyph.events', fallbackGlyphAssetId: 'utility-glyph-family.runtime' },
] as const

const channelSlots: readonly NewsHomeChannelView[] = [
  { id: 'all', label: '综合', glyphAssetId: 'news-channel-glyph.all', fallbackGlyphAssetId: 'utility-glyph-family.records', query: { type: 'metric', key: 'today' } },
  { id: 'class', label: '职业', glyphAssetId: 'news-channel-glyph.class', fallbackGlyphAssetId: 'utility-glyph-family.adjust', query: { type: 'metric', key: 'class-change' } },
  { id: 'mythic-plus', label: '大秘', glyphAssetId: 'news-channel-glyph.mythic', fallbackGlyphAssetId: 'utility-glyph-family.runtime', query: { type: 'metric', key: 'mythic-plus' } },
  { id: 'gear', label: '装备', glyphAssetId: 'news-channel-glyph.gear', fallbackGlyphAssetId: 'quick-action-gear-glyph.default', query: { type: 'metric', key: 'gear' } },
  { id: 'system', label: '系统', glyphAssetId: 'news-channel-glyph.system', fallbackGlyphAssetId: 'utility-glyph-family.shield', query: { type: 'metric', key: 'system' } },
  { id: 'more', label: '更多', glyphAssetId: 'news-channel-glyph.more', fallbackGlyphAssetId: 'utility-glyph-family.topic', query: { type: 'metric', key: 'today' } },
]

function distinctArticles(
  articles: readonly NewsArticle[],
  excludedIds: ReadonlySet<string> = new Set<string>(),
): readonly NewsArticle[] {
  const result: NewsArticle[] = []
  const ids = new Set(excludedIds)
  for (const article of articles) {
    if (!article.id || ids.has(article.id)) continue
    ids.add(article.id)
    result.push(article)
  }
  return result
}

function isOfficialReady(article: NewsArticle): boolean {
  return article.verificationStatus === 'official_verified'
    && article.sourceTier === 'official'
    && article.contentStatus === 'ready'
}

function routeStatusLabel(state: ReadinessState, allOfficial: boolean): string {
  if (state === 'loading') return '更新中'
  if (state === 'stale') return '本地回退'
  if (state === 'error' || state === 'blocked' || state === 'empty') return '不可用'
  return allOfficial ? '已更新' : '待核验'
}

function dailyStatusLabel(state: ReadinessState): string {
  if (state === 'loading') return '更新中'
  if (state === 'stale') return '本地回退'
  if (state === 'error' || state === 'blocked') return '更新失败'
  if (state === 'empty') return '暂无内容'
  if (state === 'partial') return '部分可用'
  return '已更新'
}

function articleState(article: NewsArticle, routeState: ReadinessState): Pick<NewsHomeArticleView, 'state' | 'stateLabel'> {
  if (routeState === 'stale') return { state: 'stale', stateLabel: '本地回退' }
  if (isOfficialReady(article)) return { state: 'ready', stateLabel: '已核验' }
  return { state: 'source_reference', stateLabel: '待核验' }
}

function compactSummary(value: string): string {
  const normalized = value.replace(/\s+/g, ' ').trim()
  const firstSentence = normalized.match(/^.*?[。！？!?](?:[”’」』])?/u)?.[0]
  return fitSingleLine(firstSentence ?? normalized, 31)
}

function compactCarouselTitle(value: string): string {
  const normalized = value.replace(/\s+/g, ' ').trim()
  const withoutPrefix = normalized.replace(/^(?:反馈|提醒|预告|更新)\s*[：:]\s*/u, '')
  const withoutDateRange = withoutPrefix.replace(/[（(][^（）()]{1,24}[）)]\s*$/u, '').trim()
  return fitSingleLine(withoutDateRange || normalized, 17.5)
}

function characterWidthUnits(character: string): number {
  if (/\s/u.test(character)) return 0.35
  if ((character.codePointAt(0) ?? 0) <= 0xff) {
    if (/^[ilI.,:;'|!]$/u.test(character)) return 0.3
    if (/^[MW@#%&]$/u.test(character)) return 0.85
    return 0.56
  }
  return 1
}

function fitSingleLine(value: string, maximumUnits: number): string {
  const characters = Array.from(value)
  const totalUnits = characters.reduce((sum, character) => sum + characterWidthUnits(character), 0)
  if (totalUnits <= maximumUnits) return value

  const ellipsisUnits = characterWidthUnits('…')
  let usedUnits = 0
  let result = ''
  for (const character of characters) {
    const units = characterWidthUnits(character)
    if (usedUnits + units + ellipsisUnits > maximumUnits) break
    result += character
    usedUnits += units
  }
  return `${result.trimEnd()}…`
}

function articleView(article: NewsArticle, routeState: ReadinessState, saved: boolean): NewsHomeArticleView {
  return {
    id: article.id,
    title: article.title,
    displayTitle: compactCarouselTitle(article.title),
    summary: compactSummary(article.summary),
    sourceLabel: article.sourceName || '',
    ...articleState(article, routeState),
    ...(article.imageUrl ? { mediaSource: article.imageUrl } : {}),
    ...(saved ? { saved: true } : {}),
  }
}

export function formatNewsHomeDate(value: string | undefined): string {
  const match = value?.match(/\b\d{4}-(\d{2})-(\d{2})\b/)
  return match ? `${match[1]}月${match[2]}日` : '--月--日'
}

export function buildNewsHomeModel({
  payload,
  routeState,
  homeFavorite,
  savedArticleIds,
}: BuildNewsHomeModelInput): NewsHomeViewModel {
  const heroArticles = distinctArticles(payload?.heroNews ?? []).slice(0, 3)
  const heroIds = new Set(heroArticles.map((article) => article.id))
  const feedArticles = distinctArticles(payload?.highlights ?? [], heroIds).slice(0, 4)
  const visibleArticles = [...heroArticles, ...feedArticles]
  const allOfficial = visibleArticles.length > 0 && visibleArticles.every(isOfficialReady)
  const officialSources = new Set(
    visibleArticles.filter(isOfficialReady).map((article) => article.sourceName).filter(Boolean),
  )
  const metricsByKey = new Map((payload?.metrics ?? []).map((metric) => [metric.key, metric.value]))
  const savedIds = new Set(savedArticleIds)
  const initialLoading = routeState === 'loading' && !payload

  return {
    title: payload?.navTitle || '最新资讯',
    headerSourceLabel: '来源参考',
    headerStatusLabel: routeStatusLabel(routeState, allOfficial),
    homeFavorite,
    initialLoading,
    refreshing: routeState === 'loading' && Boolean(payload),
    retryAvailable: (routeState === 'error' || routeState === 'blocked') && !payload,
    daily: {
      dateLabel: formatNewsHomeDate(payload?.lastRefreshedAt),
      statusLabel: dailyStatusLabel(routeState),
      sourceLabel: officialSources.size
        ? `来源参考：${officialSources.size} 个官方渠道`
        : '来源参考：暂不可用',
      metrics: metricSlots.map((slot) => {
        const value = metricsByKey.get(slot.key)
        return {
          id: slot.id,
          label: slot.label,
          value: value === undefined || value === null || value === '' ? '--' : String(value),
          glyphAssetId: slot.glyphAssetId,
          fallbackGlyphAssetId: slot.fallbackGlyphAssetId,
          query: { type: 'metric', key: slot.key },
          available: value !== undefined && value !== null && value !== '',
        }
      }),
    },
    carousel: {
      items: heroArticles.map((article) => articleView(article, routeState, savedIds.has(article.id))),
      visualSlotCount: 5,
    },
    channels: channelSlots,
    feed: feedArticles.map((article) => articleView(article, routeState, savedIds.has(article.id))),
  }
}
