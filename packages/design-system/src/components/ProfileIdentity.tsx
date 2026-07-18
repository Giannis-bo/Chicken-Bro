import { Image, Text, View } from '@tarojs/components'

import type { AuthUser, ReadinessState } from '@wow-mini/domain'
import { assetRuntimePath } from '@wow-mini/assets-manifest'

import { ActionButton } from './ActionButton'
import { StatusVisual } from './StatusVisual'
import { WowPanel } from './WowPanel'
import { ownerStyle } from './style'

export interface ProfileIdentityProps {
  user: AuthUser
  avatarUrl?: string | undefined
  avatarTrusted?: boolean | undefined
  state: ReadinessState
  modeLabel: string
  actionLabel?: string
  onAction?: () => void
}

export function ProfileIdentity({ user, avatarUrl, avatarTrusted = false, state, modeLabel, actionLabel, onAction }: ProfileIdentityProps) {
  const avatarFramePath = assetRuntimePath('profile-avatar-frame.default')
  return (
    <WowPanel variant="cockpit">
      <View className={ownerStyle('profileHero')}>
        <View
          className={ownerStyle('profileAvatar')}
          data-slot-id="asset_slot.profile-avatar-frame"
          {...(avatarFramePath ? { style: { backgroundImage: `url(${avatarFramePath})` } } : {})}
        >
          {avatarTrusted && avatarUrl
            ? <Image className={ownerStyle('profileAvatarImage')} mode="aspectFill" src={avatarUrl} />
            : <Text data-slot-id="slot-profile-avatar-placeholder">头像</Text>}
        </View>
        <View>
          <Text className={ownerStyle('profileName')}>{user.nickname || '未设置昵称'}</Text>
          <Text className={ownerStyle('profileMeta')}>{modeLabel}</Text>
          <StatusVisual compact state={state} />
        </View>
      </View>
      {actionLabel && onAction ? <ActionButton block variant="secondaryMetal" onClick={onAction}>{actionLabel}</ActionButton> : null}
    </WowPanel>
  )
}
