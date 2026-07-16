import { Image, Text, View } from '@tarojs/components'
import type { CSSProperties } from 'react'

import type { VerifiedWowObjectReference } from '@wow-mini/domain'

import { isTrustedRuntimeMediaUrl } from '../runtime-media'
import { ownerClass, ownerStyle } from './style'

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
  const canRender = Boolean(object?.verified && isTrustedRuntimeMediaUrl(object.iconUrl))
  const style = { '--object-size': `${size}px` } as CSSProperties
  return (
    <View
      className={ownerClass(ownerStyle('objectIcon'), round && ownerStyle('objectIconRound'))}
      style={style}
      {...(slotId ? { 'data-slot-id': slotId } : {})}
      {...(onClick ? { onClick } : {})}
    >
      {canRender ? <Image className={ownerStyle('objectImage')} mode="aspectFit" src={object?.iconUrl ?? ''} /> : null}
      {!canRender ? <Text className={ownerStyle('objectPlaceholder')}>{fallbackLabel.slice(0, 4)}</Text> : null}
      {canRender ? <View className={ownerStyle('objectSourceMarker')} /> : null}
    </View>
  )
}
