import { Image, Text, View } from '@tarojs/components'
import { useEffect, useState } from 'react'

import { assetPromotionStatus, assetRuntimePath, type AssetSlotId, type ProductionAssetId } from '@wow-mini/assets-manifest'

import { isTrustedRuntimeMediaUrl } from '../runtime-media'
import { SystemGlyph } from './SystemGlyph'
import { dataSelectorClass } from './selector-markers'
import { ownerClass, ownerStyle } from './style'

export type MaterialSourceTrust = 'generated_material' | 'verified_media' | 'placeholder' | 'design_only'
export type MaterialAspect = 'square' | 'wide' | 'banner'

export interface MaterialImageProps {
  source?: string | undefined
  sourceTrust: MaterialSourceTrust
  slotId: string
  alt: string
  fallbackLabel?: string | undefined
  fallbackAssetId?: ProductionAssetId | undefined
  fallbackSlotId?: AssetSlotId | undefined
  fallbackGlyphAssetId?: ProductionAssetId | undefined
  fallbackGlyphSlotId?: AssetSlotId | undefined
  fallbackMode?: 'aspectFill' | 'aspectFit' | undefined
  aspect?: MaterialAspect | undefined
  mode?: 'aspectFill' | 'aspectFit' | undefined
  presentation?: 'surface' | 'socket' | undefined
  className?: string | undefined
  onClick?: (() => void) | undefined
  onRenderModeChange?: ((mode: 'source' | 'fallback') => void) | undefined
}

export function MaterialImage({
  source,
  sourceTrust,
  slotId,
  alt,
  fallbackLabel,
  fallbackAssetId,
  fallbackSlotId,
  fallbackGlyphAssetId,
  fallbackGlyphSlotId,
  fallbackMode = 'aspectFit',
  aspect = 'wide',
  mode = 'aspectFill',
  presentation = 'surface',
  className,
  onClick,
  onRenderModeChange,
}: MaterialImageProps) {
  const [loadFailed, setLoadFailed] = useState(false)

  useEffect(() => {
    setLoadFailed(false)
  }, [source])

  const trustedSource = sourceTrust === 'verified_media'
    ? isTrustedRuntimeMediaUrl(source)
    : Boolean(source)
  const canRender = trustedSource
    && sourceTrust !== 'design_only'
    && sourceTrust !== 'placeholder'
    && !loadFailed
  const fallbackAssetPath = fallbackAssetId ? assetRuntimePath(fallbackAssetId) : null
  const renderMode = canRender ? 'source' : 'fallback'

  useEffect(() => {
    onRenderModeChange?.(renderMode)
  }, [onRenderModeChange, renderMode])

  return (
    <View
      className={ownerClass(
        ownerStyle('material'),
        aspect === 'square' && ownerStyle('materialSquare'),
        aspect === 'wide' && ownerStyle('materialWide'),
        aspect === 'banner' && ownerStyle('materialBanner'),
        presentation === 'socket' && ownerStyle('materialSocket'),
        dataSelectorClass('render-mode', renderMode),
        dataSelectorClass('slot-id', slotId),
        className,
      )}
      data-render-mode={renderMode}
      data-source-trust={sourceTrust}
      data-slot-id={slotId}
      {...(onClick ? { onClick } : {})}
    >
      {canRender ? (
        <Image
          className={ownerStyle('materialImage')}
          mode={mode}
          src={source ?? ''}
          onError={() => setLoadFailed(true)}
        />
      ) : null}
      {!canRender ? (
        <View className={ownerStyle('materialFallback')}>
          {fallbackAssetId && fallbackAssetPath ? (
            <Image
              className={ownerClass(
                ownerStyle('materialFallbackAsset'),
                dataSelectorClass('asset-id', fallbackAssetId),
                fallbackSlotId && dataSelectorClass('slot-id', fallbackSlotId),
              )}
              data-asset-id={fallbackAssetId}
              data-promotion-status={assetPromotionStatus(fallbackAssetId)}
              data-slot-id={fallbackSlotId}
              mode={fallbackMode}
              src={fallbackAssetPath}
            />
          ) : fallbackGlyphAssetId && fallbackGlyphSlotId ? (
            <SystemGlyph
              assetId={fallbackGlyphAssetId}
              className={ownerStyle('materialFallbackGlyph')}
              slotId={fallbackGlyphSlotId}
            />
          ) : null}
          {fallbackAssetPath ? null : <Text className={ownerStyle('materialFallbackLabel')}>{fallbackLabel ?? alt}</Text>}
        </View>
      ) : null}
    </View>
  )
}
