import { View } from '@tarojs/components'
import type { ComponentProps, ReactNode } from 'react'

import { ownerClass, ownerStyle } from './style'

export type ActionContentProps = Omit<ComponentProps<typeof View>, 'children' | 'className'> & {
  children: ReactNode
  className?: string | undefined
}

export function ActionContent({ children, className, ...props }: ActionContentProps) {
  return (
    <View {...props} className={ownerClass(ownerStyle('actionContent'), className)}>
      {children}
    </View>
  )
}
