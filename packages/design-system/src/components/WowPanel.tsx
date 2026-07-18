import { Text, View } from '@tarojs/components'
import type { ReactNode } from 'react'

import { ownerClass, ownerStyle } from './style'

export type WowPanelVariant = 'default' | 'raised' | 'inset' | 'cockpit' | 'danger'

export interface WowPanelProps {
  children: ReactNode
  variant?: WowPanelVariant | undefined
  title?: string | undefined
  description?: string | undefined
  action?: ReactNode | undefined
  flush?: boolean | undefined
  className?: string | undefined
}

const variantClass: Readonly<Record<WowPanelVariant, string>> = {
  default: '',
  raised: ownerStyle('panelRaised'),
  inset: ownerStyle('panelInset'),
  cockpit: ownerStyle('panelCockpit'),
  danger: ownerStyle('panelDanger'),
}

export function WowPanel({
  children,
  variant = 'default',
  title,
  description,
  action,
  flush = false,
  className,
}: WowPanelProps) {
  return (
    <View
      className={ownerClass(ownerStyle('panel'), variantClass[variant], flush && ownerStyle('panelFlush'), className)}
    >
      {title || action ? (
        <View className={ownerStyle('panelTitleRow')}>
          {title ? <Text className={ownerStyle('panelTitle')}>{title}</Text> : <View />}
          {action}
        </View>
      ) : null}
      {description ? <Text className={ownerStyle('panelDescription')}>{description}</Text> : null}
      {children}
    </View>
  )
}
