import Taro, { usePullDownRefresh } from '@tarojs/taro'
import { View } from '@tarojs/components'
import { useMemo, useState } from 'react'

import { wowApi } from '@wow-mini/api-client'
import { AppShell } from '@wow-mini/design-system/components/AppShell'
import {
  ChannelDock,
  type ChannelDockItem,
} from '@wow-mini/design-system/components/ChannelDock'
import {
  FeaturedCarousel,
  type FeaturedCarouselItem,
} from '@wow-mini/design-system/components/FeaturedCarousel'
import { NewsHomeBrief } from '@wow-mini/design-system/components/NewsHomeBrief'
import { PageFrame } from '@wow-mini/design-system/components/PageFrame'
import {
  RankedFeed,
  type RankedFeedItem,
} from '@wow-mini/design-system/components/RankedFeed'

import { navigateTo, useAsyncRoute } from '../_shared/route-runtime'
import { buildNewsHomeModel } from './news-home-model'
import styles from './news-home.module.scss'

export default function NewsHomePage() {
  const route = useAsyncRoute(
    () => wowApi.news.home('manual'),
    { fallbackPolicy: 'stale' },
  )
  const [savedArticleIds, setSavedArticleIds] = useState<readonly string[]>(() => wowApi.news.savedArticleIds())

  usePullDownRefresh(() => {
    void route.load().finally(() => Taro.stopPullDownRefresh())
  })

  const model = useMemo(() => buildNewsHomeModel({
    routeState: route.state.state,
    homeFavorite: false,
    savedArticleIds,
    ...(route.data ? { payload: route.data } : {}),
  }), [route.data, route.state.state, savedArticleIds])

  const featured: readonly FeaturedCarouselItem[] = model.carousel.items.map((article) => ({
    id: article.id,
    title: article.displayTitle,
    summary: article.summary,
    sourceLabel: article.sourceLabel,
    state: article.state,
    stateLabel: article.stateLabel,
    mediaSlotId: 'asset_slot.news-hero-media',
    ...(article.mediaSource ? { mediaSource: article.mediaSource, mediaTrust: 'verified_media' as const } : {}),
  }))
  const channels: readonly ChannelDockItem[] = model.channels.map((channel) => ({
    id: channel.id,
    label: channel.label,
    glyphAssetId: channel.glyphAssetId,
    fallbackGlyphAssetId: channel.fallbackGlyphAssetId,
  }))
  const feed: readonly RankedFeedItem[] = model.feed.map((article, index) => ({
    id: article.id,
    title: article.title,
    summary: article.summary,
    meta: article.sourceLabel ? [article.sourceLabel] : [],
    state: article.state,
    stateLabel: article.stateLabel,
    mediaSlotId: 'asset_slot.news-feed-fallback',
    statusGlyph: 'row',
    saved: article.saved,
    region: `news-home_target_region_feed-item-${index + 1}`,
    ...(article.mediaSource ? { mediaSource: article.mediaSource, mediaTrust: 'verified_media' as const } : {}),
  }))

  const openArticle = (id: string) => {
    void wowApi.analytics.track('news_article_open', { articleId: id, source: 'home' }, 'pages/news/news')
    navigateTo('/pages/news/detail', { id })
  }

  const toggleSavedArticle = (item: RankedFeedItem) => {
    setSavedArticleIds(wowApi.news.setArticleSaved(item.id, !item.saved))
  }

  return (
    <AppShell tabRoot>
      <PageFrame
        headerStatusLabel={model.headerStatusLabel}
        sourceLabel={model.headerSourceLabel}
        title={model.title}
        variant="news-home"
      >
        <View className={styles['surface'] ?? ''} data-owner="news-home-surface">
          <NewsHomeBrief
            dateLabel={model.daily.dateLabel}
            loading={model.initialLoading}
            metrics={model.daily.metrics}
            retryAvailable={model.retryAvailable}
            sourceLabel={model.daily.sourceLabel}
            statusLabel={model.daily.statusLabel}
            onRetry={route.load}
            onSelectMetric={(metric) => {
              const target = model.daily.metrics.find((candidate) => candidate.id === metric.id)
              if (target?.available) navigateTo('/pages/news/list', {
                type: target.query.type,
                key: target.query.key,
              })
            }}
          />
          <FeaturedCarousel
            autoplay
            items={featured}
            loading={model.initialLoading}
            paginationSlots={model.carousel.visualSlotCount}
            variant="news-home"
            onSelect={(item) => openArticle(item.id)}
          />
          <ChannelDock
            activeId="all"
            items={channels}
            variant="news-home"
            onSelect={(item) => {
              const target = model.channels.find((candidate) => candidate.id === item.id)
              if (target) navigateTo('/pages/news/list', {
                type: target.query.type,
                key: target.query.key,
              })
            }}
          />
          <RankedFeed
            emptyText="暂无可用资讯"
            items={feed}
            loading={model.initialLoading}
            loadingRows={4}
            minimumRows={4}
            title="今日重点"
            variant="news-home"
            onSelect={(item) => openArticle(item.id)}
            onToggleSaved={toggleSavedArticle}
          />
        </View>
      </PageFrame>
    </AppShell>
  )
}
