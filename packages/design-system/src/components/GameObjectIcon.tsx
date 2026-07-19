import { Image, Text, View } from '@tarojs/components'
import type { CSSProperties } from 'react'

import type { VerifiedWowObjectReference } from '@wow-mini/domain'

import { resolveRuntimeMediaUrl } from '../runtime-media'
import { ownerClass, ownerStyle } from './style'
import { useTrustedMediaLoadState } from './useTrustedMediaLoadState'

export interface GameObjectIconProps {
  object?: VerifiedWowObjectReference | null | undefined
  size?: number | undefined
  round?: boolean | undefined
  fallbackLabel?: string | undefined
  slotId?: string | undefined
  onClick?: (() => void) | undefined
}

export function GameObjectIcon({
  object,
  size = 44,
  round = false,
  fallbackLabel = '未验证',
  slotId,
  onClick,
}: GameObjectIconProps) {
  const trustedUrl = object?.verified ? resolveRuntimeMediaUrl(object.iconUrl) : ''
  const mediaLoadState = useTrustedMediaLoadState(trustedUrl)
  const canRender = mediaLoadState.visible
  const style = { '--object-size': `${size}px` } as CSSProperties
  return (
    <View
      className={ownerClass(ownerStyle('objectIcon'), round && ownerStyle('objectIconRound'))}
      style={style}
      {...(slotId ? { 'data-slot-id': slotId } : {})}
      {...(onClick ? { onClick } : {})}
    >
      {trustedUrl ? (
        <Image
          className={ownerStyle('objectImage')}
          mode="aspectFill"
          src={trustedUrl}
          onError={mediaLoadState.onError}
          onLoad={mediaLoadState.onLoad}
        />
      ) : null}
      {!canRender ? <Text className={ownerStyle('objectPlaceholder')}>{fallbackLabel.slice(0, 4)}</Text> : null}
      {canRender ? <View className={ownerStyle('objectSourceMarker')} /> : null}
    </View>
  )
}
