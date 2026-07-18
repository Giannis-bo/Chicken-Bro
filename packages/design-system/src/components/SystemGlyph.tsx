import { Image, View } from '@tarojs/components'

import { assetPromotionStatus, assetRuntimePath, type ProductionAssetId } from '@wow-mini/assets-manifest'

import { dataSelectorClass } from './selector-markers'
import { ownerClass, ownerStyle } from './style'

interface SystemGlyphProps {
  assetId: ProductionAssetId
  slotId: string
  className?: string | undefined
  dataRole?: string | undefined
}

export function SystemGlyph({ assetId, slotId, className, dataRole }: SystemGlyphProps) {
  const runtimePath = assetRuntimePath(assetId)
  const promotionStatus = assetPromotionStatus(assetId)
  const resolvedClassName = ownerClass(ownerStyle('systemGlyph'), dataSelectorClass('asset-id', assetId), className)

  if (!runtimePath) {
    return (
      <View
        className={resolvedClassName}
        data-asset-id={assetId}
        data-asset-missing="true"
        data-promotion-status={promotionStatus}
        data-role={dataRole}
        data-slot-id={slotId}
      />
    )
  }

  return (
    <Image
      className={resolvedClassName}
      data-asset-id={assetId}
      data-asset-missing="false"
      data-promotion-status={promotionStatus}
      data-role={dataRole}
      data-slot-id={slotId}
      mode="aspectFit"
      src={runtimePath}
    />
  )
}
