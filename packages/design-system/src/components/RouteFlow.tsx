import { View } from '@tarojs/components'
import type { ComponentProps, ReactNode } from 'react'

import { ownerClass, ownerStyle } from './style'

export interface RouteFlowProps {
  children: ReactNode
  className?: string | undefined
  routeState: string
  variant?: 'default' | 'news' | undefined
}

export interface RouteColumnProps {
  children: ReactNode
  className?: string | undefined
  routeState?: string | undefined
}

export type RouteGridProps = Omit<ComponentProps<typeof View>, 'children' | 'className'> & {
  children: ReactNode
  className?: string | undefined
}

export function RouteFlow({ children, className, routeState, variant = 'default' }: RouteFlowProps) {
  return (
    <View
      className={ownerClass(ownerStyle('routeFlow'), ownerStyle(`routeFlow-${variant}`), className)}
      data-owner="route-flow"
      data-route-state={routeState}
    >
      {children}
    </View>
  )
}

export function RouteColumn({ children, className, routeState }: RouteColumnProps) {
  return (
    <View
      className={ownerClass(ownerStyle('routeColumn'), className)}
      data-owner="route-column"
      data-route-state={routeState}
    >
      {children}
    </View>
  )
}

export function RouteGrid({ children, className, ...props }: RouteGridProps) {
  return (
    <View
      {...props}
      className={ownerClass(ownerStyle('routeGrid'), className)}
    >
      {children}
    </View>
  )
}
