import { describe, expect, it } from 'vitest'

import type { NewsArticle, NewsBodyBlock } from '@wow-mini/domain'

import {
  buildNewsDetailModel,
  formatNewsDetailDate,
  newsDetailTranslationId,
} from './news-detail-model'

function article(overrides: Partial<NewsArticle> = {}): NewsArticle {
  const blocks: readonly NewsBodyBlock[] = Array.from({ length: 39 }, (_, index) => ({
    type: index === 7 ? 'list' : 'paragraph',
    ...(index === 7 ? { items: ['第一项', '第二项'] } : { text: `正文段落 ${index + 1}` }),
  }))
  return {
    id: 'article-1',
    title: '真实资讯标题',
    summary: '真实资讯摘要',
    channel: '正式服动态',
    category: '正式服',
    sourceName: 'Blizzard Forums',
    sourceUrl: 'https://us.forums.blizzard.com/en/wow/t/topic/123',
    publishedAt: '2026-07-10T18:42:49.556Z',
    bodyBlocksZh: blocks,
    contentStatus: 'ready',
    translationStatus: 'llm',
    translationFidelity: 'source_translation',
    verificationStatus: 'official_verified',
    licenseStatus: 'approved',
    sourceTier: 'official',
    sourceBadges: ['官方已核验', '全文翻译'],
    ...overrides,
  }
}

describe('news detail target model', () => {
  it('maps the probed article into all truthful detail regions', () => {
    const model = buildNewsDetailModel({ article: article(), routeState: 'ready' })

    expect(model.articleTitle).toBe('真实资讯标题')
    expect(model.sourceAvailable).toBe(true)
    expect(model.sourceUrlLabel).toBe('us.forums.blizzard.com')
    expect(model.heroStateLabel).toBe('官方已核验')
    expect(model.translationSegments).toHaveLength(3)
    expect(model.translationSegments.filter((segment) => segment.selected)).toEqual([
      { id: 'machine', label: '机器翻译', selected: true },
    ])
    expect(model.bodyBlocks).toHaveLength(39)
    expect(model.evidenceRows.map((row) => row.id)).toEqual(['source', 'translation', 'published', 'license'])
    expect(model.evidenceRows.map((row) => row.statusLabel).join(' ')).not.toMatch(/%|可信度/u)
    expect(model.terminal).toMatchObject({ mode: 'ready', title: '正文与来源已载入', action: 'none' })
  })

  it('keeps all regions truthful when optional evidence is absent', () => {
    const candidate = article({ sourceName: '', sourceUrl: '', publishedAt: '', bodyZh: '' })
    delete candidate.bodyBlocksZh
    delete candidate.translationStatus
    delete candidate.translationFidelity
    delete candidate.verificationStatus
    delete candidate.licenseStatus
    delete candidate.sourceTier
    delete candidate.sourceBadges
    const model = buildNewsDetailModel({ article: candidate, routeState: 'partial' })

    expect(model.sourceAvailable).toBe(false)
    expect(model.sourceUrlLabel).toBe('来源链接不可用')
    expect(model.activeTranslationId).toBe('pending')
    expect(model.bodyBlocks).toEqual([{ type: 'paragraph', text: '真实资讯摘要' }])
    expect(model.evidenceRows).toEqual([])
    expect(model.terminal.mode).toBe('ready')
  })

  it('mounts stable loading and missing compositions without invented article facts', () => {
    const loading = buildNewsDetailModel({ routeState: 'loading' })
    const missing = buildNewsDetailModel({ routeState: 'empty' })

    expect(loading.initialLoading).toBe(true)
    expect(loading.translationSegments).toHaveLength(3)
    expect(loading.bodyBlocks).toEqual([])
    expect(loading.evidenceRows).toEqual([])
    expect(loading.terminal.mode).toBe('loading')
    expect(missing.sourceAvailable).toBe(false)
    expect(missing.terminal).toMatchObject({ mode: 'missing', action: 'go_back' })
  })

  it('preserves stale content and exposes retryable route failures', () => {
    const stale = buildNewsDetailModel({ article: article(), routeState: 'stale', routeReason: '后端超时' })
    const failed = buildNewsDetailModel({ routeState: 'error', routeReason: '网络失败' })

    expect(stale.bodyBlocks).toHaveLength(39)
    expect(stale.heroStateLabel).toBe('缓存可用')
    expect(stale.terminal.detail).toBe('当前显示缓存内容')
    expect(stale.sourceLabel).toBe('Blizzard Forums')
    expect(failed.terminal).toMatchObject({ mode: 'error', detail: '网络失败', action: 'retry' })
  })

  it('normalizes only explicit translation statuses and absolute dates', () => {
    expect(newsDetailTranslationId('llm')).toBe('machine')
    expect(newsDetailTranslationId('human_translation')).toBe('human')
    expect(newsDetailTranslationId(undefined)).toBe('pending')
    expect(formatNewsDetailDate('2026-07-10T18:42:49.556Z')).toBe('2026年07月10日')
    expect(formatNewsDetailDate('unknown')).toBe('日期未提供')
  })
})
