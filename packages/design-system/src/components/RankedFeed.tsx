import { Text, View } from '@tarojs/components'
import type { ReactNode } from 'react'

import { assetRuntimePath } from '@wow-mini/assets-manifest'
import type { ReadinessState } from '@wow-mini/domain'

import { ActionButton } from './ActionButton'
import { MaterialImage, type MaterialSourceTrust } from './MaterialImage'
import { NineSliceFrame } from './NineSliceFrame'
import { ProductionAssetGlyph } from './ProductionAssetGlyph'
import { StatusVisual } from './StatusVisual'
import { SystemGlyph } from './SystemGlyph'
import { reconstructionStyle } from './reconstruction-style'
import { dataSelectorClass } from './selector-markers'
import { ownerClass, ownerStyle } from './style'

export interface RankedFeedItem {
  id: string
  title: string
  summary?: string
  meta?: readonly string[]
  state?: ReadinessState
  stateLabel?: string
  trailing?: ReactNode
  mediaSource?: string
  mediaTrust?: MaterialSourceTrust
  mediaSlotId?: string
  statusGlyph?: 'verdict' | 'row' | 'module'
  sourceLabel?: string | undefined
  timeLabel?: string | undefined
  accent?: 'source' | 'review' | undefined
  region?: string | undefined
  saved?: boolean | undefined
  disabled?: boolean | undefined
}

export interface RankedFeedProps {
  items: readonly RankedFeedItem[]
  emptyText: string
  loading?: boolean | undefined
  loadingRows?: number | undefined
  minimumRows?: number | undefined
  onSelect?: (item: RankedFeedItem) => void
  onToggleSaved?: (item: RankedFeedItem) => void
  variant?: 'default' | 'news-home' | 'news-list' | undefined
  title?: string | undefined
  region?: string | undefined
}

export function RankedFeed({
  items,
  emptyText,
  loading = false,
  loadingRows = 3,
  minimumRows = 0,
  onSelect,
  onToggleSaved,
  variant = 'default',
  title,
  region = 'shared_ranked-feed',
}: RankedFeedProps) {
  if (variant === 'news-list') {
    const rows = loading
      ? Array.from({ length: loadingRows }, (_, index): RankedFeedItem => ({
          id: `loading-${index}`,
          title: '',
          region: `news-list_target_region_feed-card-${index + 1}`,
        }))
      : items
    return (
      <View
        className={ownerClass(ownerStyle('feed'), reconstructionStyle('newsListFeed'))}
        data-loading={loading ? 'true' : 'false'}
        data-owner="ranked-feed"
        data-region={region}
      >
        {rows.map((item) => (
          <View
            key={item.id}
            className={reconstructionStyle('newsListFeedCard')}
            data-accent={item.accent ?? 'source'}
            data-region={item.region}
            data-role="news-list-feed-card"
            onClick={() => !loading && onSelect?.(item)}
          >
            <View className={reconstructionStyle('newsListFeedAccent')} />
            <View className={reconstructionStyle('newsListFeedIcon')}>
              <SystemGlyph assetId="utility-glyph-family.document" dataRole="news-list-feed-icon" slotId="asset_slot.utility-glyph-family" />
            </View>
            <View className={reconstructionStyle('newsListFeedMain')}>
              {loading ? (
                <>
                  <View className={ownerStyle('skeletonLineStrong')} />
                  <View className={ownerStyle('skeletonLineShort')} />
                </>
              ) : (
                <>
                  <Text className={reconstructionStyle('newsListFeedTitle')}>{item.title}</Text>
                  <View className={reconstructionStyle('newsListFeedBadges')}>
                    {item.sourceLabel ? (
                      <View className={reconstructionStyle('newsListSourceBadge')}>
                        <SystemGlyph assetId="utility-glyph-family.source-link" slotId="asset_slot.utility-glyph-family" />
                        <Text className={reconstructionStyle('newsListSourceBadgeLabel')} data-role="source-reference-label">{item.sourceLabel}</Text>
                      </View>
                    ) : null}
                    {item.state ? (
                      <StatusVisual
                        compact
                        glyph={item.statusGlyph}
                        label={item.stateLabel}
                        state={item.state}
                        variant="pill"
                      />
                    ) : null}
                  </View>
                </>
              )}
            </View>
            <View className={reconstructionStyle('newsListFeedTrailing')}>
              {loading ? <View className={ownerStyle('skeletonLineShort')} /> : (
                <>
                  {item.timeLabel ? <Text className={reconstructionStyle('newsListFeedTime')} data-role="news-list-feed-time">{item.timeLabel}</Text> : null}
                  {onSelect ? <SystemGlyph assetId="utility-glyph-family.chevron-right" dataRole="news-list-feed-chevron" slotId="asset_slot.utility-glyph-family" /> : null}
                </>
              )}
            </View>
          </View>
        ))}
      </View>
    )
  }

  const frameAssetId = variant === 'news-home' ? 'news-frame.feed' as const : undefined
  const productionFrameAvailable = Boolean(frameAssetId && assetRuntimePath(frameAssetId))
  const frameLayer = frameAssetId ? (
    <NineSliceFrame
      assetId={frameAssetId}
      slotId="asset_slot.news-frame"
    />
  ) : null
  const heading = title ? (
    <View className={ownerStyle('feedSectionHeader')}>
      <Text className={ownerStyle('feedSectionTitle')} data-role="feed-section-title">{title}</Text>
      {variant === 'news-home' ? (
        <SystemGlyph
          assetId="utility-glyph-family.chevron-right"
          className={ownerStyle('feedSectionChevron')}
          dataRole="feed-section-chevron"
          slotId="asset_slot.utility-glyph-family"
        />
      ) : null}
    </View>
  ) : null
  const visibleItems: readonly RankedFeedItem[] = items.length >= minimumRows
    ? items
    : [
        ...items,
        ...Array.from({ length: minimumRows - items.length }, (_, index): RankedFeedItem => ({
          id: `unavailable-${items.length + index}`,
          title: '',
          mediaSlotId: 'asset_slot.news-feed-fallback',
          disabled: true,
        })),
      ]

  if (loading) {
    return (
      <View
        className={ownerClass(
          ownerStyle('feed'),
          variant === 'news-home' && ownerStyle('feedNewsHome'),
          dataSelectorClass('production-frame', productionFrameAvailable),
        )}
        data-loading="true"
        data-owner="ranked-feed"
        data-production-frame={productionFrameAvailable ? 'true' : 'false'}
        data-region={region}
      >
        {frameLayer}
        {heading}
        {Array.from({ length: loadingRows }, (_, index) => (
          <View
            key={`loading-${index}`}
            className={ownerClass(ownerStyle('feedRow'), ownerStyle('feedRowWithMedia'))}
            data-region={variant === 'news-home' ? `news-home_baseline_region_feed-item-${index + 1}` : undefined}
            data-role={variant === 'news-home' ? 'news-home-feed-row' : 'feed-row'}
          >
            <View
              className={ownerStyle('feedThumbSkeleton')}
              data-slot-id="asset_slot.news-feed-fallback"
            />
            <View className={ownerStyle('feedMain')} data-role="feed-main">
              <View className={ownerStyle('skeletonLineStrong')} />
              <View className={ownerStyle('skeletonLine')} />
              <View className={ownerStyle('skeletonLineShort')} />
            </View>
            <View className={ownerStyle('feedActionSkeleton')} />
          </View>
        ))}
      </View>
    )
  }
  if (!visibleItems.length) {
    return (
      <View
        className={ownerClass(
          ownerStyle('feed'),
          variant === 'news-home' && ownerStyle('feedNewsHome'),
          dataSelectorClass('production-frame', productionFrameAvailable),
        )}
        data-owner="ranked-feed"
        data-production-frame={productionFrameAvailable ? 'true' : 'false'}
        data-region={region}
      >
        {frameLayer}
        {heading}
        <View className={ownerStyle('feedEmpty')}>{emptyText}</View>
      </View>
    )
  }
  return (
    <View
      className={ownerClass(
        ownerStyle('feed'),
        variant === 'news-home' && ownerStyle('feedNewsHome'),
        dataSelectorClass('production-frame', productionFrameAvailable),
      )}
      data-owner="ranked-feed"
      data-production-frame={productionFrameAvailable ? 'true' : 'false'}
      data-region={region}
    >
      {frameLayer}
      {heading}
      {visibleItems.map((item, index) => {
        const visibleMeta = item.meta?.filter((value) => value !== item.stateLabel) ?? []
        if (item.disabled) {
          return (
            <View
              key={item.id}
              className={ownerClass(ownerStyle('feedRow'), ownerStyle('feedRowWithMedia'), ownerStyle('feedRowUnavailable'))}
              data-availability="unavailable"
              data-region={variant === 'news-home' ? `news-home_baseline_region_feed-item-${index + 1}` : undefined}
              data-role={variant === 'news-home' ? 'news-home-feed-row' : 'feed-row'}
            >
              <MaterialImage
                alt="暂无可验证资讯"
                aspect="wide"
                fallbackAssetId={`news-feed-fallback.neutral-0${(index % 4) + 1}`}
                fallbackLabel="资讯暂不可用"
                fallbackMode="aspectFill"
                fallbackSlotId="asset_slot.news-feed-fallback"
                slotId="asset_slot.news-feed-fallback"
                sourceTrust="placeholder"
              />
              <View className={ownerStyle('feedMain')}>
                <Text className={ownerStyle('feedTitle')} data-role="feed-title">暂无可验证资讯</Text>
                <View className={ownerStyle('feedMeta')} data-role="feed-meta">
                  <ProductionAssetGlyph
                    assetId="news-evidence-glyph.unavailable"
                    className={ownerStyle('feedMetaGlyph')}
                    fallbackAssetId="utility-glyph-family.source-link"
                    fallbackSlotId="asset_slot.utility-glyph-family"
                    slotId="asset_slot.news-evidence-glyph"
                  />
                  <Text data-role="feed-meta-value">来源参考暂不可用</Text>
                </View>
                <StatusVisual
                  compact
                  glyph="row"
                  label="不可用"
                  state="blocked"
                  tone="evidence"
                  variant="pill"
                />
              </View>
              <View className={ownerStyle('feedTrailing')}>
                <ProductionAssetGlyph
                  assetId="news-evidence-glyph.unavailable"
                  className={ownerStyle('feedUnavailableTrailingGlyph')}
                  fallbackAssetId="utility-glyph-family.source-link"
                  fallbackSlotId="asset_slot.utility-glyph-family"
                  slotId="asset_slot.news-evidence-glyph"
                />
              </View>
            </View>
          )
        }
        return (
          <View
            key={item.id}
            className={ownerClass(ownerStyle('feedRow'), item.mediaSlotId && ownerStyle('feedRowWithMedia'))}
            data-article-id={item.id}
            data-region={item.region}
            data-role={variant === 'news-home' ? 'news-home-feed-row' : 'feed-row'}
            onClick={() => onSelect?.(item)}
          >
            {item.mediaSlotId ? (
              <MaterialImage
                alt={item.title}
                aspect="wide"
                fallbackAssetId={`news-feed-fallback.neutral-0${(index % 4) + 1}`}
                fallbackGlyphAssetId="utility-glyph-family.media"
                fallbackGlyphSlotId="asset_slot.utility-glyph-family"
                fallbackLabel="资讯缩略图"
                fallbackMode="aspectFill"
                fallbackSlotId="asset_slot.news-feed-fallback"
                slotId={item.mediaSlotId}
                source={item.mediaSource}
                sourceTrust={item.mediaTrust ?? 'placeholder'}
              />
            ) : null}
            <View className={ownerStyle('feedMain')}>
              <Text className={ownerStyle('feedTitle')} data-role="feed-title">{item.title}</Text>
              {item.summary ? <Text className={ownerStyle('feedSummary')}>{item.summary}</Text> : null}
              {visibleMeta.length ? (
                <View className={ownerStyle('feedMeta')} data-role="feed-meta">
                  {variant === 'news-home'
                    ? (
                        <>
                          <ProductionAssetGlyph
                            assetId="news-evidence-glyph.source"
                            className={ownerStyle('feedMetaGlyph')}
                            fallbackAssetId="utility-glyph-family.source-link"
                            fallbackSlotId="asset_slot.utility-glyph-family"
                            slotId="asset_slot.news-evidence-glyph"
                          />
                          <Text data-role="feed-meta-value">{visibleMeta.join(' · ')}</Text>
                        </>
                      )
                    : visibleMeta.map((value) => <Text key={value} data-role="feed-meta-value">{value}</Text>)}
                </View>
              ) : null}
              {variant === 'news-home' && item.state ? (
                <StatusVisual
                  compact
                  glyph={item.statusGlyph}
                  label={item.stateLabel}
                  state={item.state}
                  tone="evidence"
                  variant="pill"
                />
              ) : null}
            </View>
            <View className={ownerStyle('feedTrailing')} data-role="feed-trailing">
              {item.trailing}
              {variant !== 'news-home' && item.state ? (
                <StatusVisual
                  compact
                  glyph={item.statusGlyph}
                  label={item.stateLabel}
                  state={item.state}
                  variant="pill"
                />
              ) : null}
              {variant === 'news-home' ? (
                <View
                  aria-label={item.saved ? '取消收藏资讯' : '收藏资讯'}
                  className={ownerClass(
                    ownerStyle('feedBookmarkVisual'),
                    item.saved && ownerStyle('feedBookmarkVisualSelected'),
                  )}
                  data-saved={item.saved ? 'true' : 'false'}
                  onClick={(event) => {
                    event.stopPropagation()
                    onToggleSaved?.(item)
                  }}
                >
                  <ProductionAssetGlyph
                    assetId={item.saved ? 'news-bookmark-glyph.selected' : 'news-bookmark-glyph.default'}
                    fallbackAssetId="utility-glyph-family.save"
                    fallbackSlotId="asset_slot.utility-glyph-family"
                    slotId="asset_slot.news-bookmark-glyph"
                  />
                </View>
              ) : onSelect ? (
                <ActionButton
                  ariaLabel="打开详情"
                  iconPath={assetRuntimePath('utility-glyph-family.chevron-right') ?? undefined}
                  iconSlotId="asset_slot.utility-glyph-family"
                  variant="ghost"
                >
                  {null}
                </ActionButton>
              ) : null}
            </View>
          </View>
        )
      })}
    </View>
  )
}
