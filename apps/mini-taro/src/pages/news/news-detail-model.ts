import type { NewsArticle, NewsBodyBlock, ReadinessState } from '@wow-mini/domain'

import { cachedDataPresentation } from '../_shared/data-presentation'

export type NewsDetailTranslationId = 'pending' | 'machine' | 'human'
export type NewsDetailTerminalMode = 'loading' | 'ready' | 'missing' | 'error' | 'blocked'
export type NewsDetailTerminalAction = 'none' | 'retry' | 'go_back'

export interface NewsDetailTranslationSegment {
  id: NewsDetailTranslationId
  label: string
  selected: boolean
}

export interface NewsDetailEvidenceRow {
  id: 'source' | 'translation' | 'published' | 'license'
  typeLabel: string
  summary: string
  statusLabel: string
  timeLabel: string
  state: ReadinessState
}

export interface NewsDetailTerminalView {
  mode: NewsDetailTerminalMode
  title: string
  detail: string
  action: NewsDetailTerminalAction
  actionLabel?: string
}

export interface NewsDetailViewModel {
  articleTitle: string
  sourceLabel: string
  sourceUrl: string
  sourceUrlLabel: string
  sourceAvailable: boolean
  heroState: ReadinessState
  heroStateLabel: string
  translationSegments: readonly NewsDetailTranslationSegment[]
  activeTranslationId: NewsDetailTranslationId
  bodyBlocks: readonly NewsBodyBlock[]
  evidenceRows: readonly NewsDetailEvidenceRow[]
  initialLoading: boolean
  refreshing: boolean
  terminal: NewsDetailTerminalView
}

export interface BuildNewsDetailModelInput {
  article?: NewsArticle
  routeState: ReadinessState
  routeReason?: string
}

const translationDefinitions: readonly Pick<NewsDetailTranslationSegment, 'id' | 'label'>[] = [
  { id: 'pending', label: '待翻译' },
  { id: 'machine', label: '机器翻译' },
  { id: 'human', label: '人工翻译' },
]

function clean(value: string | undefined): string {
  return value?.trim() ?? ''
}

function normalized(value: string | undefined): string {
  return clean(value).toLowerCase()
}

function isExplicitlyVerified(article: NewsArticle): boolean {
  return article.verificationStatus === 'official_verified'
    || article.sourceTier === 'official'
    || (article.sourceBadges ?? []).some((badge) => normalized(badge) === '官方已核验')
}

export function formatNewsDetailDate(value: string | undefined): string {
  const raw = clean(value)
  const match = raw.match(/\b(\d{4})-(\d{2})-(\d{2})(?=$|[T\s])/u)
  return match ? `${match[1]}年${match[2]}月${match[3]}日` : '日期未提供'
}

function formatNewsDetailCompactDate(value: string | undefined): string {
  const raw = clean(value)
  const match = raw.match(/\b\d{4}-(\d{2})-(\d{2})(?=$|[T\s])/u)
  return match ? `${match[1]}月${match[2]}日` : '未记录'
}

export function newsDetailTranslationId(status: string | undefined): NewsDetailTranslationId {
  const value = normalized(status)
  if (['human', 'manual', 'human_translation', 'translated_human'].includes(value)) return 'human'
  if (['llm', 'machine', 'machine_translation', 'translated_machine'].includes(value)) return 'machine'
  return 'pending'
}

function articleBodyBlocks(article: NewsArticle | undefined): readonly NewsBodyBlock[] {
  if (!article) return []
  if (article.bodyBlocksZh?.length) return article.bodyBlocksZh
  const paragraphs = clean(article.bodyZh)
    .split(/\n{2,}/u)
    .map((text) => text.trim())
    .filter(Boolean)
  if (paragraphs.length) return paragraphs.map((text) => ({ type: 'paragraph', text }))
  const summary = clean(article.summary)
  return summary ? [{ type: 'paragraph', text: summary }] : []
}

function sourceUrlLabel(value: string): string {
  if (!value) return '来源链接不可用'
  try {
    return new URL(value).hostname || '来源链接可复制'
  } catch {
    return '来源链接可复制'
  }
}

function heroState(
  article: NewsArticle | undefined,
  routeState: ReadinessState,
): Pick<NewsDetailViewModel, 'heroState' | 'heroStateLabel'> {
  if (routeState === 'loading') return { heroState: 'loading', heroStateLabel: article ? '刷新中' : '读取中' }
  if (routeState === 'stale') return { heroState: 'stale', heroStateLabel: cachedDataPresentation.stateLabel }
  if (routeState === 'error') return { heroState: 'error', heroStateLabel: article ? '刷新失败' : '读取失败' }
  if (routeState === 'blocked') return { heroState: 'blocked', heroStateLabel: '当前不可用' }
  if (!article) return { heroState: 'unknown', heroStateLabel: '来源待核验' }
  if (article.contentStatus && article.contentStatus !== 'ready') {
    return { heroState: 'partial', heroStateLabel: '内容部分可用' }
  }
  if (isExplicitlyVerified(article)) return { heroState: 'ready', heroStateLabel: '官方已核验' }
  if (clean(article.sourceUrl)) return { heroState: 'source_reference', heroStateLabel: '来源参考' }
  return { heroState: 'unknown', heroStateLabel: '来源待核验' }
}

function translationEvidence(article: NewsArticle): NewsDetailEvidenceRow | undefined {
  const translationStatus = clean(article.translationStatus)
  const fidelity = clean(article.translationFidelity)
  if (!translationStatus && !fidelity) return undefined
  const activeId = newsDetailTranslationId(translationStatus)
  if (activeId === 'human') {
    return {
      id: 'translation',
      typeLabel: '翻译',
      summary: fidelity === 'source_translation' ? '来源翻译正文' : '人工翻译正文',
      statusLabel: '人工翻译',
      timeLabel: '未记录',
      state: 'ready',
    }
  }
  if (activeId === 'machine') {
    return {
      id: 'translation',
      typeLabel: '翻译',
      summary: fidelity === 'source_translation' ? '来源翻译正文' : '机器翻译正文',
      statusLabel: '机器翻译',
      timeLabel: '未记录',
      state: 'source_reference',
    }
  }
  return {
    id: 'translation',
    typeLabel: '翻译',
    summary: '翻译状态待确认',
    statusLabel: '待翻译',
    timeLabel: '未记录',
    state: 'partial',
  }
}

function licenseEvidence(article: NewsArticle): NewsDetailEvidenceRow | undefined {
  const status = normalized(article.licenseStatus)
  if (!status) return undefined
  const approved = ['approved', 'allowed', 'licensed'].includes(status)
  return {
    id: 'license',
    typeLabel: '许可',
    summary: approved ? '内容许可已批准' : `许可状态：${clean(article.licenseStatus)}`,
    statusLabel: approved ? '可展示' : '待确认',
    timeLabel: '未记录',
    state: approved ? 'ready' : 'partial',
  }
}

function evidenceRows(article: NewsArticle | undefined): readonly NewsDetailEvidenceRow[] {
  if (!article) return []
  const rows: NewsDetailEvidenceRow[] = []
  const sourceName = clean(article.sourceName)
  const sourceUrl = clean(article.sourceUrl)
  if (sourceName || sourceUrl) {
    const verified = isExplicitlyVerified(article)
    rows.push({
      id: 'source',
      typeLabel: '来源',
      summary: sourceName || '来源名称未提供',
      statusLabel: verified ? '官方已核验' : sourceUrl ? '来源参考' : '链接缺失',
      timeLabel: '未记录',
      state: verified ? 'ready' : sourceUrl ? 'source_reference' : 'unknown',
    })
  }
  const translation = translationEvidence(article)
  if (translation) rows.push(translation)
  if (clean(article.publishedAt)) {
    const published = formatNewsDetailDate(article.publishedAt)
    rows.push({
      id: 'published',
      typeLabel: '发布',
      summary: published,
      statusLabel: '时间已提供',
      timeLabel: formatNewsDetailCompactDate(article.publishedAt),
      state: 'source_reference',
    })
  }
  const license = licenseEvidence(article)
  if (license) rows.push(license)
  return rows
}

function terminalView(
  article: NewsArticle | undefined,
  routeState: ReadinessState,
  routeReason: string | undefined,
): NewsDetailTerminalView {
  if (routeState === 'loading') {
    return {
      mode: 'loading',
      title: article ? '正在刷新文章' : '正在读取文章',
      detail: article ? '当前正文暂时保留' : '正在读取真实来源',
      action: 'none',
    }
  }
  if (routeState === 'blocked') {
    return {
      mode: 'blocked',
      title: '当前文章不可用',
      detail: routeReason || '当前请求已被阻断',
      actionLabel: '重试',
      action: 'retry',
    }
  }
  if (routeState === 'error') {
    return {
      mode: 'error',
      title: article ? '文章刷新失败' : '文章读取失败',
      detail: routeReason || (article ? '当前显示上次可用正文' : '请重试当前请求'),
      actionLabel: '重试',
      action: 'retry',
    }
  }
  if (!article || routeState === 'empty') {
    return {
      mode: 'missing',
      title: '未找到文章',
      detail: '返回资讯列表选择其他内容',
      actionLabel: '返回列表',
      action: 'go_back',
    }
  }
  return {
    mode: 'ready',
    title: '正文与来源已载入',
    detail: routeState === 'stale' ? cachedDataPresentation.contentDetail : '已保留原始来源与翻译状态',
    action: 'none',
  }
}

export function buildNewsDetailModel({
  article,
  routeState,
  routeReason,
}: BuildNewsDetailModelInput): NewsDetailViewModel {
  const sourceUrl = clean(article?.sourceUrl)
  const activeTranslationId = newsDetailTranslationId(article?.translationStatus)
  const currentHeroState = heroState(article, routeState)

  return {
    articleTitle: clean(article?.title) || (routeState === 'loading' ? '正在读取资讯正文' : '资讯正文不可用'),
    sourceLabel: clean(article?.sourceName) || (routeState === 'loading' ? '来源信息读取中' : '来源信息未提供'),
    sourceUrl,
    sourceUrlLabel: sourceUrlLabel(sourceUrl),
    sourceAvailable: Boolean(sourceUrl),
    ...currentHeroState,
    translationSegments: translationDefinitions.map((segment) => ({
      ...segment,
      selected: segment.id === activeTranslationId,
    })),
    activeTranslationId,
    bodyBlocks: articleBodyBlocks(article),
    evidenceRows: evidenceRows(article),
    initialLoading: routeState === 'loading' && !article,
    refreshing: routeState === 'loading' && Boolean(article),
    terminal: terminalView(article, routeState, routeReason),
  }
}
