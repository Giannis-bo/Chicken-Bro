import { Text, View } from '@tarojs/components'
import { useEffect, useState } from 'react'

import { assetRuntimePath } from '@wow-mini/assets-manifest'
import type { ReadinessState } from '@wow-mini/domain'

import { MaterialImage, type MaterialSourceTrust } from './MaterialImage'
import { NineSliceFrame } from './NineSliceFrame'
import { ProductionAssetGlyph } from './ProductionAssetGlyph'
import { StatusVisual } from './StatusVisual'
import { reconstructionClass, reconstructionStyle } from './reconstruction-style'
import { dataSelectorClass } from './selector-markers'

export interface FeaturedCarouselItem {
  id: string
  title: string
  summary?: string
  mediaSource?: string
  mediaTrust?: MaterialSourceTrust
  mediaSlotId: string
  sourceLabel?: string | undefined
  state?: ReadinessState | undefined
  stateLabel?: string | undefined
}

export interface FeaturedCarouselProps {
  items: readonly FeaturedCarouselItem[]
  autoplay?: boolean
  loading?: boolean | undefined
  paginationSlots?: number | undefined
  variant?: 'default' | 'news-home' | undefined
  region?: string | undefined
  onSelect?: ((item: FeaturedCarouselItem) => void) | undefined
}

export function FeaturedCarousel({
  items,
  autoplay = false,
  loading = false,
  paginationSlots,
  variant = 'default',
  region = 'news-home_baseline_region_featured-carousel',
  onSelect,
}: FeaturedCarouselProps) {
  const [activeIndex, setActiveIndex] = useState(0)
  const [mediaRenderMode, setMediaRenderMode] = useState<'source' | 'fallback'>('fallback')
  const active = items[activeIndex]
  const dotCount = Math.max(items.length, paginationSlots ?? 0, 1)
  const frameAssetId = 'news-frame.media' as const
  const productionFrameAvailable = Boolean(assetRuntimePath(frameAssetId))

  useEffect(() => {
    if (activeIndex >= items.length) setActiveIndex(0)
  }, [activeIndex, items.length])

  useEffect(() => {
    if (!autoplay || items.length < 2) return undefined
    const timer = setInterval(() => setActiveIndex((current) => (current + 1) % items.length), 5500)
    return () => clearInterval(timer)
  }, [autoplay, items.length])

  return (
    <View
      className={reconstructionClass(
        reconstructionStyle('featuredCarousel'),
        variant === 'news-home' && reconstructionStyle('featuredCarouselNewsHome'),
        dataSelectorClass('production-frame', productionFrameAvailable),
      )}
      data-loading={loading ? 'true' : 'false'}
      data-item-ids={items.map((item) => item.id).join(',')}
      data-owner="featured-carousel"
      data-production-frame={productionFrameAvailable ? 'true' : 'false'}
      data-region={region}
      data-state={active?.state ?? (loading ? 'loading' : 'source_reference')}
      data-variant={variant}
    >
      <NineSliceFrame
        assetId={frameAssetId}
        slotId="asset_slot.news-frame"
      />
      <View
        className={reconstructionClass(
          reconstructionStyle('featuredMedia'),
          mediaRenderMode === 'fallback' && reconstructionStyle('featuredMediaFallback'),
        )}
        data-article-id={active?.id ?? ''}
        data-role="featured-media"
        onClick={() => active && onSelect?.(active)}
      >
        <MaterialImage
          alt={active?.title ?? '资讯媒体区域'}
          aspect="banner"
          fallbackAssetId="news-hero-fallback.neutral-editorial"
          fallbackLabel={loading ? '可信媒体加载中' : '暂无经核验的资讯媒体'}
          fallbackMode="aspectFill"
          fallbackSlotId="asset_slot.news-hero-fallback-scene"
          slotId="asset_slot.news-hero-media"
          source={active?.mediaSource}
          sourceTrust={active?.mediaTrust ?? 'placeholder'}
          onRenderModeChange={setMediaRenderMode}
        />
        {active?.sourceLabel || active?.stateLabel || loading ? (
          <View className={reconstructionStyle('featuredBadges')} data-role="featured-badges">
            {active?.sourceLabel ? (
              <View className={reconstructionStyle('sourceBadge')} data-role="featured-source-badge">
                <ProductionAssetGlyph
                  assetId="news-evidence-glyph.source"
                  fallbackAssetId="utility-glyph-family.source-link"
                  fallbackSlotId="asset_slot.utility-glyph-family"
                  slotId="asset_slot.news-evidence-glyph"
                />
                <Text className={reconstructionStyle('sourceBadgeLabel')} data-role="source-reference-label">{active.sourceLabel}</Text>
              </View>
            ) : loading ? <View className={reconstructionStyle('featuredBadgeSkeleton')} /> : <View />}
            {active?.stateLabel && active.state ? (
              <View className={reconstructionStyle('featuredStateBadge')} data-role="featured-state-badge">
                      <StatusVisual compact label={active.stateLabel} state={active.state} tone="evidence" variant="pill" />
              </View>
            ) : loading ? <View className={reconstructionStyle('featuredStateSkeleton')} /> : null}
          </View>
        ) : null}
        <View className={reconstructionStyle('featuredCopy')}>
          {loading ? (
            <>
              <View className={reconstructionStyle('featuredTitleSkeleton')} />
              <View className={reconstructionStyle('featuredSummarySkeleton')} />
            </>
          ) : (
            <>
              <Text className={reconstructionStyle('featuredTitle')} data-role="featured-title">{active?.title ?? '暂无可用资讯'}</Text>
              {active?.summary ? <Text className={reconstructionStyle('featuredSummary')} data-role="featured-summary">{active.summary}</Text> : null}
            </>
          )}
        </View>
      </View>
      <View className={reconstructionStyle('carouselDots')} data-role="carousel-dots">
        {Array.from({ length: dotCount }, (_, index) => {
          const available = index < items.length
          return (
            <View
              key={`dot-${index}`}
              {...(available ? { 'aria-label': `切换到第 ${index + 1} 条` } : {})}
              className={reconstructionClass(
                reconstructionStyle('carouselDot'),
                available && index === activeIndex && reconstructionStyle('carouselDotActive'),
                !available && reconstructionStyle('carouselDotUnavailable'),
              )}
              data-available={available ? 'true' : 'false'}
              data-role="carousel-dot"
              {...(available ? { onClick: () => setActiveIndex(index) } : {})}
            />
          )
        })}
      </View>
    </View>
  )
}
