import { Image, View } from '@tarojs/components'
import type { CSSProperties } from 'react'

import {
  assetRuntimePath,
  assetPromotionStatus,
  type AssetSlotId,
  type ProductionAssetId,
} from '@wow-mini/assets-manifest'

import { reconstructionClass, reconstructionStyle } from './reconstruction-style'
import { dataSelectorClass } from './selector-markers'

export interface NineSliceFrameProps {
  assetId: ProductionAssetId
  slotId: AssetSlotId
  className?: string | undefined
  frameWidth?: number | undefined
  sliceInset?: number | undefined
  scope?: 'owner' | 'segment' | 'control' | undefined
}

const frameProfiles: Partial<Record<ProductionAssetId, { frameWidth: number; renderMode: 'full-frame' | 'nine-slice'; sliceInset: number }>> = {
  'news-frame.panel': { frameWidth: 0, renderMode: 'full-frame', sliceInset: 0 },
  'news-frame.media': { frameWidth: 0, renderMode: 'full-frame', sliceInset: 0 },
  'news-frame.tile': { frameWidth: 0, renderMode: 'full-frame', sliceInset: 0 },
  'news-frame.feed': { frameWidth: 0, renderMode: 'full-frame', sliceInset: 0 },
  'news-frame.tab': { frameWidth: 0, renderMode: 'full-frame', sliceInset: 0 },
}

export function NineSliceFrame({
  assetId,
  slotId,
  className,
  frameWidth,
  sliceInset,
  scope = 'owner',
}: NineSliceFrameProps) {
  const runtimePath = assetRuntimePath(assetId)
  const promotionStatus = assetPromotionStatus(assetId)
  if (!runtimePath) return null

  const profile = frameProfiles[assetId]
  const resolvedFrameWidth = frameWidth ?? profile?.frameWidth ?? 12
  const resolvedSliceInset = sliceInset ?? profile?.sliceInset ?? 64

  if (profile?.renderMode === 'full-frame') {
    return (
      <Image
        aria-hidden
        className={reconstructionClass(
          reconstructionStyle('fullFrameLayer'),
          dataSelectorClass('asset-id', assetId),
          dataSelectorClass('material-render', 'full-frame'),
          dataSelectorClass('slot-id', slotId),
          className,
        )}
        data-asset-id={assetId}
        data-frame-scope={scope}
        data-material-render="full-frame"
        data-promotion-status={promotionStatus}
        data-slot-id={slotId}
        mode="scaleToFill"
        src={runtimePath}
      />
    )
  }

  const style = {
    '--nine-slice-source': `url(${runtimePath})`,
    '--nine-slice-width': `${resolvedFrameWidth}px`,
    '--nine-slice-inset': resolvedSliceInset,
  } as CSSProperties

  return (
    <View
      aria-hidden
      className={reconstructionClass(
        reconstructionStyle('nineSliceFrame'),
        dataSelectorClass('asset-id', assetId),
        dataSelectorClass('material-render', 'nine-slice'),
        dataSelectorClass('slot-id', slotId),
        className,
      )}
      data-asset-id={assetId}
      data-frame-width={resolvedFrameWidth}
      data-frame-scope={scope}
      data-material-render="nine-slice"
      data-promotion-status={promotionStatus}
      data-slot-id={slotId}
      style={style}
    />
  )
}
