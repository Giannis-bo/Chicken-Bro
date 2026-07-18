import Taro, { usePullDownRefresh, useRouter } from '@tarojs/taro'
import { useState } from 'react'

import { wowApi } from '@wow-mini/api-client'
import { AppShell } from '@wow-mini/design-system/components/AppShell'
import {
  NewsListCategoryFilter,
  NewsListFeed,
  NewsListSummary,
  NewsListTerminalPanel,
  TrustDisclaimer,
  type NewsListCategoryItem,
  type NewsListFeedItem,
} from '@wow-mini/design-system/components/NewsListComponents'
import { PageFrame } from '@wow-mini/design-system/components/PageFrame'
import { RouteColumn, RouteFlow, RouteRegion } from '@wow-mini/design-system/components/RouteFlow'
import type { NewsListParams, RouteDataState } from '@wow-mini/domain'

import {
  goBack,
  navigateTo,
  safeDecode,
  useAsyncRoute,
} from '../_shared/route-runtime'
import {
  buildNewsListModel,
  type NewsListCategoryId,
  type NewsListSortDirection,
} from './news-list-model'
import styles from './news-list.module.scss'

function routeReason(state: RouteDataState<unknown>): string | undefined {
  if (state.state === 'error') return state.error
  if (state.state === 'blocked') return state.reason
  if (state.state === 'stale') return state.staleReason
  if (state.state === 'unknown') return state.reason
  return undefined
}

export default function NewsListPage() {
  const router = useRouter()
  const query: NewsListParams = {
    type: router.params['type'] || 'metric',
    key: router.params['key'] || 'today',
    value: safeDecode(router.params['value']),
  }
  const [activeCategory, setActiveCategory] = useState<NewsListCategoryId>('all')
  const [sortDirection, setSortDirection] = useState<NewsListSortDirection>('newest')
  const [visibleCount, setVisibleCount] = useState(6)
  const route = useAsyncRoute(
    () => wowApi.news.list(query),
    { fallbackPolicy: 'blocked', isEmpty: (value) => value.articles.length === 0 },
  )

  usePullDownRefresh(() => {
    void route.load().finally(() => Taro.stopPullDownRefresh())
  })
  const currentRouteReason = routeReason(route.state)
  const model = buildNewsListModel({
    ...(route.data ? { payload: route.data } : {}),
    routeState: route.state.state,
    activeCategory,
    sortDirection,
    visibleCount,
    fallbackTitle: safeDecode(query.value) || '资讯列表',
    ...(currentRouteReason ? { routeReason: currentRouteReason } : {}),
  })
  const listRowCount = model.initialLoading
    ? model.visibleRowSlotCount
    : Math.max(model.items.length, 1)
  const listHeight = listRowCount * 70.64

  const selectCategory = (item: NewsListCategoryItem) => {
    setActiveCategory(item.id as NewsListCategoryId)
    setVisibleCount(6)
    void Taro.pageScrollTo({ scrollTop: 0, duration: 180 })
  }

  const toggleSortDirection = () => {
    setSortDirection((current) => current === 'newest' ? 'oldest' : 'newest')
    setVisibleCount(6)
    void Taro.pageScrollTo({ scrollTop: 0, duration: 180 })
  }
  const openArticle = (item: NewsListFeedItem) => {
    void wowApi.analytics.track('news_article_open', { articleId: item.id, source: 'list' }, 'pages/news/list')
    navigateTo('/pages/news/detail', { id: item.id })
  }
  const handleTerminalAction = () => {
    if (model.terminal.action === 'load_more') {
      setVisibleCount((current) => current + 6)
      return
    }
    if (model.terminal.action === 'reset_filter') {
      setActiveCategory('all')
      setVisibleCount(6)
      return
    }
    if (model.terminal.action === 'refresh' || model.terminal.action === 'retry') {
      void route.load()
    }
  }

  return (
    <AppShell
      surfaceSlotId="asset_slot.news-list-surface"
    >
      <RouteFlow routeState={route.state.state} variant="news">
        <PageFrame
          backRegion="top_bar.back-control"
          region="top_bar"
          title="资讯列表"
          variant="news-list"
          onBack={() => goBack('/pages/news/news')}
        >
          <RouteColumn>
            <RouteRegion className={`${styles['region'] ?? ''} ${styles['summary'] ?? ''}`} data-region="list_summary">
              <NewsListSummary
                countLabel={model.countLabel}
                loading={route.state.state === 'loading'}
                stateLabel={model.stateLabel}
                title={model.title}
                onRefresh={() => void route.load()}
              />
            </RouteRegion>
            <RouteRegion className={`${styles['region'] ?? ''} ${styles['category'] ?? ''}`} data-region="category_filter_bar">
              <NewsListCategoryFilter
                activeId={model.activeCategory}
                items={model.categories}
                loading={model.initialLoading}
                sortDirection={model.sortDirection}
                sortLabel={model.sortLabel}
                onSelect={selectCategory}
                onSort={toggleSortDirection}
              />
            </RouteRegion>
            <RouteRegion
              className={`${styles['region'] ?? ''} ${styles['results'] ?? ''}`}
              data-region="news_results"
              style={{ height: `${listHeight}px` }}
            >
              <NewsListFeed
                items={model.items}
                loading={model.initialLoading}
                loadingRows={model.visibleRowSlotCount}
                onSelect={openArticle}
              />
            </RouteRegion>
            <RouteRegion
              className={`${styles['region'] ?? ''} ${styles['terminal'] ?? ''}`}
              data-region="list_terminal"
              data-terminal-mode={model.terminal.mode}
            >
              <NewsListTerminalPanel
                detail={model.terminal.detail}
                mode={model.terminal.mode}
                title={model.terminal.title}
                {...(model.terminal.actionLabel ? { actionLabel: model.terminal.actionLabel } : {})}
                {...(model.terminal.action !== 'none' ? { onAction: handleTerminalAction } : {})}
              />
            </RouteRegion>
            <RouteRegion className={`${styles['region'] ?? ''} ${styles['disclaimer'] ?? ''}`} data-region="reference_disclaimer">
              <TrustDisclaimer />
            </RouteRegion>
          </RouteColumn>
        </PageFrame>
      </RouteFlow>
    </AppShell>
  )
}
