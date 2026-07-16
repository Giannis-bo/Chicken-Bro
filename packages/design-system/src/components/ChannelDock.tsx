import { ScrollView, Text, View } from '@tarojs/components'

import { assetRuntimePath, type ProductionAssetId } from '@wow-mini/assets-manifest'

import { NineSliceFrame } from './NineSliceFrame'
import { ProductionAssetGlyph } from './ProductionAssetGlyph'
import { SystemGlyph } from './SystemGlyph'
import { reconstructionClass, reconstructionStyle } from './reconstruction-style'
import { dataSelectorClass } from './selector-markers'

export interface ChannelDockItem {
  id: string
  label: string
  count?: number
  glyphAssetId?: ProductionAssetId | undefined
  fallbackGlyphAssetId?: ProductionAssetId | undefined
}

export interface ChannelDockProps {
  items: readonly ChannelDockItem[]
  activeId?: string
  loading?: boolean | undefined
  variant?: 'news-home' | 'news-list' | 'scroll' | undefined
  region?: string | undefined
  onSelect?: ((item: ChannelDockItem) => void) | undefined
  onTune?: (() => void) | undefined
}

const channelGlyphs: readonly ProductionAssetId[] = [
  'utility-glyph-family.records',
  'utility-glyph-family.adjust',
  'utility-glyph-family.runtime',
  'utility-glyph-family.shield',
  'utility-glyph-family.topic',
  'utility-glyph-family.document',
]

export function ChannelDock({
  items,
  activeId,
  loading = false,
  variant = 'scroll',
  region = 'shared_channel-dock',
  onSelect,
  onTune,
}: ChannelDockProps) {
  const visibleItems: readonly ChannelDockItem[] = loading
    ? Array.from({ length: 6 }, (_, index) => ({ id: `loading-${index}`, label: '' }))
    : items
  const newsHomeFrameAvailable = variant === 'news-home' && Boolean(assetRuntimePath('news-frame.tile'))

  if (variant === 'news-list') {
    return (
      <View className={reconstructionStyle('newsListCategoryPanel')} data-owner="channel-dock" data-region={region}>
        <ScrollView scrollX showScrollbar={false}>
          <View className={reconstructionStyle('newsListCategoryDock')}>
            {visibleItems.map((item) => {
              const selected = item.id === activeId
              return (
                <View
                  key={item.id}
                  className={reconstructionClass(
                    reconstructionStyle('newsListCategoryItem'),
                    selected && reconstructionStyle('newsListCategoryItemActive'),
                    loading && reconstructionStyle('newsListCategoryItemLoading'),
                  )}
                  data-role="news-list-category"
                  data-selected={selected ? 'true' : 'false'}
                  onClick={() => !loading && onSelect?.(item)}
                >
                  {loading ? <View className={reconstructionStyle('newsListCategorySkeleton')} /> : <Text>{item.label}</Text>}
                </View>
              )
            })}
            <View
              aria-label="筛选设置"
              className={reconstructionStyle('newsListCategoryTune')}
              data-role="news-list-category-tune"
              {...(onTune ? { onClick: onTune } : {})}
            >
              <SystemGlyph assetId="utility-glyph-family.filter" slotId="asset_slot.utility-glyph-family" />
            </View>
          </View>
        </ScrollView>
      </View>
    )
  }

  const content = (
    <View
      className={reconstructionClass(
        reconstructionStyle('channelDock'),
        variant === 'news-home' && reconstructionStyle('channelDockFixed'),
        dataSelectorClass('production-frame', newsHomeFrameAvailable),
      )}
      data-production-frame={newsHomeFrameAvailable ? 'true' : 'false'}
    >
      {variant === 'news-home' ? (
        <NineSliceFrame
          assetId="news-frame.tile"
          scope="owner"
          slotId="asset_slot.news-frame"
        />
      ) : (
        <NineSliceFrame
          assetId="channel-material-family.default"
          frameWidth={8}
          scope="segment"
          slotId="asset_slot.channel-material-family"
        />
      )}
      {visibleItems.map((item, index) => {
        const selected = item.id === activeId
        return (
          <View
            key={item.id}
            className={reconstructionClass(
              reconstructionStyle('channelCell'),
              selected && reconstructionStyle('channelCellActive'),
              loading && reconstructionStyle('channelCellLoading'),
            )}
            data-role="channel-segment"
            data-selected={selected ? 'true' : 'false'}
            onClick={() => !loading && onSelect?.(item)}
          >
            <View className={reconstructionStyle('channelCellSocket')} data-role="channel-glyph-socket">
              <ProductionAssetGlyph
                assetId={item.glyphAssetId ?? channelGlyphs[index] ?? 'utility-glyph-family.document'}
                className={reconstructionStyle('channelCellGlyph')}
                dataRole="channel-dock-glyph"
                fallbackAssetId={item.fallbackGlyphAssetId ?? channelGlyphs[index] ?? 'utility-glyph-family.document'}
                fallbackSlotId="asset_slot.utility-glyph-family"
                slotId={variant === 'news-home' ? 'asset_slot.news-channel-glyphs' : 'asset_slot.utility-glyph-family'}
              />
            </View>
            {loading ? <View className={reconstructionStyle('channelLabelSkeleton')} /> : <Text className={reconstructionStyle('channelCellLabel')}>{item.label}</Text>}
            {item.count === undefined ? null : <Text className={reconstructionStyle('channelCellCount')}>{item.count}</Text>}
          </View>
        )
      })}
    </View>
  )

  return (
    <View
      className={reconstructionClass(
        variant === 'news-home' && reconstructionStyle('channelDockOwnerNewsHome'),
      )}
      data-owner="channel-dock"
      data-region={region}
    >
      {variant === 'scroll' ? <ScrollView scrollX showScrollbar={false}>{content}</ScrollView> : content}
    </View>
  )
}
