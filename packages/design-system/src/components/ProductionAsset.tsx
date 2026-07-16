import { Image, View } from '@tarojs/components'
import type { CSSProperties } from 'react'

import {
  assetRuntimePath,
  type AssetSlotId,
  type ProductionAssetId,
} from '@wow-mini/assets-manifest'

import { reconstructionClass, reconstructionStyle } from './reconstruction-style'
import { dataSelectorClass } from './selector-markers'

export interface ProductionAssetImageProps {
  assetId: ProductionAssetId
  slotId: AssetSlotId
  alt: string
  className?: string | undefined
  fit?: 'contain' | 'cover' | undefined
  enabled?: boolean | undefined
}

export function ProductionAssetImage({
  assetId,
  slotId,
  alt,
  className,
  fit = 'contain',
  enabled = true,
}: ProductionAssetImageProps) {
  const runtimePath = enabled ? assetRuntimePath(assetId) : null
  if (!runtimePath) {
    return (
      <View
        aria-label={`${alt}（素材待重建）`}
        className={reconstructionClass(
          reconstructionStyle('assetImage'),
          dataSelectorClass('asset-id', assetId),
          dataSelectorClass('slot-id', slotId),
          className,
        )}
        data-asset-fallback="true"
        data-asset-missing="true"
        data-asset-id={assetId}
        data-slot-id={slotId}
      />
    )
  }

  return (
    <Image
      className={reconstructionClass(
        reconstructionStyle('assetImage'),
        dataSelectorClass('asset-id', assetId),
        dataSelectorClass('slot-id', slotId),
        className,
      )}
      data-asset-id={assetId}
      data-asset-fallback="false"
      data-slot-id={slotId}
      mode={fit === 'cover' ? 'aspectFill' : 'aspectFit'}
      src={runtimePath}
    />
  )
}

export interface ProductionAssetSurfaceProps {
  assetId: ProductionAssetId
  slotId: AssetSlotId
  children?: React.ReactNode
  className?: string | undefined
  enabled?: boolean | undefined
  dataRole?: string | undefined
}

export function ProductionAssetSurface({
  assetId,
  slotId,
  children,
  className,
  enabled = true,
  dataRole,
}: ProductionAssetSurfaceProps) {
  const runtimePath = enabled ? assetRuntimePath(assetId) : null
  const style = runtimePath
    ? ({ '--production-asset-url': `url(${runtimePath})` } as CSSProperties)
    : undefined

  return (
    <View
      className={reconstructionClass(
        reconstructionStyle('assetSurface'),
        dataSelectorClass('asset-id', assetId),
        dataSelectorClass('slot-id', slotId),
        className,
      )}
      data-asset-fallback={runtimePath ? 'false' : 'true'}
      data-asset-missing={runtimePath ? 'false' : 'true'}
      data-role={dataRole}
      data-slot-id={slotId}
      data-asset-id={assetId}
      {...(style ? { style } : {})}
    >
      {children}
    </View>
  )
}
