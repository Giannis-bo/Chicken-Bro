import { View } from '@tarojs/components'
import type { ReactNode } from 'react'

import { ownerClass, ownerStyle } from './style'

export interface RouteStageProps {
  children: ReactNode
  className?: string | undefined
  routeState: string
  targetRegionCount: number
  width: 'full' | 'inset'
}

export function RouteStage({ children, className, routeState, targetRegionCount, width }: RouteStageProps) {
  return (
    <View
      className={ownerClass(ownerStyle('routeStage'), ownerStyle(`routeStage-${width}`), className)}
      data-owner="route-stage"
      data-route-state={routeState}
      data-target-region-count={String(targetRegionCount)}
    >
      {children}
    </View>
  )
}
