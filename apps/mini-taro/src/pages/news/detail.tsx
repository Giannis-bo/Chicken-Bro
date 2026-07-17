import Taro, { usePullDownRefresh, useRouter } from '@tarojs/taro'
import { useState } from 'react'

import { wowApi } from '@wow-mini/api-client'
import { AppShell } from '@wow-mini/design-system/components/AppShell'
import {
  ArticleEvidencePanel,
  ArticleReadingSurface,
  NewsDetailHero,
  NewsDetailTerminalPanel,
  SourceReferenceAction,
  TranslationStatusSegments,
} from '@wow-mini/design-system/components/NewsDetailComponents'
import { PageFrame } from '@wow-mini/design-system/components/PageFrame'
import { RouteColumn, RouteFlow, RouteRegion } from '@wow-mini/design-system/components/RouteFlow'
import type { RouteDataState } from '@wow-mini/domain'

import {
  copyText,
  goBack,
  useAsyncRoute,
} from '../_shared/route-runtime'
import { buildNewsDetailModel } from './news-detail-model'
import styles from './news-detail.module.scss'

function routeReason(state: RouteDataState<unknown>): string | undefined {
  if (state.state === 'error') return state.error
  if (state.state === 'blocked') return state.reason
  if (state.state === 'stale') return state.staleReason
  if (state.state === 'unknown') return state.reason
  return undefined
}

export default function NewsDetailPage() {
  const router = useRouter()
  const articleId = router.params['id'] ?? ''
  const [evidenceExpanded, setEvidenceExpanded] = useState(true)
  const route = useAsyncRoute(
    () => articleId
      ? wowApi.news.article(articleId)
      : Promise.resolve({ payload: null, fromFallback: false, error: '' }),
    { fallbackPolicy: articleId ? 'stale' : 'blocked', isEmpty: (value) => value === null },
  )

  usePullDownRefresh(() => {
    void route.load().finally(() => Taro.stopPullDownRefresh())
  })
  const currentRouteReason = routeReason(route.state)
  const model = buildNewsDetailModel({
    ...(route.data ? { article: route.data } : {}),
    routeState: route.state.state,
    ...(currentRouteReason ? { routeReason: currentRouteReason } : {}),
  })

  const handleTerminalAction = () => {
    if (model.terminal.action === 'retry') {
      void route.load()
      return
    }
    if (model.terminal.action === 'go_back') goBack('/pages/news/news')
  }

  return (
    <AppShell
      surfaceSlotId="asset_slot.news-detail-surface"
    >
      <RouteFlow routeState={route.state.state} variant="news">
        <PageFrame
          backRegion="top_bar.back-control"
          region="top_bar"
          title="资讯详情"
          variant="news-detail"
          onBack={() => goBack('/pages/news/news')}
        >
          <RouteColumn>
            <RouteRegion className={`${styles['region'] ?? ''} ${styles['hero'] ?? ''}`}>
              <NewsDetailHero
                loading={model.initialLoading}
                sourceLabel={model.sourceLabel}
                state={model.heroState}
                stateLabel={model.heroStateLabel}
                title={model.articleTitle}
              />
            </RouteRegion>
            <RouteRegion className={`${styles['region'] ?? ''} ${styles['translation'] ?? ''}`}>
              <TranslationStatusSegments
                activeId={model.activeTranslationId}
                items={model.translationSegments}
                loading={model.initialLoading}
              />
            </RouteRegion>
            <RouteRegion className={`${styles['region'] ?? ''} ${styles['body'] ?? ''}`}>
              <ArticleReadingSurface blocks={model.bodyBlocks} loading={model.initialLoading} />
            </RouteRegion>
            <RouteRegion className={`${styles['region'] ?? ''} ${styles['source'] ?? ''}`}>
              <SourceReferenceAction
                available={model.sourceAvailable}
                sourceLabel={model.sourceLabel}
                sourceUrlLabel={model.sourceUrlLabel}
                {...(model.sourceAvailable ? {
                  onCopy: () => copyText(model.sourceUrl, '来源链接已复制'),
                } : {})}
              />
            </RouteRegion>
            <RouteRegion className={`${styles['region'] ?? ''} ${styles['evidence'] ?? ''}`}>
              <ArticleEvidencePanel
                expanded={evidenceExpanded}
                rows={model.evidenceRows}
                onToggle={() => setEvidenceExpanded((current) => !current)}
              />
            </RouteRegion>
            <RouteRegion className={`${styles['region'] ?? ''} ${styles['terminal'] ?? ''}`}>
              <NewsDetailTerminalPanel
                detail={model.terminal.detail}
                mode={model.terminal.mode}
                title={model.terminal.title}
                {...(model.terminal.actionLabel ? { actionLabel: model.terminal.actionLabel } : {})}
                {...(model.terminal.action !== 'none' ? { onAction: handleTerminalAction } : {})}
              />
            </RouteRegion>
          </RouteColumn>
        </PageFrame>
      </RouteFlow>
    </AppShell>
  )
}
