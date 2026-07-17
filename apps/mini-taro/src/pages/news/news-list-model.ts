import type { NewsArticle, NewsListPayload, ReadinessState } from '@wow-mini/domain'

import { cachedDataPresentation } from '../_shared/data-presentation'

export type NewsListCategoryId = 'all' | 'official' | 'blue_post' | 'updates' | 'events' | 'community'
export type NewsListSortDirection = 'newest' | 'oldest'
export type NewsListTerminalMode = 'loading' | 'more' | 'complete' | 'empty' | 'error' | 'blocked'

export interface NewsListCategoryView {
  id: NewsListCategoryId
  label: string
  count: number
}

export interface NewsListArticleView {
  id: string
  title: string
  sourceLabel: string
  sourceAvailable: boolean
  status: ReadinessState
  statusLabel: string
  dateLabel: string
  accent: 'blue' | 'gold'
}

export interface NewsListTerminalView {
  mode: NewsListTerminalMode
  title: string
  detail: string
  actionLabel?: string
  action: 'none' | 'load_more' | 'refresh' | 'reset_filter' | 'retry'
}

export interface NewsListViewModel {
  title: string
  countLabel: string
  stateLabel: string
  initialLoading: boolean
  refreshing: boolean
  categories: readonly NewsListCategoryView[]
  activeCategory: NewsListCategoryId
  sortDirection: NewsListSortDirection
  sortLabel: string
  items: readonly NewsListArticleView[]
  filteredCount: number
  visibleRowSlotCount: 6
  terminal: NewsListTerminalView
}

export interface BuildNewsListModelInput {
  payload?: NewsListPayload
  routeState: ReadinessState
  activeCategory: NewsListCategoryId
  sortDirection: NewsListSortDirection
  visibleCount: number
  fallbackTitle?: string
  routeReason?: string
}

const categoryDefinitions: readonly Pick<NewsListCategoryView, 'id' | 'label'>[] = [
  { id: 'all', label: '全部' },
  { id: 'official', label: '官方' },
  { id: 'blue_post', label: '蓝贴' },
  { id: 'updates', label: '更新' },
  { id: 'events', label: '活动' },
  { id: 'community', label: '社区' },
]

const updateTags = new Set(['content-update', 'hotfix', 'patch', 'ptr', 'class-change'])
const eventTags = new Set(['event', 'trading-post', 'weekly', 'rewards'])
const targetAccentPattern = ['blue', 'blue', 'gold', 'blue', 'gold', 'gold'] as const

function normalizedValues(values: readonly (string | undefined)[]): readonly string[] {
  return values
    .filter((value): value is string => Boolean(value?.trim()))
    .map((value) => value.trim().toLowerCase())
}

function articleTags(article: NewsArticle): ReadonlySet<string> {
  return new Set(normalizedValues([
    ...(article.tags ?? []),
    ...(article.tagItems ?? []).flatMap((tag) => [tag.id, tag.label]),
  ]))
}

function hasAny(tags: ReadonlySet<string>, candidates: ReadonlySet<string>): boolean {
  return [...candidates].some((candidate) => tags.has(candidate))
}

export function isExplicitlyOfficial(article: NewsArticle): boolean {
  return article.verificationStatus === 'official_verified'
    || article.sourceTier === 'official'
    || normalizedValues(article.sourceBadges ?? []).includes('官方已核验')
}

function isCommunity(article: NewsArticle, tags: ReadonlySet<string>): boolean {
  if (article.sourceTier === 'community' || tags.has('community') || tags.has('社区')) return true
  const communityEvidence = normalizedValues([
    article.channel,
    article.category,
    ...(article.sourceBadges ?? []),
  ]).some((value) => value.includes('community') || value.includes('社区'))
  return communityEvidence && !article.sourceName.toLowerCase().includes('blizzard')
}

export function articleMatchesNewsCategory(article: NewsArticle, category: NewsListCategoryId): boolean {
  if (category === 'all') return true
  if (category === 'official') return isExplicitlyOfficial(article)
  if (category === 'blue_post') return article.sourceName.trim().toLowerCase() === 'blizzard forums'
  const tags = articleTags(article)
  if (category === 'updates') return hasAny(tags, updateTags)
  if (category === 'events') return hasAny(tags, eventTags)
  return isCommunity(article, tags)
}

function publishedTimestamp(value: string): number {
  const timestamp = Date.parse(value)
  return Number.isFinite(timestamp) ? timestamp : 0
}

export function formatNewsListDate(value: string): string {
  const match = value.match(/\b\d{4}-(\d{2})-(\d{2})(?=$|[T\s])/u)
  return match ? `${match[1]}月${match[2]}日` : '日期待核验'
}

function articleStatus(article: NewsArticle, routeState: ReadinessState): Pick<NewsListArticleView, 'status' | 'statusLabel'> {
  if (routeState === 'stale' || routeState === 'error') return { status: 'stale', statusLabel: cachedDataPresentation.stateLabel }
  if (!article.sourceUrl.trim()) return { status: 'blocked', statusLabel: '来源不可用' }
  if (article.translationStatus === 'llm') return { status: 'source_reference', statusLabel: '机器翻译' }
  if (article.translationStatus) return { status: 'source_reference', statusLabel: '翻译待核验' }
  if (isExplicitlyOfficial(article)) return { status: 'ready', statusLabel: '已核验' }
  return { status: 'source_reference', statusLabel: '待核验' }
}

function routeStateLabel(state: ReadinessState, hasPayload: boolean): string {
  if (state === 'loading') return hasPayload ? '刷新中' : '读取中'
  if (state === 'stale') return cachedDataPresentation.stateLabel
  if (state === 'error') return hasPayload ? '刷新失败' : '请求失败'
  if (state === 'blocked') return '请求受限'
  if (state === 'empty') return '暂无内容'
  if (state === 'partial') return '部分可用'
  return '已更新'
}

function terminalView(
  routeState: ReadinessState,
  hasPayload: boolean,
  filteredCount: number,
  visibleCount: number,
  activeCategory: NewsListCategoryId,
  routeReason: string | undefined,
): NewsListTerminalView {
  if (routeState === 'loading') {
    return {
      mode: 'loading',
      title: hasPayload ? '正在刷新资讯' : '正在同步资讯',
      detail: hasPayload ? '当前内容暂时保留' : '正在读取真实来源',
      action: 'none',
    }
  }
  if (routeState === 'blocked') {
    return {
      mode: 'blocked',
      title: '当前资讯请求受限',
      detail: routeReason || '请稍后重试当前查询',
      actionLabel: '重试',
      action: 'retry',
    }
  }
  if (routeState === 'error') {
    return {
      mode: 'error',
      title: hasPayload ? '刷新失败' : '资讯加载失败',
      detail: routeReason || (hasPayload ? '当前显示上次可用内容' : '请重试当前查询'),
      actionLabel: '重试',
      action: 'retry',
    }
  }
  if (filteredCount === 0) {
    return {
      mode: 'empty',
      title: '暂无符合条件的资讯',
      detail: activeCategory === 'all' ? '当前查询没有返回可用内容' : '可以重置分类查看全部结果',
      actionLabel: activeCategory === 'all' ? '刷新' : '重置筛选',
      action: activeCategory === 'all' ? 'refresh' : 'reset_filter',
    }
  }
  const remaining = Math.max(0, filteredCount - visibleCount)
  if (remaining > 0) {
    return {
      mode: 'more',
      title: `还有 ${remaining} 条资讯`,
      detail: routeState === 'stale' ? cachedDataPresentation.contentDetail : '继续加载当前分类的下一组内容',
      actionLabel: '加载更多',
      action: 'load_more',
    }
  }
  return {
    mode: 'complete',
    title: `已显示全部 ${filteredCount} 条资讯`,
    detail: routeState === 'stale' ? cachedDataPresentation.contentDetail : '列表已到末尾',
    actionLabel: '刷新',
    action: 'refresh',
  }
}

export function buildNewsListModel({
  payload,
  routeState,
  activeCategory,
  sortDirection,
  visibleCount,
  fallbackTitle,
  routeReason,
}: BuildNewsListModelInput): NewsListViewModel {
  const articles = payload?.articles ?? []
  const filtered = articles.filter((article) => articleMatchesNewsCategory(article, activeCategory))
  const sorted = filtered.map((article, index) => ({ article, index })).sort((left, right) => {
    const difference = publishedTimestamp(right.article.publishedAt) - publishedTimestamp(left.article.publishedAt)
    const directed = sortDirection === 'newest' ? difference : -difference
    return directed || left.index - right.index
  }).map(({ article }) => article)
  const normalizedVisibleCount = Math.max(6, Math.floor(visibleCount / 6) * 6)
  const visibleArticles = sorted.slice(0, normalizedVisibleCount)
  const hasPayload = Boolean(payload)
  const initialLoading = routeState === 'loading' && !payload

  return {
    title: payload?.title || fallbackTitle || '资讯列表',
    countLabel: payload ? `共 ${filtered.length} 条` : '共 -- 条',
    stateLabel: routeStateLabel(routeState, hasPayload),
    initialLoading,
    refreshing: routeState === 'loading' && hasPayload,
    categories: categoryDefinitions.map((category) => ({
      ...category,
      count: articles.filter((article) => articleMatchesNewsCategory(article, category.id)).length,
    })),
    activeCategory,
    sortDirection,
    sortLabel: sortDirection === 'newest' ? '最新优先' : '最早优先',
    items: visibleArticles.map((article, index) => ({
      id: article.id,
      title: article.title,
      sourceLabel: article.sourceUrl.trim() ? (article.sourceName.trim() || '来源参考') : '来源不可用',
      sourceAvailable: Boolean(article.sourceUrl.trim()),
      ...articleStatus(article, routeState),
      dateLabel: formatNewsListDate(article.publishedAt),
      accent: targetAccentPattern[index % targetAccentPattern.length] ?? 'blue',
    })),
    filteredCount: filtered.length,
    visibleRowSlotCount: 6,
    terminal: terminalView(
      routeState,
      hasPayload,
      filtered.length,
      visibleArticles.length,
      activeCategory,
      routeReason,
    ),
  }
}
