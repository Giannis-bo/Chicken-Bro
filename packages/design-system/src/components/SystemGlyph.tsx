import { View } from '@tarojs/components'
import type { CSSProperties } from 'react'

import { assetRuntimePath, type ProductionAssetId } from '@wow-mini/assets-manifest'

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
  const style = runtimePath
    ? ({ '--system-glyph-url': `url(${runtimePath})` } as CSSProperties)
    : undefined

  return (
    <View
      className={ownerClass(ownerStyle('systemGlyph'), dataSelectorClass('asset-id', assetId), className)}
      data-asset-id={assetId}
      data-asset-missing={runtimePath ? 'false' : 'true'}
      data-role={dataRole}
      data-slot-id={slotId}
      {...(style ? { style } : {})}
    />
  )
}
