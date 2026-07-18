import { Text, View } from '@tarojs/components'

import { assetRuntimePath, type ProductionAssetId } from '@wow-mini/assets-manifest'

import { ActionButton } from './ActionButton'
import { NineSliceFrame } from './NineSliceFrame'
import { ProductionAssetGlyph } from './ProductionAssetGlyph'
import { SystemGlyph } from './SystemGlyph'
import { reconstructionClass, reconstructionStyle } from './reconstruction-style'
import { dataSelectorClass } from './selector-markers'

export interface NewsHomeBriefMetric {
  id: string
  label: string
  value: string
  glyphAssetId: ProductionAssetId
  fallbackGlyphAssetId?: ProductionAssetId | undefined
  available?: boolean | undefined
}

export interface NewsHomeBriefProps {
  dateLabel: string
  statusLabel: string
  sourceLabel: string
  metrics: readonly NewsHomeBriefMetric[]
  loading?: boolean | undefined
  retryAvailable?: boolean | undefined
  region?: string | undefined
  onRetry?: (() => void) | undefined
  onSelectMetric?: ((metric: NewsHomeBriefMetric) => void) | undefined
}

export function NewsHomeBrief({
  dateLabel,
  statusLabel,
  sourceLabel,
  metrics,
  loading = false,
  retryAvailable = false,
  region = 'news-home_target_region_daily-brief',
  onRetry,
  onSelectMetric,
}: NewsHomeBriefProps) {
  const productionEmblemAvailable = Boolean(assetRuntimePath('news-daily-emblem.default'))
  const productionFrameAvailable = Boolean(assetRuntimePath('news-frame.panel'))
  return (
    <View
      className={reconstructionClass(
        reconstructionStyle('newsHomeBrief'),
        dataSelectorClass('production-frame', productionFrameAvailable),
      )}
      data-loading={loading ? 'true' : 'false'}
      data-owner="news-home-brief"
      data-production-frame={productionFrameAvailable ? 'true' : 'false'}
      data-region={region}
    >
      <NineSliceFrame
        assetId="news-frame.panel"
        slotId="asset_slot.news-frame"
      />
      <View className={reconstructionStyle('newsHomeBriefUpper')}>
        <View className={reconstructionStyle('newsHomeBriefEmblemPane')} data-slot-id="asset_slot.news-daily-emblem">
          <View className={reconstructionClass(
            reconstructionStyle('newsHomeBriefEmblem'),
            productionEmblemAvailable && reconstructionStyle('newsHomeBriefEmblemGenerated'),
          )}>
            <ProductionAssetGlyph
              assetId="news-daily-emblem.default"
              fallbackAssetId="utility-glyph-family.records"
              fallbackSlotId="asset_slot.utility-glyph-family"
              className={reconstructionStyle('newsHomeBriefEmblemGlyph')}
              slotId="asset_slot.news-daily-emblem"
            />
            {productionEmblemAvailable ? null : <View className={reconstructionStyle('newsHomeBriefGem')} />}
          </View>
        </View>
        <View className={reconstructionStyle('newsHomeBriefCopy')}>
          <View className={reconstructionStyle('newsHomeBriefTitleRow')} data-role="brief-title-row">
            <Text className={reconstructionStyle('newsHomeBriefTitle')} data-role="brief-title">每日简报</Text>
          </View>
          <View className={reconstructionStyle('newsHomeBriefDateRow')} data-role="brief-date-status-row">
            <Text className={reconstructionClass(reconstructionStyle('newsHomeBriefDate'), loading && reconstructionStyle('newsHomeBriefSkeleton'))} data-role="brief-date">
              {dateLabel}
            </Text>
            <View className={reconstructionStyle('newsHomeBriefStatus')} data-role="brief-status">
              <View className={reconstructionStyle('newsHomeBriefStatusDot')} />
              <Text>{statusLabel}</Text>
            </View>
          </View>
          <View className={reconstructionStyle('newsHomeBriefSourceRow')} data-role="brief-source-row">
            <ProductionAssetGlyph
              assetId="news-evidence-glyph.source"
              className={reconstructionStyle('newsHomeBriefSourceGlyph')}
              fallbackAssetId="utility-glyph-family.source-link"
              fallbackSlotId="asset_slot.utility-glyph-family"
              slotId="asset_slot.news-evidence-glyph"
            />
            <Text className={reconstructionStyle('newsHomeBriefSource')}>{sourceLabel}</Text>
            {retryAvailable && onRetry ? (
              <View className={reconstructionStyle('newsHomeBriefRetry')}>
                <ActionButton ariaLabel="重新加载资讯" variant="ghost" onClick={onRetry}>
                  <SystemGlyph assetId="utility-glyph-family.reset" slotId="asset_slot.utility-glyph-family" />
                </ActionButton>
              </View>
            ) : (
              <SystemGlyph
                assetId="utility-glyph-family.chevron-right"
                className={reconstructionStyle('newsHomeBriefChevron')}
                dataRole="brief-chevron"
                slotId="asset_slot.utility-glyph-family"
              />
            )}
          </View>
        </View>
      </View>
      <View className={reconstructionStyle('newsHomeBriefMetrics')}>
        {metrics.slice(0, 4).map((metric) => (
          <View
            key={metric.id}
            className={reconstructionClass(
              reconstructionStyle('newsHomeBriefMetric'),
              metric.available === false && reconstructionStyle('newsHomeBriefMetricUnavailable'),
            )}
            data-available={metric.available === false ? 'false' : 'true'}
            data-role="news-home-metric"
            onClick={() => metric.available !== false && onSelectMetric?.(metric)}
          >
            <ProductionAssetGlyph
              assetId={metric.glyphAssetId}
              className={reconstructionStyle('newsHomeBriefMetricGlyph')}
              fallbackAssetId={metric.fallbackGlyphAssetId ?? 'utility-glyph-family.document'}
              fallbackSlotId="asset_slot.utility-glyph-family"
              slotId="asset_slot.news-metric-glyphs"
            />
            <Text className={reconstructionStyle('newsHomeBriefMetricLabel')}>{metric.label}</Text>
            <Text className={reconstructionStyle('newsHomeBriefMetricValue')}>{metric.value}</Text>
          </View>
        ))}
      </View>
    </View>
  )
}
