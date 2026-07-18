import { Image } from '@tarojs/components'
import { useState } from 'react'

import { assetPromotionStatus, assetRuntimePath, type AssetSlotId, type ProductionAssetId } from '@wow-mini/assets-manifest'

import { SystemGlyph } from './SystemGlyph'
import { dataSelectorClass, selectorClass } from './selector-markers'

export interface ProductionAssetGlyphProps {
  assetId: ProductionAssetId
  slotId: AssetSlotId
  fallbackAssetId: ProductionAssetId
  fallbackSlotId: AssetSlotId
  className?: string | undefined
  dataRole?: string | undefined
  fit?: 'contain' | 'cover' | undefined
}

export function ProductionAssetGlyph({
  assetId,
  slotId,
  fallbackAssetId,
  fallbackSlotId,
  className,
  dataRole,
  fit = 'contain',
}: ProductionAssetGlyphProps) {
  const runtimePath = assetRuntimePath(assetId)
  const [failedRuntimePath, setFailedRuntimePath] = useState('')
  const promotionStatus = assetPromotionStatus(assetId)
  const resolvedClassName = selectorClass(className, dataSelectorClass('asset-id', assetId))
  if (!runtimePath || failedRuntimePath === runtimePath) {
    return (
      <SystemGlyph
        assetId={fallbackAssetId}
        className={resolvedClassName}
        dataRole={dataRole}
        slotId={fallbackSlotId}
      />
    )
  }

  return (
    <Image
      className={resolvedClassName}
      data-asset-fallback="false"
      data-asset-id={assetId}
      data-promotion-status={promotionStatus}
      data-fit={fit}
      data-slot-id={slotId}
      mode={fit === 'cover' ? 'aspectFill' : 'aspectFit'}
      src={runtimePath}
      onError={() => setFailedRuntimePath(runtimePath)}
      onLoad={() => setFailedRuntimePath((current) => current === runtimePath ? '' : current)}
      {...(dataRole ? { 'data-role': dataRole } : {})}
    />
  )
}
